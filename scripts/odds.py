"""Transparent odds conversion helpers.

Only two-way match-winner markets are de-vigged. These functions do not
produce a model forecast: they normalize the two implied probabilities from
one bookmaker's quoted American prices.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, getcontext
from typing import Any

getcontext().prec = 28


class OddsError(ValueError):
    """Raised when an odds input is missing, malformed, or not two-way-safe."""


def parse_american(value: Any) -> Decimal:
    """Parse a signed American-odds value such as ``+280`` or ``-455``.

    Unsigned values and zero are rejected rather than guessed, since they can
    be confused with decimal odds or malformed source text.
    """

    if isinstance(value, bool) or value is None:
        raise OddsError("American odds must be a signed non-zero number")
    text = str(value).strip().replace("−", "-").replace("＋", "+")
    if not text or text[0] not in "+-":
        raise OddsError(f"American odds must include an explicit sign: {value!r}")
    try:
        odds = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise OddsError(f"Invalid American odds: {value!r}") from exc
    if not odds.is_finite() or odds == 0:
        raise OddsError("American odds must be finite and non-zero")
    return odds


def implied_probability(american_odds: Any) -> Decimal:
    """Return a bookmaker's raw implied probability as a fraction in (0, 1)."""

    odds = parse_american(american_odds)
    hundred = Decimal(100)
    if odds > 0:
        return hundred / (odds + hundred)
    magnitude = -odds
    return magnitude / (magnitude + hundred)


def american_to_decimal(american_odds: Any) -> Decimal:
    """Convert signed American odds to decimal odds, including stake."""

    odds = parse_american(american_odds)
    hundred = Decimal(100)
    if odds > 0:
        return Decimal(1) + odds / hundred
    return Decimal(1) + hundred / (-odds)


def no_vig_two_way(odds_a: Any, odds_b: Any) -> dict[str, Decimal]:
    """Compute no-vig probabilities and overround for a two-outcome market.

    Returned probabilities are fractions, not percentage points. For a
    bookmaker quote, ``p_a + p_b`` is the quoted overround before
    normalization. A draw/three-way market must not be passed to this helper.
    """

    raw_a = implied_probability(odds_a)
    raw_b = implied_probability(odds_b)
    total = raw_a + raw_b
    if total <= 0:
        raise OddsError("The two-way market has no positive implied probability")
    fair_a = raw_a / total
    # Derive the second side as the complement so Decimal rounding cannot make
    # the displayed pair sum to 99.999...%.
    fair_b = Decimal(1) - fair_a
    return {
        "raw_a": raw_a,
        "raw_b": raw_b,
        "overround": total - Decimal(1),
        "fair_a": fair_a,
        "fair_b": fair_b,
    }


def as_percent(value: Decimal, places: int = 2) -> Decimal:
    """Convert a fractional probability to percentage points."""

    quantum = Decimal(1).scaleb(-places)
    return (value * Decimal(100)).quantize(quantum)
