#!/usr/bin/env python3
"""Originate a pick + both win probabilities for every open Hotspawn CS2 fixture (session f323b4a7).

Probability ladder (first rung that resolves wins; the rung used is printed on every row):

  A  Pinnacle whole-match moneyline, proportional margin removal (sharp bookmaker).
     Source: the public guest JSON that pinnacle.com's own CS2 page loads, captured
     2026-10-15T22:41:17Z and stored in this repository.
  B  Polymarket match-winner price, normalised (prediction market - not a bookmaker).
     Snapshot 2026-10-15T22:41:17Z for the rows that existed then; the Aurora-9z row was
     re-read live at 2026-10-16T04:23:06Z (see data/fresh_reads.json).
  C  Our own line: Valve Regional Standings points on Valve's curve
     P = 1/(1+10^(-k*dPoints/400)) with k = 0.4598, the slope fitted by maximum likelihood
     on Valve's own published match results (13,609 train / 901 held-out windows;
     held-out log-loss 0.6395 fitted vs 0.6541 raw).  See hotspawn/data/calibration.json.
  D  Unresolved: no outside price and a team missing from Valve's standings -> pick blank + flagged.

Hotspawn's crowd pick share is NEVER a probability input.  It is stored as "ownership" and is
used only by the leaderboard rule, which is labelled as a strategy opinion, not a probability.
"""
from __future__ import annotations

import csv
import datetime
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent
K = 0.4598                      # hotspawn/data/calibration.json (fitted on Valve's results)
CALIB_URL = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
             "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md")

# Generic-word normalisation, identical in spirit to the rule the repository's other boards use
# ("Team", "Esports", "Gaming", "GG" carry no identity).  Every non-generic equivalence below is a
# *verified* alias from hotspawn/research/aliases.json, which records the HLTV/Pinnacle evidence.
GENERIC = {"team", "esports", "esport", "gaming", "gg", "club", "cs", "cs2"}
VERIFIED_ALIASES = {          # hotspawn/research/aliases.json
    "roundsgg": "rounds", "wrotberry": "wbt", "wrotberry": "wbt",
}


def key(name: str) -> str:
    import re
    name = "".join(c for c in name.lower() if c.isalnum() or c == " ")
    toks = [t for t in name.split() if t not in GENERIC]
    k = "".join(toks)
    return VERIFIED_ALIASES.get(k, k)


def devig(oa: float, ob: float):
    """Proportional margin removal; returns (p_a, p_b, overround_pct) or None."""
    try:
        a, b = float(oa), float(ob)
    except (TypeError, ValueError):
        return None
    if a <= 1.0 or b <= 1.0:
        return None
    ia, ib = 1.0 / a, 1.0 / b
    tot = ia + ib
    if tot < 0.98 or tot > 1.25:
        return None
    return ia / tot, ib / tot, (tot - 1.0) * 100.0


def own_line(pa: float, pb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-K * (pa - pb) / 400.0))


def clamp(x: float) -> float:
    return max(0.005, min(0.995, x))


def main() -> int:
    src = json.load(open(DATA / "sources.json"))
    fresh = json.load(open(DATA / "fresh_reads.json")) if (DATA / "fresh_reads.json").exists() else {}
    vrs = {key(k): v for k, v in src["vrs"].items()}
    hltv = {key(k): v for k, v in src["hltv"].items()}
    lines = dict(src.get("lines") or {})
    # When the collector ran live it stores unjoined quotes; join them by normalised team name.
    for kind, field_a, field_b in (("polymarket_raw", "price_a", "price_b"),
                                   ("pinnacle_raw", "home", "away")):
        for q in (src.get("lines_raw") or {}).get(kind, []):
            teams = q.get("teams")
            names = (teams if teams else (q.get("a"), q.get("b")))
            if not names or not names[0] or not names[1]:
                continue
            ka, kb = key(names[0]), key(names[1])
            qend = q.get("end") or q.get("cutoff")
            for f in src["fixtures"]:
                if {key(f["team_a"]), key(f["team_b"])} != {ka, kb}:
                    continue
                if qend and f.get("lock_utc"):
                    import datetime as _dt
                    def _p(x):
                        return _dt.datetime.strptime(x[:19], "%Y-%m-%dT%H:%M:%S").replace(
                            tzinfo=_dt.timezone.utc)
                    if abs((_p(qend) - _p(f["lock_utc"])).total_seconds()) > 30 * 3600:
                        continue
                    e = lines.setdefault(f["match_id"], {})
                    if kind == "polymarket_raw":
                        e["polymarket_price_a"] = q["price_a"] if key(f["team_a"]) == ka else q["price_b"]
                        e["polymarket_price_b"] = q["price_b"] if key(f["team_a"]) == ka else q["price_a"]
                        e["polymarket_url"] = q.get("url")
                        e["polymarket_read_utc"] = q.get("updated")
                        if q.get("format"):
                            e["format"] = q["format"]
                            e["format_source"] = "Polymarket market title"
                    else:
                        e["pinnacle_odds_a"] = q["home"] if key(f["team_a"]) == ka else q["away"]
                        e["pinnacle_odds_b"] = q["away"] if key(f["team_a"]) == ka else q["home"]
                        e["pinnacle_read_utc"] = q.get("cutoff")
                    break
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixtures = [f for f in src["fixtures"] if f["lock_utc"] > now]

    rows, unresolved, flags = [], [], []
    for f in fixtures:
        ka, kb = key(f["team_a"]), key(f["team_b"])
        va, vb = vrs.get(ka), vrs.get(kb)
        ha, hb = hltv.get(ka), hltv.get(kb)
        L = dict(lines.get(f["match_id"]) or {})
        fr = fresh.get(f["match_id"]) or {}
        if fr.get("polymarket_a") is not None:
            L["polymarket_price_a"] = fr["polymarket_a"]
            L["polymarket_price_b"] = fr["polymarket_b"]
            L["polymarket_url"] = fr.get("url")
            L["polymarket_read_utc"] = fr.get("read_utc")
        for side in ("a", "b"):
            if fr.get(f"hltv_rank_{side}") is not None:
                hltv.setdefault(ka if side == "a" else kb, {})["rank"] = fr[f"hltv_rank_{side}"]
                hltv[ka if side == "a" else kb]["url"] = fr.get("url")
        if fr.get("pinnacle_odds_a"):
            L["pinnacle_odds_a"] = fr["pinnacle_odds_a"]
            L["pinnacle_odds_b"] = fr["pinnacle_odds_b"]
            L["pinnacle_read_utc"] = fr.get("read_utc")

        rung = None
        p_a = p_b = None
        basis = ""
        market_p = None
        own_p = None
        detail = {}

        dv = devig(L.get("pinnacle_odds_a"), L.get("pinnacle_odds_b")) if L.get("pinnacle_odds_a") else None
        if dv:
            rung, p_a, p_b = "A", clamp(dv[0]), clamp(dv[1])
            basis = "Pinnacle moneyline, margin removed proportionally"
            market_p = p_a
            detail["pinnacle"] = {"odds_a": L["pinnacle_odds_a"], "odds_b": L["pinnacle_odds_b"],
                                  "overround_pct": round(dv[2], 2)}
        else:
            try:
                pa = float(L.get("polymarket_price_a"))
                pb = float(L.get("polymarket_price_b"))
            except (TypeError, ValueError):
                pa = pb = None
            if pa is not None and pa + pb > 0:
                tot = pa + pb
                rung, p_a, p_b = "B", clamp(pa / tot), clamp(pb / tot)
                basis = "Polymarket match-winner price, normalised"
                market_p = p_a
                detail["polymarket"] = {"price_a": pa, "price_b": pb, "raw_sum": round(tot, 4)}
            elif va and vb:
                rung = "C"
                p_a = clamp(own_line(va["points"], vb["points"]))
                p_b = 1.0 - p_a
                basis = "Own line from Valve Regional Standings points (k=0.4598)"
            else:
                rung = "D"

        if va and vb:
            own_p = clamp(own_line(va["points"], vb["points"]))

        consensus = None
        ests = [x for x in (market_p, own_p) if x is not None]
        if ests:
            consensus = sum(ests) / len(ests)

        fmt = L.get("format") or (f"BO{f['best_of']}" if f.get("best_of") else None) \
            or (src.get("formats") or {}).get(f["match_id"], {}).get("format")
        row = {
            "match_id": f["match_id"], "competition": f["competition"], "tier": f["tier"],
            "points": f["offered_points"], "start_utc": f["start_utc"], "lock_utc": f["lock_utc"],
            "team_a": f["team_a"], "team_b": f["team_b"], "rung": rung, "basis": basis,
            "p_a": round(p_a, 4) if p_a is not None else None,
            "p_b": round(p_b, 4) if p_b is not None else None,
            "market_p_a": round(market_p, 4) if market_p is not None else None,
            "own_p_a": round(own_p, 4) if own_p is not None else None,
            "consensus_p_a": round(consensus, 4) if consensus is not None else None,
            "vrs_points_a": va["points"] if va else None, "vrs_points_b": vb["points"] if vb else None,
            "vrs_standing_a": va["standing"] if va else None, "vrs_standing_b": vb["standing"] if vb else None,
            "hltv_rank_a": (ha or {}).get("rank"), "hltv_rank_b": (hb or {}).get("rank"),
            "crowd_a_ownership_pct": f["crowd_a_pct"], "crowd_b_ownership_pct": f["crowd_b_pct"],
            "total_picks": f["total_picks"],
            "format": fmt,
            "format_source": L.get("format_source")
            or (src.get("formats") or {}).get(f["match_id"], {}).get("format_source"),
            "hotspawn_url": f["hotspawn_url"] or "https://play.hotspawn.com/lobby",
            "polymarket_url": L.get("polymarket_url"), "pinnacle_url": L.get("pinnacle_url"),
            "polymarket_read_utc": L.get("polymarket_read_utc"),
            "pinnacle_read_utc": L.get("pinnacle_read_utc"),
            "detail": detail,
        }
        row["pick"] = (f["team_a"] if p_a is not None and p_a >= 0.5 else
                       f["team_b"] if p_b is not None else None)
        fl = []
        if rung == "C":
            fl.append("NO_MARKET")
        if rung in ("A", "B") and own_p is not None:
            if abs(market_p - own_p) >= 0.10 or (market_p >= 0.5) != (own_p >= 0.5):
                fl.append("MODEL_MARKET_SPLIT")
        if p_a is not None and 0.45 <= max(p_a, p_b) <= 0.55:
            fl.append("COIN_FLIP")
        if own_p is None:
            fl.append("NO_OWN_LINE")
        if not fmt:
            fl.append("FORMAT_UNKNOWN")
        if f["lock_utc"] < "2026-10-14T00:00:00Z":
            fl.append("STALE_LISTING")
        row["flags"] = ";".join(fl)
        rows.append(row)

        if rung == "D" or row["pick"] is None:
            unresolved.append({
                "match_id": f["match_id"], "team_a": f["team_a"], "team_b": f["team_b"],
                "competition": f["competition"], "tier": f["tier"], "lock_utc": f["lock_utc"],
                "limitation": ("No outside price (Pinnacle/Polymarket) and at least one team is "
                               "absent from Valve's Regional Standings, so no own line can be "
                               "originated."),
                "sources_tried": ["Pinnacle guest CS2 markets", "Polymarket counter-strike series",
                                  "Valve Regional Standings 2026-10-05",
                                  "HLTV world ranking", "HLTV match/event pages"],
                "hotspawn_url": row["hotspawn_url"]})

    # ------------------------------------------------------------------ leaderboard rule
    for row in rows:
        ca = row["consensus_p_a"]
        dog_p = None
        if ca is not None:
            dog_p = 1.0 - ca if ca >= 0.5 else ca
        crowd_dog = None
        if ca is not None and row["crowd_a_ownership_pct"] is not None:
            crowd_dog = (row["crowd_b_ownership_pct"] if ca >= 0.5 else row["crowd_a_ownership_pct"])
        cls, play, note = "CHALK", row["pick"], "Favourite is likelier and not outvoted; take the chalk."
        if dog_p is not None and crowd_dog is not None:
            if crowd_dog > 50.0:
                cls, play, note = "VALUE", row["pick"], "Crowd majority already sits on the underdog, so the favourite is both likelier and the lower-owned side."
            elif dog_p >= 0.38 and crowd_dog <= dog_p * 100 - 10:
                cls, play, note = "CONTRARIAN", (row["team_b"] if ca >= 0.5 else row["team_a"]), "Underdog has a real chance (consensus >= 38%) and is owned 10+ points below that chance."
            elif dog_p >= 0.30 and crowd_dog <= dog_p * 100 / 2:
                cls, play, note = "SITUATIONAL", (row["team_b"] if ca >= 0.5 else row["team_a"]), "Underdog chance >= 30% with half-or-less ownership."
            elif dog_p >= 0.20 and crowd_dog <= 10:
                cls, play, note = "LONG SHOT", row["pick"], "Underdog is live (>= 20%) but barely owned; optional punt only."
        row["leaderboard_class"] = cls
        row["leaderboard_pick"] = play
        row["leaderboard_note"] = note

    DATA.mkdir(exist_ok=True)
    with open(DATA / "picks.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k in rows[0] if k != "detail"])
        w.writeheader()
        for r in rows:
            w.writerow({k: v for k, v in r.items() if k != "detail"})
    with open(DATA / "unresolved.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(unresolved[0].keys()) if unresolved else
                           ["match_id", "team_a", "team_b", "competition", "tier", "lock_utc",
                            "limitation", "sources_tried", "hotspawn_url"])
        w.writeheader()
        for r in unresolved:
            w.writerow(r)

    summary = {
        "generated_utc": now, "fixtures_total": len(src["fixtures"]), "open": len(rows),
        "open_with_pick": sum(1 for r in rows if r["pick"]), "unresolved": len(unresolved),
        "rungs": {r: sum(1 for x in rows if x["rung"] == r) for r in "ABCD"},
        "classes": {c: sum(1 for r in rows if r["leaderboard_class"] == c)
                    for c in ("VALUE", "CONTRARIAN", "SITUATIONAL", "LONG SHOT", "CHALK")},
        "s_tier": [{"match_id": r["match_id"], "teams": [r["team_a"], r["team_b"]],
                    "pick": r["pick"], "p_a": r["p_a"], "p_b": r["p_b"], "rung": r["rung"],
                    "lock_utc": r["lock_utc"]} for r in rows if r["tier"] == "S"],
        "k": K, "k_source": "MLE on Valve's published match results (hotspawn/data/calibration.json)",
        "vrs_as_of": src.get("vrs_as_of", "see sources.json"),
        "vrs_url": (list(vrs.values())[0]["url"] if vrs else CALIB_URL),
        "lines_snapshot_utc": src["lines_snapshot_utc"],
        "hotspawn_read_utc": src["live_capture"].get("read_utc"),
        "hotspawn_week_text": src["live_capture"].get("week_text"),
        "hotspawn_tier_text": src["live_capture"].get("tier_text"),
        "next_lock_utc": (sorted(rows, key=lambda r: r["lock_utc"])[0]["lock_utc"] if rows else None),
    }
    json.dump(summary, open(DATA / "summary.json", "w"), indent=1)
    json.dump({"rows": rows, "summary": summary}, open(DATA / "board.json", "w"), indent=1)
    print(json.dumps(summary, indent=1)[:1800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
