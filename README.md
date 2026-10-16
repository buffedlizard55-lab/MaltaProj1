# MaltaProj1 — Hotspawn CS2 picks & research

## Maintained route · integration 16 October 2026

**[Executive summary](https://buffedlizard55-lab.github.io/MaltaProj1/)** → **[all picks & probabilities](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/picks.html)**.
One primary, mobile-first route; every captured CS2 fixture is retained. Supported rows show a pick and both probabilities. Unsupported factual/probability values remain blank, flagged and visible—not forced into a “guaranteed pick”.

| Page | Purpose |
|---|---|
| [TWC day-3 picks & days 1–2 review](hotspawn/twc.html) | Both deciders use the current board; eight verified results/maps, Aurora rebuild timeline, separate expected-points versus optional chasing choices |
| [Leaderboard plan](hotspawn/strategy.html) | Deliberate, disclosed contrarian heuristic—not random underdogs or proven contest optimization |
| [Unresolved & limitations](hotspawn/unresolved.html) | Every unresolved fixture and every non-featured resolution, HLTV → esportsbooks → other lines research trail |
| [Flagged for Review](hotspawn/flagged.html) | Source refusals, mismatches, missing evidence and integration issues |
| [All captured fixtures](hotspawn/all.html) | Open, recently locked and stale payload listings with source links |
| [Method & sources](hotspawn/method.html) | Read times, request hashes, probability ladder and model limits |
| [Verification record](reviews/6b23e38f-verification.md) | What was checked, what was not, external evidence and release checks |

### Automatic refresh and evidence policy

`.github/workflows/hotspawn-22be6967.yml` schedules the maintained board **every four hours**, `29 */4 * * *` (UTC; best effort). It enumerates the three Hotspawn CS2 surfaces; reads direct Pinnacle, Polymarket and official Valve data; attempts HLTV for non-featured gaps then paginated esportsbook relay research. No manual input. Source refusals and absent lines are recorded honestly.

Ladder: **direct Pinnacle → named active esportsbook relay (secondary, not direct-book verified) → Polymarket → eligible Valve own estimate → unresolved**. Team, competition, scope, rematch identity, finite prices and freshness gates precede use. Known roster mismatches, unknown formats and >45-day-old ratings withhold the own fallback. The slope fits whole-match results: **no uncalibrated map-to-series transform**. Hotspawn crowd share is only ownership; it never enters win probability.

Rebuilds, per-row stored-input audits, regression tests and required real-browser phone/tablet checks gate publication. Captures older than eight hours are visibly stale. Research flags do not block publication, but a broken build/site does. All preserved alternatives use separate snapshots/methods and are folded below the primary route; this release does not certify every archived external claim.

### Reproduce / test

```sh
python3 hotspawn/model.py
python3 hotspawn/build.py
python3 hotspawn/verify.py
python3 hotspawn/tests.py
python3 -m unittest discover -s tests -v
# Requires Playwright 1.55.0 + Chromium (installed in the refresh workflow):
REQUIRE_BROWSER=1 python3 hotspawn/mobile_check.py
```

Live collection also needs a clone of Valve's official regional-standings repository (`VRS_REPO_DIR`); the workflow configures this. Rebuilding from a stored capture is not a new external verification. See [COORDINATION.md](COORDINATION.md) for claims, preserved merge work and the final PR/Pages record.

<details>
<summary>Historical integration notes and parallel boards (superseded primary-route claims, preserved for provenance)</summary>

The notes below describe earlier sessions and their own capture times. References to `executive/` or other routes as “primary”, old row counts, old probabilities, and earlier “verified” claims are **not the current maintained policy or a fresh certification**. Use the maintained route and timestamp above. Unrechecked historical facts remain outside this release's verification scope.

# MaltaProj1 — Hotspawn CS2 picks & research

## Start here — a pick for every Hotspawn CS2 match (session `22be6967`, 15 Oct 2026)

| Page | What it is |
|---|---|
| [All picks](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/picks.html) | One phone card per open match: the pick, **both teams' win probabilities**, the basis, sources and read times |
| [Leaderboard plan](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/strategy.html) | Contrarian-but-not-reckless plays (crowd share used only as ownership) + [TWC 2026 day-2 review](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/strategy.html#day2) (frozen pick vs HLTV result, 2/3 and 2/3) + day-1 review + live grading |
| [Unresolved & limitations](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/unresolved.html) | Research ladder HLTV → esportsbooks → betting lines, and the limits on every non-bookmaker pick |
| [Flagged for Review](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/flagged.html) | Irregularities and per-match flags with evidence |
| [Method & sources](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/method.html) | Probability ladder, de-vig, own-line calibration, every request with read time |
| [TWC 2026 day 3 — tonight's deciders](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/strategy.html#day3) | Aurora vs 9z and BetBoom vs Legacy: kickoff in UTC, outside prices, our own line, crowd ownership, the swing play and every source |

How it works: `.github/workflows/hotspawn-22be6967.yml` runs every 4 hours — `hotspawn/collect.py` reads the
`ng-state` TransferState of Hotspawn's `/lobby`, `/cs2-pickems` and `/thp-pickems`, Pinnacle's public guest
JSON, Polymarket's CS2 series and Valve's official standings; `hotspawn/calibrate.py` fits our own line on
Valve's published results; `hotspawn/model.py` applies the ladder (Pinnacle → Polymarket → own line →
unresolved) and the leaderboard rule; `hotspawn/build.py` writes the pages; `hotspawn/tests.py` and a
headless phone check gate publication. Hotspawn crowd percentages are never probability inputs.
Line-by-line verification: [reviews/22be6967-verification.md](reviews/22be6967-verification.md).

**TWC 2026 day 3 (16 October, session `b6f5405d`).** Both deciders are covered ahead of their kickoffs: **Aurora vs 9z**
(14:00 UTC, Hotspawn lock 13:54 UTC, bo3, Group A decider) and **BetBoom vs Legacy** (17:00 UTC, bo3, Group B decider).
Kickoffs are taken from Hotspawn's TransferState epochs and Polymarket's API records, not from rendered clocks — HLTV
renders 10:00/13:00 in the viewer's timezone and EGamersWorld renders 16:00/19:00 in venue time (UTC+2). Outside
prices for the section: bc.game 1.40/2.70 and 1.43/2.76 (Aurora–9z), 2.50/1.48 and 2.52/1.50 (BetBoom–Legacy, relayed
by EGamersWorld) plus Polymarket 0.685/0.315 and 0.605/0.395; our own line comes from Valve's official 2026-10-05
standings (Aurora 1716 vs 9z 1543; Legacy 1931 vs BetBoom 1596). Hotspawn's crowd split (88/13 and 50/50) is shown as
ownership only. Line-by-line verification with source URLs and read times:
[reviews/b6f5405d-verification.md](reviews/b6f5405d-verification.md). Fixtures on a Hotspawn surface that a snapshot
missed are named in the coverage-gap block on the unresolved page and the executive summary instead of being dropped.

- **Published site:** [buffedlizard55-lab.github.io/MaltaProj1](https://buffedlizard55-lab.github.io/MaltaProj1/)
- **Root mobile executive summary:** [landing page](https://buffedlizard55-lab.github.io/MaltaProj1/)
- **Day review & value picks (new):** [every open match with a pick, day-1 review, contrarian watches](https://buffedlizard55-lab.github.io/MaltaProj1/valuepicks/index.html)
- **Unresolved picks & limits (new):** [rows below the top evidence tier, with the reason](https://buffedlizard55-lab.github.io/MaltaProj1/valuepicks/unresolved.html)
- **Strict-evidence executive picks (previous primary):** [executive picks and probabilities](https://buffedlizard55-lab.github.io/MaltaProj1/executive/picks.html)
- **Unresolved research & limitations:** [HLTV → esportsbooks → betting-line fallback](https://buffedlizard55-lab.github.io/MaltaProj1/executive/unresolved.html)
- **Archived 2026-10-14 captured-slate report:** [88 fixtures, including verified historical results and flagged gaps](https://buffedlizard55-lab.github.io/MaltaProj1/fullpicks/index.html)
- **Acceptance/source-link audit:** [review](https://buffedlizard55-lab.github.io/MaltaProj1/reviews/6f9eab3b-acceptance.html)

The root landing page now leads with the every-match `hotspawn/` board (session `22be6967`); the strict-evidence `executive/` snapshot, `valuepicks/` (7759beef) and `leaderboard/` (2e2b2e5e) stay linked as second opinions. The separate newer `livelines/` board is preserved in the archive but is not authoritative until its malformed Valve source links (used by 88 of 89 fixture rows) and 89-versus-88 fixture discrepancy are repaired and rechecked. See the [acceptance review](reviews/6f9eab3b-acceptance.md) for exact URLs, capture times, and the request to its owner.

A mobile-first source-linked dashboard for the public [Hotspawn Pick'em lobby](https://play.hotspawn.com/lobby).
Hotspawn supplies **fixture identity and UTC lock/start epochs only**, never a probability input.

Parallel research from PR #135 is retained at [matchpicks/](matchpicks/index.html) and [its unresolved section](matchpicks/unresolved.html). It is not the primary executive route; see the [source-reliability review](reviews/bb9e05ef-reliability.html) for timestamp and exact-fixture format limitations.

## Day review, guaranteed picks and value watches (session `7759beef`, 15 October 2026)

`valuepicks/` answers the brief's "a pick for every match" requirement without weakening the
evidence rules. Every open fixture in the executive capture carries a pick and a two-sided
probability; the tier that produced the number is printed on the row.

| Page | What it is |
|---|---|
| `valuepicks/index.html` | Phone-first cards for every open match: pick, both probabilities, tier, sources |
| `valuepicks/value.html` | Contrarian value table: outside market vs the project's official-ratings line, gap in points |
| `valuepicks/unresolved.html` | Rows below tier A, the HLTV → esportsbook → own-line ladder, and the limitation on each |
| `valuepicks/coverage.html` | All 80 captured fixtures (open rows picked; locked rows as inventory) |
| `valuepicks/sources.html` / `valuepicks/flagged.html` / `valuepicks/methodology.html` | Source trail with read times, flags, and the exact maths |

Data: `valuepicks/data/board.csv`, `board.json`, `value.csv`, `unresolved.csv`, `coverage.csv`.
Research inputs (one row per fact, with URL, tier and read time): `research/7759beef/sources.json`.
Reproduce with `python3 scripts/7759beef_build.py` then `python3 -m unittest tests.test_7759beef`.
The four-hour workflow `.github/workflows/valuepicks-7759beef.yml` rebuilds and commits the board on
`main` only after the build and the 15 invariants pass.

Day-review finding used by the board: on 14 October 2026, 9z beat Aurora 2-0 (Inferno 13-11, Nuke
13-1) at the Thunderpick World Championship — Aurora's opener at this event following the July rebuild that brought
in kyxsan, Jimpphat and coach ash, and a week after their ESL Pro League bronze. The board applies
that lesson as a rule, not a hunch: take the contrarian side only where the market and the official
ratings disagree, and publish the disagreement with its caveats.

## Current reliability policy (15 October 2026)

The maintained route is **[executive/picks.html](executive/picks.html)**. All captured fixtures remain visible;
unsupported picks have blank probabilities and explicit reasons at **[Unresolved](executive/unresolved.html)**.

- Refresh scheduled every four hours; Actions timing and external source availability are best-effort.
- Require successful lobby **and** CS2 page reads, no identity conflict and a capture ≤8 h old before claiming current full-slate coverage.
- Only fresh (≤8 h), explicitly whole-match, two-sided outside quotes may drive picks. Keep original source times; never use Hotspawn crowd picks.
- Missing ranks/points are **not** worst-rank bounds; missing series formats are **not** BO1. Non-exact VRS identities without renewed proof are withheld.
- Originated probabilities are labelled project estimates, with independent-map assumptions and no claim of outcome calibration.
- [Per-row stored-input audit](executive/data/row_verification.json), [rejected quotes](executive/data/rejected_quotes.json), [live attempt provenance](executive/data/provenance.json), [reliability review](reviews/bb9e05ef-reliability.html).
- `fullpicks/` is pinned to its historical 88-row input from [merge 1d775daf](https://github.com/buffedlizard55-lab/MaltaProj1/commit/1d775daf348e291f851a7d5f34bceb0edd21013e); it no longer claims to refresh live picks. Other historical boards are secondary archives, not independently verified current forecasts.

Run `python executive/build.py`, `python executive/verify_rows.py`, `python executive/tests.py`, and
`python -m unittest discover -s tests -v` for local stored-evidence verification. Live collection runs in GitHub Actions;
this agent sandbox cannot directly reach Hotspawn/HLTV/bookmakers. Chromium checks at 360, 390 and 768 px run in
that workflow; screenshot artifacts are retained there, not in Git.

## Parallel consolidated-board audit (session `228bb5bc`, 2026-10-14)

[`console/`](console/index.html) remains a separate **cross-board audit** with one row for each open CS2 Pick'em
fixture, both team probabilities, the explicit pick, evidence rung, read time, and source URL behind each number.
It is assembled from committed captures by `scripts/228bb5bc_build.py`, rebuilt hourly by
`.github/workflows/console-228bb5bc.yml`, and fails closed on stale inputs, missing sources, or a Hotspawn-sourced
probability. It is retained for comparison and is **not** the primary picks destination. Machine-readable:
`console/data/picks.csv`, `picks.json`, `coverage.json`, `sources.csv`, `flags.csv`.

The root [`index.html`](index.html) is the single mobile-first landing page. This integration leads with the
verified `executive/` board and preserves the prior landing's local destinations in its collapsed archive;
`console/` remains linked as a distinct audit. `console/data/landing_links.csv` and
`tests/test_228bb5bc.py` continue to enforce the earlier console-board link contract.

The line-by-line record for this board is
[`reviews/228bb5bc-verification.md`](reviews/228bb5bc-verification.md): the 28-row table with the source
and verification status of every row, the official-standings anchor audit for the own originated lines
(56 sides: 48 exact, 7 via documented aliases, 1 research), the live re-reads with their arithmetic, and
the five curated manual-review findings (R-228-04..08) that also appear on
[`console/flagged.html`](console/flagged.html). Curated findings live in
`console/data/review_findings.csv` so the generated page cannot drop them.
## Start here — primary executive picks board

**All picks, every open fixture in the selected capture:** [`executive/picks.html`](executive/picks.html) —
one mobile-friendly page with each pick, both team probabilities, evidence basis, row-level source links, and UTC
lock/read times. Its `2026-10-14T05:11:44Z` capture contains 88 fixtures and 28 open-at-capture picks (26
outside-market basis, 2 model basis). “Open” is capture-time status, not a promise that a row is still actionable.
The root page computes current snapshot age, warns after four hours, and marks the capture stale after eight hours.
The picks page can also retain generated relative “in X h” countdowns after those UTC lock times have passed;
treat those labels as stale and use each row’s absolute UTC lock time and source-read time instead.

| Page | What it is |
|---|---|
| [`executive/picks.html`](executive/picks.html) | Primary all-match picks and probabilities, phone-first |
| [`executive/unresolved.html`](executive/unresolved.html) | Research ladder, non-featured routes, rejected prices, and limitations |
| [`executive/own-lines.html`](executive/own-lines.html) | Own-line estimates for matches with no usable outside market |
| [`executive/lines.html`](executive/lines.html) | Outside betting-market observations and read times |
| [`executive/coverage.html`](executive/coverage.html) | Captured Hotspawn fixture inventory and coverage distinctions |
| [`executive/sources.html`](executive/sources.html) | Source trail, refusals, and read times |
| [`executive/methodology.html`](executive/methodology.html) | Probability calculations and source hierarchy |
| [`executive/flagged.html`](executive/flagged.html) | Missing inputs, conflicts, aliases, and model caveats |
| [`executive/data/analysis.csv`](executive/data/analysis.csv) / [`summary.json`](executive/data/summary.json) | Machine-readable rows and timestamped coverage |
| [Line-by-line verification](reviews/e13aca8a-verification.md) / [landing acceptance audit](reviews/6f9eab3b-acceptance.html) | Per-row and integration evidence |

Hotspawn supplies fixture identity and lock times only — crowd-pick percentages are never probability inputs.
Outside market prices take precedence; primary bookmaker prices are de-vigged, and secondary/relayed or prediction-
market prices are labelled as such. Where no usable outside price exists, independently sourced ratings may support
an explicitly labelled own line. Anything unconfirmable stays blank and flagged. See the
[`executive/` methodology](executive/methodology.html) and the two verification records above.

### Parallel four-hour briefing board (separate snapshot)

The [`briefing/`](briefing/index.html) board remains available for comparison; its counts, sources, and capture are
separate from the selected executive snapshot and must not be substituted for it.

| Page | What it is |
|---|---|
| [`briefing/index.html`](briefing/index.html) | Executive summary — every pick on one page, phone-first |
| [`briefing/picks.html`](briefing/picks.html) | The same picks as a table, with the source per row |
| [`briefing/lines.html`](briefing/lines.html) | Outside market lines as read, with the bookmaker's overround |
| [`briefing/own-lines.html`](briefing/own-lines.html) | Our own lines for matches no market prices |
| [`briefing/coverage.html`](briefing/coverage.html) | Fixture inventory with open / locked / stale categories |
| [`briefing/sources.html`](briefing/sources.html) | Every source, what it returned, and when |
| [`briefing/methodology.html`](briefing/methodology.html) | How a pick is chosen |
| [`briefing/flagged.html`](briefing/flagged.html) | Flagged for Review |
| [`briefing/data/picks.csv`](briefing/data/picks.csv) | Machine-readable picks |

### Full-captured-slate board (parallel; not the root open-match source)

[`fullpicks/`](fullpicks/index.html) covers all 88 captured fixtures: 28 open rows with picks and probabilities joined
from the executive capture, 54 played matches with source-verified results beside the original picks, and 6
DraculaN rows left blank and flagged because their pairings could not be verified. It has a separate
[unresolved picks & limitations page](fullpicks/unresolved.html) and an
[88-row machine-readable board](fullpicks/data/fullpicks_board.csv). The 60 stale-result rows are in
[`stale_results.csv`](fullpicks/data/stale_results.csv); the line-by-line review is
[`reviews/c13ca42a-verification.md`](reviews/c13ca42a-verification.md). Its fail-closed workflow
[`.github/workflows/fullpicks-c13ca42a.yml`](.github/workflows/fullpicks-c13ca42a.yml) runs every four hours and
when executive fixture data changes. This board is useful for the complete captured slate, but it is a separate
snapshot and does not replace `executive/picks.html` as the primary open-picks page.

The boards below are parallel or historical work, kept available for review. Their snapshots, counts and model
assumptions are not interchangeable with `executive/`.

## Additional parallel dashboards and data sets

These pages preserve earlier work and independent audit perspectives; none replaces the `executive/` primary
picks link at the top of this README. For example, [`exec/`](exec/index.html) provides a cross-board coverage
audit, [`everypick/`](everypick/index.html) lays out the A–D fallback tier, and [`cs2/`](cs2/index.html) is a
separate line-analysis board. Check each page's own capture time, source links, and flags before comparing it.

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

## Additional full picks board (parallel capture)

**Board:** https://buffedlizard55-lab.github.io/MaltaProj1/picks-full/index.html

This independently built board preserves its own 2026-10-14 capture: picks, two-side win percentages, and an
explicit basis for the open fixtures it saw, including low-tier matches no betting site prices. Its counts and
method are not the root page's selected executive snapshot; compare the source timestamps before using it.

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

## Collection workflows and publication

The selected executive board is built by [`.github/workflows/executive-5545dbb8.yml`](.github/workflows/executive-5545dbb8.yml), scheduled every four hours (inside the requested 4–8 hour window). GitHub Actions schedules are best-effort; the root page computes elapsed time from the saved capture timestamp and reads coverage/source timestamps from `executive/data/summary.json`. Each match also carries its own quote time. The generated [`executive/cadence.html`](executive/cadence.html) page has previously displayed stale elapsed-age and lock-countdown text, so compare its absolute timestamps with the root's computed age rather than relying on those labels.

The separate hourly slate collector below supports other boards; it is not the selected executive snapshot source.

`.github/workflows/slate-180a42a0.yml` runs **hourly** (GitHub's schedule is best-effort), on collector changes,
plus workflow dispatch. It reads `/lobby`, `/cs2-pickems`, `/thp-pickems`, `/lol-pickems`, Pinnacle public guest
moneylines, HLTV's current ranking/listing, and Valve's published standings. No user input or private account
is required. Collection runs on GitHub Actions because this workspace cannot directly reach those source hosts.

A missing required Hotspawn page fails the capture and retains the last published snapshot. Collection,
rendering, regression tests and browser syntax must all pass before committing new data. Failed-run logs are
uploaded as artifacts, not committed over good data. A successful `main` refresh requests a GitHub Pages build.
Those separate slate pages show their own snapshot age and suppress active picks after lock or six-hour staleness; this behavior does not replace the root landing's executive snapshot age check.

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
python3 executive/tests.py
python3 -m unittest tests/test_6f9eab3b.py tests/test_landing_43c32386.py -v
python -m unittest discover -s tests -v
python scripts/audit_91e444dd.py --output /tmp/release-audit.json
python scripts/63ee81ba_build.py          # full picks board (offline, deterministic)
python -m unittest tests/test_63ee81ba.py -v
```

GitHub Pages publishes from `main:/`. See [COORDINATION.md](COORDINATION.md) for maintenance claims, release records, owner handoffs and prior sessions. Previous dashboards and all prior root-link targets are retained in the landing page's collapsed archive; their snapshot counts and model assumptions are not interchangeable with the primary executive board.

Analysis only, not betting advice. Data access/refusals and model limitations are published, not hidden.

</details>
