#!/usr/bin/env python3
"""Probe which candidate odds/rating pages are reachable from the run environment.

Read-only HEAD/GET probes of public pages, with the result written to refresh/logs/ so a blocked
source is visible in the run record instead of silently reducing coverage.
"""
from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import collect  # noqa: E402  (reuses the same fetch paths and records provenance)

CANDIDATES = [
    ("egamersworld-cs2", "https://egamersworld.com/counterstrike/matches"),
    ("egamersworld-match", "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp"),
    ("hltv-ranking", "https://www.hltv.org/ranking/teams"),
    ("hltv-matches", "https://www.hltv.org/matches"),
    ("pinnacle-cs2", "https://www.pinnacle.com/en/esports/games/cs2/matchups/"),
    ("bo3gg-matches", "https://bo3.gg/matches"),
    ("oddsportal-cs2", "https://www.oddsportal.com/esports/counter-strike/"),
    ("vprognoze", "https://vprognoze.ru/"),
    ("polymarket-esports", "https://polymarket.com/esports"),
    ("sofascore-esports", "https://www.sofascore.com/esports"),
    ("flashscore-esports", "https://www.flashscore.com/esports/"),
    ("thunderpick", "https://thunderpick.io/esports/cs2"),
]


def main() -> int:
    lines = []
    for label, url in CANDIDATES:
        got = collect.fetch_html(url)
        text = collect.text_of(got["html"]) if got.get("html") else ""
        odds_tokens = re.findall(r"\b\d{1,2}\.\d{2}\b", text)[:6]
        title = ""
        if got.get("html"):
            m = re.search(r"<title>(.*?)</title>", got["html"], re.S | re.I)
            title = unescape(m.group(1)).strip()[:80] if m else ""
        lines.append(f"{label:20s} path={got.get('path'):8s} status={got.get('status')} "
                     f"bytes={got.get('bytes')} err={got.get('error')} title='{title}' "
                     f"number_tokens={odds_tokens}")
        print(lines[-1], flush=True)
    out = Path("refresh/logs")
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe_sources.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
