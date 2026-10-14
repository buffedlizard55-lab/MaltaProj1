#!/usr/bin/env python3
"""Network collection for the secondary-market feed (session arena/a0bdf924).

Runs on GitHub Actions (the agent sandbox has no general internet access).  Reads, with an
honest identifiable User-Agent and no credentials:

  1. Hotspawn pick'em pages (/cs2-pickems, /lobby, /thp-pickems): Angular TransferState
     (<script id="ng-state">) -> CS2 fixture identity, kickoff and lock epochs, permalinks.
     Crowd pick percentages are dropped at parse time and never written.
  2. Polymarket Gamma API, series 10310 ("Counter Strike" daily match series): match-winner
     markets with prices, best bid/ask, spread, depth and volume.
  3. bo3.gg public API (the JSON its own pages load): upcoming CS2 matches with series format
     (bo_type) and the bookmaker quote it relays in ``bet_updates`` (provider + match URL).
  4. Reachability probes only (status + size, nothing parsed into the feed): OddsDigger, and
     the bookmaker match page bo3.gg links to, so we can say whether a direct check is possible.

Only the fields that the join uses are archived (gzip JSON under feeds/data/raw/), together with
the HTTP status, byte count and SHA-256 of each full response in feeds/data/capture.json, so the
published feed re-derives from committed bytes and the repository does not balloon hourly.
Exit status 2 = no Hotspawn fixture list could be read (the workflow then publishes nothing).
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
REPO = HERE.parent

UA = ("Mozilla/5.0 (compatible; MaltaProj1-feeds/1.0; "
      "+https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/feeds)")
HEADERS = {"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
           "Accept-Language": "en-US,en;q=0.9"}

HOTSPAWN_PAGES = [("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
                  ("lobby", "https://play.hotspawn.com/lobby"),
                  ("thp-pickems", "https://play.hotspawn.com/thp-pickems")]
STATE_RE = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)

PM_SERIES_ID = "10310"   # gamma-api.polymarket.com/series?slug=counter-strike -> id 10310
PM_EVENTS = "https://gamma-api.polymarket.com/events"
BO3_MATCHES = "https://api.bo3.gg/api/v1/matches"
PROBES = [("OddsDigger e-sports index", "https://oddsdigger.com/e-sports")]


def now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"[{iso(now())}] {msg}", flush=True)


def http_get(url: str, timeout: int = 40, retries: int = 2) -> dict:
    """GET with an honest UA. Retries only on network errors / 5xx / 429, never disguised."""
    rec = {"url": url, "status": None, "bytes": 0, "sha256": "", "error": None,
           "fetched_utc": None, "body": b""}
    for attempt in range(retries + 1):
        rec["fetched_utc"] = iso(now())
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                rec.update(status=resp.status, body=body, bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), error=None)
                return rec
        except urllib.error.HTTPError as exc:
            rec.update(status=exc.code, error=f"HTTPError {exc.code}")
            if exc.code not in (429, 500, 502, 503, 504):
                return rec
        except Exception as exc:  # noqa: BLE001 - recorded, never hidden
            rec.update(error=f"{type(exc).__name__}: {exc}"[:300])
        time.sleep(2 * (attempt + 1))
    return rec


def get_json(url: str, timeout: int = 40) -> tuple[object, dict]:
    rec = http_get(url, timeout=timeout)
    data = None
    if rec["body"]:
        try:
            data = json.loads(rec["body"].decode("utf-8", errors="replace"))
        except ValueError as exc:
            rec["error"] = (rec["error"] or "") + f" JSON: {exc}"[:200]
    return data, rec


def meta(rec: dict) -> dict:
    return {k: rec[k] for k in ("url", "status", "bytes", "sha256", "error", "fetched_utc")}


def save_raw(name: str, payload: object) -> str:
    RAW.mkdir(parents=True, exist_ok=True)
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    path = RAW / f"{name}.json.gz"
    # mtime=0 -> identical content gives identical bytes, so unchanged data makes no git diff
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(blob)
    return hashlib.sha256(blob).hexdigest()


# ----------------------------------------------------------------------------- 1 Hotspawn
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


# Field whitelist: identity, timing and format only.  participants*_picked_percent and
# total_picks (crowd data) are deliberately absent, so they can never reach the feed.
KEEP = ("id", "competition_id", "competition_name", "sport_alias", "status", "tier", "stage",
        "best_of", "series_format", "offered_points", "participants0_id", "participants0_name",
        "participants1_id", "participants1_name")


def collect_hotspawn() -> dict:
    fixtures: dict[str, dict] = {}
    links: dict[str, str] = {}
    pages = []
    for name, url in HOTSPAWN_PAGES:
        rec = http_get(url, timeout=45)
        page = meta(rec)
        page["page"] = name
        page["cs2_rows"] = 0
        html = rec["body"].decode("utf-8", errors="replace") if rec["body"] else ""
        m = STATE_RE.search(html)
        if html and not m:
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
                    fid = str(node.get("id") or "")
                    if not fid:
                        continue
                    row = {k: node.get(k) for k in KEEP}
                    row["start_utc"] = _ms(node.get("scheduled_start_time"))
                    row["lock_utc"] = _ms(node.get("lock_time"))
                    row["pages"] = [name]
                    row["source_url"] = url
                    row["captured_utc"] = rec["fetched_utc"]
                    page["cs2_rows"] += 1
                    if fid in fixtures:
                        if name not in fixtures[fid]["pages"]:
                            fixtures[fid]["pages"].append(name)
                    else:
                        fixtures[fid] = row
        pages.append(page)
        time.sleep(0.5)
    for fid, row in fixtures.items():
        row["hotspawn_match_url"] = links.get(fid, "")
    rows = sorted(fixtures.values(), key=lambda r: (r["start_utc"], r["id"]))
    return {"pages": pages, "fixtures": rows}


def hotspawn_fallback() -> dict | None:
    """If Hotspawn refuses this run, reuse the newest committed capture of another board,
    read-only and labelled as such (cs2/data/capture.json, session arena/a174d77f)."""
    path = REPO / "cs2" / "data" / "capture.json"
    try:
        cap = json.loads(path.read_text(encoding="utf-8"))
        rows = cap["sources"]["hotspawn"]["fixtures"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    out = []
    for r in rows:
        if str(r.get("sport") or "").lower() != "cs2":
            continue
        out.append({"id": str(r.get("match_id")), "competition_name": r.get("competition"),
                    "sport_alias": "cs2", "status": r.get("status"), "tier": r.get("tier"),
                    "stage": r.get("stage"), "best_of": r.get("best_of_payload"),
                    "series_format": None, "offered_points": r.get("offered_points"),
                    "participants0_name": r.get("team_a"), "participants1_name": r.get("team_b"),
                    "participants0_id": r.get("team_a_id"), "participants1_id": r.get("team_b_id"),
                    "start_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
                    "pages": r.get("pages") or [], "source_url": r.get("source_url"),
                    "captured_utc": r.get("captured_utc"),
                    "hotspawn_match_url": r.get("hotspawn_match_url") or ""})
    return {"fixtures": out, "generated_utc": cap.get("generated_utc"),
            "path": "cs2/data/capture.json"}


# ----------------------------------------------------------------------------- 2 Polymarket
PM_MARKET_KEEP = ("id", "question", "sportsMarketType", "groupItemTitle", "outcomes",
                  "outcomePrices", "bestBid", "bestAsk", "spread", "lastTradePrice",
                  "liquidityNum", "liquidity", "volumeNum", "volume", "closed", "active",
                  "acceptingOrders", "gameStartTime", "eventStartTime", "slug")


def _trim_pm_event(ev: dict) -> dict:
    markets = []
    for m in ev.get("markets") or []:
        if not isinstance(m, dict):
            continue
        q = str(m.get("question") or "")
        if m.get("sportsMarketType") == "moneyline" or (
                m.get("sportsMarketType") in (None, "") and not re.search(r"map\s*\d", q, re.I)):
            markets.append({k: m.get(k) for k in PM_MARKET_KEEP})
    md = ev.get("eventMetadata") or {}
    return {"id": ev.get("id"), "slug": ev.get("slug"), "title": ev.get("title"),
            "startTime": ev.get("startTime"), "endDate": ev.get("endDate"),
            "score": ev.get("score"), "live": ev.get("live"), "ended": ev.get("ended"),
            "closed": ev.get("closed"), "active": ev.get("active"),
            "eventMetadata": {k: md.get(k) for k in ("league", "leagueTier", "pandascoreMatchId",
                                                     "serie", "tournament")},
            "markets": markets}


def collect_polymarket() -> dict:
    out = {"status": "unavailable", "requests": [], "events": []}
    since = iso(now() - timedelta(hours=12))
    seen = set()
    for use_filter in (True, False):
        offset = 0
        while offset <= 3000:
            params = {"series_id": PM_SERIES_ID, "closed": "false", "limit": "100",
                      "offset": str(offset)}
            if use_filter:
                params["end_date_min"] = since
            url = PM_EVENTS + "?" + urllib.parse.urlencode(params)
            data, rec = get_json(url)
            out["requests"].append(meta(rec))
            if not isinstance(data, list):
                break
            for ev in data:
                if isinstance(ev, dict) and str(ev.get("id")) not in seen:
                    seen.add(str(ev.get("id")))
                    end = str(ev.get("endDate") or "")
                    if end and end < since:   # client-side guard when the filter is ignored
                        continue
                    out["events"].append(_trim_pm_event(ev))
            if len(data) < 100:
                break
            offset += 100
            time.sleep(0.3)
        if out["events"] or not use_filter:
            break
    ok = [r for r in out["requests"] if r["status"] == 200]
    out["status"] = "observed" if ok else "unavailable"
    log(f"polymarket: {len(out['events'])} open CS2 match events from {len(ok)} ok request(s)")
    return out


# ----------------------------------------------------------------------------- 3 bo3.gg
def _trim_bo3(m: dict) -> dict:
    def team(t):
        t = t or {}
        return {"id": t.get("id"), "name": t.get("name"), "slug": t.get("slug")}
    tour = m.get("tournament") or {}
    return {"id": m.get("id"), "slug": m.get("slug"), "status": m.get("status"),
            "bo_type": m.get("bo_type"), "start_date": m.get("start_date"), "tier": m.get("tier"),
            "team1_id": m.get("team1_id"), "team2_id": m.get("team2_id"),
            "team1": team(m.get("team1")), "team2": team(m.get("team2")),
            "tournament": {"id": tour.get("id"), "name": tour.get("name"),
                           "slug": tour.get("slug"), "tier": tour.get("tier")},
            "bet_updates": m.get("bet_updates")}


def collect_bo3() -> dict:
    out = {"status": "unavailable", "requests": [], "matches": [], "total": None}
    offset, limit = 0, 100
    while offset <= 2000:
        params = [("page[offset]", str(offset)), ("page[limit]", str(limit)),
                  ("sort", "start_date"), ("filter[matches.status][in]", "upcoming"),
                  ("filter[matches.discipline_id][eq]", "1"), ("with", "teams,tournament")]
        url = BO3_MATCHES + "?" + urllib.parse.urlencode(params)
        data, rec = get_json(url)
        out["requests"].append(meta(rec))
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            break
        out["total"] = (data.get("total") or {}).get("count")
        out["matches"].extend(_trim_bo3(m) for m in data["results"] if isinstance(m, dict))
        if len(data["results"]) < limit or (out["total"] and offset + limit >= out["total"]):
            break
        offset += limit
        time.sleep(0.3)
    ok = [r for r in out["requests"] if r["status"] == 200]
    out["status"] = "observed" if ok else "unavailable"
    quoted = sum(1 for m in out["matches"] if isinstance(m.get("bet_updates"), dict))
    log(f"bo3.gg: {len(out['matches'])} upcoming CS2 matches ({quoted} with a relayed quote) "
        f"from {len(ok)} ok request(s); API total={out['total']}")
    return out


# ----------------------------------------------------------------------------- 4 probes
def collect_probes(bo3: dict) -> list[dict]:
    rows = []
    targets = list(PROBES)
    for m in bo3.get("matches", []):
        bu = m.get("bet_updates") or {}
        if isinstance(bu, dict) and bu.get("path"):
            targets.append((f"bookmaker page relayed by bo3.gg ({bu.get('provider')})", bu["path"]))
            break
    for label, url in targets:
        rec = http_get(url, timeout=25, retries=0)
        head = rec["body"][:160].decode("utf-8", errors="replace") if rec["body"] else ""
        rows.append({"source": label, **meta(rec), "head": head})
    return rows


def main() -> int:
    started = iso(now())
    DATA.mkdir(parents=True, exist_ok=True)
    hs = collect_hotspawn()
    fallback = None
    if not hs["fixtures"]:
        fallback = hotspawn_fallback()
        if not fallback or not fallback["fixtures"]:
            log("hotspawn: no fixture list from the site or the fallback -> nothing published")
            (DATA / "collect_failed.json").write_text(json.dumps(
                {"utc": iso(now()), "pages": hs["pages"]}, indent=1), encoding="utf-8")
            return 2
        log(f"hotspawn: site unreadable this run; using {fallback['path']} "
            f"(generated {fallback['generated_utc']}), labelled as fallback")
    fixtures = hs["fixtures"] or fallback["fixtures"]
    pm = collect_polymarket()
    bo3 = collect_bo3()
    probes = collect_probes(bo3)
    capture = {
        "schema": 1, "session": "arena/a0bdf924", "started_utc": started,
        "generated_utc": iso(now()), "user_agent": UA,
        "hotspawn": {"pages": hs["pages"], "cs2_fixtures": len(fixtures),
                     "fallback": ({"path": fallback["path"],
                                   "generated_utc": fallback["generated_utc"]} if fallback else None),
                     "raw_sha256": save_raw("hotspawn_fixtures", fixtures)},
        "polymarket": {"status": pm["status"], "series_id": PM_SERIES_ID,
                       "requests": pm["requests"], "events": len(pm["events"]),
                       "raw_sha256": save_raw("polymarket_events", pm["events"])},
        "bo3": {"status": bo3["status"], "requests": bo3["requests"], "api_total": bo3["total"],
                "matches": len(bo3["matches"]),
                "raw_sha256": save_raw("bo3_matches", bo3["matches"])},
        "probes": probes,
    }
    (DATA / "capture.json").write_text(json.dumps(capture, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    try:
        (DATA / "collect_failed.json").unlink()
    except OSError:
        pass
    log(f"capture written: {len(fixtures)} CS2 fixtures, {len(pm['events'])} Polymarket events, "
        f"{len(bo3['matches'])} bo3.gg matches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
