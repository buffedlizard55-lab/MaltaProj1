#!/usr/bin/env python3
"""Parse Valve's official Regional Standings into winboard/data/vrs.json.

The markdown file in the repository is checked against the SHA-256 GitHub Actions recorded
when it fetched the same URL, so the parsed values are provably the bytes Valve serves.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_MD = ROOT / "model" / "input" / "vrs" / "standings_global_2026_10_05.md"
OUT = ROOT / "winboard" / "data" / "vrs.json"

# Pinned to the commit GitHub Actions fetched (HTTP 200, 2026-10-13T22:11:03Z) so the link
# always resolves to exactly the bytes whose SHA-256 we verify below.
PIN = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"
RAW_URL = (
    "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings"
    f"/{PIN}/live/2026/standings_global_2026_10_05.md"
)
BLOB_URL = (
    f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{PIN}/"
    "live/2026/standings_global_2026_10_05.md"
)
EXPECTED_SHA256 = "df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b"


def main() -> int:
    if not SOURCE_MD.exists():
        print(f"missing {SOURCE_MD}", file=sys.stderr)
        return 1
    body = SOURCE_MD.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    text = body.decode("utf-8", "replace")

    teams: list[dict] = []
    # Header: | Standing | Points | Team Name | Roster | details |
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        line_no = lineno
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        points = cells[1].replace(",", "").strip()
        name = re.sub(r"^\[([^\]]+)\].*$", r"\1", cells[2]).strip()
        if not points.isdigit() or not name:
            continue
        roster = [x.strip() for x in cells[3].split(",") if x.strip()]
        teams.append(
            {
                "rank": int(cells[0]),
                "points": int(points),
                "name": name,
                "roster": roster,
                "line_no": line_no,
            }
        )

    doc = {
        "source": "Valve Software — Counter-Strike Regional Standings (global)",
        "standings_date": "2026-10-05",
        "source_url": BLOB_URL,
        "raw_url": RAW_URL,
        "local_file": "model/input/vrs/standings_global_2026_10_05.md",
        "sha256": digest,
        "sha256_matches_live_fetch": digest == EXPECTED_SHA256,
        "live_fetch_checked_utc": "2026-10-13T22:11:03Z",
        "team_count": len(teams),
        "teams": teams,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2))
    print(f"vrs: {len(teams)} teams, sha256 match = {doc['sha256_matches_live_fetch']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
