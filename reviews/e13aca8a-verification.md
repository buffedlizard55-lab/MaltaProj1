# Line-by-line verification — session `arena/e13aca8a`, 2026-10-14

Scope of this record: the refreshed executive board after the research-ladder pass (E-01…E-05).
Snapshot rebuilt **2026-10-14T05:2x UTC** from `executive/data/` by `python3 executive/build.py`
(deterministic; `python3 executive/tests.py` = 15/15, whole-repo `python3 -m unittest discover -s tests` = **267 OK**).

Verification method, in the order the brief requires:

1. **Live re-read of the Hotspawn slate** (the fixture source) at 04:34–04:52Z — 28/28 open fixtures
   confirmed present with identical pairings; pool count 88 vs inventory 89 reconciled
   (one retired fixture, `1079546`, already locked). Evidence: `data/e13aca8a/live_research_2026-10-14.md` §1.
2. **Live re-read of the outside price pages this research pass adds** (Polymarket CCT Europe board,
   EGW match pages, HLTV event/team pages, Valve standings repo via GitHub API) — every price,
   format, rank and roster fact used by the research ladder was transcribed from the page named in
   the table below or in the research log. Read window 04:34–05:20Z.
3. **Re-derivation from stored inputs** — every published probability re-derives from the stored
   quote (proportional de-vig) or the stored official points (the stated logistic). The executive
   test suite asserts this (`executive/tests.py` — maths re-derived, sources present, no crowd data).
4. **Rows that could not be confirmed** stay blank/flagged. No row in the table below contains a
   number without a source link; the flags column names every caveat.

What this session did **not** re-read live (honest limits): the 2026-10-13T19:42Z Pinnacle capture
and the 2026-10-14T01:48Z EGW capture behind the older rows (CI-side re-read evidence in
`reviews/228bb5bc-verification.md` §5 and `reviews/bdc98a9a-verification.md` covers those; this
sandbox's platform fetch cannot authenticate to Pinnacle's guest endpoint deterministically).
Those rows keep their capture minutes and `FL-STALE-CAPTURE` where older than the staleness gate.

## 1. All 28 open fixtures — pick, probabilities, basis, source

Probabilities are `% (team A) / % (team B)` and always sum to 100 (proportional de-vig or the
stated model transform). "T2" rows priced by a **prediction market** carry
`FL-PREDICTION-MARKET-BASIS` in the flags column.

| id | Fixture | Lock (UTC) | Pick | pA/pB | Basis | Format | Source on the row | Flags |
|----|---------|-----------|------|-------|-------|--------|-------------------|-------|
| `1079621` | Gothic vs Lavked | 2026-10-14T07:54:00Z | **Lavked** | 44.4/55.6 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT;FL-OWN-LINE-MARKET-SPLIT;FL-RANK-FLOOR-BOUND |
| `1081111` | Enjoy vs B8 Academy | 2026-10-14T07:54:00Z | **Enjoy** | 60.2/39.8 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT |
| `1080176` | 9z vs Aurora | 2026-10-14T08:24:00Z | **Aurora** | 26.2/73.8 | T1 primary book | BO3 | [src](https://www.pinnacle.com/en/esports/cs2-tp-world-championship/9z-vs-aurora/1638111785/) | FL-FORMAT-FROM-LISTING;FL-OWN-LINE-MARKET-SPLIT;FL-STALE-CAPTURE |
| `1079438` | Astralis vs Sashi | 2026-10-14T09:54:00Z | **Astralis** | 85.3/14.7 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z) | FL-FORMAT-FROM-LISTING;FL-RANK-FLOOR-BOUND |
| `1079439` | HOTU vs Fnatic | 2026-10-14T09:54:00Z | **Fnatic** | 47.5/52.5 | T1 primary book | BO3 | [src](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/hotu-vs-fnatic/1637867148/) | FL-FORMAT-FROM-LISTING;FL-STALE-CAPTURE |
| `1079622` | ex-RUSTEC vs mellren | 2026-10-14T10:54:00Z | **ex-RUSTEC** | 65.7/34.3 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK) | FL-AMBIGUOUS-NAME;FL-FORMAT-FROM-LISTING |
| `1080177` | Falcons vs Ninjas in Pyjamas | 2026-10-14T10:54:00Z | **Falcons** | 76.5/23.5 | T1 primary book | BO3 | [src](https://www.pinnacle.com/en/esports/cs2-tp-world-championship/falcons-vs-ninjas-in-pyjamas/1638111674/) | FL-FORMAT-FROM-LISTING;FL-OWN-LINE-MARKET-SPLIT;FL-STALE-CAPTURE |
| `1081112` | Banda chuya vs 6666 | 2026-10-14T10:54:00Z | **6666** | 33.1/66.9 | T3 own line | BO3 | [src](https://egamersworld.com/counterstrike/match/4kY9VAmiEg/banda-chuya-vs-6666-JdPgKgp5y) | FL-DUPLICATE-VRS-NAME;FL-FORMAT-FROM-RESEARCH;FL-NO-MARKET;FL-RANK-FLOOR-BOUND;FL-RATINGS-WEEK-OLD;FL-RESEARCH-CROSSCHECK-CONFLICT |
| `1080178` | Legacy vs PARIVISION | 2026-10-14T13:24:00Z | **Legacy** | 53.8/46.2 | T2 secondary market | BO3 | [src](https://bo3.gg/matches/legacy-br-vs-parivision-14-10-2026) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT |
| `1079623` | G2 Ares vs The Last Resort | 2026-10-14T13:54:00Z | **G2 Ares** | 62.4/37.6 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L) | FL-FORMAT-FROM-LISTING |
| `1081113` | Ryvex vs PCIFIC | 2026-10-14T13:54:00Z | **PCIFIC** | 19.5/80.5 | T2 secondary market | BO3 | [src](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) | FL-FORMAT-FROM-LISTING;FL-PREDICTION-MARKET-BASIS |
| `1080179` | FURIA vs BetBoom | 2026-10-14T15:54:00Z | **FURIA** | 67.1/32.9 | T2 secondary market | BO3 | [src](https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH) | FL-FORMAT-FROM-LISTING |
| `1079624` | FORZE Reload vs LFO 10 | 2026-10-14T16:54:00Z | **FORZE Reload** | 84.6/15.4 | T2 secondary market | BO3 | [src](https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14) | FL-FORMAT-FROM-LISTING;FL-LISTING-ALIAS;FL-PREDICTION-MARKET-BASIS;FL-RANK-FLOOR-BOUND;FL-UNLISTED-OPPONENT |
| `1080279` | WROTBERRY vs EAC | 2026-10-15T07:54:00Z | **EAC** | 46.2/53.8 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/wbt-vs-esport-academy-copenhagen-15-10-2026) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT;FL-OWN-LINE-MARKET-SPLIT;FL-RANK-FLOOR-BOUND |
| `1079440` | MIBR vs BC.Game | 2026-10-15T09:54:00Z | **MIBR** | 57.7/42.3 | T1 primary book | BO3 | [src](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/mibr-vs-bcgame/1637936745/) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT;FL-STALE-CAPTURE |
| `1079442` | Heroic vs Envy | 2026-10-15T09:54:00Z | **Heroic** | 62.3/37.7 | T1 primary book | BO3 | [src](https://www.pinnacle.com/en/esports/cs2-stk-pulse-beat/heroic-vs-envy/1637999450/) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-OWN-LINE-MARKET-SPLIT;FL-STALE-CAPTURE |
| `1080280` | ENCE vs BOJONG | 2026-10-15T09:54:00Z | **ENCE** | 71.1/28.9 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/ence-vs-bojong-15-10-2026) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT |
| `1080281` | WROTBERRY vs ENCE | 2026-10-15T11:54:00Z | **WROTBERRY** | 57.0/43.0 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/wbt-vs-ence-15-10-2026) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT;FL-OWN-LINE-MARKET-SPLIT;FL-RANK-FLOOR-BOUND |
| `1080282` | EAC vs BOJONG | 2026-10-15T13:54:00Z | **EAC** | 76.9/23.1 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/esport-academy-copenhagen-vs-bojong-15-10-2026) | FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT |
| `1080283` | WROTBERRY vs BOJONG | 2026-10-15T15:54:00Z | **WROTBERRY** | 76.7/23.3 | T2 secondary market | BO1 | [src](https://egamersworld.com/counterstrike/match/4yn491uUVl/wbt-vs-bojong-r7kNL0-LX6) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-MODEL-MARKET-SPLIT;FL-OWN-LINE-MARKET-SPLIT;FL-RANK-FLOOR-BOUND |
| `1080284` | EAC vs ENCE | 2026-10-15T17:54:00Z | **EAC** | 61.5/38.5 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/esport-academy-copenhagen-vs-ence-15-10-2026) | FL-FORMAT-FROM-LISTING |
| `1080285` | Voca vs Phantom | 2026-10-16T07:54:00Z | **Phantom** | 48.6/51.4 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/voca-vs-phantom-esports-16-10-2026) | FL-FORMAT-FROM-LISTING |
| `1080286` | HAVU vs RoundsGG | 2026-10-16T09:54:00Z | **HAVU** | 76.9/23.1 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/havu-vs-roundsgg-16-10-2026) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-RANK-FLOOR-BOUND |
| `1080287` | Voca vs HAVU | 2026-10-16T11:54:00Z | **Voca** | 65.5/34.5 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/voca-vs-havu-16-10-2026) | FL-FORMAT-FROM-LISTING |
| `1080288` | Phantom vs RoundsGG | 2026-10-16T13:54:00Z | **Phantom** | 86.5/13.5 | T2 secondary market | BO1 | [src](https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-rounds-m6Cnk4tOxU) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-RANK-FLOOR-BOUND |
| `1081120` | mellren vs Privateer | 2026-10-16T13:54:00Z | **mellren** | 86.6/13.4 | T3 own line | BO3 | [src](https://polymarket.com/esports/cs2/cct-europe/cs2-mellre-pg5-2026-10-16) | FL-FORMAT-FROM-RESEARCH;FL-MARKET-NO-LIQUIDITY;FL-NO-MARKET;FL-RATINGS-WEEK-OLD |
| `1080289` | RoundsGG vs Voca | 2026-10-16T15:54:00Z | **Voca** | 14.6/85.4 | T2 secondary market | BO1 | [src](https://bo3.gg/matches/voca-vs-roundsgg-16-10-2026) | FL-ALIAS-NAME;FL-FORMAT-FROM-LISTING;FL-RANK-FLOOR-BOUND |
| `1080290` | Phantom vs HAVU | 2026-10-16T17:54:00Z | **Phantom** | 67.8/32.2 | T2 secondary market | BO1 | [src](https://egamersworld.com/counterstrike/match/4yn491uUVl/phantom-esports-vs-havu-H8whr4r586) | FL-FORMAT-FROM-LISTING |

## 2. Research-ladder rows — what was verified live this session

| Fixture | Claim being verified | Source read live (2026-10-14) | Result |
|---------|---------------------|-------------------------------|--------|
| `1079624` FORZE Reload vs LFO 10 | Polymarket's "Sökerorg" market prices THIS fixture | [cs2-forzer-skr2-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14) + [bo3.gg/teams/sokerorg](https://bo3.gg/teams/sokerorg) + [HLTV 14084](https://www.hltv.org/team/14084/lfo-10) | **Confirmed by roster, not inference**: Sökerorg roster Jackinho/Sapec/tvs/flaw/dottie = LFO 10's roster on HLTV and the EGW match page lineup; same event/slot/date/BO3. Prices 88¢/16¢ ($373.86 vol) → de-vig 84.6/15.4. |
| `1079624` | series length BO3 | [HLTV event 9442](https://www.hltv.org/events/9442/cct-2026-europe-series-11) (match [2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11)) + EGW page "Bo3" | Confirmed on two sources. |
| `1079624` | LFO 10's official standing | [Valve repo `live/2026/`](https://github.com/ValveSoftware/counter-strike_regional_standings) (GitHub API) + [HLTV valve-ranking beta 2026-10-12](https://www.hltv.org/valve-ranking/teams/2026/october/12) | **Official file: absent** (newest is `standings_global_2026_10_05.md`). HLTV beta page: #170 / 765 pts — labelled evidence, never an official-file entry. Published as `FL-RANK-FLOOR-BOUND`/`FL-UNLISTED-OPPONENT` on the own line. |
| `1081112` Banda chuya vs 6666 | a price exists somewhere | Polymarket CCT Europe board (10 markets, listed in the research log §4) + EGW match page | **No price anywhere** (EGW prints a single 1.8 placeholder). Row keeps the originated VRS line 33.1/66.9, pick 6666. |
| `1081112` | research cross-checks | [HLTV 13900](https://www.hltv.org/team/13900/banda-chuya), [HLTV 13882](https://www.hltv.org/team/13882/6666), [EGW page](https://egamersworld.com/counterstrike/match/4kY9VAmiEg/banda-chuya-vs-6666-JdPgKgp5y) | HLTV: Banda unranked (peak #162) vs 6666 ranked; form 26.7% 3-mo win rate vs 5-win streak — agrees with the line. **Counter-signal published**: EGW rating 902 vs 515 favours Banda → `FL-RESEARCH-CROSSCHECK-CONFLICT`, not reconciled. |
| `1081112` | series length BO3 | EGW page "14.10.26 07:00 Bo3" + HLTV match 2399462 (event 9456) | Confirmed on two sources. |
| `1081120` mellren vs Privateer | Polymarket prices for this card | [cs2-mellre-pg5-2026-10-16](https://polymarket.com/esports/cs2/cct-europe/cs2-mellre-pg5-2026-10-16) | **Refused**: uninitialised book (94¢/93¢, $0 vol). Reason recorded on `executive/unresolved.html` and in `research_lines.json` → `refusals`. Row keeps the VRS line 86.6/13.4, pick mellren. |
| `1081120` | series length BO3 | market title "(BO3)" + EGW tournament sidebar ("mellren - Privateer Gaming 16.10") | Confirmed (title + listing). |
| `1081111` / `1081113` | headline price source | feed rows (03:18:57Z) vs research read (04:50Z) | Feed rows are tighter and stay headline; research reads recorded as drift evidence (62/39 vs 63.5/36.5; 82/21 vs 79.5/20.5). Picks unchanged. |

## 3. Slate delta (E-01)

| Check | Source | Result |
|-------|--------|--------|
| Open fixtures present on live board | [lobby](https://play.hotspawn.com/lobby) + [cs2-pickems](https://play.hotspawn.com/cs2-pickems) 04:34–04:52Z | 28/28 confirmed, pairings identical |
| Pool size | tier filters (All 88 · B 24 · C 60 · S 4) | inventory 89 → live 88; delta = `1079546` (ESL Challenger League S52 NA Cup #3) retired after its 01:00Z start; kept in inventory for the record |
| Lock convention | live countdowns vs payload `lock_utc` | consistent with `lock = start − 360 s` (e.g. Gothic–Lavked 07:54Z) |

## 4. Irregularities flagged (non-blocking, published on the site)

| Code | Row(s) | What | Where published |
|------|--------|------|-----------------|
| FL-LISTING-ALIAS | `1079624` | Polymarket lists the opponent as "Sökerorg" | `executive/unresolved.html`, `executive/flagged.html`, research log §5 |
| FL-RESEARCH-CROSSCHECK-CONFLICT | `1081112` | EGW's proprietary rating favours the opposite side to the official-points line | same |
| FL-MARKET-NO-LIQUIDITY | `1081120` | Polymarket book uninitialised (94¢/93¢, $0 vol) — prices refused | same (refusals table) |
| FL-RANK-FLOOR-BOUND / FL-UNLISTED-OPPONENT | `1079624`, `1081112`, others | teams absent from the official standings file / HLTV ranking — bound used on the own line only | `executive/flagged.html` |
| FL-RATINGS-WEEK-OLD | T3 rows | newest official Valve file is still 2026-10-05 (weekly cadence confirmed via GitHub API) | `executive/flagged.html` |
| FL-STALE-CAPTURE | `1080176`, `1079439`, `1080177`, `1079440` | primary-book capture 2026-10-13T19:42Z is older than the 6 h gate — price shown with its minute, not presented as live | `executive/flagged.html` |
| FL-MODEL-MARKET-SPLIT / FL-OWN-LINE-MARKET-SPLIT | 8 rows | market vs our own line disagree >15 pp; both printed | `executive/flagged.html` |
| identity aliases | WROTBERRY=WBT, PCIFIC=WRAITH PCIFIC, Envy=ex-3DMAX core | documented earlier (R-228-04/05); re-confirmed where re-read | prior review records + this log |

## 5. Gates run before the PR

* `python3 executive/build.py` — 28/28 picks, 26 market-basis, 2 own-line, **0 provisional bounds**,
  28/28 stated formats; internal link check **231 local links, 0 broken**.
* `python3 executive/tests.py` — **15 passed / 0 failed** (sources present, maths re-derived from the
  stored rows, no Hotspawn crowd value anywhere in board data).
* `python3 -m unittest discover -s tests` — **267 OK** (includes the landing-page, console,
  own-line and feed-consumption contracts).
* Every table row above carries a source link; values this pass could not confirm are blank in
  `executive/data/analysis.csv` and listed in the flags column.

— session `arena/e13aca8a`, 2026-10-14.
