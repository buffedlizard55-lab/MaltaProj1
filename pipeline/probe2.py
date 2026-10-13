#!/usr/bin/env python3
"""Second reachability probe: which external (non-Hotspawn) esports odds / data sources can
the CI runner actually read, and what public JSON interfaces do they expose?

Read-only GETs with an honest User-Agent. No login, no wagers, no paywalls, no bot evasion.
Output: pipeline/probe/summary2.json (committed, small).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = (
    "Mozilla/5.0 (compatible; MaltaProj1-research/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1)"
)
BROWSERISH = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
SIMPLE = {"User-Agent": UA, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}

CANDIDATES: dict[str, tuple[str, dict]] = {
    "hltv_event_matches_twc": ("https://www.hltv.org/events/8932/matches", SIMPLE),
    "hltv_event_stake_pulse": ("https://www.hltv.org/events/9223/stake-pulse-beat-iii", SIMPLE),
    "hltv_search": ("https://www.hltv.org/search?query=Aurora", SIMPLE),
    "hltv_ranking": ("https://www.hltv.org/ranking/teams/2026/october/13", SIMPLE),
    "hltv_analytics_sample": (
        "https://www.hltv.org/betting/analytics/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
        SIMPLE,
    ),
    "hltv_matches_browserua": ("https://www.hltv.org/matches", BROWSERISH),
    "sofascore_esports_events": (
        "https://api.sofascore.com/api/v1/sport/esports/scheduled-events/2026-10-13",
        SIMPLE,
    ),
    "sofascore_config": ("https://api.sofascore.com/api/v1/config/all", SIMPLE),
    "oddspedia_esports": ("https://oddspedia.com/esports", BROWSERISH),
    "oddspedia_cs2": ("https://oddspedia.com/esports/counter-strike", BROWSERISH),
    "bo3gg_matches": ("https://bo3.gg/matches", BROWSERISH),
    "flashscore_esports": ("https://www.flashscore.com/esports/", BROWSERISH),
    "betexplorer_esports": ("https://www.betexplorer.com/esports/", BROWSERISH),
    "oddsportal_esports": ("https://www.oddsportal.com/esports/", BROWSERISH),
    "ggbet_cs": ("https://gg.bet/en/counter-strike", BROWSERISH),
    "betano_esports": ("https://www.betano.com/sport/esports/", BROWSERISH),
    "betway_esports": ("https://betway.com/en/sports/grp/esports", BROWSERISH),
    "bovada_esports": ("https://www.bovada.lv/sports/esports", BROWSERISH),
    "betonline_esports": ("https://www.betonline.ag/sportsbook/esports", BROWSERISH),
    "marathonbet_esports": ("https://www.marathonbet.com/en/betting/Esports/", BROWSERISH),
    "sportsbet_esports": ("https://sportsbet.io/sports/esports", BROWSERISH),
    "pinnacle_esports": ("https://www.pinnacle.com/en/esports/matchups", BROWSERISH),
    "egw_cs2_matches_browserua": ("https://egamersworld.com/counterstrike/matches", BROWSERISH),
    "egw_lol_matches_browserua": ("https://egamersworld.com/lol/matches", BROWSERISH),
    "liquipedia_lol": ("https://liquipedia.net/leagueoflegends/Main_Page", BROWSERISH),
    "liquipedia_cs": ("https://liquipedia.net/counterstrike/Main_Page", BROWSERISH),
    "hltv_google_cache_alt": ("https://www.hltv.org/stats", SIMPLE),
}

JSON_CANDIDATES = {
    "hltv_livescore_json": "https://www.hltv.org/js/livematches.json",
    "hltv_scorebot": "https://scorebot-secure.hltv.org/",
    "sofascore_cs2": "https://api.sofascore.com/api/v1/sport/esports/scheduled-events/2026-10-14",
    "oddspedia_api_guess": "https://oddspedia.com/api/v1/sports",
}

HINT_RE = re.compile(
    r"(?:https?://[^\s\"'<>`\\]{6,200}|/(?:api|graphql|_next/data)/[A-Za-z0-9_\-/.?=&%+]{2,160})"
)
SCRIPT_RE = re.compile(r'<script[^>]+src="([^"]+)"', re.I)


def fetch(url: str, headers: dict) -> tuple[int, bytes, str, str]:
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, resp.read(6_000_000), resp.url, resp.headers.get("content-type", "")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(50_000), url, (exc.headers.get("content-type", "") if exc.headers else "")
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}".encode(), url, ""


def check(item: tuple[str, tuple[str, dict]]) -> dict:
    label, (url, headers) = item
    status, body, final, ctype = fetch(url, headers)
    text = body.decode("utf-8", errors="replace")
    entry = {
        "label": label,
        "url": url,
        "status": status,
        "final_url": final,
        "content_type": ctype,
        "bytes": len(body),
        "text_head": re.sub(r"\s+", " ", text[:200]),
        "decimal_odds_like": len(re.findall(r"\b[1-9]?\.\d{2}\b", text)),
        "matchish_links": len(re.findall(r"/(?:match|matches|event)/[A-Za-z0-9\-_/]{3,80}", text)),
        "scripts": [urllib.parse.urljoin(final, s) for s in SCRIPT_RE.findall(text)][:20],
    }
    return entry


def main() -> None:
    out: dict = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sources": [], "json_endpoints": [], "hints": []}
    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check, CANDIDATES.items()))
    out["sources"] = results
    for entry in results:
        print(f"{entry['label'][:32]:34} {entry['status']:>4} {entry['bytes']:>8} {entry['content_type'][:28]:30} dec={entry['decimal_odds_like']:>4} matches={entry['matchish_links']:>4}")
    # Mine JS bundles of a few reachable, odds-relevant hosts for public JSON endpoints.
    interesting = {"bo3gg_matches", "oddspedia_esports", "pinnacle_esports", "betano_esports", "betway_esports", "sportsbet_esports"}
    for entry in results:
        if entry["label"] not in interesting or not entry["scripts"]:
            continue
        host = urllib.parse.urlparse(entry["final_url"]).hostname
        found: set[str] = set()
        for script in entry["scripts"][:8]:
            if urllib.parse.urlparse(script).hostname != host:
                continue
            status, body, _, _ = fetch(script, BROWSERISH)
            if status != 200:
                continue
            for hint in HINT_RE.findall(body.decode("utf-8", errors="replace")):
                low = hint.lower()
                if any(w in low for w in ("api", "graphql", "odds", "match", "sport")):
                    found.add(hint)
        out["hints"].append({"label": entry["label"], "hints": sorted(found)[:150]})
    for label, url in JSON_CANDIDATES.items():
        status, body, final, ctype = fetch(url, SIMPLE)
        head = body.decode("utf-8", errors="replace")[:200]
        out["json_endpoints"].append(
            {"label": label, "url": url, "status": status, "content_type": ctype, "bytes": len(body), "head": head}
        )
        print(f"JSON {label[:28]:30} {status:>4} {ctype[:24]:26} {head[:80]!r}")
    Path("pipeline/probe").mkdir(parents=True, exist_ok=True)
    Path("pipeline/probe/summary2.json").write_text(json.dumps(out, indent=1)[:3_000_000], encoding="utf-8")
    print("WROTE pipeline/probe/summary2.json")


if __name__ == "__main__":
    main()
