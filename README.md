# Hotspawn · independent CS2 lines

**Site:** https://buffedlizard55-lab.github.io/MaltaProj1/  
**Current CS2 board:** https://buffedlizard55-lab.github.io/MaltaProj1/slate/cs2.html

A mobile-first source-linked dashboard for the public [Hotspawn Pick'em lobby](https://play.hotspawn.com/lobby).
Hotspawn supplies **fixture identity and UTC lock/start epochs only**, never a probability input.

## Current board

| Category | Page | Data / verification |
|---|---|---|
| CS2 matches & picks | `slate/cs2.html` | All captured CS2 fixtures; open, locked and stale rows kept separately |
| Tournaments / tiers | `slate/tournaments.html`, `slate/tiers.html` | Source-linked tables, team/tournament search |
| Complete payload inventory | `slate/fixtures.html` | All successfully parsed fixtures, source and capture time on every row |
| Outside markets | `slate/lines.html` | Primary Pinnacle observations vs explicitly **unverified secondary** aggregator reports |
| Our own lines | `slate/own-lines.html` | Provisional, uncalibrated model, with rating-source links and arithmetic |
| Verification & sources | `slate/verified.html`, `slate/sources.html` | Per-row cross-checks plus HTTP status, time, size and SHA-256 |
| Flagged for Review | `slate/flagged.html` | Missing sources/quotes/formats, count disagreements, aliases, model caveats and automation failures |
| Methodology | `slate/methodology.html` | Exact selection rules and limitations |

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
```

GitHub Pages uses `main:/`. This session works only on `arena/a9a0c2f1-maltaproj1`.
See [COORDINATION.md](COORDINATION.md) for maintenance claims, release records and prior sessions.
Previous dashboards are preserved in the root landing page's **Previous research & parallel boards** section;
their snapshot counts and model assumptions are not interchangeable with the current board.

Analysis only, not betting advice. Data access/refusals and model limitations are published, not hidden.
