"""Render dated TWC research next to automatically discovered live board rows.
No prices, participants, lock times or source read times are inferred from research.
"""
from html import escape
from common import Aliases, devig_two_way, normalise_prices
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
    out.append('<h3>Semifinal watch — dated research, not an extra picks list</h3>'
               '<div class="tablewrap"><table><thead><tr><th>Date / format</th><th>Match at research check</th>'
               '<th>Context and limitation</th><th>Source</th></tr></thead><tbody>')
    for match in research.get('semifinals', []):
        opponent = match.get('team_b') or 'Opponent unconfirmed'
        out.append(f'<tr><td>{e(match.get("date"))}<br>{e(match.get("format"))}</td>'
                   f'<td>{e(match.get("team_a"))} vs {e(opponent)}<br>{e(match.get("opponent_note"))}</td>'
                   f'<td>{e(match.get("context"))}</td><td>{source(match.get("url"))}</td></tr>')
    out.append('</tbody></table></div><h3>Day-3 results — completed versus still unconfirmed at check</h3>'
               '<div class="tablewrap"><table><thead><tr><th>Match</th><th>Final score / status</th>'
               '<th>Maps and veto</th><th>What changes for day 4</th><th>Source</th></tr></thead><tbody>')
    for result in research.get('results', []):
        score = result.get('score') if result.get('status') == 'completed' else None
        out.append(f'<tr><td>{e(result.get("team_a"))} vs {e(result.get("team_b"))}</td>'
                   f'<td><b>{e(score)}</b><br>{e(result.get("status"))}</td>'
                   f'<td>{e(result.get("maps"))}<br>{e(result.get("veto"))}</td>'
                   f'<td>{e(result.get("meaning"))}</td><td>{source(result.get("url"))}</td></tr>')
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
