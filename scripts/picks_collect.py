"""Collector for the arena/cc8f4dca picks pipeline. Runs inside GitHub Actions.

Outputs (all committed back to the session branch):
  picks/data/fixtures.json   every CS2 pick'em fixture in the official Hotspawn SSR payload
  picks/data/vrs.json        Valve's official regional standings (global)
  picks/data/odds_<src>.json bookmaker / odds-comparison observations, per source
  picks/data/_debug_*.txt    small text samples used to write and re-verify the parsers
  picks/data/collect_meta.json  timestamps, HTTP statuses, hashes of every fetch

Rules:
  * Hotspawn is a fixture source only. Its crowd pick percentages are never read and never
    used as a probability input.
  * Nothing is inferred. A price that is not present in the fetched bytes stays null.
"""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "picks" / "data"
RAW = ROOT / "picks" / "raw"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

FETCHES: list[dict[str, object]] = []


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch(url: str, extra: dict[str, str] | None = None, label: str = "") -> tuple[int, bytes]:
    headers = dict(BASE_HEADERS)
    headers.update(extra or {})
    request = urllib.request.Request(url, headers=headers)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=60, context=context) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                try:
                    body = gzip.decompress(body)
                except OSError:
                    pass
            status = response.status
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            if error.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
        except Exception:  # noqa: BLE001
            pass
        status = error.code
    except Exception as error:  # noqa: BLE001
        FETCHES.append(
            {
                "label": label or url,
                "url": url,
                "fetched_utc": now_utc(),
                "http_status": 0,
                "bytes": 0,
                "sha256": "",
                "error": f"{type(error).__name__}: {error}",
            }
        )
        print(f"  {label}: ERROR {error}", flush=True)
        return 0, b""

    FETCHES.append(
        {
            "label": label or url,
            "url": url,
            "fetched_utc": now_utc(),
            "http_status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    )
    print(f"  {label}: HTTP {status} {len(body)}B", flush=True)
    return status, body


def text_of(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


# --------------------------------------------------------------------------------------
# 1. Hotspawn — fixture identity only
# --------------------------------------------------------------------------------------

def collect_hotspawn() -> dict[str, object]:
    print("Hotspawn", flush=True)
    out: dict[str, object] = {
        "source": "Hotspawn Play pick'em lobby (Angular SSR TransferState)",
        "pages": [],
        "fixtures": {},
    }
    seen: dict[str, dict] = {}
    for url in ("https://play.hotspawn.com/cs2-pickems", "https://play.hotspawn.com/lobby"):
        status, body = fetch(url, {"Referer": "https://play.hotspawn.com/lobby"}, "hotspawn")
        page = {"url": url, "http_status": status, "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest() if body else ""}
        (RAW / f"hotspawn-{url.rsplit('/', 1)[-1]}.html.gz").write_bytes(gzip.compress(body))
        if status != 200 or not body:
            out["pages"].append(page)
            continue
        markup = body.decode("utf-8", "replace")
        match = re.search(r'<script id="ng-state"[^>]*>(.*?)</script>', markup, re.S)
        page["transferstate_found"] = bool(match)
        out["pages"].append(page)
        if not match:
            continue
        blob = html.unescape(match.group(1))
        try:
            state = json.loads(blob)
        except json.JSONDecodeError:
            continue
        fixtures = _walk_fixtures(state)
        for fixture in fixtures:
            key = str(fixture.get("id"))
            if not key:
                continue
            entry = dict(seen.get(key, {}))
            entry.update({k: v for k, v in fixture.items() if v is not None})
            entry.setdefault("seen_on", [])
            if url not in entry["seen_on"]:
                entry["seen_on"].append(url)
            seen[key] = entry
    out["fixture_count"] = len(seen)
    out["fixtures"] = seen
    return out


def _walk_fixtures(node) -> list[dict]:
    """Find every object that looks like a pick'em fixture in the TransferState tree."""
    found: list[dict] = []
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if (
                "participants0_name" in current
                and "participants1_name" in current
                and ("lock_time" in current or "scheduled_start_time" in current)
            ):
                found.append(current)
                continue
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


# --------------------------------------------------------------------------------------
# 2. Valve official regional standings
# --------------------------------------------------------------------------------------

def collect_vrs() -> dict[str, object]:
    print("Valve VRS", flush=True)
    url = (
        "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings"
        "/main/live/2026/standings_global_2026_10_05.md"
    )
    status, body = fetch(url, label="valve-vrs")
    text = body.decode("utf-8", "replace")
    teams: list[dict] = []
    for line in text.splitlines():
        # Valve's markdown table rows look like: | 1 | [Team](url) | 1234 | ... |
        # Valve's table is: | Standing | Points | Team Name | Roster | details |
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
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
                "row": line,
            }
        )
    return {
        "source": "Valve Software — official Counter-Strike Regional Standings",
        "source_url": (
            "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
            "live/2026/standings_global_2026_10_05.md"
        ),
        "raw_url": url,
        "http_status": status,
        "sha256": hashlib.sha256(body).hexdigest() if body else "",
        "fetched_utc": now_utc(),
        "team_count": len(teams),
        "teams": teams,
    }


# --------------------------------------------------------------------------------------
# 3. Bookmaker / odds-comparison sources
# --------------------------------------------------------------------------------------

ODDSPORTAL_HEADERS = {
    "Referer": "https://www.oddsportal.com/",
    "Sec-Fetch-Site": "same-origin",
}

EGW_HEADERS = {
    "Referer": "https://egamersworld.com/",
    "Sec-Fetch-Site": "same-origin",
    "Cookie": "egw_locale=en",
}


def probe_odds_sources() -> dict[str, object]:
    print("Odds sources", flush=True)
    debug = DATA / "_debug"
    debug.mkdir(parents=True, exist_ok=True)
    results: dict[str, object] = {}

    candidates: list[tuple[str, str, dict[str, str]]] = [
        (
            "oddsportal_cs",
            "https://www.oddsportal.com/esports/counter-strike/",
            ODDSPORTAL_HEADERS,
        ),
        (
            "egamersworld_cs_matches",
            "https://egamersworld.com/counterstrike/matches",
            EGW_HEADERS,
        ),
        (
            "egamersworld_cs_upcoming",
            "https://egamersworld.com/counterstrike/matches/upcoming",
            EGW_HEADERS,
        ),
        (
            "pinnacle_guest_leagues",
            "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues",
            {"Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"},
        ),
    ]

    for label, url, headers in candidates:
        status, body = fetch(url, headers, label)
        (RAW / f"{label}.html.gz").write_bytes(gzip.compress(body))
        text = body.decode("utf-8", "replace")
        results[label] = {
            "url": url,
            "http_status": status,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest() if body else "",
            "fetched_utc": now_utc(),
        }
        if status != 200 or not body:
            continue
        # Debug sample: every internal link that looks like a match page, plus a text sample.
        links = sorted(set(re.findall(r'href="(/[^"]*(?:match|counter-strike)[^"]*)"', text)))
        (debug / f"{label}_links.txt").write_text("\n".join(links[:400]))
        (debug / f"{label}_sample.txt").write_text(text_of(text)[:6000])
        if label == "pinnacle_guest_leagues":
            try:
                leagues = json.loads(text)
                cs2 = [
                    {"id": lg.get("id"), "name": lg.get("name"), "matchupCount": lg.get("matchupCount")}
                    for lg in leagues
                    if lg.get("sport", {}).get("id") == 12
                    and "Counter-Strike" in (lg.get("name") or "")
                ]
                results[label]["cs2_leagues"] = cs2
                (debug / "pinnacle_cs2_leagues.json").write_text(json.dumps(cs2, indent=2))
            except json.JSONDecodeError:
                pass
        time.sleep(1)

    return results


def collect_pinnacle_matchups(league_ids: list[int]) -> dict[str, object]:
    print("Pinnacle matchups", flush=True)
    out: dict[str, object] = {
        "source": "Pinnacle public guest matchup feed",
        "leagues": [],
        "matchups": [],
    }
    for league_id in league_ids:
        url = (
            f"https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues/{league_id}"
            "/matchups?brandId=0&withSpecials=false"
        )
        status, body = fetch(
            url,
            {"Referer": "https://www.pinnacle.com/", "Origin": "https://www.pinnacle.com"},
            f"pinnacle-league-{league_id}",
        )
        (RAW / f"pinnacle-league-{league_id}.json.gz").write_bytes(gzip.compress(body))
        if status != 200:
            continue
        try:
            payload = json.loads(body.decode("utf-8", "replace"))
        except json.JSONDecodeError:
            continue
        matchups = payload if isinstance(payload, list) else payload.get("matchups", [])
        for matchup in matchups:
            participants = matchup.get("participants") or []
            names = {p.get("alignment"): p.get("name") for p in participants}
            out["matchups"].append(
                {
                    "id": matchup.get("id"),
                    "league_id": league_id,
                    "league_name": (matchup.get("league") or {}).get("name"),
                    "startTime": matchup.get("startTime"),
                    "status": matchup.get("status"),
                    "bestOfX": matchup.get("bestOfX"),
                    "home": names.get("home"),
                    "away": names.get("away"),
                    "prices": None,
                }
            )
        out["leagues"].append({"id": league_id, "count": len(matchups)})
        time.sleep(1)
    return out


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    started = now_utc()

    hotspawn = collect_hotspawn()
    (DATA / "fixtures.json").write_text(json.dumps(hotspawn, indent=2))

    vrs = collect_vrs()
    (DATA / "vrs.json").write_text(json.dumps(vrs, indent=2))

    odds = probe_odds_sources()
    (DATA / "odds_probe.json").write_text(json.dumps(odds, indent=2))

    league_ids = [
        lg["id"] for lg in odds.get("pinnacle_guest_leagues", {}).get("cs2_leagues", []) if lg.get("id")
    ]
    pinnacle = collect_pinnacle_matchups(league_ids[:40])
    (DATA / "odds_pinnacle.json").write_text(json.dumps(pinnacle, indent=2))

    meta = {
        "run_started_utc": started,
        "run_finished_utc": now_utc(),
        "fetches": FETCHES,
    }
    (DATA / "collect_meta.json").write_text(json.dumps(meta, indent=2))
    print("collect complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
