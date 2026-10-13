#!/usr/bin/env python3
"""Session 844ba68e: originate lines and picks for the Hotspawn pick'em fixtures.

Inputs (all verified, every row carries a source URL):
  data/844ba68e/fixtures.csv       Hotspawn fixtures (H-01..H-26) + pick % snapshot (NOT used as probability)
  data/844ba68e/ranks.csv          HLTV world ranking 2026-10-12 (verified ranks only)
  data/844ba68e/market_quotes.csv  Polymarket listing quotes (cents, decimal, volume) and aggregator odds

Outputs:
  data/844ba68e/picks.csv          one row per fixture: lines, basis, pick, sources
  docs/own-lines.html              GitHub Pages table with source links

Rules
  1. Rank-model line (originated): rating = 2000 - 300*log10(rank); P(A) = 1/(1+10^(-(rA-rB)/400)).
     Only when both teams have a verified HLTV world rank.
  2. Market line: Polymarket listing prices, de-vigged by normalising the two implied probabilities
     (1/decimal). Used only if total market volume >= LIQ_MIN_USD and the mapping is confirmed.
  3. Aggregator line: EGW / stavka.tv bookmaker odds, de-vigged the same way. No volume test.
  4. Consensus ("our line") = equal-weight mean of the usable de-vigged sources for team A.
  5. Pick = favourite of the consensus when all usable sources agree on the favourite.
     If the usable sources disagree on the favourite: NO PICK (conflict).
     If there are no usable sources: NO PICK (no usable line).
     Consensus below 55% is labelled a toss-up "Lean X".
  6. Hotspawn pick % is recorded for transparency only and is never used as a probability.
"""
import csv
import html
import math
import os
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "844ba68e")
LIQ_MIN_USD = 1000.0
TOSS_UP = 0.55
RANK_CONST = 2000.0


def rank_rating(rank: int) -> float:
    return RANK_CONST - 300.0 * math.log10(rank)


def rank_prob_a(rank_a: int, rank_b: int) -> float:
    d = rank_rating(rank_a) - rank_rating(rank_b)
    return 1.0 / (1.0 + 10 ** (-d / 400.0))


def novig_a(dec_a: float, dec_b: float) -> float:
    ia, ib = 1.0 / dec_a, 1.0 / dec_b
    return ia / (ia + ib)


def load_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def pct(p):
    return "" if p is None else f"{100 * p:.1f}"


def main():
    fixtures = load_csv("fixtures.csv")
    ranks = {r["team"].strip().lower(): r for r in load_csv("ranks.csv")}
    quotes = load_csv("market_quotes.csv")

    rows_out = []
    for fx in fixtures:
        hid, a, b = fx["hid"], fx["team_a"], fx["team_b"]

        # 1. rank-model line
        own_p = None
        ra = ranks.get(a.strip().lower(), {}).get("hltv_world_rank_2026_10_12", "")
        rb = ranks.get(b.strip().lower(), {}).get("hltv_world_rank_2026_10_12", "")
        if ra and rb:
            own_p = rank_prob_a(int(ra), int(rb))

        # 2 + 3. market and aggregator lines
        market_p, market_vol, market_src = None, None, ""
        agg_p, agg_src = None, ""
        notes = []
        for q in quotes:
            if q["hid"] != hid:
                continue
            if "MISMATCH" in q["source"]:
                notes.append(f"Excluded: {q['source']} - {q['mapping_note']}")
                continue
            if q["source"].startswith("Polymarket"):
                vol = float(q["volume_usd"])
                p = novig_a(float(q["decimal_a"]), float(q["decimal_b"]))
                market_src = q["source_url"]
                market_vol = vol
                if vol >= LIQ_MIN_USD:
                    market_p = p
                else:
                    notes.append(f"Polymarket volume ${vol:,.2f} below ${LIQ_MIN_USD:,.0f}; shown, not used")
            else:
                if q["decimal_a"] and q["decimal_b"]:
                    agg_p = novig_a(float(q["decimal_a"]), float(q["decimal_b"]))
                    agg_src = q["source_url"]

        # 4. consensus over usable sources
        sources = []
        if own_p is not None:
            sources.append(("rank model", own_p))
        if market_p is not None:
            sources.append(("Polymarket", market_p))
        if agg_p is not None:
            sources.append(("aggregator", agg_p))

        consensus = None
        pick, basis = "No pick", ""
        if not sources:
            basis = "No usable line (no verified ranks, no liquid market)"
        else:
            consensus = sum(p for _, p in sources) / len(sources)
            favs = {(p >= 0.5) for _, p in sources}
            names = " + ".join(n for n, _ in sources)
            if len(favs) > 1:
                pick = "No pick"
                basis = f"Conflict: sources disagree on favourite ({names})"
            else:
                fav_is_a = consensus >= 0.5
                fav_team = a if fav_is_a else b
                fav_p = consensus if fav_is_a else 1 - consensus
                if fav_p < TOSS_UP:
                    pick = f"Lean {fav_team} (toss-up)"
                else:
                    pick = f"{fav_team}"
                basis = (f"Single usable source: {names}" if len(sources) == 1 else f"Agree: {names}")

        rows_out.append({
            "hid": hid,
            "start_utc": fx["start_utc_hotspawn"],
            "team_a": a,
            "team_b": b,
            "tournament": fx["tournament"],
            "tier": fx["tier"],
            "points": fx["points"],
            "hotspawn_url": fx["hotspawn_match_url"],
            "hotspawn_pick_a_pct_snapshot": fx["hotspawn_pick_a_pct_snapshot"],
            "own_p_a": own_p,
            "own_rank_a": ra,
            "own_rank_b": rb,
            "market_p_a": market_p,
            "market_volume_usd": market_vol,
            "market_url": market_src,
            "agg_p_a": agg_p,
            "agg_url": agg_src,
            "consensus_p_a": consensus,
            "pick": pick,
            "basis": basis,
            "notes": " | ".join(notes),
        })

    # picks.csv
    out_csv = os.path.join(DATA, "picks.csv")
    cols = ["hid", "start_utc", "team_a", "team_b", "tournament", "tier", "points", "hotspawn_url",
            "hotspawn_pick_a_pct_snapshot", "own_rank_a", "own_rank_b", "own_p_a", "market_p_a",
            "market_volume_usd", "market_url", "agg_p_a", "agg_url", "consensus_p_a", "pick", "basis", "notes"]
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows_out:
            w.writerow({
                **{k: r[k] for k in cols if k in r and k not in ("own_p_a", "market_p_a", "agg_p_a", "consensus_p_a")},
                "own_p_a": "" if r["own_p_a"] is None else f"{r['own_p_a']:.4f}",
                "market_p_a": "" if r["market_p_a"] is None else f"{r['market_p_a']:.4f}",
                "agg_p_a": "" if r["agg_p_a"] is None else f"{r['agg_p_a']:.4f}",
                "consensus_p_a": "" if r["consensus_p_a"] is None else f"{r['consensus_p_a']:.4f}",
                "market_volume_usd": "" if r["market_volume_usd"] is None else f"{r['market_volume_usd']:.2f}",
            })

    # summary
    picks = sum(1 for r in rows_out if r["pick"] != "No pick")
    print(f"fixtures={len(rows_out)} picks={picks} no_pick={len(rows_out) - picks}")
    for r in rows_out:
        print(f"{r['hid']} {r['team_a']} v {r['team_b']}: own={pct(r['own_p_a'])} "
              f"mkt={pct(r['market_p_a'])} agg={pct(r['agg_p_a'])} cons={pct(r['consensus_p_a'])} "
              f"-> {r['pick']} [{r['basis']}]")

    write_html(rows_out)
    return rows_out


def write_html(rows):
    def esc(x):
        return html.escape(str(x))

    def link(url, label):
        return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>' if url else ""

    body = []
    for r in rows:
        pick_cls = "pick" if r["pick"] != "No pick" else "nopick"
        own = pct(r["own_p_a"])
        mkt = pct(r["market_p_a"])
        agg = pct(r["agg_p_a"])
        cons = pct(r["consensus_p_a"])
        vol = "" if r["market_volume_usd"] is None else f"${r['market_volume_usd']:,.2f}"
        srcs = " ".join(x for x in [
            link(r["hotspawn_url"], "Hotspawn"),
            link(r["market_url"], "Polymarket"),
            link(r["agg_url"], "aggregator"),
            link("https://www.hltv.org/ranking/teams/2026/october/12", "HLTV rank") if r["own_p_a"] is not None else "",
        ] if x)
        tb = (f"{esc(r['team_a'])} ({esc(r['own_rank_a']) or '-'}) vs {esc(r['team_b'])} ({esc(r['own_rank_b']) or '-'})")
        body.append(
            f"<tr class=\"{pick_cls}\"><td>{esc(r['hid'])}</td>"
            f"<td>{esc(r['start_utc'])} UTC</td>"
            f"<td>{esc(r['tier'])} ({esc(r['points'])} pts)</td>"
            f"<td>{esc(r['tournament'])}</td>"
            f"<td>{tb}</td>"
            f"<td>{own or '—'}</td>"
            f"<td>{mkt or '—'} <small>{vol}</small></td>"
            f"<td>{agg or '—'}</td>"
            f"<td>{cons or '—'}</td>"
            f"<td><strong>{esc(r['pick'])}</strong><br><small>{esc(r['basis'])}</small></td>"
            f"<td>{esc(r['notes'])}</td>"
            f"<td>{srcs}</td></tr>"
        )
    n_pick = sum(1 for r in rows if r["pick"] != "No pick")
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Own lines and picks - Hotspawn pick'em (session 844ba68e)</title>
<link rel="stylesheet" href="style.css">
<style>
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ border-bottom:1px solid #2a2f3a; padding:6px 8px; vertical-align:top; text-align:left; }}
tr.nopick td:nth-child(10) {{ color:#b8a060; }}
tr.pick td:nth-child(10) {{ color:#6fd08c; }}
small {{ color:#9aa3b2; }}
.wrap {{ overflow-x:auto; }}
</style>
</head>
<body>
<main style="padding:24px;max-width:1400px;margin:0 auto;">
<p><a href="index.html">&larr; Dashboard</a> · <a href="flagged.html">Flagged for Review</a> · <a href="sources.html">Sources</a></p>
<h1>Own lines and picks for all 26 Hotspawn pick'em fixtures</h1>
<p>Session 844ba68e. Hotspawn pick % is shown only as a snapshot and is <strong>not</strong> used as a probability.
Rank-model line: HLTV world ranking of 2026-10-12, both teams ranked. Polymarket line: listing prices, de-vigged, used only at
≥ $1,000 volume. Aggregator line: EGW/stavka.tv bookmaker odds, de-vigged. Consensus = equal-weight mean of usable sources.
A pick is made only when all usable sources agree on the favourite. <strong>{n_pick} picks, {len(rows) - n_pick} no-pick.</strong>
Full method: <code>scripts/844ba68e_build.py</code>. Data: <code>data/844ba68e/</code>.</p>
<div class="wrap">
<table>
<thead><tr>
<th>ID</th><th>Start</th><th>Tier</th><th>Tournament</th><th>Match (HLTV rank)</th>
<th>Rank model: A %</th><th>Polymarket: A % (vol)</th><th>Aggregator: A %</th><th>Consensus: A %</th>
<th>Pick and basis</th><th>Notes / exclusions</th><th>Sources</th>
</tr></thead>
<tbody>
{chr(10).join(body)}
</tbody>
</table>
</div>
<p><small>A % = probability that team A (Hotspawn order) wins the match, de-vigged. Blank or — = no usable line. Generated {datetime.utcnow().strftime('%Y-%m-%d')} UTC by scripts/844ba68e_build.py.</small></p>
</main>
</body>
</html>
"""
    with open(os.path.join(ROOT, "docs", "own-lines.html"), "w", encoding="utf-8") as f:
        f.write(doc)


if __name__ == "__main__":
    main()
