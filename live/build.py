#!/usr/bin/env python3
"""Session arena/459ff624 — build the full-slate coverage board from a snapshot.

Input : live/data/snapshot.json          (written by live/collect.py, public sources only)
Output: live/data/slate.csv              one row per CS2 fixture in the Hotspawn Pick'em payload
        live/data/coverage.csv           per-tournament coverage counters
        live/data/flags.csv              every unverified/blank value, with its source link
        live/data/snapshot_meta.json     counters + as-of stamps for the pages
        live/*.html, live/style.css      mobile-first dashboard (no external assets)

Rules enforced here (the build fails rather than print an unverified number):
  * Hotspawn supplies fixture identity and times ONLY.  Crowd pick percentages are
    read for the audit page and are never written into the slate, never used as a
    probability, and never used to pick.
  * External probability: de-vig of a two-way bookmaker market,
        p_A = (1/o_A) / ((1/o_A) + (1/o_B)),   overround = (1/o_A + 1/o_B - 1) * 100.
  * Own line: Elo over Valve's official Regional Standings points,
        p_A = 1 / (1 + 10 ** (-(vrs_A - vrs_B) / 400)).
    A team missing from the official file gets a blank own line (never inferred).
  * Final probability = the external market when a usable market exists, else our own
    line, else blank.  The pick follows the final probability and is labelled with
    its basis.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "live"
DATA = LIVE / "data"

CLOSE_PICK_MARGIN = 2.0      # percentage points; below this the pick is "no confident pick"
DIVERGENCE_MARGIN = 12.5     # percentage points between market and our own line
START_TOLERANCE_MIN = 120    # quote start must be within this of the fixture start
PLACEHOLDER_PAIRS = {(1.8, 1.8)}   # aggregator placeholder, never a real price

# Explicit, sourced alias table used only to join a bookmaker's spelling to the
# Pick'em spelling.  Every entry is documented on the Flagged page.
ALIASES = {
    "wrotberry": "wbt",
    "wbt": "wbt",
    "roundsgg": "rounds",
    "rounds": "rounds",
    "ea copenhagen": "eac",
    "esport academy copenhagen": "eac",
    "eac": "eac",
    "ninjas in pyjamas": "nip",
    "nip": "nip",
    "phantom esports": "phantom",
    "phantom": "phantom",
    "bcgame esports": "bc.game",
    "bc.game esports": "bc.game",
    "bc game": "bc.game",
    "team envy": "envy",
    "heroic": "heroic",
    # Pinnacle spells two teams differently to the Pick'em board; both joins are checked against the
    # fixture start time by the tolerance rule before a row is allowed to use them.
    "pvision": "parivision",
    "bb": "betboom",
    "aurora gaming": "aurora",
}
ALIAS_SOURCES = {
    "wrotberry": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
    "roundsgg": "https://www.hltv.org/team/12676/rounds",
    "ea copenhagen": "https://www.hltv.org/team/11648/eac",
    "ninjas in pyjamas": "https://www.hltv.org/team/4411/ninjas-in-pyjamas",
    "pvision": "https://www.hltv.org/team/12467/parivision",
    "bb": "https://betboom.team/",
    "aurora gaming": "https://www.hltv.org/team/11861/aurora",
}


# ----------------------------------------------------------------- utilities
def norm(name: str) -> str:
    text = (name or "").lower().strip()
    text = re.sub(r"[\u2018\u2019\u201c\u201d]", "", text)
    text = re.sub(r"[^a-z0-9. ]+", " ", text)
    text = re.sub(r"^ex[\s\-]+", "", text)
    text = re.sub(r"\b(esports|esport|gaming|team)\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def parse_iso(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value.replace("Z", ""), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def devig(odds_a: float, odds_b: float):
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    total = ia + ib
    return round(100 * ia / total, 1), round(100 * ib / total, 1), round(100 * total - 100, 1)


def pct(value):
    return "" if value is None else f"{value:.1f}"


# ------------------------------------------------------------------- loading
def load():
    path = DATA / "snapshot.json"
    if not path.exists():
        raise SystemExit("live/data/snapshot.json missing — run live/collect.py first")
    return json.loads(path.read_text())


def vrs_index(snapshot):
    table = {}
    for team in snapshot.get("vrs", {}).get("teams", []):
        table.setdefault(norm(team["name"]), []).append(team)
    return table


def pick_vrs(entries):
    """Valve publishes one entry per roster; a name can appear twice. Use the higher-points
    entry (documented tie-break) and return the other(s) so the row can say so."""
    if not entries:
        return None, []
    ordered = sorted(entries, key=lambda entry: (-entry["points"], entry["vrs_rank"]))
    return ordered[0], ordered[1:]


def external_quotes(snapshot):
    quotes = []
    for quote in snapshot.get("pinnacle", {}).get("quotes", []):
        quotes.append({**quote, "source_label": "Pinnacle (direct bookmaker)"})
    for quote in snapshot.get("polymarket", {}).get("quotes", []):
        quotes.append({"bookmaker": "Polymarket",
                       "source_label": "Polymarket (prediction market, not a bookmaker)",
                       "kind": "prediction_market",
                       "market": "match_winner",
                       "team_a": quote["team_a"], "team_b": quote["team_b"],
                       "start_utc": quote.get("start_utc"),
                       "odds_a": quote["odds_a"], "odds_b": quote["odds_b"],
                       "observed_utc": quote.get("observed_utc"),
                       "source_url": quote.get("source_url"),
                       "note": quote.get("note")})
    for row in snapshot.get("egw", {}).get("detail", []):
        prices = row.get("prices") or []
        if len(prices) != 2:
            continue
        if tuple(sorted(prices)) in {tuple(sorted(p)) for p in PLACEHOLDER_PAIRS}:
            continue
        quotes.append({
            "bookmaker": "EGamersWorld",
            "source_label": "EGamersWorld (aggregated bookmaker prices)",
            "market": "match_winner",
            "team_a": row["team_a"], "team_b": row["team_b"],
            "start_utc": None,
            "odds_a": prices[0], "odds_b": prices[1],
            "observed_utc": snapshot.get("generated_utc"),
            "source_url": row["url"],
            "note": "Two-way decimal pair read from the public match page.",
        })
    return quotes


def build_rows(snapshot):
    now = parse_iso(snapshot["generated_utc"])
    vrs = vrs_index(snapshot)
    hltv_ranks = {k.lower(): v for k, v in (snapshot.get("hltv", {}).get("ranks") or {}).items()}
    quotes = external_quotes(snapshot)
    vrs_url = snapshot.get("vrs", {}).get("url")
    vrs_as_of = snapshot.get("vrs", {}).get("as_of")
    rows, flags = [], []

    for fixture in snapshot.get("fixtures", []):
        if (fixture.get("sport") or "").lower() != "cs2":
            continue
        start = parse_iso(fixture["start_utc"])
        lock = parse_iso(fixture.get("lock_utc"))
        pickable = bool(lock and now and lock > now)
        reason = None
        if not pickable:
            if lock and now and lock <= now:
                reason = "locked or already started at snapshot time"
            else:
                reason = "no lock time in the payload"
        if start and now and (now - start).days >= 3:
            reason = "listed in the payload but the start time is months in the past (stale listing)"

        row = {
            "match_id": fixture["match_id"],
            "start_utc": fixture["start_utc"],
            "lock_utc": fixture.get("lock_utc") or "",
            "pickable": "yes" if pickable else "no",
            "not_pickable_reason": reason or "",
            "tier": (fixture.get("tier") or "").upper(),
            "stage": fixture.get("stage") or "",
            "points": fixture.get("offered_points") or "",
            "competition": fixture.get("competition") or "",
            "team_a": fixture["team_a"], "team_b": fixture["team_b"],
            "hotspawn_url": fixture.get("hotspawn_match_url") or fixture.get("source_url") or "",
            "hotspawn_page": fixture.get("source_url") or "",
            "status": fixture.get("status") or "",
        }
        row_flags = []

        # ---- external bookmaker market
        candidates = []
        for quote in quotes:
            pair = {norm(quote["team_a"]), norm(quote["team_b"])}
            if pair != {norm(row["team_a"]), norm(row["team_b"])}:
                continue
            if quote["team_a"] is None or quote["team_b"] is None:
                continue
            if quote.get("kind") == "prediction_market":
                # a prediction market is only usable when it names a start time, so that a
                # tournament outright ("will X win the event?") can never be mistaken for a match
                if not quote.get("start_utc") or not start:
                    continue
            delta = None
            if quote.get("start_utc") and start:
                q_start = parse_iso(quote["start_utc"])
                if q_start:
                    delta = abs((q_start - start).total_seconds()) / 60
                    if delta > START_TOLERANCE_MIN:
                        continue
            candidates.append((quote, delta))
        if len(candidates) > 1:
            # prefer a direct bookmaker, then the closest start time
            def rank(item):
                quote_row, delta = item
                kind_rank = {"Pinnacle": 0, "EGamersWorld": 1, "Polymarket": 2}.get(
                    quote_row["bookmaker"], 3)
                return (kind_rank, delta if delta is not None else 1e9)

            candidates.sort(key=rank)
            if (candidates[0][1] is not None and candidates[1][1] is not None
                    and abs(candidates[0][1] - candidates[1][1]) < 1):
                row_flags.append("FL-03")
        if candidates:
            quote = candidates[0][0]
            team_a_norm = norm(row["team_a"]), norm(quote["team_a"])
            same_order = norm(quote["team_a"]) == norm(row["team_a"])
            odds_a = quote["odds_a"] if same_order else quote["odds_b"]
            odds_b = quote["odds_b"] if same_order else quote["odds_a"]
            if odds_a and odds_b:
                p_a, p_b, over = devig(odds_a, odds_b)
                row.update(ext_bookmaker=quote["source_label"],
                           ext_odds_a=f"{odds_a:.3f}", ext_odds_b=f"{odds_b:.3f}",
                           ext_overround_pct=pct(over), ext_p_a_pct=pct(p_a), ext_p_b_pct=pct(p_b),
                           ext_url=quote.get("source_url") or "",
                           ext_observed_utc=quote.get("observed_utc") or "",
                           ext_note=quote.get("note") or "")
                if normalise_key(row["team_a"]) != normalise_key(quote["team_a"] if same_order else quote["team_b"]):
                    row_flags.append("FL-10")
                if row["ext_url"] and "pinnacle.com/en/esports/matchups/highlights" in row["ext_url"]:
                    row_flags.append("FL-12")
                if quote.get("kind") == "prediction_market":
                    row_flags.append("FL-25")
        if not row.get("ext_p_a_pct"):
            row_flags.append("FL-01")
            row.update(ext_bookmaker="", ext_odds_a="", ext_odds_b="", ext_overround_pct="",
                       ext_p_a_pct="", ext_p_b_pct="", ext_url="", ext_observed_utc="", ext_note="")

        # ---- our own line from Valve's official standings
        va, va_alt = pick_vrs(vrs.get(norm(row["team_a"])))
        vb, vb_alt = pick_vrs(vrs.get(norm(row["team_b"])))
        if va_alt or vb_alt:
            row_flags.append("FL-26")
        row["vrs_alt_a"] = "; ".join(f"#{e['vrs_rank']} ({int(e['points'])} pts)" for e in va_alt)
        row["vrs_alt_b"] = "; ".join(f"#{e['vrs_rank']} ({int(e['points'])} pts)" for e in vb_alt)
        if va and vb:
            pts_a, pts_b = va["points"], vb["points"]
            p_a = 100.0 / (1.0 + 10 ** (-(pts_a - pts_b) / 400.0))
            row.update(own_p_a_pct=pct(round(p_a, 1)), own_p_b_pct=pct(round(100 - p_a, 1)),
                       vrs_points_a=int(pts_a), vrs_points_b=int(pts_b),
                       vrs_rank_a=va["vrs_rank"], vrs_rank_b=vb["vrs_rank"],
                       vrs_url=vrs_url or "", vrs_as_of=vrs_as_of or "",
                       own_basis="Elo over Valve Regional Standings points, scale 400")
        else:
            missing = [name for name, found in ((row["team_a"], va), (row["team_b"], vb)) if not found]
            if not missing:
                missing = ["a duplicate Valve roster entry left no usable line"]
            row_flags.append("FL-02")
            row.update(own_p_a_pct="", own_p_b_pct="",
                       vrs_points_a=int(va["points"]) if va else "", vrs_points_b=int(vb["points"]) if vb else "",
                       vrs_rank_a=va["vrs_rank"] if va else "", vrs_rank_b=vb["vrs_rank"] if vb else "",
                       vrs_url=vrs_url or "", vrs_as_of=vrs_as_of or "",
                       own_basis="", own_missing=", ".join(missing))
        hltv_a, hltv_b = hltv_ranks.get(row["team_a"].lower()), hltv_ranks.get(row["team_b"].lower())
        row["hltv_rank_a"] = hltv_a or ""
        row["hltv_rank_b"] = hltv_b or ""
        row["hltv_url"] = snapshot.get("hltv", {}).get("url") or ""

        # ---- final probability, pick and divergence
        if row.get("ext_p_a_pct"):
            row["final_p_a_pct"], row["final_p_b_pct"] = row["ext_p_a_pct"], row["ext_p_b_pct"]
            row["probability_source"] = "external market (de-vigged)"
        elif row.get("own_p_a_pct"):
            row["final_p_a_pct"], row["final_p_b_pct"] = row["own_p_a_pct"], row["own_p_b_pct"]
            row["probability_source"] = "our own line (Valve VRS)"
            row_flags.append("FL-13")
        else:
            row.update(final_p_a_pct="", final_p_b_pct="", probability_source="",
                       pick="", pick_pct="", pick_basis="")
            row_flags.append("FL-04")
        if row.get("final_p_a_pct"):
            p_a, p_b = float(row["final_p_a_pct"]), float(row["final_p_b_pct"])
            if abs(p_a - p_b) < CLOSE_PICK_MARGIN:
                row.update(pick="No confident pick", pick_pct="", pick_basis="too close to call")
            else:
                winner = row["team_a"] if p_a > p_b else row["team_b"]
                row.update(pick=winner, pick_pct=f"{max(p_a, p_b):.1f}",
                           pick_basis=row["probability_source"])
            if row.get("own_p_a_pct") and row.get("ext_p_a_pct"):
                if abs(float(row["ext_p_a_pct"]) - float(row["own_p_a_pct"])) >= DIVERGENCE_MARGIN:
                    row_flags.append("FL-11")
        row["flags"] = ";".join(dict.fromkeys(row_flags))
        rows.append(row)

    rows.sort(key=lambda r: (r["start_utc"], r["match_id"]))
    return rows


def normalise_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


# ------------------------------------------------------------------ flag text
FLAG_TEXT = {
    "FL-01": ("No verified external bookmaker price for this fixture at snapshot time. "
              "The probability column falls back to our own line when it exists; otherwise it stays blank.",
              "https://egamersworld.com/counterstrike/matches"),
    "FL-02": ("At least one team is absent from Valve's official Regional Standings file, so no own "
              "rating-based line is published for this fixture (value left blank, never inferred).",
              "https://github.com/ValveSoftware/counter-strike_regional_standings"),
    "FL-03": ("Two external sources priced this pair at nearly the same moment; the direct bookmaker was "
              "preferred and both are listed for manual review.", ""),
    "FL-04": ("Neither a bookmaker price nor a rating line could be sourced, so no probability and no pick "
              "are published for this fixture.", ""),
    "FL-10": ("The bookmaker spelling differs from the Pick'em spelling; the alias used for the join is "
              "documented on this page (see the alias table in the methodology).",
              "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2"),
    "FL-11": ("Our own line and the external market disagree by 12.5 points or more on the favourite. "
              "Both values are shown; the market drives the published pick.", ""),
    "FL-12": ("The quote has no per-match Pinnacle link in the public page markup, so the row links the "
              "public matchups page instead of a deep link that was never observed.", ""),
    "FL-13": ("Published probability comes from our own line only — no external bookmaker price was "
              "readable for this fixture.", ""),
    "FL-20": ("Hotspawn's own counters and the payload disagree about how many CS2 fixtures exist; the "
              "payload is used because it carries ids and times. Counters are listed for comparison.",
              "https://play.hotspawn.com/lobby"),
    "FL-21": ("The payload still lists fixtures whose start time is months in the past (June/July 2026) "
              "while their status stays 'scheduled'. They are kept out of the slate and listed on the "
              "coverage page instead.", "https://play.hotspawn.com/cs2-pickems"),
    "FL-22": ("A public source could not be read during this run; every field it would have filled stays "
              "blank.", ""),
    "FL-23": ("Only one external bookmaker is readable for this fixture. A single source is weaker "
              "evidence than an agreeing pair and is labelled as such.", ""),
    "FL-24": ("Hotspawn does not expose a per-match page link for this fixture in the payload or the "
              "rendered page, so the row links the board itself.", "https://play.hotspawn.com/lobby"),
    "FL-25": ("The only outside market readable for this fixture is a prediction market, not a "
              "bookmaker. Its price is labelled as such and is not de-vigged.",
              "https://polymarket.com/esports/cs2"),
    "FL-26": ("Valve's standings file lists this team name more than once (one entry per roster). The "
              "higher-points entry is used and the alternative entry is listed beside the row, so the "
              "choice can be checked by hand. Nothing is averaged and nothing is hidden.",
              "https://github.com/ValveSoftware/counter-strike_regional_standings"),
}


# Row-level findings about the current slate.  The stale June/July listings are documented once as
# FL-21; they must not inflate the "needs review" counts for values we simply have not collected.
SLATE_ONLY_FLAGS = {"FL-01", "FL-02", "FL-03", "FL-04", "FL-11", "FL-12", "FL-13", "FL-25", "FL-26"}


def collect_flags(rows, snapshot):
    flags = {}
    for row in rows:
        for flag_id in (row["flags"] or "").split(";"):
            if not flag_id:
                continue
            if flag_id in SLATE_ONLY_FLAGS and row["not_pickable_reason"].startswith("listed in the payload"):
                continue
            entry = flags.setdefault(flag_id, {"id": flag_id, "text": "", "source_url": "",
                                               "fixtures": [], "severity": "needs review"})
            entry["fixtures"].append(f"{row['team_a']} vs {row['team_b']}")
            if not entry["source_url"]:
                entry["source_url"] = row.get("ext_url") or row["hotspawn_url"]
    for flag_id, entry in flags.items():
        text, url = FLAG_TEXT.get(flag_id, ("Unclassified finding.", ""))
        entry["text"] = text
        entry["source_url"] = url or (rows[0]["hotspawn_url"] if rows else "")
    # source-level findings
    for page in snapshot.get("hotspawn_pages", []):
        if page.get("error"):
            flags.setdefault("FL-22", {"id": "FL-22", "text": FLAG_TEXT["FL-22"][0],
                                       "source_url": page["url"], "fixtures": [page["page"]],
                                       "severity": "needs review"})
    source_urls = {
        "Valve Regional Standings": "https://github.com/ValveSoftware/"
                                    "counter-strike_regional_standings",
        "Pinnacle": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
        "EGamersWorld": "https://egamersworld.com/counterstrike/matches",
        "HLTV ranking": "https://www.hltv.org/ranking/teams",
    }
    for source, payload in (("Valve Regional Standings", snapshot.get("vrs", {})),
                            ("Pinnacle", snapshot.get("pinnacle", {})),
                            ("EGamersWorld", snapshot.get("egw", {})),
                            ("HLTV ranking", snapshot.get("hltv", {}))):
        if payload.get("status") != "observed":
            entry = flags.setdefault("FL-22", {"id": "FL-22", "text": FLAG_TEXT["FL-22"][0],
                                               "source_url": payload.get("url")
                                               or source_urls.get(source, ""),
                                               "fixtures": [], "severity": "needs review"})
            if not entry["source_url"]:
                entry["source_url"] = source_urls.get(source, "")
            entry["fixtures"].append(source)
    weeks = snapshot.get("week_text")
    pickable = [r for r in rows if r["pickable"] == "yes"]
    cs2_total = len(rows)
    if weeks:
        listed = int(re.search(r"\d+", weeks).group(0))
        if listed != cs2_total:
            flags.setdefault("FL-20", {"id": "FL-20", "text": FLAG_TEXT["FL-20"][0],
                                       "source_url": "https://play.hotspawn.com/lobby",
                                       "fixtures": [], "severity": "informational"})
            flags["FL-20"]["fixtures"].append(
                f"board says {listed} this week; the payload carries {cs2_total} CS2 fixtures "
                f"({len(pickable)} still open)")
    stale = [r for r in rows if r["not_pickable_reason"].startswith("listed in the payload")]
    if stale:
        flags.setdefault("FL-21", {"id": "FL-21", "text": FLAG_TEXT["FL-21"][0],
                                   "source_url": "https://play.hotspawn.com/cs2-pickems",
                                   "fixtures": [f"{r['team_a']} vs {r['team_b']} ({r['start_utc']})"
                                                for r in stale],
                                   "severity": "informational"})
    multi = [r for r in rows if r["pickable"] == "yes" and r.get("ext_p_a_pct")]
    if multi:
        flags.setdefault("FL-23", {"id": "FL-23", "text": FLAG_TEXT["FL-23"][0],
                                   "source_url": multi[0]["ext_url"], "fixtures": [
                                       f"{r['team_a']} vs {r['team_b']}" for r in multi][:25],
                                   "severity": "informational"})
    no_link = [r for r in rows if "www.hotspawn.com/matches" not in (r["hotspawn_url"] or "")]
    if no_link:
        flags.setdefault("FL-24", {"id": "FL-24", "text": FLAG_TEXT["FL-24"][0],
                                   "source_url": "https://play.hotspawn.com/lobby",
                                   "fixtures": [f"{r['team_a']} vs {r['team_b']}" for r in no_link],
                                   "severity": "informational"})
    fallback = (rows[0]["hotspawn_url"] if rows else "https://play.hotspawn.com/lobby")
    for entry in flags.values():
        if not (entry.get("source_url") or "").startswith("http"):
            entry["source_url"] = fallback
        if not entry.get("text"):
            entry["text"] = FLAG_TEXT.get(entry["id"], ("Unclassified finding.", ""))[0]
    return [flags[key] for key in sorted(flags)]


# -------------------------------------------------------------------- output
SLATE_COLUMNS = ["match_id", "start_utc", "lock_utc", "pickable", "not_pickable_reason", "tier",
                 "stage", "points", "competition", "team_a", "team_b", "status",
                 "hotspawn_url", "hotspawn_page", "ext_bookmaker", "ext_odds_a", "ext_odds_b",
                 "ext_overround_pct", "ext_p_a_pct", "ext_p_b_pct", "ext_url", "ext_observed_utc",
                 "own_p_a_pct", "own_p_b_pct", "own_basis", "vrs_points_a", "vrs_points_b",
                 "vrs_rank_a", "vrs_rank_b", "vrs_url", "vrs_as_of", "hltv_rank_a", "hltv_rank_b",
                 "hltv_url", "final_p_a_pct", "final_p_b_pct", "probability_source", "pick",
                 "pick_pct", "pick_basis", "flags"]


def write_csv(path: Path, columns, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def coverage_rows(rows):
    groups = {}
    for row in rows:
        key = row["competition"] or "(competition not in payload)"
        entry = groups.setdefault(key, {"competition": key, "fixtures": 0, "pickable": 0,
                                        "external": 0, "own": 0, "pick": 0, "blank": 0})
        entry["fixtures"] += 1
        if row["pickable"] == "yes":
            entry["pickable"] += 1
        if row.get("ext_p_a_pct"):
            entry["external"] += 1
        if row.get("own_p_a_pct"):
            entry["own"] += 1
        if row.get("pick") and row["pick"] != "No confident pick":
            entry["pick"] += 1
        if not row.get("final_p_a_pct"):
            entry["blank"] += 1
    return [groups[key] for key in sorted(groups)]


# ------------------------------------------------------------------- rendering
def link(url: str, label: str) -> str:
    if not url:
        return ""
    return (f'<a href="{escape(url, quote=True)}" target="_blank" '
            f'rel="noreferrer noopener">{escape(label)}</a>')


def page(title: str, body: str, active: str, meta: dict) -> str:
    nav = [("index.html", "Slate"), ("matches.html", "All rows"), ("coverage.html", "Coverage"),
           ("flagged.html", "Flagged for review"), ("sources.html", "Sources"),
           ("methodology.html", "Method")]
    links = "".join(
        '<a href="{href}"{cls}>{label}</a>'.format(
            href=href, cls=' class="active"' if href == active else "", label=label)
        for href, label in nav)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} · Hotspawn Pick'em live slate</title>
<link rel="stylesheet" href="style.css">
</head><body>
<header>
  <div class="wrap">
    <h1>{escape(title)}</h1>
    <p class="sub">Hotspawn Play Pick'em · CS2 · independent line analysis</p>
    <nav>{links}</nav>
  </div>
</header>
<main class="wrap">
{body}
<footer>
  <p>As of <b>{escape(meta['generated_utc'])}</b> (UTC). Fixture identity and times come from the
  Pick'em board's own server-rendered payload; probabilities come from outside bookmaker prices
  (de-vigged) and our own Valve-standings model. Hotspawn's crowd pick percentages are never used
  as a probability. Every value that could not be confirmed against an official source is left
  blank and listed on <a href="flagged.html">Flagged for review</a>.</p>
  <p><a href="../">← back to the repository hub</a> · <a href="../picks/">picks/</a> ·
  <a href="../today/">today/</a> · <a href="../docs/">docs/</a> ·
  <a href="../pickem/">pickem/</a> · <a href="../model/">model/</a></p>
</footer>
</main></body></html>
"""


def bar(p_a: str, p_b: str, team_a: str, team_b: str) -> str:
    if not p_a:
        return '<div class="bars empty"><span>no probability published for this fixture</span></div>'
    a = float(p_a)
    return (f'<div class="bars"><div class="bar a" style="width:{a:.1f}%">'
            f'<span>{escape(team_a)} {p_a}%</span></div>'
            f'<div class="bar b" style="width:{100 - a:.1f}%">'
            f'<span>{escape(team_b)} {p_b}%</span></div></div>')


def fixture_card(row, meta, published=None) -> str:
    pick = row.get("pick") or ""
    pick_class = "pick" if pick and pick != "No confident pick" else "pick none"
    pick_html = (f'<span class="{pick_class}">PICK: {escape(pick)}{" " + row["pick_pct"] + "%" if row.get("pick_pct") else ""}</span>'
                 if pick else '<span class="pick none">NO PICK — no verified line</span>')
    sources = [link(row["hotspawn_url"], "Hotspawn fixture")]
    if row.get("ext_url"):
        sources.append(link(row["ext_url"], row.get("ext_bookmaker") or "external market"))
    if row.get("vrs_url"):
        sources.append(link(row["vrs_url"], f"Valve VRS {row.get('vrs_as_of') or ''}".strip()))
    if row.get("hltv_url"):
        sources.append(link(row["hltv_url"], "HLTV ranking"))
    flag_ids = [f for f in (row["flags"] or "").split(";") if f]
    flag_html = ""
    if flag_ids:
        flag_html = ('<div class="flags">' + " ".join(
            flag_markup(f, published) for f in flag_ids) + "</div>")
    market = ("—" if not row.get("ext_p_a_pct")
              else f'{row["ext_p_a_pct"]}% / {row["ext_p_b_pct"]}% '
                   f'<span class="muted">@{row["ext_odds_a"]} / {row["ext_odds_b"]} '
                   f'overround {row["ext_overround_pct"]}%</span>')
    own = ("—" if not row.get("own_p_a_pct")
           else f'{row["own_p_a_pct"]}% / {row["own_p_b_pct"]}% '
                f'<span class="muted">VRS {row.get("vrs_points_a", "")} / {row.get("vrs_points_b", "")}</span>')
    return f"""<article class="card" data-tier="{escape(row['tier'])}" data-comp="{escape(row['competition'])}" data-ext="{'yes' if row.get('ext_p_a_pct') else 'no'}">
  <div class="cardhead">
    <div>
      <div class="comp">{escape(row['competition'] or 'competition not in payload')}
        <span class="tag">{escape(row['tier'] or '?')}</span>
        <span class="tag">{escape(str(row['points']) or '?')} pts</span></div>
      <div class="teams">{escape(row['team_a'])} <span class="vs">vs</span> {escape(row['team_b'])}</div>
      <div class="when">starts {escape(row['start_utc'])} · picks lock {escape(row['lock_utc'] or 'n/a')} UTC</div>
    </div>
    {pick_html}
  </div>
  {bar(row.get('final_p_a_pct',''), row.get('final_p_b_pct',''), row['team_a'], row['team_b'])}
  <dl class="detail">
    <dt>Headline probability</dt><dd>{escape(row.get('probability_source') or '—')}</dd>
    <dt>Outside bookmaker line (de-vigged)</dt><dd>{market}</dd>
    <dt>Our own line (Valve standings)</dt><dd>{own}</dd>
    <dt>HLTV world rank cross-check</dt><dd>{row.get('hltv_rank_a') or '—'} / {row.get('hltv_rank_b') or '—'}</dd>
    <dt>Sources</dt><dd>{' · '.join(sources)}</dd>
  </dl>
  {flag_html}
</article>"""


def render_index(rows, meta, flags, published=None) -> str:
    pickable = [r for r in rows if r["pickable"] == "yes"]
    cards = "\n".join(fixture_card(row, meta, published) for row in pickable)
    tiers = sorted({r["tier"] for r in pickable if r["tier"]})
    comps = sorted({r["competition"] for r in pickable if r["competition"]})
    tier_opts = "".join(f'<option value="{escape(t)}">{escape(t)}</option>' for t in tiers)
    comp_opts = "".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in comps)
    with_ext = sum(1 for r in pickable if r.get("ext_p_a_pct"))
    with_own = sum(1 for r in pickable if r.get("own_p_a_pct"))
    with_pick = sum(1 for r in pickable if r.get("pick") and r["pick"] != "No confident pick")
    body = f"""
<section class="counters">
  <div class="counter"><b>{len(rows)}</b><span>CS2 fixtures in the payload</span></div>
  <div class="counter"><b>{len(pickable)}</b><span>still open (pickable now)</span></div>
  <div class="counter"><b>{with_ext}</b><span>with an outside bookmaker line</span></div>
  <div class="counter"><b>{with_own}</b><span>with our own line</span></div>
  <div class="counter"><b>{with_pick}</b><span>with a pick</span></div>
  <div class="counter"><b>{len(flags)}</b><span>flagged items</span></div>
</section>
<p class="note">Every fixture the Pick'em board still allows a pick on is listed below, newest lock times last.
Cards are ordered by start time. Numbers are percentages for each team to win the match.
{"Hotspawn's own crowd percentages are deliberately not shown here — they are not a probability." if False else ""}</p>
<div class="filters">
  <label>Tier <select id="tierFilter"><option value="">all</option>{tier_opts}</select></label>
  <label>Tournament <select id="compFilter"><option value="">all</option>{comp_opts}</select></label>
  <label>Line <select id="lineFilter"><option value="">all</option><option value="yes">bookmaker line only</option><option value="no">no bookmaker line</option></select></label>
  <span id="shown" class="muted"></span>
</div>
<div id="cards">
{cards}
</div>
<script>
(function(){{
  var t=document.getElementById('tierFilter'),c=document.getElementById('compFilter'),
      l=document.getElementById('lineFilter'),cards=[].slice.call(document.querySelectorAll('.card')),
      shown=document.getElementById('shown');
  function apply(){{
    var n=0;
    cards.forEach(function(card){{
      var ok=(!t.value||card.dataset.tier===t.value)&&(!c.value||card.dataset.comp===c.value)&&(!l.value||card.dataset.ext===l.value);
      card.style.display=ok?'':'none'; if(ok)n++;
    }});
    shown.textContent=n+' of '+cards.length+' fixtures shown';
  }}
  [t,c,l].forEach(function(el){{el.addEventListener('change',apply);}});apply();
}})();
</script>"""
    return page("Live slate — every open CS2 Pick'em fixture", body, "index.html", meta)


def flag_markup(flag_id: str, published: set) -> str:
    """A flag reference is only a link when the Flagged page really publishes that section."""
    if flag_id in published:
        return f'<a class="flag" href="flagged.html#{flag_id}">{flag_id}</a>'
    return f'<span class="flag" title="recorded in the row data"> {flag_id}</span>'


def render_matches(rows, meta, published=None) -> str:
    head = ("<tr><th>Start (UTC)</th><th>Lock (UTC)</th><th>Pickable</th><th>Tier</th><th>Pts</th>"
            "<th>Tournament</th><th>Team A</th><th>Team B</th><th>Market %</th><th>Odds</th>"
            "<th>Over</th><th>Own %</th><th>Headline</th><th>Pick</th><th>Sources</th><th>Flags</th></tr>")
    out = []
    for row in rows:
        links = [link(row["hotspawn_url"], "Hotspawn")]
        if row.get("ext_url"):
            links.append(link(row["ext_url"], "Market"))
        if row.get("vrs_url"):
            links.append(link(row["vrs_url"], "VRS"))
        if row.get("hltv_url"):
            links.append(link(row["hltv_url"], "HLTV"))
        market_cell = (row["ext_p_a_pct"] + " / " + row["ext_p_b_pct"]) if row.get("ext_p_a_pct") else "—"
        odds_cell = (row["ext_odds_a"] + " / " + row["ext_odds_b"]) if row.get("ext_odds_a") else "—"
        own_cell = (row["own_p_a_pct"] + " / " + row["own_p_b_pct"]) if row.get("own_p_a_pct") else "—"
        if row.get("vrs_alt_a") or row.get("vrs_alt_b"):
            own_cell += " (also listed: " + "; ".join(
                part for part in (row.get("vrs_alt_a"), row.get("vrs_alt_b")) if part) + ")"
        
        headline_cell = row["probability_source"] if row.get("final_p_a_pct") else "—"
        flag_links = " ".join('<a href="flagged.html#%s">%s</a>' % (f, f)
                              for f in (row["flags"] or "").split(";") if f)
        pickable_cell = "yes" if row["pickable"] == "yes" else "no — " + row["not_pickable_reason"]
        row_html = "".join([
            '<tr class="%s">' % ("open" if row["pickable"] == "yes" else "closed"),
            '<td data-l="Start">%s</td>' % escape(row["start_utc"]),
            '<td data-l="Lock">%s</td>' % escape(row["lock_utc"] or "—"),
            '<td data-l="Pickable">%s</td>' % escape(pickable_cell),
            '<td data-l="Tier">%s</td>' % escape(row["tier"]),
            '<td data-l="Pts">%s</td>' % escape(str(row["points"])),
            '<td data-l="Tournament">%s</td>' % escape(row["competition"]),
            '<td data-l="Team A">%s</td>' % escape(row["team_a"]),
            '<td data-l="Team B">%s</td>' % escape(row["team_b"]),
            '<td data-l="Market %%">%s</td>' % market_cell,
            '<td data-l="Odds">%s</td>' % odds_cell,
            '<td data-l="Over">%s</td>' % (row["ext_overround_pct"] or "—"),
            '<td data-l="Own %%">%s</td>' % own_cell,
            '<td data-l="Headline">%s</td>' % escape(headline_cell),
            '<td data-l="Pick">%s</td>' % escape(row.get("pick") or "—"),
            '<td data-l="Sources">%s</td>' % " · ".join(links),
            '<td data-l="Flags">%s</td>' % (flag_links or "—"),
            "</tr>",
        ])
        out.append(row_html)
    body = """
<p class="note">Every CS2 fixture carried by the Pick'em payload, including the ones whose lock time has
passed and the stale June/July listings. Blank cells mean the value could not be confirmed against an
official source — nothing is inferred. Odds are decimal; "over" is the bookmaker overround in percent.</p>
<div class="tablewrap"><table class="grid">
<thead>%s</thead>
<tbody>%s</tbody></table></div>""" % (head, "".join(out))
    return page("All rows — full CS2 slate", body, "matches.html", meta)


def render_coverage(rows, meta, snapshot) -> str:
    coverage = coverage_rows(rows)
    head = ("<tr><th>Tournament</th><th>Fixtures</th><th>Still open</th><th>With bookmaker line</th>"
            "<th>With our own line</th><th>With a pick</th><th>Blank probability</th></tr>")
    body_rows = "".join(
        f"<tr><td>{escape(r['competition'])}</td><td>{r['fixtures']}</td><td>{r['pickable']}</td>"
        f"<td>{r['external']}</td><td>{r['own']}</td><td>{r['pick']}</td><td>{r['blank']}</td></tr>"
        for r in coverage)
    gaps = [r for r in rows if r["pickable"] == "yes" and not r.get("ext_p_a_pct")]
    gap_rows = "".join(
        f"<tr><td>{escape(r['team_a'])} vs {escape(r['team_b'])}</td><td>{escape(r['competition'])}</td>"
        f"<td>{escape(r['start_utc'])}</td>"
        f"<td>{'own line only' if r.get('own_p_a_pct') else 'no verified line'}</td>"
        f"<td>{link(r['hotspawn_url'], 'Hotspawn')} · {link('https://egamersworld.com/counterstrike/matches', 'EGamersWorld listing')}{' · ' + link(r['vrs_url'], 'Valve VRS') if r.get('vrs_url') else ''}</td></tr>"
        for r in gaps)
    stale = [r for r in rows if r["not_pickable_reason"].startswith("listed in the payload")]
    locked = [r for r in rows if r["pickable"] == "no" and not r["not_pickable_reason"].startswith("listed")]
    crowd_by_id = {f.get("match_id"): f for f in snapshot.get("fixtures", [])}
    sample = next((r for r in snapshot.get("fixtures", []) if r.get("payload_keys")), {})
    key_list = ", ".join(f"<code>{escape(k)}</code>" for k in sample.get("payload_keys", []))
    crowd_rows = "".join(
        "<tr><td>%s vs %s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            escape(r["team_a"]), escape(r["team_b"]), escape(r["start_utc"]),
            escape(str((crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_pct_a"))),
            escape(str((crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_pct_b"))),
            escape(str((crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_total_picks"))),
            escape(r.get("ext_p_a_pct") or r.get("own_p_a_pct") or "—"))
        for r in rows if r["pickable"] == "yes"
        if (crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_pct_a") is not None
        or (crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_pct_b") is not None)
    crowd_count = sum(1 for r in rows if r["pickable"] == "yes"
                      and (crowd_by_id.get(r["match_id"], {}) or {}).get("crowd_pct_a") is not None)
    counters = snapshot.get("hotspawn_pages", [])
    counter_rows = "".join(
        f"<tr><td>{escape(p['page'])}</td><td>{p['status']}</td><td>{p['state_rows']}</td>"
        f"<td>{p['cards']}</td><td>{escape(p.get('week_text') or '—')}</td>"
        f"<td>{escape(p.get('reset_text') or '—')}</td><td>{escape(p.get('error') or '—')}</td></tr>"
        for p in counters)
    body = f"""
<p class="note">The board's own counters are compared with the payload so that "full coverage" is
checkable rather than asserted. A card can only be picked before its lock time, so both sets are
counted separately.</p>
<h2>Board counters (read from the pages themselves)</h2>
<div class="tablewrap"><table class="grid"><thead><tr><th>Page</th><th>HTTP</th><th>Fixture records
in payload</th><th>Cards rendered</th><th>Header counter</th><th>Resets in</th><th>Read error</th>
</tr></thead><tbody>{counter_rows}</tbody></table></div>

<h2>Coverage by tournament</h2>
<div class="tablewrap"><table class="grid"><thead>{head}</thead><tbody>{body_rows}</tbody></table></div>

<h2>Open fixtures with no readable outside bookmaker line ({len(gaps)})</h2>
<p class="note">These are the honest gaps. Each row keeps a link to the board and to an outside
bookmaker listing so the price can be checked by hand; a value is never guessed to fill the cell.</p>
<div class="tablewrap"><table class="grid"><thead><tr><th>Fixture</th><th>Tournament</th><th>Start (UTC)</th>
<th>What we can publish</th><th>Check it yourself</th></tr></thead><tbody>{gap_rows}</tbody></table></div>

<h2>What the payload actually carries</h2>
<p class="note">Fixture records in the Pick'em transfer state expose these keys (sample of one CS2
record, key names only): {key_list}. The crowd pick share below is read from
<code>participants0_picked_percent</code> / <code>participants1_picked_percent</code>.</p>

<h2>Observed crowd pick share — audit only, never an input</h2>
<p class="note">Shown for the {crowd_count} fixture(s) still open at snapshot time (the board's own
vote counts on stale listings are meaningless).</p>
<p class="note">These numbers are what other players picked on the Hotspawn board. They are <b>not</b>
a probability, <b>not</b> an input to any model here and <b>not</b> a pick: they are published only so
the difference between crowd behaviour and the outside market/our own line can be audited. Every
probability elsewhere on this site comes from a bookmaker price or from Valve's official standings.</p>
<div class="tablewrap"><table class="grid"><thead><tr><th>Fixture</th><th>Start (UTC)</th>
<th>Crowd % team A</th><th>Crowd % team B</th><th>Votes (N)</th><th>Our published probability, team A</th>
</tr></thead><tbody>{crowd_rows or "<tr><td colspan='6'>no crowd fields present in this snapshot</td></tr>"}</tbody></table></div>

<h2>Listed but not pickable</h2>
<p class="note">{len(locked)} fixture(s) had already locked or started at snapshot time, and
{len(stale)} are stale listings the board still carries from June/July 2026. They are never given a
pick because a pick could not be changed any more.</p>
<div class="tablewrap"><table class="grid"><thead><tr><th>Fixture</th><th>Start (UTC)</th><th>Why it
is not pickable</th><th>Source</th></tr></thead><tbody>{''.join(f"<tr><td>{escape(r['team_a'])} vs {escape(r['team_b'])}</td><td>{escape(r['start_utc'])}</td><td>{escape(r['not_pickable_reason'])}</td><td>{link(r['hotspawn_url'], 'Hotspawn')}</td></tr>" for r in (locked + stale))}</tbody></table></div>"""
    return page("Coverage — is every match covered?", body, "coverage.html", meta)


def render_flagged(rows, meta, flags) -> str:
    # Historical inventory rows also link flag codes. Keep their explanations
    # reachable without counting those old rows as current actionable findings.
    flags = list(flags)
    published = {flag["id"] for flag in flags}
    referenced = {code for row in rows for code in (row.get("flags") or "").split(";") if code}
    for code in sorted(referenced - published):
        text, url = FLAG_TEXT.get(code, ("Unclassified finding.", ""))
        flags.append({"id": code, "text": text, "source_url": url,
                      "fixtures": [], "severity": "historical inventory only"})
    items = []
    for flag in flags:
        fixtures = flag["fixtures"]
        fixture_html = ""
        if fixtures:
            shown = fixtures[:60]
            fixture_html = '<ul class="tight">' + "".join(f"<li>{escape(f)}</li>" for f in shown) + "</ul>"
            if len(fixtures) > len(shown):
                fixture_html += f'<p class="muted">+{len(fixtures) - len(shown)} more</p>'
        items.append(f"""<article class="flagcard" id="{flag['id']}">
  <h3>{flag['id']} <span class="tag">{escape(flag['severity'])}</span></h3>
  <p>{escape(flag['text'])}</p>
  <p class="muted">Applies to {len(fixtures)} item(s). Source: {link(flag['source_url'], flag['source_url']) or 'none'}</p>
  {fixture_html}
</article>""")
    alias_rows = "".join(
        f"<tr><td>{escape(alias)}</td><td>{escape(target)}</td>"
        f"<td>{link(ALIAS_SOURCES.get(alias, ''), 'identity check') or 'documented alias'}</td></tr>"
        for alias, target in sorted(ALIASES.items()))
    body = f"""
<p class="note">Nothing on this site is guessed. Every row where a value could not be confirmed
against an official source is listed here with the reason and a link for manual review. These items
do not block anything — the rest of the slate publishes normally.</p>
{''.join(items)}
<h2>Alias table used to join bookmaker spellings</h2>
<div class="tablewrap"><table class="grid"><thead><tr><th>Spelling seen</th><th>Matched to</th>
<th>Evidence</th></tr></thead><tbody>{alias_rows}</tbody></table></div>"""
    return page("Flagged for review", body, "flagged.html", meta)


def render_sources(snapshot, meta) -> str:
    rows = "".join(
        f"<tr><td>{escape(p['url'])}</td><td>{escape(str(p.get('path')))}</td>"
        f"<td>{escape(str(p.get('status')))}</td><td>{escape(str(p.get('bytes')))}</td>"
        f"<td class=\"hash\">{escape((p.get('sha256') or '')[:16])}</td>"
        f"<td>{escape(p.get('fetched_utc') or '')}</td><td>{escape(p.get('error') or '—')}</td></tr>"
        for p in snapshot.get("provenance", []))
    vrs = snapshot.get("vrs", {})
    body = f"""
<p class="note">Every URL this run touched, with its HTTP status, byte size, SHA-256 (first 16 hex
characters) and fetch time, so any row can be re-fetched and compared. Raw bodies are not committed —
only these digests are.</p>
<div class="tablewrap"><table class="grid"><thead><tr><th>URL</th><th>Path</th><th>HTTP</th><th>Bytes</th>
<th>SHA-256</th><th>Fetched (UTC)</th><th>Error</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Rating input</h2>
<p>Own lines use Valve's official Regional Standings file:
{link(vrs.get('url', ''), vrs.get('file') or vrs.get('url', ''))}, standings as of
<b>{escape(vrs.get('as_of') or 'not stated in the file')}</b>, {len(vrs.get('teams', []))} teams.
HLTV world ranking (cross-check only): {link(snapshot.get('hltv', {}).get('url', ''), snapshot.get('hltv', {}).get('url', ''))}
— {len(snapshot.get('hltv', {}).get('ranks', {}))} teams read.</p>"""
    return page("Sources", body, "sources.html", meta)


def render_methodology(meta) -> str:
    body = """
<h2>What comes from where</h2>
<table class="grid plain"><tbody>
<tr><th>Fixture identity, exact UTC start and lock time</th><td>play.hotspawn.com Pick'em pages —
their own server-rendered Angular payload (<code>script#ng-state</code>). The board's rendered text is
never used as a probability.</td></tr>
<tr><th>External probability</th><td>A two-way bookmaker market, de-vigged. A single source per fixture
is labelled as such; Pinnacle (direct bookmaker) is preferred over an aggregator listing when both exist.</td></tr>
<tr><th>Our own line</th><td>Elo over Valve's official Regional Standings points, scale 400. A team
Valve does not list gets a blank line, never an invented rating.</td></tr>
<tr><td colspan="2" class="muted">Hotspawn crowd pick percentages are read from the payload for the
audit page only, are dropped from the dataset by this build script, and never enter a probability or a pick.</td></tr>
</tbody></table>

<h2>Formulas</h2>
<pre>de-vig            p_A = (1/o_A) / ((1/o_A) + (1/o_B))        overround = (1/o_A + 1/o_B - 1) * 100
own line          p_A = 1 / (1 + 10 ** (-(vrs_A - vrs_B) / 400))
headline          outside market when one exists, else our own line, else blank
pick              the higher headline probability, labelled with its basis;
                  "No confident pick" when the two sides are within 2.0 points;
                  no pick at all when no verified line exists (FL-04)</pre>

<h2>Joining a bookmaker price to a fixture</h2>
<p>A quote is accepted only when the two team names match the fixture pair after lower-casing,
punctuation removal and an explicitly documented alias (bookmaker spellings such as
<code>WBT</code> for <code>WROTBERRY</code>), and — when the source states a start time — that start
is within 120 minutes of the Pick'em start. Ambiguous joins are left blank and flagged (FL-03).</p>

<h2>What is deliberately blank</h2>
<ul class="tight">
<li>No readable bookmaker market → no market column, flagged FL-01 (the row may still carry our own line, FL-13).</li>
<li>Team absent from Valve's file → no own line, flagged FL-02.</li>
<li>Neither source → no probability and no pick, flagged FL-04.</li>
<li>Aggregator placeholder prices (identical both ways, e.g. 1.80/1.80) are treated as unreadable.</li>
</ul>

<h2>Limits, stated plainly</h2>
<ul class="tight">
<li>Prices move. Every page states the snapshot time; the workflow re-collects on a schedule and the
rows are never re-dated without re-reading the sources.</li>
<li>One external source is weaker evidence than two. Where only one is readable, that is labelled on the row.</li>
<li>This is analysis, not betting advice, and it does not predict outcomes — it reports what the
outside market and an official-rating model imply.</li>
</ul>"""
    return page("Methodology", body, "methodology.html", meta)


STYLE = """:root{--bg:#0e1116;--panel:#161b22;--panel2:#1c232c;--line:#2a323d;--fg:#e9eef5;--muted:#93a1b1;--accent:#7c5cff;--good:#3ddc97;--warn:#ffb454}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:0 14px}
header{background:linear-gradient(180deg,#171d26,#12171e);border-bottom:1px solid var(--line);padding:18px 0 10px;position:sticky;top:0;z-index:5}
header h1{font-size:19px;margin:0 0 2px;line-height:1.25}
header .sub{margin:0 0 10px;color:var(--muted);font-size:13px}
header nav{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;-webkit-overflow-scrolling:touch}
header nav a{color:#cbd5e1;text-decoration:none;font-size:13px;font-weight:600;padding:6px 10px;border:1px solid var(--line);border-radius:999px;white-space:nowrap}
header nav a.active{background:var(--accent);border-color:var(--accent);color:#fff}
main{padding:14px 14px 60px}
h2{font-size:16px;margin:26px 0 8px}
h3{font-size:15px;margin:0 0 6px}
a{color:#9db4ff}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:10px 12px;font-size:13px;color:#c6d2e0}
.counters{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:12px 0}
.counter{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.counter b{display:block;font-size:22px;line-height:1.1}
.counter span{font-size:12px;color:var(--muted)}
.filters{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:14px 0;font-size:13px;color:var(--muted)}
.filters select{background:var(--panel2);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:6px 8px;font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;margin:10px 0}
.cardhead{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
.comp{font-size:12px;color:var(--muted);margin-bottom:2px}
.teams{font-size:18px;font-weight:700}
.teams .vs{color:var(--muted);font-weight:400;font-size:13px}
.when{font-size:12px;color:var(--muted);margin-top:2px}
.tag{display:inline-block;font-size:11px;font-weight:700;border:1px solid var(--line);border-radius:999px;padding:0 7px;color:var(--muted);margin-left:4px}
.pick{background:var(--good);color:#06251a;font-weight:800;font-size:13px;padding:6px 10px;border-radius:999px;white-space:nowrap}
.pick.none{background:#2a323d;color:var(--muted);font-weight:700}
.bars{display:flex;height:34px;border-radius:8px;overflow:hidden;margin:10px 0 6px;border:1px solid var(--line)}
.bars.empty{align-items:center;justify-content:center;color:var(--muted);font-size:12px;height:30px}
.bar{display:flex;align-items:center;padding:0 8px;font-size:13px;font-weight:700;overflow:hidden;white-space:nowrap}
.bar.a{background:linear-gradient(90deg,#3b2f7a,#5b46c9)}
.bar.b{background:linear-gradient(90deg,#1f4f45,#2f8f74)}
.detail{display:grid;grid-template-columns:minmax(150px,auto) 1fr;gap:2px 10px;margin:8px 0 0;font-size:13px}
.detail dt{color:var(--muted)}
.detail dd{margin:0}
.muted{color:var(--muted)}
.flags{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}
.flag{font-size:11px;font-weight:700;color:#ffd7a1;border:1px solid #5a4526;background:#2a2317;border-radius:6px;padding:2px 6px;text-decoration:none}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table.grid{border-collapse:collapse;width:100%;font-size:13px;min-width:720px}
table.grid.plain{min-width:0}
table.grid th,table.grid td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
table.grid th{background:var(--panel2);position:sticky;top:0;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:#c9d4e2}
table.grid tr.open td{background:rgba(61,220,151,.05)}
table.grid tr.closed td{color:var(--muted)}
.hash{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:11px}
.flagcard{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--warn);border-radius:10px;padding:12px;margin:10px 0}
ul.tight{margin:6px 0 0;padding-left:18px;font-size:13px;color:#c6d2e0}
pre{background:#0b0e13;border:1px solid var(--line);border-radius:8px;padding:10px;overflow-x:auto;font-size:12px}
footer{border-top:1px solid var(--line);margin-top:30px;padding-top:12px;color:var(--muted);font-size:12px}
code{background:#0b0e13;border:1px solid var(--line);border-radius:4px;padding:0 4px;font-size:12px}
@media(max-width:520px){
  .detail{grid-template-columns:1fr}
  .detail dt{margin-top:6px;font-size:12px}
  .teams{font-size:17px}
  table.grid{min-width:640px}
}
"""


def self_check(rows, snapshot):
    problems = []
    for row in rows:
        if not row["hotspawn_url"]:
            problems.append(f"{row['match_id']}: no Hotspawn source link")
        for banned in ("crowd_pct_a", "crowd_pct_b", "crowd_total_picks"):
            if banned in row:
                problems.append(f"{row['match_id']}: crowd field {banned} leaked into the slate")
        if row.get("final_p_a_pct"):
            total = float(row["final_p_a_pct"]) + float(row["final_p_b_pct"])
            if abs(total - 100) > 0.5:
                problems.append(f"{row['match_id']}: probabilities sum to {total}")
            if not row.get("pick"):
                problems.append(f"{row['match_id']}: probability without a pick decision")
        else:
            if row.get("pick"):
                problems.append(f"{row['match_id']}: pick without a probability")
        if row.get("ext_p_a_pct") and not row.get("ext_url"):
            problems.append(f"{row['match_id']}: market probability without a source URL")
        if row["pickable"] == "yes" and row.get("ext_p_a_pct") and not row.get("ext_odds_a"):
            problems.append(f"{row['match_id']}: market probability without odds")
    return problems


def main() -> int:
    snapshot = load()
    rows = build_rows(snapshot)
    flags = collect_flags(rows, snapshot)
    problems = self_check(rows, snapshot)
    if problems:
        print("[build] SELF-CHECK FAILED:", file=sys.stderr)
        for problem in problems:
            print("  -", problem, file=sys.stderr)
        return 2
    pickable = [r for r in rows if r["pickable"] == "yes"]
    meta = {
        "generated_utc": snapshot["generated_utc"],
        "collection_started_utc": snapshot.get("collection_started_utc"),
        "fixtures": len(rows),
        "pickable": len(pickable),
        "with_external": sum(1 for r in pickable if r.get("ext_p_a_pct")),
        "with_own": sum(1 for r in pickable if r.get("own_p_a_pct")),
        "with_pick": sum(1 for r in pickable if r.get("pick") and r["pick"] != "No confident pick"),
        "flags": len(flags),
        "week_text": snapshot.get("week_text"),
        "reset_text": snapshot.get("reset_text"),
        "crowd_fields_seen": snapshot.get("fixtures_with_crowd_fields", 0),
    }
    DATA.mkdir(parents=True, exist_ok=True)
    write_csv(DATA / "slate.csv", SLATE_COLUMNS, rows)
    write_csv(DATA / "coverage.csv",
              ["competition", "fixtures", "pickable", "external", "own", "pick", "blank"],
              coverage_rows(rows))
    write_csv(DATA / "flags.csv", ["id", "severity", "text", "source_url", "fixtures"],
              [{**flag, "fixtures": " | ".join(flag["fixtures"])} for flag in flags])
    (DATA / "snapshot_meta.json").write_text(json.dumps(meta, indent=1))
    (DATA / "slate.json").write_text(json.dumps(rows, indent=1))

    LIVE.joinpath("style.css").write_text(STYLE)
    published = {flag["id"] for flag in flags}
    LIVE.joinpath("index.html").write_text(render_index(rows, meta, flags, published))
    LIVE.joinpath("matches.html").write_text(render_matches(rows, meta, published))
    LIVE.joinpath("coverage.html").write_text(render_coverage(rows, meta, snapshot))
    LIVE.joinpath("flagged.html").write_text(render_flagged(rows, meta, flags))
    LIVE.joinpath("sources.html").write_text(render_sources(snapshot, meta))
    LIVE.joinpath("methodology.html").write_text(render_methodology(meta))

    print(f"[build] fixtures={len(rows)} open={meta['pickable']} external={meta['with_external']} "
          f"own={meta['with_own']} picks={meta['with_pick']} flags={meta['flags']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
