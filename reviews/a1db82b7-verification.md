# Own-line model repair + automation reliability — verification record (session `arena/a1db82b7`)

Branch: `arena/a1db82b7-maltaproj1` · Scope: `model/**`, `.github/workflows/model-91eff436.yml` (handoff from the
stale owner `arena/91eff436`), this record · Written 2026-10-14 01:5x UTC · Nothing here is inferred: every
number below is either re-read from an official file or quoted from an official API/log a reader can open.

**Network limit, stated plainly.** The agent sandbox can reach only `github.com`, `api.github.com`,
`codeload.github.com`, `registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`. It **cannot** reach
`play.hotspawn.com`, `hltv.org`, `pinnacle.com` or `egamersworld.com`. Every live read was therefore performed by
GitHub Actions runners, and the evidence for those reads is the runner's own record committed in this repository
(`model/input/fetch_log.json`: URL, HTTP status, byte count, SHA-256, fetch time). Where this record says
"verified", it means one of two things, and it says which: **(a)** re-read from an official file through
`api.github.com` by this session, or **(b)** verified by the CI run that published it, with the run link given.

---

## 1. M-01 — the failing scheduled own-line model is repaired and green

### 1.1 What was broken

| Item | Value |
|---|---|
| Run | [38489574648](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38489574648) — `O-01 own-line model (VRS)`, event `schedule`, branch `main`, 2026-10-14T00:20:08Z |
| Failing step | job `refresh` → **Tests (incl. check against Valve's own fit.js/glicko.js)**; the later "Commit refreshed model/**" step was skipped, so **no refreshed lines were published** |
| Effect on the site | `model/index.html` and `model/data/lines.csv` stayed on the 2026-10-13T18:45Z snapshot while the board kept adding fixtures |

The run log is not downloadable from this sandbox (only the API hosts are reachable), so the failure was
reproduced instead, on this branch, by a job that commits its own evidence:
[38497399182](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497399182) → `diag/04_tests.log`.
It failed identically, and named the assertion:

```
FAIL: test_every_published_value_has_official_source
AssertionError: False is not true : None
```

### 1.2 Root cause (evidence-backed)

1. The board had **added fixtures**: the runner read 89 CS2 fixtures at 2026-10-14T01:45Z where the 2026-10-13
   snapshot had 86 (`diag/01_fetch.log`, and `model/input/fetch_log.json` after the fix).
2. The board's TransferState returns a **`null` permalink** for a fixture it has just added. `fetch.py` wrote
   `str(u)` for every permalink, and `str(None)` is the literal string `"None"`.
3. `build.py` published that string as the row's `hotspawn_url`, and the model's own source test refused it —
   correctly. The gate worked; the data was wrong.

This is the failure mode this repository's rules exist for: the value could not be tied to a real source, so the
run published nothing rather than something unverifiable.

### 1.3 The fix (no check was weakened)

| File | Change |
|---|---|
| `model/fetch.py` | Keep only permalinks that are strings starting with `https://www.hotspawn.com/` or `https://play.hotspawn.com/`. Null, blank and non-Hotspawn values are dropped at ingest and never become a published value. |
| `model/build.py` | Validate the per-match URL before publishing: anything that is not a real Hotspawn URL falls back to the Pick'em page the fixture was actually read from, the row's notes say so in words, and the source cell is labelled "Hotspawn Pick'em page" instead of "Hotspawn fixture". |
| `model/test_model.py` | Two regression tests: `test_every_row_links_an_official_hotspawn_url` (every published row carries a real official URL, never `None`/`null`, and a row without a permalink says so) and `test_permalinks_ingested_are_real_urls` (the ingest never stringifies a null). 16 tests now, up from 14. |

### 1.4 Result — green run with live inputs

| Item | Value |
|---|---|
| Green run | [38497833026](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497833026) — all steps success on this branch, 2026-10-14T01:50Z |
| Published commit it produced | `8553c83` `model(91eff436): refresh inputs + own lines [run 38497833026]` |
| Payload snapshot | 89 CS2 fixtures, fetched **2026-10-14T01:50:15Z** (`model/input/fetch_log.json`) |
| Published rows | 89 → **57 with our own line**, 32 blank + flagged, 28 upcoming / 2 started / 59 stale |
| Rows with a non-Hotspawn source URL | **0** (was the failure) |
| Tests | 16/16 (`python3 model/test_model.py`, 1 skipped locally: the Node comparison against Valve's JavaScript, which runs in CI and passed there) |

**Second defect found and fixed in the same session.** The first re-run
([38497654737](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497654737)) **passed the tests** but
failed in the new summary step I had just added: a heredoc inside a YAML block scalar has its terminator indented,
and POSIX bash will not close a heredoc on an indented terminator, so the step broke and the commit was skipped.
The summary now lives in `model/run_report.py` and the step is `continue-on-error`, so a reporting problem can
never block a verified data commit. This is logged as irregularity **A-1** below because it is exactly the kind
of change that must be exercised by a run before it is trusted.

---

## 2. M-02 — the refresh automation is not as automatic as the pages claim

Every published board in this repository says it refreshes itself on a schedule ("auto-refreshed",
"no manual input"). The official Actions API tells a different story, and this is the most important finding of
this session.

**Scheduled runs in the whole repository: 3.** Push-triggered runs: 142. Pages runs: 77.
(`GET /repos/buffedlizard55-lab/MaltaProj1/actions/runs?event=schedule&per_page=100`, read 2026-10-14T01:52Z.)

| Workflow | Cron declared | Scheduled runs ever | Last scheduled run |
|---|---|---|---|
| `update.yml` (Refresh verified snapshot) | `17,47 * * * *` | 1 | 2026-10-13T23:27:08Z success (the 23:17 slot, 10 min late) |
| `model-91eff436.yml` (this session's scope) | `17 */3 * * *` | 1 | 2026-10-14T00:20:08Z — **failure** (now repaired) |
| `release-assurance-91e444dd.yml` | `9,39 * * * *` | 1 | 2026-10-14T01:51:57Z success |
| `live-459ff624.yml` | `37 * * * *` | 0 | none |
| `refresh-b90700c6.yml` | `23 */3 * * *` | 0 | none |
| `slate-180a42a0.yml` | `41 */3 * * *` | 0 | none |
| `assurance-5515.yml` | `23 6 * * *` | 0 | none |

Between 2026-10-13T23:00Z and 2026-10-14T01:55Z those crons were due to fire about **18 times**; **3** fired
(~17%). Session `arena/08031d30` observed the same class of gap independently before this session started
(its `R-08031d30-02`: the `slate-180a42a0.yml` 00:41Z slot missing), and session `arena/a9a0c2f1` was working the
`slate/**` side of it at the same time. GitHub documents that scheduled triggers can be delayed or dropped under
load and that many scheduled workflows in one repository run in series; whatever the exact cause here, the
published claim of regular unattended refresh is **not supported by the run history** and is flagged for review.

**Mitigation built in this session's scope (`model-91eff436.yml`):**

1. **`workflow_run` trigger** on `Slate capture (180a42a0)`: the own-line model now refreshes whenever the board's
   capture job finishes, instead of waiting for its own cron.
2. **Catch-up dispatch:** after a run, if the board's capture has not run for more than six hours, this workflow
   asks it to run now (`workflow_dispatch`, `continue-on-error`, `actions: write`). This makes one firing job
   re-arm the whole chain. Verified not to loop: the model's commit touches only `model/**`, which is not a
   path the capture job triggers on.
3. **Freshness in the run summary:** `model/run_report.py` prints the input snapshot times, the Valve commit and
   file hash, the calibrated slope and the published counts into the job summary, so each run states what it read.
4. The cron is kept as a third path, but nothing now depends on it alone.

**Integration requests (not edits — those files belong to other scopes):** the six other scheduled workflows
listed above still rely on crons that are being dropped. The board-visible consequence is that `slate/**`,
`live/**`, `today/**` and `refresh/**` can sit stale for hours while their pages say otherwise. Recommended
follow-up for the owner of each: adopt the same `workflow_run` chain and correct the freshness wording on the
pages that claim unattended refresh.

---

## 3. M-03 — line-by-line verification of the repaired model's published values

### 3.1 The official input file is byte-identical to what the model claims

| Check | Result |
|---|---|
| Valve commit `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75` exists, dated 2026-10-05T16:36:11Z, message "Updating Regional Standings for 10/5/2026" | confirmed via `api.github.com/repos/ValveSoftware/counter-strike_regional_standings/commits/<sha>` |
| `live/2026/standings_global_2026_10_05.md` at that commit, 77,872 bytes | [official file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| SHA-256 of those bytes | `df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b` — **equal** to `model/input/vrs/meta.json` |
| Curve source | `model/fit.js` / `model/glicko.js` at the same commit; the closed form the model uses is checked against Valve's own JavaScript to 12 decimals by `test_against_valve_javascript` (ran in CI on run 38497833026) |
| Calibration | `k = 0.4568` fitted on Valve's own monthly history (6,765 matches, no look-ahead); out-of-sample log loss 0.66185 → 0.64351, Brier 0.22936 → 0.22575, adopted only because it beats the raw curve (Valve's raw slope `G = 0.972821`) |

### 3.2 Every published number recomputes exactly (re-run by this session on the merged branch)

| Check | Result |
|---|---|
| Own line `own_p_a = 100/(1+10^(−k·(pts_A−pts_B)/400))`, `k = 0.4568`, points from the official file | **57/57 rows exact** |
| Valve raw-curve column `valve_raw_p_a` with `G = 0.972821` | **57/57 rows exact** |
| Fair decimal odds `1/p`, `1/(1−p)` | **57/57 rows exact** |
| Every VRS deep link (`?plain=1#L<n>`) resolves to that team's standing, points and name in the official file | **114/114 row links** + **89/89 team-table links** |
| Every blank row names a reason and publishes no probability or pick | **32/32** |
| The pick is always the model's own favourite (never the market's) | 57/57 |
| Every row carries an official Hotspawn URL; 64 rows link the Pick'em page because the board publishes no per-match permalink for them, and each says so | 89/89 |

Worked example, so a reader can redo it by hand: fixture `1080176` `9z v Aurora` (kickoff 2026-10-14 08:30 UTC,
lock 08:24 UTC). VRS points 9z **1543**
([line L22 of the official file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L22))
and Aurora **1716**
([line L14](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L14))
→ `p = 1/(1+10^(−0.4568·(1543−1716)/400)) = 0.388193` → the row publishes **9z 38.8 % / Aurora 61.2 %, pick Aurora**.

### 3.3 What this session could **not** verify itself

* **The Hotspawn payload** (fixture identity, times) and the **HLTV ranking page**: not reachable from the
  sandbox. They are recorded per run in `model/input/fetch_log.json` with status, bytes, SHA-256 and fetch time,
  and the fixture set was cross-read by another session at the same time: `arena/08031d30` counted **28 open CS2
  fixtures** (Oct 14: 13, Oct 15: 8, Oct 16: 7) from the live page at ~01:40Z, which matches the 28 `upcoming`
  rows published here. Two independent readings, same count.
* **The market-reference columns** in `model/data/lines.csv` come from another session's file
  (`lines/analysis.csv`, session 79a1c6c8) and are labelled as reference only; they are never an input to the
  line or the pick. Their own capture-time anomaly is already flagged (`IR-91-09`, `IR-91-15`).

---

## 4. Irregularities flagged for review (non-blocking)

| ID | Severity | What | Evidence |
|---|---|---|---|
| **A-1** | fixed | The scheduled own-line model was red on `main`; root cause a `null` permalink turned into the string `"None"`. Fixed with regression tests. | runs [38489574648](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38489574648) → [38497399182](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497399182) → [38497833026](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497833026) |
| **A-2** | needs review | Scheduled triggers are being dropped: 3 scheduled runs ever, ~18 due in the last ~3 h, 3 fired. Pages claiming unattended refresh overstate it. | Actions API `?event=schedule`, per-workflow table in §2 |
| **A-3** | needs review | 32 of 89 published rows (36 %) still have **no line**: those teams have no usable row in Valve's official standings, so no probability is published for them, only a blank and a flag. Nothing is inferred to fill them. | `model/data/flags.csv`, `model/data/lines.csv` |
| **A-4** | info | 64 of 89 rows have **no per-match Hotspawn permalink** in the board's own payload (the board publishes permalinks for the current week's fixtures only). Each such row now links the Pick'em page it was read from and says so in its notes. | `model/input/hotspawn_cs2_fixtures.json` (`permalinks`: 25 of 89) |
| **A-5** | info | The board's header count and its payload disagree: header "68 matches this week" while the CS2 payload holds 89 records and the filter says 89. Pre-existing (flagged earlier as FL-20); unchanged. | `diag/01_fetch.log`, `model/input/fetch_log.json` |
| **A-6** | info | `model/README.md` described only the 3-hourly cron; corrected in this session to the real trigger set. | this branch's diff |
| **A-7** | fixed | Two tables had rows with **no link at all** — the "Picks at a glance" summary (30 rows) and 21 team rows for teams absent from Valve's standings and HLTV's ranking. Every row of all seven tables now carries at least one official link (fixture's own match page when the board publishes a permalink, otherwise the Pick'em page it was read from). Verified on the rebuilt page: 380 data rows, 0 without a link. | `model/index.html` on this branch |
| **A-8** | fixed | The commit gate hashed only the **data**, never the page, so any change in how a value is presented was silently discarded by the scheduled job (A-7 would never have shipped). The digest now also covers the rendered page with timestamps normalised, verified not to reintroduce commit churn. | `model/build.py`, `model/data/digest.txt` |

---

## 5. Sources

* Valve Regional Standings (official): repository <https://github.com/ValveSoftware/counter-strike_regional_standings>,
  commit `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`, file `live/2026/standings_global_2026_10_05.md`,
  model `model/fit.js`, `model/glicko.js`, `model/team.js`.
* Hotspawn Play Pick'em: <https://play.hotspawn.com/cs2-pickems> and <https://play.hotspawn.com/lobby> (read by the
  CI runner; per-read provenance in `model/input/fetch_log.json`).
* HLTV World Ranking: <https://www.hltv.org/ranking/teams/2026/october/12> (display and roster cross-check only).
* GitHub Actions API (runs, workflows, Pages): <https://api.github.com/repos/buffedlizard55-lab/MaltaProj1/actions/runs>,
  `.../actions/workflows`, `.../pages`.
* This session's runs: [38497261693](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497261693) (first
  diagnosis, evidence lost to a dirty tree), [38497399182](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497399182)
  (reproduction, `diag/`), [38497654737](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497654737)
  (tests green, summary step broke), [38497833026](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497833026)
  (green end to end, published `8553c83`).

Reproduce every check in §3 from a clone of this branch:

```bash
python3 model/test_model.py -v                      # 16 tests (Node/Valve-JS check needs VRS_REPO_DIR)
python3 model/run_report.py                         # the same summary the CI run publishes
python3 - <<'PY'                                    # §3.2 recomputation
import csv, math, json, pathlib
rows = list(csv.DictReader(open("model/data/lines.csv")))
vrs = pathlib.Path("model/input/vrs/standings_global_2026_10_05.md").read_text().splitlines()
k = json.loads(pathlib.Path("model/input/vrs/calibration.json").read_text())["k_published"]
pk = lambda a,b: 1/(1+10**(-k*(a-b)/400))
for r in rows:
    if r["line_status"] != "OWN LINE": continue
    assert abs(float(r["own_p_a"]) - round(100*pk(int(r["vrs_a_points"]), int(r["vrs_b_points"])), 1)) < 1e-9
    for s in ("a","b"):
        c = [x.strip() for x in vrs[int(r[f"vrs_{s}_url"].rsplit("#L",1)[1])-1].split("|")]
        assert (c[1], c[2], c[3]) == (r[f"vrs_{s}_standing"], r[f"vrs_{s}_points"], r[f"vrs_{s}_name"])
print("all published own lines and all VRS deep links verified")
PY
```
