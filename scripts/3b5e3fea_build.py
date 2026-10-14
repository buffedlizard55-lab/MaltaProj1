#!/usr/bin/env python3
"""Executive-summary board builder — session arena/3b5e3fea.

Builds `exec/` : one mobile-first page that answers "where are today's picks and what
are they", plus a per-row coverage audit of every other board in this repository.

Rules enforced here (and tested in tests/test_3b5e3fea.py):
  * Hotspawn supplies fixture identity (id, teams, competition, tier, kickoff/lock UTC)
    only. A Hotspawn crowd percentage is never read, stored or published.
  * Every published probability carries a basis label and a source URL.
  * A number that no source supplies is left empty and flagged, never inferred.
  * A pick is only published when the row has a stated basis.

Outputs
  exec/data/picks.json          machine-readable rows (also drives live refresh in the browser)
  exec/data/picks.csv           same rows, spreadsheet form
  exec/data/coverage_audit.csv  fixture x board coverage
  exec/data/boards.json         per-board freshness / counts
  exec/data/flags.json          this board's review items
  exec/*.html                   the pages

Run:  python3 scripts/3b5e3fea_build.py
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "exec")
DATA = os.path.join(OUT, "data")

NOW = datetime.now(timezone.utc)


# --------------------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------------------
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str):
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%MZ"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def num(value):
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def read_csv(rel_path: str):
    """Read a CSV written by another session's board. Missing file -> (None, []) ."""
    path = os.path.join(ROOT, rel_path)
    if not os.path.exists(path):
        return None, []
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = [dict(r) for r in csv.DictReader(fh)]
    except Exception as exc:  # pragma: no cover - defensive, surfaced as a flag
        return None, [{"_read_error": str(exc)}]
    return path, rows


def url_or_blank(value) -> str:
    """Only publish something that is actually a URL; a descriptive string is not a source link."""
    text = (value or "").strip()
    return text if text.startswith(("http://", "https://")) else ""


def de_vig(odds_a, odds_b):
    """Multiplicative two-way de-vig. Returns (p_a, p_b, overround_pct) or (None,)*3."""
    if not odds_a or not odds_b or odds_a <= 1 or odds_b <= 1:
        return None, None, None
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    if total <= 0:
        return None, None, None
    return 100.0 * inv_a / total, 100.0 * inv_b / total, 100.0 * (total - 1.0)


# --------------------------------------------------------------------------------------
# board adapters — every published number keeps the link it came from
# --------------------------------------------------------------------------------------
DIRECT_BOOKS = ("pinnacle",)          # primary bookmaker responses we can read directly
SECONDARY_MARKS = ("egamersworld", "egw", "bc.game")  # aggregator-mediated prices

def normalize_bo(value: str) -> str:
    """BO1 / BO3 / BO5 only. Anything else stays empty — never guessed."""
    text = (value or "").strip().upper().replace(" ", "")
    if text in ("BO1", "BO3", "BO5"):
        return text
    if text in ("1", "3", "5"):
        return "BO" + text
    if text.startswith("BEST OF"):
        digits = re.sub(r"[^0-9]", "", text)
        if digits in ("1", "3", "5"):
            return "BO" + digits
    return ""


BOARDS = [
    {
        "id": "slate",
        "name": "Live slate board (hourly)",
        "path": "slate/data/analysis.csv",
        "page": "slate/cs2.html",
        "flagged": "slate/flagged.html",
        "method": "slate/methodology.html",
        "owner": "arena/180a42a0 + arena/a9a0c2f1",
        "captured_from": {"path": "slate/data/coverage.json", "key": "generated_utc"},
        "what": "Hourly gated collector. Direct bookmaker quotes drive its pick; the model line is "
                "published separately and is left blank when the series format is unverified.",
    },
    {
        "id": "oct14",
        "name": "Oct-14 verified slate",
        "path": "data/8944bb84/analysis.csv",
        "page": "oct14/index.html",
        "flagged": "oct14/flagged.html",
        "method": "oct14/methodology.html",
        "owner": "arena/8944bb84",
        "captured_from": {"path": "data/8944bb84/coverage.json", "key": "generated_utc"},
        "what": "All 91 CS2 payload rows cross-checked against HLTV match pages and Valve VRS; "
                "per-row external book, series format and originated line.",
    },
    {
        "id": "openslate",
        "name": "Open-slate review copy",
        "path": "data/08031d30/open_slate.csv",
        "page": "open-slate/index.html",
        "flagged": "open-slate/flagged.html",
        "method": "open-slate/index.html",
        "owner": "arena/08031d30",
        "captured_from": {"path": "data/08031d30/open_slate.csv", "key": ""},
        "what": "Independent re-read of the open set with its own market reads; several rows carry "
                "prices forward from the previous day and say so.",
    },
    {
        "id": "everypick",
        "name": "Every-match picks (fallback tiers)",
        "path": "data/fbcccda2/every_pick.csv",
        "page": "everypick/index.html",
        "flagged": "everypick/flagged.html",
        "method": "everypick/methodology.html",
        "owner": "arena/fbcccda2",
        "what": "One pick for all 28 open fixtures in ordered tiers (A: latest direct price, B: earlier "
                "external report, C: sourced-format rating model, D: guided lean with the percentage left blank).",
        "captured_from": {"path": "data/fbcccda2/coverage.json", "key": "snapshot_utc"},
    },
    {
        "id": "cs2",
        "name": "CS2 board with re-calibrated model",
        "path": "cs2/data/analysis.csv",
        "page": "cs2/index.html",
        "flagged": "cs2/flagged.html",
        "method": "cs2/methodology.html",
        "owner": "arena/a174d77f",
        "captured_from": {"path": "cs2/data/summary.json", "key": "generated_utc"},
        "what": "Pinnacle guest prices and a model slope re-fitted on Valve's own match archive.",
    },
]


def adapt_slate(rows):
    """slate/data/analysis.csv -> normalised candidate lines."""
    out = []
    for r in rows:
        if (r.get("sport") or "").lower() != "cs2":
            continue
        r["fixture_id"] = (r.get("fixture_id") or "").strip()
        if not r["fixture_id"]:
            continue
        market_p_a, market_p_b = num(r.get("market_p_a_pct")), num(r.get("market_p_b_pct"))
        odds_a, odds_b = num(r.get("market_odds_a")), num(r.get("market_odds_b"))
        if market_p_a is None and odds_a and odds_b:
            market_p_a, market_p_b, _ = de_vig(odds_a, odds_b)
        out.append({
            "fixture_id": r["fixture_id"],
            "board": "slate",
            "team_a": r.get("team_a"), "team_b": r.get("team_b"),
            "kickoff_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
            "competition": r.get("competition"), "tier": r.get("tier"),
            "hotspawn_match_url": r.get("hotspawn_match_url") or "",
            "best_of": normalize_bo(r.get("best_of")),
            "best_of_source": r.get("best_of_source") or "",
            "market_book": r.get("market_book") or r.get("market_source") or "",
            "market_odds_a": odds_a, "market_odds_b": odds_b,
            "market_p_a": market_p_a, "market_p_b": market_p_b,
            "market_url": url_or_blank(r.get("market_url")) or url_or_blank(r.get("market_source")),
            "market_captured_utc": r.get("market_captured_utc") or r.get("captured_utc") or "",
            "market_note": r.get("market_note") or "",
            "own_p_a": num(r.get("own_p_a_pct")), "own_p_b": num(r.get("own_p_b_pct")),
            "own_basis": r.get("own_basis") or "",
            "own_url": url_or_blank(r.get("rating_valve_url")) or url_or_blank(r.get("own_source_url")),
            "pick": (r.get("pick") or "").strip(), "pick_pct": num(r.get("pick_pct")),
            "pick_basis": r.get("pick_basis") or "",
            "captured_utc": r.get("captured_utc") or "",
            "flags": [f for f in (r.get("flags") or "").split(";") if f.strip()],
        })
    return out


def adapt_oct14(rows):
    """data/8944bb84/analysis.csv -> normalised candidate lines."""
    out = []
    for r in rows:
        if (r.get("slate_bucket") or "") == "stale_summer_2026":
            continue
        fid = (r.get("match_id") or "").strip()
        if not fid:
            continue
        ext_a, ext_b = num(r.get("ext_odds_a")), num(r.get("ext_odds_b"))
        ext_p_a, ext_p_b = num(r.get("ext_p_a")), num(r.get("ext_p_b"))
        if ext_p_a is None and ext_a and ext_b:
            ext_p_a, ext_p_b, _ = de_vig(ext_a, ext_b)
        own_a, own_b = num(r.get("own_p_a")), num(r.get("own_p_b"))
        owner_url = r.get("vrs_url_a") or r.get("hltv_url_a") or ""
        out.append({
            "fixture_id": fid,
            "board": "oct14",
            "team_a": r.get("team_a"), "team_b": r.get("team_b"),
            "kickoff_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
            "competition": r.get("tournament"), "tier": r.get("tier"),
            "hotspawn_match_url": r.get("hotspawn_match_url") or "",
            "best_of": normalize_bo(r.get("series_format")),
            "best_of_source": r.get("hltv_match_url") or "",
            "market_book": r.get("ext_book") or "",
            "market_odds_a": ext_a, "market_odds_b": ext_b,
            "market_p_a": ext_p_a, "market_p_b": ext_p_b,
            "market_url": url_or_blank(r.get("ext_source_url")) or url_or_blank(r.get("egw_url")),
            "market_captured_utc": r.get("ext_observed_utc") or r.get("captured_utc") or "",
            "market_note": "",
            "own_p_a": own_a, "own_p_b": own_b,
            "own_basis": r.get("consensus_basis") or "Valve Regional Standings / HLTV ranking points",
            "own_url": url_or_blank(owner_url),
            "pick": (r.get("recommended_pick") or "").strip(),
            "pick_pct": num(r.get("pick_prob")),
            "pick_basis": r.get("pick_confidence") or r.get("consensus_basis") or "",
            "captured_utc": r.get("captured_utc") or "",
            "flags": [f for f in (r.get("flags") or "").split(";") if f.strip()],
        })
    return out


def adapt_openslate(rows):
    """data/08031d30/open_slate.csv -> normalised candidate lines."""
    out = []
    for r in rows:
        fid = (r.get("fixture_id") or "").strip()
        if not fid:
            continue
        odds_a, odds_b = num(r.get("external_odds_a")), num(r.get("external_odds_b"))
        p_a, p_b = num(r.get("p_team_a_pct")), num(r.get("p_team_b_pct"))
        out.append({
            "fixture_id": fid,
            "board": "openslate",
            "team_a": r.get("team_a"), "team_b": r.get("team_b"),
            "kickoff_utc": r.get("kickoff_utc"), "lock_utc": r.get("kickoff_utc"),
            "competition": r.get("competition"), "tier": r.get("tier"),
            "hotspawn_match_url": r.get("hotspawn_match_url") or "",
            "best_of": "", "best_of_source": "",
            "market_book": r.get("external_source") or "",
            "market_odds_a": odds_a, "market_odds_b": odds_b,
            "market_p_a": None, "market_p_b": None,
            "market_url": url_or_blank(r.get("external_url")),
            "market_captured_utc": r.get("external_read_utc") or "",
            "market_note": r.get("external_status") or "",
            "own_p_a": num(r.get("own_p_team_a_pct")), "own_p_b": num(r.get("own_p_team_b_pct")),
            "own_basis": r.get("own_basis") or "",
            "own_url": "",
            "pick": (r.get("pick") or "").strip(), "pick_pct": p_a if (r.get("pick") or "").strip() == (r.get("team_a") or "").strip() else (p_b if p_a is not None else None),
            "pick_basis": r.get("pick_basis") or "",
            "captured_utc": r.get("external_read_utc") or "",
            "flags": [f for f in (r.get("flags") or "").split(";") if f.strip()],
        })
    return out


def adapt_cs2(rows):
    """cs2/data/analysis.csv (session a174d77f). Column names are read defensively:
    anything not found stays None and is flagged, never guessed."""
    if not rows:
        return []
    cols = set(rows[0].keys())

    def pick_col(*candidates):
        for c in candidates:
            if c in cols:
                return c
        return None

    c_id = pick_col("fixture_id", "hotspawn_id", "match_id", "id")
    c_a = pick_col("team_a", "team1", "home")
    c_b = pick_col("team_b", "team2", "away")
    c_kick = pick_col("start_utc", "kickoff_utc", "commence_utc")
    c_lock = pick_col("lock_utc", "lock_time_utc")
    c_comp = pick_col("competition", "tournament", "league")
    c_tier = pick_col("tier",)
    c_url = pick_col("hotspawn_match_url", "match_url", "hotspawn_url")
    c_bo = pick_col("best_of", "series_format", "format")
    c_mbook = pick_col("market_book", "book", "bookmaker", "market_source")
    c_modds_a = pick_col("market_odds_a", "odds_a", "ext_odds_a")
    c_modds_b = pick_col("market_odds_b", "odds_b", "ext_odds_b")
    c_mp_a = pick_col("market_p_a_pct", "market_p_a", "ext_p_a")
    c_mp_b = pick_col("market_p_b_pct", "market_p_b", "ext_p_b")
    c_murl = pick_col("market_url", "market_source_url", "ext_source_url", "source_url")
    c_mcap = pick_col("market_captured_utc", "captured_utc", "read_utc")
    c_own_a = pick_col("own_p_a_pct", "own_p_a", "model_p_a")
    c_own_b = pick_col("own_p_b_pct", "own_p_b", "model_p_b")
    c_own_basis = pick_col("own_basis", "model_basis", "basis")
    c_own_url = pick_col("rating_valve_url", "own_source_url", "vrs_url_a", "vrs_url", "rating_url")
    c_poly_a = pick_col("poly_p_a_pct",)
    c_poly_b = pick_col("poly_p_b_pct",)
    c_poly_url = pick_col("poly_url",)
    c_pick = pick_col("pick", "recommended_pick", "model_pick")
    _ = pick_col
    c_pickpct = pick_col("pick_pct", "pick_prob", "pick_probability")
    out = []
    if not (c_id and c_a and c_b):
        return out
    for r in rows:
        fid = (r.get(c_id) or "").strip()
        if not fid:
            continue
        odds_a = num(r.get(c_modds_a)) if c_modds_a else None
        odds_b = num(r.get(c_modds_b)) if c_modds_b else None
        p_a = num(r.get(c_mp_a)) if c_mp_a else None
        p_b = num(r.get(c_mp_b)) if c_mp_b else None
        if p_a is None and odds_a and odds_b:
            p_a, p_b, _ = de_vig(odds_a, odds_b)
        if p_a is not None and p_b is None:
            p_b = 100.0 - p_a
        out.append({
            "fixture_id": fid, "board": "cs2",
            "team_a": r.get(c_a), "team_b": r.get(c_b),
            "kickoff_utc": r.get(c_kick) if c_kick else None,
            "lock_utc": r.get(c_lock) if c_lock else None,
            "competition": r.get(c_comp) if c_comp else None,
            "tier": r.get(c_tier) if c_tier else None,
            "hotspawn_match_url": (r.get(c_url) or "") if c_url else "",
            "best_of": normalize_bo(str(r.get(c_bo)) if c_bo and r.get(c_bo) else ""),
            "best_of_source": "",
            "market_book": (r.get(c_mbook) or "") if c_mbook else "",
            "market_odds_a": odds_a, "market_odds_b": odds_b,
            "market_p_a": p_a, "market_p_b": p_b,
            "market_url": url_or_blank(r.get(c_murl)) if c_murl else "",
            "market_captured_utc": (r.get(c_mcap) or "") if c_mcap else "",
            "market_note": "",
            "own_p_a": num(r.get(c_own_a)) if c_own_a else None,
            "own_p_b": num(r.get(c_own_b)) if c_own_b else None,
            "own_basis": (r.get(c_own_basis) or "") if c_own_basis else "",
            "own_url": url_or_blank(r.get(c_own_url)) if c_own_url else "",
            "pick": (r.get(c_pick) or "").strip() if c_pick else "",
            "pick_pct": num(r.get(c_pickpct)) if c_pickpct else None,
            "pick_basis": (r.get("pick_basis") or r.get(c_own_basis) or "") if (c_own_basis or "pick_basis" in cols) else "",
            "captured_utc": (r.get(c_mcap) or "") if c_mcap else "",
            "poly_p_a": num(r.get(c_poly_a)) if c_poly_a else None,
            "poly_p_b": num(r.get(c_poly_b)) if c_poly_b else None,
            "poly_url": url_or_blank(r.get(c_poly_url)) if c_poly_url else "",
            "flags": [],
        })
    return out


def adapt_everypick(rows):
    """data/fbcccda2/every_pick.csv -> normalised candidate lines.

    Rows whose pick tier is A/B come from an external market, so their odds/prices are market evidence;
    tier C rows are the board's own model; tier D rows carry no percentage at all (published as a lean)."""
    out = []
    for r in rows:
        fid = (r.get("fixture_id") or "").strip()
        if not fid:
            continue
        tier = (r.get("pick_tier") or "").strip().upper()
        odds_a, odds_b = num(r.get("odds_a")), num(r.get("odds_b"))
        p_a = p_b = None
        if tier in ("A", "B") and r.get("p_a_pct"):
            p_a, p_b = num(r.get("p_a_pct")), num(r.get("p_b_pct"))
            if p_a is None and odds_a and odds_b:
                p_a, p_b, _ = de_vig(odds_a, odds_b)
        model_a, model_b = num(r.get("model_p_a_pct")), num(r.get("model_p_b_pct"))
        if tier == "C" and model_a is not None:
            model_a, model_b = model_a, model_b
        out.append({
            "fixture_id": fid, "board": "everypick",
            "team_a": r.get("team_a"), "team_b": r.get("team_b"),
            "kickoff_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
            "competition": r.get("tournament"), "tier": r.get("tier_hotspawn"),
            "hotspawn_match_url": url_or_blank(r.get("hotspawn_url")),
            "best_of": normalize_bo(r.get("series_format")),
            "best_of_source": url_or_blank(r.get("hltv_match_url")),
            "market_book": r.get("market_book") or "",
            "market_odds_a": odds_a if tier in ("A", "B") else None,
            "market_odds_b": odds_b if tier in ("A", "B") else None,
            "market_p_a": p_a, "market_p_b": p_b,
            "market_url": url_or_blank(r.get("market_url")),
            "market_captured_utc": r.get("market_captured_utc") or "",
            "market_note": (r.get("pick_basis") if tier in ("A", "B") else ""),
            "own_p_a": model_a, "own_p_b": model_b,
            "own_basis": r.get("model_method") or "",
            "own_url": url_or_blank(r.get("vrs_url_a")) or url_or_blank(r.get("hltv_team_url_a")),
            "pick": (r.get("pick") or "").strip(),
            "pick_pct": num(r.get("pick_pct")),
            "pick_basis": r.get("pick_basis") or "",
            "captured_utc": r.get("snapshot_utc") or "",
            "flags": [f for f in (r.get("flags") or "").split(";") if f.strip()],
        })
    return out


ADAPTERS = {"slate": adapt_slate, "everypick": adapt_everypick, "oct14": adapt_oct14, "openslate": adapt_openslate, "cs2": adapt_cs2}


# --------------------------------------------------------------------------------------
# selection policy
# --------------------------------------------------------------------------------------
def market_class(book: str) -> str:
    text = (book or "").lower()
    if not text:
        return ""
    if any(d in text for d in DIRECT_BOOKS):
        return "direct"
    if any(s in text for s in SECONDARY_MARKS):
        return "secondary"
    return "other"


def candidate_lines(cands):
    """Split a fixture's board rows into market / model candidates, newest first."""
    markets, models = [], []
    for c in cands:
        if c.get("market_p_a") is not None and c.get("market_p_b") is not None and market_class(c["market_book"]):
            markets.append(c)
        if c.get("own_p_a") is not None and c.get("own_p_b") is not None:
            models.append(c)
    key = lambda c: parse_iso(c.get("market_captured_utc") or c.get("captured_utc") or "") or datetime.min.replace(tzinfo=timezone.utc)
    markets.sort(key=key, reverse=True)
    models.sort(key=lambda c: parse_iso(c.get("captured_utc") or "") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return markets, models


def select_line(fixture, cands):
    """Return the published line for one fixture, with its basis and sources.

    Precedence (documented on exec/methodology.html):
      1. direct bookmaker price (Pinnacle guest response)
      2. bookmaker price mediated by an aggregator (bc.game via EGamersWorld)
      3. our own line originated from official ratings (HLTV ranking / Valve VRS)
      4. nothing -> blank + flag
    """
    markets, models = candidate_lines(cands)
    direct = [m for m in markets if market_class(m["market_book"]) == "direct"]
    secondary = [m for m in markets if market_class(m["market_book"]) == "secondary"]
    other = [m for m in markets if market_class(m["market_book"]) == "other"]
    chosen = (direct or secondary or other or [None])[0]
    model = models[0] if models else None

    poly = None
    for c in cands:
        if c.get("poly_p_a") is not None:
            poly = {"p_a": c["poly_p_a"], "p_b": c["poly_p_b"], "url": c.get("poly_url") or "", "board": c["board"]}
            break

    row = {
        "poly_reference": poly,
        "fixture_id": fixture["fixture_id"],
        "kickoff_utc": fixture.get("start_utc") or fixture.get("kickoff_utc") or "",
        "lock_utc": fixture.get("lock_utc") or "",
        "competition": fixture.get("competition") or "",
        "tier": (fixture.get("tier") or "").upper(),
        "team_a": fixture.get("team_a") or "",
        "team_b": fixture.get("team_b") or "",
        "hotspawn_match_url": fixture.get("hotspawn_match_url") or "",
        "hotspawn_fixture_url": "https://play.hotspawn.com/cs2-pickems",
        "best_of": "", "best_of_source": "",
        "market_book": "", "market_class": "", "market_odds_a": None, "market_odds_b": None,
        "market_p_a": None, "market_p_b": None, "market_url": "", "market_captured_utc": "",
        "market_board": "", "market_page": "", "market_note": "",
        "own_p_a": None, "own_p_b": None, "own_basis": "", "own_url": "", "own_board": "", "own_page": "",
        "line_source": "none", "p_a": None, "p_b": None,
        "pick": "", "pick_pct": None, "pick_basis": "", "pick_source_url": "", "pick_board": "", "pick_page": "",
        "boards_publishing": {}, "disagreements": [], "flags": [],
    }

    if chosen:
        row.update({
            "market_book": chosen.get("market_book", ""),
            "market_class": market_class(chosen.get("market_book", "")),
            "market_odds_a": chosen.get("market_odds_a"), "market_odds_b": chosen.get("market_odds_b"),
            "market_p_a": round(chosen["market_p_a"], 2), "market_p_b": round(chosen["market_p_b"], 2),
            "market_url": chosen.get("market_url", ""), "market_captured_utc": chosen.get("market_captured_utc", ""),
            "market_board": chosen["board"], "market_page": board_page(chosen["board"]),
            "market_note": chosen.get("market_note", ""),
        })
        row["line_source"] = "market-" + row["market_class"]
        row["p_a"], row["p_b"] = row["market_p_a"], row["market_p_b"]
    if model:
        row.update({
            "own_p_a": round(model["own_p_a"], 2), "own_p_b": round(model["own_p_b"], 2),
            "own_basis": model.get("own_basis", ""), "own_url": model.get("own_url", ""),
            "own_board": model["board"], "own_page": board_page(model["board"]),
        })
        if row["line_source"] == "none":
            row["line_source"] = "model"
            row["p_a"], row["p_b"] = row["own_p_a"], row["own_p_b"]

    # series format: publish only what a board sourced (never assumed)
    for c in cands:
        if c.get("best_of"):
            row["best_of"] = normalize_bo(c["best_of"])
            row["best_of_source"] = c.get("best_of_source") or board_page(c["board"])
            break

    # pick + basis
    if row["p_a"] is not None and row["p_b"] is not None:
        if row["p_a"] >= row["p_b"]:
            row["pick"], row["pick_pct"] = row["team_a"], row["p_a"]
        else:
            row["pick"], row["pick_pct"] = row["team_b"], row["p_b"]
        if row["line_source"].startswith("market-"):
            row["pick_basis"] = (
                "external bookmaker price, de-vigged"
                + (" (direct)" if row["line_source"] == "market-direct" else " (aggregator-mediated)")
            )
            row["pick_source_url"] = row["market_url"]
            row["pick_board"], row["pick_page"] = row["market_board"], row["market_page"]
        else:
            row["pick_basis"] = "our own line from official ratings, no bookmaker price found"
            row["pick_source_url"] = row["own_url"]
            row["pick_board"], row["pick_page"] = row["own_board"], row["own_page"]

    # board-by-board publication record (coverage audit)
    for c in cands:
        board = c["board"]
        entry = row["boards_publishing"].setdefault(board, {"market": False, "model": False, "pick": False})
        if c.get("market_p_a") is not None and market_class(c.get("market_book")):
            entry["market"] = True
        if c.get("own_p_a") is not None:
            entry["model"] = True
        if c.get("pick"):
            entry["pick"] = True

    # disagreements between the two independent inputs and between boards
    if row["market_p_a"] is not None and row["own_p_a"] is not None:
        gap = abs(row["market_p_a"] - row["own_p_a"])
        if gap >= 10:
            row["disagreements"].append(
                f"market {row['market_p_a']:.0f}% vs our model {row['own_p_a']:.0f}% for {row['team_a']} ({gap:.0f} pp)")
    by_book = {}
    for c in markets:
        key = re.sub(r"[^a-z]", "", (c.get("market_book") or "").lower())[:12]
        by_book.setdefault(key, []).append(round(c["market_p_a"], 1))
    market_vals = sorted({round(c["market_p_a"], 1) for c in markets})
    if len(market_vals) > 1 and (market_vals[-1] - market_vals[0]) >= 10:
        row["disagreements"].append(
            f"the boards' outside prices differ by {market_vals[-1] - market_vals[0]:.0f} pp "
            f"({market_vals[0]:.0f}%–{market_vals[-1]:.0f}% for {row['team_a']})")
    for book, vals in by_book.items():
        if len(vals) > 1 and (max(vals) - min(vals)) >= 10:
            row["disagreements"].append(
                f"same bookmaker listed with conflicting prices across boards: {min(vals):.0f}%–{max(vals):.0f}% "
                f"for {row['team_a']}")
    model_vals = sorted({round(c["own_p_a"], 1) for c in models})
    if len(model_vals) > 1 and (model_vals[-1] - model_vals[0]) >= 10:
        row["disagreements"].append(
            f"our own lines differ between boards: {model_vals[0]:.0f}%–{model_vals[-1]:.0f}% for {row['team_a']}")

    # do the boards actually pick different sides?
    board_picks = {}
    for c in cands:
        pick = (c.get("pick") or "").strip()
        if pick:
            board_picks.setdefault(c["board"], pick)
    distinct = set(board_picks.values())
    if len(distinct) > 1:
        detail = ", ".join(f"{board}: {pick}" for board, pick in sorted(board_picks.items()))
        same_as_ours = row["pick"] in distinct
        row["disagreements"].append(
            ("boards name different winners — " if not same_as_ours else "boards name different winners — ")
            + detail + (f" (this page: {row['pick']})" if row["pick"] else " (this page: no pick)"))
    if row.get("poly_p_a") is not None:
        row["poly_reference"] = {
            "p_a": row["poly_p_a"], "p_b": row["poly_p_b"], "url": row.get("poly_url") or "",
        }

    # flags
    if row["line_source"] == "none":
        row["flags"].append({
            "code": "X-NO-BASIS",
            "severity": "unverified",
            "text": "No bookmaker price and no official rating for at least one team. Pick left blank.",
        })
    if row["line_source"] == "model":
        row["flags"].append({
            "code": "X-MODEL-ONLY",
            "severity": "caveat",
            "text": "No bookmaker prices this match outside Hotspawn; the pick is our own line from official ratings only.",
        })
    if row["line_source"] == "market-secondary":
        row["flags"].append({
            "code": "X-SECONDARY-PRICE",
            "severity": "caveat",
            "text": "Price comes from a bookmaker listing served by an aggregator, not from the bookmaker's own response.",
        })
    if not row["best_of"]:
        row["flags"].append({
            "code": "X-FORMAT-UNVERIFIED",
            "severity": "caveat",
            "text": "Series format not confirmed by a sourced match page; the line is a match-level estimate.",
        })
    for cand in cands:
        for f in cand.get("flags", []):
            if f and f not in {x["text"] for x in cands[0].get("_seen", [])}:
                pass
    if chosen and chosen.get("market_odds_a") and chosen.get("market_odds_b"):
        if abs(chosen["market_odds_a"] - chosen["market_odds_b"]) < 0.005:
            row["flags"].append({
                "code": "X-IDENTICAL-ODDS",
                "severity": "unverified",
                "text": "Both prices are identical, which is the shape of a placeholder listing rather than a priced market.",
            })
    return row


def board_page(board_id: str):
    for b in BOARDS:
        if b["id"] == board_id:
            return b["page"]
    return ""


def board_meta(board_id: str):
    for b in BOARDS:
        if b["id"] == board_id:
            return b
    return {}


# --------------------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------------------
def load_fixtures():
    """Identity spine: Hotspawn fixture id / teams / kickoff / lock, with the board that
    captured it. slate/data/fixtures.csv is the hourly collector's payload dump."""
    path, rows = read_csv("slate/data/fixtures.csv")
    spine, source = {}, None
    if rows:
        source = "slate/data/fixtures.csv"
        for r in rows:
            if (r.get("sport") or "").lower() != "cs2":
                continue
            fid = (r.get("fixture_id") or "").strip()
            if not fid:
                continue
            spine[fid] = {
                "fixture_id": fid,
                "team_a": r.get("team_a"), "team_b": r.get("team_b"),
                "start_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
                "competition": r.get("competition"), "tier": r.get("tier"),
                "hotspawn_match_url": r.get("hotspawn_match_url") or "",
                "captured_utc": r.get("captured_utc") or "",
                "live_status": r.get("live_status") or "",
                "source": source,
            }
    if not spine:
        _, rows = read_csv("data/8944bb84/fixtures.csv")
        if rows:
            source = "data/8944bb84/fixtures.csv"
            for r in rows:
                fid = (r.get("match_id") or r.get("fixture_id") or "").strip()
                if not fid:
                    continue
                spine[fid] = {
                    "fixture_id": fid,
                    "team_a": r.get("team_a"), "team_b": r.get("team_b"),
                    "start_utc": r.get("start_utc"), "lock_utc": r.get("lock_utc"),
                    "competition": r.get("tournament") or r.get("competition"),
                    "tier": r.get("tier"),
                    "hotspawn_match_url": r.get("hotspawn_match_url") or "",
                    "captured_utc": r.get("captured_utc") or "",
                    "live_status": r.get("status") or "",
                    "source": source,
                }
    return spine, source


def load_candidates():
    cands = {}
    per_board = {}
    for board in BOARDS:
        path, rows = read_csv(board["path"])
        if not rows:
            per_board[board["id"]] = {"rows": 0, "present": False, "path": board["path"]}
            continue
        adapted = ADAPTERS[board["id"]](rows)
        per_board[board["id"]] = {"rows": len(adapted), "present": True, "path": board["path"]}
        for c in adapted:
            cands.setdefault(c["fixture_id"], []).append(c)
    return cands, per_board


def build():
    spine, spine_source = load_fixtures()
    cands, per_board = load_candidates()
    now = utcnow()

    open_rows, locked_rows = [], []
    for fid, fx in spine.items():
        lock = parse_iso(fx.get("lock_utc") or "")
        if not lock:
            continue
        row = select_line(fx, cands.get(fid, []))
        row["state"] = "open" if lock > now else "locked_or_started"
        (open_rows if row["state"] == "open" else locked_rows).append(row)

    open_rows.sort(key=lambda r: r["kickoff_utc"] or "")
    locked_rows.sort(key=lambda r: r["kickoff_utc"] or "", reverse=True)

    with_market = [r for r in open_rows if r["line_source"].startswith("market-")]
    direct = [r for r in open_rows if r["line_source"] == "market-direct"]
    model_only = [r for r in open_rows if r["line_source"] == "model"]
    no_basis = [r for r in open_rows if r["line_source"] == "none"]
    with_pick = [r for r in open_rows if r["pick"]]
    flagged = [r for r in open_rows if r["flags"]]
    disagreements = [r for r in open_rows if r["disagreements"]]

    inventory = {"payload_rows": len(spine), "open": len(open_rows), "locked_or_started": len(locked_rows)}
    stale = 0
    for fid, fx in spine.items():
        start = parse_iso(fx.get("start_utc") or "")
        if start and (now - start).days > 1:
            stale += 1
    inventory["stale_over_a_day"] = stale
    inventory["started_within_a_day"] = len(locked_rows) - stale

    totals = {
        "open_fixtures": len(open_rows),
        "with_pick": len(with_pick),
        "with_market": len(with_market),
        "with_market_direct": len(direct),
        "with_market_secondary": len(with_market) - len(direct),
        "model_only": len(model_only),
        "no_basis": len(no_basis),
        "flagged_rows": len(flagged),
        "disagreement_rows": len(disagreements),
        "locked_or_started": len(locked_rows),
        "inventory": inventory,
    }

    boards_meta = []
    for board in BOARDS:
        info = per_board[board["id"]]
        captured = ""
        for c in cands.values():
            for row in c:
                if row["board"] == board["id"]:
                    stamp = row.get("captured_utc") or row.get("market_captured_utc") or ""
                    if stamp > captured:
                        captured = stamp
        sidecar = board.get("captured_from") or {}
        sidecar_stamp = ""
        if sidecar.get("path"):
            sp = os.path.join(ROOT, sidecar["path"])
            if os.path.exists(sp) and sidecar.get("key") and sp.endswith(".json"):
                try:
                    with open(sp, encoding="utf-8") as fh:
                        data = json.load(fh)
                    sidecar_stamp = str(data.get(sidecar["key"]) or "")
                except Exception:
                    sidecar_stamp = ""
        boards_meta.append({
            **{k: board[k] for k in ("id", "name", "path", "page", "flagged", "method", "owner", "what")},
            "captured_sidecar": sidecar_stamp,
            "present": info["present"],
            "rows": info["rows"],
            "captured_utc": sidecar_stamp or captured,
            "open_rows_with_pick": sum(1 for r in open_rows if r["boards_publishing"].get(board["id"], {}).get("pick")),
            "open_rows_covered": sum(1 for r in open_rows if board["id"] in r["boards_publishing"]),
        })

    payload = {
        "generated_utc": iso(now),
        "fixture_spine": spine_source,
        "totals": totals,
        "boards": boards_meta,
        "open": open_rows,
        "locked_or_started": [{k: v for k, v in r.items() if k not in ("boards_publishing",)} for r in locked_rows],
        "policy": {
            "precedence": [
                "1. direct bookmaker price (the book's own response) → de-vigged",
                "2. bookmaker price served through an aggregator → de-vigged, labelled",
                "3. our own line originated from official ratings (HLTV world ranking / Valve Regional Standings)",
                "4. no basis → blank + flagged",
            ],
            "never_used": "Hotspawn's own crowd pick percentage is never read or published by this board.",
        },
    }
    return payload, per_board, spine


# --------------------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------------------
def fmt_pct(value):
    return "—" if value is None else f"{value:.1f}%"


def fmt_time(value):
    dt = parse_iso(value or "")
    if not dt:
        return "—"
    return dt.strftime("%b %d, %H:%M UTC")


def stale_hours(iso_text):
    dt = parse_iso(iso_text or "")
    if not dt:
        return None
    return (utcnow() - dt).total_seconds() / 3600.0


def link(url, label):
    if not url:
        return esc(label)
    return f'<a href="{esc(url)}" rel="noopener">{esc(label)}</a>'


def format_source_html(source: str) -> str:
    """The format column cites either a URL or a board's own sentence; print whichever it is."""
    text = (source or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return " · " + link(text, "source")
    page = format_source_page(text)
    if page:
        return " · " + repo_link(page, esc(text))
    return " · " + esc(text)


def format_source_page(text: str) -> str:
    if not text:
        return ""
    low = text.lower()
    if "hltv" in low:
        return "https://www.hltv.org/matches"
    if "pinnacle" in low:
        return "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
    if "valve" in low:
        return "https://github.com/ValveSoftware/counter-strike_regional_standings"
    if "egamersworld" in low or "egw" in low:
        return "https://egamersworld.com/counterstrike/matches"
    return ""


def repo_link(path, label):
    """Links from exec/ to a repo-root-relative page."""
    if not path:
        return esc(label)
    if path.startswith(("http://", "https://", "../")):
        return f'<a href="{esc(path)}" rel="noopener">{esc(label)}</a>'
    return f'<a href="../{esc(path)}" rel="noopener">{esc(label)}</a>'


def row_card(r):
    basis = r["pick_basis"] or "no basis published"
    src = r["pick_source_url"]
    tier_label = {"market-direct": "bookmaker price (direct)", "market-secondary": "bookmaker price (aggregator)",
                  "market-other": "bookmaker price (other listing)", "model": "our line from official ratings",
                  "none": "no basis"}[r["line_source"]]
    flags = "".join(f'<li>{esc(f["text"])}</li>' for f in r["flags"])
    disc = "".join(f'<li>{esc(d)}</li>' for d in r["disagreements"])
    market_detail = "—"
    if r["market_p_a"] is not None:
        market_detail = f'{fmt_pct(r["market_p_a"])} / {fmt_pct(r["market_p_b"])} ({esc(r["market_book"] or "book")})'
        if r["market_odds_a"] and r["market_odds_b"]:
            market_detail += f' · odds {r["market_odds_a"]:.3f} / {r["market_odds_b"]:.3f}'
    own_detail = "—"
    if r["own_p_a"] is not None:
        own_detail = f'{fmt_pct(r["own_p_a"])} / {fmt_pct(r["own_p_b"])}'
    bo = esc(r["best_of"] or "not sourced")
    poly = r.get("poly_reference")
    poly_detail = "—"
    if poly:
        poly_detail = (f'{fmt_pct(poly["p_a"])} / {fmt_pct(poly["p_b"])} (prediction market, not a bookmaker)'
                       + ((' · ' + link(poly["url"], "market")) if poly.get("url") else ""))
    pick_html = (f'<span class="pick">{esc(r["pick"])} {fmt_pct(r["pick_pct"])}</span>'
                 if r["pick"] else '<span class="pick none">no pick</span>')
    return f'''
<article class="card fixture" data-fixture="{esc(r['fixture_id'])}" data-lock="{esc(r['lock_utc'])}">
  <header>
    <div class="when">{fmt_time(r['kickoff_utc'])}<span class="tier">{esc(r['tier'] or '?')}-tier</span></div>
    <div class="comp">{esc(r['competition'])}</div>
    <h3>{esc(r['team_a'])} <span class="vs">vs</span> {esc(r['team_b'])}</h3>
  </header>
  <div class="probs">
    <div class="{ 'side lead' if r['p_a'] is not None and r['p_b'] is not None and r['p_a'] >= r['p_b'] else 'side' }">
      <span class="team">{esc(r['team_a'])}</span><span class="pct">{fmt_pct(r['p_a'])}</span>
    </div>
    <div class="{ 'side lead' if r['p_a'] is not None and r['p_b'] is not None and r['p_b'] > r['p_a'] else 'side' }">
      <span class="team">{esc(r['team_b'])}</span><span class="pct">{fmt_pct(r['p_b'])}</span>
    </div>
  </div>
  <p class="pickline">Pick: {pick_html} <span class="basis">· {esc(tier_label)}</span></p>
  <dl class="detail">
    <dt>Basis</dt><dd>{esc(basis)}{(' · ' + link(src, 'source')) if src else ' · <span class="warn">no source</span>'}</dd>
    <dt>Market</dt><dd>{market_detail}{(' · ' + link(r['market_url'], 'quote')) if r['market_url'] else ''}{(' · ' + repo_link(r['market_page'], 'board')) if r['market_page'] else ''}</dd>
    <dt>Our line</dt><dd>{own_detail}{(' · ' + link(r['own_url'], 'ratings')) if r['own_url'] else ''}{(' · ' + repo_link(r['own_page'], 'board')) if r['own_page'] else ''}</dd>
    <dt>Format</dt><dd>{bo}{format_source_html(r['best_of_source'])}</dd>
    <dt>Match</dt><dd>{link(r['hotspawn_match_url'], 'Hotspawn')} · {repo_link(r['pick_page'], 'board row')}</dd>
  </dl>
  {(f'<ul class="flags">{flags}</ul>') if flags else ''}
  {(f'<ul class="disagree">{disc}</ul>') if disc else ''}
</article>'''


def render_index(payload):
    t = payload["totals"]
    inv = t["inventory"]
    boards = payload["boards"]
    cover = t["with_pick"] / t["open_fixtures"] * 100 if t["open_fixtures"] else 0
    age = stale_hours(payload["generated_utc"])
    age_text = f"{age:.1f} h" if age is not None else "unknown"

    board_rows = ""
    for b in sorted(boards, key=lambda x: (not x["present"], -x["open_rows_with_pick"])):
        state = "live" if b["present"] else "missing"
        board_rows += f'''
    <li class="board {state}">
      <a class="board-link" href="../{esc(b['page'])}">
        <span class="board-name">{esc(b['name'])}</span>
        <span class="board-meta">{b['open_rows_with_pick']}/{t['open_fixtures']} open matches picked · rows {b['rows']} · captured {esc(b['captured_utc'] or 'unknown')}</span>
      </a>
      <p class="board-what">{esc(b['what'])}</p>
      <p class="board-links">{repo_link(b['page'], 'Open board')} · {repo_link(b['method'], 'Method')} · {repo_link(b['flagged'], 'Flagged')}</p>
    </li>'''

    cards = "\n".join(row_card(r) for r in payload["open"]) or '<p class="empty">No open CS2 fixture in the captured payload.</p>'

    flag_list = ""
    for r in payload["open"]:
        for f in r["flags"]:
            flag_list += (f'<li><span class="code">{esc(f["code"])}</span> {esc(r["team_a"])} vs {esc(r["team_b"])}: '
                          f'{esc(f["text"])}</li>')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0b1220">
<title>Today's CS2 picks — executive summary</title>
<meta name="description" content="Mobile-first executive summary: where the Hotspawn CS2 pick'em picks are published, what they are, and every unverified item.">
<link rel="stylesheet" href="style.css">
</head>
<body>
<a class="skip" href="#picks">Skip to the picks</a>
<header class="top">
  <p class="eyebrow">Hotspawn CS2 Pick'em · independent analysis</p>
  <h1>Today's picks, in one place</h1>
  <p class="lede">Every open Counter-Strike 2 match on the Hotspawn Pick'em board, the pick we publish for it,
  how likely each side is to win and the source behind each number. Tap any board below to see the same
  rows in full.</p>
  <p class="stamp">Generated <strong id="generated">{esc(payload['generated_utc'])}</strong> · age {esc(age_text)} ·
    <a href="coverage.html">coverage audit</a> · <a href="methodology.html">method</a> ·
    <a href="sources.html">sources</a> · <a href="flagged.html">Flagged for review</a></p>
  <p class="auto">Refresh: hourly GitHub Action (<a href="https://github.com/buffedlizard55-lab/MaltaProj1/actions/workflows/exec-3b5e3fea.yml">runs</a>).
  Nothing here is typed in by hand; a row that has no source is blank.</p>
</header>

<main>
  <p class="note">Hotspawn's CS2 board also still lists {inv['locked_or_started']} rows that are already locked or
  started ({inv['stale_over_a_day']} of them over a day old). Those cannot be picked any more and are counted on the
  <a href="coverage.html">coverage audit</a>, not listed as picks.</p>

  <section class="tiles" aria-label="Coverage at a glance">
    <div class="tile"><span class="n">{t['open_fixtures']}</span><span class="l">open matches listed</span></div>
    <div class="tile good"><span class="n">{t['with_pick']}</span><span class="l">with a published pick ({cover:.0f}%)</span></div>
    <div class="tile"><span class="n">{t['with_market']}</span><span class="l">with an outside price ({t['with_market_direct']} direct, {t['with_market_secondary']} aggregator)</span></div>
    <div class="tile"><span class="n">{t['model_only']}</span><span class="l">our line only (no book prices them)</span></div>
    <div class="tile {'bad' if t['no_basis'] else ''}"><span class="n">{t['no_basis']}</span><span class="l">with no basis at all</span></div>
    <div class="tile {'warn' if t['flagged_rows'] else ''}"><span class="n">{t['flagged_rows']}</span><span class="l">rows carrying a flag</span></div>
  </section>

  <section aria-labelledby="where">
    <h2 id="where">Where the picks are</h2>
    <p class="note">These are this repository's own boards. They overlap on purpose: if one collector is
    blocked or stale, the others still carry the row. The audit page shows, per match, which boards publish
    what, so you can see a gap instead of guessing.</p>
    <ul class="boards">{board_rows}</ul>
  </section>

  <section id="picks" aria-labelledby="picks-h">
    <h2 id="picks-h">Every open match and its pick</h2>
    <p class="note">Pick = the side with the higher probability on the published line. Where a bookmaker prices
    the match, that price decides; only when no book prices it does our own line from official ratings decide.
    Both are always shown.</p>
    <div class="cards" id="cards">{cards}</div>
  </section>

  <section aria-labelledby="flags-h">
    <h2 id="flags-h">Unverified items on this page</h2>
    <ul class="flags big">{flag_list or '<li>None.</li>'}</ul>
    <p class="note">Everything else here is carried with the source it came from. The full list of review items
    across all boards is on the <a href="flagged.html">Flagged for review</a> page.</p>
  </section>
</main>

<footer>
  <p>Analysis only, not betting advice. Not affiliated with Hotspawn. Hotspawn is used for fixture identity
  only — its crowd pick percentages are never an input.</p>
  <p><a href="https://play.hotspawn.com/cs2-pickems">Official Hotspawn CS2 Pick'em board</a> ·
  <a href="../index.html">All research boards</a> ·
  <a href="https://github.com/buffedlizard55-lab/MaltaProj1">Repository</a></p>
</footer>
<script src="app.js" defer></script>
</body>
</html>
'''


def render_coverage(payload):
    boards = [b for b in payload["boards"]]
    head = "".join(f'<th scope="col">{esc(b["name"])}</th>' for b in boards)
    inv = payload["totals"]["inventory"]
    inv_block = f"""<section class="tiles" aria-label="Board inventory">
    <div class="tile"><span class="n">{inv['payload_rows']}</span><span class="l">CS2 rows in the payload</span></div>
    <div class="tile good"><span class="n">{inv['open']}</span><span class="l">still open (the rows below)</span></div>
    <div class="tile"><span class="n">{inv['locked_or_started']}</span><span class="l">locked or started</span></div>
    <div class="tile"><span class="n">{inv['stale_over_a_day']}</span><span class="l">stale by more than a day</span></div>
  </section>"""
    rows = ""
    for r in payload["open"]:
        cells = ""
        for b in boards:
            pub = r["boards_publishing"].get(b["id"])
            if not pub:
                cells += '<td class="no" data-label="%s">—</td>' % esc(b["name"])
            else:
                bits = []
                if pub["market"]:
                    bits.append("price")
                if pub["model"]:
                    bits.append("own line")
                if pub["pick"]:
                    bits.append("pick")
                cells += f'<td class="yes" data-label="{esc(b["name"])}">{" + ".join(bits) or "row only"}</td>'
        rows += f'''<tr>
      <td data-label="Kickoff">{fmt_time(r['kickoff_utc'])}</td>
      <td data-label="Match">{esc(r['team_a'])} vs {esc(r['team_b'])}</td>
      <td data-label="This board's pick">{esc(r['pick'] or '—')} {fmt_pct(r['pick_pct']) if r['pick'] else ''}</td>
      <td data-label="Basis">{esc({'market-direct': 'book (direct)', 'market-secondary': 'book (aggregator)', 'market-other': 'book (other)', 'model': 'our line only', 'none': 'none'}[r['line_source']])}</td>
      {cells}
    </tr>'''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coverage audit — every open match, every board</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <p class="eyebrow"><a href="index.html">← executive summary</a></p>
  <h1>Coverage audit</h1>
  <p class="lede">One row per open CS2 fixture in the captured Hotspawn payload, one column per board in this
  repository. "price" = the board publishes a bookmaker price for that match, "own line" = it publishes a line
  built from official ratings, "pick" = it names a side. A dash means that board has nothing for that match —
  which is the gap this page exists to show.</p>
  <p class="stamp">Generated {esc(payload['generated_utc'])} · spine: <code>{esc(payload['fixture_spine'] or 'n/a')}</code></p>
  <p class="note">Hotspawn's CS2 payload in that capture holds <strong>{inv['payload_rows']}</strong> rows:
  <strong>{inv['open']}</strong> still open, <strong>{inv['locked_or_started']}</strong> already locked or started
  (<strong>{inv['stale_over_a_day']}</strong> of them by more than a day — summer listings the site still shows as
  "scheduled", which no bookmaker would price; <strong>{inv['started_within_a_day']}</strong> started in the last day).
  Picks are only meaningful for rows that are still open; the rest are counted here so the difference is visible
  rather than quietly dropped.</p>
</header>
<main>
  {inv_block}
  <table class="audit">
    <thead><tr><th scope="col">Kickoff (UTC)</th><th scope="col">Match</th><th scope="col">Pick here</th><th scope="col">Basis</th>{head}</tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p class="note">Board counts: {' · '.join(f"{esc(b['name'])} {b['rows']} rows" for b in boards)}.</p>
</main>
<footer><p><a href="index.html">Executive summary</a> · <a href="flagged.html">Flagged for review</a> ·
<a href="../index.html">All research boards</a></p></footer>
</body>
</html>
'''


POLYMARKET_NOTE = ""


def render_sources(payload, poly):
    poly_rows = ""
    for item in (poly or {}).get("matches", []):
        poly_rows += (f'<tr><td>{esc(item.get("title", ""))}</td><td>{esc(item.get("market_kind", ""))}</td>'
                      f'<td>{fmt_pct(item.get("p_a"))} / {fmt_pct(item.get("p_b"))}</td>'
                      f'<td>{esc(item.get("updated_utc", ""))}</td>'
                      f'<td>{link(item.get("url", ""), "market")}</td></tr>')
    poly_block = ""
    if poly:
        status = poly.get("status", "unknown")
        poly_block = f'''
  <h3>Prediction market (Polymarket) — access status: {esc(status)}</h3>
  <p>Endpoint read by this board's collector: <code>{esc(poly.get('endpoint', ''))}</code> at
  {esc(poly.get('captured_utc', ''))}. {esc(poly.get('note', ''))}</p>
  <p class="note">Fixtures considered: {esc(poly.get('fixtures_considered', ''))} ·
  series markets found: {len(poly.get('matches', []))} ·
  per-map markets found: {len(poly.get('map_markets', []))} (never used as a series probability) ·
  fixtures with no market: {len(poly.get('unmatched', []))} ·
  errors: {len(poly.get('errors', []))}.</p>
  {f'<table class="audit"><thead><tr><th>Market</th><th>Kind</th><th>Implied</th><th>Updated</th><th>Link</th></tr></thead><tbody>{poly_rows}</tbody></table>' if poly_rows else ''}
  {('<p class="note">Per-map markets seen (shown only so their existence is not mistaken for a series line): ' + esc('; '.join(sorted({m.get('question', '') for m in poly.get('map_markets', [])}))[:400]) + '</p>') if poly.get('map_markets') else ''}'''
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sources — the ladder used for matches no book prices</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <p class="eyebrow"><a href="index.html">← executive summary</a></p>
  <h1>Where our numbers come from</h1>
  <p class="lede">The featured matches on the Pick'em board are priced by big bookmakers. Most of the board is
  not: low-tier online cups often have no listed market at all. For those rows this project walks down a
  documented ladder and stops at the first rung that answers, leaving the row blank if none does.</p>
</header>
<main>
  <h2>The ladder</h2>
  <ol class="ladder">
    <li><strong>Direct bookmaker response</strong> — Pinnacle's public guest endpoint
      (<code>guest.api.arcadia.pinnacle.com</code>) that its own CS2 page loads. Read on 2026-10-14 02:34 UTC
      for this session's own verification: <em>verified reachable</em>. Whole-match moneyline only; prices are
      American, converted to decimal, then de-vigged.</li>
    <li><strong>Bookmaker price served through an aggregator</strong> (bc.game prices listed on EGamersWorld).
      Used, but labelled <em>aggregator-mediated</em> on every row, and rejected outright when the listing
      shows a placeholder pair — see the flagged page.</li>
    <li><strong>Prediction market</strong> (Polymarket public API) — an outside market that does list some of
      these low-tier cups. It is a market, not a bookmaker, its low-tier liquidity is thin, and its CS2 events
      are frequently <em>per-map</em> markets, which are not a series probability. This board therefore only
      republishes what the market itself states, with the map/series distinction kept explicit.</li>
    <li><strong>Our own line from official ratings</strong> — Valve Regional Standings (Valve's own published
      standings file) cross-read with the HLTV world ranking. This is the rung that covers the matches no
      bookmaker lists; a team with neither rating leaves the row blank and flagged.</li>
    <li><strong>Nothing</strong> — no price, no rating: the row stays blank, the reason is printed, and it is
      listed on the flagged page. No default 50/50, ever.</li>
  </ol>
  <h2>Official sources this board links to</h2>
  <ul>
    <li>Hotspawn Pick'em board (fixture identity, kickoff and lock epochs only):
      <a href="https://play.hotspawn.com/cs2-pickems">play.hotspawn.com/cs2-pickems</a> and
      <a href="https://play.hotspawn.com/lobby">/lobby</a>.</li>
    <li>Valve Regional Standings (official Valve file):
      <a href="https://github.com/ValveSoftware/counter-strike_regional_standings">github.com/ValveSoftware/counter-strike_regional_standings</a>.</li>
    <li>HLTV world ranking: <a href="https://www.hltv.org/ranking/teams">hltv.org/ranking/teams</a>;
      HLTV match pages for series format and results: <a href="https://www.hltv.org/matches">hltv.org/matches</a>.</li>
    <li>Pinnacle public guest matchups:
      <a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/">pinnacle.com/en/esports/games/cs2/matchups/</a>.</li>
  </ul>
  {poly_block}
  <h2>What this board refuses to do</h2>
  <ul>
    <li>It never reads Hotspawn's crowd pick percentage; that is not a probability.</li>
    <li>It never averages a market price with a model and calls the result a market price.</li>
    <li>It never fills a missing price, rating or series format with an assumption.</li>
    <li>It never publishes a number without the link it came from.</li>
  </ul>
</main>
<footer><p><a href="index.html">Executive summary</a> · <a href="methodology.html">Method</a> ·
<a href="flagged.html">Flagged for review</a></p></footer>
</body>
</html>
'''


def render_methodology(payload):
    t = payload["totals"]
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Method — how the executive summary picks a side</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <p class="eyebrow"><a href="index.html">← executive summary</a></p>
  <h1>Method</h1>
  <p class="lede">Short version: a bookmaker price decides the pick when one exists; otherwise our own line
  from official ratings does; otherwise nothing is published. Every row prints both numbers when both exist,
  so a disagreement is visible rather than averaged away.</p>
</header>
<main>
  <h2>Precedence</h2>
  <ol>{''.join(f'<li>{esc(p)}</li>' for p in payload['policy']['precedence'])}</ol>
  <p class="note">{esc(payload['policy']['never_used'])}</p>

  <h2>The arithmetic</h2>
  <p>Market probability (multiplicative two-way de-vig):</p>
  <pre><code>p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)
overround = (1/odds_A + 1/odds_B) - 1</code></pre>
  <p>Our own line is a logistic transform of the official rating difference, published per row by the board
  that computed it, with that board's rating links attached. This page does not re-fit a model of its own; it
  names whose line it is showing.</p>

  <h2>What each column means</h2>
  <dl class="detail big">
    <dt>Pick</dt><dd>The side with the higher published probability. Blank where nothing is published.</dd>
    <dt>Basis</dt><dd>Which rung of the ladder the pick came from, plus the link.</dd>
    <dt>Market</dt><dd>De-vigged probability implied by the bookmaker price, the book's name, the decimal odds and the quote link.</dd>
    <dt>Our line</dt><dd>The board's own originated probability from official ratings, with the rating link.</dd>
    <dt>Format</dt><dd>BO1/BO3/BO5, printed only when a board sourced it. "not sourced" is printed verbatim otherwise.</dd>
    <dt>Flags</dt><dd>Machine-readable codes; the full list and definitions are on the flagged page.</dd>
  </dl>

  <h2>Freshness and locking</h2>
  <p>This summary is regenerated by <code>.github/workflows/exec-3b5e3fea.yml</code> (hourly, plus on demand).
  The page re-reads <code>data/picks.json</code> in the browser and marks a row locked the moment its lock time
  passes, so a stale cache cannot present a locked match as a live pick. The boards themselves refresh on their
  own schedules — the coverage page shows each board's own capture stamp.</p>

  <h2>Known limits of this page</h2>
  <ul>
    <li>It is an aggregator: if a board upstream is wrong, this page repeats it — with the board named, so the
      claim can be traced and challenged.</li>
    <li>Aggregator-mediated prices (rung 2) are not independently re-read from the bookmaker.</li>
    <li>Rows without a sourced series format are match-level estimates; the same pick may not hold at map level.</li>
    <li>Coverage numbers are of the fixtures the collector captured
      ({t['open_fixtures']} open at {esc(payload['generated_utc'])}); a capture gap upstream becomes a
      visible count here, not a silent omission.</li>
  </ul>
</main>
<footer><p><a href="index.html">Executive summary</a> · <a href="sources.html">Sources</a> ·
<a href="coverage.html">Coverage</a> · <a href="flagged.html">Flagged for review</a></p></footer>
</body>
</html>
'''


def render_flagged(payload, extra_notes):
    groups = {}
    for r in payload["open"]:
        for f in r["flags"]:
            groups.setdefault(f["code"], {"text": f["text"], "severity": f["severity"], "rows": []})
            groups[f["code"]]["rows"].append(f"{r['fixture_id']} {r['team_a']} vs {r['team_b']}")
    rows = ""
    for code, g in sorted(groups.items()):
        rows += (f'<tr><td><span class="code">{esc(code)}</span></td><td>{esc(g["severity"])}</td>'
                 f'<td>{esc(g["text"])}</td><td>{esc("; ".join(g["rows"]))}</td></tr>')
    disc = ""
    for r in payload["open"]:
        for d in r["disagreements"]:
            disc += (f'<li>{r["fixture_id"]} {esc(r["team_a"])} vs {esc(r["team_b"])}: {esc(d)} '
                     f'({repo_link(r["pick_page"], "board row")})</li>')
    notes = "".join(f"<li>{n}</li>" for n in extra_notes)  # pre-escaped upstream
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Flagged for review — executive summary board</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="top">
  <p class="eyebrow"><a href="index.html">← executive summary</a></p>
  <h1>Flagged for review</h1>
  <p class="lede">Items this board could not verify, could not source, or found contradicting each other.
  Nothing here is hidden from the tables; it is listed separately so it is not mistaken for verified data.</p>
  <p class="stamp">Generated {esc(payload['generated_utc'])}</p>
</header>
<main>
  <h2>Flags raised on current open rows</h2>
  <table class="audit">
    <thead><tr><th>Code</th><th>Severity</th><th>What it means</th><th>Rows ({esc(payload['generated_utc'])} capture)</th></tr></thead>
    <tbody>{rows or '<tr><td colspan="4">None.</td></tr>'}</tbody>
  </table>

  <h2>Where the boards disagree on the same match</h2>
  <ul class="flags big">{disc or '<li>No disagreement reaches the 10-point threshold on the current slate.</li>'}</ul>

  <h2>Repository review items from this session</h2>
  <ul class="flags big">{notes or '<li>None.</li>'}</ul>

  <h2>Other boards' review pages</h2>
  <ul>
    <li><a href="../slate/flagged.html">slate/flagged.html</a> — the hourly board's own review items.</li>
    <li><a href="../oct14/flagged.html">oct14/flagged.html</a> — 8944bb84's audit of the 91-fixture universe.</li>
    <li><a href="../open-slate/flagged.html">open-slate/flagged.html</a> — 08031d30's independent review.</li>
    <li><a href="../cs2/flagged.html">cs2/flagged.html</a> — the re-calibrated model board's gaps.</li>
    <li><a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/COORDINATION.md">COORDINATION.md</a> — every session's claim, sources and irregularities.</li>
  </ul>
</main>
<footer><p><a href="index.html">Executive summary</a> · <a href="coverage.html">Coverage</a> ·
<a href="methodology.html">Method</a></p></footer>
</body>
</html>
'''


APP_JS = r'''/* exec/app.js — keeps the summary current without a rebuild.
   Re-reads data/picks.json; if the committed file is newer than the copy baked into the page,
   it re-renders the match cards and the coverage tiles. Falls back to the baked HTML on any error. */
(function () {
  "use strict";
  var STALE_HOURS = 3;
  function fmtPct(v) { return (v === null || v === undefined) ? "—" : Number(v).toFixed(1) + "%"; }
  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function chips(row) {
    var out = "";
    (row.flags || []).forEach(function (f) {
      out += '<li><span class="code">' + escapeHtml(f.code) + "</span> " + escapeHtml(f.text) + "</li>";
    });
    return out ? '<ul class="flags">' + out + "</ul>" : "";
  }
  function card(row) {
    var lead = (row.p_a !== null && row.p_b !== null) ? (row.p_a >= row.p_b ? "a" : "b") : "";
    var basisLabel = {
      "market-direct": "bookmaker price (direct)",
      "market-secondary": "bookmaker price (aggregator)",
      "market-other": "bookmaker price (other listing)",
      "model": "our line from official ratings",
      "none": "no basis"
    }[row.line_source] || row.line_source;
    var market = "—";
    if (row.market_p_a !== null && row.market_p_a !== undefined) {
      market = fmtPct(row.market_p_a) + " / " + fmtPct(row.market_p_b) +
        " (" + escapeHtml(row.market_book || "book") + ")";
      if (row.market_url) {
        market += ' · <a href="' + escapeHtml(row.market_url) + '" rel="noopener">quote</a>';
      }
    }
    var own = (row.own_p_a === null || row.own_p_a === undefined) ? "—" :
      fmtPct(row.own_p_a) + " / " + fmtPct(row.own_p_b) +
      (row.own_url ? ' · <a href="' + escapeHtml(row.own_url) + '" rel="noopener">ratings</a>' : "");
    var pick = row.pick ?
      '<span class="pick">' + escapeHtml(row.pick) + " " + fmtPct(row.pick_pct) + "</span>" :
      '<span class="pick none">no pick</span>';
    var src = row.pick_source_url ?
      ' · <a href="' + escapeHtml(row.pick_source_url) + '" rel="noopener">source</a>' :
      ' · <span class="warn">no source</span>';
    return '<article class="card fixture" data-lock="' + escapeHtml(row.lock_utc) + '">' +
      '<header><div class="when">' + escapeHtml(row.kickoff_utc) +
      '<span class="tier">' + escapeHtml(row.tier || "?") + '-tier</span></div>' +
      '<div class="comp">' + escapeHtml(row.competition) + "</div>" +
      "<h3>" + escapeHtml(row.team_a) + ' <span class="vs">vs</span> ' + escapeHtml(row.team_b) + "</h3></header>" +
      '<div class="probs">' +
      '<div class="side' + (lead === "a" ? " lead" : "") + '"><span class="team">' + escapeHtml(row.team_a) +
      '</span><span class="pct">' + fmtPct(row.p_a) + "</span></div>" +
      '<div class="side' + (lead === "b" ? " lead" : "") + '"><span class="team">' + escapeHtml(row.team_b) +
      '</span><span class="pct">' + fmtPct(row.p_b) + "</span></div></div>" +
      '<p class="pickline">Pick: ' + pick + ' <span class="basis">· ' + escapeHtml(basisLabel) + "</span></p>" +
      '<dl class="detail"><dt>Basis</dt><dd>' + escapeHtml(row.pick_basis || "no basis published") + src + "</dd>" +
      "<dt>Market</dt><dd>" + market + "</dd>" +
      "<dt>Our line</dt><dd>" + own + "</dd>" +
      "<dt>Pred. mkt</dt><dd>" + (row.poly_reference ?
        fmtPct(row.poly_reference.p_a) + " / " + fmtPct(row.poly_reference.p_b) +
        " (prediction market, not a bookmaker)" +
        (row.poly_reference.url ? ' · <a href="' + escapeHtml(row.poly_reference.url) + '" rel="noopener">market</a>' : "")
        : "—") + "</dd>" +
      "<dt>Format</dt><dd>" + escapeHtml(row.best_of || "not sourced") + "</dd>" +
      "<dt>Match</dt><dd>" +
      (row.hotspawn_match_url ? '<a href="' + escapeHtml(row.hotspawn_match_url) + '" rel="noopener">Hotspawn</a>' : "Hotspawn") +
      (row.pick_page ? ' · <a href="' + escapeHtml(row.pick_page) + '">board row</a>' : "") +
      "</dd></dl>" + chips(row) + "</article>";
  }
  function markLocked() {
    var now = Date.now();
    document.querySelectorAll("[data-lock]").forEach(function (el) {
      var lock = Date.parse(el.getAttribute("data-lock"));
      if (lock && lock < now) {
        el.classList.add("locked");
        if (!el.querySelector(".locked-note")) {
          var note = document.createElement("p");
          note.className = "locked-note";
          note.textContent = "Locked — this pick can no longer be submitted.";
          el.appendChild(note);
        }
      }
    });
  }
  function ageBadge(iso) {
    var el = document.getElementById("generated");
    if (!el || !iso) { return; }
    var when = Date.parse(iso);
    if (!when) { return; }
    var hours = (Date.now() - when) / 3600000;
    var stamp = el.parentElement;
    if (hours > STALE_HOURS) {
      stamp.classList.add("stale");
      el.insertAdjacentHTML("afterend",
        ' <strong class="warn">stale by ' + hours.toFixed(1) + " h — check the boards before acting</strong>");
    }
  }
  function refresh() {
    fetch("data/picks.json", { cache: "no-store" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    }).then(function (data) {
      var baked = document.getElementById("generated");
      if (baked && data.generated_utc && data.generated_utc > baked.textContent.trim()) {
        var cards = document.getElementById("cards");
        if (cards && data.open) {
          cards.innerHTML = data.open.map(card).join("");
        }
        baked.textContent = data.generated_utc;
      }
      ageBadge((data && data.generated_utc) || (baked && baked.textContent.trim()));
      markLocked();
    }).catch(function () { markLocked(); });
  }
  document.addEventListener("DOMContentLoaded", function () {
    markLocked();
    refresh();
    setInterval(markLocked, 30000);
  });
}());
'''


STYLE_CSS = r''':root {
  --bg: #0b1220; --panel: #111c2f; --panel-2: #16233a; --ink: #e8eefb; --muted: #9fb0cc;
  --line: #22334f; --accent: #57b2ff; --good: #47d19b; --warn: #ffc44d; --bad: #ff7a7a;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.skip { position: absolute; left: -999px; }
.skip:focus { left: 8px; top: 8px; background: var(--panel); padding: 8px; z-index: 5; }
main { padding: 0 14px 32px; max-width: 980px; margin: 0 auto; }
header.top { padding: 18px 14px 8px; max-width: 980px; margin: 0 auto; }
.eyebrow { color: var(--muted); font-size: 13px; text-transform: uppercase; letter-spacing: .08em; margin: 0 0 6px; }
h1 { font-size: 24px; line-height: 1.2; margin: 0 0 8px; }
h2 { font-size: 19px; margin: 26px 0 8px; }
h3 { font-size: 17px; margin: 4px 0 10px; }
.lede { color: var(--muted); margin: 0 0 10px; }
.stamp { font-size: 13px; color: var(--muted); margin: 0 0 4px; }
.stamp.stale, .stamp.stale a { color: var(--warn); }
.auto { font-size: 13px; color: var(--muted); margin: 6px 0 0; }
.note { color: var(--muted); font-size: 14px; }
.tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 18px 0 6px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.tile .n { display: block; font-size: 26px; font-weight: 700; }
.tile .l { display: block; font-size: 12.5px; color: var(--muted); }
.tile.good .n { color: var(--good); }
.tile.warn .n { color: var(--warn); }
.tile.bad .n { color: var(--bad); }
.boards { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
.board { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
.board.missing { opacity: .55; border-style: dashed; }
.board-link { display: block; color: var(--ink); }
.board-name { display: block; font-weight: 600; font-size: 17px; }
.board-meta { display: block; font-size: 12.5px; color: var(--muted); margin-top: 2px; }
.board-what { font-size: 14px; color: var(--muted); margin: 8px 0 6px; }
.board-links { font-size: 14px; margin: 0; }
.cards { display: grid; gap: 12px; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 14px; }
.card.locked { opacity: .62; }
.fixture .when { font-size: 13px; color: var(--muted); display: flex; justify-content: space-between; align-items: center; }
.tier { background: var(--panel-2); border-radius: 999px; padding: 2px 8px; font-size: 11.5px; text-transform: uppercase; }
.comp { font-size: 13px; color: var(--muted); margin-top: 2px; }
.vs { color: var(--muted); font-weight: 400; font-size: 14px; }
.probs { display: grid; grid-template-columns: 1fr; gap: 6px; margin: 10px 0 6px; }
.side { display: flex; justify-content: space-between; align-items: center; background: var(--panel-2); border-radius: 10px; padding: 10px 12px; min-height: 46px; }
.side.lead { border: 1px solid var(--good); }
.side .team { font-weight: 600; }
.side .pct { font-variant-numeric: tabular-nums; font-size: 18px; font-weight: 700; }
.side.lead .pct { color: var(--good); }
.pickline { margin: 8px 0; font-size: 15px; }
.pick { background: rgba(71, 209, 155, .14); border: 1px solid var(--good); color: var(--good); border-radius: 8px; padding: 3px 9px; font-weight: 700; }
.pick.none { background: rgba(255, 122, 122, .12); border-color: var(--bad); color: var(--bad); }
.basis { color: var(--muted); font-size: 13px; }
.detail { display: grid; grid-template-columns: 84px 1fr; gap: 4px 10px; margin: 10px 0 0; font-size: 13.5px; }
.detail dt { color: var(--muted); }
.detail dd { margin: 0; overflow-wrap: anywhere; }
.detail.big { grid-template-columns: 110px 1fr; font-size: 15px; }
.flags { list-style: none; padding: 0; margin: 10px 0 0; font-size: 13.5px; }
.flags li { margin: 4px 0; color: var(--muted); }
.flags.big li { margin: 8px 0; font-size: 14.5px; color: var(--ink); }
.code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; background: var(--panel-2); border-radius: 6px; padding: 1px 6px; color: var(--accent); }
.disagree { list-style: none; padding: 0; margin: 8px 0 0; font-size: 13.5px; color: var(--warn); }
.warn { color: var(--warn); }
.locked-note { font-size: 13px; color: var(--warn); margin: 6px 0 0; }
.ladder li { margin: 10px 0; }
table.audit { width: 100%; border-collapse: collapse; font-size: 13.5px; }
table.audit th, table.audit td { border: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }
table.audit thead th { background: var(--panel-2); position: sticky; top: 0; }
table.audit td.yes { color: var(--good); }
table.audit td.no { color: var(--muted); }
pre { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 10px; overflow-x: auto; font-size: 13px; }
footer { border-top: 1px solid var(--line); margin-top: 28px; padding: 16px 14px 40px; color: var(--muted); font-size: 13px; max-width: 980px; margin-left: auto; margin-right: auto; }
@media (min-width: 620px) {
  h1 { font-size: 30px; }
  .tiles { grid-template-columns: repeat(3, 1fr); }
  .probs { grid-template-columns: 1fr 1fr; }
  .cards { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 619px) {
  table.audit thead { display: none; }
  table.audit tr { display: block; border: 1px solid var(--line); border-radius: 10px; margin: 0 0 10px; padding: 8px; background: var(--panel); }
  table.audit td { display: block; border: 0; padding: 3px 0; }
  table.audit td[data-label]::before { content: attr(data-label) ": "; color: var(--muted); }
}
'''


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_data(payload, per_board):
    os.makedirs(DATA, exist_ok=True)
    write(os.path.join(DATA, "picks.json"), json.dumps(payload, indent=1, sort_keys=False))
    cols = ["fixture_id", "kickoff_utc", "lock_utc", "competition", "tier", "team_a", "team_b", "line_source",
            "p_a", "p_b", "pick", "pick_pct", "pick_basis", "pick_source_url", "market_book", "market_odds_a",
            "market_odds_b", "market_p_a", "market_p_b", "market_url", "market_captured_utc", "own_p_a", "own_p_b",
            "own_basis", "own_url", "best_of", "best_of_source", "state"]
    with open(os.path.join(DATA, "picks.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in payload["open"] + payload["locked_or_started"]:
            w.writerow({k: r.get(k) for k in cols})
    with open(os.path.join(DATA, "coverage_audit.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["fixture_id", "kickoff_utc", "team_a", "team_b", "our_line_source", "our_pick", "our_pick_pct",
                    "boards_with_row", "boards_with_pick", "boards_with_price", "boards_with_own_line", "flags"])
        for r in payload["open"]:
            pub = r["boards_publishing"]
            w.writerow([r["fixture_id"], r["kickoff_utc"], r["team_a"], r["team_b"], r["line_source"], r["pick"],
                        r["pick_pct"], ";".join(sorted(pub)),
                        ";".join(sorted(b for b, v in pub.items() if v["pick"])),
                        ";".join(sorted(b for b, v in pub.items() if v["market"])),
                        ";".join(sorted(b for b, v in pub.items() if v["model"])),
                        ";".join(f["code"] for f in r["flags"])])
    write(os.path.join(DATA, "boards.json"), json.dumps(payload["boards"], indent=1))
    write(os.path.join(DATA, "flags.json"), json.dumps(
        [{"fixture_id": r["fixture_id"], "match": f"{r['team_a']} vs {r['team_b']}",
          "kickoff_utc": r["kickoff_utc"], "flags": r["flags"], "disagreements": r["disagreements"]}
         for r in payload["open"] if r["flags"] or r["disagreements"]], indent=1))


def load_polymarket():
    """Optional reference data collected by exec/collect_polymarket.py (CI has network)."""
    path = os.path.join(DATA, "polymarket.json")
    if not os.path.exists(path):
        return {"status": "not collected yet", "endpoint": "https://gamma-api.polymarket.com/events?tag_slug=cs2",
                "captured_utc": "", "note": "The collector runs in GitHub Actions; it cannot run in every environment.",
                "matches": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    payload, per_board, spine = build()
    write_data(payload, per_board)
    poly = load_polymarket()
    extra_notes = []
    review_path = os.path.join(ROOT, "reviews", "3b5e3fea-review.md")
    if os.path.exists(review_path):
        with open(review_path, encoding="utf-8") as fh:
            for line in fh:
                match = re.match(r"^- \*\*([RC]-\d+) — (.+)$", line.strip())
                if match:
                    headline = re.sub(r"\*\*$", "", match.group(2)).strip()
                    headline = re.sub(r"\s*\(verified[^)]*\)\s*\.?$", "", headline).strip().rstrip(".")
                    link_txt = (' · <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/'
                                'reviews/3b5e3fea-review.md">full detail</a>')
                    extra_notes.append(f"<strong>{esc(match.group(1))}</strong> — {esc(headline)}{link_txt}")
    write(os.path.join(OUT, "index.html"), render_index(payload))
    write(os.path.join(OUT, "coverage.html"), render_coverage(payload))
    write(os.path.join(OUT, "sources.html"), render_sources(payload, poly))
    write(os.path.join(OUT, "methodology.html"), render_methodology(payload))
    write(os.path.join(OUT, "flagged.html"), render_flagged(payload, extra_notes[:40]))
    write(os.path.join(OUT, "app.js"), APP_JS)
    write(os.path.join(OUT, "style.css"), STYLE_CSS)
    t = payload["totals"]
    print(f"exec board: {t['open_fixtures']} open fixtures | picks {t['with_pick']} | "
          f"market {t['with_market']} (direct {t['with_market_direct']}) | model-only {t['model_only']} | "
          f"no basis {t['no_basis']} | flags {t['flagged_rows']}")
    print("boards seen:", {k: v["rows"] for k, v in sorted(per_board.items())})
    return 0


if __name__ == "__main__":
    sys.exit(main())
