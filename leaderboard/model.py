"""Pure probability helpers for the contrarian leaderboard plan — session arena/2e2b2e5e.

Nothing in this module reads Hotspawn crowd data. Probabilities come from outside prices (de-vigged)
or from official rating points (Valve Regional Standings). Crowd shares enter only
``contrarian()``, which measures how *different* a pick is from the field — never how likely it is.
"""
from __future__ import annotations

import math

# Valve's VRS model file (model/glicko.js in ValveSoftware/counter-strike_regional_standings) uses the
# Elo convention "400 points = 90% chance of victory" (10^(400/400) = 10:1). We keep that convention
# and calibrate a single shrink factor k on live bookmaker lines (see fit_k).
VRS_SCALE = 400.0
DEFAULT_K = 0.55          # used only when fewer than MIN_CAL calibration pairs exist
MIN_CAL = 8


def american_to_decimal(price: float) -> float:
    value = float(price)
    if value >= 100:
        return 1.0 + value / 100.0
    if value <= -100:
        return 1.0 + 100.0 / abs(value)
    raise ValueError(f"not an American price: {price!r}")


def devig(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    """Multiplicative (proportional) de-vig of a two-way decimal price. Returns (p_a, p_b, margin%)."""
    odds_a, odds_b = float(odds_a), float(odds_b)
    if odds_a <= 1.0 or odds_b <= 1.0:
        raise ValueError("decimal odds must be > 1")
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    total = ia + ib
    return ia / total, ib / total, (total - 1.0) * 100.0


def normalize_pair(p_a: float, p_b: float) -> tuple[float, float]:
    """Normalize two prediction-market prices (USD 0-1 shares) to probabilities summing to 1."""
    p_a, p_b = float(p_a), float(p_b)
    if p_a < 0 or p_b < 0 or p_a + p_b <= 0:
        raise ValueError("invalid prices")
    return p_a / (p_a + p_b), p_b / (p_a + p_b)


def series_prob(p_map: float, best_of: int | None) -> float:
    """Probability of winning a best-of-N series given an independent per-map probability."""
    p = min(max(float(p_map), 1e-9), 1 - 1e-9)
    if best_of in (None, 1):
        return p
    need = best_of // 2 + 1
    q = 1 - p
    total = 0.0
    # P(win `need` maps before the opponent wins `need`).
    for losses in range(need):
        total += math.comb(need - 1 + losses, losses) * (p ** need) * (q ** losses)
    return total


def vrs_line(points_a: float, points_b: float, best_of: int | None, k: float = DEFAULT_K) -> float:
    """Our own line from official Valve VRS points: per-map Elo with shrink k, then series transform."""
    diff = (float(points_a) - float(points_b)) * k
    p_map = 1.0 / (1.0 + 10 ** (-diff / VRS_SCALE))
    return series_prob(p_map, best_of)


def log_loss(p: float, target: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(target * math.log(p) + (1 - target) * math.log(1 - p))


def fit_k(pairs: list[dict]) -> tuple[float, int, float | None]:
    """Fit the VRS shrink factor on (points_a, points_b, best_of, market_p_a) rows.

    Minimises cross-entropy between our line and the de-vigged market probability. Returns
    (k, n, mean absolute error in percentage points). Falls back to DEFAULT_K below MIN_CAL rows.
    """
    rows = [r for r in pairs if r.get("points_a") is not None and r.get("points_b") is not None
            and r.get("market_p_a") is not None]
    if len(rows) < MIN_CAL:
        mae = (sum(abs(vrs_line(r["points_a"], r["points_b"], r.get("best_of")) - r["market_p_a"]) for r in rows)
               / len(rows) * 100) if rows else None
        return DEFAULT_K, len(rows), mae
    best_k, best_loss = DEFAULT_K, float("inf")
    k = 0.10
    while k <= 1.50 + 1e-9:
        loss = sum(log_loss(vrs_line(r["points_a"], r["points_b"], r.get("best_of"), k), r["market_p_a"]) for r in rows)
        if loss < best_loss:
            best_k, best_loss = round(k, 3), loss
        k += 0.01
    mae = sum(abs(vrs_line(r["points_a"], r["points_b"], r.get("best_of"), best_k) - r["market_p_a"]) for r in rows) / len(rows) * 100
    return best_k, len(rows), mae


def contrarian(p_a: float, points: int | None, crowd_a: float | None, crowd_b: float | None) -> dict:
    """Leaderboard leverage for one match. p_a is OUR probability; crowd values only measure ownership.

    Returns the favourite/underdog split, the expected-points cost of taking the underdog, the
    leverage ratio (our underdog probability / share of players on the underdog) and a label:

    * ``value``  — underdog >= 40% and <= 35% of the field on it: cheap, sensible contrarian pick.
    * ``upset``  — underdog 25-40% and leverage >= 3: high-variance shot for players chasing the top.
    * ``chalk``  — everything else: take the favourite.
    """
    pts = points or 0
    fav_is_a = p_a >= 0.5
    p_fav = p_a if fav_is_a else 1 - p_a
    p_dog = 1 - p_fav
    out = {"fav": "a" if fav_is_a else "b", "dog": "b" if fav_is_a else "a", "p_dog": p_dog,
           "ev_cost": pts * (p_fav - p_dog), "crowd_dog": None, "leverage": None, "label": "chalk"}
    if crowd_a is None or crowd_b is None or (crowd_a + crowd_b) <= 0:
        out["label"] = "no crowd data"
        return out
    total = float(crowd_a) + float(crowd_b)
    crowd_dog = (float(crowd_b) if fav_is_a else float(crowd_a)) / total
    out["crowd_dog"] = crowd_dog
    out["leverage"] = (p_dog / crowd_dog) if crowd_dog > 0 else float("inf")
    if p_dog >= 0.40 and crowd_dog <= 0.35:
        out["label"] = "value"
    elif p_dog >= 0.25 and out["leverage"] >= 3.0:
        out["label"] = "upset"
    return out
