"""Validate snapshot schema, source provenance, and sportsbook calculations."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

from odds import as_percent, no_vig_two_way

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = ROOT / "site" / "data" / "snapshot.json"


def _is_https_url(value: object, allowed_hosts: set[str] | None = None) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return False
    if allowed_hosts is not None and parsed.hostname not in allowed_hosts:
        return False
    return True


def _check_probability(actual: object, expected: float, label: str, errors: list[str], row_id: str) -> None:
    try:
        number = float(actual)
    except (TypeError, ValueError):
        errors.append(f"{row_id}: {label} is missing or not numeric")
        return
    if not math.isfinite(number) or abs(number - expected) > 0.011:
        errors.append(f"{row_id}: {label} does not match the American-odds calculation")


def validate_snapshot(snapshot: dict) -> list[str]:
    errors: list[str] = []
    if snapshot.get("schemaVersion") != 1:
        errors.append("schemaVersion must be 1")
    status = snapshot.get("snapshotStatus")
    if status not in {"partial-baseline", "current-partial", "current-complete"}:
        errors.append("snapshotStatus is not recognized")
    if status != "partial-baseline" and not _is_https_url(snapshot.get("sources", [{}])[0].get("url") if snapshot.get("sources") else None):
        errors.append("refreshed snapshot is missing its source registry")
    if status in {"current-partial", "current-complete"} and not snapshot.get("generatedAt"):
        errors.append("a current snapshot must have generatedAt")

    matches = snapshot.get("matches")
    if not isinstance(matches, list):
        return errors + ["matches must be an array"]
    ids: set[str] = set()
    for row in matches:
        if not isinstance(row, dict):
            errors.append("matches contains a non-object row")
            continue
        row_id = str(row.get("id") or "(missing id)")
        if row_id in ids:
            errors.append(f"{row_id}: duplicate fixture id")
        ids.add(row_id)
        for key in ("game", "teamA", "teamB", "tournament", "hotspawnTimeLabel"):
            if not isinstance(row.get(key), str) or not row[key].strip():
                errors.append(f"{row_id}: {key} must be a non-empty string")
        if row.get("game") not in {"CS2", "LoL"}:
            errors.append(f"{row_id}: unsupported game category")
        if row.get("startAtUtc") is not None:
            start = row["startAtUtc"]
            if not isinstance(start, str) or not re.search(r"(?:Z|[+-]\d\d:\d\d)$", start):
                errors.append(f"{row_id}: startAtUtc must include an explicit timezone")

        sources = row.get("sources") or {}
        fixture_url = sources.get("fixtureUrl")
        if not _is_https_url(fixture_url, {"www.hotspawn.com", "hotspawn.com"}):
            errors.append(f"{row_id}: every row needs an official Hotspawn fixture source link")
        flags = row.get("flags")
        if not isinstance(flags, list):
            errors.append(f"{row_id}: flags must be an array")
            flags = []

        bookmaker = row.get("bookmaker")
        if bookmaker is None and not any("unverified" in str(flag).casefold() or "no sportsbook" in str(flag).casefold() for flag in flags):
            errors.append(f"{row_id}: a missing sportsbook value must have an explicit review flag")
        exchange_value = row.get("exchange")
        if exchange_value is None and not any("unverified" in str(flag).casefold() or "no active" in str(flag).casefold() for flag in flags):
            errors.append(f"{row_id}: a missing exchange value must have an explicit review flag")

        bookmaker = row.get("bookmaker")
        if bookmaker is not None:
            if not isinstance(bookmaker, dict):
                errors.append(f"{row_id}: bookmaker must be an object or null")
                continue
            if str(bookmaker.get("name", "")).casefold() == "hotspawn":
                errors.append(f"{row_id}: Hotspawn cannot be used as a probability source")
            if bookmaker.get("market") != "Match Winner":
                errors.append(f"{row_id}: only the Match Winner sportsbook market is allowed")
            if bookmaker.get("oddsFormat") != "American":
                errors.append(f"{row_id}: sportsbook odds must be explicit American format")
            if not _is_https_url(bookmaker.get("sourceUrl"), {"thunderpick.io", "www.thunderpick.io"}):
                errors.append(f"{row_id}: sportsbook price must link directly to an official Thunderpick page")
            try:
                fair = no_vig_two_way(bookmaker.get("oddsA"), bookmaker.get("oddsB"))
                _check_probability(bookmaker.get("rawProbabilityA"), float(as_percent(fair["raw_a"])), "rawProbabilityA", errors, row_id)
                _check_probability(bookmaker.get("rawProbabilityB"), float(as_percent(fair["raw_b"])), "rawProbabilityB", errors, row_id)
                _check_probability(bookmaker.get("overroundPct"), float(as_percent(fair["overround"])), "overroundPct", errors, row_id)
                _check_probability(bookmaker.get("noVigProbabilityA"), float(as_percent(fair["fair_a"])), "noVigProbabilityA", errors, row_id)
                _check_probability(bookmaker.get("noVigProbabilityB"), float(as_percent(fair["fair_b"])), "noVigProbabilityB", errors, row_id)
            except ValueError as exc:
                errors.append(f"{row_id}: invalid sportsbook odds: {exc}")

        exchange = row.get("exchange")
        if exchange is not None:
            if not isinstance(exchange, dict):
                errors.append(f"{row_id}: exchange must be an object or null")
                continue
            if str(exchange.get("name", "")).casefold() != "polymarket":
                errors.append(f"{row_id}: only the configured official Polymarket exchange is supported")
            if "not a sportsbook" not in str(exchange.get("marketType", "")).casefold():
                errors.append(f"{row_id}: exchange reference must be labeled as not a sportsbook")
            if not _is_https_url(exchange.get("sourceUrl"), {"polymarket.com", "www.polymarket.com"}):
                errors.append(f"{row_id}: exchange reference needs an official Polymarket source link")
            if not _is_https_url(exchange.get("apiUrl"), {"gamma-api.polymarket.com"}):
                errors.append(f"{row_id}: exchange API provenance is missing or not official")
            for price_key in ("priceA", "priceB"):
                try:
                    price = float(exchange.get(price_key))
                except (TypeError, ValueError):
                    errors.append(f"{row_id}: {price_key} must be numeric")
                    continue
                if not math.isfinite(price) or not 0 <= price <= 100:
                    errors.append(f"{row_id}: {price_key} must be in cents from 0 through 100")

    coverage = snapshot.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        if coverage.get("listedMatches") is not None and coverage.get("listedMatches") != len(matches):
            errors.append("coverage.listedMatches must equal the number of rows")
        expected_book = sum(isinstance(row, dict) and row.get("bookmaker") is not None for row in matches)
        expected_exchange = sum(isinstance(row, dict) and row.get("exchange") is not None for row in matches)
        if coverage.get("bookmakerPricedMatches") is not None and coverage.get("bookmakerPricedMatches") != expected_book:
            errors.append("coverage.bookmakerPricedMatches does not match rows")
        if coverage.get("exchangePricedMatches") is not None and coverage.get("exchangePricedMatches") != expected_exchange:
            errors.append("coverage.exchangePricedMatches does not match rows")
        if coverage.get("isComplete") and status != "current-complete":
            errors.append("only current-complete snapshots may claim full coverage")

    for item in snapshot.get("auditItems", []):
        if not isinstance(item, dict):
            errors.append("auditItems contains a non-object item")
            continue
        for url in item.get("sources", []):
            if not _is_https_url(url):
                errors.append(f"audit item {item.get('id', '(missing id)')} has a non-HTTPS source link")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", nargs="?", type=Path, default=DEFAULT_SNAPSHOT)
    args = parser.parse_args()
    try:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read snapshot: {exc}")
        return 1
    errors = validate_snapshot(snapshot)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"Snapshot valid: {len(snapshot['matches'])} fixture row(s), status={snapshot['snapshotStatus']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
