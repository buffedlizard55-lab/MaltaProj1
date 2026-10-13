# COORDINATION: Shared Task Board & Session Tracking

**Repository:** `buffedlizard55-lab/MaltaProj1`  
**Current Date:** 2026-10-13  
**Active Session ID:** `session-2cb6bff4`  
**Working Branch:** `arena/2cb6bff4-maltaproj1`  
**Target Deployment:** GitHub Pages (`https://buffedlizard55-lab.github.io/MaltaProj1/`)

---

## Task Board

| Task ID | Task Description | Status | Owning Session | Claimed File Scope | Completed Sources / Notes |
|---|---|---|---|---|---|
| **TASK-01** | Reverse engineer `play.hotspawn.com/lobby` and compile all active matches, formats, tiers, and pick distributions | `in progress` | `session-2cb6bff4` | `data/hotspawn_lobby.json`, `data/matches.json` | Captured 26 active Pick'em matches across 5 tournament circuits. |
| **TASK-02** | Collect external betting lines from verified bookmakers (Bwin, EGamersWorld, Polymarket, OddsDigger, HLTV) | `in progress` | `session-2cb6bff4` | `data/betting_lines.json`, `data/sources.json` | Bwin, EGW, Polymarket, HLTV verified bookmaker feeds. |
| **TASK-03** | Originate independent betting lines and win probabilities based on VRS/HLTV ratings, head-to-head, and form | `in progress` | `session-2cb6bff4` | `src/originate_lines.py`, `data/originated_lines.json` | Log-5 / Bradley-Terry rating-based formulation with vig removal. |
| **TASK-04** | Line-by-line verification, official source linking, and irregularity flagging (Flagged for Review) | `in progress` | `session-2cb6bff4` | `flagged.html`, `data/irregularities.json` | Flag unverified lines and high-bias Hotspawn skew matches. |
| **TASK-05** | Build clean, user-friendly GitHub Pages site with landing page dashboard and tournament subpages | `in progress` | `session-2cb6bff4` | `index.html`, `thunderpick.html`, `stake-pulse.html`, `cct-europe.html`, `elisa-breakout.html`, `esl-challenger.html`, `methodology.html`, `flagged.html`, `css/*`, `js/*` | Responsive dashboard, searchable/sortable tables, clean UI. |
| **TASK-06** | Integration, link auditing, PR creation to `main`, auto-merge, and deployment verification | `unclaimed` | `session-2cb6bff4` | Full repository, GitHub Pages deploy | Final integration and verification turn. |

---

## Session Activity Log

### `session-2cb6bff4`
- **2026-10-13 18:00 UTC**: Initialized task board in `COORDINATION.md`. Claimed TASK-01 through TASK-05.
- **2026-10-13 18:05 UTC**: Reverse engineered `play.hotspawn.com/lobby`. Identified 26 active matches across 5 leagues: Thunderpick World Championship 2026 (Malta LAN), Stake Pulse Beat III, CCT Europe 2026 Series #11, ESL Challenger League Season 52 (NA/SA), and Elisa BreakOut Series #2.
