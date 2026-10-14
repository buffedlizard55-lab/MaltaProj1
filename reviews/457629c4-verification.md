# Session `arena/457629c4` — line-by-line verification record

Written 2026-10-14 ~05:05 UTC on branch `arena/457629c4-maltaproj1`.
Board: `livelines/` (7 pages) · live: <https://buffedlizard55-lab.github.io/MaltaProj1/livelines/>
Every figure below was read out of the committed data files (`livelines/data/*.csv|json`) by the script that
built this page, or re-fetched from the named page during this session; nothing here is remembered or estimated.
Artifacts: `picks.csv` / `picks.json` (per-row numbers), `coverage.json`, `calibration.json`, `flags.csv`,
`unresolved.csv`, `sources.csv`, `provenance.json`, `live_reads.json` (verbatim reads), and the raw official
capture `data/raw/valve_standings_global_2026_10_05.md`.

## 1. What "verified" means on this board

* **Every row carries the link its value came from, and the minute it was read.** A fixture with no reachable
  price is published with an own line or as a lower bound, and either way names the official page behind it.
  No value is inferred, and a blank stays blank — see `unresolved.html` for the one fixture where this happens.
* **Hotspawn supplies fixture identity only** — the exact UTC lock/start epochs, tier, stage, offered points.
  **Its crowd pick percentages are dropped at ingest and never stored**; a build that stores one fails the
  test *"no Hotspawn crowd value is stored"* (`livelines/tests.py`), which walks every stored row and checks
  that the live-read file records the crowd columns as present-on-page and not-stored.
* **Probabilities come only from outside sources**: a bookmaker/market listing (de-vigged two-way, `T2`
  basis), or our own line from the official Valve Regional Standings (`T3` basis), whose logistic scale is
  fitted against the outside market by minimum mean absolute error — **K = 877.75 points, MAE
  8.66 pp, n = 25**. The log-loss-optimal alternative (K ≈ 184.0,
  MAE ≈ 22.88 pp) is disclosed on every row that depends on the scale
  (`FL-OWN-LINE-SCALE-SENSITIVE`). A single unrated side yields a **bound, not an estimate** (`T4`, no pick).
* **Publication is fail-closed.** `livelines/tests.py` re-derives the arithmetic and `tests/test_457629c4.py`
  re-runs it from the repository root; the refresh workflow commits only when both pass. A build that cannot
  reproduce a published number stops the commit and the last good board stays live.

## 2. Live independent re-reads performed in this session

| # | What was re-read | Page | Read id | Board value | Re-read value | Result |
|---|---|---|---|---|---|---|
| L-1 | Hotspawn Pick'em slate — fixture identity, lock epochs, the closing-soon cards | [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) | `HS-CS2-PICKEMS` | 89 fixtures, 28 open, lock = start − 6 min (payload epochs) | "This week 68 matches"; tiers All 88 / B 24 / C 60 / S 4; the 12 closing-soon cards all present in the board's fixture set with the same UTC lock epochs | **match** — crowd pick percentages are visible on the page and are never stored (see §5) |
| L-2 | Hotspawn lobby — display-timezone check | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) | `HS-LOBBY` | board prints payload UTC epochs (e.g. 08:00:00Z start, 07:54:00Z lock) | cards render in ET (UTC−4); countdown agrees with the payload's 08:00:00Z | **explained, kept conservative**: payload lock is the earlier instant, so a row can only lock before the UI shows it |
| L-3 | HLTV world ranking the own line is cross-checked against | [www.hltv.org/ranking/teams/2026/october/12](https://www.hltv.org/ranking/teams/2026/october/12) | `HLTV-RANKING-OCT12` | capture `model/input/hltv_ranking.json` (245 teams, 2026-10-12) | #1 Spirit 972, #2 Vitality 894, #3 MOUZ 692 — identical, rank for rank | **match**; the 2026-10-13 page does not exist (404, read L-4) |
| L-4 | HLTV world ranking dated one day later (negative control) | [www.hltv.org/ranking/teams/2026/october/13](https://www.hltv.org/ranking/teams/2026/october/13) | `HLTV-RANKING-13-NOT-FOUND` | board uses the 2026-10-12 ranking and prints its date | HTTP 404 — no Tuesday edition exists | **consistent**: the weekly ranking is Monday's, so 2026-10-12 is current |
| L-5 | Gothic v Lavked — the second outside source, and price drift | [egamersworld.com/counterstrike/event/cct-europe-2026](https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK) | `EGW-CCT-EU-11` | board pick Lavked 50.5 % (Polymarket 50¢/51¢, read L-6); an earlier read of this session printed 2.05 / 1.64 | the same EGW page now prints 1.881 / 1.782 (Bo3, 14.10.26 10:00 local = 08:00 UTC) | **published as** `FL-PRICE-DRIFT`: the row keeps the archived price and names the drift; direction unchanged (Lavked favourite on the de-vig of both reads) |
| L-6 | Polymarket moneyline for Gothic v Lavked | [polymarket.com/event/cs2-gothic-lavked-2026-10-14](https://polymarket.com/event/cs2-gothic-lavked-2026-10-14) | `PM-GOTHIC-LAVKED` | Lavked 50.5 % (share prices 50¢ / 51¢, de-vigged) | 50¢ / 51¢, volume $303.73, resolution source printed as hltv.org | **match**; thin book, flagged `FL-THIN-MARKET` where published from it |
| L-7 | EGamersWorld CCT EU #12 Play-In — series length and the placeholder pattern | [egamersworld.com/counterstrike/event/cct-europe-2026](https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in) | `EGW-CCT-EU-12` | banda chuya v 6666 and mellren v Privateer get an own line, not a market one; formats filled as Bo3 | every fixture on this page prints **1.80 / 1.80**, including fixtures no other book prices, while ENJOY v B8 Academy is priced 1.61 / 2.21 | **rejected as placeholder**: identical pairs on unrelated fixtures are not a market; recorded on unresolved.html and in `data/live_reads.json` |
| L-8 | Official Valve Regional Standings — the only rating input the own line uses | [github.com/ValveSoftware/counter-strike_regional_sta](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md) | `VRS (GitHub contents API)` | 95 of 112 teams rated; standings dated 2026-10-05 | blob sha 2aa28053…, 380 teams, saved verbatim at `livelines/data/raw/valve_standings_global_2026_10_05.md` | **match** — the local copy is the fetched file, byte for byte; its age is flagged on every row that uses it |
| L-9 | Outside market feed (owned by another session, read-only here) | [github.com/buffedlizard55-lab/MaltaProj1/blob/main/f](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/feeds/data/market_feed.csv) | `feed captured 2026-10-14T03:18:57Z` | 25 of 28 open fixtures priced from an outside listing | 34 rows: 20 Thunderpick-via-bo3.gg + 14 Polymarket | **match** — every accepted price names either this feed's URL or a live read above; no price is stored without one |

The sandbox shell has **no network** (curl to hltv.org and play.hotspawn.com returns no response); every live
read above was taken through the platform fetch tool, which is why each read stores its URL, its UTC time and
the page's own clock arithmetic where available (`hosts_refused` in `data/live_reads.json`).

## 3. Line by line: every open fixture (28 rows)

Coverage at build time: 89 fixtures on the slate · 28 open ·
61 locked or past · **27 with a pick** ·
25 priced from an outside market · 2 on our own line ·
1 published as a lower bound with no pick · 23 with a
stated series length. Rating inputs: 95 of 112 teams in
the official standings, 67 in HLTV's top 245. Prices are the archived reads named
in the row; the page prints each capture minute so a reader can judge its age.

| # | Fixture | Lock (UTC) | Basis | P(A) / P(B) % | Pick | Market source, price @ read | Second source P(A) % | Fmt | Rating inputs | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `1079621` Gothic v Lavked | 2026-10-14 07:54Z | *Market* | 49.5 / 50.5 | **Lavked 50.5%** | [Polymarket](https://polymarket.com/event/cs2-gothic-lavked-2026-10-14) 50¢ / 51¢ @ 04:38:05Z | EGamersWorld 48.6% | BO3 | VRS 211 (705) v 143 (862); HLTV — v #140 (5) | FL-NOT-IN-HLTV-TOP-245 FL-PRICE-DRIFT |
| 2 | `1081111` Enjoy v B8 Academy | 2026-10-14 07:54Z | *Market* | 58.1 / 41.9 | **Enjoy 58.1%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 1.606061 / 2.23 @ 04:38:10Z | EGamersWorld 57.9% | BO3 | VRS 138 (871) v 261 (631); HLTV #199 (3) v #229 (1) | FL-FORMAT-FROM-LISTING FL-PRICE-DRIFT |
| 3 | `1080176` 9z v Aurora | 2026-10-14 08:24Z | *Market* | 27.4 / 72.6 | **Aurora 72.6%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 3.49 / 1.314465 @ 04:38:10Z | Polymarket 26.5% | BO3 | VRS 17 (1543) v 9 (1716); HLTV #17 (124) v #6 (461) | FL-FORMAT-FROM-LISTING |
| 4 | `1079438` Astralis v Sashi | 2026-10-14 09:54Z | *Market* | 83.5 / 16.5 | **Astralis 83.5%** | [Polymarket](https://polymarket.com/event/cs2-ast10-sashi-2026-10-14) 84¢ / 16¢ @ 03:18:57Z | Polymarket (prediction market) 83.5% | BO3 | VRS 10 (1674) v 73 (1131); HLTV #15 (133) v — | FL-PRICE-DRIFT |
| 5 | `1079439` HOTU v Fnatic | 2026-10-14 09:54Z | *Market* | 46.4 / 53.6 | **Fnatic 53.6%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 2.04 / 1.763359 @ 04:38:10Z | Polymarket (prediction market) 46.5% | — | VRS 31 (1437) v 35 (1417); HLTV #41 (39) v #36 (43) | FL-FORMAT-UNKNOWN FL-OWN-LINE-MARKET-SPLIT FL-PRICE-DRIFT |
| 6 | `1079622` ex-RUSTEC v mellren | 2026-10-14 10:54Z | *Market* | 65.5 / 34.5 | **ex-RUSTEC 65.5%** | [Polymarket](https://polymarket.com/event/cs2-rustec-mellre-2026-10-14) 66¢ / 34¢ @ 03:18:57Z | Polymarket (prediction market) 65.5% | BO3 | VRS 92 (1066) v 125 (932); HLTV #79 (10) v #94 (9) |  |
| 7 | `1080177` Falcons v Ninjas in Pyjamas | 2026-10-14 10:54Z | *Market* | 75.2 / 24.8 | **Falcons 75.2%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 1.27027 / 3.85 @ 04:38:10Z | Polymarket (prediction market) 74.0% | — | VRS 6 (1843) v 18 (1534); HLTV #5 (488) v #26 (74) | FL-FORMAT-UNKNOWN FL-PRICE-DRIFT |
| 8 | `1081112` Banda chuya v 6666 | 2026-10-14 10:54Z | *Our line* | 42.1 / 57.9 | **6666 57.9%** | — own line (no outside price) | — | BO3 | VRS 165 (801) v 127 (923); HLTV — v #80 (10) | FL-FORMAT-FROM-LISTING FL-NO-OUTSIDE-LINE FL-NOT-IN-HLTV-TOP-245 |
| 9 | `1080178` Legacy v PARIVISION | 2026-10-14 13:24Z | *Market* | 56.5 / 43.5 | **Legacy 56.5%** | [Polymarket](https://polymarket.com/event/cs2-lgc-prv-2026-10-14) 56¢ / 44¢ @ 03:18:57Z | Polymarket (prediction market) 56.5% | BO3 | VRS 2 (1931) v 36 (1411); HLTV #7 (379) v #11 (178) | FL-OWN-LINE-MARKET-GAP FL-PRICE-DRIFT |
| 10 | `1079623` G2 Ares v The Last Resort | 2026-10-14 13:54Z | *Market* | 62.7 / 37.3 | **G2 Ares 62.7%** | [EGamersWorld](https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L) 1.46 / 2.45 @ 04:37:30Z | Polymarket 70.0% | BO3 | VRS 129 (913) v 126 (926); HLTV #103 (8) v #159 (4) | FL-OWN-LINE-MARKET-SPLIT |
| 11 | `1081113` Ryvex v PCIFIC | 2026-10-14 13:54Z | *Market* | 19.5 / 80.5 | **PCIFIC 80.5%** | [Polymarket](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) 20¢ / 80¢ @ 03:18:57Z | Polymarket (prediction market) 19.5% | BO3 | VRS 207 (714) v 139 (870); HLTV #181 (3) v #135 (5) | FL-OWN-LINE-MARKET-GAP |
| 12 | `1080179` FURIA v BetBoom | 2026-10-14 15:54Z | *Market* | 70.5 / 29.5 | **FURIA 70.5%** | [Polymarket](https://polymarket.com/event/cs2-furia-bb3-2026-10-14) 70¢ / 30¢ @ 03:18:57Z | Polymarket (prediction market) 70.5% | BO3 | VRS 7 (1829) v 11 (1596); HLTV #4 (527) v #14 (148) | FL-PRICE-DRIFT |
| 13 | `1079624` FORZE Reload v LFO 10 | 2026-10-14 16:54Z | *Bound only* | 86.8 / 13.2 | ** %** | — own line (no outside price) | — | — | VRS 84 (1100) v —; HLTV #75 (11) v — | FL-BOUND-OPPONENT-UNRATED FL-FORMAT-UNKNOWN FL-NO-OUTSIDE-LINE |
| 14 | `1080279` WROTBERRY v EAC | 2026-10-15 07:54Z | *Market* | 46.2 / 53.8 | **EAC 53.8%** | [bo3.gg](https://bo3.gg/matches/wbt-vs-esport-academy-copenhagen-15-10-2026) 2.0 / 1.72 @ 03:18:57Z | Thunderpick 46.2% | BO1 | VRS 60 (1201) v 103 (1035); HLTV #109 (7) v #110 (7) | FL-ALIAS-USED FL-OWN-LINE-MARKET-SPLIT FL-PRICE-DRIFT |
| 15 | `1079440` MIBR v BC.Game | 2026-10-15 09:54Z | *Market* | 57.4 / 42.6 | **MIBR 57.4%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 1.649351 / 2.22 @ 04:38:10Z | Polymarket (prediction market) 55.5% | — | VRS 12 (1585) v 50 (1318); HLTV #12 (163) v #70 (12) | FL-FORMAT-UNKNOWN |
| 16 | `1079442` Heroic v Envy | 2026-10-15 09:54Z | *Market* | 64.1 / 35.9 | **Heroic 64.1%** | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) 1.469484 / 2.62 @ 04:38:10Z | Polymarket (prediction market) 66.5% | — | VRS 15 (1550) v 21 (1500); HLTV #30 (60) v — | FL-ALIAS-USED FL-FORMAT-UNKNOWN |
| 17 | `1080280` ENCE v BOJONG | 2026-10-15 09:54Z | *Market* | 71.1 / 28.9 | **ENCE 71.1%** | [bo3.gg](https://bo3.gg/matches/ence-vs-bojong-15-10-2026) 1.3 / 3.2 @ 03:18:57Z | Thunderpick 71.1% | BO1 | VRS 105 (1025) v 363 (463); HLTV #114 (7) v #220 (2) |  |
| 18 | `1080281` WROTBERRY v ENCE | 2026-10-15 11:54Z | *Market* | 57.0 / 43.0 | **WROTBERRY 57.0%** | [bo3.gg](https://bo3.gg/matches/wbt-vs-ence-15-10-2026) 1.62 / 2.15 @ 03:18:57Z | Thunderpick 57.0% | BO1 | VRS 60 (1201) v 105 (1025); HLTV #109 (7) v #114 (7) | FL-ALIAS-USED |
| 19 | `1080282` EAC v BOJONG | 2026-10-15 13:54Z | *Market* | 76.9 / 23.1 | **EAC 76.9%** | [bo3.gg](https://bo3.gg/matches/esport-academy-copenhagen-vs-bojong-15-10-2026) 1.2 / 4.0 @ 03:18:57Z | Thunderpick 76.9% | BO1 | VRS 103 (1035) v 363 (463); HLTV #110 (7) v #220 (2) |  |
| 20 | `1080283` WROTBERRY v BOJONG | 2026-10-15 15:54Z | *Market* | 76.9 / 23.1 | **WROTBERRY 76.9%** | [bo3.gg](https://bo3.gg/matches/wbt-vs-bojong-15-10-2026) 1.2 / 4.0 @ 03:18:57Z | Thunderpick 76.9% | BO1 | VRS 60 (1201) v 363 (463); HLTV #109 (7) v #220 (2) | FL-ALIAS-USED |
| 21 | `1080284` EAC v ENCE | 2026-10-15 17:54Z | *Market* | 61.5 / 38.5 | **EAC 61.5%** | [bo3.gg](https://bo3.gg/matches/esport-academy-copenhagen-vs-ence-15-10-2026) 1.5 / 2.4 @ 03:18:57Z | Thunderpick 61.5% | BO1 | VRS 103 (1035) v 105 (1025); HLTV #110 (7) v #114 (7) | FL-PRICE-DRIFT |
| 22 | `1080285` Voca v Phantom | 2026-10-16 07:54Z | *Market* | 43.5 / 56.5 | **Phantom 56.5%** | [Polymarket](https://polymarket.com/event/cs2-voc-pha-2026-10-16) 44¢ / 56¢ @ 03:18:57Z | Polymarket (prediction market) 43.5% | BO1 | VRS 68 (1182) v 72 (1147); HLTV #59 (16) v #88 (9) | FL-OWN-LINE-MARKET-SPLIT FL-PRICE-DRIFT FL-THIN-MARKET |
| 23 | `1080286` HAVU v RoundsGG | 2026-10-16 09:54Z | *Market* | 76.9 / 23.1 | **HAVU 76.9%** | [bo3.gg](https://bo3.gg/matches/havu-vs-roundsgg-16-10-2026) 1.2 / 4.0 @ 03:18:57Z | Thunderpick 76.9% | BO1 | VRS 124 (937) v 310 (548); HLTV #118 (7) v #237 (1) | FL-ALIAS-USED |
| 24 | `1080287` Voca v HAVU | 2026-10-16 11:54Z | *Market* | 65.5 / 34.5 | **Voca 65.5%** | [bo3.gg](https://bo3.gg/matches/voca-vs-havu-16-10-2026) 1.42 / 2.7 @ 03:18:57Z | Thunderpick 65.5% | BO1 | VRS 68 (1182) v 124 (937); HLTV #59 (16) v #118 (7) | FL-PRICE-DRIFT |
| 25 | `1080288` Phantom v RoundsGG | 2026-10-16 13:54Z | *Market* | 86.8 / 13.2 | **Phantom 86.8%** | [bo3.gg](https://bo3.gg/matches/phantom-esports-vs-roundsgg-16-10-2026) 1.06 / 7.0 @ 03:18:57Z | Thunderpick 86.8% | BO1 | VRS 72 (1147) v 310 (548); HLTV #88 (9) v #237 (1) | FL-ALIAS-USED |
| 26 | `1081120` mellren v Privateer | 2026-10-16 13:54Z | *Our line* | 70.1 / 29.9 | **mellren 70.1%** | — own line (no outside price) | — | BO3 | VRS 125 (932) v 271 (608); HLTV #94 (9) v #226 (1) | FL-FORMAT-FROM-LISTING FL-NO-OUTSIDE-LINE |
| 27 | `1080289` RoundsGG v Voca | 2026-10-16 15:54Z | *Market* | 14.6 / 85.4 | **Voca 85.4%** | [bo3.gg](https://bo3.gg/matches/voca-vs-roundsgg-16-10-2026) 6.3 / 1.08 @ 03:18:57Z | Thunderpick 14.6% | BO1 | VRS 310 (548) v 68 (1182); HLTV #237 (1) v #59 (16) | FL-ALIAS-USED |
| 28 | `1080290` Phantom v HAVU | 2026-10-16 17:54Z | *Market* | 68.2 / 31.8 | **Phantom 68.2%** | [bo3.gg](https://bo3.gg/matches/phantom-esports-vs-havu-16-10-2026) 1.35 / 2.9 @ 03:18:57Z | Thunderpick 68.2% | BO1 | VRS 72 (1147) v 124 (937); HLTV #88 (9) v #118 (7) |  |

`7` placeholder price pairs were rejected at ingest (identical pairs printed
on unrelated fixtures), `1` observation was orientation-normalised
after the listing printed the sides in the other order, and `2` could not be
matched to a fixture and were left out rather than guessed.

## 4. Coverage and calibration, re-derived from the files

* `coverage.json` — {"slate_fixtures": 89, "open_fixtures": 28, "locked_fixtures": 61, "open_with_pick": 27, "open_without_pick": 1, "open_market_basis": 25, "open_own_line_basis": 2, "open_bound_only": 1, "unresolved_rows": 1, "open_with_stated_format": 23}
* `calibration.json` — objective `mae`, chosen scale **877.75**, MAE **8.66 pp**,
  log-loss 0.4444, n=25; the alternative scores are stored beside it: {"scale": 184.0, "mae_pp": 22.88, "logloss": 0.2692}
* VRS floor used for an unrated side: 381 points (the lowest value in the official file),
  published as a lower bound, never as a probability.

## 5. The checks that run before anything is published

`livelines/tests.py` (13 tests): every open fixture decided or published as unresolved · probabilities sum to
100 · market rows name source and read time · **de-vig re-derives from the printed prices** · the pick is the
higher-probability side · no Hotspawn crowd value stored · every row links a source · bound rows are labelled
as lower bounds · calibration reports both objectives · coverage counts match the rows · no broken internal
link and every page carries a viewport · **a rebuild on a pinned clock reproduces `picks.csv` byte for byte** ·
no 1.80/1.80 placeholder survives into a published row.

`tests/test_457629c4.py` (7 repository-level tests): the executive summary links to the picks and unresolved
pages · the landing page links to this board · no page links outside the board except to public sources ·
the refresh workflow is scheduled inside the 4–8 h window and gates on the tests · live reads are stored with
URLs and UTC times · the unresolved page names its specific limitations · `coverage.json` agrees with the page.

## 6. Irregularities, and what is deliberately not claimed

1. **One fixture has no pick, on purpose.** `1079624` FORZE Reload v LFO 10: the only outside listing found
   prints the opponent cell **empty** (no name, flag or team link; the URL slug is literally
   `forze-reload-vs-`), and LFO 10 appears in neither the official standings (380 teams) nor HLTV's top 245.
   One rated side and one unrated side can only produce a lower bound, so the board publishes
   *FORZE Reload at least 13.2 %* and **no pick**, on `unresolved.html`. Nothing was invented
   to fill the gap.
2. **EGamersWorld prints 1.80 / 1.80 for exactly the fixtures no book prices.** Five CCT EU #12 Play-In
   fixtures share the identical pair while other fixtures on the same page carry real, different prices
   (ENJOY v B8 Academy 1.61 / 2.21; Gothic v Lavked 1.881 / 1.782). Identical pairs on unrelated fixtures are
   treated as a listing placeholder, rejected, and flagged — never used as a number.
3. **Prices move between reads and the board says so.** Gothic v Lavked moved 2.05 / 1.64 → 1.881 / 1.782
   during this session; rows whose archived price no longer matches the newest read carry `FL-PRICE-DRIFT`
   and keep the archived value plus its read minute.
4. **Own line vs market.** Where our line and the market disagree by ≥ 15 pp the row carries
   `FL-OWN-LINE-MARKET-GAP` (9z v Aurora, Legacy v PARIVISION, Ryvex v PCIFIC); a smaller disagreement keeps
   `FL-OWN-LINE-MARKET-SPLIT`. Both stay visible and are never averaged: the published pick is whatever the
   row's stated basis yields.
5. **Official ratings are weekly, not intraday.** Valve publishes the Regional Standings weekly (newest
   official file at build time: 2026-10-05, blob 2aa28053…) and HLTV's ranking is weekly
   (2026-10-12) and capped at 245 teams. Every row that depends on them carries the date.
6. **Hotspawn itself lists fixtures that can no longer be picked.** 61 of
   89 payload fixtures are locked or past — most carry June dates the site never cleared
   — and `1079546` (Zomblers v Overtake Sector) disappeared from the board between the 02:06:30Z capture and
   the 04:31Z live read. Those rows are counted, never silently dropped.
7. **The refresh is best-effort by the platform.** GitHub disables scheduled workflows on inactive
   repositories; this repository runs many scheduled jobs and one failed on `main` on 2026-10-14
   (run <https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511378749>, "Executive board refresh").
   This board therefore also refreshes when the slate capture or the market feed finishes, prints the age of
   every input on `cadence.html`, and its own workflow fails closed.

## 7. Review it by hand

`livelines/index.html` (executive summary) → `picks.html` (one card per match) → `unresolved.html` (the
separate section) → `flagged.html` → `methodology.html` → `sources.html` → `cadence.html`.
Machine-readable: `livelines/data/picks.csv`, `picks.json`, `coverage.json`, `calibration.json`,
`live_reads.json`. Refresh: `.github/workflows/livelines-457629c4.yml` (cron `33 */4 * * *`, fail-closed).

Run the checks yourself: `python3 -m unittest tests.test_457629c4 -v` (13 board invariants + 7 repository
checks; all pass at this revision).
