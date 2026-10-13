#!/usr/bin/env python3
"""Read-only release audit. Source-link presence is NOT live source verification."""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_FIXTURE_HOSTS = {'play.hotspawn.com', 'www.hotspawn.com', 'hotspawn.com'}


def utc(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def safe_url(value, hosts=None):
    if not isinstance(value, str):
        return False
    try:
        u = urlsplit(value)
        return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password and (hosts is None or u.hostname in hosts)
    except ValueError:
        return False


def probability_pair(a, b):
    return (all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 <= x <= 100 for x in (a, b))
            and abs(a + b - 100) <= .2)


def audit_snapshot(data, now=None):
    now = now or datetime.now(timezone.utc)
    issues, rows, seen = [], [], set()
    def issue(code, detail, match_id=None, severity='review'):
        issues.append(dict(code=code, detail=detail, match_id=match_id, severity=severity))
    meta = data.get('meta', {})
    stamp = utc(meta.get('hotspawn_snapshot_utc'))
    if not stamp:
        issue('RA91-TIME', 'Fixture capture timestamp missing or invalid.', severity='error')
    elif stamp > now:
        issue('RA91-FUTURE', 'Capture timestamp is in the future.', severity='error')
    elif (now - stamp).total_seconds() > 21600:
        issue('RA91-STALE', 'Fixture snapshot is over six hours old; current coverage is unconfirmed.')
    matches = data.get('matches')
    if not isinstance(matches, list):
        return {'rows': [], 'issues': issues + [dict(code='RA91-SCHEMA', detail='Missing matches array.', severity='error', match_id=None)], 'counts': {}, 'source_snapshot_utc': meta.get('hotspawn_snapshot_utc')}
    for r in matches:
        if r.get('sport') != 'cs2':
            continue
        mid = str(r.get('match_id', ''))
        if not mid or mid in seen:
            issue('RA91-ID', 'Missing or duplicate CS2 fixture ID.', mid, 'error')
        seen.add(mid)
        if not safe_url(r.get('hotspawn_page'), OFFICIAL_FIXTURE_HOSTS):
            issue('RA91-SOURCE', 'Official fixture source link is missing or unsafe.', mid, 'error')
        for key in ('start_utc', 'lock_utc'):
            if not utc(r.get(key)):
                issue('RA91-TIME', f'{key} is missing or invalid.', mid, 'error')
        for key in ('team_a', 'team_b'):
            if not isinstance(r.get(key), str) or not r[key].strip():
                issue('RA91-TEAM', f'{key} missing.', mid, 'error')
        a, b = r.get('market_p_a_pct'), r.get('market_p_b_pct')
        market = a is not None or b is not None
        if market:
            if not probability_pair(a, b):
                issue('RA91-MATH', 'Market percentages are not a valid complementary pair.', mid, 'error')
            sources = r.get('market_sources') or []
            if not sources:
                issue('RA91-MARKET', 'Market probability has no raw external source observations.', mid, 'error')
            computed = []
            for source in sources:
                url = source.get('url')
                if not safe_url(url) or urlsplit(url).hostname in OFFICIAL_FIXTURE_HOSTS:
                    issue('RA91-MARKET', 'Market source is missing, unsafe, or Hotspawn (prohibited).', mid, 'error')
                if not utc(source.get('fetched_utc')):
                    issue('RA91-MARKET-TIME', 'Market observation timestamp missing; freshness unconfirmed.', mid)
                x, y = source.get('odds_a'), source.get('odds_b')
                if all(isinstance(o, (int, float)) and not isinstance(o, bool) and math.isfinite(o) and o > 1 for o in (x, y)):
                    computed.append(100 * (1/x) / (1/x + 1/y))
                else:
                    issue('RA91-ODDS', 'Raw odds must be finite decimal prices greater than one.', mid, 'error')
            if computed and isinstance(a, (int, float)) and abs(sum(computed)/len(computed) - a) > .2:
                issue('RA91-MATH', 'Market probability cannot be reproduced from the external raw prices.', mid, 'error')
        else:
            issue('RA91-NOMARKET', 'No external market probability in this snapshot. Blank is intentional.', mid)
        x, y = r.get('own_model_p_a_pct'), r.get('own_model_p_b_pct')
        own = x is not None or y is not None
        if own:
            if not probability_pair(x, y):
                issue('RA91-MATH', 'Model percentages are not a valid complementary pair.', mid, 'error')
            inputs = r.get('model_inputs') or []
            if not inputs or any(not safe_url(i.get('url')) for i in inputs):
                issue('RA91-MODEL-SOURCE', 'Model probability lacks linked inputs.', mid, 'error')
            issue('RA91-MODEL', 'Rating-model estimate, not a verified win frequency; source values and calibration require review.', mid)
        if not market and not own and r.get('pick'):
            issue('RA91-PICK', 'Pick published without any probability.', mid, 'error')
        if r.get('pick') and r['pick'] not in (r.get('team_a'), r.get('team_b')):
            issue('RA91-PICK', 'Pick does not name a participating team.', mid, 'error')
        for key in r:
            if 'crowd' in key.lower() or key.lower() in ('picked_pct_a', 'picked_pct_b'):
                issue('RA91-CROWD', 'Crowd metadata present in analysis output; inspect prohibited input use.', mid, 'error')
        lock = utc(r.get('lock_utc'))
        rows.append(dict(match_id=mid, team_a=r.get('team_a'), team_b=r.get('team_b'), competition=r.get('competition'),
                         source_url=r.get('hotspawn_page'), lock_utc=r.get('lock_utc'), market=market, model=own,
                         open=bool(lock and lock > now), source_values_live_verified=False))
    if not rows:
        issue('RA91-EMPTY', 'No CS2 rows: complete coverage cannot be established.')
    return dict(source_snapshot_utc=meta.get('hotspawn_snapshot_utc'), rows=rows, issues=issues,
                counts=dict(cs2=len(rows), open=sum(r['open'] for r in rows), market=sum(r['market'] for r in rows),
                            model=sum(r['model'] for r in rows)), live_source_verification=False)


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = set(); self.links = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for key in ('id', 'name'):
            if a.get(key): self.ids.add(a[key])
        for key in ('href', 'src'):
            if a.get(key): self.links.append(a[key])


def audit_links(root):
    parsed = {}
    for p in root.rglob('*.html'):
        if any(part in {'.git', 'node_modules', '.venv', '.cache'} for part in p.relative_to(root).parts): continue
        parser = Links(); parser.feed(p.read_text(encoding='utf-8')); parsed[p.resolve()] = parser
    errors, count = [], 0
    for p, parser in parsed.items():
        for link in parser.links:
            u = urlsplit(link)
            if u.scheme or u.netloc: continue
            count += 1
            # Pages is served below /MaltaProj1/. Site-relative absolute paths are treated accordingly.
            path = unquote(u.path)
            if path.startswith('/MaltaProj1/'): target = root / path[len('/MaltaProj1/'):]
            elif path.startswith('/'): target = root / path.lstrip('/')
            else: target = p.parent / path if path else p
            target = target.resolve()
            if target.is_dir(): target = target / 'index.html'
            reason = None
            if not target.is_relative_to(root.resolve()) or not target.is_file(): reason = 'missing local file'
            elif u.fragment and target in parsed and unquote(u.fragment) not in parsed[target].ids: reason = 'missing DOM fragment'
            if reason: errors.append(dict(page=str(p.relative_to(root)), link=link, reason=reason))
    return dict(html_pages=len(parsed), local_links=count, errors=errors, external_links_live_checked=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, default=ROOT/'status/report.json')
    args = parser.parse_args(); root = args.root.resolve()
    path = root/'today/data/current.json'
    try: snapshot = audit_snapshot(json.loads(path.read_text()))
    except (OSError, ValueError) as e: snapshot = dict(rows=[], counts={}, issues=[dict(code='RA91-READ', detail=str(e), severity='error', match_id=None)])
    report = dict(generated_utc=datetime.now(timezone.utc).isoformat(), evidence_path='today/data/current.json',
                  scope='Structural checks of stored observations only; not line-by-line live factual verification.',
                  snapshot=snapshot, links=audit_links(root))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'counts': snapshot['counts'], 'html_pages': report['links']['html_pages'],
                      'link_errors': len(report['links']['errors']), 'review_findings': len(snapshot['issues'])}, indent=2))
    return int(bool(report['links']['errors'] or any(i['severity'] == 'error' for i in snapshot['issues'])))

if __name__ == '__main__': raise SystemExit(main())
