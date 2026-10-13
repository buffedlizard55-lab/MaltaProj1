# MaltaProj1 — Hotspawn Pick'em betting-line analysis

Live site (GitHub Pages, from `docs/`): landing dashboard + category tables.
Start at `docs/index.html` locally, or the Pages URL after deploy.

- `data/matches.csv` — 26 verbatim Hotspawn fixtures (2026-10-13 snapshot) with external/HLTV indicators and OUR originated lines (blank = unverified).
- `data/ratings.csv` — HLTV rank inputs, each sourced. `data/lines.csv` — bookmaker outrights (Thunderpick WC). `data/tournaments_inventory.csv` — all 85 CS2 fixtures by tournament count.
- `scripts/model.py` — reproducible model: `rating=2000-300*log10(rank)`, Elo logistic. Run: `python3 scripts/model.py`.
- `docs/flagged.html` — Flagged for Review (F-01…F-12). `docs/sources.html` — S-01…S-13. `COORDINATION.md` — task board/log.

Hotspawn crowd % is never used as probability. Analysis only, not betting advice.
