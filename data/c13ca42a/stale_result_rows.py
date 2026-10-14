# Session arena/c13ca42a — C-02 verified stale results.
# Each tuple: (match_id, status, winner, score, series_format, result_date, official_source_url, flag)
# Verified 2026-10-14T08:35Z by direct reads of official HLTV results pages (and Liquipedia for DACH).
# Source pages per event:
#   Urban Riga Open #5          -> https://www.hltv.org/results?event=9219
#   TWC SA Series #1            -> https://www.hltv.org/results?event=9239
#   CCT Europe Challengers #4   -> https://www.hltv.org/results?event=9236
#   CCT South America Series #3 -> https://www.hltv.org/results?event=9233
#   EPL S8 (Play-In + Play-In groups) -> https://www.hltv.org/results?event=9245 and ?event=9246
#   Svenska CS-Ligan 2026 Finals -> https://www.hltv.org/results?event=9235
#   Rainhas do Clutch 2026      -> https://www.hltv.org/results?event=9179
#   LG UltraGear Tournament 2026 -> https://www.hltv.org/results?event=9232
#   CCT SA Series #7            -> https://www.hltv.org/results?event=9452
#   DACH CS Masters Season 5    -> https://liquipedia.net/counterstrike/DACH_CS_Masters/Season_5
#   DraculaN Season 7           -> https://www.hltv.org/events/9312/draculanan-season-7 (unresolved evidence)

DRAC = ("UNRESOLVED-DRACULAN: HLTV lists DraculaN Season 7 (event 9312) as UPCOMING "
        "2026-10-19/23 Bucharest $35k 24 teams; no results exist and this pairing is "
        "absent from the published Oct 19-23 schedule; card date contradicts the official "
        "event dates; pick withheld (no fabrication)")
SVC = "HLTV hosts this fixture under the companion event Svenska CS-Ligan 2026 Finals (event 9235)"

ROWS = [
    ("1052746", "verified", "Endless Journey", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395499", ""),
    ("1051339", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1051301", "verified", "CYBERSHOKE Prospects", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395413", ""),
    ("1053068", "verified", "ReThink", "2-1", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395365", SVC),
    ("1052747", "verified", "Sashi Academy", "2-1", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395497", ""),
    ("1053146", "verified", "Clutchain", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395353", "Name alias: HLTV lists the team as Clutchain fe"),
    ("1051340", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1053069", "verified", "train launcher", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395366", SVC),
    ("1052686", "verified", "MIBR fe", "3-1", "bo5", "2026-06-26", "https://www.hltv.org/matches/2395354", "Name alias: HLTV lists the team as Shimmer"),
    ("1051789", "verified", "MIBR Academy", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395422", ""),
    ("1053070", "verified", "ReThink", "2-1", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395367", SVC),
    ("1051790", "verified", "Keyd", "2-0", "bo3", "2026-06-26", "https://www.hltv.org/matches/2395423", "Name alias: HLTV lists the team as Keyd Stars"),
    ("1052748", "verified", "Inner Circle Academy", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395500", "Name alias: HLTV lists the team as SAW"),
    ("1053071", "verified", "roamsfiest", "2-1", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395368", SVC),
    ("1052749", "verified", "Misa", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395501", "Name alias: HLTV lists the team as WBT"),
    ("1052180", "verified", "Julie&Cie", "2-1", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395431", ""),
    ("1052181", "verified", "Just Players", "1-0", "bo1", "2026-06-27", "https://www.hltv.org/matches/2395432", ""),
    ("1051800", "verified", "ShindeN", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395424", ""),
    ("1052699", "verified", "Red Feet", "1-0", "bo1", "2026-06-27", "https://www.hltv.org/matches/2395554", ""),
    ("1052183", "verified", "Misa", "1-0", "bo1", "2026-06-27", "https://www.hltv.org/matches/2395434", ""),
    ("1051341", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1052599", "verified", "Mai Tai", "1-0", "bo1", "2026-06-27", "https://www.hltv.org/matches/2395433", "Name alias: HLTV lists the team as megoshort"),
    ("1053072", "verified", "roamsfiest", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395369", SVC),
    ("1052357", "verified", "BIG Academy", "2-0", "bo3", "2026-06-27", "https://liquipedia.net/counterstrike/DACH_CS_Masters/Season_5", "Not on HLTV; verified on Liquipedia (Grand Final, offline Munich; 1st BIG Academy $3133.17 / 2nd Esport BERG $1481.14; player match logs show BIG.A 2:0 BERG on 2026-06-27); name alias: BERG = Esport BERG"),
    ("1051801", "verified", "UNO MILLE", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395425", ""),
    ("1052700", "verified", "GameHunters", "2-1", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395555", ""),
    ("1051342", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1053073", "verified", "ReThink", "2-1", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395370", SVC),
    ("1052701", "verified", "Alka", "2-1", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395556", "Name alias: HLTV lists the team as ALKA (same team; card spelling shown on the board)"),
    ("1053313", "verified", "LP", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395426", ""),
    ("1051803", "verified", "Fluxo", "2-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395427", "Name alias: HLTV lists the team as Keyd Stars"),
    ("1052702", "verified", "BESTIA Academy", "1-0", "bo3", "2026-06-27", "https://www.hltv.org/matches/2395557", ""),
    ("1052750", "verified", "Honvéd", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395502", ""),
    ("1052751", "verified", "ex-MANA", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395503", ""),
    ("1052185", "verified", "Entropy", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395436", "AMBIGUOUS-DOUBLE-PLAY: SAW and Entropy met twice in this event (2395436 on 2026-06-28 Entropy 2-1 SAW; 2395455 on 2026-07-03 SAW 2-0 Entropy); the 2026-06-28 match matches the card date and is used; name alias: HLTV lists the team as SAW"),
    ("1053431", "verified", "Coalesce", "13-11", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395602", ""),
    ("1053432", "verified", "Leo", "13-8", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395603", ""),
    ("1053433", "verified", "Aimhaus", "13-7", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395604", ""),
    ("1053434", "verified", "Leo", "13-11", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395605", ""),
    ("1052698", "verified", "MAGICOS", "1-0", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395561", ""),
    ("1053435", "verified", "Leo", "13-7", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395606", ""),
    ("1053436", "verified", "Coalesce", "13-10", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395607", ""),
    ("1051343", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1052186", "verified", "Subtop De France", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395437", ""),
    ("1052187", "verified", "Endless Journey", "1-0", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395438", ""),
    ("1052184", "verified", "Atreides", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395435", "Name alias: HLTV lists the team as DONSTU"),
    ("1052696", "verified", "Yawara", "2-0", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395559", ""),
    ("1053439", "verified", "ASTRAL", "13-4", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395609", ""),
    ("1053469", "verified", "BERG", "13-7", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395608", ""),
    ("1053441", "verified", "ASTRAL", "13-5", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395611", ""),
    ("1053470", "verified", "SINQU REHTI", "19-17", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395610", ""),
    ("1051344", "unresolved", "", "", "", "", "https://www.hltv.org/events/9312/draculanan-season-7", DRAC),
    ("1051804", "verified", "UNO MILLE", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395428", ""),
    ("1053442", "verified", "BERG", "13-11", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395612", ""),
    ("1053471", "verified", "ASTRAL", "13-6", "bo1", "2026-06-28", "https://www.hltv.org/matches/2395613", ""),
    ("1052697", "verified", "Guara", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395560", "Name alias: HLTV lists the team as GUARA (same team; card spelling shown on the board)"),
    ("1053679", "verified", "ShindeN", "2-0", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395429", ""),
    ("1052695", "verified", "Patins de Ferrari", "2-1", "bo3", "2026-06-28", "https://www.hltv.org/matches/2395558", "Name alias: HLTV lists the winning team as Patins da Ferrari (same team; card name 'Patins de Ferrari' shown on the board)"),
    ("1055478", "verified", "Lavked", "1-0", "bo1", "2026-07-09", "https://www.hltv.org/matches/2395526", "DATE-OFF-BY-ONE: card date 2026-07-10 vs HLTV result dated 2026-07-09; only illwill-Lavked fixture in the event (Play-In groups); result certain, calendar offset noted"),
    ("1081105", "verified", "your end", "1-0", "bo1", "2026-10-13", "https://www.hltv.org/matches/2399460", ""),
]
