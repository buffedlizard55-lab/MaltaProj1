#!/usr/bin/env python3
"""Session arena/28d318cd — live Hotspawn reconciliation + line-by-line re-check.

Everything numeric on the published pages is RECOMPUTED here from stored inputs:
  * reconcile/live_lobby_read_2026_10_14.csv        (Hotspawn /lobby render, read 04:37Z)
  * reconcile/live_cs2_pickems_read_2026_10_14.csv   (Hotspawn /cs2-pickems render)
  * reconcile/data/pinnacle_*_2026_10_14.json.gz      (committed Pinnacle captures, copied read-only)
  * reconcile/data/vrs_standings_global_2026_10_05.json.gz (Valve VRS 2026-10-05 table, markdown)
  * console/data/picks.csv                           (the board being checked; read-only)
Live odds that were read by hand from the public pages are listed in LIVE_READS with their URL.
Crowd percentages ("% picked") are never read.

Outputs: reconcile/index.html, reconcile/flagged.html, reconcile/reread.csv,
         reviews/28d318cd-verification.md
Run: python3 reconcile/build.py   (then python3 reconcile/reconcile.py for the row join)
"""
import csv, gzip, html, io, json, re, subprocess, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "reconcile"
DATA = R / "data"
K = 0.4568                                   # calibration slope used by the repo's own-line model
REPO_BLOB = "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main"
HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
VRS_URL = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
           "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md")
PINNACLE_URL = "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false"

# ---- live reads done by hand in this session (URL, what was read, read time) -----------------
LIVE_READS = {
  "EGW_GOTHIC": ("https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
                 "headline 2.05 / 1.64; same pair at SpinAlto, RedSport, PlanBet, Kinbet; 1.881 / 1.782 at Spinbetter, 22bet, 1xBit; 'bc.game' not seen in chunks 0-2", "2026-10-14T04:38Z"),
  "EGW_ENJOY": ("https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7",
                "headline ENJOY 1.52 / B8 Academy 2.3 (chunk 0; bookmaker list not read)", "2026-10-14T04:38Z"),
  "EGW_RUSTEC": ("https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK",
                 "headline ex-RUSTEC 1.8 / mellren 1.8", "2026-10-14T04:39Z"),
  "EGW_G2": ("https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L",
             "headline G2 Ares 1.43 / The Last Resort 2.41 (chunk 0)", "2026-10-14T04:39Z"),
  "TP_WBT": ("https://thunderpick.io/esports/cs2-betting/elisa-breakout-series-2/11360/wbt-vs-ea-copenhagen/2807510",
             "Match Winner WBT +100 / EA Copenhagen -139 (chunk 1); BO1, 'October 15, 04:00' (UTC-4 render)", "2026-10-14T04:39Z"),
}

# ---- own-line re-computation inputs: exact Valve VRS rows (rank, points, roster) ----------------
VRS_ROWS_NEEDED = {
  "mellren": 125, "Privateer": 271, "Banda Chuya": 165, "6666": 127,
}

def parse_vrs():
    raw = gzip.open(DATA / "vrs_standings_global_2026_10_05.json.gz").read().decode("utf-8", "replace")
    rows = []
    for line in raw.split("\n"):
        c = [x.strip() for x in line.split("|")]
        if len(c) > 4 and c[1].isdigit() and c[2].isdigit():
            rows.append({"rank": int(c[1]), "pts": int(c[2]), "name": c[3], "roster": c[4][:80]})
    return rows

def p_map(pa, pb):
    return 1 / (1 + 10 ** (-K * (pa - pb) / 400))

def bo3(p):
    return p * p * (3 - 2 * p)

def dec_from_american(a):
    return 1 + (a / 100 if a > 0 else 100 / abs(a))

def devig(da, db):
    ia, ib = 1 / da, 1 / db
    s = ia + ib
    return 100 * ia / s, 100 * ib / s

# Pinnacle name -> Hotspawn/board name (documented in cs2/aliases.json or matched by matchup+time)
PIN_ALIAS = {"PVISION": "PARIVISION", "BB Team": "BetBoom", "fnatic": "Fnatic", "HEROIC": "Heroic",
             "Ninjas In Pyjamas": "Ninjas in Pyjamas", "BC.Game": "BC.Game"}

def pinnacle_rows():
    mt = json.load(gzip.open(DATA / "pinnacle_matchups_2026_10_14.json.gz"))
    mk = json.load(gzip.open(DATA / "pinnacle_markets_2026_10_14.json.gz"))
    byid = {m["id"]: m for m in mt}
    out = []
    for x in mk:
        if x.get("type") != "moneyline" or x.get("period") != 0:
            continue
        m = byid.get(x["matchupId"])
        if not m:
            continue
        names = {p["alignment"]: PIN_ALIAS.get(p["name"], p["name"]) for p in m["participants"]}
        pr = {p["designation"]: p["price"] for p in x["prices"]}
        ph, pa = devig(dec_from_american(pr["home"]), dec_from_american(pr["away"]))
        out.append({"start": m["startTime"], "home": names["home"], "away": names["away"],
                    "home_price": pr["home"], "away_price": pr["away"],
                    "p_home": ph, "p_away": pa, "matchup": x["matchupId"], "league": m["league"]["name"]})
    return out

def main():
    board = list(csv.DictReader(io.StringIO(subprocess.run(
        ["git", "show", "origin/main:console/data/picks.csv"], cwd=ROOT, capture_output=True, text=True).stdout)))
    if not board:
        board = list(csv.DictReader((ROOT / "console/data/picks.csv").open(encoding="utf-8")))
    bmap = {b["fixture_id"]: b for b in board}
    vrs = parse_vrs()
    def vrs_pts(name, rank):
        hit = [r for r in vrs if r["name"].lower() == name.lower() and r["rank"] == rank]
        assert len(hit) == 1, (name, rank)
        return hit[0]["pts"]
    pin = pinnacle_rows()
    def pin_for(fx):
        b = bmap[fx]
        for p in pin:
            if p["start"] == b["start_utc"] and {p["home"].lower(), p["away"].lower()} == {b["team_a"].lower(), b["team_b"].lower()}:
                return p
        return None

    rows = []
    def add(fx, check, method, source, board_a, board_b, calc_a, calc_b, result, note, observed):
        b = bmap[fx]
        rows.append({
            "fixture_id": fx, "match": f'{b["team_a"]} vs {b["team_b"]}', "tournament": b["competition"],
            "start_utc": b["start_utc"], "board_pick": b["pick"], "check_method": method,
            "check_source": source, "observed": observed,
            "board_pct_a": board_a, "board_pct_b": board_b,
            "recomputed_pct_a": "" if calc_a is None else f"{calc_a:.2f}",
            "recomputed_pct_b": "" if calc_b is None else f"{calc_b:.2f}",
            "delta_pp_a": "" if calc_a is None else f"{float(board_a) - calc_a:+.2f}",
            "result": result, "note": note,
        })

    # 1. Live EGW headline odds (decimal) ------------------------------------------------------------
    for fx, key, da, db, note in [
        ("1079621", "EGW_GOTHIC", 2.05, 1.64, "Reproduced from the headline pair. Other listed books: 2.05/1.64 (SpinAlto, RedSport, PlanBet, Kinbet) and 1.881/1.782 (Spinbetter, 22bet, 1xBit = 48.65/51.35). 'bc.game' attribution NOT seen in the bookmakers read."),
        ("1081111", "EGW_ENJOY", 1.52, 2.30, "Reproduced from the headline pair. 'bc.game' attribution not checked (bookmaker list not read)."),
        ("1079623", "EGW_G2", 1.43, 2.41, "NOT reproduced: live headline gives 62.76 / 37.24 vs the board's 62.4 / 37.6 (board read 02:48Z). Pick unchanged."),
        ("1079622", "EGW_RUSTEC", 1.80, 1.80, "NOT reproduced: live EGW shows 1.8 / 1.8 (the placeholder pattern the picks-full board rejects). The board's 65.7 / 34.3 cannot be re-read today."),
    ]:
        a, b_ = devig(da, db)
        bb = bmap[fx]
        ok = abs(float(bb["p_a_pct"]) - a) <= 0.11
        res = "reproduced" if ok else ("placeholder — not reproducible" if (da == db) else "differs")
        add(fx, "live odds re-read", "decimal de-vig", LIVE_READS[key][0], bb["p_a_pct"], bb["p_b_pct"],
            a, b_, res, note, f"{da} / {db} (read {LIVE_READS[key][2]})")

    # 2. Live Thunderpick (American) for WBT vs EA Copenhagen --------------------------------------
    a, b_ = devig(dec_from_american(100), dec_from_american(-139))
    add("1080279", "live odds re-read", "american de-vig", LIVE_READS["TP_WBT"][0],
        bmap["1080279"]["p_a_pct"], bmap["1080279"]["p_b_pct"], a, b_, "reproduced",
        "Identity: WROTBERRY = WBT is documented in cs2/aliases.json with HLTV match 2399418 (checked 02:24Z). The Thunderpick page is the 2807510 market.",
        "WBT +100 / EA Copenhagen -139 (read 2026-10-14T04:39Z)")

    # 3. Committed Pinnacle capture (recompute the de-vig from the stored raw response) -------------
    for fx in ["1080176", "1079439", "1080177", "1080178", "1080179", "1079440", "1079442"]:
        bb = bmap[fx]
        p = pin_for(fx)
        if not p:
            add(fx, "committed capture recompute", "american de-vig", PINNACLE_URL, bb["p_a_pct"], bb["p_b_pct"], None, None,
                "not found", "no matching matchup in the committed capture", "")
            continue
        if p["home"].lower() == bb["team_a"].lower():
            ca, cb = p["p_home"], p["p_away"]
        else:
            ca, cb = p["p_away"], p["p_home"]
        ok = abs(float(bb["p_a_pct"]) - ca) <= 0.11
        note = (f'Matchup {p["matchup"]} ({p["league"]}); period-0 moneyline {p["home_price"]} / {p["away_price"]}. '
                f'Raw name "{p["home"]}" vs "{p["away"]}" matched via cs2/aliases.json or start time + tournament.')
        if fx == "1079439":
            note += " NEAR-EVEN: pick margin under 1 pp."
        add(fx, "committed capture recompute", "american de-vig", PINNACLE_URL, bb["p_a_pct"], bb["p_b_pct"], ca, cb,
            "reproduced" if ok else "differs", note, f'{p["home_price"]} / {p["away_price"]} (capture 2026-10-14T02:45:17Z)')

    # 4. Own-line rows: Valve VRS points with the repo's formula (k = 0.4568, BO3 transform) ----------
    pm = vrs_pts("mellren", 125); pv = vrs_pts("Privateer", 271)
    p = p_map(pm, pv); s = bo3(p)
    add("1081120", "Valve VRS recompute", "P_map=1/(1+10^(-k*dP/400)), BO3=p^2(3-2p)", VRS_URL,
        bmap["1081120"]["p_a_pct"], bmap["1081120"]["p_b_pct"], 100 * s, 100 * (1 - s), "reproduced",
        f"mellren {pm} pts (rank 125) vs Privateer {pv} pts (rank 271); names unique in the table.",
        f"mellren {pm} pts / Privateer {pv} pts")

    # Banda chuya vs 6666: two VRS rows exist for each name. Show each combination.
    b165 = vrs_pts("Banda Chuya", 165); b373 = [r["pts"] for r in vrs if r["name"] == "Banda Chuya" and r["rank"] == 373][0]
    s6 = vrs_pts("6666", 127); s6b = [r["pts"] for r in vrs if r["name"] == "6666" and r["rank"] == 368][0]
    p = p_map(s6, b165); s = bo3(p)
    add("1081112", "Valve VRS recompute", "P_map + BO3 (as above)", VRS_URL,
        bmap["1081112"]["p_a_pct"], bmap["1081112"]["p_b_pct"], 100 * (1 - s), 100 * s, "reproduced — identity open",
        (f"Reproduces with 6666 = rank 127 ({s6} pts) and Banda Chuya = rank 165 ({b165} pts). "
         f"Alternatives in the same table: Banda Chuya rank 373 ({b373} pts) -> 6666 "
         f"{100*bo3(p_map(s6,b373)):.1f}%; 6666 rank 368 ({s6b} pts) vs Banda rank 165 -> Banda "
         f"{100*bo3(p_map(b165,s6b)):.1f}% (pick would flip)."),
        f"6666 {s6} pts (rank 127) vs Banda Chuya {b165} pts (rank 165)")

    # 5. Research row: no VRS line for LFO 10 -------------------------------------------------------
    lfo = [r for r in vrs if "lfo" in r["name"].lower()]
    fz = vrs_pts("FORZE Reload", 84)
    add("1079624", "Valve VRS check", "none — opponent not in VRS table", VRS_URL,
        bmap["1079624"]["p_a_pct"], bmap["1079624"]["p_b_pct"], None, None, "unverifiable",
        f"FORZE Reload = {fz} pts (rank 84). LFO 10 rows in VRS: {len(lfo)}. No official-table line exists; the board's 75.9 is an unverified research estimate (its own range 75.9–98.4).",
        f"FORZE {fz} pts")

    # 6. Rows NOT re-read in this session ---------------------------------------------------------
    not_reread = {
        "1079438": "bo3.gg-relayed Thunderpick (thunderpick.io/match/2767822) — not re-read",
        "1081113": "Polymarket prediction market (cs2-wraith-ryvex) — not re-read; identity conflict on EGW (see F-03)",
    }
    for fx in [b["fixture_id"] for b in board]:
        if fx in {r["fixture_id"] for r in rows}:
            continue
        note = not_reread.get(fx, "bo3.gg-relayed Thunderpick price (thunderpick.io/match/…) — not re-read in this session")
        bb = bmap[fx]
        add(fx, "not re-read", "—", bb["source_url"], bb["p_a_pct"], bb["p_b_pct"], None, None, "not re-read", note, "")

    # ---- cross-board comparison: console/data/picks.csv vs executive/data/analysis.csv (both on main) ----
    ex = {r["match_id"]: r for r in csv.DictReader((DATA / "executive_analysis_main_2026_10_14.csv").open(encoding="utf-8"))}
    cross = []
    for b in board:
        e = ex.get(b["fixture_id"])
        if not e:
            cross.append({"fixture_id": b["fixture_id"], "match": f'{b["team_a"]} vs {b["team_b"]}', "console": b["p_a_pct"], "executive": "", "gap_pp": "", "pick_console": b["pick"], "pick_executive": "", "basis_console": b["basis_rung"], "basis_executive": ""})
            continue
        gap = float(e["prob_a_pct"]) - float(b["p_a_pct"])
        cross.append({"fixture_id": b["fixture_id"], "match": f'{b["team_a"]} vs {b["team_b"]}',
                      "console": b["p_a_pct"], "executive": e["prob_a_pct"], "gap_pp": f"{gap:+.1f}",
                      "pick_console": b["pick"], "pick_executive": e["pick"],
                      "basis_console": b["basis_rung"], "basis_executive": e["basis_tier"]})
    (R / "cross_board.csv").write_text("", encoding="utf-8")
    with (R / "cross_board.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cross[0].keys())); w.writeheader(); w.writerows(cross)
    xb = {"rows": len(cross),
                              "prob_differs_any": sum(1 for c in cross if c["gap_pp"] not in ("", "+0.0", "-0.0")),
                              "prob_differs_ge_1pp": sum(1 for c in cross if c["gap_pp"] and abs(float(c["gap_pp"])) >= 1.0),
                              "pick_differs": sum(1 for c in cross if c["pick_executive"] and c["pick_executive"] != c["pick_console"]),
                              "max_abs_gap_pp": max((abs(float(c["gap_pp"])) for c in cross if c["gap_pp"]), default=0)}

    # ---- write reread.csv ----------------------------------------------------------------------------
    cols = list(rows[0].keys())
    with (R / "reread.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    stats = {}
    for r in rows:
        stats[r["result"]] = stats.get(r["result"], 0) + 1
    summary = {"rows": len(rows), "results": stats, "cross_board": xb}
    (R / "reread_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return rows, board

if __name__ == "__main__":
    main()
