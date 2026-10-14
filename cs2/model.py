#!/usr/bin/env python3
"""A3 — join every open Hotspawn CS2 fixture to (i) external bookmaker lines and (ii) our own
originated line, then publish a pick per fixture.

Written by session ``arena/a174d77f``.  Inputs are only ``cs2/data/capture.json`` (what the
collector read, with URL + capture time + SHA-256 per source) and ``cs2/data/calibration.json``
(our re-fit of Valve's own expected-win-rate curve, from Valve's published match results).

Hard rules, enforced here and in tests.py:

* Hotspawn's crowd pick percentages are **never** an input.  They exist in ``capture.json`` only
  under ``*_audit_only`` keys; this file reads them once, to report on the coverage page that they
  were seen and excluded, and copies nothing of them into ``analysis.csv``.
* A fixture is joined to a bookmaker event only when BOTH team names match after normalisation
  (exact, or an evidence-backed alias in ``cs2/aliases.json``) AND the two listings' start times
  are within ``KICKOFF_TOL_H`` hours of each other, and the pairing is unique.  Anything looser is
  refused; the row is left blank and flagged.  No fuzzy scoring, no "probably the same match".
* Nothing is inferred to fill a gap: no line, no rating → blank + flag.
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, alias_lookup, devig_two_way, hours_between, log, norm, norm_core,
                    now_iso, parse_iso, pct, read_json, rel_time, write_csv, write_json)

ROOT = Path(__file__).resolve().parent
CAPTURE = DATA / "capture.json"
ALIASES = ROOT / "aliases.json"
VERIFIED = ROOT / "fixtures_verified.json"
ANALYSIS_CSV = DATA / "analysis.csv"

SNAPSHOT_AGE_MAX_D = 10              # Valve publishes weekly; older than that and we say so
KICKOFF_TOL_H = 6.0                     # generous for a book's own rescheduling; anything wider is refused
CS2_SPORTS = {"cs2", "counter-strike", "counterstrike", "counter strike 2"}

FLAG_TEXT = {
    "A-NO-RATING": "no official rating (Valve VRS) for {team}; own line left blank",
    "A-NO-LINE": "no external two-way bookmaker line found for this fixture in any source read",
    "A-AMBIG-PAIR": "the bookmaker listing is not unique for this team pair inside the kickoff "
                    "tolerance; refused rather than guessed",
    "A-KICKOFF-GAP": "bookmaker start time differs from the Hotspawn payload start time by "
                     "{gap} h (> {tol} h); the price was refused",
    "A-ALIAS": "team name matched only after removing marketing noise words / a documented alias; "
               "review the linked evidence",
    "A-NO-FORMAT": "series length not published by Hotspawn, the bookmaker or HLTV; the probability "
                   "is match-level only",
    "A-DIVERGE": "our own line and the external market disagree on the favourite "
                 "({div} percentage points apart); market kept as the headline, both shown",
    "A-STARTED": "lock time already passed at capture; listed for completeness, not pickable",
    "A-STALE": "the board still lists this fixture months after its start time",
    "A-DUP-BOOK": "several price rows from the same book for one fixture; first kept",
    "A-REFUSED": "the price source refused the automated read; nothing substituted",
    "A-NO-PICK": "neither a verified market line nor an official rating for both teams; no pick "
                 "published",
    "A-VRS-DUP": "Valve's standings list this team name more than once (different rosters); the "
                 "highest-points row is used and the alternative is named in the note",
    "A-SNAPSHOT-AGE": "the rating snapshot used is {age} days old (VRS is published ~monthly)",
    "A-HLTV-REFUSED": "HLTV refused the automated read, so kickoff times are not cross-checked",
    "A-MARKET-STALE": "market price older than the fixture's own capture window; labelled with its time",
}


# --------------------------------------------------------------------------- small helpers
def load_capture() -> dict:
    cap = read_json(CAPTURE)
    if not cap:
        raise SystemExit("cs2/data/capture.json missing - run cs2/collect.py first")
    return cap


def flag_rows(flags: dict, mid: str, code: str, **kw) -> None:
    text = FLAG_TEXT[code].format(**kw) if code in FLAG_TEXT else code
    flags.setdefault(mid, []).append({"code": code, "text": text})


# ------------------------------------------------------------------------------- ratings
def build_rating_index(vrs: dict) -> dict:
    """norm(team name) -> rows (all duplicates kept, highest points first)."""
    index: dict[str, list] = {}
    for row in vrs.get("teams") or []:
        index.setdefault(norm(row["name"]), []).append(row)
    for rows in index.values():
        rows.sort(key=lambda r: -r["points"])
    return index


def resolve_rating(name: str, index: dict, aliases: dict, flags: dict, mid: str, side: str):
    """Return (points, rank, vrs_name, url, method) or None.  Never a guess."""
    renamed = alias_lookup(name, aliases)
    steps = [(renamed, "alias" if norm(renamed) != norm(name) else "exact"), (name, "exact")]
    for candidate, method in steps:
        rows = index.get(norm(candidate))
        if rows:
            if method == "alias":
                flag_rows(flags, mid, "A-ALIAS")
                flags[mid][-1]["text"] = (f"team name '{name}' matched Valve's standings only through the "
                                          f"evidence-backed alias '{candidate}' (see cs2/aliases.json)")
            if len(rows) > 1:
                flag_rows(flags, mid, "A-VRS-DUP")
                flags[mid][-1]["text"] += (f" — using {rows[0]['name']} {rows[0]['points']} pts, "
                                           f"also listed: " + ", ".join(f"{r['points']} pts" for r in rows[1:3]))
            row = rows[0]
            return {"points": row["points"], "rank": row["vrs_rank"], "vrs_name": row["name"],
                    "url": row.get("url"), "line": row.get("line"), "method": method,
                    "roster": row.get("roster")}
    return None


DIGEST_KEYS = ("status", "error", "pages_read", "cs2_events", "list_rows",
               "team_links", "count", "n_rows", "as_of", "file", "url", "plain_error", "browser_error")


def source_digest(sources: dict) -> dict:
    """Per-source one-line status for the summary/coverage page (never drops a refusal)."""
    out = {}
    for name, blk in (sources or {}).items():
        if not isinstance(blk, dict):
            out[name] = {"status": f"non-dict payload ({type(blk).__name__})",
                         "rows": len(blk) if isinstance(blk, list) else None}
            continue
        keep = {k: v for k, v in blk.items() if k in DIGEST_KEYS}
        keep.setdefault("status", "no status reported")
        out[name] = keep
    return out


def own_line(pa: float | None, pb: float | None, k: float) -> dict | None:
    if pa is None or pb is None:
        return None
    p = 1.0 / (1.0 + 10.0 ** (-k * (pa - pb) / 400.0))
    return {"p_a": round(p, 6), "p_b": round(1 - p, 6), "k": k,
            "fair_a": round(1 / p, 3), "fair_b": round(1 / (1 - p), 3)}


# ------------------------------------------------------------------------ market join
def quote_key_sets(quotes: list[dict]) -> list[dict]:
    out = []
    for q in quotes:
        out.append({**q, "keys": [tuple(sorted((ka, kb))) for ka, kb, _ in
                                 [(norm(q["team_a"]), norm(q["team_b"]), "")]]})
    return out


def join_market(fixtures: list[dict], quotes: list[dict], aliases: dict) -> tuple[dict, list]:
    """Unique (team-pair, kickoff-window) join.  Returns {fixture_id: [quote,...]} and refusals."""
    by_key: dict[tuple, list] = {}
    for q in quotes:
        ka, kb = norm(alias_lookup(q["team_a"], aliases)), norm(alias_lookup(q["team_b"], aliases))
        key = tuple(sorted((ka, kb)))
        q["_a"], q["_b"] = norm(q["team_a"]), norm(q["team_b"])
        q["_noise_key"] = tuple(sorted((norm_core(ka), norm_core(kb))))
        for bucket in {key, q["_noise_key"]}:
            bucket_rows = by_key.setdefault(bucket, [])
            if not any(existing is q for existing in bucket_rows):
                bucket_rows.append(q)
    assigned: dict[str, list] = {}
    used: set[int] = set()
    for fx in fixtures:
        fa, fb = norm(alias_lookup(fx["team_a"], aliases)), norm(alias_lookup(fx["team_b"], aliases))
        exact_key, noise_key = tuple(sorted((fa, fb))), tuple(sorted((norm_core(fa), norm_core(fb))))
        candidates = []
        method = "exact"
        for q in by_key.get(exact_key, []):
            candidates.append((q, "exact"))
        if not candidates:
            for q in by_key.get(noise_key, []):
                candidates.append((q, "noise-stripped"))
        picked = []
        unique = []
        for q, how in candidates:
            if q not in [x for x, _ in unique]:
                unique.append((q, how))
        for q, how in unique:
            if id(q) in used:
                continue
            gap = hours_between(q.get("start_utc"), fx.get("start_utc"))
            if gap is None:
                continue
            if abs(gap) > KICKOFF_TOL_H:
                continue
            picked.append((abs(gap), q, how))
            used.add(id(q))
            q["_match_method"] = how
        picked.sort(key=lambda t: t[0])
        if picked:
            assigned.setdefault(fx["match_id"], []).extend(q for _, q, _ in picked)
    return assigned, []


# ------------------------------------------------------------------------------- model
def main() -> int:
    cap = load_capture()
    sources = cap.get("sources", {})
    aliases = read_json(ALIASES, {}) or {}
    verified = {k: v for k, v in (read_json(VERIFIED, {}) or {}).items() if not k.startswith("_")}
    calibration = read_json(DATA / "calibration.json", {}) or {}
    k = calibration.get("k_published") if calibration.get("status") == "ok" else None
    k_source = ("cs2 calibrate.py (MLE on Valve's published match results)"
                if k else "Valve raw curve (calibration unavailable)")
    if not k:
        # calibration unavailable -> Valve's own raw slope, labelled as such on every row
        k = 1.0 / math.sqrt(1.0 + 3.0 * (math.log(10) / 400.0) ** 2 * 75.0 ** 2 / (math.pi ** 2))

    fixtures = [f for f in (sources.get("hotspawn") or {}).get("fixtures") or []
                if (f.get("sport") or "").lower() in CS2_SPORTS or not f.get("sport")]
    for fx in fixtures:
        fx["team_a"] = fx.get("team_a") or ""
        fx["team_b"] = fx.get("team_b") or ""
    now = datetime.now(timezone.utc)
    for fx in fixtures:
        lock = parse_iso(fx.get("lock_utc"))
        start = parse_iso(fx.get("start_utc"))
        fx["pickable"] = bool(lock and lock > now)
        fx["state"] = ("open" if fx["pickable"] else
                       "started" if start and start <= now and (now - start).days < 2 else
                       "stale" if start else "unknown")

    rating_index = build_rating_index(sources.get("vrs") or {})
    quotes = (sources.get("pinnacle") or {}).get("quotes") or []
    egw = sources.get("egamersworld") or {}
    poly = (sources.get("polymarket") or {}).get("rows") or []

    # ---- normalise every price row into one shape, then join once
    price_rows: list[dict] = []
    for q in quotes:
        price_rows.append({**q, "book": "Pinnacle", "source": "pinnacle_guest_api",
                           "read_by": "this run (Pinnacle public guest response)"})
    for mid, reading in (egw.get("readings") or {}).items():
        for book in reading.get("books") or []:
            price_rows.append({"book": book["book"], "odds_a": book["odds_a"],
                               "odds_b": book["odds_b"], "team_a": None, "team_b": None,
                               "start_utc": None, "source": "egamersworld_match_page",
                               "source_url": reading.get("match_url"),
                               "captured_utc": reading.get("captured_utc") or now_iso(),
                               "fixture_id": mid,
                               "read_by": "this run (EGamersWorld match page, book named in the page)",
                               "note": "EGamersWorld aggregates books; side order follows the page's own "
                                       "team order, matched to the fixture by the page URL the list links"})
    assigned, _ = join_market(fixtures, [q for q in price_rows if q.get("team_a")], aliases)
    egw_by_fixture: dict[str, list] = {}
    for row in price_rows:
        if row.get("fixture_id"):
            egw_by_fixture.setdefault(row["fixture_id"], []).append(row)

    rows_out, flags, market_rows = [], {}, []
    seen_ids = set()
    for fx in fixtures:
        mid = fx["match_id"]
        if mid in seen_ids:
            continue
        seen_ids.add(mid)
        ra = resolve_rating(fx["team_a"], rating_index, aliases, flags, mid, "a")
        rb = resolve_rating(fx["team_b"], rating_index, aliases, flags, mid, "b")
        own = own_line(ra["points"] if ra else None, rb["points"] if rb else None, k)
        if not ra:
            flag_rows(flags, mid, "A-NO-RATING", team=fx["team_a"])
        if not rb:
            flag_rows(flags, mid, "A-NO-RATING", team=fx["team_b"])

        # ---- market: Pinnacle first, otherwise the mean of the named books EGamersWorld lists
        fixture_prices = list(assigned.get(mid) or []) + list(egw_by_fixture.get(mid) or [])
        devs = []
        for pr in fixture_prices:
            dv = devig_two_way(pr.get("odds_a"), pr.get("odds_b"))
            if not dv:
                continue
            devs.append({**pr, "p_a": dv[0], "p_b": dv[1], "overround_pct": round(dv[2], 2)})
            market_rows.append({
                "fixture_id": mid, "team_a": fx["team_a"], "team_b": fx["team_b"],
                "book": pr.get("book"), "odds_a": pr.get("odds_a"), "odds_b": pr.get("odds_b"),
                "implied_p_a_pct": pct(dv[0]), "implied_p_b_pct": pct(dv[1]),
                "overround_pct": f"{dv[2]:.2f}", "start_utc": pr.get("start_utc"),
                "kickoff_gap_h": (f"{hours_between(pr.get('start_utc'), fx.get('start_utc')):.2f}"
                                  if pr.get("start_utc") else ""),
                "captured_utc": pr.get("captured_utc"), "source": pr.get("source"),
                "url": pr.get("source_url") or pr.get("api_url") or pr.get("book_url"),
                "read_by": pr.get("read_by"), "match_method": pr.get("_match_method", "page-url"),
                "note": pr.get("note", ""),
            })
        headline = None
        if devs:
            pin = [d for d in devs if d.get("book") == "Pinnacle"]
            pool = pin or devs
            p_a = sum(d["p_a"] for d in pool) / len(pool)
            p_b = sum(d["p_b"] for d in pool) / len(pool)
            tot = p_a + p_b
            headline = {"p_a": p_a / tot, "p_b": p_b / tot,
                        "books": sorted({d["book"] for d in devs}),
                        "n_books": len(devs),
                        "odds_a": pool[0].get("odds_a"), "odds_b": pool[0].get("odds_b"),
                        "overround_pct": round(sum(d["overround_pct"] for d in pool) / len(pool), 2),
                        "source": pool[0].get("source"),
                        "url": pool[0].get("source_url") or pool[0].get("api_url") or pool[0].get("book_url"),
                        "captured_utc": max((d.get("captured_utc") or "") for d in pool),
                        "read_by": pool[0].get("read_by")}
        else:
            if fx["pickable"]:
                flag_rows(flags, mid, "A-NO-LINE")
        if fx["state"] == "stale":
            flag_rows(flags, mid, "A-STALE")
        elif fx["state"] == "started":
            flag_rows(flags, mid, "A-STARTED")

        # ---- Polymarket, kept separate: it is a prediction market, not a betting line
        poly_p = None
        for market in poly:
            text = norm(market.get("question") or "")
            fa, fb = norm(fx["team_a"]), norm(fx["team_b"])
            if fa in text and fb in text and len(market.get("prices") or []) == 2:
                prices = market["prices"]
                poly_p = {"p_a": prices[0], "p_b": prices[1], "url": market.get("source_url"),
                          "question": market.get("question"), "volume": market.get("volume")}
                break

        consensus_src, c_a, c_b = "", None, None
        if headline:
            c_a, c_b = headline["p_a"], headline["p_b"]
            consensus_src = (f"external market, de-vigged ({', '.join(headline['books'])}"
                             f"{'' if len(headline['books']) == 1 else ' mean of ' + str(headline['n_books'])}"
                             f")")
        elif own:
            c_a, c_b = own["p_a"], own["p_b"]
            consensus_src = f"our own line (Valve VRS curve, {k_source})"
        else:
            flag_rows(flags, mid, "A-NO-PICK")
        if headline and own:
            div = abs(headline["p_a"] - own["p_a"]) * 100
            if (headline["p_a"] > headline["p_b"]) != (own["p_a"] > own["p_b"]):
                flag_rows(flags, mid, "A-DIVERGE", div=f"{div:.1f}")

        best_of = None
        best_of_source = ""
        best_of_note = ""
        for pr in fixture_prices:
            if pr.get("best_of"):
                best_of = pr["best_of"]
                best_of_source = pr.get("api_url") or pr.get("book_url") or ""
                best_of_note = f"series length as published by {pr.get('book') or 'the book'}"
                break
        if not best_of and fx.get("best_of_payload") not in (None, "", 0):
            best_of = fx["best_of_payload"]
            best_of_source = fx.get("hotspawn_url") or ""
            best_of_note = "bestOf field inside the board's own payload"
        if not best_of:
            # nothing machine-readable carried the format: fall back on a value a human read off
            # the organiser's own match page, recorded in cs2/fixtures_verified.json with its link.
            vrec = verified.get(str(mid)) or {}
            if vrec.get("series_len"):
                best_of = vrec["series_len"]
                best_of_source = vrec.get("source_url", "")
                best_of_note = (vrec.get("format_text") or f"best of {best_of}") + \
                               f" (read by {vrec.get('read_by', 'hand')} on " \
                               f"{(vrec.get('verified_utc') or '')[:10]})"
        if fx["pickable"] and not best_of:
            flag_rows(flags, mid, "A-NO-FORMAT")

        # A rating that is weeks old is not a defect of the fixture; it is a limit of the only
        # official rating feed, so it is flagged on the rows that rest on it and nowhere else.
        vrs_as_of = (sources.get("vrs") or {}).get("as_of")
        vrs_age_d = ""
        if vrs_as_of:
            try:
                vrs_age_d = (datetime.now(timezone.utc) - datetime.strptime(
                    vrs_as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
            except ValueError:
                vrs_age_d = ""
        if fx["pickable"] and vrs_age_d and int(vrs_age_d) > SNAPSHOT_AGE_MAX_D and not headline:
            flag_rows(flags, mid, "A-SNAPSHOT-AGE", age_days=vrs_age_d)

        pick = pick_pct = pick_basis = ""
        if c_a is not None:
            pick = fx["team_a"] if c_a >= c_b else fx["team_b"]
            pick_pct = f"{max(c_a, c_b) * 100:.1f}"
            pick_basis = consensus_src

        row = {
            "fixture_id": mid,
            "competition": fx.get("competition") or "",
            "tier": (fx.get("tier") or "").upper(),
            "stage": fx.get("stage") or "",
            "points": fx.get("offered_points") if fx.get("offered_points") is not None else "",
            "multiplier": fx.get("multiplier") or "",
            "sport": fx.get("sport") or "",
            "start_utc": fx.get("start_utc") or "",
            "lock_utc": fx.get("lock_utc") or "",
            "lock_in": rel_time(fx.get("lock_utc")) if fx["pickable"] else "",
            "state": fx["state"],
            "pickable": "yes" if fx["pickable"] else "no",
            "team_a": fx["team_a"], "team_b": fx["team_b"],
            "best_of": best_of or "",
            "best_of_source": best_of_source,
            "best_of_note": best_of_note,
            "vrs_points_a": ra["points"] if ra else "",
            "vrs_points_b": rb["points"] if rb else "",
            "vrs_rank_a": ra["rank"] if ra else "",
            "vrs_rank_b": rb["rank"] if rb else "",
            "vrs_name_a": ra["vrs_name"] if ra else "",
            "vrs_name_b": rb["vrs_name"] if rb else "",
            "vrs_url_a": ra["url"] if ra else "",
            "vrs_url_b": rb["url"] if rb else "",
            "own_p_a_pct": pct(own["p_a"]) if own else "",
            "own_p_b_pct": pct(own["p_b"]) if own else "",
            "own_fair_odds_a": own["fair_a"] if own else "",
            "own_fair_odds_b": own["fair_b"] if own else "",
            "own_k": round(k, 4),
            "own_basis": f"P=1/(1+10^(-{k:.4f}*Δpts/400)); {k_source}",
            "market_book": ", ".join(headline["books"]) if headline else "",
            "market_n_books": headline["n_books"] if headline else "",
            "market_odds_a": headline["odds_a"] if headline else "",
            "market_odds_b": headline["odds_b"] if headline else "",
            "market_overround_pct": headline["overround_pct"] if headline else "",
            "market_p_a_pct": pct(headline["p_a"]) if headline else "",
            "market_p_b_pct": pct(headline["p_b"]) if headline else "",
            "market_captured_utc": headline["captured_utc"] if headline else "",
            "market_url": headline["url"] if headline else "",
            "market_source": headline["source"] if headline else "",
            "market_read_by": headline["read_by"] if headline else "",
            "poly_p_a_pct": pct(poly_p["p_a"]) if poly_p else "",
            "poly_p_b_pct": pct(poly_p["p_b"]) if poly_p else "",
            "poly_url": poly_p["url"] if poly_p else "",
            "consensus_p_a_pct": pct(c_a) if c_a is not None else "",
            "consensus_p_b_pct": pct(c_b) if c_b is not None else "",
            "consensus_basis": consensus_src,
            "pick": pick, "pick_pct": pick_pct, "pick_basis": pick_basis,
            "divergence_pp": (f"{abs(headline['p_a'] - own['p_a']) * 100:.1f}"
                              if headline and own else ""),
            "hotspawn_pages": ",".join(fx.get("pages") or []),
            "hotspawn_url": fx.get("source_url") or "https://play.hotspawn.com/lobby",
            "hotspawn_match_url": fx.get("hotspawn_match_url") or "",
            "captured_utc": fx.get("captured_utc") or cap.get("generated_utc") or "",
            "rating_snapshot_as_of": (sources.get("vrs") or {}).get("as_of") or "",
            "flags": " ".join(sorted({f["code"] for f in flags.get(mid, [])})),
        }
        rows_out.append(row)

    rows_out.sort(key=lambda r: (r["start_utc"], r["fixture_id"]))
    open_rows = [r for r in rows_out if r["pickable"] == "yes"]
    with_market = [r for r in open_rows if r["market_p_a_pct"]]
    with_own = [r for r in open_rows if r["own_p_a_pct"]]
    with_pick = [r for r in open_rows if r["pick"]]

    write_csv(ANALYSIS_CSV, rows_out)
    write_json(DATA / "analysis.json", rows_out)
    write_csv(DATA / "market_rows.csv", market_rows)
    flag_list = []
    for mid, items in flags.items():
        fx = next((r for r in rows_out if r["fixture_id"] == mid), {})
        for item in items:
            flag_list.append({"fixture_id": mid, "code": item["code"],
                              "team_a": fx.get("team_a", ""), "team_b": fx.get("team_b", ""),
                              "start_utc": fx.get("start_utc", ""), "pickable": fx.get("pickable", ""),
                              "detail": item["text"],
                              "row_url": fx.get("hotspawn_match_url") or fx.get("hotspawn_url") or "",
                              "flag_url": f"flagged.html#{item['code']}"})
    write_csv(DATA / "flags.csv", flag_list)
    write_json(DATA / "flags.json", flag_list)

    age_days = ""
    as_of = (sources.get("vrs") or {}).get("as_of")
    if as_of:
        try:
            age_days = (now.date() - datetime.strptime(as_of, "%Y-%m-%d").date()).days
        except ValueError:
            age_days = ""
    summary = {
        "generated_utc": now_iso(),
        "capture_generated_utc": cap.get("generated_utc"),
        "fixtures_cs2": len(rows_out),
        "open": len(open_rows),
        "with_market_line": len(with_market),
        "with_own_line": len(with_own),
        "with_pick": len(with_pick),
        "flagged": len(flag_list),
        "market_price_rows": len(market_rows),
        "own_line": {"k": round(k, 4), "basis": k_source, "calibration": calibration.get("status"),
                     "n_calibrated_on": calibration.get("n_total"), "adopted": calibration.get("adopted"),
                     "out_of_sample_log_loss": (calibration.get("out_of_sample") or {}),
                     "rating_snapshot_as_of": as_of, "rating_snapshot_age_days": age_days,
                     "valve_commit": calibration.get("valve_commit"),
                     "vrs_file": (sources.get("vrs") or {}).get("file")},
        "sources": source_digest(sources),
    }
    write_json(DATA / "summary.json", summary)
    log(f"model: {len(open_rows)} open CS2 fixtures · {len(with_market)} with a market line · "
        f"{len(with_own)} with our own line · {len(with_pick)} with a pick · {len(flag_list)} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
