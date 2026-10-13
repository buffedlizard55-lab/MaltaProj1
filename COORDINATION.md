# COORDINATION — MaltaProj1 (Hotspawn Pick'em betting-line analysis)

## Sessions
| Session | Branch | Status |
|---------|--------|--------|
| arena/f89fbdfa | (merged to main via PRs #1, #2) | Completed initial build (26 fixtures, rank model, docs/ site) |
| arena/51fb12f8 | arena/51fb12f8-maltaproj1 | Final integration session — enriched odds, rebuilt dashboard, verified Pages |

Snapshot (UTC): 2026-10-13

| # | Task | Status | Owner | Files touched |
|---|------|--------|-------|---------------|
| 1 | Scrape Hotspawn lobby | done | arena/f89fbdfa + arena/51fb12f8 | data/matches.csv, docs/data/matches.json — 26 server-rendered fixtures |
| 2 | External odds from HLTV + verified books | done (enriched) | arena/51fb12f8 | docs/data/matches.json — added Polymarket, EGW, vprognoze lines for 17 of 26 matches |
| 3 | Originate own fair probabilities (overround-removed) | done | arena/51fb12f8 | docs/data/matches.json — P = (1/odds) / Σ(1/odds); Hotspawn public % never used |
| 4 | Rank-based model (companion) | done | arena/f89fbdfa | scripts/model.py, data/ratings.csv |
| 5 | GitHub Pages site (landing + subpages + tables) | done (rebuilt) | arena/51fb12f8 | docs/ (dashboard, S/B/C tier pages, Flagged, Methodology); dark responsive UI; filters/search; KPI cards |
| 6 | Line-by-line verification + source links | done | arena/51fb12f8 | every non-blank row has source_url; 9 unverified rows left blank and flagged; 7 source-discrepancy rows flagged |
| 7 | Integration → PR → merge → confirm Pages deploy | in progress | arena/51fb12f8 | PR to main; verify Pages build |

## Log
- 2026-10-13 ~17:45 UTC: arena/f89fbdfa completed initial work; PR #1, #2 merged; legacy GitHub Pages serving main:/ (redirect index.html → docs/) deployed successfully (build 1282041653, status "built").
- 2026-10-13 ~18:00 UTC: arena/51fb12f8 reset to origin/main (to avoid merge conflicts with already-merged work), then integrated by:
  - Replacing docs/ site with enhanced dashboard (filter/search, probability bars, per-row source links, KPI cards, S/B/C tier pages, Flagged page, Methodology page).
  - Enriching the match dataset to 26 fixtures with 17 having verified external odds from Polymarket, EGamersWorld, vprognoze (Marathonbet/Betcity/Melbet/Fonbet), HLTV, FreeTips.
  - Computing fair (overround-removed) probabilities for every match with odds.
  - Leaving 9 B/C-tier matches with no verifiable external odds BLANK, flagged UNVERIFIED (no inference).
  - Flagging 7 matches with bookmaker disagreement ≥10pp (H-01, H-03, H-06, H-09, H-14, H-15, H-21) on the Flagged page.
  - Keeping the other session's data/*.csv, scripts/model.py, and root index.html redirect intact.
  - Removing the Actions workflow since legacy Pages (main:/ → docs/) is already configured and working; adding .nojekyll in docs/.
- 2026-10-13 18:08 UTC: Local http.server integration test: all 11 page/asset URLs return HTTP 200; all internal hrefs between pages resolve.

## Sources per verified row (in docs/data/matches.json `source_url`)
- https://polymarket.com/esports/cs2
- https://www.hltv.org/events/8932/thunderpick-world-championship-2026
- https://www.hltv.org/events/9223/stake-pulse-beat-iii
- https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii
- https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii
- https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii
- https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026
- https://www.hltv.org/matches/2399424/voca-vs-phantom-elisa-breakout-series-2
- https://egamersworld.com/counterstrike/matches

## Flagged irregularities (also rendered on docs/flagged.html)
- F-COV: Hotspawn lobby advertises 86 total matches (60 this week, CS2 + LoL). Static scrape captured 26 server-rendered fixtures; the remaining ~60 load client-side via React and are NOT fabricated. LoL tab is also not enumerated.
- F-NOLINE (9 matches: H-10, H-12, H-13, H-16, H-19, H-22, H-26 plus 2 others): no verifiable external odds found at scrape time; probabilities left blank.
- F-DISPUTE (H-01 ex-Keyd/Galorys): Books sharply disagree — Polymarket Galorys 1.47 favorite, vprognoze Galorys ~1.43–1.70, stavka.tv ex-Keyd 1.20 favorite. Used Polymarket; flagged.
- F-DISPUTE (H-03 Gothic/Lavked): Market leans Gothic while Hotspawn public leans Lavked 88%.
- F-DISPUTE (H-06 HOTU/fnatic): Near coinflip at Marathonbet (1.87/1.84); HLTV widget shows 31.6/68.4 fnatic; Hotspawn public 10/90 — crowd overrates fnatic.
- F-DISPUTE (H-09 Legacy/PARIVISION): Polymarket/EGW lean Legacy; HLTV widget leans PARIVISION at capture.
- F-DISPUTE (H-14 MIBR/BC.Game): Books split — HLTV widget strong BC.Game; Polymarket near-even; EGW MIBR favorite. VRS ranks MIBR #13 vs BC.Game #47 favoring MIBR, conflicting with some lines.
- F-DISPUTE (H-15 Heroic/Envy): Polymarket Heroic favorite; HLTV widget Envy favorite.
- F-DISPUTE (H-21 Voca/Phantom): Polymarket Phantom heavy favorite (1.03); HLTV widget 69.2/30.8 Voca.
- F-LIQUIDITY: Several B/C-tier BO1 markets have low volume and possible stale odds (H-02, H-07, H-18, H-24).


## Independent assurance session — arena/5515fcc9 (2026-10-13)

| Task | Status | Owner | Exclusive file scope |
|---|---|---|---|
| A5515: independently audit existing published CSV/model/source claims, publish evidence-backed dashboard and flags, automate official-source reachability checks | in progress | arena/5515fcc9 | `assurance/**`, `.github/workflows/assurance-5515.yml` |

- Read the root board and every available remote session board before claiming. Existing root navigation, `docs/**`, CSVs, collector/pipeline/inventory/lines and other sessions' assets remain untouched. This session uses its Arena-fixed branch `arena/5515fcc9-maltaproj1`; it does not switch branches.
- Coordination discrepancy: session 2cb6bff4's remote log reports PR #5 merged; GitHub currently reports PR #5 OPEN. Do not accept task-board release claims as deployment evidence.
- Integration request to existing navigation owners: link `assurance/index.html` (Independent verification) after this session's PR is merged. Do not duplicate or overwrite existing navigation scopes.
- Scope is independent assurance, not a takeover of any active collection/integration task. Sources and results will be recorded below and on `assurance/flagged.html`. No source value is newly marked verified without retained direct evidence.

- Initial claim rebase encountered a concurrent COORDINATION.md update from PR #6. Retained the complete main board and appended this isolated claim; no other work discarded.

### Assurance findings and integration requests — arena/5515fcc9
- Independently inspected all three text chunks of the [official lobby](https://play.hotspawn.com/lobby), CS2 facet, five official Polymarket competition listings, and four direct series moneyline pages. Small transcribed excerpts and observer access window are in `assurance/observations.json`; unknown source quotation times and UTC fixture times remain null.
- Direct primary-moneyline pages: [ex-Keyd/Galorys](https://polymarket.com/esports/cs2/esl-challenger-league/cs2-keydst-gls1-2026-10-13), [HOTU/fnatic](https://polymarket.com/esports/cs2/stake-pulse/cs2-hotu-fnc-2026-10-14), [Legacy/PARIVISION](https://polymarket.com/esports/cs2/thunderpick-world-championship/cs2-lgc-prv-2026-10-14), [Heroic/Envy](https://polymarket.com/esports/cs2/stake-pulse/cs2-hero-envy-2026-10-15). These support historical price-normalized calculations, NOT calibrated win forecasts or bookmaker prices.
- [bwin official competition](https://www.bwin.com/en/sports/cs2-105/betting/world-6/thunderpick-world-championship-103887) fetched text contains no numeric event odds; no direct bookmaker pairs confirmed by this audit. Third-party / other-session claims are not promoted to verified.
- **Request to data/site owners:** investigate inherited `data/matches.json` row 25 (1.10 belongs to Voca in its own note, but is stored under RoundsGG), row 12 (official market observed is FORZE vs Sökerorg, not LFO 10), unsupported `Z` timestamps, raw inverse-odds percentages mislabeled as match likelihoods, and `data/lines.csv`'s eight no-vig calculations (denominator from recorded prices = 1.327256019; every stored normalized percentage disagrees). Do not use outrights for match-win probabilities. These findings are published on `assurance/flagged.html` and are non-blocking needs-review items.
- Existing `scripts/model.py` is rank-only with arbitrary unfitted parameters and incompatible date inputs; reproducible arithmetic is not predictive calibration. Official ranking URL: https://www.hltv.org/ranking/teams/2026/october/5. No new ranking value marked verified by this session.
- Independent site: eight pages, 26 inspected cards, four qualified historical quote pairs, 22 suppressed rows, 32 review findings. Automated tests cover source links on every data row, internal links/anchors, output normalization, explicit reversed outcomes, alias/date/competition/zero-volume/conflict gates, invalid inputs, null timezones and rejection of Hotspawn-derived probability inputs. All 21 tests pass.
- Retained immutable baseline copies under `assurance/inherited/` correspond to reviewed main commit `24877877d2395b151722f937c3f8adc106b02850`; future checks cannot silently relabel another session's updated data verified.
- Automation is explicitly scoped: daily independent baseline audit + HTTP accessibility report (not full collection). The published snapshot never claims to be a live or exhaustive feed. Full inventory/live-odds collectors remain owned by active parallel sessions.
- Rebased against concurrent integration merges (including PR #7); a COORDINATION.md conflict was resolved by preserving the entire latest main board and appending this session's claim/log. No shared site/data files changed by this session. Rebase necessarily rewrites our already-pushed commits; push uses explicit session branch with force-with-lease after pulling that branch.
- First two audit workflow runs succeeded: https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38444565505 and https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38444596625. Artifact download redirects to an Azure host outside shell egress; adding a read-accessible GitHub check report avoids that access limitation without changing anyone's branch or inventing check results.
- Remote CI for PR #11 passed (22 tests): https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38444968076. Source-check run https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38444960606 checked 34 URLs: 33 HTTP 200, one HTTP 403 (bwin); all numerical_verification fields remain false. Exact JSON recovered through the GitHub Checks API and saved in `assurance/source_checks.json`; no odds or freshness status changed.
- PR opened: https://github.com/buffedlizard55-lab/MaltaProj1/pull/11. Main changed concurrently again (including PR #9), so synchronization and coordination-only conflict resolution are required before merge. Existing main code/data are preserved.
