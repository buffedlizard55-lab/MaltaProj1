#!/usr/bin/env python3
"""
Reproducible Verification, De-Vigging, and CS2 Line Origination Engine
Session: arena/6d9c321d
Branch:  arena/6d9c321d-maltaproj1
Date:    2026-10-13 (UTC)

Generates:
  - data/6d9c321d/team_ratings_verified.csv
  - data/6d9c321d/external_bookmaker_lines.csv
  - data/6d9c321d/matches_verified.csv
  - data/6d9c321d/matches_verified.json
  - docs/verified-lines.html

Strict verification rules:
  1. Never use Hotspawn crowd pick % as an indicator of match probability.
     Hotspawn TransferState (`<script id="ng-state">`) proves each match has only
     N = 7..21 total user votes (`total_picks`).
  2. Every row links to its official verified primary sources (Hotspawn permalink,
     HLTV match page, HLTV Oct 12 World Ranking / VRS, EGamersWorld / Polymarket).
  3. If a bookmaker line cannot be confirmed from an official source (e.g. EGW
     shows its `1.80 / 1.80` default placeholder on CCT matches 1079620, 1079622,
     1079624), leave the sportsbook odds & vig-free implied probability BLANK and
     flag the row for manual review.
"""

from __future__ import annotations
import csv
import json
import math
from html import escape as _esc  # V-01 (arena/c50fb9a8): escape data strings rendered into visible HTML
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "6d9c321d"
DOCS_DIR = ROOT / "docs"

HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams/2026/october/12"
HOTSHAWN_LOBBY_URL = "https://play.hotspawn.com/lobby"

# ---------------------------------------------------------------------------
# 1. Verified Team Ratings (All 34 distinct teams across the 27 Oct fixtures)
#    Verified from HLTV World Ranking (2026-10-12, #1-#245) and official
#    HLTV match/event pages (Valve Regional Standings VRS + event-start HLTV).
# ---------------------------------------------------------------------------
TEAMS = [
    # Thunderpick World Championship 2026 (S-Tier LAN, Malta)
    {"team": "FURIA", "hltv_id": 8297, "hltv_rank": 4, "hltv_pts": 527, "vrs_rank": 7, "event_hltv_rank": 4, "star_rating_3m": 1.24, "hltv_url": "https://www.hltv.org/team/8297/furia", "source_url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026", "notes": "HLTV #4 (527 pts), VRS #7; KSCERATO 1.24 rating (past 3m)"},
    {"team": "Falcons", "hltv_id": 11283, "hltv_rank": 5, "hltv_pts": 488, "vrs_rank": 5, "event_hltv_rank": 5, "star_rating_3m": 1.29, "hltv_url": "https://www.hltv.org/team/11283/falcons", "source_url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026", "notes": "HLTV #5 (488 pts), VRS #5; m0NESY 1.29 rating (past 3m)"},
    {"team": "Aurora", "hltv_id": 11861, "hltv_rank": 6, "hltv_pts": 461, "vrs_rank": 4, "event_hltv_rank": 6, "star_rating_3m": 1.27, "hltv_url": "https://www.hltv.org/team/11861/aurora", "source_url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026", "notes": "HLTV #6 (461 pts), VRS #4; XANTARES 1.27 rating (past 3m)"},
    {"team": "Legacy", "hltv_id": 12468, "hltv_rank": 7, "hltv_pts": 379, "vrs_rank": 6, "event_hltv_rank": 7, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/12468/legacy", "source_url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026", "notes": "HLTV #7 (379 pts), VRS #6; latto 1.13 rating; bobz listed as substitute"},
    {"team": "PARIVISION", "hltv_id": 12467, "hltv_rank": 11, "hltv_pts": 178, "vrs_rank": 11, "event_hltv_rank": 11, "star_rating_3m": 1.11, "hltv_url": "https://www.hltv.org/team/12467/parivision", "source_url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026", "notes": "HLTV #11 (178 pts), VRS #11; nota 1.11 rating (past 3m)"},
    {"team": "BetBoom", "hltv_id": 12394, "hltv_rank": 14, "hltv_pts": 148, "vrs_rank": 12, "event_hltv_rank": 14, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/12394/betboom", "source_url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026", "notes": "HLTV #14 (148 pts as BETBOOM), VRS #12; ArtFr0st 1.13 rating"},
    {"team": "9z", "hltv_id": 9996, "hltv_rank": 17, "hltv_pts": 124, "vrs_rank": 15, "event_hltv_rank": 17, "star_rating_3m": 1.17, "hltv_url": "https://www.hltv.org/team/9996/9z", "source_url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026", "notes": "HLTV #17 (124 pts), VRS #15; try 1.17 rating (past 3m)"},
    {"team": "Ninjas in Pyjamas", "hltv_id": 4411, "hltv_rank": 26, "hltv_pts": 74, "vrs_rank": 16, "event_hltv_rank": 26, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/4411/ninjas-in-pyjamas", "source_url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026", "notes": "HLTV #26 (74 pts), VRS #16; r1nkle 1.13 rating (past 3m)"},

    # Stake Pulse Beat III (B-Tier LAN,Jonkoping Sweden)
    {"team": "MIBR", "hltv_id": 9215, "hltv_rank": 12, "hltv_pts": 163, "vrs_rank": 13, "event_hltv_rank": 12, "star_rating_3m": 1.24, "hltv_url": "https://www.hltv.org/team/9215/mibr", "source_url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii", "notes": "HLTV #12 (163 pts), VRS #13; kl1m 1.24 rating (past 3m)"},
    {"team": "Astralis", "hltv_id": 6665, "hltv_rank": 15, "hltv_pts": 133, "vrs_rank": 10, "event_hltv_rank": 15, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/6665/astralis", "source_url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii", "notes": "HLTV #15 (133 pts), VRS #10; Jabbi 1.13 rating (past 3m)"},
    {"team": "Envy", "hltv_id": 13913, "hltv_rank": 20, "hltv_pts": 96, "vrs_rank": 27, "event_hltv_rank": 20, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/13913/envy", "source_url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii", "notes": "HLTV #20 (96 pts), VRS #27; Maka 1.13 rating (French roster ex-3DMAX)"},
    {"team": "Heroic", "hltv_id": 7175, "hltv_rank": 30, "hltv_pts": 60, "vrs_rank": 21, "event_hltv_rank": 30, "star_rating_3m": 1.11, "hltv_url": "https://www.hltv.org/team/7175/heroic", "source_url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii", "notes": "HLTV #30 (60 pts as HEROIC), VRS #21; Brollan 1.11 rating"},
    {"team": "Fnatic", "hltv_id": 4991, "hltv_rank": 36, "hltv_pts": 43, "vrs_rank": 33, "event_hltv_rank": 36, "star_rating_3m": 1.17, "hltv_url": "https://www.hltv.org/team/4991/fnatic", "source_url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii", "notes": "HLTV #36 (43 pts as fnatic), VRS #33; jambo 1.17 rating"},
    {"team": "HOTU", "hltv_id": 11968, "hltv_rank": 41, "hltv_pts": 39, "vrs_rank": 37, "event_hltv_rank": 41, "star_rating_3m": 1.10, "hltv_url": "https://www.hltv.org/team/11968/hotu", "source_url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii", "notes": "HLTV #41 (39 pts), VRS #37; n0rb3r7 1.10 rating"},
    {"team": "BC.Game", "hltv_id": 12878, "hltv_rank": 70, "hltv_pts": 12, "vrs_rank": 46, "event_hltv_rank": 70, "star_rating_3m": 1.24, "hltv_url": "https://www.hltv.org/team/12878/bcgame", "source_url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii", "notes": "HLTV #70 (12 pts), VRS #46; s1mple 1.24 rating & electronic roster"},
    {"team": "Sashi", "hltv_id": 11681, "hltv_rank": None, "hltv_pts": None, "vrs_rank": 91, "event_hltv_rank": 132, "star_rating_3m": 1.10, "hltv_url": "https://www.hltv.org/team/11681/sashi", "source_url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii", "notes": "HLTV Unranked on Oct 12 (#132 on Event 9223 teams list), VRS #91; MistR 1.10"},

    # ESL Challenger League S52 SA & NA Cup #3 (B-Tier Online)
    {"team": "Galorys", "hltv_id": 12692, "hltv_rank": 68, "hltv_pts": 13, "vrs_rank": 82, "event_hltv_rank": 68, "star_rating_3m": 1.14, "hltv_url": "https://www.hltv.org/team/12692/galorys", "source_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3", "notes": "HLTV #68 (13 pts), VRS #82; nython 1.14 rating"},
    {"team": "ex-Keyd Stars", "hltv_id": 13922, "hltv_rank": None, "hltv_pts": None, "vrs_rank": 146, "event_hltv_rank": 148, "star_rating_3m": 1.10, "hltv_url": "https://www.hltv.org/team/13922/ex-keyd-stars", "source_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3", "notes": "HLTV Unranked on Oct 12 (#148 on Event 9385), VRS #146; cutzmeretz 1.10"},
    {"team": "Overtake Sector", "hltv_id": 13788, "hltv_rank": 143, "hltv_pts": 5, "vrs_rank": 152, "event_hltv_rank": 143, "star_rating_3m": 1.11, "hltv_url": "https://www.hltv.org/team/13788/overtake-sector", "source_url": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3", "notes": "HLTV #143 (5 pts), VRS #152; LEARSI 1.11 rating"},
    {"team": "Zomblers", "hltv_id": 12440, "hltv_rank": 197, "hltv_pts": 3, "vrs_rank": 210, "event_hltv_rank": 197, "star_rating_3m": 1.17, "hltv_url": "https://www.hltv.org/team/12440/zomblers", "source_url": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3", "notes": "HLTV #197 (3 pts), VRS #210; CoolComs 1.17 rating"},

    # CCT Europe 2026 Series #11 (B-Tier Online)
    {"team": "Black Phoenix", "hltv_id": 13924, "hltv_rank": 57, "hltv_pts": 16, "vrs_rank": 67, "event_hltv_rank": 57, "star_rating_3m": 1.09, "hltv_url": "https://www.hltv.org/team/13924/black-phoenix", "source_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11", "notes": "HLTV #57 (16 pts), VRS #67; karnez 1.09 rating"},
    {"team": "FORZE Reload", "hltv_id": 12803, "hltv_rank": 75, "hltv_pts": 11, "vrs_rank": 90, "event_hltv_rank": 75, "star_rating_3m": 1.08, "hltv_url": "https://www.hltv.org/team/12803/forze-reload", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #75 (11 pts), VRS #90 (Event 9442 seed #90)"},
    {"team": "ex-RUSTEC", "hltv_id": 13923, "hltv_rank": 79, "hltv_pts": 10, "vrs_rank": 93, "event_hltv_rank": 79, "star_rating_3m": 1.09, "hltv_url": "https://www.hltv.org/team/13923/ex-rustec", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #79 (10 pts), VRS #93 (Event 9442 seed #93); shalfey roster"},
    {"team": "6666", "hltv_id": 13882, "hltv_rank": 80, "hltv_pts": 10, "vrs_rank": 118, "event_hltv_rank": 80, "star_rating_3m": 1.12, "hltv_url": "https://www.hltv.org/team/13882/6666", "source_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11", "notes": "HLTV #80 (10 pts), VRS #118 (#120 on Event 9442); rendysky 1.12"},
    {"team": "mellren", "hltv_id": 13917, "hltv_rank": 94, "hltv_pts": 9, "vrs_rank": 123, "event_hltv_rank": 94, "star_rating_3m": 1.07, "hltv_url": "https://www.hltv.org/team/13917/mellren", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #94 (9 pts), VRS #123 (Event 9442 seed #123); lollipop21k roster"},
    {"team": "G2 Ares", "hltv_id": 12845, "hltv_rank": 103, "hltv_pts": 8, "vrs_rank": 121, "event_hltv_rank": 103, "star_rating_3m": 1.08, "hltv_url": "https://www.hltv.org/team/12845/g2-ares", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #103 (8 pts), VRS #121 (Event 9442 seed #121)"},
    {"team": "Lavked", "hltv_id": 13734, "hltv_rank": 140, "hltv_pts": 5, "vrs_rank": 144, "event_hltv_rank": 140, "star_rating_3m": 1.06, "hltv_url": "https://www.hltv.org/team/13734/lavked", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #140 (5 pts), VRS #144 (Event 9442 seed #144)"},
    {"team": "The Last Resort", "hltv_id": 13358, "hltv_rank": 159, "hltv_pts": 4, "vrs_rank": 143, "event_hltv_rank": 159, "star_rating_3m": 1.04, "hltv_url": "https://www.hltv.org/team/13358/the-last-resort", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV #159 (4 pts), VRS #143 (Event 9442 seed #143)"},
    {"team": "Gothic", "hltv_id": 13919, "hltv_rank": None, "hltv_pts": None, "vrs_rank": 169, "event_hltv_rank": 169, "star_rating_3m": 1.05, "hltv_url": "https://www.hltv.org/team/13919/gothic", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV Unranked on Oct 12 (Event 9442 seed #169), VRS #169"},
    {"team": "LFO 10", "hltv_id": 13921, "hltv_rank": None, "hltv_pts": None, "vrs_rank": 170, "event_hltv_rank": 170, "star_rating_3m": 1.04, "hltv_url": "https://www.hltv.org/team/13921/lfo-10", "source_url": "https://www.hltv.org/events/9442/cct-2026-europe-series-11", "notes": "HLTV Unranked on Oct 12 (Event 9442 seed #170), VRS #170; Jackinho/Sapec Swedish stack"},

    # Elisa BreakOut Series 2 (C-Tier LAN, Tampere Finland)
    {"team": "Voca", "hltv_id": 13499, "hltv_rank": 59, "hltv_pts": 16, "vrs_rank": 67, "event_hltv_rank": 59, "star_rating_3m": 1.18, "hltv_url": "https://www.hltv.org/team/13499/voca", "source_url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2", "notes": "HLTV #59 (16 pts), VRS #67; MarKE 1.18 rating, junior roster"},
    {"team": "Phantom", "hltv_id": 13173, "hltv_rank": 88, "hltv_pts": 9, "vrs_rank": 87, "event_hltv_rank": 88, "star_rating_3m": 1.13, "hltv_url": "https://www.hltv.org/team/13173/phantom", "source_url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2", "notes": "HLTV #88 (9 pts), VRS #87; nicoodoz 1.13 rating"},
    {"team": "WROTBERRY", "hltv_id": 13683, "hltv_rank": 109, "hltv_pts": 7, "vrs_rank": 64, "event_hltv_rank": 109, "star_rating_3m": 1.22, "hltv_url": "https://www.hltv.org/team/13683/wbt", "source_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2", "notes": "Listed on HLTV as WBT (#109, 7 pts), VRS #64; DemQQ 1.22 rating"},
    {"team": "EAC", "hltv_id": 13838, "hltv_rank": 110, "hltv_pts": 7, "vrs_rank": 115, "event_hltv_rank": 110, "star_rating_3m": 1.10, "hltv_url": "https://www.hltv.org/team/13838/eac", "source_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2", "notes": "Esport Academy Copenhagen: HLTV #110 (7 pts), VRS #115; n1Xen 1.10"},
    {"team": "ENCE", "hltv_id": 4869, "hltv_rank": 114, "hltv_pts": 7, "vrs_rank": 113, "event_hltv_rank": 114, "star_rating_3m": 1.04, "hltv_url": "https://www.hltv.org/team/4869/ence", "source_url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2", "notes": "HLTV #114 (7 pts), VRS #113; HENU 1.04 rating (Finnish roster)"},
    {"team": "HAVU", "hltv_id": 7865, "hltv_rank": 118, "hltv_pts": 7, "vrs_rank": 126, "event_hltv_rank": 118, "star_rating_3m": 1.10, "hltv_url": "https://www.hltv.org/team/7865/havu", "source_url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2", "notes": "HLTV #118 (7 pts), VRS #126; ottob 1.10 rating"},
    {"team": "BOJONG", "hltv_id": 13795, "hltv_rank": 220, "hltv_pts": 2, "vrs_rank": 387, "event_hltv_rank": 220, "star_rating_3m": 1.05, "hltv_url": "https://www.hltv.org/team/13795/bojong", "source_url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2", "notes": "HLTV #220 (2 pts), VRS #387; stunt 1.05 rating (only 11 maps in 3m)"},
    {"team": "RoundsGG", "hltv_id": 12457, "hltv_rank": 237, "hltv_pts": 1, "vrs_rank": 314, "event_hltv_rank": 237, "star_rating_3m": 1.04, "hltv_url": "https://www.hltv.org/team/12457/rounds", "source_url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2", "notes": "Listed on HLTV as ROUNDS (#237, 1 pt), VRS #314; Lapa 1.04 rating"},
]

TEAM_MAP = {t["team"]: t for t in TEAMS}

# ---------------------------------------------------------------------------
# 2. Dual-Rating CS2 Origination Model (HLTV World Rank + VRS + Star Form)
#    Explicitly zero Hotspawn crowd % input.
#    - Log-rank rating: R_rank(r) = 2000 - 300 * log10(r)
#    - Composite rank:  0.55 * R_rank(effective_hltv) + 0.45 * R_rank(vrs_rank)
#    - Form adjustment: +180 * (star_rating_3m - 1.10)
#    - Logistic win prob: P(A) = 1 / (1 + 10 ** (-(R_A - R_B) / scale))
#      where scale = 360 for BO3 (lower single-map variance) and 480 for BO1
#      (higher single-map LAN BO1 variance).
# ---------------------------------------------------------------------------
def compute_team_elo(team_name: str) -> float:
    t = TEAM_MAP[team_name]
    eff_hltv = t["hltv_rank"] if t["hltv_rank"] is not None else t["event_hltv_rank"]
    vrs = t["vrs_rank"]
    r_hltv = 2000.0 - 300.0 * math.log10(max(1, eff_hltv))
    r_vrs = 2000.0 - 300.0 * math.log10(max(1, vrs))
    r_form = 180.0 * (t["star_rating_3m"] - 1.10)
    return round(0.55 * r_hltv + 0.45 * r_vrs + r_form, 1)


def originate_match(team1: str, team2: str, fmt: str) -> dict:
    elo1 = compute_team_elo(team1)
    elo2 = compute_team_elo(team2)
    scale = 360.0 if fmt == "BO3" else 480.0
    p1 = 1.0 / (1.0 + 10.0 ** (-(elo1 - elo2) / scale))
    p1 = max(0.04, min(0.96, p1))
    p2 = 1.0 - p1
    return {
        "elo1": elo1,
        "elo2": elo2,
        "orig_prob1_pct": round(p1 * 100.0, 1),
        "orig_prob2_pct": round(p2 * 100.0, 1),
        "orig_odds1": round(1.0 / p1, 2),
        "orig_odds2": round(1.0 / p2, 2),
    }


def devig_decimal(odds1: float | None, odds2: float | None) -> tuple[float | None, float | None, float | None]:
    if not odds1 or not odds2:
        return None, None, None
    inv1 = 1.0 / odds1
    inv2 = 1.0 / odds2
    booksum = inv1 + inv2
    return (
        round((inv1 / booksum) * 100.0, 1),
        round((inv2 / booksum) * 100.0, 1),
        round(booksum * 100.0, 2),
    )


# ---------------------------------------------------------------------------
# 3. All 27 Active October 2026 Fixtures (H-00 live/hidden + H-01..H-26 SSR)
# ---------------------------------------------------------------------------
MATCHES = [
    {
        "code": "H-00",
        "hotspawn_id": "1079620",
        "dom_status": "Hidden from SSR DOM (Already LIVE at capture)",
        "utc_start": "2026-10-13 17:00 UTC",
        "edt_display": "2026-10-13 13:00 EDT",
        "tournament": "CCT Europe 2026 Series #11",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "no",
        "team1": "Black Phoenix",
        "team2": "6666",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/black-phoenix-vs-6666-cct-europe-2026-series-11-1079620",
        "hltv_url": "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld (1.80/1.80 placeholder — left blank)",
        "ext_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/black-phoenix-vs-6666-1FxyR_euv8",
        "ext_odds1": None,
        "ext_odds2": None,
        "poly_odds1": None,
        "poly_odds2": None,
        "poly_vol_usd": None,
        "status": "unverified_bookmaker",
        "flag_id": "F-28",
        "notes": "27th October fixture discovered in <script id='ng-state'> (id=1079620). Excluded from SSR DOM because match was already LIVE (Black Phoenix 1-0 after Dust2 13:4). EGW displays 1.80/1.80 placeholder; bookmaker odds left blank.",
    },
    {
        "code": "H-01",
        "hotspawn_id": "1081076",
        "dom_status": "SSR DOM #1 (Closing Soon)",
        "utc_start": "2026-10-13 21:00 UTC",
        "edt_display": "2026-10-13 17:00 EDT",
        "tournament": "ESL Challenger League S52: South America - Cup #3",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "ex-Keyd Stars",
        "team2": "Galorys",
        "hotspawn_picks": 12,
        "hotspawn_pct1": 83,
        "hotspawn_pct2": 17,
        "hotspawn_url": "https://www.hotspawn.com/matches/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3-1081076",
        "hltv_url": "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3",
        "hltv_vote1": 23.8,
        "hltv_vote2": 76.2,
        "ext_source": "EGamersWorld / Bookmaker Consensus",
        "ext_url": "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp",
        "ext_odds1": 2.43,
        "ext_odds2": 1.46,
        "poly_odds1": 3.03,
        "poly_odds2": 1.47,
        "poly_vol_usd": 3898,
        "status": "verified",
        "flag_id": "F-31",
        "notes": "Consolidation Final BO3. EGW verified odds 2.43/1.46 (bookie avg 2.508/1.464); Polymarket ($3.9K vol) 3.03/1.47; HLTV community 76.2% Galorys. Hotspawn crowd (83% ex-Keyd on N=12 picks) is completely inverted.",
    },
    {
        "code": "H-02",
        "hotspawn_id": "1079546",
        "dom_status": "SSR DOM #2 (Closing Soon)",
        "utc_start": "2026-10-14 01:00 UTC",
        "edt_display": "2026-10-13 21:00 EDT",
        "tournament": "ESL Challenger League S52: North America - Cup #3",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "Zomblers",
        "team2": "Overtake Sector",
        "hotspawn_picks": 7,
        "hotspawn_pct1": 14,
        "hotspawn_pct2": 86,
        "hotspawn_url": "https://www.hotspawn.com/matches/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3-1079546",
        "hltv_url": "https://www.hltv.org/matches/2399232/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3",
        "hltv_vote1": 28.6,
        "hltv_vote2": 71.4,
        "ext_source": "EGamersWorld / Bookmaker Consensus",
        "ext_url": "https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_",
        "ext_odds1": 2.44,
        "ext_odds2": 1.46,
        "poly_odds1": 2.94,
        "poly_odds2": 1.49,
        "poly_vol_usd": 42,
        "status": "verified",
        "flag_id": "",
        "notes": "Lower Bracket Final BO3. EGW verified match page shows 2.44/1.46 (bookie avg 2.46/1.464) and JSON-LD startDate 2026-10-14T01:00:00Z. Overtake Sector (#143 HLTV / #152 VRS) beat Zomblers (#197 HLTV / #210 VRS) 2-0 twice in past 3 months.",
    },
    {
        "code": "H-03",
        "hotspawn_id": "1079621",
        "dom_status": "SSR DOM #3 (Closing Soon)",
        "utc_start": "2026-10-14 08:00 UTC",
        "edt_display": "2026-10-14 04:00 EDT",
        "tournament": "CCT Europe 2026 Series #11",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "no",
        "team1": "Gothic",
        "team2": "Lavked",
        "hotspawn_picks": 8,
        "hotspawn_pct1": 13,
        "hotspawn_pct2": 88,
        "hotspawn_url": "https://www.hotspawn.com/matches/gothic-vs-lavked-cct-europe-2026-series-11-1079621",
        "hltv_url": "https://www.hltv.org/matches/2399298/gothic-vs-lavked-cct-2026-europe-series-11",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
        "ext_odds1": 2.10,
        "ext_odds2": 1.62,
        "poly_odds1": 1.79,
        "poly_odds2": 2.08,
        "poly_vol_usd": 3180,
        "status": "verified",
        "flag_id": "F-29",
        "notes": "EGW match page lists 2.10/1.62 favoring Lavked (bookie avg 1.999/1.688; BC.Game widget 1.881/1.782), matching HLTV #140 Lavked vs Unranked Gothic. Polymarket ($3.18K vol) leans Gothic 1.79/2.08. Hotspawn 13%+88%=101% is exact rounding of 1/8 and 7/8 votes.",
    },
    {
        "code": "H-04",
        "hotspawn_id": "1080176",
        "dom_status": "SSR DOM #4 (Closing Soon)",
        "utc_start": "2026-10-14 08:30 UTC",
        "edt_display": "2026-10-14 04:30 EDT",
        "tournament": "Thunderpick World Championship 2026",
        "tier": "S",
        "format": "BO3",
        "points": 5,
        "thp_sponsored": "yes",
        "team1": "9z",
        "team2": "Aurora",
        "hotspawn_picks": 20,
        "hotspawn_pct1": 0,
        "hotspawn_pct2": 100,
        "hotspawn_url": "https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176",
        "hltv_url": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
        "hltv_vote1": 6.8,
        "hltv_vote2": 93.2,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp",
        "ext_odds1": 3.76,
        "ext_odds2": 1.23,
        "poly_odds1": 3.85,
        "poly_odds2": 1.33,
        "poly_vol_usd": 3622,
        "status": "verified",
        "flag_id": "",
        "notes": "Group A Opening BO3 (Malta LAN). EGW 3.76/1.23; Polymarket ($3.62K vol) 3.85/1.33; HLTV Analytics Center recommends Aurora -1.5. Aurora #6 HLTV / #4 VRS vs 9z #17 HLTV / #15 VRS.",
    },
    {
        "code": "H-05",
        "hotspawn_id": "1079438",
        "dom_status": "SSR DOM #5 (Closing Soon)",
        "utc_start": "2026-10-14 10:00 UTC",
        "edt_display": "2026-10-14 06:00 EDT",
        "tournament": "Stake Pulse Beat III",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "Astralis",
        "team2": "Sashi",
        "hotspawn_picks": 21,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/astralis-vs-sashi-stake-pulse-beat-iii-1079438",
        "hltv_url": "https://www.hltv.org/matches/2399134/astralis-vs-sashi-stake-pulse-beat-iii",
        "hltv_vote1": 85.7,
        "hltv_vote2": 14.3,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z",
        "ext_odds1": 1.09,
        "ext_odds2": 6.35,
        "poly_odds1": 1.16,
        "poly_odds2": 6.67,
        "poly_vol_usd": 532,
        "status": "verified",
        "flag_id": "",
        "notes": "Upper Bracket QF BO3 (Jonkoping LAN). EGW verified match page 1.09/6.35; Polymarket ($532 vol) 1.16/6.67. Astralis #15 HLTV / #10 VRS vs Sashi Unranked (#132 Event / #91 VRS).",
    },
    {
        "code": "H-06",
        "hotspawn_id": "1079439",
        "dom_status": "SSR DOM #6 (Closing Soon)",
        "utc_start": "2026-10-14 10:00 UTC",
        "edt_display": "2026-10-14 06:00 EDT",
        "tournament": "Stake Pulse Beat III",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "HOTU",
        "team2": "Fnatic",
        "hotspawn_picks": 21,
        "hotspawn_pct1": 10,
        "hotspawn_pct2": 90,
        "hotspawn_url": "https://www.hotspawn.com/matches/hotu-vs-fnatic-stake-pulse-beat-iii-1079439",
        "hltv_url": "https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii",
        "hltv_vote1": 24.5,
        "hltv_vote2": 75.5,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC",
        "ext_odds1": 1.88,
        "ext_odds2": 1.79,
        "poly_odds1": 1.92,
        "poly_odds2": 2.00,
        "poly_vol_usd": 12210,
        "status": "verified",
        "flag_id": "F-31",
        "notes": "Upper Bracket QF BO3 (Jonkoping LAN). EGW verified match page shows near-50/50 coinflip (1.88 HOTU / 1.79 fnatic); Polymarket ($12.2K vol) has HOTU 1.92 / fnatic 2.00; HLTV ranks #41 vs #36 (VRS #37 vs #33). Hotspawn crowd 90% Fnatic (19/21 votes) is severe brand bias.",
    },
    {
        "code": "H-07",
        "hotspawn_id": "1079622",
        "dom_status": "SSR DOM #7 (Upcoming)",
        "utc_start": "2026-10-14 11:00 UTC",
        "edt_display": "2026-10-14 07:00 EDT",
        "tournament": "CCT Europe 2026 Series #11",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "no",
        "team1": "ex-RUSTEC",
        "team2": "mellren",
        "hotspawn_picks": 7,
        "hotspawn_pct1": 86,
        "hotspawn_pct2": 14,
        "hotspawn_url": "https://www.hotspawn.com/matches/ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622",
        "hltv_url": "https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGW 1.80/1.80 placeholder (blank); Polymarket $55 Vol",
        "ext_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
        "ext_odds1": None,
        "ext_odds2": None,
        "poly_odds1": 1.49,
        "poly_odds2": 2.63,
        "poly_vol_usd": 55,
        "status": "low_liquidity_only",
        "flag_id": "F-28",
        "notes": "EGW match page displays 1.80/1.80 default placeholder (sportsbook odds left blank). Polymarket has $55 volume at 1.49/2.63 (63.8%/36.2%). HLTV #79 ex-RUSTEC (VRS #93) vs #94 mellren (VRS #123).",
    },
    {
        "code": "H-08",
        "hotspawn_id": "1080177",
        "dom_status": "SSR DOM #8 (Upcoming)",
        "utc_start": "2026-10-14 11:00 UTC",
        "edt_display": "2026-10-14 07:00 EDT",
        "tournament": "Thunderpick World Championship 2026",
        "tier": "S",
        "format": "BO3",
        "points": 5,
        "thp_sponsored": "yes",
        "team1": "Falcons",
        "team2": "Ninjas in Pyjamas",
        "hotspawn_picks": 18,
        "hotspawn_pct1": 94,
        "hotspawn_pct2": 6,
        "hotspawn_url": "https://www.hotspawn.com/matches/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026-1080177",
        "hltv_url": "https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026",
        "hltv_vote1": 79.6,
        "hltv_vote2": 20.4,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp",
        "ext_odds1": 1.23,
        "ext_odds2": 3.78,
        "poly_odds1": 1.27,
        "poly_odds2": 4.35,
        "poly_vol_usd": 173,
        "status": "verified",
        "flag_id": "",
        "notes": "Group A Opening BO3 (Malta LAN). EGW 1.23/3.78; Polymarket 1.27/4.35. Falcons #5 HLTV (488 pts, VRS #5) vs NiP #26 HLTV (74 pts, VRS #16).",
    },
    {
        "code": "H-09",
        "hotspawn_id": "1080178",
        "dom_status": "SSR DOM #9 (Upcoming)",
        "utc_start": "2026-10-14 13:30 UTC",
        "edt_display": "2026-10-14 09:30 EDT",
        "tournament": "Thunderpick World Championship 2026",
        "tier": "S",
        "format": "BO3",
        "points": 5,
        "thp_sponsored": "yes",
        "team1": "Legacy",
        "team2": "PARIVISION",
        "hotspawn_picks": 17,
        "hotspawn_pct1": 88,
        "hotspawn_pct2": 12,
        "hotspawn_url": "https://www.hotspawn.com/matches/legacy-vs-parivision-thunderpick-world-championship-2026-1080178",
        "hltv_url": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026",
        "hltv_vote1": 35.8,
        "hltv_vote2": 64.2,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp",
        "ext_odds1": 1.59,
        "ext_odds2": 2.13,
        "poly_odds1": 1.72,
        "poly_odds2": 2.38,
        "poly_vol_usd": 648,
        "status": "verified",
        "flag_id": "F-32",
        "notes": "Group B Opening BO3 (Malta LAN). EGW 1.59/2.13 and Polymarket ($648 vol) 1.72/2.38 favor Legacy (#7 HLTV / #6 VRS), while HLTV community vote favors PARIVISION 64.2% because Legacy lists bobz as substitute.",
    },
    {
        "code": "H-10",
        "hotspawn_id": "1079623",
        "dom_status": "SSR DOM #10 (Upcoming)",
        "utc_start": "2026-10-14 14:00 UTC",
        "edt_display": "2026-10-14 10:00 EDT",
        "tournament": "CCT Europe 2026 Series #11",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "no",
        "team1": "G2 Ares",
        "team2": "The Last Resort",
        "hotspawn_picks": 7,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/g2-ares-vs-the-last-resort-cct-europe-2026-series-11-1079623",
        "hltv_url": "https://www.hltv.org/matches/2399300/g2-ares-vs-the-last-resort-cct-2026-europe-series-11",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
        "ext_odds1": 1.44,
        "ext_odds2": 2.39,
        "poly_odds1": None,
        "poly_odds2": None,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "",
        "notes": "EGW verified match page shows 1.44/2.39 (bookie avg 1.459/2.425; BC.Game widget 1.465/2.436). G2 Ares #103 HLTV (VRS #121) vs The Last Resort #159 HLTV (VRS #143).",
    },
    {
        "code": "H-11",
        "hotspawn_id": "1080179",
        "dom_status": "SSR DOM #11 (Upcoming)",
        "utc_start": "2026-10-14 16:00 UTC",
        "edt_display": "2026-10-14 12:00 EDT",
        "tournament": "Thunderpick World Championship 2026",
        "tier": "S",
        "format": "BO3",
        "points": 5,
        "thp_sponsored": "yes",
        "team1": "FURIA",
        "team2": "BetBoom",
        "hotspawn_picks": 17,
        "hotspawn_pct1": 94,
        "hotspawn_pct2": 6,
        "hotspawn_url": "https://www.hotspawn.com/matches/furia-vs-betboom-thunderpick-world-championship-2026-1080179",
        "hltv_url": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026",
        "hltv_vote1": 83.5,
        "hltv_vote2": 16.5,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp",
        "ext_odds1": 1.37,
        "ext_odds2": 2.75,
        "poly_odds1": 1.47,
        "poly_odds2": 3.03,
        "poly_vol_usd": 470,
        "status": "verified",
        "flag_id": "",
        "notes": "Group B Opening BO3 (Malta LAN). EGW 1.37/2.75; Polymarket ($470 vol) 1.47/3.03. FURIA #4 HLTV (527 pts, VRS #7) vs BetBoom #14 HLTV (148 pts, VRS #12).",
    },
    {
        "code": "H-12",
        "hotspawn_id": "1079624",
        "dom_status": "SSR DOM #12 (Upcoming)",
        "utc_start": "2026-10-14 17:00 UTC",
        "edt_display": "2026-10-14 13:00 EDT",
        "tournament": "CCT Europe 2026 Series #11",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "no",
        "team1": "FORZE Reload",
        "team2": "LFO 10",
        "hotspawn_picks": 7,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624",
        "hltv_url": "https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld (1.80/1.80 placeholder — left blank)",
        "ext_url": "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3",
        "ext_odds1": None,
        "ext_odds2": None,
        "poly_odds1": None,
        "poly_odds2": None,
        "poly_vol_usd": 0,
        "status": "unverified_bookmaker",
        "flag_id": "F-28",
        "notes": "EGW match page renders 'FORZE Reload VS [blank]' with 1.80/1.80 placeholder; Polymarket lists 'FORZE vs Sokerorg' (Swedish alias of Jackinho/Sapec stack). Prior session 2cb6bff4 linked a wrong 2025 Inner Circle vs FORZE Reload match on Tips.GG. Bookmaker odds left strictly blank.",
    },
    {
        "code": "H-13",
        "hotspawn_id": "1080279",
        "dom_status": "SSR DOM #13 (Upcoming)",
        "utc_start": "2026-10-15 08:00 UTC",
        "edt_display": "2026-10-15 04:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "WROTBERRY",
        "team2": "EAC",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 71,
        "hotspawn_pct2": 29,
        "hotspawn_url": "https://www.hotspawn.com/matches/wrotberry-vs-eac-elisa-breakout-series-2-1080279",
        "hltv_url": "https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
        "hltv_vote1": 71.4,
        "hltv_vote2": 28.6,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ea-copenhagen-hSC7a2mtP",
        "ext_odds1": 2.00,
        "ext_odds2": 1.72,
        "poly_odds1": 2.08,
        "poly_odds2": 1.72,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A Opening BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: WBT 2.00 vs EA Copenhagen (EAC) 1.72. WBT is #109 HLTV / #64 VRS (DemQQ 1.22 rating) vs EAC #110 HLTV / #115 VRS; our model favors WBT 59.0% vs market 46.2%.",
    },
    {
        "code": "H-14",
        "hotspawn_id": "1079440",
        "dom_status": "SSR DOM #14 (Upcoming)",
        "utc_start": "2026-10-15 10:00 UTC",
        "edt_display": "2026-10-15 06:00 EDT",
        "tournament": "Stake Pulse Beat III",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "MIBR",
        "team2": "BC.Game",
        "hotspawn_picks": 19,
        "hotspawn_pct1": 32,
        "hotspawn_pct2": 68,
        "hotspawn_url": "https://www.hotspawn.com/matches/mibr-vs-bc-game-stake-pulse-beat-iii-1079440",
        "hltv_url": "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii",
        "hltv_vote1": 20.7,
        "hltv_vote2": 79.3,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX",
        "ext_odds1": 1.64,
        "ext_odds2": 2.08,
        "poly_odds1": 2.17,
        "poly_odds2": 1.82,
        "poly_vol_usd": 203,
        "status": "verified",
        "flag_id": "F-33",
        "notes": "Upper Bracket QF BO3 (Jonkoping LAN). EGW verified match page prices MIBR 1.64 favorite vs BC.Game 2.08 (bookie avg 1.547/2.238), aligning with MIBR #12 HLTV / #13 VRS vs BC.Game #70 HLTV / #46 VRS. Public vote (79.3% HLTV / 68% Hotspawn) and thin Polymarket ($203 vol) back BC.Game due to s1mple & electronic star power.",
    },
    {
        "code": "H-15",
        "hotspawn_id": "1079442",
        "dom_status": "SSR DOM #15 (Upcoming)",
        "utc_start": "2026-10-15 10:00 UTC",
        "edt_display": "2026-10-15 06:00 EDT",
        "tournament": "Stake Pulse Beat III",
        "tier": "B",
        "format": "BO3",
        "points": 3,
        "thp_sponsored": "yes",
        "team1": "Heroic",
        "team2": "Envy",
        "hotspawn_picks": 19,
        "hotspawn_pct1": 95,
        "hotspawn_pct2": 5,
        "hotspawn_url": "https://www.hotspawn.com/matches/heroic-vs-envy-stake-pulse-beat-iii-1079442",
        "hltv_url": "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii",
        "hltv_vote1": 41.7,
        "hltv_vote2": 58.3,
        "ext_source": "EGamersWorld / Polymarket",
        "ext_url": "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC",
        "ext_odds1": 1.50,
        "ext_odds2": 2.55,
        "poly_odds1": 1.49,
        "poly_odds2": 2.94,
        "poly_vol_usd": 36,
        "status": "verified",
        "flag_id": "F-34",
        "notes": "Upper Bracket QF BO3 (Jonkoping LAN). EGW verified match page (heroic-vs-team-envy-NcCqzpPZdC; fixing truncated URL in main) shows 1.50/2.55 (bookie avg 1.484/2.502). HLTV ranks Envy #20 (VRS #27) vs HEROIC #30 (VRS #21), creating a true rank split: HLTV favors Envy while VRS & bookmakers favor Heroic.",
    },
    {
        "code": "H-16",
        "hotspawn_id": "1080280",
        "dom_status": "SSR DOM #16 (Upcoming)",
        "utc_start": "2026-10-15 10:00 UTC",
        "edt_display": "2026-10-15 06:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "yes",
        "team1": "ENCE",
        "team2": "BOJONG",
        "hotspawn_picks": 16,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/ence-vs-bojong-elisa-breakout-series-2-1080280",
        "hltv_url": "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ence-vs-bojong-qV78OzvXFg",
        "ext_odds1": 1.30,
        "ext_odds2": 3.20,
        "poly_odds1": 1.27,
        "poly_odds2": 3.45,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: ENCE 1.30 vs BOJONG 3.20. ENCE #114 HLTV / #113 VRS vs BOJONG #220 HLTV / #387 VRS.",
    },
    {
        "code": "H-17",
        "hotspawn_id": "1080281",
        "dom_status": "SSR DOM #17 (Upcoming)",
        "utc_start": "2026-10-15 12:00 UTC",
        "edt_display": "2026-10-15 08:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "WROTBERRY",
        "team2": "ENCE",
        "hotspawn_picks": 16,
        "hotspawn_pct1": 31,
        "hotspawn_pct2": 69,
        "hotspawn_url": "https://www.hotspawn.com/matches/wrotberry-vs-ence-elisa-breakout-series-2-1080281",
        "hltv_url": "https://www.hltv.org/matches/2399420/wbt-vs-ence-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-ence-GQ0xieRgQS",
        "ext_odds1": 1.62,
        "ext_odds2": 2.15,
        "poly_odds1": 2.08,
        "poly_odds2": 1.61,
        "poly_vol_usd": 19,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: WBT 1.62 favorite vs ENCE 2.15 (57.0% vs 43.0% no-vig), matching WBT #109 HLTV / #64 VRS vs ENCE #114 HLTV / #113 VRS. Hotspawn crowd (69% ENCE) and $19 Polymarket quote back ENCE on org name recognition.",
    },
    {
        "code": "H-18",
        "hotspawn_id": "1080282",
        "dom_status": "SSR DOM #18 (Upcoming)",
        "utc_start": "2026-10-15 14:00 UTC",
        "edt_display": "2026-10-15 10:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "EAC",
        "team2": "BOJONG",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/eac-vs-bojong-elisa-breakout-series-2-1080282",
        "hltv_url": "https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-bojong-vBsvfnHU5",
        "ext_odds1": 1.20,
        "ext_odds2": 4.00,
        "poly_odds1": 1.18,
        "poly_odds2": 2.17,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: EA Copenhagen (EAC) 1.20 vs BOJONG 4.00 (76.9%/23.1% no-vig, 108.3% booksum), replacing the broken $0-vol Polymarket orderbook (1.18/2.17 = 130.8% sum).",
    },
    {
        "code": "H-19",
        "hotspawn_id": "1080283",
        "dom_status": "SSR DOM #19 (Upcoming)",
        "utc_start": "2026-10-15 16:00 UTC",
        "edt_display": "2026-10-15 12:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "WROTBERRY",
        "team2": "BOJONG",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 93,
        "hotspawn_pct2": 7,
        "hotspawn_url": "https://www.hotspawn.com/matches/wrotberry-vs-bojong-elisa-breakout-series-2-1080283",
        "hltv_url": "https://www.hltv.org/matches/2399422/wbt-vs-bojong-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6",
        "ext_odds1": 1.19,
        "ext_odds2": 4.14,
        "poly_odds1": 1.18,
        "poly_odds2": 4.17,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: WBT 1.19 vs BOJONG 4.14 (77.7%/22.3% no-vig). WBT #109 HLTV / #64 VRS vs BOJONG #220 HLTV / #387 VRS.",
    },
    {
        "code": "H-20",
        "hotspawn_id": "1080284",
        "dom_status": "SSR DOM #20 (Upcoming)",
        "utc_start": "2026-10-15 18:00 UTC",
        "edt_display": "2026-10-15 14:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "EAC",
        "team2": "ENCE",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 29,
        "hotspawn_pct2": 71,
        "hotspawn_url": "https://www.hotspawn.com/matches/eac-vs-ence-elisa-breakout-series-2-1080284",
        "hltv_url": "https://www.hltv.org/matches/2399423/eac-vs-ence-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/ea-copenhagen-vs-ence-kTR_sMK3PT",
        "ext_odds1": 1.51,
        "ext_odds2": 2.35,
        "poly_odds1": 1.41,
        "poly_odds2": 2.17,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group A BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: EA Copenhagen (EAC) 1.51 vs ENCE 2.35 (60.9%/39.1% no-vig). EAC (#110 HLTV / #115 VRS, 88 maps in 3m) favored by bookmakers over ENCE (#114 HLTV / #113 VRS); Hotspawn crowd 71% ENCE.",
    },
    {
        "code": "H-21",
        "hotspawn_id": "1080285",
        "dom_status": "SSR DOM #21 (Upcoming)",
        "utc_start": "2026-10-16 08:00 UTC",
        "edt_display": "2026-10-16 04:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "yes",
        "team1": "Voca",
        "team2": "Phantom",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 21,
        "hotspawn_pct2": 79,
        "hotspawn_url": "https://www.hotspawn.com/matches/voca-vs-phantom-elisa-breakout-series-2-1080285",
        "hltv_url": "https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2",
        "hltv_vote1": 73.3,
        "hltv_vote2": 26.7,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-phantom-esports-zby52fbAja",
        "ext_odds1": 1.90,
        "ext_odds2": 1.81,
        "poly_odds1": 2.13,
        "poly_odds2": 1.03,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group B BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: Voca 1.90 vs Phantom Esports 1.81 (48.8%/51.2% no-vig), resolving the broken $0-vol Polymarket orderbook (2.13/1.03 = 144.0% sum). Voca is #59 HLTV / #67 VRS (HLTV community 73.3% Voca) vs European Phantom #88 HLTV / #87 VRS.",
    },
    {
        "code": "H-22",
        "hotspawn_id": "1080286",
        "dom_status": "SSR DOM #22 (Upcoming)",
        "utc_start": "2026-10-16 10:00 UTC",
        "edt_display": "2026-10-16 06:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "HAVU",
        "team2": "RoundsGG",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/havu-vs-roundsgg-elisa-breakout-series-2-1080286",
        "hltv_url": "https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
        "ext_odds1": 1.23,
        "ext_odds2": 3.71,
        "poly_odds1": 1.22,
        "poly_odds2": 3.85,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group B BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: HAVU 1.23 vs Rounds 3.71 (75.1%/24.9% no-vig). HAVU #118 HLTV / #126 VRS vs ROUNDS #237 HLTV / #314 VRS.",
    },
    {
        "code": "H-23",
        "hotspawn_id": "1080287",
        "dom_status": "SSR DOM #23 (Upcoming)",
        "utc_start": "2026-10-16 12:00 UTC",
        "edt_display": "2026-10-16 08:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "yes",
        "team1": "Voca",
        "team2": "HAVU",
        "hotspawn_picks": 13,
        "hotspawn_pct1": 69,
        "hotspawn_pct2": 31,
        "hotspawn_url": "https://www.hotspawn.com/matches/voca-vs-havu-elisa-breakout-series-2-1080287",
        "hltv_url": "https://www.hltv.org/matches/2399426/voca-vs-havu-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-havu-nQn6IrZXP",
        "ext_odds1": 1.38,
        "ext_odds2": 2.79,
        "poly_odds1": 1.41,
        "poly_odds2": 2.70,
        "poly_vol_usd": 3,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group B BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: Voca 1.38 vs HAVU 2.79 (66.9%/33.1% no-vig). Voca #59 HLTV / #67 VRS vs HAVU #118 HLTV / #126 VRS.",
    },
    {
        "code": "H-24",
        "hotspawn_id": "1080288",
        "dom_status": "SSR DOM #24 (Upcoming)",
        "utc_start": "2026-10-16 14:00 UTC",
        "edt_display": "2026-10-16 10:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "Phantom",
        "team2": "RoundsGG",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/phantom-vs-roundsgg-elisa-breakout-series-2-1080288",
        "hltv_url": "https://www.hltv.org/matches/2399427/phantom-vs-rounds-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU",
        "ext_odds1": 1.08,
        "ext_odds2": 6.30,
        "poly_odds1": 1.08,
        "poly_odds2": 2.17,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group B BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: Phantom Esports 1.08 vs Rounds 6.30 (85.4%/14.6% no-vig), resolving the broken $0-vol Polymarket orderbook (1.08/2.17 = 138.7% sum).",
    },
    {
        "code": "H-25",
        "hotspawn_id": "1080289",
        "dom_status": "SSR DOM #25 (Upcoming)",
        "utc_start": "2026-10-16 16:00 UTC",
        "edt_display": "2026-10-16 12:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "no",
        "team1": "RoundsGG",
        "team2": "Voca",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 0,
        "hotspawn_pct2": 100,
        "hotspawn_url": "https://www.hotspawn.com/matches/roundsgg-vs-voca-elisa-breakout-series-2-1080289",
        "hltv_url": "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U",
        "ext_odds1": 6.00,
        "ext_odds2": 1.09,
        "poly_odds1": 2.13,
        "poly_odds2": 1.10,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-35",
        "notes": "Group B BO1 (Tampere LAN). Note side order: Hotspawn lists RoundsGG (team1) vs Voca (team2), whereas HLTV (2399428) and EGW list Voca first (1.09) vs Rounds second (6.00). Aligned to Hotspawn order: RoundsGG 6.00 / Voca 1.09 (15.4%/84.6% no-vig).",
    },
    {
        "code": "H-26",
        "hotspawn_id": "1080290",
        "dom_status": "SSR DOM #26 (Upcoming)",
        "utc_start": "2026-10-16 18:00 UTC",
        "edt_display": "2026-10-16 14:00 EDT",
        "tournament": "Elisa BreakOut Series #2",
        "tier": "C",
        "format": "BO1",
        "points": 2,
        "thp_sponsored": "yes",
        "team1": "Phantom",
        "team2": "HAVU",
        "hotspawn_picks": 14,
        "hotspawn_pct1": 100,
        "hotspawn_pct2": 0,
        "hotspawn_url": "https://www.hotspawn.com/matches/phantom-vs-havu-elisa-breakout-series-2-1080290",
        "hltv_url": "https://www.hltv.org/matches/2399429/phantom-vs-havu-elisa-breakout-series-2",
        "hltv_vote1": None,
        "hltv_vote2": None,
        "ext_source": "EGamersWorld / BC.Game",
        "ext_url": "https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586",
        "ext_odds1": 1.37,
        "ext_odds2": 2.84,
        "poly_odds1": 1.35,
        "poly_odds2": 2.94,
        "poly_vol_usd": 0,
        "status": "verified",
        "flag_id": "F-30",
        "notes": "Group B BO1 (Tampere LAN). Verified on EGW Elisa BreakOut Series 2 event page: Phantom Esports 1.37 vs HAVU 2.84 (67.5%/32.5% no-vig). Phantom #88 HLTV / #87 VRS vs HAVU #118 HLTV / #126 VRS.",
    },
]


def build_datasets():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Write team_ratings_verified.csv
    team_rows = []
    for t in TEAMS:
        elo = compute_team_elo(t["team"])
        team_rows.append({
            "team": t["team"],
            "hltv_id": t["hltv_id"],
            "hltv_rank_2026_10_12": t["hltv_rank"] if t["hltv_rank"] is not None else "",
            "hltv_points": t["hltv_pts"] if t["hltv_pts"] is not None else "",
            "event_hltv_seed": t["event_hltv_rank"],
            "vrs_rank": t["vrs_rank"],
            "star_rating_3m": t["star_rating_3m"],
            "composite_elo": elo,
            "hltv_team_url": t["hltv_url"],
            "hltv_ranking_url": HLTV_RANKING_URL,
            "verification_source_url": t["source_url"],
            "notes": t["notes"],
        })
    with open(DATA_DIR / "team_ratings_verified.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(team_rows[0].keys()))
        w.writeheader()
        w.writerows(team_rows)

    # 2. Enrich matches & write external_bookmaker_lines.csv + matches_verified.csv/json
    ext_rows = []
    master_rows = []
    for m in MATCHES:
        t1 = TEAM_MAP[m["team1"]]
        t2 = TEAM_MAP[m["team2"]]
        orig = originate_match(m["team1"], m["team2"], m["format"])
        ext_p1, ext_p2, booksum = devig_decimal(m["ext_odds1"], m["ext_odds2"])
        poly_p1, poly_p2, poly_sum = devig_decimal(m["poly_odds1"], m["poly_odds2"])

        edge1 = round(orig["orig_prob1_pct"] - ext_p1, 1) if ext_p1 is not None else None
        edge2 = round(orig["orig_prob2_pct"] - ext_p2, 1) if ext_p2 is not None else None

        # Pick recommendation based purely on originated model + verified external market
        if ext_p1 is not None:
            blend_p1 = round(0.55 * ext_p1 + 0.45 * orig["orig_prob1_pct"], 1)
        elif poly_p1 is not None and (m["poly_vol_usd"] or 0) >= 50:
            blend_p1 = round(0.40 * poly_p1 + 0.60 * orig["orig_prob1_pct"], 1)
        else:
            blend_p1 = orig["orig_prob1_pct"]
        blend_p2 = round(100.0 - blend_p1, 1)

        if blend_p1 >= 50.0:
            pick_team = m["team1"]
            pick_prob = blend_p1
        else:
            pick_team = m["team2"]
            pick_prob = blend_p2

        if ext_p1 is not None and ((ext_p1 >= 55 and orig["orig_prob1_pct"] >= 55) or (ext_p2 >= 55 and orig["orig_prob2_pct"] >= 55)):
            pick_tier = "Strong Consensus Pick"
        elif ext_p1 is not None:
            pick_tier = "Market + Model Split / Edge"
        else:
            pick_tier = "Model-Only (Bookmaker Unverified)"

        ext_rows.append({
            "code": m["code"],
            "hotspawn_id": m["hotspawn_id"],
            "utc_start": m["utc_start"],
            "tournament": m["tournament"],
            "tier": m["tier"],
            "format": m["format"],
            "team1": m["team1"],
            "team2": m["team2"],
            "bookmaker_source": m["ext_source"],
            "bookmaker_odds1": m["ext_odds1"] if m["ext_odds1"] is not None else "",
            "bookmaker_odds2": m["ext_odds2"] if m["ext_odds2"] is not None else "",
            "bookmaker_overround_pct": booksum if booksum is not None else "",
            "bookmaker_novig_prob1_pct": ext_p1 if ext_p1 is not None else "",
            "bookmaker_novig_prob2_pct": ext_p2 if ext_p2 is not None else "",
            "bookmaker_source_url": m["ext_url"],
            "polymarket_odds1": m["poly_odds1"] if m["poly_odds1"] is not None else "",
            "polymarket_odds2": m["poly_odds2"] if m["poly_odds2"] is not None else "",
            "polymarket_vol_usd": m["poly_vol_usd"] if m["poly_vol_usd"] is not None else "",
            "polymarket_booksum_pct": poly_sum if poly_sum is not None else "",
            "hltv_community_pct1": m["hltv_vote1"] if m["hltv_vote1"] is not None else "",
            "hltv_community_pct2": m["hltv_vote2"] if m["hltv_vote2"] is not None else "",
            "hltv_match_url": m["hltv_url"],
            "status": m["status"],
            "flag_id": m["flag_id"],
        })

        master_rows.append({
            "code": m["code"],
            "hotspawn_id": m["hotspawn_id"],
            "dom_status": m["dom_status"],
            "utc_start": m["utc_start"],
            "edt_display": m["edt_display"],
            "tournament": m["tournament"],
            "tier": m["tier"],
            "format": m["format"],
            "points": m["points"],
            "thp_sponsored": m["thp_sponsored"],
            "team1": m["team1"],
            "team2": m["team2"],
            "team1_hltv_rank": t1["hltv_rank"] if t1["hltv_rank"] is not None else f"Unranked (#{t1['event_hltv_rank']} event)",
            "team2_hltv_rank": t2["hltv_rank"] if t2["hltv_rank"] is not None else f"Unranked (#{t2['event_hltv_rank']} event)",
            "team1_vrs_rank": t1["vrs_rank"],
            "team2_vrs_rank": t2["vrs_rank"],
            "team1_elo": orig["elo1"],
            "team2_elo": orig["elo2"],
            "ext_source": m["ext_source"],
            "ext_odds1": m["ext_odds1"] if m["ext_odds1"] is not None else "",
            "ext_odds2": m["ext_odds2"] if m["ext_odds2"] is not None else "",
            "ext_overround_pct": booksum if booksum is not None else "",
            "ext_prob1_pct": ext_p1 if ext_p1 is not None else "",
            "ext_prob2_pct": ext_p2 if ext_p2 is not None else "",
            "orig_prob1_pct": orig["orig_prob1_pct"],
            "orig_prob2_pct": orig["orig_prob2_pct"],
            "orig_odds1": orig["orig_odds1"],
            "orig_odds2": orig["orig_odds2"],
            "model_vs_market_edge1_pct": edge1 if edge1 is not None else "",
            "recommended_pick": pick_team,
            "recommended_prob_pct": pick_prob,
            "pick_classification": pick_tier,
            "hotspawn_total_picks_n": m["hotspawn_picks"],
            "hotspawn_crowd_pct1_audit_only": m["hotspawn_pct1"],
            "hotspawn_crowd_pct2_audit_only": m["hotspawn_pct2"],
            "hotspawn_url": m["hotspawn_url"],
            "hltv_url": m["hltv_url"],
            "ext_url": m["ext_url"],
            "status": m["status"],
            "flag_id": m["flag_id"],
            "notes": m["notes"],
        })

    with open(DATA_DIR / "external_bookmaker_lines.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ext_rows[0].keys()))
        w.writeheader()
        w.writerows(ext_rows)

    with open(DATA_DIR / "matches_verified.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(master_rows[0].keys()))
        w.writeheader()
        w.writerows(master_rows)

    with open(DATA_DIR / "matches_verified.json", "w", encoding="utf-8") as f:
        json.dump({
            "session": "arena/6d9c321d",
            "snapshot_utc": "2026-10-13T18:15:00Z",
            "total_ng_state_cs2_fixtures": 86,
            "active_october_fixtures": 27,
            "ssr_dom_fixtures": 26,
            "live_hidden_fixtures": 1,
            "stale_summer_fixtures": 59,
            "verified_bookmaker_lines_count": sum(1 for r in master_rows if r["status"] == "verified"),
            "unverified_bookmaker_lines_count": sum(1 for r in master_rows if r["status"] != "verified"),
            "matches": master_rows,
            "teams": team_rows,
        }, f, indent=2)

    return master_rows, team_rows


FLAGS_6D9C321D = [
    {
        "id": "F-28",
        "severity": "Unverified Bookmaker Line (Left Blank)",
        "matches": "H-00 (1079620 Black Phoenix vs 6666), H-07 (1079622 ex-RUSTEC vs mellren), H-12 (1079624 FORZE Reload vs LFO 10)",
        "summary": "EGamersWorld displays its default 1.80 / 1.80 placeholder on these three CCT Europe Series #11 matches (and renders team 2 of H-12 as blank 'FORZE Reload VS '). Sportsbook decimal odds and no-vig implied probabilities are left strictly BLANK. For H-07, Polymarket has a thin $55-volume orderbook at 1.49 / 2.63 (flagged as low-liquidity prediction market only). Prior session 2cb6bff4's link to a 2025 Inner Circle vs FORZE Reload match on Tips.GG is rejected.",
        "sources": [
            ("EGW CCT Europe 11 Event", "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
            ("EGW H-00 Match", "https://egamersworld.com/counterstrike/match/_rW8GEyWK/black-phoenix-vs-6666-1FxyR_euv8"),
            ("EGW H-07 Match", "https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK"),
            ("EGW H-12 Match", "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3"),
            ("HLTV Event 9442", "https://www.hltv.org/events/9442/cct-2026-europe-series-11"),
        ],
    },
    {
        "id": "F-29",
        "severity": "Resolved Mystery (F-01 / F-COV & F-05)",
        "matches": "All 86 CS2 fixtures in play.hotspawn.com/lobby (<script id='ng-state'>)",
        "summary": "Reverse-engineering the Angular SSR TransferState (<script id='ng-state' type='application/json'>) from phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures reveals why the lobby filter pills show 86 fixtures while only 26 appear in the HTML DOM: (1) fixtures #01-#59 (ids 1051301-1055478) are 59 stale summer 2026 CS2 fixtures (2026-06-26 to 2026-07-10) left in status='scheduled' with empty permalinks; (2) fixture #60 (id 1079620, Black Phoenix vs 6666, 2026-10-13 17:00 UTC) was hidden from the SSR DOM because it was already LIVE (13:4 Dust2); (3) fixtures #61-#86 are the 26 visible matches. Furthermore, total_picks in ng-state shows each match has only N=7 to 21 total user votes (e.g., H-03 Gothic vs Lavked has N=8 votes: 1/8=12.5% -> 13% and 7/8=87.5% -> 88%, explaining the 101% sum in F-05).",
        "sources": [
            ("Hotspawn Lobby", "https://play.hotspawn.com/lobby"),
            ("Hotspawn H-00 Permalink", "https://www.hotspawn.com/matches/black-phoenix-vs-6666-cct-europe-2026-series-11-1079620"),
            ("HLTV 2399297 (Live)", "https://www.hltv.org/matches/2399297/black-phoenix-vs-6666-cct-2026-europe-series-11"),
        ],
    },
    {
        "id": "F-30",
        "severity": "Newly Verified Sportsbook Lines vs $0-Vol Polymarket Distortion",
        "matches": "H-13, H-16 through H-26 (All 12 Elisa BreakOut Series 2 LAN BO1s)",
        "summary": "Earlier sessions marked 5-12 Elisa BreakOut Series 2 matches as having no external odds or used illiquid $0-volume Polymarket orderbooks with 130%-144% booksums (e.g., H-18 1.18/2.17 = 130.8%, H-21 2.13/1.03 = 144.0%, H-24 1.08/2.17 = 138.7%, H-25 2.13/1.10 = 137.9%). Direct inspection of the official EGamersWorld Elisa Esports BreakOut Series 2 event page (4yn491uUVl) confirms live two-way BC.Game/EGW decimal odds (with normal ~107.9%-108.5% overround) for all 12 BO1 fixtures.",
        "sources": [
            ("EGW Elisa BreakOut Series 2 Event", "https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl"),
            ("HLTV Elisa BreakOut Series 2 Event", "https://www.hltv.org/events/9332/elisa-breakout-series-2"),
            ("Polymarket CS2", "https://polymarket.com/esports/cs2"),
        ],
    },
    {
        "id": "F-31",
        "severity": "Extreme Crowd Sentiment Inversion (Small-Sample Brand Bias)",
        "matches": "H-01 (ex-Keyd Stars vs Galorys), H-06 (HOTU vs Fnatic), H-17 (WROTBERRY vs ENCE), H-20 (EAC vs ENCE)",
        "summary": "In H-01, Hotspawn's crowd picked ex-Keyd Stars 83% (10 of 12 votes), whereas verified bookmakers (EGW 2.43/1.46, Polymarket 3.03/1.47), HLTV community (76.2% Galorys), and HLTV/VRS rankings (#68/#82 Galorys vs Unranked/#146 ex-Keyd) all make Galorys a ~63-74% favorite. In H-06, Hotspawn's crowd picked Fnatic 90% (19 of 21 votes) despite a near-50/50 market (EGW 1.88/1.79, Polymarket $12.2K vol 1.92/2.00) and #41 vs #36 HLTV rank. In H-17 and H-20, Hotspawn users picked ENCE 69% and 71% on name recognition, whereas bookmakers price WBT (1.62) and EAC (1.51) as favorites against ENCE's #114 Finnish lineup.",
        "sources": [
            ("HLTV 2399204 (ex-Keyd vs Galorys)", "https://www.hltv.org/matches/2399204/ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3"),
            ("EGW H-01 Match", "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp"),
            ("EGW H-06 Match", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC"),
            ("EGW Elisa BreakOut Event", "https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl"),
        ],
    },
    {
        "id": "F-32",
        "severity": "Roster Substitute Discrepancy",
        "matches": "H-09 (1080178 Legacy vs PARIVISION)",
        "summary": "HLTV match page 2399386 lists bobz as a substitute on Legacy (#7 HLTV / #6 VRS) vs full-strength PARIVISION (#11 HLTV / #11 VRS). While bookmakers (EGW 1.59/2.13, Polymarket 1.72/2.38) and our rank model (60.6% Legacy) still favor Legacy, HLTV community voters favor PARIVISION 64.2% to 35.8%.",
        "sources": [
            ("HLTV 2399386", "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026"),
            ("EGW Thunderpick WC Schedule", "https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp"),
        ],
    },
    {
        "id": "F-33",
        "severity": "Star-Roster Public Bias vs World Ranking",
        "matches": "H-14 (1079440 MIBR vs BC.Game)",
        "summary": "MIBR is ranked #12 HLTV (163 pts) and #13 VRS, while BC.Game is #70 HLTV (12 pts) and #46 VRS. Verified bookmakers on EGamersWorld price MIBR as 1.64 favorite vs 2.08 BC.Game (bookie avg 1.547/2.238), and our model prices MIBR at 76.7%. However, because BC.Game fields s1mple (1.24 rating) and electronic, HLTV community votes (79.3% BC.Game), Hotspawn crowd (68% BC.Game), and a thin $203 Polymarket market (2.17/1.82) lean toward BC.Game.",
        "sources": [
            ("HLTV 2399136", "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii"),
            ("EGW H-14 Match", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX"),
        ],
    },
    {
        "id": "F-34",
        "severity": "HLTV vs VRS Rank Inversion & Prior Broken Link Fix",
        "matches": "H-15 (1079442 Heroic vs Envy)",
        "summary": "On the official HLTV match page (2399137), Envy is ranked higher on the HLTV World Ranking (#20, 96 pts) than HEROIC (#30, 60 pts), whereas HEROIC is ranked higher on Valve Regional Standings (VRS #21 vs Envy VRS #27). Consequently, our composite HLTV+VRS model is a virtual toss-up (48.0% Heroic / 52.0% Envy), HLTV community slightly favors Envy (58.3%), and bookmakers on EGamersWorld (1.50/2.55, avg 1.484/2.502) favor Heroic. Also fixed the truncated EGW URL from prior session 2cb6bff4 to https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC.",
        "sources": [
            ("HLTV 2399137", "https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii"),
            ("EGW H-15 Match", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC"),
        ],
    },
    {
        "id": "F-35",
        "severity": "Side-Order Reversal Across Primary Sources",
        "matches": "H-25 (1080289 RoundsGG vs Voca)",
        "summary": "Hotspawn lists RoundsGG as Team 1 and Voca as Team 2, whereas both HLTV (match 2399428 'Voca vs ROUNDS') and EGamersWorld ('Voca VS Rounds', 1.09 vs 6.00) list Voca first and ROUNDS second. We explicitly invert the EGW quote to match Hotspawn's side order (RoundsGG 6.00 / Voca 1.09 -> 15.4% / 84.6% no-vig).",
        "sources": [
            ("Hotspawn H-25", "https://www.hotspawn.com/matches/roundsgg-vs-voca-elisa-breakout-series-2-1080289"),
            ("HLTV 2399428", "https://www.hltv.org/matches/2399428/voca-vs-rounds-elisa-breakout-series-2"),
            ("EGW H-25 Match", "https://egamersworld.com/counterstrike/match/4yn491uUVl/voca-vs-rounds-_dTpdE0K7U"),
        ],
    },
]


def build_verified_html(master_rows: list[dict], team_rows: list[dict]):
    # Read ng_state_86_fixtures.csv to summarize all 17 tournaments in ng-state
    ng_rows = []
    ng_csv = DATA_DIR / "ng_state_86_fixtures.csv"
    if ng_csv.exists():
        with open(ng_csv, encoding="utf-8") as f:
            ng_rows = list(csv.DictReader(f))

    tourn_summary = {}
    for r in ng_rows:
        key = (r["tournament"], r["tier"], r["category"])
        if key not in tourn_summary:
            tourn_summary[key] = {"count": 0, "first_utc": r["utc_start"], "last_utc": r["utc_start"], "first_id": r["hotspawn_id"], "last_id": r["hotspawn_id"]}
        tourn_summary[key]["count"] += 1
        tourn_summary[key]["last_utc"] = r["utc_start"]
        tourn_summary[key]["last_id"] = r["hotspawn_id"]

    match_tr = []
    for m in master_rows:
        ext_cell = (
            f"<strong>{m['ext_prob1_pct']}% / {m['ext_prob2_pct']}%</strong><br>"
            f"<span class='sub'>({m['ext_odds1']} / {m['ext_odds2']} · vig {round(float(m['ext_overround_pct'])-100,1)}%)</span>"
            if m["ext_prob1_pct"] != ""
            else "<span class='badge-warn'>BLANK (Unverified 1.80/1.80 placeholder)</span>"
        )
        edge_val = m["model_vs_market_edge1_pct"]
        edge_str = f"{edge_val:+.1f} pp" if isinstance(edge_val, (int, float)) else "—"
        status_badge = (
            "<span class='badge-ok'>Verified Bookmaker</span>"
            if m["status"] == "verified"
            else "<span class='badge-warn'>Unverified Bookmaker (Flagged)</span>"
        )
        thp_tag = " <span class='badge-thp' title='Listed in /thp-pickems'>THP</span>" if m["thp_sponsored"] == "yes" else ""
        flag_link = f" · <a href='#{m['flag_id']}'>{m['flag_id']}</a>" if m["flag_id"] else ""

        match_tr.append(f"""
        <tr data-tier="{m['tier']}" data-status="{m['status']}" data-search="{_esc((m['code']+' '+m['team1']+' '+m['team2']+' '+m['tournament']).lower())}">
          <td><strong>{m['code']}</strong><br><span class="sub">id {m['hotspawn_id']}</span></td>
          <td><strong>{m['utc_start']}</strong><br><span class="sub">SSR: {m['edt_display']}</span></td>
          <td>{_esc(m['tournament'])}<br><span class="sub">Tier {m['tier']} · {m['format']} · {m['points']} pts{thp_tag}</span></td>
          <td><strong>{_esc(m['team1'])}</strong> vs <strong>{_esc(m['team2'])}</strong><br>
              <span class="sub">HLTV: #{m['team1_hltv_rank']} vs #{m['team2_hltv_rank']} · VRS: #{m['team1_vrs_rank']} vs #{m['team2_vrs_rank']}</span></td>
          <td>{ext_cell}</td>
          <td><strong>{m['orig_prob1_pct']}% / {m['orig_prob2_pct']}%</strong><br>
              <span class="sub">Fair: {m['orig_odds1']} / {m['orig_odds2']} (Elo {m['team1_elo']}/{m['team2_elo']})</span></td>
          <td><strong>{_esc(m['recommended_pick'])} ({m['recommended_prob_pct']}%)</strong><br>
              <span class="sub">{_esc(m['pick_classification'])} · Δ {edge_str}</span></td>
          <td><span class="sub">{m['hotspawn_crowd_pct1_audit_only']}% / {m['hotspawn_crowd_pct2_audit_only']}%<br>(N={m['hotspawn_total_picks_n']} votes · NOT used)</span></td>
          <td>{status_badge}{flag_link}<br><span class="sub">{_esc(m['notes'])}</span></td>
          <td>
            <a href="{m['hotspawn_url']}" target="_blank" rel="noopener">Hotspawn</a> ·
            <a href="{m['hltv_url']}" target="_blank" rel="noopener">HLTV</a> ·
            <a href="{m['ext_url']}" target="_blank" rel="noopener">Bookie/EGW</a>
          </td>
        </tr>""")

    team_tr = []
    for t in team_rows:
        hrank = f"#{t['hltv_rank_2026_10_12']} ({t['hltv_points']} pts)" if t["hltv_rank_2026_10_12"] != "" else f"Unranked (Event seed #{t['event_hltv_seed']})"
        team_tr.append(f"""
        <tr>
          <td><strong>{_esc(t['team'])}</strong> <span class="sub">(ID {t['hltv_id']})</span></td>
          <td>{hrank}</td>
          <td>#{t['vrs_rank']}</td>
          <td>{t['star_rating_3m']:.2f}</td>
          <td><strong>{t['composite_elo']}</strong></td>
          <td><span class="sub">{_esc(t['notes'])}</span></td>
          <td>
            <a href="{t['hltv_team_url']}" target="_blank" rel="noopener">Team Page</a> ·
            <a href="{t['hltv_ranking_url']}" target="_blank" rel="noopener">Oct 12 Ranking</a> ·
            <a href="{t['verification_source_url']}" target="_blank" rel="noopener">Match/Event Proof</a>
          </td>
        </tr>""")

    ng_tr = []
    for (tname, tier, cat), info in tourn_summary.items():
        cat_label = {
            "stale_summer_2026_unclosed": "<span class='badge-warn'>Stale Unclosed Summer 2026 (No Permalink)</span>",
            "active_oct_2026_live_hidden_from_dom": "<span class='badge-thp'>Active Oct 2026 — LIVE (Hidden from SSR DOM)</span>",
            "active_oct_2026_ssr_dom": "<span class='badge-ok'>Active Oct 2026 — Rendered in SSR DOM</span>",
        }.get(cat, cat)
        ng_tr.append(f"""
        <tr>
          <td><strong>{_esc(tname)}</strong></td>
          <td>Tier {tier}</td>
          <td><strong>{info['count']}</strong></td>
          <td>{info['first_utc']} → {info['last_utc']}</td>
          <td><code>{info['first_id']}</code> .. <code>{info['last_id']}</code></td>
          <td>{cat_label}</td>
          <td><a href="{HOTSHAWN_LOBBY_URL}" target="_blank" rel="noopener">Hotspawn ng-state</a></td>
        </tr>""")

    flags_html = []
    for fl in FLAGS_6D9C321D:
        links = " · ".join(f'<a href="{u}" target="_blank" rel="noopener">{_esc(lbl)}</a>' for lbl, u in fl["sources"])
        flags_html.append(f"""
        <div class="flag-box" id="{fl['id']}">
          <h3>{fl['id']} — {_esc(fl['severity'])}: {_esc(fl['matches'])}</h3>
          <p>{_esc(fl['summary'])}</p>
          <p class="sub"><strong>Official Sources:</strong> {links}</p>
        </div>""")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Verified 27 Lines &amp; Angular TransferState Audit — Hotspawn Pick'em Analytics</title>
<link rel="stylesheet" href="css/styles.css">
<style>
  .sub {{ color: #9aa4b2; font-size: 0.82rem; }}
  .badge-ok {{ display:inline-block; padding:2px 8px; border-radius:4px; background:rgba(16,185,129,0.18); color:#34d399; font-size:0.78rem; font-weight:600; }}
  .badge-warn {{ display:inline-block; padding:2px 8px; border-radius:4px; background:rgba(245,158,11,0.18); color:#fbbf24; font-size:0.78rem; font-weight:600; }}
  .badge-thp {{ display:inline-block; padding:2px 6px; border-radius:4px; background:rgba(59,130,246,0.22); color:#60a5fa; font-size:0.75rem; font-weight:600; }}
  .flag-box {{ background:#151923; border:1px solid #262c3a; border-left:4px solid #f59e0b; border-radius:8px; padding:14px 18px; margin-bottom:14px; }}
  .flag-box h3 {{ margin:0 0 6px 0; font-size:1rem; color:#f8fafc; }}
  .flag-box p {{ margin:4px 0; font-size:0.9rem; line-height:1.5; }}
  .section-card {{ background:#151923; border:1px solid #262c3a; border-radius:10px; padding:20px; margin:22px 0; }}
  .table-scroll {{ overflow-x:auto; }}
  table.matches th, table.matches td {{ vertical-align:top; padding:10px 8px; font-size:0.86rem; }}
</style>
</head>
<body>
<header class="topbar"><div class="container nav">
  <a href="index.html" class="brand"><span class="brand-mark">HS</span><span class="brand-text">Hotspawn Pick'em Analytics</span></a>
  <nav>
    <a href="index.html">Dashboard</a>
    <a href="verified-lines.html" class="active">Verified 27 + ng-state Audit</a>
    <a href="s-tier.html">S-Tier</a>
    <a href="b-tier.html">B-Tier</a>
    <a href="c-tier.html">C-Tier</a>
    <a href="matches.html">All Matches (CSV)</a>
    <a href="own-lines.html">Own Lines</a>
    <a href="flagged.html">Flagged for Review</a>
    <a href="methodology.html">Methodology</a>
  </nav>
</div></header>

<main class="container">
  <section class="hero">
    <h1>Complete 27-Match Verified Betting Lines &amp; Angular SSR <code>ng-state</code> Audit</h1>
    <p class="subtitle">
      Line-by-line verification of all <strong>27 active October 2026 CS2 fixtures</strong> (the 26 SSR DOM fixtures plus the 27th live fixture <code>#1079620 Black Phoenix vs 6666</code> extracted from <code>&lt;script id="ng-state"&gt;</code>),
      all <strong>38 teams' HLTV World Ranks (2026-10-12) &amp; Valve Regional Standings (VRS)</strong>,
      verified <strong>EGamersWorld / BC.Game two-way sportsbook lines (24/27 matches, including all 12 Elisa BreakOut Series 2 BO1s)</strong>,
      and our <strong>independently originated dual-rating CS2 probabilities</strong>.
      Hotspawn crowd percentages are derived from only <code>N = 7..21</code> total picks per match and are <em>never</em> used as probability indicators.
    </p>
    <div class="kpi-row">
      <div class="kpi"><div class="kpi-num">86</div><div class="kpi-label">Total CS2 Fixtures in <code>ng-state</code> (26 DOM + 1 Live + 59 Stale)</div></div>
      <div class="kpi"><div class="kpi-num">24 / 27</div><div class="kpi-label">Verified External Sportsbook Lines (EGW / BC.Game)</div></div>
      <div class="kpi warn"><div class="kpi-num">3</div><div class="kpi-label">Unverified Bookie Lines Left Blank (EGW 1.80/1.80)</div></div>
      <div class="kpi"><div class="kpi-num">27 / 27</div><div class="kpi-label">Originated Dual-Rank (HLTV + VRS) Lines</div></div>
    </div>
  </section>

  <section class="controls">
    <label>Filter tier:
      <select id="vl-tier">
        <option value="all">All Tiers (27)</option>
        <option value="S">S-Tier · Thunderpick WC (4)</option>
        <option value="B">B-Tier · Stake / CCT / ESL (11)</option>
        <option value="C">C-Tier · Elisa BreakOut 2 (12)</option>
      </select>
    </label>
    <label>Bookmaker Status:
      <select id="vl-status">
        <option value="all">All (27)</option>
        <option value="verified">Verified Bookmaker Odds (24)</option>
        <option value="unverified">Unverified / Blank Bookmaker (3)</option>
      </select>
    </label>
    <label>Search:
      <input type="search" id="vl-search" placeholder="Team, tournament, H-code, ID…">
    </label>
  </section>

  <section class="section-card">
    <h2>1. Master Table — All 27 Active October 2026 CS2 Fixtures (<code>H-00</code> through <code>H-26</code>)</h2>
    <p class="sub">
      Every row links directly to its official Hotspawn fixture page, official HLTV match page, and official external bookmaker/aggregator page.
      Where EGamersWorld displays its default <code>1.80 / 1.80</code> placeholder (<code>H-00</code>, <code>H-07</code>, <code>H-12</code>), bookmaker odds and vig-free market probabilities are left strictly <strong>BLANK</strong> and flagged.
    </p>
    <div class="table-scroll">
      <table class="matches" id="vl-table">
        <thead>
          <tr>
            <th>Code / ID</th>
            <th>True UTC Start<br><span class="sub">(vs EDT SSR)</span></th>
            <th>Tournament &amp; Format</th>
            <th>Matchup &amp; Official Ranks<br><span class="sub">(HLTV Oct 12 &amp; VRS)</span></th>
            <th>External Bookmaker<br><span class="sub">No-Vig % (Decimal Odds)</span></th>
            <th>Originated Line (Ours)<br><span class="sub">HLTV+VRS Dual Model</span></th>
            <th>Recommended Pick<br><span class="sub">(Model + Market Blend)</span></th>
            <th>Hotspawn Crowd<br><span class="sub">(Audit Only · Never Used)</span></th>
            <th>Verification &amp; Audit Notes</th>
            <th>Official Source Links</th>
          </tr>
        </thead>
        <tbody>
          {"".join(match_tr)}
        </tbody>
      </table>
    </div>
  </section>

  <section class="section-card">
    <h2>2. Complete 38-Team Verified Ratings (HLTV World Ranking 2026-10-12 &amp; Valve Regional Standings VRS)</h2>
    <p class="sub">
      All 38 distinct CS2 teams competing in the 27 active October fixtures, verified line-by-line from
      <a href="{HLTV_RANKING_URL}" target="_blank" rel="noopener">HLTV World Ranking (12 Oct 2026)</a> and each match's official HLTV lineup block.
      Composite Elo formula: <code>Elo = 0.55*(2000 - 300*log10(HLTV_eff)) + 0.45*(2000 - 300*log10(VRS)) + 180*(StarRating3m - 1.10)</code>.
    </p>
    <div class="table-scroll">
      <table class="matches">
        <thead>
          <tr>
            <th>Team (HLTV ID)</th>
            <th>HLTV World Rank (2026-10-12)</th>
            <th>Valve Regional Standings (VRS)</th>
            <th>3-Month Star Player Rating</th>
            <th>Composite Elo</th>
            <th>Verification Notes</th>
            <th>Official Source Links</th>
          </tr>
        </thead>
        <tbody>
          {"".join(team_tr)}
        </tbody>
      </table>
    </div>
  </section>

  <section class="section-card">
    <h2>3. Reverse-Engineering Audit: Why <code>play.hotspawn.com/lobby</code> Advertises 86 Fixtures While Rendering 26</h2>
    <p class="sub">
      By inspecting the Angular SSR TransferState payload (<code>&lt;script id="ng-state" type="application/json"&gt;</code>) fetched from backend API
      <code>https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures</code>, we recovered all <strong>86 CS2 fixture records</strong>:
      <strong>59 stale summer 2026 fixtures</strong> (26 Jun – 10 Jul 2026, left in <code>status: "scheduled"</code> with no permalinks),
      <strong>1 live Oct 13 fixture</strong> (<code>id=1079620 Black Phoenix vs 6666</code>, hidden from the SSR DOM because Map 1 had already finished 13:4),
      and the <strong>26 upcoming fixtures</strong> rendered in the HTML DOM. Full dataset: <a href="../data/6d9c321d/ng_state_86_fixtures.csv"><code>data/6d9c321d/ng_state_86_fixtures.csv</code></a>.
    </p>
    <div class="table-scroll">
      <table class="matches">
        <thead>
          <tr>
            <th>Tournament Name (from <code>ng-state</code>)</th>
            <th>Tier</th>
            <th>Fixture Count</th>
            <th>UTC Schedule Window (from Epoch ms)</th>
            <th>Hotspawn ID Range</th>
            <th>TransferState Audit Classification</th>
            <th>Primary Source</th>
          </tr>
        </thead>
        <tbody>
          {"".join(ng_tr)}
        </tbody>
      </table>
    </div>
  </section>

  <section class="section-card" id="flagged-audit">
    <h2>4. Flagged for Review — Line-by-Line Irregularities &amp; Verification Findings (<code>F-28</code> to <code>F-35</code>)</h2>
    <p class="sub">
      Per project instructions, unverified bookmaker lines are left blank and flagged rather than inferred or hallucinated. Flagged items do not block publication.
    </p>
    {"".join(flags_html)}
  </section>
</main>

<footer class="footer"><div class="container">
  <p>Session <code>arena/6d9c321d</code> · Reproducible build via <code>scripts/6d9c321d_build.py</code> · CSV/JSON exports in <code>data/6d9c321d/</code>.</p>
  <p class="footer-links"><a href="index.html">Dashboard</a> · <a href="flagged.html">Flagged for Review</a> · <a href="methodology.html">Methodology</a> · <a href="own-lines.html">Own Lines</a> · <a href="matches.html">All Matches</a></p>
</div></footer>

<script>
(function() {{
  const tierSel = document.getElementById('vl-tier');
  const statusSel = document.getElementById('vl-status');
  const searchInp = document.getElementById('vl-search');
  const rows = Array.from(document.querySelectorAll('#vl-table tbody tr'));
  function filterRows() {{
    const t = tierSel.value;
    const s = statusSel.value;
    const q = searchInp.value.trim().toLowerCase();
    rows.forEach(r => {{
      const rt = r.getAttribute('data-tier');
      const rs = r.getAttribute('data-status');
      const rq = r.getAttribute('data-search') || '';
      const okTier = (t === 'all') || (rt === t);
      const okStatus = (s === 'all') || (s === 'verified' && rs === 'verified') || (s === 'unverified' && rs !== 'verified');
      const okSearch = !q || rq.includes(q);
      r.style.display = (okTier && okStatus && okSearch) ? '' : 'none';
    }});
  }}
  tierSel.addEventListener('change', filterRows);
  statusSel.addEventListener('change', filterRows);
  searchInp.addEventListener('input', filterRows);
}})();
</script>
</body>
</html>
"""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DOCS_DIR / "verified-lines.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    m_rows, t_rows = build_datasets()
    build_verified_html(m_rows, t_rows)
    print(f"Built {len(m_rows)} verified matches, {len(t_rows)} verified teams, and docs/verified-lines.html")

