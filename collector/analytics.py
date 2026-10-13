"""Reproducible calculations using only independently sourced match-winner odds.

This module deliberately knows nothing about Hotspawn pick percentages, rankings,
or favorites. Missing evidence produces None, never a 50/50 prior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from statistics import mean
import unicodedata

MAX_QUOTE_AGE_SECONDS = 3600


def parse_time(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    # A date without an explicit zone is unverified, not assumed UTC.
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def iso_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("An explicit timezone is required")
    return value.astimezone(timezone.utc).isoformat(timespec="auto").replace("+00:00", "Z")


def valid_decimal(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 1


def american_to_decimal(value: int | float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or abs(value) < 100:
        raise ValueError("Invalid American odds")
    return 1 + value / 100 if value > 0 else 1 + 100 / abs(value)


def no_vig(odds_a: float, odds_b: float) -> dict[str, float]:
    if not valid_decimal(odds_a) or not valid_decimal(odds_b):
        raise ValueError("Two valid decimal odds are required")
    implied_a, implied_b = 1 / odds_a, 1 / odds_b
    total = implied_a + implied_b
    probability_a, probability_b = implied_a / total, implied_b / total
    return {
        "implied_a": implied_a,
        "implied_b": implied_b,
        "overround": total - 1,
        "probability_a": probability_a,
        "probability_b": probability_b,
        "fair_odds_a": 1 / probability_a,
        "fair_odds_b": 1 / probability_b,
    }


def normalized_name(value: str | None) -> str:
    """Only case, Unicode representation and whitespace; never guess aliases."""
    return " ".join(unicodedata.normalize("NFKC", value or "").casefold().split())


def match_orientation(match: dict, quote: dict) -> bool | None:
    """False = same order; True = reversed. Exact game/pair/UTC start only."""
    if match.get("game") != quote.get("game"):
        return None
    start_match, start_quote = parse_time(match.get("start_time")), parse_time(quote.get("start_time"))
    if not start_match or not start_quote or start_match != start_quote:
        return None
    pair_match = (normalized_name(match.get("team_a")), normalized_name(match.get("team_b")))
    pair_quote = (normalized_name(quote.get("team_a")), normalized_name(quote.get("team_b")))
    if not all(pair_match + pair_quote) or pair_match[0] == pair_match[1]:
        return None
    if pair_match == pair_quote:
        return False
    if pair_match == pair_quote[::-1]:
        return True
    return None


def eligible_quote(quote: dict, now: datetime) -> bool:
    observed = parse_time(quote.get("observed_at"))
    starts = parse_time(quote.get("start_time"))
    if observed is None or starts is None or starts <= now:
        return False
    age = (now - observed).total_seconds()
    return (
        0 <= age <= MAX_QUOTE_AGE_SECONDS
        and quote.get("market_type") == "match_winner"
        and quote.get("period") == "match"
        and quote.get("status") == "open"
        and quote.get("is_live") is False
        and quote.get("outcome_count") == 2
        and quote.get("source_role") == "primary_bookmaker"
        and bool(quote.get("evidence_id"))
        and bool(quote.get("source_url"))
        and valid_decimal(quote.get("odds_a"))
        and valid_decimal(quote.get("odds_b"))
    )


def analyze_match(match: dict, quotes: list[dict], now: datetime) -> dict:
    """One contemporaneous quote per independent bookmaker; arithmetic mean.

    Overlapping markets from a single book are not independent inputs. If a
    source has more than one distinct matching event, exclude that source.
    """
    candidates: dict[str, list[tuple[dict, bool]]] = {}
    for quote in quotes:
        orientation = match_orientation(match, quote)
        if orientation is None or not eligible_quote(quote, now):
            continue
        candidates.setdefault(quote["source_id"], []).append((quote, orientation))

    selected: list[dict] = []
    excluded_sources: list[str] = []
    for source_id, items in sorted(candidates.items()):
        if len({item[0]["event_id"] for item in items}) > 1:
            excluded_sources.append(source_id)
            continue
        quote, reverse = max(items, key=lambda item: item[0]["observed_at"])
        a, b = (quote["odds_b"], quote["odds_a"]) if reverse else (quote["odds_a"], quote["odds_b"])
        selected.append({"quote_id": quote["id"], "source_id": source_id, "reversed": reverse, **no_vig(a, b)})

    if not selected:
        return {
            "status": "unverified", "method": None, "probability_a": None,
            "probability_b": None, "fair_odds_a": None, "fair_odds_b": None,
            "source_count": 0, "inputs": [], "spread": None,
            "excluded_sources": excluded_sources,
        }
    probability_a = mean(item["probability_a"] for item in selected)
    probability_b = 1 - probability_a
    return {
        "status": "calculated", "method": "equal_bookmaker_proportional_no_vig",
        "probability_a": probability_a, "probability_b": probability_b,
        "fair_odds_a": 1 / probability_a, "fair_odds_b": 1 / probability_b,
        "source_count": len(selected), "inputs": selected,
        "spread": max(item["probability_a"] for item in selected) - min(item["probability_a"] for item in selected),
        "excluded_sources": excluded_sources,
    }
