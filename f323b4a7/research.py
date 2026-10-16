#!/usr/bin/env python3
"""Verified TWC 2026 research for the f323b4a7 board.

Every fact below was read from an official/primary source during this session
(2026-10-16, sandbox clock 04:17-04:35 UTC) or is copied from a capture already stored in
this repository with its read timestamp.  `source_url` is the page the fact came from.
"""
from __future__ import annotations

EVENT = {
    "name": "Thunderpick World Championship 2026",
    "hltv_event": "https://www.hltv.org/events/8932/thunderpick-world-championship-2026",
    "hltv_matches": "https://www.hltv.org/events/8932/matches",
    "hltv_results": "https://www.hltv.org/results?event=8932",
    "dates": "Oct 14th - Oct 18th 2026",
    "prize_pool": "$1,000,000",
    "teams": 8,
    "location": "Malta",
    "format": "Two 4-team groups (double elimination) feeding a single-elimination playoff; "
              "grand final is BO5, the rest of the playoff is BO3.",
    "read_utc": "2026-10-16T04:28:00Z",
}

# --- results, read from the HLTV event page bracket + the archived result records --------
DAY1 = [
    {"id": "1080176", "teams": ["9z", "Aurora"], "score": "2-0", "winner": "9z",
     "note": "The upset the brief refers to. 9z won the opening round of Group A.",
     "hltv": "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026",
     "verified": "HLTV event bracket + HLTV head-to-head link 2399384 + Hotspawn match page form list"},
    {"id": None, "teams": ["Falcons", "Ninjas in Pyjamas"], "score": "2-0", "winner": "Falcons",
     "note": "Group A opening round (HLTV bracket). Hotspawn fixture id and HLTV match id not captured - left blank.",
     "hltv": None, "report": None, "verified": "HLTV event bracket only"},
    {"id": None, "teams": ["Legacy", "PARIVISION"], "score": "2-0", "winner": "Legacy",
     "note": "Group B opening round.",
     "hltv": "https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026",
     "report": None, "verified": "HLTV event bracket + HLTV head-to-head link 2399386"},
    {"id": None, "teams": ["FURIA", "BetBoom"], "score": "2-0", "winner": "FURIA",
     "note": "Group B opening round.",
     "hltv": "https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45723/furia-fend-off-betboom-to-end-day-one-of-twc",
     "verified": "HLTV event bracket + HLTV head-to-head link 2399387"},
]

DAY2 = [
    {"id": "1080201", "teams": ["Aurora", "Ninjas in Pyjamas"], "score": "2-0", "winner": "Aurora",
     "maps": "Cache 13-9; Dust2 13-7",
     "hltv": "https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45724/nip-spared-scheduling-headache-after-early-thunderpick-world-championship-exit",
     "verified": "Repository capture hotspawn/research/results.json, HLTV-verified 2026-10-15T22:30:54Z"},
    {"id": "1080202", "teams": ["9z", "Falcons"], "score": "1-2", "winner": "Falcons",
     "maps": "Nuke 9-13; Mirage 13-8; Dust2 9-13",
     "hltv": "https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45728/falcons-secure-playoff-berth-at-twc-2026",
     "verified": "Repository capture hotspawn/research/results.json, HLTV-verified 2026-10-15T22:30:54Z"},
    {"id": "1080203", "teams": ["PARIVISION", "BetBoom"], "score": "1-2", "winner": "BetBoom",
     "maps": "Ancient 13-10 PARIVISION; Anubis 4-13; Mirage 7-13",
     "hltv": "https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc",
     "verified": "Repository capture hotspawn/research/results.json, HLTV-verified 2026-10-15T22:30:54Z"},
    {"id": "1080204", "teams": ["Legacy", "FURIA"], "score": "1-2", "winner": "FURIA",
     "maps": "Cache 13-10 Legacy; Inferno 5-13; Mirage 8-13",
     "hltv": "https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026",
     "report": "https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy",
     "verified": "Repository capture hotspawn/research/results.json, HLTV-verified 2026-10-15T22:30:54Z"},
]

DAY3 = [
    {"id": "1080205", "teams": ["Aurora", "9z"], "hltv": 2399412, "group": "Group A decider",
     "start_utc": "2026-10-16T14:00:00Z", "lock_utc": "2026-10-16T13:54:00Z",
     "hltv_url": "https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026",
     "analytics_url": "https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026"},
    {"id": "1081775", "teams": ["BetBoom", "Legacy"], "hltv": 2399413, "group": "Group B decider",
     "start_utc": "2026-10-16T17:00:00Z", "lock_utc": "2026-10-16T16:54:00Z",
     "hltv_url": "https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026",
     "analytics_url": "https://www.hltv.org/betting/analytics/2399413/betboom-vs-legacy-thunderpick-world-championship-2026"},
]

PLAYOFFS = [
    {"id": "2399414", "teams": ["FURIA", "Aurora/9z winner"], "when": "2026-10-17 10:00 (HLTV display)",
     "url": "https://www.hltv.org/matches/2399414/furia-vs-aurora-9z-winner-thunderpick-world-championship-2026"},
    {"id": "2399415", "teams": ["Falcons", "BETBOOM/Legacy winner"], "when": "2026-10-17 13:00 (HLTV display)",
     "url": "https://www.hltv.org/matches/2399415/falcons-vs-betboom-legacy-winner-thunderpick-world-championship-2026"},
    {"id": "2399416", "teams": ["3rd Place Decider Match"], "when": "2026-10-18 07:30 (HLTV display)",
     "url": "https://www.hltv.org/matches/2399416/thunderpick-world-championship-2026-3rd-place-decider-match-thunderpick-world-championship-2026"},
    {"id": "2399417", "teams": ["Grand Final (BO5)"], "when": "2026-10-18 11:00 (HLTV display)",
     "url": "https://www.hltv.org/matches/2399417/thunderpick-world-championship-2026-grand-final-thunderpick-world-championship-2026"},
]

# --- Aurora roster rebuild (the "recent roster change" in the brief) --------------------
AURORA_ROSTER = {
    "read_utc": "2026-10-16T04:33:00Z",
    "players": ["XANTARES", "woxic", "Wicadia", "kyxsan", "Jimpphat"],
    "coach": "ash (Ashley Battye)",
    "change_date": "2026-07-08/09",
    "sources": [
        {"label": "HLTV betting analytics, Aurora vs 9z (current five listed)",
         "url": "https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026"},
        {"label": "Hotspawn match page 1080205 (Aurora lineup)",
         "url": "https://www.hotspawn.com/matches/aurora-vs-9z-thunderpick-world-championship-2026-1080205"},
        {"label": "Valve Regional Standings 2026-10-05, Aurora #9 roster line",
         "url": "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md"},
        {"label": "Strafe - Aurora locks in new CS2 roster with kyxsan and Jimpphat (2026-07-08)",
         "url": "https://www.strafe.com/news/read/aurora-locks-in-new-cs2-roster-with-kyxsan-and-jimpphat/"},
        {"label": "Hotspawn - CS2 roster changes tracker (2026-08-05)",
         "url": "https://www.hotspawn.com/counter-strike/news/cs2-roster-changes"},
    ],
    "finding": "Aurora's roster change is real but it is NOT recent: the Turkish core was broken up and "
               "kyxsan (IGL), Jimpphat and coach ash were added on 2026-07-08/09, roughly three months "
               "before this match. Valve's 2026-10-05 standings already score this exact five (Aurora #9, "
               "1716 points), so the standings are not stale for Aurora and no roster adjustment is applied.",
    "irregularity": "The brief describes the Aurora change as 'recent'. It is a documented July 2026 rebuild, "
                    "not a days-old move; it is treated as background, not as a live edge.",
}

NINEZ = {
    "players": ["franssj", "max", "HUASOPEEK", "meyern", "luchov"],
    "source": "https://www.hotspawn.com/matches/aurora-vs-9z-thunderpick-world-championship-2026-1080205",
    "read_utc": "2026-10-16T04:20:00Z",
    "vrs": {"standing": 24, "points": 1543},
    "hltv_rank": 17,
}

SOURCES = [
    ("Hotspawn Play lobby (fixture list, tiers, points, lock countdowns, crowd share)",
     "https://play.hotspawn.com/lobby", "2026-10-16T04:18:00Z"),
    ("Hotspawn TransferState capture already in the repo (86 fixtures, exact UTC epochs)",
     "https://play.hotspawn.com/lobby", "2026-10-15T22:41:15Z"),
    ("Pinnacle public guest CS2 markets (moneyline, margin removed)",
     "https://www.pinnacle.com/en/esports/games/cs2/matchups/", "2026-10-15T22:41:17Z"),
    ("Polymarket gamma API, counter-strike series (match-winner price)",
     "https://gamma-api.polymarket.com/markets?slug=cs2-aur1-9z-2026-10-16", "2026-10-16T04:23:06Z"),
    ("Valve Regional Standings, global 2026-10-05 (points, rosters)",
     "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
     "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md",
     "2026-10-05 (Valve publication date)"),
    ("HLTV world ranking (ranks used as labelled context only)",
     "https://www.hltv.org/ranking/teams/2026/october/12", "2026-10-15T22:41:23Z"),
    ("HLTV Thunderpick World Championship 2026 event page (bracket, format, prize pool)",
     "https://www.hltv.org/events/8932/thunderpick-world-championship-2026", "2026-10-16T04:28:00Z"),
    ("HLTV TWC 2026 match list (day-3 kick-offs, playoff schedule)",
     "https://www.hltv.org/events/8932/matches", "2026-10-16T04:26:00Z"),
    ("HLTV betting analytics - Aurora vs 9z (ranks, form, head-to-head)",
     "https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026",
     "2026-10-16T04:30:00Z"),
    ("HLTV betting analytics - BETBOOM vs Legacy (ranks, form, map stats)",
     "https://www.hltv.org/betting/analytics/2399413/betboom-vs-legacy-thunderpick-world-championship-2026",
     "2026-10-16T04:30:00Z"),
]
