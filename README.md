# Hotspawn · independent CS2 lines

**Site:** https://buffedlizard55-lab.github.io/MaltaProj1/  
**Consolidated picks board (start here):** https://buffedlizard55-lab.github.io/MaltaProj1/console/  
**Flagged for Review:** https://buffedlizard55-lab.github.io/MaltaProj1/console/flagged.html

A mobile-first source-linked dashboard for the public [Hotspawn Pick'em lobby](https://play.hotspawn.com/lobby).
Hotspawn supplies **fixture identity and UTC lock/start epochs only**, never a probability input.

## The consolidated board (session `228bb5bc`, 2026-10-14)

[`console/`](console/index.html) holds **one row for every open CS2 Pick'em match** on the Hotspawn board:
both teams' win probability, the explicit pick, the basis rung (primary book → relayed book → prediction
market → own originated line → research, flagged), the read time and the source URL behind every number.
It is assembled from the committed captures of the boards below — `scripts/228bb5bc_build.py`, rebuilt
hourly by `.github/workflows/console-228bb5bc.yml`, fail-closed on stale inputs, missing sources or a
Hotspawn-sourced probability. Machine-readable: `console/data/picks.csv`, `picks.json`, `coverage.json`,
`sources.csv`, `flags.csv`.

The root [`index.html`](index.html) is the merged landing page (session `43c32386`): one executive summary,
live freshness, categories. This integration added the consolidated-board entry points to it ("All open
matches — one pick per row", the flagged page, capture times), and **every link the page carried before the
restructures still resolves** — `console/data/landing_links.csv` is the registry and
`tests/test_228bb5bc.py` enforces it.

The line-by-line record for this board is
[`reviews/228bb5bc-verification.md`](reviews/228bb5bc-verification.md): the 28-row table with the source
and verification status of every row, the official-standings anchor audit for the own originated lines
(56 sides: 48 exact, 7 via documented aliases, 1 research), the live re-reads with their arithmetic, and
the five curated manual-review findings (R-228-04..08) that also appear on
[`console/flagged.html`](console/flagged.html). Curated findings live in
`console/data/review_findings.csv` so the generated page cannot drop them.

## Current board

**Start here on a phone:** [`exec/`](exec/index.html) — the executive summary and cross-board coverage
audit (session `3b5e3fea`): every open match with its pick, which boards publish a price / own line / pick
for it, every row where two boards name different winners, the source ladder used where no bookmaker prices
a match, and the flags. [`everypick/`](everypick/index.html) gives the A–D fallback tier for all 28 open
matches; [`cs2/`](cs2/index.html) is the hourly line-analysis board.

| Category | Page | Data / verification |
|---|---|---|
| **All picks (executive summary)** | `every/index.html` | **A pick + win probability for every open CS2 Pick'em match** (market lines where they exist, originated HLTV/Valve rating lines for the rest), per-row sources, `every/data/picks.csv` |
| CS2 matches & picks | `slate/cs2.html` | All captured CS2 fixtures; open, locked and stale rows kept separately |
| Tournaments / tiers | `slate/tournaments.html`, `slate/tiers.html` | Source-linked tables, team/tournament search |
| Complete payload inventory | `slate/fixtures.html` | All successfully parsed fixtures, source and capture time on every row |
| Outside markets | `slate/lines.html` | Primary Pinnacle observations vs explicitly **unverified secondary** aggregator reports |
| Our own lines | `slate/own-lines.html` | Provisional, uncalibrated model, with rating-source links and arithmetic |
| Verification & sources | `slate/verified.html`, `slate/sources.html` | Per-row cross-checks plus HTTP status, time, size and SHA-256 |
| Flagged for Review | `slate/flagged.html` | Missing sources/quotes/formats, count disagreements, aliases, model caveats and automation failures |
| Methodology | `slate/methodology.html` | Exact selection rules and limitations |

## Full picks board (every open match)

**Board:** https://buffedlizard55-lab.github.io/MaltaProj1/picks-full/index.html

A pick — with both teams' win % and an explicit basis — for **every** open Hotspawn CS2 Pick'em fixture
(snapshot 2026-10-14: 28 open, Oct 14–16), including low-tier matches no betting site prices.

| Category | Page | Data / verification |
|---|---|---|
| All picks (cards + at-a-glance table) | `picks-full/index.html` | 28/28 picks; market-de-vigged %s where a line exists, else own research line |
| By tier / tournament | `picks-full/s-tier.html`, `b-tier.html`, `c-tier.html`, `tournaments.html` | Same cards, grouped |
| Outside market lines | `picks-full/market-lines.html` | EGW bc.game primary (read 2026-10-14T02:48Z) + Pinnacle & Polymarket cross-checks; 1.80/1.80 placeholders rejected |
| Our own lines | `picks-full/own-lines.html` | Valve VRS 2026-10-05 (calibrated k=0.4568) with BO1/BO3 transform; HLTV 2026-10-12 cross-check; 1 RESEARCH line (PF-02) |
| Methodology / sources / flags | `picks-full/methodology.html`, `sources.html`, `flagged.html` | Formulas, provenance, and all 10 flags with source links |
| Machine-readable | `data/63ee81ba/picks.csv`, `market_lines.csv`, `own_lines.csv`, `fixtures.csv`, `teams.csv`, `flags.csv`, `coverage.json` | Per-row source URLs + capture UTC |

Rules: Hotspawn crowd percentages are **never** an input; unconfirmable values stay blank and flagged;
the single unrated team (LFO 10, PF-02) publishes a roster-mapped line labelled **RESEARCH** only.
`.github/workflows/picks-full-63ee81ba.yml` checks Hotspawn/VRS/market drift hourly and is fail-closed
(a failed check never publishes; the last good board stays live).

### Honest probability labels

- **Market:** `p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)`. This is a calculated market-implied estimate,
  not an official or guaranteed win probability. Only a primary bookmaker quote read during that run, exact or
  evidence-linked names and a known kickoff within 15 minutes can drive the headline market probability.
- **Our model:** HLTV/Valve rating points transformed by a project-assumed 400-point logistic scale.
  This is **not Valve's official forecast formula**, and is not calibrated. Sourced BO1/BO3/BO5 is required for
  series estimates; otherwise the series fields and model-only match pick stay blank. Alias-derived ratings
  are excluded from current model calculations pending review. Map estimates remain research-only.
- **Pick:** primary market favourite preferred; no arbitrary market/model average. With no eligible quote,
  a confirmed-format model-only pick is labelled provisional. Ties and insufficient inputs produce no pick.
- **Unknowns:** blank/`—`, flagged. No invented odds, timestamps, ratings or format assumptions.
  Secondary EGamersWorld reports are not independently verified against the named bookmaker and do not drive
  current headline probabilities. Historical session prices are not carried into current picks.

## Automatic collection & publication

`.github/workflows/slate-180a42a0.yml` runs **hourly** (GitHub's schedule is best-effort), on collector changes,
plus workflow dispatch. It reads `/lobby`, `/cs2-pickems`, `/thp-pickems`, `/lol-pickems`, Pinnacle public guest
moneylines, HLTV's current ranking/listing, and Valve's published standings. No user input or private account
is required. Collection runs on GitHub Actions because this workspace cannot directly reach those source hosts.

A missing required Hotspawn page fails the capture and retains the last published snapshot. Collection,
rendering, regression tests and browser syntax must all pass before committing new data. Failed-run logs are
uploaded as artifacts, not committed over good data. A successful `main` refresh requests a GitHub Pages build.
The browser shows snapshot age and suppresses active picks after lock or six-hour staleness.

Full live coverage and a probability for every match **cannot be guaranteed** when public sources withhold
fixtures, odds or ratings. Payload, rendered-card and header counts can disagree; the site publishes all
successfully parsed rows and flags the discrepancy, rather than asserting that a parse proves authenticated
coverage. There is no silent 50/50 fallback.

## Reproduce / test

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium  # needed only for live collection
python slate/collect.py                # requires public-source network access
python slate/build.py                  # offline render from committed evidence
python slate/tests.py                  # math, matching, freshness, data/provenance tests
node --check slate/dashboard.js
python -m unittest discover -s tests -v
python scripts/audit_91e444dd.py --output /tmp/release-audit.json
python scripts/63ee81ba_build.py          # full picks board (offline, deterministic)
python -m unittest tests/test_63ee81ba.py -v
```

GitHub Pages uses `main:/`. This session works only on `arena/a9a0c2f1-maltaproj1`.
See [COORDINATION.md](COORDINATION.md) for maintenance claims, release records and prior sessions.
Previous dashboards are preserved in the root landing page's **Previous research & parallel boards** section;
their snapshot counts and model assumptions are not interchangeable with the current board.

Analysis only, not betting advice. Data access/refusals and model limitations are published, not hidden.
