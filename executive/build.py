#!/usr/bin/env python3
"""Build the executive board — session arena/5545dbb8.

Offline and deterministic: it only reads what ``executive/collect.py`` stored (or the seeded
repository captures) and re-derives every published number. Run order in CI is
``collect.py -> build.py -> tests.py``; a failed build never publishes.

The one row per fixture is the deliverable: match, our pick, the probability for each team, the
basis the pick came from, and a source link for every input.

Basis ladder (first available wins; the tier is printed on every row):

1. ``MARKET-PRIMARY``   — outside bookmaker whole-match moneyline read from that bookmaker's own
                          public response (Pinnacle public guest endpoint).
2. ``MARKET-SECONDARY`` — outside bookmaker prices quoted through a public aggregator listing
                          (e.g. EGamersWorld's bc.game prices). Labelled secondary.
3. ``MODEL-OFFICIAL``   — our own line from the official Valve Regional Standings points of both
                          teams through Valve's published points-to-probability relation.
4. ``MODEL-BOUND``      — the fallback for low-tier fixtures no bookmaker prices: one team is in
                          the official standings, the other is not listed at all, so the
                          unlisted team is bounded by the lowest published points in that same
                          official file. Conservative, labelled provisional, always flagged.
0. ``NONE``             — nothing sourced; the row stays blank and is flagged.

Hotspawn crowd percentages are not read, stored or used anywhere in this file.
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA, EXEC, EGW_MATCHES, HLTV_MATCHES, HLTV_RANKING, HOTSPAWN_CS2, VRS_GLICKO_FILE as HLTV_GLICKO_FILE,
    PINNACLE_CS2_PAGE, PROB_SCALE_POINTS, VRS_REPO, devig_pair, epoch_ms_to_iso, fair_odds,
    iso, logit_prob, norm, odds_text, parse_iso, pct, read_csv, read_json, roster_key,
    official_url_safe, write_csv, write_json,
)

SITE = "Hotspawn CS2 · independent lines"
STALE_HOURS = 6            # a row is labelled stale for display after this many hours
MARKET_MAX_AGE_HOURS = 12  # a price older than this may not drive the headline probability
RATINGS_WEEK_DAYS = 7      # the official standings file is published weekly
KICKOFF_TOLERANCE_MIN = 15

TIER_LABELS = {
    1: "Market · primary book",
    2: "Market · secondary listing",
    3: "Model · official ratings",
    4: "Model · official bound (provisional)",
    0: "No sourced basis",
}
TIER_SHORT = {1: "T1 market", 2: "T2 market", 3: "T3 model", 4: "T4 provisional", 0: "no basis"}

FLAG_DEFS = {
    "FL-NO-MARKET": "No outside bookmaker line for this fixture was readable at capture time.",
    "FL-UNLISTED-OPPONENT": ("A team is absent from the official standings file, so the model uses the "
                             "lowest published value in that same official file as a conservative bound."),
    "FL-MODEL-MARKET-SPLIT": "Our originated line and the external market disagree by more than 15 points.",
    "FL-FORMAT-UNKNOWN": "The source does not state a series format for this fixture; left blank.",
    "FL-COINFLIP": "The headline probability is within 1 point of 50%; the pick has no edge.",
    "FL-STALE-CAPTURE": f"The capture behind this row is older than {STALE_HOURS} hours.",
    "FL-PLACEHOLDER-REJECTED": "An equal-pair placeholder price (e.g. 1.80/1.80) was rejected, not published.",
    "FL-NO-HLTV-LINK": "No HLTV match page could be matched to this fixture.",
    "FL-LOCKED": "The fixture is locked or already started; kept for the record, not an active pick.",
    "FL-ALIAS-NAME": "The rating was found under a different team spelling; the evidence link is on the row.",
    "FL-RATING-MISSING": "At least one team has no official rating and no market line, so no pick is possible.",
    "FL-KICKOFF-UNVERIFIED": "The outside line's kickoff did not match the fixture within tolerance; not used.",
    "FL-SOURCE-REFUSED": "A source refused the automated read; its values are blank, never guessed.",
    "FL-MULTI-DAY": "Fixture was first seen on an earlier snapshot; the first-seen time is shown.",
    "FL-FORMAT-FROM-HLTV": "Hotspawn left the series format blank; the format shown comes from the HLTV match page (linked).",
    "FL-FORMAT-CONFLICT": "Hotspawn's series format and HLTV's differ; both are shown rather than one being picked silently.",
    "FL-EXTERNAL-ONLY": "No market line and no official rating for at least one team; the pick rests on the sole available basis.",
    "FL-MARKET-STALE": f"The price is older than {MARKET_MAX_AGE_HOURS} hours, so it is shown for the record but does not drive the headline probability.",
    "FL-RATINGS-WEEK-OLD": "The official standings snapshot used is more than a week old (Valve publish weekly).",
    "FL-AMBIGUOUS-NAME": "Two rosters share this name in the official standings and the roster evidence does not separate them, so no rating is attached.",
    "FL-DUPLICATE-VRS-NAME": "Several standings entries share this name; the roster evidence selects one, and that evidence is linked on the row.",
    "FL-HLTV-IDENTITY-AMBIGUOUS": "HLTV's team pages list more than one match for this team pair in the same event, so no HLTV link is published.",
    "FL-PREDICTION-MARKET-BASIS": "No bookmaker line exists for this fixture; the headline probability comes from a prediction market (Polymarket), flagged so it is never read as a bookmaker price.",
}


# ------------------------------------------------------------------ helpers
def esc(value) -> str:
    return html_lib.escape(str(value if value is not None else ""), quote=True)


def badge(text: str, kind: str = "tier") -> str:
    return f'<span class="badge badge--{esc(kind)}">{esc(text)}</span>'


def link(url: str, label: str) -> str:
    safe = official_url_safe(url)
    if not safe:
        return f'<span class="muted">{esc(label)}</span>'
    return f'<a href="{esc(safe)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def source_links(pairs: list[tuple[str, str]]) -> str:
    items = [link(url, label) for url, label in pairs if url]
    return " · ".join(items) if items else '<span class="muted">no source available</span>'


# ------------------------------------------------------------------ inputs
def load_inputs() -> dict:
    fixtures_raw = read_json(DATA / "hotspawn_pages.json", {}) or {}
    return {
        "hotspawn": fixtures_raw,
        "vrs": read_json(DATA / "vrs.json", {}) or {},
        "hltv_ranking": read_json(DATA / "hltv_ranking.json", {}) or {},
        "hltv_matches": read_json(DATA / "hltv_matches.json", {}) or {},
        "hltv_teams": read_json(DATA / "hltv_teams.json", {}) or {},
        "hltv_schedule": read_json(DATA / "hltv_schedule.json", {}) or {},
        "pinnacle": read_json(DATA / "pinnacle.json", {}) or {},
        "secondary": read_json(DATA / "secondary_lines.json", {}) or {},
        "aliases": read_json(EXEC / "aliases.json", {}) or {},
        "previous": read_json(DATA / "analysis.json", {}) or {},
        "provenance": read_json(DATA / "provenance.json", {}) or {},
    }


def fixture_rows(hotspawn: dict) -> list[dict]:
    permalinks = {str(k): v for k, v in (hotspawn.get("permalinks") or {}).items()}
    rows = []
    for fixture in hotspawn.get("fixtures", []):
        fid = str(fixture.get("id"))
        rows.append({
            "match_id": fid,
            "tournament": fixture.get("competition_name") or "",
            "tier": (fixture.get("tier") or "").upper(),
            "offered_points": fixture.get("offered_points"),
            "stage": fixture.get("stage") or "",
            "series_format": (fixture.get("series_format") or
                              (f"BO{fixture['best_of']}" if fixture.get("best_of") else "")),
            "start_utc": epoch_ms_to_iso(fixture.get("scheduled_start_time")),
            "lock_utc": epoch_ms_to_iso(fixture.get("lock_time")),
            "lock_offset_sec": fixture.get("lock_offset_sec"),
            "source_status": fixture.get("status"),
            "team_a": fixture.get("participants0_name") or "",
            "team_b": fixture.get("participants1_name") or "",
            "hotspawn_match_url": permalinks.get(fid, ""),
            "hotspawn_pickem_url": HOTSPAWN_CS2,
            "seen_on": fixture.get("seen_on") or [],
        })
    rows.sort(key=lambda r: (r["start_utc"] or "9999", r["match_id"]))
    return rows


# ------------------------------------------------------------------ identity + ratings
def build_rating_indexes(inputs: dict) -> dict:
    vrs_rows = inputs["vrs"].get("rows", [])
    by_name: dict[str, list[dict]] = {}
    for row in vrs_rows:
        by_name.setdefault(norm(row["vrs_name"]), []).append(row)
    ranking_by_name = {}
    for team in inputs["hltv_ranking"].get("teams", []):
        ranking_by_name[norm(team["name"])] = team
    hltv_teams = {norm(k): v for k, v in (inputs["hltv_teams"].get("teams") or {}).items()}
    aliases = {}
    for name, entry in ((inputs.get("aliases") or {}).get("renames") or {}).items():
        if isinstance(entry, dict) and entry.get("official_name"):
            aliases[norm(name)] = norm(entry["official_name"])
    return {"by_name": by_name, "ranking_by_name": ranking_by_name, "vrs_rows": vrs_rows,
            "hltv_teams": hltv_teams, "aliases": aliases}


def team_record(name: str, inputs: dict, indexes: dict, needed: bool = True) -> dict:
    """Resolve one Hotspawn team spelling to an official rating, with the evidence recorded.

    Methods, strongest first:
      exact    — the same name (case/punctuation-insensitive) in the official standings;
      hltv     — HLTV's own spelling of the same roster appears in the official standings;
      roster   — >=4 of 5 listed players shared with an official standings entry;
      alias    — an evidence-linked rename recorded in executive/aliases.json;
      none     — nothing sourced: the rating stays blank.
    """
    record = {
        "team": name, "vrs_name": "", "vrs_rank": "", "vrs_points": "", "vrs_roster": "",
        "vrs_url": "", "vrs_details_url": "", "match_method": "none", "match_evidence_url": "",
        "alias_note": "", "hltv_name": "", "hltv_team_id": "", "hltv_rank": "", "hltv_points": "",
        "hltv_url": "", "hltv_roster": "", "flags": [],
    }
    key = norm(name)
    candidates = indexes["by_name"].get(key) or []
    vrs = candidates[0] if len(candidates) == 1 else None
    ranking = indexes["ranking_by_name"].get(key)
    method, evidence, alias_note = "", "", ""
    if len(candidates) > 1:
        # Two rosters share this name in the official file (e.g. "6666" #127 and #368). The row is only
        # used when the roster evidence separates them; otherwise the rating stays blank and is flagged.
        hltv_team_row = indexes["hltv_teams"].get(key, {})
        players = roster_key(hltv_team_row.get("players") or [])
        scored = sorted(((len(players & roster_key(row.get("vrs_roster"))), row) for row in candidates),
                        key=lambda item: -item[0])
        if players and scored and scored[0][0] >= 3 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            vrs = scored[0][1]
            method = "exact+roster"
            evidence = official_url_safe(hltv_team_row.get("evidence_url") or hltv_team_row.get("url")) or HLTV_MATCHES
            alias_note = (f"{scored[0][0]} of the roster's listed players match the official entry "
                          f"{vrs['vrs_name']} #{vrs['vrs_rank']}, which is what separates it from the "
                          f"other entry with the same name.")
        else:
            record["flags"].append("FL-AMBIGUOUS-NAME")
            record["match_method"] = "ambiguous"
            record["alias_note"] = (f"{len(candidates)} entries in the official standings share this name "
                                    f"and the roster evidence does not separate them: "
                                    f"{', '.join('#' + str(row['vrs_rank']) for row in candidates)}. "
                                    "No rating is attached.")
            index_team = ranking or {}
            record.update({
                "hltv_name": index_team.get("name", ""), "hltv_team_id": index_team.get("team_id", ""),
                "hltv_rank": index_team.get("rank", ""), "hltv_points": index_team.get("points", ""),
                "hltv_url": inputs["hltv_ranking"].get("canonical_url", HLTV_RANKING),
            })
            return record

    hltv_team = indexes["hltv_teams"].get(key, {})
    if vrs is None:
        hltv_names = [hltv_team.get("name") or "", *(hltv_team.get("names") or [])]
        for candidate in hltv_names:
            entries = indexes["by_name"].get(norm(candidate)) or []
            if candidate and len(entries) == 1:
                vrs = entries[0]
                method = "hltv"
                evidence = official_url_safe(hltv_team.get("evidence_url")) or HLTV_MATCHES
                alias_note = f"HLTV spells this team “{candidate}”; the official standings use “{vrs['vrs_name']}”."
                break
    if vrs is None:
        players = roster_key(hltv_team.get("players") or [])
        if len(players) >= 4:
            scored = sorted(((len(players & roster_key(row.get("vrs_roster"))), row)
                             for row in indexes["vrs_rows"]), key=lambda item: -item[0])
            if scored and scored[0][0] >= 4 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
                vrs = scored[0][1]
                method = "roster"
                evidence = official_url_safe(hltv_team.get("evidence_url")) or HLTV_MATCHES
                alias_note = (f"{scored[0][0]} listed players match the official standings entry "
                              f"“{vrs['vrs_name']}” (#{vrs['vrs_rank']}).")
    if vrs is None:
        entry = (inputs["aliases"].get("renames") or {}).get(name) or {}
        target = entry.get("official_name")
        entries = indexes["by_name"].get(norm(target)) or []
        if target and len(entries) == 1:
            vrs = entries[0]
            method = "alias"
            evidence = entry.get("evidence_url", "")
            alias_note = entry.get("note", "")
    if vrs is None:
        entries = indexes["by_name"].get(key) or []
        if len(entries) == 1:
            vrs, method = entries[0], method or "exact"
    else:
        method = method or "exact"
        evidence = evidence or (inputs["vrs"].get("blob_url", "") if method == "exact" else evidence)

    record["match_method"] = method or "none"
    if vrs is not None:
        details_tail = (vrs.get("vrs_details_path") or "").lstrip("./")
        record.update({
            "vrs_name": vrs["vrs_name"], "vrs_rank": vrs["vrs_rank"], "vrs_points": vrs["vrs_points"],
            "vrs_roster": vrs.get("vrs_roster", ""),
            "vrs_url": inputs["vrs"].get("blob_url") or VRS_REPO,
            "vrs_details_url": (inputs["vrs"].get("details_base", "") + details_tail) if details_tail else "",
        })
        if record["match_method"] in ("hltv", "roster", "alias"):
            record["match_evidence_url"] = official_url_safe(evidence)
            record["alias_note"] = alias_note
            record["flags"].append("FL-ALIAS-NAME")
        elif record["match_method"] == "exact+roster":
            record["match_evidence_url"] = official_url_safe(evidence)
            record["alias_note"] = alias_note
            record["flags"].append("FL-DUPLICATE-VRS-NAME")
    if ranking is not None:
        record.update({
            "hltv_name": ranking["name"], "hltv_team_id": ranking.get("team_id") or "",
            "hltv_rank": ranking["rank"], "hltv_points": ranking.get("points") or "",
            "hltv_url": f"https://www.hltv.org/team/{ranking.get('team_id')}/{ranking.get('slug')}"
                        if ranking.get("team_id") and ranking.get("slug") else inputs["hltv_ranking"].get("canonical_url", HLTV_RANKING),
            "hltv_roster": ", ".join(ranking.get("players") or []),
        })
    else:
        if hltv_team.get("url"):
            record["hltv_url"] = hltv_team["url"]
            record["hltv_name"] = hltv_team.get("name") or ""
            record["hltv_roster"] = ", ".join(hltv_team.get("players") or [])
    return record


# ------------------------------------------------------------------ external lines
def quote_matches_fixture(quote: dict, fixture: dict) -> bool:
    """Names must line up in either order; the kickoff must agree within tolerance when known."""
    qa, qb = norm(quote.get("team_a")), norm(quote.get("team_b"))
    fa, fb = norm(fixture["team_a"]), norm(fixture["team_b"])
    same = {qa, qb} == {fa, fb}
    if not same:
        return False
    q_start, f_start = parse_iso(quote.get("start_time")), parse_iso(fixture["start_utc"])
    if q_start and f_start:
        return abs((q_start - f_start).total_seconds()) <= KICKOFF_TOLERANCE_MIN * 60
    return False


def assigned_quotes(fixture: dict, quotes: list[dict]) -> list[dict]:
    out = []
    for quote in quotes:
        if not quote_matches_fixture(quote, fixture):
            continue
        reversed_order = norm(quote.get("team_a")) == norm(fixture["team_b"])
        try:
            odds_a = float(quote["odds_b"] if reversed_order else quote["odds_a"])
            odds_b = float(quote["odds_a"] if reversed_order else quote["odds_b"])
        except (KeyError, TypeError, ValueError):
            continue
        if min(odds_a, odds_b) <= 1.0:
            continue
        if abs(odds_a - odds_b) < 1e-9:
            # An equal pair is the well-known "no market posted" placeholder (1.80/1.80).
            out.append({**quote, "placeholder": True})
            continue
        p_a, p_b, overround = devig_pair(odds_a, odds_b)
        out.append({**quote, "odds_a_for_fixture": odds_a, "odds_b_for_fixture": odds_b,
                    "p_a": p_a, "p_b": p_b, "overround_pct": overround, "placeholder": False,
                    "reversed": reversed_order})
    return out


def hltv_link_for(fixture: dict, ratings: dict, inputs: dict, indexes: dict) -> dict:
    """Find the HLTV match page for this fixture and its published format/result.

    Identity rule: both team names must match as a pair (either order) using Hotspawn's spelling or
    the HLTV spelling already recorded for that team, and the kickoff must agree within 30 minutes.
    Nothing is matched on one team alone.
    """
    def names_for(team: str) -> set[str]:
        out = {norm(team)}
        record = indexes["hltv_teams"].get(norm(team)) or {}
        out.add(norm(record.get("name")))
        for alias in record.get("names") or []:
            out.add(norm(alias))
        return {n for n in out if n}

    left, right = names_for(fixture["team_a"]), names_for(fixture["team_b"])
    start = parse_iso(fixture["start_utc"])
    for row in inputs["hltv_matches"].get("rows", []):
        row_left, row_right = norm(row.get("team_a")), norm(row.get("team_b"))
        if not (row_left and row_right):
            continue
        paired = ((row_left in left and row_right in right) or
                  (row_left in right and row_right in left))
        if not paired:
            continue
        kickoff = parse_iso(row.get("kickoff_utc"))
        if start and kickoff and abs((kickoff - start).total_seconds()) > 30 * 60:
            continue
        return {"hltv_match_url": row.get("hltv_url", ""), "hltv_match_id": row.get("hltv_match_id", ""),
                "hltv_format": row.get("format") or "", "hltv_event": row.get("event") or "",
                "hltv_kickoff": row.get("kickoff_utc") or ""}
    return {}


EVENT_STOPWORDS = {"the", "of", "and", "a", "an", "cup", "series", "stage", "group", "playoffs",
                   "playoff", "closed", "qualifier", "open", "season"}


def slug_event_tokens(slug: str, slug_a: str, slug_b: str) -> tuple[str, list[str]]:
    """Split ``<a>-vs-<b>-<event>`` and return the event part plus its tokens."""
    lowered = slug.lower()
    for first, second in ((slug_a, slug_b), (slug_b, slug_a)):
        prefix = f"{first}-vs-{second}-"
        if lowered.startswith(prefix):
            return lowered[len(prefix):], [t for t in lowered[len(prefix):].split("-") if t]
    return "", []


def hltv_schedule_match(fixture: dict, indexes: dict, schedule: dict | None) -> dict:
    """Find this fixture's HLTV match page on the team pages the collector read.

    hltv.org/matches and the individual match pages refuse automated reads, but each team page lists
    that team's fixtures as /matches/<id>/<slug> links, and HLTV writes both team slugs *and* the
    event name into the slug (``<team>-vs-<team>-<event>``).  Identity here therefore needs two
    independent agreements — the team pair and every significant word of Hotspawn's own tournament
    name — and a team pair that occurs more than once inside the same event is left unresolved rather
    than guessed.  No kickoff is claimed from these pages: the upcoming-match blocks do not carry
    data-unix stamps consistently enough to be evidence (recorded in
    reviews/5545dbb8-verification.md).
    """
    pages = (schedule or {}).get("teams") or {}
    if not pages:
        return {}
    by_team_id = {str(page.get("team_id")): page for page in pages.values() if page.get("team_id")}
    ids, slugs = {}, {}
    for field in ("team_a", "team_b"):
        key = norm(fixture[field])
        record = (indexes["hltv_teams"].get(key)
                  or indexes["hltv_teams"].get((indexes.get("aliases") or {}).get(key, ""))
                  or {})
        found = re.search(r"/team/(\d+)/([^/?#]+)", record.get("url") or "")
        if found:
            ids[field] = found.group(1)
            slugs[field] = found.group(2).lower()
    if len(ids) != 2 or not all(slugs.values()):
        return {}
    slug_a, slug_b = slugs["team_a"], slugs["team_b"]
    wanted = [t for t in re.findall(r"[a-z0-9]+", (fixture.get("tournament") or "").lower())
              if t not in EVENT_STOPWORDS]
    hits: dict[str, dict] = {}
    for field in ("team_a", "team_b"):
        page = by_team_id.get(ids[field])
        if not page:
            continue
        for row in page.get("matches") or []:
            event_part, tokens = slug_event_tokens(str(row.get("slug") or ""), slug_a, slug_b)
            if not event_part:
                continue
            if wanted:
                shared = set(wanted) & set(tokens)
                # Two independent agreements are still required (the team pair above, plus the event
                # here), but organizers reword their stages between sources: Hotspawn's
                # "CCT Europe 2026 Series #12 Play-In" is HLTV's "...-series-12-closed-qualifier".
                # So the event must keep most of its significant words and at least three of them.
                if len(shared) < 3 or len(shared) / len(wanted) < 0.6:
                    continue
            key = str(row.get("hltv_match_id") or row.get("hltv_url"))
            entry = hits.setdefault(key, {"hltv_url": row.get("hltv_url") or "", "hltv_match_id": key,
                                          "event_from_slug": event_part,
                                          "listed_on": page.get("hltv_url") or "",
                                          "pages_seen": 0})
            entry["pages_seen"] += 1
    if len(hits) != 1:
        if len(hits) > 1:
            return {"ambiguous": sorted(hits), "candidates": [h["hltv_url"] for h in hits.values()]}
        return {}
    only = list(hits.values())[0]
    return {"hltv_match_url": only["hltv_url"], "hltv_match_id": only["hltv_match_id"],
            "hltv_event_from_slug": only["event_from_slug"],
            "hltv_listed_on": only["listed_on"], "hltv_pages_seen": only["pages_seen"]}


# ------------------------------------------------------------------ analysis
def analyse(fixture: dict, ratings: dict, market: list[dict], secondary: list[dict],
            now: datetime, vrs_meta: dict, hltv: dict | None = None) -> dict:
    hltv = hltv or {}
    flags: list[str] = []
    a, b = ratings[fixture["team_a"]], ratings[fixture["team_b"]]
    start, lock = parse_iso(fixture["start_utc"]), parse_iso(fixture["lock_utc"])
    live = bool(start and start > now)
    if not live:
        flags.append("FL-LOCKED")
    series_format = fixture["series_format"]
    series_format_source = ""
    if not series_format and hltv.get("hltv_format"):
        series_format = hltv["hltv_format"]
        series_format_source = hltv.get("hltv_match_url", "")
        flags.append("FL-FORMAT-FROM-HLTV")
    elif series_format and hltv.get("hltv_format") and series_format.upper().replace(" ", "") != hltv["hltv_format"].upper():
        flags.append("FL-FORMAT-CONFLICT")
    if not series_format:
        flags.append("FL-FORMAT-UNKNOWN")
    for record in (a, b):
        flags.extend(record.get("flags") or [])

    # HLTV identity note: the link was accepted only when the team pair *and* the event name both
    # matched, so the note states the event HLTV filed the fixture under.
    schedule = hltv.get("hltv_schedule") or {}
    hltv_note = ""
    if schedule.get("ambiguous"):
        flags.append("FL-HLTV-IDENTITY-AMBIGUOUS")
        hltv_note = ("HLTV's team pages list more than one match for this pair in the same event; "
                     "no HLTV link is published rather than choosing one.")
    elif schedule.get("hltv_match_url"):
        hltv_note = (f"HLTV files this fixture under “{schedule.get('hltv_event_from_slug', '')}” "
                     f"(team pair and event name both match; seen on "
                     f"{schedule.get('hltv_pages_seen', 1)} team page(s)).")

    primary = [q for q in market if not q.get("placeholder")]
    secondary_ok = [q for q in secondary if not q.get("placeholder")]
    placeholders = [q for q in (market + secondary) if q.get("placeholder")]
    if placeholders:
        flags.append("FL-PLACEHOLDER-REJECTED")

    basis_tier, basis_detail, basis_sources = 0, "", []
    prob_a = prob_b = None
    model_prob_a = market_prob_a = None
    used = {}

    if primary:
        chosen = sorted(primary, key=lambda q: q["overround_pct"])[0]
        used = chosen
        market_prob_a = chosen["p_a"]
        prob_a, prob_b = chosen["p_a"], chosen["p_b"]
        basis_tier = 1
        basis_detail = (f"{chosen['source_name']} whole-match moneyline "
                        f"{odds_text(chosen['odds_a_for_fixture'])} / {odds_text(chosen['odds_b_for_fixture'])} "
                        f"(native {chosen.get('native_format', 'decimal')}), overround "
                        f"{chosen['overround_pct']:.2f}%, proportional de-vig.")
        basis_sources = [(chosen.get("source_url"), chosen["source_name"]),
                         (chosen.get("api_url"), "raw response")]
    elif secondary_ok:
        # Bookmaker listings outrank prediction markets; inside each group the tightest book wins.
        bookmakers = [q for q in secondary_ok if q.get("source_role") != "prediction_market"]
        chosen = sorted(bookmakers or secondary_ok, key=lambda q: q["overround_pct"])[0]
        used = chosen
        market_prob_a = chosen["p_a"]
        prob_a, prob_b = chosen["p_a"], chosen["p_b"]
        basis_tier = 2
        if chosen.get("native_format") == "implied_probability":
            flags.append("FL-PREDICTION-MARKET-BASIS")
            basis_detail = (f"{chosen['source_name']} implied probabilities "
                            f"{pct(float(chosen.get('native_a') or 0), 1)}% / "
                            f"{pct(float(chosen.get('native_b') or 0), 1)}% (native implied probability), "
                            f"normalised to 100% by proportional de-vig. Prediction market, not a "
                            "bookmaker; only used where no bookmaker line exists for this fixture.")
        else:
            basis_detail = (f"{chosen['source_name']} listing "
                            f"{odds_text(chosen['odds_a_for_fixture'])} / {odds_text(chosen['odds_b_for_fixture'])} "
                            f"(decimal), overround {chosen['overround_pct']:.2f}%, proportional de-vig. "
                            "Secondary listing: the aggregator's own page is the source, not the book itself.")
        basis_sources = [(chosen.get("source_url"), chosen["source_name"])]
    else:
        flags.append("FL-NO-MARKET")

    have_vrs_a = bool(a["vrs_points"])
    have_vrs_b = bool(b["vrs_points"])
    ranked_floor = 0
    if vrs_meta.get("rows"):
        ranked_floor = min(int(row["vrs_points"]) for row in vrs_meta["rows"])

    if have_vrs_a and have_vrs_b:
        ra, rb = float(a["vrs_points"]), float(b["vrs_points"])
        model_prob_a = logit_prob(ra, rb)
        if basis_tier == 0:
            prob_a, prob_b = model_prob_a, 1 - model_prob_a
            basis_tier = 3
        basis_detail = (basis_detail + " " if basis_detail else "") + (
            f"Originated rating line: {a['vrs_name']} {a['vrs_points']} vs {b['vrs_name']} {b['vrs_points']} "
            f"official points, p = 1/(1+10^((Rb-Ra)/400)) = {pct(model_prob_a, 1)}%.")
        basis_sources += [(a["vrs_url"], f"{a['vrs_name']} standings"),
                          (b["vrs_url"], f"{b['vrs_name']} standings")]
    elif (have_vrs_a != have_vrs_b) and ranked_floor and (
            (a["match_method"] == "none") != (b["match_method"] == "none")):
        known, known_key, missing = ((a, "a", b) if have_vrs_a else (b, "b", a))
        if missing["match_method"] != "none":
            missing = a if missing is b else b
        r_known, r_missing = float(known["vrs_points"]), float(ranked_floor)
        p_known = logit_prob(r_known, r_missing)
        model_prob_a = p_known if known_key == "a" else 1 - p_known
        if basis_tier == 0:
            prob_a, prob_b = model_prob_a, 1 - model_prob_a
            basis_tier = 4
        flags.append("FL-UNLISTED-OPPONENT")
        basis_detail = (basis_detail + " " if basis_detail else "") + (
            f"Provisional bound: {missing['team']} is absent from the official standings file, so the lowest "
            f"published value in that same file ({ranked_floor} points) is used as its ceiling; "
            f"{known['vrs_name']} keeps its published {known['vrs_points']} points. "
            f"Because the unlisted team's value can only be lower, the favourite's true win probability is at "
            f"least this estimate ({pct(model_prob_a, 1)}% for {known['team']}), which is what is published.")
        basis_sources += [(known["vrs_url"], f"{known['vrs_name']} standings"),
                          (vrs_meta.get("blob_url") or VRS_REPO, "official standings file (bound)")]
    elif a["match_method"] == "ambiguous" or b["match_method"] == "ambiguous":
        flags.append("FL-AMBIGUOUS-NAME")
        basis_detail = (basis_detail + " " if basis_detail else "") + (
            "No originated line: " + "; ".join(filter(None, [
                (a["alias_note"] if a["match_method"] == "ambiguous" else ""),
                (b["alias_note"] if b["match_method"] == "ambiguous" else "")])) )
    else:
        flags.append("FL-RATING-MISSING")

    if not primary and market_prob_a is None and secondary_ok:
        pass
    # cross-check: model vs market
    if market_prob_a is not None and model_prob_a is not None:
        if abs(market_prob_a - model_prob_a) * 100.0 > 15.0:
            flags.append("FL-MODEL-MARKET-SPLIT")

    captured = parse_iso(used.get("captured_utc")) if used else None
    if basis_tier in (1, 2) and captured:
        age_hours = (now - captured).total_seconds() / 3600.0
        if age_hours > STALE_HOURS:
            flags.append("FL-STALE-CAPTURE")
        if age_hours > MARKET_MAX_AGE_HOURS:
            flags.append("FL-MARKET-STALE")
    standings_date = vrs_meta.get("standings_date")
    standings_dt = parse_iso(standings_date) if standings_date else None
    if basis_tier in (3, 4) and standings_dt and (now - standings_dt) > timedelta(days=RATINGS_WEEK_DAYS):
        flags.append("FL-RATINGS-WEEK-OLD")

    pick, pick_prob, confidence = "", None, ""
    if prob_a is not None and prob_b is not None:
        if abs(prob_a - prob_b) < 0.005:
            flags.append("FL-COINFLIP")
            pick = "(no side — 50/50)"
        else:
            pick = fixture["team_a"] if prob_a > prob_b else fixture["team_b"]
            pick_prob = max(prob_a, prob_b)
            if abs(pick_prob - 0.5) <= 0.01:
                flags.append("FL-COINFLIP")
        confidence = {1: "High (market line)", 2: "Medium (secondary listing)",
                      3: "Low (our line, uncalibrated)", 4: "Provisional (official bound)"}.get(basis_tier, "")
    elif a["match_method"] == "ambiguous" or b["match_method"] == "ambiguous":
        flags.append("FL-AMBIGUOUS-NAME")
        basis_detail = (basis_detail + " " if basis_detail else "") + (
            "No originated line: " + "; ".join(filter(None, [
                (a["alias_note"] if a["match_method"] == "ambiguous" else ""),
                (b["alias_note"] if b["match_method"] == "ambiguous" else "")])) )
    else:
        flags.append("FL-RATING-MISSING")

    return {
        "match_id": fixture["match_id"],
        "tournament": fixture["tournament"], "tier": fixture["tier"],
        "offered_points": fixture["offered_points"], "stage": fixture["stage"],
        "series_format": series_format, "series_format_source": series_format_source,
        "hltv_match_url": hltv.get("hltv_match_url", ""), "hltv_match_id": hltv.get("hltv_match_id", ""),
        "hltv_schedule_note": hltv_note,
        "start_utc": fixture["start_utc"], "lock_utc": fixture["lock_utc"],
        "status": "open" if live else "locked",
        "team_a": fixture["team_a"], "team_b": fixture["team_b"],
        "hotspawn_pickem_url": fixture["hotspawn_pickem_url"],
        "hotspawn_match_url": fixture["hotspawn_match_url"],
        "basis_tier": basis_tier, "basis_label": TIER_LABELS[basis_tier], "basis_detail": basis_detail.strip(),
        "basis_sources": basis_sources,
        "market_source": used.get("source_name", ""), "market_odds_a": odds_text(used.get("odds_a_for_fixture")) if used else "",
        "market_odds_b": odds_text(used.get("odds_b_for_fixture")) if used else "",
        "market_overround_pct": f"{used['overround_pct']:.2f}" if used else "",
        "market_captured_utc": (used.get("captured_utc") or "") if used else "",
        "market_prob_a_pct": pct(market_prob_a), "market_prob_b_pct": pct(1 - market_prob_a) if market_prob_a is not None else "",
        "model_prob_a_pct": pct(model_prob_a), "model_prob_b_pct": pct(1 - model_prob_a) if model_prob_a is not None else "",
        "prob_a_pct": pct(prob_a), "prob_b_pct": pct(prob_b),
        "fair_odds_a": odds_text(fair_odds(prob_a)) if prob_a else "",
        "fair_odds_b": odds_text(fair_odds(prob_b)) if prob_b else "",
        "pick": pick, "pick_prob_pct": pct(pick_prob) if pick_prob is not None else "", "confidence": confidence,
        "rating_a": a, "rating_b": b,
        "flags": sorted(set(flags)),
    }


# ------------------------------------------------------------------ page shell
def page(title: str, body: str, meta: dict, active: str = "") -> str:
    nav = [
        ("index.html", "Summary"), ("picks.html", "All picks"), ("lines.html", "Betting lines"),
        ("own-lines.html", "Our lines"), ("tournaments.html", "Tournaments"),
        ("coverage.html", "Coverage"), ("verification.html", "Verification"),
        ("sources.html", "Sources"), ("methodology.html", "Method"), ("flagged.html", "Flagged"),
    ]
    links = "".join(
        f'<a class="nav__link{" nav__link--active" if href == active else ""}" href="{href}">{esc(label)}</a>'
        for href, label in nav)
    stale_banner = ""
    if meta.get("stale"):
        stale_banner = (
            '<div class="banner" role="status"><strong>Snapshot is '
            f'{esc(meta.get("snapshot_age_text", "").replace("Snapshot is ", ""))}.</strong> '
            'Prices shown are the last readable capture — each row prints its own read time. '
            'The hourly refresh replaces this snapshot with a live read; nothing here is presented as a '
            'current price until it is.</div>')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="light dark">
<title>{esc(title)} · {esc(SITE)}</title>
<meta name="description" content="Every CS2 fixture on the Hotspawn Pick'em board with our pick, the probability for each team, and a source link for every number.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="topbar">
  <div class="topbar__inner">
    <a class="brand" href="index.html"><span class="brand__mark">◎</span><span class="brand__text">{esc(SITE)}</span></a>
    <div class="topbar__meta">
      <strong>{esc(meta.get("snapshot_age_text", ""))}</strong>
      <span class="muted">{esc(meta.get("hotspawn_read_text", ""))}</span>
    </div>
  </div>
  <nav class="nav" aria-label="Sections">{links}</nav>
</header>
<main id="main" class="wrap">
{stale_banner}
{body}
</main>
<footer class="foot">
  <p><strong>Analysis only — not betting advice.</strong> Outside prices are public website reads at the
  times printed on each row; they move. Our own lines are uncalibrated unless a row says otherwise.
  Hotspawn supplies fixture identity, tier, points and UTC lock/start times only and is never used as a
  probability input. Values that no source confirms stay blank and are listed on
  <a href="flagged.html">Flagged for review</a>.</p>
  <p class="muted">Built by the executive-board session from <a href="sources.html">these sources</a>.
  Snapshot {esc(meta.get("generated_utc", ""))} · capture {esc(meta.get("capture_utc", ""))} ·
  <a href="../index.html">all boards on this site</a></p>
</footer>
<script src="board.js" defer></script>
</body>
</html>
"""


def table(headers: list[str], rows: list[list[str]], classes: str = "",
          row_attrs: list[dict] | None = None) -> str:
    head = "".join(f"<th scope=\"col\">{h}</th>" for h in headers)
    body = []
    for index, row in enumerate(rows):
        attrs = (row_attrs or [{}] * len(rows))[index] if row_attrs else {}
        attr_text = "".join(f' {esc(k)}="{esc(v)}"' for k, v in attrs.items())
        cells = "".join(
            f'<td data-label="{esc(headers[i])}">{cell}</td>' for i, cell in enumerate(row))
        body.append(f"<tr{attr_text}>{cells}</tr>")
    return (f'<div class="tablewrap"><table class="grid {classes}"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def pick_card(row: dict, now: datetime) -> str:
    start = parse_iso(row["start_utc"])
    when = ""
    if start:
        hours = (start - now).total_seconds() / 3600.0
        when = (f"in {hours:.1f} h" if hours >= 0 else f"{abs(hours):.1f} h ago")
    prob_a = row["prob_a_pct"] or "—"
    prob_b = row["prob_b_pct"] or "—"
    fav_a = (row["prob_a_pct"] or "") and float(row["prob_a_pct"]) > float(row["prob_b_pct"] or 0)
    sources = source_links([(u, l) for u, l in row["basis_sources"]][:3] +
                           [(row["hotspawn_match_url"] or row["hotspawn_pickem_url"], "Hotspawn")] +
                           ([(row["hltv_match_url"], "HLTV match")] if row.get("hltv_match_url") else []))
    hltv_note = (f'<p class="pick__note">HLTV: {esc(row["hltv_schedule_note"])}</p>'
                 if row.get("hltv_schedule_note") else "")
    return f"""<article class="pick" data-tier="{row['basis_tier']}" data-status="{esc(row['status'])}"
  data-team="{esc(row['team_a'].lower())} {esc(row['team_b'].lower())}"
  data-search="{esc((row['team_a'] + ' ' + row['team_b'] + ' ' + row['tournament']).lower())}">
  <div class="pick__top">
    <span class="pick__tour">{esc(row['tournament'])}</span>
    {badge(TIER_SHORT[row['basis_tier']], 'tier-' + str(row['basis_tier']))}
    {badge(row['status'].title(), 'status')}
  </div>
  <div class="pick__teams">
    <span class="team{' team--fav' if fav_a else ''}">{esc(row['team_a'])}<b>{esc(prob_a)}%</b></span>
    <span class="vs">vs</span>
    <span class="team{' team--fav' if row['prob_a_pct'] and not fav_a else ''}">{esc(row['team_b'])}<b>{esc(prob_b)}%</b></span>
  </div>
  <div class="pick__call">
    <span class="pick__label">Pick</span>
    <span class="pick__pick">{esc(row['pick'] or '— no pick —')}</span>
    <span class="pick__prob">{esc(row['pick_prob_pct'])}%</span>
  </div>
  <dl class="pick__meta">
    <div><dt>Locks</dt><dd>{esc(row['lock_utc'])} <span class="muted">({esc(when)})</span></dd></div>
    <div><dt>Tier / value</dt><dd>{esc(row['tier'] or '—')} · {esc(row['offered_points'] or '—')} pts</dd></div>
    <div><dt>Format</dt><dd>{esc(row['series_format'] or '—')}</dd></div>
    <div><dt>Confidence</dt><dd>{esc(row['confidence'] or '—')}</dd></div>
  </dl>
  <p class="pick__basis">{esc(row['basis_detail'])}</p>
  {hltv_note}
  <p class="pick__sources">{sources}</p>
</article>"""


# ------------------------------------------------------------------ pages
def render_index(rows: list[dict], meta: dict, coverage: dict) -> str:
    now = meta["now"]
    open_rows = [r for r in rows if r["status"] == "open"]
    with_pick = [r for r in open_rows if r["pick"] and r["pick"] != "(no side — 50/50)"]
    provisional = [r for r in open_rows if r["basis_tier"] == 4]
    no_pick = [r for r in open_rows if not r["pick"] or r["pick"] == "(no side — 50/50)"]
    market_rows = [r for r in open_rows if r["basis_tier"] in (1, 2)]
    model_rows = [r for r in open_rows if r["basis_tier"] in (3, 4)]
    next_rows = sorted(open_rows, key=lambda r: r["lock_utc"] or "9999")[:8]
    tournaments = {}
    for row in open_rows:
        entry = tournaments.setdefault(row["tournament"], {"n": 0, "picks": 0, "tier": row["tier"]})
        entry["n"] += 1
        if row["pick"] and row["pick"] != "(no side — 50/50)":
            entry["picks"] += 1
        if row["tier"]:
            entry["tier"] = row["tier"]

    board_buttons = [
        ("picks.html", "All picks & probabilities", f"{len(with_pick)} of {len(open_rows)} open fixtures"),
        ("picks.html#today", "Picks locking soon", "next 24 hours, mobile cards"),
        ("lines.html", "Betting lines from outside books", f"{len(market_rows)} fixtures priced"),
        ("own-lines.html", "Our own lines", f"{len(model_rows)} fixtures from official ratings"),
        ("coverage.html", "Hotspawn coverage check", f"{coverage['total_fixtures']} fixtures in the payload"),
        ("flagged.html", "Flagged for review", f"{coverage['flagged_rows']} rows to check"),
    ]
    other_boards = [
        ("../open-slate/index.html", "Open slate (hourly board)"),
        ("../slate/cs2.html", "Whole-slate board"),
        ("../model/index.html", "Own-line model (VRS)"),
        ("../oct14/index.html", "14 Oct categorised board"),
        ("../live/index.html", "Live board"),
        ("../picks/index.html", "Tiered picks board"),
    ]
    return f"""
<section class="hero">
  <p class="eyebrow">Executive summary</p>
  <h1>Every CS2 match on the Hotspawn board — one pick, two probabilities, and the source behind them.</h1>
  <p class="lede">This page is the starting point. It lists <strong>{len(open_rows)} open fixtures</strong>
  right now, gives a pick for <strong>{len(with_pick)} of them</strong> ({pct(len(with_pick)/len(open_rows) if open_rows else 0, 0)}%),
  and links straight to the table where every number is written down with its source.</p>
  <p class="meta-line">{esc(meta['snapshot_age_text'])} · Hotspawn read {esc(meta['hotspawn_read_text'])} ·
  outside prices {esc(meta['market_read_text'])} · official ratings {esc(meta['vrs_read_text'])}</p>
</section>

<section class="panel panel--primary">
  <h2>Where the picks are</h2>
  <div class="buttons">
    {''.join(f'<a class="button" href="{href}"><strong>{label}</strong><span>{esc(sub)}</span></a>' for href, label, sub in board_buttons)}
  </div>
  <p class="muted small">Bookmark <code>…/executive/</code> — this page and the picks table are rebuilt
  automatically every hour from the Hotspawn board and the outside sources.</p>
</section>

<section>
  <h2>Coverage in one line</h2>
  <div class="stats">
    <div class="stat"><b>{coverage['total_fixtures']}</b><span>CS2 fixtures Hotspawn lists</span></div>
    <div class="stat"><b>{len(open_rows)}</b><span>still open (lock in the future)</span></div>
    <div class="stat"><b>{len(with_pick)}</b><span>with a pick</span></div>
    <div class="stat"><b>{len(market_rows)}</b><span>priced by an outside book</span></div>
    <div class="stat"><b>{len(model_rows)}</b><span>from official ratings</span></div>
    <div class="stat"><b>{len(provisional)}</b><span>provisional (bound-based)</span></div>
    <div class="stat"><b>{len(no_pick)}</b><span>no sourced basis (flagged)</span></div>
    <div class="stat"><b>{coverage['stale_fixtures']}</b><span>stale fixtures kept by Hotspawn</span></div>
  </div>
</section>

<section>
  <h2>Next locks</h2>
  <p class="muted">Sorted by lock time. “Pick” is the favourite on the basis named on the row; the two
  percentages are that basis's win probability for each team and add to 100.</p>
  <div class="cards">{''.join(pick_card(r, now) for r in next_rows) or '<p class="muted">No open fixtures.</p>'}</div>
</section>

<section>
  <h2>By tournament</h2>
  {table(["Tournament", "Hotspawn tier", "Open fixtures", "With a pick"],
         [[esc(name), esc(data['tier'] or '—'), str(data['n']), f"{data['picks']}/{data['n']}"]
          for name, data in sorted(tournaments.items(), key=lambda kv: (-kv[1]['n'], kv[0]))])}
</section>

<section class="panel">
  <h2>How a pick is produced</h2>
  <ol class="ladder">
    <li><strong>Market · primary book</strong> — the outside bookmaker's own public response
      (Pinnacle guest endpoint), de-vigged proportionally. Highest confidence.</li>
    <li><strong>Market · secondary listing</strong> — prices quoted through a public aggregator
      (EGamersWorld/bc.game) or, where no bookmaker prices the fixture at all, a prediction market's
      implied probability (Polymarket, normalised the same way). Labelled secondary, flagged
      <code>FL-PREDICTION-MARKET-BASIS</code> when it is a prediction market, and never presented as
      the book's own feed.</li>
    <li><strong>Model · official ratings</strong> — both teams' points in Valve's official Regional
      Standings through the relation Valve publish in
      <a href="{esc(HLTV_GLICKO_FILE)}" target="_blank" rel="noopener noreferrer">model/glicko.js</a>
      (<code>p = 1/(1+10^((Rb−Ra)/−400))</code>). Uncalibrated, so labelled low confidence.</li>
    <li><strong>Model · official bound (provisional)</strong> — the fallback for low-tier fixtures no book
      prices: when one team is not in the official standings at all, the lowest published value in that
      same official file is used as that team's ceiling. Always flagged.</li>
    <li><strong>No sourced basis</strong> — the pick stays blank and the row is flagged. Nothing is invented.</li>
  </ol>
  <p class="muted small">Hotspawn's own crowd percentages are never read, stored or used — Hotspawn supplies
  fixture identity, tier, points and UTC lock/start times only.
  <a href="methodology.html">Full method and limits</a>.</p>
</section>

<section>
  <h2>Other boards on this site</h2>
  <ul class="linklist">
    {''.join(f'<li><a href="{href}">{esc(label)}</a></li>' for href, label in other_boards)}
  </ul>
</section>
"""


def render_picks(rows: list[dict], meta: dict) -> str:
    now = meta["now"]
    open_rows = [r for r in rows if r["status"] == "open"]
    soon = [r for r in sorted(open_rows, key=lambda r: r["lock_utc"] or "9999")
            if (parse_iso(r["lock_utc"]) or now) <= now + timedelta(hours=24)]
    body_rows, row_attrs = [], []
    for row in sorted(rows, key=lambda r: (r["status"], r["lock_utc"] or "9999")):
        row_attrs.append({
            "data-status": row["status"], "data-tier": str(row["basis_tier"]),
            "data-pick": row["pick"] or "", "data-flags": " ".join(row["flags"]),
        })
        sources = source_links([(u, l) for u, l in row["basis_sources"][:2]] +
                               [(row["hotspawn_match_url"] or row["hotspawn_pickem_url"], "Hotspawn")] +
                               ([(row["hltv_match_url"], "HLTV match")] if row.get("hltv_match_url")
                                else ([(row["rating_a"]["hltv_url"], "HLTV")] if row["rating_a"].get("hltv_url") else [])))
        if row.get("hltv_schedule_note"):
            sources += f'<span class="cell-sub">{esc(row["hltv_schedule_note"])}</span>'
        flags = " ".join(badge(f, "flag") for f in row["flags"]) or '<span class="muted">—</span>'
        body_rows.append([
            f'<span class="nowrap">{esc((row["lock_utc"] or "")[:16])}Z</span>',
            f'<span class="cell-teams">{esc(row["team_a"])} <span class="muted">vs</span> {esc(row["team_b"])}</span>'
            f'<span class="cell-sub">{esc(row["tournament"])} · {esc(row["tier"] or "—")} · {esc(row["series_format"] or "format —")}</span>',
            f'{badge(TIER_SHORT[row["basis_tier"]], "tier-" + str(row["basis_tier"]))}',
            f'<span class="cell-probs"><b>{esc(row["prob_a_pct"] or "—")}%</b> / <b>{esc(row["prob_b_pct"] or "—")}%</b></span>',
            f'<strong>{esc(row["pick"] or "—")}</strong>' + (f' <span class="muted">{esc(row["pick_prob_pct"])}%</span>' if row["pick_prob_pct"] else ""),
            esc(row["confidence"] or "—"),
            sources,
            flags,
        ])
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">All picks</p>
  <h1>One row per Hotspawn CS2 fixture</h1>
  <p class="lede">Every fixture Hotspawn lists, with our pick, both win probabilities, the basis and the
  sources. Blank cells mean no source confirmed a value — never a guess.</p>
</section>

<section id="today">
  <h2>Locking in the next 24 hours ({len(soon)})</h2>
  <div class="cards">{''.join(pick_card(r, now) for r in soon) or '<p class="muted">Nothing locks in the next 24 hours.</p>'}</div>
</section>

<section>
  <h2>Full table</h2>
  <div class="filters">
    <input type="search" id="q" placeholder="Filter team or tournament…" aria-label="Filter team or tournament">
    <div class="chips">
      <button type="button" class="chip chip--on" data-filter="all">All</button>
      <button type="button" class="chip" data-filter="open">Open</button>
      <button type="button" class="chip" data-filter="locked">Locked</button>
      <button type="button" class="chip" data-filter="market">Market basis</button>
      <button type="button" class="chip" data-filter="model">Model basis</button>
      <button type="button" class="chip" data-filter="provisional">Provisional</button>
      <button type="button" class="chip" data-filter="nopick">No pick</button>
    </div>
  </div>
  <p class="muted small"><span id="shown">{len(body_rows)}</span> rows shown.</p>
  {table(["Lock (UTC)", "Match", "Basis", "Probability A / B", "Pick", "Confidence", "Sources", "Flags"],
         body_rows, classes="grid--picks", row_attrs=row_attrs)}
  <p class="muted small">Percentages add to 100 per row. “A” is the left-hand team Hotspawn shows.
  Differences under 1 point from 50/50 are flagged as coin flips.</p>
</section>
"""


def render_lines(rows: list[dict], inputs: dict, meta: dict) -> str:
    market = inputs["pinnacle"]
    secondary = inputs["secondary"]
    body = []
    for row in sorted(rows, key=lambda r: (r["status"], r["lock_utc"] or "9999")):
        quotes = row.get("_market", []) + row.get("_secondary", [])
        if not quotes:
            body.append([f'{esc(row["team_a"])} vs {esc(row["team_b"])}',
                         '<span class="muted">no readable outside line</span>', "—", "—", "—",
                         source_links([(row["hotspawn_match_url"] or row["hotspawn_pickem_url"], "Hotspawn")])])
            continue
        for quote in quotes:
            if quote.get("placeholder"):
                body.append([f'{esc(row["team_a"])} vs {esc(row["team_b"])}',
                             esc(quote["source_name"]) + " " + badge("rejected", "flag"),
                             esc(odds_text(quote.get("odds_a"))), esc(odds_text(quote.get("odds_b"))),
                             "—", source_links([(quote.get("source_url"), "source")])])
                continue
            vig = f'{quote["overround_pct"]:.2f}'
            body.append([
                f'{esc(row["team_a"])} vs {esc(row["team_b"])}',
                esc(quote["source_name"]) + (" " + badge("primary", "ok") if quote.get("source_role") == "primary_bookmaker"
                                             else " " + badge("secondary", "warn")),
                f'{esc(odds_text(quote["odds_a_for_fixture"]))} / {esc(odds_text(quote["odds_b_for_fixture"]))}',
                f'{esc(pct(quote["p_a"]))}% / {esc(pct(quote["p_b"]))}% <span class="muted">(vig {esc(vig)}%)</span>',
                esc((quote.get("captured_utc") or "")[:16]) + "Z",
                source_links([(quote.get("source_url"), "book page"), (quote.get("api_url"), "raw response")]),
            ])
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Betting lines</p>
  <h1>Outside prices only — never Hotspawn</h1>
  <p class="lede">Pinnacle's own public guest response is read first ({len(market.get('quotes', []))} CS2
  moneylines this run, mode <code>{esc(market.get('mode'))}</code>); other public listings are read second
  ({len(secondary.get('quotes', []))} rows, mode <code>{esc(secondary.get('mode'))}</code>) and always labelled
  secondary. Equal-pair placeholders are rejected on sight.</p>
</section>
<section>
  <h2>Prices read this snapshot</h2>
  {table(["Match", "Source", "Decimal odds A / B", "De-vigged probability", "Read at", "Source link"], body)}
  <p class="muted small">De-vig is proportional: <code>p = (1/o) / Σ(1/o)</code>. A missing line is left
  blank and shows in <a href="flagged.html">Flagged for review</a>.</p>
</section>
"""


def render_own_lines(rows: list[dict], meta: dict) -> str:
    body = []
    for row in sorted(rows, key=lambda r: (r["status"], r["lock_utc"] or "9999")):
        a, b = row["rating_a"], row["rating_b"]
        body.append([
            f'{esc(row["team_a"])} <span class="muted">vs</span> {esc(row["team_b"])}',
            f'{esc(a["vrs_name"] or "—")} {esc(a["vrs_rank"] or "")} <span class="muted">{esc(a["vrs_points"] or "not listed")}</span>',
            f'{esc(b["vrs_name"] or "—")} {esc(b["vrs_rank"] or "")} <span class="muted">{esc(b["vrs_points"] or "not listed")}</span>',
            esc(row["model_prob_a_pct"] or "—") + "% / " + esc(row["model_prob_b_pct"] or "—") + "%",
            esc(row["basis_tier"]) if row["basis_tier"] in (3, 4) else '<span class="muted">market basis used</span>',
            source_links([(a["vrs_url"], "A standings"), (a["vrs_details_url"], "A detail"),
                          (b["vrs_url"], "B standings"), (b["vrs_details_url"], "B detail")]),
        ])
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Our own lines</p>
  <h1>Originated from Valve's official standings</h1>
  <p class="lede">For fixtures no bookmaker prices, we originate the line ourselves from the official
  Valve Regional Standings points of both teams, through the points-to-probability relation Valve publish
  in <a href="{esc(HLTV_GLICKO_FILE)}" target="_blank" rel="noopener noreferrer">model/glicko.js</a>:
  <code>p = 1/(1+10^((Rb−Ra)/−400))</code>. Rows where a team is not listed at all use the published
  floor of the same official file as a conservative bound and are always flagged.</p>
</section>
<section>
  <h2>Rating inputs and originated probabilities</h2>
  {table(["Match", "Team A rating", "Team B rating", "Our probability A / B", "Basis tier", "Sources"], body)}
  <p class="muted small">Our line is an information value, not a price you can take. It is not calibrated to
  observed outcomes in this project — treat it as low confidence.</p>
</section>
"""


def render_tournaments(rows: list[dict], meta: dict) -> str:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["tournament"], []).append(row)
    blocks = []
    for name, group in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        open_group = [r for r in group if r["status"] == "open"]
        table_rows = []
        for row in sorted(group, key=lambda r: r["start_utc"] or "9999"):
            table_rows.append([
                esc((row["start_utc"] or "")[:16]) + "Z",
                f'{esc(row["team_a"])} vs {esc(row["team_b"])}',
                esc(row["pick"] or "—"),
                f'{esc(row["prob_a_pct"] or "—")}% / {esc(row["prob_b_pct"] or "—")}%',
                badge(TIER_SHORT[row["basis_tier"]], "tier-" + str(row["basis_tier"])),
                source_links([(row["hotspawn_match_url"] or row["hotspawn_pickem_url"], "Hotspawn")] +
                             [(u, l) for u, l in row["basis_sources"][:1]]),
            ])
        blocks.append(f"""<section class="panel">
  <h2>{esc(name)} <span class="muted small">{len(group)} fixtures · {len(open_group)} open</span></h2>
  {table(["Start (UTC)", "Match", "Pick", "Probabilities", "Basis", "Sources"], table_rows)}
</section>""")
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Tournaments</p>
  <h1>Every fixture, grouped by the tournament Hotspawn puts it in</h1>
  <p class="lede">{len(groups)} tournaments in the current payload.</p>
</section>
{''.join(blocks)}
"""


def render_coverage(rows: list[dict], inputs: dict, coverage: dict, meta: dict) -> str:
    pages = inputs["hotspawn"].get("pages", [])
    page_rows = []
    for page in pages:
        page_rows.append([
            link(page.get("url"), page.get("url") or ""),
            esc(page.get("http_status")),
            esc(page.get("fixture_count")),
            esc(page.get("lobby_header_matches_this_week") or "—"),
            esc(page.get("lobby_filter_all_tiers") or "—"),
            esc(page.get("rendered_card_count") or "—"),
            esc((page.get("sha256") or "")[:12]),
            esc(page.get("fetched_utc")),
        ])
    stale = [r for r in rows if not (parse_iso(r["lock_utc"]) and parse_iso(r["lock_utc"]) > meta["now"])]
    tier_counts: dict[str, int] = {}
    for row in rows:
        tier_counts[row["tier"] or "—"] = tier_counts.get(row["tier"] or "—", 0) + 1
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Coverage</p>
  <h1>What the Hotspawn payload actually contains</h1>
  <p class="lede">Hotspawn's Angular page ships its whole render state in <code>&lt;script id="ng-state"&gt;</code>.
  We read that state — fixture identity, tier, points and UTC lock/start epochs — and separately count the
  cards the page paints, so a disagreement is visible instead of hidden.</p>
</section>
<section>
  <h2>Pages read this snapshot</h2>
  {table(["Page", "HTTP", "Fixtures in payload", "Header “this week”", "Filter “All tiers”", "Rendered cards", "SHA-256", "Read at (UTC)"], page_rows)}
  <p class="muted small">Counts can legitimately differ: the header counts the pick'em week, the filter counts
  every tier, and the payload can retain fixtures the board no longer paints. Nothing here is inferred.</p>
</section>
<section>
  <h2>Slate breakdown</h2>
  <div class="stats">
    <div class="stat"><b>{coverage['total_fixtures']}</b><span>fixtures in the payload</span></div>
    <div class="stat"><b>{coverage['open_fixtures']}</b><span>open (lock ahead of the snapshot)</span></div>
    <div class="stat"><b>{coverage['locked_fixtures']}</b><span>locked or already played</span></div>
    <div class="stat"><b>{coverage['stale_fixtures']}</b><span>dated months ago (stale in the payload)</span></div>
  </div>
  {table(["Hotspawn tier", "Fixtures"], [[esc(k), str(v)] for k, v in sorted(tier_counts.items())])}
</section>
<section>
  <h2>Locked fixtures kept for the record ({len(stale)})</h2>
  {table(["Start (UTC)", "Match", "Tournament", "Pick in our records", "Flags"],
         [[esc((r["start_utc"] or "")[:16]) + "Z", f'{esc(r["team_a"])} vs {esc(r["team_b"])}',
           esc(r["tournament"]), esc(r["pick"] or "—"),
           " ".join(badge(f, "flag") for f in r["flags"]) or "—"] for r in stale])}
</section>
"""


def render_sources(inputs: dict, meta: dict) -> str:
    prov = inputs["provenance"].get("fetches", [])
    rows = []
    for fetch in prov:
        rows.append([
            link(fetch.get("url"), fetch.get("url") or ""),
            esc(fetch.get("status")),
            esc(fetch.get("bytes") or "—"),
            esc((fetch.get("sha256") or "")[:16] or "—"),
            esc(fetch.get("mode") or "—"),
            esc(fetch.get("fetched_utc")),
            esc(fetch.get("note") or ""),
        ])
    vrs = inputs["vrs"]
    registry = [
        ["Hotspawn Pick'em", "https://play.hotspawn.com/cs2-pickems",
         "Fixture identity, tier, points, UTC lock/start. Never a probability input."],
        ["Valve Regional Standings (official)", vrs.get("blob_url") or VRS_REPO,
         f"Official team points, standings dated {vrs.get('standings_date')}, commit {(vrs.get('commit') or '')[:10]}."],
        ["Valve glicko.js (official)", HLTV_GLICKO_FILE,
         "The points-to-probability relation we use for our own lines."],
        ["Pinnacle public guest endpoint", PINNACLE_CS2_PAGE,
         "Outside bookmaker moneyline read from the JSON pinnacle.com's own page loads."],
        ["HLTV", inputs["hltv_ranking"].get("canonical_url") or HLTV_RANKING,
         "World ranking, match pages, team rosters — reference only, never a probability input on its own."],
        ["EGamersWorld (bc.game prices)", EGW_MATCHES,
         "Secondary public listing of bookmaker prices; labelled secondary wherever used."],
    ]
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Sources</p>
  <h1>Where every number comes from</h1>
  <p class="lede">Each fetch is recorded with its URL, UTC read time, HTTP status, byte count and SHA-256.
  A refusal is published as a refusal — it is never replaced by a guess.</p>
</section>
<section>
  <h2>Source registry</h2>
  {table(["Source", "Where", "What it is used for"],
         [[esc(a), link(b, b), esc(c)] for a, b, c in registry])}
</section>
<section>
  <h2>Fetch log ({len(rows)} attempts)</h2>
  {table(["URL", "HTTP", "Bytes", "SHA-256 (short)", "Mode", "Read at (UTC)", "Note"], rows)}
</section>
"""


def render_methodology(rows: list[dict], meta: dict) -> str:
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Method</p>
  <h1>Selection rules, and what they cannot do</h1>
</section>
<section class="prose">
<h2>1. The slate</h2>
<p>Hotspawn's <code>/cs2-pickems</code>, <code>/lobby</code> and <code>/thp-pickems</code> pages are read in
full. The Angular render state (<code>&lt;script id="ng-state"&gt;</code>) carries every fixture the board
knows about, including rows it no longer paints. We keep fixture id, teams, tournament, tier, offered
points, stage and the exact UTC start/lock epochs. Crowd pick percentages and pick counts are dropped at
ingest and never stored. Fixtures whose lock time is in the past are labelled <em>locked</em> and kept only
for the record. Fixtures dated months ago are labelled stale, exactly as Hotspawn still lists them.</p>

<h2>2. Outside prices (the preferred basis)</h2>
<p>Whole-match moneylines only, read from public pages at the printed UTC minute. Pinnacle's public guest
response is the primary basis because it is the book's own price feed; aggregator listings (EGamersWorld's
bc.game prices) are a secondary basis and are labelled as such wherever used. Equal-pair placeholders
(1.80/1.80) are treated as “no market posted” and rejected. De-vig is proportional:
<code>p = (1/o) / Σ(1/o)</code>, and the overround is printed per row. A quote is only accepted when the
team pair matches the fixture in either order <em>and</em> the kickoff agrees within 15 minutes.</p>

<h2>3. Our own lines</h2>
<p>Where no outside line exists, we originate one from the official Valve Regional Standings points of both
teams: <code>p = 1/(1+10^((Rb−Ra)/−400))</code>, the relation Valve publish in
<a href="{esc(HLTV_GLICKO_FILE)}" target="_blank" rel="noopener noreferrer">model/glicko.js</a>. This line is
<strong>not calibrated</strong> in this project: a 90% favourite is not observed to win 90% of the time, so the
rows carry a low-confidence label and the arithmetic is printed. Ranks are matched to Hotspawn's spelling by
exact name, HLTV's spelling, a ≥4-of-5 roster match, or an evidence-linked rename — every match method is
printed with its evidence link.</p>

<h2>4. The fallback for low-tier fixtures no book prices</h2>
<p>Some fixtures on Hotspawn are below the level any bookmaker prices (recent examples: CCT play-in rounds,
Elisa BreakOut, Svenska CS-Ligan). For those:</p>
<ul>
  <li>If <strong>both</strong> teams are in the official standings, the line is originated as in §3.</li>
  <li>If <strong>one</strong> team is listed and the other is absent from the entire official file, the absent
  team is bounded by the lowest published value in that same file — its ceiling, not its measured value.
  The favourite's probability from that bound is a conservative estimate and the row is labelled
  <em>provisional</em> and flagged, every time.</li>
  <li>If <strong>neither</strong> team is listed, or the standings file itself could not be read, the row shows
  no pick and carries the flag for review. Nothing is filled in.</li>
</ul>

<h2>5. What this board does not claim</h2>
<ul>
  <li>It is not betting advice, and no number here is an offer you can take.</li>
  <li>Hotspawn's crowd percentages are not evidence and are never used.</li>
  <li>Coverage of outside prices is limited by which books publish CS2 at the time. When the total number of
  priced fixtures is low, that is a coverage fact, not a modelling choice.</li>
  <li>Ratings are from the newest official snapshot Valve publish (weekly). The file's own date is printed
  everywhere it is used.</li>
  <li>Where a source refused the read, the row shows the refusal. Automation bias is visible on
  <a href="flagged.html">Flagged for review</a> and on <a href="verification.html">Verification</a>.</li>
</ul>
</section>
"""


def render_flagged(rows: list[dict], inputs: dict, meta: dict) -> str:
    flagged = [r for r in rows if r["flags"]]
    body_rows = []
    for row in sorted(flagged, key=lambda r: (r["status"], r["lock_utc"] or "9999")):
        body_rows.append([
            f'<span class="nowrap">{esc((row["lock_utc"] or "")[:16])}Z</span>',
            f'{esc(row["team_a"])} vs {esc(row["team_b"])}<span class="cell-sub">{esc(row["tournament"])}</span>',
            " ".join(badge(f, "flag") for f in row["flags"]),
            esc(row["basis_detail"] or "—"),
            source_links([(row["hotspawn_match_url"] or row["hotspawn_pickem_url"], "Hotspawn")] +
                         [(u, l) for u, l in row["basis_sources"]]),
        ])
    code_rows = [[f'<code>{esc(code)}</code>', esc(text)] for code, text in sorted(FLAG_DEFS.items())]
    source_flags = [f for f in inputs["provenance"].get("fetches", [])
                    if f.get("status") not in (200, None) and f.get("status") != 200]
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Flagged for review</p>
  <h1>{len(flagged)} fixture rows carry a flag</h1>
  <p class="lede">These are published, not hidden, and they do not block publication. Each row keeps its
  source links so a human can check it in a minute.</p>
</section>
<section>
  <h2>Flagged fixture rows</h2>
  {table(["Lock (UTC)", "Match", "Flags", "Basis detail", "Sources"], body_rows)}
</section>
<section>
  <h2>Flag codes</h2>
  {table(["Code", "Meaning"], code_rows)}
</section>
<section>
  <h2>Source refusals and anomalies this run</h2>
  {table(["URL", "HTTP", "Mode", "Note"],
         [[link(f.get("url"), f.get("url") or ""), esc(f.get("status")), esc(f.get("mode")),
           esc(f.get("note") or "")] for f in source_flags]) if source_flags
   else '<p class="muted">Every source read this run returned HTTP 200 or a recorded capture.</p>'}
</section>
"""


def render_verification(rows: list[dict], inputs: dict, meta: dict, checks: list[dict]) -> str:
    open_rows = [r for r in rows if r["status"] == "open"]
    with_pick = [r for r in open_rows if r["pick"] and r["pick"] != "(no side — 50/50)"]
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Verification</p>
  <h1>What was checked, on which data, and what failed</h1>
  <p class="lede">{len(with_pick)} of {len(open_rows)} open fixtures carry a pick; every published number is
  recomputed from stored inputs at build time and re-checked by the test suite before anything is committed.</p>
</section>
<section>
  <h2>Checks run on this snapshot</h2>
  {table(["Check", "Result", "Detail"], [[esc(c["name"]),
      badge("pass" if c["passed"] else "failed", "ok" if c["passed"] else "bad"), esc(c["detail"])]
      for c in checks])}
</section>
<section>
  <h2>Reproduce it yourself</h2>
  <pre><code>python executive/collect.py   # reads Hotspawn, Valve, HLTV, Pinnacle (needs internet)
python executive/build.py     # offline rebuild of every page from executive/data/
python executive/tests.py     # invariants: sources present, maths re-derived, no crowd data</code></pre>
  <p class="muted small">A published row without a source link, a probability that does not re-derive from
  its stored quote, or any stored Hotspawn crowd value fails the build.</p>
</section>
"""


# ------------------------------------------------------------------ main
def main() -> int:
    parser = argparse.ArgumentParser(description="Build the executive board")
    parser.add_argument("--now", help="override the snapshot time (UTC ISO) for reproducible builds")
    args = parser.parse_args()
    now = parse_iso(args.now) or datetime.now(timezone.utc)

    inputs = load_inputs()
    fixtures = fixture_rows(inputs["hotspawn"])
    indexes = build_rating_indexes(inputs)

    ratings = {}
    for fixture in fixtures:
        for name in (fixture["team_a"], fixture["team_b"]):
            if name and name not in ratings:
                ratings[name] = team_record(name, inputs, indexes)

    market_quotes = inputs["pinnacle"].get("quotes", [])
    secondary_quotes = inputs["secondary"].get("quotes", [])

    rows = []
    for fixture in fixtures:
        market = assigned_quotes(fixture, market_quotes)
        secondary = assigned_quotes(fixture, secondary_quotes)
        hltv = hltv_link_for(fixture, ratings, inputs, indexes)
        # A second, independent way to reach the HLTV match page: the team pages the collector read.
        scheduled = hltv_schedule_match(fixture, indexes, inputs.get("hltv_schedule"))
        if scheduled.get("hltv_match_url") and not hltv.get("hltv_match_url"):
            hltv = {"hltv_match_url": scheduled["hltv_match_url"],
                    "hltv_match_id": scheduled.get("hltv_match_id") or "",
                    "hltv_format": "", "hltv_event": scheduled.get("hltv_event_from_slug") or "",
                    "hltv_kickoff": ""}
        if scheduled:
            hltv["hltv_schedule"] = scheduled
        row = analyse(fixture, ratings, market, secondary, now, inputs["vrs"], hltv)
        row["_market"] = market
        row["_secondary"] = secondary
        rows.append(row)

    # first-seen bookkeeping: never relabel an old fixture as new
    previous = {str(k): v for k, v in (inputs["previous"].get("fixtures") or {}).items()}
    for row in rows:
        prior = previous.get(row["match_id"]) or {}
        row["first_seen_utc"] = prior.get("first_seen_utc") or now.strftime("%Y-%m-%dT%H:%M:%SZ")
        if prior.get("first_seen_utc") and prior["first_seen_utc"] != row["first_seen_utc"]:
            if (parse_iso(row["start_utc"]) or now) - parse_iso(prior["first_seen_utc"]) > timedelta(days=1):
                row["flags"] = sorted(set(row["flags"] + ["FL-MULTI-DAY"]))
        row["last_verified_utc"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    open_rows = [r for r in rows if r["status"] == "open"]
    locked_rows = [r for r in rows if r["status"] != "open"]
    stale_rows = [r for r in rows
                  if parse_iso(r["start_utc"]) and parse_iso(r["start_utc"]) < now - timedelta(days=7)]
    capture_times = [parse_iso(v) for v in
                     [inputs["hotspawn"].get("fetched_utc"),
                      inputs["pinnacle"].get("captured_utc"), inputs["secondary"].get("captured_utc")] if v]
    capture_times = [t for t in capture_times if t]
    oldest = min(capture_times) if capture_times else None
    fresh_hours = (now - oldest).total_seconds() / 3600.0 if oldest else None
    meta = {
        "now": now,
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capture_utc": iso(oldest),
        "snapshot_age_text": (f"Snapshot is {fresh_hours:.1f} h old" if fresh_hours is not None
                              else "Snapshot age unknown"),
        "hotspawn_read_text": (f"{(inputs['hotspawn'].get('fetched_utc') or '')[:16]}Z "
                               f"({inputs['hotspawn'].get('mode')})"),
        "market_read_text": (
            f"{inputs['pinnacle'].get('mode') or 'not read'} read "
            f"{(inputs['pinnacle'].get('captured_utc') or inputs['pinnacle'].get('fetched_utc') or 'time unknown')[:16]}"
            f" ({len(market_quotes)} CS2 quotes)"),
        "vrs_read_text": (f"official standings {inputs['vrs'].get('standings_date') or 'not read'}"),
        "stale": bool(fresh_hours is not None and fresh_hours > STALE_HOURS),
    }
    coverage = {
        "total_fixtures": len(rows), "open_fixtures": len(open_rows), "locked_fixtures": len(locked_rows),
        "stale_fixtures": len(stale_rows),
        "open_with_pick": len([r for r in open_rows if r["pick"] and r["pick"] != "(no side — 50/50)"]),
        "open_market_basis": len([r for r in open_rows if r["basis_tier"] in (1, 2)]),
        "open_model_basis": len([r for r in open_rows if r["basis_tier"] in (3, 4)]),
        "open_provisional": len([r for r in open_rows if r["basis_tier"] == 4]),
        "open_no_pick": len([r for r in open_rows if not r["pick"] or r["pick"] == "(no side — 50/50)"]),
        "flagged_rows": len([r for r in rows if r["flags"]]),
        "unique_teams": len(ratings),
        "teams_resolved_official": len([r for r in ratings.values() if r["vrs_points"]]),
    }

    checks = [
        {"name": "Hotspawn payload read", "passed": bool(inputs["hotspawn"].get("fixtures")),
         "detail": f"{len(rows)} CS2 fixtures from {len(inputs['hotspawn'].get('pages', []))} pages, mode {inputs['hotspawn'].get('mode')}."},
        {"name": "Official standings read", "passed": bool(inputs["vrs"].get("rows")),
         "detail": f"{len(inputs['vrs'].get('rows', []))} teams, standings {inputs['vrs'].get('standings_date')}, mode {inputs['vrs'].get('mode')}."},
        {"name": "Outside prices read", "passed": bool(market_quotes or secondary_quotes),
         "detail": f"Pinnacle {len(market_quotes)} quotes ({inputs['pinnacle'].get('mode')}); secondary {len(secondary_quotes)} ({inputs['secondary'].get('mode')})."},
        {"name": "Pick coverage on open fixtures", "passed": coverage["open_no_pick"] == 0,
         "detail": f"{coverage['open_with_pick']}/{len(open_rows)} open fixtures have a pick; {coverage['open_no_pick']} flagged without one."},
        {"name": "No Hotspawn crowd value stored",
         "passed": not any(any(key in json.dumps(fixture) for key in ("picked_percent", "total_picks", "crowd"))
                           for fixture in inputs["hotspawn"].get("fixtures", [])),
         "detail": "No stored fixture object contains a crowd pick percentage, pick count or crowd field."},
        {"name": "Every analysed row has a source link", "passed": all(
            r["basis_sources"] or r["flags"] or r["hotspawn_match_url"] for r in rows),
         "detail": "Rows without a basis carry a flag; every published number names its input."},
        {"name": "Snapshot age", "passed": not meta["stale"],
         "detail": f"Oldest capture behind this board: {meta['capture_utc']} ({meta['snapshot_age_text']})."},
    ]

    # -------- write data
    analysis_rows = []
    for row in rows:
        record = {k: v for k, v in row.items() if not k.startswith("_")}
        a, b = row["rating_a"], row["rating_b"]
        record.update({
            "rating_a_source": a["vrs_url"], "rating_a_value": a["vrs_points"],
            "rating_a_method": a["match_method"], "rating_a_match_evidence": a["match_evidence_url"],
            "rating_b_source": b["vrs_url"], "rating_b_value": b["vrs_points"],
            "rating_b_method": b["match_method"], "rating_b_match_evidence": b["match_evidence_url"],
            "hltv_match_url": row.get("hltv_match_url", ""),
            "series_format_source": row.get("series_format_source", ""),
            "source_links": " | ".join(u for u, _ in row["basis_sources"] if u),
            "flags": ";".join(row["flags"]),
        })
        record.pop("rating_a", None)
        record.pop("rating_b", None)
        analysis_rows.append(record)
    fields = ["match_id", "status", "start_utc", "lock_utc", "tournament", "tier", "offered_points",
              "stage", "series_format", "series_format_source", "team_a", "team_b",
              "basis_tier", "basis_label", "basis_detail",
              "prob_a_pct", "prob_b_pct", "fair_odds_a", "fair_odds_b", "pick", "pick_prob_pct",
              "confidence", "market_source", "market_odds_a", "market_odds_b", "market_overround_pct",
              "market_captured_utc", "market_prob_a_pct", "market_prob_b_pct", "model_prob_a_pct",
              "model_prob_b_pct", "rating_a_value", "rating_a_source", "rating_a_method",
              "rating_a_match_evidence", "rating_b_value", "rating_b_source", "rating_b_method",
              "rating_b_match_evidence", "hotspawn_pickem_url", "hotspawn_match_url", "source_links",
              "first_seen_utc", "last_verified_utc", "flags"]
    write_csv(DATA / "analysis.csv", analysis_rows, fields)
    write_json(DATA / "analysis.json", {
        "generated_utc": meta["generated_utc"], "capture_utc": meta["capture_utc"],
        "coverage": coverage, "meta": {k: v for k, v in meta.items() if k != "now"},
        "fixtures": {str(r["match_id"]): {k: v for k, v in r.items() if not k.startswith("_")}
                     for r in rows},
    })
    write_csv(DATA / "ratings.csv", list(ratings.values()))
    write_csv(DATA / "fixtures.csv", [{k: v for k, v in f.items() if k != "seen_on"} for f in fixtures],
              ["match_id", "tournament", "tier", "offered_points", "stage", "series_format", "start_utc",
               "lock_utc", "lock_offset_sec", "source_status", "team_a", "team_b",
               "hotspawn_pickem_url", "hotspawn_match_url"])
    external_rows = []
    for row in rows:
        for quote in row["_market"] + row["_secondary"]:
            external_rows.append({
                "match_id": row["match_id"], "source_name": quote.get("source_name"),
                "source_role": quote.get("source_role"), "placeholder_rejected": quote.get("placeholder"),
                "odds_a": quote.get("odds_a_for_fixture") or quote.get("odds_a"),
                "odds_b": quote.get("odds_b_for_fixture") or quote.get("odds_b"),
                "overround_pct": f"{quote['overround_pct']:.4f}" if quote.get("overround_pct") else "",
                "devig_p_a_pct": pct(quote.get("p_a"), 4), "devig_p_b_pct": pct(quote.get("p_b"), 4),
                "captured_utc": quote.get("captured_utc"), "source_url": quote.get("source_url"),
                "api_url": quote.get("api_url"),
            })
    write_csv(DATA / "external_lines.csv", external_rows)
    flag_rows = []
    for row in rows:
        for code in row["flags"]:
            flag_rows.append({
                "match_id": row["match_id"], "teams": f'{row["team_a"]} vs {row["team_b"]}',
                "tournament": row["tournament"], "lock_utc": row["lock_utc"], "code": code,
                "meaning": FLAG_DEFS.get(code, ""),
                "detail": row["basis_detail"],
                "source_url": row["hotspawn_match_url"] or row["hotspawn_pickem_url"],
                "secondary_source_url": (row["basis_sources"][0][0] if row["basis_sources"] else ""),
            })
    write_csv(DATA / "flags.csv", flag_rows, ["match_id", "teams", "tournament", "lock_utc", "code",
                                              "meaning", "detail", "source_url", "secondary_source_url"])
    write_json(DATA / "summary.json", {"meta": {k: v for k, v in meta.items() if k != "now"},
                                       "coverage": coverage, "checks": checks})

    # -------- render
    pages = {
        "index.html": ("Executive summary", render_index(rows, meta, coverage)),
        "picks.html": ("All picks", render_picks(rows, meta)),
        "lines.html": ("Betting lines", render_lines(rows, inputs, meta)),
        "own-lines.html": ("Our own lines", render_own_lines(rows, meta)),
        "tournaments.html": ("Tournaments", render_tournaments(rows, meta)),
        "coverage.html": ("Coverage", render_coverage(rows, inputs, coverage, meta)),
        "sources.html": ("Sources", render_sources(inputs, meta)),
        "methodology.html": ("Method", render_methodology(rows, meta)),
        "flagged.html": ("Flagged for review", render_flagged(rows, inputs, meta)),
        "verification.html": ("Verification", render_verification(rows, inputs, meta, checks)),
    }
    for filename, (title, body) in pages.items():
        (EXEC / filename).write_text(page(title, body, meta, active=filename), encoding="utf-8")

    links = link_check()
    write_json(DATA / "linkcheck.json", links)
    print(json.dumps({"coverage": coverage, "checks": [c["name"] for c in checks if not c["passed"]],
                      "links": links}, indent=1))
    return 0


def link_check() -> dict:
    """Every local link on every page must resolve to a file that exists on disk."""
    broken, checked = [], 0
    for page_path in sorted(EXEC.glob("*.html")):
        text = page_path.read_text(encoding="utf-8")
        for href in re.findall(r'href="([^"#]+)(?:#[^"]*)?"', text):
            if href.startswith(("http://", "https://", "mailto:", "#", "data:")):
                continue
            checked += 1
            target = (page_path.parent / href).resolve()
            if not target.exists():
                broken.append({"page": page_path.name, "href": href})
    return {"checked": checked, "broken": broken, "ok": not broken}


if __name__ == "__main__":
    sys.exit(main())
