#!/usr/bin/env python3
"""Originate a pick, both teams' win probabilities and a leaderboard play for every Hotspawn CS2
fixture — session ``arena/a6f05f99``.

Probability ladder (every rung that answers is kept; the pick is the CONSENSUS of the independent
answers, and each answer is shown on the page with the link it came from):

  Rung 1  Pinnacle whole-match moneyline, margin removed proportionally (sharp bookmaker)
  Rung 2  bo3.gg's relayed bookmaker price (the provider is named in bo3.gg's own payload) — the
          rung that reaches the low-tier leagues the sharp book does not price
  Rung 3  Polymarket match-winner price, normalised (a prediction market, NOT a bookmaker)
  Rung 4  Our own line: official Valve Regional Standings points on the calibrated Valve curve,
          cross-checked against the HLTV world ranking
  Rung 5  Unresolved — nothing answered and at least one team is missing from Valve's standings

Hotspawn's crowd pick share is NEVER a probability input.  It is carried as ``ownership`` and is
used only to measure how contrarian a play is.

Leaderboard rule (v3).  Identical thresholds to rule v2 (written by session arena/22be6967) —
deliberately NOT retuned on day 2, because day 2 produced one contrarian win and one contrarian
loss on near-identical signals, which is noise at n = 3, not evidence.  What v3 adds is that the
underdog's "real chance" is the consensus of up to four independent estimates instead of two, so
the edge the rule acts on is better measured:

  VALUE         crowd majority sits on the consensus underdog -> play the favourite
  CONTRARIAN    consensus underdog >= 38%, every estimate >= 30%, crowd share at least 10 points
                below its chance -> play the underdog
  SITUATIONAL   consensus underdog >= 30%, every estimate >= 25%, crowd share at most half its
                chance, a strong/moderate verified factor against the favourite and none against
                the underdog -> play the underdog
  LONG SHOT     underdog >= 20% with <= 10% of the crowd -> keep the favourite, listed as a punt
  CHALK         otherwise -> play the favourite
  NO CROWD DATA Hotspawn published no crowd share -> the published pick is the play
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, RESEARCH, Aliases, K_VALVE, K_VALVE_PROVENANCE, american_to_decimal,  # noqa: E402
                    devig_two_way, hours_between, mean, normalise_prices, own_line, parse_iso,
                    read_json, write_csv, write_json)

MAX_KICKOFF_GAP_H = 6.0
STALE_AFTER_H = 36.0
STALE_PRICE_H = 8.0
SPLIT_PP = 10.0
CONTRARIAN_MIN_P, CONTRARIAN_MIN_SRC, CONTRARIAN_MIN_GAP = 0.38, 0.30, 0.10
SITUATIONAL_MIN_P, SITUATIONAL_MIN_SRC = 0.30, 0.25
LONGSHOT_MIN_P, LONGSHOT_MAX_CROWD = 0.20, 0.10
COUNTING_STRENGTH = ("strong", "moderate")
MANUAL: dict = {}

RUNG_LABEL = {
    "1": "Pinnacle moneyline, margin removed (sharp bookmaker)",
    "2": "Bookmaker price relayed by bo3.gg",
    "3": "Polymarket prediction-market price, normalised",
    "4": "Our own line from official Valve Regional Standings points",
    "5": "Unresolved - no outside price and no official rating for one or both teams",
}
RUNG_SHORT = {"1": "Pinnacle", "2": "Bookmaker (bo3.gg)", "3": "Polymarket",
              "4": "Our own line", "5": "Unresolved"}

FLAG_TEXT = {
    "KICKOFF_GAP": "The outside source lists a slightly different kickoff than Hotspawn; joined because both teams match and the gap is under six hours.",
    "ALIAS": "A team name was joined through a verified alias (evidence in research/aliases.json).",
    "SPLIT": "The independent estimates disagree by ten points or more; the pick is the average of them.",
    "VRS_ROSTER_OUTDATED": "A verified roster change post-dates Valve's newest standings, so Valve points describe a different five; the own line is left out of the average.",
    "NO_VRS_TEAM": "At least one team is missing from Valve's official standings, so no own line could be made.",
    "FORMAT_UNKNOWN": "No source stated the series length; nothing was assumed.",
    "UNRESOLVED": "No outside price and no official rating for one or both teams - the pick is left blank on purpose.",
    "STALE_PRICE": "The outside price was read more than eight hours before this page was built.",
    "LOCKED": "Lock time has passed; kept for grading, not a live pick.",
    "STALE_LISTING": "Hotspawn still lists the fixture although its lock time passed more than 36 hours ago.",
    "CROWD_MISSING": "Hotspawn published no crowd share, so no contrarian play is offered.",
    "COIN_FLIP": "The two sides are within one point of even; the pick follows the consensus.",
    "HOTSPAWN_PARTIAL": "Not every Hotspawn page was read successfully in this capture.",
    "MANUAL_READ": "Includes a bookmaker price read and verified by hand against the source page (recorded with the URL and the exact time it was read); the scheduled collector re-reads it automatically.",
    "SINGLE_SOURCE": "Only one independent source could be found for this fixture, so the probability rests on it alone.",
    "DUPLICATE_LISTING": "The same pairing and kickoff appears twice in Hotspawn's payload under two ids.",
}


# ---------------------------------------------------------------------------------------- inputs
def load_inputs() -> dict:
    global MANUAL
    MANUAL = read_json(RESEARCH / "manual_lines.json", {}) or {}
    return {
        "capture": read_json(DATA / "capture.json", {}) or {},
        "aliases": Aliases(),
        "twc": read_json(RESEARCH / "twc2026.json", {}) or {},
        "factors": (read_json(RESEARCH / "factors.json", {}) or {}).get("factors", []),
    }


def status_of(fx: dict, now: str) -> str:
    lock, start = fx.get("lock_utc"), fx.get("start_utc")
    h = hours_between(lock or start, now)
    if h is None:
        return "unknown"
    if h > 0:
        return "open"
    return "locked" if h > -STALE_AFTER_H else "stale"


def match_quote(fx: dict, quotes: list, aliases: Aliases, a_field="team_a", b_field="team_b"):
    """Best quote for the fixture: both teams equal after aliasing, kickoff within six hours."""
    ka, kb = aliases.key(fx["team_a"]), aliases.key(fx["team_b"])
    best, best_gap = None, None
    for q in quotes or []:
        qa, qb = aliases.key(q.get(a_field, "")), aliases.key(q.get(b_field, ""))
        if not qa or not qb or ka == kb or {qa, qb} != {ka, kb}:
            continue
        gap = hours_between(q.get("start_utc"), fx.get("start_utc"))
        if gap is None or abs(gap) > MAX_KICKOFF_GAP_H:
            continue
        if best is None or abs(gap) < abs(best_gap):
            best, best_gap = dict(q), gap
            best["flipped"] = (qa != ka)
            best["gap_h"] = round(gap, 2)
    alias = bool(best) and any(aliases.used(n) for n in
                               (fx["team_a"], fx["team_b"], best.get(a_field, ""), best.get(b_field, "")))
    return best, alias


def active_factors(team_key: str, start_utc: str, factors: list) -> list:
    start = parse_iso(start_utc)
    out = []
    for f in factors:
        if f.get("team") != team_key:
            continue
        until = parse_iso(f"{f['relevant_until']}T23:59:59Z") if f.get("relevant_until") else None
        if start and until and start > until:
            continue
        out.append(f)
    return out


def strong_factors(team_key: str, start_utc: str, factors: list) -> list:
    return [f for f in active_factors(team_key, start_utc, factors)
            if f.get("strength") in COUNTING_STRENGTH]


# ----------------------------------------------------------------------------------- estimates
def estimates_for(fx: dict, capture: dict, aliases: Aliases, flags: list,
                 factors: list) -> list[dict]:
    """Every independent probability we can originate for this fixture, best-labelled."""
    out: list[dict] = []

    pin, alias = match_quote(fx, capture.get("pinnacle", {}).get("quotes", []), aliases)
    if pin:
        oa = american_to_decimal(pin.get("american_a"))
        ob = american_to_decimal(pin.get("american_b"))
        pair = devig_two_way(oa, ob)
        if pair:
            pa, pb, ovr = pair
            if pin.get("flipped"):
                pa, pb = pb, pa
            out.append({"rung": "1", "label": RUNG_LABEL["1"], "short": RUNG_SHORT["1"],
                        "p_a": pa, "p_b": pb,
                        "detail": f"{oa:.3f} / {ob:.3f} (overround {ovr:.1f}%)",
                        "url": pin.get("source_url"), "read_utc": pin.get("read_utc"),
                        "source": "Pinnacle"})
            if alias:
                flags.append("ALIAS")

    bo, alias = None, False
    bo3_rows = []
    for m in capture.get("bo3", {}).get("matches", []):
        q = m.get("quote")
        if not q:
            continue
        row = {"team_a": m.get("team_a"), "team_b": m.get("team_b"), "start_utc": m.get("start_utc"),
               "source": "bo3.gg", "kind": "bookmaker_relayed", "odds_a": q.get("coeff_1"),
               "odds_b": q.get("coeff_2"), "provider": q.get("provider"),
               "source_url": m.get("source_url"), "read_utc": m.get("read_utc"),
               "best_of": m.get("best_of"), "tournament": m.get("tournament")}
        bo3_rows.append(row)
    bo, alias = match_quote(fx, bo3_rows, aliases)
    if bo:
        pair = devig_two_way(bo.get("odds_a"), bo.get("odds_b"))
        if pair:
            pa, pb, ovr = pair
            if bo.get("flipped"):
                pa, pb = pb, pa
            prov = bo.get("provider") or "bookmaker"
            out.append({"rung": "2", "label": RUNG_LABEL["2"], "short": f"{prov} (via bo3.gg)",
                        "p_a": pa, "p_b": pb,
                        "detail": (f"{float(bo['odds_a']):.3f} / {float(bo['odds_b']):.3f} "
                                   f"(overround {ovr:.1f}%)"),
                        "url": bo.get("source_url"), "read_utc": bo.get("read_utc"),
                        "source": prov})
            if alias:
                flags.append("ALIAS")
            if bo.get("best_of") and not fx.get("best_of"):
                fx["best_of"] = bo["best_of"]
                fx["format_source"] = bo.get("source_url")

    pm, alias = match_quote(fx, capture.get("polymarket", {}).get("quotes", []), aliases)
    if pm:
        pair = normalise_prices(pm.get("price_a"), pm.get("price_b"))
        if pair:
            pa, pb = pair
            if pm.get("flipped"):
                pa, pb = pb, pa
            out.append({"rung": "3", "label": RUNG_LABEL["3"], "short": RUNG_SHORT["3"],
                        "p_a": pa, "p_b": pb,
                        "detail": f"{float(pm['price_a']):.3f} / {float(pm['price_b']):.3f} (market price)",
                        "url": pm.get("source_url"), "read_utc": pm.get("read_utc"),
                        "source": "Polymarket"})
            if pm.get("format") and not fx.get("best_of"):
                fx["best_of"] = int(pm["format"].replace("BO", ""))
                fx["format_source"] = pm.get("source_url")
            if alias:
                flags.append("ALIAS")

    for entry in MANUAL.get("entries", []):
        if aliases.key(entry.get("team_a")) == aliases.key(fx["team_a"]) and \
                aliases.key(entry.get("team_b")) == aliases.key(fx["team_b"]):
            pair = devig_two_way(entry.get("odds_a"), entry.get("odds_b")) or \
                (normalise_prices(entry.get("odds_a"), entry.get("odds_b")) + (0.0,)
                 if normalise_prices(entry.get("odds_a"), entry.get("odds_b")) else None)
            if pair:
                pa, pb = pair[0], pair[1]
                out.append({"rung": "2", "label": RUNG_LABEL["2"], "short": entry.get("source"),
                            "p_a": pa, "p_b": pb,
                            "detail": f"{float(entry['odds_a']):.3f} / {float(entry['odds_b']):.3f}"
                                      f" ({entry.get('note', 'hand-verified read').strip()})",
                            "url": entry.get("url"), "read_utc": entry.get("read_utc"),
                            "source": entry.get("source"), "manual": True})
                flags.append("MANUAL_READ")
            break

    vrs = {aliases.key(t.get("name")): t for t in capture.get("vrs", {}).get("teams", [])}
    ka, kb = aliases.key(fx["team_a"]), aliases.key(fx["team_b"])
    ta, tb = vrs.get(ka), vrs.get(kb)
    if ta and tb:
        p = own_line(ta.get("points"), tb.get("points"))
        if p is not None:
            roster_old = any(
                (f.get("kind", "").startswith("roster change") or "stand-in" in f.get("kind", ""))
                and f.get("strength") == "strong"
                for f in strong_factors(ka, fx.get("start_utc"), factors) +
                strong_factors(kb, fx.get("start_utc"), factors))
            out.append({
                "rung": "4", "label": RUNG_LABEL["4"], "short": RUNG_SHORT["4"],
                "p_a": p, "p_b": 1.0 - p,
                "detail": f"Valve points {ta.get('points')} vs {tb.get('points')} "
                          f"(ranks {ta.get('rank')} / {tb.get('rank')})",
                "url": capture.get("vrs", {}).get("blob_url")
                       or capture.get("vrs", {}).get("url"),
                "read_utc": capture.get("vrs", {}).get("read_utc"), "source": "Valve standings",
                "roster_outdated": roster_old})
    else:
        flags.append("NO_VRS_TEAM")
    return out


# ------------------------------------------------------------------------------------ strategy
def strategy(row: dict, factors: list) -> dict:
    pa = row.get("consensus_a")
    if pa is None:
        return {"class": "UNRESOLVED", "play": None,
                "reason": "No probability could be originated for this fixture."}
    a_fav = pa >= 0.5
    p_fav = pa if a_fav else 1 - pa
    p_dog = 1 - p_fav
    fav = row["team_a"] if a_fav else row["team_b"]
    dog = row["team_b"] if a_fav else row["team_a"]
    crowd = row.get("crowd_fav_pct")
    if crowd is None:
        return {"class": "NO CROWD DATA", "play": fav,
                "reason": "Hotspawn published no crowd share for this fixture."}
    ests = row.get("estimates") or []
    min_dog = min(min(e["p_a"], e["p_b"]) * (1 if True else 1) for e in ests) if ests else None
    # lowest estimate for the underdog, expressed on the underdog's own side
    lows = []
    for e in ests:
        low_fav = max(e["p_a"], e["p_b"])
        lows.append(1 - low_fav)
    min_dog = min(lows) if lows else None
    edge = p_dog - crowd / 100.0
    factors_vs_fav = strong_factors(row["key_fav"], row.get("start_utc"), factors)
    factors_vs_dog = strong_factors(row["key_dog"], row.get("start_utc"), factors)

    if crowd < 50:
        return {"class": "VALUE", "play": fav,
                "reason": f"The crowd majority is on {dog} ({100 - crowd:.0f}%), the side our numbers "
                          f"make the underdog ({p_dog * 100:.0f}%): taking {fav} is both more likely and less owned.",
                "p_dog": p_dog, "p_fav": p_fav, "crowd_dog": 100 - crowd, "edge_pp": edge * 100,
                "factors_vs_fav": factors_vs_fav, "factors_vs_dog": factors_vs_dog}
    if (p_dog >= CONTRARIAN_MIN_P and (min_dog is None or min_dog >= CONTRARIAN_MIN_SRC)
            and (100 - crowd) <= (p_dog * 100) - CONTRARIAN_MIN_GAP * 100):
        return {"class": "CONTRARIAN", "play": dog,
                "reason": f"{dog} is a {p_dog * 100:.0f}% chance by our numbers but only "
                          f"{100 - crowd:.0f}% of players are on them.",
                "p_dog": p_dog, "p_fav": p_fav, "crowd_dog": 100 - crowd, "edge_pp": edge * 100,
                "factors_vs_fav": factors_vs_fav, "factors_vs_dog": factors_vs_dog}
    if (p_dog >= SITUATIONAL_MIN_P and (min_dog is None or min_dog >= SITUATIONAL_MIN_SRC)
            and (100 - crowd) <= (p_dog * 100) / 2.0
            and factors_vs_fav and not factors_vs_dog):
        return {"class": "SITUATIONAL", "play": dog,
                "reason": f"{dog} is a {p_dog * 100:.0f}% chance against {100 - crowd:.0f}% ownership, "
                          f"and a verified factor counts against {fav}: {factors_vs_fav[0]['kind']}.",
                "p_dog": p_dog, "p_fav": p_fav, "crowd_dog": 100 - crowd, "edge_pp": edge * 100,
                "factors_vs_fav": factors_vs_fav, "factors_vs_dog": factors_vs_dog}
    if p_dog >= LONGSHOT_MIN_P and (100 - crowd) <= LONGSHOT_MAX_CROWD * 100:
        return {"class": "LONG SHOT", "play": fav,
                "reason": f"{dog} is a {p_dog * 100:.0f}% chance with almost no ownership "
                          f"({100 - crowd:.0f}%). Keep {fav}; punt on {dog} only if far behind.",
                "p_dog": p_dog, "p_fav": p_fav, "crowd_dog": 100 - crowd, "edge_pp": edge * 100,
                "factors_vs_fav": factors_vs_fav, "factors_vs_dog": factors_vs_dog}
    return {"class": "CHALK", "play": fav,
            "reason": f"{dog} is only a {p_dog * 100:.0f}% chance and the crowd already backs {fav}.",
            "p_dog": p_dog, "p_fav": p_fav, "crowd_dog": 100 - crowd, "edge_pp": edge * 100,
            "factors_vs_fav": factors_vs_fav, "factors_vs_dog": factors_vs_dog}


# --------------------------------------------------------------------------------------- build
def build_board() -> dict:
    inp = load_inputs()
    capture, aliases, twc, factors = inp["capture"], inp["aliases"], inp["twc"], inp["factors"]
    now = capture.get("finished_utc") or capture.get("started_utc")
    fixtures = capture.get("hotspawn", {}).get("fixtures", [])
    if not fixtures:
        raise SystemExit("no Hotspawn fixtures in the capture - refusing to publish an empty board")

    vrs = {aliases.key(t.get("name")): t for t in capture.get("vrs", {}).get("teams", [])}
    hltv = {aliases.key(t.get("name")): t for t in capture.get("hltv", {}).get("teams", [])}

    rows, seen_pair = [], {}
    for fx in fixtures:
        row = dict(fx)
        flags: list[str] = []
        row["status"] = status_of(fx, now)
        if row["status"] == "stale":
            flags.append("STALE_LISTING")
        if row["status"] == "locked":
            flags.append("LOCKED")
        if len([p for p in capture.get("hotspawn", {}).get("pages", []) if p.get("status") == 200]) < 3:
            flags.append("HOTSPAWN_PARTIAL")

        ests = estimates_for(row, capture, aliases, flags, factors)
        # Drop the own line when a verified roster change post-dates Valve's snapshot and a market exists.
        market = [e for e in ests if e["rung"] in ("1", "2", "3")]
        own = [e for e in ests if e["rung"] == "4"]
        if market and own and own[0].get("roster_outdated"):
            ests = market
            flags.append("VRS_ROSTER_OUTDATED")
        if market:
            spread = (max(max(e["p_a"], e["p_b"]) for e in market)
                      - min(max(e["p_a"], e["p_b"]) for e in market)) * 100
            if spread >= SPLIT_PP:
                flags.append("SPLIT")
        consensus = mean([e["p_a"] for e in ests])
        row["estimates"] = ests
        row["estimate_sources"] = " | ".join(e["short"] for e in ests)
        row["estimate_urls"] = [e.get("url") for e in ests if e.get("url")]
        for rung, key in (("1", "pinnacle_url"), ("2", "bo3_url"), ("3", "polymarket_url"),
                          ("4", "vrs_url")):
            row[key] = next((e.get("url") for e in ests if e["rung"] == rung and e.get("url")), "")
        row["consensus_a"] = consensus
        row["consensus_b"] = None if consensus is None else 1 - consensus
        row["best_rung"] = min((e["rung"] for e in ests), default="5")
        if not ests:
            flags.append("UNRESOLVED")
        elif len(ests) == 1:
            flags.append("SINGLE_SOURCE")
        for e in ests:
            age = hours_between(now, e.get("read_utc"))
            if age is not None and age > STALE_PRICE_H:
                flags.append("STALE_PRICE")
        if consensus is not None and abs(consensus - 0.5) < 0.005:
            flags.append("COIN_FLIP")
        if not row.get("best_of") and not row.get("series_format"):
            flags.append("FORMAT_UNKNOWN")

        ka, kb = aliases.key(row["team_a"]), aliases.key(row["team_b"])
        row["key_a"], row["key_b"] = ka, kb
        row["key_fav"] = ka if (consensus or 0.5) >= 0.5 else kb
        row["key_dog"] = kb if row["key_fav"] == ka else ka
        row["vrs_a"] = (vrs.get(ka) or {}).get("points")
        row["vrs_b"] = (vrs.get(kb) or {}).get("points")
        row["vrs_rank_a"] = (vrs.get(ka) or {}).get("rank")
        row["vrs_rank_b"] = (vrs.get(kb) or {}).get("rank")
        row["hltv_rank_a"] = (hltv.get(ka) or {}).get("rank")
        row["hltv_rank_b"] = (hltv.get(kb) or {}).get("rank")
        row["hltv_url_a"] = (hltv.get(ka) or {}).get("team_url")
        row["hltv_url_b"] = (hltv.get(kb) or {}).get("team_url")
        crowd_a = fx.get("crowd_a_ownership")
        crowd_b = fx.get("crowd_b_ownership")
        row["crowd_a"] = crowd_a
        row["crowd_b"] = crowd_b
        row["crowd_fav_pct"] = (crowd_a if (consensus or 0.5) >= 0.5 else crowd_b) \
            if (crowd_a is not None and crowd_b is not None) else None
        if crowd_a is None or crowd_b is None:
            flags.append("CROWD_MISSING")
        row["total_picks"] = fx.get("total_picks")

        pair = tuple(sorted([ka, kb])) + ((row.get("start_utc") or "")[:13],)
        if pair in seen_pair:
            flags.append("DUPLICATE_LISTING")
            row["duplicate_of"] = seen_pair[pair]
        else:
            seen_pair[pair] = row["match_id"]

        row["pick"] = None
        if consensus is not None:
            row["pick"] = row["team_a"] if consensus >= 0.5 else row["team_b"]
            row["pick_p"] = max(consensus, 1 - consensus)
        row["factors_a"] = active_factors(ka, row.get("start_utc"), factors)
        row["factors_b"] = active_factors(kb, row.get("start_utc"), factors)
        row["strategy"] = strategy(row, factors) if row["status"] == "open" else {
            "class": "LOCKED" if row["status"] == "locked" else "STALE", "play": row.get("pick"),
            "reason": "Lock time has passed; kept for grading."}
        row["flags"] = sorted(set(flags))
        row["flag_text"] = [FLAG_TEXT[f] for f in row["flags"] if f in FLAG_TEXT]
        rows.append(row)

    rows.sort(key=lambda r: (r.get("lock_utc") or "", r["match_id"]))
    open_rows = [r for r in rows if r["status"] == "open"]
    unresolved = [r for r in rows if r["status"] == "open" and not r.get("estimates")]
    coverage = {
        "generated_utc": now, "session": "arena/a6f05f99",
        "fixtures": len(rows), "open": len(open_rows),
        "locked": sum(1 for r in rows if r["status"] == "locked"),
        "stale": sum(1 for r in rows if r["status"] == "stale"),
        "open_with_pick": sum(1 for r in open_rows if r.get("pick")),
        "open_unresolved": len(unresolved),
        "open_by_rung": {r: sum(1 for x in open_rows if x.get("best_rung") == r) for r in "12345"},
        "open_by_estimates": {str(n): sum(1 for x in open_rows if len(x.get("estimates") or []) == n)
                              for n in (0, 1, 2, 3, 4)},
        "classes": {},
        "next_lock_utc": min((r["lock_utc"] for r in open_rows if r.get("lock_utc")), default=None),
        "sources": {k: capture.get(k, {}).get("mode") for k in
                    ("hotspawn", "pinnacle", "bo3", "polymarket", "vrs", "hltv")},
        "k_valve": K_VALVE, "k_valve_provenance": K_VALVE_PROVENANCE,
    }
    for r in open_rows:
        c = (r.get("strategy") or {}).get("class") or "UNRESOLVED"
        coverage["classes"][c] = coverage["classes"].get(c, 0) + 1
    return {"rows": rows, "coverage": coverage, "capture": capture, "twc": twc,
            "factors": factors, "aliases": aliases}


FIELDS = ["match_id", "status", "competition", "tier", "points", "start_utc", "lock_utc",
          "team_a", "team_b", "pick", "p_a_pct", "p_b_pct", "rung", "basis", "estimates_n",
          "estimate_sources", "format", "own_p_a_pct", "vrs_points_a", "vrs_points_b",
          "vrs_rank_a", "vrs_rank_b", "hltv_rank_a", "hltv_rank_b", "crowd_a_pct", "crowd_b_pct",
          "class", "leaderboard_play", "flags", "hotspawn_url", "hltv_url", "bo3_url",
          "pinnacle_url", "polymarket_url", "vrs_url", "sources"]


def to_csv_rows(board: dict) -> list[dict]:
    out = []
    for r in board["rows"]:
        ests = r.get("estimates") or []
        urls = [e.get("url") for e in ests if e.get("url")]
        out.append({
            "match_id": r["match_id"], "status": r["status"], "competition": r.get("competition"),
            "tier": r.get("tier"), "points": r.get("points"), "start_utc": r.get("start_utc"),
            "lock_utc": r.get("lock_utc"), "team_a": r["team_a"], "team_b": r["team_b"],
            "pick": r.get("pick") or "", "p_a_pct": pct_str(r.get("consensus_a")),
            "p_b_pct": pct_str(r.get("consensus_b")), "rung": r.get("best_rung"),
            "basis": RUNG_SHORT.get(r.get("best_rung"), ""), "estimates_n": len(ests),
            "estimate_sources": " | ".join(e["short"] for e in ests),
            "format": r.get("best_of") or r.get("series_format") or "",
            "own_p_a_pct": pct_str(next((e["p_a"] for e in ests if e["rung"] == "4"), None)),
            "vrs_points_a": r.get("vrs_a"), "vrs_points_b": r.get("vrs_b"),
            "vrs_rank_a": r.get("vrs_rank_a"), "vrs_rank_b": r.get("vrs_rank_b"),
            "hltv_rank_a": r.get("hltv_rank_a"), "hltv_rank_b": r.get("hltv_rank_b"),
            "crowd_a_pct": r.get("crowd_a"), "crowd_b_pct": r.get("crowd_b"),
            "class": (r.get("strategy") or {}).get("class", ""),
            "leaderboard_play": (r.get("strategy") or {}).get("play", ""),
            "flags": ";".join(r.get("flags", [])),
            "hotspawn_url": r.get("hotspawn_match_url") or "https://play.hotspawn.com/lobby",
            "hltv_url": r.get("hltv_url_a") or "", "bo3_url": "",
            "pinnacle_url": next((e["url"] for e in ests if e["rung"] == "1"), ""),
            "polymarket_url": next((e["url"] for e in ests if e["rung"] == "3"), ""),
            "vrs_url": next((e["url"] for e in ests if e["rung"] == "4"), ""),
            "sources": " | ".join(u for u in urls if u),
        })
    return out


def pct_str(v) -> str:
    return "" if v is None else f"{float(v) * 100:.1f}"


def main() -> int:
    board = build_board()
    write_csv(DATA / "board.csv", to_csv_rows(board), FIELDS)
    write_json(DATA / "coverage.json", board["coverage"])
    payload = {
        "coverage": board["coverage"],
        "rows": [{k: v for k, v in r.items() if k not in ("estimates",)} for r in board["rows"]],
    }
    write_json(DATA / "board.json", payload)
    unresolved = [r for r in board["rows"] if r["status"] == "open" and not r.get("estimates")]
    write_csv(DATA / "unresolved.csv", [{
        "match_id": r["match_id"], "team_a": r["team_a"], "team_b": r["team_b"],
        "competition": r.get("competition"), "tier": r.get("tier"), "start_utc": r.get("start_utc"),
        "lock_utc": r.get("lock_utc"), "limitation": " | ".join(r.get("flag_text") or [])
        or "No outside price and no official rating for one or both teams.",
        "sources_tried": "Pinnacle guest API; bo3.gg API; Polymarket gamma API; Valve Regional Standings; HLTV world ranking",
        "hotspawn_url": r.get("hotspawn_match_url") or "https://play.hotspawn.com/lobby",
    } for r in unresolved],
        ["match_id", "team_a", "team_b", "competition", "tier", "start_utc", "lock_utc",
         "limitation", "sources_tried", "hotspawn_url"])
    cov = board["coverage"]
    print(f"board: {cov['fixtures']} fixtures, {cov['open']} open, "
          f"{cov['open_with_pick']} with a pick, {cov['open_unresolved']} unresolved; "
          f"estimates per open fixture {cov['open_by_estimates']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
