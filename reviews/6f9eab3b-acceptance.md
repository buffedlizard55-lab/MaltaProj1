# E-08 landing integration acceptance review

- **Session:** `arena/6f9eab3b` · **Branch:** `arena/6f9eab3b-maltaproj1`
- **Review date:** 2026-10-14 UTC
- **Purpose:** independently record why the root landing page selects `executive/` as its primary board, the source/count defects found in the separate `livelines/` board, and what this integration does (and does not) claim.

## Decision

The root landing page and README now point to [`executive/picks.html`](../executive/picks.html) as the single primary picks destination. The 2026-10-14 05:11:44Z executive capture contains 88 fixtures and records 28 open fixtures at capture, each with a pick, two probabilities, and row-level sources (26 market-basis, 2 model-basis, 0 unpicked). The board's Valve standings links use a valid, verified Git commit ref. The root reads `executive/data/summary.json` and computes snapshot age from the capture timestamp at runtime; it does not trust the old pre-rendered `0.0 h old` text.

This is a **snapshot**, not a live betting feed. The open count means open at capture time, not still open now. The landing page shows the computed age and warns after four hours / marks the snapshot stale after eight hours, describes refresh automation as best-effort, and directs users to row-specific lock and quote times. At the time of the prior link review (~08:37Z), some 07:54Z/08:24Z lock times had already passed; no text on the landing should imply those rows remain actionable.

`livelines/` is retained and linked only in the archive disclosure, alongside a visible warning and this review. Its newer generated page is **not treated as authoritative** until the owning session corrects its Valve source links and reconciles its saved slate with the later 88-fixture read. No file under `livelines/**` was edited by this integration.

A separate `fullpicks/` board from PR #127 is also preserved in the archive: it covers the 88-fixture capture with open picks, 54 source-verified historical results, and 6 DraculaN result rows left blank and flagged when the official result could not be verified. That full-slate view is useful, but the executive board remains the primary open-match picks destination because it has per-row evidence and the fully researched unresolved route.

## Valve Regional Standings source-link defect

The `livelines` output uses this GitHub URL in 88 of its 89 fixture rows:

- **Broken URL emitted by the board:** [`blob/2aa2805394fbc68f36a5752a5b16026f2ab2fed5/live/2026/standings_global_2026_10_05.md`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/2aa2805394fbc68f36a5752a5b16026f2ab2fed5/live/2026/standings_global_2026_10_05.md)
- **Why it fails:** `2aa2805394fbc68f36a5752a5b16026f2ab2fed5` is the file's Git blob SHA, not a commit SHA. The official GitHub REST API request [`GET /commits/2aa280…`](https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/commits/2aa2805394fbc68f36a5752a5b16026f2ab2fed5) returned **HTTP 422** (`No commit found for SHA`). The valid-commit file API response at the corrected ref reports the same `2aa280…` value as the file object's SHA, confirming the identifier-type mix-up.
- **Verified corrected URL:** [`blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md). The commit API resolves `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`; the file API returns the expected path, size 77,872 bytes, and blob SHA `2aa280…`. The Markdown starts “Standings as of 2026_10_05.” Directly fetching the corrected official file succeeded in the independent source check.

The correct URL is linked from the executive board's own-line rows. The `livelines` board's embedded local copy of the standings is not enough to prove that the published per-row links work: users need a valid, reachable source citation.

## Hotspawn fixture-count discrepancy

The evidence is preserved in `livelines/data/picks.json` and `livelines/data/live_reads.json`:

| Evidence | UTC | Observed |
|---|---:|---|
| Stored Hotspawn payload capture | `2026-10-14T02:06:30Z` | 89 fixture objects. `livelines/data/picks.json` is generated at `2026-10-14T08:04:51Z` but still reports `slate.fixture_count = 89` from this earlier payload capture. |
| `/lobby` reread | `2026-10-14T04:31:25Z` | 88 fixtures: tier filter All 88; B 24 / C 60 / S 4; 17 tournaments. The recorded observation says fixture `1079546` (Zomblers vs Overtake Sector) was present in the older payload but absent from the later tournament filter. |
| `/cs2-pickems` independent reread | `2026-10-14T04:32:30Z` | Again 88 fixtures, the same 24 / 60 / 4 tier split and same 17 tournaments. |

Fixture `1079546` in the saved payload is marked locked, with `lock_utc = 2026-10-14T00:54:00Z` and start `01:00:00Z`; it is the row that explains the one-fixture difference. The evidence indicates a stale/retired locked entry in the 89-row capture, not a reason to invent a replacement fixture. The independent executive capture at `2026-10-14T05:11:44Z` also records 88 fixtures. This review does not claim the live lobby still has 88 fixtures now; it records the reads above and asks the owner to re-read and reconcile on its next build.

## Executive snapshot and root-page behavior

Source artifacts: [`executive/data/summary.json`](../executive/data/summary.json), [`executive/data/analysis.json`](../executive/data/analysis.json), [`executive/picks.html`](../executive/picks.html).

- Capture: `2026-10-14T05:11:44Z`; page/data generated: `2026-10-14T05:13:38Z`.
- At that capture: 88 total fixtures; 28 open; 28/28 picks; 26 outside-market basis; 2 own/model basis; 0 without a pick. All open rows have two probabilities and source links.
- Inputs recorded in `summary.json`: Hotspawn read `2026-10-14T05:11Z`; primary-book live read `2026-10-14T05:11` (9 CS2 quotes); official standings dated 2026-10-05; HLTV world ranking dated 2026-10-12. The displayed source timestamps do not make quotes live now; each row's own read time remains decisive.
- The root pulls counts/timestamps from the executive JSON, verifies their presence, computes elapsed age from `capture_utc`, refreshes metadata periodically, and warns beyond 4 hours / marks stale beyond 8 hours. It checks the open count against picks plus missing picks and does not hard-code fixture totals.
- The independent executive cadence page had previously been observed displaying a stale “0.0 h old” label and obsolete lock countdowns. This landing therefore computes its own age and does not copy that label. The cadence link remains available for schedule details; inspect its absolute timestamps, not its cached age/countdown text.
- No Hotspawn crowd-pick percentages are used to estimate probabilities. Missing/unverified identity, format, odds, or rating evidence must remain blank and flagged; this review adds no forecasts or source data.

## Integration scope and checks

Changed for E-08: root `index.html`, `README.md`, landing regression tests, this Markdown review, and the matching HTML review. `COORDINATION.md` is append-only. The primary action and README now lead to `executive/`; `livelines/`, the other dashboards, and the HTML/archive link structure remain intact. The root's prominent warning cites this review and states why `livelines/` is archived pending correction.

Validation results are recorded in the final E-08 completion entry in [`COORDINATION.md`](../COORDINATION.md). The acceptance checks cover snapshot counts against the captured rows, per-open-row picks/probability pairs/source links, mobile viewport and 44px actions, accessible live status, local-link resolution, lack of duplicate IDs, and regression behavior. Structural/crawl checks are scoped to the root landing and do not certify every external URL in every historical dashboard. The two live checks above are the explicit source/link exceptions found.

## Handoff to the `livelines/` owner

**Request to `arena/457629c4` (owner of `livelines/**`):**

1. Change the VRS URL builder to use the actual commit `eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`, not the content/blob SHA `2aa2805394fbc68f36a5752a5b16026f2ab2fed5`; re-fetch every generated URL and check HTTP status before publishing.
2. Re-read both Hotspawn `/lobby` and `/cs2-pickems` on the same build, reconcile the stored 89-entry capture with the 88-entry later reads (including locked fixture `1079546`), and make the true read time and fixture inventory visible in the generated board.
3. Keep this issue on `livelines/`'s Flagged for Review page until both fixes are verified. The root integration has intentionally not edited the owner's files.

**Deployment status:** the release SHA, GitHub Pages build, and live-page confirmation are recorded in the final E-08 release entry in `COORDINATION.md` after merge. This report contains no claim of deployment before that verification.
