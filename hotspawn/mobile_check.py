#!/usr/bin/env python3
"""Real HTTP phone/tablet check. Browser absence is fatal in CI, never a silent green skip."""
from __future__ import annotations
import functools
import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["index.html"] + [f"hotspawn/{p}.html" for p in ("index", "picks", "strategy", "twc", "unresolved", "all", "flagged", "method")]
SIZES = [(360, 800), (390, 844), (768, 1024)]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("mobile check: browser unavailable; no layout claim made")
        return 1 if os.getenv("REQUIRE_BROWSER") == "1" else 0
    results, failed = [], False
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            for width, height in SIZES:
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                for path in PAGES:
                    errors.clear()
                    response = page.goto(f"http://127.0.0.1:{server.server_port}/{path}", wait_until="networkidle")
                    if path == "index.html":
                        page.wait_for_function("document.querySelector('#open-count').textContent.trim() !== '—'")
                    metric = page.evaluate("""() => ({
                        cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth,
                        h1: document.querySelectorAll('h1').length,
                        primaryTargets: [...document.querySelectorAll('nav a,.filters button,.quick-link,.recheck')].map(e => ({h:e.getBoundingClientRect().height, text:e.textContent.trim()})),
                        tables: [...document.querySelectorAll('table')].filter(t=>t.scrollWidth>t.clientWidth).length
                    })""")
                    bad = not response.ok or metric["sw"] > metric["cw"] + 1 or metric["h1"] != 1 or bool(errors)
                    small = [t for t in metric.pop("primaryTargets") if t["h"] < 43.5]
                    if small: bad = True
                    results.append({"path": path, "width": width, **metric, "small_primary_targets": small, "errors": list(errors), "ok": not bad})
                    if bad: failed = True
                    if width == 390 and path in ("index.html", "hotspawn/picks.html", "hotspawn/twc.html", "hotspawn/unresolved.html"):
                        dest = ROOT / ".arena" / "mobile" / path.replace("/", "-").replace(".html", ".png")
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=str(dest), full_page=True)
                context.close()
            browser.close()
    except Exception as exc:
        failed = True
        results.append({"ok": False, "error": str(exc)})
    finally:
        server.shutdown()
        server.server_close()
    (ROOT / "hotspawn/data/mobile_check.json").write_text(json.dumps({"status": "failed" if failed else "passed", "required_browser": os.getenv("REQUIRE_BROWSER") == "1", "checks": results, "ok": not failed}, indent=1) + "\n")
    for result in results:
        print("mobile:", json.dumps(result))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
