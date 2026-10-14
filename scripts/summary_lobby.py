#!/usr/bin/env python3
"""Refresh summary/data/lobby_capture.csv from Hotspawn's public Pick'em pages (session arena/20d753a2).

Reads the server-rendered Angular state (`<script id="ng-state">`) of /lobby and /cs2-pickems using the
parser already in src/pickem_inventory.py. It keeps only CS2 rows whose lock time is still in the future.

What it deliberately does NOT do:
  * It never reads or stores crowd percentages (participants*_picked_percent).
  * It never builds a match URL from a slug. A match link is recorded only when that exact
    https://www.hotspawn.com/matches/... URL (ending in the match id) appears in the fetched HTML.

Fail-closed: if a page cannot be fetched or parsed, or the result is empty, the existing capture is kept
and the script exits non-zero so the scheduled job does not publish a partial lobby.
"""
import csv
import datetime as dt
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import pickem_inventory as pi  # noqa: E402  (reuses the repo's existing public-page parser)

OUT = ROOT / "summary" / "data" / "lobby_capture.csv"
PAGES = ["https://play.hotspawn.com/lobby", "https://play.hotspawn.com/cs2-pickems"]
FIELDS = ["captured_utc", "source_page", "competition_lobby", "lobby_team_1", "lobby_team_2",
          "start_utc", "hotspawn_match_id", "hotspawn_match_url"]


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    found = {}
    for url in PAGES:
        got = pi.fetch(url)
        if not got.get("body"):
            print(f"FAILED fetch {url}: {got.get('status')} {got.get('error')}", file=sys.stderr)
            return 1
        html = got["body"].decode("utf-8", errors="replace")
        m = pi.STATE_SCRIPT.search(html)
        if not m:
            print(f"FAILED: no ng-state on {url}", file=sys.stderr)
            return 1
        state = json.loads(m.group(1))
        for row in pi.match_rows(state):
            if str(row.get("sport_alias", "")).lower() != "cs2":
                continue
            lock = pi.ms(row.get("lock_time"))
            start = pi.ms(row.get("scheduled_start_time"))
            if not (lock and start and lock > stamp):
                continue  # closed or stale tournament rows are not on the open board
            mid = str(row["id"])
            link_re = re.compile(r"https://www\.hotspawn\.com/matches/[a-z0-9\-]+-" + re.escape(mid) + r"(?![0-9])")
            link = link_re.search(html)
            found.setdefault(mid, {
                "captured_utc": stamp,
                "source_page": url,
                "competition_lobby": row.get("competition_name", ""),
                "lobby_team_1": row.get("participants0_name", ""),
                "lobby_team_2": row.get("participants1_name", ""),
                "start_utc": start,
                "hotspawn_match_id": mid,
                "hotspawn_match_url": link.group(0) if link else "",
            })
    if not found:
        print("FAILED: no open CS2 rows parsed; keeping the existing capture", file=sys.stderr)
        return 1
    rows = sorted(found.values(), key=lambda r: (r["start_utc"], r["hotspawn_match_id"]))
    tmp = OUT.with_suffix(".csv.tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(OUT)
    print(f"ok: {len(rows)} open CS2 rows captured at {stamp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
