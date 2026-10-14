#!/usr/bin/env python3
"""Temporary structure probe (session arena/198cf31e).

The sandbox cannot download Actions artifacts or read job logs, so this runs inside CI right
after collect.py and writes a small structural report (briefing/PROBE.md) that the workflow
commits back to the branch. It never touches another session's files and is deleted once the
parsers are final.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "data" / "raw"


def load(name):
    p = RAW / f"{name}.json.gz"
    if not p.exists():
        return None
    with gzip.open(p, "rb") as fh:
        return json.loads(fh.read().decode())


def shape(obj, depth=0, maxdepth=3, maxlist=2):
    pad = "  " * depth
    if depth > maxdepth:
        return f"{pad}..."
    if isinstance(obj, dict):
        if not obj:
            return f"{pad}{{}}"
        lines = [f"{pad}{{"]
        for k in list(obj.keys())[:40]:
            lines.append(f"{pad}  {k!r}:")
            lines.append(shape(obj[k], depth + 2, maxdepth, maxlist))
        lines.append(f"{pad}}}  ({len(obj)} keys)")
        return "\n".join(lines)
    if isinstance(obj, list):
        if not obj:
            return f"{pad}[] (0)"
        out = [f"{pad}[{len(obj)} items]"]
        for i, v in enumerate(obj[:maxlist]):
            out.append(f"{pad}  [{i}]")
            out.append(shape(v, depth + 2, maxdepth, maxlist))
        return "\n".join(out)
    s = repr(obj)
    return f"{pad}{type(obj).__name__} {s[:120]}"


def main() -> None:
    out = []
    w = out.append

    for p in sorted(RAW.glob("*.json.gz")):
        w(f"- `{p.name}` {p.stat().st_size} bytes")

    w("\n## capture.json")
    cap = json.loads((HERE / "data" / "capture.json").read_text())
    for src, rec in cap.get("sources", {}).items():
        w(f"- **{src}**: {json.dumps(rec)[:400]}")

    hs = load("hotspawn_fixtures") or {}
    w(f"\n## Hotspawn: {len(hs.get('fixtures', []))} CS2 fixtures")
    w("```json")
    w(json.dumps(hs.get("fixtures", [])[:3], indent=1)[:3000])
    w("```")

    pin = load("pinnacle") or {}
    w(f"\n## Pinnacle: {len(pin.get('matchups', []))} matchups, "
      f"{len(pin.get('moneylines', []))} moneylines")
    leagues = sorted({m.get("league") for m in pin.get("matchups", [])})
    w(f"leagues ({len(leagues)}): {leagues[:60]}")
    w("### sample matchup\n```json")
    w(json.dumps(pin.get("matchups", [])[:2], indent=1)[:1200])
    w("```\n### sample moneyline\n```json")
    w(json.dumps(pin.get("moneylines", [])[:3], indent=1)[:1500])
    w("```")
    # participant ids per matchup are needed to join prices to names
    raw_mu = pin.get("matchups", [])
    if raw_mu:
        w(f"\nmatchup keys: {list(raw_mu[0].keys())}")

    bo3 = load("bo3gg") or {}
    ms = bo3.get("matches", [])
    w(f"\n## bo3.gg: {len(ms)} upcoming CS2 matches, "
      f"{len(bo3.get('team_names', {}))} team names")
    w("### sample matches\n```json")
    w(json.dumps(ms[:2], indent=1)[:4000])
    w("```")
    withq = [m for m in ms if m.get("bet_updates")]
    w(f"\nwith bet_updates: {len(withq)}")
    if withq:
        w("```json")
        w(json.dumps(withq[0].get("bet_updates"), indent=1)[:2000])
        w("```")
    bo_types = {}
    for m in ms:
        bo_types[m.get("bo_type")] = bo_types.get(m.get("bo_type"), 0) + 1
    w(f"bo_type distribution: {bo_types}")

    pm = load("polymarket") or {}
    evs = pm.get("events", [])
    w(f"\n## Polymarket: {len(evs)} open CS2 series events")
    w("```json")
    w(json.dumps(evs[:1], indent=1)[:2500])
    w("```")
    w("titles: " + json.dumps([e.get("title") for e in evs[:40]]))

    vrs = load("valve_vrs") or {}
    w(f"\n## Valve VRS: file={vrs.get('file')} as_of={vrs.get('as_of')} "
      f"rows={len(vrs.get('rows', []))}")
    w("```json")
    w(json.dumps(vrs.get("rows", [])[:3], indent=1)[:800])
    w("```")

    hltv = load("hltv") or {}
    w(f"\n## HLTV: {json.dumps(hltv)}")
    for key in ("world_ranking", "valve_ranking"):
        txt = load(f"hltv_{key}")
        if isinstance(txt, str):
            w(f"- `{key}`: {len(txt)} chars")
            w("```")
            w(txt[:1500].replace("\n\n", "\n"))
            w("```")
            # try to find ranking-team blocks
            import re
            m = re.findall(r'ranking-team[^>]*', txt[:200000])
            w(f"  `ranking-team` occurrences: {len(m)}")
            n = re.findall(r'\((\d+) (?:HLTV|Valve) points\)', txt)
            w(f"  points matches: {len(n)} -> {n[:20]}")

    (HERE / "PROBE.md").write_text("\n".join(out))
    print("PROBE.md written:", len("\n".join(out)), "chars")


if __name__ == "__main__":
    main()
