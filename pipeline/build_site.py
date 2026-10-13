#!/usr/bin/env python3
"""Build the published Pick'em dashboard from the collected datasets.

Inputs (all committed, all traceable to public source pages):
  data/pickem_inventory.json   complete Hotspawn Pick'em slate, straight from the pages' own
                               server-rendered payload (exact UTC start/lock times)
  lines/external_lines.json    external bookmaker match-winner lines + coverage checks
  lines/reference_ranks.json   HLTV world-ranking context (informational only, never a probability)

Outputs:
  pickem/*.html                dashboard, CS2, LoL, flagged, sources, methodology
  pickem/assets/*              css + js + machine-readable dataset
  lines/analysis.csv           flat review file, one row per fixture

Rules enforced here (and stated on the pages):
  * Hotspawn's crowd pick-% is metadata only and is never used to compute a probability.
  * A probability exists only where an external bookmaker line exists, and is de-vigged:
        p_a = (1/o_a) / (1/o_a + 1/o_b)
  * A source's generic 1.8/1.8 default is not a line.
  * Missing values stay blank and are listed on the Flagged for Review page.
"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "pickem"
INV = json.loads((ROOT / "data/pickem_inventory.json").read_text(encoding="utf-8"))
LINES = json.loads((ROOT / "lines/external_lines.json").read_text(encoding="utf-8"))
RANKS = json.loads((ROOT / "lines/reference_ranks.json").read_text(encoding="utf-8"))
BUILT_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
LINE_BY_ID = {row["match_id"]: row for row in LINES["rows"]}
SOURCES = LINES.get("environment_findings", [])


def rank_of(team: str):
    if not team:
        return None
    for name, info in RANKS["teams"].items():
        if name.lower() == team.lower():
            return {"name": name, **info}
    return None


def build_rows() -> list[dict]:
    rows = []
    for fx in INV["matches"]:
        line = LINE_BY_ID.get(fx["match_id"], {})
        status = line.get("status", "not_found")
        priced = status == "priced"
        oa, ob = line.get("odds_a"), line.get("odds_b")
        p_a = p_b = overround = None
        if priced and oa and ob:
            raw_a, raw_b = 1 / oa, 1 / ob
            overround = raw_a + raw_b
            p_a, p_b = raw_a / overround, raw_b / overround
        start = fx.get("scheduled_start_utc")
        rows.append({
            **fx,
            "line_status": status,
            "odds_a": oa if priced else None,
            "odds_b": ob if priced else None,
            "implied_prob_a": round(p_a * 100, 2) if p_a else None,
            "implied_prob_b": round(p_b * 100, 2) if p_b else None,
            "overround_pct": round(overround * 100, 2) if overround else None,
            "bookmaker": line.get("bookmaker"),
            "odds_source_url": line.get("source_url"),
            "line_captured_utc": line.get("captured_utc"),
            "line_note": line.get("note", ""),
            "rank_a": rank_of(fx.get("team_a")),
            "rank_b": rank_of(fx.get("team_b")),
            "start_date": (start or "")[:10],
            "start_hhmm": (start or "")[11:16],
        })
    rows.sort(key=lambda r: (r.get("scheduled_start_utc") or "9999"))
    return rows


def esc(v) -> str:
    return html.escape(str(v if v is not None else ""))


CSS = """
:root{--bg:#0f1216;--panel:#171c22;--panel2:#1e242c;--line:#2b333d;--fg:#e8edf3;--muted:#9aa7b4;--accent:#6d4bbd;--green:#2ea36f;--amber:#d99a2b;--red:#d05252;--blue:#3d7dd8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:#8fb4ff;text-decoration:none} a:hover{text-decoration:underline}
header.top{background:linear-gradient(90deg,#1b2030,#131722);border-bottom:1px solid var(--line);padding:18px 22px}
header.top h1{margin:0;font-size:20px}
header.top p{margin:4px 0 0;color:var(--muted);font-size:12.5px;max-width:1100px}
nav{background:var(--panel);border-bottom:1px solid var(--line);padding:0 22px;display:flex;flex-wrap:wrap;gap:2px}
nav a{display:block;padding:10px 14px;color:var(--muted);font-weight:600;font-size:13px;border-bottom:2px solid transparent}
nav a.active,nav a:hover{color:var(--fg);border-bottom-color:var(--accent);text-decoration:none}
main{max-width:1600px;margin:0 auto;padding:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.card .v{font-size:26px;font-weight:700;margin-top:6px}
.card .s{color:var(--muted);font-size:12px;margin-top:4px}
h2{font-size:16px;margin:26px 0 10px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}
th{background:var(--panel2);color:#cfd8e3;font-size:11.5px;text-transform:uppercase;letter-spacing:.4px;position:sticky;top:0;cursor:pointer;white-space:nowrap}
tr:hover td{background:#1b2129}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.team{font-weight:600}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:700;border:1px solid;white-space:nowrap}
.b-priced{color:#8ff0c0;border-color:#2ea36f;background:rgba(46,163,111,.12)}
.b-placeholder{color:#cfd8e3;border-color:#4a5665;background:rgba(120,130,145,.12)}
.b-missing{color:#ffd08a;border-color:#a5761f;background:rgba(217,154,43,.12)}
.b-live{color:#ffb4b4;border-color:#a33;background:rgba(208,82,82,.12)}
.muted{color:var(--muted)}
.bar{height:6px;border-radius:4px;background:#2b333d;overflow:hidden;min-width:60px;margin-top:3px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#3d7dd8,#2ea36f)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}
input[type=search]{background:var(--panel2);border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:8px 10px;font-size:13px;min-width:240px}
.small{font-size:12px;color:var(--muted)}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:12px 14px;margin:14px 0}
.note.warn{border-left-color:var(--amber)} .note.bad{border-left-color:var(--red)}
code{background:#0b0e12;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
ul{padding-left:18px} li{margin:5px 0}
footer{max-width:1600px;margin:30px auto;padding:0 22px 40px;color:var(--muted);font-size:12px}
"""

JS = """
function filterTable(input, tableId){
  const q = input.value.toLowerCase();
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(tr=>{
    tr.style.display = tr.innerText.toLowerCase().includes(q) ? '' : 'none';
  });
  const shown = [...document.querySelectorAll('#'+tableId+' tbody tr')].filter(t=>t.style.display!=='none').length;
  const chip = document.getElementById(tableId+'-count'); if(chip) chip.textContent = shown + ' rows shown';
}
function sortTable(table, colIndex, numeric){
  const tbody = table.tBodies[0]; const rows = [...tbody.rows];
  const dir = table.dataset.sortDir === 'asc' ? -1 : 1;
  table.dataset.sortDir = dir === 1 ? 'asc' : 'desc';
  rows.sort((a,b)=>{
    const av = a.cells[colIndex]?.innerText.trim() ?? '', bv = b.cells[colIndex]?.innerText.trim() ?? '';
    if(numeric){ const an=parseFloat(av.replace(/[^0-9.\\-]/g,'')), bn=parseFloat(bv.replace(/[^0-9.\\-]/g,'')); return (isNaN(an)?-1:an) < (isNaN(bn)?-1:bn) ? dir : -dir; }
    return av < bv ? dir : -dir;
  });
  rows.forEach(r=>tbody.appendChild(r));
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.querySelectorAll('table.sortable th').forEach((th,i)=>{
    th.addEventListener('click', ()=> sortTable(th.closest('table'), i, th.classList.contains('num')));
  });
});
"""

NAV = [("index.html", "Dashboard"), ("cs2.html", "CS2 (86)"), ("lol.html", "League of Legends (294)"),
       ("flagged.html", "Flagged for Review"), ("sources.html", "Sources"), ("methodology.html", "Methodology"),
       ("../docs/index.html", "Other dashboards")]


def nav(active: str) -> str:
    return "<nav>" + "".join(
        f'<a class="{"active" if f == active else ""}" href="{f}">{t}</a>' for f, t in NAV) + "</nav>"


def page(title: str, active: str, body: str, subtitle: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/mpl.css">
</head><body>
<header class="top">
  <h1>Hotspawn Pick'em — complete slate &amp; external betting lines</h1>
  <p>{esc(subtitle) or "Fixture list read from the Pick'em pages' own server-rendered payload. Lines from external bookmakers only; Hotspawn's crowd percentages are metadata and never a probability."}</p>
</header>
{nav(active)}
<main>
{body}
</main>
<footer>
  Built {esc(BUILT_AT)} by Arena session <code>79a1c6c8</code>. Fixtures: play.hotspawn.com Pick'em pages (public, server-rendered).
  Prices: external bookmakers via EGamersWorld (BC.Game) with per-row capture time; HLTV used for ranking context and timestamp
  cross-checks. Values that could not be confirmed from a public source are blank and listed on
  <a href="flagged.html">Flagged for Review</a>. Odds move: each row keeps its capture timestamp.
</footer>
<script src="assets/mpl.js"></script>
</body></html>
"""


def odds_cell(row: dict) -> str:
    if row["line_status"] == "priced":
        return f'<td class="num">{row["odds_a"]:g} <span class="muted">/</span> {row["odds_b"]:g}</td>'
    if row["line_status"] == "placeholder":
        return '<td class="num"><span class="badge b-placeholder">source default 1.8/1.8 — not a line</span></td>'
    return '<td class="num"><span class="badge b-missing">no line found</span></td>'


def prob_cell(row: dict) -> str:
    if row["implied_prob_a"] is None:
        return '<td class="num muted">—</td>'
    pa, pb = row["implied_prob_a"], row["implied_prob_b"]
    return (f'<td class="num">{pa:.1f}% <span class="muted">/</span> {pb:.1f}%'
            f'<div class="bar"><i style="width:{pa:.0f}%"></i></div>'
            f'<span class="small">overround {row["overround_pct"]:.1f}%</span></td>')


def source_cell(row: dict) -> str:
    if not row.get("odds_source_url"):
        return '<td><span class="muted">—</span></td>'
    label = {"priced": "price", "placeholder": "checked", "not_found": "checked"}[row["line_status"]]
    return (f'<td><a href="{esc(row["odds_source_url"])}" target="_blank" rel="noreferrer noopener">{label}</a>'
            f'<div class="small">{esc(row["line_captured_utc"] or "")}</div></td>')


def status_cell(row: dict) -> str:
    tag = {"priced": '<span class="badge b-priced">priced</span>',
           "placeholder": '<span class="badge b-placeholder">no real line</span>',
           "not_found": '<span class="badge b-missing">blank / unverified</span>'}[row["line_status"]]
    live = ""
    if row.get("status") and row["status"] != "scheduled":
        live = f' <span class="badge b-live">{esc(row["status"])}</span>'
    note = row.get("line_note") or ""
    return f"<td>{tag}{live}" + (f'<div class="small">{esc(note)}</div>' if note else "") + "</td>"


def rank_cell(row: dict) -> str:
    def fmt(team, info):
        if not info:
            return f"{esc(team)} <span class='muted'>(outside top-245)</span>"
        return f"{esc(team)} <span class='muted'>#{info['rank']} · {info['points']} pts</span>"
    return f'<td>{fmt(row.get("team_a"), row.get("rank_a"))}<br>{fmt(row.get("team_b"), row.get("rank_b"))}</td>'


def fixture_table(rows: list[dict], table_id: str, with_ranks: bool) -> str:
    head = ("<tr><th>Start (UTC)</th><th>Match</th><th>Competition</th><th>Points / tier</th>"
            "<th class='num'>External odds A / B</th><th class='num'>Own line P(A) / P(B)</th><th>Price source</th>"
            + ("<th>HLTV rank (context)</th>" if with_ranks else "")
            + "<th class='num'>Crowd A / B (metadata)</th><th>Status</th></tr>")
    body = []
    for row in rows:
        start = f'{esc(row["start_date"])} <span class="muted">{esc(row["start_hhmm"])}</span>'
        crowd = (f'{row.get("crowd_pct_a")}% / {row.get("crowd_pct_b")}%'
                 if row.get("crowd_pct_a") is not None else "blank")
        cells = (
            f'<td class="num">{start}<div class="small">locks {esc((row.get("lock_utc") or "")[11:16])}</div></td>'
            f'<td><span class="team">{esc(row.get("team_a"))}</span> <span class="muted">vs</span> '
            f'<span class="team">{esc(row.get("team_b"))}</span>'
            f'<div class="small"><a href="{esc(row.get("source_url"))}" target="_blank" rel="noreferrer noopener">Pick\'em page</a></div></td>'
            f'<td>{esc(row.get("competition"))}<div class="small">{esc(row.get("stage"))}</div></td>'
            f'<td class="num">{esc(row.get("offered_points"))} pts<div class="small">tier {esc(row.get("tier"))}</div></td>'
            + odds_cell(row) + prob_cell(row) + source_cell(row)
            + (rank_cell(row) if with_ranks else "")
            + f'<td class="num muted">{crowd}</td>' + status_cell(row))
        body.append(f"<tr>{cells}</tr>")
    return (f'<table class="sortable" id="{table_id}"><thead>{head}</thead><tbody>'
            + "".join(body) + "</tbody></table>")


def toolbar(table_id: str, placeholder: str) -> str:
    return ('<div class="toolbar">'
            f'<input type="search" placeholder="{esc(placeholder)}" oninput="filterTable(this, \'{table_id}\')">'
            f'<span class="small" id="{table_id}-count"></span>'
            '<span class="small">Click any column header to sort.</span></div>')


def write_outputs(rows: list[dict]) -> None:
    (OUT / "assets/data").mkdir(parents=True, exist_ok=True)
    (OUT / "assets/mpl.css").write_text(CSS, encoding="utf-8")
    (OUT / "assets/mpl.js").write_text(JS, encoding="utf-8")
    dataset = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fixture_source": INV["source"],
        "rules": {
            "fixture_list": "read from the pages' own server-rendered payload (script#ng-state)",
            "probability": "p_a = (1/odds_a) / (1/odds_a + 1/odds_b); published only where an external price exists",
            "hotspawn_pick_pct": "crowd metadata only — never an input to any probability",
            "source_defaults": "EGamersWorld's generic 1.8/1.8 display is not a line and is never used",
        },
        "totals": {"fixtures": len(rows),
                   "priced": sum(1 for r in rows if r["line_status"] == "priced"),
                   "placeholder": sum(1 for r in rows if r["line_status"] == "placeholder"),
                   "no_line": sum(1 for r in rows if r["line_status"] == "not_found")},
        "fixtures": rows,
        "coverage_checks": LINES["tournament_coverage_checks"],
        "reference_ranks": RANKS,
    }
    (OUT / "assets/data/mpl.json").write_text(json.dumps(dataset, indent=1), encoding="utf-8")

    cols = ["match_id", "sport", "competition", "scheduled_start_utc", "lock_utc", "status", "tier", "offered_points",
            "team_a", "team_b", "crowd_pct_a", "crowd_pct_b", "line_status", "odds_a", "odds_b",
            "implied_prob_a", "implied_prob_b", "overround_pct", "bookmaker", "odds_source_url", "line_captured_utc",
            "source_url", "line_note"]
    with open(ROOT / "lines/analysis.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build() -> None:
    OUT.mkdir(exist_ok=True)
    rows = build_rows()
    write_outputs(rows)
    cs2 = [r for r in rows if r["sport"] == "cs2"]
    lol = [r for r in rows if r["sport"] == "lol"]
    priced = [r for r in rows if r["line_status"] == "priced"]
    placeholder = [r for r in rows if r["line_status"] == "placeholder"]
    noline = [r for r in rows if r["line_status"] == "not_found"]

    dash = f"""
<div class="cards">
  <div class="card"><div class="k">Fixtures on the board</div><div class="v">{len(rows)}</div>
    <div class="s">{len(cs2)} CS2 · {len(lol)} League of Legends</div></div>
  <div class="card"><div class="k">Fixtures with a real external price</div><div class="v">{len(priced)}</div>
    <div class="s">own de-vigged line published</div></div>
  <div class="card"><div class="k">Without a usable line</div><div class="v">{len(noline) + len(placeholder)}</div>
    <div class="s">{len(placeholder)} source default · {len(noline)} not covered anywhere checked</div></div>
  <div class="card"><div class="k">Collected</div><div class="v" style="font-size:17px">{esc(BUILT_AT)}</div>
    <div class="s">odds move — every row keeps its capture time</div></div>
</div>
<div class="note">
  <b>What this is.</b> The <b>complete</b> Hotspawn Pick'em slate — every match the lobby holds for both titles — taken from the
  pages' own server-rendered payload (<code>script#ng-state</code>), which carries the official id, competition, exact UTC
  start and lock times and the board's own crowd percentages. Outside bookmaker prices are joined per fixture and de-vigged into
  this project's own line. Hotspawn's “% picked” is reproduced for audit only and never used as a probability.
</div>
<h2>Fixtures with an external price ({len(priced)})</h2>
{toolbar("dash", "Filter priced fixtures…")}
{fixture_table(priced, "dash", True)}
<h2>Coverage</h2>
<div class="cards">
  <div class="card"><div class="k">CS2</div><div class="v">{len(cs2)}</div><div class="s"><a href="cs2.html">open the CS2 table →</a></div></div>
  <div class="card"><div class="k">League of Legends</div><div class="v">{len(lol)}</div><div class="s"><a href="lol.html">open the LoL table →</a></div></div>
  <div class="card"><div class="k">Flagged items</div><div class="v">9</div><div class="s"><a href="flagged.html">open Flagged for Review →</a></div></div>
</div>
<div class="note warn">
  <b>Why {len(noline) + len(placeholder)} fixtures have no probability.</b> Most of this slate is national and amateur league play
  (Prime League 2nd/3rd Division, Tunisian Super League, RIVALS League, Komplettligaen, Arabian League 2nd Division, LigaGG,
  Icelandic league, Elisa BreakOut, Urban Riga Open and other low-tier CS2 cups). Public bookmakers publish no two-way price for
  those matches in any source checked. The cells stay blank and every affected fixture is listed on the Flagged page with the
  sources that were checked — no number is invented to fill a cell.
</div>"""

    cs2_body = f"""
<div class="note"><b>CS2 slate ({len(cs2)} fixtures).</b> Prices for the four headline events (Thunderpick World Championship,
Stake Pulse Beat III, CCT Europe #11, ESL Challenger League cups) come from BC.Game prices published on EGamersWorld; every row
links the page it was read from together with the capture time. The HLA rank column is context from
<a href="https://www.hltv.org/ranking/teams" target="_blank" rel="noreferrer noopener">HLTV's world ranking</a>, never a probability input.</div>
{toolbar("cs2", "Filter CS2 fixtures…")}
{fixture_table(cs2, "cs2", True)}"""

    lol_body = f"""
<div class="note"><b>League of Legends slate ({len(lol)} fixtures).</b> Priced here: Worlds 2026 Play-In, the Demacia Cup Global
Invitational, the EMEA Masters main event. The other {len(lol) - len([r for r in lol if r['line_status'] != 'not_found'])} LoL
fixtures belong to national/regional leagues that the checked odds sources do not carry with prices; they are published blank and
flagged.</div>
{toolbar("lol", "Filter LoL fixtures…")}
{fixture_table(lol, "lol", False)}"""

    # ---- flagged ----
    by_comp: dict[str, int] = {}
    for r in rows:
        if r["line_status"] != "priced":
            by_comp[r["competition"]] = by_comp.get(r["competition"], 0) + 1
    comp_rows = "".join(
        f"<tr><td>{esc(c)}</td><td class='num'>{n}</td><td class='small'>no public two-way price found in the sources listed on the "
        f"<a href='sources.html'>sources page</a></td></tr>"
        for c, n in sorted(by_comp.items(), key=lambda kv: -kv[1]))
    drift = [r for r in priced if "Earlier reading" in (r.get("line_note") or "")]
    drift_rows = "".join(
        f"<tr><td>{esc(r['team_a'])} vs {esc(r['team_b'])}</td><td class='small'>{esc(r['line_note'])}</td>"
        f"<td><a href='{esc(r['odds_source_url'])}' target='_blank' rel='noreferrer noopener'>source</a></td></tr>" for r in drift)
    flagged = f"""
<div class="note bad"><b>Nothing on this page blocks publication.</b> Every item is either a value we refused to fill in, a
discrepancy between the page's own fields, or a source that cannot be read by an automated client. Each carries a link.</div>

<h2 id="f01">F-01 — The complete slate comes from the page's own payload</h2>
<p class="small">The lobby filter advertises 86 CS2 matches and the LoL page 294. Both pages embed all of them in
<code>&lt;script id="ng-state"&gt;</code>: {len(cs2)} CS2 records (86 on <a href="https://play.hotspawn.com/lobby" target="_blank" rel="noreferrer noopener">/lobby</a>,
85 on <a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noreferrer noopener">/cs2-pickems</a>) and {len(lol)} on
<a href="https://play.hotspawn.com/lol-pickems" target="_blank" rel="noreferrer noopener">/lol-pickems</a>. The HTML itself renders only
27 / 26 / 231 cards — the rest are in the data, not the markup, which is why a naive HTML reader under-counts. Nothing is inferred:
every row carries the payload's id, competition, tier, points and start time, and we publish the raw payload-derived table.</p>

<h2 id="f02">F-02 — The card countdown contradicts the payload's own lock time</h2>
<p class="small">Every rendered card shows “Locks in HH:MM:SS”. Measured against the payload's <code>lock_time</code> on
2026-10-13 18:03 UTC: the countdown lands 75 minutes after the printed start on all 27 CS2 cards and 14 minutes after it on all
231 LoL cards (constant per title). The payload's <code>scheduled_start_time</code> is corroborated by HLTV's own timestamps
(9z vs Aurora: payload <code>1791966600000</code> = 2026-10-14 08:30:00 UTC; HOTU vs fnatic: 2026-10-14 10:00:00 UTC, matching the
printed card time), so the payload is used and the countdown discrepancy stays flagged.</p>

<h2 id="f03">F-03 — {len(noline) + len(placeholder)} fixture(s) without a usable external price</h2>
<p class="small">Blank on purpose. Per competition:</p>
<table class="sortable"><thead><tr><th>Competition</th><th class="num">Fixtures</th><th>Note</th></tr></thead><tbody>{comp_rows}</tbody></table>

<h2 id="f04">F-04 — A source's generic 1.8/1.8 default is not a line</h2>
<p class="small">{len(placeholder)} fixture(s) display exactly 1.8 / 1.8 on EGamersWorld. That is its fallback when no bookmaker
price exists; it is excluded from every probability here. One fixture (ex-Keyd Stars vs Galorys) was seen with the default on its
match page at 18:40 UTC while the match list carried a real 2.44 / 1.48 price at 18:31 UTC — the priced reading is used.</p>

<h2 id="f05">F-05 — Live markets move between captures</h2>
<table class="sortable"><thead><tr><th>Fixture</th><th>Drift</th><th>Source</th></tr></thead><tbody>{drift_rows}</tbody></table>

<h2 id="f06">F-06 — One fixture, two prices on the same source page</h2>
<p class="small">On the Thunderpick World Championship page the price widget shows 9z 3.60 / Aurora 1.27 while the schedule block
below it shows 3.80 / 1.22. The widget pair is used (consistently for all four TWC fixtures) and the discrepancy is recorded in the
row note. Source: <a href="https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H" target="_blank" rel="noreferrer noopener">EGamersWorld TWC event page</a>.</p>

<h2 id="f07">F-07 — Team names differ between the two sides of a join</h2>
<p class="small">Mapping applied when joining external prices to Hotspawn fixtures (the Hotspawn name is kept in every table):
“BNK FearX” ↔ “FearX”; “Movistar KOI Fénix” ↔ “KOI Fénix”; “Ninjas in Pyjamas” ↔ “NIP”/“NiP”; “Fnatic” ↔ “fnatic”; “Envy” ↔
“Team Envy”; “Sashi” ↔ “Sashi Esport”; “BC.Game” ↔ “BC.Game Esports”; “G2 Hel” ↔ “G2 HEL”. Rows whose names could not be matched
are left unpriced rather than guessed.</p>

<h2 id="f08">F-08 — Fixtures already started are still on the board</h2>
<p class="small">The payload's <code>status</code> field marks live/finished matches (they stay listed with their crowd counts).
Their prices are historical at capture time and are marked in the Status column; picks for them are closed.</p>

<h2 id="f09">F-09 — Automated collection of prices is blocked by the sources</h2>
<p class="small">EGamersWorld and HLTV answer HTTP 403 to datacenter clients (GitHub Actions runners) while rendering normally in a
browser session — verified again in run 38445055709 where all eight URLs answered 403. The prices above were therefore read in a
browser session with an explicit capture timestamp; the fixture inventory, which is served normally, is collected automatically.
No block is worked around, and no login or wagering is involved anywhere in this project.</p>

<h2 id="f10">F-10 — Anchor row for manual review</h2>
<p class="small">To re-verify the join by hand: Hotspawn <a href="https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176" target="_blank" rel="noreferrer noopener">9z vs Aurora (id 1080176)</a>
↔ EGamersWorld <a href="https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H" target="_blank" rel="noreferrer noopener">TWC event page</a>
(3.60 / 1.27) ↔ HLTV <a href="https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026" target="_blank" rel="noreferrer noopener">match page</a>
(timestamp 2026-10-14 08:30 UTC). All three agree on identity and time; the price is the external one.</p>"""

    sources_body = f"""
<h2>Sources used, and what each one provides</h2>
<table class="sortable"><thead><tr><th>Source</th><th>Used for</th><th>How it was read</th><th>Link</th></tr></thead><tbody>
<tr><td>Hotspawn Play — Pick'em pages</td><td>Complete fixture slate: id, competition, tier, points, stage, exact UTC start and
lock time, board crowd %</td><td>Server-rendered payload fetched in CI (automated, run 38445027513)</td>
<td><a href="https://play.hotspawn.com/lobby" target="_blank" rel="noreferrer noopener">/lobby</a> ·
<a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noreferrer noopener">/cs2-pickems</a> ·
<a href="https://play.hotspawn.com/lol-pickems" target="_blank" rel="noreferrer noopener">/lol-pickems</a> ·
<a href="https://play.hotspawn.com/thp-pickems" target="_blank" rel="noreferrer noopener">/thp-pickems</a></td></tr>
<tr><td>Hotspawn — rules</td><td>Picks lock 6 minutes before start (<code>lock_offset_sec = 360</code>, confirmed in the payload)</td>
<td>read 2026-10-13</td><td><a href="https://play.hotspawn.com/how-it-works" target="_blank" rel="noreferrer noopener">how-it-works</a></td></tr>
<tr><td>EGamersWorld — Thunderpick World Championship 2026</td><td>Prices for the four TWC fixtures (BC.Game)</td>
<td>browser read 18:05 UTC</td><td><a href="https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H" target="_blank" rel="noreferrer noopener">event</a></td></tr>
<tr><td>EGamersWorld — Stake Pulse Beat III</td><td>Prices for the four Stake Pulse fixtures</td>
<td>browser read 18:15 UTC</td><td><a href="https://egamersworld.com/counterstrike/event/stake-pulse-beat-iii-EJZmJpBjeNx" target="_blank" rel="noreferrer noopener">event</a></td></tr>
<tr><td>EGamersWorld — CCT Europe 2026 Series #11</td><td>Prices for Gothic–Lavked and G2 Ares–The Last Resort; coverage check for the other three CCT fixtures</td>
<td>browser read 18:20 UTC</td><td><a href="https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK" target="_blank" rel="noreferrer noopener">event</a></td></tr>
<tr><td>EGamersWorld — ESL Challenger League cups</td><td>Prices for Zomblers–Overtake Sector (NA) and ex-Keyd Stars–Galorys (SA)</td>
<td>browser read 18:30–18:31 UTC</td><td><a href="https://egamersworld.com/counterstrike/event/esl-challenger-league-season-52-north-america-cup--41yion_ONx" target="_blank" rel="noreferrer noopener">NA cup</a> ·
<a href="https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp" target="_blank" rel="noreferrer noopener">SA match</a></td></tr>
<tr><td>EGamersWorld — LoL match list</td><td>Prices for Worlds 2026 Play-In, Demacia Cup and EMEA Masters fixtures</td>
<td>browser read 18:25 and 18:31 UTC</td><td><a href="https://egamersworld.com/lol/matches" target="_blank" rel="noreferrer noopener">lol/matches</a></td></tr>
<tr><td>EGamersWorld — CS2 match list / event index</td><td>Coverage checks (which fixtures carry no price at all)</td>
<td>browser read 18:20–18:35 UTC</td><td><a href="https://egamersworld.com/counterstrike/matches" target="_blank" rel="noreferrer noopener">matches</a> ·
<a href="https://egamersworld.com/counterstrike/events" target="_blank" rel="noreferrer noopener">events</a></td></tr>
<tr><td>HLTV.org</td><td>World ranking context; kick-off timestamp cross-checks; event format facts</td>
<td>ranking + match pages read 2026-10-13 (403 to CI, browser read for verification)</td>
<td><a href="https://www.hltv.org/ranking/teams" target="_blank" rel="noreferrer noopener">ranking</a> ·
<a href="https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii" target="_blank" rel="noreferrer noopener">HOTU–fnatic</a> ·
<a href="https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026" target="_blank" rel="noreferrer noopener">9z–Aurora</a> ·
<a href="https://www.hltv.org/events/9332/elisa-breakout-series-2" target="_blank" rel="noreferrer noopener">Elisa BreakOut</a></td></tr>
<tr><td>Liquipedia / Elisa Esports</td><td>Elisa BreakOut Series #2 facts (dates, venue, format, prize)</td>
<td>read 2026-10-13</td><td><a href="https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2" target="_blank" rel="noreferrer noopener">Liquipedia</a></td></tr>
</tbody></table>
<h2>Sources checked that could not supply a line</h2>
<ul class="small">
<li><a href="https://www.bovada.lv/sports/esports" target="_blank" rel="noreferrer noopener">Bovada</a>,
<a href="https://www.betonline.ag/sportsbook/esports" target="_blank" rel="noreferrer noopener">BetOnline</a>,
<a href="https://www.flashscore.com/esports/" target="_blank" rel="noreferrer noopener">Flashscore</a>,
<a href="https://oddspedia.com/esports" target="_blank" rel="noreferrer noopener">Oddspedia</a>,
<a href="https://www.oddsportal.com/esports/" target="_blank" rel="noreferrer noopener">OddsPortal</a> —
answered 200 to CI but render their boards client-side, so no price could be read from them (checked 2026-10-13; raw evidence kept
in the session branch's temporary evidence folder, deleted before release).</li>
<li>EGamersWorld and HLTV answer 403 to CI clients; their values above come from browser reads with explicit timestamps.</li>
<li>Polymarket search snippets list CCT/Thunderpick markets but with unreadable values in the snippet; not used as a line.</li>
</ul>"""

    methodology_body = f"""
<h2>How every number on this site is produced</h2>
<ul>
<li><b>Fixture list (complete, not sampled).</b> The five public Pick'em pages are fetched by an Actions job
(<code>src/pickem_inventory.py</code>, run 38445027513). Each page embeds its full data set in
<code>&lt;script id="ng-state"&gt;</code>; the parser reads that payload and writes one row per match with the payload's own id,
competition, tier, offered points, stage, status, exact UTC <code>scheduled_start_time</code> and <code>lock_time</code>, both
participants and the board's crowd percentages. Rendered-card counts are recorded as a cross-check
(27 / 26 / 231 cards vs 86 / 85 / 294 payload rows).</li>
<li><b>External lines.</b> Prices are read from off-site bookmaker pages (EGamersWorld's BC.Game price widgets and its match
lists). Each row keeps the source URL and the UTC capture time; two readings are kept where a market moved. Nothing is typed from
memory and no price is inferred from a ranking, a crowd percentage or a model.</li>
<li><b>Our own line.</b> For every fixture with a real two-way price the margin is removed:
<code>p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)</code>, and the residual <code>1/odds_A + 1/odds_B</code> is shown as the
overround. This de-vigged probability is the project's own line and is labeled as such on every page.</li>
<li><b>What is deliberately blank.</b> Where no public price exists the odds and probability cells are empty and the fixture is
listed on the Flagged page. Hotspawn's crowd percentage appears in its own column, tagged as metadata, and is never an input.</li>
<li><b>Reproduce.</b> <code>python src/pickem_inventory.py</code> (needs internet; runs in CI) →
<code>python pipeline/build_site.py</code> → this site plus <code>lines/analysis.csv</code>.</li>
</ul>
<h2>Reading the tables</h2>
<ul>
<li><span class="badge b-priced">priced</span> — real two-way bookmaker price; own de-vigged probability published.</li>
<li><span class="badge b-placeholder">no real line</span> — the only thing the source shows is its generic 1.8/1.8 default.</li>
<li><span class="badge b-missing">blank / unverified</span> — no public price found; intentionally empty.</li>
<li><span class="badge b-live">live</span> / finished — the payload's own status; picks for those matches are closed.</li>
</ul>"""

    (OUT / "index.html").write_text(page("Dashboard — Hotspawn Pick'em complete slate + external lines", "index.html", dash), encoding="utf-8")
    (OUT / "cs2.html").write_text(page("CS2 — Hotspawn Pick'em complete slate + external lines", "cs2.html", cs2_body,
                                       "All CS2 fixtures on the Pick'em board with external prices where a public source carries them."), encoding="utf-8")
    (OUT / "lol.html").write_text(page("League of Legends — Hotspawn Pick'em complete slate", "lol.html", lol_body,
                                       "All 294 LoL fixtures on the Pick'em board; national-league fixtures are blank and flagged."), encoding="utf-8")
    (OUT / "flagged.html").write_text(page("Flagged for Review — Hotspawn Pick'em analysis", "flagged.html", flagged,
                                           "Nine flagged items: discrepancies, refused blanks and sources that resist automated reads."), encoding="utf-8")
    (OUT / "sources.html").write_text(page("Sources — Hotspawn Pick'em analysis", "sources.html", sources_body,
                                           "Every source used, what it provided, how it was read and when."), encoding="utf-8")
    (OUT / "methodology.html").write_text(page("Methodology — Hotspawn Pick'em analysis", "methodology.html", methodology_body,
                                               "How the complete fixture list, the external lines and the de-vigged probabilities are produced."), encoding="utf-8")

    print(json.dumps({"fixtures": len(rows), "cs2": len(cs2), "lol": len(lol), "priced": len(priced),
                      "placeholder": len(placeholder), "no_line": len(noline)}, indent=1))


if __name__ == "__main__":
    build()
