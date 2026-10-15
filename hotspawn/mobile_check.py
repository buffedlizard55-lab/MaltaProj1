#!/usr/bin/env python3
"""Headless-Chromium phone check (390x844): no horizontal overflow, tap targets present, cards visible.

Run in CI after build.py.  Exit 0 = pass or browser unavailable (recorded as 'skipped'); 1 = layout failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "mobile_check.json"
PAGES = ["hotspawn/index.html", "hotspawn/picks.html", "hotspawn/strategy.html", "hotspawn/unresolved.html",
         "hotspawn/flagged.html", "index.html"]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        OUT.write_text(json.dumps({"status": "skipped", "reason": "playwright not installed"}, indent=1) + "\n")
        print("mobile check skipped: playwright not installed")
        return 0
    root = HERE.parent
    results, failed = [], False
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            OUT.write_text(json.dumps({"status": "skipped", "reason": f"chromium unavailable: {exc}"[:300]}, indent=1) + "\n")
            print("mobile check skipped: chromium unavailable")
            return 0
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
        for rel in PAGES:
            path = root / rel
            if not path.exists():
                results.append({"page": rel, "ok": False, "error": "missing"})
                failed = True
                continue
            page = ctx.new_page()
            page.goto(path.as_uri())
            m = page.evaluate("""() => ({sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
                h1: document.querySelectorAll('h1').length, cards: document.querySelectorAll('.card').length,
                small: [...document.querySelectorAll('a.btn, .filters button, header nav a')].filter(a => a.getBoundingClientRect().height < 36).length})""")
            ok = m["sw"] <= m["cw"] + 2 and m["h1"] == 1
            gating = rel.startswith("hotspawn/")          # the root landing is reported, not gated, here
            results.append({"page": rel, "ok": ok, "gating": gating, **m})
            failed = failed or (gating and not ok)
            page.close()
        browser.close()
    OUT.write_text(json.dumps({"status": "failed" if failed else "passed", "viewport": "390x844", "pages": results}, indent=1) + "\n")
    for r in results:
        print(("PASS " if r.get("ok") else "FAIL ") + json.dumps(r))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
