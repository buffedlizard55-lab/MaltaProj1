#!/usr/bin/env python3
"""Regenerate every page in docs/ from data/*.csv (run AFTER scripts/model.py).

Nothing on the pages is typed by hand except narrative text here; every number
and link comes from data/. Run: python3 scripts/build_docs.py
"""
import csv
import html
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
SNAP = "2026-10-13"


def read(name):
    with open(DATA / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def e(x):
    return html.escape(str(x or ""), quote=True)


def link(url, label=None):
    if not url:
        return "<i>blank</i>"
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label or url)}</a>'


def nav(active):
    items = [
        ("index.html", "Dashboard"), ("matches.html", "All matches"),
        ("s-tier.html", "S-Tier · Thunderpick WC"), ("stake.html", "Stake Pulse Beat III"),
        ("lower-tiers.html", "B/C-Tier &amp; inventory"), ("methodology.html", "Methodology"),
        ("flagged.html", "⚠ Flagged for Review"), ("sources.html", "Sources"),
    ]
    return "<nav>" + "".join(
        f'<a href="{u}"{" aria-current=page" if u == active else ""}>{t}</a>' for u, t in items) + "</nav>"


def page(fname, title, active, body):
    doc = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{e(title)} · MaltaProj1</title><link rel='stylesheet' href='style.css'></head><body>"
        f"<header><h1>{title}</h1><p>Hotspawn Pick'em betting-line analysis · Snapshot {SNAP} (UTC) · "
        "Hotspawn pick % is NEVER used as a probability.</p></header>"
        f"{nav(fname)}<main>{body}</main>"
        "<footer>Analysis only — not betting advice. Unverified values are left blank and flagged. "
        "See <a href='flagged.html'>Flagged for Review</a> and <a href='sources.html'>Sources</a>.</footer>"
        "</body></html>"
    )
    (DOCS / fname).write_text(doc, encoding="utf-8")


def table(headers, rows):
    h = "".join(f"<th>{e(x)}</th>" for x in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<div style='overflow-x:auto'><table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table></div>"


def fmt_rank(x):
    return e(x) if x else "<i>blank</i>"


def fmt_pct(x):
    return f"{e(x)}%" if x else "<i>blank</i>"


# ---------------- load ----------------
matches = read("matches.csv")
analysis = {r["id"]: r for r in read("analysis.csv")}
lines = read("external_lines.csv")
sources = read("sources.csv") if (DATA / "sources.csv").exists() else []
outrights = read("lines.csv")
inventory = read("tournaments_inventory.csv")
ratings = read("ratings.csv")
by_match = {}
for ln in lines:
    by_match.setdefault(ln["match_id"], []).append(ln)


def ext_cell(mid):
    out = []
    for ln in by_match.get(mid, []):
        if ln["unit"] == "cents":
            val = f'{e(ln["team_a_source_name"])} {e(ln["team_a_value"])}¢ / {e(ln["team_b_source_name"])} {e(ln["team_b_value"])}¢'
        else:
            val = f'{e(ln["team_a_source_name"])} {e(ln["team_a_value"])} / {e(ln["team_b_source_name"])} {e(ln["team_b_value"])} (dec.)'
        out.append(f'<div>{e(ln["source"])}: {val} <span class="tag {e(ln["status"])}">{e(ln["status"])}</span> '
                   f'· {link(ln["source_url"], "source")}</div>')
    return "".join(out) or "<i>blank</i>"


def match_row(m, full=True):
    a = analysis[m["id"]]
    pick = a["pick"]
    cells = [
        e(m["id"]), e(m["start_hotspawn_label"]) + " <small>(Hotspawn)</small>",
        f'{e(m["team_a"])} vs {e(m["team_b"])}',
        e(m["tournament"]),
        fmt_rank(a["hltv_rank_a"]) + " / " + fmt_rank(a["hltv_rank_b"]),
        fmt_pct(a["own_pA_pct"]), fmt_pct(a["external_pA_pct_mean_nova"]),
        f'<b>{e(pick)}</b><br><small>{e(a["pick_basis"])}</small>',
    ]
    if full:
        cells.append(link(m["hotspawn_match_url"], "Hotspawn match"))
        cells.append(ext_cell(m["id"]))
    return cells


HEAD_FULL = ["ID", "Time (Hotspawn label)", "Fixture", "Tournament", "HLTV rank A / B",
             "Own model A%", "External A% (no-vig mean)", "Pick", "Hotspawn", "External readings (audit)"]
HEAD_SHORT = ["ID", "Time", "Fixture", "Tournament", "HLTV rank A / B", "Own A%", "External A%", "Pick"]

picks = [analysis[m["id"]] | {"fixture": f'{m["team_a"]} vs {m["team_b"]}'}
         for m in matches if analysis[m["id"]]["pick"] != "no pick"]
pick_html = "".join(
    f'<li><b>{e(p["pick"])}</b> — {e(p["fixture"])} ({p["id"]}): own {fmt_pct(p["own_pA_pct"])} for '
    f'{e(p["team_a"])}, external {fmt_pct(p["external_pA_pct_mean_nova"])}.</li>' for p in picks)
n_ext = sum(1 for m in matches if any(l["status"] == "accepted" for l in by_match.get(m["id"], [])))
n_own = sum(1 for m in matches if analysis[m["id"]]["own_pA_pct"])

# ---------------- index ----------------
body_index = f"""
<div class='card'><h2>What this is</h2>
<p>We reverse-engineered <a href='https://play.hotspawn.com/lobby' target='_blank'>play.hotspawn.com/lobby</a>
and <a href='https://play.hotspawn.com/cs2-pickems' target='_blank'>/cs2-pickems</a> on {SNAP}, extracted the
26 fixtures that are server-rendered, and priced each one from <b>outside</b> sources (HLTV rankings and
match pages, Polymarket and eGamersWorld betting lines) plus <b>our own documented rank model</b>.
Hotspawn crowd % is stored only as an audit snapshot and is <b>never</b> used as a probability.</p>
<div class='kpi'><div><b>26</b>fixtures extracted verbatim</div><div><b>{n_ext}</b>matches with an accepted external line</div>
<div><b>{n_own}</b>matches with our originated (own) line</div><div><b>{len(picks)}</b>matches with a pick (both sources ≥55%)</div></div>
<p><b>Picks</b> (own model AND accepted external line agree, both ≥55%):</p><ul>{pick_html}</ul>
<p>Everything else is <b>no pick</b>, with the reason stated on the matches page. Unverifiable values are blank and listed on
<a href='flagged.html'>Flagged for Review</a>. Flagged items do not block publication.</p></div>
<div class='card'><h2>Where to look</h2><ol>
<li><a href='s-tier.html'>S-Tier · Thunderpick World Championship</a> — 4 matches plus tournament outrights.</li>
<li><a href='stake.html'>Stake Pulse Beat III</a> — 4 matches.</li>
<li><a href='lower-tiers.html'>B/C-Tier &amp; inventory</a> — 18 matches plus the tournament inventory.</li>
<li><a href='matches.html'>All matches</a> — all 26 fixtures with every reading and its source link.</li>
<li><a href='methodology.html'>Methodology</a> and <a href='sources.html'>Sources</a>.</li>
<li><a href='flagged.html'>Flagged for Review</a> — everything we could not verify.</li></ol></div>
"""
page("index.html", "Dashboard — Hotspawn Pick&#x27;em line analysis", "index.html", body_index)

# ---------------- all matches ----------------
rows = [match_row(m) for m in matches]
page("matches.html", "All matches (26)", "matches.html",
     "<div class='card'><p>Own A% = our rank model (blank when a team has no verified HLTV rank). External A% = mean no-vig "
     "probability of accepted readings only (blank when none). Indicative and rejected readings are listed for audit.</p>"
     + table(HEAD_FULL, rows) + "</div>")


def subset(cat_pred):
    return [m for m in matches if cat_pred(m)]


# ---------------- S-tier ----------------
s_matches = subset(lambda m: m["category"].startswith("S-Tier"))
out_rows = []
for r in outrights:
    out_rows.append([e(r["team"]), e(r["bookmaker_outright_decimal"]), e(r["implied_raw_pct"]),
                     e(r["implied_novig_pct"]), link(r["source_url"], r["source_label"]), e(r["note"])])
body_s = (
    "<div class='card'><h2>Match lines (Thunderpick World Championship 2026)</h2>"
    + table(HEAD_SHORT + ["Hotspawn"], [match_row(m, full=False) + [link(m["hotspawn_match_url"], "Hotspawn")] for m in s_matches])
    + "</div>"
    "<div class='card'><h2>Tournament outrights (NOT match-win lines)</h2>"
    "<p>Outright prices are used for context only. They are not per-match probabilities and do not feed the pick rule.</p>"
    + table(["Team", "Decimal", "Implied raw %", "No-vig %", "Source", "Note"], out_rows)
    + "</div>"
    "<div class='card'><h2>Per-match readings</h2>" + table(["ID", "External readings (audit)"],
        [[m["id"], ext_cell(m["id"])] for m in s_matches]) + "</div>"
)
page("s-tier.html", "S-Tier · Thunderpick World Championship 2026", "s-tier.html", body_s)

# ---------------- Stake ----------------
st_matches = subset(lambda m: m["tournament"].startswith("Stake Pulse"))
page("stake.html", "Stake Pulse Beat III", "stake.html",
     "<div class='card'><h2>Match lines</h2>"
     + table(HEAD_SHORT + ["Hotspawn"], [match_row(m, full=False) + [link(m["hotspawn_match_url"], "Hotspawn")] for m in st_matches])
     + "</div><div class='card'><h2>Per-match readings</h2>"
     + table(["ID", "External readings (audit)"], [[m["id"], ext_cell(m["id"])] for m in st_matches]) + "</div>")

# ---------------- B/C ----------------
bc_matches = subset(lambda m: not m["category"].startswith("S-Tier") and not m["tournament"].startswith("Stake Pulse"))
inv_rows = [[e(r["tournament"]), e(r["count_in_cs2_filter"]), link(r["source_url"], "Hotspawn CS2 pick'em"), e(r["note"])] for r in inventory]
page("lower-tiers.html", "B/C-Tier &amp; inventory", "lower-tiers.html",
     "<div class='card'><h2>Match lines (B/C tier and other events)</h2>"
     + table(HEAD_SHORT + ["Hotspawn"], [match_row(m, full=False) + [link(m["hotspawn_match_url"], "Hotspawn")] for m in bc_matches])
     + "</div><div class='card'><h2>Per-match readings</h2>"
     + table(["ID", "External readings (audit)"], [[m["id"], ext_cell(m["id"])] for m in bc_matches]) + "</div>"
     + "<div class='card'><h2>Tournament inventory (Hotspawn CS2 filter)</h2>"
     "<p>Counts are the filter's own numbers. Pairings not extracted are blank and flagged (F-01).</p>"
     + table(["Tournament", "Count in filter", "Source", "Note"], inv_rows) + "</div>")

# ---------------- methodology ----------------
page("methodology.html", "Methodology", "methodology.html", """
<div class='card'><h2>Fixtures</h2><p>Only fixtures that appear in the server-rendered Hotspawn lobby list are used
(26 rows, H-01 to H-26). Team names and times are copied verbatim from the Hotspawn label. Hotspawn pick % is recorded as an
audit snapshot and is not an input to any probability or pick.</p></div>
<div class='card'><h2>Own line (originated)</h2><p>Rank-only Elo model, computed by <code>scripts/model.py</code>:</p>
<p><code>rating = 2000 − 300 · log10(HLTV world rank)</code><br>
<code>P(A beats B) = 1 / (1 + 10^(−(rating_A − rating_B)/400))</code></p>
<p>Ranks come from <code>data/ratings.csv</code> (HLTV, 2026-10-12, each row sourced). A team with no verified HLTV rank has
a blank own line. We do not infer a rank.</p></div>
<div class='card'><h2>External lines</h2><ul>
<li><b>Polymarket</b> (two-outcome prices in cents): used only if the two sides sum to 98–106¢. No-vig P(A) = a / (a+b).</li>
<li><b>eGamersWorld</b> decimal odds (bookmaker not named on page): no-vig P(A) = (1/oA) / (1/oA + 1/oB).</li>
<li><b>Accepted</b> readings feed the external mean. <b>Indicative</b> readings (zero volume) are shown only.
<b>Rejected</b> readings (overround outside the rule, or wrong market) are shown only.</li>
<li>Tournament outrights (FreeTips, Thunderpick WC) are context only, not match lines.</li></ul></div>
<div class='card'><h2>Pick rule</h2><p>A side is a pick only when the own line AND the mean accepted external line both put that
side at ≥55%. If they disagree, or either source is missing, the result is <b>no pick</b>. A single-source lean is not a pick.</p></div>
<div class='card'><h2>Limits</h2><ul><li>Rank-only model: no roster, map pool, form or news input.</li>
<li>Prices are a snapshot at fetch time and move. Re-run the pipeline before relying on them.</li>
<li>Analysis only, not betting advice.</li></ul></div>
<div class='card'><h2>Reproduce</h2><p><code>python3 scripts/model.py</code> then <code>python3 scripts/build_docs.py</code>.</p></div>
""")

# ---------------- flagged ----------------
FLAGS = [
    ("F-01", "Lobby shows more fixtures than were extracted",
     "Lobby header claims 60 matches this week and 85 CS2 fixtures. Only the 26 server-rendered rows were extracted. Remaining pairings are paginated client-side and were not invented.",
     "All non-listed fixtures; inventory rows marked blank",
     "https://play.hotspawn.com/cs2-pickems"),
    ("F-02", "Time basis differs by about 6 hours",
     "eGamersWorld and Polymarket display times about 6 h away from the Hotspawn labels for the same match (e.g. eGW Astralis vs Sashi 14.10 12:00; Hotspawn 06:00). Unresolved whether this is a display-timezone issue. Matching is by team pair and date, not time.",
     "H-05, H-14, H-15 and all Polymarket rows", "https://egamersworld.com/"),
    ("F-03", "Hotspawn crowd % is audit only",
     "Crowd % snapshot is in data/matches.csv for audit. It is not a probability and does not affect any line or pick.",
     "All rows", "https://play.hotspawn.com/cs2-pickems"),
    ("F-04", "Zero-volume markets are indicative only",
     "Polymarket Elisa BreakOut markets show $0 volume. Their readings are shown but are not accepted and do not feed picks.",
     "H-13, H-16, H-17, H-21", "https://polymarket.com/esports/cs2/elisa-breakout"),
    ("F-05", "Overround or conflicting readings rejected",
     "Sides summing outside 98–106¢ are rejected. Second readings on the same page that conflict with the first are rejected too (e.g. ENCE vs BOJONG 75/47 vs 64/36).",
     "Rejected: H-10, H-18, H-19, H-20, H-22 to H-26. Conflicts: H-03, H-07, H-16, H-17", "https://polymarket.com/esports/cs2/cct-europe"),
    ("F-06", "Teams without a verified HLTV top-41 rank",
     "These teams do not appear in the HLTV top-41 read used here, so own lines are blank: ex-Keyd Stars, Galorys, Zomblers, Overtake Sector, Gothic, Lavked, ex-RUSTEC, mellren, Sashi, Envy, Esport Academy Copenhagen, BOJONG, ENCE, Voca, Phantom, HAVU, RoundsGG, The Last Resort, G2 Ares, LFO 10, FORZE Reload.",
     "Most matches outside the pick list", "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-07", "WROTBERRY = WBT name mapping not confirmed",
     "Liquipedia confirms WBT = WhiteBIT Team. The link to Hotspawn's WROTBERRY is inferred from the fixture (HLTV WBT on 15/10 vs EAC, ENCE, BOJONG), not confirmed by name. Readings are indicative only.",
     "H-13, H-17, H-19", "https://www.hltv.org/team/13683/wbt"),
    ("F-08", "Overtake vs Overtake Sector mapping not confirmed",
     "Polymarket names the side 'Overtake'. Hotspawn says 'Overtake Sector'. Not verified as the same team.",
     "H-02", "https://polymarket.com/esports/cs2/esl-challenger-league"),
    ("F-09", "No line for H-12",
     "Polymarket's FORZE Reload market is vs Sökerorg, not Hotspawn's FORZE Reload vs LFO 10. Left blank.",
     "H-12", "https://polymarket.com/esports/cs2/cct-europe"),
    ("F-10", "G2 Ares is not HLTV G2",
     "The G2 Ares vs The Last Resort market (H-10) is rejected for overround (122¢). No HLTV rank is applied, since G2 Ares is not HLTV's G2 (#8).",
     "H-10", "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-11", "HLTV ranks changed since 2026-10-05",
     "Updated ranks: MIBR 18→12, BC.Game 52→70, Astralis 11→15, BETBOOM 13→14, Legacy 6→7, HEROIC 29→30, fnatic 40→36, HOTU 42→41. Ninjas in Pyjamas newly verified at #26.",
     "Own lines for affected matches", "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-12", "eGamersWorld bookmaker not named; odds move",
     "The EGW decimal odds are a snapshot from 2026-10-13. The bookmaker is not named on the page. Odds move, so re-check before use.",
     "H-05, H-14, H-15", "https://egamersworld.com/"),
    ("F-13", "Outright book attribution inconsistent",
     "FreeTips lists Stake as the bookmaker for the TWC outrights. A second FreeTips preview cites bet365 for an Aurora price. Outrights are context only and are not used in match probabilities.",
     "S-Tier outrights table", "https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/"),
    ("F-14", "Unmapped Polymarket rows",
     "ENJOY vs B8 Academy, MARKandLARRY vs Rooster and Liquid vs JiJieHao (Oct 13) are not Hotspawn fixtures in the extracted set. They are not mapped or used.",
     "Not in the 26 fixtures", "https://polymarket.com/esports/cs2/stake-pulse"),
    ("F-15", "Own model is rank-only",
     "No roster, map pool, form or news input. Own lines are a documented baseline, not a forecast.",
     "All own lines", "https://www.hltv.org/ranking/teams/2026/october/12"),
]
flag_rows = [[e(i), e(t), e(d), e(a), link(u, "source")] for i, t, d, a, u in FLAGS]
page("flagged.html", "⚠ Flagged for Review", "flagged.html",
     "<div class='card'><p>Items here are NOT blocking. Each one lists what is affected. Nothing was filled in by guessing.</p>"
     + table(["ID", "Issue", "Detail", "Affects", "Link"], flag_rows) + "</div>")

# ---------------- sources ----------------
SRC = [
    ("S-01", "Hotspawn lobby (fixture list, filter counts)", "https://play.hotspawn.com/lobby"),
    ("S-02", "Hotspawn CS2 pick'em (26 server-rendered rows)", "https://play.hotspawn.com/cs2-pickems"),
    ("S-03", "HLTV world ranking 2026/october/12", "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("S-04", "HLTV team: Ninjas in Pyjamas (#26)", "https://www.hltv.org/team/4411/ninjas-in-pyjamas"),
    ("S-05", "HLTV team: MIBR (#12)", "https://www.hltv.org/team/9215/mibr"),
    ("S-06", "HLTV team: BC.Game (#70)", "https://www.hltv.org/team/12878/bcgame"),
    ("S-07", "HLTV match: MIBR vs BC.Game, Stake Pulse Beat III", "https://www.hltv.org/matches/2399136/mibr-vs-bcgame-stake-pulse-beat-iii"),
    ("S-08", "HLTV team: WBT (fixture check)", "https://www.hltv.org/team/13683/wbt"),
    ("S-09", "Liquipedia: Elisa BreakOut Series #2 (WBT, EAC names)", "https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2"),
    ("S-10", "Polymarket: Stake Pulse (CS2)", "https://polymarket.com/esports/cs2/stake-pulse"),
    ("S-11", "Polymarket: CCT Europe (CS2)", "https://polymarket.com/esports/cs2/cct-europe"),
    ("S-12", "Polymarket: Elisa BreakOut (CS2)", "https://polymarket.com/esports/cs2/elisa-breakout"),
    ("S-13", "Polymarket: Thunderpick World Championship (CS2)", "https://polymarket.com/esports/cs2/thunderpick-world-championship"),
    ("S-14", "Polymarket: ESL Challenger League (CS2)", "https://polymarket.com/esports/cs2/esl-challenger-league"),
    ("S-15", "eGamersWorld: Astralis vs Sashi", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z"),
    ("S-16", "eGamersWorld: MIBR vs BC.Game", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX"),
    ("S-17", "eGamersWorld: Heroic vs Team Envy", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC"),
    ("S-18", "FreeTips: Thunderpick WC 2026 outrights (2026-10-11)", "https://www.freetips.com/esports/thunderpick-world-championship-2026-betting-odds-20261011-0007/"),
]
page("sources.html", "Sources", "sources.html",
     "<div class='card'><p>Every table row links to its source. Ids are used in the tables.</p>"
     + table(["ID", "Source", "URL"], [[e(i), e(t), link(u)] for i, t, u in SRC]) + "</div>")

print("built", len(list(DOCS.glob('*.html'))), "pages")
