# Independent Odds Board

A lightweight GitHub Pages dashboard for Hotspawn Pick’ems fixtures, checked against independent public esports market sources. The project is a static HTML/CSS/JavaScript site backed by a JSON snapshot; no frontend build step or manual user data entry is required.

## Data rules

- **Hotspawn is fixture scope only.** Its lobby supplies fixture names, competition labels, raw displayed times, and the official match-detail link. Pick selections, crowd shares, displayed percentages, tiers, streaks, and any Hotspawn-derived signal are not read into the odds model and are never used to derive a probability.
- **Sportsbook probabilities come from independent lines.** The refresh checks Thunderpick’s official market pages and accepts only a directly linked, exact-team, exact-calendar-date, two-sided **Match Winner** market with signed American odds. For raw implied probabilities `rA` and `rB`, the displayed no-vig values are `rA / (rA + rB)` and `rB / (rA + rB)`. The raw overround is shown in the data for audit purposes.
- **The exchange is separate.** Active, exact-pair/date Polymarket series **Match Winner** prices may appear as cents per outcome share. They are labeled as exchange references, never described as sportsbook odds, and never included in the sportsbook no-vig calculation. Map-winner contracts are excluded.
- **Unknowns stay blank.** Missing, stale, closed, ambiguous, mismatched, or unparseable values are `null` in the snapshot. The table leaves those numeric cells empty and shows a review flag; it never fills a value by inference.
- **Every fixture row links to Hotspawn’s official match detail page.** Verified sportsbook and exchange prices link directly to their respective official sources as well.

The displayed no-vig probability is a normalized bookmaker price, not a statistical model forecast or betting recommendation. A blank price is not evidence that no market exists anywhere; it means this collector did not verify an eligible quote at refresh time.

## Pages

- `site/index.html` — overview and latest snapshot summary
- `site/cs2/index.html` — Counter-Strike 2 fixtures and market table
- `site/lol/index.html` — League of Legends fixtures and market table
- `site/sources/index.html` — source register, coverage, calculations, and audit notes

## Refresh and deployment

`.github/workflows/pages.yml` runs on pushes to `main`, on a four-hour schedule, and by manual workflow dispatch. It:

1. runs unit, data-contract, and local-link checks;
2. fetches the public Hotspawn CS2 and LoL Pick’ems listings;
3. checks Thunderpick and Polymarket sources conservatively, retaining per-row links and flags;
4. validates the result and publishes the static `site/` directory to GitHub Pages.

A refresh creates the Pages artifact directly and does not push generated data back to a branch. If a public source is temporarily unavailable, the last valid checked-in snapshot can still deploy; the dashboard labels that data as a partial baseline and does not hide missing values. If Hotspawn’s weekly match count and parsed official fixture cards do not agree, the refreshed snapshot is labeled partial and the difference is recorded in the audit log.

The checked-in `site/data/snapshot.json` is a deliberately partial, reviewed seed baseline with three CS2 fixtures from 2026-10-13. It is not represented as the complete current lobby. A successful scheduled/manual refresh replaces the Pages artifact’s snapshot with the fetched fixture set.

## Local checks

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scripts/validate_snapshot.py
python scripts/check_site.py
```

To refresh from public sources locally:

```bash
python scripts/refresh_snapshot.py
```

The scraper does not access authenticated accounts or submit any picks. It fails closed on uncertain fixture matches and market mappings. Source retrieval may depend on the public sites’ availability and markup; coverage and timestamps are visible on the dashboard.

## GitHub Pages setup

The workflow uses GitHub’s Pages deployment actions and requests Pages enablement during deployment. The repository’s Pages source should be set to **GitHub Actions**. The deployed project site is served from the repository’s Pages URL.
