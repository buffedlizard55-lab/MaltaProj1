#!/usr/bin/env python3
"""every-match picks engine — session arena/75fd29ee (task E-02/E-03).

Builds `every/` : one pick (and a win probability wherever verified inputs allow) for
EVERY open CS2 fixture on the Hotspawn Pick'em lobby, plus a mobile-first site.

Policy (unchanged from the project charter):
  * Hotspawn supplies fixture identity and UTC lock/start epochs ONLY. Crowd pick
    percentages are never an input to any probability.
  * Probabilities come from outside betting lines and/or originated rating lines
    (HLTV ranking points, Valve Regional Standings points).
  * Every published number carries a source link. Unverified values stay blank
    and are flagged. Nothing is inferred to fill a cell.

Pick hierarchy (documented on every/methodology.html):
  1. primary bookmaker line  (direct Pinnacle guest quote)         -> market pick
  2. aggregator-reported line (bc.game odds listed on EGamersWorld) -> market pick, flagged
  3. originated rating line   (Elo-400 blend, sourced BO format)     -> model pick
  4. one-sided evidence       (one team wholly unrateable)           -> pick only, no %, flagged
  5. no pick (both teams unrateable) -> blank + flagged              (should be empty)

Inputs are read-only committed evidence:
  slate/data/*            (hourly refreshed canonical snapshot — fixtures, primary quotes, ratings)
  data/8944bb84/*         (session 8944bb84: disambiguated ratings, EGW/secondary lines,
                           HLTV-verified series formats, per-row source URLs)
  data/75fd29ee/*         (this session's researched ratings, e.g. LFO 10)

The originated line uses the exact slate model functions (Elo logistic scale 400;
BO3 p^2(3-2p); BO5 p^3(10-15p+6p^2); equal-weight mean of available HLTV/VRS sides)
so numbers on `every/` and `slate/` agree wherever inputs agree. Where slate's
collector excluded alias-derived or duplicate-affected inputs, this builder uses the
evidence-linked/disambiguated rows instead and flags them per row.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVERY = ROOT / "every"
DATA_OUT = EVERY / "data"

ELO_SCALE = 400.0  # identical to slate/collect.py ELO_SCALE


# ----------------------------------------------------------------- model (parity with slate/collect.py)
def devig(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    return inv_a / total, inv_b / total, (total - 1.0) * 100.0


def elo_p(points_a: float, points_b: float, scale: float = ELO_SCALE) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(points_a - points_b) / scale))


def series_from_map(p: float, best_of: int | None) -> float | None:
    if best_of == 1:
        return p
    if best_of == 3:
        return p * p * (3.0 - 2.0 * p)
    if best_of == 5:
        return p ** 3 * (10.0 - 15.0 * p + 6.0 * p * p)
    return None


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------- helpers
def load_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def num(value) -> float | None:
    if value is None:
        return None
    value = str(value).strip()
    if value in ("", "-", "None"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def fmt_pct(value: float | None, digits: int = 1) -> str:
    return "—" if value is None else f"{value:.{digits}f}%"


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def link(url: str, label: str) -> str:
    if not url:
        return "—"
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'


# ----------------------------------------------------------------- input loading
class Inputs:
    def __init__(self) -> None:
        self.fixtures = load_csv(ROOT / "slate/data/fixtures.csv")
        self.slate_lines = load_csv(ROOT / "slate/data/lines.csv")
        self.slate_ratings = load_csv(ROOT / "slate/data/ratings.csv")
        self.slate_own = load_csv(ROOT / "slate/data/own_lines.csv")
        self.ex_lines = load_csv(ROOT / "data/8944bb84/external_lines.csv")
        self.ex_fixtures = load_csv(ROOT / "data/8944bb84/fixtures.csv")
        self.ratings84 = load_csv(ROOT / "data/8944bb84/ratings.csv")
        self.research = load_csv(ROOT / "data/75fd29ee/team_research.csv")

    def open_cs2(self) -> list[dict]:
        return [r for r in self.fixtures
                if r.get("sport") == "cs2" and r.get("live_status") == "open"]


def build_rating_index(inp: Inputs) -> dict[str, dict]:
    """Team-name (lowercased hotspawn spelling) -> rating row with resolved fields.

    Resolution order (each row keeps its source URLs):
      1. data/75fd29ee/team_research.csv  (researched additions, e.g. LFO 10)
      2. data/8944bb84/ratings.csv        (disambiguated Valve rows + HLTV ranks/points)
      3. slate/data/ratings.csv           (fallback; last, because duplicate-name bug
                                            IRREG-02 affects some of its Valve rows)
    """
    index: dict[str, dict] = {}

    for r in inp.slate_ratings:
        name = (r.get("name") or "").strip().lower()
        if not name:
            continue
        index[name] = {
            "team": r.get("name", ""),
            "hltv_points": num(r.get("hltv_points")),
            "hltv_rank": num(r.get("hltv_rank")),
            "hltv_url": r.get("hltv_source_url") or r.get("hltv_ranking_url") or "",
            "vrs_points": num(r.get("vrs_points")),
            "vrs_rank": None,
            "vrs_url": r.get("vrs_source_url") or "",
            "input_source": "slate/data/ratings.csv",
            "flags": [],
            "note": "",
        }

    for r in inp.ratings84:
        name = (r.get("hotspawn_team") or "").strip().lower()
        if not name:
            continue
        flags = [f for f in (r.get("flags") or "").split(";") if f]
        index[name] = {
            "team": r.get("hotspawn_team", ""),
            "hltv_points": num(r.get("hltv_points")),
            "hltv_rank": num(r.get("hltv_rank")),
            "hltv_url": r.get("hltv_url") or "https://www.hltv.org/ranking/teams",
            "vrs_points": num(r.get("vrs_points")),
            "vrs_rank": num(r.get("vrs_standing")),
            "vrs_url": r.get("vrs_url") or "",
            "input_source": "data/8944bb84/ratings.csv",
            "flags": flags,
            "note": (r.get("resolution") or "").strip(),
        }

    for r in inp.research:
        name = (r.get("hotspawn_name") or r.get("team") or "").strip().lower()
        if not name:
            continue
        flags = [f for f in (r.get("flags") or "").split(";") if f]
        row = index.get(name, {
            "team": r.get("team", ""), "hltv_points": None, "hltv_rank": None,
            "hltv_url": "", "vrs_points": None, "vrs_rank": None, "vrs_url": "",
            "input_source": "", "flags": [], "note": "",
        })
        # research rows supply Valve-side points when the standard inputs could not
        if num(r.get("points")) is not None and r.get("points_unit", "").lower().startswith("valve"):
            row["vrs_points"] = num(r.get("points"))
            row["vrs_rank"] = num(r.get("rank"))
            row["vrs_url"] = r.get("source_url") or row["vrs_url"]
        elif num(r.get("points")) is not None:
            row["hltv_points"] = num(r.get("points"))
            row["hltv_rank"] = num(r.get("rank"))
            row["hltv_url"] = r.get("source_url") or row["hltv_url"]
        if r.get("source_url") and r.get("source_type", "").lower().find("hltv") >= 0:
            row["hltv_url"] = row["hltv_url"] or r.get("source_url")
        row["input_source"] = "+".join(x for x in [row["input_source"], "data/75fd29ee/team_research.csv"] if x)
        # a researched rating resolves the earlier "no official rating" flag
        row["flags"] = sorted(set(f for f in row["flags"] if f != "FL-UNVERIFIED-TEAM") | set(flags) | {"E-01-RATED-VIA-RESEARCH"})
        if r.get("notes"):
            row["note"] = (row["note"] + " | research: " + r["notes"]).strip(" |")
        row["evidence_2"] = r.get("evidence_url_2") or ""
        row["evidence_3"] = r.get("evidence_url_3") or ""
        index[name] = row
    return index


# ----------------------------------------------------------------- market lines
def market_for(fixture_id: str, inp: Inputs) -> dict | None:
    """Primary (direct bookmaker) quote preferred; aggregator-reported second."""
    for r in inp.slate_lines:
        if r.get("fixture_id") == fixture_id and num(r.get("odds_a")) and num(r.get("odds_b")):
            pa, pb, ov = devig(num(r["odds_a"]), num(r["odds_b"]))
            return {
                "tier": "primary",
                "book": r.get("book") or "bookmaker",
                "odds_a": num(r["odds_a"]), "odds_b": num(r["odds_b"]),
                "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
                "overround_pct": round(ov, 2),
                "captured_utc": r.get("captured_utc") or "",
                "url": r.get("source_url") or "",
                "match_url": r.get("match_url") or "",
                "note": "direct bookmaker guest quote (slate hourly capture)",
            }
    for r in inp.ex_lines:
        if r.get("match_id") != fixture_id:
            continue
        book = (r.get("primary_book") or "").strip()
        oa, ob = num(r.get("primary_odds_a")), num(r.get("primary_odds_b"))
        if not book or not oa or not ob:
            continue
        if "1.80" == r.get("primary_odds_a") and "1.80" == r.get("primary_odds_b"):
            continue  # placeholder pattern rejected (FL-EXT-PLACEHOLDER)
        pa, pb, ov = devig(oa, ob)
        tier = "primary" if "pinnacle" in book.lower() and "egamersworld" not in book.lower() else "aggregator"
        return {
            "tier": tier,
            "book": book,
            "odds_a": oa, "odds_b": ob,
            "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
            "overround_pct": round(ov, 2),
            "captured_utc": r.get("captured_utc") or "",
            "url": r.get("primary_source_url") or r.get("egw_url") or "",
            "match_url": r.get("hltv_match_url") or "",
            "note": ("direct bookmaker quote (capture 2026-10-14)" if tier == "primary"
                     else "aggregator-reported bookmaker odds — not independently verified against the book"),
        }
    return None


# ----------------------------------------------------------------- own originated line
def own_line_for(fx: dict, ratings: dict[str, dict]) -> dict:
    a = ratings.get((fx.get("team_a") or "").strip().lower()) or {}
    b = ratings.get((fx.get("team_b") or "").strip().lower()) or {}
    best_of = fx.get("_best_of")
    out = {
        "map_p_a": None, "map_p_b": None, "series_p_a": None, "series_p_b": None,
        "basis_parts": [], "series_label": "", "flags": [],
        "a": a, "b": b, "fair_odds_a": None, "fair_odds_b": None,
    }
    if a.get("hltv_points") is not None and b.get("hltv_points") is not None:
        p = elo_p(a["hltv_points"], b["hltv_points"])
        out["hltv_map_p_a"] = round(p * 100, 2)
        out["hltv_series_p_a"] = round(series_from_map(p, best_of) * 100, 2) if best_of in (1, 3, 5) else None
        out["basis_parts"].append("HLTV ranking points")
    else:
        out["hltv_map_p_a"] = None
    if a.get("vrs_points") is not None and b.get("vrs_points") is not None:
        p = elo_p(a["vrs_points"], b["vrs_points"])
        out["vrs_map_p_a"] = round(p * 100, 2)
        out["vrs_series_p_a"] = round(series_from_map(p, best_of) * 100, 2) if best_of in (1, 3, 5) else None
        out["basis_parts"].append("Valve Regional Standings points")
    else:
        out["vrs_map_p_a"] = None
    map_parts = [x for x in (out.get("hltv_map_p_a"), out.get("vrs_map_p_a")) if x is not None]
    series_parts = [x for x in (out.get("hltv_series_p_a"), out.get("vrs_series_p_a")) if x is not None]
    if map_parts:
        out["map_p_a"] = round(sum(map_parts) / len(map_parts), 2)
        out["map_p_b"] = round(100 - out["map_p_a"], 2)
    if series_parts:
        out["series_p_a"] = round(sum(series_parts) / len(series_parts), 2)
        out["series_p_b"] = round(100 - out["series_p_a"], 2)
        out["series_label"] = f"BO{best_of} series probability"
    elif out["map_p_a"] is not None:
        out["series_label"] = "map-level estimate (series format unverified)"
    if out["map_p_a"] is not None:
        out["fair_odds_a"] = round(100 / out["map_p_a"], 2)
        out["fair_odds_b"] = round(100 / out["map_p_b"], 2)
    for side, row in (("A", a), ("B", b)):
        if not row:
            out["flags"].append(f"E-02-UNRATED-{side}: no verified rating for team {side}")
        for f in row.get("flags", []):
            out["flags"].append(f)
    return out


# ----------------------------------------------------------------- per-fixture assembly
def best_of_for(fix84: dict, slate_fx: dict) -> tuple[int | None, str, str]:
    """(best_of, source_label, source_url) — prefer HLTV-verified formats (8944bb84)."""
    fmt = (fix84.get("series_format") or "").strip().upper()
    hltv_url = fix84.get("hltv_match_url") or ""
    if fmt in ("BO1", "BO3", "BO5") and hltv_url:
        return int(fmt[2:]), f"HLTV match page ({fmt})", hltv_url
    bo = num(slate_fx.get("best_of_resolved"))
    if bo in (1, 3, 5):
        src = slate_fx.get("best_of_source") or "payload"
        return int(bo), f"{src} (BO{int(bo)})", slate_fx.get("hotspawn_match_url") or slate_fx.get("source_url") or ""
    return None, "unverified", ""


def assemble(inp: Inputs) -> tuple[list[dict], list[dict]]:
    ratings = build_rating_index(inp)
    fx84 = {r.get("match_id"): r for r in inp.ex_fixtures}
    slate_own = {r.get("fixture_id"): r for r in inp.slate_own}
    rows: list[dict] = []
    flags: list[dict] = []

    def add_flag(fid: str, subject: str, code: str, detail: str, links: str) -> None:
        flags.append({"fixture_id": fid, "subject": subject, "code": code,
                      "detail": detail, "links": links})

    for fx in sorted(inp.open_cs2(), key=lambda r: (r.get("start_utc") or "", r.get("fixture_id") or "")):
        fid = fx["fixture_id"]
        fix84 = fx84.get(fid) or {}
        best_of, bo_label, bo_url = best_of_for(fix84, fx)
        fx["_best_of"] = best_of

        market = market_for(fid, inp)
        own = own_line_for(fx, ratings)

        row_flags: list[str] = []
        team_a, team_b = fx.get("team_a", ""), fx.get("team_b", "")

        # ---- pick decision (documented hierarchy)
        pick, pick_pct, pick_basis, pick_source = "", None, "", ""
        if market:
            if market["p_a"] >= market["p_b"]:
                pick, pick_pct = team_a, market["p_a"]
            else:
                pick, pick_pct = team_b, market["p_b"]
            if market["tier"] == "primary":
                pick_basis = f"market favourite — direct {market['book']} line (de-vig), captured {market['captured_utc']}"
                pick_source = market["url"]
            else:
                pick_basis = (f"market favourite — {market['book']} odds reported by aggregator (EGamersWorld), "
                              f"captured {market['captured_utc']}; flagged aggregator-reported")
                pick_source = market["url"]
                row_flags.append("E-02-AGGREGATOR-LINE")
        elif own["series_p_a"] is not None or own["map_p_a"] is not None:
            use_series = own["series_p_a"] is not None
            pa = own["series_p_a"] if use_series else own["map_p_a"]
            pb = own["series_p_b"] if use_series else own["map_p_b"]
            if abs(pa - pb) < 0.05:
                pick, pick_pct = "", None
                pick_basis = "no pick — model cannot separate the teams (statistical tie)"
                row_flags.append("E-02-TIE")
            else:
                pick, pick_pct = (team_a, pa) if pa > pb else (team_b, pb)
                pick_basis = (f"originated rating line — {', '.join(own['basis_parts'])} → "
                              f"Elo-400 logistic → {'BO' + str(best_of) + ' series transform' if use_series and best_of in (1,3,5) else 'map-level estimate'}"
                              f"{' (series format unverified — provisional)' if not (use_series and best_of in (1,3,5)) else ''}")
                pick_source = own["a"].get("vrs_url") or own["a"].get("hltv_url") or ""
                row_flags.append("E-02-MODEL-PICK")
        else:
            # one-sided evidence: exactly one team rateable
            a_rated = bool(own["a"]) and (own["a"].get("vrs_points") is not None or own["a"].get("hltv_points") is not None)
            b_rated = bool(own["b"]) and (own["b"].get("vrs_points") is not None or own["b"].get("hltv_points") is not None)
            if a_rated and not b_rated:
                pick, pick_pct = team_a, None
                pick_basis = "one-sided evidence pick — only team A has any verified official rating; no probability invented"
                pick_source = own["a"].get("vrs_url") or own["a"].get("hltv_url") or ""
                row_flags.append("E-02-ONE-SIDED")
            elif b_rated and not a_rated:
                pick, pick_pct = team_b, None
                pick_basis = "one-sided evidence pick — only team B has any verified official rating; no probability invented"
                pick_source = own["b"].get("vrs_url") or own["b"].get("hltv_url") or ""
                row_flags.append("E-02-ONE-SIDED")
            else:
                pick_basis = "no pick — neither team has a verified rating and no market line"
                row_flags.append("E-02-NO-PICK")

        # ---- divergence between market and model favourites
        divergence = ""
        if market and own["map_p_a"] is not None:
            m_fav = team_a if market["p_a"] >= market["p_b"] else team_b
            o_fav = team_a if own["map_p_a"] >= own["map_p_b"] else team_b
            if m_fav != o_fav:
                divergence = f"market favourite {m_fav} vs model favourite {o_fav}"
                row_flags.append("E-02-DIVERGENCE")
                add_flag(fid, f"{team_a} vs {team_b}", "E-02-DIVERGENCE", divergence,
                         (market.get("url") or "") + " " + (own["a"].get("vrs_url") or ""))

        # ---- cross-check vs slate own line where slate computed one
        parity_note = ""
        so = slate_own.get(fid) or {}
        if so.get("own_map_p_a") and own["map_p_a"] is not None:
            diff = abs(float(so["own_map_p_a"]) - own["map_p_a"])
            if diff > 0.05:
                parity_note = (f"differs from slate own-line {so['own_map_p_a']} (inputs differ: "
                               f"disambiguated/researched ratings used here)")
                row_flags.append("E-02-SLATE-PARITY")

        for f in own["flags"]:
            if f not in row_flags:
                row_flags.append(f)

        if fix84.get("flags") and "FL-EXT-PLACEHOLDER" in (fix84.get("flags") or ""):
            add_flag(fid, f"{team_a} vs {team_b}", "FL-EXT-PLACEHOLDER",
                     "aggregator page showed 1.80/1.80 placeholder prices — rejected, no market line used",
                     fix84.get("egw_match_url") or "")

        rows.append({
            "fixture_id": fid,
            "start_utc": fx.get("start_utc") or "",
            "lock_utc": fx.get("lock_utc") or "",
            "competition": fx.get("competition") or "",
            "tier": fx.get("tier") or "",
            "points": fx.get("points") or "",
            "stage": fx.get("stage") or "",
            "team_a": team_a,
            "team_b": team_b,
            "best_of": best_of if best_of else "",
            "best_of_source": bo_label,
            "best_of_source_url": bo_url,
            "market_tier": market["tier"] if market else "",
            "market_book": market["book"] if market else "",
            "market_odds_a": market["odds_a"] if market else "",
            "market_odds_b": market["odds_b"] if market else "",
            "market_p_a_pct": market["p_a"] if market else "",
            "market_p_b_pct": market["p_b"] if market else "",
            "market_captured_utc": market["captured_utc"] if market else "",
            "market_url": market["url"] if market else "",
            "market_note": market["note"] if market else "no verified market line",
            "our_map_p_a_pct": own["map_p_a"] if own["map_p_a"] is not None else "",
            "our_map_p_b_pct": own["map_p_b"] if own["map_p_b"] is not None else "",
            "our_series_p_a_pct": own["series_p_a"] if own["series_p_a"] is not None else "",
            "our_series_p_b_pct": own["series_p_b"] if own["series_p_b"] is not None else "",
            "our_basis": " + ".join(own["basis_parts"]) if own["basis_parts"] else "",
            "our_series_label": own["series_label"],
            "our_fair_odds_a": own["fair_odds_a"] if own["fair_odds_a"] is not None else "",
            "our_fair_odds_b": own["fair_odds_b"] if own["fair_odds_b"] is not None else "",
            "rating_a_hltv_points": own["a"].get("hltv_points") if own["a"] else "",
            "rating_a_vrs_points": own["a"].get("vrs_points") if own["a"] else "",
            "rating_a_source_url": (own["a"].get("vrs_url") or own["a"].get("hltv_url") or "") if own["a"] else "",
            "rating_b_hltv_points": own["b"].get("hltv_points") if own["b"] else "",
            "rating_b_vrs_points": own["b"].get("vrs_points") if own["b"] else "",
            "rating_b_source_url": (own["b"].get("vrs_url") or own["b"].get("hltv_url") or "") if own["b"] else "",
            "pick": pick,
            "pick_pct": pick_pct if pick_pct is not None else "",
            "pick_basis": pick_basis,
            "pick_source_url": pick_source,
            "divergence": divergence,
            "parity_note": parity_note,
            "hotspawn_lobby_url": fx.get("source_url") or "https://play.hotspawn.com/cs2-pickems",
            "hotspawn_match_url": fx.get("hotspawn_match_url") or "",
            "hltv_match_url": fix84.get("hltv_match_url") or "",
            "flags": ";".join(row_flags),
        })
    return rows, flags


# ----------------------------------------------------------------- HTML rendering
PAGE_CSS = """
:root{--bg:#0f1216;--panel:#171c22;--panel2:#1e242c;--line:#2b333d;--fg:#e8edf3;--muted:#9aa7b4;
--accent:#6d4bbd;--good:#3fb950;--warn:#d29922;--bad:#f85149;--pick:#3fb950}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1020px;margin:0 auto;padding:16px 14px 60px}
header.top{position:sticky;top:0;z-index:20;background:rgba(15,18,22,.97);
border-bottom:1px solid var(--line);padding:10px 0}
header.top .wrap{padding-top:0;padding-bottom:0;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.brand{font-weight:800;font-size:16px;color:#fff;text-decoration:none}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips a{font-size:12px;text-decoration:none;background:var(--panel2);border:1px solid var(--line);
border-radius:999px;padding:4px 10px;color:var(--fg);white-space:nowrap}
.chips a.on{border-color:var(--accent);color:#d9c9ff}
h1{font-size:21px;margin:14px 0 4px;line-height:1.25}
h2{font-size:15px;margin:26px 0 10px;color:#cfd8e3;text-transform:uppercase;letter-spacing:.06em}
p.lead{color:var(--muted);margin:2px 0}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:14px 0}
.scard{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.scard .n{font-size:22px;font-weight:800;color:#fff}
.scard .l{font-size:11.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.finder{background:linear-gradient(180deg,#1d2430,#171c22);border:1px solid var(--accent);
border-radius:12px;padding:14px;margin:12px 0}
.finder a.big{display:block;text-align:center;text-decoration:none;font-weight:800;font-size:16px;
background:var(--accent);color:#fff;border-radius:10px;padding:12px;margin:10px 0 8px}
.finder .mini{display:flex;flex-wrap:wrap;gap:6px}
.finder .mini a{flex:1 1 130px;text-align:center;text-decoration:none;background:var(--panel2);
border:1px solid var(--line);border-radius:8px;padding:8px;font-size:12.5px;color:var(--fg)}
table{width:100%;border-collapse:collapse;margin:8px 0;font-size:13px}
th{text-align:left;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;
padding:8px 8px;border-bottom:1px solid var(--line)}
td{padding:10px 8px;border-bottom:1px solid var(--line);vertical-align:top}
.mut{color:var(--muted);font-size:12px}
.pickbadge{display:inline-block;background:rgba(63,185,80,.12);border:1px solid var(--good);
color:#7ee787;border-radius:8px;padding:2px 8px;font-weight:800;font-size:12.5px}
.pickbadge.model{background:rgba(109,75,189,.15);border-color:var(--accent);color:#c9b6ff}
.pickbadge.agg{background:rgba(210,153,34,.12);border-color:var(--warn);color:#e3b341}
.prob{display:flex;height:8px;border-radius:999px;overflow:hidden;background:#222a33;margin:6px 0}
.prob i{display:block;height:100%}
.prob .a{background:#4c8dff}.prob .b{background:#c26bd4}
.teams{font-weight:650}
.teams .win{color:#7ee787}
.flag{display:inline-block;font-size:10.5px;font-weight:700;border-radius:999px;padding:1px 7px;
margin:2px 3px 0 0;border:1px solid var(--line);color:var(--muted)}
.flag.warn{border-color:var(--warn);color:#e3b341}
.flag.bad{border-color:var(--bad);color:#ff7b72}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:8px;padding:11px 13px;margin:12px 0;font-size:12.8px;color:var(--muted)}
a{color:#8fb4ff}
ul.plain{padding-left:18px;margin:8px 0}ul.plain li{color:var(--muted);font-size:12.8px;margin:4px 0}
code{background:#0b0e12;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
footer{margin-top:36px;padding-top:14px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
/* mobile: turn the picks table into stacked cards */
@media (max-width:640px){
  table.resp,table.resp tbody,table.resp tr,table.resp td{display:block;width:100%}
  table.resp thead{display:none}
  table.resp tr{background:var(--panel);border:1px solid var(--line);border-radius:12px;
    margin:10px 0;padding:10px 12px}
  table.resp td{border:0;padding:3px 0}
  table.resp td[data-label]::before{content:attr(data-label);display:block;font-size:10.5px;
    color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-top:6px}
  h1{font-size:19px}
  .wrap{padding:12px 10px 50px}
}
"""


def page(title: str, active: str, body: str, subtitle: str) -> str:
    def chip(href, label, key):
        cls = ' class="on"' if active == key else ""
        return f'<a href="{href}"{cls}>{esc(label)}</a>'
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(subtitle)}">
<link rel="stylesheet" href="style.css">
</head><body>
<header class="top"><div class="wrap">
<a class="brand" href="index.html">CS2 Picks</a>
<nav class="chips">
{chip('index.html', 'All picks', 'picks')}
{chip('methodology.html', 'Methodology', 'method')}
{chip('flagged.html', 'Flagged', 'flagged')}
{chip('sources.html', 'Sources', 'sources')}
{chip('../index.html', 'Site home', 'home')}
</nav>
</div></header>
<div class="wrap">
{body}
<footer>
<p>Analysis only — not betting advice. Hotspawn supplies fixture identity and UTC times only;
its crowd pick percentages are never used as probability inputs. Unknown values stay blank and flagged.</p>
<p>Generated from committed evidence by <code>scripts/75fd29ee_build.py</code> ·
<a href="data/picks.csv">picks.csv</a> · <a href="data/coverage.json">coverage.json</a></p>
</footer>
</div>
</body></html>
"""


def render_picks(rows: list[dict], coverage: dict) -> str:
    n = len(rows)
    n_market = sum(1 for r in rows if r["market_tier"] in ("primary", "aggregator"))
    n_primary = sum(1 for r in rows if r["market_tier"] == "primary")
    n_agg = sum(1 for r in rows if r["market_tier"] == "aggregator")
    n_model = sum(1 for r in rows if "E-02-MODEL-PICK" in r["flags"])
    n_onesided = sum(1 for r in rows if "E-02-ONE-SIDED" in r["flags"])
    n_nopick = sum(1 for r in rows if not r["pick"])
    n_div = sum(1 for r in rows if r["divergence"])

    cards = f"""
<h1>Every CS2 Pick&rsquo;em match &mdash; picks &amp; win probabilities</h1>
<p class="lead">Updated {esc(coverage['generated_utc'])} · snapshot {esc(coverage['snapshot_utc'])} ·
all {n} open fixtures on the
<a href="https://play.hotspawn.com/cs2-pickems" target="_blank" rel="noopener">Hotspawn CS2 lobby</a> covered.</p>

<div class="summary">
  <div class="scard"><div class="n">{n}</div><div class="l">Open matches</div></div>
  <div class="scard"><div class="n">{n - n_nopick}</div><div class="l">Matches with a pick</div></div>
  <div class="scard"><div class="n">{n_primary}</div><div class="l">Primary market lines</div></div>
  <div class="scard"><div class="n">{n_agg}</div><div class="l">Aggregator lines (flagged)</div></div>
  <div class="scard"><div class="n">{n_model}</div><div class="l">Model-only picks</div></div>
  <div class="scard"><div class="n">{n_div}</div><div class="l">Market/model divergences</div></div>
</div>

<div class="finder">
  <strong>Where to find the picks</strong>
  <p class="mut" style="margin:4px 0 0">This page is the always-current list. Every match below shows the
  pick in green, the win probability from the source that drove it, our own originated line, and source links
  you can open and check yourself.</p>
</div>
"""

    body_rows = []
    for r in rows:
        pa = num(r["market_p_a_pct"]) if r["market_p_a_pct"] != "" else num(r["our_series_p_a_pct"]) if r["our_series_p_a_pct"] != "" else num(r["our_map_p_a_pct"])
        pb = 100 - pa if pa is not None else None
        if r["market_tier"] == "primary":
            src_label, badge = f"market · {r['market_book']}", "pickbadge"
        elif r["market_tier"] == "aggregator":
            src_label, badge = f"market · {r['market_book']} (aggregator-reported)", "pickbadge agg"
        elif "E-02-MODEL-PICK" in r["flags"]:
            src_label, badge = f"our line · {r['our_series_label'] or 'rating model'}", "pickbadge model"
        elif "E-02-ONE-SIDED" in r["flags"]:
            src_label, badge = "one-sided evidence", "pickbadge model"
        else:
            src_label, badge = "no pick", "pickbadge agg"

        pick_html = (f'<span class="{badge}">PICK: {esc(r["pick"])}</span>'
                     if r["pick"] else '<span class="pickbadge agg">no pick — see flags</span>')
        pct_html = fmt_pct(num(r["pick_pct"])) if r["pick_pct"] != "" else "—"
        prob_html = ""
        if pa is not None:
            prob_html = (f'<div class="prob"><i class="a" style="width:{pa:.1f}%"></i>'
                         f'<i class="b" style="width:{100 - pa:.1f}%"></i></div>'
                         f'<div class="mut">{esc(r["team_a"])} {fmt_pct(pa)} · {fmt_pct(100 - pa)} {esc(r["team_b"])}</div>')
        flags_html = "".join(
            f'<span class="flag {"warn" if f.startswith("E-02") else ""}">{esc(f)}</span>'
            for f in (r["flags"].split(";") if r["flags"] else []))

        mkt = "—"
        if r["market_url"]:
            mkt = (f'{esc(r["market_book"])} {esc(r["market_odds_a"])}/{esc(r["market_odds_b"])} '
                   f'({fmt_pct(num(r["market_p_a_pct"]))}/{fmt_pct(num(r["market_p_b_pct"]))}) '
                   + link(r["market_url"], "quote") + f' <span class="mut">{esc(r["market_captured_utc"])}</span>')
        ours = "—"
        if r["our_series_p_a_pct"] != "" or r["our_map_p_a_pct"] != "":
            ser = (f'{fmt_pct(num(r["our_series_p_a_pct"]))}/{fmt_pct(num(r["our_series_p_b_pct"]))} '
                   f'<span class="mut">{esc(r["our_series_label"])}</span>'
                   if r["our_series_p_a_pct"] != "" else
                   f'{fmt_pct(num(r["our_map_p_a_pct"]))}/{fmt_pct(num(r["our_map_p_b_pct"]))} '
                   f'<span class="mut">map-level</span>')
            ours = (ser + "<br>" + esc(r["our_basis"]) + " " +
                    (link(r["rating_a_source_url"], "A src") if r["rating_a_source_url"] else "") + " " +
                    (link(r["rating_b_source_url"], "B src") if r["rating_b_source_url"] else ""))
        links_cell = " ".join(x for x in [
            link(r["hotspawn_lobby_url"], "Hotspawn"),
            link(r["hltv_match_url"], "HLTV") if r["hltv_match_url"] else "",
            link(r["best_of_source_url"], "format") if r["best_of_source_url"] else "",
        ] if x and x != "—")

        body_rows.append(f"""<tr>
<td data-label="Match"><div class="teams">{esc(r["team_a"])} vs {esc(r["team_b"])}</div>
<div class="mut">{esc(r["start_utc"])} · lock {esc(r["lock_utc"])} · {esc(r["competition"])}
· tier {esc(r["tier"])} ({esc(r["points"])} pts) · BO{esc(r["best_of"] or "?")} <span class="mut">via {esc(r["best_of_source"])}</span></div>
{prob_html}{flags_html}</td>
<td data-label="Pick">{pick_html}<div class="mut">{esc(src_label)} · win prob {pct_html}</div>
<div class="mut">{esc(r["pick_basis"])}</div></td>
<td data-label="Market line">{mkt}</td>
<td data-label="Our originated line">{ours}</td>
<td data-label="Sources">{links_cell}</td>
</tr>""")

    table = f"""
<h2>All matches ({n})</h2>
<table class="resp">
<thead><tr><th>Match</th><th>Pick</th><th>Market line</th><th>Our originated line</th><th>Sources</th></tr></thead>
<tbody>
{"".join(body_rows)}
</tbody></table>
<div class="note">Pick hierarchy: primary bookmaker line &gt; aggregator-reported line (flagged) &gt;
originated rating line &gt; one-sided evidence. Where a market line exists its de-vig probability is the
headline; our own line is shown on every row. Divergences are flagged, never averaged away.
See <a href="methodology.html">methodology</a> and <a href="flagged.html">flagged items</a>.</div>
"""
    return page("CS2 Picks — every Hotspawn Pick'em match", "picks", cards + table,
                "A pick and win probability for every open CS2 match on the Hotspawn Pick'em lobby, "
                "built from outside betting lines and HLTV/Valve ratings.")


def render_methodology(coverage: dict | None = None) -> str:
    n_nopick = (coverage or {}).get("no_pick", 0)
    body = f"""
<h1>Methodology</h1>
<p class="lead">How every pick on this site is produced. Generated {esc(now_iso())}.</p>

<h2>What Hotspawn is used for</h2>
<ul class="plain">
<li>Fixture identity: team names, competition, tier/points, and the open CS2 Pick'em match set.</li>
<li>UTC start and lock epochs (payload <code>scheduled_start_time</code>/<code>lock_time</code>).</li>
<li><strong>Never</strong> a probability input: Hotspawn crowd pick percentages are excluded everywhere.</li>
</ul>

<h2>Where probabilities come from</h2>
<ul class="plain">
<li><strong>Market lines.</strong> Two-way de-vig of decimal odds:
<code>p(A) = (1/o_A) / (1/o_A + 1/o_B)</code>. Primary tier = direct bookmaker guest quote
(Pinnacle, captured by the hourly slate pipeline). Aggregator tier = bookmaker odds as listed on
EGamersWorld (bc.game), capture-stamped 2026-10-14 and flagged because we cannot re-verify them
against the book ourselves. Placeholder prices (1.80/1.80) are rejected.</li>
<li><strong>Our originated line.</strong> Every team gets rating points from official sources:
HLTV world-ranking points and Valve Regional Standings (VRS) points. Each side becomes a per-map
probability with the standard Elo logistic
<code>p = 1 / (1 + 10^((r_A − r_B)/400))</code>, then a series probability
<code>BO3: p²(3−2p)</code> · <code>BO5: p³(10−15p+6p²)</code> · <code>BO1: p</code>.
When both sides exist the map/series probability is the equal-weight mean of the HLTV-based and
VRS-based values (identical arithmetic to <code>slate/collect.py</code>). The 400 scale and
equal weighting are project assumptions — not calibrated forecasts, and not Valve/HLTV formulas.</li>
<li><strong>Series formats</strong> come from HLTV match pages (BO1/BO3/BO5 labels), linked per row.</li>
</ul>

<h2>Pick hierarchy</h2>
<ol class="plain">
<li>Primary bookmaker line → market favourite.</li>
<li>Aggregator-reported line (flagged) → market favourite.</li>
<li>Originated rating line with a sourced BO format → series-probability favourite
(labeled provisional — the model is not calibrated).</li>
<li>Format unverified but ratings exist → map-level favourite as a provisional guide.</li>
<li>One team has no verified rating anywhere → pick the rateable team, probability left blank.</li>
<li>Neither team rateable and no market → no pick, flagged. (Currently {n_nopick} such matches.)</li>
</ol>

<h2>Rating inputs and name resolution</h2>
<ul class="plain">
<li>Valve VRS rows are taken from Valve's official
<a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md" target="_blank" rel="noopener">standings_global_2026_10_05.md</a>.
Where that file lists duplicate names, the disambiguated roster-verified row is used
(see <a href="flagged.html">IRREG-02</a>).</li>
<li>HLTV world-ranking points come from
<a href="https://www.hltv.org/ranking/teams" target="_blank" rel="noopener">hltv.org/ranking/teams</a>.</li>
<li>Teams absent from both (e.g. LFO 10) are researched separately; each researched value records its
own source URL and is flagged. Mixed snapshot dates across teams are flagged per row.</li>
<li>Evidence-linked name aliases (WROTBERRY→WBT, RoundsGG→ROUNDS, Envy→3DMAX, EAC→EA Copenhagen)
carry their evidence URLs; alias-derived inputs are flagged on the row.</li>
</ul>

<h2>Limitations</h2>
<ul class="plain">
<li>Model probabilities are provisional and uncalibrated; do not treat them as official forecasts.</li>
<li>Aggregator-reported odds may drift or differ from the book&rsquo;s own feed.</li>
<li>Market/model divergences are published as flags; the market favourite drives the pick when a line exists.</li>
<li>Analysis only — not betting advice.</li>
</ul>
"""
    return page("Methodology — CS2 Picks", "method", body,
                "Exact selection rules, formulas, sources and limitations behind every pick.")


def render_flagged(flags: list[dict], rows: list[dict]) -> str:
    items = []
    for f in flags:
        items.append(f"""<tr><td><code>{esc(f['code'])}</code></td>
<td>{esc(f['subject'])}<div class="mut">{esc(f['fixture_id'])}</div></td>
<td>{esc(f['detail'])}</td>
<td>{link(f['links'].split()[0] if f['links'] else '', 'source') if f['links'] else '—'}</td></tr>""")
    carried = """
<h2>Carried irregularities (from prior sessions, still open for review)</h2>
<ul class="plain">
<li><strong>IRREG-02</strong> — Valve's 2026-10-05 standings file contains duplicate team names
(ex-RUSTEC, 6666, Banda Chuya and others). <code>slate/collect.py</code> keeps the last (often
partial-roster) row; this board uses the roster-verified rows from
<a href="../reviews/8944bb84-verification.md">reviews/8944bb84-verification.md</a>
with line-anchored Valve links. Slate own-lines for those fixtures can read differently until the
collector is fixed. <a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md">Valve file</a></li>
<li><strong>FL-EXT-PLACEHOLDER</strong> — EGamersWorld pages for fixtures 1081112, 1081113, 1079624,
1081120 showed 1.80/1.80 placeholder prices; rejected as market evidence
(source: <a href="https://egamersworld.com/counterstrike/matches">egamersworld.com</a>).</li>
<li><strong>E-01 identity note</strong> — LFO 10&rsquo;s 3-man core (dottie/flaw/Sapec) appears as
&ldquo;Entropy&rdquo; #156 (813 pts) in Valve&rsquo;s 2026-10-05 file and as &ldquo;LFO 10&rdquo;
(771 Valve points, #168) on HLTV&rsquo;s Valve ranking of 2026-10-10. The match-page badge shows live
VRS #169. All three observations are recorded; the dated 2026-10-10 value is used.
<a href="https://www.hltv.org/valve-ranking/teams/2026/october/10">ranking page</a> ·
<a href="https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11">match 2399301</a></li>
<li><strong>Alias inputs</strong> — WROTBERRY→WBT, RoundsGG→ROUNDS, EAC→EA Copenhagen, Envy→3DMAX are
evidence-linked but flagged for review (see <code>slate/aliases.json</code> evidence URLs).</li>
</ul>
"""
    body = f"""
<h1>Flagged for review</h1>
<p class="lead">Irregularities and unverified items. None of these blocks a pick; each keeps its source
links so you can check it yourself. Generated {esc(now_iso())}.</p>
<h2>Row-level flags ({len(flags)})</h2>
<table class="resp"><thead><tr><th>Code</th><th>Subject</th><th>Detail</th><th>Source</th></tr></thead>
<tbody>{"".join(items) if items else '<tr><td colspan="4">No row-level flags in this snapshot.</td></tr>'}</tbody></table>
{carried}
"""
    return page("Flagged for review — CS2 Picks", "flagged", body,
                "Irregularities, unverified items and data-quality notes with source links.")


def render_sources(rows: list[dict], coverage: dict) -> str:
    src_rows = f"""
<h1>Sources</h1>
<p class="lead">Every input used to build the picks. Generated {esc(coverage['generated_utc'])}.</p>
<h2>Registers</h2>
<table class="resp"><thead><tr><th>Source</th><th>What it provides</th><th>Captured / dated</th><th>Link</th></tr></thead>
<tbody>
<tr><td>Hotspawn Pick'em lobby</td><td>Fixture identity, UTC start/lock (never probabilities)</td>
<td>{esc(coverage['snapshot_utc'])}</td>
<td>{link('https://play.hotspawn.com/cs2-pickems', 'play.hotspawn.com')}</td></tr>
<tr><td>Pinnacle guest moneylines</td><td>Primary market quotes (5 fixtures this snapshot)</td>
<td>2026-10-14T02:21Z</td>
<td>{link('https://www.pinnacle.com/en/esports/games/cs2/matchups/', 'pinnacle.com')}</td></tr>
<tr><td>EGamersWorld listing bc.game prices</td><td>Aggregator-reported market quotes (flagged)</td>
<td>2026-10-14T01:48–02:26Z</td>
<td>{link('https://egamersworld.com/counterstrike/matches', 'egamersworld.com')}</td></tr>
<tr><td>HLTV match pages</td><td>Series formats (BO1/BO3/BO5), team identity, rosters</td>
<td>per row</td>
<td>{link('https://www.hltv.org/matches', 'hltv.org/matches')}</td></tr>
<tr><td>HLTV world ranking</td><td>HLTV ranking points</td><td>2026-10-12</td>
<td>{link('https://www.hltv.org/ranking/teams', 'hltv.org/ranking/teams')}</td></tr>
<tr><td>Valve Regional Standings (official GitHub)</td><td>VRS points/standings</td><td>2026-10-05</td>
<td>{link('https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md', 'standings_global_2026_10_05.md')}</td></tr>
<tr><td>HLTV Valve global ranking</td><td>Researched addition (LFO 10: #168, 771 pts)</td><td>2026-10-10</td>
<td>{link('https://www.hltv.org/valve-ranking/teams/2026/october/10', 'hltv.org/valve-ranking')}</td></tr>
</tbody></table>

<h2>Machine-readable outputs</h2>
<ul class="plain">
<li>{link('data/picks.csv', 'every/data/picks.csv')} — one row per open fixture (pick, probabilities, sources).</li>
<li>{link('data/picks.json', 'every/data/picks.json')} — the same data as JSON.</li>
<li>{link('data/coverage.json', 'every/data/coverage.json')} — counts and input stamps.</li>
<li>{link('data/flags.csv', 'every/data/flags.csv')} — flag register.</li>
</ul>
"""
    return page("Sources — CS2 Picks", "sources", src_rows,
                "Source register for every input behind the picks, with capture times and links.")


# ----------------------------------------------------------------- main
def main() -> int:
    inp = Inputs()
    rows, flags = assemble(inp)
    DATA_OUT.mkdir(parents=True, exist_ok=True)

    now = now_iso()
    snapshot = ""
    cov_in = ROOT / "slate/data/coverage.json"
    if cov_in.exists():
        snapshot = (json.loads(cov_in.read_text()).get("generated_utc") or "")

    coverage = {
        "generated_utc": now,
        "snapshot_utc": snapshot,
        "open_cs2_fixtures": len(rows),
        "with_pick": sum(1 for r in rows if r["pick"]),
        "market_primary": sum(1 for r in rows if r["market_tier"] == "primary"),
        "market_aggregator": sum(1 for r in rows if r["market_tier"] == "aggregator"),
        "model_only": sum(1 for r in rows if "E-02-MODEL-PICK" in r["flags"]),
        "one_sided": sum(1 for r in rows if "E-02-ONE-SIDED" in r["flags"]),
        "no_pick": sum(1 for r in rows if not r["pick"]),
        "divergences": sum(1 for r in rows if r["divergence"]),
        "flags": len(flags),
        "hotspawn_crowd_used": False,
        "inputs": {
            "fixtures": "slate/data/fixtures.csv",
            "primary_lines": "slate/data/lines.csv",
            "secondary_lines": "data/8944bb84/external_lines.csv",
            "series_formats": "data/8944bb84/fixtures.csv (HLTV-verified)",
            "ratings": "data/8944bb84/ratings.csv + slate/data/ratings.csv + data/75fd29ee/team_research.csv",
        },
    }

    # ---- write data
    if rows:
        with (DATA_OUT / "picks.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    (DATA_OUT / "picks.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (DATA_OUT / "coverage.json").write_text(json.dumps(coverage, indent=1), encoding="utf-8")
    if flags:
        with (DATA_OUT / "flags.csv").open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()))
            w.writeheader()
            w.writerows(flags)
    else:
        (DATA_OUT / "flags.csv").write_text("fixture_id,subject,code,detail,links\n", encoding="utf-8")

    # ---- write pages
    (EVERY / "style.css").write_text(PAGE_CSS.strip() + "\n", encoding="utf-8")
    (EVERY / "index.html").write_text(render_picks(rows, coverage), encoding="utf-8")
    (EVERY / "methodology.html").write_text(render_methodology(coverage), encoding="utf-8")
    (EVERY / "flagged.html").write_text(render_flagged(flags, rows), encoding="utf-8")
    (EVERY / "sources.html").write_text(render_sources(rows, coverage), encoding="utf-8")

    # ---- self-checks (build fails loudly on policy breaks)
    problems = []
    for r in rows:
        if not r["pick"] and "E-02-NO-PICK" not in r["flags"] and "E-02-TIE" not in r["flags"]:
            problems.append(f"{r['fixture_id']}: missing pick without a documented flag")
        if not (r["hotspawn_lobby_url"] or r["hotspawn_match_url"]):
            problems.append(f"{r['fixture_id']}: no Hotspawn source link")
        if r["pick"] and not (r["pick_source_url"] or r["market_url"] or r["rating_a_source_url"]):
            problems.append(f"{r['fixture_id']}: pick without any source link")
    if problems:
        print("SELF-CHECK FAILED:", *problems, sep="\n  ")
        return 1

    print(f"every/ built: {len(rows)} open CS2 fixtures, "
          f"{coverage['with_pick']} picks ({coverage['market_primary']} primary + "
          f"{coverage['market_aggregator']} aggregator + {coverage['model_only']} model + "
          f"{coverage['one_sided']} one-sided), {coverage['no_pick']} no-pick, {len(flags)} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
