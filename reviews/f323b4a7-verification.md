# Line-by-line verification — session `arena/f323b4a7` (2026-10-16)

Scope: the live day-3 Hotspawn CS2 board under `f323b4a7/`. Every value below is either copied
from a capture stored in this repository (with its read timestamp) or read by this session from a
primary source. Where a value could not be confirmed it is left blank and published on
`f323b4a7/flagged.html`.

## 1. What was read, when, from where

| # | Fact | Value | Source | Read / as of |
|---|------|-------|--------|--------------|
| 1 | Hotspawn CS2 fixture count | 95 ("All tiers (95)") | https://play.hotspawn.com/lobby | 2026-10-16T04:18:00Z |
| 2 | Hotspawn week text | "123 matches this week" | https://play.hotspawn.com/lobby | 2026-10-16T04:18:00Z |
| 3 | Tier split | B 38 / C 54 / S 3 | https://play.hotspawn.com/lobby | 2026-10-16T04:18:00Z |
| 4 | Per-tournament counts | 18 tournaments summing to 95 | https://play.hotspawn.com/lobby | 2026-10-16T04:18:00Z |
| 5 | Prior capture size | 86 CS2 fixtures | https://play.hotspawn.com/lobby (TransferState, repo copy) | 2026-10-15T22:41:15Z |
| 6 | Lock offset | `lock_offset_sec = 360` on all 86 captured fixtures | TransferState payload | 2026-10-15T22:41:15Z |
| 7 | Kick-off display offset | rendered time = UTC − 4 h | verified on 6 captured fixtures | 2026-10-16T04:18:00Z |
| 8 | Pinnacle CS2 moneyline snapshot | 6 open fixtures priced | https://www.pinnacle.com/en/esports/games/cs2/matchups/ | 2026-10-15T22:41:17Z |
| 9 | Polymarket snapshot | 16 open fixtures priced | https://gamma-api.polymarket.com/markets?slug=cs2-aur1-9z-2026-10-16 | 2026-10-15T22:41:17Z |
| 10 | Polymarket live re-read, Aurora–9z | 0.695 / 0.305 | Polymarket gamma API, `updatedAt 2026-10-16T04:23:06.938887Z` | 2026-10-16T04:23:06Z |
| 11 | Valve standings snapshot | 2026-10-05 global, 349 teams parsed | ValveSoftware/counter-strike_regional_standings @ eec4853 | 2026-10-05 |
| 12 | Own-line slope | k = 0.4598, 13,609 train / 901 hold-out, hold-out log-loss 0.6395 vs 0.6541 raw | `hotspawn/data/calibration.json` | 2026-10-15T22:41:28Z |
| 13 | HLTV world ranking | ranks used as labelled context only | https://www.hltv.org/ranking/teams/2026/october/12 | 2026-10-15T22:41:23Z |
| 14 | TWC 2026 dates / prize / field | Oct 14–18 2026, $1,000,000, 8 teams, Malta | https://www.hltv.org/events/8932/thunderpick-world-championship-2026 | 2026-10-16T04:28:00Z |
| 15 | TWC 2026 format | two 4-team groups → single-elimination playoff, BO5 grand final | same page | 2026-10-16T04:28:00Z |
| 16 | Group A results | 9z 2-0 Aurora; Falcons 2-0 NiP; Falcons 2-1 9z; Aurora 2-0 NiP; decider 9z v Aurora | same page | 2026-10-16T04:28:00Z |
| 17 | Group B results | Legacy 2-0 PARIVISION; FURIA 2-0 BetBoom; FURIA 2-1 Legacy; BetBoom 2-1 PARIVISION; decider BetBoom v Legacy | same page | 2026-10-16T04:28:00Z |
| 18 | Day-3 kick-offs | Aurora–9z 14:00Z; BetBoom–Legacy 17:00Z | https://www.hltv.org/events/8932/matches + Polymarket `gameStartTime` | 2026-10-16T04:26:00Z |
| 19 | Playoff schedule | SF1 2026-10-17 FURIA v Aurora/9z winner; SF2 Falcons v BetBoom/Legacy winner; 3rd-place decider and BO5 final 2026-10-18 | https://www.hltv.org/events/8932/matches | 2026-10-16T04:26:00Z |
| 20 | Aurora ranks | HLTV #6, Valve #9 / 1716 pts | HLTV betting analytics 2399412; Valve 2026-10-05 | 2026-10-16T04:30:00Z |
| 21 | 9z ranks | HLTV #17, Valve #24 / 1543 pts | HLTV betting analytics 2399412; Valve 2026-10-05 | 2026-10-16T04:30:00Z |
| 22 | BetBoom / Legacy ranks | HLTV #14 / #7; Valve #11 / 1596 pts and #2 / 1931 pts | HLTV betting analytics 2399413; Valve 2026-10-05 | 2026-10-16T04:30:00Z |
| 23 | Aurora lineup | XANTARES, woxic, Wicadia, kyxsan, Jimpphat; coach ash | HLTV analytics 2399412; Hotspawn match page 1080205 | 2026-10-16T04:20:00Z |
| 24 | Aurora rebuild date | announced 2026-07-08/09 | https://www.strafe.com/news/read/aurora-locks-in-new-cs2-roster-with-kyxsan-and-jimpphat/ | 2026-10-16T04:33:00Z |

## 2. Verified joins (alias handling)

Only equivalences already evidenced in `hotspawn/research/aliases.json` were used, plus generic-word
normalisation. No new alias was invented.

| Hotspawn name | Joined to | Evidence |
|---------------|-----------|----------|
| RoundsGG | ROUNDS (Valve #310, 548 pts) | `hotspawn/research/aliases.json`, HLTV Elisa schedule slots |
| WROTBERRY | WBT (Valve #60, 1201 pts) | `hotspawn/research/aliases.json`, HLTV/Pinnacle fixture slots |
| Team Liquid | Liquid (Valve #19, 1527 pts) | generic word "Team" dropped; Valve lists "Liquid" |
| banda chuya | Banda Chuya (Valve #373, 402 pts) | case-insensitive match |

Teams genuinely absent from Valve's standings: **JOGA DE TERNO, LOS NINOS, Insiders, Infinite**.
All four appear in fixtures that do carry a Polymarket price, so no row needed the unresolved rung.

## 3. The 31 open fixtures and how each probability was produced

Rung A (Pinnacle, margin removed proportionally) — 6 rows: 1079586, 1080286, 1080287, 1080289,
1079589, 1079631.
Rung B (Polymarket, normalised) — 16 rows: 1080285, 1079630, 1081498, 1080205 (live re-read),
1080288, 1081120, 1081502, 1079632, 1080290, 1081526, 1081527, 1081528, 1081529, 1081530,
1081531, 1081532.
Rung C (own line, Valve points, k = 0.4598) — 9 rows: 1079167, 1081712, 1079588, 1081769,
1081775, 1079170, 1079171, 1079173, 1081126.
Rung D (unresolved) — 0 rows.

Full per-row detail with both probabilities, the basis label, the Valve points, the HLTV ranks and
the source links: `f323b4a7/picks.html` and `f323b4a7/data/picks.csv`.

## 4. Irregularities (published on `f323b4a7/flagged.html`)

| ID | Irregularity | Handling |
|----|--------------|----------|
| F-01 | The brief calls Aurora's roster change "recent"; it is a 2026-07-08/09 rebuild and Valve's standings already contain that five | Flagged; no roster adjustment applied |
| F-02 | Hotspawn's CS2 count moved from 86 (22:41Z capture) to 95 (04:18Z live) | All 95 itemised in `f323b4a7/all.html`; the 9 additions listed |
| F-03 | 9 open fixtures have no Pinnacle or Polymarket price | Rung C own line, labelled per row, register on `unresolved.html` |
| F-04 | Hotspawn renders kick-offs in UTC−4 | Derivation verified on 6 fixtures before use |
| F-05 | 1081775 and 1081712 were added after the market snapshot | No outside price captured; flagged |
| F-06 | `best_of` is null for the 9 new fixtures | No format assumed, no transform applied |
| F-07 | HLTV rank blank for 12 of the 62 teams in the open set | Left blank, never inferred |
| F-08 | Day-1 Hotspawn fixture ids for 3 of 4 opening matches not captured | Left blank on the review page |

## 5. Checks run

- `python3 f323b4a7/tests.py` → pass (31 rows; pick = higher-probability side; p_a + p_b = 1;
  rung and basis present; Hotspawn link present; 8 pages exist, carry a viewport meta tag and have
  no broken local links).
- `python3 f323b4a7/mobile_check.py` → pass at 390 px (static mode; no headless browser in the
  sandbox, the workflow installs one).
- `python3 -m unittest tests.test_landing_43c32386` → 4/4 pass after the additive root link block.
- `python3 -m unittest discover -s tests` → 405 tests, **3 failures, all pre-existing** and
  reproduced on the untouched `main` tree: `test_457629c4` determinism error and two
  `test_7759beef` board tests. Root cause is outside this session's scope.

## 6. What this board deliberately does not do

- It never uses Hotspawn's crowd pick share as a probability; the share is stored as ownership and
  only feeds the labelled leaderboard rule.
- It never fills a blank with an inferred value. Blank means "not confirmed from an official source".
- It never invents a Hotspawn pick for a fixture Hotspawn does not list (the TWC semi-finals and
  final are context only).
