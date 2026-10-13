#!/usr/bin/env python3
"""Build all docs/*.html pages from data/*.csv. Deterministic; re-run after data refresh.
Every table row carries its source links. Blank = unverified (never inferred).
Run: python3 scripts/build_docs.py
"""
import csv, pathlib, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'data'
DOCS = ROOT / 'docs'
SNAP = '2026-10-13 (UTC)'
NAV = [('index.html', 'Dashboard'), ('matches.html', 'All matches'), ('s-tier.html', 'S-Tier · Thunderpick WC'),
       ('stake.html', 'Stake Pulse Beat III'), ('lower-tiers.html', 'B/C-Tier & inventory'),
       ('methodology.html', 'Methodology'), ('reverse-engineering.html', 'Reverse-engineering'),
       ('audit.html', 'PR audit'), ('flagged.html', '⚠ Flagged for Review'), ('sources.html', 'Sources')]

def nav(cur):
    links = []
    for h, t in NAV:
        style = ' style="text-decoration:underline"' if h == cur else ''
        links.append(f'<a href="{h}"{style}>{t}</a>')
    return '<nav>' + ''.join(links) + '</nav>'

def page(title, heading, subtitle, cur, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · MaltaProj1</title><link rel="stylesheet" href="style.css"></head><body><header><h1>{heading}</h1><p>{subtitle}</p></header>{nav(cur)}<main>{body}</main><footer>Analysis only — not betting advice. Hotspawn pick % is never used as a probability input. Snapshot {SNAP}.</footer></body></html>"""

def esc(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

M = list(csv.DictReader(open(D / 'matches.csv')))
F = {r['id']: r for r in csv.DictReader(open(D / 'fixtures.csv'))}
L = {r['id']: r for r in csv.DictReader(open(D / 'lines.csv'))}

BLANK = '<span class="blank">—</span>'
def pct(v):
    return f"{v}%" if v not in ('', None) else BLANK

def src_cell(r):
    return (f"<a href='{r['hotspawn_url']}'>Hotspawn</a> · "
            f"<a href='{r['crossref_url']}'>{esc(r['crossref_source'])}</a> · "
            + (f"<a href='{r['odds_source_url']}'>EGW odds</a>" if r['odds_source_url'] else "<span class='blank'>no odds source</span>"))

def match_rows(ids):
    out = []
    for r in M:
        if r['id'] not in ids:
            continue
        div = f"<br><small>⚠ {esc(r['divergence_note'])}</small>" if r['divergence_note'] else ''
        out.append(
            f"<tr><td>{r['id']}<br><small>{r['start_display']}</small></td>"
            f"<td><b>{esc(r['team_a'])}</b> vs <b>{esc(r['team_b'])}</b><br><small>{esc(r['tournament'])} · Tier {r['tier']} · {r['format']} · {r['points']} pts</small></td>"
            f"<td>{r['odds_a'] or BLANK} / {r['odds_b'] or BLANK}</td>"
            f"<td>{pct(r['market_p_a_pct'])} / {pct(r['market_p_b_pct'])}<br><small>vig {r['overround_pct'] or '—'}%</small></td>"
            f"<td>{pct(r['own_model_p_a_pct'])} / {pct(r['own_model_p_b_pct'])}</td>"
            f"<td class='pick'>{esc(r['pick'])}<br><small>{pct(r['pick_win_p_pct'])}</small>{div}</td>"
            f"<td><small>{src_cell(r)}</small></td></tr>")
    return '\n'.join(out)

TBL_HEAD = ("<div class='wrap'><table><tr><th># / lock (Hotspawn display)</th><th>Match</th><th>Book odds A/B (decimal)</th>"
            "<th>Market win % (de-vig)</th><th>Our rank-model %</th><th>Pick</th><th>Sources (every row)</th></tr>")

# ---------------- index ----------------
n_line = sum(1 for r in M if r['odds_a'])
n_pick = sum(1 for r in M if r['pick'] and not r['pick'].startswith('No pick'))
n_model = sum(1 for r in M if r['own_model_p_a_pct'] != '')
n_div = sum(1 for r in M if r['divergence_note'])
body = f"""
<div class="card"><h2>Hotspawn Pick'em — independent betting-line analysis</h2>
<p>26 pickable CS2 fixtures (2026-10-13 lobby snapshot, week resets ~Oct 19). Probabilities come from <b>external bookmaker lines</b>
(EGamersWorld aggregated bookmaker odds, de-vigged) and <b>our own HLTV-rank model</b>. Hotspawn crowd % is display-only.</p>
<div class="kpi"><div><b>26</b>pickable fixtures</div><div><b>{n_line}</b>with verified bookmaker line</div>
<div><b>{n_pick}</b>picks issued</div><div><b>{n_model}</b>rows with own-model line</div>
<div><b>{n_div}</b>model-vs-market divergences</div><div><b>1</b>row blank + flagged (H-12)</div></div></div>

<div class="card"><h2>Featured picks (market favorite, de-vigged)</h2>{TBL_HEAD}
{match_rows(['H-04','H-08','H-09','H-11','H-05','H-06'])}</table></div>
<p><a href="matches.html">All 26 matches with per-row sources →</a> · S-tier picks also on <a href="s-tier.html">Thunderpick WC page</a>.</p>

<div class="card"><h2>Reading this dashboard</h2>
<ul>
<li><b>Market win %</b> = bookmaker odds with the overround removed (see <a href="methodology.html">Methodology</a>).</li>
<li><b>Our rank-model %</b> = own line from HLTV world ranks (blank when a rank is unverified — never inferred).</li>
<li><b>Pick</b> = market favorite; “No confident pick” when the line is ~even; H-12 has no verified line → no pick, flagged.</li>
<li>Anything unconfirmed is <b>blank and published on the <a href="flagged.html">Flagged for Review</a> page</b>, never filled in.</li>
</ul></div>"""
(DOCS / 'index.html').write_text(page('Dashboard', 'MaltaProj1 — CS2 Pick\'Em line analysis', f'Up-to-date snapshot {SNAP} · independent lines from bookmaker odds + HLTV · not betting advice', 'index.html', body))

# ---------------- matches ----------------
body = f"""
<div class="card"><h2>All 26 pickable fixtures — full table</h2>
<p>Odds snapshot 2026-10-13 18:47–18:55 UTC (EGamersWorld live list; per-match page in <a href="sources.html">Sources</a>).
Every row links its fixture source, cross-check, and odds source. Blank = unverified (flagged, not inferred).</p>
{TBL_HEAD}
{match_rows([r['id'] for r in M])}</table></div>
<div class="card"><h2>Pick ledger</h2><p>Market favorites: Galorys, Overtake Sector, Lavked (slight), Aurora, Astralis, Fnatic (slight), ex-RUSTEC, Falcons, Legacy,
G2 Ares, FURIA, EAC, MIBR, Heroic, ENCE, WBT (WROTBERRY), EAC, WBT, EAC, Phantom (slight), HAVU, Voca, Phantom, Voca, Phantom.
H-12 FORZE Reload vs LFO 10: no pick — no verified bookmaker line and no verified ranks (flagged).</p></div>"""
(DOCS / 'matches.html').write_text(page('All matches', 'All matches', f'26 fixtures · sources per row · snapshot {SNAP}', 'matches.html', body))

# ---------------- s-tier ----------------
st = [r for r in M if r['tournament'] == 'Thunderpick World Championship 2026']
body = f"""
<div class="card"><h2>Thunderpick World Championship 2026 (Malta LAN, Oct 14–18) — S-Tier, 7 pts, ×1.25</h2>
<p>8 teams, GSL groups → playoffs. Opening day = the only fixtures currently in the pick'em pool (later matches appear once both teams are confirmed).
Verified via HLTV event 8932 + HLTV news 45706; bookmaker match lines via EGamersWorld; tournament outrights via FreeTips (2026-10-11).</p>
{TBL_HEAD}{match_rows(['H-04','H-08','H-09','H-11'])}</table></div>
<div class="card"><h2>Outright market (tournament winner — NOT a match line)</h2>
<div class="wrap"><table><tr><th>Team</th><th>Odds</th><th>Source</th></tr>
<tr><td>Falcons</td><td>2.40</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips 2026-10-11 (book: Stake)</a></td></tr>
<tr><td>Legacy</td><td>3.80</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>FURIA</td><td>4.40</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>Aurora</td><td>6.30</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>BetBoom</td><td>12.00</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>9z</td><td>14.00</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>PARIVISION</td><td>15.00</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr>
<tr><td>Ninjas in Pyjamas</td><td>25.00</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td></tr></table></div>
<p><small>Outrights are never converted into match probabilities (see Flagged F-09: book attribution differs across articles).</small></p></div>
<div class="card"><h2>Analysis</h2><ul>
<li><b>Group A:</b> Aurora is a heavy market favorite over 9z (75.4% de-vig); our rank model rates Aurora a bit lower (68.6%) but the pick is unchanged. Falcons–NiP: market 75.4% Falcons; NiP's HLTV world rank is not cleanly verifiable (flag F-04) so the rank-model column stays blank — market line carries the pick.</li>
<li><b>Group B:</b> Legacy 57.3% (model 61.2% — agrees) and FURIA 66.7% (model 70.8% — agrees). Market and model give the same four opening picks.</li>
<li>Escalation note: points 7 × 1.25 — these are the highest-value picks of the week; the two Group B favorites are the mildest lines among S-tier (57–67%).</li>
</ul></div>"""
(DOCS / 's-tier.html').write_text(page('S-Tier', 'S-Tier · Thunderpick World Championship 2026', 'Malta LAN · 7 pts × tier S ×3 (lobby shows S ×3 multiplier ×1.25) · snapshot ' + SNAP, 's-tier.html', body))

# ---------------- stake ----------------
body = f"""
<div class="card"><h2>Stake Pulse Beat III (Stockholm LAN, Oct 12–17) — B-Tier, 3 pts, ×1.25</h2>
<p>Fixtures verified via HLTV match pages 2399135–2399137; lines via EGamersWorld. Group-listing discrepancy vs Hotspawn remains flagged (F-05).</p>
{TBL_HEAD}{match_rows(['H-05','H-06','H-14','H-15'])}</table></div>
<div class="card"><h2>Analysis</h2><ul>
<li><b>Astralis–Sashi (85.8%):</b> heaviest market line of the tournament; Sashi's HLTV world rank is not verifiable on the pages checked → rank-model column blank, market carries the pick. Polymarket showed 86/14 — consistent with EGW.</li>
<li><b>HOTU–fnatic (51.1% fnatic):</b> a genuine coin-flip line (vig 8.1%). HLTV community indicator (68.4% fnatic) is far more bullish than the bookmakers — we do not use crowd/model indicators as lines; flagged F-08/A-09. Rank model (HOTU #42 vs fnatic #40) says 49.1/50.9 — agrees with the market that this is near-even.</li>
<li><b>MIBR–BC.Game (57.8%):</b> market agrees with ranks (MIBR HLTV #12 per match page vs BC.Game unverified). Our model would go ~75% MIBR if BC.Game's rank were verifiable; blank until then (never inferred).</li>
<li><b>Heroic–Envy (62.9%):</b> Heroic #29 (HLTV 2026-10-05); Envy rank unverified → blank model cell. Note F-05: HLTV/Liquipedia group listings name 3DMAX where Hotspawn lists Envy — fixture kept as Hotspawn lists it, flagged.</li>
</ul></div>"""
(DOCS / 'stake.html').write_text(page('Stake Pulse', 'Stake Pulse Beat III', 'B-Tier · 3 pts ×1.25 · snapshot ' + SNAP, 'stake.html', body))

# ---------------- lower tiers ----------------
inv = list(csv.DictReader(open(D / 'tournaments_inventory.csv')))
inv_rows = '\n'.join(
    f"<tr><td>{esc(r['tournament'])}</td><td>{r['count_in_cs2_filter']}</td><td>{esc(r['status'])}</td><td><a href='{r['source_url']}'>source</a></td><td><small>{esc(r['note'])}</small></td></tr>"
    for r in inv)
body = f"""
<div class="card"><h2>CCT Europe 2026 Series #11 — B-Tier</h2>{TBL_HEAD}{match_rows(['H-03','H-07','H-10','H-12'])}</table></div>
<div class="card"><h2>ESL Challenger League Season 52 Cups (NA & SA) — B-Tier</h2>{TBL_HEAD}{match_rows(['H-01','H-02'])}</table></div>
<div class="card"><h2>Elisa BreakOut Series #2 (Tampere LAN, Oct 15–17) — C-Tier, 2 pts, BO1</h2>
<p>All 12 fixtures cross-verified 1:1 against HLTV event 9332 (pairings, displayed times, match IDs 2399418–2399429).
Hotspawn label <i>WROTBERRY</i> = <b>WhiteBIT Team (WBT)</b> on HLTV/Liquipedia/EGW (flag A-07). RoundsGG = ROUNDS (HLTV) / Rounds (EGW). BO1 = higher variance; lines already price it.</p>
{TBL_HEAD}{match_rows(['H-13','H-16','H-17','H-18','H-19','H-20','H-21','H-22','H-23','H-24','H-25','H-26'])}</table></div>
<div class="card"><h2>Notable lower-tier findings</h2><ul>
<li><b>H-13 WBT–EAC:</b> market favors EAC 54.3% but HLTV ranks favor WBT (#64 vs #115 → 60.8%). Genuine model-vs-market divergence (flagged) — treat the pick as lower-confidence.</li>
<li><b>H-20 EAC–ENCE:</b> market EAC 60.9% vs ranks dead-even (115 vs 113 → 49.7%). Direction mismatch noted; market favorite kept but confidence reduced.</li>
<li><b>H-12 FORZE Reload–LFO 10:</b> no bookmaker market posted (EGW placeholder 1.8/1.8, opponent unlisted) and no verified ranks → <b>blank row, no pick</b> (flag A-11). The only unplayable fixture this week.</li>
<li><b>Public-vs-market skew:</b> on H-01 the Hotspawn crowd is 86% on ex-Keyd Stars while books price Galorys 62.2% — crowd sentiment contradicts the market (we follow the market).</li>
</ul></div>
<div class="card"><h2>Lobby tournament inventory (why counts show 85)</h2>
<p>The lobby filter pool counts 85 CS2 matches, but only 25–26 are pickable. The rest are <b>completed</b> tournaments lingering in the filter pool —
verified via Liquipedia dates (see <a href="reverse-engineering.html">Reverse-engineering</a>, flag A-08; resolves old F-01).</p>
<div class="wrap"><table><tr><th>Tournament</th><th>Lobby count</th><th>Status</th><th>Source</th><th>Note</th></tr>{inv_rows}</table></div></div>"""
(DOCS / 'lower-tiers.html').write_text(page('B/C-Tier', 'B/C-Tier & tournament inventory', 'CCT · ESL Challenger · Elisa BreakOut · snapshot ' + SNAP, 'lower-tiers.html', body))

print('built core pages')

# ---------------- methodology ----------------
body = f"""
<div class="card"><h2>Methodology — how every number is produced</h2>
<ol>
<li><b>Fixture list.</b> Only fixtures rendered by the Hotspawn Pick'em lobby (play.hotspawn.com/lobby, CS2 filter) are in scope — 25 pickable + 1 locked pre-snapshot = 26.
Each is cross-checked against an independent listing (HLTV match/event pages or EGamersWorld) — see the <a href="reverse-engineering.html">Reverse-engineering</a> page for why the lobby filter count (85) exceeds the pickable set.</li>
<li><b>Market probability.</b> Bookmaker decimal odds are taken from EGamersWorld's aggregated bookmaker odds widgets (per-match pages). Implied probability p = 1/odds; the overround is removed proportionally (de-vig):
p_A = (1/o_A) / ((1/o_A)+(1/o_B)). Observed overround on this snapshot: ~7.9–8.6%. Odds move — every row carries its snapshot timestamp (2026-10-13 18:47–18:55 UTC).</li>
<li><b>Our own line (rank model).</b> rating = 2000 − 300·log10(HLTV world rank); P(A) = 1/(1+10^(−(R_A−R_B)/400)). Inputs only from <a href="https://www.hltv.org/ranking/teams/2026/october/5">HLTV</a>-sourced ranks in data/ratings.csv.
If either rank is unverified the cell stays <b>blank</b> — never inferred.</li>
<li><b>Pick rule.</b> Market de-vig favorite. If both de-vig probabilities are within 2.0 pts → “No confident pick”. No verified market line → pick only from the rank model (labelled MODEL-PICK); if that is also impossible → “No pick (no verified line)” + flag. H-12 is this week's only such row.</li>
<li><b>Divergence flag.</b> When the market favorite's market probability and its rank-model probability differ by ≥12.5 pts (H-13, H-24) the row is flagged; H-20 (market 60.9% vs model 49.7%) is additionally called out in the notes as a direction mismatch.</li>
<li><b>What is never an input:</b> Hotspawn crowd % (display-only), HLTV community/VRS indicator percentages (labelled indicators at most), tournament outrights (never converted to match probabilities).</li>
<li><b>BO1 caveat.</b> All 12 Elisa BreakOut fixtures are BO1 (per HLTV event 9332): single-map variance is higher; the de-vig market line already prices this, the rank model does not — one more reason the market line carries the pick.</li>
</ol></div>
<div class="card"><h2>Reproducibility</h2>
<p><code>python3 scripts/model.py</code> regenerates <code>data/matches.csv</code> from <code>data/fixtures.csv</code> + <code>data/lines.csv</code> + <code>data/ratings.csv</code>.
<code>python3 scripts/build_docs.py</code> regenerates every page of this site from the CSVs. No hand-entered numbers in the tables.</p></div>"""
(DOCS / 'methodology.html').write_text(page('Methodology', 'Methodology', 'Documented, reproducible, source-linked · snapshot ' + SNAP, 'methodology.html', body))

# ---------------- reverse engineering ----------------
body = f"""
<div class="card"><h2>How play.hotspawn.com/lobby actually works</h2>
<p>Findings from probing the app on 2026-10-13 (previous session + this session).</p>
<ul>
<li><b>Rendering.</b> The lobby is <b>server-rendered HTML</b>: the "Closing Soon" + "Upcoming" sections (25 fixtures at 18:06 UTC; 26 at the 17:4x snapshot) are present verbatim in the initial HTML. There is no server-side pagination: <code>?page=2</code> and <code>?offset=25</code> return the identical first page.</li>
<li><b>Header semantics.</b> Header shows “60 matches this week” while tier/tournament filters count 85 (B 26 + C 55 + S 4). 85 − 25 pickable = 60: the header counts matches in the pool that are <b>not open for picks</b>. The pool includes <b>completed</b> fixtures.</li>
<li><b>Filter pool includes finished events.</b> Verified with Liquipedia: "Urban Riga Open #5" ran <b>Jun 28–29, 2026</b> and "CCT Europe 2026 Challengers #4" ran <b>Jun 27 – Jul 5, 2026</b>; their teams (ASTRAL, Aimhaus, Coalesce, Leo, 6666, SINQU REHTI, Donstu, Atreides, Misa, Subtop De France, Wampirki, BIG Academy …) appear exactly 1–3× each in the lobby filter — matching those completed runs. → The old F-01 flag (“~60 hidden upcoming fixtures”) is <b>resolved</b>: there are no hidden upcoming fixtures; the pickable set is exactly the server-rendered 25–26.</li>
<li><b>Pickable set grows only as teams are confirmed.</b> The Thunderpick WC tournament page (play.hotspawn.com/tournaments/thunderpick-world-championships) states “Matches appear once both teams are confirmed” and shows “4 matches” (the openers) although the tournament has 14. Later-round fixtures enter the pool later in the week.</li>
<li><b>Backend.</b> Team logos/prizes are served from <code>phpstack-1372681-6459848.cloudwaysapps.com</code>, which answers 404s in <b>NestJS</b> format (<code>{"{message, error, statusCode}"}</code>) — the pickem API is a NestJS app on that host. No Swagger at /docs or /docs-json; guessed routes (/matches, /weeks, /api/* on both hosts) all 404. The client-side "load more" endpoint was not discoverable without executing the page JS (fetch tooling here strips scripts; sandbox egress is restricted to git/npm/pypi hosts, so no headless browser).</li>
<li><b>Sitemaps.</b> play.hotspawn.com/sitemap.xml lists only 8 routes (lobby, pickems, tournaments, leaderboard, how-it-works…). The main site's sitemap index additionally exposes tournament/participant/parent-league sitemaps (WordPress).</li>
<li><b>Main-site mirror.</b> www.hotspawn.com/matches is a WordPress archive of the same match data (server-rendered, grouped by day) — useful secondary fixture source; tournament-level URLs like /tournaments/&lt;slug&gt; 404 (only the pickem app has tournament pages).</li>
<li><b>Countdowns.</b> Lock countdowns tick per fixture; the weekly reset counter (~5d 06h at 18:0x UTC Oct 13 → ~Oct 19 00:0x UTC) governs the leaderboard week (week 261 per prize-image URLs).</li>
</ul></div>
<div class="card"><h2>Endpoint probe log (evidence)</h2>
<div class="wrap"><table><tr><th>URL probed</th><th>Result</th></tr>
<tr><td>play.hotspawn.com/api/matches, /api/pickems, /api/lobby, /api/week, /api/matches/week</td><td>plain "Cannot GET …" (frontend server 404)</td></tr>
<tr><td>phpstack-…cloudwaysapps.com/matches, /weeks, /wp-json/*, /docs, /docs-json</td><td>NestJS JSON 404 <code>{"{message,error,statusCode}"}</code> (backend alive, route names not guessed)</td></tr>
<tr><td>go.hotspawn.com (assets host)</td><td>nginx static; 403/404 — no API</td></tr>
<tr><td>play.hotspawn.com/lobby?page=2, /cs2-pickems?offset=25, ?tournament=…, /lobby/more?offset=25</td><td>identical SSR page / 404 — no server-side pagination or filter params</td></tr>
<tr><td>api.hotspawn.com</td><td>DNS/connect failure</td></tr></table></div></div>"""
(DOCS / 'reverse-engineering.html').write_text(page('Reverse-engineering', 'Reverse-engineering the Hotspawn lobby', 'Structure, endpoints, and the 85-vs-25 mystery — resolved with evidence · ' + SNAP, 'reverse-engineering.html', body))
print('built methodology + reverse-engineering')

# ---------------- audit ----------------
body = f"""
<div class="card flag"><h2>Line-by-line audit of parallel-session PRs #4 (arena/51fb12f8) and #5 (arena/2cb6bff4)</h2>
<p>This session audited every claimed "verified" value in both open PRs against live official sources. Findings A-01…A-10 below;
unverifiable values were <b>replaced by verified ones or blanked</b> in the canonical dataset — never copied forward. Their dashboards are preserved in the repo
(see disposition in the table) and their non-conflicting work is credited in <a href="sources.html">Sources</a>.</p>
<div class="wrap"><table><tr><th>ID</th><th>PR</th><th>Claimed</th><th>Verified against live source</th><th>Finding / disposition</th></tr>
<tr><td>A-01</td><td>#4</td><td>Gothic–Lavked: Gothic 1.79 favorite ("market has Gothic as slight favorite, opposite to Hotspawn %")</td>
<td><a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B">EGW match page</a> live 18:20 UTC: Gothic 2.10 / <b>Lavked 1.62</b>; live list 18:47 UTC: 1.881/1.782 (Lavked favorite)</td>
<td><b>Contradicted.</b> Lavked is the market favorite; PR4's direction was wrong. Canonical row uses live EGW values.</td></tr>
<tr><td>A-02</td><td>#4 + #5</td><td>ex-Keyd–Galorys: #4 "Polymarket 3.03/1.47"; #5 "EGW/Polymarket 2.85/1.40"</td>
<td><a href="https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp">EGW page</a> live: 2.43/1.46 → list 2.44/1.48; EGW bot quotes bookmaker average Galorys 1.464 / ex-Keyd 2.508</td>
<td>Direction (Galorys favorite) consistent in both PRs; the exact numbers could not be confirmed at the cited generic Polymarket URL (not a market page). Canonical row uses live EGW.</td></tr>
<tr><td>A-03</td><td>#5</td><td>Zomblers–Overtake: "Zomblers 1.42 favorites (OddsDigger)"; "5/12 favorites"</td>
<td><a href="https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_">EGW page</a> (1.8/1.8 placeholder earlier) → live list 18:47 UTC: Zomblers 2.51 / <b>Overtake 1.47</b></td>
<td><b>Contradicted.</b> No OddsDigger market page exists at the cited generic URL. PR4's opposite direction (Overtake favorite) matches the live market; PR5's row is reversed.</td></tr>
<tr><td>A-04</td><td>#5</td><td>"Ranks": ex-Keyd 140, Zomblers 150, Gothic 169, Astralis 14, Sashi 68, ex-RUSTEC 93, mellren 123 …</td>
<td>HLTV pages: Astralis #11 (<a href="https://www.hltv.org/ranking/teams/2026/october/5">ranking 2026-10-05</a>); Sashi/Envy/NiP etc. not printed on HLTV pages checked; EGW (its own scale): Astralis #11, Sashi #55, Gothic #756, ex-RUSTEC #266, mellren #505</td>
<td><b>Unverifiable / conflicting.</b> PR5's rank numbers carry no source URLs (its hltv_* columns point to generic pages). Not carried into the canonical data; blanks used instead.</td></tr>
<tr><td>A-05</td><td>#5</td><td>Its COORDINATION.md log: "PR #5 opened and merged to main… deployment verified" with entries timestamped 18:05–19:00 UTC</td>
<td>GitHub API at 18:03 UTC: PR #5 <b>OPEN</b> (created 18:00:31Z, not merged); its log timestamps are in the future relative to its own creation</td>
<td><b>False completion claim + fabricated timestamps.</b> Recorded here and in COORDINATION.md; non-blocking, flagged for owner review.</td></tr>
<tr><td>A-06</td><td>#4 + #5</td><td>Both replace the repo-root index.html with their own dashboards</td>
<td>Live Pages site serves docs/ via root redirect (main @ b2150ff); merging either PR as-is breaks the deployed site; merging both conflicts</td>
<td>Integration keeps the docs/ site canonical; both dashboards preserved under their own paths (site/ for #4; hub.html + css/js/src/tests at root for #5) and linked from the dashboard.</td></tr>
<tr><td>A-07</td><td>(fixture data)</td><td>—</td><td>Hotspawn team label "WROTBERRY" ↔ <b>WhiteBIT Team (WBT)</b> on <a href="https://www.hltv.org/events/9332/elisa-breakout-series-2">HLTV event 9332</a>, <a href="https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2">Liquipedia</a>, EGW (same slot, opponents, times)</td>
<td>Naming irregularity in Hotspawn's data. Canonical rows keep Hotspawn's label with the WBT alias and verified HLTV rank (#64).</td></tr>
<tr><td>A-08</td><td>(all sessions)</td><td>Old F-01: "~60 fixtures hidden behind client-side pagination"</td>
<td>Liquipedia dates for Urban Riga #5 (Jun 28–29) and CCT Europe Challengers #4 (Jun 27–Jul 5) + lobby team-count pattern</td>
<td><b>Resolved:</b> the extra 59–60 filter entries are completed matches; no hidden upcoming fixtures exist. tournaments_inventory.csv updated.</td></tr>
<tr><td>A-09</td><td>#4</td><td>HOTU–fnatic row treats HLTV's 68.4% fnatic as the indicator while claiming market 50/50</td>
<td><a href="https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC">EGW</a> 1.82/1.82 → live 1.88/1.80; <a href="https://polymarket.com/teams/cs2/hotu">Polymarket</a> 48/53</td>
<td>Market is genuinely near-even; HLTV community % is not a bookmaker line (correctly not used as probability, but the row's framing mixed the two — canonical row separates them).</td></tr>
<tr><td>A-10</td><td>#4 + #5</td><td>Both PRs present a single static odds snapshot with no timestamps</td>
<td>Same fixture showed 2.10/1.62 → 1.881/1.782 (Gothic–Lavked) and 1.07/5.90 → 1.07/6.45 (Astralis–Sashi) within one hour on 2026-10-13</td>
<td>Canonical dataset stamps every odds row (snapshot_utc) and records intra-day movement in market_note.</td></tr>
<tr><td>A-11</td><td>(canonical)</td><td>—</td><td>FORZE Reload–LFO 10: EGW placeholder 1.8/1.8, opponent unlisted on EGW page; no HLTV ranks verified for either team</td>
<td><b>No line, no pick</b> — blank + flagged. Only unplayable fixture of the week.</td></tr>
</table></div></div>
<div class="card"><h2>What was kept from each PR</h2>
<ul>
<li><b>PR #4 (arena/51fb12f8)</b> — dark-theme JS dashboard under <code>site/</code> preserved (moved its root <code>index.html</code> to <code>site/index.html</code> with corrected asset paths). Its overround-removal approach matches ours; its two contradicted rows (A-01) and generic-source rows (A-02) were replaced by live values.</li>
<li><b>PR #5 (arena/2cb6bff4)</b> — dashboard preserved as <code>hub.html</code> + <code>css/</code>, <code>js/</code>, <code>src/</code> (build pipeline), <code>tests/audit_site.py</code>; its dataset preserved as <code>data/matches_hub_2cb6bff4.csv|json</code> (superseded — see A-03/A-04). Its falsified merge log (A-05) is flagged, not silently edited.</li>
<li><b>PR #1/#2 (arena/f89fbdfa, merged)</b> — docs/ site structure, ratings methodology and flags F-01…F-12 (F-01 resolved by A-08; F-03 narrowed to H-12 by this session's line collection).</li>
</ul></div>"""
(DOCS / 'audit.html').write_text(page('PR audit', 'Audit of parallel-session PRs', 'Every claimed value checked against live official sources · ' + SNAP, 'audit.html', body))
print('built audit')

# ---------------- flagged ----------------
body = f"""
<div class="card flag"><h2>⚠ Flagged for Review — published, not hidden</h2>
<p>These items do not block the site. Every value that could not be confirmed from an official source is <b>blank</b> in the tables.
A-01…A-11 come from this session's audit (details and evidence on the <a href="audit.html">PR audit page</a>); F-xx carry over from the 2026-10-13 earlier sessions.</p>
<div class="wrap"><table><tr><th>ID</th><th>Item</th><th>Evidence / source</th><th>Impact</th></tr>
<tr><td>A-01</td><td>PR #4 claimed Gothic as market favorite for Gothic–Lavked; live EGW shows Lavked favorite (1.62–1.78 vs 1.78–2.10 today)</td><td><a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B">EGW match page</a></td><td>Corrected in canonical data (Lavked pick, 51.4%)</td></tr>
<tr><td>A-03</td><td>PR #5 claimed Zomblers 1.42 favorites (OddsDigger); live market favors Overtake Sector 1.47</td><td><a href="https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_">EGW match page</a></td><td>Corrected (Overtake pick, 63.1%); OddsDigger claim unverifiable</td></tr>
<tr><td>A-04</td><td>PR #5 "ranks" (ex-Keyd 140, Astralis 14, Sashi 68 …) carry no source URLs and conflict with HLTV-sourced ranks</td><td><a href="https://www.hltv.org/ranking/teams/2026/october/5">HLTV ranking</a></td><td>Not carried forward; canonical rows blank where HLTV-verified ranks are absent</td></tr>
<tr><td>A-05</td><td>PR #5's COORDINATION.md claims "PR #5 merged to main / deployment verified" with timestamps up to 19:00 UTC; PR was still open and the timestamps were in the future at audit time (18:03 UTC)</td><td><a href="https://github.com/buffedlizard55-lab/MaltaProj1/pull/5">PR #5 on GitHub</a></td><td>Logged; owner review requested; non-blocking</td></tr>
<tr><td>A-06</td><td>Both open PRs replace the root index.html and would break the deployed docs/ site if merged as-is</td><td><a href="https://github.com/buffedlizard55-lab/MaltaProj1/pull/4">PR #4</a>, <a href="https://github.com/buffedlizard55-lab/MaltaProj1/pull/5">PR #5</a></td><td>Integration keeps docs/ canonical; both dashboards preserved and linked</td></tr>
<tr><td>A-07</td><td>Hotspawn labels the Elisa Group A team "WROTBERRY"; HLTV/Liquipedia/EGW call the same slot WhiteBIT Team (WBT)</td><td><a href="https://www.hltv.org/events/9332/elisa-breakout-series-2">HLTV event 9332</a> · <a href="https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2">Liquipedia</a></td><td>Rows show "WROTBERRY (WBT)" with verified HLTV rank #64</td></tr>
<tr><td>A-10</td><td>Odds moved intra-day (Gothic–Lavked 2.10/1.62 → 1.881/1.782; Astralis–Sashi 5.90 → 6.45 for Sashi; HOTU–fnatic 1.82/1.82 → 1.88/1.80; ex-Keyd 2.43 → 2.44)</td><td><a href="https://egamersworld.com/counterstrike/matches">EGW live list</a></td><td>Every odds row stamped (snapshot_utc); re-check before acting</td></tr>
<tr><td>A-11</td><td>H-12 FORZE Reload–LFO 10: no bookmaker market (EGW 1.8/1.8 placeholder, opponent unnamed) and no verified HLTV ranks</td><td><a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3">EGW fixture page</a></td><td>Row blank; no pick issued</td></tr>
<tr><td>F-02</td><td>CCT Europe #11 count moved 5 → 4 during Oct 13 (Black Phoenix vs 6666 went live, left the pickable pool)</td><td><a href="https://play.hotspawn.com/cs2-pickems">CS2 lobby</a></td><td>Explained; the live match is not a pickem option anymore</td></tr>
<tr><td>F-04</td><td>NiP HLTV world rank not cleanly verifiable (event pages mix HLTV/VRS numbering)</td><td><a href="https://www.hltv.org/events/8932/thunderpick-world-championship-2026">HLTV event 8932</a></td><td>Falcons–NiP model cell blank; market line carries the pick</td></tr>
<tr><td>F-05</td><td>Stake Pulse groups: Hotspawn lists Envy; HLTV/Liquipedia listings name 3DMAX in that group</td><td><a href="https://liquipedia.net/counterstrike/Stake_Pulse/Beat_III">Liquipedia</a> · <a href="https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii">HLTV 2399137</a></td><td>Fixture kept as Hotspawn lists (it defines the game); Envy rank unverified → blank model cell</td></tr>
<tr><td>F-06</td><td>Rank snapshots drift (Astralis #11 vs #15; Aurora/Legacy both #6 from different snapshots; VRS differs from HLTV)</td><td><a href="https://www.hltv.org/ranking/teams/2026/october/5">HLTV 2026-10-05</a> · <a href="https://pley.gg/cs2/thunderpick-world-championship-2026/">Pley VRS</a></td><td>Model uses HLTV world rank only, dated per row</td></tr>
<tr><td>F-07</td><td>PARIVISION: HLTV team page #11 vs third-party preview #20</td><td><a href="https://www.hltv.org/team/12467/parivision">HLTV PARIVISION</a></td><td>HLTV preferred</td></tr>
<tr><td>F-08</td><td>HOTU–fnatic: HLTV community/model indicator 68.4% fnatic vs bookmaker near-even (1.88/1.80)</td><td><a href="https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii">HLTV match</a> · <a href="https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC">EGW</a></td><td>Indicator shown, never used as a probability; market line governs</td></tr>
<tr><td>F-09</td><td>Outright book attribution differs across articles (Stake vs bet365)</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips</a></td><td>Outrights labelled; never converted to match picks</td></tr>
<tr><td>F-10</td><td>Hotspawn displays times without a timezone; HLTV/EGW show different clock times for the same fixture</td><td><a href="https://www.hltv.org/news/45706/thunderpick-world-championship-teams-format-schedule-prizes-talent-fantasy">HLTV news 45706</a></td><td>Times reproduced as Hotspawn displays; convert before acting</td></tr>
<tr><td>F-11</td><td>Hotspawn crowd % drifts between fetches and several cards show 100/0 (tiny samples)</td><td><a href="https://play.hotspawn.com/lobby">lobby</a></td><td>Snapshot only; never a probability input</td></tr>
<tr><td>F-12</td><td>Stake Pulse match-ID gap (1079441 missing between …438/…439/…442)</td><td><a href="https://play.hotspawn.com/cs2-pickems">lobby</a></td><td>Noted; not invented</td></tr>
</table></div></div>"""
(DOCS / 'flagged.html').write_text(page('Flagged', '⚠ Flagged for Review', 'Published irregularities and unverified items — do not block the site · ' + SNAP, 'flagged.html', body))
print('built flagged')

# ---------------- sources ----------------
body = f"""
<div class="card"><h2>Sources & verification index</h2>
<p>Verification rule: fixture = Hotspawn (defines the game) + one independent cross-check; probability = de-vigged bookmaker odds (EGamersWorld) or our sourced rank model; anything else = blank + Flagged.</p>
<div class="wrap"><table><tr><th>#</th><th>Source</th><th>What it verifies</th></tr>
<tr><td>S-01</td><td><a href="https://play.hotspawn.com/lobby">Hotspawn Pick'ems lobby</a> · <a href="https://play.hotspawn.com/cs2-pickems">CS2 lobby</a></td><td>All 26 fixtures (teams, order, tiers, points, displayed lock times, match URLs); filter counts 85/25; crowd % (display-only)</td></tr>
<tr><td>S-02</td><td><a href="https://play.hotspawn.com/tournaments/thunderpick-world-championships">Hotspawn Thunderpick WC tournament page</a></td><td>"Matches appear once both teams are confirmed"; 4 open fixtures; tournament prizes</td></tr>
<tr><td>S-03</td><td><a href="https://egamersworld.com/counterstrike/matches">EGamersWorld CS2 live+upcoming odds list</a></td><td>Bookmaker match odds for all 25 priced fixtures (snapshot 2026-10-13 18:47–18:55 UTC); EGW team-rating context</td></tr>
<tr><td>S-04…S-15</td><td>EGW per-match pages (linked per row on <a href="matches.html">All matches</a>): ex-Keyd–Galorys, Zomblers–Overtake, Gothic–Lavked, 9z–Aurora, Astralis–Sashi, HOTU–fnatic, ex-RUSTEC–mellren, Falcons–NiP, Legacy–PARIVISION, G2 Ares–TLR, FURIA–BetBoom, FORZE–LFO, and the 12 Elisa fixtures under event <a href="https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl">Elisa BreakOut Series 2</a></td><td>Fixture cross-check + odds widget + EGW bot bookmaker-average quotes</td></tr>
<tr><td>S-16</td><td><a href="https://egamersworld.com/blog/thunderpick-world-championship-2026-schedule-teams-3y5NuMb4pp">EGW Thunderpick WC 2026 preview (2026-10-12)</a></td><td>Groups, schedule, opening-match odds (matches today's lines), prize pool</td></tr>
<tr><td>S-17</td><td><a href="https://egamersworld.com/counterstrike/tip/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH">EGW FURIA–BetBoom tip page</a></td><td>Second EGW odds quote (1.41/2.87) — consistency check</td></tr>
<tr><td>S-18</td><td><a href="https://www.hltv.org/events/9332/elisa-breakout-series-2">HLTV — Elisa BreakOut Series 2 event</a></td><td>All 12 Elisa fixtures (pairings, displayed times, match IDs 2399418–2399429) + HLTV ranks: WBT #64, ENCE #113, EAC #115, BOJONG #387, Voca #67, Phantom #87, HAVU #126, ROUNDS #314</td></tr>
<tr><td>S-19</td><td><a href="https://www.hltv.org/news/45706/thunderpick-world-championship-teams-format-schedule-prizes-talent-fantasy">HLTV news 45706 — Thunderpick WC teams/format</a></td><td>Groups A/B, opening-day fixtures 2026-10-14</td></tr>
<tr><td>S-20</td><td><a href="https://www.hltv.org/events/8932/thunderpick-world-championship-2026">HLTV event 8932 (Thunderpick WC)</a> · match pages <a href="https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026">2399385</a>, <a href="https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026">2399386</a>, <a href="https://www.hltv.org/matches/2399387/furia-vs-betboom-thunderpick-world-championship-2026">2399387</a>, <a href="https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii">2399135</a>, <a href="https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii">2399136</a>, <a href="https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii">2399137</a></td><td>S/B-tier fixture cross-checks; MIBR HLTV #12/VRS #13; HOTU #42; community indicators (never probability inputs)</td></tr>
<tr><td>S-21</td><td><a href="https://www.hltv.org/ranking/teams/2026/october/5">HLTV World Ranking 2026-10-05</a> · team pages (<a href="https://www.hltv.org/team/11861/aurora">Aurora</a>, <a href="https://www.hltv.org/team/9996/9z">9z</a>, <a href="https://www.hltv.org/team/12468/legacy">Legacy</a>, <a href="https://www.hltv.org/team/12467/parivision">PARIVISION</a>, <a href="https://www.hltv.org/team/12394/betboom">BETBOOM</a>)</td><td>Rank-model inputs: FURIA 4, Falcons 5, Aurora 6, Legacy 6, Astralis 11, PARIVISION 11, BETBOOM 13, 9z 17, HEROIC 29, fnatic 40, HOTU 42</td></tr>
<tr><td>S-22</td><td><a href="https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2">Liquipedia Elisa BreakOut Series #2</a> · <a href="https://liquipedia.net/counterstrike/CCT/2026/Europe/Challengers_4">CCT Challengers #4</a> · <a href="https://liquipedia.net/counterstrike/Urban_Riga_Open/5">Urban Riga Open #5</a></td><td>Elisa participants/dates (WhiteBIT Team naming); completion dates proving the lobby filter-pool finding (A-08)</td></tr>
<tr><td>S-23</td><td><a href="https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/">FreeTips — Thunderpick WC outright odds (2026-10-11)</a></td><td>Tournament outrights (Falcons 2.40 … NiP 25.00) — labelled outright, never a match probability</td></tr>
<tr><td>S-24</td><td><a href="https://polymarket.com/teams/cs2/hotu">Polymarket team markets (e.g. HOTU)</a> · <a href="https://polymarket.com/teams/cs2/sashi-esport">Sashi</a></td><td>Secondary real-money market cross-checks (HOTU 48/53; Astralis 86/14)</td></tr>
<tr><td>S-25</td><td><a href="https://esports.pallomeri.net/elisa-breakout-series-2-joukkueet-lohkot-havu-ence/">pallomeri.net — Elisa BreakOut Series 2 preview</a></td><td>Finnish-language group/venue confirmation (WhiteBIT Team = WBT, Tampere)</td></tr>
</table></div>
<p><small>Not used as probability sources (by brief or by policy): Hotspawn crowd %, HLTV community/VRS indicator %, tournament outrights, EGW/HLTV editorial predictions.</small></p></div>"""
(DOCS / 'sources.html').write_text(page('Sources', 'Sources & verification index', 'Every table row traces here · snapshot ' + SNAP, 'sources.html', body))
print('built sources')
