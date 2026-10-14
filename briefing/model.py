#!/usr/bin/env python3
"""Probability maths for the briefing board (session arena/198cf31e).

Everything here is pure and testable.  No network, no wall clock except where a timestamp is
passed in.

Rules that never bend:
  * Hotspawn crowd pick percentages are not an input anywhere in this module.
  * A probability is only produced from a price that was actually read, or from an official
    rating file.  Nothing is inferred to fill a gap.
  * De-vigging is the standard two-way proportional method; the overround is always published
    next to the probability it produced.
"""
from __future__ import annotations

import math
import re
import unicodedata

# ----------------------------------------------------------------------------- names
_NOISE = re.compile(r"\b(e-?sports|esports|gaming|gamers|team|club|organization|org)\b")


def norm(name: str) -> str:
    """Normalised comparison key: lowercase, accent-stripped, alphanumeric only."""
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def core_key(name: str) -> str:
    """Normalised key with the interchangeable corporate suffixes removed.

    Used only to *propose* a match; every non-exact match is flagged (FL-NAME-FUZZY) on the
    published row so it can be checked by hand.
    """
    base = str(name or "")
    stripped = _NOISE.sub(" ", base)
    stripped = re.sub(r"\b(gg|gc)\b", " ", stripped, flags=re.I)
    if norm(stripped):
        return norm(stripped)
    return norm(base)


def names_match(a: str, b: str) -> tuple[bool, bool]:
    """Return (matched, exact).  `exact` False means the join is fuzzy and must be flagged."""
    ka, kb = norm(a), norm(b)
    if ka and ka == kb:
        return True, True
    ca, cb = core_key(a), core_key(b)
    if ca and ca == cb:
        return True, False
    return False, False


# Verified aliases.  Every entry carries the official page where the identity was checked.
# An alias is only ever used when that evidence link is published alongside the row.
ALIASES: dict[str, tuple[str, str]] = {
    # hotspawn name -> (canonical name on outside sources, evidence URL)
    "wrotberry": ("WBT", "https://www.hltv.org/match/2399418/wbt-vs-ence-elisa-breakout-series-2"),
    "roundsgg": ("RoundsGG", "https://bo3.gg/matches"),
    "ex-keyd": ("Keyd Stars", "https://www.hltv.org/team/11798/keyd-stars"),
    "ninjasinpyjamas": ("Ninjas in Pyjamas", "https://www.hltv.org/team/4411/ninjas-in-pyjamas"),
    "9z": ("9z Team", "https://www.hltv.org/team/7285/9z-team"),
    "aurora": ("Aurora Gaming", "https://www.hltv.org/team/11861/aurora-gaming"),
    "betboom": ("BetBoom Team", "https://www.hltv.org/team/11553/betboom-team"),
    "saw": ("SAW", "https://www.hltv.org/team/10567/saw"),
    "mibr": ("MIBR", "https://www.hltv.org/team/9215/mibr"),
    "furia": ("FURIA", "https://www.hltv.org/team/8297/furia"),
    "painacademy": ("paiN Academy", "https://www.hltv.org/team/12511/pain-academy"),
    "mibracademy": ("MIBR Academy", "https://www.hltv.org/team/12512/mibr-academy"),
}


def resolve_alias(name: str) -> tuple[str, str]:
    """Map a Hotspawn name to its outside-source name. Returns (name, evidence_url)."""
    key = norm(name)
    if key in ALIASES:
        return ALIASES[key]
    return name, ""


# ----------------------------------------------------------------------------- identity
# Hotspawn names that the official Valve file either does not contain, or contains more than
# once.  Each entry was checked by hand against the official page named in `evidence` during
# session arena/198cf31e, and each carries `why` so a reviewer can re-check the reasoning
# without re-doing the research.  `origin` says which official source the points come from.
VERIFIED_IDENTITIES: dict[str, dict] = {
    "exrustec": {
        "points": 1066, "rank": 92, "origin": "Valve",
        "as": "ex-RUSTEC (Valve global #92)",
        "why": "The Valve file lists two different teams called ex-RUSTEC. HLTV's CCT 2026 "
               "Europe Series 11 page shows ex-RUSTEC at VRS #93 with shalfey, Brilliance and "
               "youka, which is the #92 roster (Brilliance, glowiing, shalfey, yiksrezo, "
               "youka); the #152 roster has none of shalfey, glowiing or yiksrezo.",
        "evidence": "https://www.hltv.org/events/9442/cct-2026-europe-series-11"},
    "6666": {
        "points": 923, "rank": 127, "origin": "Valve",
        "as": "6666 (Valve global #127)",
        "why": "Two teams called 6666 in the Valve file. HLTV's CCT 2026 Europe Series 11 "
               "Closed Qualifier page shows 6666 at VRS #127 with amster, kL1o, rendysky and "
               "skcH - exactly the #127 roster. The #368 roster (auth0ri, m4d4ra, rickangel, "
               "skcH) matches none of those four.",
        "evidence": "https://www.hltv.org/events/9441/cct-2026-europe-series-11-closed-qualifier"},
    "bandachuya": {
        "points": 801, "rank": 165, "origin": "Valve",
        "as": "Banda Chuya (Valve global #165)",
        "why": "Two teams called Banda Chuya in the Valve file. HLTV's CCT 2026 Europe Series "
               "11 Closed Qualifier page shows Banda Chuya at HLTV #161 with tomiko, maaryy, "
               "AdrieN, ezox and Showk - the complete #165 roster. The #373 entry lists only "
               "two players (ezox, manio).",
        "evidence": "https://www.hltv.org/events/9441/cct-2026-europe-series-11-closed-qualifier"},
    "envy": {
        "points": 1500, "rank": 21, "origin": "Valve",
        "as": "3DMAX / Envy (Valve global #21)",
        "why": "Envy is not in the Valve 2026-10-05 file under that name: HLTV reported on "
               "2026-09-29 that Envy signed the ex-3DMAX roster (Maka, Lucky, misutaaa, Kursy, "
               "Graviti), which is exactly the Valve entry '3DMAX' dated before the rename.",
        "evidence": "https://www.hltv.org/news/45594/envy-return-to-cs-with-ex-3dmax-roster"},
    "lfo10": {
        "points": 771, "rank": 168, "origin": "HLTV",
        "as": "LFO 10 (HLTV Valve ranking 2026-10-10 #168)",
        "why": "LFO 10 is absent from the Valve 2026-10-05 global file (only LFO 7/8/9 are "
               "there). HLTV's own Valve ranking page for 2026-10-10 publishes it at #168 with "
               "771 Valve points, roster dottie / flaw / Sapec.",
        "evidence": "https://www.hltv.org/valve-ranking/teams/2026/october/10"},
    "roundsgg": {
        "points": 548, "rank": 310, "origin": "Valve",
        "as": "ROUNDS (Valve global #310)",
        "why": "No 'RoundsGG' in the Valve file. HLTV's team page for ROUNDS (id 12457, Finnish) "
               "lists ykis, Monoxx, Kollo, Lapa and Tumppis - the complete Valve 'ROUNDS' "
               "roster (Kollo, Lapa, Monoxx, Tumppis, ykis). rounds.gg is the organisation's "
               "own site and writes the team name as ROUNDS.",
        "evidence": "https://www.hltv.org/team/12457/rounds"},
}


def verified_identity(name: str) -> dict | None:
    return VERIFIED_IDENTITIES.get(norm(name))


# ----------------------------------------------------------------------------- odds
def american_to_decimal(american: float) -> float:
    """Pinnacle publishes American prices; convert exactly, never round for storage."""
    a = float(american)
    if a > 0:
        return 1.0 + a / 100.0
    if a < 0:
        return 1.0 + 100.0 / abs(a)
    raise ValueError("american price 0 is not a price")


def american_to_prob(american: float) -> float:
    a = float(american)
    if a > 0:
        return 100.0 / (a + 100.0)
    if a < 0:
        return abs(a) / (abs(a) + 100.0)
    raise ValueError("american price 0 is not a price")


def devig(price_a: float, price_b: float) -> tuple[float, float, float]:
    """Two-way proportional de-vig.

    Returns (p_a, p_b, overround).  p_a + p_b == 1.0 by construction; overround is the
    bookmaker's margin (1 / sum of implied probabilities - 1), published next to every
    market-derived probability so the reader can see how much was removed.
    """
    ia, ib = 1.0 / float(price_a), 1.0 / float(price_b)
    total = ia + ib
    return ia / total, ib / total, total - 1.0


def fair_odds(p: float) -> float:
    return 1.0 / p if p > 0 else float("inf")


# ----------------------------------------------------------------------------- series
def series_prob(map_p: float, best_of: int | None) -> float | None:
    """P(win a best-of-n series) from P(win one map), independent maps.

    best_of None or 1 -> the single-map probability itself.
    """
    if best_of is None or best_of <= 1:
        return map_p
    p = min(max(map_p, 0.0), 1.0)
    if best_of == 3:
        return p * p * (3.0 - 2.0 * p)
    if best_of == 5:
        return p ** 3 * (10.0 - 15.0 * p + 6.0 * p * p)
    # general best-of-n: first to ceil(n/2)
    need = (best_of + 1) // 2
    total = 0.0
    for lost in range(0, need):
        maps = need + lost
        total += math.comb(best_of, lost) * (p ** (need - 1)) * ((1 - p) ** lost) * p
    return total


def best_of_from_bo(bo_type) -> int | None:
    try:
        v = int(bo_type)
    except (TypeError, ValueError):
        return None
    return v if v in (1, 3, 5) else None


# ----------------------------------------------------------------------------- our lines
# Fallback only. Used when too few market-priced fixtures exist to fit the scale; the board
# then labels every model line as uncalibrated. Never presented as a calibrated result.
DEFAULT_SCALE = 400.0


def map_prob_from_rating(points_a: float, points_b: float, scale: float) -> float:
    """Logistic on the official Valve Regional Standings points difference.

    `scale` is the number of rating points that buys a 10:1 map-win odds ratio. It is fitted
    in-sample against market prices (see calibrate_scale) and published with the fit.
    This is OUR model, not Valve's official forecast formula.
    """
    return 1.0 / (1.0 + 10.0 ** (-(float(points_a) - float(points_b)) / float(scale)))


def calibrate_scale(pairs: list[tuple[float, float, float]],
                    lo: float = 50.0, hi: float = 2000.0) -> dict:
    """Fit `scale` so our rating line tracks observed market-implied probabilities.

    pairs: (points_a, points_b, market_implied_p_a) for every fixture where BOTH an outside
    price and official ratings for both teams exist.  Least squares on a log-spaced grid, then
    a golden-section refine.  Returns the fit diagnostics so they can be published; an empty
    or one-point fit is reported as uncalibrated instead of silently defaulting.
    """
    if len(pairs) < 3:
        # No fit is possible, so the DEFAULT_SCALE below is used and the board says so.
        return {"ok": False, "n": len(pairs), "scale": DEFAULT_SCALE,
                "rmse_pp": None, "max_abs_error_pp": None,
                "note": f"only {len(pairs)} market-priced fixture(s) with two officially rated "
                        f"teams, so the scale could not be fitted this run; the board falls "
                        f"back to the default {DEFAULT_SCALE:.0f}-point logistic scale and "
                        f"labels every model line as uncalibrated"}

    def sse(k: float) -> float:
        return sum((map_prob_from_rating(a, b, k) - p) ** 2 for a, b, p in pairs)

    best_k, best_v = None, float("inf")
    steps = 240
    for i in range(steps + 1):
        k = lo * (hi / lo) ** (i / steps)
        v = sse(k)
        if v < best_v:
            best_k, best_v = k, v
    # golden-section refine around the grid winner
    a, b = max(lo, best_k / 1.2), min(hi, best_k * 1.2)
    gr = (math.sqrt(5.0) - 1.0) / 2.0
    for _ in range(80):
        c, d = b - gr * (b - a), a + gr * (b - a)
        if sse(c) < sse(d):
            b = d
        else:
            a = c
    k = (a + b) / 2.0
    resid = [map_prob_from_rating(x, y, k) - p for x, y, p in pairs]
    rmse = math.sqrt(sum(r * r for r in resid) / len(resid))
    worst = max(abs(r) for r in resid)
    return {"ok": True, "n": len(pairs), "scale": round(k, 1), "rmse_pp": round(rmse * 100, 2),
            "max_abs_error_pp": round(worst * 100, 2),
            "note": "least-squares fit of our logistic rating scale against the de-vigged "
                    "outside market prices read in this run (in-sample)"}
