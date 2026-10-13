# Independent Source Audit — MaltaProj1

- **Audit date:** 2026-10-13 UTC
- **Audited release:** `main` at `03b6336b5bbb48c936c09d50f42a3cc958aab014`
- **Latest deployment observed:** Pages run [`38450519525`](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38450519525), success for `03b6336`; Pages API reported `built`.
- **Review mode:** Read-only. No site, source-data, model, or workflow corrections were made.

## Executive assessment

The latest merged release is deployed. Its 380-fixture inventory, 26-fixture docs dashboard, 27-fixture verified-lines dashboard, and 86-fixture calibrated VRS model are distinct products with distinct denominators. Hotspawn crowd percentages are expressly excluded from match-win probabilities. PR #23 added roster- and fixture-evidenced aliases for WROTBERRY/WBT and RoundsGG/ROUNDS; PRs #23–#24 added read-only source and chronology cross-checks; PR #25 added a plain-language “Picks at a glance” section to `/model/`.

Two material trust issues remain. First, dated bookmaker observations in multiple committed artifacts post-date the commits containing them; PR #24's new validator now lists **40** such values across three files, in addition to the independently observed chronology gap in the canonical `/docs/` dataset. PR #19's bookmaker export also omits per-row quote-capture times. This does not prove the odds themselves are false, but their capture history and freshness are not established. Second, the PR #19 dashboard labels its VRS rank inputs as official Valve standings, while the new official-source comparison reports **33 mismatches among 35 resolvable team rows**. Since those ranks feed PR #19's dual-rank probability calculation, the displayed model outputs are not source-verified as Valve-VRS lines until the discrepancy is reconciled.

The live/started H-00 fixture still has pre-match-looking picks on both line dashboards. The calibrated VRS page covers 24/27 fixtures in the current week and 56/86 overall, but it is not linked from the root or docs landing pages. The audit also found broken fragment targets and older labeling issues. Unsupported values remain blank; no correction was made outside this report and the append-only coordination record.

## Release and scope checked

The latest observed `main` includes PRs #19–#25. PR #23 added two fixture-matched aliases and a read-only comparison against official VRS, HLTV, and Hotspawn snapshots. PR #24 added a check for timestamps later than each file's own last commit. PR #25 added “Picks at a glance” to the top of `/model/`. The latest Pages workflow and legacy Pages API both report a successful deployment for `03b6336`. Cache-busted live fetches confirmed the root, `/docs/`, `/docs/verified-lines.html`, and `/model/` were serving after that deployment. The root and docs landing pages link to verified lines but not `/model/`.

The product surfaces and their observed coverage are intentionally not interchangeable:

| Surface | What it counts | Published coverage observed |
|---|---|---|
| [`/pickem/`](https://buffedlizard55-lab.github.io/MaltaProj1/pickem/) | 380 Hotspawn payload fixtures: 86 CS2 + 294 LoL | 17 external-priced rows; 363 without a usable line (4 source defaults + 359 not found). These are market no-vig probabilities, not an independent model. |
| [`/docs/`](https://buffedlizard55-lab.github.io/MaltaProj1/docs/) | 26 pickable CS2 fixtures | 25 with a market line, 25 market-favorite picks, 16 HLTV-rank model lines, and H-12 blank/flagged. |
| [`/docs/verified-lines.html`](https://buffedlizard55-lab.github.io/MaltaProj1/docs/verified-lines.html) | 27 October CS2 fixtures: 26 SSR DOM fixtures plus H-00, already started/live at audit time | 24 external lines, 3 bookmaker placeholders left blank, and 27 displayed dual-rating outputs. The VRS-rank inputs for those outputs are disputed by SA-09; H-00 still has a model-only pick. |
| [`/model/`](https://buffedlizard55-lab.github.io/MaltaProj1/model/) | 86 CS2 fixtures: 26 upcoming + 1 started + 59 stale listings | 24/27 current-week fixtures and 56/86 total have a calibrated VRS line; 31 flags. PR #25's “Picks at a glance” table now surfaces a pick, win %, fair odds, and confidence for each line. Three current-week rows remain blank/ambiguous. |

The calibrated VRS model is CS2-only. The full 380-fixture inventory does not have a supported independent model line for every match; blanks remain preferable to guesses. The market-derived `/pickem/` values are not substitutes for that model.

## Findings requiring owner action

### SA-01 — High: several odds-capture timestamps post-date the files that contain them

PR #24's new [`model/data/crosscheck.csv`](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/model/data/crosscheck.csv) validator compares stated capture/snapshot times with the last commit of the corresponding file. It reports **40 future-dated values**:

- **26** `snapshot_utc` rows in root `data/lines.csv` report 18:47Z–18:55Z, although the file's last commit, `b97c24c`, is **18:19:05Z**.
- **13** `line_captured_utc` rows in `lines/analysis.csv` post-date its last commit, `32337d9` at **18:16:50Z**. Examples include `1079621` at 18:20Z, `1075807`/`1075808` at 18:25Z, and `1079334`, `1081076`, and `1079546` at 18:31Z; `1079622` is stamped 18:40Z.
- `lines/external_lines.json` says `generated_utc=18:45:00Z`, also after its last commit at 18:16:50Z.

Separately, canonical `data/matches.csv` was last committed in `8ea503f` at **18:23:40Z**, but its 25 priced rows carry `odds_snapshot_utc` values from **18:47Z to 18:55Z**. Those times are after the PR #17 merge (**18:25:34Z**) and the Pages build for `c5cdc3d` (**18:25:36Z–18:26:03Z**). The model page's M-S8 already flags four market-reference rows from `lines/analysis.csv` (`1081076`, `1079546`, `1079621`, `1079623`) as unverified for this chronology reason.

**Impact:** these static artifacts cannot establish that the later-stamped readings occurred when claimed. The odds may be plausible or may have been observed later; the record does not prove the values false. Do not describe them as verified-current or as synchronized snapshots until the provenance is repaired.

**Request:** recover genuine per-row source-read times from contemporaneous logs or recapture and rebuild the artifacts. Where the true time cannot be established, blank it and label the price historical/undated/unverified; do not infer or backdate it. Retain source identity, exact match URL, and notes about movement/placeholders.

### SA-02 — High: PR #19 bookmaker export has no per-row quote timestamp

`data/6d9c321d/external_bookmaker_lines.csv` and `matches_verified.csv` have no `captured_utc`, `observed_at`, or equivalent quote-time field. The HTML dates the audit only to 2026-10-13; that does not establish when any of its 24 displayed odds were read. PR #19's “Primary source accessibility — evidence audit” check was **skipped**, not passed.

The dashboard overlap shows why an as-of time matters: H-14 MIBR–BC.Game is 1.60/2.19 (57.8%/42.2% no-vig) in `data/matches.csv`, versus 1.64/2.08 (55.9%/44.1%) in PR #19's export. Ordinary market movement could explain this, but without a capture time the snapshots cannot be ordered or reconciled. A live EGamersWorld read can establish only what that page displays now, not replay a historical quote.

**Request:** add a per-row UTC capture time, named sportsbook/aggregator, and exact match-level source URL (or retained source snapshot) to PR #19's data and page. Until then, describe these as undated observations, not current verified lines.

### SA-03 — High: started/live fixtures still receive pre-match-looking lines or picks

- PR #19's H-00 (`1079620`, Black Phoenix–6666) record says it was hidden from the SSR DOM because it was already live, and notes a completed 13:4 first map. Yet `matches_verified.csv` and the public table still recommend **Black Phoenix (58.3%)** as a model-only pick. The calibrated VRS input labels this row `section=started`. After PR #25, the public `/model/` “Picks at a glance” table prominently lists **Black Phoenix (62.4%)**, fair odds 1.6, confidence “lean”; the detailed row still says generic “own line,” with no visible started/closed label. The current `/docs/verified-lines.html` live page likewise still offers H-00's pick.
- The LoL fixture KOI Fénix–Galions (`1079334`) is marked `priced` in `lines/analysis.csv` with an 18:31Z capture even though the row says the match was live. The direct [EGW match page](https://egamersworld.com/lol/match/z27dDLdCP/koi-fenix-vs-galions-6h6H1-26V) and [EGW live listing](https://egamersworld.com/lol/matches) labeled it Live when checked. The `/pickem/` row includes the in-play quote among its 17 priced rows.

**Request:** expose live/started/final status separately from Hotspawn's stale `scheduled` flag; exclude in-play/final quotes from pre-match counts and suppress actionable picks after start. Retain model values only if clearly labeled non-actionable historical estimates.

### SA-04 — High: Envy → VRS “3DMAX” remains a roster-based identity mapping needing authoritative confirmation

For Heroic–Envy (`1079442`), `model/data/lines.csv` publishes a line/pick using VRS name **3DMAX**. The row says `VERIFIED: HLTV roster -> VRS (name differs)` and “team matched to VRS by roster (name differs) - review.” The public flag M-05 says all five players match and explicitly asks the reader to “please confirm the org/name change.” PR #20's description also calls for confirmation. The [EGW match page](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC) and [HLTV match page](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii) identify Heroic–Envy, and the HLTV Envy team page lists the same five players as the pinned VRS `3DMAX` roster. That is roster-continuity evidence, but not itself an authoritative statement that the historical VRS row should be treated as the current Envy organization/team identity.

PR #23's new aliases for **WROTBERRY = WBT** and **RoundsGG = ROUNDS** are different: they cite HLTV pages/matches for the same event, opponents, and dates as the Hotspawn fixtures, then re-check the roster against VRS on every build; the aliased lines remain flagged for review. Those two additions do not document an Envy/3DMAX name change.

**Request:** cite an authoritative identity/name-change source and state the mapping explicitly. Otherwise leave the affected VRS-derived value blank or conditional and non-verified. The selected 18:31Z price remains independently subject to SA-01. The stored exports also retain match-specific URLs for Sashi Esport and MIBR–BC.Game Esports; those two pages were not independently replayed in this audit. For BNK FearX, the Pick'em CSV points only to the general EGW listing; retain the direct [FearX–KT match page](https://egamersworld.com/lol/match/FqxSssBfV/fearx-vs-kt-rolster-tW-gg6CEW) and source-side ordering.

### SA-05 — Medium: four internal links point at three missing fragment targets

A local HTML/fragment pass over **50 HTML files and 751 local references** found four broken fragment references:

- `docs/flagged.html` links to `verified-lines.html#F-28`, `#F-29`, and `#flagged-audit`.
- `docs/verified-lines.html` itself links to `#F-28`.

The target headings/sections have no matching `id` attributes. `python3 tests/audit_site.py` passes because it checks local files but does not validate fragment IDs. Add stable IDs or update the links, then include fragments in the link audit. HTTP 200 for the page does not establish that an anchor exists.

### SA-06 — Medium: the merged calibrated model is not discoverable from the main site

The deployed [`/model/`](https://buffedlizard55-lab.github.io/MaltaProj1/model/) page is accessible directly. Neither current root `index.html` nor `docs/index.html` links to it, and the Flagged page does not link to its model flags. PR #20 explicitly left navigation as an integration request; PRs #22–#25 did not add those links.

**Request:** add a clear root/docs link describing the calibrated VRS model and link `/model/#flags` from the review/flags surface. Until then, users following the root navigation will not find the independent calibrated CS2 line.

### SA-07 — Medium: an accessible legacy page labels EDT clock times as UTC

`docs/own-lines.html` remains published under the old session-844 title, though it is not linked from the current docs landing page. It labels H-01 **2026-10-13 17:00 UTC**, while canonical `data/fixtures.csv` gives `2026-10-13T21:00:00Z`; it labels H-14 **06:00 UTC**, while the canonical fixture is `2026-10-15T10:00:00Z`. These are four-hour offsets consistent with EDT values mislabeled UTC. The current canonical matches page correctly separates display time and UTC.

**Request:** correct the legacy labels or clearly mark/archive the page as an obsolete EDT snapshot so it cannot be mistaken for current UTC data.

### SA-08 — Low: “own de-vigged line” can be confused with an independent model

The root `/pickem/` copy calls the bookmaker no-vig calculation “this project's own line”/“own de-vigged line.” Its formula `pA = (1/oA) / ((1/oA)+(1/oB))` is a market-implied probability after removing vig, not an independent model probability. The new `/model/` output is a separate calibrated VRS model; `/docs/` has a simpler HLTV-rank model.

**Request:** label the `/pickem/` result “market no-vig probability” and reserve “own/model line” for independently originated model outputs. This distinguishes external market consensus from an independent line.

### SA-09 — High: PR #19's displayed “Valve VRS” ranks mismatch the pinned official Valve snapshot

The PR #23–#24 read-only cross-check compares `data/6d9c321d/team_ratings_verified.csv` `vrs_rank` values with Valve's pinned 2026-10-05 standings. Of **35 resolvable teams, 33 are marked MISMATCH**; only 2 match. The cross-check says the published values instead match HLTV's own dated “Valve ranking VRS” widget. Examples include:

| Team as published | PR #19 `vrs_rank` | Pinned official Valve VRS | Cross-check status |
|---|---:|---:|---|
| Legacy | 6 | 2 | MISMATCH |
| PARIVISION | 11 | 36 | MISMATCH |
| Aurora | 4 | 9 | MISMATCH |
| Black Phoenix | 67 | 76 | MISMATCH |
| 6666 | 118 | 127 | MISMATCH |
| Envy (resolved by roster to 3DMAX) | 27 | 21 | MISMATCH |
| WROTBERRY (fixture-matched to WBT) | 64 | 60 | MISMATCH |
| RoundsGG (fixture-matched to ROUNDS) | 314 | 310 | MISMATCH |

The pinned Valve file confirms representative official entries: Black Phoenix #76 and 6666 #127; 3DMAX #21; WBT #60; ROUNDS #310. The [`docs/verified-lines.html`](https://buffedlizard55-lab.github.io/MaltaProj1/docs/verified-lines.html) page calls its rank inputs Valve VRS and presents 27/27 dual-rank outputs. `scripts/6d9c321d_build.py` uses `vrs_rank` in its composite rank formula, so this provenance mismatch affects the model inputs, not merely a display label. The findings do **not** prove which individual picks would change, but they do mean those outputs are not yet source-verified as official-Valve dual-rank lines.

**Request:** either replace the rank inputs with the pinned official Valve standings and regenerate/re-review dependent probabilities and picks, or relabel the current values with their actual HLTV-widget source/date and keep them distinct from Valve ranks. Add a regression check against the official snapshot. Leave any unresolved values blank rather than asserting they are official.

### SA-10 — Low: the new cross-check finds two legacy HLTV snapshot metadata/completeness issues

The same PR #23 cross-check reports that `lines/reference_ranks.json` says the HLTV ranking is dated **2026-10-13**, while the cited official page is explicitly “World ranking on October 12th, 2026.” Its checked rank/point pairs match the Oct 12 page; the date note is the mismatch. It also finds **14 blank** ranks in legacy `data/844ba68e/ranks.csv` for teams present on that Oct 12 page (examples: Galorys #68, Voca #59, HAVU #118). These observations concern older datasets/pages, not the separate calibrated model.

**Request:** correct the snapshot date label and, if the legacy page is still intended for use, fill those ranks from the cited official page with row-level sources; otherwise mark that artifact as a historical/incomplete snapshot. As a positive control, the same cross-check reports **396/396** fixture-team/start comparisons across three datasets matching Hotspawn TransferState with zero mismatches.

## Checks that passed and issues ruled out

- `python3 tests/audit_site.py`: passed — 9 root HTML files, 20 docs HTML files, and 26 canonical match records. It did not catch the missing fragments described in SA-05.
- `python3 assurance/test_audit.py`: **22 tests passed**. Its printed `https://github.com/example` is a `MagicMock` response in `test_check_report_preserves_unicode_bytes`, not a real published accessibility report.
- `python3 model/test_model.py`: **12 tests discovered, 11 passed and 1 skipped** because `VRS_REPO_DIR` was not supplied. The run emitted two non-fatal unclosed-file `ResourceWarning`s.
- The latest `model/data/crosscheck.csv` has 627 rows, including the 40 timestamp-after-commit rows, 33 VRS standing mismatches, and 396 matching fixture identity/start checks. These cross-check results make source verification more transparent; they do not repair the affected source datasets.
- Independent arithmetic over PR #19's 27-row odds export: all 24 priced rows reproduce stored no-vig probabilities within rounding; no partial-odds or probability discrepancies found. All 27 originated probability pairs sum to 100% within rounding. H-15's Heroic recommendation follows the stated market/model blend, so comparing it only to the unblended model favorite would be a false alarm. Correct arithmetic does not validate disputed input provenance (SA-09).
- H-20's divergence rule was checked rather than assumed: `scripts/model.py` flags a market-favorite gap of at least 12.5 percentage points. H-20's 60.9% market versus 49.7% model gap is 11.2 points; the lower-tiers page separately notes the near-even direction mismatch. This is consistent with the stated threshold, not a missing-threshold bug.
- `docs/data/matches.json` is valid JSON with a metadata wrapper (`generated_at`, `sources`, etc.) and a 26-item `matches` array. Treating its top-level object as a list was an inspection assumption, not a data defect.
- Hotspawn crowd values remain marked audit-only; the VRS-model tests explicitly verify that Hotspawn pick percentages are not ingested. PR #19's page likewise says crowd percentages are never probability inputs.

### Independent source spot checks

The audit re-fetched selected match-level sources; these spot checks do not reconstruct every historical quote:

- [EGW ex-Keyd Stars–Galorys](https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp) identified the exact teams/event and displayed 2.43/1.46 when fetched. The older `/pickem/` row records 2.44/1.48 at 18:31Z; the later canonical table records 2.43/1.46 with 18:52Z. This is compatible with movement, but does not validate the impossible snapshot chronology.
- [EGW KOI Fénix–Galions](https://egamersworld.com/lol/match/z27dDLdCP/koi-fenix-vs-galions-6h6H1-26V) named KOI Fénix directly and displayed 3.05/1.31; the general listing displayed 3.07/1.396 and marked the match live. The page-specific price difference and in-play status are why the row must not be presented as a verified pre-match quote.
- [EGW FearX–KT Rolster listing](https://egamersworld.com/lol/matches) showed FearX first at 3.27 and KT second at 1.31. That supports current match identity and source-side order; it does not replay the `/pickem/` row's later 1.44/2.70 quote.
- [EGW Heroic–Team Envy](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC) and [HLTV Heroic–Envy](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii) supported the Team Envy/Envy match naming and displayed the stored 1.50/2.55 EGW price when fetched. They do not establish the Envy→3DMAX VRS identity mapping.
- The pinned [Valve Regional Standings file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) was checked against the cross-check examples in SA-09, including its rows for Black Phoenix, 6666, 3DMAX, WBT, and ROUNDS.

## Verification limits and disposition

PR #19's audit job passed, but its primary-source accessibility check was skipped. Current EGamersWorld and HLTV pages are mutable; a live re-fetch establishes what a page displays now, not what it displayed at the timestamp in a committed CSV. PR #19's bookmaker export lacks quote timestamps. The audit independently recomputed its no-vig arithmetic, checked selected source pages and the pinned Valve sample rows, counted the merged official-source cross-check results, and inspected the release/deployment state. It did **not** replay every historical bookmaker observation, freshly re-scrape every rank for all teams, or independently rerun the complete VRS calibration history.

**Disposition:** the latest Pages release is operational. Inventory integrity, tested no-vig arithmetic, model unit tests, and fixture identity checks pass. However, the dated odds should not be represented as fully verified-current until SA-01/SA-02 are corrected, and PR #19's dual-rank probabilities should not be represented as official-Valve-verified until SA-09 is resolved. Started/live picks and the Envy–3DMAX mapping need the scoped follow-up above. No site/data/model fixes were made in this audit.

## Primary references

- [Audited main commit `2d7f87a`](https://github.com/buffedlizard55-lab/MaltaProj1/commit/2d7f87a8199252ad77421b02a3ba8951a6703f72)
- [PR #16: 380-fixture Pick'em inventory](https://github.com/buffedlizard55-lab/MaltaProj1/pull/16) · [PR #17: refreshed docs dataset](https://github.com/buffedlizard55-lab/MaltaProj1/pull/17) · [PR #19: verified-lines dashboard](https://github.com/buffedlizard55-lab/MaltaProj1/pull/19) · [PR #20: calibrated VRS model](https://github.com/buffedlizard55-lab/MaltaProj1/pull/20) · [PR #22: model release/workflow record](https://github.com/buffedlizard55-lab/MaltaProj1/pull/22) · [PR #23: aliases and official-source cross-check](https://github.com/buffedlizard55-lab/MaltaProj1/pull/23) · [PR #24: commit-time chronology check](https://github.com/buffedlizard55-lab/MaltaProj1/pull/24) · [PR #25: Picks at a glance](https://github.com/buffedlizard55-lab/MaltaProj1/pull/25)
- [Pick'em quote ledger](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/lines/analysis.csv) · [canonical match data](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/data/matches.csv) · [PR #19 odds export](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/data/6d9c321d/external_bookmaker_lines.csv) · [PR #19 rank export](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/data/6d9c321d/team_ratings_verified.csv) · [official-source cross-check](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/model/data/crosscheck.csv) · [calibrated model rows](https://github.com/buffedlizard55-lab/MaltaProj1/blob/2d7f87a8199252ad77421b02a3ba8951a6703f72/model/data/lines.csv)
- [Pages deployment run `38450519525`](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38450519525) · [PR #19 checks](https://github.com/buffedlizard55-lab/MaltaProj1/pull/19/checks)
