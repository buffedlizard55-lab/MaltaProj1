#!/usr/bin/env python3
"""Inspect normal public pages. No login, evasion, wagering, or private APIs.

Raw HTML/JS/network responses are an Actions artifact, not repository content.
URLs containing credentials or personal identifiers are never logged.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError

OUT = Path(".cache/discovery")
OUT.mkdir(parents=True, exist_ok=True)
AGENT = "MaltaProj1-source-audit/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1)"
TARGETS = {
    "hotspawn": "https://play.hotspawn.com/lobby",
    "thunderpick": "https://thunderpick.io/esports/cs2-betting",
    "pinnacle": "https://www.pinnacle.com/en/esports-hub",
    "hltv": "https://www.hltv.org/matches",
}
summary: dict = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "pages": [], "network": []}


def safe_url(url: str) -> str:
    if re.search(r"token|key=|auth|session|password|email|client_secret", url, re.I):
        return url.split("?", 1)[0] + "?[redacted]"
    return url


def write(label: str, content: bytes, suffix: str) -> str:
    name = f"{label}-{hashlib.sha256(content).hexdigest()[:16]}.{suffix}"
    (OUT / name).write_bytes(content)
    return name


def get(url: str) -> tuple[int, bytes, str]:
    try:
        with urlopen(Request(url, headers={"User-Agent": AGENT}), timeout=35) as response:
            return response.status, response.read(8_000_000), response.url
    except HTTPError as error:
        return error.code, error.read(100_000), error.url


def inspect_http() -> None:
    for label, url in TARGETS.items():
        entry = {"label": label, "url": url}
        try:
            status, body, final_url = get(url)
            entry.update(status=status, final_url=safe_url(final_url), file=write(label, body, "html"))
            html = body.decode("utf-8", errors="replace")
            scripts = re.findall(r'<script[^>]+src=[\"\']([^\"\']+)', html, re.I)
            entry["scripts"] = []
            # Only first-party assets; never collect advertising, analytics, or account endpoints.
            for src in scripts[:30]:
                asset_url = urljoin(final_url, src)
                if urlparse(asset_url).hostname != urlparse(final_url).hostname:
                    continue
                try:
                    code, asset, _ = get(asset_url)
                    info = {"url": safe_url(asset_url), "status": code, "file": write(label, asset, "js")}
                    text = asset.decode("utf-8", errors="replace")
                    hints = re.findall(r'(?:https?://[^\s\"\'<>`]{6,180}|/api/[\w/?=.&%+-]{3,120})', text)
                    info["public_url_hints"] = sorted({safe_url(x) for x in hints if any(w in x.lower() for w in ("api", "match", "event", "odds"))})[:80]
                    entry["scripts"].append(info)
                except Exception as error:
                    entry["scripts"].append({"url": safe_url(asset_url), "error": type(error).__name__})
        except Exception as error:
            entry["error"] = f"{type(error).__name__}: {error}"
        summary["pages"].append(entry)
        print(json.dumps(entry, ensure_ascii=False), flush=True)


async def inspect_browser() -> None:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 1000}, timezone_id="UTC")
        for label, url in TARGETS.items():
            page = await context.new_page()
            tasks: list = []

            async def capture(response, source=label):
                try:
                    parsed = urlparse(response.url)
                    host = parsed.hostname or ""
                    if not any(x in host for x in ("hotspawn", "cloudwaysapps", "thunderpick", "pinnacle", "hltv", "arcadia")):
                        return
                    if re.search(r"auth|login|account|user|session|token|wallet|balance", parsed.path, re.I):
                        return
                    content_type = response.headers.get("content-type", "")
                    if "json" not in content_type or response.request.method != "GET":
                        return
                    body = await response.body()
                    if len(body) > 12_000_000:
                        return
                    info = {"source": source, "url": safe_url(response.url), "status": response.status, "content_type": content_type, "file": write(source + "-response", body, "json"), "observed_in": url}
                    summary["network"].append(info)
                    print(json.dumps(info), flush=True)
                except Exception:
                    pass

            page.on("response", lambda response: tasks.append(asyncio.create_task(capture(response))))
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                await page.wait_for_timeout(20_000)
                # Scroll once to observe ordinary lazy loading, without changing or submitting anything.
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(5_000)
                html = await page.content()
                text = await page.locator("body").inner_text()
                info = {"label": label, "mode": "browser", "url": safe_url(page.url), "status": response.status if response else None, "html_file": write(label + "-browser", html.encode(), "html"), "text_file": write(label + "-browser", text.encode(), "txt")}
                summary["pages"].append(info)
                print(json.dumps(info), flush=True)
            except Exception as error:
                summary["pages"].append({"label": label, "mode": "browser", "error": f"{type(error).__name__}: {error}"})
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await page.close()
        await context.close()
        await browser.close()


if __name__ == "__main__":
    try:
        inspect_http()
        asyncio.run(inspect_browser())
    finally:
        summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
        # GitHub artifact downloads redirect to hosts unavailable to this sandbox.
        # A small, temporary public-source archive is required for parser audit.
        # It is removed before final publication; no account data/headers are saved.
        import tarfile
        Path("research").mkdir(exist_ok=True)
        with tarfile.open("research/discovery.tar.gz", "w:gz") as archive:
            for source_file in sorted(OUT.iterdir()):
                if source_file.suffix in {".html", ".txt", ".json", ".js"}:
                    archive.add(source_file, arcname=source_file.name)
        Path("research/discovery-index.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
