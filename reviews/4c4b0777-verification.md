# Release assurance — arena/4c4b0777

## Scope and honesty

This is an incremental integration audit of the **canonical `hotspawn/` board**, not a claim
that every historical dashboard, source value, or line of the entire 57-directory repository
has been independently verified. Earlier boards remain archived. No probability is an official
fact: bookmaker-normalized, prediction-market, and project-model estimates are labelled separately.

## Independent source reads — 2026-10-16 UTC

- Hotspawn: https://play.hotspawn.com/lobby (all fetched chunks containing current fixture links).
  It now lists BetBoom–Legacy `1081775`, unlike the older 21:34Z capture.
- HLTV eight result pages: match IDs [2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026),
  [2399385](https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026),
  [2399386](https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026),
  [2399387](https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026),
  [2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026),
  [2399409](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026),
  [2399410](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026),
  [2399411](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026).
  Winners, series scores and all played map scores agree with the dated observations in the audit.
  **HLTV is not the organizer; organizer confirmation stays unverified.**
- Day-3 BO3 deciders: [Aurora–9z](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026),
  [BetBoom–Legacy](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026).
- Aurora roster: [team](https://www.hltv.org/team/11861/aurora),
  [dated July tracker](https://www.hltv.org/news/44998/summer-2026-rostermania-as-it-happened).
  Jimpphat July 3 and kyxsan July 8, not a days-old emergency change. Team-issued confirmation unverified.
- [Polymarket event](https://polymarket.com/event/cs2-aur1-9z-2026-10-16): contains series and map contracts;
  website's 70¢/31¢ display not substituted for the canonical API's match-winner estimate. Execution
  depth/spread remain unverified. Counterexample to calling all displayed percentages calibrated odds.
- Gap source reads and rejection reasons are recorded in [gap-research.json](4c4b0777-gap-research.json).
  Direct Pinnacle website read HTTP 500, not a statement of market nonexistence. The successful
  canonical API capture independently has no matching quote for those two fixtures.
- Official Valve file independently downloaded using the authenticated public GitHub contents API
  at commit [`eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md).
  Duplicate labels/points/rosters in the gap report are confirmed. Historical points do not establish
  an unverified current five.

## Reproducible verification

- `python hotspawn/tests.py`: 25 passed (sources, crowd isolation, complementary probabilities,
  complete capture coverage, blank unresolved estimates, no broken generated-page links).
- `python -m unittest discover -s tests -p test_4c4b0777.py -v`: 11 passed.
- `python -m unittest discover -s tests -p test_landing_43c32386.py -v`: 4 passed.
- `python -m unittest discover -s tests -p test_1b6ae823.py -v`: 25 passed.
- `node --check js/landing.js`: passed.
- `python scripts/audit_91e444dd.py`: 272 HTML pages, **0 local-link errors**. Its unrelated report-only
  output was restored; this session does not own `status/report.json`.
- Live-refresh CI [38849930923](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38849930923)
  and [38850130426](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38850130426): successful
  live collect → calibrate → model → build → 25 tests → actual Chromium report. The latter saved the
  checked capture to this session branch. No changes to the existing scheduled workflow or source model.
- Real 390×844 report in `hotspawn/data/mobile_check.json`: all six canonical/root pages have scroll
  width = client width = 390, single h1, 31 pick cards. New PR assurance also checks audit/root/picks/
  unresolved at 360, 390, 768px and fails rather than silently skipping an unavailable browser.

## Non-blocking flagged irregularities

Initial broad local run: 405 tests, two `test_7759beef` stale-coverage failures and one
`test_457629c4` livelines deterministic-build error (missing fixture key). Existing unrelated scopes,
reported publicly rather than edited or hidden. Their test-only console/summary mutations restored.
PR #150 is owned by another session, left untouched. These findings do not imply a broken canonical
site: the canonical release gates and real layout check are independent and must pass.

The day-1 4/4 leaderboard replay is **retrospective**, not four archived prospective picks. Day 2 has
three frozen picks, two correct in either strategy, and no frozen Aurora–NiP pick. No calibration or
leaderboard-optimization claim can be established from that tiny sample. Near-even markets require
explicit tiebreak caution. Scheduled collection cannot guarantee future 100% price coverage.

## Publishing

Release PR: https://github.com/buffedlizard55-lab/MaltaProj1/pull/153
Live URLs after deployment:
- https://buffedlizard55-lab.github.io/MaltaProj1/
- https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/picks.html
- https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/unresolved.html
- https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/release-audit.html

Final PR merge and Pages-run evidence will be appended to COORDINATION.md after confirmation.
