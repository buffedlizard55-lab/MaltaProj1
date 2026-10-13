#!/usr/bin/env python3
"""
Deterministic generator for Session arena/e3315a54:
- Reconciles all 32 October 2026 Hotspawn CS2 Pick'em fixtures (27 from 18:00 UTC
  snapshot + 5 newly added on play.hotspawn.com/lobby at 21:19 UTC) plus all 59 stale
  summer TransferState CS2 fixtures (= 91 total CS2 fixtures) and 294 LoL fixtures.
- Uses ONLY official verified sources (Valve Regional Standings 2026-10-05, HLTV World
  Ranking 2026-10-12 + live HLTV match pages, Pinnacle guest API, EGamersWorld/BC.Game
  live match odds captured at 2026-10-13T21:20:00Z).
- NEVER uses Hotspawn crowd pick percentages as an indicator of match probability.
- Strictly leaves unconfirmable values BLANK ("") and flags them on Flagged for Review.
- Generates data/e3315a54/*.csv, data/e3315a54/*.json, and mobile/*.html + mobile/style.css.
"""

from __future__ import annotations

import csv
import html
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
DATA_OUT = ROOT / "data" / "e3315a54"
MOBILE_OUT = ROOT / "mobile"
MODEL_LINES_CSV = ROOT / "model" / "data" / "lines.csv"
NG_STATE_86_CSV = ROOT / "data" / "6d9c321d" / "ng_state_86_fixtures.csv"

CAPTURED_UTC = "2026-10-13T21:20:00Z"
VRS_BASE_URL = "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/"
VRS_STANDINGS_URL = VRS_BASE_URL + "live/2026/standings_global_2026_10_05.md"
HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams/2026/october/12"
HOTSPAWN_LOBBY_URL = "https://play.hotspawn.com/lobby"
HOTSPAWN_CS2_URL = "https://play.hotspawn.com/cs2-pickems"
EGW_MATCHES_URL = "https://egamersworld.com/counterstrike/matches"
PINNACLE_HIGHLIGHTS_URL = "https://www.pinnacle.com/en/esports/matchups/highlights/"

# Empirical logistic scale parameters calibrated in model/input/vrs/calibration.json
# P(A beats B) = 1 / (1 + exp(-(pts_a - pts_b) / scale))
VRS_SCALE_BO3 = 215.5
VRS_SCALE_BO1 = 305.0


def esc(val: Any) -> str:
    """Strict HTML escaping for all interpolated text and attributes."""
    if val is None:
        return ""
    return html.escape(str(val), quote=True)


def devig_decimal(odds_a_str: str, odds_b_str: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Convert decimal odds pair into de-vigged probabilities and bookmaker overround (%)."""
    if not odds_a_str or not odds_b_str:
        return None, None, None
    a = float(odds_a_str)
    b = float(odds_b_str)
    inv_a = 1.0 / a
    inv_b = 1.0 / b
    overround = inv_a + inv_b
    prob_a = inv_a / overround
    prob_b = inv_b / overround
    vig_pct = (overround - 1.0) * 100.0
    return prob_a, prob_b, vig_pct


def vrs_logistic_prob(pts_a_str: str, pts_b_str: str, fmt: str) -> Tuple[Optional[float], Optional[float]]:
    """Compute win probability from official Valve VRS points using format-specific scale."""
    if not pts_a_str or not pts_b_str:
        return None, None
    pts_a = float(pts_a_str)
    pts_b = float(pts_b_str)
    scale = VRS_SCALE_BO1 if fmt.upper() == "BO1" else VRS_SCALE_BO3
    diff = pts_a - pts_b
    pa = 1.0 / (1.0 + math.exp(-diff / scale))
    pb = 1.0 - pa
    return pa, pb


# Complete 32-match October 2026 Hotspawn CS2 Pick'em dataset verified at 2026-10-13T21:20:00Z
OCTOBER_32_RAW: List[Dict[str, str]] = [
    {
        "code": "H-00",
        "hotspawn_id": "1079948",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079948",
        "lobby_visibility": "COMPLETED_DROPPED_FROM_LOBBY",
        "match_status": "COMPLETED_2_0_A",
        "status_note": "Completed 2-0 Black Phoenix (Dust2 13-4, Anubis 13-8) on HLTV #2399297; removed from active /lobby filter (91 -> 90).",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #11",
        "format": "BO3",
        "start_utc": "2026-10-13T17:00:00Z",
        "lock_utc": "2026-10-13T16:54:00Z",
        "team_a": "Black Phoenix",
        "team_b": "6666",
        "vrs_rank_a": "",
        "vrs_pts_a": "",
        "vrs_url_a": "",
        "vrs_rank_b": "127",
        "vrs_pts_b": "923",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0127--6666--amster-denzy-kl1o-rendysky-skch.md",
        "hltv_rank_a": "125",
        "hltv_pts_a": "15",
        "hltv_rank_b": "80",
        "hltv_pts_b": "34",
        "hltv_match_id": "2399297",
        "hltv_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11",
        "book_source": "EGamersWorld (BC.Game pre-match)",
        "book_odds_a": "1.45",
        "book_odds_b": "2.45",
        "book_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/black-phoenix-vs-6666-e50h8xR2b",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "46",
        "crowd_pct_b": "54",
        "flag_code": "FLG-06",
        "flag_note": "Black Phoenix unranked in 2026-10-05 Valve VRS; pre-match BC.Game/EGW line (1.45 / 2.45) priced Black Phoenix 62.8% favorite and Black Phoenix won 2-0.",
    },
    {
        "code": "H-01",
        "hotspawn_id": "1079981",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079981",
        "lobby_visibility": "LOCKED_LIVE_IN_FILTER",
        "match_status": "LIVE_LOCKED",
        "status_note": "Locked at 20:54 UTC; Live on HLTV #2399204 (Dust2, Ancient, Anubis).",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "ESL Challenger League Season 52: South America - Cup #3",
        "format": "BO3",
        "start_utc": "2026-10-13T21:00:00Z",
        "lock_utc": "2026-10-13T20:54:00Z",
        "team_a": "ex-Keyd Stars",
        "team_b": "Galorys",
        "vrs_rank_a": "195",
        "vrs_pts_a": "743",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0195--ex-keyd_stars--cutzmeretz-desh-flash-lash-t9rnay.md",
        "vrs_rank_b": "98",
        "vrs_pts_b": "1046",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0098--galorys--card-destiny-nython-pepe-tatu.md",
        "hltv_rank_a": "197",
        "hltv_pts_a": "6",
        "hltv_rank_b": "126",
        "hltv_pts_b": "15",
        "hltv_match_id": "2399204",
        "hltv_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "2.49",
        "book_odds_b": "1.46",
        "book_url": "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp",
        "pinnacle_odds_a": "2.51",
        "pinnacle_odds_b": "1.48",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-esl-challenger-league/ex-keyd-stars-vs-galorys/1615916420/",
        "crowd_pct_a": "29",
        "crowd_pct_b": "71",
        "flag_code": "FLG-06",
        "flag_note": "Match locked at 20:54 UTC and is currently Live; pre-lock Pinnacle (2.51/1.48) and EGW (2.49/1.46) + VRS (#195 vs #98) all confirm Galorys.",
    },
    {
        "code": "H-27",
        "hotspawn_id": "",
        "hotspawn_url": HOTSPAWN_LOBBY_URL,
        "lobby_visibility": "LOBBY_ONLY_NEW_OCT13",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Added to play.hotspawn.com/lobby at ~21:00 UTC (absent on /cs2-pickems); no [View Match] ID on card.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT South America 2026 Series #7",
        "format": "BO3",
        "start_utc": "2026-10-13T22:00:00Z",
        "lock_utc": "2026-10-13T21:54:00Z",
        "team_a": "SUKEBAN",
        "team_b": "your end",
        "vrs_rank_a": "",
        "vrs_pts_a": "",
        "vrs_url_a": "",
        "vrs_rank_b": "295",
        "vrs_pts_b": "582",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0295--your_end--cr1a-ghost1-lcs-lukita-rx.md",
        "hltv_rank_a": "",
        "hltv_pts_a": "",
        "hltv_rank_b": "215",
        "hltv_pts_b": "4",
        "hltv_match_id": "2399460",
        "hltv_url": "https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-series-7",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "2.37",
        "book_odds_b": "1.53",
        "book_url": "https://egamersworld.com/counterstrike/match/0U32SId-H/your-end-vs-sukeban-uZgmpQMyd7",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "19",
        "crowd_pct_b": "81",
        "flag_code": "FLG-02",
        "flag_note": "New /lobby card lacks a Hotspawn match ID and reverses HLTV/EGW team order (EGW lists your end 1.53 vs SUKEBAN 2.37; mapped to SUKEBAN 2.37 vs your end 1.53). SUKEBAN is unranked in VRS/HLTV.",
    },
    {
        "code": "H-02",
        "hotspawn_id": "1080643",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1080643",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "ESL Challenger League Season 52: North America - Cup #3",
        "format": "BO3",
        "start_utc": "2026-10-14T01:00:00Z",
        "lock_utc": "2026-10-14T00:54:00Z",
        "team_a": "Zomblers",
        "team_b": "Overtake Sector",
        "vrs_rank_a": "254",
        "vrs_pts_a": "639",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0254--zomblers--cajun-coolcoms-fxre-man327-pose1donn.md",
        "vrs_rank_b": "177",
        "vrs_pts_b": "774",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0177--overtake_sector--corim-intra-jason-learsi-umar.md",
        "hltv_rank_a": "203",
        "hltv_pts_a": "5",
        "hltv_rank_b": "170",
        "hltv_pts_b": "8",
        "hltv_match_id": "2399232",
        "hltv_url": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "2.46",
        "book_odds_b": "1.51",
        "book_url": "https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_",
        "pinnacle_odds_a": "2.45",
        "pinnacle_odds_b": "1.50",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-esl-challenger-league/zomblers-vs-overtake-sector/1615916421/",
        "crowd_pct_a": "71",
        "crowd_pct_b": "29",
        "flag_code": "FLG-11",
        "flag_note": "Major contrarian pick: Hotspawn crowd backs Zomblers 71%, whereas Pinnacle (2.45/1.50), EGW (2.46/1.51), VRS (#254 vs #177), and HLTV (#203 vs #170) all favor Overtake Sector (64.1% originated).",
    },
    {
        "code": "H-03",
        "hotspawn_id": "1079949",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079949",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #11",
        "format": "BO3",
        "start_utc": "2026-10-14T08:00:00Z",
        "lock_utc": "2026-10-14T07:54:00Z",
        "team_a": "Gothic",
        "team_b": "Lavked",
        "vrs_rank_a": "211",
        "vrs_pts_a": "705",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0211--gothic--get_jeka-raijin-ryujin-shg-synyx.md",
        "vrs_rank_b": "143",
        "vrs_pts_b": "862",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0143--lavked--1nvisiblee-azukay-k4nfuz-sol-xm1nd.md",
        "hltv_rank_a": "176",
        "hltv_pts_a": "7",
        "hltv_rank_b": "119",
        "hltv_pts_b": "16",
        "hltv_match_id": "2399298",
        "hltv_url": "https://www.hltv.org/matches/2399298/gothic-vs-lavked-cct-2026-europe-series-11",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.881",
        "book_odds_b": "1.782",
        "book_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "55",
        "crowd_pct_b": "45",
        "flag_code": "FLG-11",
        "flag_note": "Contrarian edge: Hotspawn crowd leans Gothic (55%), while EGW (1.881 vs 1.782), VRS (#211 vs #143), and HLTV (#176 vs #119) all favor Lavked (57.4% originated).",
    },
    {
        "code": "H-28",
        "hotspawn_id": "",
        "hotspawn_url": HOTSPAWN_LOBBY_URL,
        "lobby_visibility": "LOBBY_ONLY_NEW_OCT13",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Added to play.hotspawn.com/lobby at ~21:00 UTC (absent on /cs2-pickems); no [View Match] ID on card.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #12 Play-In",
        "format": "BO3",
        "start_utc": "2026-10-14T08:00:00Z",
        "lock_utc": "2026-10-14T07:54:00Z",
        "team_a": "Enjoy",
        "team_b": "B8 Academy",
        "vrs_rank_a": "138",
        "vrs_pts_a": "871",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0138--enjoy--kurosa-nbl-roxesz-sh1geo-zazzer.md",
        "vrs_rank_b": "261",
        "vrs_pts_b": "631",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0261--b8_academy--k1n-r0se-segukawa-sherman.md",
        "hltv_rank_a": "199",
        "hltv_pts_a": "5",
        "hltv_rank_b": "229",
        "hltv_pts_b": "4",
        "hltv_match_id": "2399461",
        "hltv_url": "https://www.hltv.org/matches/2399461/enjoy-vs-b8-academy-cct-2026-europe-series-12-closed-qualifier",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.52",
        "book_odds_b": "2.30",
        "book_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "33",
        "crowd_pct_b": "67",
        "flag_code": "FLG-02",
        "flag_note": "New /lobby card lacks Hotspawn match ID. Strong contrarian pick: Hotspawn crowd backs B8 Academy 67% on brand recognition, while EGW (1.52/2.30 = 60.2%), VRS (#138 871 pts vs #261 631 pts), and HLTV (#199 vs #229) all strongly favor Enjoy (64.7% originated).",
    },
    {
        "code": "H-04",
        "hotspawn_id": "1081467",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081467",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "S",
        "points": "6",
        "multiplier": "1.50",
        "tournament": "Thunderpick World Championship 2026",
        "format": "BO3",
        "start_utc": "2026-10-14T08:30:00Z",
        "lock_utc": "2026-10-14T08:24:00Z",
        "team_a": "9z",
        "team_b": "Aurora",
        "vrs_rank_a": "39",
        "vrs_pts_a": "1285",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0039--9z--buda-dgt-huasopeek-martinezsa-max.md",
        "vrs_rank_b": "9",
        "vrs_pts_b": "1674",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0009--aurora--jottaaa-maj3r-soulfly-wicadia-xantares.md",
        "hltv_rank_a": "41",
        "hltv_pts_a": "245",
        "hltv_rank_b": "9",
        "hltv_pts_b": "658",
        "hltv_match_id": "2399384",
        "hltv_url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "3.86",
        "book_odds_b": "1.21",
        "book_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb",
        "pinnacle_odds_a": "4.29",
        "pinnacle_odds_b": "1.21",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-thunderpick-world-championship/9z-team-vs-aurora-gaming/1615904970/",
        "crowd_pct_a": "15",
        "crowd_pct_b": "85",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-05",
        "hotspawn_id": "1079678",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079678",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "B",
        "points": "3",
        "multiplier": "1.25",
        "tournament": "Stake Pulse Beat III",
        "format": "BO3",
        "start_utc": "2026-10-14T10:00:00Z",
        "lock_utc": "2026-10-14T09:54:00Z",
        "team_a": "Astralis",
        "team_b": "Sashi",
        "vrs_rank_a": "12",
        "vrs_pts_a": "1586",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0012--astralis--hooxi-jabbi-phzy-ryu-staehr.md",
        "vrs_rank_b": "117",
        "vrs_pts_b": "975",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0117--sashi--acoR-cabbi-lucky-mistR-notaN.md",
        "hltv_rank_a": "12",
        "hltv_pts_a": "543",
        "hltv_rank_b": "107",
        "hltv_pts_b": "20",
        "hltv_match_id": "2399134",
        "hltv_url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "1.09",
        "book_odds_b": "6.38",
        "book_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z",
        "pinnacle_odds_a": "1.11",
        "pinnacle_odds_b": "6.31",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-stake-pulse-beat/astralis-vs-sashi-esport/1615911012/",
        "crowd_pct_a": "88",
        "crowd_pct_b": "12",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-06",
        "hotspawn_id": "1079679",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079679",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "B",
        "points": "3",
        "multiplier": "1.25",
        "tournament": "Stake Pulse Beat III",
        "format": "BO3",
        "start_utc": "2026-10-14T10:00:00Z",
        "lock_utc": "2026-10-14T09:54:00Z",
        "team_a": "HOTU",
        "team_b": "fnatic",
        "vrs_rank_a": "37",
        "vrs_pts_a": "1292",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0037--hotu--dukefissura-frontales-kade0-mizu-n0rb3r7.md",
        "vrs_rank_b": "40",
        "vrs_pts_b": "1276",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0040--fnatic--blamef-fEAR-jambo-krabeni-s0und.md",
        "hltv_rank_a": "36",
        "hltv_pts_a": "286",
        "hltv_rank_b": "42",
        "hltv_pts_b": "237",
        "hltv_match_id": "2399135",
        "hltv_url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "1.89",
        "book_odds_b": "1.81",
        "book_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC",
        "pinnacle_odds_a": "1.95",
        "pinnacle_odds_b": "1.83",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-stake-pulse-beat/hotu-vs-fnatic/1615911013/",
        "crowd_pct_a": "32",
        "crowd_pct_b": "68",
        "flag_code": "FLG-10",
        "flag_note": "Near-50/50 toss-up: Pinnacle (1.95/1.83 = 48.4%/51.6%) and EGW (1.89/1.81 = 48.9%/51.1%) slightly favor fnatic, while VRS (#37 1292 pts vs #40 1276 pts) and HLTV (#36 vs #42) give HOTU a 51.9% rating edge. Blended pick: fnatic (50.3%).",
    },
    {
        "code": "H-07",
        "hotspawn_id": "1079950",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079950",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #11",
        "format": "BO3",
        "start_utc": "2026-10-14T11:00:00Z",
        "lock_utc": "2026-10-14T10:54:00Z",
        "team_a": "ex-RUSTEC",
        "team_b": "mellren",
        "vrs_rank_a": "92",
        "vrs_pts_a": "1066",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0092--ex-rustec--brilliance-glowiing-shalfey-yiksrezo-youka.md",
        "vrs_rank_b": "125",
        "vrs_pts_b": "932",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0125--mellren--lollipop21k-maksilvl-mdl-menddel-shootic.md",
        "hltv_rank_a": "79",
        "hltv_pts_a": "35",
        "hltv_rank_b": "94",
        "hltv_pts_b": "25",
        "hltv_match_id": "2399299",
        "hltv_url": "https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.40",
        "book_odds_b": "2.68",
        "book_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "69",
        "crowd_pct_b": "31",
        "flag_code": "FLG-05",
        "flag_note": "Previously had 1.80/1.80 EGW placeholder and VRS #92 vs #152 ambiguity; now verified at 21:20 UTC with live EGW bookmaker odds (1.40 / 2.68 = 65.7% ex-RUSTEC) and HLTV #2399299 lineup (shalfey, youka, Brilliance = VRS #92, 1066 pts).",
    },
    {
        "code": "H-08",
        "hotspawn_id": "1081468",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081468",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "S",
        "points": "6",
        "multiplier": "1.50",
        "tournament": "Thunderpick World Championship 2026",
        "format": "BO3",
        "start_utc": "2026-10-14T11:00:00Z",
        "lock_utc": "2026-10-14T10:54:00Z",
        "team_a": "Falcons",
        "team_b": "Ninjas in Pyjamas",
        "vrs_rank_a": "7",
        "vrs_pts_a": "1758",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0007--falcons--kyousuke-kyxsan-m0nesy-niko-teses.md",
        "vrs_rank_b": "20",
        "vrs_pts_b": "1467",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0020--ninjas_in_pyjamas--cairne-r1nkle-sjuush-snappi-xKacpersky.md",
        "hltv_rank_a": "6",
        "hltv_pts_a": "867",
        "hltv_rank_b": "18",
        "hltv_pts_b": "482",
        "hltv_match_id": "2399385",
        "hltv_url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "1.23",
        "book_odds_b": "3.81",
        "book_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/falcons-vs-nip-QSa-aeOIR",
        "pinnacle_odds_a": "1.23",
        "pinnacle_odds_b": "4.08",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-thunderpick-world-championship/team-falcons-vs-ninjas-in-pyjamas/1615904971/",
        "crowd_pct_a": "82",
        "crowd_pct_b": "18",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-29",
        "hotspawn_id": "",
        "hotspawn_url": HOTSPAWN_LOBBY_URL,
        "lobby_visibility": "LOBBY_ONLY_NEW_OCT13",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Added to play.hotspawn.com/lobby at ~21:00 UTC (absent on /cs2-pickems); no [View Match] ID on card.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #12 Play-In",
        "format": "BO3",
        "start_utc": "2026-10-14T11:00:00Z",
        "lock_utc": "2026-10-14T10:54:00Z",
        "team_a": "Banda chuya",
        "team_b": "6666",
        "vrs_rank_a": "165",
        "vrs_pts_a": "801",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0165--banda_chuya--adrien-ezox-maaryy-showk-tomiko.md",
        "vrs_rank_b": "127",
        "vrs_pts_b": "923",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0127--6666--amster-denzy-kl1o-rendysky-skch.md",
        "hltv_rank_a": "",
        "hltv_pts_a": "",
        "hltv_rank_b": "80",
        "hltv_pts_b": "34",
        "hltv_match_id": "2399462",
        "hltv_url": "https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier",
        "book_source": "",
        "book_odds_a": "",
        "book_odds_b": "",
        "book_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "24",
        "crowd_pct_b": "76",
        "flag_code": "FLG-03",
        "flag_note": "EGamersWorld shows 1.80/1.80 default placeholder -> bookmaker odds left strictly BLANK. Official HLTV match #2399462 confirms Banda Chuya lineup (tomiko, maaryy, AdrieN, Showk, ezox = VRS #165, 801 pts) vs 6666 lineup (skcH, amster, rendysky, kL1o = VRS #127, 923 pts, HLTV #80). Originated VRS model favors 6666 (63.8%).",
    },
    {
        "code": "H-09",
        "hotspawn_id": "1081469",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081469",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "S",
        "points": "6",
        "multiplier": "1.50",
        "tournament": "Thunderpick World Championship 2026",
        "format": "BO3",
        "start_utc": "2026-10-14T13:30:00Z",
        "lock_utc": "2026-10-14T13:24:00Z",
        "team_a": "Legacy",
        "team_b": "PVISION",
        "vrs_rank_a": "19",
        "vrs_pts_a": "1477",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0019--legacy--arT-dumau-latto-lux-saadzin.md",
        "vrs_rank_b": "8",
        "vrs_pts_b": "1750",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0008--parivision--BELCHONOKK-Jame-nota-xiELO-zweih.md",
        "hltv_rank_a": "20",
        "hltv_pts_a": "475",
        "hltv_rank_b": "7",
        "hltv_pts_b": "812",
        "hltv_match_id": "2399386",
        "hltv_url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.68",
        "book_odds_b": "2.10",
        "book_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/legacy-vs-parivision--TTc59QUDJ",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "33",
        "crowd_pct_b": "67",
        "flag_code": "FLG-08",
        "flag_note": "Major Market vs VRS/HLTV divergence (SA-09): Bookmaker market (EGW/BC.Game 1.68 / 2.10) prices Legacy 55.6% favorite, whereas Valve VRS (#19 1477 pts vs #8 1750 pts) and HLTV (#20 vs #7) rate PVISION (PARIVISION) at 78.0%. Primary market pick: Legacy (55.6%); VRS model pick: PVISION (78.0%).",
    },
    {
        "code": "H-10",
        "hotspawn_id": "1079951",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079951",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #11",
        "format": "BO3",
        "start_utc": "2026-10-14T14:00:00Z",
        "lock_utc": "2026-10-14T13:54:00Z",
        "team_a": "G2 Ares",
        "team_b": "The Last Resort",
        "vrs_rank_a": "129",
        "vrs_pts_a": "913",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0129--g2_ares--hitori-junyme-shine-tmkj-yksjupe.md",
        "vrs_rank_b": "126",
        "vrs_pts_b": "926",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0126--the_last_resort--artist-bevve-extinct-girafffe-vacancy.md",
        "hltv_rank_a": "124",
        "hltv_pts_a": "15",
        "hltv_rank_b": "142",
        "hltv_pts_b": "11",
        "hltv_match_id": "2399300",
        "hltv_url": "https://www.hltv.org/matches/2399300/g2-ares-vs-the-last-resort-cct-2026-europe-series-11",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.465",
        "book_odds_b": "2.436",
        "book_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "78",
        "crowd_pct_b": "22",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-30",
        "hotspawn_id": "",
        "hotspawn_url": HOTSPAWN_LOBBY_URL,
        "lobby_visibility": "LOBBY_ONLY_NEW_OCT13",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Added to play.hotspawn.com/lobby at ~21:00 UTC (absent on /cs2-pickems); no [View Match] ID on card.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #12 Play-In",
        "format": "BO3",
        "start_utc": "2026-10-14T14:00:00Z",
        "lock_utc": "2026-10-14T13:54:00Z",
        "team_a": "Ryvex",
        "team_b": "PCIFIC",
        "vrs_rank_a": "207",
        "vrs_pts_a": "714",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0207--ryvex--jeyn-n0r1-oskvr-swaggy-tvs.md",
        "vrs_rank_b": "139",
        "vrs_pts_b": "870",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0139--pcific--jresy-l0gicman-lugsen-oyesil-scollen.md",
        "hltv_rank_a": "181",
        "hltv_pts_a": "6",
        "hltv_rank_b": "135",
        "hltv_pts_b": "13",
        "hltv_match_id": "2399463",
        "hltv_url": "https://www.hltv.org/matches/2399463/pcific-vs-ryvex-cct-2026-europe-series-12-closed-qualifier",
        "book_source": "",
        "book_odds_a": "",
        "book_odds_b": "",
        "book_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "25",
        "crowd_pct_b": "75",
        "flag_code": "FLG-03",
        "flag_note": "EGamersWorld shows 1.80/1.80 default placeholder -> bookmaker odds left strictly BLANK. Official HLTV match #2399463 & Valve VRS confirm Ryvex (VRS #207, 714 pts, HLTV #181) vs PCIFIC (VRS #139, 870 pts, HLTV #135). Originated VRS model favors PCIFIC (67.3%).",
    },
    {
        "code": "H-11",
        "hotspawn_id": "1081470",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081470",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "S",
        "points": "6",
        "multiplier": "1.50",
        "tournament": "Thunderpick World Championship 2026",
        "format": "BO3",
        "start_utc": "2026-10-14T16:00:00Z",
        "lock_utc": "2026-10-14T15:54:00Z",
        "team_a": "FURIA",
        "team_b": "BB Team",
        "vrs_rank_a": "2",
        "vrs_pts_a": "1911",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0002--furia--fallen-kscerato-molodoy-yekindar-yuurih.md",
        "vrs_rank_b": "27",
        "vrs_pts_b": "1410",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0027--betboom--artfr0st-boombl4-danistzz-magnojez-s1ren.md",
        "hltv_rank_a": "4",
        "hltv_pts_a": "877",
        "hltv_rank_b": "26",
        "hltv_pts_b": "395",
        "hltv_match_id": "2399387",
        "hltv_url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.40",
        "book_odds_b": "2.81",
        "book_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "75",
        "crowd_pct_b": "25",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-12",
        "hotspawn_id": "1081800",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081800",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T08:00:00Z",
        "lock_utc": "2026-10-15T07:54:00Z",
        "team_a": "WBT",
        "team_b": "EA Copenhagen",
        "vrs_rank_a": "60",
        "vrs_pts_a": "1201",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0060--wbt--demqq-psycho-s4ltovsk1yy-smash-tyr1k.md",
        "vrs_rank_b": "",
        "vrs_pts_b": "",
        "vrs_url_b": "",
        "hltv_rank_a": "",
        "hltv_pts_a": "",
        "hltv_rank_b": "220",
        "hltv_pts_b": "4",
        "hltv_match_id": "2399418",
        "hltv_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "2.01",
        "book_odds_b": "1.69",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ea-copenhagen-hSC7a2mtP",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "33",
        "crowd_pct_b": "67",
        "flag_code": "FLG-07",
        "flag_note": "WBT vs WBT Academy VRS ambiguity (SA-06): VRS lists #60 WBT (1201 pts) and #130 WBT Academy (911 pts), while EA Copenhagen is unranked in VRS (#220 HLTV). Bookmaker market prices EA Copenhagen 54.3% favorite (1.69 vs 2.01) in LAN BO1.",
    },
    {
        "code": "H-13",
        "hotspawn_id": "1081801",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081801",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T10:00:00Z",
        "lock_utc": "2026-10-15T09:54:00Z",
        "team_a": "ENCE",
        "team_b": "BOJONG",
        "vrs_rank_a": "105",
        "vrs_pts_a": "1025",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0105--ence--henu-joeski-millert-schwarz-teme.md",
        "vrs_rank_b": "363",
        "vrs_pts_b": "463",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0363--bojong--artwoo-blngb0ng-jkzin-stunt-villeboe.md",
        "hltv_rank_a": "83",
        "hltv_pts_a": "30",
        "hltv_rank_b": "241",
        "hltv_pts_b": "3",
        "hltv_match_id": "2399419",
        "hltv_url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.28",
        "book_odds_b": "3.22",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "88",
        "crowd_pct_b": "12",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-14",
        "hotspawn_id": "1079680",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079680",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "B",
        "points": "3",
        "multiplier": "1.25",
        "tournament": "Stake Pulse Beat III",
        "format": "BO3",
        "start_utc": "2026-10-15T10:00:00Z",
        "lock_utc": "2026-10-15T09:54:00Z",
        "team_a": "HEROIC",
        "team_b": "Envy",
        "vrs_rank_a": "25",
        "vrs_pts_a": "1417",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0025--heroic--alkarenn-chr1zn-nil0-susp-yxngstxr.md",
        "vrs_rank_b": "87",
        "vrs_pts_b": "1076",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0087--envy--ayy-birdfromsky-bitchird-krasnal-shield.md",
        "hltv_rank_a": "25",
        "hltv_pts_a": "426",
        "hltv_rank_b": "74",
        "hltv_pts_b": "41",
        "hltv_match_id": "2399137",
        "hltv_url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "1.45",
        "book_odds_b": "2.47",
        "book_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC",
        "pinnacle_odds_a": "1.47",
        "pinnacle_odds_b": "2.61",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-stake-pulse-beat/heroic-vs-team-envy/1615911014/",
        "crowd_pct_a": "80",
        "crowd_pct_b": "20",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-15",
        "hotspawn_id": "1079681",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079681",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "B",
        "points": "3",
        "multiplier": "1.25",
        "tournament": "Stake Pulse Beat III",
        "format": "BO3",
        "start_utc": "2026-10-15T10:00:00Z",
        "lock_utc": "2026-10-15T09:54:00Z",
        "team_a": "MIBR",
        "team_b": "BC.Game",
        "vrs_rank_a": "42",
        "vrs_pts_a": "1266",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0042--mibr--brnz4n-exit-insani-kl1m-venomzera.md",
        "vrs_rank_b": "34",
        "vrs_pts_b": "1314",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0034--bc_game--aragornn-electroNic-mutiris-s1mple-story.md",
        "hltv_rank_a": "40",
        "hltv_pts_a": "255",
        "hltv_rank_b": "34",
        "hltv_pts_b": "308",
        "hltv_match_id": "2399136",
        "hltv_url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii",
        "book_source": "Pinnacle + EGamersWorld (BC.Game)",
        "book_odds_a": "1.69",
        "book_odds_b": "2.06",
        "book_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX",
        "pinnacle_odds_a": "1.70",
        "pinnacle_odds_b": "2.11",
        "pinnacle_url": "https://www.pinnacle.com/en/esports/cs2-stake-pulse-beat/mibr-vs-bc-game-esports/1615911015/",
        "crowd_pct_a": "52",
        "crowd_pct_b": "48",
        "flag_code": "FLG-10",
        "flag_note": "Market vs VRS mild split: Both Pinnacle (1.70/2.11 = 55.4% MIBR) and EGW (1.69/2.06 = 54.9% MIBR) price MIBR favorite on Stockholm LAN, whereas VRS (#42 1266 pts vs #34 1314 pts) and HLTV (#40 vs #34) give BC.Game a 55.5% rating edge. Blended pick: MIBR (51.8%).",
    },
    {
        "code": "H-16",
        "hotspawn_id": "1081802",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081802",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T12:00:00Z",
        "lock_utc": "2026-10-15T11:54:00Z",
        "team_a": "WBT",
        "team_b": "ENCE",
        "vrs_rank_a": "60",
        "vrs_pts_a": "1201",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0060--wbt--demqq-psycho-s4ltovsk1yy-smash-tyr1k.md",
        "vrs_rank_b": "105",
        "vrs_pts_b": "1025",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0105--ence--henu-joeski-millert-schwarz-teme.md",
        "hltv_rank_a": "",
        "hltv_pts_a": "",
        "hltv_rank_b": "83",
        "hltv_pts_b": "30",
        "hltv_match_id": "2399420",
        "hltv_url": "https://www.hltv.org/matches/2399420/wbt-vs-ence-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.62",
        "book_odds_b": "2.107",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "16",
        "crowd_pct_b": "84",
        "flag_code": "FLG-07",
        "flag_note": "Major contrarian pick (+45.0% vs Hotspawn crowd): Crowd backs ENCE 84% on legacy brand name, while EGW bookmaker odds (1.62 vs 2.107 = 56.5% WBT) and main VRS (#60 1201 pts vs #105 ENCE Academy roster 1025 pts) both favor WBT (61.0% originated).",
    },
    {
        "code": "H-17",
        "hotspawn_id": "1081803",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081803",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T14:00:00Z",
        "lock_utc": "2026-10-15T13:54:00Z",
        "team_a": "EA Copenhagen",
        "team_b": "BOJONG",
        "vrs_rank_a": "",
        "vrs_pts_a": "",
        "vrs_url_a": "",
        "vrs_rank_b": "363",
        "vrs_pts_b": "463",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0363--bojong--artwoo-blngb0ng-jkzin-stunt-villeboe.md",
        "hltv_rank_a": "220",
        "hltv_pts_a": "4",
        "hltv_rank_b": "241",
        "hltv_pts_b": "3",
        "hltv_match_id": "2399421",
        "hltv_url": "https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.19",
        "book_odds_b": "4.02",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "80",
        "crowd_pct_b": "20",
        "flag_code": "FLG-09",
        "flag_note": "EA Copenhagen is unranked in 2026-10-05 Valve VRS (HLTV #220 vs BOJONG #241); originated probability (77.2% EA Copenhagen) uses verified EGW bookmaker line (1.19 / 4.02).",
    },
    {
        "code": "H-18",
        "hotspawn_id": "1081804",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081804",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T16:00:00Z",
        "lock_utc": "2026-10-15T15:54:00Z",
        "team_a": "WBT",
        "team_b": "BOJONG",
        "vrs_rank_a": "60",
        "vrs_pts_a": "1201",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0060--wbt--demqq-psycho-s4ltovsk1yy-smash-tyr1k.md",
        "vrs_rank_b": "363",
        "vrs_pts_b": "463",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0363--bojong--artwoo-blngb0ng-jkzin-stunt-villeboe.md",
        "hltv_rank_a": "",
        "hltv_pts_a": "",
        "hltv_rank_b": "241",
        "hltv_pts_b": "3",
        "hltv_match_id": "2399422",
        "hltv_url": "https://www.hltv.org/matches/2399422/wbt-vs-bojong-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.21",
        "book_odds_b": "3.99",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "78",
        "crowd_pct_b": "22",
        "flag_code": "FLG-07",
        "flag_note": "Both WBT (#60 VRS 1201 pts) and WBT Academy (#130 VRS 911 pts) strongly outrate BOJONG (#363 VRS 463 pts), matching EGW bookmaker odds (1.21 / 3.99 = 76.7% WBT).",
    },
    {
        "code": "H-19",
        "hotspawn_id": "1081805",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081805",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-15T18:00:00Z",
        "lock_utc": "2026-10-15T17:54:00Z",
        "team_a": "EA Copenhagen",
        "team_b": "ENCE",
        "vrs_rank_a": "",
        "vrs_pts_a": "",
        "vrs_url_a": "",
        "vrs_rank_b": "105",
        "vrs_pts_b": "1025",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0105--ence--henu-joeski-millert-schwarz-teme.md",
        "hltv_rank_a": "220",
        "hltv_pts_a": "4",
        "hltv_rank_b": "83",
        "hltv_pts_b": "30",
        "hltv_match_id": "2399423",
        "hltv_url": "https://www.hltv.org/matches/2399423/eac-vs-ence-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.51",
        "book_odds_b": "2.35",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "16",
        "crowd_pct_b": "84",
        "flag_code": "FLG-09",
        "flag_note": "Major contrarian pick (+44.9% vs Hotspawn crowd): EGW bookmakers price EA Copenhagen as 1.51 favorite (60.9%) against ENCE (2.35 / 39.1%) in Tampere LAN BO1 despite ENCE holding HLTV #83 / VRS #105.",
    },
    {
        "code": "H-20",
        "hotspawn_id": "1081806",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081806",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T08:00:00Z",
        "lock_utc": "2026-10-16T07:54:00Z",
        "team_a": "Voca",
        "team_b": "Phantom",
        "vrs_rank_a": "68",
        "vrs_pts_a": "1182",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0068--voca--dare-junior-marke-nosrac-snav.md",
        "vrs_rank_b": "72",
        "vrs_pts_b": "1147",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0072--phantom--kei-kunai-kylar-nicoodoz-tmb.md",
        "hltv_rank_a": "59",
        "hltv_pts_a": "84",
        "hltv_rank_b": "67",
        "hltv_pts_b": "57",
        "hltv_match_id": "2399424",
        "hltv_url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.87",
        "book_odds_b": "1.77",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "64",
        "crowd_pct_b": "36",
        "flag_code": "FLG-10",
        "flag_note": "True 50/50 BO1 toss-up: EGW bookmaker line (1.87 / 1.77) gives Phantom 51.4%, while Valve VRS (#68 1182 pts vs #72 1147 pts) and HLTV (#59 vs #67) give Voca 52.9%. Market pick: Phantom (51.4%); VRS model pick: Voca (52.9%).",
    },
    {
        "code": "H-21",
        "hotspawn_id": "1081807",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081807",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T10:00:00Z",
        "lock_utc": "2026-10-16T09:54:00Z",
        "team_a": "HAVU",
        "team_b": "Rounds",
        "vrs_rank_a": "124",
        "vrs_pts_a": "937",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0124--havu--8juho8-alxc-ottob-p3kko-uli.md",
        "vrs_rank_b": "310",
        "vrs_pts_b": "548",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0310--rounds--kollo-lapa-monoxx-tumppis-ykis.md",
        "hltv_rank_a": "120",
        "hltv_pts_a": "16",
        "hltv_rank_b": "",
        "hltv_pts_b": "",
        "hltv_match_id": "2399425",
        "hltv_url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.21",
        "book_odds_b": "3.96",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "85",
        "crowd_pct_b": "15",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-22",
        "hotspawn_id": "1081808",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081808",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T12:00:00Z",
        "lock_utc": "2026-10-16T11:54:00Z",
        "team_a": "Voca",
        "team_b": "HAVU",
        "vrs_rank_a": "68",
        "vrs_pts_a": "1182",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0068--voca--dare-junior-marke-nosrac-snav.md",
        "vrs_rank_b": "124",
        "vrs_pts_b": "937",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0124--havu--8juho8-alxc-ottob-p3kko-uli.md",
        "hltv_rank_a": "59",
        "hltv_pts_a": "84",
        "hltv_rank_b": "120",
        "hltv_pts_b": "16",
        "hltv_match_id": "2399426",
        "hltv_url": "https://www.hltv.org/matches/2399426/voca-vs-havu-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.38",
        "book_odds_b": "2.70",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "41",
        "crowd_pct_b": "59",
        "flag_code": "FLG-11",
        "flag_note": "Strong contrarian pick (+26.5% vs Hotspawn crowd): Crowd backs HAVU 59% on Finnish home-crowd name recognition, while EGW (1.38 / 2.70 = 66.2% Voca), VRS (#68 1182 pts vs #124 937 pts), and HLTV (#59 vs #120) all favor Voca (67.5% originated).",
    },
    {
        "code": "H-23",
        "hotspawn_id": "1081809",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081809",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T14:00:00Z",
        "lock_utc": "2026-10-16T13:54:00Z",
        "team_a": "Phantom",
        "team_b": "Rounds",
        "vrs_rank_a": "72",
        "vrs_pts_a": "1147",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0072--phantom--kei-kunai-kylar-nicoodoz-tmb.md",
        "vrs_rank_b": "310",
        "vrs_pts_b": "548",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0310--rounds--kollo-lapa-monoxx-tumppis-ykis.md",
        "hltv_rank_a": "67",
        "hltv_pts_a": "57",
        "hltv_rank_b": "",
        "hltv_pts_b": "",
        "hltv_match_id": "2399427",
        "hltv_url": "https://www.hltv.org/matches/2399427/phantom-vs-rounds-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.05",
        "book_odds_b": "7.11",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "78",
        "crowd_pct_b": "22",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-31",
        "hotspawn_id": "",
        "hotspawn_url": HOTSPAWN_LOBBY_URL,
        "lobby_visibility": "LOBBY_ONLY_NEW_OCT13",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Added to play.hotspawn.com/lobby at ~21:00 UTC (absent on /cs2-pickems); no [View Match] ID on card.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "CCT Europe 2026 Series #12 Play-In",
        "format": "BO3",
        "start_utc": "2026-10-16T14:00:00Z",
        "lock_utc": "2026-10-16T13:54:00Z",
        "team_a": "mellren",
        "team_b": "Privateer",
        "vrs_rank_a": "125",
        "vrs_pts_a": "932",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0125--mellren--lollipop21k-maksilvl-mdl-menddel-shootic.md",
        "vrs_rank_b": "271",
        "vrs_pts_b": "608",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0271--privateer--ariant0-frazehh-jaustere-m1n1mal-prime.md",
        "hltv_rank_a": "94",
        "hltv_pts_a": "25",
        "hltv_rank_b": "226",
        "hltv_pts_b": "4",
        "hltv_match_id": "2399471",
        "hltv_url": "https://www.hltv.org/matches/2399471/mellren-vs-privateer-cct-2026-europe-series-12-closed-qualifier",
        "book_source": "",
        "book_odds_a": "",
        "book_odds_b": "",
        "book_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/mellren-vs-privateer-gaming-ASh_MyDBS",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "71",
        "crowd_pct_b": "29",
        "flag_code": "FLG-03",
        "flag_note": "EGamersWorld shows 1.80/1.80 default placeholder -> bookmaker odds left strictly BLANK. Official HLTV match #2399471 & Valve VRS confirm mellren (VRS #125, 932 pts, HLTV #94) vs Privateer (VRS #271, 608 pts, HLTV #226). Originated VRS model strongly favors mellren (81.8%).",
    },
    {
        "code": "H-24",
        "hotspawn_id": "1081810",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081810",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T16:00:00Z",
        "lock_utc": "2026-10-16T15:54:00Z",
        "team_a": "Voca",
        "team_b": "Rounds",
        "vrs_rank_a": "68",
        "vrs_pts_a": "1182",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0068--voca--dare-junior-marke-nosrac-snav.md",
        "vrs_rank_b": "310",
        "vrs_pts_b": "548",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0310--rounds--kollo-lapa-monoxx-tumppis-ykis.md",
        "hltv_rank_a": "59",
        "hltv_pts_a": "84",
        "hltv_rank_b": "",
        "hltv_pts_b": "",
        "hltv_match_id": "2399428",
        "hltv_url": "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.063",
        "book_odds_b": "6.40",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "82",
        "crowd_pct_b": "18",
        "flag_code": "",
        "flag_note": "",
    },
    {
        "code": "H-25",
        "hotspawn_id": "1081811",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1081811",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "OPEN_PRELOCK",
        "status_note": "Open pre-lock on both /lobby and /cs2-pickems.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "Elisa BreakOut Series #2",
        "format": "BO1",
        "start_utc": "2026-10-16T18:00:00Z",
        "lock_utc": "2026-10-16T17:54:00Z",
        "team_a": "Phantom",
        "team_b": "HAVU",
        "vrs_rank_a": "72",
        "vrs_pts_a": "1147",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0072--phantom--kei-kunai-kylar-nicoodoz-tmb.md",
        "vrs_rank_b": "124",
        "vrs_pts_b": "937",
        "vrs_url_b": VRS_BASE_URL + "live/2026/details/2026_10_05/0124--havu--8juho8-alxc-ottob-p3kko-uli.md",
        "hltv_rank_a": "67",
        "hltv_pts_a": "57",
        "hltv_rank_b": "120",
        "hltv_pts_b": "16",
        "hltv_match_id": "2399429",
        "hltv_url": "https://www.hltv.org/matches/2399429/phantom-vs-havu-elisa-breakout-series-2",
        "book_source": "EGamersWorld (BC.Game)",
        "book_odds_a": "1.37",
        "book_odds_b": "2.91",
        "book_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "50",
        "crowd_pct_b": "50",
        "flag_code": "FLG-11",
        "flag_note": "Contrarian edge (+17.5% vs Hotspawn crowd): Crowd splits 50/50, while EGW (1.37 / 2.91 = 68.0% Phantom), VRS (#72 1147 pts vs #124 937 pts), and HLTV (#67 vs #120) all favor Phantom (67.5% originated).",
    },
    {
        "code": "H-26",
        "hotspawn_id": "1079654",
        "hotspawn_url": "https://play.hotspawn.com/cs2/match/1079654",
        "lobby_visibility": "BOTH_LOBBY_AND_CS2_PICKEMS",
        "match_status": "FLAGGED_PHANTOM",
        "status_note": "Bogus/stale fixture on Hotspawn: Rebels disbanded in 2025 and neither team is in European Pro League Series 8 on HLTV.",
        "tier": "C",
        "points": "2",
        "multiplier": "1.25",
        "tournament": "European Pro League Series 8",
        "format": "BO5",
        "start_utc": "2026-10-18T10:30:00Z",
        "lock_utc": "2026-10-18T10:24:00Z",
        "team_a": "Eternal Fire",
        "team_b": "Rebels",
        "vrs_rank_a": "73",
        "vrs_pts_a": "1141",
        "vrs_url_a": VRS_BASE_URL + "live/2026/details/2026_10_05/0073--eternal_fire--calyx-imoRR-lugseN-maRky-xfl0ud.md",
        "vrs_rank_b": "",
        "vrs_pts_b": "",
        "vrs_url_b": "",
        "hltv_rank_a": "88",
        "hltv_pts_a": "28",
        "hltv_rank_b": "",
        "hltv_pts_b": "",
        "hltv_match_id": "",
        "hltv_url": "https://www.hltv.org/events/8983/european-pro-league-series-8",
        "book_source": "",
        "book_odds_a": "",
        "book_odds_b": "",
        "book_url": "",
        "pinnacle_odds_a": "",
        "pinnacle_odds_b": "",
        "pinnacle_url": "",
        "crowd_pct_a": "79",
        "crowd_pct_b": "21",
        "flag_code": "FLG-04",
        "flag_note": "PHANTOM FIXTURE (SA-04): European Pro League Series 8 ran Sep 28 - Oct 11 2026 on HLTV without Eternal Fire or Rebels, and Rebels disbanded in 2025. All bookmaker odds, originated probabilities, and pick cells are left strictly BLANK.",
    },
]

# ---------------------------------------------------------------------------
# Reconciliation and publication layer
# ---------------------------------------------------------------------------
from datetime import datetime, timezone
import re

OLD_ORDER = [
    "1079620", "1081076", "1079546", "1079621", "1080176", "1079438", "1079439",
    "1079622", "1080177", "1080178", "1079623", "1080179", "1079624", "1080279",
    "1079440", "1079442", "1080280", "1080281", "1080282", "1080283", "1080284",
    "1080285", "1080286", "1080287", "1080288", "1080289", "1080290",
]
OLD_CODES = {match_id: f"H-{index:02d}" for index, match_id in enumerate(OLD_ORDER)}
NEW_CODES = {
    ("sukeban", "your end"): "H-27",
    ("enjoy", "b8 academy"): "H-28",
    ("banda chuya", "6666"): "H-29",
    ("ryvex", "pcific"): "H-30",
    ("mellren", "privateer"): "H-31",
}

# This is a new, timestamped market read. It is deliberately separate from the
# old static odds snapshots in model/data/lines.csv, which are retained as model
# inputs only. A blank entry means no eligible two-way pre-match price was confirmed.
CURRENT_ODDS: Dict[str, Tuple[str, str]] = {
    "1079546": ("2.46", "1.51"),       # Zomblers / Overtake Sector
    "1079621": ("1.881", "1.782"),     # Gothic / Lavked
    "1080176": ("3.86", "1.21"),       # 9z / Aurora
    "1079438": ("1.09", "6.38"),       # Astralis / Sashi
    "1079439": ("1.89", "1.81"),       # HOTU / fnatic
    "1079622": ("1.40", "2.68"),       # ex-RUSTEC / mellren
    "1080177": ("1.23", "3.81"),       # Falcons / NiP
    "1080178": ("1.68", "2.10"),       # Legacy / PARIVISION
    "1079623": ("1.465", "2.436"),     # G2 Ares / The Last Resort
    "1080179": ("1.40", "2.81"),       # FURIA / BetBoom Team
    "1079440": ("1.69", "2.06"),       # MIBR / BC.Game
    "1079442": ("1.45", "2.47"),       # HEROIC / Envy
    "1080280": ("1.28", "3.22"),       # ENCE / BOJONG
    "1080281": ("1.62", "2.107"),      # WBT / ENCE
    "1080282": ("1.19", "4.02"),       # EAC / BOJONG
    "1080283": ("1.21", "3.99"),       # WBT / BOJONG
    "1080284": ("1.51", "2.35"),       # EAC / ENCE
    "1080285": ("1.87", "1.77"),       # Voca / Phantom
    "1080286": ("1.21", "3.96"),       # HAVU / Rounds
    "1080287": ("1.38", "2.70"),       # Voca / HAVU
    "1080288": ("1.05", "7.11"),       # Phantom / Rounds
    "1080289": ("6.40", "1.063"),      # Rounds / Voca; source lists Voca first
    "1080290": ("1.37", "2.91"),       # Phantom / HAVU
    # 1079624 is a displayed 1.80/1.80 placeholder; all started rows and
    # new rows without a confirmed pre-match pair remain blank.
}

# Direct EGW links captured from the current listing where available. When a
# direct link was not read for a fixture, the generated row links the official
# EGW listing and leaves the price blank rather than guessing a match URL.
CURRENT_EGW_URLS: Dict[str, str] = {
    "1079546": "https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_",
    "1079621": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
    "1080176": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb",
    "1079438": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z",
    "1079439": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC",
    "1079622": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
    "1080177": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/falcons-vs-nip-QSa-aeOIR",
    "1080178": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/legacy-vs-parivision--TTc59QUDJ",
    "1079623": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
    "1080179": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH",
    "1079440": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX",
    "1079442": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC",
    "1080280": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg",
    "1080281": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS",
    "1080282": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5",
    "1080283": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6",
    "1080284": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT",
    "1080285": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja",
    "1080286": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
    "1080287": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP",
    "1080288": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU",
    "1080289": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U",
    "1080290": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586",
}

# New lobby-only cards were validated against these official HLTV records. The
# Hotspawn card did not expose a match ID, so the Hotspawn source remains the
# official lobby rather than an invented match URL.
NEW_KEYS = set(NEW_CODES)
NEW_ODDS: Dict[str, Tuple[str, str]] = {
    "H-28": ("1.52", "2.30"),  # Enjoy / B8 Academy
}
NEW_EGW_URLS: Dict[str, str] = {
    "H-27": "https://egamersworld.com/counterstrike/matches",
    "H-28": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7",
    "H-29": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y",
    "H-30": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3",
    "H-31": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/mellren-vs-privateer-gaming-ASh_MyDBS",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def raw_pair_index() -> Dict[Tuple[str, str], Dict[str, str]]:
    return {
        ((r.get("team_a", "").strip().lower()), (r.get("team_b", "").strip().lower())): r
        for r in OCTOBER_32_RAW
    }


def pct_string(value: Optional[float]) -> str:
    return "" if value is None else f"{value * 100:.1f}"


def probability_from_text(value: str) -> Optional[float]:
    try:
        return float(value) / 100.0 if value else None
    except (TypeError, ValueError):
        return None


def current_status(start_utc: str, match_id: str) -> Tuple[str, str]:
    """Return (status, actionable) for the fixed capture timestamp."""
    if match_id == "1079620":
        return "completed_not_actionable", "no"
    if match_id == "1081076":
        return "live_not_actionable", "no"
    try:
        start = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
        captured = datetime.fromisoformat(CAPTURED_UTC.replace("Z", "+00:00"))
        if start <= captured:
            return "started_not_actionable", "no"
    except ValueError:
        return "unverified_time", "no"
    return "open_prelock", "yes"


def base_row(code: str, *, match_id: str, team_a: str, team_b: str, tournament: str, tier: str,
             points: str, fmt: str, start_utc: str, lock_utc: str, hotspawn_url: str,
             hltv_url: str, hltv_match_id: str, vrs_rank_a: str, vrs_pts_a: str,
             vrs_url_a: str, vrs_rank_b: str, vrs_pts_b: str, vrs_url_b: str,
             hltv_rank_a: str, hltv_pts_a: str, hltv_url_a: str, hltv_rank_b: str,
             hltv_pts_b: str, hltv_url_b: str, source_type: str, book_url: str,
             book_odds_a: str, book_odds_b: str, note: str, flag_code: str,
             lobby_visibility: str = "") -> Dict[str, Any]:
    status, actionable = current_status(start_utc, match_id) if match_id else ("open_prelock", "yes")
    return {
        "code": code,
        "hotspawn_id": match_id,
        "hotspawn_url": hotspawn_url or HOTSPAWN_LOBBY_URL,
        "lobby_visibility": lobby_visibility,
        "match_status": status,
        "actionable": actionable,
        "status_note": note,
        "tier": tier,
        "points": points,
        "format": fmt,
        "tournament": tournament,
        "start_utc": start_utc,
        "lock_utc": lock_utc,
        "team_a": team_a,
        "team_b": team_b,
        "vrs_rank_a": vrs_rank_a,
        "vrs_pts_a": vrs_pts_a,
        "vrs_url_a": vrs_url_a,
        "vrs_rank_b": vrs_rank_b,
        "vrs_pts_b": vrs_pts_b,
        "vrs_url_b": vrs_url_b,
        "hltv_rank_a": hltv_rank_a,
        "hltv_pts_a": hltv_pts_a,
        "hltv_url_a": hltv_url_a,
        "hltv_rank_b": hltv_rank_b,
        "hltv_pts_b": hltv_pts_b,
        "hltv_url_b": hltv_url_b,
        "hltv_match_id": hltv_match_id,
        "hltv_url": hltv_url,
        "book_source": source_type,
        "book_url": book_url,
        "book_odds_a": book_odds_a,
        "book_odds_b": book_odds_b,
        "book_captured_utc": CAPTURED_UTC if book_odds_a and book_odds_b else "",
        "market_p_a": "",
        "market_p_b": "",
        "market_vig_pct": "",
        "own_p_a": "",
        "own_p_b": "",
        "own_fair_a": "",
        "own_fair_b": "",
        "pick": "",
        "pick_probability": "",
        "pick_source": "",
        "verification": "",
        "flag_code": flag_code,
        "flag_note": note,
        "notes": note,
        "is_stale": "no",
    }


def augment_market_and_pick(row: Dict[str, Any], *, own_p_a: Optional[float] = None,
                            own_p_b: Optional[float] = None, raw_flag: str = "",
                            raw_note: str = "") -> None:
    """Apply strict market/model arithmetic and the actionable pick policy."""
    if raw_flag and raw_flag not in row["flag_code"]:
        row["flag_code"] = ",".join(x for x in (row["flag_code"], raw_flag) if x)
    if raw_note:
        row["notes"] = "; ".join(x for x in (row["notes"], raw_note) if x)
        row["flag_note"] = row["notes"]
    pa, pb, vig = devig_decimal(row["book_odds_a"], row["book_odds_b"])
    if pa is not None and row["actionable"] == "yes":
        row["market_p_a"] = pct_string(pa)
        row["market_p_b"] = pct_string(pb)
        row["market_vig_pct"] = f"{vig:.2f}"
    else:
        # Started/live/completed or placeholder odds are never published as
        # actionable market probabilities.
        if pa is not None and row["actionable"] != "yes":
            row["notes"] = "; ".join(x for x in (row["notes"], "price observed after lock/start; suppressed") if x)
        row["book_odds_a"] = "" if row["actionable"] != "yes" else row["book_odds_a"]
        row["book_odds_b"] = "" if row["actionable"] != "yes" else row["book_odds_b"]
        row["book_captured_utc"] = "" if row["actionable"] != "yes" else row["book_captured_utc"]
    if own_p_a is not None and own_p_b is not None:
        row["own_p_a"] = pct_string(own_p_a)
        row["own_p_b"] = pct_string(own_p_b)
        row["own_fair_a"] = f"{1.0 / own_p_a:.2f}"
        row["own_fair_b"] = f"{1.0 / own_p_b:.2f}"
    if row["actionable"] == "yes":
        market_a = probability_from_text(row["market_p_a"])
        model_a = probability_from_text(row["own_p_a"])
        if market_a is not None:
            pick_a = market_a >= 0.5
            row["pick"] = row["team_a"] if pick_a else row["team_b"]
            row["pick_probability"] = f"{(market_a if pick_a else 1.0 - market_a) * 100:.1f}"
            row["pick_source"] = "external market, de-vigged"
        elif model_a is not None:
            pick_a = model_a >= 0.5
            row["pick"] = row["team_a"] if pick_a else row["team_b"]
            row["pick_probability"] = f"{(model_a if pick_a else 1.0 - model_a) * 100:.1f}"
            row["pick_source"] = "our VRS model (market unavailable)"
        else:
            row["pick"] = ""
            row["pick_probability"] = ""
            row["pick_source"] = ""
    else:
        row["pick"] = ""
        row["pick_probability"] = ""
        row["pick_source"] = ""
    if row["actionable"] == "yes" and not row["market_p_a"]:
        if "placeholder" in row["notes"].lower() or row["book_url"]:
            row["verification"] = "unverified — no eligible two-way line"
            if "NO-MARKET" not in row["flag_code"]:
                row["flag_code"] = ",".join(x for x in (row["flag_code"], "NO-MARKET") if x)
        else:
            row["verification"] = "unverified — no market captured"
    elif row["actionable"] == "yes":
        row["verification"] = "market observed at capture"
    else:
        row["verification"] = "not actionable at capture"
    # Differences are review metadata only. They never override the market pick.
    if row["market_p_a"] and row["own_p_a"]:
        edge = abs(float(row["market_p_a"]) - float(row["own_p_a"]))
        if edge >= 12.5:
            row["flag_code"] = ",".join(x for x in (row["flag_code"], "MODEL-MARKET") if x)
            row["notes"] = "; ".join(x for x in (row["notes"], f"market/model gap {edge:.1f} pp") if x)
            row["flag_note"] = row["notes"]


def model_lookup() -> Dict[str, Dict[str, str]]:
    return {r["hotspawn_match_id"]: r for r in read_csv(MODEL_LINES_CSV)}


def make_old_rows() -> List[Dict[str, Any]]:
    model = model_lookup()
    raw = raw_pair_index()
    state_by_id = {r["hotspawn_id"]: r for r in read_csv(NG_STATE_86_CSV)}
    verified_by_id = {r["hotspawn_id"]: r for r in read_csv(ROOT / "data" / "6d9c321d" / "matches_verified.csv")}
    rows: List[Dict[str, Any]] = []
    for match_id in OLD_ORDER:
        m = model[match_id]
        pair = (m["team_a"].strip().lower(), m["team_b"].strip().lower())
        rr = raw.get(pair, {})
        fmt = "BO1" if match_id in {"1080279", "1080280", "1080281", "1080282", "1080283", "1080284", "1080285", "1080286", "1080287", "1080288", "1080289", "1080290"} else "BO3"
        state = state_by_id.get(match_id, {})
        verified = verified_by_id.get(match_id, {})
        # use direct row-level URL from the new capture where it was read;
        # otherwise retain the official EGW listing URL. Never invent a match URL.
        book_url = CURRENT_EGW_URLS.get(match_id, rr.get("book_url", "") or m.get("market_source_url", "") or EGW_MATCHES_URL)
        odds_a, odds_b = CURRENT_ODDS.get(match_id, ("", ""))
        note_extra = "EGW displayed 1.80/1.80 default placeholder; price left blank." if match_id == "1079624" else ""
        hltv_url = verified.get("hltv_url", "") or rr.get("hltv_url", "")
        hltv_match_id = ""
        match_parts = re.search(r"/matches/(\d+)/", hltv_url)
        if match_parts:
            hltv_match_id = match_parts.group(1)
        points = state.get("points", "") or rr.get("points", "")
        start_raw = m["scheduled_start_utc"]
        lock_raw = m["lock_utc"]
        start_iso = start_raw.replace(" ", "T") + ":00Z" if len(start_raw) == 16 else start_raw
        lock_iso = lock_raw.replace(" ", "T") + ":00Z" if len(lock_raw) == 16 else lock_raw
        row = base_row(
            OLD_CODES[match_id], match_id=match_id, team_a=m["team_a"], team_b=m["team_b"],
            tournament=m["competition"], tier=m["tier"], points=points,
            fmt=fmt, start_utc=start_iso, lock_utc=lock_iso,
            hotspawn_url=m["hotspawn_url"], hltv_url=hltv_url,
            hltv_match_id=hltv_match_id,
            vrs_rank_a=m.get("vrs_a_standing", ""), vrs_pts_a=m.get("vrs_a_points", ""), vrs_url_a=m.get("vrs_a_url", ""),
            vrs_rank_b=m.get("vrs_b_standing", ""), vrs_pts_b=m.get("vrs_b_points", ""), vrs_url_b=m.get("vrs_b_url", ""),
            hltv_rank_a=m.get("hltv_a_rank", ""), hltv_pts_a="", hltv_url_a=m.get("hltv_a_url", ""),
            hltv_rank_b=m.get("hltv_b_rank", ""), hltv_pts_b="", hltv_url_b=m.get("hltv_b_url", ""),
            source_type="EGamersWorld / BC.Game" if odds_a else ("EGamersWorld checked — placeholder/none" if book_url else ""),
            book_url=book_url, book_odds_a=odds_a, book_odds_b=odds_b,
            note="; ".join(x for x in (m.get("notes", ""), note_extra) if x), flag_code=m.get("flag_id", ""),
            lobby_visibility="SSR_OR_TRANSFERSTATE",
        )
        # The model artifact's probabilities are a read-only official-VRS model
        # reference. Reuse them only as independent model estimates; do not use
        # Hotspawn crowd percentages anywhere.
        own_a = probability_from_text(m.get("own_p_a", ""))
        own_b = probability_from_text(m.get("own_p_b", ""))
        augment_market_and_pick(row, own_p_a=own_a, own_p_b=own_b)
        if match_id in ("1079620", "1081076"):
            row["notes"] = "; ".join(x for x in (row["notes"], "started/live fixture retained for audit only") if x)
            row["flag_code"] = ",".join(x for x in (row["flag_code"], "STATUS") if x)
        rows.append(row)
    return rows


def make_new_rows() -> List[Dict[str, Any]]:
    raw = raw_pair_index()
    rows: List[Dict[str, Any]] = []
    for key, code in NEW_CODES.items():
        rr = raw[key]
        odds_a, odds_b = NEW_ODDS.get(code, ("", ""))
        row = base_row(
            code, match_id="", team_a=rr["team_a"], team_b=rr["team_b"], tournament=rr["tournament"], tier=rr["tier"],
            points=rr["points"], fmt=rr["format"], start_utc=rr["start_utc"], lock_utc=rr["lock_utc"],
            hotspawn_url=HOTSPAWN_LOBBY_URL, hltv_url=rr["hltv_url"], hltv_match_id=rr["hltv_match_id"],
            vrs_rank_a=rr.get("vrs_rank_a", ""), vrs_pts_a=rr.get("vrs_pts_a", ""), vrs_url_a=rr.get("vrs_url_a", ""),
            vrs_rank_b=rr.get("vrs_rank_b", ""), vrs_pts_b=rr.get("vrs_pts_b", ""), vrs_url_b=rr.get("vrs_url_b", ""),
            hltv_rank_a=rr.get("hltv_rank_a", ""), hltv_pts_a=rr.get("hltv_pts_a", ""), hltv_url_a="",
            hltv_rank_b=rr.get("hltv_rank_b", ""), hltv_pts_b=rr.get("hltv_pts_b", ""), hltv_url_b="",
            source_type="EGamersWorld / BC.Game" if odds_a else "EGamersWorld checked — placeholder/none",
            book_url=NEW_EGW_URLS[code], book_odds_a=odds_a, book_odds_b=odds_b,
            note=rr.get("flag_note", ""), flag_code=rr.get("flag_code", ""), lobby_visibility=rr.get("lobby_visibility", "LOBBY_ONLY"),
        )
        pa, pb = vrs_logistic_prob(row["vrs_pts_a"], row["vrs_pts_b"], row["format"])
        augment_market_and_pick(row, own_p_a=pa, own_p_b=pb, raw_flag=rr.get("flag_code", ""), raw_note=rr.get("flag_note", ""))
        # A new card without a Hotspawn ID is not falsely given a match URL.
        row["notes"] = "; ".join(x for x in (row["notes"], "Hotspawn card had no match ID in the fetched lobby") if x)
        rows.append(row)
    return rows


def make_stale_rows() -> List[Dict[str, Any]]:
    model = model_lookup()
    inv = read_csv(NG_STATE_86_CSV)
    out: List[Dict[str, Any]] = []
    for state in inv:
        start = state["utc_start"]
        if not start.startswith("2026-06") and not start.startswith("2026-07"):
            continue
        match_id = state["hotspawn_id"]
        m = model.get(match_id, {})
        start_iso = start.replace(" UTC", "").replace(" ", "T") + ":00Z"
        lock = state.get("lock_time_utc", "").replace(" UTC", "").replace(" ", "T") + ":00Z"
        row = base_row(
            f"S-{int(state['seq_num']):03d}", match_id=match_id, team_a=state["team1"], team_b=state["team2"],
            tournament=state["tournament"], tier=state["tier"], points=state["points"], fmt=m.get("best_of", "") or "",
            start_utc=start_iso, lock_utc=lock, hotspawn_url=m.get("hotspawn_url", HOTSPAWN_CS2_URL),
            hltv_url="", hltv_match_id="", vrs_rank_a=m.get("vrs_a_standing", ""), vrs_pts_a=m.get("vrs_a_points", ""),
            vrs_url_a=m.get("vrs_a_url", ""), vrs_rank_b=m.get("vrs_b_standing", ""), vrs_pts_b=m.get("vrs_b_points", ""),
            vrs_url_b=m.get("vrs_b_url", ""), hltv_rank_a=m.get("hltv_a_rank", ""), hltv_pts_a="", hltv_url_a=m.get("hltv_a_url", ""),
            hltv_rank_b=m.get("hltv_b_rank", ""), hltv_pts_b="", hltv_url_b=m.get("hltv_b_url", ""),
            source_type="", book_url="", book_odds_a="", book_odds_b="",
            note="stale TransferState listing; start/lock predates the current 2026-10-12 pick'em week",
            flag_code="STALE",
            lobby_visibility="TRANSFERSTATE_ONLY",
        )
        row["is_stale"] = "yes"
        row["actionable"] = "no"
        row["match_status"] = "stale_not_actionable"
        own_a = probability_from_text(m.get("own_p_a", ""))
        own_b = probability_from_text(m.get("own_p_b", ""))
        augment_market_and_pick(row, own_p_a=own_a, own_p_b=own_b)
        row["pick"] = ""
        row["pick_probability"] = ""
        row["pick_source"] = ""
        row["verification"] = "stale — not actionable"
        out.append(row)
    return out


def add_source_links(row: Dict[str, Any]) -> None:
    links: List[Tuple[str, str]] = [("Hotspawn identity", row["hotspawn_url"])]
    if row.get("hltv_url"):
        links.append(("HLTV match", row["hltv_url"]))
    if row.get("vrs_url_a"):
        links.append(("Valve VRS A", row["vrs_url_a"]))
    if row.get("vrs_url_b"):
        links.append(("Valve VRS B", row["vrs_url_b"]))
    if row.get("hltv_url_a"):
        links.append(("HLTV team A", row["hltv_url_a"]))
    if row.get("hltv_url_b"):
        links.append(("HLTV team B", row["hltv_url_b"]))
    if row.get("book_url"):
        links.append(("EGW / book check", row["book_url"]))
    row["source_links"] = links


def build_rows() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    current = make_old_rows() + make_new_rows()
    # Sort by scheduled kickoff; retain a stable code tie-breaker.
    current.sort(key=lambda r: (r["start_utc"], r["code"]))
    stale = make_stale_rows()
    for r in current + stale:
        add_source_links(r)
    return current, stale


CSV_FIELDS = [
    "code", "hotspawn_id", "match_status", "actionable", "is_stale", "lobby_visibility", "status_note",
    "start_utc", "lock_utc", "tournament", "tier", "points", "format", "team_a", "team_b",
    "vrs_rank_a", "vrs_pts_a", "vrs_url_a", "vrs_rank_b", "vrs_pts_b", "vrs_url_b",
    "hltv_rank_a", "hltv_url_a", "hltv_rank_b", "hltv_url_b", "hltv_match_id", "hltv_url",
    "book_source", "book_odds_a", "book_odds_b", "book_captured_utc", "book_url",
    "market_p_a", "market_p_b", "market_vig_pct", "own_p_a", "own_p_b", "own_fair_a", "own_fair_b",
    "pick", "pick_probability", "pick_source", "verification", "flag_code", "flag_note", "notes",
]


def make_flags(rows: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    flags: List[Dict[str, str]] = []
    for row in rows:
        if row["flag_code"]:
            flags.append({
                "flag_id": row["flag_code"],
                "severity": "review" if row["actionable"] == "yes" else "info/review",
                "subject": f"{row['code']} — {row['team_a']} vs {row['team_b']}",
                "detail": row["notes"] or row["verification"],
                "source_links": json.dumps(row.get("source_links", []), ensure_ascii=False),
            })
        if row["actionable"] == "yes" and not row["market_p_a"]:
            flags.append({
                "flag_id": f"NO-MARKET-{row['code']}",
                "severity": "unverified",
                "subject": f"{row['code']} — no confirmed external two-way line",
                "detail": "Probability from bookmaker odds is blank. The row is not filled from Hotspawn crowd picks or tournament outrights.",
                "source_links": json.dumps(row.get("source_links", []), ensure_ascii=False),
            })
    flags.extend([
        {"flag_id": "GLOBAL-01", "severity": "review", "subject": "Hotspawn counts are inconsistent", "detail": "The live lobby reported 90 CS2 filter fixtures, the CS2 page reported 85, the header reported 68 matches this week, and the TransferState inventory contains 91 CS2 records after the five new lobby-only rows were added. This dashboard uses the dated records and publishes the mismatch instead of guessing a hidden set.", "source_links": json.dumps([["Hotspawn lobby", HOTSPAWN_LOBBY_URL], ["Hotspawn CS2", HOTSPAWN_CS2_URL]])},
        {"flag_id": "GLOBAL-02", "severity": "review", "subject": "Current snapshot includes lobby-only cards", "detail": "Five rows were visible on /lobby but absent from /cs2-pickems and had no Hotspawn match ID. They are included only with the official lobby link and a matching HLTV record; no match URL was invented.", "source_links": json.dumps([["Hotspawn lobby", HOTSPAWN_LOBBY_URL], ["HLTV matches", "https://www.hltv.org/matches"]])},
        {"flag_id": "GLOBAL-03", "severity": "info", "subject": "Hotspawn crowd percentages excluded", "detail": "The published dataset does not expose crowd percentages and no crowd value is used by the market or VRS model. Only the external odds and the independent VRS calculation produce probability values.", "source_links": json.dumps([["Hotspawn lobby", HOTSPAWN_LOBBY_URL], ["Valve VRS", VRS_STANDINGS_URL]])},
        {"flag_id": "GLOBAL-04", "severity": "review", "subject": "Odds move and capture scope", "detail": f"External odds shown as verified were read from EGamersWorld/BC.Game's public listing at the capture window {CAPTURED_UTC}. The site is mutable; rows retain source URLs and timestamp, and rows without a confirmed pair stay blank.", "source_links": json.dumps([["EGamersWorld CS2 matches", EGW_MATCHES_URL], ["Pinnacle esports highlights", PINNACLE_HIGHLIGHTS_URL]])},
        {"flag_id": "GLOBAL-05", "severity": "review", "subject": "Stale TransferState listings", "detail": "59 CS2 rows in the official TransferState have start dates in June/July 2026 and remain status=scheduled. They are retained in All matches for audit completeness, greyed out, and never presented as actionable picks.", "source_links": json.dumps([["Hotspawn CS2 Pick'em", HOTSPAWN_CS2_URL], ["Valve VRS", VRS_STANDINGS_URL]])},
    ])
    return flags


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str] = CSV_FIELDS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def link_list(row: Dict[str, Any]) -> str:
    return " · ".join(f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>' for label, url in row.get("source_links", []) if url)


def prob_block(row: Dict[str, Any]) -> str:
    pa = row.get("market_p_a") or ""
    pb = row.get("market_p_b") or ""
    oa = row.get("own_p_a") or ""
    ob = row.get("own_p_b") or ""
    market = f"<div><span class=label>Market no-vig</span><strong>{esc(pa or '—')}% / {esc(pb or '—')}%</strong></div>"
    own = f"<div><span class=label>Our VRS model</span><strong>{esc(oa or '—')}% / {esc(ob or '—')}%</strong></div>"
    if pa:
        try:
            width = max(0.0, min(100.0, float(pa)))
        except ValueError:
            width = 0
        bar = f'<div class=bar aria-label="Team A market probability {esc(pa)} percent"><i style="width:{width}%"></i></div>'
    else:
        bar = "<div class=bar empty-bar aria-label=unverified></div>"
    return market + own + bar


def card(row: Dict[str, Any], *, compact: bool = False) -> str:
    status = row["match_status"].replace("_", " ")
    badge_class = "good" if row["actionable"] == "yes" and row["market_p_a"] else ("muted" if row["actionable"] != "yes" else "warn")
    pick = row["pick"] or "No pick — value unverified"
    if row["actionable"] != "yes":
        pick = "Not actionable at capture"
    note = row["notes"] or row["verification"]
    stale_class = " stale" if row.get("is_stale") == "yes" else ""
    return f'''<article class="match-card{stale_class}">
      <div class="card-top"><span class="code">{esc(row["code"])}</span><span class="badge {badge_class}">{esc(status)}</span><span class="tier">Tier {esc(row["tier"])} · {esc(row["format"] or "format unverified")}</span></div>
      <h3>{esc(row["team_a"])} <span>vs</span> {esc(row["team_b"])}</h3>
      <p class="event">{esc(row["tournament"])} · {esc(row["start_utc"])} <small>lock {esc(row["lock_utc"])}</small></p>
      <div class="probabilities">{prob_block(row)}</div>
      <div class="pick"><span>Pick</span><strong>{esc(pick)}</strong>{f'<small>{esc(row["pick_probability"])}% · {esc(row["pick_source"])}</small>' if row["pick_probability"] else ''}</div>
      <p class="note">{esc(note)}</p>
      <p class="sources">{link_list(row)}</p>
    </article>'''


def table_rows(rows: List[Dict[str, Any]]) -> str:
    return "\n".join(card(r) for r in rows)


def page_shell(title: str, active: str, body: str) -> str:
    nav = "".join(f'<a class="{"active" if key == active else ""}" href="{href}">{label}</a>' for key, href, label in [
        ("index", "index.html", "Overview"), ("all", "all-matches.html", "All matches"),
        ("s", "s-tier.html", "S tier"), ("b", "b-tier.html", "B tier"), ("c", "c-tier.html", "C tier"),
        ("flags", "flagged.html", "Flagged for Review"), ("sources", "sources.html", "Sources"),
        ("method", "methodology.html", "Methodology"),
    ])
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Source-linked Hotspawn CS2 Pick'em probabilities; blank where unverified."><title>{esc(title)} · MaltaProj1</title><link rel="stylesheet" href="style.css"></head><body><header><div class="brand"><span class="logo">HS</span><div><strong>Hotspawn Pick'em evidence</strong><small>Independent lines · mobile first · analysis only</small></div></div><nav>{nav}</nav></header><main>{body}</main><footer>Capture {CAPTURED_UTC}. Hotspawn identifies fixtures only; crowd picks are never used as probability. Blank = unverified. Analysis only — not betting advice.</footer></body></html>'''


def write_site(current: List[Dict[str, Any]], stale: List[Dict[str, Any]], flags: List[Dict[str, str]]) -> None:
    MOBILE_OUT.mkdir(parents=True, exist_ok=True)
    (MOBILE_OUT / "style.css").write_text('''
:root{--bg:#0b1020;--panel:#121a2d;--panel2:#18233c;--line:#293858;--text:#eef4ff;--muted:#9fb0ce;--blue:#66a3ff;--green:#42d392;--amber:#ffca62;--red:#ff7485}*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#090e1b,#111a31 65%,#0b1020);color:var(--text);font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}header{position:sticky;top:0;z-index:5;background:rgba(11,16,32,.96);backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:13px max(16px,calc((100% - 1180px)/2))}.brand{display:flex;gap:10px;align-items:center}.logo{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:linear-gradient(135deg,#377dff,#8d5cff);font-weight:800}.brand strong{display:block;font-size:16px}.brand small{display:block;color:var(--muted);font-size:11px}nav{display:flex;gap:6px;overflow:auto;padding-top:12px;scrollbar-width:none}nav a{white-space:nowrap;padding:7px 10px;border:1px solid transparent;border-radius:8px;color:var(--muted);font-size:13px}nav a.active,nav a:hover{color:var(--text);background:var(--panel2);border-color:var(--line);text-decoration:none}main{max-width:1180px;margin:auto;padding:24px 16px 48px}h1{font-size:clamp(25px,5vw,42px);line-height:1.08;margin:0 0 10px}h2{margin:28px 0 12px;font-size:22px}h3{font-size:18px;margin:10px 0 4px}.lead{color:var(--muted);max-width:800px}.hero{display:grid;grid-template-columns:1.6fr 1fr;gap:20px;align-items:end}.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:22px 0}.metric,.panel,.match-card,.flag{background:linear-gradient(180deg,rgba(24,35,60,.96),rgba(18,26,45,.96));border:1px solid var(--line);border-radius:14px;padding:14px}.metric strong{font-size:27px;display:block;color:var(--blue)}.metric span{color:var(--muted);font-size:12px}.notice{border-left:3px solid var(--amber);background:rgba(255,202,98,.08);padding:11px 14px;border-radius:8px;color:var(--muted);margin:16px 0}.filters{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.filters input,.filters select{background:var(--panel);color:var(--text);border:1px solid var(--line);padding:9px;border-radius:8px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.match-card{min-width:0}.match-card.stale{opacity:.62}.card-top{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.code{font-weight:800;color:var(--blue)}.tier{color:var(--muted);font-size:12px;margin-left:auto}.badge{border-radius:999px;padding:3px 8px;font-size:11px;text-transform:capitalize;border:1px solid var(--line)}.badge.good{color:var(--green);background:rgba(66,211,146,.1)}.badge.warn{color:var(--amber);background:rgba(255,202,98,.1)}.badge.muted{color:var(--muted)}.match-card h3 span{font-weight:400;color:var(--muted);font-size:13px}.event{color:var(--muted);font-size:12px;margin:0 0 10px}.event small{display:block;color:#8091b2}.probabilities{background:#0d1527;border-radius:10px;padding:9px;margin:8px 0}.probabilities>div{display:flex;justify-content:space-between;gap:8px;align-items:baseline}.probabilities strong{font-variant-numeric:tabular-nums}.label{color:var(--muted);font-size:12px}.bar{height:7px;background:#263653;border-radius:99px;overflow:hidden;margin-top:7px}.bar i{display:block;height:100%;background:linear-gradient(90deg,#418aff,#57d7ca);border-radius:99px}.empty-bar{opacity:.35}.pick{display:flex;align-items:baseline;gap:8px;padding:9px 0;border-bottom:1px solid var(--line)}.pick span{font-size:12px;color:var(--muted)}.pick strong{color:var(--green)}.pick small{color:var(--muted);margin-left:auto;text-align:right}.note{color:var(--muted);font-size:12px;min-height:18px}.sources{font-size:12px;line-height:1.8;margin:0}.sources a{margin-right:5px}.flag{margin:10px 0}.flag h3{font-size:16px}.flag p{color:var(--muted);margin:5px 0}.flag .sources{margin-top:8px}.small{font-size:12px;color:var(--muted)}footer{border-top:1px solid var(--line);color:var(--muted);font-size:12px;padding:18px 16px;text-align:center}.table-wrap{overflow:auto}.simple-table{width:100%;border-collapse:collapse;min-width:700px}.simple-table th,.simple-table td{padding:9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}.simple-table th{color:var(--muted);font-size:12px}.top-picks{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}.top-picks .match-card{padding:12px}@media(max-width:760px){header{position:relative}.hero{display:block}.metrics{grid-template-columns:repeat(2,1fr)}.grid,.top-picks{grid-template-columns:1fr}main{padding:18px 12px 38px}.tier{margin-left:0}.pick{align-items:flex-start;flex-wrap:wrap}.pick small{width:100%;margin-left:0;text-align:left}.match-card h3{font-size:17px}}
''', encoding="utf-8")
    actionable = [r for r in current if r["actionable"] == "yes"]
    market = [r for r in actionable if r["market_p_a"]]
    own = [r for r in actionable if r["own_p_a"]]
    future = [r for r in actionable if r["start_utc"] >= CAPTURED_UTC]
    top = sorted(future, key=lambda r: float(r["pick_probability"] or 0), reverse=True)[:6]
    body = f'''<section class="hero"><div><p class="small">CAPTURED {CAPTURED_UTC}</p><h1>Current Pick'em lines, without the guesswork.</h1><p class="lead">Every current CS2 fixture read from Hotspawn's public board and cross-checked against official HLTV match records, Valve's Regional Standings, and external market pages. Market probabilities are de-vigged bookmaker prices; model probabilities are independently calculated from Valve VRS points. Hotspawn crowd percentages are deliberately excluded.</p></div><div class="panel"><strong>Read this first</strong><p class="small">A blank value is intentional. It means no eligible external line or no unambiguous official rating was confirmed. Started, completed, and stale rows remain visible for audit but are not actionable.</p><a href="flagged.html">Review all flags →</a></div></section><section class="metrics"><div class="metric"><strong>{len(current)}</strong><span>current CS2 records</span></div><div class="metric"><strong>{len(actionable)}</strong><span>open before lock</span></div><div class="metric"><strong>{len(market)}</strong><span>external market lines</span></div><div class="metric"><strong>{len(stale)}</strong><span>stale rows retained</span></div></section><section class="panel"><h2>Next picks</h2><p class="small">Open rows only. Pick is the external-market favorite when a verified two-way price exists; otherwise it is the VRS model favorite and is labeled.</p><div class="top-picks">{table_rows(top)}</div><p><a href="all-matches.html">See all {len(current)+len(stale)} CS2 records →</a></p></section><section class="panel"><h2>Browse by tier</h2><div class="grid"><a class="metric" href="s-tier.html"><strong>{sum(r["tier"] == "S" for r in current)}</strong><span>S tier · Thunderpick World Championship</span></a><a class="metric" href="b-tier.html"><strong>{sum(r["tier"] == "B" for r in current)}</strong><span>B tier · league and CCT fixtures</span></a><a class="metric" href="c-tier.html"><strong>{sum(r["tier"] == "C" for r in current)}</strong><span>C tier · lower tier and Elisa</span></a><a class="metric" href="flagged.html"><strong>{len(flags)}</strong><span>Flagged for Review</span></a></div></section>'''
    (MOBILE_OUT / "index.html").write_text(page_shell("Overview", "index", body), encoding="utf-8")

    all_body = f'''<h1>All CS2 matches</h1><p class="lead">{len(current)} current records plus {len(stale)} stale TransferState records. Use the search box to find a team or tournament. Rows marked not actionable are never presented as current picks.</p><div class="filters"><input id="q" type="search" placeholder="Search team or event" oninput="filterCards()"><select id="status" onchange="filterCards()"><option value="all">All statuses</option><option value="open">Open before lock</option><option value="market">External market</option><option value="blank">Blank/unverified</option><option value="stale">Stale</option></select></div><div id="cards" class="grid">{table_rows(current + stale)}</div><script>function filterCards(){{const q=document.getElementById('q').value.toLowerCase(),s=document.getElementById('status').value;document.querySelectorAll('.match-card').forEach(c=>{{const t=c.textContent.toLowerCase(),stale=c.classList.contains('stale'),market=t.includes('market no-vig')&&!t.includes('market no-vig</span><strong>—'),open=t.includes('open prelock'),show=!q||t.includes(q);let kind=s==='all'||(s==='stale'&&stale)||(s==='open'&&open&&!stale)||(s==='market'&&market&&!stale)||(s==='blank'&&!market&&!stale);c.style.display=show&&kind?'':'none'}})}}</script>'''
    (MOBILE_OUT / "all-matches.html").write_text(page_shell("All CS2 matches", "all", all_body), encoding="utf-8")
    for key, title, tier in [("s", "S tier matches", "S"), ("b", "B tier matches", "B"), ("c", "C tier matches", "C")]:
        tier_rows = [r for r in current if r["tier"] == tier]
        body_t = f'<h1>{esc(title)}</h1><p class="lead">{len(tier_rows)} current rows. Probabilities are calculated from external prices or the independent VRS model; crowd picks are not an input.</p><div class="grid">{table_rows(tier_rows)}</div>'
        (MOBILE_OUT / f"{key}-tier.html").write_text(page_shell(title, key, body_t), encoding="utf-8")
    flag_body = f'<h1>Flagged for Review</h1><p class="lead">These are evidence and provenance issues, not hidden assumptions. They do not block publication. Unknown values stay blank.</p>' + "".join(f'<article class="flag"><div class="card-top"><span class="code">{esc(f["flag_id"])}</span><span class="badge warn">{esc(f["severity"])}</span></div><h3>{esc(f["subject"])}</h3><p>{esc(f["detail"])}</p><p class="sources">{source_json_links(f["source_links"])}</p></article>' for f in flags)
    (MOBILE_OUT / "flagged.html").write_text(page_shell("Flagged for Review", "flags", flag_body), encoding="utf-8")
    sources_body = f'''<h1>Sources & verification</h1><p class="lead">All published rows carry source links. Hotspawn is used for fixture identity and lock/start metadata only. External prices are separate observations from EGamersWorld/BC.Game and are timestamped; HLTV is used for match identity and rank context; Valve is the official source for VRS points.</p><section class="grid"><article class="panel"><h2>Fixture identity</h2><p><a href="{HOTSPAWN_LOBBY_URL}">Hotspawn lobby</a><br><a href="{HOTSPAWN_CS2_URL}">Hotspawn CS2 Pick'em page</a><br>Capture: {CAPTURED_UTC}; transfer-state stale rows retained.</p></article><article class="panel"><h2>External markets</h2><p><a href="{EGW_MATCHES_URL}">EGamersWorld CS2 matches</a><br><a href="{PINNACLE_HIGHLIGHTS_URL}">Pinnacle esports highlights</a><br>Placeholders and post-start prices are not probabilities.</p></article><article class="panel"><h2>Ratings</h2><p><a href="{HLTV_RANKING_URL}">HLTV World Ranking, 12 Oct 2026</a><br><a href="{VRS_STANDINGS_URL}">Valve Regional Standings, 5 Oct 2026</a><br>VRS roster/name ambiguity is flagged.</p></article></section><section class="panel"><h2>Coverage statement</h2><p>CS2 current records: {len(current)}; stale records: {len(stale)}; LoL is not merged into this CS2 dashboard because this task's independent rating and moneyline coverage is CS2-only. The repository retains the separate full LoL inventory at <a href="../pickem/lol.html">pickem/lol.html</a>.</p></section>'''
    (MOBILE_OUT / "sources.html").write_text(page_shell("Sources", "sources", sources_body), encoding="utf-8")
    method_body = f'''<h1>Methodology</h1><section class="panel"><h2>1. Fixture set</h2><p>Rows are read from Hotspawn's public lobby/TransferState identity. At capture, 32 October rows were reconciled (27 carried from the CS2 Pick'em TransferState plus five lobby-only cards) and 59 older summer TransferState rows were retained as stale. No card is fabricated when a match ID is absent.</p><h2>2. Market line</h2><p>For a verified decimal pair <code>oA, oB</code>, implied probabilities are <code>(1/oA)/(1/oA + 1/oB)</code> and <code>(1/oB)/(1/oA + 1/oB)</code>. This removes the two-way overround. A 1.80/1.80 placeholder, a missing pair, or an in-play/started page is not a line and remains blank.</p><h2>3. Our line</h2><p>Our independent CS2 estimate uses the official Valve Regional Standings points snapshot dated 5 October 2026. The reproducible logistic form is <code>P(A)=1/(1+exp(-(pointsA-pointsB)/scale))</code>; BO3 scale = {VRS_SCALE_BO3}, BO1 scale = {VRS_SCALE_BO1}. The model is not Hotspawn's crowd percentage and does not read it.</p><h2>4. Pick rule</h2><p>For an actionable row, use the de-vigged external market favorite first. If no eligible external pair exists, use the VRS model only when both teams have unambiguous points. If neither is confirmed, publish no pick. Completed, live, locked, and stale rows are informational only.</p><h2>5. Reproduce</h2><p><code>python3 scripts/e3315a54_build.py</code> regenerates <code>data/e3315a54/</code> and <code>mobile/</code>. It reads committed official snapshots for ratings and TransferState, and the session's explicit 21:20 UTC market ledger; no user input or credentials are required.</p></section>'''
    (MOBILE_OUT / "methodology.html").write_text(page_shell("Methodology", "method", method_body), encoding="utf-8")


def source_json_links(value: str) -> str:
    try:
        links = json.loads(value)
    except Exception:
        links = []
    out = []
    for item in links:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            out.append(f'<a href="{esc(item[1])}" target="_blank" rel="noopener">{esc(item[0])}</a>')
        elif isinstance(item, dict) and item.get("url"):
            out.append(f'<a href="{esc(item["url"])}" target="_blank" rel="noopener">{esc(item.get("label", "source"))}</a>')
    return " · ".join(out)


def main() -> None:
    current, stale = build_rows()
    flags = make_flags(current + stale)
    DATA_OUT.mkdir(parents=True, exist_ok=True)
    write_csv(DATA_OUT / "current.csv", current)
    write_csv(DATA_OUT / "stale.csv", stale)
    write_csv(DATA_OUT / "flags.csv", flags, ["flag_id", "severity", "subject", "detail", "source_links"])
    payload = {
        "generated_utc": CAPTURED_UTC,
        "coverage": {"current_cs2": len(current), "stale_cs2": len(stale), "total_cs2": len(current) + len(stale), "market_lines": sum(bool(r["market_p_a"]) for r in current), "own_lines": sum(bool(r["own_p_a"]) for r in current)},
        "sources": {"hotspawn": HOTSPAWN_LOBBY_URL, "hlty": HLTV_RANKING_URL, "valve_vrs": VRS_STANDINGS_URL, "egw": EGW_MATCHES_URL, "pinnacle": PINNACLE_HIGHLIGHTS_URL},
        "crowd_percentages_used": False,
        "current": current,
        "stale": stale,
        "flags": flags,
    }
    (DATA_OUT / "snapshot.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_site(current, stale, flags)
    print(json.dumps(payload["coverage"], indent=2))


if __name__ == "__main__":
    main()
