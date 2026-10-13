# MaltaProj1 — Hotspawn Pick'em betting-line analysis

Live site (GitHub Pages, from `docs/`): https://buffedlizard55-lab.github.io/MaltaProj1/

Independent analysis of the CS2 matches in the Hotspawn Play Pick'em game
(https://play.hotspawn.com/lobby). Probabilities come from **external bookmaker
lines** (EGamersWorld aggregated bookmaker odds, de-vigged) and **our own
HLTV-rank model** — never from Hotspawn's crowd percentages.

- `data/fixtures.csv` — the 26 verified pickable fixtures (Hotspawn + HLTV/EGW cross-refs).
- `data/lines.csv` — external bookmaker match lines (snapshot-stamped) + Thunderpick WC outrights.
- `data/ratings.csv` — HLTV world ranks, every row sourced. Blank = unverified (never inferred).
- `data/matches.csv` — generated analysis table (run `python3 scripts/model.py`).
- `data/tournaments_inventory.csv` — why the lobby filter counts 85 when only 25 are pickable.
- `scripts/model.py` — regenerates `data/matches.csv` (de-vig + Elo-logistic rank model + pick rule).
- `scripts/build_docs.py` — regenerates every page in `docs/` from the CSVs.
- `docs/` — the site: dashboard, per-category pages, methodology, reverse-engineering notes,
  PR audit, **Flagged for Review** (all unverified items published there, non-blocking).

Parallel-session contributions preserved: `site/` (PR #4 dashboard, arena/51fb12f8) and
`hub.html` + `css/ js/ src/ tests/` + `data/matches_hub_2cb6bff4.*` (PR #5, arena/2cb6bff4).
Their data discrepancies are audited in `docs/audit.html`; the canonical dataset is `data/matches.csv`.

Analysis only — not betting advice.
