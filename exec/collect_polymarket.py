#!/usr/bin/env python3
"""Collect Polymarket's public CS2 markets as an extra outside reference — session arena/3b5e3fea.

Why this exists: the Hotspawn Pick'em board lists many low-tier online-cup matches that the large
bookmakers do not price. Polymarket's public API does list some of those cups, so it is worth reading —
but it must be published honestly:

  * a per-map market ("Map 1 Winner") is NOT a series probability and is never published as the pick;
  * a thin market's price is the market's price, not a prediction we endorse;
  * if the API is unreachable or a fixture has no market, the row stays blank and is flagged.

No credentials are used and no account is required. The raw response is archived (gzipped) next to the
normalised file so any published number can be re-derived from the bytes.

Run (needs network):  python3 exec/collect_polymarket.py
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "exec", "data")
RAW = os.path.join(OUT, "raw")
ENDPOINT = "https://gamma-api.polymarket.com/events"
SEARCH = "https://gamma-api.polymarket.com/public-search"
UA = "MaltaProj1-exec-board/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1)"
MAX_SKEW = timedelta(minutes=15)
SERIES_RE = re.compile(r"\b(bo[135])\b", re.I)
MAP_RE = re.compile(r"map\s*\d", re.I)
# A market whose question is not about "who wins" is never a winner probability, whatever its outcomes are.
NOT_WINNER_RE = re.compile(r"handicap|spread|total|over\s*/?\s*under|rounds|correct score|odd/even|both teams",
                           re.I)


def fetch(url: str, timeout: int = 45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
    return body


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_open_fixtures():
    """Match identities come from this repository's own capture, never re-scraped here."""
    for rel in ("slate/data/fixtures.csv",):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            continue
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = [dict(r) for r in csv.DictReader(fh)]
        now = datetime.now(timezone.utc)
        out = []
        for r in rows:
            if (r.get("sport") or "").lower() != "cs2":
                continue
            lock = r.get("lock_utc") or ""
            try:
                lock_dt = datetime.strptime(lock, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if lock_dt <= now:
                continue
            out.append({
                "fixture_id": (r.get("fixture_id") or "").strip(),
                "team_a": (r.get("team_a") or "").strip(),
                "team_b": (r.get("team_b") or "").strip(),
                "start_utc": r.get("start_utc") or "",
                "competition": r.get("competition") or "",
                "source": rel,
            })
        return out
    return []


def parse_time(text: str):
    if not text:
        return None
    text = text.strip().replace(" ", "T")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def market_rows(event, fixture):
    """Return (series_rows, map_rows) for one fixture.

    A market is only accepted when its two outcomes are exactly the two team names of the fixture and
    its question asks who wins (handicaps, totals, rounds and similar are dropped). Per-map winners are
    returned separately and are never treated as a series probability."""
    a, b = norm(fixture["team_a"]), norm(fixture["team_b"])
    series, maps = [], []
    for m in event.get("markets", []) or []:
        question = m.get("question") or ""
        try:
            outcomes = json.loads(m.get("outcomes") or "[]")
        except Exception:
            outcomes = []
        try:
            prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except Exception:
            prices = []
        if len(outcomes) != 2 or len(prices) != 2:
            continue
        if {norm(o) for o in outcomes} != {a, b}:
            continue  # e.g. Yes/No, Over/Under, or another pairing
        if NOT_WINNER_RE.search(question):
            continue  # a handicap or total is not a winner probability
        rec = {
            "question": question,
            "outcomes": outcomes,
            "prices": prices,
            "best_bid": m.get("bestBid"),
            "best_ask": m.get("bestAsk"),
            "liquidity": m.get("liquidityNum") or m.get("liquidity"),
            "volume": m.get("volumeNum") or m.get("volume"),
            "updated_utc": m.get("updatedAt") or "",
            "slug": m.get("slug") or "",
        }
        if MAP_RE.search(question):
            maps.append(rec)
        else:
            series.append(rec)
    return series, maps


def event_start(event):
    """The match kickoff as the market itself states it. `startDate` is when the market was created,
    so it is never used as a kickoff — only the explicit game/event start fields are."""
    for key in ("gameStartTime", "eventStartTime"):
        stamp = parse_time(event.get(key) or "")
        if stamp:
            return stamp
    for market in event.get("markets", []) or []:
        for key in ("gameStartTime", "eventStartTime"):
            stamp = parse_time(market.get(key) or "")
            if stamp:
                return stamp
    return None


def match_fixture(event, fixtures):
    """Match by both team names (in any order) and, when the market states a kickoff, by a start time
    within MAX_SKEW. Returns (fixture, how) or (None, reason)."""
    title = event.get("title") or ""
    start = event_start(event)
    for fx in fixtures:
        a, b = norm(fx["team_a"]), norm(fx["team_b"])
        if not a or not b:
            continue
        hay = norm(title)
        if a in hay and b in hay:
            fx_start = parse_time(fx["start_utc"])
            if start is None:
                return fx, "names-only (market states no kickoff)"
            if fx_start and abs(start - fx_start) > MAX_SKEW:
                return None, f"kickoff mismatch ({iso(start)} vs {fx['start_utc']})"
            return fx, "names+kickoff"
    return None, "no title match"


def search_event(team_a: str, team_b: str):
    """Ask Polymarket's public search for this pairing. Returns (events, raw_bytes) or raises."""
    query = urllib.parse.urlencode({"q": f"{team_a} {team_b}", "limit_per_type": "4"})
    body = fetch(f"{SEARCH}?{query}")
    payload = json.loads(body.decode("utf-8"))
    events = payload.get("events") or []
    return events, body


def main() -> int:
    """One search per open fixture. A fixture whose market cannot be found is recorded as unmatched,
    never guessed from a neighbouring market."""
    os.makedirs(RAW, exist_ok=True)
    captured = datetime.now(timezone.utc)
    fixtures = load_open_fixtures()
    result = {
        "status": "ok",
        "endpoint": f"{SEARCH}?q=<team_a> <team_b>&limit_per_type=4 (one lookup per open fixture)",
        "captured_utc": iso(captured),
        "fixtures_considered": len(fixtures),
        "note": ("Polymarket lists some of the low-tier cups that big bookmakers skip. Only whole-match "
                 "(series) markets are republished as a series reference; per-map markets are recorded "
                 "separately and are never used as a series probability. A fixture with no matching event "
                 "is recorded as unmatched, not filled in."),
        "matches": [],
        "map_markets": [],
        "unmatched": [],
        "errors": [],
    }
    search_log = []
    for fx in fixtures:
        try:
            events, body = search_event(fx["team_a"], fx["team_b"])
        except Exception as exc:
            result["errors"].append(f"{fx['fixture_id']}: {type(exc).__name__}: {exc}")
            search_log.append({"fixture_id": fx["fixture_id"], "events": 0, "matched": ""})
            continue
        with gzip.open(os.path.join(RAW, f"polymarket_search_{fx['fixture_id']}.json.gz"), "wb") as fh:
            fh.write(body)
        chosen, how = None, "no events returned"
        for event in events:
            fx_match, why = match_fixture(event, [fx])
            if fx_match:
                chosen, how = event, why
                break
            how = why
        search_log.append({"fixture_id": fx["fixture_id"], "events": len(events),
                           "matched": (chosen or {}).get("slug", ""), "how": how})
        if not chosen:
            result["unmatched"].append({"fixture_id": fx["fixture_id"],
                                        "team_a": fx["team_a"], "team_b": fx["team_b"]})
            continue
        series, maps = market_rows(chosen, fx)
        slug = chosen.get("slug") or ""
        page = f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com/esports/cs2"
        for rec in series:
            result["matches"].append({
                "fixture_id": fx["fixture_id"], "team_a": fx["team_a"], "team_b": fx["team_b"],
                "title": chosen.get("title") or "", "market_kind": "series",
                "question": rec["question"], "outcomes": rec["outcomes"],
                "p_a": round(rec["prices"][0] * 100, 2), "p_b": round(rec["prices"][1] * 100, 2),
                "best_bid": rec["best_bid"], "best_ask": rec["best_ask"],
                "liquidity_usd": rec["liquidity"], "volume_usd": rec["volume"],
                "updated_utc": rec["updated_utc"], "url": page,
            })
        for rec in maps:
            result["map_markets"].append({
                "fixture_id": fx["fixture_id"], "title": chosen.get("title") or "",
                "market_kind": "map", "question": rec["question"],
                "p_a": round(rec["prices"][0] * 100, 2), "p_b": round(rec["prices"][1] * 100, 2),
                "liquidity_usd": rec["liquidity"], "updated_utc": rec["updated_utc"], "url": page,
            })
    result["search_log"] = search_log
    result["matched_fixtures"] = len({m["fixture_id"] for m in result["matches"]} |
                                     {m["fixture_id"] for m in result["map_markets"]})
    if result["errors"] and not result["search_log"]:
        result["status"] = "unreachable"
    with open(os.path.join(OUT, "polymarket.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
    print(f"polymarket: {len(result['matches'])} series markets, {len(result['map_markets'])} map markets, "
          f"{len(result['unmatched'])} fixtures without a market, {len(result['errors'])} error(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
