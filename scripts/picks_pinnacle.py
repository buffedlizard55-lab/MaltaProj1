"""Pinnacle public guest-feed collector for the arena/cc8f4dca picks pipeline.

Endpoint set observed from a real browser session on https://www.pinnacle.com/ , then replayed
with a plain HTTP client inside GitHub Actions:

  /0.1/sports/12/leagues?all=true                       all e-sports leagues
  /0.1/leagues/{leagueId}/matchups                      matchups for a league (names, ids)
  /0.1/matchups/{matchupId}/markets/related/straight    markets + prices (participants carry ids)
  /0.1/sports/12/markets/highlighted/straight           highlighted markets + prices

Only the **full-match moneyline** (period 0, key ``s;0;m``) is kept. Prices are stored exactly
as returned; the decimal conversion happens in the model step, where it is also checked.
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
DATA = ROOT / "picks" / "data"
RAW = ROOT / "picks" / "raw"

API = "https://guest.api.arcadia.pinnacle.com/0.1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.pinnacle.com/",
    "Origin": "https://www.pinnacle.com",
}
SPORT_ESPORTS = 12
CS_TOKENS = ("counter-strike", "cs2", "cs:go", "csgo", "counter strike")


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get(path: str) -> tuple[int, object]:
    url = f"{API}{path}" if path.startswith("/") else path
    request = urllib.request.Request(url, headers=HEADERS)
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, timeout=45, context=context) as response:
            body = response.read()
            return response.status, json.loads(body.decode("utf-8", "replace")) if body else None
    except urllib.error.HTTPError as error:
        return error.code, None
    except Exception as error:  # noqa: BLE001
        print(f"   ! {path}: {type(error).__name__}: {error}", flush=True)
        return 0, None


def moneyline(matchup: dict) -> dict | None:
    """Return the full-match moneyline with home/away prices, or None."""
    participants = {
        p.get("id"): p.get("name")
        for p in (matchup.get("participants") or [])
        if p.get("id") is not None
    }
    by_align = {p.get("alignment"): p.get("name") for p in (matchup.get("participants") or [])}
    for market in matchup.get("markets") or []:
        if market.get("key") != "s;0;m" or market.get("period") != 0:
            continue
        prices = market.get("prices") or []
        if len(prices) < 2:
            return None
        rows = []
        for price in prices:
            if price.get("designation") not in ("home", "away", None):
                continue
            rows.append(price)
        if len(rows) < 2:
            return None
        home = next((r for r in rows if r.get("designation") == "home"), None)
        away = next((r for r in rows if r.get("designation") == "away"), None)
        if home is None or away is None:
            home, away = rows[0], rows[1]
        return {
            "key": market.get("key"),
            "period": market.get("period"),
            "cutoff_at": market.get("cutoffAt"),
            "status": market.get("status"),
            "home_name": by_align.get("home") or participants.get(home.get("participantId")),
            "away_name": by_align.get("away") or participants.get(away.get("participantId")),
            "home_price_raw": home.get("price"),
            "away_price_raw": away.get("price"),
            "home_participant_id": home.get("participantId"),
            "away_participant_id": away.get("participantId"),
        }
    return None


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    out: dict[str, object] = {
        "source": "Pinnacle public guest feed (prices observed on pinnacle.com)",
        "source_pages": {
            "esports_matchups": "https://www.pinnacle.com/en/esports/matchups/highlights/",
        },
        "fetched_utc": now_utc(),
        "leagues": [],
        "matchups": [],
        "errors": [],
    }

    status, leagues = get("/sports/12/leagues?all=true")
    print(f"leagues: HTTP {status} -> {len(leagues) if isinstance(leagues, list) else 0}", flush=True)
    if not isinstance(leagues, list):
        out["errors"].append({"path": "/sports/12/leagues?all=true", "http_status": status})
        (DATA / "odds_pinnacle.json").write_text(json.dumps(out, indent=2))
        return 0

    cs_leagues = [
        lg
        for lg in leagues
        if (lg.get("sport") or {}).get("id") == SPORT_ESPORTS
        and any(token in (lg.get("name") or "").lower() for token in CS_TOKENS)
    ]
    out["leagues"] = [
        {"id": lg.get("id"), "name": lg.get("name"), "matchupCount": lg.get("matchupCount")}
        for lg in cs_leagues
    ]
    print(f"counter-strike leagues: {len(cs_leagues)}", flush=True)

    matchup_ids: list[tuple[str, int]] = []
    for league in cs_leagues:
        league_id = league.get("id")
        status, matchups = get(f"/leagues/{league_id}/matchups")
        if not isinstance(matchups, list):
            out["errors"].append({"path": f"/leagues/{league_id}/matchups", "http_status": status})
            time.sleep(0.5)
            continue
        for matchup in matchups:
            if matchup.get("type") != "matchup":
                continue
            matchup_ids.append((league.get("name"), matchup.get("id")))
        print(f"  league {league_id} ({league.get('name')}): {len(matchups)} matchups", flush=True)
        time.sleep(0.4)

    # Highlighted markets carry prices for the featured board.
    status, highlighted = get("/sports/12/markets/highlighted/straight?primaryOnly=false")
    if isinstance(highlighted, list):
        (RAW / "pinnacle_markets_highlighted.json.gz").write_bytes(
            gzip.compress(json.dumps(highlighted).encode())
        )
        for matchup in highlighted:
            line = moneyline(matchup)
            if not line:
                continue
            league_name = (matchup.get("league") or {}).get("name")
            if not league_name or not any(t in league_name.lower() for t in CS_TOKENS):
                continue
            out["matchups"].append(
                {
                    "matchup_id": matchup.get("id"),
                    "league": league_name,
                    "start_time": matchup.get("startTime"),
                    "status": matchup.get("status"),
                    "best_of": matchup.get("bestOfX"),
                    "via": "markets/highlighted/straight",
                    **line,
                }
            )
        print(f"highlighted: {len(out['matchups'])} CS moneylines", flush=True)

    # One call per league returns every matchup with its markets and prices.
    for league in cs_leagues:
        league_id = league.get("id")
        status, payload = get(f"/leagues/{league_id}/markets/straight")
        if not isinstance(payload, list):
            out["errors"].append({"path": f"/leagues/{league_id}/markets/straight",
                                  "http_status": status})
            time.sleep(0.4)
            continue
        kept = 0
        for matchup in payload:
            line = moneyline(matchup)
            if not line:
                continue
            out["matchups"].append(
                {
                    "matchup_id": matchup.get("id"),
                    "league": league.get("name"),
                    "start_time": matchup.get("startTime"),
                    "status": matchup.get("status"),
                    "best_of": matchup.get("bestOfX"),
                    "via": "leagues/{id}/markets/straight",
                    **line,
                }
            )
            kept += 1
        print(f"  league {league_id} ({league.get('name')}): {len(payload)} matchups, {kept} moneylines", flush=True)
        time.sleep(0.4)

    out["matchup_count"] = len(out["matchups"])
    (DATA / "odds_pinnacle.json").write_text(json.dumps(out, indent=2))
    print(f"pinnacle moneylines: {len(out['matchups'])}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 2026-10-13T22:19:30Z trigger
