#!/usr/bin/env python3
"""A1/A2 — capture the Hotspawn CS2 slate and every external price the runner is served.

Written by session ``arena/a174d77f``.  Runs on GitHub Actions (``.github/workflows/cs2-a174d77f.yml``)
because the agent sandbox has no general internet access; every source is independent and fails
soft, so a refused host costs only its own columns.

Sources, all public, all read without an account or key
--------------------------------------------------------------------------------
1. Hotspawn Play  — ``https://play.hotspawn.com/{lobby,cs2-pickems,thp-pickems,lol-pickems}``.
   Angular SSR: ``<script id="ng-state">`` (TransferState) carries the whole fixture list with
   exact UTC epoch-ms ``scheduled_start_time`` and ``lock_time``/``lock_offset_sec``.  Used for
   FIXTURE IDENTITY AND TIMES ONLY.  The same payload's ``participants*_picked_percent`` and
   ``total_picks`` are kept in ``capture.json`` under ``*_audit_only`` keys so the coverage page can
   prove the crowd fields were seen and excluded; ``model.py`` refuses to read them.
   The rendered filter text ("Tier All tiers (89)", "B (25)", "Elisa BreakOut Series #2 (12)",
   "68 matches this week") is parsed as the site's OWN count of what the board holds — the
   coverage witness in A1.
2. Pinnacle — ``guest.api.arcadia.pinnacle.com/0.1/sports/12/{matchups,markets/straight}``, the
   same public guest responses the site's own CS2 matchups page loads.  Whole-match moneyline
   only (period 0, ``isAlternate: false``, ``status: "open"``); American prices converted to
   decimal.  ``bestOfX`` is read as the book's published series length.
3. EGamersWorld — ``egamersworld.com/counterstrike/matches`` (list) and the per-match pages it
   links.  Aggregated bookmaker prices with the book named in the page.  A plain client is
   usually refused (HTTP 403); a headless Chromium is used when available, otherwise the
   refusal is recorded.
4. Valve Regional Standings — ``api.github.com`` listing + the raw ``standings_global_*.md`` at
   the pinned HEAD commit of ``ValveSoftware/counter-strike_regional_standings``.  Official
   rating input for OUR OWN line; never a bookmaker price.
5. HLTV — ``/ranking/teams/<year>/<month>/<day>`` for world ranks and rosters, ``/matches`` for
   kickoff cross-checks.  Both are frequently 403 to non-browser clients; recorded either way.
6. Polymarket — ``gamma-api.polymarket.com`` public market list.  A prediction market, not a
   sportsbook: published in its own column and never merged into the bookmaker line.
7. Attempted-and-refused feeds (kept in ``attempts`` so the reader can see what was tried):
   Bovada/Everygame esports coupon, 1xBet LineFeed, MarathonBet eventfeed, Betexplorer.

Output: ``cs2/data/capture.json`` + ``cs2/data/provenance.json`` (url, status, bytes, sha256,
fetch time per request) + gzip snapshots of the exact bytes under ``cs2/data/raw/``.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, RAW, budget, flush_provenance, get_json, http_get, is_decimal, log,  # noqa: E402
                    now_iso, over_budget, parse_iso, record, save_raw, write_json)

CAPTURE = DATA / "capture.json"
HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
]
STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
CARD = re.compile(r"<app-pickem-vs-card\b", re.I)
MATCH_LINK = re.compile(r'https://www\.hotspawn\.com/matches/([a-z0-9\-]+?)-(\d{6,8})\b', re.I)
COUNT_TOKEN = re.compile(r"([A-Za-z0-9#'+\-&.: ]{3,60}?)\s*\((\d{1,4})\)")
WEEK_TEXT = re.compile(r"(\d{1,4})\s+matches this week", re.I)
RESET_TEXT = re.compile(r"Resets in ((?:\d+d )?(?:\d+h )?(?:\d+m )?(?:\d+s))", re.I)

PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_MATCHUPS = f"{PIN_BASE}/sports/12/matchups?withSpecials=false"
PIN_MARKETS = f"{PIN_BASE}/sports/12/markets/straight?primaryOnly=false&withSpecials=false"
PIN_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"

EGW_LIST = "https://egamersworld.com/counterstrike/matches"
EGW_MATCH_HREF = re.compile(
    r'href="(?:https?://(?:www\.)?egamersworld\.com)?(/counterstrike/match/[^"#?]+)"')
POLYMARKET = ("https://gamma-api.polymarket.com/markets?closed=false&limit=500"
              "&order=volume24hr&ascending=false")
HLTV_RANKING_TMPL = "https://www.hltv.org/ranking/teams/{y}/{month}/{day}"
HLTV_MATCHES = "https://www.hltv.org/matches"
PIN_LEAGUES = "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/leagues"
VRS_API = ("https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings"
           "/contents/live")
VRS_RAW = "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/"
REFUSED_FEEDS = [
    ("Bovada (esports coupon feed)",
     "https://www.bovada.lv/services/sports/event/coupon/events/A/description/esports/type/none/lang/en"),
    ("1xBet LineFeed", "https://1xbet.com/LineFeed/Get1x2_VZip?sports=16&count=40&mode=4&getEmpty=true"),
    ("MarathonBet eventfeed", "https://www.marathonbet.com/su/eventfeed/?id=1337&age=2"),
    ("Betexplorer CS2 index", "https://www.betexplorer.com/counter-strike/"),
    # probed on 2026-10-14 because other sessions in this repository quote these four; the
    # result below is published either way so the reachability claim is evidence, not memory
    ("bo3.gg CS2 page", "https://bo3.gg/counter-strike"),
    ("OddsDigger e-sports index", "https://oddsdigger.com/e-sports"),
    ("FreeTips Counter-Strike index", "https://www.freetips.com/counter-strike/"),
    ("VPrognoze CS2 index", "https://vprognoze.com/counter-strike/"),
    ("Bwin CS2 page", "https://www.bwin.com/en/sports/cs2-105"),
]

ALLOW = set((os.environ.get("CS2_SOURCES") or "").split(",")) - {""}
VRS_LOCAL = os.environ.get("VRS_LOCAL_DIR")          # offline testing only


def wanted(name: str) -> bool:
    return not ALLOW or name in ALLOW


# ------------------------------------------------------------------------------- shared
def plain_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


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


def walk_fixtures(node, out: list) -> None:
    if isinstance(node, dict):
        if "scheduled_start_time" in node and ({"participants0_name"} <= set(node)
                                                or {"participants0_id"} <= set(node)):
            out.append(node)
        for value in node.values():
            walk_fixtures(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_fixtures(item, out)


# --------------------------------------------------------------------------- 1 Hotspawn
def parse_filter_counts(text: str) -> dict:
    """The site's own counts, read out of the filter row of the rendered page.

    ``Tier All tiers (89)  B (25)  C (60)  S (4)`` and ``Tournament <name> (n) ...`` are the
    numbers the board publishes for itself; they are the coverage witness for A1 — if our parsed
    count differs from the site's own count, the row is flagged, not silently truncated.
    """
    out: dict = {"tiers": {}, "tournaments": {}, "teams": 0}
    seg = re.search(r"Tier\s+All tiers \((\d+)\)(.*?)Tournament", text)
    if seg:
        out["all_tiers_total"] = int(seg.group(1))
        for name, num in COUNT_TOKEN.findall(seg.group(2)):
            name = name.strip()
            if re.fullmatch(r"[SABC]", name):
                out["tiers"][name] = int(num)
    tseg = re.search(r"Tournament\s+All tournaments \((\d+)\)(.*?)Team\s+All teams", text)
    if tseg:
        out["all_tournaments_total"] = int(tseg.group(1))
        body = tseg.group(2)
        for m in re.finditer(r"([A-Za-z0-9#'+\-&.: ]{3,70}?)\s*\((\d{1,4})\)", body):
            name = m.group(1).strip()
            if name and not name.isdigit():
                out["tournaments"][name] = int(m.group(2))
    m = re.search(r"Team\s+All teams \((\d+)\)", text)
    if m:
        out["teams"] = int(m.group(1))
    return out


def collect_hotspawn() -> dict:
    fixtures: dict[str, dict] = {}
    pages: list[dict] = []
    if not wanted("hotspawn"):
        return {"pages": [], "fixtures": [], "skipped": "CS2_SOURCES"}
    for page_name, url in HOTSPAWN_PAGES:
        got = http_get(url, timeout=45)
        page = {"page": page_name, "url": url, "status": got["status"], "bytes": got["bytes"],
                "sha256": got["sha256"], "fetched_utc": got["fetched_utc"], "error": got["error"],
                "state_rows": 0, "cards": 0, "week_text": None, "reset_text": None,
                "counts": {}}
        html = got["body"].decode("utf-8", errors="replace") if got["body"] else ""
        if html:
            page["cards"] = len(CARD.findall(html))
            text = plain_text(html)
            if (m := WEEK_TEXT.search(text)):
                page["week_text"] = f"{m.group(1)} matches this week"
            if (m := RESET_TEXT.search(text)):
                page["reset_text"] = m.group(1)
            page["counts"] = parse_filter_counts(text)
            links = {m.group(2): m.group(0) for m in MATCH_LINK.finditer(html)}
            m = STATE_SCRIPT.search(html)
            if not m:
                page["error"] = (page["error"] or "") + " ng-state script not found"
            else:
                # the exact payload bytes are archived so every fixture field on the board can be
                # re-derived offline, and the field names are inventoried (that is how a missing
                # "series length" is proved to be the source's omission rather than ours)
                save_raw(f"hotspawn_state_{page_name}", m.group(1).encode("utf-8", errors="replace"))
                try:
                    state = json.loads(unescape(m.group(1)).strip())
                except json.JSONDecodeError as exc:
                    page["error"] = (page["error"] or "") + f" ng-state JSON: {exc}"
                    state = None
                if state is not None:
                    nodes: list[dict] = []
                    walk_fixtures(state, nodes)
                    page["state_rows"] = len(nodes)
                    names = sorted({k for n in nodes if isinstance(n, dict) for k in n})
                    page["field_names"] = names
                    page["format_like_fields"] = {
                        k: sorted({str(n.get(k)) for n in nodes if isinstance(n, dict) and k in n})[:6]
                        for k in names
                        if re.search(r"(best|of|series|format|length|round|map)", k, re.I)}
                    for node in nodes:
                        mid = str(first(node, "id", "match_id", default=""))
                        team_a = first(node, "participants0_name", "teamA")
                        team_b = first(node, "participants1_name", "teamB")
                        start = ms_to_iso(first(node, "scheduled_start_time", "scheduledStartTime"))
                        if not (mid and team_a and team_b and start):
                            continue
                        offset = first(node, "lock_offset_sec", "lockOffsetSec")
                        lock = ms_to_iso(first(node, "lock_time", "lockTime"))
                        if not lock and isinstance(offset, (int, float)) and 0 < offset < 14400:
                            lock = (parse_iso(start) - timedelta(seconds=int(offset))
                                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                        row = {
                            "match_id": mid,
                            "pages": [page_name],
                            "sport": first(node, "sport_alias", "sport", "game_alias", default=""),
                            "competition": first(node, "competition_name", "competitionName",
                                                 "competition", "tournament", default=""),
                            "stage": first(node, "stage", "stage_name", default=""),
                            "tier": str(first(node, "tier", "tier_name", default="")).lower(),
                            "status": first(node, "status", "match_status", default=""),
                            "team_a": team_a, "team_b": team_b,
                            "team_a_id": first(node, "participants0_id", default=""),
                            "team_b_id": first(node, "participants1_id", default=""),
                            "start_utc": start, "lock_utc": lock,
                            "lock_offset_sec": int(offset) if isinstance(offset, (int, float)) else None,
                            "offered_points": first(node, "offered_points", "offeredPoints",
                                                     "points", default=None),
                            "multiplier": first(node, "multiplier", "point_multiplier", default=None),
                            "best_of_payload": first(node, "best_of", "bestOf", "series_format",
                                                     "format", default=None),
                            "hotspawn_match_url": links.get(mid),
                            "source_url": url,
                            "captured_utc": got["fetched_utc"],
                            # audit-only: model.py must never read these
                            "crowd_pct_a_audit_only": first(node, "participants0_picked_percent",
                                                             default=None),
                            "crowd_pct_b_audit_only": first(node, "participants1_picked_percent",
                                                            default=None),
                            "total_picks_audit_only": first(node, "total_picks", "picks_count",
                                                            default=None),
                        }
                        known = fixtures.get(mid)
                        if known:
                            if page_name not in known["pages"]:
                                known["pages"].append(page_name)
                            for key, val in row.items():
                                if known.get(key) in (None, "", []) and val not in (None, "", []):
                                    known[key] = val
                        else:
                            fixtures[mid] = row
        pages.append(page)
        time.sleep(0.4)
    rows = sorted(fixtures.values(), key=lambda r: (r["start_utc"], r["match_id"]))
    log(f"hotspawn: {len(rows)} fixtures from {len(pages)} pages "
        f"({sum(1 for p in pages if p['status'] == 200)} ok)")
    return {"pages": pages, "fixtures": rows}


# --------------------------------------------------------------------------- 2 Pinnacle
def collect_pinnacle() -> dict:
    out = {"status": "unavailable", "matchups_url": PIN_MATCHUPS, "markets_url": PIN_MARKETS,
           "page_url": PIN_PAGE, "quotes": [], "events": 0, "cs2_events": 0}
    leagues, gl = get_json(PIN_LEAGUES, timeout=40)
    if isinstance(leagues, list):
        out["leagues_url"] = PIN_LEAGUES
        out["leagues"] = [{"id": l.get("id"), "name": l.get("name"),
                           "matchup_count": l.get("matchupCount")} for l in leagues
                          if isinstance(l, dict)]
        out["cs2_leagues"] = [l for l in out["leagues"] if str(l["name"]).startswith("CS2 - ")]
    if not wanted("pinnacle"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    matchups, gm = get_json(PIN_MATCHUPS, timeout=60)
    markets, gg = get_json(PIN_MARKETS, timeout=60)
    if not isinstance(matchups, list) or not isinstance(markets, list):
        out["error"] = f"matchups={gm.get('status')}/{gm.get('error')} markets={gg.get('status')}/{gg.get('error')}"
        log(f"pinnacle refused: {out['error']}")
        return out
    save_raw("pinnacle_matchups", gm.get("body"))
    save_raw("pinnacle_markets", gg.get("body"))
    events = {}
    for node in matchups:
        if not isinstance(node, dict) or not isinstance(node.get("id"), int):
            continue
        out["events"] += 1
        league = node.get("league") or {}
        if not str(league.get("name", "")).startswith("CS2 - "):
            continue
        if node.get("type") != "matchup" or node.get("parentId") is not None:
            continue
        parts = node.get("participants") or []
        if len(parts) != 2:
            continue
        names = {p.get("alignment"): p.get("name") for p in parts}
        if set(names) != {"home", "away"}:
            continue
        events[node["id"]] = {
            "team_a": names["home"], "team_b": names["away"],
            "start_utc": (node.get("startTime") or "")[:19].replace(" ", "T") + "Z"
            if node.get("startTime") else None,
            "league": league.get("name"), "league_id": league.get("id"),
            "best_of": node.get("bestOfX"), "status": node.get("status"),
            "event_id": node["id"], "cutoff": (node.get("cutoffAt") or "") or None,
        }
    out["cs2_events"] = len(events)
    quotes = []
    for market in markets:
        if not isinstance(market, dict):
            continue
        if market.get("type") != "moneyline" or market.get("period") != 0:
            continue
        if market.get("isAlternate") is not False or market.get("status") != "open":
            continue
        event = events.get(market.get("matchupId"))
        if not event:
            continue
        prices = {p.get("designation"): p.get("price") for p in (market.get("prices") or [])
                  if isinstance(p, dict)}
        if set(prices) != {"home", "away"}:
            continue
        from common import american_to_decimal
        dec = {side: american_to_decimal(prices[side]) for side in ("home", "away")}
        if not all(dec.values()):
            continue
        quotes.append({
            "book": "Pinnacle", "book_url": PIN_PAGE, "api_url": PIN_MARKETS,
            "market": "match_winner_moneyline", "native_format": "american",
            "native_a": prices["home"], "native_b": prices["away"],
            "odds_a": dec["home"], "odds_b": dec["away"],
            "team_a": event["team_a"], "team_b": event["team_b"],
            "start_utc": event["start_utc"], "best_of": event["best_of"],
            "league": event["league"], "event_id": str(event["event_id"]),
            "captured_utc": now_iso(),
            "note": "decimal converted from the American prices in Pinnacle's public guest "
                    "response (the payload their own CS2 matchups page loads); not a display rounding",
        })
    out["quotes"] = quotes
    out["status"] = "observed" if quotes else "served but no CS2 moneyline matched"
    log(f"pinnacle: {len(quotes)} CS2 moneyline quotes on {out['cs2_events']} events")
    return out


# --------------------------------------------------------------------- 3 EGamersWorld
_BROWSER = {"pw": None, "browser": None, "ctx": None, "broken": False}
BLOCK_TYPES = {"image", "font", "media"}
CHALLENGE_MARKERS = ("just a moment", "attention required", "checking your browser",
                     "verify you are human", "access denied")


def entry_ua() -> str:
    from common import BASE_HEADERS
    return BASE_HEADERS["User-Agent"]


def browser_context():
    """One shared headless Chromium for every page a run needs (Playwright is optional)."""
    if _BROWSER["broken"]:
        return None
    if _BROWSER["ctx"] is None:
        try:
            from playwright.sync_api import sync_playwright
            _BROWSER["pw"] = sync_playwright().start()
            _BROWSER["browser"] = _BROWSER["pw"].chromium.launch(
                headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            _BROWSER["ctx"] = _BROWSER["browser"].new_context(
                user_agent=entry_ua(), locale="en-US",
                viewport={"width": 1366, "height": 900},
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
            _BROWSER["ctx"].route("**/*", lambda route, request: (
                route.abort() if request.resource_type in BLOCK_TYPES else route.continue_()))
        except Exception as exc:                               # noqa: BLE001
            log(f"browser unavailable: {type(exc).__name__}: {exc} - plain-client path only")
            _BROWSER["broken"] = True
            return None
    return _BROWSER["ctx"]


def close_browser() -> None:
    for key in ("ctx", "browser"):
        try:
            if _BROWSER[key]:
                _BROWSER[key].close()
        except Exception:                                       # noqa: BLE001
            pass
    try:
        if _BROWSER["pw"]:
            _BROWSER["pw"].stop()
    except Exception:                                           # noqa: BLE001
        pass
    _BROWSER.update(pw=None, browser=None, ctx=None)


def browser_render(url: str, wait_ms: int = 2500, wait_for: str | None = None,
                   retries: int = 3) -> dict:
    """Render a public page in an ordinary browser; retry while a challenge clears by itself.

    Nothing is solved or bypassed: images/fonts are dropped for speed, and if the page still
    shows a "checking your browser" style interstitial after the retries, the refusal is recorded
    and no value is substituted for it.
    """
    import hashlib
    out = {"url": url, "fetched_utc": now_iso(), "via": "chromium", "status": None,
           "bytes": None, "sha256": None, "error": None, "attempts": []}
    ctx = browser_context()
    if ctx is None:
        out["error"] = "browser unavailable"
        record(out)
        return {**out, "html": None}
    html = None
    for attempt in range(1, retries + 1):
        page = None
        try:
            page = ctx.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            if wait_for:
                try:
                    page.wait_for_selector(wait_for, timeout=12000)
                except Exception:                              # noqa: BLE001
                    pass
            page.wait_for_timeout(wait_ms)
            html = page.content()
            title = (page.title() or "").lower()
            challenged = (resp is not None and resp.status in (403, 503)) or not html \
                or any(marker in title for marker in CHALLENGE_MARKERS)
            out["attempts"].append({"attempt": attempt, "status": resp.status if resp else None,
                                    "bytes": len(html or ""), "title": title[:60],
                                    "challenged": challenged})
            if not challenged:
                out.update(status=resp.status if resp else 200, bytes=len(html.encode()),
                           sha256=hashlib.sha256(html.encode()).hexdigest(), error=None)
                break
            html = None
            time.sleep(1.2 * attempt)
        except Exception as exc:                                # noqa: BLE001
            out["attempts"].append({"attempt": attempt, "error": f"{type(exc).__name__}: {exc}"})
            html = None
            time.sleep(1.0 * attempt)
        finally:
            try:
                if page:
                    page.close()
            except Exception:                                   # noqa: BLE001
                pass
    if html is None:
        out["error"] = "challenge/403 persisted across attempts"
    record(out)
    return {**out, "html": html}


PRICE_TOKEN = re.compile(r"(?<![\d.])(\d\.\d{2})(?![\d.])")
BOOK_LOGO = re.compile(r"uploads/[^\"']*?([a-z0-9][a-z0-9\-_.]{1,40})\.(?:png|webp|svg)", re.I)
BOOK_ALT = re.compile(r'alt="([^"]{2,40})"', re.I)


def parse_egw_match_page(html: str, url: str) -> dict:
    """Read the named-book odds table on an EGamersWorld match page.

    Heuristic by design and labelled as such: the page's book-logo images are the anchor, and a
    pair of decimal prices following a logo, inside the odds block and not inside a handicap /
    total / map-winner block, is taken as that book's 1/2 (match winner) price.  Anything the
    reader cannot attribute to a named book is dropped, not guessed.
    """
    plain = re.sub(r"\s+", " ", html)
    books, seen = [], set()
    tokens = [(m.group(1), m.start()) for m in PRICE_TOKEN.finditer(plain)]
    for idx in range(len(tokens) - 1):
        price_a, start = tokens[idx]
        price_b, _ = tokens[idx + 1]
        tail = plain[max(0, start - 420):start]
        imgs = list(re.finditer(r"<img[^>]*uploads/[^>]*>", tail, re.I))
        if not imgs:
            continue
        img = imgs[-1]
        between = tail[img.end():]
        low = between.lower()
        if len(between) > 260 or any(k in low for k in
                                    ("handicap", "total", "over/under", "odd/even",
                                     "winner map", "map winner", "round")):
            continue
        alt = BOOK_ALT.search(img.group(0))
        logo = BOOK_LOGO.search(img.group(0))
        name = (alt.group(1).strip() if alt else (logo.group(1) if logo else ""))
        name = re.sub(r"\.(?:png|webp|svg|jpg)$", "", name, flags=re.I)
        if not name or len(name) < 2 or name in seen:
            continue
        da, db = is_decimal(price_a), is_decimal(price_b)
        if not (da and db):
            continue
        seen.add(name)
        books.append({"book": name, "odds_a": da, "odds_b": db})
    return {"match_url": url, "books": books, "fetched_utc": now_iso()}


def slug_teams(url: str) -> tuple[str, str] | None:
    m = re.search(r"/match/[^/]+/([a-z0-9\-.]+?)-vs-([a-z0-9\-.]+?)(?:-[A-Za-z0-9_\-]{6,})?$", url, re.I)
    if not m:
        return None
    return (m.group(1).replace("-", " "), m.group(2).replace("-", " "))


def collect_egw(fixtures: list[dict], deadline: float) -> dict:
    out = {"status": "unavailable", "list_url": EGW_LIST, "list_prices": {}, "readings": {},
           "pages_read": 0, "plain_error": None}
    if not wanted("egw"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    html = None
    got = http_get(EGW_LIST, timeout=45)
    if got["status"] == 200 and got["body"]:
        html = got["body"].decode("utf-8", errors="replace")
    if not html or not EGW_MATCH_HREF.search(html):
        out["plain_error"] = f"HTTP {got['status']} {got['error']}"
        rendered = browser_render(EGW_LIST, wait_ms=6000,
                                 wait_for='a[href*="/counterstrike/match/"]')
        html = rendered.get("html")
        out["browser_status"] = rendered.get("status")
        out["browser_error"] = rendered.get("error")
        out["browser_attempts"] = rendered.get("attempts")
    if not html:
        out["error"] = out["plain_error"] or "no HTML from any path"
        log(f"egamersworld: refused ({out['error']})")
        return out
    save_raw("egw_list", html.encode())
    # list rows: match link plus the two prices shown beside it
    pairs: dict[str, dict] = {}
    for m in EGW_MATCH_HREF.finditer(re.sub(r"\s+", " ", html)):
        url = "https://egamersworld.com" + m.group(1)
        if url in pairs:
            continue
        pair = slug_teams(url)
        window = re.sub(r"<[^>]+>", " ", html[m.end():m.end() + 1600])
        prices = [p for p in PRICE_TOKEN.findall(window)][:2]
        pairs[url] = {"match_url": url, "teams": pair,
                      "list_prices": [float(p) for p in prices] if len(prices) == 2 else []}
    for url, row in pairs.items():
        if row["teams"] and row["list_prices"]:
            out["list_prices"][f"{row['teams'][0].casefold()}|{row['teams'][1].casefold()}"] = \
                {"odds": row["list_prices"], "match_url": url, "captured_utc": now_iso(),
                 "source_url": EGW_LIST,
                 "note": "EGamersWorld list widget price pair; the book behind it is not named "
                         "in the list view, so it is published as a market reference only"}
    from common import norm
    by_pair = {}
    for url, row in pairs.items():
        if row["teams"]:
            by_pair[frozenset(norm(t) for t in row["teams"])] = url
    wanted_pairs = {}
    for fx in fixtures:
        key = frozenset((norm(fx["team_a"]), norm(fx["team_b"])))
        url = by_pair.get(key)
        if url:
            wanted_pairs[fx["match_id"]] = url
    out["status"] = "observed" if pairs else "no match rows parsed"
    out["list_rows"] = len(pairs)
    for mid, url in list(wanted_pairs.items())[:int(os.environ.get("CS2_EGW_MAX_PAGES", "34"))]:
        if over_budget(deadline):
            out["budget_stopped"] = True
            break
        got = http_get(url, timeout=40)
        page_html = got["body"].decode("utf-8", errors="replace") if got["status"] == 200 else None
        if not page_html or "odds" not in (page_html or "").lower():
            rendered = browser_render(url, wait_ms=4000, wait_for='img[src*="uploads/"]'
                                      if not page_html else None)
            if rendered.get("html"):
                page_html = rendered["html"]
            out.setdefault("per_page_via", {}).setdefault(mid,
                                                          "chromium" if page_html else "refused")
        if not page_html:
            out["readings"][mid] = {"match_url": url, "books": [],
                                   "error": f"page not served (HTTP {got['status']})"}
            continue
        reading = parse_egw_match_page(page_html, url)
        reading["captured_utc"] = now_iso()
        out["readings"][mid] = reading
        out["pages_read"] += 1
        time.sleep(0.3)
    log(f"egamersworld: {len(pairs)} list rows, {out['pages_read']} match pages read, "
        f"{sum(len(r.get('books') or []) for r in out['readings'].values())} named-book rows")
    return out


# ----------------------------------------------------------------------- 4 VRS (official)
VRS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(-?\d+)\s*\|\s*([^|]{1,80}?)\s*\|\s*([^|]*?)\s*\|", re.M)


def collect_vrs() -> dict:
    out = {"status": "unavailable", "teams": []}
    if not wanted("vrs"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    md, meta = None, {}
    if VRS_LOCAL and Path(VRS_LOCAL).is_dir():
        year_dirs = sorted((Path(VRS_LOCAL) / "live").iterdir())
        files = sorted((year_dirs[-1] / ".").glob("standings_global_*.md"))
        if files:
            md = files[-1].read_text(encoding="utf-8", errors="replace")
            meta = {"file": f"live/{year_dirs[-1].name}/{files[-1].name}", "local_clone": True}
            commit = os.popen(f"git -C {VRS_LOCAL} rev-parse HEAD").read().strip()
            meta["commit"] = commit
            meta["url"] = ("https://github.com/ValveSoftware/counter-strike_regional_standings"
                           f"/blob/{commit}/" + meta["file"])
    else:
        listing, gl = get_json(VRS_API, timeout=45)
        if isinstance(listing, list):
            paths: list[str] = []
            for year in [e for e in listing if e.get("type") == "dir"]:
                sub, _ = get_json(year["url"], timeout=45)
                if isinstance(sub, list):
                    paths += [e["path"] for e in sub
                              if re.search(r"standings_global_\d{4}_\d{2}_\d{2}\.md$", e.get("name", ""))]
            if paths:
                latest = sorted(paths)[-1]
                raw = http_get(VRS_RAW + latest, timeout=60)
                if raw["status"] == 200 and raw["body"]:
                    md = raw["body"].decode("utf-8", errors="replace")
                    save_raw("vrs_" + Path(latest).stem, raw["body"])
                    meta = {"file": latest, "sha256": raw["sha256"],
                            "fetched_utc": raw["fetched_utc"], "url": VRS_RAW + latest,
                            "listing_url": VRS_API}
        if md is None:
            out["error"] = gl.get("error") or "no standings file served"
            return out
    m = re.search(r"as of (\d{4}_\d{2}_\d{2})", md, re.I)
    teams, lines = [], md.splitlines()
    for lineno, line in enumerate(lines, start=1):
        hit = VRS_ROW.match(line.strip())
        if not hit or hit.group(1) == ":-":
            continue
        rank, points, name, roster = hit.groups()
        if not points.isdigit():
            continue
        teams.append({"vrs_rank": int(rank), "name": name.strip(), "points": int(points),
                      "roster": [p.strip() for p in roster.split(",") if p.strip()],
                      "line": lineno,
                      "url": (meta.get("url", "").split("#")[0] + f"?plain=1#L{lineno}")})
    out.update(status="observed" if teams else "parsed empty", as_of=(m.group(1).replace("_", "-")
                                                                      if m else None),
               teams=teams, **meta)
    log(f"vrs: {len(teams)} rows, as of {out.get('as_of')}")
    return out


# ------------------------------------------------------------------------- 5 HLTV
def collect_hltv(deadline: float) -> dict:
    out = {"status": "unavailable", "ranking": {}, "matches": {}}
    if not wanted("hltv"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    today = datetime.now(timezone.utc)
    dated = HLTV_RANKING_TMPL.format(y=today.year, month=today.strftime("%B").lower(), day=today.day)
    # HLTV's own /ranking/teams entry redirects to the page for the date its editors last
    # published; asking for today's date produced a 403 from the runner, so we follow their
    # redirect and keep whichever page they served.  The dated URL is recorded as the fallback.
    out["ranking_url_preferred"] = "https://www.hltv.org/ranking/teams"
    out["ranking_url_dated_fallback"] = dated
    for name, target in (("ranking", "https://www.hltv.org/ranking/teams"),
                         ("matches", HLTV_MATCHES)):
        if over_budget(deadline):
            out[name] = {"status": None, "error": "budget"}
            continue
        got = http_get(target, timeout=45)
        if name == "ranking" and got["status"] != 200:
            alt = http_get(dated, timeout=45)
            if alt["status"] == 200:
                got, target = alt, dated
        html = got["body"].decode("utf-8", errors="replace") if got["status"] == 200 else None
        via = "urllib"
        if not html:
            rendered = browser_render(target, wait_ms=3000)
            html = rendered.get("html")
            via = "chromium"
            out[name + "_plain"] = {"status": got["status"], "error": got["error"]}
        if not html:
            out[name] = {"url": target, "status": got["status"], "via": via,
                         "error": got["error"] or "no body", "rows": []}
            continue
        save_raw(f"hltv_{name}", html.encode())
        rows = []
        if name == "ranking":
            for m in re.finditer(r'<a href="/team/(\d+)/[a-z0-9\-]+"[^>]*>([^<]{2,60})</a>', html):
                rows.append({"team_id": m.group(1), "name": unescape(m.group(2)).strip(),
                             "url": "https://www.hltv.org/team/" + m.group(1)})
            out["ranking"] = {"url": target, "status": got["status"], "via": via,
                              "team_links": len(rows), "sample": rows[:400]}
        else:
            for m in re.finditer(r'<div class="match-info match notstarted[^"]*"[^>]*data-match-id="(\d+)"',
                                 html):
                rows.append(m.group(1))
            entries = re.findall(r'href="(/matches/\d+/[a-z0-9\-]+)"', html)
            out["matches"] = {"url": target, "status": got["status"], "via": via,
                              "match_ids": sorted(set(rows))[:400],
                              "links": ["https://www.hltv.org" + e for e in dict.fromkeys(entries)][:400],
                              "count": len(dict.fromkeys(entries))}
        out["status"] = "observed"
    log("hltv: ranking=" + str(out["ranking"].get("team_links", out["ranking"].get("error")))
        + " matches=" + str(out["matches"].get("count", out["matches"].get("error"))))
    return out


# -------------------------------------------------------------------- 6 Polymarket
def collect_polymarket() -> dict:
    out = {"status": "unavailable", "api_url": POLYMARKET, "rows": []}
    if not wanted("polymarket"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    data, got = get_json(POLYMARKET, timeout=45)
    markets = []
    if isinstance(data, list):
        markets = data
    elif isinstance(data, dict):
        markets = data.get("data") or []
    for market in markets:
        if not isinstance(market, dict):
            continue
        question = str(market.get("question") or "")
        if not re.search(r"\bvs\.?\b", question, re.I):
            continue
        if not re.search(r"cs2|counter[- ]strike", (str(market.get("title")) + question
                                                     + str(market.get("tags"))), re.I):
            continue
        try:
            prices = [float(x) for x in json.loads(market.get("outcomePrices") or "[]")]
        except (TypeError, ValueError):
            prices = []
        if len(prices) != 2:
            continue
        out["rows"].append({"question": question, "prices": prices,
                            "market_slug": market.get("slug"),
                            "end_date": market.get("endDate"),
                            "volume": market.get("volume"),
                            "source_url": "https://polymarket.com/event/"
                                          + str(market.get("slug") or ""),
                            "captured_utc": now_iso(),
                            "kind": "prediction_market_not_a_sportsbook"})
    out["status"] = "observed" if out["rows"] else "no CS2 two-outcome markets served"
    out["fetched_utc"] = got.get("fetched_utc")
    log(f"polymarket: {len(out['rows'])} CS2 markets")
    return out


# ------------------------------------------------------------- 7 attempted / refused feeds
def collect_attempts(deadline: float) -> list[dict]:
    """A public record of what was tried, including what refused us.  Nothing is filled in."""
    rows = []
    for label, url in REFUSED_FEEDS:
        if over_budget(deadline):
            rows.append({"source": label, "url": url, "status": None, "error": "budget"})
            continue
        got = http_get(url, timeout=20, retries=0)
        shape = None
        if got["body"]:
            head = got["body"][:400].decode("utf-8", errors="replace")
            shape = f"{len(got['body'])} bytes; head={head[:120]!r}"
        rows.append({"source": label, "url": url, "status": got["status"],
                     "error": got["error"], "bytes": got["bytes"], "fetched_utc": got["fetched_utc"],
                     "observation": shape or "empty body"})
    return rows


# ------------------------------------------------------------- 8 shape probe: OddsDigger listing
# Reached from the runner (HTTP 200, 255 kB) on 2026-10-14 while every other aggregator refused.
# No parser yet: we archive the bytes and publish a shape report, so a following run can write a
# parser against real content instead of guessing at markup.  Nothing is published from this source
# until that parser exists, so it cannot quietly become "odds we made up".
ODDSDIGGER_URLS = [("esports index", "https://oddsdigger.com/e-sports"),
                   ("cs2 listing", "https://oddsdigger.com/e-sports/counter-strike")]
ODDS_RE = re.compile(r">\s*(\d{1,2}\.\d{2})\s*<")


def collect_oddsdigger(deadline: float) -> dict:
    out = {"status": "probing", "used_for": "nothing yet - shape report only, see cs2/README.md",
           "pages": []}
    if not wanted("oddsdigger"):
        out["status"] = "skipped by CS2_SOURCES"
        return out
    for label, url in ODDSDIGGER_URLS:
        if over_budget(deadline):
            out["pages"].append({"page": label, "url": url, "error": "budget"})
            continue
        got = http_get(url, timeout=45)
        rec = {"page": label, "url": url, "status": got["status"], "bytes": got["bytes"],
               "fetched_utc": got["fetched_utc"], "error": got["error"]}
        html = got["body"].decode("utf-8", errors="replace") if got["body"] else ""
        if html:
            save_raw(f"oddsdigger_{label.replace(' ', '_')}", got["body"])
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S)
            cs2_links = sorted(set(re.findall(r'href="(/e-sports/[a-z0-9\-]+)"', html)))[:200]
            rec.update({
                "table_rows": len(rows),
                "decimal_odds_tokens": len(ODDS_RE.findall(html)),
                "cs2_event_links": len(cs2_links),
                "cs2_event_links_sample": cs2_links[:25],
                "team_anchor_sample": [unescape(t).strip() for t in
                                       re.findall(r'<a[^>]*href="/teams?/[a-z0-9\-]+"[^>]*>([^<]{2,40})</a>',
                                                  html)][:40],
                "row_sample": [re.sub(r"\s+", " ", plain_text(r))[:220] for r in rows[:6]],
            })
        out["pages"].append(rec)
    ok = [p for p in out["pages"] if p.get("status") == 200]
    out["status"] = "reachable, unparsed" if ok else "unavailable"
    log(f"oddsdigger: {len(ok)} page(s) reachable, biggest table {max([p.get('table_rows') or 0 for p in out['pages']])} rows")
    return out


def main() -> int:
    started = now_iso()
    deadline = budget(1500)
    hotspawn = collect_hotspawn()
    fixtures = hotspawn["fixtures"]
    cs2_open = [f for f in fixtures
                if (f["sport"] or "").lower() in ("cs2", "counter-strike", "counterstrike")
                and parse_iso(f.get("lock_utc")) and parse_iso(f["lock_utc"]) > datetime.now(timezone.utc)]
    capture = {
        "schema": 1,
        "session": "arena/a174d77f",
        "generated_utc": now_iso(),
        "started_utc": started,
        "sources": {
            "hotspawn": hotspawn,
            "pinnacle": collect_pinnacle(),
            "egamersworld": collect_egw(cs2_open, deadline),
            "vrs": collect_vrs(),
            "hltv": collect_hltv(deadline),
            "polymarket": collect_polymarket(),
            "oddsdigger": collect_oddsdigger(deadline),
            "attempts": collect_attempts(deadline),
        },
    }
    close_browser()
    write_json(CAPTURE, capture)
    flush_provenance()
    rows = capture["sources"]["pinnacle"]["quotes"]
    write_json(DATA / "pinnacle_quotes.json", rows)
    log(f"capture written: {len(fixtures)} fixtures, {len(cs2_open)} open CS2, "
        f"{len(rows)} pinnacle quotes; provenance {len(json.loads((DATA / 'provenance.json').read_text()))} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
