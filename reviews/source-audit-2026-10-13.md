# Independent Source Audit — MaltaProj1

- **Audit date:** 2026-10-13 UTC
- **Audited release:** `main` at `273f816273365b7865cb32f41eb0b0d8323b541f`
- **Latest deployment observed:** Pages run [`38448358664`](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38448358664), success for `273f816`; Pages API reported `built`.
- **Review mode:** Read-only. No site, source-data, model, or workflow corrections were made.

## Executive assessment

The latest merged site is deployed, the three principal fixture universes are documented separately, the tested no-vig calculations reproduce, and the project explicitly excludes Hotspawn crowd picks from match-win probabilities. The newer calibrated VRS model is live at `/model/` and leaves unsupported ratings blank.

**The archived bookmaker quotes are not currently source-audit cleared as dated/current lines.** The principal problem is chronology: several `captured_utc`/`odds_snapshot_utc` values occur after the last commit containing those values and, for the canonical `/docs/` table, after its merge and Pages build. Separately, PR #19's new bookmaker export has no quote-capture timestamp at all. This does not prove the numeric odds are false; it does mean their stated capture history and freshness cannot be trusted without corrected logs or a new, properly timestamped capture.

A second material issue is that fixtures known to be live/started still appear in “priced” or “recommended pick” tables. The main page also does not link the now-merged calibrated model, and several audit links on the verified-lines page point to missing HTML anchors.

## Release and scope checked

The latest observed main commit includes PRs #19–#22. PR #20's calibrated Valve-VRS model is now merged; PR #22 records that merge and adds its main-branch refresh trigger. The latest Pages workflow and legacy Pages API both report a successful deployment for `273f816`. Cache-busted live fetches confirmed the root, `/docs/`, `/docs/verified-lines.html`, and `/model/` were serving. The root and docs landing pages link to the verified-lines page, but neither links to `/model/`.

The site contains several deliberately different universes; their denominators should not be compared as if they were one refresh:

| Surface | What it counts | Published coverage observed |
|---|---|---|
| [`/pickem/`](https://buffedlizard55-lab.github.io/MaltaProj1/pickem/) | 380 Hotspawn payload fixtures: 86 CS2 + 294 LoL | 17 external-priced rows; 363 without a usable line (4 source defaults + 359 not found). Its formula is a bookmaker no-vig probability, not an independent model. |
| [`/docs/`](https://buffedlizard55-lab.github.io/MaltaProj1/docs/) | 26 pickable CS2 fixtures | 25 with a market line, 25 market-favorite picks, 16 HLTV-rank model lines, and H-12 blank/flagged. |
| [`/docs/verified-lines.html`](https://buffedlizard55-lab.github.io/MaltaProj1/docs/verified-lines.html) | 27 October CS2 fixtures: the 26 SSR DOM fixtures plus H-00, already live at capture | 24 external lines, 3 bookmaker placeholders left blank, and 27 dual-rating outputs. H-00 nevertheless still has a recommended model-only pick. |
| [`/model/`](https://buffedlizard55-lab.github.io/MaltaProj1/model/) | 86 CS2 fixtures: 26 upcoming + 1 started + 59 stale listings | 18/27 current-week fixtures and 49/86 total have a calibrated VRS line. The model uses the 2026-10-05 VRS snapshot and has explicit blank/ambiguity flags. It is not linked from the root or docs landing page. |

The calibrated VRS model is CS2-only. The full 380-fixture inventory does not yet have a supported independent model line for every match; blank values remain preferable to guessed values.

## Findings requiring owner action

### SA-01 — High: odds capture chronology is impossible as recorded

**Evidence**

- `lines/analysis.csv` was last committed in `32337d9` at **18:16:50Z**. Its `line_captured_utc` values range from **18:00Z to 18:40Z**; for example, the ex-Keyd Stars–Galorys row says 18:31Z, and the file also records later source observations. PR #16 did not merge until 18:19:44Z. The `/pickem/` page headline says “Collected 18:19 UTC,” but the data file itself predates several row timestamps.
- `data/matches.csv` was last committed in `8ea503f` at **18:23:40Z**. Its 25 priced rows carry `odds_snapshot_utc` values from **18:47Z to 18:55Z**. PR #17 merged at **18:25:34Z**; the Pages build for `c5cdc3d` ran from **18:25:36Z to 18:26:03Z**. Therefore the recorded quote snapshots post-date the data commit, merge, and deployed page.
- The merged model dashboard also records four `lines/analysis.csv` market-reference rows after that file's last commit (18:20Z or 18:31Z); its own M-S8 note correctly says to treat those references as unverified: fixture IDs `1081076`, `1079546`, `1079621`, and `1079623`.

**Impact:** the quote values may be plausible or may have been observed later, but the repository history cannot support the timestamps attached to them. A static artifact cannot establish the claimed later capture time. Do not treat those prices as verified-current, or compare them as synchronized snapshots, until the chronology is repaired.

**Request:** for each source row, recover a genuine source-read timestamp from contemporaneous logs or recapture the market and rebuild the artifact. If the true capture time cannot be established, leave the timestamp blank and label the quote historical/unverified; do not backdate or infer it. Preserve the existing notes about source-page drift and placeholders.

### SA-02 — High: PR #19 bookmaker export has no quote timestamp

`data/6d9c321d/external_bookmaker_lines.csv` and `matches_verified.csv` have no `captured_utc`, `observed_at`, or equivalent field. The HTML page dates the audit only to 2026-10-13; it does not establish when any of the 24 displayed odds were read. PR #19's “Primary source accessibility — evidence audit” check was **skipped**, not passed.

The overlap between dashboards illustrates why an as-of value matters: H-14 MIBR–BC.Game is 1.60/2.19 (57.8%/42.2% no-vig) in `data/matches.csv`, versus 1.64/2.08 (55.9%/44.1%) in PR #19's export. This can be ordinary market movement; with no capture time on the PR #19 row, the snapshots cannot be ordered or reconciled. The live EGamersWorld source can confirm a displayed price now, but cannot replay a historical quote.

**Request:** add a per-row UTC capture time, the named sportsbook/aggregator and its exact match-level source URL (or a retained source snapshot) to PR #19's data and page. Until then, describe the prices as undated observations, not current verified lines.

### SA-03 — High: started/live fixtures still receive pre-match-looking lines or picks

- PR #19's H-00 (`1079620`, Black Phoenix–6666) record says it was hidden from the SSR DOM because it was already live, and even notes the completed 13:4 first map. Yet `matches_verified.csv` and the public table still recommend **Black Phoenix (58.3%)** as a model-only pick. The VRS-model input correctly labels this row `section=started`, but its public table still shows the pick and generic “own line” status without a visible started/closed label.
- The LoL fixture KOI Fénix–Galions (`1079334`) is marked `priced` in `lines/analysis.csv` with an 18:31Z capture even though the same row says the match was live. The direct [EGW match page](https://egamersworld.com/lol/match/z27dDLdCP/koi-fenix-vs-galions-6h6H1-26V) and [EGW live listing](https://egamersworld.com/lol/matches) label it Live. The `/pickem/` row also carries this in-play quote among the 17 priced rows.

**Request:** expose a live/started/final status separately from Hotspawn's stale `scheduled` status; exclude in-play/final quotes from the pre-match count and suppress actionable pre-match picks after start. Retain historical model values only if clearly labeled non-actionable.

### SA-04 — High: Envy → VRS “3DMAX” remains an unconfirmed model identity mapping

For Heroic–Envy (`1079442`), `model/data/lines.csv` publishes an own line and pick using VRS name **3DMAX**, with `resolution_b = “VERIFIED: HLTV roster -> VRS (name differs)”` and note “team matched to VRS by roster (name differs) - review.” PR #20's description explicitly says Envy is rated via the 3DMAX roster and asks for confirmation of the name change. The dual-rank PR #19 team file also gives Envy VRS #27 with an “ex-3DMAX” roster note.

The [EGW match page](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC) identifies Team Envy and the [HLTV match page](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii) identifies Envy for the same opponent/event. These support the match/team identity, but do not by themselves establish that a historical VRS row named 3DMAX should be treated as Envy under the user's no-inferred-alias rule.

**Request:** attach an official name-change/roster-continuity source and make the mapping explicit; otherwise blank the affected VRS-derived model value or mark it conditional and non-verified. KOI Fénix is named directly on its re-fetched EGW match page. The stored exports also retain match-specific URLs for Sashi Esport and MIBR–BC.Game Esports; those two pages were not independently replayed in this audit. For BNK FearX, the Pick'em CSV points only to the general EGW listing; store the direct [FearX–KT match page](https://egamersworld.com/lol/match/FqxSssBfV/fearx-vs-kt-rolster-tW-gg6CEW) and preserve its source-side ordering. The selected 18:31Z price remains subject to SA-01.

### SA-05 — Medium: four internal links point at three missing fragment targets

A local HTML/fragment pass over **44 HTML files and 697 local references** found four broken fragment references:

- `docs/flagged.html` links to `verified-lines.html#F-28`, `#F-29`, and `#flagged-audit`.
- `docs/verified-lines.html` itself links to `#F-28`.

The target headings/sections have no matching `id` attributes. The existing `tests/audit_site.py` run passes because it verifies local files but does not validate fragment IDs. Add stable IDs or update the links, then include fragments in the link audit. The live pages return HTTP 200, which alone does not establish that an anchor exists.

### SA-06 — Medium: the merged calibrated model is not discoverable from the main site

The deployed [`/model/`](https://buffedlizard55-lab.github.io/MaltaProj1/model/) page is accessible directly. Neither the current root `index.html` nor `docs/index.html` links to it, and the Flagged page does not link to its model flags. PR #20's description explicitly left navigation as an integration request; PR #22 did not add those links.

**Request:** add a clear root/docs link describing the calibrated VRS model and a link to `/model/#flags` from the review/flags surface. Until then, users following the root navigation will not find the most recent calibrated independent CS2 line.

### SA-07 — Medium: an accessible legacy page labels EDT clock times as UTC

`docs/own-lines.html` remains published under the old session-844 title, though it is not linked from the current docs landing page. It labels H-01 as **2026-10-13 17:00 UTC**, while canonical `data/fixtures.csv` gives `2026-10-13T21:00:00Z`; it labels H-14 **06:00 UTC**, while the canonical fixture is `2026-10-15T10:00:00Z`. These are four-hour offsets consistent with EDT values mislabeled UTC. The current canonical matches page correctly separates display time and UTC.

**Request:** correct the legacy labels or clearly mark/archive the page as an obsolete EDT snapshot so it cannot be mistaken for current UTC data.

### SA-08 — Low: “own de-vigged line” can be confused with an independent model

The root `/pickem/` copy calls the bookmaker no-vig calculation “this project's own line”/“own de-vigged line.” Its formula is `pA = (1/oA) / ((1/oA)+(1/oB))`, which is a market-implied probability after removing vig, not an independent model probability. The new `/model/` output is a separate calibrated VRS model, while `/docs/` has a simpler HLTV-rank model.

**Request:** label the `/pickem/` result “market no-vig probability” and reserve “own/model line” for the independently originated model outputs. This keeps an external market consensus distinct from the requested independent line.

## Checks that passed and issues ruled out

- `python3 tests/audit_site.py`: passed — 9 root HTML files, 20 docs HTML files, 26 canonical match records. It did not catch the missing fragments described in SA-05.
- `python3 assurance/test_audit.py`: 22 tests passed. Its printed `https://github.com/example` is a `MagicMock` response in `test_check_report_preserves_unicode_bytes`, not a real published accessibility report.
- `python3 model/test_model.py`: 11 tests discovered; 10 ran successfully and 1 (comparison against Valve's JavaScript) was skipped because `VRS_REPO_DIR` was not supplied. The test output also emitted two non-fatal unclosed-file `ResourceWarning`s.
- Independent arithmetic over PR #19's 27-row odds export: all 24 priced rows reproduce the stored no-vig probabilities within rounding; no partial-odds or probability discrepancies found. All 27 originated probability pairs sum to 100% within rounding. H-15's Heroic recommendation follows the stated market/model blend, so a direct comparison to the unblended model favorite would be a false alarm.
- The H-20 divergence rule was checked rather than assumed: `scripts/model.py` flags a market-favorite gap of at least 12.5 percentage points. H-20's 60.9% market versus 49.7% model gap is 11.2 points; the lower-tiers page separately notes the near-even direction mismatch. This is consistent with the stated threshold, not a missing-threshold bug.
- `docs/data/matches.json` is valid JSON with a metadata wrapper (`generated_at`, `sources`, etc.) and a 26-item `matches` array. The earlier attempt that treated its top-level object as a list was a parser assumption, not a data defect.
- Hotspawn crowd values remain marked audit-only; the VRS-model tests explicitly verify that Hotspawn pick percentages are not ingested. PR #19's page likewise says crowd percentages are never probability inputs.

### Independent source spot checks

The audit re-fetched selected match-level sources; these spot checks do not reconstruct every historical quote:

- [EGW ex-Keyd Stars–Galorys](https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp) identifies the exact teams/event and displayed 2.43/1.46 when fetched. The older `/pickem/` row records 2.44/1.48 at 18:31Z; the later canonical table records 2.43/1.46 with 18:52Z. This is compatible with market movement but does not validate the impossible snapshot chronology.
- [EGW KOI Fénix–Galions](https://egamersworld.com/lol/match/z27dDLdCP/koi-fenix-vs-galions-6h6H1-26V) names KOI Fénix directly and displayed 3.05/1.31; the general listing displayed 3.07/1.396 and marked the match live. The page-specific difference and in-play status are why the row must not be presented as a verified pre-match price.
- [EGW FearX–KT Rolster listing](https://egamersworld.com/lol/matches) showed FearX first at 3.27 and KT second at 1.31. That supports the current match identity and source-side order; it does not replay the `/pickem/` row's later 1.44/2.70 quote.
- [EGW Heroic–Team Envy](https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC) and [HLTV Heroic–Envy](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii) support the Team Envy/Envy match naming and the stored 1.50/2.55 EGW price when fetched. They do not resolve Envy→3DMAX in the VRS model.

## Verification limits and disposition

PR #19's audit job passed, but its primary-source accessibility check was skipped. Current EGamersWorld and HLTV pages are mutable; a live re-fetch can establish what a page displays now, not what it displayed at the date embedded in a committed CSV. The PR #19 export does not retain quote timestamps. This audit independently checked formula arithmetic, page/link integrity, release/deploy state, selected live source pages, and model logic; it did **not** replay every historical bookmaker observation or independently rerun the complete VRS calibration history.

**Disposition:** the Pages release is operational and the inventory/model arithmetic checks pass, but the odds should not be represented as fully verified-current until SA-01 and SA-02 are corrected. Started/live fixtures and the Envy–3DMAX mapping need the scoped follow-up described above. No site/data fixes were made in this audit.

## Primary references

- [Main commit `273f816`](https://github.com/buffedlizard55-lab/MaltaProj1/commit/273f816273365b7865cb32f41eb0b0d8323b541f)
- [PR #16: 380-fixture Pick'em inventory](https://github.com/buffedlizard55-lab/MaltaProj1/pull/16) · [PR #17: refreshed docs dataset](https://github.com/buffedlizard55-lab/MaltaProj1/pull/17) · [PR #19: verified-lines dashboard](https://github.com/buffedlizard55-lab/MaltaProj1/pull/19) · [PR #20: calibrated VRS model](https://github.com/buffedlizard55-lab/MaltaProj1/pull/20) · [PR #22: model release/workflow record](https://github.com/buffedlizard55-lab/MaltaProj1/pull/22)
- [Pick'em quote ledger](https://github.com/buffedlizard55-lab/MaltaProj1/blob/273f816273365b7865cb32f41eb0b0d8323b541f/lines/analysis.csv) · [canonical match data](https://github.com/buffedlizard55-lab/MaltaProj1/blob/273f816273365b7865cb32f41eb0b0d8323b541f/data/matches.csv) · [PR #19 odds export](https://github.com/buffedlizard55-lab/MaltaProj1/blob/273f816273365b7865cb32f41eb0b0d8323b541f/data/6d9c321d/external_bookmaker_lines.csv) · [VRS-model market references](https://github.com/buffedlizard55-lab/MaltaProj1/blob/273f816273365b7865cb32f41eb0b0d8323b541f/model/data/lines.csv)
- [Pages deployment run `38448358664`](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38448358664) · [PR #19 checks](https://github.com/buffedlizard55-lab/MaltaProj1/pull/19/checks)
