#!/usr/bin/env python3
"""FB-01/FB-02: Every-match CS2 picks for the published Hotspawn snapshot.

Sources of truth (committed evidence only; no network, no invention):
  * slate/data/analysis.csv + coverage.json  (session 180a42a0, captured 2026-10-14T02:23:08Z)
      - Hotspawn fixture identity / UTC start+lock, latest primary Pinnacle quotes (5),
        slate map-level own line (HLTV+VRS, provisional).
  * data/8944bb84/fixtures.csv, external_lines.csv, own_lines.csv, ratings.csv
    (session 8944bb84, captured 2026-10-14T01:48:00Z, HLTV match-page verified)
      - series format (BO1/BO3) + HLTV match URL for all 28 open fixtures,
        earlier external quotes (Pinnacle Direct / EGamersWorld bc.game; 1.80/1.80
        placeholders already blank there and re-rejected here),
        originated model probabilities (Valve VRS Glicko D=372.12, HLTV blend).

Pick hierarchy (first tier that resolves; tiers are never averaged together):
  A  Latest primary market  - slate Pinnacle de-vig.
  B  Earlier verified external market - 8944bb84 quote de-vig (recomputed here).
     Labelled secondary/earlier: EGW reports are not re-read against the bookmaker.
  C  Sourced-format rating model - 8944bb84 own line, both teams VRS-verified.
  D  Guided lean, NO numeric probability - only #1079624 FORZE Reload vs LFO 10:
     FORZE Reload is VRS #84 / HLTV #75; LFO 10 has no standing in the official
     2026-10-05 Valve VRS file and no HLTV ranking (blank in 8944bb84 ratings).
     Pick = FORZE Reload, probability left blank, flagged EP-01.

Hotspawn crowd percentages are never used. Any open CS2 fixture found in slate
with no tier evidence is emitted as NO PICK - FLAGGED (never invented).
"""
import csv, html, json, os, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DATA = os.path.join(ROOT, "data", "fbcccda2")
OUT_SITE = os.path.join(ROOT, "everypick")
HOTSPAWN = "https://play.hotspawn.com/cs2-pickems"
VRS_URL = "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md"
HLTV_RANK = "https://www.hltv.org/ranking/teams/2026/october/12"

def rd(p):
    with open(os.path.join(ROOT, p), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def devig(oa, ob):
    ia, ib = 1.0/float(oa), 1.0/float(ob)
    t = ia+ib
    return round(100*ia/t, 1), round(100*ib/t, 1), round(100*(t-1), 2)

def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def main():
    slate = [r for r in rd("slate/data/analysis.csv") if r["sport"] == "cs2"]
    cov = json.load(open(os.path.join(ROOT, "slate/data/coverage.json")))
    snap = cov["generated_utc"]
    fx84 = {r["match_id"]: r for r in rd("data/8944bb84/fixtures.csv")}
    ext84 = {r["match_id"]: r for r in rd("data/8944bb84/external_lines.csv")}
    own84 = {r["match_id"]: r for r in rd("data/8944bb84/own_lines.csv")}
    rat84 = {r["hotspawn_team"]: r for r in rd("data/8944bb84/ratings.csv")}

    rows, flags = [], []
    for s in sorted(slate, key=lambda r: (r["start_utc"], r["fixture_id"])):
        fid = s["fixture_id"]; fx = fx84.get(fid, {}); ex = ext84.get(fid, {}); ow = own84.get(fid, {})
        fmt = fx.get("series_format", "") or s.get("best_of", "")
        hltv = fx.get("hltv_match_url", "") or s.get("hltv_url", "")
        flags_r = []
        if not fx: flags_r.append("EP-NO84: no 8944bb84 HLTV verification row")
        if not fmt: flags_r.append("EP-FMT: series format unverified in both boards")
        tier = ""; pick = ""; pa = pb = ""; basis = ""; book = ""; oa_s = ob_s = ""; murl = ""; mcap = ""
        over = ""
        # Tier A: latest primary market from slate
        if s.get("market_p_a_pct"):
            oa_s, ob_s = s["market_odds_a"], s["market_odds_b"]
            pa, pb, over = devig(oa_s, ob_s)
            assert abs(pa - float(s["market_p_a_pct"])) < 0.15, fid
            tier, book = "A", s["market_book"] or "Pinnacle"
            murl, mcap = s["market_url"], s["market_captured_utc"]
            basis = "Featured pick — latest primary Pinnacle market (slate snapshot), de-vigged"
        # Tier B: earlier verified external market (8944bb84)
        elif ex.get("primary_odds_a") and ex.get("primary_odds_b"):
            oa_s, ob_s = ex["primary_odds_a"], ex["primary_odds_b"]
            if {oa_s, ob_s} == {"1.8", "1.80"} or oa_s in ("1.8", "1.80") and ob_s in ("1.8", "1.80"):
                flags_r.append("EP-PH: 1.80/1.80 placeholder rejected")
            else:
                pa, pb, over = devig(oa_s, ob_s)
                assert abs(pa - float(ex["devig_p_a_pct"])) < 0.15, fid
                tier = "B"; book = ex["primary_book"]
                murl = ex["primary_source_url"]; mcap = ex["captured_utc"]
                kind = "Pinnacle Direct (earlier capture)" if "Pinnacle" in book else "EGamersWorld bc.game report (secondary, not re-read vs bookmaker)"
                basis = f"External market — {kind}, de-vigged"
        # Tier C: sourced-format rating model
        if not tier and ow.get("own_p_a") and ow.get("own_p_b") and fmt:
            pa, pb = float(ow["own_p_a"]), float(ow["own_p_b"])
            tier = "C"; basis = f"Rating model — {ow.get('own_method','Valve VRS Glicko D=372.12')} ({fmt}, format from HLTV match page)"
            mcap = "2026-10-14T01:48:00Z (8944bb84)"
        # Tier D: the one guided lean
        if not tier and fid == "1079624":
            tier = "D"; pick = "FORZE Reload"
            basis = "Guided lean — NO numeric line: FORZE Reload VRS #84 (1100 pts) / HLTV #75 vs LFO 10 with no 2026-10-05 VRS standing and no HLTV ranking (both blank in 8944bb84 ratings)"
            flags_r.append("EP-01: guided lean only; probability blank by design")
        if tier in ("A", "B", "C"):
            pick = s["team_a"] if float(pa) >= float(pb) else s["team_b"]
        if not tier:
            flags_r.append("EP-NOPICK: no market and no verified rating for both teams — left blank, flagged")
        # cross-checks / disputes (flagged, never hidden, never averaged)
        model_pa = fnum(ow.get("own_p_a")); slate_pa = fnum(s.get("own_p_a_pct"))
        agree = ""
        if tier in ("A", "B") and model_pa is not None and pa != "":
            agree = "model agrees" if (float(pa) >= 50) == (model_pa >= 50) else "MODEL DISAGREES — see Flagged EP-02"
            if "DISAGREES" in agree: flags_r.append("EP-02: market pick direction differs from 8944bb84 rating model")
        if tier in ("A", "B") and slate_pa is not None and pa != "" and (float(pa) >= 50) != (slate_pa >= 50):
            flags_r.append("EP-03: direction differs from slate map-level own line")
        ra, rb = rat84.get(s["team_a"], {}), rat84.get(s["team_b"], {})
        rows.append(dict(fixture_id=fid, start_utc=s["start_utc"], lock_utc=s["lock_utc"],
            tournament=s["competition"], tier_hotspawn=s["tier"], series_format=fmt,
            team_a=s["team_a"], team_b=s["team_b"], pick=pick,
            pick_pct=(max(float(pa), float(pb)) if pa != "" else ""), p_a_pct=pa, p_b_pct=pb,
            pick_tier=tier, pick_basis=basis, market_book=book, odds_a=oa_s, odds_b=ob_s,
            overround_pct=over, market_url=murl, market_captured_utc=mcap,
            model_p_a_pct=(ow.get("own_p_a","")), model_p_b_pct=(ow.get("own_p_b","")),
            model_method=ow.get("own_method",""), slate_own_p_a_pct=s.get("own_p_a_pct",""),
            vrs_a=f"{ra.get('vrs_standing','')} ({ra.get('vrs_points','')} pts)" if ra.get('vrs_points') else "",
            vrs_b=f"{rb.get('vrs_standing','')} ({rb.get('vrs_points','')} pts)" if rb.get('vrs_points') else "",
            vrs_url_a=ra.get("vrs_url",""), vrs_url_b=rb.get("vrs_url",""),
            hltv_team_url_a=ra.get("hltv_url",""), hltv_team_url_b=rb.get("hltv_url",""),
            model_agreement=agree, hotspawn_url=HOTSPAWN, hltv_match_url=hltv,
            snapshot_utc=snap, flags="; ".join(flags_r)))
        for fl in flags_r:
            flags.append(dict(fixture_id=fid, match=f"{s['team_a']} vs {s['team_b']}", code=fl.split(":")[0],
                detail=fl, hotspawn_url=HOTSPAWN, hltv_match_url=hltv, source_url=murl or hltv or VRS_URL))

    os.makedirs(OUT_DATA, exist_ok=True); os.makedirs(OUT_SITE, exist_ok=True)
    cols = list(rows[0].keys())
    with open(os.path.join(OUT_DATA, "every_pick.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    with open(os.path.join(OUT_DATA, "flags.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(flags[0].keys())); w.writeheader(); w.writerows(flags)
    json.dump(dict(snapshot_utc=snap, generated_by="scripts/fbcccda2_build.py (offline, committed evidence only)",
        counts=dict(open_cs2=len(rows), with_pick=sum(1 for r in rows if r["pick"]),
                    with_numeric_pct=sum(1 for r in rows if r["p_a_pct"] != ""),
                    tier_A=sum(1 for r in rows if r["pick_tier"]=="A"), tier_B=sum(1 for r in rows if r["pick_tier"]=="B"),
                    tier_C=sum(1 for r in rows if r["pick_tier"]=="C"), tier_D=sum(1 for r in rows if r["pick_tier"]=="D"),
                    no_pick=sum(1 for r in rows if not r["pick"]))),
        open(os.path.join(OUT_DATA, "coverage.json"), "w"), indent=1)
    render(rows, flags, snap)
    print(f"rows={len(rows)} picks={sum(1 for r in rows if r['pick'])} numeric={sum(1 for r in rows if r['p_a_pct']!='')} flags={len(flags)}")

def esc(x): return html.escape(str(x if x is not None else ""), quote=True)
CSS = """:root{--bg:#0f1216;--panel:#171c22;--panel2:#1e242c;--line:#2b333d;--fg:#e8edf3;--muted:#9aa7b4;--accent:#7857cf;--good:#3fb950;--warn:#d29922}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:18px 14px 56px} a{color:#8fb4ff}
nav{display:flex;gap:6px;overflow-x:auto;padding:10px 0}nav a{white-space:nowrap;text-decoration:none;color:var(--fg);background:var(--panel2);border:1px solid var(--line);border-radius:999px;padding:7px 12px;font-size:14px}nav a.on{background:var(--accent);color:#fff}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:15px;margin:12px 0}
.pick{font-size:20px;font-weight:800}.pick small{display:block;font-size:12px;color:var(--muted);font-weight:600;letter-spacing:.05em}
.bar{height:10px;background:#2b333d;border-radius:5px;overflow:hidden}.bar>i{display:block;height:100%;background:linear-gradient(90deg,#2f81f7,#7857cf)}
.row{display:flex;justify-content:space-between;gap:10px}.mut{color:var(--muted);font-size:13px}.badge{font-size:11px;font-weight:800;border:1px solid var(--accent);color:#c9b6ff;border-radius:999px;padding:2px 8px}
.badge.D{border-color:var(--warn);color:#e3b341}.src{font-size:13px;word-break:break-word}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
.cta{display:inline-block;background:var(--accent);color:#fff;padding:13px 18px;border-radius:10px;text-decoration:none;font-weight:800}
@media(max-width:640px){.pick{font-size:19px}table,thead,tbody,tr,th,td{display:block}thead{display:none}tr{background:var(--panel);border:1px solid var(--line);border-radius:10px;margin:10px 0;padding:8px}}
"""
def head(t):
    return f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(t)}</title><style>{CSS}</style></head><body><main class="wrap">'
NAV = '<nav><a href="index.html">Every-match picks</a><a href="../index.html">Site home</a><a href="../slate/cs2.html">Featured board</a><a href="methodology.html">How picks are made</a><a href="flagged.html">Flagged for Review</a></nav>'
def render(rows, flags, snap):
    cards = []
    for r in rows:
        pct = f'{r["pick_pct"]}%' if r["pick_pct"] != "" else "no % — guided lean"
        bar = f'<div class="row"><span>{esc(r["team_a"])} <b>{esc(r["p_a_pct"])}%</b></span><span>{esc(r["team_b"])} <b>{esc(r["p_b_pct"])}%</b></span></div><div class="bar"><i style="width:{esc(r["p_a_pct"] or 50)}%"></i></div>' if r["p_a_pct"] != "" else '<p class="mut">Probability: — (blank by design, see Flagged EP-01)</p>'
        odds = f' · odds {esc(r["odds_a"])}/{esc(r["odds_b"])} · overround {esc(r["overround_pct"])}%' if r["odds_a"] else ""
        model = f'<br>Rating model: {esc(r["team_a"])} {esc(r["model_p_a_pct"])}% / {esc(r["team_b"])} {esc(r["model_p_b_pct"])}% {esc(r["model_agreement"])}' if r["model_p_a_pct"] else ""
        srcs = " · ".join(x for x in [f'<a href="{esc(r["hotspawn_url"])}">Hotspawn fixture</a>', (f'<a href="{esc(r["hltv_match_url"])}">HLTV match / format</a>' if r["hltv_match_url"] else ""), (f'<a href="{esc(r["market_url"])}">Market quote</a>' if r["market_url"] else ""), (f'<a href="{esc(r["vrs_url_a"])}">VRS {esc(r["team_a"])}</a>' if r["vrs_url_a"] else ""), (f'<a href="{esc(r["vrs_url_b"])}">VRS {esc(r["team_b"])}</a>' if r["vrs_url_b"] else "")] if x)
        cards.append(f'''<article class="card" data-lock="{esc(r['lock_utc'])}"><div class="row"><span class="mut">{esc(r['start_utc'])} · {esc(r['tournament'])} · {esc(r['series_format'] or 'format unverified')} · #{esc(r['fixture_id'])}</span><span class="badge {esc(r['pick_tier'])}">TIER {esc(r['pick_tier'] or '—')}</span></div>
<div class="pick"><small>PICK</small>{esc(r['pick'] or 'NO PICK — FLAGGED')} · {esc(pct)}</div>{bar}
<p class="mut">{esc(r['pick_basis'])}{esc(odds)}{model}</p><p class="src">Sources: {srcs}</p>{('<p class="mut">Flags: '+esc(r['flags'])+'</p>') if r['flags'] else ''}</article>''')
    counts = json.load(open(os.path.join(OUT_DATA, "coverage.json")))["counts"]
    index = head("Every CS2 match — pick & probability") + NAV + f"""
<h1>Every CS2 match: pick &amp; probability</h1>
<p><strong>Executive summary.</strong> Snapshot <b>{esc(snap)}</b> (Hotspawn via slate collector). Of <b>{counts['open_cs2']} open CS2 matches</b>, <b>{counts['with_pick']} now have a pick</b> ({counts['with_numeric_pct']} with a numeric probability, 1 guided lean with % blank). Featured Tier-A picks: {counts['tier_A']} · external-market Tier B: {counts['tier_B']} · rating-model Tier C: {counts['tier_C']} · guided-lean Tier D: {counts['tier_D']}.</p>
<p class="mut">Start here on mobile: each card below shows the pick first, then both teams' %. Locked-at-view-time cards are marked by your browser clock. Low-tier matches not on Polymarket/featured books are covered by Tiers B–D only — read the tier badge. Hotspawn crowd % is never used.</p>
<p><a class="cta" href="#picks">Jump to all {counts['open_cs2']} picks ↓</a> &nbsp; <a href="flagged.html">Flagged for Review</a> · <a href="methodology.html">Methodology</a> · <a href="../slate/cs2.html">Featured board (Tier A only)</a></p>
<h2 id="picks">All picks</h2>{''.join(cards)}
<footer class="mut">Analysis only, not betting advice. Probabilities are de-vigged market or provisional model estimates, not guarantees. Data: <a href="../data/fbcccda2/every_pick.csv">every_pick.csv</a>. Rebuilt by scripts/fbcccda2_build.py from committed slate + 8944bb84 evidence.<script>document.querySelectorAll('[data-lock]').forEach(c=>{{if(new Date(c.dataset.lock)<new Date()){{c.insertAdjacentHTML('afterbegin','<p><span class="badge D">LOCKED at view time — historical pick</span></p>')}}}});</script></footer></main></body></html>"""
    open(os.path.join(OUT_SITE, "index.html"), "w").write(index)
    frows = "".join(f'<tr><td>{esc(f["fixture_id"])}</td><td>{esc(f["match"])}</td><td>{esc(f["code"])}</td><td>{esc(f["detail"])}</td><td><a href="{esc(f["source_url"])}">source</a> · <a href="{esc(f["hltv_match_url"] or f["source_url"])}">HLTV</a></td></tr>' for f in flags)
    open(os.path.join(OUT_SITE, "flagged.html"), "w").write(head("Flagged for Review — every-pick") + NAV + f"<h1>Flagged for Review</h1><p class='mut'>Non-blocking. EP-01 guided lean (blank %), EP-02/EP-03 market-vs-model direction disputes, placeholder/format gaps. Snapshot {esc(snap)}.</p><table><thead><tr><th>ID</th><th>Match</th><th>Code</th><th>Detail</th><th>Sources</th></tr></thead><tbody>{frows}</tbody></table></main></body></html>")
    open(os.path.join(OUT_SITE, "methodology.html"), "w").write(head("Methodology — every-pick") + NAV + f"""<h1>How every-match picks are made</h1>
<p>Fixture identity/start/lock only from Hotspawn (slate snapshot {esc(snap)}). Hotspawn crowd % never enters a probability.</p>
<table><thead><tr><th>Tier</th><th>Rule</th><th>Source</th></tr></thead><tbody>
<tr><td>A — Featured</td><td>Latest primary Pinnacle quote in slate, de-vigged p=(1/o)/Σ(1/o)</td><td><a href="../slate/cs2.html">slate board</a> · <a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/">Pinnacle</a></td></tr>
<tr><td>B — External market</td><td>Earlier verified quote (Pinnacle Direct or EGamersWorld bc.game report) captured 2026-10-14T01:48Z by session 8944bb84, de-vig recomputed; 1.80/1.80 placeholders rejected. EGW is secondary — not re-read against the bookmaker.</td><td><a href="../data/8944bb84/external_lines.csv">external_lines.csv</a> · <a href="https://egamersworld.com/counterstrike/matches">EGamersWorld</a></td></tr>
<tr><td>C — Rating model</td><td>Sourced BO format (HLTV match page) + both teams VRS-verified; 8944bb84 originated line (Valve VRS Glicko D=372.12 ± HLTV blend). Provisional, uncalibrated.</td><td><a href="{VRS_URL}">Valve VRS 2026-10-05</a> · <a href="{HLTV_RANK}">HLTV ranking 2026-10-12</a></td></tr>
<tr><td>D — Guided lean</td><td>Only where A–C cannot resolve (#1079624): pick guided by sourced ranking presence/absence; <b>probability blank</b>.</td><td><a href="https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11">HLTV 2399301</a></td></tr>
</tbody></table><p class="mut">Tiers are never averaged. Market/model disagreements are flagged (EP-02/EP-03), not blended. New Hotspawn fixtures are picked up by the hourly slate collector; everypick rebuilds on schedule and any fixture without tier evidence appears as NO PICK — FLAGGED.</p></main></body></html>""")

if __name__ == "__main__":
    main()
