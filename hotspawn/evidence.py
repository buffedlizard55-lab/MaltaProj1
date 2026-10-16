"""Strict, deterministic fixture/market identity checks (no network, no crowd inputs).

The six-hour tolerance accommodates documented schedule drift, NOT interchangeable same-day matches.
A quote must name both teams, the same competition family, a whole-match scope, a usable read time,
and an unambiguous nearest fixture. Missing evidence rejects a quote; nothing is guessed.
"""
from __future__ import annotations
import re
from common import fold, hours_between, parse_iso, devig_two_way, normalise_prices
from urllib.parse import urlsplit

MAX_PRICE_AGE_H = 8.0
MAX_KICKOFF_GAP_H = 6.0


def event_key(text: str) -> tuple[str, str, str]:
    t = re.sub(r"[^a-z0-9]+", " ", fold(text))
    t = re.sub(r"\b(?:counter strike|cs2|csgo)\b", " ", t)
    # Public guest-feed abbreviations cross-checked against the same Hotspawn fixtures and times.
    t = re.sub(r"\bstk pulse beat\b", "stake pulse beat", t)
    t = re.sub(r"\btp world championship\b", "thunderpick world championship", t)
    family = next((v for k, v in (
        ('thunderpick', 'thunderpick'), ('elisa', 'elisa'), ('nodwin', 'nodwin'),
        ('clutch series', 'nodwin'), ('stake pulse', 'stake pulse'), ('draculan', 'draculan'),
        ('cct', 'cct'), ('european pro league', 'epl'), ('svenska', 'svenska')) if k in t), '')
    region = next((v for k, v in (('south america', 'sa'), ('south american', 'sa'),
                  ('north america', 'na'), ('europe', 'eu')) if k in t), '')
    # Do not mistake the year for an edition number. A missing edition is not filled in.
    n = re.search(r'(?:series|season|challengers|breakout)\s*(\d{1,3})\b', t)
    edition = n.group(1) if n else ''
    return family or re.sub(r'\b20\d{2}\b', '', t).strip(), region, edition


def event_compatible(fixture_event: str, quote_event: str) -> bool:
    if not fixture_event or not quote_event:
        return False
    a, b = event_key(fixture_event), event_key(quote_event)
    if a[0] != b[0]:
        return False
    if a[1] and b[1] and a[1] != b[1]:
        return False
    if a[2] and b[2] and a[2] != b[2]:
        return False
    # The main LAN is not a regional Thunderpick qualifier of the same name.
    if a[0] == 'thunderpick' and a[1] != b[1]:
        return False
    return True


def select_quote(fx: dict, quotes: list[dict], aliases, reference: str | None = None,
                 fixtures: list[dict] | None = None, rejections: list[dict] | None = None,
                 expected_format: str | None = None, require_price: bool = True):
    """Return the freshest nearest eligible quote plus alias flag, recording every same-pair rejection."""
    ka, kb = aliases.key(fx.get('team_a', '')), aliases.key(fx.get('team_b', ''))
    eligible = []
    for q in quotes or []:
        qa, qb = aliases.key(q.get('team_a', '')), aliases.key(q.get('team_b', ''))
        if not ka or ka == kb or {qa, qb} != {ka, kb}:
            continue
        reasons = []
        context = q.get('event') or q.get('league') or q.get('tournament')
        if not event_compatible(fx.get('competition', ''), context or ''):
            reasons.append('competition missing or conflicting')
        if not require_price:
            pass # fixture metadata is not a quote and can never become a probability
        elif "odds_a" in q or "odds_b" in q:
            if not devig_two_way(q.get("odds_a"), q.get("odds_b")):
                reasons.append("invalid or missing finite two-sided decimal odds")
        elif "price_a" in q or "price_b" in q:
            if not normalise_prices(q.get("price_a"), q.get("price_b")):
                reasons.append("invalid, terminal or nonbinary outcome prices")
        else:
            reasons.append("missing two-sided price")
        gap = hours_between(q.get('start_utc'), fx.get('start_utc'))
        if gap is None or abs(gap) > MAX_KICKOFF_GAP_H:
            reasons.append('kickoff missing or more than 6 h apart')
        if reference:
            age = hours_between(reference, q.get('read_utc'))
            if age is None or not -1 <= age <= MAX_PRICE_AGE_H:
                reasons.append('quote read time missing, in the future, or older than 8 h')
        if require_price and q.get('market_scope') != 'match_winner':
            reasons.append('not a whole-match winner market')
        if q.get('accepting_orders') is False or q.get('active') is False or q.get('closed') is True:
            reasons.append('market not accepting orders / closed')
        qfmt = q.get('format') or (f"BO{q['best_of']}" if q.get('best_of') in (1, 3, 5, 7) else '')
        if expected_format and qfmt and expected_format.upper() != qfmt.upper():
            reasons.append('series format conflicts with verified fixture format')
        if not parse_iso(q.get('read_utc')):
            reasons.append('unparseable read time')
        source_url = urlsplit(str(q.get('source_url') or ''))
        if source_url.scheme != 'https' or not source_url.hostname:
            reasons.append('missing source URL')
        if gap is not None and not reasons and fixtures:
            peers = [f for f in fixtures if str(f.get('match_id')) != str(fx.get('match_id'))
                     and {aliases.key(f.get('team_a', '')), aliases.key(f.get('team_b', ''))} == {ka, kb}
                     and event_compatible(f.get('competition', ''), context or '')]
            for other in peers:
                other_gap = hours_between(q.get('start_utc'), other.get('start_utc'))
                if other_gap is not None and abs(other_gap) <= abs(gap) + 1 / 60:
                    reasons.append('another listed fixture is equally close or closer (rematch/duplicate)')
                    break
        if reasons:
            if rejections is not None:
                rejections.append({'source': q.get('source'), 'source_url': q.get('source_url'),
                                   'read_utc': q.get('read_utc'), 'listed_start': q.get('start_utc'),
                                   'reasons': list(dict.fromkeys(reasons))})
            continue
        eligible.append({**q, 'flipped': qa != ka, 'gap_h': round(gap, 3)})
    if not eligible:
        return None, False
    # Negative timestamp sorts newest first after distance. No averaging or value-based cherry-picking.
    eligible.sort(key=lambda q: (abs(q['gap_h']), -parse_iso(q['read_utc']).timestamp()))
    best = eligible[0]
    alias = any(aliases.used(n) for n in (fx.get('team_a'), fx.get('team_b'), best.get('team_a'), best.get('team_b')))
    return best, alias


def select_match_metadata(fx, records, aliases, reference, fixtures):
    """A source-linked, dated series format only. Does not fabricate or expose any price."""
    known = [r for r in records if r.get('best_of') in (1,3,5,7)]
    return select_quote(fx, known, aliases, reference, fixtures, require_price=False)[0]
