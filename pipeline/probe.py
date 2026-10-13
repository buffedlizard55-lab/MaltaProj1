#!/usr/bin/env python3
"""Probe public, unauthenticated pages needed for the MaltaProj1 project.

Runs on a GitHub Actions runner (full internet). The agent sandbox cannot reach
these hosts directly, so this job is the project's network worker.

It performs ordinary GET requests with an honest User-Agent, records status codes,
sizes and small machine-readable summaries, and uploads raw bodies as run artifacts
(never committed to the repository). It does not log in, submit forms, place wagers,
or touch private APIs.

Outputs:
  pipeline/probe/summary.json      <- committed (small, evidence)
  pipeline/probe/raw/**            <- uploaded as artifact only (git-ignored)
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = (
    "MaltaProj1-research/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1; "
    "public-page read-only audit for a pick'em line-analysis dashboard)"
)
RAW = Path("pipeline/probe/raw")
RAW.mkdir(parents=True, exist_ok=True)
SUMMARY_PATH = Path("pipeline/probe/summary.json")

HOTSPAWN_PAGES = {
    "lobby": "https://play.hotspawn.com/lobby",
    "cs2-pickems": "https://play.hotspawn.com/cs2-pickems",
    "lol-pickems": "https://play.hotspawn.com/lol-pickems",
    "thp-pickems": "https://play.hotspawn.com/thp-pickems",
    "cs2-thunderpick-tournament": "https://play.hotspawn.com/tournaments/thunderpick-world-championships",
    "cs2-pickems-page2": "https://play.hotspawn.com/cs2-pickems?page=2",
    "cs2-pickems-offset26": "https://play.hotspawn.com/cs2-pickems?offset=26",
    "cs2-pickems-limit200": "https://play.hotspawn.com/cs2-pickems?limit=200",
    "cs2-pickems-all": "https://play.hotspawn.com/cs2-pickems?show=all",
    "lol-pickems-page2": "https://play.hotspawn.com/lol-pickems?page=2",
}

ODDS_PAGES = {
    "egw-cs2-matches": "https://egamersworld.com/counterstrike/matches",
    "egw-cs2-matches-tomorrow": "https://egamersworld.com/counterstrike/matches?date=tomorrow",
    "egw-lol-matches": "https://egamersworld.com/lol/matches",
    "egw-tp-event": "https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H",
    "hltv-matches": "https://www.hltv.org/matches",
    "hltv-results": "https://www.hltv.org/results",
    "hltv-analytics-sample": (
        "https://www.hltv.org/betting/analytics/2399384/"
        "9z-vs-aurora-thunderpick-world-championship-2026"
    ),
    "pinnacle-esports": "https://www.pinnacle.com/en/esports/matchups",
    "thunderpick-esports": "https://thunderpick.io/sports/esports",
}

API_CANDIDATES = [
    "/api/lobby",
    "/api/matches",
    "/api/pickems",
    "/api/fixtures",
    "/api/events",
    "/api/tournaments",
    "/api/v1/matches",
    "/api/v1/events",
    "/api/matches?game=cs2",
    "/api/events?game=cs2",
]

TOP_LEVEL_JSON_HINTS = re.compile(r'"buildId"\s*:\s*"([^"]+)"')
MATCH_LINK_RE = re.compile(r"hotspawn\.com/matches/([a-z0-9\-]+)-(\d{6,8})", re.I)
SCRIPT_SRC_RE = re.compile(r'<script[^>]+src="([^"]+)"', re.I)
HINT_RE = re.compile(r'(?:https?://[^\s"\'<>`\\]{6,200}|/api/[A-Za-z0-9_\-/?=.&%+]{2,160})')


def fetch(url: str, accept: str | None = None) -> tuple[int, bytes, str, str]:
    """Return (status, body, final_url, content_type). Never raises for HTTP errors."""
    headers = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.status, resp.read(12_000_000), resp.url, resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(200_000)
        except Exception:
            body = b""
        return exc.code, body, url, exc.headers.get("content-type", "") if exc.headers else ""
    except Exception as exc:  # DNS, TLS, timeout
        return 0, f"{type(exc).__name__}: {exc}".encode(), url, ""


def save(label: str, body: bytes, suffix: str) -> str:
    name = f"{label}.{suffix}"
    (RAW / name).write_bytes(body)
    return str(RAW / name)


def summarise_hotspawn(label: str, url: str) -> dict:
    status, body, final_url, ctype = fetch(url)
    text = body.decode("utf-8", errors="replace")
    ids = {m.group(2) for m in MATCH_LINK_RE.finditer(text)}
    scripts = SCRIPT_SRC_RE.findall(text)
    entry = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "content_type": ctype,
        "bytes": len(body),
        "match_links": len(MATCH_LINK_RE.findall(text)),
        "distinct_match_ids": len(ids),
        "match_ids": sorted(ids, key=int)[:200],
        "script_count": len(scripts),
        "has_next_data": "__NEXT_DATA__" in text or "self.__next_f" in text,
        "build_id": (TOP_LEVEL_JSON_HINTS.search(text).group(1) if TOP_LEVEL_JSON_HINTS.search(text) else None),
        "show_more_hits": len(re.findall(r"(?i)show (?:more|all)|load more|view more", text)),
        "raw_file": save(label, body, "html") if status else None,
    }
    print(json.dumps({k: v for k, v in entry.items() if k != "match_ids"}, ensure_ascii=False), flush=True)
    return entry


def probe_apis(entries: list[dict]) -> list[dict]:
    """Try discovery of public JSON endpoints; record only status/shape, no guessing of data."""
    results: list[dict] = []
    candidates = list(API_CANDIDATES)
    for entry in entries:
        build = entry.get("build_id")
        if build:
            candidates += [
                f"/_next/data/{build}/lobby.json",
                f"/_next/data/{build}/cs2-pickems.json",
                f"/_next/data/{build}/lol-pickems.json",
                f"/_next/data/{build}/index.json",
            ]
    seen = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        url = "https://play.hotspawn.com" + path
        status, body, _, ctype = fetch(url, accept="application/json,text/html;q=0.8")
        head = body[:400].decode("utf-8", errors="replace")
        results.append(
            {
                "path": path,
                "status": status,
                "content_type": ctype,
                "bytes": len(body),
                "looks_like_json": head.lstrip()[:1] in "{[" and "json" in (ctype or "").lower(),
                "head": head if status and status < 400 else head[:120],
            }
        )
        print(json.dumps({"api": path, "status": status, "ctype": ctype, "bytes": len(body)}), flush=True)
        time.sleep(0.3)
    return results


def probe_odds(label: str, url: str) -> dict:
    status, body, final_url, ctype = fetch(url)
    text = body.decode("utf-8", errors="replace")
    decimal_odds = re.findall(r"\b([1-9]\.\d{2,3})\b", text)
    entry = {
        "url": url,
        "final_url": final_url,
        "status": status,
        "content_type": ctype,
        "bytes": len(body),
        "final_url_host": urllib.parse.urlparse(final_url).hostname,
        "decimal_like_numbers": len(decimal_odds),
        "text_head": re.sub(r"\s+", " ", text[:300]),
    }
    if status:
        entry["raw_file"] = save(label, body, "html")
    print(json.dumps(entry, ensure_ascii=False)[:900], flush=True)
    return entry


def project_script_hints(entries: list[dict]) -> list[dict]:
    """Fetch a few first-party JS bundles and mine them for public endpoint hints."""
    hints: list[dict] = []
    for entry in entries:
        if not entry.get("status"):
            continue
        html_path = entry.get("raw_file")
        if not html_path or not Path(html_path).exists():
            continue
        html = Path(html_path).read_text(encoding="utf-8", errors="replace")
        base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(entry["url"]))
        scripts = [urllib.parse.urljoin(base, s) for s in SCRIPT_SRC_RE.findall(html)]
        scripts = [s for s in scripts if urllib.parse.urlparse(s).hostname == urllib.parse.urlparse(base).hostname]
        collected: set[str] = set()
        for script in scripts[:12]:
            status, body, _, _ = fetch(script)
            if status != 200:
                continue
            text = body.decode("utf-8", errors="replace")
            for hit in HINT_RE.findall(text):
                low = hit.lower()
                if any(word in low for word in ("api", "match", "event", "odds", "pick", "fixture")):
                    collected.add(hit)
        hints.append({"page": entry["url"], "script_count": len(scripts), "hints": sorted(collected)[:120]})
    return hints


def main() -> None:
    summary: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "runner": os.environ.get("RUNNER_NAME"),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
        "hotspawn": [],
        "api": [],
        "odds": [],
        "script_hints": [],
    }
    for label, url in HOTSPAWN_PAGES.items():
        summary["hotspawn"].append(summarise_hotspawn(label, url))
        time.sleep(0.4)
    summary["api"] = probe_apis(summary["hotspawn"])
    for label, url in ODDS_PAGES.items():
        summary["odds"].append(probe_odds(label, url))
        time.sleep(0.4)
    summary["script_hints"] = project_script_hints(summary["hotspawn"])
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=1)[:4_000_000], encoding="utf-8")
    print("SUMMARY WRITTEN", SUMMARY_PATH)


if __name__ == "__main__":
    main()
