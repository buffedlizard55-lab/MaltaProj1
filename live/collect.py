#!/usr/bin/env python3
"""Session arena/459ff624 — live-slate collector.

Reads PUBLIC pages only and writes one provenance-stamped snapshot to
``live/data/snapshot.json``.  Runs on GitHub Actions (the agent sandbox has no
outbound access to these hosts); every step degrades gracefully — a source that
cannot be read leaves its fields empty and records the failure, it never
substitutes a guessed value.

Sources
  1. play.hotspawn.com/lobby, /cs2-pickems, /thp-pickems, /lol-pickems
     Angular SSR pages.  ``<script id="ng-state">`` (TransferState) carries every
     fixture: id, participants, competition, tier, stage, offered points,
     ``scheduled_start_time`` (13-digit epoch ms) and ``lock_offset_sec``.
     Used for FIXTURE IDENTITY AND TIMES ONLY.  The crowd pick percentages in
     the same payload are read for the coverage audit and dropped: build.py
     refuses to emit a dataset that contains them.
  2. Valve Regional Standings — Valve's own published standings file
     (github.com/ValveSoftware/counter-strike_regional_standings).  Official
     rating input for our own line, never a bookmaker price.
  3. Pinnacle public guest responses that the public matchups page loads by
     itself (no account, no API key, no licensed endpoint): whole-match
     moneyline.  American prices are converted to decimal.
  4. EGamersWorld public match pages — aggregated bookmaker prices, read in
     headless Chromium (a plain client gets HTTP 403).  Optional: used to fill
     fixtures Pinnacle does not list just yet.
  5. HLTV world ranking page (headless Chromium) — cross-check input only.

No login, no challenge solving, no private endpoint.  Raw bodies stay out of
Git: only URL, status, byte size, SHA-256 and fetch time are kept.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "live" / "data"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
]
VRS_DIR_API = ("https://api.github.com/repos/ValveSoftware/"
               "counter-strike_regional_standings/contents/live/2026")
PINNACLE_MATCHUPS = ("https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups"
                     "?withSpecials=false")
PINNACLE_MARKETS = ("https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/"
                    "straight?primaryOnly=false&withSpecials=false")
PINNACLE_PAGES = ["https://www.pinnacle.com/en/esports/games/cs2/matchups/"]
EGW_LIST = "https://egamersworld.com/counterstrike/matches"
POLYMARKET_API = ("https://gamma-api.polymarket.com/markets?closed=false&limit=500"
                  "&order=volume24hr&ascending=false")
HLTV_RANKING = "https://www.hltv.org/ranking/teams/2026/october/12"

STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
DOM_MATCH_LINK = re.compile(r'https://www\.hotspawn\.com/matches/([a-z0-9\-]+?)-(\d{6,8})\b', re.I)
EGW_MATCH_LINK = re.compile(r'href="(https://egamersworld\.com/counterstrike/match/[^"#?]+)"')
SKIP_ROOT_KEYS = {"participants"}

BROWSER_HOSTS = ("egamersworld.com", "hltv.org", "pinnacle.com")
BUDGET_SECONDS = int(__import__("os").environ.get("LIVE_BUDGET_SECONDS", "900"))
DEADLINE = time.time() + BUDGET_SECONDS

provenance: list[dict] = []
_browser = None
_browser_failed = False


# --------------------------------------------------------------------- plumbing
def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(entry: dict) -> None:
    provenance.append(entry)


def http_get(url: str, timeout: int = 45, accept: str | None = None) -> dict:
    headers = dict(HEADERS)
    if accept:
        headers["Accept"] = accept
    req = Request(url, headers=headers)
    stamp = now_iso()
    entry = {"url": url, "fetched_utc": stamp, "path": "http", "status": None,
             "bytes": None, "sha256": None, "error": None}
    body = b""
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(20_000_000)
            entry.update(status=resp.status, bytes=len(body),
                         sha256=hashlib.sha256(body).hexdigest())
    except HTTPError as exc:
        entry.update(status=exc.code, error=f"HTTPError {exc.code}")
    except (URLError, TimeoutError, OSError) as exc:
        entry.update(error=f"{type(exc).__name__}: {exc}")
    record(entry)
    return {**entry, "body": body}


def browser_session():
    """Headless Chromium, used only where a plain client is refused."""
    global _browser, _browser_failed
    if _browser_failed:
        return None
    if _browser is None:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:  # noqa: BLE001
            print(f"[collect] playwright unavailable: {type(exc).__name__}: {exc}", flush=True)
            _browser_failed = True
            return None
        try:
            _browser = sync_playwright().start().chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        except Exception as exc:  # noqa: BLE001
            print(f"[collect] chromium launch failed: {type(exc).__name__}: {exc}", flush=True)
            _browser_failed = True
            return None
    return _browser


def browser_get(url: str, wait_ms: int = 2500) -> dict:
    """Render a public page; also keep any JSON bodies the page itself loads."""
    stamp = now_iso()
    entry = {"url": url, "fetched_utc": stamp, "path": "browser", "status": None,
             "bytes": None, "sha256": None, "error": None}
    if time.time() > DEADLINE:
        entry["error"] = "collection budget reached"
        record(entry)
        return {**entry, "html": None, "captured": []}
    browser = browser_session()
    if browser is None:
        entry["error"] = "browser unavailable"
        record(entry)
        return {**entry, "html": None, "captured": []}
    captured: list[dict] = []
    context = browser.new_context(user_agent=UA, locale="en-US",
                                  viewport={"width": 1366, "height": 900},
                                  extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
    page = context.new_page()
    seen: set[str] = set()

    def on_response(resp):
        ctype = (resp.headers or {}).get("content-type", "")
        if "json" not in ctype or resp.url in seen:
            return
        if "arcadia.pinnacle.com" not in resp.url:
            return
        seen.add(resp.url)
        try:
            captured.append({"url": resp.url, "status": resp.status, "body": resp.json()})
        except Exception:  # noqa: BLE001
            pass

    page.on("response", on_response)
    html = None
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        entry.update(status=resp.status if resp else None,
                     bytes=len(html.encode("utf-8")),
                     sha256=hashlib.sha256(html.encode("utf-8")).hexdigest())
    except Exception as exc:  # noqa: BLE001
        entry["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            context.close()
        except Exception:  # noqa: BLE001
            pass
    record(entry)
    return {**entry, "html": html, "captured": captured}


# ------------------------------------------------------------------- Hotspawn
def ms_to_iso(value) -> str | None:
    if isinstance(value, bool) or value is None:
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 13:
        return None
    try:
        return datetime.fromtimestamp(int(digits) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


def first(node: dict, *names, default=None):
    for name in names:
        if name in node and node[name] not in (None, "", [], {}):
            return node[name]
    return default


def walk_fixture_nodes(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        if "scheduled_start_time" in node and ({"participants0_name"} <= set(node)
                                               or {"participants0_id"} <= set(node)):
            out.append(node)
        for value in node.values():
            walk_fixture_nodes(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_fixture_nodes(item, out)


def text_of(html: str) -> str:
    plain = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    plain = re.sub(r"(?s)<[^>]+>", " ", plain)
    return re.sub(r"\s+", " ", unescape(plain)).strip()


def collect_hotspawn() -> dict:
    fixtures: dict[str, dict] = {}
    pages: list[dict] = []
    week_text = None
    reset_in = None
    crowd_seen = 0
    for page_name, url in HOTSPAWN_PAGES:
        got = http_get(url)
        page = {"page": page_name, "url": url, "status": got["status"], "bytes": got["bytes"],
                "sha256": got["sha256"], "error": got["error"], "state_rows": 0,
                "cards": 0, "week_text": None, "reset_text": None}
        body = got["body"].decode("utf-8", errors="replace") if got["body"] else ""
        if body:
            page["cards"] = len(re.findall(r"<app-pickem-vs-card\b", body, re.I))
            plain = text_of(body)
            m = re.search(r"(\d+)\s+matches this week", plain)
            if m:
                page["week_text"] = f"{m.group(1)} matches this week"
                week_text = week_text or page["week_text"]
            m = re.search(r"Resets in ((?:\d+d )?(?:\d+h )?(?:\d+m )?(?:\d+s))", plain)
            if m:
                page["reset_text"] = m.group(1)
                reset_in = reset_in or page["reset_text"]
            links = {m2.group(2): m2.group(0) for m2 in DOM_MATCH_LINK.finditer(body)}
            m = STATE_SCRIPT.search(body)
            if not m:
                page["error"] = (page["error"] or "") + " ng-state not found"
            else:
                try:
                    state = json.loads(unescape(m.group(1)).strip())
                except json.JSONDecodeError as exc:
                    page["error"] = (page["error"] or "") + f" ng-state JSON: {exc}"
                else:
                    nodes: list[dict] = []
                    walk_fixture_nodes(state, nodes)
                    page["state_rows"] = len(nodes)
                    for node in nodes:
                        match_id = str(first(node, "id", "match_id", default=""))
                        team_a = first(node, "participants0_name", "teamA")
                        team_b = first(node, "participants1_name", "teamB")
                        start = ms_to_iso(first(node, "scheduled_start_time", "scheduledStartTime"))
                        if not (match_id and team_a and team_b and start):
                            continue
                        offset = first(node, "lock_offset_sec", "lockOffsetSec")
                        lock = ms_to_iso(first(node, "lock_time", "lockTime"))
                        if not lock and isinstance(offset, (int, float)) and 0 < offset < 7200:
                            lock = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
                                    .replace(tzinfo=timezone.utc) - timedelta(seconds=int(offset))
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        participants = node.get("participants")
                        crowd = [first(node, "participants0_picked_percent", "participants0_picked"),
                                 first(node, "participants1_picked_percent", "participants1_picked"),
                                 first(node, "total_picks", "picks_count")]
                        if isinstance(participants, list) and len(participants) >= 2 and crowd[0] is None:
                            crowd[0] = first(participants[0], "picked_percent", "picked")
                            crowd[1] = first(participants[1], "picked_percent", "picked")
                        row = {
                            "match_id": match_id,
                            "hotspawn_page": page_name,
                            "sport": first(node, "sport_alias", "sport", "game_alias"),
                            "competition": first(node, "competition_name", "competitionName",
                                                 "competition", "tournament"),
                            "status": first(node, "status", "match_status"),
                            "tier": str(first(node, "tier", "tier_name", default="")).lower() or None,
                            "stage": first(node, "stage", "stage_name"),
                            "start_utc": start,
                            "lock_utc": lock,
                            "lock_offset_sec": int(offset) if isinstance(offset, (int, float)) else None,
                            "team_a": team_a,
                            "team_b": team_b,
                            "team_a_id": str(first(node, "participants0_id", "teamA_id", default="")) or None,
                            "team_b_id": str(first(node, "participants1_id", "teamB_id", default="")) or None,
                            "offered_points": first(node, "offered_points", "offeredPoints", "points"),
                            "base_points": first(node, "base_points", "basePoints"),
                            "started_utc": ms_to_iso(node.get("started_time")),
                            "ended_utc": ms_to_iso(node.get("ended_time")),
                            "hotspawn_match_url": links.get(match_id),
                            "source_url": url,
                            "snapshot_utc": None,
                            "payload_keys": sorted(k for k in node if not k.startswith("_")),
                            "participant_keys": (
                                sorted({k for p in participants if isinstance(p, dict)
                                        for k in p}) if isinstance(participants, list) else []),
                            # crowd fields are kept ONLY for the audit page; build.py drops them
                            "crowd_pct_a": crowd[0],
                            "crowd_pct_b": crowd[1],
                            "crowd_total_picks": crowd[2],
                        }
                        if crowd[0] is not None or crowd[1] is not None:
                            crowd_seen += 1
                        known = fixtures.get(match_id)
                        if known:
                            if page_name not in known["_pages"]:
                                known["_pages"].append(page_name)
                            for key, value in row.items():
                                if known.get(key) in (None, "") and value not in (None, ""):
                                    known[key] = value
                        else:
                            row["_pages"] = [page_name]
                            fixtures[match_id] = row
        pages.append(page)
        time.sleep(0.3)
    rows = sorted(fixtures.values(), key=lambda r: (r["start_utc"], r["match_id"]))
    for row in rows:
        row["snapshot_utc"] = now_iso()
    return {"pages": pages, "fixtures": rows, "week_text": week_text,
            "reset_text": reset_in, "fixtures_with_crowd_fields": crowd_seen}


# --------------------------------------------------------------- Valve standings
VRS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]{1,80}?)\s*\|", re.M)


def collect_vrs() -> dict:
    listing = http_get(VRS_DIR_API, accept="application/vnd.github+json")
    files: list[str] = []
    if listing["body"]:
        try:
            entries = json.loads(listing["body"].decode())
            files = [e["path"] for e in entries if re.search(r"standings_global_\d{4}_\d{2}_\d{2}\.md$",
                                                             e.get("path", ""))]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            record({"url": VRS_DIR_API, "fetched_utc": now_iso(), "path": "parse",
                    "status": listing["status"], "bytes": None, "sha256": None,
                    "error": f"listing parse: {exc}"})
    if not files:
        return {"status": "unavailable", "url": VRS_DIR_API, "as_of": None, "teams": []}
    latest = sorted(files)[-1]
    raw_url = ("https://raw.githubusercontent.com/ValveSoftware/"
               "counter-strike_regional_standings/main/" + latest)
    got = http_get(raw_url)
    teams = []
    as_of = None
    if got["body"]:
        md = got["body"].decode("utf-8", errors="replace")
        m = re.search(r"as of (\d{4}_\d{2}_\d{2})", md, re.I)
        as_of = m.group(1).replace("_", "-") if m else None
        for rank, points, name in VRS_ROW.findall(md):
            teams.append({"vrs_rank": int(rank), "name": name.strip(), "points": float(points)})
    return {"status": "observed" if teams else "unavailable", "url": raw_url,
            "listing_url": VRS_DIR_API, "file": latest, "as_of": as_of,
            "sha256": got["sha256"], "fetched_utc": got["fetched_utc"], "teams": teams}


# ------------------------------------------------------------------- Pinnacle
def american_to_decimal(value) -> float | None:
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price <= 100 and price >= -100:  # not a valid American price
        return None
    return round(1 + (price / 100 if price > 0 else 100 / abs(price)), 6)


def iso_utc(value) -> str | None:
    """Accept the several ISO spellings a public API may use, return one canonical spelling."""
    if not isinstance(value, str) or len(value) < 16:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_pinnacle(matchups: list, markets: list, observed_url: str) -> list[dict]:
    events = {}
    for node in matchups:
        if isinstance(node, dict) and isinstance(node.get("id"), int):
            events.setdefault(node["id"], node)
    quotes = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        if market.get("type") != "moneyline" or market.get("period") != 0:
            continue
        if market.get("isAlternate") is not False:
            continue
        if market.get("status") != "open":
            continue
        event = events.get(market.get("matchupId"))
        if not event:
            continue
        league = event.get("league") or {}
        if (league.get("sport") or {}).get("id") != 12:
            continue
        if not str(league.get("name", "")).startswith("CS2 - "):
            continue
        if event.get("parentId") is not None or event.get("type") != "matchup":
            continue
        participants = event.get("participants") or []
        prices = market.get("prices") or []
        if len(participants) != 2 or len(prices) != 2:
            continue
        names = {p.get("alignment"): p.get("name") for p in participants}
        native = {p.get("designation"): p.get("price") for p in prices}
        if set(names) != {"home", "away"} or set(native) != {"home", "away"}:
            continue
        odds_a = american_to_decimal(native["home"])
        odds_b = american_to_decimal(native["away"])
        start_utc = iso_utc(event.get("startTime"))
        if not (start_utc and odds_a and odds_b):
            continue
        quotes.append({
            "bookmaker": "Pinnacle",
            "bookmaker_role": "primary_bookmaker",
            "market": "match_winner",
            "team_a": names["home"], "team_b": names["away"],
            "start_utc": start_utc,
            "odds_a": odds_a, "odds_b": odds_b,
            "native_a": native["home"], "native_b": native["away"],
            "native_format": "american",
            "league": league.get("name"),
            "event_id": str(event.get("id")),
            "observed_utc": now_iso(),
            "api_url": observed_url,
            "source_url": f"https://www.pinnacle.com/en/esports/matchups/highlights/",
            "note": "Decimal odds converted from the American prices in the public guest response "
                    "the matchups page loads itself; not a rounded website display value.",
        })
    return quotes


def collect_pinnacle() -> dict:
    quotes: list[dict] = []
    matchups_body = http_get(PINNACLE_MATCHUPS)
    markets_body = http_get(PINNACLE_MARKETS)
    if matchups_body["body"] and markets_body["body"]:
        try:
            matchups = json.loads(matchups_body["body"].decode())
            markets = json.loads(markets_body["body"].decode())
            quotes = parse_pinnacle(matchups, markets, PINNACLE_MATCHUPS)
        except (json.JSONDecodeError, TypeError) as exc:
            record({"url": PINNACLE_MARKETS, "fetched_utc": now_iso(), "path": "parse",
                    "status": None, "bytes": None, "sha256": None,
                    "error": f"pinnacle JSON: {exc}"})
    if not quotes:
        for page_url in PINNACLE_PAGES:
            got = browser_get(page_url, wait_ms=4000)
            matchups = [c["body"] for c in got["captured"] if "/matchups" in c["url"]
                        and isinstance(c["body"], list)]
            markets = [c["body"] for c in got["captured"] if "/markets/" in c["url"]
                       and isinstance(c["body"], list)]
            if matchups and markets:
                quotes = parse_pinnacle([e for body in matchups for e in body],
                                        [m for body in markets for m in body],
                                        got["captured"][0]["url"])
                if quotes:
                    break
    return {"status": "observed" if quotes else "unavailable", "quotes": quotes}


# ---------------------------------------------------------------- EGamersWorld
PRICE_TOKEN = re.compile(r">\s*(\d{1,2}\.\d{1,3})\s*<")


def egw_fixture_pair(url: str) -> tuple[str, str] | None:
    slug = url.rstrip("/").split("/")[-1]
    m = re.match(r"(.+?)-vs-(.+)$", slug, re.I)
    if not m:
        return None
    tail = re.sub(r"-(?:[A-Za-z0-9_\-]{6,14})$", "", m.group(2))
    return (m.group(1).replace("-", " ").strip(), tail.replace("-", " ").strip())


def parse_egw_odds(html: str) -> list[float]:
    """Two-way decimal pair from the page's own odds markup, or nothing."""
    plain = re.sub(r"\s+", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html))
    for match in PRICE_TOKEN.finditer(plain):
        window = plain[match.start(): match.start() + 260]
        pair = [float(x) for x in PRICE_TOKEN.findall(window)][:2]
        if len(pair) == 2 and pair[0] != pair[1] and all(1.01 <= x <= 40 for x in pair):
            return pair
    return []


def collect_egw(limit: int = 14) -> dict:
    got = browser_get(EGW_LIST, wait_ms=4000)
    listing = []
    html = got["html"] or ""
    for m in EGW_MATCH_LINK.finditer(html):
        url = m.group(1)
        window = html[m.end(): m.end() + 1600]
        prices = [float(p) for p in PRICE_TOKEN.findall(window)][:2]
        pair = egw_fixture_pair(url)
        if not pair:
            continue
        listing.append({"url": url, "team_a": pair[0], "team_b": pair[1],
                        "list_prices": prices if len(prices) == 2 and prices[0] != prices[1] else []})
    detail = []
    seen = {row["url"] for row in listing}
    for row in listing:
        if len(detail) >= limit or time.time() > DEADLINE:
            break
        page = browser_get(row["url"], wait_ms=2500)
        prices = parse_egw_odds(page["html"] or "")
        detail.append({**row, "url": row["url"], "prices": prices,
                       "status": page["status"], "error": page["error"]})
    return {"status": "observed" if listing else "unavailable", "listing_url": EGW_LIST,
            "listing": listing, "detail": detail, "seen_urls": sorted(seen)}


# ------------------------------------------------------------------- Polymarket
def _json_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def collect_polymarket() -> dict:
    """Public prediction-market prices for CS2 matches.

    Kept strictly separate from bookmaker prices: a prediction market is a different
    instrument, it is labelled as such on every row that uses it, and it is only
    published for a fixture pair whose two outcome names both match the fixture.
    """
    got = http_get(POLYMARKET_API, accept="application/json")
    quotes, skipped = [], 0
    if got["body"]:
        try:
            markets = json.loads(got["body"].decode())
        except json.JSONDecodeError as exc:
            record({"url": POLYMARKET_API, "fetched_utc": now_iso(), "path": "parse", "status": None,
                    "bytes": None, "sha256": None, "error": f"polymarket JSON: {exc}"})
            markets = []
        for market in markets if isinstance(markets, list) else []:
            if not isinstance(market, dict):
                continue
            slug = str(market.get("slug") or "")
            question = str(market.get("question") or "")
            if "cs2-" not in slug.lower() and "counter-strike" not in question.lower():
                continue
            outcomes = _json_list(market.get("outcomes"))
            prices = _json_list(market.get("outcomePrices"))
            if not (outcomes and prices and len(outcomes) == 2 == len(prices)):
                skipped += 1
                continue
            try:
                p_a, p_b = float(prices[0]), float(prices[1])
            except (TypeError, ValueError):
                skipped += 1
                continue
            if not (0.01 < p_a < 0.99 and 0.01 < p_b < 0.99):
                skipped += 1
                continue
            quotes.append({
                "bookmaker": "Polymarket",
                "kind": "prediction_market",
                "market": "match_winner",
                "team_a": str(outcomes[0]), "team_b": str(outcomes[1]),
                "start_utc": iso_utc(market.get("gameStartTime") or market.get("startDate")),
                "implied_p_a": round(100 * p_a, 1), "implied_p_b": round(100 * p_b, 1),
                "odds_a": round(1 / p_a, 6), "odds_b": round(1 / p_b, 6),
                "observed_utc": now_iso(),
                "source_url": f"https://polymarket.com/event/{slug}" if slug else POLYMARKET_API,
                "note": ("Prediction-market price converted to implied probability; not a "
                         "bookmaker price and not de-vigged."),
                "volume_usd": market.get("volumeNum") or market.get("volume"),
                "liquidity_usd": market.get("liquidityNum") or market.get("liquidity"),
            })
    return {"status": "observed" if quotes else "unavailable", "api_url": POLYMARKET_API,
            "quotes": quotes, "skipped_markets": skipped}


# ------------------------------------------------------------------------ HLTV
HLTV_TEAM_LINK = re.compile(r'/team/(\d+)/([a-z0-9\-]+)', re.I)
HLTV_BLOCK_SPLIT = re.compile(r'class="ranked-team', re.I)
HLTV_POSITION = re.compile(r'class="position"[^>]*>\s*#?(\d+)', re.I)


def parse_hltv_ranking(html: str) -> dict[str, int]:
    """Several spellings of the same page have shipped; try the documented shapes in turn."""
    ranks: dict[str, int] = {}
    blocks = HLTV_BLOCK_SPLIT.split(html)[1:]
    for block in blocks:
        window = block[:4000]
        position = HLTV_POSITION.search(window)
        link = HLTV_TEAM_LINK.search(window)
        if position and link:
            ranks[link.group(2).replace("-", " ")] = int(position.group(1))
    if len(ranks) < 10:
        for position, link in zip(HLTV_POSITION.finditer(html), HLTV_TEAM_LINK.finditer(html)):
            if link.start() > position.start():
                ranks.setdefault(link.group(2).replace("-", " "), int(position.group(1)))
    return ranks


def collect_hltv(names: set[str]) -> dict:
    got = browser_get(HLTV_RANKING, wait_ms=3000)
    html = got["html"] or ""
    ranks = parse_hltv_ranking(html)
    marker = html.lower().find('class="position"')
    if marker < 0:
        marker = html.find("/team/")
    sample = re.sub(r"\s+", " ", html[max(0, marker - 200): marker + 600]) if marker >= 0 else ""
    if not sample:
        sample = re.sub(r"\s+", " ", html[:600])
    record({"url": f"{HLTV_RANKING}#markup", "fetched_utc": got["fetched_utc"], "path": "diagnostic",
            "status": got["status"], "bytes": len(html), "sha256": None,
            "error": None if sample else "empty page"})
    hit = {n: r for n, r in ranks.items() if n.lower() in {x.lower() for x in names}}
    return {"status": "observed" if ranks else "unavailable", "url": HLTV_RANKING,
            "total_rows": len(ranks), "ranks": ranks, "matched": hit,
            "fetched_utc": got["fetched_utc"], "sha256": got["sha256"],
            "debug_sample": sample[:600]}


# ------------------------------------------------------------------------ main
def main() -> int:
    started = now_iso()
    print(f"[collect] start {started} budget={BUDGET_SECONDS}s", flush=True)
    hotspawn = collect_hotspawn()
    print(f"[collect] hotspawn fixtures={len(hotspawn['fixtures'])}", flush=True)
    vrs = collect_vrs()
    print(f"[collect] valve VRS teams={len(vrs['teams'])} as_of={vrs['as_of']}", flush=True)
    pinnacle = collect_pinnacle()
    print(f"[collect] pinnacle quotes={len(pinnacle['quotes'])}", flush=True)
    egw = collect_egw()
    print(f"[collect] egw listing={len(egw['listing'])} detail={len(egw['detail'])}", flush=True)
    polymarket = collect_polymarket()
    print(f"[collect] polymarket quotes={len(polymarket['quotes'])}", flush=True)
    cs2_names = {row["team_a"] for row in hotspawn["fixtures"] if row.get("sport") == "cs2"}
    cs2_names |= {row["team_b"] for row in hotspawn["fixtures"] if row.get("sport") == "cs2"}
    hltv = collect_hltv(cs2_names)
    print(f"[collect] hltv ranks={len(hltv['ranks'])}", flush=True)

    snapshot = {
        "schema": 1,
        "session": "arena/459ff624",
        "generated_utc": now_iso(),
        "collection_started_utc": started,
        "week_text": hotspawn["week_text"],
        "reset_text": hotspawn["reset_text"],
        "hotspawn_pages": hotspawn["pages"],
        "fixtures": hotspawn["fixtures"],
        "fixtures_with_crowd_fields": hotspawn["fixtures_with_crowd_fields"],
        "vrs": vrs,
        "pinnacle": pinnacle,
        "egw": egw,
        "polymarket": polymarket,
        "hltv": hltv,
        "provenance": provenance,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "snapshot.json"
    out.write_text(json.dumps(snapshot, indent=1, sort_keys=False))
    print(f"[collect] wrote {out} ({out.stat().st_size} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
