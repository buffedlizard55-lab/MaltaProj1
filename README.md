# MaltaProj1 — Hotspawn Pick'em Analytics

An independent analysis of betting lines for the CS2 matches listed on the [Hotspawn Pick'em lobby](https://play.hotspawn.com/lobby).

## Live site
**[Open the dashboard](https://buffedlizard55-lab.github.io/MaltaProj1/)** (after Pages deploy completes).

## What this is
- Scrapes the Hotspawn lobby for match metadata (tournament, teams, tier, lock time).
- Pulls betting odds from **external, trusted esports odds sources**: HLTV bookmaker aggregate, Polymarket (real-money prediction market), EGamersWorld, vprognoze.
- Removes overround to derive fair implied probabilities per side.
- **Never uses Hotspawn public pick % as a probability input** — that column is shown only to identify where the public crowd differs from the market (potential pick'em value).
- Rows without verifiable external odds are left blank and surfaced on the **Flagged for Review** page.

## Pages
- `/index.html` — full dashboard with filter/search
- `/site/s-tier.html` — S-tier only (Thunderpick World Championship 2026, $1M LAN)
- `/site/b-tier.html` — B-tier (Stake Pulse Beat III, CCT, ESL Challenger cups)
- `/site/c-tier.html` — C-tier (Elisa BreakOut Series, etc.)
- `/site/flagged.html` — all unverified rows and source discrepancies
- `/site/methodology.html` — how probabilities are computed and sources prioritized

## Data
- `/site/data/matches.json` — all match records with odds, implied probabilities, notes, and source URLs.

## Verification policy
- Every non-blank probability cell is backed by a source link in the table.
- Unverified rows are explicitly labeled — we never infer or fill in values.
- Discrepancies between bookmakers/prediction markets are flagged, not averaged away.
- See [Methodology](site/methodology.html) for the full policy.

## Limitations
The Hotspawn lobby is a React SPA. Our static scraper captures the ~26 server-rendered "Closing Soon"/"Upcoming" matches. The remaining ~60 matches (additional CCT/DraculaN/European Pro League/Urban Riga/LoL etc.) load client-side and are not in this first snapshot. They are listed as coverage gaps on the Flagged page, not fabricated.
