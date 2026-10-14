#!/usr/bin/env python3
"""Render the canonical CS2 briefing board from the archived raw captures.

Offline and deterministic: reads only briefing/data/raw/*.json.gz (+ capture.json) written by
collect.py, and writes the pages plus the machine-readable tables under briefing/data/.

The basis ladder, applied in this order, is the whole point of the board:

  1. PINNACLE    - Pinnacle's own public guest moneyline for this match (primary bookmaker).
  2. BOOK        - a named bookmaker's price relayed by bo3.gg's public API.
  3. PREDICTION  - Polymarket's match-winner market (a prediction market, not a bookmaker).
  4. MODEL       - our own line, originated from the official Valve Regional Standings with a
                   scale fitted against the market prices read in the same run.

A pick is the higher-probability side of the highest tier available.  Where nothing can be
sourced the probability stays blank and the row is flagged - never inferred, never 50/50.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from model import (american_to_decimal, best_of_from_bo, calibrate_scale, core_key,
                   verified_identity,
                   devig, fair_odds, map_prob_from_rating, names_match, norm,
                   resolve_alias, series_prob)

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "raw"

KICKOFF_WINDOW_MIN = 150        # identity + kickoff must both agree
THIN_PM_SPREAD = 0.06           # Polymarket spread above this is treated as thin
THIN_PM_VOLUME = 500.0

BASIS_ORDER = ["PINNACLE", "BOOK", "PREDICTION", "MODEL"]
BASIS_LABEL = {
    "PINNACLE": "Pinnacle moneyline (primary bookmaker)",
    "BOOK": "Named bookmaker price relayed by bo3.gg",
    "PREDICTION": "Polymarket match-winner market (prediction market, not a bookmaker)",
    "MODEL": "Our line from the official Valve Regional Standings",
}


# ----------------------------------------------------------------------------- helpers
def load(name):
    p = RAW / f"{name}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def require_raw() -> None:
    """Refuse to overwrite a live board with an empty one.

    The raw captures are produced by collect.py on a runner that can reach the source hosts and
    are gitignored, so they are not part of the committed tree.  Without them build.py can only
    render an empty board, and publishing that over a good one is the worst possible failure,
    so it exits non-zero instead.
    """
    if not (RAW / "hotspawn_fixtures.json.gz").exists() or \
            not (DATA / "capture.json").exists():
        raise SystemExit(
            "build.py: no archived Hotspawn capture in %s. Run briefing/collect.py first (it "
            "needs network access); build.py renders from archived bytes and will not "
            "overwrite a good board with an empty one." % RAW)


def parse_utc(value) -> float | None:
    """Seconds since epoch, or None.  Accepts the shapes each source actually sends."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    if re.fullmatch(r"\d{13}", s):
        return int(s) / 1000.0
    s = s.replace("Z", "+00:00")
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None


def pct(x) -> str:
    return "" if x is None else f"{x * 100:.1f}"


def hhmm(ts_iso: str) -> str:
    return (ts_iso or "")[11:16] + " UTC" if ts_iso else ""


# ----------------------------------------------------------------------------- load
def load_all():
    hs = load("hotspawn_fixtures") or {"fixtures": [], "pages": []}
    pin = load("pinnacle") or {"cs2_matchups": [], "moneylines": []}
    bo3 = load("bo3gg") or {"matches": []}
    pm = load("polymarket") or {"events": []}
    vrs = load("valve_vrs") or {"rows": [], "file": "", "as_of": ""}
    hltv = load("hltv") or {}
    cap = json.loads((DATA / "capture.json").read_text())
    return hs, pin, bo3, pm, vrs, hltv, cap


# ----------------------------------------------------------------------------- ratings
def build_rating_index(vrs: dict) -> tuple[dict, list]:
    """Valve VRS points by normalised team name.  Ambiguous names are recorded, not guessed."""
    idx: dict[str, list] = {}
    for row in vrs.get("rows", []):
        idx.setdefault(norm(row.get("team")), []).append(row)
    flat, ambiguous = {}, []
    for key, rows in idx.items():
        if len({r["points"] for r in rows}) > 1:
            ambiguous.append(key)
            continue                      # two different teams share the name -> unusable
        flat[key] = rows[0]
    return flat, ambiguous


def rating_for(team_name: str, vrs_idx: dict, vrs: dict) -> dict:
    """Official rating for one Hotspawn team name.

    Order: exact/alias hit in the official Valve file -> hand-verified identity (for names the
    Valve file does not contain, or contains more than once) -> suffix-stripped fuzzy hit ->
    blank.  Every non-exact route is flagged on the published row.
    """
    name, evidence = resolve_alias(team_name)
    out = {"team": team_name, "matched_name": "", "rank": None, "points": None,
           "url": vrs.get("source_url", ""), "evidence": evidence, "fuzzy": False,
           "origin": "Valve", "resolved_by": "", "why_blank": ""}
    for candidate in (team_name, name):
        row = vrs_idx.get(norm(candidate))
        if row:
            matched, exact = names_match(candidate, row["team"])
            out.update(matched_name=row["team"], rank=row["rank"], points=row["points"],
                       fuzzy=not exact)
            return out

    vid = verified_identity(team_name)
    if vid:
        out.update(matched_name=vid["as"], rank=vid["rank"], points=vid["points"],
                   url=vid["evidence"], origin=vid["origin"],
                   resolved_by=vid["why"], fuzzy=True)
        return out

    ck = core_key(name) or core_key(team_name)
    for key, row in vrs_idx.items():
        if ck and core_key(row["team"]) == ck and ck == norm(row["team"])[:len(ck)]:
            out.update(matched_name=row["team"], rank=row["rank"], points=row["points"],
                       fuzzy=True)
            return out
    out["why_blank"] = "no team of this name in the official Valve Regional Standings file"
    return out


# ----------------------------------------------------------------------------- joins
def _within(a: float | None, b: float | None, minutes: int) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= minutes * 60.0


def _match_teams(fa: str, fb: str, xa: str, xb: str) -> tuple[bool, bool]:
    """Both fixtures are unordered pairs; try both orientations."""
    m1 = names_match(fa, xa)
    m2 = names_match(fb, xb)
    if m1[0] and m2[0]:
        return True, m1[1] and m2[1]
    m1 = names_match(fa, xb)
    m2 = names_match(fb, xa)
    if m1[0] and m2[0]:
        return True, m1[1] and m2[1]
    return False, False


def _orient(fa: str, fb: str, xa: str, xb: str) -> bool:
    """True when the external side A is the fixture's side A (not swapped)."""
    return names_match(fa, xa)[0]


def join_pinnacle(fx: dict, quotes: list, flags: list) -> None:
    best = None
    for q in quotes:
        if not _within(parse_utc(fx["start_utc"]), parse_utc(q.get("start_utc")),
                       KICKOFF_WINDOW_MIN):
            continue
        ok, exact = _match_teams(fx["team_a"], fx["team_b"], q.get("team_a", ""),
                                 q.get("team_b", ""))
        if not ok:
            continue
        swap = not _orient(fx["team_a"], fx["team_b"], q.get("team_a", ""), q.get("team_b", ""))
        oa, ob = float(q["american_a"]), float(q["american_b"])
        if swap:
            oa, ob = ob, oa
        da, db = american_to_decimal(oa), american_to_decimal(ob)
        pa, pb, over = devig(da, db)
        rec = {"basis": "PINNACLE", "book": "Pinnacle", "odds_a": round(da, 4),
               "odds_b": round(db, 4), "p_a": pa, "p_b": pb, "overround": over,
               "url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
               "api_url": q.get("market_url", ""),
               "matched_names": f'{q.get("team_a")} / {q.get("team_b")}',
               "start_utc": q.get("start_utc"), "exact": exact,
               "source_id": str(q.get("event_id") or ""), "source_slug": "",
               "source_page": "https://www.pinnacle.com/en/esports/games/cs2/matchups/"}
        if best is None or rec["p_a"] > 0:
            best = rec
        if not exact:
            flags.append(("FL-NAME-FUZZY", fx["fixture_id"],
                          f'Pinnacle match joined on a non-exact team name: Hotspawn '
                          f'"{fx["team_a"]} / {fx["team_b"]}" vs Pinnacle '
                          f'"{q.get("team_a")} / {q.get("team_b")}"',
                          rec["url"]))
    if best:
        fx["quotes"].append(best)


def join_bo3(fx: dict, matches: list, flags: list) -> None:
    for m in matches:
        t1 = ((m.get("team1") or {}).get("name") or "")
        t2 = ((m.get("team2") or {}).get("name") or "")
        if not _within(parse_utc(fx["start_utc"]), parse_utc(m.get("start_date")),
                       KICKOFF_WINDOW_MIN):
            continue
        ok, exact = _match_teams(fx["team_a"], fx["team_b"], t1, t2)
        if not ok:
            continue
        slug = m.get("slug") or ""
        bo = best_of_from_bo(m.get("bo_type"))
        if bo and not fx.get("best_of"):
            fx["best_of"] = bo
            fx["best_of_source"] = f"https://bo3.gg/matches/{slug}" if slug else \
                "https://bo3.gg/matches"
        bu = m.get("bet_updates")
        if not isinstance(bu, dict):
            continue
        s1 = bu.get("team_1") or {}
        s2 = bu.get("team_2") or {}
        ca, cb = s1.get("coeff"), s2.get("coeff")
        if ca is None or cb is None:
            continue
        try:
            da, db = float(ca), float(cb)
        except (TypeError, ValueError):
            continue
        if da <= 1.0 or db <= 1.0:
            continue
        swap = not _orient(fx["team_a"], fx["team_b"], t1, t2)
        if s1.get("team_id") and m.get("team2") and s1.get("team_id") == \
                (m.get("team2") or {}).get("id"):
            swap = not swap
        if swap:
            da, db = db, da
        if abs(da - 1.0) < 1e-9 and abs(db - 1.0) < 1e-9:
            continue
        pa, pb, over = devig(da, db)
        provider = str(bu.get("provider") or "").strip() or "unnamed provider"
        fx["quotes"].append({
            "basis": "BOOK", "book": provider.title(), "odds_a": round(da, 4),
            "odds_b": round(db, 4), "p_a": pa, "p_b": pb, "overround": over,
            "url": bu.get("path") or (f"https://bo3.gg/matches/{slug}" if slug
                                      else "https://bo3.gg/matches"),
            "matched_names": f"{t1} / {t2}", "start_utc": m.get("start_date"),
            "source_id": str(m.get("id") or ""), "source_slug": slug,
            "source_page": f"https://bo3.gg/matches/{slug}" if slug else "https://bo3.gg/matches",
            "exact": exact})
        if not exact:
            flags.append(("FL-NAME-FUZZY", fx["fixture_id"],
                          f'bo3.gg match joined on a non-exact team name: Hotspawn '
                          f'"{fx["team_a"]} / {fx["team_b"]}" vs bo3.gg "{t1} / {t2}"',
                          f"https://bo3.gg/matches/{slug}" if slug else "https://bo3.gg/matches"))
        break


PM_TITLE = re.compile(r"Counter-Strike:?\s*(.+?)\s+vs\.?\s+(.+?)\s*\((BO\d)\)", re.I)


def join_polymarket(fx: dict, events: list, flags: list) -> None:
    for ev in events:
        title = str(ev.get("title") or "")
        m = PM_TITLE.search(title)
        if not m:
            continue
        ta, tb = m.group(1).strip(), m.group(2).strip()
        ok, exact = _match_teams(fx["team_a"], fx["team_b"], ta, tb)
        if not ok:
            continue
        when = parse_utc(ev.get("startTime") or ev.get("endDate"))
        if not _within(parse_utc(fx["start_utc"]), when, KICKOFF_WINDOW_MIN):
            continue
        bo = best_of_from_bo(str(m.group(3)).lower().replace("bo", ""))
        if bo and not fx.get("best_of"):
            fx["best_of"] = bo
            fx["best_of_source"] = f"https://polymarket.com/event/{ev.get('slug')}"
        for mk in ev.get("markets") or []:
            raw_prices = mk.get("outcomePrices")
            try:
                prices = json.loads(raw_prices) if isinstance(raw_prices, str) else raw_prices
            except ValueError:
                continue
            if not isinstance(prices, list) or len(prices) != 2:
                continue
            try:
                pa_raw, pb_raw = float(prices[0]), float(prices[1])
            except (TypeError, ValueError):
                continue
            if not (0.0 < pa_raw < 1.0) or not (0.0 < pb_raw < 1.0):
                continue
            swap = not _orient(fx["team_a"], fx["team_b"], ta, tb)
            if swap:
                pa_raw, pb_raw = pb_raw, pa_raw
            total = pa_raw + pb_raw
            spread = mk.get("spread")
            volume = mk.get("volume")
            url = f"https://polymarket.com/event/{ev.get('slug')}"
            thin = (spread is not None and float(spread) > THIN_PM_SPREAD) or \
                   (volume is not None and float(volume) < THIN_PM_VOLUME)
            fx["quotes"].append({
                "basis": "PREDICTION", "book": "Polymarket", "odds_a": round(1 / pa_raw, 4),
                "odds_b": round(1 / pb_raw, 4), "p_a": pa_raw / total, "p_b": pb_raw / total,
                "overround": total - 1.0, "url": url, "matched_names": f"{ta} / {tb}",
                "start_utc": ev.get("startTime"), "exact": exact, "thin": thin,
                "source_id": str(ev.get("id") or ""), "source_slug": str(ev.get("slug") or ""),
                "source_page": f"https://polymarket.com/event/{ev.get('slug')}",
                "raw": f"{pa_raw:.3f}/{pb_raw:.3f}", "spread": spread, "volume": volume})
            flags.append(("FL-PREDICTION-MARKET", fx["fixture_id"],
                          f"Probability backed by Polymarket, a prediction market, not a "
                          f"bookmaker price. Raw outcomes {pa_raw:.3f}/{pb_raw:.3f}, "
                          f"spread {spread}, volume {volume}."
                          + (" Treated as thin." if thin else ""), url))
            if not exact:
                flags.append(("FL-NAME-FUZZY", fx["fixture_id"],
                              f'Polymarket event joined on a non-exact team name: Hotspawn '
                              f'"{fx["team_a"]} / {fx["team_b"]}" vs Polymarket "{ta} / {tb}"',
                              url))
            return


# ----------------------------------------------------------------------------- main build
def build() -> dict:
    hs, pin, bo3, pm, vrs, hltv, cap = load_all()
    now_iso = cap.get("generated_utc") or ""
    now_ts = parse_utc(now_iso) or 0.0

    vrs_idx, vrs_ambiguous = build_rating_index(vrs)
    flags: list[tuple[str, str, str, str]] = []
    needed = {norm(t) for f in hs.get("fixtures", [])
              for t in (f.get("participants0_name"), f.get("participants1_name"))}
    for key in vrs_ambiguous:
        if key not in needed:
            continue          # unused duplicate: noted in the review, not on the board
        flags.append(("FL-RATING-AMBIGUOUS", "",
                      f'"{key}" appears more than once with different points in the official '
                      f'Valve file, so the plain name lookup cannot be used; the row resolves '
                      f'it against HLTV and cites that page.', vrs.get("source_url", "")))

    fixtures = []
    for f in hs.get("fixtures", []):
        lock_ts = parse_utc(f.get("lock_utc"))
        start_ts = parse_utc(f.get("start_utc"))
        state = "open" if (lock_ts and lock_ts > now_ts) else (
            "locked" if (start_ts and start_ts > now_ts - 86400) else "stale")
        fx = {
            "fixture_id": str(f.get("id")),
            "tournament": f.get("competition_name") or "",
            "tier": (f.get("tier") or "").upper(),
            "stage": f.get("stage") or "",
            "start_utc": f.get("start_utc") or "",
            "lock_utc": f.get("lock_utc") or "",
            "team_a": f.get("participants0_name") or "",
            "team_b": f.get("participants1_name") or "",
            "permalink": f.get("permalink") or "",
            "state": state, "quotes": [], "best_of": None, "best_of_source": "",
            "rating_a": None, "rating_b": None, "basis": "", "pick": "", "p_pick": None,
            "p_a": None, "p_b": None, "model_p_a": None, "format_known": False,
        }
        fixtures.append(fx)

    open_fx = [f for f in fixtures if f["state"] == "open"]

    for fx in open_fx:
        join_pinnacle(fx, pin.get("moneylines", []), flags)
        join_bo3(fx, bo3.get("matches", []), flags)
        join_polymarket(fx, pm.get("events", []), flags)
        fx["rating_a"] = rating_for(fx["team_a"], vrs_idx, vrs)
        fx["rating_b"] = rating_for(fx["team_b"], vrs_idx, vrs)

    # --- calibrate our rating scale against the market prices read in this same run
    pairs = []
    for fx in open_fx:
        q = pick_quote(fx)
        if not q:
            continue
        ra, rb = fx["rating_a"]["points"], fx["rating_b"]["points"]
        if ra is None or rb is None:
            continue
        pairs.append((float(ra), float(rb), q["p_a"], fx.get("best_of")))
    fit = calibrate_scale(pairs)

    # --- originate our own line for every fixture whose two teams are officially rated
    for fx in open_fx:
        ra, rb = fx["rating_a"]["points"], fx["rating_b"]["points"]
        if ra is None or rb is None:
            fx["model_note"] = "no official Valve rating for one or both teams"
            continue
        if not fit["ok"]:
            fx["model_note"] = "uncalibrated default scale " + fit["note"]
        map_p = map_prob_from_rating(float(ra), float(rb), fit["scale"])
        bo = fx.get("best_of")
        if bo:
            fx["model_p_a"] = series_prob(map_p, bo)
            fx["format_known"] = True
        else:
            fx["model_p_a"] = map_p          # single-map estimate, format unknown
            flags.append(("FL-FORMAT-UNKNOWN", fx["fixture_id"],
                          "Hotspawn publishes no series format and no outside source in this "
                          "run states one, so the model line is a single-map estimate and its "
                          "series probability is not published.", fx.get("permalink") or ""))

    # --- integrity: two different fixtures must not be given an identical price pair
    seen_quotes: dict[tuple, str] = {}
    for fx in open_fx:
        for q in fx["quotes"]:
            key = (q["book"], round(float(q["odds_a"]), 4), round(float(q["odds_b"]), 4))
            if key in seen_quotes and seen_quotes[key] != fx["fixture_id"]:
                flags.append(("FL-DUPLICATE-QUOTE", fx["fixture_id"],
                              f'{q["book"]} lists the same price pair '
                              f'({q["odds_a"]}/{q["odds_b"]}) for this fixture and for '
                              f'{seen_quotes[key]}. Both joins matched on different source '
                              f'records and different kickoffs, so this is most likely a '
                              f'coarse odds ladder rather than a mismatch - but the two rows '
                              f'cannot be told apart from the price alone, so it is listed '
                              f'here for a human check. Neither price is dropped.', q["url"]))
            seen_quotes.setdefault(key, fx["fixture_id"])

    # --- decide the basis, the pick and the published probability
    for fx in open_fx:
        q = pick_quote(fx)
        if q:
            fx["basis"] = q["basis"]
            fx["p_a"], fx["p_b"] = q["p_a"], q["p_b"]
            fx["quote"] = q
            if q["basis"] == "BOOK":
                prov = q.get("book") or "the named bookmaker"
                flags.append((
                    "FL-BOOK-RELAYED", fx["fixture_id"],
                    f'This is the price this row publishes, and it was read from bo3.gg\'s '
                    f'public API, not from {prov} directly. bo3.gg names the provider and '
                    f'links the bookmaker\'s own match page, and that page is the link on this '
                    f'row, but the quote has not been confirmed against the bookmaker itself. '
                    f'Other boards on this site treat relayed prices as unverified and publish '
                    f'them blank; this one publishes them because the provider and the source '
                    f'URL are both named, and flags them so the difference is visible. '
                    f'Pinnacle and Polymarket rows carry no such caveat.',
                    q.get("url") or "https://bo3.gg/matches"))
        elif fx.get("model_p_a") is not None:
            fx["basis"] = "MODEL"
            fx["p_a"] = fx["model_p_a"]
            fx["p_b"] = 1.0 - fx["model_p_a"]
        else:
            fx["basis"] = ""
            fx["p_a"] = fx["p_b"] = None
            flags.append(("FL-NO-BASIS", fx["fixture_id"],
                          "Neither an outside price nor official ratings for both teams could "
                          "be sourced, so no probability and no pick are published.",
                          fx.get("permalink") or ""))
        if fx["p_a"] is None:
            fx["pick"] = ""
            fx["p_pick"] = None
            continue
        pa, pb = fx["p_a"], fx["p_b"]
        if abs(pa - pb) < 1e-9:
            fx["pick"] = ""
            fx["p_pick"] = None
            flags.append(("FL-COINFLIP", fx["fixture_id"],
                          "The two sides price identically, so no pick is published rather "
                          "than breaking the tie arbitrarily.",
                          (fx.get("quote") or {}).get("url", fx.get("permalink", ""))))
            continue
        fx["pick"] = fx["team_a"] if pa > pb else fx["team_b"]
        fx["p_pick"] = max(pa, pb)
        # market vs our model, where both exist
        if fx.get("quote") and fx.get("model_p_a") is not None:
            qa = fx["quote"]["p_a"]
            if (qa > 0.5) != (fx["model_p_a"] > 0.5):
                flags.append(("FL-MODEL-MARKET-SPLIT", fx["fixture_id"],
                              f'The outside price favours '
                              f'{(fx["team_a"] if qa > 0.5 else fx["team_b"])} '
                              f'({qa * 100:.1f}%) while our Valve-rating line favours '
                              f'{(fx["team_a"] if fx["model_p_a"] > 0.5 else fx["team_b"])} '
                              f'({fx["model_p_a"] * 100:.1f}%). The published pick follows the '
                              f'outside price. Both are shown on the row.',
                              fx["quote"]["url"]))

    result = {"generated_utc": now_iso, "capture": cap, "fixtures": fixtures,
              "open": open_fx, "fit": fit, "flags": flags, "vrs": vrs, "hltv": hltv,
              "vrs_ambiguous": vrs_ambiguous,
              "counts": {
                  "fixtures": len(fixtures), "open": len(open_fx),
                  "locked": sum(1 for f in fixtures if f["state"] == "locked"),
                  "stale": sum(1 for f in fixtures if f["state"] == "stale"),
                  "picks": sum(1 for f in open_fx if f["pick"]),
                  "market": sum(1 for f in open_fx
                                if f["basis"] in ("PINNACLE", "BOOK", "PREDICTION")),
                  "model": sum(1 for f in open_fx if f["basis"] == "MODEL"),
                  "blank": sum(1 for f in open_fx if not f["pick"]),
              }}
    return result


def pick_quote(fx: dict):
    """Highest-tier quote on this fixture, or None."""
    best = None
    for q in fx["quotes"]:
        if q.get("thin") and q["basis"] == "PREDICTION":
            continue                     # thin prediction markets are recorded, never used
        if best is None or BASIS_ORDER.index(q["basis"]) < BASIS_ORDER.index(best["basis"]):
            best = q
    return best


def main() -> int:
    require_raw()
    r = build()
    import render
    render.render(r)
    render.write_data(r)
    print(json.dumps(r["counts"], indent=1))
    print(json.dumps(r["fit"], indent=1))
    print("flags:", len(r["flags"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
