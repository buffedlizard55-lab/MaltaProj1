"""Render dated TWC research next to automatically discovered live board rows.
No prices, participants, lock times or source read times are inferred from research.
"""
from html import escape
from common import Aliases, devig_two_way, normalise_prices, own_line
from evidence import select_quote


def preview_quotes(capture, research, reference):
    """Read-only market watch. Does not add synthetic fixtures to inventory/history.

    Kickoff below is the source-listed schedule, never a Hotspawn lock. Require the
    exact named semifinal, date/format, whole-match scope and existing freshness gates.
    """
    rows = []
    for match in research.get('semifinals', []):
        if not match.get('team_b') or not match.get('market_start_utc'):
            continue
        fx = {'match_id': 'research-only', 'team_a': match['team_a'], 'team_b': match['team_b'],
              'competition': 'Thunderpick World Championship 2026', 'start_utc': match['market_start_utc']}
        for kind, label in [('pinnacle', 'Pinnacle'), ('esportsbooks', 'bo3.gg relay'), ('polymarket', 'Polymarket')]:
            q, _ = select_quote(fx, capture.get(kind, {}).get('quotes', []), Aliases(), reference,
                                expected_format='BO3')
            if not q:
                continue
            odds = 'odds_a' in q
            numbers = (q.get('odds_a'), q.get('odds_b')) if odds else (q.get('price_a'), q.get('price_b'))
            numbers = numbers[::-1] if q.get('flipped') else numbers
            p = devig_two_way(*numbers) if odds else normalise_prices(*numbers)
            if p:
                rows.append({'match': match, 'label': label, 'numbers': numbers, 'p_a': p[0], 'p_b': p[1],
                             'read_utc': q.get('read_utc'), 'source_url': q['source_url'],
                             'provider_url': q.get('provider_url'), 'odds': odds})
    return rows



def day4_rows(board):
    return [r for r in board.get('rows', [])
            if r.get('status') == 'open'
            and r.get('competition', '').casefold() == 'thunderpick world championship 2026'
            and r.get('start_utc', '').startswith('2026-10-17')]


def render(board, research, card, capture=None, compact=False):
    def e(value):
        return escape('' if value is None else str(value), quote=True)

    def source(url, text='HLTV source'):
        return f'<a href="{e(url)}">{e(text)}</a>'

    out = ['<section aria-labelledby="day4"><h2 id="day4">Day 4 — 17 October semifinals</h2>',
           '<p><strong>Use the current outside line, not yesterday’s upset.</strong> The headline pick '
           'targets expected points. A contrarian choice is an optional higher-variance chase, not a '
           'claim of higher win probability. <a href="picks.html">All current picks →</a> · '
           '<a href="unresolved.html">Unresolved &amp; limitations</a></p>',
           f'<p class="small">Research snapshot: {e(research.get("checked_date_utc"))}, '
           f'{e(research.get("checked_window_utc"))} UTC. {e(research.get("provenance"))}</p>']
    live = day4_rows(board)
    if compact:
        out.append(f'<p>{len(live)} open day-4 main-event fixtures in this capture. '
                   'If none appear, this is a listing limitation, not a prediction. '
                   '<a href="twc.html#day4">Open day-4 picks / external market watch and day-3 results →</a></p>')
        out.append('</section>')
        return ''.join(out)
    if live:
        out.append('<h3>Day-4 matches open in the current Hotspawn capture</h3>')
        out.extend(card(row, board) for row in live)
    else:
        out.append('<p class="note">No open TWC main-event match dated 17 October is present in this '
                   'Hotspawn capture. The HLTV semifinal watch below is <b>not a pickable Hotspawn listing</b>. '
                   'Picks and probabilities remain blank here until a named fixture and eligible evidence '
                   'are captured. The four-hour refresh automatically discovers new fixtures across '
                   '<a href="https://play.hotspawn.com/lobby">the lobby</a>, '
                   '<a href="https://play.hotspawn.com/cs2-pickems">CS2</a> and '
                   '<a href="https://play.hotspawn.com/thp-pickems">TWC</a>; there is no fixed match-ID list.</p>')
    prices = preview_quotes(capture or {}, research, board.get('summary', {}).get('reference_utc'))
    if prices and not live:
        out.append('<h3>External market watch — not yet a Hotspawn pick</h3><p>No ownership-based '
                   'chase is available without a current Hotspawn listing and sample. Near-even lines '
                   'are not a strong favourite. These observed quotes update with the normal capture; '
                   'they do not create a contest fixture or a graded pre-lock pick.</p>'
                   '<div class="tablewrap"><table><thead><tr><th>Match</th><th>Source / inputs</th>'
                   '<th>Source-implied win chances</th><th>Read UTC / evidence</th></tr></thead><tbody>')
        for p in prices:
            m = p['match']
            a, b = p['numbers']
            pa = round(p['p_a'] * 100, 1)
            out.append(f'<tr><td>{e(m["team_a"])} vs {e(m["team_b"])}</td>'
                       f'<td>{e(p["label"])}: {e(a)} / {e(b)}<br>'
                       + ('Decimal odds; margin removed' if p['odds'] else 'Outcome prices; normalized')
                       + f'</td><td>{e(m["team_a"])} {pa:.1f}% / {e(m["team_b"])} {100-pa:.1f}%</td>'
                       + f'<td>{e(p["read_utc"])}<br>{source(m["url"])} · '
                       + source(p['source_url'], 'quote source')
                       + (' · ' + source(p['provider_url'], 'provider link') if p.get('provider_url') else '')
                       + '</td></tr>')
        out.append('</tbody></table></div>')
    k_fit = (board.get('summary') or {}).get('own_line_k')
    own_cells, own_used = {}, False
    for match in research.get('semifinals', []):
        points = match.get('valve_points') or {}
        a, b = points.get('side_a') or {}, points.get('side_b') or {}
        if k_fit and a.get('points') is not None and b.get('points') is not None:
            pa = own_line(a['points'], b['points'], float(k_fit))
            own_cells[id(match)] = (pa, 1 - pa, a, b, points.get('as_of'))
            own_used = True
    out.append('<h3>Semifinal watch — dated research, not an extra picks list</h3>'
               '<div class="tablewrap"><table><thead><tr><th>Date / format</th><th>Match at research check</th>'
               '<th>Context and limitation</th>'
               + ('<th>Our own line (Valve points)</th>' if own_used else '')
               + '<th>Source</th></tr></thead><tbody>')
    for match in research.get('semifinals', []):
        opponent = match.get('team_b') or 'Opponent unconfirmed'
        cell = ''
        if id(match) in own_cells:
            pa, pb, a, b, as_of = own_cells[id(match)]
            links = ''
            if a.get('row_url') and b.get('row_url'):
                links = ' · ' + source(a.get('row_url'), 'row A') + ' · ' + source(b.get('row_url'), 'row B')
            cell = (f'<td><b>{e(a.get("team"))} {pa * 100:.1f}% / {e(b.get("team"))} {pb * 100:.1f}%</b>'
                    f'<br><span class="small">our estimate, not a bookmaker quote<br>'
                    f'Valve {e(as_of)} points: {e(a.get("points"))} vs {e(b.get("points"))}{links}</span></td>')
        out.append(f'<tr><td>{e(match.get("date"))}<br>{e(match.get("format"))}</td>'
                   f'<td>{e(match.get("team_a"))} vs {e(opponent)}<br>{e(match.get("opponent_note"))}</td>'
                   f'<td>{e(match.get("context"))}</td>' + cell + f'<td>{source(match.get("url"))}</td></tr>')
    out.append('</tbody></table></div><h3>Day-3 results — confirmed from HLTV</h3>'
               '<div class="tablewrap"><table><thead><tr><th>Match</th><th>Final score / status</th>'
               '<th>Maps and veto</th><th>What changes for day 4</th><th>Source</th></tr></thead><tbody>')
    for result in research.get('results', []):
        score = result.get('score') if result.get('status') == 'completed' else None
        out.append(f'<tr><td>{e(result.get("team_a"))} vs {e(result.get("team_b"))}</td>'
                   f'<td><b>{e(score)}</b><br>{e(result.get("status"))}</td>'
                   f'<td>{e(result.get("maps"))}<br>{e(result.get("veto"))}</td>'
                   f'<td>{e(result.get("meaning"))}</td><td>{source(result.get("url"))}</td></tr>')
    if own_used:
        method = research.get('own_line_method') or {}
        out.append('<p class="small"><b>How the own line is computed:</b> '
                   + e(method.get('formula')) + f' with k = <b>{e(k_fit)}</b>, '
                   + source('data/calibration.json', 'fitted on Valve’s published results') + '. '
                   'Inputs are Valve’s official numbers for each side, linked in the column above; the estimate carries no '
                   'map-veto, preparation or fatigue term, so it is kept separate from the outside prices and is not a pick. '
                   'HLTV’s own pick-a-winner shares for these ties are recorded in the research file only and are never used '
                   'in a number here.</p>')
    picks = research.get('day4_contrarian_picks') or {}
    if picks:
        out.append('<h3>Day-4 contrarian options — source-backed, and audited</h3>')
        out.append(f'<p class="lead"><strong>Headline:</strong> {e(picks.get("headline_strategy"))}</p>')
        out.append(f'<p class="lead"><strong>Recommendation:</strong> {e(picks.get("recommended"))}</p>')
        out.append('<div class="tablewrap"><table><thead><tr><th>Match</th><th>Start (UTC)</th><th>Contrarian option</th>'
                   '<th>Class</th><th>Why it is defensible</th><th>Risk / expected-points cost</th></tr></thead><tbody>')
        for key in ('contrarian_option_1', 'contrarian_option_2'):
            opt = picks.get(key)
            if not opt:
                continue
            start = ''
            for sf in research.get('semifinals', []):
                if sf.get('team_a') in (opt.get('match') or '') and sf.get('team_b') in (opt.get('match') or ''):
                    start = sf.get('start_utc') or sf.get('market_start_utc') or ''
                    break
            cls = opt.get('class') or ''
            out.append(f'<tr><td>{e(opt.get("match"))}</td><td>{e(start)}</td><td><strong>{e(opt.get("pick"))}</strong></td>'
                       f'<td><span class="tag c-{e(cls.replace(" ", "-"))}">{e(cls)}</span></td>'
                       f'<td>{e(opt.get("rationale"))}</td>'
                       f'<td>{e(opt.get("risk"))}<br><span class="small">{e(opt.get("ev_cost"))}</span></td></tr>')
        out.append('</tbody></table></div>')
        audit = picks.get('audit') or []
        if audit:
            out.append('<p class="small"><b>Merge audit of the merged draft&#39;s claims:</b> every line below was re-checked against the '
                       'sources read on 16-17 October. Corrections are applied above; unverified claims are not republished.</p>'
                       '<div class="tablewrap"><table><thead><tr><th>Claim</th><th>Status</th><th>Finding</th><th>Source</th>'
                       '</tr></thead><tbody>')
            for item in audit:
                src = source(item.get("source_url")) if item.get("source_url") else "—"
                out.append(f'<tr><td>{e(item.get("claim"))}</td><td>{e(item.get("status"))}</td>'
                           f'<td>{e(item.get("detail"))}</td><td>{src}</td></tr>')
            out.append('</tbody></table></div>')
    for sf in research.get('semifinals', []):
        ca = sf.get('contrarian_analysis') or {}
        if not ca:
            continue
        out.append(f'<h3>{e(sf.get("team_a"))} vs {e(sf.get("team_b"))} — analysis behind the option</h3>'
                   '<div class="tablewrap"><table><thead><tr><th>Factor</th><th>Detail</th></tr></thead><tbody>')
        for label, value in (("Favourite", ca.get('favourite')), ("Underdog", ca.get('underdog')),
                             ("Head-to-head", ca.get('h2h_2026') or ca.get('h2h')),
                             ("Map pool", ca.get('map_pool')), ("Map-pool check", ca.get('map_pool_flag')),
                             ("Upset case", ca.get('upset_case')), ("Favourite case", ca.get('favourite_case')),
                             ("Verdict", ca.get('verdict'))):
            if value:
                out.append(f'<tr><td>{e(label)}</td><td>{e(value)}</td></tr>')
        out.append('</tbody></table></div>')
    out.append('</tbody></table></div><h3>How days 1–3 guide the decision</h3><ul>')
    for lesson in research.get('lessons', []):
        out.append(f'<li>{e(lesson.get("text"))} {source(lesson.get("url"))}</li>')
    out.append('</ul><p class="note"><b>Practical rule:</b> first take the supported favourite. '
               'Consider an underdog only when the current outside estimate gives a meaningful chance '
               'and the ownership sample is sufficiently large to show genuine differentiation. '
               'The existing conservative gates and expected-points cost are on '
               '<a href="strategy.html">Leaderboard plan</a>. Do not force a fade when ownership is '
               'missing, or use a roster-only model as proof of an unpriced upset. No finish-rank '
               'optimization is claimed without your rank, points gap and the field’s joint selections.</p></section>')
    return ''.join(out)
