# MaltaProj1 — Hotspawn Pick'em Analytics

Independent betting-line analysis for CS2 matches listed on the [Hotspawn Pick'em lobby](https://play.hotspawn.com/lobby).

## Live site
**https://buffedlizard55-lab.github.io/MaltaProj1/** (legacy GitHub Pages serving `main:/`, redirecting to `docs/`).

## What this is
- Extracts match metadata (tournament, teams, tier, lock time) from the Hotspawn lobby.
- Pulls betting odds from **external, trusted esports odds sources** — HLTV bookmaker aggregate, Polymarket real-money prediction markets, EGamersWorld, vprognoze (Marathonbet/Betcity/Melbet/Fonbet), FreeTips.
- Derives fair implied probabilities by removing the bookmaker overround: `P(a) = (1/a) / (1/a + 1/b)`.
- **Never uses Hotspawn public pick % as a probability input.** The public % is shown side-by-side only to surface where the crowd disagrees with the market (potential pick'em value).
- Rows without verifiable external odds are left **blank** and surfaced on the **Flagged for Review** page. Nothing is inferred or made up.

## Pages (all under `docs/`)
- `index.html` — full dashboard with KPI cards, tier/verification/search filters
- `s-tier.html` — S-tier (Thunderpick World Championship 2026, $1M LAN)
- `b-tier.html` — B-tier (Stake Pulse Beat III, CCT, ESL Challenger cups)
- `c-tier.html` — C-tier (Elisa BreakOut Series BO1s, etc.)
- `flagged.html` — unverified rows, source discrepancies, coverage gaps
- `methodology.html` — how probabilities are computed and sources prioritized

## Data
- `docs/data/matches.json` — all match records (26 fixtures) with odds, overround-removed probabilities, notes, source URLs, verification status.
- `data/matches.csv`, `data/lines.csv`, `data/ratings.csv`, `data/tournaments_inventory.csv` — earlier session's CSV exports and rank-based model data (companion reference).
- `scripts/model.py` — earlier session's rank-based model.

## Verification policy
- Every non-blank probability cell links to its source via the Source column.
- Unverified rows are explicitly labeled; we never infer values.
- Source disagreements are flagged, not silently averaged away.
- Local integration test: all HTML pages, CSS, JS, and JSON return HTTP 200; internal links resolve.

## Known limitations
- Hotspawn is a React SPA; ~60 additional fixtures (plus the LoL tab) load client-side and are not enumerated. They are documented as a coverage gap on the Flagged page, not fabricated.
- Odds move. The data is a snapshot at the generated_at timestamp shown on the dashboard.
- BO1 matches have thinner markets than BO3s.

## Not financial / betting advice
Independent informational analysis. Not affiliated with Hotspawn, HLTV, Polymarket, or any bookmaker referenced.
