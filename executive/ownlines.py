#!/usr/bin/env python3
"""Own-line origination for every fixture on the Hotspawn board — session arena/1b6ae823.

Why this module exists
----------------------
The board's headline probability is always an outside market price where one exists (tiers 1-2 of
``build.py``).  This module adds two things the brief asks for on top of that:

1. **An originated line for every fixture**, not only for the unpriced ones.  Two official inputs are
   used, in this order, and only ever with the file they came from printed on the row:
     * the official Valve Regional Standings points file (already loaded by ``collect.py``);
     * the official HLTV.org world ranking (rank number only — the points column is not used because
       HLTV publishes no published scale for it).
2. **A research basis for fixtures no betting site prices** (low-tier CCT / Elisa / qualifier matches).
   When neither a market line nor a VRS pair exists, a 5th tier is published: the HLTV-rank logistic,
   converted to the length of the series when a source states one.

Missing official ranks and missing series formats stay blank. Absence from a ranking does not
establish a strength bound. All probabilities here are project estimates, not official forecasts.

All functions are pure and re-derivable: ``tests/test_1b6ae823.py`` recomputes every published number
from the stored inputs and fails the build if a page disagrees.

Series maths (classic, exact, no fitting)
-----------------------------------------
For a best-of-(2n+1) series where each map is won independently with probability ``p``::

    BO1 = p
    BO3 = 3p^2 - 2p^3
    BO5 = 10p^3 - 15p^4 + 6p^5

Those are the closed forms of the negative-binomial "first to n+1 maps" sums, and the invariant suite
checks them against the enumerated sums (not against themselves).
"""
from __future__ import annotations

import math
from typing import Any, Iterable

# ------------------------------------------------------------------ constants
DEFAULT_RANK_SCALE = 100.0      # HLTV rank positions that correspond to a 90% per-map favourite
RATIO_POINTS = 400.0            # official VRS convention: 400 points = 90% (Valve's own glicko.js)
CALIBRATION_MIN_SAMPLES = 4     # below this the fitted scale is not published, the default is kept
CALIBRATION_GRID = range(5, 401)  # rank positions per 90% favourite, searched in unit steps

BO_MAPS = {1: 1, 3: 2, 5: 3, 7: 4}
BO_LABELS = {1: "BO1", 3: "BO3", 5: "BO5", 7: "BO7"}


# ------------------------------------------------------------------ series maths
def maps_to_win(best_of: int) -> int:
    """Maps a side must take to win the series (``BO7`` → 4).  Unknown lengths fall back to 1."""
    try:
        bo = int(best_of)
    except (TypeError, ValueError):
        return 1
    return BO_MAPS.get(bo, 1)


def series_probability(p_map: float, best_of: int) -> float:
    """Probability of winning a best-of-N series given an independent per-map win probability."""
    if p_map is None:
        return None  # type: ignore[return-value]
    p = min(max(float(p_map), 0.0), 1.0)
    first_to = maps_to_win(best_of)
    total = 0.0
    # Exact negative-binomial sum: win the deciding map, having taken (first_to-1) of the preceding
    # (first_to + k - 1) maps.  Computed with logs so long series do not overflow.
    for k in range(first_to):                      # k = maps won by the opponent
        n = first_to - 1 + k
        log_choice = sum(math.log(n - i) - math.log(i + 1) for i in range(first_to - 1))
        total += math.exp(log_choice) * (p ** (first_to - 1)) * ((1 - p) ** k) * p
    return min(max(total, 0.0), 1.0)


def format_to_best_of(value: Any) -> int | None:
    """``"BO3"``/``"bo1"``/``3`` → 1, 3, 5, 7.  Anything unrecognised stays ``None`` (blank)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        n = int(value)
        return n if n in BO_MAPS else None
    text = str(value).strip().upper()
    if not text:
        return None
    if text.isdigit():
        n = int(text)
        return n if n in BO_MAPS else None
    # "3.0" (a float serialised from a CSV) is the same answer as 3; "BO5" is found by its digits.
    if all(ch.isdigit() or ch == "." for ch in text):
        try:
            n = int(float(text))
        except ValueError:
            return None
        return n if n in BO_MAPS else None
    digits = "".join(ch for ch in text if ch.isdigit())
    if digits:
        n = int(digits)
        return n if n in BO_MAPS else None
    return None


# ------------------------------------------------------------------ ratings → probability
def logit_ratio(rank_a: float, rank_b: float, scale: float) -> float:
    """Probability that side A beats side B from two rating values, higher rating is better.

    ``p = 1 / (1 + 10^((R_b - R_a)/scale))`` — the same logistic the official VRS model file uses.
    Ranks are inverted by the caller (a *smaller* rank number is better), so both inputs are already
    in "higher is better" units.
    """
    if rank_a is None or rank_b is None or not scale:
        return None  # type: ignore[return-value]
    return 1.0 / (1.0 + 10.0 ** ((float(rank_b) - float(rank_a)) / float(scale)))


def rating_strength(points: float) -> float:
    """Convert VRS points to a monotone strength value usable by :func:`logit_ratio`."""
    return float(points)


def rank_strength(rank: float, floor: float) -> float:
    """Convert an HLTV rank number (1 = best) into a strength where *higher is better*.

    ``floor`` is the number of teams in that same official list, so the arithmetic stays in
    "rank positions" and the published scale is directly interpretable ("100 places ≈ 90%").
    """
    return float(floor) - float(rank)


# ------------------------------------------------------------------ calibration
def calibrate_scale(samples: Iterable[tuple[float, float]]) -> dict:
    """Choose the rank scale that reproduces the outside market most closely.

    ``samples`` is an iterable of ``(rank_difference, market_probability_a)`` pairs, where
    ``rank_difference = strength_a - strength_b`` in rank positions and ``market_probability_a`` is a
    de-vigged, externally sourced probability.  The fitted value is the grid point with the lowest
    mean absolute error; ties resolve to the smallest scale so the result is deterministic.
    """
    data = [(float(s[0]), float(s[1]), int(s[2]) if len(s) > 2 else 1) for s in samples]
    if len(data) < CALIBRATION_MIN_SAMPLES:
        return {"scale": DEFAULT_RANK_SCALE, "fitted": False, "n": len(data),
                "mae_pp": None, "reason": f"only {len(data)} calibration pairs (<{CALIBRATION_MIN_SAMPLES})"}
    best = None
    for scale in CALIBRATION_GRID:
        errors = [abs(series_probability(logit_ratio(dr, 0.0, scale), bo) - p) * 100.0 for dr, p, bo in data]
        mae = sum(errors) / len(errors)
        if best is None or mae < best[1] - 1e-12:
            best = (scale, mae)
    scale, mae = best
    return {"scale": float(scale), "fitted": True, "n": len(data), "mae_pp": round(mae, 3),
            "default_scale": DEFAULT_RANK_SCALE,
            "reason": "grid search 5-400 rank positions per 90% favourite, minimum mean absolute error"}


# ------------------------------------------------------------------ the line itself
def originate(rows: list[dict], ranking: dict, ranking_rows: list[dict],
              market_by_id: dict[str, float]) -> dict:
    """Attach an originated line to every row and promote unpriced rows to the research tier.

    Mutates ``rows`` (each is the dict ``build.analyse`` returned) and returns the board-level
    calibration metadata that is printed on the pages and re-checked by the tests.

    ``market_by_id`` maps ``match_id`` → de-vigged probability for team A from an outside source and is
    used *only* to fit the rank scale — never to fill a gap.
    """
    from evidence import rating_is_recent
    from datetime import datetime, timezone
    # The build supplies its clock so replaying stored evidence is deterministic.
    clock = next((r.get("_build_now") for r in rows if r.get("_build_now")), datetime.now(timezone.utc))
    ranking_recent = rating_is_recent(ranking.get("ranking_date"), clock)
    ranked = [int(t["rank"]) for t in ranking_rows if str(t.get("rank", "")).isdigit()]
    rank_floor = max(ranked) if ranked else 0
    rank_count = len(ranked)

    def rating_pair(row: dict) -> tuple[dict, dict]:
        return row["rating_a"], row["rating_b"]

    def rank_of(record: dict) -> tuple[float | None, bool]:
        """(strength in rank positions, was-a-bound) for one team's official HLTV rank."""
        raw = str(record.get("hltv_rank") or "").strip()
        if raw.isdigit() and ranking_recent:
            return rank_strength(int(raw), rank_floor), False
        return None, False

    # ---- calibration from the rows that an outside market prices
    diffs: list[tuple[float, float]] = []
    for row in rows:
        if int(row.get("basis_tier") or 0) not in (1, 2):
            continue
        prob = market_by_id.get(row["match_id"])
        if prob is None:
            continue
        a, b = rating_pair(row)
        sa, bound_a = rank_of(a)
        sb, bound_b = rank_of(b)
        if sa is None or sb is None or bound_a or bound_b:
            continue
        bo = format_to_best_of(row.get("series_format"))
        if bo:
            diffs.append((sa - sb, prob, bo))
    calibration = calibrate_scale(diffs)
    scale = calibration["scale"]

    def series_of(row: dict) -> int:
        bo = format_to_best_of(row.get("series_format"))
        return bo

    for row in rows:
        a, b = rating_pair(row)
        flags = list(row.get("flags") or [])
        sa, bound_a = rank_of(a)
        sb, bound_b = rank_of(b)
        bo = series_of(row)
        if not ranking_recent:
            flags.append("FL-RATING-EXPIRED")
        info = {"best_of": bo, "scale": scale, "fitted": calibration["fitted"],
                "rank_floor": rank_floor, "rank_count": rank_count,
                "rank_a": a.get("hltv_rank", ""), "rank_b": b.get("hltv_rank", ""),
                "bound_a": bound_a, "bound_b": bound_b,
                "p_map": None, "p_series": None, "method": "", "sources": [], "detail": ""}

        if sa is not None and sb is not None and bo is not None:
            p_map = logit_ratio(sa, sb, scale)
            info["p_map"] = p_map
            info["p_series"] = series_probability(p_map, bo)
            info["method"] = "HLTV world-rank logistic"
            rank_url = ranking.get("canonical_url") or "https://www.hltv.org/ranking/teams"
            info["sources"] = [(a.get("hltv_url") or rank_url, f"{a.get('team')} (HLTV rank)"),
                              (b.get("hltv_url") or rank_url, f"{b.get('team')} (HLTV rank)"),
                              (rank_url, "official HLTV world ranking")]
            parts = [f"ranks {a.get('hltv_rank') or '—'} vs {b.get('hltv_rank') or '—'} "
                     f"(official HLTV ranking, {ranking.get('ranking_date') or 'date not read'}), "
                     f"{scale:g} places per 90% "
                     f"({'fitted on ' + str(calibration['n']) + ' priced fixtures' if calibration['fitted'] else 'documented default'}), "
                     f"per-map p = 1/(1+10^((rb-ra)/{scale:g})) = {p_map * 100:.1f}%"]
            if bo in (3, 5, 7):
                parts.append(f"converted to {BO_LABELS[bo]}: p = {info['p_series'] * 100:.1f}%")
            if bound_a or bound_b:
                flags.append("FL-RANK-FLOOR-BOUND")
                parts.append(f"one side is absent from that ranking, so {rank_floor + 1} "
                             f"(one place below the last ranked team) is used as a conservative bound")
            info["detail"] = "; ".join(parts)
        else:
            flags.append("FL-RANK-MISSING" if sa is None or sb is None else "FL-FORMAT-UNKNOWN")
            info["method"] = "not originated — inputs unverified"
            info["detail"] = "Both sourced ranks and a confirmed series format are required; missing inputs stay blank."
        if rank_floor == 0:
            flags.append("FL-NO-HLTV-RANKING")
            info["method"] = "no official ranking read"
            info["detail"] = ("The official HLTV world ranking was not readable this run, so no rank line "
                              "could be originated. Nothing was substituted.")

        # VRS line (the existing tier-3 arithmetic) is kept alongside as a cross-check.
        vrs_a, vrs_b = a, b
        if vrs_a.get("vrs_points") and vrs_b.get("vrs_points") and bo is not None:
            p_vrs = logit_ratio(float(vrs_a["vrs_points"]), float(vrs_b["vrs_points"]), RATIO_POINTS)
            info["vrs_p_series"] = series_probability(p_vrs, bo)
            info["vrs_p_map"] = p_vrs
        else:
            info["vrs_p_series"] = None
            info["vrs_p_map"] = None

        row["own"] = info
        row["flags"] = sorted(set(flags))

        # ---- promotion: a fixture with no market line and no VRS pair gets the research line
        if int(row.get("basis_tier") or 0) == 0 and info["p_series"] is not None:
            p_a = info["p_series"]
            row["basis_tier"] = 5
            row["basis_label"] = "Research · official ranking line"
            row["prob_a_pct"] = f"{p_a * 100:.1f}"
            row["prob_b_pct"] = f"{(1 - p_a) * 100:.1f}"
            row["model_prob_a_pct"] = f"{p_a * 100:.1f}"
            row["model_prob_b_pct"] = f"{(1 - p_a) * 100:.1f}"
            row["basis_detail"] = info["detail"]
            row["basis_sources"] = info["sources"]
            row["confidence"] = "Low (our line, uncalibrated)"
            flags.append("FL-RESEARCH-BASIS")
            if bound_a or bound_b:
                flags.append("FL-RANK-FLOOR-BOUND")
            row["flags"] = sorted(set(flags))
            pick = ("(no side — 50/50)" if abs(p_a - 0.5) < 0.0025 else
                    row["team_a"] if p_a > 0.5 else row["team_b"])
            row["pick"] = pick
            row["pick_prob_pct"] = f"{max(p_a, 1 - p_a) * 100:.1f}" if pick != "(no side — 50/50)" else ""

    return {"calibration": calibration, "rank_floor": rank_floor, "rank_count": rank_count,
            "ranking_date": ranking.get("ranking_date"), "ranking_mode": ranking.get("mode"),
            "default_scale": DEFAULT_RANK_SCALE, "min_samples": CALIBRATION_MIN_SAMPLES,
            "ratio_points": RATIO_POINTS}


__all__ = ["series_probability", "format_to_best_of", "logit_ratio", "rank_strength",
           "calibrate_scale", "originate", "maps_to_win", "DEFAULT_RANK_SCALE", "RATIO_POINTS",
           "BO_LABELS"]
