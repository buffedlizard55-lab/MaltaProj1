#!/usr/bin/env python3
"""Dump external odds pages + Hotspawn pages for parser development (CI job).

Everything here is a public, unauthenticated GET with an honest UA.
Scratch output is temporary and removed before publication.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = "Mozilla/5.0 (compatible; MaltaProj1-research/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1)"
OUT = Path("pipeline/_scratch/raw")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "hotspawn-lobby.html": "https://play.hotspawn.com/lobby",
    "hotspawn-cs2-pickems.html": "https://play.hotspawn.com/cs2-pickems",
    "hotspawn-lol-pickems.html": "https://play.hotspawn.com/lol-pickems",
    "hotspawn-thp-pickems.html": "https://play.hotspawn.com/thp-pickems",
    "hotspawn-tournament-twc.html": "https://play.hotspawn.com/tournaments/thunderpick-world-championships",
    "bovada-esports.html": "https://www.bovada.lv/sports/esports",
    "bovada-cs2.html": "https://www.bovada.lv/sports/esports/counter-strike",
    "bovada-lol.html": "https://www.bovada.lv/sports/esports/league-of-legends",
    "betonline-esports.html": "https://www.betonline.ag/sportsbook/esports",
    "flashscore-esports.html": "https://www.flashscore.com/esports/",
    "flashscore-cs2.html": "https://www.flashscore.com/esports/counter-strike/",
    "oddspedia-esports.html": "https://oddspedia.com/esports",
    "oddsportal-esports.html": "https://www.oddsportal.com/esports/",
    "hltv-search-galorys.html": "https://www.hltv.org/search?query=Galorys",
    "hltv-search-aurora.html": "https://www.hltv.org/search?query=Aurora",
    "hltv-event-stake-pulse.html": "https://www.hltv.org/events/9223/stake-pulse-beat-iii",
    "hltv-analytics-2399384.html": (
        "https://www.hltv.org/betting/analytics/2399384/9z-vs-aurora-thunderpick-world-championship-2026"
    ),
    "hltv-team-aurora.html": "https://www.hltv.org/team/11861/aurora",
    "hltv-ranking.html": "https://www.hltv.org/ranking/teams",
}

meta = {"dumped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": []}
for name, url in PAGES.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        (OUT / name).write_bytes(body)
        meta["pages"].append({"file": name, "url": url, "status": 200, "bytes": len(body)})
        print(f"{name} {len(body)} bytes")
    except urllib.error.HTTPError as exc:
        meta["pages"].append({"file": name, "url": url, "status": exc.code})
        print(f"{name} HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        meta["pages"].append({"file": name, "url": url, "error": f"{type(exc).__name__}: {exc}"})
        print(f"{name} ERROR {exc}")
(OUT.parent / "dump-meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
