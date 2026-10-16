#!/usr/bin/env python3
"""Phone-layout check: render every page at 390x844 and fail if anything overflows horizontally.

Uses a real headless Chromium when one can be installed; otherwise falls back to a static check that
no element in the markup declares a width wider than the viewport and that every table sits inside a
horizontally scrollable container.  The result is written to data/mobile_check.json.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
PAGES = ["index", "picks", "day3", "review", "unresolved", "flagged", "all", "method"]
WIDTH = 390


def static_check():
    problems = []
    for p in PAGES:
        text = (HERE / f"{p}.html").read_text()
        for m in re.finditer(r'style="[^"]*width:\s*(\d+)px', text):
            if int(m.group(1)) > WIDTH:
                problems.append(f"{p}.html: inline width {m.group(1)}px")
        # every <table> must be inside .scroll or carry the .tbl class (which scrolls)
        for m in re.finditer(r"<table([^>]*)>", text):
            if "tbl" not in m.group(1):
                problems.append(f"{p}.html: <table> without the scrolling .tbl class")
        if "viewport" not in text:
            problems.append(f"{p}.html: no viewport meta tag")
    return problems


def browser_check():
    try:
        from playwright.sync_api import sync_playwright
    except Exception:                                            # noqa: BLE001
        return None
    problems = []
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": WIDTH, "height": 844})
        for p in PAGES:
            pg.goto((HERE / f"{p}.html").as_uri())
            pg.wait_for_timeout(120)
            over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            if over > 1:
                problems.append(f"{p}.html overflows by {over}px at 390px")
        b.close()
    return problems


def main() -> int:
    problems = static_check()
    live = browser_check()
    if live is None:
        mode = "static (no headless browser available)"
    else:
        mode = "headless chromium 390x844"
        problems += live
    json.dump({"status": "pass" if not problems else "fail", "mode": mode,
               "width": WIDTH, "problems": problems},
              open(HERE / "data" / "mobile_check.json", "w"), indent=1)
    print(f"phone check ({mode}): {'pass' if not problems else 'FAIL'}")
    for x in problems:
        print(" -", x)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
