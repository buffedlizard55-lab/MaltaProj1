#!/usr/bin/env python3
"""Build the contrarian leaderboard plan — session arena/2e2b2e5e.

Inputs (all committed in this directory):
  data/capture.json        live capture written by collect.py (Hotspawn, Pinnacle, bo3.gg, Polymarket,
                           Valve VRS, HLTV ranking) — refreshed every four hours by Actions
  research/research.json   facts read during the session from HLTV / Liquipedia / Valve, each with URL

Outputs: index.html (the plan), day1.html, factors.html, unresolved.html, flagged.html, method.html,
data/plan.csv, data/plan.json, data/day1.csv, data/summary.json, data/calibration.csv.

Probability ladder per open fixture (first rung that resolves wins; the others are still shown):
  1. Pinnacle two-way moneyline for the same fixture, de-vigged.
  2. Other outside prices for the same fixture: Polymarket (normalized share prices) and the bookmaker
     price bo3.gg relays (de-vigged); when both exist they are averaged.
  3. Our own line: official Valve VRS points -> Elo per map with a shrink factor k fitted on the live
     outside prices -> series probability for the fixture's best-of.
Hotspawn's crowd split is used only by model.contrarian() to measure ownership. It never reaches any
probability: probability() below does not receive it (tests mutate it to prove that).
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import model  # noqa: E402

DATA = HERE / "data"
RESEARCH = HERE / "research" / "research.json"
REPO = HERE.parent
SITE = "https://buffedlizard55-lab.github.io/MaltaProj1/"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
HOTSPAWN_RULES = "https://play.hotspawn.com/how-it-works"
PINNACLE_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
WORKFLOW_URL = "https://github.com/buffedlizard55-lab/MaltaProj1/actions/workflows/leaderboard-2e2b2e5e.yml"
STALE_HOURS = 8
MATCH_WINDOW_H = 3.0

ORG_SUFFIXES = ("esports", "esport", "gaming", "team", "gg", "club")


# ------------------------------------------------------------------ small utils
def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def fmt_utc(value: str | None) -> str:
    dt = parse_iso(value)
    return dt.strftime("%a %d %b %H:%M UTC") if dt else "—"


def pct(p: float | None) -> str:
    return "—" if p is None else f"{p * 100:.1f}%"


def norm(name: str | None) -> str:
    s = (name or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "", s)


def strip_org(name: str | None) -> str:
    words = re.findall(r"[a-z0-9.]+", (name or "").lower())
    while len(words) > 1 and words[-1] in ORG_SUFFIXES:
        words.pop()
    while len(words) > 1 and words[0] in ("team",):
        words.pop(0)
    s = "".join(words)
    if s.endswith("gg") and len(s) > 4 and not (name or "").lower().endswith(" gg"):
        s = s[:-2]
    return re.sub(r"[^a-z0-9]+", "", s)


class Names:
    """Canonical team identity: exact normalized names + the research alias table. No fuzzy matching."""

    def __init__(self, aliases: list[dict]):
        self.map: dict[str, str] = {}
        self.proof: dict[str, dict] = {}
        for entry in aliases:
            canon = norm(entry["hotspawn"])
            for raw in [entry["hotspawn"], *entry.get("equivalents", [])]:
                for key in {norm(raw), strip_org(raw)}:
                    if key:
                        self.map.setdefault(key, canon)
            self.proof[canon] = entry

    def canon(self, name: str | None) -> str:
        if not name:
            return ""
        for key in (norm(name), strip_org(name)):
            if key in self.map:
                return self.map[key]
        return strip_org(name) or norm(name)


# ------------------------------------------------------------------ inputs
def load_inputs(capture_path: Path = DATA / "capture.json", research_path: Path = RESEARCH):
    capture = json.loads(capture_path.read_text())
    research = json.loads(research_path.read_text())
    return capture, research


def now_from(capture: dict) -> datetime:
    forced = os.environ.get("LEADERBOARD_NOW_UTC")
    if forced:
        return parse_iso(forced)
    return parse_iso(capture.get("finished_utc")) or datetime.now(timezone.utc)


def team_tables(capture: dict, names: Names):
    vrs = capture.get("vrs") or {}
    vrs_map = {}
    for row in vrs.get("teams") or []:
        key = names.canon(row["team"])
        vrs_map.setdefault(key, row)
    hltv = capture.get("hltv_ranking") or {}
    hltv_map = {}
    for row in hltv.get("teams") or []:
        hltv_map.setdefault(names.canon(row["team"]), row)
    return vrs, vrs_map, hltv, hltv_map


def hours_between(a: str | None, b: str | None) -> float | None:
    da, db = parse_iso(a), parse_iso(b)
    if not da or not db:
        return None
    return abs((da - db).total_seconds()) / 3600.0


def pair_match(names: Names, fa: str, fb: str, qa: str, qb: str) -> str | None:
    """'same' / 'swapped' when the quote's teams are the fixture's teams, else None."""
    ca, cb, xa, xb = names.canon(fa), names.canon(fb), names.canon(qa), names.canon(qb)
    if not ca or not cb or ca == cb:
        return None
    if (ca, cb) == (xa, xb):
        return "same"
    if (ca, cb) == (xb, xa):
        return "swapped"
    return None


def best_by_time(cands: list[tuple[float, dict]]) -> dict | None:
    cands = [c for c in cands if c[0] is not None and c[0] <= MATCH_WINDOW_H]
    if not cands:
        return None
    cands.sort(key=lambda c: c[0])
    if len(cands) > 1 and abs(cands[0][0] - cands[1][0]) < 1e-6:
        return None  # two equally close listings: ambiguous, not used
    return cands[0][1]


def find_pinnacle(fx: dict, capture: dict, names: Names) -> dict | None:
    cands = []
    for q in (capture.get("pinnacle") or {}).get("quotes") or []:
        if q.get("is_live"):
            continue
        orient = pair_match(names, fx["team_a"], fx["team_b"], q["team_a"], q["team_b"])
        if not orient:
            continue
        try:
            pa, pb, margin = model.devig(q["odds_a"], q["odds_b"])
        except (ValueError, TypeError, KeyError):
            continue
        if orient == "swapped":
            pa, pb = pb, pa
        dh = hours_between(fx["start_utc"], q.get("start_utc"))
        cands.append((dh, {"source": "Pinnacle", "p_a": pa, "p_b": pb, "margin_pct": margin,
                           "native": f"{q['team_a']} {q['native_a']:+d} / {q['team_b']} {q['native_b']:+d}" if isinstance(q.get("native_a"), int) and isinstance(q.get("native_b"), int) else f"{q.get('native_a')} / {q.get('native_b')}",
                           "names": f"{q['team_a']} vs {q['team_b']}", "start_utc": q.get("start_utc"),
                           "kickoff_gap_min": round((dh or 0) * 60), "observed_utc": q.get("observed_utc"),
                           "url": PINNACLE_PAGE, "league": q.get("league"), "best_of": q.get("best_of")}))
    return best_by_time(cands)


def find_polymarket(fx: dict, capture: dict, names: Names) -> dict | None:
    cands = []
    for m in (capture.get("polymarket") or {}).get("markets") or []:
        orient = pair_match(names, fx["team_a"], fx["team_b"], m.get("outcome_a"), m.get("outcome_b"))
        if not orient:
            continue
        try:
            pa, pb = model.normalize_pair(m["price_a"], m["price_b"])
        except (ValueError, TypeError, KeyError):
            continue
        if max(pa, pb) > 0.985:
            continue  # a settled / in-play market, not a pre-match price
        if orient == "swapped":
            pa, pb = pb, pa
        bo = re.search(r"\(BO(\d)\)", m.get("title") or "", re.I)
        dh = hours_between(fx["start_utc"], m.get("start_utc"))
        cands.append((dh, {"source": "Polymarket", "p_a": pa, "p_b": pb,
                           "native": f"{m.get('outcome_a')} {m.get('price_a')} / {m.get('outcome_b')} {m.get('price_b')}",
                           "names": f"{m.get('outcome_a')} vs {m.get('outcome_b')}", "start_utc": m.get("start_utc"),
                           "kickoff_gap_min": round((dh or 0) * 60), "observed_utc": m.get("observed_utc"),
                           "url": m.get("url") or "https://polymarket.com/sports/cs2", "title": m.get("title"),
                           "best_of": int(bo.group(1)) if bo else None}))
    return best_by_time(cands)


def find_bo3(fx: dict, capture: dict, names: Names) -> dict | None:
    cands = []
    for m in (capture.get("bo3") or {}).get("matches") or []:
        orient = pair_match(names, fx["team_a"], fx["team_b"], m.get("team_1"), m.get("team_2"))
        if not orient:
            continue
        dh = hours_between(fx["start_utc"], m.get("start_utc"))
        entry = {"source": "bo3.gg", "bo_type": m.get("bo_type"), "url": m.get("url"),
                 "start_utc": m.get("start_utc"), "kickoff_gap_min": round((dh or 0) * 60),
                 "observed_utc": m.get("observed_utc"), "tournament": m.get("tournament"), "price": None}
        q = m.get("quote") or {}
        try:
            c1, c2 = float(q.get("coeff_1")), float(q.get("coeff_2"))
            if q.get("active_1") is not False and q.get("active_2") is not False and c1 > 1 and c2 > 1:
                pa, pb, margin = model.devig(c1, c2)
                if orient == "swapped":
                    pa, pb = pb, pa
                entry["price"] = {"source": f"{(q.get('provider') or 'bookmaker').title()} (relayed by bo3.gg)",
                                  "p_a": pa, "p_b": pb, "margin_pct": margin,
                                  "native": f"{m.get('team_1')} {c1} / {m.get('team_2')} {c2}",
                                  "names": f"{m.get('team_1')} vs {m.get('team_2')}",
                                  "url": m.get("url"), "book_url": q.get("book_url"),
                                  "observed_utc": m.get("observed_utc"), "start_utc": m.get("start_utc"),
                                  "kickoff_gap_min": entry["kickoff_gap_min"]}
        except (TypeError, ValueError):
            pass
        cands.append((dh, entry))
    return best_by_time(cands)


def fixture_format(fx: dict, research: dict, pin: dict | None, poly: dict | None, bo3: dict | None):
    links = research.get("fixture_links", {}).get(fx["match_id"], {})
    for value, src in ((fx.get("best_of"), "Hotspawn"), (links.get("best_of"), links.get("format_source")),
                       (bo3.get("bo_type") if bo3 else None, bo3.get("url") if bo3 else None),
                       (pin.get("best_of") if pin else None, PINNACLE_PAGE),
                       (poly.get("best_of") if poly else None, poly.get("url") if poly else None)):
        if isinstance(value, (int, float)) and int(value) in (1, 2, 3, 5):
            return int(value), src
    return None, None


def probability(market: dict | None, own_p: float | None) -> tuple[float | None, str]:
    """Final probability for team A. Inputs are outside prices and our own line — never crowd data."""
    if market is not None:
        return market["p_a"], market["basis"]
    if own_p is not None:
        return own_p, "Own line · Valve VRS"
    return None, "Unresolved"


# ------------------------------------------------------------------ the plan
def build_rows(capture: dict, research: dict, now: datetime):
    names = Names(research.get("aliases", []))
    vrs, vrs_map, hltv, hltv_map = team_tables(capture, names)
    fixtures = (capture.get("hotspawn") or {}).get("fixtures") or []
    context = research.get("context", [])
    ctx_by_team: dict[str, list] = {}
    for item in context:
        ctx_by_team.setdefault(names.canon(item["team"]), []).append(item)
    results = {r["match_id"]: r for r in research.get("results", [])}

    rows, cal_pairs = [], []
    for fx in fixtures:
        lock, start = parse_iso(fx.get("lock_utc")), parse_iso(fx.get("start_utc"))
        if not fx.get("team_a") or not fx.get("team_b") or not start:
            status = "incomplete"
        elif lock and lock > now:
            status = "open"
        elif start and start < now - timedelta(days=3):
            status = "stale"
        else:
            status = "locked"
        pin = find_pinnacle(fx, capture, names) if status in ("open", "locked") else None
        poly = find_polymarket(fx, capture, names) if status in ("open", "locked") else None
        bo3 = find_bo3(fx, capture, names) if status in ("open", "locked") else None
        best_of, format_src = fixture_format(fx, research, pin, poly, bo3)
        va, vb = vrs_map.get(names.canon(fx["team_a"])), vrs_map.get(names.canon(fx["team_b"]))
        ha, hb = hltv_map.get(names.canon(fx["team_a"])), hltv_map.get(names.canon(fx["team_b"]))

        secondary = [s for s in (poly, (bo3 or {}).get("price")) if s]
        market = None
        if pin:
            market = {"p_a": pin["p_a"], "basis": "Market · Pinnacle", "parts": [pin]}
        elif secondary:
            p_a = sum(s["p_a"] for s in secondary) / len(secondary)
            label = " + ".join(s["source"].split(" (")[0] for s in secondary)
            market = {"p_a": p_a, "basis": f"Market · {label}", "parts": secondary}
        if market and va and vb:
            cal_pairs.append({"match_id": fx["match_id"], "points_a": va["points"], "points_b": vb["points"],
                              "best_of": best_of, "market_p_a": market["p_a"], "source": market["basis"],
                              "team_a": fx["team_a"], "team_b": fx["team_b"], "start_utc": fx["start_utc"]})
        rows.append({"fx": fx, "status": status, "pin": pin, "poly": poly, "bo3": bo3, "market": market,
                     "best_of": best_of, "format_src": format_src, "vrs_a": va, "vrs_b": vb,
                     "hltv_a": ha, "hltv_b": hb, "result": results.get(fx["match_id"]),
                     "links": research.get("fixture_links", {}).get(fx["match_id"], {}),
                     "ctx_a": ctx_by_team.get(names.canon(fx["team_a"]), []),
                     "ctx_b": ctx_by_team.get(names.canon(fx["team_b"]), []),
                     "alias_a": names.proof.get(names.canon(fx["team_a"])),
                     "alias_b": names.proof.get(names.canon(fx["team_b"]))})
    # Calibrate our own line on today's outside prices (+ persisted history).
    history = load_calibration()
    merged = {r["match_id"]: r for r in history}
    for r in cal_pairs:
        merged[r["match_id"]] = r
    cal = list(merged.values())[-400:]
    k, n_cal, mae = model.fit_k(cal)
    for row in rows:
        va, vb, fx = row["vrs_a"], row["vrs_b"], row["fx"]
        row["own_p"] = model.vrs_line(va["points"], vb["points"], row["best_of"] or 3, k) if va and vb else None
        p_a, basis = probability(row["market"], row["own_p"])
        row["p_a"], row["basis"] = p_a, basis
        own = fx.get("ownership") or {}
        row["crowd_a"], row["crowd_b"], row["crowd_n"] = own.get("crowd_pct_a"), own.get("crowd_pct_b"), own.get("total_picks")
        if p_a is not None:
            row["pick"] = fx["team_a"] if p_a >= 0.5 else fx["team_b"]
            row["c"] = model.contrarian(p_a, fx.get("offered_points"), row["crowd_a"], row["crowd_b"])
            fav = fx["team_a"] if row["c"]["fav"] == "a" else fx["team_b"]
            dog = fx["team_b"] if row["c"]["fav"] == "a" else fx["team_a"]
            row["fav"], row["dog"] = fav, dog
            row["protect_pick"] = dog if row["c"]["label"] == "value" else fav
            row["chase_pick"] = dog if row["c"]["label"] in ("value", "upset") else fav
        else:
            row["pick"] = row["fav"] = row["dog"] = row["protect_pick"] = row["chase_pick"] = None
            row["c"] = None
        row["flags"] = row_flags(row)
    return rows, {"k": k, "n": n_cal, "mae_pp": mae, "rows": cal}, vrs, hltv


def row_flags(row: dict) -> list[str]:
    fx, flags = row["fx"], []
    if row["status"] != "open":
        return flags
    if not row["market"]:
        flags.append("No outside price for this fixture: the probability is our own Valve-VRS line only.")
    elif not row["pin"]:
        flags.append("No Pinnacle line: probability uses secondary outside prices (" + row["market"]["basis"].split("· ")[1] + ").")
    for part in (row["market"] or {}).get("parts", []):
        if part.get("kickoff_gap_min"):
            flags.append(f"{part['source']} lists kickoff {part['kickoff_gap_min']} min away from Hotspawn's start ({fmt_utc(part.get('start_utc'))}); matched on the same two teams within {MATCH_WINDOW_H:.0f} h.")
    for side in ("a", "b"):
        alias = row[f"alias_{side}"]
        if alias and alias.get("sources") and norm(alias["hotspawn"]) == norm(fx[f"team_{side}"]) and alias.get("equivalents"):
            used = [p.get("names") for p in (row["market"] or {}).get("parts", []) if p.get("names")]
            if any(norm(fx[f"team_{side}"]) not in norm(u) for u in used):
                flags.append(f"Name differs across sources: Hotspawn '{fx[f'team_{side}']}' = {', '.join(alias['equivalents'][:3])} ({alias['proof'][:160]}{'…' if len(alias['proof']) > 160 else ''})")
    if row["best_of"] is None:
        flags.append("Series format not published by any source read; our own line assumes best-of-three.")
    if row["crowd_n"] is not None and row["crowd_n"] < 25:
        flags.append(f"Crowd split rests on only {row['crowd_n']} Hotspawn picks — ownership estimate is noisy.")
    if not row["vrs_a"] or not row["vrs_b"]:
        missing = [fx[f"team_{s}"] for s in ("a", "b") if not row[f"vrs_{s}"]]
        flags.append("Not in Valve's VRS standings (own line unavailable): " + ", ".join(missing) + ".")
    if row["own_p"] is not None and row["market"] and abs(row["own_p"] - row["market"]["p_a"]) >= 0.15:
        flags.append(f"Our VRS line ({pct(row['own_p'])} {fx['team_a']}) and the market ({pct(row['market']['p_a'])}) differ by 15 pp or more.")
    return flags


# ------------------------------------------------------------------ calibration persistence
CAL_FIELDS = ["match_id", "team_a", "team_b", "start_utc", "best_of", "points_a", "points_b", "market_p_a", "source"]


def load_calibration() -> list[dict]:
    path = DATA / "calibration.csv"
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as fh:
        raw_rows = list(csv.DictReader(fh))
    for r in raw_rows:
        try:
            out.append({**r, "points_a": float(r["points_a"]), "points_b": float(r["points_b"]),
                        "market_p_a": float(r["market_p_a"]),
                        "best_of": int(r["best_of"]) if r.get("best_of") not in (None, "", "None") else None})
        except (ValueError, KeyError):
            continue
    return out


def save_calibration(rows: list[dict]) -> None:
    with (DATA / "calibration.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CAL_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x.get("start_utc") or "", x["match_id"])):
            w.writerow({**r, "market_p_a": f"{float(r['market_p_a']):.4f}"})


# ------------------------------------------------------------------ day 1
def day1_rows(research: dict, vrs_map: dict, names: Names):
    out = []
    results = {r["match_id"]: r for r in research.get("results", [])}
    links = research.get("fixture_links", {})
    for d in research.get("day1", {}).get("rows", []):
        p_a = None
        if d.get("native_a") is not None and d.get("native_b") is not None:
            pa, pb, _ = model.devig(model.american_to_decimal(d["native_a"]), model.american_to_decimal(d["native_b"]))
            p_a = pa
        res = results.get(d["match_id"], {})
        winner = res.get("winner")
        crowd_fav = d["team_a"] if (d.get("crowd_a") or 0) >= (d.get("crowd_b") or 0) else d["team_b"]
        mkt_fav = None if p_a is None else (d["team_a"] if p_a >= 0.5 else d["team_b"])
        c = model.contrarian(p_a, d["points"], d.get("crowd_a"), d.get("crowd_b")) if p_a is not None else None
        out.append({**d, "p_a": p_a, "winner": winner, "score": res.get("score"), "hltv": res.get("hltv") or links.get(d["match_id"], {}).get("hltv"),
                    "crowd_fav": crowd_fav, "mkt_fav": mkt_fav, "c": c,
                    "crowd_fav_won": winner is not None and norm(winner) == norm(crowd_fav),
                    "mkt_fav_won": None if mkt_fav is None or winner is None else norm(winner) == norm(mkt_fav)})
    return out


def day1_upset_phrase(r: dict) -> str:
    """'9z over Aurora (picked by 4% of players; market ~25.9%)' — numbers straight from the stored row."""
    win_a = norm(r["winner"]) == norm(r["team_a"])
    loser = r["team_b"] if win_a else r["team_a"]
    crowd = r["crowd_a"] if win_a else r["crowd_b"]
    p = None if r["p_a"] is None else (r["p_a"] if win_a else 1 - r["p_a"])
    return f"{r['winner']} over {loser} (picked by {crowd}% of players; market {pct(p)})"


def day1_strategies(rows: list[dict]) -> dict:
    """Points each simple strategy would have scored on day 1 (S 7 / B 3 / C 2; streak bonus ignored)."""
    def score(pick_fn):
        pts = 0
        for r in rows:
            pick = pick_fn(r)
            if pick and r.get("winner") and norm(pick) == norm(r["winner"]):
                pts += r["points"]
        return pts

    def mkt_or_crowd(r):
        return r["mkt_fav"] or r["crowd_fav"]

    def protect(r):
        if r["c"] and r["c"]["label"] == "value":
            return r["team_b"] if r["c"]["dog"] == "b" else r["team_a"]
        return mkt_or_crowd(r)

    def chase(r):
        if r["c"] and r["c"]["label"] in ("value", "upset"):
            return r["team_b"] if r["c"]["dog"] == "b" else r["team_a"]
        return mkt_or_crowd(r)

    return {"available": sum(r["points"] for r in rows if r.get("winner")),
            "crowd_favourite": score(lambda r: r["crowd_fav"]),
            "market_favourite": score(mkt_or_crowd),
            "protect": score(protect), "chase": score(chase)}


# ------------------------------------------------------------------ HTML
CSS_LINK = '<link rel="stylesheet" href="style.css">'
NAV = [("index.html", "Plan"), ("day1.html", "Day 1 review"), ("factors.html", "Roster & rest"),
       ("unresolved.html", "Unresolved & limits"), ("flagged.html", "Flagged for review"), ("method.html", "Method")]


def page(title: str, active: str, body: str, meta: dict) -> str:
    current = ' aria-current="page"'
    nav = "".join(f'<a href="{href}"{current if href == active else ""}>{esc(label)}</a>' for href, label in NAV)
    stale = meta.get("stale")
    banner = (f'<p class="banner warn" role="status">This plan was built from a capture taken {esc(meta["age_text"])} ago '
              f'({esc(fmt_utc(meta["capture_utc"]))}) — older than {STALE_HOURS} h. Check lock times on Hotspawn before relying on it.</p>'
              if stale else
              f'<p class="banner" role="status">Live capture {esc(fmt_utc(meta["capture_utc"]))} · rebuilt automatically every 4 h · '
              f'<a href="{WORKFLOW_URL}">refresh log</a></p>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Hotspawn CS2 leaderboard plan</title>
<meta name="description" content="Contrarian-but-not-stupid Hotspawn CS2 Pick'em plan: outside-market win probabilities vs. crowd ownership for every open match.">
{CSS_LINK}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="top">
  <div class="wrap">
    <p class="crumbs"><a href="../index.html">Home</a> › Leaderboard plan</p>
    <nav aria-label="Leaderboard plan sections">{nav}</nav>
  </div>
</header>
<main id="main" class="wrap">
{banner}
{body}
</main>
<footer class="wrap foot">
  <p>Independent analysis (session arena/2e2b2e5e). Not affiliated with Hotspawn, HLTV, Valve, Pinnacle, Polymarket or bo3.gg.
  Hotspawn crowd shares are used only to measure how many players pick each side — never as a win probability.
  Data: <a href="data/plan.csv">plan.csv</a> · <a href="data/plan.json">plan.json</a> · <a href="data/day1.csv">day1.csv</a> · <a href="data/summary.json">summary.json</a>.</p>
</footer>
<script>
(function () {{
  var now = Date.now();
  document.querySelectorAll("[data-lock]").forEach(function (el) {{
    var t = Date.parse(el.getAttribute("data-lock"));
    if (t && t <= now) {{
      el.classList.add("locked");
      var b = el.querySelector(".lockstate");
      if (b) {{ b.textContent = "Locked on Hotspawn · "; }}
    }}
  }});
}})();
</script>
</body>
</html>
"""


def link(url: str | None, label: str) -> str:
    if not url:
        return ""
    return f'<a href="{esc(url)}">{esc(label)}</a>'


def label_chip(label: str | None) -> str:
    text = {"fade": "Crowd fades the favourite", "value": "Contrarian value", "upset": "Upset shot",
            "chalk": "Take the favourite", "no crowd data": "No crowd data"}.get(label or "", label or "—")
    return f'<span class="chip chip-{esc((label or "none").replace(" ", "-"))}">{esc(text)}</span>'


def sources_html(row: dict) -> str:
    fx, parts = row["fx"], []
    parts.append(link(fx.get("hotspawn_match_url") or HOTSPAWN_LOBBY, "Hotspawn"))
    if row["links"].get("hltv"):
        parts.append(link(row["links"]["hltv"], "HLTV match"))
    for p in (row["market"] or {}).get("parts", []):
        parts.append(link(p.get("url"), p["source"].split(" (")[0]))
    if row["vrs_a"] and row["vrs_b"]:
        parts.append(link(VRS_BLOB_URL, "Valve VRS"))
    return " · ".join(p for p in parts if p)


VRS_BLOB_URL = ""


def match_card(row: dict, mode: str = "plan") -> str:
    fx, c = row["fx"], row["c"] or {}
    pa = row["p_a"]
    pb = None if pa is None else 1 - pa
    crowd = (f'{esc(row["crowd_a"])}% / {esc(row["crowd_b"])}%'
             + (f' <span class="muted">(n={esc(row["crowd_n"])})</span>' if row["crowd_n"] is not None else "")
             if row["crowd_a"] is not None else "—")
    if pa is None:
        rec = '<p class="rec none">No pick: no outside price and no official rating for both teams. See <a href="unresolved.html">Unresolved</a>.</p>'
    else:
        lev = c.get("leverage")
        lev_txt = "—" if lev is None else ("∞" if lev == float("inf") else f"{lev:.1f}×")
        if c.get("label") == "value":
            rec = (f'<p class="rec value"><strong>Leaderboard pick: {esc(row["dog"])}</strong> — {pct(c["p_dog"])} to win, '
                   f'but only {pct(c["crowd_dog"])} of players are on it. Costs {c["ev_cost"]:.1f} expected pts; '
                   f'if it lands you gain {esc(fx.get("offered_points"))} pts on {pct(1 - c["crowd_dog"])} of the field.</p>')
        elif c.get("label") == "fade":
            rec = (f'<p class="rec value"><strong>Pick: {esc(row["fav"])}</strong> — the market favourite ({pct(1 - c["p_dog"])}), '
                   f'yet only {pct(1 - c["crowd_dog"])} of players are on it. Higher expected points <em>and</em> a hit gains '
                   f'{esc(fx.get("offered_points"))} pts on {pct(c["crowd_dog"])} of the field.</p>')
        elif c.get("label") == "upset":
            rec = (f'<p class="rec upset"><strong>Safe: {esc(row["fav"])}.</strong> Chasing the top? {esc(row["dog"])} is a real upset shot '
                   f'({pct(c["p_dog"])}, owned by {pct(c["crowd_dog"])}, leverage {lev_txt}) — costs {c["ev_cost"]:.1f} expected pts.</p>')
        elif c.get("label") == "no crowd data":
            rec = f'<p class="rec chalk"><strong>Pick: {esc(row["pick"])}</strong> (crowd split not published).</p>'
        else:
            rec = (f'<p class="rec chalk"><strong>Pick: {esc(row["fav"])}</strong> — the underdog is not live enough or not '
                   f'under-owned enough to be worth a contrarian pick (underdog {pct(c.get("p_dog"))}, owned by {pct(c.get("crowd_dog"))}).</p>')
    factors = []
    for side in ("a", "b"):
        for item in row[f"ctx_{side}"]:
            src = item["sources"][0]["url"] if item.get("sources") else None
            factors.append(f'<li><strong>{esc(item["team"])}</strong> · {esc(item["kind"])}: {esc(item["summary"])} {link(src, "source")}</li>')
    fac_html = f'<details class="factors"><summary>Roster / rest factors ({len(factors)})</summary><ul>{"".join(factors)}</ul></details>' if factors else ""
    flags = "".join(f"<li>{esc(f)}</li>" for f in row["flags"])
    flag_html = f'<details class="flags"><summary>Notes & flags ({len(row["flags"])})</summary><ul>{flags}</ul></details>' if row["flags"] else ""
    def side_cls(team):
        cls = []
        if pa is not None and team == row["pick"]:
            cls.append("likely")
        if team == row.get("protect_pick"):
            cls.append("pick")
        return " ".join(cls)

    def side_tag(team):
        tags = []
        if team == row.get("protect_pick"):
            tags.append('<span class="tag">PICK</span>')
        if team == row.get("chase_pick") and row.get("chase_pick") != row.get("protect_pick"):
            tags.append('<span class="tag chase">CHASE</span>')
        return "".join(tags)
    win_a, win_b = side_cls(fx["team_a"]), side_cls(fx["team_b"])
    own = f'Our VRS line: {esc(fx["team_a"])} {pct(row["own_p"])}' if row["own_p"] is not None else "Our VRS line: n/a"
    return f"""<article class="card" id="m{esc(fx['match_id'])}" data-lock="{esc(fx.get('lock_utc'))}">
  <p class="meta"><span class="lockstate" aria-live="polite"></span><span class="tier tier-{esc(fx.get('tier') or 'x')}">Tier {esc((fx.get('tier') or '?').upper())} · {esc(fx.get('offered_points'))} pts</span>
  {esc(fx.get('competition'))} · {'BO' + str(row['best_of']) if row['best_of'] else 'format n/a'}</p>
  <h3>{esc(fx['team_a'])} <span class="vs">vs</span> {esc(fx['team_b'])}</h3>
  <p class="when">Locks {esc(fmt_utc(fx.get('lock_utc')))} · starts {esc(fmt_utc(fx.get('start_utc')))}</p>
  <div class="probs" role="group" aria-label="Win probabilities">
    <div class="side {win_a}"><span class="team">{esc(fx['team_a'])} {side_tag(fx['team_a'])}</span><span class="p">{pct(pa)}</span></div>
    <div class="side {win_b}"><span class="team">{esc(fx['team_b'])} {side_tag(fx['team_b'])}</span><span class="p">{pct(pb)}</span></div>
  </div>
  <p class="basis">{esc(row['basis'])} · {own} · Crowd on Hotspawn: {crowd} {label_chip(c.get('label'))}</p>
  {rec}
  {fac_html}
  {flag_html}
  <p class="src">{sources_html(row)}</p>
</article>"""


def plan_table(rows: list[dict]) -> str:
    trs = []
    for r in rows:
        fx, c = r["fx"], r["c"] or {}
        lev = c.get("leverage")
        lev_txt = "—" if lev is None else ("∞" if lev == float("inf") else f"{lev:.1f}×")
        trs.append(f"""<tr data-lock="{esc(fx.get('lock_utc'))}"><td data-label="Match"><a href="#m{esc(fx['match_id'])}">{esc(fx['team_a'])} vs {esc(fx['team_b'])}</a><br><span class="muted">{esc(fx.get('competition'))}</span></td>
<td data-label="Locks">{esc(fmt_utc(fx.get('lock_utc')))}</td><td data-label="Pts">{esc(fx.get('offered_points'))}</td>
<td data-label="Win %">{esc(fx['team_a'])} {pct(r['p_a'])}<br>{esc(fx['team_b'])} {pct(None if r['p_a'] is None else 1 - r['p_a'])}</td>
<td data-label="Basis">{esc(r['basis'])}</td>
<td data-label="Crowd">{'—' if r['crowd_a'] is None else f"{esc(r['crowd_a'])}% / {esc(r['crowd_b'])}%"}</td>
<td data-label="Leverage">{lev_txt}</td>
<td data-label="Protect a lead"><strong>{esc(r['protect_pick'] or '—')}</strong></td>
<td data-label="Chase the top"><strong>{esc(r['chase_pick'] or '—')}</strong></td>
<td data-label="Label">{label_chip(c.get('label'))}</td></tr>""")
    return ('<div class="table-wrap quick"><table class="plan"><thead><tr><th>Match</th><th>Locks</th><th>Pts</th><th>Win %</th>'
            '<th>Basis</th><th>Crowd A/B</th><th>Leverage</th><th>Protect a lead</th><th>Chase the top</th><th>Label</th>'
            f'</tr></thead><tbody>{"".join(trs)}</tbody></table></div>')


def render(rows, cal, vrs, hltv, capture, research, now):
    global VRS_BLOB_URL
    VRS_BLOB_URL = vrs.get("blob_url") or "https://github.com/ValveSoftware/counter-strike_regional_standings"
    names = Names(research.get("aliases", []))
    _, vrs_map, _, _ = team_tables(capture, names)
    hot = capture.get("hotspawn") or {}
    capture_utc = hot.get("fetched_utc") or capture.get("finished_utc")
    age_h = (now - parse_iso(capture_utc)).total_seconds() / 3600 if parse_iso(capture_utc) else None
    real_now = datetime.now(timezone.utc) if not os.environ.get("LEADERBOARD_NOW_UTC") else now
    age_now = (real_now - parse_iso(capture_utc)).total_seconds() / 3600 if parse_iso(capture_utc) else None
    meta = {"capture_utc": capture_utc, "stale": age_now is not None and age_now > STALE_HOURS,
            "age_text": f"{age_now:.1f} h" if age_now is not None else "unknown"}
    open_rows = sorted([r for r in rows if r["status"] == "open"], key=lambda r: (r["fx"].get("lock_utc") or "", r["fx"]["match_id"]))
    value = [r for r in open_rows if r["c"] and r["c"]["label"] == "value"]
    upset = [r for r in open_rows if r["c"] and r["c"]["label"] == "upset"]
    unresolved = [r for r in open_rows if r["p_a"] is None]
    fallback = [r for r in open_rows if r["p_a"] is not None and not r["pin"]]
    lb = hot.get("leaderboard_points") or []
    tenth = next((x["points"] for x in sorted(lb, key=lambda x: x["position"]) if x["position"] >= 9), None)
    leader = next((x["points"] for x in lb if x["position"] == 1), None)
    pts_open = sum(r["fx"].get("offered_points") or 0 for r in open_rows)
    ev_safe = sum((max(r["p_a"], 1 - r["p_a"])) * (r["fx"].get("offered_points") or 0) for r in open_rows if r["p_a"] is not None)
    ev_protect = sum(((r["c"]["p_dog"] if r["protect_pick"] == r["dog"] else 1 - r["c"]["p_dog"]) * (r["fx"].get("offered_points") or 0))
                     for r in open_rows if r["c"])
    ev_chase = sum(((r["c"]["p_dog"] if r["chase_pick"] == r["dog"] else 1 - r["c"]["p_dog"]) * (r["fx"].get("offered_points") or 0))
                   for r in open_rows if r["c"])
    week = hot.get("week") or {}
    d1 = day1_rows(research, vrs_map, names)
    strat = day1_strategies(d1)

    d1_upsets = sum(1 for r in d1 if r["winner"] and not r["crowd_fav_won"])
    d1_list = "; ".join(day1_upset_phrase(r) for r in d1 if r["winner"] and not r["crowd_fav_won"])

    # ---------- index
    fade = [r for r in open_rows if r["c"] and r["c"]["label"] == "fade"]

    def hl_items(group, pick_dog):
        items = []
        for r in group:
            c, fx = r["c"], r["fx"]
            team = r["dog"] if pick_dog else r["fav"]
            other = r["fav"] if pick_dog else r["dog"]
            p = c["p_dog"] if pick_dog else 1 - c["p_dog"]
            own = c["crowd_dog"] if pick_dog else 1 - c["crowd_dog"]
            items.append(f'<li data-lock="{esc(fx.get("lock_utc"))}"><a href="#m{esc(fx["match_id"])}"><strong>{esc(team)}</strong> over {esc(other)}</a> — '
                         f'{pct(p)} to win, {pct(own)} of players on it · {esc(fx.get("offered_points"))} pts · '
                         f'locks {esc(fmt_utc(fx.get("lock_utc")))}</li>')
        return "".join(items)

    groups = []
    if fade:
        groups.append(f'<h3>Free edge — the crowd fades the favourite</h3><p class="muted">Take these favourites: more expected points and still contrarian.</p><ol class="headline">{hl_items(fade, False)}</ol>')
    if value:
        groups.append(f'<h3>Contrarian value — near coin flips the crowd ignores</h3><p class="muted">Cheap in expected points, big swing on the field.</p><ol class="headline">{hl_items(value, True)}</ol>')
    if upset:
        groups.append(f'<h3>Upset shots — only if you need to catch up</h3><p class="muted">Real chances the crowd almost ignores; they cost more expected points.</p><ol class="headline">{hl_items(upset, True)}</ol>')
    headline = "".join(groups) or '<p>No open match currently passes the contrarian rule — take the favourites (full list below).</p>'
    other_boards = []
    for path, label in (("../valuepicks/index.html", "Pick for every match (valuepicks)"),
                        ("../hotspawn/index.html", "Every-match board (hotspawn)"),
                        ("../executive/picks.html", "Executive picks board")):
        if (HERE / path).resolve().exists():
            other_boards.append(f'<a class="btn ghost" href="{path}">{esc(label)}</a>')
    body = f"""
<section class="hero">
  <p class="eyebrow">Hotspawn CS2 Pick'em · week {esc(week.get('weekId'))} ({esc((week.get('weekStartUtc') or '')[:10])} → {esc((week.get('weekEndUtc') or '')[:10])})</p>
  <h1>Climb the leaderboard: contrarian, not stupid</h1>
  <p class="lede">Every open Hotspawn CS2 match with both teams' win chances from outside prices (Pinnacle first), how much of the
  Hotspawn field is on each side, and when an underdog is worth taking. A contrarian pick is only suggested when the underdog is
  close to a coin flip <em>and</em> the crowd under-owns it.</p>
  <div class="stats">
    <div><b>{len(open_rows)}</b><span>open matches</span></div>
    <div><b>{len(fade) + len(value)}</b><span>contrarian picks</span></div>
    <div><b>{len(upset)}</b><span>upset shots</span></div>
    <div><b>{pts_open}</b><span>pts on the board</span></div>
  </div>
  <p class="callout"><strong>Day 1 lesson:</strong> the crowd's favourite lost {d1_upsets} of {len(d1)} Hotspawn matches on 14 Oct — {d1_list}.
  Each winner was rated far higher by the betting market than by the crowd. <a href="day1.html">Day 1 review →</a></p>
  <p class="muted">Leaderboard now: leader {esc(leader if leader is not None else '—')} pts, 10th ≈ {esc(tenth if tenth is not None else '—')} pts
  (top 10 win Steam vouchers; min. 10 picks). <a href="method.html#scoring">Scoring rules</a></p>
</section>

<section aria-labelledby="h-now">
  <h2 id="h-now">Contrarian picks right now</h2>
  {headline}
  <p class="muted">Expected points if you take every favourite: {ev_safe:.1f}. "Protect a lead" plan (favourites + value spots): {ev_protect:.1f}.
  "Chase the top" plan (also upset shots): {ev_chase:.1f}. The small expected-point cost buys the swings you need to pass players above you.</p>
</section>

<section aria-labelledby="h-all">
  <h2 id="h-all">Every open match ({len(open_rows)})</h2>
  <p class="muted">Sorted by lock time. {len(fallback)} use a secondary outside price or our own line and {len(unresolved)} have no pick —
  both listed on <a href="unresolved.html">Unresolved &amp; limits</a>.</p>
  {plan_table(open_rows)}
  <div class="cards">{"".join(match_card(r) for r in open_rows)}</div>
</section>

<section aria-labelledby="h-more">
  <h2 id="h-more">More</h2>
  <p><a class="btn" href="day1.html">Day 1 review: what the 9z upset teaches</a> <a class="btn" href="factors.html">Roster, onboarding &amp; rest factors</a></p>
  <p>{"".join(other_boards)}</p>
</section>"""
    (HERE / "index.html").write_text(page("Leaderboard plan", "index.html", body, meta))

    # ---------- day 1
    trs = []
    for r in d1:
        c = r["c"] or {}
        won = "✔" if r["crowd_fav_won"] else "✘"
        mwon = "—" if r["mkt_fav_won"] is None else ("✔" if r["mkt_fav_won"] else "✘")
        line = f'{esc(r["team_a"])} {pct(r["p_a"])}' if r["p_a"] is not None else "no line captured"
        trs.append(f"""<tr class="{'upset-row' if r['winner'] and not r['crowd_fav_won'] else ''}"><td data-label="Match">{esc(r['team_a'])} vs {esc(r['team_b'])}<br><span class="muted">{esc(r['competition'])} · {esc(r['tier'].upper())} {esc(r['points'])} pts</span></td>
<td data-label="Pre-lock line">{line}</td><td data-label="Crowd A/B">{esc(r['crowd_a'])}% / {esc(r['crowd_b'])}% <span class="muted">n={esc(r['crowd_n'])}</span></td>
<td data-label="Result">{link(r['hltv'], (r['winner'] or '?') + ' ' + (r['score'] or ''))}</td>
<td data-label="Crowd fav won">{won}</td><td data-label="Market fav won">{mwon}</td><td data-label="Rule said">{label_chip(c.get('label')) if c else '—'}</td></tr>""")
    upsets = [r for r in d1 if r["winner"] and not r["crowd_fav_won"]]
    body = f"""
<section class="hero">
  <p class="eyebrow">Wednesday 14 October 2026 · all {len(d1)} Hotspawn CS2 fixtures</p>
  <h1>Day 1 review</h1>
  <p class="lede">The crowd's favourite lost {len(upsets)} of {len(d1)} times: {"; ".join(day1_upset_phrase(r) for r in upsets)}.
  In every case the betting market rated the winner far higher than the Hotspawn crowd did. The headline upset: <strong>9z beat Aurora 2-0</strong>
  (Inferno 13-11, Nuke 13-1).</p>
</section>
<section aria-labelledby="h-d1">
  <h2 id="h-d1">Every day-1 match</h2>
  <div class="table-wrap"><table class="plan"><thead><tr><th>Match</th><th>Pre-lock line</th><th>Crowd</th><th>Result (HLTV)</th><th>Crowd fav won</th><th>Market fav won</th><th>Rule said</th></tr></thead>
  <tbody>{"".join(trs)}</tbody></table></div>
  <p class="muted">Lines: Pinnacle moneylines captured 2026-10-14 07:58Z, 26 minutes before the first lock, de-vigged ({link(research['day1']['capture_url'], 'capture')}).
  Crowd: Hotspawn's public split in the same capture. Results: {link(research.get('results_source'), 'HLTV results')} (each row links its match page).</p>
</section>
<section aria-labelledby="h-sim">
  <h2 id="h-sim">How simple plans would have scored on day 1</h2>
  <ul class="tight">
    <li>Follow the crowd: <b>{strat['crowd_favourite']}</b> of {strat['available']} pts</li>
    <li>Market favourite (crowd favourite where no line): <b>{strat['market_favourite']}</b></li>
    <li>"Protect a lead" (favourites + contrarian value spots): <b>{strat['protect']}</b></li>
    <li>"Chase the top" (also upset shots): <b>{strat['chase']}</b></li>
  </ul>
  <p class="muted">One day is far too small a sample to prove a rule; streak bonuses are ignored. The point is the shape: the crowd herds onto big names
  (96% on Aurora, 92% on fnatic) far beyond what the prices justify, so a correct contrarian pick moves you past almost the whole field at once.</p>
</section>
<section aria-labelledby="h-aur">
  <h2 id="h-aur">Why Aurora was vulnerable</h2>
  <p>Aurora rebuilt in July: new in-game leader kyxsan (from Falcons) and Jimpphat joined the Turkish core, with ash as coach, replacing MAJ3R, soulfly and coach Fabre
  ({link('https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan', 'HLTV, 8 Jul')}). HLTV counts just 62 maps for the new pieces, and kyxsan rated 0.53 in the
  9z series ({link('https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026', 'match page')}). Aurora had beaten 9z 2-0 eleven days earlier at EPL 24, and 9z
  arrived after four straight group-stage exits ({link('https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026', 'HLTV report')}) — so the crowd's 96% looked safe, but the
  price (about 26%) already said an upset was a one-in-four event. <a href="factors.html">All roster &amp; rest factors →</a></p>
</section>"""
    (HERE / "day1.html").write_text(page("Day 1 review", "day1.html", body, meta))

    # ---------- factors
    items = []
    for item in research.get("context", []):
        srcs = " · ".join(link(s["url"], s["label"]) for s in item.get("sources", []))
        items.append(f'<article class="card"><p class="meta">{esc(item["kind"])} · {esc(item["date"])} · '
                     f'{"works against" if item["effect"] == "against" else "works for"} {esc(item["team"])}</p>'
                     f'<h3>{esc(item["team"])}</h3><p>{esc(item["summary"])}</p><p class="src">{srcs}</p></article>')
    body = f"""
<section class="hero"><h1>Roster, onboarding &amp; rest factors</h1>
<p class="lede">Situations that make an upset more likely than a team's name suggests: a new in-game leader still being onboarded, a player signed weeks ago,
a late replacement with no preparation, a heavy schedule. These are shown next to each match; they do not change the numbers (the prices already react to news),
but they help pick between two similar contrarian spots.</p></section>
<div class="cards">{"".join(items)}</div>"""
    (HERE / "factors.html").write_text(page("Roster & rest factors", "factors.html", body, meta))

    # ---------- unresolved & limits
    fb_items = []
    for r in open_rows:
        if r["pin"] and r["p_a"] is not None and not r["flags"]:
            continue
        fx = r["fx"]
        if r["p_a"] is None:
            why = "No pick — no outside price and no official rating for both teams."
        else:
            why = f"Likely winner {r['pick']} ({pct(max(r['p_a'], 1 - r['p_a']))}, {r['basis']}); plan pick: {r['protect_pick']}"
            if r["chase_pick"] != r["protect_pick"]:
                why += f" (chasing: {r['chase_pick']})"
            why += "."
        fb_items.append(f'<li><a href="index.html#m{esc(fx["match_id"])}"><strong>{esc(fx["team_a"])} vs {esc(fx["team_b"])}</strong></a> '
                        f'({esc(fmt_utc(fx.get("lock_utc")))}) — {esc(why)}<ul>{"".join(f"<li>{esc(f)}</li>" for f in r["flags"])}</ul></li>')
    body = f"""
<section class="hero"><h1>Unresolved picks &amp; limitations</h1>
<p class="lede">{len(unresolved)} open matches have no pick; {len(fallback)} rely on a secondary outside price or on our own line instead of Pinnacle.
Every open match with any caveat is listed below with the reason.</p></section>
<section aria-labelledby="h-ladder"><h2 id="h-ladder">Research ladder</h2>
<ol class="tight"><li><b>Pinnacle</b> moneyline for the same fixture (same two teams, kickoff within {MATCH_WINDOW_H:.0f} h), de-vigged.</li>
<li><b>Other outside prices</b>: Polymarket share prices and the bookmaker price bo3.gg relays (usually Thunderpick); averaged when both exist.</li>
<li><b>Our own line</b> from Valve's official VRS points (calibrated on today's outside prices: k = {cal['k']:.2f}, n = {cal['n']}, mean gap {('%.1f' % cal['mae_pp']) if cal['mae_pp'] is not None else '—'} pp).</li>
<li>HLTV pages are used for identity, format and results (read during the session; HLTV refuses most automated reads).</li></ol></section>
<section aria-labelledby="h-list"><h2 id="h-list">Matches with caveats ({len(fb_items)})</h2><ul class="caveats">{"".join(fb_items) or "<li>None.</li>"}</ul></section>
<section aria-labelledby="h-lim"><h2 id="h-lim">Limitations</h2><ul class="tight">
<li>Crowd splits are Hotspawn's public percentages; for TWC matches they rest on 15–20 picks, so one or two players move them several points.</li>
<li>Hotspawn's streak bonus size is not published; contrarian picks can break a streak — weigh that if you hold a long one.</li>
<li>Prices move; each row shows which source and capture it used. Matches Hotspawn adds between refreshes appear on the next 4-hourly run.</li>
<li>Our own line uses Valve VRS points only (no map pool, no roster changes after the 2026-10-05 standings — e.g. PARIVISION's 17 Sep signing).</li>
<li>{len([r for r in rows if r['status'] == 'stale'])} Hotspawn listings from June–July are still marked "scheduled" but locked months ago; they are counted, not picked (see <a href="flagged.html">Flagged</a>).</li>
</ul></section>"""
    (HERE / "unresolved.html").write_text(page("Unresolved & limits", "unresolved.html", body, meta))

    # ---------- flagged
    flagged = flagged_items(rows, capture, research)
    body = f"""
<section class="hero"><h1>Flagged for review</h1><p class="lede">Irregularities found while building this plan. None blocks a pick; each has a link for manual checking.</p></section>
<ul class="caveats">{"".join(f'<li><strong>{esc(t)}</strong> — {d} {link(u, "check")}</li>' for t, d, u in flagged)}</ul>"""
    (HERE / "flagged.html").write_text(page("Flagged for review", "flagged.html", body, meta))

    # ---------- method
    sc = research.get("scoring", {})
    body = f"""
<section class="hero"><h1>Method</h1><p class="lede">How the probabilities, the crowd leverage and the two plans are produced.</p></section>
<section id="scoring" aria-labelledby="h-sc"><h2 id="h-sc">Hotspawn scoring</h2><p>{esc(sc.get('summary'))} ({link(sc.get('source'), 'how it works')}, {link(sc.get('lobby_source'), 'lobby')})</p></section>
<section aria-labelledby="h-pr"><h2 id="h-pr">Win probabilities</h2><ul class="tight">
<li>Decimal prices are de-vigged proportionally: p = (1/odds) / Σ(1/odds). American prices are converted first.</li>
<li>Polymarket share prices are normalized to sum to 1; a market above 98.5% for one side is treated as settled and skipped.</li>
<li>Own line: per-map p = 1 / (1 + 10^(−k·ΔVRS/400)) (Valve's VRS convention, "400 points = 90%"), then the series probability for the fixture's best-of. k is fitted daily on matched outside prices (current k = {cal['k']:.2f}, n = {cal['n']}).</li>
<li>Teams are matched across sources only by exact name or a documented alias with evidence (e.g. Hotspawn "WROTBERRY" = WBT, proven by the identical six-fixture schedule on HLTV).</li>
<li>Hotspawn's crowd split is <strong>never</strong> a probability input; the build's probability function does not receive it, and a test changes the crowd numbers to prove the probabilities do not move.</li></ul></section>
<section aria-labelledby="h-lev"><h2 id="h-lev">Leverage and labels</h2><ul class="tight">
<li><b>Expected-points cost</b> of taking the underdog = points × (p<sub>fav</sub> − p<sub>dog</sub>).</li>
<li><b>Leverage</b> = p<sub>dog</sub> ÷ (share of Hotspawn players on the underdog). Above 1 the crowd under-owns the underdog relative to its real chance.</li>
<li><b>Contrarian value</b>: underdog ≥ 40% and leverage ≥ 1.5 — costs at most 20% of the match's points in expectation, but a hit gains the full points on most of the field.</li>
<li><b>Upset shot</b>: underdog 25–40% and leverage ≥ 3 — for players who must pass several people above them.</li>
<li><b>Take the favourite</b>: everything else. Thresholds are judgement calls shown openly so you can apply your own.</li>
<li><b>Protect a lead</b> = favourites + value spots. <b>Chase the top</b> = also upset shots. S-tier matches (7 pts) carry 3.5× the swing of C-tier (2 pts).</li></ul></section>
<section aria-labelledby="h-src"><h2 id="h-src">Sources and refresh</h2><ul class="tight">
<li>Hotspawn lobby / CS2 / Thunderpick boards — public Angular TransferState (fixture list, tier, points, lock time, crowd split).</li>
<li>Pinnacle public guest prices, Polymarket gamma API, bo3.gg public match API, Valve VRS repository ({link(VRS_BLOB_URL, vrs.get('file') or 'standings')}), HLTV world ranking ({esc(hltv.get('ranking_date'))}).</li>
<li>{link(WORKFLOW_URL, 'GitHub Actions')} re-collects and rebuilds every 4 hours; tests must pass before anything is published.</li></ul></section>"""
    (HERE / "method.html").write_text(page("Method", "method.html", body, meta))

    return {"meta": meta, "open": open_rows, "value": value, "upset": upset, "unresolved": unresolved,
            "fallback": fallback, "day1": d1, "day1_strategies": strat, "leader": leader, "tenth": tenth,
            "ev": {"safe": ev_safe, "protect": ev_protect, "chase": ev_chase}, "pts_open": pts_open}


def flagged_items(rows, capture, research):
    out = []
    hot = capture.get("hotspawn") or {}
    stale = [r for r in rows if r["status"] == "stale"]
    if stale:
        first = min(r["fx"]["start_utc"] for r in stale)
        last = max(r["fx"]["start_utc"] for r in stale)
        out.append(("Stale Hotspawn listings", esc(f"{len(stale)} CS2 fixtures dated {first[:10]} to {last[:10]} are still 'scheduled' in Hotspawn's data and counted in its filter totals, though they locked long ago."), HOTSPAWN_LOBBY))
    pages = hot.get("pages") or []
    main_pages = [p for p in pages if p.get("page") in ("lobby", "cs2-pickems")]
    heads = {p.get("header_matches_this_week") for p in main_pages if p.get("header_matches_this_week")}
    totals = {p.get("filter_all_tiers") for p in main_pages if p.get("filter_all_tiers")}
    if heads and totals:
        out.append(("Counter mismatch", esc(f"Hotspawn's header says {', '.join(map(str, sorted(heads)))} matches this week while the tier filter counts {', '.join(map(str, sorted(totals)))} (the filter includes the stale listings; the header may include LoL)."), HOTSPAWN_LOBBY))
    for r in rows:
        fx = r["fx"]
        if r["status"] != "open":
            continue
        url = fx.get("hotspawn_match_url") or ""
        if "waiting-for-information" in url:
            out.append(("Placeholder Hotspawn link", esc(f"{fx['team_a']} vs {fx['team_b']}: Hotspawn's 'View Match' link is a placeholder ({url}); use the HLTV link instead."), r["links"].get("hltv") or url))
        for part in (r["market"] or {}).get("parts", []):
            if part.get("kickoff_gap_min"):
                out.append(("Kickoff differs", esc(f"{fx['team_a']} vs {fx['team_b']}: {part['source']} lists {fmt_utc(part.get('start_utc'))}, Hotspawn {fmt_utc(fx.get('start_utc'))}."), part.get("url")))
    for a in research.get("aliases", []):
        if a.get("sources") and a["hotspawn"] in ("WROTBERRY",):
            out.append(("Team name differs", esc(f"Hotspawn calls WBT (WhiteBIT) '{a['hotspawn']}'. {a['proof']}"), a["sources"][0]))
    for item in research.get("context", []):
        if item["team"] == "PARIVISION":
            out.append(("Official ranking roster outdated", esc("Valve's 2026-10-05 VRS lists PARIVISION with slaxejezzz; HLTV and Liquipedia show HObbit signed 2026-09-17. Own-line rating may not reflect the current five."), item["sources"][2]["url"]))
        if item["team"] == "Privateer":
            out.append(("Incomplete roster", esc(item["summary"]), item["sources"][0]["url"]))
    for r in rows:
        if r["status"] == "open" and r["crowd_n"] is not None and r["crowd_n"] < 25:
            out.append(("Tiny crowd sample", esc(f"{r['fx']['team_a']} vs {r['fx']['team_b']}: crowd split from {r['crowd_n']} picks."), r["fx"].get("hotspawn_match_url") or HOTSPAWN_LOBBY))
    return out


# ------------------------------------------------------------------ data files
PLAN_FIELDS = ["match_id", "status", "competition", "tier", "points", "start_utc", "lock_utc", "best_of", "team_a", "team_b",
               "prob_a_pct", "prob_b_pct", "pick", "basis", "pinnacle_a_pct", "secondary_a_pct", "own_line_a_pct",
               "crowd_a_pct", "crowd_b_pct", "crowd_picks", "leverage", "ev_cost_pts", "label", "protect_pick", "chase_pick",
               "hotspawn_url", "hltv_url", "source_urls", "flags"]


def write_data(rows, cal, summary, capture, research, now):
    DATA.mkdir(parents=True, exist_ok=True)
    out = []
    for r in sorted(rows, key=lambda x: (x["fx"].get("start_utc") or "", x["fx"]["match_id"])):
        fx, c = r["fx"], r["c"] or {}
        sec = [p for p in (r["market"] or {}).get("parts", []) if p["source"] != "Pinnacle"]
        srcs = [fx.get("hotspawn_match_url") or HOTSPAWN_LOBBY] + [p.get("url") for p in (r["market"] or {}).get("parts", []) if p.get("url")]
        if r["links"].get("hltv"):
            srcs.append(r["links"]["hltv"])
        if r["own_p"] is not None:
            srcs.append(VRS_BLOB_URL)
        lev = c.get("leverage")
        out.append({
            "match_id": fx["match_id"], "status": r["status"], "competition": fx.get("competition"), "tier": fx.get("tier"),
            "points": fx.get("offered_points"), "start_utc": fx.get("start_utc"), "lock_utc": fx.get("lock_utc"),
            "best_of": r["best_of"], "team_a": fx.get("team_a"), "team_b": fx.get("team_b"),
            "prob_a_pct": None if r["p_a"] is None else round(r["p_a"] * 100, 1),
            "prob_b_pct": None if r["p_a"] is None else round((1 - r["p_a"]) * 100, 1),
            "pick": r["pick"], "basis": r["basis"] if r["status"] in ("open", "locked") else "",
            "pinnacle_a_pct": round(r["pin"]["p_a"] * 100, 1) if r["pin"] else None,
            "secondary_a_pct": round(sum(p["p_a"] for p in sec) / len(sec) * 100, 1) if sec else None,
            "own_line_a_pct": None if r["own_p"] is None else round(r["own_p"] * 100, 1),
            "crowd_a_pct": r["crowd_a"], "crowd_b_pct": r["crowd_b"], "crowd_picks": r["crowd_n"],
            "leverage": None if lev is None else (None if lev == float("inf") else round(lev, 2)),
            "ev_cost_pts": None if not c else round(c["ev_cost"], 2), "label": c.get("label"),
            "protect_pick": r["protect_pick"], "chase_pick": r["chase_pick"],
            "hotspawn_url": fx.get("hotspawn_match_url") or HOTSPAWN_LOBBY, "hltv_url": r["links"].get("hltv") or "",
            "source_urls": " ".join(dict.fromkeys(s for s in srcs if s)), "flags": " | ".join(r["flags"]),
        })
    with (DATA / "plan.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=PLAN_FIELDS)
        w.writeheader()
        for row in out:
            w.writerow({k: ("" if row[k] is None else row[k]) for k in PLAN_FIELDS})
    (DATA / "plan.json").write_text(json.dumps({"generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                                "capture_utc": summary["meta"]["capture_utc"], "rows": out}, indent=1, ensure_ascii=False) + "\n")
    d1f = ["match_id", "start_utc", "competition", "tier", "points", "team_a", "team_b", "pinnacle_a_pct", "crowd_a", "crowd_b",
           "crowd_n", "winner", "score", "crowd_fav", "crowd_fav_won", "market_fav", "market_fav_won", "label", "hltv_url", "capture_url"]
    with (DATA / "day1.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=d1f)
        w.writeheader()
        for r in summary["day1"]:
            w.writerow({"match_id": r["match_id"], "start_utc": r["start_utc"], "competition": r["competition"], "tier": r["tier"],
                        "points": r["points"], "team_a": r["team_a"], "team_b": r["team_b"],
                        "pinnacle_a_pct": "" if r["p_a"] is None else round(r["p_a"] * 100, 1),
                        "crowd_a": r["crowd_a"], "crowd_b": r["crowd_b"], "crowd_n": r["crowd_n"], "winner": r["winner"],
                        "score": r["score"], "crowd_fav": r["crowd_fav"], "crowd_fav_won": r["crowd_fav_won"],
                        "market_fav": r["mkt_fav"] or "", "market_fav_won": "" if r["mkt_fav_won"] is None else r["mkt_fav_won"],
                        "label": (r["c"] or {}).get("label", ""), "hltv_url": r["hltv"], "capture_url": research["day1"]["capture_url"]})
    save_calibration(cal["rows"])
    hot = capture.get("hotspawn") or {}
    summ = {
        "generated_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "capture_utc": summary["meta"]["capture_utc"],
        "sources": {k: {"mode": (capture.get(k) or {}).get("mode"), "fetched_utc": (capture.get(k) or {}).get("fetched_utc")}
                    for k in ("hotspawn", "pinnacle", "bo3", "polymarket", "vrs", "hltv_ranking")},
        "fixtures_total": len(rows), "open": len(summary["open"]),
        "open_with_pick": sum(1 for r in summary["open"] if r["p_a"] is not None),
        "open_pinnacle": sum(1 for r in summary["open"] if r["pin"]),
        "open_secondary": sum(1 for r in summary["open"] if r["market"] and not r["pin"]),
        "open_own_line": sum(1 for r in summary["open"] if r["p_a"] is not None and not r["market"]),
        "open_unresolved": len(summary["unresolved"]), "value": len(summary["value"]), "upset": len(summary["upset"]),
        "stale_listings": sum(1 for r in rows if r["status"] == "stale"),
        "locked_recent": sum(1 for r in rows if r["status"] == "locked"),
        "calibration": {"k": cal["k"], "n": cal["n"], "mae_pp": None if cal["mae_pp"] is None else round(cal["mae_pp"], 2)},
        "leaderboard": {"leader": summary["leader"], "tenth": summary["tenth"]}, "week": hot.get("week"),
        "expected_points": {k: round(v, 2) for k, v in summary["ev"].items()}, "points_open": summary["pts_open"],
        "day1_strategies": summary["day1_strategies"],
    }
    (DATA / "summary.json").write_text(json.dumps(summ, indent=1, ensure_ascii=False) + "\n")
    return summ


def main() -> int:
    capture, research = load_inputs()
    now = now_from(capture)
    rows, cal, vrs, hltv = build_rows(capture, research, now)
    summary = render(rows, cal, vrs, hltv, capture, research, now)
    summ = write_data(rows, cal, summary, capture, research, now)
    print(f"leaderboard: {summ['open']} open, {summ['open_with_pick']} picked "
          f"({summ['open_pinnacle']} Pinnacle, {summ['open_secondary']} secondary, {summ['open_own_line']} own line), "
          f"{summ['value']} value, {summ['upset']} upset, k={summ['calibration']['k']} n={summ['calibration']['n']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
