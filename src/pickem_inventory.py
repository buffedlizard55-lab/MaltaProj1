#!/usr/bin/env python3
"""Hotspawn Pick'em inventory probe + parser (runs on GitHub Actions).

Purpose
-------
The Pick'em lobby is server-rendered, so the complete set of match cards *that the
server is willing to render* can be read without a browser.  This script:

  1. fetches every public Pick'em / tournament page reachable from the lobby,
  2. stores the raw bodies as gzipped evidence (temporary branch evidence, not the
     final deliverable),
  3. parses every match card it finds into a normalised record, and
  4. writes parse diagnostics so a failed selector shows up immediately.

No login, no evasion, no private API.  Only pages a normal visitor can open.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
EVID = ROOT / "evidence"
DATA = ROOT / "data"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SEED_PAGES = [
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
    ("lol-pickems", "https://play.hotspawn.com/lol-pickems"),
    ("thp-pickems", "https://play.hotspawn.com/thp-pickems"),
]


def fetch(url: str, timeout: int = 40) -> dict:
    started = datetime.now(timezone.utc)
    req = Request(url, headers=HEADERS)
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read(12_000_000)
            return {
                "url": url,
                "status": resp.status,
                "final_url": resp.url,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest()[:16],
                "fetched_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "body": body,
            }
    except HTTPError as exc:
        return {"url": url, "status": exc.code, "error": f"HTTPError {exc.code}",
                "fetched_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "body": b""}
    except Exception as exc:  # noqa: BLE001
        return {"url": url, "status": None, "error": f"{type(exc).__name__}: {exc}",
                "fetched_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"), "body": b""}


def strip_tags(html: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text).strip()


def card_blocks(html: str) -> list[str]:
    """Split the document into Pick'em match-card blocks (plus per-tournament rows)."""
    blocks = []
    for tag in ("app-pickem-vs-card", "app-pickem-match-card", "app-vs-card"):
        pattern = re.compile(rf"<{tag}\b.*?</{tag}>", re.S | re.I)
        blocks.extend(pattern.findall(html))
    if not blocks:  # fallback: anchor every block on the match link itself
        pattern = re.compile(r"(?s)<a[^>]+hotspawn\.com/matches/[^>]+>.{0,4000}?</a>")
        blocks.extend(pattern.findall(html))
    return blocks


TIME_RE = re.compile(r"\b([A-Z][a-z]{2} \d{1,2}, \d{1,2}:\d{2})\b")
MATCH_LINK_RE = re.compile(r"https://www\.hotspawn\.com/matches/([a-z0-9-]+?)-(\d{5,9})\b")
LOCKS_RE = re.compile(r"Locks in\s*(\d{1,2}:\d{2}:\d{2}|\d+d \d+h \d+m)")
POINTS_RE = re.compile(r"(\d+)\s*pts")
TIER_RE = re.compile(r"Tier\s*([SABC])\b")
MULT_RE = re.compile(r"×\s*([\d.]+)")
PCT_RE = re.compile(r"(\d{1,3})\s*%")
TOURN_LINK_RE = re.compile(r"https://play\.hotspawn\.com/tournaments/([a-z0-9-]+)")
IMG_ALT_RE = re.compile(r'<img[^>]+alt="([^"]{2,40})"')


def parse_card(block: str, page: str, snapshot: str) -> dict | None:
    link = MATCH_LINK_RE.search(block)
    if not link:
        return None
    slug, match_id = link.group(1), link.group(2)
    text = strip_tags(block)
    names = [n for n in IMG_ALT_RE.findall(block) if n.lower() not in {"logo", "hotspawn"}]
    times = TIME_RE.findall(text)
    pts = POINTS_RE.search(text)
    tier = TIER_RE.search(text)
    mult = MULT_RE.search(text)
    pcts = [int(p) for p in PCT_RE.findall(text)][:2]
    tourn = TOURN_LINK_RE.search(block)
    return {
        "match_id": match_id,
        "slug": slug,
        "hotspawn_url": f"https://www.hotspawn.com/matches/{slug}-{match_id}",
        "game_page": page,
        "snapshot_utc": snapshot,
        "display_time_raw": times[0] if times else None,
        "locks_in": LOCKS_RE.search(text).group(1) if LOCKS_RE.search(text) else None,
        "points_raw": pts.group(1) + " pts" if pts else None,
        "tier_raw": tier.group(1) if tier else None,
        "multiplier_raw": mult.group(1) if mult else None,
        "tournament_slug": tourn.group(1) if tourn else None,
        "pick_pct_raw": pcts or None,
        "img_alts": names[:4],
        "text_sample": text[:400],
    }


def main() -> None:
    EVID.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    page_meta, matches, diagnostics = [], {}, {}

    seen_pages = list(SEED_PAGES)
    fetched = {}
    for label, url in seen_pages:
        got = fetch(url)
        fetched[label] = got
        page_meta.append({k: v for k, v in got.items() if k != "body"})
        html = got["body"].decode("utf-8", errors="replace")
        snapshot = got["fetched_utc"]
        blocks = card_blocks(html)
        cards = [c for c in (parse_card(b, label, snapshot) for b in blocks) if c]
        for card in cards:
            matches.setdefault(card["match_id"], card).setdefault("pages", []).append(label)
            matches[card["match_id"]].setdefault("pages", []).append(label)
        diagnostics[label] = {
            "status": got.get("status"),
            "bytes": got.get("bytes"),
            "card_blocks": len(blocks),
            "parsed_cards": len(cards),
            "match_links_total": len(set(MATCH_LINK_RE.findall(html))),
            "tournament_slugs_found": sorted(set(TOURN_LINK_RE.findall(html))),
            "text_head": strip_tags(html)[:1500],
            "first_block_text": strip_tags(blocks[0])[:600] if blocks else None,
            "time_strings_seen": sorted(set(TIME_RE.findall(strip_tags(html))))[:20],
        }
        if got.get("body"):
            (EVID / f"hotspawn-{label}.html.gz").write_bytes(gzip.compress(got["body"], 9))

    # follow every tournament page discovered above (they render per-event card lists)
    tourn_slugs = sorted({s for d in diagnostics.values() for s in d["tournament_slugs_found"]})
    for slug in tourn_slugs:
        url = f"https://play.hotspawn.com/tournaments/{slug}"
        got = fetch(url)
        label = f"tournament/{slug}"
        page_meta.append({k: v for k, v in got.items() if k != "body"})
        html = got["body"].decode("utf-8", errors="replace")
        blocks = card_blocks(html)
        cards = [c for c in (parse_card(b, label, got["fetched_utc"]) for b in blocks) if c]
        for card in cards:
            rec = matches.setdefault(card["match_id"], card)
            rec.setdefault("pages", []).append(label)
        diagnostics[label] = {
            "status": got.get("status"), "bytes": got.get("bytes"),
            "card_blocks": len(blocks), "parsed_cards": len(cards),
            "match_links_total": len(set(MATCH_LINK_RE.findall(html))),
            "text_head": strip_tags(html)[:600],
        }
        if got.get("body"):
            (EVID / f"hotspawn-tournament-{slug}.html.gz").write_bytes(gzip.compress(got["body"], 9))
        time.sleep(0.7)

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "play.hotspawn.com Pick'em pages (public, server-rendered)",
        "pages": page_meta,
        "match_count": len(matches),
        "matches": sorted(matches.values(), key=lambda m: m["match_id"]),
    }
    (DATA / "pickem_inventory.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    (EVID / "parse-diagnostics.json").write_text(json.dumps(diagnostics, indent=1), encoding="utf-8")
    print(json.dumps({"matches": len(matches), "pages": len(page_meta),
                      "per_page_cards": {k: v["parsed_cards"] for k, v in diagnostics.items()}},
                     indent=1))


if __name__ == "__main__":
    main()
