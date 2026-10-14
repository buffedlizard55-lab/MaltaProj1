#!/usr/bin/env python3
"""Collect the inputs for the executive board — session arena/5545dbb8.

Runs on GitHub Actions (this project's agent sandbox has no general internet access; Actions
runners do). Everything this module writes is raw evidence plus a normalized projection:

* ``data/hotspawn_pages.json`` + ``data/hotspawn_fixtures.csv`` — the fixture slate.
* ``data/vrs.csv`` — Valve Regional Standings (official Valve repository, newest snapshot).
* ``data/hltv_ranking.csv``, ``data/hltv_matches.csv``, ``data/hltv_match_pages.csv``,
  ``data/hltv_team_rosters.csv`` — HLTV reference data.
* ``data/external_lines.csv`` — outside bookmaker prices (Pinnacle public guest endpoint first,
  then other public coverage such as EGamersWorld).
* ``data/provenance.json`` — URL, UTC minute, HTTP status, byte count and SHA-256 per fetch.

Every source is attempted live. If a source cannot be read, the previous capture committed in this
repository is used **and labelled with its original capture time** (never relabelled as fresh), or
the affected field stays blank and is flagged by the build. Nothing is filled in from memory.
Hotspawn crowd percentages are dropped at ingest: they are never stored and never used.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    DATA, EGW_MATCHES, HLTV_MATCHES, HLTV_RANKING, HLTV_RESULTS, HOTSPAWN_CS2, HOTSPAWN_LOBBY,
    HOTSPAWN_THP, PIN_BASE, PIN_HEADERS, epoch_ms_to_iso, norm, parse_iso,
)

# ------------------------------------------------------------------ constants
HOTSPAWN_PAGES = [HOTSPAWN_CS2, HOTSPAWN_LOBBY, HOTSPAWN_THP]
KEEP_FIELDS = [
    "id", "competition_id", "competition_name", "sport_alias", "status",
    "scheduled_start_time", "lock_time", "lock_offset_sec", "best_of", "series_format",
    "tier", "offered_points", "stage", "participants0_id", "participants0_name",
    "participants1_id", "participants1_name",
]
# Fields that must never be stored. Hotspawn pick'em crowd percentages are not a probability input.
DROPPED_FIELDS = ["participants0_picked_percent", "participants1_picked_percent", "total_picks"]

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]

ROOT_REPO = Path(__file__).resolve().parent.parent
PROV: list[dict] = []


def parse_dt(value):
    from common import parse_iso
    return parse_iso(value)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prov(url: str, **extra) -> dict:
    row = {"url": url, "fetched_utc": now_iso(), "status": None, "bytes": None, "sha256": None,
           "mode": None, "note": None}
    row.update(extra)
    PROV.append(row)
    return row


def http_get(url: str, headers: dict | None = None, timeout: int = 45,
             tries: int = 3) -> tuple[int, bytes, str]:
    """GET with retries. Returns (status, body, final_url); status 0 on transport failure."""
    hdrs = {"User-Agent": ("Mozilla/5.0 (compatible; MaltaProj1-executive/1.0; "
                           "+https://github.com/buffedlizard55-lab/MaltaProj1)"),
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"}
    if headers:
        hdrs.update(headers)
    last = (0, b"", url)
    for attempt in range(tries):
        req = urllib.request.Request(url, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read(12_000_000)
                return resp.status, body, resp.geturl()
        except urllib.error.HTTPError as exc:
            last = (exc.code, b"", url)
            if exc.code in (403, 404, 429) and attempt + 1 < tries:
                time.sleep(3 * (attempt + 1))
                continue
            if exc.code in (403, 404):
                break
            time.sleep(2 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - transport errors are recorded, not raised
            last = (0, str(exc).encode()[:200], url)
            time.sleep(2 * (attempt + 1))
    return last


# ------------------------------------------------------------------ Hotspawn fixtures
def parse_hotspawn_page(url: str) -> tuple[dict, list[dict], dict, dict | None]:
    t = now_iso()
    status, body, final = http_get(url, tries=3)
    entry = {"url": url, "final_url": final, "fetched_utc": t, "http_status": status,
             "bytes": len(body), "sha256": None}
    if status != 200:
        entry["result"] = f"FAILED - HTTP {status}"
        prov(url, status=status, bytes=len(body), mode="live", note=entry["result"])
        return entry, [], {}, None
    text = body.decode("utf-8", "replace")
    from common import sha256_bytes
    entry["sha256"] = sha256_bytes(body)
    prov(url, status=status, bytes=len(body), sha256=entry["sha256"], mode="live")
    match = re.search(r'<script[^>]*id="ng-state"[^>]*>(.*?)</script>', text, re.S)
    if not match:
        entry["result"] = "FAILED - ng-state TransferState not found"
        return entry, [], {}, None
    state = json.loads(match.group(1))
    fixtures: list[dict] = []
    permalinks: dict[str, str] = {}
    week = None
    for key, value in state.items():
        body_item = value.get("b") if isinstance(value, dict) else None
        if isinstance(body_item, list) and body_item and isinstance(body_item[0], dict) \
                and "participants0_name" in body_item[0] and len(body_item) > len(fixtures):
            fixtures = body_item
        if isinstance(body_item, dict) and "weekStartUtc" in body_item:
            week = {k: body_item.get(k) for k in ("weekId", "weekStartUtc", "weekEndUtc", "cutoffUtc")}
        if isinstance(body_item, dict) and isinstance(body_item.get("permalinks"), dict):
            for fid, link in body_item["permalinks"].items():
                if isinstance(link, str) and link.startswith(("https://www.hotspawn.com/",
                                                             "https://play.hotspawn.com/")):
                    permalinks[str(fid)] = link
    plain = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)))
    header = re.search(r"(\d+)\s*matches this week", plain)
    total = re.search(r"All tiers \((\d+)\)", plain)
    entry.update({
        "transferstate_key": next((k for k, v in state.items()
                                   if isinstance(v, dict) and isinstance(v.get("b"), list)
                                   and v["b"] and isinstance(v["b"][0], dict)
                                   and "participants0_name" in v["b"][0] and len(v["b"]) == len(fixtures)), None),
        "fixture_count": len(fixtures),
        "lobby_header_matches_this_week": int(header.group(1)) if header else None,
        "lobby_filter_all_tiers": int(total.group(1)) if total else None,
        "rendered_card_count": len(re.findall(r"<app-pickem-vs-card\b", text)),
        "result": f"OK - {len(fixtures)} fixtures",
    })
    return entry, fixtures, permalinks, week


def collect_hotspawn(use_previous: bool = True) -> dict:
    pages, union, permalinks, week = [], {}, {}, None
    for url in HOTSPAWN_PAGES:
        entry, fixtures, links, wk = parse_hotspawn_page(url)
        pages.append(entry)
        permalinks.update(links)
        week = week or wk
        for fixture in fixtures:
            if (fixture.get("sport_alias") or "").lower() != "cs2":
                continue
            fid = str(fixture.get("id"))
            record = {field: fixture.get(field) for field in KEEP_FIELDS}
            record["seen_on"] = []
            union.setdefault(fid, record)
            union[fid]["seen_on"].append(url)
    payload = {
        "source_url": HOTSPAWN_CS2, "source_urls": HOTSPAWN_PAGES,
        "fetched_utc": max((p["fetched_utc"] for p in pages if p.get("fixture_count")), default=now_iso()),
        "pages": pages, "fixture_count": len(union), "pickem_week": week,
        "crowd_fields_dropped": DROPPED_FIELDS,
        "note": "Fixture identity, tier, points and UTC lock/start epochs only. No crowd percentage is stored.",
        "permalinks": {k: v for k, v in permalinks.items() if k in union},
        "fixtures": sorted(union.values(), key=lambda f: (int(f.get("scheduled_start_time") or 0), str(f.get("id")))),
        "mode": "live" if union else None,
    }
    if not union and use_previous:
        prev = json.loads((DATA / "hotspawn_pages.json").read_text()) if (DATA / "hotspawn_pages.json").exists() else None
        if prev and prev.get("fixtures"):
            prev["mode"] = "previous_capture"
            prov(HOTSPAWN_CS2, mode="previous_capture", status=0,
                 note=f"live read failed; reusing capture from {prev.get('fetched_utc')}")
            return prev
    return payload


# ------------------------------------------------------------------ Hotspawn (repo-capture fallback for offline development)
def hotspawn_from_repo_capture() -> dict | None:
    """Read the most recent committed Hotspawn capture in this repository (read-only).

    Used only when the live read fails, or when collect.py runs with --offline. The capture keeps
    its original ``fetched_utc`` so no page can present old data as a fresh read.
    """
    candidates = [
        (Path("/home/user/MaltaProj1") / "model/input/hotspawn_cs2_fixtures.json", "model/input"),
        (DATA.parent.parent / "model/input/hotspawn_cs2_fixtures.json", "model/input"),
    ]
    for path, label in candidates:
        if not path.exists():
            continue
        raw = json.loads(path.read_text())
        fixtures = []
        for fixture in raw.get("fixtures", []):
            record = {field: fixture.get(field) for field in KEEP_FIELDS}
            record["seen_on"] = fixture.get("seen_on", [])
            fixtures.append(record)
        if not fixtures:
            continue
        prov(path.as_posix(), mode="repo_capture", status=200, bytes=path.stat().st_size,
             note=f"offline/repo fallback snapshot captured {raw.get('fetched_utc')}")
        return {
            "source_url": HOTSPAWN_CS2, "source_urls": raw.get("source_urls", []),
            "fetched_utc": raw.get("fetched_utc"), "pages": raw.get("pages", []),
            "fixture_count": len(fixtures), "pickem_week": raw.get("pickem_week"),
            "crowd_fields_dropped": DROPPED_FIELDS,
            "note": (f"Offline fallback: repo capture {label} captured {raw.get('fetched_utc')}. "
                     "Fixture identity only; crowd percentages were dropped by that capture too."),
            "permalinks": {k: v for k, v in (raw.get("permalinks") or {}).items()
                           if isinstance(v, str) and v.startswith("https://")},
            "fixtures": fixtures,
            "mode": "repo_capture",
            "repo_capture_path": path.as_posix(),
        }
    return None


# ------------------------------------------------------------------ Valve Regional Standings (official)
def collect_vrs(offline: bool = False) -> dict:
    """Newest ``live/<year>/standings_global_<date>.md`` straight from Valve's official repository."""
    if offline:
        local = DATA / "vrs.json"
        if local.exists():
            payload = json.loads(local.read_text())
            payload["mode"] = "previous_capture"
            return payload
    t = now_iso()
    with tempfile.TemporaryDirectory() as tmp:
        run = subprocess.run(["git", "clone", "-q", "--depth", "1",
                              "https://github.com/ValveSoftware/counter-strike_regional_standings",
                              f"{tmp}/vrs"], capture_output=True, text=True)
        if run.returncode != 0:
            prov("https://github.com/ValveSoftware/counter-strike_regional_standings",
                 status=0, mode="live", note=f"git clone failed: {run.stderr[-200:]}")
            local = DATA / "vrs.json"
            if local.exists():
                payload = json.loads(local.read_text())
                payload["mode"] = "previous_capture"
                return payload
            return {"rows": [], "mode": "failed", "fetched_utc": t}
        repo = Path(tmp) / "vrs"
        commit = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H|%cI|%s"],
                                capture_output=True, text=True).stdout.strip().split("|", 2)
        candidates = []
        for path in repo.glob("live/*/standings_global_*.md"):
            found = re.search(r"standings_global_(\d{4})_(\d{2})_(\d{2})\.md$", path.name)
            if found:
                candidates.append(("-".join(found.groups()), path))
        if not candidates:
            prov("https://github.com/ValveSoftware/counter-strike_regional_standings",
                 status=0, mode="live", note="no standings_global_*.md in clone")
            return {"rows": [], "mode": "failed", "fetched_utc": t}
        date, path = max(candidates)
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(repo).as_posix()
        rows = []
        for line in text.splitlines():
            found = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\|\s*"
                             r"\[details\]\(([^)]+)\)", line)
            if not found:
                continue
            rows.append({
                "vrs_rank": int(found.group(1)), "vrs_points": int(found.group(2)),
                "vrs_name": found.group(3).strip(), "vrs_roster": found.group(4).strip(),
                "vrs_details_path": found.group(5).strip(),
            })
        from common import sha256_bytes
        prov(f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{commit[0]}/{rel}",
             status=200, bytes=len(text), sha256=sha256_bytes(text.encode()), mode="live",
             note=f"official Valve standings, commit {commit[0][:10]}")
        return {
            "repo": "https://github.com/ValveSoftware/counter-strike_regional_standings",
            "commit": commit[0], "commit_date": commit[1], "commit_message": commit[2],
            "path": rel, "standings_date": date,
            "blob_url": f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{commit[0]}/{rel}",
            "details_base": f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{commit[0]}/live/2026/",
            "sha256": sha256_bytes(text.encode()),
            "rows": rows, "mode": "live", "fetched_utc": now_iso(),
        }


# ------------------------------------------------------------------ HLTV
def collect_hltv_ranking(offline: bool = False) -> dict:
    urls = [HLTV_RANKING]
    today = datetime.now(timezone.utc).date()
    for weeks_back in (0, 1, 2):
        day = today.fromordinal(today.toordinal() - today.weekday() - 7 * weeks_back)
        urls.append(f"{HLTV_RANKING}/{day.year}/{MONTHS[day.month - 1]}/{day.day}")
    for url in urls:
        status, body, _ = http_get(url, tries=2)
        if status != 200:
            prov(url, status=status, mode="live", note="HLTV ranking read failed")
            continue
        text = body.decode("utf-8", "replace")
        teams = []
        for block in text.split('<div class="ranked-team standard-box">')[1:]:
            pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
            name = re.search(r'<span class="name">([^<]+)</span>', block)
            pts = re.search(r'<span class="points">\((\d+)', block)
            tid = re.search(r'href="/team/(\d+)/([^"]+)"', block)
            nicks = [unescape(n) for n in re.findall(r'<div class="rankingNicknames"><span>([^<]+)</span>', block)]
            if pos and name:
                teams.append({"rank": int(pos.group(1)), "name": unescape(name.group(1)).strip(),
                              "points": int(pts.group(1)) if pts else None,
                              "team_id": tid.group(1) if tid else None,
                              "slug": tid.group(2) if tid else None, "players": nicks})
        date_match = re.search(r"World ranking on ([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", text)
        from common import sha256_bytes
        prov(url, status=status, bytes=len(body), sha256=sha256_bytes(body), mode="live")
        if not teams or not date_match:
            continue
        month, day, year = date_match.group(1), int(date_match.group(2)), int(date_match.group(3))
        return {
            "source_url": url,
            "canonical_url": f"{HLTV_RANKING}/{year}/{month.lower()}/{day}",
            "ranking_date": f"{year:04d}-{MONTHS.index(month.lower()) + 1:02d}-{day:02d}",
            "ranking_date_text": date_match.group(0), "team_count": len(teams), "teams": teams,
            "fetched_utc": now_iso(), "mode": "live",
        }
    if offline or True:
        local = DATA / "hltv_ranking.json"
        if local.exists():
            payload = json.loads(local.read_text())
            payload["mode"] = "previous_capture"
            return payload
    return {"teams": [], "mode": "failed", "fetched_utc": now_iso()}


def parse_hltv_match_list(html: str) -> list[dict]:
    rows, seen = [], set()
    for match in re.finditer(r'href="(/matches/(\d+)/([a-z0-9\-]+))"', html or ""):
        path, match_id, slug = match.group(1), match.group(2), match.group(3)
        if match_id in seen:
            continue
        window = (html or "")[match.end(): match.end() + 2600]
        nxt = re.search(r'href="/matches/\d+/', window)
        if nxt:
            window = window[:nxt.start()]
        unix = re.search(r'data-unix="(\d{13})"', window)
        if not unix:
            continue
        event = re.search(r'class="event-name"[^>]*>\s*([^<]{2,70})\s*<', window)
        fmt = re.search(r"\b(bo[135])\b", window, re.I)
        live_names = re.findall(r'class="team[^"]*"[^>]*>\s*([^<]{2,40})\s*<', window)
        team_links = re.findall(r'href="/team/(\d+)/([^"]+)"', window)
        if len(live_names) < 2:
            continue
        seen.add(match_id)
        rows.append({
            "hltv_match_id": match_id, "hltv_url": "https://www.hltv.org" + path, "slug": slug,
            "team_a": unescape(live_names[0]).strip(), "team_b": unescape(live_names[1]).strip(),
            "team_a_link": (f"https://www.hltv.org/team/{team_links[0][0]}/{team_links[0][1]}"
                            if len(team_links) > 0 else None),
            "team_b_link": (f"https://www.hltv.org/team/{team_links[1][0]}/{team_links[1][1]}"
                            if len(team_links) > 1 else None),
            "event": unescape(event.group(1)).strip() if event else None,
            "format": fmt.group(1).upper() if fmt else None,
            "kickoff_utc": datetime.fromtimestamp(int(unix.group(1)) / 1000, timezone.utc)
                           .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return rows


def collect_hltv_matches(offline: bool = False) -> dict:
    rows: dict[str, dict] = {}
    for url in (HLTV_MATCHES, HLTV_RESULTS):
        status, body, _ = http_get(url, tries=2)
        from common import sha256_bytes
        prov(url, status=status, bytes=len(body) or None,
             sha256=sha256_bytes(body) if body else None, mode="live")
        if status != 200:
            continue
        for row in parse_hltv_match_list(body.decode("utf-8", "replace")):
            row["listed_on"] = url
            rows.setdefault(row["hltv_match_id"], row)
    if rows:
        return {"rows": sorted(rows.values(), key=lambda r: r["kickoff_utc"]), "mode": "live",
                "fetched_utc": now_iso(), "sources": [HLTV_MATCHES, HLTV_RESULTS]}
    local = DATA / "hltv_matches.json"
    if local.exists():
        payload = json.loads(local.read_text())
        payload["mode"] = "previous_capture"
        return payload
    return {"rows": [], "mode": "failed", "fetched_utc": now_iso(), "sources": [HLTV_MATCHES, HLTV_RESULTS]}


def collect_hltv_match_page(url: str) -> dict | None:
    status, body, final = http_get(url, tries=2)
    from common import sha256_bytes
    prov(url, status=status, bytes=len(body) or None,
         sha256=sha256_bytes(body) if body else None, mode="live")
    if status != 200:
        return None
    html = body.decode("utf-8", "replace")
    plain = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    teams = re.findall(r'href="/team/(\d+)/([^"]+)"', html)
    fmt = re.search(r"Best of (\d)", plain) or re.search(r"\((bo[135])\)", plain, re.I)
    vrs_badges = re.findall(r"VRS(?: Europe| Americas| Asia| Global)?\s*#(\d+)", plain)
    id_match = re.search(r"/matches/(\d+)/", url)
    return {
        "hltv_url": url,
        "hltv_match_id": id_match.group(1) if id_match else None,
        "team_links": sorted({f"https://www.hltv.org/team/{tid}/{slug}" for tid, slug in teams}),
        "team_names": sorted({unescape(slug.replace("-", " ")) for _, slug in teams}),
        "format": (f"BO{fmt.group(1)}" if fmt and fmt.group(1).isdigit() else (fmt.group(1).upper() if fmt else None)),
        "vrs_badges_on_page": vrs_badges,
        "observed_utc": now_iso(),
    }


def collect_hltv_team_roster(url: str) -> dict | None:
    status, body, _ = http_get(url, tries=2)
    from common import sha256_bytes
    prov(url, status=status, bytes=len(body) or None,
         sha256=sha256_bytes(body) if body else None, mode="live")
    if status != 200:
        return None
    html = body.decode("utf-8", "replace")
    nicks, seen = [], set()
    for _, nick in re.findall(r'href="/player/(\d+)/([^"]+)"', html):
        name = unescape(nick.replace("-", " "))
        if name.lower() not in seen:
            seen.add(name.lower())
            nicks.append(name)
    plain = unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)))
    rank = re.search(r"World ranking\s*#(\d+)", plain)
    return {"hltv_url": url, "players": nicks[:6],
            "world_rank_text": rank.group(1) if rank else None, "observed_utc": now_iso()}


# ------------------------------------------------------------------ Pinnacle (public guest endpoint)
def pin_get(path: str, timeout: int = 30):
    url = f"{PIN_BASE}{path}"
    status, body, _ = http_get(url, headers=PIN_HEADERS, timeout=timeout, tries=2)
    from common import sha256_bytes
    prov(url, status=status, bytes=len(body) or None,
         sha256=sha256_bytes(body) if status == 200 and body else None, mode="live",
         note="Pinnacle public guest response (same endpoint pinnacle.com's own page loads)")
    if status != 200:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def collect_pinnacle() -> dict:
    from common import PIN_SPORT_ESPORTS, american_to_decimal
    leagues = pin_get(f"/sports/{PIN_SPORT_ESPORTS}/leagues?all=false")
    if not isinstance(leagues, list):
        return {"quotes": [], "mode": "failed", "leagues": [], "fetched_utc": now_iso()}
    cs2_leagues = [(lg.get("id"), lg.get("name")) for lg in leagues
                   if str(lg.get("name", "")).startswith("CS2 - ")]
    quotes, seen_events = [], set()
    deadline = time.time() + 7 * 60
    for league_id, league_name in cs2_leagues:
        if time.time() > deadline:
            break
        matchups = pin_get(f"/leagues/{league_id}/matchups?withSpecials=false")
        if not isinstance(matchups, list):
            continue
        for matchup in matchups:
            if time.time() > deadline:
                break
            event_id = matchup.get("id")
            participants = matchup.get("participants") or []
            if not isinstance(participants, list) or len(participants) != 2 or event_id is None:
                continue
            names = {p.get("alignment"): p.get("name") for p in participants}
            if set(names) != {"home", "away"}:
                continue
            markets = pin_get(f"/matchups/{event_id}/markets/related/straight")
            if not isinstance(markets, list):
                continue
            for market in markets:
                if (market.get("type") != "moneyline" or market.get("period") != 0
                        or market.get("isAlternate") is not False or market.get("status") != "open"):
                    continue
                prices = {p.get("designation"): p.get("price") for p in market.get("prices") or []}
                if set(prices) != {"home", "away"}:
                    continue
                try:
                    odds_a = american_to_decimal(prices["home"])
                    odds_b = american_to_decimal(prices["away"])
                except ValueError:
                    continue
                key = (str(matchup.get("id")), league_id)
                if key in seen_events:
                    continue
                seen_events.add(key)
                quotes.append({
                    "source_id": "pinnacle", "source_name": "Pinnacle",
                    "source_role": "primary_bookmaker",
                    "event_id": str(event_id), "league": unescape(str(league_name)),
                    "team_a": unescape(str(names["home"])), "team_b": unescape(str(names["away"])),
                    "start_time": str(matchup.get("startTime") or "")[:19] + "Z",
                    "best_of": matchup.get("bestOfX"),
                    "native_format": "american",
                    "native_a": prices["home"], "native_b": prices["away"],
                    "odds_a": round(odds_a, 6), "odds_b": round(odds_b, 6),
                    "market_type": "match_winner", "status": "open",
                    "source_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
                    "api_url": f"{PIN_BASE}/matchups/{event_id}/markets/related/straight",
                    "captured_utc": now_iso(),
                })
                break
    return {"quotes": quotes, "mode": "live" if quotes else "empty",
            "leagues": [name for _, name in cs2_leagues], "fetched_utc": now_iso()}


def collect_pinnacle_from_repo() -> dict:
    """Read this repository's last committed Pinnacle capture (read-only) when live read is empty."""
    path = Path("/home/user/MaltaProj1/data/snapshot/latest.json")
    if not path.exists():
        path = DATA.parent.parent / "data/snapshot/latest.json"
    if not path.exists():
        return {"quotes": [], "mode": "unavailable"}
    snapshot = json.loads(path.read_text())
    quotes = []
    for quote in snapshot.get("quotes", []):
        if quote.get("source_id") != "pinnacle" or quote.get("game") != "cs2":
            continue
        quotes.append({
            "source_id": "pinnacle", "source_name": "Pinnacle", "source_role": "primary_bookmaker",
            "event_id": str(quote.get("event_id")), "league": quote.get("tournament"),
            "team_a": quote.get("team_a"), "team_b": quote.get("team_b"),
            "start_time": quote.get("start_time"), "best_of": quote.get("best_of"),
            "native_format": quote.get("native_format"),
            "native_a": quote.get("native_odds_a"), "native_b": quote.get("native_odds_b"),
            "odds_a": quote.get("odds_a"), "odds_b": quote.get("odds_b"),
            "market_type": "match_winner", "status": quote.get("status"),
            "source_url": quote.get("source_url"), "api_url": quote.get("api_url"),
            "captured_utc": (quote.get("observed_at") or "")[:19] + "Z",
        })
    prov(path.as_posix(), mode="repo_capture", status=200, bytes=path.stat().st_size,
         note=f"repo Pinnacle capture generated {snapshot.get('generated_at')}")
    return {"quotes": quotes, "mode": "repo_capture", "captured_from": path.as_posix(),
            "captured_utc": snapshot.get("generated_at")}


def collect_secondary_lines_from_repo() -> dict:
    """Read the repository's last committed secondary-bookmaker capture (read-only).

    The numbers are copied verbatim with the capture time of the file they came from; they are never
    presented as a fresh read. Any equal-pair placeholder (1.80/1.80) is dropped and flagged by the
    build exactly as the live collector would drop it.
    """
    path = Path("/home/user/MaltaProj1/data/8944bb84/external_lines.csv")
    if not path.exists():
        path = DATA.parent.parent / "data/8944bb84/external_lines.csv"
    if not path.exists():
        return {"quotes": [], "mode": "unavailable"}
    import csv
    quotes = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for prefix, label in (("egw", "EGamersWorld (bc.game)"),):
                try:
                    oa = float(row.get(f"{prefix}_odds_a") or "")
                    ob = float(row.get(f"{prefix}_odds_b") or "")
                except ValueError:
                    continue
                if not oa or not ob:
                    continue
                quotes.append({
                    "source_id": prefix, "source_name": label, "source_role": "secondary_bookmaker",
                    "event_id": row.get("match_id"), "league": row.get("tournament"),
                    "team_a": row.get("team_a"), "team_b": row.get("team_b"),
                    "start_time": row.get("start_utc"), "best_of": None,
                    "native_format": "decimal", "native_a": oa, "native_b": ob,
                    "odds_a": oa, "odds_b": ob, "market_type": "match_winner", "status": "open",
                    "source_url": row.get(f"{prefix}_url") or EGW_MATCHES,
                    "api_url": None, "captured_utc": (row.get("captured_utc") or "")[:19] + "Z",
                })
    prov(path.as_posix(), mode="repo_capture", status=200, bytes=path.stat().st_size,
         note="repo secondary-bookmaker capture (EGamersWorld listing of bc.game prices)")
    return {"quotes": quotes, "mode": "repo_capture", "captured_from": path.as_posix(),
            "captured_utc": None}


def collect_egw() -> dict:
    """EGamersWorld public CS2 match list. Frequently refuses automated reads (documented, not hidden)."""
    status, body, _ = http_get(EGW_MATCHES, tries=2)
    from common import sha256_bytes
    prov(EGW_MATCHES, status=status, bytes=len(body) or None,
         sha256=sha256_bytes(body) if status == 200 and body else None, mode="live")
    if status != 200:
        return {"quotes": [], "mode": f"refused_http_{status}", "captured_utc": now_iso()}
    text = body.decode("utf-8", "replace")
    quotes = []
    for match in re.finditer(r'href="(/counterstrike/match/[^"]+)"[^>]*>(.*?)</a>', text, re.S):
        window = text[match.end(): match.end() + 900]
        odds = re.findall(r">\s*(\d\.\d{2})\s*<", window)
        if len(odds) < 2:
            continue
        try:
            oa, ob = float(odds[0]), float(odds[1])
        except ValueError:
            continue
        if oa <= 1.0 or ob <= 1.0:
            continue
        quotes.append({"source_id": "egw", "source_name": "EGamersWorld", "source_role": "secondary_bookmaker",
                       "match_url": "https://egamersworld.com" + match.group(1),
                       "odds_a": oa, "odds_b": ob, "native_format": "decimal",
                       "native_a": oa, "native_b": ob, "captured_utc": now_iso()})
    return {"quotes": quotes, "mode": "live" if quotes else "parsed_empty", "captured_utc": now_iso(),
            "source_url": EGW_MATCHES}


# ------------------------------------------------------------------ Valve Regional Standings via the public API
def collect_vrs_api() -> dict:
    """Read the newest official standings file through GitHub's public API (no git needed).

    Used when ``git clone`` is unavailable and for offline development snapshots. The API returns the
    file's own bytes, which are hashed here, so the capture is as auditable as a clone.
    """
    import base64
    listing_url = "https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/live/2026"
    status, body, _ = http_get(listing_url, headers={"Accept": "application/vnd.github+json"}, tries=2)
    if status != 200:
        prov(listing_url, status=status, mode="api", note="GitHub API listing failed")
        return {"rows": [], "mode": "failed", "fetched_utc": now_iso()}
    try:
        entries = json.loads(body.decode())
    except json.JSONDecodeError:
        return {"rows": [], "mode": "failed", "fetched_utc": now_iso()}
    candidates = []
    for entry in entries:
        found = re.match(r"standings_global_(\d{4})_(\d{2})_(\d{2})\.md$", entry.get("name", ""))
        if found:
            candidates.append(("-".join(found.groups()), entry))
    if not candidates:
        return {"rows": [], "mode": "failed", "fetched_utc": now_iso()}
    date, entry = max(candidates, key=lambda item: item[0])
    status, raw, _ = http_get(entry["download_url"], headers={"Accept": "application/vnd.github+json"}, tries=2)
    if status != 200:
        return {"rows": [], "mode": "failed", "fetched_utc": now_iso()}
    text = raw.decode("utf-8", "replace")
    rows = []
    for line in text.splitlines():
        found = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\|\s*"
                         r"\[details\]\(([^)]+)\)", line)
        if found:
            rows.append({"vrs_rank": int(found.group(1)), "vrs_points": int(found.group(2)),
                         "vrs_name": found.group(3).strip(), "vrs_roster": found.group(4).strip(),
                         "vrs_details_path": found.group(5).strip()})
    from common import sha256_bytes
    prov(entry["download_url"], status=status, bytes=len(raw), sha256=sha256_bytes(raw), mode="api",
         note="official Valve standings file, newest snapshot")
    return {
        "repo": "https://github.com/ValveSoftware/counter-strike_regional_standings",
        "commit": (entry.get("sha") or ""), "commit_date": None,
        "path": entry.get("path"), "standings_date": date,
        "blob_url": entry.get("html_url") or "https://github.com/ValveSoftware/counter-strike_regional_standings",
        "details_base": ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
                         f"live/2026/details/{date.replace('-', '_')}/"),
        "sha256": sha256_bytes(raw), "rows": rows, "mode": "api", "fetched_utc": now_iso(),
    }


def hltv_ranking_from_repo() -> dict | None:
    for path in (ROOT_REPO / "model/input/hltv_ranking.json", DATA / "hltv_ranking.json"):
        if path.exists():
            payload = json.loads(path.read_text())
            payload["mode"] = "repo_capture"
            payload["repo_capture_path"] = path.as_posix()
            prov(path.as_posix(), mode="repo_capture", status=200, bytes=path.stat().st_size,
                 note=f"repo HLTV ranking capture ({payload.get('ranking_date_text')})")
            return payload
    return None


def resolve_hltv_spellings(hotspawn: dict, hltv_matches: dict) -> dict:
    """Pair Hotspawn fixtures with the HLTV match listing to learn HLTV's spelling of each team.

    A pair is only accepted when one side matches exactly (case/punctuation-insensitive) and the
    kickoff agrees within 30 minutes; the partner's HLTV spelling is then recorded with the match
    URL as evidence. Nothing is paired on kickoff alone.
    """
    rows = hltv_matches.get("rows", [])
    out: dict[str, dict] = {}
    for fixture in hotspawn.get("fixtures", []):
        teams = [fixture.get("participants0_name"), fixture.get("participants1_name")]
        start = epoch_ms_to_iso(fixture.get("scheduled_start_time"))
        start_dt = parse_dt(start)
        for row in rows:
            pair = [row.get("team_a"), row.get("team_b")]
            kickoff = parse_dt(row.get("kickoff_utc"))
            if start_dt and kickoff and abs((kickoff - start_dt).total_seconds()) > 30 * 60:
                continue
            keys = [norm(p) for p in pair]
            matched = [(idx, teams.index(t)) for idx, t in enumerate(teams)
                       if t and norm(t) in keys]
            if len(matched) != 1:
                continue
            hot_idx = matched[0][1]
            other_hot = teams[1 - hot_idx]
            other_hltv = pair[1 - keys.index(norm(teams[hot_idx]))]
            link = row.get("team_b_link") if keys.index(norm(other_hltv)) == 1 else row.get("team_a_link")
            if not other_hot or not other_hltv:
                continue
            key = norm(other_hot)
            record = out.setdefault(key, {"name": other_hot, "names": [], "url": link,
                                          "evidence_url": row.get("hltv_url"), "source": "hltv_match_listing"})
            if norm(other_hltv) != key and other_hltv not in record["names"]:
                record["names"].append(other_hltv)
            record["url"] = record["url"] or link
            record["evidence_url"] = record["evidence_url"] or row.get("hltv_url")
    return out


def hltv_teams_from_repo() -> dict:
    """Read HLTV team pages already captured in this repository (read-only), for offline builds."""
    path = ROOT_REPO / "data/8944bb84/ratings.csv"
    teams: dict[str, dict] = {}
    if path.exists():
        import csv
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                name = (row.get("hotspawn_team") or "").strip()
                if not name:
                    continue
                players = [p.strip() for p in (row.get("hltv_roster") or "").split(",") if p.strip()]
                teams[norm(name)] = {
                    "name": (row.get("hltv_name") or name).strip(),
                    "names": [n for n in [(row.get("hltv_name") or "").strip()] if n and norm(n) != norm(name)],
                    "url": (row.get("hltv_url") or "").strip(),
                    "players": players,
                    "evidence_url": (row.get("hltv_url") or "").strip(),
                    "source": "repo_capture:data/8944bb84/ratings.csv",
                }
        prov(path.as_posix(), mode="repo_capture", status=200, bytes=path.stat().st_size,
             note="repo HLTV team rosters capture (read-only)")
    return {"teams": teams, "mode": "repo_capture" if teams else "unavailable", "generated_utc": now_iso()}


def collect_hltv_teams(hotspawn: dict, vrs: dict, ranking: dict, hltv_matches: dict,
                       offline: bool = False) -> dict:
    teams: dict[str, dict] = {}
    for team in ranking.get("teams", []):
        teams[norm(team["name"])] = {
            "name": team["name"], "names": [],
            "url": (f"https://www.hltv.org/team/{team['team_id']}/{team['slug']}"
                    if team.get("team_id") and team.get("slug") else ""),
            "players": team.get("players") or [],
            "evidence_url": ranking.get("canonical_url") or HLTV_RANKING,
            "source": "hltv_ranking_page",
        }
    for key, record in resolve_hltv_spellings(hotspawn, hltv_matches).items():
        entry = teams.setdefault(key, {"name": record["name"], "names": [], "url": "", "players": [],
                                       "evidence_url": record.get("evidence_url"),
                                       "source": record.get("source")})
        for alias in record.get("names") or []:
            if alias not in entry["names"]:
                entry["names"].append(alias)
        entry["url"] = entry.get("url") or record.get("url") or ""
        entry["evidence_url"] = entry.get("evidence_url") or record.get("evidence_url") or ""
    repo = hltv_teams_from_repo()
    for key, record in repo["teams"].items():
        entry = teams.setdefault(key, record)
        if not entry.get("players"):
            entry["players"] = record.get("players") or []
        if not entry.get("url"):
            entry["url"] = record.get("url") or ""
        if record.get("name") and norm(record["name"]) != key and record["name"] not in entry.setdefault("names", []):
            entry["names"].append(record["name"])
    # Which teams still need a live roster read? Only those the official standings cannot name.
    vrs_names = {norm(row["vrs_name"]) for row in vrs.get("rows", [])}
    needed = []
    for fixture in hotspawn.get("fixtures", []):
        for team in (fixture.get("participants0_name"), fixture.get("participants1_name")):
            if not team or norm(team) in vrs_names:
                continue
            entry = teams.get(norm(team), {})
            candidates = [norm(entry.get("name"))] + [norm(a) for a in entry.get("names") or []]
            if any(c in vrs_names for c in candidates if c):
                continue
            entry = teams.setdefault(norm(team), {"name": team, "names": [], "url": "", "players": [],
                                                  "evidence_url": "", "source": "pending"})
            if len(entry.get("players") or []) >= 4:
                continue
            if entry.get("url"):
                needed.append(entry["url"])
    fetched = 0
    if not offline:
        for url in sorted(set(needed))[:12]:
            page = collect_hltv_team_roster(url)
            if not page:
                continue
            fetched += 1
            for entry in teams.values():
                if entry.get("url") == url:
                    entry["players"] = page["players"]
                    entry["source"] = "hltv_team_page"
                    entry["evidence_url"] = url
            time.sleep(1.5)
    return {"teams": teams, "mode": "live" if (not offline and fetched) else ("repo_capture" if repo["teams"] else "partial"),
            "live_team_pages_fetched": fetched, "generated_utc": now_iso(),
            "note": "Team spellings and rosters used only to look a team up in the official standings; "
                    "the board always prints Hotspawn's own spelling."}


# ------------------------------------------------------------------ main
def main() -> int:
    parser = argparse.ArgumentParser(description="Collect executive-board inputs")
    parser.add_argument("--offline", action="store_true",
                        help="use this repository's committed captures instead of the network")
    args = parser.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)

    hotspawn = hotspawn_from_repo_capture() if args.offline else collect_hotspawn()
    if not hotspawn.get("fixtures") and not args.offline:
        hotspawn = hotspawn_from_repo_capture() or hotspawn
    vrs = collect_vrs(offline=args.offline)
    if not vrs.get("rows"):
        vrs = collect_vrs_api()
    hltv_ranking = collect_hltv_ranking(offline=args.offline)
    if not hltv_ranking.get("teams"):
        hltv_ranking = hltv_ranking_from_repo() or hltv_ranking
    hltv_matches = collect_hltv_matches(offline=args.offline)
    pinnacle = {"quotes": [], "mode": "skipped"} if args.offline else collect_pinnacle()
    if not pinnacle.get("quotes"):
        fallback = collect_pinnacle_from_repo()
        if fallback.get("quotes"):
            pinnacle = fallback
    secondary = {"quotes": [], "mode": "skipped"} if args.offline else collect_egw()
    secondary_repo = collect_secondary_lines_from_repo()
    secondary_rows = secondary.get("quotes") or secondary_repo.get("quotes", [])
    if secondary_rows and secondary.get("quotes"):
        pass
    elif secondary_repo.get("quotes"):
        secondary = secondary_repo

    hltv_teams = collect_hltv_teams(hotspawn, vrs, hltv_ranking, hltv_matches, offline=args.offline)

    from common import write_json
    write_json(DATA / "hltv_teams.json", hltv_teams)
    write_json(DATA / "hotspawn_pages.json", hotspawn)
    write_json(DATA / "vrs.json", vrs)
    write_json(DATA / "hltv_ranking.json", hltv_ranking)
    write_json(DATA / "hltv_matches.json", hltv_matches)
    write_json(DATA / "pinnacle.json", pinnacle)
    write_json(DATA / "secondary_lines.json", secondary)
    write_json(DATA / "provenance.json", {
        "generated_utc": now_iso(), "offline": args.offline,
        "fetches": PROV,
        "note": "Every fetch attempt: URL, UTC minute, HTTP status, byte count, SHA-256, mode.",
    })
    print(json.dumps({
        "hotspawn": {"mode": hotspawn.get("mode"), "fixtures": hotspawn.get("fixture_count"),
                     "fetched_utc": hotspawn.get("fetched_utc")},
        "vrs": {"mode": vrs.get("mode"), "rows": len(vrs.get("rows", [])),
                "standings_date": vrs.get("standings_date")},
        "hltv_ranking": {"mode": hltv_ranking.get("mode"), "teams": len(hltv_ranking.get("teams", [])),
                         "date": hltv_ranking.get("ranking_date")},
        "hltv_matches": {"mode": hltv_matches.get("mode"), "rows": len(hltv_matches.get("rows", []))},
        "hltv_teams": {"mode": hltv_teams.get("mode"), "teams": len(hltv_teams.get("teams", {}))},
        "pinnacle": {"mode": pinnacle.get("mode"), "quotes": len(pinnacle.get("quotes", []))},
        "secondary": {"mode": secondary.get("mode"), "quotes": len(secondary.get("quotes", []))},
    }, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
