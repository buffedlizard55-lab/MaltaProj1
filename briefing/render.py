#!/usr/bin/env python3
"""HTML rendering for the briefing board (session arena/198cf31e).

Plain strings, no templating engine, no external assets.  Mobile-first: the match list is a
stack of cards that reads correctly at 360 px and uses a table only where a table is the
honest shape of the data (and every such table scrolls sideways inside its own wrapper).
"""
from __future__ import annotations

import html
import json
from pathlib import Path

from build import BASIS_LABEL

HERE = Path(__file__).resolve().parent

PAGES = [("index.html", "Executive summary"), ("picks.html", "All picks"),
         ("lines.html", "Outside market lines"), ("own-lines.html", "Our own lines"),
         ("coverage.html", "Coverage"), ("sources.html", "Sources"),
         ("flagged.html", "Flagged for Review"), ("methodology.html", "Methodology")]

HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
VRS_URL = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
           "live/2026/")


def esc(x) -> str:
    return html.escape(str(x if x is not None else ""), quote=True)


# ----------------------------------------------------------------------------- chrome
def page(title: str, active: str, body: str, generated: str) -> str:
    parts = []
    for fn, label in PAGES:
        current = ' aria-current="page"' if fn == active else ""
        parts.append(f'<a href="{fn}"{current}>{esc(label)}</a>')
    tabs = "".join(parts)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Hotspawn CS2 briefing</title>
<meta name="description" content="A sourced pick and win probability for every open Counter-Strike 2 Pick'em match on Hotspawn.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<a class="skiplink" href="#main">Skip to content</a>
<div class="wrap">
  <div class="brand">
    <b>Hotspawn CS2 briefing</b>
    <span class="sub">picks for every match · outside lines only</span>
    <span class="spacer"></span>
    <span class="sub">snapshot {esc(generated)}</span>
  </div>
  <nav class="tabs" aria-label="Sections">{tabs}</nav>
  <main id="main">
{body}
  </main>
  <footer>
    Analysis only, not betting advice. Hotspawn supplies fixture identity and lock times only;
    its crowd pick percentages are never used. Every published number links to the official
    source it came from; anything unconfirmable is left blank and listed on
    <a href="flagged.html">Flagged for Review</a>.
    Fixture list: <a href="{HOTSPAWN_LOBBY}">play.hotspawn.com/lobby</a>.
    Snapshot {esc(generated)}.
  </footer>
</div>
</body>
</html>
"""


def tag(text: str, cls: str = "") -> str:
    return f'<span class="tag {cls}">{esc(text)}</span>'


# ----------------------------------------------------------------------------- components
def match_card(fx: dict) -> str:
    fid = fx["fixture_id"]
    basis = fx.get("basis") or ""
    bcls = {"PINNACLE": "basis", "BOOK": "basis",
            "PREDICTION": "pred", "MODEL": "model"}.get(basis, "blank")
    blabel = BASIS_LABEL.get(basis, "No basis — nothing could be sourced")

    def side(name, p, is_pick):
        cls = "side win" if is_pick else "side"
        if p is None:
            return (f'<div class="{cls}"><span class="nm">{esc(name)}</span>'
                    f'<span class="pc">—</span><div class="bar"><i style="width:0%"></i></div></div>')
        return (f'<div class="{cls}"><span class="nm">{esc(name)}</span>'
                f'<span class="pc">{p * 100:.1f}%{" ✓" if is_pick else ""}</span>'
                f'<div class="bar"><i style="width:{max(0.0, min(100.0, p * 100)):.1f}%"></i></div>'
                f'</div>')

    if fx["p_a"] is None:
        a_pick = b_pick = False
    else:
        a_pick = fx["p_a"] > fx["p_b"]
        b_pick = fx["p_b"] > fx["p_a"]

    links = []
    q = fx.get("quote")
    if q:
        links.append((q.get("book") or q["basis"], q["url"]))
    links.append(("Hotspawn", fx.get("permalink") or HOTSPAWN_LOBBY))
    ra, rb = fx["rating_a"], fx["rating_b"]
    for r in (ra, rb):
        if r.get("url") and r.get("matched_name"):
            label = (f'{r["team"]} rating ({r["points"]})'
                     if r.get("points") is not None else f'{r["team"]} rating')
            links.append((label, r["url"]))
    srcs = "".join(f'<a href="{esc(u)}">{esc(t)}</a>' for t, u in links)

    fmt = f'BO{fx["best_of"]}' if fx.get("best_of") else "format unknown"
    return f"""<article class="match" id="m{fid}">
  <div class="meta">
    <span class="tour">{esc(fx["tournament"])}</span>
    <span class="spacer"></span>
    {tag(fx["tier"] or "tier n/a", "t" + (fx["tier"] or ""))}
    <span>{esc(fx["start_utc"][:16].replace("T", " "))} UTC</span>
    <span>{esc(fmt)}</span>
    <span class="small">#{esc(fid)}</span>
  </div>
  {side(fx["team_a"], fx["p_a"], a_pick)}
  {side(fx["team_b"], fx["p_b"], b_pick)}
  <div class="foot">
    {tag(basis or "NO BASIS", bcls)}
    <span class="basis-text">{esc(blabel)}</span>
    <span class="spacer"></span>
    <span class="small">locks {esc((fx["lock_utc"] or "")[11:16])} UTC</span>
  </div>
  <div class="foot"><div class="srcs">{srcs}</div></div>
</article>"""


def table(headers: list, rows: list, nums: set | None = None) -> str:
    nums = nums or set()
    th = "".join(f'<th class="{"num" if i in nums else ""}">{esc(h)}</th>'
                 for i, h in enumerate(headers))
    tr = []
    for r in rows:
        tr.append("<tr>" + "".join(
            f'<td class="{"num" if i in nums else ""}">{c}</td>' for i, c in enumerate(r)
        ) + "</tr>")
    return ('<div class="tablewrap"><table><thead><tr>' + th +
            "</tr></thead><tbody>" + "".join(tr) + "</tbody></table></div>")


# ----------------------------------------------------------------------------- pages
def render(result: dict) -> None:
    gen = result["generated_utc"]
    c = result["counts"]
    fit = result["fit"]
    open_fx = result["open"]
    flags = result["flags"]

    # ---------------------------------------------------------------- executive summary
    hero = f"""
  <section class="hero">
    <h1>Every open CS2 Pick'em match, with a pick and a probability</h1>
    <p class="lede">This is the whole board on one page. {c["open"]} open Hotspawn CS2
    fixtures, {c["picks"]} with a published pick. Probabilities come from outside betting and
    prediction markets first ({c["market"]} matches) and from our own officially-sourced rating
    line only where no market prices the match ({c["model"]} matches). Hotspawn's own crowd
    percentages are never used.</p>
    <div class="cta-row">
      <a class="btn" href="#picks">Jump to the picks →</a>
      <a class="btn ghost" href="picks.html">Full table view</a>
      <a class="btn ghost" href="flagged.html">Flagged for Review ({len(flags)})</a>
    </div>
    <div class="stats">
      <div class="stat"><b>{c["open"]}</b><span>Open CS2 fixtures</span></div>
      <div class="stat"><b>{c["picks"]}</b><span>Picks published</span></div>
      <div class="stat"><b>{c["market"]}</b><span>Priced by an outside market</span></div>
      <div class="stat"><b>{c["model"]}</b><span>Our own rating line</span></div>
    </div>
  </section>
  <div class="note"><b>Where everything lives.</b>
    <a href="#picks">Picks for every match</a> (below) ·
    <a href="lines.html">Outside market lines</a> ·
    <a href="own-lines.html">Our own lines for unpriced matches</a> ·
    <a href="coverage.html">Coverage of all {c["fixtures"]} Hotspawn CS2 fixtures</a> ·
    <a href="sources.html">Sources and what each one returned</a> ·
    <a href="methodology.html">How a pick is chosen</a> ·
    <a href="flagged.html">Flagged for Review</a>.
    This board re-reads Hotspawn and every outside source automatically every 4 hours; the
    snapshot time at the top of the page is the moment the data was captured.
  </div>"""

    matches = "".join(match_card(f) for f in open_fx)
    body = (hero + f'\n  <h2 id="picks">Picks for every open match</h2>\n'
            f'  <div class="matches">{matches}</div>')
    (HERE / "index.html").write_text(page("Executive summary", "index.html", body, gen))

    # ---------------------------------------------------------------- picks (table view)
    rows = []
    for f in open_fx:
        q = f.get("quote") or {}
        rows.append([
            f'<a href="index.html#m{f["fixture_id"]}">{esc(f["start_utc"][:16].replace("T"," "))}</a>',
            esc(f["tournament"]), esc(f["tier"] or "—"),
            f'<b>{esc(f["team_a"])}</b>', f'<b>{esc(f["team_b"])}</b>',
            f'{f["p_a"]*100:.1f}%' if f["p_a"] is not None else "—",
            f'{f["p_b"]*100:.1f}%' if f["p_b"] is not None else "—",
            f'<b>{esc(f["pick"])}</b>' if f["pick"] else "—",
            f'{f["p_pick"]*100:.1f}%' if f["p_pick"] is not None else "—",
            tag(f["basis"] or "NONE", {"PINNACLE": "basis", "BOOK": "basis",
                                       "PREDICTION": "pred", "MODEL": "model"}.get(
                                           f["basis"], "blank")),
            f'<a href="{esc(q.get("url") or f.get("permalink") or HOTSPAWN_LOBBY)}">'
            f'{esc(q.get("book") or "Hotspawn")}</a>',
        ])
    body = (f'  <h2>All picks ({c["picks"]} of {c["open"]})</h2>\n'
            '  <p class="small">Every row links to the official source behind its number. '
            'Tap a kickoff time to open the card on the executive summary.</p>\n'
            + table(["Start (UTC)", "Tournament", "Tier", "Team A", "Team B", "A %", "B %",
                     "Pick", "Pick %", "Basis", "Primary source"], rows, nums={5, 6, 8}))
    (HERE / "picks.html").write_text(page("All picks", "picks.html", body, gen))

    # ---------------------------------------------------------------- outside lines
    rows = []
    for f in open_fx:
        for q in f["quotes"]:
            thin = " (thin, not used)" if q.get("thin") else ""
            rows.append([
                esc(f["fixture_id"]),
                f'{esc(f["team_a"])} v {esc(f["team_b"])}',
                esc(q["basis"]) + thin, esc(q["book"]),
                f'{q["odds_a"]:.3f}', f'{q["odds_b"]:.3f}',
                f'{q["p_a"]*100:.1f}%', f'{q["p_b"]*100:.1f}%',
                f'{q["overround"]*100:.2f}%',
                f'<a href="{esc(q["url"])}">source</a>',
            ])
    body = ('  <h2>Outside market lines read this run</h2>\n'
            '  <p class="small">Prices are shown exactly as read, with the bookmaker\'s '
            'overround (margin) beside them. The probability is the two-way de-vigged value: '
            'p = (1/odds) / (1/oddsA + 1/oddsB). Pinnacle is its own public guest feed; the '
            'book rows are prices that bo3.gg relays with the bookmaker named; Polymarket is a '
            'prediction market, not a bookmaker, and is always labelled as such.</p>\n'
            + (table(["Fixture", "Match", "Matched as", "Source kickoff", "Tier", "Book",
                      "Odds A", "Odds B", "A %", "B %", "Overround", "Source"], rows,
                     nums={6, 7, 8, 9, 10})
               if rows else '  <div class="note">No outside price was read for any open '
                            'fixture in this snapshot.</div>'))
    (HERE / "lines.html").write_text(page("Outside market lines", "lines.html", body, gen))

    # ---------------------------------------------------------------- our own lines
    rows = []
    for f in open_fx:
        ra, rb = f["rating_a"], f["rating_b"]
        if f.get("model_p_a") is None:
            continue
        rows.append([
            esc(f["fixture_id"]), f'{esc(f["team_a"])} v {esc(f["team_b"])}',
            f'{ra["points"]} <span class="small">({esc(ra["matched_name"])})</span>',
            f'{rb["points"]} <span class="small">({esc(rb["matched_name"])})</span>',
            f'{ra["points"] - rb["points"]:+d}',
            f'BO{f["best_of"]}' if f.get("best_of") else "unknown",
            f'{f["model_p_a"]*100:.1f}%', f'{(1 - f["model_p_a"]) * 100:.1f}%',
            tag(f["basis"] if f["basis"] == "MODEL" else "market used", "model"),
            f'<a href="{esc(ra["url"])}">A</a> · <a href="{esc(rb["url"])}">B</a>',
        ])
    calib = (f'fitted this run on {fit["n"]} market-priced fixtures, RMSE '
             f'{fit["rmse_pp"]} pp, worst error {fit["max_abs_error_pp"]} pp'
             if fit["ok"] else
             f'<b>not calibrated this run</b> — {esc(fit["note"])}')
    body = (f'  <h2>Our own lines for matches no market prices</h2>\n'
            f'  <div class="note"><b>What this is.</b> A logistic transform of the official '
            f'Valve Regional Standings points difference, converted to a series probability '
            f'with the sourced best-of. The scale is {esc(fit["scale"])} rating points per 10:1 '
            f'map-odds ratio, {calib}. This is our model, not Valve\'s official forecast '
            f'formula, and it is published in full so it can be checked.</div>\n'
            f'  <p class="small">Ratings are from '
            f'<a href="{esc(result["vrs"].get("source_url", VRS_URL))}">'
            f'the official Valve standings file {esc(result["vrs"].get("file", ""))}</a>'
            f' (standings as of {esc(result["vrs"].get("as_of", ""))}). Where a team is missing '
            f'from that file, or the name is ambiguous inside it, the identity is resolved '
            f'against HLTV and the evidence link is in the row.</p>\n'
            + table(["Fixture", "Match", "A rating", "B rating", "Diff", "Format", "A %",
                     "B %", "Used", "Rating sources"], rows, nums={2, 3, 4, 6, 7}))
    (HERE / "own-lines.html").write_text(page("Our own lines", "own-lines.html", body, gen))

    # ---------------------------------------------------------------- coverage
    rows = []
    for f in result["fixtures"]:
        st = f["state"]
        cls = {"open": "basis", "locked": "model", "stale": ""}.get(st, "")
        rows.append([esc(f["fixture_id"]), esc(f["tournament"]), esc(f["tier"] or "—"),
                     f'{esc(f["team_a"])} v {esc(f["team_b"])}',
                     esc((f["start_utc"] or "—")[:16].replace("T", " ")),
                     esc((f["lock_utc"] or "—")[:16].replace("T", " ")),
                     tag(st, cls)])
    body = (f'  <h2>Coverage of all {c["fixtures"]} Hotspawn CS2 fixtures</h2>\n'
            f'  <p class="small">Every CS2 row in the Hotspawn pick\'em payload, including the '
            f'{c["stale"]} stale rows Hotspawn still lists (their lock times are in the past). '
            f'Only the {c["open"]} <b>open</b> fixtures carry picks — a locked match cannot be '
            f'picked. Counts: {c["open"]} open, {c["locked"]} locked, {c["stale"]} stale.</p>\n'
            + table(["Fixture", "Tournament", "Tier", "Match", "Start (UTC)", "Lock (UTC)",
                     "State"], rows))
    (HERE / "coverage.html").write_text(page("Coverage", "coverage.html", body, gen))

    # ---------------------------------------------------------------- sources
    rows = []
    for name, rec in sorted(result["capture"].get("sources", {}).items()):
        if isinstance(rec, dict) and "status" in rec:
            reqs = [rec]
        else:
            reqs = []
            for v in (rec or {}).values():
                if isinstance(v, list):
                    reqs.extend(x for x in v if isinstance(x, dict))
                elif isinstance(v, dict):
                    reqs.append(v)
        for r in reqs:
            rows.append([esc(name), esc(r.get("url", ""))[:110], esc(r.get("status")),
                         esc(r.get("bytes")), esc(r.get("fetched_utc")),
                         esc(r.get("error") or "")])
    note_bits = [
        ("Hotspawn", "fixture identity and UTC lock times only; crowd pick percentages are "
                     "discarded at parse time and never written to disk"),
        ("Pinnacle", "public guest API, sport 12 (esports)"),
        ("bo3.gg", "public API; supplies the series format and the bookmaker price it relays"),
        ("Polymarket", "Gamma API series 10310; a prediction market, always labelled"),
        ("Valve", f'official Regional Standings file {result["vrs"].get("file", "")}'),
        ("HLTV", f'world-ranking rows parsed: '
                 f'{len((result["hltv"].get("world_ranking") or {}).get("rows", []))}'),
    ]
    notes = "".join(f'<li><b>{esc(a)}</b> — {esc(b)}</li>' for a, b in note_bits)
    body = (f'  <h2>Sources and what each returned this run</h2>\n  <ul>{notes}</ul>\n'
            + table(["Source", "URL", "HTTP", "Bytes", "Captured (UTC)", "Error"], rows,
                    nums={2, 3}))
    (HERE / "sources.html").write_text(page("Sources", "sources.html", body, gen))

    # ---------------------------------------------------------------- flagged
    counts: dict[str, int] = {}
    for code, _fid, _msg, _url in flags:
        counts[code] = counts.get(code, 0) + 1
    summary = "".join(f'<li><code>{esc(code)}</code> — {n} row(s)</li>'
                      for code, n in sorted(counts.items()))
    rows = [[f'<code>{esc(code)}</code>',
             f'<a href="index.html#m{fid}">{esc(fid)}</a>' if fid else "—",
             esc(msg),
             f'<a href="{esc(url)}">source</a>' if url else "—"]
            for code, fid, msg, url in flags]
    body = (f'  <h2>Flagged for Review ({len(flags)})</h2>\n'
            f'  <div class="note">Nothing here is hidden and nothing here blocks the board. '
            f'These are the rows where a value could not be confirmed from an official source '
            f'(and is therefore left blank), where a name had to be matched non-exactly, or '
            f'where two sources disagree. Each entry links to the official page a reviewer '
            f'should open.</div>\n'
            + (f'  <h3>Counts by flag</h3>\n  <ul>{summary}</ul>\n' if summary else "")
            + (table(["Flag", "Fixture", "What needs review", "Evidence"], rows)
               if rows else '  <div class="note">No flags raised in this snapshot.</div>'))
    (HERE / "flagged.html").write_text(page("Flagged for Review", "flagged.html", body, gen))

    # ---------------------------------------------------------------- methodology
    body = f"""  <h2>How a pick is chosen</h2>

  <h3>1. The fixture list comes from Hotspawn, nothing else</h3>
  <p>The board reads the Angular TransferState payload embedded in
  <a href="{HOTSPAWN_LOBBY}">play.hotspawn.com/lobby</a> (and the CS2 and Thunderpick pick'em
  pages) and keeps the CS2 rows. From it we take only: the two team names, the tournament, the
  tier, the stage, the UTC kickoff, the UTC lock time and the permalink.
  <b>Hotspawn's crowd pick percentages are dropped at parse time</b> and are never written to
  disk, so they cannot reach a probability by accident.</p>

  <h3>2. Probabilities come from outside markets first</h3>
  <p>For each open fixture we look for a price, in this order, and stop at the first one we
  find:</p>
  <ol>
    <li><b>Pinnacle</b> — its own public guest API (sport 12, esports), whole-match moneyline
        only.</li>
    <li><b>Bookmaker</b> — the price bo3.gg's public API relays, with the bookmaker named and
        a link to the bookmaker's own match page.</li>
    <li><b>Polymarket</b> — its match-winner market. A prediction market, not a bookmaker; it
        is always labelled, and a market with a spread above {0.06} or volume below 500 is
        recorded but never used.</li>
    <li><b>Our own line</b> — see below, used only when no market prices the match.</li>
  </ol>
  <p>A match must be identified by <b>both</b> its two team names and a kickoff inside
  ±150 minutes. A name that matches only after stripping a corporate suffix (Esports, Gaming,
  Team, Club, GG) is joined but flagged.</p>

  <h3>3. De-vigging</h3>
  <p>Two-way proportional: <code>p(A) = (1/oddsA) / (1/oddsA + 1/oddsB)</code>. The
  bookmaker's overround is published next to every market-derived probability so the reader
  can see how much margin was removed. Pinnacle publishes American prices; these are converted
  to decimal exactly and stored as read.</p>

  <h3>4. Our own line for matches no market prices</h3>
  <p>Where neither a bookmaker nor a prediction market prices a match, we originate a line from
  the <a href="{esc(result["vrs"].get("source_url", VRS_URL))}">official Valve Regional
  Standings</a> ({esc(result["vrs"].get("as_of", ""))}):</p>
  <ul>
    <li>map win probability <code>p = 1 / (1 + 10^(-(ratingA - ratingB) / scale))</code></li>
    <li>series probability from the sourced best-of: BO3 <code>p²(3-2p)</code>,
        BO5 <code>p³(10-15p+6p²)</code></li>
    <li><code>scale</code> = {esc(fit["scale"])} rating points per 10:1 map-odds ratio,
        {'fitted by least squares against the de-vigged market prices read in this same run '
         f'(n={fit["n"]}, RMSE {fit["rmse_pp"]} pp, worst {fit["max_abs_error_pp"]} pp)' if fit["ok"]
         else 'not fitted this run — ' + esc(fit["note"])}</li>
  </ul>
  <div class="note warnbox"><b>This is our model, not Valve's official forecast formula.</b>
  It is fitted in-sample on a single day's market prices, so it is a description of how those
  markets priced rating gaps that day, not a validated predictor. Where a market line exists
  the market wins; our line is shown beside it and any disagreement in direction is flagged on
  the row and listed on <a href="flagged.html">Flagged for Review</a>.</div>

  <h3>5. The pick</h3>
  <p>The pick is simply the higher-probability side of the highest tier available. We do not
  average market and model. If the two sides price identically the pick is left blank rather
  than broken arbitrarily. If neither a market price nor official ratings for both teams can be
  sourced, the probability stays blank and the row is flagged — we never assume 50/50.</p>

  <h3>6. What is deliberately not done</h3>
  <ul>
    <li>Hotspawn crowd percentages are never an input.</li>
    <li>No series format is assumed from Hotspawn (its payload leaves <code>best_of</code>
        null); the format comes only from a source that states it, otherwise the model line is
        published as a single-map estimate and flagged.</li>
    <li>No historical price is carried into a current pick.</li>
    <li>Historical or secondary aggregator reports are not used as probabilities.</li>
  </ul>

  <h3>7. Automation</h3>
  <p><code>.github/workflows/briefing-198cf31e.yml</code> re-reads every source on a 4-hourly
  schedule, on push and on demand. It publishes only if collection, the render, the regression
  tests and a zero-broken-link check all pass — a failed run leaves the previous board live.
  Raw responses are archived (with HTTP status, byte count, SHA-256 and capture time) so every
  published number re-derives from bytes that were actually received.</p>"""
    (HERE / "methodology.html").write_text(page("Methodology", "methodology.html", body, gen))


def write_data(result: dict) -> None:
    import csv
    data = HERE / "data"
    data.mkdir(exist_ok=True)

    with (data / "picks.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fixture_id", "start_utc", "lock_utc", "tournament", "tier", "team_a",
                    "team_b", "p_a_pct", "p_b_pct", "pick", "pick_pct", "basis",
                    "basis_detail", "book", "odds_a", "odds_b", "overround_pct", "best_of",
                    "rating_a", "rating_b", "rating_source_a", "rating_source_b",
                    "model_p_a_pct", "primary_source_url", "hotspawn_permalink",
                    "source_matched_names", "source_start_utc", "source_id", "source_page"])
        for f in result["open"]:
            q = f.get("quote") or {}
            w.writerow([
                f["fixture_id"], f["start_utc"], f["lock_utc"], f["tournament"], f["tier"],
                f["team_a"], f["team_b"],
                "" if f["p_a"] is None else f'{f["p_a"] * 100:.2f}',
                "" if f["p_b"] is None else f'{f["p_b"] * 100:.2f}',
                f["pick"], "" if f["p_pick"] is None else f'{f["p_pick"] * 100:.2f}',
                f["basis"], BASIS_LABEL.get(f["basis"], ""), q.get("book", ""),
                q.get("odds_a", ""), q.get("odds_b", ""),
                "" if not q else f'{q["overround"] * 100:.3f}',
                f.get("best_of") or "", f["rating_a"]["points"], f["rating_b"]["points"],
                f["rating_a"]["url"], f["rating_b"]["url"],
                "" if f.get("model_p_a") is None else f'{f["model_p_a"] * 100:.2f}',
                q.get("url") or f.get("permalink") or HOTSPAWN_LOBBY,
                f.get("permalink") or HOTSPAWN_LOBBY,
                q.get("matched_names", ""), q.get("start_utc", ""),
                q.get("source_id", ""), q.get("source_page", "")])

    with (data / "flags.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["flag", "fixture_id", "detail", "source_url"])
        w.writerows(result["flags"])

    with (data / "fixtures.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["fixture_id", "state", "start_utc", "lock_utc", "tournament", "tier",
                    "team_a", "team_b", "permalink"])
        for f in result["fixtures"]:
            w.writerow([f["fixture_id"], f["state"], f["start_utc"], f["lock_utc"],
                        f["tournament"], f["tier"], f["team_a"], f["team_b"],
                        f.get("permalink") or HOTSPAWN_LOBBY])

    (data / "coverage.json").write_text(json.dumps(
        {"generated_utc": result["generated_utc"], "counts": result["counts"],
         "fit": result["fit"], "flag_counts": {
             code: sum(1 for f in result["flags"] if f[0] == code)
             for code in sorted({f[0] for f in result["flags"]})}}, indent=1))
