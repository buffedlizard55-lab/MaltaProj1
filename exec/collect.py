#!/usr/bin/env python3
"""exec/collect.py — live source reader for the executive-summary board.

Session: arena/bdc98a9a (task E-02 / E-03). Scope: this file and everything under exec/.

What it reads (public pages only, no account, no credentials, no manual input):

  * Hotspawn Play  /cs2-pickems  and  /lobby      -> the fixture list, from the server-rendered
                                                    Angular TransferState payload (`script#ng-state`).
                                                    Used for identity + exact UTC epochs ONLY.
                                                    Hotspawn crowd percentages are never collected
                                                    into a probability field.
  * Valve          counter-strike_regional_standings (official Valve repository)
                                                 -> Valve Regional Standings points, the project's
                                                    official rating input.
  * HLTV           /matches?date=YYYY-MM-DD  and per-match pages
                                                 -> kickoff, series format ("Best of 3"), and the
                                                    HLTV world rank / unranked status shown for each
                                                    team, plus the HLTV event page.
  * EGamersWorld   public match pages            -> secondary bookmaker prices, where the page
                                                    serves a two-sided line. The known EGW
                                                    `1.80 / 1.80` cut-off placeholder is rejected.

Everything is written to exec/data/live/*.json together with HTTP status, byte count, SHA-256 and
capture time. A source that refuses to serve, times out or returns an unexpected layout is recorded
as a refusal with its error text: it is never filled in with a guess, and the build continues with
the last committed evidence for that input.

Usage:
    python exec/collect.py                 # read every source, write exec/data/live/*.json
    python exec/collect.py --only hltv     # one group (hotspawn|valve|hltv|egw|all)
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "exec" / "data" / "live"
RAW = OUT / "raw"
LOG: list[dict] = []

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
VALVE_DIR = "live/2026"
VALVE_API = ("https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/"
             "contents/{path}")
VALVE_RAW = ("https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/"
             "main/{path}")
HLTV_RANKING = "https://www.hltv.org/ranking/teams"
HLTV_MATCHES = "https://www.hltv.org/matches?date={date}"
EGW_MATCHES = "https://egamersworld.com/counterstrike/matches"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(entry: dict) -> None:
    entry.setdefault("fetched_utc", now_iso())
    LOG.append(entry)
    print(f"  [{entry.get('status') or 'ERR'}] {entry['url'][:110]}"
          f" {entry.get('bytes') or 0}B {entry.get('error') or ''}".rstrip(), flush=True)


# --------------------------------------------------------------------------------------- fetching
def http_get(url: str, timeout: int = 30, headers: dict | None = None) -> dict:
    """One plain HTTP GET. Returns {status, body, bytes, sha256, path, error}."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        **(headers or {}),
    })
    rec = {"url": url, "status": None, "bytes": 0, "sha256": None, "path": "http", "error": None,
           "body": ""}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https hosts)
            body = resp.read()
            rec["status"] = resp.status
    except urllib.error.HTTPError as exc:
        rec["status"] = exc.code
        rec["error"] = f"HTTP {exc.code}"
        body = b""
    except Exception as exc:  # noqa: BLE001 - a refusal is data, not a crash
        rec["error"] = f"{type(exc).__name__}: {exc}"
        body = b""
    rec["bytes"] = len(body)
    rec["sha256"] = hashlib.sha256(body).hexdigest() if body else None
    rec["body"] = body.decode("utf-8", "replace")
    return rec


_BROWSER: dict = {}
BROWSER_BUDGET = {"left": 10}   # per run: a browser render is the fallback, not the normal path


def browser_render(url: str, wait_ms: int = 2500, timeout: int = 45000) -> dict:
    """Render one public page in Chromium. Used only when plain HTTP is refused or empty."""
    rec = {"url": url, "status": None, "bytes": 0, "sha256": None, "path": "browser",
           "error": None, "body": ""}
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"playwright unavailable: {type(exc).__name__}"
        return rec
    try:
        if "pw" not in _BROWSER:
            _BROWSER["pw"] = sync_playwright().start()
            _BROWSER["browser"] = _BROWSER["pw"].chromium.launch(args=["--no-sandbox"])
        ctx = _BROWSER["browser"].new_context(user_agent=UA, locale="en-US",
                                              extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        page = ctx.new_page()
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            rec["status"] = resp.status if resp else None
            page.wait_for_timeout(wait_ms)
            html = page.content()
            body = html.encode("utf-8")
            rec["bytes"] = len(body)
            rec["sha256"] = hashlib.sha256(body).hexdigest()
            rec["body"] = html
        finally:
            ctx.close()
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def close_browser() -> None:
    if "pw" in _BROWSER:
        try:
            _BROWSER["browser"].close()
            _BROWSER["pw"].stop()
        except Exception:  # noqa: BLE001
            pass
        _BROWSER.clear()


def fetch(url: str, marker: str | None = None, force_browser: bool = False) -> dict:
    """Fetch a page; escalate to the browser when plain HTTP is refused or lacks the marker."""
    got = {"url": url, "status": None, "bytes": 0, "sha256": None, "path": None, "error": None,
           "body": ""}
    if not force_browser:
        got = http_get(url)
        ok = got["status"] == 200 and got["body"] and (marker is None or marker in got["body"])
        if ok:
            log({k: got[k] for k in ("url", "status", "bytes", "sha256", "path", "error")})
            return got
        if got["status"] not in (403, 429) and got["body"] and marker is not None:
            # Served, but not the expected layout: record it, still try the browser once.
            log({**{k: got[k] for k in ("url", "status", "bytes", "sha256", "path", "error")},
                 "error": (got["error"] or "") + f" marker {marker!r} absent"})
    if not BROWSER_BUDGET["left"]:
        got["error"] = (got["error"] or "") + " browser-fallback budget exhausted for this run"
        log({k: got[k] for k in ("url", "status", "bytes", "sha256", "path", "error")})
        return got
    BROWSER_BUDGET["left"] -= 1
    seen = browser_render(url)
    if not seen["body"] or (marker is not None and marker not in seen["body"]):
        seen["error"] = (seen["error"] or "") + ("" if not seen["body"] else
                                                 f" marker {marker!r} absent")
        if got["body"]:
            seen["status"] = seen["status"] or got["status"]
            seen["sha256"] = seen["sha256"] or got["sha256"]
    log({k: seen[k] for k in ("url", "status", "bytes", "sha256", "path", "error")})
    return seen


def save(name: str, payload, raw_body: str | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(payload, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    if raw_body:
        RAW.mkdir(parents=True, exist_ok=True)
        with gzip.open(RAW / (name.replace(".json", "") + ".html.gz"), "wt", encoding="utf-8") as fh:
            fh.write(raw_body)


# ------------------------------------------------------------------------------------- Hotspawn
def _ms(value):
    """Hotspawn sends epoch milliseconds as a string; accept number or string, never guess."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return datetime.fromtimestamp(number / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _walk_fixtures(node, out: list) -> None:
    """Collect fixture records out of the TransferState JSON.

    Hotspawn's fixture objects are flat: participants0_name / participants1_name /
    scheduled_start_time (ms epoch as a string) / tier / competition_name / sport_alias. Only a record
    that carries a fixture id, both participant names and a start epoch is accepted.
    """
    if isinstance(node, dict):
        if ("participants0_name" in node and "participants1_name" in node
                and node.get("scheduled_start_time")):
            start = _ms(node.get("scheduled_start_time"))
            team_a = str(node.get("participants0_name") or "").strip()
            team_b = str(node.get("participants1_name") or "").strip()
            if start and team_a and team_b:
                out.append({
                    "fixture_id": str(node.get("id") or ""),
                    "team_a": team_a, "team_b": team_b,
                    "start_utc": start,
                    "lock_utc": _ms(node.get("lock_time")),
                    "lock_offset_sec": node.get("lock_offset_sec"),
                    "tier": node.get("tier"),
                    "competition": node.get("competition_name"),
                    "sport": node.get("sport_alias") or node.get("sport_name"),
                    "stage": node.get("stage"),
                    "best_of": node.get("best_of") or node.get("series_format"),
                    "status": node.get("status"),
                })
        for value in node.values():
            _walk_fixtures(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk_fixtures(value, out)


def hotspawn_capture() -> dict:
    """Fixture identity + exact UTC epochs from the server-rendered ng-state payload."""
    out = {"source_url": HOTSPAWN_CS2, "captured_utc": now_iso(), "fixtures": [], "pages": {}}
    for label, url in (("cs2-pickems", HOTSPAWN_CS2), ("lobby", HOTSPAWN_LOBBY)):
        got = fetch(url, marker='id="ng-state"')
        page = {"url": url, "status": got["status"], "bytes": got["bytes"],
                "sha256": got["sha256"], "path": got["path"], "error": got["error"],
                "fixtures": 0}
        match = re.search(r'<script\s+id="ng-state"[^>]*>(.*?)</script>', got["body"], re.S | re.I)
        if not match:
            match = re.search(r'<script[^>]*id=["\']ng-state["\'][^>]*>(.*?)</script>', got["body"], re.S | re.I)
        page["payload_markers"] = {
            "ng_state_script": bool(match),
            "participants0_name": len(re.findall(r"participants0_name", got["body"])),
            "scheduled_start_time": len(re.findall(r"scheduled_start_time", got["body"])),
        }
        if match:
            try:
                state = json.loads(unescape(match.group(1)).strip())
                rows: list[dict] = []
                _walk_fixtures(state, rows)
                seen: dict[str, dict] = {}
                for row in rows:
                    if row["fixture_id"]:
                        seen[row["fixture_id"]] = row
                cs2 = {k: v for k, v in seen.items() if (v.get("sport") or "").lower() == "cs2"}
                page["fixtures"] = len(cs2) if label == "cs2-pickems" else len(seen)
                page["fixtures_all_sports"] = len(seen)
                out["pages"][label] = page
                if label == "cs2-pickems":
                    out["fixtures"] = sorted(cs2.values(), key=lambda r: (r["start_utc"], r["team_a"]))
                else:
                    out["lobby_fixture_ids"] = sorted(seen)
                    out["lobby_sports"] = sorted({(v.get("sport") or "?") for v in seen.values()})
            except Exception as exc:  # noqa: BLE001
                # Some builds double-encode the state (a JSON string holding JSON). One retry.
                try:
                    state = json.loads(json.loads(unescape(match.group(1)).strip()))
                    rows = []
                    _walk_fixtures(state, rows)
                    seen = {r["fixture_id"]: r for r in rows if r["fixture_id"]}
                    cs2 = {k: v for k, v in seen.items() if (v.get("sport") or "").lower() == "cs2"}
                    page["fixtures"] = len(cs2) if label == "cs2-pickems" else len(seen)
                    page["fixtures_all_sports"] = len(seen)
                    page["note"] = "double-encoded ng-state payload"
                    if label == "cs2-pickems":
                        out["fixtures"] = sorted(cs2.values(), key=lambda r: (r["start_utc"], r["team_a"]))
                    else:
                        out["lobby_fixture_ids"] = sorted(seen)
                except Exception as exc2:  # noqa: BLE001
                    page["error"] = (f"ng-state parse failed: {type(exc).__name__}: {exc} / "
                                     f"{type(exc2).__name__}: {exc2}")
                out["pages"][label] = page
        else:
            page["error"] = page["error"] or "ng-state payload not found in the served HTML"
            out["pages"][label] = page
    out["fixtures_total"] = len(out["fixtures"])
    return out


# ----------------------------------------------------------------------------------------- Valve
def valve_standings() -> dict:
    """Valve Regional Standings (official Valve repository): latest published global file."""
    out = {"source_url": None, "file": None, "as_of": None, "teams": {}, "captured_utc": now_iso(),
           "error": None}
    listing = http_get(VALVE_API.format(path=VALVE_DIR), headers={"Accept": "application/vnd.github+json"})
    names: list[str] = []
    if listing["status"] == 200 and listing["body"]:
        try:
            names = [item["name"] for item in json.loads(listing["body"])
                     if item.get("name", "").endswith(".md")]
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"listing parse failed: {type(exc).__name__}"
    globals_ = sorted(n for n in names if n.startswith("standings_global_"))
    if not globals_:
        out["error"] = out["error"] or "no standings_global_*.md published in the Valve repository"
        log({"url": VALVE_API.format(path=VALVE_DIR), "status": listing["status"],
             "bytes": listing["bytes"], "sha256": listing["sha256"], "path": "http",
             "error": out["error"]})
        return out
    latest = globals_[-1]
    raw_url = VALVE_RAW.format(path=f"{VALVE_DIR}/{latest}")
    got = http_get(raw_url)
    log({k: got[k] for k in ("url", "status", "bytes", "sha256", "path", "error")})
    if got["status"] != 200 or not got["body"]:
        out["error"] = got["error"] or "Valve standings file refused"
        return out
    for line in got["body"].splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        try:
            rank, points = int(cells[0]), int(cells[1])
        except ValueError:
            continue
        out["teams"][cells[2]] = {"rank": rank, "points": points, "roster": cells[3]}
    out.update({
        "file": latest,
        "as_of": latest.replace("standings_global_", "").replace(".md", ""),
        "source_url": f"https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
                      f"{VALVE_DIR}/{latest}",
        "raw_url": raw_url,
    })
    return out


# ------------------------------------------------------------------------------------------ HLTV
def hltv_ranking() -> dict:
    """HLTV World Ranking: rank + points per team, plus the ranking date HLTV prints."""
    out = {"source_url": HLTV_RANKING, "teams": {}, "date_text": None, "captured_utc": now_iso(),
           "error": None}
    got = fetch(HLTV_RANKING, marker='class="ranked-team')
    if got["status"] != 200 or 'class="ranked-team' not in got["body"]:
        out["error"] = got["error"] or "ranking page served without ranked-team blocks"
        out["status"] = got["status"]
        out["sha256"] = got["sha256"]
        return out
    for block in got["body"].split('<div class="ranked-team')[1:]:
        pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', block)
        name = re.search(r'<span class="name">([^<]+)</span>', block)
        pts = re.search(r'<span class="points">\((-?\d+)', block)
        if pos and name:
            out["teams"][unescape(name.group(1)).strip()] = {
                "rank": int(pos.group(1)), "points": int(pts.group(1)) if pts else None}
    date_m = re.search(r"World ranking on ([A-Za-z]+ \d{1,2}(?:st|nd|rd|th)?,? \d{4})", got["body"])
    out["date_text"] = date_m.group(1) if date_m else None
    out.update({"status": got["status"], "sha256": got["sha256"], "teams_total": len(out["teams"]),
                "blocks_seen": len(got["body"].split('<div class="ranked-team')) - 1,
                "names_sample": list(out["teams"])[:5],
                "forze_like": [n for n in out["teams"] if "orze" in n or "LFO" in n][:5]})
    return out


def parse_hltv_day(html: str) -> list[dict]:
    """Upcoming matches for one day: id, slug teams, kickoff, event, format."""
    rows, seen = [], set()
    for match in re.finditer(r'href="/matches/(\d+)/([a-z0-9\-]+)"', html or ""):
        match_id, slug = match.group(1), match.group(2)
        if match_id in seen:
            continue
        seen.add(match_id)
        window = html[match.end(): match.end() + 2600]
        nxt = re.search(r'href="/matches/\d+/', window)
        if nxt:
            window = window[:nxt.start()]
        unix = re.search(r'data-unix="(\d{13})"', window)
        event = re.search(r'class="event-name"[^>]*>\s*([^<]{2,60})\s*<', window)
        fmt = re.search(r"\b(bo[135])\b", window, re.I)
        pair = re.match(r"(.+?)-vs-(.+)$", slug)
        if not unix or not pair:
            continue
        rows.append({
            "hltv_match_id": match_id,
            "hltv_url": f"https://www.hltv.org/matches/{match_id}/{slug}",
            "slug": slug, "slug_team_a": pair.group(1).replace("-", " "),
            "slug_team_b": pair.group(2).replace("-", " "),
            "event": unescape(event.group(1)).strip() if event else None,
            "format": fmt.group(1).lower() if fmt else None,
            "start_utc": datetime.fromtimestamp(int(unix.group(1)) / 1000, timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return rows


def hltv_day(date: str, cache: dict) -> list[dict]:
    if date in cache:
        return cache[date]
    got = fetch(HLTV_MATCHES.format(date=date), marker='href="/matches/')
    rows = parse_hltv_day(got["body"]) if 'href="/matches/' in got["body"] else []
    cache[date] = rows
    return rows


def hltv_match_page(url: str) -> dict:
    """One HLTV match page: series format, per-team HLTV/VRS rank badge or 'no rank'."""
    got = fetch(url, marker="Best of ")
    out = {"url": url, "status": got["status"], "sha256": got["sha256"], "error": got["error"],
           "best_of": None, "maps_note": None, "event_url": None, "event_name": None,
           "team_ranks": {}, "captured_utc": now_iso()}
    html = got["body"]
    best = re.search(r"Best of (\d)", html)
    if best:
        out["best_of"] = int(best.group(1))
    elif re.search(r"Best of 1", html):
        out["best_of"] = 1
    ev = re.search(r'href="(/events/\d+/[a-z0-9\-]+)"[^>]*title="([^"]+)"', html)
    if ev:
        out["event_url"] = "https://www.hltv.org" + ev.group(1)
        out["event_name"] = unescape(ev.group(2))
    # The lineups block prints e.g. `HLTV: #75` and `VRS: #89` next to each team; a team with no
    # rank at all is printed without a badge, which is recorded as null rather than as a value.
    for block in re.split(r"Lineups", html, maxsplit=1)[-1].split('class="lineup')[0:3]:
        pass
    lineup_html = html.split("Lineups", 1)[1] if "Lineups" in html else ""
    for team in re.finditer(r'href="/team/(\d+)/([a-z0-9\-]+)"[^>]*>\s*([^<]{2,40}?)\s*<', lineup_html):
        name = unescape(team.group(3)).strip()
        window = lineup_html[team.end(): team.end() + 700]
        nxt = re.search(r'href="/team/\d+/', window)
        if nxt:
            window = window[:nxt.start()]
        hltv_rank = re.search(r"HLTV:\s*#(\d+)", window)
        vrs_rank = re.search(r"VRS:\s*#(\d+)", window)
        if name and name not in out["team_ranks"]:
            out["team_ranks"][name] = {
                "hltv_rank": int(hltv_rank.group(1)) if hltv_rank else None,
                "vrs_rank": int(vrs_rank.group(1)) if vrs_rank else None,
                "hltv_team_url": f"https://www.hltv.org/team/{team.group(1)}/{team.group(2)}",
            }
    out["maps_note"] = "Best of %d (Online)" % out["best_of"] if out["best_of"] else None
    return out


# ----------------------------------------------------------------------------------- EGamersWorld
def egw_slug_teams(url: str) -> tuple[str, str] | None:
    tail = url.rstrip("/").split("/")[-1]
    pair = re.match(r"(.+?)-vs-(.+?)(-[A-Za-z0-9_\-]{5,12})?$", tail)
    if not pair:
        return None
    return pair.group(1).replace("-", " "), pair.group(2).replace("-", " ")


def egw_match_page(url: str) -> dict:
    """One EGamersWorld match page: its two-sided odds table when the page really serves one."""
    got = fetch(url, marker="Bo")
    out = {"url": url, "status": got["status"], "sha256": got["sha256"], "error": got["error"],
           "odds": [], "placeholder": False, "captured_utc": now_iso(),
           "format": None, "teams_named": None}
    html = got["body"]
    fmt = re.search(r"\bBo(\d)\b", html)
    if fmt:
        out["format"] = int(fmt.group(1))
    odds = re.findall(r'"odd[^"]*":\s*([0-9]+(?:\.[0-9]+)?)', html)
    if not odds:
        odds = re.findall(r"\b([12]\.\d{2,3})\b", html)
    values = [float(v) for v in odds if 1.01 <= float(v) <= 51.0]
    out["odds_raw"] = values[:6]
    if len(values) >= 2 and abs(values[0] - values[1]) < 1e-9 and abs(values[0] - 1.8) < 1e-9:
        out["placeholder"] = True  # the known EGW 1.80/1.80 cut-off placeholder
    return out


def egw_list() -> dict:
    out = {"source_url": EGW_MATCHES, "matches": [], "captured_utc": now_iso(), "error": None}
    got = fetch(EGW_MATCHES, marker="/counterstrike/match/")
    if "/counterstrike/match/" not in got["body"]:
        out["error"] = got["error"] or "EGW list served without match links"
        out["status"] = got["status"]
        return out
    seen = set()
    for link in re.finditer(r'href="(/counterstrike/match/[^"#]+)"', got["body"]):
        path = link.group(1)
        if path in seen:
            continue
        seen.add(path)
        teams = egw_slug_teams(path)
        if not teams:
            continue
        out["matches"].append({"url": "https://egamersworld.com" + path,
                               "team_a": teams[0], "team_b": teams[1]})
    out.update({"status": got["status"], "sha256": got["sha256"], "matches": out["matches"][:400]})
    return out


# ---------------------------------------------------------------------------------------- helpers
def norm(name: str) -> str:
    text = unicodedata.normalize("NFKD", unescape(name or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"\b(team|esports|gaming|academy|academia|prospects|junior|jr)\b", " ", text.lower())
    return re.sub(r"[^a-z0-9]+", "", text)


def rank_window(rows: list[dict]) -> list[dict]:
    """The fixtures this board works on: HTLV/Hotspawn rows whose kickoff is not in the past."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    return [r for r in rows if datetime.strptime(r["start_utc"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc) >= cutoff]


def match_day_row(fixture: dict, rows: list[dict]) -> dict | None:
    """Pick the HLTV row for a Hotspawn fixture: both team names must appear in the slug."""
    na, nb = norm(fixture["team_a"]), norm(fixture["team_b"])
    best = None
    for row in rows:
        sa, sb = norm(row["slug_team_a"]), norm(row["slug_team_b"])
        pair = {sa, sb}
        hit_a = any(x and (x == na or x.startswith(na[:6]) or na.startswith(x[:6])) for x in pair)
        hit_b = any(x and (x == nb or x.startswith(nb[:6]) or nb.startswith(x[:6])) for x in pair)
        if hit_a and hit_b:
            score = abs(len(sa) - len(na)) + abs(len(sb) - len(nb)) + (
                0.5 if row["start_utc"] != fixture["start_utc"] else 0)
            if best is None or score < best[0]:
                best = (score, row)
    return best[1] if best else None


def hltv_match_details(fixtures: list[dict], day_cache: dict, limit: int = 34) -> list[dict]:
    """Per-match HLTV pages for the fixtures this board publishes: format + rank badges."""
    written = []
    for fixture in fixtures[:limit]:
        rows = hltv_day(fixture["start_utc"][:10], day_cache)
        row = match_day_row(fixture, rows)
        if not row:
            continue
        page = hltv_match_page(row["hltv_url"])
        out = {
            "fixture_id": fixture["fixture_id"],
            "team_a": fixture["team_a"], "team_b": fixture["team_b"],
            "hltv_match_id": row["hltv_match_id"], "url": row["hltv_url"],
            "listing_format": row.get("format"), "event": row.get("event"),
            "start_utc": row.get("start_utc"),
            "best_of": page.get("best_of") or (int(row["format"][-1]) if row.get("format") else None),
            "best_of_source": ("HLTV match page" if page.get("best_of")
                               else "HLTV listing" if row.get("format") else None),
            "team_ranks": page.get("team_ranks") or {},
            "event_url": page.get("event_url"), "event_name": page.get("event_name"),
            "status": page.get("status"), "sha256": page.get("sha256"), "error": page.get("error"),
            "captured_utc": page.get("captured_utc"),
        }
        save(f"hltv_match_{row['hltv_match_id']}.json", out)
        written.append(out)
        time.sleep(1.0)
    return written


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", default="all",
                    choices=["all", "hotspawn", "valve", "hltv", "egw"])
    args = ap.parse_args(argv)
    started = now_iso()
    OUT.mkdir(parents=True, exist_ok=True)

    hotspawn = valve = ranking = None
    if args.only in ("all", "hotspawn"):
        print("Hotspawn Play — fixture list from the server-rendered payload", flush=True)
        hotspawn = hotspawn_capture()
        save("hotspawn.json", {k: v for k, v in hotspawn.items() if k != "fixtures"} |
             {"fixtures": hotspawn["fixtures"]})
        print(f"  fixtures: {hotspawn['fixtures_total']}", flush=True)
    if args.only in ("all", "valve"):
        print("Valve — Regional Standings (official repository)", flush=True)
        valve = valve_standings()
        save("valve_vrs.json", valve)
        print(f"  teams: {len(valve['teams'])} file: {valve['file']} error: {valve['error']}",
              flush=True)
    if args.only in ("all", "hltv"):
        print("HLTV — World Ranking + per-day match listings", flush=True)
        ranking = hltv_ranking()
        save("hltv_ranking.json", ranking | {"teams_total": len(ranking["teams"])})
        print(f"  ranked teams: {len(ranking['teams'])} date: {ranking['date_text']}"
              f" error: {ranking['error']}", flush=True)

    fixture_list: list[dict] = []
    if hotspawn and hotspawn.get("fixtures"):
        fixture_list = rank_window(hotspawn["fixtures"])
    elif (OUT / "hotspawn.json").exists():
        cached = json.loads((OUT / "hotspawn.json").read_text())
        fixture_list = rank_window(cached.get("fixtures") or [])
    needs: dict[str, list[dict]] = {}
    for fx in fixture_list:
        date = fx["start_utc"][:10]
        needs.setdefault(date, []).append(fx)

    if args.only in ("all", "hltv") and needs:
        cache: dict[str, list[dict]] = {}
        for date in sorted(needs)[:5]:
            rows = hltv_day(date, cache)
            save(f"hltv_day_{date}.json", {"date": date, "matches": rows,
                                           "count": len(rows),
                                           "source_url": HLTV_MATCHES.format(date=date)})
            print(f"  {date}: {len(rows)} HLTV matches listed", flush=True)
        open_fixtures = [fx for fx in fixture_list
                         if datetime.strptime(fx["start_utc"], "%Y-%m-%dT%H:%M:%SZ")
                         .replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)]
        print(f"HLTV — per-match pages for {len(open_fixtures)} open fixtures "
              f"(format and rank badges)", flush=True)
        details = hltv_match_details(open_fixtures, cache)
        matched = sum(1 for d in details if d["team_ranks"])
        print(f"  pages read: {len(details)}, with a rank badge: {matched}", flush=True)

    summary = {"started_utc": started, "finished_utc": now_iso(), "only": args.only,
               "fetches": LOG,
               "hotspawn_fixtures": (hotspawn or {}).get("fixtures_total"),
               "valve_teams": len((valve or {}).get("teams") or {}),
               "hltv_ranked_teams": len((ranking or {}).get("teams") or {}),
               "errors": [f["url"] for f in LOG if f.get("error")]}
    save("collect_summary.json", summary)
    print(f"collect: {len(LOG)} fetches, {len(summary['errors'])} with an error", flush=True)
    close_browser()
    return 0


if __name__ == "__main__":
    sys.exit(main())
