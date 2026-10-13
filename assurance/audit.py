#!/usr/bin/env python3
"""Fail-closed independent audit. Network access can NEVER turn a claim verified.
Only inspected primary-source observations supply quote-derived output values.
Run from any directory; all generated files stay in assurance/.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
from html import escape
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EVIDENCE = HERE / 'observations.json'
REPO = 'https://github.com/buffedlizard55-lab/MaltaProj1'
MAX_PRICE_SUM = 110  # conservative publication policy, NOT a fact about odds quality


def link(url, label):
    if urlparse(url).scheme not in ('https', ''):
        raise ValueError('Unsafe link')
    return f'<a href="{escape(url, quote=True)}">{escape(str(label))}</a>'


def normalize_pair(a, b):
    """Arithmetic only; caller must validate provenance and outcome identity."""
    if any(isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) or x <= 0 for x in (a, b)):
        raise ValueError('Two positive, finite prices required')
    return a / (a + b), b / (a + b)


def rejection_reasons(row):
    reasons = []
    expected = sorted((row['team_a'].casefold(), row['team_b'].casefold()))
    observed = sorted((row['observed_team_a'].casefold(), row['observed_team_b'].casefold()))
    if expected != observed:
        reasons.append('Team names differ; no independently confirmed alias mapping')
    if row.get('conflicting_decimal_pair'):
        reasons.append('Hero and event-list prices disagree in the same inspected page')
    if row['volume_display'] in ('$0.00', '$0'):
        reasons.append('Source displays zero traded volume')
    if row['observed_cents_a'] + row['observed_cents_b'] > MAX_PRICE_SUM:
        reasons.append('Price sum exceeds conservative 110-cent publication limit')
    if not row.get('moneyline_direct_checked'):
        reasons.append('Individual Series Lines / Moneyline section not independently inspected')
    date = row.get('market_date', '')
    if len(date) != 10 or date[5:7] + '/' + date[8:10] != row['displayed_start'].split(',')[0]:
        reasons.append('Market date does not match the inspected displayed fixture day')
    if not row.get('market_competition_checked'):
        reasons.append('Exact market competition not independently checked on the direct page')
    if urlparse(row.get('market_url', '')).hostname != 'polymarket.com':
        reasons.append('Not the inspected primary market publisher')
    return reasons


def analyze(data):
    results = []
    for obs in data['fixtures']:
        row = dict(obs)
        row['reasons'] = rejection_reasons(obs)
        row['probability_a'] = row['probability_b'] = None
        row['fair_decimal_a'] = row['fair_decimal_b'] = None
        row['market_lean'] = None
        if not row['reasons']:
            # Exact case-insensitive outcome names; order is explicit, never assumed.
            a, b = obs['observed_cents_a'], obs['observed_cents_b']
            if obs['team_a'].casefold() != obs['observed_team_a'].casefold():
                a, b = b, a
            pa, pb = normalize_pair(a, b)
            row.update(probability_a=pa, probability_b=pb,
                       fair_decimal_a=1 / pa, fair_decimal_b=1 / pb,
                       market_lean=obs['team_a'] if pa > pb else obs['team_b'] if pb > pa else None)
        row['status'] = 'quote-derived snapshot' if not row['reasons'] else 'needs review'
        results.append(row)
    return results


def audit_repository(data):
    findings = []
    def add(id_, summary, detail, sources, severity='review'):
        findings.append(dict(id=id_, severity=severity, summary=summary, detail=detail, sources=sources, status='needs review'))
    missing = data['reported_cs2_facet_count'] - len(data['fixtures'])
    add('A-01', 'Full fixture coverage is not established',
        f"Only {len(data['fixtures'])} fixture cards were independently inspected; the CS2 facet reports {data['reported_cs2_facet_count']}. Difference: {missing}. A facet count is not an extracted pairing list. Do not invent the missing pairings or assume pagination mechanics without network evidence.",
        [data['facet_source'], 'https://play.hotspawn.com/lobby'])
    add('A-02', 'No official bookmaker prices confirmed in this audit',
        'The fetched bwin competition page exposed a competition and market heading but no numerical event quotes. Polymarket is a prediction market, not a bookmaker. Existing third-party preview quotes and tournament outrights do not prove current match moneylines.',
        [data['bwin_check']['url'], 'https://polymarket.com/esports/cs2'])
    add('A-03', 'UTC fixture timestamps are unconfirmed',
        'Hotspawn displays month/day and time without a timezone in the inspected lobby text. The inherited JSON appends Z. That UTC designation is unsupported by the lobby evidence. This audit leaves start_utc and start_timezone null; Polymarket rules independently state ET for the inspected direct markets.',
        ['https://play.hotspawn.com/lobby', data['fixtures'][0]['market_url'], REPO+'/blob/'+data['reviewed_repository_commit']+'/data/matches.json'])
    add('A-04', 'FORZE opponent mismatch',
        'The inherited JSON assigns FORZE Reload vs LFO 10 odds using related entries. The official market inspected is FORZE Reload vs Sökerorg, not LFO 10. No alias equivalence was established. Both fixture probabilities remain blank.',
        [data['fixtures'][11]['fixture_url'], data['fixtures'][11]['market_url']])
    add('A-05', 'RoundsGG / Voca price is assigned to the wrong stored outcome',
        'Inherited JSON row 25 stores 1.10 under team1=RoundsGG, while its note says that 1.10 belongs to Voca, team2. The official observed market lists Voca 1.10x91¢ and RoundsGG 2.13x47¢. Values remain suppressed because volume is zero and the paired prices are problematic.',
        [data['fixtures'][24]['market_url'], data['fixtures'][24]['fixture_url'], REPO+'/blob/'+data['reviewed_repository_commit']+'/data/matches.json'])
    js = HERE / 'inherited/matches.json'
    if js.exists():
        payload = json.loads(js.read_text())
        inherited = payload.get('matches', []) if isinstance(payload, dict) else payload
        sums = []
        for row in inherited:
            if not isinstance(row, dict):
                continue
            p = row.get('impliedProbability', {})
            if isinstance(p, dict) and all(isinstance(p.get(k), (int, float)) for k in ('team1', 'team2')):
                total = p['team1'] + p['team2']
                if abs(total - 100) > 0.2:
                    sums.append({'id': row['id'], 'sum_pct': round(total, 2)})
        add('A-06', 'Raw inverse odds are not normalized win probabilities',
            f"The inherited JSON contains {len(sums)} complete pairs whose displayed implied percentages differ from 100% by more than 0.2 percentage points. Raw 1/odds can legitimately include a spread/overround, but must not be mistaken for a coherent two-outcome forecast. Normalize only after verifying the exact moneyline and outcomes; arithmetic cannot repair wrong-market quotes. Audit row totals: "+json.dumps(sums),
            ['https://polymarket.com/esports/cs2', REPO+'/blob/'+data['reviewed_repository_commit']+'/data/matches.json'])
    lines = HERE / 'inherited/lines.csv'
    corrections = []
    if lines.exists():
        with lines.open() as f:
            outright = list(csv.DictReader(f))
        try:
            total = sum(1 / float(r['bookmaker_outright_decimal']) for r in outright)
            for r in outright:
                computed = round(100 / float(r['bookmaker_outright_decimal']) / total, 1)
                stored = float(r['implied_novig_pct'])
                if abs(stored - computed) > 0.1:
                    corrections.append({'team': r['team'], 'stored_pct': stored, 'recomputed_pct': computed})
            add('A-07', 'Stored outright no-vig arithmetic disagrees with its inputs',
                f"Recomputed denominator from the eight inherited decimal prices is {total:.9f}. All {len(corrections)} discrepancies are audit calculations from unverified repository inputs, NOT new verified bookmaker prices: "+json.dumps(corrections)+'. Outrights are not used for any match probability.',
                [data['bwin_check']['url'], 'https://polymarket.com/event/thunderpick-world-championship-2026-winner/will-falcons-win-the-thunderpick-world-championship-2026', REPO+'/blob/'+data['reviewed_repository_commit']+'/data/lines.csv'])
        except (KeyError, ValueError, ZeroDivisionError):
            add('A-07', 'Outright schema changed', 'Independent arithmetic audit could not parse the current inherited lines file. No values promoted.', [data['bwin_check']['url']])
    add('A-08', 'Rank-only model is reproducible, not calibrated',
        'scripts/model.py maps HLTV ranks to artificial ratings with an arbitrary coefficient of 300 and an Elo denominator of 400. No fitted parameters, historical calibration, holdout evaluation, roster/map adjustment or uncertainty evidence is supplied. Its existing inputs mix dated rankings and undated team pages. This audit does not promote those derived percentages as validated win probabilities.',
        ['https://www.hltv.org/ranking/teams/2026/october/5', REPO+'/blob/'+data['reviewed_repository_commit']+'/scripts/model.py'])
    add('A-09', 'Source reachability is not numerical verification',
        'A successful HTTP response can be an empty shell, challenge or unrelated market. The scheduled checks retain status, final URL, title, body hash and a warning, but never mark fixture or odds values verified. The published observation timestamp remains unchanged.',
        ['https://play.hotspawn.com/lobby', data['bwin_check']['url'], REPO+'/actions/workflows/assurance-5515.yml'])
    add('A-10', 'Historical snapshot; not a live odds feed',
        'These observations were inspected on '+data['checked_at']+'. Source quotation timestamps, best bid/ask depth and quote executability were not confirmed. Four exact-name, directly inspected moneyline pairs support historical price-normalized calculations only. No guarantee of current prices or actual outcome accuracy.',
        [data['fixtures'][5]['market_url'], data['fixtures'][8]['market_url']])
    for row in analyze(data):
        if row['reasons']:
            add('M-'+row['id'], row['team_a']+' vs '+row['team_b'], '; '.join(row['reasons']), [row['fixture_url'], row['market_url']])
    return findings, corrections


def page(name, title, body, timestamp):
    nav = [('index.html', 'Overview'), ('matches.html', 'All matches'), ('s-tier.html', 'S tier'), ('b-tier.html', 'B tier'), ('c-tier.html', 'C tier'), ('flagged.html', 'Flagged for Review'), ('sources.html', 'Evidence'), ('methodology.html', 'Methodology')]
    menu = ''.join(f'<a {"aria-current=page" if target == name else ""} href="{target}">{text}</a>' for target, text in nav)
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · Independent assurance</title><meta name="description" content="Source-linked CS2 Pick’em evidence audit. Unknown odds stay blank; calculations are labeled."><link rel="stylesheet" href="style.css"><script src="dashboard.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><header><div class="brand"><span class="mark">M</span><div>MALTA / RESEARCH DESK<small>Independent evidence assurance</small></div></div><a class="repo" href="{REPO}">Repository ↗</a></header><nav aria-label="Primary">{menu}</nav><main id="main"><div class="eyebrow">CS2 PICK’EM · SOURCE AUDIT</div><h1>{escape(title)}</h1><p class="lead">Fixture facts, market observations and calculations — kept separate.</p><div class="notice" data-checked="{timestamp}"><strong>Dated snapshot · {timestamp}</strong><span id="age">Not a live odds feed. Source quote timestamps are unknown.</span></div>{body}</main><footer>Hotspawn is used only to identify fixtures, never to estimate probability. Analysis, not betting advice.<br>Unknown values are blank and flagged. {link('../docs/index.html', 'Existing project dashboard')} · {link('report.json', 'Download audit JSON')} · {link('observations.json', 'Source excerpts')}</footer></body></html>'''
    (HERE / name).write_text(html)


def table(rows):
    rendered = []
    for r in rows:
        pa, pb = r['probability_a'], r['probability_b']
        prob = '' if pa is None else f'<b>{pa:.1%} / {pb:.1%}</b><small>Calculated from primary moneyline prices</small>'
        fair = '' if pa is None else f"{r['fair_decimal_a']:.2f} / {r['fair_decimal_b']:.2f}<small>Calculated fair line, not offered odds</small>"
        lean = '' if r['market_lean'] is None else escape(r['market_lean'])+'<small>Price-implied preference only</small>'
        status = 'needs review' if r['reasons'] else 'historical calculation'
        reasons = '; '.join(r['reasons']) if r['reasons'] else 'Exact names, dated market and direct series moneyline inspected. UTC start and quote freshness unconfirmed.'
        flag_url = 'flagged.html#M-'+r['id'] if r['reasons'] else 'flagged.html#A-10'
        rendered.append(f'''<tr data-status="{status}"><td><small>{escape(r['id'])}</small><strong>{escape(r['team_a'])}<span class="vs">vs</span>{escape(r['team_b'])}</strong></td><td>{escape(r['tournament'])}<small>Tier {escape(r['tier'])} · {escape(r['displayed_start'])}<br>Timezone unconfirmed</small></td><td>{prob}</td><td>{fair}</td><td>{lean}</td><td><span class="badge {'ok' if pa is not None else 'warn'}">{status}</span><small>{escape(reasons)}</small>{link(flag_url, 'Review note')}</td><td>{link(r['fixture_url'], 'Official fixture')}<br>{link(r['market_url'], 'Official market')}<br>{link('sources.html#'+r['id'], 'Retained excerpts')}</td></tr>''')
    return '<section class="panel"><div class="controls"><label>Search matches<input type="search" id="search" placeholder="Team or tournament" autocomplete="off"></label><label>Show<select id="status"><option value="all">All entries</option><option value="historical calculation">Calculated snapshots</option><option value="needs review">Needs review</option></select></label><span id="result-count" aria-live="polite"></span></div><div class="table-scroll" tabindex="0" role="region" aria-label="Match evidence table"><table><caption>Team A / Team B order is used in both percentage and fair-line columns. Empty numeric cells mean unverified or suppressed — never 50/50.</caption><thead><tr><th>Match</th><th>Competition / displayed start</th><th>Price-normalized A / B</th><th>Our fair decimal A / B</th><th>Market lean</th><th>Audit status</th><th>Primary sources</th></tr></thead><tbody>'+''.join(rendered)+'</tbody></table></div><p id="empty" hidden>No matching entries. Clear the search or change the status filter.</p></section>'


def build():
    data = json.loads(EVIDENCE.read_text())
    rows = analyze(data)
    findings, corrections = audit_repository(data)
    evidence_hash = hashlib.sha256(EVIDENCE.read_bytes()).hexdigest()
    report = {'schema_version': 1, 'checked_at': data['checked_at'], 'reviewed_repository_commit': data['reviewed_repository_commit'], 'observation_sha256': evidence_hash, 'source_quote_timestamp': None, 'reported_cs2_facet_count': data['reported_cs2_facet_count'], 'fixture_count': len(rows), 'qualified_quote_pairs': sum(r['probability_a'] is not None for r in rows), 'primary_bookmaker_pairs_confirmed': 0, 'rows': rows, 'findings': findings, 'outright_arithmetic_discrepancies': corrections}
    (HERE / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    n = report['qualified_quote_pairs']
    summary = f'''<section class="metrics" aria-label="Audit summary"><article><span>Inspected fixture cards</span><b>{len(rows)}</b><small>Not a complete inventory</small></article><article><span>Reported CS2 facet</span><b>{data['reported_cs2_facet_count']}</b><small>59 pairings not established here</small></article><article><span>Qualified quote pairs</span><b>{n}</b><small>Prediction-market snapshots</small></article><article><span>Verified bookmaker pairs</span><b>0</b><small>Unsupported prices remain blank</small></article></section><section class="intro-grid"><article class="panel"><h2>Evidence before picks.</h2><p>This audit covers the 26 cards actually inspected on Hotspawn. It independently checks the inherited repository rather than accepting its “verified” labels. Every match has primary-source links.</p><p>Four exact-name moneyline observations support <em>calculated</em> fair lines. All other probabilities are blank. Normalized prices are not calibrated forecasts.</p>{link('flagged.html', 'Read the audit findings →')}</article><article class="panel"><h2>What changed in the review?</h2><ul><li>Flagged unsupported UTC timestamps and outcome assignment.</li><li>Detected inconsistent outright no-vig arithmetic.</li><li>Suppressed ambiguous aliases, conflicting page prices and zero-volume observations.</li><li>Kept third-party odds and uncalibrated ranks out of qualified lines.</li></ul></article></section><h2>Qualified historical moneylines</h2>'''
    page('index.html', 'A clearer view of the evidence.', summary+table([r for r in rows if not r['reasons']]), data['checked_at'])
    page('matches.html', 'All inspected matches', '<p>All 26 inspected fixture cards, including every unverified entry. No unseen fixture was inferred from a facet count.</p>'+table(rows), data['checked_at'])
    for tier in ('S', 'B', 'C'):
        page(tier.lower()+'-tier.html', tier+' tier matches', '<p>Tier label observed on Hotspawn; not a probability input. Market outcomes must independently match the fixture.</p>'+table([r for r in rows if r['tier']==tier]), data['checked_at'])
    flags = ''.join('<tr id="'+escape(f['id'])+'"><td><b>'+escape(f['id'])+'</b><small>Needs review · non-blocking</small></td><td><strong>'+escape(f['summary'])+'</strong><p>'+escape(f['detail'])+'</p></td><td>'+'<br>'.join(link(url, 'Primary source' if 'github.com' not in url else 'Repository evidence') for url in f['sources'])+'</td></tr>' for f in findings)
    page('flagged.html', 'Flagged for Review', '<p>Published irregularities do not block release of this audit. They do block promotion of ambiguous numbers into qualified probabilities. Existing datasets owned by other sessions are not silently edited.</p><div class="panel table-scroll"><table><caption>Every finding links to primary source pages; repository links identify the exact inherited claims being audited.</caption><thead><tr><th>Reference</th><th>Finding / required resolution</th><th>Evidence links</th></tr></thead><tbody>'+flags+'</tbody></table></div>', data['checked_at'])
    entries = []
    for r in rows:
        conflicts = '' if not r['conflicting_decimal_pair'] else '<p>Also observed in hero panel: '+escape(str(r['conflicting_decimal_pair']))+'. Conflict retained, not reconciled by guessing.</p>'
        moneyline = '' if not r['moneyline_excerpt'] else '<h3>Direct moneyline section</h3><pre>'+escape(r['moneyline_excerpt'])+'</pre>'
        entries.append(f'''<tr id="{r['id']}"><td><strong>{r['id']}</strong>{escape(r['team_a'])} vs {escape(r['team_b'])}<small>Observed, not inferred</small></td><td>{link(r['fixture_source'], 'Official lobby')} · {link(r['fixture_url'], 'Match detail')}<pre>{escape(r['fixture_excerpt'])}</pre><small>Excerpt: non-probability fixture fields only. The lobby does not state a timezone or year in the card.</small></td><td>{link(r['observed_page'], 'Official market listing')} · {link(r['market_url'], 'Exact market page')}<pre>{escape(r['market_excerpt'])}</pre>{conflicts}{moneyline}<small>Quote timestamp unconfirmed. Volume is the source’s displayed aggregate, not proof of moneyline liquidity.</small></td></tr>''')
    source_intro = '<section class="panel"><h2>What “official” means here</h2><p>Hotspawn is the primary publisher of its fixture cards. Polymarket is the primary publisher of its own prediction-market prices; it is not a bookmaker or tournament organizer. HLTV is the primary publisher of HLTV rankings, not an official organizer schedule. Third-party previews cannot satisfy direct bookmaker verification.</p><p>Retained evidence consists of short transcribed excerpts from the fetch tool responses actually inspected. It is not a raw response archive. The access window is '+escape(data['access_window_utc'])+'. This is the observer’s time, not a source quote time. Exact market titles, names and the four direct Series Lines / Moneyline sections were inspected; unrelated map/handicap/total markets are excluded.</p><p>Evidence SHA-256: <code>'+evidence_hash+'</code></p><p>'+link('observations.json','Download source excerpts')+' · '+link('source_checks.json','HTTP source checks')+' · '+link(REPO+'/actions/workflows/assurance-5515.yml','Automated audit runs')+'</p><h3>Bookmaker check</h3><p>'+escape(data['bwin_check']['observed'])+' '+link(data['bwin_check']['url'],'bwin official competition')+'</p></section>'
    page('sources.html', 'Evidence & source roles', source_intro+'<div class="panel table-scroll"><table><caption>Every fixture row is supported by official-publisher URLs and the specific inspected excerpts.</caption><thead><tr><th>Fixture</th><th>Hotspawn evidence</th><th>External market evidence</th></tr></thead><tbody>'+''.join(entries)+'</tbody></table></div>', data['checked_at'])
    method = '''<section class="panel prose"><h2>Our originated fair lines</h2><p>Qualified observations use the cents displayed in the directly inspected <strong>Series Lines → Moneyline</strong> section. For prices cA and cB, compute pA = cA/(cA+cB), pB = cB/(cA+cB). Fair decimal lines are 1/pA and 1/pB. Never round intermediate values. Rounded reciprocal display multipliers are retained as evidence but do not supply the calculation.</p><p>This is our reproducible price-normalization calculation, not a quote from a sportsbook or a new independently calibrated statistical prediction. Fees, spread, cancellation/50-50 settlement rules and fill depth are not modeled. A market lean is simply the outcome with the larger normalized price.</p><h2>Strict publication gates</h2><ol><li>Both team names must match case-insensitively; no fuzzy matching or automatic aliases. Source outcome order is explicitly mapped.</li><li>The inspected dated market must be within the fixture window and competition must agree in the retained observation.</li><li>The individual series moneyline section must actually have been inspected. Map winners, handicap, totals and outrights cannot substitute.</li><li>Conflicting hero/list observations and zero-volume displays are suppressed. A sum above 110 cents is suppressed as a conservative policy, not a claim that such quotes are impossible.</li><li>Both prices must be finite and positive. Missing inputs produce blank probabilities, never default 50/50.</li></ol><h2>Verification is field-specific</h2><p>The fixture names, displayed month/day/time, tier and tournament were observed. UTC start and timezone are unconfirmed and remain null. Stored rank inputs are not newly verified. A reachable URL is not proof of the number it allegedly supports.</p><h2>Freshness and automation</h2><p>This dashboard is an immutable historical evidence snapshot. Its age is shown prominently; it is never relabeled live by a successful HTTP check. The daily GitHub Actions job reruns repository arithmetic audits and primary-source reachability checks and uploads machine-readable reports automatically. It does not fetch an exhaustive fixture inventory, silently refresh odds, or auto-verify numbers. The active parallel collection sessions own those tasks.</p><h2>Research still needed</h2><p>A validated full-match model requires confirmed team identities, dated compatible HLTV/VRS inputs, current rosters, map/series context, multiple independently verified match moneylines, historical backtesting/calibration and quantified uncertainty. No unsupported coefficients, injuries, rankings or win percentages are invented to fill coverage gaps.</p></section>'''
    page('methodology.html', 'Methodology & limits', method, data['checked_at'])
    print(f'Built 8 pages: {len(rows)} inspected fixtures, {n} qualified historical quote pairs, {len(findings)} review findings. No official bookmaker pairs confirmed.')
    return report


if __name__ == '__main__':
    build()
