# MaltaProj1 - CS2 Betting Analysis Dashboard

Independent betting line analysis for CS2 matches listed on [Hotspawn Pick'em](https://play.hotspawn.com/lobby).

## Overview

This project collects, organizes, and analyzes CS2 match data from the Hotspawn pick'em game lobby. All betting probabilities are derived from **external betting markets only** — Hotspawn community picks are never used as an input for probability estimates.

## Live Site

👉 **[View the Dashboard](https://buffedlizard55-lab.github.io/MaltaProj1/)**

## Contents

- **Dashboard** — Overview of key matches, statistics, and value opportunities
- **Match Lines** — Complete table of all 26 matches with betting odds and implied probabilities
- **Analysis** — In-depth breakdown of each tournament with market commentary
- **Flagged for Review** — Discrepancies, unverified data, and missing odds
- **Sources** — Full list of data sources with links for manual verification

## Data Sources

All odds and probabilities sourced from:
- [Polymarket](https://polymarket.com/esports/cs2) — Primary prediction market
- [HLTV.org](https://www.hltv.org) — Match data, VRS rankings, team stats
- [Bwin](https://www.bwin.com) — Sportsbook odds
- [EGamersWorld](https://egamersworld.com) — Odds aggregator
- [vprognoze.ru](https://vprognoze.ru) — Betting odds
- [Kalshi](https://kalshi.com) — Regulated prediction market
- [bo3.gg](https://bo3.gg) — CS2 match data
- [tips.gg](https://tips.gg) — Tournament predictions
- And others (see Sources page for full list)

## Verification

Every data point is verified against external sources. Values that cannot be confirmed are left blank and flagged on the Flagged for Review page. No values are inferred from Hotspawn data.

## Structure

```
├── docs/               # GitHub Pages site
│   ├── index.html      # Dashboard
│   ├── matches.html    # All match lines
│   ├── analysis.html   # Betting analysis
│   ├── flagged.html    # Items needing review
│   ├── sources.html    # Data sources
│   ├── style.css       # Styles
│   └── app.js          # Interactive features
├── data/
│   └── matches.json    # Raw match data with odds
└── COORDINATION.md     # Task coordination
```
