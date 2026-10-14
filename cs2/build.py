#!/usr/bin/env python3
"""A4 — generate the mobile-first board under ``cs2/`` from ``cs2/data/*.csv``.

Every published row carries: both teams' win probabilities, the explicit pick, what the number is
built from, and a link to the exact source that produced it.  A value that was not confirmed is
printed as an em dash with its flag id — never as an invented number.

Pages: index (the board), lines (every price row, per book), own-lines (the VRS table),
fixtures (full slate incl. started/stale), tournaments (category index + one page per event),
coverage (what was read, what refused, site-count reconciliation), methodology, sources,
flagged (Flagged for Review).
"""
from __future__ import annotations

import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, ROOT, log, now_iso, read_csv, read_json  # noqa: E402

SITE = ROOT
PAGES = ["index.html", "lines.html", "own-lines.html", "fixtures.html", "tournaments.html",
          "coverage.html", "methodology.html", "sources.html", "flagged.html"]
NAV = [("index.html", "Board"), ("lines.html", "Market lines"), ("own-lines.html", "Our own lines"),
       ("tournaments.html", "Tournaments"), ("fixtures.html", "Full slate"),
       ("coverage.html", "Coverage"), ("methodology.html", "Method"),
       ("sources.html", "Sources"), ("flagged.html", "Flagged for review")]


def e(text) -> str:
    return html.escape(str(text), quote=True)


def dash(value, suffix="") -> str:
    if value is None or str(value).strip() in ("", "None"):
        return '<span class="dash" title="not confirmed from a source — see Flagged for review">—</span>'
    return e(value) + (e(suffix) if suffix else "")


def pct_cell(value) -> str:
    if value in (None, ""):
        return '<span class="dash">—</span>'
    try:
        num = float(value)
    except (TypeError, ValueError):
        return e(value)
    return f'<span class="num">{num:.1f}<span class="unit">%</span></span>'


def link(url: str, label: str, extra: str = "") -> str:
    if not url:
        return ""
    return (f'<a href="{e(url)}" target="_blank" rel="noopener nofollow"'
            f' title="opens the source that produced this value">{e(label)}</a>{extra}')


def page(title: str, active: str, body: str, as_of: str, note: str = "", prefix: str = "") -> str:
    nav = "".join(f'<a class="{"on" if href == active else ""}" href="{prefix}{href}">{e(label)}</a>'
                  for href, label in NAV)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0d1117">
<meta name="description" content="Hotspawn Pick'em CS2 board: win probability per team for every listed match, built from external bookmaker lines and our own VRS line. Mobile first.">
<title>{e(title)} · Hotspawn CS2 board</title>
<link rel="stylesheet" href="{prefix}style.css">
</head><body>
<header class="top">
  <div class="brand"><span class="mark">CS2</span>
    <div><strong>Hotspawn Pick&#8217;em board</strong><small>independent lines · mobile first · not betting advice</small></div>
  </div>
  <p class="asof">captured <b>{e(as_of or 'unknown')}</b> UTC{note}</p>
  <nav class="scrollnav">{nav}</nav>
</header>
<main>{body}</main>
<footer class="foot">
  <p>Session <code>arena/a174d77f</code> · generated {e(now_iso())} by <code>cs2/build.py</code> from
  <code>cs2/data</code> · refreshed automatically by <code>.github/workflows/cs2-a174d77f.yml</code>.</p>
  <p>Probabilities come from external bookmaker prices (de-vigged) and our own rating line.
  Hotspawn&#8217;s crowd pick percentages are excluded from every number on this site; they appear only on the
  <a href="{prefix}coverage.html">coverage page</a> as evidence that they were seen and dropped.
  Analysis only — not betting advice.</p>
</footer>
</body></html>
"""


FILTER_JS = """<script>
(function(){
  var cards = [].slice.call(document.querySelectorAll('#main-cards .card, main .card'));
  var comps = document.getElementById('fComp'), tiers = document.getElementById('fTier'), line = document.getElementById('fLine');
  var shown = document.getElementById('shown');
  function apply(){
    var n = 0;
    cards.forEach(function(c){
      var ok = (!comps.value || c.dataset.comp === comps.value)
            && (!tiers.value || c.dataset.tier === tiers.value)
            && (!line.value || c.dataset.line === line.value);
      c.style.display = ok ? '' : 'none';
      if (ok) n++;
    });
    [].slice.call(document.querySelectorAll('h2.day')).forEach(function(h){
      var el = h.nextElementSibling, any = false;
      while (el && !el.classList.contains('day')) {
        if (el.classList.contains('card') && el.style.display !== 'none') any = true;
        el = el.nextElementSibling;
      }
      h.style.display = any ? '' : 'none';
    });
    if (shown) shown.textContent = n + ' of ' + cards.length + ' shown';
  }
  [comps, tiers, line].forEach(function(el){ if (el) el.addEventListener('change', apply); });
  apply();
})();
</script>"""


# ---------------------------------------------------------------------------- fixtures
def fmt_utc(iso: str) -> str:
    dt = None
    try:
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return e(iso or "—")
    return dt.strftime("%a %d %b · %H:%M UTC")


def card(row: dict, flags: list[dict], prefix: str = "") -> str:
    pa, pb = row["consensus_p_a_pct"], row["consensus_p_b_pct"]
    try:
        wa = float(pa)
    except (TypeError, ValueError):
        wa = 50.0
    pick_side = row["pick"]
    if row.get("hotspawn_match_url"):
        hs = link(row["hotspawn_match_url"], "Hotspawn match page")
    else:
        hs = link(row.get("hotspawn_url") or "https://play.hotspawn.com/lobby",
                  f"Hotspawn payload row {row['fixture_id']} (no per-match page was served to the runner)")
    src_bits = [hs]
    if row.get("market_url"):
        label = {"pinnacle_guest_api": "Pinnacle line", "egamersworld_match_page":
                 "EGamersWorld / book page"}.get(row.get("market_source"), "market line")
        src_bits.append(link(row["market_url"], f"{label} ({row.get('market_book') or 'book'})"))
    if row.get("poly_url"):
        src_bits.append(link(row["poly_url"], "Polymarket (prediction market)"))
    if row.get("vrs_url_a"):
        src_bits.append(link(row["vrs_url_a"], f"Valve VRS {row['team_a']}"))
    if row.get("vrs_url_b"):
        src_bits.append(link(row["vrs_url_b"], f"Valve VRS {row['team_b']}"))
    flag_html = "".join(f' <a class="chip flag" href="{prefix}flagged.html#{e(f["code"])}">{e(f["code"])}</a>'
                        for f in flags)
    state = row.get("state") or ""
    lock = ' · picks lock ' + e(row["lock_utc"]) if row.get("lock_utc") else ""
    pts = e(row["points"]) + " pts" if row.get("points") else "points n/a"
    best = str(row.get("best_of") or "").strip()
    bo = ""
    if best:
        digits = re.sub(r"[^0-9]", "", best)
        bo = " · BO" + e(digits or best)
        note = str(row.get("best_of_note") or "").strip()
        if row.get("best_of_source"):
            bo += " (" + link(row["best_of_source"], note or "source") + ")"
    market_note = ""
    if row.get("market_p_a_pct"):
        market_note = (f'overround {e(row["market_overround_pct"])}% · '
                       f'{e(row["market_odds_a"])} / {e(row["market_odds_b"])} · '
                       f'{e(row["market_n_books"])} price row(s) · read {e(row["market_captured_utc"])}')
    return f"""<article class="card" data-tier="{e(row['tier'])}" data-comp="{e(row['competition'])}"
 data-state="{e(state)}" data-line="{ 'yes' if row.get('market_p_a_pct') else 'no'}">
  <div class="chead">
    <div class="comp">{e(row['competition'] or '—')}
      <span class="pill">{e(row['tier'] or '?')} tier</span><span class="pill">{pts}</span>{bo}
    </div>
    <div class="when">{fmt_utc(row['start_utc'])} <span class="muted">{lock}</span></div>
  </div>
  <div class="teams">
    <div class="team {'win' if pick_side == row['team_a'] else ''}">
      <span class="tname">{e(row['team_a'])}</span>
      <span class="prob">{pct_cell(pa)}</span>
    </div>
    <div class="bar"><i style="width:{wa:.1f}%"></i><em>{wa:.1f}</em><em>{(100 - wa):.1f}</em></div>
    <div class="team {'win' if pick_side == row['team_b'] else ''}">
      <span class="tname">{e(row['team_b'])}</span>
      <span class="prob">{pct_cell(pb)}</span>
    </div>
  </div>
  <p class="basis">{e(row['consensus_basis'] or 'no confirmed basis — see flags')}{'; ' + market_note if market_note else ''}</p>
  <table class="split">
    <tr><th></th><th>Market (de-vigged)</th><th>Our own line (VRS)</th></tr>
    <tr><td>{e(row['team_a'])}</td><td>{pct_cell(row['market_p_a_pct'])}</td><td>{pct_cell(row['own_p_a_pct'])}</td></tr>
    <tr><td>{e(row['team_b'])}</td><td>{pct_cell(row['market_p_b_pct'])}</td><td>{pct_cell(row['own_p_b_pct'])}</td></tr>
  </table>
  <p class="pick">Pick: <strong>{dash(row['pick'])}</strong>
     {'<span class="pp">' + e(row['pick_pct']) + '%</span>' if row.get('pick_pct') else ''}
     <span class="why">{e(row['pick_basis'] or 'no pick published')}</span></p>
  {f'<p class="diverge">market vs our line: {e(row["divergence_pp"])} pp apart</p>' if row.get('divergence_pp') else ''}
  <p class="src">{' · '.join(b for b in src_bits if b)}</p>
  {f'<p class="flags">flags:{flag_html}</p>' if flag_html else ''}
</article>"""


# ---------------------------------------------------------------------------- pages
def build() -> int:
    rows = read_csv(DATA / "analysis.csv")
    market_rows = read_csv(DATA / "market_rows.csv")
    flags = read_csv(DATA / "flags.csv")
    summary = read_json(DATA / "summary.json", {}) or {}
    cap = read_json(DATA / "capture.json", {}) or {}
    provenance = read_json(DATA / "provenance.json", []) or []
    calibration = read_json(DATA / "calibration.json", {}) or {}
    by_fixture = defaultdict(list)
    for f in flags:
        by_fixture[f["fixture_id"]].append(f)
    as_of = summary.get("capture_generated_utc") or cap.get("generated_utc") or ""
    age_note = ""
    try:
        age_h = (datetime.now(timezone.utc) - datetime.strptime(
            as_of, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_h > 6:
            age_note = f' <span class="warn">⚠ {age_h:.0f} h old — the scheduled refresh did not run</span>'
    except (TypeError, ValueError):
        age_note = " <span class='warn'>⚠ capture timestamp unreadable</span>"

    open_rows = [r for r in rows if r["pickable"] == "yes"]
    counters = [
        (len(rows), "CS2 fixtures on the board"),
        (len(open_rows), "still pickable"),
        (sum(1 for r in open_rows if r["market_p_a_pct"]), "with an external line"),
        (sum(1 for r in open_rows if r["own_p_a_pct"]), "with our own line"),
        (sum(1 for r in open_rows if r["pick"]), "with a pick"),
        (len({f["fixture_id"] for f in flags}), "fixtures flagged"),
    ]
    comps = Counter(r["competition"] for r in open_rows)
    comps_all = Counter(r["competition"] for r in rows)

    # ---------------------------------------------------------------- index.html
    groups: dict[str, list] = defaultdict(list)
    for r in open_rows:
        groups[r["start_utc"][:10] or "unknown date"].append(r)
    body = [f'<section class="hero"><h1>Every CS2 match on the Hotspawn board, with a probability per team.</h1>'
            f'<p class="lead">Built only from external bookmaker prices (de-vigged) and our own line from Valve&#8217;s'
            f' Regional Standings. Hotspawn&#8217;s own crowd percentages are never used. A blank cell means the value was'
            f' not confirmed anywhere official — it is listed on <a href="flagged.html">Flagged for review</a>, not guessed.</p>'
            f'<div class="counters">' + "".join(f'<div class="counter"><b>{n}</b><span>{e(lab)}</span></div>'
                                                for n, lab in counters) + '</div></section>']
    body.append('<div class="filters"><label>Tournament <select id="fComp"><option value="">all</option>'
                + "".join(f'<option value="{e(c)}">{e(c)} ({comps[c]})</option>' for c in sorted(comps))
                + '</select></label><label>Tier <select id="fTier"><option value="">all</option>'
                + "".join(f'<option value="{t}">{t}</option>' for t in sorted({r["tier"] for r in open_rows if r["tier"]}))
                + '</select></label><label>Line <select id="fLine"><option value="">all</option>'
                  '<option value="yes">bookmaker line</option><option value="no">our line only</option>'
                '</select></label><span class="muted" id="shown"></span></div>')
    for day in sorted(groups):
        rows_d = groups[day]
        body.append(f'<h2 class="day">{e(day)} <span class="muted">{len(rows_d)} fixture(s)</span></h2>')
        body.extend(card(r, by_fixture.get(r["fixture_id"], [])) for r in rows_d)
    if not open_rows:
        body.append('<p class="empty">Nothing is pickable at this capture — every fixture in the payload is past its'
                    ' lock time. The full slate is still published on <a href="fixtures.html">Full slate</a>.</p>')
    body.append('<p class="foot-note"><a href="fixtures.html">started / stale rows</a> ·'
                ' <a href="lines.html">every price row</a> · <a href="coverage.html">coverage &amp; refusals</a></p>')
    body.append(FILTER_JS)
    write(SITE / "index.html", page("Board", "index.html", "\n".join(body), as_of, age_note))

    # ---------------------------------------------------------------- lines.html
    tr = ['<table class="grid"><thead><tr><th>fixture</th><th>book</th><th>odds A</th><th>odds B</th>'
          '<th>no-vig A</th><th>no-vig B</th><th>overround</th><th>kickoff gap</th><th>read by</th>'
          '<th>captured</th><th>source</th></tr></thead><tbody>']
    for m in market_rows:
        tr.append(f'<tr><td>{e(m["team_a"])} v {e(m["team_b"])}</td><td>{e(m["book"])}</td>'
                  f'<td>{dash(m["odds_a"])}</td><td>{dash(m["odds_b"])}</td>'
                  f'<td>{pct_cell(m["implied_p_a_pct"])}</td><td>{pct_cell(m["implied_p_b_pct"])}</td>'
                  f'<td>{dash(m["overround_pct"], "%")}</td><td>{dash(m["kickoff_gap_h"], " h")}</td>'
                  f'<td>{e(m["source"])}</td><td>{e(m["captured_utc"])}</td>'
                  f'<td>{link(m["url"], "open") or "—"}</td></tr>')
    if len(tr) == 1:
        tr.append('<tr><td colspan="11">No bookmaker served a two-way price to the runner at this capture. '
                  'Sources tried and their responses are on the <a href="coverage.html">coverage page</a>.</td></tr>')
    tr.append('</tbody></table>')
    write(SITE / "lines.html", page(
        "Market lines", "lines.html",
        '<section class="hero"><h1>Every price row, one line per book</h1><p class="lead">De-vigged with the '
        'multiplicative method: p(A) = (1/odds<sub>A</sub>) / (1/odds<sub>A</sub> + 1/odds<sub>B</sub>). '
        'A three-way market (draw offered) is never used for the pick&#8217;em question. "Kickoff gap" is the '
        f'difference between the book&#8217;s start time and the Hotspawn payload start time; a gap over '
        f'{e(summary.get("kickoff_tolerance_h", 6))} h means the price was refused, not used.</p></section>'
        + "\n".join(tr), as_of, age_note))

    # ---------------------------------------------------------------- own-lines.html
    tr = ['<table class="grid"><thead><tr><th>fixture</th><th>comp</th><th>VRS pts A</th><th>VRS pts B</th>'
          '<th>our P(A)</th><th>our P(B)</th><th>fair A</th><th>fair B</th><th>rating sources</th>'
          '<th>flag</th></tr></thead><tbody>']
    for r in rows:
        if r["pickable"] != "yes":
            continue
        src = " · ".join(x for x in (link(r["vrs_url_a"], "VRS " + r["team_a"]),
                                      link(r["vrs_url_b"], "VRS " + r["team_b"])) if x) or "—"
        tr.append(f'<tr><td>{e(r["team_a"])} v {e(r["team_b"])}</td><td>{e(r["competition"])}</td>'
                  f'<td>{dash(r["vrs_points_a"])}</td><td>{dash(r["vrs_points_b"])}</td>'
                  f'<td>{pct_cell(r["own_p_a_pct"])}</td><td>{pct_cell(r["own_p_b_pct"])}</td>'
                  f'<td>{dash(r["own_fair_odds_a"])}</td><td>{dash(r["own_fair_odds_b"])}</td>'
                  f'<td>{src}</td><td>{e(r["flags"]) or "—"}</td></tr>')
    tr.append('</tbody></table>')
    k = summary.get("own_line", {})
    write(SITE / "own-lines.html", page(
        "Our own lines", "own-lines.html",
        f'<section class="hero"><h1>Our own line, from official ratings only</h1><p class="lead">'
        f'P(A) = 1 / (1 + 10<sup>−k·(pts<sub>A</sub> − pts<sub>B</sub>)/400</sup>) with '
        f'k = {e(k.get("k"))} — our re-fit of Valve&#8217;s expected-win-rate slope on the match results Valve '
        f'publishes ({e(k.get("n_calibrated_on"))} matches, {e(k.get("basis"))}). Ratings: Valve Regional '
        f'Standings snapshot {e(k.get("rating_snapshot_as_of"))} '
        f'({e(k.get("rating_snapshot_age_days"))} days old at capture), pinned commit '
        f'<code>{e((k.get("valve_commit") or "")[:10])}</code>. A blank row means a team is not in Valve&#8217;s '
        f'published file — that is recorded, not estimated.</p></section>' + "\n".join(tr), as_of, age_note))

    # ---------------------------------------------------------------- tournaments
    tbody = ['<table class="grid"><thead><tr><th>tournament</th><th>fixtures on the board</th>'
             '<th>pickable now</th><th>with external line</th><th>with our line</th><th>page</th></tr></thead><tbody>']
    per_comp: dict[str, list] = defaultdict(list)
    for r in rows:
        per_comp[r["competition"] or "—"].append(r)
    slugs = {}
    for comp in sorted(per_comp, key=lambda c: (-sum(1 for r in per_comp[c] if r["pickable"] == "yes"), c)):
        group = per_comp[comp]
        open_g = [r for r in group if r["pickable"] == "yes"]
        slug = re.sub(r"[^a-z0-9]+", "-", comp.lower()).strip("-")[:48] or "untitled"
        slugs[comp] = slug
        tbody.append(f'<tr><td>{e(comp)}</td><td>{len(group)}</td><td>{len(open_g)}</td>'
                     f'<td>{sum(1 for r in open_g if r["market_p_a_pct"])}</td>'
                     f'<td>{sum(1 for r in open_g if r["own_p_a_pct"])}</td>'
                     f'<td><a href="t/{e(slug)}.html">open</a></td></tr>')
    tbody.append('</tbody></table>')
    write(SITE / "tournaments.html", page(
        "Tournaments", "tournaments.html",
        '<section class="hero"><h1>Subpages by category — one page per tournament on the board</h1>'
        '<p class="lead">Same rows and rules as the board, grouped by event so a phone screen shows one '
        'competition at a time. Every subpage links back to the shared <a href="flagged.html">Flagged for '
        'review</a> list.</p></section>' + "\n".join(tbody), as_of, age_note))
    (SITE / "t").mkdir(exist_ok=True)
    written = set()
    for comp, group in per_comp.items():
        slug = slugs[comp]
        if slug in written:
            continue
        written.add(slug)
        b = [f'<section class="hero"><h1>{e(comp)}</h1><p class="lead">{len(group)} fixture(s) on the board, '
             f'{sum(1 for r in group if r["pickable"] == "yes")} still pickable.</p></section>']
        b.extend(card(r, by_fixture.get(r["fixture_id"], []), prefix="../") for r in
                 sorted(group, key=lambda r: r["start_utc"]))
        write(SITE / "t" / f"{slug}.html",
              page(comp, "tournaments.html", "\n".join(b), as_of, age_note, prefix="../"))

    # ---------------------------------------------------------------- fixtures (full slate)
    fbody = ['<table class="grid"><thead><tr><th>kickoff</th><th>state</th><th>comp</th><th>tier</th>'
             '<th>pts</th><th>team A</th><th>P(A)</th><th>team B</th><th>P(B)</th><th>pick</th>'
             '<th>basis</th><th>flags</th><th>source</th></tr></thead><tbody>']
    for r in rows:
        fbody.append(f'<tr><td>{e(r["start_utc"])}</td><td>{e(r["state"])}</td><td>{e(r["competition"])}</td>'
                     f'<td>{e(r["tier"])}</td><td>{dash(r["points"])}</td>'
                     f'<td>{e(r["team_a"])}</td><td>{pct_cell(r["consensus_p_a_pct"])}</td>'
                     f'<td>{e(r["team_b"])}</td><td>{pct_cell(r["consensus_p_b_pct"])}</td>'
                     f'<td>{dash(r["pick"])}</td><td>{e(r["consensus_basis"]) or "—"}</td>'
                     f'<td>{e(r["flags"]) or "—"}</td>'
                     f'<td>{link(r["hotspawn_match_url"] or r["hotspawn_url"], "Hotspawn")}</td></tr>')
    fbody.append('</tbody></table>')
    write(SITE / "fixtures.html", page(
        "Full slate", "fixtures.html",
        '<section class="hero"><h1>Full CS2 slate as published by the board</h1><p class="lead">Everything in the '
        'site&#8217;s own payload at this capture, including rows whose lock has passed and stale listings the board '
        'still serves. Pickable rows are the only actionable ones.</p></section>' + "\n".join(fbody), as_of, age_note))

    # ---------------------------------------------------------------- coverage
    hs = (cap.get("sources") or {}).get("hotspawn") or {}
    pages = hs.get("pages") or []
    prow = ['<table class="grid"><thead><tr><th>page</th><th>HTTP</th><th>bytes</th><th>sha256 (first 12)</th>'
            '<th>payload rows</th><th>rendered cards</th><th>site&#8217;s own counts</th><th>captured</th>'
            '<th>error</th></tr></thead><tbody>']
    for p in pages:
        counts = p.get("counts") or {}
        tstr = " ".join(f"{t}:{n}" for t, n in sorted((counts.get("tiers") or {}).items()))
        total = counts.get("all_tiers_total")
        comp_total = counts.get("all_tournaments_total")
        n_comp = sum((counts.get("tournaments") or {}).values())
        prow.append(f'<tr><td>{link(p["url"], e(p["page"]))}</td><td>{e(p["status"])}</td>'
                    f'<td>{e(p["bytes"])}</td><td>{e((p["sha256"] or "")[:12])}</td>'
                    f'<td>{e(p["state_rows"])}</td><td>{e(p["cards"])}</td>'
                    f'<td>{e(p["week_text"] or "")} · tiers {e(tstr)} · all-tiers {e(total)} · '
                    f'tournament-sum {n_comp} · all-tournaments {e(comp_total)}</td>'
                    f'<td>{e(p["fetched_utc"])}</td><td class="err">{e(p["error"] or "")}</td></tr>')
    prow.append('</tbody></table>')
    cs2_rows = [p for p in pages]
    parsed_cs2 = sum(1 for r in rows)
    recon = (f'Payload rows across the {len(pages)} pick&#8217;em pages: {len(hs.get("fixtures") or [])}; CS2 rows kept in '
             f'the analysis: {parsed_cs2}. The site&#8217;s own filter counts (e.g. "All tiers (89)") are printed '
             f'next to our parsed counts per page; a difference is a coverage failure and is flagged, never hidden.')
    src_status = ['<table class="grid"><thead><tr><th>source</th><th>status</th><th>what it gave us</th>'
                  '<th>detail</th></tr></thead><tbody>']
    srcs = cap.get("sources") or {}
    for name in ("hotspawn", "pinnacle", "egamersworld", "vrs", "hltv", "polymarket"):
        blk = srcs.get(name) or {}
        detail = {k2: v2 for k2, v2 in blk.items()
                  if k2 in ("status", "error", "cs2_events", "list_rows", "pages_read", "plain_error",
                            "browser_error", "as_of", "file", "team_links")}
        gave = {"hotspawn": "fixture identity + exact UTC start/lock epochs",
                "pinnacle": "whole-match moneyline prices (decimal converted from American)",
                "egamersworld": "per-book aggregated prices on each match page",
                "vrs": "Valve Regional Standings points — our own line's only rating input",
                "hltv": "world ranking + match list cross-check",
                "polymarket": "prediction-market prices (own column, never a betting line)"}[name]
        src_status.append(f'<tr><td>{e(name)}</td><td>{e(blk.get("status"))}</td><td>{e(gave)}</td>'
                          f'<td class="mono">{e(json.dumps(detail, sort_keys=True)[:400])}</td></tr>')
    for a in (srcs.get("attempts") or []):
        src_status.append(f'<tr><td>{e(a["source"])}</td><td>{e(a.get("status") or "attempted")}</td>'
                          f'<td>nothing — refused or empty</td><td class="mono">{e(str(a.get("observation") or a.get("error") or "")[:220])}</td></tr>')
    src_status.append('</tbody></table>')

    # ---------- what the priced sources could possibly cover (the ceiling, stated as evidence)
    pin = srcs.get("pinnacle") or {}
    csl = pin.get("cs2_leagues") or []
    n_all = len(pin.get("leagues") or [])
    n_pin_cs2 = sum(int(l.get("matchup_count") or 0) for l in csl)
    open_n = sum(1 for r in rows if r.get("pickable") == "yes")
    ceil = [f'<h2>The coverage ceiling of the priced sources, as evidence</h2>',
            f'<p>Pinnacle&#8217;s public guest endpoint — the same feed its own CS2 page loads — listed '
            f'{n_all} esports leagues at {e(pin.get("captured_utc") or "this capture")}, of which '
            f'<b>{len(csl)}</b> were Counter-Strike, carrying <b>{n_pin_cs2}</b> priced matchups in total. '
            f'The board has <b>{open_n}</b> open CS2 fixtures. The difference is not a fetch failure on our '
            f'side: the tournaments below simply are not priced there, and every other feed we tried '
            f'(listed as refusals in the table above) either answered nothing or blocked the runner. Those '
            f'fixtures therefore carry our own line and <a href="flagged.html#A-NO-LINE">A-NO-LINE</a>, '
            f'never a number copied from a source that did not publish one.</p>']
    if csl:
        ceil.append('<table class="grid"><thead><tr><th>CS2 league priced by Pinnacle</th>'
                    '<th>league id</th><th>matchups priced</th><th>on our board?</th></tr></thead><tbody>')
        my_comps = {(r.get("competition") or "").lower() for r in rows}
        for l in csl:
            nm = str(l.get("name", ""))
            key = nm.replace("CS2 - ", "").lower()
            hits = sum(1 for r in rows if key[:12] in (r.get("competition") or "").lower())
            ceil.append(f'<tr><td>{e(nm)}</td><td>{e(l.get("id"))}</td>'
                        f'<td>{e(l.get("matchup_count"))}</td><td>{e(hits)} fixture row(s) share this name</td></tr>')
        ceil.append('</tbody></table>')
    else:
        ceil.append('<p>This capture did not record the league list, so no ceiling claim is made.</p>')
    write_part = "\n".join(ceil)

    prov_tbl = ['<table class="grid"><thead><tr><th>fetched</th><th>via</th><th>HTTP</th><th>bytes</th>'
                '<th>sha256</th><th>url</th></tr></thead><tbody>']
    for p in provenance[-160:]:
        prov_tbl.append(f'<tr><td>{e(p.get("fetched_utc"))}</td><td>{e(p.get("via"))}</td>'
                        f'<td>{e(p.get("status"))}</td><td>{e(p.get("bytes"))}</td>'
                        f'<td class="mono">{e((p.get("sha256") or "")[:16])}</td>'
                        f'<td class="mono wrap">{link(p.get("url"), (p.get("url") or "")[:90])}</td></tr>')
    prov_tbl.append('</tbody></table>')
    crowd_rows = [f for f in (hs.get("fixtures") or []) if f.get("crowd_pct_a_audit_only") not in (None, "")]
    write(SITE / "coverage.html", page(
        "Coverage", "coverage.html",
        '<section class="hero"><h1>Coverage: what the board holds, what we read, what refused us</h1>'
        f'<p class="lead">{recon}</p></section>' + "\n".join(prow) +
        '<h2>Sources</h2>' + "\n".join(src_status) + write_part +
        f'<h2>Crowd percentages — seen and excluded</h2><p>Fixtures whose payload carried a crowd pick field: '
        f'<b>{len(crowd_rows)}</b>. They are dropped before the analysis is written and are never a probability '
        f'input on any page of this site (enforced by <code>cs2/tests.py</code>).</p>' +
        '<h2>Request log (last 160 fetches)</h2>' + "\n".join(prov_tbl), as_of, age_note))

    # ---------------------------------------------------------------- methodology
    write(SITE / "methodology.html", page(
        "Method", "methodology.html",
        '<section class="hero"><h1>How every number here is produced</h1></section>'
        f"""<ol class="method">
<li><b>Fixtures.</b> The {len(pages)} public pick&#8217;em pages we crawl are Angular SSR; the
<code>&lt;script id="ng-state"&gt;</code> TransferState carries the whole fixture list, not only the rendered
cards, so nothing depends on how many cards the page chose to paint. Each row gives
<code>scheduled_start_time</code> and <code>lock_time</code> as epoch milliseconds — converted to UTC and
published in full. A fixture is pickable while its lock time is in the future.</li>
<li><b>External line.</b> Pinnacle&#8217;s public guest responses (the payload its own CS2 matchups page loads)
give the whole-match moneyline; EGamersWorld match pages give named books&#8217; aggregate prices. Both are
converted to decimal, de-vigged multiplicatively, and averaged across the books when more than one quotes the
fixture. Pinnacle, when it lists the fixture, is the headline because it sets the market other books follow.</li>
<li><b>Joining a price to a fixture.</b> Only exact normalised team-pair equality plus a start time within
{e(summary.get("kickoff_tolerance_h", 6))} h, and the pairing must be unique. Group stages where the same two
teams play twice are resolved by kickoff time; anything ambiguous is refused and flagged.</li>
<li><b>Our own line.</b> Valve Regional Standings points through
<code>P(A) = 1/(1+10^(−k·Δ/400))</code>. <code>k</code> is re-fitted by maximum likelihood on the match results
Valve publishes in the same repository ({e(calibration.get("n_total"))} matches over
{e(len(calibration.get("windows") or []))} snapshot windows), because Valve&#8217;s README states the raw curve
over-confidently separates strong and weak teams. Out-of-sample it beats the raw curve: log loss
{e(round((calibration.get("out_of_sample") or {}).get("raw_valve_k", {}).get("log_loss", 0), 4))} →
{e(round((calibration.get("out_of_sample") or {}).get("calibrated_train_k", {}).get("log_loss", 0), 4))}, Brier
{e(round((calibration.get("out_of_sample") or {}).get("raw_valve_k", {}).get("brier", 0), 4))} →
{e(round((calibration.get("out_of_sample") or {}).get("calibrated_train_k", {}).get("brier", 0), 4))}. The curve is
fitted on match results, so it is a match-level probability; no series transform is layered on top of it
(format mixtures are already inside the data the slope was fitted on).</li>
<li><b>The pick.</b> The market favourite when a verified line exists, otherwise our own line&#8217;s favourite,
labelled as such on the row. When the two disagree on direction the row carries flag
<code>A-DIVERGE</code> and both numbers stay visible.</li>
<li><b>Blanks.</b> No price and no official rating for both teams → no probability, no pick, and a flag saying
what was missing. Nothing is filled in from a neighbouring round, an "average team", or Hotspawn&#8217;s own
crowd percentage.</li>
<li><b>Reproduce.</b> <code>python3 cs2/collect.py</code> (needs internet, run by the workflow) →
<code>VRS_REPO_DIR=&lt;clone&gt; python3 cs2/calibrate.py</code> → <code>python3 cs2/model.py</code> →
<code>python3 cs2/build.py</code> → <code>python3 cs2/tests.py</code>.</li>
</ol>""", as_of, age_note))

    # ---------------------------------------------------------------- verification
    vrec = read_json(DATA / "verification.json", {}) or {}
    checks = vrec.get("checks") if isinstance(vrec, dict) else vrec
    checks = checks or []
    vb = ['<section class="hero"><h1>Verification log — every check, its source and its result</h1>'
          '<p class="lead">Each row is a check a human (or an offline test) can repeat from the linked official'
          ' source. The rule used throughout: if a value cannot be re-derived from what was archived, it is not'
          ' published — it is blank and listed on <a href="flagged.html">Flagged for review</a>.</p></section>']
    if checks:
        vb.append('<table class="grid"><thead><tr><th>id</th><th>what was checked</th><th>method</th>'
                  '<th>official source</th><th>result</th><th>checked (UTC)</th><th>status</th></tr></thead><tbody>')
        for c in checks:
            status = c.get("status", "checked")
            vb.append(f'<tr><td>{e(c.get("id"))}</td><td class="wrap">{e(c.get("title"))}</td>'
                      f'<td class="wrap">{e(c.get("method"))}</td>'
                      f'<td class="wrap">{link(c.get("source_url"), c.get("source_label") or c.get("source_url"))}</td>'
                      f'<td class="wrap">{e(c.get("result"))}</td><td>{e(c.get("checked_utc"))}</td>'
                      f'<td><span class="chip {("ok" if status=="verified" else "warn")}">{e(status)}</span></td></tr>')
        vb.append('</tbody></table>')
    else:
        vb.append('<p>No manual verification log has been written for this capture yet.</p>')
    vb.append('<h2>Automatic re-checks (run in CI on every refresh, <code>cs2/tests.py</code>)</h2>'
              '<ul class="src-list"><li>Market probabilities are re-derived from the archived price pairs '
              '(multiplicative de-vig) and must match the published figure to 0.3 pp.</li>'
              '<li>Every own line is recomputed from the linked Valve standings row and must match to 0.2 pp.</li>'
              '<li>Every published rating link must point at the exact line of Valve&#8217;s file carrying that '
              'team and those points.</li>'
              '<li>No probability column may equal the Hotspawn crowd percentage of the same side (leakage guard).</li>'
              '<li>Every row carries a source link; every blank is flagged; every internal link resolves.</li></ul>')
    cmpath = DATA / "board_comparison_open_slate.json"
    comp = read_json(cmpath, None) if cmpath.exists() else None
    if comp:
        vb.append('<h2>Cross-board comparison</h2>'
                  f'<p>Our open rows were compared, fixture id by fixture id, with '
                  f'<code>{e(comp.get("source"))}</code> — a board built in this repository from the same '
                  f'Hotspawn slate (its prices were read from pages our runner is refused, see V-12, and its '
                  f'series length is assumed rather than sourced). We agree on the picked side in '
                  f'<b>{comp.get("agree")}</b> of <b>{comp.get("compared")}</b> comparable fixtures, disagree '
                  f'in <b>{comp.get("disagree")}</b>; they publish <b>{comp.get("their_external_lines")}</b> '
                  f'external lines where we publish <b>{comp.get("our_external_lines")}</b>. Disagreements are '
                  f'listed in full rather than averaged: a different side on a near coin-flip is exactly the '
                  f'kind of row a reader should look at twice.</p>')
        vb.append('<table class="grid"><thead><tr><th>fixture</th><th>matchup</th><th>their pick</th>'
                  '<th>they had a price?</th><th>our pick</th><th>our basis</th><th>our %</th></tr></thead><tbody>')
        for r in comp.get("rows") or []:
            if r.get("agree"):
                continue
            vb.append(f'<tr><td>{link("https://play.hotspawn.com/lobby", "fixture " + str(r["fixture"]))}</td>'
                      f'<td>{e(r["team_a"])} v {e(r["team_b"])}</td><td>{e(r["them_pick"])}</td>'
                      f'<td>{"yes (EGW page)" if r.get("them_external") else "no"}</td>'
                      f'<td>{e(r["us_pick"])}</td><td>{e(r["us_basis"])}</td><td>{e(r["us_pct"])}</td></tr>')
        vb.append('</tbody></table>')
    write(SITE / "verification.html", page("Verification", "verification.html", "\n".join(vb), as_of, age_note))

    # ---------------------------------------------------------------- sources
    srows = []
    for url in dict.fromkeys(p.get("url") for p in provenance if p.get("url")):
        srows.append(url)
    write(SITE / "sources.html", page(
        "Sources", "sources.html",
        '<section class="hero"><h1>Sources, one row per request</h1><p class="lead">Every URL the generator read to '
        'produce this capture, with its HTTP status and SHA-256 in the request log on the '
        '<a href="coverage.html">coverage page</a>. Raw bytes of the payloads that drive the numbers are kept under '
        '<code>cs2/data/raw/</code> (gzip) so any published figure can be re-derived offline.</p></section>'
        '<ul class="src-list">'
        + "".join(f'<li class="mono"><a href="{e(u)}" target="_blank" rel="noopener nofollow">{e(u)}</a></li>'
                  for u in srows[:200]) + '</ul>'
        + '<h2>Named references</h2><ul class="src-list">'
        + "".join(f'<li><a href="{e(u)}" target="_blank" rel="noopener nofollow">{e(l)}</a></li>' for l, u in [
            ("Hotspawn CS2 Pick'em lobby", "https://play.hotspawn.com/cs2-pickems"),
            ("Hotspawn lobby (all titles)", "https://play.hotspawn.com/lobby"),
            ("Pinnacle CS2 matchups page", "https://www.pinnacle.com/en/esports/games/cs2/matchups/"),
            ("Pinnacle public guest API (matchups)", "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups"),
            ("EGamersWorld CS2 matches", "https://egamersworld.com/counterstrike/matches"),
            ("Valve Regional Standings repository",
             "https://github.com/ValveSoftware/counter-strike_regional_standings"),
            ("Valve standings file used for ratings",
             "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
             + (summary.get("own_line", {}).get("vrs_file") or "live/2026/standings_global_2026_10_05.md").split("/")[-1]),
            ("HLTV world ranking", "https://www.hltv.org/ranking/teams"),
            ("HLTV matches", "https://www.hltv.org/matches"),
            ("This repository", "https://github.com/buffedlizard55-lab/MaltaProj1"),
        ]) + '</ul>', as_of, age_note))

    # ---------------------------------------------------------------- flagged
    grouped: dict[str, list] = defaultdict(list)
    for f in flags:
        grouped[f["code"]].append(f)
    fb = ['<section class="hero"><h1>Flagged for review</h1><p class="lead">Everything this board could not '
          'confirm, everything that disagrees with another published table, and every refusal by a source. '
          'None of it blocks the site; all of it is here so a human can check it after publication.</p></section>']
    for code in sorted(grouped):
        items = grouped[code]
        fb.append(f'<h2 id="{e(code)}">{e(code)} <span class="muted">{len(items)} row(s)</span></h2>'
                  f'<p class="expl">{e(items[0]["detail"])}</p><table class="grid"><thead><tr>'
                  '<th>fixture</th><th>kickoff</th><th>pickable</th><th>row source</th></tr></thead><tbody>')
        for it in items[:60]:
            fb.append(f'<tr><td>{e(it["team_a"])} v {e(it["team_b"])}</td><td>{e(it["start_utc"])}</td>'
                      f'<td>{e(it["pickable"])}</td><td>{link(it["row_url"], "open") or "—"}</td></tr>')
        fb.append('</tbody></table>')
    if not grouped:
        fb.append('<p>No flags at this capture.</p>')
    fb.append('<h2 id="A-SOURCE-REFUSAL">Source refusals recorded by the collector</h2>'
              '<p class="expl">Hosts that answered anything other than 200 to the runner. A refusal costs its own '
              'columns only — no value is ever substituted.</p><table class="grid"><thead><tr><th>url</th>'
              '<th>HTTP</th><th>error</th><th>when</th></tr></thead><tbody>')
    for p in provenance:
        if p.get("status") != 200:
            fb.append(f'<tr><td class="mono wrap">{e((p.get("url") or "")[:110])}</td><td>{e(p.get("status"))}</td>'
                      f'<td class="mono">{e(str(p.get("error") or "")[:160])}</td><td>{e(p.get("fetched_utc"))}</td></tr>')
    fb.append('</tbody></table>')
    write(SITE / "flagged.html", page("Flagged for review", "flagged.html", "\n".join(fb), as_of, age_note))
    log(f"build: wrote {len(PAGES)} pages + {len(written)} tournament pages; "
        f"{len(open_rows)} open rows, {len(flags)} flag rows")
    return 0


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(build())
