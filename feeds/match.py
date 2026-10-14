#!/usr/bin/env python3
"""Pure, offline-testable logic for the secondary-market feed (session arena/a0bdf924).

Nothing in this module touches the network.  ``feeds/collect.py`` archives the raw (trimmed)
responses; ``feeds/join.py`` calls the functions below on those archives, so every published
number can be re-derived from committed bytes by ``feeds/tests.py``.

Rules (also printed on feeds/method.html):

* Hotspawn is used ONLY for fixture identity, kickoff and lock time.  Its crowd pick
  percentages are never read by this module.
* A source quote is attached to a Hotspawn fixture only when
    - at least one team name is an exact match (after the normalisation below, or through an
      evidence-linked alias in feeds/aliases.json), AND
    - the other team is exact (kickoff within 60 minutes) or a recognisable variant of the same
      name — substring or initials — with the kickoff within 15 minutes.
  Anything else is reported as a conflict / candidate and is never used.
* Bookmaker decimal odds are de-vigged multiplicatively (p_i = (1/o_i) / sum_j 1/o_j).
  Polymarket prices are already probabilities of complementary outcomes; they are normalised
  to sum to 1 and their quality gates (spread, depth, degenerate quotes) are applied.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone

EXACT_WINDOW_MIN = 60      # both names exact
VARIANT_WINDOW_MIN = 15    # one exact + one variant name
CANDIDATE_WINDOW_MIN = 360  # reported for review only

PM_MAX_SPREAD = 0.10       # Polymarket shows last trade instead of midpoint above this spread
PM_MIN_LIQUIDITY = 100.0   # USD resting in the match-winner book
BOOK_MAX_OVERROUND = 0.20  # a two-way book above 20 % margin is treated as invalid

_LEAD_DROP = {"team"}
_TRAIL_DROP = {"esports", "esport", "gaming", "team", "club", "clan"}


# ----------------------------------------------------------------------------- time helpers
def parse_time(value) -> datetime | None:
    """Accepts ISO strings ('...Z', '+00:00', '+00'), 'YYYY-MM-DD HH:MM:SS+00' and ms epochs."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        digits = str(int(float(value)))
        if len(digits) == 13:
            return datetime.fromtimestamp(int(digits) / 1000, timezone.utc).replace(microsecond=0)
        if len(digits) == 10:
            return datetime.fromtimestamp(int(digits), timezone.utc)
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    if re.search(r"[+-]\d\d$", text):          # '+00' -> '+00:00'
        text += ":00"
    text = text.replace(" ", "T", 1) if re.match(r"\d{4}-\d\d-\d\d \d", text) else text
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.\d+)?([+-]\d\d:\d\d)?$", text)
        if not m:
            return None
        dt = datetime.fromisoformat(m.group(1) + (m.group(2) or "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).replace(microsecond=0)


def iso(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def minutes_apart(a: datetime | None, b: datetime | None) -> float | None:
    if not a or not b:
        return None
    return abs((a - b).total_seconds()) / 60.0


# ----------------------------------------------------------------------------- names
def norm_name(name: str | None) -> str:
    """Case/accents/punctuation-insensitive key; drops generic org words at the ends only.

    'Team Falcons' -> 'falcons', 'BC.Game Esports' -> 'bcgame', 'Aurora Gaming' -> 'aurora',
    'Sökerorg' -> 'sokerorg'.  Words that change identity ('Academy', 'Reload', 'Junior',
    'Fe', numbers) are kept, so 'B8' and 'B8 Academy' never collapse into one key.
    """
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    s = s.replace("&", " and ")
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    while len(tokens) > 1 and tokens[0] in _LEAD_DROP:
        tokens = tokens[1:]
    while len(tokens) > 1 and tokens[-1] in _TRAIL_DROP:
        tokens = tokens[:-1]
    if len(tokens) > 1 and tokens[-2:] == ["e", "sports"]:
        tokens = tokens[:-2] or tokens
    return "".join(tokens)


def _initials(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    return "".join(t[0] for t in tokens) if len(tokens) >= 2 else ""


class Aliases:
    """Evidence-linked equivalence groups from feeds/aliases.json."""

    def __init__(self, groups: list[dict] | None = None):
        self.groups = groups or []
        self._key_to_group: dict[str, int] = {}
        for idx, grp in enumerate(self.groups):
            for nm in grp.get("names", []):
                self._key_to_group[norm_name(nm)] = idx

    @classmethod
    def load(cls, path) -> "Aliases":
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
        return cls(data.get("groups", []))

    def same(self, a: str, b: str) -> dict | None:
        ga = self._key_to_group.get(norm_name(a))
        gb = self._key_to_group.get(norm_name(b))
        if ga is not None and ga == gb:
            return self.groups[ga]
        return None


def name_relation(a: str, b: str, aliases: Aliases | None = None) -> tuple[str, str]:
    """Returns (kind, note) with kind in {'exact', 'alias', 'variant', 'different'}."""
    na, nb = norm_name(a), norm_name(b)
    if not na or not nb:
        return "different", "blank name"
    if na == nb:
        return "exact", ""
    if aliases:
        grp = aliases.same(a, b)
        if grp:
            return "alias", grp.get("evidence_url", "")
    short, long_ = sorted((na, nb), key=len)
    if len(short) >= 3 and short in long_:
        return "variant", f"'{short}' is contained in '{long_}'"
    ia, ib = _initials(a), _initials(b)
    if (ia and ia == nb) or (ib and ib == na):
        return "variant", "initials"
    return "different", ""


# ----------------------------------------------------------------------------- prices
def devig_decimal(odds_a, odds_b) -> dict | None:
    try:
        oa, ob = float(odds_a), float(odds_b)
    except (TypeError, ValueError):
        return None
    if oa <= 1.0 or ob <= 1.0:
        return None
    ia, ib = 1.0 / oa, 1.0 / ob
    total = ia + ib
    return {"implied_a": ia, "implied_b": ib, "overround": total - 1.0,
            "p_a": ia / total, "p_b": ib / total}


def normalise_pair(price_a, price_b) -> dict | None:
    try:
        pa, pb = float(price_a), float(price_b)
    except (TypeError, ValueError):
        return None
    if pa < 0 or pb < 0 or pa + pb <= 0:
        return None
    total = pa + pb
    return {"implied_a": pa, "implied_b": pb, "overround": total - 1.0,
            "p_a": pa / total, "p_b": pb / total}


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    try:
        out = json.loads(value or "[]")
        return out if isinstance(out, list) else []
    except (TypeError, ValueError):
        return []


def _num(value) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def format_from_text(text: str | None) -> int | None:
    m = re.search(r"\bBO\s*([1-7])\b", str(text or ""), re.I)
    return int(m.group(1)) if m else None


# ----------------------------------------------------------------------------- Polymarket
def polymarket_quote(event: dict) -> dict:
    """Extract the match-winner (moneyline) quote from one Gamma API event.

    Returns a dict with 'ok' (bool) and either the quote fields or a 'reject' reason.
    """
    out: dict = {"source": "Polymarket", "book": "Polymarket (prediction market)",
                 "event_id": str(event.get("id") or ""), "slug": event.get("slug") or "",
                 "title": event.get("title") or "", "ok": False}
    out["source_url"] = f"https://polymarket.com/event/{out['slug']}" if out["slug"] else ""
    meta = event.get("eventMetadata") or {}
    out["league"] = meta.get("league") or ""
    out["league_tier"] = meta.get("leagueTier") or ""
    out["format_bo"] = format_from_text(out["title"]) or format_from_text(event.get("score"))
    market = None
    for m in event.get("markets") or []:
        if not isinstance(m, dict):
            continue
        if m.get("sportsMarketType") == "moneyline":
            market = m
            break
    if market is None:   # older events: the two-team market that is not a map market
        for m in event.get("markets") or []:
            outs = _json_list(m.get("outcomes"))
            q = str(m.get("question") or "")
            if len(outs) == 2 and "yes" not in [str(o).lower() for o in outs] \
                    and not re.search(r"\bmap\s*\d|game\s*\d", q, re.I):
                market = m
                break
    if market is None:
        out["reject"] = "no match-winner market in event"
        return out
    outcomes = [str(o) for o in _json_list(market.get("outcomes"))]
    prices = _json_list(market.get("outcomePrices"))
    out.update({
        "market_id": str(market.get("id") or ""),
        "team_a": outcomes[0] if len(outcomes) == 2 else "",
        "team_b": outcomes[1] if len(outcomes) == 2 else "",
        "price_a": _num(prices[0]) if len(prices) == 2 else None,
        "price_b": _num(prices[1]) if len(prices) == 2 else None,
        "best_bid": _num(market.get("bestBid")),
        "best_ask": _num(market.get("bestAsk")),
        "spread": _num(market.get("spread")),
        "last_trade": _num(market.get("lastTradePrice")),
        "liquidity_usd": _num(market.get("liquidityNum") if market.get("liquidityNum") is not None
                              else market.get("liquidity")),
        "volume_usd": _num(market.get("volumeNum") if market.get("volumeNum") is not None
                           else market.get("volume")),
        "kickoff_utc": iso(parse_time(market.get("gameStartTime"))
                           or parse_time(market.get("eventStartTime"))
                           or parse_time(event.get("startTime"))),
    })
    if market.get("closed") or event.get("closed") or event.get("ended"):
        out["reject"] = "market closed / event ended"
        return out
    if market.get("acceptingOrders") is False:
        out["reject"] = "market not accepting orders"
        return out
    if event.get("live"):
        out["reject"] = "match live (in-play price)"
        return out
    if len(outcomes) != 2 or out["price_a"] is None or out["price_b"] is None:
        out["reject"] = "outcomes/prices missing"
        return out
    pa, pb = out["price_a"], out["price_b"]
    if not (0.95 <= pa + pb <= 1.05) or max(pa, pb) >= 0.99 or min(pa, pb) <= 0.01:
        out["reject"] = f"degenerate quote ({pa:.3f}/{pb:.3f})"
        return out
    if out["spread"] is None or out["spread"] > PM_MAX_SPREAD:
        out["reject"] = f"spread {out['spread']} above {PM_MAX_SPREAD} (displayed price = last trade)"
        return out
    if out["liquidity_usd"] is None or out["liquidity_usd"] < PM_MIN_LIQUIDITY:
        out["reject"] = f"book depth ${out['liquidity_usd']} below ${PM_MIN_LIQUIDITY:.0f}"
        return out
    probs = normalise_pair(pa, pb)
    out.update(probs or {})
    out["ok"] = probs is not None
    if not out["ok"]:
        out["reject"] = "prices not normalisable"
    return out


# ----------------------------------------------------------------------------- bo3.gg
def bo3_quote(match: dict) -> dict:
    """Extract the bookmaker quote bo3.gg relays in ``bet_updates`` for one match."""
    t1 = match.get("team1") or {}
    t2 = match.get("team2") or {}
    tour = match.get("tournament") or {}
    slug = match.get("slug") or ""
    out: dict = {"source": "bo3.gg", "match_id": str(match.get("id") or ""), "slug": slug,
                 "source_url": f"https://bo3.gg/matches/{slug}" if slug else "",
                 "team_a": t1.get("name") or "", "team_b": t2.get("name") or "",
                 "league": tour.get("name") or "", "league_tier": match.get("tier") or "",
                 "format_bo": match.get("bo_type") if isinstance(match.get("bo_type"), int) else None,
                 "kickoff_utc": iso(parse_time(match.get("start_date"))),
                 "status": match.get("status") or "", "ok": False}
    bu = match.get("bet_updates") or None
    if not isinstance(bu, dict):
        out["reject"] = "no bookmaker quote relayed"
        out["book"] = ""
        return out
    provider = str(bu.get("provider") or "").strip()
    out["book"] = provider.title() if provider else "unnamed provider"
    out["book_url"] = bu.get("path") or ""
    s1, s2 = bu.get("team_1") or {}, bu.get("team_2") or {}
    # align the quote to team1/team2 by team id when present
    if s1.get("team_id") and s1.get("team_id") == t2.get("id"):
        s1, s2 = s2, s1
    out["price_a"] = _num(s1.get("coeff"))
    out["price_b"] = _num(s2.get("coeff"))
    out["book_name_a"] = s1.get("name") or ""
    out["book_name_b"] = s2.get("name") or ""
    if out["status"] not in ("upcoming", ""):
        out["reject"] = f"match status '{out['status']}'"
        return out
    if not (s1.get("active") and s2.get("active")):
        out["reject"] = "quote suspended (active=false)"
        return out
    probs = devig_decimal(out["price_a"], out["price_b"])
    if probs is None:
        out["reject"] = "odds missing or <= 1.00"
        return out
    if probs["overround"] < -0.02 or probs["overround"] > BOOK_MAX_OVERROUND:
        out["reject"] = f"overround {probs['overround']*100:.1f}% outside [-2%, 20%]"
        return out
    out.update(probs)
    out["ok"] = True
    return out


# ----------------------------------------------------------------------------- matching
def match_quote(fixture: dict, quote: dict, aliases: Aliases | None = None) -> dict:
    """Relate one source quote to one Hotspawn fixture.

    Returns {'status': 'accepted'|'candidate'|'conflict'|'none', 'swap': bool, 'quality': ...,
    'delta_min': float|None, 'note': str}.  'swap' means the source lists the teams in the
    opposite order to Hotspawn.
    """
    ko_f = parse_time(fixture.get("start_utc"))
    ko_q = parse_time(quote.get("kickoff_utc"))
    delta = minutes_apart(ko_f, ko_q)
    best = {"status": "none", "swap": False, "quality": "", "delta_min": delta, "note": ""}
    if delta is None or delta > CANDIDATE_WINDOW_MIN:
        return best
    for swap in (False, True):
        qa, qb = (quote.get("team_b"), quote.get("team_a")) if swap else \
            (quote.get("team_a"), quote.get("team_b"))
        ra, na = name_relation(fixture.get("team_a"), qa, aliases)
        rb, nb = name_relation(fixture.get("team_b"), qb, aliases)
        strong = {"exact", "alias"}
        if ra in strong and rb in strong:
            if delta <= EXACT_WINDOW_MIN:
                q = "exact" if (ra == rb == "exact") else "alias"
                return {"status": "accepted", "swap": swap, "quality": q, "delta_min": delta,
                        "note": "; ".join(x for x in (na, nb) if x)}
            best = {"status": "candidate", "swap": swap, "quality": "kickoff-mismatch",
                    "delta_min": delta,
                    "note": f"both teams match but kickoff differs by {delta:.0f} min"}
            continue
        if (ra in strong and rb == "variant") or (rb in strong and ra == "variant"):
            if delta <= VARIANT_WINDOW_MIN:
                return {"status": "accepted", "swap": swap, "quality": "variant",
                        "delta_min": delta,
                        "note": f"name variant: '{fixture.get('team_a') if ra == 'variant' else fixture.get('team_b')}'"
                                f" vs '{qa if ra == 'variant' else qb}' ({na if ra == 'variant' else nb});"
                                " opponent and kickoff identical"}
            if best["status"] == "none":
                best = {"status": "candidate", "swap": swap, "quality": "variant-kickoff-mismatch",
                        "delta_min": delta, "note": f"name variant and kickoff differs by {delta:.0f} min"}
            continue
        if (ra in strong) != (rb in strong) and delta <= VARIANT_WINDOW_MIN:
            known = fixture.get("team_a") if ra in strong else fixture.get("team_b")
            hs_other = fixture.get("team_b") if ra in strong else fixture.get("team_a")
            src_other = qb if ra in strong else qa
            if best["status"] in ("none",):
                best = {"status": "conflict", "swap": swap, "quality": "opponent-conflict",
                        "delta_min": delta,
                        "note": f"{known} at the same kickoff, but the source's opponent is "
                                f"'{src_other}' where Hotspawn lists '{hs_other}'"}
    return best


def pick_from(p_a: float | None, team_a: str, team_b: str) -> str:
    if p_a is None:
        return ""
    if abs(p_a - 0.5) < 1e-9:
        return ""
    return team_a if p_a > 0.5 else team_b
