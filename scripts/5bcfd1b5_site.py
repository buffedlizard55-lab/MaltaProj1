#!/usr/bin/env python3
"""arena/5bcfd1b5 — render the mobile-first `allpicks/` board from committed data.

Offline and deterministic: reads only data/5bcfd1b5/*.csv|json and writes allpicks/*.html.
Every data row it renders carries at least one link to the official source of that value.
"""

from __future__ import annotations

import csv
import datetime as dt
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "allpicks")
DATA = os.path.join(ROOT, "data", "5bcfd1b5")

HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
VALVE_REPO = "https://github.com/ValveSoftware/counter-strike_regional_standings"

TIER_LABEL = {
    "A": ("A", "Primary book", "moneyline read from a primary bookmaker by CI this cycle"),
    "B": ("B", "Book price, not re-read this cycle",
          "a bookmaker moneyline we could not re-read during this build: either a direct "
          "read of a primary book's own price feed at an earlier timestamp, or a named "
          "aggregator's report of a book price"),
    "C": ("C", "Our own line", "both teams uniquely ranked in the official Valve standings in force"),
    "D": ("D", "Our own line (soft)",
          "our own line from official Valve standings, via a roster-verified alias, a pinned "
          "duplicate-name row, or a rating period later than the match date"),
    "E": ("E", "Directional only",
          "one side is officially ranked and the other is confirmed unranked everywhere, so a "
          "direction is published and the probability is deliberately left blank"),
    "F": ("F", "No pick", "no official rating for both sides and no market price — nothing is inferred"),
}

NAV = [
    ("index.html", "Executive summary"),
    ("open.html", "Open matches"),
    ("all.html", "All 89 fixtures"),
    ("tiers.html", "By tier"),
    ("tournaments.html", "By tournament"),
    ("market.html", "Outside lines"),
    ("own-lines.html", "Our own lines"),
    ("ratings.html", "Team ratings"),
    ("methodology.html", "Methodology"),
    ("sources.html", "Sources"),
    ("flagged.html", "Flagged for review"),
]


def e(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def read_csv(name: str) -> list[dict]:
    p = os.path.join(DATA, name)
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fmt_when(iso: str) -> str:
    if not iso:
        return "—"
    d = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    return d.strftime("%a %d %b · %H:%M UTC")


def short_when(iso: str) -> str:
    if not iso:
        return "—"
    d = dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")
    return d.strftime("%d %b %H:%M")


def pct(v: str) -> str:
    return v if v else ""


# ---------------------------------------------------------------- CSS
CSS = """
:root{
  --bg:#0b0f17; --panel:#131a26; --panel2:#0f1520; --line:#22304a; --line2:#2f4160;
  --ink:#e9eef7; --dim:#9fb0c8; --dim2:#7488a3;
  --a:#4ea1ff; --b:#ffb454; --pick:#22c55e; --warn:#f59e0b; --bad:#ef4444; --ok:#22c55e;
  --S:#f472b6; --B:#60a5fa; --C:#94a3b8;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  padding-bottom:5rem}
a{color:var(--a);text-decoration:none}
a:hover,a:focus{text-decoration:underline}
.wrap{max-width:1100px;margin:0 auto;padding:0 .75rem}
header.top{position:sticky;top:0;z-index:30;background:rgba(11,15,23,.96);
  border-bottom:1px solid var(--line);backdrop-filter:blur(6px)}
.brand{display:flex;align-items:baseline;gap:.5rem;flex-wrap:wrap;padding:.6rem 0 .35rem}
.brand h1{font-size:1.05rem;margin:0;letter-spacing:.2px}
.brand .tag{color:var(--dim2);font-size:.78rem}
nav.jump{display:flex;gap:.4rem;overflow-x:auto;padding:.35rem 0 .55rem;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
nav.jump::-webkit-scrollbar{display:none}
nav.jump a{flex:0 0 auto;padding:.42rem .7rem;border:1px solid var(--line);border-radius:999px;
  background:var(--panel2);color:var(--dim);font-size:.83rem;white-space:nowrap}
nav.jump a[aria-current="page"]{background:var(--a);border-color:var(--a);color:#04101f;font-weight:700}
main{padding-top:.9rem}
h2{font-size:1.12rem;margin:1.5rem 0 .5rem}
h3{font-size:.98rem;margin:1.15rem 0 .4rem;color:var(--dim)}
p{margin:.45rem 0}
.lede{color:var(--dim);font-size:.93rem}
.small{font-size:.8rem;color:var(--dim2)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.85rem;margin:.7rem 0}
.hero{background:linear-gradient(160deg,#152238,#0f1520);border:1px solid var(--line2)}
.hero .big{font-size:1.55rem;font-weight:800;line-height:1.15;margin:.15rem 0}
.hero .big span{color:var(--pick)}
.stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem;margin:.7rem 0 0}
@media(min-width:720px){.stats{grid-template-columns:repeat(4,minmax(0,1fr))}}
.stat{background:var(--panel2);border:1px solid var(--line);border-radius:12px;padding:.55rem .65rem}
.stat b{display:block;font-size:1.3rem;line-height:1.1}
.stat span{color:var(--dim2);font-size:.74rem;display:block;margin-top:.15rem}
.cta{display:block;background:var(--pick);color:#05230f;font-weight:800;border-radius:12px;
  padding:.85rem .9rem;margin:.7rem 0;font-size:1.02rem;text-align:center}
.cta:hover,.cta:focus{text-decoration:none;filter:brightness(1.06)}
.cta.alt{background:var(--panel2);color:var(--ink);border:1px solid var(--line2);font-weight:600}
.grid{display:grid;grid-template-columns:1fr;gap:.55rem}
@media(min-width:820px){.grid.two{grid-template-columns:1fr 1fr}}

/* match card */
.match{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:.7rem .75rem .6rem;
  margin:.55rem 0;break-inside:avoid}
.match.no-pick{border-left:4px solid var(--bad)}
.match.tierA{border-left:4px solid var(--ok)}
.match.tierB{border-left:4px solid var(--a)}
.match.tierC{border-left:4px solid var(--b)}
.match.tierD{border-left:4px solid #a78bfa}
.match.tierE{border-left:4px solid var(--warn)}
.match.tierF{border-left:4px solid var(--bad)}
.mrow{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;font-size:.76rem;color:var(--dim2)}
.badge{border:1px solid var(--line2);border-radius:999px;padding:.1rem .48rem;font-size:.72rem;
  color:var(--dim);background:var(--panel2);white-space:nowrap}
.badge.S{color:#0b0f17;background:var(--S);border-color:var(--S);font-weight:700}
.badge.Bt{color:#0b0f17;background:var(--B);border-color:var(--B);font-weight:700}
.badge.Ct{color:#0b0f17;background:var(--C);border-color:var(--C);font-weight:700}
.badge.locked{color:#ffd9d9;border-color:#5b2b2b;background:#2a1414}
.badge.live{color:#d9ffe6;border-color:#255c39;background:#12291c}
.teams{margin:.5rem 0 .35rem}
.tline{display:grid;grid-template-columns:1fr auto;gap:.5rem;align-items:center;padding:.28rem 0}
.tname{font-weight:650;font-size:1rem;display:flex;align-items:center;gap:.4rem;min-width:0}
.tname .star{color:var(--pick);font-weight:800}
.tname span.nm{overflow-wrap:anywhere}
.tpct{font-variant-numeric:tabular-nums;font-weight:800;font-size:1.12rem;text-align:right;
  min-width:4.1rem}
.tpct.mute{color:var(--dim2);font-weight:600;font-size:.86rem}
.bar{height:.55rem;border-radius:999px;background:#25324a;overflow:hidden;display:flex;margin:.3rem 0 .1rem}
.bar i{display:block;height:100%}
.bar i.pa{background:var(--a)}
.bar i.pb{background:var(--b)}
.basis{font-size:.79rem;color:var(--dim);margin-top:.4rem}
.basis b{color:var(--ink)}
.links{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.5rem}
.links a{font-size:.74rem;border:1px solid var(--line);background:var(--panel2);color:var(--dim);
  border-radius:8px;padding:.24rem .5rem}
.links a:hover,.links a:focus{color:var(--ink);border-color:var(--line2);text-decoration:none}
.flagchip{font-size:.72rem;color:#ffd9a8;border:1px solid #6b4a1f;background:#2a1e0f;
  border-radius:8px;padding:.2rem .45rem}

/* tables */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:12px;
  margin:.6rem 0}
table{border-collapse:collapse;width:100%;font-size:.84rem;min-width:640px}
th,td{text-align:left;padding:.5rem .55rem;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--panel2);color:var(--dim);font-size:.75rem;text-transform:uppercase;
  letter-spacing:.04em;position:sticky;top:0}
tbody tr:nth-child(even){background:rgba(255,255,255,.015)}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;border-radius:6px;padding:.05rem .35rem;font-size:.72rem;font-weight:700}
.pill.A{background:#0f2f1c;color:#7ee2a8}.pill.B{background:#0f2438;color:#8cc4ff}
.pill.C{background:#33270f;color:#ffcf87}.pill.D{background:#251b3d;color:#c4b0ff}
.pill.E{background:#33260f;color:#ffcf87}.pill.F{background:#331414;color:#ff9d9d}
.blank{color:var(--dim2);font-style:italic}
ul.tight{margin:.35rem 0 .35rem 1.1rem;padding:0}
ul.tight li{margin:.22rem 0}
.note{border-left:3px solid var(--line2);padding:.2rem 0 .2rem .7rem;color:var(--dim);font-size:.86rem}
.warn{border-left:3px solid var(--warn);background:#221a0c;padding:.6rem .7rem;border-radius:8px;
  font-size:.86rem;margin:.6rem 0}
footer{margin:2rem 0 1rem;padding-top:1rem;border-top:1px solid var(--line);color:var(--dim2);
  font-size:.78rem}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap}
"""

JS = """
/* Progressive enhancement only: the board is complete, readable HTML without JS. */
(function(){
  var f=document.getElementById('q');
  if(!f) return;
  f.addEventListener('input',function(){
    var v=f.value.trim().toLowerCase();
    document.querySelectorAll('[data-search]').forEach(function(el){
      el.style.display = !v || el.getAttribute('data-search').toLowerCase().indexOf(v)>=0 ? '' : 'none';
    });
    var n=document.getElementById('qcount');
    if(n) n.textContent = v ? 'filter: "'+f.value+'"' : '';
  });
})();
"""


def page(title: str, active: str, body: str, subtitle: str = "") -> str:
    nav = "\n".join(
        '<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if href == active else "", e(label))
        for href, label in NAV)
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<meta name="description" content="%(desc)s">
<title>%(title)s · Hotspawn CS2 picks</title>
<style>%(css)s</style>
</head>
<body>
<header class="top"><div class="wrap">
<div class="brand"><h1>Hotspawn CS2 — every match, one pick</h1>
<span class="tag">independent lines · never Hotspawn crowd&nbsp;%%</span></div>
<nav class="jump" aria-label="Board sections">%(nav)s</nav>
</div></header>
<main class="wrap">
%(subtitle)s
%(body)s
<footer>
<p>Independent analysis for research purposes only — not betting advice. Fixture identity and
UTC start/lock times come from Hotspawn's public pick'em pages; every probability comes from an
outside bookmaker price or from Valve's official Regional Standings, never from Hotspawn's crowd
pick percentages and never from HLTV's &ldquo;Pick a winner&rdquo; vote.</p>
<p>Built by session <code>arena/5bcfd1b5</code> from committed evidence.
See <a href="methodology.html">Methodology</a> and <a href="flagged.html">Flagged for review</a>.</p>
</footer>
</main>
<script>%(js)s</script>
</body></html>
""" % {"title": e(title), "desc": e(subtitle or title), "css": CSS, "js": JS, "nav": nav,
       "subtitle": subtitle, "body": body}


# ---------------------------------------------------------------- cards
def win_pct_cell(r: dict) -> str:
    """Headline win probability, with the bracket range when Valve's file is ambiguous."""
    if not r["pick_pct"]:
        return "—"
    hi = r["pick_pct_hi"]
    if hi and hi != r["pick_pct"]:
        return "%s%% <span class='small'>(to %s%%)</span>" % (e(r["pick_pct"]), e(hi))
    return "%s%%" % e(r["pick_pct"])


def prob_bar(pa: str, pb: str) -> str:
    try:
        a = float(pa)
    except (TypeError, ValueError):
        return ""
    b = 100.0 - a if not pb else float(pb)
    return ('<div class="bar" role="img" aria-label="Win probability %(a).1f%% vs %(b).1f%%">'
            '<i class="pa" style="width:%(a).2f%%"></i><i class="pb" style="width:%(b).2f%%"></i>'
            '</div>') % {"a": a, "b": b}


def valve_cand_links(team: str, urls: str, cand_text: str) -> list[tuple[str, str]]:
    """Label every admissible Valve row so an ambiguous rating stays clickable.

    `cand_text` is team_ratings.candidate_standings: '#119/991pts/2026_06_01.md/L124;…'.
    """
    if not urls:
        return []
    info: dict[str, str] = {}
    for part in (cand_text or "").split(";"):
        m = re.match(r"#(\d+)/(\d+)pts/[^/]+/L(\d+)$", part.strip())
        if m:
            info[m.group(3)] = "#%s (%s pts)" % (m.group(1), m.group(2))
    out = []
    urls_list = [u for u in urls.split(";") if u]
    for i, u in enumerate(urls_list, 1):
        line = u.rsplit("#L", 1)[-1]
        label = info.get(line) or "row %d of %d" % (i, len(urls_list))
        out.append(("Valve VRS · %s %s" % (team, label), u))
    return out


def match_card(r: dict, show_state: bool = True) -> str:
    ta, tb = r["team_a"], r["team_b"]
    pick = r["pick"]
    tier = r["pick_tier"] or "F"
    pa, pb = r["own_p_a_pct"] or "", r["own_p_b_pct"] or ""
    if r["market_tier"]:
        pa, pb = r["market_p_a_pct"], r["market_p_b_pct"]
    state = r["state"]
    chips = []
    if show_state:
        if state == "open":
            chips.append('<span class="badge live">OPEN — pickable</span>')
        elif state == "started":
            chips.append('<span class="badge locked">locked / started</span>')
        else:
            chips.append('<span class="badge locked">expired</span>')
    tcls = {"S": "S", "B": "Bt", "C": "Ct"}.get(r["tier"], "")
    chips.append('<span class="badge %s">Tier %s · %s pts</span>' % (tcls, e(r["tier"]), e(r["points"])))
    if r["best_of"]:
        chips.append('<span class="badge">BO%s</span>' % e(r["best_of"]))
    chips.append('<span class="badge">pick tier %s</span>' % e(tier))
    if r["rating_note"]:
        for n in sorted(set(r["rating_note"].split(";"))):
            if n:
                chips.append('<span class="flagchip">%s</span>' % e(n))

    pick_hi = r["pick_pct_hi"]
    has_range = bool(pick_hi and r["pick_pct"] and pick_hi != r["pick_pct"])

    def side(name, p, is_pick):
        star = '<span class="star" aria-hidden="true">★</span>' if is_pick else ""
        lab = ' <span class="sr">(our pick)</span>' if is_pick else ""
        if p:
            val = '<span class="tpct">%s%%%s</span>' % (e(p), lab)
            if is_pick and has_range:
                val += ('<span class="tpct mute" style="display:block;font-size:.7rem">'
                        'up&nbsp;to&nbsp;%s%%</span>' % e(pick_hi))
        elif is_pick:
            val = ('<span class="tpct mute">no&nbsp;%<span class="sr"> (probability '
                   'deliberately blank)</span></span>')
        else:
            val = '<span class="tpct mute">—</span>'
        return ('<div class="tline"><div class="tname">%s<span class="nm">%s</span></div>%s</div>'
                % (star, e(name), val))

    bar = prob_bar(pa, pb)
    basis = '<div class="basis"><b>Why:</b> %s</div>' % e(r["pick_basis"]) if r["pick_basis"] else ""
    if has_range:
        basis += ('<div class="basis"><b>Range:</b> %s%%&ndash;%s%%. Valve\'s standings publish more '
                  'than one row under this team name, so every admissible combination was '
                  'evaluated. The headline figure is the <b>conservative</b> bound; the favourite '
                  'is the same under every combination.</div>'
                  % (e(r["pick_pct"]), e(pick_hi)))

    links = []
    links.append(('Hotspawn fixture', r["hotspawn_match_url"] or r["hotspawn_url"] or HOTSPAWN_CS2))
    if r["hltv_match_url"]:
        links.append(("HLTV match", r["hltv_match_url"]))
    if r["market_url"]:
        links.append(("Market price (%s)" % (r["market_book"].split(" ")[0]), r["market_url"]))
    for team_name, sdx in ((ta, "a"), (tb, "b")):
        url = r["vrs_url_%s" % sdx]
        if url:
            links.append(("Valve VRS · %s" % (r["vrs_name_%s" % sdx] or team_name), url))
        else:
            links.extend(valve_cand_links(r["vrs_name_%s" % sdx] or team_name,
                                          r.get("vrs_cand_urls_%s" % sdx, ""),
                                          CAND_TEXT.get((team_name, r["vrs_period_%s" % sdx]),
                                                          CAND_TEXT.get(team_name, ""))))
    if r["verified_result_url"]:
        links.append(("Official result", r["verified_result_url"]))
    lk = "".join('<a href="%s" rel="noopener">%s</a>' % (e(u), e(t)) for t, u in links if u)

    res = ""
    if r["verified_result"]:
        res = ('<div class="note" style="margin-top:.45rem"><b>Official result (HLTV):</b> %s%s</div>'
               % (e(r["verified_result"]),
                  " — " + e(r["verified_result_note"]) if r["verified_result_note"] else ""))

    model_note = ""
    if r["market_tier"] and r["own_p_a_pct"]:
        model_note = ('<div class="small" style="margin-top:.35rem">Our own model says %s%% / %s%%'
                      ' &middot; %s</div>'
                      % (e(r["own_p_a_pct"] or "—"), e(r["own_p_b_pct"] or "—"),
                         e(r["own_basis"][:170])))

    search_blob = " ".join([ta, tb, r["competition"], r["fixture_id"], r["tier"],
                            r["pick_tier"], r["start_utc"]])
    return (
        '<article class="match tier%(t)s" data-search="%(sb)s">'
        '<div class="mrow"><strong>%(when)s</strong><span>%(comp)s</span>'
        '<span style="margin-left:auto">#%(fid)s</span></div>'
        '<div class="mrow" style="margin-top:.3rem">%(chips)s</div>'
        '<div class="teams">%(sa)s%(bar)s%(sbs)s</div>'
        '%(basis)s%(res)s%(model)s'
        '<div class="links">%(lk)s</div></article>'
    ) % {
        "t": e(tier), "sb": e(search_blob), "when": e(fmt_when(r["start_utc"])),
        "comp": e(r["competition"]), "fid": e(r["fixture_id"]), "chips": "".join(chips),
        "sa": side(ta, pa, pick == ta), "bar": bar, "sbs": side(tb, pb, pick == tb),
        "basis": basis, "res": res, "model": model_note, "lk": lk,
    }


def card(r, show_state=True):
    return match_card(r, show_state)


def searchbox(placeholder="Filter by team, tournament or fixture id…") -> str:
    return ('<p><label class="sr" for="q">%s</label>'
            '<input id="q" type="search" placeholder="%s" '
            'style="width:100%%;max-width:34rem;padding:.6rem .7rem;border-radius:10px;'
            'border:1px solid var(--line2);background:var(--panel2);color:var(--ink);font-size:1rem">'
            '<span id="qcount" class="small"></span></p>') % (e(placeholder), e(placeholder))


def table(headers, rows_html, widths=None) -> str:
    th = "".join('<th%s>%s</th>' % (' class="num"' if h.startswith("#") else "",
                                    e(h.lstrip("#"))) for h in headers)
    return '<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
        th, rows_html)


def src_cell(items: list[tuple[str, str]]) -> str:
    out = [t for t in ('<a href="%s" rel="noopener">%s</a>' % (e(u), e(l)) for l, u in items if u)]
    return " ".join(out) if out else '<span class="blank">no official source</span>'


# ---------------------------------------------------------------- pages
CAND_TEXT: dict[str, str] = {}


def build() -> dict[str, str]:
    global CAND_TEXT
    for _t in read_csv("team_ratings.csv"):
        CAND_TEXT[(_t["hotspawn_team"], _t["rating_period"])] = _t["candidate_standings"]
        CAND_TEXT.setdefault(_t["hotspawn_team"], _t["candidate_standings"])
    rows = read_csv("every_match.csv")
    flags = read_csv("flags.csv")
    teams = read_csv("team_ratings.csv")
    cov = json.load(open(os.path.join(DATA, "coverage.json"), encoding="utf-8"))
    if not rows:
        raise SystemExit("no rows in data/5bcfd1b5/every_match.csv — run scripts/5bcfd1b5_build.py")
    counts = cov["counts"]
    gen = cov["generated_utc"]
    cap = rows[0]["captured_utc"]
    pages: dict[str, str] = {}

    open_rows = [r for r in rows if r["state"] == "open"]
    started = [r for r in rows if r["state"] == "started"]
    stale = [r for r in rows if r["state"] == "stale"]

    # ---------------- index.html : executive summary ----------------
    tier_counts = counts["pick_tiers"]
    tier_lines = "".join(
        "<li><b>%s</b> — %s: <b>%d</b> %s</li>"
        % (e(k), e(TIER_LABEL[k][1]), tier_counts[k], "match" if tier_counts[k] == 1 else "matches")
        for k in sorted(tier_counts) if k in TIER_LABEL)

    top_open = open_rows[:6]
    idx = page(
        "Executive summary", "index.html",
        subtitle='<p class="lede">Every Counter-Strike 2 match Hotspawn lists, with our pick and a '
                 'win probability from outside betting markets and Valve\'s official team standings.</p>',
        body="""
<section class="panel hero">
<p class="small" style="margin:0">Executive summary &middot; generated %(gen)s &middot;
Hotspawn capture %(cap)s</p>
<div class="big">Picks for <span>%(opick)d of %(otot)d</span> open matches<br>
and %(apick)d of %(atot)d listed matches</div>
<p class="lede" style="margin-top:.4rem">Hotspawn's own lobby lists <b>%(atot)d</b> CS2 fixtures
(this week's filter says 88&ndash;89; the payload holds %(atot)d). Only <b>%(otot)d</b> are still
pickable &mdash; the rest are locked or expired. Every one of them is on this board.</p>
<div class="stats">
<div class="stat"><b>%(otot)d</b><span>open &amp; pickable now</span></div>
<div class="stat"><b>%(onum)d</b><span>open with a numeric win&nbsp;%%</span></div>
<div class="stat"><b>%(mktA)d</b><span>priced by a primary book</span></div>
<div class="stat"><b>%(mktB)d</b><span>priced by a secondary book</span></div>
</div>
<a class="cta" href="open.html">&#9733; See the %(otot)d open matches &amp; picks</a>
<a class="cta alt" href="all.html">See all %(atot)d fixtures (open, locked and expired)</a>
</section>

<h2>Where the picks are</h2>
<div class="grid two">
<div class="panel">
<h3 style="margin-top:0">On your phone, start here</h3>
<ul class="tight">
<li><a href="open.html"><b>Open matches</b></a> &mdash; the %(otot)d fixtures you can still pick in
Hotspawn's game. One card per match: the pick starred, both teams' win&nbsp;%%, a probability bar,
why, and a source link on every row.</li>
<li><a href="all.html"><b>All fixtures</b></a> &mdash; the full %(atot)d-match list including locked
and expired matches, so nothing Hotspawn lists is missing.</li>
<li><a href="flagged.html"><b>Flagged for review</b></a> &mdash; the %(nflag)d items we could not
verify, with the source links we did check.</li>
</ul>
</div>
<div class="panel">
<h3 style="margin-top:0">By category</h3>
<ul class="tight">
<li><a href="tiers.html">By Hotspawn tier</a> &mdash; S (%(ts)d), B (%(tb)d), C (%(tc)d).</li>
<li><a href="tournaments.html">By tournament</a> &mdash; %(ntourn)d competitions.</li>
<li><a href="market.html">Outside betting lines</a> &mdash; bookmaker odds, de-vigged, with the
overround and the read time.</li>
<li><a href="own-lines.html">Our own lines</a> &mdash; the model, its Valve inputs and the arithmetic.</li>
<li><a href="ratings.html">Team ratings</a> &mdash; how each of the %(nteam)d team names resolved to an
official Valve standing, with the exact file line.</li>
<li><a href="methodology.html">Methodology</a> &middot; <a href="sources.html">Sources</a></li>
</ul>
</div>
</div>

<h2>How each pick was decided</h2>
<div class="panel">
<p>Picks follow a fixed hierarchy. A match is decided by the <b>first</b> tier that has a usable
input; tiers are never averaged together, and the tier is printed on every card.</p>
<ul class="tight">%(tierlines)s</ul>
<p class="small">Hotspawn's crowd &ldquo;%% picked&rdquo; and HLTV's &ldquo;Pick a winner&rdquo; vote
are crowd polls. Neither is used as a probability anywhere on this board.</p>
</div>

<h2>Open now &mdash; first %(ntop)d of %(otot)d</h2>
<p class="small"><a href="open.html">Open the full list &rarr;</a></p>
%(topcards)s

<h2>What this session changed</h2>
<div class="panel">
<p>Before this pass, the boards on <code>main</code> published a pick for <b>64 of %(atot)d</b>
fixtures and <b>27 of %(otot)d</b> open matches. The 25 blanks were all rating lookups against
Valve's <b>2026-10-05</b> standings &mdash; but 23 of those fixtures were played in June/July 2026,
so the October file was the wrong official source for them.</p>
<ul class="tight">
<li>Ratings are now taken from the official Valve standings <b>in force at the match date</b>
(five periods, %(nperiod)d committed).</li>
<li>Six roster-verified name aliases were added &mdash; e.g. <b>Envy = 3DMAX</b>, proven by a 5/5
roster match between HLTV's match page and Valve's #21 row.</li>
<li>All 94 inherited duplicate-name row pins were re-checked line by line against Valve's own file
before use: <b>94 accepted, 0 rejected</b>.</li>
<li><b>LFO 10</b> is confirmed absent from every Valve period and unranked on HLTV, so its match
gets a directional pick with the probability deliberately blank rather than an invented number.</li>
<li>3 expired June fixtures stay blank: Valve publishes two same-name rows whose ratings disagree on
the favourite. Nothing is inferred &mdash; they are flagged.</li>
</ul>
</div>

<div class="warn"><b>Read this before using any number here.</b> Market probabilities are
de-vigged bookmaker prices, not guaranteed outcomes. Our own lines come from Valve's published
standings points through a logistic curve fitted on Valve's own match results; they are estimates,
uncalibrated per tournament, and diverge from the market on some matches. Those divergences are
listed on <a href="flagged.html">Flagged for review</a>, not hidden. Locked and expired fixtures
cannot be picked in Hotspawn's game; their rows are archival.</div>
""" % {"gen": e(gen), "cap": e(cap), "opick": counts["open_with_pick"], "otot": counts["state_open"],
       "apick": counts["with_pick"], "atot": counts["fixtures_total"],
       "onum": counts["open_with_numeric_probability"],
       "mktA": counts["market_tier_A"], "mktB": counts["market_tier_B"],
       "nflag": counts["flags"], "nteam": len({t["hotspawn_team"] for t in teams}), "nperiod": len(cov["official_rating_source"]
                                                                     ["periods_used"]),
       "ts": sum(1 for r in rows if r["tier"] == "S"),
       "tb": sum(1 for r in rows if r["tier"] == "B"),
       "tc": sum(1 for r in rows if r["tier"] == "C"),
       "ntourn": len({r["competition"] for r in rows}),
       "ntop": len(top_open), "tierlines": tier_lines,
       "topcards": "".join(match_card(r) for r in top_open)})
    pages["index.html"] = idx

    # ---------------- open.html ----------------
    days = {}
    for r in open_rows:
        days.setdefault(r["start_utc"][:10], []).append(r)
    body = ['<p class="lede">The <b>%d</b> CS2 fixtures Hotspawn still lets you pick. '
            'Every card shows the pick, both teams&rsquo; win&nbsp;%%, the basis, and a source '
            'link. Sorted by lock time.</p>' % len(open_rows)]
    body.append('<p class="small"><b>%d of %d</b> have a numeric probability; %d is a directional '
                'pick with the probability deliberately blank (see '
                '<a href="flagged.html">Flagged</a>).</p>'
                % (counts["open_with_numeric_probability"], len(open_rows),
                   len(open_rows) - counts["open_with_numeric_probability"]))
    body.append(searchbox())
    for d in sorted(days):
        body.append("<h2>%s</h2>" % e(fmt_when(days[d][0]["start_utc"]).split(" · ")[0]))
        for r in days[d]:
            body.append(match_card(r, show_state=False))
    pages["open.html"] = page("Open matches &amp; picks", "open.html", "".join(body))

    # ---------------- all.html ----------------
    body = ['<p class="lede">All <b>%d</b> CS2 fixtures in Hotspawn&rsquo;s pick&rsquo;em payload: '
            '%d open, %d locked/started and %d expired. Nothing Hotspawn lists is omitted.</p>'
            % (len(rows), len(open_rows), len(started), len(stale)), searchbox()]
    for label, subset in (("Open — pickable now", open_rows),
                          ("Locked / started", started),
                          ("Expired (still listed by Hotspawn)", stale)):
        body.append("<h2>%s (%d)</h2>" % (e(label), len(subset)))
        if subset is stale:
            body.append('<p class="small">These fixtures are months old and cannot be picked in '
                        'Hotspawn&rsquo;s game. They are kept because Hotspawn still lists them, and '
                        'their ratings come from the official Valve standings in force at the match '
                        'date &mdash; not from today&rsquo;s standings.</p>')
        for r in subset:
            body.append(match_card(r, show_state=(subset is not open_rows)))
    pages["all.html"] = page("All fixtures", "all.html", "".join(body))

    # ---------------- tiers.html ----------------
    body = ['<p class="lede">Hotspawn assigns each fixture a tier and a point value. Tier S pays '
            'the most. The tier is Hotspawn&rsquo;s label, not ours, and is never used as a '
            'probability input.</p>']
    for t in ("S", "B", "C"):
        sub = [r for r in rows if r["tier"] == t]
        if not sub:
            continue
        op = [r for r in sub if r["state"] == "open"]
        body.append("<h2>Tier %s &mdash; %d fixtures (%d open)</h2>" % (e(t), len(sub), len(op)))
        tr = []
        for r in sorted(sub, key=lambda x: x["start_utc"]):
            tr.append('<tr data-search="%s"><td>%s</td><td>%s<br><span class="small">%s</span></td>'
                      '<td>%s</td><td class="num">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                      % (e(" ".join([r["team_a"], r["team_b"], r["competition"]])),
                         e(short_when(r["start_utc"])),
                         e(r["team_a"]), e(r["team_b"]),
                         e(r["pick"] or "—"),
                         e(win_pct_cell(r)),
                         '<span class="pill %s">%s</span>' % (e(r["pick_tier"]), e(r["pick_tier"])),
                         e(r["state"]),
                         src_cell([("Hotspawn", r["hotspawn_match_url"] or r["hotspawn_url"]),
                                   ("HLTV", r["hltv_match_url"]),
                                   ("Valve A", r["vrs_url_a"]), ("Valve B", r["vrs_url_b"])])))
        body.append(table(["Kickoff (UTC)", "Match", "Pick", "#Win %", "Tier", "State", "Sources"],
                          "".join(tr)))
    pages["tiers.html"] = page("By tier", "tiers.html", "".join(body))

    # ---------------- tournaments.html ----------------
    comps = {}
    for r in rows:
        comps.setdefault(r["competition"], []).append(r)
    body = ['<p class="lede">%d competitions. Each row links to the official source of every '
            'published value.</p>' % len(comps), searchbox()]
    for c in sorted(comps, key=lambda k: (-len(comps[k]), k)):
        sub = sorted(comps[c], key=lambda x: x["start_utc"])
        body.append("<h2>%s <span class=\"small\">(%d fixtures, %d open)</span></h2>"
                    % (e(c), len(sub), sum(1 for r in sub if r["state"] == "open")))
        tr = []
        for r in sub:
            tr.append('<tr data-search="%s"><td>%s</td><td>%s<br><span class="small">%s</span></td>'
                      '<td>%s</td><td class="num">%s</td><td>%s</td><td>%s</td></tr>'
                      % (e(" ".join([r["team_a"], r["team_b"]])), e(short_when(r["start_utc"])),
                         e(r["team_a"]), e(r["team_b"]), e(r["pick"] or "—"),
                         e(win_pct_cell(r)),
                         '<span class="pill %s">%s</span>' % (e(r["pick_tier"]), e(r["pick_tier"])),
                         src_cell([("Hotspawn", r["hotspawn_match_url"] or r["hotspawn_url"]),
                                   ("HLTV", r["hltv_match_url"]),
                                   ("Market", r["market_url"]),
                                   ("Valve A", r["vrs_url_a"]), ("Valve B", r["vrs_url_b"])])))
        body.append(table(["Kickoff (UTC)", "Match", "Pick", "#Win %", "Tier", "Sources"],
                          "".join(tr)))
    pages["tournaments.html"] = page("By tournament", "tournaments.html", "".join(body))

    # ---------------- market.html ----------------
    mkt = [r for r in rows if r["market_tier"]]
    body = ['<p class="lede">Every match an outside book prices. Probabilities are the book&rsquo;s '
            'own odds with the margin removed: <code>p(A) = (1/o_A) / (1/o_A + 1/o_B)</code>. '
            '<b>Tier A</b> is a primary bookmaker read by CI this cycle; <b>Tier B</b> is a named '
            'aggregator report we could not re-read at the book itself.</p>',
            '<p class="small">%d fixtures priced: %d tier A, %d tier B. '
            'EGamersWorld&rsquo;s <code>1.80/1.80</code> rows are its un-priced placeholder and are '
            'rejected, never de-vigged.</p>'
            % (len(mkt), counts["market_tier_A"], counts["market_tier_B"]), searchbox()]
    tr = []
    for r in sorted(mkt, key=lambda x: x["start_utc"]):
        tr.append('<tr data-search="%s"><td>%s</td><td>%s<br><span class="small">%s</span></td>'
                  '<td>%s</td><td class="num">%s</td><td class="num">%s</td>'
                  '<td class="num">%s%%</td><td class="num">%s%%</td><td class="num">%s%%</td>'
                  '<td>%s</td><td>%s</td><td>%s</td></tr>'
                  % (e(" ".join([r["team_a"], r["team_b"], r["market_book"]])),
                     e(short_when(r["start_utc"])), e(r["team_a"]), e(r["team_b"]),
                     e(r["market_book"]), e(r["market_odds_a"]), e(r["market_odds_b"]),
                     e(r["market_p_a_pct"]), e(r["market_p_b_pct"]), e(r["market_overround_pct"]),
                     '<span class="pill %s">%s</span>' % (e(r["market_tier"]), e(r["market_tier"])),
                     e(r["market_captured_utc"]),
                     src_cell([("price", r["market_url"]), ("Hotspawn",
                                                            r["hotspawn_match_url"] or
                                                            r["hotspawn_url"])])))
    body.append(table(["Kickoff (UTC)", "Match", "Book", "#Odds A", "#Odds B", "#p(A)", "#p(B)",
                       "#Overround", "Tier", "Read (UTC)", "Sources"], "".join(tr)))
    body.append('<h2>Model vs market</h2><p class="small">Where we have both, the gap in percentage '
                'points between our own Valve-standings line and the de-vigged market. Large gaps are '
                'review items, not corrections &mdash; we publish both.</p>')
    tr = []
    for r in sorted((x for x in rows if x["market_tier"] and x["own_p_a_pct"]),
                    key=lambda x: -abs(float(x["market_p_a_pct"]) - float(x["own_p_a_pct"]))):
        gap = float(r["market_p_a_pct"]) - float(r["own_p_a_pct"])
        tr.append('<tr><td>%s vs %s</td><td>%s</td><td class="num">%s%%</td><td class="num">%s%%</td>'
                  '<td class="num">%s%.1f pp</td><td>%s</td></tr>'
                  % (e(r["team_a"]), e(r["team_b"]), e(short_when(r["start_utc"])),
                     e(r["market_p_a_pct"]), e(r["own_p_a_pct"]),
                     "+" if gap >= 0 else "&minus;", abs(gap),
                     src_cell([("market", r["market_url"]), ("Valve A", r["vrs_url_a"]),
                               ("Valve B", r["vrs_url_b"])])))
    body.append(table(["Match", "Kickoff (UTC)", "#Market p(A)", "#Our p(A)", "#Gap", "Sources"],
                      "".join(tr)))
    pages["market.html"] = page("Outside betting lines", "market.html", "".join(body))

    # ---------------- own-lines.html ----------------
    own = [r for r in rows if r["own_p_a_pct"]]
    body = ['<p class="lede">Our own originated line for every fixture whose two teams both resolve '
            'to an official Valve standing. No Hotspawn input is used.</p>',
            '<div class="panel"><b>Formula</b><br><code>p_map(A) = 1 / (1 + 10^(-k &middot; '
            '(pts_A &minus; pts_B) / 400))</code> with <b>k = %s</b>.<br><span class="small">%s'
            '<br>Series: BO1 identity; BO3 <code>p&sup2;(3-2p)</code>; BO5 '
            '<code>p&sup3;(10-15p+6p&sup2;)</code>. Both series transforms are strictly increasing '
            'and fix 0.5, so <b>the favourite side never depends on the format</b> &mdash; only the '
            'margin does. That is why an unverified format still supports a pick, and is labelled as '
            'a single-map estimate.</span></div>'
            % (e(cov["model"]["k"]), e(cov["model"]["k_basis"])),
            '<p class="small">%d fixtures have our own line. Where Valve publishes two rows with the '
            'same team name, the headline probability is the <b>conservative</b> bound and the full '
            'range is printed.</p>' % len(own), searchbox()]
    tr = []
    for r in sorted(own, key=lambda x: x["start_utc"]):
        tr.append('<tr data-search="%s"><td>%s</td><td>%s<br><span class="small">%s</span></td>'
                  '<td>%s<br><span class="small">#%s &middot; %s pts &middot; %s</span></td>'
                  '<td>%s<br><span class="small">#%s &middot; %s pts &middot; %s</span></td>'
                  '<td class="num">%s%%</td><td class="num">%s%%</td>'
                  '<td class="num">%s</td><td>%s</td><td>%s</td></tr>'
                  % (e(" ".join([r["team_a"], r["team_b"], r["competition"]])),
                     e(short_when(r["start_utc"])),
                     e("%s vs %s" % (r["team_a"], r["team_b"])), e(r["competition"]),
                     e(r["team_a"]), e(r["vrs_rank_a"] or "—"), e(r["vrs_points_a"] or "—"),
                     e(r["vrs_period_a"] or "—"),
                     e(r["team_b"]), e(r["vrs_rank_b"] or "—"), e(r["vrs_points_b"] or "—"),
                     e(r["vrs_period_b"] or "—"),
                     e(r["own_p_a_pct"]), e(r["own_p_b_pct"]),
                     e(("%s–%s%%" % (r["own_p_lo_pct"], r["own_p_hi_pct"]))
                       if r["own_p_lo_pct"] != r["own_p_hi_pct"] else "—"),
                     e(r["rating_note"] or "—"),
                     src_cell([("Valve A", r["vrs_url_a"]), ("Valve B", r["vrs_url_b"])])))
    body.append(table(["Kickoff (UTC)", "Match", "Team A (Valve VRS)", "Team B (Valve VRS)",
                       "#Our p(A)", "#Our p(B)", "#Range", "Notes", "Official source"], "".join(tr)))
    pages["own-lines.html"] = page("Our own lines", "own-lines.html", "".join(body))

    # ---------------- ratings.html ----------------
    nteams = len({t["hotspawn_team"] for t in teams})
    body = ['<p class="lede">How each of the <b>%d</b> team names on Hotspawn resolved to an '
            'official Valve Regional Standings row &mdash; one line per (name, rating period), '
            'because the same name can legitimately resolve to a different Valve row in a '
            'different month (<b>WROTBERRY</b> is itself in Valve\'s June standings but is '
            '<b>WBT</b> by October). Where a name could not be resolved from an official source '
            'it says so, and no rating was used.</p>' % nteams,
            '<p class="small">Publisher: <a href="%s" rel="noopener">Valve Corporation &mdash; '
            'counter-strike_regional_standings</a>, pinned commit <code>%s</code>. Periods used: %s. '
            'Selection rule: %s</p>'
            % (VALVE_REPO, e(cov["official_rating_source"]["pinned_commit"][:12]),
               e(", ".join(cov["official_rating_source"]["periods_used"])),
               e(cov["official_rating_source"]["selection_rule"])), searchbox()]
    def rating_evidence(t: dict) -> str:
        parts: list[str] = []
        if t["alias"]:
            if t["alias_evidence"]:
                parts.append('<div class="small">%s</div>' % e(t["alias_evidence"]))
            for u in [x for x in t["alias_urls"].split(";") if x]:
                parts.append('<a href="%s" rel="noopener">evidence</a>' % e(u))
        elif t["unranked_finding"]:
            parts.append('<div class="small">%s</div>' % e(t["unranked_finding"]))
            for u in [x for x in t["unranked_urls"].split(";") if x]:
                parts.append('<a href="%s" rel="noopener">evidence</a>' % e(u))
        if t["source_url"]:
            parts.append('<a href="%s" rel="noopener">Valve row</a>' % e(t["source_url"]))
        return " ".join(parts) if parts else '<span class="blank">no official source</span>'

    tr = []
    for t in sorted(teams, key=lambda x: (x["hotspawn_team"].lower(), x["rating_period"])):
        cand = t["candidate_standings"] or '<span class="blank">none</span>'
        tr.append('<tr data-search="%s"><td><b>%s</b></td><td>%s</td><td>%s</td><td>%s</td>'
                  '<td>%s</td><td>%s</td><td class="small">%s</td></tr>'
                  % (e(t["hotspawn_team"] + " " + (t["resolved_vrs_name"] or "")
                       + " " + t["rating_period"]),
                     e(t["hotspawn_team"]),
                     e(t["resolved_vrs_name"] or '<span class="blank">ambiguous</span>'),
                     e(t["rating_period"] or "—"),
                     e(cand), e(t["alias"] or "—"), rating_evidence(t),
                     e(t.get("fixtures", "") or "—")))
    body.append(table(["Hotspawn name", "Valve name", "Rating period", "Candidate Valve rows",
                       "Alias applied", "Evidence / official source", "Used by fixtures"],
                      "".join(tr)))
    pages["ratings.html"] = page("Team ratings", "ratings.html", "".join(body))

    # ---------------- methodology.html ----------------
    pages["methodology.html"] = page("Methodology", "methodology.html", METHODOLOGY % {
        "k": e(cov["model"]["k"]), "kbasis": e(cov["model"]["k_basis"]),
        "kn": e(cov["model"]["k_calibrated_on"]), "gen": e(gen),
        "atot": counts["fixtures_total"], "otot": counts["state_open"],
        "lobby": HOTSPAWN_LOBBY, "cs2": HOTSPAWN_CS2,
    })

    # ---------------- sources.html ----------------
    srcs = cov["official_rating_source"]
    commit = srcs["pinned_commit"]
    tr = "".join(
        '<tr><td><code>%s</code></td><td class="small"><code>%s</code></td>'
        '<td><a href="%s/blob/%s/live/2026/%s" rel="noopener">Valve &middot; live/2026/%s</a></td></tr>'
        % (e(k), e(v), VALVE_REPO, e(commit), e(k.replace(".gz", "")), e(k.replace(".gz", "")))
        for k, v in sorted(srcs["files"].items()))
    pages["sources.html"] = page("Sources", "sources.html", SOURCES % {
        "gen": e(gen), "cap": e(cap), "commit": e(commit),
        "vrsfiles": tr, "nflags": counts["flags"], "k": e(cov["model"]["k"]),
        "lobby": HOTSPAWN_LOBBY, "cs2": HOTSPAWN_CS2,
    })

    # ---------------- flagged.html ----------------
    sev_order = {"NEEDS REVIEW": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
    fl = sorted(flags, key=lambda f: (sev_order.get(f["severity"], 9), f["code"]))
    by_code = {}
    for f in fl:
        by_code.setdefault(f["code"], []).append(f)
    body = ['<p class="lede"><b>%d</b> items we could not confirm from an official source, or where '
            'two official sources disagree. None of them blocks publication, and none of them was '
            'filled in with a guess &mdash; the affected value is blank on the board.</p>' % len(fl)]
    for code in sorted(by_code):
        body.append("<h2>%s <span class=\"small\">(%d)</span></h2>" % (e(code), len(by_code[code])))
        tr = []
        for f in by_code[code]:
            tr.append('<tr><td class="small"><code>%s</code></td><td>%s</td><td>%s</td>'
                      '<td>%s</td><td>%s</td></tr>'
                      % (e(f["flag_id"]), e(f["severity"]), e(f["subject"]), e(f["detail"]),
                         src_cell([("official", f["official_source_url"])]
                                  + [("source", u) for u in f["other_source_urls"].split(";")
                                     if u])))
        body.append(table(["Flag id", "Severity", "Item", "What we found", "Sources"],
                          "".join(tr)))
    body.append(IRREGULARITIES)
    pages["flagged.html"] = page("Flagged for review", "flagged.html", "".join(body))

    os.makedirs(OUT, exist_ok=True)
    for name, content in pages.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as fh:
            fh.write(content)
    for extra in ("style.css", "app.js"):
        pass
    with open(os.path.join(OUT, ".nojekyll"), "w", encoding="utf-8") as fh:
        fh.write("")
    print("[5bcfd1b5] wrote %d pages to allpicks/" % len(pages))
    return pages


METHODOLOGY = """
<p class="lede">Exactly how every number on this board is produced, and what we refuse to produce.
Generated %(gen)s.</p>

<h2>1. What Hotspawn gives us &mdash; and what it does not</h2>
<div class="panel">
<p>From <a href="%(lobby)s" rel="noopener">play.hotspawn.com/lobby</a> and
<a href="%(cs2)s" rel="noopener">/cs2-pickems</a> we take <b>fixture identity only</b>: the fixture
id, the two team names, the competition, Hotspawn's tier and point value, and the UTC start and lock
epochs embedded in the page's Angular <code>TransferState</code> payload.</p>
<p><b>Hotspawn's &ldquo;%% picked&rdquo; figures are never used as a probability.</b> They are a crowd
poll of the site's own users, sampled at an unknown size, and the brief for this project excludes them
explicitly. The same rule applies to HLTV's &ldquo;Pick a winner&rdquo; vote, which is also a crowd
poll (for example HLTV shows 87.5%%/12.5%% on fixture 1079624; that number appears nowhere in our
output).</p>
</div>

<h2>2. Coverage: %(atot)d fixtures, %(otot)d open</h2>
<div class="panel">
<p>Hotspawn's own tier filter reports 88&ndash;89 CS2 fixtures while its page header says
&ldquo;68 matches this week&rdquo;. We publish what the payload actually contains &mdash;
<b>%(atot)d</b> CS2 rows &mdash; and record the disagreement as a flag rather than claiming the
header proves coverage. Of those, <b>%(otot)d</b> have a lock time still in the future and are
pickable; 2 are locked/started; the remainder are June&ndash;July 2026 fixtures Hotspawn still
carries.</p>
</div>

<h2>3. Outside market lines</h2>
<div class="panel">
<p>A bookmaker price is converted to a two-way probability by removing the overround:</p>
<p><code>p(A) = (1/o_A) / (1/o_A + 1/o_B)</code> &nbsp;&nbsp;
<code>overround = (1/o_A + 1/o_B &minus; 1) &times; 100</code></p>
<ul class="tight">
<li><b>Tier A</b> &mdash; a primary bookmaker's own public price feed, read by CI during the run
(Pinnacle's public guest moneyline endpoint, the payload its CS2 matchups page loads). Decimal odds
are converted from the American prices in that response.</li>
<li><b>Tier B</b> &mdash; a book price we could not re-read during this build. Two kinds, labelled
apart on every row: a <b>direct read of a primary book&rsquo;s own price feed</b> at an earlier
timestamp (Pinnacle&rsquo;s public guest API, read 2026-10-14T01:48Z by session
<code>arena/8944bb84</code>), and a <b>named aggregator&rsquo;s report</b> of a book price
(EGamersWorld reporting bc.game). We print the book, the exact URL carrying those numbers and the
read time, and we state plainly that the price was not re-read this cycle.</li>
<li><b>Citation integrity:</b> the book label, the odds and the source URL on a row always come from
the <em>same</em> read. Eight fixtures carry two independent reads upstream whose numbers differ
&mdash; for example Pinnacle 2.700/1.410 against EGamersWorld&rsquo;s bc.game 2.450/1.480 on
fixture 1079546. The primary read wins and the other is printed as a labelled cross-check, never
mixed into one row.</li>
<li><b>Rejected:</b> EGamersWorld prints <code>1.80/1.80</code> when it has no price. Identical
prices on both sides carry zero information, so those rows are rejected and flagged, never
de-vigged into a fake 50/50.</li>
<li><b>Orientation:</b> aggregators do not always list the teams in Hotspawn's order. Odds are mapped
by team name, not by column position, and every swap is recorded in
<code>data/5bcfd1b5/market_reads.csv</code>.</li>
</ul>
</div>

<h2>4. Our own line</h2>
<div class="panel">
<p><code>p_map(A) = 1 / (1 + 10^(-k &middot; (pts_A &minus; pts_B) / 400))</code></p>
<p><b>k = %(k)s</b> &mdash; %(kbasis)s, fitted on %(kn)s of Valve's own published match results.
This constant is inherited from <code>main</code>'s calibrated model
(<code>cs2/data/summary.json</code>) and is read at build time, not hard-coded.</p>
<p>Series transform from a single-map probability: BO1 identity; BO3 <code>p&sup2;(3-2p)</code>;
BO5 <code>p&sup3;(10-15p+6p&sup2;)</code>. Both transforms are strictly increasing on [0,1] and fix
0.5, so <b>the favourite side is format-invariant</b>. Where the format is unverified we publish the
single-map estimate and label it as such; the pick is still sound.</p>
<p><b>Rating input:</b> official Valve Regional Standings points for the period <em>in force at the
match date</em> &mdash; the latest Valve publication on or before that date. If the team is absent
there, we use the earliest later official period containing that exact name and flag the row as
anachronistic. This is the single biggest reason the previous boards had 25 blank picks: they read
only the 2026-10-05 file, but 23 of the blank fixtures were played in June and July 2026.</p>
</div>

<h2>5. Pick hierarchy</h2>
<div class="panel">
<p>The first tier with a usable input decides the pick. Tiers are never averaged.</p>
<ul class="tight">
<li><b>A</b> &mdash; primary book moneyline, de-vigged.</li>
<li><b>B</b> &mdash; named secondary book moneyline, de-vigged.</li>
<li><b>C</b> &mdash; our own line, both teams uniquely ranked in the official Valve standings in
force at the match date.</li>
<li><b>D</b> &mdash; our own line where a rating needed a roster-verified alias, a pinned
duplicate-name row, or a later Valve period. Same arithmetic, weaker provenance, labelled.</li>
<li><b>E</b> &mdash; directional only: one side officially ranked, the other confirmed unranked in
every Valve period and on HLTV. A pick is published; the probability is <b>deliberately blank</b>
because no official number exists for the unranked side.</li>
<li><b>F</b> &mdash; no pick: no official rating for both sides and no market price. Blank and
flagged.</li>
</ul>
</div>

<h2>6. Duplicate team names in Valve's own file</h2>
<div class="panel">
<p>Valve's standings legitimately contain more than one row with the same team name (an active
five-man roster and an older or partial one). We handle this in two ways and never guess:</p>
<ul class="tight">
<li>If a roster check pins one row &mdash; inherited from <code>data/8944bb84/ratings.csv</code> and
<b>re-verified line by line against Valve's file</b> before use (94 accepted, 0 rejected) &mdash; that
row is used and the pin is cited.</li>
<li>Otherwise <b>every</b> same-name row stays admissible and we evaluate all combinations. If they
all agree on the favourite, the pick is published at the <b>conservative</b> bound of the probability
range and the range is printed. If they disagree on the favourite, no probability and no pick are
published at all.</li>
</ul>
</div>

<h2>7. What we never do</h2>
<div class="panel">
<ul class="tight">
<li>No invented odds, timestamps, ratings, rosters or formats.</li>
<li>No 50/50 fallback, no averaging of market and model, no crowd poll as a probability.</li>
<li>No mixing of HLTV's <code>VRS: #N</code> badge numbers with Valve's published standings. They are
different snapshots: HLTV shows HEROIC as &ldquo;VRS #22&rdquo; while Valve's 2026-10-05 file ranks
HEROIC #15 (1550 pts). We use Valve's file and cite the exact line.</li>
<li>Unverifiable means blank plus a flag on <a href="flagged.html">Flagged for review</a>.</li>
</ul>
</div>

<h2>8. Limits</h2>
<div class="panel">
<p>Valve's standings are published roughly monthly, so a rating can be weeks older than the match and
cannot reflect a last-minute roster change. A points logistic is a coarse model: it knows nothing
about map pool, form, travel or a team's motivation in a dead rubber. Aggregator prices can drift
within the hour, and we print the read time so you can judge the age yourself. Locked and expired
fixtures cannot be picked in Hotspawn's game; their rows are archival and are labelled as such.
Nothing here is betting advice.</p>
</div>
"""

SOURCES = """
<p class="lede">Every source used to build this board, with what was taken from it. Board generated
%(gen)s from a Hotspawn capture at %(cap)s.</p>

<h2>Fixture identity and schedule</h2>
<div class="panel"><ul class="tight">
<li><a href="%(lobby)s" rel="noopener">play.hotspawn.com/lobby</a> &mdash; fixture ids, team names,
competition, tier, points, and the Angular <code>TransferState</code> payload carrying UTC start and
lock epochs. <b>Identity and schedule only.</b> Its &ldquo;%% picked&rdquo; crowd poll is never a
probability input.</li>
<li><a href="%(cs2)s" rel="noopener">play.hotspawn.com/cs2-pickems</a> &mdash; the CS2-filtered view,
read in full (all chunks) and cross-checked against the lobby payload.</li>
<li><a href="https://www.hotspawn.com/matches" rel="noopener">hotspawn.com/matches</a> &mdash;
per-fixture permalink where Hotspawn publishes one. Four CCT Europe Series #12 Play-In fixtures have
no permalink; those rows link the lobby and the official HLTV match page instead.</li>
</ul></div>

<h2>Team ratings (official)</h2>
<div class="panel">
<p>Publisher: <b>Valve Corporation</b>. Repository:
<a href="https://github.com/ValveSoftware/counter-strike_regional_standings" rel="noopener">
ValveSoftware/counter-strike_regional_standings</a>. Pinned commit
<code>%(commit)s</code> (HEAD of <code>live/2026</code> at capture time).</p>
<p>Files committed to this repository under <code>data/5bcfd1b5/vrs/</code>, with the SHA-256 of each
gzipped copy so any reader can prove the bytes we used:</p>
<div class="tw"><table><thead><tr><th>File</th><th>SHA-256 (gzipped)</th><th>Upstream</th></tr>
</thead><tbody>%(vrsfiles)s</tbody></table></div>
<p class="small">Selection rule: the latest official publication on or before the match date; if the
team is absent there, the earliest later official period containing that exact name, flagged as
anachronistic.</p>
</div>

<h2>Outside market prices</h2>
<div class="panel"><ul class="tight">
<li><b>Pinnacle</b> &mdash; public guest moneyline feed
(<code>guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight</code>), the payload
<a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/" rel="noopener">Pinnacle's own CS2
matchups page</a> loads. Read by CI; tier A. Note: this endpoint returns HTTP 401 without a token from
our build sandbox, so tier-A rows come from <code>main</code>'s scheduled CI capture
(<code>cs2/data/market_rows.csv</code>) rather than from a live read in this session.</li>
<li><b>EGamersWorld reporting BC.Game</b> &mdash;
<a href="https://egamersworld.com/counterstrike/matches" rel="noopener">
egamersworld.com/counterstrike/matches</a> and the per-match pages it links. Tier B: an aggregator's
report of a book price, not a re-read at the book. 14 prices were read live during this session and
are recorded with their exact URLs and read times in
<code>data/5bcfd1b5/market_reads.csv</code>; the remainder come from <code>main</code>'s committed
read at <code>data/8944bb84/external_lines.csv</code>.</li>
<li><b>Rejected:</b> <code>1.80/1.80</code> is EGamersWorld's un-priced placeholder. Those rows are
refused and flagged.</li>
</ul></div>

<h2>Match pages used for verification</h2>
<div class="panel"><ul class="tight">
<li><b>HLTV</b> &mdash; match pages, team pages, event pages and the world ranking. Used to confirm
rosters, formats, official results and name changes. HLTV's <code>VRS: #N</code> badges are a
<i>different, newer</i> Valve snapshot than Valve's published file and are never mixed with it.</li>
<li><b>Liquipedia</b> &mdash; used only to corroborate the 2026-06-01 Tricked&rarr;Echo transfer that
proves the <code>ex-Tricked</code> alias.</li>
</ul></div>

<h2>Not used</h2>
<div class="panel"><ul class="tight">
<li>Hotspawn crowd &ldquo;%% picked&rdquo; &mdash; crowd poll.</li>
<li>HLTV &ldquo;Pick a winner&rdquo; vote &mdash; crowd poll.</li>
<li>Polymarket &mdash; no CS2 market for these fixtures was reachable in this session; it is not a
source for any number here.</li>
<li>Any historical session price carried forward into a current pick.</li>
</ul></div>

<h2>Reproduce</h2>
<div class="panel"><pre style="overflow-x:auto;font-size:.8rem"><code>python3 scripts/5bcfd1b5_build.py   # resolve ratings, read markets, decide picks
python3 scripts/5bcfd1b5_site.py    # render allpicks/ from the committed CSVs
python3 -m unittest discover -s tests -p 'test_5bcfd1b5.py' -v</code></pre>
<p class="small">Both scripts are offline: they read only committed evidence. %(nflags)d flags are
published on <a href="flagged.html">Flagged for review</a>. The model constant k = %(k)s is read from
<code>cs2/data/summary.json</code> at build time.</p></div>
"""

IRREGULARITIES = """
<h2>Repository irregularities found during this review</h2>
<p class="lede">Raised while reviewing <code>main</code> line by line against official sources. Each
has the source we checked. None blocks publication; all are for human review.</p>
<div class="tw"><table><thead><tr><th>ID</th><th>Finding</th><th>Evidence</th></tr></thead><tbody>
<tr><td><b>IR-05-01</b></td>
<td><b>Period-mismatch caused 23 of main's 25 blank picks.</b> Every board on <code>main</code>
resolves team ratings against Valve's <code>standings_global_2026_10_05.md</code> only. 23 fixtures
were played 2026-06-26 to 2026-07-10, so the October file is the wrong official source: the teams
are ranked in Valve's 2026-06-01 and 2026-07-06 files. Fixed here by selecting the period in force at
the match date.</td>
<td><a href="https://github.com/ValveSoftware/counter-strike_regional_standings/tree/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026" rel="noopener">Valve live/2026 directory</a></td></tr>

<tr><td><b>IR-05-02</b></td>
<td><b>Galorys was marked unrated although Valve ranks it.</b> <code>data/8944bb84/analysis.csv</code>
leaves <code>vrs_standing_b</code> blank for fixture 1081076 (ex-Keyd Stars vs Galorys) and
<code>ratings.csv</code> has no Galorys row, yet Valve's 2026-10-05 standings rank
<b>Galorys #85 with 1099 pts</b> at line 90. A lookup gap, not a data gap.</td>
<td><a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L90" rel="noopener">Valve standings line 90</a></td></tr>

<tr><td><b>IR-05-03</b></td>
<td><b>HLTV's <code>VRS: #N</code> badges do not match Valve's published standings.</b> HLTV's match
2399137 shows HEROIC &ldquo;VRS: #22&rdquo; while Valve's 2026-10-05 file ranks HEROIC <b>#15</b>
(1550 pts). HLTV's match 2399301 shows LFO 10 &ldquo;VRS: #169&rdquo; while Valve's file ranks
<b>Honvéd #169</b> (788 pts) and contains no LFO 10 at all. HLTV is rendering a newer Valve snapshot
(its links point at <code>/valve-ranking/teams/2026/october/14</code>). Mixing the two numbering
systems silently would corrupt every rating, so this board uses Valve's file exclusively and cites
the exact line.</td>
<td><a href="https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii" rel="noopener">HLTV 2399137</a> ·
<a href="https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11" rel="noopener">HLTV 2399301</a> ·
<a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L20" rel="noopener">Valve line 20</a></td></tr>

<tr><td><b>IR-05-04</b></td>
<td><b>Two boards on <code>main</code> disagree about the team &ldquo;Envy&rdquo;.</b>
<code>data/8944bb84/ratings.csv</code> asserts <code>Envy → 3DMAX</code> (VRS #21), while
<code>COORDINATION.md</code> records an earlier session's claim of &ldquo;Envy #20 / VRS #27&rdquo;
(VRS #27 is <b>GamerLegion</b>). We settled it from the official sources: HLTV's match 2399137 lineup
for Envy is Graviti, Kursy, Maka, misutaaa, Lucky &mdash; a <b>5/5 exact match</b> to Valve's #21 row
&ldquo;3DMAX&rdquo;. <code>Envy = 3DMAX</code> is correct; the #27 claim is wrong. Note
<code>cs2/data/analysis.csv</code> leaves Envy blank rather than asserting either, which is why this
only affected one board.</td>
<td><a href="https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii" rel="noopener">HLTV 2399137 lineups</a> ·
<a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L26" rel="noopener">Valve line 26</a></td></tr>

<tr><td><b>IR-05-05</b></td>
<td><b>Market prices drift inside an hour and the boards do not always say which read they show.</b>
For fixture 1080177 (Falcons vs Ninjas in Pyjamas) <code>data/8944bb84/external_lines.csv</code>
records Pinnacle 1.254/4.010 at 01:48Z while <code>cs2/data/market_rows.csv</code> records Pinnacle
1.27027/3.85 at 02:35:36Z. For 1080176 (9z vs Aurora) the same two files record 3.550/1.307 and
3.41/1.325733. Both are real reads of a moving market; neither is wrong, but a reader comparing pages
sees different numbers for the same match. This board prints the read time on every price row.</td>
<td><a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/" rel="noopener">Pinnacle CS2 matchups</a></td></tr>

<tr><td><b>IR-05-06</b></td>
<td><b>Hotspawn's own counts disagree with its payload.</b> The CS2 page header says &ldquo;68 matches
this week&rdquo; and its tier filter says &ldquo;All tiers (88)&rdquo;, while the
<code>TransferState</code> payload in the same response holds 89 CS2 rows (the lobby holds 89 and
renders 29 cards). We publish all payload rows and record the disagreement instead of asserting that
a successful parse proves coverage.</td>
<td><a href="https://play.hotspawn.com/cs2-pickems" rel="noopener">play.hotspawn.com/cs2-pickems</a></td></tr>

<tr><td><b>IR-05-07</b></td>
<td><b>Four fixtures have no Hotspawn permalink.</b> The CCT Europe 2026 Series #12 Play-In fixtures
(1081111 Enjoy vs B8 Academy, 1081112 Banda chuya vs 6666, 1081113 Ryvex vs PCIFIC, 1081120 mellren
vs Privateer) have no <code>/matches/&hellip;</code> URL in Hotspawn's payload. This board links the
CS2 lobby and the official HLTV match page for those rows instead of printing a broken link. This is
also the null-permalink bug that crashed <code>model/build.py</code> in CI run 38489574648.</td>
<td><a href="https://www.hltv.org/events/9456/cct-2026-europe-series-12-closed-qualifier" rel="noopener">HLTV event 9456</a></td></tr>

<tr><td><b>IR-05-08</b></td>
<td><b>EGamersWorld lists fixture 1079624 with no away team.</b> Its row for
&ldquo;FORZE Reload&rdquo; on 14.10.26 19:00 has an empty opponent string in both the link text and
the title, priced 1.80/1.80. Hotspawn names the opponent LFO 10 and HLTV confirms the fixture, so the
aggregator row is incomplete rather than the fixture being unplayed. No price was taken from it.</td>
<td><a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3" rel="noopener">EGW match row</a> ·
<a href="https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11" rel="noopener">HLTV 2399301</a></td></tr>

<tr><td><b>IR-05-09</b></td>
<td><b>Stale PR #54 is still open.</b> <code>arena/9920c263-maltaproj1</code> (PR #54) has been open
since 2026-10-13T22:47Z and was already recorded as needing disposition by an earlier session
(flag U-F-7). It is left untouched here; the integration owner should close or rebase it.</td>
<td><a href="https://github.com/buffedlizard55-lab/MaltaProj1/pull/54" rel="noopener">PR #54</a></td></tr>

<tr><td><b>IR-05-10</b></td>
<td><b>Two published boards give different own-line probabilities for the same fixtures.</b>
<code>slate/data/analysis.csv</code> and <code>cs2/data/analysis.csv</code> both compute a Valve-points
logistic but use different constants (a project-assumed 400-point scale with no fitted k, versus the
calibrated k = %(k)s) and different rating periods. They are not interchangeable. This board states
its own constant and period on every row and does not modify either of theirs.</td>
<td><a href="https://buffedlizard55-lab.github.io/MaltaProj1/slate/methodology.html" rel="noopener">slate methodology</a> ·
<a href="https://buffedlizard55-lab.github.io/MaltaProj1/cs2/methodology.html" rel="noopener">cs2 methodology</a></td></tr>
<tr><td><b>IR-05-11</b></td>
<td><b><code>data/8944bb84/external_lines.csv</code> carries two different market reads per row with
no marker saying which one is published.</b> Each row holds <code>primary_book</code> /
<code>primary_odds_*</code> / <code>primary_source_url</code> <i>and</i> <code>egw_odds_*</code> /
<code>egw_url</code>. On 8 fixtures the two reads disagree (1079546 Pinnacle 2.700/1.410 vs
EGamersWorld bc.game 2.450/1.480; 1080176 3.550/1.307 vs 3.870/1.200; 1080177 1.254/4.010 vs
1.190/3.950; plus 1079439, 1079440, 1079442, 1080178, 1080179). A consumer that takes the label
from one column group and the numbers from the other silently misattributes the price &mdash; the
first draft of this board did exactly that on all 8 rows, labelling EGamersWorld&rsquo;s numbers
&ldquo;Pinnacle (Direct)&rdquo;. Fixed here: label, odds and URL now always come from the same read,
and the other read is printed as a labelled cross-check. Recorded because the trap is live for every
downstream board reading that file.</td>
<td><a href="https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638279105/markets/related/straight" rel="noopener">Pinnacle read for 1079546</a> ·
<a href="https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_" rel="noopener">EGamersWorld read for 1079546</a></td></tr>
</tbody></table></div>
""" % {"k": "0.4630"}


if __name__ == "__main__":
    build()
