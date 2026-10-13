#!/usr/bin/env python3
"""Dump raw public pick'em pages to a scratch folder so the agent session can inspect the
exact server-rendered markup and write a precise parser.

TEMPORARY: pipeline/_scratch/ is deleted before the final pull request. Raw third-party
markup is never part of the published site.
"""
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

USER_AGENT = (
    "MaltaProj1-research/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1; "
    "public-page read-only audit for a pick'em line-analysis dashboard)"
)
OUT = Path("pipeline/_scratch/raw")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = {
    "lobby.html": "https://play.hotspawn.com/lobby",
    "cs2-pickems.html": "https://play.hotspawn.com/cs2-pickems",
    "lol-pickems.html": "https://play.hotspawn.com/lol-pickems",
    "thp-pickems.html": "https://play.hotspawn.com/thp-pickems",
    "tournament-twc.html": "https://play.hotspawn.com/tournaments/thunderpick-world-championships",
}

meta = {"dumped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": []}
for name, url in PAGES.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read()
        (OUT / name).write_bytes(body)
        meta["pages"].append({"file": name, "url": url, "status": 200, "bytes": len(body)})
        print(f"{name} {len(body)} bytes")
    except Exception as exc:  # noqa: BLE001
        meta["pages"].append({"file": name, "url": url, "error": f"{type(exc).__name__}: {exc}"})
        print(f"{name} ERROR {exc}")
(OUT.parent / "dump-meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
