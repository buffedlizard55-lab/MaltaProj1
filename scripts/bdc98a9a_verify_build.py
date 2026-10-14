#!/usr/bin/env python3
"""Render the source re-read verification pages (session arena/bdc98a9a).

Input:  reread/data/source_check.csv + reread/data/summary.json written by reread/collect.py
Output: reread/index.html, reread/flagged.html, reread/method.html, reread/style.css

Static HTML only, no JavaScript, so the pages render on any phone browser and in the GitHub Pages
publish step. Every published row keeps its exact source URL.
"""

from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VER = ROOT / "reread"
DATA = VER / "data"

BAD = {"mismatch", "refused", "dead", "placeholder", "not-checkable"}
CHIPS = {
    "match": "ok", "mismatch": "bad", "refused": "warn", "dead": "bad",
    "placeholder": "warn", "not-checkable": "muted",
}
KIND_LABELS = {
    "vrs": "Valve Regional Standings line", "hltv_match": "HLTV match page",
    "egw_market": "EGamersWorld match page (market quote)", "pinnacle": "Pinnacle page/API",
    "hotspawn": "Hotspawn fixture page (identity only)", "hltv_team": "HLTV team page",
    "polymarket": "Polymarket reference",
}


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def css() -> str:
    return """/* verify/ — session arena/bdc98a9a (source re-read verification) */
:root{--bg:#0f1420;--card:#182033;--ink:#eef2f8;--dim:#9fb0c8;--ok:#1f9d55;--bad:#c0392b;
--warn:#c07a00;--muted:#5b6b85;--link:#7cc4ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,
"Segoe UI",Roboto,sans-serif;padding:12px 12px 48px}
h1{font-size:1.35rem;margin:.2rem 0 .6rem}
h2{font-size:1.1rem;margin:1.4rem 0 .5rem}
a{color:var(--link)}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;padding:0;list-style:none}
.nav a{background:var(--card);border:1px solid #26314a;border-radius:999px;padding:7px 12px;
text-decoration:none;font-size:.9rem}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;margin:12px 0}
.tile{background:var(--card);border:1px solid #26314a;border-radius:12px;padding:10px}
.tile b{display:block;font-size:1.4rem}
.tile span{color:var(--dim);font-size:.8rem}
.note{background:#131a2a;border-left:4px solid var(--link);padding:10px 12px;border-radius:8px;
margin:12px 0}
details{background:var(--card);border:1px solid #26314a;border-radius:12px;padding:10px 12px;
margin:10px 0}
details>summary{cursor:pointer;font-weight:600}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{text-align:left;padding:6px 4px;border-bottom:1px solid #26314a;vertical-align:top}
th{color:var(--dim);font-weight:600;font-size:.8rem}
.chip{display:inline-block;border-radius:999px;padding:3px 9px;font-size:.78rem;font-weight:700;
color:#fff}
.chip.ok{background:var(--ok)}.chip.bad{background:var(--bad)}.chip.warn{background:var(--warn)}
.chip.muted{background:var(--muted)}
.u{word-break:break-all;font-size:.82rem;color:var(--dim)}
.obs{color:#ffd9d0}
.meta{color:var(--dim);font-size:.85rem}
.row1{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
@media(min-width:760px){body{max-width:900px;margin:0 auto}}
"""


def write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    print("wrote", path.relative_to(ROOT))


def nav(active: str) -> str:
    items = [("index.html", "Verification"), ("flagged.html", "Flagged for Review"),
             ("method.html", "Method & policy"), ("../exec/index.html", "Executive summary"),
             ("../everypick/", "Every-match picks")]
    out = []
    for href, label in items:
        cls = ' style="border-color:#7cc4ff"' if href == active else ""
        out.append(f'<li><a href="{esc(href)}"{cls}>{esc(label)}</a></li>')
    return '<ul class="nav">' + "".join(out) + "</ul>"


def load_rows() -> list[dict]:
    path = DATA / "source_check.csv"
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_summary() -> dict:
    path = DATA / "summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def claim_cell(row: dict) -> str:
    bits = [f'<a href="{esc(row["url"])}" rel="noopener nofollow">source</a>']
    if row.get("claimed"):
        bits.append(f"claimed <b>{esc(row['claimed'])}</b>")
    if row.get("observed"):
        bits.append(f'<span class="obs">source says: {esc(row["observed"])}</span>')
    if row.get("note"):
        bits.append(f'<span class="meta">{esc(row["note"])}</span>')
    if row.get("reused") == "yes":
        bits.append('<span class="meta">reused from a run less than 6 h old</span>')
    return "<br>".join(bits)


def claims_table(rows: list[dict]) -> str:
    body = []
    for r in rows:
        chip = CHIPS.get(r["verdict"], "muted")
        body.append(
            "<tr><td>" + f'<span class="chip {chip}">{esc(r["verdict"])}</span>'
            f'<div class="meta">{esc(KIND_LABELS.get(r["kind"], r["kind"]))}</div></td>'
            f"<td>{esc(r['team_a'])}" + (f" / {esc(r['team_b'])}" if r.get("team_b") else "") +
            f'<div class="meta">#{esc(r["fixture_id"])} · {esc(r["board"])}</div></td>'
            f"<td>{claim_cell(r)}</td></tr>")
    return ('<table><thead><tr><th>Re-read</th><th>Fixture</th><th>Cited source &amp; value</th>'
            "</tr></thead><tbody>" + "".join(body) + "</tbody></table>")


def fixture_sections(rows: list[dict]) -> str:
    order: list[tuple[str, str, str]] = []
    grouped: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r["fixture_id"], r["team_a"] + (" / " + r["team_b"] if r["team_b"] else ""))
        if key not in grouped:
            grouped[key] = []
            order.append((r["fixture_id"], r["team_a"], r["team_b"]))
        grouped[key].append(r)
    out = []
    for fid, a, b in order:
        key = (fid, a + (" / " + b if b else ""))
        rows_here = grouped[key]
        counts: dict[str, int] = {}
        for r in rows_here:
            counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        title = f"#{esc(fid)} {esc(a)}" + (f" vs {esc(b)}" if b else "")
        meta = " · ".join(f"{n} {v}" for v, n in sorted(counts.items()))
        out.append(f"<details><summary>{title} <span class=\"meta\">{esc(meta)}</span></summary>"
                   + claims_table(rows_here) + "</details>")
    return "".join(out)


def page(title: str, active: str, body: str, summary: dict) -> str:
    stamp = esc(summary.get("generated_utc", ""))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title><link rel="stylesheet" href="style.css"></head><body>
<h1>{esc(title)}</h1>
{nav(active)}
{body}
<p class="meta">Generated {stamp} by session <code>arena/bdc98a9a</code>. This page never changes
another board's data; a re-read that disagrees is listed for manual review, not silently fixed.</p>
</body></html>
"""


def build() -> dict:
    rows = load_rows()
    summary = load_summary()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    flagged = [r for r in rows if r["verdict"] in BAD]

    if not rows:
        body = ('<div class="note">No re-read has been published yet. Run '
                '<code>python3 reread/collect.py</code> in CI or locally with network access, then '
                '<code>python3 scripts/bdc98a9a_verify_build.py</code>.</div>')
    else:
        tiles = "".join(f'<div class="tile"><b>{n}</b><span>{esc(v)}</span></div>'
                        for v, n in sorted(counts.items(), key=lambda kv: -kv[1]))
        body = (
            '<div class="note"><b>What this is.</b> Every external URL cited by the merged pick '
            'boards was opened again and compared with the value the board prints beside it. '
            f'{len(rows)} cited values, {counts.get("match", 0)} re-read exactly as printed, '
            f'{len(flagged)} needing review (the '
            '<a href="flagged.html">Flagged for Review</a> page lists them with the source link and '
            'what the source says now).</div>'
            f'<div class="tiles">{tiles}</div>'
            '<h2>Per-fixture re-read</h2>'
            '<p class="meta">Tap a match to open its cited sources and the re-read result.</p>'
            + fixture_sections(rows))
    write(VER / "index.html", page("Source re-read verification", "index.html", body, summary))

    if flagged:
        body = ('<div class="note">Rows where the live source did <b>not</b> confirm the published '
                'value, or could not be read by the runner. Each row keeps its link so a human can '
                'check it in one tap.</div>'
                '<h2>Disagreements and refusals</h2>' + claims_table(flagged))
    else:
        body = '<div class="note">Nothing flagged in the latest run.</div>'
    write(VER / "flagged.html", page("Flagged for Review — source re-read", "flagged.html", body,
                                     summary))

    kinds = summary.get("by_kind", {})
    kind_rows = "".join(
        f"<tr><td>{esc(KIND_LABELS.get(k, k))}</td><td>{esc(v.get('total', 0))}</td>"
        f"<td>{esc(v.get('match', 0))}</td><td>{esc(sum(1 for kk, vv in v.items() if kk in BAD))}"
        "</td></tr>" for k, v in sorted(kinds.items()))
    hosts = summary.get("by_host", {})
    host_rows = "".join(f"<tr><td>{esc(h)}</td><td>{esc(n)}</td></tr>"
                        for h, n in list(hosts.items())[:12])
    body = f"""
<div class="note"><b>Why this page exists.</b> The repository's boards publish prices and ratings
that were copied into data files by earlier sessions. An audit flagged that most of those values
were never re-read from the source afterwards. This tool re-reads them, on a schedule, and records
what the source says now.</div>
<h2>What is checked</h2>
<table><thead><tr><th>Kind</th><th>Cited</th><th>Re-read as printed</th><th>Needs review</th></tr>
</thead><tbody>{kind_rows or "<tr><td colspan=4>no run yet</td></tr>"}</tbody></table>
<h2>Hosts touched</h2>
<table><thead><tr><th>Host</th><th>Cited values</th></tr></thead><tbody>
{host_rows or "<tr><td colspan=2>no run yet</td></tr>"}</tbody></table>
<h2>Policy</h2>
<ul>
<li>Hotspawn is read for <b>fixture identity and series format only</b>. Its crowd percentages are
never parsed and never used as a probability.</li>
<li>A refusal (HTTP 403/429), a dead link (404) or an unparsable page is recorded as such. It is
never filled in with an assumed value.</li>
<li>This tool never edits another board's data. A disagreement is published on
<a href="flagged.html">Flagged for Review</a> with the source link.</li>
<li>The 1.80/1.80 EGamersWorld pair is recognised as a placeholder, not a market.</li>
<li>A row whose source is re-read less often than every 6 hours is marked "reused"; the row keeps
the timestamp of the run that actually read it.</li>
<li>Team names are compared against the evidence-backed rename map published by the
line-analysis board (<code>cs2/aliases.json</code>); a name that only matches through such an alias
is reported as <code>alias:</code>, never as a silent pass and never invented here.</li>
</ul>
<h2>Reproduce</h2>
<pre><code>python3 reread/collect.py            # re-read every cited URL (needs network)
python3 scripts/bdc98a9a_verify_build.py
python3 -m unittest tests.test_bdc98a9a_verify -v</code></pre>
<p class="meta">CI: <code>.github/workflows/verify-bdc98a9a.yml</code> — hourly, plus a run whenever
a board's data file changes. Validation runs on every branch; generated files are committed on
<code>main</code> only.</p>
"""
    write(VER / "method.html", page("Method — source re-read verification", "method.html", body,
                                    summary))
    write(VER / "style.css", css())
    return {"claims": len(rows), "flagged": len(flagged), "verdicts": counts}


if __name__ == "__main__":
    print("verify build:", json.dumps(build()))
    print("built", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
