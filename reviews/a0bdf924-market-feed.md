# Secondary-market feed — verification record (session `arena/a0bdf924`)

Scope: MF-01…MF-04 in `COORDINATION.md`. Files: `feeds/**`, `.github/workflows/feed-a0bdf924.yml`, this file.
No other session's file was edited. Published page: `feeds/index.html` (+ `flagged.html`, `method.html`).

## What was built

An **automated, CI-run** reader of two public market sources that the existing pipelines did not reach, matched
strictly to the live Hotspawn CS2 fixture list, de-vigged, archived and tested, refreshing hourly with no manual input.

| Source | Endpoint (public, no key) | What is used | Official link per row |
|---|---|---|---|
| Hotspawn pick'em | `play.hotspawn.com/cs2-pickems`, `/lobby`, `/thp-pickems` → `<script id="ng-state">` | fixture id, teams, competition, tier, `scheduled_start_time`, `lock_time` (crowd % dropped at parse time) | Hotspawn match permalink from the same payload |
| Polymarket | `gamma-api.polymarket.com/events?series_id=10310&closed=false` ([series 10310](https://gamma-api.polymarket.com/series?slug=counter-strike) = "Counter Strike" daily matches) | `moneyline` market: outcome prices, bid/ask, spread, depth, volume, `gameStartTime`; title gives BO | `https://polymarket.com/event/<slug>` |
| bo3.gg | `api.bo3.gg/api/v1/matches?filter[matches.status][in]=upcoming&filter[matches.discipline_id][eq]=1&with=teams,tournament` | `bo_type` (series format), `start_date`, relayed bookmaker quote `bet_updates` (provider, bookmaker match URL, decimal odds, `active`) | bookmaker match URL (e.g. thunderpick.io/match/…) + bo3.gg match page |
| OddsDigger | `oddsdigger.com/e-sports` | probe only — `/e-sports/counter-strike` is HTTP 410 and the index table has no kickoff times, so it cannot pass the kickoff rule | — |

Rules: a quote attaches only with ≥1 exact team name (or evidence-linked alias) **and** the other name exact
(kickoff ≤ 60 min) or a substring/initials variant (kickoff ≤ 15 min). Same team vs a different opponent at the
same kickoff = conflict, never used. Bookmaker odds de-vigged multiplicatively; Polymarket prices normalised and
gated (spread ≤ 0.10, depth ≥ $100, not degenerate, not closed/live). Blank + flag where nothing passes.

## Verification performed

1. **Unit tests** (`feeds/tests.py`: names, aliases, de-vig arithmetic, Polymarket gates, bo3.gg team-id
   realignment, matching windows, conflict detection, time parsing) — pass locally and as the first CI step.
2. **Re-derivation**: the published CSV/JSON must be byte-identical to a fresh join of the archived raw captures
   (`feeds/data/raw/*.json.gz`, SHA-256 of every full response in `feeds/data/capture.json`). Enforced in CI.
3. **No crowd data**: the archived Hotspawn rows are a whitelist without `participants*_picked_percent` /
   `total_picks`; a test fails if either string appears.
4. **CI runs on the session branch** (no manual input):
   * [38503145599](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38503145599) — all steps green;
     Hotspawn answered **403** to all three pages for a JSON-first `Accept` header → labelled fallback to
     `cs2/data/capture.json` (MF-12) worked as designed.
   * [38503458961](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38503458961) — HTML-first `Accept`
     (same as `cs2/common.py`) → Hotspawn **200** on all three pages (88 CS2 rows), Polymarket 96 open CS2 match
     events, bo3.gg 344 upcoming CS2 matches.
5. **Independent price cross-check against Pinnacle** (read-only from `cs2/data/analysis.csv`, captured 02:45:17Z)
   on the 7 fixtures Pinnacle prices: bookmaker-via-bo3.gg and Polymarket de-vigged probabilities are within
   **3.1 pp** of Pinnacle (mean 1.63 pp over 14 comparisons) and name the **same favourite in 14/14**.

   | Fixture | Pinnacle | Thunderpick via bo3.gg | Polymarket |
   |---|---|---|---|
   | 1080176 9z v Aurora | 28.0 | 27.0 | 26.5 |
   | 1079439 HOTU v Fnatic | 49.6 | 48.1 | 46.5 |
   | 1080177 Falcons v NIP | 75.2 | 75.7 | 74.0 |
   | 1080178 Legacy v PARIVISION | 53.9 | 56.0 | 56.5 |
   | 1080179 FURIA v BetBoom | 70.0 | 68.2 | 70.5 |
   | 1079440 MIBR v BC.Game | 57.4 | 56.0 | 55.5 |
   | 1079442 Heroic v Envy | 64.1 | 65.5 | 66.5 |

   (team-A win %, bo3.gg/Polymarket from capture 02:50:49Z.)
6. **Aliases checked on HLTV by this session** (fetched 02:52–02:53Z):
   [2399418 "WBT vs. EAC"](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) — Elisa BreakOut
   Series 2, Group A, Best of 1 (LAN), 04:00 15 Oct (UTC-4) = 08:00Z = Hotspawn WROTBERRY v EAC;
   [2399427 "Phantom vs. ROUNDS"](https://www.hltv.org/matches/2399427/phantom-vs-rounds-elisa-breakout-series-2) — Group B,
   Best of 1 (LAN), 10:00 16 Oct (UTC-4) = 14:00Z = Hotspawn Phantom v RoundsGG. Both pages also confirm **BO1**
   for Elisa BreakOut, matching bo3.gg `bo_type=1` and Polymarket "(BO1)".

## Coverage (capture 2026-10-14T02:54:23Z, run 38503458961)

28 open Hotspawn CS2 fixtures → **25 priced by ≥1 secondary source** (20 bookmaker via bo3.gg, 15 Polymarket, 10 both),
**26 with series format** (14 BO3, 12 BO1). Before this feed the automated boards had market prices for 7/28 (Pinnacle)
and Hotspawn's payload gives no format for any fixture. The live table is `feeds/data/fixtures.csv`; the snapshot:

| # | Hotspawn fixture | Kickoff UTC | BO | Bookmaker via bo3.gg (team A %) | Polymarket (team A %) | Secondary favourite | Flags |
|---|---|---|---|---|---|---|---|
| 1 | [1079621](https://www.hotspawn.com/matches/gothic-vs-lavked-cct-europe-2026-series-11-1079621) Gothic vs Lavked | 10-14 08:00 | 3 | — | [50.0%](https://polymarket.com/event/cs2-gothic-lavked-2026-10-14) | even (50/50) | MF-14 |
| 2 | [1081111](https://play.hotspawn.com/cs2-pickems) Enjoy vs B8 Academy | 10-14 08:00 | 3 | — | [63.5%](https://polymarket.com/event/cs2-enjoy-b8acad-2026-10-14) | Enjoy 63.5% |  |
| 3 | [1080176](https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176) 9z vs Aurora | 10-14 08:30 | 3 | [Thunderpick 27.0%](https://thunderpick.io/match/2796376) | [26.5%](https://polymarket.com/event/cs2-9z-aur1-2026-10-14) | Aurora 73.2% |  |
| 4 | [1079438](https://www.hotspawn.com/matches/astralis-vs-sashi-stake-pulse-beat-iii-1079438) Astralis vs Sashi | 10-14 10:00 | 3 | [Thunderpick 85.4%](https://thunderpick.io/match/2767822) | [83.5%](https://polymarket.com/event/cs2-ast10-sashi-2026-10-14) | Astralis 84.4% |  |
| 5 | [1079439](https://www.hotspawn.com/matches/hotu-vs-fnatic-stake-pulse-beat-iii-1079439) HOTU vs Fnatic | 10-14 10:00 | 3 | [Thunderpick 48.1%](https://thunderpick.io/match/2767823) | [46.5%](https://polymarket.com/event/cs2-hotu-fnc-2026-10-14) | Fnatic 52.7% |  |
| 6 | [1079622](https://www.hotspawn.com/matches/ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622) ex-RUSTEC vs mellren | 10-14 11:00 | 3 | — | [65.0%](https://polymarket.com/event/cs2-rustec-mellre-2026-10-14) | ex-RUSTEC 65.0% |  |
| 7 | [1080177](https://www.hotspawn.com/matches/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026-1080177) Falcons vs Ninjas in Pyjamas | 10-14 11:00 | 3 | [Thunderpick 75.7%](https://thunderpick.io/match/2796377) | [74.0%](https://polymarket.com/event/cs2-fal2-nip-2026-10-14) | Falcons 74.8% |  |
| 8 | [1081112](https://play.hotspawn.com/cs2-pickems) Banda chuya vs 6666 | 10-14 11:00 | — | — | — | — (blank) | MF-01;MF-02 |
| 9 | [1080178](https://www.hotspawn.com/matches/legacy-vs-parivision-thunderpick-world-championship-2026-1080178) Legacy vs PARIVISION | 10-14 13:30 | 3 | [Thunderpick 56.0%](https://thunderpick.io/match/2796375) | [56.5%](https://polymarket.com/event/cs2-lgc-prv-2026-10-14) | Legacy 56.2% |  |
| 10 | [1079623](https://www.hotspawn.com/matches/g2-ares-vs-the-last-resort-cct-europe-2026-series-11-1079623) G2 Ares vs The Last Resort | 10-14 14:00 | 3 | — | [65.5%](https://polymarket.com/event/cs2-g2a-tlr-2026-10-14) | G2 Ares 65.5% |  |
| 11 | [1081113](https://play.hotspawn.com/cs2-pickems) Ryvex vs PCIFIC | 10-14 14:00 | 3 | — | [16.0%](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) | PCIFIC 84.0% |  |
| 12 | [1080179](https://www.hotspawn.com/matches/furia-vs-betboom-thunderpick-world-championship-2026-1080179) FURIA vs BetBoom | 10-14 16:00 | 3 | [Thunderpick 68.2%](https://thunderpick.io/match/2796374) | [70.5%](https://polymarket.com/event/cs2-furia-bb3-2026-10-14) | FURIA 69.4% |  |
| 13 | [1079624](https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624) FORZE Reload vs LFO 10 | 10-14 17:00 | — | — | — | — (blank) | MF-01;MF-02 |
| 14 | [1080279](https://www.hotspawn.com/matches/wrotberry-vs-eac-elisa-breakout-series-2-1080279) WROTBERRY vs EAC | 10-15 08:00 | 1 | [Thunderpick 46.2%](https://thunderpick.io/match/2807510) | — | EAC 53.8% | MF-05 |
| 15 | [1079440](https://www.hotspawn.com/matches/mibr-vs-bc-game-stake-pulse-beat-iii-1079440) MIBR vs BC.Game | 10-15 10:00 | 3 | [Thunderpick 56.0%](https://thunderpick.io/match/2767837) | [55.5%](https://polymarket.com/event/cs2-mibr-bcg-2026-10-15) | MIBR 55.8% |  |
| 16 | [1079442](https://www.hotspawn.com/matches/heroic-vs-envy-stake-pulse-beat-iii-1079442) Heroic vs Envy | 10-15 10:00 | 3 | [Thunderpick 65.5%](https://thunderpick.io/match/2767856) | [66.5%](https://polymarket.com/event/cs2-hero-envy-2026-10-15) | Heroic 66.0% |  |
| 17 | [1080280](https://www.hotspawn.com/matches/ence-vs-bojong-elisa-breakout-series-2-1080280) ENCE vs BOJONG | 10-15 10:00 | 1 | [Thunderpick 71.1%](https://thunderpick.io/match/2807501) | — | ENCE 71.1% | MF-05 |
| 18 | [1080281](https://www.hotspawn.com/matches/wrotberry-vs-ence-elisa-breakout-series-2-1080281) WROTBERRY vs ENCE | 10-15 12:00 | 1 | [Thunderpick 57.0%](https://thunderpick.io/match/2807512) | — | WROTBERRY 57.0% | MF-05 |
| 19 | [1080282](https://www.hotspawn.com/matches/eac-vs-bojong-elisa-breakout-series-2-1080282) EAC vs BOJONG | 10-15 14:00 | 1 | [Thunderpick 76.9%](https://thunderpick.io/match/2807496) | — | EAC 76.9% | MF-05 |
| 20 | [1080283](https://www.hotspawn.com/matches/wrotberry-vs-bojong-elisa-breakout-series-2-1080283) WROTBERRY vs BOJONG | 10-15 16:00 | 1 | [Thunderpick 76.9%](https://thunderpick.io/match/2807511) | — | WROTBERRY 76.9% | MF-05 |
| 21 | [1080284](https://www.hotspawn.com/matches/eac-vs-ence-elisa-breakout-series-2-1080284) EAC vs ENCE | 10-15 18:00 | 1 | [Thunderpick 61.5%](https://thunderpick.io/match/2807492) | — | EAC 61.5% | MF-05 |
| 22 | [1080285](https://www.hotspawn.com/matches/voca-vs-phantom-elisa-breakout-series-2-1080285) Voca vs Phantom | 10-16 08:00 | 1 | [Thunderpick 48.6%](https://thunderpick.io/match/2807497) | [44.0%](https://polymarket.com/event/cs2-voc-pha-2026-10-16) | Phantom 53.7% |  |
| 23 | [1080286](https://www.hotspawn.com/matches/havu-vs-roundsgg-elisa-breakout-series-2-1080286) HAVU vs RoundsGG | 10-16 10:00 | 1 | [Thunderpick 76.9%](https://thunderpick.io/match/2807498) | — | HAVU 76.9% | MF-05 |
| 24 | [1080287](https://www.hotspawn.com/matches/voca-vs-havu-elisa-breakout-series-2-1080287) Voca vs HAVU | 10-16 12:00 | 1 | [Thunderpick 65.5%](https://thunderpick.io/match/2807499) | — | Voca 65.5% | MF-05 |
| 25 | [1080288](https://www.hotspawn.com/matches/phantom-vs-roundsgg-elisa-breakout-series-2-1080288) Phantom vs RoundsGG | 10-16 14:00 | 1 | [Thunderpick 86.8%](https://thunderpick.io/match/2807503) | [88.5%](https://polymarket.com/event/cs2-pha-rgg-2026-10-16) | Phantom 87.7% |  |
| 26 | [1081120](https://play.hotspawn.com/cs2-pickems) mellren vs Privateer | 10-16 14:00 | 3 | — | — | — (blank) | MF-01;MF-05 |
| 27 | [1080289](https://www.hotspawn.com/matches/roundsgg-vs-voca-elisa-breakout-series-2-1080289) RoundsGG vs Voca | 10-16 16:00 | 1 | [Thunderpick 14.6%](https://thunderpick.io/match/2807505) | — | Voca 85.4% | MF-05 |
| 28 | [1080290](https://www.hotspawn.com/matches/phantom-vs-havu-elisa-breakout-series-2-1080290) Phantom vs HAVU | 10-16 18:00 | 1 | [Thunderpick 68.2%](https://thunderpick.io/match/2807508) | — | Phantom 68.2% | MF-05 |

## Irregularities found (published on `feeds/flagged.html`; none blocks the site)

* **IRR-MF-1 — the existing Polymarket reader misses low-tier CS2 markets.** `cs2/collect.py` queries
  `markets?closed=false&limit=500&order=volume24hr` — the top 500 markets of *all* Polymarket — so 4 CS2 matches
  survived at 02:36Z, while series 10310 lists 96 open CS2 match events (15 of today's open Hotspawn fixtures pass the
  quality gates). Request to `arena/a174d77f` logged; this feed is available to consume instead.
* **IRR-MF-2 — #1079624 FORZE Reload vs "LFO 10":** bo3.gg match 131436
  [`forze-reload-vs-sokerorg-14-10-2026`](https://bo3.gg/matches/forze-reload-vs-sokerorg-14-10-2026) (CCT Europe 2026 Series 11,
  17:00Z, BO3) and Polymarket [`cs2-forzer-skr2-2026-10-14`](https://polymarket.com/event/cs2-forzer-skr2-2026-10-14)
  ("CCT Europe Series #11 Group Stage", PandaScore 1733054) both name the opponent **Sökerorg**. Not used (MF-02).
* **IRR-MF-3 — #1081112 Banda chuya vs 6666:** bo3.gg match 131877
  [`los-kogutos-vs-sixsixsixsix-14-10-2026`](https://bo3.gg/matches/los-kogutos-vs-sixsixsixsix-14-10-2026) (CCT Europe 2026 Series 12
  Play-In, 11:00Z) names the opponent **los kogutos**. Not used (MF-02).
* **IRR-MF-4 — WROTBERRY = WBT** and **RoundsGG = ROUNDS**: resolved with HLTV evidence above (`feeds/aliases.json`).
* **IRR-MF-5 — name variants accepted for review (MF-04):** Polymarket "WRAITH PCIFIC" for Hotspawn "PCIFIC"
  (#1081113, opponent Ryvex and kickoff identical) and "NIP" for "Ninjas in Pyjamas" (#1080177; Pinnacle agrees on price).
* **IRR-MF-6 — Hotspawn edge behaviour:** 403 for `Accept: application/json,…` and 200 for
  `Accept: text/html,…` from the same runner type and an honest UA (runs 38503145599 vs 38503458961).
* **IRR-MF-7 — bookmaker relay not directly checkable:** thunderpick.io answers the runner 403, so the relayed odds
  carry MF-09 on every row; the Pinnacle cross-check above is the independent control.
* **IRR-MF-8 — thin Polymarket books:** Elisa BreakOut markets spread 0.11–0.32, mellren v Privateer 0.82 → rejected (MF-05).
* **IRR-MF-9 — even market:** Gothic v Lavked priced exactly 50/50 on Polymarket (depth ≈ $6.9k) → no favourite (MF-14).
* **IRR-MF-10 — format absent at the source:** Hotspawn `best_of`/`series_format` are null on every open fixture (MF-13).

## Still blank (and why)

#1081112 and #1079624 (opponent conflicts above) and #1081120 mellren v Privateer (Polymarket spread 0.82; bo3.gg
relays no quote). These stay blank here; resolving them is research claimed by other sessions (`bdc98a9a` E-02,
`63ee81ba` X-03 for #1079624).
