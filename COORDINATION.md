# COORDINATION.md — Shared Task Board

## Session Registry
| Session ID | Agent | Start Time | Branch |
|------------|-------|------------|--------|
| arena-51fb12f8 | primary agent | 2026-10-13 | arena/51fb12f8-maltaproj1 |

## Task Board
| Task ID | Task | Status | Owning Session | Files / Scope | Notes |
|---------|------|--------|----------------|---------------|-------|
| T1 | Scrape Hotspawn lobby for full match list | done | arena-51fb12f8 | site/data/matches.json | 26 server-rendered matches captured (Closing Soon + Upcoming); ~60 remaining load client-side and are documented as coverage gaps on Flagged page |
| T2 | Collect external betting odds from HLTV & verified esports books | done | arena-51fb12f8 | site/data/matches.json | Sources: HLTV, Polymarket, EGamersWorld, vprognoze. Hotspawn % NEVER used as probability. |
| T3 | Compute fair probabilities from betting lines | done | arena-51fb12f8 | site/data/matches.json | Removed overround (P = (1/odds)/Σ(1/odds)). Rows without confirmed odds left blank. |
| T4 | Build GitHub Pages dashboard site | done | arena-51fb12f8 | index.html, site/*.html, site/css/, site/js/ | 6 pages: dashboard, S/B/C tier views, Flagged, Methodology. Dark dashboard theme, filter/search controls. |
| T5 | Line-by-line verification + source links | done | arena-51fb12f8 | all pages | Each non-blank row has source_url linking to official page. Unverified rows (9) are blank & flagged. Discrepancies (7) are flagged. |
| T6 | PR, merge, deploy to GitHub Pages | in progress | arena-51fb12f8 | PR to main, .github/workflows/pages.yml | Integration session: verifying build, Pages config, then merge. |

## Log
- 2026-10-13 17:48 UTC: Session arena-51fb12f8 started. Claimed T1-T5.
- 2026-10-13 17:50 UTC: Scraped server-rendered Hotspawn lobby (26 matches visible). Could not access JS-loaded portion of lobby via curl due to TLS/JS rendering; documented as coverage gap.
- 2026-10-13 17:50-17:56 UTC: Gathered odds from HLTV, Polymarket, EGamersWorld, vprognoze for listed matches.
- 2026-10-13 17:56-17:58 UTC: Built site (dashboard, tier pages, Flagged, Methodology), computed overround-removed probabilities, linked source URLs.
- 2026-10-13 17:58 UTC: Tested with local http.server; all pages return 200, JSON loads correctly.

## Source Links
(To be filled per match row during T5.)

## Flagged Irregularities
(To be listed here and on Flagged for Review page.)

## Handoff Log
- (none yet)
