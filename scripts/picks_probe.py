"""Primary-source probe for the arena/cc8f4dca picks pipeline.

Runs inside GitHub Actions (which has unrestricted outbound internet) and writes, for
every candidate source, the HTTP status, the response size and a SHA-256 of the body,
plus a gzipped copy of the body itself.

Nothing is parsed or inferred here: this step only proves what is reachable and preserves
the exact bytes so the parser can be written and re-run against the same evidence.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "picks" / "raw"
OUT = ROOT / "picks" / "data"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# name -> (url, slug used for the raw file, extra headers)
SOURCES: list[tuple[str, str, str, dict[str, str]]] = [
    (
        "hotspawn_cs2_pickems",
        "https://play.hotspawn.com/cs2-pickems",
        "hotspawn-cs2-pickems.html",
        {"Referer": "https://play.hotspawn.com/lobby"},
    ),
    (
        "hotspawn_lobby",
        "https://play.hotspawn.com/lobby",
        "hotspawn-lobby.html",
        {},
    ),
    (
        "egamersworld_cs2_matches",
        "https://egamersworld.com/counterstrike/matches",
        "egamersworld-cs2-matches.html",
        {"Referer": "https://egamersworld.com/"},
    ),
    (
        "pinnacle_guest_highlighted",
        "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/highlighted",
        "pinnacle-highlighted.json",
        {"Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"},
    ),
    (
        "pinnacle_guest_leagues",
        "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues",
        "pinnacle-leagues.json",
        {"Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"},
    ),
    (
        "pinnacle_guest_moneyline",
        "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/moneyline"
        "?matchupIds=1638111674",
        "pinnacle-moneyline.json",
        {"Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"},
    ),
    (
        "pinnacle_esports_highlights_page",
        "https://www.pinnacle.com/en/esports/matchups/highlights/",
        "pinnacle-esports-highlights.html",
        {},
    ),
    (
        "hltv_matches",
        "https://www.hltv.org/matches",
        "hltv-matches.html",
        {},
    ),
    (
        "hltv_ranking",
        "https://www.hltv.org/ranking/teams/2026/october/12",
        "hltv-ranking.html",
        {},
    ),
    (
        "betexplorer_cs",
        "https://www.betexplorer.com/counter-strike/",
        "betexplorer-cs.html",
        {},
    ),
    (
        "oddsportal_cs",
        "https://www.oddsportal.com/esports/counter-strike/",
        "oddsportal-cs.html",
        {},
    ),
    (
        "escorenews_cs_matches",
        "https://www.escorenews.com/en/counterstrike/matches",
        "escorenews-cs-matches.html",
        {},
    ),
    (
        "valve_vrs_2026_10_05",
        "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings"
        "/main/live/2026/standings_global_2026_10_05.md",
        "valve-vrs-2026-10-05.md",
        {},
    ),
]


def fetch(url: str, extra: dict[str, str]) -> tuple[int, bytes, str]:
    headers = dict(BROWSER_HEADERS)
    headers.update(extra)
    request = urllib.request.Request(url, headers=headers)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=45, context=context) as response:
            return response.status, response.read(), response.headers.get("Content-Type", "")
    except urllib.error.HTTPError as error:  # status is still real evidence
        return error.code, error.read(), error.headers.get("Content-Type", "") if error.headers else ""
    except Exception as error:  # noqa: BLE001 - record and continue
        return 0, b"", f"EXCEPTION: {type(error).__name__}: {error}"


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    report: list[dict[str, object]] = []

    for name, url, filename, extra in SOURCES:
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        status, body, content_type = fetch(url, extra)
        digest = hashlib.sha256(body).hexdigest() if body else ""
        (RAW / f"{filename}.gz").write_bytes(gzip.compress(body))
        report.append(
            {
                "name": name,
                "url": url,
                "raw_file": f"{filename}.gz",
                "fetched_utc": fetched_at,
                "http_status": status,
                "content_type": content_type,
                "bytes": len(body),
                "sha256": digest,
                "head": body[:300].decode("utf-8", "replace"),
            }
        )
        print(f"{name}: HTTP {status} {len(body)}B", flush=True)
        time.sleep(1)

    (OUT / "probe.json").write_text(
        json.dumps({"started_utc": started, "sources": report}, indent=2)
    )
    print(f"probe complete: {len(report)} sources -> {RAW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
