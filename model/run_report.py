#!/usr/bin/env python3
"""Print a Markdown summary of the current own-line model inputs and output.

Used by `.github/workflows/model-91eff436.yml` (step "Freshness report") to append a short,
verifiable statement of what the run read and what it published to the job summary, so anyone can
see the snapshot dates and the published counts without opening the run log.

It reads only files that the run itself wrote (`model/input/*`, `model/data/lines.csv`), prints
nothing it cannot read, and exits 0 even when a file is missing - a reporting problem must never
block or fake a published value.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> int:
    print("### Own-line model run")
    print()
    print("| What | Value |")
    print("|------|-------|")

    fx_path = ROOT / "input" / "hotspawn_cs2_fixtures.json"
    if fx_path.exists():
        fx = json.loads(fx_path.read_text(encoding="utf-8"))
        print(f"| Hotspawn snapshot fetched | {fx.get('fetched_utc')} |")
        print(f"| CS2 fixtures in that payload | {fx.get('fixture_count')} |")
        print(f"| Board header 'matches this week' | {fx.get('lobby_header_matches_this_week')} |")
        print(f"| Board filter 'All tiers' | {fx.get('lobby_filter_all_tiers')} |")
        print(f"| Permalinks read (per-match URLs) | {len(fx.get('permalinks') or {})} |")
    else:
        print("| Hotspawn snapshot | not present |")

    log_path = ROOT / "input" / "fetch_log.json"
    if log_path.exists():
        log = json.loads(log_path.read_text(encoding="utf-8"))
        print(f"| Valve Regional Standings | {log.get('vrs', {}).get('result', 'unknown')} |")
        print(f"| HLTV world ranking | {log.get('hltv', {}).get('result', 'unknown')} |")
        print(f"| Fetch run started | {log.get('run_utc', 'unknown')} |")

    meta_path = ROOT / "input" / "vrs" / "meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print(f"| Valve standings file | `{meta.get('path')}` @ `{str(meta.get('commit'))[:10]}` |")
        print(f"| Valve file SHA-256 | `{meta.get('sha256')}` |")

    cal_path = ROOT / "input" / "vrs" / "calibration.json"
    if cal_path.exists():
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
        print(f"| Calibrated slope k | {cal.get('k_published')} (Valve's raw {cal.get('raw_k_valve')}) |")

    lines_path = ROOT / "data" / "lines.csv"
    if lines_path.exists():
        rows = list(csv.DictReader(lines_path.open(encoding="utf-8")))
        own = [r for r in rows if r["line_status"] == "OWN LINE"]
        upcoming = [r for r in rows if r["section"] == "upcoming"]
        pickem = [r for r in rows if r["hotspawn_url"].endswith("/cs2-pickems")]
        print(f"| Published rows | {len(rows)} ({len(upcoming)} upcoming, {len(rows) - len(upcoming)} started/stale) |")
        print(f"| Own line published | {len(own)} rows |")
        print(f"| Blank + flagged | {len(rows) - len(own)} rows |")
        print(f"| Rows linking the Pick'em page (no per-match permalink) | {len(pickem)} |")
        bad = [r for r in rows if not r["hotspawn_url"].startswith(("https://www.hotspawn.com/", "https://play.hotspawn.com/"))]
        print(f"| Rows with a non-Hotspawn source URL | {len(bad)} |")
    else:
        print("| Published rows | model/data/lines.csv not present |")

    print()
    print("Hotspawn crowd percentages are not read by this pipeline; see `model/README.md`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
