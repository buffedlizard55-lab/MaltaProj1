"""Fail-closed evidence policy. Source facts and project estimates are distinct.

A missing rank is NOT a worst rank; a missing series length is NOT BO1.
Absence of a market in our read is NOT evidence that no bookmaker offers it.
"""
from __future__ import annotations

import math
from datetime import timedelta
from urllib.parse import urlsplit

from common import parse_iso

MAX_QUOTE_HOURS = 8
MAX_RATING_DAYS = 14


def quote_rejection(quote: dict, now) -> str:
    stamp = parse_iso(quote.get('captured_utc'))
    if not stamp or not -300 <= (now - stamp).total_seconds() <= MAX_QUOTE_HOURS * 3600:
        return 'missing, future or older-than-8h quote timestamp'
    if quote.get('market_type') != 'match_winner':
        return 'market is not explicitly whole-match winner'
    if str(quote.get('status', '')).lower() not in ('open', 'active', 'trading', 'online'):
        return 'market status not confirmed open'
    url = quote.get('source_url') or ''
    host = urlsplit(url).hostname or ''
    if not url.startswith('https://') or host.endswith('hotspawn.com'):
        return 'missing independent HTTPS price source'
    if quote.get('match_quality') == 'alias':
        return 'market identity uses a manually asserted alias; requires renewed exact-identity evidence'
    for side in ('a', 'b'):
        try:
            odds = float(quote['odds_' + side])
        except (KeyError, ValueError, TypeError):
            return 'missing two-sided decimal price'
        if not math.isfinite(odds) or odds <= 1:
            return 'invalid decimal price'
    return ''


def split_quotes(quotes, now):
    accepted, rejected = [], []
    for quote in quotes:
        reason = quote_rejection(quote, now)
        if reason:
            rejected.append({**quote, 'rejection_reason': reason})
        else:
            accepted.append(quote)
    return accepted, rejected


def rating_is_recent(date, now):
    stamp = parse_iso(date)
    return bool(stamp and timedelta(days=-1) <= now - stamp <= timedelta(days=MAX_RATING_DAYS))


def slate_health(hotspawn, now):
    stamp = parse_iso(hotspawn.get('fetched_utc'))
    age = (now - stamp).total_seconds() / 3600 if stamp else None
    pages = hotspawn.get('pages') or []
    required = ('https://play.hotspawn.com/lobby', 'https://play.hotspawn.com/cs2-pickems')
    successful = {p.get('url') for p in pages if p.get('http_status') == 200 and p.get('fixture_count')}
    complete = hotspawn.get('mode') == 'live' and all(u in successful for u in required)
    conflicts = hotspawn.get('identity_conflicts') or []
    return {'mode': hotspawn.get('mode'), 'fetched_utc': hotspawn.get('fetched_utc'),
            'age_hours': round(age, 3) if age is not None else None,
            'complete_live_read': bool(complete and not conflicts),
            'current': bool(complete and not conflicts and age is not None and 0 <= age <= 8),
            'identity_conflicts': conflicts,
            'limitation': '' if complete and not conflicts else
            'Current full coverage is unverified: both lobby and CS2 source reads must succeed with no identity conflict. Saved fixtures remain visible with their original timestamp.'}
