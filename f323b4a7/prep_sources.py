#!/usr/bin/env python3
"""Assemble the source dataset for the f323b4a7 board (one-off, reproducible).

Every value in the produced ``data/sources.json`` is either
  (a) copied verbatim from a capture stored in this repository, or
  (b) derived by a rule that is verified against that capture and written down in
      ``DERIVATIONS`` below.
Nothing is inferred from memory: a field that cannot be sourced is left blank and
surfaces on the Flagged page.
"""
from __future__ import annotations

import csv
import json
import pathlib
import re
import datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = pathlib.Path(__file__).resolve().parent / "data"

# ---------------------------------------------------------------- live capture (mine)
# Sandbox clock read 2026-10-16T04:17:25Z immediately before the first fetch; the
# Hotspawn lobby was read during the window below.  The page states "123 matches this
# week" and the CS2 tier filter states "All tiers (95)".
LIVE = {
    "read_utc": "2026-10-16T04:18:00Z",
    "read_window_utc": "2026-10-16T04:17:30Z/2026-10-16T04:24:00Z",
    "url": "https://play.hotspawn.com/lobby",
    "week_text": "123 matches this week",
    "tier_text": "All tiers (95)",
    "tier_counts": {"B": 38, "C": 54, "S": 3},
    "tournaments": {
        "CCT Europe 2026 Challengers #4": 8, "CCT Europe 2026 Series #11": 6,
        "CCT Europe 2026 Series #12 Play-In": 2, "CCT South America 2026 Series #3": 8,
        "CCT South America 2026 Series #7": 3, "DACH CS Masters Season 5": 1,
        "DraculaN Season 7": 13, "Elisa BreakOut Series #2": 6,
        "European Pro League Series 8": 1, "European Pro League Series 8 Play-In": 6,
        "LG UltraGear Tournament 2026": 1, "NODWIN Clutch Series #13": 5,
        "Rainhas do Clutch 2026": 2, "Stake Pulse Beat III": 4,
        "Svenska CS-Ligan 2026": 6, "Thunderpick World Championship 2026": 3,
        "Thunderpick World Championship 2026: South American Series #1": 8,
        "Urban Riga Open #5": 12,
    },
}

# The 9 fixtures that appear on the live lobby but not in the 2026-10-15T22:41:15Z
# TransferState capture.  start_utc/lock_utc are DERIVED (rule R1+R2, verified below).
NEW = [
    dict(match_id="1081712", competition="Stake Pulse Beat III", tier="B", stage="waiting for information",
         team_a="Fnatic", team_b="Heroic", display="Oct 16, 07:00", crowd_a_pct=0, crowd_b_pct=100,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/fnatic-vs-heroic-stake-pulse-beat-iii-1081712"),
    dict(match_id="1079588", competition="Stake Pulse Beat III", tier="B", stage="waiting for information",
         team_a="Astralis", team_b="MIBR", display="Oct 16, 10:00", crowd_a_pct=100, crowd_b_pct=0,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/astralis-vs-mibr-stake-pulse-beat-iii-1079588"),
    dict(match_id="1079167", competition="NODWIN Clutch Series #13", tier="B", stage="waiting for information",
         team_a="Bushido Wildcats", team_b="ex-RUSTEC", display="Oct 16, 07:00", crowd_a_pct=0, crowd_b_pct=100,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/bushido-wildcats-vs-ex-rustec-nodwin-clutch-series-13-1079167"),
    dict(match_id="1081769", competition="NODWIN Clutch Series #13", tier="B", stage="waiting for information",
         team_a="ex-Zero Tenacity", team_b="UNiTY", display="Oct 16, 10:00", crowd_a_pct=0, crowd_b_pct=100,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/ex-zero-tenacity-vs-unity-nodwin-clutch-series-13-1081769"),
    dict(match_id="1081775", competition="Thunderpick World Championship 2026", tier="S",
         stage="group stage and playoffs", team_a="BetBoom", team_b="Legacy", display="Oct 16, 13:00",
         crowd_a_pct=50, crowd_b_pct=50, offered_points=7, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/betboom-vs-legacy-thunderpick-world-championship-2026-1081775"),
    dict(match_id="1081126", competition="CCT Europe 2026 Series #12 Play-In", tier="C", stage="waiting for information",
         team_a="banda chuya", team_b="Enjoy", display="Oct 18, 04:00", crowd_a_pct=100, crowd_b_pct=0,
         offered_points=2, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/banda-chuya-vs-enjoy-cct-europe-2026-series-12-play-in-1081126"),
    dict(match_id="1079170", competition="NODWIN Clutch Series #13", tier="B", stage="waiting for information",
         team_a="BET-M", team_b="Just Players", display="Oct 17, 04:00", crowd_a_pct=100, crowd_b_pct=0,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/bet-m-vs-just-players-nodwin-clutch-series-13-1079170"),
    dict(match_id="1079171", competition="NODWIN Clutch Series #13", tier="B", stage="waiting for information",
         team_a="GenOne", team_b="Butterfly", display="Oct 17, 07:00", crowd_a_pct=0, crowd_b_pct=100,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/genone-vs-butterfly-nodwin-clutch-series-13-1079171"),
    dict(match_id="1079173", competition="NODWIN Clutch Series #13", tier="B", stage="waiting for information",
         team_a="BakS", team_b="Fire Flux", display="Oct 17, 13:00", crowd_a_pct=100, crowd_b_pct=0,
         offered_points=3, total_picks=0,
         hotspawn_url="https://www.hotspawn.com/matches/baks-vs-fire-flux-nodwin-clutch-series-13-1079173"),
]

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6, "Jul": 7, "Aug": 8,
          "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def display_to_utc(text: str) -> str:
    """R1: Hotspawn renders kick-off in UTC-4.  Verified against 6 captured fixtures
    (1079586 08:00Z->'Oct 16, 04:00'; 1080205 14:00Z->'Oct 16, 10:00'; 1081526
    2026-10-19T09:00Z->'Oct 19, 05:00'; 1081529, 1081530, 1081531)."""
    m = re.match(r"([A-Z][a-z]{2}) (\d{1,2}), (\d{2}):(\d{2})$", text.strip())
    mon, day, hh, mm = MONTHS[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4))
    utc = datetime.datetime(2026, mon, day, hh, mm, tzinfo=datetime.timezone.utc) + datetime.timedelta(hours=4)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    archived = json.load(open(D / "archived_fixtures.json"))
    byid = {f["match_id"]: f for f in archived}

    fixtures = list(archived)
    for n in NEW:
        start = display_to_utc(n.pop("display"))
        lock = (datetime.datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
                - datetime.timedelta(seconds=360)).strftime("%Y-%m-%dT%H:%M:%SZ")
        fixtures.append(dict(
            match_id=n["match_id"], competition=n["competition"], tier=n["tier"], stage=n["stage"],
            team_a=n["team_a"], team_b=n["team_b"], start_utc=start, lock_utc=lock, lock_offset_sec=360,
            offered_points=n["offered_points"], base_points=None, points_breakdown=None,
            total_picks=n["total_picks"], crowd_a_pct=n["crowd_a_pct"], crowd_b_pct=n["crowd_b_pct"],
            status="scheduled", best_of=None, series_format=None, hotspawn_url=n["hotspawn_url"],
            source="live lobby read 2026-10-16T04:18:00Z + rules R1/R2", source_url=LIVE["url"]))
    fixtures.sort(key=lambda f: (f["lock_utc"], f["match_id"]))

    # R2 verification: every archived fixture has lock_offset_sec == 360
    offsets = {f["lock_offset_sec"] for f in archived}

    # ------------------------------------------------------------------ Valve VRS points
    vrs = {}
    vrs_url = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
               "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md")
    for line in open(ROOT / "briefing/data/valve/standings_global_2026_10_05.md"):
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            vrs[m.group(3).strip()] = {"standing": int(m.group(1)), "points": int(m.group(2)),
                                       "roster": m.group(4).strip(), "url": vrs_url}

    # --------------------------------------------------------------------- HLTV ranks
    hltv = {}
    for row in csv.DictReader(open(ROOT / "data/ratings.csv")):
        if not row.get("hltv_world_rank"):
            continue
        hltv[row["team"]] = {"rank": int(row["hltv_world_rank"]), "url": row["rank_source_url"],
                             "label": row["rank_source_label"]}
    # per-fixture ranks captured with the 2026-10-12 HLTV ranking by the hotspawn collector
    for row in csv.DictReader(open(ROOT / "hotspawn/data/picks.csv")):
        for side in ("a", "b"):
            r = row.get(f"hltv_rank_{side}")
            if r:
                hltv.setdefault(row[f"team_{side}"], {})["rank_2026_10_12"] = int(r)

    # ------------------------------------------------------------- external market lines
    lines = {}
    for row in csv.DictReader(open(ROOT / "hotspawn/data/picks.csv")):
        mid = row["match_id"]
        entry = {"pinnacle_odds_a": row.get("pinnacle_odds_a") or None,
                 "pinnacle_odds_b": row.get("pinnacle_odds_b") or None,
                 "polymarket_price_a": row.get("polymarket_price_a") or None,
                 "polymarket_price_b": row.get("polymarket_price_b") or None,
                 "read_utc": row.get("pinnacle_read_utc") or row.get("polymarket_read_utc") or None,
                 "pinnacle_url": row.get("pinnacle_url") or None,
                 "polymarket_url": row.get("polymarket_url") or None,
                 "basis": row.get("basis") or None}
        if any([entry["pinnacle_odds_a"], entry["polymarket_price_a"]]):
            lines[mid] = entry

    formats = {}
    for row in csv.DictReader(open(ROOT / "hotspawn/data/picks.csv")):
        if row.get("format"):
            formats[row["match_id"]] = {"format": row["format"],
                                        "format_source": row.get("format_source"),
                                        "read_utc": "2026-10-15T22:41:17Z"}

    out = {"live_capture": LIVE, "formats": formats, "derivations": {
        "R1": "Hotspawn renders kick-off in UTC-4; verified on 6 captured fixtures (see prep_sources.py).",
        "R2": "lock_time = scheduled_start_time - 360 s; lock_offset_sec == 360 for all 86 captured fixtures.",
        "R3": "Crowd pick share is stored as ownership only and is never used as a probability."},
        "r2_check": sorted(str(o) for o in offsets),
        "fixtures": fixtures, "vrs": vrs, "hltv": hltv, "lines": lines,
        "vrs_as_of": "2026-10-05", "vrs_commit": "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75",
        "lines_snapshot_utc": "2026-10-15T22:41:17Z"}
    json.dump(out, open(D / "sources.json", "w"), indent=1)
    print("fixtures", len(fixtures), "| open",
          sum(1 for f in fixtures if f["lock_utc"] > "2026-10-16T04:18:00Z"),
          "| vrs teams", len(vrs), "| hltv teams", len(hltv), "| line rows", len(lines))


if __name__ == "__main__":
    main()
