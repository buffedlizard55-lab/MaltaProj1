#!/usr/bin/env python3
"""Session arena/b44b5d5e — every-match picks board builder.

Input : ``matchpicks/data/snapshot.json`` (written by ``matchpicks/collect_full.py``)
Output: ``matchpicks/data/*.csv``, ``matchpicks/data/summary.json`` and the four pages
        ``matchpicks/{index,unresolved,flagged,methodology}.html``

The board answers one question for **every** Counter-Strike 2 fixture Hotspawn lists:
which team to pick and how likely each team is to win, with the source of that number
printed on the row.

Rules that are enforced in code, not in prose
---------------------------------------------
* Hotspawn is the fixture authority (who plays whom, when, which tier, the offered points
  and the published score of a finished fixture).  Its crowd pick percentages are dropped
  at ingest by the collector and the build fails if one is read from the snapshot.
* A published probability must come from an outside source, in this order:
    1. an exact-match bookmaker moneyline (Pinnacle primary, EGamersWorld aggregate second),
       de-vigged;
    2. an exact-match prediction market (Polymarket), labelled as such and never de-vigged;
    3. our own line originated from **official** inputs — Valve's Regional Standings points
       (scale 400) or, when those are missing, the official HLTV world ranking;
    4. otherwise blank, and the row is published on the Unresolved page with its limitation.
* A fixture whose identity cannot be confirmed (participants not published by Hotspawn yet,
  or an outside quote that fails the name/start-time check) gets no probability.
* Every row on every page carries at least one source link and the UTC time it was read,
  or it is listed on the Unresolved page.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import math
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# Reuse the repository's already-verified rules instead of writing second versions of them:
#  * live/build.py    — name normalisation + documented alias table, de-vig, quote joining with a
#                       start-time tolerance, placeholder-pair rejection, VRS index/tie-break.
#  * executive/ownlines.py — the exact best-of series transform and the rank logistic scale.
live_build = _load_module("live_build_459ff624", ROOT / "live" / "build.py")
ownlines = _load_module("ownlines_1b6ae823", ROOT / "executive" / "ownlines.py")

norm = live_build.norm
parse_iso = live_build.parse_iso
devig = live_build.devig
pct = live_build.pct
vrs_index = live_build.vrs_index
pick_vrs = live_build.pick_vrs
ALIAS_SOURCES = live_build.ALIAS_SOURCES
START_TOLERANCE_MIN = live_build.START_TOLERANCE_MIN
PLACEHOLDER_PAIRS = {tuple(sorted(pair)) for pair in live_build.PLACEHOLDER_PAIRS}

VRS_SCALE = 400.0            # official VRS convention used by executive/ownlines.py
RANK_SCALE = ownlines.DEFAULT_RANK_SCALE   # HLTV rank positions per 90% per-map favourite
STALE_AFTER_DAYS = 3         # a listing whose start is days past is a stale listing, not a fixture
FULLPICKS_RESULTS = ROOT / "fullpicks" / "data" / "stale_results.csv"
SERIES_RESEARCH = ROOT / "matchpicks" / "series_research.csv"   # hand-checked, source-linked
                                                                # best-of lengths (see reviews/)

SOURCES_TABLE = [
    ("Hotspawn Pick'em lobby", "https://play.hotspawn.com/lobby",
     "fixture identity, tier, offered points, exact UTC start/lock epochs, published score"),
    ("Hotspawn CS2 Pick'ems", "https://play.hotspawn.com/cs2-pickems", "same payload, CS2 tab"),
    ("Hotspawn Thunderpick Pick'ems", "https://play.hotspawn.com/thp-pickems",
     "same payload, Thunderpick tab (carries the Tier-S fixtures)"),
    ("Valve Regional Standings", "https://github.com/ValveSoftware/counter-strike_regional_standings",
     "official team rating points for the originated line"),
    ("Pinnacle (public guest response)", "https://www.pinnacle.com/en/esports/matchups/highlights/",
     "primary bookmaker moneyline"),
    ("EGamersWorld", "https://egamersworld.com/counterstrike/matches",
     "aggregated bookmaker prices for the low-tier fixtures the primary book does not list"),
    ("Polymarket", "https://polymarket.com/", "prediction-market price, labelled and never de-vigged"),
    ("HLTV world ranking", "https://www.hltv.org/ranking/teams",
     "official rank number used only when the VRS pair is missing"),
]


# --------------------------------------------------------------------------- helpers
def is_cs2(fixture: dict) -> bool:
    sport = (fixture.get("sport") or "").lower()
    if sport:
        return sport in ("cs2", "counter-strike", "counterstrike")
    return True


def format_lookup(snapshot: dict) -> dict:
    """Official HLTV match-list reads, keyed by the unordered pair of normalised team names."""
    table: dict[tuple[str, str], dict] = {}
    for row in (snapshot.get("hltv_formats") or {}).get("matches") or []:
        key = tuple(sorted([norm(row.get("team_a") or ""), norm(row.get("team_b") or "")]))
        if all(key):
            table[key] = row
    return table


def series_length(fixture: dict) -> int | None:
    """Best-of length as stated by Hotspawn, or None when the payload does not state one.

    Observed 2026-10-15: Hotspawn leaves ``best_of``/``series_format`` null for every fixture, so in
    practice the length comes from :func:`series_info` (the official HLTV match list) instead."""
    for key in ("best_of", "series_format"):
        value = fixture.get(key)
        if value in (None, ""):
            continue
        bo = ownlines.format_to_best_of(value)
        if bo:
            return bo
        digits = re.findall(r"\d+", str(value))
        if digits:
            bo = ownlines.format_to_best_of(digits[0])
            if bo:
                return bo
    stage = (fixture.get("stage") or "")
    match = re.search(r"\b(?:bo|best of)\s*([1357])\b", stage, re.I)
    if match:
        return int(match.group(1))
    return None


def logistic(diff: float, scale: float) -> float:
    """p = 1 / (1 + 10^(-diff/scale)) — the logistic both official inputs are interpreted with."""
    return 1.0 / (1.0 + 10.0 ** (-float(diff) / float(scale)))


HLTV_ID_ONLY = re.compile(r"^https://www\.hltv\.org/matches/(\d+)/?$")


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", (value or "").lower())).strip("-")


def repair_source_url(url: str, team_a: str = "", team_b: str = "") -> tuple[str, bool]:
    """Make an id-only HLTV match link resolve.

    The repository's result trail stores links such as ``https://www.hltv.org/matches/2395365``.
    HLTV answers that form with HTTP 404 ("Page not found"), but serves the canonical page for any
    slug segment (verified by this session on 2026-10-15: ``/matches/2395365/x`` and
    ``/matches/2395497/<wrong-event-slug>`` both returned the correct match page).  Rather than
    publish a dead link, the board appends a slug built from the two team names; the repaired link is
    flagged so the repair is visible.
    """
    match = HLTV_ID_ONLY.match((url or "").strip())
    if not match:
        return url, False
    slug = "-vs-".join(part for part in (slugify(team_a), slugify(team_b)) if part) or "match"
    return f"https://www.hltv.org/matches/{match.group(1)}/{slug}", True


def load_series_research() -> dict:
    """Source-linked best-of lengths read by hand for the fixtures the automated runner cannot source.

    The runner's fetch of HLTV's live match list is refused by that site's bot protection (recorded
    per capture), and Hotspawn's own payload states no length, so for those fixtures the length is
    taken from a named official page that was read by hand and is linked on the row.  Only rows that
    carry a real URL and a best-of value are used; nothing is inferred.
    """
    table: dict[str, dict] = {}
    if not SERIES_RESEARCH.exists():
        return table
    with SERIES_RESEARCH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            bo = (row.get("series") or "").strip().upper()
            if not (row.get("match_id") and row.get("source_url") and bo[:2] == "BO" and bo[2:].isdigit()):
                continue
            table[str(row["match_id"]).strip()] = {
                "bo": int(bo[2:]), "source": (row.get("source") or "").strip(),
                "url": row["source_url"].strip(), "evidence": (row.get("evidence") or "").strip(),
                "read_utc": (row.get("read_utc") or "").strip()}
    return table


def series_info(fixture: dict, formats: dict, research: dict, trail_row: dict | None) -> dict:
    """The series length and the source it came from — never guessed.

    Order of sources, all of them named and linked on the row:
      1. what Hotspawn's payload states (in practice never);
      2. the official HLTV match list captured by this run, joined on the team pair with the label
         and the start time on the same row (MP-F11);
      3. the hand-checked research trail of official HLTV match/event pages (MP-F33);
      4. the official match page already linked by the repository's verified result trail (MP-F33).
    A fixture whose length no source states keeps an empty length and is flagged MP-F05.
    """
    stated = series_length(fixture)
    if stated:
        return {"bo": stated, "source": "Hotspawn payload", "url": fixture.get("source_url") or "",
                "evidence": "", "read_utc": fixture.get("snapshot_utc") or ""}
    key = tuple(sorted([norm(fixture.get("team_a") or ""), norm(fixture.get("team_b") or "")]))
    row = formats.get(key)
    if row and row.get("best_of"):
        meta = (fixture.get("_formats_meta") or {})
        return {"bo": int(row["best_of"]), "source": "official HLTV match list",
                "url": meta.get("url") or "https://www.hltv.org/matches",
                "evidence": row.get("evidence") or "", "read_utc": meta.get("read_utc") or ""}
    entry = research.get(str(fixture.get("match_id") or "").strip())
    if entry:
        return {"bo": entry["bo"], "source": entry["source"], "url": entry["url"],
                "evidence": entry["evidence"], "read_utc": entry["read_utc"]}
    if trail_row:
        bo = ownlines.format_to_best_of(trail_row.get("series_format") or "") or \
             (int(re.findall(r"\d+", trail_row["series_format"])[0])
              if re.findall(r"\d+", trail_row.get("series_format") or "") else None)
        if bo and trail_row.get("official_source_url"):
            return {"bo": bo, "source": "official match page (verified result trail)",
                    "url": trail_row["official_source_url"], "evidence": "best-of recorded with the "
                    "verified result on the same official match page", "read_utc": trail_row.get("read_utc") or ""}
    return {"bo": None, "source": "", "url": "", "evidence": "", "read_utc": ""}


def own_line(fixture: dict, vrs: dict, hltv_ranks: dict, formats: dict,
             research: dict, trail_row: dict | None) -> dict:
    """Originated probability from official inputs only, or a reason why it cannot be made.

    Tier A: both teams present in Valve's official Regional Standings → points ratio, scale 400.
    Tier B: otherwise, both teams present in the official HLTV world ranking → rank logistic.
    The per-map figure is converted to the stated series length when Hotspawn states one.
    """
    series = series_info(fixture, formats, research, trail_row)
    bo = series["bo"]
    a, b = fixture.get("team_a"), fixture.get("team_b")
    entry_a, alt_a = pick_vrs(vrs.get(norm(a or "")))
    entry_b, alt_b = pick_vrs(vrs.get(norm(b or "")))
    out = {"bo": bo, "series_source": series["source"], "series_url": series["url"],
           "series_evidence": series["evidence"], "series_read_utc": series["read_utc"],
           "vrs_a": entry_a, "vrs_b": entry_b, "vrs_alt_a": alt_a, "vrs_alt_b": alt_b,
           "basis": "", "p_map_a": None, "p_series_a": None, "missing": []}
    if entry_a and entry_b:
        p_map = logistic(entry_a["points"] - entry_b["points"], VRS_SCALE)
        out.update(basis="Valve Regional Standings points (official), scale 400", p_map_a=p_map)
    else:
        rank_a = hltv_ranks.get((a or "").lower())
        rank_b = hltv_ranks.get((b or "").lower())
        out["hltv_a"], out["hltv_b"] = rank_a, rank_b
        if rank_a and rank_b:
            p_map = logistic(float(rank_b) - float(rank_a), RANK_SCALE)
            out.update(basis="HLTV world ranking (official), rank logistic, scale "
                             f"{int(RANK_SCALE)}", p_map_a=p_map, via_rank=True)
        else:
            out["missing"] = [name for name, entry in ((a, entry_a), (b, entry_b),
                                                       (a if rank_a else f"{a} (HLTV)", rank_a),
                                                       (b if rank_b else f"{b} (HLTV)", rank_b))
                              if not entry]
    if out["p_map_a"] is not None:
        if bo:
            out["p_series_a"] = ownlines.series_probability(out["p_map_a"], bo)
        out["published_a"] = out["p_series_a"] if bo else out["p_map_a"]
    return out


def quote_is_usable(quote: dict, fixture: dict) -> tuple[bool, float | None, str]:
    """Join an outside quote to a fixture: normalised name pair + start-time tolerance."""
    if not quote.get("odds_a") or not quote.get("odds_b"):
        return False, None, "quote carries no two-sided price"
    if {norm(quote["team_a"]), norm(quote["team_b"])} != {norm(fixture["team_a"]), norm(fixture["team_b"])}:
        return False, None, "names do not join to this fixture"
    start = parse_iso(fixture.get("start_utc"))
    quote_start = parse_iso(quote.get("start_utc"))
    delta = None
    if quote_start and start:
        delta = abs((quote_start - start).total_seconds()) / 60.0
        if delta > START_TOLERANCE_MIN:
            return False, delta, f"start time differs by {delta:.0f} min"
    elif quote.get("kind") == "prediction_market":
        return False, None, "prediction market without a start time cannot be joined"
    if tuple(sorted([quote["odds_a"], quote["odds_b"]])) in PLACEHOLDER_PAIRS:
        return False, delta, "aggregator placeholder pair (identical prices)"
    return True, delta, ""


def external_quotes(snapshot: dict) -> list[dict]:
    quotes = []
    for quote in snapshot.get("pinnacle", {}).get("quotes", []):
        quotes.append({**quote, "source_label": "Pinnacle (direct bookmaker)", "rank": 0})
    for row in snapshot.get("egw", {}).get("detail", []):
        prices = row.get("prices") or []
        if len(prices) != 2:
            continue
        quotes.append({"bookmaker": "EGamersWorld",
                       "source_label": "EGamersWorld (aggregated bookmaker prices)", "rank": 1,
                       "market": "match_winner", "team_a": row["team_a"], "team_b": row["team_b"],
                       "start_utc": None, "odds_a": prices[0], "odds_b": prices[1],
                       "observed_utc": snapshot.get("generated_utc"),
                       "source_url": row["url"],
                       "note": "Two-way decimal pair read from the public match page."})
    for quote in snapshot.get("polymarket", {}).get("quotes", []):
        quotes.append({"bookmaker": "Polymarket",
                       "source_label": "Polymarket (prediction market, not a bookmaker)", "rank": 2,
                       "kind": "prediction_market", "market": "match_winner",
                       "team_a": quote["team_a"], "team_b": quote["team_b"],
                       "start_utc": quote.get("start_utc"),
                       "odds_a": quote["odds_a"], "odds_b": quote["odds_b"],
                       "observed_utc": quote.get("observed_utc"),
                       "source_url": quote.get("source_url"),
                       "volume_usd": quote.get("volume_usd"),
                       "note": "Prediction-market price converted to an implied probability; "
                               "not a bookmaker price and not de-vigged."})
    return quotes


def load_published_results() -> dict[str, dict]:
    """Earlier sessions' independently verified results, used only to cross-check scores."""
    table: dict[str, dict] = {}
    if not FULLPICKS_RESULTS.exists():
        return table
    with FULLPICKS_RESULTS.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("match_id"):
                table[row["match_id"].strip()] = row
    return table


FINISHED_STATUSES = {"finished", "completed", "closed", "ended"}


def hotspawn_score(fixture: dict) -> str:
    """The score **only** when the payload really publishes one.

    Observed 2026-10-15: Hotspawn's payload carries ``participants0_score``/``participants1_score``
    as ``0`` for every fixture, including June fixtures that are long over, and keeps
    ``status = "scheduled"``.  A placeholder therefore has to be rejected explicitly: a score is
    published here only when the payload calls the fixture finished *and* the two sides differ and at
    least one is non-zero.  Anything else is "not published", never "0-0".
    """
    status = (fixture.get("status") or "").strip().lower()
    a, b = fixture.get("team_a_score"), fixture.get("team_b_score")
    if status not in FINISHED_STATUSES:
        return ""
    try:
        a_int, b_int = int(a), int(b)
    except (TypeError, ValueError):
        return ""
    if a_int == b_int or (a_int == 0 and b_int == 0):
        return ""
    return f"{a_int}-{b_int}"


# --------------------------------------------------------------------------- build
def build(snapshot: dict) -> dict:
    now = parse_iso(snapshot["generated_utc"])
    vrs = vrs_index(snapshot)
    hltv_ranks = {k.lower(): v for k, v in (snapshot.get("hltv", {}).get("ranks") or {}).items()}
    vrs_url = snapshot.get("vrs", {}).get("url")
    vrs_as_of = snapshot.get("vrs", {}).get("as_of")
    hltv_url = snapshot.get("hltv", {}).get("url")
    hltv_read = snapshot.get("hltv", {}).get("fetched_utc")
    quotes = external_quotes(snapshot)
    formats = format_lookup(snapshot)
    series_research = load_series_research()
    formats_meta = {"url": (snapshot.get("hltv_formats") or {}).get("url") or "",
                    "read_utc": (snapshot.get("hltv_formats") or {}).get("read_utc") or ""}
    published = load_published_results()
    complete = snapshot.get("fixtures_complete") or snapshot.get("fixtures") or []
    incomplete = snapshot.get("fixtures_incomplete") or []

    rows, unresolved, flags = [], [], []
    for fixture in complete:
        if not is_cs2(fixture):
            continue
        start, lock = parse_iso(fixture.get("start_utc")), parse_iso(fixture.get("lock_utc"))
        open_now = bool(lock and now and lock > now)
        days_past = (now - start).days if (start and now) else 0
        stale = bool(start and now and days_past >= STALE_AFTER_DAYS)

        row = {
            "match_id": fixture["match_id"],
            "state": "open" if open_now else ("stale listing" if stale else "locked"),
            "lock_utc": fixture.get("lock_utc") or "",
            "start_utc": fixture.get("start_utc") or "",
            "competition": fixture.get("competition") or "",
            "tier": (fixture.get("tier") or "").upper(),
            "stage": fixture.get("stage") or "",
            "points": fixture.get("points") or "",
            "team_a": fixture.get("team_a") or "",
            "team_b": fixture.get("team_b") or "",
            "series": "",
            "hotspawn_url": fixture.get("hotspawn_match_url") or fixture.get("source_url") or "",
            "hotspawn_page": fixture.get("source_url") or "",
            "hotspawn_status": fixture.get("status") or "",
            "hotspawn_read_utc": snapshot.get("generated_utc"),
            "score": hotspawn_score(fixture),
            "aliases": "", "flags": "",
        }
        row_flags = []

        # ---- 1/2. outside market or prediction market
        candidates = []
        for quote in quotes:
            ok, delta, why = quote_is_usable(quote, fixture)
            if ok:
                candidates.append((quote, delta))
        candidates.sort(key=lambda item: (item[0]["rank"], item[1] if item[1] is not None else 1e9))
        if len(candidates) > 1 and candidates[0][1] is not None and candidates[1][1] is not None \
                and abs(candidates[0][1] - candidates[1][1]) < 1:
            row_flags.append("MP-F03")
        if candidates:
            quote = candidates[0][0]
            same_order = norm(quote["team_a"]) == norm(row["team_a"])
            odds_a = quote["odds_a"] if same_order else quote["odds_b"]
            odds_b = quote["odds_b"] if same_order else quote["odds_a"]
            if quote.get("kind") == "prediction_market":
                implied_a = round(100.0 / float(odds_a), 1)
                implied_b = round(100.0 / float(odds_b), 1)
                total = implied_a + implied_b
                p_a, p_b, over = implied_a, implied_b, round(total - 100.0, 1)
                row_flags.append("MP-F25")
            else:
                p_a, p_b, over = devig(float(odds_a), float(odds_b))
            row.update(market_source=quote["source_label"], market_book=quote["bookmaker"],
                       market_odds_a=f"{float(odds_a):.3f}", market_odds_b=f"{float(odds_b):.3f}",
                       market_overround_pct=pct(over), market_p_a_pct=pct(p_a), market_p_b_pct=pct(p_b),
                       market_url=quote.get("source_url") or "",
                       market_observed_utc=quote.get("observed_utc") or "")
            # Document when a source's spelling had to be normalised to join the fixture, so a
            # name-based join is never silent (the alias table itself is printed on the method page).
            variants = []
            for source_name, fixture_name in ((quote["team_a"], row["team_a"]),
                                              (quote["team_b"], row["team_b"])):
                if (source_name or "").strip().lower() != (fixture_name or "").strip().lower():
                    variants.append(f"{source_name} → {fixture_name}")
            if variants:
                row["aliases"] = "; ".join(variants)
                row_flags.append("MP-F10")
        else:
            row_flags.append("MP-F01")
            row.update(market_source="", market_book="", market_odds_a="", market_odds_b="",
                       market_overround_pct="", market_p_a_pct="", market_p_b_pct="",
                       market_url="", market_observed_utc="")

        # ---- 3. our own originated line from official inputs
        fixture["_formats_meta"] = formats_meta
        trail = published.get(row["match_id"])
        own = own_line(fixture, vrs, hltv_ranks, formats, series_research, trail)
        if own["bo"]:
            row["series"] = f"BO{own['bo']}"
            row["series_source"] = own["series_source"]
            repaired, was_repaired = repair_source_url(own["series_url"], row["team_a"], row["team_b"])
            row["series_url"] = repaired
            if was_repaired:
                row_flags.append("MP-F35")
            row["series_read_utc"] = own["series_read_utc"]
            row["series_evidence"] = own.get("series_evidence") or ""
            if own["series_source"] == "official HLTV match list":
                row_flags.append("MP-F11")
            elif own["series_source"] != "Hotspawn payload":
                row_flags.append("MP-F33")
        else:
            row["series_source"] = row["series_url"] = row["series_read_utc"] = ""
            row["series_evidence"] = ""
        row["own_basis"] = own["basis"]
        row["own_url"] = vrs_url if own.get("vrs_a") and own.get("vrs_b") else (hltv_url or "")
        row["own_read_utc"] = (vrs_as_of if own.get("vrs_a") and own.get("vrs_b") else hltv_read) or ""
        row["vrs_points_a"] = int(own["vrs_a"]["points"]) if own.get("vrs_a") else ""
        row["vrs_points_b"] = int(own["vrs_b"]["points"]) if own.get("vrs_b") else ""
        row["vrs_rank_a"] = own["vrs_a"]["vrs_rank"] if own.get("vrs_a") else ""
        row["vrs_rank_b"] = own["vrs_b"]["vrs_rank"] if own.get("vrs_b") else ""
        row["hltv_rank_a"] = hltv_ranks.get(row["team_a"].lower(), "")
        row["hltv_rank_b"] = hltv_ranks.get(row["team_b"].lower(), "")
        if own["p_map_a"] is not None:
            published_a = own["published_a"]
            row.update(own_p_a_pct=pct(round(100 * published_a, 1)),
                       own_p_b_pct=pct(round(100 * (1 - published_a), 1)),
                       own_scope="series" if own["bo"] else "per-map")
        else:
            row.update(own_p_a_pct="", own_p_b_pct="", own_scope="")
            row_flags.append("MP-F02")
            row["own_missing"] = ", ".join(own["missing"])
        # Every row whose series length no source states is flagged, whether or not an own line is
        # published on it — the length itself is never inferred from the score or the map count.
        if not own["bo"]:
            row_flags.append("MP-F05")
        if own.get("vrs_alt_a") or own.get("vrs_alt_b"):
            row_flags.append("MP-F26")

        # ---- 4. what we publish, and the pick
        if row.get("market_p_a_pct"):
            row.update(p_a=row["market_p_a_pct"], p_b=row["market_p_b_pct"],
                       probability_source=row["market_source"], pick_basis=row["market_source"])
        elif row.get("own_p_a_pct"):
            row.update(p_a=row["own_p_a_pct"], p_b=row["own_p_b_pct"],
                       probability_source=row["own_basis"],
                       pick_basis=row["own_basis"] + ("" if row["own_scope"] == "series"
                                                      else " — per-map; series length not stated"))
        else:
            row.update(p_a="", p_b="", probability_source="", pick_basis="")

        if row["p_a"]:
            a_pct, b_pct = float(row["p_a"]), float(row["p_b"])
            row["pick"] = row["team_a"] if a_pct >= b_pct else row["team_b"]
            row["pick_pct"] = f"{max(a_pct, b_pct):.1f}"
        else:
            row["pick"], row["pick_pct"] = "", ""

        # ---- divergence between the market and our own line (published, never averaged)
        if row.get("market_p_a_pct") and row.get("own_p_a_pct"):
            row["divergence_pp"] = f"{float(row['p_a']) - float(row['own_p_a_pct']):+.1f}"
            if abs(float(row["p_a"]) - float(row["own_p_a_pct"])) >= 12.5:
                row_flags.append("MP-F20")

        # ---- played fixtures: publish the result from the independent verification trail, and
        #      cross-check it against the payload's own score whenever the payload publishes one.
        if trail and (trail.get("status") or "").strip() == "verified" and trail.get("winner"):
            row["result"] = f"{trail['winner']} {trail.get('score') or ''}".strip()
            repaired, was_repaired = repair_source_url(trail.get("official_source_url") or "",
                                                       row["team_a"], row["team_b"])
            row["result_source_url"] = repaired
            if was_repaired:
                row_flags.append("MP-F35")
            row["result_read_utc"] = trail.get("read_utc") or ""
            row["result_note"] = ("carried from the repository's independently verified result "
                                  f"trail, which cites the official match page above and was read "
                                  f"{(trail.get('read_utc') or '').strip() or 'earlier'}; Hotspawn's "
                                  "payload publishes no usable score for this fixture (it keeps "
                                  "every fixture at 0-0 / \u201cscheduled\u201d), so the linked match "
                                  "page is the only source shown")
        elif trail and (trail.get("status") or "").strip():
            row["result"] = ""
            repaired, was_repaired = repair_source_url(trail.get("official_source_url") or "",
                                                       row["team_a"], row["team_b"])
            row["result_source_url"] = repaired
            if was_repaired:
                row_flags.append("MP-F35")
            row["result_read_utc"] = trail.get("read_utc") or ""
            row["result_note"] = f"trail status “{trail['status']}”: {(trail.get('flag') or '')[:220]}"
            row_flags.append("MP-F32")
        else:
            row["result"], row["result_source_url"], row["result_read_utc"] = "", "", ""
            row["result_note"] = "no independent result on file for this fixture"
        if row["score"]:
            if trail and trail.get("winner"):
                a_int, b_int = (int(x) for x in row["score"].split("-"))
                hotspawn_winner = row["team_a"] if a_int > b_int else row["team_b"]
                if norm(hotspawn_winner) == norm(trail["winner"]):
                    row["result_cross_check"] = f"payload score agrees with {trail['official_source_url']}"
                else:
                    row["result_cross_check"] = (f"DISAGREES: payload score says {hotspawn_winner}, "
                                                 f"{trail['official_source_url']} says {trail['winner']}")
                    row_flags.append("MP-F30")
            else:
                row["result_cross_check"] = "payload publishes a score but no independent result is on file"
                row_flags.append("MP-F31")
        else:
            row["result_cross_check"] = ""

        if stale:
            row_flags.append("MP-F04")
            # A stale listing is not a playable fixture: the absence of a market line, of an own line
            # or of a series length is inherent to it, so those flags would only add noise.
            row_flags = [f for f in row_flags if f in ("MP-F04", "MP-F06", "MP-F30", "MP-F31")]
        if not row["hotspawn_url"].startswith("http"):
            row_flags.append("MP-F06")
        if row["competition"].lower().startswith("thunderpick") and row["tier"] == "S":
            row_flags.append("MP-F07") if not row.get("market_p_a_pct") else None

        row["flags"] = ";".join(row_flags)
        rows.append(row)
        if not row["pick"]:
            unresolved.append(row)

    # participant-less payload nodes: published so a fixture can never vanish silently
    for fixture in incomplete:
        if not is_cs2(fixture):
            continue
        missing = fixture.get("missing_fields") or []
        labels = {"team_a": "team A name", "team_b": "team B name", "start_utc": "start time"}
        unresolved.append({
            "match_id": fixture["match_id"],
            "state": "identity incomplete",
            "lock_utc": fixture.get("lock_utc") or "",
            "start_utc": fixture.get("start_utc") or "",
            "competition": fixture.get("competition") or "",
            "tier": (fixture.get("tier") or "").upper(),
            "stage": fixture.get("stage") or "",
            "points": fixture.get("points") or "",
            "team_a": fixture.get("team_a") or "",
            "team_b": fixture.get("team_b") or "",
            "series": "", "hotspawn_url": fixture.get("source_url") or "",
            "hotspawn_page": fixture.get("source_url") or "",
            "hotspawn_status": fixture.get("status") or "",
            "hotspawn_read_utc": snapshot.get("generated_utc"),
            "score": "", "aliases": "", "flags": "MP-F08",
            "market_source": "", "market_book": "", "market_odds_a": "", "market_odds_b": "",
            "market_overround_pct": "", "market_p_a_pct": "", "market_p_b_pct": "",
            "market_url": "", "market_observed_utc": "", "own_basis": "", "own_url": "",
            "own_read_utc": "", "vrs_points_a": "", "vrs_points_b": "", "vrs_rank_a": "",
            "vrs_rank_b": "", "hltv_rank_a": "", "hltv_rank_b": "", "own_p_a_pct": "",
            "own_p_b_pct": "", "own_scope": "", "p_a": "", "p_b": "", "probability_source": "",
            "pick_basis": "", "pick": "", "pick_pct": "", "divergence_pp": "",
            "result_cross_check": "",
            "unresolved_reason": "Hotspawn has opened this fixture but has not published "
                                 + " and ".join(labels[m] for m in missing if m in labels)
                                 + " yet; no outside source can be joined to it and no pick is "
                                   "invented from an unpublished identity",
            "payload_keys": ", ".join(fixture.get("payload_keys") or []),
        })

    dom_only = snapshot.get("dom_only_ids") or []
    if dom_only:
        unresolved.append({
            "match_id": f"{len(dom_only)} id(s)", "state": "markup only",
            "competition": "rendered links on the Hotspawn pages",
            "flags": "MP-F09",
            "unresolved_reason": ("rendered link ids that have no fixture node in the TransferState "
                                 "payload; they are counted here instead of being published as "
                                 "fixtures. Ids: " + ", ".join(dom_only[:30])
                                 + (" …" if len(dom_only) > 30 else "")),
            "hotspawn_read_utc": snapshot.get("generated_utc"),
        })

    flags = collect_flags(rows, unresolved)
    source_health = {
        "pinnacle_quotes": len(snapshot.get("pinnacle", {}).get("quotes") or []),
        "pinnacle_status": snapshot.get("pinnacle", {}).get("status") or "unknown",
        "egw_status": snapshot.get("egw", {}).get("status") or "unknown",
        "egw_detail": len(snapshot.get("egw", {}).get("detail") or []),
        "egw_http": next((str(p.get("status")) for p in (snapshot.get("provenance") or [])
                          if "egamersworld" in (p.get("url") or "")), ""),
        "polymarket_quotes": len(snapshot.get("polymarket", {}).get("quotes") or []),
        "hltv_rank_rows": snapshot.get("hltv", {}).get("total_rows") or 0,
        "hltv_format_rows": len((snapshot.get("hltv_formats") or {}).get("matches") or []),
        "hotspawn_series_stated": sum(1 for r in rows if r.get("series_source") == "Hotspawn payload"),
    }
    summary = summarise(snapshot, rows, unresolved, flags)
    summary["flag_kinds_documented"] = len(FLAG_TEXT)
    summary["source_health"] = source_health
    return {"rows": rows, "unresolved": unresolved, "flags": flags, "summary": summary,
            "meta": {"source_health": source_health,
                     "generated_utc": snapshot["generated_utc"],
                     "week_text": snapshot.get("week_text") or "",
                     "reset_text": snapshot.get("reset_text") or "",
                     "pages": snapshot.get("hotspawn_pages") or [],
                     "vrs": {"url": vrs_url, "as_of": vrs_as_of,
                             "read_utc": snapshot.get("vrs", {}).get("fetched_utc")},
                     "hltv": {"url": hltv_url, "read_utc": hltv_read,
                              "rows": snapshot.get("hltv", {}).get("total_rows") or 0},
                     "crowd_fields_dropped": snapshot.get("crowd_fields_dropped") or 0,
                     "incomplete": len(incomplete),
                     "dom_only": len(snapshot.get("dom_only_ids") or [])}}


FLAG_TEXT = {
    "MP-F01": ("No outside market line joined", "No bookmaker or prediction-market quote could be "
               "joined to this fixture by name and start time. The pick therefore rests on our own "
               "originated line, or is withheld."),
    "MP-F02": ("No originated line", "Neither the official Valve Regional Standings pair nor the "
               "official HLTV ranking pair is complete for both teams, so no own line is published."),
    "MP-F03": ("Two quotes equally close", "Two outside quotes join this fixture with start times "
               "less than a minute apart; the higher-ranked source was used and the tie is disclosed."),
    "MP-F04": ("Stale listing", "The payload still lists the fixture but its start time is days in "
               "the past. It is published as a stale listing, not as a pickable match."),
    "MP-F05": ("Series length not stated", "Hotspawn does not state a best-of length for this "
               "fixture, so the own line is published per map and labelled as such."),
    "MP-F06": ("No public match page", "Hotspawn has no generated match page for this fixture yet "
               "(the page links to a waiting-for-information placeholder); the payload URL is used."),
    "MP-F07": ("Tier-S fixture without a market", "A Tier-S fixture with no joined outside line; "
               "check the market section before using the own line."),
    "MP-F08": ("Identity incomplete in the payload", "Hotspawn has opened the fixture but has not "
               "published both participant names and/or the start time. No pick can be produced "
               "without inventing an identity."),
    "MP-F11": ("Series length from the official HLTV match list", "Hotspawn's payload publishes no "
               "best-of length for any fixture (its fields are null), so the length that turns a "
               "per-map probability into a match probability is taken from the official HLTV match "
               "list, joined on the team pair with the label and start time on the same row. The "
               "matched text is kept as evidence."),
    "MP-F10": ("Name variant joined", "The source spells a team differently from the fixture (for "
               "example an abbreviation); the join used the repository's documented alias table and "
               "the fixture's start time, and both spellings are shown on the row."),
    "MP-F09": ("Markup-only fixture id", "The id is rendered on the page but is absent from the "
               "TransferState payload, so it cannot be confirmed."),
    "MP-F20": ("Market and own line diverge", "The joined outside line and our own originated line "
               "differ by 12.5 percentage points or more. The market line is published as the "
               "probability; the own line is shown next to it and never averaged in."),
    "MP-F25": ("Prediction market, not a bookmaker", "The published probability comes from a "
               "prediction market; it is not de-vigged and is not comparable to a bookmaker price."),
    "MP-F26": ("Duplicate roster entry", "Valve's standings list more than one entry for this team "
               "name; the higher-points entry is used (documented tie-break) and the other is listed."),
    "MP-F30": ("Result disagreement with the verification trail", "The score in the Hotspawn payload "
               "and the independently verified result on file disagree. Both are linked; neither is "
               "overwritten."),
    "MP-F31": ("Payload score without an independent check", "Hotspawn's payload publishes a score "
               "for this fixture but no independently verified result is on file yet to check it "
               "against. The payload score is shown only for finished fixtures and is never presented "
               "as verified."),
    "MP-F32": ("Result unverified", "The fixture is over but the repository's result trail records "
               "the outcome as unresolved (for example an event whose official page contradicts the "
               "listed card). No result is published rather than a guessed one."),
    "MP-F33": ("Series length from a researched official page", "The live capture could not read "
               "HLTV's match list for this fixture (the site's bot protection refuses the automated "
               "read, which is recorded in every capture), so the best-of length comes from a named "
               "official HLTV match or event page read by hand, quoted on the row and linked with "
               "its read time. Nothing is inferred from the score or the number of maps."),
    "MP-F35": ("Source link repaired so it resolves", "The link stored by the source trail was the "
               "id-only form (for example https://www.hltv.org/matches/2395365), which HLTV answers "
               "with HTTP 404; the board appends a slug built from the two team names, which HLTV "
               "serves as the canonical match page (verified by hand on the id-only links "
               "2395365 and 2395497 on 2026-10-15). The underlying claim is unchanged — only the link is."),
    "MP-F34": ("Capture gap closed by this board", "This fixture was missing from the other boards' "
               "captured inventories because the payload node had no participant names when they "
               "were read; it is listed here so it cannot disappear silently."),
}


def collect_flags(rows: list[dict], unresolved: list[dict]) -> dict[str, dict]:
    """Count each (fixture, flag) pair once — an unresolved row can be the same object as a
    board row (a stale listing with no pick), and double counting it would misreport the load."""
    seen: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for row in list(rows) + list(unresolved):
        for flag in (row.get("flags") or "").split(";"):
            if not flag:
                continue
            key = (str(row.get("match_id")), flag)
            if key in seen:
                continue
            seen.add(key)
            counts[flag] = counts.get(flag, 0) + 1
    table = {}
    for flag, count in sorted(counts.items()):
        title, detail = FLAG_TEXT.get(flag, ("Unclassified flag", ""))
        table[flag] = {"title": title, "detail": detail, "count": count}
    return table


def summarise(snapshot: dict, rows: list[dict], unresolved: list[dict], flags: dict) -> dict:
    open_rows = [r for r in rows if r["state"] == "open"]
    stale_rows = [r for r in rows if r["state"] == "stale listing"]
    locked_rows = [r for r in rows if r["state"] == "locked"]
    identity_rows = [r for r in unresolved if r.get("state") == "identity incomplete"]
    markup_rows = [r for r in unresolved if r.get("state") == "markup only"]
    return {
        "generated_utc": snapshot["generated_utc"],
        "fixtures_captured": len(rows),
        "open": len(open_rows),
        "locked": len(locked_rows),
        "stale": len(stale_rows),
        "open_with_pick": sum(1 for r in open_rows if r["pick"]),
        "open_market_basis": sum(1 for r in open_rows if r.get("market_p_a_pct") and r["pick"]),
        "open_own_line_basis": sum(1 for r in open_rows
                                   if not r.get("market_p_a_pct") and r.get("own_p_a_pct") and r["pick"]),
        "open_without_pick": sum(1 for r in open_rows if not r["pick"]),
        "open_without_any_probability": sum(1 for r in open_rows if not r["p_a"] and not r["own_p_a_pct"]),
        "open_with_market": sum(1 for r in open_rows if r.get("market_p_a_pct")),
        "open_with_own_line": sum(1 for r in open_rows if r.get("own_p_a_pct")),
        "identity_incomplete": len(identity_rows),
        "markup_only": len(dom_only) if (dom_only := snapshot.get("dom_only_ids") or []) else 0,
        "unresolved_total": len(unresolved),
        "flags_total": sum(v["count"] for v in flags.values()),
        "flag_kinds": len(flags),
        "crowd_fields_dropped": snapshot.get("crowd_fields_dropped") or 0,
        "results_verified_with_source": sum(1 for r in rows if r.get("result")),
        "results_unverified": sum(1 for r in rows if not r.get("result")
                                  and r["state"] == "stale listing"
                                  and (r.get("result_note") or "").startswith("trail status")),
        "independent_checks_agreed": sum(1 for r in rows if (r.get("result_cross_check") or "")
                                         .startswith("agrees")),
        "independent_checks_failed": sum(1 for r in rows if (r.get("result_cross_check") or "")
                                         .startswith("DISAGREES")),
    }


# --------------------------------------------------------------------------- output
COLUMNS = ["match_id", "state", "lock_utc", "start_utc", "competition", "tier", "stage", "points",
           "team_a", "team_b", "series", "series_source", "series_url", "series_read_utc", "series_evidence",
           "pick", "pick_pct", "p_a", "p_b", "probability_source",
           "pick_basis", "market_source", "market_book", "market_odds_a", "market_odds_b",
           "market_overround_pct", "market_p_a_pct", "market_p_b_pct", "market_url",
           "market_observed_utc", "own_p_a_pct", "own_p_b_pct", "own_basis", "own_scope", "own_url",
           "own_read_utc", "vrs_points_a", "vrs_points_b", "vrs_rank_a", "vrs_rank_b",
           "hltv_rank_a", "hltv_rank_b", "divergence_pp", "score", "result", "result_source_url",
           "result_read_utc", "result_note", "result_cross_check",
           "hotspawn_status", "hotspawn_url", "hotspawn_page", "hotspawn_read_utc", "flags"]


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def link(url: str, label: str) -> str:
    if not url:
        return ""
    return f'<a href="{escape(url, quote=True)}" rel="noopener noreferrer nofollow" target="_blank">{escape(label)}</a>'


def fmt_lock(row: dict) -> str:
    text = row.get("lock_utc") or row.get("start_utc") or ""
    return text.replace("T", " ").replace("Z", "Z")[:16] if text else "—"


def bar(row: dict) -> str:
    if not row.get("p_a"):
        return '<div class="bar empty"><span class="fill a" style="width:0"></span></div>'
    a = float(row["p_a"])
    return (f'<div class="bar" role="img" aria-label="{escape(row["team_a"])} {a:.1f}% '
            f'{escape(row["team_b"])} {100 - a:.1f}%">'
            f'<span class="fill a" style="width:{a:.1f}%">{a:.1f}%</span>'
            f'<span class="fill b" style="width:{100 - a:.1f}%">{100 - a:.1f}%</span></div>')


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {kind}">{escape(text)}</span>'


def fixture_card(row: dict) -> str:
    pick = row.get("pick")
    pick_line = (f'<strong class="pick">{escape(pick)}</strong> '
                 f'<span class="muted">at {escape(row.get("pick_pct") or "")}%</span>') if pick else \
        '<strong class="pick none">no pick published — see the Unresolved page</strong>'
    basis = row.get("probability_source") or ""
    badges = [badge(row.get("state", ""), "state")]
    if row.get("tier"):
        badges.append(badge(f"Tier {row['tier']}", "tier"))
    if row.get("series"):
        badges.append(badge(row["series"], "series"))
    if basis.startswith("Pinnacle"):
        badges.append(badge("bookmaker line", "market"))
    elif basis.startswith("EGamersWorld"):
        badges.append(badge("aggregated book line", "market"))
    elif basis.startswith("Polymarket"):
        badges.append(badge("prediction market", "poly"))
    elif basis:
        badges.append(badge("our own line", "own"))
    flags = [f for f in (row.get("flags") or "").split(";") if f]
    flag_line = ""
    if flags:
        flag_line = '<div class="flags">' + " ".join(
            f'<span class="badge flag">{escape(f)}</span>' for f in flags) + "</div>"
    sources = " ".join(filter(None, [
        link(row.get("market_url", ""), "market source"),
        link(row.get("own_url", ""), "official rating source"),
        link(row.get("hotspawn_url", ""), "Hotspawn fixture"),
    ]))
    detail_rows = [
        ("Competition", escape(row.get("competition") or "—")
         + (f' · {escape(row["stage"])}' if row.get("stage") else "")
         + (f' · {escape(str(row["points"]))} pts' if row.get("points") else "")),
        ("Lock (UTC)", escape(fmt_lock(row))),
        ("Series length", (escape(row.get("series") or "") + " — " + escape(row.get("series_source") or "")
                           + " " + link(row.get("series_url") or "", "source")
                           + (f' <span class="muted">read {escape((row.get("series_read_utc") or "")[:16])}Z</span>'
                              if row.get("series_read_utc") else ""))
         if row.get("series") else ('<em>not stated by any source read in this run — the own line is '
                                   'published per map (MP-F05)</em>'
                                   if "MP-F05" in flags else
                                   '<em>not stated by any source read in this run; no length is '
                                   'published rather than a guessed one</em>')),
        ("Probability source", escape(basis) if basis else '<em>none published</em>'),
        ("Own originated line", (f'{escape(row.get("own_p_a_pct"))}% / '
                                 f'{escape(row.get("own_p_b_pct"))}%'
                                 + (f' <span class="muted">({escape(row.get("own_scope"))})</span>'
                                    if row.get("own_scope") else "")
                                 ) if row.get("own_p_a_pct") else '<em>not available</em>'),
        ("Name variants from sources", escape(row.get("aliases") or "") or '<em>none — spellings matched exactly</em>'),
        ("Market price", (f'{escape(row.get("market_odds_a"))} / {escape(row.get("market_odds_b"))} · '
                          f'overround {escape(row.get("market_overround_pct"))}% · read '
                          f'{escape((row.get("market_observed_utc") or "")[:16])}Z')
         if row.get("market_odds_a") else '<em>none joined</em>'),
        ("Official ratings", (", ".join(filter(None, [
            f'VRS #{row["vrs_rank_a"]} {row["vrs_points_a"]} pts' if row.get("vrs_rank_a") else "",
            f'VRS #{row["vrs_rank_b"]} {row["vrs_points_b"]} pts' if row.get("vrs_rank_b") else "",
            f'HLTV #{row["hltv_rank_a"]} / #{row["hltv_rank_b"]}' if row.get("hltv_rank_a") else ""]))
            or '<em>not available</em>')),
        ("Market vs own line", escape(row.get("divergence_pp", "")) + " pp"
         if row.get("divergence_pp") else '<em>only one line available</em>'),
        ("Result (verified, with source)", (escape(row["result"]) + " — " + link(row["result_source_url"], "official match page")
                                            + f' <span class="muted">read {escape((row["result_read_utc"] or "")[:16])}Z</span>')
         if row.get("result") else f'<em>{escape(row.get("result_note") or "not published")}</em>'),
        ("Result (Hotspawn payload)", escape(row.get("score") or "")
         + ("" if row.get("score") else ' <span class="muted">— the payload publishes 0-0 placeholders for '
            'every fixture and keeps status “scheduled”, so no score is used from it</span>')),
        ("Payload vs trail", escape(row.get("result_cross_check") or "") or '<em>no payload score to compare</em>'),
        ("Sources", sources or '<em>none</em>'),
    ]
    details = "".join(f"<tr><th>{escape(name)}</th><td>{value}</td></tr>" for name, value in detail_rows)
    return f"""
<article class="card" data-state="{escape(row.get('state',''))}" data-tier="{escape(row.get('tier',''))}" id="m{escape(row['match_id'])}">
  <header>
    <div class="teams"><span class="team a">{escape(row['team_a'] or '?')}</span>
      <span class="vs">vs</span> <span class="team b">{escape(row['team_b'] or '?')}</span></div>
    <div class="badges">{''.join(badges)}</div>
  </header>
  <p class="pickline">Pick: {pick_line}</p>
  {bar(row)}
  <p class="baseline">{escape(basis) if basis else 'No probability published for this fixture.'}</p>
  {flag_line}
  <details><summary>Evidence &amp; sources</summary><table class="detail">{details}</table></details>
</article>"""


def page(title: str, body: str, active: str, summary: dict, meta: dict) -> str:
    nav = [("index.html", "Executive summary & picks"), ("all-fixtures.html", "Full inventory"),
           ("unresolved.html", "Unresolved picks"), ("flagged.html", "Flagged for review"),
           ("methodology.html", "Method & sources")]
    links = "".join(
        '<a href="{href}"{cls}>{label}</a>'.format(
            href=href, cls=' class="on"' if href == active else "", label=escape(label))
        for href, label in nav)
    age = ""
    generated = parse_iso(summary.get("generated_utc"))
    if generated:
        hours = (datetime.now(timezone.utc) - generated).total_seconds() / 3600
        age = f"{hours:.1f} h old"
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)}</title>
<meta name="description" content="Every Counter-Strike 2 fixture on the Hotspawn Pick'em board with a pick, a win probability from outside sources, and the source of every number.">
<link rel="stylesheet" href="style.css">
</head><body>
<header class="top"><div class="wrap">
  <a class="home" href="index.html">Hotspawn CS2 — every-match picks</a>
  <nav>{links}</nav>
  <p class="freshness">Board generated <time datetime="{escape(summary.get('generated_utc',''))}">{escape(summary.get('generated_utc',''))}</time>
  ({escape(age)}) · Hotspawn fixture read {escape(summary.get('generated_utc',''))} · refreshes every 4 hours automatically.</p>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap"><p>Hotspawn supplies fixture identity, times and the published score only. Its crowd
pick percentages are dropped at ingest and are never used as a probability. Every probability on this
board comes from an outside market or from our own line built on official rating files, and carries its
source link and read time. Values that could not be confirmed are left blank and listed on the
<a href="unresolved.html">Unresolved picks &amp; limitations</a> page.</p></footer>
</body></html>
"""


LADDER_TEXT = ("a de-vigged bookmaker line where one exists (Pinnacle first, then the EGamersWorld "
               "aggregate), a labelled prediction market next, and otherwise our own line built from "
               "Valve's official Regional Standings or the official HLTV ranking")


def render_index(rows: list[dict], unresolved: list[dict], flags: dict, summary: dict, meta: dict) -> str:
    open_rows = [r for r in rows if r["state"] == "open"]

    def group(rows_in: list[dict]) -> str:
        by_comp: dict[str, list[dict]] = {}
        for row in rows_in:
            by_comp.setdefault(row["competition"] or "(no competition in payload)", []).append(row)
        chunks = []
        for competition, items in sorted(by_comp.items()):
            picks = sum(1 for r in items if r["pick"])
            chunks.append(f'<h3 class="comp">{escape(competition)} '
                          f'<span class="muted">{picks}/{len(items)} with a pick</span></h3>')
            chunks.extend(fixture_card(r) for r in sorted(items, key=lambda r: (r["lock_utc"], r["match_id"])))
        return "".join(chunks)

    unresolved_open = [r for r in unresolved if r.get("state") == "open"]
    summary_html = f"""
<section class="cards" aria-label="Executive summary">
  <div class="stat"><span class="n">{summary['fixtures_captured']}</span><span class="l">CS2 fixtures captured from Hotspawn</span></div>
  <div class="stat"><span class="n">{summary['open']}</span><span class="l">still open at capture time</span></div>
  <div class="stat"><span class="n">{summary['open_with_pick']}/{summary['open']}</span><span class="l">open fixtures with a published pick</span></div>
  <div class="stat"><span class="n">{summary['open_market_basis']}</span><span class="l">open picks on an outside market line</span></div>
  <div class="stat"><span class="n">{summary['open_own_line_basis']}</span><span class="l">open picks on our own official-input line</span></div>
  <div class="stat warn"><span class="n">{summary['unresolved_total']}</span><span class="l">rows on the Unresolved page</span></div>
  <div class="stat"><span class="n">{summary['independent_checks_agreed']}</span><span class="l">fixtures where Hotspawn published a score at all (it publishes none: every fixture sits at 0-0 “scheduled”, so results are taken from the linked official match pages instead)</span></div>
  <div class="stat"><span class="n">{summary['crowd_fields_dropped']}</span><span class="l">Hotspawn crowd fields dropped at ingest</span></div>
</section>
<section class="notice" id="summary">
  <h2>Executive summary</h2>
  <p><strong>What this is.</strong> Every Counter-Strike 2 fixture Hotspawn's Pick'em board lists, with the
  team to pick and the probability of each team winning. Probabilities come from outside sources only:
  {LADDER_TEXT}
  Hotspawn is used for fixture identity, times and the published score — never for a probability.</p>
  <p><strong>Where the picks are:</strong> <a href="#open">Open fixtures (pick now)</a> ·
  <a href="#all">{summary['fixtures_captured']} captured fixtures incl. played &amp; stale listings</a> ·
  <a href="unresolved.html">Unresolved picks &amp; limitations ({summary['unresolved_total']})</a> ·
  <a href="flagged.html">Flagged for review ({summary['flags_total']} item(s))</a> ·
  <a href="methodology.html">Method &amp; sources</a></p>
  <p><strong>Limitations, stated up front.</strong> Two of the sources this ladder prefers refused the
  automated read during this capture — HLTV's upcoming-match list and the EGamersWorld aggregate both
  answer the runner with HTTP 403 (recorded in every capture), so the length of a series comes from a
  hand-checked, linked official HLTV page ({meta.get('source_health', {}).get('hltv_format_rows', 0)}
  row(s) joined live this time, the rest from the research trail), and rows that would have used an
  aggregate price are labelled as our own line instead. The own line is built on Valve's newest
  <em>published</em> standings file, so between publications a team's live rating may have moved.
  Hotspawn publishes no best-of length and no usable score at all — its <code>best_of</code> and
  <code>series_format</code> fields are null for every fixture and every fixture is stuck at 0-0
  “scheduled”, even ones from June. Everything that could not be confirmed stays blank and is flagged:
  <a href="unresolved.html">Unresolved picks &amp; limitations ({summary['unresolved_total']})</a> lists
  every row without a pick, with the reason, and <a href="flagged.html">Flagged for review
  ({summary['flags_total']} item(s))</a> lists every irregularity with the rows it touches.</p>
  <p><strong>Freshness.</strong> Captured {escape(summary['generated_utc'])}; Hotspawn reports
  “{escape(meta.get('week_text') or '')}” and a reset in {escape(meta.get('reset_text') or '')}. The board
  rebuilds automatically every 4 hours; the timestamp above is the time of the data on this page, not of
  your visit. Use the absolute UTC lock time on each row, not a relative countdown.</p>
</section>
<section id="open">
  <h2>Open fixtures — pick now ({len(open_rows)})</h2>
  <p class="muted">Locked by 6 minutes before the stated start; a fixture disappears from this section as
  soon as its lock time passes and moves to “Captured fixtures incl. played &amp; stale”.</p>
  {group(open_rows) if open_rows else '<p class="notice">No fixture is open at the capture time on this page. The next automatic refresh will pick up the new slate.</p>'}
  {'<p class="notice warn"><strong>Open fixtures without a published pick:</strong> ' + ", ".join(escape(r["match_id"]) for r in unresolved_open) + ' — see <a href="unresolved.html">Unresolved picks</a>.</p>' if unresolved_open else ''}
</section>
<section id="all">
  <h2>Complete Hotspawn inventory</h2>
  <p>{len(rows) - len(open_rows)} further fixtures are captured to keep this board equal to Hotspawn's own
  inventory: locked fixtures whose lock time has passed, and the stale listings Hotspawn never closes.
  They are on their own page so this one stays small on a phone.</p>
  <p><a class="button" href="all-fixtures.html">See all {len(rows)} captured fixtures →</a></p>
</section>
"""
    return page("Hotspawn CS2 — every-match picks", summary_html, "index.html", summary, meta)


def render_all_fixtures(rows: list[dict], unresolved: list[dict], summary: dict, meta: dict) -> str:
    other_rows = [r for r in rows if r["state"] != "open"]

    def group(rows_in: list[dict]) -> str:
        by_comp: dict[str, list[dict]] = {}
        for row in rows_in:
            by_comp.setdefault(row["competition"] or "(no competition in payload)", []).append(row)
        chunks = []
        for competition, items in sorted(by_comp.items()):
            picks = sum(1 for r in items if r["pick"])
            chunks.append(f'<h3 class="comp">{escape(competition)} '
                          f'<span class="muted">{picks}/{len(items)} with a pick</span></h3>')
            chunks.extend(fixture_card(r) for r in sorted(items, key=lambda r: (r["lock_utc"], r["match_id"])))
        return "".join(chunks)

    body = f"""
<section class="notice">
  <h2>Full inventory — every captured fixture ({len(rows)})</h2>
  <p>This page exists so the board can be checked against Hotspawn's own list. It carries the
  {len([r for r in rows if r['state'] == 'locked'])} fixture(s) whose lock time had passed at capture
  and the {len([r for r in rows if r['state'] == 'stale listing'])} stale listing(s) Hotspawn never
  closes. A finished fixture shows the score published in Hotspawn's payload and, where an independent
  verification trail exists, whether that score agrees with it.</p>
  <p class="muted">Open fixtures with a live pick are on the <a href="index.html">executive summary
  page</a>. Fixtures with no derivable pick are on the <a href="unresolved.html">Unresolved page</a>.</p>
</section>
{group(other_rows) if other_rows else '<p>No locked or stale fixture was captured.</p>'}
"""
    return page("Full inventory — Hotspawn CS2", body, "all-fixtures.html", summary, meta)


def render_unresolved(rows: list[dict], unresolved: list[dict], summary: dict, meta: dict) -> str:
    def table(items: list[dict]) -> str:
        if not items:
            return "<p>Nothing in this group.</p>"
        head = ("<tr><th>Fixture</th><th>Why there is no pick</th><th>What it would need</th>"
                "<th>Source / read time</th><th>Flags</th></tr>")
        body = []
        for row in items:
            name = f"{escape(row.get('team_a') or '?')} vs {escape(row.get('team_b') or '?')}"
            ident = escape(row.get("match_id", ""))
            why = escape(row.get("unresolved_reason") or "")
            if not why:
                needs = []
                if not row.get("market_p_a_pct"):
                    needs.append("no outside market line joined by name and start time")
                if not row.get("own_p_a_pct"):
                    needs.append("official rating pair incomplete"
                                 + (f" ({escape(row.get('own_missing') or '')})" if row.get("own_missing") else ""))
                why = "; ".join(needs) or "no probability could be derived"
            if row.get("state") == "stale listing":
                need = "nothing — Hotspawn keeps the fixture listed without a playable match; a pick would be a fabrication"
                if row.get("result"):
                    need += (f". Played: {escape(row['result'])} ("
                             + link(row["result_source_url"], "official match page") + ")")
                elif row.get("result_note"):
                    need += f". {escape(row['result_note'])}"
            elif row.get("state") == "identity incomplete":
                need = "Hotspawn publishing the participant names and start time; the next refresh then fills this row automatically"
            elif row.get("state") == "markup only":
                need = "the fixture appearing in the TransferState payload"
            else:
                need = ("an exact-match bookmaker or prediction-market price, or a complete official "
                        "rating pair (Valve Regional Standings or HLTV ranking)")
            source = " ".join(filter(None, [
                link(row.get("market_url", ""), "market"),
                link(row.get("own_url", ""), "rating file"),
                link(row.get("hotspawn_url", ""), "Hotspawn"),
            ])) or '<em>none</em>'
            read = escape((row.get("hotspawn_read_utc") or "")[:16])
            body.append(f"<tr><td><strong>{name}</strong><br><span class='muted'>{ident}"
                        + (f" · {escape(row.get('competition'))}" if row.get('competition') else "")
                        + (f" · lock {escape(fmt_lock(row))}" if row.get('lock_utc') else "")
                        + f"</span></td><td>{why}</td><td>{need}</td><td>{source}<br>"
                          f"<span class='muted'>read {read}</span></td>"
                          f"<td>{escape(row.get('flags') or '')}</td></tr>")
        return f"<table class='grid'>{head}{''.join(body)}</table>"

    groups = {
        "Identity not published by Hotspawn yet (no pick can exist)":
            [r for r in unresolved if r.get("state") == "identity incomplete"],
        "Open or upcoming fixture with no usable outside line and no complete official rating pair":
            [r for r in unresolved if r.get("state") in ("open", "locked", "identity incomplete")
             and r.get("state") != "identity incomplete"],
        "Stale listings Hotspawn never closes (no playable match)":
            [r for r in unresolved if r.get("state") == "stale listing"],
        "Page markup without a payload record":
            [r for r in unresolved if r.get("state") == "markup only"],
    }
    sections = []
    for title, items in groups.items():
        sections.append(f"<h3>{escape(title)} <span class='muted'>({len(items)})</span></h3>{table(items)}")
    body = f"""
<section class="notice warn" id="unresolved">
  <h2>Unresolved picks &amp; limitations</h2>
  <p>This page is the honest counterpart of the picks list. Every fixture on Hotspawn that this board
  cannot produce a pick for appears here with the exact reason, the limitation that caused it, what
  would resolve it, and the sources that were read. Nothing on this page is estimated: where a source
  could not be read or a fixture's identity is not published yet, the value stays blank.</p>
  <p><strong>Summary:</strong> {summary['fixtures_captured']} fixtures captured ·
  {summary['open']} open · {summary['open_with_pick']} of them with a pick ·
  {summary['unresolved_total']} row(s) unresolved ·
  {summary['identity_incomplete']} of those are fixtures Hotspawn has opened without participant names ·
  {summary['markup_only']} appear only in page markup.</p>
  <ul>
    <li><strong>Identity limitation.</strong> A fixture whose two participant names Hotspawn has not
      published cannot be joined to any source; publishing a pick for it would mean inventing teams.
      The board lists it and fills it in on the next automatic refresh (every 4 hours).</li>
    <li><strong>Market-coverage limitation.</strong> Low-tier fixtures (CCT, Elisa BreakOut, national
      leagues, qualifiers) are not priced by every book. When no bookmaker or prediction-market line
      joins, the pick rests on our own line from Valve's official Regional Standings or the official
      HLTV ranking — labelled as our own line, never presented as a market price.</li>
    <li><strong>Rating-coverage limitation.</strong> Teams outside both official lists (very low-tier
      orgs, academy and mix teams) have no rating pair, so no own line either. Those rows stay blank.</li>
    <li><strong>Stale-listing limitation.</strong> Hotspawn keeps fixtures from past events in the
      payload (June 2026 cards are still listed). They are not playable matches; a “pick” for them would
      be meaningless, so they are shown as stale listings.</li>
    <li><strong>Source-availability limitation.</strong> The ladder can only use a source it can read
      from the automated runner. In the capture behind this page the primary bookmaker
      (Pinnacle) returned {meta.get('source_health', {}).get('pinnacle_quotes', 0)} whole-match
      quote(s) and the prediction market {meta.get('source_health', {}).get('polymarket_quotes', 0)};
      the aggregator tier (EGamersWorld) returned
      {meta.get('source_health', {}).get('egw_detail', 0)} usable match page(s)
      (its status was “{escape(meta.get('source_health', {}).get('egw_status', 'unknown'))}”,
      HTTP {escape(meta.get('source_health', {}).get('egw_http', 'n/a'))} on
      2026-10-15 — it refuses automated reads). Rows that would have used an aggregator price are
      labelled as our own line instead, or stay unresolved.</li>
    <li><strong>Series-length limitation.</strong> Hotspawn's payload publishes no best-of length at
      all (its <code>best_of</code> and <code>series_format</code> fields are null for every fixture,
      observed 2026-10-15). Where the official HLTV match list states one, this board uses it and
      links the row ({meta.get('source_health', {}).get('hltv_format_rows', 0)} match(es) joined in
      the capture shown here); where no source states one, the own line is published per map and
      flagged MP-F05.</li>
    <li><strong>Rating-age limitation.</strong> The own line is built on the newest **officially
      published** Valve Regional Standings file ({escape(meta.get('vrs', {}).get('as_of') or '')}).
      Valve publishes that file periodically, so between publications a team's live rating may have
      moved (HLTV's live mirror page shows the in-between numbers). No un-official rating is used and
      no value is interpolated.</li>
    <li><strong>Freshness limitation.</strong> Numbers are as fresh as the read time printed on each row.
      A market can move after the read; re-read the linked source before acting.</li>
    <li><strong>Score limitation.</strong> Hotspawn's payload publishes no usable score at all — every
      fixture, including ones from June, sits at <code>0-0</code> with status “scheduled”, so a payload
      score is never published here. A finished fixture's result is taken from the repository's
      independently verified trail, which links the official match page (and the read time) on the row;
      if a payload score ever appears it is cross-checked against that trail and a disagreement is
      flagged, never silently resolved. Results that cannot be verified stay blank and flagged MP-F32;
      forfeit outcomes are labelled as defaults on the row.</li>
  </ul>
</section>
{''.join(sections)}
"""
    return page("Unresolved picks & limitations — Hotspawn CS2", body, "unresolved.html", summary, meta)


def render_flagged(rows: list[dict], unresolved: list[dict], flags: dict, summary: dict, meta: dict) -> str:
    def table(items: list[dict]) -> str:
        if not items:
            return "<p>No row carries this flag.</p>"
        body = []
        for row in items:
            name = f"{escape(row.get('team_a') or '?')} vs {escape(row.get('team_b') or '?')}"
            body.append(f"<tr><td>{name}<br><span class='muted'>{escape(row.get('match_id',''))}"
                        f"{' · ' + escape(row.get('competition')) if row.get('competition') else ''}</span></td>"
                        f"<td>{escape(row.get('state',''))}</td>"
                        f"<td>{escape(row.get('pick') or '—')}</td>"
                        f"<td>{escape(row.get('probability_source') or '—')}</td>"
                        f"<td>{escape(row.get('result_cross_check') or '—')}</td></tr>")
        return ("<table class='grid'><tr><th>Fixture</th><th>State</th><th>Pick</th>"
                "<th>Probability source</th><th>Cross-check</th></tr>" + "".join(body) + "</table>")

    blocks = []
    seen_rows: set[tuple] = set()
    unique: list[dict] = []
    for row in rows + unresolved:
        key = (row.get("match_id"), row.get("state"))
        if key in seen_rows:
            continue
        seen_rows.add(key)
        unique.append(row)
    for flag in sorted(set(FLAG_TEXT) | set(flags)):
        title, detail = FLAG_TEXT.get(flag, (flags.get(flag, {}).get("title", ""),
                                            flags.get(flag, {}).get("detail", "")))
        count = flags.get(flag, {}).get("count", 0)
        items = [r for r in unique if flag in (r.get("flags") or "").split(";")]
        blocks.append(f"<h3><code>{escape(flag)}</code> {escape(title)} "
                      f"<span class='muted'>({count} row(s) in this capture)</span></h3>"
                      f"<p class='muted'>{escape(detail)}</p>{table(items)}")
    body = f"""
<section class="notice warn">
  <h2>Flagged for review</h2>
  <p>Every irregularity this board found is published here with the rows it affects, so it can be
  reviewed after publication. Flags do not block the board; they mark where a reader should look before
  trusting a number. Flagged, unverified values are never filled in — they stay blank.</p>
  <p><strong>{summary['flags_total']}</strong> flagged item(s) across
  <strong>{summary['flag_kinds']}</strong> flag kind(s) raised in this capture. Every kind this board
  can raise is documented below (<strong>{summary.get('flag_kinds_documented', len(FLAG_TEXT))}</strong>
  in total), including the kinds that no row raised here — a documented check that finds nothing is
  still a check.</p>
</section>
{''.join(blocks)}
"""
    return page("Flagged for review — Hotspawn CS2", body, "flagged.html", summary, meta)


def render_methodology(rows: list[dict], summary: dict, meta: dict) -> str:
    sources = "".join(
        f"<tr><td>{link(url, name)}</td><td>{escape(what)}</td>"
        f"<td>{escape((read or '—')[:19])}</td></tr>"
        for (name, url, what), read in zip(
            SOURCES_TABLE,
            [summary.get("generated_utc")] * 3 + [meta.get("vrs", {}).get("read_utc"),
                                                   summary.get("generated_utc"), summary.get("generated_utc"),
                                                   summary.get("generated_utc"),
                                                   meta.get("hltv", {}).get("read_utc")]))
    body = f"""
<section class="notice">
  <h2>Method &amp; sources</h2>
  <p>This board exists to answer the brief's question for <em>every</em> Counter-Strike 2 fixture on
  Hotspawn, including the low-tier matches that bookmakers do not cover. It is built automatically:
  a GitHub Actions job reads the public pages, rebuilds the pages and the CSV data, and fails without
  publishing if any check does not hold.</p>

  <h3>How a probability is chosen (in this order)</h3>
  <ol>
    <li><strong>Bookmaker line</strong> — an exact-match whole-match moneyline from Pinnacle's public
      guest response (American prices converted to decimal), or from EGamersWorld's aggregated
      two-way decimal pair on the match page. De-vigged:
      <code>p_A = (1/odds_A) / (1/odds_A + 1/odds_B)</code>. The overround is printed on the row.</li>
    <li><strong>Prediction market</strong> — Polymarket, only when the market names both teams and a
      start time within {int(START_TOLERANCE_MIN)} minutes of the fixture. Published as the implied
      probability, labelled, never de-vigged and never averaged with a bookmaker price.</li>
    <li><strong>Our own line</strong> — originated from official rating files only:
      Valve Regional Standings points with the official 400-point logistic, or, when either team is
      missing there, the official HLTV world ranking with a rank logistic
      ({int(RANK_SCALE)} rank positions per 90% per-map favourite, the repository's documented default).
      The per-map figure is converted to the series length <em>only</em> when Hotspawn states one
      ({ownlines.BO_LABELS.get(3, 'BO3')} → {ownlines.series_probability(0.55, 3):.4f} at
      p<sub>map</sub>=0.55, for example); otherwise the row says “per-map” and is flagged MP-F05.</li>
    <li><strong>Blank.</strong> If none of the above is available, no probability and no pick are
      published; the row goes to the <a href="unresolved.html">Unresolved page</a>.</li>
  </ol>

  <h3>What Hotspawn is and is not used for</h3>
  <p>Used: fixture identity, competition, tier, stage, offered points, exact UTC start and lock epochs,
  and the score published for a finished fixture. <strong>Not used:</strong> the crowd pick percentages
  in the same payload. The collector drops every crowd field at ingest and this page reports how many
  were dropped ({summary['crowd_fields_dropped']} in the capture shown here); the build fails if a
  crowd value appears in the dataset.</p>

  <h3>Verification rules</h3>
  <ul>
    <li>Every published row carries a source link and the UTC time the source was read.</li>
    <li>If a value cannot be confirmed from an official or clearly-labelled source it is left blank and
      flagged — never inferred, never interpolated.</li>
    <li>A fixture the payload lists without participant names is published as an unresolved row rather
      than dropped, so a coverage gap can never be invisible.</li>
    <li>The score of a finished fixture is cross-checked against the repository's independently verified
      result trail (HLTV match pages read by an earlier session); a mismatch is flagged MP-F30 and both
      values are shown.</li>
    <li>Unit tests recompute every published probability from the stored inputs and compare it to the
      generated page, so a page can never disagree with its own data.</li>
  </ul>

  <h3>Refresh cadence</h3>
  <p>The workflow runs every 4 hours (and on demand). Each run re-reads Hotspawn, the rating files, the
  bookmaker sources and the prediction market; the data files and pages are regenerated together, so the
  timestamp on a row always belongs to the numbers next to it.</p>

  <h3>Sources used in this capture</h3>
  <table class="grid"><tr><th>Source</th><th>What it supplies</th><th>Read (UTC)</th></tr>{sources}</table>
  <p class="muted">Total fixtures captured: {summary['fixtures_captured']} · open at capture:
  {summary['open']} · with an outside market line: {summary['open_with_market']} ·
  with our own line: {summary['open_with_own_line']} · unresolved rows: {summary['unresolved_total']}.</p>
</section>
"""
    return page("Method & sources — Hotspawn CS2", body, "methodology.html", summary, meta)


def self_check(rows: list[dict], unresolved: list[dict], summary: dict) -> None:
    """Fail the build rather than publish something that breaks the rules."""
    problems = []
    if summary["fixtures_captured"] == 0:
        # A read that returns nothing must never replace a board that has content.
        problems.append("no CS2 fixture was captured — refusing to overwrite the published board")
    for row in rows:
        if row.get("p_a"):
            if not row.get("probability_source"):
                problems.append(f"{row['match_id']}: probability without a named source")
            if not (row.get("market_url") or row.get("own_url")):
                problems.append(f"{row['match_id']}: probability without a source link")
            if row.get("pick") not in (row.get("team_a"), row.get("team_b")):
                problems.append(f"{row['match_id']}: pick is not one of the two teams")
            try:
                if abs(float(row["p_a"]) + float(row["p_b"]) - 100.0) > 0.35:
                    problems.append(f"{row['match_id']}: probabilities do not sum to 100")
            except (TypeError, ValueError):
                problems.append(f"{row['match_id']}: non-numeric probability")
        if "crowd" in json.dumps(row).lower():
            problems.append(f"{row['match_id']}: a crowd field reached the dataset")
    for row in unresolved:
        if row.get("pick"):
            problems.append(f"{row['match_id']}: an unresolved row carries a pick")
    if summary["open_with_pick"] + summary["open_without_pick"] != summary["open"]:
        problems.append("open fixture accounting does not add up")
    if problems:
        raise SystemExit("SELF-CHECK FAILED:\n  - " + "\n  - ".join(problems))


CSV_FIELDS_UNRESOLVED = ["match_id", "state", "team_a", "team_b", "competition", "tier", "stage",
                         "lock_utc", "start_utc", "unresolved_reason", "payload_keys", "flags",
                         "hotspawn_page", "hotspawn_read_utc"]


def main() -> int:
    snapshot = json.loads((DATA / "snapshot.json").read_text())
    built = build(snapshot)
    rows, unresolved, flags, summary, meta = (built["rows"], built["unresolved"], built["flags"],
                                              built["summary"], built["meta"])
    self_check(rows, unresolved, summary)
    DATA.mkdir(parents=True, exist_ok=True)
    write_csv(DATA / "fixtures.csv", COLUMNS, rows)
    write_csv(DATA / "unresolved.csv", CSV_FIELDS_UNRESOLVED, unresolved)
    write_csv(DATA / "flags.csv", ["flag", "title", "detail", "count"],
              [{"flag": k, **v} for k, v in flags.items()])
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1))
    (HERE / "index.html").write_text(render_index(rows, unresolved, flags, summary, meta))
    (HERE / "all-fixtures.html").write_text(render_all_fixtures(rows, unresolved, summary, meta))
    (HERE / "unresolved.html").write_text(render_unresolved(rows, unresolved, summary, meta))
    (HERE / "flagged.html").write_text(render_flagged(rows, unresolved, flags, summary, meta))
    (HERE / "methodology.html").write_text(render_methodology(rows, summary, meta))
    print(f"[matchpicks] fixtures={summary['fixtures_captured']} open={summary['open']} "
          f"open_with_pick={summary['open_with_pick']} market={summary['open_market_basis']} "
          f"own={summary['open_own_line_basis']} unresolved={summary['unresolved_total']} "
          f"flags={summary['flags_total']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
