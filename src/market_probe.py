#!/usr/bin/env python3
"""Probe candidate *public* esports-odds endpoints from a GitHub Actions runner.

EGamersWorld and HLTV answer 403 to datacenter clients (verified 2026-10-13, run
38445055709), so this probe asks which other public sources can be read
programmatically at all.  Nothing here logs in, wagers or bypasses a block: a
status code and a short public sample is recorded for each candidate.

Outputs data/market_probe.json (committed) + evidence/*.txt (temporary).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "evidence"
DATA = ROOT / "data"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

CANDIDATES = [
    ("polymarket-gamma-cs2", "https://gamma-api.polymarket.com/events?closed=false&limit=50&tag=Counter-Strike"),
    ("polymarket-gamma-lol", "https://gamma-api.polymarket.com/events?closed=false&limit=50&tag=League%20of%20Legends"),
    ("polymarket-clob-cs2", "https://clob.polymarket.com/markets?limit=20"),
    ("sofascore-esports", "https://www.sofascore.com/api/v1/sport/esports/scheduled-events/2026-10-14"),
    ("leaguepedia-schedule", "https://lol.fandom.com/api.php?action=cargoquery&tables=MatchSchedule&fields=MatchSchedule.OverviewPage,MatchSchedule.Team1,MatchSchedule.Team2,MatchSchedule.DateTime_UTC&where=MatchSchedule.DateTime_UTC%20LIKE%20%272026-10%25%27&limit=50&format=json"),
    ("liquipedia-cs2-api", "https://liquipedia.net/counterstrike/api.php?action=query&list=recentchanges&format=json&rclimit=5"),
    ("betexplorer-cs2", "https://www.betexplorer.com/esports/"),
    ("oddsportal-esports", "https://www.oddsportal.com/esports/"),
    ("oddspedia-esports", "https://oddspedia.com/esports"),
    ("flashscore-esports", "https://www.flashscore.com/esports/"),
    ("bovada-esports", "https://www.bovada.lv/sports/esports"),
    ("betonline-esports", "https://www.betonline.ag/sportsbook/esports"),
    ("ggbet-esports", "https://gg.bet/en/esports"),
    ("thunderpick-esports", "https://thunderpick.io/esports"),
    ("pinnacle-esports", "https://www.pinnacle.com/en/esports/matchups"),
    ("1xbet-esports", "https://1xbet.com/en/line/esports"),
    ("betano-esports", "https://www.betano.com/sport/esports/"),
    ("esportsbattle", "https://esportsbattle.com/en/counter-strike"),
    ("bo3-gg", "https://bo3.gg/matches/upcoming"),
    ("escorenews-matches", "https://escorenews.com/en/csgo/matches"),
]


def probe(url: str) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=35) as resp:
            body = resp.read(4_000_000)
            text = body.decode("utf-8", errors="replace")
            return {"url": url, "status": resp.status, "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()[:16], "fetched_utc": stamp,
                    "content_type": resp.headers.get("content-type", ""),
                    "odds_like_numbers": len(__import__("re").findall(r"\b[12]\.\d{2}\b", text)),
                    "has_team_names": bool(__import__("re").search(r"(Aurora|Falcons|fnatic|Astralis|9z|G2|NaVi|T1|Gen\.G|Cloud9|Karmine)", text, re.I)),
                    "sample": text[:400].replace("\n", " "),
                    "_body": body}
    except HTTPError as exc:
        return {"url": url, "status": exc.code, "error": f"HTTPError {exc.code}", "fetched_utc": stamp}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}", "fetched_utc": stamp}


def main() -> None:
    import re  # noqa: F401  (used inside probe via builtins import above)
    EVID.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    results = []
    for label, url in CANDIDATES:
        got = probe(url)
        if got.pop("_body", None):
            (EVID / f"market-{label}.body").write_text(got["sample"], encoding="utf-8")
        results.append({"label": label, **got})
        print(json.dumps({k: v for k, v in results[-1].items() if k != "sample"}), flush=True)
    (DATA / "market_probe.json").write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": "read-only probe of public endpoints; 403/blocked sources are recorded, never worked around",
        "results": results,
    }, indent=1), encoding="utf-8")
    ok = [r["label"] for r in results if r.get("status") == 200 and r.get("odds_like_numbers", 0) > 0]
    print("sources with 200 + odds-like numbers:", ok)


if __name__ == "__main__":
    import re  # noqa: F811
    main()
