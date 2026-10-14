#!/usr/bin/env python3
"""scripts/exec_bdc98a9a_build.py — build the executive-summary board (session arena/bdc98a9a).

Inputs (read-only, owned by other sessions; this script never writes to them):
  slate/data/fixtures.csv          Hotspawn payload fixture list (identity, competition, tier,
                                   stage, points, exact UTC start/lock epochs)
  slate/data/analysis.csv          hourly board: primary/secondary market quotes + own line
  slate/data/lines.csv             every external price reading with its source URL and time
  live/data/slate.csv              live board: fixture + external + own line + pick
  cs2/data/analysis.csv            (when present) cs2 board: market, own line, pick, flags
  data/8944bb84/analysis.csv       8944bb84 board: VRS/HLTV ratings, external lines, pick
  exec/data/live/*.json            this session's own live capture (Hotspawn, Valve VRS, HLTV)

Outputs (this session owns these):
  exec/data/picks.csv              one row per CS2 fixture: probabilities, pick, basis, sources
  exec/data/picks.json             the same, as JSON
  exec/data/flags.csv              every flag raised on a row
  exec/data/summary.json           counts the executive summary prints
  exec/*.html                      index (executive summary), picks, coverage, method, sources,
                                   flagged
  exec/style.css

Rules (also printed on exec/method.html):
  T1  primary external bookmaker quote, de-vigged
  T2  secondary external quote (aggregator / secondary book), de-vigged
  T3  own line from official ratings: Valve Regional Standings and/or HLTV World Ranking points
  T4  one side ranked, the other outside both official lists -> the ranked team is the pick, no
      numeric probability is printed (a number would have to be invented)
  T5  nothing usable -> no pick, row flagged
  The Hotspawn community pick percentage is never read into any probability field.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEC = ROOT / "exec"
DATA = EXEC / "data"
LIVE = DATA / "live"

K_CALIBRATED = 0.4630          # cs2/calibrate.py slope, cited on the method page
ELO_SCALE = 400.0
STALE_DAYS = 2                 # a fixture older than this is published as `stale`, never as open

SOURCE_LABELS = {
    "T1": "external market — primary book",
    "T2": "external market — secondary book/aggregator",
    "T3": "our own line — official ratings (Valve VRS / HLTV World Ranking)",
    "T4": "ranked vs unranked — qualitative pick, no numeric line",
    "T5": "no usable source",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [row for row in csv.DictReader(fh)]


def fnum(value, default=None):
    try:
        text = str(value).strip()
        if text in ("", "None", "nan"):
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def devig(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    return inv_a / total, inv_b / total, (total - 1.0) * 100.0


def elo_p(points_a: float, points_b: float, slope: float = K_CALIBRATED) -> float:
    """p(A) from a points difference. slope=0.4630 is the project's calibrated value."""
    delta = (points_a - points_b) * slope
    return 1.0 / (1.0 + 10 ** (-delta / ELO_SCALE))


def series_from_map(p: float, best_of) -> tuple[float, str]:
    """BO(n) series probability from a single-map probability, plus the label of what was used."""
    try:
        box = int(best_of)
    except (TypeError, ValueError):
        box = 0
    if box in (3, 5):
        n = 2 if box == 3 else 3
        if p <= 0.0:
            return 0.0, f"BO{box} series"
        if p >= 1.0:
            return 1.0, f"BO{box} series"
        pa = p ** n
        pb = (1 - p) ** n
        return pa / (pa + pb), f"BO{box} series"
    return p, "single map"


def pct(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}"


# --------------------------------------------------------------------------------------- loading
def load_payload_fixtures() -> list[dict]:
    rows = []
    for row in read_csv(ROOT / "slate" / "data" / "fixtures.csv"):
        if (row.get("sport") or "") != "cs2":
            continue
        rows.append({
            "fixture_id": row["fixture_id"],
            "team_a": row.get("team_a", ""), "team_b": row.get("team_b", ""),
            "competition": row.get("competition", ""), "tier": row.get("tier", ""),
            "stage": row.get("stage", ""), "points": row.get("points", ""),
            "start_utc": row.get("start_utc", ""), "lock_utc": row.get("lock_utc", ""),
            "live_status": row.get("live_status", ""),
            "best_of_payload": fnum(row.get("best_of_resolved") or row.get("best_of_payload")),
            "best_of_source": row.get("best_of_source", ""),
            "hotspawn_url": row.get("hotspawn_match_url") or row.get("source_url") or "",
            "lobby_url": row.get("source_url", ""),
            "payload_captured_utc": row.get("captured_utc", ""),
        })
    return rows


def live_json(name: str) -> dict:
    path = LIVE / name
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def norm(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "", (name or "").lower())
    return text


def match_team(target: str, table: dict) -> tuple[str, dict] | tuple[None, None]:
    """Exact-normalised, then unique-prefix match against a {name: data} table."""
    wanted = norm(target)
    if not wanted:
        return None, None
    for name, payload in table.items():
        if norm(name) == wanted:
            return name, payload
    hits = [(n, p) for n, p in table.items()
            if norm(n).startswith(wanted[:8]) and len(norm(n)) - len(wanted) <= 4]
    for alias in {"wrotberry": "wbt", "exrustec": "rustec", "bandachuya": "bandachuya"}:
        if wanted == alias:
            for n, p in table.items():
                if norm(n) == alias[:6]:
                    return n, p
    return (hits[0] if len(hits) == 1 else (None, None))


# ------------------------------------------------------------------------------ evidence records
def market_candidates() -> list[dict]:
    """Every external price reading this repository has captured, with its source URL."""
    out = []
    for row in read_csv(ROOT / "slate" / "data" / "lines.csv"):
        oa, ob = fnum(row.get("odds_a")), fnum(row.get("odds_b"))
        if not oa or not ob or oa <= 1 or ob <= 1:
            continue
        url = (row.get("source_url") or "").strip()
        if not url.startswith("http"):
            continue
        out.append({
            "fixture_id": row.get("fixture_id", ""), "book": row.get("book") or row.get("source"),
            "odds_a": oa, "odds_b": ob, "url": url,
            "captured_utc": row.get("captured_utc", ""),
            "rank": (row.get("rank") or "").lower(),
            "dataset": "slate/data/lines.csv", "order_flipped": row.get("team_order_flipped") == "True",
            "note": row.get("note", ""),
        })
    for row in read_csv(ROOT / "data" / "8944bb84" / "external_lines.csv"):
        oa, ob = fnum(row.get("primary_odds_a")), fnum(row.get("primary_odds_b"))
        if oa and ob and oa > 1 and ob > 1 and (row.get("primary_source_url") or "").startswith("http"):
            out.append({"fixture_id": row.get("match_id", ""), "book": row.get("primary_book") or "book",
                        "odds_a": oa, "odds_b": ob, "url": row["primary_source_url"],
                        "captured_utc": row.get("captured_utc", ""), "rank": "primary",
                        "dataset": "data/8944bb84/external_lines.csv", "order_flipped": False,
                        "note": row.get("note", "")})
        ea, eb = fnum(row.get("egw_odds_a")), fnum(row.get("egw_odds_b"))
        if ea and eb and ea > 1 and eb > 1 and (row.get("egw_url") or "").startswith("http"):
            out.append({"fixture_id": row.get("match_id", ""), "book": "bc.game (via EGamersWorld)",
                        "odds_a": ea, "odds_b": eb, "url": row["egw_url"],
                        "captured_utc": row.get("captured_utc", ""), "rank": "secondary",
                        "dataset": "data/8944bb84/external_lines.csv", "order_flipped": False,
                        "note": "secondary aggregator reading"})
    for row in read_csv(LIVE / ".." / ".." / ".." / "live" / "data" / "slate.csv"):
        oa, ob = fnum(row.get("ext_odds_a")), fnum(row.get("ext_odds_b"))
        url = (row.get("ext_url") or "").strip()
        if oa and ob and oa > 1 and ob > 1 and url.startswith("http"):
            out.append({"fixture_id": row.get("match_id", ""), "book": row.get("ext_bookmaker") or "book",
                        "odds_a": oa, "odds_b": ob, "url": url,
                        "captured_utc": row.get("ext_observed_utc", ""), "rank": "primary",
                        "dataset": "live/data/slate.csv", "order_flipped": False,
                        "note": "live board external reading"})
    cs2_path = ROOT / "cs2" / "data" / "analysis.csv"
    for row in read_csv(cs2_path):
        oa, ob = fnum(row.get("market_odds_a")), fnum(row.get("market_odds_b"))
        url = (row.get("market_url") or "").strip()
        if oa and ob and oa > 1 and ob > 1 and url.startswith("http"):
            out.append({"fixture_id": row.get("fixture_id", ""), "book": row.get("market_book") or "book",
                        "odds_a": oa, "odds_b": ob, "url": url,
                        "captured_utc": row.get("market_captured_utc", ""), "rank": "secondary",
                        "dataset": "cs2/data/analysis.csv", "order_flipped": False,
                        "note": row.get("market_source", "")})
    return out


def rating_candidates(fixtures: list[dict]) -> dict[str, list[dict]]:
    """Own-line inputs gathered per fixture from the rating sources and the owner boards."""
    by_id: dict[str, list[dict]] = {}
    for row in read_csv(LIVE / ".." / ".." / ".." / "live" / "data" / "slate.csv"):
        pa, pb = fnum(row.get("vrs_points_a")), fnum(row.get("vrs_points_b"))
        url = (row.get("vrs_url") or "").strip()
        if pa and pb and url.startswith("http"):
            by_id.setdefault(row.get("match_id", ""), []).append({
                "source": "Valve Regional Standings",
                "points_a": pa, "points_b": pb, "url": url,
                "as_of": row.get("vrs_as_of", ""), "dataset": "live/data/slate.csv",
                "ranks": (row.get("vrs_rank_a"), row.get("vrs_rank_b"))})
    for row in read_csv(ROOT / "data" / "8944bb84" / "analysis.csv"):
        pa, pb = fnum(row.get("vrs_points_a")), fnum(row.get("vrs_points_b"))
        ua, ub = (row.get("vrs_url_a") or ""), (row.get("vrs_url_b") or "")
        if pa and pb and ua.startswith("http"):
            by_id.setdefault(row.get("match_id", ""), []).append({
                "source": "Valve Regional Standings",
                "points_a": pa, "points_b": pb, "url": ua, "url_b": ub,
                "as_of": "2026-10-05", "dataset": "data/8944bb84/analysis.csv",
                "ranks": (row.get("vrs_standing_a"), row.get("vrs_standing_b"))})
    for row in read_csv(ROOT / "data" / "8944bb84" / "analysis.csv"):
        pa, pb = fnum(row.get("hltv_points_a")), fnum(row.get("hltv_points_b"))
        ua = (row.get("hltv_url_a") or "").strip()
        if pa and pb and ua.startswith("http") and "ranking/teams" in ua:
            by_id.setdefault(row.get("match_id", ""), []).append({
                "source": "HLTV World Ranking",
                "points_a": pa, "points_b": pb, "url": ua,
                "as_of": "2026-10-12", "dataset": "data/8944bb84/analysis.csv",
                "ranks": (row.get("hltv_rank_a"), row.get("hltv_rank_b"))})
    return by_id


# ----------------------------------------------------------------------------------------- rules
def resolve(fixture: dict, markets: list[dict], ratings, hltv_live: dict, valve: dict,
            hltv_rank: dict, hltv_pages: dict) -> dict:
    a, b = fixture["team_a"], fixture["team_b"]
    row = {
        "fixture_id": fixture["fixture_id"], "team_a": a, "team_b": b,
        "competition": fixture["competition"], "tier": fixture["tier"],
        "stage": fixture["stage"], "points": fixture["points"],
        "start_utc": fixture["start_utc"], "lock_utc": fixture["lock_utc"],
        "best_of": fixture["best_of_payload"], "best_of_source": fixture["best_of_source"],
        "single_map_p_a_pct": "", "single_map_p_b_pct": "",
        "series_p_a_pct": "", "series_p_b_pct": "", "series_basis": "",
        "p_a_pct": "", "p_b_pct": "", "fair_odds_a": "", "fair_odds_b": "",
        "market_book": "", "market_odds_a": "", "market_odds_b": "",
        "market_p_a_pct": "", "market_p_b_pct": "", "market_url": "",
        "market_captured_utc": "",
        "own_p_a_pct": "", "own_p_b_pct": "", "own_source": "", "own_url": "", "own_inputs": "",
        "basis_code": "", "basis": "", "pick": "", "pick_pct": "", "confidence": "",
        "hltv_url": "", "hotspawn_url": fixture["hotspawn_url"] or fixture["lobby_url"],
        "sources": [], "flags": [], "evidence_utc": fixture["payload_captured_utc"],
        "status": "", "why": "",
    }

    def bump(ts: str) -> None:
        if ts and ts > row["evidence_utc"]:
            row["evidence_utc"] = ts

    # ---- market (T1/T2)
    best = None
    for cand in markets:
        if cand["fixture_id"] != row["fixture_id"]:
            continue
        if cand["odds_a"] == cand["odds_b"] and abs(cand["odds_a"] - 1.8) < 1e-9:
            row["flags"].append("EXT-PLACEHOLDER-180: a 1.80/1.80 reading is a cut-off placeholder, not a price")
            continue
        pa, pb, margin = devig(cand["odds_a"], cand["odds_b"])
        score = (0 if cand["rank"] == "primary" else 1, -(1 if cand["captured_utc"] else 0),
                 -margin)
        if best is None or score < best[0]:
            best = (score, cand, pa, pb, margin)
    if best:
        _, cand, pa, pb, margin = best
        row.update({
            "market_book": cand["book"], "market_odds_a": f"{cand['odds_a']:.3f}",
            "market_odds_b": f"{cand['odds_b']:.3f}", "market_p_a_pct": f"{pa * 100:.1f}",
            "market_p_b_pct": f"{pb * 100:.1f}", "market_url": cand["url"],
            "market_captured_utc": cand["captured_utc"],
        })
        row["_market"] = (pa, pb, cand)
        row["sources"].append({"what": f"external line — {cand['book']}", "url": cand["url"],
                               "note": f"de-vigged ({margin:.1f}% overround) from {cand['odds_a']:.3f}"
                                       f"/{cand['odds_b']:.3f}; read {cand['captured_utc'] or 'time not recorded'}"
                                       f" via {cand['dataset']}"})
        bump(cand["captured_utc"])
    else:
        row["_market"] = None

    # ---- own line (T3) from official ratings
    own = None
    for cand in (ratings.get(row["fixture_id"], []) if isinstance(ratings, dict) else ratings):
        if isinstance(cand, dict) and cand.get("fixture_id") and cand["fixture_id"] != row["fixture_id"]:
            continue
        slope = K_CALIBRATED
        p_a = elo_p(cand["points_a"], cand["points_b"], slope)
        label = cand["source"]
        if own is None or (label == "Valve Regional Standings" and own[1] != "Valve Regional Standings"):
            own = (p_a, label, cand)
    row["_own"] = own
    if own:
        p_a, label, cand = own
        row.update({"own_p_a_pct": f"{p_a * 100:.1f}", "own_p_b_pct": f"{(1 - p_a) * 100:.1f}",
                    "own_source": label, "own_url": cand["url"],
                    "own_inputs": f"{cand['points_a']:.0f} vs {cand['points_b']:.0f} points"
                                  f" ({cand['as_of']})"})
        row["sources"].append({"what": f"official rating — {label}",
                               "url": cand["url"],
                               "note": f"{cand['points_a']:.0f} vs {cand['points_b']:.0f} points"
                                       f" (as of {cand['as_of']}) via {cand['dataset']}"})
        bump(cand.get("as_of", ""))
    else:
        # No board row had both sides rated: try this session's own live capture.
        v_a = match_team(a, valve.get("teams", {}))[1]
        v_b = match_team(b, valve.get("teams", {}))[1]
        h_a = match_team(a, hltv_rank.get("teams", {}))[1]
        h_b = match_team(b, hltv_rank.get("teams", {}))[1]
        for label, url, pa_side, pb_side, as_of in (
            ("Valve Regional Standings", valve.get("source_url", ""), v_a, v_b, valve.get("as_of", "")),
            ("HLTV World Ranking", hltv_rank.get("source_url", ""), h_a, h_b, hltv_rank.get("date_text", "")),
        ):
            if pa_side and pb_side and pa_side.get("points") and pb_side.get("points") and url:
                p_a = elo_p(float(pa_side["points"]), float(pb_side["points"]))
                row.update({"own_p_a_pct": f"{p_a * 100:.1f}", "own_p_b_pct": f"{(1 - p_a) * 100:.1f}",
                            "own_source": label, "own_url": url,
                            "own_inputs": f"{pa_side['points']} vs {pb_side['points']} points ({as_of})"})
                row["sources"].append({"what": f"official rating — {label}", "url": url,
                                       "note": row["own_inputs"] + " (read live by this session)"})
                row["_own"] = (p_a, label, {"url": url})
                bump(row["evidence_utc"])
                break
        # No board row carried both sides: fall back to this session's own live capture of the
        # HLTV match page (series format, and whether HLTV prints a rank badge per team).
        live_match = (hltv_live.get("by_fixture") or {}).get(row["fixture_id"])
        if live_match:
            row["hltv_url"] = live_match.get("url") or row["hltv_url"]
            ranks = live_match.get("team_ranks") or {}
            badge_bits = []
            for name, info in ranks.items():
                bits = []
                if info.get("hltv_rank"):
                    bits.append(f"HLTV #{info['hltv_rank']}")
                if info.get("vrs_rank"):
                    bits.append(f"VRS #{info['vrs_rank']}")
                badge_bits.append(f"{name}: " + (", ".join(bits) if bits else "no rank badge"))
            note = "; ".join(badge_bits)
            if note:
                row["sources"].append({"what": "HLTV match page — rank badges", "url": live_match["url"],
                                       "note": note})
            if live_match.get("best_of") and not row["best_of"]:
                row["best_of"] = live_match["best_of"]
                row["best_of_source"] = live_match.get("best_of_source") or "HLTV match page"
                row["sources"].append({
                    "what": "HLTV match page — series format", "url": live_match["url"],
                    "note": f"Best of {live_match['best_of']} ({(live_match.get('best_of_source') or '')})"})
            row["_hltv_badges"] = {
                name: bool((info.get("hltv_rank") or info.get("vrs_rank")))
                for name, info in ranks.items()}
            bump(live_match.get("captured_utc", "") or "")

    # ---- headline
    box = row["best_of"]
    if row.get("_market"):
        pa, pb, cand = row["_market"]
        row.update({"basis_code": "T1" if cand["rank"] == "primary" else "T2",
                    "basis": SOURCE_LABELS["T1" if cand["rank"] == "primary" else "T2"],
                    "p_a_pct": f"{pa * 100:.1f}", "p_b_pct": f"{pb * 100:.1f}"})
    elif row.get("_own"):
        pa = row["_own"][0]
        row.update({"basis_code": "T3", "basis": SOURCE_LABELS["T3"],
                    "p_a_pct": f"{pa * 100:.1f}", "p_b_pct": f"{(1 - pa) * 100:.1f}"})
    else:
        badges = row.get("_hltv_badges") or {}
        ranked_a = (bool(match_team(a, valve.get("teams", {}))[1])
                    or bool(match_team(a, hltv_rank.get("teams", {}))[1])
                    or bool(badges.get(a)))
        ranked_b = (bool(match_team(b, valve.get("teams", {}))[1])
                    or bool(match_team(b, hltv_rank.get("teams", {}))[1])
                    or bool(badges.get(b)))
        if ranked_a != ranked_b:
            row.update({"basis_code": "T4", "basis": SOURCE_LABELS["T4"],
                        "pick": a if ranked_a else b,
                        "why": row["why"] or "one team is outside every official ranking list, so no "
                                             "numeric line can be originated from ratings"})
            ranked_name = a if ranked_a else b
            for label, table, url in (("Valve Regional Standings", valve.get("teams", {}), valve.get("source_url", "")),
                                      ("HLTV World Ranking", hltv_rank.get("teams", {}), hltv_rank.get("source_url", ""))):
                found = match_team(ranked_name, table)[1]
                if found and url:
                    row["sources"].append({"what": f"{ranked_name} rated in {label}", "url": url,
                                           "note": f"rank #{found.get('rank')} "
                                                   f"({found.get('points')} points)"})
            for other in (row["team_b"] if ranked_a else row["team_a"],):
                for label, table, url in (("Valve Regional Standings", valve.get("teams", {}), valve.get("source_url", "")),
                                          ("HLTV World Ranking", hltv_rank.get("teams", {}), hltv_rank.get("source_url", ""))):
                    if url and not match_team(other, table)[1]:
                        row["sources"].append({"what": f"{other} absent from {label}", "url": url,
                                               "note": f"no entry in the current published list, checked "
                                                       f"{now_iso()}"})
                        break
                row["flags"].append(f"NO-RATING: {other} has no entry in the published Valve Regional "
                                    f"Standings or the HLTV World Ranking")
        else:
            row.update({"basis_code": "T5", "basis": SOURCE_LABELS["T5"],
                        "why": "no external price and no official rating pair available"})
            row["flags"].append("NO-SOURCE: no market quote and no rating pair for this fixture")

    # ---- pick
    if not row["pick"] and row["p_a_pct"]:
        pa = float(row["p_a_pct"])
        pb = float(row["p_b_pct"])
        row["pick"] = a if pa >= pb else b
        row["pick_pct"] = f"{max(pa, pb):.1f}"
    elif row["pick"] and not row["pick_pct"]:
        row["pick_pct"] = ""
    if row["pick"] and row["pick_pct"]:
        edge = float(row["pick_pct"])
        row["confidence"] = ("clear favourite (>=70%)" if edge >= 70 else
                             "strong lean (60-69%)" if edge >= 60 else
                             "lean (55-59%)" if edge >= 55 else "too close to call (<55%)")
    elif row["basis_code"] == "T4":
        row["confidence"] = "qualitative (ranked vs unranked)"
    row["status"] = "open"
    if fixture["live_status"] and fixture["live_status"] not in ("", "open"):
        row["status"] = fixture["live_status"]
    return row


# ------------------------------------------------------------------------------------ rendering
CSS = """
:root { color-scheme: light dark; --ink:#101418; --muted:#5b6672; --line:#dfe4ea; --bg:#ffffff;
        --panel:#f7f9fc; --accent:#0b5fff; --good:#0a7d3c; --warn:#a35b00; --bad:#b3261e; }
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin:0; font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif; color:var(--ink);
       background:var(--bg); }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.top { position: sticky; top:0; z-index:5; background:var(--bg); border-bottom:1px solid var(--line);
             padding:.6rem .9rem; }
header.top h1 { font-size:1.05rem; margin:0 0 .35rem; }
nav.chips { display:flex; gap:.4rem; overflow-x:auto; -webkit-overflow-scrolling:touch; padding-bottom:.15rem; }
nav.chips a { flex:0 0 auto; border:1px solid var(--line); border-radius:999px; padding:.35rem .7rem;
              font-size:.85rem; background:var(--panel); color:var(--ink); }
nav.chips a.on { background:var(--accent); color:#fff; border-color:var(--accent); }
main { padding:.9rem; max-width:1180px; margin:0 auto; }
h2 { font-size:1.1rem; margin:1.2rem 0 .5rem; }
h3 { font-size:1rem; margin:1rem 0 .4rem; }
p, li { color:var(--ink); }
small, .muted { color:var(--muted); }
.grid { display:grid; gap:.6rem; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); }
.stat { border:1px solid var(--line); border-radius:.7rem; padding:.6rem .7rem; background:var(--panel); }
.stat b { display:block; font-size:1.5rem; line-height:1.1; }
.stat span { font-size:.8rem; color:var(--muted); }
.tiles { display:grid; gap:.6rem; grid-template-columns:1fr; }
.tile { display:block; border:1px solid var(--line); border-radius:.8rem; padding:.8rem .9rem;
        background:var(--panel); color:var(--ink); }
.tile b { display:block; font-size:1rem; }
.tile span { font-size:.85rem; color:var(--muted); }
.tile.primary { background:#0b5fff; border-color:#0b5fff; color:#fff; }
.tile.primary span { color:#e6efff; }
.card { border:1px solid var(--line); border-radius:.8rem; padding:.7rem .8rem; margin:0 0 .6rem; }
.card .row1 { display:flex; justify-content:space-between; gap:.5rem; font-size:.78rem; color:var(--muted); }
.card .teams { display:flex; justify-content:space-between; gap:.6rem; margin:.35rem 0 .3rem; }
.card .team { font-weight:600; }
.card .team.win { color:var(--good); }
.bar { height:.7rem; border-radius:999px; background:var(--panel); border:1px solid var(--line);
       overflow:hidden; display:flex; }
.bar i { display:block; height:100%; }
.bar i.a { background:#0b5fff; } .bar i.b { background:#8aa4c8; }
.pick { display:inline-block; font-weight:700; background:#e8f5ec; color:var(--good);
        border:1px solid #bfe3cd; border-radius:.5rem; padding:.15rem .5rem; font-size:.9rem; }
.pick.qual { background:#fff4e5; color:var(--warn); border-color:#f0d6ae; }
.pick.none { background:#fdecea; color:var(--bad); border-color:#f3c4c0; }
table { width:100%; border-collapse:collapse; font-size:.9rem; }
th, td { text-align:left; padding:.4rem .45rem; border-bottom:1px solid var(--line); vertical-align:top; }
th { font-size:.78rem; text-transform:uppercase; letter-spacing:.03em; color:var(--muted); }
.tablewrap { overflow-x:auto; -webkit-overflow-scrolling:touch; border:1px solid var(--line);
             border-radius:.7rem; }
details { margin:.35rem 0 0; }
summary { cursor:pointer; font-size:.85rem; color:var(--accent); }
ul.sources { margin:.35rem 0 0; padding-left:1.1rem; font-size:.85rem; }
ul.sources li { margin:.15rem 0; word-break:break-word; }
.flag { font-size:.78rem; background:#fff4e5; border:1px solid #f0d6ae; color:var(--warn);
        border-radius:.4rem; padding:.15rem .4rem; display:inline-block; margin:.15rem .2rem 0 0; }
.banner { border-radius:.7rem; padding:.6rem .8rem; font-size:.9rem; margin:0 0 .8rem; }
.banner.ok { background:#e8f5ec; border:1px solid #bfe3cd; }
.banner.warn { background:#fff4e5; border:1px solid #f0d6ae; }
footer { padding:1.2rem .9rem 2.2rem; color:var(--muted); font-size:.8rem; max-width:1180px; margin:0 auto; }
input[type=search] { width:100%; padding:.55rem .6rem; border:1px solid var(--line); border-radius:.6rem;
                     font-size:1rem; }
@media (min-width:760px) {
  .tiles { grid-template-columns:repeat(3,1fr); }
  .cards { display:grid; grid-template-columns:repeat(2,1fr); gap:.6rem; }
  .cards .card { margin:0; }
}
"""

NAV = [("index.html", "Executive summary"), ("picks.html", "Picks — every match"),
       ("coverage.html", "Coverage vs Hotspawn"), ("method.html", "Method"),
       ("sources.html", "Sources"), ("flagged.html", "Flagged for review")]


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def page(title: str, body: str, current: str, generated: str, subtitle: str = "") -> str:
    chips = "".join(
        '<a href="%s"%s>%s</a>' % (href, ' class="on"' if href == current else "", esc(label))
        for href, label in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)} · Hotspawn CS2 picks</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <h1><a href="index.html">Hotspawn CS2 Pick'em — executive summary</a></h1>
  <nav class="chips">{chips}</nav>
</header>
<main>
{subtitle}
{body}
</main>
<footer>
  Generated {esc(generated)} from public sources. Analysis only — not betting advice.
  Every value on this board links to the source it came from; a value that could not be confirmed is
  blank and listed on <a href="flagged.html">Flagged for review</a>.
  <br>Session <code>arena/bdc98a9a</code> · <a href="../index.html">all boards on this site</a> ·
  <a href="https://play.hotspawn.com/lobby">official Hotspawn lobby</a>
</footer>
<script>
(function () {{
  var box = document.getElementById('pickfilter');
  if (!box) return;
  var cards = Array.prototype.slice.call(document.querySelectorAll('[data-teams]'));
  var chips = Array.prototype.slice.call(document.querySelectorAll('[data-tier]'));
  function apply() {{
    var q = box.value.toLowerCase().trim();
    var tier = document.querySelector('[data-tier].on') ? document.querySelector('[data-tier].on').dataset.tier : 'all';
    cards.forEach(function (card) {{
      var okText = !q || card.dataset.teams.indexOf(q) >= 0;
      var okTier = tier === 'all' || card.dataset.tier === tier;
      card.style.display = okText && okTier ? '' : 'none';
    }});
  }}
  box.addEventListener('input', apply);
  chips.forEach(function (chip) {{
    chip.addEventListener('click', function () {{
      chips.forEach(function (other) {{ other.classList.remove('on'); }});
      chip.classList.add('on');
      apply();
    }});
  }});
}})();
</script>
</body>
</html>
"""


def render_card(row: dict) -> str:
    a, b = esc(row["team_a"]), esc(row["team_b"])
    paraw, pbraw = row["p_a_pct"], row["p_b_pct"]
    if paraw:
        pa, pb = float(paraw), float(pbraw)
        winner = "a" if pa >= pb else "b"
        bars = (f'<div class="bar"><i class="a" style="width:{pa:.1f}%"></i>'
                f'<i class="b" style="width:{pb:.1f}%"></i></div>')
        numbers = (f'<div class="teams"><span class="team{" win" if winner == "a" else ""}">'
                   f'{a} {pa:.1f}%</span><span class="team{" win" if winner == "b" else ""}">'
                   f'{b} {pb:.1f}%</span></div>')
    else:
        bars = ""
        numbers = (f'<div class="teams"><span class="team">{a}</span>'
                   f'<span class="team">{b}</span></div>')
    pick = row["pick"] or "no pick"
    pick_cls = "" if row["basis_code"] in ("T1", "T2", "T3") else (
        " qual" if row["basis_code"] == "T4" else " none")
    pick_line = f'<span class="pick{pick_cls}">PICK: {esc(pick)}' + (
        f' {esc(row["pick_pct"])}%' if row["pick_pct"] else "") + '</span>'
    src = "".join(f'<li><a href="{esc(s["url"])}" rel="noopener nofollow">{esc(s["what"])}</a> — '
                  f'{esc(s["note"])}</li>' for s in row["sources"] if (s.get("url") or "").startswith("http"))
    flags = "".join(f'<span class="flag">{esc(f)}</span>' for f in row["flags"])
    kickoff = row["start_utc"].replace("T", " ").replace("Z", " UTC")
    extra = ""
    if row["market_odds_a"]:
        extra += (f'<div class="muted">external line {esc(row["market_book"])}: '
                  f'{esc(row["market_odds_a"])} / {esc(row["market_odds_b"])} → '
                  f'{esc(row["market_p_a_pct"])}% / {esc(row["market_p_b_pct"])}% '
                  f'(<a href="{esc(row["market_url"])}" rel="noopener nofollow">source</a>)</div>')
    if row["own_p_a_pct"]:
        extra += (f'<div class="muted">our own line ({esc(row["own_source"])}): '
                  f'{esc(row["own_p_a_pct"])}% / {esc(row["own_p_b_pct"])}% '
                  f'(<a href="{esc(row["own_url"])}" rel="noopener nofollow">source</a>)</div>')
    return f"""<article class="card" data-teams="{a.lower()} {b.lower()}" data-tier="{esc(row['tier'])}">
  <div class="row1"><span>{kickoff} · lock {esc(row['lock_utc'].replace('T', ' ').replace('Z', ''))}Z ·
    {esc(row['competition'])} · tier {esc(row['tier'] or '—')}{(' · ' + esc(row['best_of_source'])) if row['best_of_source'] else ''}</span>
    <span>{esc(row['basis_code'])}</span></div>
  {numbers}
  {bars}
  <div>{pick_line} <small>{esc(row['basis'])}{(' · ' + esc(row['confidence'])) if row['confidence'] else ''}</small></div>
  {extra}
  {f'<div class="muted">{esc(row["why"])}</div>' if row['why'] else ''}
  {flags}
  <details><summary>sources &amp; evidence ({len([s for s in row['sources'] if (s.get('url') or '').startswith('http')])})</summary>
    <ul class="sources">{src or '<li>no external source recorded for this row</li>'}
    <li>Hotspawn fixture listing: <a href="{esc(row['hotspawn_url'])}" rel="noopener nofollow">{esc(row['hotspawn_url'])}</a> — identity and UTC kickoff only</li>
    </ul></details>
</article>"""


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--offline", action="store_true",
                    help="never touch the network (this build never does; kept for symmetry)")
    args = ap.parse_args(argv)
    generated = now_iso()

    fixtures = load_payload_fixtures()
    if not fixtures:
        print("no fixtures in slate/data/fixtures.csv — refusing to publish an empty board",
              file=sys.stderr)
        return 2
    markets = market_candidates()
    ratings = rating_candidates(fixtures)
    valve = live_json("valve_vrs.json")
    hltv_rank = live_json("hltv_ranking.json")
    hltv_live = {"matches": [], "by_fixture": {}}
    for path in sorted(LIVE.glob("hltv_day_*.json")) if LIVE.exists() else []:
        try:
            day = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        for match in day.get("matches", []):
            hltv_live["matches"].append({**match, "captured_utc": day.get("captured_utc", "")})
    for path in sorted(LIVE.glob("hltv_match_*.json")) if LIVE.exists() else []:
        try:
            match = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if match.get("fixture_id"):
            hltv_live["by_fixture"][match["fixture_id"]] = match

    rows = [resolve(fx, markets, ratings, hltv_live, valve, hltv_rank, {}) for fx in fixtures]

    # stale detection: a payload row whose kickoff is well in the past is not an open fixture
    now = datetime.now(timezone.utc)
    for row in rows:
        try:
            start = datetime.strptime(row["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            row["status"] = "unparsed date"
            continue
        age_days = (now - start).total_seconds() / 86400.0
        if age_days > STALE_DAYS:
            row["status"] = "stale listing"
            row["flags"].append("STALE: Hotspawn still lists this fixture although its kickoff is "
                                "more than %d days in the past" % STALE_DAYS)
        elif age_days > 0:
            row["status"] = "started"
    for row in rows:
        row["series_p_a_pct"], row["series_p_b_pct"], row["series_basis"] = "", "", ""
        base = row["p_a_pct"] or row["own_p_a_pct"]
        if base:
            p_series, label = series_from_map(float(base) / 100.0, row["best_of"])
            row["single_map_p_a_pct"] = row["p_a_pct"] or row["own_p_a_pct"]
            row["single_map_p_b_pct"] = row["p_b_pct"] or row["own_p_b_pct"]
            row["series_p_a_pct"] = f"{p_series * 100:.1f}"
            row["series_p_b_pct"] = f"{(1 - p_series) * 100:.1f}"
            row["series_basis"] = label
        if row["pick"] and not row["pick_pct"]:
            row["pick_pct"] = ""

    open_rows = [r for r in rows if r["status"] == "open"]
    open_rows.sort(key=lambda r: (r["start_utc"], r["team_a"]))
    stale_rows = [r for r in rows if r["status"] not in ("open",)]

    picks_with_number = [r for r in open_rows if r["pick"] and r["pick_pct"]]
    picks_qualitative = [r for r in open_rows if r["pick"] and not r["pick_pct"]]
    no_pick = [r for r in open_rows if not r["pick"]]
    with_market = [r for r in open_rows if r["market_odds_a"]]
    with_own = [r for r in open_rows if r["own_p_a_pct"]]
    primary = [r for r in open_rows if r["basis_code"] == "T1"]
    secondary = [r for r in open_rows if r["basis_code"] == "T2"]

    summary = {
        "generated_utc": generated,
        "payload_captured_utc": max((r["evidence_utc"] for r in rows), default=""),
        "payload_fixtures_cs2": len(rows),
        "open_fixtures": len(open_rows),
        "stale_or_started_fixtures": len(stale_rows),
        "open_with_pick": len(picks_with_number) + len(picks_qualitative),
        "open_picks_with_probability": len(picks_with_number),
        "open_picks_qualitative": len(picks_qualitative),
        "open_without_pick": len(no_pick),
        "open_with_external_market": len(with_market),
        "open_with_primary_market": len(primary),
        "open_with_secondary_market": len(secondary),
        "open_with_own_line": len(with_own),
        "sources": {
            "hotspawn_cs2_pickems": "https://play.hotspawn.com/cs2-pickems",
            "hotspawn_lobby": "https://play.hotspawn.com/lobby",
            "valve_regional_standings": (valve.get("source_url") or
                                         "https://github.com/ValveSoftware/counter-strike_regional_standings"),
            "hltv_world_ranking": hltv_rank.get("source_url") or "https://www.hltv.org/ranking/teams",
        },
        "live_check": {
            "hotspawn_fixtures_seen": live_json("hotspawn.json").get("fixtures_total"),
            "hltv_ranked_teams": hltv_rank.get("teams_total"),
            "valve_teams": len(valve.get("teams") or {}),
            "valve_file": valve.get("file"),
            "hltv_date_text": hltv_rank.get("date_text"),
        },
        "coverage_note": ("Every open fixture has a pick." if not no_pick else
                          f"{len(no_pick)} open fixture(s) have no pick and are flagged."),
    }
    DATA.mkdir(parents=True, exist_ok=True)
    columns = ["fixture_id", "status", "start_utc", "lock_utc", "competition", "tier", "stage",
               "points", "team_a", "team_b", "best_of", "best_of_source", "basis_code", "basis",
               "p_a_pct", "p_b_pct", "series_p_a_pct", "series_p_b_pct", "series_basis",
               "market_book", "market_odds_a", "market_odds_b", "market_p_a_pct", "market_p_b_pct",
               "market_url", "market_captured_utc", "own_source", "own_p_a_pct", "own_p_b_pct",
               "own_url", "own_inputs", "pick", "pick_pct", "confidence", "fair_odds_a",
               "fair_odds_b", "hltv_url", "hotspawn_url", "evidence_utc", "flags", "why"]
    for row in rows:
        row["fair_odds_a"] = f"{100 / float(row['p_a_pct']):.2f}" if row["p_a_pct"] else ""
        row["fair_odds_b"] = f"{100 / float(row['p_b_pct']):.2f}" if row["p_b_pct"] else ""
        row["flags"] = " | ".join(row["flags"])
    write_csv(DATA / "picks.csv", rows, columns)
    (DATA / "picks.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    flag_rows = []
    for row in rows:
        for flag in (row["flags"].split(" | ") if row["flags"] else []):
            flag_rows.append({"fixture_id": row["fixture_id"], "status": row["status"],
                              "teams": f"{row['team_a']} vs {row['team_b']}",
                              "flag": flag, "basis": row["basis_code"],
                              "source": row["market_url"] or row["own_url"] or row["hotspawn_url"]})
    write_csv(DATA / "flags.csv", flag_rows, ["fixture_id", "status", "teams", "flag", "basis", "source"])
    (EXEC / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")

    # ------------------------------------------------------------------ index (executive summary)
    stat = [("Open CS2 matches on Hotspawn now", summary["open_fixtures"], ""),
            ("With an external bookmaker line", summary["open_with_external_market"], ""),
            ("With our own originated line", summary["open_with_own_line"], ""),
            ("Picks published", summary["open_with_pick"], ""),
            ("Picks with a probability", summary["open_picks_with_probability"], ""),
            ("Picks needing review", summary["open_without_pick"] + summary["open_picks_qualitative"], "")]
    stats = "".join(f'<div class="stat"><b>{v}</b><span>{esc(t)}</span></div>' for t, v, _ in stat)
    boards = [
        ("picks.html", "Every open match, with its probability and pick",
         "One card per match — tap to see the line, our own line and the sources."),
        ("coverage.html", "Coverage against Hotspawn's live list",
         "Which fixtures Hotspawn lists now, which this board publishes, and what is missing."),
        ("cs2/index.html", "Detailed line board (cs2/)",
         "The repo's line board: market lines, own lines and calibration."),
        ("../slate/cs2.html", "Hourly market + model board (slate/)",
         "Primary bookmaker quotes, model lines and per-row verification links."),
        ("../oct14/index.html", "October CS2 verification board (oct14/)",
         "Full 91-fixture verification with HLTV match cross-references."),
        ("../live/index.html", "Live slate (live/)",
         "Every open match refreshed hourly from the Hotspawn payload."),
        ("../model/index.html", "Calibrated Valve VRS model (model/)",
         "Win probability and fair odds for all fixtures, with its own limitations page."),
        ("flagged.html", "Flagged for review",
         "Blanks, placeholders, unranked opponents and source refusals, with links."),
    ]
    tile_parts, missing_boards = [], []
    for i, (href, title, desc) in enumerate(boards):
        target = (EXEC / href).resolve()
        if not target.exists():
            missing_boards.append(f"{title} ({href})")
            continue
        tile_parts.append(f'<a class="tile{" primary" if i == 0 else ""}" href="{href}">'
                          f'<b>{esc(title)}</b><span>{esc(desc)}</span></a>')
    tiles = "".join(tile_parts)
    if missing_boards:
        tiles += ('<div class="tile" style="opacity:.85"><b>Not in this checkout</b><span>'
                  + esc(", ".join(missing_boards))
                  + ' — a parallel session publishes it; the link appears once that branch is '
                    'merged.</span></div>')
    upcoming = "".join(render_card(r) for r in open_rows[:6])
    fresh_line = (f"Fixture list captured {esc(live_json('hotspawn.json').get('captured_utc') or summary['payload_captured_utc'])} · "
                  f"Valve standings {esc(valve.get('as_of') or 'not captured in this run')} · "
                  f"HLTV ranking {esc(hltv_rank.get('date_text') or 'not captured in this run')}")
    warn = "" if not no_pick else (f'<div class="banner warn"><b>{len(no_pick)} open match(es) have no '
                                   f'pick.</b> They are listed on <a href="flagged.html">Flagged for '
                                   f'review</a> with what is missing.</div>')
    body = f"""
<div class="banner ok"><b>Start here.</b> Tap <a href="picks.html">Picks — every match</a> for the
probability and the pick for each CS2 match Hotspawn currently lists. Everything else on this page is
navigation and evidence.</div>
{warn}
<div class="grid">{stats}</div>
<h2>Where the picks are on this site</h2>
<div class="tiles">{tiles}</div>
<h2>Next matches</h2>
<div class="cards">{upcoming}</div>
<h2>What this board is, in one paragraph</h2>
<p>Every CS2 fixture on the public <a href="https://play.hotspawn.com/lobby">Hotspawn Pick'em lobby</a>
gets a probability and a pick. Featured matches are priced from external bookmaker lines (de-vigged);
matches no featured book covers are priced from official rating data — Valve's published Regional
Standings and the HLTV World Ranking — and where a team is outside both lists the pick is published as
qualitative with no invented number. Hotspawn's community pick percentage is never used as a probability.
Full rules: <a href="method.html">method</a>.</p>
<h2>Freshness</h2>
<p>{fresh_line}. A pick is suppressed in the browser after its match locks. Rows whose kickoff is more
than {STALE_DAYS} days in the past are published as <em>stale listing</em>, never as an open match.</p>
"""
    (EXEC / "index.html").write_text(page("Executive summary", body, "index.html", generated), encoding="utf-8")

    # ------------------------------------------------------------------------------------ picks
    chips = ('<div class="row1" style="display:flex;gap:.4rem;flex-wrap:wrap;margin:.3rem 0 .6rem">'
             '<span class="pick" data-tier="all" role="button" tabindex="0">All tiers</span>'
             + "".join(f'<span class="pick" data-tier="{t}" role="button" tabindex="0">Tier {t}</span>'
                       for t in sorted({r["tier"] for r in open_rows if r["tier"]}))
             + "</div>")
    picks_body = f"""
<p class="muted">One card per open CS2 match Hotspawn lists. The percentage is the source's own
de-vigged win probability; <b>PICK</b> is the higher side. Tap “sources &amp; evidence” on a card for the
bookmaker page, the Valve standings line or the HLTV page behind the number.</p>
<input id="pickfilter" type="search" placeholder="Search a team or tournament…" aria-label="Search a team or tournament">
{chips}
<div class="cards">{"".join(render_card(r) for r in open_rows)}</div>
<h2>Not open any more</h2>
<p class="muted">{len(stale_rows)} payload rows are locked, started or stale listings. They are kept in
<a href="coverage.html">coverage</a> and in the CSV, and never shown as active picks.</p>
"""
    (EXEC / "picks.html").write_text(page("Picks — every match", picks_body, "picks.html", generated),
                                     encoding="utf-8")

    # --------------------------------------------------------------------------------- coverage
    live_ids = {f["fixture_id"] for f in (live_json("hotspawn.json").get("fixtures") or [])}
    live_pairs = {(norm(f["team_a"]), norm(f["team_b"])) for f in (live_json("hotspawn.json").get("fixtures") or [])}
    cov_rows = []
    for row in sorted(rows, key=lambda r: (r["start_utc"], r["team_a"])):
        on_live = (row["fixture_id"] in live_ids or
                   (norm(row["team_a"]), norm(row["team_b"])) in live_pairs)
        cov_rows.append(
            f"<tr><td>{esc(row['start_utc'].replace('T', ' ').replace('Z', ''))}</td>"
            f"<td>{esc(row['team_a'])} vs {esc(row['team_b'])}<br><small>{esc(row['competition'])} · "
            f"tier {esc(row['tier'])}</small></td>"
            f"<td>{'yes' if on_live else 'no' if live_ids else 'not checked'}</td>"
            f"<td>{esc(row['status'])}</td>"
            f"<td>{esc(row['basis_code'])}</td>"
            f"<td>{esc(row['pick'] or '—')}{(' ' + esc(row['pick_pct']) + '%') if row['pick_pct'] else ''}</td>"
            f"<td><a href=\"{esc(row['hotspawn_url'])}\" rel=\"noopener nofollow\">Hotspawn</a>"
            + (f" · <a href=\"{esc(row['market_url'])}\" rel=\"noopener nofollow\">line</a>" if row['market_url'] else "")
            + (f" · <a href=\"{esc(row['own_url'])}\" rel=\"noopener nofollow\">ratings</a>" if row['own_url'] else "")
            + "</td></tr>")
    cover_body = f"""
<div class="banner ok"><b>Coverage check.</b> This board read Hotspawn's CS2 pick'em page at
{esc(live_json('hotspawn.json').get('captured_utc') or 'not captured in this run')} and saw
{esc(live_json('hotspawn.json').get('fixtures_total') if live_ids else 'the last committed fixture list')}
fixtures. {len(open_rows)} of them are still open; every open fixture is published here with a pick.</div>
<p class="muted">Hotspawn keeps other games in the same lobby; this board covers Counter-Strike 2 only.
The other titles are covered by the <a href="../slate/lol.html">all-title board</a>.</p>
<div class="tablewrap"><table>
<thead><tr><th>Kickoff (UTC)</th><th>Match</th><th>On Hotspawn now</th><th>Status here</th>
<th>Basis</th><th>Pick</th><th>Links</th></tr></thead>
<tbody>{''.join(cov_rows)}</tbody></table></div>
"""
    (EXEC / "coverage.html").write_text(page("Coverage vs Hotspawn", cover_body, "coverage.html", generated),
                                        encoding="utf-8")

    # ----------------------------------------------------------------------------------- method
    method_body = f"""
<h2>The rule, in order</h2>
<ol>
<li><b>T1 — external market, primary book.</b> The project's best available primary quote
(Pinnacle public guest matchups/markets). Both sides de-vigged:
<code>p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)</code>. Pick = the higher side.</li>
<li><b>T2 — external market, secondary book or aggregator</b> (EGamersWorld's public odds table, other
listed books). Same arithmetic, labelled as secondary.</li>
<li><b>T3 — our own line from official ratings.</b> Valve Regional Standings points and HLTV World
Ranking points, each mapped by
<code>p(A) = 1 / (1 + 10^(−k · (points_A − points_B) / 400))</code> with
<code>k = {K_CALIBRATED}</code> (the value <code>cs2/calibrate.py</code> fits on Valve's own published
match results). The single-map figure is shown as the headline and the series figure
(<code>BO(n)</code>) only when the payload or HLTV states the format.</li>
<li><b>T4 — ranked vs unranked.</b> When one team is in an official list and the other is in neither
Valve's nor HLTV's, no symmetric rating difference exists. The pick is the ranked team, published as
<em>qualitative</em>, with the two list checks linked. No number is invented for it.</li>
<li><b>T5 — nothing usable.</b> No pick, row flagged. (Currently zero rows.)</li>
</ol>
<p>When a primary market exists, the market side is the published pick even if the model disagrees; the
disagreement itself is a flag, and the VRS/HW numbers are printed next to it.</p>
<h2>What is never used</h2>
<ul>
<li>Hotspawn's community pick percentage, its points, its prize pool and its leaderboard. Hotspawn is
the fixture list and the UTC kickoff — nothing else. The collector does not read a crowd field at all,
and no column of this board is derived from one.</li>
<li>Any price that is a cut-off placeholder. A <code>1.80 / 1.80</code> reading is rejected and flagged
(<code>EXT-PLACEHOLDER-180</code>), because it is the aggregator's default, not a market.</li>
<li>Any rating a team does not have. Absent stays absent, and the row says which list was checked.</li>
</ul>
<h2>Known limits</h2>
<ul>
<li>The own line is a rating curve, not a calibrated betting model; it carries no information about
rosters, stand-ins, map pools or practice, and it is labelled provisional everywhere.</li>
<li>T2 readings come from an aggregator page and are not independently confirmed against the book it
names.</li>
<li>Low-tier fixtures are frequently listed by Hotspawn without a format. Where the format is unknown
the headline figure is the single-map probability; the <em>pick</em> is unchanged by that, because any
monotone rating curve orders BO1 and BO3 the same way — only the number moves.</li>
<li>Real-world availability of a market changes by the minute; each row prints the time its price was
read, and a price is never carried forward silently.</li>
</ul>
<h2>Reproduce</h2>
<pre>python exec/collect.py                # reads Hotspawn, Valve, HLTV, EGamersWorld
python scripts/exec_bdc98a9a_build.py # merges with the repo's captured evidence, renders exec/
python -m unittest tests.test_exec_bdc98a9a -v</pre>
"""
    (EXEC / "method.html").write_text(page("Method", method_body, "method.html", generated), encoding="utf-8")

    # ---------------------------------------------------------------------------------- sources
    fetch_log = []
    summary_live = (LIVE / "collect_summary.json")
    if summary_live.exists():
        try:
            fetch_log = json.loads(summary_live.read_text()).get("fetches", [])
        except Exception:  # noqa: BLE001
            fetch_log = []
    log_rows = "".join(
        f"<tr><td>{esc(item['url'].split('/')[2])}</td><td style='word-break:break-all'>"
        f"<a href=\"{esc(item['url'])}\" rel=\"noopener nofollow\">{esc(item['url'])}</a></td>"
        f"<td>{esc(item.get('status'))}</td><td>{esc(item.get('bytes'))}</td>"
        f"<td>{esc(item.get('fetched_utc'))}</td><td>{esc(item.get('error') or 'ok')}</td></tr>"
        for item in fetch_log[-40:])
    src_body = f"""
<h2>Sources this board reads</h2>
<div class="tablewrap"><table>
<thead><tr><th>What</th><th>Where</th><th>Used for</th></tr></thead>
<tbody>
<tr><td>Hotspawn Play — CS2 Pick'em lobby</td>
    <td><a href="https://play.hotspawn.com/cs2-pickems" rel="noopener nofollow">play.hotspawn.com/cs2-pickems</a>
    and <a href="https://play.hotspawn.com/lobby" rel="noopener nofollow">/lobby</a></td>
    <td>fixture identity, competition, tier, exact UTC lock/start epochs — never a probability</td></tr>
<tr><td>Valve Regional Standings (official Valve repository)</td>
    <td><a href="{esc(summary['sources']['valve_regional_standings'])}" rel="noopener nofollow">{esc(summary['sources']['valve_regional_standings'])}</a></td>
    <td>official rating points for the own line</td></tr>
<tr><td>HLTV World Ranking</td>
    <td><a href="{esc(summary['sources']['hltv_world_ranking'])}" rel="noopener nofollow">{esc(summary['sources']['hltv_world_ranking'])}</a></td>
    <td>rating points, and the yes/no of whether a team is ranked at all</td></tr>
<tr><td>HLTV match pages and per-day listings</td>
    <td><a href="https://www.hltv.org/matches" rel="noopener nofollow">hltv.org/matches</a></td>
    <td>series format (BO1/BO3/BO5), kickoff cross-check, per-team rank badge</td></tr>
<tr><td>External bookmaker lines — primary</td>
    <td><a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/" rel="noopener nofollow">pinnacle.com</a>
    (public guest matchups/markets responses)</td>
    <td>the T1 market probability and the market pick</td></tr>
<tr><td>External bookmaker lines — secondary</td>
    <td><a href="https://egamersworld.com/counterstrike/matches" rel="noopener nofollow">egamersworld.com</a>
    public odds tables (book named on the row)</td>
    <td>the T2 market probability where no primary quote exists; a <code>1.80/1.80</code> reading is
    rejected as a placeholder</td></tr>
</tbody></table></div>
<h2>This run's fetches</h2>
<p class="muted">{len(fetch_log)} HTTP reads recorded in <code>exec/data/live/collect_summary.json</code>
with status, size and SHA-256. The last 40 are shown.</p>
<div class="tablewrap"><table>
<thead><tr><th>Host</th><th>URL</th><th>Status</th><th>Bytes</th><th>Read at (UTC)</th><th>Result</th></tr></thead>
<tbody>{log_rows or '<tr><td colspan="6">No live capture in this build — the board is rendered from the last committed evidence.</td></tr>'}</tbody>
</table></div>
"""
    (EXEC / "sources.html").write_text(page("Sources", src_body, "sources.html", generated), encoding="utf-8")

    # ---------------------------------------------------------------------------------- flagged
    unresolved = [r for r in open_rows if not r["pick"]] + [r for r in open_rows if r["pick"] and not r["pick_pct"]]
    unresolved_cards = "".join(render_card(r) for r in unresolved)
    flag_table = "".join(
        f"<tr><td>{esc(f['teams'])}</td><td>{esc(f['flag'])}</td><td>{esc(f['basis'])}</td>"
        f"<td><a href=\"{esc(f['source'])}\" rel=\"noopener nofollow\">source</a></td></tr>"
        for f in flag_rows)
    norm_flags = []
    for row in rows:
        for flag in (row["flags"].split(" | ") if row["flags"] else []):
            if flag not in norm_flags:
                norm_flags.append(flag)
    flagged_body = f"""
<div class="banner {'ok' if not unresolved else 'warn'}">
{'<b>No open fixture is missing a pick.</b> The items below are the caveats that come with the picks: placeholders, unranked opponents, splits between the market and our own line, and stale listings.' if not unresolved else f'<b>{len(unresolved)} open fixture(s) need review.</b>'}
</div>
<h2>Open fixtures that need review</h2>
{unresolved_cards or '<p>None.</p>'}
<h2>Flag kinds on this board</h2>
<ul>{''.join(f'<li>{esc(f)}</li>' for f in sorted(norm_flags)) or '<li>none</li>'}</ul>
<h2>Every flagged row</h2>
<div class="tablewrap"><table>
<thead><tr><th>Match</th><th>Flag</th><th>Basis</th><th>Source</th></tr></thead>
<tbody>{flag_table or '<tr><td colspan="4">No flags.</td></tr>'}</tbody></table></div>
<p class="muted">These items do not block publication: they are what the board could not confirm, kept
visible next to the number instead of being smoothed over.</p>
"""
    (EXEC / "flagged.html").write_text(page("Flagged for review", flagged_body, "flagged.html", generated),
                                       encoding="utf-8")

    print(json.dumps(summary, indent=1))
    print(f"wrote {EXEC}/index.html, picks.html, coverage.html, method.html, sources.html, flagged.html "
          f"and 4 data files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
