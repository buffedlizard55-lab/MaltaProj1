#!/usr/bin/env python3
"""Render the mobile-first pages of the every-match board from data/board.json (session arena/22be6967).

Pages: index.html (executive summary incl. unresolved & limitations), picks.html (every open match),
strategy.html (leaderboard plays + day-1 review + grading), unresolved.html, flagged.html (Flagged for
Review), all.html (every captured fixture), method.html (methodology, sources, read times).
No external requests; the only script is inline and optional (local lock countdowns, filters).
"""
from __future__ import annotations

import re
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, REPO_URL, RESEARCH, ROOT, SESSION, devig_two_way, norm_name,  # noqa: E402
                    normalise_prices, own_line, parse_iso, read_json, utc_label, write_json)

DAY3_FILE = RESEARCH / "day3_twc2026.json"

NAV = [("index.html", "Summary"), ("picks.html", "All picks"), ("twc.html", "TWC 2026"),
       ("strategy.html", "Leaderboard plan"), ("unresolved.html", "Unresolved"), ("flagged.html", "Flagged"),
       ("method.html", "Method")]
CLASS_ORDER = ["VALUE", "CONTRARIAN", "SITUATIONAL", "LONG SHOT", "CHALK", "NO CROWD DATA"]
CLASS_TEXT = {
    "VALUE": "Keep the published favourite; most crowd picks are on its opponent. “Value” here means ownership differentiation, not proven betting value.",
    "CONTRARIAN": "Play the underdog: every estimate gives it a real chance, well above its crowd share.",
    "SITUATIONAL": "Play the underdog: real chance, heavily faded, and a verified roster/stand-in/late-notice factor hits the favourite.",
    "LONG SHOT": "Keep the favourite. The underdog is an optional punt only if you are far behind.",
    "CHALK": "Keep the favourite. Fading it costs points without enough upside.",
    "NO CROWD DATA": "Ownership missing or fewer than 10 crowd picks; no automatic fade. Keep the headline pick.",
}
RUNG_TEXT = {"A": "Pinnacle odds (margin removed)", "B": "Secondary outside market",
             "C": "Our own line (official Valve points)", "D": "Unresolved"}


def e(x) -> str:
    return escape("" if x is None else str(x), quote=True)


def pc(x, d=0) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def pair(pa, pb) -> tuple[str, str]:
    """Both teams' percentages rounded so they always add up to 100."""
    if pa is None or pb is None:
        return pc(pa), pc(pb)
    a = round(pa * 100)
    return f"{a}%", f"{100 - a}%"


def link(url, text=None) -> str:
    if not url:
        return e(text or "")
    return f'<a href="{e(url)}">{e(text or url)}</a>'


def cls_tag(c: str | None) -> str:
    if not c:
        return ""
    return f'<span class="tag c-{e(c.replace(" ", "-"))}">{e(c)}</span>'


def page(name: str, title: str, body: str, board: dict, extra_head: str = "", script: str = "") -> None:
    body = body.replace('<div class="tablewrap">', '<div class="tablewrap" tabindex="0" role="region" aria-label="Scrollable source-linked table">')
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == name else ""}>{e(t)}</a>' for h, t in NAV)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d1218">
<meta name="description" content="Hotspawn Counter-Strike 2 pick'em: a pick and both teams' win probabilities for every resolvable open match, with sources.">
<title>{e(title)} · Hotspawn CS2 picks</title>
<link rel="stylesheet" href="style.css">
{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><a class="brand" href="../index.html">HOTSPAWN CS2 <span>picks</span></a><nav aria-label="Board pages">{nav}</nav></header>
<main id="main">
{snapshot_banner(board)}
{body}
</main>
<footer>
<p>Independent research, not affiliated with Hotspawn; not betting advice. Probabilities come from outside prices (Pinnacle, Polymarket) or our own line from Valve's official standings (or explicitly secondary relayed-book prices) — never from Hotspawn's crowd percentages, which appear only as "ownership" for the leaderboard plan.</p>
<p>Maintained primary board · original session <code>{e(SESSION)}</code> · <a href="data/picks.csv">picks.csv</a> · <a href="data/all_fixtures.csv">all_fixtures.csv</a> · <a href="data/flags.csv">flags.csv</a> · <a href="data/board.json">board.json</a> · <a href="{REPO_URL}/blob/main/.github/workflows/hotspawn-22be6967.yml">refresh workflow</a> · <a href="{REPO_URL}">source</a></p>
</footer>
<script>
(function(){{var s=document.getElementById('snap');if(!s)return;var t=Date.parse(s.getAttribute('data-ref'));if(!t)return;var h=(Date.now()-t)/36e5;var a=document.getElementById('snap-age');if(a)a.textContent=h<1?Math.round(h*60)+' min ago':h.toFixed(1)+' h ago';if(h>8){{s.className='snap bad';a.textContent+=' — older than 8 h: the scheduled refresh may have failed; check the lobby before relying on it';}}}})();
{script}
</script>
</body>
</html>
"""
    (ROOT / name).write_text(html, encoding="utf-8")


def snapshot_banner(board: dict) -> str:
    m, s = board["meta"], board["summary"]
    hs = m["hotspawn"]
    ok = hs.get("complete") and not hs.get("stale_carry")
    pin, pm = m["pinnacle"], m["polymarket"]
    cls = "snap" if ok else "snap warn"
    warn = "" if ok else " <strong>Hotspawn read incomplete — new matches may be missing.</strong>"
    return (f'<p id="snap" class="{cls}" data-ref="{e(m["reference_utc"])}">Snapshot: Hotspawn read '
            f'<strong>{e(utc_label(m["reference_utc"]))}</strong> (<span id="snap-age">age unknown</span>) · '
            f'Pinnacle {e(pin.get("status"))} · Polymarket {e(pm.get("status"))} · Valve standings {e(m["vrs"].get("as_of"))} · '
            f'HLTV ranking {e(m["hltv"].get("status"))}. Auto-refresh every 4 h.{warn} '
            f'<a href="https://play.hotspawn.com/lobby">Open the live Hotspawn lobby</a></p>')


def team_bar(name, p, fav, label=None) -> str:
    w = 0 if p is None else max(2, round(p * 100))
    return (f'<div class="bar{" fav" if fav else ""}"><span class="name">{e(name)}</span>'
            f'<span class="track"><i style="width:{w}%"></i></span><span class="v">{label or pc(p)}</span></div>')


def evidence_list(r: dict, board: dict) -> str:
    items = []
    b, p = r.get("book"), r.get("pm")
    if b:
        gap = f"; Pinnacle lists kickoff {e(utc_label(b.get('listed_start')))}" if abs(b.get("gap_h") or 0) > 0.01 else ""
        items.append(f"Pinnacle ({e(b.get('names'))}, {e(b.get('league'))}): {b['odds_a']:.3f} / {b['odds_b']:.3f}, margin {b['overround_pct']:.1f}% → "
                     f"{pc(b['p_a'])} / {pc(b['p_b'])}; read {e(utc_label(b.get('read_utc')) or b.get('read_utc'))}{gap}. {link(b.get('url'), 'Pinnacle CS2')} · {link(b.get('api_url'), 'API')}")
    else:
        items.append("Pinnacle: no open whole-match line for this fixture at read time.")
    if p:
        items.append(f"Polymarket: {e(p.get('question'))} — {p['price_a']} / {p['price_b']} → {pc(p['p_a'])} / {pc(p['p_b'])}; read {e(utc_label(p.get('read_utc')) or p.get('read_utc'))}. {link(p.get('url'), 'market')}")
    else:
        items.append("Polymarket: no match-winner market for this fixture at read time.")
    if r.get("format_evidence"):
        items.append("Series format: " + e(r.get("format")) + " from " + link(r["format_evidence"].get("url"), "bo3.gg match metadata") + "; read " + e(r["format_evidence"].get("read_utc")) + ". This metadata is not a betting price.")
    relay = r.get("relay")
    if relay:
        items.append(f"Secondary esportsbook: {e(relay.get('provider'))} via bo3.gg — {relay['odds_a']} / {relay['odds_b']}, margin {relay['overround_pct']:.1f}% → {pc(relay['p_a'],1)} / {pc(relay['p_b'],1)}; read {e(relay.get('read_utc'))}. Not verified directly with the book. {link(relay.get('url'), 'relay source')} · {link(relay.get('provider_url'), 'named bookmaker fixture')}")
    attempt = r.get("research_attempt")
    if attempt:
        items.append(f"Gap-only HLTV research: HTTP {e(attempt.get('status'))}; {e(attempt.get('error') or 'page read')} · read {e(attempt.get('read_utc'))}. {link(attempt.get('url'), 'research target')}")
    for rejected in r.get("rejected_quotes", []):
        items.append("Rejected quote: " + e(rejected.get("source")) + " — " + e("; ".join(rejected.get("reasons", []))) + ". " + link(rejected.get("source_url"), "source"))
    va, vb = r.get("vrs_a"), r.get("vrs_b")
    if r.get("own_p_a") is not None:
        items.append(f"Our line: {e(r['team_a'])} {pc(r['own_p_a'])} / {e(r['team_b'])} {pc(r['own_p_b'])} from Valve points {va['points']} (#{va['rank']}) vs {vb['points']} (#{vb['rank']}), "
                     f"slope k={board['meta']['k']} ({e(board['meta']['k_label'])}). {link(board['meta']['vrs'].get('url'), 'Valve standings')}")
    else:
        missing = [n for n, v in ((r["team_a"], va), (r["team_b"], vb)) if not v]
        items.append("Our line: withheld — " + e(r.get("own_line_limitation") or ("missing or ambiguous roster entry: " + ", ".join(missing))) + ".")
    if r.get("hltv_rank_a") or r.get("hltv_rank_b"):
        items.append(f"HLTV world ranking: {e(r['team_a'])} {('#' + str(r['hltv_rank_a'])) if r.get('hltv_rank_a') else 'not in captured ranking'} · "
                     f"{e(r['team_b'])} {('#' + str(r['hltv_rank_b'])) if r.get('hltv_rank_b') else 'not in captured ranking'}. {link(board['meta']['hltv'].get('url'), 'HLTV ranking')}")
    if r.get("hltv_url"):
        items.append(f"HLTV: {link(r['hltv_url'], 'match/team page')}" + (f" — {e(r['hltv_note'])}" if r.get("hltv_note") else ""))
    for f in r.get("factors", []):
        srcs = " ".join(link(u, "source") for u in f.get("source_urls", []))
        strength = f.get("strength", "")
        items.append(f"Factor ({e(strength)}) — {e(f['team'])}: {e(f['kind'])}. {e(f['summary'])} {srcs}")
    flags = "".join(f'<li><span class="flag">{e(fl)}</span> {e(board["flag_text"].get(fl, ""))}</li>' for fl in r.get("flags", []))
    srcs = " · ".join(link(u, u.split("/")[2] if "//" in u else u) for u in r.get("sources", []))
    return (f'<details><summary>Evidence, sources &amp; flags</summary><ul>{"".join(f"<li>{x}</li>" for x in items)}{flags}</ul>'
            f'<p class="small">Format: {e(r.get("format") or "not stated by any source")}{(" (" + e(r.get("format_source")) + ")") if r.get("format_source") else ""}. '
            f'Sources: {srcs}</p></details>')


def card(r: dict, board: dict) -> str:
    s = r.get("strategy") or {}
    la, lb = pair(r.get("p_a"), r.get("p_b"))
    fav_a = r.get("pick") == r["team_a"]
    pick_line = (f'<div class="pick">Pick: <strong>{e(r["pick"])}</strong><span class="pp">{la if fav_a else lb}</span></div>'
                 if r.get("pick") else '<div class="pick"><strong style="color:var(--red)">No pick — unresolved</strong></div>')
    bars = team_bar(r["team_a"], r.get("p_a"), fav_a and r.get("pick"), la) + team_bar(r["team_b"], r.get("p_b"), (not fav_a) and r.get("pick"), lb)
    basis = r.get("basis") or RUNG_TEXT.get(r.get("rung"))
    own = ""
    if r.get("own_p_a") is not None and r.get("rung") in ("A", "B"):
        own = f'<div class="own">Our line: {e(r["team_a"])} {pc(r["own_p_a"])} · {e(r["team_b"])} {pc(r["own_p_b"])}</div>'
    play = ""
    if s.get("class") and s.get("class") != "NO CROWD DATA":
        extra = f' — underdog {e(s.get("underdog"))} {pc(s.get("p_dog"))} vs {pc(s.get("crowd_dog"))} of players'
        play = f'<div class="play">{cls_tag(s["class"])} Leaderboard play: <b>{e(s.get("leaderboard_pick"))}</b>{extra}</div>'
    crowd = ""
    if r.get("crowd_a") is not None:
        crowd = (f'<div class="crowd">Hotspawn crowd (ownership only, not a probability): {e(r["team_a"])} {e(r["crowd_a"])}% · '
                 f'{e(r["team_b"])} {e(r["crowd_b"])}%' + (f' · {e(r["total_picks"])} picks' if r.get("total_picks") is not None else "") + "</div>")
    flags = "".join(f'<span class="flag">{e(f)}</span>' for f in r.get("flags", []) if f not in ("ALIAS",))
    hs = r.get("hotspawn_match_url") or r.get("lobby_url")
    return f"""<article class="card" id="m{e(r['match_id'])}" data-lock="{e(r.get('lock_utc'))}" data-tier="{e(r.get('tier'))}" data-class="{e(s.get('class', ''))}">
<div class="meta">{e(r.get('tier'))}-tier · {e(r.get('points'))} pts · {e(r.get('competition'))}{(' · ' + e(r.get('format'))) if r.get('format') else ''}</div>
<div class="lock">Locks <time datetime="{e(r.get('lock_utc'))}">{e(utc_label(r.get('lock_utc')))}</time> <span class="rel"></span></div>
<h3 class="match">{e(r['team_a'])} vs {e(r['team_b'])}</h3>
{pick_line}
<div class="bars">{bars}</div>
<div class="basis">Basis: {e(basis)} · <a href="{e(hs)}">Hotspawn #{e(r['match_id'])}</a></div>
{own}{play}{crowd}
<div>{flags}</div>
{evidence_list(r, board)}
</article>"""


LOCK_SCRIPT = """
(function(){var now=Date.now();document.querySelectorAll('.card[data-lock]').forEach(function(c){var t=Date.parse(c.getAttribute('data-lock'));var rel=c.querySelector('.rel');if(!t||!rel)return;var h=(t-now)/36e5;if(h<=0){c.classList.add('is-locked');rel.textContent='LOCKED';}else{rel.textContent=h<1?'in '+Math.round(h*60)+' min':h<48?'in '+h.toFixed(1)+' h':'in '+Math.round(h/24)+' d';}var tm=c.querySelector('time');if(tm){try{tm.title=new Date(t).toLocaleString();}catch(x){}}});
var bs=document.querySelectorAll('.filters button');bs.forEach(function(b){b.addEventListener('click',function(){bs.forEach(function(x){x.setAttribute('aria-pressed','false')});b.setAttribute('aria-pressed','true');var f=b.getAttribute('data-f');document.querySelectorAll('.card[data-lock]').forEach(function(c){var show=f==='all'||(f==='S'&&c.getAttribute('data-tier')==='S')||(f==='plays'&&/VALUE|CONTRARIAN|SITUATIONAL/.test(c.getAttribute('data-class')));c.style.display=show?'':'none';});});});})();
"""


def picks_page(board: dict) -> None:
    rows = [r for r in board["rows"] if r["status"] == "open"]
    by_day: dict[str, list] = {}
    for r in rows:
        d = parse_iso(r["start_utc"])
        by_day.setdefault(d.strftime("%A %d %B (UTC)") if d else "Date unknown", []).append(r)
    s = board["summary"]
    body = [f"""<h1>Every open Hotspawn CS2 match</h1>
<p class="lead">{s['open']} matches were open at this capture. Each card shows <strong>the pick and both teams' win probabilities</strong> first, then the basis, the leaderboard play, and the sources. Cards turn grey when their lock time passes on your clock.</p>
<div class="filters" role="group" aria-label="Filter"><button type="button" data-f="all" aria-pressed="true">All ({len(rows)})</button><button type="button" data-f="S" aria-pressed="false">S-tier only</button><button type="button" data-f="plays" aria-pressed="false">Leaderboard plays only</button></div>"""]
    if not rows:
        body.append('<p class="note red">No open CS2 fixtures in this snapshot. Check the <a href="https://play.hotspawn.com/lobby">live lobby</a>.</p>')
    for day, items in by_day.items():
        body.append(f'<h2 class="day">{e(day)}</h2>')
        body.extend(card(r, board) for r in items)
    body.append('<p class="small">S-tier deciders today (Aurora vs 9z, BetBoom vs Legacy): evidence, outside prices and the swing view are on '
                '<a href="strategy.html#day3">Day 3 — the two deciders</a>. Unresolved or model-only picks and their limitations: '
                '<a href="unresolved.html">Unresolved &amp; limitations</a>. Everything flagged: <a href="flagged.html">Flagged for Review</a>.</p>')
    page("picks.html", "All picks", "\n".join(body), board, script=LOCK_SCRIPT)


def plays_table(rows: list[dict]) -> str:
    out = ['<div class="tablewrap"><table><thead><tr><th>Lock (UTC)</th><th>Match</th><th class="num">Pts</th><th>Pick (prob.)</th><th>Underdog: chance vs crowd</th><th>Class</th><th>Leaderboard play</th><th class="num">EV cost</th><th>Factors vs favourite</th></tr></thead><tbody>']
    for r in rows:
        s = r.get("strategy") or {}
        out.append(f"<tr><td>{e(utc_label(r.get('lock_utc')))}</td><td><a href=\"picks.html#m{e(r['match_id'])}\">{e(r['team_a'])} vs {e(r['team_b'])}</a><br><span class=small>{e(r.get('competition'))}</span></td>"
                   f"<td class=num>{e(r.get('points'))}</td><td>{e(r.get('pick'))} {pc(r.get('pick_p'))}<br><span class=small>{e(RUNG_TEXT.get(r.get('rung')))}</span></td>"
                   f"<td>{e(s.get('underdog'))}: {pc(s.get('p_dog'))} vs {pc(s.get('crowd_dog'))}</td><td>{cls_tag(s.get('class'))}</td><td><b>{e(s.get('leaderboard_pick'))}</b></td>"
                   f"<td class=num>{'' if s.get('ev_cost_pts') is None else e(s.get('ev_cost_pts'))}</td><td>{e('; '.join(s.get('factors_against_favourite') or []) or '—')}</td></tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def day3_section(board: dict) -> str:
    """B6 entry points retained; a second, static price average can never override the live row."""
    data = read_json(DAY3_FILE, {}) or {}
    by_id = {str(r.get("match_id")): r for r in board.get("rows", [])}
    out = ['<p><a href="twc.html">Full TWC review, sourced maps, roster timeline &amp; optional chasing choices →</a>. '
           'These cards use the same capture and evidence gates as All picks, never a second hand-maintained probability.</p>']
    for match in data.get("matches", []):
        row = by_id.get(str(match.get("hotspawn_id")))
        out.append('<p>' + link(match.get('hltv_match_url'), match.get('team_a','') + ' vs ' + match.get('team_b','')) + ' · ' + link(match.get('hotspawn_match_url'), 'Hotspawn fixture') + '</p>')
        if row and row.get('status') == 'open':
            out.append(card(row, board))
        elif not row:
            out.append('<p class="note">Coverage gap: no board row for this researched fixture. No current pick or probability is fabricated from an older research price. <a href="unresolved.html">Research limitation →</a></p>')
        else:
            out.append('<p class="small">Not open at this capture; see <a href="all.html">the source-linked inventory</a>. No archived probability is promoted as a new pick.</p>')
    return ''.join(out)


def coverage_gaps_section(board: dict) -> str:
    """A previously researched ID missing from a capture is a watch item, not proof of live listing."""
    data = read_json(DAY3_FILE, {}) or {}
    have = {str(r.get('match_id')) for r in board.get('rows', [])}
    gaps = [m for m in data.get('matches', []) if str(m.get('hotspawn_id')) not in have]
    if not gaps: return ''
    rows = ''.join('<li>' + e(m.get('hotspawn_id')) + ' · ' + link(m.get('hltv_match_url'), m.get('team_a','') + ' vs ' + m.get('team_b','')) + ' · ' + link(m.get('hotspawn_match_url'), 'last known Hotspawn source') + '</li>' for m in gaps)
    return '<h3>Coverage watch — researched fixtures absent from this capture</h3><p>Earlier linked evidence is not proof these matches are still pickable. No current side is invented. <a href="strategy.html#day3">Day-3 research →</a></p><ul>' + rows + '</ul>'


def strategy_page(board: dict) -> None:
    rows = [r for r in board["rows"] if r["status"] == "open" and r.get("strategy")]
    rows.sort(key=lambda r: (CLASS_ORDER.index(r["strategy"]["class"]) if r["strategy"]["class"] in CLASS_ORDER else 9, r.get("lock_utc") or ""))
    week = board["meta"]["hotspawn"].get("week") or {}
    prizes = ", ".join(f"{p.get('rank')}: {p.get('title')}" for p in week.get("prizes", []))
    d1 = board["day1"]
    d1rows = []
    for x in d1["matches"]:
        st = x.get("strategy") or {}
        d1rows.append(f"<tr><td><a href=\"{e(x['hltv'])}\">{e(x['team_a'])} vs {e(x['team_b'])}</a></td><td>{e(x['team_a'])} {pc(x['p_a'])} / {pc(x['p_b'])}<br><span class=small>Pinnacle {x['odds_a']:.3f} / {x['odds_b']:.3f}</span><br>{link(x.get('book_source_url'), 'archived Pinnacle endpoint')} · {e(x.get('book_read_utc'))}</td>"
                      f"<td>{pc(x.get('own_p_a'))} / {pc(x.get('own_p_b'))}</td><td>{e(x['crowd_a'])}% / {e(x['crowd_b'])}%</td><td>{e(x['pick'])}</td>"
                      f"<td>{cls_tag(st.get('class'))} {e(st.get('leaderboard_pick'))}</td><td><b>{e(x['winner'])}</b> {e(x['score'])}<br><span class=small>{e(x['maps'])}</span></td>"
                      f"<td class=\"{'ok' if x['pick_correct'] else 'miss'}\">{'✓' if x['pick_correct'] else '✗'}</td><td class=\"{'ok' if x.get('leaderboard_correct') else 'miss'}\">{'✓' if x.get('leaderboard_correct') else '✗'}</td></tr>")
    info = d1.get("info", {})
    graded = board.get("graded", [])
    gr = [g for g in graded if g.get("result")]
    grows = "".join(f"<tr><td>{e(g['team_a'])} vs {e(g['team_b'])}</td><td>{e(g.get('pick'))}</td><td>{e(g.get('class'))} → {e(g.get('leaderboard_pick'))}</td><td>{link(g['result'].get('source_url'), g['result']['winner'])}<br><span class=small>{e(g['result'].get('kind'))}</span></td>"
                    f"<td class=\"{'ok' if g.get('pick_correct') else 'miss'}\">{'✓' if g.get('pick_correct') else '✗'}</td><td class=\"{'ok' if g.get('leaderboard_correct') else 'miss'}\">{'✓' if g.get('leaderboard_correct') else '✗'}</td></tr>" for g in gr)
    pending = [g for g in graded if not g.get("result")]
    lessons = "".join(f"<li>{e(t)}</li>" for t in d1.get("info", {}).get("lessons", []) or read_json(RESEARCH / "day1_twc2026.json", {}).get("lessons", []))
    body = f"""<h1>Leaderboard plan: contrarian, not reckless</h1>
<p class="lead">Every Hotspawn player who picks the same side scores the same points, so you only climb when you are right where the field is wrong. The plan below fades the crowd <strong>only</strong> when the underdog's real chance is high — judged by outside prices and our own line together, never by the crowd itself.</p>
<div class="note green"><strong>How to use it:</strong> take every <span class="tag c-VALUE">VALUE</span> play (likely winner that most players are against). Add <span class="tag c-CONTRARIAN">CONTRARIAN</span> plays when you need to gain ground. Use <span class="tag c-SITUATIONAL">SITUATIONAL</span> plays when you are chasing; they rest on verified roster changes, stand-ins or late replacements. Treat <span class="tag c-LONG-SHOT">LONG SHOT</span> underdogs as an occasional punt only when far behind with few matches left. S-tier matches are worth {e(next((r.get('points') for r in board['rows'] if r.get('tier') == 'S'), 7))} points versus 2 for C-tier, so the S-tier calls matter most.</div>
<p class="small">This week: {e(week.get('weekStartUtc'))} → {e(week.get('weekEndUtc'))} (Hotspawn payload). Prizes: {e(prizes) or 'not published in payload'}. Hotspawn requires at least 10 picks to qualify (lobby text).</p>
<h2>Plays for the open slate ({len(rows)})</h2>
{plays_table(rows)}
<p class="small">EV cost = expected points given up versus taking the published pick, measured on the published probabilities (points × gap in win chance). Underdog chance = heuristic average of the market and our eligible own line (separate estimates, not statistically independent evidence) (our line is dropped when Valve's roster is out of date). Crowd = Hotspawn's pick share, used here only to measure how contrarian a pick is.</p>
<h2 id="day3">Day 3 — the two deciders</h2>
{day3_section(board)}
<h2>The heuristic rule (v3: evidence eligibility)</h2>
<ul>
<li><span class="tag c-VALUE">VALUE</span> crowd majority sits on the published favourite’s opponent → play the favourite.</li>
<li><span class="tag c-CONTRARIAN">CONTRARIAN</span> underdog consensus ≥ 38%, every estimate ≥ 30%, and crowd share at least 10 points below its chance → play the underdog.</li>
<li><span class="tag c-SITUATIONAL">SITUATIONAL</span> underdog consensus ≥ 30%, every estimate ≥ 25%, crowd share ≤ half its chance, a strong/moderate verified factor against the favourite and none against the underdog → play the underdog.</li>
<li><span class="tag c-LONG-SHOT">LONG SHOT</span> underdog ≥ 20% with ≤ 10% of players → keep the favourite (optional punt).</li>
<li><span class="tag c-CHALK">CHALK</span> everything else → keep the favourite.</li>
</ul>
<p class="note">Honesty note: earlier v2 thresholds were chosen after day 1 and its reported 4/4 was in-sample, not a forecast. This revision keeps the thresholds but tightens source/roster eligibility; July’s Aurora change is now weak context only. The table below is retrospective, not a backfilled pre-lock record. Archived live picks retain their original rule version. No leaderboard strategy has been validated on four matches.</p>
<h2>Day 1 review — Thunderpick World Championship 2026 (14 Oct)</h2>
<p>{e(info.get('event', {}).get('format', ''))} {link(info.get('event', {}).get('hltv'), 'HLTV event')} · {link(info.get('event', {}).get('results'), 'HLTV results')}</p>
<div class="tablewrap"><table><thead><tr><th>Match</th><th>Market (pre-match)</th><th>Our line</th><th>Crowd</th><th>Market pick</th><th>Retrospective plan</th><th>Result (HLTV)</th><th>Pick</th><th>Plan</th></tr></thead><tbody>{''.join(d1rows)}</tbody></table></div>
<p class="small">Prices: {link(info.get('price_source', {}).get('url'), info.get('price_source', {}).get('label'))} (read {e(info.get('price_source', {}).get('read_utc'))}). Crowd: {link(info.get('crowd_source', {}).get('url'), info.get('crowd_source', {}).get('label'))} — {e(info.get('crowd_source', {}).get('note'))} Board pick before lock: {link(info.get('pick_source', {}).get('url'), info.get('pick_source', {}).get('label'))}.</p>
<h3>What day 1 taught us</h3><ul>{lessons}</ul>
<p><a href="twc.html">Day 2 review, group standings and day-3 picks for the TWC 2026 deciders →</a></p>
<h3>The upset: 9z 2-0 Aurora</h3>
<p>Aurora rebuilt in July 2026 — Jimpphat joined on 3 Jul and kyxsan became in-game leader on 8 Jul (coach ash). That is about three months before TWC, and the new five had just finished 3rd at ESL Pro League S24, beating 9z 2-0 there on 3 Oct. In Malta 9z won Inferno 13-11 and Nuke 13-1 (luchov 1.61). Pinnacle had 9z at 27%, our official-points line at 39%, and only 5% of Hotspawn players picked 9z. {link('https://www.hltv.org/team/11861/aurora', 'HLTV: Aurora roster & transfers')} · {link('https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026', 'HLTV match report')}</p>
<h2>Grading since launch</h2>
<p>The last recorded pre-lock pick is frozen on the next refresh after lock (not necessarily a read at the exact lock time) and graded once a result exists (verified HLTV result first; otherwise the Polymarket resolution, which names HLTV as its source, marked provisional).</p>
{('<div class="tablewrap"><table><thead><tr><th>Match</th><th>Pick</th><th>Plan</th><th>Winner</th><th>Pick</th><th>Plan</th></tr></thead><tbody>' + grows + '</tbody></table></div>') if gr else '<p class="small">No graded fixtures yet.</p>'}
<p class="small">{len(pending)} frozen pick(s) awaiting a result.</p>
"""
    page("strategy.html", "Leaderboard plan", body, board, script=LOCK_SCRIPT)


def twc_page(board: dict) -> None:
    """Sourced historical facts + current board rows; never keep a second, stale day-3 prediction."""
    d = read_json(RESEARCH / "twc2026.json", {})
    if not d:
        return
    by_id = {str(r["match_id"]): r for r in board["rows"]}
    result_rows = []
    for m in d.get("series", []):
        veto = " · ".join(f"{k}: {v}" for k, v in (m.get("map_picks") or {}).items())
        result_rows.append(f'<tr><td>{e(m.get("day"))}<br>{e(m.get("stage"))}</td><td><b>{e(m.get("score"))}</b>'
                          f'<br><span class="small">{e(m.get("note"))}</span></td><td>{e(m.get("maps"))}'
                          f'<br><span class="small">{e(veto)}</span></td><td>{link(m.get("hltv"), "HLTV match / veto")}'
                          f'<br><span class="small">Checked {e(m.get("maps_verified_utc"))}</span></td></tr>')
    standings = []
    for group in ("group_a", "group_b"):
        for r in d.get("standings", {}).get(group, []):
            standings.append(f'<tr><td>{e(group[-1].upper())}</td><td>{e(r.get("team"))}</td>'
                             f'<td>{e(r.get("record"))}</td><td>{e(r.get("state"))}</td>'
                             f'<td>{link(r.get("source_url"), "HLTV bracket")}</td></tr>')
    plays = []
    for f in d.get("day3", []):
        live = by_id.get(str(f.get("hotspawn_match_id")))
        live_html = card(live, board) if live and live["status"] == "open" else (
            '<p class="note">This fixture is not open in this capture. No historic probability is being presented '
            'as a new pick. Check the <a href="all.html">full inventory</a> and the '
            '<a href="https://play.hotspawn.com/lobby">live lobby</a>.</p>')
        chasing = '<p class="small">No automatic upset watch meets the conservative gates at this capture. Keep the headline pick.</p>'
        if live and live.get("rung") in ("A", "B") and live.get("p_a") is not None and live.get("total_picks", 0) >= 10:
            is_a = live["p_a"] < live["p_b"]
            pd = live["p_a"] if is_a else live["p_b"]
            dog = live["team_a"] if is_a else live["team_b"]
            crowd = live.get("crowd_a") if is_a else live.get("crowd_b")
            total = (live.get("crowd_a") or 0) + (live.get("crowd_b") or 0)
            ownership = crowd / total if crowd is not None and total else None
            if ownership is not None and pd >= .30 and pd - ownership >= .10:
                cost = (live.get("points") or 0) * (1 - 2 * pd)
                chasing = (f'<p class="note"><b>Optional chasing pick: {e(dog)}</b> — outside line {pc(pd, 1)} '
                           f'versus {pc(ownership, 1)} crowd ownership ({e(live["total_picks"])} recorded picks). '
                           f'This is not the most likely winner. Expected-points cost versus the favourite: '
                           f'<b>{cost:.2f}</b> from {e(live.get("points"))} × (P(favourite) − P(underdog)). '
                           'Use only as a deliberate risk to differentiate, not as a proven edge or a guarantee of rank gain.</p>')
        limits = "".join(f'<li>{e(x)}</li>' for x in f.get("limitations", []))
        plays.append(f'<section><h2>{e(f["team_a"])} vs {e(f["team_b"])} · {e(f.get("stage"))}</h2>'
                     f'<p>{e(f.get("analysis"))} {link(f.get("hltv_url"), "HLTV: BO3 / group decider")} · {link(f.get("hotspawn_url"), "Hotspawn fixture")}</p>'
                     + live_html + chasing + '<details><summary>Limits on this recommendation</summary><ul>' + limits + '</ul></details></section>')
    situations = []
    for row in d.get("situations", []):
        srcs = " · ".join(link(x.get("url"), x.get("label")) for x in row.get("sources", []))
        situations.append(f'<tr><td><b>{e(row.get("team"))}</b></td><td>{e(row.get("what"))}'
                          f'<br><span class="small">{e(row.get("turnaround"))}</span></td>'
                          f'<td>{e(row.get("verdict"))}</td><td>{srcs}</td></tr>')
    ev = d.get("event", {})
    ev_src = " · ".join(link(x.get("url"), x.get("label")) for x in ev.get("sources", []))
    lessons = "".join(f'<li>{e(x)}</li>' for x in d.get("lessons", []))
    body = f"""<h1>TWC 2026: day-3 picks &amp; what days 1–2 changed</h1>
<p class="lead">Start with the two deciders below. The <b>headline pick maximizes expected points</b> on the published line;
a separate <b>optional chasing pick</b> can help differentiate if you accept the risk. Neither guarantees a leaderboard climb.
<a href="picks.html">All CS2 picks →</a> · <a href="#day2">Day-2 results ↓</a> · <a href="unresolved.html">Unresolved &amp; limitations</a>.</p>
<p class="small">{e(ev.get("name"))}, {e(ev.get("dates"))}, {e(ev.get("prize_pool"))}. {e(ev.get("format"))} {ev_src}.</p>
{''.join(plays)}
<h2 id="day2">Every result from days 1–2</h2>
<div class="tablewrap" tabindex="0" role="region" aria-label="TWC results; scroll horizontally for sources"><table>
<thead><tr><th>Day / stage</th><th>Result / meaning</th><th>Maps / veto</th><th>Source</th></tr></thead><tbody>{''.join(result_rows)}</tbody></table></div>
<p class="small">{e(d.get("maps_convention"))} Result research checked {e(d.get("read_utc"))}. Probabilities and lock times above use the current board capture instead.</p>
<h2>Groups after day 2</h2><div class="tablewrap"><table><thead><tr><th>Group</th><th>Team</th><th>Record</th><th>Status</th><th>Source</th></tr></thead><tbody>{''.join(standings)}</tbody></table></div>
<p class="small">Records count the linked series results. No unverified group rank, round differential or tiebreak value is filled in.</p>
<h2>Roster, onboarding &amp; rest: facts versus narrative</h2><div class="tablewrap"><table><thead><tr><th>Team</th><th>Verified context</th><th>Effect / limits</th><th>Source</th></tr></thead><tbody>{''.join(situations)}</tbody></table></div>
<h2>Contrarian, not reckless</h2><ul>{lessons}</ul>
<p class="note">We do not know your current rank, points gap or the full field’s correlated picks. Ownership is only the percentage of Hotspawn picks on each side, never a win probability. July’s roster rebuild is not evidence of an unpriced October edge.</p>
"""
    page("twc.html", "TWC day-3 picks & day-2 review", body, board, script=LOCK_SCRIPT)


def h2h_li(item: str) -> str:
    """One head-to-head research line: everything before the URL is text, the URL becomes a source link."""
    urls = re.findall(r"https?://\S+", item)
    text = re.sub(r"https?://\S+", "", item)
    text = re.sub(r"\s*Source:\s*", " ", text)
    text = re.sub(r"\s*\u2014\s*$", "", text).strip().strip("\u2014- ").strip()
    text = re.sub(r"\s{2,}", " ", text).strip()
    links = " \u00b7 ".join(f'<a href="{u}">source</a>' if u else "" for u in urls)
    return f"<li>{e(text)} {links}</li>"


def pair_bar(name_a: str, name_b: str, pa, pb) -> str:
    if pa is None or pb is None:
        return ""
    return f'<div class="bars">{team_bar(name_a, pa / 100.0, pa >= pb)}{team_bar(name_b, pb / 100.0, pb > pa)}</div>'


def unresolved_section(board: dict, full: bool) -> str:
    """An actual per-fixture research trail, not a claim that an unrequested source was checked."""
    rows = [r for r in board["rows"] if r["status"] == "open"]
    unresolved = [r for r in rows if not r.get("pick")]
    fallback = [r for r in rows if r.get("rung") in ("B", "C")]
    pm = sum(1 for r in fallback if r.get("rung") == "B" and not r.get("relay"))
    relays = sum(1 for r in fallback if r.get("relay"))
    own = sum(1 for r in fallback if r.get("rung") == "C")
    out = [f'<p><strong>{len(unresolved)} unresolved picks</strong>: no supported probability/side is invented. '
           f'<strong>{len(fallback)} non-featured resolutions</strong>: {pm} prediction-market, {relays} relayed esportsbook, '
           f'{own} own estimate. Every captured fixture is retained, including low-tier and unpriced matches. '
           '<a href="picks.html">Open all match cards →</a></p>']

    def research_trail(r):
        attempt = r.get("research_attempt") or {}
        researched = (f'HLTV: {link(attempt.get("url"), "target")} · HTTP {e(attempt.get("status"))} '
                      f'{e(attempt.get("error") or "page read")} · {e(attempt.get("read_utc"))}') if attempt else (
                         'HLTV: ' + link(r.get("hltv_url"), 'curated source') + ' (no additional live match-page read recorded in this capture)')
        books = 'Esportsbooks: no eligible Pinnacle quote in the capture; bo3.gg relay ' + e(board["meta"].get("esportsbooks", {}).get("status", "not requested"))
        rejected = '; '.join('; '.join(q.get('reasons', [])) for q in r.get('rejected_quotes', []))
        return researched + '<br>' + books + ('<br>Rejected: ' + e(rejected) if rejected else '')

    def sources(r):
        urls = list(dict.fromkeys([r.get('hotspawn_match_url') or r.get('lobby_url')] + r.get('sources', [])))
        return ' · '.join(link(u, u.split('/')[2]) for u in urls if u)

    out.append(coverage_gaps_section(board))
    out.append('<p><a href="release-audit.html#unresolved-research">Independent gap research &amp; evidence limitations</a>. Missing or ambiguous roster entry is not the same as an absent team.</p>')
    if unresolved:
        out.append('<h3>Unresolved picks — limitation per match</h3><ul class="plain">')
        for r in unresolved:
            why = r.get('own_line_limitation') or r.get('basis') or 'No eligible outside price or independently supported estimate'
            if 'NO_DIRECTION' in r.get('flags', []): why = 'Eligible price is exactly 50/50; no independent line supports a directional pick.'
            out.append(f'<li><a href="picks.html#m{e(r["match_id"])}"><b>{e(r["team_a"])} vs {e(r["team_b"])}</b></a>'
                       f'<br>{e(why)}<br><span class="small">{research_trail(r)}<br>{sources(r)}</span></li>')
        out.append('</ul>')
    else:
        out.append('<p class="note green">No unresolved picks in this capture. This is not a promise that every future listing can be priced: unsupported new rows will appear here with blanks.</p>')
    if fallback:
        tr = []
        for r in fallback:
            limit = 'Prediction-market outcome price, not bookmaker odds or a guaranteed executable quote.'
            if r.get('relay'): limit = 'Named sportsbook price relayed by bo3.gg; not verified directly with the book. Secondary, flagged evidence.'
            if r['rung'] == 'C': limit = 'Own match-level rating estimate, not a bookmaker quote; no format-specific, map-veto or fatigue calibration.'
            if r.get('own_line_limitation'): limit += ' Independent own line withheld: ' + r['own_line_limitation'] + '.'
            tr.append(f'<tr><td><a href="picks.html#m{e(r["match_id"])}">{e(r["team_a"])} vs {e(r["team_b"])}</a><br>{e(utc_label(r.get("lock_utc")))}</td>'
                      f'<td><b>{e(r.get("pick"))}</b><br>{e(r["team_a"])} {pc(r.get("p_a"),1)} / {e(r["team_b"])} {pc(r.get("p_b"),1)}<br>{e(r.get("basis"))}</td>'
                      f'<td>{research_trail(r)}</td><td>{e(limit)}<br>{sources(r)}</td></tr>')
        out.append('<h3>Resolved below the featured rung — research &amp; limits</h3><div class="tablewrap"><table><thead><tr>'
                   '<th>Match / lock UTC</th><th>Pick / both probabilities</th><th>HLTV → esportsbooks → other lines</th><th>Limitations / sources</th>'
                   '</tr></thead><tbody>' + ''.join(tr) + '</tbody></table></div>')
    out.append("""<h3>Limitations that apply to every pick</h3><ul>
<li>Four-hour scheduled snapshots, not live odds. Scheduling and source access are best effort; a capture older than eight hours is marked stale. Check each read time and absolute UTC lock.</li>
<li>Both teams, competition, series format (when independently known), freshness and rematch identity must agree. Rejected or stale quotes do not silently drive picks.</li>
<li>HLTV is tried for non-featured fixtures first. A refusal is recorded; a 403/429 circuit breaker is not a successful read. Then esportsbook relays and other external lines are checked automatically.</li>
<li>The own line is fitted to Valve’s whole-match results, not map probabilities. No extra BO3 transform is applied. Missing teams, unknown formats, known roster mismatches and ratings older than 45 days withhold that fallback.</li>
<li>Roster news can already be priced into the market. A three-month-old rebuild is context only; no unverified travel, sleep, injury or fatigue adjustment is made.</li>
<li>Hotspawn crowd percentages are ownership only. Small samples, rounding and correlated picks limit leaderboard analysis; low ownership never increases a team’s win probability.</li>
</ul>""")
    return '\n'.join(out)


def unresolved_page(board: dict) -> None:
    body = f"""<h1>Unresolved picks &amp; limitations</h1>
<p class="lead">Featured matches are priced by a sharp bookmaker. When one is not, we climb the research ladder — HLTV first, then esportsbooks, then other betting lines — and fall back to our own line from Valve's official standings. Nothing is guessed: if no source supports a value it stays blank and is flagged.</p>
{unresolved_section(board, True)}"""
    page("unresolved.html", "Unresolved & limitations", body, board)


def flagged_page(board: dict) -> None:
    irr = read_json(RESEARCH / "irregularities.json", {}).get("items", [])
    irows = "".join(f"<tr><td>{e(i['id'])}</td><td>{e(i['status'])}</td><td><b>{e(i['title'])}</b><br>{e(i['detail'])}</td><td>{'<br>'.join(link(u, u.split('/')[2]) for u in i.get('evidence', []))}</td></tr>" for i in irr)
    frows = []
    for r in board["rows"]:
        if r["status"] == "stale":
            continue
        for f in r.get("flags", []):
            anchor = f"picks.html#m{e(r['match_id'])}" if r["status"] == "open" else f"all.html#f{e(r['match_id'])}"
            frows.append(f"<tr><td><a href=\"{anchor}\">{e(r['match_id'])}</a></td><td>{e(r['team_a'])} vs {e(r['team_b'])}</td><td>{e(r['status'])}</td><td><span class=flag>{e(f)}</span></td><td>{e(board['flag_text'].get(f, ''))}</td><td>{' '.join(link(u, u.split('/')[2]) for u in r.get('sources', [])[:4])}</td></tr>")
    stale = sum(1 for r in board["rows"] if r["status"] == "stale")
    body = f"""<h1>Flagged for Review</h1>
<p class="lead">Known unverified, disputed or irregular items in the primary board are listed here with evidence. Unconfirmable values stay blank. Research flags do not block publication; a broken build or site does. The preserved historical dashboards are not certified by this scoped audit (IR-26).</p>
<h2>Irregularities found in research and review</h2>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Status</th><th>Finding</th><th>Evidence</th></tr></thead><tbody>{irows}</tbody></table></div>
<p class="small">The current line-by-line primary-board review is <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/reviews/6b23e38f-verification.md">6b23e38f verification</a>; the earlier review is in <a href="{REPO_URL}/blob/main/reviews/22be6967-verification.md">reviews/22be6967-verification.md</a>.</p>
<h2>Fixture flags in this snapshot</h2>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Match</th><th>Status</th><th>Flag</th><th>Meaning</th><th>Evidence</th></tr></thead><tbody>{''.join(frows) or '<tr><td colspan=6>No flags.</td></tr>'}</tbody></table></div>
<p class="small">{stale} stale listings (lock passed more than 36 h ago) are flagged STALE_LISTING and listed in the <a href="all.html">full inventory</a>.</p>"""
    page("flagged.html", "Flagged for Review", body, board)


def all_page(board: dict) -> None:
    rows = []
    for r in board["rows"]:
        res = (r.get("result") or {}).get("winner", "")
        rows.append(f"<tr id=\"f{e(r['match_id'])}\"><td>{e(r['match_id'])}</td><td>{e(r['status'])}</td><td>{e(utc_label(r.get('start_utc')))}</td><td>{e(r.get('tier'))}</td><td>{e(r.get('competition'))}</td>"
                    f"<td>{e(r['team_a'])} vs {e(r['team_b'])}</td><td>{e(r.get('pick') or '')}</td><td class=num>{pc(r.get('p_a'))} / {pc(r.get('p_b'))}</td><td>{e(RUNG_TEXT.get(r.get('rung'), ''))}</td>"
                    f"<td>{e(res)}</td><td>{' '.join('<span class=flag>' + e(f) + '</span>' for f in r.get('flags', []))}</td><td>{link(r.get('hotspawn_match_url') or r.get('lobby_url'), 'Hotspawn')}</td></tr>")
    s = board["summary"]
    body = f"""<h1>Every captured Hotspawn CS2 fixture</h1>
<p class="lead">{s['fixtures']} fixtures in the payload: {s['open']} open, {s['locked_recent']} locked in the last 36 h, {s['stale_listings']} stale listings (lock passed long ago but still in Hotspawn's data; not pickable).</p>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Status</th><th>Start</th><th>Tier</th><th>Tournament</th><th>Match</th><th>Pick</th><th class=num>Prob. A / B</th><th>Basis</th><th>Result</th><th>Flags</th><th>Link</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"""
    page("all.html", "All fixtures", body, board)


def method_page(board: dict) -> None:
    m = board["meta"]
    cal = m.get("calibration") or {}
    hold = cal.get("holdout") or {}
    prov = read_json(DATA / "capture.json", {}).get("provenance", [])
    prow = "".join(f"<tr><td>{link(p.get('url'), (p.get('url') or '')[:70])}</td><td>{e(p.get('status'))}</td><td>{e(p.get('fetched_utc'))}</td><td class=num>{e(p.get('bytes'))}</td><td><code>{e((p.get('sha256') or '')[:12])}</code></td><td>{e(p.get('error') or '')}</td></tr>" for p in prov)
    pages = "".join(f"<li>{link(p.get('url'))}: HTTP {e(p.get('status'))}, {e(p.get('state_rows'))} payload rows, read {e(p.get('read_utc'))}{(' — ' + e(p.get('error'))) if p.get('error') else ''}</li>" for p in m["hotspawn"].get("pages", []))
    body = f"""<h1>Method, sources &amp; read times</h1>
<h2>1. Fixture list (Hotspawn)</h2>
<p>Hotspawn Play is an Angular app that ships its data in the page as <code>&lt;script id="ng-state"&gt;</code>. The collector reads all three CS2 surfaces and takes, per fixture: id, tournament, tier, stage, points breakdown, teams, <code>scheduled_start_time</code> and <code>lock_time</code> (epoch ms), plus the crowd pick share (kept as "ownership").</p><ul>{pages}</ul>
<h2>2. Probability ladder</h2>
<ol><li><b>Pinnacle</b> whole-match moneyline from the public guest JSON behind {link(m['pinnacle'].get('page_url'), 'pinnacle.com CS2')}; American prices → decimal; margin removed proportionally (p = (1/o) / Σ(1/o)).</li>
<li><b>Secondary esportsbook relay</b> from bo3.gg, only after the HLTV gap attempt. A named, active, same-book two-sided line, labelled relayed and not verified directly with the sportsbook.</li>
<li><b>Polymarket</b> match-winner markets (tag "counter strike 2"), outcome prices normalised to 100% (not asserted to be a fresh midpoint or executable bid/ask). A prediction market, labelled as such.</li>
<li><b>Our own line</b>: P(A) = 1 / (1 + 10^(−k·ΔPoints/400)) with Valve's official points ({link(m['vrs'].get('url'), 'standings ' + str(m['vrs'].get('as_of')))}). k = {e(m['k'])} ({e(m['k_label'])}); trained on {e(cal.get('n_train'))} Valve-rated matches, held out on {e(cal.get('n_test'))} (window {e(cal.get('last_window'))}): log-loss {e(hold.get('log_loss_fitted'))} vs {e(hold.get('log_loss_valve_raw'))} for Valve's raw curve; Brier {e(hold.get('brier_fitted'))} vs {e(hold.get('brier_valve_raw'))}.</li>
<li><b>Unresolved</b>: blank pick, flagged, listed on the Unresolved page with the research trail.</li></ol>
<p>Joins require both teams to match after verified aliases ({link(REPO_URL + '/blob/main/hotspawn/research/aliases.json', 'aliases.json')}) the competition family/region/edition and a kickoff within 6 h, with no equally close or nearer same-pair rematch; any gap is flagged. Unknown scope, nonfinite/terminal prices, closed markets and quotes older than 8 h are rejected, not quietly used. HLTV ranks are shown as a cross-check ({link(m['hltv'].get('url'), 'HLTV ranking')}, status {e(m['hltv'].get('status'))}).</p>
<h2>3. Leaderboard plan</h2><p>See <a href="strategy.html">Leaderboard plan</a>; thresholds live in {link(REPO_URL + '/blob/main/hotspawn/model.py', 'model.py')}. Situational factors come from {link(REPO_URL + '/blob/main/hotspawn/research/notes.json', 'research/notes.json')} (HLTV links, read times, strength) plus an automatic "new five" check on Valve's per-team match tables.</p>
<h2>4. Automation</h2><p>{link(REPO_URL + '/blob/main/.github/workflows/hotspawn-22be6967.yml', 'GitHub Actions workflow')} is scheduled every 4 hours (best effort; captures older than 8 hours are marked stale): collect → calibrate → model → build → per-row audit → tests → required real-browser phone/tablet check; pages are committed only when the tests pass, otherwise the last good pages stay up and the failure is visible in the run log.</p>
<h2>5. Every request in this snapshot</h2>
<div class="tablewrap"><table><thead><tr><th>URL</th><th>HTTP</th><th>Read (UTC)</th><th class=num>Bytes</th><th>SHA-256</th><th>Error</th></tr></thead><tbody>{prow or '<tr><td colspan=6>Offline build (no network requests recorded).</td></tr>'}</tbody></table></div>"""
    page("method.html", "Method & sources", body, board)


def index_page(board: dict) -> None:
    s = board["summary"]
    open_rows = [r for r in board["rows"] if r["status"] == "open"]
    nxt = sorted(open_rows, key=lambda r: r.get("lock_utc") or "")[:6]
    plays = [r for r in open_rows if (r.get("strategy") or {}).get("class") in ("VALUE", "CONTRARIAN", "SITUATIONAL")]
    plays.sort(key=lambda r: r.get("lock_utc") or "")

    def li(r):
        st = r.get("strategy") or {}
        return (f"<li><a href=\"picks.html#m{e(r['match_id'])}\"><b>{e(r['team_a'])} vs {e(r['team_b'])}</b></a> · {e(r.get('tier'))}-tier · locks {e(utc_label(r.get('lock_utc')))}<br>"
                f"Pick <b>{e(r.get('pick') or '—')}</b> {pair(r.get('p_a'), r.get('p_b'))[0 if r.get('pick') == r['team_a'] else 1]} ({e(r['team_a'])} {pair(r.get('p_a'), r.get('p_b'))[0]} / {e(r['team_b'])} {pair(r.get('p_a'), r.get('p_b'))[1]}) · {cls_tag(st.get('class'))} play <b>{e(st.get('leaderboard_pick'))}</b></li>")
    d1 = board["day1"]["matches"]
    body = f"""<h1>Hotspawn CS2 — executive summary</h1>
<p class="lead">A source-backed pick and two-sided probability for every resolvable open Counter-Strike 2 match in the captured Hotspawn slate; unsupported rows stay visible with blanks, plus a leaderboard plan that fades the crowd only when the numbers support it.</p>
<div class="btns">
<a class="btn primary" href="picks.html"><strong>All picks ({s['open']} open) →</strong><span>One card per match: pick, both probabilities, sources.</span></a>
<a class="btn" href="strategy.html"><strong>Leaderboard plan</strong><span>{s['leaderboard_classes'].get('VALUE', 0)} value · {s['leaderboard_classes'].get('CONTRARIAN', 0)} contrarian · {s['leaderboard_classes'].get('SITUATIONAL', 0)} situational plays; day-1 review.</span></a>
<a class="btn" href="twc.html"><strong>TWC 2026 day review</strong><span>Every series of days 1-2 with sources, the groups, and both day-3 deciders with all outside lines plus our own.</span></a>
<a class="btn" href="unresolved.html"><strong>Unresolved &amp; limitations</strong><span>{s['open_rung'].get('B', 0) + s['open_rung'].get('C', 0)} via the research ladder · {s['open_unresolved']} without a pick.</span></a>
<a class="btn" href="flagged.html"><strong>Flagged for Review</strong><span>Irregularities and per-match flags with evidence.</span></a>
</div>
<div class="stats" aria-label="Coverage">
<div><b>{s['open']}</b><span>open matches</span></div><div><b>{s['open_with_pick']}</b><span>with a pick</span></div>
<div><b>{s['open_rung'].get('A', 0)}</b><span>featured (Pinnacle)</span></div><div><b>{s['open_rung'].get('B', 0) + s['open_rung'].get('C', 0)}</b><span>via research ladder</span></div>
</div>
<h2>Next to lock</h2><ul class="plain">{''.join(li(r) for r in nxt) or '<li>No open fixtures in this snapshot.</li>'}</ul>
<h2>Leaderboard plays right now</h2><ul class="plain">{''.join(li(r) for r in plays) or '<li>No value/contrarian/situational plays — take the picks.</li>'}</ul>
<p><a href="strategy.html">Why these plays, and the rule behind them →</a></p>
<h2>Day 1 in one line</h2>
<p>TWC 2026 day 1: all four series ended 2-0; favourites won three. The upset was <b>9z 2-0 Aurora</b> (archived pre-lock market 27%, retrospective own line 39%, archived ownership 5%). Market picks went {s['day1_review']['picks_correct']}/{s['day1_review']['matches']}. <a href="strategy.html">Full review →</a></p>
<h2 id="day3">Day 3 — the two deciders</h2>
{day3_section(board)}
<h2 id="unresolved">Unresolved picks &amp; limitations</h2>
{unresolved_section(board, True)}
<h2>Coverage &amp; freshness</h2>
<p class="small">{s['fixtures']} fixtures in Hotspawn's payload: {s['open']} open, {s['locked_recent']} recently locked, {s['stale_listings']} stale listings (<a href="all.html">full inventory</a>). Sources: Pinnacle {e(s['sources']['pinnacle'])}, Polymarket {e(s['sources']['polymarket'])}, Valve {e(s['sources']['vrs'])}, HLTV {e(s['sources']['hltv'])}. Generated {e(utc_label(s['generated_utc']))}. <a href="method.html">Method, sources &amp; read times</a>.</p>"""
    page("index.html", "Executive summary", body, board, script=LOCK_SCRIPT)


def landing_json(board: dict) -> None:
    s = board["summary"]
    open_rows = sorted([r for r in board["rows"] if r["status"] == "open"], key=lambda r: r.get("lock_utc") or "")
    write_json(DATA / "landing.json", {
        "generated_utc": s["generated_utc"], "reference_utc": s["reference_utc"], "open": s["open"],
        "open_with_pick": s["open_with_pick"], "open_rung": s["open_rung"], "open_unresolved": s["open_unresolved"],
        "classes": s["leaderboard_classes"], "hotspawn_complete": s["hotspawn_complete"],
        "next": [{"id": r["match_id"], "a": r["team_a"], "b": r["team_b"], "tier": r.get("tier"), "lock": r.get("lock_utc"),
                  "pick": r.get("pick"), "p": r.get("pick_p"), "pa": r.get("p_a"), "pb": r.get("p_b"), "basis": r.get("rung"),
                  "play": (r.get("strategy") or {}).get("leaderboard_pick"), "class": (r.get("strategy") or {}).get("class")}
                 for r in open_rows[:8]],
    })


def main() -> int:
    board = read_json(DATA / "board.json")
    if not board:
        print("build: no data/board.json")
        return 1
    index_page(board)
    picks_page(board)
    strategy_page(board)
    twc_page(board)
    unresolved_page(board)
    flagged_page(board)
    all_page(board)
    method_page(board)
    landing_json(board)
    print("build: 8 pages written")
    return 0


if __name__ == "__main__":
    from common import run_main
    run_main(main)
