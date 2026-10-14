#!/usr/bin/env python3
"""arena/5bcfd1b5 — a pick for every CS2 fixture Hotspawn lists.

Why this exists
---------------
On `main` @ 936d577 the published boards leave 25 of 89 Hotspawn CS2 fixtures without a
pick (`cs2/data/analysis.csv`, flags `A-NO-PICK` + `A-NO-RATING`).  Every one of those
blanks is a *lookup* failure, not a data failure: the boards only ever read Valve's
**2026-10-05** Regional Standings file, but 23 of the 25 fixtures were played in
June/July 2026 and the teams involved are ranked in Valve's **2026-06-01** /
**2026-07-06** standings.

What this script does
---------------------
1.  Reads the fixture set from `main`'s freshest committed capture (read-only).
2.  Resolves every team against the official Valve Regional Standings period that was
    **in force at the match date**, then walks a documented fallback cascade.
3.  Reads outside market prices (Pinnacle primary from `main`'s CI capture; EGamersWorld
    → BC.Game secondary from `main`'s committed lines plus this session's own live read).
4.  Publishes a pick + win probability for every fixture it can support, and leaves the
    probability **blank** — never guessed — where no official input exists.

Hard rules
----------
* Hotspawn crowd pick percentages are NEVER a probability input (nor is HLTV's
  "Pick a winner" vote).  Both are crowd polls.
* HLTV's `VRS: #N` badges are a *different, newer* Valve snapshot than Valve's own
  published file (verified: HLTV shows HEROIC "VRS #22" while Valve's 2026-10-05 file
  ranks HEROIC #15).  Badges are never mixed with Valve file standings.
* No value is inferred.  Unresolvable => blank + flag.

Run:  python3 scripts/5bcfd1b5_build.py
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import itertools
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from importlib import import_module  # noqa: E402

_ratings = import_module("5bcfd1b5_ratings")  # module name starts with a digit

Standings = _ratings.Standings
norm = _ratings.norm

OUT = os.path.join(ROOT, "data", "5bcfd1b5")
SITE = os.path.join(ROOT, "allpicks")
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
NOW_S = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")

FIXTURE_SRC = os.path.join(ROOT, "cs2", "data", "analysis.csv")          # main, 02:35:29Z
MARKET_PRIMARY = os.path.join(ROOT, "cs2", "data", "market_rows.csv")    # Pinnacle, 02:35:36Z
MARKET_SECONDARY = os.path.join(ROOT, "data", "8944bb84", "external_lines.csv")
MARKET_OWN_READ = os.path.join(OUT, "market_reads.csv")
FORMAT_SRC = os.path.join(ROOT, "data", "8944bb84", "fixtures.csv")      # HLTV-verified formats
HLTV_URL_SRC = os.path.join(ROOT, "data", "8944bb84", "fixtures.csv")
MODEL_K_SRC = os.path.join(ROOT, "cs2", "data", "summary.json")

HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"

# --------------------------------------------------------------------------
# Verified team-name aliases.  Every entry carries the evidence that proves it;
# an alias without roster-level evidence is deliberately NOT listed here.
# --------------------------------------------------------------------------
ALIASES: dict[str, dict] = {
    "Envy": {
        "vrs_name": "3DMAX",
        "evidence": ("HLTV match 2399137 lineups list Envy (team 5991) as Graviti, Kursy, Maka, "
                     "misutaaa, Lucky; Valve's 2026-10-05 standings rank 3DMAX #21 (1500 pts) with "
                     "exactly Graviti, Kursy, Lucky, Maka, misutaaa — 5/5 roster match"),
        "urls": ["https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_10_05.md?plain=1#L26"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
    "WROTBERRY": {
        "vrs_name": "WBT",
        "evidence": ("HLTV files the Elisa BreakOut Series #2 matches under the slug "
                     "'wbt-vs-...'; Valve's 2026-10-05 standings rank WBT #60 (1201 pts). "
                     "Inherited roster verification from data/8944bb84/ratings.csv."),
        "urls": ["https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_10_05.md?plain=1#L65"],
        "verified_by": "arena/8944bb84 (inherited), re-checked by arena/5bcfd1b5",
    },
    "RoundsGG": {
        "vrs_name": "ROUNDS",
        "evidence": ("HLTV files the Elisa BreakOut Series #2 matches under the slug "
                     "'havu-vs-rounds-...'; Valve's 2026-10-05 standings rank ROUNDS #310 (548 pts). "
                     "Inherited roster verification from data/8944bb84/ratings.csv."),
        "urls": ["https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_10_05.md?plain=1#L315"],
        "verified_by": "arena/8944bb84 (inherited), re-checked by arena/5bcfd1b5",
    },
    "Patins de Ferrari": {
        "vrs_name": "Patins da Ferrari",
        "evidence": ("EGamersWorld's team page for the slug 'patins-de-ferrari' is titled "
                     "'Patins da Ferrari' and lists t9rnay, CutzMeretz, history, mlhzin, nicks; "
                     "Valve's 2026-08-03 standings rank 'Patins da Ferrari' #241 (692 pts) with "
                     "exactly CutzMeretz, history, mlhzin, nicks, t9rnay — 5/5 roster match. "
                     "The team appears in no earlier Valve period."),
        "urls": ["https://egamersworld.com/counterstrike/team/patins-de-ferrari-XBfksnqnWl",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_08_03.md?plain=1#L246"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
    "ex-Tricked": {
        "vrs_name": "Tricked",
        "evidence": ("HLTV's Tricked (team 4602) transfer log and Liquipedia's Tricked Esport "
                     "former-squad table both date the departure of Boye, IceBerg, leakz, NickyB, "
                     "salazar (and coach Rejin) to Echo at 2026-06-01. Valve's 2026-06-01 standings "
                     "rank 'Tricked' #50 (1251 pts) with exactly Boye, IceBerg, leakz, NickyB, "
                     "salazar — 5/5 roster match. The five players therefore carried Valve's "
                     "Tricked ranking into the 2026-06-27 fixtures as 'ex-Tricked'."),
        "urls": ["https://www.hltv.org/team/4602/tricked",
                 "https://liquipedia.net/counterstrike/Tricked_Esport",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_06_01.md?plain=1#L55"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
    "Keyd": {
        "vrs_name": "Keyd Stars",
        "evidence": ("HLTV files this exact fixture as 'Keyd Stars vs. Yawara at Thunderpick World "
                     "Championship 2026 South America Series 1' (match 2395423, played 26 Jun 2026), "
                     "and HLTV's event 9239 participant table names the team 'Keyd Stars'. Hotspawn "
                     "lists the same fixture (1051790, 2026-06-26T21:00Z) as 'Keyd vs Yawara'. "
                     "Valve's 2026-06-01 standings contain TWO different 'Keyd Stars' rosters "
                     "(#119 991 pts and #359 416 pts), so the alias resolves the name but not the "
                     "row — both rows stay admissible and the bracket test below decides."),
        "urls": ["https://www.hltv.org/matches/2395423/keyd-stars-vs-yawara-thunderpick-world-"
                 "championship-2026-south-america-series-1",
                 "https://www.hltv.org/events/9239/thunderpick-world-championship-2026-south-"
                 "america-series-1",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_06_01.md?plain=1#L124"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
    "ex-MANA": {
        "vrs_name": "MANA",
        "evidence": ("Valve's own two consecutive files prove the continuity: 2026-06-01 ranks "
                     "'MANA' #143 (907 pts) with ammar, BledarD, cerber, SENER1, xonn1k, and "
                     "2026-07-06 ranks 'ex-MANA' #160 (815 pts) with ammar, arbnorz, BledarD, "
                     "cerber, xonn1k — the same 4-player core under the new name. HLTV's ex-MANA "
                     "lineups (ammar, BledarD, cerber, xonn1k, vAloN) match that core."),
        "urls": ["https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_06_01.md?plain=1#L148",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_07_06.md?plain=1#L165",
                 "https://www.hltv.org/matches/2395918/ex-mana-vs-misa-cct-2026-europe-series-5-"
                 "closed-qualifier"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
}

# Teams confirmed absent from every official Valve period and unranked on HLTV.
# Recorded so the board can publish a directional pick without inventing a number.
NO_OFFICIAL_RATING: dict[str, dict] = {
    "LFO 10": {
        "finding": ("Absent from all five official Valve Regional Standings periods under any name. "
                    "A roster search for LFO 10's HLTV five (Jackinho, Sapec, flaw, dottie, tvs) "
                    "returns at most 3/5 overlap, with Entropy (#156, 813 pts) — a different team. "
                    "Valve ranks LFO 7, LFO 8 and LFO 9 but not LFO 10. HLTV shows "
                    "'HLTV: Unranked' and a 'VRS: #169' badge that contradicts Valve's own file "
                    "(#169 there is Honvéd, 788 pts), so the badge is not usable."),
        "urls": ["https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-"
                 "series-11",
                 "https://www.hltv.org/team/14084/lfo-10",
                 "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
                 "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/"
                 "standings_global_2026_10_05.md?plain=1#L174"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
    "SUKEBAN": {
        "finding": ("HLTV's match page for fixture 1081105 states 'HLTV: Unranked' and "
                    "'VRS: Unranked' for SUKEBAN (team 14091), roster RAYQUAZA, thpp, thoth, k1st, "
                    "pml. The name appears in no Valve Regional Standings period. The same HLTV page "
                    "records that SUKEBAN forfeited: 'SUKEBAN forfeit the match as they are unable "
                    "to field a complete roster.'"),
        "urls": ["https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-"
                 "series-7",
                 "https://www.hltv.org/team/14091/sukeban"],
        "verified_by": "arena/5bcfd1b5, 2026-10-14",
    },
}

# Official results confirmed on HLTV match pages during this session.
VERIFIED_RESULTS: dict[str, dict] = {
    "1081105": {
        "result": "your end 1 - 0 SUKEBAN (default / forfeit)",
        "note": "HLTV: 'SUKEBAN forfeit the match as they are unable to field a complete roster.'",
        "url": "https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-"
               "series-7",
    },
}


# --------------------------------------------------------------------------
# model
# --------------------------------------------------------------------------
def logistic(delta_points: float, k: float) -> float:
    """Valve-points logistic. delta = points(A) - points(B)."""
    return 1.0 / (1.0 + 10.0 ** (-k * delta_points / 400.0))


def series_transform(p_map: float, best_of: str) -> tuple[float, str]:
    """Best-of-n series win probability from a single-map probability.

    Both BO3 and BO5 transforms are strictly increasing on [0,1] and fix 0.5, so the
    *favourite side never depends on the format* — only the margin does.  That is why an
    unverified format still supports a pick, and is published as such on the site.
    """
    if best_of == "1":
        return p_map, "BO1 (identity)"
    if best_of == "3":
        return p_map ** 2 * (3 - 2 * p_map), "BO3 p^2(3-2p)"
    if best_of == "5":
        return p_map ** 3 * (10 - 15 * p_map + 6 * p_map ** 2), "BO5 p^3(10-15p+6p^2)"
    return p_map, "format unverified — single-map estimate (favourite side is format-invariant)"


def devig(oa: float, ob: float) -> tuple[float, float, float]:
    ia, ib = 1.0 / oa, 1.0 / ob
    return ia / (ia + ib), ib / (ia + ib), (ia + ib - 1.0) * 100.0


def is_placeholder(oa: str, ob: str) -> bool:
    """EGamersWorld prints 1.80/1.80 when it has no real price."""
    try:
        a, b = float(oa), float(ob)
    except (TypeError, ValueError):
        return True
    return abs(a - b) < 1e-9 and abs(a - 1.80) < 0.005


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------
def read_csv(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model_k() -> tuple[float, str, int]:
    try:
        with open(MODEL_K_SRC, encoding="utf-8") as fh:
            s = json.load(fh)["own_line"]
        return float(s["k"]), s["basis"], int(s["n_calibrated_on"])
    except Exception:
        return 1.0, "Valve default k=1.0 (calibration file unavailable)", 0


PIN_SRC = os.path.join(ROOT, "data", "8944bb84", "ratings.csv")
PIN_FILE = "standings_global_2026_10_05.md"


def load_verified_pins(st: Standings) -> dict[str, dict]:
    """Re-check another session's duplicate-name disambiguation against Valve's own file.

    `data/8944bb84/ratings.csv` records, for 94 teams, the exact Valve standings line that
    an HLTV roster check selected when a team name appears more than once.  Inheriting that
    saves re-fetching 94 HLTV pages, but it is only trusted after this function re-reads the
    official file and confirms team name, standing and points all still agree.  A pin that
    fails the re-check is dropped and flagged, never used.
    """
    oct_rows = {r["line"]: r for r in st.periods[dt.date(2026, 10, 5)]}
    pins: dict[str, dict] = {}
    rejected: list[dict] = []
    for r in read_csv(PIN_SRC):
        line = (r.get("vrs_line") or "").strip()
        if not line.isdigit() or not (r.get("resolution") or "").startswith("VERIFIED"):
            continue
        row = oct_rows.get(int(line))
        team = r["hotspawn_team"]
        if not row:
            rejected.append({"team": team, "why": "line %s is not a standings row" % line})
            continue
        ok_name = norm(row["team"]) == norm(r["vrs_name"])
        ok_rank = str(row["standing"]) == str(r["vrs_standing"]).strip()
        ok_pts = str(row["points"]) == str(r["vrs_points"]).strip()
        if not (ok_name and ok_rank and ok_pts):
            rejected.append({"team": team,
                             "why": "pin says %s #%s/%s pts but Valve's line %s reads %s #%d/%d pts"
                                    % (r["vrs_name"], r["vrs_standing"], r["vrs_points"], line,
                                       row["team"], row["standing"], row["points"])})
            continue
        pins[team] = {"row": row, "resolution": r["resolution"],
                      "url": st.source_url(row),
                      "hltv_url": (r.get("hltv_url") or "").strip()}
    if rejected:
        print("[5bcfd1b5] inherited pins re-checked: %d accepted, %d rejected -> %s"
              % (len(pins), len(rejected), rejected[:3]))
    else:
        print("[5bcfd1b5] inherited pins re-checked: %d accepted, 0 rejected" % len(pins))
    load_verified_pins.rejected = rejected  # type: ignore[attr-defined]
    return pins


def resolve_team(st: Standings, team: str, when: dt.datetime,
                 pins: dict[str, dict] | None = None) -> dict:
    """Official-rating cascade for one team at one match date.

    Returns a dict with `candidates` (a list of Valve VRS rows) and `basis`.  An empty
    candidate list means: no official rating exists, so no probability may be printed.
    """
    period = st.period_in_force(when)
    out = {
        "team": team, "candidates": [], "basis": "", "period": "", "alias": "",
        "alias_evidence": "", "alias_urls": [], "anachronistic": False, "unranked": "",
        "unranked_urls": [], "pin": "",
    }
    if period is None:
        out["basis"] = "no official Valve standings published on or before the match date"
        return out

    names = [team]
    alias_of = {}
    if team in ALIASES:
        a = ALIASES[team]
        names.append(a["vrs_name"])
        alias_of[a["vrs_name"]] = a

    def claim_alias(matched_name: str) -> None:
        """Record the alias only if the alias name is what matched Valve's file.

        WROTBERRY appears under its own name in Valve's June standings and only becomes WBT
        by October, so a June fixture must not be reported as alias-resolved.
        """
        a = alias_of.get(matched_name)
        if a and matched_name != team:
            out["alias"] = "%s → %s" % (team, matched_name)
            out["alias_evidence"] = a["evidence"]
            out["alias_urls"] = list(a["urls"])

    # 1. period in force, exact name (alias second)
    for n in names:
        hits = st.exact(period, n)
        if hits:
            # 1b. a re-checked roster pin narrows same-name duplicates to one official row
            pin = (pins or {}).get(team)
            if pin and len(hits) > 1 and pin["row"]["file"] == PIN_FILE:
                match = [h for h in hits if h["line"] == pin["row"]["line"]]
                if match:
                    out["candidates"] = match
                    out["period"] = period.isoformat()
                    claim_alias(n)
                    out["pin"] = ("duplicate Valve name disambiguated by the HLTV roster check "
                                  "recorded in data/8944bb84/ratings.csv (%s) and re-verified "
                                  "line-by-line against Valve's file by this session"
                                  % pin["resolution"])
                    out["basis"] = ("official Valve Regional Standings in force at the match date "
                                    "(%s), row pinned by roster" % period.isoformat())
                    return out
            out["candidates"] = hits
            out["period"] = period.isoformat()
            claim_alias(n)
            out["basis"] = ("official Valve Regional Standings in force at the match date "
                            "(%s)" % period.isoformat())
            return out

    # 2. earliest official period at/after the match period that contains the exact name
    for n in names:
        found = st.first_period_containing(n, period)
        if found:
            p, hits = found
            out["candidates"] = hits
            out["period"] = p.isoformat()
            claim_alias(n)
            out["anachronistic"] = p != period
            out["basis"] = ("team absent from the %s standings; earliest official Valve period "
                            "containing this exact name is %s" % (period.isoformat(), p.isoformat()))
            return out

    if team in NO_OFFICIAL_RATING:
        d = NO_OFFICIAL_RATING[team]
        out["unranked"] = d["finding"]
        out["unranked_urls"] = list(d["urls"])
        out["basis"] = "confirmed absent from every official Valve period and unranked on HLTV"
    else:
        out["basis"] = "not found in any official Valve Regional Standings period"
    return out


LIVECHECK = os.path.join(OUT, "livecheck.json")


def merge_live_fixtures(fixtures: list[dict], flag, now_s: str) -> int:
    """Append fixtures the scheduled live check found on Hotspawn that the board lacks.

    `scripts/5bcfd1b5_livecheck.py` re-reads Hotspawn's own Angular payload and reports
    fixtures it now lists. Merging them here closes the loop: a newly listed match reaches
    the board, gets the same official-rating cascade and our own line as every other row,
    and is flagged NEEDS REVIEW so a human sees that it was discovered after the capture.

    Only values Hotspawn's payload actually carries are copied. Anything it does not carry
    (its point value, an HLTV match id) is left BLANK and never inferred.
    """
    if not os.path.exists(LIVECHECK):
        return 0
    try:
        with open(LIVECHECK, encoding="utf-8") as fh:
            report = json.load(fh)
    except (OSError, ValueError):
        return 0
    if not report.get("comparison_possible") or not report.get("new_on_hotspawn"):
        return 0
    have = {f["fixture_id"] for f in fixtures}
    added = 0
    for n in report["new_on_hotspawn"]:
        fid = str(n.get("fixture_id") or "")
        if not fid or fid in have:
            continue
        lock = n.get("lock_utc") or ""
        start = n.get("start_utc") or ""
        is_open = bool(lock) and lock > now_s
        fmt = (n.get("series_format") or "").strip()
        best_of = fmt.replace("BO", "").strip() if fmt else ""
        fixtures.append({
            "fixture_id": fid, "state": "open" if is_open else "stale",
            "pickable": "yes" if is_open else "no",
            "start_utc": start, "lock_utc": lock,
            "competition": n.get("tournament") or "", "tier": n.get("tier") or "",
            # Hotspawn's payload does not carry the pick'em point value: blank, not guessed.
            "points": "", "best_of": best_of if best_of in ("1", "3", "5") else "",
            "team_a": n.get("team_a") or "", "team_b": n.get("team_b") or "",
            "hotspawn_url": "https://play.hotspawn.com/lobby",
            "hotspawn_match_url": n.get("source_url") or "",
            "captured_utc": report.get("compared_utc") or now_s,
            "live_discovered": "yes",
        })
        have.add(fid)
        added += 1
        flag("LIVE-NEW-FIXTURE", "%s vs %s (%s)" % (n.get("team_a"), n.get("team_b"), fid),
             "Hotspawn began listing this fixture after the board's capture (%s). It was picked up "
             "by the scheduled live check and added to the board with the same official-rating "
             "cascade as every other row. Its Hotspawn point value is not in the payload, so it is "
             "left blank rather than inferred. Needs review: confirm the rating resolution and, if "
             "a book prices it, that the market line is picked up on the next cycle."
             % (report.get("compared_utc") or "unknown"),
             [n.get("source_url") or "https://play.hotspawn.com/lobby"], "NEEDS REVIEW")
    return added


def main() -> int:
    st = Standings()
    K, K_BASIS, K_N = load_model_k()
    pins = load_verified_pins(st)

    fixtures = read_csv(FIXTURE_SRC)
    if not fixtures:
        print("FATAL: no fixtures at %s" % FIXTURE_SRC, file=sys.stderr)
        return 1

    fmt_by_id = {r["match_id"]: r for r in read_csv(FORMAT_SRC)}
    primary = {r["fixture_id"]: r for r in read_csv(MARKET_PRIMARY)}
    secondary = {r["match_id"]: r for r in read_csv(MARKET_SECONDARY)}
    own_read = {r["fixture_id"]: r for r in read_csv(MARKET_OWN_READ)}

    rows: list[dict] = []
    flags: list[dict] = []
    team_log: dict[str, dict] = {}

    def flag(code: str, subject: str, detail: str, urls: list[str], severity: str = "INFO"):
        flags.append({"flag_id": "%s-%d" % (code, len(flags) + 1), "code": code,
                      "subject": subject, "detail": detail, "severity": severity,
                      "official_source_url": urls[0] if urls else "",
                      "other_source_urls": ";".join(urls[1:]) if len(urls) > 1 else "",
                      "raised_utc": NOW_S, "raised_by": "arena/5bcfd1b5"})

    n_live = merge_live_fixtures(fixtures, flag, NOW_S)
    if n_live:
        print("[5bcfd1b5] live check added %d newly listed fixture(s) to the board" % n_live)

    for f in fixtures:
        fid = f["fixture_id"]
        start = dt.datetime.strptime(f["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
        ta, tb = f["team_a"], f["team_b"]
        fmtrow = fmt_by_id.get(fid, {})
        best_of = (fmtrow.get("series_format") or "").replace("BO", "").strip()
        if best_of not in ("1", "3", "5"):
            best_of = f.get("best_of") or ""
        if best_of not in ("1", "3", "5"):
            best_of = ""
        fmt_src = ("HLTV match page (data/8944bb84/fixtures.csv, arena/8944bb84)"
                   if (fmtrow.get("series_format") or "").strip() else
                   ("Hotspawn payload best_of" if f.get("best_of") else ""))

        ra = resolve_team(st, ta, start, pins)
        rb = resolve_team(st, tb, start, pins)
        # Keyed by (team, rating period): the same Hotspawn name can legitimately resolve to
        # DIFFERENT Valve rows in different periods (WROTBERRY is itself in the June standings
        # but is WBT by October), so collapsing on the name alone would hide a real resolution.
        for side, r in ((ta, ra), (tb, rb)):
            key = (side, r["period"] or ("unranked" if r["unranked"] else "unresolved"))
            if key not in team_log:
                team_log[key] = dict(r)
                team_log[key]["cand_count"] = len(r["candidates"])
                team_log[key]["fixtures"] = []
            team_log[key]["fixtures"].append(fid)

        # ---- market: tier A (primary book) then tier B (named secondary book) ----
        m_tier = m_book = m_oa = m_ob = m_url = m_cap = m_read = ""
        m_pa = m_pb = m_over = ""
        p = primary.get(fid)
        if p and p.get("odds_a") and p.get("odds_b"):
            oa, ob = float(p["odds_a"]), float(p["odds_b"])
            pa, pb, ov = devig(oa, ob)
            m_tier, m_book = "A", "%s (primary, read by CI)" % p["book"]
            m_oa, m_ob = "%.4f" % oa, "%.4f" % ob
            m_pa, m_pb, m_over = "%.1f" % (pa * 100), "%.1f" % (pb * 100), "%.2f" % ov
            m_url = p.get("url") or p.get("source") or ""
            m_cap, m_read = p.get("captured_utc", ""), "main CI capture (cs2/data/market_rows.csv)"
        if not m_tier:
            for src, label, geturls in (
                (own_read.get(fid), "this session's live read",
                 lambda r: (r["odds_listed_a"], r["odds_listed_b"], r["aggregator_url"],
                            r["read_utc"], r["book"], r["aggregator"], r["accepted"],
                            r["reject_reason"], r["team_listed_a"], r["team_listed_b"],
                            r["orientation_note"])),
                (secondary.get(fid), "main's committed read", None),
            ):
                if not src:
                    continue
                if geturls:
                    (oa_s, ob_s, url, cap, book, agg, acc, rej, la, lb, orient) = geturls(src)
                    if acc != "yes":
                        flag("MARKET-PLACEHOLDER", "%s vs %s (%s)" % (ta, tb, fid),
                             "%s rejected this fixture's price: %s" % (book + "/" + agg, rej),
                             [url], "INFO")
                        continue
                    # EGW column order can differ from Hotspawn's — map by team name.
                    if norm(lb) == norm(ta) and norm(la) == norm(tb):
                        oa_s, ob_s = ob_s, oa_s
                        orient += " [odds swapped to Hotspawn order]"
                    oa, ob = float(oa_s), float(ob_s)
                    book_lbl = "%s via %s (secondary)" % (book, agg)
                else:
                    # CITATION INTEGRITY: book label, odds and source URL must all come from the
                    # SAME read. Upstream records two independent reads for 8 fixtures — a direct
                    # Pinnacle API read and an EGamersWorld bc.game read — with different numbers.
                    # An earlier draft of this build paired Pinnacle's label with EGamersWorld's
                    # odds and URL, which misattributes the price; the primary read wins and its
                    # own URL is cited, with the aggregator read kept as a cross-check note.
                    pk_book = (src.get("primary_book") or "").strip()
                    pk_oa, pk_ob = src.get("primary_odds_a") or "", src.get("primary_odds_b") or ""
                    pk_url = (src.get("primary_source_url") or "").strip()
                    cap = src.get("captured_utc", "")
                    if pk_book and pk_oa and pk_ob and pk_url:
                        oa_s, ob_s, url = pk_oa, pk_ob, pk_url
                        book_lbl = "%s — read directly at %s (arena/8944bb84), not re-read this " \
                                   "cycle" % (pk_book, cap or "an unstated time")
                        if src.get("egw_odds_a") and src.get("egw_odds_a") != pk_oa:
                            book_lbl += "; cross-check: EGamersWorld reports bc.game %s/%s at %s" \
                                        % (src["egw_odds_a"], src["egw_odds_b"],
                                           src.get("egw_url") or "egamersworld.com")
                    else:
                        oa_s = src.get("egw_odds_a") or ""
                        ob_s = src.get("egw_odds_b") or ""
                        url = src.get("egw_url") or ""
                        book_lbl = ("%s (secondary)" % pk_book) if pk_book else \
                                   "bc.game via EGamersWorld (secondary)"
                    if not oa_s or not ob_s:
                        continue
                    if is_placeholder(oa_s, ob_s):
                        flag("MARKET-PLACEHOLDER", "%s vs %s (%s)" % (ta, tb, fid),
                             "%s shows the 1.80/1.80 un-priced placeholder; rejected, not "
                             "de-vigged." % (pk_book or "EGamersWorld"),
                             [url or "https://egamersworld.com/counterstrike/matches"], "INFO")
                        continue
                    oa, ob = float(oa_s), float(ob_s)
                    orient = ""
                pa, pb, ov = devig(oa, ob)
                m_tier, m_book = "B", book_lbl
                m_oa, m_ob = "%.3f" % oa, "%.3f" % ob
                m_pa, m_pb, m_over = "%.1f" % (pa * 100), "%.1f" % (pb * 100), "%.2f" % ov
                m_url, m_cap = url, cap
                m_read = label + (("; " + orient) if orient else "")
                break

        # ---- our own line from official Valve points ----
        own_pa = own_pb = own_lo = own_hi = ""
        own_basis = own_period = ""
        cand_a, cand_b = ra["candidates"], rb["candidates"]
        rating_note = []
        if cand_a and cand_b:
            combos = []
            for ca, cb in itertools.product(cand_a, cand_b):
                pm = logistic(ca["points"] - cb["points"], K)
                ps, tf = series_transform(pm, best_of)
                combos.append((ps, ca, cb, tf))
            ps_all = [c[0] for c in combos]
            lo_a, hi_a = min(ps_all), max(ps_all)
            winners = {("A" if p >= 0.5 else "B") for p in ps_all}
            tf = combos[0][3]
            periods = sorted({ra["period"], rb["period"]})
            own_period = "/".join(periods)
            own_lo, own_hi = "%.1f" % (lo_a * 100), "%.1f" % (hi_a * 100)
            if len(winners) == 1:
                fav = winners.pop()
                # Publish the CONSERVATIVE bound as the headline so an ambiguous rating can
                # never overstate the favourite; the full range is printed next to it.
                head_a = lo_a if fav == "A" else hi_a
                own_pa = "%.1f" % (head_a * 100)
                own_pb = "%.1f" % ((1 - head_a) * 100)
                own_basis = ("Valve VRS points logistic k=%.4f (%s); %s" % (K, K_BASIS, tf))
                if len(combos) > 1:
                    dupes = []
                    if len(cand_a) > 1:
                        dupes.append("%d admissible same-name rows for %s" % (len(cand_a), ta))
                    if len(cand_b) > 1:
                        dupes.append("%d admissible same-name rows for %s" % (len(cand_b), tb))
                    own_basis += ("; Valve publishes %s, giving %d rating combinations — the "
                                  "favourite side is identical under every combination, so the pick "
                                  "stands and the probability is published at its conservative "
                                  "bound (team-A range %s%%–%s%%)"
                                  % (" and ".join(dupes) or "%d combinations" % len(combos),
                                     len(combos), own_lo, own_hi))
                    rating_note.append("VRS-DUPLICATE-NAME-BRACKETED")
                if ra["pin"] or rb["pin"]:
                    rating_note.append("VRS-DUPLICATE-ROW-PINNED")
            else:
                own_basis = ("AMBIGUOUS: %d admissible same-name Valve rows disagree on the "
                             "favourite (team-A range %s%%–%s%%), so no own-line probability is "
                             "published" % (len(combos), own_lo, own_hi))
                own_pa = own_pb = own_lo = own_hi = ""
                rating_note.append("VRS-DUPLICATE-NAME-UNRESOLVED")
                flag("RATING-AMBIGUOUS", "%s vs %s (%s)" % (ta, tb, fid),
                     "Valve's standings contain more than one row with this exact team name and the "
                     "admissible ratings disagree on which side is the favourite. No probability is "
                     "inferred and no pick is published.",
                     [st.source_url(combos[0][1]), st.source_url(combos[0][2])], "NEEDS REVIEW")
            if ra["alias"] or rb["alias"]:
                rating_note.append("ALIAS-RESOLVED")
            if ra["anachronistic"] or rb["anachronistic"]:
                rating_note.append("RATING-PERIOD-LATER-THAN-MATCH")
        else:
            miss = [t for t, r in ((ta, ra), (tb, rb)) if not r["candidates"]]
            own_basis = "no official Valve rating for: " + ", ".join(miss)
            rating_note.append("NO-OFFICIAL-RATING")
            for t in miss:
                r = ra if t == ta else rb
                urls = r["unranked_urls"] or [HOTSPAWN_CS2]
                flag("RATING-MISSING", "%s (%s vs %s, %s)" % (t, ta, tb, fid),
                     (r["unranked"] or r["basis"]), urls, "NEEDS REVIEW")

        # ---- pick ----
        pick = pick_pct = pick_hi = pick_tier = pick_basis = ""
        actionable = f["pickable"] == "yes" and f["state"] == "open"
        if m_tier == "A":
            pick_tier = "A"
            pa, pb = float(m_pa), float(m_pb)
            pick, pick_pct = (ta, m_pa) if pa >= pb else (tb, m_pb)
            pick_basis = "%s moneyline, de-vigged — primary book read by CI this cycle" % m_book
        elif m_tier == "B":
            pick_tier = "B"
            pa, pb = float(m_pa), float(m_pb)
            pick, pick_pct = (ta, m_pa) if pa >= pb else (tb, m_pb)
            pick_basis = "%s moneyline, de-vigged — secondary aggregator report, not re-read at the book" % m_book
        elif own_pa:
            soft = ("VRS-DUPLICATE-NAME-BRACKETED" in rating_note
                    or "ALIAS-RESOLVED" in rating_note
                    or "RATING-PERIOD-LATER-THAN-MATCH" in rating_note
                    or "VRS-DUPLICATE-ROW-PINNED" in rating_note)
            pick_tier = "D" if soft else "C"
            pa = float(own_pa)
            if pa >= 50:
                pick, pick_pct = ta, own_pa
                pick_hi = own_hi if "VRS-DUPLICATE-NAME-BRACKETED" in rating_note else ""
            else:
                pick, pick_pct = tb, own_pb
                pick_hi = ("%.1f" % (100 - float(own_lo))
                           if "VRS-DUPLICATE-NAME-BRACKETED" in rating_note else "")
            pick_basis = "our own line — " + own_basis
        else:
            # tier E: official-ranking asymmetry.  One side is officially ranked by Valve and
            # the other is confirmed unranked everywhere.  Directional pick, no number invented.
            ranked = [t for t, r in ((ta, ra), (tb, rb)) if r["candidates"]]
            unranked = [t for t, r in ((ta, ra), (tb, rb))
                        if not r["candidates"] and r["unranked"]]
            if len(ranked) == 1 and len(unranked) == 1:
                pick_tier = "E"
                pick = ranked[0]
                pick_pct = ""
                r = (ra if ranked[0] == ta else rb)
                u = (ra if unranked[0] == ta else rb)
                pick_basis = ("official-ranking asymmetry: %s is ranked in Valve's %s standings "
                              "(#%d, %d pts) while %s is confirmed unranked in every official Valve "
                              "period and on HLTV. Probability deliberately left blank — no number "
                              "is invented for an unranked side."
                              % (ranked[0], r["period"], r["candidates"][0]["standing"],
                                 r["candidates"][0]["points"], unranked[0]))
                flag("PICK-WITHOUT-PROBABILITY", "%s vs %s (%s)" % (ta, tb, fid), pick_basis,
                     [st.source_url(r["candidates"][0])] + u["unranked_urls"], "NEEDS REVIEW")
            else:
                pick_tier = "F"
                pick_basis = "no official rating for at least one side and no market price — no pick"
                flag("NO-PICK", "%s vs %s (%s)" % (ta, tb, fid),
                     "Neither an outside market price nor an official Valve rating exists for both "
                     "sides, so no pick and no probability is published.",
                     [HOTSPAWN_CS2], "NEEDS REVIEW")

        if not actionable and pick:
            pick_basis += (" || Not actionable: Hotspawn locked this fixture on %s (state=%s)."
                           % (f["lock_utc"], f["state"]))

        res = VERIFIED_RESULTS.get(fid, {})
        hltv_url = (fmtrow.get("hltv_match_url") or "").strip()

        rows.append({
            "fixture_id": fid, "state": f["state"], "pickable": f["pickable"],
            "fixture_origin": ("live Hotspawn payload via scripts/5bcfd1b5_livecheck.py"
                               if f.get("live_discovered") == "yes"
                               else "cs2/data/analysis.csv capture"),
            "actionable": "yes" if actionable else "no",
            "start_utc": f["start_utc"], "lock_utc": f["lock_utc"],
            "competition": f["competition"], "tier": f["tier"], "points": f["points"],
            "best_of": best_of, "format_source": fmt_src,
            "team_a": ta, "team_b": tb,
            "vrs_period_a": ra["period"], "vrs_rank_a": (ra["candidates"][0]["standing"]
                                                         if len(ra["candidates"]) == 1 else ""),
            "vrs_points_a": (ra["candidates"][0]["points"] if len(ra["candidates"]) == 1 else ""),
            "vrs_name_a": (ra["candidates"][0]["team"] if len(ra["candidates"]) == 1 else ""),
            "vrs_roster_a": (ra["candidates"][0]["roster"] if len(ra["candidates"]) == 1 else ""),
            "vrs_url_a": (st.source_url(ra["candidates"][0]) if len(ra["candidates"]) == 1 else ""),
            "vrs_n_candidates_a": len(ra["candidates"]),
            # Every admissible Valve row is cited even when no single row was chosen, so a
            # bracketed or unresolved rating stays clickable back to Valve's own file.
            "vrs_cand_urls_a": ";".join(st.source_url(c) for c in ra["candidates"]),
            "vrs_period_b": rb["period"], "vrs_rank_b": (rb["candidates"][0]["standing"]
                                                         if len(rb["candidates"]) == 1 else ""),
            "vrs_points_b": (rb["candidates"][0]["points"] if len(rb["candidates"]) == 1 else ""),
            "vrs_name_b": (rb["candidates"][0]["team"] if len(rb["candidates"]) == 1 else ""),
            "vrs_roster_b": (rb["candidates"][0]["roster"] if len(rb["candidates"]) == 1 else ""),
            "vrs_url_b": (st.source_url(rb["candidates"][0]) if len(rb["candidates"]) == 1 else ""),
            "vrs_n_candidates_b": len(rb["candidates"]),
            "vrs_cand_urls_b": ";".join(st.source_url(c) for c in rb["candidates"]),
            "pin_a": ra["pin"], "pin_b": rb["pin"],
            "alias_a": ra["alias"], "alias_b": rb["alias"],
            "alias_evidence": ra["alias_evidence"] or rb["alias_evidence"],
            "alias_urls": ";".join(ra["alias_urls"] or rb["alias_urls"]),
            "model_k": "%.4f" % K, "model_k_basis": K_BASIS, "model_k_n": K_N,
            "own_p_a_pct": own_pa, "own_p_b_pct": own_pb,
            "own_p_lo_pct": own_lo, "own_p_hi_pct": own_hi,
            "own_basis": own_basis, "own_rating_periods": own_period,
            "market_tier": m_tier, "market_book": m_book, "market_odds_a": m_oa,
            "market_odds_b": m_ob, "market_p_a_pct": m_pa, "market_p_b_pct": m_pb,
            "market_overround_pct": m_over, "market_url": m_url,
            "market_captured_utc": m_cap, "market_read_by": m_read,
            "pick": pick, "pick_pct": pick_pct, "pick_pct_hi": pick_hi,
            "pick_tier": pick_tier, "pick_basis": pick_basis,
            "rating_note": ";".join(rating_note),
            "verified_result": res.get("result", ""), "verified_result_note": res.get("note", ""),
            "verified_result_url": res.get("url", ""),
            "hotspawn_url": f.get("hotspawn_url") or HOTSPAWN_CS2,
            "hotspawn_match_url": f.get("hotspawn_match_url", ""),
            "hltv_match_url": hltv_url,
            "captured_utc": f.get("captured_utc", ""),
            "generated_utc": NOW_S,
        })

    rows.sort(key=lambda r: (r["start_utc"], r["fixture_id"]))
    write_outputs(rows, flags, team_log, st, K, K_BASIS, K_N)
    return 0


def write_outputs(rows, flags, team_log, st, K, K_BASIS, K_N):
    os.makedirs(OUT, exist_ok=True)
    cols = list(rows[0].keys())
    with open(os.path.join(OUT, "every_match.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(OUT, "flags.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(flags[0].keys()) if flags else
                           ["flag_id", "code", "subject", "detail", "severity",
                            "official_source_url", "other_source_urls", "raised_utc", "raised_by"])
        w.writeheader()
        w.writerows(flags)
    tl = []
    for (name, _period), r in sorted(team_log.items()):
        c = r["candidates"]
        tl.append({
            "hotspawn_team": name, "resolved_vrs_name": c[0]["team"] if len(c) == 1 else "",
            "fixtures": ";".join(r["fixtures"]),
            "n_candidates": len(c),
            "candidate_standings": ";".join("#%d/%dpts/%s/L%d" % (x["standing"], x["points"],
                                                                  x["file"].replace(
                                                                      "standings_global_", ""),
                                                                  x["line"]) for x in c),
            "rating_period": r["period"], "alias": r["alias"],
            "alias_evidence": r["alias_evidence"], "alias_urls": ";".join(r["alias_urls"]),
            "anachronistic": "yes" if r["anachronistic"] else "no",
            "source_url": st.source_url(c[0]) if len(c) == 1 else "",
            "roster": c[0]["roster"] if len(c) == 1 else "",
            "basis": r["basis"], "unranked_finding": r["unranked"],
            "unranked_urls": ";".join(r["unranked_urls"]),
        })
    with open(os.path.join(OUT, "team_ratings.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tl[0].keys()))
        w.writeheader()
        w.writerows(tl)

    n = len(rows)
    open_rows = [r for r in rows if r["state"] == "open"]
    tiers = {}
    for r in rows:
        tiers[r["pick_tier"]] = tiers.get(r["pick_tier"], 0) + 1
    coverage = {
        "session": "arena/5bcfd1b5",
        "generated_utc": NOW_S,
        "hotspawn_crowd_percentages_used_as_probability": False,
        "hltv_pick_a_winner_vote_used_as_probability": False,
        "fixture_source": {"path": "cs2/data/analysis.csv",
                           "captured_utc": rows[0]["captured_utc"],
                           "origin": "main CI capture of play.hotspawn.com/lobby + /cs2-pickems"},
        "counts": {
            "fixtures_total": n,
            "state_open": len(open_rows),
            "state_started": sum(1 for r in rows if r["state"] == "started"),
            "state_stale": sum(1 for r in rows if r["state"] == "stale"),
            "with_pick": sum(1 for r in rows if r["pick"]),
            "without_pick": sum(1 for r in rows if not r["pick"]),
            "with_numeric_probability": sum(1 for r in rows if r["pick_pct"]),
            "open_with_pick": sum(1 for r in open_rows if r["pick"]),
            "open_with_numeric_probability": sum(1 for r in open_rows if r["pick_pct"]),
            "open_without_pick": sum(1 for r in open_rows if not r["pick"]),
            "pick_tiers": tiers,
            "market_tier_A": sum(1 for r in rows if r["market_tier"] == "A"),
            "market_tier_B": sum(1 for r in rows if r["market_tier"] == "B"),
            "own_line_computed": sum(1 for r in rows if r["own_p_a_pct"]),
            "flags": len(flags),
        },
        "model": {"k": K, "k_basis": K_BASIS, "k_calibrated_on": K_N,
                  "formula": "p_map(A)=1/(1+10^(-k*(ptsA-ptsB)/400))",
                  "series": "BO1 identity; BO3 p^2(3-2p); BO5 p^3(10-15p+6p^2); "
                            "unverified format publishes the single-map estimate"},
        "official_rating_source": {
            "publisher": "Valve Corporation",
            "repository": "https://github.com/ValveSoftware/counter-strike_regional_standings",
            "pinned_commit": _ratings.VALVE_COMMIT,
            "periods_used": [p.isoformat() for p in st.ordered],
            "files": {os.path.basename(os.path.join(OUT, "vrs", fn)):
                      sha256(os.path.join(OUT, "vrs", fn))
                      for fn in sorted(os.listdir(os.path.join(OUT, "vrs")))},
            "selection_rule": "latest official publication on or before the match date; if the team "
                              "is absent there, the earliest later official period containing the "
                              "exact name, flagged as anachronistic",
        },
    }
    with open(os.path.join(OUT, "coverage.json"), "w", encoding="utf-8") as fh:
        json.dump(coverage, fh, indent=1, sort_keys=False)
        fh.write("\n")

    print("[5bcfd1b5] fixtures=%d open=%d with_pick=%d without_pick=%d tiers=%s flags=%d"
          % (n, len(open_rows), coverage["counts"]["with_pick"],
             coverage["counts"]["without_pick"], tiers, len(flags)))


if __name__ == "__main__":
    raise SystemExit(main())
