#!/usr/bin/env python3
"""Post-build check for the a6f05f99 pages (session ``arena/a6f05f99``).

Two jobs, in order of strictness:

1. **Local links.** Every relative ``href`` on every generated page must point at a file that
   exists. This is a hard failure: a page that links to a missing page ships a dead board.
2. **External source links.** Every ``https://`` link is fetched with a short timeout. This is a
   *report*, not a gate — Hotspawn, HLTV and bo3.gg all rate-limit or refuse datacentre clients at
   times, and a refusal says nothing about whether the link was right when the number was read. The
   result is written to ``data/verify.json`` and surfaced on the flagged page.

Nothing here edits the board or invents a value.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, HERE, ensure_dirs, http_get, iso, log, now_utc, write_json  # noqa: E402

PAGES = ["index.html", "picks.html", "twc.html", "unresolved.html", "method.html", "flagged.html"]
HREF = re.compile(r'href="([^"]+)"')
# Links that are templated (per-team HLTV profiles, market pages) rather than fixture-specific.
SKIP_HOSTS = ("polymarket.com/event/",)


def local_links() -> list[dict]:
    """Return one record per broken relative link."""
    broken = []
    for name in PAGES:
        page = HERE / name
        if not page.exists():
            broken.append({"page": name, "href": "(page missing)", "exists": False})
            continue
        for href in HREF.findall(page.read_text(encoding="utf-8")):
            if href.startswith(("http", "mailto:", "//", "#")):
                continue
            target = (HERE / href.split("#")[0]).resolve()
            if not target.exists():
                broken.append({"page": name, "href": href, "exists": False})
    return broken


def external_links(budget_s: float = 120.0, per_url_s: int = 8) -> list[dict]:
    """Fetch a bounded sample of external links. Report only; never raises.

    A refusal is *not* evidence that a link is wrong: Hotspawn, HLTV and bo3.gg all rate-limit or
    refuse datacentre clients. The whole sweep is capped by a wall-clock budget so a slow or
    unreachable source can never stall a scheduled run.
    """
    seen: set[str] = set()
    for name in PAGES:
        page = HERE / name
        if not page.exists():
            continue
        for href in HREF.findall(page.read_text(encoding="utf-8")):
            if not href.startswith("https://") or href in seen:
                continue
            if any(host in href for host in SKIP_HOSTS):
                continue
            seen.add(href)
    deadline = time.monotonic() + budget_s
    results = []
    for url in sorted(seen):
        if time.monotonic() >= deadline:
            results.append({"url": url, "status": None, "error": "skipped: link budget exhausted"})
            continue
        try:
            rec = http_get(url, timeout=per_url_s, retries=0)
            results.append({"url": url, "status": rec["status"], "error": rec.get("error", "")})
        except Exception as exc:  # noqa: BLE001 - a network hiccup must not fail the run
            results.append({"url": url, "status": None, "error": str(exc)[:200]})
    return results


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    local_only = "--local-only" in argv
    ensure_dirs()
    broken = local_links()
    external = [] if local_only else external_links()
    report = {
        "schema": "a6f05f99-verify/1",
        "checked_utc": iso(now_utc()),
        "pages": PAGES,
        "broken_local_links": broken,
        "external_links_checked": len(external),
        "external_links": external,
    }
    write_json(DATA / "verify.json", report)
    reachable = sum(1 for r in external if r["status"] and 200 <= r["status"] < 400)
    log(f"verify: {len(broken)} broken local link(s), "
        f"{reachable}/{len(external)} external links answered 2xx/3xx"
        + (" (external sweep skipped)" if not external else ""))
    for item in broken:
        log(f"  BROKEN {item['page']} -> {item['href']}")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
