# Session arena/83090640 — line-by-line verification record (2026-10-16)

Scope: research-fallback resolution for the two fixtures without picks (M83-1), TWC day-1/day-2/day-3
review and roster verification (M83-2), coverage completeness (M83-3), executive-summary/phone audit
(M83-4), flagged irregularities (M83-5), final integration (M83-6). Every fact below was read from the
linked official source in the read window **2026-10-16T07:21Z–07:35Z** unless another time is stated.
HLTV page clocks are viewer-local and were not used; UTC times come from Hotspawn's payload epochs,
Polymarket's API, or the repository's frozen captures.

## 1. Coverage completeness (M83-3)

| Fact | Value | Source | Read (UTC) |
|---|---|---|---|
| CS2 fixtures listed on the Hotspawn lobby | 95 ("All tiers (95)"; per-tournament counts sum to 95) | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) | 2026-10-16T07:26Z |
| Fixtures in the board's capture | 95 (same tournament split) | `hotspawn/data/capture.json` (2026-10-16T05:58:32Z) | generated 05:58Z |
| New CS2 fixtures since the capture | none (week counter 123→149 is non-CS2 titles) | same two reads above | 07:26Z |
| Open fixtures at capture | 31; **31 with a pick after this session's rung E** | `hotspawn/data/summary.json` | rebuilt 07:35Z |

## 2. The two previously-unresolved fixtures (M83-1)

Both were rung-D (blank pick) at the 05:58:32Z capture with the recorded limitation "one or both teams
not uniquely identified in Valve standings". The root cause, found and verified this session, is that the
names are **duplicated** in Valve's official file.

### 2.1 Valve standings rows (official source, pinned commit)

Source for every row: [standings_global_2026_10_05.md @ eec4853](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)
(clone HEAD of 2026-10-16 = `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`, the same commit the board cites).
All six candidate rows were re-verified line-by-line against the raw file by
`83090640/resolve_fallback.py --vrs-file` (rank, points, name, roster all matched).

| Team | Rank | Points | Roster (as printed in the file) | Overlap with HLTV match lineup | Permalink |
|---|---|---|---|---|---|
| BET-M (row 1) | 71 | 1149 | bluewh1te, executor, Raijin, synyx, z1Nny | 4 | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0071--bet-m--bluewh1te-executor-raijin-synyx-z1nny.md) |
| Just Players (row 1) | 118 | 974 | bl1x1, h1te, sm3t, sstiNiX, Temny Prince | **4 (winner)** | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0118--just_players--bl1x1-h1te-sm3t-sstinix-temny_prince.md) |
| Just Players (row 2) | 347 | 485 | em0k1d, rexxie, Something, spirit, sstiNiX | 1 | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0347--just_players--em0k1d-rexxie-something-spirit-sstinix.md) |
| Banda Chuya (row 1) | 165 | 801 | AdrieN, ezox, maaryy, Showk, tomiko | **5 (winner)** | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0165--banda_chuya--adrien-ezox-maaryy-showk-tomiko.md) |
| Banda Chuya (row 2) | 373 | 402 | ezox, manio | 1 | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0373--banda_chuya--ezox-manio.md) |
| Enjoy | 138 | 871 | kurosa, nbl, roxesz, sh1geo, zazzer | 3 | [row](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/details/2026_10_05/0138--enjoy--kurosa-nbl-roxesz-sh1geo-zazzer.md) |

A full scan of the file found **31 duplicated names** (published as IR-36). The roster-overlap rule
(≥ 3 shared nicknames, strictly best; documented in `83090640/resolve_fallback.py` and the method page)
chose rows 118 and 165; the model recomputes the rule from the capture and cross-checks the pack's
chosen points before publishing (test `test_disambiguation_rule_is_reproducible`).

### 2.2 HLTV match pages (official source)

| Fact | Source | Read (UTC) |
|---|---|---|
| 1079170 BET-M vs Just Players, BO3, Swiss round 2 (0-1 teams), 17 Oct | [HLTV 2399087](https://www.hltv.org/matches/2399087/bet-m-vs-just-players-nodwin-clutch-series-13) | 07:22Z |
| BET-M lineup: Patsi, Raijin, executor, z1Nny, bluewh1te; HLTV #65 / VRS #87 | same page (Lineups panel) | 07:22Z |
| Just Players lineup: h1te, sm3t, sstiNiX, Temny Prince, wh1teout; HLTV #116 / VRS #108 | same page | 07:22Z |
| No sportsbook odds on 2399087 (Stake sweepstake promo only) | same page (#betting) | 07:22Z |
| 1081126 Banda Chuya vs Enjoy, BO3, Group A decider, 18 Oct | [HLTV 2399477](https://www.hltv.org/matches/2399477/banda-chuya-vs-enjoy-cct-2026-europe-series-12-closed-qualifier) | 07:25Z |
| Banda Chuya lineup: tomiko, maaryy, AdrieN, Showk, ezox; HLTV Unranked / VRS #187 | same page | 07:25Z |
| Enjoy lineup: reyoz, sh1geo, kurosa, nbl, flawix; HLTV #199 / VRS #157 | same page | 07:25Z |
| No sportsbook odds on 2399477 (Stake sweepstake promo only) | same page (#betting) | 07:25Z |
| CCT Europe Series 12 Closed Qualifier Group A bracket results (2-1/1-2 lines for both deciderists) | [HLTV event 9456](https://www.hltv.org/events/9456/cct-2026-europe-series-12-closed-qualifier) | 07:25Z |

### 2.3 Esportsbooks / betting lines (negative evidence, recorded not invented)

| Check | Result | Source |
|---|---|---|
| Pinnacle public CS2 feed | not listed for either fixture at the 05:58Z capture | board `research_attempt` records |
| Polymarket | no market for either fixture; the Sept "BET-M 33 – Just Players" market is a different match and was rejected (IR-35) | [rejected market](https://polymarket.com/esports/cs2/nodwin-clutch-series/cs2-33-justpl-2026-09-18) |
| EGamersWorld (banda chuya vs Enjoy) | 1.8/1.8 symmetric placeholder + 0%/0% votes — not a market, rejected (IR-34) | [EGW page](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-enjoy-9ru7xO5OG) |
| bo3.gg-class esportsbook relays | no eligible named-book relay for either fixture (board `relay` absent) | capture records |
| Web search "BET-M Just Players odds" / "Banda Chuya Enjoy odds" | no book line found for either fixture | search run 2026-10-16 (session log) |

### 2.4 Published picks (rung E — the board's own line formula, no invented inputs)

Formula (unchanged, fitted on 13,609 Valve-published results): P(A) = 1/(1+10^(−k·ΔPoints/400)), k = 0.4598.

| Fixture | Chosen rows | Computed line | Pick | Flags |
|---|---|---|---|---|
| 1079170 | BET-M 1149 vs Just Players 974 | BET-M 61.4% / 38.6% | **BET-M** | RESEARCH_FALLBACK, VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED (Patsi in, synyx out), NO_MARKET, MODEL_ONLY |
| 1081126 | Banda Chuya 801 vs Enjoy 871 | Banda chuya 45.4% / Enjoy 54.6% | **Enjoy** | RESEARCH_FALLBACK, VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED (reyoz+flawix in, roxesz+zazzer out), NO_MARKET, MODEL_ONLY |

Both rows carry the full evidence pack on the site: `hotspawn/research/fallback_83090640.json`
(generated by `83090640/resolve_fallback.py`, verified against the official file at generation time).
Both leaderboard classes are **NO CROWD DATA** (4 Hotspawn picks each — under the 10-pick threshold; no
automatic fade is issued on tiny samples).

## 3. TWC 2026 day 1 / day 2 / day 3 (M83-2)

| Fact | Source |
|---|---|
| Day 1: 9z 2-0 Aurora (Inferno 13-11, Nuke 13-1) — the upset | [HLTV 2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) · [HLTV news 45723](https://www.hltv.org/news/45723/furia-fend-off-betboom-to-end-day-one-of-twc) |
| Day 1: Falcons 2-0 NIP (Ancient 16-13 OT, Dust2 13-6); Legacy 2-0 PARIVISION; FURIA 2-0 BETBOOM | [HLTV news 45723](https://www.hltv.org/news/45723/furia-fend-off-betboom-to-end-day-one-of-twc) · [pley.gg schedule](https://pley.gg/cs2/thunderpick-world-championship-2026/) |
| Day 2: Aurora 2-0 NIP (Cache 13-9, Dust2 13-7), NIP eliminated | [HLTV 2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) |
| Day 2: Falcons 2-1 9z (Nuke 9-13, Mirage 13-8, Dust2 9-13 from 9z side), Falcons to playoffs | [HLTV 2399409](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) |
| Day 2: BetBoom 2-1 PARIVISION, PARIVISION eliminated | [HLTV 2399410](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) |
| Day 2: FURIA 2-1 Legacy, FURIA to playoffs | [HLTV 2399411](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026) |
| Day 3 deciders: Aurora vs 9z (14:00Z), BetBoom vs Legacy (17:00Z), 16 Oct | [HLTV 2399412](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) · [HLTV 2399413](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026) · Hotspawn payload epochs |
| Aurora roster change: kyxsan IGL (8 Jul 2026), Jimpphat + coach ashhh (3 Jul); MAJ3R/soulfly/Fabre out. **~3 months old by TWC — context, not a fresh onboarding event** | [HLTV 45082](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan) · [Strafe 8 Jul](https://www.strafe.com/news/read/aurora-locks-in-new-cs2-roster-with-kyxsan-and-jimpphat/) · [pley.gg 8 Jul](https://pley.gg/cs2/aurora-finalizes-international-transition-with-the-signing-of-kyxsan/) |

Day-2 grades in this repo (frozen pre-lock picks 2/3, leaderboard plan 2/3) come from the already-verified
`hotspawn/research/day2_twc2026.json` (session b6f5405d) and were re-checked against the HLTV match pages
above; map-score orientation matches. The day-3 plan copy added this session states only the verified
facts (9z's day-1 2-0, the map off Falcons on day 2, the July rebuild date) and defers all probabilities
to the live board rows — no second hand-maintained number.

## 4. Executive summary & phone (M83-4)

| Check | Result |
|---|---|
| Landing links to picks/TWC/leaderboard/unresolved/flagged/method | rendered (`hotspawn/index.html` btns block) |
| "31 open matches · 31 with a pick · 12 featured · 19 via research ladder · 0 without a pick" | rendered from `summary.json` (dynamic) |
| Every page carries a viewport meta + mobile stylesheet | `hotspawn/tests.py` Pages tests (pass) |
| Real-browser 360/390/768 px layout cases | run in CI (`hotspawn-22be6967.yml`); local sandbox has no browser — no layout claim made locally |
| Local link audit of the 10 primary pages | 458 local links, **0 broken** (script in session log) |

## 5. Tests (M83-5)

- `python3 hotspawn/tests.py`: **73 tests OK** (31 open rows: pick = higher-probability side, probabilities
  sum to 1, each rung reproduces its labelled formula, crowd never moves a probability, fallback rows are
  pack-backed with ≥3 unique-best overlaps, negative price checks recorded, roster deltas flagged).
- `python3 -m unittest discover -s tests`: **427 tests OK** (repo-wide suite).
- `83090640/resolve_fallback.py --vrs-file …`: all 6 candidate rows verified against Valve's official file.

## 6. Flagged for review (M83-5) — non-blocking, published on `hotspawn/flagged.html`

IR-31 (resolved by the documented rule), IR-32 (BET-M Patsi/synyx delta), IR-33 (Enjoy 2-player delta),
IR-34 (EGW placeholder rejected), IR-35 (historical Polymarket market rejected), IR-36 (31 duplicated
Valve names). None of these block publication; each carries its evidence links on the Flagged page.

## 7. What this session did NOT claim

Direct bookmaker odds of its own invention; any probability from Hotspawn crowd shares; any value for a
fixture without a source; edits to other sessions' namespaces (`docs/`, `executive/`, `f323b4a7/`,
`a6f05f99/`, …). The board's data and pages were regenerated only through the repo's own
`collect.py → model.py → build.py → tests.py` pipeline.

---

# Second wave (2026-10-16 08:10–09:00Z): 11 new lobby fixtures, 8 new rows researched

The scheduled live refresh (run 38869789949) pulled a 07:51:12Z capture with **106 fixtures** (was 95);
the 11 new CS2 fixtures produced 8 fresh rung-D rows. Every row below was researched against official
sources in the window above; the pack (`hotspawn/research/fallback_83090640.json`) was regenerated and
every candidate row re-verified line-by-line against Valve's raw file (`resolve_fallback.py --vrs-file`,
25 rows checked). Result: **41 of 42 open fixtures carry a pick**; the single documented absence is
1081497 (IR-38). The ladder re-flowed as designed: rows with unique Valve identities got the strict own
line (rung C), rows needing disambiguation got rung E.

| Fixture (lock UTC) | HLTV match (lineups) | Valve rows (official links in pack) | Disambiguation | Line | Pick | Flags |
|---|---|---|---|---|---|---|
| Eternal Fire vs Apogee Betclic (16 Oct 07:54, BO3) | [2399654](https://www.hltv.org/matches/2399654/eternal-fire-vs-betclic-pgl-bucharest-2027-closed-qualifier) | EF #33 1429 (5/5); Betclic #45 1333 (5/5) vs #183 765 (2) | #45 | 56.3 / 43.7 | Eternal Fire | POST_LOCK_RESOLUTION (researched 08:45Z), VALVE_NAME_AMBIGUOUS |
| Young27 vs Young TigeRES (16 Oct 12:54, BO3 LAN) | [2399642](https://www.hltv.org/matches/2399642/young-tigeres-vs-y27-gluck-yungstar-2026-series-3) | YT #199 728 (3/5); **Y27: none** (HLTV+VRS Unranked) | — | — | **blank (IR-38)** | UNRESOLVED |
| Rune Eaters vs HyperSpirit (16 Oct 12:54, BO3) | [2399760](https://www.hltv.org/matches/2399760/rune-eaters-vs-hyperspirit-cis-esports-league-cyberclash-season-2) | RE #81 1110 (5/5); HYPERSPIRIT #162 803 (5/5) | unique | 69.3 / 30.7 | Rune Eaters | MODEL_ONLY, NO_MARKET |
| PRIVATE vs UPGRADE (16 Oct 15:54, BO3) | [2399761](https://www.hltv.org/matches/2399761/private-vs-upgrade-cis-esports-league-cyberclash-season-2) | PRIVATE #95 1064 (5/5); UPGRADE #67 1185 (4/5, synyx in) | unique | 42.1 / 57.9 | UPGRADE | VRS_ROSTER_OUTDATED |
| Honvéd vs Lavked (16 Oct 18:54, BO3) | [2399762](https://www.hltv.org/matches/2399762/honvd-vs-lavked-cis-esports-league-cyberclash-season-2) | Honvéd #169 788 (3) vs #331 515 (2); Lavked #143 862 (4) | #169 | 45.1 / 54.9 | Lavked | VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED |
| Bebop vs Donstu (17 Oct 10:54, BO3) | [2399676](https://www.hltv.org/matches/2399676/bebop-vs-donstu-cct-2026-challengers-europe-series-8) | Bebop #212 702 (5) vs #282 597 (2); DONSTU #197 732 (4) | #212 | 48.0 / 52.0 | Donstu | VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED |
| ex-6666 vs Privateer (18 Oct 13:39, BO3) | [2399681](https://www.hltv.org/matches/2399681/ex-6666-vs-privateer-cct-2026-challengers-europe-series-8) | 6666 #127 923 (4) vs #368 425 (1); Privateer #271 608 (3) | #127 | 69.7 / 30.3 | ex-6666 | VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED |
| antidaun vs Phantom Academy (18 Oct 13:39, BO3) | [2399682](https://www.hltv.org/matches/2399682/antidaun-vs-phantom-academy-cct-2026-challengers-europe-series-8) | "Strael Bora" #217 692 (4) (IR-37); Phantom Academy #172 783 (4) | #217 | 44.0 / 56.0 | Phantom Academy | VALVE_NAME_AMBIGUOUS, VRS_ROSTER_OUTDATED |

Market checks for every row (all negatives recorded in the pack): HLTV betting tables show only the
Stake sweepstake promo cell; EGW's 1.8/1.8 placeholders rejected (F-28 class); no Pinnacle listing at
the 05:58Z capture; Polymarket's CyberClash surface carried only 15 Oct group-stage markets (search
read ~08:25Z); no named esportsbook relay in the 07:51Z capture. The vprognoze aggregator's 1.37/2.85
for EF–Betclic is recorded as context only and never used as a price (IR-40).

Formats (the strict gate requires an independently stated format): all eight are BO3 — stated by HLTV
(Best of 3 fields / event matches tab) and corroborated by EGW match pages and, for the PGL qualifier,
Liquipedia's Valve Tier 1 qualifier page.

Grading hygiene: the POST_LOCK row (1081493) is excluded from `pick_history.json` (tested:
`test_post_lock_research_is_never_graded_or_passed_off_as_pre_lock`); pre-lock research rows enter
history normally and freeze at lock.

Flagged additions: IR-37 (antidaun=Strael Bora rename), IR-38 (Y27 unratable — the one blank), IR-39
(six snapshot roster deltas, all flagged), IR-40 (post-lock research). None block publication.
