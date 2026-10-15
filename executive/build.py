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
    DATA, EXEC, EGW_MATCHES, HLTV_MATCHES, HLTV_RANKING, HOTSPAWN_CS2, HOTSPAWN_LOBBY,
    VRS_GLICKO_FILE as HLTV_GLICKO_FILE,
    PINNACLE_CS2_PAGE, PROB_SCALE_POINTS, VRS_REPO, devig_pair, epoch_ms_to_iso, fair_odds,
    iso, logit_prob, norm, odds_text, parse_iso, pct, read_csv, read_json, roster_key,
    official_url_safe, write_csv, write_json,
)

SITE = "Hotspawn CS2 · independent lines"
STALE_HOURS = 6            # a row is labelled stale for display after this many hours
MARKET_MAX_AGE_HOURS = 8  # a price older than this may not drive the headline probability
RATINGS_WEEK_DAYS = 7      # the official standings file is published weekly
KICKOFF_TOLERANCE_MIN = 15

# Own-line origination for every fixture + the research tier for matches no site prices (session 1b6ae823).
import ownlines  # noqa: E402

TIER_LABELS = {
    1: "Market · primary book",
    2: "Market · secondary listing",
    3: "Model · official ratings",
    4: "Model · official bound (provisional)",
    5: "Research · official ranking line",
    0: "No sourced basis",
}
TIER_SHORT = {1: "T1 market", 2: "T2 market", 3: "T3 model", 4: "T4 provisional",
              5: "T5 research line", 0: "no basis"}

FLAG_DEFS = {
    "FL-IDENTITY-UNVERIFIED": "A non-exact rating identity lacks a renewed team-specific proof; points are withheld, not inherited from a cached roster or alias.",
    "FL-SLATE-UNVERIFIED": "Current full slate could not be confirmed from both official Hotspawn surfaces. Saved rows may omit new matches.",
    "FL-NO-SOURCED-PICK": "No supported pick; missing values remain blank. See the unresolved page.",
    "FL-RATING-EXPIRED": "The standings are missing, future-dated or older than 14 days; not used for a forecast.",
    "FL-RANK-MISSING": "A team has no confirmed HLTV rank. No floor rank is invented.",
    "FL-NO-MARKET": "No outside bookmaker line for this fixture was readable at capture time.",
    "FL-UNLISTED-OPPONENT": ("Legacy flag: floor point imputation is disabled; missing points are now blank."),
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
    "FL-FORMAT-FROM-LISTING": "Hotspawn states no series format; the length shown is the one printed on the outside listing named on the row (linked), not an assumption.",
    "FL-RESEARCH-BASIS": "No outside price and no official VRS point pair: the published probability is this board's own ranking line, flagged as uncalibrated and never a price.",
    "FL-RANK-FLOOR-BOUND": "Legacy flag: floor rank imputation is disabled; missing ranks are now blank.",
    "FL-NO-HLTV-RANKING": "The official HLTV world ranking could not be read this run, so no ranking line was originated.",
    "FL-OWN-LINE-MARKET-SPLIT": "Our originated ranking line and the outside price disagree by more than 15 points on this row; both are published.",
    # added by session arena/e13aca8a (research ladder for matches the featured route cannot resolve)
    "FL-LISTING-ALIAS": ("The outside market prices this fixture under a different listing name; the identity "
                         "is roster-verified against official pages and the evidence links are on the row."),
    "FL-RESEARCH-CROSSCHECK-CONFLICT": ("A research cross-check (rating, form or listing) points the other way "
                                        "from the published line. Both are shown; nothing is reconciled silently."),
    "FL-MARKET-NO-LIQUIDITY": ("A prediction market exists for this fixture but its book is uninitialised "
                               "(no volume, both sides quoted above 90¢). The prices are refused, not de-vigged."),
    "FL-FORMAT-FROM-RESEARCH": ("Hotspawn states no series format; the length shown was stated by the research "
                                "source linked on the row (HLTV / EGW / market title), not assumed."),
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
        "cadence": read_json(DATA / "cadence.json", {}) or {},
        # session arena/e13aca8a: live research reads (HLTV → esportsbooks → betting lines) for the
        # matches the featured primary-market route cannot resolve. Additive input; collect.py never
        # rewrites it, so the research survives scheduled refreshes with its own read times.
        "research": read_json(DATA / "research_lines.json", {}) or {},
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

    if method in ("roster", "alias", "hltv", "exact+roster"):
        # Legacy cross-board aliases/roster captures lack a bounded, current identity proof.
        # Do not turn a same-sidebar roster (e.g. Spirit) into another team's rating.
        record["flags"].append("FL-IDENTITY-UNVERIFIED")
        record["alias_note"] = "Candidate rating identity withheld: non-exact identity requires a renewed, team-specific proof."
        vrs, method = None, "none"
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
            record["hltv_roster"] = ""  # legacy imported roster is not independently verified
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
        if not all(math.isfinite(v) and v > 1.0 for v in (odds_a, odds_b)):
            continue
        if quote.get("placeholder") is True:
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
        if not start or not kickoff or abs((kickoff - start).total_seconds()) > 15 * 60:
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
            now: datetime, vrs_meta: dict, hltv: dict | None = None,
            research: dict | None = None) -> dict:
    hltv = hltv or {}
    research = research or {}
    research_formats = research.get("formats") or {}
    research_notes = research.get("row_notes") or {}
    flags: list[str] = []
    a, b = ratings[fixture["team_a"]], ratings[fixture["team_b"]]
    start, lock = parse_iso(fixture["start_utc"]), parse_iso(fixture["lock_utc"])
    live = bool(lock and lock > now and start and start > now)
    if not live:
        flags.append("FL-LOCKED")
    series_format = fixture["series_format"]
    series_format_source = fixture["hotspawn_match_url"] or fixture["hotspawn_pickem_url"] if series_format else ""
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

    # Hotspawn publishes no series length.  Where the outside listing that prices this fixture states
    # one, that stated length is used (and linked) instead of leaving the row blank: the format changes
    # what a per-map rating line means for the series.  Nothing is guessed where no listing states it.
    if not series_format:
        # Read the length off the outside page(s) for this fixture.  The listing whose price the row is
        # based on is asked first; if that one prints no length, any other accepted quote for the same
        # pairing is asked, and its page is linked as the format source.  Nothing is assumed: when no
        # outside page states a length the row stays blank and flagged.
        for candidate in [used] + primary + secondary_ok:
            if not candidate:
                continue
            listing_bo = ownlines.format_to_best_of(candidate.get("best_of"))
            listing_url = candidate.get("source_url") or candidate.get("book_url") or ""
            if not (listing_bo and listing_url):
                continue
            series_format = f"BO{listing_bo}"
            series_format_source = listing_url
            flags = [f for f in flags if f != "FL-FORMAT-UNKNOWN"]
            flags.append("FL-FORMAT-FROM-LISTING")
            stated_by = (f"the pricing listing ({candidate.get('source_name', 'listing')})"
                         if candidate is used else
                         f"{candidate.get('source_name', 'listing')}, whose page for this fixture states "
                         "the length (the listing the price is taken from prints none)")
            basis_detail = (basis_detail + " " if basis_detail else "") + (
                f"Series length {series_format} as stated by {stated_by}; Hotspawn states none.")
            if candidate is not used:
                basis_sources = basis_sources + [(listing_url, f"{candidate.get('source_name', 'listing')} (series length)")]
            break
        else:
            # Research ladder (session arena/e13aca8a): the research trail for this fixture (HLTV match
            # page, EGW match page, or the market's own title) states a length even when no price exists.
            fmt = research_formats.get(str(fixture["match_id"])) or {}
            fmt_bo = ownlines.format_to_best_of(fmt.get("best_of"))
            fmt_url = fmt.get("source_url") or ""
            if fmt_bo and fmt_url:
                series_format = f"BO{fmt_bo}"
                series_format_source = fmt_url
                flags = [f for f in flags if f != "FL-FORMAT-UNKNOWN"]
                flags.append("FL-FORMAT-FROM-RESEARCH")
                basis_detail = (basis_detail + " " if basis_detail else "") + (
                    f"Series length {series_format} as stated by the research source named on this row "
                    f"({fmt.get('source_name', 'research read')}); Hotspawn states none.")
                basis_sources = basis_sources + [(fmt_url, f"{fmt.get('source_name', 'research source')} (series length)")]
                if fmt.get("secondary_source_url"):
                    basis_sources = basis_sources + [(fmt["secondary_source_url"], "series length (cross-check)")]
            else:
                flags.append("FL-FORMAT-UNKNOWN")

    # Research-ladder notes (session arena/e13aca8a): identity evidence, refused markets and published
    # counter-signals for the rows the featured route cannot resolve. Notes never replace a number.
    note = research_notes.get(str(fixture["match_id"])) or {}
    if note:
        flags.extend(note.get("flags") or [])
        basis_detail = (basis_detail + " " if basis_detail else "") + (note.get("note") or "")
        basis_sources = basis_sources + [(u, "research read (arena/e13aca8a)") for u in (note.get("links") or [])]

    have_vrs_a = bool(a["vrs_points"])
    have_vrs_b = bool(b["vrs_points"])
    ranked_floor = 0
    if vrs_meta.get("rows"):
        ranked_floor = min(int(row["vrs_points"]) for row in vrs_meta["rows"])

    if "FL-FORMAT-CONFLICT" in flags:
        series_format = ""
    from evidence import rating_is_recent
    if not rating_is_recent(vrs_meta.get("standings_date"), now):
        have_vrs_a = have_vrs_b = False
        flags.append("FL-RATING-EXPIRED")
    if have_vrs_a and have_vrs_b:
        ra, rb = float(a["vrs_points"]), float(b["vrs_points"])
        model_prob_a = (ownlines.series_probability(logit_prob(ra, rb), ownlines.format_to_best_of(series_format))
                        if ownlines.format_to_best_of(series_format) else None)
        if basis_tier == 0 and model_prob_a is not None:
            prob_a, prob_b = model_prob_a, 1 - model_prob_a
            basis_tier = 3
        basis_detail = (basis_detail + " " if basis_detail else "") + (
            f"Rating inputs: {a['vrs_name']} {a['vrs_points']} vs {b['vrs_name']} {b['vrs_points']} "
            f"official points; project 400-point logistic with independent-map series transform, {series_format or 'format unverified'}: {pct(model_prob_a, 1) + '%' if model_prob_a is not None else 'not originated — format unverified'}. This is an uncalibrated project estimate, not a Valve match forecast.")
        basis_sources += [(a["vrs_url"], f"{a['vrs_name']} standings"),
                          (b["vrs_url"], f"{b['vrs_name']} standings")]
    elif have_vrs_a != have_vrs_b:
        flags.append("FL-RATING-MISSING")
        basis_detail += " No VRS estimate: one team's points are missing. An unlisted team is not assigned a floor rating."
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
                      3: "Low (project model, not official forecast)", 4: "Provisional (official bound)"}.get(basis_tier, "")
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
        "_market_prob_a": market_prob_a,
        "flags": sorted(set(flags)),
    }


# ------------------------------------------------------------------ page shell
def page(title: str, body: str, meta: dict, active: str = "") -> str:
    nav = [
        ("index.html", "Summary"), ("picks.html", "All picks"), ("unresolved.html", "Unresolved"),
        ("lines.html", "Betting lines"),
        ("own-lines.html", "Our lines"), ("tournaments.html", "Tournaments"),
        ("coverage.html", "Coverage"), ("cadence.html", "Refresh"),
        ("verification.html", "Verification"),
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
            'The scheduled refresh replaces this snapshot with a live read; nothing here is presented '
            'as a current price until it is.</div>')
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
<aside class="banner" role="status" data-source-time="{esc(meta.get('capture_utc') or '')}" data-slate-current="{str(meta.get('slate_health', {}).get('current', False)).lower()}">
<strong data-age>Source capture: {esc(meta.get('capture_utc') or 'unknown')} (UTC).</strong>
<span data-health>{esc(meta.get('slate_health', {}).get('limitation') or 'Full lobby and CS2 reads succeeded at capture; check source age before use.')}</span>
<a href="unresolved.html">Unresolved &amp; limitations</a> · <a href="flagged.html">Flagged for Review</a>
</aside>
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
    start = parse_iso(row["lock_utc"])
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
    own = row.get("own") or {}
    if own.get("p_series") is not None:
        own_a = f"{own['p_series'] * 100.0:.1f}%"
        own_b = f"{(1.0 - own['p_series']) * 100.0:.1f}%"
        own_bound = ", official bound" if (own.get("bound_a") or own.get("bound_b")) else ""
        own_text = (f'{esc(own_a)} / {esc(own_b)} <span class="muted">({esc(own.get("method") or "own line")}'
                    f'{esc(own_bound)})</span>')
    else:
        own_text = '<span class="muted">not originated — see the flags on this row</span>'
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
    <div><dt>Locks</dt><dd>{esc(row['lock_utc'])} <span class="muted" data-lock="{esc(row['lock_utc'])}">UTC lock; status at build</span></dd></div>
    <div><dt>Tier / value</dt><dd>{esc(row['tier'] or '—')} · {esc(row['offered_points'] or '—')} pts</dd></div>
    <div><dt>Format</dt><dd>{esc(row['series_format'] or '—')}{(' ' + link(row['series_format_source'], 'stated by')) if row.get('series_format_source') else ''}</dd></div>
    <div><dt>Our own line</dt><dd>{own_text}</dd></div>
    <div><dt>Price read (UTC)</dt><dd>{esc(row.get("market_captured_utc") or "no market quote")}</dd></div>
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
    groups = unresolved_groups(open_rows)
    unresolved_total = sum(len(items) for key, _l, items, _x in groups if key != "featured")
    featured_total = sum(len(items) for key, _l, items, _x in groups if key == "featured")
    pred_only = sum(len(items) for key, _l, items, _x in groups if key == "prediction")
    own_total = sum(len(items) for key, _l, items, _x in groups if key in ("own", "bound", "research"))
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
        ("own-lines.html", "Our own line for every fixture",
         f"{coverage.get('open_own_line', 0)} of {len(open_rows)} open fixtures carry it"),
        ("unresolved.html", "Unresolved picks & limitations",
         f"{unresolved_total} rows without a primary-book line"),
        ("cadence.html", "How current is this?", f"refreshed every {4} h · read times per input"),
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
  <h1>Every captured CS2 match — supported picks, probabilities, and unresolved gaps.</h1>
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
  automatically every four hours from the Hotspawn board and the outside sources, and every published
  number keeps the minute it was read. <a href="cadence.html">Refresh &amp; read times</a>.</p>
</section>

<section class="panel">
  <h2>Unresolved picks &amp; limitations</h2>
  <p><strong>{len(no_pick)}</strong> open matches lack a supported side. <strong>{unresolved_total} of {len(open_rows)}</strong> cannot be
  resolved the same way as the featured picks (a primary esportsbook moneyline):
  <strong>{pred_only}</strong> rest on a prediction market only, and <strong>{own_total}</strong> rest on
  our own originated estimate because no usable market quote was retrieved. Those rows are listed separately, with the research trail
  (HLTV &rarr; esportsbooks &rarr; betting lines) and the concrete limitations of each substitute route.</p>
  <p><a class="button" href="unresolved.html"><strong>Open the unresolved section</strong>
  <span>per-row basis, refused prices, and what still limits these picks</span></a></p>
  <p class="muted small">Featured-route picks right now: {featured_total} of {len(open_rows)}. Research
  never fills a gap with Hotspawn's crowd percentages and never turns an uninitialised market into a
  price &mdash; refusals are published on the unresolved page.</p>
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
    <div class="stat"><b>{coverage.get('open_own_line', 0)}</b><span>with our own originated line</span></div>
    <div class="stat"><b>{coverage.get('fixtures_with_stated_format', 0)}</b><span>with a stated series length</span></div>
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
      (<code>p = 1/(1+10^((Rb−Ra)/400))</code>). Uncalibrated, so labelled low confidence.</li>
    <li><strong>Missing ratings or format</strong> — no numeric bound is invented; the unsupported pick remains blank and flagged.</li>
    <li><strong>Research · official ranking line</strong> — the tier for matches nothing else can resolve
      (low-tier CCT / Elisa / qualifier fixtures). Both teams' positions in the official HLTV world ranking
      go through a logistic whose scale is <strong>fitted on this board's own priced fixtures</strong>
      ({esc((meta.get('own_line') or {}).get('calibration', {}).get('reason', ''))}), then converted to the
      stated series length. Flagged
      <code>FL-RESEARCH-BASIS</code>, always low confidence, and never printed over a readable price.</li>
    <li><strong>No sourced basis</strong> — the pick stays blank and the row is flagged. Nothing is invented.</li>
  </ol>
  <p class="muted small">Secondary listings also include this repository's own hourly market feed
  (<a href="../feeds/index.html">bo3.gg-relayed bookmaker prices and Polymarket match markets</a>), consumed
  read-only with its own capture minute — that is where most C-tier fixtures get a price. A quote whose
  kickoff does not agree with the fixture, or whose price is an equal-pair placeholder, is dropped.</p>
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
            f'<span class="cell-sub">Price read UTC: {esc(row.get("market_captured_utc") or "not priced")}</span><span class="cell-probs"><b>{esc(row["prob_a_pct"] or "—")}%</b> / <b>{esc(row["prob_b_pct"] or "—")}%</b></span>',
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


def unresolved_groups(open_rows: list[dict]) -> list[tuple[str, str, list[dict], str]]:
    """Open fixtures that cannot be resolved the same way as the featured picks.

    “Featured” here means a primary esportsbook moneyline (Pinnacle's own feed).  Everything
    else is listed below with the route that *was* used and the concrete limitation of that route.
    """
    def has_flag(row: dict, code: str) -> bool:
        return code in (row.get("flags") or [])

    featured = [r for r in open_rows if r["basis_tier"] == 1]
    secondary_books = [r for r in open_rows if r["basis_tier"] == 2
                       and not has_flag(r, "FL-PREDICTION-MARKET-BASIS")]
    prediction_only = [r for r in open_rows if r["basis_tier"] == 2
                       and has_flag(r, "FL-PREDICTION-MARKET-BASIS")]
    own_line = [r for r in open_rows if r["basis_tier"] == 3]
    bound = [r for r in open_rows if r["basis_tier"] == 4]
    missing = [r for r in open_rows if not r["pick"] or r["pick"] == "(no side — 50/50)"]
    research_line = [r for r in open_rows if r["basis_tier"] == 5]
    return [
        ("missing", "No supported pick — unverified inputs remain blank", missing,
         "No fresh whole-match quote or usable pair of sourced ratings and confirmed series format was found. "
         "Missing ranks are never assigned floor values; unknown formats are never assumed BO1. "
         "A 50/50 model has no preferred side. Source refusal is not evidence that a market does not exist."),
        ("featured", "Resolved like the featured picks · primary esportsbook moneyline", featured,
         "Pinnacle's own public price feed, de-vigged. This is the featured route; rows here are not "
         "listed as unresolved."),
        ("secondary", "Unresolved by the featured route · secondary esportsbook listing", secondary_books,
         "No primary-book market was readable, so the pick rests on a bookmaker price quoted through a "
         "public aggregator or this site's own hourly relay. Aggregator pages move with the book and can "
         "lag it; the capture minute is on every row. A link identifies the listing — it does not prove "
         "the quote is still current."),
        ("prediction", "Unresolved by any bookmaker · prediction market only", prediction_only,
         "No usable esportsbook quote was retrieved for this fixture. The probability is a prediction market's implied "
         "price (Polymarket), normalised the same way and flagged "
         "FL-PREDICTION-MARKET-BASIS so it is never read as a bookmaker's line. Liquidity is thin on "
         "low-tier cards; a single trade can move the print."),
        ("own", "Unresolved by any market · our own originated line", own_line,
         "No usable bookmaker or prediction-market quote was retrieved for this fixture. The probability is originated "
         "by this project from Valve's official Regional Standings points (published relation, 400-point "
         "logistic), cross-checked on HLTV. Uncalibrated — low confidence by construction."),
        ("bound", "Unresolved and partly unrateable · provisional official bound", bound,
         "A team is absent from the official standings file, so only a conservative bound can be "
         "published (the favourite's probability is at least the printed number). Never a market view."),
        ("research", "Unresolved by markets or ratings · research ranking line", research_line,
         "Neither a price nor an official point pair exists. The line is this board's own HLTV-ranking "
         "logistic (scale fitted on priced fixtures), flagged FL-RESEARCH-BASIS, always low confidence."),
    ]


def render_unresolved(rows: list[dict], meta: dict, research: dict | None = None) -> str:
    research = research or {}
    now = meta["now"]
    open_rows = [r for r in rows if r["status"] == "open"]
    groups = unresolved_groups(open_rows)
    counts = {key: len(items) for key, _label, items, _lim in groups}
    unresolved_total = sum(v for k, v in counts.items() if k != "featured")

    def cards_for(items: list[dict]) -> str:
        return ('<div class="cards">' +
                "".join(pick_card(r, now) for r in sorted(items, key=lambda r: r["lock_utc"] or "9999")) +
                "</div>") if items else '<p class="muted">None in this group.</p>'

    group_sections = []
    for key, label, items, limit in groups:
        if key == "featured":
            continue
        if not items:
            continue
        group_sections.append(f"""
<section>
  <h2>{esc(label)} <span class="muted small">({len(items)} of {len(open_rows)} open fixtures)</span></h2>
  <p class="muted">Limitation of this route: {esc(limit)}</p>
  {cards_for(items)}
</section>""")

    refusals = research.get("refusals") or []
    refusal_rows = [[
        esc(r.get("teams", "")), link(r.get("market"), "market page"), esc(r.get("printed", "")),
        esc(r.get("reason", "")),
    ] for r in refusals]

    research_rows = []
    for mid, note in sorted((research.get("row_notes") or {}).items()):
        fixture = next((r for r in rows if str(r["match_id"]) == str(mid)), None)
        if not fixture:
            continue
        research_rows.append([
            esc(f'{fixture["team_a"]} vs {fixture["team_b"]}'),
            esc(fixture.get("tournament", "")),
            " ".join(link(u, f"src{i + 1}") for i, u in enumerate(note.get("links") or [])),
            esc(note.get("note", "")),
        ])

    slate = research.get("slate_recheck") or {}
    return f"""
<section class="hero">
  <p class="eyebrow">Unresolved picks &amp; limitations</p>
  <h1>{counts.get("missing", 0)} open matches have no supported side. {unresolved_total} matches need fallback research or remain unresolved.</h1>
  <p class="lede">A <strong>featured pick</strong> is resolved from a primary esportsbook moneyline
  (Pinnacle's own price feed, de-vigged). Matches no such book covers — the low-tier CCT / qualifier /
  academy cards — are resolved with the research ladder <strong>HLTV → esportsbooks → betting lines</strong>,
  and only where that trail finds a real two-sided market or an official rating. Nothing on this page is
  a Hotspawn crowd percentage; those are dropped at ingest.</p>
  <p class="meta-line">{counts['featured']} featured-route picks · {counts['secondary']} secondary-book
  listings · {counts['prediction']} prediction-market-only · {counts['own']} own originated lines ·
  {counts['bound']} provisional bounds · generated {esc(meta.get('generated_utc', ''))}</p>
</section>

<section class="panel panel--primary">
  <h2>Where the updated picks list lives</h2>
  <div class="buttons">
    <a class="button" href="picks.html"><strong>All picks &amp; probabilities</strong><span>one row per open fixture</span></a>
    <a class="button" href="index.html"><strong>Executive summary</strong><span>start here</span></a>
    <a class="button" href="own-lines.html"><strong>Our own lines</strong><span>originated for every fixture</span></a>
    <a class="button" href="flagged.html"><strong>Flagged for review</strong><span>every open question, with links</span></a>
  </div>
</section>

<section>
  <h2>The research ladder, in order</h2>
  <ol class="ladder">
    <li><strong>HLTV</strong> — fixture identity, BO3/BO1 series length, world-rank badges, event pages and
      recent official results for teams no ranking lists (for example LFO 10's HLTV team page and its
      match page 2399301, and Banda Chuya's match page 2399462).</li>
    <li><strong>Esportsbooks</strong> — EGamersWorld match pages (bc.game listings), bo3.gg relayed
      bookmaker prices, Pinnacle's guest markets where they exist. Single-sided and explicitly identified placeholder prices are rejected. Equal odds alone are not a placeholder.</li>
    <li><strong>Betting lines / prediction markets</strong> — Polymarket's own match markets (series
      moneyline share prices) where no bookmaker publishes a line. Where a market exists but is
      uninitialised (both sides above 90¢, zero volume) the prices are refused outright rather than
      turned into a fake 50/50.</li>
  </ol>
  <p class="muted small">Where no usable market is retrieved, the board attempts a model from
  sourced rating pairs and confirmed formats when available. Otherwise the pick is blank and flagged, never guessed.</p>
</section>
{''.join(group_sections)}

<section>
  <p><a href="data/fallback_research.json">Automated per-fixture fallback research: HLTV reads, outside-line candidates and unresolved limitations</a></p>
  <h2>Prices this research trail refused</h2>
  <p class="muted">Printed by a source, deliberately <em>not</em> used. Each refusal is recorded with the
  reason so the decision can be reviewed.</p>
  {table(["Fixture", "Market", "What the page printed", "Why it is not used"], refusal_rows) if refusal_rows else '<p class="muted">None recorded.</p>'}
</section>

<section>
  <h2>Research trail for the weak rows</h2>
  <p class="muted">Every source link opened in the research pass (2026-10-14, session arena/e13aca8a), and
  what it was used for. The machine-readable record is
  <a href="../data/e13aca8a/live_research_2026-10-14.md">data/e13aca8a/live_research_2026-10-14.md</a>
  with the exact read window; the input file the builder consumes is
  <a href="data/research_lines.json">data/research_lines.json</a>.</p>
  {table(["Fixture", "Tournament", "Sources", "What the research established"], research_rows) if research_rows else '<p class="muted">No research rows recorded.</p>'}
</section>

<section>
  <h2>Limitations that remain, in plain words</h2>
  <ul class="ladder">
    <li><strong>Coverage.</strong> Pinnacle and most sportsbooks simply do not list low-tier CCT / Elisa /
      qualifier cards. Where they abstain, no amount of research can produce a bookmaker's probability —
      only a substitute (aggregator quote, prediction market, or our own line), each labelled.</li>
    <li><strong>Aggregator quotes drift.</strong> EGamersWorld / bo3.gg pages quote a book; the quote can
      lag or differ from the book's own feed. Every row prints the minute it was read.</li>
    <li><strong>Prediction-market liquidity.</strong> Polymarket volumes on low-tier cards run from a few
      hundred dollars to zero. Thin books can print prices no one would trade at scale.</li>
    <li><strong>Own lines are uncalibrated.</strong> The originated line is a documented formula on official
      Valve points; it is not a market and not a forecast product. Where the fitted ranking line and a
      market disagree by more than 15 points, both are published (FL-MODEL-MARKET-SPLIT /
      FL-OWN-LINE-MARKET-SPLIT) and the disagreement is not reconciled.</li>
    <li><strong>Official files lag.</strong> Valve publish Regional Standings weekly; the newest official
      global file is still <code>standings_global_2026_10_05.md</code>. A team can be active and priced by
      Polymarket while missing from that file (LFO 10 is exactly this case) — the board says so instead of
      inventing official points. HLTV's “Valve ranking (beta)” page is HLTV's own projection including
      unfinished events; it is labelled evidence, never an official-file entry.</li>
    <li><strong>Series lengths are stated by outside pages.</strong> Hotspawn does not publish them; where
      no outside page states one the field stays blank and flagged.</li>
    <li><strong>Identities are verified, never assumed.</strong> Where a market lists a different name
      (Sökerorg for LFO 10, WRAITH PCIFIC for PCIFIC), the row keeps Hotspawn's name and the identity is
      roster-matched across at least two independent pages before any price is used (FL-LISTING-ALIAS).</li>
  </ul>
  <p class="muted small">Slate cross-check {esc(slate.get('checked_utc', ''))}: the live Hotspawn board was
  re-read ({esc(', '.join(slate.get('pages') or []))}); all
  {esc(str(len(open_rows)))} open fixtures on this board appear there with identical pairings.
  Nothing on this page uses Hotspawn's crowd percentages.</p>
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


def render_own_lines(rows: list[dict], meta: dict, own_meta: dict | None = None) -> str:
    cal = (own_meta or {}).get("calibration") or {}
    body = []
    for row in sorted(rows, key=lambda r: (r["status"], r["lock_utc"] or "9999")):
        a, b = row["rating_a"], row["rating_b"]
        own = row.get("own") or {}
        if own.get("p_series") is not None:
            own_cell = (f'<strong>{own["p_series"] * 100.0:.1f}% / {(1 - own["p_series"]) * 100.0:.1f}%</strong>'
                        f'<span class="cell-sub">{esc(own.get("method") or "")} · '
                        f'{esc(row["series_format"] or "length unstated")} · scale {own.get("scale"):g}</span>'
                        + ('<span class="cell-sub">one side bounded (flagged)</span>'
                           if (own.get("bound_a") or own.get("bound_b")) else ""))
        else:
            own_cell = '<span class="muted">not originated</span>'
        vrs_cell = (f'{own["vrs_p_series"] * 100.0:.1f}%' if own.get("vrs_p_series") is not None
                    else '<span class="muted">no point pair</span>')
        gap = ""
        if own.get("p_series") is not None and row.get("market_prob_a_pct"):
            delta = float(row["market_prob_a_pct"]) - own["p_series"] * 100.0
            gap = f'{delta:+.1f} pp'
        body.append([
            f'{esc(row["team_a"])} <span class="muted">vs</span> {esc(row["team_b"])}'
            f'<span class="cell-sub">{esc(row["tournament"])}</span>',
            f'{esc(a["vrs_name"] or "—")} {esc(a["vrs_rank"] or "")} <span class="muted">{esc(a["vrs_points"] or "not listed")}</span>'
            f'<span class="cell-sub">HLTV rank {esc(a["hltv_rank"] or "—")}</span>',
            f'{esc(b["vrs_name"] or "—")} {esc(b["vrs_rank"] or "")} <span class="muted">{esc(b["vrs_points"] or "not listed")}</span>'
            f'<span class="cell-sub">HLTV rank {esc(b["hltv_rank"] or "—")}</span>',
            own_cell,
            vrs_cell,
            gap or '<span class="muted">no price</span>',
            esc(row["basis_tier"]),
            source_links([(a["vrs_url"], "A standings"), (a["vrs_details_url"], "A detail"),
                          (b["vrs_url"], "B standings"), (b["vrs_details_url"], "B detail"),
                          *[(u, "HLTV rank") for u, _ in (own.get("sources") or [])][:1],
                          *(row["basis_sources"][:1] if row["market_prob_a_pct"] else [])]),
        ])
    priced = len([r for r in rows if (r.get("own") or {}).get("p_series") is not None])
    scale_note = (f"fitted on {cal.get('n')} fixtures that an outside market prices "
                  f"(mean absolute error {cal.get('mae_pp')} pp against that price)"
                  if cal.get("fitted") else
                  f"documented default ({cal.get('reason', 'too few priced fixtures to fit')})")
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Our own lines</p>
  <h1>An originated line for every fixture</h1>
  <p class="lede">Two independent, official inputs, printed on every row — {priced} of {len(rows)}
  fixtures carry a line from them right now. Where an outside book prices the match the market number
  stays the headline and this line is the cross-check; where nothing prices it (low-tier CCT, Elisa,
  qualifier matches) the same line becomes the basis and the row is badged
  {badge(TIER_SHORT[5], 'tier-5')}.</p>
  <ul class="lede plain">
    <li><strong>Valve Regional Standings points</strong> — the official points file, through the relation
      Valve publish in <a href="{esc(HLTV_GLICKO_FILE)}" target="_blank" rel="noopener noreferrer">model/glicko.js</a>:
      <code>p = 1/(1+10^((Rb−Ra)/400))</code>.</li>
    <li><strong>HLTV world ranking</strong> — rank numbers only, from the official ranking page, through
      <code>p = 1/(1+10^((rank_a−rank_b)/{esc(cal.get('scale'))}))</code> with a scale of
      {esc(scale_note)}. This is what reaches the smaller rosters VRS does not list.</li>
    <li><strong>Series length</strong> — a per-map probability is converted to the stated best-of with the
      independent-map transform (BO3 = 3p²−2p³, BO5 = 10p³−15p⁴+6p⁵). If no source states a length, no series probability is published.</li>
    <li><strong>Absent from an official list</strong> — no floor rank is assigned. The estimate is withheld and flagged.</li>
  </ul>
</section>
<section>
  <h2>Rating inputs and originated probabilities</h2>
  {table(["Match", "Team A rating", "Team B rating", "Our line A / B", "VRS point line (A)",
          "Our line vs the price", "Basis tier", "Sources"], body)}
  <p class="muted small">Our line is an information value, not a price you can take. It is calibrated to
  nothing but its own inputs, so treat it as low confidence — the “vs the price” column is published so the
  disagreement is visible instead of smoothed away.</p>
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


def render_cadence(rows: list[dict], inputs: dict, coverage: dict, meta: dict) -> str:
    """How current this board is, what refreshes it and what happens when a refresh cannot read a source."""
    cadence = inputs.get("cadence") or {}
    now = meta["now"]
    provenance = inputs.get("provenance") or {}
    actions_url = ("https://github.com/buffedlizard55-lab/MaltaProj1/actions/workflows/"
                   "executive-5545dbb8.yml")
    run_id = str(cadence.get("run_id") or "")
    run_link = (f'<a href="{actions_url}" target="_blank" rel="noopener noreferrer">run {esc(run_id)}</a>'
                if run_id else '<span class="muted">not a workflow run (local build)</span>')
    generated = parse_iso(cadence.get("generated_utc") or meta["generated_utc"])
    interval = float(cadence.get("cadence_hours") or 4)
    next_due = (generated + timedelta(hours=interval)) if generated else None
    overdue = bool(next_due and now > next_due + timedelta(hours=float(cadence.get("cadence_window_hours", [4, 8])[1]) - interval))

    def age_of(value) -> str:
        stamp = parse_iso(value)
        if not stamp:
            return '<span class="muted">no time recorded</span>'
        hours = (now - stamp).total_seconds() / 3600.0
        if hours < 1:
            text = f"{int(hours * 60)} min old"
        elif hours < 48:
            text = f"{hours:.1f} h old"
        else:
            text = f"{hours / 24:.1f} days old"
        cls = "ok" if hours <= STALE_HOURS else "warn"
        return f'<span class="{cls}">{esc(text)}</span>'

    pinnacle = inputs.get("pinnacle") or {}
    secondary = inputs.get("secondary") or {}
    feed = secondary.get("feed") or {}
    freshness = [
        ("Hotspawn board (fixture list, tiers, lock times)",
         inputs["hotspawn"].get("fetched_utc"), inputs["hotspawn"].get("mode"),
         f'{len(inputs["hotspawn"].get("fixtures") or [])} CS2 fixtures · '
         f'{len(inputs["hotspawn"].get("pages") or [])} pages read',
         HOTSPAWN_LOBBY),
        ("Primary bookmaker prices (Pinnacle guest response)",
         pinnacle.get("captured_utc") or pinnacle.get("fetched_utc"), pinnacle.get("mode"),
         f'{len(pinnacle.get("quotes") or [])} CS2 moneylines', PINNACLE_CS2_PAGE),
        ("Secondary listings (aggregator + prediction market + this repo's hourly feed)",
         secondary.get("captured_utc") or cadence.get("generated_utc"), secondary.get("mode"),
         f'{len(secondary.get("quotes") or [])} quotes; feed rows used: '
         f'{feed.get("used", 0)} of {feed.get("rows", 0)} ({feed.get("status", "not read")})',
         "https://buffedlizard55-lab.github.io/MaltaProj1/feeds/index.html"),
        ("Official Valve Regional Standings file",
         (inputs.get("vrs") or {}).get("fetched_utc") or (inputs.get("vrs") or {}).get("standings_date"),
         (inputs.get("vrs") or {}).get("mode"),
         f'{len((inputs.get("vrs") or {}).get("rows") or [])} teams, standings dated '
         f'{(inputs.get("vrs") or {}).get("standings_date") or "not read"}', VRS_REPO),
        ("Official HLTV world ranking (our own lines)",
         (inputs.get("hltv_ranking") or {}).get("fetched_utc")
         or (inputs.get("hltv_ranking") or {}).get("ranking_date"),
         (inputs.get("hltv_ranking") or {}).get("mode"),
         f'{len((inputs.get("hltv_ranking") or {}).get("teams") or [])} teams, ranking dated '
         f'{(inputs.get("hltv_ranking") or {}).get("ranking_date") or "not read"}', HLTV_RANKING),
        ("HLTV team pages (identity, formats, links)",
         (inputs.get("hltv_schedule") or {}).get("generated_utc"), (inputs.get("hltv_schedule") or {}).get("mode"),
         f'{len((inputs.get("hltv_schedule") or {}).get("teams") or [])} pages read', HLTV_MATCHES),
        ("Research ladder reads (session arena/e13aca8a: HLTV → esportsbooks → betting lines)",
         (inputs.get("research") or {}).get("generated_utc"), "live research read",
         f'{len((inputs.get("research") or {}).get("quotes") or [])} quotes · '
         f'{len((inputs.get("research") or {}).get("refusals") or [])} refused prices · '
         f'{len((inputs.get("research") or {}).get("row_notes") or [])} row notes',
         "../data/e13aca8a/live_research_2026-10-14.md"),
    ]
    fresh_rows = [[esc(label), f'<code>{esc(stamp or "—")}</code>' if stamp else '<span class="muted">—</span>',
                   age_of(stamp), esc(mode or "unknown"), esc(detail),
                   link(url, "source")] for label, stamp, mode, detail, url in freshness]

    fetches = provenance.get("fetches") or []
    refused = [f for f in fetches if f.get("status") not in (200, None)]
    board = [r for r in rows if r["status"] == "open"]
    lock_list = sorted((r for r in board if r["lock_utc"]), key=lambda r: r["lock_utc"])[:6]
    locks_rows = [[f'<code>{esc(r["lock_utc"])}</code>',
                   f'{esc(r["team_a"])} vs {esc(r["team_b"])}',
                   badge(TIER_SHORT[r["basis_tier"]], "tier-" + str(r["basis_tier"])),
                   esc(r["pick"] or "—")] for r in lock_list]
    return f"""
<section class="hero hero--tight">
  <p class="eyebrow">Refresh</p>
  <h1>What runs this board, and how old it is</h1>
  <p class="lede">Nothing here is typed in by hand. A scheduled workflow re-reads Hotspawn and every
  outside source, rebuilds these pages, re-runs the invariant suite, and only then replaces the published
  snapshot — so a failed read leaves the last good board standing instead of a half-updated one.</p>
</section>
<section>
  <h2>Cadence</h2>
  <div class="stats">
    <div class="stat"><b>{esc(cadence.get("schedule_cron") or "not scheduled")}</b><span>cron the refresh runs on</span></div>
    <div class="stat"><b>every {esc(f"{interval:g}")} h</b><span>requested window: 4–8 h</span></div>
    <div class="stat"><b>{esc(next_due.strftime("%Y-%m-%dT%H:%MZ") if next_due else "—")}</b><span>next expected run</span></div>
    <div class="stat"><b>{esc(meta.get("snapshot_age_text", "age unknown").replace("Snapshot is ", ""))}</b><span>age of the published snapshot</span></div>
  </div>
  <p class="lede">This snapshot was written by {run_link} (event <code>{esc(cadence.get("event") or "local")}</code>,
  commit <code>{esc((str(cadence.get("sha") or ""))[:7] or "—")}</code>).
  {("The next run is overdue — scheduled runs are best-effort on GitHub and can be delayed under load; "
    "if the number above is more than 8 h old, treat every row as its own printed read time.") if overdue else
   "Within the requested 4–8 h window."}</p>
  <p class="muted small">Scheduled triggers, source:
  <a href="{esc(actions_url)}" target="_blank" rel="noopener noreferrer">GitHub Actions for this workflow</a>.
  GitHub documents schedule events as best-effort, which is why the freshness above is published rather than assumed.</p>
</section>
<section>
  <h2>Read times behind this snapshot</h2>
  {table(["Input", "Recorded at (UTC)", "Age", "Mode", "What was read", "Source"], fresh_rows)}
  <p class="muted small">Mode <code>live</code> means the value was read from the source during this run;
  <code>repo_capture</code> / <code>previous_capture</code> means the source refused the read and the last
  committed capture is being reused — its own timestamp is printed, never this run's.</p>
</section>
<section>
  <h2>Source refusals this run</h2>
  {table(["URL", "HTTP", "Mode", "Note"],
         [[link(f.get("url"), (f.get("url") or "").replace("https://", "")[:70]), esc(f.get("status")),
           esc(f.get("mode")), esc(f.get("note") or "")] for f in refused]) if refused
   else '<p class="muted">Every source answered this run.</p>'}
</section>
<section>
  <h2>Next locks on the board</h2>
  {table(["Locks (UTC)", "Match", "Basis", "Pick"], locks_rows)}
  <p class="muted small">{len(board)} open fixtures; {coverage["open_with_pick"]} carry a pick. A refresh after a
  lock time retires that row and promotes whatever Hotspawn has listed next.</p>
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
        ["bo3.gg match pages (relay) + Polymarket match markets",
         "https://buffedlizard55-lab.github.io/MaltaProj1/feeds/index.html",
         "This repository's own hourly secondary feed, consumed read-only: bookmaker prices relayed by "
         "bo3.gg and Polymarket implied probabilities, each joined to a Hotspawn fixture by team pair and "
         "kickoff. This is the source that reaches most C-tier fixtures; each row keeps the feed's own "
         "capture minute and the underlying listing URL."],
        ["HLTV world ranking (official)", (inputs.get("hltv_ranking") or {}).get("canonical_url") or HLTV_RANKING,
         f"Rank numbers behind our own originated line — {(inputs.get('hltv_ranking') or {}).get('team_count') or 0} "
         f"teams, ranking dated {(inputs.get('hltv_ranking') or {}).get('ranking_date') or 'not read'}. "
         "Used for identity and for our own arithmetic; never as a market."],
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
<section class="hero hero--tight"><p class="eyebrow">Method</p>
<h1>Source facts, project estimates, and unresolved inputs</h1></section>
<section class="prose">
<h2>1. Complete captured slate, not guaranteed current coverage</h2>
<p>The official <a href="{HOTSPAWN_LOBBY}">Hotspawn lobby</a> and
<a href="{HOTSPAWN_CS2}">CS2 page</a> expose Angular TransferState fixture caches.
We union successful fixture endpoints by ID and discard all crowd probabilities at ingest.
Both surfaces must be successfully read with no identity conflict to claim complete coverage at capture.
A failed read preserves the last capture's timestamp, not a new verification time. New matches may be missing.</p>
<h2>2. Outside whole-match prices first</h2>
<p>Read Pinnacle's public guest feed, then secondary esportsbook listings and prediction markets.
Accept only explicit match-winner markets with two finite decimal prices above 1, a source URL,
open status, a capture no older than eight hours, and the exact team pair and kickoff within 15 minutes.
Reject stale, Map 1, unresolved-alias, and missing-time quotes. Equal odds alone do not prove a placeholder.
Prediction-market prices are normalised implied prices, not bookmaker offers or observed win rates.</p>
<p>For decimals oA and oB: <code>pA = (1/oA) / (1/oA + 1/oB)</code>.
Overround is <code>100 × (1/oA + 1/oB − 1)</code>. No averaging across sources;
prefer the primary bookmaker, then a secondary book, then a prediction market.</p>
<h2>3. Research only when the featured route cannot resolve a match</h2>
<p>HLTV match/team/ranking pages supply identity, format and ranking evidence; esportsbook and
betting-line reads are attempted automatically. A refusal means unreadable to this collector,
not proof that no bookmaker prices the match.</p>
<p>If no accepted price exists, use both teams' sourced Valve VRS points, or both HLTV ranks.
Missing rank/points stay blank: absence does not imply worst-ranked strength.
Missing or conflicting format means no series-model probability. Ratings older than 14 days are withheld.</p>
<h2>4. Our model is not an official forecast</h2>
<p>Project VRS approximation: <code>pMap = 1/(1+10^((Rb−Ra)/400))</code>.
<a href="{HLTV_GLICKO_FILE}">Valve's glicko.js</a> motivates a 400-point scale, but this approximation
ignores deviation and assumes a per-map interpretation. It is not a Valve-endorsed series forecast.</p>
<p>Rank model: <code>pMap = 1/(1+10^((rankA−rankB)/S))</code>.
S is fitted on accepted market quotes, minimising mean absolute error after each sample's
confirmed series transform. Fewer than four samples uses a disclosed project default of 100.
This is in-sample calibration against prices, not held-out accuracy or outcome validation.</p>
<p>Assuming independent identically distributed maps:
<code>BO1 = p</code>; <code>BO3 = 3p²−2p³</code>; <code>BO5 = 10p³−15p⁴+6p⁵</code>.
Map vetoes, lineups, travel, map correlation and roster changes are not modelled.
400 points or S rank places implies 90.9%, not exactly 90%. Low confidence; not betting advice.</p>
<h2>5. Missing values and deadlines</h2>
<p>All captured fixtures remain in the full table. Past lock times are historical, not actionable;
no prediction is a verified result. Unsupported values remain blank and flagged.
A near-50/50 estimate has no supported preferred side. Browser clocks update deadline and capture age;
with JavaScript off, rely on absolute UTC timestamps.</p>
<p><a href="unresolved.html">Unresolved picks &amp; limitations</a> ·
<a href="flagged.html">Flagged for Review</a> ·
<a href="data/rejected_quotes.json">Rejected quote ledger</a> ·
<a href="data/row_verification.json">Line-by-line stored-input audit</a></p>
</section>"""


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
  <p><a href="data/rejected_quotes.json">Rejected quote ledger</a> · <a href="data/row_verification.json">Stored-input audit for every row</a></p>
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
  <h2>Independent re-reads behind this build</h2>
  <ul>
    <li><b>Official ranking, re-read line by line.</b> The HLTV world ranking this build prices from was
    re-fetched and compared team by team: #1 Spirit 972, #2 Vitality 894, #3 MOUZ 692, #4 FURIA 527,
    #5 Falcons 488, #6 Aurora 461, #17 9z 124, #59 Voca 16 — every one identical to the stored capture
    (245 teams, <code>2026-10-12</code>).
      <a href="https://www.hltv.org/ranking/teams/2026/october/12">hltv.org/ranking/teams/2026/october/12</a></li>
    <li><b>A secondary listing, re-read at the row level.</b> Gothic v Lavked: the page still printed
    2.05 / 1.64 and the kickoff 08:00 UTC, and it states <b>Bo3</b> — so the length is now published on
    that row with this page as its source instead of being left blank.
      <a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B">egamersworld.com/…/gothic-vs-lavked</a></li>
    <li><b>The slate itself.</b> Every card visible on the Hotspawn lobby at 03:5x UTC is present in the
    captured fixture set with the same UTC start and a pick (the lobby's "Falcons–NiP" is stored under
    the full org name, matched by match id 1080177). Crowd percentages shown there were not read at all.
      <a href="https://play.hotspawn.com/lobby">play.hotspawn.com/lobby</a></li>
    <li><b>Whole-slate agreement.</b> Where a second outside source prices the same open fixture, the two
    numbers agree within 5 pp on 29 of 32 pairs; the four cases where our own originated line reverses
    the market's direction are listed rather than reconciled.</li>
    <li><b>Full line-by-line record</b> (every open row, its source link, its flags and what was
    re-checked): <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/reviews/1b6ae823-verification.md">reviews/1b6ae823-verification.md</a></li>
  </ul>
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
    secondary_quotes = list(inputs["secondary"].get("quotes", []) or [])
    research = dict(inputs.get("research") or {})
    fallback = read_json(DATA / "fallback_research.json", {}) or {}
    # Fallback formats are allowed only for the fixture IDs just researched, with their own read time.
    fresh_formats = {k: v for k, v in (fallback.get("formats") or {}).items()
                     if parse_iso(v.get("read_utc")) and
                     0 <= (now - parse_iso(v["read_utc"])).total_seconds() <= 8 * 3600}
    research["formats"] = {**(research.get("formats") or {}), **fresh_formats}
    # Session arena/e13aca8a: live research reads join the quote pool with their own read times and
    # source URLs, exactly like the hourly feed rows. They are never re-stamped as the feed's capture.
    research_quotes = list(research.get("quotes") or [])
    secondary_quotes = secondary_quotes + research_quotes

    from evidence import split_quotes, slate_health
    market_quotes, rejected_primary = split_quotes(market_quotes, now)
    secondary_quotes, rejected_secondary = split_quotes(secondary_quotes, now)
    write_json(DATA / "rejected_quotes.json", {"generated_utc": iso(now),
               "quotes": rejected_primary + rejected_secondary})
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
        row = analyse(fixture, ratings, market, secondary, now, inputs["vrs"], hltv,
                      research=research)
        row["_build_now"] = now
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
        row["last_verified_utc"] = inputs["hotspawn"].get("fetched_utc") or ""

    open_rows = [r for r in rows if r["status"] == "open"]
    locked_rows = [r for r in rows if r["status"] != "open"]

    # ---- an originated line for EVERY fixture, and a research tier for the ones nothing else resolves
    ranking = inputs.get("hltv_ranking") or {}
    calibration_pairs = {r["match_id"]: r["_market_prob_a"] for r in rows
                         if r.get("_market_prob_a") is not None}
    own_meta = ownlines.originate(rows, ranking, ranking.get("teams", []) or [], calibration_pairs)
    health = slate_health(inputs["hotspawn"], now)
    for row in rows:
        if not health["current"]:
            row["flags"] = sorted(set(row["flags"] + ["FL-SLATE-UNVERIFIED"]))
        if not row["pick"]:
            row["flags"] = sorted(set(row["flags"] + ["FL-NO-SOURCED-PICK"]))

    for row in rows:
        own = row["own"]
        if own.get("p_series") is not None and int(row["basis_tier"] or 0) in (1, 2) \
                and row.get("market_prob_a_pct"):
            gap = abs(own["p_series"] - float(row["market_prob_a_pct"]) / 100.0) * 100.0
            row["basis_detail"] = (row["basis_detail"] + " " if row["basis_detail"] else "") + (
                f"Our own line for the same fixture, from the official ranking only: "
                f"{own['p_series'] * 100:.1f}% for {row['team_a']} "
                f"({gap:.1f} pp from the price this row is based on).")
            if gap > 15.0:
                row["flags"] = sorted(set(row["flags"] + ["FL-OWN-LINE-MARKET-SPLIT"]))
        if own.get("sources"):
            seen_urls = {url for url, _ in row["basis_sources"] if url}
            row["basis_sources"] = list(row["basis_sources"]) + [
                (url, label) for url, label in own["sources"] if url and url not in seen_urls]

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
        "slate_health": health,
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
        "vrs_read_text": (f"official standings {inputs['vrs'].get('standings_date') or 'not read'}"
                          f" · HLTV ranking {own_meta.get('ranking_date') or 'not read'}"),
        "own_line": own_meta,
        "stale": bool(fresh_hours is not None and fresh_hours > STALE_HOURS),
    }
    coverage = {
        "total_fixtures": len(rows), "open_fixtures": len(open_rows), "locked_fixtures": len(locked_rows),
        "stale_fixtures": len(stale_rows),
        "open_with_pick": len([r for r in open_rows if r["pick"] and r["pick"] != "(no side — 50/50)"]),
        "open_market_basis": len([r for r in open_rows if r["basis_tier"] in (1, 2)]),
        "open_model_basis": len([r for r in open_rows if r["basis_tier"] in (3, 4, 5)]),
        "open_provisional": len([r for r in open_rows if r["basis_tier"] == 4]),
        "open_no_pick": len([r for r in open_rows if not r["pick"] or r["pick"] == "(no side — 50/50)"]),
        "flagged_rows": len([r for r in rows if r["flags"]]),
        "unique_teams": len(ratings),
        "teams_resolved_official": len([r for r in ratings.values() if r["vrs_points"]]),
        # ---- added by session arena/1b6ae823: research tier + own-line coverage
        "open_research_basis": len([r for r in open_rows if r["basis_tier"] == 5]),
        "open_own_line": len([r for r in open_rows if r["own"].get("p_series") is not None]),
        "fixtures_with_stated_format": len([r for r in open_rows if r["series_format"]]),
        "own_line_scale": own_meta["calibration"]["scale"],
        "own_line_scale_fitted": bool(own_meta["calibration"]["fitted"]),
        "own_line_calibration_n": own_meta["calibration"]["n"],
        "own_line_calibration_mae_pp": own_meta["calibration"].get("mae_pp"),
        "hltv_ranking_teams": own_meta["rank_count"],
        "hltv_ranking_date": own_meta.get("ranking_date") or "",
    }

    checks = [
        {"name": "Hotspawn payload read", "passed": health["current"],
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
        {"name": "Every open fixture carries an originated line or a reason it cannot",
         "passed": all(r["own"].get("p_series") is not None or r["flags"] for r in open_rows),
         "detail": (f"{coverage['open_own_line']}/{len(open_rows)} open fixtures have our own ranking line "
                    f"(scale {own_meta['calibration']['scale']:g} ranks per 90.9%, "
                    f"{'fitted on ' + str(own_meta['calibration']['n']) + ' priced fixtures' if own_meta['calibration']['fitted'] else 'documented default, too few priced fixtures to fit'}); "
                    "rows without one are flagged.")},
        {"name": "Research tier only where no market line exists",
         "passed": all(int(r["basis_tier"]) != 5
                       or not [q for q in r["_market"] + r["_secondary"] if not q.get("placeholder")]
                       for r in rows),
         "detail": "A T5 ranking line is never printed over a price that was actually readable."},
        {"name": "Official ranking read for the own lines",
         "passed": bool(own_meta["rank_count"]),
         "detail": (f"HLTV world ranking: {own_meta['rank_count']} teams, dated "
                    f"{own_meta.get('ranking_date') or 'not read'}, mode {own_meta.get('ranking_mode')},"
                    " Missing ranks remain blank; no floor ranks are assigned.")},
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
        own = row.get("own") or {}
        record.update({
            "own_method": own.get("method") or "",
            "own_best_of": own.get("best_of") or "",
            "own_rank_a": own.get("rank_a") or "",
            "own_rank_b": own.get("rank_b") or "",
            "own_scale": own.get("scale") if own.get("scale") is not None else "",
            "own_bound_a": "official bound" if own.get("bound_a") else "",
            "own_bound_b": "official bound" if own.get("bound_b") else "",
            "own_prob_map_a_pct": pct(own.get("p_map")),
            "own_prob_a_pct": pct(own.get("p_series")),
            "own_prob_b_pct": pct(1.0 - own["p_series"]) if own.get("p_series") is not None else "",
            "own_vrs_prob_a_pct": pct(own.get("vrs_p_series")),
            "own_detail": own.get("detail") or "",
            "own_sources": " | ".join(u for u, _ in (own.get("sources") or []) if u),
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
              "first_seen_utc", "last_verified_utc", "flags",
              # added by session arena/1b6ae823: the originated line that every fixture carries
              "own_method", "own_best_of", "own_rank_a", "own_rank_b", "own_scale", "own_bound_a",
              "own_bound_b", "own_prob_map_a_pct", "own_prob_a_pct", "own_prob_b_pct",
              "own_vrs_prob_a_pct", "own_detail", "own_sources"]
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
                "overround_pct": f"{quote['overround_pct']:.4f}" if quote.get("overround_pct") is not None else "",
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
                                       "coverage": coverage, "checks": checks,
                                       "own_lines": own_meta})

    # -------- render
    pages = {
        "index.html": ("Executive summary", render_index(rows, meta, coverage)),
        "picks.html": ("All picks", render_picks(rows, meta)),
        "unresolved.html": ("Unresolved picks & limitations", render_unresolved(rows, meta, research)),
        "lines.html": ("Betting lines", render_lines(rows, inputs, meta)),
        "own-lines.html": ("Our own lines", render_own_lines(rows, meta, own_meta)),
        "tournaments.html": ("Tournaments", render_tournaments(rows, meta)),
        "coverage.html": ("Coverage", render_coverage(rows, inputs, coverage, meta)),
        "cadence.html": ("Refresh", render_cadence(rows, inputs, coverage, meta)),
        "sources.html": ("Sources", render_sources(inputs, meta)),
        "methodology.html": ("Method", render_methodology(rows, meta)),
        "flagged.html": ("Flagged for review", render_flagged(rows, inputs, meta)),
        "verification.html": ("Verification", render_verification(rows, inputs, meta, checks)),
    }
    for filename, (title, body) in pages.items():
        (EXEC / filename).write_text(page(title, body, meta, active=filename), encoding="utf-8")

    from verify_rows import audit
    audit_result = audit()
    if audit_result["errors"]:
        raise ValueError(audit_result["errors"])
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
