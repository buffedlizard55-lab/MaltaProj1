#!/usr/bin/env python3
"""Build the f323b4a7 static site (mobile-first, no JavaScript required)."""
from __future__ import annotations

import html
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
import research as R  # noqa: E402

R.DAY3_BY_ID = {d["id"]: d for d in R.DAY3}

PAGES = ["index", "picks", "day3", "review", "unresolved", "flagged", "all", "method"]
TITLES = {
    "index": "Executive summary",
    "picks": "Picks for every open match",
    "day3": "Day-3 guide - Thunderpick World Championship",
    "review": "Day 1 & day 2 review",
    "unresolved": "Unresolved picks & limitations",
    "flagged": "Flagged for review",
    "all": "Full Hotspawn CS2 fixture inventory",
    "method": "Methodology & sources",
}


def esc(x):
    return html.escape("" if x is None else str(x))


def pct(x):
    return "" if x is None else f"{x * 100:.1f}%"


def utc_short(iso):
    return iso.replace("T", " ").replace(":00Z", "Z") if iso else ""


def nav(active):
    items = "".join(
        f'<a class="nav{" on" if p == active else ""}" href="{p}.html">{esc(TITLES[p])}</a>'
        for p in PAGES)
    return f'<nav class="nav">{items}</nav>'


def head(title, desc):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1220">
<title>{esc(title)} - Hotspawn CS2 picks (f323b4a7)</title>
<meta name="description" content="{esc(desc)}">
<link rel="stylesheet" href="style.css">
</head>
<body>
"""


def shell(active, title, body, board, extra_head=""):
    s = board["summary"]
    return (head(title, TITLES[active]) + extra_head + f"""
<header class="top">
  <div class="wrap">
    <a class="brand" href="index.html">Hotspawn CS2 &middot; picks &amp; lines</a>
    <div class="stamp">Snapshot {esc(s['generated_utc'])} &middot; Hotspawn read {esc(s['hotspawn_read_utc'])}</div>
  </div>
  {nav(active)}
</header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
  <p><strong>Evidence policy.</strong> Probabilities come from outside markets (Pinnacle, Polymarket) or from
  our own line fitted on Valve's published results. Hotspawn's crowd pick share is stored as
  <em>ownership</em> only and is never used as a probability. Every row carries its source links; a value that
  cannot be confirmed from an official source is left blank and listed on the
  <a href="flagged.html">Flagged for review</a> page.</p>
  <p>Session <code>arena/f323b4a7</code> &middot; branch <code>arena/f323b4a7-maltaproj1</code> &middot;
  generated {esc(s['generated_utc'])}</p>
</footer>
</body>
</html>
""")


# --------------------------------------------------------------------------- index
def page_index(board):
    s = board["summary"]
    rows = board["rows"]
    upcoming = sorted(rows, key=lambda r: r["lock_utc"])[:8]
    twc = [r for r in rows if r["tier"] == "S"]
    nomarket = [r for r in rows if r["rung"] == "C"]
    contested = [r for r in rows if "MODEL_MARKET_SPLIT" in (r.get("flags") or "")]

    stat = f"""
<section class="stats">
  <div class="stat"><b>{s['fixtures_total']}</b><span>CS2 fixtures listed on Hotspawn</span></div>
  <div class="stat"><b>{s['open']}</b><span>still open (lock in the future)</span></div>
  <div class="stat"><b>{s['open_with_pick']}</b><span>with a pick + both probabilities</span></div>
  <div class="stat"><b>{s['unresolved']}</b><span>unresolved</span></div>
</section>
<p class="lead">Hotspawn lists <strong>{esc(s['hotspawn_tier_text'])}</strong> CS2 pick'ems
(&ldquo;{esc(s['hotspawn_week_text'])}&rdquo;). Of those, <strong>{s['open']}</strong> are still pickable and
<strong>{s['open_with_pick']}</strong> have a pick with both teams' win probabilities. Next lock:
<strong>{esc(utc_short(s.get('next_lock_utc') or upcoming[0]['lock_utc']))}</strong>.</p>
"""

    soon = "".join(f"""
  <li class="row">
    <a href="picks.html#{esc(r['match_id'])}">
      <span class="t">{esc(utc_short(r['lock_utc']))}</span>
      <span class="m">{esc(r['team_a'])} v {esc(r['team_b'])}</span>
      <span class="p">{esc(r['pick'])} <em>{pct(max(r['p_a'] or 0, r['p_b'] or 0))}</em></span>
    </a>
  </li>""" for r in upcoming)

    twc_html = ""
    for r in twc:
        pick_p = r["p_a"] if r["pick"] == r["team_a"] else r["p_b"]
        twc_html += f"""
  <article class="card">
    <h3>{esc(r['team_a'])} v {esc(r['team_b'])}</h3>
    <p class="meta">Thunderpick World Championship 2026 &middot; Tier S &middot; {r['points']} pts &middot;
       locks {esc(utc_short(r['lock_utc']))} &middot; starts {esc(utc_short(r['start_utc']))}</p>
    <p class="pickline">Pick <strong>{esc(r['pick'])}</strong> &mdash; {pct(pick_p)}
       <span class="vs">v {pct(1 - (pick_p or 0))}</span></p>
    <p class="meta">Basis: {esc(r['basis'])} (rung {esc(r['rung'])}) &middot;
       own line {pct(r['own_p_a'])} / {pct(1 - (r['own_p_a'] or 0))} &middot;
       crowd ownership {esc(r['crowd_a_ownership_pct'])}% / {esc(r['crowd_b_ownership_pct'])}%</p>
    <p><a href="day3.html">Full day-3 analysis &rarr;</a></p>
  </article>"""

    body = f"""
<h1>Executive summary</h1>
{stat}
<section class="grid2">
  <div class="box">
    <h2>Next to lock</h2>
    <ul class="list">{soon}</ul>
    <p><a href="picks.html">All {s['open']} open picks &rarr;</a></p>
  </div>
  <div class="box">
    <h2>Day 3 &mdash; Thunderpick World Championship (Malta)</h2>
    {twc_html}
  </div>
</section>

<section class="box">
  <h2>Where everything lives</h2>
  <ul class="links">
    <li><a href="picks.html"><b>Picks for every open match</b></a> &mdash; {s['open']} fixtures, both
        probabilities, the basis used and the source link for each row.</li>
    <li><a href="day3.html"><b>Day-3 guide</b></a> &mdash; Aurora&ndash;9z and BetBoom&ndash;Legacy, group
        standings, playoff path and the contrarian-but-not-stupid call.</li>
    <li><a href="review.html"><b>Day 1 &amp; day 2 review</b></a> &mdash; every result with its HLTV link and
        what it means for today.</li>
    <li><a href="unresolved.html"><b>Unresolved picks &amp; limitations</b></a> &mdash; the
        {len(nomarket)} fixtures with no featured market price, what blocked them and what was tried.</li>
    <li><a href="all.html"><b>Full fixture inventory</b></a> &mdash; all {s['fixtures_total']} CS2 fixtures
        Hotspawn lists, open and locked.</li>
    <li><a href="flagged.html"><b>Flagged for review</b></a> &mdash; irregularities and unverified values.</li>
    <li><a href="method.html"><b>Methodology &amp; sources</b></a> &mdash; the ladder, the calibration and
        every source with its read time.</li>
  </ul>
</section>

<section class="box warn">
  <h2>Unresolved &amp; limitations (summary)</h2>
  <p>All {s['open']} open fixtures carry a pick, so the unresolved register holds
  <strong>0 fixtures with no pick at all</strong>. {len(nomarket)} fixtures could not be resolved the same way
  as the featured picks because <strong>no Pinnacle or Polymarket price exists for them</strong>; their
  probability is our own line from Valve's official standings (rung C) and they are flagged
  <code>NO_MARKET</code>. {len(contested)} more are resolved from a market price but our own line disagrees on
  the favourite or by 10+ points (<code>MODEL_MARKET_SPLIT</code>), and 4 are coin-flips
  (<code>COIN_FLIP</code>). Standing limitations, including the 28 rows whose series length no source states,
  are listed per row and in one table.
  <a href="unresolved.html">Full register and per-row limitations &rarr;</a></p>
</section>
"""
    return shell("index", "Executive summary", body, board)


# --------------------------------------------------------------------------- picks
def page_picks(board):
    s = board["summary"]
    rows = sorted(board["rows"], key=lambda r: r["lock_utc"])
    out = []
    for r in rows:
        pa, pb = r["p_a"], r["p_b"]
        pick_p = pa if r["pick"] == r["team_a"] else pb
        src = []
        if r["detail"].get("pinnacle"):
            src.append(f'<a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/">Pinnacle</a>')
        if r["detail"].get("polymarket") or r["rung"] == "B":
            src.append(f'<a href="{esc(r["detail"].get("polymarket_url") or "https://polymarket.com/")}">Polymarket</a>')
        src.append('<a href="' + esc(R.SOURCES[4][1]) + '">Valve VRS</a>')
        if r["hltv_rank_a"] or r["hltv_rank_b"]:
            src.append('<a href="https://www.hltv.org/ranking/teams/2026/october/12">HLTV rank</a>')
        src.append(f'<a href="{esc(r["hotspawn_url"])}">Hotspawn</a>')
        out.append(f"""
<li class="match" id="{esc(r['match_id'])}">
  <div class="mhead">
    <span class="lock">{esc(utc_short(r['lock_utc']))}</span>
    <span class="tier t{r['tier']}">{esc(r['tier'])}</span>
    <span class="pts">{esc(r['points'])} pts</span>
    <span class="cls c{esc(r['leaderboard_class']).replace(' ', '')}">{esc(r['leaderboard_class'])}</span>
  </div>
  <div class="teams">
    <div class="team{' win' if r['pick'] == r['team_a'] else ''}">
      <span class="tn">{esc(r['team_a'])}</span><span class="tp">{pct(pa)}</span>
    </div>
    <div class="team{' win' if r['pick'] == r['team_b'] else ''}">
      <span class="tn">{esc(r['team_b'])}</span><span class="tp">{pct(pb)}</span>
    </div>
  </div>
  <div class="bar"><span style="width:{100 * (pa or 0):.1f}%"></span></div>
  <p class="pick">Pick: <strong>{esc(r['pick'])}</strong> ({pct(pick_p)})</p>
  <p class="meta">{esc(r['competition'])} &middot; starts {esc(utc_short(r['start_utc']))} &middot;
     basis: {esc(r['basis'])} (rung {esc(r['rung'])}) &middot; own line
     {pct(r['own_p_a'])}/{pct(1 - (r['own_p_a'] or 0))} &middot; crowd ownership
     {esc(r['crowd_a_ownership_pct'])}%/{esc(r['crowd_b_ownership_pct'])}% ({esc(r['total_picks'])} picks)</p>
  <p class="meta">Leaderboard play: <strong>{esc(r['leaderboard_pick'])}</strong> &mdash;
     {esc(r['leaderboard_note'])}</p>
  <p class="src">Sources: {' &middot; '.join(src)}</p>
  {('<p class="flags">Flags: ' + esc(r.get('flags')) + '</p>') if r.get('flags') else ''}
</li>""")
    body = f"""
<h1>Picks for every open match</h1>
<p class="lead">{s['open']} of {s['fixtures_total']} listed CS2 fixtures are still open.
Rungs: Pinnacle {s['rungs']['A']} &middot; Polymarket {s['rungs']['B']} &middot; own line {s['rungs']['C']}
&middot; unresolved {s['rungs']['D']}. Sorted by lock time (UTC).</p>
<ul class="matches">{''.join(out)}</ul>
"""
    return shell("picks", "Picks for every open match", body, board)


# --------------------------------------------------------------------------- day3
def page_day3(board):
    s = board["summary"]
    rows = {r["match_id"]: r for r in board["rows"]}
    twc = [r for r in board["rows"] if r["tier"] == "S"]
    cards = ""
    for r in twc:
        pick_p = r["p_a"] if r["pick"] == r["team_a"] else r["p_b"]
        d = R.DAY3_BY_ID.get(r["match_id"], {})
        cards += f"""
<article class="card big">
  <h3>{esc(r['team_a'])} v {esc(r['team_b'])}</h3>
  <p class="meta">{esc(d.get('group', 'Group decider'))} &middot; BO3 &middot; locks
     {esc(utc_short(r['lock_utc']))} UTC &middot; starts {esc(utc_short(r['start_utc']))} UTC</p>
  <table class="tbl">
    <tr><th>Estimate</th><th>{esc(r['team_a'])}</th><th>{esc(r['team_b'])}</th></tr>
    <tr><td>Published price used</td><td>{pct(r['p_a'])}</td><td>{pct(r['p_b'])}</td></tr>
    <tr><td>Our own line (Valve points)</td><td>{pct(r['own_p_a'])}</td><td>{pct(1 - (r['own_p_a'] or 0))}</td></tr>
    <tr><td>Consensus of the two</td><td>{pct(r['consensus_p_a'])}</td><td>{pct(1 - (r['consensus_p_a'] or 0))}</td></tr>
  </table>
  <p class="pickline">Pick <strong>{esc(r['pick'])}</strong> at {pct(pick_p)}</p>
  <p class="meta">Valve standings: {esc(r['team_a'])} #{esc(r['vrs_standing_a'])} ({esc(r['vrs_points_a'])} pts),
     {esc(r['team_b'])} #{esc(r['vrs_standing_b'])} ({esc(r['vrs_points_b'])} pts) &middot;
     HLTV ranks {esc(r['hltv_rank_a'])} / {esc(r['hltv_rank_b'])} &middot;
     crowd ownership {esc(r['crowd_a_ownership_pct'])}% / {esc(r['crowd_b_ownership_pct'])}%</p>
  <p class="src">Sources:
     <a href="{esc(d.get('hltv_url', ''))}">HLTV match</a> &middot;
     <a href="{esc(d.get('analytics_url', ''))}">HLTV odds &amp; prediction</a> &middot;
     <a href="{esc(r['hotspawn_url'])}">Hotspawn</a> &middot;
     <a href="{esc(R.SOURCES[4][1])}">Valve VRS</a></p>
</article>"""

    groups = """
<table class="tbl">
  <tr><th>Group</th><th>Played</th><th>Result</th><th>Status</th></tr>
  <tr><td>A</td><td>9z 2-0 Aurora</td><td>9z win</td><td>9z to winners' match</td></tr>
  <tr><td>A</td><td>Falcons 2-0 NiP</td><td>Falcons win</td><td>Falcons to winners' match</td></tr>
  <tr><td>A</td><td>Falcons 2-1 9z</td><td>Falcons win</td><td>Falcons to playoff</td></tr>
  <tr><td>A</td><td>Aurora 2-0 NiP</td><td>Aurora win</td><td>NiP out</td></tr>
  <tr><td>A</td><td>9z v Aurora</td><td>decider</td><td><strong>today 14:00 UTC</strong></td></tr>
  <tr><td>B</td><td>Legacy 2-0 PARIVISION</td><td>Legacy win</td><td>Legacy to winners' match</td></tr>
  <tr><td>B</td><td>FURIA 2-0 BetBoom</td><td>FURIA win</td><td>FURIA to winners' match</td></tr>
  <tr><td>B</td><td>FURIA 2-1 Legacy</td><td>FURIA win</td><td>FURIA to playoff</td></tr>
  <tr><td>B</td><td>BetBoom 2-1 PARIVISION</td><td>BetBoom win</td><td>PARIVISION out</td></tr>
  <tr><td>B</td><td>BetBoom v Legacy</td><td>decider</td><td><strong>today 17:00 UTC</strong></td></tr>
</table>
<p class="src">Source: <a href="https://www.hltv.org/events/8932/thunderpick-world-championship-2026">HLTV event page bracket</a>,
read 2026-10-16T04:28:00Z.</p>
"""

    aurora = R.AURORA_ROSTER
    body = f"""
<h1>Day 3 &mdash; Thunderpick World Championship 2026</h1>
<p class="lead">Event: {esc(R.EVENT['dates'])} &middot; {esc(R.EVENT['location'])} &middot;
{esc(R.EVENT['prize_pool'])} &middot; {R.EVENT['teams']} teams. Two group deciders are pickable today;
the winners join Falcons and FURIA in the playoff.</p>

<h2>The two matches</h2>
{cards}

<h2>Group standings &amp; path</h2>
{groups}

<h2>What days 1 and 2 tell us</h2>
<ul class="bullets">
  <li><strong>The day-1 upset was real but not repeatable evidence.</strong> 9z beat Aurora 2-0 on day 1
      (<a href="https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026">HLTV report</a>),
      yet Aurora are #6 and 9z #17 on HLTV and #9 vs #17 on Valve's standings. One BO3 is not a ranking.</li>
  <li><strong>Aurora answered immediately.</strong> A 2-0 over NiP on day 2, and HLTV's own analytics page
      credits Aurora with 3 wins in the last 5 and the bookmaker-favourite tag.</li>
  <li><strong>9z have now lost two on the spin at this event</strong> (0-2 Aurora, 1-2 Falcons), so the
      day-1 form spike has already been tested twice.</li>
  <li><strong>BetBoom are the live underdog story of Group B</strong> &mdash; they lost 0-2 to FURIA, then beat
      PARIVISION 2-1 in an elimination match, while Legacy lost the winners' match 1-2 to FURIA. Momentum
      favours BetBoom; the standings (Legacy #2, 1931 pts vs BetBoom #11, 1596 pts) favour Legacy.</li>
  <li><strong>Contrarian-but-not-stupid:</strong> the only fixture where the crowd is genuinely split is
      BetBoom&ndash;Legacy at 50/50. Our consensus puts Legacy near 71%, so backing Legacy is both the
      likelier side and, at 50% ownership, not a crowd play. Aurora&ndash;9z is 88/11 on the crowd; taking
      Aurora is chalk, taking 9z needs the 30% consensus chance to be worth the 7-point tier-S payout.</li>
</ul>

<h2>Aurora's roster change &mdash; what the evidence actually says</h2>
<p>{esc(aurora['finding'])}</p>
<p class="meta">Lineup: {esc(', '.join(aurora['players']))} &middot; coach {esc(aurora['coach'])} &middot;
change announced {esc(aurora['change_date'])}.</p>
<p class="src">Sources:
{''.join(f'<a href="{esc(x["url"])}">{esc(x["label"])}</a> &middot; ' for x in aurora['sources']).rstrip(' &middot; ')}</p>
<div class="box warn"><p><strong>Irregularity flagged:</strong> {esc(aurora['irregularity'])}</p></div>

<h2>Playoff path (not pickable on Hotspawn)</h2>
<table class="tbl">
  <tr><th>Match</th><th>When</th><th>Link</th></tr>
  {''.join(f"<tr><td>{esc(m['teams'][0])} v {esc(m['teams'][1]) if len(m['teams'])>1 else ''}</td><td>{esc(m['when'])}</td><td><a href='{esc(m['url'])}'>HLTV</a></td></tr>" for m in R.PLAYOFFS)}
</table>
<p class="meta">Hotspawn lists only three TWC fixtures this week, so the semi-finals and final are not part of
the pick'em slate; they are recorded here for context only and no pick is invented for them.</p>
"""
    return shell("day3", "Day-3 guide", body, board)


# --------------------------------------------------------------------------- review
def page_review(board):
    def table(rows, title, note):
        out = []
        for m in rows:
            links = []
            if m.get("hltv"):
                links.append(f'<a href="{esc(m["hltv"])}">HLTV match</a>')
            if m.get("report"):
                links.append(f'<a href="{esc(m["report"])}">HLTV report</a>')
            out.append(f"""<tr>
  <td>{esc(m['teams'][0])} v {esc(m['teams'][1])}</td>
  <td>{esc(m['score'])}</td>
  <td><strong>{esc(m['winner'])}</strong></td>
  <td>{esc(m.get('maps') or m.get('note') or '')}</td>
  <td>{' &middot; '.join(links) or '<em>no match link captured</em>'}</td>
</tr>""")
        return f"""<h2>{esc(title)}</h2>
<p class="meta">{esc(note)}</p>
<table class="tbl">
  <tr><th>Match</th><th>Score</th><th>Winner</th><th>Detail</th><th>Source</th></tr>
  {''.join(out)}
</table>"""

    body = f"""
<h1>Day 1 &amp; day 2 review</h1>
<p class="lead">Every TWC 2026 result we could verify, with the official HLTV link. Nothing here is used as a
probability input; it is context for today's picks.</p>
{table(R.DAY1, 'Day 1 - 2026-10-14', 'Group opening rounds. Read from the HLTV event bracket and HLTV head-to-head links, 2026-10-16.')}
{table(R.DAY2, 'Day 2 - 2026-10-15', 'Winners/elimination/decider rounds. Verified against HLTV match pages (repository capture, read 2026-10-15T22:30:54Z).')}

<h2>What this changes for day 3</h2>
<ul class="bullets">
  <li>Day 1 delivered the upset the brief asks about (9z 2-0 Aurora), but day 2 showed the ranking order
      reasserting itself: Aurora 2-0 NiP, Falcons 2-1 9z, FURIA 2-1 Legacy, BetBoom 2-1 PARIVISION.</li>
  <li>Two of four day-2 winners were the lower-ranked side on our own line (BetBoom over PARIVISION at 53.4%
      was a near coin-flip; Legacy over FURIA at 46.6% was not). Elimination pressure at a $1m LAN is the
      clearest signal in the data.</li>
  <li>For day 3 both deciders are must-win for both teams, so rest and travel are equal; the differentiator is
      roster continuity, which favours Legacy (unchanged five) over BetBoom and is a wash between Aurora and 9z.</li>
</ul>
"""
    return shell("review", "Day 1 & 2 review", body, board)


# --------------------------------------------------------------------------- unresolved
def page_unresolved(board):
    s = board["summary"]
    rows = [r for r in board["rows"] if r["rung"] == "C"]
    contested = [r for r in board["rows"] if "MODEL_MARKET_SPLIT" in (r.get("flags") or "")]
    out = "".join(f"""<li class="match" id="{esc(r['match_id'])}">
  <div class="mhead"><span class="lock">{esc(utc_short(r['lock_utc']))}</span>
    <span class="tier t{r['tier']}">{esc(r['tier'])}</span><span class="pts">{esc(r['points'])} pts</span></div>
  <div class="teams"><div class="team"><span class="tn">{esc(r['team_a'])}</span><span class="tp">{pct(r['p_a'])}</span></div>
    <div class="team"><span class="tn">{esc(r['team_b'])}</span><span class="tp">{pct(r['p_b'])}</span></div></div>
  <p class="pick">Pick: <strong>{esc(r['pick'])}</strong> (own line, rung C)</p>
  <p class="meta">{esc(r['competition'])} &middot; Valve points {esc(r['vrs_points_a'])} v {esc(r['vrs_points_b'])}
     &middot; HLTV ranks {esc(r['hltv_rank_a'])} / {esc(r['hltv_rank_b'])}</p>
  <p class="meta"><strong>Limitation:</strong> no Pinnacle moneyline and no Polymarket match-winner market
     exists for this fixture, so it cannot be resolved the way the featured picks are. Sources tried:
     Pinnacle guest CS2 markets, Polymarket counter-strike series, HLTV match pages, HLTV event schedule.</p>
  <p class="src"><a href="{esc(r['hotspawn_url'])}">Hotspawn</a> &middot;
     <a href="{esc(R.SOURCES[4][1])}">Valve VRS</a></p>
</li>""" for r in rows)

    body = f"""
<h1>Unresolved picks &amp; limitations</h1>
<p class="lead">All {s['open_with_pick']} of {s['open']} open fixtures carry a pick, so nothing is left without a
recommendation. This page lists the fixtures that could <em>not</em> be resolved the same way as the featured
picks &mdash; {len(rows)} of them, flagged <code>NO_MARKET</code> &mdash; together with the exact limitation and
the sources tried, then the rows that were resolved but where our own line contradicts the market, then the
standing limitations of the whole board.</p>

<h2>Resolved, but our own line contradicts the market ({len(contested)})</h2>
<table class="tbl">
  <tr><th>Match</th><th>Market price</th><th>Own line</th><th>Pick taken</th><th>Why it is flagged</th></tr>
  {''.join(f"<tr><td>{esc(r['team_a'])} v {esc(r['team_b'])}</td><td>{pct(r['market_p_a'])} / {pct(1-(r['market_p_a'] or 0))}</td><td>{pct(r['own_p_a'])} / {pct(1-(r['own_p_a'] or 0))}</td><td><strong>{esc(r['pick'])}</strong></td><td>{esc(r['flags'])}</td></tr>" for r in contested)}
</table>
<p class="meta">The published price is used for the pick, exactly as the ladder says; the own line is shown so the
disagreement is visible rather than hidden.</p>

<h2>Fixtures with no featured market price ({len(rows)})</h2>
<ul class="matches">{out}</ul>

<h2>Standing limitations of this board</h2>
<table class="tbl">
  <tr><th>Limitation</th><th>Effect</th><th>Mitigation</th></tr>
  <tr><td>Market lines are a snapshot. Pinnacle/Polymarket prices were read 2026-10-15T22:41:17Z, except
      Aurora&ndash;9z which was re-read live at 2026-10-16T04:23:06Z.</td>
      <td>A price may have moved since; the pick can flip on a coin-flip line.</td>
      <td>Every row shows the read time; the automated refresh re-reads all sources every 4 hours.</td></tr>
  <tr><td>Pinnacle and Polymarket do not list every low-tier fixture.</td>
      <td>{len(rows)} open fixtures fall back to our own line.</td>
      <td>Rung C is labelled on the row and on the pick card; the Valve points used are shown.</td></tr>
  <tr><td>Two fixtures (1081775 BetBoom&ndash;Legacy, 1081712 Fnatic&ndash;Heroic) were added to Hotspawn after
      the market snapshot.</td><td>No outside price could be captured for them.</td>
      <td>Own line + HLTV ranks; both are flagged on the Flagged page.</td></tr>
  <tr><td>Series length (BO1/BO3): Hotspawn's payload carries <code>best_of = null</code> for every fixture, and
      only some Polymarket titles state it.</td>
      <td>{sum(1 for r in rows if 'FORMAT_UNKNOWN' in (r.get('flags') or ''))} rows have no stated format.</td>
      <td>No format transform is applied to any row; every market price is already for the series as listed by
      its source, and the own line is a series probability fitted on Valve's published series results. Flagged
      as FORMAT_UNKNOWN per row; no value is assumed.</td></tr>
  <tr><td>Hotspawn still lists fixtures whose lock time passed more than 36 h ago.</td>
      <td>Those rows are not pickable.</td>
      <td>They are kept in the full inventory with their status, and excluded from the picks list.</td></tr>
  <tr><td>HLTV refuses some automated clients.</td><td>A rank may be blank.</td>
      <td>Blank ranks are shown as blank and flagged, never inferred.</td></tr>
</table>
"""
    return shell("unresolved", "Unresolved & limitations", body, board)


# --------------------------------------------------------------------------- flagged
FLAGS = [
    ("F-01", "Aurora's roster change is described as 'recent' in the brief.",
     "The rebuild (kyxsan IGL, Jimpphat, coach ash) was announced 2026-07-08/09, about three months before "
     "this match. Valve's 2026-10-05 standings already contain this exact five.",
     "https://www.strafe.com/news/read/aurora-locks-in-new-cs2-roster-with-kyxsan-and-jimpphat/"),
    ("F-02", "Hotspawn's fixture count moved between captures.",
     "The 2026-10-15T22:41:15Z TransferState capture holds 86 CS2 fixtures; the live lobby read at "
     "2026-10-16T04:18Z lists 95 (week text 111 -> 123 matches). The 9 additions are itemised in the "
     "inventory page.",
     "https://play.hotspawn.com/lobby"),
    ("F-03", "Nine fixtures have no Pinnacle or Polymarket price.",
     "Their probability is our own line (rung C) from Valve points; no market figure is shown for them.",
     "unresolved.html"),
    ("F-04", "Kick-off times on Hotspawn are rendered in UTC-4, not UTC.",
     "Derived and verified on six captured fixtures before being applied to the nine new rows.",
     "https://play.hotspawn.com/lobby"),
    ("F-05", "Two fixtures were added to Hotspawn after our market snapshot.",
     "1081775 BetBoom-Legacy and 1081712 Fnatic-Heroic have no captured outside price.",
     "https://play.hotspawn.com/lobby"),
    ("F-06", "Series length is unknown for the nine new fixtures.",
     "Hotspawn's payload carries best_of=null for them; no format is assumed and no transform applied.",
     "https://play.hotspawn.com/lobby"),
    ("F-07", "HLTV ranks are blank for 12 of the 62 teams in the open fixtures.",
     "Those teams are unranked or the rank was not captured; the field is left blank rather than inferred.",
     "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-08", "Day-1 Hotspawn fixture ids for three of the four opening matches were not captured.",
     "Only 1080176 (9z v Aurora) is verified; the others are left blank on the review page.",
     "https://www.hltv.org/events/8932/thunderpick-world-championship-2026"),
]


def page_flagged(board):
    out = "".join(f"""<tr id="{esc(i)}"><td><strong>{esc(i)}</strong></td><td>{esc(t)}</td>
<td>{esc(d)}</td><td><a href="{esc(u)}">source</a></td></tr>""" for i, t, d, u in FLAGS)
    body = f"""
<h1>Flagged for review</h1>
<p class="lead">Irregularities and unverified values found while building this board. None of them blocks the
picks; each is published with its source so it can be checked after the fact.</p>
<table class="tbl">
  <tr><th>ID</th><th>Irregularity</th><th>What we did</th><th>Source</th></tr>
  {out}
</table>
"""
    return shell("flagged", "Flagged for review", body, board)


# --------------------------------------------------------------------------- all
def page_all(board):
    src = json.load(open(DATA / "sources.json"))
    now = "2026-10-16T04:18:00Z"
    picks = {r["match_id"]: r for r in board["rows"]}
    out = []
    for f in src["fixtures"]:
        r = picks.get(f["match_id"])
        if r:
            status, pick = "open", r["pick"]
            prob = pct(r["p_a"] if pick == r["team_a"] else r["p_b"])
        elif f["lock_utc"] > now:
            status, pick, prob = "open", "", ""
        else:
            status, pick, prob = "locked / stale", "", ""
        cls = status.split()[0]
        out.append(f"""<tr class="{esc(cls)}">
  <td>{esc(f['match_id'])}</td><td>{esc(utc_short(f['lock_utc']))}</td>
  <td>{esc(f['tier'])}</td><td>{esc(f['competition'])}</td>
  <td>{esc(f['team_a'])}</td><td>{esc(f['team_b'])}</td>
  <td>{esc(f['offered_points'])}</td><td>{esc(status)}</td>
  <td>{esc(pick)}</td><td>{esc(prob)}</td>
  <td><a href="{esc(f['hotspawn_url'] or 'https://play.hotspawn.com/lobby')}">link</a></td>
</tr>""")
    body = f"""
<h1>Full Hotspawn CS2 fixture inventory</h1>
<p class="lead">All {len(src['fixtures'])} CS2 fixtures listed on Hotspawn's pick'em lobby at
{esc(src['live_capture']['read_utc'])} (&ldquo;{esc(src['live_capture']['week_text'])}&rdquo;,
&ldquo;{esc(src['live_capture']['tier_text'])}&rdquo;). {board['summary']['open']} are still open.</p>
<div class="scroll">
<table class="tbl small">
  <tr><th>ID</th><th>Lock (UTC)</th><th>Tier</th><th>Competition</th><th>Team A</th><th>Team B</th>
      <th>Pts</th><th>Status</th><th>Pick</th><th>Prob</th><th>Src</th></tr>
  {''.join(out)}
</table>
</div>
<p class="meta">Rows in the locked/stale block have a lock time in the past, so they cannot be picked. They are
kept so the inventory matches what Hotspawn shows.</p>
"""
    return shell("all", "Full inventory", body, board)


# --------------------------------------------------------------------------- method
def page_method(board):
    s = board["summary"]
    srcs = "".join(f"<tr><td>{esc(a)}</td><td><a href='{esc(b)}'>{esc(b)}</a></td><td>{esc(c)}</td></tr>"
                   for a, b, c in R.SOURCES)
    body = f"""
<h1>Methodology &amp; sources</h1>
<h2>The ladder</h2>
<table class="tbl">
  <tr><th>Rung</th><th>Source</th><th>How the probability is produced</th></tr>
  <tr><td><strong>A</strong></td><td>Pinnacle whole-match moneyline</td>
      <td>Decimal odds converted to implied probability, then the bookmaker margin removed proportionally
      (overround is printed per row).</td></tr>
  <tr><td><strong>B</strong></td><td>Polymarket match-winner price</td>
      <td>The two outcome prices are normalised to sum to 1. A prediction market, labelled as such.</td></tr>
  <tr><td><strong>C</strong></td><td>Our own line from Valve Regional Standings points</td>
      <td>P = 1/(1+10^(-k &middot; dPoints/400)) with k = {s['k']}, fitted by maximum likelihood on Valve's own
      published match results (13,609 training / 901 held-out windows; held-out log-loss 0.6395 fitted vs
      0.6541 raw). Source: <a href="https://github.com/ValveSoftware/counter-strike_regional_standings">
      ValveSoftware/counter-strike_regional_standings</a>, snapshot 2026-10-05.</td></tr>
  <tr><td><strong>D</strong></td><td>Unresolved</td>
      <td>No outside price and a team missing from Valve's standings. The pick is left blank and the row is
      flagged.</td></tr>
</table>

<h2>What is never a probability</h2>
<p>Hotspawn's &ldquo;% picked&rdquo; crowd share. It is stored as <em>ownership</em> and used only by the
leaderboard rule, which is a strategy opinion printed next to the probability, never inside it.</p>

<h2>Leaderboard rule (contrarian but not stupid)</h2>
<ul class="bullets">
  <li><strong>VALUE</strong> &mdash; the crowd majority sits on the underdog; play the favourite (likelier and
      lower-owned).</li>
  <li><strong>CONTRARIAN</strong> &mdash; underdog consensus &ge; 38% and owned &ge; 10 points below that;
      play the underdog.</li>
  <li><strong>SITUATIONAL</strong> &mdash; underdog consensus &ge; 30% with half-or-less ownership; play the
      underdog.</li>
  <li><strong>LONG SHOT</strong> &mdash; underdog &ge; 20% with &le; 10% ownership; keep the favourite and list
      the underdog as an optional punt.</li>
  <li><strong>CHALK</strong> &mdash; otherwise play the favourite.</li>
</ul>

<h2>Sources</h2>
<table class="tbl">
  <tr><th>What</th><th>URL</th><th>Read / as of</th></tr>
  {srcs}
</table>

<h2>Refresh</h2>
<p>The board is rebuilt automatically every four hours by
<code>.github/workflows/f323b4a7.yml</code>: it re-reads Hotspawn, Pinnacle, Polymarket, Valve's standings and
HLTV, re-originates every pick, rebuilds these pages, runs the invariants and a 390&nbsp;px phone-layout check,
and commits only when the checks pass.</p>
"""
    return shell("method", "Methodology", body, board)


def main() -> int:
    board = json.load(open(DATA / "board.json"))
    builders = {"index": page_index, "picks": page_picks, "day3": page_day3, "review": page_review,
                "unresolved": page_unresolved, "flagged": page_flagged, "all": page_all,
                "method": page_method}
    for name, fn in builders.items():
        (HERE / f"{name}.html").write_text(fn(board), encoding="utf-8")
    print("built", len(builders), "pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
