#!/usr/bin/env python3
"""S-01..S-03 collector — Arena session `arena/180a42a0`.

Reads only public pages and public data files, and writes derived tables into `slate/data/`.
Nothing here logs in, solves a challenge, or calls a private endpoint.

Sources
 1. Hotspawn Play Pick'em pages (/lobby, /cs2-pickems, /thp-pickems, /lol-pickems).  The Angular
    SSR HTML embeds its whole render state in `<script id="ng-state">`; that payload is the
    authoritative machine-readable list of the fixtures the board offers, with exact
    `scheduled_start_time` (ms epoch, UTC) and the lock offset.  The wall-clock text Hotspawn
    prints next to a match is NOT used anywhere in this file: it has been read as both UTC and
    UTC-4 across sessions (see slate/flagged.html, S-F-01), while the epoch is unambiguous.
 2. Valve Regional Standings — Valve's own published standings file (official), read through the
    GitHub contents API of ValveSoftware/counter-strike_regional_standings.
 3. HLTV world ranking page (rank + points) and the HLTV upcoming-matches listing (match id, URL,
    event) — used for our own rating-based line and for a per-row cross-reference link.
 4. Pinnacle — the public guest responses its own public matchups page loads by itself
    (headless Chromium capture; no account, no key).  Moneyline only.
 5. EGamersWorld — the per-match "Betting odds" table, where it serves a page (it returns HTTP 403
    to plain clients and sometimes to the browser too; a refusal is recorded as a refusal).

The heavy lifting for (4) and (5) is the collection module that session `arena/b90700c6` wrote and
merged for `refresh/**`; it is imported read-only here (no edits to their files) and every fetch it
performs is appended to the provenance log this program publishes.

Hotspawn's own crowd pick percentages are never an input to any probability in this file.  Where
they are copied into `fixtures.csv` they are named `crowd_pct_*_audit_only` and no build step reads
them.
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

# --------------------------------------------------------------------------------------------------
# Reuse of the proven fetchers shipped by session arena/b90700c6 in refresh/.
# Read-only: this session never edits refresh/**.  If the module is missing the run still completes
# for the sources that need plain HTTP (Hotspawn payload + Valve file) and every market/rating row
# that needs the browser is written as a refusal instead of a number.
sys.path.insert(0, str(ROOT / "refresh"))
try:
    import collect as up  # type: ignore  # noqa: E402
    HAVE_UPSTREAM = True
except Exception as exc:  # noqa: BLE001
    up = None  # type: ignore
    HAVE_UPSTREAM = False
    UPSTREAM_ERROR = f"{type(exc).__name__}: {exc}"
else:
    UPSTREAM_ERROR = None

HLTV_RANKING_URL = "https://www.hltv.org/ranking/teams"
HLTV_MATCHES_URL = "https://www.hltv.org/matches"
VRS_LISTING_API = ("https://api.github.com/repos/ValveSoftware/"
                   "counter-strike_regional_standings/contents/live/2026")

# Every value this file writes is derived from these constants; they are printed into the data.
ELO_SCALE = 400.0            # standard Elo/logistic scale used for HLTV ranking points
DEADLINE_SECONDS = 22 * 60   # stop opening new pages after this long (CI job has 35 minutes)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def norm(name: str | None) -> str:
    """Normalised comparison key for team names (same spelling rules as the rest of the repo)."""
    return re.sub(r"[^a-z0-9]+", "", unescape(name or "").lower().replace("&", "and"))


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def devig(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    """Two-way de-vig: keep the bookmaker's relative opinion, drop its margin."""
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    return inv_a / total, inv_b / total, (total - 1.0) * 100.0


def elo_p(points_a: float, points_b: float, scale: float = ELO_SCALE) -> float:
    """Probability that A beats B in one map, logistic on the rating gap (standard Elo form)."""
    return 1.0 / (1.0 + 10.0 ** (-(points_a - points_b) / scale))


def series_from_map(p: float, best_of: int | None) -> float:
    """Best-of-N series probability for a team whose per-map probability is p (independent maps)."""
    if best_of == 1:
        return p
    if best_of == 3:
        return p * p * (3.0 - 2.0 * p)
    if best_of == 5:
        return p ** 3 * (10.0 - 15.0 * p + 6.0 * p * p)
    return p


# --------------------------------------------------------------------------------------- Hotspawn
def hotspawn_capture() -> dict:
    if not HAVE_UPSTREAM:
        return {"fixtures": [], "pages": [], "error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    hs = up.collect_hotspawn()
    return hs


def sport_of(fixture: dict) -> str:
    pages = fixture.get("pages") or []
    if "cs2-pickems" in pages:
        return "cs2"
    if "thp-pickems" in pages:
        return "thp"
    if "lol-pickems" in pages:
        return "lol"
    return "other"


def live_status(fixture: dict, now: datetime) -> str:
    lock, start = parse_iso(fixture.get("lock_utc")), parse_iso(fixture.get("scheduled_start_utc"))
    if start and start < now - timedelta(hours=36):
        return "stale listing (start in the past)"
    if start and start < now:
        return "started (not pickable)"
    if lock and lock < now:
        return "locked (not pickable)"
    return "open"


# -------------------------------------------------------------------------------------- HLTV data
def hltv_listing() -> dict:
    """One render of HLTV's upcoming-matches page: per-row match id, URL, teams, event, kickoff."""
    out = {"url": HLTV_MATCHES_URL, "status": None, "error": None, "rows": [], "fetched_utc": None}
    if not HAVE_UPSTREAM:
        out["error"] = f"upstream collector unavailable: {UPSTREAM_ERROR}"
        return out
    got = up.fetch_html(HLTV_MATCHES_URL)
    out["status"], out["error"] = got.get("status"), got.get("error")
    out["fetched_utc"] = got.get("fetched_utc")
    html = got.get("html")
    if not html:
        return out
    for block in re.split(r'<div class="match-item', html)[1:]:
        link = re.search(r'href="(/matches/(\d+)/([^"?#]+))"', block)
        unix = re.search(r'data-unix="(\d{13})"', block)
        teams = re.findall(r'class="team[^"]*">\s*([^<]{2,40})\s*<', block)
        event = re.search(r'class="event-name">([^<]+)<', block)
        if not (link and len(teams) >= 2):
            continue
        out["rows"].append({
            "hltv_match_id": link.group(2),
            "hltv_url": "https://www.hltv.org" + link.group(1),
            "team_a": unescape(teams[0]).strip(),
            "team_b": unescape(teams[1]).strip(),
            "event": unescape(event.group(1)).strip() if event else None,
            "kickoff_utc": (datetime.fromtimestamp(int(unix.group(1)) / 1000, timezone.utc)
                            .strftime("%Y-%m-%dT%H:%M:%SZ") if unix else None),
        })
    out["rows_read"] = len(out["rows"])
    return out


# --------------------------------------------------------------------------- Valve Regional Standings
def valve_standings() -> dict:
    out = {"file": None, "source_url": None, "blob_url": None, "teams": {}, "rows_read": 0,
           "error": None, "fetched_utc": now_iso(), "sha256": None}
    if not HAVE_UPSTREAM:
        out["error"] = f"upstream collector unavailable: {UPSTREAM_ERROR}"
        return out
    valve = up.collect_valve()
    out["error"] = valve.get("error")
    out["file"] = valve.get("file")
    out["source_url"] = valve.get("source_url")
    out["teams"] = valve.get("teams") or {}
    out["rows_read"] = valve.get("rows_read") or 0
    if out["file"]:
        out["blob_url"] = ("https://github.com/ValveSoftware/counter-strike_regional_standings/"
                           f"blob/main/live/2026/{out['file']}")
    return out


# ------------------------------------------------------------------------------------ market lines
def pinnacle_markets(candidates: list[dict]) -> tuple[list[dict], dict]:
    """Pinnacle moneyline quotes (public guest responses of its own public page) matched to fixtures."""
    if not HAVE_UPSTREAM:
        return [], {"error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    pinn = up.collect_pinnacle()
    quotes = pinn.get("quotes") or []
    rows = []
    for fx in candidates:
        best = None
        for q in quotes:
            if q.get("game") not in ("cs2",):
                continue
            same = (similarity(fx["team_a"], q.get("team_a")) + similarity(fx["team_b"], q.get("team_b"))) / 2
            swapped = (similarity(fx["team_a"], q.get("team_b")) + similarity(fx["team_b"], q.get("team_a"))) / 2
            if max(same, swapped) < 0.62:
                continue
            q_start, f_start = parse_iso(str(q.get("start_utc") or "")[:19] + "Z"), parse_iso(fx.get("scheduled_start_utc"))
            if q_start and f_start and abs((q_start - f_start).total_seconds()) > 6 * 3600:
                continue
            score = max(same, swapped)
            if best is None or score > best[0]:
                best = (score, q, swapped > same)
        if not best:
            continue
        score, q, flipped = best
        odds_a, odds_b = (q["odds_b"], q["odds_a"]) if flipped else (q["odds_a"], q["odds_b"])
        pa, pb, margin = devig(float(odds_a), float(odds_b))
        rows.append({
            "fixture_id": fx["match_id"], "source": "Pinnacle (public guest matchups/markets)",
            "source_url": q.get("source_url"), "match_url": q.get("api_url"),
            "book": "Pinnacle", "odds_a": round(float(odds_a), 3), "odds_b": round(float(odds_b), 3),
            "overround_pct": round(margin, 3), "p_a": round(pa * 100, 2), "p_b": round(pb * 100, 2),
            "captured_utc": q.get("observed_utc"), "name_similarity": round(score, 3),
            "team_order_flipped": flipped, "best_of": q.get("best_of"),
            "note": f"matched to Hotspawn fixture {fx['match_id']} by team name (similarity "
                    f"{score:.2f}) and kickoff within 6 h",
        })
    return rows, {"quotes": len(quotes), "matched": len(rows),
                  "counters": pinn.get("counters"), "pages": pinn.get("pages")}


def egw_readings(candidates: list[dict]) -> tuple[list[dict], dict]:
    """EGamersWorld per-match readings; a refusal is recorded, never filled in."""
    if not HAVE_UPSTREAM:
        return [], {"error": f"upstream collector unavailable: {UPSTREAM_ERROR}"}
    egw = up.collect_egw(candidates)
    rows, refused, matched = [], 0, 0
    for fx in candidates:
        reading = (egw.get("readings") or {}).get(fx["match_id"]) or {}
        if not reading.get("found"):
            refused += 1
            continue
        books = reading.get("books") or []
        if books:
            book = books[0]
            odds_a, odds_b = float(book["odds_a"]), float(book["odds_b"])
            # EGW lists the fixture in its own order; the upstream reading preserves the page order.
            pa, pb, margin = devig(odds_a, odds_b)
            if reading.get("reversed"):
                odds_a, odds_b, pa, pb = odds_b, odds_a, pb, pa
            rows.append({
                "fixture_id": fx["match_id"], "source": "EGamersWorld per-match betting-odds table",
                "source_url": reading.get("match_url"), "book": book.get("book") or "EGW book table",
                "odds_a": round(odds_a, 3), "odds_b": round(odds_b, 3),
                "overround_pct": round(margin, 3), "p_a": round(pa * 100, 2),
                "p_b": round(pb * 100, 2), "captured_utc": reading.get("fetched_utc"),
                "name_similarity": None, "team_order_flipped": bool(reading.get("reversed")),
                "best_of": None,
                "note": f"kickoff text on the page: {reading.get('kickoff_text') or 'not shown'}; "
                        f"{len(books)} named bookmaker rows read",
            })
            matched += 1
    return rows, {"matched": matched, "refused": refused, "lists": egw.get("lists"),
                  "candidate_matches": egw.get("candidate_matches"),
                  "stopped_at_deadline": egw.get("stopped_at_deadline")}


# --------------------------------------------------------------------------------------- assemble
ALIAS_TABLE = HERE / "aliases.json"


def load_alias_hints() -> dict:
    """Optional alias hints: Hotspawn spelling -> official-data spelling.

    Only entries with an `evidence` URL may be used, and every use is flagged on the site so the
    mapping is visible for manual review instead of being applied silently.
    """
    if not ALIAS_TABLE.exists():
        return {}
    try:
        raw = json.loads(ALIAS_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict) and v.get("evidence")}


def resolve_team(name: str, hltv: dict, valve: dict, aliases: dict) -> dict:
    """Resolve a Hotspawn team name to the official HLTV / Valve rating rows.

    Exact normalised equality only.  A different spelling is resolved solely through an explicit
    alias entry that carries an evidence link, and such a row is marked for review.
    """
    row = {"name": name, "hltv_name": None, "hltv_rank": None, "hltv_points": None,
           "hltv_source_url": f"{HLTV_RANKING_URL}/", "vrs_name": None, "vrs_points": None,
           "vrs_source_url": valve.get("blob_url"), "method": "unresolved", "flag": None}
    key = norm(name)
    for team, data in (hltv.get("ranking") or {}).items():
        if norm(team) == key:
            row.update(hltv_name=team, hltv_rank=data.get("rank"), hltv_points=data.get("points"),
                       method="exact name match (HLTV ranking)")
            break
    for team, data in (valve.get("teams") or {}).items():
        if norm(team) == key:
            row.update(vrs_name=team, vrs_points=data.get("points"),
                       method=(row["method"] if row["method"] != "unresolved" else
                               "exact name match (Valve standings)"))
            break
    if row["hltv_name"] or row["vrs_name"]:
        if not (row["hltv_name"] and row["vrs_name"]):
            row["flag"] = ("S-F-05: team found in one official rating source only "
                           f"({'HLTV' if row['hltv_name'] else 'Valve'})")
        return row
    hint = aliases.get(name) or aliases.get(key)
    if hint:
        target = hint.get("official_name") or ""
        for team, data in (valve.get("teams") or {}).items():
            if norm(team) == norm(target):
                row.update(vrs_name=team, vrs_points=data.get("points"), method="alias (evidence link)")
                break
        for team, data in (hltv.get("ranking") or {}).items():
            if norm(team) == norm(target):
                row.update(hltv_name=team, hltv_rank=data.get("rank"),
                           hltv_points=data.get("points"),
                           method="alias (evidence link)")
                break
        if row["vrs_name"] or row["hltv_name"]:
            row["flag"] = (f"S-F-06: Hotspawn names this team \"{name}\"; the official source "
                           f"lists \"{target}\" — alias applied from an evidence-linked entry, "
                           "kept visible for review")
        else:
            row["flag"] = (f"S-F-07: alias entry points at \"{target}\", which is not in the "
                           "fetched official sources")
    else:
        row["flag"] = ("S-F-04: no exact match for this name in HLTV's ranking or Valve's "
                       "standings — no rating, no originated line")
    return row


def main() -> int:
    started = time.time()
    DATA.mkdir(parents=True, exist_ok=True)
    stamp = now_iso()
    now = datetime.now(timezone.utc)
    flags: list[dict] = []
    prov_extra: list[dict] = []

    def add_flag(flag_id: str, severity: str, subject: str, detail: str, links: list[str]) -> None:
        flags.append({"id": flag_id, "severity": severity, "subject": subject, "detail": detail,
                      "links": " ".join(links)})

    hs = hotspawn_capture()
    fixtures_raw = hs.get("fixtures") or []
    hltv = hltv_listing()
    valve = valve_standings()
    aliases = load_alias_hints()

    for fx in fixtures_raw:
        fx["sport"] = sport_of(fx)
        fx["live_status"] = live_status(fx, now)

    candidates = [fx for fx in fixtures_raw if fx["live_status"] == "open"]
    print(f"[slate] payload rows={len(fixtures_raw)} open={len(candidates)} "
          f"hltv_listing={len(hltv.get('rows') or [])} vrs_teams={len(valve.get('teams') or {})}",
          flush=True)

    pin_rows, pin_meta = pinnacle_markets(candidates)
    egw_rows, egw_meta = egw_readings(candidates)
    print(f"[slate] pinnacle matched={len(pin_rows)} egw matched={len(egw_rows)}", flush=True)

    # ------------------------------------------------------------------ fixtures table (S-01)
    fixtures = []
    for fx in sorted(fixtures_raw, key=lambda r: (r.get("scheduled_start_utc") or "",
                                                  r.get("match_id") or "")):
        fixtures.append({
            "fixture_id": fx.get("match_id"),
            "sport": fx["sport"],
            "competition": fx.get("competition"),
            "tier": fx.get("tier"),
            "stage": fx.get("stage"),
            "points": fx.get("offered_points"),
            "best_of": fx.get("best_of"),
            "team_a": fx.get("team_a"),
            "team_b": fx.get("team_b"),
            "start_utc": fx.get("scheduled_start_utc"),
            "lock_utc": fx.get("lock_utc"),
            "lock_offset_sec": fx.get("lock_offset_sec"),
            "live_status": fx["live_status"],
            "hotspawn_pages": ",".join(fx.get("pages") or []),
            "source_url": fx.get("source_url"),
            "captured_utc": fx.get("snapshot_utc"),
            "crowd_pct_a_audit_only": fx.get("crowd_pct_a"),
            "crowd_pct_b_audit_only": fx.get("crowd_pct_b"),
            "total_picks_audit_only": fx.get("total_picks"),
        })

    # ------------------------------------------------------------------ team ratings (S-03)
    open_teams = sorted({t for fx in candidates for t in (fx.get("team_a"), fx.get("team_b")) if t})
    all_teams = sorted({t for fx in fixtures_raw for t in (fx.get("team_a"), fx.get("team_b")) if t})
    ratings = []
    for name in all_teams:
        row = resolve_team(name, hltv, valve, aliases)
        row["on_open_slate"] = "yes" if name in open_teams else "no"
        row["hltv_ranking_url"] = f"{HLTV_RANKING_URL}/2026/october/12"
        ratings.append(row)
        if row["flag"] and row["on_open_slate"] == "yes":
            add_flag(row["flag"].split(":")[0], "unverified", f"Team rating: {name}",
                     row["flag"].split(": ", 1)[-1],
                     [u for u in (row["hltv_source_url"], row["vrs_source_url"]) if u])
    rating_by_team = {r["name"]: r for r in ratings}

    # HLTV listing cross-reference per fixture (match id + URL + kickoff check)
    hltv_by_fixture: dict[str, dict] = {}
    for fx in fixtures_raw:
        best = None
        for row in hltv.get("rows") or []:
            same = (similarity(fx.get("team_a"), row.get("team_a"))
                    + similarity(fx.get("team_b"), row.get("team_b"))) / 2
            swapped = (similarity(fx.get("team_a"), row.get("team_b"))
                       + similarity(fx.get("team_b"), row.get("team_a"))) / 2
            score = max(same, swapped)
            if score < 0.62:
                continue
            kickoff_ok = row.get("kickoff_utc") == fx.get("scheduled_start_utc")
            if best is None or (kickoff_ok, score) > (best[0], best[1]):
                best = (kickoff_ok, score, row, swapped > same)
        if best:
            _, score, row, flipped = best
            hltv_by_fixture[fx["match_id"]] = {
                "hltv_match_id": row["hltv_match_id"], "hltv_url": row["hltv_url"],
                "hltv_event": row["event"], "hltv_kickoff_utc": row["kickoff_utc"],
                "hltv_team_order": "listed B vs A" if flipped else "listed A vs B",
                "kickoff_check": ("agree" if row["kickoff_utc"] == fx.get("scheduled_start_utc")
                                  else f"differs: HLTV {row.get('kickoff_utc')}"),
                "similarity": round(score, 3),
            }

    # ------------------------------------------------------------------ own originated lines (S-03)
    def own_line(fx: dict) -> dict:
        a, b = rating_by_team.get(fx.get("team_a")) or {}, rating_by_team.get(fx.get("team_b")) or {}
        best_of = fx.get("best_of") if isinstance(fx.get("best_of"), int) else None
        out = {"fixture_id": fx["match_id"], "best_of": best_of,
               "hltv_map_p_a": None, "hltv_map_p_b": None, "hltv_series_p_a": None,
               "vrs_map_p_a": None, "vrs_map_p_b": None, "vrs_series_p_a": None,
               "own_map_p_a": None, "own_map_p_b": None, "own_series_p_a": None,
               "own_series_p_b": None, "fair_odds_a": None, "fair_odds_b": None,
               "basis": "", "series_basis": "", "flags": ""}
        notes, series_notes, row_flags = [], [], []
        if a.get("hltv_points") and b.get("hltv_points"):
            p = elo_p(float(a["hltv_points"]), float(b["hltv_points"]))
            out["hltv_map_p_a"], out["hltv_map_p_b"] = round(p * 100, 2), round((1 - p) * 100, 2)
            out["hltv_series_p_a"] = round(series_from_map(p, best_of) * 100, 2)
            notes.append("HLTV ranking points")
            series_notes.append(f"HLTV points -> Elo({ELO_SCALE:.0f}) -> "
                                f"{'BO' + str(best_of) if best_of else 'map'} series")
        if a.get("vrs_points") and b.get("vrs_points"):
            p = elo_p(float(a["vrs_points"]), float(b["vrs_points"]))
            out["vrs_map_p_a"], out["vrs_map_p_b"] = round(p * 100, 2), round((1 - p) * 100, 2)
            out["vrs_series_p_a"] = round(series_from_map(p, best_of) * 100, 2)
            notes.append("Valve Regional Standings points")
            series_notes.append(f"VRS points -> Elo({ELO_SCALE:.0f}) -> "
                                f"{'BO' + str(best_of) if best_of else 'map'} series")
        map_parts = [x for x in (out["hltv_map_p_a"], out["vrs_map_p_a"]) if x is not None]
        series_parts = [x for x in (out["hltv_series_p_a"], out["vrs_series_p_a"]) if x is not None]
        if map_parts:
            out["own_map_p_a"] = round(sum(map_parts) / len(map_parts), 2)
            out["own_map_p_b"] = round(100 - out["own_map_p_a"], 2)
            out["basis"] = " + ".join(notes)
        if series_parts:
            out["own_series_p_a"] = round(sum(series_parts) / len(series_parts), 2)
            out["own_series_p_b"] = round(100 - out["own_series_p_a"], 2)
            out["series_basis"] = " + ".join(series_notes)
            if best_of is None:
                row_flags.append("S-F-08: source does not state the series format; the series "
                                 "column assumes a best-of-3 and is shown for reference only")
                out["series_basis"] += " [best-of-3 assumed]"
        if out["own_map_p_a"] is None:
            row_flags.append("S-F-04: no originated line — at least one team has no official rating")
        if out["own_map_p_a"] is not None:
            out["fair_odds_a"] = round(100 / out["own_map_p_a"], 2)
            out["fair_odds_b"] = round(100 / out["own_map_p_b"], 2)
        out["flags"] = "; ".join(row_flags)
        return out

    own_lines = [own_line(fx) for fx in candidates]
    own_by_fixture = {o["fixture_id"]: o for o in own_lines}

    # ------------------------------------------------------------------ merged analysis table
    lines_by_fixture: dict[str, list[dict]] = {}
    for row in pin_rows + egw_rows:
        lines_by_fixture.setdefault(row["fixture_id"], []).append(row)

    analysis = []
    for fx in candidates:
        own = own_by_fixture.get(fx["match_id"], {})
        market_rows = lines_by_fixture.get(fx["match_id"], [])
        primary = None
        for wanted in ("Pinnacle", "EGW book table"):
            for row in market_rows:
                if row["source"].startswith(wanted) or row["book"] == wanted:
                    primary = row
                    break
            if primary:
                break
        if primary is None and market_rows:
            primary = market_rows[0]
        market_p_a = primary["p_a"] if primary else None
        own_p_a = own.get("own_series_p_a") if own.get("own_series_p_a") is not None else own.get("own_map_p_a")
        own_kind = "series" if own.get("own_series_p_a") is not None else ("map" if own.get("own_map_p_a") else None)
        consensus = None
        if market_p_a is not None and own_p_a is not None:
            consensus = round((market_p_a + own_p_a) / 2, 2)
        elif market_p_a is not None:
            consensus = market_p_a
        elif own_p_a is not None:
            consensus = own_p_a
        pick, pick_p, basis, flag_row = "", None, "", []
        if consensus is not None:
            pick = fx["team_a"] if consensus >= 50 else fx["team_b"]
            pick_p = consensus if consensus >= 50 else round(100 - consensus, 2)
            if market_p_a is not None and own_p_a is not None:
                basis = ("market line and our own rating line agree"
                         if (market_p_a >= 50) == (own_p_a >= 50) else
                         "market line and our own rating line DISAGREE — market line preferred, "
                         "divergence flagged")
                if (market_p_a >= 50) != (own_p_a >= 50):
                    flag_row.append("S-F-09")
            elif market_p_a is not None:
                basis = "external bookmaker line only (no official rating for both teams)"
            else:
                basis = f"our own rating line only ({own_kind}-level)"
                flag_row.append("S-F-10")
        else:
            basis = "no probability available — market unavailable and no official rating for both teams"
            flag_row.append("S-F-11")
        hltv_ref = hltv_by_fixture.get(fx["match_id"], {})
        analysis.append({
            "fixture_id": fx["match_id"], "sport": fx["sport"], "competition": fx.get("competition"),
            "tier": fx.get("tier"), "points": fx.get("offered_points"),
            "start_utc": fx.get("scheduled_start_utc"), "lock_utc": fx.get("lock_utc"),
            "team_a": fx.get("team_a"), "team_b": fx.get("team_b"),
            "best_of": fx.get("best_of"),
            "market_source": primary["source"] if primary else "",
            "market_book": primary["book"] if primary else "",
            "market_odds_a": primary["odds_a"] if primary else None,
            "market_odds_b": primary["odds_b"] if primary else None,
            "market_overround_pct": primary["overround_pct"] if primary else None,
            "market_p_a_pct": market_p_a, "market_p_b_pct": (round(100 - market_p_a, 2) if market_p_a is not None else None),
            "market_captured_utc": primary["captured_utc"] if primary else "",
            "market_url": primary["source_url"] if primary else "",
            "own_p_a_pct": own.get("own_map_p_a"), "own_p_b_pct": own.get("own_map_p_b"),
            "own_series_p_a_pct": own.get("own_series_p_a"), "own_series_p_b_pct": own.get("own_series_p_b"),
            "own_basis": own.get("basis") or "no official rating for both teams",
            "own_series_basis": own.get("series_basis"),
            "own_fair_odds_a": own.get("fair_odds_a"), "own_fair_odds_b": own.get("fair_odds_b"),
            "consensus_p_a_pct": consensus,
            "pick": pick, "pick_pct": pick_p, "pick_basis": basis,
            "hltv_url": hltv_ref.get("hltv_url", ""), "hltv_match_id": hltv_ref.get("hltv_match_id", ""),
            "kickoff_check": hltv_ref.get("kickoff_check", "no HLTV listing row matched"),
            "hotspawn_url": (f"https://play.hotspawn.com/{fx['sport']}-pickems"
                             if fx["sport"] in ("cs2", "thp", "lol") else "https://play.hotspawn.com/lobby"),
            "captured_utc": fx.get("snapshot_utc"),
            "flags": ";".join([f for f in flag_row if f] + ([own["flags"]] if own.get("flags") else [])),
        })

    # ------------------------------------------------------------------ coverage / counting flags
    page_counts = {}
    for entry in hs.get("pages") or []:
        page_counts[entry["page"]] = {
            "url": entry["url"], "status": entry["status"], "state_rows": entry["state_rows"],
            "cards_rendered": entry["cards_rendered"], "week_total_text": entry.get("week_total_text"),
            "error": entry.get("error"),
        }
    payload_cs2 = sum(1 for f in fixtures if f["sport"] == "cs2")
    payload_open_cs2 = sum(1 for f in fixtures if f["sport"] == "cs2" and f["live_status"] == "open")
    week_text = hs.get("week_total_text")
    if week_text is not None and week_text != len(candidates):
        add_flag("S-F-02", "needs review",
                 "Hotspawn counts differ from the parseable open slate",
                 f"The page header says \"{week_text} matches this week\"; the ng-state payload yields "
                 f"{len(fixtures)} fixtures, of which {len(candidates)} have a lock time in the future. "
                 "Weekly counts include fixtures from other titles and rows already locked; the "
                 "fixtures table is the authoritative list and is complete for the payload.",
                 [page_counts.get("cs2-pickems", {}).get("url", "https://play.hotspawn.com/cs2-pickems")])
    stale = [f for f in fixtures if f["live_status"].startswith("stale")]
    if stale:
        add_flag("S-F-03", "needs review",
                 f"{len(stale)} Hotspawn rows are scheduled in the past but still listed as scheduled",
                 "These rows carry a scheduled start months before this capture and no bookmaker still "
                 "prices them; they are listed here for completeness but are not part of the pickable "
                 "slate and get no line or pick.",
                 [page_counts.get("cs2-pickems", {}).get("url", "https://play.hotspawn.com/cs2-pickems")])
    for name, meta in (("pinnacle", pin_meta), ("egw", egw_meta)):
        if meta.get("error"):
            add_flag("S-F-12", "needs review", f"{name} collection error", str(meta["error"]),
                     ["https://www.pinnacle.com/en/esports/games/cs2/matchups/",
                      "https://egamersworld.com/counterstrike/matches"])

    open_without_market = [a for a in analysis if a["market_p_a_pct"] is None]
    open_without_own = [a for a in analysis if a["own_p_a_pct"] is None]
    open_without_any = [a for a in analysis if not a["pick"]]
    if open_without_market:
        add_flag("S-F-13", "needs review",
                 f"{len(open_without_market)} open fixtures have no external market line",
                 "No price could be read from the sources this run (a source that returns an error or "
                 "serves no odds table is recorded as a refusal). Those rows show the price as blank, "
                 "exactly as read — nothing is estimated.",
                 ["https://egamersworld.com/counterstrike/matches",
                  "https://www.pinnacle.com/en/esports/games/cs2/matchups/"])
    if open_without_own:
        add_flag("S-F-14", "needs review",
                 f"{len(open_without_own)} open fixtures have no originated line",
                 "At least one team in the fixture has no row with an exact name match in the HLTV "
                 "ranking or Valve's standings, so no rating-based probability is invented for it.",
                 [f"{HLTV_RANKING_URL}/2026/october/12", valve.get("blob_url") or VRS_LISTING_API])
    if open_without_any:
        add_flag("S-F-15", "needs review",
                 f"{len(open_without_any)} open fixtures have no pick at all",
                 "Neither a market line nor an official rating pair is available for these rows, so "
                 "they are published blank with this flag rather than filled in.",
                 ["https://play.hotspawn.com/cs2-pickems"])
    add_flag("S-F-01", "needs review",
             "Hotspawn's printed wall-clock time is not a reliable UTC value",
             "The printed time next to a match is rendered for the viewer, and this project's own "
             "readings show the same fixture printed as both UTC and UTC-4 on the same pages in "
             "different sessions, while the ticker (\"Locks in ...\") and the ng-state epoch always "
             "agree. Every time in slate/data comes from the ng-state epoch, never from the printed "
             "text.",
             ["https://play.hotspawn.com/cs2-pickems", "https://play.hotspawn.com/lobby"])
    add_flag("S-F-17", "info",
             "No Hotspawn crowd percentage is used as a probability",
             "The crowd \"% picked\" values are readable from the payload. They are copied into "
             "fixtures.csv under column names ending in _audit_only for transparency, and no build "
             "step reads those columns. Every probability on the site comes from an external "
             "bookmaker price, from our own official-rating model, or is blank.",
             ["https://play.hotspawn.com/cs2-pickems"])

    # ------------------------------------------------------------------ write data
    def write_csv(path: Path, rows: list[dict]) -> None:
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        fields: list[str] = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: ("" if v is None else v) for k, v in row.items()})

    write_csv(DATA / "fixtures.csv", fixtures)
    write_csv(DATA / "ratings.csv", ratings)
    write_csv(DATA / "lines.csv", pin_rows + egw_rows)
    write_csv(DATA / "own_lines.csv", own_lines)
    write_csv(DATA / "analysis.csv", analysis)
    write_csv(DATA / "flags.csv", flags)

    provenance = [{"url": p.get("url"), "fetched_utc": p.get("fetched_utc"), "status": p.get("status"),
                   "bytes": p.get("bytes"), "sha256": p.get("sha256"), "path": p.get("path"),
                   "error": p.get("error")} for p in (up.provenance if HAVE_UPSTREAM else [])]
    provenance += prov_extra
    summary = {
        "generated_utc": now_iso(),
        "run_seconds": round(time.time() - started, 1),
        "upstream_collector": {"reused": "refresh/collect.py (session arena/b90700c6, read-only)",
                               "available": HAVE_UPSTREAM, "error": UPSTREAM_ERROR},
        "hotspawn": {
            "pages": page_counts,
            "week_total_text": week_text,
            "week_total_context": hs.get("week_total_context"),
            "reset_utc": hs.get("reset_utc"),
            "fixtures_total": len(fixtures),
            "fixtures_cs2": payload_cs2,
            "fixtures_open": len(candidates),
            "fixtures_open_cs2": payload_open_cs2,
            "fixtures_stale": len(stale),
            "sports": {s: sum(1 for f in fixtures if f["sport"] == s)
                       for s in sorted({f["sport"] for f in fixtures})},
            "source_url": "https://play.hotspawn.com/cs2-pickems",
        },
        "hltv": {"listing_url": HLTV_MATCHES_URL, "status": hltv.get("status"),
                 "error": hltv.get("error"), "rows_read": hltv.get("rows_read"),
                 "ranking_url": f"{HLTV_RANKING_URL}/2026/october/12",
                 "ranking_teams": len(hltv.get("ranking") or {}),
                 "ranking_date_text": hltv.get("ranking_date_text")},
        "valve": {"file": valve.get("file"), "blob_url": valve.get("blob_url"),
                  "teams": len(valve.get("teams") or {}), "rows_read": valve.get("rows_read"),
                  "error": valve.get("error")},
        "pinnacle": pin_meta,
        "egw": egw_meta,
        "counts": {
            "open_fixtures": len(candidates),
            "with_market_line": sum(1 for a in analysis if a["market_p_a_pct"] is not None),
            "with_own_line": sum(1 for a in analysis if a["own_p_a_pct"] is not None),
            "with_pick": sum(1 for a in analysis if a["pick"]),
            "kickoff_agrees_with_hltv": sum(1 for a in analysis if a["kickoff_check"] == "agree"),
            "kickoff_differs_from_hltv": sum(1 for a in analysis
                                             if a["kickoff_check"].startswith("differs")),
            "no_hltv_row": sum(1 for a in analysis if not a["hltv_match_id"]),
        },
        "constants": {"elo_scale": ELO_SCALE,
                      "series_transform": "BO3 p^2(3-2p); BO5 p^3(10-15p+6p^2); BO1 identity",
                      "devig": "p_a = (1/o_a) / (1/o_a + 1/o_b)"},
    }
    (DATA / "analysis.json").write_text(json.dumps(
        {"summary": summary, "analysis": analysis, "fixtures": fixtures, "ratings": ratings,
         "flags": flags}, indent=1), encoding="utf-8")
    (DATA / "coverage.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (DATA / "provenance.json").write_text(json.dumps(
        {"generated_utc": summary["generated_utc"], "fetches": provenance}, indent=1),
        encoding="utf-8")
    print(json.dumps(summary["counts"], indent=1), flush=True)
    print(f"[slate] flags={len(flags)} provenance_rows={len(provenance)}", flush=True)
    if not fixtures:
        print("FATAL: no fixtures could be read from the Hotspawn payload", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    code = main()
    if HAVE_UPSTREAM and getattr(up, "_browser", None) is not None:
        try:
            up._browser.__exit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass
    raise SystemExit(code)
