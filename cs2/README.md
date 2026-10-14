# `cs2/` — the Hotspawn CS2 Pick'em board (canonical for this repo)

Session `arena/a174d77f`. Published at <https://buffedlizard55-lab.github.io/MaltaProj1/cs2/>.

One place where **every** CS2 fixture the Hotspawn board currently lists gets (a) both teams' win
probability from **external bookmaker lines**, de-vigged, (b) **our own** originated line from
Valve's Regional Standings, and (c) an explicit pick — with the source of every number linked on
the row. Mobile-first tables; blanks are blanks and are listed on *Flagged for review*.

| Path | What |
|------|------|
| `collect.py` | A1+A2 — reads the public sources (Hotspawn `ng-state` payload, Pinnacle guest responses, EGamersWorld match pages, Valve VRS file, HLTV, Polymarket) and writes `data/capture.json` + `data/provenance.json` + gzip raw evidence in `data/raw/` |
| `calibrate.py` | A3 — re-fits the slope of Valve's own expected-win-rate curve on the match results Valve publishes; `data/calibration.json` |
| `model.py` | strict join (exact team pair + kickoff window + uniqueness), de-vig, own line, pick, flags |
| `build.py` | the pages: board, market lines, own lines, tournaments, full slate, coverage, method, sources, flagged |
| `tests.py` | A6 — the promises the site makes to its reader (see `docs` in the file) |
| `data/` | every table the pages are generated from, plus `summary.json`, `last_run.txt` and per-step logs |

Reproduce offline (needs no network once `data/capture.json` exists):

```bash
VRS_REPO_DIR=/tmp/vrs python3 cs2/calibrate.py   # /tmp/vrs = clone of ValveSoftware/counter-strike_regional_standings
python3 cs2/model.py && python3 cs2/build.py && python3 cs2/tests.py
```

Refresh automation: `.github/workflows/cs2-a174d77f.yml` (hourly + dispatch + push).
Analysis only — not betting advice.

