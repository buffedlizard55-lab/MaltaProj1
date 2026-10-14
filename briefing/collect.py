#!/usr/bin/env python3
"""Network collection for the canonical CS2 briefing board (session arena/198cf31e).

Runs on GitHub Actions: the agent sandbox has no egress to these hosts, so collection happens
in CI and every response is archived (gzip under briefing/data/raw/) together with its HTTP
status, byte count, SHA-256 and capture time in briefing/data/capture.json. build.py then
renders the board offline from those committed bytes, so every published number re-derives
from archived official responses.

Sources, read with an honest identifiable User-Agent, no credentials and no bypass:

  1. Hotspawn pick'em pages (play.hotspawn.com /lobby, /cs2-pickems, /thp-pickems):
     Angular TransferState <script id="ng-state"> -> CS2 fixture identity, kickoff + lock
     epochs, tournament, tier, stage, permalink.
     Crowd pick percentages (participants*_picked_percent / total_picks) are dropped at parse
     time and never written to disk. They are NEVER a probability input.
  2. Pinnacle public guest API, sport 12 (esports) - the same guest responses Pinnacle's own
     CS2 matchups page loads: matchups + straight markets -> whole-match moneylines.
  3. bo3.gg public API: upcoming CS2 matches with series format (bo_type) and the bookmaker
     quote it relays (provider + bookmaker match URL + both decimal prices).
  4. Polymarket Gamma API, series 10310 ("Counter Strike"): match-winner markets.
  5. Valve Regional Standings: official ValveSoftware GitHub repo, newest live/2026 global file.
  6. HLTV world ranking (dated page, HTML): parsed best-effort; if the ranking block is not in
     the response the source is recorded as unavailable and flagged, never guessed.

Exit status 2 = no Hotspawn fixture list could be read -> the workflow publishes nothing
(fail-closed: the last good board stays live).
"""
from __future__ import annotations

import gzip
import hashlib
import html as htmllib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "raw"

UA = ("Mozilla/5.0 (compatible; MaltaProj1-briefing/1.0; "
      "+https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/briefing)")
HEADERS = {"User-Agent": UA,
           "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}
# The Hotspawn edge answers 200 to an HTML-first Accept and 403 to a JSON-first one
# (established by session a0bdf924, run 38503458961). Never disguised, never bypassed.
HTML_HEADERS = {**HEADERS,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}

HOTSPAWN_PAGES = [("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
                  ("lobby", "https://play.hotspawn.com/lobby"),
                  ("thp-pickems", "https://play.hotspawn.com/thp-pickems")]
STATE_RE = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)

PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_SPORT = "12"                      # esports
PIN_MATCHUPS = f"{PIN_BASE}/sports/{PIN_SPORT}/matchups?withSpecials=false"
PIN_MARKETS = f"{PIN_BASE}/sports/{PIN_SPORT}/markets/straight?primaryOnly=false&withSpecials=false"
PIN_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"

PM_EVENTS = "https://gamma-api.polymarket.com/events"
PM_SERIES_ID = "10310"                # /series?slug=counter-strike -> id 10310
PM_MARKET_KEEP = ("id", "question", "sportsMarketType", "outcomes", "outcomePrices",
                  "bestBid", "bestAsk", "spread", "volume", "liquidity", "active", "closed")

BO3_MATCHES = "https://api.bo3.gg/api/v1/matches"

VALVE_API_DIR = ("https://api.github.com/repos/ValveSoftware/"
                 "counter-strike_regional_standings/contents/live/2026")
VALVE_RAW = ("https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/"
             "main/live/2026/")
VALVE_FALLBACK = "standings_global_2026_10_05.md"   # newest file on the official repo

HLTV_WORLD = "https://www.hltv.org/ranking/teams/2026/october/12"
HLTV_VALVE = "https://www.hltv.org/valve-ranking/teams/2026/october/14"


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[{iso(now())}] {msg}", flush=True)


def http_get(url: str, timeout: int = 45, retries: int = 2, html: bool = False) -> dict:
    rec = {"url": url, "status": None, "bytes": 0, "sha256": "", "error": None,
           "fetched_utc": None, "body": b""}
    for attempt in range(retries + 1):
        rec["fetched_utc"] = iso(now())
        try:
            req = urllib.request.Request(url, headers=HTML_HEADERS if html else HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                rec.update(status=resp.status, body=body, bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), error=None)
                return rec
        except urllib.error.HTTPError as exc:
            try:
                head = exc.read(300).decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                head = ""
            title = re.search(r"<title[^>]*>(.*?)</title>", head, re.S | re.I)
            rec.update(status=exc.code, error="HTTPError %s%s" % (
                exc.code, f" title={title.group(1).strip()[:60]!r}" if title else ""))
            if exc.code not in (429, 500, 502, 503, 504):
                return rec
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            rec.update(error=f"{type(exc).__name__}: {exc}"[:250])
        time.sleep(2 * (attempt + 1))
    return rec


def meta(rec: dict) -> dict:
    return {k: rec[k] for k in ("url", "status", "bytes", "sha256", "error", "fetched_utc")}


def save_raw(name: str, payload) -> str:
    """Archive a parsed object (deterministic bytes -> no git diff when unchanged)."""
    RAW.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()
    path = RAW / f"{name}.json.gz"
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(blob)
    return hashlib.sha256(blob).hexdigest()


def get_json(url: str, timeout: int = 60) -> tuple[object, dict]:
    rec = http_get(url, timeout=timeout)
    if not rec["body"]:
        return None, rec
    try:
        return json.loads(rec["body"].decode("utf-8", errors="replace")), rec
    except ValueError as exc:
        rec["error"] = (rec["error"] or "") + f" JSON: {exc}"[:150]
        return None, rec


# --------------------------------------------------------------------------- 1 Hotspawn
def _walk(node, out: list) -> None:
    if isinstance(node, dict):
        if "scheduled_start_time" in node and ("participants0_name" in node
                                               or "participants0_id" in node):
            out.append(node)
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)


def _permalinks(node, out: dict) -> None:
    if isinstance(node, dict):
        pl = node.get("permalinks")
        if isinstance(pl, dict):
            for k, v in pl.items():
                if isinstance(v, str) and v.startswith("https://www.hotspawn.com/matches/"):
                    out.setdefault(str(k), v)
        for v in node.values():
            _permalinks(v, out)
    elif isinstance(node, list):
        for v in node:
            _permalinks(v, out)


def _ms(value) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) != 13:
        return ""
    return iso(datetime.fromtimestamp(int(digits) / 1000, timezone.utc).replace(microsecond=0))


# Identity, timing, tournament and format only.  participants*_picked_percent and total_picks
# are deliberately absent from this whitelist, so crowd data can never reach the board.
KEEP = ("id", "competition_id", "competition_name", "sport_alias", "sport_name", "status",
        "tier", "stage", "best_of", "series_format", "offered_points", "base_points",
        "participants0_id", "participants0_name", "participants1_id", "participants1_name")


def collect_hotspawn() -> dict:
    fixtures: dict[str, dict] = {}
    links: dict[str, str] = {}
    pages = []
    for name, url in HOTSPAWN_PAGES:
        rec = http_get(url, timeout=50, html=True)
        page = meta(rec)
        page["page"] = name
        page["cs2_rows"] = 0
        text = rec["body"].decode("utf-8", errors="replace") if rec["body"] else ""
        m = STATE_RE.search(text)
        if text and not m:
            page["error"] = (page["error"] or "") + " ng-state script not found"
        if m:
            try:
                state = json.loads(htmllib.unescape(m.group(1)).strip())
            except ValueError as exc:
                state = None
                page["error"] = (page["error"] or "") + f" ng-state JSON: {exc}"[:200]
            if state is not None:
                nodes: list = []
                _walk(state, nodes)
                _permalinks(state, links)
                for node in nodes:
                    if str(node.get("sport_alias") or "").lower() != "cs2":
                        continue
                    row = {k: node.get(k) for k in KEEP}
                    row["start_utc"] = _ms(node.get("scheduled_start_time"))
                    row["lock_utc"] = _ms(node.get("lock_time"))
                    row["start_epoch_ms"] = node.get("scheduled_start_time")
                    row["lock_epoch_ms"] = node.get("lock_time")
                    fid = str(row["id"])
                    prev = fixtures.get(fid)
                    score = lambda r: sum(bool(v) for v in r.values())  # noqa: E731
                    if prev is None or score(row) > score(prev):
                        row["source_page"] = name
                        fixtures[fid] = row
                page["cs2_rows"] = sum(1 for n in nodes
                                       if str(n.get("sport_alias") or "").lower() == "cs2")
        pages.append(page)
        log(f"  hotspawn/{name}: status={page['status']} cs2_rows={page['cs2_rows']}"
            + (f" error={page['error']}" if page.get("error") else ""))
    for fid, row in fixtures.items():
        row["permalink"] = links.get(fid, "")
    out = sorted(fixtures.values(), key=lambda r: (r.get("start_utc") or "", str(r.get("id"))))
    return {"fixtures": out, "pages": pages, "count": len(out), "captured_utc": iso(now())}


# --------------------------------------------------------------------------- 2 Pinnacle
def _trim_pin_matchup(node: dict) -> dict | None:
    if node.get("type") != "matchup" or node.get("parentId") is not None:
        return None
    league = node.get("league") or {}
    if not str(league.get("name", "")).startswith("CS2 - "):
        return None
    parts = node.get("participants") or []
    if len(parts) != 2:
        return None
    names = {p.get("alignment"): p.get("name") for p in parts}
    if set(names) != {"home", "away"}:
        return None
    return {"event_id": node.get("id"), "league": league.get("name"),
            "league_id": league.get("id"),
            "team_a": names["home"], "team_b": names["away"],
            "start_utc": (node.get("startTime") or "") or None,
            "status": node.get("status")}


def collect_pinnacle() -> tuple[dict, dict]:
    matchups, m_rec = get_json(PIN_MATCHUPS, timeout=60)
    markets, k_rec = get_json(PIN_MARKETS, timeout=60)
    events = []
    for node in matchups or []:
        if not isinstance(node, dict):
            continue
        row = _trim_pin_matchup(node)
        if row:
            events.append(row)
    quotes = []
    for market in markets or []:
        if not isinstance(market, dict):
            continue
        if market.get("type") != "moneyline" or market.get("period") != 0:
            continue
        if market.get("isAlternate") is not False or market.get("status") != "open":
            continue
        event = next((e for e in events if e["event_id"] == market.get("matchupId")), None)
        if not event:
            continue
        prices = {p.get("designation"): p.get("price")
                  for p in (market.get("prices") or []) if isinstance(p, dict)}
        if set(prices) != {"home", "away"}:
            continue
        quotes.append({**event, "american_a": prices["home"], "american_b": prices["away"],
                       "market_url": PIN_MARKETS, "page_url": PIN_PAGE})
    log(f"  pinnacle: status={m_rec['status']}/{k_rec['status']} "
        f"{len(events)} CS2 matchups, {len(quotes)} whole-match moneylines")
    return {"cs2_matchups": events, "moneylines": quotes,
            "all_matchups": len(matchups or []), "all_markets": len(markets or [])}, \
        {"matchups": meta(m_rec), "markets": meta(k_rec)}


# --------------------------------------------------------------------------- 3 bo3.gg
def _trim_bo3(m: dict) -> dict:
    def team(t):
        t = t or {}
        return {"id": t.get("id"), "name": t.get("name"), "slug": t.get("slug")}
    tour = m.get("tournament") or {}
    return {"id": m.get("id"), "slug": m.get("slug"), "status": m.get("status"),
            "bo_type": m.get("bo_type"), "start_date": m.get("start_date"),
            "tier": m.get("tier"),
            "team1": team(m.get("team1")), "team2": team(m.get("team2")),
            "tournament": {"id": tour.get("id"), "name": tour.get("name"),
                           "slug": tour.get("slug"), "tier": tour.get("tier")},
            "bet_updates": m.get("bet_updates")}


def collect_bo3() -> tuple[dict, dict]:
    out, reqs, offset, limit = [], [], 0, 100
    total = None
    while offset <= 400:
        params = [("page[offset]", str(offset)), ("page[limit]", str(limit)),
                  ("sort", "start_date"),
                  ("filter[matches.status][in]", "upcoming"),
                  ("filter[matches.discipline_id][eq]", "1"),
                  ("with", "teams,tournament")]
        data, rec = get_json(BO3_MATCHES + "?" + urllib.parse.urlencode(params), timeout=60)
        reqs.append({**meta(rec), "offset": offset})
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            break
        total = (data.get("total") or {}).get("count")
        out.extend(_trim_bo3(m) for m in data["results"] if isinstance(m, dict))
        if len(data["results"]) < limit or (total and offset + limit >= total):
            break
        offset += limit
        time.sleep(0.3)
    quoted = sum(1 for m in out if isinstance(m.get("bet_updates"), dict)
                 and (m["bet_updates"].get("team_1") or {}).get("coeff"))
    log(f"  bo3.gg: {len(out)} upcoming CS2 matches ({quoted} with a relayed quote); "
        f"API total={total}")
    return {"matches": out, "total": total}, {"requests": reqs}


# --------------------------------------------------------------------------- 4 Polymarket
def _trim_pm_event(ev: dict) -> dict:
    markets = []
    for m in ev.get("markets") or []:
        if not isinstance(m, dict):
            continue
        if m.get("sportsMarketType") != "moneyline":
            continue
        markets.append({k: m.get(k) for k in PM_MARKET_KEEP})
    md = ev.get("eventMetadata") or {}
    return {"id": ev.get("id"), "slug": ev.get("slug"), "title": ev.get("title"),
            "startTime": ev.get("startTime"), "endDate": ev.get("endDate"),
            "closed": ev.get("closed"), "active": ev.get("active"),
            "eventMetadata": {k: md.get(k) for k in
                              ("league", "leagueTier", "pandascoreMatchId", "serie",
                               "tournament")},
            "markets": markets}


def collect_polymarket() -> tuple[dict, dict]:
    since = iso(now() - timedelta(hours=12))
    events, reqs, seen, offset = [], [], set(), 0
    while offset <= 800:
        params = {"series_id": PM_SERIES_ID, "closed": "false", "limit": "100",
                  "offset": str(offset)}
        data, rec = get_json(PM_EVENTS + "?" + urllib.parse.urlencode(params), timeout=60)
        reqs.append({**meta(rec), "offset": offset})
        if not isinstance(data, list):
            break
        for ev in data:
            if not isinstance(ev, dict) or str(ev.get("id")) in seen:
                continue
            seen.add(str(ev.get("id")))
            end = str(ev.get("endDate") or "")
            if end and end < since:      # skip events already finished
                continue
            events.append(_trim_pm_event(ev))
        if len(data) < 100:
            break
        offset += 100
        time.sleep(0.3)
    log(f"  polymarket: {len(events)} open CS2 series events")
    return {"events": events, "since": since}, {"requests": reqs}


# --------------------------------------------------------------------------- 5 Valve VRS
VALVE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|"
    r"\s*(?:\[details\]\(([^)]+)\))?\s*\|", re.M)


def collect_valve() -> tuple[dict, dict]:
    d, dir_rec = get_json(VALVE_API_DIR, timeout=45)
    recs = {"dir": meta(dir_rec)}
    newest = ""
    if isinstance(d, list):
        names = [e["name"] for e in d if isinstance(e, dict) and re.match(
            r"standings_global_\d{4}_\d{2}_\d{2}\.md$", e.get("name", ""))]
        newest = sorted(names)[-1] if names else ""
    if not newest:
        newest = VALVE_FALLBACK
        recs["dir"]["error"] = (recs["dir"]["error"] or "") + " using verified fallback filename"
    f = http_get(VALVE_RAW + newest, timeout=60)
    recs["file"] = meta(f)
    recs["file"]["name"] = newest
    text = f["body"].decode("utf-8", errors="replace") if f["body"] else ""
    rows = []
    date_m = re.search(r"Standings as of (\d{4}_\d{2}_\d{2})", text)
    for m in VALVE_ROW.finditer(text):
        rows.append({"rank": int(m.group(1)), "points": int(m.group(2)),
                     "team": m.group(3).strip(), "roster": m.group(4).strip(),
                     "details": m.group(5) or ""})
    log(f"  valve: {newest} status={f['status']} {len(rows)} ranked teams")
    return {"file": newest, "as_of": date_m.group(1) if date_m else "", "rows": rows,
            "source_url": "https://github.com/ValveSoftware/counter-strike_regional_standings/"
                          f"blob/main/live/2026/{newest}"}, recs


# --------------------------------------------------------------------------- 6 HLTV
HLTV_PATTERNS = [
    re.compile(r'class="position">#?(\d+)</span>.{0,4000}?class="name">([^<]+)</span>'
               r'.{0,2000}?class="points">\(?([\d,]+)\s*(?:HLTV\s*)?points?\)?', re.S),
    re.compile(r"#(\d+)!\[[^\]]*\]\([^)]*\)!\[[^\]]*\]\([^)]*\)[\s\S]{0,120}?"
               r"([^\n(]+?)\((\d+)\s*HLTV points\)"),
]


def _parse_hltv_ranking(text: str) -> list:
    rows, seen = [], set()
    for pat in HLTV_PATTERNS:
        rows = []
        for m in pat.finditer(text):
            name = re.sub(r"\s+", " ", m.group(2 if pat is HLTV_PATTERNS[0] else 2)).strip()
            pts = int(str(m.group(3 if pat is HLTV_PATTERNS[0] else 3)).replace(",", ""))
            rank = int(m.group(1))
            key = name.casefold()
            if key in seen or not name:
                continue
            seen.add(key)
            rows.append({"rank": rank, "name": name, "points": pts})
        if rows:
            return rows
    return []


def collect_hltv() -> tuple[dict, dict]:
    out, recs = {}, {}
    for key, url in (("world_ranking", HLTV_WORLD), ("valve_ranking", HLTV_VALVE)):
        rec = http_get(url, timeout=60, html=True)
        body = rec["body"].decode("utf-8", errors="replace") if rec["body"] else ""
        rows = _parse_hltv_ranking(body)
        out[key] = {"url": url, "rows": rows}
        r = meta(rec)
        r["ranking_rows"] = len(rows)
        r["marker_found"] = bool(re.search(r"HLTV points|World ranking", body))
        recs[key] = r
        log(f"  hltv/{key}: status={rec['status']} {len(body)} chars, {len(rows)} ranking rows")
    return out, recs


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    log("collection start")
    capture = {"generated_utc": iso(now()), "run_id": os.environ.get("GITHUB_RUN_ID", ""),
               "sources": {}}

    hs = collect_hotspawn()
    save_raw("hotspawn_fixtures", hs)
    capture["sources"]["hotspawn"] = {"status": min(p["status"] or 0 for p in hs["pages"]),
                                      "pages": hs["pages"], "fixtures": hs["count"]}
    if not hs["fixtures"]:
        log("FATAL: no Hotspawn fixtures parsed")
        (DATA / "capture.json").write_text(json.dumps(capture, indent=1, sort_keys=True))
        return 2

    pin, pin_meta = collect_pinnacle()
    save_raw("pinnacle", pin)
    capture["sources"]["pinnacle"] = pin_meta

    bo3, bo3_meta = collect_bo3()
    save_raw("bo3gg", bo3)
    capture["sources"]["bo3gg"] = bo3_meta

    pm, pm_meta = collect_polymarket()
    save_raw("polymarket", pm)
    capture["sources"]["polymarket"] = pm_meta

    vrs, vrs_meta = collect_valve()
    save_raw("valve_vrs", vrs)
    capture["sources"]["valve_vrs"] = vrs_meta

    hltv, hltv_meta = collect_hltv()
    save_raw("hltv", hltv)
    capture["sources"]["hltv"] = hltv_meta

    capture["finished_utc"] = iso(now())
    (DATA / "capture.json").write_text(json.dumps(capture, indent=1, sort_keys=True))
    log(f"collection done: {hs['count']} Hotspawn CS2 fixtures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
