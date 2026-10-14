#!/usr/bin/env python3
"""Render reconcile/index.html, reconcile/flagged.html and reviews/28d318cd-verification.md.
Imports the recomputation from build.py so every number shown is the recomputed one."""
import csv, datetime as dt, html, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build as B

ROOT = B.ROOT; R = B.R
SITE = "https://buffedlizard55-lab.github.io/MaltaProj1"
NOW = "2026-10-14T05:00Z"

FLAGS = [
 # id, severity, fixture(s), title, evidence, action
 ("F-01", "HIGH", "1079622", "ex-RUSTEC vs mellren: board value does not reproduce",
  "Board: ex-RUSTEC 65.7 / 34.3 (EGamersWorld, read 02:48Z). Live EGamersWorld read 04:39Z: 1.80 / 1.80 (= 50.0 / 50.0). The picks-full board already treats 1.80/1.80 as a placeholder. Pick: ex-RUSTEC.",
  "Re-read the price before lock (10:54Z). Until then the 65.7 value is not confirmed."),
 ("F-02", "HIGH", "1081112", "Banda chuya vs 6666: duplicate team names in the Valve table; the probability depends on which roster",
  "VRS 2026-10-05 has two rows named 'Banda Chuya' (rank 165 / 801 pts, AdrieN-ezox-maaryy-Showk-tomiko; rank 373 / 402 pts, ezox-manio) and two rows named '6666' (rank 127 / 923 pts; rank 368 / 425 pts). The board's 38.2 / 61.8 reproduces only with rank 165 and rank 127. Other combinations: 6666 (923) vs Banda rank 373 -> 6666 89.4%; 6666 rank 368 (425) vs Banda rank 165 -> Banda 81.9% (pick flips); 6666 rank 368 vs Banda rank 373 -> 6666 52.3%. Hotspawn's roster for either team is not shown on the page.",
  "Confirm both rosters against the Hotspawn/HLTV match page before publishing a probability. Pick stays '6666' only if the 923-point 6666 and 801-point Banda are the teams playing."),
 ("F-03", "MED", "1081113", "Ryvex vs PCIFIC: two EGamersWorld listings for the same slot",
  "EGamersWorld lists 'PCIFIC Espor vs Ryvex' and 'WRAITH PCIFIC vs Ryvex' at 14.10 16:00 (= 14:00Z). The Polymarket market is 'cs2-wraith-ryvex-2026-10-14'. Board R-228-04 records the identity as confirmed; this read does not show the confirmation. Board pick: PCIFIC 80.5% (Polymarket). Not re-read today.",
  "Re-check the identity on the HLTV page before lock. The 'WRAITH' and 'PCIFIC' names both appear, so this is an open question for the reader."),
 ("F-04", "MED", "1079623", "G2 Ares vs The Last Resort: small mismatch with the live read",
  "Board 62.4 / 37.6 (EGamersWorld, 02:48Z). Live 04:39Z: 1.43 / 2.41 -> 62.76 / 37.24 (difference -0.36 pp). The 0.4 pp gap is larger than the rounding of the decimal odds, so the price likely moved.",
  "Update the board value from a fresh read. The pick (G2 Ares) is unchanged."),
 ("F-05", "MED", "1079621", "Bookmaker attribution and price dispersion on the Gothic vs Lavked row",
  "Board attributes the 2.05 / 1.64 price to bc.game via EGamersWorld. The bookmaker list I read (chunks 0-2) shows 2.05 / 1.64 at SpinAlto, RedSport, PlanBet and Kinbet, not bc.game. Spinbetter, 22bet and 1xBit show 1.881 / 1.782 = 48.7 / 51.3, a 4.2 pp spread from the board's 44.4 / 55.6. The percentages match the board; the attribution is not confirmed.",
  "Correct the source label to the bookmaker that actually posts the price, or record the spread."),
 ("F-06", "MED", "1079439", "HOTU vs Fnatic: pick margin under 1 pp",
  "Pinnacle capture 2026-10-14T02:45Z: HOTU -110 / Fnatic -114 -> 49.6 / 50.4. Reproduces on recompute. The pick is a near coin flip.",
  "Show as a near-even pick (no confidence tier)."),
 ("F-07", "HIGH", "1081111, 1081112, 1081113, 1081120", "Four Play-In rows have no Hotspawn match link visible on the rendered page",
  "The /lobby and /cs2-pickems renders show the 28 fixtures (names, times, tournament, tier) but no 'View match' link or fixture ID for these four rows. The board's IDs (1081111, 1081112, 1081113, 1081120) come from the board's own payload capture and cannot be confirmed from the page.",
  "Check the IDs against a Hotspawn match URL before using them as identity. Treat the rows as identity-unconfirmed until then."),
 ("F-08", "HIGH", "all", "Site front door shows no picks",
  "The root landing page (index.html, owned by arena/198cf31e, task B-04) is served from a stale snapshot dated 2026-10-13T19:42:13Z, so picks show as blank. The consolidated board at console/index.html shows 28 of 28 picks as of 04:23Z.",
  "Owner of B-04 to refresh the landing snapshot. This session did not edit index.html (scope)."),
 ("F-09", "MED", "all", "Hotspawn pages render at different times",
  "/cs2-pickems countdowns anchor to a render near 02:50:21Z; /lobby countdowns anchor to 04:37:25Z. Both list the same 28 fixtures. The 1h47m gap is not shown to readers. Lock times use the /lobby anchor.",
  "Treat /cs2-pickems as a stale source for timing. Use /lobby."),
 ("F-10", "MED", "all", "'68 matches this week' on /cs2-pickems vs 28 listed",
  "The /cs2-pickems header says '68 matches this week'. Only 28 fixtures are listed as open ('Closing Soon' 13, 'Upcoming' 15). The 40-match gap is not explained on the page.",
  "Scope every coverage claim to '28 open fixtures visible on the public page at read time'."),
 ("F-11", "MED", "1079624", "Research pick FORZE Reload vs LFO 10 has no official line",
  "LFO 10 is absent from the Valve 2026-10-05 table (LFO 7, 8 and 9 are present, at ranks 279, 285 and 297). The board's 75.9 (range 75.9-98.4) is a research estimate that cannot be recomputed from an official source. FORZE Reload is 1100 pts (rank 84).",
  "Leave the probability blank under the 'never infer' rule, or keep it labelled RESEARCH and unverified. This is a policy decision for the owner."),
 ("F-12", "MED", "13 rows", "Most prices come through aggregators, not the bookmaker's own feed",
  "Pinnacle (own guest API) covers 7 rows. Thunderpick is read through bo3.gg relays for 13 rows (1079438, 1080279-1080290 excluding 1080279 read directly on Thunderpick). EGamersWorld relays 4 rows. Polymarket covers 1 row. Relays are not official bookmaker sites.",
  "Keep the source link on every row. Label the source type (bookmaker API / aggregator / prediction market / own line) on the page."),
 ("F-13", "LOW", "13 rows", "Rows not re-read in this session",
  "13 rows were not re-read today (see reconcile/reread.csv, result 'not re-read'). Their values are the board's, unchanged, and are not confirmed by this session.",
  "Re-read in the next refresh."),
 ("F-14", "HIGH", "14 rows (8 by ≥1 pp)", "Two boards on main disagree on win probabilities",
  "console/data/picks.csv and executive/data/analysis.csv (both on main) give the same pick on 28/28 fixtures but different win probabilities on 14 rows, 8 of them by at least 1 pp: 1079624 +22.5 (research), 1081120 +8.1 (own line), 1081112 -5.1 (own line), 1080179 -2.9, 1079439 -2.1, 1080176 -1.8, 1079442 -1.8, 1080177 +1.3. Per-row values are in reconcile/cross_board.csv. The console values reproduce from the committed Pinnacle capture (02:45Z); the executive values come from a different snapshot or method, not reconciled here.",
  "Owners of both boards to agree on one value per row and state the snapshot time. Until then both values are shown with the source for each."),
 ("F-15", "MED", "1081112, 1081120", "Two different own-line methods on main",
  "Console: Valve points with the repo's k = 0.4568 and the BO3 transform (reproduces 38.2 / 61.8 and 78.5 / 21.5). Executive: rank-based 1/(1+10^((rank_b−rank_a)/212)) with a fitted scale (33.1 / 66.9 and 86.6 / 13.4). The picks agree (6666 and mellren) but the probabilities do not.",
  "Pick one own-line method for all open rows and document it. Not decided here."),
]

def sev_class(s):
    return {"HIGH": "hi", "MED": "md", "LOW": "lo"}.get(s, "lo")

def load():
    rows = list(csv.DictReader((R / "reread.csv").open(encoding="utf-8")))
    recon = list(csv.DictReader((R / "reconciliation.csv").open(encoding="utf-8")))
    return rows, recon

CSS = """
*{box-sizing:border-box}body{margin:0;font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#111;background:#f6f7f9}
header,main{max-width:760px;margin:0 auto;padding:14px}
h1{font-size:1.35rem;margin:.2rem 0}h2{font-size:1.1rem;margin:1.4rem 0 .5rem}
nav a{display:inline-block;margin:4px 8px 4px 0;padding:6px 10px;background:#fff;border:1px solid #d5d9e0;border-radius:8px;color:#0b4da2;text-decoration:none;font-size:.9rem}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.kpi{background:#fff;border:1px solid #d5d9e0;border-radius:10px;padding:10px}
.kpi b{display:block;font-size:1.3rem}
.card{background:#fff;border:1px solid #d5d9e0;border-radius:12px;padding:12px;margin:10px 0}
.card h3{font-size:1rem;margin:0 0 4px}
.meta{color:#4a5260;font-size:.85rem}
.pick{display:flex;justify-content:space-between;gap:8px;margin:8px 0;font-weight:600}
.bar{height:10px;border-radius:5px;background:#e3e7ee;overflow:hidden;display:flex}
.bar span{display:block;height:100%}
.pcts{display:flex;justify-content:space-between;font-size:.9rem;margin-top:4px}
.tag{display:inline-block;font-size:.75rem;padding:2px 7px;border-radius:999px;background:#eef1f6;margin-right:4px}
.ok{background:#e4f5e9;color:#17642d}.warn{background:#fff3d6;color:#7a5200}.bad{background:#fde3e1;color:#9a1c12}.gray{background:#eceef2;color:#444}
.hi{background:#fde3e1;color:#9a1c12}.md{background:#fff3d6;color:#7a5200}.lo{background:#eceef2;color:#444}
ul.links{padding-left:18px;margin:6px 0;font-size:.9rem}
.note{font-size:.88rem;color:#333;background:#fffbea;border:1px solid #f0e2a6;border-radius:8px;padding:8px;margin:8px 0}
table{width:100%;border-collapse:collapse;font-size:.85rem;background:#fff}td,th{border:1px solid #d5d9e0;padding:6px;vertical-align:top;text-align:left}
.wrap{overflow-x:auto}
footer{font-size:.8rem;color:#555;padding:20px 14px;max-width:760px;margin:auto}
"""

def esc(s): return html.escape(s or "")

def bar(a, b, label_a, label_b):
    return (f'<div class="bar" role="img" aria-label="{esc(label_a)} {a:.1f} percent, {esc(label_b)} {b:.1f} percent">'
            f'<span style="width:{a:.1f}%;background:#2b6cb0"></span><span style="width:{b:.1f}%;background:#c9d3e3"></span></div>')

def fmt_utc_et(s):
    d = dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    et = d - dt.timedelta(hours=4)
    return f'{d:%a %d %b %H:%MZ} · {et:%H:%M} ET'

def result_tag(r):
    m = {"reproduced": ("ok", "reproduced"), "reproduced — identity open": ("warn", "reproduced · identity open"),
         "differs": ("bad", "differs from live"), "placeholder — not reproducible": ("bad", "placeholder · not reproducible"),
         "unverifiable": ("bad", "unverifiable"), "not re-read": ("gray", "not re-read")}
    cls, txt = m.get(r["result"], ("gray", r["result"]))
    return f'<span class="tag {cls}">{esc(txt)}</span>'

def page_head(title, desc):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><meta name="description" content="{esc(desc)}">'
            f'<style>{CSS}</style></head><body>')

NAV = ('<nav><a href="../index.html">Site home</a><a href="../console/index.html">All picks (board)</a>'
       '<a href="../console/flagged.html">Board flags</a><a href="index.html">Live reconciliation</a>'
       '<a href="flagged.html">Flagged for Review</a><a href="../console/methodology.html">Method</a></nav>')

def render_index(rows, recon, board):
    by = {r["fixture_id"]: r for r in rows}
    rec = {r["fixture_id"]: r for r in recon} if recon and "fixture_id" in recon[0] else {}
    total = len(board)
    stats = {}
    for r in rows: stats[r["result"]] = stats.get(r["result"], 0) + 1
    unresolved = [b for b in board if b["fixture_id"] in ("1081112", "1081120", "1079624")]
    out = [page_head("Live Hotspawn reconciliation — CS2 picks", "Row-by-row reconciliation of the open Hotspawn CS2 fixtures to the picks board, with re-checks and flags.")]
    out.append(f'<header><h1>Live reconciliation: {total} open CS2 fixtures</h1>'
               f'<div class="meta">Read {esc(NOW)} · Hotspawn /lobby (ET, countdown-anchored) and /cs2-pickems (UTC; stale, see F-09). '
               f'Hotspawn crowd percentages are not read and are not an input.</div>{NAV}</header><main>')
    out.append('<h2>Summary</h2><div class="kpis">'
               f'<div class="kpi"><b>{total}</b>open fixtures on Hotspawn</div>'
               f'<div class="kpi"><b>{total}/{total}</b>one-to-one with the board, 0 extra rows</div>'
               f'<div class="kpi"><b>{sum(1 for b in board if b["pick"])}/{total}</b>have a pick</div>'
               f'<div class="kpi"><b>{stats.get("reproduced",0)+stats.get("reproduced — identity open",0)}</b>re-checks reproduce the board</div>'
               f'<div class="kpi"><b>{stats.get("differs",0)+stats.get("placeholder — not reproducible",0)}</b>differ or not reproducible</div>'
               f'<div class="kpi"><b>{stats.get("not re-read",0)}</b>not re-read this session</div>'
               '</div>')
    out.append('<h2>Unresolved picks and limitations</h2>'
               '<div class="note">Three fixtures have no bookmaker or prediction-market price in any source read. Their picks come from our own Valve-points model or from an unverified research line. They are shown but not confirmed.</div>')
    for b in unresolved:
        r = by[b["fixture_id"]]
        out.append(f'<div class="card"><h3>{esc(b["team_a"])} vs {esc(b["team_b"])}</h3>'
                   f'<div class="meta">{esc(b["competition"])} · {fmt_utc_et(b["start_utc"])}</div>'
                   f'<div class="pick"><span>Pick: {esc(b["pick"])}</span></div>'
                   f'<div class="meta">Board: {esc(b["team_a"])} {esc(b["p_a_pct"])}% / {esc(b["team_b"])} {esc(b["p_b_pct"])}%</div>'
                   f'<div>{result_tag(r)}</div><div class="meta">{esc(r["note"])}</div>'
                   f'<ul class="links"><li><a href="{esc(r["check_source"])}">Check source</a></li>'
                   f'<li><a href="{B.HOTSPAWN_CS2}">Hotspawn /cs2-pickems</a></li></ul></div>')
    out.append('<h2>All 28 fixtures</h2>'
               '<div class="meta">Each card: board pick, both win probabilities (bar and text), recheck result, and official or source links. Blank or unverified values are flagged; see Flagged for Review.</div>')
    for b in board:
        r = by[b["fixture_id"]]
        a, bb = float(b["p_a_pct"]), float(b["p_b_pct"])
        out.append(f'<div class="card"><h3>{esc(b["team_a"])} vs {esc(b["team_b"])}</h3>'
                   f'<div class="meta">{esc(b["competition"])} · {fmt_utc_et(b["start_utc"])} · #{esc(b["fixture_id"])}</div>'
                   f'<div class="pick"><span>Pick: {esc(b["pick"])}</span></div>'
                   f'{bar(a, bb, b["team_a"], b["team_b"])}'
                   f'<div class="pcts"><span>{esc(b["team_a"])} {a:.1f}%</span><span>{esc(b["team_b"])} {bb:.1f}%</span></div>'
                   f'<div>{result_tag(r)}</div>'
                   f'<div class="meta">{esc(r["note"])}</div>'
                   f'<div class="meta">Basis: {esc(b["basis_label"])} · confidence: {esc(b["confidence"])}</div>'
                   f'<ul class="links"><li><a href="{esc(b["source_url"])}">Board source (row)</a></li>'
                   f'<li><a href="{esc(r["check_source"])}">Re-check source</a></li>'
                   + (f'<li><a href="{esc(b["hotspawn_match_url"])}">Hotspawn match</a></li>' if b.get("hotspawn_match_url") else '<li class="meta">Hotspawn match link not visible on the page (F-07)</li>')
                   + (f'<li><a href="{esc(b["hltv_match_url"])}">HLTV match</a></li>' if b.get("hltv_match_url") else '')
                   + '</ul></div>')
    out.append('<h2>Method</h2><div class="meta">'
               'Hotspawn: fixture identity, time and tier only. Percentages are not used. '
               'Own lines: P_map = 1/(1+10^(−0.4568·ΔVRS/400)), best-of-three p²(3−2p) (repo calibration, scripts/63ee81ba_build.py). '
               'Market rows: de-vig of the decimal or American odds shown. Values are recomputed by reconcile/build.py from the stored inputs.</div>'
               '<h2>Files</h2><ul class="links">'
               '<li><a href="reread.csv">reread.csv</a> — per-row recheck, 28 rows</li>'
               '<li><a href="reconciliation.csv">reconciliation.csv</a> — Hotspawn ↔ board join</li>'
               '<li><a href="flagged.html">Flagged for Review</a></li>'
               '<li><a href="../reviews/28d318cd-verification.md">Verification record (markdown)</a></li></ul>'
               '</main><footer>Session arena/28d318cd · checked 2026-10-14. Not investment advice.</footer></body></html>')
    return "".join(out)

def render_flagged():
    out = [page_head("Flagged for Review — CS2 picks", "Irregularities found in the live Hotspawn reconciliation. They do not block publication.")]
    out.append(f'<header><h1>Flagged for Review</h1><div class="meta">Read {esc(NOW)}. Flags do not block the merge; each has a stated action.</div>{NAV}</header><main>')
    for fid, sev, fx, title, ev, act in FLAGS:
        out.append(f'<div class="card"><div><span class="tag {sev_class(sev)}">{sev}</span><span class="tag gray">{esc(fid)}</span></div>'
                   f'<h3>{esc(title)}</h3><div class="meta">Fixture(s): {esc(fx)}</div>'
                   f'<p style="font-size:.92rem">{esc(ev)}</p><div class="note"><b>Action:</b> {esc(act)}</div></div>')
    out.append('<h2>Corrections made during this check</h2><div class="meta">'
               'My first pass suspected WBT and WROTBERRY had no documented alias. cs2/aliases.json documents WROTBERRY → WBT (HLTV 2399418), so this is not flagged. '
               'Likewise RoundsGG → ROUNDS is documented, so Phantom vs RoundsGG is not flagged.</div>'
               '</main><footer>Session arena/28d318cd · checked 2026-10-14.</footer></body></html>')
    return "".join(out)

def render_md(rows, board):
    L = []
    L.append("# Verification record — arena/28d318cd (live Hotspawn reconciliation)\n")
    L.append(f"Checked: {NOW}. Scope S-01..S-05 (COORDINATION.md). Files: `reconcile/**`, this file.\n")
    L.append("## What was checked\n")
    L.append("- Hotspawn `/lobby` (ET, countdown-anchored at 04:37:25Z) and `/cs2-pickems` (UTC, stale at ~02:50Z; F-09). Both list the same 28 open fixtures (F-10 for the 68-match header).")
    L.append("- Reconciliation to `console/data/picks.csv` (origin/main): 28/28 one-to-one, 28/28 with a pick, 0 extra rows (`reconcile/summary.json`).")
    L.append("- Line-by-line re-check of each row (`reconcile/reread.csv`, produced by `reconcile/build.py`).\n")
    stats = {}
    for r in rows: stats[r["result"]] = stats.get(r["result"], 0) + 1
    L.append("## Result counts\n")
    for k, v in stats.items(): L.append(f"- {k}: {v}")
    L.append("")
    L.append("## Unresolved picks (no bookmaker or prediction-market price)\n")
    L.append("- 1081112 Banda chuya vs 6666 — own line, roster identity open (F-02).")
    L.append("- 1081120 mellren vs Privateer — own line, reproduces 78.5 / 21.5 (unique names).")
    L.append("- 1079624 FORZE Reload vs LFO 10 — research only, unverifiable (F-11).\n")
    L.append("## Row table\n")
    L.append("| Fixture | Match | Board pick | Board % (A / B) | Recheck | Recomputed (A / B) | Result | Source |")
    L.append("|---|---|---|---|---|---|---|---|")
    for r in rows:
        rec = f"{r['recomputed_pct_a']} / {r['recomputed_pct_b']}" if r["recomputed_pct_a"] else "—"
        L.append(f"| {r['fixture_id']} | {r['match']} | {r['board_pick']} | {r['board_pct_a']} / {r['board_pct_b']} | {r['check_method']} | {rec} | {r['result']} | [{r['check_source'].split('/')[2]}]({r['check_source']}) |")
    L.append("")
    L.append("## Flags (full text in reconcile/flagged.html)\n")
    for fid, sev, fx, title, ev, act in FLAGS:
        L.append(f"- **{fid} [{sev}] {title}** ({fx}). {ev} *Action:* {act}")
    L.append("")
    L.append("## Sources\n")
    L.append(f"- Hotspawn: {B.HOTSPAWN_LOBBY} · {B.HOTSPAWN_CS2}")
    L.append(f"- Valve VRS 2026-10-05 (repo copy `cs2/data/raw/vrs_standings_global_2026_10_05.json.gz`): {B.VRS_URL}")
    L.append(f"- Pinnacle guest API (committed capture): {B.PINNACLE_URL}")
    for k, (u, what, t) in B.LIVE_READS.items():
        L.append(f"- {k} ({t}): {u} — {what}")
    L.append("")
    return "\n".join(L)

def main():
    rows, board = B.main()
    recon = list(csv.DictReader((R / "reconciliation.csv").open(encoding="utf-8")))
    (R / "index.html").write_text(render_index(rows, recon, board), encoding="utf-8")
    (R / "flagged.html").write_text(render_flagged(), encoding="utf-8")
    (ROOT / "reviews").mkdir(exist_ok=True)
    (ROOT / "reviews" / "28d318cd-verification.md").write_text(render_md(rows, board), encoding="utf-8")
    print("wrote reconcile/index.html, reconcile/flagged.html, reviews/28d318cd-verification.md")

if __name__ == "__main__":
    main()
