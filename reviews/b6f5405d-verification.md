# Session `arena/b6f5405d` — line-by-line verification (TWC 2026 day 3, 16 October 2026)

Scope of this session: the Thunderpick World Championship 2026 day-3 board — day-1/day-2 review, today's two
deciders (Aurora vs 9z, BetBoom vs Legacy), the every-match coverage gap, and the mobile executive-summary links.
Claim and file scope: see the `arena/b6f5405d` section of [COORDINATION.md](../COORDINATION.md).

Every value below carries the source URL it was read from and the read time. Nothing here is inferred: where a value
could not be confirmed it is left blank and listed under **Not verified**. All percentages on the published pages are
recomputed at build time by `hotspawn/build.py` from the raw inputs in `hotspawn/research/day3_twc2026.json`
(decimal odds → margin removal via `common.devig_two_way`; Valve points → `common.own_line` with the calibrated slope
from `hotspawn/data/calibration.json`). No probability is typed into a file by hand.

## 1. Event and schedule

| Fact | Value | Source | Read (UTC) |
|---|---|---|---|
| Event | Thunderpick World Championship 2026, Malta, 8 teams, $1,000,000, 14–18 Oct 2026 | https://www.hltv.org/events/8932/thunderpick-world-championship-2026 | 2026-10-16 04:19 |
| Day 3 fixtures | Fri 16 Oct: Aurora vs 9z (bo3), BetBoom vs Legacy (bo3) | https://www.hltv.org/events/8932/matches | 2026-10-16 04:33 |
| Playoffs | Sat 17 Oct: FURIA vs Aurora/9z winner, Falcons vs BetBoom/Legacy winner (both bo3). Sun 18 Oct: 3rd-place decider (bo3), grand final (bo5) | https://www.hltv.org/events/8932/matches | 2026-10-16 04:33 |
| Stage labels | Aurora vs 9z = "* Group A decider match"; PARIVISION vs BETBOOM (15 Oct) = "* Group B elimination match" | https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026, https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026 | 2026-10-16 04:27–04:33 |
| Groups | Group A: Falcons, NiP, 9z, Aurora. Group B: FURIA, Legacy, PARIVISION, BETBOOM (derived from the two decider labels plus the four opening matches and the bracket) | https://www.hltv.org/events/8932/matches | 2026-10-16 04:33 |

## 2. Kickoff times — three machine-readable sources, one conclusion

| Source | What it says | Read (UTC) |
|---|---|---|
| Hotspawn TransferState (this project's own capture, `hotspawn/data/capture.json`) | Aurora–9z `start 2026-10-16T14:00:00Z`, `lock 2026-10-16T13:54:00Z`, `lock_offset_sec 360`, tier `S`, 7 offered points | 2026-10-15 22:41:15 |
| Polymarket API record for the two markets | `start_utc 2026-10-16T14:00:00Z` (Aurora Gaming vs 9z, BO3) and `start_utc 2026-10-16T17:00:00Z` (Legacy vs BetBoom Team, BO3) | 2026-10-15 22:41:17 |
| HLTV match pages | render **10:00** / **13:00** and countdowns of 9h43m / 12h43m at ~04:2xZ → 14:00Z / 17:00Z | 2026-10-16 04:26–04:33 |
| Hotspawn fixture page | renders **14:00 16 OCT** | https://www.hotspawn.com/matches/aurora-vs-9z-thunderpick-world-championship-2026-1080205 — 2026-10-16 04:40 |
| EGamersWorld event page | renders **16:00** and **19:00** (= UTC+2, venue time) | https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H — 2026-10-16 04:39 |

Conclusion published: **14:00Z (Aurora–9z) and 17:00Z (BetBoom–Legacy), i.e. 16:00 and 19:00 in Malta.** Human-readable
clocks are viewer-timezone renderings and are never used as times on the page. This corrects two earlier readings in
this project: (a) "venue-local CEST" was assumed while HLTV was in fact rendering in the fetch path's timezone (UTC-4),
and (b) EGamersWorld was described as GMT+3 when its 16:00/19:00 displays are UTC+2. The UTC values above agree with
Hotspawn's own epochs, so no irregularity record is required.

## 3. Day 1 and day 2 results (all series scores)

Source for every series score: https://www.hltv.org/results?event=8932 (read 2026-10-16 04:19 and 04:32).

| Day | Match | Score | Maps (where re-verified this session) | HLTV |
|---|---|---|---|---|
| 14 Oct | 9z vs Aurora | 2-0 | Inferno 13-11, Nuke 13-1 (page re-read 04:34) | https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026 |
| 14 Oct | Falcons vs NiP | 2-0 | not re-verified this session | https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026 |
| 14 Oct | Legacy vs PARIVISION | 2-0 | not re-verified this session | https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026 |
| 14 Oct | FURIA vs BETBOOM | 2-0 | not re-verified this session | https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026 |
| 15 Oct | Aurora vs NiP | 2-0 | not re-verified this session | https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026 |
| 15 Oct | 9z vs Falcons | 1-2 | Nuke 9-13, Mirage 13-8, Dust2 9-13 (page re-read 04:37) | https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026 |
| 15 Oct | PARIVISION vs BETBOOM | 1-2 | Ancient 13-10 PARIVISION, Anubis 4-13, Mirage 7-13 (page re-read 04:27) | https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026 |
| 15 Oct | Legacy vs FURIA | 1-2 | not re-verified this session | https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026 |

The day-2 Legacy 1-2 FURIA score is cross-checked by EGamersWorld's schedule row (15.10.26, "1:2") at
https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H (read 04:39).

## 4. Outside prices and crowd ownership for today's deciders

| Input | Aurora–9z | BetBoom–Legacy | Source & read time |
|---|---|---|---|
| bc.game schedule row (secondary relay via EGamersWorld) | 1.40 / 2.70 | 2.50 / 1.48 | https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H — 2026-10-16 04:39 |
| bc.game prematch block (same page) | 1.43 / 2.76 | 2.52 / 1.50 | same page — 2026-10-16 04:39 |
| Polymarket match-winner market | 0.685 / 0.315 (US$8,364.86 traded) | 0.605 / 0.395 (Legacy first) | this project's own capture of the Polymarket API, `hotspawn/data/capture.json` — 2026-10-15 22:41:17 |
| Hotspawn crowd ownership | 88 / 13 (9 picks at the capture) | 50 / 50 | https://play.hotspawn.com/lobby — 2026-10-16 04:22 |
| Official Valve points (2026-10-05 snapshot) | Aurora 1716 (#9), 9z 1543 (#17) | Legacy 1931 (#2), BetBoom 1596 (#11) | https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md (repo HEAD `eec4853d…`, cloned 2026-10-16 04:29) |
| Pinnacle | **no quote** for either fixture — the live read returned 8 CS2 quotes, none for TWC | same | `hotspawn/data/capture.json`, Pinnacle guest API, 2026-10-15 22:41:17 |

Margin removal on the bc.game rows gives Aurora 65.9% / 9z 34.1% (1.40/2.70) and 65.9% / 34.1% (1.43/2.76);
BetBoom 37.2% / Legacy 62.8% (2.50/1.48) and BetBoom 37.3% / Legacy 62.7% (2.52/1.50). The Polymarket prices are
already normalised. The own line is `1/(1+10^(-0.4598·Δpoints/400))` → Aurora 61.0% / 9z 39.0%; Legacy 70.3% /
BetBoom 29.7%. Hotspawn's crowd share is ownership only and is never an input to any probability on the site.

## 5. Roster changes, form and maps — checked, not assumed

| Claim | Verdict | Source |
|---|---|---|
| "Aurora had a recent roster change" | Partly. The change is a **summer rebuild now ~100 days old**: Jimpphat joined 3 Jul 2026, kyxsan joined from Falcons as in-game leader on 8 Jul 2026, coach ash; MAJ3R, soulfly and coach Fabre left. No stand-in or replacement is reported for this event. | https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan (reported 8 Jul 2026), https://www.hltv.org/team/11861/aurora, https://liquipedia.net/counterstrike/Aurora_Gaming |
| 9z roster change | None found; 9z's five (dgt, HUASOPEEK, luchov, max, meyern) equals Valve's 2026-10-05 snapshot. | Valve standings file above; https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026 |
| BetBoom / Legacy roster changes | None found around this event; both fives equal Valve's 2026-10-05 snapshot. | Valve standings file; https://www.hltv.org/betting/analytics/2399413/betboom-vs-legacy-thunderpick-world-championship-2026 |
| Head-to-head | 9z won the only recent meeting 2-0 on 14 Oct at this event; HLTV's analytics summary states Aurora "played 2 matches against 9z in the past 30 days, and lost the latest". | https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026, https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026 |
| HLTV community vote | Aurora 81.0% / 9z 19.0% — a site visitor vote, **not a price**, and not used as one. | https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026 (read 04:31) |
| Map pool | Aurora: Nuke 78% (9 maps), Anubis 75% (12), Mirage 62% (16), Ancient first-ban 87%. 9z: Mirage 67% (6), Cache 50% (4), Dust2 43% (7), Nuke 30% (10), Inferno 25% (4), Anubis first-ban 84%. | https://www.hltv.org/betting/analytics/2399412/aurora-vs-9z-thunderpick-world-championship-2026 |
| Lineups and form | Hotspawn's fixture page lists both fives and the last five series for each side (9z: L Falcons 1-2, W Aurora 2-0, L FURIA 0-2, W BetBoom 2-0, L NaVi 0-2). | https://www.hotspawn.com/matches/aurora-vs-9z-thunderpick-world-championship-2026-1080205 |

## 6. What the board does with these inputs (rule v2, unchanged)

`hotspawn/model.py` classifies each open fixture from the consensus of the outside estimate(s) and our own line,
against the crowd share: VALUE (crowd is not even on the favourite) → CONTRARIAN (underdog ≥ 38%, every source
≥ 30%, crowd ≤ underdog − 10 pp) → SITUATIONAL (underdog ≥ 30%, every source ≥ 25%, crowd ≤ half the underdog's
chance, and a verified factor against the favourite with none against the underdog) → LONG SHOT (≥ 20%, crowd
≤ 10%) → CHALK. With the inputs above:

* **Aurora vs 9z** — consensus underdog (9z) ≈ 35%; crowd on 9z 12.9% (normalised from 88/13). CONTRARIAN needs
  38%, so the rule does not fire; SITUATIONAL does (the July rebuild is the rule's active moderate factor against
  Aurora). The board therefore keeps **Aurora** as the pick and shows **9z** as the leaderboard play, with the
  leverage (crowd 12.9% vs ≈35% chance, i.e. winning that side gains on ~87% of the field picking this match)
  printed on the page rather than hidden.
* **BetBoom vs Legacy** — consensus underdog (BetBoom) ≈ 35% but the crowd is level (50/50), so no crowd-fade
  rule applies; class CHALK → pick **Legacy** by market and own line. Legacy's own line is 70.3% while the market
  pays 62.7%: the favourite is a value-lean favourite, which is why the board does not fade it.

Both fixtures lack a Pinnacle price, so they sit on rung B (Polymarket) in the ladder — recorded, not hidden.

## 7. Coverage gap (every-match guarantee)

`BetBoom vs Legacy` (Hotspawn `1081775`) was **not** in the 2026-10-15T22:41:15Z Hotspawn capture, so the board has no
row for it. It is in Hotspawn's lobby now (https://play.hotspawn.com/lobby, read 04:22). Rather than publishing a
blank, the day-3 section renders the fallback lean from the outside prices plus our own line, labels it
"no board row", and the unresolved page and the executive summary carry a **coverage gap** block naming the fixture,
the reason and the sources. The next three-hourly refresh (triggered by this merge) re-reads Hotspawn and should pick
it up; the invariant `hotspawn/tests.py::Day3.test_coverage_gaps_are_surfaced_when_they_exist` fails the build if a
researched fixture is neither covered by the board nor named as a gap.

## 8. Tests run in this session (all local, offline inputs)

* `python3 hotspawn/model.py` → 22 open / 86 fixtures, rungs A 6 / B 16 / C 0 / D 0.
* `python3 hotspawn/build.py` → 7 pages; verified by re-reading the generated HTML that the day-3 table, the
  coverage-gap block and the internal links (`strategy.html#day3`, `unresolved.html`) are present.
* `python3 hotspawn/tests.py` → **31 tests, all passing** (added: raw-input discipline, two-way price sanity,
  board cross-check on teams/start/lock/Valve points, rendered-and-linked section, coverage-gap surfacing,
  computed fallback lean).
* `python3 tests/test_landing_43c32386.py` → 4 tests passing (root landing quick-link contract).
* `python3 -m unittest discover -s tests` → 405 tests with the same **pre-existing** failures recorded in
  `COORDINATION.md`: `test_457629c4.TestBoardInvariants.test_rebuild_is_deterministic_with_a_pinned_clock` (error),
  `test_7759beef.ValuePicksBoardTests.test_coverage_page_lists_every_captured_fixture` and
  `...test_every_open_executive_fixture_has_a_pick_and_two_probabilities` (failures; that board covers
  1081526–1081531 while the open fixtures are 1079440/1079442/1080202–1080204/1080280–1080284). Not owned by this
  session; left untouched and logged.

## 9. Not verified / left blank (deliberately)

* Hotspawn **lock time for BetBoom–Legacy**: the fixture was not in the capture, so no lock is published. Hotspawn's
  own offset is 360 s before start (would be 16:54Z) — that is arithmetic, not a read, and is labelled as derived.
* **Map vetoes for today's deciders**: not published before the match; both pages say maps TBA.
* **Day-1/day-2 map scores** for Falcons–NiP, Legacy–PARIVISION, FURIA–BETBOOM, Aurora–NiP and Legacy–FURIA were not
  re-read in this session; only their series scores are asserted here.
* **No price is taken from HLTV's analytics pages**: the odds cells there render placeholder values for anonymous
  readers; HLTV is used for facts (ranks, H2H, form, map pools) only.
* **No price is taken from Hotspawn**: its crowd share is ownership, its site is used for lineup/form/stage only.
* The 26 other red/flagged items outside this scope (four failing workflows on `main` — Slate capture `180a42a0`
  run 38836131515, Live picks board `457629c4` runs 38836621281/38836170355, Every-match CS2 picks rebuild
  `75fd29ee` run 38836582191, O-01 own-line model (VRS) run 38836621329) are pre-existing, belong to other sessions,
  and are listed for review rather than edited here.
