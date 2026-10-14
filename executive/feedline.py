#!/usr/bin/env python3
"""Secondary-market quotes relayed by this repository's own hourly feed — session arena/1b6ae823.

``feeds/`` (session ``arena/a0bdf924``, workflow ``feed-a0bdf924.yml``, cron hourly) reads two public
listings every run and writes ``feeds/data/market_feed.csv``: bookmaker odds relayed by bo3.gg match
pages and Polymarket's own match markets, each row already joined to a Hotspawn fixture by team pair
and kickoff, with the source URL, the source's own kickoff, the overround and the capture minute.

This board is allowed to *consume* that file as a read-only input (COORDINATION: other sessions' data
are read-only inputs; nothing here writes into ``feeds/``).  The rules applied here are the same ones
``collect.py`` applies to its own reads:

* the capture keeps **its own** ``captured_utc`` — a stale feed is labelled stale, never re-stamped;
* if the file is missing, unreadable or older than ``MAX_AGE_HOURS``, no quote is taken and the build
  says so on the row (the fixture then falls to the originated line rather than to a guess);
* a price whose own kickoff disagrees with the fixture's start by more than the tolerance is dropped;
* an equal pair of prices (the usual "no market posted" placeholder) is dropped by ``build.py`` and
  flagged, exactly as it does for the other secondary sources.
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FEED_CSV = ROOT / "feeds" / "data" / "market_feed.csv"
FEED_CAPTURE = ROOT / "feeds" / "data" / "capture.json"
MAX_AGE_HOURS = 12          # a feed older than this is not used to set a headline probability
KICKOFF_TOLERANCE_MIN = 15  # the same tolerance build.py uses for every other source


def _parse(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _float(value: object) -> float | None:
    try:
        out = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return out


def capture_generated(path: Path = FEED_CAPTURE) -> datetime | None:
    payload = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {}
    return _parse(payload.get("generated_utc") or payload.get("started_utc"))


def read_quotes(now: datetime | None = None, path: Path = FEED_CSV) -> dict:
    """Return ``{"quotes": [...], "status": ..., "captured_utc": ...}`` for ``collect.py`` to merge.

    Quote objects use exactly the shape ``build.assigned_quotes`` expects, so nothing downstream has
    to know where a price came from: ``odds_a``/``odds_b`` are decimal, ``p_a``/``p_b`` are recomputed
    by the de-vig helper, and ``best_of`` carries the listing's own stated series length.
    """
    now = now or datetime.now(timezone.utc)
    result = {"quotes": [], "status": "unavailable", "rows": 0, "used": 0,
              "dropped_kickoff": 0, "dropped_price": 0, "dropped_stale": 0,
              "captured_utc": None, "feed_generated_utc": None, "max_age_hours": MAX_AGE_HOURS,
              "source_file": "feeds/data/market_feed.csv",
              "feed_page": "https://buffedlizard55-lab.github.io/MaltaProj1/feeds/index.html"}
    if not path.exists():
        result["status"] = "missing"
        return result
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error) as exc:
        result["status"] = f"unreadable ({type(exc).__name__})"
        return result

    file_generated = capture_generated()
    result["feed_generated_utc"] = file_generated.strftime("%Y-%m-%dT%H:%M:%SZ") if file_generated else None
    stamps = [_parse(row.get("captured_utc")) for row in rows]
    stamps = [s for s in stamps if s]
    oldest_row = min(stamps) if stamps else None
    reference = file_generated or oldest_row
    if reference is not None and now - reference > timedelta(hours=MAX_AGE_HOURS):
        result["status"] = "stale"
        result["age_hours"] = round((now - reference).total_seconds() / 3600.0, 2)
        result["captured_utc"] = reference.strftime("%Y-%m-%dT%H:%M:%SZ")
        return result

    quotes = []
    for row in rows:
        result["rows"] += 1
        price_a, price_b = _float(row.get("price_a")), _float(row.get("price_b"))
        kind = str(row.get("price_kind") or "")
        odds_a = odds_b = None
        native_format = "decimal"
        if "share price" in kind.lower() and price_a and price_b and 0 < price_a < 1 and 0 < price_b < 1:
            odds_a, odds_b = 1.0 / price_a, 1.0 / price_b
            native_format = "implied_probability"
        elif price_a and price_b and price_a > 1.0 and price_b > 1.0:
            odds_a, odds_b = price_a, price_b
        if odds_a is None:
            result["dropped_price"] += 1
            continue
        start = row.get("source_kickoff_utc") or row.get("start_utc") or ""
        src_start, hs_start = _parse(row.get("source_kickoff_utc")), _parse(row.get("start_utc"))
        if src_start and hs_start and abs(src_start - hs_start) > timedelta(minutes=KICKOFF_TOLERANCE_MIN):
            result["dropped_kickoff"] += 1
            continue
        source = str(row.get("source") or "").strip()
        book = str(row.get("book") or source).strip()
        is_prediction = "polymarket" in source.lower()
        captured = str(row.get("captured_utc") or "").strip()
        quotes.append({
            "source_id": f"feed-{source.lower().replace('.', '').replace(' ', '-') or 'unknown'}",
            "source_name": book or source or "Secondary listing",
            # build.py gives bookmaker listings priority over prediction markets on this key.
            "source_role": "prediction_market" if is_prediction else "secondary_aggregator",
            "relay": source,
            "event_id": "", "market_id": "",
            "league": str(row.get("competition") or ""),
            "team_a": str(row.get("team_a") or ""), "team_b": str(row.get("team_b") or ""),
            "start_time": str(start).replace("+00:00", "")[:19] + ("Z" if start else ""),
            "best_of": _float(row.get("format_bo")),
            "native_format": native_format,
            "native_a": price_a, "native_b": price_b,
            "odds_a": round(odds_a, 6), "odds_b": round(odds_b, 6),
            "market_type": "match_winner", "status": "open",
            "source_url": str(row.get("source_url") or ""),
            "book_url": str(row.get("book_url") or ""),
            "source_event": str(row.get("source_event") or ""),
            "hotspawn_url": str(row.get("hotspawn_url") or ""),
            "captured_utc": captured,
            "feed": "feeds/data/market_feed.csv",
            "match_quality": str(row.get("match_quality") or ""),
        })
        result["used"] += 1
    result["quotes"] = quotes
    result["captured_utc"] = (oldest_row or reference or now).strftime("%Y-%m-%dT%H:%M:%SZ")
    if quotes:
        result["status"] = "ok"
    else:
        result["status"] = "no-usable-rows"
    return result


__all__ = ["read_quotes", "capture_generated", "FEED_CSV", "MAX_AGE_HOURS"]
