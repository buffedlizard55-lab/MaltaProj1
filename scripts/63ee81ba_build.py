#!/usr/bin/env python3
"""
scripts/63ee81ba_build.py — Session arena/63ee81ba (branch arena/63ee81ba-maltaproj1)

Full-coverage Hotspawn CS2 Pick'em picks board (`picks-full/`) + verified datasets
(`data/63ee81ba/*`).

Mission (user task):
  1. A pick (or explicit win % per team) for EVERY open Hotspawn CS2 match — including
     low-tier matches and matches no betting site prices.
  2. For matches without an outside market line, originate our own line from official
     CS2 esports research (Valve Regional Standings + HLTV) so a pick can still be made.
  3. Mobile-friendly board with obvious per-team probabilities, obvious pick, and a
     source link on every row. Flagged, never inferred.

Non-negotiables (enforced structurally, see tests/test_63ee81ba.py):
  * Hotspawn crowd pick percentages are NEVER read, stored or used (0.0% weight).
    The pinned inputs below contain no crowd fields at all.
  * Every published number has a source URL + capture UTC on its row.
  * Unconfirmable values are left blank and flagged — never inferred.
    The one exception is explicitly labelled "RESEARCH" (see PF-02): LFO 10 is absent
    by name from the 2026-10-05 VRS file, so its line is a roster-mapped research line
    that is published ONLY with that label and a flag, never as a verified value.

Model (documented on picks-full/methodology.html):
  * Map win probability from official Valve VRS points (2026-10-05 file):
        P_map(A) = 1 / (1 + 10 ** (-K * (pts_A - pts_B) / 400))
    K = 0.4568 — the calibrated slope adopted by this repository
    (model/input/vrs/calibration.json, adopted=true, k_published; MLE on Valve's
    6,765 published results, out-of-sample log loss 0.6619 raw -> 0.6435 calibrated,
    Brier 0.2294 -> 0.2258).
  * Series transform (independent-map approximation; series format verified on the
    official HLTV match page for every fixture):
        BO1: P_series = p
        BO3: P_series = p^3 + 3 p^2 (1-p) = p^2 (3 - 2p)
  * Outside market lines are series moneylines: de-vigging
        p_A = (1/d_A) / (1/d_A + 1/d_B)
    yields series-win probabilities directly (no transform applied).
  * Pick rule: if a priced outside market exists, the pick follows the de-vigged
    market favourite; otherwise it follows the originated line favourite.
    Confidence tiers: OBVIOUS LOCK >= 70%, STRONG PICK 60-69%, SOLID LEAN 55-59%,
    otherwise CLOSE TOSS-UP.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ----------------------------------------------------------------------------- session
SESSION = "arena/63ee81ba"
BRANCH = "arena/63ee81ba-maltaproj1"
SNAP_UTC = "2026-10-14T02:48:00Z"  # pinned snapshot of record (end of EGW listing read)
DATA_DIR = ROOT / "data" / "63ee81ba"
SITE_DIR = ROOT / "picks-full"
REVIEW = ROOT / "reviews" / "63ee81ba-repo-review.md"

# ----------------------------------------------------------------------------- sources
VRS_COMMIT = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"
VRS_FILE_REL = "live/2026/standings_global_2026_10_05.md"
VRS_FILE = DATA_DIR / "vrs_2026_10_05.md"
VRS_SHA256 = "df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b"
VRS_BASE_URL = f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/{VRS_FILE_REL}"
VRS_DETAILS_BASE = f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/live/2026/"
VRS_API_DIR = "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/2026"
VRS_LOCAL_FETCHEd = "2026-10-14T02:35:00Z"  # re-fetched + hash-verified today

HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams/2026/october/12"
HLTV_RANKING_SNAP = "2026-10-12 (snapshot verified 2026-10-14T02:26:00Z via data/8944bb84/ratings.csv)"

HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
HOTSPAWN_PAYLOAD_READ = "2026-10-14T02:38:00Z"  # live /cs2-pickems read (countdown cross-check)
HOTSPAWN_CIK_PAYLOAD = "2026-10-14T02:18:56Z"   # scheduled CI capture (slate/data/fixtures.csv)

EGW_MATCHES = "https://egamersworld.com/counterstrike/matches"
EGW_READ = "2026-10-14T02:48:00Z"  # full listing read (chunks 0-9, 02:40-02:48Z); values unchanged since 01:48Z
EGW_PREVIOUS_READ = "2026-10-14T01:48:00Z"  # session 8944bb84 independent earlier read

PINNACLE_URL = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
PINNACLE_READ = "2026-10-14T01:48:00Z"  # direct guest API reads, session 8944bb84 (cross-referenced)

PM_BASE = "https://polymarket.com/esports/cs2/cct-europe"
PM_READ = "2026-10-14T02:46:00Z"  # view-only read (US geo block; banner non-blocking)

CALIBRATION_FILE = ROOT / "model" / "input" / "vrs" / "calibration.json"
K = 0.4568  # calibration.json: adopted=true, k_published (re-checked at build time if file present)

# ----------------------------------------------------------------------------- fixtures
# Open Hotspawn CS2 pick'em slate captured 2026-10-14 (see PF-06: the site's displayed
# countdowns run UTC-4; the payload epochs below are the truth). Team order is
# Hotspawn's (team_a is the first-listed team). Lock = start - 360s (verified in the
# payload for all 28 rows, see PF-08). No Hotspawn crowd fields are recorded here.
FIXTURES: list[dict] = [
    # id, team_a, team_b, tournament, tier, points, start_utc (payload epoch)
    {"mid": "1081111", "a": "Enjoy", "b": "B8 Academy", "tourney": "CCT Europe 2026 Series #12 Closed Qualifier", "tier": "C", "pts": "2", "start": "2026-10-14T08:00:00Z"},
    {"mid": "1079621", "a": "Gothic", "b": "Lavked", "tourney": "CCT Europe 2026 Series #11", "tier": "B", "pts": "3", "start": "2026-10-14T08:00:00Z"},
    {"mid": "1080176", "a": "9z", "b": "Aurora", "tourney": "Thunderpick World Championship 2026", "tier": "S", "pts": "7", "start": "2026-10-14T08:30:00Z"},
    {"mid": "1079438", "a": "Astralis", "b": "Sashi", "tourney": "Stake Pulse Beat III", "tier": "B", "pts": "3", "start": "2026-10-14T10:00:00Z"},
    {"mid": "1079439", "a": "HOTU", "b": "Fnatic", "tourney": "Stake Pulse Beat III", "tier": "B", "pts": "3", "start": "2026-10-14T10:00:00Z"},
    {"mid": "1081112", "a": "Banda chuya", "b": "6666", "tourney": "CCT Europe 2026 Series #12 Closed Qualifier", "tier": "C", "pts": "2", "start": "2026-10-14T11:00:00Z"},
    {"mid": "1079622", "a": "ex-RUSTEC", "b": "mellren", "tourney": "CCT Europe 2026 Series #11", "tier": "B", "pts": "3", "start": "2026-10-14T11:00:00Z"},
    {"mid": "1080177", "a": "Falcons", "b": "Ninjas in Pyjamas", "tourney": "Thunderpick World Championship 2026", "tier": "S", "pts": "7", "start": "2026-10-14T11:00:00Z"},
    {"mid": "1080178", "a": "Legacy", "b": "PARIVISION", "tourney": "Thunderpick World Championship 2026", "tier": "S", "pts": "7", "start": "2026-10-14T13:30:00Z"},
    {"mid": "1081113", "a": "Ryvex", "b": "PCIFIC", "tourney": "CCT Europe 2026 Series #12 Closed Qualifier", "tier": "C", "pts": "2", "start": "2026-10-14T14:00:00Z"},
    {"mid": "1079623", "a": "G2 Ares", "b": "The Last Resort", "tourney": "CCT Europe 2026 Series #11", "tier": "B", "pts": "3", "start": "2026-10-14T14:00:00Z"},
    {"mid": "1080179", "a": "FURIA", "b": "BetBoom", "tourney": "Thunderpick World Championship 2026", "tier": "S", "pts": "7", "start": "2026-10-14T16:00:00Z"},
    {"mid": "1079624", "a": "FORZE Reload", "b": "LFO 10", "tourney": "CCT Europe 2026 Series #11", "tier": "B", "pts": "3", "start": "2026-10-14T17:00:00Z"},
    {"mid": "1080279", "a": "WROTBERRY", "b": "EAC", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T08:00:00Z"},
    {"mid": "1079440", "a": "MIBR", "b": "BC.Game", "tourney": "Stake Pulse Beat III", "tier": "B", "pts": "3", "start": "2026-10-15T10:00:00Z"},
    {"mid": "1079442", "a": "Heroic", "b": "Envy", "tourney": "Stake Pulse Beat III", "tier": "B", "pts": "3", "start": "2026-10-15T10:00:00Z"},
    {"mid": "1080280", "a": "ENCE", "b": "BOJONG", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T10:00:00Z"},
    {"mid": "1080281", "a": "WROTBERRY", "b": "ENCE", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T12:00:00Z"},
    {"mid": "1080282", "a": "EAC", "b": "BOJONG", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T14:00:00Z"},
    {"mid": "1080283", "a": "WROTBERRY", "b": "BOJONG", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T16:00:00Z"},
    {"mid": "1080284", "a": "EAC", "b": "ENCE", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-15T18:00:00Z"},
    {"mid": "1080285", "a": "Voca", "b": "Phantom", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T08:00:00Z"},
    {"mid": "1080286", "a": "HAVU", "b": "RoundsGG", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T10:00:00Z"},
    {"mid": "1080287", "a": "Voca", "b": "HAVU", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T12:00:00Z"},
    {"mid": "1081120", "a": "mellren", "b": "Privateer", "tourney": "CCT Europe 2026 Series #12 Closed Qualifier", "tier": "C", "pts": "2", "start": "2026-10-16T14:00:00Z"},
    {"mid": "1080288", "a": "Phantom", "b": "RoundsGG", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T14:00:00Z"},
    {"mid": "1080289", "a": "RoundsGG", "b": "Voca", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T16:00:00Z"},
    {"mid": "1080290", "a": "Phantom", "b": "HAVU", "tourney": "Elisa BreakOut Series 2", "tier": "C", "pts": "2", "start": "2026-10-16T18:00:00Z"},
]

# Hotspawn permalink per fixture. The 5 CCT Series #12 Play-In fixtures were added
# after Hotspawn's permalink generation and have no /matches/ permalink (repo
# finding IRREG-01); their row links go to the CS2 pick'em lobby instead.
HOTSPAWN_PERMALINKS: dict[str, str] = {
    "1079621": "https://www.hotspawn.com/matches/gothic-vs-lavked-cct-europe-2026-series-11-1079621",
    "1080176": "https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176",
    "1079438": "https://www.hotspawn.com/matches/astralis-vs-sashi-stake-pulse-beat-iii-1079438",
    "1079439": "https://www.hotspawn.com/matches/hotu-vs-fnatic-stake-pulse-beat-iii-1079439",
    "1079622": "https://www.hotspawn.com/matches/ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622",
    "1080177": "https://www.hotspawn.com/matches/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026-1080177",
    "1080178": "https://www.hotspawn.com/matches/legacy-vs-parivision-thunderpick-world-championship-2026-1080178",
    "1079623": "https://www.hotspawn.com/matches/g2-ares-vs-the-last-resort-cct-europe-2026-series-11-1079623",
    "1080179": "https://www.hotspawn.com/matches/furia-vs-betboom-thunderpick-world-championship-2026-1080179",
    "1079624": "https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624",
    "1079440": "https://www.hotspawn.com/matches/mibr-vs-bcgame-stake-pulse-beat-iii-1079440",
    "1079442": "https://www.hotspawn.com/matches/heroic-vs-envy-stake-pulse-beat-iii-1079442",
}
# (all other open fixtures: no permalink -> lobby link)

# Official HLTV match pages, verified 2026-10-14 (session 8944bb84, 02:26Z cross-check):
# each page states the series format (BO1/BO3) and the active lineups.
HLTV_MATCHES: dict[str, dict] = {
    "1081111": {"hid": "2399461", "url": "https://www.hltv.org/matches/2399461/enjoy-vs-b8-academy-cct-2026-europe-series-12-closed-qualifier", "fmt": "BO3"},
    "1079621": {"hid": "2399298", "url": "https://www.hltv.org/matches/2399298/gothic-vs-lavked-cct-2026-europe-series-11", "fmt": "BO3"},
    "1080176": {"hid": "2399384", "url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026", "fmt": "BO3"},
    "1079438": {"hid": "2399134", "url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii", "fmt": "BO3"},
    "1079439": {"hid": "2399135", "url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii", "fmt": "BO3"},
    "1081112": {"hid": "2399462", "url": "https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier", "fmt": "BO3"},
    "1079622": {"hid": "2399299", "url": "https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11", "fmt": "BO3"},
    "1080177": {"hid": "2399385", "url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026", "fmt": "BO3"},
    "1080178": {"hid": "2399386", "url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026", "fmt": "BO3"},
    "1081113": {"hid": "2399463", "url": "https://www.hltv.org/matches/2399463/pcific-vs-ryvex-cct-2026-europe-series-12-closed-qualifier", "fmt": "BO3"},
    "1079623": {"hid": "2399300", "url": "https://www.hltv.org/matches/2399300/g2-ares-vs-the-last-resort-cct-2026-europe-series-11", "fmt": "BO3"},
    "1080179": {"hid": "2399387", "url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026", "fmt": "BO3"},
    "1079624": {"hid": "2399301", "url": "https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11", "fmt": "BO3"},
    "1080279": {"hid": "2399418", "url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2", "fmt": "BO1"},
    "1079440": {"hid": "2399136", "url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii", "fmt": "BO3"},
    "1079442": {"hid": "2399137", "url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii", "fmt": "BO3"},
    "1080280": {"hid": "2399419", "url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2", "fmt": "BO1"},
    "1080281": {"hid": "2399420", "url": "https://www.hltv.org/matches/2399420/wbt-vs-ence-elisa-breakout-series-2", "fmt": "BO1"},
    "1080282": {"hid": "2399421", "url": "https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2", "fmt": "BO1"},
    "1080283": {"hid": "2399422", "url": "https://www.hltv.org/matches/2399422/wbt-vs-bojong-elisa-breakout-series-2", "fmt": "BO1"},
    "1080284": {"hid": "2399423", "url": "https://www.hltv.org/matches/2399423/eac-vs-ence-elisa-breakout-series-2", "fmt": "BO1"},
    "1080285": {"hid": "2399424", "url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2", "fmt": "BO1"},
    "1080286": {"hid": "2399425", "url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2", "fmt": "BO1"},
    "1080287": {"hid": "2399426", "url": "https://www.hltv.org/matches/2399426/voca-vs-havu-elisa-breakout-series-2", "fmt": "BO1"},
    "1081120": {"hid": "2399471", "url": "https://www.hltv.org/matches/2399471/mellren-vs-privateer-cct-2026-europe-series-12-closed-qualifier", "fmt": "BO3"},
    "1080288": {"hid": "2399427", "url": "https://www.hltv.org/matches/2399427/phantom-vs-rounds-elisa-breakout-series-2", "fmt": "BO1"},
    "1080289": {"hid": "2399428", "url": "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2", "fmt": "BO1"},
    "1080290": {"hid": "2399429", "url": "https://www.hltv.org/matches/2399429/phantom-vs-havu-elisa-breakout-series-2", "fmt": "BO1"},
}

# ----------------------------------------------------------------------------- teams
# Verified team ratings (source of record: data/8944bb84/ratings.csv, verified
# 2026-10-14T02:26:00Z line by line against the 2026-10-05 VRS file + HLTV match
# pages; every row below carries its own line anchor). Duplicate same-name VRS rows
# were disambiguated via official 5-man lineups (see resolution notes).
def _v(url_line: int, details: str = "") -> dict:
    return {
        "vrs_url": (f"{VRS_BASE_URL}?plain=1#L{url_line}" if url_line else VRS_BASE_URL),
        "vrs_details_url": (f"{VRS_DETAILS_BASE}details/2026_10_05/{details}" if details else ""),
    }

TEAMS: dict[str, dict] = {
    # --- open-slate teams -----------------------------------------------------
    "Enjoy": {"rank": "138", "pts": "871", "line": 143, "det": "0138--enjoy--kurosa-nbl-roxesz-sh1geo-zazzer.md", "h_rank": "199", "h_pts": "3", "h_id": "4246", "h_url": "https://www.hltv.org/team/4246/enjoy", "res": "VERIFIED: VRS name + HLTV roster (3/5 core kurosa, nbl, sh1geo on HLTV match 2399461)", "flags": ""},
    "B8 Academy": {"rank": "261", "pts": "631", "line": 266, "det": "0261--b8_academy--k1n-r0se-segukawa-sherman.md", "h_rank": "229", "h_pts": "1", "h_id": "13732", "h_url": "https://www.hltv.org/team/13732/b8-academy", "res": "VERIFIED: VRS name + HLTV roster (4/4 core on HLTV match 2399461)", "flags": ""},
    "Gothic": {"rank": "211", "pts": "705", "line": 216, "det": "0211--gothic--get_jeka-raijin-ryujin-shg-synyx.md", "h_rank": "", "h_pts": "", "h_id": "14014", "h_url": "https://www.hltv.org/team/14014/gothic", "res": "VERIFIED: VRS name + HLTV match 2399298 lineup (3/5 core Get_Jeka, Ryujin, shg)", "flags": ""},
    "Lavked": {"rank": "143", "pts": "862", "line": 148, "det": "0143--lavked--danylo-kryvoruchko-matthew-moody-robin-ruiz-van-dam.md", "h_rank": "140", "h_pts": "5", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (4 shared players)", "flags": ""},
    "9z": {"rank": "17", "pts": "1543", "line": 22, "det": "", "h_rank": "17", "h_pts": "124", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Aurora": {"rank": "9", "pts": "1716", "line": 14, "det": "", "h_rank": "6", "h_pts": "461", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Astralis": {"rank": "10", "pts": "1674", "line": 15, "det": "", "h_rank": "15", "h_pts": "133", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (3 shared players)", "flags": ""},
    "Sashi": {"rank": "73", "pts": "1131", "line": 78, "det": "0073--sashi--acor-anlelele-cabbi-mistr-zyphon.md", "h_rank": "", "h_pts": "", "h_id": "11712", "h_url": "https://www.hltv.org/team/11712/sashi", "res": "VERIFIED: VRS name + HLTV match 2399134 lineup (3/5 core acoR, Anlelele, Zyphon)", "flags": ""},
    "HOTU": {"rank": "31", "pts": "1437", "line": 36, "det": "", "h_rank": "41", "h_pts": "39", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Fnatic": {"rank": "35", "pts": "1417", "line": 40, "det": "", "h_rank": "36", "h_pts": "43", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Banda chuya": {"rank": "165", "pts": "801", "line": 170, "det": "0165--banda_chuya--adrien-ezox-maaryy-showk-tomiko.md", "h_rank": "", "h_pts": "", "h_id": "13900", "h_url": "https://www.hltv.org/team/13900/banda-chuya", "res": "VERIFIED: VRS name + HLTV match 2399462 lineup (5/5 exact match; disambiguates #165 from #373)", "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED"},
    "6666": {"rank": "127", "pts": "923", "line": 132, "det": "0127--6666--amster-denzyskl-klio-rendysk-sck.md", "h_rank": "80", "h_pts": "10", "h_id": "13882", "h_url": "https://www.hltv.org/team/13882/6666", "res": "VERIFIED: VRS name + HLTV roster (5 shared players; disambiguates #127 from #368)", "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED"},
    "ex-RUSTEC": {"rank": "92", "pts": "1066", "line": 97, "det": "0092--ex-rustec--brilliance-glowiing-shalfey-yiksrezo-youka.md", "h_rank": "79", "h_pts": "10", "h_id": "13901", "h_url": "https://www.hltv.org/team/13901/ex-rustec", "res": "VERIFIED: VRS #92 (1066 pts) + HLTV #79 (3/5 core + live VRS badge #93 on match 2399299; disambiguates #92 from #152)", "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED"},
    "mellren": {"rank": "125", "pts": "932", "line": 130, "det": "0125--mellren--lollipop21k-maksilvl-mdl-menddel-shootic.md", "h_rank": "94", "h_pts": "9", "h_id": "13759", "h_url": "https://www.hltv.org/team/13759/mellren", "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Falcons": {"rank": "6", "pts": "1843", "line": 11, "det": "", "h_rank": "5", "h_pts": "488", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Ninjas in Pyjamas": {"rank": "18", "pts": "1534", "line": 23, "det": "", "h_rank": "26", "h_pts": "74", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Legacy": {"rank": "2", "pts": "1931", "line": 7, "det": "", "h_rank": "7", "h_pts": "379", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "PARIVISION": {"rank": "36", "pts": "1411", "line": 41, "det": "", "h_rank": "11", "h_pts": "178", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (4 shared players)", "flags": ""},
    "Ryvex": {"rank": "207", "pts": "714", "line": 212, "det": "0207--ryvex--jeyn-n0r1-oskvr-swaggy-tvs.md", "h_rank": "181", "h_pts": "3", "h_id": "13974", "h_url": "https://www.hltv.org/team/13974/ryvex", "res": "VERIFIED: VRS name + HLTV roster (4/5 core jeyN, N0R1, oskvr, swaggy on HLTV match 2399463)", "flags": ""},
    "PCIFIC": {"rank": "139", "pts": "870", "line": 144, "det": "0139--pcific--jresy-logician-lugsen-oyesil-scollen.md", "h_rank": "135", "h_pts": "5", "h_id": "13054", "h_url": "https://www.hltv.org/team/13054/pcific", "res": "VERIFIED: VRS name + HLTV roster (4 shared players; identity note PF-03: EGW/Polymarket list 'WRAITH PCIFIC' for this fixture)", "flags": "FL-IDENTITY-PCIFIC"},
    "G2 Ares": {"rank": "129", "pts": "913", "line": 134, "det": "0129--g2-ares--caca-sch1ene-tacolara-w4czz-zewex.md", "h_rank": "103", "h_pts": "8", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "The Last Resort": {"rank": "126", "pts": "926", "line": 131, "det": "0126--the-last-resort--ab0r1gen-emile-ferrari-kubik-marcin.md", "h_rank": "159", "h_pts": "4", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "FURIA": {"rank": "7", "pts": "1829", "line": 12, "det": "", "h_rank": "4", "h_pts": "527", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "BetBoom": {"rank": "11", "pts": "1596", "line": 16, "det": "", "h_rank": "14", "h_pts": "148", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "FORZE Reload": {"rank": "84", "pts": "1100", "line": 89, "det": "0084--forze-reload--heckbnk-kaide-kusme-lack1-yumsan.md", "h_rank": "75", "h_pts": "11", "h_id": "12857", "h_url": "https://www.hltv.org/team/12857/forze-reload", "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "LFO 10": {"rank": "", "pts": "", "line": 0, "det": "", "h_rank": "", "h_pts": "", "h_id": "14084", "h_url": "https://www.hltv.org/team/14084/lfo-10", "res": "UNVERIFIED in 2026-10-05 VRS by name (HLTV match 2399301 lists LFO 10 at live VRS #169 with 4-man core dottie, flaw, Sapec, tevsii shared with VRS #156 Entropy, 813 pts). Official line left BLANK; research line only, see PF-02.", "flags": "FL-UNVERIFIED-TEAM"},
    "WROTBERRY": {"rank": "60", "pts": "1201", "line": 65, "det": "", "h_rank": "109", "h_pts": "7", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: fixture-matched alias WBT -> HLTV roster -> VRS (HLTV match slugs list 'wbt')", "flags": "FL-ALIAS-WBT"},
    "EAC": {"rank": "103", "pts": "1035", "line": 108, "det": "", "h_rank": "110", "h_pts": "7", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players; HLTV slug 'ea-copenhagen')", "flags": ""},
    "ENCE": {"rank": "105", "pts": "1025", "line": 110, "det": "", "h_rank": "114", "h_pts": "7", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "BOJONG": {"rank": "363", "pts": "463", "line": 368, "det": "", "h_rank": "220", "h_pts": "2", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "MIBR": {"rank": "12", "pts": "1585", "line": 17, "det": "", "h_rank": "12", "h_pts": "163", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "BC.Game": {"rank": "50", "pts": "1318", "line": 55, "det": "", "h_rank": "70", "h_pts": "12", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Heroic": {"rank": "15", "pts": "1550", "line": 20, "det": "", "h_rank": "30", "h_pts": "60", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Envy": {"rank": "21", "pts": "1500", "line": 26, "det": "", "h_rank": "20", "h_pts": "96", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: HLTV roster -> VRS (name change confirmed on HLTV match 2399137)", "flags": ""},
    "Voca": {"rank": "68", "pts": "1182", "line": 73, "det": "", "h_rank": "59", "h_pts": "16", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "Phantom": {"rank": "72", "pts": "1147", "line": 77, "det": "", "h_rank": "88", "h_pts": "9", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "HAVU": {"rank": "124", "pts": "937", "line": 129, "det": "0124--havu--aaron-bjorn-david-jon-matias.md", "h_rank": "118", "h_pts": "7", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: VRS name + HLTV roster (5 shared players)", "flags": ""},
    "RoundsGG": {"rank": "310", "pts": "548", "line": 315, "det": "", "h_rank": "237", "h_pts": "1", "h_id": "", "h_url": HLTV_RANKING_URL, "res": "VERIFIED: fixture-matched alias 'ROUNDS' -> HLTV roster -> VRS (HLTV match slugs list 'rounds')", "flags": "FL-ALIAS-ROUNDS"},
    "Privateer": {"rank": "271", "pts": "608", "line": 276, "det": "0271--privateer--ariant0-frazehh-jaustere-m1n1mal-prime.md", "h_rank": "226", "h_pts": "1", "h_id": "13914", "h_url": "https://www.hltv.org/team/13914/privateer", "res": "VERIFIED: VRS name + HLTV roster (4/5 core Ariant0, Frazehh, M1n1maL, Prime on HLTV match 2399471)", "flags": ""},
    # --- research anchor for LFO 10 (PF-02) ------------------------------------
    "Entropy (research anchor)": {"rank": "156", "pts": "813", "line": 161, "det": "0156--entropy--dottie-flaw-sapec-tevsii.md", "h_rank": "", "h_pts": "", "h_id": "", "h_url": "", "res": "VRS #156 Entropy 813 pts — roster anchor for LFO 10 via HLTV match 2399301 (4 shared players). RESEARCH USE ONLY.", "flags": "RESEARCH-ONLY"},
}

# Research mapping for the single unrated team (published ONLY as labelled research,
# flagged PF-02). LFO 10 (HLTV 14084) plays HLTV match 2399301 with the 4-man core
# (dottie, flaw, Sapec, tevsii) of VRS #156 Entropy (813 pts); Valve's own
# model/team.js treats rosters sharing >= 3 players as the same team entity.
RESEARCH_POINTS = {"LFO 10": {"pts": "813", "basis": "VRS #156 Entropy 813 pts (roster-mapped, HLTV match 2399301)", "url": _v(161)["vrs_url"]}}

# ----------------------------------------------------------------------------- market lines
# EGW (bc.game) — primary outside line, read 2026-10-14T02:48:00Z (listing chunks 0-9,
# 02:40-02:48Z; values identical to the independent 01:48Z read by session 8944bb84).
# Odds are oriented to Hotspawn team order (team_a / team_b). 1.80/1.80 = unpriced
# placeholder, rejected as a line (blank + flag), never treated as 50/50.
EGW_LINES: dict[str, dict] = {
    "1081111": {"oa": "1.52", "ob": "2.30", "url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7", "note": ""},
    "1079621": {"oa": "2.05", "ob": "1.64", "url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B", "note": ""},
    "1080176": {"oa": "3.87", "ob": "1.20", "url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb", "note": ""},
    "1079438": {"oa": "1.09", "ob": "6.33", "url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z", "note": ""},
    "1079439": {"oa": "1.89", "ob": "1.81", "url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC", "note": ""},
    "1081112": {"oa": "", "ob": "", "url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y", "note": "EGW displays 1.80/1.80 placeholder — rejected, line left blank (PF-01)"},
    "1079622": {"oa": "1.40", "ob": "2.68", "url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK", "note": ""},
    "1080177": {"oa": "1.19", "ob": "3.95", "url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/falcons-vs-nip-QSa-aeOIR", "note": ""},
    "1080178": {"oa": "1.66", "ob": "2.07", "url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/legacy-vs-parivision--TTc59QUDJ", "note": ""},
    "1081113": {"oa": "", "ob": "", "url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3", "note": "EGW displays 1.80/1.80 placeholder (two rows: 'PCIFIC Espor' and 'WRAITH PCIFIC' vs Ryvex) — rejected, line left blank (PF-01, PF-03)"},
    "1079623": {"oa": "1.465", "ob": "2.436", "url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L", "note": ""},
    "1080179": {"oa": "1.40", "ob": "2.86", "url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH", "note": ""},
    "1079624": {"oa": "", "ob": "", "url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3", "note": "EGW displays 1.80/1.80 placeholder, opponent name blank on EGW — rejected, line left blank (PF-01, PF-04)"},
    "1080279": {"oa": "2.01", "ob": "1.69", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ea-copenhagen-hSC7a2mtP", "note": ""},
    "1079440": {"oa": "1.62", "ob": "2.09", "url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX", "note": ""},
    "1079442": {"oa": "1.45", "ob": "2.47", "url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC", "note": ""},
    "1080280": {"oa": "1.30", "ob": "3.17", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg", "note": ""},
    "1080281": {"oa": "1.62", "ob": "2.107", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS", "note": ""},
    "1080282": {"oa": "1.19", "ob": "4.02", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5", "note": ""},
    "1080283": {"oa": "1.21", "ob": "3.99", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6", "note": ""},
    "1080284": {"oa": "1.51", "ob": "2.35", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT", "note": ""},
    "1080285": {"oa": "1.87", "ob": "1.77", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja", "note": ""},
    "1080286": {"oa": "1.19", "ob": "4.02", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9", "note": ""},
    "1080287": {"oa": "1.38", "ob": "2.70", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP", "note": ""},
    "1081120": {"oa": "", "ob": "", "url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/mellren-vs-privateer-gaming-ASh_MyDBS", "note": "EGW displays 1.80/1.80 placeholder — rejected, line left blank (PF-01)"},
    "1080288": {"oa": "1.08", "ob": "6.94", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU", "note": ""},
    "1080289": {"oa": "6.40", "ob": "1.063", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U", "note": "EGW lists the fixture Voca vs ROUNDS (1.063/6.400); odds oriented here to Hotspawn order (RoundsGG first)"},
    "1080290": {"oa": "1.36", "ob": "2.87", "url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586", "note": ""},
}

# Pinnacle (direct guest API, session 8944bb84, 2026-10-14T01:48:00Z) — cross-check.
PINNACLE_LINES: dict[str, dict] = {
    "1080176": {"oa": "3.550", "ob": "1.307", "event": "1638111785"},
    "1079439": {"oa": "1.990", "ob": "1.800", "event": "1637867148"},
    "1080177": {"oa": "1.254", "ob": "4.010", "event": "1638111674"},
    "1080178": {"oa": "1.654", "ob": "2.260", "event": "1638111786"},
    "1080179": {"oa": "1.364", "ob": "3.180", "event": "1638111787"},
    "1079440": {"oa": "1.637", "ob": "2.230", "event": "1637936745"},
    "1079442": {"oa": "1.469", "ob": "2.620", "event": "1637999450"},
}

# Polymarket (view-only read 2026-10-14T02:46:00Z; US geo block, banner non-blocking).
# 'x' values are the displayed decimal odds; cents are the share prices.
PM_LINES: dict[str, dict] = {
    "1081111": {"xa": "1.61", "xb": "2.44", "ca": "62", "cb": "41", "vol": "251.82", "slug": "cs2-enjoy-b8acad-2026-10-14", "note": ""},
    "1079621": {"xa": "1.96", "xb": "1.96", "ca": "51", "cb": "51", "vol": "266", "slug": "cs2-gothic-lavked-2026-10-14", "note": "market near coin-flip"},
    "1079622": {"xa": "1.52", "xb": "2.78", "ca": "66", "cb": "36", "vol": "9600", "slug": "cs2-rustec-mellre-2026-10-14", "note": ""},
    "1079623": {"xa": "1.49", "xb": "2.78", "ca": "67", "cb": "36", "vol": "140.98", "slug": "cs2-g2a-tlr-2026-10-14", "note": ""},
    "1081113": {"xa": "1.16", "xb": "5.56", "ca": "86", "cb": "18", "vol": "38.66", "slug": "cs2-wraith-ryvex-2026-10-14", "note": "listed as WRAITH PCIFIC vs Ryvex — identity PF-03; cross-check only (gap vs own line flagged)"},
    "1079624": {"xa": "1.11", "xb": "6.25", "ca": "90", "cb": "16", "vol": "313.86", "slug": "cs2-forzer-skr2-2026-10-14", "note": "opponent mismatch: Polymarket lists 'Sökerorg', Hotspawn lists 'LFO 10' (PF-04) — NOT used as a line"},
    "1081120": {"xa": "1.06", "xb": "1.06", "ca": "94", "cb": "94", "vol": "0", "slug": "cs2-mellre-pg5-2026-10-16", "note": "degenerate market (both sides 94¢, $0 volume) — NOT used as a line (PF-05)"},
}
PM_NON_SLAte_MARKETS = [  # PM CCT Europe markets with no open Hotspawn fixture (context only)
    ("Saint Sinners vs maybe", "cs2-ssins-maybe-2026-10-14", "1.09x / 2.04x", "$0"),
    ("Lilmix vs Revise", "cs2-lilmix-revise-2026-10-16", "1.06x / 1.10x", "$0"),
    ("MORROW vs ILLYRIANS", "cs2-morrow-ill4-2026-10-16", "1.06x / 1.06x", "$0"),
]

# Locked / completed current-week matches (context; picks not offered — lock has passed).
LOCKED_WEEK: list[dict] = [
    {"mid": "1079620", "a": "Black Phoenix", "b": "6666", "tourney": "CCT Europe 2026 Series #11", "tier": "B", "pts": "3", "start": "2026-10-13T17:00:00Z", "lock": "2026-10-13T16:54:00Z", "fmt": "BO3", "result": "Black Phoenix 2 – 0 6666 (Final)", "hltv": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11"},
    {"mid": "1081076", "a": "ex-Keyd Stars", "b": "Galorys", "tourney": "ESL Challenger League Season 52: South America - Cup #3", "tier": "B", "pts": "3", "start": "2026-10-13T21:00:00Z", "lock": "2026-10-13T20:54:00Z", "fmt": "BO3", "result": "ex-Keyd Stars 0 – 2 Galorys (Final)", "hltv": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3"},
    {"mid": "1081105", "a": "SUKEBAN", "b": "your end", "tourney": "CCT South America 2026 Series #7", "tier": "C", "pts": "2", "start": "2026-10-13T22:00:00Z", "lock": "2026-10-13T21:54:00Z", "fmt": "BO3", "result": "your end 1 – 0 SUKEBAN (default/forfeit)", "hltv": "https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-series-7"},
    {"mid": "1079546", "a": "Zomblers", "b": "Overtake Sector", "tourney": "ESL Challenger League Season 52: North America - Cup #3", "tier": "B", "pts": "3", "start": "2026-10-14T01:00:00Z", "lock": "2026-10-14T00:54:00Z", "fmt": "BO3", "result": "LIVE at snapshot: Overtake Sector 1 – 0 Zomblers after Map 1 (13–8)", "hltv": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3"},
]

# ----------------------------------------------------------------------------- flags
FLAGS: list[dict] = [
    {"id": "PF-01", "sev": "MEDIUM", "subject": "EGW 1.80/1.80 placeholders rejected as lines (4 fixtures)",
     "detail": "EGamersWorld (bc.game feed) displays the unpriced placeholder 1.80/1.80 for #1081112 Banda chuya vs 6666, #1081113 Ryvex vs PCIFIC (two rows), #1079624 FORZE Reload vs LFO 10 (opponent name also blank on EGW) and #1081120 mellren vs Privateer Gaming. An equal placeholder carries no market information: it is NOT treated as 50/50. These rows instead carry our originated line (all four teams/ rosters verified) or, for LFO 10, the labelled research line.",
     "links": [EGW_MATCHES]},
    {"id": "PF-02", "sev": "HIGH", "subject": "LFO 10 unverified in the 2026-10-05 VRS file — research line only (#1079624)",
     "detail": "LFO 10 (HLTV team 14084, roster Jackinho, Sapec, flaw, dottie, tvs) is absent by name from Valve's standings_global_2026_10_05.md, so its official line is left BLANK (zero-inference rule). Research anchor: HLTV match 2399301 lists LFO 10 at live VRS #169 with the 4-man core (dottie, flaw, Sapec, tevsii) of VRS #156 Entropy (813 pts); Valve's own model/team.js treats rosters sharing >= 3 players as one team entity. The published row therefore shows a FORZE Reload vs 'Entropy-mapped 813 pts' line clearly labelled RESEARCH (roster-mapped) and flagged for review. FORZE Reload (VRS #84, 1100 pts) is verified.",
     "links": ["https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11", "https://www.hltv.org/team/14084/lfo-10", _v(161)["vrs_url"], "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/" + VRS_COMMIT + "/model/team.js"]},
    {"id": "PF-03", "sev": "MEDIUM", "subject": "PCIFIC identity: Hotspawn 'PCIFIC' vs EGW/Polymarket 'WRAITH PCIFIC' (#1081113)",
     "detail": "Hotspawn lists 'PCIFIC'; EGW shows two placeholder rows ('PCIFIC Espor' and 'WRAITH PCIFIC' vs Ryvex, same 14:00Z slot); Polymarket prices 'WRAITH PCIFIC vs Ryvex' at 1.16x/5.56x (86¢/18¢, $38.66 vol). HLTV match 2399463 (the official fixture page for this exact Hotspawn slot, CCT Europe #12 Closed Qualifier) lists PCIFIC vs Ryvex, and the VRS #139 PCIFIC row (870 pts) matches its HLTV roster (4 shared players) — the most likely reading is a rename/sponsor variant, but this is NOT confirmed, so the row's pick follows our originated line (PCIFIC 870 vs Ryvex 714 -> 65.0%) and the Polymarket quote is shown as a cross-check only. Cross-check gap: own line PCIFIC 65.0% vs PM 82.7% (17.7 pp) — same direction, flagged FL-CROSS-GAP.",
     "links": ["https://www.hltv.org/matches/2399463/pcific-vs-ryvex-cct-2026-europe-series-12-closed-qualifier", PM_BASE + "/cs2-wraith-ryvex-2026-10-14", "https://www.hltv.org/team/13054/pcific"]},
    {"id": "PF-04", "sev": "HIGH", "subject": "Opponent mismatch on FORZE Reload's only outside market (#1079624)",
     "detail": "Polymarket's only market for this slot is 'FORZE Reload vs Sökerorg' (1.11x/6.25x, 90¢/16¢, $313.86 vol) while Hotspawn lists 'LFO 10' and EGW leaves the opponent name blank. Because the opponent identity conflicts, the Polymarket quote is NOT used as the line for this fixture; it is published as context only. The pick follows the labelled research line (FORZE Reload).",
     "links": [PM_BASE + "/cs2-forzer-skr2-2026-10-14", "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3"]},
    {"id": "PF-05", "sev": "LOW", "subject": "Polymarket mellren vs Privateer Gaming market is degenerate (#1081120)",
     "detail": "The PM market shows both outcomes at 94¢ (1.06x/1.06x) with $0.00 volume — a non-functional quote. Not used; the row follows our originated line (mellren 932 vs Privateer 608).",
     "links": [PM_BASE + "/cs2-mellre-pg5-2026-10-16"]},
    {"id": "PF-06", "sev": "INFO", "subject": "Hotspawn countdown display runs UTC-4 — payload epochs are the truth",
     "detail": "The /cs2-pickems cards display start times in a UTC-4 frame: the 08:00:00Z Enjoy vs B8 Academy card showed 'Oct 14, 04:00' with a lock countdown of 05:21:21 while the server clock read ~02:38:39Z — i.e. displayed 04:00 = lock 07:54Z − 05:21:21, confirming display = UTC-4. All start/lock times on this board are the payload epochs (cross-checked by the scheduled CI capture at 02:18:56Z and the independent 8944bb84 verification). Readers comparing against the rendered cards should add 4 hours.",
     "links": [HOTSPAWN_CS2]},
    {"id": "PF-07", "sev": "INFO", "subject": "Polymarket read is view-only (US geo block)",
     "detail": "polymarket.com serves a 'trading blocked in the United States' banner to this reader; the market page content (prices, volumes) remains fully readable in view-only mode. Quotes were read from the CCT Europe tab (10 markets) and cross-referenced, not traded.",
     "links": [PM_BASE]},
    {"id": "PF-08", "sev": "INFO", "subject": "Lock rule: picks lock at start − 360s (verified)",
     "detail": "Every one of the 28 open fixtures carries lock_utc = start_utc − 360s in the Hotspawn payload (slate/data/fixtures.csv, CI capture 2026-10-14T02:18:56Z) and the live countdown cross-check on /cs2-pickems (02:38Z) is consistent with it. The pick you submit on Hotspawn must be in before the row's Lock (UTC).",
     "links": [HOTSPAWN_CS2]},
    {"id": "PF-09", "sev": "LOW", "subject": "Team-order note on #1080289 (RoundsGG vs Voca)",
     "detail": "EGW lists this fixture as 'Voca vs ROUNDS' (1.063 / 6.400). Odds on this board are oriented to Hotspawn's order (team_a = RoundsGG): RoundsGG 6.40 / Voca 1.063 -> 14.2% / 85.8% de-vigged. HLTV match 2399428 (Voca vs Rounds) confirms the fixture; the pick (Voca) is unaffected.",
     "links": ["https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U", "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2"]},
    {"id": "PF-10", "sev": "INFO", "subject": "Coverage context: 4 locked + 59 stale fixtures",
     "detail": "The current Hotspawn CS2 week also contains 4 locked/started fixtures (Black Phoenix vs 6666, ex-Keyd Stars vs Galorys, SUKEBAN vs your end [forfeit], Zomblers vs Overtake Sector [live at snapshot]) and Hotspawn's payload retains 59 stale June–July 2026 records. None are pickable; they are listed for completeness on the board's 'This week' section, and the 59 stale rows are retained (with sources) on the 8944bb84 full-coverage page.",
     "links": ["https://buffedlizard55-lab.github.io/MaltaProj1/oct14/coverage-all-91.html"]},
]

# ----------------------------------------------------------------------------- math
def p_map(pa: float, pb: float, k: float = K) -> float:
    """Map win probability for A from VRS points (calibrated logistic, repo-adopted k)."""
    return 1.0 / (1.0 + 10.0 ** (-k * (pa - pb) / 400.0))


def p_series(p: float, fmt: str) -> float:
    """Independent-map series transform. BO1: p; BO3: p^3 + 3p^2(1-p)."""
    if fmt == "BO1":
        return p
    if fmt == "BO3":
        return p * p * (3.0 - 2.0 * p)
    return p  # unknown format: no transform (flagged upstream)


def devig(oa: str, ob: str) -> tuple[float, float, float]:
    """Proportional de-vig. Returns (p_a_pct, p_b_pct, overround_pct) or (0,0,0) if blank."""
    if not oa or not ob:
        return 0.0, 0.0, 0.0
    ia, ib = 1.0 / float(oa), 1.0 / float(ob)
    tot = ia + ib
    return ia / tot * 100.0, ib / tot * 100.0, (tot - 1.0) * 100.0


def pct_pair(pa: float) -> tuple[str, str]:
    """Round to 1 dp so the pair sums to exactly 100.0."""
    a = round(pa, 1)
    a = min(max(a, 0.1), 99.9)
    return f"{a:.1f}", f"{100.0 - a:.1f}"


def conf(prob: float) -> str:
    if prob >= 70.0:
        return "OBVIOUS LOCK (≥70%)"
    if prob >= 60.0:
        return "STRONG PICK (60–69%)"
    if prob >= 55.0:
        return "SOLID LEAN (55–59%)"
    return "CLOSE TOSS-UP (<55%)"

# ----------------------------------------------------------------------------- rows
def build_rows() -> list[dict]:
    rows: list[dict] = []
    for fx in FIXTURES:
        mid, a, b = fx["mid"], fx["a"], fx["b"]
        start = fx["start"]
        lock = iso_shift(start, -360)
        ta, tb = TEAMS[a], TEAMS[b]
        hm = HLTV_MATCHES[mid]
        fmt = hm["fmt"]

        egw = EGW_LINES[mid]
        pa_e, pb_e, over = devig(egw["oa"], egw["ob"])
        pin = PINNACLE_LINES.get(mid)
        pa_p, pb_p, _ = (devig(pin["oa"], pin["ob"]) if pin else (0.0, 0.0, 0.0))
        pm = PM_LINES.get(mid)
        pm_use = bool(pm) and pm["note"].find("NOT used") == -1 and float(pm["vol"]) > 0
        pa_m, pb_m = 0.0, 0.0
        if pm and pm_use:
            ca, cb = float(pm["ca"]), float(pm["cb"])
            pa_m, pb_m = ca / (ca + cb) * 100.0, cb / (ca + cb) * 100.0

        # originated line
        research = a in RESEARCH_POINTS or b in RESEARCH_POINTS
        pts_a = RESEARCH_POINTS[a]["pts"] if a in RESEARCH_POINTS else ta["pts"]
        pts_b = RESEARCH_POINTS[b]["pts"] if b in RESEARCH_POINTS else tb["pts"]
        own_pa = own_pb = ""
        own_fav = ""
        map_pa = ""
        if pts_a and pts_b:
            pm_ = p_map(float(pts_a), float(pts_b))
            ps = p_series(pm_, fmt)
            own_pa, own_pb = pct_pair(ps * 100.0)
            own_fav = a if ps >= 0.5 else b
            map_pa = f"{pm_:.4f}"
        method = "BLANK — UNVERIFIED"
        if own_pa:
            method = ("RESEARCH (roster-mapped) — " if research else "") + \
                f"Own VRS model, calibrated k={K}, {fmt} transform"

        # pick
        flags: list[str] = []
        if not egw["oa"]:
            flags.append("PF-01")
        if research:
            flags.append("PF-02")
        if pm and not pm_use:
            flags.append("PF-05" if "degenerate" in pm["note"] else "PF-04")
        if ta.get("flags"):
            flags.append(ta["flags"])
        if tb.get("flags"):
            flags.append(tb["flags"])
        if not HOTSPAWN_PERMALINKS.get(mid):
            flags.append("FL-NO-PERMALINK")
        if mid == "1080289":
            flags.append("PF-09")

        if pa_e:
            pick, prob = (a, pa_e) if pa_e >= pb_e else (b, pb_e)
            basis = f"External market — EGW bc.game {egw['oa']}/{egw['ob']} de-vigged"
        elif own_pa:
            pick, prob = (a, float(own_pa)) if float(own_pa) >= float(own_pb) else (b, float(own_pb))
            basis = ("RESEARCH line (roster-mapped, flagged PF-02) — " if research else "") + \
                f"Own VRS model k={K}, {fmt}"
        else:
            pick, prob = "", 0.0
            basis = "NO PICK — FLAGGED"

        rows.append({
            "mid": mid, "a": a, "b": b, "tourney": fx["tourney"], "tier": fx["tier"],
            "pts": fx["pts"], "start": start, "lock": lock, "fmt": fmt,
            "hs_url": HOTSPAWN_PERMALINKS.get(mid, HOTSPAWN_CS2),
            "hs_kind": "match" if mid in HOTSPAWN_PERMALINKS else "lobby",
            "hltv_id": hm["hid"], "hltv_url": hm["url"],
            "egw": egw, "egw_pa": pa_e, "egw_pb": pb_e, "egw_over": over,
            "pin": pin, "pin_pa": pa_p, "pin_pb": pb_p,
            "pm": pm, "pm_pa": pa_m, "pm_pb": pb_m,
            "ta": ta, "tb": tb,
            "pts_a_eff": pts_a, "pts_b_eff": pts_b, "research": research,
            "map_pa": map_pa,
            "own_pa": own_pa, "own_pb": own_pb, "own_fav": own_fav, "method": method,
            "own_fair_odds_a": (f"{1.0 / (float(own_pa) / 100.0):.2f}" if own_pa else ""),
            "own_fair_odds_b": (f"{1.0 / (float(own_pb) / 100.0):.2f}" if own_pb else ""),
            "pick": pick, "pick_prob": prob, "basis": basis,
            "conf": conf(prob) if prob else "UNVERIFIED",
            "flags": sorted(set(f for f in flags if f)),
        })
    return rows


def iso_shift(iso: str, secs: int) -> str:
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    from datetime import timedelta
    return (t + timedelta(seconds=secs)).strftime("%Y-%m-%dT%H:%M:%SZ")

# ----------------------------------------------------------------------------- datasets
def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def write_datasets(rows: list[dict]) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    fx_fields = ["match_id", "team_a", "team_b", "tournament", "tier", "points",
                 "start_utc", "lock_utc", "series_format", "hltv_match_id", "hltv_match_url",
                 "hotspawn_match_url", "hotspawn_lobby_url"]
    write_csv(DATA_DIR / "fixtures.csv", [
        {"match_id": r["mid"], "team_a": r["a"], "team_b": r["b"], "tournament": r["tourney"],
         "tier": r["tier"], "points": r["pts"], "start_utc": r["start"], "lock_utc": r["lock"],
         "series_format": r["fmt"], "hltv_match_id": r["hltv_id"], "hltv_match_url": r["hltv_url"],
         "hotspawn_match_url": (r["hs_url"] if r["hs_kind"] == "match" else ""),
         "hotspawn_lobby_url": HOTSPAWN_CS2} for r in rows], fx_fields)

    team_names: list[str] = []
    for r in rows:
        for t in (r["a"], r["b"]):
            if t not in team_names:
                team_names.append(t)
    team_names.append("Entropy (research anchor)")
    tm_fields = ["team", "vrs_standing", "vrs_points", "vrs_line", "vrs_url", "vrs_details_url",
                 "hltv_rank", "hltv_points", "hltv_team_id", "hltv_url", "resolution", "flags"]
    write_csv(DATA_DIR / "teams.csv", [
        {"team": name, "vrs_standing": TEAMS[name]["rank"], "vrs_points": TEAMS[name]["pts"],
         "vrs_line": TEAMS[name]["line"], "vrs_url": _v(TEAMS[name]["line"])["vrs_url"],
         "vrs_details_url": _v(TEAMS[name]["line"], TEAMS[name]["det"])["vrs_details_url"],
         "hltv_rank": TEAMS[name]["h_rank"], "hltv_points": TEAMS[name]["h_pts"],
         "hltv_team_id": TEAMS[name]["h_id"], "hltv_url": TEAMS[name]["h_url"],
         "resolution": TEAMS[name]["res"], "flags": TEAMS[name]["flags"]}
        for name in team_names], tm_fields)

    ml_fields = ["match_id", "team_a", "team_b", "primary_book", "odds_a", "odds_b",
                 "overround_pct", "devig_p_a_pct", "devig_p_b_pct", "source_url", "captured_utc",
                 "secondary_book", "secondary_odds_a", "secondary_odds_b", "secondary_devig_p_a_pct",
                 "secondary_source_url", "secondary_captured_utc", "polymarket_odds", "polymarket_cents",
                 "polymarket_vol_usd", "polymarket_p_a_pct", "polymarket_source_url", "polymarket_captured_utc",
                 "note", "flags"]
    ml_rows = []
    for r in rows:
        pin = r["pin"]
        ml_rows.append({
            "match_id": r["mid"], "team_a": r["a"], "team_b": r["b"],
            "primary_book": ("bc.game (EGamersWorld)" if r["egw"]["oa"] else ""),
            "odds_a": r["egw"]["oa"], "odds_b": r["egw"]["ob"],
            "overround_pct": (f"{r['egw_over']:.2f}" if r["egw_over"] else ""),
            "devig_p_a_pct": (f"{r['egw_pa']:.1f}" if r["egw_pa"] else ""),
            "devig_p_b_pct": (f"{r['egw_pb']:.1f}" if r["egw_pb"] else ""),
            "source_url": r["egw"]["url"], "captured_utc": EGW_READ,
            "secondary_book": ("Pinnacle (direct)" if pin else ""),
            "secondary_odds_a": (pin["oa"] if pin else ""), "secondary_odds_b": (pin["ob"] if pin else ""),
            "secondary_devig_p_a_pct": (f"{r['pin_pa']:.1f}" if r["pin_pa"] else ""),
            "secondary_source_url": (f"https://guest.api.arcadia.pinnacle.com/0.1/matchups/{pin['event']}/markets/related/straight" if pin else ""),
            "secondary_captured_utc": (PINNACLE_READ if pin else ""),
            "polymarket_odds": (f"{r['pm']['xa']}x / {r['pm']['xb']}x" if r["pm"] else ""),
            "polymarket_cents": (f"{r['pm']['ca']}¢ / {r['pm']['cb']}¢" if r["pm"] else ""),
            "polymarket_vol_usd": (r["pm"]["vol"] if r["pm"] else ""),
            "polymarket_p_a_pct": (f"{r['pm_pa']:.1f}" if r["pm_pa"] else ""),
            "polymarket_source_url": (PM_BASE + "/" + r["pm"]["slug"] if r["pm"] else ""),
            "polymarket_captured_utc": (PM_READ if r["pm"] else ""),
            "note": r["egw"]["note"], "flags": ";".join(r["flags"]),
        })
    write_csv(DATA_DIR / "market_lines.csv", ml_rows, ml_fields)

    ol_fields = ["match_id", "team_a", "team_b", "series_format", "vrs_standing_a", "vrs_points_a",
                 "vrs_url_a", "vrs_standing_b", "vrs_points_b", "vrs_url_b",
                 "points_a_effective", "points_b_effective", "research", "map_p_a",
                 "own_p_a_pct", "own_p_b_pct", "own_fair_odds_a", "own_fair_odds_b", "method",
                 "hltv_match_url", "flags"]
    write_csv(DATA_DIR / "own_lines.csv", [
        {"match_id": r["mid"], "team_a": r["a"], "team_b": r["b"], "series_format": r["fmt"],
         "vrs_standing_a": r["ta"]["rank"], "vrs_points_a": r["ta"]["pts"],
         "vrs_url_a": _v(r["ta"]["line"])["vrs_url"],
         "vrs_standing_b": r["tb"]["rank"], "vrs_points_b": r["tb"]["pts"],
         "vrs_url_b": _v(r["tb"]["line"])["vrs_url"],
         "points_a_effective": r["pts_a_eff"], "points_b_effective": r["pts_b_eff"],
         "research": "yes" if r["research"] else "no",
         "map_p_a": r["map_pa"],
         "own_p_a_pct": r["own_pa"], "own_p_b_pct": r["own_pb"],
         "own_fair_odds_a": (f"{1.0 / (float(r['own_pa']) / 100.0):.2f}" if r["own_pa"] else ""),
         "own_fair_odds_b": (f"{1.0 / (float(r['own_pb']) / 100.0):.2f}" if r["own_pb"] else ""),
         "method": r["method"], "hltv_match_url": r["hltv_url"], "flags": ";".join(r["flags"])}
        for r in rows], ol_fields)

    pk_fields = ["match_id", "team_a", "team_b", "start_utc", "lock_utc", "series_format",
                 "published_p_a_pct", "published_p_b_pct", "pick", "pick_prob_pct",
                 "pick_basis", "confidence", "market_source_url", "own_model_k", "flags"]
    write_csv(DATA_DIR / "picks.csv", [
        {"match_id": r["mid"], "team_a": r["a"], "team_b": r["b"],
         "start_utc": r["start"], "lock_utc": r["lock"], "series_format": r["fmt"],
         "published_p_a_pct": (f"{r['egw_pa']:.1f}" if r["egw_pa"] else r["own_pa"]),
         "published_p_b_pct": (f"{r['egw_pb']:.1f}" if r["egw_pb"] else r["own_pb"]),
         "pick": r["pick"], "pick_prob_pct": (f"{r['pick_prob']:.1f}" if r["pick_prob"] else ""),
         "pick_basis": r["basis"], "confidence": r["conf"],
         "market_source_url": (r["egw"]["url"] if r["egw"]["oa"] else r["hltv_url"]),
         "own_model_k": K, "flags": ";".join(r["flags"])}
        for r in rows], pk_fields)

    fl_fields = ["flag_id", "severity", "subject", "detail", "source_urls"]
    write_csv(DATA_DIR / "flags.csv", [
        {"flag_id": f["id"], "severity": f["sev"], "subject": f["subject"],
         "detail": f["detail"], "source_urls": " | ".join(f["links"])} for f in FLAGS], fl_fields)

    n_market = sum(1 for r in rows if r["egw_pa"])
    n_own = sum(1 for r in rows if not r["egw_pa"] and r["own_pa"])
    n_research = sum(1 for r in rows if r["research"])
    n_pick = sum(1 for r in rows if r["pick"])
    coverage = {
        "session": SESSION, "branch": BRANCH, "snapshot_utc": SNAP_UTC,
        "generated_by": "scripts/63ee81ba_build.py",
        "hotspawn_crowd_data_used": False,
        "model": {"k": K, "source": "model/input/vrs/calibration.json (adopted=true, k_published)",
                  "map_formula": "1/(1+10^(-k*(A-B)/400))",
                  "series_transform": {"BO1": "p", "BO3": "p^2(3-2p)"}},
        "counts": {
            "open_fixtures": len(rows),
            "with_external_market_line": n_market,
            "with_placeholders_rejected": len(rows) - n_market,
            "with_own_originated_line": sum(1 for r in rows if r["own_pa"]),
            "with_research_line": n_research,
            "with_pick": n_pick,
            "obvious_locks": sum(1 for r in rows if r["conf"].startswith("OBVIOUS")),
            "strong_picks": sum(1 for r in rows if r["conf"].startswith("STRONG")),
            "solid_leans": sum(1 for r in rows if r["conf"].startswith("SOLID")),
            "close_tossups": sum(1 for r in rows if r["conf"].startswith("CLOSE")),
            "locked_week_listed": len(LOCKED_WEEK),
            "s_tier": sum(1 for r in rows if r["tier"] == "S"),
            "b_tier": sum(1 for r in rows if r["tier"] == "B"),
            "c_tier": sum(1 for r in rows if r["tier"] == "C"),
            "unique_teams": len([n for n in team_names]),
        },
        "sources": {
            "hotspawn_cs2_lobby": HOTSPAWN_CS2,
            "hotspawn_payload_read_utc": HOTSPAWN_PAYLOAD_READ,
            "hotspawn_ci_capture_utc": HOTSPAWN_CIK_PAYLOAD,
            "valve_vrs_file": VRS_FILE_REL, "valve_vrs_commit": VRS_COMMIT,
            "valve_vrs_url": VRS_BASE_URL,
            "vrs_local_sha256": VRS_SHA256, "vrs_local_fetched_utc": VRS_LOCAL_FETCHEd,
            "hltv_ranking_url": HLTV_RANKING_URL, "hltv_ranking_snapshot": HLTV_RANKING_SNAP,
            "egamersworld": EGW_MATCHES, "egw_read_utc": EGW_READ,
            "pinnacle": PINNACLE_URL, "pinnacle_read_utc": PINNACLE_READ,
            "polymarket": PM_BASE, "polymarket_read_utc": PM_READ,
        },
        "flags": len(FLAGS),
    }
    (DATA_DIR / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    return coverage

# ----------------------------------------------------------------------------- html
CSS = """
:root{--bg:#0b0f17;--panel:#121826;--panel2:#18202f;--line:#26314a;--fg:#e9eef7;--muted:#9aa9c2;--accent:#4ea8de;--accent2:#38bdf8;--green:#22c55e;--greenbg:rgba(34,197,94,.13);--amber:#f59e0b;--amberbg:rgba(245,158,11,.14);--red:#ef4444;--redbg:rgba(239,68,68,.15);--purple:#a855f7;--purplebg:rgba(168,85,247,.15)}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent2);text-decoration:none}a:hover{text-decoration:underline}
.topbar{background:#070b13;border-bottom:1px solid var(--line);padding:10px 12px;position:sticky;top:0;z-index:40}
.topbar .in{max-width:1100px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}
.brand{font-weight:700;font-size:14.5px}.brand b{color:var(--accent2)}
.nav{display:flex;flex-wrap:wrap;gap:5px}
.nav a{padding:5px 9px;border-radius:7px;background:var(--panel);border:1px solid var(--line);font-size:12px;color:var(--fg);white-space:nowrap}
.nav a.act,.nav a:hover{background:var(--accent);color:#04101c;border-color:var(--accent);text-decoration:none;font-weight:700}
.wrap{max-width:1100px;margin:0 auto;padding:14px 12px 48px}
.hero{background:linear-gradient(135deg,#111827,#16213c);border:1px solid var(--line);border-radius:14px;padding:18px 16px;margin:12px 0}
.hero h1{margin:0 0 6px;font-size:clamp(20px,4.5vw,28px);line-height:1.2}
.hero p{margin:0;color:var(--muted);font-size:13.5px}
.banner{background:rgba(56,189,248,.08);border-left:4px solid var(--accent2);padding:10px 12px;border-radius:8px;font-size:12.8px;margin-top:12px;color:#cfe3f7}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:14px 0}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
.kpi b{display:block;font-size:24px;margin:2px 0}.kpi span{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
.kpi i{font-style:normal;color:var(--muted);font-size:11.5px;display:block}
section.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px;margin:16px 0}
section.card h2{margin:0 0 4px;font-size:17px}
section.card .desc{margin:0 0 10px;color:var(--muted);font-size:12.8px}
table{width:100%;border-collapse:collapse;font-size:12.8px}
.tw{width:100%;overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px}
th{background:#0d1322;color:var(--muted);text-transform:uppercase;font-size:10.8px;letter-spacing:.03em;text-align:left;padding:8px 9px;position:sticky;top:0}
td{padding:9px;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:nth-child(even){background:var(--panel2)}
tbody tr:hover{background:rgba(78,168,222,.08)}
.badge{display:inline-block;padding:2px 7px;border-radius:6px;font-size:10.8px;font-weight:700;white-space:nowrap}
.b-s{background:var(--purplebg);color:#d8b4fe;border:1px solid var(--purple)}
.b-b{background:rgba(56,189,248,.15);color:#7dd3fc;border:1px solid var(--accent2)}
.b-c{background:rgba(148,163,184,.15);color:#cbd5e1;border:1px solid #64748b}
.b-lock{background:var(--greenbg);color:#86efac;border:1px solid var(--green)}
.b-strong{background:rgba(56,189,248,.15);color:#7dd3fc;border:1px solid var(--accent2)}
.b-lean{background:var(--amberbg);color:#fcd34d;border:1px solid var(--amber)}
.b-toss{background:rgba(249,115,22,.15);color:#fdba74;border:1px solid #f97316}
.b-unv{background:var(--redbg);color:#fca5a5;border:1px solid var(--red)}
.b-research{background:var(--purplebg);color:#d8b4fe;border:1px solid var(--purple)}
.srcs{display:flex;flex-wrap:wrap;gap:4px;margin-top:5px}
.sp{display:inline-block;padding:2px 7px;border-radius:5px;background:#0d1322;border:1px solid var(--line);font-size:10.8px;color:var(--accent2);white-space:nowrap}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11.5px}
.mut{color:var(--muted);font-size:11.8px}
.cards{display:grid;grid-template-columns:1fr;gap:10px}
@media(min-width:900px){.cards{grid-template-columns:1fr 1fr}}
.fc{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:8px}
.fc .head{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.fc .mm{font-size:15px;font-weight:750}
.fc .meta{font-size:11.8px;color:var(--muted)}
.bar{display:flex;height:10px;border-radius:6px;overflow:hidden;background:#22304c;margin:2px 0}
.bar .fa{background:var(--accent2)}.bar .fb{background:#5b6b85}
.pct{display:flex;justify-content:space-between;font-size:13px;font-weight:700}
.pct .na{color:#7dd3fc}.pct .nb{color:#cbd5e1}
.pickbox{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--green);border-radius:9px;padding:9px 10px}
.pickbox.research{border-left-color:var(--purple)}
.pickbox .pk{font-size:15.5px;font-weight:800}
.pickbox .bb{font-size:11.5px;color:var(--muted);margin-top:2px}
.flaglink{font-size:11.5px}
footer{margin-top:26px;padding:14px;border-top:1px solid var(--line);color:var(--muted);font-size:11.8px;text-align:center}
ul.plain{padding-left:18px;margin:6px 0}ul.plain li{margin:4px 0;color:var(--muted);font-size:12.8px}
details{margin:10px 0}summary{cursor:pointer;font-weight:600;color:var(--muted);font-size:13px}
"""

NAV = [
    ("index.html", "All picks (28)"), ("s-tier.html", "S-Tier (4)"), ("b-tier.html", "B-Tier (9)"),
    ("c-tier.html", "C-Tier (15)"), ("tournaments.html", "Tournaments"), ("market-lines.html", "Market lines"),
    ("own-lines.html", "Own lines"), ("sources.html", "Sources"), ("methodology.html", "Method"),
    ("flagged.html", "Flagged"),
]


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


def tier_badge(tier: str, pts: str) -> str:
    cls = {"S": "b-s", "B": "b-b"}.get(tier, "b-c")
    return f'<span class="badge {cls}">{tier}-Tier · {pts} pts</span>'


def conf_badge(c: str) -> str:
    cls = "b-lock" if c.startswith("OBVIOUS") else "b-strong" if c.startswith("STRONG") else \
          "b-lean" if c.startswith("SOLID") else "b-toss" if c.startswith("CLOSE") else "b-unv"
    return f'<span class="badge {cls}">{esc(c)}</span>'


def src_pills(r: dict) -> str:
    pills = [f'<a class="sp" href="{esc(r["hs_url"])}" target="_blank" rel="noopener">Hotspawn {esc(r["hs_kind"])}</a>']
    pills.append(f'<a class="sp" href="{esc(r["hltv_url"])}" target="_blank" rel="noopener">HLTV match {esc(r["hltv_id"])}</a>')
    pills.append(f'<a class="sp" href="{esc(_v(r["ta"]["line"])["vrs_url"])}" target="_blank" rel="noopener">VRS {esc(r["a"])}</a>')
    vb_url = RESEARCH_POINTS[r["b"]]["url"] if (r["research"] and r["b"] in RESEARCH_POINTS) else _v(r["tb"]["line"])["vrs_url"]
    pills.append(f'<a class="sp" href="{esc(vb_url)}" target="_blank" rel="noopener">VRS {esc(r["b"])}</a>')
    if r["egw"]["oa"]:
        pills.append(f'<a class="sp" href="{esc(r["egw"]["url"])}" target="_blank" rel="noopener">EGW quote</a>')
    if r["pin"]:
        pills.append(f'<a class="sp" href="{esc(PINNACLE_URL)}" target="_blank" rel="noopener">Pinnacle</a>')
    if r["pm"]:
        pills.append(f'<a class="sp" href="{esc(PM_BASE + "/" + r["pm"]["slug"])}" target="_blank" rel="noopener">Polymarket</a>')
    return f'<div class="srcs">{"".join(pills)}</div>'


def fixture_card(r: dict) -> str:
    pa_pub = f"{r['egw_pa']:.1f}" if r["egw_pa"] else r["own_pa"]
    pb_pub = f"{r['egw_pb']:.1f}" if r["egw_pb"] else r["own_pb"]
    wa = max(4, min(96, int(round(float(pa_pub)))) if pa_pub else 50)
    wb = 100 - wa
    pa_v = float(pa_pub) if pa_pub else 50.0
    # bar for team_a
    if r["egw_pa"]:
        ext = (f'{esc(r["egw"]["oa"])} / {esc(r["egw"]["ob"])} · '
               f'<a href="{esc(r["egw"]["url"])}" target="_blank" rel="noopener">bc.game (EGW)</a>, de-vigged '
               f'({r["egw_over"]:.1f}% margin)')
    else:
        ext = '<span class="badge b-unv">No market line — 1.80/1.80 placeholder rejected</span> ' \
              f'<a href="flagged.html#pf-01" class="flaglink">PF-01</a>'
    pin_txt = ""
    if r["pin"]:
        pin_txt = f' · Pinnacle {r["pin"]["oa"]}/{r["pin"]["ob"]} (<a href="{esc(PINNACLE_URL)}" target="_blank" rel="noopener">API {r["pin_pa"]:.0f}%/{r["pin_pb"]:.0f}%</a>)'
    pm_txt = ""
    if r["pm"]:
        use = "cross-check" if r["pm_pa"] else "context only — see flag"
        pm_txt = f' · Polymarket {r["pm"]["xa"]}x/{r["pm"]["xb"]}x ({r["pm"]["ca"]}¢/{r["pm"]["cb"]}¢, ${esc(r["pm"]["vol"])} vol, {use})'
    if r["own_pa"]:
        if r["research"] and r["b"] in RESEARCH_POINTS:
            vrs_b_disp = "#156 (813, research-mapped)"
        else:
            vrs_b_disp = f"#{esc(r['tb']['rank'])} ({esc(r['tb']['pts'])})"
        own = (f'{r["own_pa"]}% / {r["own_pb"]}% — '
               f'<span class="mono">VRS #{esc(r["ta"]["rank"])} ({esc(r["ta"]["pts"])}) vs {vrs_b_disp}</span>')
        if r["research"]:
            own += ' <span class="badge b-research">RESEARCH</span> <a href="flagged.html#pf-02" class="flaglink">PF-02</a>'
    else:
        own = '<span class="badge b-unv">Blank — unverified</span> <a href="flagged.html#pf-02" class="flaglink">PF-02</a>'
    flags = ""
    if r["flags"]:
        fl_map = {"FL-UNVERIFIED-TEAM": "pf-02", "FL-IDENTITY-PCIFIC": "pf-03"}
        shown = []
        for f in r["flags"]:
            if f.startswith("PF") or f in fl_map:
                shown.append(f)
        if shown:
            anchors = "".join(
                f'<a class="flaglink" href="flagged.html#{fl_map.get(f, f.lower())}">{f}</a> ' for f in shown)
            flags = f'<div class="mut">Flags: {anchors}</div>'
    pickbox_cls = "pickbox research" if r["research"] else "pickbox"
    if r["pick"]:
        prob_disp = f"{r['pick_prob']:.1f}%" if r["pick_prob"] else ""
        pick_html = f'<div class="{pickbox_cls}"><div class="pk">PICK: {esc(r["pick"])} {esc(prob_disp)}</div>' \
                    f'<div>{conf_badge(r["conf"])}</div>' \
                    f'<div class="bb">Basis: {esc(r["basis"])}</div></div>'
    else:
        pick_html = f'<div class="{pickbox_cls}"><div class="pk">NO PICK — FLAGGED</div></div>'
    lock = r["lock"]
    return f"""
    <div class="fc" id="f-{esc(r['mid'])}">
      <div class="head"><span class="mono mut">#{esc(r['mid'])}</span> {tier_badge(r['tier'], r['pts'])}
        <span class="badge b-b">{esc(r['fmt'])}</span><span class="mut">{esc(r['tourney'])}</span></div>
      <div><span class="mm">{esc(r['a'])}</span> <span class="mut">vs</span> <span class="mm">{esc(r['b'])}</span></div>
      <div><div class="pct"><span class="na">{esc(r['a'])} {esc(pa_pub)}%</span><span class="nb">{esc(pb_pub)}% {esc(r['b'])}</span></div>
        <div class="bar"><div class="fa" style="width:{wa}%"></div><div class="fb" style="width:{wb}%"></div></div></div>
      {pick_html}
      <div class="mut"><b>Market:</b> {ext}{pin_txt}{pm_txt}</div>
      <div class="mut"><b>Own line:</b> {own}</div>
      <div class="mut"><b>Start:</b> <span class="mono">{esc(r['start'][:16])} UTC</span> ·
        <b>Lock:</b> <span class="mono">{esc(lock[:16])} UTC</span> <a class="flaglink" href="flagged.html#pf-08">(PF-08)</a></div>
      {src_pills(r)}
      {flags}
    </div>"""


def shell(active: str, title: str, body: str) -> str:
    nav = "".join(f'<a href="{f}"{" class=act" if f == active else ""}>{esc(l)}</a>' for f, l in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Hotspawn CS2 Full Picks</title>
<style>{CSS}</style></head><body>
<header class="topbar"><div class="in">
<div class="brand"><b>Full picks</b> · Hotspawn CS2 Pick'em</div>
<nav class="nav">{nav}</nav></div></header>
<main class="wrap">{body}
<footer>Session {esc(SESSION)} · snapshot {esc(SNAP_UTC)} ·
<a href="../index.html">repo home</a> ·
data: <a href="../data/63ee81ba/picks.csv">picks.csv</a> ·
<a href="../data/63ee81ba/market_lines.csv">market_lines.csv</a> ·
<a href="../data/63ee81ba/own_lines.csv">own_lines.csv</a> ·
<a href="../data/63ee81ba/flags.csv">flags.csv</a> ·
Independent research — not betting advice.</footer>
</main></body></html>"""


def render_pages(rows: list[dict], coverage: dict) -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "style.css").write_text(CSS, encoding="utf-8")
    c = coverage["counts"]
    open_rows = rows

    # ---- index -----------------------------------------------------------------
    by_date: dict[str, list[dict]] = {}
    for r in open_rows:
        by_date.setdefault(r["start"][:10], []).append(r)
    date_secs = []
    for d in sorted(by_date):
        cards = "".join(fixture_card(r) for r in by_date[d])
        day = {"2026-10-14": "Tuesday, Oct 14", "2026-10-15": "Wednesday, Oct 15", "2026-10-16": "Thursday, Oct 16"}[d]
        date_secs.append(f"""
    <section class="card"><h2>{day} — {len(by_date[d])} matches</h2>
      <p class="desc">All times UTC. Lock = start − 6 min (PF-08). Submit your pick on Hotspawn before lock.</p>
      <div class="cards">{cards}</div></section>""")

    locked_rows_html = ""
    for lk in LOCKED_WEEK:
        locked_rows_html += f"""
        <tr><td class="mono">#{esc(lk['mid'])}</td><td>{esc(lk['start'][:16])} UTC</td>
        <td>{esc(lk['tourney'])}</td><td><b>{esc(lk['a'])}</b> vs <b>{esc(lk['b'])}</b></td>
        <td>{esc(lk['fmt'])}</td><td>{esc(lk['result'])}
        <a class="sp" href="{esc(lk['hltv'])}" target="_blank" rel="noopener">HLTV result</a></td></tr>"""

    # at-a-glance table
    glance = []
    for r in open_rows:
        pa_pub = f"{r['egw_pa']:.1f}" if r["egw_pa"] else r["own_pa"]
        pb_pub = f"{r['egw_pb']:.1f}" if r["egw_pb"] else r["own_pb"]
        glance.append(f"""
        <tr id="g-{esc(r['mid'])}">
          <td class="mono"><a href="#f-{esc(r['mid'])}">#{esc(r['mid'])}</a></td>
          <td>{esc(r['start'][5:16].replace('T', ' '))}</td>
          <td>{esc(r['a'])} vs {esc(r['b'])}</td>
          <td><b>{esc(pa_pub)}%</b> / <b>{esc(pb_pub)}%</b></td>
          <td><b>{esc(r['pick'])}</b> {esc(f'{r["pick_prob"]:.1f}%' if r['pick_prob'] else '')}</td>
          <td>{conf_badge(r['conf'])}</td>
          <td>{esc(r['basis'].split(' — ')[0] if r['basis'] else '—')}</td>
        </tr>""")

    idx_body = f"""
    <div class="hero">
      <h1>Every open Hotspawn CS2 match — one pick each.</h1>
      <p>Full coverage of all <b>{c['open_fixtures']}</b> open Pick'em fixtures (Oct 14–16, 2026, UTC):
      {c['with_external_market_line']} priced by outside markets and {c['with_own_originated_line'] - c['with_research_line']} originated from official
      Valve VRS + HLTV research — so every row carries a pick. Snapshot {esc(SNAP_UTC)} ·
      <a href="flagged.html">flagged items ({len(FLAGS)})</a> · <a href="methodology.html">method</a> ·
      <a href="sources.html">sources</a></p>
      <div class="banner"><b>Read first:</b> Hotspawn's cards display times in UTC−4 — use the UTC times on this board
      (PF-06). Crowds' pick percentages are never used (0.0% weight). Every number links to its official source.
      Not betting advice.</div>
    </div>
    <div class="kpis">
      <div class="kpi"><span>Open matches</span><b>{c['open_fixtures']}</b><i>S {c['s_tier']} · B {c['b_tier']} · C {c['c_tier']}</i></div>
      <div class="kpi"><span>Picks made</span><b>{c['with_pick']} / {c['open_fixtures']}</b><i>100% coverage</i></div>
      <div class="kpi"><span>Obvious locks (≥70%)</span><b>{c['obvious_locks']}</b><i>strong {c['strong_picks']} · lean {c['solid_leans']} · close {c['close_tossups']}</i></div>
      <div class="kpi"><span>Outside market lines</span><b>{c['with_external_market_line']} / {c['open_fixtures']}</b><i>EGW bc.game + Pinnacle/PM cross-checks</i></div>
      <div class="kpi"><span>Own research lines</span><b>{c['with_own_originated_line']}</b><i>incl. {c['with_research_line']} labelled RESEARCH (PF-02)</i></div>
    </div>
    <section class="card"><h2>At a glance — all {c['open_fixtures']} picks (chronological)</h2>
      <p class="desc">Tap a row ID to jump to its card below. %s are the published win probabilities (market-de-vigged where a line exists, otherwise our own model).</p>
      <div class="tw"><table><thead><tr><th>ID</th><th>Start (UTC)</th><th>Matchup (Hotspawn order)</th><th>P(A) / P(B)</th><th>Pick</th><th>Confidence</th><th>Basis</th></tr></thead>
      <tbody>{''.join(glance)}</tbody></table></div>
    </section>
    {''.join(date_secs)}
    <section class="card"><h2>This week, already locked or started (no pick offered)</h2>
      <p class="desc">Current-week fixtures whose lock time has passed at the snapshot. Results verified on HLTV.</p>
      <div class="tw"><table><thead><tr><th>ID</th><th>Start (UTC)</th><th>Tournament</th><th>Matchup</th><th>Format</th><th>Status / verified result</th></tr></thead>
      <tbody>{locked_rows_html}</tbody></table></div>
      <p class="desc">Hotspawn's payload also retains 59 stale Jun–Jul 2026 records (not pickable) — retained with sources on
      the <a href="../oct14/coverage-all-91.html">8944bb84 full-coverage page</a> (PF-10).</p>
    </section>"""
    (SITE_DIR / "index.html").write_text(shell("index.html", "All 28 Open CS2 Picks", idx_body), encoding="utf-8")

    # ---- tier pages -------------------------------------------------------------
    for tier, fname, title in (("S", "s-tier.html", "S-Tier picks (7 pts each)"),
                               ("B", "b-tier.html", "B-Tier picks (3 pts each)"),
                               ("C", "c-tier.html", "C-Tier picks (2 pts each)")):
        trows = [r for r in open_rows if r["tier"] == tier]
        (SITE_DIR / fname).write_text(shell(fname, title, f"""
        <section class="card"><h2>{title} — {len(trows)} open matches</h2>
        <p class="desc">Every card shows both teams' published win %, the pick with its confidence tier and basis,
        the outside market line where one exists (else the rejected placeholder is shown), our own line, and all source links.</p>
        <div class="cards">{''.join(fixture_card(r) for r in trows)}</div></section>"""), encoding="utf-8")

    # ---- tournaments --------------------------------------------------------------
    by_t: dict[str, list[dict]] = {}
    for r in open_rows:
        by_t.setdefault(r["tourney"], []).append(r)
    tourney_secs = []
    for tname in sorted(by_t, key=lambda t: -len(by_t[t])):
        trs = by_t[tname]
        tourney_secs.append(f"""
      <section class="card"><h2>{esc(tname)} — {len(trs)} matches</h2>
      <p class="desc">{esc(trs[0]['fmt'])} series · {' / '.join(sorted({r['tier'] + '-Tier' for r in trs}))}</p>
      <div class="cards">{''.join(fixture_card(r) for r in trs)}</div></section>""")
    (SITE_DIR / "tournaments.html").write_text(shell("tournaments.html", "Picks by tournament", f"""
      <div class="hero"><h1>By tournament</h1><p>Every open fixture grouped by its Hotspawn competition
      ({len(by_t)} active competitions on the open slate).</p></div>
      {''.join(tourney_secs)}"""), encoding="utf-8")

    # ---- market lines ---------------------------------------------------------------
    ml_tr = []
    for r in open_rows:
        if r["egw_pa"]:
            line, dev = f'{r["egw"]["oa"]} / {r["egw"]["ob"]}', f'{r["egw_pa"]:.1f}% / {r["egw_pb"]:.1f}%'
            book = f'<a href="{esc(r["egw"]["url"])}" target="_blank" rel="noopener">bc.game (EGW)</a>'
            margin = f'<div class="mut">margin {r["egw_over"]:.2f}%</div>'
        else:
            line, dev, book, margin = "— (1.80/1.80 rejected)", "—", f'<a href="flagged.html#pf-01" class="flaglink">PF-01</a>', ""
        pin = f'{r["pin"]["oa"]} / {r["pin"]["ob"]} (de-vig {r["pin_pa"]:.1f}%/{r["pin_pb"]:.1f}%)' if r["pin"] else "—"
        pm = (f'{r["pm"]["xa"]}x/{r["pm"]["xb"]}x · {r["pm"]["ca"]}¢/{r["pm"]["cb"]}¢ · ${esc(r["pm"]["vol"])} vol'
              if r["pm"] else "—")
        note = r["egw"]["note"] if r["egw"]["note"] else (r["pm"]["note"] if r["pm"] else "")
        ml_tr.append(f"""
        <tr><td class="mono"><a href="index.html#f-{esc(r['mid'])}">#{esc(r['mid'])}</a></td>
        <td>{esc(r['start'][:16].replace('T',' '))} UTC</td>
        <td><b>{esc(r['a'])}</b> vs <b>{esc(r['b'])}</b> ({esc(r['fmt'])})</td>
        <td>{book} <span class="mono">{esc(line)}</span>{margin}</td>
        <td><b>{esc(dev)}</b></td>
        <td class="mono">{esc(pin)}</td><td class="mono">{esc(pm)}</td>
        <td class="mut">{esc(note)}</td></tr>""")
    (SITE_DIR / "market-lines.html").write_text(shell("market-lines.html", "Outside market lines (de-vigged)", f"""
      <div class="hero"><h1>Outside betting lines, line by line</h1>
      <p>Primary line: EGamersWorld (bc.game feed), read {esc(EGW_READ)} (values identical to the independent {esc(EGW_PREVIOUS_READ)} read by session 8944bb84).
      Cross-checks: Pinnacle direct API ({esc(PINNACLE_READ)}) and Polymarket ({esc(PM_READ)}, view-only). De-vig: p = (1/d) / (1/d_A + 1/d_B).
      1.80/1.80 placeholders rejected (PF-01).</p></div>
      <section class="card"><div class="tw"><table><thead><tr><th>ID</th><th>Start</th><th>Matchup</th>
      <th>Primary (EGW bc.game)</th><th>De-vigged P(A)/P(B)</th><th>Pinnacle cross-check</th><th>Polymarket cross-check</th><th>Notes</th></tr></thead>
      <tbody>{''.join(ml_tr)}</tbody></table></div>
      <p class="desc" style="margin-top:10px">Polymarket CCT Europe tab also lists markets with no open Hotspawn fixture (context only):
      {' · '.join(f"{esc(n)} ({esc(v)})" for n, s, v, vol in [(a, c, d, e) for a, c, d, e in PM_NON_SLAte_MARKETS])}.</p>
      </section>"""), encoding="utf-8")

    # ---- own lines -------------------------------------------------------------------
    ol_tr = []
    for r in open_rows:
        vrs_b = ("#156 (813) " + '<span class="badge b-research">research-mapped</span>'
                 if r["research"] and r["b"] in RESEARCH_POINTS
                 else f"#{esc(r['tb']['rank'])} ({esc(r['tb']['pts'])})")
        vrs_a = f"#{esc(r['ta']['rank'])} ({esc(r['ta']['pts'])})"
        hltv = f'#{esc(r["ta"]["h_rank"]) or "NR"} / #{esc(r["tb"]["h_rank"]) or "NR"}'
        own = (f'<b>{r["own_pa"]}% / {r["own_pb"]}%</b> <span class="mono">(fair {r["own_fair_odds_a"] if r["own_fair_odds_a"] else "—"}/{r["own_fair_odds_b"] if r["own_fair_odds_b"] else "—"})</span>'
               if r["own_pa"] else '<span class="badge b-unv">blank — unverified</span>')
        ol_tr.append(f"""
        <tr><td class="mono"><a href="index.html#f-{esc(r['mid'])}">#{esc(r['mid'])}</a></td>
        <td><b>{esc(r['a'])}</b> vs <b>{esc(r['b'])}</b> ({esc(r['fmt'])})</td>
        <td><a class="sp" href="{esc(_v(r['ta']['line'])['vrs_url'])}" target="_blank" rel="noopener">{esc(vrs_a)}</a> vs
            <a class="sp" href="{esc(RESEARCH_POINTS[r['b']]['url'] if r['research'] and r['b'] in RESEARCH_POINTS else _v(r['tb']['line'])['vrs_url'])}" target="_blank" rel="noopener">{vrs_b}</a></td>
        <td class="mut">HLTV {esc(hltv)}</td>
        <td>{own}</td>
        <td class="mut">{esc(r['method'])}</td>
        <td class="mut">{esc(';'.join(f for f in r['flags'] if f.startswith(('PF', 'FL-UN', 'FL-ID'))))}</td></tr>""")
    (SITE_DIR / "own-lines.html").write_text(shell("own-lines.html", "Our own originated lines", f"""
      <div class="hero"><h1>Own lines — official VRS + HLTV research</h1>
      <p>Map probability from Valve VRS points with the repo-adopted calibrated slope k = {K}
      (<a href="../model/input/vrs/calibration.json">{esc(str(CALIBRATION_FILE.relative_to(ROOT)))}</a>), series transform
      BO1: p, BO3: p²(3−2p) — format verified on each HLTV match page. HLTV ranks shown as cross-check only.
      Team ratings source of record: <a href="../data/8944bb84/ratings.csv">data/8944bb84/ratings.csv</a> (verified {esc('2026-10-14T02:26:00Z')}).</p></div>
      <section class="card"><div class="tw"><table><thead><tr><th>ID</th><th>Matchup</th><th>VRS (line anchors)</th>
      <th>HLTV cross-check</th><th>Own series P(A)/P(B)</th><th>Method</th><th>Flags</th></tr></thead>
      <tbody>{''.join(ol_tr)}</tbody></table></div></section>
      <section class="card"><h2>Team rating registry ({coverage['counts']['unique_teams']} teams)</h2>
      <p class="desc">Every team on the open slate with its verified VRS standing (line anchor into the 2026-10-05 file) and HLTV rank.</p>
      <div class="tw"><table><thead><tr><th>Team</th><th>VRS (2026-10-05)</th><th>HLTV (2026-10-12)</th><th>Verification</th><th>Links</th></tr></thead><tbody>
      {''.join(team_row(name) for name in sorted(set(r['a'] for r in open_rows) | set(r['b'] for r in open_rows)))}
      </tbody></table></div></section>"""), encoding="utf-8")

    # ---- sources ---------------------------------------------------------------------
    src_rows = [
        ("Hotspawn CS2 Pick'em lobby", "Fixture list, team order, tiers/points, start/lock epochs (crowd % never used)",
         f"read {HOTSPAWN_PAYLOAD_READ} (live) · CI capture {HOTSPAWN_CIK_PAYLOAD}", HOTSPAWN_CS2),
        ("Valve Regional Standings (VRS) 2026-10-05", "Official team ratings + rosters — primary input for own lines",
         f"commit {VRS_COMMIT[:12]} · local sha256 {VRS_SHA256[:16]}… · fetched {VRS_LOCAL_FETCHEd}", VRS_BASE_URL),
        ("Valve VRS model code", "Calibration basis (k) + roster-identity rule (PF-02)",
         "commit " + VRS_COMMIT[:12], "https://github.com/ValveSoftware/counter-strike_regional_standings/tree/" + VRS_COMMIT + "/model"),
        ("HLTV World Ranking 2026-10-12", "Secondary official ranking + roster cross-checks",
         f"snapshot {HLTV_RANKING_SNAP}", HLTV_RANKING_URL),
        ("HLTV official match pages (28)", "Series format (BO1/BO3), lineups, results",
         "matches 2399134–2399471, verified 2026-10-14", "https://www.hltv.org/matches"),
        ("EGamersWorld (bc.game feed)", "Primary outside moneylines (24/28 priced; 4 placeholders rejected)",
         f"read {EGW_READ} (listing chunks 0–9, 02:40–02:48Z); cross-ref {EGW_PREVIOUS_READ}", EGW_MATCHES),
        ("Pinnacle (direct guest API)", "Cross-check sharp lines (7 fixtures)",
         f"read {PINNACLE_READ} (session 8944bb84, re-used with citation)", PINNACLE_URL),
        ("Polymarket CCT Europe", "Cross-check prediction-market prices (7 fixtures; 2 unusable, flagged)",
         f"read {PM_READ}, view-only (PF-07)", PM_BASE),
    ]
    (SITE_DIR / "sources.html").write_text(shell("sources.html", "Official sources", f"""
      <div class="hero"><h1>Official sources & provenance</h1>
      <p>Every row on this board links to its source. Local evidence: <code>data/63ee81ba/</code> (CSVs + VRS file with sha256) and <code>data/8944bb84/</code> (team ratings).</p></div>
      <section class="card"><div class="tw"><table><thead><tr><th>Source</th><th>Role</th><th>Snapshot / timestamp</th><th>Link</th></tr></thead>
      <tbody>{''.join(f'<tr><td><b>{esc(a)}</b></td><td>{esc(b)}</td><td class="mut">{esc(c)}</td><td><a class="sp" href="{esc(d)}" target="_blank" rel="noopener">open</a></td></tr>' for a, b, c, d in src_rows)}</tbody></table></div></section>"""), encoding="utf-8")

    # ---- methodology -------------------------------------------------------------------
    (SITE_DIR / "methodology.html").write_text(shell("methodology.html", "Methodology", f"""
      <div class="hero"><h1>Method — how each pick is produced</h1>
      <p>Deterministic, reproducible by <code>scripts/63ee81ba_build.py</code>; checked by <code>tests/test_63ee81ba.py</code>.</p></div>
      <section class="card"><h2>1. Inputs (all source-linked, all timestamped)</h2>
      <ul class="plain">
        <li>Open fixture list, team order, tiers, start/lock epochs — Hotspawn <code>/cs2-pickems</code> payload (read {esc(HOTSPAWN_PAYLOAD_READ)}; CI capture {esc(HOTSPAWN_CIK_PAYLOAD)}). Displayed card times run UTC−4 (PF-06); payload epochs are used.</li>
        <li>Outside moneylines — EGW bc.game (primary, {esc(EGW_READ)}); Pinnacle direct API + Polymarket (cross-checks). Proportional de-vig: <span class="mono">p_A = (1/d_A)/(1/d_A + 1/d_B)</span>. 1.80/1.80 placeholders rejected (PF-01). Market moneylines are series prices → no format transform.</li>
        <li>Team ratings — Valve VRS 2026-10-05 (points + line anchors) and HLTV 2026-10-12 (cross-check), verified roster-by-roster on data/8944bb84/ratings.csv.</li>
        <li>Series format — official HLTV match page per fixture (BO1 for all 12 Elisa BreakOut matches, BO3 elsewhere).</li>
      </ul></section>
      <section class="card"><h2>2. Own line (used only when no priced market exists)</h2>
      <ul class="plain">
        <li>Map probability: <span class="mono">P_map(A) = 1/(1 + 10^(−k·(pts_A − pts_B)/400))</span> with <b>k = {K}</b> — the slope this repository adopted after MLE calibration on Valve's 6,765 published results (model/input/vrs/calibration.json: log loss 0.6619 raw → 0.6435 calibrated; Brier 0.2294 → 0.2258 out-of-sample).</li>
        <li>Series transform (independent maps): BO1 → p; BO3 → <span class="mono">p²(3−2p)</span>.</li>
        <li>Unrated team → line left blank + flagged. The single exception, LFO 10 (PF-02), publishes a roster-mapped line against VRS #156 Entropy (813 pts) that is labelled RESEARCH on every surface and never counted as verified.</li>
      </ul></section>
      <section class="card"><h2>3. Pick rule & confidence</h2>
      <ul class="plain">
        <li>Priced market exists → pick = de-vigged favourite; published %s = market de-vig.</li>
        <li>No priced market → pick = own-line favourite; published %s = own series probabilities.</li>
        <li>Confidence tiers on the pick probability: OBVIOUS LOCK ≥ 70% · STRONG PICK 60–69% · SOLID LEAN 55–59% · CLOSE TOSS-UP &lt; 55%.</li>
        <li>Hotspawn crowd pick percentages: 0.0% weight, structurally excluded (the build's inputs contain no crowd fields; test-enforced).</li>
      </ul></section>
      <section class="card"><h2>4. Automated refresh (fail-closed)</h2>
      <ul class="plain">
        <li><span class="mono">.github/workflows/picks-full-63ee81ba.yml</span> runs hourly + on push: re-runs the repo's <span class="mono">live/collect.py</span> (Hotspawn payload, latest VRS file, Pinnacle, EGW, Polymarket, HLTV), rebuilds this board from the live snapshot, runs the test suite, and commits only when tests pass and output changed. Any failure keeps the last good board published (fail-closed).</li>
        <li>New/renamed fixtures or teams that the mapping cannot verify are published with blank lines + flags, never guesses.</li>
      </ul></section>"""), encoding="utf-8")

    # ---- flagged ------------------------------------------------------------------------
    fl_secs = []
    for f in FLAGS:
        sev = "b-unv" if f["sev"] == "HIGH" else "b-lean" if f["sev"] == "MEDIUM" else "b-c"
        links = "".join(f'<a class="sp" href="{esc(u)}" target="_blank" rel="noopener">source</a>' for u in f["links"])
        fl_secs.append(f"""
        <div class="fc" id="{f['id'].lower()}">
          <div class="head"><span class="mono">{esc(f['id'])}</span> <span class="badge {sev}">{esc(f['sev'])}</span></div>
          <div class="mm">{esc(f['subject'])}</div>
          <div class="mut" style="color:var(--fg);font-size:13px">{esc(f['detail'])}</div>
          <div class="srcs">{links}</div>
        </div>""")
    (SITE_DIR / "flagged.html").write_text(shell("flagged.html", "Flagged for review", f"""
      <div class="hero"><h1>Flagged for Review</h1>
      <p>Every unconfirmed, conflicting or rejected input on this board, with sources. Flagged items are published,
      labelled and never inferred away. {len(FLAGS)} flags.</p></div>
      <div class="cards">{''.join(fl_secs)}</div>"""), encoding="utf-8")


def team_row(name: str) -> str:
    t = TEAMS.get(name)
    if not t:
        return f"<tr><td>{esc(name)}</td><td colspan='4' class='mut'>—</td></tr>"
    vrs = (f'<a class="sp" href="{esc(_v(t["line"])["vrs_url"])}" target="_blank" rel="noopener">#{esc(t["rank"])} ({esc(t["pts"])})</a>'
           if t["rank"] else '<span class="badge b-unv">not in VRS file</span>')
    hltv = (f"#{esc(t['h_rank'])} ({esc(t['h_pts'])} pts)" if t["h_rank"] else "outside top-245")
    h_url = t["h_url"] or HLTV_RANKING_URL
    return f"<tr><td><b>{esc(name)}</b></td><td>{vrs}</td><td>{esc(hltv)} <a class='sp' href='{esc(h_url)}' target='_blank' rel='noopener'>HLTV</a></td><td class='mut'>{esc(t['res'])}</td><td class='mut'>{esc(t['flags'])}</td></tr>"

# ----------------------------------------------------------------------------- live mode
def build_live() -> int:
    """Live verification pass for scheduled runs (fail-closed).

    Reads live/data/snapshot.json (written by live/collect.py earlier in the same
    workflow run) and VERIFIES the published board against the fresh capture:
      * snapshot freshness (refuses to run on a stale capture),
      * open CS2 slate drift (new / disappeared fixture IDs) — reported to the log,
      * latest Valve VRS file vs the pinned one — reported, never auto-re-pinned,
      * any market quote that disappeared or moved materially — reported.
    It never mutates the verified pinned board: publishing changes requires a
    source-linked build change (a session), so the site can never silently serve
    an unverified pick. Any check that cannot complete -> non-zero exit -> the
    workflow publishes nothing and the last good board stays live.
    """
    snap_path = ROOT / "live" / "data" / "snapshot.json"
    if not snap_path.exists():
        print("[63ee81ba] LIVE: live/data/snapshot.json missing — run live/collect.py first", file=sys.stderr)
        return 2
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    gen = snap.get("generated_utc", "")
    try:
        age_h = (datetime.now(timezone.utc)
                 - datetime.strptime(gen, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600.0
    except ValueError:
        print(f"[63ee81ba] LIVE: unparsable generated_utc {gen!r}", file=sys.stderr)
        return 2
    if age_h > 24:
        print(f"[63ee81ba] LIVE: snapshot too old ({age_h:.1f} h) — refusing", file=sys.stderr)
        return 2

    # 1) VRS file drift
    vrs = snap.get("vrs", {})
    latest_file = vrs.get("file", "")
    pinned_file = VRS_FILE_REL.rsplit("/", 1)[-1]
    if latest_file and latest_file != pinned_file:
        print(f"[63ee81ba] LIVE: NEW VRS FILE AVAILABLE: {latest_file} (board pinned to {pinned_file}). "
              f"Re-pinning requires a source-linked session; board unchanged.")

    # 2) open slate drift (fixtures whose start is still ahead at run time)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fx_live = [f for f in snap.get("fixtures", []) if f.get("sport") == "cs2"]
    open_live = [f for f in fx_live if str(f.get("start_utc", "")) >= now_iso]
    pinned_ids = {f["mid"] for f in FIXTURES}
    live_ids = {str(f.get("match_id", "")) for f in open_live}
    new = sorted(live_ids - pinned_ids)
    gone = sorted(pinned_ids - live_ids)
    if new:
        print(f"[63ee81ba] LIVE: NEW open CS2 fixtures on Hotspawn (not on this board): {new}")
    if gone:
        print(f"[63ee81ba] LIVE: pinned fixtures no longer open on Hotspawn: {gone}")
    if not new and not gone:
        print(f"[63ee81ba] LIVE: open slate unchanged ({len(pinned_ids)} fixtures).")

    # 3) market quote movement (EGW listing in snapshot)
    egw_listing = {str(row.get("match_id", "")): row for row in snap.get("egw", {}).get("listing", [])}
    moved = []
    for fx in FIXTURES:
        row = egw_listing.get(fx["mid"])
        if not row:
            continue
        pin_ = EGW_LINES[fx["mid"]]
        for key in ("odds_a", "odds_b"):
            live_val = str(row.get(key, "") or "")
            if pin_["oa"] and live_val:
                try:
                    if abs(float(live_val) - float(pin_["oa"] if key == "odds_a" else pin_["ob"])) > 0.05:
                        moved.append(f"{fx['mid']} {key}: {pin_['oa'] if key == 'odds_a' else pin_['ob']} -> {live_val}")
                        break
                except ValueError:
                    pass
    if moved:
        print(f"[63ee81ba] LIVE: EGW quote movement detected: {moved}")
    else:
        print("[63ee81ba] LIVE: no material EGW quote movement vs pinned snapshot.")
    return 0

# ----------------------------------------------------------------------------- main
def verify_pins() -> list[str]:
    problems: list[str] = []
    if VRS_FILE.exists():
        h = hashlib.sha256(VRS_FILE.read_bytes()).hexdigest()
        if h != VRS_SHA256:
            problems.append(f"VRS file hash mismatch: {h}")
    if CALIBRATION_FILE.exists():
        cal = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
        if not (cal.get("adopted") and abs(float(cal.get("k_published", 0)) - K) < 1e-9):
            problems.append(f"calibration.json does not confirm k={K}")
    # structural zero-crowd check on every input table in this module
    blob = json.dumps({k: v for k, v in EGW_LINES.items()})
    blob += json.dumps(PINNACLE_LINES) + json.dumps(PM_LINES) + json.dumps(FIXTURES)
    for banned in ("crowd", "picked_percent", "total_picks"):
        if banned in blob.lower():
            problems.append(f"forbidden Hotspawn crowd field present: {banned}")
    if len(FIXTURES) != 28:
        problems.append(f"expected 28 open fixtures, got {len(FIXTURES)}")
    for fx in FIXTURES:
        if fx["a"] not in TEAMS or fx["b"] not in TEAMS:
            problems.append(f"fixture {fx['mid']}: team missing from TEAMS registry")
        if fx["mid"] not in HLTV_MATCHES:
            problems.append(f"fixture {fx['mid']}: missing HLTV match mapping")
    return problems


def main(argv: list[str]) -> int:
    live = "--live" in argv
    problems = verify_pins()
    if problems:
        for p in problems:
            print(f"[63ee81ba] PIN CHECK FAILED: {p}", file=sys.stderr)
        return 1
    if live:
        rc = build_live()
        if rc != 0:
            return rc
    rows = build_rows()
    cov = write_datasets(rows)
    render_pages(rows, cov)
    c = cov["counts"]
    print(f"[63ee81ba] Built picks-full/ : {c['open_fixtures']} fixtures, {c['with_pick']} picks "
          f"({c['obvious_locks']} locks / {c['strong_picks']} strong / {c['solid_leans']} lean / {c['close_tossups']} close), "
          f"{c['with_external_market_line']} market lines, {c['with_own_originated_line']} own lines "
          f"({c['with_research_line']} research), {cov['flags']} flags.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
