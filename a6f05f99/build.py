#!/usr/bin/env python3
"""Build every page of the a6f05f99 board from ``data/`` (session ``arena/a6f05f99``).

Mobile first: one column by default, cards instead of wide tables, 44 px tap targets, and the
pick plus both probabilities readable without horizontal scrolling on a 390 px phone.  The
executive summary (``index.html``) exists for one reason - to get you to the picks in one tap.
"""
from __future__ import annotations

import html
import json
import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA, RESEARCH, complementary, hours_between, parse_iso, read_json,  # noqa: E402
                    write_csv, write_json)
import model  # noqa: E402

HERE = Path(__file__).resolve().parent
LOBBY = "https://play.hotspawn.com/lobby"
REPO = "https://github.com/buffedlizard55-lab/MaltaProj1"
SESSION = "arena/a6f05f99"

CSS = """
:root{color-scheme:dark;--bg:#0c1116;--panel:#151d26;--panel2:#1b2632;--line:#26333f;
--text:#e8eef4;--muted:#9fb0c0;--accent:#b7a6ff;--green:#57d99a;--amber:#ffc46b;--red:#ff8f8f}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
font-size:16px;line-height:1.5;-webkit-text-size-adjust:100%}
a{color:var(--accent)}
.wrap{max-width:1080px;margin:0 auto;padding:16px 14px 64px}
header.top{border-bottom:1px solid var(--line);background:var(--panel);position:sticky;top:0;z-index:5}
header.top .wrap{padding-top:10px;padding-bottom:10px}
.brand{font-weight:800;font-size:1.05rem;color:var(--text);text-decoration:none;display:inline-block;min-height:44px;line-height:44px}
nav.topnav{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
nav.topnav a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border-radius:8px;
background:var(--panel2);border:1px solid var(--line);color:var(--text);text-decoration:none;font-size:.92rem}
nav.topnav a[aria-current="page"]{background:var(--accent);border-color:var(--accent);color:#17132b;font-weight:700}
.skip{position:absolute;left:-9999px}
.skip:focus{position:static;display:inline-block;margin:8px}
h1{font-size:1.5rem;line-height:1.25;margin:14px 0 8px}
h2{font-size:1.15rem;margin:26px 0 10px}
h3{font-size:1rem;margin:18px 0 8px}
p,li{color:var(--text)}
.muted{color:var(--muted)}
.eyebrow{text-transform:uppercase;letter-spacing:.08em;font-size:.72rem;color:var(--muted);margin:0}
.snap{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:12px 0;font-size:.9rem}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0}
.stats>div{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.stats b{display:block;font-size:1.6rem;line-height:1.1}
.stats span{display:block;color:var(--muted);font-size:.8rem;margin-top:2px}
.jump{display:grid;gap:10px;margin:14px 0}
.jump a{display:block;padding:14px;border-radius:12px;border:1px solid var(--line);background:var(--panel);
text-decoration:none;min-height:44px}
.jump a.primary{background:var(--accent);border-color:var(--accent)}
.jump a.primary strong,.jump a.primary span{color:#17132b}
.jump strong{display:block;font-size:1.02rem;color:var(--text)}
.jump span{display:block;color:var(--muted);font-size:.85rem;margin-top:4px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin:12px 0}
.card.hot{border-left:4px solid var(--accent)}
.pickline{display:flex;align-items:baseline;justify-content:space-between;gap:10px;flex-wrap:wrap}
.pick{font-size:1.15rem;font-weight:800}
.probs{display:flex;gap:8px;margin:10px 0;flex-wrap:wrap}
.prob{flex:1 1 130px;min-width:130px;background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.prob b{display:block;font-size:1.35rem}
.prob span{display:block;color:var(--muted);font-size:.78rem;overflow-wrap:anywhere}
.bar{height:8px;border-radius:5px;background:var(--panel2);overflow:hidden;margin:6px 0 10px;display:flex}
.bar i{display:block;height:100%}
.bar i.a{background:var(--accent)}
.bar i.b{background:#4d6a86}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
.tag{display:inline-block;padding:2px 8px;border-radius:999px;font-size:.72rem;font-weight:700;
border:1px solid var(--line);background:var(--panel2);color:var(--muted);white-space:nowrap}
.tag.VALUE{color:#8ef0b8;border-color:#8ef0b8}
.tag.CONTRARIAN{color:var(--accent);border-color:var(--accent)}
.tag.SITUATIONAL{color:var(--amber);border-color:var(--amber)}
.tag.LONG{color:#ff8f8f;border-color:#ff8f8f}
.tag.CHALK{color:var(--muted)}
.tag.UNRESOLVED{color:var(--red);border-color:var(--red)}
ul.clean{list-style:none;padding:0;margin:8px 0}
ul.clean li{padding:8px 0;border-bottom:1px solid var(--line)}
ul.tight li{padding:4px 0;border:0}
.src{font-size:.78rem;color:var(--muted);overflow-wrap:anywhere}
.src a{color:#8fb8e0}
footer{border-top:1px solid var(--line);margin-top:32px;padding-top:14px;color:var(--muted);font-size:.82rem}
.notice{border-left:4px solid var(--amber);background:var(--panel);padding:10px 12px;border-radius:6px;margin:12px 0}
.notice.red{border-left-color:var(--red)}
.notice.green{border-left-color:var(--green)}
details{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px;margin:12px 0}
summary{min-height:44px;cursor:pointer;font-weight:700}
@media(min-width:760px){
 .stats{grid-template-columns:repeat(4,minmax(0,1fr))}
 .jump{grid-template-columns:repeat(2,minmax(0,1fr))}
 h1{font-size:1.9rem}
 .grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
}
"""

def a_href(url, label):
    return '<a href="' + esc(url) + '">' + esc(label) + '</a>'


def est_item(e, link_label="source"):
    pa_e, pb_e = complementary(e.get("p_a"))
    return ('<li>' + esc(e.get("short")) + ': ' + esc(pa_e) + '% / ' + esc(pb_e) + '% &mdash; '
            + a_href(e.get("url"), link_label)
            + ' <span class="muted">(' + esc(e.get("detail")) + ')</span></li>')

NAV = [("index.html", "Summary"), ("picks.html", "All picks"), ("twc.html", "Thunderpick day 3"),
       ("unresolved.html", "Unresolved"), ("method.html", "Method"), ("flagged.html", "Flagged")]


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def page(title: str, active: str, body: str, description: str) -> str:
    links = []
    for href, label in NAV:
        current = ' aria-current="page"' if href == active else ""
        links.append(f'<a href="{href}"{current}>{esc(label)}</a>')
    nav = "".join(links)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0c1116">
<meta name="description" content="{esc(description)}">
<title>{esc(title)}</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top"><div class="wrap">
<a class="brand" href="index.html">Hotspawn CS2 &middot; every match, one pick</a>
<nav class="topnav">{nav}</nav>
</div></header>
<main class="wrap" id="content">
{body}
</main>
<footer><div class="wrap">
<p>Session {SESSION} &middot; built by an unattended collector that reads Hotspawn's public pages,
Pinnacle, bo3.gg, Polymarket, Valve's Regional Standings and HLTV. Hotspawn's own crowd percentages
are never used as a probability &mdash; only as ownership, to measure how contrarian a play is.</p>
<p><a href="{REPO}">Repository</a> &middot; <a href="{LOBBY}">Hotspawn lobby</a></p>
</div></footer>
</body>
</html>
"""


def fmt_lock(lock: str) -> str:
    dt = parse_iso(lock)
    if not dt:
        return esc(lock or "")
    return dt.strftime("%a %d %b %H:%M") + " UTC"


def prob_block(a: str, b: str, pa, pb, name_a: str, name_b: str) -> str:
    try:
        f = float(pa) / 100.0
    except (TypeError, ValueError):
        f = 0.5
    return f"""<div class="probs">
<div class="prob"><b>{esc(pa)}%</b><span>{esc(name_a)}</span></div>
<div class="prob"><b>{esc(pb)}%</b><span>{esc(name_b)}</span></div>
</div>
<div class="bar"><i class="a" style="width:{f * 100:.1f}%"></i><i class="b" style="width:{100 - f * 100:.1f}%"></i></div>"""


def class_tag(klass: str) -> str:
    key = (klass or "").replace(" ", "-")
    short = {"LONG-SHOT": "LONG SHOT", "NO-CROWD-DATA": "NO CROWD DATA"}.get(key, klass or "")
    return f'<span class="tag {esc(key)}">{esc(short)}</span>'


# --------------------------------------------------------------------------------- index
def build_index(board: dict) -> str:
    cov = board["coverage"]
    rows = board["rows"]
    open_rows = [r for r in rows if r["status"] == "open"]
    unresolved = [r for r in open_rows if not r.get("estimates")]
    single = [r for r in open_rows if len(r.get("estimates") or []) == 1]
    read = cov.get("generated_utc") or ""
    twc = board["twc"]
    day3 = next((m for d in twc.get("days", []) for m in d.get("matches", [])
                 if m.get("hotspawn_id")), None)
    day3_row = next((r for r in open_rows if r["match_id"] == (day3 or {}).get("hotspawn_id")), None)

    head = f"""
<p class="eyebrow">Executive summary</p>
<h1>Every Hotspawn CS2 match, with a pick and both teams' chances</h1>
<p class="muted">One page to start from. Everything below is generated from outside prices and
official ratings &mdash; never from Hotspawn's own crowd percentages.</p>
<div class="snap"><strong>Snapshot:</strong> Hotspawn read {esc(read)}
&nbsp;&middot;&nbsp; {cov['fixtures']} CS2 listings &middot;
<strong>{cov['open']} open</strong> &middot; <strong>{cov['open_with_pick']} with a pick</strong>
&middot; <strong>{cov['open_unresolved']} unresolved</strong>.
Next lock {esc(fmt_lock(cov.get('next_lock_utc') or ''))}. Auto-refreshed every four hours.</p>
"""

    jump = """
<h2>Where to find the picks</h2>
<div class="jump">
<a class="primary" href="picks.html"><strong>All picks &mdash; every open match</strong>
<span>Pick, both probabilities, how we got the number, and the source links. One card per match, readable on a phone.</span></a>
<a href="twc.html"><strong>Thunderpick day 3 &mdash; the 7-point call</strong>
<span>Day 1 and day 2 graded against what we published before lock, and what it says about Aurora v 9z.</span></a>
<a href="unresolved.html"><strong>Unresolved picks &amp; limitations</strong>
<span>Every fixture we cannot price, exactly why, and which sources were tried.</span></a>
<a href="method.html"><strong>Method &amp; sources</strong>
<span>The ladder, the own line, the leaderboard rule, and every source with its read time.</span></a>
</div>
"""

    multi = (cov["open_by_estimates"].get("2", 0) + cov["open_by_estimates"].get("3", 0)
             + cov["open_by_estimates"].get("4", 0))
    stats = f"""
<h2>Coverage at a glance</h2>
<div class="stats">
<div><b>{cov['open_with_pick']}/{cov['open']}</b><span>open fixtures with a pick</span></div>
<div><b>{cov['open_unresolved']}</b><span>unresolved (blank on purpose)</span></div>
<div><b>{multi}</b><span>backed by 2+ independent sources</span></div>
<div><b>{len(single)}</b><span>rest on a single source</span></div>
</div>
"""

    d3 = ""
    if day3_row:
        pa, pb = complementary(day3_row.get("consensus_a"))
        st = day3_row.get("strategy") or {}
        ests = "".join(est_item(e) for e in day3_row.get("estimates") or [])
        d3 = f"""
<div class="card hot">
<p class="eyebrow">Today's big call &middot; Thunderpick World Championship 2026 &middot; {esc(day3_row.get('points'))} points</p>
<h2 style="margin:6px 0 2px">{esc(day3_row['team_a'])} vs {esc(day3_row['team_b'])}</h2>
<p class="muted">Group A decider &middot; Bo3 LAN &middot; locks {esc(fmt_lock(day3_row.get('lock_utc')))}"""
        hltv3 = (day3 or {}).get("hltv")
        if hltv3:
            d3 += ' &middot; <a href="' + esc(hltv3) + '">HLTV match page</a>'
        d3 += f"""</p>
{prob_block(pa, pb, pa, pb, day3_row['team_a'], day3_row['team_b'])}
<div class="pickline"><span class="pick">Pick: {esc(day3_row.get('pick'))}</span>
{class_tag(st.get('class', ''))}</div>
<p><strong>Leaderboard play: {esc(st.get('play') or day3_row.get('pick'))}</strong> &mdash; {esc(st.get('reason', ''))}</p>
<p class="muted">Crowd: {esc(day3_row.get('crowd_a'))}% on {esc(day3_row['team_a'])},
{esc(day3_row.get('crowd_b'))}% on {esc(day3_row['team_b'])} (ownership only, never a probability).</p>
<ul class="clean tight">{ests}</ul>
<p><a href="twc.html">Read the full day-3 guide, with day 1 and day 2 graded &rarr;</a></p>
</div>
"""

    nxt_bits = []
    for r in open_rows[:6]:
        pa, pb = complementary(r.get("consensus_a"))
        nxt_bits.append(
            '<li><a href="picks.html#m' + esc(r["match_id"]) + '"><strong>'
            + esc(r["team_a"]) + ' vs ' + esc(r["team_b"]) + '</strong></a>'
            + ' <span class="muted">&mdash; ' + esc(pa) + '% / ' + esc(pb) + '%'
            + ' &middot; pick ' + esc(r.get("pick") or "none") + ' &middot; '
            + esc(r.get("competition")) + ' (' + esc(r.get("points")) + ' pts)</span>'
            + '<br><span class="src">locks ' + esc(fmt_lock(r.get("lock_utc"))) + '</span></li>')
    nxt = "".join(nxt_bits)

    lim_bits = []
    for r in unresolved:
        lim_bits.append(
            '<li><strong>' + esc(r["team_a"]) + ' vs ' + esc(r["team_b"]) + '</strong>'
            + ' <span class="muted">&mdash; ' + esc(r.get("competition"))
            + ' &middot; locks ' + esc(fmt_lock(r.get("lock_utc"))) + '</span><br>'
            + '<span class="src">'
            + esc(" ".join(r.get("flag_text") or [])
                  or "No outside price and no official rating for one or both teams.")
            + '</span></li>')
    if not lim_bits:
        lim_bits.append('<li class="muted">Nothing is unresolved in this snapshot. The register '
                        'still records every limitation that applies to the rows we did price.</li>')
    single_bits = []
    for r in single[:10]:
        only = (r.get("estimates") or [{}])[0].get("short")
        single_bits.append(
            '<li>' + esc(r["team_a"]) + ' vs ' + esc(r["team_b"]) + ' &mdash; only <strong>'
            + esc(only) + '</strong> priced it <span class="src">('
            + esc(r.get("competition")) + ', locks ' + esc(fmt_lock(r.get("lock_utc")))
            + ')</span></li>')
    single_block = ('<ul class="clean tight">' + "".join(single_bits) + '</ul>') if single_bits else ''
    vrs_date = ((board["capture"].get("vrs") or {}).get("standings_date")
                or (board["capture"].get("vrs") or {}).get("as_of") or "unknown")

    unres = f"""
<h2 id="unresolved">Unresolved picks and the limitations behind them</h2>
<div class="notice {'red' if unresolved else 'green'}">
<strong>{cov['open_unresolved']} open fixture(s) with no pick.</strong>
A pick is left blank on purpose when no outside price exists <em>and</em> at least one team is
missing from Valve's official standings, because then there is nothing honest to base a number on.
Nothing is guessed and no placeholder is filled in.</div>
<ul class="clean">{"".join(lim_bits)}</ul>
<h3>Limitations that apply to the picks we did make</h3>
<ul class="clean">
<li><strong>Single-source fixtures ({len(single)} of {cov['open']}).</strong> These rest on one market,
usually Polymarket, because no bookmaker priced them. They are the softest numbers on the board.
{single_block}</li>
<li><strong>Prediction markets are not bookmakers.</strong> Polymarket prices are shown and labelled
as such. Where a bookmaker price also exists, both are averaged rather than one being preferred.</li>
<li><strong>Crowd percentages are ownership only, never a probability.</strong> How many Hotspawn
players picked a team is shown alongside every match, but it never feeds the number. It only tells
you how crowded a pick is, which is what the leaderboard rule is built on.</li>
<li><strong>Valve's standings are a snapshot.</strong> The newest official file is
{esc(vrs_date)}; any roster change after that date is not reflected in the own line, and such rows
are flagged.</li>
<li><strong>Hotspawn drops finished fixtures.</strong> Once a match locks and settles it leaves the
public payload, so grading is done against HLTV instead.</li>
<li><strong>Hotspawn does not list every match of an event.</strong> The Thunderpick Group&nbsp;B
decider (BETBOOM v Legacy, 16 Oct) is on HLTV but has no Hotspawn listing, so there is no pick'em
pick to make for it.</li>
</ul>
<p><a href="unresolved.html">Full unresolved register &rarr;</a></p>
"""

    others = """
<h2>Other boards in this repository</h2>
<p class="muted">Earlier sessions built their own boards on the same fixtures. They are kept and
linked; this one is the newest and cross-checks them.</p>
<ul class="clean">
<li><a href="../hotspawn/picks.html">hotspawn/picks.html</a> &mdash; the every-match board this one
cross-checks.</li>
<li><a href="../hotspawn/strategy.html">hotspawn/strategy.html</a> &mdash; contrarian leaderboard plan.</li>
<li><a href="../leaderboard/index.html">leaderboard/index.html</a> &mdash; day-1 contrarian review.</li>
<li><a href="../valuepicks/index.html">valuepicks/index.html</a> &mdash; value and coverage view.</li>
<li><a href="../docs/index.html">docs/</a> &mdash; the older verified analysis pages.</li>
</ul>
"""

    return page("Hotspawn CS2 — every match, one pick", "index.html",
                head + jump + stats + d3
                + f"<h2>Next to lock</h2><ul class=\"clean\">{nxt}</ul>"
                  f"<p><a href=\"picks.html\">See all {cov['open']} open fixtures &rarr;</a></p>"
                + unres + others,
                "Executive summary for the Hotspawn CS2 pick'em board: where the picks are, the "
                "day-3 Thunderpick call, coverage, unresolved picks and limitations.")


# --------------------------------------------------------------------------------- picks
def build_picks(board: dict) -> str:
    cov = board["coverage"]
    rows = [r for r in board["rows"] if r["status"] == "open"]
    locked = [r for r in board["rows"] if r["status"] == "locked"]
    cards = []
    for r in rows:
        pa, pb = complementary(r.get("consensus_a"))
        st = r.get("strategy") or {}
        ests = "".join(est_item(e, "link") for e in (r.get("estimates") or []))

        if not ests:
            ests = '<li class="muted">No outside price and no official rating &mdash; left blank on purpose.</li>'
        links = "".join(
            f' <a href="{esc(url)}">{esc(label)}</a>' for label, url in [
                ("Hotspawn", r.get("hotspawn_match_url") or LOBBY),
                ("HLTV (A)", r.get("hltv_url_a")), ("HLTV (B)", r.get("hltv_url_b")),
            ] if url)
        facts = []
        if r.get("vrs_a") and r.get("vrs_b"):
            facts.append(f"Valve points {r['vrs_a']} v {r['vrs_b']} "
                         f"(# {r.get('vrs_rank_a')} v # {r.get('vrs_rank_b')})")
        if r.get("hltv_rank_a") and r.get("hltv_rank_b"):
            facts.append(f"HLTV rank # {r['hltv_rank_a']} v # {r['hltv_rank_b']} "
                         f"({(board['capture'].get('hltv') or {}).get('ranking_date')})")
        if r.get("crowd_a") is not None:
            facts.append(f"crowd {r['crowd_a']}% / {r['crowd_b']}% "
                         f"({r.get('total_picks') or '?'} picks) - ownership only, never a probability")
        flags = "".join(f'<span class="tag">{esc(f.replace("_", " ").title())}</span> '
                        for f in (r.get("flags") or []))
        cards.append(f"""
<div class="card" id="m{esc(r['match_id'])}">
<p class="eyebrow">{esc(r.get('competition'))} &middot; tier {esc(r.get('tier'))}
&middot; {esc(r.get('points'))} pts &middot; {esc(r.get('best_of') and ('best of ' + str(r['best_of'])) or 'series length unknown')}</p>
<h3 style="margin:4px 0 2px">{esc(r['team_a'])} vs {esc(r['team_b'])}</h3>
<p class="src">Locks {esc(fmt_lock(r.get('lock_utc')))} &middot; starts {esc((r.get('start_utc') or '')[11:16])} UTC</p>
{prob_block(pa, pb, pa, pb, r['team_a'], r['team_b'])}
<div class="pickline"><span class="pick">Pick: {esc(r.get('pick') or 'unresolved')}</span>
{class_tag(st.get('class', ''))}</div>
<p><strong>Leaderboard play: {esc(st.get('play') or r.get('pick') or 'none')}</strong>
<span class="muted">{esc(st.get('reason') or '')}</span></p>
<p class="src">{esc('; '.join(facts))}</p>
<h4 style="margin:10px 0 4px;font-size:.85rem;color:var(--muted)">How we got the number</h4>
<ul class="clean tight">{ests}</ul>
<p class="src">{flags}</p>
<p class="src">Sources:{links}</p>
</div>""")
    locked_html = ""
    if locked:
        locked_html = "<h2>Locked in the last 36 hours (kept for grading)</h2><div class='scroll'><table>" \
            "<tr><th>Lock (UTC)</th><th>Match</th><th>Pts</th><th>Pick</th><th>Prob.</th><th>Basis</th></tr>" + \
            "".join(f"<tr><td>{esc(r.get('lock_utc'))}</td><td>{esc(r['team_a'])} v {esc(r['team_b'])}"
                    f"<br><span class='src'>{esc(r.get('competition'))}</span></td><td>{esc(r.get('points'))}</td>"
                    f"<td>{esc(r.get('pick') or 'unresolved')}</td>"
                    f"<td>{esc(complementary(r.get('consensus_a'))[0])}/{esc(complementary(r.get('consensus_a'))[1])}</td>"
                    f"<td class='src'>{esc(', '.join(e['short'] for e in (r.get('estimates') or [])) or 'none')}</td></tr>"
                    for r in locked) + "</table></div>"
    body = f"""
<p class="eyebrow">All picks</p>
<h1>Every open Hotspawn CS2 match</h1>
<p class="muted">{cov['open']} open fixtures, {cov['open_with_pick']} with a pick,
{cov['open_unresolved']} unresolved. Snapshot {esc(cov.get('generated_utc'))}.
<a href="#unresolved">Jump to the unresolved ones</a>.</p>
{''.join(cards) if cards else '<div class="notice red">No open fixtures in this snapshot.</div>'}
{locked_html}
<h2 id="unresolved">Unresolved in this snapshot</h2>
<div class="notice {'red' if cov['open_unresolved'] else 'green'}">
{esc(cov['open_unresolved'])} open fixtures have no pick. Each one is listed on the
<a href="unresolved.html">unresolved page</a> with the reason and the sources that were tried.</div>
"""
    return page("All picks — Hotspawn CS2", "picks.html", body,
                "A pick and both teams' win probability for every open Hotspawn CS2 fixture, with "
                "the source of each number.")


# --------------------------------------------------------------------------------- twc
def build_twc(board: dict) -> str:
    twc = board["twc"]
    ev = twc.get("event", {})
    board_rows = {r["match_id"]: r for r in board["rows"]}
    out = [f"""
<p class="eyebrow">Thunderpick World Championship 2026</p>
<h1>Day 1 and day 2 graded, day 3 called</h1>
<p class="muted">{esc(ev.get('format'))}
&middot; <a href="{esc(ev.get('hltv_event_url'))}">HLTV event page</a>
&middot; <a href="{esc(ev.get('hltv_results_url'))}">HLTV results</a>
&middot; <a href="{esc(ev.get('format_source'))}">format and line-up source</a></p>
"""]

    # ---------------------------------------------------------------- graded days
    ledger = {"picks": 0, "picks_ok": 0, "plays": 0, "plays_ok": 0,
              "pts_play": 0, "pts_crowd": 0, "frozen": 0}
    for day in twc.get("days", []):
        played = [m for m in day.get("matches", []) if m.get("winner")]
        upcoming = [m for m in day.get("matches", []) if not m.get("winner")]
        if played:
            out.append(f"<h2>Day {esc(day['day'])} &middot; {esc(day['date'])} &middot; "
                       f"{esc(day['label'])}</h2>")
            out.append('<div class="scroll"><table><tr><th>Match</th><th>Result</th>'
                       '<th>Our pick before lock</th><th>Crowd</th><th>Leaderboard play</th>'
                       '<th>Verdict</th><th>Sources</th></tr>')
            for m in played:
                winner = m.get("winner")
                pick = m.get("board_pick")
                play = m.get("leaderboard_play")
                pts = m.get("points") or 0
                if pick:
                    ledger["picks"] += 1
                    ledger["picks_ok"] += 1 if pick == winner else 0
                if play:
                    ledger["plays"] += 1
                    ledger["plays_ok"] += 1 if play == winner else 0
                    ledger["pts_play"] += pts if play == winner else 0
                    crowd_fav = (m.get("team_a") if (m.get("crowd_a") or 0) >= (m.get("crowd_b") or 0)
                                 else m.get("team_b"))
                    ledger["pts_crowd"] += pts if crowd_fav == winner else 0
                if m.get("pick_record_frozen"):
                    ledger["frozen"] += 1
                pick_cell = "not listed on Hotspawn"
                if pick:
                    when = (m.get("pick_record_utc") or "")[:16]
                    whence = (m.get("pick_record_source") or "").rstrip("/").split("/")[-1]
                    pick_cell = (esc(pick) + " <span class='muted'>("
                                 + f"{float(m.get('board_pick_p') or 0) * 100:.1f}" + "%)</span>"
                                 + ("<br><span class='src'>" + esc(whence) + " " + esc(when)
                                    + ("Z" if when else "") + "</span>" if whence or when else ""))
                crowd = ((str(m.get("crowd_a")) + "% / " + str(m.get("crowd_b")) + "%")
                         if m.get("crowd_a") is not None else "not published")
                play_cell = "none"
                if play:
                    play_cell = esc(play)
                    if m.get("class"):
                        play_cell += ' <span class="tag">' + esc(m.get("class")) + "</span>"
                verdict = "not applicable"
                if play:
                    verdict = ("<span class='tag VALUE'>play won</span>" if play == winner
                               else "<span class='tag LONG'>play lost</span>")
                    if pick and pick == winner and play != winner:
                        verdict += " <span class='src'>pick won, play lost</span>"
                    elif pick and pick != winner and play == winner:
                        verdict += " <span class='src'>pick lost, play won</span>"
                link_bits = []
                for key in ("hltv", "report", "bo3gg", "polymarket"):
                    if m.get(key):
                        link_bits.append(a_href(m.get(key), key))
                when_start = (m.get("start_utc") or "")[:16]
                extra = []
                if m.get("points"):
                    extra.append(str(m.get("points")) + " pts")
                if m.get("stage"):
                    extra.append(esc(m.get("stage")))
                out.append(
                    "<tr><td><strong>" + esc(m.get("team_a")) + " v " + esc(m.get("team_b"))
                    + "</strong><br><span class='src'>" + esc(when_start)
                    + ("Z" if when_start else "")
                    + (" &middot; " + " &middot; ".join(extra) if extra else "")
                    + "</span></td>"
                    + "<td><strong>" + esc(winner) + " " + esc(m.get("score") or "") + "</strong>"
                    + "<br><span class='src'>" + esc(m.get("maps") or "") + "</span></td>"
                    + "<td>" + pick_cell + "</td><td>" + esc(crowd) + "</td>"
                    + "<td>" + play_cell + "</td><td>" + verdict + "</td>"
                    + "<td class='src'>"
                    + (" ".join(link_bits) or "&mdash;") + "</td></tr>")
            out.append("</table></div>")
            for m in played:
                if m.get("note"):
                    out.append("<p class='src'>" + esc(m["team_a"]) + " v " + esc(m["team_b"])
                               + ": " + esc(m["note"]) + "</p>")
                if m.get("pick_record_note"):
                    out.append("<p class='src'>" + esc(m["team_a"]) + " v " + esc(m["team_b"])
                               + " &mdash; where that pick came from: "
                               + esc(m["pick_record_note"]) + "</p>")

    out.append(f"""
<h2>What two days are worth</h2>
<div class="stats">
<div><b>{ledger['picks_ok']}/{ledger['picks']}</b><span>published picks correct</span></div>
<div><b>{ledger['plays_ok']}/{ledger['plays']}</b><span>leaderboard plays correct</span></div>
<div><b>{ledger['pts_play']}</b><span>points if you took every play</span></div>
<div><b>{ledger['pts_crowd']}</b><span>points if you took the crowd</span></div>
</div>
<div class="notice"><strong>Provenance and sample size.</strong> {ledger['frozen']} of the
{ledger['picks']} graded matches have a frozen pre-lock record in this repository
(<code>hotspawn/data/pick_history.json</code>, entries flagged <code>frozen: true</code>). The four
day-1 rows are itemised in <code>reviews/22be6967-verification.md</code> section 3 and were produced
by rule v2 <em>in sample</em> (n = 4) after the fact; the aggregate &mdash; 3 of 4 picks, 4 of 4
plays &mdash; is what <code>hotspawn/data/summary.json</code> records under
<code>day1_review</code>. Read the day-1 column as a retrospective, not as a live record. Seven
graded matches is far too few to tune a rule
on: day 2 produced one contrarian win and one contrarian loss on signals that look the same on
paper. That is why rule v3 keeps v2's thresholds and only improves how the underdog's chance is
measured. Read the numbers above as a record, not as proof.</div>
<h2>What day 1 and day 2 say about day 3</h2>
<ul class="clean">{"".join('<li>' + esc(x) + '</li>' for x in twc.get('lessons', []))}</ul>
""")

    # ---------------------------------------------------------------- day 3 guide
    d3_matches = [m for d in twc.get("days", []) if d.get("day") == 3 for m in d.get("matches", [])]
    for m in d3_matches:
        r = board_rows.get(m.get("hotspawn_id"))
        head = ("<h2>Day 3 &middot; " + esc(m.get("team_a")) + " v " + esc(m.get("team_b")))
        if m.get("points"):
            head += " &middot; " + esc(m.get("points")) + " points"
        out.append(head + "</h2>")
        meta = [esc(m.get("stage"))]
        meta.append("locks " + (esc(fmt_lock(m.get("lock_utc"))) if m.get("lock_utc")
                                else "not listed on Hotspawn"))
        meta_links = []
        for key in ("hltv", "bo3gg", "polymarket"):
            if m.get(key):
                meta_links.append(a_href(m.get(key), key))
        out.append("<p class='muted'>" + " &middot; ".join(meta)
                   + (" &middot; " + " &middot; ".join(meta_links) if meta_links else "")
                   + "</p>")
        if r:
            pa, pb = complementary(r.get("consensus_a"))
            st = r.get("strategy") or {}
            out.append(prob_block(pa, pb, pa, pb, r["team_a"], r["team_b"]))
            out.append('<div class="pickline"><span class="pick">Pick: '
                       + esc(r.get("pick")) + "</span>" + class_tag(st.get("class", "")) + "</div>")
            out.append("<p><strong>Leaderboard play: " + esc(st.get("play")) + "</strong> &mdash; "
                       + esc(st.get("reason", "")) + "</p>")
            out.append("<ul class='clean tight'>"
                       + "".join(est_item(e) for e in (r.get("estimates") or [])) + "</ul>")
            ev_cost = ((st.get("p_fav") or 0) - (st.get("p_dog") or 0)) * (r.get("points") or 0)
            out.append("<p class='src'>Taking the underdog instead of the favourite gives up "
                       + f"{ev_cost:.1f}" + " points of expectation on our own numbers; it only "
                       + "pays if the underdog is better than "
                       + f"{(st.get('p_dog') or 0) * 100:.0f}" + "%.</p>")
            out.append("<p class='src'>Crowd: " + esc(r.get("crowd_a")) + "% on "
                       + esc(r["team_a"]) + ", " + esc(r.get("crowd_b")) + "% on "
                       + esc(r["team_b"]) + " &mdash; ownership only, never a probability.</p>")
        if m.get("head_to_head"):
            h2h = []
            for h in m["head_to_head"]:
                h2h.append("<li>" + esc(h.get("when")) + " &mdash; " + esc(h.get("result")) + " "
                           + a_href(h.get("url"), "source") + "</li>")
            out.append("<h3>Head to head</h3><ul class='clean tight'>" + "".join(h2h) + "</ul>")
        if m.get("map_pool_note"):
            out.append("<h3>Map pool</h3><p class='src'>" + esc(m["map_pool_note"]) + "</p>")
        if m.get("lineups"):
            lu = m["lineups"]
            out.append("<h3>Line-ups</h3><p class='src'>" + esc(m.get("team_a")) + ": "
                       + esc(", ".join(lu.get(m.get("team_a"), []))) + "<br>"
                       + esc(m.get("team_b")) + ": "
                       + esc(", ".join(lu.get(m.get("team_b"), []))) + "<br>"
                       + a_href(lu.get("source"), "source") + "</p>")
        if m.get("hltv_rank"):
            hr = m["hltv_rank"]
            out.append("<p class='src'>HLTV world ranking " + esc(hr.get("date")) + ": "
                       + esc(m.get("team_a")) + " #" + esc(hr.get("a")) + ", "
                       + esc(m.get("team_b")) + " #" + esc(hr.get("b")) + " &mdash; "
                       + a_href(hr.get("url"), "source") + "</p>")
        for mr in m.get("market_reads", []):
            out.append("<p class='src'>" + esc(mr.get("source")) + ": " + esc(mr.get("note"))
                       + " &mdash; " + a_href(mr.get("url"), "source") + "</p>")
        if m.get("note"):
            out.append("<p class='src'>" + esc(m["note"]) + "</p>")

    srcs = "".join("<li>" + a_href(u, u) + "</li>" for u in twc.get("sources", []))
    out.append("<h2>Sources</h2><ul class='clean tight'>" + srcs + "</ul>")
    return page("Thunderpick World Championship 2026 — day 3", "twc.html", "".join(out),
                "Thunderpick World Championship 2026: day 1 and day 2 graded against what was "
                "published before lock, and the day-3 Aurora v 9z call.")


def build_unresolved(board: dict) -> str:
    cov = board["coverage"]
    rows = [r for r in board["rows"] if r["status"] == "open"]
    unresolved = [r for r in rows if not r.get("estimates")]
    single = [r for r in rows if len(r.get("estimates") or []) == 1]
    twc_gaps = [m for d in board["twc"].get("days", []) for m in d.get("matches", [])
                if not m.get("hotspawn_id")]
    cap = board["capture"]
    prov = "".join(
        f"<tr><td class='src'>{esc(p.get('url'))}</td><td>{esc(p.get('status'))}</td>"
        f"<td>{esc((p.get('error') or '')[:60])}</td><td>{esc(p.get('fetched_utc'))}</td></tr>"
        for p in (cap.get("provenance") or [])[:40])
    body = f"""
<p class="eyebrow">Unresolved</p>
<h1>What we could not price, and exactly why</h1>
<p class="muted">A pick is left blank only when there is nothing honest to base it on. This page
lists every such fixture, the reason, and the sources that were tried. Nothing here is filled in
with a guess.</p>
<div class="stats">
<div><b>{cov['open_unresolved']}</b><span>open, no pick</span></div>
<div><b>{len(single)}</b><span>open, one source only</span></div>
<div><b>{cov['open']}</b><span>open fixtures in total</span></div>
<div><b>{cov['fixtures']}</b><span>CS2 listings read</span></div>
</div>
<h2>Open fixtures with no pick</h2>
"""
    if unresolved:
        body += '<div class="scroll"><table><tr><th>Match</th><th>Locks (UTC)</th>' \
                '<th>Why it cannot be priced</th><th>Sources tried</th><th>Hotspawn</th></tr>'
        for r in unresolved:
            body += (f"<tr><td><strong>{esc(r['team_a'])} v {esc(r['team_b'])}</strong>"
                     f"<br><span class='src'>{esc(r.get('competition'))} &middot; tier {esc(r.get('tier'))}</span></td>"
                     f"<td>{esc(fmt_lock(r.get('lock_utc')))}</td>"
                     f"<td>{esc(' '.join(r.get('flag_text') or []) or 'No outside price and no official rating.')}</td>"
                     f"<td class='src'>Pinnacle &middot; bo3.gg &middot; Polymarket &middot; Valve standings &middot; HLTV ranking</td>"
                     f"<td>" + a_href(r.get("hotspawn_match_url") or LOBBY, "link")
                     + "</td></tr>")
        body += "</table></div>"
    else:
        body += ('<div class="notice green">Nothing is unresolved in this snapshot: every open '
                 'Hotspawn CS2 fixture has at least one independent outside price or an official '
                 'rating for both teams. The register of limitations still applies to the rows '
                 'that were priced from a single source.</div>')

    body += "<h2>Limitations behind the numbers we did publish</h2><ul class='clean'>"
    body += f"""<li><strong>Single-source rows ({len(single)}).</strong> Only one outside source priced
these, so there is no cross-check. They are the softest numbers on the board and are tagged
<code>SINGLE_SOURCE</code> everywhere they appear."""
    if single:
        body += "<ul class='clean tight'>" + "".join(
            f"<li>{esc(r['team_a'])} v {esc(r['team_b'])} &mdash; {esc((r.get('estimates') or [{}])[0].get('short'))}"
            f" <span class='src'>({esc(r.get('competition'))}, locks {esc(fmt_lock(r.get('lock_utc')))})</span></li>"
            for r in single) + "</ul>"
    body += f"""</li>
<li><strong>Valve's standings lag roster moves.</strong> The newest official file is
{esc((cap.get('vrs') or {}).get('standings_date') or 'unknown')} ({esc((cap.get('vrs') or {}).get('commit', '')[:10])}).
A team that changed players after that date is rated on a five that no longer plays; those rows are
flagged <code>VRS_ROSTER_OUTDATED</code> and the own line is dropped when the change is less than
60 days old.</li>
<li><strong>Hand-verified prices.</strong> Where no automated source priced a fixture, a bookmaker
price was read by hand from the named page and tagged <code>MANUAL_READ</code> with the exact time.
It is dropped from the average once it is more than eight hours old, like any other price.</li>
<li><strong>Prediction markets are not bookmakers.</strong> Polymarket prices are market opinions,
not bookmaker odds, and are labelled as such. They are averaged with bookmaker prices rather than
substituted for them.</li>
<li><strong>Hotspawn removes settled fixtures.</strong> Once a match locks and settles it leaves the
public payload, so grading uses HLTV's official results instead of Hotspawn's own page.</li>
<li><strong>Not every match of an event is listed by Hotspawn.</strong> The fixtures below exist on
HLTV but have no Hotspawn listing, so there is no pick'em pick to make for them.</li>
</ul>"""
    if twc_gaps:
        body += '<div class="scroll"><table><tr><th>Match</th><th>Starts (UTC)</th><th>Event</th>' \
                '<th>Sources</th></tr>'
        for m in twc_gaps:
            body += (f"<tr><td><strong>{esc(m.get('team_a'))} v {esc(m.get('team_b'))}</strong></td>"
                     f"<td>{esc((m.get('start_utc') or '')[:16])}Z</td>"
                     f"<td>{esc(m.get('stage') or 'Thunderpick World Championship 2026')}</td>"
                     f"<td class='src'>" + "".join(
                         f'<a href="{esc(m.get(k))}">{esc(k)}</a> '
                         for k in ("hltv", "bo3gg") if m.get(k)) + "</td></tr>")
        body += "</table></div>"
    body += f"""
<h2>What the last collection actually reached</h2>
<div class="scroll"><table><tr><th>URL</th><th>HTTP</th><th>Error</th><th>Read (UTC)</th></tr>
{prov or '<tr><td colspan="4" class="src">No provenance recorded (seeded capture).</td></tr>'}
</table></div>
<p class="src">A source that answers with an error, or is refused, keeps its previous capture with
the original read time &mdash; it is never relabelled as fresh.</p>
"""
    return page("Unresolved picks and limitations — Hotspawn CS2", "unresolved.html", body,
                "Every Hotspawn CS2 fixture this board could not price, the reason, and the sources "
                "that were tried.")


# --------------------------------------------------------------------------------- method
def build_method(board: dict) -> str:
    cov = board["coverage"]
    cap = board["capture"]
    vrs = cap.get("vrs") or {}
    hltv = cap.get("hltv") or {}
    src_rows = "".join(f"""<tr><td><strong>{esc(k)}</strong></td><td>{esc((cap.get(k) or {}).get('mode'))}</td>
<td class="src">{esc((cap.get(k) or {}).get('read_utc') or (cap.get(k) or {}).get('fetched_utc') or '')}</td>
<td class="src">{esc((cap.get(k) or {}).get('page_url') or (cap.get(k) or {}).get('blob_url')
or (cap.get(k) or {}).get('url') or '')}</td></tr>"""
                       for k in ("hotspawn", "pinnacle", "bo3", "polymarket", "vrs", "hltv"))
    ladder = "".join(f"<li><strong>{esc(v)}</strong> &mdash; {esc(model.RUNG_LABEL[k])}"
                     f"{' (' + str(cov['open_by_rung'].get(k, 0)) + ' open fixtures resolved on this rung)' if k in '1234' else ''}</li>"
                     for k, v in model.RUNG_SHORT.items())
    rules = [("VALUE", "The crowd majority is on the side our numbers make the underdog. Take the "
                       "favourite: it is both more likely and less owned."),
             ("CONTRARIAN", "Underdog consensus at least 38%, every estimate at least 30%, and crowd "
                            "share at least 10 points below its chance. Take the underdog."),
             ("SITUATIONAL", "Underdog consensus at least 30%, every estimate at least 25%, crowd "
                             "share at most half its chance, and a strong or moderate verified factor "
                             "against the favourite with none against the underdog. Take the underdog."),
             ("LONG SHOT", "Underdog at least 20% with 10% or less of the crowd. Keep the favourite; "
                           "punt on the underdog only if you are far behind."),
             ("CHALK", "Anything else. Take the favourite.")]
    rule_rows = "".join(f"<li><strong>{esc(a)}</strong> &mdash; {esc(b)}</li>" for a, b in rules)
    body = f"""
<p class="eyebrow">Method</p>
<h1>How every number on this board is produced</h1>
<h2>Reverse-engineering the Hotspawn lobby</h2>
<p>play.hotspawn.com is an Angular app that renders on the server. Every public page
(<code>/lobby</code>, <code>/cs2-pickems</code>, <code>/thp-pickems</code>) ships its data inside a
single <code>&lt;script id="ng-state"&gt;</code> block (Angular TransferState). The collector fetches
the three pages, parses that JSON, and walks it for objects that carry
<code>scheduled_start_time</code> and <code>participants0_name</code>. That gives the fixture id,
competition, tier, stage, points, the exact <code>lock_time</code> epoch, both teams, and the public
crowd pick share. Nothing is scraped out of the rendered HTML, and no login or key is used.</p>
<p class="src">The crowd share is stored as <em>ownership</em> and is never allowed to touch a
probability. A unit test fails the build if it ever does.</p>
<h2>The probability ladder</h2>
<p>Every rung that answers is kept, and the published probability is the average of the independent
answers. Each answer is shown on the pick card with its own link.</p>
<ul class="clean">{ladder}</ul>
<h2>Our own line</h2>
<p>When no market prices a fixture we originate one from Valve's official Regional Standings:
<code>P = 1/(1+10^(-k*(pointsA-pointsB)/400))</code> with <code>k = {cov['k_valve']}</code>.
{cov['k_valve_provenance']} HLTV's world ranking is carried alongside as an independent cross-check
and is shown on every row that has one.</p>
<p class="src">Valve file: {esc(vrs.get('file') or 'unknown')} @ {esc((vrs.get('commit') or '')[:10])}
&mdash; <a href="{esc(vrs.get('blob_url'))}">official source</a>.
HLTV ranking: {esc(hltv.get('ranking_date') or 'unknown')} &mdash;
<a href="{esc(hltv.get('url'))}">official source</a>.</p>
<h2>Margin removal</h2>
<p>Bookmaker odds are converted with proportional (multiplicative) margin removal: each side's
implied probability is divided by the sum of both. A pair is rejected as not a real two-way book when
the overround is below 0.98 or above 1.25. Polymarket prices are normalised the same way.</p>
<h2>Leaderboard rule (v3)</h2>
<ul class="clean">{rule_rows}</ul>
<div class="notice">v3 keeps v2's thresholds. Day 2 produced one contrarian win and one contrarian
loss on signals that look the same on paper; at seven graded matches, retuning those thresholds
would be fitting noise. What v3 changes is measurement: the underdog's chance is the consensus of up
to four independent estimates instead of two, because bo3.gg and the hand-verified book reads were
added to the ladder.</div>
<h2>Sources in the latest collection</h2>
<div class="scroll"><table><tr><th>Source</th><th>Mode</th><th>Read (UTC)</th><th>URL</th></tr>
{src_rows}</table></div>
<h2>Automation</h2>
<p>The scheduled workflow runs every four hours: collect, model, build, run the invariant tests,
commit, and ask GitHub Pages to rebuild. A source that fails keeps its previous capture with the
original read time. Nothing is hand-edited on a schedule.</p>
<h2>Known gaps</h2>
<ul class="clean"><li>Not every Hotspawn fixture has an HLTV match page; low-tier events often do not.
Where HLTV is missing, the row links the team's HLTV page or, failing that, the Hotspawn fixture only.</li>
<li>Pinnacle's public feed prices a small number of CS2 leagues, so most bookmaker prices on this
board come from the provider relayed by bo3.gg, and that provider is named on every row.</li>
<li>Hotspawn's own "View match" links are placeholders on some listings; the row then falls back to
the lobby.</li></ul>
"""
    return page("Method and sources — Hotspawn CS2", "method.html", body,
                "How the board reverse-engineers Hotspawn, the probability ladder, the own line and "
                "the leaderboard rule, with every source and its read time.")


# --------------------------------------------------------------------------------- flagged
def build_flagged(board: dict) -> str:
    rows = board["rows"]
    groups: dict[str, list[dict]] = {}
    for r in rows:
        for f in (r.get("flags") or []):
            groups.setdefault(f, []).append(r)

    # Order: things that change a number first, platform housekeeping last.
    order = ["UNRESOLVED", "SINGLE_SOURCE", "MANUAL_READ", "SPLIT", "NO_VRS_TEAM",
             "VRS_ROSTER_OUTDATED", "DUPLICATE_LISTING", "ALIAS", "STALE_LISTING"]
    keys = [k for k in order if k in groups] + [k for k in sorted(groups) if k not in order]
    counts = "".join('<div><b>' + str(len(groups[k])) + '</b><span>'
                     + esc(k.replace("_", " ").lower()) + "</span></div>" for k in keys)
    body = f"""
<p class="eyebrow">Flagged for review</p>
<h1>Irregularities and caveats</h1>
<p class="muted">Everything below is published rather than quietly fixed. None of it blocks the
board; each item carries the link needed to check it by hand.</p>
<div class="stats">{counts or '<div><b>0</b><span>flags raised</span></div>'}</div>
"""
    for k in keys:
        listed = groups[k]
        title = k.replace("_", " ").title()
        if k == "STALE_LISTING":
            body += ("<h2>" + esc(title) + " (" + str(len(listed)) + ")</h2>"
                     "<p class='muted'>Hotspawn keeps fixtures in its public payload long after "
                     "their lock time passes. That is how the platform behaves, not a mistake in "
                     "our data: these rows are excluded from the open board, so they never receive "
                     "a pick. Listed for completeness.</p>"
                     "<details><summary>Show the " + str(len(listed)) + " stale listings</summary>"
                     "<ul class='clean tight'>")
            for r in listed:
                body += ("<li>" + esc(r["team_a"]) + " v " + esc(r["team_b"])
                         + " <span class='src'>&mdash; " + esc(r.get("competition"))
                         + ", locked " + esc(fmt_lock(r.get("lock_utc"))) + "</span></li>")
            body += "</ul></details>"
            continue
        body += ("<h2>" + esc(title) + " (" + str(len(listed)) + ")</h2>"
                 "<p class='muted'>" + esc(model.FLAG_TEXT.get(k, "")) + "</p>"
                 "<div class='scroll'><table><tr><th>Match</th><th>Event</th>"
                 "<th>Published number</th><th>Sources</th></tr>")
        for r in listed:
            link_bits = []
            if r.get("hotspawn_match_url"):
                link_bits.append(a_href(r["hotspawn_match_url"], "hotspawn"))
            for key, label in (("hltv_url_a", "hltv"), ("polymarket_url", "polymarket"),
                               ("pinnacle_url", "pinnacle"), ("bo3_url", "bo3.gg")):
                if r.get(key):
                    link_bits.append(a_href(r[key], label))
            pa, pb = complementary(r.get("consensus_a"))
            num = (str(pa) + "% / " + str(pb) + "%") if r.get("consensus_a") is not None else "blank"
            body += ("<tr><td><strong>" + esc(r["team_a"]) + " v " + esc(r["team_b"]) + "</strong>"
                     + ("<br><span class='src'>#"
                        + esc(r["match_id"]) + "</span>" if r.get("match_id") else "")
                     + "</td><td class='src'>" + esc(r.get("competition")) + "</td>"
                     + "<td>" + esc(num) + "<br><span class='src'>"
                     + esc(r.get("estimate_sources") or "none") + "</span></td>"
                     + "<td class='src'>"
                     + (" ".join(link_bits) or "&mdash;") + "</td></tr>")
        body += "</table></div>"

    # ---------------------------------------------------------------- link check
    verify = read_json(DATA / "verify.json", {}) or {}
    if verify.get("external_links"):
        bad = [x for x in verify["external_links"]
               if not (x.get("status") and 200 <= x["status"] < 400)]
        body += ("<h2>Source links that did not answer (" + str(len(bad)) + " of "
                 + str(len(verify["external_links"])) + ")</h2>"
                 "<p class='muted'>Checked " + esc(str(verify.get("checked_utc", ""))[:16])
                 + "Z. A refusal is not evidence that a link is wrong &mdash; Hotspawn, HLTV and "
                 + "bo3.gg all rate-limit automated clients. Each link below still carries the "
                 + "read time it was captured with.</p>")
        if bad:
            body += ('<div class="scroll"><table><tr><th>URL</th><th>HTTP</th>'
                     '<th>Error</th></tr>')
            for x in bad:
                body += ("<tr><td class='src'>" + esc(x.get("url")) + "</td><td>"
                         + esc(x.get("status") if x.get("status") is not None else "&mdash;")
                         + "</td><td class='src'>" + esc(x.get("error") or "") + "</td></tr>")
            body += "</table></div>"

    body += f"""
<h2>Repository-level irregularities found by this session</h2>
<ul class="clean">
<li><strong>Duplicate Hotspawn listing.</strong> Hotspawn carried Legacy v FURIA twice on 15 Oct
(ids <code>1080204</code> at 16:00 UTC and <code>1081614</code> at 17:00 UTC) for the same match.
Both were priced identically; only one should count if you are tallying points.</li>
<li><strong>Hotspawn does not list every match in an event.</strong> Aurora v Ninjas in Pyjamas
(15 Oct) and BETBOOM v Legacy (16 Oct, Group B decider) are on
<a href="https://www.hltv.org/results?event=8932">HLTV</a> but have no row in any capture this
repository holds, so no pick'em pick exists for them.</li>
<li><strong>Finished fixtures disappear from the payload.</strong> 9z v Falcons and PARIVISION v
BetBoom were captured before lock on 15 Oct and are gone from the 21:34 UTC payload, so grading
depends on HLTV, not on Hotspawn. The pre-lock numbers survive in
<code>hotspawn/data/pick_history.json</code>.</li>
<li><strong>One fixture has an unnamed opponent.</strong> Hotspawn lists
<code>1079628</code> Gothic v <em>LFO 10</em>; the counterpart book page names only a line-up
(Jackinho, Sapec, dottie, flaw, tvs), never a team, so the identity is inferred and flagged rather
than asserted.</li>
<li><strong>Hotspawn names WBT "WROTBERRY".</strong> HLTV, Liquipedia and the markets call the team
WBT; the alias and its evidence are in <code>a6f05f99/research/aliases.json</code>.</li>
<li><strong>Valve's snapshot is older than some roster moves.</strong> The newest official file is
2026-10-05; PARIVISION's 17 Sep swap of slaxejezzz for HObbit is still not reflected in it.</li>
<li><strong>ASTRAL is not Astralis.</strong> Two different teams. No alias links them and the
matcher requires both teams plus a kickoff inside six hours before it joins any price to a
fixture.</li>
</ul>
<h2>Inherited from earlier sessions</h2>
<p class="muted">Earlier boards in this repository keep their own flagged pages:
<a href="../hotspawn/flagged.html">hotspawn/flagged.html</a>,
<a href="../leaderboard/flagged.html">leaderboard/flagged.html</a>,
<a href="../valuepicks/flagged.html">valuepicks/flagged.html</a>,
<a href="../flagged.html">flagged.html</a>.</p>
"""
    return page("Flagged for review — Hotspawn CS2", "flagged.html", body,
                "Irregularities and caveats found while building the Hotspawn CS2 board, each with "
                "the link needed to check it.")


# --------------------------------------------------------------------------------- main
def main() -> int:
    board = model.build_board()
    (HERE / "style.css").write_text(CSS, encoding="utf-8")
    (HERE / "index.html").write_text(build_index(board), encoding="utf-8")
    (HERE / "picks.html").write_text(build_picks(board), encoding="utf-8")
    (HERE / "twc.html").write_text(build_twc(board), encoding="utf-8")
    (HERE / "unresolved.html").write_text(build_unresolved(board), encoding="utf-8")
    (HERE / "method.html").write_text(build_method(board), encoding="utf-8")
    (HERE / "flagged.html").write_text(build_flagged(board), encoding="utf-8")
    write_json(DATA / "board.json", {
        "coverage": board["coverage"],
        "rows": [{k: v for k, v in r.items() if k != "estimates"} for r in board["rows"]],
    })
    write_csv(DATA / "board.csv", model.to_csv_rows(board), model.FIELDS)
    cov = board["coverage"]
    print(f"pages built: index, picks, twc, unresolved, method, flagged "
          f"({cov['open']} open / {cov['open_with_pick']} picked / {cov['open_unresolved']} unresolved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
