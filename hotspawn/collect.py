#!/usr/bin/env python3
"""Collect every input of the every-match board from public sources (session arena/22be6967).

Sources (all public, no keys):

1. Hotspawn Play — ``/lobby``, ``/cs2-pickems``, ``/thp-pickems``.  Each page is server-side
   rendered by Angular and embeds its data in ``<script id="ng-state">`` (TransferState).  That
   JSON carries, per fixture: id, competition, tier, stage, ``scheduled_start_time`` and
   ``lock_time`` (epoch ms), points breakdown, participants, and the crowd pick share
   (``participants*_picked_percent``, ``total_picks``).  The crowd share is stored as
   ``crowd_*_ownership`` and is only ever read by the strategy layer, never by a probability.
2. Pinnacle — the public guest JSON that pinnacle.com's own CS2 page loads
   (``guest.api.arcadia.pinnacle.com/0.1/sports/12/{matchups,markets/straight}``): whole-match
   moneyline only (period 0, not alternate, open).
3. Polymarket — ``gamma-api.polymarket.com/markets`` filtered to the "counter strike 2" tag
   (id 100780) and to markets that end after yesterday; only "Match Winner" markets are kept.
   A prediction market, labelled as such everywhere.
4. Valve Regional Standings — the newest ``live/<year>/standings_global_*.md`` from
   ``ValveSoftware/counter-strike_regional_standings`` (local clone via ``VRS_REPO_DIR`` in CI,
   otherwise the GitHub API + raw file).  Official points + roster per team; the per-team
   details tables give how many rated matches the current five has played together.
5. HLTV world ranking — ``www.hltv.org/ranking/teams`` (rank, points, five nicknames).  HLTV
   often refuses automated clients; a refusal is recorded and the previous good read is reused
   only if it is younger than 9 days (HLTV publishes weekly).

Usage:  python3 hotspawn/collect.py            (live)
        HOTSPAWN_OFFLINE_DIR=cs2/data/raw python3 hotspawn/collect.py   (offline test fixtures)
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys
from datetime import timedelta
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, PROVENANCE, SESSION, american_to_decimal, ensure_dirs, get_json,  # noqa: E402
                    http_get, iso, ms_to_iso, now_iso, now_utc, parse_iso, read_json, save_raw,
                    write_json)

CAPTURE = DATA / "capture.json"
HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
]
STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)
MATCH_LINK = re.compile(r'https://www\.hotspawn\.com/(?:matches/[a-z0-9\-]+?-|\?fixtures=[a-z0-9\-]*?-)(\d{6,8})\b', re.I)
WEEK_TEXT = re.compile(r"(\d{1,4})\s+matches this week", re.I)
TIER_TEXT = re.compile(r"Tier\s*All tiers \((\d+)\)", re.I)

PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_MATCHUPS = f"{PIN_BASE}/sports/12/matchups?withSpecials=false"
PIN_MARKETS = f"{PIN_BASE}/sports/12/markets/straight?primaryOnly=false&withSpecials=false"
PIN_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"

PM_TAG = 100780  # Polymarket tag "counter strike 2"
PM_URL = "https://gamma-api.polymarket.com/markets?closed=false&tag_id={tag}&end_date_min={since}&limit=500&offset={offset}"
PM_QUESTION = re.compile(r"^Counter-Strike:\s*(?P<a>.+?)\s+vs\.?\s+(?P<b>.+?)\s*\((?P<fmt>BO\d)\)\s*-\s*(?P<event>.+)$", re.I)

VRS_REPO = "ValveSoftware/counter-strike_regional_standings"
VRS_API_LIVE = f"https://api.github.com/repos/{VRS_REPO}/contents/live"
VRS_RAW = f"https://raw.githubusercontent.com/{VRS_REPO}"
STANDINGS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*\[details\]\(([^)]+)\)")

HLTV_RANKING = "https://www.hltv.org/ranking/teams"
OFFLINE = os.environ.get("HOTSPAWN_OFFLINE_DIR")


def log(msg: str) -> None:
    print(f"[collect {now_iso()}] {msg}", flush=True)


# -------------------------------------------------------------------------------- Hotspawn
def walk_fixtures(node, out: list) -> None:
    if isinstance(node, dict):
        if "scheduled_start_time" in node and "participants0_name" in node:
            out.append(node)
        for value in node.values():
            walk_fixtures(value, out)
    elif isinstance(node, list):
        for item in node:
            walk_fixtures(item, out)


def find_week(node):
    if isinstance(node, dict):
        if "weekStartUtc" in node and "weekEndUtc" in node:
            return node
        for value in node.values():
            found = find_week(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = find_week(item)
            if found:
                return found
    return None


def fixture_row(node: dict, page: str, url: str, read_utc: str, links: dict) -> dict | None:
    mid = str(node.get("id") or "").strip()
    a, b = node.get("participants0_name"), node.get("participants1_name")
    start = ms_to_iso(node.get("scheduled_start_time"))
    if not (mid and a and b and start):
        return None
    lock = ms_to_iso(node.get("lock_time"))
    breakdown = node.get("points_breakdown") or {}
    return {
        "match_id": mid,
        "sport": node.get("sport_alias"),
        "competition": node.get("competition_name"),
        "competition_id": node.get("competition_id"),
        "tier": str(node.get("tier") or "").upper(),
        "stage": node.get("stage"),
        "status": node.get("status"),
        "team_a": a.strip(), "team_b": b.strip(),
        "team_a_id": node.get("participants0_id"), "team_b_id": node.get("participants1_id"),
        "start_utc": start, "lock_utc": lock,
        "lock_offset_sec": node.get("lock_offset_sec"),
        "offered_points": node.get("offered_points"),
        "base_points": node.get("base_points"),
        "points_breakdown": breakdown,
        "best_of_payload": node.get("best_of"),
        "series_format_payload": node.get("series_format"),
        "score_a_payload": node.get("participants0_score"),
        "score_b_payload": node.get("participants1_score"),
        # ownership only — read by strategy.py, never by a probability
        "crowd_a_ownership": node.get("participants0_picked_percent"),
        "crowd_b_ownership": node.get("participants1_picked_percent"),
        "total_picks_ownership": node.get("total_picks"),
        "hotspawn_match_url": links.get(mid),
        "pages": [page],
        "source_url": url,
        "read_utc": read_utc,
    }


def read_state(page: str, url: str) -> tuple[dict | None, dict, str]:
    """Return (state_json, page_record, html) for one Hotspawn page (live or offline)."""
    rec = {"page": page, "url": url, "status": None, "error": None, "read_utc": now_iso(),
           "bytes": 0, "sha256": None, "week_text": None, "tier_total": None, "state_rows": 0}
    if OFFLINE:
        path = Path(OFFLINE) / f"hotspawn_state_{page}_2026_10_15.json.gz"
        if not path.exists():
            rec["error"] = f"offline fixture missing: {path}"
            return None, rec, ""
        text = gzip.open(path).read().decode("utf-8", errors="replace")
        rec.update(status=200, bytes=len(text), read_utc="offline-fixture")
        try:
            return json.loads(unescape(text).strip()), rec, ""
        except json.JSONDecodeError as exc:
            rec["error"] = f"offline JSON: {exc}"
            return None, rec, ""
    got = http_get(url, timeout=45)
    rec.update(status=got["status"], error=got["error"], read_utc=got["fetched_utc"],
               bytes=got["bytes"], sha256=got["sha256"])
    html = got["body"].decode("utf-8", errors="replace") if got["body"] else ""
    if not html:
        return None, rec, ""
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    if (m := WEEK_TEXT.search(text)):
        rec["week_text"] = f"{m.group(1)} matches this week"
    if (m := TIER_TEXT.search(re.sub(r"\s+", " ", unescape(text)))):
        rec["tier_total"] = int(m.group(1))
    m = STATE_SCRIPT.search(html)
    if not m:
        rec["error"] = (rec["error"] or "") + " ng-state script not found"
        return None, rec, html
    save_raw(f"hotspawn_state_{page}", m.group(1))
    try:
        return json.loads(unescape(m.group(1)).strip()), rec, html
    except json.JSONDecodeError as exc:
        rec["error"] = f"ng-state JSON: {exc}"
        return None, rec, html


def collect_hotspawn() -> dict:
    fixtures: dict[str, dict] = {}
    pages, week = [], None
    for page, url in HOTSPAWN_PAGES:
        state, rec, html = read_state(page, url)
        links = {m.group(1): m.group(0) for m in MATCH_LINK.finditer(html)} if html else {}
        if state is not None:
            nodes: list[dict] = []
            walk_fixtures(state, nodes)
            rec["state_rows"] = len(nodes)
            week = week or find_week(state)
            for node in nodes:
                row = fixture_row(node, page, url, rec["read_utc"], links)
                if not row or str(row.get("sport") or "").lower() != "cs2":
                    continue
                known = fixtures.get(row["match_id"])
                if known:
                    if page not in known["pages"]:
                        known["pages"].append(page)
                    for key, val in row.items():
                        if known.get(key) in (None, "", []) and val not in (None, "", []):
                            known[key] = val
                else:
                    fixtures[row["match_id"]] = row
        pages.append(rec)
    rows = sorted(fixtures.values(), key=lambda r: (r["start_utc"], r["match_id"]))
    ok = sum(1 for p in pages if p["status"] == 200 and p["state_rows"])
    log(f"hotspawn: {len(rows)} CS2 fixtures from {ok}/{len(pages)} pages")
    week_out = None
    if week:
        week_out = {k: week.get(k) for k in ("weekId", "status", "weekStartUtc", "weekEndUtc", "cutoffUtc", "title")}
        week_out["prizes"] = [{"rank": (p.get("rank") or {}).get("label"), "title": p.get("title"),
                               "minRank": p.get("minRank"), "maxRank": p.get("maxRank")}
                              for p in (week.get("prizes") or []) if isinstance(p, dict)]
    return {"pages": pages, "fixtures": rows, "week": week_out,
            "complete": ok == len(pages)}


# -------------------------------------------------------------------------------- Pinnacle
def collect_pinnacle() -> dict:
    out = {"status": "unavailable", "page_url": PIN_PAGE, "matchups_url": PIN_MATCHUPS,
           "markets_url": PIN_MARKETS, "quotes": [], "cs2_matchups": 0, "read_utc": now_iso()}
    if OFFLINE:
        try:
            matchups = json.loads(gzip.open(Path(OFFLINE) / "pinnacle_matchups_2026_10_15.json.gz").read())
            markets = json.loads(gzip.open(Path(OFFLINE) / "pinnacle_markets_2026_10_15.json.gz").read())
            out["read_utc"] = "offline-fixture"
        except (OSError, json.JSONDecodeError) as exc:
            out["error"] = f"offline fixture: {exc}"
            return out
    else:
        matchups, gm = get_json(PIN_MATCHUPS, timeout=60)
        markets, gk = get_json(PIN_MARKETS, timeout=60)
        out["read_utc"] = gk.get("fetched_utc") or now_iso()
        if not isinstance(matchups, list) or not isinstance(markets, list):
            out["error"] = f"matchups {gm.get('status')}/{gm.get('error')}; markets {gk.get('status')}/{gk.get('error')}"
            log(f"pinnacle refused: {out['error']}")
            return out
        save_raw("pinnacle_matchups", gm["body"])
        save_raw("pinnacle_markets", gk["body"])
    events = {}
    for node in matchups:
        if not isinstance(node, dict) or node.get("type") != "matchup" or node.get("parentId") is not None:
            continue
        league = node.get("league") or {}
        if not str(league.get("name", "")).startswith("CS2 - "):
            continue
        names = {p.get("alignment"): p.get("name") for p in (node.get("participants") or [])}
        if set(names) != {"home", "away"}:
            continue
        start = parse_iso(node.get("startTime"))
        events[node.get("id")] = {"team_a": names["home"], "team_b": names["away"],
                                  "start_utc": iso(start), "league": league.get("name"),
                                  "best_of": node.get("bestOfX"), "matchup_id": node.get("id")}
    out["cs2_matchups"] = len(events)
    for market in markets:
        if not isinstance(market, dict) or market.get("type") != "moneyline" or market.get("period") != 0:
            continue
        if market.get("isAlternate") or market.get("status") != "open":
            continue
        ev = events.get(market.get("matchupId"))
        if not ev:
            continue
        prices = {p.get("designation"): p.get("price") for p in (market.get("prices") or []) if isinstance(p, dict)}
        if set(prices) != {"home", "away"}:
            continue
        da, db = american_to_decimal(prices["home"]), american_to_decimal(prices["away"])
        if not (da and db):
            continue
        out["quotes"].append({**ev, "source": "Pinnacle", "kind": "bookmaker",
                              "american_a": prices["home"], "american_b": prices["away"],
                              "odds_a": da, "odds_b": db, "read_utc": out["read_utc"],
                              "source_url": PIN_PAGE, "api_url": PIN_MARKETS})
    out["status"] = "observed" if out["quotes"] else "served, no open CS2 moneyline"
    log(f"pinnacle: {len(out['quotes'])} CS2 moneylines on {len(events)} matchups")
    return out


# ------------------------------------------------------------------------------ Polymarket
def _json_list(value) -> list:
    """gamma-api encodes list fields as JSON strings ("[\"9z\", \"Team Falcons\"]"); accept both forms."""
    if isinstance(value, list):
        return value
    return json.loads(value or "[]")


PM_SERIES = 10310  # Polymarket series "counter-strike" (every CS2 match event)
PM_EVENTS_URL = ("https://gamma-api.polymarket.com/events?series_id={series}&closed={closed}"
                 "&end_date_min={since}&limit=200&offset={offset}")


def _pm_markets(closed: bool, since: str, out: dict) -> list[dict]:
    """Match markets from the CS2 series (events -> nested markets) plus the tag query, de-duplicated."""
    markets, seen = [], set()
    for offset in (0, 200, 400, 600):
        url = PM_EVENTS_URL.format(series=PM_SERIES, closed=str(closed).lower(), since=since, offset=offset)
        out.setdefault("api_urls", []).append(url)
        page, got = get_json(url, timeout=60)
        if not isinstance(page, list):
            out["error"] = f"events {got.get('status')}/{got.get('error')}"
            break
        out["read_utc"] = got["fetched_utc"]
        for ev in page:
            for m in (ev.get("markets") or []) if isinstance(ev, dict) else []:
                if isinstance(m, dict) and m.get("slug") not in seen:
                    seen.add(m.get("slug"))
                    markets.append(m)
        if len(page) < 200:
            break
    if not closed:
        url = PM_URL.format(tag=PM_TAG, since=since, offset=0)
        out["api_urls"].append(url)
        page, got = get_json(url, timeout=60)
        for m in page if isinstance(page, list) else []:
            if isinstance(m, dict) and m.get("slug") not in seen:
                seen.add(m.get("slug"))
                markets.append(m)
    return markets


def _pm_match(m: dict):
    """(outcomes, prices, regex match) for a match-winner market, else None."""
    q = (m.get("question") or "").strip()
    mm = PM_QUESTION.match(q)
    if not mm:
        return None
    group = (m.get("groupItemTitle") or "Match Winner").strip().lower()
    if group not in ("match winner", ""):
        return None
    try:
        outcomes = _json_list(m.get("outcomes"))
        prices = [float(x) for x in _json_list(m.get("outcomePrices"))]
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    return outcomes, prices, mm


def collect_polymarket() -> dict:
    out = {"status": "unavailable", "quotes": [], "resolved": [], "read_utc": now_iso(), "api_urls": []}
    if OFFLINE:
        fixture = Path(OFFLINE) / "polymarket_markets_test.json"
        markets = read_json(fixture, []) if fixture.exists() else []
        out["read_utc"] = "offline-fixture"
    else:
        markets = _pm_markets(False, iso(now_utc() - timedelta(days=1)), out)
    for m in markets:
        if not isinstance(m, dict) or m.get("closed"):
            continue
        parsed = _pm_match(m)
        if not parsed:
            continue
        outcomes, prices, mm = parsed
        slug = m.get("slug") or ""
        out["quotes"].append({
            "source": "Polymarket", "kind": "prediction_market",
            "team_a": outcomes[0], "team_b": outcomes[1], "price_a": prices[0], "price_b": prices[1],
            "format": mm.group("fmt").upper(), "event": mm.group("event").strip(), "question": m.get("question"),
            "start_utc": iso(parse_iso(m.get("gameStartTime"))), "end_utc": iso(parse_iso(m.get("endDate"))),
            "volume": m.get("volumeNum") or m.get("volume"), "slug": slug,
            "source_url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com/",
            "read_utc": out["read_utc"]})
    if not OFFLINE:
        for m in _pm_markets(True, iso(now_utc() - timedelta(days=4)), {"api_urls": out["api_urls"]}):
            parsed = _pm_match(m)
            if not parsed or max(parsed[1]) < 0.99:
                continue
            outcomes, prices, _ = parsed
            slug = m.get("slug") or ""
            out["resolved"].append({"team_a": outcomes[0], "team_b": outcomes[1],
                                    "winner": outcomes[0] if prices[0] > prices[1] else outcomes[1],
                                    "start_utc": iso(parse_iso(m.get("gameStartTime"))), "question": m.get("question"),
                                    "source_url": f"https://polymarket.com/event/{slug}" if slug else "https://polymarket.com/",
                                    "resolution_source": m.get("resolutionSource") or "", "read_utc": out["read_utc"]})
    out["status"] = "observed" if out["quotes"] else ("served, no CS2 match-winner market" if markets else out["status"])
    log(f"polymarket: {len(out['quotes'])} CS2 match-winner markets; {len(out['resolved'])} resolved in the last 4 days")
    return out


# ------------------------------------------------------------------------------ Valve VRS
def parse_standings(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        m = STANDINGS_ROW.match(line.strip())
        if not m:
            continue
        roster = [x.strip() for x in m.group(4).split(",") if x.strip()]
        rows.append({"rank": int(m.group(1)), "points": int(m.group(2)), "name": m.group(3).strip(),
                     "roster": roster, "details": m.group(5).strip()})
    return rows


DETAIL_ROW = re.compile(r"^\|\s*\d+\s*\|\s*(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([^|]+?)\s*\|\s*([WL])\s*\|.*\|\s*([^|]+?)\s*\|\s*$")


def roster_history(details_text: str, roster: list[str]) -> dict:
    """Rated matches (Valve details table) played by exactly the current five."""
    current = {r.casefold() for r in roster}
    dates = []
    for line in details_text.splitlines():
        m = DETAIL_ROW.match(line.strip())
        if not m:
            continue
        five = {x.strip().casefold() for x in m.group(5).split(",") if x.strip()}
        if five == current:
            dates.append(m.group(2))
    return {"matches_with_current_five": len(dates), "first_rated_match_current_five": min(dates) if dates else None,
            "last_rated_match_current_five": max(dates) if dates else None}


def collect_vrs() -> dict:
    out = {"status": "unavailable", "teams": [], "file": None, "as_of": None, "commit": None, "url": None}
    local = os.environ.get("VRS_REPO_DIR")
    if local and Path(local).is_dir():
        base = Path(local)
        files = sorted(base.glob("live/*/standings_global_*.md"))
        if not files:
            out["error"] = "no standings_global file in local clone"
            return out
        newest = files[-1]
        rel = newest.relative_to(base).as_posix()
        commit = os.environ.get("VRS_COMMIT") or ""
        text = newest.read_text(encoding="utf-8", errors="replace")
        teams = parse_standings(text)
        for t in teams:
            dpath = newest.parent / t["details"]
            if dpath.exists():
                t.update(roster_history(dpath.read_text(encoding="utf-8", errors="replace"), t["roster"]))
        out.update(status="observed", file=rel, commit=commit or None, teams=teams)
    else:
        listing, got = get_json(VRS_API_LIVE, timeout=40)
        if not isinstance(listing, list):
            out["error"] = f"github api {got.get('status')}/{got.get('error')}"
            return out
        years = sorted(e["name"] for e in listing if e.get("type") == "dir" and str(e.get("name", "")).isdigit())
        if not years:
            out["error"] = "no year folders"
            return out
        files, got = get_json(f"{VRS_API_LIVE}/{years[-1]}", timeout=40)
        names = sorted(e["name"] for e in (files or []) if str(e.get("name", "")).startswith("standings_global_"))
        if not names:
            out["error"] = "no standings_global file"
            return out
        rel = f"live/{years[-1]}/{names[-1]}"
        commits, _ = get_json(f"https://api.github.com/repos/{VRS_REPO}/commits?path={rel}&per_page=1", timeout=40)
        commit = commits[0]["sha"] if isinstance(commits, list) and commits else "main"
        got = http_get(f"{VRS_RAW}/{commit}/{rel}", timeout=40)
        if got["status"] != 200:
            out["error"] = f"raw {got['status']}/{got['error']}"
            return out
        teams = parse_standings(got["body"].decode("utf-8", errors="replace"))
        out.update(status="observed", file=rel, commit=commit, teams=teams)
    m = re.search(r"(\d{4})_(\d{2})_(\d{2})", out["file"] or "")
    out["as_of"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else None
    ref = out["commit"] or "main"
    out["url"] = f"https://github.com/{VRS_REPO}/blob/{ref}/{out['file']}"
    log(f"vrs: {len(out['teams'])} teams from {out['file']} ({out['as_of']})")
    return out


# ----------------------------------------------------------------------------------- HLTV
RANK_BLOCK = re.compile(r'<div class="ranked-team standard-box">(.*?)(?=<div class="ranked-team standard-box">|$)', re.S)


def parse_hltv_ranking(html: str) -> dict:
    teams = []
    for block in RANK_BLOCK.findall(html):
        pos = re.search(r'class="position[^"]*">#(\d+)<', block)
        name = re.search(r'<span class="name">([^<]+)</span>', block)
        pts = re.search(r'<span class="points">\((\d+)', block)
        if not (pos and name):
            continue
        tid = re.search(r'href="/team/(\d+)/([^"]+)"', block)
        players = re.findall(r'<div class="rankingNicknames"><span>([^<]+)</span>', block)
        teams.append({"rank": int(pos.group(1)), "name": unescape(name.group(1)).strip(),
                      "points": int(pts.group(1)) if pts else None, "players": players[:5],
                      "team_url": f"https://www.hltv.org/team/{tid.group(1)}/{tid.group(2)}" if tid else None})
    date = re.search(r'/ranking/teams/(\d{4})/([a-z]+)/(\d{1,2})', html)
    return {"teams": teams, "date_path": "/".join(date.groups()) if date else None}


def collect_hltv(previous: dict | None) -> dict:
    out = {"status": "unavailable", "teams": [], "url": HLTV_RANKING, "read_utc": now_iso()}
    if OFFLINE:
        path = Path(OFFLINE) / "hltv_ranking_2026_10_15.json.gz"
        html = gzip.open(path).read().decode("utf-8", errors="replace") if path.exists() else ""
        out["read_utc"] = "offline-fixture"
    else:
        got = http_get(HLTV_RANKING, timeout=40)
        out["read_utc"] = got["fetched_utc"]
        html = got["body"].decode("utf-8", errors="replace") if got["status"] == 200 else ""
        if not html:
            out["error"] = f"{got['status']}/{got['error']}"
    if html:
        parsed = parse_hltv_ranking(html)
        if len(parsed["teams"]) >= 30:
            out.update(status="observed", teams=parsed["teams"], date_path=parsed["date_path"])
            if parsed["date_path"]:
                out["url"] = f"https://www.hltv.org/ranking/teams/{parsed['date_path']}"
            # raw HTML is not archived (165 KB per run); provenance keeps its SHA-256
    if out["status"] != "observed" and previous and previous.get("status") == "observed":
        age = None
        prev_dt = parse_iso(previous.get("read_utc"))
        if prev_dt:
            age = (now_utc() - prev_dt).total_seconds() / 86400
        if age is not None and age <= 9:
            carried = dict(previous)
            carried["status"] = "carried_forward"
            carried["carry_note"] = f"live read refused ({out.get('error')}); previous read {previous.get('read_utc')} reused (age {age:.1f} d <= 9 d)"
            log("hltv: " + carried["carry_note"])
            return carried
    log(f"hltv: {out['status']} ({len(out['teams'])} teams)")
    return out


# ----------------------------------------------------------------------------------- main
def main() -> int:
    ensure_dirs()
    previous = read_json(CAPTURE, {}) or {}
    started = now_iso()
    hotspawn = collect_hotspawn()
    capture = {
        "schema": "hotspawn-board/1",
        "session": SESSION,
        "started_utc": started,
        "offline": bool(OFFLINE),
        "hotspawn": hotspawn,
        "pinnacle": collect_pinnacle(),
        "polymarket": collect_polymarket(),
        "vrs": collect_vrs(),
        "hltv": collect_hltv((previous.get("hltv") if isinstance(previous, dict) else None)),
    }
    if not hotspawn["fixtures"] and previous.get("hotspawn", {}).get("fixtures"):
        # fail closed: keep the previous fixture list, mark the capture as stale
        capture["hotspawn"] = dict(previous["hotspawn"])
        capture["hotspawn"]["stale_carry"] = f"live Hotspawn read failed at {started}; previous capture kept"
        capture["hotspawn"]["complete"] = False
        log("hotspawn read failed; previous fixtures carried forward and marked stale")
    capture["finished_utc"] = now_iso()
    capture["provenance"] = PROVENANCE
    write_json(CAPTURE, capture)
    log(f"capture written: {len(capture['hotspawn']['fixtures'])} fixtures")
    return 0


if __name__ == "__main__":
    from common import run_main
    run_main(main)
