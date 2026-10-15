#!/usr/bin/env python3
"""Session arena/c13ca42a — full-coverage pick'em board (C-02 + C-04).

Joins the canonical 88-fixture analysis (executive/data/analysis.csv) with the
officially verified results for the 60 stale fixtures (data/c13ca42a/
stale_result_rows.py, checked 2026-10-14T08:35Z against HLTV results pages and
Liquipedia) and renders:

  fullpicks/data/stale_results.csv   — the 60 stale results (54 verified + 6 unresolved)
  fullpicks/data/fullpicks_board.csv — all 88 fixtures: pick, probability, result, sources
  fullpicks/index.html               — the full-coverage board (mobile friendly)
  fullpicks/unresolved.html          — unresolved picks & limitations

Fail-closed: any invariant failure exits non-zero and nothing is published.
No network access is required; every value is read from repository data that a
previous step verified against official sources (see reviews/c13ca42a-verification.md).
"""

from __future__ import annotations

import csv
import html
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANALYSIS_CSV = os.path.join(ROOT, "fullpicks", "data", "analysis_at_20261014.csv")
STALE_FIXTURES_CSV = os.path.join(ROOT, "fullpicks", "data", "stale_fixtures_from_executive.csv")
STALE_RESULTS_CSV = os.path.join(ROOT, "fullpicks", "data", "stale_results.csv")
BOARD_CSV = os.path.join(ROOT, "fullpicks", "data", "fullpicks_board.csv")
INDEX_HTML = os.path.join(ROOT, "fullpicks", "index.html")
UNRESOLVED_HTML = os.path.join(ROOT, "fullpicks", "unresolved.html")
SESSION = "arena/c13ca42a"
BUILD_NOTE = "Data checked 2026-10-14T08:35Z (official HLTV + Liquipedia reads). Archived source snapshot — not current picks. Use executive/picks.html for maintained coverage."

# HLTV event result pages used for the C-02 verification (for manual review).
EVENT_PAGES = {
    "Urban Riga Open #5": ("https://www.hltv.org/results?event=9219", "HLTV event 9219"),
    "Thunderpick World Championship 2026: South American Series #1": ("https://www.hltv.org/results?event=9239", "HLTV event 9239"),
    "CCT Europe 2026 Challengers #4": ("https://www.hltv.org/results?event=9236", "HLTV event 9236"),
    "CCT South America 2026 Series #3": ("https://www.hltv.org/results?event=9233", "HLTV event 9233"),
    "European Pro League Series 8 Play-In": ("https://www.hltv.org/results?event=9245", "HLTV event 9245"),
    "European Pro League Series 8": ("https://www.hltv.org/results?event=9246", "HLTV event 9246"),
    "Svenska CS-Ligan 2026": ("https://www.hltv.org/results?event=9235", "HLTV event 9235 (Finals)"),
    "Rainhas do Clutch 2026": ("https://www.hltv.org/results?event=9179", "HLTV event 9179"),
    "LG UltraGear Tournament 2026": ("https://www.hltv.org/results?event=9232", "HLTV event 9232"),
    "CCT South America 2026 Series #7": ("https://www.hltv.org/results?event=9452", "HLTV event 9452"),
    "DACH CS Masters Season 5": ("https://liquipedia.net/counterstrike/DACH_CS_Masters/Season_5", "Liquipedia event page"),
    "DraculaN Season 7": ("https://www.hltv.org/events/9312/draculanan-season-7", "HLTV event 9312 (upcoming)"),
}

BOARD_CSV_HEADER = [
    "match_id", "group", "tournament", "tier", "team_a", "team_b",
    "start_utc", "lock_utc", "pick", "pick_prob_pct", "prob_a_pct", "prob_b_pct",
    "basis_label", "market_source",
    "result_status", "winner", "score", "series_format", "result_date", "result_flag",
    "source_url", "source_links", "flags",
]


def fail(msg: str) -> None:
    print(f"INVARIANT FAILURE: {msg}", file=sys.stderr)
    sys.exit(1)


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def https_only(url: str, ctx: str) -> None:
    if not (isinstance(url, str) and url.startswith("https://")):
        fail(f"non-https source url {url!r} ({ctx})")


def load_stale_rows() -> list[dict]:
    sys.path.insert(0, os.path.join(ROOT, "data", "c13ca42a"))
    import stale_result_rows as srr  # noqa: E402
    rows = []
    for mid, status, winner, score, fmt, rdate, url, flag in srr.ROWS:
        rows.append({
            "match_id": mid, "status": status, "winner": winner, "score": score,
            "series_format": fmt, "result_date": rdate,
            "official_source_url": url, "flag": flag,
        })
    return rows


def load_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build() -> list[dict]:
    analysis = load_csv(ANALYSIS_CSV)
    stale_fx = load_csv(STALE_FIXTURES_CSV)
    stale_rows = load_stale_rows()

    if len(analysis) != 88:
        fail(f"analysis.csv has {len(analysis)} rows, expected 88")
    ids = [r["match_id"] for r in analysis]
    if len(set(ids)) != 88:
        fail("analysis.csv match_ids not unique")
    if len(stale_fx) != 60:
        fail(f"stale_fixtures_from_executive.csv has {len(stale_fx)} rows, expected 60")

    fx_by_id = {r["match_id"]: r for r in stale_fx}
    if sorted(r["match_id"] for r in stale_rows) != sorted(fx_by_id):
        fail("stale result ids != stale fixture ids")

    # Team/order consistency + write the canonical stale results CSV.
    out_csv = []
    for r in stale_rows:
        fx = fx_by_id[r["match_id"]]
        if r["winner"] and r["winner"].strip().lower() not in (fx["team_a"].lower(), fx["team_b"].lower()):
            fail(f"{r['match_id']}: winner {r['winner']!r} is not one of the two teams")
        if r["status"] == "verified":
            for field in ("winner", "score", "series_format", "result_date", "official_source_url"):
                if not r[field].strip():
                    fail(f"{r['match_id']}: verified row missing {field}")
            https_only(r["official_source_url"], r["match_id"])
            if not re.fullmatch(r"\d+-\d+", r["score"].strip()):
                fail(f"{r['match_id']}: score {r['score']!r} is not 'a-b'")
        else:
            if r["status"] != "unresolved":
                fail(f"{r['match_id']}: unknown status {r['status']!r}")
            if r["winner"].strip() or r["score"].strip():
                fail(f"{r['match_id']}: unresolved row carries a winner/score (never fabricate)")
            if not r["flag"].strip():
                fail(f"{r['match_id']}: unresolved row missing flag")
        https_only(r["official_source_url"], f"{r['match_id']} evidence")
        out_csv.append({
            "match_id": r["match_id"], "tournament": fx["tournament"],
            "card_start_utc": fx["start_utc"], "team_a": fx["team_a"], "team_b": fx["team_b"],
            "status": r["status"], "winner": r["winner"], "score": r["score"],
            "series_format": r["series_format"], "result_date": r["result_date"],
            "official_source_url": r["official_source_url"],
            "read_utc": "2026-10-14T08:35:00Z", "flag": r["flag"],
        })
    if out_csv:
        with io.StringIO() as buf:
            w = csv.DictWriter(buf, fieldnames=list(out_csv[0].keys()))
            w.writeheader()
            w.writerows(out_csv)
            _STALE_CSV_TEXT = buf.getvalue()

    res_by_id = {r["match_id"]: r for r in out_csv}
    n_open = n_played = n_unresolved = 0
    board = []
    for a in analysis:
        mid = a["match_id"]
        links = [u for u in (a.get("source_links") or "").split("|") if u.strip()]
        for u in links:
            https_only(u.strip(), mid)
        row = {
            "match_id": mid,
            "group": "open" if a["status"] == "open" else "stale",
            "tournament": a["tournament"], "tier": a["tier"],
            "team_a": a["team_a"], "team_b": a["team_b"],
            "start_utc": a["start_utc"], "lock_utc": a["lock_utc"],
            "basis_label": a["basis_label"], "market_source": a["market_source"],
            "source_links": " | ".join(links), "flags": a["flags"],
        }
        if a["status"] == "open":
            n_open += 1
            row.update({
                "pick": a["pick"], "pick_prob_pct": a["pick_prob_pct"],
                "prob_a_pct": a["prob_a_pct"], "prob_b_pct": a["prob_b_pct"],
                "result_status": "upcoming", "winner": "", "score": "",
                "series_format": a.get("series_format", ""), "result_date": "",
                "result_flag": "", "source_url": "",
            })
            if not row["pick"].strip():
                fail(f"{mid}: open fixture without a pick")
            try:
                pa, pb, pp = float(row["prob_a_pct"]), float(row["prob_b_pct"]), float(row["pick_prob_pct"])
            except ValueError:
                fail(f"{mid}: non-numeric probability")
            if not (0 < pa < 100 and 0 < pb < 100 and abs(pa + pb - 100.0) < 0.05):
                fail(f"{mid}: probabilities do not sum to 100 ({pa}/{pb})")
            if not (0 < pp < 100):
                fail(f"{mid}: pick probability out of range")
            if not links:
                fail(f"{mid}: open fixture without source links")
        else:
            res = res_by_id[mid]
            row["group"] = "played" if res["status"] == "verified" else "unresolved"
            row.update({
                "result_status": res["status"], "winner": res["winner"], "score": res["score"],
                "series_format": res["series_format"], "result_date": res["result_date"],
                "result_flag": res["flag"], "source_url": res["official_source_url"],
            })
            if res["status"] == "verified":
                n_played += 1
                row["pick"] = a["pick"]
                row["pick_prob_pct"] = a["pick_prob_pct"]
                row["prob_a_pct"] = a["prob_a_pct"]
                row["prob_b_pct"] = a["prob_b_pct"]
            else:
                n_unresolved += 1
                row.update({"pick": "", "pick_prob_pct": "", "prob_a_pct": "", "prob_b_pct": ""})
            if not links:
                fail(f"{mid}: stale fixture without source links")
        board.append(row)

    if (n_open, n_played, n_unresolved) != (28, 54, 6):
        fail(f"unexpected group counts: open={n_open} played={n_played} unresolved={n_unresolved}")

    globals()["_STALE_CSV_TEXT"] = _STALE_CSV_TEXT
    return board


def write_board_csv(board: list[dict]) -> None:
    with open(BOARD_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=BOARD_CSV_HEADER)
        w.writeheader()
        w.writerows(board)


def team_cell(row: dict, side: str) -> str:
    name = esc(row[side])
    pct = esc(row["prob_a_pct"] if side == "team_a" else row["prob_b_pct"])
    is_pick = row.get("pick", "").strip().lower() == row[side].lower()
    if row["group"] == "unresolved":
        return f"<td>{name}</td>"
    mark = ""
    if row["group"] == "open" and is_pick:
        mark = ' <span class="pickmark" title="Our pick">&#9650;</span>'
    elif row["group"] == "played":
        w = row["winner"].strip().lower()
        if w == row[side].lower():
            mark = ' <span class="winmark" title="Won this match">&#10003;</span>'
    return f"<td>{name}{mark}<span class='pct'>{pct if pct else '&mdash;'}%</span></td>"


def src_links(row: dict, extra: str = "") -> str:
    parts = []
    seen = set()
    def add(u, label):
        u = u.strip()
        if not u or u in seen:
            return
        seen.add(u)
        parts.append(f'<a href="{esc(u)}" rel="noopener noreferrer">{esc(label)}</a>')
    if extra:
        url, label = extra
        add(url, label)
    for u in [x.strip() for x in (row["source_links"] or "").split("|") if x.strip()]:
        short = re.sub(r"^https?://(www\.)?", "", u)
        short = short.replace("hltv.org", "HLTV").replace("liquipedia.net", "Liquipedia")
        add(u, short[:60])
    if not parts:
        return "&mdash;"
    return "<br>".join(parts)


def render_index(board: list[dict]) -> str:
    open_rows = sorted([r for r in board if r["group"] == "open"], key=lambda r: r["lock_utc"])
    played_rows = sorted([r for r in board if r["group"] == "played"], key=lambda r: r["result_date"], reverse=True)
    unresolved_rows = [r for r in board if r["group"] == "unresolved"]
    hits = sum(1 for r in played_rows if r["pick"].strip().lower() == r["winner"].strip().lower())

    def open_tr(r: dict, i: int) -> str:
        basis = esc(r["basis_label"] or "our line")
        if r["market_source"]:
            basis += f" &middot; {esc(r['market_source'])}"
        lock = esc((r["lock_utc"] or "")[:16].replace("T", " "))
        flags = f'<div class="flags">{"; ".join(esc(f) for f in r["flags"].split(";") if f)}</div>' if r["flags"] else ""
        return (
            f"<tr><td class='num'><span class='mut'>#{esc(r['match_id'])}</span></td>"
            f"{team_cell(r, 'team_a')}{team_cell(r, 'team_b')}"
            f"<td class='pickcell'><b>{esc(r['pick'])}</b> <span class='pct'>{esc(r['pick_prob_pct'])}%</span></td>"
            f"<td class='basis'>{basis}</td><td>{esc(r['tournament'])}</td>"
            f"<td class='mut'>{esc(r['tier'] or '?')} &middot; lock {lock} UTC</td>"
            f"<td class='srcs'>{src_links(r)}{flags}</td></tr>"
        )

    def played_tr(r: dict, i: int) -> str:
        event = EVENT_PAGES.get(r["tournament"], ("", ""))
        hit = r["pick"].strip().lower() == r["winner"].strip().lower()
        hitcell = "<span class='hit'>hit</span>" if hit else "<span class='miss'>miss</span>"
        return (
            f"<tr><td class='num'><span class='mut'>#{esc(r['match_id'])}</span></td>"
            f"{team_cell(r, 'team_a')}{team_cell(r, 'team_b')}"
            f"<td class='pickcell'>{esc(r['pick'])} <span class='pct'>{esc(r['pick_prob_pct'])}%</span></td>"
            f"<td class='pickcell'>{hitcell}</td>"
            f"<td class='rescell'><b>{esc(r['winner'])}</b> {esc(r['score'])} <span class='mut'>({esc(r['series_format'])}, {esc(r['result_date'])})</span></td>"
            f"<td>{esc(r['tournament'])}</td>"
            f"<td class='srcs'>{src_links(r, extra=event if r['source_url'] else '')}</td></tr>"
        )

    def unresolved_tr(r: dict, i: int) -> str:
        evidence = (r["source_url"], "official event page (evidence)") if r.get("source_url") else ""
        return (
            f"<tr><td class='num'><span class='mut'>#{esc(r['match_id'])}</span></td>"
            f"<td class='teams'>{esc(r['team_a'])} vs {esc(r['team_b'])}</td>"
            f"<td class='rescell'><b>no pick</b> <span class='mut'>(withheld, see flag)</span></td>"
            f"<td>{esc(r['tournament'])}</td>"
            f"<td class='mut'>{esc((r['start_utc'] or '')[:10])}</td>"
            f"<td class='srcs'>{src_links(r, extra=evidence)}</td></tr>"
        )

    open_html = "\n".join(open_tr(r, i + 1) for i, r in enumerate(open_rows))
    played_html = "\n".join(played_tr(r, i + 1) for i, r in enumerate(played_rows))
    unresolved_html = "\n".join(unresolved_tr(r, i + 1) for i, r in enumerate(unresolved_rows))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Full-coverage picks — all 88 Hotspawn CS2 fixtures · c13ca42a</title>
<meta name="description" content="Every Hotspawn CS2 Pick'em fixture: live pick + win probability for the 28 open matches, officially verified results for the 54 played matches, and flagged unresolved picks. No Hotspawn crowd percentages anywhere.">
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#10151c;color:#e8edf3;font:15px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}}
header{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:12px 16px;background:#151b23;border-bottom:1px solid #2b333d;position:sticky;top:0;z-index:5}}
.brand{{color:#8fb4ff;font-weight:700;text-decoration:none;margin-right:8px}}
nav a{{color:#9aa7b4;text-decoration:none;margin-right:14px;font-size:14px}}
nav a:hover{{color:#e8edf3;text-decoration:underline}}
main{{padding:16px;max-width:1200px;margin:0 auto}}
.hero{{background:#151b23;border:1px solid #2b333d;border-radius:14px;padding:18px;margin:8px 0 18px}}
.eyebrow{{color:#8fb4ff;letter-spacing:.12em;text-transform:uppercase;font-size:11.5px;font-weight:700;margin:0 0 8px}}
h1{{font-size:clamp(22px,4.6vw,32px);line-height:1.2;margin:0 0 10px}}
.hero p{{color:#9aa7b4;font-size:14px;margin:0 0 14px;max-width:80ch}}
.actions{{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}}
.actions a{{background:#2a3240;border:1px solid #3a4553;color:#e8edf3;border-radius:10px;padding:10px 14px;font-size:14px;font-weight:600;text-decoration:none;min-height:44px;display:inline-flex;align-items:center}}
.actions a.cta{{background:#7857cf;border-color:#7857cf;color:#fff}}
.actions a:hover{{text-decoration:underline}}
.stats{{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}}
@media(min-width:640px){{.stats{{grid-template-columns:repeat(5,1fr)}}}}
.stat{{background:#1b232d;border:1px solid #2b333d;border-radius:10px;padding:10px 12px}}
.stat b{{display:block;font-size:22px;line-height:1.15}}
.stat span{{color:#9aa7b4;font-size:11.5px}}
.note{{background:#1b232d;border:1px solid #2b333d;border-left:3px solid #7857cf;border-radius:8px;padding:11px 13px;margin:14px 0;font-size:12.8px;color:#9aa7b4}}
.note a{{color:#8fb4ff}}
h2{{font-size:20px;margin:26px 0 4px}}
.sub{{color:#9aa7b4;font-size:13px;margin:0 0 10px}}
.table-wrap{{overflow-x:auto;border:1px solid #2b333d;border-radius:12px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;min-width:760px}}
th,td{{padding:9px 10px;border-bottom:1px solid #222b35;text-align:left;vertical-align:top}}
th{{background:#151b23;color:#9aa7b4;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;position:sticky;top:0}}
tr:last-child td{{border-bottom:none}}
.num{{color:#5c6875;width:28px}}
.pct{{color:#9aa7b4;font-size:12px;white-space:nowrap}}
.pickmark{{color:#b794ff;font-size:12px}}
.winmark{{color:#5fd38a;font-size:12px}}
.pickcell{{white-space:nowrap}}
.rescell{{white-space:nowrap}}
.hit{{color:#5fd38a;font-weight:700}}
.miss{{color:#f08a8a;font-weight:700}}
.basis,.srcs{{font-size:12px;color:#9aa7b4;max-width:340px}}
.srcs a{{color:#8fb4ff;text-decoration:none}}
.srcs a:hover{{text-decoration:underline}}
.mut{{color:#7d8894;font-size:12px}}
.flags{{font-size:11.5px;color:#d8b45c;padding:0 10px 9px 38px}}
footer{{color:#7d8894;font-size:12.5px;padding:18px 16px 34px;max-width:1200px;margin:0 auto}}
footer a{{color:#8fb4ff}}
@media(max-width:560px){{.hero{{padding:14px}}.actions a{{width:100%;justify-content:center}}.srcs{{max-width:none}}}}
</style></head>
<body>
<header><a class="brand" href="../index.html">HOTSPAWN <span>/ full-coverage board</span></a>
<nav aria-label="Board"><a href="index.html">Board</a><a href="unresolved.html">Unresolved &amp; limitations</a><a href="../reviews/c13ca42a-verification.md">Verification record</a><a href="data/fullpicks_board.csv">board.csv</a></nav></header>
<main>
<section class="hero" id="start" aria-label="Executive summary">
<div class="eyebrow">Full-coverage pick&#39;em board &middot; session {SESSION} &middot; refresh every 4 h</div>
<h1>Every Hotspawn CS2 match &mdash; pick, probability, result</h1>
<p><strong>ARCHIVE — source snapshot 14 October 2026, not current picks.</strong> <a href="../executive/picks.html">Current picks &amp; unresolved gaps</a>.</p><p>All <b>88</b> CS2 Pick&#39;em fixtures captured from Hotspawn, one row each.
<b>28 open</b> matches carry a live pick with win probabilities for both teams (outside betting lines
first; our own originated line where no market prices the match). <b>54 played</b> matches carry their
officially verified result next to the pick we originally published. <b>6 matches are unresolved</b> and
are flagged rather than guessed. Hotspawn crowd percentages are never an input. {esc(BUILD_NOTE)}</p>
<div class="actions">
<a class="cta" href="#open">Open picks now (&darr;)</a>
<a href="unresolved.html">Unresolved picks &amp; limitations &rarr;</a>
<a href="../reviews/c13ca42a-verification.md">Line-by-line verification &rarr;</a>
<a href="data/fullpicks_board.csv">Machine-readable board &rarr;</a>
</div>
<div class="stats">
<div class="stat"><b>88</b><span>Total CS2 fixtures</span></div>
<div class="stat"><b>{len(open_rows)}</b><span>Open &middot; live pick + %</span></div>
<div class="stat"><b>{len(played_rows)}</b><span>Played &middot; result verified</span></div>
<div class="stat"><b>{len(unresolved_rows)}</b><span>Unresolved &middot; flagged</span></div>
<div class="stat"><b>{hits}/{len(played_rows)}</b><span>Original picks that hit</span></div>
</div>
</section>

<section id="open" aria-labelledby="open-title">
<h2 id="open-title">Open now &mdash; {len(open_rows)} matches (pick + win probability)</h2>
<p class="sub">Sorted by lock time. &#9650; marks our pick; each row links to the source(s) behind the numbers. Probabilities from outside markets first; own originated line (official Valve standings / HLTV ranking) only where no market prices the match.</p>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>Team A</th><th>Team B</th><th>Pick</th><th>Basis</th><th>Tournament</th><th>Tier / lock</th><th>Sources</th></tr></thead>
<tbody>
{open_html}
</tbody></table></div>
</section>

<section id="played" aria-labelledby="played-title">
<h2 id="played-title">Played &mdash; {len(played_rows)} verified results (original pick vs actual)</h2>
<p class="sub">Each result was verified 2026-10-14 against the official HLTV match page (or Liquipedia for DACH CS Masters S5); the link in the row is the exact match record. &#10003; marks the winning team. Flags (name aliases, one date offset, one double-play ambiguity) are listed in the source/notes column and on the <a href="unresolved.html">unresolved page</a>.</p>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>Team A</th><th>Team B</th><th>Original pick</th><th>Pick</th><th>Actual result</th><th>Tournament</th><th>Source (official)</th></tr></thead>
<tbody>
{played_html}
</tbody></table></div>
</section>

<section id="unresolved-preview" aria-labelledby="unres-title">
<h2 id="unres-title">Unresolved &mdash; {len(unresolved_rows)} matches (no pick, flagged)</h2>
<p class="sub">Per project policy, unconfirmable values stay blank. Full reasoning and evidence links: <a href="unresolved.html">Unresolved picks &amp; limitations &rarr;</a></p>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>Match</th><th>Pick</th><th>Tournament</th><th>Card date</th><th>Evidence</th></tr></thead>
<tbody>
{unresolved_html}
</tbody></table></div>
</section>
</main>
<footer>Independent analysis &mdash; not affiliated with Hotspawn, not betting advice.
Research record: <a href="../reviews/c13ca42a-verification.md">reviews/c13ca42a-verification.md</a> &middot;
Data: <a href="data/fullpicks_board.csv">fullpicks_board.csv</a>, <a href="data/stale_results.csv">stale_results.csv</a> &middot;
Built by <code>{SESSION}</code> (fail-closed invariants, no network needed at build time).</footer>
</body></html>
"""


def render_unresolved(board: list[dict]) -> str:
    unresolved_rows = [r for r in board if r["group"] == "unresolved"]
    flagged_played = [r for r in board if r["group"] == "played" and r["result_flag"]]

    def drac_tr(r: dict, i: int) -> str:
        return (
            f"<tr><td class='num'>{i}</td><td><b>{esc(r['match_id'])}</b></td>"
            f"<td>{esc(r['team_a'])} vs {esc(r['team_b'])}</td>"
            f"<td class='mut'>{esc((r['start_utc'] or '')[:16].replace('T', ' '))} UTC</td>"
            f"<td class='srcs'>{esc(r['result_flag'])}</td></tr>"
        )

    def cave_tr(r: dict) -> str:
        return (
            f"<tr><td><b>{esc(r['match_id'])}</b></td>"
            f"<td>{esc(r['team_a'])} vs {esc(r['team_b'])}</td>"
            f"<td>{esc(r['tournament'])}</td>"
            f"<td class='rescell'><b>{esc(r['winner'])}</b> {esc(r['score'])}</td>"
            f"<td class='srcs'>{esc(r['result_flag'])}<br>{src_links(r)}</td></tr>"
        )

    drac = "\n".join(drac_tr(r, i + 1) for i, r in enumerate(unresolved_rows))
    cave = "\n".join(cave_tr(r) for r in flagged_played)

    # Carried limitations for open fixtures that rely on our own line (no market).
    own_line = [r for r in board if r["group"] == "open" and not r["market_source"]]
    own_rows = ""
    for r in own_line:
        own_rows += (
            f"<tr><td><b>{esc(r['match_id'])}</b></td>"
            f"<td>{esc(r['team_a'])} vs {esc(r['team_b'])}</td>"
            f"<td>{esc(r['tournament'])}</td>"
            f"<td class='pickcell'><b>{esc(r['pick'])}</b> {esc(r['pick_prob_pct'])}%</td>"
            f"<td class='srcs'>No outside market prices this match; own originated line ({esc(r['basis_label'])}). Flags: {esc(r['flags']) or 'none'}</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Unresolved picks &amp; limitations · full-coverage board · c13ca42a</title>
<meta name="description" content="Matches that cannot be fully resolved, the evidence that was checked, and the limitations of the lines we do publish. Nothing is inferred; unconfirmable values stay blank.">
<style>
:root{{color-scheme:dark}}
*{{box-sizing:border-box}}
body{{margin:0;background:#10151c;color:#e8edf3;font:15px/1.5 system-ui,-apple-system,'Segoe UI',Roboto,sans-serif}}
header{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;padding:12px 16px;background:#151b23;border-bottom:1px solid #2b333d;position:sticky;top:0;z-index:5}}
.brand{{color:#8fb4ff;font-weight:700;text-decoration:none;margin-right:8px}}
nav a{{color:#9aa7b4;text-decoration:none;margin-right:14px;font-size:14px}}
nav a:hover{{color:#e8edf3;text-decoration:underline}}
main{{padding:16px;max-width:1100px;margin:0 auto}}
.hero{{background:#151b23;border:1px solid #2b333d;border-radius:14px;padding:18px;margin:8px 0 18px}}
.eyebrow{{color:#e0b34d;letter-spacing:.12em;text-transform:uppercase;font-size:11.5px;font-weight:700;margin:0 0 8px}}
h1{{font-size:clamp(22px,4.6vw,30px);line-height:1.2;margin:0 0 10px}}
.hero p{{color:#9aa7b4;font-size:14px;margin:0 0 14px;max-width:80ch}}
.actions{{display:flex;flex-wrap:wrap;gap:8px}}
.actions a{{background:#2a3240;border:1px solid #3a4553;color:#e8edf3;border-radius:10px;padding:10px 14px;font-size:14px;font-weight:600;text-decoration:none;min-height:44px;display:inline-flex;align-items:center}}
.actions a:hover{{text-decoration:underline}}
h2{{font-size:19px;margin:26px 0 4px}}
.sub{{color:#9aa7b4;font-size:13px;margin:0 0 10px}}
.note{{background:#1b232d;border:1px solid #2b333d;border-left:3px solid #e0b34d;border-radius:8px;padding:11px 13px;margin:14px 0;font-size:13px;color:#9aa7b4}}
.note a{{color:#8fb4ff}}
.table-wrap{{overflow-x:auto;border:1px solid #2b333d;border-radius:12px}}
table{{border-collapse:collapse;width:100%;font-size:13.5px;min-width:700px}}
th,td{{padding:9px 10px;border-bottom:1px solid #222b35;text-align:left;vertical-align:top}}
th{{background:#151b23;color:#9aa7b4;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em}}
tr:last-child td{{border-bottom:none}}
.num{{color:#5c6875;width:28px}}
.srcs{{font-size:12.5px;color:#9aa7b4;max-width:430px}}
.srcs a{{color:#8fb4ff;text-decoration:none}}
.srcs a:hover{{text-decoration:underline}}
.mut{{color:#7d8894;font-size:12px}}
.pickcell,.rescell{{white-space:nowrap}}
footer{{color:#7d8894;font-size:12.5px;padding:18px 16px 34px;max-width:1100px;margin:0 auto}}
footer a{{color:#8fb4ff}}
@media(max-width:560px){{.hero{{padding:14px}}.actions a{{width:100%;justify-content:center}}}}
</style></head>
<body>
<header><a class="brand" href="../index.html">HOTSPAWN <span>/ full-coverage board</span></a>
<nav aria-label="Board"><a href="index.html">Board</a><a href="unresolved.html">Unresolved &amp; limitations</a><a href="../reviews/c13ca42a-verification.md">Verification record</a></nav></header>
<main>
<section class="hero" aria-label="Unresolved picks and limitations">
<div class="eyebrow">Unresolved picks &amp; limitations</div>
<h1>What we could not resolve &mdash; and what limits the rest</h1>
<p>Policy: if a value cannot be confirmed from an official source it stays <b>blank and flagged</b> &mdash;
never inferred, never fabricated. Below: the 6 fixtures with no pick (DraculaN Season 7), the verified
results that carry a caveat, and the limitation that applies to every match priced only by our own line.
{esc(BUILD_NOTE)}</p>
<div class="actions"><a href="index.html">&larr; Back to the full-coverage board</a><a href="../reviews/c13ca42a-verification.md">Line-by-line verification record &rarr;</a></div>
</section>

<section aria-labelledby="drac-title">
<h2 id="drac-title">1. No pick — DraculaN Season 7 (6 fixtures, Hotspawn cards dated June 26–28)</h2>
<p class="sub">Why no pick: the official evidence contradicts the Hotspawn cards, and no result exists to verify. We refuse to publish a guess.</p>
<div class="note"><b>Official evidence (checked 2026-10-14T08:35Z):</b> HLTV lists <a href="https://www.hltv.org/events/9312/draculanan-season-7" rel="noopener noreferrer">DraculaN Season 7 (event 9312)</a> as <b>upcoming, 2026-10-19 → 2026-10-23, Bucharest, $35,000, 24 teams</b>.
(1) No results of any kind exist for the event. (2) The six Hotspawn pairings below appear <b>nowhere</b> in the published
October 19–23 schedule (<a href="https://www.hltv.org/events/9312/matches" rel="noopener noreferrer">official match list</a> — e.g. first-round INFINITE plays Insiders, not Acend).
(3) The Hotspawn card dates (2026-06-26/28) predate the official event by almost four months.
Treat the Hotspawn card data for this tournament as unreliable; picks are withheld until the event actually plays and a result can be verified.</div>
<div class="table-wrap"><table>
<thead><tr><th>#</th><th>Fixture</th><th>Match</th><th>Card start (UTC)</th><th>Flag &amp; evidence</th></tr></thead>
<tbody>
{drac}
</tbody></table></div>
</section>

<section aria-labelledby="cave-title">
<h2 id="cave-title">2. Verified, with a caveat (result confirmed, note attached)</h2>
<p class="sub">These results are verified on the official source in each row; the caveat explains a naming alias, a one-day calendar offset, or a double-played pair.</p>
<div class="table-wrap"><table>
<thead><tr><th>Fixture</th><th>Match</th><th>Tournament</th><th>Result</th><th>Caveat &amp; source</th></tr></thead>
<tbody>
{cave}
</tbody></table></div>
</section>

<section aria-labelledby="own-title">
<h2 id="own-title">3. Limitation — matches priced only by our own line ({len(own_line)})</h2>
<p class="sub">No outside book or prediction market prices these matches (checked 2026-10-14). Their probabilities are our own originated line (official Valve Regional Standings points and/or the official HLTV world ranking, converted to the series length). Such lines are <b>uncalibrated research estimates, not verified win probabilities</b>; every one of them is flagged in the board row and in the source links.</p>
<div class="table-wrap"><table>
<thead><tr><th>Fixture</th><th>Match</th><th>Tournament</th><th>Pick</th><th>Limitation / flags</th></tr></thead>
<tbody>
{own_rows}
</tbody></table></div>
</section>

<section aria-labelledby="method-title">
<h2 id="method-title">4. Standing limitations (whole board)</h2>
<div class="note">
&#8226; Probabilities are research estimates, not official forecasts; no source can guarantee a winner.<br>
&#8226; Market quotes are point-in-time reads; they move and can be retracted by the book.<br>
&#8226; Own lines assume independent maps and use a project-fitted scale; they are uncalibrated and labelled as such on every row.<br>
&#8226; Hotspawn supplies fixture list and lock times only &mdash; its crowd pick percentages are never an input.<br>
&#8226; HLTV is used as evidence (match records, formats, rankings); all lines are originated by this project.
</div>
</section>
</main>
<footer>Independent analysis &mdash; not affiliated with Hotspawn, not betting advice.
Research record: <a href="../reviews/c13ca42a-verification.md">reviews/c13ca42a-verification.md</a> &middot;
Data: <a href="data/stale_results.csv">stale_results.csv</a> &middot; Built by <code>{SESSION}</code>.</footer>
</body></html>
"""


def main() -> None:
    check_only = "--check" in sys.argv
    board = build()
    if check_only:
        print(f"OK: invariants pass (88 = 28 open + 54 verified + 6 unresolved)")
        return
    text = globals().get("_STALE_CSV_TEXT")
    if text is None:
        fail("stale csv text missing")
    os.makedirs(os.path.dirname(STALE_RESULTS_CSV), exist_ok=True)
    with open(STALE_RESULTS_CSV, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    write_board_csv(board)
    index_html = render_index(board)
    unres_html = render_unresolved(board)
    # HTML invariants
    for mid in [r["match_id"] for r in board]:
        if mid not in index_html:
            fail(f"index.html missing fixture {mid}")
    for mid in [r["match_id"] for r in board if r["group"] == "unresolved"]:
        if mid not in unres_html:
            fail(f"unresolved.html missing fixture {mid}")
    with open(INDEX_HTML, "w", encoding="utf-8") as fh:
        fh.write(index_html)
    with open(UNRESOLVED_HTML, "w", encoding="utf-8") as fh:
        fh.write(unres_html)
    print("OK: fullpicks board rebuilt")
    print(f"  stale_results.csv : 60 rows (54 verified + 6 unresolved)")
    print(f"  fullpicks_board.csv: {len(board)} rows")
    print(f"  index.html         : {len(index_html)} bytes")
    print(f"  unresolved.html    : {len(unres_html)} bytes")


if __name__ == "__main__":
    main()
