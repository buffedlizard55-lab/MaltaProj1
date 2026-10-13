"""Refresh the static dashboard snapshot from public fixture and market pages."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from hotspawn import GAME_PAGES, parse_hotspawn_listing
from market_sources import PolymarketSource, THUNDERPICK_INDEX, ThunderpickSource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "site" / "data" / "snapshot.json"


def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "MaltaProj1-odds-dashboard/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1)",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.8",
        }
    )
    retry = Retry(
        total=2,
        connect=2,
        read=1,
        status=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_hotspawn(session: requests.Session, game: str) -> tuple[dict[str, Any], str | None]:
    url = GAME_PAGES[game]
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        result = parse_hotspawn_listing(response.text, game, url)
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"Hotspawn {game} fixture page could not be read: {exc}") from exc
    if not result["parsedFixtures"]:
        raise RuntimeError(
            f"Hotspawn {game} page yielded no parseable fixture cards; refusing to replace the last known snapshot."
        )
    if result["unparsedMatchLinks"]:
        print(
            f"WARN {game}: {len(result['unparsedMatchLinks'])} official match link(s) were not parsed.",
            file=sys.stderr,
        )
    return result, None


def _source_registry() -> list[dict[str, str]]:
    return [
        {
            "id": "hotspawn-cs2",
            "name": "Hotspawn CS2 Pick'ems lobby",
            "url": GAME_PAGES["CS2"],
            "role": "Fixture scope, team names, competition, and raw displayed schedule only. Player picks and crowd shares are never read or used as probabilities.",
        },
        {
            "id": "hotspawn-lol",
            "name": "Hotspawn League of Legends Pick'ems lobby",
            "url": GAME_PAGES["LoL"],
            "role": "Fixture scope, team names, competition, and raw displayed schedule only. Player picks and crowd shares are never read or used as probabilities.",
        },
        {
            "id": "thunderpick-cs2",
            "name": "Thunderpick CS2 bookmaker index",
            "url": THUNDERPICK_INDEX["CS2"],
            "role": "Independent bookmaker source. Only a directly linked, exact-team, exact-date two-way Match Winner market is converted to no-vig probabilities.",
        },
        {
            "id": "thunderpick-lol",
            "name": "Thunderpick League of Legends bookmaker index",
            "url": THUNDERPICK_INDEX["LoL"],
            "role": "Independent bookmaker source. Only a directly linked, exact-team, exact-date two-way Match Winner market is converted to no-vig probabilities.",
        },
        {
            "id": "polymarket-api",
            "name": "Polymarket Gamma public market-data API",
            "url": "https://docs.polymarket.com/getting-started/api",
            "role": "Official prediction-market exchange reference. A quote is displayed separately and never enters the sportsbook no-vig calculation.",
        },
    ]


def _audit_for_coverage(listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for listing in listings:
        if listing["coverageComplete"]:
            continue
        game = listing["game"]
        expected = listing["statedMatchesThisWeek"]
        parsed = len(listing["parsedFixtures"])
        unparsed = len(listing["unparsedMatchLinks"])
        if expected is None:
            detail = (
                f"The {game} page did not expose a machine-readable weekly count. "
                f"The scraper parsed {parsed} fixture card(s); coverage is not claimed complete."
            )
        else:
            detail = (
                f"Hotspawn reports {expected} {game} matches this week; the refresh parsed {parsed} fixture card(s) "
                f"and found {unparsed} unparsed official match link(s). This snapshot is explicitly partial."
            )
        items.append(
            {
                "id": f"hotspawn-coverage-{game.casefold()}",
                "status": "needs-review",
                "severity": "review",
                "title": f"{game} fixture extraction is incomplete",
                "details": detail,
                "sources": [listing["pageUrl"], *listing["unparsedMatchLinks"][:10]],
            }
        )
    return items


def _build_snapshot(session: requests.Session, now: datetime) -> dict[str, Any]:
    listings: list[dict[str, Any]] = []
    fixtures: list[dict[str, Any]] = []
    for game in ("CS2", "LoL"):
        listing, _ = fetch_hotspawn(session, game)
        listings.append(listing)
        fixtures.extend(listing["parsedFixtures"])

    thunderpick = ThunderpickSource(session)
    polymarket = PolymarketSource(session)
    rows: list[dict[str, Any]] = []
    provider_warnings: list[str] = []
    missing_tz_fixtures: list[str] = []

    for index, fixture in enumerate(fixtures):
        # The user-visible fixture clock is retained exactly as Hotspawn prints
        # it. Only an explicitly zoned independent event time may populate UTC.
        bookmaker, bookmaker_reason = thunderpick.quote_for(fixture, now)
        if bookmaker_reason != "verified" and bookmaker_reason.startswith("Thunderpick") and "No direct" not in bookmaker_reason:
            if bookmaker_reason not in provider_warnings:
                provider_warnings.append(bookmaker_reason)

        exchange, exchange_reason = polymarket.quote_for(fixture, now)
        if exchange_reason != "verified" and exchange_reason.startswith("Polymarket") and "No active" not in exchange_reason and "No active official" not in exchange_reason:
            if exchange_reason not in provider_warnings:
                provider_warnings.append(exchange_reason)

        start_at_utc = exchange.get("eventStartAtUtc") if exchange else None
        if not start_at_utc:
            missing_tz_fixtures.append(fixture["id"])
        flags: list[str] = []
        if not bookmaker:
            flags.append(
                "Unverified sportsbook line: " + bookmaker_reason
            )
        if not exchange:
            flags.append(
                "Unverified exchange reference: " + exchange_reason
            )
        if not start_at_utc:
            flags.append(
                "Hotspawn's displayed clock has no verified timezone; raw time is shown without UTC conversion."
            )
        rows.append(
            {
                "id": fixture["id"],
                "game": fixture["game"],
                "tournament": fixture["tournament"],
                "teamA": fixture["teamA"],
                "teamB": fixture["teamB"],
                "hotspawnTimeLabel": fixture["hotspawnTimeLabel"],
                "startAtUtc": start_at_utc,
                "lineStatus": (
                    "bookmaker-and-exchange-verified"
                    if bookmaker and exchange
                    else "bookmaker-only"
                    if bookmaker
                    else "exchange-only"
                    if exchange
                    else "unverified"
                ),
                "bookmaker": bookmaker,
                "exchange": exchange,
                "sources": {
                    "fixtureUrl": fixture["fixtureUrl"],
                    "fixtureLabel": "Hotspawn match detail (fixture only)",
                    "scheduleUrl": exchange.get("apiUrl") if exchange else None,
                },
                "flags": flags,
            }
        )
        if (index + 1) % 25 == 0:
            print(f"Checked {index + 1}/{len(fixtures)} fixtures")

    if not rows:
        raise RuntimeError("No fixtures were available after parsing; refusing to write an empty snapshot.")

    audit_items = _audit_for_coverage(listings)
    if missing_tz_fixtures:
        audit_items.append(
            {
                "id": "hotspawn-timezone-not-stated",
                "status": "needs-review",
                "severity": "review",
                "title": "Some Hotspawn lobby clocks have no verified timezone",
                "details": (
                    f"{len(missing_tz_fixtures)} fixture(s) have no explicitly zoned UTC timestamp from an independent "
                    "market source. Their raw Hotspawn clock is preserved; the dashboard does not guess a timezone."
                ),
                "sources": [GAME_PAGES["CS2"], GAME_PAGES["LoL"]],
            }
        )
    for warning_index, warning in enumerate(provider_warnings, start=1):
        audit_items.append(
            {
                "id": f"source-fetch-warning-{warning_index}",
                "status": "needs-review",
                "severity": "review",
                "title": "An independent market source could not be checked for every fixture",
                "details": warning,
                "sources": [
                    "https://thunderpick.io/esports/cs2-betting",
                    "https://thunderpick.io/esports/league-of-legends",
                    "https://gamma-api.polymarket.com/public-search",
                ],
            }
        )

    bookmaker_count = sum(row["bookmaker"] is not None for row in rows)
    exchange_count = sum(row["exchange"] is not None for row in rows)
    complete = all(listing["coverageComplete"] for listing in listings)
    by_game = {
        listing["game"]: {
            "sourceUrl": listing["pageUrl"],
            "statedMatchesThisWeek": listing["statedMatchesThisWeek"],
            "discoveredMatchLinks": listing["discoveredMatchLinks"],
            "parsedFixtures": len(listing["parsedFixtures"]),
            "unparsedMatchLinks": len(listing["unparsedMatchLinks"]),
            "isComplete": listing["coverageComplete"],
        }
        for listing in listings
    }
    return {
        "schemaVersion": 1,
        "snapshotStatus": "current-complete" if complete else "current-partial",
        "generatedAt": now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verifiedOn": now.astimezone(timezone.utc).date().isoformat(),
        "coverage": {
            "isComplete": complete,
            "listedMatches": len(rows),
            "bookmakerPricedMatches": bookmaker_count,
            "exchangePricedMatches": exchange_count,
            "unpricedMatches": len(rows) - bookmaker_count,
            "byGame": by_game,
            "note": (
                "Coverage is complete only when each Hotspawn game page's stated weekly match count equals the number of parsed official fixture cards. "
                "A partial snapshot is visibly flagged; unverified market values remain null."
            ),
        },
        "policy": {
            "hotspawnUse": "fixture scope, team names, competition, and raw schedule label only; Hotspawn picks, crowd shares, displayed percentages, and any derived signal are never read or used as probability evidence",
            "bookmakerProbability": "two-way Thunderpick Match Winner American prices converted to raw implied probabilities and normalized by their sum to remove overround",
            "exchangePrice": "official Polymarket series Match Winner price shown in a separate exchange column; never represented as sportsbook odds or blended into no-vig probabilities",
            "missingValue": "null means the value could not be independently verified; the site displays a blank and a review flag rather than inferring it",
            "timeZone": "Hotspawn's raw time label is preserved. UTC is populated only from an explicitly zoned independent market API timestamp.",
        },
        "sources": _source_registry(),
        "auditItems": audit_items,
        "matches": rows,
    }


def refresh(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    session = create_session()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    snapshot = _build_snapshot(session, now)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, output)
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Snapshot JSON destination")
    args = parser.parse_args()
    snapshot = refresh(args.output)
    coverage = snapshot["coverage"]
    print(
        f"Wrote {coverage['listedMatches']} fixtures; sportsbook quotes: "
        f"{coverage['bookmakerPricedMatches']}; exchange references: "
        f"{coverage['exchangePricedMatches']}; complete: {coverage['isComplete']}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # A failed refresh must leave the prior JSON intact.
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
