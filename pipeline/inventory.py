#!/usr/bin/env python3
"""Build the complete Hotspawn Pick'em fixture inventory.

Source of record: the server-rendered Pick'em lobby pages on play.hotspawn.com
(lobby, cs2-pickems, lol-pickems, thp-pickems, tournament pages). Every fixture row keeps
the Hotspawn match URL it came from, so each row is independently checkable.

Times: the Pick'em cards render a countdown ("Locks in HH:MM:SS", "Nd Nh Nm", or
"Locking soon") next to a *locale-rendered* wall-clock time. The countdown is the
timezone-independent truth, and picks lock 5 minutes before the scheduled start
(source: https://play.hotspawn.com/how-it-works), so:

    utc_start_estimate = snapshot_utc + locks_in + 5 minutes

The wall-clock string is kept verbatim as evidence and never used for scheduling.

Outputs (committed):
  inventory/fixtures.json, inventory/fixtures.csv, inventory/meta.json
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

UA = "Mozilla/5.0 (compatible; MaltaProj1-research/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1)"

PAGES = [
    ("CS2", "all-games-lobby", "https://play.hotspawn.com/lobby"),
    ("CS2", "cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("LoL", "lol-pickems", "https://play.hotspawn.com/lol-pickems"),
    ("Thunderpick", "thp-pickems", "https://play.hotspawn.com/thp-pickems"),
    ("CS2", "twc-tournament-page", "https://play.hotspawn.com/tournaments/thunderpick-world-championships"),
]

CARD_SPLIT = re.compile(r"<app-pickem-vs-card\b")
DATE_RE = re.compile(r'class="vs-card-date">\s*([^<]+?)\s*</div>')
TOUR_RE = re.compile(r'class="vs-card-tournament">\s*([^<]+?)\s*</div>')
CHIP_RE = re.compile(r'class="match-card-meta-chip match-card-meta-chip--(\w+)"[^>]*title="([^"]*)"')
COUNTDOWN_RE = re.compile(r'class="vs-card-countdown-value">\s*([^<]*?)\s*</div>')
LINK_RE = re.compile(r'href="(https://www\.hotspawn\.com/matches/[^"#]+?-(\d{5,9}))"')
TEAM_RE = re.compile(r'class="vs-card-team-name">\s*([^<]+?)\s*</div>')
PICKED_RE = re.compile(r'class="vs-card-team-picked">\s*(\d+)% picked')
H2_RE = re.compile(r'<h2[^>]*>\s*([^<]+?)\s*</h2>')


def fetch(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read()
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc).encode()


def parse_countdown(value: str) -> int | None:
    value = value.strip()
    if not value or "locking" in value.lower():
        return None
    d = re.search(r"(\d+)\s*d", value)
    h = re.search(r"(\d+)\s*h", value)
    m = re.search(r"(\d+)\s*m", value)
    if d or h or m:
        return int(d.group(1) if d else 0) * 86400 + int(h.group(1) if h else 0) * 3600 + int(m.group(1) if m else 0) * 60
    parts = value.split(":")
    if len(parts) == 3 and all(p.strip().isdigit() for p in parts):
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return None


def sections_by_offset(html: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group(1)) for m in H2_RE.finditer(html)]


def parse_page(game: str, page_label: str, url: str) -> tuple[list[dict], dict]:
    status, body = fetch(url)
    snapshot = datetime.now(timezone.utc)
    html = body.decode("utf-8", errors="replace")
    page_meta = {
        "page": page_label,
        "url": url,
        "status": status,
        "bytes": len(body),
        "sha256": hashlib.sha256(body).hexdigest()[:16] if status else None,
        "snapshot_utc": snapshot.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cards_found": 0,
    }
    if status != 200:
        return [], page_meta
    chunks = CARD_SPLIT.split(html)
    sections = sections_by_offset(html)
    fixtures: list[dict] = []
    for chunk in chunks[1:]:
        section = None
        for offset, name in sections:
            if name in ("Closing Soon", "Upcoming"):
                section = name
        date = DATE_RE.search(chunk)
        tour = TOUR_RE.search(chunk)
        link = LINK_RE.search(chunk)
        if not (date and tour and link):
            continue
        chips = {key: value for key, value in CHIP_RE.findall(chunk)}
        cd = COUNTDOWN_RE.search(chunk)
        cd_text = cd.group(1) if cd else ""
        locks_in = parse_countdown(cd_text)
        teams = [t.strip() for t in TEAM_RE.findall(chunk)]
        picked = [int(p) for p in PICKED_RE.findall(chunk)]
        utc_start = (
            (snapshot + timedelta(seconds=locks_in + 300)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if locks_in is not None
            else None
        )
        fixtures.append(
            {
                "hotspawn_match_id": link.group(2),
                "hotspawn_url": link.group(1),
                "game": game,
                "page": page_label,
                "page_url": url,
                "snapshot_utc": page_meta["snapshot_utc"],
                "section": section,
                "display_date_local": date.group(1),
                "tournament": tour.group(1),
                "points": chips.get("points", "").replace("Points available: ", ""),
                "tier": chips.get("tier", "").replace("Tier: ", ""),
                "stage": (chips.get("stage") or "").replace("Stage: ", ""),
                "multiplier": (chips.get("multiplier") or "").replace("Multiplier: ", ""),
                "locks_in_text": cd_text,
                "locks_in_seconds": locks_in,
                "utc_start_estimate": utc_start,
                "team_a": teams[0] if len(teams) > 0 else None,
                "team_b": teams[1] if len(teams) > 1 else None,
                "hotspawn_pick_pct_a": picked[0] if len(picked) > 0 else None,
                "hotspawn_pick_pct_b": picked[1] if len(picked) > 1 else None,
            }
        )
    page_meta["cards_found"] = len(fixtures)
    print(f"{page_label}: {len(fixtures)} cards (status {status})")
    return fixtures, page_meta


def main() -> None:
    all_rows: list[dict] = []
    metas: list[dict] = []
    for game, label, url in PAGES:
        rows, meta = parse_page(game, label, url)
        all_rows.extend(rows)
        metas.append(meta)
        time.sleep(0.5)

    # De-duplicate on Hotspawn match id; keep every source page reference.
    merged: dict[str, dict] = {}
    for row in all_rows:
        key = row["hotspawn_match_id"]
        if key not in merged:
            row = dict(row)
            row["source_pages"] = [row["page_url"]]
            merged[key] = row
        else:
            merged[key].setdefault("source_pages", []).append(row["page_url"])
    fixtures = sorted(merged.values(), key=lambda r: (r["utc_start_estimate"] or "9999", r["tournament"]))

    Path("inventory").mkdir(parents=True, exist_ok=True)
    Path("inventory/fixtures.json").write_text(
        json.dumps({"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "source": "play.hotspawn.com Pick'em lobby pages",
                    "fixtures": fixtures}, indent=1),
        encoding="utf-8",
    )
    cols = [
        "hotspawn_match_id", "game", "utc_start_estimate", "display_date_local", "tournament",
        "tier", "points", "stage", "multiplier", "team_a", "team_b",
        "hotspawn_pick_pct_a", "hotspawn_pick_pct_b", "locks_in_text", "section",
        "hotspawn_url", "page", "snapshot_utc",
    ]
    with open("inventory/fixtures.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(fixtures)

    summary = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": metas,
        "fixture_count": len(fixtures),
        "by_game": {g: sum(1 for r in fixtures if r["game"] == g) for g in sorted({r["game"] for r in fixtures})},
        "by_tournament": {},
    }
    for row in fixtures:
        summary["by_tournament"].setdefault(row["tournament"], 0)
        summary["by_tournament"][row["tournament"]] += 1
    Path("inventory/meta.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    print(f"TOTAL fixtures: {len(fixtures)}")
    for game, count in summary["by_game"].items():
        print(f"  {game}: {count}")
    for tour, count in sorted(summary["by_tournament"].items(), key=lambda kv: -kv[1]):
        print(f"  {count:>3}  {tour[:70]}")
    # Fail loudly if a page yielded nothing: that means the parser or the source changed.
    empty = [m["page"] for m in metas if m["status"] == 200 and m["cards_found"] == 0]
    if empty or any(m["status"] != 200 for m in metas):
        problems = [m["page"] for m in metas if m["status"] != 200 or m["cards_found"] == 0]
        Path("inventory/errors.txt").write_text("pages without cards: " + ", ".join(problems), encoding="utf-8")
        raise SystemExit(f"inventory incomplete, pages without cards: {problems}")


if __name__ == "__main__":
    main()
