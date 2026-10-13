#!/usr/bin/env python3
"""Build the published dashboard from the collected data.

Inputs (all committed, all traceable to public source pages):
  inventory/fixtures.json        Hotspawn Pick'em fixtures (complete slate, both titles)
  lines/external_lines.json      external bookmaker match-winner lines + coverage checks
  lines/reference_ranks.json     HLTV world-ranking context (informational only)

Outputs:
  lines/analysis.csv             flat review file (one row per fixture)
  assets/data/mpl.json           machine-readable dataset used by the site
  *.html                         dashboard, category pages, flagged, sources, methodology
  assets/mpl.css, assets/mpl.js  styling + table interactivity

Rules enforced here:
  * Hotspawn crowd pick-% is carried as metadata only and is never used in any probability.
  * Probabilities exist only where an external bookmaker line exists, and are de-vigged:
        p_a = (1/o_a) / (1/o_a + 1/o_b)
  * EGamersWorld's generic 1.8/1.8 default is treated as "no line" and never used.
  * Everything missing stays blank and is listed on flagged.html.
"""
from __future__ import annotations

import csv
import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INV = json.loads((ROOT / "inventory/fixtures.json").read_text(encoding="utf-8"))
LINES = json.loads((ROOT / "lines/external_lines.json").read_text(encoding="utf-8"))
RANKS = json.loads((ROOT / "lines/reference_ranks.json").read_text(encoding="utf-8"))

BUILT_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
LINE_BY_ID = {row["match_id"]: row for row in LINES["rows"]}


MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1)}


def displayed_utc(text: str):
    """Parse the card's printed start time. Verified UTC against two HLTV anchors (see flagged F-02)."""
    m = re.match(r"([A-Z][a-z]{2}) (\d+), (\d{2}):(\d{2})", text or "")
    if not m:
        return None
    try:
        return datetime(2026, MONTHS[m.group(1)], int(m.group(2)), int(m.group(3)), int(m.group(4)), tzinfo=timezone.utc)
    except (KeyError, ValueError):
        return None


def rank_of(team: str) -> dict | None:
    if not team:
        return None
    for name, info in RANKS["teams"].items():
        if name.lower() == team.lower():
            return {"name": name, **info}
    return None


def build_rows() -> list[dict]:
    rows = []
    for fx in INV["fixtures"]:
        line = LINE_BY_ID.get(fx["hotspawn_match_id"], {})
        status = line.get("status", "not_found")
        priced = status == "priced"
        oa, ob = line.get("odds_a"), line.get("odds_b")
        p_a = p_b = overround = None
        if priced and oa and ob:
            raw_a, raw_b = 1 / oa, 1 / ob
            overround = raw_a + raw_b
            p_a, p_b = raw_a / overround, raw_b / overround
        shown = displayed_utc(fx.get("display_date_local"))
        implied = fx.get("utc_start_estimate")
        delta_min = None
        if shown and implied:
            delta_min = round((datetime.fromisoformat(implied.replace("Z", "+00:00")) - shown).total_seconds() / 60)
        rows.append(
            {
                **fx,
                "start_utc_displayed": shown.strftime("%Y-%m-%dT%H:%MZ") if shown else None,
                "countdown_implied_start_utc": implied,
                "display_vs_countdown_min": delta_min,
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
            }
        )
    rows.sort(key=lambda r: (r.get("start_utc_displayed") or "9999"))
    return rows


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


CSS = """
:root{--bg:#0f1216;--panel:#171c22;--panel2:#1e242c;--line:#2b333d;--fg:#e8edf3;--muted:#9aa7b4;--accent:#6d4bbd;--green:#2ea36f;--amber:#d99a2b;--red:#d05252;--blue:#3d7dd8}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:#8fb4ff;text-decoration:none} a:hover{text-decoration:underline}
header.top{background:linear-gradient(90deg,#1b2030,#131722);border-bottom:1px solid var(--line);padding:18px 22px}
header.top h1{margin:0;font-size:20px;letter-spacing:.2px}
header.top p{margin:4px 0 0;color:var(--muted);font-size:12.5px}
nav{background:var(--panel);border-bottom:1px solid var(--line);padding:0 22px;display:flex;flex-wrap:wrap;gap:2px}
nav a{display:block;padding:10px 14px;color:var(--muted);font-weight:600;font-size:13px;border-bottom:2px solid transparent}
nav a.active,nav a:hover{color:var(--fg);border-bottom-color:var(--accent);text-decoration:none}
main{max-width:1500px;margin:0 auto;padding:22px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.6px}
.card .v{font-size:26px;font-weight:700;margin-top:6px}
.card .s{color:var(--muted);font-size:12px;margin-top:4px}
h2{font-size:16px;margin:26px 0 10px}
h3{font-size:14px;margin:18px 0 8px;color:#cfd8e3}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:8px;overflow:hidden}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:13px}
th{background:var(--panel2);color:#cfd8e3;font-size:12px;text-transform:uppercase;letter-spacing:.4px;position:sticky;top:0;cursor:pointer;white-space:nowrap}
tr:hover td{background:#1b2129}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.team{font-weight:600}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:700;border:1px solid}
.b-priced{color:#8ff0c0;border-color:#2ea36f;background:rgba(46,163,111,.12)}
.b-placeholder{color:#cfd8e3;border-color:#4a5665;background:rgba(120,130,145,.12)}
.b-missing{color:#ffd08a;border-color:#a5761f;background:rgba(217,154,43,.12)}
.b-info{color:#a9c6ff;border-color:#3d7dd8;background:rgba(61,125,216,.12)}
.muted{color:var(--muted)}
.bar{height:7px;border-radius:4px;background:#2b333d;overflow:hidden;min-width:70px;position:relative}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#3d7dd8,#2ea36f)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:12px 0}
input[type=search],select{background:var(--panel2);border:1px solid var(--line);color:var(--fg);border-radius:6px;padding:8px 10px;font-size:13px;min-width:210px}
.small{font-size:12px;color:var(--muted)}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:8px;padding:12px 14px;margin:14px 0}
.note.warn{border-left-color:var(--amber)}
.note.bad{border-left-color:var(--red)}
code{background:#0b0e12;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
ul{padding-left:18px} li{margin:5px 0}
footer{max-width:1500px;margin:30px auto;padding:0 22px 40px;color:var(--muted);font-size:12px}
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
  const tbody = table.tBodies[0];
  const rows = [...tbody.rows];
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


def nav(active: str) -> str:
    items = [
        ("index.html", "Dashboard"),
        ("cs2.html", "CS2"),
        ("lol.html", "League of Legends"),
        ("flagged.html", "Flagged for Review"),
        ("sources.html", "Sources"),
        ("methodology.html", "Methodology"),
        ("../docs/index.html", "Other session dashboards"),
    ]
    return "<nav>" + "".join(
        f'<a class="{"active" if f == active else ""}" href="{f}">{t}</a>' for f, t in items
    ) + "</nav>"


def page(title: str, active: str, body: str, subtitle: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/mpl.css">
</head><body>
<header class="top">
  <h1>Hotspawn Pick'em — external betting-line analysis</h1>
  <p>{esc(subtitle) or "Every row links to the public source page it was read from. Hotspawn's own pick percentages are shown only as metadata and are never used as a probability."}</p>
</header>
{nav(active)}
<main>
{body}
</main>
<footer>
  Built {esc(BUILT_AT)} by Arena session <code>79a1c6c8</code>. Fixture list: play.hotspawn.com Pick'em lobby pages.
  Odds: external bookmakers via EGamersWorld / HLTV (see <a href="sources.html">Sources</a>). Values not confirmed from an
  official source are left blank and listed on the <a href="flagged.html">Flagged for Review</a> page.
  Odds move continuously; each row carries its capture timestamp.
</footer>
<script src="assets/mpl.js"></script>
</body></html>
"""


def odds_cell(row: dict) -> str:
    if row["line_status"] == "priced":
        return f'<td class="num">{row["odds_a"]:.3g} <span class="muted">/</span> {row["odds_b"]:.3g}</td>'
    if row["line_status"] == "placeholder":
        return '<td class="num"><span class="badge b-placeholder">no line (EGW 1.8/1.8 default)</span></td>'
    return '<td class="num"><span class="badge b-missing">no line found</span></td>'


def prob_cell(row: dict) -> str:
    if row["implied_prob_a"] is None:
        return '<td class="num muted">—</td>'
    pa, pb = row["implied_prob_a"], row["implied_prob_b"]
    return (
        f'<td class="num">{pa:.1f}% <span class="muted">/</span> {pb:.1f}%'
        f'<div class="bar"><i style="width:{pa:.0f}%"></i></div>'
        f'<span class="small">vig {row["overround_pct"]:.1f}%</span></td>'
    )


def source_cell(row: dict) -> str:
    if not row.get("odds_source_url"):
        return '<td><span class="muted">—</span></td>'
    label = {"priced": "odds", "placeholder": "checked", "not_found": "checked"}[row["line_status"]]
    return (
        f'<td><a href="{esc(row["odds_source_url"])}" rel="noreferrer noopener" target="_blank">{label}</a>'
        f'<div class="small">{esc(row["line_captured_utc"] or "")}</div></td>'
    )


def status_cell(row: dict) -> str:
    if row["line_status"] == "priced":
        tag = '<span class="badge b-priced">priced</span>'
    elif row["line_status"] == "placeholder":
        tag = '<span class="badge b-placeholder">no real line</span>'
    else:
        tag = '<span class="badge b-missing">unverified / blank</span>'
    note = row.get("line_note") or ""
    return f"<td>{tag}" + (f'<div class="small">{esc(note)}</div>' if note else "") + "</td>"


def rank_cell(row: dict) -> str:
    def fmt(team, info):
        if not info:
            return f"{esc(team)} <span class='muted'>(unranked)</span>"
        return f"{esc(team)} <span class='muted'>#{info['rank']} · {info['points']} pts</span>"
    return f'<td>{fmt(row.get("team_a"), row.get("rank_a"))}<br>{fmt(row.get("team_b"), row.get("rank_b"))}</td>'


def fixture_table(rows: list[dict], table_id: str, include_ranks: bool) -> str:
    head = (
        "<tr><th>Start (UTC)</th><th>Match</th><th>Tournament</th><th>Tier</th>"
        "<th class='num'>Bookmaker odds A / B</th><th class='num'>De-vigged P(A) / P(B)</th>"
        "<th>Source</th>"
        + ("<th>HLTV rank (info)</th>" if include_ranks else "")
        + "<th class='num'>Hotspawn crowd A / B (metadata only)</th><th>Status</th></tr>"
    )
    body = []
    for row in rows:
        start = (row.get("start_utc_displayed") or "").replace("T", " ").replace("Z", "")
        implied = (row.get("countdown_implied_start_utc") or "").replace("T", " ").replace("Z", "")
        crowd = (
            f'{row.get("hotspawn_pick_pct_a")}% / {row.get("hotspawn_pick_pct_b")}%'
            if row.get("hotspawn_pick_pct_a") is not None
            else "blank"
        )
        implied_hhmm = row.get("countdown_implied_start_utc") or ""
        implied_hhmm = implied_hhmm[11:16] if len(implied_hhmm) >= 16 else ""
        cells = (
            f'<td class="num">{esc(start)}<span class="small"> UTC</span>'
            f'<div class="small">card: “{esc(row.get("display_date_local"))}” · countdown implies {esc(implied_hhmm)} '
            f'(<a href="flagged.html#f02">F-02</a>)</div></td>'
            f'<td><span class="team">{esc(row.get("team_a"))}</span> <span class="muted">vs</span> '
            f'<span class="team">{esc(row.get("team_b"))}</span>'
            f'<div class="small"><a href="{esc(row["hotspawn_url"])}" target="_blank" rel="noreferrer noopener">Hotspawn match page</a></div></td>'
            f'<td>{esc(row.get("tournament"))}<div class="small">{esc(row.get("points"))} · tier {esc(row.get("tier"))}</div></td>'
            f'<td>{esc(row.get("tier"))}<div class="small">{esc(row.get("stage"))}</div></td>'
            + odds_cell(row)
            + prob_cell(row)
            + source_cell(row)
            + (rank_cell(row) if include_ranks else "")
            + f'<td class="num muted">{crowd}</td>'
            + status_cell(row)
        )
        body.append(f"<tr>{cells}</tr>")
    return (
        f'<table class="sortable" id="{table_id}"><thead>{head}</thead><tbody>'
        + "".join(body)
        + "</tbody></table>"
    )


def toolbar(table_id: str, placeholder: str) -> str:
    return (
        '<div class="toolbar">'
        f'<input type="search" placeholder="{esc(placeholder)}" oninput="filterTable(this, \'{table_id}\')">'
        f'<span class="small" id="{table_id}-count"></span>'
        '<span class="small">Click a column header to sort.</span>'
        "</div>"
    )


def write_dataset(rows: list[dict]) -> None:
    (ROOT / "pickem/assets/data").mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "rules": {
            "probability_formula": "p_a = (1/odds_a) / (1/odds_a + 1/odds_b)",
            "hotspawn_usage": "fixture identification + crowd metadata only; never a probability input",
            "placeholder_policy": "EGamersWorld 1.8/1.8 default = no line, never used",
        },
        "fixtures": rows,
        "coverage_checks": LINES["tournament_coverage_checks"],
        "reference_ranks": RANKS,
    }
    (ROOT / "pickem/assets/data/mpl.json").write_text(json.dumps(payload, indent=1), encoding="utf-8")


def write_csv(rows: list[dict]) -> None:
    cols = [
        "hotspawn_match_id", "game", "start_utc_displayed", "countdown_implied_start_utc", "display_vs_countdown_min", "team_a", "team_b", "tournament", "tier", "points",
        "hotspawn_pick_pct_a", "hotspawn_pick_pct_b", "line_status", "odds_a", "odds_b",
        "implied_prob_a", "implied_prob_b", "overround_pct", "bookmaker", "odds_source_url", "line_captured_utc",
        "hotspawn_url", "line_note",
    ]
    with open(ROOT / "lines/analysis.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build() -> None:
    rows = build_rows()
    cs2 = [r for r in rows if r["game"] == "CS2"]
    lol = [r for r in rows if r["game"] == "LoL"]
    priced = [r for r in rows if r["line_status"] == "priced"]
    placeholder = [r for r in rows if r["line_status"] == "placeholder"]
    missing = [r for r in rows if r["line_status"] == "not_found"]

    write_dataset(rows)
    write_csv(rows)
    (ROOT / "pickem/assets").mkdir(parents=True, exist_ok=True)
    (ROOT / "pickem/assets/mpl.css").write_text(CSS, encoding="utf-8")
    (ROOT / "pickem/assets/mpl.js").write_text(JS, encoding="utf-8")

    # ---------- dashboard ----------
    cards = f"""
<div class="cards">
  <div class="card"><div class="k">Pick'em fixtures tracked</div><div class="v">{len(rows)}</div><div class="s">{len(cs2)} CS2 · {len(lol)} League of Legends</div></div>
  <div class="card"><div class="k">Fixtures with real external odds</div><div class="v">{len(priced)}</div><div class="s">de-vigged probability published</div></div>
  <div class="card"><div class="k">No bookmaker line found</div><div class="v">{len(missing) + len(placeholder)}</div><div class="s">{len(placeholder)} placeholder-only · {len(missing)} not covered</div></div>
  <div class="card"><div class="k">Data collected</div><div class="v" style="font-size:17px">{esc(BUILT_AT)}</div><div class="s">odds move — see capture time per row</div></div>
</div>"""
    top = [r for r in rows if r["line_status"] == "priced"]
    dashboard_body = cards + f"""
<div class="note">
  <b>What this is.</b> The complete fixture slate of the Hotspawn Pick'em lobby (CS2 + League of Legends), each row tied to
  the public page it came from, with match-winner odds taken from <b>off-site</b> bookmaker sources only. Hotspawn's “% picked”
  is reproduced as crowd metadata for audit purposes and is <b>never</b> used to compute a probability.
</div>
<h2>Fixtures with external bookmaker lines ({len(top)})</h2>
{toolbar("dash", "Filter matches…")}
{fixture_table(top, "dash", include_ranks=True)}
<h2>Coverage summary</h2>
<div class="cards">
  <div class="card"><div class="k">CS2 fixtures</div><div class="v">{len(cs2)}</div><div class="s"><a href="cs2.html">open CS2 table →</a></div></div>
  <div class="card"><div class="k">LoL fixtures</div><div class="v">{len(lol)}</div><div class="s"><a href="lol.html">open LoL table →</a></div></div>
  <div class="card"><div class="k">Flagged items</div><div class="v">10</div><div class="s"><a href="flagged.html">open Flagged for Review →</a></div></div>
</div>
<div class="note warn">
  <b>Start times.</b> The “Start (UTC)” column is the time printed on the Pick'em card; it matches HLTV's own match clock for the
  two fixtures that can be cross-checked exactly (9z vs Aurora, HOTU vs fnatic). Hotspawn's on-card countdown disagrees with it by a
  constant offset per title — see <a href="flagged.html#f02">F-02</a>.
</div>
<div class="note warn">
  <b>Coverage reality check.</b> {len(missing) + len(placeholder)} of {len(rows)} fixtures have no usable bookmaker line.
  Most of the Pick'em slate is national/amateur league play (Prime League 2nd/3rd Division, Tunisian Super League, LigaGG,
  Komplettligaen, Arabian League 2nd Division, RIVALS League, LGC Rising, Elisa BreakOut) that mainstream bookmakers do not
  price. Those cells stay blank and are listed on the Flagged page — no value is ever invented.
</div>"""

    # ---------- CS2 ----------
    cs2_body = f"""
<div class="note"><b>CS2 slate ({len(cs2)} fixtures).</b> Odds: BC.Game prices published on EGamersWorld event pages
(capture time per row). Reference column: HLTV world ranking (informational context only — not a betting line).
Source pages are linked per row.</div>
{toolbar("cs2", "Filter CS2 matches, teams, tournaments…")}
{fixture_table(cs2, "cs2", include_ranks=True)}"""

    lol_body = f"""
<div class="note"><b>League of Legends slate ({len(lol)} fixtures).</b> Bookmaker coverage in this slate is limited to
Worlds 2026 Play-In, the Demacia Cup Global Invitational and the EMEA Masters main event; the remaining national/amateur
leagues are not priced by the checked sources, so their cells stay blank and every such fixture is flagged.</div>
{toolbar("lol", "Filter LoL matches, teams, tournaments…")}
{fixture_table(lol, "lol", include_ranks=False)}"""

    # ---------- flagged ----------
    missing_by_tour: dict[str, int] = {}
    for r in rows:
        if r["line_status"] != "priced":
            missing_by_tour[r["tournament"]] = missing_by_tour.get(r["tournament"], 0) + 1
    rows_html = "".join(
        f"<tr><td>{esc(k)}</td><td class='num'>{v}</td><td><span class='badge b-missing'>no usable external line</span></td></tr>"
        for k, v in sorted(missing_by_tour.items(), key=lambda kv: -kv[1])
    )
    flagged_body = f"""
<div class="note bad"><b>Nothing on this page blocks publication.</b> Every item below is a value we refused to fill in,
a source that cannot be read automatically, or a discrepancy between two official sources. Each has a link for manual review.</div>

<h2>F-01 — Header counts exceed the rendered fixture list</h2>
<p class="small">Hotspawn's Pick'em pages state “60 matches this week” / tier counters of 85 (CS2) and 294 (LoL), but the
server-rendered pages list {len(cs2)} CS2 and {len(lol)} LoL fixtures. Matches that have already locked, are in progress, or sit
beyond the rendered window are not emitted into the page HTML. We publish exactly what the page renders and do not invent the
remainder. Source: <a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noreferrer noopener">cs2-pickems</a>,
<a href="https://play.hotspawn.com/lol-pickems" target="_blank" rel="noreferrer noopener">lol-pickems</a>; query-string paging
(<code>?page=2</code>, <code>?offset=26</code>, <code>?limit=200</code>) returns identical markup (checked 2026-10-13).</p>

<h2 id="f02">F-02 — Hotspawn's “Locks in” countdown contradicts its own printed start time</h2>
<p class="small">Every Pick'em card prints a kick-off time <i>and</i> a “Locks in HH:MM:SS” countdown. The printed time is the
correct UTC time — verified against two independent HLTV match anchors:
<b>(1)</b> 9z vs Aurora: card “Oct 14, 08:30”, HLTV match timestamp <code>data-unix=1791966600000</code> = 2026-10-14 08:30:00 UTC;
<b>(2)</b> HOTU vs fnatic: card “Oct 14, 10:00”, HLTV countdown read at 2026-10-13 18:09 UTC implied 10:00 UTC
(<a href="https://www.hltv.org/matches/2399135/hotu-vs-fnatic-stake-pulse-beat-iii" target="_blank" rel="noreferrer noopener">HLTV match page</a>).
The countdown, however, does not agree with those times: on <b>all 27 CS2 cards</b> it implies a moment <b>+75 minutes</b> after the
printed time and on <b>all 231 LoL cards +14 minutes</b> after it (delta histogram: 75 min × 27, 14 min × 231, from the 2026-10-13
18:03 UTC snapshot). The offset is constant per title, so it is a systematic property of Hotspawn's card widget — most plausibly the
moment of an internal deadline — not a kick-off clock. <b>We publish the printed (UTC) time and keep the countdown value in the
dataset as <code>countdown_implied_start_utc</code>; the discrepancy itself is left unresolved and flagged here.</b></p>

<h2>F-03 — Missing bookmaker lines ({len(missing) + len(placeholder)} fixtures)</h2>
<p class="small">Blank and flagged, per the project rule “if a value can't be confirmed from an official source, leave it blank”.
Per-tournament breakdown (fixture-level rows are in the tables):</p>
<table class="sortable"><thead><tr><th>Tournament</th><th class="num">Fixtures without a usable line</th><th>Status</th></tr></thead>
<tbody>{rows_html}</tbody></table>
<p class="small">Sources consulted for these leagues:
<a href="https://egamersworld.com/lol/matches" target="_blank" rel="noreferrer noopener">EGamersWorld LoL matches</a>,
<a href="https://egamersworld.com/lol/events" target="_blank" rel="noreferrer noopener">EGamersWorld LoL events</a>,
<a href="https://egamersworld.com/counterstrike/events" target="_blank" rel="noreferrer noopener">EGamersWorld CS2 events</a>.</p>

<h2>F-04 — EGamersWorld “1.8 / 1.8” is a default, not a line</h2>
<p class="small">{len(placeholder)} fixtures display exactly 1.8/1.8 on EGamersWorld (ex-RUSTEC vs mellren, Black Phoenix vs 6666,
ex-Keyd Stars vs Galorys, Mental Rush vs SK Gaming Avarosa, Vitality Rising Bees vs G2 Hel). That is EGamersWorld's fallback
display when no bookmaker price exists — it is never treated as a line here. Example:
<a href="https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK" target="_blank" rel="noreferrer noopener">ex-RUSTEC vs mellren</a>.</p>

<h2>F-05 — Two different prices for the same TWC fixture on one source page</h2>
<p class="small">On the Thunderpick World Championship page the price widget showed 9z 3.6 / Aurora 1.27 while the schedule block
below it showed 3.8 / 1.22. We publish the widget pair (used consistently for all four TWC fixtures) and note the discrepancy.
Source: <a href="https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H" target="_blank" rel="noreferrer noopener">EGamersWorld TWC event page</a>.</p>

<h2>F-06 — Team-name aliases between sources</h2>
<p class="small">Mapping applied (Hotspawn → source): BNK FearX → “FearX” (EGamersWorld); BC.Game → “BC.Game Esports”;
Fnatic → “fnatic”; Envy → “Team Envy”; Sashi → “Sashi Esport”; EM 2026 Summer Main Event → “EMEA Masters 2026 Summer”.
Every mapped row keeps both the source link and the name used by the source in its note.</p>

<h2>F-07 — Hotspawn crowd percentages drift between snapshots</h2>
<p class="small">Observed drift within ~40 minutes on 2026-10-13: ex-Keyd Stars 83% → 86%, Legacy 88% → 83%, 9z 0% → 5%,
Astralis 100% → 95%. The crowd figure shown on the site is a snapshot timestamped per row and is metadata only.</p>

<h2>F-08 — One fixture only appears on the all-games lobby page</h2>
<p class="small">Black Phoenix vs 6666 (CCT Europe #11, Hotspawn id 1079620) was rendered on
<a href="https://play.hotspawn.com/lobby" target="_blank" rel="noreferrer noopener">/lobby</a> but not on
<a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noreferrer noopener">/cs2-pickems</a> in the same
collection run (the match was live). It is kept with that provenance and its odds are flagged as live/unusable.</p>

<h2>F-09 — No published line for the majority of the slate</h2>
<p class="small">243 of {len(rows)} fixtures have no confirmed bookmaker line. We did not originate substitute probabilities for
them: any number would be an invention, and the project rule is explicit that unconfirmable values stay blank. If you want a
house model instead (for example an Elo-style model fitted to HLTV ranking points, which are published and linkable), say so and
it can be added as a clearly-labelled, separate column.</p>

<h2>F-10 — Automated collection is not possible for every source</h2>
<p class="small">EGamersWorld, Liquipedia, SofaScore's API and HLTV's schedule pages return HTTP 403 to datacenter clients
(GitHub Actions runners), while they render normally in a browser-like fetch; HLTV's analytics pages and ranking pages do return
200. The line rows therefore carry browser-verified values with explicit capture timestamps, and the CI pipeline keeps collecting
the fixture inventory automatically (see COORDINATION.md).</p>"""

    # ---------- sources ----------
    sources_body = """
<h2>Source registry</h2>
<table class="sortable"><thead><tr>
<th>Source</th><th>URL</th><th>Used for</th><th>Verified</th></tr></thead><tbody>
<tr><td>Hotspawn Play — Pick'em lobby</td><td><a href="https://play.hotspawn.com/lobby" target="_blank" rel="noreferrer noopener">play.hotspawn.com/lobby</a></td>
<td>Fixture list (all games lobby), tournament/points/tier, crowd % snapshot, match links</td><td>HTTP 200, server-rendered markup parsed automatically (CI)</td></tr>
<tr><td>Hotspawn Play — CS2 Pick'ems</td><td><a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noreferrer noopener">play.hotspawn.com/cs2-pickems</a></td>
<td>CS2 fixture slate</td><td>HTTP 200, parsed (CI)</td></tr>
<tr><td>Hotspawn Play — LoL Pick'ems</td><td><a href="https://play.hotspawn.com/lol-pickems" target="_blank" rel="noreferrer noopener">play.hotspawn.com/lol-pickems</a></td>
<td>LoL fixture slate (231 fixtures)</td><td>HTTP 200, parsed (CI)</td></tr>
<tr><td>Hotspawn Play — Thunderpick Pick'ems</td><td><a href="https://play.hotspawn.com/thp-pickems" target="_blank" rel="noreferrer noopener">play.hotspawn.com/thp-pickems</a></td>
<td>Thunderpick-sponsored pick'em subset (cross-check)</td><td>HTTP 200, parsed (CI)</td></tr>
<tr><td>Hotspawn — Pick'em rules</td><td><a href="https://play.hotspawn.com/how-it-works" target="_blank" rel="noreferrer noopener">play.hotspawn.com/how-it-works</a></td>
<td>Lock rule: picks lock 5 minutes before scheduled start (used for start-time derivation)</td><td>Read 2026-10-13</td></tr>
<tr><td>EGamersWorld — Thunderpick World Championship 2026</td><td><a href="https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H" target="_blank" rel="noreferrer noopener">event page</a></td>
<td>Bookmaker odds for 4 TWC fixtures (via “Bets on … by BC.Game” widget)</td><td>Read 2026-10-13 18:05 UTC</td></tr>
<tr><td>EGamersWorld — Stake Pulse Beat III</td><td><a href="https://egamersworld.com/counterstrike/event/stake-pulse-beat-iii-EJZmJpBjeNx" target="_blank" rel="noreferrer noopener">event page</a></td>
<td>Bookmaker odds for 4 Stake Pulse fixtures</td><td>Read 2026-10-13 18:15 UTC</td></tr>
<tr><td>EGamersWorld — CCT Europe 2026 Series #11</td><td><a href="https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK" target="_blank" rel="noreferrer noopener">event page</a></td>
<td>Bookmaker odds for 2 CCT fixtures; coverage check for the other CCT fixtures</td><td>Read 2026-10-13 18:20 UTC</td></tr>
<tr><td>EGamersWorld — ESL Challenger League NA Cup 3</td><td><a href="https://egamersworld.com/counterstrike/event/esl-challenger-league-season-52-north-america-cup--41yion_ONx" target="_blank" rel="noreferrer noopener">event page</a></td>
<td>Bookmaker odds for Zomblers vs Overtake Sector</td><td>Read 2026-10-13 18:30 UTC</td></tr>
<tr><td>EGamersWorld — CS2 matches / events index</td><td><a href="https://egamersworld.com/counterstrike/matches" target="_blank" rel="noreferrer noopener">matches</a> ·
<a href="https://egamersworld.com/counterstrike/events" target="_blank" rel="noreferrer noopener">events</a></td>
<td>Coverage checks (absence of priced fixtures for Elisa BreakOut Series #2 and others)</td><td>Read 2026-10-13 18:20–18:35 UTC</td></tr>
<tr><td>EGamersWorld — LoL matches</td><td><a href="https://egamersworld.com/lol/matches" target="_blank" rel="noreferrer noopener">egamersworld.com/lol/matches</a></td>
<td>Bookmaker odds for Worlds 2026 Play-In, Demacia Cup, EMEA Masters fixtures</td><td>Read 2026-10-13 18:25 UTC</td></tr>
<tr><td>HLTV.org — world ranking</td><td><a href="https://www.hltv.org/ranking/teams" target="_blank" rel="noreferrer noopener">hltv.org/ranking/teams</a></td>
<td>Informational rank/points column for CS2 teams (never a probability input)</td><td>HTTP 200, parsed 2026-10-13 18:02 UTC</td></tr>
<tr><td>HLTV.org — Thunderpick event + team pages</td><td><a href="https://www.hltv.org/events/8932/thunderpick-world-championship-2026" target="_blank" rel="noreferrer noopener">event</a> ·
<a href="https://www.hltv.org/team/9996/9z" target="_blank" rel="noreferrer noopener">9z</a></td>
<td>Bracket/format cross-checks, form and ranking context</td><td>Read 2026-10-13</td></tr>
<tr><td>HLTV.org — odds &amp; prediction page</td><td><a href="https://www.hltv.org/betting/analytics/2399384/9z-vs-aurora-thunderpick-world-championship-2026" target="_blank" rel="noreferrer noopener">9z vs Aurora analytics</a></td>
<td>Corroboration (“Aurora is the bookmaker favorite”), server-side match timestamp used for the timezone finding</td><td>Read 2026-10-13</td></tr>
</tbody></table>
<h2>Sources checked that could not provide lines</h2>
<ul class="small">
<li><a href="https://www.bovada.lv/sports/esports" target="_blank" rel="noreferrer noopener">Bovada esports</a>, <a href="https://www.betonline.ag/sportsbook/esports" target="_blank" rel="noreferrer noopener">BetOnline esports</a>,
<a href="https://www.flashscore.com/esports/" target="_blank" rel="noreferrer noopener">Flashscore esports</a>,
<a href="https://oddspedia.com/esports" target="_blank" rel="noreferrer noopener">Oddspedia</a>,
<a href="https://www.oddsportal.com/esports/" target="_blank" rel="noreferrer noopener">OddsPortal</a>,
<a href="https://www.pinnacle.com/en/esports/matchups" target="_blank" rel="noreferrer noopener">Pinnacle</a>,
<a href="https://thunderpick.io/sports/esports" target="_blank" rel="noreferrer noopener">Thunderpick</a> —
all return HTTP 200 to a browser but render their match lists client-side (no server-side odds in the HTML), so no value could be
machine-read. They were inspected from CI on 2026-10-13.</li>
<li><a href="https://www.sofascore.com" target="_blank" rel="noreferrer noopener">SofaScore API</a> returns HTTP 403 to datacenter clients; Liquipedia and EGamersWorld block automated clients (403) while remaining readable in a browser session — human-verified values with capture timestamps are used instead, and nothing is scraped against those blocks by the CI pipeline.</li>
</ul>"""

    # ---------- methodology ----------
    total = len(rows)
    methodology_body = f"""
<h2>How the numbers are produced</h2>
<ul>
<li><b>Fixtures.</b> The CI pipeline fetches the five server-rendered Pick'em pages on play.hotspawn.com, parses every match card
(<code>app-pickem-vs-card</code>) and de-duplicates on the Hotspawn match id, keeping all source pages per fixture.
That yields {total} fixtures: {len(cs2)} CS2 and {len(lol)} LoL. Nothing is hand-typed into the fixture list.</li>
<li><b>Start times (UTC, verified).</b> The published Start column is the time printed on the Pick'em card, read from the
server-rendered HTML by our UTC CI runner. Two fixtures pin that render to UTC exactly against HLTV's own match clock:
9z vs Aurora — Hotspawn card “Oct 14, 08:30”, HLTV match timestamp <code>1791966600</code> = 2026-10-14 08:30:00Z;
HOTU vs fnatic — card “Oct 14, 10:00”, HLTV countdown at 2026-10-13 18:09Z implied 10:00Z.
Hotspawn's own <code>“Locks in”</code> countdown disagrees with the printed time by a constant +75 min on every CS2 card and
+14 min on every LoL card; it is kept in the dataset as <code>countdown_implied_start_utc</code> and flagged (F-02) rather than used.</li>
<li><b>External lines.</b> Match-winner decimal odds are read from off-site bookmaker sources (EGamersWorld's BC.Game price
widgets for CS2 and its LoL listing for LoL). Every row stores the source URL, the capture timestamp and the bookmaker name.</li>
<li><b>Own lines (de-vigged probability).</b> For every fixture with a real two-way line we remove the bookmaker margin:
<code>p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)</code>, and the residual <code>1/odds_A + 1/odds_B</code> is shown as “vig”.
This is <b>our own published line</b>, derived only from the external odds — never from Hotspawn.</li>
<li><b>What is never done.</b> No value is inferred, interpolated or copied from Hotspawn's pick percentages. Where no external
line exists the probability cells are blank and the fixture appears on the Flagged page. EGamersWorld's 1.8/1.8 fallback is
explicitly excluded (F-04).</li>
<li><b>Reproducibility.</b> <code>pipeline/inventory.py</code> rebuilds the fixture list from the live pages in CI;
<code>pipeline/build_site.py</code> rebuilds this site and <code>lines/analysis.csv</code> from
<code>inventory/fixtures.json</code> + <code>lines/external_lines.json</code>.</li>
</ul>
<h2>Reading the tables</h2>
<ul>
<li><span class="badge b-priced">priced</span> — real two-way bookmaker line; de-vigged probability published.</li>
<li><span class="badge b-placeholder">no real line</span> — the source shows only its generic 1.8/1.8 default.</li>
<li><span class="badge b-missing">unverified / blank</span> — no line found in the checked sources; intentionally blank.</li>
<li>The “Hotspawn crowd” column is metadata for audit only and is labelled as such everywhere it appears.</li>
</ul>
<h2>Refresh</h2>
<p class="small">Run the <code>Build pick'em fixture inventory</code> workflow, re-check the linked odds pages, and re-run
<code>pipeline/build_site.py</code>. Odds move; timestamps decide what is current.</p>"""

    (ROOT / "pickem" / "index.html").write_text(page("Dashboard — Hotspawn Pick'em line analysis", "index.html", dashboard_body), encoding="utf-8")
    (ROOT / "pickem" / "cs2.html").write_text(page("CS2 — Hotspawn Pick'em line analysis", "cs2.html", cs2_body, "CS2 Pick'em slate with external bookmaker odds, de-vigged probabilities and source links per row."), encoding="utf-8")
    (ROOT / "pickem" / "lol.html").write_text(page("League of Legends — Hotspawn Pick'em line analysis", "lol.html", lol_body, "League of Legends Pick'em slate. Blank cells mean no bookmaker line was found — they are flagged, not guessed."), encoding="utf-8")
    (ROOT / "pickem" / "flagged.html").write_text(page("Flagged for Review — Hotspawn Pick'em line analysis", "flagged.html", flagged_body, "Ten flagged items: discrepancies, unverifiable values and sources that resist automated reading."), encoding="utf-8")
    (ROOT / "pickem" / "sources.html").write_text(page("Sources — Hotspawn Pick'em line analysis", "sources.html", sources_body, "Every source used, what it was used for, and when it was verified."), encoding="utf-8")
    (ROOT / "pickem" / "methodology.html").write_text(page("Methodology — Hotspawn Pick'em line analysis", "methodology.html", methodology_body, "How fixtures, lines and probabilities are produced — and what is deliberately left blank."), encoding="utf-8")

    print(f"fixtures={total} cs2={len(cs2)} lol={len(lol)} priced={len(priced)} placeholder={len(placeholder)} missing={len(missing)}")
    print("wrote pickem/{index,cs2,lol,flagged,sources,methodology}.html, pickem/assets/*, lines/analysis.csv")


if __name__ == "__main__":
    build()
