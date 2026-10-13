# COORDINATION.md - Shared Task Board

## Final Integration Status

### Session: arena/fe2de00c-maltaproj1
**Status: COMPLETE**
**PR: #6** — https://github.com/buffedlizard55-lab/MaltaProj1/pull/6
**Merged: 2026-10-13**
**Site: https://buffedlizard55-lab.github.io/MaltaProj1/**
**GitHub Pages: Deployed successfully (status: built)**

### Previous Session: arena/f89fbdfa
**PRs: #1, #2** — Merged into main
**Contribution:** Initial lobby extraction, rank model, methodology page, site infrastructure

---

## Task Summary

| Task | Status | Owner | Files | Notes |
|------|--------|-------|-------|-------|
| Data Collection - Hotspawn Match List | DONE | Both sessions | data/matches.json, data/matches.csv | 26 CS2 matches extracted from lobby |
| Data Collection - External Betting Odds | DONE | arena/fe2de00c-maltaproj1 | data/matches.json | Polymarket, Bwin, EGW, vprognoze, Kalshi, etc. |
| Rank Model | DONE | arena/f89fbdfa | scripts/model.py, data/ratings.csv | Elo logistic from HLTV world ranks |
| Site Creation - GitHub Pages | DONE | Both sessions | docs/** | 9 HTML pages, CSS, JS |
| Verification | DONE | arena/fe2de00c-maltaproj1 | docs/*.html | 15 verified, 6 partial, 1 unverified, 4 S-tier triple-verified |
| Integration & Merge | DONE | arena/fe2de00c-maltaproj1 | All | Rebased on main, merged PR #6 |
| GitHub Pages Deploy | DONE | — | — | https://buffedlizard55-lab.github.io/MaltaProj1/ |

## Data Sources Used (with verification)

| Source | Type | Matches Covered | Verification |
|--------|------|----------------|--------------|
| [Polymarket](https://polymarket.com/esports/cs2) | Prediction market | 25 of 26 | Primary source - real money markets |
| [HLTV.org](https://www.hltv.org) | Official data | All 26 | Rankings, VRS forecasts, match pages |
| [Bwin](https://www.bwin.com/en/sports/cs2-105/betting/world-6/thunderpick-world-championship-103887) | Sportsbook | 4 (Thunderpick) | Regulated bookmaker |
| [EGamersWorld](https://egamersworld.com) | Odds aggregator | 8+ | Multiple bookmaker lines |
| [vprognoze.ru](https://vprognoze.ru) | Russian tipsters | 3 (Stake Pulse) | Aggregates bookmaker odds |
| [Kalshi](https://kalshi.com) | Regulated market | 1 (HAVU vs RoundsGG) | CFTC-regulated US market |
| [tips.gg](https://tips.gg) | Tournament predictions | 1 (ESL CL SA) | Tournament-level odds |
| [bo3.gg](https://bo3.gg) | Match data | Referenced | CS2 match data |
| [stavka.tv](https://stavka.tv) | Russian betting | 1 (FURIA vs BetBoom) | Betting odds |
| [freetips.com](https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/) | Betting tips | Thunderpick outrights | Tournament outright odds |

## Key Findings

### Discrepancies (Flagged for Review)
1. **MIBR vs BC.Game** (Stake Pulse Beat III): HLTV VRS gives BC.Game 79.5%, Polymarket gives MIBR 54.9% — largest market-vs-model gap
2. **Voca vs Phantom** (Elisa BreakOut): HLTV VRS gives Voca 69.2%, Polymarket gives Phantom 54.1%
3. **HOTU vs Fnatic** (Stake Pulse Beat III): HLTV VRS gives Fnatic 68.4%, Polymarket sees near-even 52.9%
4. **FORZE Reload vs LFO 10** (CCT Europe S11): Direct odds not independently confirmed
5. **WROTBERRY vs EAC** (Elisa BreakOut): Market and Hotspawn community disagree on favorite

### Hotspawn vs External Market Divergence
- Largest divergence: HOTU vs Fnatic (+39.1% difference between Hotspawn and market)
- Hotspawn community tends toward more extreme convictions
- Market prices matches more evenly than community picks
- 9z vs Aurora: Hotspawn gives 9z only 5% but market gives 29%

## Site Structure

```
https://buffedlizard55-lab.github.io/MaltaProj1/
├── docs/index.html       → Dashboard (overview, stats, key matches)
├── docs/matches.html     → All 26 match lines with odds & sources
├── docs/s-tier.html      → Thunderpick WC detail (both sessions' data)
├── docs/stake.html       → Stake Pulse Beat III detail
├── docs/lower-tiers.html → B/C-tier matches & tournament inventory
├── docs/analysis.html    → Deep analysis with market commentary
├── docs/methodology.html → How numbers are produced (rank model)
├── docs/flagged.html     → 5 flagged discrepancies + missing data
├── docs/sources.html     → All data sources with links
├── docs/style.css        → Dark theme dashboard styling
└── docs/app.js           → Table sort functionality
```

## Irregularities Flagged

| ID | Item | Location | Status |
|----|------|----------|--------|
| F-01 | 59 matches across 11 tournaments have no external odds | Flagged page | Needs review |
| F-02 | CCT Europe S11 lobby filter said 5 matches but only 4 extracted | Lower-tiers page | Minor discrepancy |
| F-03 | Matches with no external line found - values left blank | All pages | By design per protocol |
| F-04 | Falcons vs NiP - NiP HLTV rank unverified for own line | S-tier page | Rank model limitation |
| F-05 | Stake group listings differ between HLTV/Liquipedia | Stake page | Needs review |
| F-06 | Astralis HLTV rank inconsistency (#11 vs #15) | Ratings | Minor - noted |
| F-08 | HOTU vs Fnatic - HLTV indicator differs from rank model | Stake page | Discrepancy flagged |
| F-10 | Hotspawn timezone not stated | Methodology | Minor |

## Pull Request & Merge Record

- **PR #6**: https://github.com/buffedlizard55-lab/MaltaProj1/pull/6
- **Merged**: 2026-10-13 (merge commit)
- **GitHub Pages**: Built and deployed successfully
- **Live URL**: https://buffedlizard55-lab.github.io/MaltaProj1/
