# TWC day-4 coverage audit — session `arena/4e8d38ae`

**Disposition: needs review.** This is a snapshot audit, not a live update or a new betting recommendation. I did not fetch Hotspawn, HLTV, or bookmaker sites in this session; the environment’s permitted outbound hosts do not include them. Values below are transcribed from the repository’s timestamped evidence files and linked to their original source pages for manual review. No missing result or price is inferred.

## Executive finding

The latest primary-board evidence in this checkout is **2026-10-16 13:23:10 UTC**, with a generated summary at 13:23:27 UTC. It reports 30 open matches, 30 picks, zero unresolved matches, and a next lock at 13:54 UTC on 16 October. Its TWC rows are the **day-3 deciders** Aurora–9z and BetBoom–Legacy. The stored TWC day-3 result fields are empty, and the primary pick inventory contains no day-4 TWC semifinal rows. The archived schedule describes the 17 October semifinal opponents conditionally on the decider winners, but this capture does not contain verified semifinal fixtures, prices, or picks. Therefore this repository snapshot cannot substantiate day-4 TWC picks; its day-3 picks must not be presented as day-4 picks.

The automated four-hour refresh can capture newly listed Hotspawn matches when they appear, but it cannot backfill TWC results into the retrospective research file. A current refresh and independently sourced results/fixture audit are required before publishing day-4 TWC analysis.

## Day 1 — the 9z upset, without hindsight inflation

| Match | Archived pre-match market | Archived crowd ownership | Reported result | Evidence |
|---|---:|---:|---|---|
| 9z vs Aurora (Hotspawn `1080176`) | Pinnacle decimal odds 3.55 / 1.307; the research file describes the resulting 9z chance as about 26.9% | 5% / 95% (captured hours before lock; not a probability) | 9z won 2–0 (Inferno 13–11, Nuke 13–1) | [HLTV match #2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) · [HLTV report](https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026) · [Pinnacle archived market URL](https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111785/markets/related/straight) · [Valve standings snapshot](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |

**Takeaway:** 9z’s win is a real upset and demonstrates a non-zero underdog path; it does not by itself establish that the pre-match market was wrong. The board correctly treats Hotspawn’s 5%/95% as ownership, not win chance. A leaderboard contrarian play is only defensible when a current outside line supports a meaningful upset probability and the ownership sample is adequate. The archived four-match day-1 sample is too small to validate a general strategy.

Aurora’s roster news is sourced to [HLTV’s July rebuild announcement](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan). It predates this October event by months, so it is context—not proof of acute onboarding, fatigue, rest, or an unpriced edge. No numerical roster adjustment is justified by the archived evidence.

## Day 2 — results and grading limits

The repository’s audited day-2 file records four series on 15 October. Three have frozen pre-lock picks; one has no archived pick and is expressly not graded.

| Match | Reported winner | Frozen board pick | Grade | Source |
|---|---|---|---|---|
| Aurora vs Ninjas in Pyjamas (`1080201`) | Aurora, 2–0 | **No archived pick** | Not graded; no reconstruction | [HLTV match #2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) · [Hotspawn official lobby](https://play.hotspawn.com/lobby) |
| 9z vs Falcons (`1080202`) | Falcons, 2–1 | Falcons | Correct | [HLTV match #2399409](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) · [HLTV report](https://www.hltv.org/news/45728/falcons-secure-playoff-berth-at-twc-2026) |
| PARIVISION vs BetBoom (`1080203`) | BetBoom, 2–1 | PARIVISION | Incorrect | [HLTV match #2399410](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) · [HLTV report](https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc) |
| Legacy vs FURIA (`1080204`) | FURIA, 2–1 | FURIA | Correct | [HLTV match #2399411](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026) · [HLTV report](https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy) |

The three archived picks went **2–1**. That is descriptive only; one unarchived match prevents a four-for-four grading, and three observations do not establish predictive skill. The archival record is `hotspawn/research/day2_twc2026.json`; its provenance says the missing Aurora–NiP pick must not be backfilled.

## Day 3 and the day-4 evidence gap

| Day-3 decider in the 13:23Z pick snapshot | Frozen snapshot pick | Probability in the pick CSV | Day-3 outcome in the retrospective evidence | Source |
|---|---|---:|---|---|
| Aurora vs 9z (`1080205`) | Aurora | 67.4% / 32.6% | **Not recorded** | [HLTV match #2399412](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) · [Pinnacle API market](https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111785/markets/related/straight) · [Polymarket market](https://polymarket.com/event/cs2-aur1-9z-2026-10-16) |
| BetBoom vs Legacy (`1081775`) | Legacy | 38.6% / 61.4% (team order BetBoom / Legacy) | **Not recorded** | [HLTV match #2399413](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026) · [Polymarket market](https://polymarket.com/event/cs2-lgc-bb3-2026-10-16) · [EGamersWorld event relay](https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H) |

These are dated pre-lock prices, not current prices. In the primary CSV, the Pinnacle reads are both timestamped 2026-10-16 13:23:15Z (Aurora/9z 1.414938/2.93; BetBoom/Legacy 2.47/1.555556); the margin-removed probabilities shown above come from those prices. The row flags are `KICKOFF_GAP` for Aurora–9z and `ALIAS` for BetBoom–Legacy; consult the per-row notes before using them. The day-3 audit (`hotspawn/research/day3_twc2026.json`, reviewed 2026-10-16 04:45Z) contains no result for either match. Its cited [HLTV event schedule](https://www.hltv.org/events/8932/matches) describes 17 October semifinals as FURIA vs the Aurora/9z winner and Falcons vs the BetBoom/Legacy winner; that is a conditional schedule statement, not confirmation of final opponents. The 13:23Z primary inventory contains only the two day-3 TWC rows and no day-4 TWC row.

### Required next verification before day-4 recommendations

1. Refresh all Hotspawn CS2 surfaces and retain the raw timestamped response; confirm any semifinal cards/IDs and lock times against the live [Hotspawn lobby](https://play.hotspawn.com/lobby).
2. Verify the actual day-3 results and day-4 participants from the [HLTV event results/schedule](https://www.hltv.org/events/8932/thunderpick-world-championship-2026) and linked match pages.
3. Read new external prices (Pinnacle first, then the documented research ladder); never reuse the 16 October pre-lock line as a day-4 price. Use the Valve line only under the board’s roster/format safeguards.
4. Publish a day-4 result review only with source-linked rows and the source read times. Until then, preserve blank outcome fields and label the day-4 analysis unavailable, not unresolved by guesswork.

## Additional release-gate finding — existing broken anchors

After rebasing this audit branch on the current `main`, the repository's independent `scripts/audit_91e444dd.py` reports **8 missing fragments** in `hotspawn/release-audit.html`: `picks.html#m1079586`, `#m1080285`, `#m1080286`, `#m1079167`, `#m1079630`, `#m1081712`, `#m1080287`, and `#m1081498`. These links point to closed cards that are no longer rendered on the open-picks page. Six IDs (`1080286`, `1079167`, `1079630`, `1081712`, `1080287`, `1081498`) are present in the current all-fixtures inventory and can use `all.html#f<ID>`; IDs `1079586` and `1080285` do not exist in the current inventory and need an archived-source link or removal from that historical table. This is a pre-existing shared-page finding, not caused by this audit PR. The full independent audit therefore fails its link gate until the integration owner fixes these links.

A second independent release gate also fails in the full repository test suite: `python -m unittest discover -s tests -v` ran 427 tests and had one error in `livelines/tests.py::TestBoardInvariants::test_rebuild_is_deterministic_with_a_pinned_clock`. The rebuild raised `KeyError: 'logloss_alternative'` at `livelines/build.py:488`. Running `python3 livelines/build.py` directly reproduces it. This is outside this PR's file scope; the owning session should make the calibration builder tolerate a missing alternative or emit a documented fallback, then rerun the full suite. No generated test outputs were retained.

## Verification performed in this session

- Compared `hotspawn/data/summary.json`, `hotspawn/data/capture.json`, `hotspawn/data/picks.csv`, `hotspawn/research/day2_twc2026.json`, and `hotspawn/research/day3_twc2026.json` locally; confirmed the snapshot timestamp, two TWC pick IDs, the missing day-3 result fields, and conditional day-4 schedule text.
- `python3 hotspawn/verify.py`: **100/100 source fixtures, 0 errors**.
- `python3 hotspawn/tests.py`: **75 tests, all passed**.
- `python3 tests/audit_site.py`: **passed**, zero broken internal links in root and `docs/`, 26 data records passed.
- `python3 hotspawn/mobile_check.py`: **browser unavailable**. No real-browser mobile-layout claim is made by this session; a previous mobile-check artifact may exist, but it was not regenerated here.
- No live network requests to Hotspawn, HLTV, Pinnacle, Polymarket, or other esportsbooks were made. Consequently this report does not certify that the snapshot remains current.

## Integration request / flagged limitation

The primary executive summary and TWC page are integration-owned. Request the integration owner to surface a prominent, snapshot-driven notice: **“Day-3 deciders are the latest TWC evidence in this capture; day-3 results/day-4 fixtures have not been verified here. Check the read time and live board.”** Keep it linked to this audit or the existing Flagged for Review page. Do not edit the shared landing, picks, or TWC pages from this session.
