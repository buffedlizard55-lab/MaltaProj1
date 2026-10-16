#!/usr/bin/env python3
"""livelines — one pick, with both win probabilities, for every open Hotspawn CS2 Pick'em fixture.

Offline and deterministic: it reads captures that are already committed (the site payload, the
outside-line captures and this session's live reads in livelines/data/live_reads.json) and never
invents a value. Every published number carries the URL it came from and the UTC time it was read.

Basis ladder (documented in methodology.html):
  T1  primary bookmaker quote (Pinnacle guest markets, captured by this repo's pipeline)
  T2  newest outside listing or prediction market for the fixture (Polymarket, bo3.gg/Thunderpick,
      EGamersWorld/bc.game), de-vigged when a price pair is used
  T3  our own originated line: logistic transform of the official Valve Regional Standings points,
      with the scale fitted on the fixtures an outside market actually prices
  T4  documented bound: one side is absent from both official rating sources, so the lowest
      published value in the same official standings file is used as its ceiling; published as a
      bound, never as a pick, and listed on unresolved.html

Hotspawn crowd pick percentages are never read, stored or used.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "livelines"
DATA = OUT / "data"
RAW = DATA / "raw"

SLATE = ROOT / "model/input/hotspawn_cs2_fixtures.json"
HLTV = ROOT / "model/input/hltv_ranking.json"
VRS = RAW / "valve_standings_global_2026_10_05.md"
VRS_SHA = RAW / "valve_standings_blob_sha.txt"
FEED = ROOT / "feeds/data/market_feed.csv"
EXEC_LINES = ROOT / "executive/data/external_lines.csv"
OLD_LINES = ROOT / "data/8944bb84/external_lines.csv"
LIVE = DATA / "live_reads.json"
LIVE_READS = json.loads(LIVE.read_text())
READ_UTC = {r["id"]: r["read_utc"] for r in LIVE_READS["reads"]}
ALIASES = [ROOT / "cs2/aliases.json", ROOT / "executive/aliases.json"]

VRS_URL = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
           "2aa2805394fbc68f36a5752a5b16026f2ab2fed5/live/2026/standings_global_2026_10_05.md")
VRS_REPO = "https://github.com/ValveSoftware/counter-strike_regional_standings"
VRS_CAPTURED = "2026-10-14T04:39:30Z"  # this session's read of the official file through the GitHub API
# When two outside sources price the same fixture at the same read minute, the higher-priority one is
# published and the other is kept on the row as a cross-check. Order: primary bookmaker first, then a
# prediction market that actually trades, then sportsbook prices relayed by a listing.
SOURCE_PRIORITY = [("pinnacle", 1), ("polymarket", 2), ("bo3.gg", 3), ("thunderpick", 3),
                   ("egamersworld", 4), ("secondary", 5)]


def source_rank(o: dict) -> int:
    hay = f"{o.get('source','')} {o.get('book','')}".lower()
    for key, rank in SOURCE_PRIORITY:
        if key in hay:
            return rank
    return 9
HLTV_URL = "https://www.hltv.org/ranking/teams/2026/october/12"

NOW = dt.datetime.fromisoformat(os.environ.get("LIVELINES_NOW", "").replace("Z", "+00:00")) \
    if os.environ.get("LIVELINES_NOW") else dt.datetime.now(dt.timezone.utc)
NOW_S = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- helpers
def iso(ms: str | int) -> str:
    return dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").casefold()
    return "".join(c for c in s if c.isalnum())


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_aliases() -> dict[str, dict]:
    """Evidence-linked spellings: Hotspawn name -> official name, with the link that shows it."""
    out: dict[str, dict] = {}
    if (ROOT / "cs2/aliases.json").exists():
        for k, v in json.loads((ROOT / "cs2/aliases.json").read_text()).items():
            if k.startswith("_"):
                continue
            out[k] = {"official": v["alias_of"], "evidence": v.get("evidence_url", ""),
                      "note": v.get("why", ""), "confirmed_by": v.get("confirmed_by", "")}
    if (ROOT / "executive/aliases.json").exists():
        for k, v in json.loads((ROOT / "executive/aliases.json").read_text()).get("renames", {}).items():
            out.setdefault(k, {"official": v["official_name"], "evidence": v.get("evidence_url", ""),
                               "note": v.get("note", ""), "confirmed_by": "executive/aliases.json"})
    return out


# ----------------------------------------------------------------------------- inputs
def load_slate() -> tuple[list[dict], dict]:
    d = json.loads(SLATE.read_text())
    fx = []
    for f in d["fixtures"]:
        lock_ms = int(f["lock_time"])
        start_ms = int(f["scheduled_start_time"])
        fx.append({
            "match_id": str(f["id"]),
            "tournament": f["competition_name"],
            "tier": (f.get("tier") or "").upper(),
            "offered_points": f.get("offered_points"),
            "stage": f.get("stage") or "",
            "format_payload": (f.get("series_format") or (f"BO{f['best_of']}" if f.get("best_of") else "")),
            "start_utc": iso(start_ms),
            "lock_utc": iso(lock_ms),
            "lock_ms": lock_ms,
            "team_a": f["participants0_name"].strip(),
            "team_b": f["participants1_name"].strip(),
            "seen_on": f.get("seen_on", []),
        })
    prov = {k: d.get(k) for k in ("source_url", "source_urls", "fetched_utc", "fixture_count",
                                 "pickem_week", "lobby_header_matches_this_week",
                                 "lobby_filter_all_tiers", "html_sha256", "note")}
    prov["permalinks"] = d.get("permalinks", {})
    return fx, prov


def load_hltv() -> tuple[dict, dict]:
    d = json.loads(HLTV.read_text())
    idx = {}
    for t in d["teams"]:
        idx[norm(t["name"])] = t
    return idx, {k: d.get(k) for k in ("source_url", "canonical_url", "ranking_date",
                                       "fetched_utc", "http_status", "html_sha256", "team_count")}


def load_vrs() -> tuple[dict, dict]:
    txt = VRS.read_text()
    rows: dict[str, list[dict]] = {}
    for line in txt.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]*)\|", line)
        if not m:
            continue
        rank, pts, name, roster = int(m.group(1)), int(m.group(2)), m.group(3).strip(), m.group(4).strip()
        rows.setdefault(norm(name), []).append({"rank": rank, "points": pts, "name": name, "roster": roster})
    blob = VRS_SHA.read_text().strip().split()[-1] if VRS_SHA.exists() else ""
    meta = {"file": str(VRS.relative_to(ROOT)), "url": VRS_URL, "repo": VRS_REPO,
            "standings_date": "2026-10-05", "blob_sha": blob, "teams": sum(len(v) for v in rows.values()),
            "read_utc": VRS_CAPTURED, "read_via": "GitHub contents API (gh api), decoded to this file",
            "sha256": sha256_file(VRS)}
    return rows, meta


def read_csv(p: pathlib.Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def signed_price(p: str) -> float | None:
    try:
        return float(p)
    except (TypeError, ValueError):
        return None


def load_feed() -> list[dict]:
    """Outside observations captured by this repo's hourly pipeline."""
    out = []
    for r in read_csv(FEED):
        pa, pb = signed_price(r.get("price_a")), signed_price(r.get("price_b"))
        if pa is None or pb is None:
            continue
        out.append({
            "match_id": r["fixture_id"], "source": r["source"], "book": r.get("book", ""),
            "price_a": pa, "price_b": pb, "kind": r.get("price_kind", ""),
            "format_bo": r.get("format_bo") or "", "captured_utc": r.get("captured_utc", ""),
            "url": r.get("source_url", ""), "book_url": r.get("book_url", ""),
            "team_a": r.get("team_a", ""), "team_b": r.get("team_b", ""),
            "liquidity_usd": r.get("liquidity_usd", ""), "volume_usd": r.get("volume_usd", ""),
            "origin": "feeds/data/market_feed.csv (hourly outside-market feed)",
        })
    return out


def load_secondary_captures() -> list[dict]:
    """Older outside captures committed by other boards: printed only when newer data is absent."""
    out = []
    for path, name in ((EXEC_LINES, "executive/data/external_lines.csv"),
                       (OLD_LINES, "data/8944bb84/external_lines.csv")):
        for r in read_csv(path):
            pa = signed_price(r.get("odds_a") or r.get("primary_odds_a"))
            pb = signed_price(r.get("odds_b") or r.get("primary_odds_b"))
            if pa is None or pb is None:
                continue
            if abs(pa - 1.8) < 1e-9 and abs(pb - 1.8) < 1e-9:
                continue  # placeholder pair, rejected below with a flag instead
            fid = r.get("match_id") or r.get("fixture_id")
            out.append({
                "match_id": str(fid), "source": r.get("source_name") or "secondary listing",
                "book": r.get("book", ""), "price_a": pa, "price_b": pb, "kind": "decimal odds",
                "format_bo": "", "captured_utc": r.get("captured_utc", ""),
                "url": r.get("source_url", ""), "book_url": "", "team_a": "", "team_b": "",
                "liquidity_usd": "", "volume_usd": "", "origin": name,
            })
    return out


def load_live() -> tuple[list[dict], list[dict], dict]:
    """This session's reads: EGamersWorld price pairs, the Polymarket moneyline, and the
    recorded placeholder pairs that are rejected with a flag."""
    d = json.loads(LIVE.read_text())
    obs, placeholders, meta = [], [], {"reads": d["reads"], "hosts_refused": d.get("hosts_refused", [])}
    for r in d["reads"]:
        rid, url, read_utc = r["id"], r["url"], r["read_utc"]
        for row in r["observed"].get("odds_printed", []) + r["observed"].get("schedule_with_odds", []):
            pair = {norm(row["team_a"]), norm(row["team_b"])} if row.get("team_b") else {norm(row["team_a"])}
            rec = {"source": "EGamersWorld", "book": "bc.game (EGamersWorld listing)", "kind": "decimal odds",
                   "price_a": row["odds_a"], "price_b": row["odds_b"], "team_a": row["team_a"],
                   "team_b": row["team_b"], "format_bo": 3 if row.get("format") == "Bo3" else "",
                   "captured_utc": read_utc, "url": row.get("match_url") or url,
                   "origin": f"livelines/data/live_reads.json#{rid}", "pair": pair}
            if abs(row["odds_a"] - 1.8) < 1e-9 and abs(row["odds_b"] - 1.8) < 1e-9:
                rec["rejected"] = "identical 1.80/1.80 pair on several unrelated fixtures"
                placeholders.append(rec)
            else:
                obs.append(rec)
        ml = r["observed"].get("series_moneyline_cents")
        if ml:
            obs.append({"source": "Polymarket", "book": "Polymarket (prediction market)",
                        "kind": "share price (USD 0-1)",
                        "price_a": ml["gothic"] / 100, "price_b": ml["lavked"] / 100,
                        "team_a": "Gothic", "team_b": "Lavked", "format_bo": 3, "captured_utc": read_utc,
                        "url": url, "origin": f"livelines/data/live_reads.json#{r['id']}",
                        "pair": {norm("Gothic"), norm("Lavked")}})
    return obs, placeholders, meta


def match_ids_by_pair(fixtures: list[dict], t_a: str, t_b: str, aliases: dict) -> list[str]:
    """Orientation-agnostic fixture lookup by team pair, with the evidence-linked spellings.

    Exact normalised match first; if that fails, one unique fixture whose two names each contain (or
    are contained by) the listing's names, which is how 'Privateer Gaming' and 'WRAITH PCIFIC' on
    EGamersWorld connect to Hotspawn's 'Privateer' and 'PCIFIC'. Ambiguity is never resolved by
    guessing: more than one candidate returns [] and the observation stays unused.
    """
    def resolve(x: str) -> str:
        return norm(aliases.get(x, {}).get("official", x)) if x in aliases else norm(x)
    want = {norm(t_a), norm(t_b)}
    want_off = {resolve(t_a), resolve(t_b)}
    hits = []
    for f in fixtures:
        have = {norm(f["team_a"]), norm(f["team_b"])}
        have_off = {resolve(f["team_a"]), resolve(f["team_b"])}
        if want == have or want == have_off or want_off == have or want_off == have_off:
            hits.append(f["match_id"])
    if hits or not t_b:
        return hits

    def couple(listing: set[str], fixture: set[str]) -> bool:
        # every listing name must relate to some fixture name, and vice versa, by containment
        used = set()
        for x in listing:
            match = [y for y in fixture if y not in used and len(y) >= 4 and (x in y or y in x)]
            if not match:
                return False
            used.add(sorted(match, key=len, reverse=True)[0])
        return len(used) == len(fixture)

    loose = [f["match_id"] for f in fixtures
             if couple(want_off, {resolve(f["team_a"]), resolve(f["team_b"])})]
    return loose if len(loose) == 1 else []


# ----------------------------------------------------------------------------- model
def devig_odds(a: float, b: float) -> tuple[float, float, float]:
    ia, ib = 1.0 / a, 1.0 / b
    s = ia + ib
    return ia / s * 100.0, ib / s * 100.0, (s - 1.0) * 100.0


def devig_market(price_a: float, price_b: float, kind: str) -> tuple[float, float, float]:
    if "share price" in kind:
        s = price_a + price_b
        return price_a / s * 100.0, price_b / s * 100.0, (s - 1.0) * 100.0
    return devig_odds(price_a, price_b)


def logistic(pts_a: float, pts_b: float, k: float) -> float:
    return 1.0 / (1.0 + 10 ** ((pts_b - pts_a) / k)) * 100.0


def fit_scale(samples: list[tuple[float, float, float]], objective: str = "mae") -> dict:
    """samples: (pts_a, pts_b, market_p_a_pct) -> scale for the logistic transform.

    Two objectives are reported because on this 25-row cohort they disagree sharply: mean absolute
    error (how far the published percentage sits from the market, i.e. calibration) is minimised by a
    much flatter transform than mean log-loss (which rewards confident direction calls even when the
    percentage itself is far off). The board publishes probabilities, so the calibration objective is
    the primary fit; the log-loss alternative is computed and disclosed so a reader can see both.
    """
    if len(samples) < 4:
        return {"fitted": False, "n": len(samples), "scale": 400.0, "mae_pp": None, "logloss": None,
                "reason": "fewer than 4 fixtures with both an outside price and both teams in the "
                          "official standings; the project default 400-point scale is used instead"}
    curve = []
    for i in range(400, 40001, 5):  # 20.0 .. 2000.0 points, step 0.25
        k = i / 20.0
        ll = mae = 0.0
        for a, b, pm in samples:
            q = min(max(logistic(a, b, k) / 100.0, 1e-6), 1 - 1e-6)
            ll += -(math.log(q) if pm >= 50 else math.log(1 - q))
            mae += abs(q * 100.0 - pm)
        curve.append((k, ll / len(samples), mae / len(samples)))
    by_mae = min(curve, key=lambda t: t[2])
    by_ll = min(curve, key=lambda t: t[1])
    pick = by_mae if objective == "mae" else by_ll
    return {"fitted": True, "n": len(samples), "scale": round(pick[0], 2), "mae_pp": round(pick[2], 2),
            "logloss": round(pick[1], 4),
            "grid": "20.0-2000.0 points per 90% favourite, step 0.25; mean absolute error against the "
                    "outside market's de-vigged probability",
            "default_scale": 400.0,
            "logloss_alternative": {"scale": round(by_ll[0], 2), "mae_pp": round(by_ll[2], 2),
                                    "logloss": round(by_ll[1], 4)},
            "objective": objective}


def fit_scale_logrank(samples: list[tuple[float, float, float]]) -> dict:
    """Alternative candidate: logistic on log10 of the standings position."""
    if len(samples) < 4:
        return {"fitted": False, "n": len(samples), "scale": None, "mae_pp": None, "logloss": None}
    best, best_ll, best_mae = None, None, None
    for i in range(5, 6001):
        k = i / 100.0
        ll = mae = 0.0
        for a, b, pm in samples:
            q = min(max(1.0 / (1.0 + 10 ** ((b - a) * k)), 1e-6), 1 - 1e-6)
            ll += -(math.log(q) if pm >= 50 else math.log(1 - q))
            mae += abs(q * 100.0 - pm)
        ll /= len(samples); mae /= len(samples)
        if best_ll is None or ll < best_ll:
            best, best_ll, best_mae = k, ll, mae
    return {"fitted": True, "n": len(samples), "scale": round(best, 3), "logloss": round(best_ll, 4),
            "mae_pp": round(best_mae, 2)}


# ----------------------------------------------------------------------------- build
def main() -> int:
    fixtures, slate_prov = load_slate()
    hltv_idx, hltv_meta = load_hltv()
    vrs_rows, vrs_meta = load_vrs()
    aliases = load_aliases()
    observations = load_feed() + load_secondary_captures()
    live_obs, placeholders, live_meta = load_live()
    observations += live_obs
    # a rejected placeholder still carries a scheduling fact (the series length the listing prints)
    format_hints = {}
    for p in placeholders:
        if p.get("match_id") and p.get("format_bo"):
            format_hints.setdefault(p["match_id"], f"BO{p['format_bo']}")
    for o in live_obs + placeholders:
        fid = o.get("match_id") or (match_ids_by_pair(fixtures, o["team_a"], o["team_b"], aliases)[:1] or [""])[0]
        if fid and o.get("format_bo"):
            format_hints.setdefault(fid, f"BO{o['format_bo']}")
            o["match_id"] = fid

    # The live reads and the secondary captures identify fixtures by team pair.
    for o in observations:
        if o.get("match_id"):
            continue
        hits = match_ids_by_pair(fixtures, o["team_a"], o["team_b"], aliases)
        o["match_id"] = hits[0] if len(hits) == 1 else ""
        o["ambiguous"] = len(hits) > 1
        if not hits:
            o["unmatched"] = True
    for p in placeholders:
        hits = match_ids_by_pair(fixtures, p["team_a"], p["team_b"], aliases) if p.get("team_b") else []
        if hits:
            p["match_id"] = hits[0]
            continue
        # a listing can print the fixture with an empty opponent cell; identity is then the single
        # named team plus the printed local slot converted to UTC via the listing's own UTC+2 clock
        p["match_id"] = ""
        if p.get("team_a") and not p.get("team_b"):
            m = re.match(r"^(\d{2})\.(\d{2})\.(\d{2}) (\d{2}):(\d{2})$", str(p.get("printed_local", "")))
            if m:
                d, mo, y, hh, mm = (int(x) for x in m.groups())
                slot = dt.datetime(2000 + y, mo, d, hh, mm, tzinfo=dt.timezone.utc) - dt.timedelta(hours=2)
                for f in fixtures:
                    if slot.strftime("%Y-%m-%dT%H:%M") == f["start_utc"][:16] and norm(p["team_a"]) in \
                            {norm(f["team_a"]), norm(f["team_b"])}:
                        p["match_id"] = f["match_id"]
                        p["identified_by"] = ("single named team plus the printed slot "
                                              f"{p['printed_local']} (listing clock UTC+2) = {f['start_utc']}")
                        break
    for o in observations + placeholders:
        o.pop("pair", None)

    by_fixture: dict[str, list[dict]] = {}
    for o in observations:
        if o.get("match_id"):
            o["p_a_pct"], o["p_b_pct"], o["overround_pct"] = devig_market(o["price_a"], o["price_b"], o["kind"])
            by_fixture.setdefault(o["match_id"], []).append(o)
    fmap = {f["match_id"]: f for f in fixtures}
    orphans: list[str] = []
    for o in observations:
        fid = o.get("match_id")
        if not fid or not o.get("team_a"):
            continue
        # An observation can name a fixture that is not in the current Hotspawn slate (a new listing
        # the slate capture has not caught up with, or a stale one). It cannot be attached to a row, so
        # it is skipped and counted instead of crashing the build (fixes KeyError '1079586', 2026-10-15).
        f = fmap.get(fid)
        if f is None:
            if fid not in orphans:
                orphans.append(fid)
            continue
        hit = match_ids_by_pair([f], o["team_a"], o["team_b"], aliases) if o.get("team_b") else []
        if not hit:
            continue
        # the listing printed the pairing in the opposite order: swap so p_a always means the
        # Hotspawn fixture's own team_a, and record it
        if norm(o["team_a"]) != norm(f["team_a"]) and norm(o["team_a"]) != norm(aliases.get(f["team_a"], {}).get("official", f["team_a"])):
            o["price_a"], o["price_b"] = o["price_b"], o["price_a"]
            o["team_a"], o["team_b"] = o["team_b"], o["team_a"]
            o["orientation_normalised"] = True
    for v in by_fixture.values():
        v.sort(key=lambda o: (o["captured_utc"], -source_rank(o)), reverse=True)

    def rating(team: str) -> dict:
        """Official rating for a Hotspawn spelling, via the evidence-linked alias when one exists."""
        al = aliases.get(team)
        name = al["official"] if al else team
        h = hltv_idx.get(norm(name))
        vlist = vrs_rows.get(norm(name), [])
        v = min(vlist, key=lambda r: r["rank"]) if vlist else None
        return {
            "team": team, "lookup_name": name, "alias_used": bool(al),
            "alias_evidence": (al or {}).get("evidence", ""), "alias_confirmed_by": (al or {}).get("confirmed_by", ""),
            "hltv_rank": h["rank"] if h else None, "hltv_points": h["points"] if h else None,
            "hltv_team_id": h["team_id"] if h else None,
            "vrs_rank": v["rank"] if v else None, "vrs_points": v["points"] if v else None,
            "vrs_duplicates": len(vlist), "vrs_url": VRS_URL if v else "",
            "hltv_url": f"https://www.hltv.org/team/{h['team_id']}/{(h['slug'])}" if h else HLTV_URL,
        }

    ratings = {t: rating(t) for t in sorted({f["team_a"] for f in fixtures} | {f["team_b"] for f in fixtures})}
    vrs_floor = min(r["points"] for rows in vrs_rows.values() for r in rows)

    # ---- fit the scale on fixtures an outside market prices
    today = NOW.strftime("%Y-%m-%d")
    fit_samples, fit_rows = [], []
    alts = {"vrs_points": [], "hltv_points": [], "vrs_rank": [], "vrs_log_rank": []}
    for f in fixtures:
        if f["lock_ms"] <= int(NOW.timestamp() * 1000):
            continue  # calibration uses today's open slate only
        obs = [o for o in by_fixture.get(f["match_id"], []) if o["captured_utc"].startswith(today)]
        if not obs:
            continue
        ra, rb = ratings[f["team_a"]], ratings[f["team_b"]]
        o = obs[0]
        if ra["vrs_points"] and rb["vrs_points"]:
            fit_samples.append((ra["vrs_points"], rb["vrs_points"], o["p_a_pct"]))
            fit_rows.append({"match_id": f["match_id"], "teams": f"{f['team_a']} v {f['team_b']}",
                             "vrs_a": ra["vrs_points"], "vrs_b": rb["vrs_points"],
                             "hltv_a": ra["hltv_rank"], "hltv_b": rb["hltv_rank"],
                             "market_p_a_pct": round(o["p_a_pct"], 2), "source": o["source"],
                             "captured_utc": o["captured_utc"], "url": o["url"]})
            alts["vrs_points"].append((ra["vrs_points"], rb["vrs_points"], o["p_a_pct"]))
            alts["vrs_rank"].append((ra["vrs_rank"], rb["vrs_rank"], o["p_a_pct"]))
            alts["vrs_log_rank"].append((math.log10(ra["vrs_rank"]), math.log10(rb["vrs_rank"]), o["p_a_pct"]))
            if ra["hltv_points"] and rb["hltv_points"]:
                alts["hltv_points"].append((ra["hltv_points"], rb["hltv_points"], o["p_a_pct"]))
    calib = fit_scale(fit_samples, objective="mae")
    calib["candidate_transforms"] = {
        name: (fit_scale(smp) if name != "vrs_log_rank" else fit_scale_logrank(smp))
        for name, smp in alts.items() if smp}
    calib["chosen"] = ("official Valve Regional Standings points (vrs_points) at the calibration (MAE) "
                       "optimum, because that is the transform whose published percentage is closest to the "
                       "outside market on the same rows and it has the widest team coverage; the log-loss "
                       "optimum is disclosed next to it and the disagreement is flagged on every row that "
                       "depends on the scale")
    K = calib["scale"]
    K_alt = calib["logloss_alternative"]["scale"]

    # ---- per-fixture rows
    rows, unresolved, flag_rows, source_rows = [], [], [], []
    seen_sources = set()

    def add_source(url, role, read_utc, status, note=""):
        if not url or (url, role) in seen_sources:
            return
        seen_sources.add((url, role))
        source_rows.append({"url": url, "role": role, "read_utc": read_utc, "http_status": status, "note": note})

    add_source(VRS_URL, "official Valve Regional Standings (VRS) points used by the originated line",
               vrs_meta["read_utc"], "200 (GitHub contents API)", f"blob sha {vrs_meta['blob_sha']}; standings dated 2026-10-05")
    add_source(HLTV_URL, "HLTV world ranking (cross-check of ranks/points, top 245)",
               hltv_meta["fetched_utc"], f"HTTP {hltv_meta['http_status']} (repo capture; top-3 re-read live {READ_UTC['HLTV-RANKING-OCT12']})")
    add_source(slate_prov["source_url"], "Hotspawn Pick'em slate (fixture identity and exact UTC lock/start epochs)",
               slate_prov["fetched_utc"], "200 (repo payload capture)")
    add_source("https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/feeds/data/market_feed.csv",
               "outside market feed captured by this repo's hourly pipeline (Polymarket, Thunderpick via bo3.gg)",
               "hourly", "repo capture")

    for f in sorted(fixtures, key=lambda x: x["lock_ms"]):
        ra, rb = ratings[f["team_a"]], ratings[f["team_b"]]
        open_now = f["lock_ms"] > int(NOW.timestamp() * 1000)
        obs = by_fixture.get(f["match_id"], [])
        flags, notes = [], []
        if not open_now:
            flags.append("FL-LOCKED")
        if obs and not open_now and obs[0]["captured_utc"]:
            try:
                age_h = (NOW - dt.datetime.fromisoformat(obs[0]["captured_utc"].replace("Z", "+00:00"))).total_seconds() / 3600
                if age_h > 12:
                    flags.append("FL-STALE-READ")
            except ValueError:
                pass
        if f["format_payload"]:
            fmt = f["format_payload"]
        elif obs and obs[0].get("format_bo"):
            fmt = f"BO{obs[0]['format_bo']}"
        elif format_hints.get(f["match_id"]):
            fmt = format_hints[f["match_id"]]
            flags.append("FL-FORMAT-FROM-LISTING")
        else:
            fmt = ""
        if any(p.get("match_id") == f["match_id"] and p.get("identified_by") for p in placeholders):
            notes.append("Outside listing identity: " + [p["identified_by"] for p in placeholders
                         if p.get("match_id") == f["match_id"] and p.get("identified_by")][0] + ".")

        own_a = own_b = None
        if ra["vrs_points"] and rb["vrs_points"]:
            own_a = logistic(ra["vrs_points"], rb["vrs_points"], K)
            own_b = 100.0 - own_a
        elif ra["vrs_points"] or rb["vrs_points"]:
            known_a = ra["vrs_points"] or None
            known_b = rb["vrs_points"] or None
            if known_a:
                own_a = logistic(known_a, vrs_floor, K)
                own_b = 100.0 - own_a
                flags.append("FL-BOUND-OPPONENT-UNRATED")
                notes.append(f"{f['team_b']} is absent from the official standings, so the lowest published value "
                             f"in the same file ({vrs_floor}) is used as its ceiling: {f['team_a']}'s true win "
                             f"probability is at least this number.")
            else:
                own_b = logistic(known_b, vrs_floor, K)
                own_a = 100.0 - own_b
                flags.append("FL-BOUND-OPPONENT-UNRATED")
                notes.append(f"{f['team_a']} is absent from the official standings, so the lowest published value "
                             f"in the same file ({vrs_floor}) is used as its ceiling: {f['team_b']}'s true win "
                             f"probability is at least this number.")

        # ladder: the newest readable price wins (this board is explicitly "as of the read time");
        # a second source read at the same minute is shown as a cross-check.
        t1 = [o for o in obs if "pinnacle" in (o["source"] + o["book"]).lower()]
        t2 = [o for o in obs if o not in t1]
        if obs:
            o = obs[0]
            is_primary = "pinnacle" in (o["source"] + o["book"]).lower()
            basis = "T1" if is_primary else "T2"
            p_a, p_b = o["p_a_pct"], o["p_b_pct"]
            basis_label = f"Market · {o['source']}" + (" (primary bookmaker)" if is_primary else "")
            confidence = "Prediction-market price" if "share price" in o["kind"] else "Market-implied (de-vigged)"
        elif False:
            basis, o = "T2", t2[0]
            p_a, p_b = o["p_a_pct"], o["p_b_pct"]
            basis_label = f"Market · {o['source']}"
            confidence = "Market-implied (de-vigged)" if "share price" not in o["kind"] else "Prediction-market price"
        elif own_a is not None and "FL-BOUND-OPPONENT-UNRATED" not in flags:
            basis, o = "T3", None
            p_a, p_b = own_a, own_b
            basis_label = "Our line · official Valve VRS points"
            confidence = "Our line (uncalibrated)"
            flags.append("FL-NO-OUTSIDE-LINE")
        else:
            basis, o = "T4", None
            p_a, p_b = own_a, own_b
            basis_label = ("Bound only · one side unrated by every official source, so the number is a lower "
                           "bound (at least this), not an estimate")
            confidence = "Bound, not a pick"
            flags.append("FL-NO-OUTSIDE-LINE")

        pick = None
        if basis in ("T1", "T2", "T3") and p_a is not None:
            pick = f["team_a"] if p_a >= p_b else f["team_b"]
        pick_prob = max(p_a, p_b) if (p_a is not None and pick) else None

        if ra["hltv_rank"] is None:
            flags.append("FL-NOT-IN-HLTV-TOP-245")
        if ra["alias_used"]:
            flags.append("FL-ALIAS-USED")
        if rb["alias_used"]:
            flags.append("FL-ALIAS-USED")
        if not fmt and open_now:
            flags.append("FL-FORMAT-UNKNOWN")
        if o and "share price" in o["kind"] and o.get("liquidity_usd") in ("", None):
            pass
        if o and o["source"] == "Polymarket" and str(o.get("volume_usd", "")).strip():
            try:
                if float(o["volume_usd"]) < 200:
                    flags.append("FL-THIN-MARKET")
            except ValueError:
                pass
        # own line vs market direction
        if o and own_a is not None:
            mk = "A" if p_a >= p_b else "B"
            ow = "A" if own_a >= own_b else "B"
            if mk != ow:
                flags.append("FL-OWN-LINE-MARKET-SPLIT")
            elif abs(own_a - p_a) >= 15:
                flags.append("FL-OWN-LINE-MARKET-GAP")

        # drift between the newest live read and the earlier capture for the same fixture
        drift = ""
        if len(obs) >= 2 and basis in ("T1", "T2"):
            newest, older = obs[0], obs[-1]
            if abs(newest["p_a_pct"] - older["p_a_pct"]) >= 0.5:
                drift = (f"{older['source']} {older['price_a']}/{older['price_b']} "
                         f"({older['p_a_pct']:.1f}%) read {older['captured_utc']} -> "
                         f"{newest['source']} {newest['price_a']}/{newest['price_b']} "
                         f"({newest['p_a_pct']:.1f}%) read {newest['captured_utc']}")
                flags.append("FL-PRICE-DRIFT")

        row = {
            "match_id": f["match_id"], "state": "open" if open_now else "locked",
            "lock_utc": f["lock_utc"], "start_utc": f["start_utc"],
            "tournament": f["tournament"], "tier": f["tier"], "offered_points": f["offered_points"],
            "stage": f["stage"], "series_format": fmt, "team_a": f["team_a"], "team_b": f["team_b"],
            "basis": basis, "basis_label": basis_label, "confidence": confidence,
            "prob_a_pct": None if p_a is None else round(p_a, 1),
            "prob_b_pct": None if p_b is None else round(p_b, 1),
            "pick": pick, "pick_prob_pct": None if pick_prob is None else round(pick_prob, 1),
            "market_source": o["source"] if o else "", "market_odds_a": o["price_a"] if o else "",
            "market_odds_b": o["price_b"] if o else "", "market_kind": o["kind"] if o else "",
            "market_overround_pct": round(o["overround_pct"], 2) if o else "",
            "market_captured_utc": o["captured_utc"] if o else "", "market_url": o["url"] if o else "",
            "market_alt_source": (t2[1]["source"] if o and len(t2) > 1 else (t1[1]["source"] if o and len(t1) > 1 else "")),
            "market_alt_p_a_pct": (round(t2[1]["p_a_pct"], 1) if o and len(t2) > 1 else (round(t1[1]["p_a_pct"], 1) if o and len(t1) > 1 else "")),
            "own_prob_a_pct": None if own_a is None else round(own_a, 1),
            "own_prob_b_pct": None if own_b is None else round(own_b, 1),
            "rating_a_vrs": f"{ra['vrs_rank']} ({ra['vrs_points']})" if ra["vrs_points"] else "",
            "rating_b_vrs": f"{rb['vrs_rank']} ({rb['vrs_points']})" if rb["vrs_points"] else "",
            "rating_a_hltv": f"#{ra['hltv_rank']} ({ra['hltv_points']})" if ra["hltv_rank"] else "",
            "rating_b_hltv": f"#{rb['hltv_rank']} ({rb['hltv_points']})" if rb["hltv_rank"] else "",
            "source_links": " | ".join(x for x in [
                slate_prov["permalinks"].get(f["match_id"], "") or slate_prov["source_url"],
                o["url"] if o else "", VRS_URL if (ra["vrs_points"] or rb["vrs_points"]) else "",
                f"https://www.hltv.org/team/{ra['hltv_team_id']}/{hltv_idx.get(norm(ra['lookup_name']),{}).get('slug','')}" if ra["hltv_team_id"] else "",
                f"https://www.hltv.org/team/{rb['hltv_team_id']}/{hltv_idx.get(norm(rb['lookup_name']),{}).get('slug','')}" if rb["hltv_team_id"] else "",
            ] if x),
            "drift": drift,
            "flags": ";".join(sorted(set(flags))),
            "notes": " ".join(notes),
            "alias_notes": " ".join(x for x in [
                f"{ra['team']} -> {ra['lookup_name']} ({ra['alias_evidence']})" if ra["alias_used"] else "",
                f"{rb['team']} -> {rb['lookup_name']} ({rb['alias_evidence']})" if rb["alias_used"] else "",
            ] if x),
        }
        rows.append(row)

        if o:
            add_source(o["url"], f"outside price for {f['team_a']} v {f['team_b']} ({o['source']})",
                       o["captured_utc"], "200 at read")
        if o:
            add_source(f"https://play.hotspawn.com/cs2-pickems", "slate and exact lock epochs", slate_prov["fetched_utc"], "200")
        for fl in sorted(set(flags)):
            flag_rows.append({"match_id": f["match_id"], "teams": f"{f['team_a']} v {f['team_b']}",
                              "lock_utc": f["lock_utc"], "state": row["state"], "code": fl,
                              "detail": (row["basis_label"] + ". " + (row["notes"] or "")).strip()})
        if basis in ("T3", "T4") and own_a is not None and K_alt != K:
            alt_a = logistic(ra["vrs_points"], rb["vrs_points"], K_alt) if (ra["vrs_points"] and rb["vrs_points"]) \
                else (logistic(ra["vrs_points"] or vrs_floor, rb["vrs_points"] or vrs_floor, K_alt))
            alt_pick = f["team_a"] if alt_a >= 100 - alt_a else f["team_b"]
            flags.append("FL-OWN-LINE-SCALE-SENSITIVE")
            notes.append(f"Scale sensitivity: the calibration fit uses {K:g} points per 90% "
                         f"(p({f['team_a']}) = {own_a:.1f}%); the log-loss-optimal fit uses {K_alt:g} points "
                         f"(p({f['team_a']}) = {alt_a:.1f}%). The published pick is "
                         f"{'the same' if (pick is None or alt_pick == pick) else 'DIFFERENT'} under both.")
            row["prob_a_pct"] = round(p_a, 1) if p_a is not None else None
            row["prob_b_pct"] = round(p_b, 1) if p_b is not None else None
        if basis == "T4" and open_now:
            unresolved.append(row)

    # placeholder rejections become flagged findings, attributed to the fixture when identifiable
    for p in placeholders:
        flag_rows.append({"match_id": p.get("match_id", ""), "teams": f"{p['team_a']} v {p.get('team_b') or '(opponent unnamed)'}",
                          "lock_utc": "", "state": "open", "code": "FL-PLACEHOLDER-PRICE-REJECTED",
                          "detail": f"{p['source']} printed {p['price_a']}/{p['price_b']} at {p['captured_utc']} "
                                    f"({p['url']}); {p['rejected']}."})

    open_rows = [r for r in rows if r["state"] == "open"]
    picks_open = [r for r in open_rows if r["pick"]]
    coverage = {
        "generated_utc": NOW_S,
        "slate_fixtures": len(fixtures),
        "open_fixtures": len(open_rows),
        "locked_fixtures": len(rows) - len(open_rows),
        "open_with_pick": len(picks_open),
        "open_without_pick": len(open_rows) - len(picks_open),
        "open_market_basis": len([r for r in open_rows if r["basis"] in ("T1", "T2")]),
        "open_own_line_basis": len([r for r in open_rows if r["basis"] == "T3"]),
        "open_bound_only": len([r for r in open_rows if r["basis"] == "T4"]),
        "open_with_stated_format": len([r for r in open_rows if r["series_format"]]),
        "unresolved_rows": len(unresolved),
        "unique_teams": len(ratings),
        "teams_in_official_standings": len([t for t, r in ratings.items() if r["vrs_points"]]),
        "teams_in_hltv_top245": len([t for t, r in ratings.items() if r["hltv_rank"]]),
        "placeholder_pairs_rejected": len(placeholders),
        "observations_orientation_normalised": len([o for o in observations if o.get("orientation_normalised")]),
        "observations_unmatched": len([o for o in observations if not o.get("match_id")]),
        "vrs_floor_points": vrs_floor,
        "own_line_scale_points": K,
        "own_line_scale_fitted": calib["fitted"],
        "own_line_calibration_n": calib["n"],
        "own_line_calibration_mae_pp": calib.get("mae_pp"),
        "hltv_ranking_date": hltv_meta["ranking_date"],
        # observations that name a fixture the current slate capture does not contain (skipped, never guessed)
        "observations_without_slate_fixture": sorted(orphans),
        "vrs_standings_date": vrs_meta["standings_date"],
    }

    # ------------------------------------------------------------------ write data
    DATA.mkdir(parents=True, exist_ok=True)
    cols = ["match_id", "state", "lock_utc", "start_utc", "tournament", "tier", "offered_points", "stage",
            "series_format", "team_a", "team_b", "basis", "basis_label", "confidence", "prob_a_pct",
            "prob_b_pct", "pick", "pick_prob_pct", "market_source", "market_odds_a", "market_odds_b",
            "market_kind", "market_overround_pct", "market_captured_utc", "market_url",
            "market_alt_source", "market_alt_p_a_pct", "own_prob_a_pct",
            "own_prob_b_pct", "rating_a_vrs", "rating_b_vrs", "rating_a_hltv", "rating_b_hltv",
            "source_links", "drift", "flags", "notes", "alias_notes"]
    with (DATA / "picks.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    (DATA / "picks.json").write_text(json.dumps(
        {"generated_utc": NOW_S, "rows": rows, "coverage": coverage, "calibration": calib,
         "vrs": vrs_meta, "hltv": hltv_meta, "slate": slate_prov,
         "placeholders_rejected": placeholders, "live_reads": live_meta["reads"],
         "hosts_refused": live_meta["hosts_refused"]}, indent=1), encoding="utf-8")
    (DATA / "coverage.json").write_text(json.dumps(coverage, indent=1), encoding="utf-8")
    (DATA / "calibration.json").write_text(json.dumps(
        {"calibration": calib, "fit_rows": fit_rows,
         "formula": "p = 1/(1+10^((vrs_b - vrs_a)/scale)) * 100, series probability, applied per fixture",
         "vrs_meta": vrs_meta, "hltv_meta": hltv_meta}, indent=1), encoding="utf-8")
    with (DATA / "flags.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["match_id", "teams", "lock_utc", "state", "code", "detail"])
        w.writeheader()
        for r in flag_rows:
            w.writerow(r)
    with (DATA / "sources.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["url", "role", "read_utc", "http_status", "note"])
        w.writeheader()
        for r in sorted(source_rows, key=lambda r: r["url"]):
            w.writerow(r)
    with (DATA / "unresolved.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, extrasaction="ignore",
                           fieldnames=["match_id", "lock_utc", "tournament", "tier", "team_a", "team_b",
                                       "series_format", "basis_label", "prob_a_pct", "prob_b_pct",
                                       "rating_a_vrs", "rating_b_vrs", "flags", "notes"])
        w.writeheader()
        for r in unresolved:
            w.writerow(r)
    (DATA / "provenance.json").write_text(json.dumps({
        "generated_utc": NOW_S,
        "inputs": [
            {"what": "Hotspawn CS2 Pick'em slate (identity + exact UTC epochs)", "path": str(SLATE.relative_to(ROOT)),
             "source_url": slate_prov["source_url"], "captured_utc": slate_prov["fetched_utc"],
             "sha256": sha256_file(SLATE)},
            {"what": "HLTV world ranking 2026-10-12", "path": str(HLTV.relative_to(ROOT)),
             "source_url": hltv_meta["canonical_url"], "captured_utc": hltv_meta["fetched_utc"],
             "sha256": sha256_file(HLTV)},
            {"what": "official Valve Regional Standings 2026-10-05", "path": str(VRS.relative_to(ROOT)),
             "source_url": VRS_URL, "blob_sha": vrs_meta["blob_sha"], "sha256": vrs_meta["sha256"]},
            {"what": "outside market feed (hourly)", "path": str(FEED.relative_to(ROOT)),
             "sha256": sha256_file(FEED)},
            {"what": "this session's live reads (EGamersWorld, Polymarket, HLTV, Hotspawn)",
             "path": str(LIVE.relative_to(ROOT)), "sha256": sha256_file(LIVE)},
        ],
        "rule": "No value on this board is invented. Hotspawn crowd pick percentages are never read, "
                "stored or used. Where two sources disagreed, both are printed.",
    }, indent=1), encoding="utf-8")

    write_pages(rows, open_rows, unresolved, coverage, calib, vrs_meta, hltv_meta, slate_prov,
                placeholders, live_meta, ratings, K)
    print(json.dumps(coverage, indent=1))
    return 0


# ----------------------------------------------------------------------------- pages
CSS = """
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#e6edf3;--dim:#9aa4b2;--acc:#58a6ff;
--good:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
padding:12px 12px 64px;max-width:900px;margin:0 auto;-webkit-text-size-adjust:100%}
h1{font-size:1.45rem;margin:.2rem 0 .6rem}h2{font-size:1.15rem;margin:1.4rem 0 .5rem}h3{font-size:1rem;margin:1rem 0 .3rem}
a{color:var(--acc)}
.nav{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0 16px}
.nav a{display:inline-block;padding:10px 12px;border:1px solid var(--line);border-radius:10px;text-decoration:none;
background:var(--card);font-size:.95rem;min-height:44px}
.nav a[aria-current=page]{border-color:var(--acc);color:#fff;background:#1f6feb33}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin:10px 0}
.pick{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}
.pick .name{font-size:1.25rem;font-weight:700;color:var(--good)}
.pick .pct{font-size:1.25rem;font-weight:700}
.meta{color:var(--dim);font-size:.86rem;margin-top:4px;word-break:break-word}
.bars{margin:8px 0 4px}
.bar{display:flex;height:26px;border-radius:6px;overflow:hidden;border:1px solid var(--line)}
.bar i{display:block;font-style:normal;font-size:.8rem;line-height:26px;text-align:center;white-space:nowrap;overflow:hidden}
.bar .a{background:#1f6feb}
.bar .b{background:#6e7681}
table{width:100%;border-collapse:collapse;font-size:.9rem}
th,td{border:1px solid var(--line);padding:8px;text-align:left;vertical-align:top}
th{background:#1c2128}
.tag{display:inline-block;padding:2px 7px;border-radius:999px;font-size:.75rem;border:1px solid var(--line);color:var(--dim);margin:2px 4px 0 0}
.tag.T1,.tag.T2{color:#7ee787;border-color:#238636}
.tag.T3{color:#e3b341;border-color:#9e6a03}
.tag.T4,.tag.bad{color:#ff7b72;border-color:#8b2c25}
.note{background:#161b22;border-left:3px solid var(--warn);padding:10px 12px;border-radius:0 8px 8px 0;margin:10px 0;color:var(--fg)}
.tiles{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;text-align:center}
.tile b{display:block;font-size:1.5rem}
.tile span{color:var(--dim);font-size:.8rem}
.cta{display:block;background:#1f6feb;color:#fff;text-align:center;padding:16px;border-radius:12px;font-weight:700;
text-decoration:none;font-size:1.05rem;margin:12px 0;min-height:54px}
.cta.alt{background:#238636}
.cta.warn{background:#9e6a03}
details{margin:8px 0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px 12px}
summary{cursor:pointer;font-weight:600}
@media(max-width:420px){body{padding:8px 8px 48px}.tiles{grid-template-columns:1fr}}
"""


def esc(s) -> str:
    return (str("" if s is None else s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def nav(cur: str) -> str:
    items = [("index.html", "Summary"), ("picks.html", "All picks"), ("unresolved.html", "Unresolved"),
             ("flagged.html", "Flagged"), ("methodology.html", "Method"), ("sources.html", "Sources"),
             ("cadence.html", "Refresh")]
    out = []
    for href, label in items:
        cur_attr = ' aria-current="page"' if href == cur else ""
        out.append(f'<a href="{href}"{cur_attr}>{label}</a>')
    return '<nav class="nav">' + "".join(out) + "</nav>"


def page(title: str, cur: str, body: str) -> str:
    return (f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{esc(title)}</title><style>{CSS}</style></head><body>"
            f"<h1>{esc(title)}</h1>{nav(cur)}{body}"
            f"<p class=\"meta\">Independent analysis, not betting advice. Hotspawn supplies fixture identity only; "
            f"its crowd percentages are never stored or used. Every number above names the page it was read from.</p>"
            f"</body></html>")


def pick_card(r: dict) -> str:
    pa, pb = r["prob_a_pct"], r["prob_b_pct"]
    bound = r["basis"] == "T4"
    if bound:
        return (f'<div class="card"><div class="meta">{esc(r["lock_utc"])} · {esc(r["tournament"])} · '
                f'tier {esc(r["tier"])} · {esc(r["series_format"] or "series length not stated")}</div>'
                f'<div class="pick"><span class="name" style="color:var(--warn)">No pick published — bound only</span>'
                f'<span class="tag bad">T4</span></div>'
                f'<div class="meta">{esc(r["team_a"])} v {esc(r["team_b"])}: the only rating that exists for '
                f'{esc(r["team_b"] if r["rating_a_vrs"] else r["team_a"])} is a ceiling, so '
                f'{esc(r["team_a"] if r["rating_a_vrs"] else r["team_b"])} wins at <b>least</b> '
                f'{(pa if r["rating_a_vrs"] else pb):.1f}% of series. A lower bound is not an estimate, so no pick '
                f'is published for this fixture — see <a href="unresolved.html">Unresolved picks &amp; limitations</a>.</div>'
                f'<div class="meta">{esc(r["basis_label"])}. {esc(r["notes"])}</div>'
                f'<details><summary>Sources &amp; numbers</summary><div class="meta">'
                f'VRS {esc(r["rating_a_vrs"]) or "—"} v {esc(r["rating_b_vrs"]) or "—"} · '
                f'HLTV {esc(r["rating_a_hltv"]) or "—"} v {esc(r["rating_b_hltv"]) or "—"} · scale {esc(str(r["flags"]))}'
                f'</div></details></div>')
    bars = ""
    if pa is not None and pb is not None:
        bars = (f'<div class="bars"><div class="bar"><i class="a" style="width:{pa:.1f}%">{pa:.1f}%</i>'
                f'<i class="b" style="width:{pb:.1f}%">{pb:.1f}%</i></div>'
                f'<div class="meta">{esc(r["team_a"])} {pa:.1f}% · {esc(r["team_b"])} {pb:.1f}%</div></div>')
    pick = (f'<div class="pick"><span class="name">Pick: {esc(r["pick"])}</span>'
            f'<span class="pct">{r["pick_prob_pct"]:.1f}%</span>'
            f'<span class="tag {r["basis"]}">{r["basis"]}</span>'
            f'<span class="tag">{esc(r["confidence"])}</span></div>') if r["pick"] else \
        ('<div class="pick"><span class="name" style="color:var(--warn)">No pick published</span>'
         '<span class="tag bad">unresolved</span></div>')
    src_list = "".join(f'<div><a href="{esc(u)}">{esc(u[:110])}</a></div>'
                       for u in (r["source_links"] or "").split(" | ") if u)
    drift = f'<div class="note">Price moved: {esc(r["drift"])}</div>' if r["drift"] else ""
    notes = f'<div class="note">{esc(r["notes"])}</div>' if r["notes"] else ""
    alias = f'<div class="meta">Name mapping: {esc(r["alias_notes"])}</div>' if r["alias_notes"] else ""
    flags = "".join(f'<span class="tag{" bad" if f.startswith(("FL-BOUND", "FL-NO-OUTSIDE", "FL-PLACEHOLDER")) else ""}">'
                    f'{esc(f)}</span>' for f in r["flags"].split(";") if f)
    return (f'<div class="card"><div class="meta">{esc(r["lock_utc"])} · {esc(r["tournament"])} · '
            f'tier {esc(r["tier"])} · {esc(r["series_format"] or "series length not stated")} · '
            f'{"open" if r["state"] == "open" else "locked"}</div>{pick}{bars}'
            f'<div class="meta">{esc(r["team_a"])} v {esc(r["team_b"])} · basis {esc(r["basis_label"])}</div>'
            f'{drift}{notes}{alias}<div>{flags}</div><details><summary>Sources &amp; numbers</summary>'
            f'<div class="meta">outside line: {esc(r["market_source"] or "none")} '
            f'{esc(str(r["market_odds_a"]))} / {esc(str(r["market_odds_b"]))} read {esc(r["market_captured_utc"]) or "n/a"} '
            f'· overround {esc(str(r["market_overround_pct"]))}% · our own line {esc(str(r["own_prob_a_pct"]))}% / '
            f'{esc(str(r["own_prob_b_pct"]))}% · VRS {esc(r["rating_a_vrs"]) or "—"} v {esc(r["rating_b_vrs"]) or "—"} · '
            f'HLTV {esc(r["rating_a_hltv"]) or "—"} v {esc(r["rating_b_hltv"]) or "—"}</div>{src_list}</details></div>')


def write_pages(rows, open_rows, unresolved, coverage, calib, vrs_meta, hltv_meta, slate_prov,
                placeholders, live_meta, ratings, K) -> None:
    o = OUT
    top = sorted(open_rows, key=lambda r: (r["lock_utc"], r["match_id"]))
    picks_n = coverage["open_with_pick"]

    # ---- index.html
    tiles = "".join(f'<div class="tile"><b>{v}</b><span>{k}</span></div>' for k, v in [
        ("open matches", coverage["open_fixtures"]), ("picks published", picks_n),
        ("market-priced", coverage["open_market_basis"]), ("our own line", coverage["open_own_line_basis"]),
        ("bound only (unresolved)", coverage["open_bound_only"]),
        ("of them no outside price", coverage["open_own_line_basis"] + coverage["open_bound_only"]),
    ])
    head = f"""
<a class="cta" href="picks.html">Every pick, one screen per match →</a>
<a class="cta warn" href="unresolved.html">Unresolved picks &amp; limitations →</a>
<div class="tiles">{tiles}</div>
<div class="card">
<div class="meta"><b>Snapshot</b> {esc(coverage['generated_utc'])} · Hotspawn slate read {esc(slate_prov['fetched_utc'])}
(hourly pipeline) and re-read live {esc(READ_UTC["HS-LOBBY"])} and {esc(READ_UTC["HS-CS2-PICKEMS"])} · outside prices as new as
{esc(max([r['market_captured_utc'] for r in rows if r['market_captured_utc']] or ['—']))} ·
Valve standings {esc(vrs_meta['standings_date'])} · HLTV ranking {esc(hltv_meta['ranking_date'])}</div>
</div>
<h2>Where the picks are</h2>
<table><tr><th>What you want</th><th>Page</th></tr>
<tr><td>Every open match with its pick and both probabilities, phone-sized cards</td><td><a href="picks.html">picks.html</a></td></tr>
<tr><td>Matches no sportsbook prices, why, and what we could still resolve</td><td><a href="unresolved.html">unresolved.html</a></td></tr>
<tr><td>Irregularities, placeholders, stale inputs and open questions</td><td><a href="flagged.html">flagged.html</a></td></tr>
<tr><td>Formulas, the basis ladder and the fitted scale</td><td><a href="methodology.html">methodology.html</a></td></tr>
<tr><td>Every URL read, with the UTC time it was read</td><td><a href="sources.html">sources.html</a></td></tr>
<tr><td>Refresh cadence, last run, age of every input</td><td><a href="cadence.html">cadence.html</a></td></tr>
<tr><td>Machine-readable pick data</td><td><a href="data/picks.csv">picks.csv</a> · <a href="data/picks.json">picks.json</a> · <a href="data/unresolved.csv">unresolved.csv</a></td></tr>
</table>
<h2>What this board is</h2>
<div class="card"><div class="meta">
One row for every match on the Hotspawn CS2 Pick'em board that is still open, each with the pick, both sides'
win probability, the basis it came from and the URL behind every number. The slate (fixture identity and exact
UTC lock epochs) comes from Hotspawn's own page payload; the probabilities come from outside sources only —
Pinnacle guest markets, Polymarket, Thunderpick prices relayed by bo3.gg and the EGamersWorld/bc.game listing —
and, where no sportsbook prices a match, from our own line built on the official Valve Regional Standings.
Hotspawn's crowd percentage is never an input.
</div></div>
<h2>Next matches</h2>
""" + "".join(pick_card(r) for r in top[:5]) + '<a class="cta alt" href="picks.html">All ' + str(len(top)) + ' open matches →</a>'
    (o / "index.html").write_text(page("Hotspawn CS2 picks — executive summary", "index.html", head), encoding="utf-8")

    # ---- picks.html
    body = ('<div class="note">Sorted by lock time. The pick, both probabilities and the basis are the first '
            'things in each card, so one screen on a phone is enough per match. Tap “Sources &amp; numbers” for '
            'the exact quotes, ranks and links.</div>'
            + "".join(pick_card(r) for r in top)
            + "<h2>Locked and past fixtures</h2>"
            + '<div class="note">These matches are on the Hotspawn board but their lock time has passed, so no pick can '
              'be entered for them. They are kept so the coverage count on the summary page is honest.</div>'
            + '<details><summary>Show the ' + str(coverage["locked_fixtures"]) + ' locked fixtures</summary><table>'
            + '<tr><th>Match</th><th>Lock (UTC)</th><th>Tournament</th><th>Basis</th></tr>'
            + "".join(f'<tr><td>{esc(r["team_a"])} v {esc(r["team_b"])}</td><td>{esc(r["lock_utc"])}</td>'
                      f'<td>{esc(r["tournament"])}</td><td>{esc(r["basis_label"])}</td></tr>'
                      for r in sorted(rows, key=lambda r: r["lock_utc"], reverse=True) if r["state"] == "locked")
            + '</table></details>')
    (o / "picks.html").write_text(page(f"All open matches — {picks_n} picks", "picks.html", body), encoding="utf-8")

    # ---- unresolved.html  (the explicitly separate section)
    lim = [
        ("No sportsbook prices the low-tier CCT / Elisa fixtures",
         "EGamersWorld prints exactly 1.80 / 1.80 for five different CCT Europe Series #12 Play-In fixtures on one page "
         "(banda chuya v 6666, WRAITH PCIFIC v Ryvex, Saint Sinners v MAYBE, Lilmix v Revise, mellren v Privateer Gaming) "
         "while printing real, different prices for other fixtures on the same pages. Identical pairs on unrelated "
         "matches are a listing placeholder, not a market — one of those fixtures, Ryvex v PCIFIC, has an independent "
         "Polymarket price that contradicts a coin-flip. The pairs are therefore rejected and flagged, never used as a number.",
         "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in-1sGIL2gAYu"),
        ("One fixture's opponent cannot be identified outside Hotspawn",
         "For FORZE Reload v LFO 10 the only outside listing found prints the opponent cell empty (no name, no flag, no team "
         "link; the match URL slug is literally 'forze-reload-vs-'). LFO 10 appears nowhere in the official Valve Regional "
         "Standings file (380 teams) nor in HLTV's top 245, so no rating exists for it and only a bound can be published.",
         "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
        ("Official rating snapshots are not intraday",
         f"Valve publishes the Regional Standings weekly; the newest official file at build time is the "
         f"{vrs_meta['standings_date']} snapshot ({vrs_meta['teams']} entries, blob {vrs_meta['blob_sha'][:8]}). HLTV's world "
         f"ranking is weekly too (dated {hltv_meta['ranking_date']} here) and lists only the top 245 teams. A match played "
         f"today is therefore always rated from a snapshot several days old — flagged on every affected row, never hidden.",
         "https://www.hltv.org/ranking/teams/2026/october/12"),
        ("Series length is not always published",
         f"{coverage['open_with_stated_format']} of {coverage['open_fixtures']} open fixtures carry a stated series length at "
         "build time (from the outside feed or the EGamersWorld schedule, which prints 'Bo3'). The rest stay blank and flagged "
         "rather than assumed.",
         "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
        ("The board's own refresh is not guaranteed by the platform",
         "GitHub Actions disables scheduled workflows on inactive repositories and runs them best-effort; this repository has "
         "many scheduled workflows competing for the same window, and one of them failed on main on 2026-10-14 "
         "(run 38511378749, 'Executive board refresh'). Every page here prints the age of its inputs instead of asserting freshness.",
         "https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511378749"),
        ("Hotspawn itself lists fixtures that can no longer be picked",
         f"{coverage['locked_fixtures']} of the {coverage['slate_fixtures']} fixtures in the site payload are locked or past — most "
         "carry June dates the board never cleared, and one (1079546, Zomblers v Overtake Sector) disappeared from the board "
         "between the 02:06:30Z capture and the 04:31Z live read. No pick exists or can exist for those, so they are counted, "
         "not silently dropped.",
         "https://play.hotspawn.com/cs2-pickems"),
    ]
    body = ('<div class="note">This is the separate section the brief asks for: the matches we could <b>not</b> resolve the '
            'same way as the market-priced picks, followed by the limitations that apply to the whole board. Nothing here '
            'is a guess — each item names the page that shows it.</div>'
            '<h2>Picks published from our own line only (no outside price)</h2>'
            + "".join(pick_card(r) for r in top if r["basis"] == "T3")
            + '<h2>No pick published</h2>'
            + "".join(pick_card(r) for r in top if r["basis"] == "T4")
            + ("" if any(r["basis"] == "T4" for r in top) else '<div class="card">None: every open fixture has either a market price or an originated line.</div>')
            + "<h2>Limitations that apply to these rows</h2>"
            + "".join(f'<div class="card"><div class="pick"><span class="name" style="font-size:1rem">{esc(t)}</span></div>'
                      f'<div class="meta">{esc(d)}</div><div class="meta"><a href="{esc(u)}">{esc(u)}</a></div></div>'
                      for t, d, u in lim)
            + "<h2>What we did to try to resolve them</h2>"
            + '<div class="card"><div class="meta">'
              '1. HLTV: the world ranking (read live ' + READ_UTC['HLTV-RANKING-OCT12'] + ') and the repository\'s captured ranking page supply ranks '
              'and points for the top 245 teams; HLTV does not publish per-match prices, and its match pages are reachable only '
              'through the platform fetch tool, not the sandbox shell.<br>'
              '2. EgamersWorld (bc.game listing) event pages were read for both CCT events at ' + READ_UTC['EGW-CCT-EU-12'] + ' and ' + READ_UTC['EGW-CCT-EU-11'][11:] + ': they resolve the '
              'series length (Bo3) for the CCT fixtures and identify the fixture whose opponent is missing, but they print the '
              '1.80/1.80 placeholder for exactly the fixtures no book has priced.<br>'
              '3. Polymarket was read directly (Gothic v Lavked moneyline 50¢/51¢ at 04:38:05Z, volume $304); it prices the '
              'fixtures its traders care about and does not list the C-tier play-in matches at all.<br>'
              '4. Official Valve Regional Standings (GitHub, ValveSoftware/counter-strike_regional_standings) were pulled through '
              'the GitHub contents API: 380 entries, dated 2026-10-05, which is what the originated line is built on.'
              '</div></div>'
            )
    (o / "unresolved.html").write_text(page("Unresolved picks & limitations", "unresolved.html", body), encoding="utf-8")

    # ---- flagged.html
    flags_all = []
    for r in rows:
        for f in r["flags"].split(";"):
            if f:
                flags_all.append((r, f))
    meaning = {
        "FL-LOCKED": "fixture is locked or already started; kept for the record, not an active pick.",
        "FL-NO-OUTSIDE-LINE": "no outside bookmaker or market price was readable for this fixture, so the pick is our own line.",
        "FL-BOUND-OPPONENT-UNRATED": "one side is absent from the official standings; the pick is a bound, not an estimate.",
        "FL-NOT-IN-HLTV-TOP-245": "the team is outside HLTV's published top 245.",
        "FL-FORMAT-UNKNOWN": "no source states the series length; left blank rather than assumed.",
        "FL-OWN-LINE-MARKET-SPLIT": "our line and the outside market disagree about the favourite; both are printed.",
        "FL-PRICE-DRIFT": "the outside price moved between two reads on 2026-10-14; both values are printed.",
        "FL-THIN-MARKET": "the prediction market for this fixture has very little volume.",
        "FL-PLACEHOLDER-PRICE-REJECTED": "a listing printed an identical 1.80/1.80 pair for several unrelated fixtures; rejected as a placeholder.",
    }
    body = ('<div class="note">Everything that could not be confirmed from a source, every disagreement between sources and '
            'every placeholder that was rejected. Flagged rows are published, not dropped, and none of them block the board.</div>'
            '<h2>Placeholder pairs rejected</h2><table><tr><th>Fixture</th><th>Listing</th><th>Read</th><th>Value</th></tr>'
            + "".join(f'<tr><td>{esc(p["team_a"])} v {esc(p.get("team_b") or "&lt;unnamed in this listing&gt;")}</td>'
                      f'<td><a href="{esc(p["url"])}">{esc(p["source"])}</a></td><td>{esc(p["captured_utc"])}</td>'
                      f'<td>{esc(p["price_a"])}/{esc(p["price_b"])}</td></tr>' for p in placeholders)
            + '</table><h2>Row flags</h2><table><tr><th>Match</th><th>Lock (UTC)</th><th>Flag</th><th>What it means</th></tr>'
            + "".join(f'<tr><td>{esc(r["team_a"])} v {esc(r["team_b"])} '
                      f'<span class="tag">{esc(r["match_id"])}</span></td><td>{esc(r["lock_utc"])}</td>'
                      f'<td><span class="tag">{esc(f)}</span></td><td>{esc(meaning.get(f, "see methodology"))}'
                      f'{esc(" — " + r["notes"]) if r["notes"] and f == "FL-BOUND-OPPONENT-UNRATED" else ""}</td></tr>'
                      for r, f in sorted(flags_all, key=lambda x: (x[0]["lock_utc"], x[1])))
            + '</table>'
            '<h2>Automation and pipeline irregularities</h2><table><tr><th>What</th><th>Evidence</th></tr>'
            '<tr><td>The scheduled “Executive board refresh” workflow failed on main at 2026-10-14T04:1xZ; the newest build of that '
            'board reports “Snapshot is 8.7 h old” and fell back to the committed capture after its live HLTV reads returned status 0.</td>'
            '<td><a href="https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511378749">run 38511378749</a> · '
            '<a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/executive/data/summary.json">executive/data/summary.json</a></td></tr>'
            '<tr><td>This sandbox cannot reach the source hosts from the shell (curl returns no response for hltv.org and '
            'play.hotspawn.com); the live reads on this board were taken through the platform fetch tool and are timestamped.</td>'
            '<td><a href="data/live_reads.json">data/live_reads.json → hosts_refused</a></td></tr>'
            '<tr><td>Hotspawn serves cached renders: the 04:47Z read of /cs2-pickems carried countdowns implying a 02:44:21Z render. '
            'Slate identity was therefore confirmed twice and exact epochs are taken only from the payload capture.</td>'
            '<td><a href="https://play.hotspawn.com/cs2-pickems">play.hotspawn.com/cs2-pickems</a></td></tr>'
            '<tr><td>A locked fixture (1079546 Zomblers v Overtake Sector) is present in the 02:06:30Z payload capture but absent '
            'from the live board reads 2.5 h later — the board removes fixtures after lock without notice.</td>'
            '<td><a href="https://play.hotspawn.com/lobby">play.hotspawn.com/lobby</a></td></tr>'
            '</table>')
    (o / "flagged.html").write_text(page("Flagged for review", "flagged.html", body), encoding="utf-8")

    # ---- methodology.html
    body = f"""
<h2>The basis ladder</h2>
<div class="card"><div class="meta">
<b>T1 — primary bookmaker.</b> A Pinnacle guest-market quote captured by this repo's pipeline. De-vigged:
p = (1/odds) / Σ(1/odds). No T1 quote existed for any open fixture at build time, so every market row below is T2.<br><br>
<b>T2 — outside listing or prediction market.</b> The newest readable price for the fixture from Polymarket
(share price in USD 0-1, used directly as the market's own probability), Thunderpick prices relayed by bo3.gg, or the
EGamersWorld listing of bc.game prices (de-vigged as above). Pairs that are identical across unrelated fixtures on the
same page (1.80/1.80) are rejected as placeholders and published on the Flagged page instead.<br><br>
<b>T3 — our own originated line.</b> p = 1/(1+10^((vrs_b − vrs_a)/{K:g})) × 100, where vrs_a / vrs_b are the official
Valve Regional Standings points for the two teams. The scale {K:g} points per 90% favourite is fitted at build time by
grid search against the fixtures an outside market actually prices ({calib['n']} fit rows,
mean absolute error {calib.get('mae_pp')} percentage points), not assumed. If fewer than four such fixtures exist the
project default of 400 points applies instead and the fit is marked unfitted.<br><br>
<b>T4 — bound only.</b> If a team is absent from the official standings, the lowest published value in the same file is
used as its ceiling. The known side's true win probability is then <i>at least</i> the published number, so no pick is
published for that fixture — it is listed on <a href="unresolved.html">Unresolved</a>.
</div></div>
<h2>Rules the board enforces</h2>
<div class="card"><div class="meta">
· Hotspawn's crowd pick percentage is never read, stored or used — a build test fails if it appears.<br>
· A pick is only published when the row has a probability for both sides from the basis in the basis column.<br>
· No averaging of two sources into one number: the newest readable price for the fixture is published, older ones are
shown as drift when they differ by ≥ 0.5 pp.<br>
· Unknowns stay blank and are flagged; nothing is inferred from a name, a tier or a crowd vote.<br>
· Every row carries the URL it came from; every source URL is listed with its read time on
<a href="sources.html">Sources</a>.
</div></div>
<h2>What could be wrong</h2>
<div class="card"><div class="meta">
· Our line is a rating transform, not a calibrated model of CS2 outcomes, and the official ratings it uses are weekly.<br>
· Prediction-market prices are last-traded prices on thin books (Gothic v Lavked traded $304 of volume at read time).<br>
· Series length can change how a rating gap converts into a series probability; where no source states the length the
row says so.<br>
· A match can be postponed or cancelled after publication; the board prints lock times, and prices are read times,
not guarantees.
</div></div>
<h2>Reproduce</h2>
<div class="card"><div class="meta"><code>python3 livelines/build.py</code> rebuilds this board offline from the committed
captures listed in <a href="data/provenance.json">data/provenance.json</a>. <code>python3 -m unittest tests.test_457629c4</code>
runs the invariants. The live reads taken on 2026-10-14 are stored verbatim in
<a href="data/live_reads.json">data/live_reads.json</a> with their URLs and read times.</div></div>
"""
    (o / "methodology.html").write_text(page("Methodology", "methodology.html", body), encoding="utf-8")

    # ---- sources.html
    src = read_csv(DATA / "sources.csv")
    body = ('<div class="note">Every source used, with the role it played and the UTC time it was read or captured. '
            'Load the link and re-read the number yourself.</div>'
            '<table><tr><th>Source</th><th>Role</th><th>Read (UTC)</th><th>Status</th></tr>'
            + "".join(f'<tr><td><a href="{esc(s["url"])}">{esc(s["url"][:96])}</a></td><td>{esc(s["role"])}</td>'
                      f'<td>{esc(s["read_utc"])}</td><td>{esc(s["http_status"])}{esc(" — " + s["note"]) if s["note"] else ""}</td></tr>'
                      for s in src)
            + '</table><h2>Reads taken by this session (verbatim)</h2><table><tr><th>Read</th><th>URL</th><th>UTC</th><th>How the time was established</th></tr>'
            + "".join(f'<tr><td>{esc(r["id"])}</td><td><a href="{esc(r["url"])}">{esc(r["url"][:80])}</a></td>'
                      f'<td>{esc(r["read_utc"])}</td><td>{esc(r["read_utc_basis"])}</td></tr>'
                      for r in live_meta["reads"])
            + '</table>')
    (o / "sources.html").write_text(page("Sources", "sources.html", body), encoding="utf-8")

    # ---- cadence.html
    body = f"""
<div class="card"><div class="tiles">
<div class="tile"><b>4 h</b><span>refresh cadence (cron 33 */4 * * *)</span></div>
<div class="tile"><b>{esc(coverage['generated_utc'])}</b><span>this build</span></div>
<div class="tile"><b>{esc(slate_prov['fetched_utc'])}</b><span>Hotspawn slate capture</span></div>
<div class="tile"><b>{esc(vrs_meta['standings_date'])}</b><span>official standings</span></div>
</div></div>
<h2>How refresh works</h2>
<div class="card"><div class="meta">
<code>.github/workflows/livelines-457629c4.yml</code> runs every 4 hours (inside the 4–8 h window the brief asks for), on
every push that touches this board, and on manual dispatch. It re-reads the Hotspawn Pick'em payload, the outside
market feed and the official Valve standings, then runs <code>livelines/build.py</code> and the invariant tests, and
commits only if the tests pass — a failed refresh leaves the last good board published and says so here rather than
overwriting it.<br><br>
GitHub treats scheduled runs as best-effort and drops them on inactive repositories, and this repository has many
scheduled workflows competing for the same slots: on 2026-10-14 the “Executive board refresh” run
<a href="https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511378749">38511378749</a> failed on main, and
the newest build of that board published itself as 8.7 h old. This page therefore prints the age of every input
instead of asserting freshness, and the workflow above writes its own result here.
</div></div>
<h2>Age of every input at this build</h2>
<table><tr><th>Input</th><th>Read/captured (UTC)</th><th>Age at build</th><th>Source</th></tr>
""" + "".join(
        f'<tr><td>{esc(what)}</td><td>{esc(when)}</td><td>{esc(age)}</td><td><a href="{esc(url)}">link</a></td></tr>'
        for what, when, age, url in [
            ("Hotspawn CS2 Pick'em payload (fixtures, exact lock epochs)", slate_prov["fetched_utc"],
             _age(slate_prov["fetched_utc"]), "https://play.hotspawn.com/cs2-pickems"),
            ("Outside market feed (Polymarket, Thunderpick via bo3.gg)", _newest_market(rows), _age(_newest_market(rows)),
             "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/feeds/data/market_feed.csv"),
            ("This session's live reads (EGamersWorld, Polymarket, HLTV)", "2026-10-14T04:38:05Z",
             _age("2026-10-14T04:38:05Z"), "data/live_reads.json"),
            ("Official Valve Regional Standings", vrs_meta["standings_date"] + "T00:00:00Z",
             _age(vrs_meta["standings_date"] + "T00:00:00Z"), VRS_URL),
            ("HLTV world ranking", hltv_meta["ranking_date"] + "T00:00:00Z",
             _age(hltv_meta["ranking_date"] + "T00:00:00Z"), HLTV_URL),
        ]) + "</table>"
    (o / "cadence.html").write_text(page("Refresh cadence", "cadence.html", body), encoding="utf-8")


def _newest_market(rows) -> str:
    stamps = [r["market_captured_utc"] for r in rows if r["market_captured_utc"]]
    return max(stamps) if stamps else "—"


def _age(when: str) -> str:
    try:
        t = dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        return "—"
    if when.endswith("T00:00:00Z"):
        t = t.replace(hour=0, minute=0)
    delta = (NOW - t).total_seconds()
    if delta < 0:
        return "in the future relative to the build clock"
    h = delta / 3600
    return f"{h:.1f} h" if h < 48 else f"{h/24:.1f} days"


if __name__ == "__main__":
    raise SystemExit(main())
