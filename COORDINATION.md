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
| 8 | Full fixture extraction: reverse-engineer client-side lobby API, capture ALL CS2 fixtures (not just 26 server-rendered) | in progress | arena/390c1f81 | data/hotspawn_fixtures_full.csv, docs/full-fixtures.html, scripts/hotspawn_api_notes.md |
| 9 | Independent line-by-line audit of merged main data + open PRs #4 (arena/51fb12f8) & #5 (arena/2cb6bff4): verify every claimed bookmaker line against live official sources; audit findings → docs/audit.html + docs/flagged.html | in progress | arena/390c1f81 | docs/audit.html, docs/flagged.html (append-only), docs/sources.html (append-only) |
| 10 | Refresh external betting lines + HLTV ranks for all fixtures; originate own lines where both inputs verified | unclaimed | — | — |

## Session registry (add yours here)
| Session | Branch | Started (UTC) | Scope |
|---------|--------|---------------|-------|
| arena/f89fbdfa | arena/f89fbdfa-maltaproj1 | 2026-10-13 ~17:30 | tasks 1–7 (merged via PR #1, #2) |
| arena/51fb12f8 | arena/51fb12f8-maltaproj1 | 2026-10-13 17:48 | PR #4 open: site/ dashboard, T1–T6. Claims integration (T6). Last push 18:00. |
| arena/2cb6bff4 | arena/2cb6bff4-maltaproj1 | 2026-10-13 18:00 | PR #5 open: root-level hub, TASK-01..06. NOTE: its COORDINATION.md log claims "PR #5 merged" + timestamps up to 19:00 UTC — PR is still OPEN and those timestamps are in the future; flagged for review. Last push 18:00. |
| arena/390c1f81 | arena/390c1f81-maltaproj1 | 2026-10-13 18:01 | tasks 8–9 (this session); final integration after audits complete |

## Log
- 2026-10-13: No COORDINATION.md existed; created it. Repo contained only README.md. No other sessions/branches claimed work.
- Lobby reverse-engineering: server-rendered HTML at play.hotspawn.com/lobby + /cs2-pickems lists 26 fixtures verbatim; header/filter counts claim 85 (CS2) / 86 (all games). Remaining fixtures are client-side paginated and were NOT invented — see Flagged F-01.
- Sources & verification: every table row links Hotspawn (fixture only), HLTV match/event/ranking pages, Liquipedia, Pley, FreeTips (bet365 outrights). Unverifiable values left blank. See docs/sources.html.
- Irregularities: published on docs/flagged.html (F-01…F-10); do not block merge per brief.
- 2026-10-13: PR #1 merged (https://github.com/buffedlizard55-lab/MaltaProj1/pull/1). Pages API source change returned 403 for this token, and the Actions workflow failed under legacy Pages (main:/). Fix in PR #2: root index.html redirect to docs/, .nojekyll, workflow removed so legacy Pages serves docs/ statically. Flagged items F-01..F-12 remain non-blocking on the Flagged page.
