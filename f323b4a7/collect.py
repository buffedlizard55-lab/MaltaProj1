#!/usr/bin/env python3
"""Live collector for the f323b4a7 board (session arena/f323b4a7).

Reads, with no credentials and no manual input:
  1. Hotspawn Play `/lobby`, `/cs2-pickems`, `/thp-pickems` - Angular TransferState
     (`<script id="ng-state">`) gives every CS2 fixture with exact UTC epochs, tier, points and the
     crowd pick share (ownership only).
  2. Pinnacle's public guest JSON for CS2 (whole-match moneyline, period 0, not alternate).
  3. Polymarket's gamma API, "counter strike 2" tag (match-winner prices).
  4. Valve's official Regional Standings (newest live/global file) via the GitHub API.
  5. HLTV's world ranking page.

Every source is optional: if one fails the last good value stored in the repository is reused and the
failure is recorded in data/collect_status.json, so a single refusal never breaks the build.
"""
from __future__ import annotations

import gzip
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
RAW = DATA / "raw"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) MaltaProj1-f323b4a7/1.0"}

HOTSPAWN_PAGES = ["https://play.hotspawn.com/lobby",
                  "https://play.hotspawn.com/cs2-pickems",
                  "https://play.hotspawn.com/thp-pickems"]
STATE = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
TIER_TEXT = re.compile(r"Tier\s*All tiers\s*\((\d+)\)", re.I)
WEEK_TEXT = re.compile(r"(\d{1,4})\s+matches this week", re.I)

PIN_MATCHUPS = "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups?withSpecials=false"
PIN_MARKETS = "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false"
PM_URL = ("https://gamma-api.polymarket.com/markets?closed=false&tag_id=100780"
          "&end_date_min={since}&limit=500&offset={offset}")
VRS_REPO = "ValveSoftware/counter-strike_regional_standings"
VRS_API = f"https://api.github.com/repos/{VRS_REPO}/contents/live"
HLTV_RANKING = "https://www.hltv.org/ranking/teams"


def log(msg):
    print(f"[collect {msg}]", flush=True)


def get(url, timeout=45):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url, timeout=45):
    return json.loads(get(url, timeout).decode("utf-8", "replace"))


# --------------------------------------------------------------------- Hotspawn
def walk_fixtures(node, out):
    if isinstance(node, dict):
        if "scheduled_start_time" in node and "participants0_name" in node:
            out.append(node)
        for v in node.values():
            walk_fixtures(v, out)
    elif isinstance(node, list):
        for i in node:
            walk_fixtures(i, out)


def find_week(node):
    if isinstance(node, dict):
        if "weekStartUtc" in node and "weekEndUtc" in node:
            return node
        for v in node.values():
            f = find_week(v)
            if f:
                return f
    elif isinstance(node, list):
        for i in node:
            f = find_week(i)
            if f:
                return f
    return None


def iso(ms):
    import datetime
    return datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def collect_hotspawn(status):
    fixtures, pages = [], []
    for url in HOTSPAWN_PAGES:
        try:
            body = get(url).decode("utf-8", "replace")
        except Exception as e:                                   # noqa: BLE001
            status["hotspawn"] = f"FAILED {type(e).__name__}: {e}"
            log(f"hotspawn {url} failed: {e}")
            continue
        RAW.mkdir(parents=True, exist_ok=True)
        name = url.rstrip("/").split("/")[-1]
        with gzip.open(RAW / f"hotspawn_state_{name}.json.gz", "wt") as fh:
            fh.write(body)
        m = STATE.search(body)
        if not m:
            continue
        try:
            state = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        rows = []
        walk_fixtures(state, rows)
        week = find_week(state)
        pages.append({"page": name, "url": url, "status": 200,
                      "read_utc": iso_now(), "bytes": len(body),
                      "sha256": __import__("hashlib").sha256(body.encode()).hexdigest(),
                      "week_text": (WEEK_TEXT.search(body) or [None, None])[1]
                      if WEEK_TEXT.search(body) else None,
                      "tier_total": int(TIER_TEXT.search(body).group(1)) if TIER_TEXT.search(body) else None,
                      "state_rows": len(rows), "week": week})
        for r in rows:
            fixtures.append({
                "match_id": str(r["id"]), "competition": r.get("competition_name"),
                "tier": str(r.get("tier") or "").upper(), "stage": r.get("stage"),
                "team_a": r.get("participants0_name"), "team_b": r.get("participants1_name"),
                "start_utc": iso(r["scheduled_start_time"]), "lock_utc": iso(r.get("lock_time")),
                "lock_offset_sec": r.get("lock_offset_sec"),
                "offered_points": r.get("offered_points"), "base_points": r.get("base_points"),
                "points_breakdown": r.get("points_breakdown"), "total_picks": r.get("total_picks"),
                "crowd_a_pct": r.get("participants0_picked_percent"),
                "crowd_b_pct": r.get("participants1_picked_percent"), "status": r.get("status"),
                "best_of": r.get("best_of"), "series_format": r.get("series_format"),
                "hotspawn_url": None, "source": f"Hotspawn TransferState {iso_now()}",
                "source_url": url})
    # de-duplicate (lobby and cs2-pickems carry the same rows)
    seen, uniq = set(), []
    for f in fixtures:
        if f["match_id"] in seen:
            continue
        seen.add(f["match_id"])
        uniq.append(f)
    status["hotspawn"] = f"ok {len(uniq)} fixtures from {len(pages)} pages"
    return uniq, pages


def iso_now():
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------- Pinnacle
def collect_pinnacle(status):
    try:
        matchups = get_json(PIN_MATCHUPS)
        markets = get_json(PIN_MARKETS)
    except Exception as e:                                   # noqa: BLE001
        status["pinnacle"] = f"FAILED {type(e).__name__}: {e}"
        return None, None
    with gzip.open(RAW / "pinnacle_matchups.json.gz", "wt") as fh:
        json.dump(matchups, fh)
    with gzip.open(RAW / "pinnacle_markets.json.gz", "wt") as fh:
        json.dump(markets, fh)
    status["pinnacle"] = f"ok {len(matchups)} matchups / {len(markets)} markets"
    return matchups, markets


# ------------------------------------------------------------------- Polymarket
def collect_polymarket(status):
    import datetime
    since = (datetime.datetime.now(datetime.timezone.utc)
             - datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = []
    try:
        for off in range(0, 1000, 500):
            batch = get_json(PM_URL.format(since=since, offset=off))
            if not batch:
                break
            out.extend(batch)
    except Exception as e:                                   # noqa: BLE001
        status["polymarket"] = f"FAILED {type(e).__name__}: {e}"
        return None
    with gzip.open(RAW / "polymarket_markets.json.gz", "wt") as fh:
        json.dump(out, fh)
    status["polymarket"] = f"ok {len(out)} markets"
    return out


# ------------------------------------------------------------------------- VRS
def collect_vrs(status):
    try:
        live = get_json(VRS_API)
        files = [f["name"] for f in live if f["name"].startswith("standings_global_")]
        files.sort()
        name = files[-1]
        year = name.split("_")[2]
        meta = get_json(f"https://api.github.com/repos/{VRS_REPO}/contents/live/{year}/{name}")
        import base64
        text = base64.b64decode(meta["content"]).decode("utf-8", "replace")
    except Exception as e:                                   # noqa: BLE001
        status["vrs"] = f"FAILED {type(e).__name__}: {e}"
        return None
    vrs = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            vrs[m.group(3).strip()] = {"standing": int(m.group(1)), "points": int(m.group(2)),
                                       "roster": m.group(4).strip(),
                                       "url": f"https://github.com/{VRS_REPO}/blob/"
                                              f"{meta['sha']}/live/{year}/{name}"}
    status["vrs"] = f"ok {len(vrs)} teams from {name}"
    return vrs


# ----------------------------------------------------------------------- HLTV
def collect_hltv(status):
    try:
        body = get(HLTV_RANKING, timeout=40).decode("utf-8", "replace")
    except Exception as e:                                   # noqa: BLE001
        status["hltv"] = f"FAILED {type(e).__name__}: {e}"
        return None
    hltv = {}
    for m in re.finditer(r'href="/team/(\d+)/([a-z0-9\-]+)"[^>]*>.*?</a>', body, re.S):
        hltv[m.group(2).replace("-", " ")] = {"team_url": f"https://www.hltv.org/team/{m.group(1)}/{m.group(2)}"}
    status["hltv"] = f"ok {len(hltv)} team links"
    return hltv


def main() -> int:
    status = {"started_utc": iso_now()}
    prev = json.load(open(DATA / "sources.json")) if (DATA / "sources.json").exists() else {}

    fixtures, pages = collect_hotspawn(status)
    if not fixtures:
        fixtures = prev.get("fixtures", [])
        log("hotspawn unavailable - reusing stored fixtures")
    pin = collect_pinnacle(status)
    pm = collect_polymarket(status)
    vrs = collect_vrs(status) or prev.get("vrs", {})
    hltv = collect_hltv(status) or prev.get("hltv", {})

    lines = {}
    if pin and pin[0] and pin[1]:
        by_id = {}
        for mu in pin[0]:
            parts = mu.get("participants") or []
            if len(parts) == 2:
                by_id[mu["id"]] = (parts[0].get("name"), parts[1].get("name"))
        for mk in pin[1]:
            if mk.get("type") != "moneyline" or mk.get("period") != 0 or mk.get("isAlternate"):
                continue
            pr = {p.get("designation"): p.get("price") for p in mk.get("prices", [])}
            if "home" in pr and "away" in pr:
                lines.setdefault("pinnacle_raw", []).append(
                    {"matchupId": mk["matchupId"], "home": pr["home"], "away": pr["away"],
                     "teams": by_id.get(mk["matchupId"]), "cutoff": mk.get("cutoffAt")})
    if pm:
        for m in pm:
            q = m.get("question") or ""
            mm = re.match(r"^Counter-Strike:\s*(?P<a>.+?)\s+vs\.?\s+(?P<b>.+?)\s*\((?P<f>BO\d)\)", q, re.I)
            if not mm:
                continue
            try:
                pa, pb = (float(x) for x in json.loads(m.get("outcomePrices") or "[]"))
            except Exception:                                   # noqa: BLE001
                continue
            lines.setdefault("polymarket_raw", []).append(
                {"a": mm.group("a"), "b": mm.group("b"), "format": mm.group("f"),
                 "price_a": pa, "price_b": pb, "slug": m.get("slug"),
                 "url": f"https://polymarket.com/event/{m.get('slug')}",
                 "end": m.get("endDate"), "updated": m.get("updatedAt")})

    out = dict(prev)
    out.update({
        "live_capture": {
            "read_utc": iso_now(), "url": HOTSPAWN_PAGES[0], "pages": pages,
            "week_text": (pages[0].get("week_text") if pages else None),
            "tier_text": f"All tiers ({pages[0].get('tier_total')})" if pages else None,
            "tier_counts": {}, "tournaments": {},
        },
        "fixtures": fixtures, "vrs": vrs, "hltv": hltv,
        "lines_raw": lines,
        "vrs_as_of": "see vrs[*].url",
    })
    json.dump(out, open(DATA / "sources.json", "w"), indent=1)
    status["finished_utc"] = iso_now()
    json.dump(status, open(DATA / "collect_status.json", "w"), indent=1)
    log(json.dumps(status, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
