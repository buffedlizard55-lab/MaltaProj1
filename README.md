# MaltaProj1 — Hotspawn Pick'em betting-line analysis

Live site: **https://buffedlizard55-lab.github.io/MaltaProj1/** (GitHub Pages, `main:/`).

Independent, source-linked analysis of the CS2 matches in the [Hotspawn Play Pick'em](https://play.hotspawn.com/lobby).
Probabilities come only from **external bookmaker lines** (EGamersWorld aggregated odds, de-vigged) and
**our own HLTV-rank model** — never from Hotspawn's crowd percentages. Unverifiable values are left
**blank** and published on the **Flagged for Review** page — nothing is inferred.

## Where to look
| Path | What |
|------|------|
| `docs/` | **Canonical verified dashboard** (generated): all 26 pickable fixtures, market win %, own-model %, pick per match, per-row source links, `audit.html` (parallel-PR audit), `flagged.html`, `sources.html`, `methodology.html`, `reverse-engineering.html` |
| `index.html` (root) | Landing hub (links `pickem/`, `docs/`, `lines/analysis.csv`) |
| `pickem/` | Full-slate dashboard for both titles (380 fixtures from the site's own payload) + its own Flagged/Sources/Methodology |
| `data/fixtures.csv` | The 26 pickable fixtures — Hotspawn + payload + HLTV/EGW cross-refs, exact UTC start/lock times |
| `data/lines.csv` | Verified bookmaker match lines (snapshot-stamped) + Thunderpick WC outrights |
| `data/ratings.csv` | HLTV world ranks, every row sourced; blank = unverified |
| `data/matches.csv` | Generated analysis table |
| `assurance/`, `site/`, `hub.html` | Parallel-session dashboards, preserved (see `docs/audit.html` for their data audit) |

## Reproduce
```bash
python3 scripts/model.py        # data/fixtures.csv + lines.csv + ratings.csv -> data/matches.csv
python3 scripts/build_docs.py   # data/*.csv -> every docs/*.html page
```

Analysis only — not betting advice.
