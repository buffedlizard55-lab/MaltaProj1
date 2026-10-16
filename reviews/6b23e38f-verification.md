# Primary CS2 integration: verification and evidence limits

Session `arena/6b23e38f`, 16 October 2026. Maintained route: **[root summary](../index.html) → [all picks](../hotspawn/picks.html)**. No new competing board. Work stays on the Arena-fixed branch; PR150's authored contributions and newer main captures are preserved.

## What was actually checked

- Inspected the primary collector, shared helpers, calibration, model, builder, workflow, research, tests and mobile gate; reviewed PR150's source/test fixes and merge conflicts. Generated inventory/probabilities are reconciled **row by row** in [`hotspawn/data/row_audit.json`](../hotspawn/data/row_audit.json). This is a stored-input reproducibility audit, not proof that a future outcome is correct.
- The successful first live refresh [38850155496](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38850155496) captured **95 CS2 fixtures / 31 open at 04:21:10 UTC**, including newly listed **BetBoom–Legacy 1081775**. These are timestamped snapshot counts, not a permanent coverage promise. Subsequent live-run evidence is recorded below at release.
- Re-read all eight HLTV match pages below, including the map/veto block, and both day-3 decider pages. Corrected the inherited “BetBoom 2-0” statement: **BetBoom won 2-1**. Map scores below are winner-first.

| Day | Result | Maps | Independently read source |
|---|---|---|---|
| 1 | 9z 2-0 Aurora | Inferno 13-11; Nuke 13-1 | [HLTV 2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) |
| 1 | Falcons 2-0 NIP | Ancient 16-13; Dust2 13-6 | [HLTV 2399385](https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) |
| 1 | Legacy 2-0 PARIVISION | Dust2 13-11; Mirage 16-14 | [HLTV 2399386](https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026) |
| 1 | FURIA 2-0 BetBoom | Ancient 13-10; Mirage 13-9 | [HLTV 2399387](https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026) |
| 2 | Aurora 2-0 NIP | Cache 13-9; Dust2 13-7 | [HLTV 2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) |
| 2 | Falcons 2-1 9z | Nuke 13-9 Falcons; Mirage 13-8 9z; Dust2 13-9 Falcons | [HLTV 2399409](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) |
| 2 | BetBoom 2-1 PARIVISION | Ancient 13-10 PARIVISION; Anubis 13-4 BetBoom; Mirage 13-7 BetBoom | [HLTV 2399410](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026) |
| 2 | FURIA 2-1 Legacy | Cache 13-10 Legacy; Inferno 13-5 FURIA; Mirage 13-8 FURIA | [HLTV 2399411](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026) |

Day 3: [Aurora–9z / Group A decider](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) and [BetBoom–Legacy / Group B decider](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026), both **BO3 LAN**. Exact UTC locks/start times come from Hotspawn JSON epochs, not a rendered HLTV clock with unspecified timezone. Day-3 cards use the current primary model; no second static prediction copy is maintained.

Roster: [HLTV's official-signing report, 8 July](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan) confirms kyxsan completed the Aurora rebuild after Jimpphat and coach ash. This is roughly three months old by TWC, not a fresh stand-in/onboarding edge. The note is now weak/neutral context; no invented penalty or “youngest/most settled system” assertion. Day-2 Aurora 2-0 NIP is explicit counterevidence to a simplistic fade.

## Historical inputs versus current evidence

The day-1 quote pairs and ownership percentages were checked exactly against their stored, pre-lock artifacts, with pinned source paths, SHA-256 and original provider endpoints in [`day1_archive_audit.json`](../hotspawn/research/day1_archive_audit.json). This is **archival reconciliation**, not a fresh read of closed bookmaker markets. The own line/heuristic comparison is retrospective; four matches, and the earlier v2 4/4 in-sample result, do not validate forecasting skill. Frozen day-2 picks are graded only when an actual pre-lock record exists; no Aurora–NIP pick is invented.

Unsupported player ratings, group rank/round-differential, playoff series length, exact rest/travel/health effects and un-rechecked editorial outright prices are omitted or blank. Links remain for manual review, not as proof those facts were verified. Only linked match results and dated official/primary source observations are factual inputs.

## Source and probability safeguards

1. All three Hotspawn surfaces are enumerated and per-page IDs retained; cross-surface identity conflicts mark collection incomplete and withhold that ID's line. Every captured CS2 ID remains in the board, including low-tier, locked, stale, duplicate-looking and unresolved rows. A successful HTTP response alone is not full-slate proof.
2. Hotspawn is fixture/ownership data only. Mutation tests change crowd data without changing win probabilities. Ownership with fewer than ten picks cannot trigger an automatic fade.
3. Quote eligibility checks both teams/aliases, competition family/region/edition, nearest unambiguous kickoff within six hours, explicit whole-match scope, format consistency, finite two-sided prices, usable HTTPS source/read time, active status and read age ≤8 hours. Stale, terminal, mismatched and rematch-ambiguous evidence is rejected visibly, not used with a warning.
4. Non-featured gaps get HLTV attempts first; 403/429 opens a refusal-respecting circuit breaker. Blocked/unattempted entries remain explicitly different from successful reads. Paginated bo3.gg match/line research follows. A named book relay is **secondary** and not called direct-book verification. No mixed-book or unattributed placeholder pair is de-vigged.
5. Ladder: direct Pinnacle → named active esportsbook relay → Polymarket binary price → eligible Valve own line → blank/flagged. Rungs B/C are all listed with their limitations. An exact unsupported tie does not generate an arbitrary team pick.
6. Own-line slope is fitted to **whole-match** Valve W/L results, not maps. No additional BO3 transform. Missing/ambiguous teams, unknown format, known roster mismatch, future or >45-day-old ratings withhold the own-line fallback. Format-specific calibration, veto and fatigue are unmodelled limitations.
7. Last recorded pre-lock predictions freeze on a later refresh, including fixtures which disappear from the latest payload. The site does not pretend to have an observation at the exact lock time.
8. Four-hour schedule `29 */4 * * *`; source-capture artifact, row audit and mandatory real-browser phone/tablet checks gate publication. Conflicted rebases and exhausted pushes fail closed; research flags alone do not block merge/publication. GitHub scheduling/source access remain best effort, with an eight-hour stale warning.

## Scope limitations and reproducible checks

This is a primary-board audit plus a review of the integrated CI repairs. It **does not certify every externally sourced historical statement across hundreds of preserved parallel dashboards**. Alternatives are folded below the one primary executive route and publicly flagged under IR-26. Source/link presence is not a factual verification certificate.

- `python3 hotspawn/model.py && python3 hotspawn/build.py`
- `python3 hotspawn/verify.py && python3 hotspawn/tests.py`
- `python3 -m unittest discover -s tests -v`
- `REQUIRE_BROWSER=1 python3 hotspawn/mobile_check.py` (requires installed Playwright Chromium; browser absence fails)
- The phone test serves real HTTP, checks root plus all eight primary pages at 360/390/768 px, document overflow, a single h1, script errors and ≥44px main navigation/filter targets; captures screenshots as CI artifacts.

## Release checks

Implementation source tests: **50 primary invariants passed locally** before the fresh-scope collector run. A legacy capture without an explicit market-scope field is deliberately rejected rather than silently upgraded; do not publish its temporary rebuild as a new live read. Fresh collector run, final full-suite result, PR, Pages run and deployed snapshot checks will be appended here only after actually observed.

### Pre-integration checks — 16 October, after final factual/UI cleanup

- Fresh strict capture: [Actions38852030376](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38852030376), source `f5ccf3d`, bot `b961350`, Hotspawn reference **04:43:07 UTC**. **95 fixtures / 31 open / 29 picks**, **9A / 18B / 2C / 2D**. B is seven named-book relays plus eleven Polymarket lines. Three source surfaces succeeded with no fixture-identity conflicts; remaining blanks are the two ambiguous-roster gaps, not teams absent from Valve.
- Official Valve snapshot: **380/380 rank/name/points/roster rows, zero mismatches** against a directly retrieved, pinned official file. [Audit and body/blob hashes](../hotspawn/research/vrs_source_audit.json). This does not claim independently re-fetched per-team match histories or today's exact lineups.
- Final local worktree: **60 primary invariants passed; all 424 whole-repository tests passed**. Repaired isolated-module and explicitly unpriced-card test assumptions without inventing probabilities. Unrelated test-only summary/livelines timestamp drift was restored; intended ancillary rebuilds are retained in the earlier CI-fix commit.
- Whole-site local-file/fragment audit: **273 HTML pages / 6,489 local links / zero errors**. This is not a blanket live check of external sources. Every primary table's actual data row also has an HTTPS evidence link; link presence alone does not certify its contents.
- First actual Chromium run: **27/27 cases passed** on `f5ccf3d` at 360/390/768px. Final search/filter/lock-clock improvements postdate that run; the next mandatory browser run will additionally exercise a positive team search, an empty-result search, reset and the S-tier subset. No final-browser pass is claimed yet.
- Independently re-read HLTV's [PARIVISION signing report](https://www.hltv.org/news/45534/parivision-replace-slaxejezzz-with-hobbit), [TWC preview](https://www.hltv.org/news/45688/thunderpick-world-championship-matchups-announced-with-virtuspro-replaced-by-nip) and [Voca–Phantom analytics summary](https://www.hltv.org/betting/analytics/2399424/voca-vs-phantom-elisa-breakout-series-2). Removed unsupported HObbit/player ratings, exact roster totals and EPL placement. Dated arT-return/schedule reports remain weak context, not current-health or numerical fatigue assumptions.
- A Phantom stand-in report is now scoped to the actual Voca fixture. Later RoundsGG/HAVU lineup facts are blank/unverified, not assumed identical; the own line is withheld and no strong stand-in factor is manufactured. NIP's TWC late-invite factor cannot spill into Stake Pulse Beat. [Public IR29/IR30](../hotspawn/flagged.html).
- Historical result rereads retain their known checked date; exact HTTP read clocks that were not retained are blank, not substituted with an editorial edit time. Archival reconciliation timestamps and automatic live quote timestamps remain distinct.
- Phone UI has searchable identities, all/S/B/C/plays filters, periodically updated lock/source-age clocks, a compact executive fallback summary and external sources on strategy rows. A rejected Pages rebuild request now fails the unattended job instead of silently succeeding.

PR, final-browser and live Pages confirmation remain pending below; they will be recorded only after observation.

### Concurrent-main integration and second live proof

[Fresh run38853646824](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38853646824) passed on source3ac755b; bot551b47a records **05:02:02 UTC**, **95/31/29**, **9A/18B/2C/2D** and **27/27 real-browser cases**, including positive/negative team search, reset and exact tier filtering. All underlying snapshots and mobile JSON were inspected, not inferred from a green icon.

[Integration PR161](https://github.com/buffedlizard55-lab/MaltaProj1/pull/161) encountered later main PR158/159/160. Their full contributions are retained: the separate f323b4a7 board remains a clearly labelled alternative, and the new b6f5405d day-2 scorecard is integrated with all six regressions. Primary capture/history retains the later strict source read; no frozen historical record differed. Newer executive inputs were kept, then all dependent views rebuilt. **425 root tests / 66 primary invariants passed; 281 pages / 6,639 local links / zero errors.** The executive workflow now keeps its dependent boards synchronized, so the same stale-snapshot failure is not reintroduced by the next scheduled run. An in-memory test covers both manual-resolution use and later direct-feed precedence even when today's manual-resolution use count is legitimately zero.

The day-2 addition is subsequent to the second browser run; final integration browser and deployment checks still pending.

### Final integrated source/browser/dependency checks — 16 October, 05:15–05:18 UTC

- [Primary run38854794393](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38854794393) **succeeded** on the fully integrated source7df1865, including the new day-2 scorecard: **66 primary invariants and 27/27 mandatory Chromium cases**. The actual committed capture (`c7f288e`) is **05:15:25 UTC**, **95 fixtures / 31 open / 29 picks**, **9A/18B/2C/2D**, with two explicit blank, ambiguous-roster gaps. Inspected the committed board/mobile JSON.
- [Executive/dependency run38854794409](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38854794409) **succeeded**, including live source collection, exact-row checks, mobile clocks, all **83 targeted dependency tests**, both pre-/post-rebase dependent rebuilds, and publication. Resulting combined tip7ff30bb has executive/valuepicks **16/31 named picks with15 explicit blanks** and synchronized console/livelines outputs; a count of16 is not falsely reported as17.
- [Full verify38854796360](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38854796360), [live-source landing38854796253](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38854796253), [canonical assurance38854796318](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38854796318), console, valuepicks and independent coverage checks all succeeded on the integration source. **425 root tests passed again locally after pulling both bots**, not merely before their data updates.
- A normal documentation push re-triggers the final PR checks on the combined tip, since bot-token pushes do not initiate ordinary workflows. Source/interactive-browser evidence above remains applicable: no application source changes in this documentation update.

Deployment is the next gate, not assumed from these branch checks. The actual main merge, Pages build and live route/snapshot receipt will be recorded after they are observed.

### Main merge and actual public-page receipt

PR161 merged as **fddbf9b** at **05:22:40 UTC**; the preserved PR150 head is an ancestor and GitHub auto-marked PR150 merged too. [Main primary run38855456101](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38855456101) succeeded, including its mandatory browser and strict Pages-build request. [Pages run38855576427](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38855576427) succeeded for **3287fd0**; the Pages API reported **built**, not just queued. Actually fetched the public [root](https://buffedlizard55-lab.github.io/MaltaProj1/), [picks](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/picks.html), [TWC](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/twc.html) and [unresolved](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/unresolved.html) pages. They serve the **05:22 UTC fixture read**, 31/29 counts, source-linked picks, day-2/day-3 analysis and two explicit gaps.

The main-only fan-out exposed two legacy publisher failures after their data/row/browser gates had passed: livelines38855456028 and executive38855456040. Their failed publication did not overwrite the last good data. A narrow follow-up now keeps **only executive evidence** in the executive pre-rebase commit, then rebuilds/gates/commits all derived views after pulling other publishers' changes. Livelines retries non-fast-forward pushes up to three times and rebuilds/tests after every pull, refuses actual source/output conflicts, and explicitly requests a main Pages build. Its still-four-hour cron is staggered by20min from the executive collector.

Follow-up also derives the day-1 retrospective own percentage on each model refit, dates fixed16October navigation instead of saying “today/tonight”, distinguishes a service read from a selected fixture quote, and formats two-sided evidence percentages to total100 (e.g.45.5/54.5, not46/55). **427 root tests,68 primary invariants and95/95 source rows passed locally.** These are display/publication safeguards, not new invented evidence or a blanket certification of the alternative boards. Live follow-up workflow/main deployment checks are still required before calling that repair complete.

### Follow-up branch publication gates succeeded

On source681c2e6, all three live publishers now succeeded: [primary38856732353](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38856732353) (**68 primary tests,27/27 required browser cases**), [executive38856732351](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38856732351) (own evidence first, post-rebase derived rebuild/83-test gate and successful push), and [livelines38856732533](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38856732533) (both suites and retry-capable publication). The actual resulting data/mobile JSON and combined bot commits were pulled and inspected; **427 repository tests passed again on that combined output**. [Live-source landing38856736149](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38856736149) also succeeded. Final follow-up PR/main/live confirmation is the remaining release gate, not a request for human approval.

### Completion receipt — main source, publishers and public website verified

[PR164](https://github.com/buffedlizard55-lab/MaltaProj1/pull/164) merged as **ffaaada** at **05:43:48 UTC**. All relevant main jobs succeeded, including the formerly failing publication paths: [primary38857293677](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38857293677), [executive38857293664](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38857293664), [livelines38857293853](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38857293853), [landing/public release38857293841](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38857293841), full verify, console, valuepicks and the source snapshot. No failed data gate was bypassed and no conflicting source edit was forced.

Pulled resulting **main694fe14**, reran **427 repository tests successfully**, and re-audited **281 HTML /6,630 local links /zero errors**. Actual main primary gates passed **68 tests,95/95 fixture rows and27/27 mandatory Chromium cases**. [Pages38857541374](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38857541374) succeeded for694fe14; API status **built**, finished **05:47:05 UTC**. Separately fetched public **root, picks, TWC, unresolved and Flagged**. They serve the **05:44 UTC** source snapshot and the new dated navigation/consistent probability pairs/service-versus-quote wording.

That observed release contains **95 captured rows /31 open /29 picks /2 explicit gaps**, **12A/15B/2C/2D**, not the older9A/18B split. Both day-3 headlines now have direct Pinnacle pairs: **Aurora67% /9z33%; BetBoom35.99% /Legacy64.01%**.9z is an optional differentiation risk, not the likeliest winner or a proved edge; it costs2.38 expected7-point points versus the favourite. The BB/Legacy crowd sample is only7 and does not justify an automatic fade. Prices/counts can change on later automated refreshes; these are the exact values of this receipt, not timeless promises.

Final audit-only clarification: the old IR01/02 numerical coverage/HLTV-UTC attribution was not independently retained. Those exact historical values are now omitted and marked unverified, with the previous record pinned for provenance. This adds no invented fact or probability. The completion follow-up changes only this disclosure/receipt and its generated Flagged page; it is not an alternate prediction model. Main/source/live Pages gates above are actual observations. Later follow-up deployment confirmation is recorded in its PR.

**Handoff:** primary analysis, research ladder, day1/day2/day3 chronology, mobile navigation, blank-plus-flag policy, unattended refresh, publisher repair and integration are complete. No human task claim remains exclusive. Historical/alternative boards remain preserved but not blanket fact-certified; official-row replication does not establish current rosters or out-of-sample forecasting skill.
