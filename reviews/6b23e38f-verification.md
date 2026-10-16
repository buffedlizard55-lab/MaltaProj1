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
