#!/usr/bin/env python3
"""Research only unsupported open rows: HLTV first, then inspect outside lines.

Normal public browser, no login, challenge solving, proxy or access-control bypass.
Only an exact pair, matching epoch and explicitly printed format may fill a field.
Refusals and kickoff/name discrepancies are published per fixture.
"""
import json
import re
from datetime import datetime, timezone
from common import DATA, norm, parse_iso, write_json
from evidence import quote_rejection


def format_evidence(text, teams, kickoff, row):
    """Never infer format from the event name or another match in the event."""
    if len(teams) != 2 or {norm(t) for t in teams} != {norm(row['team_a']), norm(row['team_b'])}:
        return None, 'HLTV team identity is not an exact pair'
    try:
        stamp = datetime.fromtimestamp(int(kickoff) / 1000, timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None, 'HLTV kickoff is unverified'
    if abs((stamp - parse_iso(row['start_utc'])).total_seconds()) > 900:
        return None, 'HLTV and Hotspawn kickoffs disagree by more than 15 min'
    found = re.search(r'\bBest of ([1357])\b', text, re.I)
    if not found:
        return None, 'HLTV did not explicitly state a supported best-of'
    return int(found[1]), ''


def main():
    from playwright.sync_api import sync_playwright
    analysis = json.loads((DATA / 'analysis.json').read_text())
    missing = [r for r in analysis['fixtures'].values() if r['status'] == 'open' and not r['pick']]
    now = datetime.now(timezone.utc)
    quotes = []
    for name in ('pinnacle.json', 'secondary_lines.json'):
        quotes.extend(json.loads((DATA / name).read_text()).get('quotes') or [])
    report = {'generated_utc': now.isoformat(), 'scope': 'Only open rows without a supported pick',
              'formats': {}, 'rows': []}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for row in missing:
            mid = row['match_id']
            item = {'match_id': mid, 'teams': [row['team_a'], row['team_b']],
                    'hotspawn_source': row['hotspawn_match_url'] or row['hotspawn_pickem_url'],
                    'attempts': [], 'limitations': [], 'outside_candidates': []}
            url = row.get('hltv_match_url')
            if url:
                try:
                    response = page.goto(url, wait_until='domcontentloaded', timeout=25000)
                    status = response.status if response else 0
                    attempt = {'source': 'HLTV match page', 'url': url, 'http_status': status,
                               'read_utc': datetime.now(timezone.utc).isoformat()}
                    if status == 200:
                        teams = page.locator('.teamsBox .teamName').all_text_contents()
                        date = page.locator('.timeAndEvent .date[data-unix]')
                        kickoff = date.first.get_attribute('data-unix') if date.count() else None
                        text = page.locator('.preformatted-text').first.inner_text() if page.locator('.preformatted-text').count() else ''
                        best_of, reason = format_evidence(text, teams, kickoff, row)
                        attempt.update(teams=teams, kickoff_epoch_ms=kickoff, printed_format=text[:500], reason=reason)
                        if best_of:
                            report['formats'][mid] = {'best_of': best_of, 'source_url': url,
                                                     'source_name': 'HLTV exact-match browser read',
                                                     'read_utc': attempt['read_utc']}
                    else:
                        attempt['reason'] = 'Source refused or unavailable; no value substituted'
                    item['attempts'].append(attempt)
                except Exception as exc:
                    item['attempts'].append({'source': 'HLTV', 'url': url, 'http_status': 0,
                                             'reason': type(exc).__name__})
            else:
                item['limitations'].append('No independently matched HLTV match URL')
            # Bookmaker and betting lines were read by collect.py this run; preserve their own stamps.
            for q in quotes:
                pair = {norm(q.get('team_a')), norm(q.get('team_b'))}
                wanted = {norm(row['team_a']), norm(row['team_b'])}
                if not pair.intersection(wanted):
                    continue
                if pair != wanted:
                    continue  # one common team is not a fixture
                reason = quote_rejection(q, now)
                delta = None
                if parse_iso(q.get('start_time')):
                    delta = abs((parse_iso(q['start_time']) - parse_iso(row['start_utc'])).total_seconds()) / 60
                    if delta > 15:
                        reason = f'Kickoff differs from Hotspawn by {delta:g} min; quote not assigned'
                item['outside_candidates'].append({'source_url': q.get('source_url'),
                    'source_name': q.get('source_name'), 'captured_utc': q.get('captured_utc'),
                    'kickoff_difference_min': delta, 'rejection_reason': reason,
                    'odds_a': q.get('odds_a'), 'odds_b': q.get('odds_b')})
            if not item['outside_candidates']:
                item['limitations'].append('No exact-pair outside quote was retrieved; variant names are not silently equated')
            item['limitations'].append('Missing rank, identity or confirmed format remains blank. No probability is a verified future outcome.')
            report['rows'].append(item)
        browser.close()
    write_json(DATA / 'fallback_research.json', report)
    print(json.dumps(report))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
