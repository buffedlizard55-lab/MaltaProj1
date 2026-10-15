#!/usr/bin/env python3
"""Render the mobile-first pages of the every-match board from data/board.json (session arena/22be6967).

Pages: index.html (executive summary incl. unresolved & limitations), picks.html (every open match),
strategy.html (leaderboard plays + day-1 review + grading), unresolved.html, flagged.html (Flagged for
Review), all.html (every captured fixture), method.html (methodology, sources, read times).
No external requests; the only script is inline and optional (local lock countdowns, filters).
"""
from __future__ import annotations

import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, REPO_URL, RESEARCH, ROOT, SESSION, parse_iso, read_json, utc_label, write_json  # noqa: E402

NAV = [("index.html", "Summary"), ("picks.html", "All picks"), ("strategy.html", "Leaderboard plan"),
       ("unresolved.html", "Unresolved"), ("flagged.html", "Flagged"), ("method.html", "Method")]
CLASS_ORDER = ["VALUE", "CONTRARIAN", "SITUATIONAL", "LONG SHOT", "CHALK", "NO CROWD DATA"]
CLASS_TEXT = {
    "VALUE": "Play the favourite: it is the likely winner AND most players are on the other side.",
    "CONTRARIAN": "Play the underdog: every estimate gives it a real chance, well above its crowd share.",
    "SITUATIONAL": "Play the underdog: real chance, heavily faded, and a verified roster/stand-in/late-notice factor hits the favourite.",
    "LONG SHOT": "Keep the favourite. The underdog is an optional punt only if you are far behind.",
    "CHALK": "Keep the favourite. Fading it costs points without enough upside.",
    "NO CROWD DATA": "Hotspawn published no crowd share; keep the pick.",
}
RUNG_TEXT = {"A": "Pinnacle odds (margin removed)", "B": "Polymarket price (prediction market)",
             "C": "Our own line (official Valve points)", "D": "Unresolved"}


def e(x) -> str:
    return escape("" if x is None else str(x), quote=True)


def pc(x, d=0) -> str:
    return "—" if x is None else f"{x * 100:.{d}f}%"


def link(url, text=None) -> str:
    if not url:
        return e(text or "")
    return f'<a href="{e(url)}">{e(text or url)}</a>'


def cls_tag(c: str | None) -> str:
    if not c:
        return ""
    return f'<span class="tag c-{e(c.replace(" ", "-"))}">{e(c)}</span>'


def page(name: str, title: str, body: str, board: dict, extra_head: str = "", script: str = "") -> None:
    nav = "".join(f'<a href="{h}"{" aria-current=page" if h == name else ""}>{e(t)}</a>' for h, t in NAV)
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d1218">
<meta name="description" content="Hotspawn Counter-Strike 2 pick'em: a pick and both teams' win probabilities for every open match, with sources.">
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
<p>Independent research, not affiliated with Hotspawn; not betting advice. Probabilities come from outside prices (Pinnacle, Polymarket) or our own line from Valve's official standings — never from Hotspawn's crowd percentages, which appear only as "ownership" for the leaderboard plan.</p>
<p>Built by session <code>{e(SESSION)}</code> · <a href="data/picks.csv">picks.csv</a> · <a href="data/all_fixtures.csv">all_fixtures.csv</a> · <a href="data/flags.csv">flags.csv</a> · <a href="data/board.json">board.json</a> · <a href="{REPO_URL}/blob/main/.github/workflows/hotspawn-22be6967.yml">refresh workflow</a> · <a href="{REPO_URL}">source</a></p>
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
            f'HLTV ranking {e(m["hltv"].get("status"))}. Auto-refresh every 3 h.{warn} '
            f'<a href="https://play.hotspawn.com/lobby">Open the live Hotspawn lobby</a></p>')


def team_bar(name, p, fav) -> str:
    w = 0 if p is None else max(2, round(p * 100))
    return (f'<div class="bar{" fav" if fav else ""}"><span class="name">{e(name)}</span>'
            f'<span class="track"><i style="width:{w}%"></i></span><span class="v">{pc(p)}</span></div>')


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
    va, vb = r.get("vrs_a"), r.get("vrs_b")
    if r.get("own_p_a") is not None:
        items.append(f"Our line: {e(r['team_a'])} {pc(r['own_p_a'])} / {e(r['team_b'])} {pc(r['own_p_b'])} from Valve points {va['points']} (#{va['rank']}) vs {vb['points']} (#{vb['rank']}), "
                     f"slope k={board['meta']['k']} ({e(board['meta']['k_label'])}). {link(board['meta']['vrs'].get('url'), 'Valve standings')}")
    else:
        missing = [n for n, v in ((r["team_a"], va), (r["team_b"], vb)) if not v]
        items.append(f"Our line: not possible — not in Valve's standings: {e(', '.join(missing))}.")
    if r.get("hltv_rank_a") or r.get("hltv_rank_b"):
        items.append(f"HLTV world ranking: {e(r['team_a'])} {('#' + str(r['hltv_rank_a'])) if r.get('hltv_rank_a') else 'unranked'} · "
                     f"{e(r['team_b'])} {('#' + str(r['hltv_rank_b'])) if r.get('hltv_rank_b') else 'unranked'}. {link(board['meta']['hltv'].get('url'), 'HLTV ranking')}")
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
    pick_line = (f'<div class="pick">Pick: <strong>{e(r["pick"])}</strong><span class="pp">{pc(r.get("pick_p"))}</span></div>'
                 if r.get("pick") else '<div class="pick"><strong style="color:var(--red)">No pick — unresolved</strong></div>')
    fav_a = r.get("pick") == r["team_a"]
    bars = team_bar(r["team_a"], r.get("p_a"), fav_a and r.get("pick")) + team_bar(r["team_b"], r.get("p_b"), (not fav_a) and r.get("pick"))
    basis = RUNG_TEXT.get(r.get("rung"), r.get("basis"))
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
<p class="lead">{s['open']} matches can still be picked. Each card shows <strong>the pick and both teams' win probabilities</strong> first, then the basis, the leaderboard play, and the sources. Cards turn grey when their lock time passes on your clock.</p>
<div class="filters" role="group" aria-label="Filter"><button type="button" data-f="all" aria-pressed="true">All ({len(rows)})</button><button type="button" data-f="S" aria-pressed="false">S-tier only</button><button type="button" data-f="plays" aria-pressed="false">Leaderboard plays only</button></div>"""]
    if not rows:
        body.append('<p class="note red">No open CS2 fixtures in this snapshot. Check the <a href="https://play.hotspawn.com/lobby">live lobby</a>.</p>')
    for day, items in by_day.items():
        body.append(f'<h2 class="day">{e(day)}</h2>')
        body.extend(card(r, board) for r in items)
    body.append('<p class="small">Unresolved or model-only picks and their limitations: <a href="unresolved.html">Unresolved &amp; limitations</a>. Everything flagged: <a href="flagged.html">Flagged for Review</a>.</p>')
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


def strategy_page(board: dict) -> None:
    rows = [r for r in board["rows"] if r["status"] == "open" and r.get("strategy")]
    rows.sort(key=lambda r: (CLASS_ORDER.index(r["strategy"]["class"]) if r["strategy"]["class"] in CLASS_ORDER else 9, r.get("lock_utc") or ""))
    week = board["meta"]["hotspawn"].get("week") or {}
    prizes = ", ".join(f"{p.get('rank')}: {p.get('title')}" for p in week.get("prizes", []))
    d1 = board["day1"]
    d1rows = []
    for x in d1["matches"]:
        st = x.get("strategy") or {}
        d1rows.append(f"<tr><td><a href=\"{e(x['hltv'])}\">{e(x['team_a'])} vs {e(x['team_b'])}</a></td><td>{e(x['team_a'])} {pc(x['p_a'])} / {pc(x['p_b'])}<br><span class=small>Pinnacle {x['odds_a']:.3f} / {x['odds_b']:.3f}</span></td>"
                      f"<td>{pc(x.get('own_p_a'))} / {pc(x.get('own_p_b'))}</td><td>{e(x['crowd_a'])}% / {e(x['crowd_b'])}%</td><td>{e(x['pick'])}</td>"
                      f"<td>{cls_tag(st.get('class'))} {e(st.get('leaderboard_pick'))}</td><td><b>{e(x['winner'])}</b> {e(x['score'])}<br><span class=small>{e(x['maps'])}</span></td>"
                      f"<td class=\"{'ok' if x['pick_correct'] else 'miss'}\">{'✓' if x['pick_correct'] else '✗'}</td><td class=\"{'ok' if x.get('leaderboard_correct') else 'miss'}\">{'✓' if x.get('leaderboard_correct') else '✗'}</td></tr>")
    info = d1.get("info", {})
    graded = board.get("graded", [])
    gr = [g for g in graded if g.get("result")]
    grows = "".join(f"<tr><td>{e(g['team_a'])} vs {e(g['team_b'])}</td><td>{e(g.get('pick'))}</td><td>{e(g.get('class'))} → {e(g.get('leaderboard_pick'))}</td><td>{e(g['result']['winner'])}<br><span class=small>{e(g['result'].get('kind'))}</span></td>"
                    f"<td class=\"{'ok' if g.get('pick_correct') else 'miss'}\">{'✓' if g.get('pick_correct') else '✗'}</td><td class=\"{'ok' if g.get('leaderboard_correct') else 'miss'}\">{'✓' if g.get('leaderboard_correct') else '✗'}</td></tr>" for g in gr)
    pending = [g for g in graded if not g.get("result")]
    lessons = "".join(f"<li>{e(t)}</li>" for t in d1.get("info", {}).get("lessons", []) or read_json(RESEARCH / "day1_twc2026.json", {}).get("lessons", []))
    body = f"""<h1>Leaderboard plan: contrarian, not reckless</h1>
<p class="lead">Every Hotspawn player who picks the same side scores the same points, so you only climb when you are right where the field is wrong. The plan below fades the crowd <strong>only</strong> when the underdog's real chance is high — judged by outside prices and our own line together, never by the crowd itself.</p>
<div class="note green"><strong>How to use it:</strong> take every <span class="tag c-VALUE">VALUE</span> play (likely winner that most players are against). Add <span class="tag c-CONTRARIAN">CONTRARIAN</span> plays when you need to gain ground. Use <span class="tag c-SITUATIONAL">SITUATIONAL</span> plays when you are chasing; they rest on verified roster changes, stand-ins or late replacements. Treat <span class="tag c-LONG-SHOT">LONG SHOT</span> underdogs as an occasional punt only when far behind with few matches left. S-tier matches are worth {e(next((r.get('points') for r in board['rows'] if r.get('tier') == 'S'), 7))} points versus 2 for C-tier, so the S-tier calls matter most.</div>
<p class="small">This week: {e(week.get('weekStartUtc'))} → {e(week.get('weekEndUtc'))} (Hotspawn payload). Prizes: {e(prizes) or 'not published in payload'}. Hotspawn requires at least 10 picks to qualify (lobby text).</p>
<h2>Plays for the open slate ({len(rows)})</h2>
{plays_table(rows)}
<p class="small">EV cost = expected points given up versus simply taking the favourite (points × gap in win chance). Underdog chance = consensus of the market and our own line (our line is dropped when Valve's roster is out of date). Crowd = Hotspawn's pick share, used here only to measure how contrarian a pick is.</p>
<h2>The rule (v2)</h2>
<ul>
<li><span class="tag c-VALUE">VALUE</span> crowd majority sits on the consensus underdog → play the favourite.</li>
<li><span class="tag c-CONTRARIAN">CONTRARIAN</span> underdog consensus ≥ 38%, every estimate ≥ 30%, and crowd share at least 10 points below its chance → play the underdog.</li>
<li><span class="tag c-SITUATIONAL">SITUATIONAL</span> underdog consensus ≥ 30%, every estimate ≥ 25%, crowd share ≤ half its chance, a strong/moderate verified factor against the favourite and none against the underdog → play the underdog.</li>
<li><span class="tag c-LONG-SHOT">LONG SHOT</span> underdog ≥ 20% with ≤ 10% of players → keep the favourite (optional punt).</li>
<li><span class="tag c-CHALK">CHALK</span> everything else → keep the favourite.</li>
</ul>
<p class="note">Honesty note: rule v1 used the market alone and let weak factors (for example "busy schedule") count. Graded on TWC day 1 it would have gone 1/4, so it was replaced by v2 before publication. v2 goes 4/4 on the same four matches, but that is in-sample with n = 4 and proves nothing; the live grading below is the real test.</p>
<h2>Day 1 review — Thunderpick World Championship 2026 (14 Oct)</h2>
<p>{e(info.get('event', {}).get('format', ''))} {link(info.get('event', {}).get('hltv'), 'HLTV event')} · {link(info.get('event', {}).get('results'), 'HLTV results')}</p>
<div class="tablewrap"><table><thead><tr><th>Match</th><th>Market (pre-match)</th><th>Our line</th><th>Crowd</th><th>Market pick</th><th>Plan (v2)</th><th>Result (HLTV)</th><th>Pick</th><th>Plan</th></tr></thead><tbody>{''.join(d1rows)}</tbody></table></div>
<p class="small">Prices: {link(info.get('price_source', {}).get('url'), info.get('price_source', {}).get('label'))} (read {e(info.get('price_source', {}).get('read_utc'))}). Crowd: {link(info.get('crowd_source', {}).get('url'), info.get('crowd_source', {}).get('label'))} — {e(info.get('crowd_source', {}).get('note'))} Board pick before lock: {link(info.get('pick_source', {}).get('url'), info.get('pick_source', {}).get('label'))}.</p>
<h3>What day 1 taught us</h3><ul>{lessons}</ul>
<h3>The upset: 9z 2-0 Aurora</h3>
<p>Aurora rebuilt in July 2026 — Jimpphat joined on 3 Jul and kyxsan became in-game leader on 8 Jul (coach ash). That is about three months before TWC, and the new five had just finished 3rd at ESL Pro League S24, beating 9z 2-0 there on 3 Oct. In Malta 9z won Inferno 13-11 and Nuke 13-1 (luchov 1.61). Pinnacle had 9z at 27%, our official-points line at 39%, and only 5% of Hotspawn players picked 9z. {link('https://www.hltv.org/team/11861/aurora', 'HLTV: Aurora roster & transfers')} · {link('https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026', 'HLTV match report')}</p>
<h2>Grading since launch</h2>
<p>Every pick is frozen at its lock time and graded once a result exists (verified HLTV result first; otherwise the Polymarket resolution, which names HLTV as its source, marked provisional).</p>
{('<div class="tablewrap"><table><thead><tr><th>Match</th><th>Pick</th><th>Plan</th><th>Winner</th><th>Pick</th><th>Plan</th></tr></thead><tbody>' + grows + '</tbody></table></div>') if gr else '<p class="small">No graded fixtures yet.</p>'}
<p class="small">{len(pending)} frozen pick(s) awaiting a result.</p>
"""
    page("strategy.html", "Leaderboard plan", body, board)


def unresolved_section(board: dict, full: bool) -> str:
    open_rows = [r for r in board["rows"] if r["status"] == "open"]
    d = [r for r in open_rows if r.get("rung") == "D"]
    c = [r for r in open_rows if r.get("rung") == "C"]
    issues = [r for r in open_rows if r.get("rung") in ("A", "B") and set(r.get("flags", [])) & {"KICKOFF_GAP", "MODEL_MARKET_SPLIT", "BOOK_PM_SPLIT", "VRS_ROSTER_OUTDATED", "FORMAT_UNKNOWN", "STALE_PRICE"}]
    out = [f"<p><strong>{len(d)}</strong> open match(es) have no pick at all; <strong>{len(c)}</strong> rely on our own line only (no outside price yet); "
           f"<strong>{len(issues)}</strong> priced matches carry a data-quality flag.</p>"]
    if d:
        out.append("<h3>No pick possible</h3><ul>" + "".join(
            f"<li><a href=\"picks.html#m{e(r['match_id'])}\">{e(r['team_a'])} vs {e(r['team_b'])}</a> — {e(utc_label(r.get('lock_utc')))}: no Pinnacle or Polymarket price, and "
            f"{e(', '.join(n for n, v in ((r['team_a'], r.get('vrs_a')), (r['team_b'], r.get('vrs_b'))) if not v))} missing from Valve's standings. Research trail: {link(r.get('hltv_url'), 'HLTV')} · "
            f"<a href=\"https://www.hltv.org/search?query={e(r['team_a'])}\">HLTV search {e(r['team_a'])}</a> · <a href=\"https://www.hltv.org/search?query={e(r['team_b'])}\">HLTV search {e(r['team_b'])}</a></li>" for r in d) + "</ul>")
    if c:
        rows = []
        for r in c:
            lim = ["no Pinnacle line at read time", "no Polymarket market"]
            if "VRS_ROSTER_OUTDATED" in r.get("flags", []):
                lim.append("Valve's five differs from the lineup now playing")
            if not r.get("format"):
                lim.append("series length not stated")
            elif r.get("format") == "BO1":
                lim.append("Bo1: more upsets than the rating gap suggests")
            hl = f"HLTV #{r.get('hltv_rank_a') or '–'} vs #{r.get('hltv_rank_b') or '–'}"
            rows.append(f"<tr><td><a href=\"picks.html#m{e(r['match_id'])}\">{e(r['team_a'])} vs {e(r['team_b'])}</a><br><span class=small>{e(utc_label(r.get('lock_utc')))}</span></td>"
                        f"<td>{e(r.get('pick'))} {pc(r.get('pick_p'))}</td><td>1 HLTV: {link(r.get('hltv_url'), 'page')} ({e(hl)})<br>2 Esportsbook: Pinnacle — not listed<br>3 Betting lines: Polymarket — not listed</td>"
                        f"<td>{e('; '.join(lim))}</td></tr>")
        out.append("<h3>Picks from our own line only</h3><div class=\"tablewrap\"><table><thead><tr><th>Match</th><th>Pick</th><th>Research ladder (HLTV → esportsbooks → lines)</th><th>Limitations</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>")
    if full and issues:
        out.append("<h3>Priced matches with data-quality flags</h3><ul>" + "".join(
            f"<li><a href=\"picks.html#m{e(r['match_id'])}\">{e(r['team_a'])} vs {e(r['team_b'])}</a>: " + ", ".join(f'<span class="flag">{e(f)}</span>' for f in r["flags"] if f != "ALIAS") + "</li>" for r in issues) + "</ul>")
    out.append("""<h3>Limitations that apply to every pick</h3><ul>
<li>Snapshots, not live odds: prices are read every 3 hours; a line can move or be pulled before lock. Every price shows its read time.</li>
<li>Pinnacle usually posts low-tier lines about a day ahead, so next-day C-tier matches often start on our own line and switch to a market price on a later refresh.</li>
<li>Our own line uses Valve's official points (published monthly; current file named in the snapshot bar) on a curve fitted to Valve's own results; it knows nothing about stand-ins or brand-new rosters — those are shown as factors.</li>
<li>HLTV blocks most automated reads, so HLTV facts (formats, rosters, stand-ins) come from this session's manual research with links; new fixtures get HLTV links but no new notes until researched.</li>
<li>Hotspawn's crowd share is shown as ownership only and changes until lock.</li>
</ul>""")
    return "\n".join(out)


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
<p class="lead">Everything that is unverified, disputed or irregular is listed here with its evidence. Flags never block publication; they tell you where to look before trusting a number.</p>
<h2>Irregularities found in research and review</h2>
<div class="tablewrap"><table><thead><tr><th>ID</th><th>Status</th><th>Finding</th><th>Evidence</th></tr></thead><tbody>{irows}</tbody></table></div>
<p class="small">The line-by-line repository review with links for manual checking is in <a href="{REPO_URL}/blob/main/reviews/22be6967-verification.md">reviews/22be6967-verification.md</a>.</p>
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
<li><b>Polymarket</b> match-winner markets (tag "counter strike 2"), mid prices normalised to 100%. A prediction market, labelled as such.</li>
<li><b>Our own line</b>: P(A) = 1 / (1 + 10^(−k·ΔPoints/400)) with Valve's official points ({link(m['vrs'].get('url'), 'standings ' + str(m['vrs'].get('as_of')))}). k = {e(m['k'])} ({e(m['k_label'])}); trained on {e(cal.get('n_train'))} Valve-rated matches, held out on {e(cal.get('n_test'))} (window {e(cal.get('last_window'))}): log-loss {e(hold.get('log_loss_fitted'))} vs {e(hold.get('log_loss_valve_raw'))} for Valve's raw curve; Brier {e(hold.get('brier_fitted'))} vs {e(hold.get('brier_valve_raw'))}.</li>
<li><b>Unresolved</b>: blank pick, flagged, listed on the Unresolved page with the research trail.</li></ol>
<p>Joins require both teams to match after verified aliases ({link(REPO_URL + '/blob/main/hotspawn/research/aliases.json', 'aliases.json')}) and a kickoff within 6 h; any gap is flagged. HLTV ranks are shown as a cross-check ({link(m['hltv'].get('url'), 'HLTV ranking')}, status {e(m['hltv'].get('status'))}).</p>
<h2>3. Leaderboard plan</h2><p>See <a href="strategy.html">Leaderboard plan</a>; thresholds live in {link(REPO_URL + '/blob/main/hotspawn/model.py', 'model.py')}. Situational factors come from {link(REPO_URL + '/blob/main/hotspawn/research/notes.json', 'research/notes.json')} (HLTV links, read times, strength) plus an automatic "new five" check on Valve's per-team match tables.</p>
<h2>4. Automation</h2><p>{link(REPO_URL + '/blob/main/.github/workflows/hotspawn-22be6967.yml', 'GitHub Actions workflow')} runs every 3 hours (inside the 4–8 h requirement even if a scheduled run is dropped): collect → calibrate → model → build → tests; pages are committed only when the tests pass, otherwise the last good pages stay up and the failure is visible in the run log.</p>
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
                f"Pick <b>{e(r.get('pick') or '—')}</b> {pc(r.get('pick_p'))} ({e(r['team_a'])} {pc(r.get('p_a'))} / {e(r['team_b'])} {pc(r.get('p_b'))}) · {cls_tag(st.get('class'))} play <b>{e(st.get('leaderboard_pick'))}</b></li>")
    d1 = board["day1"]["matches"]
    body = f"""<h1>Hotspawn CS2 — executive summary</h1>
<p class="lead">A pick and both teams' win probabilities for <strong>every</strong> open Counter-Strike 2 match on Hotspawn, plus a leaderboard plan that fades the crowd only when the numbers support it.</p>
<div class="btns">
<a class="btn primary" href="picks.html"><strong>All picks ({s['open']} open) →</strong><span>One card per match: pick, both probabilities, sources.</span></a>
<a class="btn" href="strategy.html"><strong>Leaderboard plan</strong><span>{s['leaderboard_classes'].get('VALUE', 0)} value · {s['leaderboard_classes'].get('CONTRARIAN', 0)} contrarian · {s['leaderboard_classes'].get('SITUATIONAL', 0)} situational plays; day-1 review.</span></a>
<a class="btn" href="unresolved.html"><strong>Unresolved &amp; limitations</strong><span>{s['open_unresolved']} without a pick · {s['open_rung'].get('C', 0)} on our own line only.</span></a>
<a class="btn" href="flagged.html"><strong>Flagged for Review</strong><span>Irregularities and per-match flags with evidence.</span></a>
</div>
<div class="stats" aria-label="Coverage">
<div><b>{s['open']}</b><span>open matches</span></div><div><b>{s['open_with_pick']}</b><span>with a pick</span></div>
<div><b>{s['open_rung'].get('A', 0) + s['open_rung'].get('B', 0)}</b><span>priced by a market</span></div><div><b>{s['open_rung'].get('C', 0)}</b><span>our own line only</span></div>
</div>
<h2>Next to lock</h2><ul class="plain">{''.join(li(r) for r in nxt) or '<li>No open fixtures in this snapshot.</li>'}</ul>
<h2>Leaderboard plays right now</h2><ul class="plain">{''.join(li(r) for r in plays) or '<li>No value/contrarian/situational plays — take the picks.</li>'}</ul>
<p><a href="strategy.html">Why these plays, and the rule behind them →</a></p>
<h2>Day 1 in one line</h2>
<p>TWC 2026 day 1: all four series ended 2-0; favourites won three. The upset was <b>9z 2-0 Aurora</b> (market 27%, our line 39%, picked by 5% of players). Market picks went {s['day1_review']['picks_correct']}/{s['day1_review']['matches']}. <a href="strategy.html">Full review →</a></p>
<h2 id="unresolved">Unresolved picks &amp; limitations</h2>
{unresolved_section(board, False)}
<h2>Coverage &amp; freshness</h2>
<p class="small">{s['fixtures']} fixtures in Hotspawn's payload: {s['open']} open, {s['locked_recent']} recently locked, {s['stale_listings']} stale listings (<a href="all.html">full inventory</a>). Sources: Pinnacle {e(s['sources']['pinnacle'])}, Polymarket {e(s['sources']['polymarket'])}, Valve {e(s['sources']['vrs'])}, HLTV {e(s['sources']['hltv'])}. Generated {e(utc_label(s['generated_utc']))}. <a href="method.html">Method, sources &amp; read times</a>.</p>"""
    page("index.html", "Executive summary", body, board)


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
    unresolved_page(board)
    flagged_page(board)
    all_page(board)
    method_page(board)
    landing_json(board)
    print("build: 7 pages written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
