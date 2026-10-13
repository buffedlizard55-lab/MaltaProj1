#!/usr/bin/env python3
"""Generate gapfill/index.html and gapfill/flagged.html from data/gapfill.csv.

Probabilities are de-vigged from the two decimal prices of one read:
p_a = (1/dec_a) / ((1/dec_a) + (1/dec_b)). Rows without a verified two-sided
price keep blank probability fields and are listed as NOT PRICED.
"""
import csv
import html
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROWS = list(csv.DictReader(open(os.path.join(HERE, "data", "gapfill.csv"), encoding="utf-8")))
SNAPSHOT = "2026-10-13, reads between ~22:49 and ~22:54 UTC"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/cs2-pickems"
FLAGS = {
    "GF-01": ("Banda chuya v 6666: no market line found",
              "EGamersWorld match page shows only 1.8/1.8 placeholders with 0% for both teams. The match is not on the Polymarket CCT Europe tab (10 markets read). No line is used."),
    "GF-02": ("Ryvex v PCIFIC: team identity not confirmed",
              "Hotspawn lists PCIFIC. Polymarket lists WRAITH PCIFIC vs Ryvex (kickoff 14:00 UTC per EGamersWorld). EGamersWorld carries two pages for the same slot: 'WRAITH PCIFIC VS Ryvex' and 'PCIFIC Espor VS Ryvex'. The Polymarket price is shown for review only and is not used."),
    "GF-03": ("FORZE Reload v LFO 10: opponent conflict",
              "Hotspawn lists LFO 10 (match 1079624). Polymarket lists FORZE Reload vs Sökerorg at the same kickoff (17:00 UTC). The EGamersWorld page shows FORZE Reload with a blank opponent name and 1.8/1.8 placeholders. Blank until a source confirms the opponent."),
    "GF-04": ("mellren v Privateer: no usable two-sided price",
              "Polymarket quotes both teams at 97 cents with $0.00 volume, so the pair cannot be de-vigged into a meaningful probability. EGamersWorld shows 1.8/1.8 placeholders. Hotspawn says 'Privateer'; EGamersWorld and Polymarket say 'Privateer Gaming'. The alias is not confirmed."),
    "GF-05": ("Enjoy v B8 Academy: single source, zero volume",
              "Only one market source (Polymarket, $0.00 volume). Two reads taken about 3 minutes apart differ by 9.0 pp for Enjoy (59.5% then 61.0%); the later read is used. EGamersWorld shows 1.8/1.8 placeholders. The Hotspawn lobby row has no match ID (F-NOID). Event naming differs: Polymarket says 'CCT Europe Closed Qualifier: Series #12 Group A', EGamersWorld says 'CCT 2026 Europe Series 12 Closed Qualifier'; Hotspawn says 'Play-In'."),
    "GF-06": ("ex-RUSTEC v mellren: single source, limited volume",
              "Only one market source (Polymarket, about $56 volume). Two reads differ by 5.8 pp for ex-RUSTEC (64.5% then 61.4%); the later read is used. EGamersWorld shows 1.8/1.8 placeholders."),
    "GF-07": ("Polymarket time display is not consistent across page regions",
              "Polymarket's CCT Europe card times (for example G2 Ares v The Last Resort at 10:00 AM) do not agree with Hotspawn's UTC kickoff (14:00 UTC). Its listing times fit a fixed UTC-4 offset for all nine comparable rows. Kickoff was therefore confirmed from EGamersWorld page titles, which state UTC, not from Polymarket card times."),
}
SOURCES = [
    ("Hotspawn CS2 Pick'em lobby (fixture list)", HOTSPAWN_LOBBY),
    ("Hotspawn match page, ex-RUSTEC v mellren (1079622)", "https://www.hotspawn.com/matches/ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622"),
    ("Hotspawn match page, FORZE Reload v LFO 10 (1079624)", "https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624"),
    ("Polymarket CS2 listing", "https://polymarket.com/esports/cs2"),
    ("Polymarket CCT Europe tab", "https://polymarket.com/esports/cs2/cct-europe"),
    ("EGamersWorld, CCT Europe 2026 Series #12 Play-In", "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in-1sGIL2gAYu"),
    ("EGamersWorld, CCT Europe 2026 Series #11", "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
]


def esc(s):
    return html.escape(s or "", quote=True)


def devig(dec_a, dec_b):
    ia, ib = 1 / float(dec_a), 1 / float(dec_b)
    t = ia + ib
    return round(100 * ia / t, 1), round(100 * ib / t, 1)


def check_row(r):
    """Recompute probabilities for priced rows and assert they match the CSV."""
    if r["verdict"] != "PRICED":
        assert r["p_a_pct"] == "" and r["pick"] == "", r["row_key"]
        return None
    pa, pb = devig(r["pm_dec_a"], r["pm_dec_b"])
    assert abs(pa - float(r["p_a_pct"])) < 0.05, (r["row_key"], pa, r["p_a_pct"])
    assert abs(pb - float(r["p_b_pct"])) < 0.05, (r["row_key"], pb, r["p_b_pct"])
    assert r["pick"] in (r["team_a"], r["team_b"]), r["row_key"]
    return pa, pb


def card(r):
    priced = r["verdict"] == "PRICED"
    flags = [f for f in r["flags"].split(";") if f]
    links = [("Hotspawn", r["hotspawn_url"])]
    links += [("EGamersWorld", u) for u in r["egw_url"].split(";") if u]
    if r["pm_url"]:
        links.append(("Polymarket", r["pm_url"]))
    else:
        links.append(("Polymarket CCT Europe tab (checked, not listed)", "https://polymarket.com/esports/cs2/cct-europe"))
    link_html = " · ".join(f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(n)}</a>' for n, u in links)
    if priced:
        pa, pb = check_row(r)
        pick_pct = pa if r["pick"] == r["team_a"] else pb
        bars = (
            f'<div class="bar"><span>{esc(r["team_a"])}</span><b>{pa:.1f}%</b>'
            f'<i style="width:{pa:.1f}%"></i></div>'
            f'<div class="bar"><span>{esc(r["team_b"])}</span><b>{pb:.1f}%</b>'
            f'<i style="width:{pb:.1f}%"></i></div>'
        )
        status = f'<div class="pick">PICK: <strong>{esc(r["pick"])}</strong> ({pick_pct:.1f}%)</div>'
        conf = f'<div class="conf">Confidence: {esc(r["confidence"])} · market read {esc(r["market_read_utc"])}</div>'
    else:
        bars = '<div class="none">No verified two-sided line. Probabilities left blank.</div>'
        status = '<div class="pick nopick">NO PICK: not priced</div>'
        conf = ""
    return f"""
<article class="card {'priced' if priced else 'unpriced'}">
  <header>
    <div class="teams">{esc(r["team_a"])} <span>v</span> {esc(r["team_b"])}</div>
    <div class="meta">{esc(r["start_utc"])} · {esc(r["tournament_hotspawn"])}</div>
  </header>
  {status}
  {bars}
  {conf}
  <div class="flags">Flags: {esc(', '.join(flags)) or 'none'} · <a href="flagged.html">see Flagged for Review</a></div>
  <div class="links">{link_html}</div>
</article>"""


def table_row(r):
    priced = r["verdict"] == "PRICED"
    if priced:
        pa, pb = check_row(r)
        prob = f"{esc(r['team_a'])} {pa:.1f}% · {esc(r['team_b'])} {pb:.1f}%"
        pick = f"{esc(r['pick'])} ({(pa if r['pick']==r['team_a'] else pb):.1f}%)"
    else:
        prob, pick = "", "NO PICK"
    src = " · ".join(
        f'<a href="{esc(u)}" target="_blank" rel="noopener">{esc(n)}</a>'
        for n, u in [("Hotspawn", r["hotspawn_url"])]
        + [("EGW", u) for u in r["egw_url"].split(";") if u]
        + ([("Polymarket", r["pm_url"])] if r["pm_url"] else [])
    )
    return f"""<tr>
<td data-label="Match">{esc(r['team_a'])} v {esc(r['team_b'])}</td>
<td data-label="Kickoff (UTC)">{esc(r['start_utc'])}</td>
<td data-label="Win probability (external, de-vigged)">{prob or '<span class="blank">blank</span>'}</td>
<td data-label="Pick">{pick}</td>
<td data-label="Status">{'PRICED · ' + esc(r['confidence']) if priced else '<span class="blank">NOT PRICED</span> · see ' + esc(r['flags'])}</td>
<td data-label="Sources">{src}</td>
</tr>"""


CSS = """
:root{--ink:#111827;--muted:#6b7280;--line:#e5e7eb;--ok:#047857;--warn:#b45309;--bg:#f8fafc;--acc:#1d4ed8}
*{box-sizing:border-box}body{margin:0;font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header.top{background:#fff;border-bottom:1px solid var(--line);padding:14px 16px;position:sticky;top:0;z-index:2}
header.top h1{font-size:19px;margin:0}header.top nav{margin-top:6px;font-size:14px}
main{max-width:1000px;margin:0 auto;padding:16px}
a{color:var(--acc)}
.summary{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0 16px}
.summary div{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 14px;flex:1 1 150px}
.summary b{display:block;font-size:22px}
.note{font-size:14px;color:var(--muted)}
.cards{display:grid;gap:12px;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));margin-bottom:24px}
.card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}
.card.unpriced{border-left:5px solid var(--warn)}.card.priced{border-left:5px solid var(--ok)}
.teams{font-weight:700;font-size:17px}.teams span{color:var(--muted);font-weight:400}
.meta{font-size:13px;color:var(--muted);margin-bottom:8px}
.pick{font-weight:600;margin:6px 0;color:var(--ok)}.pick.nopick{color:var(--warn)}
.bar{position:relative;background:#eef2ff;border-radius:6px;height:30px;margin:5px 0;overflow:hidden}
.bar span,.bar b{position:absolute;top:6px;z-index:1;font-size:14px}.bar span{left:8px}.bar b{right:8px}
.bar i{position:absolute;left:0;top:0;bottom:0;background:#c7d2fe}
.none{font-size:14px;color:var(--muted);border:1px dashed var(--line);padding:8px;border-radius:8px}
.conf,.flags{font-size:13px;color:var(--muted);margin-top:6px}
.links{font-size:14px;margin-top:8px}
table{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:14px}
th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f1f5f9;font-size:13px}
.blank{color:var(--warn);font-weight:600}
@media (max-width:640px){
  table,thead,tbody,tr,td{display:block;width:100%}
  thead{display:none}
  tr{border-bottom:1px solid var(--line);padding:8px 0}
  td{border:0;padding:4px 10px}
  td::before{content:attr(data-label);display:block;font-size:12px;color:var(--muted)}
}
"""


def page(title, body, active):
    nav = [("index.html", "Gap-fill"), ("flagged.html", "Flagged for Review"), ("../index.html", "Repo home")]
    navhtml = " · ".join(
        (f"<strong>{n}</strong>" if h == active else f'<a href="{h}">{n}</a>') for h, n in nav
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>{CSS}</style></head>
<body>
<header class="top"><h1>{esc(title)}</h1><nav>{navhtml}</nav></header>
<main>{body}</main>
</body></html>
"""


def build_index():
    priced = [r for r in ROWS if r["verdict"] == "PRICED"]
    unpriced = [r for r in ROWS if r["verdict"] != "PRICED"]
    cards = "".join(card(r) for r in ROWS)
    rows = "".join(table_row(r) for r in ROWS)
    srcs = "".join(f'<li><a href="{esc(u)}" target="_blank" rel="noopener">{esc(n)}</a></li>' for n, u in SOURCES)
    body = f"""
<p class="note">Snapshot: {esc(SNAPSHOT)}. Probabilities come only from external market prices (no Hotspawn crowd percentages). Times are UTC.</p>
<div class="summary">
  <div>Open rows in gap-fill<b>{len(ROWS)}</b></div>
  <div>With a verified external line<b>{len(priced)}</b></div>
  <div>Not priced (flagged)<b>{len(unpriced)}</b></div>
</div>
<h2>Matches</h2>
<div class="cards">{cards}</div>
<h2>Table</h2>
<table><thead><tr><th>Match</th><th>Kickoff (UTC)</th><th>Win probability</th><th>Pick</th><th>Status</th><th>Sources</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Method</h2>
<p class="note">Each price is one read of a two-outcome market. Probability = implied probability of each side divided by the sum of both sides (de-vig). A match is only priced when team names and kickoff match the Hotspawn row. Single-source prices are marked Low confidence. Nothing is inferred or filled in.</p>
<h2>Sources</h2><ul>{srcs}</ul>
"""
    return page("Gap-fill: unpriced CS2 Pick'em rows", body, "index.html")


def build_flagged():
    items = []
    for k, (t, d) in FLAGS.items():
        used = [r for r in ROWS if k in r["flags"].split(";")]
        links = []
        for r in used:
            links.append(f'<a href="{esc(r["hotspawn_url"])}" target="_blank" rel="noopener">Hotspawn {esc(r["team_a"])} v {esc(r["team_b"])}</a>')
            for u in r["egw_url"].split(";"):
                if u:
                    links.append(f'<a href="{esc(u)}" target="_blank" rel="noopener">EGamersWorld page</a>')
            if r["pm_url"]:
                links.append(f'<a href="{esc(r["pm_url"])}" target="_blank" rel="noopener">Polymarket page</a>')
        items.append(
            f'<article class="card unpriced"><header><div class="teams">{k} · {esc(t)}</div></header>'
            f'<p>{esc(d)}</p><div class="links">{" · ".join(dict.fromkeys(links))}</div>'
            f'<div class="flags">Rows: {esc(", ".join(r["row_key"] for r in used))}</div></article>'
        )
    body = f"""
<p class="note">Flagged for Review: items that are not confirmed, conflict between sources, or are unverifiable. These are non-blocking and listed for manual review. Every item links its sources.</p>
<div class="cards">{''.join(items)}</div>
"""
    return page("Flagged for Review: gap-fill", body, "flagged.html")


if __name__ == "__main__":
    for r in ROWS:
        check_row(r)
    open(os.path.join(HERE, "index.html"), "w", encoding="utf-8").write(build_index())
    open(os.path.join(HERE, "flagged.html"), "w", encoding="utf-8").write(build_flagged())
    print("built", len(ROWS), "rows")
