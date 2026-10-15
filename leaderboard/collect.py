#!/usr/bin/env python3
"""Live collector for the contrarian leaderboard plan — session arena/2e2b2e5e.

Runs unattended on GitHub Actions every four hours (this project's agent sandbox has no general
internet access; Actions runners do). It writes one normalized capture,
``leaderboard/data/capture.json``, plus a provenance ledger. Sources, in the order they are read:

1. **Hotspawn** (fixture identity only) — the public Angular pages ``/lobby``, ``/cs2-pickems`` and
   ``/thp-pickems`` embed their server-side API responses in ``<script id="ng-state">``
   (Angular TransferState). Entries whose ``u`` ends in ``/api/v1/fixtures`` hold the complete
   fixture arrays the site renders (``phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures``).
   We keep fixture id, teams, competition, tier, offered points, explicit start/lock epochs, status,
   and the public crowd split. The crowd split is stored **only** under ``ownership`` and is used
   solely to measure how contrarian a pick is; it is never an input to any probability.
2. **Pinnacle** public guest JSON (the same responses pinnacle.com's own CS2 page loads) — CS2
   period-0 moneylines.
3. **bo3.gg** public API (the JSON its own match pages load) — upcoming CS2 matches with series
   format and the bookmaker price bo3.gg relays (Thunderpick and others).
4. **Polymarket** gamma API (series 10310 = Counter-Strike) — open match-winner markets.
5. **Valve Regional Standings** — newest ``standings_global_*.md`` in Valve's official repository.
6. **HLTV world ranking** — attempted; HLTV often answers runners with HTTP 403. On refusal the
   previous capture is kept and labelled with its original read time.

No source failure stops the run. A failed source keeps its previous capture **with the original
capture time** (never relabelled as fresh) and the refusal is recorded. Nothing is invented.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CAPTURE = DATA / "capture.json"

UA = "Mozilla/5.0 (compatible; MaltaProj1-leaderboard/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/leaderboard)"
HTML_HEADERS = {"User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"}
JSON_HEADERS = {"User-Agent": UA, "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"}

HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
]
STATE_RE = re.compile(r'<script[^>]*id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)

# Pinnacle's public web app sends this key from every visitor's browser; it is not an account key.
# Same constant this repository's executive collector already uses (executive/common.py).
PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_HEADERS = {
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pinnacle.com",
    "Referer": "https://www.pinnacle.com/",
}
PIN_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
BO3_MATCHES = "https://api.bo3.gg/api/v1/matches"
PM_EVENTS = "https://gamma-api.polymarket.com/events"
PM_SERIES_ID = "10310"
VRS_REPO = "ValveSoftware/counter-strike_regional_standings"
VRS_LISTING = f"https://api.github.com/repos/{VRS_REPO}/contents/live/2026"
HLTV_RANKING = "https://www.hltv.org/ranking/teams"

PROVENANCE: list[dict] = []


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[{iso(now())}] {msg}", flush=True)


def http_get(url: str, headers: dict | None = None, timeout: int = 45, retries: int = 2) -> dict:
    """GET with an honest user agent. Retries only on transport errors, 429 and 5xx."""
    rec = {"url": url, "status": None, "bytes": 0, "sha256": None, "error": None,
           "fetched_utc": None, "body": b""}
    for attempt in range(retries + 1):
        rec["fetched_utc"] = iso(now())
        try:
            req = urllib.request.Request(url, headers=headers or JSON_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                rec.update(status=resp.status, body=body, bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), error=None)
                break
        except urllib.error.HTTPError as exc:
            rec.update(status=exc.code, error=f"HTTP {exc.code}")
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:  # noqa: BLE001 - transport failures are recorded, never hidden
            rec.update(error=f"{type(exc).__name__}: {exc}"[:240])
        time.sleep(2 * (attempt + 1))
    PROVENANCE.append({k: rec[k] for k in ("url", "status", "bytes", "sha256", "error", "fetched_utc")})
    return rec


def get_json(url: str, headers: dict | None = None, timeout: int = 45):
    rec = http_get(url, headers=headers, timeout=timeout)
    if rec["status"] != 200 or not rec["body"]:
        return None, rec
    try:
        return json.loads(rec["body"].decode("utf-8", "replace")), rec
    except ValueError as exc:
        rec["error"] = f"JSON: {exc}"[:200]
        return None, rec


def epoch_ms_to_iso(value) -> str | None:
    try:
        ms = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return iso(datetime.fromtimestamp(ms / 1000, tz=timezone.utc))


def american_to_decimal(price) -> float:
    value = float(price)
    if value >= 100:
        return 1.0 + value / 100.0
    if value <= -100:
        return 1.0 + 100.0 / abs(value)
    raise ValueError(f"not an American price: {price!r}")


# ------------------------------------------------------------------ 1. Hotspawn
def _int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_hotspawn_state(html: str, page: str, page_url: str, fetched: str) -> dict:
    """Parse one Hotspawn page. Returns fixtures, week window and page-level counters."""
    out = {"fixtures": [], "week": None, "permalinks": {}, "leaderboard_points": [],
           "header_matches_this_week": None, "filter_all_tiers": None, "api_urls": []}
    match = STATE_RE.search(html)
    if not match:
        out["error"] = "ng-state TransferState not found"
        return out
    try:
        state = json.loads(match.group(1))
    except ValueError:
        out["error"] = "invalid TransferState JSON"
        return out
    for value in state.values():
        if not isinstance(value, dict):
            continue
        body, url = value.get("b"), str(value.get("u") or "")
        if url and url not in out["api_urls"]:
            out["api_urls"].append(url.split("?")[0])
        if (isinstance(body, list) and value.get("s") == 200 and url.split("?")[0].endswith("/api/v1/fixtures")):
            for item in body:
                if isinstance(item, dict) and "participants0_name" in item:
                    out["fixtures"].append(item)
        if isinstance(body, dict):
            if "weekStartUtc" in body and out["week"] is None:
                out["week"] = {k: body.get(k) for k in ("weekId", "weekStartUtc", "weekEndUtc", "cutoffUtc")}
            links = body.get("permalinks")
            if isinstance(links, dict):
                for fid, link in links.items():
                    if isinstance(link, str) and link.startswith(("https://www.hotspawn.com/", "https://play.hotspawn.com/")):
                        out["permalinks"][str(fid)] = link
        # Leaderboard: keep only position + points (no player names are stored).
        if url.split("?")[0].endswith("/leaderboard") and isinstance(body, (list, dict)):
            rows = body if isinstance(body, list) else (body.get("items") or body.get("rows") or body.get("data") or [])
            for row in rows if isinstance(rows, list) else []:
                if isinstance(row, dict):
                    pos = _int_or_none(row.get("position") or row.get("rank"))
                    pts = _int_or_none(row.get("points") or row.get("total_points") or row.get("score"))
                    if pos is not None and pts is not None:
                        out["leaderboard_points"].append({"position": pos, "points": pts})
    plain = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    head = re.search(r"(\d+)\s*matches this week", plain)
    total = re.search(r"All tiers \((\d+)\)", plain)
    out["header_matches_this_week"] = int(head.group(1)) if head else None
    out["filter_all_tiers"] = int(total.group(1)) if total else None
    if not out["leaderboard_points"]:
        # Rendered leaderboard fallback: "Position Player Points 1 <name> 109 2 <name> 97 ...".
        block = re.search(r"Leaderboard.*?Position\s+Player\s+Points\s+(.*?)(?:Leaderboard|Top prizes|$)", plain)
        if block:
            for pos, pts in re.findall(r"(?:^|\s)(\d{1,2})\s+\S.*?\s(\d{1,4})(?=\s+\d{1,2}\s|\s*$)", block.group(1))[:10]:
                out["leaderboard_points"].append({"position": int(pos), "points": int(pts)})
    out["fetched_utc"] = fetched
    out["page"] = page
    out["page_url"] = page_url
    return out


def normalize_fixture(raw: dict, page: str, page_url: str, fetched: str, permalinks: dict) -> dict:
    fid = str(raw.get("id"))
    p0, p1 = raw.get("participants0_picked_percent"), raw.get("participants1_picked_percent")
    return {
        "match_id": fid,
        "sport": str(raw.get("sport_alias") or "").lower(),
        "competition": raw.get("competition_name"),
        "competition_id": str(raw.get("competition_id") or ""),
        "status": raw.get("status"),
        "tier": str(raw.get("tier") or "").lower() or None,
        "stage": raw.get("stage"),
        "offered_points": _int_or_none(raw.get("offered_points")),
        "base_points": _int_or_none(raw.get("base_points")),
        "best_of": _int_or_none(raw.get("best_of")),
        "series_format": raw.get("series_format"),
        "start_utc": epoch_ms_to_iso(raw.get("scheduled_start_time")),
        "lock_utc": epoch_ms_to_iso(raw.get("lock_time")),
        "lock_offset_sec": _int_or_none(raw.get("lock_offset_sec")),
        "started_utc": epoch_ms_to_iso(raw.get("start_time")),
        "ended_utc": epoch_ms_to_iso(raw.get("end_time")),
        "team_a": (raw.get("participants0_name") or "").strip() or None,
        "team_b": (raw.get("participants1_name") or "").strip() or None,
        "team_a_id": str(raw.get("participants0_id") or "") or None,
        "team_b_id": str(raw.get("participants1_id") or "") or None,
        "score_a": _int_or_none(raw.get("participants0_score")),
        "score_b": _int_or_none(raw.get("participants1_score")),
        "hotspawn_match_url": permalinks.get(fid) or "",
        "pages": [page],
        "source_url": page_url,
        "captured_utc": fetched,
        # Ownership only (how many Hotspawn players picked each side). Never a probability input.
        "ownership": {"crowd_pct_a": _int_or_none(p0), "crowd_pct_b": _int_or_none(p1),
                      "total_picks": _int_or_none(raw.get("total_picks"))},
    }


def collect_hotspawn(previous: dict | None) -> dict:
    pages, fixtures, week = [], {}, None
    leaderboard, permalinks = [], {}
    for page, url in HOTSPAWN_PAGES:
        rec = http_get(url, headers=HTML_HEADERS, timeout=60)
        entry = {"page": page, "url": url, "status": rec["status"], "bytes": rec["bytes"],
                 "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"], "error": rec["error"]}
        if rec["status"] == 200 and rec["body"]:
            parsed = parse_hotspawn_state(rec["body"].decode("utf-8", "replace"), page, url, rec["fetched_utc"])
            permalinks.update(parsed["permalinks"])
            entry.update(fixture_records=len(parsed["fixtures"]), error=parsed.get("error"),
                         header_matches_this_week=parsed["header_matches_this_week"],
                         filter_all_tiers=parsed["filter_all_tiers"], api_urls=parsed["api_urls"][:12])
            week = week or parsed["week"]
            if parsed["leaderboard_points"] and not leaderboard:
                leaderboard = parsed["leaderboard_points"]
            for raw in parsed["fixtures"]:
                fx = normalize_fixture(raw, page, url, rec["fetched_utc"], parsed["permalinks"])
                if fx["sport"] != "cs2":
                    continue
                if fx["match_id"] in fixtures:
                    if page not in fixtures[fx["match_id"]]["pages"]:
                        fixtures[fx["match_id"]]["pages"].append(page)
                    continue
                fixtures[fx["match_id"]] = fx
        pages.append(entry)
    for fid, fx in fixtures.items():
        if not fx["hotspawn_match_url"] and permalinks.get(fid):
            fx["hotspawn_match_url"] = permalinks[fid]
    ok = [p for p in pages if p["status"] == 200 and p.get("fixture_records")]
    result = {"mode": "live" if fixtures else "failed", "pages": pages, "week": week,
              "leaderboard_points": leaderboard,
              "fixtures": sorted(fixtures.values(), key=lambda f: (f["start_utc"] or "", f["match_id"])),
              "fetched_utc": max((p["fetched_utc"] for p in ok), default=None)}
    log(f"hotspawn: {len(fixtures)} CS2 fixtures from {len(ok)}/{len(pages)} pages")
    if not fixtures and previous and previous.get("fixtures"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        previous["latest_attempt"] = pages
        log(f"hotspawn: live read failed; keeping capture from {previous.get('fetched_utc')}")
        return previous
    return result


# ------------------------------------------------------------------ 2. Pinnacle
def collect_pinnacle(previous: dict | None) -> dict:
    matchups, rec_a = get_json(f"{PIN_BASE}/sports/12/matchups", headers=PIN_HEADERS, timeout=60)
    markets, rec_b = get_json(f"{PIN_BASE}/sports/12/markets/straight?primaryOnly=false&withSpecials=false",
                              headers=PIN_HEADERS, timeout=60)
    quotes = []
    if isinstance(matchups, list) and isinstance(markets, list):
        cs2 = {}
        for m in matchups:
            league = unescape(str((m.get("league") or {}).get("name") or ""))
            if league.startswith("CS2 - ") and m.get("id") is not None and not m.get("parentId"):
                cs2[str(m["id"])] = (m, league)
        seen = set()
        for mk in markets:
            mid = str(mk.get("matchupId"))
            if mid not in cs2 or mid in seen:
                continue
            if (mk.get("type") != "moneyline" or mk.get("period") != 0 or mk.get("isAlternate") is not False
                    or mk.get("status") != "open"):
                continue
            m, league = cs2[mid]
            parts = {p.get("alignment"): p.get("name") for p in (m.get("participants") or [])}
            prices = {p.get("designation"): p.get("price") for p in (mk.get("prices") or [])}
            if set(parts) != {"home", "away"} or set(prices) != {"home", "away"}:
                continue
            try:
                da, db = american_to_decimal(prices["home"]), american_to_decimal(prices["away"])
            except ValueError:
                continue
            seen.add(mid)
            quotes.append({
                "source": "Pinnacle", "role": "primary_bookmaker", "event_id": mid, "league": league,
                "team_a": unescape(str(parts["home"])), "team_b": unescape(str(parts["away"])),
                "start_utc": str(m.get("startTime") or "").replace("+00:00", "")[:19] + "Z",
                "best_of": m.get("bestOfX"), "native_a": prices["home"], "native_b": prices["away"],
                "native_format": "american", "odds_a": round(da, 6), "odds_b": round(db, 6),
                "is_live": bool(m.get("isLive")), "observed_utc": rec_b["fetched_utc"],
                "review_url": PIN_PAGE, "api_url": f"{PIN_BASE}/sports/12/markets/straight",
            })
    result = {"mode": "live" if quotes else "empty", "quotes": quotes,
              "status": [rec_a["status"], rec_b["status"]], "fetched_utc": rec_b["fetched_utc"]}
    log(f"pinnacle: {len(quotes)} CS2 moneylines (HTTP {rec_a['status']}/{rec_b['status']})")
    if not quotes and previous and previous.get("quotes"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        return previous
    return result


# ------------------------------------------------------------------ 3. bo3.gg
def collect_bo3(previous: dict | None) -> dict:
    matches, statuses = [], []
    offset, limit = 0, 100
    while offset <= 1500:
        params = [("page[offset]", str(offset)), ("page[limit]", str(limit)), ("sort", "start_date"),
                  ("filter[matches.status][in]", "upcoming"),
                  ("filter[matches.discipline_id][eq]", "1"), ("with", "teams,tournament")]
        data, rec = get_json(BO3_MATCHES + "?" + urllib.parse.urlencode(params))
        statuses.append(rec["status"])
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            break
        for m in data["results"]:
            if not isinstance(m, dict):
                continue
            tour = m.get("tournament") or {}
            t1, t2 = m.get("team1") or {}, m.get("team2") or {}
            bu = m.get("bet_updates") if isinstance(m.get("bet_updates"), dict) else None
            quote = None
            if bu and isinstance(bu.get("team_1"), dict) and isinstance(bu.get("team_2"), dict):
                quote = {"provider": bu.get("provider"), "book_url": bu.get("path"),
                         "coeff_1": bu["team_1"].get("coeff"), "coeff_2": bu["team_2"].get("coeff"),
                         "active_1": bu["team_1"].get("active"), "active_2": bu["team_2"].get("active"),
                         "name_1": bu["team_1"].get("name"), "name_2": bu["team_2"].get("name")}
            matches.append({
                "id": m.get("id"), "slug": m.get("slug"), "status": m.get("status"), "bo_type": m.get("bo_type"),
                "start_utc": str(m.get("start_date") or "")[:19] + "Z" if m.get("start_date") else None,
                "team_1": t1.get("name"), "team_2": t2.get("name"),
                "team_1_score": m.get("team1_score"), "team_2_score": m.get("team2_score"),
                "tournament": tour.get("name"), "tier": m.get("tier"),
                "url": f"https://bo3.gg/matches/{m.get('slug')}" if m.get("slug") else None,
                "quote": quote, "observed_utc": rec["fetched_utc"],
            })
        total = (data.get("total") or {}).get("count")
        if len(data["results"]) < limit or (total and offset + limit >= total):
            break
        offset += limit
        time.sleep(0.4)
    result = {"mode": "live" if matches else "empty", "matches": matches, "status": statuses,
              "fetched_utc": iso(now())}
    log(f"bo3.gg: {len(matches)} matches ({sum(1 for m in matches if m['quote'])} with a relayed price)")
    if not matches and previous and previous.get("matches"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        return previous
    return result


# ------------------------------------------------------------------ 4. Polymarket
def collect_polymarket(previous: dict | None) -> dict:
    events, statuses = [], []
    since = iso(now() - timedelta(hours=12))
    offset = 0
    while offset <= 1500:
        params = {"series_id": PM_SERIES_ID, "closed": "false", "limit": "100", "offset": str(offset),
                  "end_date_min": since}
        data, rec = get_json(PM_EVENTS + "?" + urllib.parse.urlencode(params))
        statuses.append(rec["status"])
        if not isinstance(data, list):
            break
        for ev in data:
            if not isinstance(ev, dict):
                continue
            for mk in ev.get("markets") or []:
                if not isinstance(mk, dict) or mk.get("closed"):
                    continue
                q = str(mk.get("question") or "")
                if mk.get("sportsMarketType") not in ("moneyline", None, "") or re.search(r"map\s*\d|game\s*\d", q, re.I):
                    continue
                try:
                    outcomes = json.loads(mk.get("outcomes") or "[]")
                    prices = [float(x) for x in json.loads(mk.get("outcomePrices") or "[]")]
                except (ValueError, TypeError):
                    continue
                if len(outcomes) != 2 or len(prices) != 2:
                    continue
                events.append({
                    "event_id": ev.get("id"), "slug": ev.get("slug"), "title": ev.get("title"),
                    "market_id": mk.get("id"), "question": q, "outcome_a": outcomes[0], "outcome_b": outcomes[1],
                    "price_a": prices[0], "price_b": prices[1], "best_bid": mk.get("bestBid"),
                    "best_ask": mk.get("bestAsk"), "liquidity": mk.get("liquidityNum") or mk.get("liquidity"),
                    "accepting_orders": mk.get("acceptingOrders"),
                    "start_utc": (str(mk.get("gameStartTime") or ev.get("startTime") or "").replace(" ", "T")[:19] + "Z"),
                    "url": f"https://polymarket.com/event/{ev.get('slug')}" if ev.get("slug") else None,
                    "observed_utc": rec["fetched_utc"],
                })
        if len(data) < 100:
            break
        offset += 100
        time.sleep(0.3)
    result = {"mode": "live" if events else "empty", "markets": events, "status": statuses,
              "fetched_utc": iso(now())}
    log(f"polymarket: {len(events)} open match-winner markets")
    if not events and previous and previous.get("markets"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        return previous
    return result


# ------------------------------------------------------------------ 5. Valve VRS
VRS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|")


def parse_vrs(md: str) -> list[dict]:
    rows = []
    for line_no, line in enumerate(md.splitlines(), start=1):
        m = VRS_ROW.match(line)
        if m:
            rows.append({"rank": int(m.group(1)), "points": int(m.group(2)), "team": m.group(3).strip(),
                         "roster": [p.strip() for p in m.group(4).split(",") if p.strip()], "line": line_no})
    return rows


def collect_vrs(previous: dict | None) -> dict:
    listing, rec = get_json(VRS_LISTING, headers={**JSON_HEADERS, "Accept": "application/vnd.github+json"})
    if isinstance(listing, list):
        files = sorted(e["name"] for e in listing if isinstance(e, dict)
                       and re.fullmatch(r"standings_global_\d{4}_\d{2}_\d{2}\.md", str(e.get("name"))))
        if files:
            name = files[-1]
            commits, _ = get_json(f"https://api.github.com/repos/{VRS_REPO}/commits?path=live/2026/{name}&per_page=1",
                                  headers={**JSON_HEADERS, "Accept": "application/vnd.github+json"})
            sha = commits[0]["sha"] if isinstance(commits, list) and commits else "main"
            raw = http_get(f"https://api.github.com/repos/{VRS_REPO}/contents/live/2026/{name}?ref={sha}",
                           headers={**JSON_HEADERS, "Accept": "application/vnd.github.raw"})
            if raw["status"] == 200 and raw["body"]:
                rows = parse_vrs(raw["body"].decode("utf-8", "replace"))
                if len(rows) > 50:
                    date = re.search(r"(\d{4})_(\d{2})_(\d{2})", name)
                    log(f"vrs: {name} @ {sha[:10]} — {len(rows)} teams")
                    return {"mode": "live", "file": name, "commit": sha,
                            "standings_date": f"{date.group(1)}-{date.group(2)}-{date.group(3)}",
                            "blob_url": f"https://github.com/{VRS_REPO}/blob/{sha}/live/2026/{name}",
                            "teams": rows, "fetched_utc": raw["fetched_utc"]}
    log(f"vrs: live read failed (HTTP {rec['status']})")
    if previous and previous.get("teams"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        return previous
    return {"mode": "failed", "teams": [], "fetched_utc": iso(now())}


# ------------------------------------------------------------------ 6. HLTV ranking
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]


def parse_hltv_ranking(html: str) -> tuple[str | None, list[dict]]:
    """Parse HLTV's world ranking page (same selectors as this repo's executive collector)."""
    teams = []
    for block in html.split('<div class="ranked-team standard-box">')[1:]:
        pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
        name = re.search(r'<span class="name">([^<]+)</span>', block)
        pts = re.search(r'<span class="points">\((\d+)', block)
        tid = re.search(r'href="/team/(\d+)/([^"]+)"', block)
        if pos and name:
            teams.append({"rank": int(pos.group(1)), "team": unescape(name.group(1)).strip(),
                          "points": int(pts.group(1)) if pts else None,
                          "url": f"https://www.hltv.org/team/{tid.group(1)}/{tid.group(2)}" if tid else None})
    date = re.search(r"World ranking on ([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", html)
    when = None
    if date and date.group(1).lower() in MONTHS:
        when = f"{int(date.group(3)):04d}-{MONTHS.index(date.group(1).lower()) + 1:02d}-{int(date.group(2)):02d}"
    return when, teams


def collect_hltv_ranking(previous: dict | None) -> dict:
    rec = http_get(HLTV_RANKING, headers=HTML_HEADERS, timeout=40, retries=1)
    if rec["status"] == 200 and rec["body"]:
        when, teams = parse_hltv_ranking(rec["body"].decode("utf-8", "replace"))
        if len(teams) >= 30:
            log(f"hltv ranking: {len(teams)} teams ({when})")
            return {"mode": "live", "ranking_date": when, "teams": teams, "fetched_utc": rec["fetched_utc"],
                    "url": (f"{HLTV_RANKING}/{when[:4]}/{MONTHS[int(when[5:7]) - 1]}/{int(when[8:])}"
                            if when else HLTV_RANKING)}
    log(f"hltv ranking: not readable from this runner (HTTP {rec['status']}); keeping previous capture")
    if previous and previous.get("teams"):
        previous = dict(previous)
        previous["mode"] = "previous_capture"
        previous["latest_attempt"] = {"status": rec["status"], "fetched_utc": rec["fetched_utc"]}
        return previous
    return {"mode": "failed", "teams": [], "fetched_utc": rec["fetched_utc"]}


# ------------------------------------------------------------------ main
def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = json.loads(CAPTURE.read_text()) if CAPTURE.exists() else {}
    started = iso(now())
    capture = {
        "schema": 1, "session": "arena/2e2b2e5e", "started_utc": started,
        "hotspawn": collect_hotspawn(previous.get("hotspawn")),
        "pinnacle": collect_pinnacle(previous.get("pinnacle")),
        "bo3": collect_bo3(previous.get("bo3")),
        "polymarket": collect_polymarket(previous.get("polymarket")),
        "vrs": collect_vrs(previous.get("vrs")),
        "hltv_ranking": collect_hltv_ranking(previous.get("hltv_ranking")),
    }
    capture["finished_utc"] = iso(now())
    capture["provenance"] = PROVENANCE
    CAPTURE.write_text(json.dumps(capture, indent=1, ensure_ascii=False) + "\n")
    modes = {k: capture[k].get("mode") for k in ("hotspawn", "pinnacle", "bo3", "polymarket", "vrs", "hltv_ranking")}
    log(f"capture written: {CAPTURE.relative_to(HERE.parent)} modes={modes}")
    # Fail only when there is no fixture list at all (a board without fixtures must not be published).
    return 0 if capture["hotspawn"].get("fixtures") else 2


if __name__ == "__main__":
    sys.exit(main())
