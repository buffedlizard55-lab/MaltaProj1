# `allpicks/` — every Hotspawn CS2 match, one pick each

Mobile-first board published at
**https://buffedlizard55-lab.github.io/MaltaProj1/allpicks/** (start at `index.html`).

Built by session `arena/5bcfd1b5`. **Do not edit the HTML by hand** — it is generated. Edit the
data or the renderer and rebuild:

```bash
python3 scripts/5bcfd1b5_livecheck.py    # optional: re-read Hotspawn for new/changed fixtures
python3 scripts/5bcfd1b5_build.py        # ratings -> market lines -> own lines -> picks -> flags
python3 scripts/5bcfd1b5_site.py         # render these 11 pages from data/5bcfd1b5/*.csv
python3 -m unittest discover -s tests -p 'test_5bcfd1b5.py' -v
```

Both build steps are offline: they read only committed evidence under `data/5bcfd1b5/`,
`data/8944bb84/` and `cs2/data/`. CI refreshes this directory every 3 hours
(`.github/workflows/allpicks-5bcfd1b5.yml`).

## Pages

| File | What it answers |
|---|---|
| `index.html` | Executive summary: how many matches have a pick, and where the picks are |
| `open.html` | The matches you can still pick in Hotspawn's game — one card each |
| `all.html` | Every fixture Hotspawn lists: open, locked and expired |
| `tiers.html` | The same board grouped by Hotspawn's tier (S / B / C) |
| `tournaments.html` | Grouped by competition |
| `market.html` | Outside bookmaker prices, de-vigged, with overround and read time; plus model-vs-market gaps |
| `own-lines.html` | Our own line per fixture with the Valve standings inputs and the arithmetic |
| `ratings.html` | How every team name resolved to an official Valve row, one line per (name, period) |
| `methodology.html` | Exact rules, the pick hierarchy, and what we refuse to produce |
| `sources.html` | Every source, what was taken from it, and the SHA-256 of the committed Valve bytes |
| `flagged.html` | **Flagged for review**: everything unverified or contradictory, with links |

## Ground rules

* Fixture identity and UTC start/lock times come from Hotspawn. **Nothing else does.**
* Hotspawn's crowd `% picked` and HLTV's "Pick a winner" vote are crowd polls and are never
  probability inputs. The board carries no crowd column at all.
* Every probability comes from an outside bookmaker price or from Valve's official Regional
  Standings, cited to the exact line.
* If a value cannot be confirmed it is **left blank and flagged**. It is never inferred, and there is
  no 50/50 fallback.
* Every table row carries at least one link to the official source of that row's values.

Verification notes and the eleven irregularities raised against `main` are in
`reviews/5bcfd1b5-verification.md`.
