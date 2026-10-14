# Executive board — one pick for every Hotspawn CS2 fixture

Live board: <https://buffedlizard55-lab.github.io/MaltaProj1/executive/>

This session (`arena/5545dbb8`) publishes a mobile-first **executive summary** and a **pick for every
fixture** Hotspawn lists for Counter-Strike 2, including the low-tier matches no bookmaker prices.

| Page | What it answers |
|---|---|
| `index.html` | Executive summary: what is open, how many fixtures have a pick, and links to everything |
| `picks.html` | One row per fixture — pick, both win probabilities, basis, sources, flags |
| `lines.html` | Outside bookmaker prices, overround and de-vigged probabilities, with read times |
| `own-lines.html` | Our own line where no book prices, from the official Valve Regional Standings |
| `tournaments.html` | The same rows grouped by tournament |
| `coverage.html` | What the Hotspawn payload contains, and where its own counts disagree |
| `verification.html` | The checks run on this snapshot and what failed |
| `sources.html` | Source registry plus the full fetch log (URL, status, bytes, SHA-256, UTC minute) |
| `methodology.html` | Selection rules, the basis ladder, and what the board cannot do |
| `flagged.html` | Every row that needs a human: unpriced fixtures, provisional bounds, ambiguities, refusals |

## How a pick is produced

1. **Market · primary book** — the outside bookmaker's own public response (Pinnacle's public guest
   endpoint, the same JSON pinnacle.com's own page loads), de-vigged proportionally.
2. **Market · secondary listing** — prices quoted through a public aggregator (EGamersWorld/bc.game),
   labelled secondary, never passed off as the book's own feed.
3. **Model · official ratings** — both teams' points in Valve's official Regional Standings through the
   relation Valve publish in
   [`model/glicko.js`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/model/glicko.js):
   `p = 1/(1+10^((Rb−Ra)/400))`.
4. **Model · official bound (provisional)** — the answer for low-tier fixtures no book prices: when one
   team is absent from the entire official standings file, the lowest published value in that same file
   is used as its ceiling, and the row is labelled provisional and flagged. Nothing is invented.
0. **No sourced basis** — the row stays blank and carries a flag.

Hotspawn supplies fixture identity, tier, offered points and UTC lock/start epochs only. Its crowd pick
percentages are dropped at ingest, are not stored anywhere in `executive/data/`, and are never a
probability input — the invariant suite fails the build if one appears.

## Automation

`.github/workflows/executive-5545dbb8.yml` runs **hourly** (plus on changes to the files above and on
manual dispatch). It collects, rebuilds, runs the invariant suite and only then commits. A failed
capture keeps the last published snapshot; a source refusal leaves a blank and a flag. On `main` it also
requests a Pages build and verifies the public pages over HTTPS.

## Reproduce locally

```bash
python executive/collect.py --offline   # build from the captures already committed in this repo
python executive/build.py               # render every page from executive/data/
python executive/tests.py               # invariants: sources, arithmetic, no crowd data
python -m unittest tests/test_5545dbb8.py -v
```

`collect.py` without `--offline` reads the live sources and needs general internet access, which the
agent sandbox does not have — so live collection runs on GitHub Actions and the resulting data is
committed here.

Analysis only. Not betting advice.
