# refresh/ — session `arena/b90700c6` (R-01 / R-02)

Live refresh pipeline for the Hotspawn Play Pick'em line board (`../today/`).

```bash
python3 refresh/collect.py     # public pages -> refresh/data/collected.json + provenance.json
python3 refresh/build.py       # -> current.json / current.csv / odds.csv / ratings.csv
python3 refresh/build_site.py  # -> ../today/*.html (mobile-first, dependency-free)
python3 refresh/verify.py      # row, link, arithmetic and policy checks; fails the run on error
```

`collect.py` needs outbound access to `play.hotspawn.com`, `egamersworld.com`, `hltv.org` and
`api.github.com` (Valve's Regional Standings repository), so it runs in
`.github/workflows/refresh-b90700c6.yml` rather than in the sandbox shell.

Policy: Hotspawn supplies fixture identity and exact UTC lock times only. Its crowd pick
percentages are dropped on ingest — `build.py` refuses to publish a dataset containing them.
Prices come from EGamersWorld's per-bookmaker match-winner table; ratings from HLTV's world
ranking and Valve's official Regional Standings. Anything unreadable stays blank and is flagged.
