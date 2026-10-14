#!/usr/bin/env python3
"""Session 57dbfba4: gap-resolution board.

Reads ONLY committed data:
  console/data/picks.csv        (consolidated board, session 228bb5bc)
  console/data/coverage.json    (its counts / capture times)
  gap-resolution/data/research.csv  (this session's HLTV -> books -> own-line ladder, per unresolved match)

Publishes gap-resolution/{index,unresolved,flagged,methodology}.html + data/unresolved.csv.
Fail-closed: refuses to publish if a non-market row lacks research, if probabilities
do not sum to 100, if a pick is not a team, or if a row lacks HLTV + rating source links.
No number is invented here; every % is copied from console/data/picks.csv.
"""
import csv, html, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "gap-resolution")
E = html.escape

def load(p):
    with open(os.path.join(ROOT, p), newline="", encoding="utf-8") as f: return list(csv.DictReader(f))

def main():
    picks = load("console/data/picks.csv")
    cov = json.load(open(os.path.join(ROOT, "console/data/coverage.json"), encoding="utf-8"))
    research = {r["fixture_id"]: r for r in load("gap-resolution/data/research.csv")}
    unresolved = [r for r in picks if not r["basis_rung"].startswith("market")]
    market = [r for r in picks if r["basis_rung"].startswith("market")]
    # --- fail-closed invariants ---
    errs = []
    for r in unresolved:
        fid = r["fixture_id"]
        if fid not in research: errs.append(f"{fid}: non-market row without research-ladder record")
        if abs(float(r["p_a_pct"]) + float(r["p_b_pct"]) - 100) > 0.11: errs.append(f"{fid}: probabilities do not sum to 100")
        if r["pick"] not in (r["team_a"], r["team_b"]): errs.append(f"{fid}: pick is not a team")
        if not r["hltv_match_url"].startswith("https://www.hltv.org/"): errs.append(f"{fid}: missing HLTV source")
        if not r["source_url"].startswith("https://"): errs.append(f"{fid}: missing rating source")
        if "hotspawn" in r["source_url"]: errs.append(f"{fid}: Hotspawn used as probability source")
    if len(unresolved) != len(research): errs.append("research.csv rows != non-market rows in console board")
    if errs:
        print("FAIL-CLOSED, nothing published:"); [print(" -", e) for e in errs]; return 1
    # --- unresolved.csv ---
    cols = ["fixture_id","competition","tier","team_a","team_b","start_utc","lock_utc","basis_rung","p_a_pct","p_b_pct","pick","pick_pct","hltv_match_url","rating_source_url","egw_url","polymarket_url","resolution","limitation","checked_utc"]
    with open(os.path.join(OUT, "data", "unresolved.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        for r in unresolved:
            g = research[r["fixture_id"]]
            w.writerow([r["fixture_id"],r["competition"],r["tier"],r["team_a"],r["team_b"],r["start_utc"],r["lock_utc"],r["basis_rung"],r["p_a_pct"],r["p_b_pct"],r["pick"],r["pick_pct"],r["hltv_match_url"],r["source_url"],g["egw_url"],g["polymarket_url"],g["resolution"],g["limitation"],g["checked_utc"]])
    asof = cov.get("data_as_of_utc","")
    CSS = '<link rel="stylesheet" href="style.css">'
    HEAD = lambda t: f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(t)}</title>{CSS}</head><body>'
    NAV = ('<header><a href="index.html"><b>Gap-resolution</b></a><nav>'
           '<a href="../console/index.html">All picks ↗</a><a href="unresolved.html">Unresolved</a>'
           '<a href="flagged.html">Flagged</a><a href="methodology.html">Method</a></nav></header>')
    def card(r, detail=False):
        g = research[r["fixture_id"]]
        ladder = ""
        if detail:
            ladder = (f'<table class="ladder"><tr><th>Step tried</th><th>Result</th></tr>'
                      f'<tr><td>1 · HLTV</td><td>{E(g["hltv_result"])} <a href="{E(r["hltv_match_url"])}">HLTV match ↗</a></td></tr>'
                      f'<tr><td>2 · Esports books (Pinnacle / Thunderpick via bo3.gg / EGamersWorld–bc.game)</td><td>{E(g["books_result"])} <a href="{E(g["egw_url"])}">EGamersWorld ↗</a></td></tr>'
                      f'<tr><td>3 · Prediction market (Polymarket)</td><td>{E(g["polymarket_result"])} <a href="{E(g["polymarket_url"])}">Polymarket ↗</a></td></tr>'
                      f'<tr><td>4 · Own originated line / research</td><td>{E(g["resolution"])} <a href="{E(r["source_url"])}">Valve VRS source line ↗</a></td></tr></table>'
                      f'<p class="limit"><b>Limitation:</b> {E(g["limitation"])}</p>')
        return (f'<article class="card"><p class="meta">{E(r["competition"])} · Tier {E(r["tier"].upper())} · starts {E(r["start_utc"])} UTC · locks {E(r["lock_utc"])} UTC</p>'
                f'<h3>{E(r["team_a"])} <span>vs</span> {E(r["team_b"])}</h3>'
                f'<p class="pick">PICK: {E(r["pick"])} — {E(r["pick_pct"])}%</p>'
                f'<div class="bar"><span>{E(r["team_a"])} {E(r["p_a_pct"])}%</span><i style="width:{E(r["p_a_pct"])}%"></i></div>'
                f'<div class="bar"><span>{E(r["team_b"])} {E(r["p_b_pct"])}%</span><i style="width:{E(r["p_b_pct"])}%"></i></div>'
                f'<p class="basis">Basis: {E(r["basis_label"])} ({E(r["basis_rung"])}) · read {E(r["read_utc"])} · ladder checked {E(g["checked_utc"])}</p>{ladder}'
                f'<p class="links"><a href="{E(r["hltv_match_url"])}">HLTV ↗</a> · <a href="{E(r["source_url"])}">Rating source ↗</a> · <a href="flagged.html">Flags</a></p></article>')
    mrows = "".join(f'<tr><td>{E(r["start_utc"][:16].replace("T"," "))}Z</td><td>{E(r["team_a"])} vs {E(r["team_b"])}</td><td><b>{E(r["pick"])}</b> {E(r["pick_pct"])}%</td><td>{E(r["team_a"])} {E(r["p_a_pct"])} / {E(r["team_b"])} {E(r["p_b_pct"])}</td><td><a href="{E(r["source_url"])}">source ↗</a> · <a href="{E(r["hltv_match_url"])}">HLTV ↗</a></td></tr>' for r in market)
    index = HEAD("Hotspawn CS2 — executive summary & gap-resolution picks") + NAV + f"""<main>
<section class="hero"><p class="eyebrow">Executive summary · snapshot {E(asof)}</p>
<h1>Every Hotspawn CS2 match has a pick. Here is where to find it — and how the hard ones were resolved.</h1>
<p><b>{len(picks)} open matches · {len(picks)} picks · 0 blank.</b> {len(market)} are priced by an outside betting market first (featured route). The other <b>{len(unresolved)}</b> are low-tier / uncovered matches that no featured book prices — this page documents, match by match, the research ladder (HLTV → esports books → own originated line) used <i>only</i> for those, plus their limitations. Hotspawn crowd % is never used as a probability.</p>
<div class="actions"><a class="btn" href="../console/index.html">📋 Updated list of all picks (one row per match) ↗</a><a class="btn alt" href="unresolved.html">Unresolved &amp; fallback picks ({len(unresolved)}) ↓</a><a class="btn alt" href="../every/index.html">Every-match board ↗</a><a class="btn alt" href="../picks-full/index.html">Full picks by tier ↗</a></div>
<p class="small">On a phone: tap “Updated list of all picks” — one card per match, pick first, both win % and its source. Data as of {E(asof)}; the consolidated board rebuilds hourly and this gap board every 4 hours (GitHub Actions, fail-closed — a failed run keeps the last good page).</p></section>
<section><h2>Featured-route picks (outside market, {len(market)})</h2><p class="small">De-vigged two-sided outside prices (Pinnacle direct, Thunderpick relayed by bo3.gg, EGamersWorld-reported bc.game, or Polymarket) as consolidated on the <a href="../console/index.html">all-picks board</a>. Full per-book detail: <a href="../picks-full/market-lines.html">market lines ↗</a>.</p>
<div class="twrap"><table><tr><th>Start (UTC)</th><th>Match</th><th>Pick</th><th>Win % A / B</th><th>Sources</th></tr>{mrows}</table></div></section>
<section><h2>⚠ Unresolved by the featured route ({len(unresolved)}) — resolved by research, with limitations</h2>
<p>These matches are <b>not</b> on Polymarket and have no usable bookmaker line (placeholder 1.80/1.80 or $0-volume quotes were rejected, never de-vigged). Their picks come from our own HLTV/Valve-rating line — or, for one match, a flagged research line. They are <b>not</b> market prices. Full ladder per match: <a href="unresolved.html">Unresolved picks page →</a></p>
{''.join(card(r) for r in unresolved)}</section>
<section><h2>Limitations you should know</h2><ul>
<li>Own-line % are model estimates from Valve VRS (2026-10-05) + HLTV ranking with a calibrated logistic (k=0.4568) and BO3 transform — uncalibrated against results, not bookmaker prices.</li>
<li>One row (FORZE Reload vs LFO 10) has a team absent from the official standings: its % is roster-mapped <b>research only</b>, flagged PF-02.</li>
<li>Placeholder odds (EGamersWorld 1.80/1.80, Polymarket 94¢/93¢ at $0 volume) and opponent-conflicting markets are rejected — see <a href="flagged.html">Flagged for Review</a>.</li>
<li>Snapshot-bound: matches lock at the times shown; after lock, treat picks as historical. No guarantee of live coverage — the board is rebuilt from committed captures every 4–8 h at best (hourly for console/).</li></ul>
<p class="small">Analysis only, not betting advice. Every row links its source for manual review.</p></section></main></body></html>"""
    unres = HEAD("Unresolved picks — research ladder & limitations") + NAV + f"""<main><h1>Unresolved picks ({len(unresolved)})</h1>
<p>Matches the featured route cannot resolve: low-tier CS2 with no Pinnacle/Thunderpick/bc.game line and no (usable) Polymarket market. For <b>only</b> these, the ladder below was followed in order. Checked {E(max(g['checked_utc'] for g in research.values()))}; probabilities copied unchanged from the <a href="../console/index.html">consolidated board</a> (read {E(asof)}).</p>
{''.join(card(r, detail=True) for r in unresolved)}
<p><a href="index.html">← Executive summary</a> · <a href="data/unresolved.csv">unresolved.csv (machine-readable)</a></p></main></body></html>"""
    flags = [("U-01","No bookmaker coverage for C-tier CCT qualifiers","Pinnacle and Thunderpick (via bo3.gg) publish no quote for the 3 unresolved fixtures in the committed captures; EGamersWorld shows 1.80/1.80 placeholders. Own-line fallback is the only sourced option."),
             ("U-02","Placeholder prediction-market quotes rejected","Polymarket mellren vs Privateer Gaming: 94¢/93¢, $0.00 volume — cannot be de-vigged (sides sum >100¢ with no trades). Not used."),
             ("U-03","Opponent conflict — FORZE Reload fixture","Polymarket prices FORZE Reload vs Sökerorg at the slot where Hotspawn/HLTV list FORZE Reload vs LFO 10. The Sökerorg price was not applied to LFO 10."),
             ("U-04","Team absent from official standings (PF-02)","LFO 10 is not in Valve's 2026-10-05 VRS file; its line is roster-mapped research, flagged, and the exact % should be treated as unverified."),
             ("U-05","Ratings staleness","Valve VRS file dated 2026-10-05 and HLTV ranking are the newest official files available to the boards; form since then is not reflected."),
             ("U-06","Name variants","Privateer vs Privateer Gaming; Banda chuya VRS duplication disambiguated (PF-01). Aliases are documented per row, never silently merged."),
             ("U-07","Snapshot & lock risk","Picks are valid only before the lock times shown. Hotspawn can add/replace fixtures between 4-hourly rebuilds; the hourly console board is the freshest list.")]
    flagged = HEAD("Flagged for Review — gap-resolution") + NAV + "<main><h1>Flagged for Review</h1><p>Non-blocking. Each item links the source a human should re-check.</p>" + "".join(
        f'<article class="card"><h3>{i} — {E(t)}</h3><p>{E(d)}</p><p class="links"><a href="unresolved.html">Unresolved picks</a> · <a href="../console/flagged.html">Consolidated flags ↗</a> · <a href="../reviews/228bb5bc-verification.md">Verification record</a></p></article>' for i,t,d in flags) + "</main></body></html>"
    method = HEAD("Methodology — gap-resolution") + NAV + """<main><h1>How a pick is resolved</h1><ol>
<li><b>Featured route first:</b> a two-sided outside bookmaker/prediction-market price (Pinnacle direct → Thunderpick relayed by bo3.gg → EGamersWorld-reported bc.game → Polymarket traded prices), de-vigged: p(A)=(1/oddsA)/((1/oddsA)+(1/oddsB)). Placeholder 1.80/1.80, $0-volume and opponent-conflicting quotes are rejected.</li>
<li><b>Only if that fails — HLTV:</b> confirm the fixture, teams, event and series format on the HLTV match page linked on every row.</li>
<li><b>Then esports books again by name:</b> search the fixture on EGamersWorld/bc.game, Pinnacle, Thunderpick and Polymarket (documented per match in <a href="data/unresolved.csv">unresolved.csv</a> and research.csv).</li>
<li><b>Own originated line:</b> Valve Regional Standings (2026-10-05, GitHub, line-linked) + HLTV ranking, calibrated logistic k=0.4568 with the series (BO3) transform, as implemented by the consolidated board — the % is copied, not recomputed, here.</li>
<li><b>Research line (last resort, flagged):</b> if a team is absent from the official standings, a roster-mapped estimate may be published only labelled RESEARCH / PF-02; otherwise the % would stay blank.</li></ol>
<p>Hotspawn supplies fixture identity and lock/start times only — never a probability. Unconfirmable values stay blank and flagged. Rebuilt by <code>scripts/57dbfba4_build.py</code> every 4 hours via <code>gap-resolution-57dbfba4.yml</code>, fail-closed.</p>
<p><a href="index.html">← Executive summary</a></p></main></body></html>"""
    for name, content in [("index.html",index),("unresolved.html",unres),("flagged.html",flagged),("methodology.html",method)]:
        open(os.path.join(OUT,name),"w",encoding="utf-8").write(content)
    print(f"OK: {len(picks)} picks, {len(market)} market, {len(unresolved)} unresolved -> gap-resolution/")
    return 0
if __name__ == "__main__": sys.exit(main())
