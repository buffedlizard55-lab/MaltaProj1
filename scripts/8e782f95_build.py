#!/usr/bin/env python3
"""B-02..B-05 (session arena/8e782f95): build the consolidated pick'em line board.

Inputs (all captured this session, all in data/8e782f95/):
  fixtures.csv        - the current Hotspawn CS2 pick'em slate, read from the official
                        pages https://play.hotspawn.com/cs2-pickems and /lobby.
                        Times are UTC, verified against the page's own "Locks in"
                        countdowns and cross-checked against EGamersWorld kickoffs.
  external_lines.csv  - non-Hotspawn bookmaker match-winner prices (EGamersWorld's
                        bc.game market block), each with its capture time and URL.
  vrs_global_2026_10_05.md / _extract.csv
                      - Valve Regional Standings, official file from
                        github.com/ValveSoftware/counter-strike_regional_standings
                        at pinned commit eec4853d7bcf0f1f7efe7f0d901234bef7e98b75.

Outputs:
  data/8e782f95/analysis.csv   - one verified row per fixture
  board/*.html                 - the mobile-first GitHub Pages site
  board/data/*.json            - the same data as JSON for the pages

Rules:
  * Hotspawn crowd pick percentages are recorded for audit only. They are NEVER
    an input to any probability, line, or pick.
  * A value that cannot be read from an official source is left blank and flagged.
  * Nothing is inferred.

Model (documented, reproducible):
  map win probability from Valve's own Glicko expected-win function, using the
  constants published in Valve's repository (model/glicko.js):
      Q = ln(10)/400          ("rank delta of 400 points = 90% chance of victory")
      g(rd) = 1/sqrt(1 + 3*Q^2*rd^2/pi^2),  rd = 75 (Valve's default)
      E     = 1 / (1 + 10 ** (-g*(rA - rB)/S))
  rA, rB are the teams' Valve Regional Standings points.  S is a single scale
  constant; Valve's 400 is the raw-Glicko value and is far too confident for the
  published (compressed) standings point column, so S is fitted - see
  calibrate() and the Method page for the fit, its cross-entropy and the caveat.
  Valve's own source line is: const Q = Math.log(10) / 400;  rd : 75
  series probability: Bo1 -> E ; Bo3 -> E^3 + 3*E^2*(1-E)
  The series format is taken from the EGamersWorld fixture (source on every row).
  Where no format is published, the series probability is left blank and flagged.

Run:  python3 scripts/8e782f95_build.py     (from the repository root)
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import math
import os
import re
import unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "8e782f95")
BOARD = os.path.join(ROOT, "board")

AS_OF_UTC = "2026-10-13 22:35 UTC"
NOW = dt.datetime(2026, 10, 13, 22, 35)

HOTSPAWN_PICKEMS = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
VRS_COMMIT = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"
VRS_FILE_URL = (
    "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
    + VRS_COMMIT
    + "/live/2026/standings_global_2026_10_05.md"
)
VRS_RAW_URL = (
    "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/"
    + VRS_COMMIT
    + "/live/2026/standings_global_2026_10_05.md"
)
VRS_GITHUB_URL = "https://github.com/ValveSoftware/counter-strike_regional_standings"

# ---------------------------------------------------------------------------
# Valve's Glicko expected-win function (constants from Valve's model/glicko.js)
# ---------------------------------------------------------------------------
G_Q = math.log(10) / 400.0
G_RD = 75.0
G_FACTOR = 1.0 / math.sqrt(1.0 + 3.0 * G_Q * G_Q * G_RD * G_RD / (math.pi ** 2))


def map_prob(points_a: float, points_b: float) -> float:
    """Valve's Glicko expected-win function with the calibrated scale SCALE."""
    return 1.0 / (1.0 + 10.0 ** (-G_FACTOR * (points_a - points_b) / SCALE))


# ---------------------------------------------------------------------------
# Scale calibration.
#
# Valve's glicko.js comment says "rank delta of 400 points = 90% chance of
# victory", i.e. a scale of 400.  Applied directly to the published Regional
# Standings point totals that is far too confident (it puts Legacy-PARIVISION,
# VRS #2 vs #36, at 99.7% for a Bo3 where the market is at 54.6%), because the
# standings point column is a compressed scale, not a raw Glicko rating.
#
# We therefore fit the single scale constant SCALE to the external market's
# implied per-map probabilities (inverse series transform of the de-vigged
# prices) on every fixture that has both a market line and two rated teams.
# This is a deterministic one-parameter fit; the in-sample and leave-one-out
# cross-entropy are published on the Method page.
#
# Consequence, stated openly: the own line is a market-calibrated rating model.
# It is used to produce a probability where no market line exists.  On rows that
# DO have a market line the market-vs-own difference is a consistency check,
# not an independent validation.
# ---------------------------------------------------------------------------
def _inv_series(ps: float, fmt: str) -> float:
    lo, hi = 0.0, 1.0
    for _ in range(200):
        m = (lo + hi) / 2.0
        v = m if fmt == "Bo1" else 3 * m * m - 2 * m ** 3
        if v < ps:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2.0


def _cross_entropy(scale: float, data) -> float:
    total = 0.0
    for d, pm, _fmt in data:
        p = 1.0 / (1.0 + 10.0 ** (-G_FACTOR * d / scale))
        p = min(max(p, 1e-9), 1 - 1e-9)
        total += -(pm * math.log(p) + (1 - pm) * math.log(1 - p))
    return total / len(data)


def _fit_scale(data, lo=100.0, hi=60000.0, step=1.01):
    best, best_v = lo, None
    s = lo
    while s < hi:
        v = _cross_entropy(s, data)
        if best_v is None or v < best_v:
            best, best_v = s, v
        s *= step
    return best, best_v


def calibrate(rows):
    """Fit SCALE on the rows that have both a market line and two VRS ratings."""
    data = []
    for r in rows:
        if (
            r["market_p_a"] is not None
            and r["vrs_a"] != ""
            and r["vrs_b"] != ""
            and r["format"]
        ):
            pm = _inv_series(r["market_p_a"], r["format"])
            data.append((float(r["vrs_a"]) - float(r["vrs_b"]), pm, r["format"]))
    if not data:
        return None
    scale, ce_in = _fit_scale(data)
    loo = []
    for i in range(len(data)):
        sub = data[:i] + data[i + 1:]
        s_i, _ = _fit_scale(sub)
        d, pm, _f = data[i]
        p = 1.0 / (1.0 + 10.0 ** (-G_FACTOR * d / s_i))
        p = min(max(p, 1e-9), 1 - 1e-9)
        loo.append(-(pm * math.log(p) + (1 - pm) * math.log(1 - p)))
    base = -sum(
        pm * math.log(pm) + (1 - pm) * math.log(1 - pm) for _d, pm, _f in data
    ) / len(data)
    return {
        "scale": scale,
        "n": len(data),
        "cross_entropy_in_sample": ce_in,
        "cross_entropy_leave_one_out": sum(loo) / len(loo),
        "market_self_entropy": base,
        "coin_flip_entropy": math.log(2),
    }


SCALE = 400.0  # replaced by calibrate() during the build
CALIB = None


def series_prob(p: float, fmt: str):
    """Bo1 -> p ; Bo3 -> p^3 + 3 p^2 (1-p).  Unknown format -> None."""
    if fmt == "Bo1":
        return p
    if fmt == "Bo3":
        return p ** 3 + 3.0 * p ** 2 * (1.0 - p)
    return None


def devig(odds_a: float, odds_b: float):
    """Proportional margin removal on a two-way price pair."""
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    total = ia + ib
    return ia / total, ib / total, total - 1.0


# ---------------------------------------------------------------------------
# Name -> Valve Regional Standings row.
# Only aliases that are evidenced by an opponent + kickoff match on an external
# esports-betting page (or by a named official HLTV roster) are admitted, and
# every admitted alias is published on the Flagged page for review.
# ---------------------------------------------------------------------------
ALIASES = {
    "WROTBERRY": (
        "WBT",
        "EGamersWorld lists this fixture as \"WBT\" at the same kickoff and against "
        "the same opponent (Elisa Esports BreakOut Series 2 event page)",
        "https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl",
    ),
    "RoundsGG": (
        "ROUNDS",
        "EGamersWorld lists this fixture as \"Rounds\" (logo file roundsgg-logo.webp) "
        "at the same kickoff and against the same opponent",
        "https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl",
    ),
    "Envy": (
        "3DMAX",
        "HLTV news 45594: \"Envy have announced their return to Counter-Strike with the "
        "signing of the ex-3DMAX roster\"; the Valve row 3DMAX carries that exact roster",
        "https://www.hltv.org/news/45594/envy-return-to-cs-with-ex-3dmax-roster",
    ),
}


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def load_vrs():
    path = os.path.join(DATA, "vrs_global_2026_10_05_extract.csv")
    rows = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows[_norm(r["team_name"])] = {
                "name": r["team_name"],
                "rank": int(r["vrs_rank"]),
                "points": int(r["vrs_points"]),
                "roster": r["roster"],
                "details": r["details_path"],
            }
    return rows


def vrs_url(row) -> str:
    # line 1 = title, 2 = <br/>, 3 = blank, 4 = table header, 5 = separator,
    # so standing N sits on line N + 5.
    return VRS_FILE_URL + "?plain=1#L" + str(row["rank"] + 5)


def resolve(team: str, vrs: dict):
    key = _norm(team)
    if key in vrs:
        return vrs[key], None
    if team in ALIASES:
        alias, why, url = ALIASES[team]
        akey = _norm(alias)
        if akey in vrs:
            row = dict(vrs[akey])
            row["alias_note"] = why
            row["alias_url"] = url
            return row, alias
    return None, None


FLAGS: list[dict] = []


def flag(code: str, severity: str, fixture: str, title: str, detail: str, sources: list):
    FLAGS.append(
        {
            "code": code,
            "severity": severity,
            "fixture": fixture,
            "title": title,
            "detail": detail,
            "sources": [s for s in sources if s],
        }
    )


def main() -> int:
    vrs = load_vrs()

    fixtures = list(csv.DictReader(open(os.path.join(DATA, "fixtures.csv"), newline="", encoding="utf-8")))
    lines = {}
    for r in csv.DictReader(open(os.path.join(DATA, "external_lines.csv"), newline="", encoding="utf-8")):
        key = (r["hotspawn_id"].strip(), _norm(r["team_a"]), _norm(r["team_b"]))
        lines[key] = r

    # ---- pass 0: market probabilities + ratings, then fit the scale --------
    global SCALE, CALIB
    pre = []
    for fx in fixtures:
        ta, tb = fx["team_a"], fx["team_b"]
        key = (fx["hotspawn_id"].strip(), _norm(ta), _norm(tb))
        ext = lines.get(key)
        m_pa = None
        if ext and ext["odds_a"].strip() and ext["odds_b"].strip():
            m_pa = devig(float(ext["odds_a"]), float(ext["odds_b"]))[0]
        ra0, _ = resolve(ta, vrs)
        rb0, _ = resolve(tb, vrs)
        pre.append(
            {
                "market_p_a": m_pa,
                "vrs_a": ra0["points"] if ra0 else "",
                "vrs_b": rb0["points"] if rb0 else "",
                "format": (ext or {}).get("format", "") or "",
            }
        )
    CALIB = calibrate(pre)
    if CALIB:
        SCALE = CALIB["scale"]

    out_rows = []
    for fx in fixtures:
        ta, tb = fx["team_a"], fx["team_b"]
        key = (fx["hotspawn_id"].strip(), _norm(ta), _norm(tb))
        ext = lines.get(key)

        # ---- external market line -----------------------------------------
        m_pa = m_pb = None
        margin = None
        odds_a = odds_b = None
        if ext and ext["odds_a"].strip() and ext["odds_b"].strip():
            odds_a, odds_b = float(ext["odds_a"]), float(ext["odds_b"])
            m_pa, m_pb, margin = devig(odds_a, odds_b)
            if m_pa is not None and abs((m_pa + m_pb) - 1.0) > 1e-9:  # pragma: no cover
                raise AssertionError("de-vigged pair does not sum to 1")

        # ---- own line from Valve's official standings ----------------------
        ra, alias_a = resolve(ta, vrs)
        rb, alias_b = resolve(tb, vrs)
        own_map = own_series = None
        fmt = (ext or {}).get("format", "") or ""
        if ra and rb:
            own_map = map_prob(ra["points"], rb["points"])
            own_series = series_prob(own_map, fmt)
        else:
            missing = [t for t, r in ((ta, ra), (tb, rb)) if not r]
            flag(
                "B-F-RATING",
                "unverified",
                f"{ta} vs {tb}",
                "No official rating for " + ", ".join(missing),
                "The team(s) do not appear in Valve's official Regional Standings file "
                "(standings_global_2026_10_05.md, 380 rows) and no evidenced alias was "
                "admitted. The own line is left blank rather than inferred.",
                [VRS_FILE_URL, fx["hotspawn_url"]],
            )

        if ra and ra.get("alias_note"):
            flag(
                "B-F-ALIAS",
                "needs review",
                f"{ta} vs {tb}",
                f"Name mapping: Hotspawn \"{ta}\" = Valve \"{ra['name']}\"",
                ra["alias_note"],
                [ra["alias_url"], VRS_FILE_URL],
            )
        if rb and rb.get("alias_note"):
            flag(
                "B-F-ALIAS",
                "needs review",
                f"{ta} vs {tb}",
                f"Name mapping: Hotspawn \"{tb}\" = Valve \"{rb['name']}\"",
                rb["alias_note"],
                [rb["alias_url"], VRS_FILE_URL],
            )

        # ---- pick ----------------------------------------------------------
        pick = pick_basis = None
        if m_pa is not None:
            pick = ta if m_pa >= m_pb else tb
            pick_basis = "external market line"
        elif own_series is not None:
            pick = ta if own_series >= 0.5 else tb
            pick_basis = "own model (Valve standings)"
        elif own_map is not None:
            pick = ta if own_map >= 0.5 else tb
            pick_basis = "own model (map probability; series format unverified)"
        if pick is None:
            flag(
                "B-F-NOPICK",
                "unverified",
                f"{ta} vs {tb}",
                "No pick published",
                "Neither an external bookmaker line nor an official rating pair could be "
                "verified for this fixture, so no probability and no pick are published.",
                [fx["hotspawn_url"]],
            )

        # ---- divergence ----------------------------------------------------
        divergence = None
        if m_pa is not None and own_series is not None:
            divergence = m_pa - own_series
            if abs(divergence) >= 0.10 and (m_pa >= 0.5) == (own_series >= 0.5):
                flag(
                    "B-F-GAP",
                    "needs review",
                    f"{ta} vs {tb}",
                    f"Market and own model differ by {abs(divergence)*100:.0f} percentage points",
                    f"De-vigged market gives {ta} {m_pa*100:.1f}% (series); our Valve-standings "
                    f"model gives {own_series*100:.1f}%. Both point the same way, but the gap is "
                    "large enough to be worth a manual look. The published pick follows the "
                    "external market line.",
                    [(ext or {}).get("source_url", ""), VRS_FILE_URL, fx["hotspawn_url"]],
                )
            if (m_pa >= 0.5) != (own_series >= 0.5):
                flag(
                    "B-F-DIVERGE",
                    "needs review",
                    f"{ta} vs {tb}",
                    "Market and own model disagree on the winner",
                    f"De-vigged market gives {ta} {m_pa*100:.1f}% (series); our Valve-standings "
                    f"model gives {own_series*100:.1f}%. The two point at different winners. "
                    "The published pick follows the external market line.",
                    [(ext or {}).get("source_url", ""), VRS_FILE_URL, fx["hotspawn_url"]],
                )

        lock = dt.datetime.strptime(fx["lock_utc"], "%Y-%m-%d %H:%M")
        actionable = "yes" if lock > NOW else "no"

        out_rows.append(
            {
                "hotspawn_id": fx["hotspawn_id"],
                "start_utc": fx["start_utc"],
                "lock_utc": fx["lock_utc"],
                "actionable": actionable,
                "tournament": fx["tournament"],
                "tier": fx["tier"],
                "points": fx["points"],
                "team_a": ta,
                "team_b": tb,
                "format": fmt or "",
                "format_source": (ext or {}).get("source_url", ""),
                "hotspawn_url": fx["hotspawn_url"],
                "ext_odds_a": odds_a,
                "ext_odds_b": odds_b,
                "ext_margin": margin,
                "ext_url": (ext or {}).get("source_url", ""),
                "ext_captured_utc": (ext or {}).get("captured_utc", ""),
                "market_p_a": m_pa,
                "market_p_b": m_pb,
                "vrs_a": ra["points"] if ra else "",
                "vrs_b": rb["points"] if rb else "",
                "vrs_rank_a": ra["rank"] if ra else "",
                "vrs_rank_b": rb["rank"] if rb else "",
                "own_map_p_a": own_map,
                "own_series_p_a": own_series,
                "pick": pick or "",
                "pick_basis": pick_basis or "",
                "divergence_pp": (divergence * 100.0) if divergence is not None else "",
                "crowd_pct_a_audit_only": fx["crowd_pct_a_audit_only"],
                "crowd_pct_b_audit_only": fx["crowd_pct_b_audit_only"],
                "status": fx["status"],
                "vrs_source": VRS_FILE_URL,
            }
        )

    # ------------------------------------------------------------------
    # Cross-cutting flags
    # ------------------------------------------------------------------
    flag(
        "B-S1",
        "needs review",
        "(all)",
        "Hotspawn filter counts do not match the listed slate",
        "At 22:04-22:08 UTC on 2026-10-13 the /cs2-pickems page header says \"68 matches this "
        "week\" while its own tournament filter says \"All tiers (89)\" and /lobby says "
        "\"All tiers (90)\"; only 30 CS2 fixtures carry a live \"Locks in\" countdown. The "
        "remaining ~59 rows are stale 2026-06-26..2026-07-10 fixtures that Hotspawn still "
        "reports as \"scheduled\". This board lists the 30 actionable fixtures.",
        [HOTSPAWN_PICKEMS, HOTSPAWN_LOBBY],
    )
    flag(
        "B-S2",
        "needs review",
        "(all)",
        "/lobby and /cs2-pickems render times in different time zones",
        "The same fixture is shown as \"Oct 14, 04:00\" on /lobby and \"Oct 14, 08:00\" on "
        "/cs2-pickems, while both pages show the identical \"Locks in 09:55:xx\" countdown. "
        "The countdown arithmetic (22:04:51 UTC + 9h55m = 08:00 UTC) shows /cs2-pickems "
        "renders UTC and /lobby renders UTC-4. This board publishes the countdown-derived "
        "UTC time; EGamersWorld independently shows the same kickoffs (UTC+2 display).",
        [HOTSPAWN_PICKEMS, HOTSPAWN_LOBBY],
    )
    flag(
        "B-S3",
        "needs review",
        "Gothic vs Lavked; Astralis vs Sashi; 9z vs Aurora",
        "EGamersWorld shows different prices on its event page and its match page",
        "Gothic-Lavked: event schedule 1.881/1.782 (22:27Z) vs match page 2.05/1.64 (22:12Z). "
        "Astralis-Sashi: event bets block 1.11/6.2 vs match page 1.07/6.41 (both 22:19Z). "
        "9z-Aurora: event bets block 3.75/1.25 vs event schedule 3.8/1.22. Only one price "
        "pair per fixture is published; the other is recorded here. All are the same "
        "bookmaker (bc.game) quoted by the same site minutes apart.",
        [
            "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK",
            "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
        ],
    )
    flag(
        "B-S4",
        "unverified",
        "ex-RUSTEC vs mellren; FORZE Reload vs LFO 10",
        "EGamersWorld placeholder price 1.80 / 1.80 treated as no line",
        "Both rows show the equal pair 1.80/1.80, which is EGamersWorld's placeholder when no "
        "bookmaker price is loaded (the FORZE Reload row also leaves the opponent unnamed). "
        "These are left blank here rather than converted into probabilities.",
        ["https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"],
    )
    flag(
        "B-S5",
        "needs review",
        "Voca vs Phantom",
        "Price pair 1.90 / 1.80 is close to EGamersWorld's 1.80 / 1.80 placeholder",
        "The pair is published because it is not the exact placeholder value, but it should be "
        "re-checked against a live bookmaker before it is relied on.",
        ["https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl"],
    )
    flag(
        "B-S6",
        "unverified",
        "CCT Europe 2026 Series #12 Play-In (4 fixtures)",
        "No external bookmaker line found for any CCT Europe Series #12 Play-In fixture",
        "No EGamersWorld page or price was captured for Enjoy-B8 Academy, Banda chuya-6666, "
        "Ryvex-PCIFIC or mellren-Privateer. Market probability is blank; the own Valve-"
        "standings map probability is published where both teams are rated.",
        [HOTSPAWN_PICKEMS],
    )
    flag(
        "B-S7",
        "needs review",
        "(all)",
        "Series format is not published by Hotspawn",
        "Hotspawn shows \"Stage: Waiting For Information\" and no map count. The Bo1/Bo3 "
        "format on every row is read from EGamersWorld and is linked on that row. Where "
        "EGamersWorld has no page, the series probability is blank and only the map "
        "probability is published.",
        [HOTSPAWN_PICKEMS],
    )
    flag(
        "B-S8",
        "needs review",
        "(all)",
        "Ratings snapshot is dated 2026-10-05, the fixture slate is 2026-10-13/16",
        "Valve publishes Regional Standings weekly; the newest file at capture time is "
        "standings_global_2026_10_05.md. Rosters may have changed since. Every row links "
        "the exact Valve file used.",
        [VRS_FILE_URL, VRS_GITHUB_URL],
    )

    flag(
        "B-S9",
        "needs review",
        "Legacy vs PARIVISION (and every row using the 2026-10-05 standings)",
        "The Valve standings snapshot predates a confirmed PARIVISION roster change",
        "Valve's official file standings_global_2026_10_05.md lists PARIVISION at #36 "
        "(1411 points) with the roster FL1T, Jame, slaxejezzz, xiELO, zweih. HLTV's team page "
        "shows the current roster as HObbit, FL1T, Jame, xiELO, zweih and records that "
        "\"after HObbit joined and slaxejezzz was benched on Sep 17\" the team's results "
        "changed. HLTV's own VRS widget puts PARIVISION at #11, not #36, and Legacy at #6 "
        "rather than Valve's #2. The rating we publish is the one Valve's official file "
        "states; the roster caveat is published here instead of being silently corrected.",
        [
            VRS_FILE_URL,
            "https://www.hltv.org/team/12467/parivision",
            "https://www.hltv.org/team/12468/legacy",
        ],
    )

    # ------------------------------------------------------------------
    # Write analysis.csv
    # ------------------------------------------------------------------
    cols = [
        "hotspawn_id", "start_utc", "lock_utc", "actionable", "tournament", "tier", "points",
        "team_a", "team_b", "format", "format_source", "hotspawn_url",
        "ext_odds_a", "ext_odds_b", "ext_margin", "ext_url", "ext_captured_utc",
        "market_p_a", "market_p_b",
        "vrs_rank_a", "vrs_a", "vrs_rank_b", "vrs_b",
        "own_map_p_a", "own_series_p_a",
        "pick", "pick_basis", "divergence_pp",
        "crowd_pct_a_audit_only", "crowd_pct_b_audit_only", "status", "vrs_source",
    ]
    with open(os.path.join(DATA, "analysis.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in out_rows:
            w.writerow(r)

    with open(os.path.join(DATA, "flags.json"), "w", encoding="utf-8") as fh:
        json.dump(FLAGS, fh, indent=2)

    # ------------------------------------------------------------------
    # Build board/**
    # ------------------------------------------------------------------
    build_site(out_rows, FLAGS)
    return 0


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#0f1420;--panel:#161d2c;--panel2:#1d2637;--line:#2a3547;--txt:#e8edf6;
--dim:#93a1b9;--acc:#4cc2ff;--good:#37d67a;--warn:#ffcc4d;--bad:#ff6b6b;--pick:#7c5cff}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--txt);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc)}
.wrap{max-width:1100px;margin:0 auto;padding:0 14px 60px}
header{background:linear-gradient(180deg,#131b2b,#0f1420);border-bottom:1px solid var(--line)}
header .wrap{padding-top:18px;padding-bottom:14px}
h1{font-size:22px;margin:0 0 6px}
.sub{color:var(--dim);font-size:13px;margin:0}
nav{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 0}
nav a{padding:7px 11px;border:1px solid var(--line);border-radius:8px;text-decoration:none;
color:var(--txt);font-size:13px;background:var(--panel)}
nav a.on{background:var(--acc);color:#08111c;border-color:var(--acc);font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
.card .k{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.card .v{font-size:24px;font-weight:800;margin-top:4px}
h2{font-size:18px;margin:26px 0 10px}
p{color:#c8d3e6}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);
border-radius:12px;overflow:hidden}
th,td{padding:9px 10px;text-align:left;border-bottom:1px solid var(--line);font-size:13px;
vertical-align:top}
th{background:var(--panel2);color:var(--dim);font-size:11px;text-transform:uppercase;
letter-spacing:.05em;white-space:nowrap}
tr:last-child td{border-bottom:none}
.tscroll{overflow-x:auto;-webkit-overflow-scrolling:touch;border-radius:12px}
.pick{font-weight:800;color:var(--pick)}
.bar{position:relative;height:22px;border-radius:6px;overflow:hidden;background:#2a3547;
min-width:120px}
.bar span{position:absolute;top:0;bottom:0;left:0;background:linear-gradient(90deg,#2f7fd6,#4cc2ff);
border-radius:6px}
.bar i{position:absolute;top:0;bottom:0;right:0;background:#3a4busy}
.bar em{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
font-style:normal;font-size:11px;font-weight:800;text-shadow:0 1px 2px rgba(0,0,0,.6)}
.dim{color:var(--dim)}
.stale{opacity:.5}
.tag{display:inline-block;padding:2px 7px;border-radius:999px;font-size:11px;font-weight:700}
.t-yes{background:#12341f;color:#5fe08f}
.t-no{background:#3a1c1c;color:#ff9b9b}
.tier{display:inline-block;width:20px;height:20px;line-height:20px;text-align:center;
border-radius:5px;font-weight:800;font-size:12px;background:#2a3547}
.tier-S{background:#4a2f7a;color:#d9c6ff}
.tier-B{background:#1f3a5f;color:#a8d5ff}
.tier-C{background:#333b2a;color:#c8dba0}
ul.src{font-size:13px}
ul.src li{margin-bottom:6px}
code{background:#0b1018;padding:1px 5px;border-radius:4px;font-size:12px}
footer{border-top:1px solid var(--line);margin-top:40px;padding:18px 0;color:var(--dim);font-size:12px}
.flag{border:1px solid var(--line);border-left:4px solid var(--warn);border-radius:10px;
padding:12px;margin-bottom:10px;background:var(--panel)}
.flag.unverified{border-left-color:var(--bad)}
.flag h3{margin:0 0 4px;font-size:14px}
.flag .m{color:var(--dim);font-size:12px;margin-bottom:6px}
@media(max-width:820px){
  h1{font-size:19px}
  th,td{font-size:12px;padding:8px 7px}
  .card .v{font-size:20px}
}
@media(max-width:720px){
  .tscroll{overflow:visible}
  table,tbody,tr,td{display:block;width:100%}
  thead{display:none}
  table{border:none;background:none}
  tr{background:var(--panel);border:1px solid var(--line);border-radius:12px;
     padding:10px 12px;margin:0 0 10px}
  tr.stale{opacity:.55}
  td{border:none;padding:4px 0;display:flex;align-items:baseline;
     justify-content:space-between;gap:12px;text-align:right}
  td::before{content:attr(data-label);color:var(--dim);font-size:12px;
     text-transform:uppercase;letter-spacing:.04em;flex:0 0 auto;text-align:left}
  td.match,td.pick{font-size:15px;font-weight:700}
  .bar{min-width:160px}
}
"""


def esc(x) -> str:
    return html.escape("" if x is None else str(x))


def pct(v, nd=1):
    if v is None or v == "":
        return '<span class="dim">&mdash;</span>'
    return f"{float(v)*100:.{nd}f}%"


def link(url, text=None):
    if not url:
        return ""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text or "source")}</a>'


def bar(pa, pb):
    if pa is None or pb is None:
        return '<span class="dim">no line</span>'
    a, b = float(pa) * 100, float(pb) * 100
    return (
        f'<div class="bar"><span style="width:{a:.1f}%"></span>'
        f'<em>{a:.0f}% / {b:.0f}%</em></div>'
    )


NAV = [
    ("index.html", "Picks"),
    ("all-matches.html", "All matches"),
    ("s-tier.html", "S-tier"),
    ("b-tier.html", "B-tier"),
    ("c-tier.html", "C-tier"),
    ("sources.html", "Sources"),
    ("method.html", "Method"),
    ("flagged.html", "Flagged"),
]


def page(title, body, active):
    nav = "".join(
        f'<a href="{u}" class="{"on" if u==active else ""}">{esc(t)}</a>' for u, t in NAV
    )
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} — Hotspawn Pick'em line board</title>
<style>{CSS}</style>
</head><body>
<header><div class="wrap">
<h1>Hotspawn Pick'em — CS2 line board</h1>
<p class="sub">Independent match probabilities from external bookmaker lines and our own Valve&nbsp;Regional&nbsp;Standings model.
Hotspawn crowd percentages are never used as probability. Data captured {esc(AS_OF_UTC)}.</p>
<nav>{nav}</nav>
</div></header>
<div class="wrap">
{body}
<footer>
Built by session <code>arena/8e782f95</code>. Analysis only, not betting advice.
Every row links the official page the value was read from; anything unconfirmed is left blank and listed on the
<a href="flagged.html">Flagged for Review</a> page.
</footer>
</div></body></html>
"""


def table_rows(rows, show_tournament=True):
    out = []
    for r in rows:
        cls = "" if r["actionable"] == "yes" else "stale"
        a = r["team_a"]
        b = r["team_b"]
        pick = r["pick"]
        pa = r["market_p_a"]
        pb = r["market_p_b"]
        if pa is None:
            # no market line: fall back to our own series probability, and if the
            # series format is not published, to the single-map probability.
            pa = r["own_series_p_a"]
            if pa is None:
                pa = r["own_map_p_a"]
            pb = (1 - pa) if pa is not None else None
        lock = r["lock_utc"][5:]
        series_known = bool(r["own_series_p_a"])
        cells = [
            f'<td data-label="Locks">{esc(lock)}Z</td>',
        ]
        if show_tournament:
            cells.append(f'<td data-label="Event">{esc(r["tournament"])}</td>')
        cells += [
            f'<td data-label="Tier"><span class="tier tier-{esc(r["tier"])}">{esc(r["tier"])}</span>'
            f'<span class="dim"> · {esc(r["points"])} pts</span></td>',
            f'<td class="match" data-label="Match">{esc(a)} <span class="dim">vs</span> {esc(b)}'
            f'<br><span class="dim">{esc(r["format"] or "format not published")}</span></td>',
            f'<td data-label="Win %">{bar(pa, pb)}'
            + ('' if series_known or not r["own_map_p_a"] else '<span class="dim"> (single map)</span>')
            + "</td>",
            f'<td data-label="Market">{pct(r["market_p_a"])}<br><span class="dim">'
            f"{esc(r['ext_odds_a'] or '')} / {esc(r['ext_odds_b'] or '')}</span></td>",
            f'<td data-label="Own model">{pct(r["own_series_p_a"])}'
            f'<br><span class="dim">map {pct(r["own_map_p_a"])}</span></td>',
            '<td class="pick" data-label="Pick">'
            + (esc(pick) if pick else '<span class="dim">no pick</span>')
            + ('<br><span class="dim">' + esc(r["pick_basis"]) + "</span>" if pick else "")
            + "</td>",
            f'<td data-label="Sources">{link(r["hotspawn_url"], "Hotspawn")}<br>'
            + (link(r["ext_url"], "EGW line") if r["ext_url"] else '<span class="dim">no market line</span>')
            + "<br>"
            + link(r["vrs_source"], "Valve VRS")
            + "</td>",
        ]
        out.append(f'<tr class="{cls}">{"".join(cells)}</tr>')
    return "".join(out)


HEAD = (
    "<th>Lock (UTC)</th>" + "<th>Tournament</th>" + "<th>Tier</th><th>Match</th>"
    "<th>Win probability</th><th>Market (de-vigged)</th><th>Own model (VRS)</th>"
    "<th>Pick</th><th>Sources</th>"
)


def matches_table(rows, show_tournament=True):
    if not rows:
        return '<p class="dim">No fixtures in this category.</p>'
    return (
        f'<div class="tscroll"><table><thead><tr>{HEAD if show_tournament else HEAD.replace("<th>Tournament</th>","")}'
        f"</tr></thead><tbody>{table_rows(rows, show_tournament)}</tbody></table></div>"
    )


def build_site(rows, flags):
    os.makedirs(os.path.join(BOARD, "data"), exist_ok=True)
    open(os.path.join(BOARD, ".nojekyll"), "w").close()
    with open(os.path.join(BOARD, "data", "analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(
            {
                "as_of_utc": AS_OF_UTC,
                "generated_by": "scripts/8e782f95_build.py",
                "vrs_commit": VRS_COMMIT,
                "glicko_g_factor": G_FACTOR,
                "scale_calibration": CALIB,
                "matches": rows,
                "flags": flags,
            },
            fh,
            indent=2,
        )
    with open(os.path.join(BOARD, "data", "analysis.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    open_rows = [r for r in rows if r["actionable"] == "yes"]
    priced = [r for r in rows if r["market_p_a"] is not None]
    picked = [r for r in open_rows if r["pick"]]
    own = [r for r in rows if r["own_series_p_a"] is not None or r["own_map_p_a"] is not None]

    # ---------------------------------------------------------------- index
    cards = (
        f'<div class="cards">'
        f'<div class="card"><div class="k">Actionable CS2 fixtures</div><div class="v">{len(open_rows)}</div></div>'
        f'<div class="card"><div class="k">With an external line</div><div class="v">{len(priced)}</div></div>'
        f'<div class="card"><div class="k">With our own line</div><div class="v">{len(own)}</div></div>'
        f'<div class="card"><div class="k">Picks published</div><div class="v">{len(picked)}</div></div>'
        f'<div class="card"><div class="k">Flagged items</div><div class="v">{len(flags)}</div></div>'
        f"</div>"
    )
    body = cards + f"""
<h2>Today's board — pick, probability and source on every row</h2>
<p>Only fixtures whose Hotspawn lock time has not passed are listed here. Probabilities come
from a de-vigged external bookmaker price pair where one exists, otherwise from our own
Valve&nbsp;Regional&nbsp;Standings model (clearly labelled). Hotspawn's own crowd percentages
are shown on the <a href="all-matches.html">all-matches</a> page as audit metadata only and are
never used to produce a number on this site.</p>
{matches_table(open_rows)}
<h2>How to read a row</h2>
<ul class="src">
<li><b>Market (de-vigged)</b> — the two-way bookmaker price pair read from EGamersWorld's
bc.game block, with the overround removed proportionally. Blank where no price was published.</li>
<li><b>Own model (VRS)</b> — our own line, computed from Valve's official Regional Standings
points with Valve's own Glicko expected-win function, then adjusted for the series format.
<a href="method.html">Full method</a>.</li>
<li><b>Pick</b> — the external market favourite where a line exists; otherwise the favourite by
our own model. Where neither exists, no pick is published.</li>
<li><b>Sources</b> — Hotspawn fixture, the exact EGamersWorld page the price was read from, and
the Valve standings file.</li>
</ul>
<h2>Other boards in this repository</h2>
<p class="dim">Parallel sessions published their own dashboards; they are linked here read-only and are
not re-verified by this session: <a href="../docs/">docs</a>, <a href="../pickem/">pickem</a>,
<a href="../model/">model (VRS)</a>, <a href="../picks/">picks</a>, <a href="../dashboard/">dashboard</a>,
<a href="../assurance/">assurance</a>.</p>
"""
    open(os.path.join(BOARD, "index.html"), "w", encoding="utf-8").write(
        page("Picks", body, "index.html")
    )

    # ------------------------------------------------------- all / tier pages
    def tier_page(name, t):
        sub = [r for r in rows if r["tier"] == t]
        return page(
            f"{t}-tier",
            f"<h2>{esc(t)}-tier fixtures ({len(sub)})</h2>"
            + matches_table(sub)
            + '<p class="dim">Greyed rows have already locked and are kept for transparency; they are not pickable.</p>',
            name,
        )

    open(os.path.join(BOARD, "all-matches.html"), "w", encoding="utf-8").write(
        page(
            "All matches",
            "<h2>Every fixture on the current CS2 pick'em slate</h2>"
            + matches_table(rows)
            + "<h2>Hotspawn crowd pick percentages (audit only)</h2>"
            + '<div class="tscroll"><table><thead><tr><th>Match</th><th>Hotspawn crowd %% team A</th>'
            "<th>Hotspawn crowd %% team B</th><th>Our pick</th><th>Hotspawn page</th></tr></thead><tbody>"
            + "".join(
                f'<tr><td>{esc(r["team_a"])} vs {esc(r["team_b"])}</td>'
                f'<td class="dim">{esc(r["crowd_pct_a_audit_only"])}%</td>'
                f'<td class="dim">{esc(r["crowd_pct_b_audit_only"])}%</td>'
                f'<td class="pick">{esc(r["pick"] or "no pick")}</td>'
                f'<td>{link(r["hotspawn_url"], "Hotspawn")}</td></tr>'
                for r in rows
            )
            + "</tbody></table></div>"
            + '<p class="dim">These crowd percentages are published as evidence only. They are inputs to '
            "nothing on this site — no probability, line or pick on any page uses them.</p>",
            "all-matches.html",
        )
    )
    for t, f in (("S", "s-tier.html"), ("B", "b-tier.html"), ("C", "c-tier.html")):
        open(os.path.join(BOARD, f), "w", encoding="utf-8").write(tier_page(f, t))

    # ------------------------------------------------------------- sources
    src_rows = []
    seen = set()
    for r in rows:
        for u, lbl in ((r["hotspawn_url"], "Hotspawn fixture"), (r["ext_url"], "External line")):
            if u and u not in seen:
                seen.add(u)
                src_rows.append((r, u, lbl))
    body = f"""
<h2>Primary sources used on every row</h2>
<ul class="src">
<li><b>Fixture identity, lock time, tier, points</b> —
<a href="{HOTSPAWN_PICKEMS}" target="_blank" rel="noopener">play.hotspawn.com/cs2-pickems</a> and
<a href="{HOTSPAWN_LOBBY}" target="_blank" rel="noopener">play.hotspawn.com/lobby</a>, read {esc(AS_OF_UTC)}.
Hotspawn is used only to say which matches are pickable, never as a probability.</li>
<li><b>External match-winner prices</b> — EGamersWorld's bookmaker block (bookmaker: bc.game),
one URL per priced fixture, each with its capture time. Listed below.</li>
<li><b>Our own line</b> — Valve Regional Standings, official file
<a href="{VRS_FILE_URL}" target="_blank" rel="noopener">live/2026/standings_global_2026_10_05.md</a>
at pinned commit <code>{VRS_COMMIT}</code>
(sha256 <code>df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b</code>),
with the expected-win constants from Valve's own
<a href="https://github.com/ValveSoftware/counter-strike_regional_standings/blob/{VRS_COMMIT}/model/glicko.js"
target="_blank" rel="noopener">model/glicko.js</a>.</li>
</ul>
<h2>Every URL used</h2>
<div class="tscroll"><table><thead><tr><th>Fixture</th><th>What it is</th><th>URL</th><th>Captured (UTC)</th></tr></thead><tbody>
{''.join(
    f'<tr><td>{esc(r["team_a"])} vs {esc(r["team_b"])}</td><td>{esc(lbl)}</td>'
    f'<td>{link(u, u)}</td>'
    f'<td class="dim">{esc(r["ext_captured_utc"] if lbl=="External line" else "2026-10-13T22:05Z")}</td></tr>'
    for r, u, lbl in src_rows
)}
</tbody></table></div>
<h2>Raw data</h2>
<ul class="src">
<li><a href="data/analysis.csv">board/data/analysis.csv</a> — one verified row per fixture</li>
<li><a href="data/analysis.json">board/data/analysis.json</a> — the same data as JSON</li>
<li><code>data/8e782f95/fixtures.csv</code>, <code>external_lines.csv</code>,
<code>vrs_global_2026_10_05.md</code> in the repository</li>
</ul>
"""
    open(os.path.join(BOARD, "sources.html"), "w", encoding="utf-8").write(
        page("Sources", body, "sources.html")
    )

    c = CALIB or {}
    cal = {
        "n": c.get("n", 0),
        "scale": "%.0f" % c.get("scale", 0),
        "ce_in": "%.4f" % c.get("cross_entropy_in_sample", 0),
        "ce_loo": "%.4f" % c.get("cross_entropy_leave_one_out", 0),
        "ce_mkt": "%.4f" % c.get("market_self_entropy", 0),
        "ce_coin": "%.4f" % c.get("coin_flip_entropy", 0),
    }
    # -------------------------------------------------------------- method
    body = f"""
<h2>Where each number comes from</h2>
<h3>1. The match list</h3>
<p>The slate is read from the official Hotspawn pick'em pages. Only fixtures that still show a
"Locks in" countdown are treated as pickable. Times are stated in UTC: the page's own countdown
is subtracted from the fetch time to confirm the offset, and EGamersWorld independently lists
the same kickoffs.</p>
<h3>2. Market probability (external bookmaker line)</h3>
<p>For a two-way decimal price pair <code>(oA, oB)</code> the overround is removed
proportionally:</p>
<p><code>pA = (1/oA) / (1/oA + 1/oB)</code>, <code>pB = 1 - pA</code>,
<code>margin = 1/oA + 1/oB - 1</code>.</p>
<p>The margin is published on every row so the size of the bookmaker's edge is visible.
Prices are read from EGamersWorld's bc.game block. Where EGamersWorld shows its equal
placeholder pair (1.80 / 1.80) the row is left blank, not converted.</p>
<h3>3. Our own line (Valve Regional Standings)</h3>
<p>Each team's rating is its points total in Valve's official Regional Standings file
<code>live/2026/standings_global_2026_10_05.md</code> (380 rows, pinned commit
<code>{VRS_COMMIT}</code>, sha256
<code>df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b</code>). The map win
probability uses Valve's own published Glicko expected-win function, with the constants taken
from Valve's repository <code>model/glicko.js</code>: <code>Q = ln(10)/400</code> and
<code>g = 1/sqrt(1 + 3·Q²·rd²/π²)</code> with Valve's default <code>rd = 75</code>, giving
<code>g = {G_FACTOR:.6f}</code>:</p>
<p><code>E = 1 / (1 + 10^(-g·(rA - rB)/S))</code></p>
<p><b>The scale constant S.</b> Valve's source comment says "rank delta of 400 points = 90%
chance of victory", i.e. S = 400. Applied directly to the published standings point totals that
is far too confident — it puts Legacy (VRS #2) over PARIVISION (VRS #36) at 99.7% for a Bo3
where the bookmaker line is at 54.6%. The standings point column is a compressed scale, not a
raw Glicko rating. We therefore fit S by minimising cross-entropy against the external market's
implied per-map probabilities on every fixture that has both a market line and two rated teams
({cal['n']} fixtures). The fit is a deterministic one-parameter grid search:</p>
<p><code>S = {cal['scale']}</code> ·
in-sample cross-entropy <code>{cal['ce_in']}</code> ·
leave-one-out cross-entropy <code>{cal['ce_loo']}</code> ·
the market's own entropy on the same rows <code>{cal['ce_mkt']}</code> ·
a coin flip scores <code>{cal['ce_coin']}</code>.</p>
<p><b>What that means, stated openly.</b> The own line is a market-calibrated rating model. It
is used to produce a probability where no bookmaker line exists. On rows that <i>do</i> have a
market line, the market-versus-own difference is a consistency check, not an independent
validation — the two are not independent of each other.</p>
<p>The series probability is <code>E</code> for a Bo1 and
<code>E³ + 3·E²·(1-E)</code> for a Bo3. The format is read from the EGamersWorld fixture and
linked on that row; where no format is published, only the map probability is shown and the
row is flagged.</p>
<p>A team with no row in Valve's file gets no rating and no own line — the value is left blank
and flagged, never estimated. Name mappings between Hotspawn and Valve are only admitted with
evidence (identical opponent plus identical kickoff on an external page, or a named official
roster) and every one of them is listed on the <a href="flagged.html">Flagged</a> page.</p>
<h3>4. The pick</h3>
<p>External market line first; our own model only where no external line exists (labelled on the
row); no pick where neither exists. Where the market and our model disagree on the winner, the
row is flagged and the market pick is published.</p>
<h3>5. What is never used</h3>
<p>Hotspawn's crowd pick percentages are recorded on the all-matches page as audit metadata and
appear in no calculation anywhere on this site.</p>
<h3>Reproduce</h3>
<p><code>python3 scripts/8e782f95_build.py</code> regenerates every page from
<code>data/8e782f95/</code>. <code>python3 -m unittest tests.test_8e782f95 -v</code> checks the
math, the source links and the blank-value rules.</p>
"""
    open(os.path.join(BOARD, "method.html"), "w", encoding="utf-8").write(
        page("Method", body, "method.html")
    )

    # ------------------------------------------------------------- flagged
    seen_codes = {}
    body = "<h2>Flagged for review</h2><p>Everything below is published rather than silently fixed. None of it blocks publication; each item links the source it was checked against.</p>"
    for f in flags:
        seen_codes[f["code"]] = seen_codes.get(f["code"], 0) + 1
        body += (
            f'<div class="flag {esc(f["severity"].replace(" ", "-"))}">'
            f'<h3>{esc(f["code"])} — {esc(f["title"])}</h3>'
            f'<div class="m">{esc(f["fixture"])} · {esc(f["severity"])}</div>'
            f"<p>{esc(f['detail'])}</p>"
            + (
                '<p class="dim">Sources: '
                + " · ".join(link(u, u) for u in f["sources"])
                + "</p>"
                if f["sources"]
                else ""
            )
            + "</div>"
        )
    body += (
        '<h2>Irregularities noted in other sessions\' published data</h2>'
        '<p class="dim">Read-only, for manual review. This session did not edit those files.</p>'
        "<ul class=\"src\">"
        "<li>Root <code>index.html</code>, <code>docs/</code>, <code>pickem/</code>, "
        "<code>dashboard/</code>, <code>picks/</code> and <code>model/</code> each publish a "
        "different slate size (26, 86, 380, 258, 30). They are separate snapshots taken at "
        "different times, not one reconciled set.</li>"
        "<li><code>docs/verified-lines.html</code> contains an unescaped literal "
        "<code>&lt;script id='ng-state'&gt;</code> in visible copy, which breaks three in-page "
        "anchors (<code>#F-28</code>, <code>#F-29</code>, <code>#flagged-audit</code>). "
        "Reported by session <code>3d05c62d</code>; not fixed here (out of scope).</li>"
        "<li>Several stored price sets carry capture timestamps later than the commit that "
        "publishes them (reported as <code>IR-91-15</code> / <code>SA-01</code>). Every "
        "timestamp on this board is a capture time recorded in this session.</li>"
        "<li>The <code>vrs_rank</code> column of <code>data/6d9c321d/team_ratings_verified.csv</code> "
        "matches HLTV's own VRS widget, not Valve's published file (reported as "
        "<code>IR-91-12</code>). This board reads Valve's file directly.</li>"
        "<li><code>.github/workflows/update.yml</code> is configured with a "
        "<code>17,47 * * * *</code> cron but GitHub reported zero scheduled runs up to 21:28 UTC "
        "(reported by <code>3d05c62d</code> and <code>366849f7</code>).</li>"
        "</ul>"
    )
    open(os.path.join(BOARD, "flagged.html"), "w", encoding="utf-8").write(
        page("Flagged", body, "flagged.html")
    )


if __name__ == "__main__":
    raise SystemExit(main())
