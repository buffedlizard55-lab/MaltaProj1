# Coordination board

Updated: 2026-10-13 (UTC)

## Session constraints

- Active owner/session: `3ee8c478-maltaproj1` (Arena branch `arena/3ee8c478-maltaproj1`). This checkout is fixed to that branch; work remains on it.
- No prior coordination file or task claims existed when this board was created.
- Do not treat Hotspawn's picks, displayed probabilities, or any Hotspawn-derived value as match-probability evidence.
- Publish unknown/unverifiable values as blank and flag them; do not infer them.

## Task board

| Task | Status | Owner/session | File scope | Notes |
|---|---|---|---|---|
| Repository review, source policy, data model, website, and final integration | in progress | `3ee8c478-maltaproj1` | `COORDINATION.md`, `README.md`, all new site/app/config/data files | Sole active task. No other claims were present. Research and implementation stay within this task; shared data/navigation are controlled by this integration owner. |
| External-source verification and live-odds availability assessment | in progress | `3ee8c478-maltaproj1` | Source notes and data files created for this site | Three CS2 fixtures have line-by-line checked sources. This is not a claim that every listed match has a sportsbook market. Unknown values stay blank. |
| Build, link, and GitHub Pages deployment verification | in progress | `3ee8c478-maltaproj1` | `.github/workflows/pages.yml`, `site/**`, `scripts/check_site.py`, `tests/**` | Local build/data/link checks pass. Live Actions refresh, PR checks, merge, and Pages deployment still need confirmation. |

## Activity / handoffs

- 2026-10-13: Created this board after confirming that `COORDINATION.md` did not exist. Claimed the sole integration/research task above. No concurrent task owner or file-scope conflict was found.
- 2026-10-13: Inspected the public Hotspawn Pick'ems lobby and category pages. At inspection time, the CS2 page reported 60 matches this week and the League of Legends page reported 126. The page text exposes match-detail links and logo labels, but the checked-in seed remains partial until the automated collector's parsed-card count is reconciled with each source-reported weekly count.
- 2026-10-13: Independently checked Thunderpick's direct CS2 Match Winner pages for 9z Team–Aurora and Astralis–Sashi. Calculated two-way no-vig prices from signed American lines only. No Hotspawn pick percentage entered either calculation.
- 2026-10-13: Checked Polymarket's official Gamma API for the series Match Winner contracts for 9z–Aurora, Astralis–Sashi, and ex-Keyd Stars–Galorys. Kept the exchange prices separate from sportsbook columns and excluded all Map Winner contracts.
- 2026-10-13: Implemented category tables, source/audit pages, odds helpers, conservative Hotspawn/Thunderpick/Polymarket refresh parsers, snapshot validation, and a scheduled GitHub Pages workflow. Local verification: 18 unit tests pass; snapshot and local-link validators pass; JavaScript syntax check passes.
- 2026-10-13: No end-to-end live refresh has been run from this sandbox. Runtime source access, the workflow run, PR status checks, merge, and live Pages deployment remain unconfirmed.

## Sources, verification, irregularities, and release record

### Verified bookmaker lines

- 9z Team vs Aurora, Thunderpick World Championship 2026, 2026-10-14: Thunderpick Match Winner American prices `+280 / -455`; no-vig `24.30% / 75.70%`; overround `8.30%`.
  - Direct market: `https://thunderpick.io/esports/cs2-betting/thunderpick-world-championship-2026/11024/9z-team-vs-aurora/2796376`
  - Tournament context: `https://thunderpick.io/esports/cs2-betting/thunderpick-world-championship-2026/11024`
  - Fixture source: `https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176`
- Astralis vs Sashi Esport, Stake Pulse Beat III, 2026-10-14: Thunderpick Match Winner American prices `-1250 / +530`; no-vig `85.37% / 14.63%`; overround `8.47%`.
  - Direct market: `https://thunderpick.io/esports/cs2-betting/pulse-beat-iii/11173/astralis-vs-sashi/2767822`
  - Tournament context: `https://thunderpick.io/esports/cs2-betting/pulse-beat-iii/11173`
  - Fixture source: `https://www.hotspawn.com/matches/astralis-vs-sashi-stake-pulse-beat-iii-1079438`
- No two-sided sportsbook Match Winner quote was confirmed for ex-Keyd Stars vs Galorys. Bookmaker/no-vig values remain `null`; the separately sourced Polymarket reference is not substituted.

### Verified exchange references (not sportsbook lines)

- 9z–Aurora: Polymarket series Match Winner `25.5¢ / 74.5¢`; official market API `https://gamma-api.polymarket.com/markets?slug=cs2-9z-aur1-2026-10-14`.
- Astralis–Sashi: Polymarket series Match Winner `85.5¢ / 14.5¢`; official market API `https://gamma-api.polymarket.com/markets?slug=cs2-ast10-sashi-2026-10-14`.
- ex-Keyd Stars–Galorys: Polymarket series Match Winner `32.5¢ / 67.5¢`; official market API `https://gamma-api.polymarket.com/markets?slug=cs2-keydst-gls1-2026-10-13`.
- Each event is also linked to its official Polymarket page from the dashboard data. These prices are labelled as exchange references and do not enter the no-vig calculation.

### Irregularities and safeguards

- For the three audited CS2 fixtures, the Hotspawn lobby clock is four hours earlier than the match-detail display. Polymarket event descriptions explicitly identify the lobby-side clock as ET and the API supplies an explicit UTC timestamp (9z–Aurora 08:30 UTC, Astralis–Sashi 10:00 UTC, ex-Keyd–Galorys 21:00 UTC). The seed records preserve the raw Hotspawn label and use UTC only from the explicit API field. This reconciliation is fixture-specific; the refresh never generalizes it to future rows.
- The initial checked-in snapshot is deliberately partial: three audited CS2 fixtures, not the complete Hotspawn lobby. The browser UI labels this state as partial and flags all unavailable values. The automated refresh compares parsed cards with each page's reported weekly count and does not claim complete coverage when they differ.
- Match identity is exact-pair/date and source-link based. The collector accepts only explicit series `Match Winner` contracts/markets. Closed, ambiguous, unmatched, map-winner, or incomplete quotes remain blank.
- No end-to-end refresh has been performed yet. Do not mark source collection or Pages deployment complete until the relevant GitHub Actions run and deployed site are checked.

### Release record

- PR: not opened yet.
- Merge: not performed.
- GitHub Pages deployment: not confirmed.
