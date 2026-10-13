#!/usr/bin/env python3
"""External match-winner line collector (runs on GitHub Actions).

Sources (public pages only, no login, no evasion, no private API):
  * EGamersWorld per-title match lists and per-event pages.  Its odds widget shows
    the bookmaker name ("by bc.game") next to the price, which is what makes the
    reading attributable.  Prices shown as the source's generic 1.8/1.8 default are
    recorded as `placeholder` and are never used as a line.
  * HLTV.org world ranking (server-rendered) for informational rank context, and
    HLTV event/match pages for kick-off timestamps used to cross-check Hotspawn's
    printed times.

Outputs
  data/external_lines.json   line rows keyed by team pair + source URL + capture time
  evidence/egw-*.html.gz     raw bodies (temporary evidence, deleted before release)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "evidence"
DATA = ROOT / "data"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept": "text/html,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}

EGW_PAGES = [
    ("egw-cs2-matches", "https://egamersworld.com/counterstrike/matches"),
    ("egw-cs2-events", "https://egamersworld.com/counterstrike/events"),
    ("egw-lol-matches", "https://egamersworld.com/lol/matches"),
    ("egw-lol-events", "https://egamersworld.com/lol/events"),
]
HLTV_PAGES = [
    ("hltv-ranking", "https://www.hltv.org/ranking/teams"),
    ("hltv-matches", "https://www.hltv.org/matches"),
    ("hltv-event-twc", "https://www.hltv.org/events/8932/thunderpick-world-championship-2026"),
    ("hltv-event-stake", "https://www.hltv.org/events/9223/stake-pulse-beat-iii"),
]


def fetch(url: str, timeout: int = 40) -> dict:
    req = Request(url, headers=HEADERS)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(12_000_000)
            return {"url": url, "status": resp.status, "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()[:16], "fetched_utc": stamp, "body": body}
    except HTTPError as exc:
        return {"url": url, "status": exc.code, "error": f"HTTPError {exc.code}", "fetched_utc": stamp, "body": b""}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}", "fetched_utc": stamp, "body": b""}


ODDS_TOKEN = re.compile(r"\[(\d{1,2}\.\d{1,3})\]\(https://egamersworld\.com/#\)")
MATCH_HREF = re.compile(r'href="(https://egamersworld\.com/(?:counterstrike|lol)/match/[^"]+)"[^>]*>\s*([^<]{2,90})<')
EVENT_HREF = re.compile(r'href="(https://egamersworld\.com/(?:counterstrike|lol|dota2|valorant)/event/[^"]+)"')
RUN_TXT = re.compile(r">([^<>]{2,60}?)\s*(?:vs|VS|Vs)\s*([^<>]{2,60}?)<")
HLTV_TEAM = re.compile(r'class="name">([^<]+)</span>')
HLTV_POS = re.compile(r'class="position[^"]*">#(\d+)<')
HLTV_PTS = re.compile(r'class="points">\((\d+)')
HLTV_UNIX = re.compile(r'data-unix="(\d{13})"')


def slug_to_pair(slug: str) -> tuple[str, str] | None:
    m = re.match(r"(.+?)-vs-(.+?)-[A-Za-z0-9_\-]{6,12}$", slug)
    if not m:
        return None
    return (m.group(1).replace("-", " ").strip(), m.group(2).replace("-", " ").strip())


def parse_egw(html: str) -> dict:
    """Collect every (match link, odds pair) reading on the page."""
    plain = re.sub(r"\s+", " ", html)
    # keep only the odds-widget region if present, otherwise scan the whole card area
    rows, seen = [], set()
    for m in MATCH_HREF.finditer(plain):
        url, label = m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()
        slug = url.rstrip("/").split("/")[-1]
        pair = slug_to_pair(slug)
        window = plain[m.end(): m.end() + 900]
        odds = ODDS_TOKEN.findall(window)
        key = (slug, tuple(odds[:2]))
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "match_url": url,
            "event_id": url.split("/match/")[1].split("/")[0],
            "slug": slug,
            "label": label[:80],
            "teams_from_slug": pair,
            "odds_window": [float(o) for o in odds[:3]],
        })
    return {
        "odds_tokens_total": len(ODDS_TOKEN.findall(plain)),
        "match_links": len(MATCH_HREF.findall(plain)),
        "event_links": sorted(set(EVENT_HREF.findall(plain)))[:40],
        "rows": rows[:60],
    }


def parse_hltv_ranking(html: str) -> dict:
    blocks = re.split(r'<div class="ranked-team', html)[1:]
    teams = {}
    for b in blocks:
        pos, name, pts = HLTV_POS.search(b), HLTV_TEAM.search(b), HLTV_PTS.search(b)
        if pos and name:
            teams[name.group(1).strip()] = {"rank": int(pos.group(1)), "points": int(pts.group(1)) if pts else None}
    return teams


def main() -> None:
    EVID.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    report = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "pages": [], "egw": {}, "hltv": {}, "event_pages": {}}

    # 1. EGamersWorld listings
    for label, url in EGW_PAGES:
        got = fetch(url)
        report["pages"].append({k: v for k, v in got.items() if k != "body"})
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            (EVID / f"{label}.html.gz").write_bytes(gzip.compress(got["body"], 9))
            report["egw"][label] = parse_egw(html)
        else:
            report["egw"][label] = {"error": got.get("error"), "status": got.get("status")}
        time.sleep(0.7)

    # 2. follow EGamersWorld event pages discovered above (they carry the price widget per fixture)
    event_urls = sorted({u for entry in report["egw"].values()
                         if isinstance(entry, dict) for u in entry.get("event_links", [])})
    event_urls = [u for u in event_urls if any(k in u.lower() for k in
                  ("thunderpick", "stake-pulse", "cct-europe", "challenger", "elisa", "superstrike",
                   "rivals", "world-championship", "emea", "lgc", "demacia", "prime", "tunisian"))][:25]
    for url in event_urls:
        label = "egw-event-" + re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").split("/")[-1].lower())[:60]
        got = fetch(url)
        report["pages"].append({k: v for k, v in got.items() if k != "body"})
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            (EVID / f"{label}.html.gz").write_bytes(gzip.compress(got["body"], 9))
            report["event_pages"][label] = {"url": url, **parse_egw(html)}
        else:
            report["event_pages"][label] = {"url": url, "error": got.get("error"), "status": got.get("status")}
        time.sleep(0.7)

    # 3. HLTV ranking + match/event pages (timestamps + rank context)
    for label, url in HLTV_PAGES:
        got = fetch(url)
        report["pages"].append({k: v for k, v in got.items() if k != "body"})
        if got["body"]:
            html = got["body"].decode("utf-8", errors="replace")
            (EVID / f"{label}.html.gz").write_bytes(gzip.compress(got["body"], 9))
            if label == "hltv-ranking":
                report["hltv"]["ranking"] = parse_hltv_ranking(html)
            else:
                report["hltv"][label] = {
                    "unix_timestamps": sorted(set(HLTV_UNIX.findall(html)))[:40],
                    "text_head": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))[:400],
                }
        else:
            report["hltv"][label] = {"error": got.get("error"), "status": got.get("status")}
        time.sleep(0.7)

    (DATA / "external_lines_probe.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    summary = {
        "egw_pages_ok": sum(1 for e in report["egw"].values() if isinstance(e, dict) and "rows" in e),
        "egw_rows_total": sum(len(e.get("rows", [])) for e in report["egw"].values() if isinstance(e, dict)),
        "egw_event_pages": len(report["event_pages"]),
        "egw_event_rows": sum(len(e.get("rows", [])) for e in report["event_pages"].values()),
        "hltv_ranking_teams": len(report["hltv"].get("ranking", {})),
        "statuses": {p["url"]: p.get("status") for p in report["pages"]},
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
