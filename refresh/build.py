#!/usr/bin/env python3
"""R-01 build step — turn the collected public readings into probabilities and picks.

Policy (non-negotiable, asserted at the bottom of this file):
  * Hotspawn supplies fixture identity and exact UTC lock times ONLY.  Its crowd pick
    percentages are dropped on ingest and never reach any published file or calculation.
  * Probabilities come from (a) external bookmaker match-winner prices (de-vigged median
    across the books whose names are printed next to the price) and (b) our own rating-based
    line from official rating sources (HLTV world ranking points; Valve Regional Standings
    points as a second input).  Both are published side by side, with their source links.
  * Anything that cannot be read from a source stays null and gets a flag; nothing is inferred.

Outputs (all under refresh/data/):
  current.json   the published dataset (schema below) + metadata + flags
  current.csv    one row per fixture in the live slate
  odds.csv       one row per fixture/bookmaker reading
  ratings.csv    one row per team used by the own-line model
"""
from __future__ import annotations

import csv
import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "refresh" / "data"

MARKET_WEIGHT = 0.70   # documented blend weight; model weight is 1 - MARKET_WEIGHT
MODEL_WEIGHT = 0.30
ELO_SCALE = 400.0      # classic Elo logistic scale, applied to the rating inputs as published

# Explicit, individually-verified aliases only.  Each entry must carry the evidence URL that
# shows both names refer to the same team; anything else is left unmatched and flagged.
ALIASES: dict[str, dict] = {
    # hotspawn-normalised name -> {source-normalised name: evidence url}
    "wrotberry": {"whitebitteam": "https://www.hltv.org/team/11621/whitebit-team",
                  "wbt": "https://www.hltv.org/team/11621/whitebit-team"},
}


def norm(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", s)


def norm_variants(name: str) -> list[str]:
    base = norm(name)
    out = [base]
    for alias_target in ALIASES.get(base, {}):
        out.append(alias_target)
    return out


def load(name: str) -> dict:
    path = DATA / name
    return json.loads(path.read_text(encoding="utf-8"))


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def lookup(mapping: dict, name: str) -> tuple[str | None, dict | None, list[str]]:
    """Exact normalised lookup, then explicit aliases.  Never fuzzy."""
    notes: list[str] = []
    for variant in norm_variants(name):
        if variant in mapping:
            if variant != norm(name):
                notes.append(f"alias:{name}->{variant}")
            return variant, mapping[variant], notes
    return None, None, notes


def elo(points_a: float, points_b: float) -> float:
    """Standard Elo expectation from a published rating difference."""
    return 1.0 / (1.0 + 10 ** (-(points_a - points_b) / ELO_SCALE))


def main() -> int:
    collected = load("collected.json")
    now = parse_utc(collected["generated_utc"])
    hs = collected["hotspawn"]
    egw = collected["egw"]
    hltv = collected["hltv"]
    vrs = collected["valve_vrs"]
    reset = parse_utc(hs.get("reset_utc"))
    hltv_rank = hltv.get("ranking") or {}
    vrs_teams = vrs.get("teams") or {}

    fixtures = hs["fixtures"]
    flagged: list[dict] = []
    rows: list[dict] = []
    stale: list[dict] = []
    odds_rows: list[dict] = []
    rating_rows: dict[str, dict] = {}

    week_end = reset or (now + timedelta(days=7))
    horizon_start = now - timedelta(hours=36)

    for fx in fixtures:
        start = parse_utc(fx["scheduled_start_utc"])
        lock = parse_utc(fx.get("lock_utc"))
        in_week = bool(start and horizon_start <= start <= week_end)
        if not in_week:
            stale.append({
                "match_id": fx["match_id"], "sport": fx.get("sport"),
                "competition": fx.get("competition"), "team_a": fx["team_a"],
                "team_b": fx["team_b"], "start_utc": fx["scheduled_start_utc"],
                "reason": ("listed as scheduled but starts outside this pick'em week"
                           if start and start > week_end else
                           "listed as scheduled but its start time is in the past"),
                "source_url": fx["source_url"],
            })
            continue

        reading = (egw.get("readings") or {}).get(fx["match_id"], {})
        row_flags: list[str] = []
        odds_a = odds_b = None
        odds_source = None
        odds_kind = None
        books_used: list[str] = []
        overround = None
        market_a = market_b = None
        if reading.get("books"):
            wa = [b["odds_a"] for b in reading["books"]]
            wb = [b["odds_b"] for b in reading["books"]]
            odds_a, odds_b = statistics.median(wa), statistics.median(wb)
            books_used = sorted({b["book"] for b in reading["books"]})
            odds_source = reading.get("match_url")
            odds_kind = f"median of {len(reading['books'])} bookmaker prices"
            if reading.get("reversed"):
                odds_a, odds_b = odds_b, odds_a
                books_used = books_used
                row_flags.append("odds_pair_order_reversed_vs_hotspawn")
            if len(reading["books"]) == 1:
                row_flags.append("single_bookmaker")
            for b in reading["books"]:
                oa, ob = (b["odds_b"], b["odds_a"]) if reading.get("reversed") else (b["odds_a"],
                                                                                    b["odds_b"])
                odds_rows.append({"match_id": fx["match_id"], "team_a": fx["team_a"],
                                  "team_b": fx["team_b"], "bookmaker": b["book"],
                                  "odds_a": oa, "odds_b": ob,
                                  "source_url": reading.get("match_url"),
                                  "fetched_utc": reading.get("fetched_utc")})
        elif reading.get("widget"):
            odds_a, odds_b = reading["widget"][0], reading["widget"][1]
            if reading.get("reversed"):
                odds_a, odds_b = odds_b, odds_a
            odds_source = reading.get("match_url")
            odds_kind = "headline widget price (single reading, no bookmaker table parsed)"
            row_flags.append("single_reading_widget_price")
        elif (egw.get("lists") or {}):
            row_flags.append("no_bookmaker_price_found")
        if not reading.get("found"):
            row_flags.append("no_external_match_page_matched")

        if odds_a and odds_b and odds_a > 1 and odds_b > 1:
            raw_a, raw_b = 1 / odds_a, 1 / odds_b
            overround = raw_a + raw_b
            market_a = raw_a / overround
            market_b = raw_b / overround
            if overround < 1.0:
                row_flags.append("overround_below_1_check_source")

        # ---- our own line (rating sources, never the market) -------------------------------
        model_inputs = []
        model_probs = []
        for key, source_name, source_url in (
            ("hltv", "HLTV world ranking points", hltv.get("ranking_url")),
            ("vrs", "Valve Regional Standings points", vrs.get("source_url")),
        ):
            mapping = hltv_rank if key == "hltv" else vrs_teams
            if not mapping:
                continue
            found_a, entry_a, notes_a = lookup(mapping, fx["team_a"])
            found_b, entry_b, notes_b = lookup(mapping, fx["team_b"])
            row_flags += [f"{key}:{n}" for n in notes_a + notes_b]
            if key == "hltv" and (found_a or found_b):
                for team, found, entry in ((fx["team_a"], found_a, entry_a),
                                           (fx["team_b"], found_b, entry_b)):
                    if found:
                        rating_rows.setdefault(team, {
                            "team": team, "hltv_rank": entry.get("rank"),
                            "hltv_points": entry.get("points"),
                            "hltv_source_url": hltv.get("ranking_url")})
            if found_a and found_b and entry_a.get("points") is not None \
                    and entry_b.get("points") is not None:
                p = elo(entry_a["points"], entry_b["points"])
                model_probs.append(p)
                model_inputs.append({"source": source_name, "url": source_url,
                                     "team_a_points": entry_a["points"],
                                     "team_b_points": entry_b["points"],
                                     "p_a": round(p, 4)})
            else:
                missing = [t for t, f in ((fx["team_a"], found_a), (fx["team_b"], found_b)) if not f]
                row_flags.append(f"{key}_rating_missing:" + ",".join(missing))
        model_a = statistics.fmean(model_probs) if model_probs else None
        model_b = 1 - model_a if model_a is not None else None

        # ---- combined estimate -------------------------------------------------------------
        if market_a is not None and model_a is not None:
            final_a = MARKET_WEIGHT * market_a + MODEL_WEIGHT * model_a
            basis = f"market {MARKET_WEIGHT:.0%} + own line {MODEL_WEIGHT:.0%}"
        elif market_a is not None:
            final_a = market_a
            basis = "market only (no own-line rating for both teams)"
            row_flags.append("market_only_no_own_line")
        elif model_a is not None:
            final_a = model_a
            basis = "own line only (no external bookmaker price found)"
            row_flags.append("own_line_only_no_market")
        else:
            final_a = None
            basis = "unavailable: neither a bookmaker price nor a rating line could be sourced"
            row_flags.append("no_probability_available")

        pick = pick_pct = None
        if final_a is not None:
            pick = fx["team_a"] if final_a >= 0.5 else fx["team_b"]
            pick_pct = max(final_a, 1 - final_a) * 100

        rows.append({
            "match_id": fx["match_id"],
            "sport": (fx.get("sport") or "").lower(),
            "competition": fx.get("competition"),
            "tier": (fx.get("tier") or "").upper() or None,
            "stage": fx.get("stage"),
            "points": fx.get("offered_points"),
            "best_of": fx.get("best_of"),
            "team_a": fx["team_a"], "team_b": fx["team_b"],
            "start_utc": fx["scheduled_start_utc"], "lock_utc": fx.get("lock_utc"),
            "status": fx.get("status"),
            "hotspawn_url": f"https://www.hotspawn.com/matches/{fx['match_id']}",
            "hotspawn_page": fx["source_url"],
            "odds_a": odds_a, "odds_b": odds_b, "odds_kind": odds_kind,
            "odds_bookmakers": books_used, "odds_source_url": odds_source,
            "odds_fetched_utc": reading.get("fetched_utc"),
            "overround_pct": round(overround * 100, 2) if overround else None,
            "market_p_a_pct": round(market_a * 100, 1) if market_a is not None else None,
            "market_p_b_pct": round(market_b * 100, 1) if market_b is not None else None,
            "own_model_p_a_pct": round(model_a * 100, 1) if model_a is not None else None,
            "own_model_p_b_pct": round(model_b * 100, 1) if model_b is not None else None,
            "model_inputs": model_inputs,
            "final_p_a_pct": round(final_a * 100, 1) if final_a is not None else None,
            "final_p_b_pct": round((1 - final_a) * 100, 1) if final_a is not None else None,
            "estimate_basis": basis,
            "pick": pick, "pick_pct": round(pick_pct, 1) if pick_pct else None,
            "locked": bool(lock and now and lock <= now),
            "started": bool(start and now and start <= now),
            "flags": sorted(set(row_flags)),
        })

    # ---- dataset metadata ------------------------------------------------------------------
    sources = [
        {"label": "Hotspawn Play Pick'em lobby (fixture identity, UTC lock times)",
         "url": "https://play.hotspawn.com/lobby", "kind": "fixture"},
        {"label": "Hotspawn CS2 pick'ems page", "url": "https://play.hotspawn.com/cs2-pickems",
         "kind": "fixture"},
        *[{"label": f"EGamersWorld {t} match list (bookmaker odds)",
           "url": e.get("url"), "kind": "odds"} for t, e in (egw.get("lists") or {}).items()],
        {"label": "HLTV world ranking (rating input for our own line)",
         "url": hltv.get("ranking_url"), "kind": "rating"},
        {"label": "HLTV Valve Regional Standings mirror (secondary rating input)",
         "url": hltv.get("valve_ranking_url"), "kind": "rating"},
        {"label": "Valve Regional Standings — official Valve data repository",
         "url": vrs.get("source_url") or vrs.get("error"), "kind": "rating"},
    ]
    meta = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_snapshot_utc": collected["generated_utc"],
        "hotspawn_snapshot_utc": hs["generated_utc"],
        "egw_snapshot_utc": egw.get("generated_utc"),
        "hltv_snapshot_utc": hltv.get("generated_utc"),
        "pickem_week_reset_utc": hs.get("reset_utc"),
        "pickem_week_total_text": hs.get("week_total_text"),
        "method": {
            "market_probability": ("median decimal price across the bookmakers printed on the "
                                   "match page, converted to implied probability and normalised "
                                   "to remove the bookmaker overround (proportional de-vig)"),
            "own_line": (f"standard Elo expectation 1/(1+10^(-dP/{ELO_SCALE:.0f})) on published "
                         "rating points (HLTV world ranking; Valve Regional Standings second "
                         "input), averaged when both are available"),
            "combined_estimate": (f"{MARKET_WEIGHT:.0%} market + {MODEL_WEIGHT:.0%} own line when "
                                  "both exist; otherwise whichever single source exists, flagged"),
            "policy": ("Hotspawn crowd pick percentages are never read into this dataset and "
                       "never influence any probability or pick"),
        },
        "sources": sources,
        "counts": {
            "fixtures_in_payload": len(fixtures),
            "fixtures_in_week": len(rows),
            "cs2": sum(1 for r in rows if r["sport"] in {"cs2", "counterstrike", "cs"}),
            "lol": sum(1 for r in rows if r["sport"] in {"lol", "leagueoflegends"}),
            "with_market_probability": sum(1 for r in rows if r["market_p_a_pct"] is not None),
            "with_own_line": sum(1 for r in rows if r["own_model_p_a_pct"] is not None),
            "with_pick": sum(1 for r in rows if r["pick"]),
            "stale_listings_excluded": len(stale),
        },
        "weights": {"market": MARKET_WEIGHT, "own_line": MODEL_WEIGHT},
    }

    def add_flag(code: str, title: str, detail: str, url: str | None, items: list | None = None):
        flagged.append({"code": code, "title": title, "detail": detail, "source_url": url,
                        "items": items or []})

    if meta["counts"]["fixtures_in_week"] == 0:
        add_flag("R-EMPTY", "No fixtures extracted from the live payload",
                 "The collector read the page but no fixture rows were in this pick'em week. "
                 "Nothing is published as a probability.", "https://play.hotspawn.com/lobby")
    if hs.get("week_total_text") and meta["counts"]["fixtures_in_week"] != hs["week_total_text"]:
        add_flag("R-COUNT", "Published 'matches this week' headline differs from the extracted rows",
                 f"Page headline says {hs['week_total_text']} matches this week; the payload "
                 f"yielded {meta['counts']['fixtures_in_week']} rows inside the week window "
                 f"(window end {hs.get('reset_utc')} from the page's own reset countdown).",
                 "https://play.hotspawn.com/lobby")
    if stale:
        add_flag("R-STALE", f"{len(stale)} listings in the payload are outside this pick'em week",
                 "These rows are still marked 'scheduled' in Hotspawn's payload but their start "
                 "time is outside the current week window, so no line is originated for them. "
                 "They are listed on the Flagged for Review page.", "https://play.hotspawn.com/lobby",
                 items=stale)
    if vrs.get("error"):
        add_flag("R-VRS", "Valve Regional Standings could not be read this run",
                 f"{vrs['error']} — the own-line model used the HLTV ranking only.", None)
    no_market = [r["match_id"] for r in rows if r["market_p_a_pct"] is None]
    if no_market:
        add_flag("R-NOMKT", f"{len(no_market)} fixtures have no external bookmaker price",
                 "No usable match-winner price was found on the external source for these "
                 "fixtures; their market probability is left blank.",
                 "https://egamersworld.com/counterstrike/matches", items=no_market)
    no_line = [r["match_id"] for r in rows if r["own_model_p_a_pct"] is None]
    if no_line:
        add_flag("R-NORATE", f"{len(no_line)} fixtures have no own-line rating for both teams",
                 "At least one team is missing from the published rating sources, so our own "
                 "line is left blank for those fixtures (never inferred from the market).",
                 hltv.get("ranking_url"), items=no_line)
    single = [r["match_id"] for r in rows if "single_bookmaker" in r["flags"]
              or "single_reading_widget_price" in r["flags"]]
    if single:
        add_flag("R-SINGLE", f"{len(single)} fixtures rest on a single price reading",
                 "Only one bookmaker price (or one headline widget price) was readable, so the "
                 "median carries no cross-book agreement. Treat those rows as lower confidence.",
                 "https://egamersworld.com/counterstrike/matches", items=single)
    very_short = [r["match_id"] for r in rows if r["locked"]]
    if very_short:
        add_flag("R-LOCKED", f"{len(very_short)} fixtures are already locked at publication time",
                 "Their pick'em lock time has passed. Probabilities are still shown for "
                 "completeness and are labelled as locked.", None, items=very_short)

    payload = {"meta": meta, "matches": rows, "flagged": flagged, "stale_listings": stale}
    serialised = json.dumps(payload, indent=1)
    # Hard policy gate: no Hotspawn crowd-pick field may survive into the published dataset.
    banned = [token for token in ("crowd_pct", "crowd", "picked_percent", "total_picks")
              if token in serialised]
    if banned:
        raise SystemExit(f"POLICY VIOLATION: Hotspawn crowd fields leaked into the dataset: "
                         f"{banned}")
    (DATA / "current.json").write_text(serialised, encoding="utf-8")

    columns = ["match_id", "sport", "competition", "tier", "stage", "points", "team_a", "team_b",
               "start_utc", "lock_utc", "status", "odds_a", "odds_b", "odds_kind",
               "odds_bookmakers", "overround_pct", "market_p_a_pct", "market_p_b_pct",
               "own_model_p_a_pct", "own_model_p_b_pct", "final_p_a_pct", "final_p_b_pct",
               "estimate_basis", "pick", "pick_pct", "locked", "started", "odds_source_url",
               "hotspawn_url", "flags"]
    with (DATA / "current.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            flat = dict(row)
            flat["odds_bookmakers"] = "; ".join(row["odds_bookmakers"])
            flat["flags"] = "; ".join(row["flags"])
            writer.writerow(flat)
    with (DATA / "odds.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["match_id", "team_a", "team_b", "bookmaker",
                                                "odds_a", "odds_b", "source_url", "fetched_utc"])
        writer.writeheader()
        for row in odds_rows:
            writer.writerow(row)
    with (DATA / "ratings.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["team", "hltv_rank", "hltv_points",
                                                "hltv_source_url"])
        writer.writeheader()
        for row in sorted(rating_rows.values(), key=lambda r: (r["hltv_rank"] or 999)):
            writer.writerow(row)

    print(json.dumps({"in_week": len(rows), "stale": len(stale), "odds_rows": len(odds_rows),
                      "flags": [(f["code"], len(f["items"])) for f in flagged],
                      "counts": meta["counts"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
