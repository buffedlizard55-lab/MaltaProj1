# Repository review and line-by-line verification — session `arena/a6f05f99` (15–16 Oct 2026)

**What this is.** A review of the repository as it stood when this session started, plus a
line-by-line verification of the board this session published under `a6f05f99/`. Every number in the
tables below is copied out of `a6f05f99/data/board.csv`; nothing was typed by hand. Where a value
could not be confirmed from an official source it is left blank and flagged — never inferred.

**Snapshot verified.** Hotspawn read **2026-10-15T21:34:19Z** (lobby, cs2-pickems and
thp-pickems, all HTTP 200). Pinnacle guest JSON read 2026-10-15 21:34Z. Polymarket read
2026-10-15 21:34Z. Valve Regional Standings **2026-10-05**
([file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)). HLTV world ranking read 2026-10-15 21:34Z
([page](https://www.hltv.org/ranking/teams)).

**How to re-check any row.** Open the Hotspawn link (fixture identity, lock time, points), then each
price link in the "Basis & sources" column and compare the odds with the read time printed on the
page. Own-line rows can be recomputed from the two Valve point totals with
P = 1/(1+10^(−k·Δ/400)), k = **0.4598** (k = 0.4598, fitted by session arena/22be6967 on 13,609 official Valve-rated matches (held-out log-loss 0.6395 vs 0.6541 for Valve's raw slope); see hotspawn/data/calibration.json and hotspawn/calibrate.py in this repository.).
Crowd percentages are ownership only and never enter a probability.

## 1. Coverage

- Hotspawn payload: **88** CS2 listings — **22 open**,
  5 locked, 61 stale (lock passed; not pickable).
- Open fixtures with a pick: **22/22**
  (0 unresolved).
- Independent estimates per open fixture: {'0': 0, '1': 3, '2': 12, '3': 7, '4': 0}.
- Highest rung reached per open fixture: {'1': 6, '2': 1, '3': 15, '4': 0, '5': 0}
  (1 Pinnacle · 2 bookmaker line relayed by bo3.gg · 3 Polymarket · 4 our own line · 5 hand-read).
- Leaderboard classes on the open slate: {'VALUE': 4, 'CONTRARIAN': 2, 'LONG SHOT': 4, 'CHALK': 11, 'SITUATIONAL': 1}.
- Single-source rows: **3** — JOGA DE TERNO v your end, Procyon v LOS NINOS, Infinite v Insiders.
- Next lock: **2026-10-16T07:54:00Z**.

**The five-rung ladder.** 1 Pinnacle (sharp book) → 2 bookmaker line relayed by bo3.gg →
3 Polymarket (prediction market, labelled as such) → 4 our own line from Valve's official standings
→ 5 hand-verified price (`research/manual_lines.json`) → UNRESOLVED. The published probability is
the mean of every rung that answered. Hotspawn's crowd percentage is never one of them.

## 2. Every open fixture, line by line

| Hotspawn | Match | Lock (UTC) | Tier/pts | Pick | Prob. A / B | Basis & sources | Our line (Valve pts) | HLTV | Crowd (ownership) | Plan | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|
| [1079586](https://play.hotspawn.com/lobby) | Ninjas in Pyjamas vs Team Liquid | 2026-10-16 07:54Z | B/3 | **Ninjas in Pyjamas** | 52.4% / 47.6% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-nip-tl1-2026-10-16) | 50.5% (1534 vs 1527, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/4411/ninjas-in-pyjamas) | 44% / 56% | VALUE → Ninjas in Pyjamas | ALIAS |
| [1080285](https://play.hotspawn.com/lobby) | Voca vs Phantom | 2026-10-16 07:54Z | C/2 | **Phantom** | 47.4% / 52.6% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-voc-pha-2026-10-16) | 52.3% (1182 vs 1147, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13499/voca) | 16% / 84% | CONTRARIAN → Voca |   |
| [1080286](https://play.hotspawn.com/lobby) | HAVU vs RoundsGG | 2026-10-16 09:54Z | C/2 | **HAVU** | 78.2% / 21.8% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-havu-rgg-2026-10-16) | 73.7% (937 vs 548, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/7865/havu) | 94% / 6% | LONG SHOT → HAVU | ALIAS |
| [1079630](https://play.hotspawn.com/lobby) | ex-RUSTEC vs Saint Sinners | 2026-10-16 10:54Z | B/3 | **ex-RUSTEC** | 55.7% / 44.3% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-rustec-ssins-2026-10-16) | 50.9% (824 vs 810, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13901/ex-rustec) | 88% / 13% | CONTRARIAN → Saint Sinners |   |
| [1080287](https://play.hotspawn.com/lobby) | Voca vs HAVU | 2026-10-16 11:54Z | C/2 | **Voca** | 65.7% / 34.3% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-voc-havu-2026-10-16) | 65.7% (1182 vs 937, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13499/voca) | 86% / 14% | CHALK → Voca |   |
| [1081498](https://play.hotspawn.com/lobby) | JOGA DE TERNO vs your end | 2026-10-16 12:54Z | C/2 | **your end** | 47.0% / 53.0% | Polymarket — [Polymarket](https://polymarket.com/event/cs2-jdt-youren-2026-10-16) | — (a team is missing from Valve's standings) | — | 71% / 29% | VALUE → your end | NO_VRS_TEAM, SINGLE_SOURCE |
| [1079631](https://play.hotspawn.com/lobby) | FORZE Reload vs Lavked | 2026-10-16 13:54Z | B/3 | **FORZE Reload** | 73.5% / 26.5% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-forzer-lavked-2026-10-16) | 65.2% (1100 vs 862, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/12857/forze-reload) | 86% / 14% | CHALK → FORZE Reload |   |
| [1080205](https://play.hotspawn.com/lobby) | Aurora vs 9z | 2026-10-16 13:54Z | S/7 | **Aurora** | 65.1% / 34.9% | Polymarket | Thunderpick (bookmaker), price relayed by bo3.gg | Our own line — [Polymarket](https://polymarket.com/event/cs2-aur1-9z-2026-10-16) | 61.3% (1716 vs 1543, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/11861/aurora) | 89% / 11% | SITUATIONAL → 9z | ALIAS, MANUAL_READ |
| [1080288](https://play.hotspawn.com/lobby) | Phantom vs RoundsGG | 2026-10-16 13:54Z | C/2 | **Phantom** | 86.2% / 13.8% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-pha-rgg-2026-10-16) | 83.0% (1147 vs 548, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13173/phantom) | 97% / 3% | CHALK → Phantom | ALIAS |
| [1081120](https://play.hotspawn.com/lobby) | mellren vs Privateer | 2026-10-16 13:54Z | C/2 | **mellren** | 80.4% / 19.6% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-mellre-pg5-2026-10-16) | 70.2% (932 vs 608, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13759/mellren) | 95% / 5% | CHALK → mellren |   |
| [1080289](https://play.hotspawn.com/lobby) | RoundsGG vs Voca | 2026-10-16 15:54Z | C/2 | **Voca** | 15.1% / 84.9% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-voc-rgg-2026-10-16) | 15.7% (548 vs 1182, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/12457/rounds) | 5% / 95% | CHALK → Voca | ALIAS |
| [1081502](https://play.hotspawn.com/lobby) | Procyon vs LOS NINOS | 2026-10-16 15:54Z | C/2 | **Procyon** | 65.0% / 35.0% | Polymarket — [Polymarket](https://polymarket.com/event/cs2-pcy-ln-2026-10-16) | — (a team is missing from Valve's standings) | [link](https://www.hltv.org/team/10997/procyon) | 86% / 14% | CHALK → Procyon | NO_VRS_TEAM, SINGLE_SOURCE |
| [1079589](https://play.hotspawn.com/lobby) | 100 Thieves vs Sangal | 2026-10-16 16:54Z | B/3 | **100 Thieves** | 63.2% / 36.8% | Pinnacle | Polymarket | Our own line — [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [Polymarket](https://polymarket.com/event/cs2-100t-sng2-2026-10-16) | 57.6% (1478 vs 1362, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/8474/100-thieves) | 88% / 13% | CHALK → 100 Thieves |   |
| [1079632](https://play.hotspawn.com/lobby) | BakS vs G2 Ares | 2026-10-16 16:54Z | B/3 | **BakS** | 64.8% / 35.2% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-baks-g2a-2026-10-16) | 58.6% (1044 vs 913, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/11699/baks) | 50% / 50% | CHALK → BakS |   |
| [1080290](https://play.hotspawn.com/lobby) | Phantom vs HAVU | 2026-10-16 17:54Z | C/2 | **Phantom** | 67.3% / 32.7% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-pha-havu-2026-10-16) | 63.5% (1147 vs 937, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13173/phantom) | 98% / 2% | LONG SHOT → Phantom |   |
| [1081526](https://play.hotspawn.com/lobby) | Infinite vs Insiders | 2026-10-19 08:54Z | B/3 | **Infinite** | 69.0% / 31.0% | Polymarket — [Polymarket](https://polymarket.com/event/cs2-inf6-ins-2026-10-19) | — (a team is missing from Valve's standings) | [link](https://www.hltv.org/team/10823/infinite) | 100% / 0% | LONG SHOT → Infinite | NO_VRS_TEAM, SINGLE_SOURCE |
| [1081527](https://play.hotspawn.com/lobby) | aimclub vs BASEMENT BOYS | 2026-10-19 08:54Z | B/3 | **BASEMENT BOYS** | 34.6% / 65.4% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-aim1-bmb-2026-10-19) | 19.7% (504 vs 1036, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/6810/aimclub) | 75% / 25% | VALUE → BASEMENT BOYS |   |
| [1081528](https://play.hotspawn.com/lobby) | BC.Game vs Drama | 2026-10-19 08:54Z | B/3 | **BC.Game** | 76.4% / 23.6% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-bcg-drama-2026-10-19) | 77.8% (1318 vs 845, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/12878/bcgame) | 100% / 0% | LONG SHOT → BC.Game | ALIAS |
| [1081529](https://play.hotspawn.com/lobby) | Nexus vs WROTBERRY | 2026-10-19 08:54Z | B/3 | **WROTBERRY** | 43.7% / 56.3% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-wbt-nxs1-2026-10-19) | 37.5% (1008 vs 1201, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/7187/nexus) | 75% / 25% | VALUE → WROTBERRY | ALIAS |
| [1081530](https://play.hotspawn.com/lobby) | Iberian Soul vs HyperSpirit | 2026-10-19 10:39Z | B/3 | **Iberian Soul** | 69.7% / 30.3% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-is-hs2-2026-10-19) | 75.0% (1218 vs 803, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13104/iberian-soul) | 75% / 25% | CHALK → Iberian Soul |   |
| [1081531](https://play.hotspawn.com/lobby) | Sashi vs mouz NXT | 2026-10-19 10:39Z | B/3 | **Sashi** | 74.7% / 25.3% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-sashi-mouzn-2026-10-19) | 82.9% (1131 vs 534, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | — | 75% / 25% | CHALK → Sashi |   |
| [1081532](https://play.hotspawn.com/lobby) | ASTRAL vs Leo | 2026-10-19 10:39Z | B/3 | **ASTRAL** | 65.8% / 34.2% | Polymarket | Our own line — [Polymarket](https://polymarket.com/event/cs2-ast-leo2-2026-10-19) | 82.0% (1072 vs 499, [Valve](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md)) | [link](https://www.hltv.org/team/13333/astral) | 50% / 50% | CHALK → ASTRAL |   |

Read times: Pinnacle 2026-10-15 21:34Z, Polymarket 2026-10-15 21:34Z,
Valve 2026-10-05, HLTV 2026-10-15 21:34Z. A source link is not proof of a current price —
always check the read time.

## 3. Thunderpick World Championship 2026 — days 1 and 2 graded, day 3 called

### Day 1 · 2026-10-14 · Group openers (both groups)

| Match | Result (HLTV) | Maps | Our pick before lock | Crowd (ownership) | Leaderboard play | Verdict |
|---|---|---|---|---|---|---|
| [9z vs Aurora](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) | **9z** 2-0 | Inferno 13-11, Nuke 13-1 | **Aurora** (73.0%) | 5% / 95% | 9z () | play won; pick lost |
| [Falcons vs Ninjas in Pyjamas](https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) | **Falcons** 2-0 | Ancient 16-13 (OT), Dust2 13-6 | **Falcons** (82.0%) | 90% / 10% | Falcons () | play won; pick won |
| [Legacy vs PARIVISION](https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026) | **Legacy** 2-0 | Dust2 13-11, Mirage 16-14 (OT) | **Legacy** (64.0%) | 75% / 25% | Legacy () | play won; pick won |
| [FURIA vs BETBOOM](https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026) | **FURIA** 2-0 | Ancient 13-10, Mirage 13-9 | **FURIA** (72.0%) | 90% / 10% | FURIA () | play won; pick won |

### Day 2 · 2026-10-15 · Winners' and elimination matches

| Match | Result (HLTV) | Maps | Our pick before lock | Crowd (ownership) | Leaderboard play | Verdict |
|---|---|---|---|---|---|---|
| [9z vs Falcons](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) | **Falcons** 2-1 | Nuke 9-13 (9z pick), Mirage 13-8 (Falcons pick, 9z win), Dust2 9-13 | **Falcons** (75.6%)<br>`pick_history.json` 2026-10-15 10:53Z | 6% / 94% | Falcons (LONG SHOT) | play won; pick won |
| [PARIVISION vs BetBoom](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) | **BetBoom** 2-1 | PARIVISION won map 1; BetBoom took maps 2 and 3, closing Mirage 13-7 | **PARIVISION** (53.4%)<br>`pick_history.json` 2026-10-15 10:57Z | 69% / 31% | BetBoom (CONTRARIAN) | play won; pick lost |
| [Legacy vs FURIA](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026) | **FURIA** 2-1 | Cache 10-13 (FURIA pick, Legacy steal), Inferno 5-13 (FURIA), Mirage 8-13 (FURIA) | **FURIA** (57.6%)<br>`pick_history.json` 2026-10-15 10:57Z | 27% / 73% | Legacy (CONTRARIAN) | play lost; pick won |
| [Aurora vs Ninjas in Pyjamas](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) | **Aurora** 2-0 | Cache 13-9, Dust2 13-7 | — (not listed on Hotspawn) | not published | — | — |

### Day 3 · 2026-10-16 · Group deciders (winner reaches the playoffs)

| Match | Result (HLTV) | Maps | Our pick before lock | Crowd (ownership) | Leaderboard play | Verdict |
|---|---|---|---|---|---|---|
| [Aurora vs 9z](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) | — | — | — (not listed on Hotspawn) | not published | — | not played yet |
| [BETBOOM vs Legacy](https://www.hltv.org/matches/2399413/betboom-vs-legacy-furia-loser-thunderpick-world-championship-2026) | — | — | — (not listed on Hotspawn) | not published | — | not played yet |

**Ledger.** 5 of 7 published picks correct; 6 of 7 leaderboard plays correct; 42 points if you took
every play, 35 if you took the crowd favourite every time.

**Provenance of that ledger — read this before quoting it.** Only 3 of the 7 rows have a frozen
pre-lock record in this repository (`hotspawn/data/pick_history.json`, entries flagged
`frozen: true`): those are the three day-2 matches published before their locks. The four day-1 rows
are **not** a live record. They are itemised in `reviews/22be6967-verification.md` section 3 and were
produced by rule v2 *in sample* (n = 4) after the results were known; `hotspawn/data/summary.json`
records the aggregate under `day1_review` (3 of 4 picks, 4 of 4 plays). So the honest statement is:
**day 2 (live, out of sample) went 2 of 3 on picks and 2 of 3 on plays**, and the 5-of-7 / 6-of-7
headline mixes that with a retrospective. Seven graded matches is far too few to tune a rule on,
which is why rule v3 keeps v2's thresholds and only changes how the underdog's chance is *measured*.

**The day-3 call.** Aurora vs 9z is the only Thunderpick fixture Hotspawn still lists for 16 Oct
(id `1080205`, 7 points, lock 2026-10-16 13:54Z). Our published number is **65% / 35%** from three
rungs — Polymarket 68.5/31.5, the Thunderpick book line relayed by bo3.gg at 1.42/2.70, our own
Valve line 61.3/38.7 — class SITUATIONAL, **leaderboard play 9z**: 9z is a 35% chance against 11%
ownership and a verified roster factor counts against Aurora. Taking 9z instead of Aurora gives up
about 2.1 points of expectation on our own numbers; it pays only if 9z is better than 35%.

**Why 9z is not a silly play.** On day 2, 9z lost 1-2 to Falcons but took Falcons' own Mirage pick
13-8 and lost the other two maps 9-13 — a competitive series against the group winner, not a
collapse. On day 1 they beat this same Aurora 2-0 (Inferno 13-11, Nuke 13-1).

## 4. Situational factors used by the leaderboard rule (official HLTV pages)

| Team | Factor | Strength | As of | Summary | Sources |
|---|---|---|---|---|---|
| aurora | roster change (new in-game leader + new player + new coach) | moderate | 2026-07-08 | Aurora rebuilt around their Turkish core (XANTARES, woxic, Wicadia) in July 2026: MAJ3R stepped down and soulfly was benched on 2 July, Jimpphat signed from MOUZ on 3 July, ash became head coach on 3 July and kyxsan joined from Falcons as in-game leader on 8 July. That is about 100 days before the day-3 decider, and the rebuilt five has since reached the StarSeries Fall final (HLTV news, 19 Sep 2026) and sits 5th on Valve's official standings. Treat the churn as a tiebreak on a close match, not as evidence of a broken team. | [link](https://www.hltv.org/news/45057/jimpphat-signs-with-aurora) [link](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan) [link](https://www.hltv.org/team/11861/aurora) [link](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) |
| parivision | roster change (player swap 28 days before the event) | strong | 2026-09-17 | HObbit replaced the benched slaxejezzz on 17 Sep 2026. Valve's 2026-10-05 standings still list the old five, so Valve points describe a roster that no longer plays. PARIVISION lost 0-2 to Legacy and 1-2 to BetBoom and are eliminated from Thunderpick. | [link](https://www.hltv.org/news/45534/parivision-replace-slaxejezzz-with-hobbit) [link](https://www.hltv.org/team/12467/parivision) [link](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) |
| nip | late call-up (five days' notice) | strong | 2026-10-09 | Ninjas in Pyjamas replaced Virtus.pro at Thunderpick after Virtus.pro withdrew (visa issue for AquaRS, health of F0R3VER); announced 9 Oct 2026. They lost 0-2 to Falcons and 0-2 to Aurora and are eliminated. They have an ordinary league match on 16 Oct against Team Liquid in which this factor no longer applies as an event-specific call-up, but the short preparation window does. | [link](https://www.hltv.org/news/45688/thunderpick-world-championship-matchups-announced-with-virtuspro-replaced-by-nip) [link](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) |
| 9z | schedule load (third best-of-three in three days) | weak | 2026-10-16 | 9z played Aurora on 14 Oct 08:30 UTC, Falcons on 15 Oct 11:00 UTC and meet Aurora again on 16 Oct 14:00 UTC - three best-of-threes in three days at a LAN. Aurora's schedule is the same shape (14 Oct 08:30, 15 Oct 08:30, 16 Oct 14:00), so this is close to symmetric and is recorded as context only; it never moves a pick. | [link](https://www.hltv.org/results?event=8932) [link](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) |
| aurora | schedule load (third best-of-three in three days) | weak | 2026-10-16 | Same as the 9z entry above: Aurora also play their third best-of-three in three days on 16 Oct. Context only. | [link](https://www.hltv.org/results?event=8932) |

Factors never move a probability. They only decide whether a match qualifies as SITUATIONAL, which
is what allows the leaderboard rule to back an underdog.

## 5. Team-name aliases (each proven by fixture slot, never assumed)

| Key | Names joined | Evidence | Sources |
|---|---|---|---|
| wbt | WROTBERRY, WBT | HLTV's Elisa BreakOut Series 2 schedule lists 'WBT vs ENCE' (match 2399420) and 'WBT vs BOJONG' (2399422) in exactly the slots Hotspawn lists as WROTBERRY vs ENCE (1080281, 12:00 UTC) and WROTBERRY vs BOJONG (1080283, 16:00 UTC); Pinnacle's 'CS2 - Elisa BreakOut' league prices 'WBT vs ENCE' 12:00 UTC and 'WBT vs BOJONG' 16:00 UTC; Valve's standings list WBT (#60). | [link](https://www.hltv.org/events/9332/matches) [link](https://www.hltv.org/matches/2399420/wbt-vs-ence-elisa-breakout-series-2) |
| rounds | RoundsGG, ROUNDS, Rounds | HLTV's Elisa BreakOut Series 2 schedule lists 'HAVU vs ROUNDS' (2399425), 'Phantom vs ROUNDS' (2399427) and 'Voca vs ROUNDS' (2399428) in the slots Hotspawn lists with RoundsGG (1080286, 1080288, 1080289); Valve's standings list ROUNDS (#310). | [link](https://www.hltv.org/events/9332/matches) [link](https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2) |
| parivision | PVISION, PARIVISION | Pinnacle's 'CS2 - TP World Championship' league lists 'PVISION vs BB Team' at 13:30 UTC on 2026-10-15, the slot of HLTV match 2399410 PARIVISION vs BETBOOM and Hotspawn 1080203 PARIVISION vs BetBoom; Polymarket names the same market 'PARIVISION vs BetBoom Team'. | [link](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) [link](https://polymarket.com/event/cs2-prv-bb3-2026-10-15) |
| betboom | BetBoom, BB Team, BetBoom Team, BETBOOM | Same fixture slot as above (HLTV writes BETBOOM, Hotspawn BetBoom, Pinnacle 'BB Team', Polymarket 'BetBoom Team'); Valve's standings list BETBOOM (#11). | [link](https://www.hltv.org/team/12394/betboom) [link](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) |
| nip | NIP, NiP, Ninjas in Pyjamas | Polymarket market cs2-aur1-nip-2026-10-15 'Aurora Gaming vs NIP - Thunderpick World Championship Group A' is HLTV match 2399408 Aurora vs Ninjas in Pyjamas (Hotspawn 1080201). | [link](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) [link](https://polymarket.com/event/cs2-aur1-nip-2026-10-15) |
| aurora | Aurora Gaming | Same Polymarket market as above ('Aurora Gaming'); HLTV team page names the team Aurora. | [link](https://www.hltv.org/team/11861/aurora) |
| falcons | Team Falcons | Polymarket market cs2-9z-fal2-2026-10-15 '9z vs Team Falcons' (gameStartTime 2026-10-15 11:00 UTC) is HLTV match 2399409 9z vs Falcons (Hotspawn 1080202). | [link](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) [link](https://polymarket.com/event/cs2-9z-fal2-2026-10-15) |
| bcgame | BC.Game Esports, BC.Game | Polymarket 'MIBR vs BC.Game Esports - Stake Pulse Beat III Group D' and Pinnacle 'MIBR vs BC.Game' (10:00 UTC) are the Hotspawn Stake Pulse Beat III MIBR vs BC.Game fixture. | [link](https://polymarket.com/event/cs2-mibr-bcg-2026-10-15) |
| eac | Esport Academy Copenhagen, EAC | Polymarket's Elisa BreakOut Series #2 Group A markets 'Esport Academy Copenhagen vs BOJONG' (slug cs2-eac-bojong-2026-10-15, 14:00 UTC) and 'Esport Academy Copenhagen vs ENCE' (cs2-eac-ence-2026-10-15, 18:00 UTC) sit in exactly the slots of HLTV matches 2399421 'EAC vs BOJONG' and 2399423 'EAC vs ENCE' (Hotspawn 1080282/1080284); Valve's standings list EAC (#103). NOT the same team as 'EAC Extra' (European Pro League), which stays separate. | [link](https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2) [link](https://polymarket.com/event/cs2-eac-bojong-2026-10-15) [link](https://polymarket.com/event/cs2-eac-ence-2026-10-15) |

Never aliased on purpose: Hotspawn's `ASTRAL` is **not** Astralis, and `Phantom` is **not** Phantom
Academy. The matcher requires both team names plus a kickoff inside six hours before any outside
price is joined to a fixture.

## 6. Hand-verified prices (no automated source priced these)

| Match | Source | Odds A / B | Read (UTC) | Page | Note |
|---|---|---|---|---|---|
| Aurora vs 9z | Thunderpick (bookmaker), price relayed by bo3.gg | 1.42 / 2.7 | 2026-10-15T22:55:00Z | [link](https://bo3.gg/matches/aurora-gaming-vs-9z-16-10-2026) | Two-way moneyline shown on the match page ('view all markets: 1 1.42 / 2 2.70'). The page's bet link goes to Thunderpick, and bo3.gg's API names the provider in bet_updates.provider. Also cross-checked on the same page: Aurora to win at least one map 1.13, 9z +1.5 maps 1.50. |
| BETBOOM vs Legacy | Thunderpick (bookmaker), price relayed by bo3.gg | 2.5 / 1.48 | 2026-10-15T22:55:00Z | [link](https://bo3.gg/matches/legacy-br-vs-betboom-team-16-10-2026) | Group B decider. Stated here for context only: Hotspawn does not list this match, so no pick'em pick is made for it and it is not counted in the board's coverage numbers. |

Each is tagged `MANUAL_READ` and carries the exact page, provider and read time. It is dropped from
the average once it is more than eight hours old, like any other price.

## 7. Irregularities found (published on the Flagged page rather than silently fixed)

1. **Duplicate Hotspawn listing.** Legacy v FURIA appeared twice on 15 Oct (ids `1080204` 16:00 UTC
   and `1081614` 17:00 UTC) for the same match, priced identically. Only one should count.
2. **Hotspawn does not list every match of an event.** Aurora v Ninjas in Pyjamas (15 Oct) and
   BETBOOM v Legacy (16 Oct, Group B decider) are on
   [HLTV](https://www.hltv.org/results?event=8932) but have no row in any capture this repository
   holds, so there is no pick'em pick to make for them.
3. **Settled fixtures vanish from the payload.** 9z v Falcons and PARIVISION v BetBoom were captured
   before lock on 15 Oct and are gone from the 21:34 UTC capture. Grading therefore depends on
   HLTV, not on Hotspawn; the pre-lock numbers survive in `hotspawn/data/pick_history.json`.
4. **One fixture has an unnamed opponent.** Hotspawn lists `1079628` Gothic v *LFO 10*. The
   counterpart book page names only a line-up (Jackinho, Sapec, dottie, flaw, tvs) and never a team,
   so the identity is flagged rather than asserted.
5. **Valve's snapshot predates some roster moves.** The newest official file is 2026-10-05;
   PARIVISION's 17 Sep swap of slaxejezzz for HObbit is not in it. Rows affected are flagged
   `VRS_ROSTER_OUTDATED` and the own line is dropped when the change is under 60 days old.
6. **Prediction markets are not bookmakers.** Polymarket prices are labelled as market opinion
   everywhere and averaged with bookmaker prices rather than substituted for them.
7. **Relayed bookmaker prices.** bo3.gg and EGamersWorld name the provider but link through an
   affiliate redirect, so these rungs are published with the provider and the exact page rather than
   passed off as a direct book read.

## 8. State of the repository when this session started

- **23 merged PRs** in the last two days from 20+ parallel sessions; `COORDINATION.md` is the claim
  ledger and is now 557 KB — read slices, not the whole file.
- **Two red checks on `main`, both pre-existing and neither caused by this session:**
  - `tests/test_228bb5bc.py::CommittedBoard::test_every_open_fixture_has_a_pick_or_explicit_unresolved_flag`
    — the console board publishes a probability for `1080202` with no pick. Session `228bb5bc` has
    been inactive since 14 Oct.
  - the `O-01 own-line model (VRS)` check.
- **Overlapping boards.** `hotspawn/`, `leaderboard/`, `valuepicks/`, `executive/`, `board/`, `cs2/`
  and now `a6f05f99/` each keep their own captures and pages for the same fixtures. They disagree in
  places because they read at different times with different ladders. All are linked from the
  landing page; none was deleted or overwritten by this session.

## 9. Known gaps in this session's board

- `a6f05f99/collect.py` **has been executed end to end** and does not crash, but this sandbox can
  only reach `github.com` and `api.github.com`, so Hotspawn, Pinnacle, bo3.gg, Polymarket and HLTV
  could not be read live here. What that run *did* verify: every one of those five sources fell back
  to its previous capture **with the original read time** rather than being relabelled as fresh, the
  run still exited 0, and the board rebuilt unchanged afterwards. What it did **not** verify: the
  request parameters for Hotspawn, Pinnacle, bo3.gg and Polymarket, which are copied from other
  sessions' collectors. The first scheduled GitHub Actions run exercises them.
- One real defect was found and fixed by that exercise: `collect_vrs` listed `/contents/live`, which
  returns *directories* (`2024`, `2025`, `2026`) rather than files, so the regular expression for
  `standings_global_*.md` could never match and the live Valve read could never succeed. It now lists
  `/contents/live/<year>` for the current and previous year. Re-run and confirmed:
  `standings_global_2026_10_05.md @ eec4853d7b`, 380 teams, mode `live`.
- The `bo3.gg` rung in today's board therefore comes from a hand-verified price
  (`research/manual_lines.json`) rather than an automated read.
- No headless-browser check of the phone layout ran in CI. The pages are single-column with a
  viewport meta tag and 44 px tap targets, and `a6f05f99/tests.py` asserts the viewport tag and that
  every internal link resolves, but a real device render has not been captured.

## 10. Links for manual review

| What | Where |
|---|---|
| Executive summary (start here) | [a6f05f99/index.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/index.html) |
| All picks and probabilities | [a6f05f99/picks.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/picks.html) |
| Thunderpick day 3 | [a6f05f99/twc.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/twc.html) |
| Unresolved and limitations | [a6f05f99/unresolved.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/unresolved.html) |
| Method and sources | [a6f05f99/method.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/method.html) |
| Flagged for review | [a6f05f99/flagged.html](https://buffedlizard55-lab.github.io/MaltaProj1/a6f05f99/flagged.html) |
| Board rows (CSV) | `a6f05f99/data/board.csv` |
| Coverage snapshot (JSON) | `a6f05f99/data/coverage.json` |
| TWC 2026 research (days 1–3) | `a6f05f99/research/twc2026.json` |
| Situational factors | `a6f05f99/research/factors.json` |
| Hand-verified prices | `a6f05f99/research/manual_lines.json` |
| Aliases and evidence | `a6f05f99/research/aliases.json` |
| Hotspawn lobby (fixture source) | https://play.hotspawn.com/lobby |
| HLTV TWC 2026 results | https://www.hltv.org/results?event=8932 |
| Valve Regional Standings | https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md |
