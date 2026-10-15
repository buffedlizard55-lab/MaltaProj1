#!/usr/bin/env python3
"""Line-by-line arithmetic/identity audit against preserved source projections.

This does not claim that a URL's existence verifies a prediction. Source capture
facts, model assumptions and live-coverage limitations are reported separately.
"""
import json
from datetime import datetime, timezone
from common import DATA, devig_pair, parse_iso, write_json, norm
from evidence import quote_rejection


def audit():
    analysis = json.loads((DATA / 'analysis.json').read_text())
    hotspawn = json.loads((DATA / 'hotspawn_pages.json').read_text())
    source = {str(f['id']): f for f in hotspawn['fixtures']}
    rows = analysis['fixtures']
    quotes = []
    for name in ('pinnacle.json', 'secondary_lines.json', 'research_lines.json'):
        quotes.extend(json.loads((DATA / name).read_text()).get('quotes') or [])
    now = parse_iso(analysis['generated_utc'])
    results, errors = [], []
    if set(source) != set(rows):
        errors.append('Source fixture IDs do not exactly equal published fixture IDs')
    for mid, r in rows.items():
        f = source.get(mid, {})
        issues = []
        for side, field in (('a', 'participants0_name'), ('b', 'participants1_name')):
            if r['team_' + side] != f.get(field):
                issues.append('fixture team identity mismatch')
        for key, rawkey in (('start_utc', 'scheduled_start_time'), ('lock_utc', 'lock_time')):
            raw = f.get(rawkey)
            stamp = parse_iso(r.get(key))
            if raw and (not stamp or abs(stamp.timestamp() * 1000 - int(raw)) > 1):
                issues.append(key + ' differs from official epoch')
        tier = int(r['basis_tier'])
        if tier in (1, 2):
            matched = []
            for q in quotes:
                if quote_rejection(q, now) or q.get('captured_utc') != r['market_captured_utc']:
                    continue
                a, b = norm(q.get('team_a')), norm(q.get('team_b'))
                if (a, b) == (norm(r['team_a']), norm(r['team_b'])):
                    oa, ob = q['odds_a'], q['odds_b']
                elif (b, a) == (norm(r['team_a']), norm(r['team_b'])):
                    ob, oa = q['odds_a'], q['odds_b']
                else:
                    continue
                if abs((parse_iso(q['start_time']) - parse_iso(r['start_utc'])).total_seconds()) > 900:
                    continue
                p, _, _ = devig_pair(float(oa), float(ob))
                if abs(p * 100 - float(r['prob_a_pct'])) <= .06:
                    matched.append(q)
            if not matched:
                issues.append('headline quote not reproducible from fresh exact-pair source input')
        if tier in (3, 5) and not r.get('series_format'):
            issues.append('model has no confirmed format')
        if tier == 4 or (r.get('own') or {}).get('bound_a') or (r.get('own') or {}).get('bound_b'):
            issues.append('invented floor bound is forbidden')
        if not r.get('pick') and not r.get('flags'):
            issues.append('missing pick not flagged')
        results.append({'match_id': mid, 'team_a': r['team_a'], 'team_b': r['team_b'],
                        'pick': r['pick'], 'basis_tier': tier, 'status': r['status'],
                        'fixture_source': r['hotspawn_match_url'] or r['hotspawn_pickem_url'],
                        'fixture_read_utc': hotspawn.get('fetched_utc'),
                        'price_read_utc': r.get('market_captured_utc'),
                        'sources': r['basis_sources'], 'flags': r['flags'],
                        'verification': 'passed' if not issues else 'failed', 'errors': issues})
        errors.extend(mid + ': ' + i for i in issues)
    report = {'generated_utc': analysis['generated_utc'], 'rows_checked': len(results),
              'errors': errors, 'rows': results,
              'limitation': 'Stored-input audit, not a live reread or independent validation of forecasting accuracy. See provenance.json for live attempts and source refusals.'}
    write_json(DATA / 'row_verification.json', report)
    return report


if __name__ == '__main__':
    result = audit()
    print(json.dumps({'rows_checked': result['rows_checked'], 'errors': result['errors']}))
    raise SystemExit(bool(result['errors']))
