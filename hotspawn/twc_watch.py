"""Render dated TWC research next to automatically discovered live board rows.
No prices, participants, lock times or source read times are inferred from research.
"""
from html import escape


def day4_rows(board):
    return [r for r in board.get('rows', [])
            if r.get('status') == 'open'
            and r.get('competition', '').casefold() == 'thunderpick world championship 2026'
            and r.get('start_utc', '').startswith('2026-10-17')]


def render(board, research, card):
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
