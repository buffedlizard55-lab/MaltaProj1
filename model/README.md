# O-01: our own lines for every Hotspawn CS2 Pick'em fixture

Session `arena/91eff436` · scope `model/**` and `.github/workflows/model-91eff436.yml` · page: `model/index.html`
(published at `https://buffedlizard55-lab.github.io/MaltaProj1/model/` once merged).

For **every** CS2 fixture in the Hotspawn Pick'em lobby, we originate a win probability, fair decimal odds, and a pick.
The inputs are official rating data, and Hotspawn crowd picks are never used. A value that can't be tied to an
official source without guessing is left blank and flagged.

## Pipeline

| Step | Script | Output |
|---|---|---|
| 1. Fetch official inputs (GitHub Actions; the sandbox has no general internet access) | `fetch.py` | `input/hotspawn_cs2_fixtures.json`, `input/vrs/standings_global_*.md` + `meta.json`, `input/hltv_ranking.json`, `input/fetch_log.json` |
| 2. Calibrate the curve on Valve's published history | `calibrate.py` | `input/vrs/calibration.json` |
| 3. Resolve teams, compute lines, flags, page | `build.py` | `data/lines.csv`, `data/lines.json`, `data/teams.csv`, `data/flags.csv`, `data/digest.txt`, `index.html` |
| 4. Tests | `test_model.py` | 11 tests (below) |

Reproduce: `python3 model/fetch.py && VRS_REPO_DIR=<clone of ValveSoftware/counter-strike_regional_standings> python3 model/calibrate.py && python3 model/build.py && VRS_REPO_DIR=… python3 model/test_model.py -v`

Automation: `.github/workflows/model-91eff436.yml` runs every 3 hours from `main` (cron `17 */3 * * *`), on any push to
`main` or this session's branch that changes the model code or the workflow, and by manual dispatch. It commits
`model/**` only, and only when the content digest changes; timestamp-only refreshes are discarded. After a data commit
to `main` it also asks GitHub Pages to rebuild (best effort). To stop it, disable the workflow in the Actions tab.

## Sources (all official; each row links its exact source)

1. **Fixtures**: <https://play.hotspawn.com/cs2-pickems> and <https://play.hotspawn.com/lobby>. Both pages are Angular SSR,
   and `<script id="ng-state">` (TransferState) carries the full fixture list: id, teams, competition, tier,
   `scheduled_start_time` in epoch ms, `lock_offset_sec`. The two pages are rendered or cached at different moments, so
   we take the union by id. Only identity fields are kept. `participants*_picked_percent` and `total_picks` are dropped
   on ingest and never written to disk.
2. **Ratings**: Valve Regional Standings, <https://github.com/ValveSoftware/counter-strike_regional_standings>. We use
   the newest `live/<year>/standings_global_<date>.md` at the HEAD commit and record the commit SHA and file SHA-256.
   Each team row links to its exact line (`?plain=1#L<n>`) and to Valve's per-team details page. A standings "Points"
   value is the roster's Final Rank Value, as shown in the details page.
3. **Roster check**: HLTV World Ranking, <https://www.hltv.org/ranking/teams/2026/october/12> on this run. We use the
   rank, points and listed players. The page is fetched with an honest User-Agent and no bot evasion. On failure, the
   previous snapshot is kept and flagged.
4. **Market reference (read-only)**: `lines/analysis.csv`, published by session 79a1c6c8 (task C-02). We recompute
   no-vig from the raw odds. These prices are shown for comparison only and are **never** used in our line or pick.

## Model

* Valve's own expected-win function (`model/fit.js` → `Fit.priorWinExpectation`, rd = 75, with `model/glicko.js`)
  reduces exactly to `P(A) = 1 / (1 + 10^(−g·(pts_A − pts_B)/400))`, where `g = 1/√(1 + 3q²·75²/π²) = 0.97282` and
  `q = ln10/400`. `test_model.py` checks this closed form against Valve's actual JavaScript (run through Node) to 12
  decimal places.
* **Calibration (what makes the line ours).** Valve's README notes the raw curve's slope is too steep. `calibrate.py`
  applies Valve's own evaluation recipe to the monthly snapshots. Every match in a snapshot's per-team details tables
  is rated with the **previous** snapshot's points, so there is no look-ahead. Both sides are identified by the roster
  that played (≥ 3 shared players, Valve `team.js`). The slope k is fitted by maximum likelihood. Run of 2026-10-13:
  6,765 matches (2025-12-01 → 2026-10-05), **k = 0.4568**. On the held-out windows (2026-08-03 → 2026-10-05,
  n = 1,709), log loss improves from 0.6619 (raw) to 0.6435 and Brier from 0.2294 to 0.2258. The raw curve's favourites
  rated about 94% actually won about 81%. The calibrated slope is adopted only if it beats the raw curve out of sample.
* **Team resolution** (no fuzzy matching):
  * An exact, case-insensitive VRS name is a candidate.
  * If HLTV lists the team, its players must share ≥ 3 with the VRS roster.
  * Exactly one qualifying VRS row is used. Several qualifying rows → AMBIGUOUS. None → NOT IN VRS or ROSTER MISMATCH.
    Each of these leaves the line blank and raises a flag.
  * A team whose HLTV roster matches a VRS roster listed under another name (e.g. Envy = VRS "3DMAX", 5/5 players)
    gets a line and a needs-review flag.
* Pick = our line's favourite. Confidence: strong ≥ 75%, lean 60–75%, toss-up < 60%. Fair odds = 1/P.

## Limitations (all also on the page's Flagged list)

* VRS is published monthly (2026-10-05 on this run), so later results are not reflected.
* Hotspawn publishes no series format (`best_of` is null), so no BO1/BO3 adjustment is applied.
* 59 of the 86 fixtures carry scheduled dates months before the current pick'em week but are still `status: scheduled`
  (stale listings). Their lines are informational only.
* Teams absent from VRS (lower-tier and academy sides) and ambiguous duplicates get no line. They are listed per team
  with their affected fixtures.
* Market reference rows carry capture times later than the file's own commit (IR-91-09). They are treated as unverified.

Not affiliated with Hotspawn, Valve or HLTV. Analysis only, not betting advice.
