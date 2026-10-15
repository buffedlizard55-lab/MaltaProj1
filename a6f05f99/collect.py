#!/usr/bin/env python3
"""Collect every input for the a6f05f99 board from public sources (session ``arena/a6f05f99``).

Runs unattended on GitHub Actions every four hours.  Sources, in the order they are read:

1. **Hotspawn Play** — ``/lobby``, ``/cs2-pickems``, ``/thp-pickems``.  Each page is server-side
   rendered by Angular and ships its data inside ``<script id="ng-state">`` (TransferState).  That
   JSON carries per fixture: id, competition, tier, stage, ``scheduled_start_time`` / ``lock_time``
   (epoch ms), points, participants and the public crowd pick share.  The crowd share is stored as
   ``crowd_*_ownership`` and is only ever read by the strategy layer, never by a probability.
2. **Pinnacle** — the public guest JSON that pinnacle.com's own CS2 page loads.  Whole-match
   moneylines only (period 0, not alternate, open).  A sharp bookmaker.
3. **bo3.gg** — the public JSON its own match pages load (``api.bo3.gg/api/v1/matches``).  Carries
   the bookmaker price bo3.gg relays (provider named in the payload) plus the series length.  This
   is the rung that reaches the low-tier leagues the sharp book does not price.
4. **Polymarket** — gamma API, Counter-Strike series 10310 plus the "counter strike 2" tag 100780.
   A prediction market; labelled as such everywhere it is used.
5. **Valve Regional Standings** — newest ``live/<year>/standings_global_*.md`` in Valve's official
   repository.  Official points + roster per team.
6. **HLTV world ranking** — ``www.hltv.org/ranking/teams``.  HLTV often refuses datacentre clients;
   a refusal is recorded and the previous good read (with its original timestamp) is kept.

No single source failure stops the run.  A failed source keeps its previous capture **with the
original read time** (never relabelled as fresh) and the refusal is written to ``provenance``.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, PROVENANCE, RAW, SESSION, HTML_HEADERS, JSON_HEADERS,  # noqa: E402
                    ensure_dirs, get_json, http_get, iso, log, ms_to_iso, now_iso, now_utc,
                    read_json, write_json)

CAPTURE = DATA / "capture.json"

# ----------------------------------------------------------------------------------- 1. Hotspawn
HOTSPAWN_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
]
NG_STATE = re.compile(r'<script[^>]*id="ng-state"[^>]*>(.*?)</script>', re.S | re.I)

# ----------------------------------------------------------------------------------- 2. Pinnacle
PIN_BASE = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_HEADERS = {
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pinnacle.com", "Referer": "https://www.pinnacle.com/",
}
PIN_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"

# --------------------------------------------------------------------------------------- 3. bo3
BO3_API = "https://api.bo3.gg/api/v1/matches"
BO3_PAGE = "https://bo3.gg/matches/current"

# --------------------------------------------------------------------------------- 4. Polymarket
PM_EVENTS = "https://gamma-api.polymarket.com/events"
PM_MARKETS = "https://gamma-api.polymarket.com/markets"
PM_TAG_CS2 = 100780
PM_SERIES_CS2 = 10310

# --------------------------------------------------------------------------------- 5. Valve VRS
VRS_REPO = "ValveSoftware/counter-strike_regional_standings"
VRS_CONTENTS = f"https://api.github.com/repos/{VRS_REPO}/contents/live"  # year dirs live under this
VRS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|")

# --------------------------------------------------------------------------------- 6. HLTV rank
HLTV_RANKING = "https://www.hltv.org/ranking/teams"
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


# ============================================================================== Hotspawn
def _walk(node, out: list) -> None:
    """Every object in the TransferState that looks like a fixture row."""
    if isinstance(node, dict):
        if "scheduled_start_time" in node and "participants0_name" in node:
            out.append(node)
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for item in node:
            _walk(item, out)


def _walk_key(node, key: str, out: list) -> None:
    if isinstance(node, dict):
        if key in node:
            out.append(node)
        for value in node.values():
            _walk_key(value, key, out)
    elif isinstance(node, list):
        for item in node:
            _walk_key(item, key, out)


def collect_hotspawn(previous: dict | None) -> dict:
    pages, fixtures, week = [], {}, None
    for page, url in HOTSPAWN_PAGES:
        rec = http_get(url, headers=HTML_HEADERS, timeout=60)
        entry = {"page": page, "url": url, "status": rec["status"], "bytes": rec["bytes"],
                 "sha256": rec["sha256"], "fetched_utc": rec["fetched_utc"], "error": rec["error"]}
        if rec["status"] == 200 and rec["body"]:
            RAW.mkdir(parents=True, exist_ok=True)
            (RAW / f"hotspawn_state_{page}.json.gz").write_bytes(
                gzip.compress(rec["body"], mtime=0))
            html = rec["body"].decode("utf-8", "replace")
            match = NG_STATE.search(html)
            state = None
            if match:
                try:
                    state = json.loads(match.group(1))
                except ValueError:
                    entry["error"] = "invalid TransferState JSON"
            else:
                entry["error"] = "ng-state TransferState not found"
            rows: list = []
            if state is not None:
                _walk(state, rows)
                weeks: list = []
                _walk_key(state, "weekStartUtc", weeks)
                week = week or (weeks[0] if weeks else None)
            entry["fixture_records"] = len(rows)
            for raw in rows:
                fid = str(raw.get("id") or "").strip()
                a = (raw.get("participants0_name") or "").strip()
                b = (raw.get("participants1_name") or "").strip()
                start = ms_to_iso(raw.get("scheduled_start_time"))
                if not (fid and a and b and start):
                    continue
                if str(raw.get("sport_alias") or "").lower() != "cs2":
                    continue
                row = {
                    "match_id": fid, "competition": raw.get("competition_name"),
                    "competition_id": str(raw.get("competition_id") or ""),
                    "tier": str(raw.get("tier") or "").upper(), "stage": raw.get("stage"),
                    "status": raw.get("status"),
                    "team_a": a, "team_b": b,
                    "team_a_id": str(raw.get("participants0_id") or ""),
                    "team_b_id": str(raw.get("participants1_id") or ""),
                    "start_utc": start, "lock_utc": ms_to_iso(raw.get("lock_time")),
                    "points": raw.get("offered_points") or raw.get("base_points"),
                    "best_of": raw.get("best_of"), "series_format": raw.get("series_format"),
                    "score_a": raw.get("participants0_score"), "score_b": raw.get("participants1_score"),
                    # ownership only - never a probability input
                    "crowd_a_ownership": raw.get("participants0_picked_percent"),
                    "crowd_b_ownership": raw.get("participants1_picked_percent"),
                    "total_picks": raw.get("total_picks"),
                    "pages": [page], "source_url": url, "read_utc": rec["fetched_utc"],
                }
                if fid in fixtures:
                    if page not in fixtures[fid]["pages"]:
                        fixtures[fid]["pages"].append(page)
                else:
                    fixtures[fid] = row
        pages.append(entry)
    ok = [p for p in pages if p.get("fixture_records")]
    result = {"mode": "live" if fixtures else "failed", "pages": pages, "week": week,
              "fixtures": sorted(fixtures.values(), key=lambda f: (f["lock_utc"] or "", f["match_id"])),
              "read_utc": max((p["fetched_utc"] for p in ok), default=None)}
    log(f"hotspawn: {len(fixtures)} CS2 fixtures from {len(ok)}/{len(pages)} pages")
    if not fixtures and previous and previous.get("fixtures"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        kept["latest_attempt"] = pages
        return kept
    return result


# ============================================================================== Pinnacle
def collect_pinnacle(previous: dict | None) -> dict:
    matchups, rec_a = get_json(f"{PIN_BASE}/sports/12/matchups?withSpecials=false",
                               headers=PIN_HEADERS, timeout=60)
    markets, rec_b = get_json(
        f"{PIN_BASE}/sports/12/markets/straight?primaryOnly=false&withSpecials=false",
        headers=PIN_HEADERS, timeout=60)
    by_id = {str(m.get("id")): m for m in (matchups or []) if isinstance(m, dict)}
    quotes = []
    for mkt in (markets or []):
        if not isinstance(mkt, dict):
            continue
        if str(mkt.get("matchupId") or "") not in by_id:
            continue
        mu = by_id[str(mkt["matchupId"])]
        if not isinstance(mu.get("participants"), list) or len(mu.get("participants") or []) < 2:
            continue
        parts = {str(p.get("participantId")): p for p in (mu.get("participants") or [])}
        prices = {}
        for price in (mkt.get("prices") or []):
            if not isinstance(price, dict):
                continue
            if price.get("period") != 0 or price.get("type") != "moneyline":
                continue
            if price.get("status") not in (None, "open"):
                continue
            pid = str(price.get("participantId"))
            if pid in parts:
                prices[pid] = price.get("price")
        if len(prices) != 2:
            continue
        names = [((parts[pid].get("name") or "").strip()) for pid in prices]
        if not all(names):
            continue
        # The series length is not carried by this feed; bo3.gg and HLTV supply it.
        quotes.append({
            "source": "Pinnacle", "kind": "bookmaker",
            "team_a": names[0], "team_b": names[1],
            "american_a": list(prices.values())[0], "american_b": list(prices.values())[1],
            "league": ((mu.get("league") or {}).get("name") if isinstance(mu.get("league"), dict)
                       else None),
            "start_utc": iso(parse_dt(mu.get("startTime"))),
            "matchup_id": mu.get("id"), "best_of": best_of,
            "source_url": PIN_PAGE, "api_url": f"{PIN_BASE}/sports/12/markets/straight",
            "read_utc": rec_b["fetched_utc"],
        })
    result = {"mode": "live" if quotes else "empty", "quotes": quotes, "page_url": PIN_PAGE,
              "status": [rec_a["status"], rec_b["status"]], "read_utc": rec_b["fetched_utc"]}
    log(f"pinnacle: {len(quotes)} CS2 two-way moneylines (HTTP {rec_a['status']}/{rec_b['status']})")
    if not quotes and previous and previous.get("quotes"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        return kept
    return result


def parse_dt(value):
    from common import parse_iso
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime
        return datetime.fromisoformat(text)
    except ValueError:
        return None


# ============================================================================== bo3.gg
def collect_bo3(previous: dict | None) -> dict:
    """Upcoming CS2 matches with the bookmaker price bo3.gg relays (provider named in payload)."""
    matches, statuses = [], []
    offset, limit = 0, 100
    while offset <= 1500:
        params = [("page[offset]", str(offset)), ("page[limit]", str(limit)),
                  ("sort", "start_date"), ("filter[matches.status][in]", "upcoming"),
                  ("filter[matches.discipline_id][eq]", "1"), ("with", "teams,tournament")]
        data, rec = get_json(BO3_API + "?" + urllib.parse.urlencode(params), timeout=60)
        statuses.append(rec["status"])
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            break
        for m in data["results"]:
            if not isinstance(m, dict):
                continue
            tour = m.get("tournament") or {}
            t1, t2 = m.get("team1") or {}, m.get("team2") or {}
            bu = m.get("bet_updates") if isinstance(m.get("bet_updates"), dict) else None
            quote = None
            if bu and isinstance(bu.get("team_1"), dict) and isinstance(bu.get("team_2"), dict):
                c1, c2 = bu["team_1"].get("coeff"), bu["team_2"].get("coeff")
                if c1 and c2:
                    quote = {"provider": bu.get("provider"),
                             "coeff_1": c1, "coeff_2": c2,
                             "active_1": bu["team_1"].get("active"),
                             "active_2": bu["team_2"].get("active"),
                             "book_url": bu.get("path")}
            matches.append({
                "source": "bo3.gg", "kind": "bookmaker_relayed",
                "bo3_id": m.get("id"), "slug": m.get("slug"),
                "team_a": t1.get("name"), "team_b": t2.get("name"),
                "tournament": tour.get("name"), "tier": m.get("tier"),
                "best_of": m.get("bo_type"),
                "start_utc": (str(m.get("start_date") or "")[:19] + "Z") if m.get("start_date") else None,
                "quote": quote,
                "source_url": f"https://bo3.gg/matches/{m.get('slug')}" if m.get("slug") else BO3_PAGE,
                "api_url": BO3_API, "read_utc": rec["fetched_utc"],
            })
        total = (data.get("total") or {}).get("count")
        if len(data["results"]) < limit or (total and offset + limit >= total):
            break
        offset += limit
        time.sleep(0.4)
    priced = sum(1 for m in matches if m.get("quote"))
    result = {"mode": "live" if matches else "empty", "matches": matches, "page_url": BO3_PAGE,
              "status": statuses, "read_utc": now_iso()}
    log(f"bo3.gg: {len(matches)} upcoming CS2 matches ({priced} with a relayed bookmaker price)")
    if not matches and previous and previous.get("matches"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        return kept
    return result


# ============================================================================== Polymarket
def _pm_market(ev: dict, mk: dict, rec: dict) -> dict | None:
    if not isinstance(mk, dict) or mk.get("closed"):
        return None
    question = str(mk.get("question") or "")
    if re.search(r"map\s*\d|game\s*\d|handicap|total", question, re.I):
        return None
    try:
        outcomes = json.loads(mk.get("outcomes") or "[]")
        prices = [float(x) for x in json.loads(mk.get("outcomePrices") or "[]")]
    except (ValueError, TypeError):
        return None
    if len(outcomes) != 2 or len(prices) != 2:
        return None
    fmt = re.search(r"\(BO(\d)\)", question, re.I)
    return {
        "source": "Polymarket", "kind": "prediction_market",
        "team_a": outcomes[0], "team_b": outcomes[1],
        "price_a": prices[0], "price_b": prices[1],
        "format": f"BO{fmt.group(1)}" if fmt else None,
        "event": ev.get("title"), "question": question,
        "start_utc": (str(mk.get("gameStartTime") or ev.get("startTime") or "").replace(" ", "T")[:19] + "Z"),
        "volume": mk.get("liquidityNum") or mk.get("liquidity"),
        "source_url": f"https://polymarket.com/event/{ev.get('slug')}" if ev.get("slug") else None,
        "api_url": PM_EVENTS, "read_utc": rec["fetched_utc"],
    }


def collect_polymarket(previous: dict | None) -> dict:
    quotes, statuses = [], []
    since = iso(now_utc() - __import__("datetime").timedelta(hours=12))
    for offset in range(0, 400, 100):
        params = {"series_id": str(PM_SERIES_CS2), "closed": "false", "limit": "100",
                  "offset": str(offset), "end_date_min": since}
        data, rec = get_json(PM_EVENTS + "?" + urllib.parse.urlencode(params), timeout=60)
        statuses.append(rec["status"])
        if not isinstance(data, list) or not data:
            break
        for ev in data:
            for mk in ev.get("markets") or []:
                row = _pm_market(ev, mk, rec)
                if row:
                    quotes.append(row)
        if len(data) < 100:
            break
        time.sleep(0.3)
    # Second, independent query: the "counter strike 2" tag (catches markets outside the series).
    for offset in (0, 500):
        params = {"closed": "false", "tag_id": str(PM_TAG_CS2), "end_date_min": since,
                  "limit": "500", "offset": str(offset)}
        data, rec = get_json(PM_MARKETS + "?" + urllib.parse.urlencode(params), timeout=60)
        statuses.append(rec["status"])
        if not isinstance(data, list):
            break
        have = {(str(q["source_url"]), str(q["question"])) for q in quotes}
        for mk in data:
            row = _pm_market({"slug": mk.get("slug"), "title": mk.get("question")}, mk, rec)
            if row and (str(row["source_url"]), str(row["question"])) not in have:
                quotes.append(row)
        if len(data) < 500:
            break
        time.sleep(0.3)
    result = {"mode": "live" if quotes else "empty", "quotes": quotes, "status": statuses,
              "page_url": "https://polymarket.com/sports/counter-strike-2", "read_utc": now_iso()}
    log(f"polymarket: {len(quotes)} open match-winner markets")
    if not quotes and previous and previous.get("quotes"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        return kept
    return result


# ============================================================================== Valve VRS
def parse_vrs(md: str) -> list[dict]:
    rows = []
    for line_no, line in enumerate(md.splitlines(), start=1):
        m = VRS_ROW.match(line)
        if m:
            rows.append({"rank": int(m.group(1)), "points": int(m.group(2)),
                         "name": m.group(3).strip(),
                         "roster": [p.strip() for p in m.group(4).split(",") if p.strip()],
                         "line": line_no})
    return rows


def collect_vrs(previous: dict | None) -> dict:
    """Read the newest ``live/<year>/standings_global_*.md`` from Valve's official repository.

    ``/contents/live`` lists *directories* (2024, 2025, 2026), not files, so each year directory has
    to be listed separately. The current year is tried first, then the previous one, so a capture
    still works across a New Year boundary before Valve has published the first file of the year.
    """
    this_year = now_utc().year
    for year in (this_year, this_year - 1):
        listing, rec = get_json(f"https://api.github.com/repos/{VRS_REPO}/contents/live/{year}",
                                headers={**JSON_HEADERS,
                                         "Accept": "application/vnd.github+json"})
        files = []
        if isinstance(listing, list):
            files = sorted(e["name"] for e in listing if isinstance(e, dict)
                           and re.fullmatch(r"standings_global_\d{4}_\d{2}_\d{2}\.md",
                                            str(e.get("name"))))
        if not files:
            continue
        name = files[-1]
        commits, _ = get_json(
            f"https://api.github.com/repos/{VRS_REPO}/commits?path=live/{year}/{name}&per_page=1",
            headers={**JSON_HEADERS, "Accept": "application/vnd.github+json"})
        sha = commits[0]["sha"] if isinstance(commits, list) and commits else "main"
        raw = http_get(
            f"https://api.github.com/repos/{VRS_REPO}/contents/live/{year}/{name}?ref={sha}",
            headers={**JSON_HEADERS, "Accept": "application/vnd.github.raw"}, timeout=60)
        if raw["status"] == 200 and raw["body"]:
            teams = parse_vrs(raw["body"].decode("utf-8", "replace"))
            if len(teams) > 50:
                date = re.search(r"(\d{4})_(\d{2})_(\d{2})", name)
                log(f"vrs: {name} @ {sha[:10]} - {len(teams)} teams")
                return {"mode": "live", "file": name, "commit": sha,
                        "standings_date": f"{date.group(1)}-{date.group(2)}-{date.group(3)}",
                        "blob_url": f"https://github.com/{VRS_REPO}/blob/{sha}/live/{year}/{name}",
                        "teams": teams, "read_utc": raw["fetched_utc"]}
    log("vrs: live read failed - no readable standings_global_*.md in live/<year>")
    if previous and previous.get("teams"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        return kept
    return {"mode": "failed", "teams": [], "read_utc": now_iso()}


# ============================================================================== HLTV ranking
def parse_hltv_ranking(html: str):
    teams = []
    for block in html.split('<div class="ranked-team standard-box">')[1:]:
        import html as _html
        pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
        name = re.search(r'<span class="name">([^<]+)</span>', block)
        pts = re.search(r'<span class="points">\((\d+)', block)
        tid = re.search(r'href="/team/(\d+)/([^"]+)"', block)
        if pos and name:
            teams.append({"rank": int(pos.group(1)), "name": _html.unescape(name.group(1)).strip(),
                          "points": int(pts.group(1)) if pts else None,
                          "team_url": (f"https://www.hltv.org/team/{tid.group(1)}/{tid.group(2)}"
                                       if tid else None)})
    date = re.search(r"World ranking on ([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", html)
    when = None
    if date and date.group(1).lower() in MONTHS:
        when = (f"{int(date.group(3)):04d}-{MONTHS.index(date.group(1).lower()) + 1:02d}-"
                f"{int(date.group(2)):02d}")
    return when, teams


def collect_hltv(previous: dict | None) -> dict:
    rec = http_get(HLTV_RANKING, headers=HTML_HEADERS, timeout=40, retries=1)
    if rec["status"] == 200 and rec["body"]:
        when, teams = parse_hltv_ranking(rec["body"].decode("utf-8", "replace"))
        if len(teams) >= 30:
            log(f"hltv ranking: {len(teams)} teams ({when})")
            url = HLTV_RANKING
            if when:
                url = f"{HLTV_RANKING}/{when[:4]}/{MONTHS[int(when[5:7]) - 1]}/{int(when[8:10])}"
            return {"mode": "live", "ranking_date": when, "teams": teams,
                    "url": url, "read_utc": rec["fetched_utc"]}
    log(f"hltv ranking: not readable from this runner (HTTP {rec['status']}); keeping previous")
    if previous and previous.get("teams"):
        kept = dict(previous)
        kept["mode"] = "previous_capture"
        kept["latest_attempt"] = {"status": rec["status"], "fetched_utc": rec["fetched_utc"]}
        return kept
    return {"mode": "failed", "teams": [], "read_utc": rec["fetched_utc"]}


# ============================================================================== main
def main() -> int:
    ensure_dirs()
    previous = read_json(CAPTURE, {}) or {}
    capture = {
        "schema": "a6f05f99-board/1", "session": SESSION, "started_utc": now_iso(),
        "hotspawn": collect_hotspawn(previous.get("hotspawn")),
        "pinnacle": collect_pinnacle(previous.get("pinnacle")),
        "bo3": collect_bo3(previous.get("bo3")),
        "polymarket": collect_polymarket(previous.get("polymarket")),
        "vrs": collect_vrs(previous.get("vrs")),
        "hltv": collect_hltv(previous.get("hltv")),
    }
    capture["finished_utc"] = now_iso()
    capture["provenance"] = PROVENANCE
    write_json(CAPTURE, capture)
    modes = {k: capture[k].get("mode") for k in ("hotspawn", "pinnacle", "bo3", "polymarket",
                                                 "vrs", "hltv")}
    log(f"capture written: {CAPTURE} modes={modes}")
    return 0 if capture["hotspawn"].get("fixtures") else 2


if __name__ == "__main__":
    sys.exit(main())
