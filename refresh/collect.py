#!/usr/bin/env python3
"""R-01 live refresh collector — session arena/b90700c6.

Runs on GitHub Actions (the sandbox shell cannot reach these hosts).  Everything written is a
derived, source-linked projection of public pages; raw bodies stay out of Git (only byte size and
SHA-256 are recorded in refresh/data/provenance.json, so anyone can re-fetch and compare).

Sources
  1. Hotspawn Play Pick'em — fixture identity and exact UTC times ONLY.
       https://play.hotspawn.com/lobby, /cs2-pickems, /thp-pickems, /lol-pickems
     The Angular SSR pages embed their full render state in `<script id="ng-state">`, which gives
     fixture id, competition, tier, stage, offered points, `scheduled_start_time` (ms epoch),
     `lock_time`/`lock_offset_sec` and the crowd pick percentages.  Crowd percentages are read for
     transparency and then dropped: build.py refuses to publish a dataset that contains them.
  2. EGamersWorld — external bookmaker match-winner prices, per bookmaker, from the "Betting odds"
     table on each match page (rendered in headless Chromium: plain clients get HTTP 403).
  3. Pinnacle — public guest matchups/markets responses that the public matchups page loads by
     itself (no account, no key); moneyline prices are converted from American to decimal.
  4. HLTV — world ranking (rating input for our own line) and the upcoming-matches list.
  5. Valve Regional Standings — Valve's own published data (official), read through the GitHub
     contents API.

No login, no private API, no challenge solving.  A field that cannot be read stays null.
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

import browser as browser_mod

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "refresh" / "data"
UA = browser_mod.UA
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
]
EGW_LISTS = [("cs2", "https://egamersworld.com/counterstrike/matches"),
             ("lol", "https://egamersworld.com/lol/matches")]
EGW_EVENTS = [("cs2", "https://egamersworld.com/counterstrike/events"),
              ("lol", "https://egamersworld.com/lol/events")]
HLTV_PAGES = [("hltv-ranking", "https://www.hltv.org/ranking/teams"),
              ("hltv-matches", "https://www.hltv.org/matches")]
PINNACLE_PAGES = [("pinnacle-highlights", "https://www.pinnacle.com/en/esports/matchups/highlights"),
                  ("pinnacle-cs2", "https://www.pinnacle.com/en/esports/games/cs2/matchups/"),
                  ("pinnacle-lol",
                   "https://www.pinnacle.com/en/esports/games/league-of-legends/matchups/")]
VRS_LATEST_API = ("https://api.github.com/repos/ValveSoftware/"
                  "counter-strike_regional_standings/contents/live/2026")

STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
CARD_BLOCK = re.compile(r"<app-pickem-vs-card\b", re.I)

BROWSER_HOSTS = ("egamersworld.com", "hltv.org", "pinnacle.com")
DEADLINE = time.time() + 20 * 60          # stop opening new pages after 20 minutes
provenance: list[dict] = []
_browser: browser_mod.BrowserSession | None = None
_browser_failed = False


def record(rec: dict) -> None:
    provenance.append({k: v for k, v in rec.items() if k != "body"})


def fetch(url: str, timeout: int = 45, accept_json: bool = False) -> dict:
    """Plain HTTP client — used for Hotspawn and the GitHub contents API (both reachable)."""
    headers = dict(HEADERS)
    if accept_json:
        headers["Accept"] = "application/vnd.github+json"
    req = Request(url, headers=headers)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = {"url": url, "fetched_utc": stamp, "status": None, "bytes": None, "sha256": None,
           "error": None, "path": "http"}
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(20_000_000)
            rec.update(status=resp.status, bytes=len(body),
                       sha256=hashlib.sha256(body).hexdigest())
            rec["body"] = body
    except HTTPError as exc:
        rec.update(error=f"HTTPError {exc.code}", status=exc.code, body=b"")
    except (URLError, TimeoutError, OSError) as exc:
        rec.update(error=f"{type(exc).__name__}: {exc}", body=b"")
    record(rec)
    return rec


def browser() -> browser_mod.BrowserSession | None:
    global _browser, _browser_failed
    if _browser_failed or not browser_mod.HAVE_PLAYWRIGHT:
        return None
    if _browser is None:
        try:
            _browser = browser_mod.BrowserSession().__enter__()
        except Exception as exc:  # noqa: BLE001
            print(f"browser unavailable: {type(exc).__name__}: {exc}", flush=True)
            _browser_failed = True
            return None
    return _browser


def fetch_html(url: str) -> dict:
    """Render a page in the browser when the host needs it, else use the HTTP client."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if any(host in url for host in BROWSER_HOSTS):
        if time.time() > DEADLINE:
            rec = {"url": url, "fetched_utc": stamp, "status": None, "bytes": None,
                   "sha256": None, "path": "browser", "error": "collection deadline reached"}
            record(rec)
            return {**rec, "html": None, "captured": []}
        session = browser()
        if session is not None:
            got = session.get(url)
            html = got.get("html") or ""
            rec = {"url": url, "fetched_utc": got["fetched_utc"], "status": got["status"],
                   "bytes": len(html.encode("utf-8")) if html else None,
                   "sha256": hashlib.sha256(html.encode("utf-8")).hexdigest() if html else None,
                   "path": "browser", "error": got.get("error")}
            record(rec)
            return {**rec, "html": html or None, "captured": got.get("captured") or []}
    got = fetch(url)
    body = got.get("body") or b""
    return {**got, "html": body.decode("utf-8", errors="replace") if body else None,
            "captured": []}


def text_of(html: str) -> str:
    plain = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    plain = re.sub(r"(?s)<[^>]+>", " ", plain)
    return re.sub(r"\s+", " ", unescape(plain)).strip()


def ms_to_iso(value) -> str | None:
    if isinstance(value, bool):
        return None
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 13:
        return None
    try:
        return datetime.fromtimestamp(int(digits) / 1000, timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError, OSError):
        return None


# --------------------------------------------------------------------------- Hotspawn payload
def walk_for_matches(node, out: list[dict]) -> None:
    if isinstance(node, dict):
        keys = set(node)
        if (({"participants0_name", "participants1_name"} <= keys)
                or {"scheduled_start_time"} <= keys
                or {"teamA", "teamB"} <= keys):
            out.append(node)
        for value in node.values():
            walk_for_matches(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_for_matches(item, out)


def first(d: dict, *names, default=None):
    for name in names:
        if name in d and d[name] not in (None, "", [], {}):
            return d[name]
    return default


def normalise_fixture(node: dict, page: str, stamp: str) -> dict | None:
    start = ms_to_iso(first(node, "scheduled_start_time", "scheduledStartTime"))
    if not start:
        return None
    offset = first(node, "lock_offset_sec", "lockOffsetSec")
    lock = ms_to_iso(first(node, "lock_time", "lockTime"))
    if not lock and isinstance(offset, (int, float)) and 0 < offset < 7200:
        lock = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                - timedelta(seconds=int(offset))).strftime("%Y-%m-%dT%H:%M:%SZ")
    match_id = first(node, "id", "match_id", "matchId")
    team_a = first(node, "participants0_name", "teamA")
    team_b = first(node, "participants1_name", "teamB")
    if not (match_id and team_a and team_b):
        return None
    participants = node.get("participants")
    pct = [None, None, first(node, "total_picks", "picks_count")]
    if isinstance(participants, list) and len(participants) >= 2:
        pct[0] = first(participants[0], "picked_percent", "picked")
        pct[1] = first(participants[1], "picked_percent", "picked")
    return {
        "match_id": str(match_id),
        "sport": first(node, "sport_alias", "sport", "game_alias"),
        "competition": first(node, "competition_name", "competitionName", "competition",
                             "tournament"),
        "status": first(node, "status", "match_status"),
        "tier": first(node, "tier", "tier_name"),
        "stage": first(node, "stage", "stage_name"),
        "best_of": first(node, "best_of", "bestOf", "series_format", "format"),
        "offered_points": first(node, "offered_points", "offeredPoints", "points"),
        "base_points": first(node, "base_points", "basePoints"),
        "scheduled_start_utc": start,
        "lock_utc": lock,
        "lock_offset_sec": int(offset) if isinstance(offset, (int, float)) else None,
        "team_a": team_a, "team_b": team_b,
        "team_a_id": first(node, "participants0_id", "teamA_id"),
        "team_b_id": first(node, "participants1_id", "teamB_id"),
        "crowd_pct_a": pct[0], "crowd_pct_b": pct[1], "total_picks": pct[2],
        "pages": [page],
        "source_url": f"https://play.hotspawn.com/{page}",
        "snapshot_utc": stamp,
    }


def collect_hotspawn() -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixtures: dict[str, dict] = {}
    pages_report = []
    reset_utc = week_total_text = week_total_context = None
    for page, url in HOTSPAWN_PAGES:
        got = fetch(url)
        entry = {"page": page, "url": url, "status": got["status"], "bytes": got["bytes"],
                 "sha256": got["sha256"], "error": got["error"], "state_rows": 0,
                 "cards_rendered": 0, "week_total_text": None, "week_total_context": None,
                 "reset_utc": None}
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            entry["cards_rendered"] = len(CARD_BLOCK.findall(html))
            plain = text_of(html)
            m = re.search(r"(\d+)\s+matches this week", plain)
            if m:
                week_total_text = int(m.group(1))
                week_total_context = plain[max(0, m.start() - 90):m.end() + 40]
                entry["week_total_text"] = week_total_text
                entry["week_total_context"] = week_total_context
            m = re.search(r"Resets in (?:(\d+)d )?(?:(\d+)h )?(?:(\d+)m )?(?:(\d+)s)", plain)
            if m:
                d, h, mi, s = (int(g) if g else 0 for g in m.groups())
                reset_utc = (datetime.now(timezone.utc) + timedelta(days=d, hours=h, minutes=mi,
                                                                    seconds=s)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                entry["reset_utc"] = reset_utc
                entry["reset_context"] = plain[max(0, m.start() - 60):m.end() + 30]
            m = STATE_SCRIPT.search(html)
            if m:
                try:
                    state = json.loads(unescape(m.group(1)).strip())
                except json.JSONDecodeError as exc:
                    entry["error"] = f"ng-state JSON decode failed: {exc}"
                else:
                    rows: list[dict] = []
                    walk_for_matches(state, rows)
                    entry["state_rows"] = len(rows)
                    for node in rows:
                        row = normalise_fixture(node, page, stamp)
                        if not row:
                            continue
                        known = fixtures.get(row["match_id"])
                        if known:
                            if page not in known["pages"]:
                                known["pages"].append(page)
                            for key, value in row.items():
                                if known.get(key) in (None, "") and value not in (None, ""):
                                    known[key] = value
                        else:
                            fixtures[row["match_id"]] = row
            else:
                entry["error"] = "no ng-state script found"
        pages_report.append(entry)
        time.sleep(0.3)
    rows = sorted(fixtures.values(), key=lambda r: (r["scheduled_start_utc"], r["match_id"]))
    sports = {}
    for row in rows:
        sports[row.get("sport")] = sports.get(row.get("sport"), 0) + 1
    return {"generated_utc": stamp, "reset_utc": reset_utc, "week_total_text": week_total_text,
            "week_total_context": week_total_context, "sport_counts": sports,
            "pages": pages_report, "fixtures": rows}


# --------------------------------------------------------------------------- EGamersWorld
MATCH_HREF = re.compile(
    r'href="(https://egamersworld\.com/(?:counterstrike|lol|dota2|valorant)/match/[^"#?]+)"')
EVENT_HREF = re.compile(
    r'href="(https://egamersworld\.com/(?:counterstrike|lol|dota2|valorant)/event/[^"#?]+)"')
PRICE_TOKEN = re.compile(r">\s*(\d{1,2}\.\d{1,3})\s*<")
BOOK_LOGO = re.compile(r"uploads/ensign/[^\"']+?/([^/\"']+?)\.(?:svg|webp|png)")
EGW_SLUG_TAIL = re.compile(r"-(?:[A-Za-z0-9_\-]{6,14})$")


def egw_match_pair(url: str) -> tuple[str, str] | None:
    slug = url.rstrip("/").split("/")[-1]
    m = re.match(r"(.+?)-vs-(.+)$", slug)
    if not m:
        return None
    return (m.group(1).replace("-", " ").strip(),
            EGW_SLUG_TAIL.sub("", m.group(2)).replace("-", " ").strip())


def scan_list_page(html: str) -> dict:
    plain = re.sub(r"\s+", " ", html)
    rows, seen = {}, set()
    for m in MATCH_HREF.finditer(plain):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        window = plain[m.end(): m.end() + 1400]
        rows[url] = {"match_url": url,
                     "list_prices": [float(p) for p in PRICE_TOKEN.findall(window)][:4]}
    return {"match_links": len(rows), "rows": rows}


def parse_match_page(html: str, url: str) -> dict:
    plain = re.sub(r"\s+", " ", html)
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    out = {"match_url": url, "title": unescape(title.group(1)).strip() if title else None,
           "kickoff_text": None, "books": [], "widget": [], "layout": "unknown",
           "snapshot_context": None}
    if title:
        m = re.search(r"(\d{2}\.\d{2}\.\d{2})\s+(\d{1,2}:\d{2})", title.group(1))
        if m:
            out["kickoff_text"] = f"{m.group(1)} {m.group(2)}"
    tokens = [(float(m.group(1)), m.start()) for m in PRICE_TOKEN.finditer(plain)]
    out["price_tokens_total"] = len(tokens)
    out["widget"] = [p for p, _ in tokens[:2]]
    books, seen_books = [], set()
    skip_labels = ("winner map", "total", "winner round", "handicap", "over/under", "odd/even")
    book_img = re.compile(r"<img[^>]*uploads/ensign/[^>]*>", re.I)
    for idx, (price, start) in enumerate(tokens):
        if idx + 1 >= len(tokens):
            break
        nxt = tokens[idx + 1][0]
        tail = plain[max(0, start - 320):start]
        imgs = list(book_img.finditer(tail))
        if not imgs:
            continue
        img = imgs[-1]
        between = tail[img.end():]
        if len(between) > 220 or any(label in between.lower() for label in skip_labels):
            continue
        alt = re.search(r'alt="([^"]{2,40})"', img.group(0))
        name = alt.group(1).strip() if alt else BOOK_LOGO.search(img.group(0)).group(1)
        if name in seen_books or not (1.01 <= price <= 30 and 1.01 <= nxt <= 30):
            continue
        seen_books.add(name)
        books.append({"book": name, "odds_a": price, "odds_b": nxt})
    out["books"] = books
    out["layout"] = "book_table" if books else ("widget_only" if out["widget"] else "none")
    marker = plain.find("Betting odds")
    out["snapshot_context"] = plain[marker: marker + 260] if marker >= 0 else ""
    return out


def collect_egw(candidates: list[dict]) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lists, event_links = {}, []
    for title, url in EGW_LISTS:
        got = fetch_html(url)
        if got.get("html"):
            lists[title] = scan_list_page(got["html"])
            lists[title]["url"] = url
            event_links += EVENT_HREF.findall(got["html"])
        else:
            lists[title] = {"url": url, "error": got.get("error"), "status": got.get("status"),
                            "rows": {}}
        time.sleep(0.2)
    for title, url in EGW_EVENTS:
        got = fetch_html(url)
        if got.get("html"):
            event_links += EVENT_HREF.findall(got["html"])
        time.sleep(0.2)
    event_links = sorted(set(event_links))
    wanted = set()
    for fx in candidates:
        for word in re.findall(r"[a-z0-9]{4,}", (fx.get("competition") or "").lower()):
            if word not in {"season", "series", "stage", "league", "the", "with", "playin"}:
                wanted.add(word)
    picked_events = [u for u in event_links if any(w in u.lower() for w in wanted)][:24]

    candidates_by_url: dict[str, dict] = {}
    for url in picked_events:
        got = fetch_html(url)
        if got.get("html"):
            for match_url, row in scan_list_page(got["html"])["rows"].items():
                candidates_by_url.setdefault(match_url, row)
        time.sleep(0.2)
    for entry in lists.values():
        for match_url, row in (entry.get("rows") or {}).items():
            candidates_by_url.setdefault(match_url, row)

    by_pair: dict[str, str] = {}
    for url, row in candidates_by_url.items():
        pair = egw_match_pair(url)
        if not pair:
            continue
        row["teams_from_slug"] = pair
        by_pair.setdefault(norm_key(pair[0]) + "|" + norm_key(pair[1]), url)

    readings, stopped = {}, False
    for fx in candidates:
        ka, kb = norm_key(fx["team_a"]), norm_key(fx["team_b"])
        url = by_pair.get(ka + "|" + kb) or by_pair.get(kb + "|" + ka)
        if not url:
            readings[fx["match_id"]] = {"found": False,
                                        "reason": "no EGamersWorld match page matched this team "
                                                  "pair"}
            continue
        if time.time() > DEADLINE:
            stopped = True
            readings[fx["match_id"]] = {"found": False, "match_url": url,
                                        "reason": "collection deadline reached before this page"}
            continue
        got = fetch_html(url)
        if not got.get("html"):
            readings[fx["match_id"]] = {"found": False, "match_url": url,
                                        "reason": f"page render failed ({got.get('error')})"}
            continue
        parsed = parse_match_page(got["html"], url)
        parsed["found"] = True
        parsed["reversed"] = by_pair.get(ka + "|" + kb) is None
        parsed["fetched_utc"] = got.get("fetched_utc") or stamp
        readings[fx["match_id"]] = parsed
    return {"generated_utc": stamp, "lists": lists, "events_scanned": picked_events,
            "candidate_matches": len(candidates_by_url), "readings": readings,
            "stopped_at_deadline": stopped}


# --------------------------------------------------------------------------- Pinnacle
def collect_pinnacle() -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    quotes, counters, pages = [], {}, []
    session = browser()
    for label, url in PINNACLE_PAGES:
        got = fetch_html(url)
        captured = got.get("captured") or []
        pages.append({"label": label, "url": url, "status": got.get("status"),
                      "bytes": got.get("bytes"), "error": got.get("error"),
                      "captured_json_responses": len(captured)})
        if captured:
            found, sub = browser_mod.extract_pinnacle_quotes(captured, url)
            quotes.extend(found)
            for key, value in sub.items():
                counters[key] = counters.get(key, 0) + value
        time.sleep(0.2)
    if session is None:
        counters["browser"] = "unavailable"
    dedup = {}
    for quote in quotes:
        key = (quote["game"], quote["event_id"])
        if key not in dedup or quote["observed_utc"] > dedup[key]["observed_utc"]:
            dedup[key] = quote
    return {"generated_utc": stamp, "pages": pages, "counters": counters,
            "quotes": sorted(dedup.values(), key=lambda q: (q.get("team_a") or ""))}


# --------------------------------------------------------------------------- HLTV
def collect_hltv() -> dict:
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "pages": {}, "ranking": {}, "matches": []}
    for label, url in HLTV_PAGES:
        got = fetch_html(url)
        out["pages"][label] = {"url": url, "status": got.get("status"), "bytes": got.get("bytes"),
                               "sha256": got.get("sha256"), "error": got.get("error"),
                               "path": got.get("path")}
        html = got.get("html")
        if not html:
            continue
        if label == "hltv-ranking":
            for block in html.split('<div class="ranked-team standard-box">')[1:]:
                pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
                name = re.search(r'<span class="name">([^<]+)</span>', block)
                pts = re.search(r'<span class="points">\((\d+)', block)
                if pos and name:
                    out["ranking"][unescape(name.group(1)).strip()] = {
                        "rank": int(pos.group(1)), "points": int(pts.group(1)) if pts else None}
            out["ranking_url"] = url
            out["ranking_blocks"] = html.count('<div class="ranked-team standard-box">')
            date_match = re.search(
                r"World ranking on ([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4})", html)
            out["ranking_date_text"] = date_match.group(1) if date_match else None
            if not out["ranking"]:
                marker = html.find('ranked-team')
                out["ranking_debug_snippet"] = html[max(0, marker - 200): marker + 700] \
                    if marker >= 0 else html[:400]
        elif label == "hltv-matches":
            for block in re.split(r'<div class="match-item', html)[1:]:
                unix = re.search(r'data-unix="(\d{13})"', block)
                teams = re.findall(r'class="team[^"]*">\s*([^<]{2,40})\s*<', block)
                event = re.search(r'class="event-name">([^<]+)<', block)
                if unix and len(teams) >= 2:
                    out["matches"].append({
                        "unix": int(unix.group(1)),
                        "utc": datetime.fromtimestamp(int(unix.group(1)) / 1000,
                                                      timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "team_a": unescape(teams[0]).strip(),
                        "team_b": unescape(teams[1]).strip(),
                        "event": unescape(event.group(1)).strip() if event else None})
            out["match_rows"] = len(out["matches"])
        time.sleep(0.2)
    return out


# --------------------------------------------------------------------------- Valve VRS
def collect_valve() -> dict:
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "file": None, "source_url": None, "teams": {}, "error": None, "rows_read": 0}
    listing = fetch(VRS_LATEST_API, accept_json=True)
    if not listing["body"]:
        out["error"] = f"VRS listing failed: {listing['error']}"
        return out
    try:
        files = json.loads(listing["body"].decode("utf-8"))
    except json.JSONDecodeError as exc:
        out["error"] = f"VRS listing JSON decode failed: {exc}"
        return out
    standings = [f for f in files if isinstance(f, dict)
                 and re.match(r"standings_global_\d{4}_\d{2}_\d{2}\.md$", f.get("name", ""))]
    if not standings:
        out["error"] = "no standings_global_*.md file in Valve's live/2026 directory"
        return out
    standings.sort(key=lambda f: f["name"])
    latest = standings[-1]
    out["file"], out["source_url"] = latest["name"], latest["download_url"]
    got = fetch(latest["download_url"])
    if not got["body"]:
        out["error"] = f"VRS file fetch failed: {got['error']}"
        return out
    body = got["body"].decode("utf-8", errors="replace")
    # Valve's table: | Standing | Points | Team Name | Roster | details | — read the header.
    columns: dict[str, int] = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            continue
        lower = [c.lower() for c in cells]
        if "points" in lower and any("team" in c for c in lower):
            for idx, cell in enumerate(lower):
                if cell == "points":
                    columns["points"] = idx
                elif cell.startswith("team"):
                    columns["team"] = idx
            continue
        if "points" not in columns or "team" not in columns:
            continue
        if len(cells) <= max(columns.values()):
            continue
        name = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cells[columns["team"]]).strip()
        try:
            points = float(cells[columns["points"]])
        except ValueError:
            continue
        if not name:
            continue
        out["teams"][name] = {"points": points, "source_url": latest["download_url"]}
        out["rows_read"] += 1
    if not out["teams"]:
        out["error"] = "Valve standings table was found but no team rows could be read"
    return out


# --------------------------------------------------------------------------- helpers
def norm_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", unescape(name or "").lower().replace("&", "and"))


def probe_hosts() -> None:
    for label, url in (("hotspawn", "https://play.hotspawn.com/lobby"),
                       ("egw-cs2", "https://egamersworld.com/counterstrike/matches"),
                       ("hltv-ranking", "https://www.hltv.org/ranking/teams"),
                       ("valve-api", VRS_LATEST_API)):
        if any(host in url for host in BROWSER_HOSTS):
            got = fetch_html(url)
            print(f"probe {label:14s} path={got.get('path')} status={got.get('status')} "
                  f"bytes={got.get('bytes')} err={got.get('error')}", flush=True)
        else:
            got = fetch(url)
            print(f"probe {label:14s} path=http status={got['status']} bytes={got['bytes']} "
                  f"err={got['error']}", flush=True)
        time.sleep(0.2)


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    print(f"playwright available: {browser_mod.HAVE_PLAYWRIGHT}", flush=True)
    probe_hosts()
    hs = collect_hotspawn()
    fixtures = hs["fixtures"]
    now = datetime.now(timezone.utc)
    reset = (datetime.strptime(hs["reset_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
             if hs.get("reset_utc") else None)
    week_end = reset or (now + timedelta(days=7))
    horizon_start = now - timedelta(hours=36)
    candidates = []
    for fx in fixtures:
        try:
            start = datetime.strptime(fx["scheduled_start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if horizon_start <= start <= week_end:
            candidates.append(fx)
    print(f"slate candidates for odds lookup: {len(candidates)} of {len(fixtures)} payload rows",
          flush=True)
    egw = collect_egw(candidates)
    pinnacle = collect_pinnacle()
    hltv = collect_hltv()
    valve = collect_valve()

    payload = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "hotspawn": hs, "egw": egw, "pinnacle": pinnacle, "hltv": hltv,
               "valve_vrs": valve}
    (DATA / "collected.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")
    (DATA / "provenance.json").write_text(
        json.dumps({"generated_utc": payload["generated_utc"], "fetches": provenance}, indent=1),
        encoding="utf-8")

    sports: dict[str, int] = {}
    for fx in fixtures:
        sports[fx.get("sport")] = sports.get(fx.get("sport"), 0) + 1
    summary = {
        "generated_utc": payload["generated_utc"],
        "hotspawn_fixtures": len(fixtures), "sports": sports,
        "week_total_text": hs["week_total_text"], "week_total_context": hs["week_total_context"],
        "reset_utc": hs["reset_utc"],
        "ng_state_rows": {p["page"]: p["state_rows"] for p in hs["pages"]},
        "cards_rendered": {p["page"]: p["cards_rendered"] for p in hs["pages"]},
        "egw_candidates": egw["candidate_matches"], "egw_events_scanned": len(egw["events_scanned"]),
        "egw_fixtures_with_book_table": sum(1 for r in egw["readings"].values() if r.get("books")),
        "egw_fixtures_without_link": sum(1 for r in egw["readings"].values() if not r.get("found")),
        "egw_deadline_hit": egw["stopped_at_deadline"],
        "pinnacle_quotes": len(pinnacle["quotes"]), "pinnacle_counters": pinnacle["counters"],
        "hltv_ranking_teams": len(hltv["ranking"]), "hltv_matches": len(hltv["matches"]),
        "valve_vrs_file": valve["file"], "valve_vrs_teams": len(valve["teams"]),
        "valve_vrs_error": valve["error"],
        "fetch_failures": sorted({(p["url"], p["status"]) for p in provenance
                                  if p.get("error")}),
    }
    print(json.dumps(summary, indent=1)[:5000], flush=True)
    if not fixtures:
        print("FATAL: no fixtures extracted from the Hotspawn payload", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        code = main()
    finally:
        if _browser is not None:
            try:
                _browser.__exit__(None, None, None)
            except Exception:  # noqa: BLE001
                pass
    raise SystemExit(code)
