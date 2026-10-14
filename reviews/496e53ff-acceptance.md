# Independent acceptance audit — published CS2 coverage

**Audit time:** 2026-10-14 02:59 UTC<br>
**Repository state:** `main` at `6007c1760d3dbaae718539d8aedd9c0b37ad9e41` (including PR #90, the new `picks-full/` board).<br>
**Scope:** read-only review of `everypick/`, `cs2/`, `exec/`, the newer `picks-full/` board, their public landing/navigation, source provenance, probability arithmetic, automation history and deployment. This audit changed no owner pages or data.

## Verdict

**The published pages and probability arithmetic pass; cross-board acceptance is conditional.** The root now puts the new full-coverage board first, and the public root, `picks-full/`, `everypick/`, `cs2/`, and `exec/` routes load. The 28-match IDs align, arithmetic is internally sound, mobile/navigation checks pass, and Hotspawn crowd percentages are excluded.

Three material caveats remain:

1. `exec/` was generated before PR #90 and still inventories only five boards. It therefore omits the new primary `picks-full/` board and understates current pick coverage, including for fixture `1079624`.
2. The three winner-direction disagreements between `everypick`/`picks-full` market-led picks and `cs2`'s own VRS line remain unresolved. The executive view surfaces the old three-board disagreements but is not yet a complete audit of the latest site.
3. `picks-full/` publishes a clearly labelled, flagged research estimate for `1079624`, but the linked roster evidence is described as four shared players when the exact HLTV match lineups show three. Three still meets Valve's documented roster-overlap threshold; the mapping is plausible, but the page's `OBVIOUS LOCK` confidence badge and its “VRS LFO 10” source-pill label overstate what the linked source proves.

## Coverage and snapshot comparison

| Surface | Published snapshot / coverage | Acceptance note |
|---|---|---|
| [`everypick/`](../everypick/index.html) | `2026-10-14T02:23:08Z`; 28 open rows; tiers A=5, B=19, C=3, D=1; 27 numeric probability pairs and one intentionally blank pair | Complete directional picks; the Tier-D `1079624` lean is FORZE Reload with no fabricated percentage. Tier B is explicitly an EGW `bc.game` secondary report, not a direct bookmaker read. |
| [`cs2/`](../cs2/index.html) | generated `02:47:24Z`, source capture `02:45:17Z`; 88 rows (28 open, 60 locked/started); 7 market lines, 26 own lines, 27 picks | The market/model fields are separate; `1079624` has no pick or probabilities and is flagged for missing rating/format. Its own-line curve uses `k=0.463` fitted on Valve results and a 2026-10-05 VRS snapshot (nine days old at capture). |
| [`exec/`](../exec/index.html) | data generated `02:48:19Z`; 28 open, 27 picks, 24 priced (7 direct + 17 aggregator), 3 own-line-only, 1 no-basis | The data's five-board inventory is `slate`, `oct14`, `open-slate`, `cs2`, `everypick`; `picks-full/` is absent. Its counts were coherent for that input set, not for the later merged site. |
| [`picks-full/`](../picks-full/index.html) | snapshot `2026-10-14T02:48:00Z`; 28 open, 28 picks, 24 EGW-reported outside lines, 28 own lines (one labelled RESEARCH) | Added by PR #90 after the `exec/` snapshot. It is now the root's primary CTA. Four unpriced rows are model/research-based, and the LFO 10 estimate is explicitly flagged PF-02. |

I independently matched the 28 open fixture IDs across all four datasets: no missing or extra IDs. `cs2/` and `exec/` also retain the 60 locked/started rows in their larger inventories; those rows are not extra open matches.

### Arithmetic and pick direction

- `everypick/`: all 27 numeric pairs sum to 100% within the test tolerance, and every numeric pick is the higher-probability team. The only blank pair is `1079624`, by design.
- `picks-full/`: all 28 pairs sum to 100% and every pick matches the higher published probability, including the explicitly labelled research row. Its 22-test suite checks the devig math, own-line math, format, row sources and research label.
- `cs2/`: the 23 board tests pass; the one unsupported row remains blank instead of inventing a number.
- These are not one model: `cs2/` uses `k=0.463`; `picks-full/` uses `k=0.4568` plus a BO1/BO3 series transform. Market estimates, model lines and the one guided lean should not be averaged together.

### Remaining pick-direction conflicts

| Fixture | `everypick/` and `picks-full/` | `cs2/` | Interpretation |
|---|---|---|---|
| `1079623` — G2 Ares vs The Last Resort | G2 Ares 62.4% (EGW `bc.game`, aggregator-mediated) | The Last Resort 50.9% (own VRS line) | Opposite picks; no direct Pinnacle line in this `cs2/` row. |
| `1080279` — WROTBERRY vs EAC | EAC 54.3% (EGW `bc.game`, aggregator-mediated) | WROTBERRY 60.9% (own VRS line) | Opposite picks; no direct Pinnacle line in this `cs2/` row. |
| `1080285` — Voca vs Phantom | Phantom 51.4% (EGW `bc.game`, aggregator-mediated) | Voca 52.3% (own VRS line) | Opposite picks; a close market/model disagreement, not a settled consensus. |

`picks-full/` and `everypick/` agree on these three because they use the same market direction; `cs2/` follows a different own-line curve. `exec/` still reports these three, but needs to add `picks-full/` before it can be treated as the current all-board comparison.

## Source quality and the no-market case `1079624`

The user-supplied source correction is confirmed: a blank per-fixture `hotspawn_match_url` in the older capture is **not** a missing fixture source. The collector records `hotspawn_pages=lobby,cs2-pickems` and the `/cs2-pickems` fixture source; the exact [HLTV match page 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) is linked by the relevant pick/verification boards. It directly confirms **Best of 3 (Online)**. `picks-full/data/63ee81ba/fixtures.csv` now also has the exact Hotspawn match URL. The earlier `exec` CSV's `best_of_source` is the HLTV match page, so its BO3 provenance is present even though its Hotspawn per-match permalink is blank.

No verified, match-matched outside price was found:

- The current official Valve snapshot, [VRS 2026-10-05, pinned commit `eec4853d`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L89), lists FORZE Reload but has no LFO 10 row. `cs2/` correctly leaves its own line and pick blank.
- `picks-full/` rejects EGW's 1.80/1.80 placeholder and blank opponent, and rejects the Polymarket listing “FORZE Reload vs Sökerorg” because Hotspawn says LFO 10. There is no matched Polymarket series price. HLTV's [match analytics](https://www.hltv.org/betting/analytics/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) yielded no verified current match-specific quote. HLTV's community vote (87.5/12.5 on the page) is not a probability input.
- `everypick/` keeps the Tier-D pick FORZE Reload but leaves both probabilities blank. The `exec/` snapshot has no pick. Since PR #90, `picks-full/` adds FORZE Reload 75.9% / LFO 10 24.1% as **RESEARCH**, not a market price.

The new research line is mechanically reproducible from the pinned VRS row for FORZE (1100) and the roster-mapped Entropy anchor (813), `k=0.4568`, and the match's BO3 transform: map probability 68.02%, series probability 75.9%. The mapping cites [Valve's roster-identity code](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/model/team.js), where `TEAM_OVERLAP_TO_SHARE_ROSTER` is 3. The [HLTV match lineups](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) show LFO 10's five listed players as Jackinho, Sapec, flaw, dottie and tvs; the pinned VRS Entropy roster is dottie, flaw, Sapec, tevsii and Toshas. The shared core is **three**, not the four stated in PF-02; three meets Valve's threshold, so the mapping remains plausible, but the explanation must be corrected.

As an additional guide—not a replacement official input—the [HLTV Valve-ranking page for 2026-10-14](https://www.hltv.org/valve-ranking/teams/2026/october/14) showed FORZE Reload #89 / 1068 points and LFO 10 #169 / 764 points on a fresh re-fetch during this audit. That page labels the table Beta and says it includes unfinished-event matches and secured prize money; its LFO row lists only three players. Applying `picks-full/`'s `k=0.4568` and BO3 transform mechanically to those mirror points would give about 77.1% / 22.9% for FORZE, but that is a sensitivity check only—not an official or published price. The direction supports the existing lean; the point snapshot and roster caveats do not justify an “OBVIOUS LOCK” confidence label for PF-02.

**Source-quality distinction:** the new board's 24 non-placeholder market readings are EGW's `bc.game` feed, read 02:40–02:48Z. They are recent, row-linked aggregator reports, not 24 direct bookmaker responses. Pinnacle was used as a direct cross-check on seven fixtures from the older 01:48Z snapshot. For example, #1080176 is 76.3% Aurora from EGW 3.87/1.20 at 02:48Z, versus a 73.1% Pinnacle cross-check from 3.550/1.307 at 01:48Z; `everypick/` and the later `cs2/` capture carry still different Pinnacle reads. Those are time/source differences, not arithmetic errors. Keep the source and timestamp visible and do not describe aggregator values as direct bookmaker quotes.

## Mobile, internal links and deployment

- `python3 -m unittest discover -s tests -v`: **160 tests passed**. Focused runs also passed: every-pick 5/5; full-picks 22/22; `cs2/tests.py` 23/23; `slate/tests.py` and `node --check slate/dashboard.js` exited successfully. Existing `ResourceWarning`s for unclosed test-file handles were non-fatal.
- `python3 scripts/audit_91e444dd.py`: **183 HTML pages, 0 internal-link errors** (53 separate review findings; these are not broken links). Mobile viewport/navigation checks pass in the relevant suites.
- GitHub Pages API reports `built`; the latest checked Pages deployment, [run 38503815605](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38503815605), succeeded for `6007c17`. Public fetches confirmed the root now leads with `picks-full/` and that the root, `picks-full/`, `everypick/`, `cs2/`, and `exec/` routes load. The root's older observation block still describes the 02:23 snapshot and says odds are not live; the new 02:48 CTA is clearly above it.

## Automation freshness (GitHub Actions run history, checked 02:59Z)

Cron configuration is not proof of a successful scheduled refresh. At 02:59Z, none of the last 50 returned runs for these five workflows had event `schedule`:

| Workflow | Configured schedule | Observed state |
|---|---|---|
| `slate-180a42a0.yml` | hourly at `:41` | Main's latest successful run was push run [38500324242](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38500324242), 02:18Z; payload capture 02:18:56Z. The expected 02:41 slot had no schedule run by 02:59. This is an observable cadence gap, not proof of a permanent cron failure (GitHub schedules can be delayed/dropped). |
| `everypick-fbcccda2.yml` | every 3 hours at `:17` | Main push run [38501839453](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38501839453) succeeded at 02:35Z; snapshot 02:23:08Z. Next slot, 03:17Z, had not arrived. |
| `cs2-a174d77f.yml` | hourly at `:13` | Main push run [38502607814](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38502607814) succeeded and captured 02:45:17Z. Its first post-merge `:13` slot, 03:13Z, had not arrived. |
| `exec-3b5e3fea.yml` | hourly at `:51` | The snapshot remains generated 02:48:19Z. The 02:51 schedule event was absent by 02:59; main push run [38503665600](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38503665600) at 02:56 was not a schedule event and did not add `picks-full/` to the board inventory. |
| `picks-full-63ee81ba.yml` | hourly at `:47` | PR #90 reached main at 02:56Z, after the 02:47 slot; the first post-merge slot is 03:47Z, so scheduled execution was not yet due. The PR/branch checks passed; continue monitoring the first main schedule. |

A separate O-01 own-line model workflow run [38501763317](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38501763317) failed at its test step; failed-log retrieval returned EOF, so the cause is unknown. It is not the successful CS2 board-refresh run and should not be conflated with it.

## Post-audit updates — 03:02–03:11Z

After the 02:59Z snapshot above, PR #92 merged at 03:02:09Z. It adds [`feeds/`](../feeds/index.html) as a **secondary-market data source**, not another picks board, and one root-page card; `picks-full/` remains the primary picks CTA. The new feed capture was generated at 03:02:29Z and covers 25/28 open matches (20 bookmaker quotes relayed by bo3.gg, 15 Polymarket markets, 10 on both); it leaves three rows blank, lists 26 formats, and marks questionable joins/quotes for review.

The post-audit feed confirms `1079624` still has **no matched market**: it flags both the bo3.gg listing and Polymarket listing because each says FORZE Reload vs Sökerorg at the same 17:00Z kickoff, while Hotspawn says FORZE Reload vs LFO 10. See [feed row](https://buffedlizard55-lab.github.io/MaltaProj1/feeds/index.html#f1079624), [flagged join](https://buffedlizard55-lab.github.io/MaltaProj1/feeds/flagged.html#MF-02), [bo3.gg listing](https://bo3.gg/matches/forze-reload-vs-sokerorg-14-10-2026), [Polymarket listing](https://polymarket.com/event/cs2-forzer-skr2-2026-10-14), and the [Hotspawn match](https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624). The new source therefore reinforces—not weakens—the decision to leave the outside probability blank.

For the three direction conflicts, the new feed adds independent secondary corroboration in the `everypick/`/`picks-full/` direction: `1079623` Polymarket 68.5% G2 Ares; `1080279` Thunderpick via bo3.gg 53.8% EAC; `1080285` Thunderpick via bo3.gg 51.4% Phantom and Polymarket 56.0% Phantom (mean 53.7%). These are separate, timestamped sources—not direct bookmaker responses and not values to average into the existing boards' published probabilities. They do not erase the own-line disagreements in `cs2/`.

A fresh public fetch during this update confirmed the root, `/feeds/`, `/picks-full/` and `/exec/` serve the new main content. The root still gives `picks-full/` the primary CTA and links `feeds/` as a source; `exec/` still shows 27/28 picks and omits `picks-full/`. GitHub Pages deployment run [38504189993](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38504189993) completed successfully for `dd6f075`; however, a simultaneous `GET /pages` returned status `errored` even though the public pages loaded. This is a deployment-status discrepancy, not evidence that the pages are unreachable, and should be reconciled by the Pages owner. The feed's first post-merge hourly `:41` run was not yet due at 03:06Z.

### PR #94: new `/every/` board — 03:09–03:11Z

PR #94 merged at 03:09:55Z and added [`every/`](https://buffedlizard55-lab.github.io/MaltaProj1/every/index.html), a separately generated 28/28 picks board. It is **not** the older `everypick/` board and is distinct from `picks-full/`. Its page was generated at 03:08:10Z from the 02:23:08Z fixture snapshot: 7 primary-market lines, 17 aggregator lines, 4 model-only picks and 4 market/model divergences. An independent ID-set comparison confirmed that `/every/` has the same 28 open IDs as the four originally audited pick boards. It follows the market direction on the three original cross-board conflicts and separately flags its model/market divergences. The root now links it as an independent source-verified copy; `picks-full/` remains the prominent CTA.

For #1079624, `/every/` publishes FORZE Reload 95.31% / LFO 10 4.69% as a **MODEL-PICK**, not a market quote. It uses exact-name LFO 10 points from the [HLTV Valve-ranking page dated Oct. 10](https://www.hltv.org/valve-ranking/teams/2026/october/10) (771) against FORZE Reload's Oct. 5 Valve VRS points (1100), plus BO3. Its research file correctly records the three-player core (dottie/flaw/Sapec), says Entropy's 813 points are **not** used, and flags the mixed snapshot, rank drift, former-core mapping and research provenance (E-01-MIXED-SNAPSHOT, E-01-RANK-DRIFT, E-01-FORMER-CORE, E-01-RATED-VIA-RESEARCH). This fixes the earlier four-versus-three roster claim on the new board, but does not fix `picks-full/`'s PF-02 wording or confidence badge.

The new 95.31% output comes from the board's uncalibrated standard Elo-400 slope (`k=1`) and BO3 transform; it is not comparable with `picks-full/`'s 75.9% (`k=0.4568`, the older 813-point Entropy research anchor). As a sensitivity check only, the Oct. 14 HLTV VRS mirror points (FORZE 1068 vs LFO 10 764) mechanically yield about 94.1% with `k=1`, versus 77.1% with `k=0.4568` and the same BO3 transform. The direction is consistently FORZE; the wide range shows that slope/snapshot choice materially drives the number. Keep these as explicitly sourced model/research outputs—not a bookmaker probability—and do not average them.

After PR #94, I re-fetched the root, `/every/`, legacy `/everypick/`, and `/exec/`; the new page and links load, while `exec/` remains at 27/28 picks and still inventories neither `picks-full/` nor `/every/`. Pages build run [38504826038](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38504826038) succeeded for `1c65c97`, the refreshed main Pages API now reports `built`, and the public routes serve the new content. This clears the transient `status: errored` discrepancy reported in the earlier post-audit check.

Final local verification against `1c65c97`: `python3 -m unittest discover -s tests -q` passed **177**; `feeds/tests.py` passed **15**; focused pick-board suites passed **44** total (everypick 5, picks-full 22, `/every/` 17), `cs2/tests.py` **23**, and `slate/tests.py` **17**; `node --check slate/dashboard.js` passed. The repo HTML audit found **190 pages, 0 internal-link errors, 53 review findings**; all five local Markdown links in this report resolve. Existing non-fatal `ResourceWarning`s for unclosed files remain in legacy tests.

## Integration requests (no other-owner files changed)

1. **Executive/coverage owner:** add the post-snapshot `/picks-full/` and `/every/` pick boards as distinct sources to `exec/`'s inventory, source ladder and coverage audit; show `/feeds/` as a secondary-market data source, not another picks board. Refresh the #1079624 row and coverage counts while preserving each estimate's source, capture time, model and flags. At the last public fetch, `exec/` still showed 27/28 picks from its 02:48 snapshot and inventoried neither new picks board.
2. **`picks-full/` owner:** correct PF-02 from four shared players to the verified three; label the linked row as an Entropy research anchor rather than “VRS LFO 10”; and suppress/downgrade the `OBVIOUS LOCK` badge for this flagged research estimate. Preserve the distinct RESEARCH label and market/own-line separation. If the roster mapping or point basis is not accepted, leave the numeric field blank rather than treating the lean as an official probability.
3. **`cs2/` owner:** reconcile the `1079624` `A-NO-FORMAT`/blank-format row with the directly linked HLTV BO3 page already used by the other verification surfaces. The missing Hotspawn per-match permalink is not itself a blocker; the `/cs2-pickems` source and HLTV match source are present.
4. **Slate automation owner:** investigate the absent `:41` schedule event and monitor the first post-merge cron runs for `exec/` and `picks-full/`; keep the visible snapshot age/current-run status honest if GitHub delays or drops scheduled jobs.

These are integration requests only. No owner data, HTML, workflows or generated pages were edited for this audit.