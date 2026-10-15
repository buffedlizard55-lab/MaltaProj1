#!/usr/bin/env python3
"""Development seed: build ``a6f05f99/data/capture.json`` from another session's committed capture.

This repository already holds a live capture taken by session arena/22be6967 at
``hotspawn/data/capture.json`` (Hotspawn + Pinnacle + Polymarket + Valve + HLTV, read
2026-10-15 21:34Z).  This script re-shapes it into this module's schema so the pages can be built
and the tests can run without network access.  It invents nothing: every value is copied, and the
``seeded_from`` block records where it came from and when it was read.

In CI the real ``collect.py`` overwrites this file on the first run (a live capture always wins).
This script is a developer convenience only and is never part of the scheduled workflow.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, log, now_iso, read_json, write_json  # noqa: E402

SOURCE = Path(__file__).resolve().parent.parent / "hotspawn" / "data" / "capture.json"


def main() -> int:
    src = read_json(SOURCE, {})
    if not src:
        log(f"seed source missing: {SOURCE}")
        return 1
    fixtures = []
    for f in src.get("hotspawn", {}).get("fixtures", []):
        fixtures.append({
            "match_id": f.get("match_id"), "competition": f.get("competition"),
            "competition_id": f.get("competition_id"), "tier": f.get("tier"),
            "stage": f.get("stage"), "status": f.get("status"),
            "team_a": f.get("team_a"), "team_b": f.get("team_b"),
            "team_a_id": f.get("team_a_id"), "team_b_id": f.get("team_b_id"),
            "start_utc": f.get("start_utc"), "lock_utc": f.get("lock_utc"),
            "points": f.get("offered_points") if f.get("offered_points") is not None else f.get("base_points"),
            "best_of": f.get("best_of_payload"), "series_format": f.get("series_format_payload"),
            "score_a": f.get("score_a_payload"), "score_b": f.get("score_b_payload"),
            # ownership only - never a probability input
            "crowd_a_ownership": f.get("crowd_a_ownership"), "crowd_b_ownership": f.get("crowd_b_ownership"),
            "total_picks": f.get("total_picks_ownership"),
            "pages": f.get("pages", []), "source_url": f.get("source_url"),
            "read_utc": f.get("read_utc"),
        })
    capture = {
        "schema": "a6f05f99-board/1", "session": "arena/a6f05f99",
        "started_utc": src.get("started_utc"), "finished_utc": src.get("finished_utc"),
        "seeded_from": {
            "path": "hotspawn/data/capture.json",
            "session": src.get("session"),
            "read_utc": src.get("finished_utc"),
            "why": "No general internet access from the agent sandbox; the scheduled workflow "
                   "replaces this file with a fresh live capture on its first run (and adds bo3.gg).",
        },
        "hotspawn": {"mode": "seeded", "pages": src.get("hotspawn", {}).get("pages", []),
                     "week": src.get("hotspawn", {}).get("week"),
                     "fixtures": fixtures,
                     "read_utc": src.get("hotspawn", {}).get("read_utc")},
        "pinnacle": {"mode": "seeded", "quotes": src.get("pinnacle", {}).get("quotes", []),
                     "page_url": src.get("pinnacle", {}).get("page_url"),
                     "read_utc": src.get("pinnacle", {}).get("read_utc")},
        # Not present in the source capture; filled in by the first live run in CI.
        "bo3": {"mode": "not_collected_yet", "matches": [], "page_url": "https://bo3.gg/matches/current",
                "read_utc": None},
        "polymarket": {"mode": "seeded", "quotes": src.get("polymarket", {}).get("quotes", []),
                       "page_url": "https://polymarket.com/sports/counter-strike-2",
                       "read_utc": src.get("polymarket", {}).get("read_utc")},
        "vrs": {**src.get("vrs", {}),
                "standings_date": (src.get("vrs") or {}).get("standings_date")
                or (src.get("vrs") or {}).get("as_of"),
                "blob_url": (src.get("vrs") or {}).get("blob_url")
                or (src.get("vrs") or {}).get("url")},
        "hltv": {**src.get("hltv", {}),
                 "ranking_date": (src.get("hltv") or {}).get("ranking_date")
                 or (src.get("hltv") or {}).get("date_path")},
        "provenance": src.get("provenance", []),
    }
    write_json(DATA / "capture.json", capture)
    log(f"seeded {DATA / 'capture.json'}: {len(fixtures)} fixtures "
        f"(source read {src.get('finished_utc')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
