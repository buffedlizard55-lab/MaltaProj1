#!/usr/bin/env python3
"""Network collection for the canonical CS2 briefing board (session arena/198cf31e).

Runs on GitHub Actions: the agent sandbox has no general egress to these hosts, so collection
happens in CI and every response is archived (gzip JSON/HTML under briefing/data/raw/) together
with its HTTP status, byte count, SHA-256 and capture time in briefing/data/capture.json.
The published pages are then rendered offline from those committed bytes by build.py, so every
number on the site re-derives from archived official responses.

What is read, with an honest identifiable User-Agent and no credentials / no bypass:

  1. Hotspawn pick'em pages (play.hotspawn.com /lobby, /cs2-pickems, /thp-pickems):
     Angular TransferState <script id="ng-state"> -> CS2 fixture identity, kickoff + lock
     epochs, tournament, tier, stage, permalink.
     Crowd pick percentages (participants*_picked_percent / total_picks) are dropped at parse
     time and never written to disk. They are NEVER a probability input.
  2. Pinnacle public guest API, sport 12 (esports): matchups + straight markets -> moneylines.
  3. bo3.gg public API (the JSON its own pages load): upcoming CS2 matches with series format
     (bo_type) and the bookmaker quote it relays (provider + bookmaker match URL).
  4. Polymarket Gamma API, series 10310 ("Counter Strike"): match-winner markets.
  5. Valve Regional Standings: the official ValveSoftware GitHub repo, newest live/2026 global
     markdown file.
  6. HLTV: world ranking and Valve-ranking pages (public HTML).

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
import urllib.request
from datetime import datetime, timezone
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

PM_EVENTS = "https://gamma-api.polymarket.com/events"
PM_SERIES_ID = "10310"                # /series?slug=counter-strike -> id 10310

BO3_MATCHES = "https://api.bo3.gg/api/v1/matches"

VALVE_API_DIR = ("https://api.github.com/repos/ValveSoftware/"
                 "counter-strike_regional_standings/contents/live/2026")
VALVE_RAW = ("https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/"
             "main/live/2026/")

HLTV_WORLD = "https://www.hltv.org/ranking/teams/"
HLTV_VALVE = "https://www.hltv.org/valve-ranking/teams/"


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
                exc.code,
                f" title={title.group(1).strip()[:60]!r}" if title else ""))
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
    if isinstance(payload, str):
        blob = payload.encode()
    else:
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode()
    path = RAW / f"{name}.json.gz"
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(blob)
    return hashlib.sha256(blob).hexdigest()


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
                    # keep the most complete row; record the page it came from
                    if prev is None or sum(bool(v) for v in row.values()) > sum(
                            bool(v) for v in prev.values()):
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
    return {"fixtures": out, "pages": pages,
            "count": len(out), "captured_utc": iso(now())}


# --------------------------------------------------------------------------- 2 Pinnacle
def collect_pinnacle() -> tuple[dict, dict]:
    m_rec = http_get(PIN_MATCHUPS, timeout=60)
    matchups = []
    if m_rec["body"]:
        try:
            matchups = json.loads(m_rec["body"].decode("utf-8", errors="replace"))
        except ValueError as exc:
            m_rec["error"] = (m_rec["error"] or "") + f" JSON: {exc}"[:150]
    k_rec = http_get(PIN_MARKETS, timeout=60)
    markets = []
    if k_rec["body"]:
        try:
            markets = json.loads(k_rec["body"].decode("utf-8", errors="replace"))
        except ValueError as exc:
            k_rec["error"] = (k_rec["error"] or "") + f" JSON: {exc}"[:150]

    # Archive only moneyline-relevant fields: the published board re-derives from these bytes.
    slim_m = []
    for m in matchups if isinstance(matchups, list) else []:
        if m.get("type") != "matchup":
            continue
        parts = m.get("participants") or []
        slim_m.append({
            "id": m.get("id"), "league": (m.get("league") or {}).get("name"),
            "startTime": m.get("startTime"), "type": m.get("type"),
            "status": m.get("status"),
            "participants": [{"name": p.get("name"), "alignment": p.get("alignment")}
                             for p in parts],
        })
    slim_k = []
    for k in markets if isinstance(markets, list) else []:
        if k.get("marketType") != "moneyline":
            continue
        slim_k.append({
            "matchupId": k.get("matchupId"), "type": k.get("type"),
            "marketType": k.get("marketType"), "period": k.get("period"),
            "status": k.get("status"), "isAlternate": k.get("isAlternate"),
            "prices": [{"participantId": p.get("participantId"), "decimal": p.get("decimal"),
                        "american": p.get("american"), "status": p.get("status")}
                       for p in (k.get("prices") or [])],
        })
    payload = {"matchups": slim_m, "moneylines": slim_k}
    log(f"  pinnacle: matchups status={m_rec['status']} ({len(slim_m)} matchups), "
        f"markets status={k_rec['status']} ({len(slim_k)} moneylines)")
    return payload, {"matchups": meta(m_rec), "markets": meta(k_rec)}


# --------------------------------------------------------------------------- 3 bo3.gg
def collect_bo3() -> tuple[dict, dict]:
    rows, page_recs, page_no = [], [], 1
    while page_no <= 4:
        url = (f"{BO3_MATCHES}?filter[matches.status][in]=upcoming"
               f"&filter[matches.discipline_id][eq]=1&with=teams,tournament"
               f"&page[number]={page_no}&page[size]=100")
        rec = http_get(url, timeout=60)
        data = None
        if rec["body"]:
            try:
                data = json.loads(rec["body"].decode("utf-8", errors="replace"))
            except ValueError as exc:
                rec["error"] = (rec["error"] or "") + f" JSON: {exc}"[:150]
        items = (data or {}).get("data") if isinstance(data, dict) else None
        page_recs.append({**meta(rec), "page": page_no, "rows": len(items or [])})
        if not items:
            break
        for it in items:
            attrs = it.get("attributes") or it
            teams = []
            for rel in ((it.get("relationships") or {}).get("teams") or {}).get("data") or []:
                teams.append(rel)
            rows.append({
                "id": attrs.get("id") or it.get("id"),
                "start_date": attrs.get("start_date"),
                "status": attrs.get("status"),
                "bo_type": attrs.get("bo_type"),
                "tournament": ((attrs.get("tournament") or {}).get("name")
                               if isinstance(attrs.get("tournament"), dict)
                               else attrs.get("tournament_name")),
                "team_ids": [t.get("id") for t in teams],
                "bet_updates": attrs.get("bet_updates"),
                "slug": attrs.get("slug"),
            })
        page_no += 1
    # team names come from the "included" array of the first page; re-fetch page 1 and keep it
    rec1 = http_get(f"{BO3_MATCHES}?filter[matches.status][in]=upcoming"
                    f"&filter[matches.discipline_id][eq]=1&with=teams,tournament"
                    f"&page[number]=1&page[size]=100", timeout=60)
    included = []
    if rec1["body"]:
        try:
            included = (json.loads(rec1["body"].decode("utf-8", errors="replace"))
                        or {}).get("included") or []
        except ValueError:
            included = []
    names = {}
    for inc in included:
        if (inc.get("type") or "").startswith("team"):
            names[str(inc.get("id"))] = ((inc.get("attributes") or {}).get("name")
                                         or (inc.get("attributes") or {}).get("slug"))
    for row in rows:
        row["team_names"] = [names.get(str(t), "") for t in (row.get("team_ids") or [])]
    log(f"  bo3.gg: {len(rows)} upcoming CS2 matches, {len(names)} team names resolved")
    return {"matches": rows, "team_names": names}, {"pages": page_recs}


# --------------------------------------------------------------------------- 4 Polymarket
def collect_polymarket() -> tuple[dict, dict]:
    url = f"{PM_EVENTS}?series_id={PM_SERIES_ID}&closed=false&limit=500&order=startTime"
    rec = http_get(url, timeout=60)
    events = []
    if rec["body"]:
        try:
            events = json.loads(rec["body"].decode("utf-8", errors="replace"))
        except ValueError as exc:
            rec["error"] = (rec["error"] or "") + f" JSON: {exc}"[:150]
    slim = []
    for ev in events if isinstance(events, list) else []:
        markets = []
        for mk in ev.get("markets") or []:
            if str(mk.get("marketSlug") or mk.get("slug") or "").lower() != "moneyline":
                continue
            outcomes, prices, bids, asks = [], [], [], []
            try:
                outs = json.loads(mk.get("outcomes") or "[]")
                prs = json.loads(mk.get("outcomePrices") or "[]")
            except ValueError:
                continue
            for i, o in enumerate(outs):
                outcomes.append(o)
                prices.append(float(prs[i]) if i < len(prs) else None)
            markets.append({"outcomes": outcomes, "prices": prices,
                            "bestBid": mk.get("bestBid"), "bestAsk": mk.get("bestAsk"),
                            "spread": mk.get("spread"), "volume": mk.get("volume"),
                            "liquidity": mk.get("liquidity"), "active": mk.get("active"),
                            "closed": mk.get("closed")})
        slim.append({
            "id": ev.get("id"), "slug": ev.get("slug"), "title": ev.get("title"),
            "startDate": ev.get("startDate") or ev.get("gameStartTime"),
            "gameStartTime": (ev.get("eventMetadata") or {}).get("gameStartTime"),
            "league": (ev.get("eventMetadata") or {}).get("league"),
            "pandascoreMatchId": (ev.get("eventMetadata") or {}).get("pandascoreMatchId"),
            "markets": markets,
        })
    log(f"  polymarket: status={rec['status']} {len(slim)} open CS2 series events")
    return {"events": slim}, meta(rec)


# --------------------------------------------------------------------------- 5 Valve VRS
VALVE_ROW = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*(?:\[details\]\(([^)]+)\))?\s*\|",
    re.M)


def collect_valve() -> tuple[dict, dict]:
    recs = {"dir": None, "file": None}
    d = http_get(VALVE_API_DIR, timeout=45)
    recs["dir"] = meta(d)
    newest = ""
    if d["body"]:
        try:
            entries = json.loads(d["body"].decode("utf-8", errors="replace"))
            names = [e["name"] for e in entries
                     if isinstance(e, dict) and re.match(r"standings_global_\d{4}_\d{2}_\d{2}\.md$",
                                                         e.get("name", ""))]
            newest = sorted(names)[-1] if names else ""
        except ValueError as exc:
            recs["dir"]["error"] = (recs["dir"]["error"] or "") + f" JSON: {exc}"[:150]
    if not newest:
        newest = "standings_global_2026_10_05.md"   # last file verified present on the official repo
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
    return {"file": newest, "as_of": date_m.group(1) if date_m else "", "rows": rows}, recs


# --------------------------------------------------------------------------- 6 HLTV
def collect_hltv() -> tuple[dict, dict]:
    out, recs = {}, {}
    targets = {
        "world_ranking": HLTV_WORLD,
        "valve_ranking": HLTV_VALVE,
    }
    for key, url in targets.items():
        rec = http_get(url, timeout=60, html=True)
        recs[key] = meta(rec)
        body = rec["body"].decode("utf-8", errors="replace") if rec["body"] else ""
        save_raw(f"hltv_{key}", body)
        out[key] = {"chars": len(body)}
        log(f"  hltv/{key}: status={rec['status']} {len(body)} chars")
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
        (DATA / "capture.json").write_text(json.dumps(capture, indent=1))
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
