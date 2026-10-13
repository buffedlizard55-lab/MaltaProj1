#!/usr/bin/env python3
"""S-04 page builder — Arena session `arena/180a42a0`.  Offline: reads only committed data.

Inputs (all committed):
    slate/data/analysis.csv       one row per open fixture: market line, own line, pick, sources
    slate/data/fixtures.csv       every fixture the Hotspawn payload lists (coverage proof)
    slate/data/ratings.csv        per-team HLTV / Valve rating rows with the exact source used
    slate/data/lines.csv          every external price reading, one row per source
    slate/data/own_lines.csv      our originated line per fixture, with the arithmetic named
    slate/data/flags.csv          everything that could not be confirmed
    slate/data/coverage.json      page-level counts read from Hotspawn itself
    slate/data/provenance.json    every fetch: URL, time, status, bytes, SHA-256
Read-only cross-checks against the other sessions' published tables (never modified):
    picks/data/fixtures.csv, today/data/current.csv, board/data/analysis.csv,
    model/data/lines.csv, data/matches.csv, verify/data/verification.csv

Every value written into HTML goes through esc(); no data field is ever concatenated raw (a previous
session shipped a page that a literal `<script>` inside a flag text broke in half).
"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
ROOT = HERE.parent

NAV = [
    ("index.html", "Board"),
    ("cs2.html", "CS2"),
    ("lol.html", "LoL / other"),
    ("tournaments.html", "Tournaments"),
    ("tiers.html", "Tiers"),
    ("fixtures.html", "All fixtures"),
    ("lines.html", "Market lines"),
    ("own-lines.html", "Own lines"),
    ("verified.html", "Verification"),
    ("sources.html", "Sources"),
    ("methodology.html", "Method"),
    ("flagged.html", "Flagged for review"),
]

CSS = """\
:root{--bg:#0e1116;--panel:#161b22;--panel2:#1c232c;--line:#2a323d;--fg:#e9eef5;--muted:#9aa7b4;
--accent:#7c5cd6;--good:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:#8fb4ff}
header{background:var(--panel);border-bottom:1px solid var(--line);padding:14px 16px 0;position:sticky;top:0;z-index:5}
header .brand{font-weight:700;font-size:17px;margin:0 0 2px}
header .sub{color:var(--muted);font-size:12.5px;margin:0 0 10px}
nav{display:flex;gap:6px;overflow-x:auto;padding-bottom:10px;scrollbar-width:thin}
nav a{white-space:nowrap;font-size:13px;text-decoration:none;color:var(--fg);background:var(--panel2);
border:1px solid var(--line);border-radius:999px;padding:5px 11px}
nav a.active{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
main{max-width:1080px;margin:0 auto;padding:16px 14px 64px}
h1{font-size:21px;margin:8px 0 4px}
h2{font-size:17px;margin:26px 0 8px}
h3{font-size:15px;margin:20px 0 6px;color:#cfd8e3}
p.lead{color:var(--muted);margin:0 0 14px;font-size:13.5px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin:12px 0 18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:11px 12px}
.card .n{font-size:22px;font-weight:700}
.card .l{color:var(--muted);font-size:12px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
border-radius:10px;overflow:hidden;font-size:13.5px}
caption{caption-side:top;text-align:left;color:var(--muted);font-size:12.5px;padding:0 0 6px}
th,td{padding:8px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--panel2);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:last-child td{border-bottom:0}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pick{display:inline-block;background:#153;border:1px solid var(--good);color:#7ee787;border-radius:6px;
padding:1px 7px;font-weight:700;font-size:12.5px;white-space:nowrap}
.pick.none{background:#2a2f38;border-color:var(--line);color:var(--muted);font-weight:500}
.bar{height:7px;border-radius:4px;background:#2b333d;overflow:hidden;margin-top:3px;min-width:64px}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,#2f81f7,#7c5cd6)}
.pct{font-variant-numeric:tabular-nums;font-weight:600}
.mut{color:var(--muted)}
.tag{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:999px;
padding:0 7px;color:var(--muted);margin-left:5px}
.tag.open{border-color:var(--good);color:#7ee787}
.tag.locked,.tag.started{color:var(--warn);border-color:var(--warn)}
.tag.stale{color:var(--muted)}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:8px;padding:10px 12px;margin:14px 0;font-size:13px;color:var(--muted)}
.note b{color:var(--fg)}
code{background:#0a0d12;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
.scroll{overflow-x:auto}
footer{color:var(--muted);font-size:12px;padding:22px 14px 40px;max-width:1080px;margin:0 auto}
@media(max-width:760px){
  body{font-size:14px}
  table,thead,tbody,th,td,tr{display:block}
  table{border:0;background:transparent}
  thead{display:none}
  tr{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:0 0 10px;padding:6px 2px}
  td{border:0;padding:4px 10px;display:flex;justify-content:space-between;gap:10px}
  td:before{content:attr(data-label);color:var(--muted);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.04em;flex:0 0 42%}
  td.num{text-align:right}
  .bar{min-width:0;width:100%}
  td:before{flex-basis:38%}
}
"""


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_json(path: Path):
    if not path.exists() or path.stat().st_size == 0:
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def num(value, digits=1, suffix="%"):
    if value in (None, "", "None"):
        return '<span class="mut">—</span>'
    try:
        number = float(value)
    except (TypeError, ValueError):
        return esc(value)
    return f"{number:.{digits}f}{suffix}"


def bar(value) -> str:
    try:
        width = max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return ""
    return f'<div class="bar"><i style="width:{width:.1f}%"></i></div>'


def link(url: str, label: str) -> str:
    if not url:
        return '<span class="mut">—</span>'
    return f'<a href="{esc(url)}" rel="noopener nofollow">{esc(label)}</a>'


def status_tag(status: str) -> str:
    kind = "open" if status.startswith("open") else ("stale" if status.startswith("stale") else
                                                     ("started" if status.startswith("started") else "locked"))
    return f'<span class="tag {kind}">{esc(status)}</span>'


def sources_cell(row: dict) -> str:
    bits = [link(row.get("hotspawn_url"), "Hotspawn")]
    if row.get("hltv_url"):
        bits.append(link(row["hltv_url"], "HLTV"))
    if row.get("market_url"):
        bits.append(link(row["market_url"], "market"))
    if row.get("own_source_url"):
        bits.append(link(row["own_source_url"], "ratings"))
    return " · ".join(bits)


def page(title: str, body: str, active: str, subtitle: str) -> str:
    nav_parts = []
    for href, label in NAV:
        cls = ' class="active"' if href == active else ""
        nav_parts.append(f'<a href="{href}"{cls}>{esc(label)}</a>')
    nav = "".join(nav_parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <p class="brand">Hotspawn Pick'em — line board</p>
  <p class="sub">{esc(subtitle)}</p>
  <nav>{nav}</nav>
</header>
<main>
{body}
</main>
<footer>
Built by Arena session <code>arena/180a42a0</code> from committed data in <code>slate/data/</code>
(<code>slate/build.py</code>). Analysis only — not betting advice. Hotspawn's own crowd percentages are
never used as a probability. Values that could not be read from a source stay blank and are listed on
the <a href="flagged.html">Flagged for review</a> page.
</footer>
</body>
</html>
"""


def card(number, label):
    return f'<div class="card"><div class="n">{esc(number)}</div><div class="l">{esc(label)}</div></div>'


# ------------------------------------------------------------------------------- read the data
def load_all():
    data = {
        "analysis": load_csv(DATA / "analysis.csv"),
        "fixtures": load_csv(DATA / "fixtures.csv"),
        "ratings": load_csv(DATA / "ratings.csv"),
        "lines": load_csv(DATA / "lines.csv"),
        "own": load_csv(DATA / "own_lines.csv"),
        "flags": load_csv(DATA / "flags.csv"),
        "coverage": load_json(DATA / "coverage.json"),
        "provenance": load_json(DATA / "provenance.json"),
        "bundle": load_json(DATA / "analysis.json"),
    }
    return data


# ----------------------------------------------------------------------- cross-table verification
def norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def same_team(a: str, b: str) -> bool:
    a, b = norm(a), norm(b)
    if not a or not b:
        return False
    if a == b:
        return True
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio() >= 0.86


def find_row(rows: list[dict], team_a: str, team_b: str, key_a: str, key_b: str) -> dict | None:
    for row in rows:
        a, b = row.get(key_a) or "", row.get(key_b) or ""
        if (same_team(a, team_a) and same_team(b, team_b)) or (same_team(a, team_b) and same_team(b, team_a)):
            return row
    return None


def external_tables():
    """The other sessions' published tables, read-only, with the file each row came from."""
    tables = []
    picks = load_csv(ROOT / "picks" / "data" / "fixtures.csv")
    if picks:
        tables.append({
            "name": "picks/ (session cc8f4dca)",
            "file": "picks/data/fixtures.csv",
            "url": "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/picks/data/fixtures.csv",
            "rows": picks, "a": "team_a", "b": "team_b", "start": "start_utc", "pick": "pick",
            "pick_pct": "pick_p", "prob_a": "ext_p_a",
        })
    today = load_csv(ROOT / "today" / "data" / "current.csv")
    if today:
        tables.append({
            "name": "today/ (session b90700c6)",
            "file": "today/data/current.csv",
            "url": "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/today/data/current.csv",
            "rows": today, "a": "team_a", "b": "team_b", "start": "start_utc", "pick": "pick",
            "pick_pct": "pick_pct", "prob_a": "market_p_a_pct",
        })
    board = load_csv(ROOT / "board" / "data" / "analysis.csv")
    if board:
        tables.append({
            "name": "board/ (session 8e782f95)",
            "file": "board/data/analysis.csv",
            "url": "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/board/data/analysis.csv",
            "rows": board, "a": "team_a", "b": "team_b", "start": "start_utc", "pick": "pick",
            "pick_pct": None, "prob_a": "ext_odds_a",
        })
    model = load_csv(ROOT / "model" / "data" / "lines.csv")
    if model:
        tables.append({
            "name": "model/ (session 91eff436)",
            "file": "model/data/lines.csv",
            "url": "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/model/data/lines.csv",
            "rows": model, "a": "team_a", "b": "team_b", "start": "scheduled_start_utc",
            "pick": "pick", "pick_pct": None, "prob_a": "market_p_a",
        })
    canonical = load_csv(ROOT / "data" / "matches.csv")
    if canonical:
        tables.append({
            "name": "data/matches.csv (canonical)",
            "file": "data/matches.csv",
            "url": "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/matches.csv",
            "rows": canonical, "a": "team_a", "b": "team_b", "start": "start_utc", "pick": "pick",
            "pick_pct": "pick_win_p_pct", "prob_a": "market_p_a_pct",
        })
    return tables


def build_audit(analysis: list[dict]) -> list[dict]:
    tables = external_tables()
    audit = []
    for row in analysis:
        entry = {
            "fixture_id": row["fixture_id"], "start_utc": row["start_utc"],
            "team_a": row["team_a"], "team_b": row["team_b"],
            "my_pick": row["pick"], "my_p_a": row["market_p_a_pct"] or row["own_p_a_pct"],
            "checks": {},
        }
        for table in tables:
            found = find_row(table["rows"], row["team_a"], row["team_b"], table["a"], table["b"])
            if not found:
                entry["checks"][table["file"]] = {"present": "no", "time": "", "pick": "", "url": table["url"]}
                continue
            start = (found.get(table["start"]) or "").replace("T", " ").replace("Z", "").strip()
            mine = (row["start_utc"] or "").replace("T", " ").replace("Z", "").strip()
            entry["checks"][table["file"]] = {
                "present": "yes",
                "time": "agree" if start[:16] == mine[:16] else f"differs ({start})",
                "pick": found.get(table["pick"]) or "",
                "url": table["url"],
                "name": table["name"],
            }
        audit.append(entry)
    return audit


# ------------------------------------------------------------------------------------- pages
def board_table(rows: list[dict], *, show_status=False, caption="") -> str:
    head = ("<tr><th>Match</th><th>Starts (UTC)</th><th>Tournament</th>"
            "<th class=\"num\">Market</th><th class=\"num\">Our model</th><th>Pick</th><th>Sources</th></tr>")
    body = []
    for row in rows:
        market_a, market_b = row.get("market_p_a_pct"), row.get("market_p_b_pct")
        own_a, own_b = row.get("own_p_a_pct"), row.get("own_p_b_pct")
        pick = row.get("pick") or ""
        pick_html = (f'<span class="pick">{esc(pick)} {num(row.get("pick_pct"))}</span>' if pick
                     else '<span class="pick none">no pick — see flag</span>')
        read_by = row.get("market_read_by") or ""
        market_html = ((f'<span class="pct">{esc(row.get("team_a"))} {num(market_a)}</span>'
                        + bar(market_a) +
                        f'<span class="pct mut">{esc(row.get("team_b"))} {num(market_b)}</span>'
                        + (f'<div class="mut" style="font-size:11.5px">{esc(read_by)} · '
                           f'{esc(row.get("market_captured_utc"))}</div>' if read_by else ""))
                       if market_a else '<span class="mut">— no readable price</span>')
        own_html = (f'<span class="pct">{esc(row.get("team_a"))} {num(own_a)}</span>' + bar(own_a) +
                    f'<span class="pct mut">{esc(row.get("team_b"))} {num(own_b)}</span>'
                    if own_a else '<span class="mut">— no official rating pair</span>')
        status = status_tag(row.get("live_status")) if show_status else ""
        fmt = row.get("best_of") or ""
        fmt_src = row.get("best_of_source") or "format not stated by any source read"
        body.append(
            "<tr>"
            f'<td data-label="Match"><b>{esc(row.get("team_a"))}</b> vs <b>{esc(row.get("team_b"))}</b>{status}'
            f'<div class="mut" style="font-size:12px">{"BO" + fmt + " · from " + esc(fmt_src) if fmt else esc(fmt_src)}</div>'
            f'<div class="mut" style="font-size:12px">{esc(row.get("pick_basis"))}</div></td>'
            f'<td data-label="Starts (UTC)">{esc(row.get("start_utc"))}</td>'
            f'<td data-label="Tournament">{esc(row.get("competition"))}'
            f'<div class="mut" style="font-size:12px">tier {esc(row.get("tier"))} · {esc(row.get("points"))} pts</div></td>'
            f'<td class="num" data-label="Market">{market_html}</td>'
            f'<td class="num" data-label="Our model">{own_html}</td>'
            f'<td data-label="Pick">{pick_html}</td>'
            f'<td data-label="Sources">{sources_cell(row)}</td>'
            "</tr>")
    cap = f"<caption>{esc(caption)}</caption>" if caption else ""
    return f'<div class="scroll"><table>{cap}{head}{"".join(body)}</table></div>'


def summary_cards(analysis: list[dict], fixtures: list[dict], flags: list[dict]) -> str:
    open_rows = analysis
    with_market = sum(1 for r in analysis if r.get("market_p_a_pct"))
    with_own = sum(1 for r in analysis if r.get("own_p_a_pct"))
    with_pick = sum(1 for r in analysis if r.get("pick"))
    stale = sum(1 for r in fixtures if (r.get("live_status") or "").startswith("stale"))
    return ('<div class="cards">' + "".join([
        card(len(open_rows), "fixtures open now"),
        card(with_market, "with an external market line"),
        card(with_own, "with our own rating line"),
        card(with_pick, "with a published pick"),
        card(len(flags), "flagged items"),
        card(stale, "stale rows still listed by Hotspawn"),
    ]) + "</div>")


def page_index(data: dict, audit: list[dict]) -> str:
    analysis, fixtures, flags = data["analysis"], data["fixtures"], data["flags"]
    coverage = data["coverage"] or {}
    hot = coverage.get("hotspawn", {})
    counts = coverage.get("counts", {})
    generated = coverage.get("generated_utc", "")
    body = [f"<h1>Every open Hotspawn Pick'em fixture, with a probability for each team</h1>",
            '<p class="lead">Captured from the board\'s own server-rendered payload '
            f'({esc(hot.get("fixtures_total"))} fixtures listed, {esc(hot.get("fixtures_open"))} with a lock '
            f'time still ahead of the capture). Probabilities come from external bookmaker prices and from our '
            'own model built on official rating data — never from Hotspawn\'s crowd percentages. '
            f'Capture time {esc(generated)} UTC.</p>',
            summary_cards(analysis, fixtures, flags),
            '<div class="note"><b>How to read a row.</b> <b>Market</b> is the de-vigged probability implied by '
            'the external bookmaker price (links in the Sources column). <b>Our model</b> is this project\'s own '
            'line, originated from the official HLTV ranking points and Valve Regional Standings points. '
            '<b>Pick</b> is the side with the higher combined probability; where the market and our model disagree '
            'the row says so and is listed on the Flagged page.</div>']
    if not analysis:
        body.append('<div class="note">No capture is committed yet — run '
                    '<code>slate/collect.py</code> (the CI job does it automatically) and rebuild.</div>')
    else:
        body.append("<h2>Open fixtures</h2>")
        body.append(board_table(analysis, caption=f"{len(analysis)} fixtures with a lock time in the future"))
    body.append("""<h2>Coverage</h2>
<p class="lead">Nothing on the board is skipped: the parse reads the same payload the page renders its cards
from, and the counts below are the board's own numbers next to what this project actually parsed.</p>""")
    rows = []
    for page_name, meta in sorted((hot.get("pages") or {}).items()):
        rows.append(f'<tr><td data-label="Page">{link(meta.get("url"), page_name)}</td>'
                    f'<td data-label="HTTP">{esc(meta.get("status"))}</td>'
                    f'<td data-label="Fixtures in payload">{esc(meta.get("state_rows"))}</td>'
                    f'<td data-label="Cards rendered">{esc(meta.get("cards_rendered"))}</td>'
                    f'<td data-label="Board says">{esc(meta.get("week_total_text") or "—")} '
                    f'{esc(meta.get("error") or "")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>Page</th><th>HTTP</th><th>Fixtures in payload</th>'
                '<th>Cards rendered</th><th>Board says</th></tr>' + "".join(rows) + "</table></div>")
    body.append(f'<div class="note"><b>Kickoff cross-check.</b> {esc(counts.get("kickoff_agrees_with_hltv"))} of '
                f'{len(analysis)} open fixtures have an HLTV listing row whose kickoff matches the payload '
                f'exactly, {esc(counts.get("kickoff_differs_from_hltv"))} differ, '
                f'{esc(counts.get("no_hltv_row"))} have no HLTV row. Full detail on the '
                '<a href="verified.html">Verification</a> page.</div>')
    return page("Hotspawn Pick'em — line board", "".join(body), "index.html",
                "CS2 + other titles · external market lines · our own rating-based lines · per-row sources")


def page_cs2(data: dict) -> str:
    analysis = [r for r in data["analysis"] if r.get("sport") == "cs2"]
    all_cs2 = [r for r in data["fixtures"] if r.get("sport") == "cs2"]
    stale = [r for r in all_cs2 if (r.get("live_status") or "").startswith("stale")]
    body = ["<h1>Counter-Strike 2</h1>",
            f'<p class="lead">{len(all_cs2)} CS2 rows in the board\'s payload '
            f'({len(analysis)} open at capture time). Rows Hotspawn still lists with a start date in the past '
            'are kept in the last table — they are not pickable and no bookmaker still prices them.</p>',
            board_table(analysis, caption="Open CS2 fixtures")]
    if stale:
        body.append("<h2>Stale rows Hotspawn still lists</h2>")
        rows = []
        for row in stale:
            rows.append(f'<tr><td data-label="Match">{esc(row.get("team_a"))} vs {esc(row.get("team_b"))}</td>'
                        f'<td data-label="Date listed">{esc((row.get("start_utc") or "")[:10])}</td>'
                        f'<td data-label="Tournament">{esc(row.get("competition"))}</td>'
                        f'<td data-label="Source">{link(row.get("source_url"), "Hotspawn")}</td></tr>')
        body.append('<div class="scroll"><table><tr><th>Match</th><th>Date listed</th><th>Tournament</th>'
                    '<th>Source</th></tr>' + "".join(rows) + "</table></div>")
    return page("CS2 — Hotspawn Pick'em line board", "".join(body), "cs2.html",
                "Counter-Strike 2 fixtures on the board, with sources")


def page_other(data: dict) -> str:
    other = [r for r in data["analysis"] if r.get("sport") not in ("cs2",)]
    fixtures = [r for r in data["fixtures"] if r.get("sport") not in ("cs2",)]
    body = ["<h1>Other titles on the board</h1>",
            f'<p class="lead">{len(fixtures)} rows on the Thunderpick and LoL pick\'em pages '
            f'({len(other)} open at capture time). The same rules apply: external prices where readable, our own '
            'line only where both teams have an official rating, blank and flagged otherwise.</p>',
            board_table(other, caption="Open fixtures outside CS2")]
    return page("Other titles — Hotspawn Pick'em line board", "".join(body), "lol.html",
                "Thunderpick and League of Legends rows from the same payload")


def page_tournaments(data: dict) -> str:
    analysis = data["analysis"]
    groups: dict[str, list[dict]] = {}
    for row in analysis:
        groups.setdefault(row.get("competition") or "(none)", []).append(row)
    body = ["<h1>By tournament</h1>",
            '<p class="lead">Every open fixture grouped by the competition the board names, with the count of '
            'fixtures this project could and could not price.</p>']
    overview = []
    for name, rows in sorted(groups.items()):
        priced = sum(1 for r in rows if r.get("market_p_a_pct"))
        body.append(f"<h2>{esc(name)}</h2>")
        overview.append(f'<tr><td data-label="Tournament">{esc(name)}</td>'
                        f'<td data-label="Open fixtures">{len(rows)}</td>'
                        f'<td data-label="With market line">{priced}</td>'
                        f'<td data-label="Tiers">{esc(", ".join(sorted({r.get("tier") or "?" for r in rows})))}</td></tr>')
        body.append(board_table(rows, caption=f"{len(rows)} fixtures"))
    if overview:
        body.insert(2, '<div class="scroll"><table><tr><th>Tournament</th><th>Open fixtures</th>'
                       '<th>With market line</th><th>Tiers</th></tr>' + "".join(overview) + "</table></div>")
    return page("Tournaments — Hotspawn Pick'em line board", "".join(body), "tournaments.html",
                "Open fixtures grouped by competition")


def page_tiers(data: dict) -> str:
    analysis = data["analysis"]
    groups: dict[str, list[dict]] = {}
    for row in analysis:
        groups.setdefault(row.get("tier") or "(none)", []).append(row)
    body = ["<h1>By tier</h1>",
            '<p class="lead">The board labels each fixture with a tier (S / B / C) and a points value; '
            'this is how the open slate splits across them.</p>']
    for name, rows in sorted(groups.items()):
        body.append(f"<h2>Tier {esc(name)} — {len(rows)} open fixtures</h2>")
        body.append(board_table(rows))
    return page("Tiers — Hotspawn Pick'em line board", "".join(body), "tiers.html",
                "Open fixtures grouped by the board's tier label")


def page_fixtures(data: dict) -> str:
    fixtures = data["fixtures"]
    body = ["<h1>Every fixture the board lists</h1>",
            '<p class="lead">The complete payload list, including rows Hotspawn still shows with a start date in '
            'the past and rows from other titles. Times are the payload\'s own UTC epoch, not the printed text. '
            'This table is the coverage proof: each row links the page it was read from.</p>']
    rows = []
    for row in fixtures:
        rows.append(f'<tr><td data-label="Match">{esc(row.get("team_a"))} vs {esc(row.get("team_b"))}</td>'
                    f'<td data-label="Sport">{esc(row.get("sport"))}</td>'
                    f'<td data-label="Start (UTC)">{esc(row.get("start_utc"))}</td>'
                    f'<td data-label="Lock (UTC)">{esc(row.get("lock_utc"))}</td>'
                    f'<td data-label="Tournament">{esc(row.get("competition"))}</td>'
                    f'<td data-label="Tier / points">{esc(row.get("tier"))} · {esc(row.get("points"))}</td>'
                    f'<td data-label="Status">{status_tag(row.get("live_status") or "")}</td>'
                    f'<td data-label="Pages">{esc(row.get("hotspawn_pages"))}</td>'
                    f'<td data-label="Source">{link(row.get("source_url"), "board")}</td></tr>')
    body.append('<p class="lead">' + str(len(fixtures)) + " rows.</p>")
    body.append('<div class="scroll"><table><tr><th>Match</th><th>Sport</th><th>Start (UTC)</th>'
                '<th>Lock (UTC)</th><th>Tournament</th><th>Tier / points</th><th>Status</th><th>Pages</th>'
                '<th>Source</th></tr>' + "".join(rows) + "</table></div>")
    return page("All fixtures — Hotspawn Pick'em line board", "".join(body), "fixtures.html",
                "Every row in the board's own payload, with the page it came from")


def page_lines(data: dict) -> str:
    lines, analysis = data["lines"], data["analysis"]
    coverage = data["coverage"] or {}
    pin = (coverage.get("pinnacle") or {})
    egw = (coverage.get("egw") or {})
    sess = (coverage.get("session_readings") or {})
    carried = (coverage.get("carried_readings") or {})
    body = ["<h1>External market lines</h1>",
            '<p class="lead">Only external sources are used for market probabilities — a bookmaker price or an '
            'aggregated odds table. Hotspawn publishes no odds and its crowd percentages are never converted into '
            'one. Each row keeps the bookmaker name, the capture time and the page it was read from, so a stale or '
            'moved price is visible.</p>',
            f'<div class="note"><b>This run.</b> Pinnacle moneyline quotes matched to fixtures: '
            f'{esc(pin.get("matched", 0))} of {esc(pin.get("quotes", 0))} quotes read. '
            f'EGamersWorld match pages matched: {esc(egw.get("matched", 0))}, refused/without a table: '
            f'{esc(egw.get("refused", 0))}. '
            f'The session read {esc(sess.get("matched", 0))} prices itself through the project\'s fetch '
            f'service from a capture file with one URL and read time per row, and '
            f'{esc(carried.get("used_for_headline", 0))} rows fall back to a source-linked reading another '
            f'session published. A refusal is recorded, never filled in.</div>']
    rows = []
    for row in lines:
        rows.append(f'<tr><td data-label="Fixture">{esc(row.get("fixture_id"))}</td>'
                    f'<td data-label="Book / source">{esc(row.get("book"))}<div class="mut" style="font-size:12px">'
                    f'{esc(row.get("source"))}</div><div class="mut" style="font-size:11.5px">'
                    f'{esc(row.get("read_by") or "")}</div></td>'
                    f'<td class="num" data-label="Odds">{esc(row.get("odds_a"))} / {esc(row.get("odds_b"))}</td>'
                    f'<td class="num" data-label="De-vigged">{num(row.get("p_a"))} / {num(row.get("p_b"))}</td>'
                    f'<td class="num" data-label="Margin">{num(row.get("overround_pct"))}</td>'
                    f'<td data-label="Captured">{esc(row.get("captured_utc"))}</td>'
                    f'<td data-label="Source">{link(row.get("source_url"), "page")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>Fixture</th><th>Book / source</th><th>Odds</th>'
                '<th>De-vigged</th><th>Margin</th><th>Captured</th><th>Source</th></tr>'
                + "".join(rows) + "</table></div>")
    body.append('<h2>Fixtures with no readable price</h2>')
    missing = [r for r in analysis if not r.get("market_p_a_pct")]
    rows = [f'<tr><td data-label="Match">{esc(r.get("team_a"))} vs {esc(r.get("team_b"))}</td>'
            f'<td data-label="Starts (UTC)">{esc(r.get("start_utc"))}</td>'
            f'<td data-label="Board">{link(r.get("hotspawn_url"), "Hotspawn")}</td>'
            f'<td data-label="Note">no price readable from the sources this run — shown blank</td></tr>'
            for r in missing]
    body.append('<div class="scroll"><table><tr><th>Match</th><th>Starts (UTC)</th><th>Board</th><th>Note</th></tr>'
                + ("".join(rows) if rows else '<tr><td>none — every open fixture carried a readable price</td></tr>')
                + "</table></div>")
    return page("Market lines — Hotspawn Pick'em line board", "".join(body), "lines.html",
                "External bookmaker prices, de-vigged, with capture times")


def page_own(data: dict) -> str:
    ratings, own = data["ratings"], data["own"]
    coverage = data["coverage"] or {}
    valve = coverage.get("valve") or {}
    body = ["<h1>Our own lines</h1>",
            '<p class="lead">This project originates its own probability for every fixture whose two teams both '
            'have a published official rating. Two independent official inputs are used and the arithmetic is '
            'published next to the number, so any row can be recomputed by hand.</p>',
            f'<div class="note"><b>Official inputs.</b> Valve Regional Standings file '
            f'{link(valve.get("blob_url"), esc(valve.get("file")))} read from Valve\'s own repository '
            f'({esc(valve.get("teams"))} team rows). HLTV world ranking points from '
            f'{link("https://www.hltv.org/ranking/teams/2026/october/12", "hltv.org/ranking/teams/2026/october/12")}. '
            'Elo scale 400, series transform '
            '<code>BO3 p²(3−2p)</code>. No bookmaker price enters this computation.</div>']
    body.append("<h2>Open fixtures</h2>")
    rows = []
    for row in own:
        fixture = next((a for a in data["analysis"] if a["fixture_id"] == row["fixture_id"]), {})
        rows.append(
            f'<tr><td data-label="Match">{esc(fixture.get("team_a"))} vs {esc(fixture.get("team_b"))}</td>'
            f'<td class="num" data-label="HLTV points model">{num(row.get("hltv_map_p_a"))} / {num(row.get("hltv_map_p_b"))}</td>'
            f'<td class="num" data-label="VRS points model">{num(row.get("vrs_map_p_a"))} / {num(row.get("vrs_map_p_b"))}</td>'
            f'<td class="num" data-label="Our map line">{num(row.get("own_map_p_a"))} / {num(row.get("own_map_p_b"))}</td>'
            f'<td class="num" data-label="Our series line">{num(row.get("own_series_p_a"))} / {num(row.get("own_series_p_b"))}'
            + (f'<div class="mut" style="font-size:12px">BO{esc(row.get("best_of"))}</div>' if row.get("best_of") else
               '<div class="mut" style="font-size:12px">format unstated → BO3 assumed, flagged</div>') + '</td>'
            f'<td class="num" data-label="Fair odds">{esc(row.get("fair_odds_a"))} / {esc(row.get("fair_odds_b"))}</td>'
            f'<td data-label="Arithmetic">{esc(row.get("basis") or "—")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>Match</th><th>HLTV points</th><th>VRS points</th>'
                '<th>Our map line</th><th>Our series line</th><th>Fair odds</th><th>Arithmetic</th></tr>'
                + "".join(rows) + "</table></div>")
    body.append("<h2>Team ratings used (every row sourced)</h2>")
    rows = []
    for row in ratings:
        rows.append(
            f'<tr><td data-label="Team">{esc(row.get("name"))}</td>'
            f'<td data-label="On open slate">{esc(row.get("on_open_slate"))}</td>'
            f'<td data-label="HLTV">{esc(row.get("hltv_name") or "—")} '
            f'{("(#" + str(row.get("hltv_rank")) + ", " + str(row.get("hltv_points")) + " pts)") if row.get("hltv_name") else ""}</td>'
            f'<td data-label="Valve VRS">{esc(row.get("vrs_name") or "—")} '
            f'{(str(row.get("vrs_points")) + " pts") if row.get("vrs_points") else ""}</td>'
            f'<td data-label="Resolution">{esc(row.get("method"))}'
            f'<div class="mut" style="font-size:12px">{esc(row.get("flag") or "")}</div></td>'
            f'<td data-label="Sources">{link(row.get("hltv_source_url"), "HLTV")} · '
            f'{link(row.get("vrs_source_url"), "Valve")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>Team (Hotspawn spelling)</th><th>On open slate</th>'
                '<th>HLTV ranking</th><th>Valve VRS</th><th>Resolution</th><th>Sources</th></tr>'
                + "".join(rows) + "</table></div>")
    body.append('<div class="note">A team with no exact name match in the official sources gets no rating row, '
                'so its fixtures carry no originated probability. Names are never substituted by similarity: an '
                'alias is used only when an entry with an evidence link exists, and every such row is flagged on '
                '<a href="flagged.html">Flagged for review</a>.</div>')
    return page("Own lines — Hotspawn Pick'em line board", "".join(body), "own-lines.html",
                "Probability originated from official rating data only")


def page_verified(data: dict, audit: list[dict]) -> str:
    tables = external_tables()
    coverage = data["coverage"] or {}
    counts = coverage.get("counts", {})
    body = ["<h1>Verification</h1>",
            '<p class="lead">Line-by-line checks this session performed against the sources themselves and '
            'against the other published tables in this repository. Nothing here overwrites another session\'s '
            'file: the audit only reads them and reports what it sees.</p>',
            '<div class="cards">' + "".join([
                card(counts.get("kickoff_agrees_with_hltv", 0), "kickoffs matching HLTV"),
                card(counts.get("kickoff_differs_from_hltv", 0), "kickoff disagreements"),
                card(counts.get("no_hltv_row", 0), "fixtures with no HLTV row"),
                card(counts.get("with_pick", 0), "rows with a pick"),
            ]) + "</div>"]
    body.append("<h2>Fixture identity and kickoff</h2>")
    rows = []
    for row in data["analysis"]:
        rows.append(
            f'<tr><td data-label="Match">{esc(row.get("team_a"))} vs {esc(row.get("team_b"))}</td>'
            f'<td data-label="Hotspawn (payload, UTC)">{esc(row.get("start_utc"))}</td>'
            f'<td data-label="HLTV kickoff">{esc(row.get("hltv_kickoff_utc") or "")}</td>'
            f'<td data-label="Check">{esc(row.get("kickoff_check"))}</td>'
            f'<td data-label="HLTV match">{link(row.get("hltv_url"), esc(row.get("hltv_match_id") or "—"))}</td>'
            f'<td data-label="Board">{link(row.get("hotspawn_url"), "Hotspawn")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>Match</th><th>Hotspawn payload (UTC)</th>'
                '<th>HLTV kickoff</th><th>Check</th><th>HLTV match</th><th>Board</th></tr>'
                + "".join(rows) + "</table></div>")
    body.append("<h2>Do the other published tables agree?</h2>")
    body.append('<p class="lead">For every fixture this session captured, the same fixture is looked up in each '
                'of the other sessions\' published datasets by team names, and its start time and pick are '
                'compared. "agree" means the published start time matches to the minute.</p>')
    for table in tables:
        rows = []
        agree = differ = absent = 0
        for entry in audit:
            check = entry["checks"].get(table["file"])
            if not check:
                continue
            if check["present"] == "no":
                absent += 1
                continue
            if check["time"] == "agree":
                agree += 1
            else:
                differ += 1
            rows.append(f'<tr><td data-label="Match">{esc(entry["team_a"])} vs {esc(entry["team_b"])}</td>'
                        f'<td data-label="Their start (UTC)">{esc(check["time"])}</td>'
                        f'<td data-label="Their pick">{esc(check["pick"])}</td>'
                        f'<td data-label="My pick">{esc(entry["my_pick"] or "—")}</td>'
                        f'<td data-label="Their file">{link(check["url"], table["file"])}</td></tr>')
        body.append(f"<h3>{esc(table['name'])} — {agree} agree, {differ} differ, {absent} not listed</h3>")
        body.append('<div class="scroll"><table><tr><th>Match</th><th>Their start (UTC)</th><th>Their pick</th>'
                    '<th>My pick</th><th>Their file</th></tr>' + "".join(rows) + "</table></div>")
    return page("Verification — Hotspawn Pick'em line board", "".join(body), "verified.html",
                "Per-row checks against the sources and against this repository's other tables")


def page_sources(data: dict) -> str:
    provenance = (data["provenance"] or {}).get("fetches", [])
    coverage = data["coverage"] or {}
    hot = coverage.get("hotspawn", {})
    body = ["<h1>Sources</h1>",
            '<p class="lead">Every fetch behind this page, with the time it was read, the HTTP status, the size '
            'and the SHA-256 of the body. Anyone can re-fetch the same URL and compare the hash — that is how a '
            'reading here can be checked rather than trusted.</p>']
    if hot.get("week_total_context"):
        body.append(f'<div class="note"><b>The board\'s own words</b> at capture time: '
                    f'<code>{esc(hot.get("week_total_context"))}</code></div>')
    rows = []
    for entry in provenance:
        rows.append(f'<tr><td data-label="URL">{link(entry.get("url"), entry.get("url"))}</td>'
                    f'<td data-label="Read at">{esc(entry.get("fetched_utc"))}</td>'
                    f'<td class="num" data-label="Status">{esc(entry.get("status"))}</td>'
                    f'<td class="num" data-label="Bytes">{esc(entry.get("bytes"))}</td>'
                    f'<td data-label="Method">{esc(entry.get("path"))}</td>'
                    f'<td data-label="SHA-256"><code style="font-size:11px">{esc((entry.get("sha256") or "")[:32])}</code></td>'
                    f'<td data-label="Note">{esc(entry.get("error") or "")}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>URL</th><th>Read at</th><th>Status</th><th>Bytes</th>'
                '<th>Method</th><th>SHA-256</th><th>Note</th></tr>' + "".join(rows) + "</table></div>")
    body.append(f'<div class="note">Raw bodies are not committed: only size and hash, so the repository stays '
                f'small and no third-party content is redistributed. Fetch log generated '
                f'{esc((data["provenance"] or {}).get("generated_utc"))}.</div>')
    return page("Sources — Hotspawn Pick'em line board", "".join(body), "sources.html",
                "Every URL read, with time, status and hash")


METHOD_BODY = """\
<h1>Method</h1>
<p class="lead">The rules this board follows, stated so that any number on it can be reproduced or refuted.</p>

<h2>1. Where the fixture list comes from</h2>
<p>The Hotspawn Play pick'em pages are Angular server-side-rendered pages that embed their whole render state in
<code>&lt;script id="ng-state"&gt;</code>. The fixture list, its competition, tier, stage, offered points and the
exact <code>scheduled_start_time</code> (milliseconds since the epoch, UTC) and lock offset are read from that
payload. The wall-clock text printed next to a match is <b>not</b> used: this project's own readings show the same
fixture printed as both UTC and UTC-4 in different sessions, while the epoch and the page's own countdown always
agree. Stale rows — fixtures whose scheduled start is months in the past but which the board still lists — are
kept and labelled, never silently dropped.</p>

<h2>2. Where probabilities come from</h2>
<p><b>External market line.</b> A two-way moneyline price pair from an external source (a bookmaker's public
page, or an aggregated odds table) is de-vigged:
<code>p_a = (1/o_a) / (1/o_a + 1/o_b)</code>. The margin <code>(1/o_a + 1/o_b − 1)</code> is published per row.
Hotspawn publishes no odds at all, and its crowd pick percentages are never converted into a probability —
they are copied into the data under column names ending in <code>_audit_only</code> for transparency, and no
build step reads them.</p>
<p><b>Our own line.</b> Two independent official inputs: the HLTV world-ranking points and Valve's published
Regional Standings points. Each becomes a per-map probability with the standard Elo logistic
<code>p = 1 / (1 + 10^((r_b − r_a)/400))</code>, then a series probability with
<code>BO3: p²(3−2p)</code> (BO1 identity, BO5 <code>p³(10−15p+6p²)</code>). Both official values are
published per row, so the arithmetic can be redone by hand. No bookmaker price is an input to this line.</p>
<p><b>Pick.</b> The side with the higher combined probability. Where the market line and our own line disagree on
the favourite, the row says so, follows the market, and is listed on the Flagged page.</p>

<h2>3. What is left blank</h2>
<p>If a price cannot be read, the price column is blank and the fixture is listed on the Flagged page. If a team
has no exact name match in the official rating sources, it gets no rating row and its fixtures get no originated
line. Nothing is inferred, interpolated, carried forward from an earlier capture, or filled in from a similar
name. Alias mappings are used only where an entry carries an evidence link, and each use is flagged.</p>

<h2>4. Verification</h2>
<p>Every fixture's kickoff is compared against HLTV's own listing and the result is published per row; the
fixtures are also looked up in the other datasets this repository publishes, and disagreements in start time or
pick are shown on the Verification page rather than corrected. Each source fetch is logged with its status and
SHA-256.</p>

<h2>5. Limits, stated plainly</h2>
<p>Odds move; every row carries its capture time. Aggregated odds tables can show a white-label price for the
operator that pays for the placement, so the bookmaker name is shown next to each price. Ratings-based
probabilities are only as good as the ratings and ignore roster changes between the rating date and the match.
This board is analysis, not betting advice, and it places no wagers.</p>
"""


def page_methodology() -> str:
    return page("Method — Hotspawn Pick'em line board", METHOD_BODY, "methodology.html",
                "Every rule behind the numbers, in one page")


def page_flags(data: dict) -> str:
    flags = data["flags"]
    severity_order = {"needs review": 0, "unverified": 1, "info": 2}
    flags = sorted(flags, key=lambda f: severity_order.get(f.get("severity") or "", 3))
    body = ["<h1>Flagged for review</h1>",
            '<p class="lead">Everything this session could not confirm from a source, every disagreement found '
            'between published tables, and every process caveat. Each row links the source to check it by. These '
            'items are non-blocking: the rows they affect are published blank rather than guessed.</p>']
    rows = []
    for flag in flags:
        links = " ".join(link(url, url.replace("https://", "")[:46]) for url in (flag.get("links") or "").split() if url.startswith("http"))
        rows.append(f'<tr><td data-label="ID"><code>{esc(flag.get("id"))}</code></td>'
                    f'<td data-label="Severity">{esc(flag.get("severity"))}</td>'
                    f'<td data-label="Subject">{esc(flag.get("subject"))}</td>'
                    f'<td data-label="Detail">{esc(flag.get("detail"))}</td>'
                    f'<td data-label="Sources">{links}</td></tr>')
    body.append('<div class="scroll"><table><tr><th>ID</th><th>Severity</th><th>Subject</th><th>Detail</th>'
                '<th>Sources</th></tr>' + "".join(rows) + "</table></div>")
    body.append("""<h2>Standing caveats</h2>
<div class="note"><b>Printed Hotspawn times are viewer-local.</b> The same fixture has been read as both UTC and
UTC-4 on these pages in different sessions. Every time on this site comes from the payload epoch, and the
countdown the page itself renders agrees with it.</div>
<div class="note"><b>EGamersWorld refuses automated reads.</b> Its pages return HTTP 403 to plain clients and
sometimes to the browser as well. When it refuses, the row keeps the price it could read from another source or
stays blank; refusals are recorded, not filled in.</div>
<div class="note"><b>Rosters change between rating snapshots.</b> Valve's standings file and HLTV's ranking are
dated snapshots; a transfer after the snapshot date is not modelled and shows up as rating-versus-market
divergence on the Verification page.</div>""")
    return page("Flagged for review — Hotspawn Pick'em line board", "".join(body), "flagged.html",
                "Unconfirmed values, disagreements and caveats, with sources")


def main() -> int:
    data = load_all()
    audit = build_audit(data["analysis"])
    with (DATA / "audit.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["fixture_id", "start_utc", "team_a", "team_b", "table", "present",
                         "their_start", "their_pick", "my_pick", "file_url"])
        for entry in audit:
            for table, check in entry["checks"].items():
                writer.writerow([entry["fixture_id"], entry["start_utc"], entry["team_a"], entry["team_b"],
                                 table, check["present"], check["time"], check["pick"],
                                 entry["my_pick"], check["url"]])
    pages = {
        "index.html": page_index(data, audit),
        "cs2.html": page_cs2(data),
        "lol.html": page_other(data),
        "tournaments.html": page_tournaments(data),
        "tiers.html": page_tiers(data),
        "fixtures.html": page_fixtures(data),
        "lines.html": page_lines(data),
        "own-lines.html": page_own(data),
        "verified.html": page_verified(data, audit),
        "sources.html": page_sources(data),
        "methodology.html": page_methodology(),
        "flagged.html": page_flags(data),
    }
    for name, body in pages.items():
        (HERE / name).write_text(body, encoding="utf-8")
    print(f"[slate] wrote {len(pages)} pages: {', '.join(sorted(pages))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
