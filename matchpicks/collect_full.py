#!/usr/bin/env python3
"""Session arena/b44b5d5e — full-slate collector for every Hotspawn CS2 fixture.

Why this exists
---------------
The published boards capture Hotspawn fixtures through a filter that keeps only nodes
that already carry ``id + team_a + team_b + scheduled_start_time``.  Fixtures Hotspawn has
opened but not yet populated with participant names (their match page slug is literally
``?fixtures=waiting-for-information-<id>``) therefore disappear from the inventory with no
trace.  On 2026-10-15 that hid the four Tier-S Thunderpick World Championship fixtures
``1080201``–``1080204`` from ``live/data/slate.csv`` while they were visible on
``play.hotspawn.com/lobby``.

This collector reads the same public pages and keeps *every* fixture node:

* ``fixtures_complete``   — id + both participants + start time (a pick can be derived);
* ``fixtures_incomplete`` — a node that is a fixture but is missing participants and/or the
  start time; recorded with its raw (crowd-free) fields so it can be published as an
  unresolved row instead of vanishing;
* ``dom_ids`` / ``dom_only_ids`` — fixture ids rendered in the page markup, so a payload/
  markup disagreement is visible rather than silent.

Sources (all public, no login, no key, no challenge solving):
  1. ``play.hotspawn.com/{lobby,cs2-pickems,thp-pickems}`` — the Angular ``ng-state``
     TransferState payload.  Used for fixture identity, tier, offered points and the exact
     UTC ``scheduled_start_time`` / ``lock_time`` epochs, plus the published score of a
     finished fixture.  The crowd pick percentages that sit in the same payload are dropped
     at ingest: this snapshot never stores them, and ``build.py`` fails if one appears.
  2. Valve Regional Standings — Valve's own published standings file (official rating input
     for the originated line).
  3. Pinnacle public guest responses that the public matchups page loads itself (whole-match
     moneyline; American prices converted to decimal).
  4. EGamersWorld public match pages (aggregated bookmaker prices, read in headless Chromium).
  5. Polymarket public market API (prediction-market price, labelled as such).
  6. HLTV world ranking page (rank number only; headless Chromium).

The readers for sources 2–6 are imported from the repository's existing, already-verified
collector ``live/collect.py`` (session arena/459ff624) instead of being re-written, so the
same parsing rules that other boards validate are used here.  This module never writes
outside ``matchpicks/``.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# Give the reused readers a generous budget (their default is 900 s; the workflow allows more).
os.environ.setdefault("LIVE_BUDGET_SECONDS", "1500")

# Crowd fields are dropped at ingest.  Listed explicitly so the drop is auditable.
CROWD_KEYS = (
    "participants0_picked", "participants1_picked", "participants0_picked_percent",
    "participants1_picked_percent", "picked_percent", "picked", "total_picks", "picks_count",
)


def load_live_collector():
    """Import the repository's verified public-source readers as a read-only library."""
    path = ROOT / "live" / "collect.py"
    spec = importlib.util.spec_from_file_location("live_collect_459ff624", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


lc = load_live_collector()


def load_live_builder():
    """The repository's name normalisation (including the documented alias table), read-only."""
    path = ROOT / "live" / "build.py"
    spec = importlib.util.spec_from_file_location("live_build_459ff624", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


lb = load_live_builder()

FIELD_ALIASES = {
    "match_id": ("id", "match_id", "fixture_id"),
    "team_a": ("participants0_name", "teamA", "home_name"),
    "team_b": ("participants1_name", "teamB", "away_name"),
    "team_a_id": ("participants0_id", "teamA_id"),
    "team_b_id": ("participants1_id", "teamB_id"),
    "team_a_score": ("participants0_score", "teamA_score"),
    "team_b_score": ("participants1_score", "teamB_score"),
    "start": ("scheduled_start_time", "scheduledStartTime", "start_time"),
    "lock": ("lock_time", "lockTime"),
    "lock_offset": ("lock_offset_sec", "lockOffsetSec"),
    "competition": ("competition_name", "competitionName", "competition", "tournament"),
    "tier": ("tier", "tier_name"),
    "stage": ("stage", "stage_name"),
    "status": ("status", "match_status"),
    "points": ("offered_points", "offeredPoints", "points"),
    "base_points": ("base_points", "basePoints"),
    "best_of": ("best_of", "bestOf"),
    "series_format": ("series_format", "seriesFormat"),
    "sport": ("sport_alias", "sport", "game_alias"),
    "sport_name": ("sport_name", "game_name"),
    "started": ("started_time", "startedTime"),
    "ended": ("end_time", "end_time_ms", "ended_time"),
}

MULTIPLIER = re.compile(r"Multiplier\s*×\s*([0-9.]+)", re.I)


def get(node: dict, key: str, default=None):
    """Read the first present spelling of a field from a payload node."""
    for name in FIELD_ALIASES[key]:
        if name in node and node[name] not in (None, ""):
            return node[name]
    return default


def strip_crowd(node: dict) -> dict:
    """Copy a payload node with every crowd-pick field removed (they are never published)."""
    clean = {}
    for key, value in node.items():
        if key in CROWD_KEYS:
            continue
        if key == "participants" and isinstance(value, list):
            clean[key] = [
                {k: v for k, v in part.items() if k not in CROWD_KEYS}
                if isinstance(part, dict) else part
                for part in value
            ]
            continue
        clean[key] = value
    return clean


def collect_hotspawn_full() -> dict:
    """Read every CS2 fixture node from the Hotspawn pick'em pages."""
    complete: dict[str, dict] = {}
    incomplete: dict[str, dict] = {}
    dom_ids: set[str] = set()
    payload_ids_all: set[str] = set()   # every fixture node on every page, any sport
    pages: list[dict] = []
    crowd_fields_dropped = 0

    for page_name, url in lc.HOTSPAWN_PAGES:
        got = lc.http_get(url)
        body = got["body"].decode("utf-8", errors="replace") if got["body"] else ""
        page = {"page": page_name, "url": url, "status": got["status"], "bytes": got["bytes"],
                "sha256": got["sha256"], "error": got["error"], "state_rows": 0,
                "complete_rows": 0, "incomplete_rows": 0, "dom_ids": 0,
                "week_text": None, "reset_text": None, "multiplier": None}
        if body:
            page["dom_ids"] = len(set(m.group(2) for m in lc.DOM_MATCH_LINK.finditer(body)))
            dom_ids.update(m.group(2) for m in lc.DOM_MATCH_LINK.finditer(body))
            plain = lc.text_of(body)
            match = re.search(r"(\d+)\s+matches this week", plain)
            if match:
                page["week_text"] = f"{match.group(1)} matches this week"
            match = re.search(r"Resets in ((?:\d+d )?(?:\d+h )?(?:\d+m )?(?:\d+s))", plain)
            if match:
                page["reset_text"] = match.group(1)
            match = MULTIPLIER.search(plain)
            if match:
                page["multiplier"] = match.group(1)
            state_match = lc.STATE_SCRIPT.search(body)
            if not state_match:
                page["error"] = (page["error"] or "") + " ng-state not found"
            else:
                try:
                    state = json.loads(unescape(state_match.group(1)).strip())
                except json.JSONDecodeError as exc:
                    page["error"] = (page["error"] or "") + f" ng-state JSON: {exc}"
                else:
                    nodes: list[dict] = []
                    lc.walk_fixture_nodes(state, nodes)
                    page["state_rows"] = len(nodes)
                    links = {m.group(2): m.group(0) for m in lc.DOM_MATCH_LINK.finditer(body)}
                    for node in nodes:
                        clean = strip_crowd(node)
                        crowd_fields_dropped += sum(1 for k in node if k in CROWD_KEYS)
                        match_id = str(get(node, "match_id", "") or "")
                        if not match_id:
                            continue
                        payload_ids_all.add(match_id)
                        sport = get(node, "sport")
                        team_a, team_b = get(node, "team_a"), get(node, "team_b")
                        start = lc.ms_to_iso(get(node, "start"))
                        offset = get(node, "lock_offset")
                        lock = lc.ms_to_iso(get(node, "lock"))
                        if not lock and isinstance(offset, (int, float)) and 0 < offset < 7200 and start:
                            lock = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
                                    .replace(tzinfo=timezone.utc) - timedelta(seconds=int(offset))
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        row = {
                            "match_id": match_id,
                            "hotspawn_page": page_name,
                            "source_url": url,
                            "sport": sport,
                            "sport_name": get(node, "sport_name"),
                            "competition": get(node, "competition"),
                            "competition_id": node.get("competition_id"),
                            "tier": str(get(node, "tier", "") or "").lower() or None,
                            "stage": get(node, "stage"),
                            "status": get(node, "status"),
                            "points": get(node, "points"),
                            "base_points": get(node, "base_points"),
                            "best_of": get(node, "best_of"),
                            "series_format": get(node, "series_format"),
                            "start_utc": start,
                            "lock_utc": lock,
                            "lock_offset_sec": int(offset) if isinstance(offset, (int, float)) else None,
                            "team_a": team_a,
                            "team_b": team_b,
                            "team_a_id": str(get(node, "team_a_id", "") or "") or None,
                            "team_b_id": str(get(node, "team_b_id", "") or "") or None,
                            "team_a_score": get(node, "team_a_score"),
                            "team_b_score": get(node, "team_b_score"),
                            "started_utc": lc.ms_to_iso(get(node, "started")),
                            "ended_utc": lc.ms_to_iso(get(node, "ended")),
                            "hotspawn_match_url": links.get(match_id),
                            "payload_keys": sorted(k for k in node if not k.startswith("_")),
                            "participant_keys": sorted({k for p in (node.get("participants") or [])
                                                        if isinstance(p, dict) for k in p}),
                            "raw": clean,
                        }
                        missing = [name for name, value in
                                   (("team_a", team_a), ("team_b", team_b), ("start_utc", start))
                                   if value in (None, "")]
                        if missing:
                            row["missing_fields"] = missing
                            row["first_seen_page"] = page_name
                            previous = incomplete.get(match_id)
                            if previous is None:
                                incomplete[match_id] = row
                                page["incomplete_rows"] += 1
                            else:
                                # A later page may carry fields the first one lacked; merge them.
                                for key, value in row.items():
                                    if previous.get(key) in (None, "", []) and value not in (None, "", []):
                                        previous[key] = value
                                previous["missing_fields"] = [
                                    name for name, value in
                                    (("team_a", previous.get("team_a")), ("team_b", previous.get("team_b")),
                                     ("start_utc", previous.get("start_utc")))
                                    if value in (None, "")
                                ]
                            continue
                        if sport and str(sport).lower() not in ("cs2", "counter-strike", "counterstrike"):
                            continue
                        known = complete.get(match_id)
                        if known:
                            if page_name not in known["_pages"]:
                                known["_pages"].append(page_name)
                            for key, value in row.items():
                                if key in ("raw", "payload_keys", "participant_keys", "_pages"):
                                    continue
                                if known.get(key) in (None, "") and value not in (None, ""):
                                    known[key] = value
                        else:
                            row["_pages"] = [page_name]
                            complete[match_id] = row
                            page["complete_rows"] += 1
        pages.append(page)
        time.sleep(0.3)

    complete_rows = sorted(complete.values(), key=lambda r: (r["start_utc"] or "", r["match_id"]))
    incomplete_rows = sorted(incomplete.values(), key=lambda r: (r.get("start_utc") or "", r["match_id"]))
    for row in complete_rows + incomplete_rows:
        row["snapshot_utc"] = lc.now_iso()
    complete_ids = set(complete) | set(incomplete)
    return {
        "pages": pages,
        "fixtures_complete": complete_rows,
        "fixtures_incomplete": incomplete_rows,
        "dom_ids": sorted(dom_ids),
        "payload_ids_all": sorted(payload_ids_all),
        # A rendered link with no payload node at all — compared against every sport, so the LoL
        # fixtures on the same lobby can never be reported as missing CS2 fixtures.
        "dom_only_ids": sorted(dom_ids - payload_ids_all),
        "crowd_fields_dropped": crowd_fields_dropped,
        "week_text": next((p["week_text"] for p in pages if p["week_text"]), None),
        "reset_text": next((p["reset_text"] for p in pages if p["reset_text"]), None),
    }


HLTV_MATCHES_URL = "https://www.hltv.org/matches"
BO_TOKEN = re.compile(r"^bo([135])$", re.I)


def parse_hltv_formats(text: str, fixtures: list[dict]) -> dict:
    """Best-of length per fixture from HLTV's own upcoming-matches page text.

    Hotspawn's payload leaves ``best_of``/``series_format`` null for every fixture (observed
    2026-10-15), so the length of a series — which decides how a per-map probability becomes a match
    probability — has to come from an official source.  HLTV publishes it as a ``bo1``/``bo3``/``bo5``
    label on the match row.

    The join is deliberately strict and never guesses: a fixture is only given a length when both of
    its team names appear next to each other in the flattened page text with a single bo label inside
    the same window.  The window is kept as evidence on the row.  No match → no value.
    """
    tokens = [t for t in re.split(r"\s+", text) if t]
    compact = [re.sub(r"[^a-z0-9]", "", t.lower()) for t in tokens]
    found: list[dict] = []
    for fixture in fixtures:
        keys = []
        for raw in (fixture.get("team_a"), fixture.get("team_b")):
            key = re.sub(r"[^a-z0-9]", "", lb.norm(raw or ""))
            keys.append(key)
        if not all(keys):
            continue
        # HLTV renders each name twice in a row (image alt + visible text); accept either spelling.
        hits = []
        for key in keys:
            pairs = [i for i in range(len(compact) - 1)
                     if compact[i] == key and compact[i + 1] == key]
            singles = [i for i, token in enumerate(compact) if token == key]
            hits.append(pairs or singles)
        if not (hits[0] and hits[1]):
            continue
        window = None
        for i in hits[0]:
            for j in hits[1]:
                if i == j or abs(i - j) > 6:
                    continue        # the two names must sit in the same match row
                low, high = min(i, j), max(i, j)
                start = max(0, low - 8)
                labels = {int(BO_TOKEN.match(tokens[k]).group(1))
                          for k in range(start, high + 1)
                          if BO_TOKEN.match(tokens[k] or "")}
                # a real HLTV match row always carries its start time next to the label
                has_time = any(re.fullmatch(r"\d{1,2}:\d{2}", tokens[k])
                               for k in range(start, high + 1))
                if len(labels) == 1 and has_time:
                    window = (start, high, labels.pop())
                    break
            if window:
                break
        if not window:
            continue
        start, high, best_of = window
        found.append({"match_id": fixture["match_id"], "team_a": fixture.get("team_a"),
                      "team_b": fixture.get("team_b"), "best_of": best_of,
                      "evidence": " ".join(tokens[start: high + 2])[:300]})
    return {"matches": found}


def collect_hltv_formats(fixtures: list[dict]) -> dict:
    got = lc.browser_get(HLTV_MATCHES_URL, wait_ms=4000)
    html = got["html"] or ""
    text = lc.text_of(html) if html else ""
    parsed = parse_hltv_formats(text, fixtures) if text else {"matches": []}
    sample = re.sub(r"\s+", " ", text)[:1500]
    return {"status": "observed" if parsed["matches"] else "unavailable",
            "url": HLTV_MATCHES_URL, "read_utc": got["fetched_utc"],
            "matches": parsed["matches"], "text_sha256": got["sha256"],
            "debug_text_sample": sample}


def main() -> int:
    started = lc.now_iso()
    print(f"[matchpicks] collect start {started}", flush=True)
    hotspawn = collect_hotspawn_full()
    print(f"[matchpicks] complete={len(hotspawn['fixtures_complete'])} "
          f"incomplete={len(hotspawn['fixtures_incomplete'])} "
          f"dom_only={len(hotspawn['dom_only_ids'])}", flush=True)

    vrs = lc.collect_vrs()
    print(f"[matchpicks] VRS teams={len(vrs['teams'])} as_of={vrs['as_of']}", flush=True)
    pinnacle = lc.collect_pinnacle()
    print(f"[matchpicks] pinnacle quotes={len(pinnacle['quotes'])}", flush=True)
    egw = lc.collect_egw(limit=int(os.environ.get("MATCHPICKS_EGW_LIMIT", "40")))
    print(f"[matchpicks] egw listing={len(egw['listing'])} detail={len(egw['detail'])}", flush=True)
    polymarket = lc.collect_polymarket()
    print(f"[matchpicks] polymarket quotes={len(polymarket['quotes'])}", flush=True)

    open_fixtures = [row for row in hotspawn["fixtures_complete"]
                     if row.get("team_a") and row.get("team_b")]
    formats = collect_hltv_formats(open_fixtures)
    print(f"[matchpicks] hltv format rows={len(formats['matches'])}", flush=True)

    names = {row["team_a"] for row in hotspawn["fixtures_complete"]}
    names |= {row["team_b"] for row in hotspawn["fixtures_complete"]}
    hltv = lc.collect_hltv({n for n in names if n})
    print(f"[matchpicks] hltv ranks={len(hltv['ranks'])} matched={len(hltv['matched'])}", flush=True)

    snapshot = {
        "schema": 1,
        "session": "arena/b44b5d5e",
        "generated_utc": lc.now_iso(),
        "collection_started_utc": started,
        "week_text": hotspawn["week_text"],
        "reset_text": hotspawn["reset_text"],
        "hotspawn_pages": hotspawn["pages"],
        "fixtures_complete": hotspawn["fixtures_complete"],
        "fixtures_incomplete": hotspawn["fixtures_incomplete"],
        "dom_ids": hotspawn["dom_ids"],
        "dom_only_ids": hotspawn["dom_only_ids"],
        "crowd_fields_dropped": hotspawn["crowd_fields_dropped"],
        "vrs": vrs,
        "pinnacle": pinnacle,
        "egw": egw,
        "polymarket": polymarket,
        "hltv": hltv,
        "hltv_formats": formats,
        "provenance": lc.provenance,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "snapshot.json"
    out.write_text(json.dumps(snapshot, indent=1, sort_keys=False))
    print(f"[matchpicks] wrote {out} ({out.stat().st_size} bytes)", flush=True)
    print(f"[matchpicks] crowd fields dropped at ingest: {hotspawn['crowd_fields_dropped']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
