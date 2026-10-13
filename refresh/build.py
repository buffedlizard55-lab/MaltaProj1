#!/usr/bin/env python3
"""R-01 build step — turn the collected public readings into probabilities and picks.

Policy (enforced in code, see the gate at the end):
  * Hotspawn supplies fixture identity and exact UTC lock times ONLY.  Its crowd pick
    percentages are read by the collector for transparency and dropped here; a dataset that
    still contained them would fail the build.
  * Market probabilities come from external bookmaker match-winner prices, de-vigged:
      - EGamersWorld "Betting odds" table -> median price across the bookmakers printed there;
      - Pinnacle public guest moneyline (American -> decimal).
    When both are available their de-vigged probabilities are averaged and the spread between
    them is published as a cross-source check.
  * Our own line is a standard Elo expectation on published rating points (HLTV world ranking,
    Valve Regional Standings), averaged when both exist.  It never uses the market.
  * The pick is the higher-probability side of the combined estimate (70% market / 30% own line
    when both exist, otherwise whichever single source exists — flagged).
  * Anything unreadable stays null and is flagged; nothing is inferred.

Outputs (refresh/data/): current.json, current.csv, odds.csv, ratings.csv
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

MARKET_WEIGHT = 0.70
MODEL_WEIGHT = 0.30
ELO_SCALE = 400.0
DIVERGENCE_FLAG_PP = 5.0     # cross-source disagreement worth flagging
PINNACLE_TIME_TOLERANCE_S = 180

# Explicit, individually-verified aliases only; everything else must match exactly.
ALIASES: dict[str, dict[str, str]] = {}


def norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower().replace("&", " and "))


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.replace("+00:00", "Z"), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except ValueError:
        return None


def lookup(mapping: dict, name: str) -> tuple[str | None, dict | None, list[str]]:
    notes: list[str] = []
    base = norm(name)
    for variant in [base] + list(ALIASES.get(base, {})):
        if variant and variant in mapping:
            if variant != base:
                notes.append(f"alias:{name}->{variant}")
            return variant, mapping[variant], notes
    return None, None, notes


def elo(points_a: float, points_b: float) -> float:
    return 1.0 / (1.0 + 10 ** (-(points_a - points_b) / ELO_SCALE))


def find_keys(node, banned: set[str], path: str = "") -> list[str]:
    """Recursively collect key paths whose name is banned (field-level policy gate)."""
    hits: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key.lower() in banned:
                hits.append(f"{path}.{key}".strip("."))
            hits += find_keys(value, banned, f"{path}.{key}".strip("."))
    elif isinstance(node, list):
        for idx, value in enumerate(node):
            hits += find_keys(value, banned, f"{path}[{idx}]")
    return hits


def main() -> int:
    collected = load("collected.json")
    now = parse_utc(collected["generated_utc"])
    hs, egw = collected["hotspawn"], collected["egw"]
    pinnacle = collected.get("pinnacle") or {"quotes": [], "counters": {}, "pages": []}
    hltv, vrs = collected["hltv"], collected["valve_vrs"]
    reset = parse_utc(hs.get("reset_utc"))
    hltv_rank, vrs_teams = hltv.get("ranking") or {}, vrs.get("teams") or {}

    # Pinnacle quotes indexed by sport + normalised team pair; matched on start time below.
    pin_index: dict[tuple[str, str, str], list[dict]] = {}
    for quote in pinnacle.get("quotes") or []:
        key = (norm(quote.get("game")), norm(quote.get("team_a")), norm(quote.get("team_b")))
        pin_index.setdefault(key, []).append(quote)

    def pinnacle_for(fixture: dict) -> dict | None:
        sport = norm(fixture.get("sport"))
        sport = {"counterstrike": "cs2", "cs": "cs2", "leagueoflegends": "lol"}.get(sport, sport)
        pa, pb = norm(fixture["team_a"]), norm(fixture["team_b"])
        for pair in ((pa, pb), (pb, pa)):
            for quote in pin_index.get((sport, pair[0], pair[1]), []):
                q_start, f_start = parse_utc(quote.get("start_utc")), parse_utc(
                    fixture["scheduled_start_utc"])
                if q_start and f_start and abs((q_start - f_start).total_seconds()) <= \
                        PINNACLE_TIME_TOLERANCE_S:
                    return quote
        return None

    fixtures = hs["fixtures"]
    rows, stale, odds_rows, rating_rows, flagged = [], [], [], {}, []
    week_end = reset or (now + timedelta(days=7))
    horizon_start = now - timedelta(hours=36)

    for fx in fixtures:
        start, lock = parse_utc(fx["scheduled_start_utc"]), parse_utc(fx.get("lock_utc"))
        if not (start and horizon_start <= start <= week_end):
            stale.append({"match_id": fx["match_id"], "sport": fx.get("sport"),
                          "competition": fx.get("competition"), "team_a": fx["team_a"],
                          "team_b": fx["team_b"], "start_utc": fx["scheduled_start_utc"],
                          "reason": ("marked scheduled in Hotspawn's payload but starts outside "
                                     "the current pick'em week"
                                     if start and start > week_end else
                                     "marked scheduled but its start time is in the past"),
                          "source_url": fx["source_url"]})
            continue

        reading = (egw.get("readings") or {}).get(fx["match_id"], {})
        row_flags: list[str] = []
        market_detail: list[dict] = []
        overrounds: list[float] = []
        books_used: list[str] = []

        # ---- source 1: EGamersWorld per-bookmaker table ------------------------------------
        egw_odds = None
        if reading.get("books"):
            wa = [b["odds_a"] for b in reading["books"]]
            wb = [b["odds_b"] for b in reading["books"]]
            odds_a, odds_b = statistics.median(wa), statistics.median(wb)
            books_used = sorted({b["book"] for b in reading["books"]})
            if reading.get("reversed"):
                odds_a, odds_b = odds_b, odds_a
                row_flags.append("odds_pair_order_reversed_vs_hotspawn")
            if len(reading["books"]) == 1:
                row_flags.append("single_bookmaker")
            for book in reading["books"]:
                native_a, native_b = ((book["odds_b"], book["odds_a"]) if reading.get("reversed")
                                      else (book["odds_a"], book["odds_b"]))
                odds_rows.append({"match_id": fx["match_id"], "team_a": fx["team_a"],
                                  "team_b": fx["team_b"], "source": "EGamersWorld (median input)",
                                  "bookmaker": book["book"], "odds_a": native_a,
                                  "odds_b": native_b, "source_url": reading.get("match_url"),
                                  "fetched_utc": reading.get("fetched_utc")})
            egw_odds = (odds_a, odds_b)
        elif reading.get("widget"):
            odds_a, odds_b = reading["widget"][0], reading["widget"][1]
            if reading.get("reversed"):
                odds_a, odds_b = odds_b, odds_a
            egw_odds = (odds_a, odds_b)
            row_flags.append("single_reading_widget_price")
        if egw_odds:
            raw_a, raw_b = 1 / egw_odds[0], 1 / egw_odds[1]
            overrounds.append(raw_a + raw_b)
            market_detail.append({
                "source": "EGamersWorld (aggregated bookmaker prices)",
                "odds_a": egw_odds[0], "odds_b": egw_odds[1],
                "p_a_pct": round(100 * raw_a / (raw_a + raw_b), 1),
                "overround_pct": round(100 * (raw_a + raw_b - 1), 2),
                "bookmakers": books_used,
                "url": reading.get("match_url"), "fetched_utc": reading.get("fetched_utc")})

        # ---- source 2: Pinnacle public guest moneyline --------------------------------------
        pin = pinnacle_for(fx)
        if pin:
            odds = (pin["odds_a"], pin["odds_b"])
            if norm(pin["team_a"]) != norm(fx["team_a"]):
                odds = (pin["odds_b"], pin["odds_a"])
                row_flags.append("pinnacle_pair_order_reversed")
            raw_a, raw_b = 1 / odds[0], 1 / odds[1]
            overrounds.append(raw_a + raw_b)
            market_detail.append({
                "source": "Pinnacle (public guest moneyline)",
                "odds_a": odds[0], "odds_b": odds[1],
                "p_a_pct": round(100 * raw_a / (raw_a + raw_b), 1),
                "overround_pct": round(100 * (raw_a + raw_b - 1), 2),
                "native": {"odds_a": pin.get("native_odds_a"), "odds_b": pin.get("native_odds_b"),
                           "format": pin.get("native_format")},
                "url": pin.get("api_url") or pin.get("source_url"),
                "page_url": pin.get("source_url"), "fetched_utc": pin.get("observed_utc")})
            odds_rows.append({"match_id": fx["match_id"], "team_a": fx["team_a"],
                              "team_b": fx["team_b"], "source": "Pinnacle", "bookmaker": "Pinnacle",
                              "odds_a": odds[0], "odds_b": odds[1],
                              "source_url": pin.get("source_url"),
                              "fetched_utc": pin.get("observed_utc")})

        if len(market_detail) > 1:
            spread = abs(market_detail[0]["p_a_pct"] - market_detail[1]["p_a_pct"])
            if spread > DIVERGENCE_FLAG_PP:
                row_flags.append(f"market_sources_diverge:{spread:.1f}pp")
        market_a = market_b = None
        if market_detail:
            market_a = statistics.fmean(m["p_a_pct"] for m in market_detail) / 100
            market_b = 1 - market_a
            if len(market_detail) == 1:
                row_flags.append("single_market_source")
        if not market_detail:
            row_flags.append("no_external_price_found")
            if not reading.get("found"):
                row_flags.append("no_external_match_page_matched")
        elif any(o <= 1.0 for o in overrounds):
            row_flags.append("overround_below_1_check_source")

        # ---- our own line (published rating points only) ------------------------------------
        model_inputs, model_probs = [], []
        for key, source_name, source_url, mapping in (
                ("hltv", "HLTV world ranking points", hltv.get("ranking_url"), hltv_rank),
                ("vrs", "Valve Regional Standings points", vrs.get("source_url"), vrs_teams)):
            if not mapping:
                continue
            found_a, entry_a, notes_a = lookup(mapping, fx["team_a"])
            found_b, entry_b, notes_b = lookup(mapping, fx["team_b"])
            row_flags += [f"{key}:{note}" for note in notes_a + notes_b]
            if key == "hltv":
                for team, found, entry in ((fx["team_a"], found_a, entry_a),
                                           (fx["team_b"], found_b, entry_b)):
                    if found:
                        rating_rows.setdefault(team, {"team": team,
                                                      "hltv_rank": entry.get("rank"),
                                                      "hltv_points": entry.get("points"),
                                                      "hltv_source_url": hltv.get("ranking_url")})
            if key == "vrs":
                for team, found, entry in ((fx["team_a"], found_a, entry_a),
                                           (fx["team_b"], found_b, entry_b)):
                    if found and team in rating_rows:
                        rating_rows[team]["vrs_points"] = entry.get("points")
                        rating_rows[team]["vrs_source_url"] = vrs.get("source_url")
            if found_a and found_b and None not in (entry_a.get("points"), entry_b.get("points")):
                p = elo(entry_a["points"], entry_b["points"])
                model_probs.append(p)
                model_inputs.append({"source": source_name, "url": source_url,
                                     "team_a_points": entry_a["points"],
                                     "team_b_points": entry_b["points"], "p_a": round(p, 4)})
            else:
                missing = [t for t, f in ((fx["team_a"], found_a), (fx["team_b"], found_b))
                           if not f]
                row_flags.append(f"{key}_rating_missing:" + ",".join(missing))
        model_a = statistics.fmean(model_probs) if model_probs else None
        model_b = 1 - model_a if model_a is not None else None

        if market_a is not None and model_a is not None:
            final_a = MARKET_WEIGHT * market_a + MODEL_WEIGHT * model_a
            basis = f"market {MARKET_WEIGHT:.0%} + own line {MODEL_WEIGHT:.0%}"
        elif market_a is not None:
            final_a, basis = market_a, "market only (no rating line for both teams)"
            row_flags.append("market_only_no_own_line")
        elif model_a is not None:
            final_a, basis = model_a, "own line only (no external price found)"
            row_flags.append("own_line_only_no_market")
        else:
            final_a = None
            basis = "unavailable — neither a bookmaker price nor a rating line could be sourced"
            row_flags.append("no_probability_available")

        pick = pick_pct = None
        if final_a is not None:
            pick = fx["team_a"] if final_a >= 0.5 else fx["team_b"]
            pick_pct = max(final_a, 1 - final_a) * 100

        primary = max(market_detail, key=lambda m: len(m.get("bookmakers") or [])) \
            if market_detail else None
        rows.append({
            "match_id": fx["match_id"], "sport": (fx.get("sport") or "").lower(),
            "competition": fx.get("competition"), "tier": (fx.get("tier") or "").upper() or None,
            "stage": fx.get("stage"), "points": fx.get("offered_points"),
            "best_of": fx.get("best_of"), "team_a": fx["team_a"], "team_b": fx["team_b"],
            "start_utc": fx["scheduled_start_utc"], "lock_utc": fx.get("lock_utc"),
            "status": fx.get("status"),
            "hotspawn_url": f"https://www.hotspawn.com/matches/{fx['match_id']}",
            "hotspawn_page": fx["source_url"],
            "odds_a": primary["odds_a"] if primary else None,
            "odds_b": primary["odds_b"] if primary else None,
            "odds_kind": ("median of the bookmaker prices printed on the match page"
                          if reading.get("books") else
                          ("headline widget price" if reading.get("widget") else None)),
            "odds_bookmakers": books_used,
            "odds_source_url": primary["url"] if primary else None,
            "odds_fetched_utc": primary["fetched_utc"] if primary else None,
            "market_sources": market_detail,
            "overround_pct": round(statistics.fmean(overrounds) * 100 - 100, 2)
            if overrounds else None,
            "market_p_a_pct": round(market_a * 100, 1) if market_a is not None else None,
            "market_p_b_pct": round(market_b * 100, 1) if market_b is not None else None,
            "own_model_p_a_pct": round(model_a * 100, 1) if model_a is not None else None,
            "own_model_p_b_pct": round(model_b * 100, 1) if model_b is not None else None,
            "model_inputs": model_inputs,
            "final_p_a_pct": round(final_a * 100, 1) if final_a is not None else None,
            "final_p_b_pct": round((1 - final_a) * 100, 1) if final_a is not None else None,
            "estimate_basis": basis, "pick": pick,
            "pick_pct": round(pick_pct, 1) if pick_pct else None,
            "locked": bool(lock and now and lock <= now),
            "started": bool(start and now and start <= now),
            "flags": sorted(set(row_flags)),
        })

    sources = [
        {"label": "Hotspawn Play Pick'em lobby (fixture identity + exact UTC lock times)",
         "url": "https://play.hotspawn.com/lobby", "kind": "fixture"},
        {"label": "Hotspawn CS2 pick'ems page (payload cross-check)",
         "url": "https://play.hotspawn.com/cs2-pickems", "kind": "fixture"},
        *[{"label": f"EGamersWorld {title} match list (bookmaker odds)",
           "url": entry.get("url"), "kind": "odds"}
          for title, entry in (egw.get("lists") or {}).items()],
        {"label": "Pinnacle public matchups page (guest moneyline prices)",
         "url": (pinnacle.get("pages") or [{}])[0].get("url"), "kind": "odds"},
        {"label": "HLTV world ranking (own-line rating input)",
         "url": hltv.get("ranking_url"), "kind": "rating"},
        {"label": "Valve Regional Standings — official Valve data repository",
         "url": vrs.get("source_url"), "kind": "rating"},
    ]
    meta = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_snapshot_utc": collected["generated_utc"],
        "hotspawn_snapshot_utc": hs["generated_utc"],
        "egw_snapshot_utc": egw.get("generated_utc"),
        "pinnacle_snapshot_utc": pinnacle.get("generated_utc"),
        "hltv_snapshot_utc": hltv.get("generated_utc"),
        "valve_snapshot_utc": vrs.get("generated_utc"),
        "pickem_week_reset_utc": hs.get("reset_utc"),
        "pickem_week_total_text": hs.get("week_total_text"),
        "pickem_week_total_context": hs.get("week_total_context"),
        "pickem_page_header_counts": [
            {"page": p.get("page"), "url": p.get("url"), "matches_this_week_text":
             p.get("week_total_text"), "context": p.get("week_total_context"),
             "rows_in_payload": p.get("state_rows"), "cards_rendered": p.get("cards_rendered")}
            for p in hs.get("pages", [])],
        "valve_vrs_file": vrs.get("file"),
        "method": {
            "market_probability": ("each external source's match-winner prices are converted to "
                                   "implied probability and normalised to remove the bookmaker "
                                   "overround; EGamersWorld uses the median price across the "
                                   "bookmakers printed on the page, Pinnacle uses its public "
                                   "guest moneyline; the sources' de-vigged probabilities are "
                                   "then averaged"),
            "own_line": (f"standard Elo expectation 1/(1+10^(-dP/{ELO_SCALE:.0f})) on published "
                         "rating points (HLTV world ranking and Valve Regional Standings, "
                         "averaged where both cover both teams)"),
            "combined_estimate": (f"{MARKET_WEIGHT:.0%} market + {MODEL_WEIGHT:.0%} own line when "
                                  "both exist; whichever single source exists otherwise, flagged"),
            "policy": ("Hotspawn crowd pick percentages are read by the collector for "
                       "transparency, dropped before publication, and never influence a "
                       "probability or a pick (enforced by the build gate)"),
        },
        "sources": sources,
        "counts": {
            "fixtures_in_payload": len(fixtures), "fixtures_in_week": len(rows),
            "cs2": sum(1 for r in rows if r["sport"] in {"cs2", "counterstrike", "cs"}),
            "lol": sum(1 for r in rows if r["sport"] in {"lol", "leagueoflegends"}),
            "with_market_probability": sum(1 for r in rows if r["market_p_a_pct"] is not None),
            "with_own_line": sum(1 for r in rows if r["own_model_p_a_pct"] is not None),
            "with_pick": sum(1 for r in rows if r["pick"]),
            "pinnacle_matched": sum(1 for r in rows if any("Pinnacle" in m["source"]
                                                          for m in r["market_sources"])),
            "stale_listings_excluded": len(stale),
        },
        "weights": {"market": MARKET_WEIGHT, "own_line": MODEL_WEIGHT},
    }

    def add_flag(code, title, detail, url, items=None):
        flagged.append({"code": code, "title": title, "detail": detail, "source_url": url,
                        "items": items or []})

    counts = meta["counts"]
    if counts["fixtures_in_week"] == 0:
        add_flag("R-EMPTY", "No fixtures in the current pick'em week",
                 "The collector read the page but no fixture rows fell inside the week window; "
                 "an empty board is not published as a pass.", "https://play.hotspawn.com/lobby")
    lobby_header = next((p.get("week_total_text") for p in hs.get("pages", [])
                         if p.get("page") == "lobby"), None)
    header_counts = ", ".join(
        f"{p.get('page')}={p.get('week_total_text')}" for p in hs.get("pages", [])
        if p.get("week_total_text")) or "n/a"
    if lobby_header and counts["fixtures_in_week"] != lobby_header:
        add_flag("R-COUNT", "The lobby's 'matches this week' count differs from the rows in the "
                            "payload window",
                 f"The lobby page prints {lobby_header} matches this week "
                 f"(context: \"{hs.get('week_total_context') or 'n/a'}\"), while the same page's "
                 f"payload yields {counts['fixtures_in_week']} rows whose start falls inside the "
                 f"week window that ends {hs.get('reset_utc')} (the window comes from the page's "
                 f"own reset countdown). Per-page header counts: {header_counts}. The difference "
                 f"is published, not explained away; the board shows every row the payload "
                 f"contains in the window.", "https://play.hotspawn.com/lobby")
    if stale:
        add_flag("R-STALE", f"{len(stale)} payload listings fall outside this pick'em week",
                 "Hotspawn still serves these rows as 'scheduled' although their start time is "
                 "outside the current week window, so no line is originated for them.",
                 "https://play.hotspawn.com/lobby", items=stale)
    for code, label, key, url in (("R-NOMKT", "no external bookmaker price", "market_p_a_pct",
                                   "https://egamersworld.com/counterstrike/matches"),
                                  ("R-NORATE", "no own-line rating for both teams",
                                   "own_model_p_a_pct", hltv.get("ranking_url"))):
        missing = [r["match_id"] for r in rows if r[key] is None]
        if missing:
            add_flag(code, f"{len(missing)} fixtures have {label}",
                     'Those values are left blank in the published dataset and shown as "-" on '
                     'the board.', url, items=missing)
    single = [r["match_id"] for r in rows if "single_bookmaker" in r["flags"]
              or "single_market_source" in r["flags"] or "single_reading_widget_price"
              in r["flags"]]
    if single:
        add_flag("R-SINGLE", f"{len(single)} fixtures rest on a single price reading",
                 "Only one bookmaker price (or one source) was readable, so there is no "
                 "cross-source agreement behind the median.",
                 "https://egamersworld.com/counterstrike/matches", items=single)
    diverge = [r["match_id"] for r in rows
               if any(f.startswith("market_sources_diverge") for f in r["flags"])]
    if diverge:
        add_flag("R-DIVERGE", f"{len(diverge)} fixtures where the two market sources disagree",
                 f"The EGamersWorld consensus and Pinnacle's moneyline differ by more than "
                 f"{DIVERGENCE_FLAG_PP:.0f} percentage points after de-vigging.", None,
                 items=diverge)
    if vrs.get("error"):
        add_flag("R-VRS", "Valve Regional Standings could not be fully read",
                 f"{vrs['error']} — the own line fell back to the HLTV ranking only.", None)
    locked = [r["match_id"] for r in rows if r["locked"]]
    if locked:
        add_flag("R-LOCKED", f"{len(locked)} fixtures were already locked when this board was built",
                 "Their pick'em lock time had passed; the rows stay published for completeness and "
                 "are labelled locked.", None, items=locked)

    payload = {"meta": meta, "matches": rows, "flagged": flagged, "stale_listings": stale}
    serialised = json.dumps(payload, indent=1)
    leaks = find_keys(payload, {"crowd_pct_a", "crowd_pct_b", "total_picks", "picked_percent",
                                "crowd"})
    if leaks:
        raise SystemExit(f"POLICY VIOLATION: Hotspawn crowd fields reached the dataset: {leaks}")
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
        writer = csv.DictWriter(fh, fieldnames=["match_id", "team_a", "team_b", "source",
                                                "bookmaker", "odds_a", "odds_b", "source_url",
                                                "fetched_utc"])
        writer.writeheader()
        writer.writerows(odds_rows)
    rating_columns = ["team", "hltv_rank", "hltv_points", "vrs_points", "hltv_source_url",
                      "vrs_source_url"]
    with (DATA / "ratings.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=rating_columns, extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rating_rows.values(), key=lambda r: (r.get("hltv_rank") or 9999)):
            writer.writerow(row)

    print(json.dumps({"in_week": len(rows), "stale": len(stale), "odds_rows": len(odds_rows),
                      "counts": meta["counts"],
                      "flags": [(f["code"], len(f["items"])) for f in flagged]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
