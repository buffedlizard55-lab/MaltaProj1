"""Fail-closed identity, freshness and pick rules. No network or crowd inputs."""
from datetime import datetime, timezone
import math

MAX_QUOTE_AGE_HOURS = 6
MAX_KICKOFF_DELTA_SECONDS = 15 * 60


def timestamp(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.astimezone(timezone.utc) if dt.tzinfo else None
    except (ValueError, TypeError):
        return None


def aligned_pair(a, b, x, y, canonical):
    """Exact or explicitly curated canonical names only, never fuzzy similarity."""
    aa, bb, xx, yy = map(canonical, (a, b, x, y))
    if not all((aa, bb, xx, yy)) or aa == bb or xx == yy:
        return None
    if (aa, bb) == (xx, yy):
        return False
    if (aa, bb) == (yy, xx):
        return True
    return None


def kickoff_agrees(a, b):
    aa, bb = timestamp(a), timestamp(b)
    return bool(aa and bb and abs((aa - bb).total_seconds()) <= MAX_KICKOFF_DELTA_SECONDS)


def eligible_market(row, now):
    """Only newly collected primary-book observations may drive the headline pick."""
    captured = timestamp(row.get('captured_utc'))
    if not captured or not 0 <= (now - captured).total_seconds() <= MAX_QUOTE_AGE_HOURS * 3600:
        return False
    if row.get('rank') != 0 or row.get('book') != 'Pinnacle':
        return False
    try:
        return all(math.isfinite(float(row[k])) and float(row[k]) > 1 for k in ('odds_a', 'odds_b'))
    except (KeyError, ValueError, TypeError):
        return False


def pick_probability(market, model, best_of):
    """Market preferred; no arbitrary blend, map-as-match substitution or pick on a tie."""
    if market is not None:
        return market, 'primary bookmaker moneyline (de-vigged)'
    if model is not None and best_of in (1, 3, 5):
        return model, 'provisional own model — confirmed series format; not calibrated'
    return None, 'unverified — no eligible primary quote or confirmed-format model'
