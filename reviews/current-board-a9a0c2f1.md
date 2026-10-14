# Current-board review · session a9a0c2f1

Date: 2026-10-14 UTC. Scope: `slate/**`, its workflow, root landing and README. Other session data and code remain read-only. This report is **not** a claim that every historical dashboard or every external value in the repository was freshly verified.

## Verification levels

1. **Source observation:** collection from a public official page/response, identified by URL, UTC fetch time, HTTP status, byte length and SHA-256 in [`slate/data/provenance.json`](../slate/data/provenance.json). A refusal does not verify a value.
2. **Calculated market estimate:** re-compute both inverse-odds probabilities and the overround from a qualifying primary bookmaker quote. These are market-implied estimates, not official win probabilities or promises of outcomes.
3. **Provisional model:** source-linked rating inputs transformed with explicit project assumptions. Neither Valve nor HLTV publishes these forecast percentages; official input data does not verify model calibration.
4. **Stored cross-check:** compare other sessions' published rows. This checks consistency, not live source truth. Their files are not overwritten or endorsed by this review.

The workspace permits network access to GitHub/package registries, not the match/odds hosts. Fresh capture therefore runs on GitHub Actions. No login, private betting account, challenge solver or user input is used. Actual collection failures are logged.

## Line-by-line review findings and corrections

| Finding | Evidence / source | Resolution and remaining limit |
|---|---|---|
| Fuzzy identities could assign an external line to the wrong fixture | [Original collector](https://github.com/buffedlizard55-lab/MaltaProj1/blob/9d841fdee9a4fbb0b68b3a3e682b23b7bde1c7db/slate/collect.py), `pinnacle_guest`, `session_readings`, carried-reading matching | Exact normalised/evidence-linked names only; known kickoff within 15 minutes required; participant order explicitly flipped. Similar names and missing times fail closed. |
| Six-hour kickoff tolerance could confuse repeated team pairings | Same original collector | Tightened to 15 minutes. Missing kickoff cannot qualify. |
| Historic fallback data could drive current picks; one carried read timestamp was hard-coded | Same original collector, `carried_readings` | Historical/session fallback disabled. Original evidence files preserved, not relabelled as fresh. |
| Secondary aggregated odds were not primary bookmaker verification | [EGamersWorld](https://egamersworld.com/counterstrike/matches), [Pinnacle](https://www.pinnacle.com/en/esports/games/cs2/matchups/) | Secondary reports remain a research table and are explicitly unverified against the named bookmaker. Only fresh primary Pinnacle observations can drive headline market estimates. |
| Unknown format returned a map value in a series column while text said BO3 assumed | Original `series_from_map`, `own_line`, builder | Unknown series format leaves series values and model-only match pick blank. No inferred BO3. Explicit Pinnacle best-of metadata or HLTV/Hotspawn format can support BO1/BO3/BO5. |
| Published market-preference text disagreed with an arbitrary market/model average | Original merged analysis block and builder | Pick follows primary market without blending; model divergence stays visible. Ties have no pick. |
| Rating transforms could appear to be official probabilities | [Official HLTV ranking](https://www.hltv.org/ranking/teams), [official Valve repository](https://github.com/ValveSoftware/counter-strike_regional_standings) | Scale 400, equal-weight blending and map independence are project assumptions, explicitly uncalibrated. No claim that this is Valve's official forecast formula. Alias-derived ratings excluded pending review. |
| Shared organisation names could leak CS2 ratings into another esport | Original rating resolution/own-line code | Rating-model calculations restricted to CS2. Other titles retained in the inventory with unsupported forecasts blank. |
| A missing schedule could default to open | Original `live_status` | Missing lock/start is unverified, never pickable. |
| HLTV parser could borrow another nearby fixture's fields or infer a team from a URL slug | Original `parse_hltv_matches` | Stop at the next fixture link; require actual team-name markup. Missing data is not inferred from slugs. |
| Failed capture/build/tests could still publish changed data | [Original workflow](https://github.com/buffedlizard55-lab/MaltaProj1/blob/9d841fdee9a4fbb0b68b3a3e682b23b7bde1c7db/.github/workflows/slate-180a42a0.yml) | Commit only after successful collection, build, tests, JS syntax and browser checks. Missing any required Hotspawn page fails collection. Failed-run evidence is an artifact, not a replacement snapshot. Rebase errors are not suppressed. |
| Successful scheduled commits may not independently trigger Pages | [GitHub Actions token documentation](https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow), [Pages builds API](https://docs.github.com/en/rest/pages/pages#create-a-github-pages-build) | Successful main refresh explicitly requests a Pages build through the official API; API failure remains visible as a failed job. Documentation links are for manual review; they were not fetched from this restricted workspace. |
| Static picks could remain displayed after lock or failed refresh | Current `slate/dashboard.js` | Browser-time lock, quote age and snapshot age checks suppress active picks. Unknown fetch/time state explicitly marks data unavailable. Six-hour expiry, one-minute browser re-check, hourly best-effort collection. |
| Root landing was crowded; inherited card markup nested links | Root HTML inspection | Current CS2 dashboard promoted; prior boards collapsed for audit. Every previous link destination preserved, nested anchors corrected. Concurrent `open-slate/` owner request integrated without editing its files. |
| Separate legacy model refresh is failing | [Official run 38489574648](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38489574648) | Official jobs API confirms its test step failed. Published on current Flagged for Review. That owner's model/workflow remains unchanged; current board does not depend on it. |

## Fresh source observations

[First successful maintenance capture 38497270864](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497270864) generated a snapshot at **2026-10-14T01:49:17Z**:

- Required Hotspawn public pages each returned HTTP 200 and parseable payloads.
- 387 union fixtures: 89 CS2 and 298 LoL; 28 CS2 rows had future lock times.
- **5 CS2 primary-bookmaker quotes/picks** qualified (6 across both titles in that intermediate run); 27 CS2 rating-map estimates, 5 sourced-format series estimates. Intermediate outputs are superseded by the final CS2-only run.
- HLTV current ranking: HTTP 200, 245 teams, page date text “October 12th, 2026”. HLTV upcoming listing: HTTP 403, no match-row verification claimed.
- Hotspawn header counts, rendered cards and payload sizes do not agree. They are recorded separately, not treated as interchangeable proof of complete authenticated coverage.

The final capture/run and deployment evidence are recorded in the session's release section of [COORDINATION.md](../COORDINATION.md). Counts are snapshot-dependent and are never hard-coded into the landing page.

## Gates and scope of tests

- 108 repository unit tests passed after concurrent PR #71 integration.
- Current-board tests cover de-vig math, bounds/complements, market preference, exact identity/orientation, required kickoff, stale/future/malformed quotes, unknown formats, cross-sport separation, missing schedules and per-row primary provenance.
- Whole-repository local-link audit: 126 HTML pages, zero broken local links at integration. This does **not** establish that external websites will serve those URLs.
- Browser gate: real stored data at 390px and 1280px, no document overflow, filter behavior, snapshot loading, JavaScript exceptions and failed-fetch suppression. Render tests are not external-value verification.

## Remaining limitations / manual review

- A parsed public payload is not guaranteed to expose every authenticated Hotspawn card; source refusals, caching and header discrepancies remain review findings.
- A complete probability/pick for every fixture is not supportable when primary prices, ratings or format are unavailable. Those cells stay blank rather than inventing odds, assigning 50/50, or guessing BO3.
- Model calibration, roster changes and alias evidence require further independent review. Research map estimates must not be mistaken for confirmed match-win probabilities.
- Other preserved dashboards can contain older observations and different model assumptions. The root's collapsed archive is not a fresh endorsement.
- GitHub's hourly schedules are best-effort, not an uptime guarantee. Source read time, snapshot generation time, workflow completion and Pages deployment are separate events.

All current unresolved per-fixture gaps and standing caveats are published on [Flagged for Review](../slate/flagged.html), with official fixture/rating/bookmaker links for manual checking.
