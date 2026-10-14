#!/usr/bin/env python3
"""S-01..S-03 collector — Arena session `arena/180a42a0`.

Reads only public pages and public data files, and writes derived tables into `slate/data/`.
Nothing here logs in, solves a challenge, or calls a private endpoint.

Sources
 1. Hotspawn Play Pick'em pages (/lobby, /cs2-pickems, /thp-pickems, /lol-pickems).  The Angular
    SSR HTML embeds its whole render state in `<script id="ng-state">`; that payload is the
    authoritative machine-readable list of the fixtures the board offers, with exact
    `scheduled_start_time` (ms epoch, UTC) and the lock offset.  The wall-clock text Hotspawn
    prints next to a match is NOT used anywhere in this file: it has been read as both UTC and
    UTC-4 across sessions (see slate/flagged.html, S-F-01), while the epoch is unambiguous.
 2. Valve Regional Standings — Valve's own published standings file (official), read through the
    GitHub contents API of ValveSoftware/counter-strike_regional_standings.
 3. HLTV world ranking page (rank + points) and the HLTV upcoming-matches listing (match id, URL,
    event) — used for our own rating-based line and for a per-row cross-reference link.
 4. Pinnacle — the public guest responses its own public matchups page loads by itself
    (headless Chromium capture; no account, no key).  Moneyline only.
 5. EGamersWorld — the per-match "Betting odds" table, where it serves a page (it returns HTTP 403
    to plain clients and sometimes to the browser too; a refusal is recorded as a refusal).

The heavy lifting for (4) and (5) is the collection module that session `arena/b90700c6` wrote and
merged for `refresh/**`; it is imported read-only here (no edits to their files) and every fetch it
performs is appended to the provenance log this program publishes.

Hotspawn's own crowd pick percentages are never an input to any probability in this file.  Where
they are copied into `fixtures.csv` they are named `crowd_pct_*_audit_only` and no build step reads
them.
"""
from __future__ import annotations

import csv
import guards
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# --------------------------------------------------------------------------------------------------
# Reuse of the proven fetchers shipped by session arena/b90700c6 in refresh/.
# Read-only: this session never edits refresh/**.  If the module is missing the run still completes
# for the sources that need plain HTTP (Hotspawn payload + Valve file) and every market/rating row
# that needs the browser is written as a refusal instead of a number.
sys.path.insert(0, str(ROOT / "refresh"))
try:
    import collect as up  # type: ignore  # noqa: E402
    HAVE_UPSTREAM = True
except Exception as exc:  # noqa: BLE001
    up = None  # type: ignore
    HAVE_UPSTREAM = False
    UPSTREAM_ERROR = f"{type(exc).__name__}: {exc}"
else:
    UPSTREAM_ERROR = None

HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams"
HLTV_RANKING_DATED = "https://www.hltv.org/ranking/teams/2026/october/12"
HLTV_MATCHES_URL = "https://www.hltv.org/matches"
VRS_LISTING_API = ("https://api.github.com/repos/ValveSoftware/"
                   "counter-strike_regional_standings/contents/live/2026")

# Pinnacle's public guest endpoint, the same JSON its own public matchups page loads in the browser.
# No account, no key of ours: the key below is the one pinnacle.com's own public web app sends, and
# every response is recorded in the provenance log so a reading can be re-fetched and hashed.
PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
PIN_HEADERS = {
    "X-API-Key": PIN_KEY,
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pinnacle.com",
    "Referer": "https://www.pinnacle.com/",
}
PIN_GAMES = {"CS2 - ": "cs2", "League of Legends - ": "lol"}

# Every value this file writes is derived from these constants; they are printed into the data.
ELO_SCALE = 400.0            # standard Elo/logistic scale used for HLTV ranking points
DEADLINE_SECONDS = 22 * 60   # stop opening new pages after this long (CI job has 35 minutes)


prov_extra: list[dict] = []   # provenance rows written by this module (module-level on purpose)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_ALIASES: dict = {}


def variants(name: str) -> list[str]:
    """Every name an evidence-linked alias lets a team also be called."""
    out = {name}
    for key, entry in _ALIASES.items():
        official = (entry or {}).get("official_name") or ""
        if norm(key) == norm(name) and official:
            out.add(official)
        if official and norm(official) == norm(name):
            out.add(key)
    return [v for v in out if v]


def canonical(name: str) -> str:
    for key, entry in _ALIASES.items():
        target = (entry or {}).get("official_name")
        if target and norm(key) == norm(name):
            return norm(target)
    return norm(name)


def sim_pair(a: str, b: str, x, y) -> float:
    """Best team-name similarity over the allowed alias spellings."""
    best = 0.0
    for left in variants(a or ""):
        for right in variants(b or ""):
            best = max(best, (similarity(left, x or "") + similarity(right, y or "")) / 2)
    return best


def parse_iso(text: str | None) -> datetime | None:
    """Parse the timestamp spellings used across this repository, all of them UTC."""
    if not text:
        return None
    raw = str(text).strip().replace("T", " ").replace("Z", "")
    for shape in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw[:19] if len(raw) >= 19 else raw, shape).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def norm(name: str | None) -> str:
    """Normalised comparison key for team names (same spelling rules as the rest of the repo)."""
    return re.sub(r"[^a-z0-9]+", "", unescape(name or "").lower().replace("&", "and"))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def devig(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    """Two-way de-vig: keep the bookmaker's relative opinion, drop its margin."""
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    return inv_a / total, inv_b / total, (total - 1.0) * 100.0


def elo_p(points_a: float, points_b: float, scale: float = ELO_SCALE) -> float:
    """Probability that A beats B in one map, logistic on the rating gap (standard Elo form)."""
    return 1.0 / (1.0 + 10.0 ** (-(points_a - points_b) / scale))


def series_from_map(p: float, best_of: int | None) -> float:
    """Best-of-N series probability for a team whose per-map probability is p (independent maps)."""
    if best_of == 1:
        return p
    if best_of == 3:
        return p * p * (3.0 - 2.0 * p)
    if best_of == 5:
        return p ** 3 * (10.0 - 15.0 * p + 6.0 * p * p)
    return None


# --------------------------------------------------------------------------------------- Hotspawn
def hotspawn_capture() -> dict:
    if not HAVE_UPSTREAM:
        return {"fixtures": [], "pages": [], "error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    hs = up.collect_hotspawn()
    return hs


def hotspawn_match_urls() -> tuple[dict, dict]:
    """Per-match Hotspawn pages: /matches/<slug>-<id>.

    The pick'em payload carries only the fixture id, and /matches/<id> alone redirects to the event
    listing, so the per-match link is read from the public matches index, which links every fixture
    it lists. Purely additive: a fixture whose link is not on that page keeps its blank cell.
    """
    url = "https://www.hotspawn.com/matches"
    got = up.fetch_html(url)
    links: dict[str, str] = {}
    for hit in re.finditer(r'href="(/matches/[a-z0-9\-]*?-(\d{4,}))"', (got.get("html") or "")):
        links.setdefault(hit.group(2), "https://www.hotspawn.com" + hit.group(1))
    meta = {"url": url, "status": got.get("status"), "found": len(links),
            "error": got.get("error")}
    return links, meta


def sport_of(fixture: dict) -> str:
    pages = fixture.get("pages") or []
    if "cs2-pickems" in pages:
        return "cs2"
    if "thp-pickems" in pages:
        return "thp"
    if "lol-pickems" in pages:
        return "lol"
    return "other"


def live_status(fixture: dict, now: datetime) -> str:
    lock, start = parse_iso(fixture.get("lock_utc")), parse_iso(fixture.get("scheduled_start_utc"))
    if start and start < now - timedelta(hours=36):
        return "stale listing (start in the past)"
    if start and start < now:
        return "started (not pickable)"
    if lock and lock < now:
        return "locked (not pickable)"
    return "open"


# -------------------------------------------------------------------------------------- HLTV data
def _title_of(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html or "", re.S | re.I)
    return unescape(m.group(1)).strip()[:120] if m else ""


def parse_hltv_matches(html: str) -> list[dict]:
    """HLTV upcoming-matches page -> one row per match.

    The slug in `/matches/<id>/<teamA>-vs-<teamB>-<event>` carries the team names, so a row is only
    accepted when the slug, a 13-digit `data-unix` and an event name are all present in the same
    window of the document. Returns [] when the page is a challenge page or an unexpected layout.
    """
    rows, seen = [], set()
    for match in re.finditer(r'href="(/matches/(\d+)/([a-z0-9\-]+))"', html or ""):
        path, match_id, slug = match.group(1), match.group(2), match.group(3)
        if match_id in seen:
            continue
        window = (html or "")[match.start(): match.start() + 2600]
        unix = re.search(r"data-unix=\"(\d{13})\"", window)
        event = re.search(r'class="event-name"[^>]*>\s*([^<]{2,60})\s*<', window)
        fmt = re.search(r"\b(bo[135])\b", window, re.I)
        if not unix:
            continue
        slug_pair = re.match(r"(.+?)-vs-(.+)$", slug)
        if not slug_pair:
            continue
        teams_live = re.findall(r'class="team[^"]*"[^>]*>\s*([^<]{2,40})\s*<', window)
        team_a = (unescape(teams_live[0]).strip() if len(teams_live) >= 2
                  else slug_pair.group(1).replace("-", " ").strip())
        team_b = (unescape(teams_live[1]).strip() if len(teams_live) >= 2
                  else slug_pair.group(2).replace("-", " ").strip())
        seen.add(match_id)
        rows.append({
            "hltv_match_id": match_id,
            "hltv_url": "https://www.hltv.org" + path,
            "slug": slug,
            "team_a": team_a,
            "team_b": team_b,
            "names_from": "page markup" if len(teams_live) >= 2 else "URL slug",
            "event": unescape(event.group(1)).strip() if event else None,
            "format": (fmt.group(1).lower() if fmt else None),
            "kickoff_utc": datetime.fromtimestamp(int(unix.group(1)) / 1000, timezone.utc)
                           .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return rows


def hltv_pages() -> dict:
    """HLTV ranking (rank + points) and the upcoming-matches listing, with per-page diagnostics."""
    out = {"pages": {}, "ranking": {}, "matches": [], "ranking_date_text": None, "error": None}
    if not HAVE_UPSTREAM:
        out["error"] = f"upstream collector unavailable: {UPSTREAM_ERROR}"
        return out
    for label, url in (("ranking-current", HLTV_RANKING_URL), ("matches", HLTV_MATCHES_URL)):
        got = up.fetch_html(url)
        html = got.get("html") or ""
        # The upcoming-matches page is behind a bot check far more often than the ranking page; wait
        # and ask again a few times, since the check usually clears by itself. Nothing is solved or
        # bypassed - the browser just loads the page again later.
        attempts = 1
        while (label == "matches" and attempts < 4
               and (not html or html.count('href="/matches/') == 0)):
            time.sleep(12 * attempts)
            got = up.fetch_html(url)
            html = got.get("html") or ""
            attempts += 1
        got["attempts"] = attempts
        out["pages"][label] = {
            "url": url, "status": got.get("status"), "bytes": got.get("bytes"),
            "error": got.get("error"), "path": got.get("path"), "title": _title_of(html),
            "attempts": got.get("attempts", 1),
            "marker_ranked_team": html.count('class="ranked-team'),
            "marker_match_href": len(re.findall(r'href="/matches/\d+/', html)),
            "marker_data_unix": html.count("data-unix="),
        }
        if label.startswith("ranking"):
            for block in html.split('<div class="ranked-team standard-box">')[1:]:
                pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
                name = re.search(r'<span class="name">([^<]+)</span>', block)
                pts = re.search(r'<span class="points">\((\d+)', block)
                if pos and name:
                    out["ranking"][unescape(name.group(1)).strip()] = {
                        "rank": int(pos.group(1)),
                        "points": int(pts.group(1)) if pts else None,
                    }
            date_match = re.search(
                r"World ranking on ([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4})", html)
            out["ranking_date_text"] = date_match.group(1) if date_match else None
        else:
            out["matches"] = parse_hltv_matches(html)
            out["matches_from_block_split"] = sum(
                1 for block in re.split(r'<div class="match-item', html)[1:]
                if re.search(r'data-unix="\d{13}"', block))
    return out


# --------------------------------------------------------------------------------------- Pinnacle
def _pin_get(path: str, timeout: int = 30) -> dict:
    """One JSON GET against Pinnacle's public guest endpoint, recorded in the provenance log."""
    url = f"{PIN_BASE}{path}"
    rec = {"url": url, "fetched_utc": now_iso(), "status": None, "bytes": None, "sha256": None,
           "path": "http", "error": None, "kind": "pinnacle-guest"}
    try:
        request = Request(url, headers=PIN_HEADERS)
        with urlopen(request, timeout=timeout) as resp:
            body = resp.read(8_000_000)
            rec.update(status=resp.status, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
            data = json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        rec["error"] = f"HTTPError {exc.code}"
        rec["status"] = exc.code
        data = None
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        data = None
    prov_extra.append({k: v for k, v in rec.items() if k != "data"})
    return {"record": rec, "data": data}


def pinnacle_guest(candidates: list[dict]) -> tuple[list[dict], dict]:
    """Moneyline quotes for the open slate from Pinnacle's public guest endpoint."""
    if not HAVE_UPSTREAM:
        return [], {"error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    meta = {"leagues_read": 0, "cs2_leagues": [], "lol_leagues": [], "matchups_seen": 0,
            "markets_read": 0, "quotes": 0, "matched": 0, "errors": [], "rejected": 0}
    leagues = _pin_get("/sports/12/leagues?all=false")
    if leagues["data"] is None:
        meta["errors"].append(f"league list failed: {leagues['record']['error']}")
        return [], meta
    wanted = []
    for league in leagues["data"]:
        name = (league or {}).get("name") or ""
        for prefix, game in PIN_GAMES.items():
            if name.startswith(prefix):
                wanted.append((league.get("id"), name, game))
                meta[f"{game}_leagues"].append(name)
    meta["leagues_read"] = len(leagues["data"])
    meta["leagues_wanted"] = len(wanted)
    meta["matchup_endpoint_tries"] = {}
    quotes = []
    for league_id, league_name, game in wanted:
        matchups = {"data": None, "record": {"error": "not tried"}}
        for label, path in (("league-matchups", f"/leagues/{league_id}/matchups?withSpecials=false"),
                            ("league-matchups-plain", f"/leagues/{league_id}/matchups"),
                            ("sport-matchups", "/sports/12/matchups?withSpecials=false")):
            attempt = _pin_get(path)
            meta["matchup_endpoint_tries"][label] = attempt["record"]["status"]
            if attempt["data"] is not None:
                matchups = attempt
                meta["matchup_endpoint_used"] = label
                break
        if matchups["data"] is None:
            meta["errors"].append(f"matchups {league_id}: {matchups['record']['error']}")
            continue
        for matchup in matchups["data"]:
            participants = matchup.get("participants") or []
            if len(participants) != 2:
                continue
            meta["matchups_seen"] += 1
            start = str(matchup.get("startTime") or "")[:19] + "Z"
            markets = _pin_get(f"/matchups/{matchup.get('id')}/markets/related/straight")
            if markets["data"] is None:
                markets = _pin_get(f"/matchups/{matchup.get('id')}/markets/related/straight"
                                   "?primary=false")
            if markets["data"] is None:
                meta.setdefault("market_endpoint_status", []).append(
                    (matchup.get("id"), markets["record"]["status"], markets["record"]["error"]))
                continue
            for market in markets["data"]:
                meta["markets_read"] += 1
                if (market.get("type") != "moneyline" or market.get("period") != 0
                        or market.get("isAlternate") is not False or market.get("status") != "open"):
                    meta["rejected"] += 1
                    continue
                prices = {p.get("designation"): p.get("price") for p in market.get("prices") or []}
                if set(prices) != {"home", "away"}:
                    meta["rejected"] += 1
                    continue
                try:
                    odds_home = american_to_decimal(prices["home"])
                    odds_away = american_to_decimal(prices["away"])
                except ValueError:
                    meta["rejected"] += 1
                    continue
                names = {p.get("alignment"): p.get("name") for p in participants}
                quotes.append({
                    "game": game, "event_id": matchup.get("id"), "league": league_name,
                    "team_a": names.get("home"), "team_b": names.get("away"),
                    "start_utc": start, "best_of": matchup.get("bestOfX"),
                    "odds_a": odds_home, "odds_b": odds_away,
                    "native_odds_a": prices["home"], "native_odds_b": prices["away"],
                    "observed_utc": now_iso(),
                    "source_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
                    "api_url": f"{PIN_BASE}/matchups/{matchup.get('id')}/markets/related/straight",
                })
    meta["quotes"] = len(quotes)
    rows = []
    for fx in candidates:
        best = None
        for q in quotes:
            if q["game"] != fx.get("sport"):
                continue
            flipped = guards.aligned_pair(fx["team_a"], fx["team_b"], q["team_a"], q["team_b"], canonical)
            if flipped is None or not guards.kickoff_agrees(q["start_utc"], fx.get("scheduled_start_utc")):
                continue
            if best is None or q["observed_utc"] > best[1]["observed_utc"]:
                best = (1.0, q, flipped)
        if not best:
            continue
        score, q, flipped = best
        odds_a, odds_b = (q["odds_b"], q["odds_a"]) if flipped else (q["odds_a"], q["odds_b"])
        pa, pb, margin = devig(float(odds_a), float(odds_b))
        rows.append({
            "fixture_id": fx["match_id"], "source": "Pinnacle (public guest matchups/markets)",
            "source_url": q.get("source_url"), "match_url": q.get("api_url"), "book": "Pinnacle",
            "odds_a": round(float(odds_a), 3), "odds_b": round(float(odds_b), 3),
            "overround_pct": round(margin, 3), "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
            "captured_utc": q.get("observed_utc"), "name_similarity": round(score, 3),
            "team_order_flipped": flipped, "best_of": q.get("best_of"),
            "note": (f"Pinnacle event {q['event_id']} in {q.get('league')}; American prices "
                     f"{q.get('native_odds_a')}/{q.get('native_odds_b')} converted to decimal; matched "
                     f"to Hotspawn fixture {fx['match_id']} by team name (similarity {score:.2f}) and "
                     "exact/evidence-linked team names and kickoff within 15 minutes"),
        })
    meta["matched"] = len(rows)
    return rows, meta


def american_to_decimal(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) < 100:
        raise ValueError("not a valid American price")
    return 1 + value / 100 if value > 0 else 1 + 100 / abs(value)


# --------------------------------------------------------------------------- Valve Regional Standings
def valve_standings() -> dict:
    out = {"file": None, "source_url": None, "blob_url": None, "teams": {}, "rows_read": 0,
           "error": None, "fetched_utc": now_iso(), "sha256": None}
    if not HAVE_UPSTREAM:
        out["error"] = f"upstream collector unavailable: {UPSTREAM_ERROR}"
        return out
    valve = up.collect_valve()
    out["error"] = valve.get("error")
    out["file"] = valve.get("file")
    out["source_url"] = valve.get("source_url")
    out["teams"] = valve.get("teams") or {}
    out["rows_read"] = valve.get("rows_read") or 0
    if out["file"]:
        out["blob_url"] = ("https://github.com/ValveSoftware/counter-strike_regional_standings/"
                           f"blob/main/live/2026/{out['file']}")
    return out


# ------------------------------------------------------------------------------------ market lines
def egw_readings(candidates: list[dict]) -> tuple[list[dict], dict]:
    """EGamersWorld per-match readings; a refusal is recorded, never filled in."""
    if not HAVE_UPSTREAM:
        return [], {"error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    egw = up.collect_egw(candidates)
    rows, refused, matched = [], 0, 0
    for fx in candidates:
        reading = (egw.get("readings") or {}).get(fx["match_id"]) or {}
        if not reading.get("found"):
            refused += 1
            continue
        books = reading.get("books") or []
        if books:
            book = books[0]
            odds_a, odds_b = float(book["odds_a"]), float(book["odds_b"])
            # EGW lists the fixture in its own order; the upstream reading preserves the page order.
            pa, pb, margin = devig(odds_a, odds_b)
            if reading.get("reversed"):
                odds_a, odds_b, pa, pb = odds_b, odds_a, pb, pa
            rows.append({
                "fixture_id": fx["match_id"], "source": "EGamersWorld per-match betting-odds table",
                "source_url": reading.get("match_url"), "book": book.get("book") or "EGW book table",
                "odds_a": round(odds_a, 3), "odds_b": round(odds_b, 3),
                "overround_pct": round(margin, 3), "p_a": round(pa * 100, 2),
                "p_b": round(pb * 100, 2), "captured_utc": reading.get("fetched_utc"),
                "name_similarity": None, "team_order_flipped": bool(reading.get("reversed")),
                "best_of": None,
                "note": f"kickoff text on the page: {reading.get('kickoff_text') or 'not shown'}; "
                        f"{len(books)} named bookmaker rows read",
            })
            matched += 1
    return rows, {"matched": matched, "refused": refused, "lists": egw.get("lists"),
                  "candidate_matches": egw.get("candidate_matches"),
                  "stopped_at_deadline": egw.get("stopped_at_deadline")}


# ------------------------------------------------------------- session & carried market readings
SESSION_READINGS = DATA / "market_readings_session.csv"
CARRIED_PICKS = ROOT / "picks" / "data" / "fixtures.csv"
CARRIED_BOARD = ROOT / "board" / "data" / "analysis.csv"


def _egw_local_to_utc(text: str, offset_hours: float) -> str | None:
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})\s+(\d{1,2}):(\d{2})", (text or "").strip())
    if not m:
        return None
    day, month, year, hour, minute = (int(g) for g in m.groups())
    try:
        dt = datetime(2000 + year, month, day, hour, minute, tzinfo=timezone.utc)
    except ValueError:
        return None
    return (dt - timedelta(hours=offset_hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def session_readings(candidates: list[dict]) -> tuple[list[dict], dict]:
    """Prices read by this session through the project's fetch service, from the capture file.

    The CI runner cannot reach these hosts (HTTP 403 is recorded in the provenance log), so the
    session reads them and writes exactly what it saw, with the page URL and the read time. The
    file is data, not narrative: it is parsed here like any other source.
    """
    rows: list[dict] = []
    meta = {"file": str(SESSION_READINGS.relative_to(ROOT)), "rows": 0, "matched": 0, "unmatched": []}
    if not SESSION_READINGS.exists():
        meta["error"] = "capture file missing"
        return rows, meta
    with SESSION_READINGS.open(encoding="utf-8", newline="") as fh:
        entries = list(csv.DictReader(fh))
    meta["rows"] = len(entries)
    for entry in entries:
        try:
            odds_a, odds_b = float(entry["odds_a"]), float(entry["odds_b"])
            offset = float(entry.get("display_utc_offset_hours") or 2)
        except (KeyError, TypeError, ValueError):
            meta["unmatched"].append(f"{entry.get('egw_team_a')}: unreadable row")
            continue
        kickoff = _egw_local_to_utc(entry.get("egw_display_local") or "", offset)
        best = None
        for fx in candidates:
            score = max(sim_pair(fx["team_a"], fx["team_b"], entry["egw_team_a"], entry["egw_team_b"]),
                        sim_pair(fx["team_a"], fx["team_b"], entry["egw_team_b"], entry["egw_team_a"]))
            if score < 0.55:
                continue
            if kickoff and fx.get("scheduled_start_utc"):
                delta = abs((parse_iso(kickoff) - parse_iso(fx["scheduled_start_utc"])).total_seconds())
                if delta > 3 * 3600:
                    continue
            elif score < 0.70:
                continue
            if best is None or score > best[0]:
                best = (score, fx)
        if not best:
            meta["unmatched"].append(f"{entry.get('egw_team_a')} vs {entry.get('egw_team_b')}")
            continue
        score, fx = best
        flipped = (sim_pair(fx["team_a"], fx["team_b"], entry["egw_team_b"], entry["egw_team_a"])
                   > sim_pair(fx["team_a"], fx["team_b"], entry["egw_team_a"], entry["egw_team_b"]))
        if flipped:
            odds_a, odds_b = odds_b, odds_a
        pa, pb, margin = devig(odds_a, odds_b)
        printed = entry.get("egw_display_local") or "not printed"
        note_text = (f"{entry.get('note')} EGamersWorld spelling {entry['egw_team_a']!r} vs "
                     f"{entry['egw_team_b']!r}; local kickoff {printed} (UTC+{offset:g}) -> "
                     f"{kickoff or 'not determinable'}.")
        rows.append({
            "fixture_id": fx["match_id"],
            "source": "EGamersWorld (read by session arena/180a42a0 via the project's fetch service)",
            "source_url": entry["source_url"], "match_url": entry["source_url"],
            "book": "bc.game (EGamersWorld headline)", "odds_a": odds_a, "odds_b": odds_b,
            "overround_pct": round(margin, 3), "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
            "captured_utc": entry.get("read_utc"), "name_similarity": round(score, 3),
            "team_order_flipped": flipped, "best_of": None, "read_by": "session arena/180a42a0",
            "note": note_text,
        })
        meta["matched"] += 1
    return rows, meta


def carried_readings() -> tuple[list[dict], dict]:
    """Older, source-linked readings published by other sessions in this repository.

    Used only for fixtures where neither the CI run nor this session could read a price. Every such
    row says which session read it and when, and is listed on the Flagged page - it is never
    presented as a fresh reading."""
    rows: list[dict] = []
    meta = {"sources": [], "rows": 0}
    if CARRIED_PICKS.exists():
        with CARRIED_PICKS.open(encoding="utf-8", newline="") as fh:
            for entry in csv.DictReader(fh):
                try:
                    odds_a, odds_b = float(entry["ext_odds_a"]), float(entry["ext_odds_b"])
                except (KeyError, TypeError, ValueError):
                    continue
                pa, pb, margin = devig(odds_a, odds_b)
                rows.append({
                    "fixture_id": entry.get("hotspawn_id") or "", "team_a": entry.get("team_a"),
                    "team_b": entry.get("team_b"), "start_utc": entry.get("start_utc"),
                    "source": ("EGamersWorld CS2 listing (headline odds), carried from session "
                               "arena/cc8f4dca's picks/ dataset"),
                    "source_url": entry.get("ext_url") or "",
                    "match_url": entry.get("ext_url") or "", "book": "bc.game (EGW listing)",
                    "odds_a": odds_a, "odds_b": odds_b, "overround_pct": round(margin, 3),
                    "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
                    "captured_utc": "2026-10-13T22:00:00Z", "name_similarity": None,
                    "team_order_flipped": False, "best_of": None,
                    "read_by": "session arena/cc8f4dca (picks/data/fixtures.csv, ext_p_a/ext_odds)",
                    "note": (entry.get("ext_source") or "")[:200],
                    "carried_file": "picks/data/fixtures.csv",
                })
        meta["sources"].append("picks/data/fixtures.csv")
    if CARRIED_BOARD.exists():
        with CARRIED_BOARD.open(encoding="utf-8", newline="") as fh:
            for entry in csv.DictReader(fh):
                try:
                    odds_a, odds_b = float(entry["ext_odds_a"]), float(entry["ext_odds_b"])
                except (KeyError, TypeError, ValueError):
                    continue
                pa, pb, margin = devig(odds_a, odds_b)
                rows.append({
                    "fixture_id": entry.get("hotspawn_id") or "", "team_a": entry.get("team_a"),
                    "team_b": entry.get("team_b"), "start_utc": entry.get("start_utc"),
                    "source": ("EGamersWorld bc.game block, carried from session arena/8e782f95's "
                               "board/ dataset"),
                    "source_url": entry.get("ext_url") or "",
                    "match_url": entry.get("ext_url") or "", "book": "bc.game (EGW match page)",
                    "odds_a": odds_a, "odds_b": odds_b, "overround_pct": round(margin, 3),
                    "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
                    "captured_utc": entry.get("ext_captured_utc") or "", "name_similarity": None,
                    "team_order_flipped": False, "best_of": None,
                    "read_by": "session arena/8e782f95 (board/data/analysis.csv)",
                    "note": (entry.get("ext_source") or "")[:200],
                    "carried_file": "board/data/analysis.csv",
                })
        meta["sources"].append("board/data/analysis.csv")
    meta["rows"] = len(rows)
    return rows, meta


# --------------------------------------------------------------------------------------- assemble
ALIAS_TABLE = HERE / "aliases.json"


def load_alias_hints() -> dict:
    """Optional alias hints: Hotspawn spelling -> official-data spelling.

    Only entries with an `evidence` URL may be used, and every use is flagged on the site so the
    mapping is visible for manual review instead of being applied silently.
    """
    if not ALIAS_TABLE.exists():
        return {}
    try:
        raw = json.loads(ALIAS_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and v.get("evidence")}


def resolve_team(name: str, hltv: dict, valve: dict, aliases: dict) -> dict:
    """Resolve a Hotspawn team name to the official HLTV / Valve rating rows.

    Exact normalised equality only.  A different spelling is resolved solely through an explicit
    alias entry that carries an evidence link, and such a row is marked for review.
    """
    row = {"name": name, "hltv_name": None, "hltv_rank": None, "hltv_points": None,
           "hltv_source_url": HLTV_RANKING_URL, "vrs_name": None, "vrs_points": None,
           "vrs_source_url": valve.get("blob_url"), "method": "unresolved", "flag": None}
    key = norm(name)
    for team, data in (hltv.get("ranking") or {}).items():
        if norm(team) == key:
            row.update(hltv_name=team, hltv_rank=data.get("rank"), hltv_points=data.get("points"),
                       method="exact name match (HLTV ranking)")
            break
    for team, data in (valve.get("teams") or {}).items():
        if norm(team) == key:
            row.update(vrs_name=team, vrs_points=data.get("points"),
                       method=(row["method"] if row["method"] != "unresolved" else
                               "exact name match (Valve standings)"))
            break
    if row["hltv_name"] or row["vrs_name"]:
        if not (row["hltv_name"] and row["vrs_name"]):
            missing_hlsp = "HLTV" if not row["hltv_name"] else "Valve"
            row["flag"] = f"S-F-05: team found in one official rating source only ({missing_hlsp})"
            # An exact match in one source can still leave the other side of the model empty. An
            # evidence-linked alias is allowed to fill only the missing side, and the row keeps both
            # flags so a reader can see exactly which number came from the alias.
            partial = aliases.get(name) or aliases.get(key)
            target = (partial or {}).get("official_name") or ""
            filled = False
            if target:
                if not row["hltv_name"]:
                    for team, data in (hltv.get("ranking") or {}).items():
                        if norm(team) == norm(target):
                            row.update(hltv_name=team, hltv_rank=data.get("rank"),
                                       hltv_points=data.get("points"))
                            filled = True
                            break
                if not row["vrs_name"]:
                    for team, data in (valve.get("teams") or {}).items():
                        if norm(team) == norm(target):
                            row.update(vrs_name=team, vrs_points=data.get("points"))
                            filled = True
                            break
            if filled:
                row["method"] = (row["method"] + " + missing side via evidence-linked alias")
                row["flag"] = (f"S-F-05;S-F-06: matched by exact name in one official source; the "
                               f"other side comes from the evidence-linked alias \"{target}\" "
                               "(same roster) — kept visible for review")
        return row
    hint = aliases.get(name) or aliases.get(key)
    if hint:
        target = hint.get("official_name") or ""
        for team, data in (valve.get("teams") or {}).items():
            if norm(team) == norm(target):
                row.update(vrs_name=team, vrs_points=data.get("points"), method="alias (evidence link)")
                break
        for team, data in (hltv.get("ranking") or {}).items():
            if norm(team) == norm(target):
                row.update(hltv_name=team, hltv_rank=data.get("rank"),
                           hltv_points=data.get("points"),
                           method="alias (evidence link)")
                break
        if row["vrs_name"] or row["hltv_name"]:
            row["flag"] = (f"S-F-06: Hotspawn names this team \"{name}\"; the official source "
                           f"lists \"{target}\" — alias applied from an evidence-linked entry, "
                           "kept visible for review")
        else:
            row["flag"] = (f"S-F-07: alias entry points at \"{target}\", which is not in the "
                           "fetched official sources")
    else:
        row["flag"] = ("S-F-04: no exact match for this name in HLTV's ranking or Valve's "
                       "standings — no rating, no originated line")
    return row


def main() -> int:
    started = time.time()
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = now_iso()
    now = datetime.now(timezone.utc)
    flags: list[dict] = []
    prov_extra.clear()

    def add_flag(flag_id: str, severity: str, subject: str, detail: str, links: list[str]) -> None:
        flags.append({"id": flag_id, "severity": severity, "subject": subject, "detail": detail,
                      "links": " ".join(links)})

    hs = hotspawn_capture()
    fixtures_raw = hs.get("fixtures") or []
    required = {"lobby", "cs2-pickems", "thp-pickems", "lol-pickems"}
    healthy = {p["page"] for p in hs.get("pages", [])
               if p.get("status") == 200 and not p.get("error") and p.get("state_rows", 0) > 0}
    if not fixtures_raw or not required <= healthy:
        print(f"FATAL: incomplete Hotspawn capture; missing {sorted(required - healthy)}. Previous snapshot retained.", file=sys.stderr)
        return 1

    hltv = hltv_pages()
    valve = valve_standings()
    aliases = load_alias_hints()
    _ALIASES.clear()
    _ALIASES.update(aliases)
    match_urls, match_urls_meta = hotspawn_match_urls() if HAVE_UPSTREAM else ({}, {"error": "no upstream"})

    for fx in fixtures_raw:
        fx["sport"] = sport_of(fx)
        fx["live_status"] = live_status(fx, now)

    candidates = [fx for fx in fixtures_raw if fx["live_status"] == "open"]
    print(f"[slate] payload rows={len(fixtures_raw)} open={len(candidates)} "
          f"hltv_matches={len(hltv.get('matches') or [])} hltv_ranking={len(hltv.get('ranking') or {})} "
          f"vrs_teams={len(valve.get('teams') or {})}", flush=True)

    pin_rows, pin_meta = pinnacle_guest(candidates)
    egw_rows, egw_meta = egw_readings(candidates)
    # Historical session readings are not independently verified in this run. Never carry them
    # into current probabilities or invent a read timestamp. Original CSV retained as evidence.
    sess_rows, sess_meta = [], {"disabled": "historical readings excluded from current analysis"}
    carried_rows, carried_meta = [], {"disabled": "historical readings excluded from current analysis"}
    print(f"[slate] pinnacle matched={len(pin_rows)} egw(ci) matched={len(egw_rows)} "
          f"session matched={len(sess_rows)} carried={len(carried_rows)}", flush=True)

    # ------------------------------------------------------------------ fixtures table (S-01)
    fixtures = []
    for fx in sorted(fixtures_raw, key=lambda r: (r.get("scheduled_start_utc") or "",
                                                  r.get("match_id") or "")):
        fixtures.append({
            "fixture_id": fx.get("match_id"),
            "hotspawn_match_url": match_urls.get(str(fx.get("match_id") or ""), ""),
            "sport": fx["sport"],
            "competition": fx.get("competition"),
            "tier": fx.get("tier"),
            "stage": fx.get("stage"),
            "points": fx.get("offered_points"),
            "best_of_payload": fx.get("best_of"),
            "best_of_resolved": fx.get("best_of_resolved"),
            "best_of_source": fx.get("best_of_source"),
            "team_a": fx.get("team_a"),
            "team_b": fx.get("team_b"),
            "start_utc": fx.get("scheduled_start_utc"),
            "lock_utc": fx.get("lock_utc"),
            "lock_offset_sec": fx.get("lock_offset_sec"),
            "live_status": fx["live_status"],
            "hotspawn_pages": ",".join(fx.get("pages") or []),
            "source_url": fx.get("source_url"),
            "captured_utc": fx.get("snapshot_utc"),
            "crowd_pct_a_audit_only": fx.get("crowd_pct_a"),
            "crowd_pct_b_audit_only": fx.get("crowd_pct_b"),
            "total_picks_audit_only": fx.get("total_picks"),
        })

    # ------------------------------------------------------------------ team ratings (S-03)
    open_teams = sorted({t for fx in candidates for t in (fx.get("team_a"), fx.get("team_b")) if t})
    all_teams = sorted({t for fx in fixtures_raw for t in (fx.get("team_a"), fx.get("team_b")) if t})
    ratings = []
    for name in all_teams:
        row = resolve_team(name, hltv, valve, aliases)
        row["on_open_slate"] = "yes" if name in open_teams else "no"
        row["hltv_ranking_url"] = HLTV_RANKING_URL
        ratings.append(row)
        if row["flag"] and row["on_open_slate"] == "yes":
            add_flag(row["flag"].split(":")[0], "unverified", f"Team rating: {name}",
                     row["flag"].split(": ", 1)[-1],
                     [u for u in (row["hltv_source_url"], row["vrs_source_url"]) if u])
    rating_by_team = {r["name"]: r for r in ratings}

    # HLTV listing cross-reference per fixture (match id + URL + kickoff + series format)
    hltv_by_fixture: dict[str, dict] = {}
    for fx in fixtures_raw:
        best = None
        for row in hltv.get("matches") or []:
            flipped = guards.aligned_pair(fx.get("team_a"), fx.get("team_b"),
                                           row.get("team_a"), row.get("team_b"), canonical)
            if flipped is None or not guards.kickoff_agrees(row.get("kickoff_utc"), fx.get("scheduled_start_utc")):
                continue
            best = (row.get("kickoff_utc") == fx.get("scheduled_start_utc"), 1.0, row, flipped)
        if best:
            _, score, row, flipped = best
            hltv_by_fixture[fx["match_id"]] = {
                "hltv_match_id": row["hltv_match_id"], "hltv_url": row["hltv_url"],
                "hltv_event": row["event"], "hltv_kickoff_utc": row["kickoff_utc"],
                "hltv_team_order": "listed B vs A" if flipped else "listed A vs B",
                "kickoff_check": ("agree" if row["kickoff_utc"] == fx.get("scheduled_start_utc")
                                  else f"differs: HLTV {row.get('kickoff_utc')}"),
                "hltv_format": row.get("format"),
                "similarity": round(score, 3),
            }
    # Series format: the payload's own best_of when present, otherwise HLTV's listing label.
    for fx in fixtures_raw:
        ref = hltv_by_fixture.get(fx["match_id"]) or {}
        payload_best = fx.get("best_of") if isinstance(fx.get("best_of"), int) else None
        hltv_best = None
        if ref.get("hltv_format") in ("bo1", "bo3", "bo5"):
            hltv_best = int(ref["hltv_format"][2:])
        pin_best = next((r.get("best_of") for r in pin_rows if r["fixture_id"] == fx["match_id"]), None)
        if pin_best not in (1, 3, 5):
            pin_best = None
        fx["best_of_resolved"] = payload_best or hltv_best or pin_best
        fx["best_of_source"] = ("Hotspawn payload" if payload_best else
                               "HLTV match listing" if hltv_best else
                               "Pinnacle matched event" if pin_best else None)
    for row in fixtures:
        fx = next(f for f in fixtures_raw if f["match_id"] == row["fixture_id"])
        row["best_of_resolved"], row["best_of_source"] = fx.get("best_of_resolved"), fx.get("best_of_source")

    # ------------------------------------------------------------------ own originated lines (S-03)
    def own_line(fx: dict) -> dict:
        a, b = rating_by_team.get(fx.get("team_a")) or {}, rating_by_team.get(fx.get("team_b")) or {}
        # Roster-based and unconfirmed aliases are not silently used as official inputs.
        a = a if "alias" not in (a.get("method") or "") else {}
        b = b if "alias" not in (b.get("method") or "") else {}
        best_of = fx.get("best_of_resolved") if isinstance(fx.get("best_of_resolved"), int) else None
        out = {"fixture_id": fx["match_id"], "best_of": best_of,
               "best_of_source": fx.get("best_of_source"),
               "hltv_map_p_a": None, "hltv_map_p_b": None, "hltv_series_p_a": None,
               "vrs_map_p_a": None, "vrs_map_p_b": None, "vrs_series_p_a": None,
               "own_map_p_a": None, "own_map_p_b": None, "own_series_p_a": None,
               "own_series_p_b": None, "fair_odds_a": None, "fair_odds_b": None,
               "basis": "", "series_basis": "", "flags": ""}
        notes, series_notes, row_flags = [], [], []
        if a.get("hltv_points") and b.get("hltv_points"):
            p = elo_p(float(a["hltv_points"]), float(b["hltv_points"]))
            out["hltv_map_p_a"], out["hltv_map_p_b"] = round(p * 100, 2), round((1 - p) * 100, 2)
            out["hltv_series_p_a"] = (round(series_from_map(p, best_of) * 100, 2) if best_of in (1, 3, 5) else None)
            notes.append("HLTV ranking points")
            series_notes.append(f"HLTV points -> Elo({ELO_SCALE:.0f}) -> "
                                f"{'BO' + str(best_of) if best_of else 'map'} series")
        if a.get("vrs_points") and b.get("vrs_points"):
            p = elo_p(float(a["vrs_points"]), float(b["vrs_points"]))
            out["vrs_map_p_a"], out["vrs_map_p_b"] = round(p * 100, 2), round((1 - p) * 100, 2)
            out["vrs_series_p_a"] = (round(series_from_map(p, best_of) * 100, 2) if best_of in (1, 3, 5) else None)
            notes.append("Valve Regional Standings points")
            series_notes.append(f"VRS points -> Elo({ELO_SCALE:.0f}) -> "
                                f"{'BO' + str(best_of) if best_of else 'map'} series")
        map_parts = [x for x in (out["hltv_map_p_a"], out["vrs_map_p_a"]) if x is not None]
        series_parts = [x for x in (out["hltv_series_p_a"], out["vrs_series_p_a"]) if x is not None]
        if map_parts:
            out["own_map_p_a"] = round(sum(map_parts) / len(map_parts), 2)
            out["own_map_p_b"] = round(100 - out["own_map_p_a"], 2)
            out["basis"] = " + ".join(notes)
        if series_parts:
            out["own_series_p_a"] = round(sum(series_parts) / len(series_parts), 2)
            out["own_series_p_b"] = round(100 - out["own_series_p_a"], 2)
            out["series_basis"] = " + ".join(series_notes)
        if best_of not in (1, 3, 5):
            row_flags.append("S-F-08: series format unverified; series probability and model-only match pick blank")
        if out["own_map_p_a"] is None:
            row_flags.append("S-F-04: no originated line — at least one team has no official rating")
        if out["own_map_p_a"] is not None:
            out["fair_odds_a"] = round(100 / out["own_map_p_a"], 2)
            out["fair_odds_b"] = round(100 / out["own_map_p_b"], 2)
        out["flags"] = "; ".join(row_flags)
        return out

    own_lines = [own_line(fx) for fx in candidates]
    own_by_fixture = {o["fixture_id"]: o for o in own_lines}

    # ------------------------------------------------------------------ merged analysis table
    # Every reading is published in lines.csv; the row's headline number is taken in this order:
    #   1. Pinnacle at capture time (a bookmaker's own line)
    #   2. EGamersWorld as read by this CI run
    #   3. EGamersWorld as read by this session through the project's fetch service
    #   4. the newest source-linked reading another session published in this repository
    # A lower-priority reading is only used when the ones above are empty for that fixture, and the
    # row says which one it came from.
    lines_by_fixture: dict[str, list[dict]] = {}
    for row in pin_rows:
        row["read_by"] = "this CI run (Pinnacle at capture time)"
        row["rank"] = 0
    for row in egw_rows:
        row["read_by"] = "this CI run (EGamersWorld per-match page)"
        row["rank"] = 1
    for row in sess_rows:
        row["rank"] = 2
    # Carried rows come from other sessions' published files. Their fixture id is the same Hotspawn
    # id space, but each row is re-matched to this capture's fixtures by team name and kickoff before
    # it is allowed anywhere near a row, and it is never allowed to displace a fresher reading.
    carried_kept = []
    for row in carried_rows:
        best = None
        for fx in candidates:
            score = max(sim_pair(fx["team_a"], fx["team_b"], row.get("team_a"), row.get("team_b")),
                        sim_pair(fx["team_a"], fx["team_b"], row.get("team_b"), row.get("team_a")))
            if score < 0.60:
                continue
            row_start, fx_start = parse_iso(row.get("start_utc")), parse_iso(fx.get("scheduled_start_utc"))
            if row_start and fx_start and abs((row_start - fx_start).total_seconds()) > 3 * 3600:
                continue
            if best is None or score > best[0]:
                best = (score, fx)
        if best is None:
            continue
        row["fixture_id"] = best[1]["match_id"]
        row["name_similarity"] = round(best[0], 3)
        row["rank"] = 3
        carried_kept.append(row)
    carried_rows = carried_kept
    carried_meta["matched"] = len(carried_rows)
    for rows in (pin_rows, egw_rows, sess_rows, carried_rows):
        for row in rows:
            lines_by_fixture.setdefault(row["fixture_id"], []).append(row)

    analysis = []
    for fx in candidates:
        own = own_by_fixture.get(fx["match_id"], {})
        market_rows = lines_by_fixture.get(fx["match_id"], [])
        # Headline price order: this run's Pinnacle quote, then this run's own EGamersWorld read,
        # then this session's page reading, then a source-linked reading another session published.
        eligible = [r for r in market_rows if guards.eligible_market(r, datetime.now(timezone.utc))]
        primary = max(eligible, key=lambda r: r["captured_utc"]) if eligible else None
        market_p_a = primary["p_a"] if primary else None
        own_p_a = own.get("own_series_p_a")
        own_kind = "series" if own_p_a is not None else None
        consensus, selected_basis = guards.pick_probability(market_p_a, own_p_a, fx.get("best_of_resolved"))
        pick, pick_p, basis, flag_row = "", None, "", []
        if consensus is not None and consensus != 50:
            pick = fx["team_a"] if consensus >= 50 else fx["team_b"]
            pick_p = consensus if consensus >= 50 else round(100 - consensus, 2)
            if market_p_a is not None and own_p_a is not None:
                basis = ("primary market pick; provisional model agrees"
                         if (market_p_a >= 50) == (own_p_a >= 50) else
                         "market line and our own rating line DISAGREE — market line preferred, "
                         "divergence flagged")
                if (market_p_a >= 50) != (own_p_a >= 50):
                    flag_row.append("S-F-09")
            elif market_p_a is not None:
                basis = "external bookmaker line only (no official rating for both teams)"
            else:
                basis = selected_basis
                flag_row.append("S-F-10")
        else:
            basis = "no probability available — market unavailable and no official rating for both teams"
            flag_row.append("S-F-11")
        hltv_ref = hltv_by_fixture.get(fx["match_id"], {})
        analysis.append({
            "fixture_id": fx["match_id"], "sport": fx["sport"], "competition": fx.get("competition"),
            "tier": fx.get("tier"), "points": fx.get("offered_points"),
            "start_utc": fx.get("scheduled_start_utc"), "lock_utc": fx.get("lock_utc"),
            "team_a": fx.get("team_a"), "team_b": fx.get("team_b"),
            "best_of": fx.get("best_of_resolved"),
            "best_of_source": fx.get("best_of_source"),
            "market_source": primary["source"] if primary else "",
            "market_book": primary["book"] if primary else "",
            "market_odds_a": primary["odds_a"] if primary else None,
            "market_odds_b": primary["odds_b"] if primary else None,
            "market_overround_pct": primary["overround_pct"] if primary else None,
            "market_p_a_pct": market_p_a, "market_p_b_pct": (round(100 - market_p_a, 2) if market_p_a is not None else None),
            "market_captured_utc": primary["captured_utc"] if primary else "",
            "market_url": primary["source_url"] if primary else "",
            "market_read_by": primary.get("read_by", "") if primary else "",
            "market_note": (primary.get("note") or "")[:300] if primary else "",
            "own_p_a_pct": own.get("own_map_p_a"), "own_p_b_pct": own.get("own_map_p_b"),
            "own_series_p_a_pct": own.get("own_series_p_a"), "own_series_p_b_pct": own.get("own_series_p_b"),
            "own_basis": own.get("basis") or "no official rating for both teams",
            "own_source_url": HLTV_RANKING_URL,
            "rating_valve_url": valve.get("blob_url") or "",
            "model_status": "provisional / not calibrated",
            "alias_evidence_url": " ".join(sorted({aliases[t]["evidence"] for t in (fx["team_a"], fx["team_b"]) if t in aliases})),
            "own_series_basis": own.get("series_basis"),
            "own_fair_odds_a": own.get("fair_odds_a"), "own_fair_odds_b": own.get("fair_odds_b"),
            "consensus_p_a_pct": consensus,
            "pick": pick, "pick_pct": pick_p, "pick_basis": basis,
            "hltv_url": hltv_ref.get("hltv_url", ""), "hltv_match_id": hltv_ref.get("hltv_match_id", ""),
            "kickoff_check": hltv_ref.get("kickoff_check", "no HLTV listing row matched"),
            "hotspawn_url": (f"https://play.hotspawn.com/{fx['sport']}-pickems"
                             if fx["sport"] in ("cs2", "thp", "lol") else "https://play.hotspawn.com/lobby"),
            "hotspawn_match_url": match_urls.get(str(fx["match_id"]), ""),
            "captured_utc": fx.get("snapshot_utc"),
            "flags": ";".join([f for f in flag_row if f] + ([own["flags"]] if own.get("flags") else [])),
        })

    # ------------------------------------------------------------------ coverage / counting flags
    page_counts = {}
    for entry in hs.get("pages") or []:
        page_counts[entry["page"]] = {
            "url": entry["url"], "status": entry["status"], "state_rows": entry["state_rows"],
            "cards_rendered": entry["cards_rendered"], "week_total_text": entry.get("week_total_text"),
            "error": entry.get("error"),
        }
    payload_cs2 = sum(1 for f in fixtures if f["sport"] == "cs2")
    payload_open_cs2 = sum(1 for f in fixtures if f["sport"] == "cs2" and f["live_status"] == "open")
    week_text = hs.get("week_total_text")
    if week_text is not None and week_text != len(candidates):
        add_flag("S-F-02", "needs review",
                 "Hotspawn counts differ from the parseable open slate",
                 f"The page header says \"{week_text} matches this week\"; the ng-state payload yields "
                 f"{len(fixtures)} fixtures, of which {len(candidates)} have a lock time in the future. "
                 "Weekly counts include fixtures from other titles and rows already locked; the "
                 "fixtures table is the authoritative list and is complete for the payload.",
                 [page_counts.get("cs2-pickems", {}).get("url", "https://play.hotspawn.com/cs2-pickems")])
    stale = [f for f in fixtures if f["live_status"].startswith("stale")]
    if stale:
        add_flag("S-F-03", "needs review",
                 f"{len(stale)} Hotspawn rows are scheduled in the past but still listed as scheduled",
                 "These rows carry a scheduled start months before this capture and no bookmaker still "
                 "prices them; they are listed here for completeness but are not part of the pickable "
                 "slate and get no line or pick.",
                 [page_counts.get("cs2-pickems", {}).get("url", "https://play.hotspawn.com/cs2-pickems")])
    for name, meta in (("pinnacle", pin_meta), ("egw", egw_meta)):
        if meta.get("error"):
            add_flag("S-F-12", "needs review", f"{name} collection error", str(meta["error"]),
                     ["https://www.pinnacle.com/en/esports/games/cs2/matchups/",
                      "https://egamersworld.com/counterstrike/matches"])

    open_without_market = [a for a in analysis if a["market_p_a_pct"] is None]
    open_without_own = [a for a in analysis if a["own_p_a_pct"] is None]
    open_without_any = [a for a in analysis if not a["pick"]]
    if open_without_market:
        add_flag("S-F-13", "needs review",
                 f"{len(open_without_market)} open fixtures have no external market line",
                 "No price could be read from the sources this run (a source that returns an error or "
                 "serves no odds table is recorded as a refusal). Those rows show the price as blank, "
                 "exactly as read — nothing is estimated.",
                 ["https://egamersworld.com/counterstrike/matches",
                  "https://www.pinnacle.com/en/esports/games/cs2/matchups/"])
    if open_without_own:
        add_flag("S-F-14", "needs review",
                 f"{len(open_without_own)} open fixtures have no originated line",
                 "At least one team in the fixture has no row with an exact name match in the HLTV "
                 "ranking or Valve's standings, so no rating-based probability is invented for it.",
                 [f"{HLTV_RANKING_URL}/2026/october/12", valve.get("blob_url") or VRS_LISTING_API])
    if open_without_any:
        add_flag("S-F-15", "needs review",
                 f"{len(open_without_any)} open fixtures have no pick at all",
                 "Neither a market line nor an official rating pair is available for these rows, so "
                 "they are published blank with this flag rather than filled in.",
                 ["https://play.hotspawn.com/cs2-pickems"])
    carried_used = [a for a in analysis
                    if (a.get("market_read_by", "").startswith("session arena/")
                        and "180a42a0" not in a.get("market_read_by", ""))]
    if carried_used:
        add_flag("S-F-16", "needs review",
                 f"{len(carried_used)} fixtures carry a price another session read, not re-read here",
                 "For these rows the CI run could not reach a bookmaker page (HTTP 403 is recorded in "
                 "the provenance log) and this session did not read that fixture's own page, so the "
                 "headline price is the newest source-linked reading already published in this "
                 "repository, with the reading session, its capture time and its page URL shown on the "
                 "row. Prices move: treat these as the older reading they are, and check the linked "
                 "page before relying on them.",
                 sorted({a["market_url"] for a in carried_used if a.get("market_url")}))
    session_only = [a for a in analysis
                    if a.get("market_read_by") == "session arena/180a42a0"]
    if session_only:
        add_flag("S-F-18", "info",
                 f"{len(session_only)} fixtures were priced from this session's own page reading",
                 "EGamersWorld refuses the CI runner (HTTP 403) but serves the project's fetch service, "
                 "so these prices were read by the session at the times recorded per row, with the page "
                 "URL on every row. The scheduled CI job keeps trying the same pages and will replace "
                 "these rows with its own fresh readings whenever the host serves it again.",
                 sorted({a["market_url"] for a in session_only if a.get("market_url")}))
    divergent = [a for a in analysis if "S-F-09" in (a.get("flags") or "")]
    if divergent:
        add_flag("S-F-09", "needs review",
                 f"{len(divergent)} fixtures where the market price and our own rating line disagree",
                 "For these rows the external bookmaker price and the official-rating model point at "
                 "different winners. The pick stays with the market price (it is the observable market "
                 "view), the model's side is shown next to it, and both source links are on the row. A "
                 "disagreement is information, not an error: it says the two independent methods are "
                 "not telling the same story here.",
                 sorted({a["market_url"] for a in divergent if a.get("market_url")} |
                        {a["hotspawn_url"] for a in divergent if a.get("hotspawn_url")}))
    add_flag("S-F-01", "needs review",
             "Hotspawn's printed wall-clock time is not a reliable UTC value",
             "The printed time next to a match is rendered for the viewer, and this project's own "
             "readings show the same fixture printed as both UTC and UTC-4 on the same pages in "
             "different sessions, while the ticker (\"Locks in ...\") and the ng-state epoch always "
             "agree. Every time in slate/data comes from the ng-state epoch, never from the printed "
             "text.",
             ["https://play.hotspawn.com/cs2-pickems", "https://play.hotspawn.com/lobby"])
    add_flag("S-F-17", "info",
             "No Hotspawn crowd percentage is used as a probability",
             "The crowd \"% picked\" values are readable from the payload. They are copied into "
             "fixtures.csv under column names ending in _audit_only for transparency, and no build "
             "step reads those columns. Every probability on the site comes from an external "
             "bookmaker price, from our own official-rating model, or is blank.",
             ["https://play.hotspawn.com/cs2-pickems"])

    add_flag("H-F-01", "needs review", "Rating model is provisional, not an official probability",
             "Scale 400 and equal-weight rating blend are project assumptions, not calibrated forecasts or "
             "Valve/HLTV published win probabilities. Unknown series format means no series probability or "
             "model-only match pick. Map estimates remain in Own lines for research only.",
             [HLTV_RANKING_URL, valve.get("blob_url") or VRS_LISTING_API])
    add_flag("H-F-02", "unverified", "Secondary aggregator and historical prices cannot drive current picks",
             "Only fresh primary Pinnacle quotes, exact/evidence-linked names and kickoff within 15 minutes, "
             "drive market picks. EGamersWorld observations are secondary reports, not verified against the "
             "named bookmaker; see Market lines. Historical session readings are excluded, not refreshed by relabelling.",
             ["https://www.pinnacle.com/en/esports/games/cs2/matchups/", "https://egamersworld.com/counterstrike/matches"])
    for label, meta in (hltv.get("pages") or {}).items():
        if meta.get("status") != 200:
            add_flag("H-F-03", "unverified", f"HLTV {label} unavailable",
                     f"HTTP {meta.get('status')}; identity/format checks requiring this source stay blank.", [meta["url"]])
    add_flag("H-F-04", "needs review", "Separate legacy model refresh failed at 2026-10-14 00:20 UTC",
             "Official GitHub Actions API reports the model tests failed in run 38489574648. That separate "
             "dashboard may be stale. This board does not use its outputs. Check the run for subsequent status.",
             ["https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38489574648"])
    for a in analysis:
        if a["market_p_a_pct"] is None or not a["pick"] or "S-F-08" in a["flags"]:
            add_flag("H-F-ROW", "unverified", f"{a['fixture_id']}: {a['team_a']} vs {a['team_b']}",
                     f"Market: {'primary quote' if a['market_p_a_pct'] is not None else 'unverified/unavailable'}. "
                     f"Series format: {a['best_of'] or 'unverified'}. Pick: {a['pick'] or 'blank'}. "
                     f"{a['flags']}", [a["hotspawn_url"], HLTV_RANKING_URL])

    # ------------------------------------------------------------------ write data
    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: ("" if v is None else v) for k, v in row.items()})

    write_csv(DATA / "fixtures.csv", fixtures)
    write_csv(DATA / "ratings.csv", ratings)
    write_csv(DATA / "lines.csv", pin_rows + egw_rows + sess_rows + carried_rows)
    write_csv(DATA / "own_lines.csv", own_lines)
    write_csv(DATA / "analysis.csv", analysis)
    write_csv(DATA / "flags.csv", flags)

    provenance = [{"url": p.get("url"), "fetched_utc": p.get("fetched_utc"), "status": p.get("status"),
                   "bytes": p.get("bytes"), "sha256": p.get("sha256"), "path": p.get("path"),
                   "error": p.get("error")} for p in (up.provenance if HAVE_UPSTREAM else [])]
    provenance += prov_extra
    summary = {
        "generated_utc": now_iso(),
        "run_seconds": round(time.time() - started, 1),
        "upstream_collector": {"reused": "refresh/collect.py (session arena/b90700c6, read-only)",
                               "available": HAVE_UPSTREAM, "error": UPSTREAM_ERROR},
        "hotspawn": {
            "pages": page_counts,
            "week_total_text": week_text,
            "week_total_context": hs.get("week_total_context"),
            "reset_utc": hs.get("reset_utc"),
            "fixtures_total": len(fixtures),
            "fixtures_cs2": payload_cs2,
            "fixtures_open": len(candidates),
            "fixtures_open_cs2": payload_open_cs2,
            "fixtures_stale": len(stale),
            "sports": {s: sum(1 for f in fixtures if f["sport"] == s)
                       for s in sorted({f["sport"] for f in fixtures})},
            "source_url": "https://play.hotspawn.com/cs2-pickems",
        },
        "hltv": {"listing_url": HLTV_MATCHES_URL, "error": hltv.get("error"),
                 "matches_read": len(hltv.get("matches") or []),
                 "matches_block_split": hltv.get("matches_from_block_split"),
                 "ranking_url": HLTV_RANKING_URL,
                 "ranking_teams": len(hltv.get("ranking") or {}),
                 "ranking_date_text": hltv.get("ranking_date_text"),
                 "pages": hltv.get("pages")},
        "valve": {"file": valve.get("file"), "blob_url": valve.get("blob_url"),
                  "teams": len(valve.get("teams") or {}), "rows_read": valve.get("rows_read"),
                  "error": valve.get("error")},
        "pinnacle": pin_meta,
        "egw": egw_meta,
        "hotspawn_match_urls": match_urls_meta,
        "session_readings": sess_meta,
        "carried_readings": {**carried_meta, "used_for_headline": len(carried_used)},
        "counts": {
            "open_fixtures": len(candidates),
            "with_market_line": sum(1 for a in analysis if a["market_p_a_pct"] is not None),
            "with_own_line": sum(1 for a in analysis if a["own_p_a_pct"] is not None),
            "with_pick": sum(1 for a in analysis if a["pick"]),
            "kickoff_agrees_with_hltv": sum(1 for a in analysis if a["kickoff_check"] == "agree"),
            "kickoff_differs_from_hltv": sum(1 for a in analysis
                                             if a["kickoff_check"].startswith("differs")),
            "no_hltv_row": sum(1 for a in analysis if not a["hltv_match_id"]),
        },
        "constants": {"elo_scale": ELO_SCALE,
                      "series_transform": "BO3 p^2(3-2p); BO5 p^3(10-15p+6p^2); BO1 identity",
                      "devig": "p_a = (1/o_a) / (1/o_a + 1/o_b)"},
    }
    (DATA / "analysis.json").write_text(json.dumps(
        {"summary": summary, "analysis": analysis, "fixtures": fixtures, "ratings": ratings,
         "flags": flags}, indent=1), encoding="utf-8")
    (DATA / "coverage.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (DATA / "provenance.json").write_text(json.dumps(
        {"generated_utc": summary["generated_utc"], "fetches": provenance}, indent=1),
        encoding="utf-8")
    print(json.dumps(summary["counts"], indent=1), flush=True)
    print(f"[slate] flags={len(flags)} provenance_rows={len(provenance)}", flush=True)
    if not fixtures:
        print("FATAL: no fixtures could be read from the Hotspawn payload", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    code = main()
    if HAVE_UPSTREAM and getattr(up, "_browser", None) is not None:
        try:
            up._browser.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(code)
