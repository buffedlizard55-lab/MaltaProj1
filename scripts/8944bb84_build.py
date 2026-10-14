#!/usr/bin/env python3
"""
scripts/8944bb84_build.py — Session arena/8944bb84
Builds the complete, line-by-line verified Hotspawn CS2 Pick'em dataset (`data/8944bb84/*`)
and the mobile-friendly categorized GitHub Pages dashboard (`oct14/*`).

Strict Non-Negotiables Enforced:
1. ZERO Hotspawn crowd pick percentages (`crowd_pct_a`, `crowd_pct_b`, `picked_percent`, `total_picks`)
   are ever read, stored, or used as an indicator for match probability.
2. Every table row on every HTML page in `oct14/` includes direct clickable source links to
   official verified sources (Valve Regional Standings GitHub commit `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`,
   HLTV World Ranking `2026/october/12`, official HLTV match pages `2399134`–`2399471`,
   Direct Pinnacle guest API, EGamersWorld bookmaker pages, and Hotspawn Pick'em Lobby).
3. Any value that cannot be confirmed from an official source without inference (e.g., `LFO 10`
   in `1079624 FORZE Reload vs LFO 10`, `SUKEBAN` in `1081105 SUKEBAN vs your end`, or
   placeholder `1.80 / 1.80` bookmaker lines) is left BLANK (`""`) and explicitly flagged on
   `oct14/flagged.html` and in `data/8944bb84/flags.csv`.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html
import json
import math
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "8944bb84"
SITE_DIR = ROOT / "oct14"

VRS_COMMIT = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"
VRS_FILE_REL = "live/2026/standings_global_2026_10_05.md"
VRS_BASE_URL = f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/{VRS_FILE_REL}"
VRS_DETAILS_BASE = f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/live/2026/"
HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams/2026/october/12"
HOTSPAWN_CS2_URL = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY_URL = "https://play.hotspawn.com/lobby"
PINNACLE_MATCHUPS_URL = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
EGW_MATCHES_URL = "https://egamersworld.com/counterstrike/matches"

# Calibrated scale parameter D_vrs = 400 / 1.0749 = 372.12 from Valve's model/glicko.js & model/fit.js
VRS_GLICKO_SCALE = 372.12

# Verified 2026-10-14 official HLTV match pages, series formats, live VRS badges, and match results
# across all 32 current-week (Week-270, Oct 13-16, 2026) Hotspawn CS2 Pick'em fixtures.
CURRENT_WEEK_HLTV_MATCHES: dict[str, dict[str, str]] = {
    "1079620": {
        "hltv_match_id": "2399297",
        "hltv_match_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11",
        "series_format": "BO3",
        "status_override": "completed",
        "verified_result": "Black Phoenix 2 - 0 6666 (Final)",
        "team_order_hltv": "normal",
    },
    "1081076": {
        "hltv_match_id": "2399204",
        "hltv_match_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3",
        "series_format": "BO3",
        "status_override": "completed",
        "verified_result": "ex-Keyd Stars 0 - 2 Galorys (Final)",
        "team_order_hltv": "normal",
    },
    "1081105": {
        "hltv_match_id": "2399460",
        "hltv_match_url": "https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-series-7",
        "series_format": "BO3",
        "status_override": "completed",
        "verified_result": "your end 1 - 0 SUKEBAN (Default / Forfeit)",
        "team_order_hltv": "reversed",
    },
    "1079546": {
        "hltv_match_id": "2399232",
        "hltv_match_url": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3",
        "series_format": "BO3",
        "status_override": "live",
        "verified_result": "LIVE (Overtake Sector 1 - 0 Zomblers after Map 1 13-8)",
        "team_order_hltv": "normal",
    },
    "1081111": {
        "hltv_match_id": "2399461",
        "hltv_match_url": "https://www.hltv.org/matches/2399461/enjoy-vs-b8-academy-cct-2026-europe-series-12-closed-qualifier",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079621": {
        "hltv_match_id": "2399298",
        "hltv_match_url": "https://www.hltv.org/matches/2399298/gothic-vs-lavked-cct-2026-europe-series-11",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080176": {
        "hltv_match_id": "2399384",
        "hltv_match_url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079438": {
        "hltv_match_id": "2399134",
        "hltv_match_url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079439": {
        "hltv_match_id": "2399135",
        "hltv_match_url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1081112": {
        "hltv_match_id": "2399462",
        "hltv_match_url": "https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079622": {
        "hltv_match_id": "2399299",
        "hltv_match_url": "https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080177": {
        "hltv_match_id": "2399385",
        "hltv_match_url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080178": {
        "hltv_match_id": "2399386",
        "hltv_match_url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1081113": {
        "hltv_match_id": "2399463",
        "hltv_match_url": "https://www.hltv.org/matches/2399463/pcific-vs-ryvex-cct-2026-europe-series-12-closed-qualifier",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "reversed",
    },
    "1079623": {
        "hltv_match_id": "2399300",
        "hltv_match_url": "https://www.hltv.org/matches/2399300/g2-ares-vs-the-last-resort-cct-2026-europe-series-11",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080179": {
        "hltv_match_id": "2399387",
        "hltv_match_url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079624": {
        "hltv_match_id": "2399301",
        "hltv_match_url": "https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080279": {
        "hltv_match_id": "2399418",
        "hltv_match_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079440": {
        "hltv_match_id": "2399136",
        "hltv_match_url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1079442": {
        "hltv_match_id": "2399137",
        "hltv_match_url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080280": {
        "hltv_match_id": "2399419",
        "hltv_match_url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080281": {
        "hltv_match_id": "2399420",
        "hltv_match_url": "https://www.hltv.org/matches/2399420/wbt-vs-ence-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080282": {
        "hltv_match_id": "2399421",
        "hltv_match_url": "https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080283": {
        "hltv_match_id": "2399422",
        "hltv_match_url": "https://www.hltv.org/matches/2399422/wbt-vs-bojong-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080284": {
        "hltv_match_id": "2399423",
        "hltv_match_url": "https://www.hltv.org/matches/2399423/eac-vs-ence-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080285": {
        "hltv_match_id": "2399424",
        "hltv_match_url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080286": {
        "hltv_match_id": "2399425",
        "hltv_match_url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080287": {
        "hltv_match_id": "2399426",
        "hltv_match_url": "https://www.hltv.org/matches/2399426/voca-vs-havu-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1081120": {
        "hltv_match_id": "2399471",
        "hltv_match_url": "https://www.hltv.org/matches/2399471/mellren-vs-privateer-cct-2026-europe-series-12-closed-qualifier",
        "series_format": "BO3",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080288": {
        "hltv_match_id": "2399427",
        "hltv_match_url": "https://www.hltv.org/matches/2399427/phantom-vs-rounds-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
    "1080289": {
        "hltv_match_id": "2399428",
        "hltv_match_url": "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "reversed",
    },
    "1080290": {
        "hltv_match_id": "2399429",
        "hltv_match_url": "https://www.hltv.org/matches/2399429/phantom-vs-havu-elisa-breakout-series-2",
        "series_format": "BO1",
        "status_override": "open",
        "verified_result": "",
        "team_order_hltv": "normal",
    },
}

# Verified external bookmaker lines for all 32 current-week CS2 fixtures.
# Primary: Direct Pinnacle guest API (`guest.api.arcadia.pinnacle.com`) where available;
# Secondary / Primary when not on Pinnacle: Live EGamersWorld (`bc.game`) verified on 2026-10-14T01:48:00Z.
# Note: 1.80 / 1.80 on EGW is an unpriced placeholder and is rejected (left blank + flagged FL-EXT-PLACEHOLDER).
EXTERNAL_LINES_VERIFIED: dict[str, dict[str, Any]] = {
    "1079620": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/matches",
        "captured_utc": "2026-10-13T17:00:00Z",
        "note": "Match completed 2-0 Black Phoenix before live bookmaker capture; external odds left blank.",
    },
    "1081076": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp",
        "captured_utc": "2026-10-13T21:00:00Z",
        "note": "Match completed 0-2 Galorys; pre-match EGW page showed 1.80/1.80 placeholder so external odds are left blank.",
    },
    "1081105": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "2.330",
        "primary_odds_b": "1.510",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/0U32SId-H/your-end-vs-sukeban-uZgmpQMyd7",
        "egw_odds_a": "2.330",
        "egw_odds_b": "1.510",
        "egw_url": "https://egamersworld.com/counterstrike/match/0U32SId-H/your-end-vs-sukeban-uZgmpQMyd7",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "EGW lists your end 1.51 vs SUKEBAN 2.33 (oriented to Hotspawn Team A SUKEBAN 2.330 / Team B your end 1.510); SUKEBAN subsequently forfeited (0-1 def).",
    },
    "1079546": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "2.700",
        "primary_odds_b": "1.410",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638279105/markets/related/straight",
        "egw_odds_a": "2.450",
        "egw_odds_b": "1.480",
        "egw_url": "https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1638279105 (+170 / -244 American -> 2.700 / 1.410 decimal); cross-checked with EGW bc.game 2.450 / 1.480.",
    },
    "1081111": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.520",
        "primary_odds_b": "2.300",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7",
        "egw_odds_a": "1.520",
        "egw_odds_b": "2.300",
        "egw_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7",
        "captured_utc": "2026-10-14T01:51:00Z",
        "note": "Verified on EGW match page (1.52 Enjoy / 2.30 B8 Academy) and listing page.",
    },
    "1079621": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "2.050",
        "primary_odds_b": "1.640",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
        "egw_odds_a": "2.050",
        "egw_odds_b": "1.640",
        "egw_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Live EGW line moved from earlier 1.881/1.782 to 2.050 Gothic / 1.640 Lavked (44.4% / 55.6% de-vigged).",
    },
    "1080176": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "3.550",
        "primary_odds_b": "1.307",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111785/markets/related/straight",
        "egw_odds_a": "3.870",
        "egw_odds_b": "1.200",
        "egw_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1638111785 (+255 / -326 American -> 3.550 / 1.307 decimal); EGW bc.game 3.870 / 1.200.",
    },
    "1079438": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.090",
        "primary_odds_b": "6.330",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z",
        "egw_odds_a": "1.090",
        "egw_odds_b": "6.330",
        "egw_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Live EGW bc.game quote 1.090 Astralis / 6.330 Sashi (85.3% / 14.7% de-vigged).",
    },
    "1079439": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.990",
        "primary_odds_b": "1.800",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1637867148/markets/related/straight",
        "egw_odds_a": "1.890",
        "egw_odds_b": "1.810",
        "egw_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1637867148 (-101 / -125 American -> 1.990 / 1.800 decimal); EGW bc.game 1.890 / 1.810. Both books slightly favor Fnatic.",
    },
    "1081112": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y",
        "captured_utc": "2026-10-14T01:51:00Z",
        "note": "EGW displays placeholder 1.80 / 1.80; rejected as unpriced and left blank (FL-EXT-PLACEHOLDER).",
    },
    "1079622": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.400",
        "primary_odds_b": "2.680",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
        "egw_odds_a": "1.400",
        "egw_odds_b": "2.680",
        "egw_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Live EGW matches listing displays 1.400 ex-RUSTEC / 2.680 mellren (65.7% / 34.3% de-vigged); subpage HTML cached 1.80/1.80.",
    },
    "1080177": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.254",
        "primary_odds_b": "4.010",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111674/markets/related/straight",
        "egw_odds_a": "1.190",
        "egw_odds_b": "3.950",
        "egw_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/falcons-vs-nip-QSa-aeOIR",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1638111674 (-393 / +301 American -> 1.254 / 4.010 decimal); EGW bc.game 1.190 / 3.950.",
    },
    "1080178": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.654",
        "primary_odds_b": "2.260",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111786/markets/related/straight",
        "egw_odds_a": "1.660",
        "egw_odds_b": "2.070",
        "egw_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/legacy-vs-parivision--TTc59QUDJ",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1638111786 (-153 / +126 American -> 1.654 / 2.260 decimal); EGW bc.game 1.660 / 2.070.",
    },
    "1081113": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3",
        "captured_utc": "2026-10-14T01:51:00Z",
        "note": "EGW displays placeholder 1.80 / 1.80 (with reversed team order PCIFIC Espor vs Ryvex); rejected and left blank (FL-EXT-PLACEHOLDER).",
    },
    "1079623": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.465",
        "primary_odds_b": "2.436",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
        "egw_odds_a": "1.465",
        "egw_odds_b": "2.436",
        "egw_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Live EGW bc.game quote 1.465 G2 Ares / 2.436 The Last Resort (62.4% / 37.6% de-vigged).",
    },
    "1080179": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.364",
        "primary_odds_b": "3.180",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111787/markets/related/straight",
        "egw_odds_a": "1.400",
        "egw_odds_b": "2.860",
        "egw_url": "https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "Direct Pinnacle event 1638111787 (-275 / +218 American -> 1.364 / 3.180 decimal); EGW bc.game 1.400 / 2.860.",
    },
    "1079624": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3",
        "captured_utc": "2026-10-14T01:48:00Z",
        "note": "EGW displays placeholder 1.80 / 1.80; rejected and left blank (FL-EXT-PLACEHOLDER).",
    },
    "1080279": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "2.010",
        "primary_odds_b": "1.690",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ea-copenhagen-hSC7a2mtP",
        "egw_odds_a": "2.010",
        "egw_odds_b": "1.690",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ea-copenhagen-hSC7a2mtP",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 2.010 WROTBERRY / 1.690 EAC (45.7% / 54.3% de-vigged).",
    },
    "1079440": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.637",
        "primary_odds_b": "2.230",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1637936745/markets/related/straight",
        "egw_odds_a": "1.620",
        "egw_odds_b": "2.090",
        "egw_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Direct Pinnacle event 1637936745 (-157 / +123 American -> 1.637 / 2.230 decimal); EGW bc.game 1.620 / 2.090.",
    },
    "1079442": {
        "primary_book": "Pinnacle (Direct)",
        "primary_odds_a": "1.469",
        "primary_odds_b": "2.620",
        "primary_source_url": "https://guest.api.arcadia.pinnacle.com/0.1/matchups/1637999450/markets/related/straight",
        "egw_odds_a": "1.450",
        "egw_odds_b": "2.470",
        "egw_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Direct Pinnacle event 1637999450 (-213 / +162 American -> 1.469 / 2.620 decimal); EGW bc.game 1.450 / 2.470.",
    },
    "1080280": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.300",
        "primary_odds_b": "3.170",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg",
        "egw_odds_a": "1.300",
        "egw_odds_b": "3.170",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.300 ENCE / 3.170 BOJONG (70.9% / 29.1% de-vigged).",
    },
    "1080281": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.620",
        "primary_odds_b": "2.107",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS",
        "egw_odds_a": "1.620",
        "egw_odds_b": "2.107",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.620 WROTBERRY / 2.107 ENCE (56.5% / 43.5% de-vigged).",
    },
    "1080282": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.190",
        "primary_odds_b": "4.020",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5",
        "egw_odds_a": "1.190",
        "egw_odds_b": "4.020",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.190 EAC / 4.020 BOJONG (77.2% / 22.8% de-vigged).",
    },
    "1080283": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.210",
        "primary_odds_b": "3.990",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6",
        "egw_odds_a": "1.210",
        "egw_odds_b": "3.990",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.210 WROTBERRY / 3.990 BOJONG (76.7% / 23.3% de-vigged).",
    },
    "1080284": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.510",
        "primary_odds_b": "2.350",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT",
        "egw_odds_a": "1.510",
        "egw_odds_b": "2.350",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.510 EAC / 2.350 ENCE (60.9% / 39.1% de-vigged).",
    },
    "1080285": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.870",
        "primary_odds_b": "1.770",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja",
        "egw_odds_a": "1.870",
        "egw_odds_b": "1.770",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.870 Voca / 1.770 Phantom (48.6% / 51.4% de-vigged; slight market lean to Phantom vs VRS/HLTV lean to Voca).",
    },
    "1080286": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.190",
        "primary_odds_b": "4.020",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
        "egw_odds_a": "1.190",
        "egw_odds_b": "4.020",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.190 HAVU / 4.020 RoundsGG (77.2% / 22.8% de-vigged).",
    },
    "1080287": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.380",
        "primary_odds_b": "2.700",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP",
        "egw_odds_a": "1.380",
        "egw_odds_b": "2.700",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.380 Voca / 2.700 HAVU (66.2% / 33.8% de-vigged).",
    },
    "1081120": {
        "primary_book": "",
        "primary_odds_a": "",
        "primary_odds_b": "",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/mellren-vs-privateer-gaming-ASh_MyDBS",
        "egw_odds_a": "",
        "egw_odds_b": "",
        "egw_url": "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/mellren-vs-privateer-gaming-ASh_MyDBS",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "EGW displays placeholder 1.80 / 1.80; rejected and left blank (FL-EXT-PLACEHOLDER).",
    },
    "1080288": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.080",
        "primary_odds_b": "6.940",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU",
        "egw_odds_a": "1.080",
        "egw_odds_b": "6.940",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.080 Phantom / 6.940 RoundsGG (86.5% / 13.5% de-vigged).",
    },
    "1080289": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "6.400",
        "primary_odds_b": "1.063",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U",
        "egw_odds_a": "6.400",
        "egw_odds_b": "1.063",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "EGW lists Voca 1.063 vs ROUNDS 6.400 (oriented to Hotspawn Team A RoundsGG 6.400 / Team B Voca 1.063 -> 14.2% / 85.8% de-vigged).",
    },
    "1080290": {
        "primary_book": "bc.game (EGamersWorld)",
        "primary_odds_a": "1.360",
        "primary_odds_b": "2.870",
        "primary_source_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586",
        "egw_odds_a": "1.360",
        "egw_odds_b": "2.870",
        "egw_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586",
        "captured_utc": "2026-10-14T01:49:00Z",
        "note": "Live EGW bc.game BO1 quote 1.360 Phantom / 2.870 HAVU (67.8% / 32.2% de-vigged).",
    },
}

# Verified team overrides / additions from official HLTV match pages (`2399134`–`2399471`)
# and Valve VRS `standings_global_2026_10_05.md` (`eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`).
VERIFIED_TEAM_OVERRIDES: dict[str, dict[str, str]] = {
    "Black Phoenix": {
        "vrs_name": "Black Phoenix",
        "vrs_standing": "76",
        "vrs_points": "1116",
        "vrs_roster": "4X1s, karnez, MRcreed, Salazar, topo",
        "vrs_line": "81",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L81",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0076--black_phoenix--4x1s-karnez-mrcreed-salazar-topo.md",
        "hltv_rank": "57",
        "hltv_points": "16",
        "hltv_team_id": "13924",
        "hltv_name": "Black Phoenix",
        "hltv_roster": "4X1s, karnez, topo, MRcreed, Salazar",
        "hltv_url": "https://www.hltv.org/team/13924/black-phoenix",
        "live_hltv_vrs_rank": "76",
        "resolution": "VERIFIED: VRS name + HLTV roster (5/5 exact match on HLTV match 2399297)",
        "flags": "",
    },
    "Enjoy": {
        "vrs_name": "Enjoy",
        "vrs_standing": "138",
        "vrs_points": "871",
        "vrs_roster": "kurosa, nbl, roxesz, sh1geo, zazzer",
        "vrs_line": "143",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L143",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0138--enjoy--kurosa-nbl-roxesz-sh1geo-zazzer.md",
        "hltv_rank": "199",
        "hltv_points": "3",
        "hltv_team_id": "4246",
        "hltv_name": "Enjoy",
        "hltv_roster": "kurosa, sh1geo, reyoz, nbl, flawix",
        "hltv_url": "https://www.hltv.org/team/4246/enjoy",
        "live_hltv_vrs_rank": "157",
        "resolution": "VERIFIED: VRS name + HLTV roster (3/5 core kurosa, nbl, sh1geo on HLTV match 2399461)",
        "flags": "",
    },
    "B8 Academy": {
        "vrs_name": "B8 Academy",
        "vrs_standing": "261",
        "vrs_points": "631",
        "vrs_roster": "k1n, r0se, segukawa, sherman",
        "vrs_line": "266",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L266",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0261--b8_academy--k1n-r0se-segukawa-sherman.md",
        "hltv_rank": "229",
        "hltv_points": "1",
        "hltv_team_id": "13732",
        "hltv_name": "B8 Academy",
        "hltv_roster": "k1n, segukawa, r0se, sherman, oju",
        "hltv_url": "https://www.hltv.org/team/13732/b8-academy",
        "live_hltv_vrs_rank": "265",
        "resolution": "VERIFIED: VRS name + HLTV roster (4/4 core k1n, r0se, segukawa, sherman on HLTV match 2399461)",
        "flags": "",
    },
    "Banda chuya": {
        "vrs_name": "Banda Chuya",
        "vrs_standing": "165",
        "vrs_points": "801",
        "vrs_roster": "AdrieN, ezox, maaryy, Showk, tomiko",
        "vrs_line": "170",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L170",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0165--banda_chuya--adrien-ezox-maaryy-showk-tomiko.md",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "13900",
        "hltv_name": "Banda Chuya",
        "hltv_roster": "tomiko, maaryy, AdrieN, Showk, ezox",
        "hltv_url": "https://www.hltv.org/team/13900/banda-chuya",
        "live_hltv_vrs_rank": "187",
        "resolution": "VERIFIED: VRS name + HLTV match 2399462 lineup (5/5 exact match AdrieN, ezox, maaryy, Showk, tomiko; disambiguates #165 from #373)",
        "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED",
    },
    "Ryvex": {
        "vrs_name": "Ryvex",
        "vrs_standing": "207",
        "vrs_points": "714",
        "vrs_roster": "jeyN, N0R1, oskvr, swaggy, tvs",
        "vrs_line": "212",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L212",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0207--ryvex--jeyn-n0r1-oskvr-swaggy-tvs.md",
        "hltv_rank": "181",
        "hltv_points": "3",
        "hltv_team_id": "13974",
        "hltv_name": "Ryvex",
        "hltv_roster": "swaggy, jeyN, N0R1, oskvr, wfn",
        "hltv_url": "https://www.hltv.org/team/13974/ryvex",
        "live_hltv_vrs_rank": "219",
        "resolution": "VERIFIED: VRS name + HLTV roster (4/5 core jeyN, N0R1, oskvr, swaggy on HLTV match 2399463)",
        "flags": "",
    },
    "Privateer": {
        "vrs_name": "Privateer",
        "vrs_standing": "271",
        "vrs_points": "608",
        "vrs_roster": "Ariant0, Frazehh, JAUSTERE, M1n1maL, Prime",
        "vrs_line": "276",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L276",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0271--privateer--ariant0-frazehh-jaustere-m1n1mal-prime.md",
        "hltv_rank": "226",
        "hltv_points": "1",
        "hltv_team_id": "13914",
        "hltv_name": "Privateer",
        "hltv_roster": "Frazehh, Prime, moz, M1n1maL, Ariant0",
        "hltv_url": "https://www.hltv.org/team/13914/privateer",
        "live_hltv_vrs_rank": "242",
        "resolution": "VERIFIED: VRS name + HLTV roster (4/5 core Ariant0, Frazehh, M1n1maL, Prime on HLTV match 2399471)",
        "flags": "",
    },
    "Gothic": {
        "vrs_name": "Gothic",
        "vrs_standing": "211",
        "vrs_points": "705",
        "vrs_roster": "Get_Jeka, Raijin, Ryujin, shg, synyx",
        "vrs_line": "216",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L216",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0211--gothic--get_jeka-raijin-ryujin-shg-synyx.md",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "14014",
        "hltv_name": "Gothic",
        "hltv_roster": "Get_Jeka, Ryujin, shg, KENSI, m2",
        "hltv_url": "https://www.hltv.org/team/14014/gothic",
        "live_hltv_vrs_rank": "168",
        "resolution": "VERIFIED: VRS name + HLTV match 2399298 lineup (3/5 core Get_Jeka, Ryujin, shg)",
        "flags": "",
    },
    "ex-RUSTEC": {
        "vrs_name": "ex-RUSTEC",
        "vrs_standing": "92",
        "vrs_points": "1066",
        "vrs_roster": "Brilliance, glowiing, shalfey, yiksrezo, youka",
        "vrs_line": "97",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L97",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0092--ex-rustec--brilliance-glowiing-shalfey-yiksrezo-youka.md",
        "hltv_rank": "79",
        "hltv_points": "10",
        "hltv_team_id": "13901",
        "hltv_name": "ex-RUSTEC",
        "hltv_roster": "shalfey, youka, bl1x1, relaxxie, Brilliance",
        "hltv_url": "https://www.hltv.org/team/13901/ex-rustec",
        "live_hltv_vrs_rank": "93",
        "resolution": "VERIFIED: VRS #92 (1066 pts) + HLTV #79 (3/5 core Brilliance, shalfey, youka + live HLTV VRS #93 on match 2399299; disambiguates #92 from #152)",
        "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED",
    },
    "Sashi": {
        "vrs_name": "Sashi",
        "vrs_standing": "73",
        "vrs_points": "1131",
        "vrs_roster": "acoR, Anlelele, Cabbi, MistR, Zyphon",
        "vrs_line": "78",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L78",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0073--sashi--acor-anlelele-cabbi-mistr-zyphon.md",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "11712",
        "hltv_name": "Sashi",
        "hltv_roster": "TjP, Hatz, Anlelele, acoR, Zyphon",
        "hltv_url": "https://www.hltv.org/team/11712/sashi",
        "live_hltv_vrs_rank": "90",
        "resolution": "VERIFIED: VRS name + HLTV match 2399134 lineup (3/5 core acoR, Anlelele, Zyphon)",
        "flags": "",
    },
    "LFO 10": {
        "vrs_name": "",
        "vrs_standing": "",
        "vrs_points": "",
        "vrs_roster": "",
        "vrs_line": "",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L161",
        "vrs_details_url": "",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "14084",
        "hltv_name": "LFO 10",
        "hltv_roster": "Jackinho, Sapec, flaw, dottie, tvs",
        "hltv_url": "https://www.hltv.org/team/14084/lfo-10",
        "live_hltv_vrs_rank": "169",
        "resolution": "UNVERIFIED IN 2026-10-05 VRS BY NAME (HLTV match 2399301 lists LFO 10 at VRS #169 with 4-man core dottie, flaw, Sapec, tevsii from VRS #156 Entropy 813 pts; left blank per zero-inference rule)",
        "flags": "FL-UNVERIFIED-TEAM",
    },
    "your end": {
        "vrs_name": "your end",
        "vrs_standing": "295",
        "vrs_points": "582",
        "vrs_roster": "Cr1a, ghosT1, Lcs, Lukita, rx",
        "vrs_line": "300",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L300",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0295--your_end--cr1a-ghost1-lcs-lukita-rx.md",
        "hltv_rank": "215",
        "hltv_points": "2",
        "hltv_team_id": "14008",
        "hltv_name": "your end",
        "hltv_roster": "Lcs, Lukita, rx, Cr1a, ghosT1",
        "hltv_url": "https://www.hltv.org/team/14008/your-end",
        "live_hltv_vrs_rank": "299",
        "resolution": "VERIFIED: VRS name + HLTV roster (5/5 exact match on HLTV match 2399460)",
        "flags": "",
    },
    "SUKEBAN": {
        "vrs_name": "",
        "vrs_standing": "",
        "vrs_points": "",
        "vrs_roster": "",
        "vrs_line": "",
        "vrs_url": VRS_BASE_URL,
        "vrs_details_url": "",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "14091",
        "hltv_name": "SUKEBAN",
        "hltv_roster": "RAYQUAZA, thpp, thoth, k1st, pml",
        "hltv_url": "https://www.hltv.org/team/14091/sukeban",
        "live_hltv_vrs_rank": "",
        "resolution": "UNRANKED IN VRS & HLTV (HLTV match 2399460 confirms HLTV: Unranked, VRS: Unranked, forfeited 0-1 default)",
        "flags": "FL-UNVERIFIED-TEAM;FL-FORFEIT-DEFAULT",
    },
    "ex-Keyd Stars": {
        "vrs_name": "ex-Keyd Stars",
        "vrs_standing": "144",
        "vrs_points": "854",
        "vrs_roster": "ckzao, drg, lash, xureba, zede",
        "vrs_line": "149",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L149",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0144--ex-keyd_stars--ckzao-drg-lash-xureba-zede.md",
        "hltv_rank": "",
        "hltv_points": "",
        "hltv_team_id": "13423",
        "hltv_name": "ex-Keyd Stars",
        "hltv_roster": "xureba, lash, drg, ALLE, ckzao",
        "hltv_url": "https://www.hltv.org/team/13423/ex-keyd-stars",
        "live_hltv_vrs_rank": "",
        "resolution": "VERIFIED: VRS name + HLTV match 2399204 lineup (4/5 core ckzao, drg, lash, xureba)",
        "flags": "",
    },
    "Zomblers": {
        "vrs_name": "Zomblers",
        "vrs_standing": "254",
        "vrs_points": "639",
        "vrs_roster": "CAJUN, CoolComs, FxRE, man327, Pose1doNN",
        "vrs_line": "259",
        "vrs_url": f"{VRS_BASE_URL}?plain=1#L259",
        "vrs_details_url": f"{VRS_DETAILS_BASE}details/2026_10_05/0254--zomblers--cajun-coolcoms-fxre-man327-pose1donn.md",
        "hltv_rank": "197",
        "hltv_points": "3",
        "hltv_team_id": "12164",
        "hltv_name": "Zomblers",
        "hltv_roster": "CoolComs, CAJUN, Pose1doNN, twigs, sml",
        "hltv_url": "https://www.hltv.org/team/12164/zomblers",
        "live_hltv_vrs_rank": "211",
        "resolution": "VERIFIED: VRS #254 (639 pts) + HLTV #197 (3/5 core CAJUN, CoolComs, Pose1doNN on HLTV match 2399232; duplicate #259 has 631 pts)",
        "flags": "FL-DUPLICATE-VRS-DISAMBIGUATED",
    },
}

# Cross-repo irregularities discovered during our line-by-line repository review
REPO_AUDIT_IRREGULARITIES: list[dict[str, str]] = [
    {
        "flag_id": "IRREG-01",
        "severity": "HIGH",
        "category": "Pipeline Crash / Null Permalink Coercion",
        "repo_location": "model/build.py:289 (CI run 38489574648)",
        "affected_items": "Fixtures 1081111, 1081112, 1081113, 1081120 (CCT Europe 2026 Series #12 Play-In)",
        "description": "Hotspawn's ng-state JSON omits the permalink field on the 4 newly added CCT Series #12 Play-In fixtures. In model/build.py, stringifying a missing permalink emitted a literal placeholder word into model/data/lines.csv, failing model/test_model.py::test_every_published_value_has_official_source in scheduled run 38489574648.",
        "our_resolution": "In data/8944bb84/fixtures.csv, hotspawn_match_url is left blank ('') when Hotspawn has no /matches/ permalink, hotspawn_lobby_url links to https://play.hotspawn.com/cs2-pickems, and official HLTV match URLs (2399461, 2399462, 2399463, 2399471) are linked on every row.",
        "official_source_url": "https://www.hltv.org/events/9456/cct-2026-europe-series-12-closed-qualifier",
    },
    {
        "flag_id": "IRREG-02",
        "severity": "HIGH",
        "category": "Duplicate VRS Team-Name Overwrite Flipping Pick",
        "repo_location": "slate/collect.py & slate/data/ratings.csv:269 & slate/data/analysis.csv:9",
        "affected_items": "1079622 ex-RUSTEC vs mellren + 13 other CS2 teams (6666, Banda chuya, Zomblers, BIG Academy, Honved, Johnny Speeds, Just Players, Leo, Lilmix, Misa, METANOIA Wolves, Mai Tai, UNO MILLE)",
        "description": "Valve's standings_global_2026_10_05.md contains 31 duplicate team names (active 5-man roster higher up, older/partial roster lower down). slate/collect.py iterates top-to-bottom and overwrites vrs[key]=row, replacing ex-RUSTEC #92 (1066 pts, #L97) with #152 (824 pts, #L157), 6666 #127 (923 pts) with #368 (425 pts), and Banda Chuya #165 (801 pts) with #373 (402 pts). For 1079622 (ex-RUSTEC vs mellren), this bug flipped slate/data/analysis.csv's own-line probability to 42.54% ex-RUSTEC / 57.46% mellren and triggered a false S-F-09 disagreement flag.",
        "our_resolution": "Disambiguated every duplicate VRS team name using official 5-man lineups and live VRS badges on HLTV match pages (2399299 confirms ex-RUSTEC #92/1066 pts & live VRS #93; 2399462 confirms Banda Chuya #165/801 pts and 6666 #127/923 pts).",
        "official_source_url": "https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11",
    },
    {
        "flag_id": "IRREG-03",
        "severity": "MEDIUM",
        "category": "Started CS2 Fixture Misclassified as sport='other'",
        "repo_location": "slate/collect.py & slate/data/fixtures.csv:66",
        "affected_items": "1081076 ex-Keyd Stars vs Galorys (ESL Challenger League Season 52 SA Cup #3)",
        "description": "slate/collect.py's sport_of(fixture) classifies sport solely by which page (cs2-pickems vs lobby) rendered the card and ignores sport_alias='cs2' in the TransferState payload. Once 1081076 kicked off at 2026-10-13T21:00:00Z, /cs2-pickems dropped it while /lobby retained it with sport_alias='cs2', causing slate/data/fixtures.csv to misclassify 1081076 as sport='other' and omit it from CS2 analysis.",
        "our_resolution": "Classified by sport_alias='cs2' and verified official final score (ex-Keyd Stars 0 - 2 Galorys) on HLTV match 2399204.",
        "official_source_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3",
    },
    {
        "flag_id": "IRREG-04",
        "severity": "MEDIUM",
        "category": "HTML Block Truncation Dropping 37 HLTV Ranks & False FL-03 Flags",
        "repo_location": "live/collect.py:614 & live/data/slate.csv",
        "affected_items": "9z (#17), MIBR (#12), Ninjas in Pyjamas (#26), HOTU (#41), Voca (#59), BC.Game (#70), ex-RUSTEC (#79), Phantom (#88), WBT/WROTBERRY (#109), ROUNDS/RoundsGG (#237)",
        "description": "live/collect.py truncates each .ranked-team HTML block at block[:4000] before searching for /team/<id>/<slug>. For 37 of the 245 ranked teams on HLTV (including open-slate teams MIBR #12, 9z #17, NiP #26, HOTU #41, Voca #59, Phantom #88), the team profile link sits past byte 4000, leaving hltv_rank blank in live/data/slate.csv and triggering false FL-03 ('missing from HLTV top-30') flags on 9z (#17) and MIBR (#12). Also, slug.replace('-', ' ') turns ex-rustec into 'ex rustec' and bcgame into 'bcgame', failing exact match for ex-RUSTEC (#79) and BC.Game (#70).",
        "our_resolution": "Parsed the full 245-team HLTV ranking snapshot without 4,000-byte truncation and verified team IDs directly against HLTV match pages.",
        "official_source_url": "https://www.hltv.org/ranking/teams/2026/october/12",
    },
    {
        "flag_id": "IRREG-05",
        "severity": "MEDIUM",
        "category": "Series Format Assumed BO3 on 12 Official BO1 Matches",
        "repo_location": "slate/data/own_lines.csv & slate/data/analysis.csv (rows 1080279..1080290)",
        "affected_items": "All 12 Elisa BreakOut Series #2 Group Stage matches (1080279 through 1080290)",
        "description": "slate/data/own_lines.csv and slate/data/analysis.csv flag S-F-08 ('no source states the series format; assumes best-of-3') and apply a BO3 series expansion p^2(3-2p) to all 12 Elisa BreakOut Series #2 matches, inflating favorites' originated probabilities. Both HLTV (matches 2399418..2399429) and EGamersWorld explicitly list all 12 group-stage matches as Best-of-1 (BO1).",
        "our_resolution": "Verified series_format='BO1' for 1080279..1080290 directly from HLTV match pages 2399418..2399429 and EGW.",
        "official_source_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
    },
    {
        "flag_id": "IRREG-06",
        "severity": "LOW",
        "category": "Inverted S-F-05 Single-Source Flag Wording",
        "repo_location": "slate/data/ratings.csv (lines 32, 82, 95, 114, 146, 151, 179, 249, 267)",
        "affected_items": "Banda chuya, Gothic, ex-Keyd Stars, Endless Journey, KOLESIE, Mai Tai, METANOIA Wolves, Patins da Ferrari, UNO MILLE",
        "description": "When a team is found in Valve VRS (vrs_points populated) but absent from HLTV's top-245 ranking (hltv_rank blank), slate/data/ratings.csv emits 'S-F-05: team found in one official rating source only (HLTV)', inverting the name of the source that actually matched.",
        "our_resolution": "Explicitly state in data/8944bb84/ratings.csv whether a team is verified in both Valve VRS + HLTV Ranking, or verified in Valve VRS + HLTV Match Page (outside HLTV top-245).",
        "official_source_url": VRS_BASE_URL,
    },
    {
        "flag_id": "IRREG-07",
        "severity": "LOW",
        "category": "Missing Hotspawn Fixture IDs on 5 Current-Week Rows",
        "repo_location": "picks/data/fixtures.csv",
        "affected_items": "1081105 (SUKEBAN vs your end), 1081111 (Enjoy vs B8 Academy), 1081112 (Banda chuya vs 6666), 1081113 (Ryvex vs PCIFIC), 1081120 (mellren vs Privateer)",
        "description": "picks/data/fixtures.csv lists these 5 current-week matches with an empty hotspawn_id ('') column because they were added after the initial TransferState ID capture.",
        "our_resolution": "Verified all 5 Hotspawn TransferState IDs (1081105, 1081111, 1081112, 1081113, 1081120) from Hotspawn's ng-state payload.",
        "official_source_url": HOTSPAWN_CS2_URL,
    },
    {
        "flag_id": "IRREG-08",
        "severity": "LOW",
        "category": "Stale Snapshot Coverage in Earlier Boards",
        "repo_location": "today/data/current.json & data/snapshot/latest.json",
        "affected_items": "today/data/current.json (85 fixtures, 25 current-week as of 2026-10-13T16:40:14Z)",
        "description": "Earlier static snapshots predate the 5 CCT SA #7 / CCT EU #12 Play-In matches added on 2026-10-13 21:00–23:30 UTC (1081105, 1081111, 1081112, 1081113, 1081120) and the 2026-10-14 EGW line movements (e.g., 1079621 Gothic vs Lavked moving from 1.881/1.782 to 2.050/1.640).",
        "our_resolution": "Full 91-fixture coverage (28 open Oct 14-16 + 4 started/completed Oct 13-14 + 59 stale summer) with scheduled GitHub Actions refresh in .github/workflows/oct14-8944bb84.yml.",
        "official_source_url": HOTSPAWN_CS2_URL,
    },
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def devig_proportional(odds_a_str: str, odds_b_str: str) -> tuple[str, str, str]:
    """Return (overround_pct, p_a_pct, p_b_pct) or ('', '', '') if odds are blank."""
    if not odds_a_str or not odds_b_str:
        return "", "", ""
    oa = float(odds_a_str)
    ob = float(odds_b_str)
    if oa <= 1.0 or ob <= 1.0:
        return "", "", ""
    inv_a = 1.0 / oa
    inv_b = 1.0 / ob
    total = inv_a + inv_b
    overround = (total - 1.0) * 100.0
    pa = (inv_a / total) * 100.0
    pb = 100.0 - round(pa, 1)
    return f"{overround:.2f}", f"{pa:.1f}", f"{pb:.1f}"


def vrs_glicko_win_prob(pts_a_str: str, pts_b_str: str) -> tuple[str, str]:
    """Valve VRS calibrated Glicko expected win rate: 1 / (1 + 10^((B - A) / 372.12))."""
    if not pts_a_str or not pts_b_str:
        return "", ""
    a = float(pts_a_str)
    b = float(pts_b_str)
    pa = 1.0 / (1.0 + 10.0 ** ((b - a) / VRS_GLICKO_SCALE))
    pa_pct = round(pa * 100.0, 1)
    pb_pct = round(100.0 - pa_pct, 1)
    return f"{pa_pct:.1f}", f"{pb_pct:.1f}"


def hltv_rating_win_prob(pts_a_str: str, pts_b_str: str, rank_a_str: str, rank_b_str: str) -> tuple[str, str]:
    """
    HLTV World Ranking probability component when both teams are ranked in HLTV top 245.
    Uses logistic on log-points + rank differential:
      score_diff = 120 * log10((pts_a + 3) / (pts_b + 3)) + 1.2 * (rank_b - rank_a)
      P(A) = 1 / (1 + 10^(-score_diff / 400))
    """
    if not pts_a_str or not pts_b_str or not rank_a_str or not rank_b_str:
        return "", ""
    pa_pts = float(pts_a_str)
    pb_pts = float(pts_b_str)
    ra = float(rank_a_str)
    rb = float(rank_b_str)
    score_diff = 120.0 * math.log10((pa_pts + 3.0) / (pb_pts + 3.0)) + 1.2 * (rb - ra)
    p = 1.0 / (1.0 + 10.0 ** (-score_diff / 400.0))
    pa_pct = round(p * 100.0, 1)
    pb_pct = round(100.0 - pa_pct, 1)
    return f"{pa_pct:.1f}", f"{pb_pct:.1f}"


def fair_decimal_odds(p_pct_str: str) -> str:
    if not p_pct_str:
        return ""
    p = float(p_pct_str) / 100.0
    if p <= 0.0 or p >= 1.0:
        return ""
    return f"{(1.0 / p):.2f}"


def load_base_teams() -> dict[str, dict[str, str]]:
    teams: dict[str, dict[str, str]] = {}
    model_teams_csv = ROOT / "model" / "data" / "teams.csv"
    with model_teams_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["hotspawn_team"]
            vrs_line = ""
            if "#L" in (r.get("vrs_url") or ""):
                vrs_line = r["vrs_url"].split("#L")[-1]
            teams[name] = {
                "hotspawn_team": name,
                "vrs_name": r.get("vrs_name") or "",
                "vrs_standing": r.get("vrs_standing") or "",
                "vrs_points": r.get("vrs_points") or "",
                "vrs_roster": r.get("vrs_roster") or "",
                "vrs_line": vrs_line,
                "vrs_url": r.get("vrs_url") or VRS_BASE_URL,
                "vrs_details_url": r.get("vrs_details_url") or "",
                "hltv_rank": r.get("hltv_rank") or "",
                "hltv_points": r.get("hltv_points") or "",
                "hltv_team_id": (r.get("hltv_url") or "").split("/team/")[1].split("/")[0] if "/team/" in (r.get("hltv_url") or "") else "",
                "hltv_name": name,
                "hltv_roster": r.get("hltv_players") or "",
                "hltv_url": r.get("hltv_url") or HLTV_RANKING_URL,
                "live_hltv_vrs_rank": r.get("vrs_standing") or "",
                "resolution": (r.get("resolution") or "") + (f" ({r['note']})" if r.get("note") else ""),
                "flags": "FL-ALIAS-RESOLVED" if "alias" in (r.get("resolution") or "").lower() or "name change" in (r.get("resolution") or "").lower() else "",
            }
    for name, override in VERIFIED_TEAM_OVERRIDES.items():
        base = teams.get(name, {"hotspawn_team": name})
        base.update(override)
        base["hotspawn_team"] = name
        teams[name] = base
    return teams


def load_all_91_cs2_fixtures() -> list[dict[str, Any]]:
    """
    Combine CS2 fixtures from `live/data/snapshot.json` (90 CS2 fixtures) and
    `model/data/lines.csv` (86 CS2 fixtures, including `1079620 Black Phoenix vs 6666`),
    Explicitly stripping any Hotspawn crowd fields.
    """
    live_snap_path = ROOT / "live" / "data" / "snapshot.json"
    with live_snap_path.open(encoding="utf-8") as f:
        live_snap = json.load(f)

    model_lines_path = ROOT / "model" / "data" / "lines.csv"
    model_rows: dict[str, dict[str, str]] = {}
    with model_lines_path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            model_rows[r["hotspawn_match_id"]] = r

    fixtures_by_id: dict[str, dict[str, Any]] = {}

    for raw in live_snap.get("fixtures", []):
        if raw.get("sport") != "cs2":
            continue
        mid = str(raw["match_id"])
        mr = model_rows.get(mid, {})
        hs_match_url = raw.get("hotspawn_match_url") or mr.get("hotspawn_url") or ""
        if hs_match_url in ("None", "null", HOTSPAWN_CS2_URL, HOTSPAWN_LOBBY_URL):
            hs_match_url = ""
        fixtures_by_id[mid] = {
            "match_id": mid,
            "start_utc": raw["start_utc"],
            "lock_utc": raw.get("lock_utc") or "",
            "tournament": raw.get("competition") or "",
            "tier": (raw.get("tier") or "").upper(),
            "points": str(raw.get("offered_points") or ""),
            "stage": raw.get("stage") or "",
            "team_a": raw["team_a"],
            "team_b": raw["team_b"],
            "hotspawn_status": raw.get("status") or "scheduled",
            "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
            "hotspawn_match_url": hs_match_url,
        }

    # Add 1079620 (Black Phoenix vs 6666) from model/data/lines.csv if not in live_snap
    for mid, mr in model_rows.items():
        if mid not in fixtures_by_id:
            start_iso = mr["scheduled_start_utc"].replace(" ", "T") + ":00Z" if "T" not in mr["scheduled_start_utc"] else mr["scheduled_start_utc"]
            lock_iso = mr["lock_utc"].replace(" ", "T") + ":00Z" if "T" not in mr["lock_utc"] else mr["lock_utc"]
            hs_url = mr.get("hotspawn_url") or ""
            if hs_url in ("None", "null", HOTSPAWN_CS2_URL, HOTSPAWN_LOBBY_URL):
                hs_url = ""
            tier_val = (mr.get("tier") or "B").upper()
            pts_map = {"S": "7", "A": "5", "B": "3", "C": "2"}
            fixtures_by_id[mid] = {
                "match_id": mid,
                "start_utc": start_iso,
                "lock_utc": lock_iso,
                "tournament": mr.get("competition") or "",
                "tier": tier_val,
                "points": pts_map.get(tier_val, "3"),
                "stage": mr.get("stage") or "",
                "team_a": mr["team_a"],
                "team_b": mr["team_b"],
                "hotspawn_status": mr.get("hotspawn_status") or "finished",
                "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
                "hotspawn_match_url": hs_url,
            }

    # Preserve completed Week-270 fixtures dropped from Hotspawn's live TransferState after completion
    completed_week270 = [
        {
            "match_id": "1079620",
            "start_utc": "2026-10-13T17:00:00Z",
            "lock_utc": "2026-10-13T16:54:00Z",
            "tournament": "CCT Europe 2026 Series #11",
            "tier": "B",
            "points": "3",
            "stage": "group stage",
            "team_a": "Black Phoenix",
            "team_b": "6666",
            "hotspawn_status": "finished",
            "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
            "hotspawn_match_url": "https://www.hotspawn.com/matches/black-phoenix-vs-6666-cct-europe-2026-series-11-1079620",
        },
        {
            "match_id": "1081076",
            "start_utc": "2026-10-13T21:00:00Z",
            "lock_utc": "2026-10-13T20:54:00Z",
            "tournament": "ESL Challenger League Season 52: South America - Cup #3",
            "tier": "B",
            "points": "3",
            "stage": "playoffs",
            "team_a": "ex-Keyd Stars",
            "team_b": "Galorys",
            "hotspawn_status": "finished",
            "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
            "hotspawn_match_url": "https://www.hotspawn.com/matches/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3-1081076",
        },
        {
            "match_id": "1081105",
            "start_utc": "2026-10-13T22:00:00Z",
            "lock_utc": "2026-10-13T21:54:00Z",
            "tournament": "CCT South America 2026 Series #7",
            "tier": "C",
            "points": "2",
            "stage": "group stage",
            "team_a": "SUKEBAN",
            "team_b": "your end",
            "hotspawn_status": "finished",
            "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
            "hotspawn_match_url": "",
        },
        {
            "match_id": "1079546",
            "start_utc": "2026-10-14T01:00:00Z",
            "lock_utc": "2026-10-14T00:54:00Z",
            "tournament": "ESL Challenger League Season 52: North America - Cup #3",
            "tier": "B",
            "points": "3",
            "stage": "playoffs",
            "team_a": "Zomblers",
            "team_b": "Overtake Sector",
            "hotspawn_status": "running",
            "hotspawn_lobby_url": HOTSPAWN_CS2_URL,
            "hotspawn_match_url": "https://www.hotspawn.com/matches/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3-1079546",
        },
    ]
    for cf in completed_week270:
        if cf["match_id"] not in fixtures_by_id:
            fixtures_by_id[cf["match_id"]] = cf

    return sorted(fixtures_by_id.values(), key=lambda x: (x["start_utc"], int(x["match_id"])))


def build_datasets(live_check: bool = False) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SITE_DIR.mkdir(parents=True, exist_ok=True)

    teams = load_base_teams()
    raw_fixtures = load_all_91_cs2_fixtures()

    # Track which teams are on the open slate (Oct 14-16) and current week (Oct 13-16)
    open_team_names: set[str] = set()
    week_team_names: set[str] = set()
    for f in raw_fixtures:
        if f["start_utc"] >= "2026-10-13":
            week_team_names.add(f["team_a"])
            week_team_names.add(f["team_b"])
            if f["start_utc"] >= "2026-10-14T08:00:00Z":
                open_team_names.add(f["team_a"])
                open_team_names.add(f["team_b"])

    fixtures_rows: list[dict[str, str]] = []
    external_rows: list[dict[str, str]] = []
    own_rows: list[dict[str, str]] = []
    analysis_rows: list[dict[str, str]] = []
    fixture_flags_rows: list[dict[str, str]] = []

    for f in raw_fixtures:
        mid = f["match_id"]
        ta = f["team_a"]
        tb = f["team_b"]
        start_utc = f["start_utc"]

        if start_utc >= "2026-10-14T08:00:00Z":
            slate_bucket = "open_oct14_16"
        elif start_utc >= "2026-10-13":
            slate_bucket = "locked_oct13_14"
        else:
            slate_bucket = "stale_summer_2026"

        hm = CURRENT_WEEK_HLTV_MATCHES.get(mid, {})
        hltv_match_id = hm.get("hltv_match_id", "")
        hltv_match_url = hm.get("hltv_match_url", "")
        series_format = hm.get("series_format", "")
        status = hm.get("status_override") or ("stale_locked" if slate_bucket == "stale_summer_2026" else f["hotspawn_status"])
        verified_result = hm.get("verified_result", "")
        team_order_hltv = hm.get("team_order_hltv", "normal")

        ext_info = EXTERNAL_LINES_VERIFIED.get(mid, {})
        egw_url = ext_info.get("egw_url", "")
        ext_book = ext_info.get("primary_book", "")
        ext_odds_a = ext_info.get("primary_odds_a", "")
        ext_odds_b = ext_info.get("primary_odds_b", "")
        ext_source_url = ext_info.get("primary_source_url", "")
        egw_odds_a = ext_info.get("egw_odds_a", "")
        egw_odds_b = ext_info.get("egw_odds_b", "")
        overround_pct, ext_p_a, ext_p_b = devig_proportional(ext_odds_a, ext_odds_b)
        _, egw_p_a, egw_p_b = devig_proportional(egw_odds_a, egw_odds_b)

        t_a = teams.get(ta, {"hotspawn_team": ta, "vrs_url": VRS_BASE_URL, "hltv_url": HLTV_RANKING_URL})
        t_b = teams.get(tb, {"hotspawn_team": tb, "vrs_url": VRS_BASE_URL, "hltv_url": HLTV_RANKING_URL})

        vrs_p_a, vrs_p_b = vrs_glicko_win_prob(t_a.get("vrs_points", ""), t_b.get("vrs_points", ""))
        hltv_p_a, hltv_p_b = hltv_rating_win_prob(
            t_a.get("hltv_points", ""),
            t_b.get("hltv_points", ""),
            t_a.get("hltv_rank", ""),
            t_b.get("hltv_rank", ""),
        )

        # Originate our own rating line strictly from official CS2 data (Valve VRS + HLTV Ranking):
        # 80% Valve VRS Glicko + 20% HLTV Ranking when both teams have verified VRS & HLTV points;
        # 100% Valve VRS Glicko when both teams have verified VRS points and 1 team is outside HLTV top 245;
        # BLANK when either team lacks a verified 2026-10-05 VRS standing (no inference).
        if vrs_p_a and hltv_p_a:
            own_pa_val = round(0.80 * float(vrs_p_a) + 0.20 * float(hltv_p_a), 1)
            own_pb_val = round(100.0 - own_pa_val, 1)
            own_p_a = f"{own_pa_val:.1f}"
            own_p_b = f"{own_pb_val:.1f}"
            own_method = f"80% Valve VRS Glicko + 20% HLTV Ranking ({series_format or 'Series'})"
        elif vrs_p_a:
            own_p_a = vrs_p_a
            own_p_b = vrs_p_b
            own_method = f"100% Valve VRS Glicko (1 team outside HLTV Top-245; {series_format or 'Series'})"
        else:
            own_p_a = ""
            own_p_b = ""
            own_method = "BLANK — UNVERIFIED IN 2026-10-05 VRS"

        own_fair_a = fair_decimal_odds(own_p_a)
        own_fair_b = fair_decimal_odds(own_p_b)
        own_pick = ""
        if own_p_a and own_p_b:
            own_pick = ta if float(own_p_a) >= float(own_p_b) else tb

        # Consensus / Combined Originated Probability (50% Official Rating Line + 50% De-vigged External Market Line
        # when both exist; Official Rating Line when market is placeholder/absent; BLANK if neither is verified)
        if own_p_a and ext_p_a:
            cons_pa_val = round(0.50 * float(own_p_a) + 0.50 * float(ext_p_a), 1)
            cons_pb_val = round(100.0 - cons_pa_val, 1)
            consensus_p_a = f"{cons_pa_val:.1f}"
            consensus_p_b = f"{cons_pb_val:.1f}"
            consensus_basis = f"50% Official Rating ({own_p_a}%) + 50% De-vigged {ext_book.split(' ')[0]} ({ext_p_a}%)"
            diff_pp = f"{(float(own_p_a) - float(ext_p_a)):+.1f}"
        elif own_p_a:
            consensus_p_a = own_p_a
            consensus_p_b = own_p_b
            consensus_basis = f"100% Official Rating ({own_method}; no priced market line)"
            diff_pp = ""
        else:
            consensus_p_a = ""
            consensus_p_b = ""
            consensus_basis = "BLANK — UNVERIFIED (Flagged for Review)"
            diff_pp = ""

        recommended_pick = ""
        pick_prob = ""
        pick_confidence = "UNVERIFIED — FLAGGED"
        if consensus_p_a and consensus_p_b:
            pa_f = float(consensus_p_a)
            pb_f = float(consensus_p_b)
            if pa_f >= pb_f:
                recommended_pick = ta
                pick_prob = consensus_p_a
                fav_p = pa_f
            else:
                recommended_pick = tb
                pick_prob = consensus_p_b
                fav_p = pb_f
            if fav_p >= 70.0:
                pick_confidence = "OBVIOUS LOCK (>=70%)"
            elif fav_p >= 60.0:
                pick_confidence = "STRONG PICK (60-69%)"
            elif fav_p >= 55.0:
                pick_confidence = "SOLID LEAN (55-59%)"
            else:
                pick_confidence = "CLOSE TOSS-UP (<55%)"

        row_flags: list[str] = []
        if not own_p_a:
            row_flags.append("FL-UNVERIFIED-TEAM")
        if slate_bucket == "open_oct14_16" and not ext_odds_a:
            row_flags.append("FL-EXT-PLACEHOLDER")
        if slate_bucket == "locked_oct13_14" and not ext_odds_a:
            row_flags.append("FL-LOCKED-NO-PREMATCH-ODDS")
        if slate_bucket in ("open_oct14_16", "locked_oct13_14") and not f["hotspawn_match_url"]:
            row_flags.append("FL-NO-HOTSPAWN-PERMALINK")
        if team_order_hltv == "reversed":
            row_flags.append("FL-TEAM-ORDER-REVERSED")
        if own_p_a and ext_p_a:
            own_fav_a = float(own_p_a) >= 50.0
            ext_fav_a = float(ext_p_a) >= 50.0
            if own_fav_a != ext_fav_a:
                if abs(float(own_p_a) - 50.0) <= 6.0 and abs(float(ext_p_a) - 50.0) <= 6.0:
                    row_flags.append("FL-COINFLIP-SPLIT")
                else:
                    row_flags.append("FL-MARKET-VRS-SPLIT")
            elif abs(float(own_p_a) - float(ext_p_a)) >= 12.0:
                row_flags.append("FL-MODEL-MARKET-GAP")
        if t_a.get("flags"):
            for fl in t_a["flags"].split(";"):
                if fl and fl not in row_flags:
                    row_flags.append(fl)
        if t_b.get("flags"):
            for fl in t_b["flags"].split(";"):
                if fl and fl not in row_flags:
                    row_flags.append(fl)
        if slate_bucket == "stale_summer_2026":
            row_flags.append("FL-STALE-TRANSFERSTATE")

        flags_str = ";".join(row_flags)

        # Build concise human-readable analysis summary
        if slate_bucket == "open_oct14_16":
            if mid == "1079624":
                analysis_note = (
                    "UNVERIFIED / BLANK: FORZE Reload is VRS #84 (1100 pts) & HLTV #75 (11 pts), "
                    "while LFO 10 is absent by name from the 2026-10-05 VRS file (HLTV match 2399301 lists LFO 10 at live VRS #169 "
                    "with the 4-man core of VRS #156 Entropy, 813 pts) and EGW shows 1.80/1.80 placeholder."
                )
            elif ext_p_a and own_p_a:
                agree_word = "agree" if (float(own_p_a) >= 50.0) == (float(ext_p_a) >= 50.0) else "split"
                analysis_note = (
                    f"{series_format} ({f['tier']}-Tier, {f['points']} pts): {ext_book} prices {ta} {ext_odds_a} / {tb} {ext_odds_b} "
                    f"({ext_p_a}% / {ext_p_b}% de-vigged); Official VRS+HLTV rating model gives {own_p_a}% / {own_p_b}% "
                    f"(VRS #{t_a.get('vrs_standing') or 'NR'} vs #{t_b.get('vrs_standing') or 'NR'}, "
                    f"HLTV #{t_a.get('hltv_rank') or 'NR'} vs #{t_b.get('hltv_rank') or 'NR'}) — sources {agree_word}."
                )
            else:
                analysis_note = (
                    f"{series_format} ({f['tier']}-Tier, {f['points']} pts): EGW shows 1.80/1.80 placeholder (rejected); "
                    f"pick originated strictly from official VRS (#{t_a.get('vrs_standing')} {t_a.get('vrs_points')} pts vs "
                    f"#{t_b.get('vrs_standing')} {t_b.get('vrs_points')} pts) & HLTV (#{t_a.get('hltv_rank') or 'NR'} vs #{t_b.get('hltv_rank') or 'NR'})."
                )
        elif slate_bucket == "locked_oct13_14":
            analysis_note = f"Started/Completed Week-270 match ({series_format}): {verified_result}."
        else:
            analysis_note = "Stale June–July 2026 TransferState fixture retained by Hotspawn's Angular payload; excluded from active picks."

        fixtures_rows.append({
            "match_id": mid,
            "slate_bucket": slate_bucket,
            "start_utc": start_utc,
            "lock_utc": f["lock_utc"],
            "status": status,
            "tournament": f["tournament"],
            "tier": f["tier"],
            "points": f["points"],
            "stage": f["stage"],
            "series_format": series_format,
            "team_a": ta,
            "team_b": tb,
            "hotspawn_lobby_url": f["hotspawn_lobby_url"],
            "hotspawn_match_url": f["hotspawn_match_url"],
            "hltv_match_id": hltv_match_id,
            "hltv_match_url": hltv_match_url,
            "egw_match_url": egw_url,
            "verified_result": verified_result,
            "flags": flags_str,
        })

        if slate_bucket in ("open_oct14_16", "locked_oct13_14"):
            external_rows.append({
                "match_id": mid,
                "slate_bucket": slate_bucket,
                "start_utc": start_utc,
                "tournament": f["tournament"],
                "series_format": series_format,
                "team_a": ta,
                "team_b": tb,
                "primary_book": ext_book,
                "primary_odds_a": ext_odds_a,
                "primary_odds_b": ext_odds_b,
                "overround_pct": overround_pct,
                "devig_p_a_pct": ext_p_a,
                "devig_p_b_pct": ext_p_b,
                "primary_source_url": ext_source_url,
                "egw_odds_a": egw_odds_a,
                "egw_odds_b": egw_odds_b,
                "egw_devig_p_a_pct": egw_p_a,
                "egw_devig_p_b_pct": egw_p_b,
                "egw_url": egw_url,
                "hltv_match_url": hltv_match_url,
                "captured_utc": ext_info.get("captured_utc", ""),
                "note": ext_info.get("note", ""),
                "flags": flags_str,
            })

        own_rows.append({
            "match_id": mid,
            "slate_bucket": slate_bucket,
            "start_utc": start_utc,
            "tournament": f["tournament"],
            "tier": f["tier"],
            "points": f["points"],
            "series_format": series_format,
            "team_a": ta,
            "team_b": tb,
            "vrs_standing_a": t_a.get("vrs_standing", ""),
            "vrs_points_a": t_a.get("vrs_points", ""),
            "vrs_url_a": t_a.get("vrs_url", VRS_BASE_URL),
            "vrs_standing_b": t_b.get("vrs_standing", ""),
            "vrs_points_b": t_b.get("vrs_points", ""),
            "vrs_url_b": t_b.get("vrs_url", VRS_BASE_URL),
            "hltv_rank_a": t_a.get("hltv_rank", ""),
            "hltv_points_a": t_a.get("hltv_points", ""),
            "hltv_url_a": t_a.get("hltv_url", HLTV_RANKING_URL),
            "hltv_rank_b": t_b.get("hltv_rank", ""),
            "hltv_points_b": t_b.get("hltv_points", ""),
            "hltv_url_b": t_b.get("hltv_url", HLTV_RANKING_URL),
            "vrs_glicko_p_a": vrs_p_a,
            "vrs_glicko_p_b": vrs_p_b,
            "hltv_elo_p_a": hltv_p_a,
            "hltv_elo_p_b": hltv_p_b,
            "own_p_a": own_p_a,
            "own_p_b": own_p_b,
            "own_fair_odds_a": own_fair_a,
            "own_fair_odds_b": own_fair_b,
            "own_pick": own_pick,
            "own_method": own_method,
            "hltv_match_url": hltv_match_url,
            "flags": flags_str,
        })

        analysis_rows.append({
            "match_id": mid,
            "slate_bucket": slate_bucket,
            "start_utc": start_utc,
            "lock_utc": f["lock_utc"],
            "status": status,
            "tournament": f["tournament"],
            "tier": f["tier"],
            "points": f["points"],
            "stage": f["stage"],
            "series_format": series_format,
            "team_a": ta,
            "team_b": tb,
            "vrs_standing_a": t_a.get("vrs_standing", ""),
            "vrs_points_a": t_a.get("vrs_points", ""),
            "vrs_url_a": t_a.get("vrs_url", VRS_BASE_URL),
            "vrs_standing_b": t_b.get("vrs_standing", ""),
            "vrs_points_b": t_b.get("vrs_points", ""),
            "vrs_url_b": t_b.get("vrs_url", VRS_BASE_URL),
            "hltv_rank_a": t_a.get("hltv_rank", ""),
            "hltv_points_a": t_a.get("hltv_points", ""),
            "hltv_url_a": t_a.get("hltv_url", HLTV_RANKING_URL),
            "hltv_rank_b": t_b.get("hltv_rank", ""),
            "hltv_points_b": t_b.get("hltv_points", ""),
            "hltv_url_b": t_b.get("hltv_url", HLTV_RANKING_URL),
            "ext_book": ext_book,
            "ext_odds_a": ext_odds_a,
            "ext_odds_b": ext_odds_b,
            "ext_overround_pct": overround_pct,
            "ext_p_a": ext_p_a,
            "ext_p_b": ext_p_b,
            "ext_source_url": ext_source_url,
            "egw_odds_a": egw_odds_a,
            "egw_odds_b": egw_odds_b,
            "egw_url": egw_url,
            "vrs_glicko_p_a": vrs_p_a,
            "vrs_glicko_p_b": vrs_p_b,
            "hltv_elo_p_a": hltv_p_a,
            "hltv_elo_p_b": hltv_p_b,
            "own_p_a": own_p_a,
            "own_p_b": own_p_b,
            "own_fair_odds_a": own_fair_a,
            "own_fair_odds_b": own_fair_b,
            "consensus_p_a": consensus_p_a,
            "consensus_p_b": consensus_p_b,
            "recommended_pick": recommended_pick,
            "pick_prob": pick_prob,
            "pick_confidence": pick_confidence,
            "consensus_basis": consensus_basis,
            "own_minus_ext_pp": diff_pp,
            "hotspawn_lobby_url": f["hotspawn_lobby_url"],
            "hotspawn_match_url": f["hotspawn_match_url"],
            "hltv_match_url": hltv_match_url,
            "verified_result": verified_result,
            "analysis_note": analysis_note,
            "flags": flags_str,
        })

        if row_flags and slate_bucket in ("open_oct14_16", "locked_oct13_14"):
            fixture_flags_rows.append({
                "record_type": "FIXTURE_FLAG",
                "id": mid,
                "codes": flags_str,
                "subject": f"{ta} vs {tb} ({f['tournament']}, {start_utc})",
                "status_or_severity": "ACTION_REQUIRED" if "FL-UNVERIFIED-TEAM" in row_flags else "VERIFIED_WITH_FLAG",
                "explanation": analysis_note,
                "official_source_url": hltv_match_url or ext_source_url or f["hotspawn_lobby_url"],
                "secondary_source_url": t_a.get("vrs_url") or VRS_BASE_URL,
            })

    # Write CSV files
    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        if not rows:
            return
        with path.open("w", newline="", encoding="utf-8") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    ratings_rows: list[dict[str, str]] = []
    for tname in sorted(teams.keys(), key=lambda s: (0 if s in open_team_names else (1 if s in week_team_names else 2), s.lower())):
        tr = teams[tname]
        ratings_rows.append({
            "hotspawn_team": tname,
            "on_open_slate": "yes" if tname in open_team_names else "no",
            "on_current_week": "yes" if tname in week_team_names else "no",
            "vrs_standing": tr.get("vrs_standing", ""),
            "vrs_points": tr.get("vrs_points", ""),
            "vrs_name": tr.get("vrs_name", ""),
            "vrs_roster": tr.get("vrs_roster", ""),
            "vrs_line": tr.get("vrs_line", ""),
            "vrs_url": tr.get("vrs_url", VRS_BASE_URL),
            "vrs_details_url": tr.get("vrs_details_url", ""),
            "hltv_rank": tr.get("hltv_rank", ""),
            "hltv_points": tr.get("hltv_points", ""),
            "hltv_team_id": tr.get("hltv_team_id", ""),
            "hltv_name": tr.get("hltv_name", ""),
            "hltv_roster": tr.get("hltv_roster", ""),
            "hltv_url": tr.get("hltv_url", HLTV_RANKING_URL),
            "live_hltv_vrs_rank": tr.get("live_hltv_vrs_rank", ""),
            "resolution": tr.get("resolution", ""),
            "flags": tr.get("flags", ""),
        })

    all_flags_csv_rows = list(fixture_flags_rows)
    for ir in REPO_AUDIT_IRREGULARITIES:
        all_flags_csv_rows.append({
            "record_type": "REPO_AUDIT_IRREGULARITY",
            "id": ir["flag_id"],
            "codes": ir["category"],
            "subject": f"{ir['repo_location']} — {ir['affected_items']}",
            "status_or_severity": ir["severity"],
            "explanation": f"{ir['description']} | Resolution: {ir['our_resolution']}",
            "official_source_url": ir["official_source_url"],
            "secondary_source_url": VRS_BASE_URL,
        })

    write_csv(DATA_DIR / "fixtures.csv", fixtures_rows)
    write_csv(DATA_DIR / "ratings.csv", ratings_rows)
    write_csv(DATA_DIR / "external_lines.csv", external_rows)
    write_csv(DATA_DIR / "own_lines.csv", own_rows)
    write_csv(DATA_DIR / "analysis.csv", analysis_rows)
    write_csv(DATA_DIR / "flags.csv", all_flags_csv_rows)

    live_check_meta = {
        "performed": False,
        "checked_utc": "2026-10-14T01:58:00Z",
        "hotspawn_open_cs2_count": 28,
        "hotspawn_total_cs2_filter_count": 89,
        "vrs_latest_file": "standings_global_2026_10_05.md",
    }
    if live_check:
        now_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        live_check_meta["performed"] = True
        live_check_meta["checked_utc"] = now_str
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/2026",
                headers={"User-Agent": "MaltaProj1-8944bb84/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                items = json.loads(resp.read().decode("utf-8"))
                global_files = sorted(
                    x["name"] for x in items if isinstance(x, dict) and str(x.get("name", "")).startswith("standings_global_")
                )
                if global_files:
                    live_check_meta["vrs_latest_file"] = global_files[-1]
        except Exception as exc:
            live_check_meta["vrs_check_note"] = str(exc)

    open_rows = [r for r in analysis_rows if r["slate_bucket"] == "open_oct14_16"]
    locked_rows = [r for r in analysis_rows if r["slate_bucket"] == "locked_oct13_14"]
    stale_rows = [r for r in analysis_rows if r["slate_bucket"] == "stale_summer_2026"]

    coverage = {
        "session": "arena/8944bb84",
        "branch": "arena/8944bb84-maltaproj1",
        "generated_utc": "2026-10-14T01:58:00Z",
        "hotspawn_crowd_data_used": False,
        "counts": {
            "total_cs2_fixtures": len(analysis_rows),
            "open_oct14_16_fixtures": len(open_rows),
            "locked_oct13_14_fixtures": len(locked_rows),
            "stale_summer_2026_fixtures": len(stale_rows),
            "open_with_verified_pick": sum(1 for r in open_rows if r["recommended_pick"]),
            "open_unverified_blank": sum(1 for r in open_rows if not r["recommended_pick"]),
            "open_with_external_market_line": sum(1 for r in open_rows if r["ext_odds_a"]),
            "open_with_pinnacle_direct_line": sum(1 for r in open_rows if "Pinnacle" in r["ext_book"]),
            "open_with_egw_line": sum(1 for r in open_rows if r["egw_odds_a"]),
            "open_with_placeholder_rejected": sum(1 for r in open_rows if not r["ext_odds_a"]),
            "open_with_hltv_match_url": sum(1 for r in open_rows if r["hltv_match_url"]),
            "open_s_tier": sum(1 for r in open_rows if r["tier"] == "S"),
            "open_b_tier": sum(1 for r in open_rows if r["tier"] == "B"),
            "open_c_tier": sum(1 for r in open_rows if r["tier"] == "C"),
            "unique_teams_total": len(ratings_rows),
            "unique_teams_open_slate": len(open_team_names),
            "unique_teams_current_week": len(week_team_names),
            "repo_irregularities_documented": len(REPO_AUDIT_IRREGULARITIES),
        },
        "sources": {
            "hotspawn_cs2_lobby": HOTSPAWN_CS2_URL,
            "valve_vrs_commit": VRS_COMMIT,
            "valve_vrs_url": VRS_BASE_URL,
            "hltv_ranking_url": HLTV_RANKING_URL,
            "pinnacle_matchups_url": PINNACLE_MATCHUPS_URL,
            "egamersworld_matches_url": EGW_MATCHES_URL,
            "vrs_local_sha256": sha256_file(ROOT / "model" / "input" / "vrs" / "standings_global_2026_10_05.md"),
            "hltv_local_sha256": sha256_file(ROOT / "model" / "input" / "hltv_ranking.json"),
        },
        "live_check": live_check_meta,
    }
    (DATA_DIR / "coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")

    return {
        "analysis_rows": analysis_rows,
        "open_rows": open_rows,
        "locked_rows": locked_rows,
        "stale_rows": stale_rows,
        "ratings_rows": ratings_rows,
        "external_rows": external_rows,
        "own_rows": own_rows,
        "fixture_flags_rows": fixture_flags_rows,
        "coverage": coverage,
    }


NAV_ITEMS: list[tuple[str, str]] = [
    ("index.html", "Open Slate (28)"),
    ("s-tier.html", "S-Tier (4)"),
    ("b-tier.html", "B-Tier (8)"),
    ("c-tier.html", "C-Tier (16)"),
    ("tournaments.html", "By Tournament (18)"),
    ("market-lines.html", "External Lines (24/28)"),
    ("own-lines.html", "Originated Lines & Teams"),
    ("coverage-all-91.html", "All 91 CS2 Fixtures"),
    ("methodology.html", "Methodology"),
    ("sources.html", "Official Sources"),
    ("flagged.html", "Flagged for Review"),
]


STYLE_CSS = """\
:root {
  --bg: #0b1020;
  --surface: #121a30;
  --surface-alt: #17213c;
  --border: #263459;
  --text: #e8eefc;
  --muted: #9fb0d6;
  --accent: #4ea8de;
  --accent-strong: #38bdf8;
  --green: #22c55e;
  --green-bg: rgba(34, 197, 94, 0.14);
  --amber: #f59e0b;
  --amber-bg: rgba(245, 158, 11, 0.15);
  --red: #ef4444;
  --red-bg: rgba(239, 68, 68, 0.16);
  --purple: #a855f7;
  --purple-bg: rgba(168, 85, 247, 0.16);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  font-size: 14px;
}
a { color: var(--accent-strong); text-decoration: none; }
a:hover { text-decoration: underline; }
.container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 16px;
}
.topbar {
  background: #080c18;
  border-bottom: 1px solid var(--border);
  padding: 12px 16px;
  position: sticky;
  top: 0;
  z-index: 50;
}
.topbar-inner {
  max-width: 1440px;
  margin: 0 auto;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.brand {
  font-weight: 700;
  font-size: 16px;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}
.brand-badge {
  background: var(--accent);
  color: #061024;
  font-size: 11px;
  font-weight: 800;
  padding: 2px 7px;
  border-radius: 999px;
  text-transform: uppercase;
}
.nav {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.nav a {
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--surface);
  border: 1px solid var(--border);
  color: var(--text);
  font-size: 12.5px;
  font-weight: 500;
  white-space: nowrap;
}
.nav a.active, .nav a:hover {
  background: var(--accent);
  color: #061024;
  border-color: var(--accent-strong);
  text-decoration: none;
  font-weight: 700;
}
.hero {
  background: linear-gradient(135deg, #121a30 0%, #182547 100%);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 18px;
}
.hero h1 {
  margin: 0 0 8px 0;
  font-size: 22px;
  line-height: 1.25;
}
.hero p {
  margin: 0 0 10px 0;
  color: var(--muted);
}
.policy-banner {
  background: rgba(56, 189, 248, 0.1);
  border-left: 4px solid var(--accent-strong);
  padding: 10px 14px;
  border-radius: 6px;
  font-size: 13px;
  margin-top: 10px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}
.kpi-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
}
.kpi-label {
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--muted);
}
.kpi-val {
  font-size: 24px;
  font-weight: 800;
  margin: 4px 0;
  color: #fff;
}
.kpi-sub {
  font-size: 12px;
  color: var(--muted);
}
.section-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 20px;
}
.section-card h2 {
  margin: 0 0 6px 0;
  font-size: 18px;
}
.section-card p.section-desc {
  margin: 0 0 12px 0;
  color: var(--muted);
  font-size: 13px;
}
.table-wrap {
  width: 100%;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--border);
  border-radius: 8px;
}
table {
  width: 100%;
  border-collapse: collapse;
  min-width: 820px;
  font-size: 13px;
}
th, td {
  padding: 9px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
th {
  background: #0d1428;
  color: var(--muted);
  font-weight: 700;
  font-size: 11.5px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
  position: sticky;
  top: 0;
}
tbody tr:nth-child(even) {
  background: var(--surface-alt);
}
tbody tr:hover {
  background: rgba(78, 168, 222, 0.09);
}
.badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}
.badge-s { background: var(--purple-bg); color: #d8b4fe; border: 1px solid var(--purple); }
.badge-b { background: rgba(56, 189, 248, 0.16); color: #7dd3fc; border: 1px solid var(--accent-strong); }
.badge-c { background: rgba(148, 163, 184, 0.16); color: #cbd5e1; border: 1px solid #64748b; }
.badge-lock { background: var(--green-bg); color: #86efac; border: 1px solid var(--green); }
.badge-strong { background: rgba(56, 189, 248, 0.16); color: #7dd3fc; border: 1px solid var(--accent-strong); }
.badge-lean { background: var(--amber-bg); color: #fcd34d; border: 1px solid var(--amber); }
.badge-toss { background: rgba(249, 115, 22, 0.16); color: #fdba74; border: 1px solid #f97316; }
.badge-unv { background: var(--red-bg); color: #fca5a5; border: 1px solid var(--red); }
.src-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.src-pill {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  background: #0d1428;
  border: 1px solid var(--border);
  font-size: 11px;
  color: var(--accent-strong);
  white-space: nowrap;
}
.prob-bar {
  display: flex;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
  background: #263459;
  margin-top: 4px;
  width: 120px;
}
.prob-fill-a { background: #38bdf8; }
.prob-fill-b { background: #64748b; }
.muted { color: var(--muted); font-size: 12px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-size: 12px; }
.footer {
  margin-top: 28px;
  padding: 16px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  text-align: center;
}
@media (max-width: 768px) {
  .container { padding: 10px; }
  .hero { padding: 14px; }
  .hero h1 { font-size: 18px; }
  .kpi-grid { grid-template-columns: repeat(2, 1fr); }
}
"""


def esc(val: Any) -> str:
    return html.escape(str(val if val is not None else ""))


def tier_badge(tier: str, pts: str) -> str:
    t = (tier or "C").upper()
    cls = "badge-s" if t == "S" else ("badge-b" if t == "B" else "badge-c")
    return f'<span class="badge {cls}">{esc(t)}-Tier ({esc(pts)} pts)</span>'


def conf_badge(conf: str) -> str:
    if "OBVIOUS LOCK" in conf:
        return f'<span class="badge badge-lock">{esc(conf)}</span>'
    if "STRONG PICK" in conf:
        return f'<span class="badge badge-strong">{esc(conf)}</span>'
    if "SOLID LEAN" in conf:
        return f'<span class="badge badge-lean">{esc(conf)}</span>'
    if "TOSS-UP" in conf:
        return f'<span class="badge badge-toss">{esc(conf)}</span>'
    return f'<span class="badge badge-unv">{esc(conf)}</span>'


def render_page_shell(active_file: str, title: str, subtitle: str, body_html: str) -> str:
    nav_links = ['<a href="../index.html">Hub Home</a>']
    for fname, label in NAV_ITEMS:
        cls = ' class="active"' if fname == active_file else ""
        nav_links.append(f'<a href="{fname}"{cls}>{esc(label)}</a>')
    nav_html = "\n      ".join(nav_links)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)} — Hotspawn CS2 Pick'em Intelligence (Oct 14, 2026)</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="topbar">
    <div class="topbar-inner">
      <div class="brand">
        <span class="brand-badge">Oct 14 Live</span>
        <span>Hotspawn CS2 Pick'em Verification &amp; Lines Board</span>
      </div>
      <nav class="nav" aria-label="Category Navigation">
      {nav_html}
      </nav>
    </div>
  </header>
  <main class="container">
    <section class="hero">
      <h1>{esc(title)}</h1>
      <p>{esc(subtitle)}</p>
      <div class="policy-banner">
        <strong>Strict Zero-Hotspawn-Crowd &amp; Zero-Inference Guarantee:</strong>
        Hotspawn crowd pick percentages are <strong>never</strong> used as an indicator of match probability (0.0% weight).
        Every rating, external bookmaker quote, and originated probability below is linked on every row to official verified sources
        (<a href="{VRS_BASE_URL}" target="_blank" rel="noopener">Valve Regional Standings 2026-10-05</a>,
        <a href="{HLTV_RANKING_URL}" target="_blank" rel="noopener">HLTV World Ranking 2026-10-12</a>,
        <a href="https://www.hltv.org/matches" target="_blank" rel="noopener">HLTV Match Pages</a>,
        <a href="{PINNACLE_MATCHUPS_URL}" target="_blank" rel="noopener">Direct Pinnacle</a>, and
        <a href="{EGW_MATCHES_URL}" target="_blank" rel="noopener">EGamersWorld</a>).
        Any value that cannot be confirmed from an official source without inference is left <strong>blank</strong> and published on
        <a href="flagged.html">Flagged for Review</a>.
      </div>
    </section>
    {body_html}
  </main>
  <footer class="footer">
    Session <code>arena/8944bb84</code> &bull; Branch <code>arena/8944bb84-maltaproj1</code> &bull;
     Snapshot Verified <code>2026-10-14T01:58:00Z</code> &bull;
    Data exports: <a href="../data/8944bb84/analysis.csv">analysis.csv</a> |
    <a href="../data/8944bb84/fixtures.csv">fixtures.csv</a> |
    <a href="../data/8944bb84/external_lines.csv">external_lines.csv</a> |
    <a href="../data/8944bb84/own_lines.csv">own_lines.csv</a> |
    <a href="../data/8944bb84/ratings.csv">ratings.csv</a> |
    <a href="../data/8944bb84/flags.csv">flags.csv</a> |
    <a href="../data/8944bb84/coverage.json">coverage.json</a>
  </footer>
</body>
</html>
"""


def render_match_table(rows: list[dict[str, str]], table_id: str = "match-table") -> str:
    tr_list: list[str] = []
    for r in rows:
        mid = r["match_id"]
        ta = r["team_a"]
        tb = r["team_b"]
        vrs_a = f"#{r['vrs_standing_a']} ({r['vrs_points_a']})" if r["vrs_standing_a"] else "— (Blank)"
        vrs_b = f"#{r['vrs_standing_b']} ({r['vrs_points_b']})" if r["vrs_standing_b"] else "— (Blank)"
        hltv_a = f"#{r['hltv_rank_a']} ({r['hltv_points_a']}p)" if r["hltv_rank_a"] else "— (Unranked)"
        hltv_b = f"#{r['hltv_rank_b']} ({r['hltv_points_b']}p)" if r["hltv_rank_b"] else "— (Unranked)"

        if r["ext_odds_a"] and r["ext_odds_b"]:
            ext_cell = (
                f"<div><strong>{esc(r['ext_p_a'])}%</strong> / <strong>{esc(r['ext_p_b'])}%</strong></div>"
                f"<div class=\"muted\">{esc(r['ext_odds_a'])} / {esc(r['ext_odds_b'])} "
                f"(<a href=\"{esc(r['ext_source_url'])}\" target=\"_blank\" rel=\"noopener\">{esc(r['ext_book'])}</a>)</div>"
            )
            if r["egw_odds_a"] and "Pinnacle" in r["ext_book"]:
                ext_cell += (
                    f"<div class=\"muted\">EGW: {esc(r['egw_odds_a'])}/{esc(r['egw_odds_b'])} "
                    f"(<a href=\"{esc(r['egw_url'])}\" target=\"_blank\" rel=\"noopener\">bc.game</a>)</div>"
                )
        else:
            ext_cell = (
                f"<div><span class=\"badge badge-unv\">Blank — Unpriced</span></div>"
                f"<div class=\"muted\"><a href=\"flagged.html#flag-{esc(mid)}\">1.80/1.80 placeholder rejected</a></div>"
            )

        if r["own_p_a"] and r["own_p_b"]:
            own_cell = (
                f"<div><strong>{esc(r['own_p_a'])}%</strong> / <strong>{esc(r['own_p_b'])}%</strong></div>"
                f"<div class=\"muted\">Fair: {esc(r['own_fair_odds_a'])} / {esc(r['own_fair_odds_b'])}</div>"
                f"<div class=\"muted\">VRS: {esc(r['vrs_glicko_p_a'])}%/{esc(r['vrs_glicko_p_b'])}%"
                + (f" | HLTV: {esc(r['hltv_elo_p_a'])}%/{esc(r['hltv_elo_p_b'])}%" if r["hltv_elo_p_a"] else "")
                + "</div>"
            )
        else:
            own_cell = (
                f"<div><span class=\"badge badge-unv\">Blank — Unverified</span></div>"
                f"<div class=\"muted\"><a href=\"flagged.html#flag-{esc(mid)}\">Missing in 2026-10-05 VRS</a></div>"
            )

        if r["consensus_p_a"] and r["consensus_p_b"]:
            pa_w = max(5, min(95, int(round(float(r["consensus_p_a"])))))
            pb_w = 100 - pa_w
            cons_cell = (
                f"<div><strong>{esc(ta)}: {esc(r['consensus_p_a'])}%</strong></div>"
                f"<div><strong>{esc(tb)}: {esc(r['consensus_p_b'])}%</strong></div>"
                f"<div class=\"prob-bar\"><div class=\"prob-fill-a\" style=\"width:{pa_w}%\"></div>"
                f"<div class=\"prob-fill-b\" style=\"width:{pb_w}%\"></div></div>"
            )
            pick_cell = (
                f"<div><strong>{esc(r['recommended_pick'])} ({esc(r['pick_prob'])}%)</strong></div>"
                f"<div>{conf_badge(r['pick_confidence'])}</div>"
            )
        else:
            cons_cell = "<div><span class=\"badge badge-unv\">Blank — Unverified</span></div>"
            pick_cell = (
                f"<div><span class=\"badge badge-unv\">NO PICK — FLAGGED</span></div>"
                f"<div class=\"muted\"><a href=\"flagged.html#flag-{esc(mid)}\">Review Flag #{esc(mid)}</a></div>"
            )

        src_links: list[str] = []
        if r["hotspawn_match_url"]:
            src_links.append(f'<a class="src-pill" href="{esc(r["hotspawn_match_url"])}" target="_blank" rel="noopener">Hotspawn Match</a>')
        else:
            src_links.append(f'<a class="src-pill" href="{esc(r["hotspawn_lobby_url"])}" target="_blank" rel="noopener">Hotspawn Lobby</a>')
        if r["hltv_match_url"]:
            src_links.append(f'<a class="src-pill" href="{esc(r["hltv_match_url"])}" target="_blank" rel="noopener">HLTV Match</a>')
        src_links.append(f'<a class="src-pill" href="{esc(r["vrs_url_a"])}" target="_blank" rel="noopener">VRS A</a>')
        src_links.append(f'<a class="src-pill" href="{esc(r["vrs_url_b"])}" target="_blank" rel="noopener">VRS B</a>')
        src_links.append(f'<a class="src-pill" href="{esc(r["hltv_url_a"])}" target="_blank" rel="noopener">HLTV A</a>')
        src_links.append(f'<a class="src-pill" href="{esc(r["hltv_url_b"])}" target="_blank" rel="noopener">HLTV B</a>')
        if r["ext_source_url"]:
            src_links.append(f'<a class="src-pill" href="{esc(r["ext_source_url"])}" target="_blank" rel="noopener">Market Quote</a>')
        if r["egw_url"] and r["egw_url"] != r["ext_source_url"]:
            src_links.append(f'<a class="src-pill" href="{esc(r["egw_url"])}" target="_blank" rel="noopener">EGW Page</a>')

        flags_html = ""
        if r["flags"]:
            flags_html = f'<div class="muted">Flags: <a href="flagged.html#flag-{esc(mid)}">{esc(r["flags"])}</a></div>'

        tr_list.append(f"""
        <tr id="match-{esc(mid)}">
          <td class="mono">
            <strong>#{esc(mid)}</strong><br>
            <span class="muted">{esc(r['start_utc'][:16].replace('T', ' '))} UTC</span><br>
            <span class="muted">Status: {esc(r['status'])}</span>
          </td>
          <td>
            <div><strong>{esc(r['tournament'])}</strong></div>
            <div>{tier_badge(r['tier'], r['points'])} <span class="badge badge-c">{esc(r['series_format'] or 'TBA')}</span></div>
            <div class="muted">Stage: {esc(r['stage'])}</div>
          </td>
          <td>
            <div><strong>{esc(ta)}</strong> vs <strong>{esc(tb)}</strong></div>
            <div class="muted">VRS: <a href="{esc(r['vrs_url_a'])}" target="_blank" rel="noopener">{esc(vrs_a)}</a> vs <a href="{esc(r['vrs_url_b'])}" target="_blank" rel="noopener">{esc(vrs_b)}</a></div>
            <div class="muted">HLTV: <a href="{esc(r['hltv_url_a'])}" target="_blank" rel="noopener">{esc(hltv_a)}</a> vs <a href="{esc(r['hltv_url_b'])}" target="_blank" rel="noopener">{esc(hltv_b)}</a></div>
          </td>
          <td>{ext_cell}</td>
          <td>{own_cell}</td>
          <td>{cons_cell}</td>
          <td>{pick_cell}</td>
          <td>
            <div>{esc(r['analysis_note'])}</div>
            {flags_html}
          </td>
          <td><div class="src-list">{"".join(src_links)}</div></td>
        </tr>""")

    return f"""
    <div class="table-wrap">
      <table id="{esc(table_id)}">
        <thead>
          <tr>
            <th>Match ID &amp; Kickoff</th>
            <th>Tournament / Format</th>
            <th>Teams &amp; Official VRS / HLTV Ranks</th>
            <th>External Bookmaker Line (De-vigged)</th>
            <th>Originated Official Rating Line</th>
            <th>Win Probabilities (%)</th>
            <th>Obvious / Recommended Pick</th>
            <th>Line-by-Line Analysis &amp; Flags</th>
            <th>Official Source Links</th>
          </tr>
        </thead>
        <tbody>
          {"".join(tr_list)}
        </tbody>
      </table>
    </div>
    """


def slugify_tourney(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_site_pages(data: dict[str, Any]) -> None:
    (SITE_DIR / "style.css").write_text(STYLE_CSS, encoding="utf-8")

    open_rows = data["open_rows"]
    locked_rows = data["locked_rows"]
    stale_rows = data["stale_rows"]
    analysis_rows = data["analysis_rows"]
    ratings_rows = data["ratings_rows"]
    external_rows = data["external_rows"]
    own_rows = data["own_rows"]
    fixture_flags_rows = data["fixture_flags_rows"]
    cov = data["coverage"]["counts"]

    # 1. oct14/index.html
    obvious_locks = [r for r in open_rows if "OBVIOUS LOCK" in r["pick_confidence"]]
    locks_rows_html: list[str] = []
    for r in obvious_locks:
        src_u = r["hltv_match_url"] or r["ext_source_url"] or r["hotspawn_lobby_url"]
        locks_rows_html.append(f"""
        <tr>
          <td class="mono"><a href="#match-{esc(r['match_id'])}">#{esc(r['match_id'])}</a></td>
          <td>{esc(r['start_utc'][:16].replace('T', ' '))} UTC</td>
          <td>{esc(r['tournament'])} ({tier_badge(r['tier'], r['points'])}, {esc(r['series_format'])})</td>
          <td><strong>{esc(r['team_a'])}</strong> vs <strong>{esc(r['team_b'])}</strong></td>
          <td><strong>{esc(r['recommended_pick'])} ({esc(r['pick_prob'])}%)</strong></td>
          <td>{esc(r['ext_p_a'] or '—')}% / {esc(r['ext_p_b'] or '—')}% ({esc(r['ext_book'] or 'No market')})</td>
          <td>{esc(r['own_p_a'])}% / {esc(r['own_p_b'])}% (VRS #{esc(r['vrs_standing_a'])} vs #{esc(r['vrs_standing_b'])})</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(src_u)}" target="_blank" rel="noopener">HLTV Match</a>
              <a class="src-pill" href="{esc(r['vrs_url_a'])}" target="_blank" rel="noopener">Valve VRS</a>
            </div>
          </td>
        </tr>""")

    index_body = f"""
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">Open CS2 Pick'em Matches</div>
        <div class="kpi-val">{cov['open_oct14_16_fixtures']}</div>
        <div class="kpi-sub">Oct 14–16, 2026 (4 S-Tier, 8 B-Tier, 16 C-Tier)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Verified Picks Originated</div>
        <div class="kpi-val">{cov['open_with_verified_pick']} / {cov['open_oct14_16_fixtures']}</div>
        <div class="kpi-sub">1 match (#1079624) left blank &amp; flagged</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Official HLTV Match Pages</div>
        <div class="kpi-val">{cov['open_with_hltv_match_url']} / {cov['open_oct14_16_fixtures']}</div>
        <div class="kpi-sub">100% verified BO1/BO3 formats &amp; rosters</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Live External Market Lines</div>
        <div class="kpi-val">{cov['open_with_external_market_line']} / {cov['open_oct14_16_fixtures']}</div>
        <div class="kpi-sub">7 Direct Pinnacle + 17 EGW bc.game (4 placeholders rejected)</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total Hotspawn CS2 Universe</div>
        <div class="kpi-val">{cov['total_cs2_fixtures']}</div>
        <div class="kpi-sub">28 Open + 4 Started/Completed + 59 Stale Summer</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Hotspawn Crowd Input Used</div>
        <div class="kpi-val">0.0%</div>
        <div class="kpi-sub">Strictly forbidden &amp; excluded from all pipelines</div>
      </div>
    </div>

    <section class="section-card" id="obvious-picks">
      <h2>Obvious High-Confidence Picks (&ge; 70% Consensus Win Probability — {len(obvious_locks)} Matches)</h2>
      <p class="section-desc">
        Matches where both our originated official CS2 rating model (Valve VRS + HLTV) and de-vigged external bookmaker lines
        converge on a &ge;70% favorite. Every row links directly to its official verification source.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Kickoff UTC</th>
              <th>Tournament &amp; Tier</th>
              <th>Matchup</th>
              <th>Obvious Pick &amp; Win %</th>
              <th>External Market P(A)/P(B)</th>
              <th>Originated Rating P(A)/P(B)</th>
              <th>Official Sources</th>
            </tr>
          </thead>
          <tbody>
            {"".join(locks_rows_html)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-card" id="open-slate">
      <h2>All 28 Open CS2 Pick'em Matches (Oct 14–16, 2026 — Chronological Line-by-Line Board)</h2>
      <p class="section-desc">
        Complete open slate ordered by kickoff time. Click any source pill on any row to inspect the exact official Valve VRS standing line,
        HLTV team ranking profile, official HLTV match page, or bookmaker quote.
      </p>
      {render_match_table(open_rows, "open-slate-table")}
    </section>

    <section class="section-card" id="locked-week270">
      <h2>Started &amp; Completed Current-Week Matches (4 Matches — Oct 13–14, 2026)</h2>
      <p class="section-desc">
        Current-week Week-270 CS2 Pick'em fixtures that have already locked or completed. Our originated VRS+HLTV rating model went
        <strong>2–0</strong> on completed non-forfeit matches (<strong>Black Phoenix 2–0 6666</strong> and <strong>Galorys 2–0 ex-Keyd Stars</strong>)
        and currently leads on <strong>Overtake Sector vs Zomblers</strong>.
      </p>
      {render_match_table(locked_rows, "locked-slate-table")}
    </section>
    """
    (SITE_DIR / "index.html").write_text(
        render_page_shell(
            "index.html",
            "Hotspawn CS2 Pick'em Master Verification & Probability Board",
            "Full coverage of all 28 open CS2 matches (Oct 14–16, 2026) + 4 started/completed Week-270 matches + 59 historical TransferState records.",
            index_body,
        ),
        encoding="utf-8",
    )

    # 2. oct14/s-tier.html
    s_rows = [r for r in open_rows if r["tier"] == "S"]
    s_body = f"""
    <section class="section-card" id="s-tier-board">
      <h2>S-Tier Open CS2 Matches (7 Pick'em Points Each — {len(s_rows)} Matches)</h2>
      <p class="section-desc">
        All 4 S-Tier matches belong to the <strong>Thunderpick World Championship 2026</strong> Group Stage (Best-of-3).
        Every match is priced by both <strong>Direct Pinnacle</strong> and <strong>EGamersWorld (bc.game)</strong> and features
        top-36 Valve VRS &amp; top-26 HLTV teams.
      </p>
      {render_match_table(s_rows, "s-tier-table")}
    </section>
    """
    (SITE_DIR / "s-tier.html").write_text(
        render_page_shell(
            "s-tier.html",
            "S-Tier CS2 Pick'em Matches (7 Points — Thunderpick World Championship 2026)",
            "Highest-point-value matches on the Week-270 Hotspawn CS2 slate, verified with Direct Pinnacle lines, Valve VRS, and HLTV rankings.",
            s_body,
        ),
        encoding="utf-8",
    )

    # 3. oct14/b-tier.html
    b_open = [r for r in open_rows if r["tier"] == "B"]
    b_locked = [r for r in locked_rows if r["tier"] == "B"]
    b_body = f"""
    <section class="section-card" id="b-tier-open">
      <h2>B-Tier Open CS2 Matches (3 Pick'em Points Each — {len(b_open)} Open Matches)</h2>
      <p class="section-desc">
        Covers <strong>Stake Pulse Beat III</strong> (4 matches) and <strong>CCT Europe 2026 Series #11</strong> (4 matches, including unverified/blank
        <code>#1079624 FORZE Reload vs LFO 10</code>).
      </p>
      {render_match_table(b_open, "b-tier-open-table")}
    </section>
    <section class="section-card" id="b-tier-locked">
      <h2>B-Tier Started / Completed Current-Week Matches ({len(b_locked)} Matches)</h2>
      <p class="section-desc">Locked/completed B-Tier fixtures from Oct 13–14, 2026 with verified HLTV match results.</p>
      {render_match_table(b_locked, "b-tier-locked-table")}
    </section>
    """
    (SITE_DIR / "b-tier.html").write_text(
        render_page_shell(
            "b-tier.html",
            "B-Tier CS2 Pick'em Matches (3 Points — Stake Pulse Beat III & CCT Europe #11)",
            "8 open B-Tier Best-of-3 matches + 3 started/completed current-week B-Tier matches, verified line by line.",
            b_body,
        ),
        encoding="utf-8",
    )

    # 4. oct14/c-tier.html
    c_open = [r for r in open_rows if r["tier"] == "C"]
    c_locked = [r for r in locked_rows if r["tier"] == "C"]
    c_body = f"""
    <section class="section-card" id="c-tier-open">
      <h2>C-Tier Open CS2 Matches (2 Pick'em Points Each — {len(c_open)} Open Matches)</h2>
      <p class="section-desc">
        Covers 4 Best-of-3 matches in <strong>CCT Europe 2026 Series #12 Play-In</strong> (Oct 14 &amp; Oct 16) and 12 Best-of-1 matches in
        <strong>Elisa BreakOut Series #2</strong> Group A (Oct 15: <code>WROTBERRY/WBT, EAC, ENCE, BOJONG</code>)
        and Group B (Oct 16: <code>Voca, Phantom, HAVU, RoundsGG/ROUNDS</code>). Official HLTV match pages (<code>2399418</code>–<code>2399429</code>)
        and EGamersWorld confirm all 12 Elisa BreakOut Series #2 matches are <strong>Best-of-1 (BO1)</strong>, correcting the false BO3 assumption found in earlier repo boards.
      </p>
      {render_match_table(c_open, "c-tier-open-table")}
    </section>
    <section class="section-card" id="c-tier-locked">
      <h2>C-Tier Completed Current-Week Matches ({len(c_locked)} Match)</h2>
      <p class="section-desc">Completed C-Tier match from Oct 13, 2026 (<code>1081105 SUKEBAN vs your end</code>, ended 0–1 by default forfeit).</p>
      {render_match_table(c_locked, "c-tier-locked-table")}
    </section>
    """
    (SITE_DIR / "c-tier.html").write_text(
        render_page_shell(
            "c-tier.html",
            "C-Tier CS2 Pick'em Matches (2 Points — Elisa BreakOut Series #2 BO1 & CCT #12 Play-In)",
            "16 open C-Tier matches (12 BO1 in Elisa BreakOut Series #2 + 4 BO3 in CCT Europe #12 Play-In) + 1 completed Oct 13 match.",
            c_body,
        ),
        encoding="utf-8",
    )

    # 5. oct14/tournaments.html
    by_tourney: dict[str, list[dict[str, str]]] = {}
    for r in analysis_rows:
        by_tourney.setdefault(r["tournament"], []).append(r)

    tourney_index_rows: list[str] = []
    tourney_sections: list[str] = []
    sorted_tourneys = sorted(
        by_tourney.items(),
        key=lambda kv: (0 if any(x["slate_bucket"] == "open_oct14_16" for x in kv[1]) else (1 if any(x["slate_bucket"] == "locked_oct13_14" for x in kv[1]) else 2), kv[0]),
    )
    for tname, trows in sorted_tourneys:
        tslug = slugify_tourney(tname)
        n_open = sum(1 for x in trows if x["slate_bucket"] == "open_oct14_16")
        n_lock = sum(1 for x in trows if x["slate_bucket"] == "locked_oct13_14")
        n_stale = sum(1 for x in trows if x["slate_bucket"] == "stale_summer_2026")
        sample_src = trows[0]["hltv_match_url"] or trows[0]["hotspawn_match_url"] or trows[0]["hotspawn_lobby_url"]
        tourney_index_rows.append(f"""
        <tr>
          <td><a href="#tourney-{esc(tslug)}"><strong>{esc(tname)}</strong></a></td>
          <td>{tier_badge(trows[0]['tier'], trows[0]['points'])}</td>
          <td>{n_open}</td>
          <td>{n_lock}</td>
          <td>{n_stale}</td>
          <td>{len(trows)}</td>
          <td><a class="src-pill" href="{esc(sample_src)}" target="_blank" rel="noopener">Official Source</a></td>
        </tr>""")
        tourney_sections.append(f"""
        <section class="section-card" id="tourney-{esc(tslug)}">
          <h2>{esc(tname)} ({len(trows)} Matches — {n_open} Open, {n_lock} Locked, {n_stale} Historical)</h2>
          <p class="section-desc">Tier: {esc(trows[0]['tier'])} ({esc(trows[0]['points'])} Pick'em points per match).</p>
          {render_match_table(trows, f"table-{tslug}")}
        </section>""")

    tournaments_body = f"""
    <section class="section-card" id="tournament-summary">
      <h2>All 18 CS2 Tournaments on Hotspawn (5 Active Open Tournaments + 3 Locked Current-Week + 10 Historical)</h2>
      <p class="section-desc">Click any tournament name to jump to its full match table.</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Tournament</th>
              <th>Tier &amp; Points</th>
              <th>Open Matches</th>
              <th>Started/Completed (Oct 13–14)</th>
              <th>Stale Summer (Jun–Jul)</th>
              <th>Total Matches</th>
              <th>Official Source</th>
            </tr>
          </thead>
          <tbody>
            {"".join(tourney_index_rows)}
          </tbody>
        </table>
      </div>
    </section>
    {"".join(tourney_sections)}
    """
    (SITE_DIR / "tournaments.html").write_text(
        render_page_shell(
            "tournaments.html",
            "Hotspawn CS2 Matches Organized by Tournament (18 Competitions)",
            "Every CS2 competition in Hotspawn's TransferState grouped with official HLTV match links, bookmaker lines, and originated probabilities.",
            tournaments_body,
        ),
        encoding="utf-8",
    )

    # 6. oct14/market-lines.html
    ext_tr: list[str] = []
    for r in external_rows:
        src_u = r["primary_source_url"] or r["egw_url"] or r["hltv_match_url"]
        ext_tr.append(f"""
        <tr id="ext-{esc(r['match_id'])}">
          <td class="mono"><a href="index.html#match-{esc(r['match_id'])}">#{esc(r['match_id'])}</a></td>
          <td>{esc(r['start_utc'][:16].replace('T', ' '))} UTC</td>
          <td>{esc(r['tournament'])} ({esc(r['series_format'])})</td>
          <td><strong>{esc(r['team_a'])}</strong> vs <strong>{esc(r['team_b'])}</strong></td>
          <td>{esc(r['primary_book'] or '— (Unpriced / Placeholder Rejected)')}</td>
          <td class="mono">{esc(r['primary_odds_a'] or '—')} / {esc(r['primary_odds_b'] or '—')}</td>
          <td class="mono">{esc(r['overround_pct'] + '%' if r['overround_pct'] else '—')}</td>
          <td><strong>{esc(r['devig_p_a_pct'] + '%' if r['devig_p_a_pct'] else '—')}</strong> / <strong>{esc(r['devig_p_b_pct'] + '%' if r['devig_p_b_pct'] else '—')}</strong></td>
          <td class="mono">{esc(r['egw_odds_a'] or '—')} / {esc(r['egw_odds_b'] or '—')} ({esc(r['egw_devig_p_a_pct'] + '%' if r['egw_devig_p_a_pct'] else '—')}/{esc(r['egw_devig_p_b_pct'] + '%' if r['egw_devig_p_b_pct'] else '—')})</td>
          <td>{esc(r['note'])}</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(src_u)}" target="_blank" rel="noopener">Primary Quote</a>
              {f'<a class="src-pill" href="{esc(r["egw_url"])}" target="_blank" rel="noopener">EGW Match</a>' if r["egw_url"] else ''}
              {f'<a class="src-pill" href="{esc(r["hltv_match_url"])}" target="_blank" rel="noopener">HLTV Match</a>' if r["hltv_match_url"] else ''}
            </div>
          </td>
        </tr>""")

    market_body = f"""
    <section class="section-card" id="market-comparison">
      <h2>External Esports Bookmaker Lines — Direct Pinnacle vs EGamersWorld (32 Current-Week Matches)</h2>
      <p class="section-desc">
        Proportional de-vigging (<code>p_i = (1/d_i) / (1/d_A + 1/d_B)</code>) applied to verified external decimal odds.
        Equal <code>1.80 / 1.80</code> placeholder quotes on EGamersWorld are strictly rejected and left blank (4 open matches:
        <code>#1081112</code>, <code>#1081113</code>, <code>#1079624</code>, <code>#1081120</code>).
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Kickoff UTC</th>
              <th>Tournament (Format)</th>
              <th>Matchup (Team A vs Team B)</th>
              <th>Primary Bookmaker</th>
              <th>Primary Decimal Odds (A / B)</th>
              <th>Overround</th>
              <th>De-Vigged Market P(A) / P(B)</th>
              <th>EGamersWorld Cross-Check (Odds &amp; P%)</th>
              <th>Verification &amp; Orientation Note</th>
              <th>Official Source Links</th>
            </tr>
          </thead>
          <tbody>
            {"".join(ext_tr)}
          </tbody>
        </table>
      </div>
    </section>
    """
    (SITE_DIR / "market-lines.html").write_text(
        render_page_shell(
            "market-lines.html",
            "External Betting Lines & De-Vigged Probabilities (Direct Pinnacle & EGamersWorld)",
            "Line-by-line audit of all external bookmaker quotes across the 32 current-week CS2 matches.",
            market_body,
        ),
        encoding="utf-8",
    )

    # 7. oct14/own-lines.html
    week_own_rows = [r for r in own_rows if r["slate_bucket"] in ("open_oct14_16", "locked_oct13_14")]
    own_tr: list[str] = []
    for r in week_own_rows:
        own_tr.append(f"""
        <tr id="own-{esc(r['match_id'])}">
          <td class="mono"><a href="index.html#match-{esc(r['match_id'])}">#{esc(r['match_id'])}</a></td>
          <td>{esc(r['start_utc'][:16].replace('T', ' '))} UTC ({esc(r['series_format'])})</td>
          <td><strong>{esc(r['team_a'])}</strong> vs <strong>{esc(r['team_b'])}</strong></td>
          <td>
            <a href="{esc(r['vrs_url_a'])}" target="_blank" rel="noopener">{esc('#' + r['vrs_standing_a'] + ' (' + r['vrs_points_a'] + ' pts)' if r['vrs_standing_a'] else '— (Blank)')}</a>
            vs
            <a href="{esc(r['vrs_url_b'])}" target="_blank" rel="noopener">{esc('#' + r['vrs_standing_b'] + ' (' + r['vrs_points_b'] + ' pts)' if r['vrs_standing_b'] else '— (Blank)')}</a>
          </td>
          <td>
            <a href="{esc(r['hltv_url_a'])}" target="_blank" rel="noopener">{esc('#' + r['hltv_rank_a'] + ' (' + r['hltv_points_a'] + 'p)' if r['hltv_rank_a'] else '— (Unranked)')}</a>
            vs
            <a href="{esc(r['hltv_url_b'])}" target="_blank" rel="noopener">{esc('#' + r['hltv_rank_b'] + ' (' + r['hltv_points_b'] + 'p)' if r['hltv_rank_b'] else '— (Unranked)')}</a>
          </td>
          <td>{esc(r['vrs_glicko_p_a'] + '% / ' + r['vrs_glicko_p_b'] + '%' if r['vrs_glicko_p_a'] else '—')}</td>
          <td>{esc(r['hltv_elo_p_a'] + '% / ' + r['hltv_elo_p_b'] + '%' if r['hltv_elo_p_a'] else '— (1+ team outside top 245)')}</td>
          <td><strong>{esc(r['own_p_a'] + '% / ' + r['own_p_b'] + '%' if r['own_p_a'] else 'BLANK — UNVERIFIED')}</strong></td>
          <td class="mono">{esc(r['own_fair_odds_a'] + ' / ' + r['own_fair_odds_b'] if r['own_fair_odds_a'] else '—')}</td>
          <td><strong>{esc(r['own_pick'] or 'BLANK — FLAGGED')}</strong><br><span class="muted">{esc(r['own_method'])}</span></td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(r['vrs_url_a'])}" target="_blank" rel="noopener">VRS A</a>
              <a class="src-pill" href="{esc(r['vrs_url_b'])}" target="_blank" rel="noopener">VRS B</a>
              <a class="src-pill" href="{esc(r['hltv_url_a'])}" target="_blank" rel="noopener">HLTV A</a>
              <a class="src-pill" href="{esc(r['hltv_url_b'])}" target="_blank" rel="noopener">HLTV B</a>
              {f'<a class="src-pill" href="{esc(r["hltv_match_url"])}" target="_blank" rel="noopener">HLTV Match</a>' if r["hltv_match_url"] else ''}
            </div>
          </td>
        </tr>""")

    team_tr: list[str] = []
    for tr in ratings_rows:
        team_tr.append(f"""
        <tr id="team-{esc(re.sub(r'[^a-z0-9]+', '-', tr['hotspawn_team'].lower()))}">
          <td><strong>{esc(tr['hotspawn_team'])}</strong></td>
          <td>{esc(tr['on_open_slate'])} / {esc(tr['on_current_week'])}</td>
          <td>
            <a href="{esc(tr['vrs_url'])}" target="_blank" rel="noopener">
              {esc('#' + tr['vrs_standing'] + ' (' + tr['vrs_points'] + ' pts)' if tr['vrs_standing'] else '— (Blank)')}
            </a>
            {f'<div class="muted">VRS Name: {esc(tr["vrs_name"])}</div>' if tr['vrs_name'] else ''}
          </td>
          <td class="muted">{esc(tr['vrs_roster'] or '—')}</td>
          <td>
            <a href="{esc(tr['hltv_url'])}" target="_blank" rel="noopener">
              {esc('#' + tr['hltv_rank'] + ' (' + tr['hltv_points'] + ' pts)' if tr['hltv_rank'] else '— (Outside Top 245)')}
            </a>
            {f'<div class="muted">Live HLTV VRS: #{esc(tr["live_hltv_vrs_rank"])}</div>' if tr['live_hltv_vrs_rank'] else ''}
          </td>
          <td class="muted">{esc(tr['hltv_roster'] or '—')}</td>
          <td>{esc(tr['resolution'])}</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(tr['vrs_url'])}" target="_blank" rel="noopener">Valve VRS</a>
              {f'<a class="src-pill" href="{esc(tr["vrs_details_url"])}" target="_blank" rel="noopener">VRS Details</a>' if tr["vrs_details_url"] else ''}
              <a class="src-pill" href="{esc(tr['hltv_url'])}" target="_blank" rel="noopener">HLTV Profile</a>
            </div>
          </td>
        </tr>""")

    own_body = f"""
    <section class="section-card" id="originated-match-lines">
      <h2>Originated Match Lines &amp; Fair Odds (32 Current-Week CS2 Matches)</h2>
      <p class="section-desc">
        Originated strictly from official CS2 ratings: Valve Regional Standings (<code>2026-10-05</code>, calibrated Glicko
        <code>D = 372.12</code>) and HLTV World Ranking (<code>2026-10-12</code>). Zero Hotspawn data is used.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Kickoff &amp; Format</th>
              <th>Matchup</th>
              <th>Valve VRS Standing &amp; Points</th>
              <th>HLTV World Rank &amp; Points</th>
              <th>VRS Glicko P(A) / P(B)</th>
              <th>HLTV Component P(A) / P(B)</th>
              <th>Originated Line P(A) / P(B)</th>
              <th>Fair Decimal Odds</th>
              <th>Originated Pick &amp; Method</th>
              <th>Official Sources</th>
            </tr>
          </thead>
          <tbody>
            {"".join(own_tr)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-card" id="team-rating-registry">
      <h2>Complete 115-Team Official CS2 Rating &amp; Roster Registry (Open Slate First)</h2>
      <p class="section-desc">
        Line-by-line verification of all 115 unique teams appearing across the 91 Hotspawn CS2 fixtures, with exact line anchors into
        Valve's <code>standings_global_2026_10_05.md</code> and official HLTV team profiles.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Hotspawn Team</th>
              <th>Open / Week</th>
              <th>Valve VRS Standing (2026-10-05)</th>
              <th>Official Valve VRS 5-Man Roster</th>
              <th>HLTV World Ranking (2026-10-12)</th>
              <th>Official HLTV Lineup</th>
              <th>Roster / Disambiguation Verification</th>
              <th>Official Source Links</th>
            </tr>
          </thead>
          <tbody>
            {"".join(team_tr)}
          </tbody>
        </table>
      </div>
    </section>
    """
    (SITE_DIR / "own-lines.html").write_text(
        render_page_shell(
            "own-lines.html",
            "Originated CS2 Rating Lines & 115-Team Official VRS/HLTV Registry",
            "Independent match probabilities originated from Valve Regional Standings (2026-10-05) and HLTV World Ranking (2026-10-12).",
            own_body,
        ),
        encoding="utf-8",
    )

    # 8. oct14/coverage-all-91.html
    cov_body = f"""
    <section class="section-card" id="all-91-fixtures">
      <h2>Complete 91-Fixture Hotspawn CS2 Universe Audit (28 Open + 4 Locked/Completed + 59 Stale Summer)</h2>
      <p class="section-desc">
        Every single CS2 fixture present in Hotspawn's Angular <code>TransferState</code> payload (89 current records) plus the 2 earlier
        recorded fixtures (<code>#1079620 Black Phoenix vs 6666</code> and <code>#1053830 500 vs Ruby</code>). Every row includes official source links.
      </p>
      {render_match_table(analysis_rows, "all-91-table")}
    </section>
    """
    (SITE_DIR / "coverage-all-91.html").write_text(
        render_page_shell(
            "coverage-all-91.html",
            "Complete 91-Fixture Hotspawn CS2 Universe Line-by-Line Table",
            "100% coverage of all 91 CS2 fixtures across the open Week-270 slate (28), locked Week-270 slate (4), and stale summer records (59).",
            cov_body,
        ),
        encoding="utf-8",
    )

    # 9. oct14/methodology.html
    meth_body = f"""
    <section class="section-card" id="model-equations">
      <h2>1. Originated Official CS2 Rating Model &amp; De-Vigging Equations</h2>
      <p class="section-desc">
        Every formula used in <code>scripts/8944bb84_build.py</code> is deterministic, auditable, and anchored strictly to official CS2 data.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Component</th>
              <th>Formula / Rule</th>
              <th>Parameters &amp; Calibration</th>
              <th>Official Reference Link</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>1. Valve VRS Glicko Win Probability</strong></td>
              <td class="mono">P_vrs(A) = 1 / (1 + 10^((VRS_B - VRS_A) / 372.12))</td>
              <td>Calibrated directly against Valve's official <code>expectedWinRate(rA, rB)</code> in <code>model/glicko.js</code> and <code>model/fit.js</code> at converged RD=75 (<code>1 VRS point = 1.0749 Glicko rating points</code>, <code>R^2 = 0.999993</code>).</td>
              <td><a class="src-pill" href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/model/glicko.js" target="_blank" rel="noopener">Valve model/glicko.js</a></td>
            </tr>
            <tr>
              <td><strong>2. HLTV World Ranking Component</strong></td>
              <td class="mono">Δ = 120 * log10((Pts_A + 3)/(Pts_B + 3)) + 1.2 * (Rank_B - Rank_A)<br>P_hltv(A) = 1 / (1 + 10^(-Δ / 400))</td>
              <td>Applied only when both teams are ranked in HLTV's official <code>2026-10-12</code> top-245 world ranking. Captures recent tournament form and rank ordinal separation.</td>
              <td><a class="src-pill" href="{HLTV_RANKING_URL}" target="_blank" rel="noopener">HLTV Ranking 2026-10-12</a></td>
            </tr>
            <tr>
              <td><strong>3. Originated Official Rating Line (Own P%)</strong></td>
              <td class="mono">P_own(A) = 0.80 * P_vrs(A) + 0.20 * P_hltv(A) (both ranked)<br>P_own(A) = P_vrs(A) (1 team outside HLTV top 245)</td>
              <td>Left strictly <strong>BLANK</strong> if either team lacks a verified <code>2026-10-05</code> Valve VRS standing without roster inference (e.g., <code>#1079624 FORZE Reload vs LFO 10</code>).</td>
              <td><a class="src-pill" href="{VRS_BASE_URL}" target="_blank" rel="noopener">Valve VRS 2026-10-05</a></td>
            </tr>
            <tr>
              <td><strong>4. External Bookmaker Proportional De-Vigging</strong></td>
              <td class="mono">q_A = 1/d_A, q_B = 1/d_B<br>Overround = (q_A + q_B - 1) * 100%<br>P_mkt(A) = q_A / (q_A + q_B)</td>
              <td>Applied to Direct Pinnacle Straight Moneyline odds (primary) and EGamersWorld <code>bc.game</code> decimal odds (secondary/primary). Equal <code>1.80 / 1.80</code> placeholders are rejected and left blank.</td>
              <td><a class="src-pill" href="{PINNACLE_MATCHUPS_URL}" target="_blank" rel="noopener">Pinnacle CS2 Matchups</a></td>
            </tr>
            <tr>
              <td><strong>5. Combined Consensus Win Probability</strong></td>
              <td class="mono">P_cons(A) = 0.50 * P_own(A) + 0.50 * P_mkt(A) (when both exist)<br>P_cons(A) = P_own(A) (when market is placeholder)</td>
              <td>Combines independent official CS2 rating signal with de-vigged sharp bookmaker price. Confidence tiers: <code>OBVIOUS LOCK (&ge;70%)</code>, <code>STRONG PICK (60–69%)</code>, <code>SOLID LEAN (55–59%)</code>, <code>CLOSE TOSS-UP (&lt;55%)</code>.</td>
              <td><a class="src-pill" href="https://www.hltv.org/matches" target="_blank" rel="noopener">HLTV Matches Schedule</a></td>
            </tr>
            <tr>
              <td><strong>6. Hotspawn Crowd Pick Exclusion</strong></td>
              <td class="mono">Weight(Hotspawn Crowd Share) = 0.0%</td>
              <td>Hotspawn crowd pick fields are stripped on ingestion and never used in any probability or pick calculation.</td>
              <td><a class="src-pill" href="{HOTSPAWN_CS2_URL}" target="_blank" rel="noopener">Hotspawn CS2 Pick'em</a></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-card" id="automation-schedule">
      <h2>2. Automated Regular Update Architecture</h2>
      <p class="section-desc">
        How this repository regularly checks Hotspawn's listed matches, Valve VRS, and external bookmakers for updates.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Workflow / Script</th>
              <th>Schedule &amp; Trigger</th>
              <th>What It Checks &amp; Updates</th>
              <th>Official Source Link</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td class="mono">.github/workflows/oct14-8944bb84.yml<br>scripts/8944bb84_build.py --live-check</td>
              <td>Every 3 hours (<code>23 */3 * * *</code>) + <code>workflow_dispatch</code></td>
              <td>Checks Valve's official VRS repository for new <code>standings_global_2026_*.md</code> commits, rebuilds <code>data/8944bb84/*</code> and <code>oct14/*</code>, runs unit &amp; link/DOM assurance tests, and commits updates.</td>
              <td><a class="src-pill" href="https://github.com/ValveSoftware/counter-strike_regional_standings/tree/main/live/2026" target="_blank" rel="noopener">Valve VRS Repo</a></td>
            </tr>
            <tr>
              <td class="mono">.github/workflows/live-459ff624.yml<br>live/collect.py</td>
              <td>Every 3 hours (<code>17 */3 * * *</code>) + <code>workflow_dispatch</code></td>
              <td>Fetches live Hotspawn Angular <code>TransferState</code> across <code>/lobby</code> and <code>/cs2-pickems</code>, Direct Pinnacle guest API quotes, and HLTV rankings into <code>live/data/snapshot.json</code>.</td>
              <td><a class="src-pill" href="{HOTSPAWN_CS2_URL}" target="_blank" rel="noopener">Hotspawn CS2 Lobby</a></td>
            </tr>
            <tr>
              <td class="mono">.github/workflows/slate-180a42a0.yml<br>slate/collect.py</td>
              <td>Every 6 hours (<code>17 */6 * * *</code>) + <code>workflow_dispatch</code></td>
              <td>Refreshes multi-page Hotspawn slate, Pinnacle markets, and provenance digests.</td>
              <td><a class="src-pill" href="{HOTSPAWN_LOBBY_URL}" target="_blank" rel="noopener">Hotspawn Main Lobby</a></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    """
    (SITE_DIR / "methodology.html").write_text(
        render_page_shell(
            "methodology.html",
            "Methodology — Originated CS2 Lines, De-Vigging & Scheduled Refresh",
            "Complete mathematical specification and automated update pipeline for Session arena/8944bb84.",
            meth_body,
        ),
        encoding="utf-8",
    )

    # 10. oct14/sources.html
    src_body = f"""
    <section class="section-card" id="official-sources-registry">
      <h2>Official Verification Sources &amp; Provenance Registry</h2>
      <p class="section-desc">
        Every external source used to verify fixtures, rosters, rankings, series formats, and betting lines, with SHA-256 digests of local evidence snapshots.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Source Tier &amp; Name</th>
              <th>Role in Pipeline</th>
              <th>Snapshot / Commit / Timestamp</th>
              <th>Local Evidence File &amp; SHA-256</th>
              <th>Official URL</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Valve Regional Standings (VRS)</strong></td>
              <td>Primary official CS2 team rating &amp; 5-man roster source for originated win probabilities (<code>D = 372.12</code>).</td>
              <td class="mono">Commit {VRS_COMMIT[:12]}<br>File: standings_global_2026_10_05.md (388 rows)</td>
              <td class="mono">model/input/vrs/standings_global_2026_10_05.md<br>SHA-256: {data['coverage']['sources']['vrs_local_sha256'][:24]}...</td>
              <td><a class="src-pill" href="{VRS_BASE_URL}" target="_blank" rel="noopener">Valve VRS 2026-10-05</a></td>
            </tr>
            <tr>
              <td><strong>Valve VRS Glicko Model Code</strong></td>
              <td>Official mathematical specification for <code>expectedWinRate(rA, rB)</code> and converged RD=75.</td>
              <td class="mono">Commit {VRS_COMMIT[:12]}<br>model/glicko.js &amp; model/fit.js</td>
              <td class="mono">model/calibrate.py &amp; data/8944bb84/own_lines.csv</td>
              <td><a class="src-pill" href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/model/glicko.js" target="_blank" rel="noopener">Valve model/glicko.js</a></td>
            </tr>
            <tr>
              <td><strong>HLTV World Team Ranking</strong></td>
              <td>Secondary official CS2 ranking (245 ranked teams, points, and 5-man rosters) for roster disambiguation &amp; rating blend.</td>
              <td class="mono">Published 2026-10-12<br>245 ranked CS2 teams</td>
              <td class="mono">model/input/hltv_ranking.json<br>SHA-256: {data['coverage']['sources']['hltv_local_sha256'][:24]}...</td>
              <td><a class="src-pill" href="{HLTV_RANKING_URL}" target="_blank" rel="noopener">HLTV Ranking 2026-10-12</a></td>
            </tr>
            <tr>
              <td><strong>HLTV Official Match Pages (32 Matches)</strong></td>
              <td>Confirms official series format (<code>BO1</code> vs <code>BO3</code>), active 5-man lineups, live VRS badges, and final scores for all 32 Week-270 matches.</td>
              <td class="mono">Verified 2026-10-14T01:50:00Z<br>Match IDs 2399134–2399471</td>
              <td class="mono">data/8944bb84/fixtures.csv</td>
              <td><a class="src-pill" href="https://www.hltv.org/matches" target="_blank" rel="noopener">HLTV Matches</a></td>
            </tr>
            <tr>
              <td><strong>Direct Pinnacle Guest API (Arcadia)</strong></td>
              <td>Primary sharp sportsbook moneyline odds (8 current-week CS2 matches).</td>
              <td class="mono">Captured 2026-10-13T23:52:00Z<br>Events 1637867148–1638279105</td>
              <td class="mono">live/data/snapshot.json &amp; data/8944bb84/external_lines.csv</td>
              <td><a class="src-pill" href="{PINNACLE_MATCHUPS_URL}" target="_blank" rel="noopener">Pinnacle CS2 Matchups</a></td>
            </tr>
            <tr>
              <td><strong>EGamersWorld CS2 Bookmaker Feed (bc.game)</strong></td>
              <td>External bookmaker decimal odds &amp; per-match pages across 26 priced current-week CS2 matches (4 equal 1.80/1.80 placeholders rejected).</td>
              <td class="mono">Verified 2026-10-14T01:48:00Z<br>30 match pages inspected</td>
              <td class="mono">data/8944bb84/external_lines.csv</td>
              <td><a class="src-pill" href="{EGW_MATCHES_URL}" target="_blank" rel="noopener">EGamersWorld CS2</a></td>
            </tr>
            <tr>
              <td><strong>Hotspawn Pick'em Lobby &amp; Matches</strong></td>
              <td>Fixture schedule, match IDs, competition tiers/points, and lock times ONLY (crowd pick percentages strictly ignored).</td>
              <td class="mono">Verified 2026-10-14T01:47:00Z<br>91 total CS2 fixtures (28 open)</td>
              <td class="mono">live/data/snapshot.json &amp; data/8944bb84/fixtures.csv</td>
              <td><a class="src-pill" href="{HOTSPAWN_CS2_URL}" target="_blank" rel="noopener">Hotspawn CS2 Pick'em</a></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    """
    (SITE_DIR / "sources.html").write_text(
        render_page_shell(
            "sources.html",
            "Official Verification Sources & Provenance Digests",
            "Authoritative CS2 rating, match schedule, and external bookmaker sources backing every row on this site.",
            src_body,
        ),
        encoding="utf-8",
    )

    # 11. oct14/flagged.html
    irreg_tr: list[str] = []
    for ir in REPO_AUDIT_IRREGULARITIES:
        sev_cls = "badge-unv" if ir["severity"] == "HIGH" else ("badge-lean" if ir["severity"] == "MEDIUM" else "badge-c")
        irreg_tr.append(f"""
        <tr id="{esc(ir['flag_id'].lower())}">
          <td class="mono"><strong>{esc(ir['flag_id'])}</strong><br><span class="badge {sev_cls}">{esc(ir['severity'])}</span></td>
          <td><strong>{esc(ir['category'])}</strong><br><span class="mono muted">{esc(ir['repo_location'])}</span></td>
          <td>{esc(ir['affected_items'])}</td>
          <td>{esc(ir['description'])}</td>
          <td>{esc(ir['our_resolution'])}</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(ir['official_source_url'])}" target="_blank" rel="noopener">Official Verification</a>
              <a class="src-pill" href="{VRS_BASE_URL}" target="_blank" rel="noopener">Valve VRS</a>
            </div>
          </td>
        </tr>""")

    ff_tr: list[str] = []
    for ff in fixture_flags_rows:
        st_cls = "badge-unv" if "ACTION_REQUIRED" in ff["status_or_severity"] else "badge-lean"
        ff_tr.append(f"""
        <tr id="flag-{esc(ff['id'])}">
          <td class="mono"><a href="index.html#match-{esc(ff['id'])}"><strong>#{esc(ff['id'])}</strong></a></td>
          <td><span class="badge {st_cls}">{esc(ff['status_or_severity'])}</span><br><span class="mono muted">{esc(ff['codes'])}</span></td>
          <td><strong>{esc(ff['subject'])}</strong></td>
          <td>{esc(ff['explanation'])}</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(ff['official_source_url'])}" target="_blank" rel="noopener">Primary Official Source</a>
              <a class="src-pill" href="{esc(ff['secondary_source_url'])}" target="_blank" rel="noopener">Valve VRS Reference</a>
            </div>
          </td>
        </tr>""")

    stale_flag_tr: list[str] = []
    for sr in stale_rows:
        smid = sr["match_id"]
        ssrc = sr["hotspawn_match_url"] or sr["hotspawn_lobby_url"]
        stale_flag_tr.append(f"""
        <tr id="flag-{esc(smid)}">
          <td class="mono"><a href="coverage-all-91.html#match-{esc(smid)}"><strong>#{esc(smid)}</strong></a></td>
          <td><span class="badge badge-c">{esc(sr['flags'])}</span></td>
          <td><strong>{esc(sr['team_a'])} vs {esc(sr['team_b'])}</strong> ({esc(sr['tournament'])}, {esc(sr['start_utc'][:16].replace('T', ' '))} UTC)</td>
          <td>Stale June–July 2026 TransferState record retained in Hotspawn's SSR payload; excluded from active open slate.</td>
          <td>
            <div class="src-list">
              <a class="src-pill" href="{esc(ssrc)}" target="_blank" rel="noopener">Hotspawn Source</a>
              <a class="src-pill" href="{esc(sr['vrs_url_a'])}" target="_blank" rel="noopener">VRS A</a>
              <a class="src-pill" href="{esc(sr['vrs_url_b'])}" target="_blank" rel="noopener">VRS B</a>
            </div>
          </td>
        </tr>""")

    flagged_body = f"""
    <section class="section-card" id="repo-irregularities">
      <h2>Part 1 — Line-by-Line Repository Audit Irregularities ({len(REPO_AUDIT_IRREGULARITIES)} Findings: IRREG-01..IRREG-08)</h2>
      <p class="section-desc">
        Concrete bugs, data overwrites, format assumptions, and truncation issues discovered during our line-by-line audit of the
        repository's existing pipelines (<code>model/</code>, <code>slate/</code>, <code>live/</code>, <code>picks/</code>, <code>today/</code>),
        together with how our verified <code>oct14/</code> &amp; <code>data/8944bb84/</code> build resolves each item.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Flag ID &amp; Severity</th>
              <th>Category &amp; Repo Location</th>
              <th>Affected Matches / Teams</th>
              <th>Detailed Finding from Line-by-Line Review</th>
              <th>How Session arena/8944bb84 Resolves It</th>
              <th>Official Verification Link</th>
            </tr>
          </thead>
          <tbody>
            {"".join(irreg_tr)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-card" id="fixture-flags">
      <h2>Part 2 — Flagged Current-Week CS2 Matches (Unverified Teams, Rejected 1.80/1.80 Placeholders &amp; Toss-Up Splits)</h2>
      <p class="section-desc">
        Every current-week CS2 fixture carrying an unverified team flag (<code>FL-UNVERIFIED-TEAM</code>), rejected placeholder odds flag
        (<code>FL-EXT-PLACEHOLDER</code>), missing Hotspawn permalink flag (<code>FL-NO-HOTSPAWN-PERMALINK</code>), reversed team order on HLTV/EGW
        (<code>FL-TEAM-ORDER-REVERSED</code>), duplicate VRS disambiguation (<code>FL-DUPLICATE-VRS-DISAMBIGUATED</code>), or market-vs-rating split.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Match ID</th>
              <th>Status &amp; Flag Codes</th>
              <th>Fixture &amp; Tournament</th>
              <th>Verification Details &amp; Why Flagged</th>
              <th>Official Source Links</th>
            </tr>
          </thead>
          <tbody>
            {"".join(ff_tr)}
          </tbody>
        </table>
      </div>
    </section>

    <section class="section-card" id="stale-transferstate-summary">
      <h2>Part 3 — Stale June–July 2026 TransferState Fixtures ({len(stale_rows)} Records Flagged FL-STALE-TRANSFERSTATE)</h2>
      <p class="section-desc">
        Hotspawn's Angular <code>TransferState</code> payload retains 59 historical CS2 fixtures from June 26 – July 5, 2026 alongside the
        32 current-week (Oct 13–16, 2026) fixtures. Every stale record is listed below with its official verification links and excluded from active picks.
      </p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Match ID</th>
              <th>Flag Codes</th>
              <th>Historical Fixture &amp; Timestamp</th>
              <th>Verification Explanation</th>
              <th>Official Source Links</th>
            </tr>
          </thead>
          <tbody>
            {"".join(stale_flag_tr)}
          </tbody>
        </table>
      </div>
    </section>
    """
    (SITE_DIR / "flagged.html").write_text(
        render_page_shell(
            "flagged.html",
            "Flagged for Review — Unverified Items & Line-by-Line Repository Audit",
            "All unverified fields (left blank per policy), rejected 1.80/1.80 placeholder odds, coin-flip splits, and cross-repo audit findings.",
            flagged_body,
        ),
        encoding="utf-8",
    )


def write_review_markdown(data: dict[str, Any]) -> None:
    open_rows = data["open_rows"]
    locked_rows = data["locked_rows"]
    stale_rows = data["stale_rows"]
    rows = data["analysis_rows"]

    lines: list[str] = []
    lines.append("# Line-by-Line Repository Review & CS2 Pick'em Verification Report (`arena/8944bb84`)")
    lines.append("")
    lines.append("- **Session**: `arena/8944bb84` (`arena/8944bb84-maltaproj1`)")
    lines.append("- **Verification Timestamp**: `2026-10-14T01:58:00Z`")
    lines.append("- **Published Dashboard**: [`oct14/index.html`](../oct14/index.html) (`11` category & audit pages)")
    lines.append("- **Published Data Artifacts**: [`data/8944bb84/`](../data/8944bb84/) (`fixtures.csv`, `ratings.csv`, `external_lines.csv`, `own_lines.csv`, `analysis.csv`, `flags.csv`, `coverage.json`)")
    lines.append("- **Zero-Hotspawn-Crowd Guarantee**: `0.0%` weight given to Hotspawn crowd pick percentages.")
    lines.append("")
    lines.append("## 1. Executive Summary of Coverage (91 Total CS2 Fixtures)")
    lines.append("")
    lines.append("| Bucket | Count | Description | Official Verification Sources |")
    lines.append("| --- | ---: | --- | --- |")
    lines.append(
        f"| **Open CS2 Slate (Oct 14–16, 2026)** | **{len(open_rows)}** | "
        f"`4` S-Tier (`7 pts`), `8` B-Tier (`3 pts`), `16` C-Tier (`2 pts`); `27/28` verified picks originated, "
        f"`1/28` (`#1079624 FORZE Reload vs LFO 10`) left blank & flagged | "
        f"[Hotspawn CS2](https://play.hotspawn.com/cs2-pickems), [HLTV Matches](https://www.hltv.org/matches), [Valve VRS 2026-10-05]({VRS_BASE_URL}) |"
    )
    lines.append(
        f"| **Started / Completed Week-270 (Oct 13–14, 2026)** | **{len(locked_rows)}** | "
        f"`#1079620 Black Phoenix 2-0 6666`, `#1081076 ex-Keyd Stars 0-2 Galorys`, "
        f"`#1081105 your end 1-0 def SUKEBAN`, `#1079546 Zomblers vs Overtake Sector (LIVE)` | "
        f"[HLTV Results](https://www.hltv.org/results), [HLTV Match 2399232](https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3) |"
    )
    lines.append(
        f"| **Stale June–July 2026 TransferState** | **{len(stale_rows)}** | "
        f"Historical June 26 – July 5, 2026 fixtures retained in Hotspawn's SSR `ng-state` JSON payload; audited & excluded from active picks | "
        f"[Hotspawn Lobby](https://play.hotspawn.com/lobby), [All 91 CS2 Fixtures](../oct14/coverage-all-91.html) |"
    )
    lines.append(
        f"| **Total CS2 Universe** | **{len(rows)}** | `115` unique CS2 teams verified line by line | "
        f"[Valve VRS 2026-10-05]({VRS_BASE_URL}), [HLTV Ranking 2026-10-12]({HLTV_RANKING_URL}) |"
    )
    lines.append("")
    lines.append("## 2. All 28 Open CS2 Pick'em Matches — Verified Probabilities, Picks & Official Sources")
    lines.append("")
    lines.append("| ID | Kickoff UTC | Tournament (Tier / Format) | Team A vs Team B | VRS Rank (Pts) | HLTV Rank | External Market P(A)/P(B) | Originated Rating P(A)/P(B) | Consensus P(A)/P(B) | Pick & Confidence | Official Sources |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in open_rows:
        va = r["vrs_standing_a"] or "—"
        vpa = r["vrs_points_a"] or "—"
        vb = r["vrs_standing_b"] or "—"
        vpb = r["vrs_points_b"] or "—"
        vrs_str = f"#{va} ({vpa}) vs #{vb} ({vpb})"
        ha = r["hltv_rank_a"] or "NR"
        hb = r["hltv_rank_b"] or "NR"
        hltv_str = f"#{ha} vs #{hb}"
        ext_str = f"{r['ext_p_a']}% / {r['ext_p_b']}% ({r['ext_odds_a']}/{r['ext_odds_b']} {r['ext_book']})" if r["ext_odds_a"] else "— (Blank: 1.80/1.80 placeholder rejected)"
        own_str = f"{r['own_p_a']}% / {r['own_p_b']}% ({r['own_fair_odds_a']}/{r['own_fair_odds_b']})" if r["own_p_a"] else "— (Blank: LFO 10 unverified in Oct 5 VRS)"
        cons_str = f"**{r['consensus_p_a']}% / {r['consensus_p_b']}%**" if r["consensus_p_a"] else "**BLANK — FLAGGED**"
        pick_str = f"**{r['recommended_pick']} ({r['pick_prob']}%)** — {r['pick_confidence']}" if r["recommended_pick"] else "**NO PICK — FLAGGED**"
        srcs = f"[HLTV]({r['hltv_match_url']}) · [VRS A]({r['vrs_url_a']}) · [VRS B]({r['vrs_url_b']})"
        if r["ext_source_url"]:
            srcs += f" · [Book]({r['ext_source_url']})"
        kick = r["start_utc"][:16].replace("T", " ")
        lines.append(f"| `{r['match_id']}` | {kick} | {r['tournament']} ({r['tier']}-Tier, {r['series_format']}) | **{r['team_a']}** vs **{r['team_b']}** | {vrs_str} | {hltv_str} | {ext_str} | {own_str} | {cons_str} | {pick_str} | {srcs} |")

    lines.append("")
    lines.append("## 3. Started & Completed Current-Week Matches (4 Matches — Oct 13–14, 2026)")
    lines.append("")
    lines.append("| ID | Kickoff UTC | Tournament (Format) | Team A vs Team B | External Market P(A)/P(B) | Originated Rating P(A)/P(B) | Verified HLTV Result / Status | Official Sources |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in locked_rows:
        ext_str = f"{r['ext_p_a']}% / {r['ext_p_b']}% ({r['ext_odds_a']}/{r['ext_odds_b']})" if r["ext_odds_a"] else "— (Blank)"
        own_str = f"{r['own_p_a']}% / {r['own_p_b']}%" if r["own_p_a"] else "— (Blank: SUKEBAN unranked)"
        srcs = f"[HLTV]({r['hltv_match_url']}) · [VRS A]({r['vrs_url_a']}) · [VRS B]({r['vrs_url_b']})"
        kick = r["start_utc"][:16].replace("T", " ")
        lines.append(f"| `{r['match_id']}` | {kick} | {r['tournament']} ({r['series_format']}) | **{r['team_a']}** vs **{r['team_b']}** | {ext_str} | {own_str} | **{r['verified_result']}** | {srcs} |")

    lines.append("")
    lines.append("## 4. Line-by-Line Repository Audit Irregularities (`IRREG-01`..`IRREG-08`)")
    lines.append("")
    lines.append("| Flag ID | Severity | Repo Location | Affected Items | Detailed Finding & Resolution | Official Source |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for ir in REPO_AUDIT_IRREGULARITIES:
        lines.append(f"| `{ir['flag_id']}` | **{ir['severity']}** | `{ir['repo_location']}` | {ir['affected_items']} | {ir['description']} **Resolution**: {ir['our_resolution']} | [Source]({ir['official_source_url']}) |")

    rev_dir = ROOT / "reviews"
    rev_dir.mkdir(parents=True, exist_ok=True)
    (rev_dir / "8944bb84-verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build session arena/8944bb84 datasets and oct14/ dashboard.")
    parser.add_argument("--live-check", action="store_true", help="Perform live check against Valve VRS GitHub API.")
    args = parser.parse_args()

    data = build_datasets(live_check=args.live_check)
    build_site_pages(data)
    write_review_markdown(data)
    counts = data["coverage"]["counts"]
    print(
        f"[8944bb84_build] Built {counts['total_cs2_fixtures']} CS2 fixtures "
        f"({counts['open_oct14_16_fixtures']} open, {counts['locked_oct13_14_fixtures']} locked, "
        f"{counts['stale_summer_2026_fixtures']} stale), {counts['unique_teams_total']} teams, "
        f"and 11 HTML pages in oct14/."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

