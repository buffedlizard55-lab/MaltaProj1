# Independent evidence assurance (session 5515fcc9)

This is an additive, independently audited snapshot, not a replacement for another
session's collector or navigation. It does not claim exhaustive or live odds coverage.

- Open `index.html`: official fixture observations, qualified quote-derived lines.
- `flagged.html`: every suppressed match, numerical discrepancies and coverage gaps.
- `sources.html`: publisher roles, direct URLs, retained excerpts and timestamps.
- `methodology.html`: exact calculations, rejection rules and limitations.
- `observations.json`: small, transcribed excerpts of tool responses actually inspected
  on 2026-10-13. These are excerpts, NOT raw response archives or source timestamps.
- `report.json`: machine-readable independent audit of the inherited repository baseline.
- `inherited/`: immutable input copies from reviewed commit `24877877` for reproducible arithmetic audits; these are claims, not verified source facts.
- `source_checks.json`: HTTP accessibility only; never proof that a number is correct.

```sh
python3 assurance/audit.py        # deterministic, offline report + HTML generation
python3 -m unittest discover -s assurance -p 'test_*.py' -v
python3 assurance/check_sources.py # network-only source checks; full internet needed
```

The uniquely scoped Actions workflow runs offline tests/build on changes, and repeats
baseline arithmetic audits and source accessibility checks daily without manual input. Reports are uploaded as Actions
artifacts; it does NOT silently alter fixture/odds datasets or label reachable pages
verified. The public dashboard uses an immutable dated snapshot; its age banner does
not change when HTTP source checks run. A complete inventory and live bookmaker feed
remain owned by the parallel collection sessions recorded in COORDINATION.md.
