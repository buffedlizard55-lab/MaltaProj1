#!/usr/bin/env python3
"""Hotspawn Pick'em inventory == COMPLETE slate (runs on GitHub Actions).

Why this works
--------------
play.hotspawn.com is an Angular app rendered on the server.  Besides the HTML
cards, every page embeds the *complete* data it was rendered from in
`<script id="ng-state" type="application/json">`.  That state carries, for every
match on the board:

    id, competition_name, sport_alias, status,
    scheduled_start_time (epoch ms, UTC), lock_time, lock_offset_sec,
    offered_points, base_points, tier, stage, points_breakdown,
    participants0/1 name + picked percent

So the "full list" does not need paging, an API key or a browser: it is the
server's own payload.  Card counting is kept as a cross-check (cards rendered vs
rows in the state), and the header/filter counters are recorded as published
totals.

Outputs
  data/pickem_inventory.json   complete slate + page metadata + counters
  data/pickem_inventory.csv    flat review file
  evidence/*.html.gz           raw bodies (temporary evidence, deleted at release)
No login, no evasion, no private API: only the public Pick'em pages.
"""
from __future__ import annotations

import csv
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

PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
]

CARD_BLOCK = re.compile(r"<app-pickem-vs-card\b.*?</app-pickem-vs-card>", re.S | re.I)
STATE_SCRIPT = re.compile(r'<script id="ng-state"[^>]*>(.*?)</script>', re.S)
COUNTER_RE = re.compile(r"Tier ([A-Z][a-z]+)(?: tiers)? \((\d+)\)|Tournament [^()]*\((\d+)\)")


def fetch(url: str, timeout: int = 40) -> dict:
    req = Request(url, headers=HEADERS)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(15_000_000)
            return {"url": url, "status": resp.status, "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest()[:16],
                    "fetched_utc": stamp, "body": body}
    except HTTPError as exc:
        return {"url": url, "status": exc.code, "error": f"HTTPError {exc.code}",
                "fetched_utc": stamp, "body": b""}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}",
                "fetched_utc": stamp, "body": b""}


def match_rows(state: dict) -> list[dict]:
    """Every match list embedded in the page state (there can be one per sport/tab)."""
    rows = []
    for node in state.values():
        payload = node.get("b") if isinstance(node, dict) else None
        if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "competition_name" in payload[0]:
            rows.extend(payload)
    return rows


def ms(value) -> str | None:
    try:
        return datetime.fromtimestamp(int(value) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def counters(text: str) -> dict:
    """Header/filter counters as published on the page (evidence of the advertised totals)."""
    out = {}
    week = re.search(r"(\d+)\s+matches this week", text)
    if week:
        out["matches_this_week"] = int(week.group(1))
    all_tiers = re.search(r"All tiers \((\d+)\)", text)
    if all_tiers:
        out["all_tiers_count"] = int(all_tiers.group(1))
    tiers = dict(re.findall(r"\bTier\s+([SABC]) \((\d+)\)", text))
    if tiers:
        out["tier_counts"] = {k: int(v) for k, v in tiers.items()}
    all_tourn = re.search(r"All tournaments \((\d+)\)", text)
    if all_tourn:
        out["all_tournaments_count"] = int(all_tourn.group(1))
    tourn = re.findall(r"([A-Za-z0-9][A-Za-z0-9 :#&.'’\-]{3,60}?) \((\d+)\)", text)
    if tourn:
        out["tournament_counts_raw"] = [[t.strip(), int(c)] for t, c in tourn][:40]
    resets = re.search(r"Resets in ([0-9dhm ]+)", text)
    if resets:
        out["weekly_reset_in"] = resets.group(1).strip()
    return out


def main() -> None:
    EVID.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    pages, matches, diagnostics = [], {}, {}

    for label, url in PAGES:
        got = fetch(url)
        pages.append({k: v for k, v in got.items() if k != "body"})
        if not got["body"]:
            diagnostics[label] = {"status": got.get("status"), "error": got.get("error")}
            continue
        html = got["body"].decode("utf-8", errors="replace")
        (EVID / f"hotspawn-{label}.html.gz").write_bytes(gzip.compress(got["body"], 9))
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", re.sub(r"<script.*?</script>", " ", html, flags=re.S)))
        state_match = STATE_SCRIPT.search(html)
        state = json.loads(state_match.group(1)) if state_match else {}
        rows = match_rows(state)
        cards = CARD_BLOCK.findall(html)
        for row in rows:
            rec = matches.setdefault(row["id"], {
                "match_id": str(row["id"]),
                "sport": row.get("sport_alias"),
                "competition": row.get("competition_name"),
                "status": row.get("status"),
                "scheduled_start_utc": ms(row.get("scheduled_start_time")),
                "lock_utc": ms(row.get("lock_time")),
                "lock_offset_sec": row.get("lock_offset_sec"),
                "tier": row.get("tier"),
                "stage": row.get("stage"),
                "offered_points": row.get("offered_points"),
                "base_points": row.get("base_points"),
                "points_breakdown": row.get("points_breakdown"),
                "team_a": row.get("participants0_name"),
                "team_b": row.get("participants1_name"),
                "team_a_id": row.get("participants0_id"),
                "team_b_id": row.get("participants1_id"),
                "crowd_pct_a": row.get("participants0_picked_percent"),
                "crowd_pct_b": row.get("participants1_picked_percent"),
                "total_picks": row.get("total_picks"),
                "started_utc": ms(row.get("start_time")),
                "ended_utc": ms(row.get("end_time")),
                "pages": [],
                "source_url": url,
                "snapshot_utc": got["fetched_utc"],
            })
            if label not in rec["pages"]:
                rec["pages"].append(label)
            rec["hotspawn_url"] = f"https://www.hotspawn.com/matches/-{row['id']}"
        diagnostics[label] = {
            "status": got.get("status"), "bytes": got.get("bytes"),
            "state_rows": len(rows), "cards_rendered": len(cards),
            "counters": counters(text),
            "competitions": sorted({r.get("competition_name") for r in rows if r.get("competition_name")}),
        }
        time.sleep(0.6)

    rows_out = sorted(matches.values(), key=lambda m: (m["scheduled_start_utc"] or "", m["match_id"]))
    for rec in rows_out:
        rec["hotspawn_url"] = f"https://www.hotspawn.com/matches/{rec['competition'] or 'match'}-{rec['match_id']}".replace(" ", "-").lower()
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "play.hotspawn.com Pick'em pages — server-rendered Angular state (public pages only)",
        "note": "scheduled_start_utc and lock_utc come from the page's own payload (epoch ms), not from a countdown.",
        "pages": pages,
        "diagnostics": diagnostics,
        "totals": {
            "matches": len(rows_out),
            "cs2": sum(1 for r in rows_out if r["sport"] == "cs2"),
            "lol": sum(1 for r in rows_out if r["sport"] == "lol"),
        },
        "matches": rows_out,
    }
    (DATA / "pickem_inventory.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")

    cols = ["match_id", "sport", "competition", "status", "scheduled_start_utc", "lock_utc", "lock_offset_sec",
            "tier", "stage", "offered_points", "team_a", "team_b", "crowd_pct_a", "crowd_pct_b", "total_picks",
            "started_utc", "ended_utc", "source_url", "hotspawn_url"]
    with open(DATA / "pickem_inventory.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_out)

    (EVID / "parse-diagnostics.json").write_text(json.dumps(diagnostics, indent=1), encoding="utf-8")
    print(json.dumps({"totals": payload["totals"],
                      "per_page": {k: {kk: vv for kk, vv in v.items() if kk in ("state_rows", "cards_rendered")}
                                   for k, v in diagnostics.items()},
                      "advertised": {k: v.get("counters", {}) for k, v in diagnostics.items()}}, indent=1))


if __name__ == "__main__":
    main()
