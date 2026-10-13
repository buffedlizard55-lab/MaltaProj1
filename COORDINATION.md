# COORDINATION — MaltaProj1 (Hotspawn Pick'em betting-line analysis)

Session ID (this session): `arena/f89fbdfa` — branch fixed by Arena to `arena/f89fbdfa-maltaproj1`
(system constraint overrides the generic `session-<id>/<task>` naming in the task brief; noted here, no other branch created)
Snapshot (UTC): 2026-10-13 (lobby states "60 matches this week", resets in ~5d 06h at fetch time)

| # | Task | Status | Owner | Files touched |
|---|------|--------|-------|---------------|
| 1 | Claim + coordination board | done | arena/f89fbdfa | COORDINATION.md |
| 2 | Reverse-engineer Hotspawn lobby, extract fixtures | done | arena/f89fbdfa | data/matches.csv, docs/matches.html |
| 3 | External lines (HLTV + bookmaker outrights), no Hotspawn % as probability | done | arena/f89fbdfa | data/lines.csv, docs/*.html |
| 4 | Originate own model lines (documented, reproducible) | done | arena/f89fbdfa | scripts/model.py, data/ratings.csv, data/matches.csv |
| 5 | GitHub Pages site (landing + category subpages, tables) | done | arena/f89fbdfa | docs/, .github/workflows/pages.yml |
| 6 | Line-by-line verification + Flagged for Review page | done | arena/f89fbdfa | docs/flagged.html, docs/sources.html |
| 7 | Integration, PR to main, merge, confirm Pages deploy | in progress | arena/f89fbdfa | (integration = this session; no parallel sessions found — repo had only README on main) |

## Log
- 2026-10-13: No COORDINATION.md existed; created it. Repo contained only README.md. No other sessions/branches claimed work.
- Lobby reverse-engineering: server-rendered HTML at play.hotspawn.com/lobby + /cs2-pickems lists 26 fixtures verbatim; header/filter counts claim 85 (CS2) / 86 (all games). Remaining fixtures are client-side paginated and were NOT invented — see Flagged F-01.
- Sources & verification: every table row links Hotspawn (fixture only), HLTV match/event/ranking pages, Liquipedia, Pley, FreeTips (bet365 outrights). Unverifiable values left blank. See docs/sources.html.
- Irregularities: published on docs/flagged.html (F-01…F-10); do not block merge per brief.
- 2026-10-13: PR #1 merged (https://github.com/buffedlizard55-lab/MaltaProj1/pull/1). Pages API source change returned 403 for this token, and the Actions workflow failed under legacy Pages (main:/). Fix in PR #2: root index.html redirect to docs/, .nojekyll, workflow removed so legacy Pages serves docs/ statically. Flagged items F-01..F-12 remain non-blocking on the Flagged page.
