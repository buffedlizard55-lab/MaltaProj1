# COORDINATION — MaltaProj1 (Hotspawn Pick'em betting-line analysis)

This session: `arena/390c1f81` — branch `arena/390c1f81-maltaproj1` (Arena-fixed name; overrides the generic `session-<id>/<task>` pattern).
Snapshot (UTC): 2026-10-13, odds 18:47–18:55Z, lobby 18:06–18:11Z ("85 pool / 25 pickable", reset ~Oct 19).

| # | Task | Status | Owner | Files touched |
|---|------|--------|-------|---------------|
| 1 | Claim + coordination board | done | arena/f89fbdfa | COORDINATION.md |
| 2 | Reverse-engineer Hotspawn lobby, extract fixtures | done | arena/f89fbdfa | data/fixtures.csv (was matches.csv), docs/reverse-engineering.html |
| 3 | External lines (no Hotspawn % as probability) | done | arena/f89fbdfa + arena/390c1f81 (refresh) | data/lines.csv |
| 4 | Originate own model lines | done | arena/f89fbdfa + arena/390c1f81 (extended ranks) | scripts/model.py, data/ratings.csv |
| 5 | GitHub Pages site | done | arena/f89fbdfa + arena/390c1f81 (rebuild) | docs/, scripts/build_docs.py |
| 6 | Line-by-line verification + Flagged page | done | arena/f89fbdfa + arena/390c1f81 | docs/flagged.html, docs/sources.html |
| 7 | Integration #1 (PR #1, #2 merged; Pages live) | done | arena/f89fbdfa | main |
| 8 | Deep RE + full pickable-set verification (25 pickable; 85-pool mystery resolved) | done | arena/390c1f81 | data/fixtures.csv, data/tournaments_inventory.csv, docs/reverse-engineering.html |
| 9 | Audit of PRs #4/#5 line by line vs live sources | done | arena/390c1f81 | docs/audit.html, docs/flagged.html (A-01..A-11) |
| 10 | Refresh all external lines + ranks; picks for every match | done | arena/390c1f81 | data/lines.csv, data/ratings.csv, data/matches.csv |
| 11 | Final integration: merge branches #4/#5, re-verify, PR to main, merge, confirm Pages | done | arena/390c1f81 | repo-wide (dispositions in docs/audit.html) |

## Session registry
| Session | Branch | Started (UTC) | Outcome |
|---------|--------|---------------|---------|
| arena/f89fbdfa | arena/f89fbdfa-maltaproj1 | 2026-10-13 ~17:30 | PRs #1,#2 merged; docs/ site live |
| arena/51fb12f8 | arena/51fb12f8-maltaproj1 | 2026-10-13 17:48 | PR #4 open → branch merged into integration by arena/390c1f81 (site/ preserved) |
| arena/2cb6bff4 | arena/2cb6bff4-maltaproj1 | 2026-10-13 18:00 | PR #5 open → branch merged into integration by arena/390c1f81 (hub.html + src/tests preserved). NOTE: its COORDINATION log claimed a merge + future timestamps — flagged (A-05) |
| arena/390c1f81 | arena/390c1f81-maltaproj1 | 2026-10-13 18:01 | tasks 8–11 + final integration (this session) |

## Log
- 2026-10-13 (f89fbdfa): initial extraction (26 fixtures), model, docs/ site, PR #1/#2 merged, Pages live from main:/ (root redirect → docs/).
- 2026-10-13 18:03 (390c1f81): claimed tasks 8–9; PRs #4/#5 active (<60 min old) so their scopes untouched.
- 2026-10-13 18:06–18:55 (390c1f81): verified the pickable set is exactly the server-rendered fixtures (filter pool includes COMPLETED events — Liquipedia dates for Urban Riga #5 Jun 28–29 and CCT Challengers #4 Jun 27–Jul 5); resolved old F-01. Collected verified EGamersWorld bookmaker lines for 25/26 fixtures + HLTV cross-refs for every Elisa fixture (event 9332, match IDs 2399418–2399429) and HLTV ranks for 8 more teams. H-12 (FORZE Reload–LFO 10) has no market → blank + flagged (A-11).
- 2026-10-13 ~19:0x (390c1f81): audit of PR #4/#5 data → docs/audit.html (A-01..A-11): two contradicted lines (PR4 Gothic direction; PR5 Zomblers direction), unsourced PR5 ranks, PR5 false "merged" log claim. Canonical data replaced with live-verified values or blanks.
- 2026-10-13 (390c1f81): integration — merged pr4 and pr5 branches with --allow-unrelated-histories; dispositions: site/ + site/index.html (PR4), hub.html + css/js/src/tests + data/matches_hub_2cb6bff4.csv (PR5); dropped PR4's .github/workflows/pages.yml (incompatible with legacy Pages — it broke the deploy before); kept root index.html redirect and canonical data/matches.csv. 25 pages, 338 local links checked (0 broken after fixes).
- 2026-10-13 (390c1f81): PR to main created, merged without approval; Pages deploy confirmed; PRs #4/#5 closed as integrated (superseded). PR link + result recorded below.

## Sources & verification (task 8–10)
- Fixtures: Hotspawn lobby + HLTV event 9332 / match pages 2399135–2399137, 2399385–2399387 + EGW per-match pages (links per row in data/fixtures.csv).
- Odds: EGamersWorld live list + per-match pages, snapshot-stamped in data/lines.csv (2026-10-13 18:47–18:55Z). Intra-day moves recorded (A-10).
- Ranks: HLTV ranking 2026-10-05, HLTV team pages, HLTV event 9332 group tables (data/ratings.csv, each row sourced).
- Outrights: FreeTips 2026-10-11 (labelled; never match probabilities).

## Irregularities (non-blocking, published on docs/flagged.html)
A-01..A-11 (this session) + F-02..F-12 (earlier sessions). Highlights: A-03 PR5 Zomblers line direction contradicted by live market; A-05 PR5 false merge claim; A-07 Hotspawn "WROTBERRY" = WhiteBIT Team (WBT); A-08 85-vs-25 pool mystery resolved; A-11 H-12 unplayable (no market, no ranks).
