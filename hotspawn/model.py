#!/usr/bin/env python3
"""Originate a pick, both teams' win probabilities and a leaderboard play for every fixture.

Probability ladder (first rung that resolves wins; every rung is labelled on the page):
  A  Pinnacle whole-match moneyline, margin removed proportionally (sharp bookmaker)
  B  Polymarket match-winner price, normalised (prediction market — not a bookmaker)
  C  Our own line: Valve Regional Standings points on Valve's curve with a slope fitted on Valve's
     own published results (calibrate.py).  Used when no outside price exists.
  E  Research fallback (research/fallback_83090640.json): same own line, but the Valve standings row
     is disambiguated by documented roster overlap with the HLTV-listed match lineup when a team name
     maps to several Valve rows (>= 3 shared nicknames, strictly the best overlap; verified row links
     in the pack).  Used only when A–C cannot resolve an open fixture; roster deltas vs the snapshot
     are flagged, never silently ignored.  Softer than a market price.
  D  Unresolved: no price and no eligible research-fallback row -> pick left blank + flagged.

Hotspawn's crowd pick share is NEVER a probability input.  It is used only afterwards, by the
leaderboard-strategy rule, as "ownership": how many other players already hold each side.

Leaderboard heuristic v3 (evidence eligibility) ("contrarian but not stupid"), applied to open fixtures with a probability.
  The underdog's "real chance" is a heuristic average of the separately sourced estimates we hold (not statistically independent) (the market rung
  A/B and our own line, averaged; our line is left out when a verified roster change post-dates Valve's
  snapshot and a market exists); MIN is the lowest of them.  Only "strong" or "moderate" verified
  factors count (roster change, stand-in, late replacement); "weak" ones (e.g. schedule) never do.
  VALUE        crowd majority is on the consensus underdog -> play the favourite (likely AND contrarian)
  CONTRARIAN   consensus >= 38%, MIN >= 30%, crowd share <= consensus - 10 points -> play the underdog
  SITUATIONAL  consensus >= 30%, MIN >= 25%, crowd share <= half the consensus, a strong/moderate
               factor against the favourite and none against the underdog -> play the underdog
  LONG SHOT    consensus >= 20% with <= 10% crowd share -> favourite still played; listed as an optional
               punt for players far behind
  CHALK        otherwise -> play the favourite
  v1 (written before day 1 was graded) used the market alone and let weak factors count; graded on
  TWC day 1 it went 1/4, so v2 was adopted.  v2's 4/4 on day 1 is in-sample (n = 4), not evidence.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import timedelta
from evidence import select_quote, select_match_metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, RESEARCH, SESSION, Aliases, K_VALVE_RAW, devig_two_way, fold, hours_between,  # noqa: E402
                    iso, normalise_prices, now_iso, own_line, parse_iso, read_json, write_json)

LOBBY = "https://play.hotspawn.com/lobby"
MAX_KICKOFF_GAP_H = 6.0
STALE_AFTER_H = 36.0
SPLIT_PP = 10.0
BOOK_PM_SPLIT_PP = 8.0
CONTRARIAN_MIN_P, CONTRARIAN_MIN_SRC, CONTRARIAN_MIN_GAP = 0.38, 0.30, 0.10
SITUATIONAL_MIN_P, SITUATIONAL_MIN_SRC = 0.30, 0.25
LONGSHOT_MIN_P, LONGSHOT_MAX_CROWD = 0.20, 0.10
COUNTING_STRENGTH = ("strong", "moderate")
NEW_FIVE_MAX_MATCHES, NEW_FIVE_DAYS = 10, 75

FLAG_TEXT = {
    "KICKOFF_GAP": "Outside source lists a different kickoff than Hotspawn (joined because both teams match and the gap is within 6 h).",
    "ALIAS": "A team name was joined through a verified alias (see research/aliases.json for the evidence).",
    "NO_MARKET": "No eligible outside price captured; the probability is our own line from official Valve points.",
    "MODEL_MARKET_SPLIT": "Our own line and the market disagree on the favourite or by 10+ points.",
    "BOOK_PM_SPLIT": "Pinnacle and Polymarket differ by 8+ points.",
    "ROSTER_UNVERIFIED": "A match-specific roster report does not verify this fixture’s current lineup; own probabilities withheld and factual lineup left blank.",
    "VRS_ROSTER_OUTDATED": "A source-checked lineup differs from the five rated in Valve's snapshot; the dated rating does not establish the actual current lineup.",
    "FORMAT_UNKNOWN": "No source stated the series length; nothing was assumed.",
    "UNRESOLVED": "No eligible outside line or independent direction satisfies the evidence gates; pick and probabilities are left blank.",
    "RESEARCH_FALLBACK": "No outside price and no strict own line; the pick is our own line on a Valve standings row disambiguated by documented roster overlap with HLTV's listed match lineup (research rung E). Softer than a market price.",
    "VALVE_NAME_AMBIGUOUS": "The team name maps to more than one roster row in Valve's standings, or the Valve row is filed under a different team name; the row used was chosen by the documented roster-overlap rule and is linked on the row.",
    "POST_LOCK_RESOLUTION": "The fixture appeared minutes before its pick lock and research finished after it. The pick is retrospective analysis only, is excluded from the graded pick history, and was never a submittable pick'em pick.",
    "STALE_LISTING": "Hotspawn still lists this fixture although its lock time passed more than 36 h ago (not pickable).",
    "LOCKED": "Lock time has passed; kept for the record and for grading.",
    "CROWD_MISSING": "Hotspawn did not publish a crowd share; no leaderboard play computed.",
    "HOTSPAWN_PARTIAL": "At least one Hotspawn surface is empty, unavailable or inconsistent in this capture; full live coverage is not certified.",
    "COIN_FLIP": "Probabilities within one point of 50%; no meaningful directional edge. Only an exact tie may use the eligible own line as a tiebreaker.",
    "STALE_PRICE": "An outside quote is missing a usable read time or is older than 8 h; rejected, not used.",
    "REJECTED_QUOTE": "A same-pair quote was rejected (competition, rematch ambiguity, freshness, format, or validity); see the row's evidence.",
    "BOOKMAKER_UNVERIFIED": "Two-sided match quote observed in bo3.gg, but the operator is identified only by an internal ID. Bookmaker name is blank, not inferred from an affiliate URL; no automatic contrarian fade.",
    "RELAYED_BOOK": "A sportsbook line relayed by bo3.gg (operator name or internal ID retained); not verified directly with the bookmaker. Secondary evidence only.",
    "VRS_STALE": "Valve's rating snapshot has no usable date, is future-dated, or is more than 45 days old; an own-line probability is withheld.",
    "OWN_LINE_WITHHELD": "An own line is not supported for this fixture's known roster/format/rating freshness; blank rather than invented.",
    "IDENTITY_CONFLICT": "Hotspawn surfaces disagree on fixture identity or timing; no probability is published for this ID.",
    "NO_DIRECTION": "The eligible outside price is exactly 50/50 and no eligible independent line breaks the tie; no side invented.",
    "MODEL_ONLY": "Own originated estimate, not an observed bookmaker line; format-specific calibration and map veto are not modelled.",
    "DIRECTION_ONLY": "Research rung F: a pick direction is published from HLTV's own one-sided verdict (ranking, recent form, head-to-head) because no price and no rating pair exist. No win probability is published for this match.",
    "NO_PERCENTAGE": "No eligible outside price and no rating pair for both teams, so the percentage columns are blank rather than invented.",
    "EGW_PLACEHOLDER": "EGamersWorld displays its 1.8 / 1.8 placeholder price on this match. A placeholder is not a market price and was rejected.",
}


def load_inputs() -> dict:
    return {
        "capture": read_json(DATA / "capture.json", {}) or {},
        "calibration": read_json(DATA / "calibration.json", {}) or {},
        "notes": (read_json(RESEARCH / "notes.json", {}) or {}).get("notes", []),
        "hltv_links": read_json(RESEARCH / "hltv_links.json", {}) or {},
        "day1": read_json(RESEARCH / "day1_twc2026.json", {}) or {},
        "day2": read_json(RESEARCH / "day2_twc2026.json", {}) or {},
        "results": (read_json(RESEARCH / "results.json", {}) or {}).get("results", {}),
        "history": read_json(DATA / "pick_history.json", {}) or {},
        "fallback": read_json(RESEARCH / "fallback_83090640.json", {}) or {},
        "verdicts": read_json(RESEARCH / "29171622" / "gap_verdicts.json", {}) or {},
        "twc_days": read_json(RESEARCH / "29171622" / "twc_days.json", {}) or {},
    }


def index_by_key(rows: list[dict], aliases: Aliases, name_field: str = "name") -> dict:
    out: dict[str, list] = {}
    for row in rows or []:
        out.setdefault(aliases.key(row.get(name_field, "")), []).append(row)
    return out


def unique(index: dict, key: str):
    hits = index.get(key) or []
    return hits[0] if len(hits) == 1 else None


def _nick(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(name))


def disambiguate_valve(rows: list[dict], lineup: list[str], min_overlap: int = 3) -> tuple[dict | None, dict]:
    """Roster-overlap rule (research rung E): among same-name Valve standings rows, pick the row whose
    roster shares the most nicknames with the lineup HLTV lists for this match.  The winner must have
    ``>= min_overlap`` shared nicknames AND strictly more than any other candidate; otherwise the
    fixture stays unresolved.  Returns (row_or_None, metadata) where metadata records every count."""
    lin = {_nick(p) for p in lineup or []}
    scored = sorted(((len(lin & {_nick(p) for p in (row.get("roster") or [])}), row) for row in rows or []),
                    key=lambda t: -t[0])
    best = scored[0] if scored else (0, None)
    second = scored[1][0] if len(scored) > 1 else 0
    meta = {"rule": "roster-overlap disambiguation", "min_overlap": min_overlap,
            "candidates": len(rows or []), "overlap_best": best[0], "overlap_second": second}
    if best[1] is not None and best[0] >= min_overlap and best[0] > second:
        meta["ok"] = True
        return best[1], meta
    meta["ok"] = False
    return None, meta


def match_quote(fx: dict, quotes: list[dict], aliases: Aliases, reference: str | None = None,
                fixtures: list[dict] | None = None, rejections: list[dict] | None = None,
                expected_format: str | None = None) -> tuple[dict | None, bool]:
    return select_quote(fx, quotes, aliases, reference, fixtures, rejections, expected_format)


def active_notes(team_key: str, start_utc: str, notes: list[dict], match_id: str | None = None) -> list[dict]:
    start = parse_iso(start_utc)
    out = []
    for n in notes:
        if n.get("team") != team_key:
            continue
        if n.get("match_ids") and str(match_id) not in {str(mid) for mid in n["match_ids"]}:
            continue
        until = parse_iso(f"{n.get('relevant_until')}T23:59:59Z") if n.get("relevant_until") else None
        since = parse_iso(f"{n.get('as_of')}T00:00:00Z") if n.get("as_of") else None
        if start and until and start > until:
            continue
        if start and since and start < since:
            continue
        out.append(n)
    return out


def valve_new_five(team: dict | None, ref) -> dict | None:
    if not team or team.get("matches_with_current_five") is None:
        return None
    first = parse_iso(f"{team.get('first_rated_match_current_five')}T00:00:00Z") if team.get("first_rated_match_current_five") else None
    n = team.get("matches_with_current_five") or 0
    if first and ref and n <= NEW_FIVE_MAX_MATCHES and (ref - first) <= timedelta(days=NEW_FIVE_DAYS):
        return {"kind": "new five (Valve data)", "risk_for": None,
                "summary": f"Valve's standings show only {n} rated matches for this exact five, the first on {team.get('first_rated_match_current_five')}.",
                "source_urls": [], "automated": True}
    return None


def classify(p_dog: float, min_src: float, crowd_dog: float, crowd_fav: float,
             factor_vs_fav: bool, factor_vs_dog: bool) -> tuple[str, str]:
    if crowd_fav < 0.5:
        return "VALUE", "Most players are on the underdog, so the likely winner is also the contrarian pick."
    if p_dog >= CONTRARIAN_MIN_P and min_src >= CONTRARIAN_MIN_SRC and crowd_dog <= p_dog - CONTRARIAN_MIN_GAP:
        return "CONTRARIAN", "Close match that the crowd treats as lopsided: every estimate gives the underdog a real chance, far above its crowd share."
    if (p_dog >= SITUATIONAL_MIN_P and min_src >= SITUATIONAL_MIN_SRC and crowd_dog <= p_dog / 2
            and factor_vs_fav and not factor_vs_dog):
        return "SITUATIONAL", "Real upset chance, heavily faded by the crowd, plus a verified factor (roster change, stand-in or late replacement) against the favourite."
    if p_dog >= LONGSHOT_MIN_P and crowd_dog <= LONGSHOT_MAX_CROWD:
        return "LONG SHOT", "Big leverage but a low chance: keep the favourite unless you are far behind with few matches left."
    return "CHALK", "The favourite is both likely and popular; fading it costs points without enough upside."


def strategy(row: dict) -> dict | None:
    pa, pb = row.get("p_a"), row.get("p_b")
    ca, cb = row.get("crowd_a"), row.get("crowd_b")
    if pa is not None and "BOOKMAKER_UNVERIFIED" in (row.get("flags") or []):
        return {"class": "EVIDENCE LIMITED", "leaderboard_pick": row.get("pick"),
                "reason": "Operator identity unverified: retain the source-implied side, no automatic contrarian fade."}
    if pa is None or pb is None:
        if row.get("rung") == "F" and row.get("pick"):
            return {"class": "DIRECTION ONLY", "leaderboard_pick": row["pick"],
                    "reason": "Only a direction is published for this match, with no win probability, so no "
                              "value/contrarian leverage can be computed. Take the published side."}
        return None
    if ca is None or cb is None or (ca + cb) <= 0:
        return {"class": "NO CROWD DATA", "leaderboard_pick": row.get("pick"), "reason": "Hotspawn published no crowd share."}
    if row.get("total_picks") is not None and row["total_picks"] < 10:
        return {"class": "NO CROWD DATA", "leaderboard_pick": row.get("pick"),
                "reason": "Fewer than 10 crowd picks; ownership is too sparse for an automatic fade."}
    ca, cb = ca / (ca + cb), cb / (ca + cb)
    estimates_a = [("own line" if row.get("rung") in ("C", "E") else "market", pa)]
    roster_outdated = "VRS_ROSTER_OUTDATED" in (row.get("flags") or [])
    if row.get("own_p_a") is not None and row.get("rung") not in ("C", "E") and not roster_outdated:
        estimates_a.append(("own line", row["own_p_a"]))
    cons_a = sum(v for _, v in estimates_a) / len(estimates_a)
    fav_is_a = (row.get("pick") == row["team_a"]) if pa == pb else pa > pb
    fav, dog = (row["team_a"], row["team_b"]) if fav_is_a else (row["team_b"], row["team_a"])
    dog_vals = [(1 - v) if fav_is_a else v for _, v in estimates_a]
    p_dog = sum(dog_vals) / len(dog_vals)
    p_fav = 1 - p_dog
    min_src = min(dog_vals)
    c_fav, c_dog = (ca, cb) if fav_is_a else (cb, ca)
    fav_side, dog_side = ("a", "b") if fav_is_a else ("b", "a")
    counting = [f for f in row.get("factors", []) if f.get("argues_against") and (f.get("strength") in COUNTING_STRENGTH)]
    vs_fav = [f for f in counting if f.get("side") == fav_side]
    vs_dog = [f for f in counting if f.get("side") == dog_side and f.get("strength") == "strong"]
    cls, reason = classify(p_dog, min_src, c_dog, c_fav, bool(vs_fav), bool(vs_dog))
    play = dog if cls in ("CONTRARIAN", "SITUATIONAL") else fav
    pts = row.get("points") or 0
    # EV cost is measured on the DISPLAYED probabilities (the pick's basis), not the consensus, so it is
    # never understated: points x (chance of the pick - chance of the play).
    shown = {row["team_a"]: pa, row["team_b"]: pb}
    pick_side = row.get("pick") or (row["team_a"] if pa >= pb else row["team_b"])
    other = row["team_b"] if pick_side == row["team_a"] else row["team_a"]
    cost_play = max(0.0, pts * (shown[pick_side] - shown[play])) if play != pick_side else 0.0
    cost_fade = max(0.0, pts * (shown[pick_side] - shown[other]))
    return {
        "class": cls, "reason": reason, "leaderboard_pick": play, "favourite": fav, "underdog": dog,
        "p_fav": round(p_fav, 4), "p_dog": round(p_dog, 4), "min_src_dog": round(min_src, 4),
        "estimates": [name for name, _ in estimates_a],
        "crowd_fav": round(c_fav, 4), "crowd_dog": round(c_dog, 4),
        "edge_vs_crowd_pp": round((p_dog - c_dog) * 100, 1),
        "leverage": round(p_dog / max(c_dog, 0.01), 2),
        "ev_cost_pts": round(cost_play, 2),
        "ev_cost_if_faded": round(cost_fade, 2),
        "field_gain_if_dog_wins_pct": round(c_fav * 100),
        "factors_against_favourite": [f.get("kind") for f in vs_fav],
        "factors_against_underdog": [f.get("kind") for f in vs_dog],
        "differs_from_pick": play != row.get("pick"),
    }


def build_rows(inp: dict) -> tuple[list[dict], dict]:
    cap = inp["capture"]
    aliases = Aliases()
    hs = cap.get("hotspawn", {})
    fixtures = hs.get("fixtures", [])
    ref = parse_iso(next((p.get("read_utc") for p in hs.get("pages", []) if parse_iso(p.get("read_utc"))), None)) \
        or parse_iso(cap.get("finished_utc")) or parse_iso(now_iso())
    calib = inp["calibration"]
    k = float(calib.get("k") or K_VALVE_RAW)
    k_label = calib.get("k_source") or "Valve raw g (uncalibrated)"
    vrs = cap.get("vrs", {})
    vrs_idx = index_by_key(vrs.get("teams", []), aliases)
    hltv = cap.get("hltv", {})
    hltv_idx = index_by_key(hltv.get("teams", []), aliases)
    pin_quotes = cap.get("pinnacle", {}).get("quotes", [])
    pm_quotes = cap.get("polymarket", {}).get("quotes", [])
    relay_quotes = cap.get("esportsbooks", {}).get("quotes", [])
    research_by_id = {str(a.get("match_id")): a for a in cap.get("gap_research", {}).get("hltv", [])}
    fallback_by_id = {str(e.get("match_id")): e for e in (inp.get("fallback") or {}).get("entries", [])}
    conflicts = {str(c.get("match_id")) for c in hs.get("conflicts", [])}
    links = inp["hltv_links"].get("fixtures", {})
    events = inp["hltv_links"].get("events", {})
    rows = []
    for fx in fixtures:
        r = {k2: fx.get(k2) for k2 in ("match_id", "competition", "tier", "stage", "start_utc", "lock_utc",
                                        "team_a", "team_b", "hotspawn_match_url", "pages", "read_utc")}
        r["points"] = fx.get("offered_points")
        r["lobby_url"] = LOBBY
        r["source_url"] = fx.get("source_url")
        lock = parse_iso(fx.get("lock_utc")) or parse_iso(fx.get("start_utc"))
        if lock and lock > ref:
            r["status"] = "open"
        elif lock and (ref - lock).total_seconds() / 3600 > STALE_AFTER_H:
            r["status"] = "stale"
        else:
            r["status"] = "locked"
        flags: list[str] = []
        r["rejected_quotes"] = []
        r["research_attempt"] = research_by_id.get(str(fx["match_id"]))
        if r["status"] == "stale":
            flags.append("STALE_LISTING")
        elif r["status"] == "locked":
            flags.append("LOCKED")
        if not hs.get("complete", True):
            flags.append("HOTSPAWN_PARTIAL")
        ka, kb = aliases.key(fx["team_a"]), aliases.key(fx["team_b"])
        # ---- crowd (ownership only)
        r["crowd_a"], r["crowd_b"] = fx.get("crowd_a_ownership"), fx.get("crowd_b_ownership")
        r["total_picks"] = fx.get("total_picks_ownership")
        # ---- research links / format
        link = links.get(str(fx["match_id"]), {})
        fb_entry = fallback_by_id.get(str(fx["match_id"])) or {}
        # A competition fallback must be an event page, never a team page borrowed from
        # one fixture. Otherwise new opponents inherit an unrelated team's evidence link.
        event_url = (events.get(fx.get("competition") or "", {}) or {}).get("url") or ""
        r["hltv_url"] = link.get("hltv") or (event_url if event_url.startswith("https://www.hltv.org/events/") else None)
        r["hltv_note"] = link.get("note")
        fmt, fmt_src = link.get("format") or "", "HLTV match page" if link.get("format") else ""
        if not fmt and fb_entry.get("format"):
            fmt, fmt_src = fb_entry["format"], f"research pack (fallback_83090640.json; {fb_entry.get('format_source')})"
        researched = r.get("research_attempt") or {}
        if researched.get("format") and not fmt:
            fmt, fmt_src = researched["format"], "HLTV live match-page read"
        # ---- A: Pinnacle. All sources must match teams + competition + unambiguous kickoff + freshness.
        book, alias_b = match_quote(fx, pin_quotes, aliases, iso(ref), fixtures, r["rejected_quotes"], fmt)
        if book:
            oa, ob = (book["odds_b"], book["odds_a"]) if book["flipped"] else (book["odds_a"], book["odds_b"])
            dv = devig_two_way(oa, ob)
            if dv:
                r["book"] = {"source": "Pinnacle", "odds_a": oa, "odds_b": ob, "p_a": round(dv[0], 4), "p_b": round(dv[1], 4),
                             "overround_pct": round(dv[2], 2), "read_utc": book.get("read_utc"), "url": book.get("source_url"),
                             "api_url": book.get("api_url"), "league": book.get("league"), "listed_start": book.get("start_utc"),
                             "gap_h": book.get("gap_h"), "names": f"{book.get('team_a')} vs {book.get('team_b')}"}
                if not fmt and book.get("best_of"):
                    fmt, fmt_src = f"BO{book['best_of']}", "Pinnacle bestOfX"
                if abs(book.get("gap_h") or 0) > 0.01:
                    flags.append("KICKOFF_GAP")
                if alias_b:
                    flags.append("ALIAS")
                age = hours_between(iso(ref), book.get("read_utc"))
                if age is not None and age > 8:
                    flags.append("STALE_PRICE")
        if "book" not in r and not fmt:
            metadata = select_match_metadata(fx, cap.get("esportsbooks", {}).get("matches", []), aliases, iso(ref), fixtures)
            if metadata:
                fmt, fmt_src = f"BO{metadata['best_of']}", "bo3.gg match metadata (secondary)"
                r["format_evidence"] = {"url": metadata.get("source_url"), "read_utc": metadata.get("read_utc")}
        # ---- Secondary book relay is queried only for gaps; keep its provenance distinct from Pinnacle.
        if "book" not in r:
            relay, alias_r = match_quote(fx, relay_quotes, aliases, iso(ref), fixtures, r["rejected_quotes"], fmt)
            if relay:
                oa, ob = (relay["odds_b"], relay["odds_a"]) if relay["flipped"] else (relay["odds_a"], relay["odds_b"])
                dv = devig_two_way(oa, ob)
                if dv:
                    r["relay"] = {"provider": relay.get("provider"), "provider_id": relay.get("provider_id"), "odds_a": oa, "odds_b": ob,
                                  "p_a": round(dv[0], 4), "p_b": round(dv[1], 4), "overround_pct": round(dv[2], 2),
                                  "read_utc": relay.get("read_utc"), "url": relay.get("source_url"),
                                  "provider_url": relay.get("provider_url"), "api_url": relay.get("api_url"),
                                  "listed_start": relay.get("start_utc"), "gap_h": relay.get("gap_h")}
                    flags.append("RELAYED_BOOK")
                    if not relay.get("provider"):
                        flags.append("BOOKMAKER_UNVERIFIED")
                    if not fmt and relay.get("best_of") in (1,3,5,7):
                        fmt, fmt_src = f"BO{relay['best_of']}", "bo3.gg match record"
                    if abs(relay.get("gap_h") or 0) > 0.01: flags.append("KICKOFF_GAP")
                    if alias_r: flags.append("ALIAS")
        # ---- B: Polymarket
        pmq, alias_p = match_quote(fx, pm_quotes, aliases, iso(ref), fixtures, r["rejected_quotes"], fmt)
        if pmq:
            pa_, pb_ = (pmq["price_b"], pmq["price_a"]) if pmq["flipped"] else (pmq["price_a"], pmq["price_b"])
            nz = normalise_prices(pa_, pb_)
            if nz:
                r["pm"] = {"source": "Polymarket", "price_a": pa_, "price_b": pb_, "p_a": round(nz[0], 4), "p_b": round(nz[1], 4),
                           "read_utc": pmq.get("read_utc"), "url": pmq.get("source_url"), "listed_start": pmq.get("start_utc"),
                           "gap_h": pmq.get("gap_h"), "question": pmq.get("question"), "volume": pmq.get("volume")}
                if not fmt and pmq.get("format"):
                    fmt, fmt_src = pmq["format"], "Polymarket market title"
                if alias_p and "ALIAS" not in flags:
                    flags.append("ALIAS")
        r["format"], r["format_source"] = fmt, fmt_src
        if not fmt and r["status"] == "open":
            flags.append("FORMAT_UNKNOWN")
        # ---- C: own line (Valve points) + HLTV rank cross-check
        va, vb = unique(vrs_idx, ka), unique(vrs_idx, kb)
        r["vrs_a"] = {"name": va["name"], "rank": va["rank"], "points": va["points"], "roster": va["roster"],
                      "matches_with_current_five": va.get("matches_with_current_five"),
                      "first_rated_match_current_five": va.get("first_rated_match_current_five")} if va else None
        r["vrs_b"] = {"name": vb["name"], "rank": vb["rank"], "points": vb["points"], "roster": vb["roster"],
                      "matches_with_current_five": vb.get("matches_with_current_five"),
                      "first_rated_match_current_five": vb.get("first_rated_match_current_five")} if vb else None
        if va and vb:
            r["own_p_a"] = round(own_line(va["points"], vb["points"], k), 4)
            r["own_p_b"] = round(1 - r["own_p_a"], 4)
        else:
            r["own_p_a"] = r["own_p_b"] = None
        ha, hb = unique(hltv_idx, ka), unique(hltv_idx, kb)
        r["hltv_rank_a"] = ha["rank"] if ha else None
        r["hltv_rank_b"] = hb["rank"] if hb else None
        r["hltv_team_a"] = ha.get("team_url") if ha else None
        r["hltv_team_b"] = hb.get("team_url") if hb else None
        # ---- choose the rung
        if "book" in r:
            r["p_a"], r["p_b"], r["basis"], r["rung"] = r["book"]["p_a"], r["book"]["p_b"], "Pinnacle odds, margin removed", "A"
        elif "relay" in r:
            r["p_a"], r["p_b"], r["basis"], r["rung"] = r["relay"]["p_a"], r["relay"]["p_b"], f"Secondary sportsbook relay: {r['relay'].get('provider') or ('operator unverified, bo3 ID ' + str(r['relay'].get('provider_id')))} via bo3.gg (not direct-book verified)", "B"
        elif "pm" in r:
            r["p_a"], r["p_b"], r["basis"], r["rung"] = r["pm"]["p_a"], r["pm"]["p_b"], "Polymarket price (prediction market)", "B"
        elif r["own_p_a"] is not None:
            r["p_a"], r["p_b"], r["basis"], r["rung"] = r["own_p_a"], r["own_p_b"], "Our own line (Valve points)", "C"
            if r["status"] == "open":
                flags.append("NO_MARKET")
        else:
            r["p_a"] = r["p_b"] = None
            r["basis"], r["rung"] = "Unresolved", "D"
            if r["status"] == "open":
                flags.append("UNRESOLVED")
        if "book" in r and "pm" in r and abs(r["book"]["p_a"] - r["pm"]["p_a"]) * 100 >= BOOK_PM_SPLIT_PP:
            flags.append("BOOK_PM_SPLIT")
        if r["p_a"] is not None and r["own_p_a"] is not None and r["rung"] in ("A", "B"):
            if (r["p_a"] - 0.5) * (r["own_p_a"] - 0.5) < 0 or abs(r["p_a"] - r["own_p_a"]) * 100 >= SPLIT_PP:
                flags.append("MODEL_MARKET_SPLIT")
        # ---- situational factors (research notes + automated Valve roster age)
        factors = []
        for side, key, team in (("a", ka, va), ("b", kb, vb)):
            for n in active_notes(key, fx["start_utc"], inp["notes"], fx["match_id"]):
                factors.append({"side": side, "team": fx[f"team_{side}"], "kind": n.get("kind"), "summary": n.get("summary"),
                                "argues_against": n.get("verification_status") != "unverified" and n.get("risk_for") == key, "strength": "weak" if n.get("verification_status") == "unverified" else n.get("strength", "weak"),
                                "source_urls": n.get("source_urls", []), "read_utc": n.get("read_utc"),
                                "checked_date_utc": n.get("checked_date_utc"), "verification_status": n.get("verification_status")})
                if n.get("withhold_own_line"):
                    flags.append("ROSTER_UNVERIFIED")
                if team and (n.get("players_in") or n.get("players_out")):
                    roster = {p.casefold() for p in team.get("roster", [])}
                    stale_out = [x for x in n.get("players_out", []) if x.casefold() in roster]
                    missing_in = [x for x in n.get("players_in", []) if x.casefold() not in roster]
                    if stale_out or missing_in:
                        flags.append("VRS_ROSTER_OUTDATED")
            auto = valve_new_five(team, ref)
            if auto:
                factors.append({"side": side, "team": fx[f"team_{side}"], "kind": auto["kind"], "summary": auto["summary"],
                                "argues_against": True, "strength": "moderate",
                                "source_urls": [vrs.get("url")] if vrs.get("url") else [], "automated": True})
        r["factors"] = factors
        # Verify eligibility BEFORE an own line can drive a pick or the leverage consensus.
        vrs_age = hours_between(iso(ref), str(vrs.get("as_of") or "") + "T00:00:00Z")
        own_reasons = []
        if "ROSTER_UNVERIFIED" in flags:
            own_reasons.append("current lineup unresolved after a match-specific roster report")
        if "VRS_ROSTER_OUTDATED" in flags:
            own_reasons.append("verified lineup differs from Valve's five")
        if vrs_age is None or vrs_age < 0 or vrs_age > 45 * 24:
            own_reasons.append("Valve snapshot missing a usable date or older than 45 days")
            if va and vb: flags.append("VRS_STALE")
        if not fmt:
            own_reasons.append("series format not independently confirmed")
        if not va or not vb:
            # Distinguish a team that is absent from Valve's file from one whose name matches several rows.
            missing = []
            for team, key, row in ((fx["team_a"], ka, va), (fx["team_b"], kb, vb)):
                if row:
                    continue
                cands = vrs_idx.get(key) or []
                if not cands:
                    missing.append(f"{team} has no row in Valve's 2026-10-05 standings")
                else:
                    missing.append(f"{team} matches {len(cands)} same-name rows in Valve's 2026-10-05 standings")
            own_reasons.append("; ".join(missing))
        r["own_line_limitation"] = "; ".join(own_reasons)
        if own_reasons:
            r["own_p_a"] = r["own_p_b"] = None
            if va and vb: flags.append("OWN_LINE_WITHHELD")
            flags = [f for f in flags if f != "MODEL_MARKET_SPLIT"]
            if r["rung"] == "C":
                r["p_a"] = r["p_b"] = None
                r["rung"], r["basis"] = "D", "Unresolved: " + r["own_line_limitation"]
        elif r["rung"] == "C":
            flags.append("MODEL_ONLY")
        if str(r["match_id"]) in conflicts:
            flags.append("IDENTITY_CONFLICT")
            r["own_p_a"] = r["own_p_b"] = r["p_a"] = r["p_b"] = None
            r["rung"], r["basis"] = "D", "Unresolved: conflicting Hotspawn fixture records"
        # ---- E: research fallback for open rung-D rows (roster-disambiguated Valve points).
        # The pack's candidate rows (verified line-by-line against Valve's published file at generation)
        # are the evidence of record; the capture's parsed rows are a consistency cross-check.
        fb = fallback_by_id.get(str(r["match_id"]))
        if (r["rung"] == "D" and r["status"] == "open" and fb and fb.get("resolved") and fb.get("format")
                and not str(r["match_id"]) in conflicts):
            sides_fb = fb.get("sides", {})
            sa, sb_ = sides_fb.get("a") or {}, sides_fb.get("b") or {}
            cand_a = [{"rank": c.get("rank"), "points": c.get("points"), "roster": c.get("roster"),
                       "file_name": c.get("file_name"), "details_url": c.get("details_url")}
                      for c in sa.get("valve_candidates") or []]
            cand_b = [{"rank": c.get("rank"), "points": c.get("points"), "roster": c.get("roster"),
                       "file_name": c.get("file_name"), "details_url": c.get("details_url")}
                      for c in sb_.get("valve_candidates") or []]
            ra, ma = disambiguate_valve(cand_a, sa.get("hltv_lineup"))
            rb, mb = disambiguate_valve(cand_b, sb_.get("hltv_lineup"))

            def _consistent(row, key):
                cap_rows = [x for x in (vrs_idx.get(key) or []) if x.get("rank") == row.get("rank")]
                return not cap_rows or cap_rows[0].get("points") == row.get("points")
            if (ra and rb and _consistent(ra, ka) and _consistent(rb, kb)):
                r["vrs_a"] = {"name": ra.get("file_name") or ra.get("name"), "rank": ra.get("rank"), "points": ra.get("points"),
                              "roster": ra.get("roster"), "disambiguated": True, "disambiguation": ma,
                              "details_url": ra.get("details_url") or sa.get("chosen_details_url")}
                r["vrs_b"] = {"name": rb.get("file_name") or rb.get("name"), "rank": rb.get("rank"), "points": rb.get("points"),
                              "roster": rb.get("roster"), "disambiguated": True, "disambiguation": mb,
                              "details_url": rb.get("details_url") or sb_.get("chosen_details_url")}
                r["own_p_a"] = round(own_line(ra["points"], rb["points"], k), 4)
                r["own_p_b"] = round(1 - r["own_p_a"], 4)
                r["p_a"], r["p_b"] = r["own_p_a"], r["own_p_b"]
                r["rung"] = "E"
                r["basis"] = ("Research fallback: our own line (Valve points, row disambiguated by documented "
                              "roster overlap with HLTV's listed lineups; no eligible outside price captured)")
                flags = [f for f in flags if f != "UNRESOLVED"]
                for extra in ("RESEARCH_FALLBACK", "NO_MARKET", "MODEL_ONLY"):
                    if extra not in flags:
                        flags.append(extra)
                if (ma.get("candidates", 0) > 1 or mb.get("candidates", 0) > 1
                        or (ra.get("file_name") and fold(ra.get("file_name")) != fold(fx["team_a"]))
                        or (rb.get("file_name") and fold(rb.get("file_name")) != fold(fx["team_b"]))):
                    flags.append("VALVE_NAME_AMBIGUOUS")
                if fb.get("research_after_lock"):
                    flags.append("POST_LOCK_RESOLUTION")
                    r["basis"] += " (research completed after the pick lock — retrospective analysis only, excluded from graded history)"
                for side, sd in (("a", sa), ("b", sb_)):
                    delta = sd.get("roster_delta_vs_snapshot") or {}
                    if delta.get("in") or delta.get("out"):
                        if "VRS_ROSTER_OUTDATED" not in flags:
                            flags.append("VRS_ROSTER_OUTDATED")
                        r["factors"].append({
                            "side": side, "team": sd.get("team"),
                            "kind": "roster change vs Valve snapshot (research fallback)",
                            "summary": (f"HLTV lists {', '.join(delta.get('in') or []) or 'nobody'} in and "
                                        f"{', '.join(delta.get('out') or []) or 'nobody'} out versus the five "
                                        f"rated in Valve's 2026-10-05 snapshot."),
                            "argues_against": True, "strength": "moderate",
                            "source_urls": [fb.get("hltv_match_url")],
                            "read_utc": fb.get("hltv_read_utc"),
                            "checked_date_utc": (fb.get("hltv_read_utc") or "")[:10],
                            "verification_status": "verified",
                        })
                r["own_line_limitation"] = (
                    "strict own line withheld (" + (r.get("own_line_limitation") or "see flags") +
                    "); rung E resolved identity by documented roster-overlap disambiguation")
                fb_sources = [fb.get("hltv_match_url"), sa.get("chosen_details_url"), sb_.get("chosen_details_url"),
                              sa.get("hltv_rank_url"), sb_.get("hltv_rank_url"),
                              sa.get("hltv_vrs_display_url"), sb_.get("hltv_vrs_display_url"),
                              fb.get("hotspawn_match_url")]
                r["fallback"] = {
                    "pack": "hotspawn/research/fallback_83090640.json",
                    "rule": ">= 3 shared nicknames vs HLTV lineup, strictly best overlap; own-line formula on the chosen rows",
                    "hltv_match_url": fb.get("hltv_match_url"),
                    "hltv_read_utc": fb.get("hltv_read_utc"),
                    "market_check": fb.get("market_check"),
                    "sides": {
                        "a": {kk: sa.get(kk) for kk in ("team", "hltv_lineup", "hltv_rank", "hltv_rank_url",
                                                        "hltv_rank_note", "hltv_vrs_display_rank", "hltv_vrs_display_url",
                                                        "roster_delta_vs_snapshot", "chosen_rank", "chosen_points",
                                                        "disambiguation", "chosen_details_url", "chosen_name", "note")},
                        "b": {kk: sb_.get(kk) for kk in ("team", "hltv_lineup", "hltv_rank", "hltv_rank_url",
                                                         "hltv_rank_note", "hltv_vrs_display_rank", "hltv_vrs_display_url",
                                                         "roster_delta_vs_snapshot", "chosen_rank", "chosen_points",
                                                         "disambiguation", "chosen_details_url", "chosen_name", "note")},
                    },
                    "research_after_lock": fb.get("research_after_lock"),
                    "format": fb.get("format"),
                    "format_source": fb.get("format_source"),
                    "sources": [u for u in fb_sources if u],
                }
        # ---- F: research rung for open rung-D rows with no price and no rating pair.
        # A direction is published only from HLTV's own one-sided verdict on the linked match
        # (every "in favour of" line on one side, every "against" line on the other). No percentage
        # is produced: the opponent is unranked on HLTV and absent from Valve's official standings,
        # so any number would be invented rather than sourced.
        vd = (inp.get("verdicts") or {}).get("fixtures") or []
        vmap = {str(v.get("match_id")): v for v in vd}
        vd_row = vmap.get(str(r["match_id"]))
        if (r["rung"] == "D" and r["status"] == "open" and vd_row
                and str(r["match_id"]) not in conflicts
                and vd_row.get("format") and vd_row.get("pick")
                and (vd_row.get("verdict") or {}).get("one_sided")
                and not (vd_row["verdict"].get("against_pick") or vd_row["verdict"].get("in_favour_of_other"))
                and (vd_row["verdict"].get("in_favour_of_pick") and vd_row["verdict"].get("against_other"))
                and vd_row["pick"] in (fx["team_a"], fx["team_b"])):
            prev_format = r.get("format")
            r["format"] = vd_row["format"]
            r["format_source"] = vd_row.get("format_source") or ""
            r["format_source_kind"] = vd_row.get("format_source_kind") or "primary (HLTV match page)"
            if not prev_format:
                flags = [f for f in flags if f != "FORMAT_UNKNOWN"]
            r["rung"] = "F"
            r["basis"] = ("Research rung F: direction published from HLTV's own one-sided verdict on the "
                          "linked match page; no eligible outside price and no rating pair exist, so no "
                          "win probability is published.")
            r["pick"] = vd_row["pick"]
            r["pick_p"] = None
            r["p_a"] = r["p_b"] = None
            r["own_p_a"] = r["own_p_b"] = None
            # The format gap this row was rejected for is now closed by HLTV's own match page, so the
            # stale "format not confirmed" clause must not survive into the published limitation text.
            if not prev_format:
                parts = [x.strip() for x in (r.get("own_line_limitation") or "").split(";")
                         if x.strip() and "format" not in x.lower()]
                r["own_line_limitation"] = "; ".join(parts)
            r["own_line_limitation"] = (
                (r["own_line_limitation"] + "; " if r.get("own_line_limitation") else "")
                + (inp.get("verdicts") or {}).get("why_not_a_percentage", ""))
            flags = [f for f in flags if f != "UNRESOLVED"]
            for extra in ("DIRECTION_ONLY", "NO_PERCENTAGE", "RESEARCH_FALLBACK", "NO_MARKET"):
                if extra not in flags:
                    flags.append(extra)
            r["verdict"] = {
                "pack": "hotspawn/research/29171622/gap_verdicts.json",
                "rule": (inp.get("verdicts") or {}).get("rule", ""),
                "hltv_match_url": vd_row.get("hltv_match_url"),
                "hltv_analytics_url": vd_row.get("hltv_analytics_url"),
                "hltv_read_utc": vd_row.get("hltv_read_utc"),
                "stage": vd_row.get("stage"),
                "time_match_check": vd_row.get("time_match_check"),
                "sides": vd_row.get("sides"),
                "in_favour_of_pick": vd_row["verdict"].get("in_favour_of_pick") or [],
                "against_other": vd_row["verdict"].get("against_other") or [],
                "head_to_head": vd_row["verdict"].get("head_to_head"),
                "head_to_head_note": vd_row["verdict"].get("head_to_head_note"),
                "checks": (inp.get("verdicts") or {}).get("checks_performed") or [],
                "sources": vd_row.get("sources") or [],
            }

        if r["rejected_quotes"] and r["status"] == "open":
            flags.append("REJECTED_QUOTE")
            if any("older than 8 h" in reason for q in r["rejected_quotes"] for reason in q["reasons"]):
                flags.append("STALE_PRICE")
        # Headline pick always follows the larger published probability. A genuine exact tie can
        # use an eligible independent estimate, but an arbitrary first-listed team is never a pick.
        if r["rung"] != "F":
            # Rung F keeps the direction set from the published verdict; it has no percentage to compare.
            r["pick"] = r["pick_p"] = None
        if r["p_a"] is not None:
            if abs(r["p_a"] - 0.5) < 0.01: flags.append("COIN_FLIP")
            if r["p_a"] == r["p_b"]:
                if r["own_p_a"] is not None and r["own_p_a"] != 0.5:
                    a_wins = r["own_p_a"] > 0.5
                else:
                    flags.append("NO_DIRECTION")
                    r["rung"], r["basis"] = "D", "Unresolved: exact tie, no supported direction"
                    r["p_a"] = r["p_b"] = None
                    a_wins = None
            else:
                a_wins = r["p_a"] > r["p_b"]
            if a_wins is not None:
                r["pick"] = r["team_a"] if a_wins else r["team_b"]
                r["pick_p"] = r["p_a"] if a_wins else r["p_b"]
        if r["rung"] == "D" and r["status"] == "open": flags.append("UNRESOLVED")
        r["flags"] = sorted(set(flags))
        r["strategy"] = strategy(r) if r["status"] == "open" else None
        if r["status"] == "open" and r["strategy"] and r["strategy"]["class"] == "NO CROWD DATA":
            flags.append("CROWD_MISSING")
        r["flags"] = sorted(set(flags))
        srcs = [u for u in [fx.get("source_url"), r.get("hotspawn_match_url"), r.get("hltv_url"),
                            (r.get("book") or {}).get("url"), (r.get("pm") or {}).get("url"),
                            (r.get("relay") or {}).get("url"), (r.get("relay") or {}).get("provider_url"),
                            (r.get("research_attempt") or {}).get("url"), (r.get("format_evidence") or {}).get("url"),
                            vrs.get("url") if (va or vb) else None,
                            *((r.get("fallback") or {}).get("sources") or []),
                            # Rung F has no price, rating or market to cite: the row's own source list
                            # has to carry the pages the direction was actually read from.
                            *((r.get("verdict") or {}).get("sources") or [])] if u]
        r["sources"] = list(dict.fromkeys(srcs))
        rows.append(r)
    meta = {"reference_utc": iso(ref), "k": k, "k_label": k_label, "vrs": {k2: vrs.get(k2) for k2 in ("as_of", "url", "file", "status")},
            "hltv": {k2: hltv.get(k2) for k2 in ("status", "url", "read_utc", "carry_note")},
            "pinnacle": {k2: cap.get("pinnacle", {}).get(k2) for k2 in ("status", "read_utc", "page_url", "markets_url", "error")},
            "polymarket": {k2: cap.get("polymarket", {}).get(k2) for k2 in ("status", "read_utc", "error")},
            "hotspawn": {"pages": hs.get("pages", []), "complete": hs.get("complete"), "week": hs.get("week"),
                         "stale_carry": hs.get("stale_carry"), "conflicts": hs.get("conflicts", [])},
            "esportsbooks": {"status": cap.get("esportsbooks", {}).get("status", "not requested")},
            "calibration": {k2: calib.get(k2) for k2 in ("status", "k", "k_source", "n_train", "n_test", "holdout", "valve_commit", "last_window")}}
    return rows, meta


def update_history(rows: list[dict], history: dict, ref_iso: str) -> dict:
    # Rows may disappear from the next Hotspawn payload. Freeze their existing pre-lock record too.
    ref = parse_iso(ref_iso)
    for record in history.values():
        lock = parse_iso(record.get("lock_utc"))
        if ref and lock and lock <= ref:
            record["frozen"] = True
    for r in rows:
        mid = str(r["match_id"])
        if r["status"] == "open" and r.get("pick") and "POST_LOCK_RESOLUTION" not in (r.get("flags") or []):
            history[mid] = {"match_id": mid, "team_a": r["team_a"], "team_b": r["team_b"], "competition": r["competition"],
                            "start_utc": r["start_utc"], "lock_utc": r["lock_utc"], "points": r["points"],
                            "pick": r["pick"], "pick_p": r["pick_p"], "p_a": r["p_a"], "p_b": r["p_b"], "basis": r["basis"],
                            "leaderboard_pick": (r.get("strategy") or {}).get("leaderboard_pick"),
                            "class": (r.get("strategy") or {}).get("class"), "rule_version": "v3-evidence-2026-10-16",
                            "crowd_a": r.get("crowd_a"), "crowd_b": r.get("crowd_b"), "as_of": ref_iso, "frozen": False}
        elif mid in history and r["status"] != "open":
            history[mid]["frozen"] = True
    return history


def day1_review(inp: dict, k: float) -> list[dict]:
    aliases = Aliases()
    vrs_idx = index_by_key(inp["capture"].get("vrs", {}).get("teams", []), aliases)
    out = []
    for m in inp["day1"].get("matches", []):
        dv = devig_two_way(m["odds_a"], m["odds_b"])
        va, vb = unique(vrs_idx, aliases.key(m["team_a"])), unique(vrs_idx, aliases.key(m["team_b"]))
        own_a = round(own_line(va["points"], vb["points"], k), 4) if va and vb else None
        row = {**m, "p_a": round(dv[0], 4), "p_b": round(dv[1], 4), "overround_pct": round(dv[2], 2),
               "own_p_a": own_a, "own_p_b": None if own_a is None else round(1 - own_a, 4),
               "vrs_points_a": va["points"] if va else None, "vrs_points_b": vb["points"] if vb else None}
        row["pick"] = m["team_a"] if row["p_a"] >= row["p_b"] else m["team_b"]
        notes = []
        for side in ("a", "b"):
            key = aliases.key(m[f"team_{side}"])
            for n in active_notes(key, m["start_utc"], inp["notes"], m["hotspawn_id"]):
                notes.append({"side": side, "kind": n.get("kind"), "argues_against": n.get("risk_for") == key,
                              "strength": n.get("strength", "weak")})
        row["factors"] = notes
        row["strategy"] = strategy({**row, "rung": "A", "points": m.get("points"), "crowd_a": m.get("crowd_a"), "crowd_b": m.get("crowd_b"),
                                    "factors": notes})
        row["pick_correct"] = row["pick"] == m["winner"]
        lp = (row["strategy"] or {}).get("leaderboard_pick")
        row["leaderboard_correct"] = (lp == m["winner"]) if lp else None
        out.append(row)
    return out


def attach_results(rows: list[dict], inp: dict) -> None:
    """Result for locked fixtures: verified (research/results.json, HLTV) first, then the provisional
    Polymarket-resolution feed (Polymarket names HLTV as its resolution source)."""
    aliases = Aliases()
    resolved = inp["capture"].get("polymarket", {}).get("resolved", []) or []
    for r in rows:
        r["result"] = None
        if r["status"] == "open":
            continue
        manual = inp["results"].get(str(r["match_id"]))
        if manual and manual.get("winner"):
            r["result"] = {**manual, "kind": "verified (HLTV)"}
            continue
        ka, kb = aliases.key(r["team_a"]), aliases.key(r["team_b"])
        for q in resolved:
            if {aliases.key(q.get("team_a", "")), aliases.key(q.get("team_b", ""))} != {ka, kb}:
                continue
            gap = hours_between(q.get("start_utc"), r["start_utc"])
            if gap is None or abs(gap) > 12:
                continue
            wk = aliases.key(q.get("winner", ""))
            winner = r["team_a"] if wk == ka else r["team_b"] if wk == kb else None
            if winner:
                r["result"] = {"winner": winner, "kind": "provisional (Polymarket resolution; resolution source HLTV)",
                               "source_url": q.get("source_url"), "read_utc": q.get("read_utc")}
            break


def graded_history(history: dict, rows: list[dict], results: dict | None = None) -> list[dict]:
    """Grade only frozen picks, preferring a verified result even after its fixture leaves the live feed.

    Historical rows disappear from Hotspawn's current payload. ``results.json`` is keyed by the frozen
    Hotspawn id, so it remains authoritative for those matches and is also preferred over a provisional
    resolution attached to a current row.
    """
    by_id = {str(r["match_id"]): r for r in rows}
    results = results or {}
    out = []
    for mid, h in sorted(history.items(), key=lambda kv: kv[1].get("start_utc") or ""):
        r = by_id.get(mid)
        manual = results.get(str(mid))
        res = {**manual, "kind": "verified (HLTV)"} if manual and manual.get("winner") else (r or {}).get("result")
        if not h.get("frozen"):
            continue
        out.append({**h, "result": res, "pick_correct": (res["winner"] == h.get("pick")) if res else None,
                    "leaderboard_correct": (res["winner"] == h.get("leaderboard_pick")) if res and h.get("leaderboard_pick") else None})
    return out


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def flat(r: dict) -> dict:
    s = r.get("strategy") or {}
    b, p = r.get("book") or r.get("relay") or {}, r.get("pm") or {}
    return {
        "match_id": r["match_id"], "status": r["status"], "competition": r["competition"], "tier": r["tier"],
        "points": r["points"], "start_utc": r["start_utc"], "lock_utc": r["lock_utc"], "team_a": r["team_a"], "team_b": r["team_b"],
        "pick": r.get("pick") or "", "p_a_pct": "" if r.get("p_a") is None else round(r["p_a"] * 100, 1),
        "p_b_pct": "" if r.get("p_b") is None else round(r["p_b"] * 100, 1), "basis": r.get("basis"), "rung": r.get("rung"),
        "format": r.get("format"), "format_source": r.get("format_source"),
        "outside_book_provider": b.get("source") or b.get("provider", ""),
        "outside_book_source": b.get("url", ""), "own_line_limitation": r.get("own_line_limitation", ""),
        "pinnacle_odds_a": (r.get("book") or {}).get("odds_a", ""), "pinnacle_odds_b": (r.get("book") or {}).get("odds_b", ""), "pinnacle_read_utc": (r.get("book") or {}).get("read_utc", ""),
        "polymarket_price_a": p.get("price_a", ""), "polymarket_price_b": p.get("price_b", ""), "polymarket_read_utc": p.get("read_utc", ""),
        "own_p_a_pct": "" if r.get("own_p_a") is None else round(r["own_p_a"] * 100, 1),
        "vrs_points_a": (r.get("vrs_a") or {}).get("points", ""), "vrs_points_b": (r.get("vrs_b") or {}).get("points", ""),
        "hltv_rank_a": r.get("hltv_rank_a") or "", "hltv_rank_b": r.get("hltv_rank_b") or "",
        "crowd_a_ownership_pct": "" if r.get("crowd_a") is None else r["crowd_a"],
        "crowd_b_ownership_pct": "" if r.get("crowd_b") is None else r["crowd_b"],
        "leaderboard_class": s.get("class", ""), "leaderboard_pick": s.get("leaderboard_pick", ""),
        "flags": ";".join(r.get("flags", [])), "hotspawn_url": r.get("hotspawn_match_url") or r.get("lobby_url"),
        "hltv_url": r.get("hltv_url") or "", "pinnacle_url": (r.get("book") or {}).get("url", ""), "polymarket_url": p.get("url", ""),
        "sources": " | ".join(r.get("sources", [])),
    }


def main() -> int:
    inp = load_inputs()
    if not inp["capture"].get("hotspawn", {}).get("fixtures"):
        print("model: no capture with fixtures; nothing to do")
        return 1
    rows, meta = build_rows(inp)
    rows.sort(key=lambda r: ({"open": 0, "locked": 1, "stale": 2}[r["status"]], r["start_utc"], r["match_id"]))
    attach_results(rows, inp)
    history = update_history(rows, inp["history"], meta["reference_utc"])
    graded = graded_history(history, rows, inp["results"])
    review = day1_review(inp, meta["k"])
    d2_matches = inp["day2"].get("day2_matches", [])
    d2_ids = {str(m.get("hotspawn_id")) for m in d2_matches}
    d2_graded = [g for g in graded if str(g.get("match_id")) in d2_ids and g.get("result")]
    d2_picks = [g for g in d2_graded if g.get("pick")]
    d2_unarchived = [str(m.get("hotspawn_id")) for m in d2_matches if not m.get("prelock_pick")]
    day2_review = {
        "matches": len(d2_matches), "archived_picks": len(d2_picks), "graded_picks": len(d2_picks),
        "picks_correct": sum(1 for g in d2_picks if g.get("pick_correct")),
        "leaderboard_correct": sum(1 for g in d2_picks if g.get("leaderboard_correct")),
        "unarchived_match_ids": d2_unarchived,
    }
    open_rows = [r for r in rows if r["status"] == "open"]
    summary = {
        "generated_utc": now_iso(), "session": SESSION, "reference_utc": meta["reference_utc"],
        "fixtures": len(rows), "open": len(open_rows),
        "locked_recent": sum(1 for r in rows if r["status"] == "locked"),
        "stale_listings": sum(1 for r in rows if r["status"] == "stale"),
        "open_with_pick": sum(1 for r in open_rows if r.get("pick")),
        "open_rung": {x: sum(1 for r in open_rows if r.get("rung") == x) for x in "ABCDEF"},
        "open_unresolved": sum(1 for r in open_rows if r.get("rung") == "D"),
        "open_direction_only": sum(1 for r in open_rows if r.get("rung") == "F"),
        "open_flagged": sum(1 for r in open_rows if set(r["flags"]) - {"ALIAS"}),
        "leaderboard_classes": {c: sum(1 for r in open_rows if (r.get("strategy") or {}).get("class") == c)
                                for c in ("VALUE", "CONTRARIAN", "SITUATIONAL", "LONG SHOT", "CHALK",
                                          "EVIDENCE LIMITED", "NO CROWD DATA", "DIRECTION ONLY")},
        "next_lock_utc": min((r["lock_utc"] for r in open_rows if r.get("lock_utc")), default=None),
        "hotspawn_complete": meta["hotspawn"]["complete"],
        "sources": {"pinnacle": meta["pinnacle"].get("status"), "polymarket": meta["polymarket"].get("status"),
                    "vrs": meta["vrs"].get("status"), "hltv": meta["hltv"].get("status")},
        "own_line_k": meta["k"], "own_line_k_source": meta["k_label"],
        "graded_since_launch": {"n": sum(1 for g in graded if g.get("result")),
                                "picks_correct": sum(1 for g in graded if g.get("pick_correct")),
                                "leaderboard_correct": sum(1 for g in graded if g.get("leaderboard_correct"))},
        "day1_review": {"matches": len(review), "picks_correct": sum(1 for x in review if x["pick_correct"]),
                        "leaderboard_correct": sum(1 for x in review if x.get("leaderboard_correct"))},
        "day2_review": day2_review,
    }
    board = {"meta": meta, "summary": summary, "rows": rows, "day1": {"info": {k2: v for k2, v in inp["day1"].items() if k2 != "matches"},
                                                                      "matches": review},
             "flag_text": FLAG_TEXT, "history": history, "graded": graded,
             "twc_days": inp["twc_days"], "gap_verdicts": inp["verdicts"]}
    write_json(DATA / "board.json", board)
    write_json(DATA / "summary.json", summary)
    write_json(DATA / "pick_history.json", history)
    fields = list(flat(rows[0]).keys()) if rows else []
    write_csv(DATA / "picks.csv", [flat(r) for r in open_rows], fields)
    write_csv(DATA / "all_fixtures.csv", [flat(r) for r in rows], fields)
    flag_rows = [{"match_id": r["match_id"], "status": r["status"], "match": f"{r['team_a']} vs {r['team_b']}", "flag": f,
                  "meaning": FLAG_TEXT.get(f, ""), "hotspawn_url": r.get("hotspawn_match_url") or r.get("lobby_url"),
                  "evidence": " | ".join(r.get("sources", []))} for r in rows for f in r["flags"]]
    write_csv(DATA / "flags.csv", flag_rows, ["match_id", "status", "match", "flag", "meaning", "hotspawn_url", "evidence"])
    print(f"model: {summary['open']} open / {summary['fixtures']} fixtures; picks {summary['open_with_pick']}; "
          f"rungs {summary['open_rung']}; classes {summary['leaderboard_classes']}")
    return 0


if __name__ == "__main__":
    from common import run_main
    run_main(main)
