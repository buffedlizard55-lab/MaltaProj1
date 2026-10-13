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

- 2026-10-13 18:13 UTC: Resolved mid-flight merge conflicts from two other parallel sessions that had pushed additional tournament pages (thunderpick/stake-pulse/cct-europe/elisa-breakout/esl-challenger), own-lines page, additional scripts, and data shards. Kept all their additions alongside our integrated dashboard.
- 2026-10-13 18:13 UTC: PR #9 merged to main. Pages build 1282045331 status "built" (no errors), duration 30.9s, commit 9624f16.
- Live site: https://buffedlizard55-lab.github.io/MaltaProj1/
- PR link: https://github.com/buffedlizard55-lab/MaltaProj1/pull/9
