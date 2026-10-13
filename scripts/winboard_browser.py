"""Browser-based collector for the arena/cc8f4dca picks pipeline.

Runs Playwright Chromium inside GitHub Actions. Several odds sources refuse plain HTTP
clients (403 to datacentre IPs) but serve a normal browser, so this step renders them
exactly as a user would see them and captures both the DOM text and the JSON the page
itself requested.

Nothing is inferred: whatever the page actually returned is what is written out.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "winboard" / "data"
RAW = ROOT / "winboard" / "raw"
DEBUG = DATA / "_debug"

TARGETS = [
    ("egamersworld_matches", "https://egamersworld.com/counterstrike/matches"),
    ("hltv_ranking", "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("hltv_matches", "https://www.hltv.org/matches"),
    ("pinnacle_esports", "https://www.pinnacle.com/en/esports/matchups/highlights/"),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> int:
    from playwright.sync_api import sync_playwright  # imported here; Actions installs it

    for directory in (DATA, RAW, DEBUG):
        directory.mkdir(parents=True, exist_ok=True)

    report: dict[str, object] = {"run_started_utc": now_utc(), "targets": []}
    captured: dict[str, list[dict[str, object]]] = {}
    json_hits: dict[str, list[dict[str, object]]] = {}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context(
            locale="en-US",
            timezone_id="UTC",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 2400},
        )

        for name, url in TARGETS:
            print(f"== {name} {url}", flush=True)
            page = context.new_page()
            responses: list[dict[str, object]] = []
            blobs: list[dict[str, object]] = []

            def on_response(response, responses=responses, blobs=blobs):
                try:
                    ctype = (response.headers or {}).get("content-type", "")
                    if "json" not in ctype:
                        return
                    body = response.body()
                except Exception:  # noqa: BLE001
                    return
                responses.append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "content_type": ctype,
                        "bytes": len(body),
                    }
                )
                if len(body) < 400_000:
                    text = body.decode("utf-8", "replace")
                    if any(key in text for key in ("odds", "participants", "ranking", "matches")):
                        blobs.append({"url": response.url, "text": text})

            page.on("response", on_response)
            status = None
            error = None
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                status = response.status if response else None
                page.wait_for_timeout(6000)
                for _ in range(6):
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1200)
                page.wait_for_timeout(3000)
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"

            text = ""
            try:
                text = page.inner_text("body")
            except Exception as exc:  # noqa: BLE001
                error = (error or "") + f" | inner_text: {exc}"

            (DEBUG / f"{name}_text.txt").write_text(text[:200_000])
            (RAW / f"{name}.txt.gz").write_bytes(gzip.compress(text.encode("utf-8")))
            captured[name] = responses
            json_hits[name] = blobs
            report["targets"].append(
                {
                    "name": name,
                    "url": url,
                    "http_status": status,
                    "error": error,
                    "text_bytes": len(text),
                    "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "json_responses": len(responses),
                    "json_blobs": len(blobs),
                    "fetched_utc": now_utc(),
                }
            )
            print(f"   status={status} text={len(text)}B json={len(responses)} blobs={len(blobs)}", flush=True)
            page.close()

        browser.close()

    (DEBUG / "browser_json_responses.json").write_text(json.dumps(captured, indent=2)[:400_000])
    for name, blobs in json_hits.items():
        for index, blob in enumerate(blobs[:6]):
            (DEBUG / f"{name}_blob{index}.json").write_text(blob["text"][:200_000])
    (DEBUG / "browser_report.json").write_text(json.dumps(report, indent=2))
    print("browser collect complete", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
