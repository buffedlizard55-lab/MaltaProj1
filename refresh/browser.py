#!/usr/bin/env python3
"""Headless-browser fetch path for sources that reject plain HTTP clients.

EGamersWorld and HLTV return HTTP 403 to a stdlib client from a datacenter IP but serve an
ordinary browser normally, so this module loads those pages in headless Chromium (the same
"ordinary browser" approach the repository already uses for Pinnacle) and also captures the JSON
responses the pages themselves request — in particular Pinnacle's public guest matchups/markets
responses, which carry moneyline prices but require no account and no API key.

Nothing here logs in, defeats a challenge, or calls an undocumented private endpoint: it renders
public pages and records the public responses those pages load on their own.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
BLOCK_TYPES = {"image", "font", "media"}
JSON_HOSTS = ("guest.api.arcadia.pinnacle.com",)

try:  # Playwright is optional: the collector still runs (HTTP-client path) without it.
    from playwright.sync_api import Error as PWError
    from playwright.sync_api import sync_playwright
    HAVE_PLAYWRIGHT = True
except Exception:  # noqa: BLE001 - import failure must not break the collector
    HAVE_PLAYWRIGHT = False
    PWError = Exception


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class BrowserSession:
    """One Chromium instance reused for every page in a collection run."""

    def __init__(self, timeout_ms: int = 45000, settle_ms: int = 1500,
                 capture_hosts: tuple[str, ...] = JSON_HOSTS):
        self.timeout_ms = timeout_ms
        self.settle_ms = settle_ms
        self.capture_hosts = capture_hosts
        self._pw = None
        self._browser = None
        self._ctx = None
        self.captured: list[dict] = []

    def __enter__(self) -> "BrowserSession":
        if not HAVE_PLAYWRIGHT:
            raise RuntimeError("playwright is not installed")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        self._ctx = self._browser.new_context(
            user_agent=UA, locale="en-US", viewport={"width": 1366, "height": 900},
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        self._ctx.route("**/*", self._route)
        return self

    def _route(self, route, request) -> None:
        try:
            if request.resource_type in BLOCK_TYPES:
                route.abort()
            else:
                route.continue_()
        except PWError:
            pass

    def _on_response(self, response) -> None:
        try:
            url = response.url
            if not any(host in url for host in self.capture_hosts):
                return
            ctype = (response.headers or {}).get("content-type", "")
            if "json" not in ctype:
                return
            body = response.json()
        except Exception:  # noqa: BLE001 - a capture failure must never break a page load
            return
        self.captured.append({"url": url, "status": response.status,
                              "observed_utc": now_iso(), "body": body})

    def __exit__(self, *exc) -> None:
        for closer in (self._ctx, self._browser):
            try:
                if closer:
                    closer.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:  # noqa: BLE001
            pass

    def get(self, url: str) -> dict:
        """Render one public page; return its HTML plus any captured JSON from that load."""
        out = {"url": url, "status": None, "html": None, "error": None,
               "fetched_utc": now_iso(), "captured": []}
        page = None
        try:
            page = self._ctx.new_page()
            page.on("response", self._on_response)
            before = len(self.captured)
            response = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_timeout(self.settle_ms)
            out["status"] = response.status if response else None
            out["html"] = page.content()
            out["captured"] = self.captured[before:]
        except Exception as exc:  # noqa: BLE001
            out["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:  # noqa: BLE001
                    pass
        return out


def extract_pinnacle_quotes(captured: list[dict], page_url: str) -> tuple[list[dict], dict]:
    """Moneyline quotes from Pinnacle's public guest responses loaded by the matchups page."""
    events: dict[int, dict] = {}
    markets: list[tuple[dict, str]] = []
    for packet in captured:
        url, body = packet["url"], packet.get("body")
        if not isinstance(body, list):
            continue
        if "/matchups" in url:
            for item in body:
                if isinstance(item, dict) and isinstance(item.get("id"), int):
                    events[item["id"]] = item
        elif "/markets/" in url:
            for item in body:
                if isinstance(item, dict):
                    markets.append((item, url))
    quotes: dict[tuple[str, int], dict] = {}
    counters = {"events": len(events), "market_records": len(markets), "rejected": 0}
    for market, market_url in markets:
        if (market.get("type") != "moneyline" or market.get("period") != 0
                or market.get("isAlternate") is not False or market.get("status") != "open"):
            counters["rejected"] += 1
            continue
        event = events.get(market.get("matchupId"))
        if not event:
            counters["rejected"] += 1
            continue
        league = event.get("league") or {}
        sport = (league.get("sport") or {}).get("id")
        game = "cs2" if sport == 12 else ("lol" if sport == 2 else None)
        participants = event.get("participants") or []
        prices = market.get("prices") or []
        if game is None or len(participants) != 2 or len(prices) != 2:
            counters["rejected"] += 1
            continue
        names = {p.get("alignment"): p.get("name") for p in participants}
        native = {p.get("designation"): p.get("price") for p in prices}
        if set(names) != {"home", "away"} or set(native) != {"home", "away"}:
            counters["rejected"] += 1
            continue
        try:
            odds_home = american_to_decimal(native["home"])
            odds_away = american_to_decimal(native["away"])
        except ValueError:
            counters["rejected"] += 1
            continue
        start = event.get("startTime")
        quotes[(game, int(event["id"]))] = {
            "game": game, "event_id": event["id"], "team_a": names["home"],
            "team_b": names["away"], "tournament": league.get("name"),
            "start_utc": start, "best_of": event.get("bestOfX"),
            "odds_a": odds_home, "odds_b": odds_away,
            "native_odds_a": native["home"], "native_odds_b": native["away"],
            "native_format": "american (converted to decimal with 1 + value/100 for positive "
                             "prices and 1 + 100/|value| for negative prices)",
            "source_url": page_url, "api_url": market_url, "observed_utc": now_iso(),
        }
    counters["quotes"] = len(quotes)
    return sorted(quotes.values(), key=lambda q: (q.get("start_utc") or "", q["team_a"])), counters


def american_to_decimal(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value) < 100:
        raise ValueError("not a valid American price")
    return 1 + value / 100 if value > 0 else 1 + 100 / abs(value)


def load_json(path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
