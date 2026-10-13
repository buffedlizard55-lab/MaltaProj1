#!/usr/bin/env python3
"""R-01 live refresh collector — session arena/b90700c6.

Runs on GitHub Actions (the sandbox shell cannot reach these hosts).  Everything it writes is a
derived, source-linked projection of public pages; raw bodies stay out of Git (only their
byte size and SHA-256 are recorded, in refresh/data/provenance.json, so anyone can re-fetch and
compare).

Sources
  1. Hotspawn Play Pick'em (fixture identity + exact UTC times ONLY):
       https://play.hotspawn.com/lobby, /cs2-pickems, /thp-pickems, /lol-pickems
     The Angular SSR pages embed their full render state in `<script id="ng-state">`.  Fixture id,
     competition, tier, stage, offered points, `scheduled_start_time` (ms epoch), `lock_time`,
     `lock_offset_sec` and the crowd pick percentages all come from that payload.  Crowd
     percentages are stored in the `crowd_pct_*` fields for transparency and are NEVER used by
     build.py (asserted there).
  2. EGamersWorld (external bookmaker match-winner odds, per bookmaker):
       https://egamersworld.com/<title>/matches, /events, event pages and per-match "Betting odds"
       tables.  Each price is recorded with the bookmaker name shown next to it.
  3. HLTV (rating context + fixture cross-check): world ranking page and upcoming-matches list.
  4. Valve Regional Standings (official Valve data, CC0) for a second, Valve-published rating.

No login, no private API, no evasion.  Unknown stays unknown: a field that cannot be read from the
source is written as null, never guessed.
"""
from __future__ import annotations

import gzip
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
DATA = ROOT / "refresh" / "data"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
]

EGW_LISTS = [
    ("cs2", "https://egamersworld.com/counterstrike/matches"),
    ("lol", "https://egamersworld.com/lol/matches"),
]
EGW_EVENTS = [
    ("cs2", "https://egamersworld.com/counterstrike/events"),
    ("lol", "https://egamersworld.com/lol/events"),
]

HLTV_PAGES = [
    ("hltv-ranking", "https://www.hltv.org/ranking/teams"),
    ("hltv-matches", "https://www.hltv.org/matches"),
    ("hltv-valve-ranking", "https://www.hltv.org/valve-ranking/teams"),
]

VRS_LATEST_API = ("https://api.github.com/repos/ValveSoftware/"
                  "counter-strike_regional_standings/contents/live/2026")

STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
CARD_BLOCK = re.compile(r"<app-pickem-vs-card\b", re.I)
STATE_TAG = re.compile(r'<script id="ng-state"[^>]*type="application/json"[^>]*>', re.I)

provenance: list[dict] = []


# --------------------------------------------------------------------------- fetching helpers
def fetch(url: str, timeout: int = 45, accept_json: bool = False) -> dict:
    headers = dict(HEADERS)
    if accept_json:
        headers["Accept"] = "application/vnd.github+json"
    req = Request(url, headers=headers)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rec = {"url": url, "fetched_utc": stamp, "status": None, "bytes": None, "sha256": None,
           "error": None}
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(20_000_000)
            rec.update(status=resp.status, bytes=len(body),
                       sha256=hashlib.sha256(body).hexdigest())
            rec["body"] = body
    except HTTPError as exc:  # noqa: PERF203
        rec["error"] = f"HTTPError {exc.code}"
        rec["status"] = exc.code
        rec["body"] = b""
    except (URLError, TimeoutError, OSError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["body"] = b""
    provenance.append({k: v for k, v in rec.items() if k != "body"})
    return rec


def text_of(html: str) -> str:
    plain = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    plain = re.sub(r"(?s)<[^>]+>", " ", plain)
    plain = unescape(plain)
    return re.sub(r"\s+", " ", plain).strip()


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


# --------------------------------------------------------------------------- Hotspawn
def walk_for_matches(node, out: list[dict]) -> None:
    """Collect every dict that looks like a Pick'em fixture (structure-agnostic)."""
    if isinstance(node, dict):
        keys = set(node)
        looks_like_match = (
            ({"participants0_name", "participants1_name"} <= keys)
            or ({"scheduled_start_time"} <= keys and ({"competition_name"} & keys))
            or ({"teamA", "teamB"} <= keys)
        )
        if looks_like_match:
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


def pct_pair(node: dict) -> tuple[int | None, int | None, int | None]:
    """Crowd pick percentages (reference only) — several payload shapes are tried."""
    picked = [node.get("participants0_picked_percent"),
              node.get("participants1_picked_percent")]
    if all(isinstance(x, (int, float)) for x in picked):
        return int(picked[0]), int(picked[1]), first(node, "total_picks", "picks_count")
    nested = node.get("participants")
    if isinstance(nested, list) and len(nested) >= 2 and all(isinstance(x, dict) for x in nested):
        p0 = first(nested[0], "picked_percent", "picked", "percent")
        p1 = first(nested[1], "picked_percent", "picked", "percent")
        if isinstance(p0, (int, float)) and isinstance(p1, (int, float)):
            return int(p0), int(p1), first(node, "total_picks", "picks_count")
    return None, None, first(node, "total_picks", "picks_count")


def normalise_fixture(node: dict, page: str, stamp: str) -> dict | None:
    start = ms_to_iso(first(node, "scheduled_start_time", "scheduledStartTime",
                            "scheduled_start"))
    if not start:
        return None
    offset = first(node, "lock_offset_sec", "lockOffsetSec")
    lock = ms_to_iso(first(node, "lock_time", "lockTime"))
    if not lock and isinstance(offset, (int, float)) and 0 < offset < 7200:
        lock = (datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                - timedelta(seconds=int(offset))).strftime("%Y-%m-%dT%H:%M:%SZ")
    pa, pb, picks = pct_pair(node)
    match_id = first(node, "id", "match_id", "matchId")
    team_a = first(node, "participants0_name", "teamA", "team_a")
    team_b = first(node, "participants1_name", "teamB", "team_b")
    if not (match_id and team_a and team_b):
        return None
    return {
        "match_id": str(match_id),
        "sport": first(node, "sport_alias", "sport", "game_alias", default=None),
        "competition": first(node, "competition_name", "competitionName", "competition",
                             "tournament", default=None),
        "status": first(node, "status", "match_status", default=None),
        "tier": first(node, "tier", "tier_name", default=None),
        "stage": first(node, "stage", "stage_name", default=None),
        "best_of": first(node, "best_of", "bestOf", "series_format", "format", default=None),
        "offered_points": first(node, "offered_points", "offeredPoints", "points", default=None),
        "base_points": first(node, "base_points", "basePoints", default=None),
        "scheduled_start_utc": start,
        "lock_utc": lock,
        "lock_offset_sec": int(offset) if isinstance(offset, (int, float)) else None,
        "team_a": team_a,
        "team_b": team_b,
        "team_a_id": first(node, "participants0_id", "teamA_id", default=None),
        "team_b_id": first(node, "participants1_id", "teamB_id", default=None),
        "crowd_pct_a": pa,
        "crowd_pct_b": pb,
        "total_picks": picks,
        "pages": [page],
        "source_url": f"https://play.hotspawn.com/{page}",
        "snapshot_utc": stamp,
    }


def collect_hotspawn() -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    fixtures: dict[str, dict] = {}
    page_report = []
    reset_utc = None
    week_total_text = None
    for page, url in HOTSPAWN_PAGES:
        got = fetch(url)
        entry = {"page": page, "url": url, "status": got["status"], "bytes": got["bytes"],
                 "sha256": got["sha256"], "error": got["error"], "state_rows": 0,
                 "cards_rendered": 0, "week_total_text": None, "reset_utc": None}
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            entry["cards_rendered"] = len(CARD_BLOCK.findall(html))
            plain = text_of(html)
            m = re.search(r"(\d+)\s+matches this week", plain)
            if m:
                week_total_text = int(m.group(1))
                entry["week_total_text"] = week_total_text
            m = re.search(r"Resets in (?:(\d+)d )?(?:(\d+)h )?(?:(\d+)m )?(?:(\d+)s)", plain)
            if m:
                d, h, mi, s = (int(g) if g else 0 for g in m.groups())
                reset_utc = (datetime.now(timezone.utc)
                             + timedelta(days=d, hours=h, minutes=mi, seconds=s)).strftime(
                                 "%Y-%m-%dT%H:%M:%SZ")
                entry["reset_utc"] = reset_utc
            m = STATE_SCRIPT.search(html)
            if m:
                payload = unescape(m.group(1)).strip()
                try:
                    state = json.loads(payload)
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
                        match_id = row["match_id"]
                        if match_id in fixtures:
                            if page not in fixtures[match_id]["pages"]:
                                fixtures[match_id]["pages"].append(page)
                        else:
                            fixtures[match_id] = row
            else:
                entry["error"] = "no ng-state script found"
        page_report.append(entry)
        time.sleep(0.5)

    rows = sorted(fixtures.values(), key=lambda r: (r["scheduled_start_utc"], r["match_id"]))
    return {"generated_utc": stamp, "reset_utc": reset_utc, "week_total_text": week_total_text,
            "pages": page_report, "fixtures": rows}


# --------------------------------------------------------------------------- EGamersWorld
MATCH_HREF = re.compile(
    r'href="(https://egamersworld\.com/(?:counterstrike|lol|dota2|valorant)/match/[^"#?]+)"')
EVENT_HREF = re.compile(
    r'href="(https://egamersworld\.com/(?:counterstrike|lol|dota2|valorant)/event/[^"#?]+)"')
# EGamersWorld renders every price as an anchor whose text is the decimal odd and whose href is
# the site's own "#" placeholder (the bookmaker link is attached to the logo next to it).
PRICE_TOKEN = re.compile(r">\s*(\d{1,2}\.\d{1,3})\s*<")
LOGO_ALT = re.compile(r'alt="([^"]{2,40})"')
BOOK_LOGO = re.compile(r"uploads/ensign/[^\"']+?/([^/\"']+?)\.(?:svg|webp|png)")
EGW_SLUG_TAIL = re.compile(r"-(?:[A-Za-z0-9_\-]{6,14})$")


def egw_match_pair(url: str) -> tuple[str, str] | None:
    slug = url.rstrip("/").split("/")[-1]
    m = re.match(r"(.+?)-vs-(.+)$", slug)
    if not m:
        return None
    left = m.group(1)
    right = EGW_SLUG_TAIL.sub("", m.group(2))
    return (left.replace("-", " ").strip(), right.replace("-", " ").strip())


def scan_list_page(html: str, base_url: str) -> dict:
    """Find match links and, for each, the price pair shown next to it on the listing page."""
    plain = re.sub(r"\s+", " ", html)
    rows, seen = {}, set()
    for m in MATCH_HREF.finditer(plain):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        window = plain[m.end(): m.end() + 1400]
        prices = [float(p) for p in PRICE_TOKEN.findall(window)][:4]
        rows[url] = {"match_url": url, "list_prices": prices}
    return {"url": base_url, "match_links": len(rows), "rows": rows}


def parse_match_page(html: str, url: str) -> dict:
    """Per-bookmaker match-winner prices from the 'Betting odds' table (map markets excluded)."""
    plain = re.sub(r"\s+", " ", html)
    title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    out: dict = {
        "match_url": url,
        "title": unescape(title.group(1)).strip() if title else None,
        "kickoff_text": None,
        "books": [],
        "widget": [],
        "layout": "unknown",
    }
    t = unescape(title.group(1)) if title else ""
    m = re.search(r"(\d{2}\.\d{2}\.\d{2})\s+(\d{1,2}:\d{2})", t)
    if m:
        out["kickoff_text"] = f"{m.group(1)} {m.group(2)}"

    # Price tokens on the page, in document order, each with the ~400 chars that precede it.
    tokens = []
    for m in PRICE_TOKEN.finditer(plain):
        before = plain[max(0, m.start() - 500):m.start()]
        tokens.append((float(m.group(1)), before))
    out["price_tokens_total"] = len(tokens)
    out["widget"] = [p for p, _ in tokens[:2]]

    # Bookmaker rows: the logo sits immediately before the two prices of that row.  Rows for map
    # or total markets carry a text label ("Winner Map 1/2", "Total", ...) instead of a logo, so
    # they never enter `books`.  Only the first pair seen for a bookmaker is kept: later pairs
    # from the same book on the same page belong to those secondary markets.
    books: list[dict] = []
    seen_books: set[str] = set()
    skip_labels = ("winner map", "total", "winner round", "handicap", "over/under", "odd/even")
    book_img = re.compile(r"<img[^>]*uploads/ensign/[^>]*>", re.I)
    for idx, (price, before) in enumerate(tokens):
        if idx + 1 >= len(tokens):
            break
        nxt = tokens[idx + 1][0]
        tail = before[-320:]
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
    out["layout"] = "book_table" if out["books"] else ("widget_only" if out["widget"] else "none")
    # A small, bounded snippet around the first price keeps parser changes verifiable without
    # committing third-party page bodies.
    first = plain.find("Betting odds")
    out["snippet"] = plain[first: first + 700] if first >= 0 else ""
    return out


def collect_egw(fixtures: list[dict]) -> dict:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lists: dict[str, dict] = {}
    event_links: list[str] = []
    for title, url in EGW_LISTS:
        got = fetch(url)
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            lists[title] = scan_list_page(html, url)
            event_links += EVENT_HREF.findall(html)
        else:
            lists[title] = {"url": url, "error": got["error"], "status": got["status"]}
        time.sleep(0.4)
    for title, url in EGW_EVENTS:
        got = fetch(url)
        if got["body"]:
            event_links += EVENT_HREF.findall(got["body"].decode("utf-8", errors="replace"))
        time.sleep(0.4)
    event_links = sorted(set(event_links))

    # Only fetch event pages whose slug looks like it could hold one of our slate's tournaments.
    wanted = set()
    for fx in fixtures:
        comp = (fx.get("competition") or "").lower()
        for word in re.findall(r"[a-z0-9]{4,}", comp):
            if word not in {"season", "series", "stage", "league", "cup", "the", "2026", "with"}:
                wanted.add(word)
    picked_events = [u for u in event_links
                     if any(w in u.lower() for w in wanted)][:30]

    candidates: dict[str, dict] = {}
    for url in picked_events:
        got = fetch(url)
        if got["body"]:
            scanned = scan_list_page(got["body"].decode("utf-8", errors="replace"), url)
            for match_url, row in scanned["rows"].items():
                candidates.setdefault(match_url, row)
        time.sleep(0.4)

    # Add everything visible on the title listing pages too.
    for title, entry in lists.items():
        for match_url, row in (entry.get("rows") or {}).items():
            candidates.setdefault(match_url, row)

    by_pair = {}
    for url, row in candidates.items():
        pair = egw_match_pair(url)
        if pair:
            row["teams_from_slug"] = pair
            by_pair.setdefault(norm_key(pair[0]) + "|" + norm_key(pair[1]), url)

    # Fetch the per-match page for every slate fixture that has a candidate link.
    readings = {}
    for fx in fixtures:
        ka, kb = norm_key(fx["team_a"]), norm_key(fx["team_b"])
        url = by_pair.get(ka + "|" + kb) or by_pair.get(kb + "|" + ka)
        if not url:
            readings[fx["match_id"]] = {"found": False, "reason": "no EGamersWorld match link "
                                                                  "matched this team pair"}
            continue
        got = fetch(url)
        if not got["body"]:
            readings[fx["match_id"]] = {"found": False, "match_url": url,
                                        "reason": f"match page fetch failed ({got['error']})"}
            time.sleep(0.4)
            continue
        parsed = parse_match_page(got["body"].decode("utf-8", errors="replace"), url)
        parsed["found"] = True
        parsed["reversed"] = by_pair.get(ka + "|" + kb) is None
        parsed["fetched_utc"] = stamp
        readings[fx["match_id"]] = parsed
        time.sleep(0.5)

    return {"generated_utc": stamp, "lists": lists, "events_scanned": picked_events,
            "candidate_matches": len(candidates), "readings": readings}


# --------------------------------------------------------------------------- HLTV
def collect_hltv() -> dict:
    out: dict = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "pages": {}, "ranking": {}, "valve_ranking": {}, "matches": []}
    for label, url in HLTV_PAGES:
        got = fetch(url)
        out["pages"][label] = {"url": url, "status": got["status"], "bytes": got["bytes"],
                               "sha256": got["sha256"], "error": got["error"]}
        if not got["body"]:
            time.sleep(0.5)
            continue
        html = got["body"].decode("utf-8", errors="replace")
        if label == "hltv-ranking":
            blocks = re.split(r'<div class="ranked-team', html)[1:]
            for block in blocks:
                pos = re.search(r'class="position[^"]*">#(\d+)<', block)
                name = re.search(r'class="name">([^<]+)</span>', block)
                pts = re.search(r'class="points">\((\d+)', block)
                if pos and name:
                    out["ranking"][unescape(name.group(1)).strip()] = {
                        "rank": int(pos.group(1)),
                        "points": int(pts.group(1)) if pts else None}
            out["ranking_url"] = url
        elif label == "hltv-valve-ranking":
            blocks = re.split(r'<div class="ranked-team', html)[1:]
            for block in blocks:
                pos = re.search(r'class="position[^"]*">#(\d+)<', block)
                name = re.search(r'class="name">([^<]+)</span>', block)
                pts = re.search(r'class="points">\((\d+)', block)
                if pos and name:
                    out["valve_ranking"][unescape(name.group(1)).strip()] = {
                        "rank": int(pos.group(1)),
                        "points": int(pts.group(1)) if pts else None}
            out["valve_ranking_url"] = url
        elif label == "hltv-matches":
            # Upcoming matches as (unix, team names, event) for an independent fixture cross-check.
            blocks = re.split(r'<div class="match-item', html)[1:]
            for block in blocks:
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
        time.sleep(0.6)
    out["ranking_url"] = out.get("ranking_url")
    out["valve_ranking_url"] = out.get("valve_ranking_url")
    return out


# --------------------------------------------------------------------------- Valve VRS
def collect_valve() -> dict:
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "file": None, "source_url": None, "teams": {}, "error": None}
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
    out["file"] = latest["name"]
    got = fetch(latest["download_url"])
    if not got["body"]:
        out["error"] = f"VRS file fetch failed: {got['error']}"
        return out
    out["source_url"] = latest["download_url"]
    body = got["body"].decode("utf-8", errors="replace")
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if not re.fullmatch(r"\d+", cells[0]):
            continue
        name = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cells[1]).strip()  # markdown links
        points = None
        for cell in cells[2:]:
            try:
                points = float(cell)
                break
            except ValueError:
                continue
        if name and points is not None:
            out["teams"][name] = {"points": points, "source_url": latest["download_url"]}
    return out


# --------------------------------------------------------------------------- name normalisation
def norm_key(name: str) -> str:
    s = unescape(name or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    hs = collect_hotspawn()
    fixtures = hs["fixtures"]
    # Only the live week gets an odds lookup: fixtures outside the window (the stale summer
    # listings Hotspawn still serves) are kept in the payload for transparency but never priced.
    now = datetime.now(timezone.utc)
    reset = None
    if hs.get("reset_utc"):
        reset = datetime.strptime(hs["reset_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
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
    print(f"slate candidates for odds lookup: {len(candidates)} of {len(fixtures)} payload rows")
    egw = collect_egw(candidates)
    hltv = collect_hltv()
    valve = collect_valve()

    payload = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "hotspawn": hs, "egw": egw, "hltv": hltv, "valve_vrs": valve}
    raw = json.dumps(payload, indent=1)
    (DATA / "collected.json").write_text(raw, encoding="utf-8")
    (DATA / "provenance.json").write_text(
        json.dumps({"generated_utc": payload["generated_utc"], "fetches": provenance}, indent=1),
        encoding="utf-8")

    cs2 = [f for f in fixtures if (f.get("sport") or "").lower() in {"cs2", "counterstrike", "cs"}]
    lol = [f for f in fixtures if (f.get("sport") or "").lower() in {"lol", "leagueoflegends"}]
    priced = sum(1 for r in egw["readings"].values() if r.get("books"))
    summary = {
        "generated_utc": payload["generated_utc"],
        "hotspawn_fixtures": len(fixtures),
        "hotspawn_cs2": len(cs2), "hotspawn_lol": len(lol),
        "other_sports": len(fixtures) - len(cs2) - len(lol),
        "week_total_text": hs["week_total_text"], "reset_utc": hs["reset_utc"],
        "ng_state_rows": {p["page"]: p["state_rows"] for p in hs["pages"]},
        "cards_rendered": {p["page"]: p["cards_rendered"] for p in hs["pages"]},
        "egw_candidates": egw["candidate_matches"],
        "egw_events_scanned": len(egw["events_scanned"]),
        "egw_fixtures_with_book_table": priced,
        "egw_fixtures_without_link": sum(1 for r in egw["readings"].values()
                                        if not r.get("found")),
        "hltv_ranking_teams": len(hltv["ranking"]),
        "hltv_valve_teams": len(hltv["valve_ranking"]),
        "hltv_matches": len(hltv["matches"]),
        "valve_vrs_file": valve["file"], "valve_vrs_teams": len(valve["teams"]),
        "valve_vrs_error": valve["error"],
        "fetch_status": sorted({(p["url"], p["status"]) for p in provenance}),
    }
    print(json.dumps(summary, indent=1)[:4000])
    if not fixtures:
        print("FATAL: no fixtures extracted from the Hotspawn payload", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
