# MaltaProj1: Hotspawn Pick'Em Reverse Engineering & Independent Esports Lines Hub

[![GitHub Pages Deployment](https://img.shields.io/badge/GitHub%20Pages-Live-brightgreen)](https://buffedlizard55-lab.github.io/MaltaProj1/)
[![Verified Matches](https://img.shields.io/badge/Monitored%20Matches-26-blue)](data/matches.json)
[![Originated Lines](https://img.shields.io/badge/Originated%20Lines-100%25-blueviolet)](methodology.html)
[![Flagged for Review](https://img.shields.io/badge/Flagged%20for%20Review-18-amber)](flagged.html)

**Live Dashboard:** [https://buffedlizard55-lab.github.io/MaltaProj1/](https://buffedlizard55-lab.github.io/MaltaProj1/)  
**Primary Target:** Thunderpick World Championship 2026 (Malta LAN - $1,000,000 USD Prize Pool) &amp; Global Active Pick'em Circuits.

---

## 1. Project Overview & Objectives

The goal of this project is to collect, reverse engineer, organize, analyze, and originate independent betting lines for all matches active on Hotspawn's esports prediction platform:
- **Source Platform:** [https://play.hotspawn.com/lobby](https://play.hotspawn.com/lobby)
- **Core Directive:** Do **not** use Hotspawn user pick distributions as match probability indicators. Real-world betting lines are retrieved from established external sportsbooks and prediction markets (Bwin, EGamersWorld, Polymarket, Stake, OddsDigger). Furthermore, independent statistical lines are originated for **all 26 fixtures**.
- **Verification Requirement:** Every row contains verified direct source links to official sites (HLTV, sportsbooks, Hotspawn). If an external sportsbook line has not yet opened or cannot be verified from an official source, it is left strictly blank and flagged for review—**no hallucinations, no guessing**.

---

## 2. Reverse Engineering Hotspawn's Pick'Em Engine

Hotspawn hosts a weekly Pick'em tournament where users predict the winners of CS2 and League of Legends fixtures to compete for weekly prize pools ($400, $200, $100, and $50 Steam Vouchers):

1. **Scoring Mechanism:**
   $$\text{Points} = \text{Base Points} \times \text{Tier Multiplier} \times \text{Streak Multiplier}$$
   - **Tier S:** $\times 3.0$ Multiplier (7 Base Points, e.g. Thunderpick World Championship 2026)
   - **Tier B:** $\times 1.5$ Multiplier (3 Base Points, e.g. Stake Pulse Beat III, CCT Europe 11, ESL Challenger)
   - **Tier C:** $\times 1.0$ Multiplier (2 Base Points, e.g. Elisa BreakOut Series #2)
   - **Streak Multiplier:** Up to $\times 1.25$ for consecutive correct predictions.
2. **Lockout Policy:** Picks lock precisely 5 minutes before scheduled match start times.
3. **Public Sentiment Mispricings:**
   The Hotspawn Pick% metric measures public sentiment, which suffers from severe psychological biases:
   - *Prestige/Brand Bias:* E.g. 91% of Hotspawn players selected Fnatic against HOTU, despite sportsbooks pricing the match as a dead-heat 50/50 pick'em (1.82 / 1.82), and HOTU holding a higher Valve Regional Standing (#34 vs #45).
   - *Inverse Public Consensus:* In ESL SA, 86% of players backed ex-Keyd Stars, whereas professional bookmakers priced Galorys as a 67.1% favorite (1.40 odds).
   - *Overconfidence in BO1 Formats:* In the Elisa BreakOut LAN, the community posted 100% vs 0% sweeps, completely ignoring the high variance inherent in Best-of-One Counter-Strike.

---

## 3. Independent Line Origination Methodology

### A. De-Vigging External Sportsbook Lines
Where verified bookmaker odds $O_1, O_2$ are published, the bookmaker's overround margin is removed proportionally:
$$P_{raw, i} = \frac{1}{O_i}, \quad P_{fair, 1} = \frac{P_{raw, 1}}{P_{raw, 1} + P_{raw, 2}}$$

### B. Statistical Origination Model
Independent win probabilities are originated using a multi-factor logistic Bradley-Terry formulation:
- **Composite Skill Rating:** Weighted blend of HLTV World Ranking points (60%) and Valve Regional Standings (40%).
- **Recent Form Index:** 30-day and 90-day win percentages across official HLTV match logs.
- **Format Modeling:**
  - **BO1 (Single Map):** High-variance baseline model $P_{BO1} = p_{base}$.
  - **BO3 (Series):** Binomial series expansion $P_{BO3} = p_{base}^2 (3 - 2 p_{base})$.
- **Fair Price Generation:** $O_{originated} = \frac{1}{P_{originated}}$.

---

## 4. Monitored Tournaments & Key Findings

| Tournament | Tier | Matches | Key Teams | Analysis Highlights |
|---|---|---|---|---|
| **Thunderpick World Championship 2026** | **Tier S** | 4 | Falcons, FURIA, Legacy, Aurora, NiP, 9z, BetBoom, PARIVISION | Flagship Malta LAN ($1M prize pool). Falcons are overall 2.40 tournament favorites. NiP entered as replacement for VP. |
| **Stake Pulse Beat III** | **Tier B** | 4 | Astralis, Heroic, MIBR, fnatic, HOTU, BC.Game | Astralis heavy 1.07 favorite. Fnatic vs HOTU is a massive +EV opportunity on HOTU. MIBR mispriced by public. |
| **CCT Europe 2026 Series #11** | **Tier B** | 4 | FORZE Reload, G2 Ares, ex-RUSTEC, Gothic, Lavked, mellren | Swiss format online. FORZE Reload and G2 Ares carry heavy public skews. |
| **Elisa BreakOut Series #2** | **Tier C** | 12 | WROTBERRY, ENCE, EAC, BOJONG, Voca, Phantom, HAVU, RoundsGG | Tampere LAN BO1 round-robin. Sportsbook lines pending; originated lines capture single-map upset risks. |
| **ESL Challenger League Season 52** | **Tier B** | 2 | ex-Keyd Stars, Galorys, Zomblers, Overtake Sector | SA & NA regional playoff cups. Extreme public inversions detected. |

---

## 5. Repository Structure

```
MaltaProj1/
├── COORDINATION.md         # Shared task board and multi-session coordination log
├── README.md               # Repository documentation and verification audit
├── index.html              # Main dashboard: Master match table, KPI cards, filters
├── thunderpick.html        # Tier S Malta LAN flagship deep-dive
├── stake-pulse.html        # Stake Pulse Beat III analysis
├── cct-europe.html         # CCT Europe Series 11 analysis
├── elisa-breakout.html     # Elisa BreakOut Series 2 LAN analysis
├── esl-challenger.html     # ESL Challenger League (NA & SA) analysis
├── methodology.html        # Mathematical origination formulation & de-vigging
├── flagged.html            # Flagged for Review page (unverified lines & public skews)
├── css/
│   └── styles.css          # Responsive styling, color palette, dark mode UI
├── js/
│   └── dashboard.js        # Client-side filtering, live search, and sorting
├── data/
│   ├── matches.json        # Structured JSON dataset with all 26 matches
│   ├── matches.csv         # Tabular CSV export of matches and odds
│   ├── lines.csv           # Bookmaker lines inventory
│   ├── ratings.csv         # HLTV and VRS rating inputs
│   └── tournaments_inventory.csv # CS2 tournaments inventory
├── docs/                   # Full mirror of site for Pages compatibility
├── src/
│   ├── originate_lines.py  # Statistical modeling and de-vigging algorithms
│   └── build_site.py       # Static site generation pipeline
└── tests/
    └── audit_site.py       # Automated QA suite: link checker and data integrity
```

---

## 6. Verification and Source Links

All data entries are cross-verified against official portals:
- [HLTV.org Official Match Directory](https://www.hltv.org)
- [HLTV Thunderpick World Championship Event Page](https://www.hltv.org/events/8932/thunderpick-world-championship-2026)
- [Hotspawn Match Portal](https://play.hotspawn.com/lobby)
- [EGamersWorld Esports Odds Database](https://egamersworld.com)
- [Bwin International Sportsbook](https://www.bwin.com/en/sports/cs2-105)
- [Polymarket Esports Prediction Markets](https://polymarket.com/esports/cs2)
