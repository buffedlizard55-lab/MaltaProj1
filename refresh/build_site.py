#!/usr/bin/env python3
"""R-02 site builder — renders today/** (mobile-first, dependency-free) from refresh/data/.

Every published row carries at least one link to the official page the value came from, and any
value that could not be sourced is rendered as "—" together with its flag chip.
"""
from __future__ import annotations

import csv
import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "refresh" / "data"
OUT = ROOT / "today"

ELO_SCALE = 400.0   # documented standard Elo logistic scale used by the own-line model

SPORT_LABEL = {"cs2": "CS2", "counterstrike": "CS2", "cs": "CS2",
               "lol": "LoL", "leagueoflegends": "LoL"}

FLAG_TEXT = {
    "no_bookmaker_price_found": "No bookmaker price found on the external source",
    "no_external_match_page_matched": "No external match page matched this fixture",
    "single_bookmaker": "Only one bookmaker price readable",
    "single_reading_widget_price": "Single headline price reading (no bookmaker table parsed)",
    "overround_below_1_check_source": "Overround below 100% — check the source reading",
    "odds_pair_order_reversed_vs_hotspawn": "External page lists the teams in the other order; "
                                            "prices were swapped to match Hotspawn's order",
    "market_only_no_own_line": "No own-line rating for both teams; estimate is market-only",
    "own_line_only_no_market": "No external bookmaker price; estimate is our own line only",
    "no_probability_available": "Neither a bookmaker price nor a rating line could be sourced",
}


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def pct(value) -> str:
    return "—" if value is None else f"{value:.1f}%"


def bar(a, b) -> str:
    if a is None or b is None:
        return '<div class="bar empty"><span>—</span></div>'
    return (f'<div class="bar" role="img" aria-label="{a:.1f}% vs {b:.1f}%">'
            f'<span class="a" style="width:{a:.1f}%">{a:.1f}%</span>'
            f'<span class="b" style="width:{b:.1f}%">{b:.1f}%</span></div>')


def pick_badge(row) -> str:
    if not row.get("pick"):
        return '<span class="chip warn">no pick</span>'
    state = "locked" if row.get("locked") else "open"
    return (f'<span class="pick {state}">{esc(row["pick"])}</span>'
            f'<span class="muted small">{pct(row.get("pick_pct"))}</span>')


def flag_chips(flags: list[str]) -> str:
    out = []
    for flag in flags or []:
        label = FLAG_TEXT.get(flag, flag)
        if flag.endswith("_rating_missing:"):
            pass
        out.append(f'<span class="chip warn" title="{esc(label)}">{esc(short_flag(flag))}</span>')
    return " ".join(out) or '<span class="chip ok">verified inputs</span>'


def short_flag(flag: str) -> str:
    if flag.startswith("hltv_rating_missing"):
        return "no HLTV rating: " + flag.split(":", 1)[1]
    if flag.startswith("vrs_rating_missing"):
        return "no VRS rating: " + flag.split(":", 1)[1]
    if flag.startswith("hltv:alias:"):
        return "alias used (HLTV)"
    if flag.startswith("vrs:alias:"):
        return "alias used (VRS)"
    return FLAG_TEXT.get(flag, flag)[:48]


def source_links(row) -> str:
    links = []
    if row.get("hotspawn_url"):
        links.append(f'<a href="{esc(row["hotspawn_url"])}" rel="noopener">Hotspawn</a>')
    elif row.get("hotspawn_page"):
        links.append(f'<a href="{esc(row["hotspawn_page"])}" rel="noopener">Hotspawn</a>')
    for entry in row.get("market_sources") or []:
        if entry.get("url"):
            label = "Pinnacle" if "Pinnacle" in entry["source"] else "EGamersWorld"
            links.append(f'<a href="{esc(entry["url"])}" rel="noopener">{label} odds</a>')
    for entry in row.get("model_inputs") or []:
        if entry.get("url"):
            label = "HLTV rank" if "HLTV" in entry["source"] else "Valve VRS"
            links.append(f'<a href="{esc(entry["url"])}" rel="noopener">{label}</a>')
    return " · ".join(dict.fromkeys(links)) or "—"


NAV = [
    ("index.html", "Dashboard"),
    ("matches.html", "All matches"),
    ("cs2.html", "CS2"),
    ("lol.html", "LoL"),
    ("tournaments.html", "Tournaments"),
    ("by-tier.html", "Tiers"),
    ("odds.html", "Bookmaker lines"),
    ("ratings.html", "Team ratings"),
    ("methodology.html", "Method"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
    ("repo-review.html", "Repo review"),
]

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--panel2:#1c2330;--ink:#e6edf3;--muted:#8b949e;
--line:#2d333b;--accent:#3fb950;--accent2:#58a6ff;--warn:#d29922;--bad:#f85149;}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent2)}
header.top{position:sticky;top:0;z-index:5;background:rgba(13,17,23,.96);
border-bottom:1px solid var(--line);backdrop-filter:blur(6px)}
.top-in{max-width:1180px;margin:0 auto;padding:10px 14px}
.brand{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.brand h1{font-size:16px;margin:0}
.brand .stamp{color:var(--muted);font-size:12px}
nav.pages{display:flex;gap:6px;overflow-x:auto;padding:8px 0 2px;scrollbar-width:thin}
nav.pages a{white-space:nowrap;padding:6px 10px;border:1px solid var(--line);border-radius:999px;
font-size:13px;text-decoration:none;color:var(--ink)}
nav.pages a.active{background:var(--accent2);border-color:var(--accent2);color:#04121f;font-weight:600}
main{max-width:1180px;margin:0 auto;padding:14px}
h2{font-size:18px;margin:22px 0 8px}
h3{font-size:15px;margin:18px 0 6px;color:var(--ink)}
p,li{color:#c9d1d9}
.muted{color:var(--muted)}
.small{font-size:12px}
.grid{display:grid;gap:10px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:10px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.card .v{font-size:20px;font-weight:600}
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);
border-radius:10px;background:var(--panel)}
table{border-collapse:collapse;width:100%;min-width:820px}
th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;
font-size:13.5px}
th{background:var(--panel2);position:sticky;top:0;font-size:12px;text-transform:uppercase;
letter-spacing:.04em;color:var(--muted)}
tbody tr:hover{background:#1b2230}
.bar{display:flex;height:22px;border-radius:6px;overflow:hidden;background:#0b0f14;min-width:150px;
border:1px solid var(--line)}
.bar span{display:flex;align-items:center;justify-content:center;font-size:11.5px;
font-weight:600;color:#04121f;white-space:nowrap;overflow:hidden}
.bar .a{background:var(--accent)}
.bar .b{background:#7d8590}
.bar.empty span{width:100%;background:#2d333b;color:var(--muted)}
.pick{display:inline-block;padding:2px 8px;border-radius:999px;font-weight:700;font-size:12.5px;
background:var(--accent);color:#04121f}
.pick.locked{background:#7d8590}
.chip{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11.5px;
border:1px solid var(--line);color:var(--muted)}
.chip.warn{border-color:var(--warn);color:var(--warn)}
.chip.ok{border-color:#2ea043;color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:4px}
.tag{font-size:11.5px;color:var(--muted)}
.tier{display:inline-block;min-width:20px;text-align:center;border-radius:4px;padding:0 5px;
background:var(--panel2);border:1px solid var(--line);font-size:11.5px}
.note{background:var(--panel);border-left:3px solid var(--accent2);padding:10px 12px;
border-radius:0 8px 8px 0;margin:12px 0}
.warnbox{border-left-color:var(--warn)}
footer{max-width:1180px;margin:0 auto;padding:18px 14px 40px;color:var(--muted);font-size:12px}
.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}
.toolbar input,.toolbar select{background:var(--panel);color:var(--ink);border:1px solid var(--line);
border-radius:8px;padding:7px 9px;font-size:13px}
.toolbar label{font-size:12px;color:var(--muted)}
@media (max-width:720px){
  table{min-width:0}
  thead{display:none}
  tbody tr{display:block;border-bottom:1px solid var(--line);padding:8px 10px}
  tbody td{display:grid;grid-template-columns:96px 1fr;gap:8px;border:0;padding:3px 0}
  tbody td::before{content:attr(data-label);color:var(--muted);font-size:11.5px;
  text-transform:uppercase;letter-spacing:.03em}
  .bar{min-width:0}
  .tablewrap{border-radius:8px}
}
"""

JS = """
document.querySelectorAll('[data-filter]').forEach(function(el){
  el.addEventListener('input', function(){ apply(); });
});
function apply(){
  var q=(document.getElementById('q')||{}).value||'';
  var tour=(document.getElementById('tournament')||{}).value||'';
  var sport=(document.getElementById('sport')||{}).value||'';
  var onlyMissing=document.getElementById('missing')&&document.getElementById('missing').checked;
  q=q.toLowerCase();
  document.querySelectorAll('tbody tr').forEach(function(tr){
    var text=(tr.dataset.search||'');
    var ok=!q||text.indexOf(q)>=0;
    if(tour) ok=ok&&tr.dataset.tournament===tour;
    if(sport) ok=ok&&tr.dataset.sport===sport;
    if(onlyMissing) ok=ok&&tr.dataset.missing==='1';
    tr.style.display=ok?'':'none';
  });
  var shown=0;document.querySelectorAll('tbody tr').forEach(function(tr){
    if(tr.style.display!=='none')shown++;});
  var out=document.getElementById('count');if(out)out.textContent=shown+' rows shown';
}
function localise(){
  var opts={month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'};
  document.querySelectorAll('time[data-utc]').forEach(function(t){
    var d=new Date(t.dataset.utc);
    if(!isNaN(d)) t.textContent=d.toLocaleString(undefined,opts);
  });
}
document.addEventListener('DOMContentLoaded',function(){localise();apply();});
"""

LOCAL_TIME_JS = """
document.querySelectorAll('time[data-utc]').forEach(function(t){
  var d = new Date(t.dataset.utc);
  if (isNaN(d)) return;
  var shown = t.dataset.show || 'both';
  var local = d.toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',
    minute:'2-digit',timeZoneName:'short'});
  t.innerHTML = '<span class="muted">local</span> ' + local +
    (shown === 'both' ? ' <span class="muted">· UTC</span> ' +
      t.dataset.utc.replace('T',' ').replace('Z','') : '');
});
"""


def page(filename: str, title: str, body: str, stamp: str, subtitle: str = "") -> str:
    nav = "".join(
        '<a href="%s"%s>%s</a>' % (href, ' class="active"' if href == filename else "",
                                   esc(label))
        for href, label in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Hotspawn Pick'em line board</title>
<meta name="description" content="Source-linked win probabilities and picks for the CS2/LoL matches in the Hotspawn Play Pick'em, built from external bookmaker lines and official rating data.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top"><div class="top-in">
  <div class="brand">
    <h1>Hotspawn Pick'em — line board</h1>
    <span class="stamp">data snapshot {esc(stamp)} UTC · <span id="count"></span></span>
  </div>
  <nav class="pages">{nav}</nav>
</div></header>
<main>
<h2>{esc(title)}</h2>
{f'<p class="muted">{subtitle}</p>' if subtitle else ''}
{body}
</main>
<footer>
  <p><strong>Not betting advice.</strong> Probabilities are derived from third-party bookmaker
  prices (de-vigged) and from published rating points, each linked per row. Hotspawn Play is used
  only to identify which matches are in the Pick'em and when they lock; Hotspawn's crowd
  percentages are not collected into this dataset and never influence a probability or a pick.</p>
  <p>Values that could not be confirmed from an official page are shown as “—” and listed on the
  <a href="flagged.html">Flagged for review</a> page. Generated automatically — no manual input.</p>
</footer>
<script>{JS}</script>
<script>{LOCAL_TIME_JS}</script>
</body>
</html>
"""


def match_row(row: dict) -> str:
    missing = "1" if (row.get("market_p_a_pct") is None or row.get("own_model_p_a_pct") is None) \
        else "0"
    status = []
    if row.get("started"):
        status.append('<span class="chip">started</span>')
    elif row.get("locked"):
        status.append('<span class="chip">locked</span>')
    else:
        status.append('<span class="chip ok">open</span>')
    books = row.get("odds_bookmakers") or []
    sources = row.get("market_sources") or []
    return f"""<tr data-search="{esc((row['team_a'] + ' ' + row['team_b'] + ' ' + (row['competition'] or '')).lower())}" data-tournament="{esc(row.get('competition') or '')}" data-sport="{esc(row.get('sport') or '')}" data-missing="{missing}">
<td data-label="Match"><strong>{esc(row['team_a'])}</strong> <span class="muted">vs</span> <strong>{esc(row['team_b'])}</strong>
  <div class="tag"><span class="tier">{esc(row.get('tier') or '–')}</span> {esc(row.get('competition') or '')}{f" · {esc(row['points'])} pts" if row.get('points') else ''}
  {f" · {esc(row['best_of'])}" if row.get('best_of') else ''}</div></td>
<td data-label="Start (UTC)"><time data-utc="{esc(row['start_utc'])}">{esc(row['start_utc'])}</time>
  <div class="tag">lock {esc((row.get('lock_utc') or '—'))}{' · ' if row.get('lock_utc') else ''}{' '.join(status)}</div></td>
<td data-label="Bookmaker line">{bar(row.get('market_p_a_pct'), row.get('market_p_b_pct'))}
  <div class="tag">{esc(row.get('odds_a') if row.get('odds_a') else '—')} / {esc(row.get('odds_b') if row.get('odds_b') else '—')}{f" · {len(books)} books" if books else ''}{f" · {len(sources)} sources" if sources else ''}
  {f" · overround {row['overround_pct']:.1f}%" if row.get('overround_pct') else ''}</div></td>
<td data-label="Our own line">{bar(row.get('own_model_p_a_pct'), row.get('own_model_p_b_pct'))}
  <div class="tag">{esc('rating model' if row.get('own_model_p_a_pct') is not None else 'not available — see flag')}</div></td>
<td data-label="Pick">{pick_badge(row)}</td>
<td data-label="Sources">{source_links(row)}<div class="chips">{flag_chips(row.get('flags') or [])}</div></td>
</tr>"""


def table(rows: list[dict], caption: str = "") -> str:
    head = ("<tr><th>Match</th><th>Start</th><th>Bookmaker line (de-vigged)</th>"
            "<th>Our own line</th><th>Pick</th><th>Sources &amp; flags</th></tr>")
    body = "\n".join(match_row(r) for r in rows)
    if not body:
        body = '<tr><td colspan="6" class="muted">No rows in this section.</td></tr>'
    cap = f'<caption class="muted small" style="text-align:left;padding:8px 10px">{esc(caption)}</caption>' if caption else ""
    return f'<div class="tablewrap"><table>{cap}<thead>{head}</thead><tbody>{body}</tbody></table></div>'


def toolbar(rows: list[dict]) -> str:
    tours = sorted({r.get("competition") or "" for r in rows if r.get("competition")})
    opts = "".join(f'<option value="{esc(t)}">{esc(t)}</option>' for t in tours)
    sports = sorted({r.get("sport") or "" for r in rows})
    sopts = "".join(f'<option value="{esc(s)}">{esc(SPORT_LABEL.get(s, s))}</option>'
                    for s in sports)
    return f"""<div class="toolbar">
<input id="q" type="search" placeholder="Search team or tournament" aria-label="Search">
<select id="sport" aria-label="Title"><option value="">All titles</option>{sopts}</select>
<select id="tournament" aria-label="Tournament"><option value="">All tournaments</option>{opts}</select>
<label><input type="checkbox" id="missing"> only rows with a missing value</label>
</div>"""


def kpi(k: str, v: str) -> str:
    return f'<div class="card"><div class="k">{esc(k)}</div><div class="v">{esc(v)}</div></div>'


def main() -> int:
    payload = json.loads((DATA / "current.json").read_text(encoding="utf-8"))
    meta, rows = payload["meta"], payload["matches"]
    flagged, stale = payload["flagged"], payload["stale_listings"]
    stamp = meta["source_snapshot_utc"]
    counts = meta["counts"]
    OUT.mkdir(exist_ok=True)
    (OUT / "style.css").write_text(CSS, encoding="utf-8")

    cs2 = [r for r in rows if (r.get("sport") or "").lower() in {"cs2", "counterstrike", "cs"}]
    lol = [r for r in rows if (r.get("sport") or "").lower() in {"lol", "leagueoflegends"}]

    def summary_cards(subset: list[dict]) -> str:
        n = len(subset)
        mk = sum(1 for r in subset if r["market_p_a_pct"] is not None)
        ol = sum(1 for r in subset if r["own_model_p_a_pct"] is not None)
        pk = sum(1 for r in subset if r["pick"])
        return (kpi("Fixtures in this week", str(n)) + kpi("With bookmaker line", f"{mk}/{n}") +
                kpi("With our own line", f"{ol}/{n}") + kpi("Picks published", f"{pk}/{n}"))

    def kind_rows(subset, kind_value, note):
        sel = [r for r in subset if (tier_of(r) == kind_value)]
        return (f'<h3>{esc(kind_value)} tier — {len(sel)} fixtures</h3>' + (toolbar(sel) if sel else "")
                + table(sel, note))

    def tier_of(row):
        return (row.get("tier") or "—").upper()

    # ---------------------------------------------------------------- index
    top_picks = sorted([r for r in rows if r["pick"] and not r["locked"]],
                       key=lambda r: -(r["pick_pct"] or 0))[:8]
    picks_html = "".join(
        f'<div class="card"><div class="k">{esc(r["competition"] or "")}</div>'
        f'<div class="v">{esc(r["pick"])} <span class="muted small">{pct(r["pick_pct"])}</span></div>'
        f'<div class="tag">{esc(r["team_a"])} vs {esc(r["team_b"])} · '
        f'<time data-utc="{esc(r["start_utc"])}">{esc(r["start_utc"])}</time></div></div>'
        for r in top_picks) or '<p class="muted">No open fixtures with a published pick.</p>'
    cs2_caption = ("Every CS2 fixture in the current Pick'em week. \"—\" means the value could "
                   "not be sourced.")
    lol_caption = ("Every LoL fixture in the current Pick'em week (no official rating source "
                   "feeds an own line for LoL, so that column stays blank and is flagged).")
    cs2_table = table(cs2, cs2_caption)
    lol_table = table(lol, lol_caption)
    index_body = f"""
<div class="grid">{summary_cards(rows)}</div>
<div class="note"><strong>How to read this board.</strong> The green/grey bar under
<em>Bookmaker line</em> is the win probability implied by the median external bookmaker price for
that match after removing the overround (the book's margin). <em>Our own line</em> is our
independent rating-based probability. The <em>Pick</em> column is the combined estimate
(70% market / 30% own line where both exist). Tap any source link to see the page the number came
from. Full details on the <a href="methodology.html">Method</a> page.</div>
<h2>Strongest picks right now</h2>
<div class="grid">{picks_html}</div>
<h2>CS2 slate</h2>
<div class="grid">{summary_cards(cs2)}</div>
{toolbar(cs2)}
{cs2_table}
<h2>League of Legends slate</h2>
<div class="grid">{summary_cards(lol)}</div>
{lol_table}
"""
    (OUT / "index.html").write_text(page("index.html", "Pick'em line board", index_body, stamp,
                                         "Win probabilities and picks for every match in the "
                                         "Hotspawn Play Pick'em, each row linked to its source."),
                                    encoding="utf-8")

    # ---------------------------------------------------------------- matches
    body = (f'<div class="grid">{summary_cards(rows)}</div>' + toolbar(rows) +
            table(rows, f"All {len(rows)} fixtures in the current Pick'em week."))
    (OUT / "matches.html").write_text(page("matches.html", "All matches", body, stamp),
                                      encoding="utf-8")

    for name, subset, label in (("cs2.html", cs2, "CS2"), ("lol.html", lol, "League of Legends")):
        if not subset:
            body = '<p class="muted">No fixtures for this title in the current week.</p>'
        else:
            body = (f'<div class="grid">{summary_cards(subset)}</div>' + toolbar(subset) +
                    table(subset))
        (OUT / name).write_text(page(name, f"{label} fixtures", body, stamp), encoding="utf-8")

    # ---------------------------------------------------------------- tournaments / tiers
    tours: dict[str, list[dict]] = {}
    for r in rows:
        tours.setdefault(r.get("competition") or "Unknown tournament", []).append(r)
    tbody = []
    for tname in sorted(tours, key=lambda t: min(r["start_utc"] for r in tours[t])):
        subset = tours[tname]
        mk = sum(1 for r in subset if r["market_p_a_pct"] is not None)
        tbody.append(f'<h3>{esc(tname)} <span class="muted small">· {len(subset)} fixtures · '
                     f'{mk} priced</span></h3>' + table(subset))
    (OUT / "tournaments.html").write_text(
        page("tournaments.html", "By tournament", "".join(tbody), stamp), encoding="utf-8")

    tiers = {}
    for r in rows:
        tiers.setdefault(tier_of(r), []).append(r)
    tier_html = "".join(f'<h3>Tier {esc(t)} — {len(tiers[t])} fixtures</h3>' + table(tiers[t])
                        for t in sorted(tiers))
    (OUT / "by-tier.html").write_text(page("by-tier.html", "By tier", tier_html or
                                           '<p class="muted">No fixtures.</p>', stamp),
                                      encoding="utf-8")

    # ---------------------------------------------------------------- odds register
    odds_path = DATA / "odds.csv"
    odds_rows = list(csv.DictReader(odds_path.open(encoding="utf-8"))) if odds_path.exists() else []
    orows = []
    for row in odds_rows:
        a, b = float(row["odds_a"]), float(row["odds_b"])
        over = (1 / a + 1 / b)
        orows.append(
            f'<tr><td data-label="Match">{esc(row["team_a"])} vs {esc(row["team_b"])}</td>'
            f'<td data-label="Source">{esc(row.get("source") or "")}</td>'
            f'<td data-label="Bookmaker">{esc(row["bookmaker"])}</td>'
            f'<td data-label="Prices">{a:.2f} / {b:.2f}</td>'
            f'<td data-label="De-vigged A">{100 * (1 / a) / over:.1f}%</td>'
            f'<td data-label="Margin">{100 * (over - 1):.1f}%</td>'
            f'<td data-label="Source link"><a href="{esc(row["source_url"])}" rel="noopener">page</a>'
            f' <span class="muted small">{esc(row["fetched_utc"] or "")}</span></td></tr>')
    od_table = ('<div class="tablewrap"><table><thead><tr><th>Match</th><th>Source</th><th>Bookmaker</th>'
                '<th>Match-winner prices</th><th>De-vigged favourite</th><th>Margin</th>'
                '<th>Source page</th></tr></thead><tbody>' + ("".join(orows) or
                '<tr><td colspan="7" class="muted">No bookmaker rows collected.</td></tr>') +
                '</tbody></table></div>')
    (OUT / "odds.html").write_text(
        page("odds.html", "Bookmaker lines used",
             f'<p class="muted">Every price read this run, one row per bookmaker. The board\'s '
             f'market probability is the median of the match-winner column per fixture.</p>'
             + od_table, stamp), encoding="utf-8")

    # ---------------------------------------------------------------- ratings
    ratings_path = DATA / "ratings.csv"
    rrows = list(csv.DictReader(ratings_path.open(encoding="utf-8"))) \
        if ratings_path.exists() else []
    rating_html = []
    for row in rrows:
        url = row.get("hltv_source_url") or ""
        vrs_url = row.get("vrs_source_url") or ""
        rank = row.get("hltv_rank") or "—"
        pts = row.get("hltv_points") or "—"
        vrs_pts = row.get("vrs_points") or "—"
        rating_html.append(f'<tr><td data-label="Team">{esc(row["team"])}</td>'
                           f'<td data-label="HLTV rank">#{esc(rank)}</td>'
                           f'<td data-label="HLTV points">{esc(pts)}</td>'
                           f'<td data-label="Valve VRS points">{esc(vrs_pts)}</td>'
                           f'<td data-label="Sources">'
                           + (f'<a href="{esc(url)}" rel="noopener">HLTV</a> ' if url else '')
                           + (f'<a href="{esc(vrs_url)}" rel="noopener">Valve</a>' if vrs_url else '')
                           + '</td></tr>')
    rtable = ('<div class="tablewrap"><table><thead><tr><th>Team</th><th>HLTV world rank</th>'
              '<th>HLTV points</th><th>Valve VRS points</th><th>Sources</th></tr></thead><tbody>' +
              ("".join(rating_html) or '<tr><td colspan="5" class="muted">No ratings read.</td>'
                                       '</tr>') + '</tbody></table></div>')
    vrs_line = (f'<p>Valve Regional Standings file used as the second own-line input: '
                f'<a href="{esc(meta.get("sources")[-1].get("url") or "")}" rel="noopener">'
                f'{esc(meta.get("sources")[-1].get("url") or "not read this run")}</a>.</p>')
    (OUT / "ratings.html").write_text(
        page("ratings.html", "Team ratings used by our own line",
             f'<p class="muted">Only teams that appear in the published rating source are listed; '
             f'a team missing here yields a blank own-line value for its fixtures (flagged, never '
             f'inferred).</p>' + rtable + vrs_line, stamp), encoding="utf-8")

    # ---------------------------------------------------------------- methodology
    method = meta["method"]
    work = next((r for r in rows if r["odds_a"] and r["market_p_a_pct"]), None)
    example = ""
    if work:
        raw_a, raw_b = 1 / work["odds_a"], 1 / work["odds_b"]
        example = (f'<h3>Worked example — {esc(work["team_a"])} vs {esc(work["team_b"])}</h3>'
                   f'<p>Median external prices: {work["odds_a"]:.2f} and {work["odds_b"]:.2f} '
                   f'(from {len(work["odds_bookmakers"])} bookmaker rows on '
                   f'<a href="{esc(work["odds_source_url"])}" rel="noopener">EGamersWorld</a>). '
                   f'Raw implied: {raw_a * 100:.1f}% + {raw_b * 100:.1f}% = '
                   f'{(raw_a + raw_b) * 100:.1f}% (the {(raw_a + raw_b - 1) * 100:.1f}% above 100 '
                   f'is the bookmaker margin). Removing it proportionally gives '
                   f'{work["market_p_a_pct"]:.1f}% / {work["market_p_b_pct"]:.1f}%, the number on '
                   f'the board.</p>')
    meth_body = f"""
<div class="note"><strong>What this board does and does not do.</strong>
<ul>
<li>Fixture identity and lock times: Hotspawn Play's own payload.</li>
<li>Market probability: {esc(method['market_probability'])}.</li>
<li>Own line: {esc(method['own_line'])}.</li>
<li>Combined estimate: {esc(method['combined_estimate'])}.</li>
<li>{esc(method['policy'])}.</li>
</ul></div>
{example}
<h3>Limits</h3>
<ul>
<li>Bookmaker prices move. Every price on this site carries the UTC time it was read; the
<a href="sources.html">Sources</a> page lists the exact page and its SHA-256.</li>
<li>Where only one bookmaker price was readable, the row says so and is listed under
<a href="flagged.html">Flagged for review</a>.</li>
<li>Rating points are not Elo ratings; the logistic scale ({ELO_SCALE:.0f}) is the standard Elo
constant and is documented, not fitted to this slate.</li>
<li>Series format (Bo1/Bo3) is taken from the Pick'em payload when present; where it is absent the
row shows "Waiting For Information" and no format adjustment is applied.</li>
<li>Academy teams are never matched to their parent organisation, and no name is ever matched
fuzzily — an unmatched team produces a blank value plus a flag.</li>
</ul>
"""
    (OUT / "methodology.html").write_text(page("methodology.html", "Method & policy", meth_body,
                                               stamp), encoding="utf-8")

    # ---------------------------------------------------------------- sources
    prov_path = DATA / "provenance.json"
    prov = json.loads(prov_path.read_text(encoding="utf-8"))["fetches"] if prov_path.exists() else []
    prows = "".join(
        f'<tr><td data-label="Source"><a href="{esc(p["url"])}" rel="noopener">{esc(p["url"])[:96]}'
        f'</a></td><td data-label="Status">{esc(p.get("status") if p.get("status") is not None else "—")}'
        f'</td><td data-label="Bytes">{esc(p.get("bytes") if p.get("bytes") is not None else "—")}'
        f'</td><td data-label="SHA-256">{esc((p.get("sha256") or "—")[:16])}</td>'
        f'<td data-label="Read at">{esc(p.get("fetched_utc") or "")}</td>'
        f'<td data-label="Error">{esc(p.get("error") or "")}</td></tr>' for p in prov)
    ptable = ('<div class="tablewrap"><table><thead><tr><th>Page fetched</th><th>HTTP</th>'
              '<th>Bytes</th><th>SHA-256 (16)</th><th>Read at (UTC)</th><th>Error</th></tr>'
              '</thead><tbody>' + (prows or '<tr><td colspan="6" class="muted">No provenance '
                                            'record.</td></tr>') + '</tbody></table></div>')
    also = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener">{esc(s["label"])}</a></li>'
                   for s in meta["sources"] if s.get("url"))
    (OUT / "sources.html").write_text(
        page("sources.html", "Sources & provenance",
             '<p class="muted">Every page this board read on its last refresh, with the byte size '
             'and hash of the response so anyone can re-fetch and compare. Raw page bodies are '
             'deliberately not committed.</p>' + ptable +
             f'<h3>Sources in use</h3><ul>{also}</ul>'
             '<h3>Re-verify in one step</h3><pre class="card">python3 refresh/collect.py &amp;&amp; '
             'python3 refresh/build.py &amp;&amp; python3 refresh/build_site.py &amp;&amp; '
             'python3 refresh/verify.py</pre>', stamp), encoding="utf-8")

    # ---------------------------------------------------------------- flagged
    fblocks = []
    for flag in flagged:
        items = flag.get("items") or []
        chips = "".join(f'<span class="chip warn">{esc(str(i))}</span> ' for i in items[:60])
        more = f' <span class="muted small">(+{len(items) - 60} more)</span>' if len(items) > 60 else ""
        link = (f'<div class="tag">source: <a href="{esc(flag["source_url"])}" rel="noopener">'
                f'{esc(flag["source_url"])}</a></div>') if flag.get("source_url") else ""
        fblocks.append(f'<div class="card"><div class="k">{esc(flag["code"])}</div>'
                       f'<h3>{esc(flag["title"])}</h3><p>{esc(flag["detail"])}</p>{link}'
                       f'<div class="chips" style="margin-top:6px">{chips}{more}</div></div>')
    row_flags = [r for r in rows if any(f not in ("market_only_no_own_line",
                                                  "own_line_only_no_market") for f in r["flags"])]
    ftable = table(row_flags, "Fixtures whose values are incomplete or rest on a single reading — "
                              "never filled in by inference.")
    stale_table = table([{**s, "tier": None, "points": None, "odds_a": None, "odds_b": None,
                          "odds_kind": None, "odds_bookmakers": [], "odds_source_url": None,
                          "market_p_a_pct": None, "market_p_b_pct": None,
                          "own_model_p_a_pct": None, "own_model_p_b_pct": None,
                          "pick": None, "pick_pct": None, "locked": False, "started": False,
                          "flags": ["stale_listing_outside_week"], "hotspawn_url": s["source_url"],
                          "sport": s.get("sport") or "", "start_utc": s["start_utc"],
                          "lock_utc": None, "competition": s.get("competition"),
                          "team_a": s["team_a"], "team_b": s["team_b"]}
                         for s in stale],
                         "Listings still present in Hotspawn's payload but outside this Pick'em "
                         "week — no line is originated for them.") if stale else ""
    (OUT / "flagged.html").write_text(
        page("flagged.html", "Flagged for review",
             '<div class="note warnbox">Nothing on this page blocks publication: each item is a '
             'value that could not be confirmed from an official source, or a reading that rests '
             'on a single source. Review the linked evidence and open an issue if a value looks '
             'wrong.</div>' + "".join(fblocks) + "<h2>Fixture rows with incomplete values</h2>" +
             ftable + ("<h2>Stale listings excluded from the analysis</h2>" + stale_table
                       if stale_table else ""), stamp), encoding="utf-8")

    # ---------------------------------------------------------------- repo review page (if present)
    review_path = DATA / "repo_review.json"
    if not review_path.exists():
        review = {"intro": ("Repository review has not been generated for this refresh yet. "
                           "The pipeline writes it before the integration pull request."),
                  "sections": []}
    else:
        review = json.loads(review_path.read_text(encoding="utf-8"))
    if True:
        blocks = []
        for section in review["sections"]:
            rows_html = "".join(
                f'<tr><td data-label="Item">{esc(i["item"])}</td>'
                f'<td data-label="Status">{esc(i["status"])}</td>'
                f'<td data-label="Evidence / source">'
                + (f'<a href="{esc(i["source"])}" rel="noopener">{esc(i["source"])}</a>'
                   if i.get("source") else "—")
                + (f'<div class="tag">{esc(i.get("note") or "")}</div>' if i.get("note") else "")
                + '</td></tr>' for i in section["rows"])
            blocks.append(f'<h3>{esc(section["title"])}</h3>'
                          f'<div class="tablewrap"><table><thead><tr><th>Item</th><th>Status</th>'
                          f'<th>Evidence / source</th></tr></thead><tbody>{rows_html}'
                          f'</tbody></table></div>')
        (OUT / "repo-review.html").write_text(
            page("repo-review.html", "Repository review",
                 f'<p class="muted">{esc(review["intro"])}</p>' + "".join(blocks), stamp),
            encoding="utf-8")

    # ---------------------------------------------------------------- copy data for the site
    data_dir = OUT / "data"
    data_dir.mkdir(exist_ok=True)
    for name in ("current.json", "current.csv", "odds.csv", "ratings.csv", "provenance.json"):
        src = DATA / name
        if src.exists():
            shutil.copy2(src, data_dir / name)
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    print(json.dumps({"pages": sorted(p.name for p in OUT.glob("*.html")),
                      "rows": len(rows), "cs2": len(cs2), "lol": len(lol),
                      "odds_rows": len(odds_rows)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
