# Final source and landing-integration audit — 262b4d3b

**Review date:** 2026-10-14 UTC

**Evidence reads:** fixture/market and LFO review approximately 08:39–08:41Z; ten exact HLTV format pages for the current VRS estimates were re-read around 09:11Z. Snapshot counts were recomputed at 09:11:55Z. Individual source times are noted separately.

**Scope:** root landing, current-picks renderer, its live fixture inputs, and the unresolved FORZE Reload–LFO 10 row. Source/data boards owned by other sessions were read-only. This report is not betting advice and does not claim that an estimate is a calibrated win frequency.

## Release disposition

The root page now has one primary route to `current-picks.html`, a direct unresolved/limitations route, a directly labelled Flagged for Review link, and a collapsed archive for the older board links. The page is designed to fail closed when the snapshot, market, exact fixture join, VRS inputs, or series format is not verified. Local scoped tests and the repository local-link audit pass. **Do not treat this report as a public-deployment confirmation until the PR checks and Pages verification below are completed.**

## Fixture spine and freshness

- The sole fixture inventory is `live/data/slate.csv`, validated against `live/data/snapshot_meta.json`. The captured file has 88 CS2 rows and `generated_utc=2026-10-14T07:58:35Z`; the capture metadata recorded 26 pickable rows at that instant. No crowd percentage field is read by the landing code; it does not request `live/data/snapshot.json`.
- Fixture counts, team names, kickoff/lock times, and current-row inventory are never taken from `exec/`. That build was generated at `2026-10-14T08:03:41Z`, but its fixture spine is older. It is used only to corroborate best-of format after an exact fixture ID, team-order, kickoff, and lock-time join, and an HLTV match URL whose slug identifies both exact fixture names. At approximately 09:11Z, the ten HLTV match pages behind the currently rendered VRS estimates were manually re-read: participants and displayed BO labels match the cross-board rows listed below. The renderer validates the URL and exact join but does not fetch or parse HLTV pages itself.
- At the fixed browser-time check `2026-10-14T08:39:00Z`, the renderer filtered out the already locked 9z–Aurora match and reported 25 rows with a captured future lock: 8 validated market lines, 10 transparent VRS series estimates, and 7 unresolved rows. The 7 unresolved rows are `1079624`, `1080279`, `1080281`, `1080283`, `1080286`, `1080288`, and `1080289`. All seven display no pick and no probability pair. These counts are a reproducible check against the committed files at that fixed time, not a claim about a later Hotspawn state.
- The live-source refresh workflow, `.github/workflows/live-459ff624.yml`, schedules an hourly public-source capture and rebuild (GitHub scheduling remains best-effort). The page re-evaluates lock times every minute; it does not claim to make an hourly committed capture instantaneous. Other project refresh workflows also run within the requested 4–8-hour window.

## Probability and source rules in the current view

1. **Pinnacle:** the collector reads Pinnacle's public guest API and accepts open, non-alternate `moneyline`, `period=0` (match-winner) markets. The builder joins on the normalized team pair and requires the event start within 120 minutes of the Hotspawn fixture, then de-vigs the decimal odds. The public URL available in the capture is a generic Pinnacle matchups page, not a per-match deep link; the existing `FL-12` flag is retained and linked for review on each affected row. This is a direct-source capture, but the missing deep link is an explicit limitation.
2. **EGamersWorld secondary aggregate:** when the live CSV carries one, the page accepts only a fresh two-sided decimal pair with a per-match Counter-Strike page; it labels the line as an aggregate and de-vigs it. The known 1.80 / 1.80 placeholder is explicitly refused. No EGamersWorld line is in the current 07:58 snapshot.
3. **Polymarket:** this is not a bookmaker and its price is never de-vigged. The renderer admits only fixture `1079438` at its exact `2026-10-14T07:58:31Z` observation (`84.5% / 15.5%`) against the `cs2-ast10-sashi-2026-10-14` event. That event page was re-read around 08:39Z and distinguishes Series Lines → Moneyline from map winner contracts; only the series-moneyline scope is allowed. The CSV's generic event URL alone does not identify a later contract, so any different timestamp or probability pair fails closed until re-reviewed.
4. **Own VRS series estimate:** for a row without an accepted live market, the client recomputes a per-map probability from the exact two official Valve points, `p=1/(1+10^(-(R_a-R_b)/400))`. It then applies the independent-map BO1/BO3/BO5 series transform: BO1 `p`; BO3 `p²(3−2p)`; BO5 `p³(10−15p+6p²)`. The scale, independent-map assumption, and lack of calibration are printed next to each estimate. The code first checks that its per-map calculation reproduces the live CSV's stored VRS line, that the Valve file is official and no more than 14 days old, and that a fresh exact-row HLTV best-of record exists. The published `exec` own probability is not copied into this page.
5. A source with a generic event page, an unverified Polymarket scope, a stale read, a mismatched favorite, a missing VRS side, or an HLTV slug whose team spelling needs an unverified alias does not create a probability. The rejected source or candidate is linked for manual review. Market/model disagreements of at least 15 percentage points are marked for review, without replacing the market pick.

## HLTV best-of cross-check for current model rows

The following ten exact fixture pages were fetched again at approximately 09:11Z. The visible HLTV page content identified the listed teams and displayed the recorded best-of. This check validates series format only; **no HLTV community-pick/crowd percentages were used as probabilities**. The site's renderer still uses only the linked, exact-row `exec` format record and checks the URL/join locally; it does not scrape HLTV at runtime.

| Fixture ID | Exact fixture | HLTV page | Displayed format |
|---|---|---|---|
| `1079622` | ex-RUSTEC vs mellren | [HLTV match](https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11) | BO3 |
| `1081112` | Banda Chuya vs 6666 | [HLTV match](https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier) | BO3 |
| `1079623` | G2 Ares vs The Last Resort | [HLTV match](https://www.hltv.org/matches/2399300/g2-ares-vs-the-last-resort-cct-2026-europe-series-11) | BO3 |
| `1080280` | ENCE vs BOJONG | [HLTV match](https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2) | BO1 |
| `1080282` | EAC vs BOJONG | [HLTV match](https://www.hltv.org/matches/2399421/eac-vs-bojong-elisa-breakout-series-2) | BO1 |
| `1080284` | EAC vs ENCE | [HLTV match](https://www.hltv.org/matches/2399423/eac-vs-ence-elisa-breakout-series-2) | BO1 |
| `1080285` | Voca vs Phantom | [HLTV match](https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2) | BO1 |
| `1080287` | Voca vs HAVU | [HLTV match](https://www.hltv.org/matches/2399426/voca-vs-havu-elisa-breakout-series-2) | BO1 |
| `1081120` | mellren vs Privateer | [HLTV match](https://www.hltv.org/matches/2399471/mellren-vs-privateer-cct-2026-europe-series-12-closed-qualifier) | BO3 |
| `1080290` | Phantom vs HAVU | [HLTV match](https://www.hltv.org/matches/2399429/phantom-vs-havu-elisa-breakout-series-2) | BO1 |

## FORZE Reload–LFO 10 (Hotspawn fixture 1079624)

**Status: unresolved; no pick; both probabilities blank.**

- The live row has no outside price or published own line. It has a FORZE Reload Valve value but no LFO 10 value. HLTV's match page confirms the listed fixture and BO3 format; HLTV's LFO 10 team page shows no active players/current rank. A one-sided rating is not converted into a two-sided pick.
- The older `livelines/` value `84.6% / 15.4%` was captured at 04:50Z against a generic multi-market Polymarket event link. The contract scope associated with that quote settles on **Map 1**, not the BO3 series; it is explicitly withdrawn as a series probability here.
- A separate Polymarket Series Moneyline was visible at about 77–78¢ / 24–25¢ around 08:40Z for **FORZE Reload vs Sökerorg** and its rules resolve on the match winner. The opponent name does not match Hotspawn/HLTV's “LFO 10”. bo3.gg and EGamersWorld roster/schedule pages provide third-party alias clues, but no authoritative identity link was found. The price is not assigned to fixture 1079624.
- EGamersWorld's FORZE listing showed the opponent name absent and 1.80 / 1.80 placeholders. That is not a usable two-sided market or an identity proof.

Manual review links are embedded in the current page and row card: [Hotspawn fixture](https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624), [HLTV BO3 match](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11), [HLTV LFO 10 profile](https://www.hltv.org/team/14084/lfo-10), [pinned official Valve standings](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md), [EGamersWorld listing](https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3), [Polymarket event](https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14), and [third-party Sökerorg roster](https://bo3.gg/teams/sokerorg).

## Other withheld rows

- `1080279`, `1080281`, and `1080283` name WROTBERRY on Hotspawn but their linked HLTV match slugs name WBT. The other integration contains a documented alias mapping, but this renderer does not treat that mapping as authoritative team-identity proof; the estimate remains blank.
- `1080286`, `1080288`, and `1080289` name RoundsGG on Hotspawn while the best-of candidate URL names “Rounds”. No exact alias proof is incorporated into this integration, so each remains blank pending source review.
- These candidates are linked as unverified HLTV references in the unresolved list. Their blank values are intentional, not missing rendering.

## Automation and provenance

`live/collect.py` and `live/build.py` were inspected read-only. The collector describes public Hotspawn fixture reads, Pinnacle public guest responses, EGamersWorld/HLTV, and official Valve standings; a failed source leaves fields blank. The live workflow is scheduled hourly, the separate `livelines` workflow every four hours, and the current page fetches only the committed live CSV, its metadata, and the optional exact-join format cross-check. No user-triggered refresh is required. Scheduled Actions are best-effort, so the UI exposes capture time and suppresses stale evidence.

## Verification results

- Dynamic evaluation at `2026-10-14T09:25:06Z` against the committed live CSV/metadata and optional exact-join format evidence: 88 captured fixtures, 25 still active, 8 market prices, 10 VRS estimates, 7 unresolved, 0 unknown lock times, and 63 locked/past. The unresolved IDs remain `1079624`, `1080279`, `1080281`, `1080283`, `1080286`, `1080288`, and `1080289`.
- Reconciled the PR branch against the then-current `origin/main` (`47dbdc4`) after GitHub reported a root-page conflict. The current-picks page is now the single root primary CTA; the executive board survives only as a collapsed comparison snapshot. The root preserves the full 137-destination union of the latest main landing (120 unique hrefs) and the pre-rebase session landing (119 unique hrefs).
- `node --check js/262b4d3b-picks.js`, `node tests/262b4d3b-picks.cjs`, and `node --check js/landing.js`: passed; the Node suite checks fresh inventory, strict lock filtering, scoped prices, exact format/rating joins, VRS math, unresolved blanks and fail-closed freshness.
- `python -m unittest discover -s tests -p 'test_262b4d3b_landing.py' -v`: 4 tests passed.
- `python -m unittest discover -s tests -p 'test_landing_43c32386.py' -v`: 4 root-landing acceptance tests passed. `python -m unittest discover -s tests -p 'test_6f9eab3b.py' -v`: 2 additional landing checks passed.
- `python scripts/audit_91e444dd.py --output /tmp/landing-links-final-pr.json`: 240 HTML pages, 5,720 local links, and 0 local-link errors. Its unrelated structural audit of `today/data/current.json` reports 49 review-only findings (29 rows without an external market and 20 model-use caveats); no finding is a link error, and those stored-board findings were not modified by this integration.
- Root href-union check passed: all 137 distinct destinations from latest `origin/main` and the pre-rebase landing remain present. `git diff origin/main...HEAD --check` passed.
- The root contract regression `test_landing_has_one_executive_summary_and_no_leaked_comment_text` passes after commit `c7dee46` restored the visible “Executive summary” label. The session landing suites pass 4/4 + 4/4 + 2/2; Node evidence and both JavaScript syntax checks pass.
- To diagnose the Actions full-suite failures without running collector side effects in the worktree, `python -m unittest discover -s tests -v` was run in isolated `git archive` copies of `origin/main` and PR HEAD. Main ran 319 tests and PR HEAD ran 323; **both had exactly the same two failures** in `test_228bb5bc.CommittedBoard`: `test_every_open_fixture_has_a_pick` and `test_team_names_and_ids_match_the_feed` (the test fixture IDs `1079621`, `1080176`, and `1081111` are absent from that board's committed feed). The first PR-head comparison also exposed the missing root “Executive summary” text; that integration-specific failure is fixed, and the latest PR archive has no additional full-suite failures. No other board/data files were changed.
- The prior remote run on `cab9c61` failed at the two full `unittest discover` steps; the root-label fix is on local HEAD and awaits its remote rerun. Do not merge or claim deployment while required checks are red.
- Public Pages release verification: **pending**.

## Known limits and no-go conditions

- VRS points are ratings, not observed win frequencies; a 400-point mapping and independent-map transform are project assumptions. The estimate should not be interpreted as calibrated certainty or betting advice.
- The source workflow refreshes hourly best-effort, while the UI is a committed static-data reader. A lock filter cannot recover a fixture added after the last capture.
- The generic Pinnacle URL is not a per-match receipt (`FL-12`); use the capture time and Flagged for Review source notes as part of manual review.
- The current LFO 10 alias/series-market question remains unresolved. Do not restore either Polymarket quote to the series row without an authoritative identity and exact market-scope link.
- **Do not merge a failing site or report a Pages release as confirmed unless the scoped tests, link audit, required PR checks, and deployed page checks succeed.**
