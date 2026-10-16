#!/usr/bin/env python3
"""Read-only assurance of the canonical snapshot; never alters picks or researches missing facts.

The per-row findings prove internal consistency/provenance presence, NOT source truth or execution
quality. The dated HLTV observations were independently re-read using fetch_page on 2026-10-16.
Run after a canonical refresh: python scripts/audit_4c4b0777.py.
"""
from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKED = '2026-10-16'
HLTV = 'https://www.hltv.org/matches/'
OBSERVATIONS = [
    (1, '9z', 'Aurora', '2–0', 'Inferno 13–11; Nuke 13–1', '2399384/9z-vs-aurora'),
    (1, 'Falcons', 'Ninjas in Pyjamas', '2–0', 'Ancient 16–13; Dust2 13–6', '2399385/falcons-vs-ninjas-in-pyjamas'),
    (1, 'Legacy', 'PARIVISION', '2–0', 'Dust2 13–11; Mirage 16–14', '2399386/legacy-vs-parivision'),
    (1, 'FURIA', 'BetBoom', '2–0', 'Ancient 13–10; Mirage 13–9', '2399387/furia-vs-betboom'),
    (2, 'Aurora', 'Ninjas in Pyjamas', '2–0', 'Cache 13–9; Dust2 13–7', '2399408/aurora-vs-ninjas-in-pyjamas'),
    (2, 'Falcons', '9z', '2–1', 'Nuke 13–9; Mirage 8–13; Dust2 13–9', '2399409/9z-vs-falcons'),
    (2, 'BetBoom', 'PARIVISION', '2–1', 'Ancient 10–13; Anubis 13–4; Mirage 13–7', '2399410/parivision-vs-betboom'),
    (2, 'FURIA', 'Legacy', '2–1', 'Cache 10–13; Inferno 13–5; Mirage 13–8', '2399411/legacy-vs-furia'),
]


def instant(value):
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (TypeError, ValueError, AttributeError):
        return None


def probability(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1


def inspect(row, reference):
    """Findings are independent of crowd ownership; do not turn absent inputs into 50/50."""
    issues = []
    a, b = row.get('p_a'), row.get('p_b')
    if not probability(a) or not probability(b) or abs(a + b - 1) > .0002:
        issues.append('Unresolved: missing or invalid complementary probabilities')
    if row.get('pick') not in (row.get('team_a'), row.get('team_b')) or not row.get('pick'):
        issues.append('Unresolved: no valid pick')
    if probability(a) and probability(b) and abs(a - b) < .02:
        issues.append('No meaningful market edge: near-even line; any directional pick is a tiebreak, not evidence of superiority')
    selected = row.get('book') if row.get('rung') == 'A' else (row.get('relay') or row.get('pm')) if row.get('rung') == 'B' else None
    if selected:
        read = instant(selected.get('read_utc'))
        if not read or not reference or (reference - read).total_seconds() > 8 * 3600 or (reference - read).total_seconds() < -300:
            issues.append('Unverified: selected quote timestamp missing or outside eight-hour window')
        if not selected.get('url', '').startswith('https://'):
            issues.append('Unverified: selected quote has no HTTPS source')
        if row.get('rung') == 'B' and not row.get('relay'):
            issues.append('Prediction-market estimate: spread, order-book depth and executable size not verified; volume is not liquidity')
        if row.get('rung') == 'B' and row.get('relay'):
            issues.append('Secondary relayed-book estimate: not verified directly with the bookmaker')
        if row.get('rung') == 'A' or (row.get('rung') == 'B' and row.get('relay')):
            oa, ob = selected.get('odds_a'), selected.get('odds_b')
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 1 for x in (oa, ob)):
                issues.append('Unverified: invalid two-way bookmaker prices')
            elif not probability(a) or abs(a - (1 / oa) / (1 / oa + 1 / ob)) > .0002:
                issues.append('Unverified: displayed probability does not reproduce from the retained prices')
    elif row.get('rung') in ('A', 'B'):
        issues.append('Unverified: selected external quote is absent')
    if row.get('rung') == 'C':
        issues.append('Model-only: project forecast from official inputs, not an official Valve probability or verified betting line')
    if not row.get('hotspawn_match_url') and not row.get('lobby_url'):
        issues.append('Unverified: fixture source missing')
    return issues


def link(url, label):
    return f'<a href="{escape(str(url), quote=True)}">{escape(label)}</a>' if str(url).startswith('https://') else ''


def main():
    board = json.loads((ROOT / 'hotspawn/data/board.json').read_text())
    reference = instant(board['meta']['reference_utc'])
    records = []
    for r in board['rows']:
        if r['status'] != 'open':
            continue
        records.append({'match_id': r['match_id'], 'match': f"{r['team_a']} vs {r['team_b']}",
                        'rung': r.get('rung'), 'findings': inspect(r, reference),
                        'source': r.get('hotspawn_match_url') or r.get('lobby_url')})
    report = {'source_reread_date_utc': CHECKED, 'snapshot_utc': board['meta']['reference_utc'],
              'scope': 'Canonical hotspawn board only. Internal consistency is not independent source verification.',
              'open_rows': len(records), 'rows_with_findings': sum(bool(r['findings']) for r in records),
              'rows': records}
    (ROOT / 'reviews/4c4b0777-row-audit.json').write_text(json.dumps(report, indent=2) + '\n')
    rows = ''
    for r in records:
        findings = '<br>'.join(escape(x) for x in r['findings']) or 'No internal inconsistency detected; source truth not re-verified by this test'
        rows += f'<tr><th scope="row">{escape(r["match"])}</th><td>{escape(str(r["rung"]))}</td><td>{findings}</td><td>{link(r["source"], "Hotspawn fixture")} · <a href="picks.html" title="Current picks list; historical audit row may no longer be open">Pick &amp; external sources</a></td></tr>'
    results = ''
    for day, win, lose, score, maps, slug in OBSERVATIONS:
        url = HLTV + slug + '-thunderpick-world-championship-2026'
        results += f'<tr><td>{day}</td><th scope="row">{escape(win)} over {escape(lose)}</th><td>{score}</td><td>{maps}</td><td>{link(url, "HLTV match record")}<br>Organizer confirmation: unverified</td></tr>'
    gaps = json.loads((ROOT / 'reviews/4c4b0777-gap-research.json').read_text())
    gap_rows = ''
    for g in gaps['rows']:
        source_links = ' · '.join(link(g[k], label) for k, label in [('hotspawn_source', 'Hotspawn'), ('hltv_source', 'HLTV'), ('book_source', 'Pinnacle'), ('secondary_source', 'Secondary check')])
        gap_rows += f'<tr><th scope="row">{escape(g["match"])}</th><td>{escape(g["hltv_observed"])}</td><td>{escape(g["secondary_observed"])}</td><td>{escape(g["model_limit"])}</td><td>{source_links}<br>Probabilities: unverified (blank)</td></tr>'
    html = '''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Source audit &amp; Flagged for Review · Hotspawn CS2</title><link rel="stylesheet" href="style.css"><style>th,td{white-space:normal;overflow-wrap:anywhere}table{min-width:0!important;width:100%}a{overflow-wrap:anywhere}nav a{min-height:44px;display:inline-flex;align-items:center}.audit-status{padding:16px;border:2px solid #dba84d;border-radius:8px} @media(max-width:600px){.audit-table thead{display:none}.audit-table tr{display:block;border:1px solid #536270;margin:12px 0;padding:12px}.audit-table th,.audit-table td{display:block;border:0;padding:6px;text-align:left}}</style></head><body><a class="skip" href="#main">Skip to content</a><header class="top"><a class="brand" href="../index.html">HOTSPAWN CS2</a><nav aria-label="Audit navigation"><a href="picks.html">All updated picks</a><a href="strategy.html">Leaderboard plan</a><a href="unresolved.html">Unresolved</a><a href="flagged.html">Board flags</a></nav></header><main id="main"><h1>Source audit &amp; Flagged for Review</h1><p class="note">Historical release audit: completed fixtures may no longer appear in the current picks list. Original source links remain beside each row. See <a href="twc.html#day4">Day-4 watch</a> and <a href="../reviews/4061d8f1-verification.md">latest scoped verification</a>.</p>
<p class="lead">An independent release check, not another picks board. <a href="picks.html">Use the canonical picks list</a> for the latest recommendations.</p>
<div class="audit-status"><strong>Dated audit, not a live-feed guarantee.</strong> Source pages re-read on CHECKED UTC; row audit uses snapshot SNAPSHOT. Subsequent scheduled collections can change the slate. <span id="audit-age"></span> <a href="../reviews/4c4b0777-row-audit.json">Download row audit</a>.</div>
<h2>Executive summary</h2><ul><li><a href="picks.html">All picks and both probabilities</a> · <a href="strategy.html">day-1/day-2 review and day-3 plan</a>.</li><li><a href="unresolved.html">Unresolved matches and research limitations</a>: no invented percentages when evidence is missing. Having a pick does not mean having a strong directional edge.</li><li>Hotspawn identifies fixtures and crowd ownership only; it is never evidence of win probability.</li><li>Each result below was re-read on HLTV itself. HLTV is specialist reporting, <strong>not the tournament organizer</strong>. Organizer confirmation remains unverified; we do not label these official results.</li></ul>
<h2>Day 1 and day 2: independently re-read results</h2><p>Maps are listed from the winner's perspective. Day 1 = 14 October; day 2 = 15 October 2026.</p><table class="audit-table"><thead><tr><th>Day</th><th>Winner / opponent</th><th>Series</th><th>Maps</th><th>Source / verification</th></tr></thead><tbody>RESULTS</tbody></table>
<h2>How this should guide day 3</h2><p><strong>Aurora remains the default; 9z is an optional chase pick, not the most likely winner.</strong> The 13–1 Nuke on day 1 is real evidence that 9z can compete, not proof that the rematch is theirs. Aurora's 2–0 rebound over NiP and 9z taking a map off Falcons argue against either “Aurora is broken” or “9z was a pure fluke.” This is qualitative analysis, not an extra numeric adjustment.</p>
<p>The July 3 Jimpphat and July 8 kyxsan moves were about three months before TWC, not a fresh emergency substitution. Verified against <a href="https://www.hltv.org/news/44998/summer-2026-rostermania-as-it-happened">HLTV's dated transfer tracker</a>; current names also appear on <a href="https://www.hltv.org/team/11861/aurora">Aurora's HLTV team page</a>. Team-issued confirmation and a quantified onboarding penalty are unverified. No rest/fatigue adjustment is justified without travel, practice or rest evidence.</p>
<p><a href="picks.html" title="Current picks list; historical fixture may no longer be open">Aurora–9z current pick and probabilities</a> · <a href="https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026">HLTV Group A decider, BO3</a>. <a href="https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026">BetBoom–Legacy is the Group B decider</a>; Hotspawn now lists it as <a href="https://www.hotspawn.com/matches/betboom-vs-legacy-thunderpick-world-championship-2026-1081775">1081775</a>. Earlier “absent from Hotspawn” statements apply only to their dated captures.</p>
<h2 id="flagged">Flagged for Review: limitations that a coverage count can hide</h2><ul><li><strong>Hindsight:</strong> day-1 leaderboard “4/4” is a retrospective application of a later rule, not proof of four bets or picks made before lock. Do not use it as a backtest of the deployed strategy.</li><li><strong>Small sample:</strong> the saved day-2 review has three frozen picks, two correct for both strategies; Aurora–NiP has no frozen pick and is excluded. Four results are not four archived predictions.</li><li><strong>Prediction-market quality:</strong> a 50/50 quote is not affirmative support for either side. Trade volume does not establish current depth. The <a href="https://polymarket.com/event/cs2-aur1-9z-2026-10-16">Aurora event page</a> contains both series and map contracts and displayed 70¢ / 31¢ in this re-read; do not mix contract scopes or call that 101% pair a calibrated probability. The collector filters match-winner titles; executable spread/depth remain unverified.</li><li><strong>Leaderboard objective:</strong> ownership gaps measure differentiation, not betting value or the probability of finishing first. The optimal risk depends on your deficit, remaining matches, opponents and streak rules. No strategy here guarantees a climb.</li><li><strong>Refresh reliability:</strong> the existing <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/.github/workflows/hotspawn-22be6967.yml">four-hour workflow</a> checks all three Hotspawn surfaces. Schedules can be delayed; check actual capture age. A prior phone script can return success when the browser is unavailable; release assurance requires an actual passed browser report.</li><li><strong>Legacy repo checks:</strong> the initial 405-test run had two valuepicks coverage failures and one livelines deterministic-build error, outside the canonical board. These are not evidence that every archive is current. <a href="https://github.com/buffedlizard55-lab/MaltaProj1/pull/150">Separate PR #150</a> is not silently integrated by this session.</li></ul>
<h2 id="unresolved-research">Unresolved picks: extra research completed</h2><p>These two fixtures were unresolved in the audited 04:20Z capture. We tried HLTV first, the captured esportsbook/prediction-market feeds next, then secondary odds pages. Pinnacle's direct website returned HTTP 500 in the manual re-read, while the canonical API collection succeeded but contained no quote for either match. Do not interpret that as global bookmaker absence. No probability is supplied below because it could not be confirmed or supported without an ambiguous roster choice. <a href="../reviews/4c4b0777-gap-research.json">Research log</a> · <a href="unresolved.html">Current automatic unresolved register</a>.</p><table class="audit-table"><thead><tr><th>Match</th><th>HLTV checked</th><th>Secondary lines checked</th><th>Why a model is limited</th><th>Sources / probability</th></tr></thead><tbody>GAPROWS</tbody></table><p>Historical five's points are in <a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md">Valve's official standings</a>. A matching team label alone is insufficient when two rosters share it. Scheduled collections retry the feeds; current-five confirmation or an attributable market can unblock a row.</p><h2>Per-row evidence limitations</h2><p>ROWS open rows in this dated canonical snapshot; FINDINGS have at least one limitation below. These checks reproduce arithmetic and inspect retained provenance; they do <strong>not</strong> certify all external facts. External probability sources are linked from each pick. The automatic board's unresolved list remains separate.</p><table class="audit-table"><thead><tr><th>Match</th><th>Basis rung</th><th>Limitation / check result</th><th>Source</th></tr></thead><tbody>AUDITROWS</tbody></table>
<p>Reproduce: <code>python scripts/audit_4c4b0777.py</code>. No picks, prices or research files are changed by this audit.</p></main><footer><p>Independent research; estimates are not facts or betting advice. <a href="../index.html">Executive summary</a></p></footer><script>(function(){var t=Date.parse('SNAPSHOT');var h=(Date.now()-t)/3600000;document.getElementById('audit-age').textContent=Number.isFinite(h)?'Audited snapshot age: '+h.toFixed(1)+' h'+(h>8?' — older than 8 h; open the updated picks list.':'.'): 'Timestamp unverified.';})();</script></body></html>'''
    for key, value in [('CHECKED', CHECKED), ('SNAPSHOT', report['snapshot_utc']), ('RESULTS', results), ('AUDITROWS', rows), ('GAPROWS', gap_rows), ('FINDINGS', str(report['rows_with_findings'])), ('ROWS', str(report['open_rows']))]:
        html = html.replace(key, value)
    (ROOT / 'hotspawn/release-audit.html').write_text(html + '\n')
    print(f"Audited {len(records)} open rows; {report['rows_with_findings']} with limitations. No picks changed.")


if __name__ == '__main__':
    main()
