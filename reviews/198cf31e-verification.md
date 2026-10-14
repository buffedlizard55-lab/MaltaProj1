# Line-by-line verification — session `arena/198cf31e`

Branch `arena/198cf31e-maltaproj1` · board `briefing/` · snapshot `2026-10-14T04:29:37Z`
(run [38511650170](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511650170);
the board re-reads every source every 4 hours, so the numbers on the live pages move on — the
checks in §9 and the evidence links below are what stay fixed).

## 1. What was built and why

The repository had ~20 published boards, each from a parallel session, and the root landing page
had grown **two competing "executive summary" blocks** plus a third stats strip (recorded as an
observation by session `a0bdf924`, which deliberately did not edit it). This session:

1. built one canonical board, `briefing/`, that publishes a pick for **every** open Hotspawn CS2
   fixture with a source link on each row;
2. resolved the six teams that were stopping low-tier matches from getting a pick, each against
   an official page (§4);
3. collapsed the competing summaries at the top of the root `index.html` into one, keeping every
   pre-existing card and link in a clearly labelled archive section;
4. wired a 4-hourly fail-closed refresh.

Hotspawn supplies **fixture identity and UTC lock/start epochs only**. Its crowd pick
percentages are dropped at parse time and are never written to disk; a test asserts this
(`briefing/tests.py`).

## 2. Results

| Metric | Value |
|---|---|
| CS2 fixtures in the Hotspawn payload | 88 |
| Open (lock time still ahead) | **28** |
| Locked / stale | 1 / 59 |
| Picks published | **28 / 28** |
| Priced by an outside market | 17 (6 Pinnacle, 9 Thunderpick via bo3.gg, 2 Polymarket) |
| Our own originated line | 11 |
| Blank / no pick | 0 |
| Flags raised | 38 |

## 3. Every published row, with its source

| Fixture | Match | Pick | Pick % | Basis | Outside price | Source record | Primary source |
|---|---|---|---|---|---|---|---|
| 1079621 | Gothic v Lavked | **Lavked** | 59.52% | MODEL | — | `1079621` | [official Valve standings](https://www.hotspawn.com/matches/gothic-vs-lavked-cct-europe-2026-series-11-1079621) |
| 1081111 | Enjoy v B8 Academy | **Enjoy** | 58.13% | PINNACLE | 1.6061 / 2.23 | `1638339066` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1080176 | 9z v Aurora | **Aurora** | 72.41% | PINNACLE | 3.46 / 1.3185 | `1638111785` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1079438 | Astralis v Sashi | **Astralis** | 85.37% | BOOK | 1.08 / 6.3 | `131331` | [Thunderpick](https://thunderpick.io/match/2767822) |
| 1079439 | HOTU v Fnatic | **Fnatic** | 53.64% | PINNACLE | 2.04 / 1.7634 | `1637867148` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1079622 | ex-RUSTEC v mellren | **ex-RUSTEC** | 67.00% | PREDICTION | 1.4925 / 3.0303 | `1179792` | [Polymarket](https://polymarket.com/event/cs2-rustec-mellre-2026-10-14) |
| 1080177 | Falcons v Ninjas in Pyjamas | **Falcons** | 75.19% | PINNACLE | 1.2703 / 3.85 | `1638111674` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1081112 | Banda chuya v 6666 | **6666** | 54.97% | MODEL | — | `https://play.hotspawn.com/lobby` | [official Valve standings](https://play.hotspawn.com/lobby) |
| 1080178 | Legacy v PARIVISION | **Legacy** | 54.96% | BOOK | 1.68 / 2.05 | `131661` | [Thunderpick](https://thunderpick.io/match/2796375) |
| 1079623 | G2 Ares v The Last Resort | **G2 Ares** | 69.50% | PREDICTION | 1.4388 / 3.2787 | `1179794` | [Polymarket](https://polymarket.com/event/cs2-g2a-tlr-2026-10-14) |
| 1081113 | Ryvex v PCIFIC | **PCIFIC** | 59.46% | MODEL | — | `https://play.hotspawn.com/lobby` | [official Valve standings](https://play.hotspawn.com/lobby) |
| 1080179 | FURIA v BetBoom | **FURIA** | 68.24% | BOOK | 1.35 / 2.9 | `131662` | [Thunderpick](https://thunderpick.io/match/2796374) |
| 1079624 | FORZE Reload v LFO 10 | **FORZE Reload** | 63.13% | MODEL | — | `1079624` | [official Valve standings](https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624) |
| 1080279 | WROTBERRY v EAC | **WROTBERRY** | 56.74% | MODEL | — | `1080279` | [official Valve standings](https://www.hotspawn.com/matches/wrotberry-vs-eac-elisa-breakout-series-2-1080279) |
| 1079440 | MIBR v BC.Game | **MIBR** | 57.37% | PINNACLE | 1.6494 / 2.22 | `1637936745` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1079442 | Heroic v Envy | **Heroic** | 64.07% | PINNACLE | 1.4695 / 2.62 | `1637999450` | [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) |
| 1080280 | ENCE v BOJONG | **ENCE** | 71.11% | BOOK | 1.3 / 3.2 | `131774` | [Thunderpick](https://thunderpick.io/match/2807501) |
| 1080281 | WROTBERRY v ENCE | **WROTBERRY** | 57.14% | MODEL | — | `1080281` | [official Valve standings](https://www.hotspawn.com/matches/wrotberry-vs-ence-elisa-breakout-series-2-1080281) |
| 1080282 | EAC v BOJONG | **EAC** | 76.92% | BOOK | 1.2 / 4.0 | `131776` | [Thunderpick](https://thunderpick.io/match/2807496) |
| 1080283 | WROTBERRY v BOJONG | **WROTBERRY** | 76.97% | MODEL | — | `1080283` | [official Valve standings](https://www.hotspawn.com/matches/wrotberry-vs-bojong-elisa-breakout-series-2-1080283) |
| 1080284 | EAC v ENCE | **EAC** | 61.54% | BOOK | 1.5 / 2.4 | `131778` | [Thunderpick](https://thunderpick.io/match/2807492) |
| 1080285 | Voca v Phantom | **Phantom** | 51.35% | BOOK | 1.9 / 1.8 | `131779` | [Thunderpick](https://thunderpick.io/match/2807497) |
| 1080286 | HAVU v RoundsGG | **HAVU** | 65.38% | MODEL | — | `1080286` | [official Valve standings](https://www.hotspawn.com/matches/havu-vs-roundsgg-elisa-breakout-series-2-1080286) |
| 1080287 | Voca v HAVU | **Voca** | 65.53% | BOOK | 1.42 / 2.7 | `131781` | [Thunderpick](https://thunderpick.io/match/2807499) |
| 1080288 | Phantom v RoundsGG | **Phantom** | 72.70% | MODEL | — | `1080288` | [official Valve standings](https://www.hotspawn.com/matches/phantom-vs-roundsgg-elisa-breakout-series-2-1080288) |
| 1081120 | mellren v Privateer | **mellren** | 68.98% | MODEL | — | `https://play.hotspawn.com/lobby` | [official Valve standings](https://play.hotspawn.com/lobby) |
| 1080289 | RoundsGG v Voca | **Voca** | 73.82% | MODEL | — | `1080289` | [official Valve standings](https://www.hotspawn.com/matches/roundsgg-vs-voca-elisa-breakout-series-2-1080289) |
| 1080290 | Phantom v HAVU | **Phantom** | 68.24% | BOOK | 1.35 / 2.9 | `131784` | [Thunderpick](https://thunderpick.io/match/2807508) |

`Source record` is the source's own identifier for that match (Pinnacle matchup id, bo3.gg match
id, Polymarket event id, or the Hotspawn fixture id), so any row can be re-pulled by hand.

## 4. Teams that had no rating, resolved one by one against official pages

The official Valve file (`standings_global_2026_10_05.md`) does not contain these teams under
their Hotspawn name, or contains the name twice. Each was resolved by roster, and each row on
the board carries the evidence link.

| Hotspawn name | Resolved to | Rating | Official evidence | How it was checked |
|---|---|---|---|---|
| `ex-RUSTEC` | Valve global **#92** | 1066 | [HLTV event 9442](https://www.hltv.org/events/9442/cct-2026-europe-series-11) | The file has two `ex-RUSTEC` entries (#92 1066 pts, #152 824 pts). HLTV shows the CCT Series 11 entrant at VRS #93 with shalfey, Brilliance and youka — the #92 roster. The #152 roster has none of shalfey, glowiing or yiksrezo. |
| `6666` | Valve global **#127** | 923 | [HLTV event 9441](https://www.hltv.org/events/9441/cct-2026-europe-series-11-closed-qualifier) | Two `6666` entries (#127 923 pts, #368 425 pts). HLTV lists the entrant at VRS #127 with amster, kL1o, rendysky, skcH — an exact match for the #127 roster. |
| `Banda chuya` | Valve global **#165** | 801 | [HLTV event 9441](https://www.hltv.org/events/9441/cct-2026-europe-series-11-closed-qualifier) | Two `Banda Chuya` entries (#165 801 pts, #373 402 pts). HLTV lists the entrant at HLTV #161 with tomiko, maaryy, AdrieN, ezox, Showk — the complete #165 roster; #373 has only two players. |
| `Envy` | Valve global **#21** ("3DMAX") | 1500 | [HLTV news 45594](https://www.hltv.org/news/45594/envy-return-to-cs-with-ex-3dmax-roster) | Envy is absent from the 2026-10-05 Valve file under that name. HLTV reported on 2026-09-29 that Envy signed the ex-3DMAX roster (Maka, Lucky, misutaaa, Kursy, Graviti), which is exactly the Valve `3DMAX` entry. Cross-checked on [team 5991](https://www.hltv.org/team/5991/envy) and [match 2399137](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii). |
| `LFO 10` | HLTV Valve ranking **#168** | 771 | [HLTV Valve ranking 2026-10-10](https://www.hltv.org/valve-ranking/teams/2026/october/10) | Not in the Valve file (only LFO 7/8/9 are). HLTV's own Valve-ranking page publishes it at #168 with 771 points, roster dottie / flaw / Sapec. Corroborated by [match 2399361](https://www.hltv.org/matches/2399361/ence-vs-lfo-10-esl-challenger-league-season-52-europe-cup-8). Note: this rating comes from HLTV, not the Valve file, and the board labels it as such. |
| `RoundsGG` | Valve global **#310** ("ROUNDS") | 548 | [HLTV team 12457](https://www.hltv.org/team/12457/rounds) | No `RoundsGG` in the Valve file. HLTV's ROUNDS page lists ykis, Monoxx, Kollo, Lapa, Tumppis — the complete Valve `ROUNDS` roster. Polymarket's own market title for the same match also reads "RoundsGG". |

## 5. Independent cross-check of the market prices

The bo3.gg-relayed Thunderpick prices were checked against Polymarket's own published markets for
the same Elisa BreakOut Series #2 matches ([polymarket.com/esports/cs2](https://polymarket.com/esports/cs2)):

| Match | Thunderpick via bo3.gg | Polymarket (independent) |
|---|---|---|
| Voca v Phantom (16 Oct 08:00) | 48.7% Voca | 47¢ / 54¢ → 46.5% Voca |
| Voca v HAVU (16 Oct 12:00) | 65.5% Voca | 71¢ / 39¢ → 64.5% Voca |
| Phantom v HAVU (16 Oct 18:00) | 68.2% Phantom | 79¢ / 48¢ → 62.2% Phantom |

The two independent sources agree on the favourite in all three and sit within ~6 pp. The board
uses the bookmaker price and records the prediction-market price as a separate row.

## 6. Our own line: what it is, and how bad it is

p(map) = 1 / (1 + 10^(-(ratingA - ratingB) / scale)), then the sourced best-of transform
(BO3: p²(3-2p), BO5: p³(10-15p+6p²)).

`scale` is fitted by least squares against the de-vigged outside prices read in the same run:

- **scale = 1408.5** points per 10:1 map-odds ratio, fitted on **n = 17** market-priced fixtures
- **RMSE = 10.37 pp**, **worst error = 23.51 pp**

That is a weak fit and is published as such. It says the outside markets are considerably sharper
than a single-parameter logistic on Valve ranking points — which is expected, because the markets
price form, map pool and roster changes that a ranking file does not. Every model row is labelled
`MODEL`, every row where the market and our line name different winners is flagged
`FL-MODEL-MARKET-SPLIT` and both numbers are shown. Where a market price exists the market wins;
our line is only ever the fallback.

## 7. Flags (38) — published on `briefing/flagged.html`, none blocking

| Flag | Count | Meaning |
|---|---|---|
| `FL-PREDICTION-MARKET` | 14 | Probability backed by Polymarket, a prediction market, not a bookmaker. |
| `FL-RATING-AMBIGUOUS` | 13 | The Valve file contains the name more than once with different points; the row resolves it against HLTV and cites that page. |
| `FL-FORMAT-UNKNOWN` | 5 | Hotspawn publishes no series format and no source in this run states one, so the model line is a single-map estimate. |
| `FL-MODEL-MARKET-SPLIT` | 3 | Our rating line and the outside price name different winners (1079439, 1079623, 1080285). The pick follows the market. |
| `FL-DUPLICATE-QUOTE` | 3 | Two fixtures carry the same price pair from the same book (1080286/1079623, 1080287/1079442, 1080290/1080179). |

**On `FL-DUPLICATE-QUOTE`:** all three were checked by hand. The joins matched on *different*
source records, *different* source kickoffs and *different* team names — e.g. 1080290
(Phantom v HAVU, bo3.gg id 131784, 16 Oct 18:00) and 1080179 (FURIA v BetBoom, bo3.gg id 131662,
14 Oct 16:00) both carry Thunderpick 1.35 / 2.9. This is a coarse odds ladder, not a mismatch.
The prices are kept and the flags remain so a reviewer can re-check rather than take it on trust.

## 8. Irregularities found in the repository (not caused by this session)

1. **Leaked conflict-marker text rendering as visible page copy.** The root `index.html` shipped
   two lines of `#`-prefixed merge-conflict commentary ("# Conflict resolved 2026-10-14 …") as
   visible text on the live landing page. Removed in this session's landing-page edit; flagged
   here because the same pattern could exist on other pages.
2. **Two competing executive summaries** on the root page (recorded by `a0bdf924`): one pointing
   at `picks-full/` ("24/28 outside lines"), one at `everypick/` ("28/28"), plus a third stats
   strip from `slate/` reading "5 Supported picks". Addressed by this session: both blocks are
   preserved verbatim under a new "All boards, and research from earlier sessions" heading, and
   the page now opens with a single summary.
3. **Valve's official standings are 9 days old.** The newest file on the official
   [ValveSoftware/counter-strike_regional_standings](https://github.com/ValveSoftware/counter-strike_regional_standings)
   repo is `standings_global_2026_10_05.md` (verified by listing `live/2026` through the GitHub
   API). Every rating row is stamped with that date.
4. **The global Valve file is a strict superset of the regional files.** Europe (245), Americas
   (89) and Asia (46) were checked against global (380): no team appears in a regional file that
   is absent from global. The regional files were still useful — they exposed the duplicate-name
   rosters used in §4.
5. **`1.80 / 1.80` placeholder prices** reported by EGamersWorld for some fixtures (flagged by
   earlier sessions as PF-01) are not used here: this board does not read EGamersWorld at all,
   and `briefing/tests.py` asserts every published price is strictly greater than 1.0.

## 9. Verification performed

- `briefing/tests.py` — maths (de-vig sums to 1, series transforms, logistic symmetry,
  calibration), board invariants (every pick is a team in the fixture, every probability pair
  sums to 1, every unpicked row is flagged, every rating has a source URL, **no crowd-percentage
  field is present anywhere in the archived payload**), and page checks.
- `briefing/linkcheck.py` — 8 pages, 155 internal links, **0 broken**.
- Repository-wide: `scripts/audit_91e444dd.py` → **208 HTML pages, 0 link errors**;
  `python -m unittest discover -s tests` → **180 tests, OK**.
- Every source response is archived with HTTP status, byte count, SHA-256 and capture time in
  `briefing/data/capture.json` and shown on `briefing/sources.html`.

## 10. Known limitations

- Only 17 of 28 open fixtures have an outside price. The other 11 rest on our rating line, whose
  in-sample RMSE is 10.4 pp; treat those percentages as indicative, not as prices.
- Pinnacle's public guest feed lists few CS2 leagues, so most book prices are relayed by bo3.gg
  with the bookmaker named. Each such row links to the bookmaker's own match page.
- Polymarket prices sum to 1.0 by construction, so no overround can be shown for them; they are
  labelled as a prediction market throughout.
- HLTV's ranking pages returned HTTP 200 to the collector but no parseable ranking block, so HLTV
  is used for identity evidence (§4) and for the LFO 10 rating, not as an automated feed.
