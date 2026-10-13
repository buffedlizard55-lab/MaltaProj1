#!/usr/bin/env python3
"""Check generated UI against real snapshot data. Never creates fixture/odds input."""
from __future__ import annotations

import asyncio
import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import unquote, urlparse

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent


async def checks(url: str, data: dict) -> None:
    errors = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 1000})
        # Offline feature tests serve actual built output through a mock of the
        # public transport only. No invented source rows or price values.
        async def local_transport(route):
            path = urlparse(route.request.url).path
            prefix = "/repos/buffedlizard55-lab/MaltaProj1/contents/"
            if not path.startswith(prefix):
                await route.abort()
                return
            relative = unquote(path[len(prefix):])
            target = (ROOT / relative).resolve()
            if not target.is_relative_to(ROOT) or not target.is_file():
                await route.fulfill(status=404, content_type="application/json", body='{"message":"Missing test transport target"}')
                return
            body = {"type": "file", "path": relative, "encoding": "base64", "content": base64.b64encode(target.read_bytes()).decode()}
            await route.fulfill(content_type="application/json", body=json.dumps(body), headers={"Access-Control-Allow-Origin": "*"})
        await context.route("https://api.github.com/**", local_transport)
        page = await context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(url + "/index.html")
        assert await page.locator("h1").count() == 1
        assert await page.locator(".sort").count() == 0
        await page.goto(url + "/matches.html")
        assert await page.locator("tr[data-row]").count() == len(data["matches"])
        await page.locator("#match-search").fill("aurora")
        expected = sum("aurora" in " ".join(str(row.get(key) or "") for key in ("team_a", "team_b", "tournament", "game")).lower() for row in data["matches"])
        assert await page.locator("tr[data-row]:visible").count() == expected
        await page.reload()
        assert await page.locator("#match-search").input_value() == "aurora"
        await page.locator("#clear-filters").click()
        await page.locator("#coverage-filter").select_option("priced")
        expected = sum(row["analysis"]["status"] == "calculated" for row in data["matches"])
        assert await page.locator("tr[data-row]:visible").count() == expected
        await page.locator("#clear-filters").click()
        await page.locator('[data-game-tab="lol"]').click()
        assert await page.locator("tr[data-row]:visible").count() == sum(row["game"] == "lol" for row in data["matches"])
        await page.locator("#clear-filters").click()
        await page.locator('[data-sort="match"]').click()
        assert await page.locator('[data-sort="match"]').evaluate("node => node.closest('th').getAttribute('aria-sort')") == "ascending"
        await page.locator("#match-search").fill("NoSuchSyntheticTestSearch_NotARealTeam")
        assert await page.locator("#no-results").is_visible()
        await page.locator("#clear-filters").click()
        async with page.expect_download() as information:
            await page.locator("#download-csv").click()
        assert (await information.value).suggested_filename.endswith(".csv")
        await page.goto(url + "/inventory.html")
        assert await page.locator("tbody tr").count() == len(data["inventory"])
        stale = await context.new_page()
        await stale.add_init_script("const actualNow=Date.now; Date.now=()=>actualNow()+7200000;")
        await stale.goto(url + "/matches.html")
        assert await stale.locator("#snapshot-banner").is_visible()
        assert await stale.locator('tr[data-priced="true"]:not(.quote-expired)').count() == 0
        await stale.locator("#coverage-filter").select_option("priced")
        assert await stale.locator("tr[data-row]:visible").count() == 0
        await stale.close()
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto(url + "/index.html")
        await page.locator("#menu-toggle").click()
        assert await page.locator("#menu-toggle").get_attribute("aria-expanded") == "true"
        await page.keyboard.press("Escape")
        assert await page.locator("#menu-toggle").get_attribute("aria-expanded") == "false"
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        await browser.close()
    print("Browser checks passed: actual records, filters/search/sort/CSV, inventory, expiry, mobile, no script errors.")


if __name__ == "__main__":
    data = json.loads((ROOT / "data/snapshot/latest.json").read_text())
    server = ThreadingHTTPServer(("0.0.0.0", 0), partial(SimpleHTTPRequestHandler, directory=str(ROOT / "dashboard")))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        asyncio.run(checks(f"http://127.0.0.1:{server.server_address[1]}", data))
    finally:
        server.shutdown()
        server.server_close()
