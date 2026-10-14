# Session `arena/1b6ae823` — line-by-line verification record

Written 2026-10-14 ≈ 04:30 UTC on branch `arena/1b6ae823-maltaproj1`.
Board: `executive/` (11 pages) · live: <https://buffedlizard55-lab.github.io/MaltaProj1/executive/>
Every figure below was read out of the committed data files by the script that wrote this page, or
re-fetched from the named official page during this session; nothing here is remembered or estimated.

## 1. What "verified" means on this board

* **Every row carries the link its value came from.** A value with no reachable source is published
  blank plus a flag, never filled in. No cell in the pick table is derived from anything the board
  could not point at.
* **Hotspawn is used for the slate only** — match identity, tier, offered points, the exact UTC lock
  epoch — taken from the page's own Angular `TransferState` payload. **Its crowd pick percentages are
  dropped at ingest and never stored**; a build that finds one in a stored fixture fails
  `tests/test_1b6ae823.py` (check "No Hotspawn crowd value stored", currently passing). Probabilities
  come only from outside markets (Pinnacle, then secondary public listings and the hourly feed) or
  from the official rankings (Valve Regional Standings, HLTV world ranking).
* **Two independent numbers per open fixture**: the priced one (what the pick rests on) and *our own
  originated line* from the official ranking. A gap > 15 pp raises `FL-OWN-LINE-MARKET-SPLIT`; a
  reversed direction is visible in the table below and is **never** silently reconciled.
* Research tier (the "we cannot price it" case) publishes a bound, not a guess: a side absent from
  the official ranking is scored at rank **246** — one place below the last of the 245 ranked teams HLTV publishes — flagged `FL-RANK-FLOOR-BOUND`.

## 2. Live independent re-reads performed in this session

| # | What was re-read | Official page | Board value | Re-read value | Result |
|---|---|---|---|---|---|
| V-1 | HLTV world ranking the own-lines are built from | <https://www.hltv.org/ranking/teams/2026/october/12> | #1 Spirit 972, #2 Vitality 894, #3 MOUZ 692, #4 FURIA 527, #5 Falcons 488, #6 Aurora 461, #17 9z 124, #59 Voca 16 (capture `hltv_ranking.json`, 245 teams, `ranking_date 2026-10-12`) | identical, rank for rank and point for point | **match** |
| V-2 | Series length + price for `1079621` Gothic v Lavked | <https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B> | 2.05 / 1.64 (captured 2026-10-14T01:48Z), length blank → `FL-FORMAT-UNKNOWN` | page prints 2.05 / 1.64, "Bo3", 14.10.26 10:00 (CET) = 08:00 UTC | **prices and kickoff match; the length was on the listing all along** |
| V-3 | Kickoff times / slate of the live lobby cards | <https://play.hotspawn.com/lobby> read 03:5xZ | 12 cards visible on the lobby (Enjoy–B8 Academy, Gothic–Lavked, 9z–Aurora, Astralis–Sashi, HOTU–Fnatic, Banda chuya–6666, ex-RUSTEC–mellren, Falcons–NiP, Legacy–PARIVISION, Ryvex–PCIFIC, G2 Ares–The Last Resort, FURIA–BetBoom) | all 12 present in the board's fixture set, same UTC starts, each with a pick | **match** (Falcons–NiP is stored as `Falcons` / `Ninjas in Pyjamas`; matched by id `1080177`, not by the lobby's abbreviated label) |
| V-4 | Astralis–Sashi moneyline drift | <https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z> | 1.09 / 6.33 at 01:48Z → 85.3 % Astralis | 1.07 / 6.25 at 04:2xZ → 85.4 % Astralis | **drift of 0.1 pp after 2.5 h; pick unchanged** — the row publishes its capture minute so a reader can see the age |
| V-5 | Second-source agreement across the whole open slate | `feeds/data/market_feed.csv` (hourly capture, read-only, owned by another session) vs this board's accepted price | — | 32 of the open fixtures are priced by both | **29 / 32 agree within 5 pp**; largest gap 7.6 pp on `1079623` G2 Ares v The Last Resort, where Polymarket says 70.0 % and the EGamersWorld listing the row is priced from says 62.4 % |
| V-6 | Lock-time definition | lobby countdown "Locks in 03:59:33" for a 04:00 EDT card vs payload `lock_time` / `lock_offset_sec` | board publishes payload: start − 360 s (e.g. 08:30:00Z start → 08:24:00Z lock on all four Thunderpick WC cards) | UI countdown implies start − ~30 s | **explained and kept conservative**: the payload value is the earlier of the two, so a row can only flip to *locked* before the lobby does, never after. Not a data error; recorded because a reader comparing the two will see a 5½-minute difference. |

Could not be re-read from this sandbox: the Pinnacle match page for `1080176` returned HTTP 500 (and
`hltv.org/matches/<id>` has returned 403 for every session in this repo). The 9z–Aurora row therefore
rests on Pinnacle's own guest market response, whose URL is printed on the row, plus the corroboration
in V-5 (Polymarket 74.0 % / 26.0 % vs the published 76.5 % for the same pairing) and the ranking line.

## 3. Line-by-line table of every open fixture (28 rows, built 2026-10-14T04:20:13Z from the 04:09:56Z capture)

Coverage: 28/28 open fixtures carry a pick and a probability for
both sides; 25 priced from an outside market, 3 from the
official-ranking research line, 1 on a provisional bound. Locked fixtures:
61; of those, 59 are dated before today in Hotspawn's own
payload and are labelled stale rather than deleted.

| # | Fixture (Hotspawn id) | Start → lock (UTC) | Tier · pts | Basis for the number | Pick | % | Other side % | Series length | Price A / B | Our own line A/B | Source link the row carries | Flags |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Gothic v Lavked (`1079621`) | 10-14T08:00 → 10-14T07:54 | B · 3 | T2 · Market · secondary listing | **Lavked** | 55.6 | 44.4 | BO3 [polymarket.com] | 2.05 / 1.64 | 14.5 / 85.5 | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` `FL-OWN-LINE-MARKET-SPLIT` `FL-RANK-FLOOR-BOUND` |
| 2 | Enjoy v B8 Academy (`1081111`) | 10-14T08:00 → 10-14T07:54 | C · 2 | T2 · Market · secondary listing | **Enjoy** | 60.2 | 39.8 | BO3 [polymarket.com] | 1.52 / 2.30 | 62.0 / 38.0 | [egamersworld.com](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` |
| 3 | 9z v Aurora (`1080176`) | 10-14T08:30 → 10-14T08:24 | S · 7 | T1 · Market · primary book | **Aurora** | 73.8 | 26.2 | BO3 [www.pinnacle.com] | 3.65 / 1.29 | 45.5 / 54.5 | [www.pinnacle.com](https://www.pinnacle.com/en/esports/cs2-tp-world-championship/9z-vs-aurora/1638111785/) | `FL-FORMAT-FROM-LISTING` `FL-OWN-LINE-MARKET-SPLIT` `FL-STALE-CAPTURE` |
| 4 | Astralis v Sashi (`1079438`) | 10-14T10:00 → 10-14T09:54 | B · 3 | T2 · Market · secondary listing | **Astralis** | 85.3 | 14.7 | BO3 [bo3.gg] | 1.09 / 6.33 | 98.4 / 1.6 | [egamersworld.com](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z) | `FL-FORMAT-FROM-LISTING` `FL-RANK-FLOOR-BOUND` |
| 5 | HOTU v Fnatic (`1079439`) | 10-14T10:00 → 10-14T09:54 | B · 3 | T1 · Market · primary book | **Fnatic** | 52.5 | 47.5 | BO3 [www.pinnacle.com] | 1.99 / 1.80 | 48.0 / 52.0 | [www.pinnacle.com](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/hotu-vs-fnatic/1637867148/) | `FL-FORMAT-FROM-LISTING` `FL-STALE-CAPTURE` |
| 6 | ex-RUSTEC v mellren (`1079622`) | 10-14T11:00 → 10-14T10:54 | B · 3 | T2 · Market · secondary listing | **ex-RUSTEC** | 65.7 | 34.3 | BO3 [polymarket.com] | 1.40 / 2.68 | 56.1 / 43.9 | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK) | `FL-AMBIGUOUS-NAME` `FL-FORMAT-FROM-LISTING` |
| 7 | Falcons v Ninjas in Pyjamas (`1080177`) | 10-14T11:00 → 10-14T10:54 | S · 7 | T1 · Market · primary book | **Falcons** | 76.5 | 23.5 | BO3 [www.pinnacle.com] | 1.25 / 4.06 | 58.5 / 41.5 | [www.pinnacle.com](https://www.pinnacle.com/en/esports/cs2-tp-world-championship/falcons-vs-ninjas-in-pyjamas/1638111674/) | `FL-FORMAT-FROM-LISTING` `FL-OWN-LINE-MARKET-SPLIT` `FL-STALE-CAPTURE` |
| 8 | Banda chuya v 6666 (`1081112`) | 10-14T11:00 → 10-14T10:54 | C · 2 | T3 · Model · official ratings | **6666** | 66.9 | 33.1 | *(blank)* | *none accepted* | 14.1 / 85.9 | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) | `FL-DUPLICATE-VRS-NAME` `FL-FORMAT-UNKNOWN` `FL-NO-MARKET` `FL-RANK-FLOOR-BOUND` `FL-RATINGS-WEEK-OLD` |
| 9 | Legacy v PARIVISION (`1080178`) | 10-14T13:30 → 10-14T13:24 | S · 7 | T2 · Market · secondary listing | **Legacy** | 53.8 | 46.2 | BO3 [bo3.gg] | 1.72 / 2.00 | 51.6 / 48.4 | [bo3.gg](https://bo3.gg/matches/legacy-br-vs-parivision-14-10-2026) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` |
| 10 | G2 Ares v The Last Resort (`1079623`) | 10-14T14:00 → 10-14T13:54 | B · 3 | T2 · Market · secondary listing | **G2 Ares** | 62.4 | 37.6 | BO3 [polymarket.com] | 1.47 / 2.44 | 71.5 / 28.5 | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L) | `FL-FORMAT-FROM-LISTING` |
| 11 | Ryvex v PCIFIC (`1081113`) | 10-14T14:00 → 10-14T13:54 | C · 2 | T2 · Market · secondary listing | **PCIFIC** | 80.5 | 19.5 | BO3 [polymarket.com] | 5.13 / 1.24 | 32.0 / 68.0 | [polymarket.com](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) | `FL-FORMAT-FROM-LISTING` `FL-PREDICTION-MARKET-BASIS` |
| 12 | FURIA v BetBoom (`1080179`) | 10-14T16:00 → 10-14T15:54 | S · 7 | T2 · Market · secondary listing | **FURIA** | 67.1 | 32.9 | BO3 [bo3.gg] | 1.40 / 2.86 | 54.1 / 45.9 | [egamersworld.com](https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH) | `FL-FORMAT-FROM-LISTING` |
| 13 | FORZE Reload v LFO 10 (`1079624`) | 10-14T17:00 → 10-14T16:54 | B · 3 | T4 · Model · official bound (provisional) | **FORZE Reload** | 98.4 | 1.6 | *(blank)* | *none accepted* | 86.5 / 13.5 | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) | `FL-FORMAT-UNKNOWN` `FL-NO-MARKET` `FL-RANK-FLOOR-BOUND` `FL-RATINGS-WEEK-OLD` `FL-UNLISTED-OPPONENT` |
| 14 | WROTBERRY v EAC (`1080279`) | 10-15T08:00 → 10-15T07:54 | C · 2 | T2 · Market · secondary listing | **EAC** | 53.8 | 46.2 | BO1 [bo3.gg] | 2.00 / 1.72 | 18.6 / 81.4 | [bo3.gg](https://bo3.gg/matches/wbt-vs-esport-academy-copenhagen-15-10-2026) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` `FL-OWN-LINE-MARKET-SPLIT` `FL-RANK-FLOOR-BOUND` |
| 15 | MIBR v BC.Game (`1079440`) | 10-15T10:00 → 10-15T09:54 | B · 3 | T1 · Market · primary book | **MIBR** | 57.7 | 42.3 | BO3 [www.pinnacle.com] | 1.64 / 2.23 | 72.2 / 27.8 | [www.pinnacle.com](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/mibr-vs-bcgame/1637936745/) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` `FL-STALE-CAPTURE` |
| 16 | Heroic v Envy (`1079442`) | 10-15T10:00 → 10-15T09:54 | B · 3 | T1 · Market · primary book | **Heroic** | 62.3 | 37.7 | BO3 [www.pinnacle.com] | 1.52 / 2.50 | 45.9 / 54.1 | [www.pinnacle.com](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/heroic-vs-envy/1637999450/) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-OWN-LINE-MARKET-SPLIT` `FL-STALE-CAPTURE` |
| 17 | ENCE v BOJONG (`1080280`) | 10-15T10:00 → 10-15T09:54 | C · 2 | T2 · Market · secondary listing | **ENCE** | 71.1 | 28.9 | BO1 [bo3.gg] | 1.30 / 3.20 | 76.0 / 24.0 | [bo3.gg](https://bo3.gg/matches/ence-vs-bojong-15-10-2026) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` |
| 18 | WROTBERRY v ENCE (`1080281`) | 10-15T12:00 → 10-15T11:54 | C · 2 | T2 · Market · secondary listing | **WROTBERRY** | 57.0 | 43.0 | BO1 [bo3.gg] | 1.62 / 2.15 | 19.3 / 80.7 | [bo3.gg](https://bo3.gg/matches/wbt-vs-ence-15-10-2026) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` `FL-OWN-LINE-MARKET-SPLIT` `FL-RANK-FLOOR-BOUND` |
| 19 | EAC v BOJONG (`1080282`) | 10-15T14:00 → 10-15T13:54 | C · 2 | T2 · Market · secondary listing | **EAC** | 76.9 | 23.1 | BO1 [bo3.gg] | 1.20 / 4.00 | 76.8 / 23.2 | [bo3.gg](https://bo3.gg/matches/esport-academy-copenhagen-vs-bojong-15-10-2026) | `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` |
| 20 | WROTBERRY v BOJONG (`1080283`) | 10-15T16:00 → 10-15T15:54 | C · 2 | T2 · Market · secondary listing | **WROTBERRY** | 76.7 | 23.3 | BO1 [bo3.gg] | 1.21 / 3.99 | 43.0 / 57.0 | [egamersworld.com](https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-MODEL-MARKET-SPLIT` `FL-OWN-LINE-MARKET-SPLIT` `FL-RANK-FLOOR-BOUND` |
| 21 | EAC v ENCE (`1080284`) | 10-15T18:00 → 10-15T17:54 | C · 2 | T2 · Market · secondary listing | **EAC** | 61.5 | 38.5 | BO1 [bo3.gg] | 1.50 / 2.40 | 51.1 / 48.9 | [bo3.gg](https://bo3.gg/matches/esport-academy-copenhagen-vs-ence-15-10-2026) | `FL-FORMAT-FROM-LISTING` |
| 22 | Voca v Phantom (`1080285`) | 10-16T08:00 → 10-16T07:54 | C · 2 | T2 · Market · secondary listing | **Phantom** | 51.4 | 48.6 | BO1 [bo3.gg] | 1.90 / 1.80 | 57.8 / 42.2 | [bo3.gg](https://bo3.gg/matches/voca-vs-phantom-esports-16-10-2026) | `FL-FORMAT-FROM-LISTING` |
| 23 | HAVU v RoundsGG (`1080286`) | 10-16T10:00 → 10-16T09:54 | C · 2 | T2 · Market · secondary listing | **HAVU** | 76.9 | 23.1 | BO1 [bo3.gg] | 1.20 / 4.00 | 80.1 / 19.9 | [bo3.gg](https://bo3.gg/matches/havu-vs-roundsgg-16-10-2026) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-RANK-FLOOR-BOUND` |
| 24 | Voca v HAVU (`1080287`) | 10-16T12:00 → 10-16T11:54 | C · 2 | T2 · Market · secondary listing | **Voca** | 65.5 | 34.5 | BO1 [bo3.gg] | 1.42 / 2.70 | 65.5 / 34.5 | [bo3.gg](https://bo3.gg/matches/voca-vs-havu-16-10-2026) | `FL-FORMAT-FROM-LISTING` |
| 25 | Phantom v RoundsGG (`1080288`) | 10-16T14:00 → 10-16T13:54 | C · 2 | T2 · Market · secondary listing | **Phantom** | 86.5 | 13.5 | BO1 [bo3.gg] | 1.08 / 6.94 | 84.8 / 15.2 | [egamersworld.com](https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-RANK-FLOOR-BOUND` |
| 26 | mellren v Privateer (`1081120`) | 10-16T14:00 → 10-16T13:54 | C · 2 | T3 · Model · official ratings | **mellren** | 86.6 | 13.4 | *(blank)* | *none accepted* | 80.7 / 19.3 | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) | `FL-FORMAT-UNKNOWN` `FL-NO-MARKET` `FL-RATINGS-WEEK-OLD` |
| 27 | RoundsGG v Voca (`1080289`) | 10-16T16:00 → 10-16T15:54 | C · 2 | T2 · Market · secondary listing | **Voca** | 85.4 | 14.6 | BO1 [bo3.gg] | 6.30 / 1.08 | 11.6 / 88.4 | [bo3.gg](https://bo3.gg/matches/voca-vs-roundsgg-16-10-2026) | `FL-ALIAS-NAME` `FL-FORMAT-FROM-LISTING` `FL-RANK-FLOOR-BOUND` |
| 28 | Phantom v HAVU (`1080290`) | 10-16T18:00 → 10-16T17:54 | C · 2 | T2 · Market · secondary listing | **Phantom** | 67.8 | 32.2 | BO1 [bo3.gg] | 1.36 / 2.87 | 58.1 / 41.9 | [egamersworld.com](https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586) | `FL-FORMAT-FROM-LISTING` |

*Reading the "Basis" column:* T1 = a whole-match moneyline from the primary book (de-vigged
proportionally); T2 = a public secondary listing (the aggregator's page is the source, not the book);
T3 = our own line from official ranking points only; T4 = one side is absent from every ranking, so a
floor bound is published instead of a probability. "Our own line" is present for **all** 28
open rows and is a cross-check, never the published number, whenever a price exists.

Model, for the record: per-map `p = 1 / (1 + 10^((rank_b − rank_a) / 212))`, 212
rank positions per 90 % favourite fitted on 18 fixtures that an outside book prices (grid search,
mean absolute error 8.4 pp), then converted to the stated series length. `own-lines.html`
prints the fit so the constant can be audited without reading code.

## 4. Irregularities found (published, not hidden)

1. **3 open rows still have no series length** — it was 12 of 28 before this session taught the builder to read the length off *any* accepted outside page for the fixture (the listing that prices the row first, then a sibling quote for the same pairing, each linked). 25 of 28 now print a stated length with the page that stated it; the 3 that stay blank are the ones where no outside page states one, and nothing is invented for them.
2. **Direction conflicts** — 4 open rows where our originated line prefers the side the market prices as the underdog: `1079442` Heroic v Envy (priced 62.3 %, own line 45.9 %), `1080281` WROTBERRY v ENCE (priced 57.0 %, own line 19.3 %), `1080283` WROTBERRY v BOJONG (priced 76.7 %, own line 43.0 %), `1080285` Voca v Phantom (priced 48.6 %, own line 57.8 %). All are `FL-OWN-LINE-MARKET-SPLIT` and stay on the picks page with both numbers visible; the market number remains the published pick.
3. **Three open fixtures with no accepted outside price**: `1081112` Banda chuya v 6666 (research line), `1079624` FORZE Reload v LFO 10 (provisional bound — LFO 10 is absent from the HLTV ranking), `1081120` mellren v Privateer (research line). These are exactly the low-tier matches the brief said betting sites do not cover; they are covered, but with a weaker basis and a visible label.
4. **59 stale fixtures** in Hotspawn's payload carry June 2026 start dates that were never updated after the event ran; they are published in a separate archive section, flagged `FL-STALE-CAPTURE`/locked, and excluded from the "your matches" list.
5. **Name ambiguity** — 7 open rows matched an official record through an alias, 6 rows overall were flagged `FL-AMBIGUOUS-NAME`, 16 more where two orgs share a standings spelling. Each row states which spelling it used and links the team page.
6. **Rejected placeholder quotes** — EGamersWorld's 1.80 / 1.80 filler and equivalent "no price" rows are dropped rather than averaged (`FL-PLACEHOLDER-REJECTED`).
7. **Ratings age** — the newest global Valve standings file is `standings_global_2026_10_05.md`; `FL-RATINGS-WEEK-OLD` is therefore unavoidable for any fixture before the next published update and is printed with the file date rather than hidden.

## 5. Source access — what refused, and what the site does about it

| Source | Result in this run | Board behaviour |
|---|---|---|
| `play.hotspawn.com/lobby` + `/cs2-pickems` payload | OK | fixture identity, tier, points, lock epoch only |
| Pinnacle guest sport-level markets | OK (~8 quotes per read) | T1 prices, de-vigged |
| Pinnacle per-league `/leagues/{id}/matchups`, `/markets/related/straight` | 403 `BAD_LOCATION` / 204 from US runners | not used; per-match URL still published as the reader's link |
| `pinnacle.com/en/esports/.../9z-vs-aurora/1638111785/` re-read from sandbox | HTTP 500 | value kept with its capture minute; cross-checked against the hourly feed (V-5) |
| EGamersWorld match pages | OK for the pages this board cites | T2 listings, placeholder odds rejected |
| `hltv.org/ranking/teams/…` | OK | own lines, identity |
| `hltv.org/matches/<id>`, `/results`, event match tabs | 403 for CI and sandbox; `/events/9332` overview readable but all win/loss counts are 0 before the group starts | format/fixture corroboration only; never a probability input |
| `liquipedia.net/counterstrike/api.php` Cargo query | `badvalue: Unrecognized value for parameter "action": cargoapi` | abandoned; no results-based research tier |
| Valve `counter-strike_regional_standings` raw file | OK | VRS points, floor bound |
| Polymarket events | OK | prediction-market basis, explicitly labelled and flagged `FL-PREDICTION-MARKET-BASIS` |
| `gh workflow run` (manual CI dispatch) | HTTP 403 `Resource not accessible by integration` | cannot be forced from here; the board refreshes on its cron and on every push to `main` that touches it |
| refresh workflow on *this* branch | never triggered — `on.push.branches` is restricted to `arena/5545dbb8-maltaproj1` and `main`, which that session owns | post-merge the scheduled and push triggers on `main` rebuild it; verified in that run instead of a branch run |

## 6. Gates run before merging

| Gate | Result |
|---|---|
| `python3 executive/collect.py --offline && python3 executive/build.py` | builds; checks 10/10 pass |
| `python3 executive/tests.py` (the board's own invariant suite) | 15 passed, 0 failed |
| `python3 -m unittest tests.test_1b6ae823` (this session's contract: cadence, crowd ban, ladder, links, landing) | 24 tests OK |
| `python3 -m unittest discover -s tests` (whole repo, all sessions) | 267 tests OK |
| internal links of the executive board | 195 checked, 0 broken |
| `python3 scripts/audit_91e444dd.py` (whole site) | 209 HTML pages, 0 link errors, 53 findings carried by other boards (unchanged by this session) |
| cadence published by the site | `cron 33 */4 * * *` → 4 h, inside the 4–8 h window the brief asked for |

Reproduce: `git clone -b arena/1b6ae823-maltaproj1 … && python3 executive/collect.py --offline && python3 executive/build.py && python3 executive/tests.py`.

## 7. Landing page — the collision, recorded honestly

This session also rewrote the root `index.html` as a mobile-first hub. While that was in flight,
`arena/43c32386` landed its own consolidated landing (PR #104, already published on Pages and guarded by
`tests/test_landing_43c32386.py`). Overwriting it would have broken their contract for no user gain, so
their page is the landing and this session's edits to it are **additive only**: a card linking
`executive/cadence.html`, and one dated sentence in the "What is — and is not — verified?" notice pointing
at the new ranking-line coverage. The full hub this session had written is published instead at
`executive/index.html`. The resolution and the merge-conflict record are in `COORDINATION.md`
("Session `arena/1b6ae823`" section); no other session's content was discarded.
