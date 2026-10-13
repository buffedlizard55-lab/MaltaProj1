#!/usr/bin/env python3
"""Fetch the official inputs for the O-01 own-line model (session arena/91eff436).

Runs on GitHub Actions: the agent sandbox has no general internet access, while Actions
runners do. Each snapshot written under model/input/ records the URL, UTC fetch time,
HTTP status and the SHA-256 of the exact bytes received, so every derived number can be
traced to its source.

Inputs
1. Hotspawn CS2 Pick'em lobby, https://play.hotspawn.com/cs2-pickems
   The page is Angular SSR. Its <script id="ng-state" type="application/json"> TransferState
   carries the full fixture list (the same 85 the lobby filter counts), not only the ~26
   rendered cards. Used for FIXTURE IDENTITY ONLY: the participants*_picked_percent and
   total_picks fields are dropped here, never written to disk, and never used as probability.
2. Valve Regional Standings (official Valve data),
   https://github.com/ValveSoftware/counter-strike_regional_standings
   The newest live/<year>/standings_global_<YYYY_MM_DD>.md at the repository HEAD commit.
3. HLTV World Ranking, https://www.hltv.org/ranking/teams
   Rank, HLTV points, team id and the listed player nicknames. Used for roster
   cross-checks and display only.

A failed fetch keeps the previous snapshot and is recorded in model/input/fetch_log.json.
The build then reports that input's original date, and old data is never relabelled as fresh.
"""
from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INP = ROOT / "input"
# Honest, identifiable User-Agent (no browser impersonation, no bot-evasion).
UA = "Mozilla/5.0 (compatible; MaltaProj1-model/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1)"

HOTSPAWN_URL = "https://play.hotspawn.com/cs2-pickems"
HLTV_URL = "https://www.hltv.org/ranking/teams"
VRS_REPO = "https://github.com/ValveSoftware/counter-strike_regional_standings"

# Hotspawn fields kept. Anything about picks or crowd percentages is deliberately excluded.
KEEP = [
    "id", "competition_id", "competition_name", "sport_alias", "status",
    "scheduled_start_time", "lock_time", "lock_offset_sec", "best_of", "series_format",
    "tier", "stage", "offered_points", "start_time", "end_time",
    "participants0_id", "participants0_name", "participants0_score",
    "participants1_id", "participants1_name", "participants1_score",
]
DROPPED = ["participants0_picked_percent", "participants1_picked_percent", "total_picks"]

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url: str) -> tuple[int, bytes, str]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read(), r.geturl()
    except urllib.error.HTTPError as e:  # keep status for the log
        return e.code, b"", url
    except Exception as e:  # noqa: BLE001
        return 0, str(e).encode()[:300], url


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_hotspawn(log: dict) -> None:
    t = now()
    status, body, final = get(HOTSPAWN_URL)
    entry = {"url": HOTSPAWN_URL, "final_url": final, "fetched_utc": t, "http_status": status,
             "bytes": len(body), "sha256": sha(body) if status == 200 else None}
    if status != 200:
        entry["result"] = "FAILED - previous snapshot kept"
        log["hotspawn"] = entry
        return
    text = body.decode("utf-8", "replace")
    m = re.search(r'<script[^>]*id="ng-state"[^>]*>(.*?)</script>', text, re.S)
    if not m:
        entry["result"] = "FAILED - ng-state TransferState not found; previous snapshot kept"
        log["hotspawn"] = entry
        return
    state = json.loads(m.group(1))
    fixtures, key_used = None, None
    for k, v in state.items():
        b = v.get("b") if isinstance(v, dict) else None
        if isinstance(b, list) and b and isinstance(b[0], dict) and "participants0_name" in b[0]:
            if fixtures is None or len(b) > len(fixtures):
                fixtures, key_used = b, k
    if not fixtures:
        entry["result"] = "FAILED - no fixture list inside TransferState; previous snapshot kept"
        log["hotspawn"] = entry
        return
    week, permalinks = None, {}
    for v in state.values():
        b = v.get("b") if isinstance(v, dict) else None
        if isinstance(b, dict) and "weekStartUtc" in b:
            week = {k: b.get(k) for k in ("weekId", "sportAlias", "status", "weekStartUtc",
                                          "weekEndUtc", "cutoffUtc")}
        if isinstance(b, dict) and isinstance(b.get("permalinks"), dict):
            permalinks.update({str(k): str(u) for k, u in b["permalinks"].items()})
    # Lobby header ("NN matches this week") and filter total, as printed, for cross-checking.
    plain = re.sub(r"<[^>]+>", " ", text)
    plain = htmllib.unescape(re.sub(r"\s+", " ", plain))
    hdr = re.search(r"(\d+)\s*matches this week", plain)
    tot = re.search(r"All tiers \((\d+)\)", plain)
    slim = [{k: f.get(k) for k in KEEP} for f in fixtures]
    out = {
        "source_url": HOTSPAWN_URL, "fetched_utc": t, "http_status": status,
        "html_sha256": entry["sha256"], "transferstate_key": key_used,
        "fixture_count": len(slim), "lobby_header_matches_this_week": int(hdr.group(1)) if hdr else None,
        "lobby_filter_all_tiers": int(tot.group(1)) if tot else None, "pickem_week": week,
        "fields_dropped_on_ingest": DROPPED,
        "note": "Fixture identity only. Hotspawn pick percentages are dropped on ingest and never used.",
        "permalinks": permalinks,
        "fixtures": slim,
    }
    (INP / "hotspawn_cs2_fixtures.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    entry["result"] = f"OK - {len(slim)} fixtures (TransferState key {key_used})"
    log["hotspawn"] = entry


def hltv_candidates() -> list[str]:
    """Generic ranking URL first, then the dated URLs of the two most recent Mondays."""
    today = datetime.now(timezone.utc).date()
    last_monday = today - timedelta(days=today.weekday())
    urls = [HLTV_URL]
    for d in (last_monday, last_monday - timedelta(days=7)):
        urls.append(f"{HLTV_URL}/{d.year}/{MONTHS[d.month - 1]}/{d.day}")
    return urls


def fetch_hltv(log: dict) -> None:
    attempts = []
    status, body, final, t, url = 0, b"", HLTV_URL, now(), HLTV_URL
    for url in hltv_candidates():
        for k in range(2):
            t = now()
            status, body, final = get(url)
            attempts.append({"url": url, "fetched_utc": t, "http_status": status})
            if status == 200:
                break
            time.sleep(4 * (k + 1))
        if status == 200:
            break
    entry = {"url": url, "final_url": final, "fetched_utc": t, "http_status": status,
             "bytes": len(body), "sha256": sha(body) if status == 200 else None, "attempts": attempts}
    text = body.decode("utf-8", "replace") if status == 200 else ""
    blocks = text.split('<div class="ranked-team standard-box">')[1:]
    teams = []
    for b in blocks:
        pos = re.search(r'<span class="position[^"]*">#(\d+)</span>', b)
        name = re.search(r'<span class="name">([^<]+)</span>', b)
        pts = re.search(r'<span class="points">\((\d+)', b)
        tid = re.search(r'href="/team/(\d+)/([^"]+)" class="moreLink"', b)
        nicks = [htmllib.unescape(x) for x in re.findall(r'<div class="rankingNicknames"><span>([^<]+)</span>', b)]
        if pos and name and pts:
            teams.append({"rank": int(pos.group(1)), "name": htmllib.unescape(name.group(1)),
                          "points": int(pts.group(1)),
                          "team_id": tid.group(1) if tid else None, "slug": tid.group(2) if tid else None,
                          "players": nicks})
    dm = re.search(r"World ranking on ([A-Za-z]+) (\d{1,2})(?:st|nd|rd|th)?,? (\d{4})", text)
    if status != 200 or not teams or not dm:
        entry["result"] = "FAILED - previous snapshot kept (HTTP/parse)"
        log["hltv"] = entry
        return
    month, day, year = dm.group(1), int(dm.group(2)), int(dm.group(3))
    mi = MONTHS.index(month.lower()) + 1
    out = {
        "source_url": url,
        "canonical_url": f"https://www.hltv.org/ranking/teams/{year}/{month.lower()}/{day}",
        "ranking_date": f"{year:04d}-{mi:02d}-{day:02d}", "ranking_date_text": dm.group(0),
        "fetched_utc": t, "http_status": status, "html_sha256": entry["sha256"],
        "team_count": len(teams), "teams": teams,
    }
    (INP / "hltv_ranking.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    entry["result"] = f"OK - {len(teams)} teams, {out['ranking_date_text']}"
    log["hltv"] = entry


def fetch_vrs(log: dict) -> None:
    t = now()
    entry = {"url": VRS_REPO, "fetched_utc": t}
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", VRS_REPO, td + "/vrs"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            entry["result"] = "FAILED - git clone: " + r.stderr[-300:]
            log["vrs"] = entry
            return
        repo = Path(td) / "vrs"
        head = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H|%cI|%s"],
                              capture_output=True, text=True).stdout.strip().split("|", 2)
        cands = []
        for p in repo.glob("live/*/standings_global_*.md"):
            m = re.search(r"standings_global_(\d{4})_(\d{2})_(\d{2})\.md$", p.name)
            if m:
                cands.append(("-".join(m.groups()), p))
        if not cands:
            entry["result"] = "FAILED - no live/*/standings_global_*.md found"
            log["vrs"] = entry
            return
        date, path = max(cands)
        rel = path.relative_to(repo).as_posix()
        data = path.read_bytes()
        dest = INP / "vrs"
        dest.mkdir(parents=True, exist_ok=True)
        for old in dest.glob("standings_global_*.md"):
            old.unlink()
        (dest / path.name).write_bytes(data)
        meta = {"repo": VRS_REPO, "commit": head[0], "commit_date": head[1], "commit_message": head[2],
                "path": rel, "standings_date": date, "sha256": sha(data), "fetched_utc": t,
                "blob_url": f"{VRS_REPO}/blob/{head[0]}/{rel}"}
        (dest / "meta.json").write_text(json.dumps(meta, indent=1) + "\n")
        entry.update({"result": f"OK - {rel} @ {head[0][:10]}", "commit": head[0], "path": rel})
        log["vrs"] = entry


def main() -> int:
    INP.mkdir(parents=True, exist_ok=True)
    log: dict = {"run_utc": now()}
    fetch_hotspawn(log)
    fetch_vrs(log)
    fetch_hltv(log)
    (INP / "fetch_log.json").write_text(json.dumps(log, indent=1) + "\n")
    print(json.dumps(log, indent=1))
    # Exit 0 even on partial failure. The build reports each input's real date.
    return 0


if __name__ == "__main__":
    sys.exit(main())
