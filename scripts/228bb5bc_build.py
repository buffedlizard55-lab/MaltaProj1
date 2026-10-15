#!/usr/bin/env python3
"""Consolidated every-match picks board (session arena/228bb5bc).

Reads the *committed* data of the boards that already collect and verify outside
market prices and official ratings, and publishes one mobile-first page with a
row for every open Counter-Strike 2 fixture on the Hotspawn Pick'em board:

    console/index.html       one row per open fixture: both win probabilities,
                             the explicit pick, the basis rung it rests on,
                             the read time and the source URL behind every number
    console/flagged.html     every flag, with counts and source links
    console/methodology.html the rungs and formulas, exactly as implemented
    console/sources.html     every source the board reads, with read times
    console/data/*.csv|json  machine-readable rows + coverage

Rules enforced by this script (see tests/test_228bb5bc.py):

* Hotspawn supplies fixture identity, kickoff/lock times and competition only.
  A published probability may never come from a play.hotspawn.com URL.
* Every published probability carries a source URL and a read/capture time.
* Numbers are never averaged across rungs and never typed in by hand: the
  headline is the highest rung available, alternates are listed beside it.
* A row with no usable outside price falls back to the board's own originated
  line (Valve Regional Standings + HLTV ranking, formula published), and a row
  with no rating at all falls back to the labelled RESEARCH line. A row with
  nothing gets a blank probability and a flag -- never a guess.

No network access: this script is deterministic and only reads committed files.
"""

from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "console"
DATA = OUT / "data"

# ---------------------------------------------------------------------------
# inputs (read-only)
# ---------------------------------------------------------------------------
INPUTS = {
    "feeds": {
        "rows": "feeds/data/fixtures.csv",
        "summary": "feeds/data/summary.json",
        "label": "Secondary-market feed (arena/a0bdf924)",
        "page": "feeds/index.html",
    },
    "cs2": {
        "rows": "cs2/data/analysis.csv",
        "summary": "cs2/data/capture.json",
        "label": "Line-analysis board (arena/a174d77f)",
        "page": "cs2/index.html",
    },
    "executive": {
        "rows": "executive/data/analysis.csv",
        "summary": "executive/data/summary.json",
        "label": "Executive board (arena/5545dbb8)",
        "page": "executive/index.html",
    },
    "every": {
        "rows": "every/data/picks.csv",
        "summary": None,
        "label": "Every-match picks (arena/75fd29ee)",
        "page": "every/index.html",
    },
    "picks_full_market": {
        "rows": "data/63ee81ba/market_lines.csv",
        "summary": "data/63ee81ba/coverage.json",
        "label": "Full picks board, market lines (arena/63ee81ba)",
        "page": "picks-full/market-lines.html",
    },
    "picks_full_own": {
        "rows": "data/63ee81ba/own_lines.csv",
        "summary": "data/63ee81ba/coverage.json",
        "label": "Full picks board, own lines (arena/63ee81ba)",
        "page": "picks-full/own-lines.html",
    },
}

CADENCE_TEXT = (
    "The source boards refresh hourly in GitHub Actions; this page is rebuilt "
    "from their committed captures on every refresh and on every change to those "
    "files, so it is never older than its newest input."
)

# A headline may be at most this old before the build refuses to publish.
MAX_INPUT_AGE_HOURS = 6.0


class BuildError(RuntimeError):
    """Raised before anything is written when an invariant is broken."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def read_csv(rel: str) -> list[dict]:
    path = ROOT / rel
    if not path.exists():
        raise BuildError(f"missing input {rel}")
    with path.open(newline="", encoding="utf-8") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def read_json(rel: str):
    path = ROOT / rel
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def sha256(rel: str) -> str:
    path = ROOT / rel
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fnum(value) -> float | None:
    """Parse a numeric cell; blanks and junk return None (never zero)."""
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    if text == "" or text.lower() in {"nan", "none", "null", "-", "—"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_utc(value) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%MZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:  # ISO with offset
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def iso(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def pct(value: float | None, nd: int = 1) -> str:
    return "" if value is None else f"{value:.{nd}f}"


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""), quote=True)


def slug(fixture_id: str) -> str:
    return f"m-{fixture_id}"


def is_http(url: str) -> bool:
    return bool(url) and str(url).startswith(("http://", "https://"))


def host_of(url: str) -> str:
    m = re.match(r"https?://([^/]+)/?", str(url or ""))
    return m.group(1).lower() if m else ""


# ---------------------------------------------------------------------------
# load
# ---------------------------------------------------------------------------
def load_inputs(now: datetime) -> tuple[dict, list[dict]]:
    data, problems = {}, []
    for key, spec in INPUTS.items():
        rows = read_csv(spec["rows"])
        summary = read_json(spec["summary"]) if spec.get("summary") else None
        data[key] = {
            "key": key,
            "rows": rows,
            "summary": summary,
            "label": spec["label"],
            "page": spec["page"],
            "file": spec["rows"],
            "sha256": sha256(spec["rows"]),
            "captured_utc": newest_capture(rows, summary),
        }
    return data, problems


ROW_STAMP_FIELDS = ("captured_utc", "capture_utc", "last_verified_utc", "first_seen_utc",
                    "market_captured_utc", "read_utc", "generated_utc")
SUMMARY_STAMP_KEYS = ("snapshot_utc", "generated_utc", "as_of_utc", "capture_utc", "started_utc")


def newest_capture(rows: list[dict], summary=None) -> str:
    """Latest read/capture time declared by the input file or its sidecar."""
    stamps = []
    for row in rows:
        for field in ROW_STAMP_FIELDS:
            dt = parse_utc(row.get(field))
            if dt:
                stamps.append(dt)
    if isinstance(summary, dict):
        for key in SUMMARY_STAMP_KEYS:
            dt = parse_utc(summary.get(key))
            if dt:
                stamps.append(dt)
        meta = summary.get("meta")
        if isinstance(meta, dict):
            for key in SUMMARY_STAMP_KEYS:
                dt = parse_utc(meta.get(key))
                if dt:
                    stamps.append(dt)
    return iso(max(stamps)) if stamps else ""


# ---------------------------------------------------------------------------
# per-source extraction
# ---------------------------------------------------------------------------
def index_by(rows: list[dict], *keys: str) -> dict:
    out = {}
    for row in rows:
        for key in keys:
            value = str(row.get(key, "")).strip()
            if value:
                out.setdefault(value, row)
                break
    return out


def market_candidates(fid: str, feeds: dict | None, cs2: dict | None,
                      execu: dict | None, every: dict | None,
                      pf_market: dict | None) -> list[dict]:
    """Collect every outside price for one fixture, best rung first.

    Rung order (documented on console/methodology.html):

      1  book, read directly          (Pinnacle public guest response)
      2  book, relayed by bo3.gg      (bookmaker match URL linked)
      3  book, relayed by EGamersWorld (aggregator-mediated)
      4  prediction market            (Polymarket traded prices)

    A higher rung is never averaged with a lower one; the headline is the best
    rung and every other rung is published beside it.
    """
    cands: list[dict] = []

    if cs2:
        book = (cs2.get("market_book") or "").strip()
        p_a, p_b = fnum(cs2.get("market_p_a_pct")), fnum(cs2.get("market_p_b_pct"))
        if book and p_a is not None and p_b is not None:
            cands.append({
                "rung": 1,
                "rung_label": "book · read directly",
                "book": book,
                "p_a": p_a,
                "p_b": p_b,
                "odds_a": cs2.get("market_odds_a", ""),
                "odds_b": cs2.get("market_odds_b", ""),
                "overround_pct": cs2.get("market_overround_pct", ""),
                "url": (cs2.get("market_url") or "").strip(),
                "manual_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
                "read_utc": iso(parse_utc(cs2.get("market_captured_utc"))),
                "caveat": "public guest response read by the line-analysis board; "
                          "de-vigged two-way price (manual check: Pinnacle CS2 matchups page)",
            })

    if feeds:
        book = (feeds.get("bookmaker_book") or "").strip()
        p_a, p_b = fnum(feeds.get("bookmaker_p_a_pct")), fnum(feeds.get("bookmaker_p_b_pct"))
        if book and p_a is not None and p_b is not None:
            cands.append({
                "rung": 2,
                "rung_label": "book · relayed via bo3.gg",
                "book": book,
                "p_a": p_a,
                "p_b": p_b,
                "odds_a": "",
                "odds_b": "",
                "overround_pct": "",
                "url": (feeds.get("bookmaker_url") or "").strip(),
                "read_utc": iso(parse_utc(feeds.get("captured_utc"))),
                "caveat": "quote relayed by bo3.gg's public API, not read from the "
                          "bookmaker's own site (MF-09); the bookmaker match URL is "
                          "linked so the price can be checked by hand",
            })

    if pf_market:
        book = (pf_market.get("primary_book") or "").strip()
        p_a, p_b = fnum(pf_market.get("devig_p_a_pct")), fnum(pf_market.get("devig_p_b_pct"))
        if book and p_a is not None and p_b is not None:
            cands.append({
                "rung": 3,
                "rung_label": "book · relayed via EGamersWorld",
                "book": book,
                "p_a": p_a,
                "p_b": p_b,
                "odds_a": pf_market.get("odds_a", ""),
                "odds_b": pf_market.get("odds_b", ""),
                "overround_pct": pf_market.get("overround_pct", ""),
                "url": (pf_market.get("source_url") or "").strip(),
                "read_utc": iso(parse_utc(pf_market.get("captured_utc"))),
                "caveat": "aggregator-reported bookmaker odds, not independently "
                          "verified against the book (PF-01 class)",
            })

    if feeds:
        p_a, p_b = fnum(feeds.get("polymarket_p_a_pct")), fnum(feeds.get("polymarket_p_b_pct"))
        if p_a is not None and p_b is not None:
            cands.append({
                "rung": 4,
                "rung_label": "prediction market · Polymarket",
                "book": "Polymarket",
                "p_a": p_a,
                "p_b": p_b,
                "odds_a": "",
                "odds_b": "",
                "overround_pct": "",
                "url": (feeds.get("polymarket_url") or "").strip(),
                "read_utc": iso(parse_utc(feeds.get("captured_utc"))),
                "caveat": "prediction market (traded prices, no bookmaker margin, "
                          "MF-10); thin books move quickly",
            })

    cands.sort(key=lambda c: (c["rung"], c["book"]))
    return cands



def load_alias_map() -> dict:
    """Documented, evidence-linked team spellings from the boards that published them."""
    aliases: dict[str, dict] = {}
    cs2_aliases = read_json("cs2/aliases.json") or {}
    for name, entry in cs2_aliases.items():
        if name.startswith("_") or not isinstance(entry, dict):
            continue
        official = (entry.get("alias_of") or "").strip()
        if official:
            aliases[name.lower()] = {
                "official_name": official,
                "evidence_url": entry.get("evidence_url") or "",
                "why": entry.get("why") or "",
            }
    exec_aliases = (read_json("executive/aliases.json") or {}).get("renames") or {}
    for name, entry in exec_aliases.items():
        if not isinstance(entry, dict):
            continue
        official = (entry.get("official_name") or "").strip()
        if official and name.lower() not in aliases:
            aliases[name.lower()] = {
                "official_name": official,
                "evidence_url": entry.get("evidence_url") or "",
                "why": entry.get("note") or "",
            }
    return aliases


def parse_vrs_file() -> tuple[list[str], dict]:
    """Read the committed official standings file and its claimed hash."""
    rel = "data/63ee81ba/vrs_2026_10_05.md"
    path = ROOT / rel
    if not path.exists():
        return [], {}
    lines = path.read_text(encoding="utf-8").splitlines()
    claimed = ((read_json("data/63ee81ba/coverage.json") or {}).get("sources") or {}).get("vrs_local_sha256")
    actual = sha256(rel)
    return lines, {"file": rel, "sha256": actual, "claimed_sha256": claimed,
                   "integrity_ok": bool(claimed) and actual == claimed}


VRS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|")


def verify_rating_anchor(anchor_url: str, team: str, standings_claimed, points_claimed,
                         vrs_lines: list[str], aliases: dict) -> dict:
    """Re-check one cited rating row against the committed official standings file.

    Confirms that the URL's #Lnnn anchor exists, that the line is a standings row, that the team
    named on it is the team (or a documented, evidence-linked alias of it) and that the points on
    that line are the points the row publishes. Anything else is reported as unverified.
    """
    out = {"ok": False, "alias_of": "", "evidence_url": "", "detail": ""}
    m = re.search(r"#L(\d+)$", anchor_url or "")
    if not m:
        out["detail"] = "no #L anchor in the rating-source URL"
        return out
    if not vrs_lines:
        out["detail"] = "committed standings file unavailable"
        return out
    n = int(m.group(1))
    if n < 1 or n > len(vrs_lines):
        out["detail"] = f"anchor line {n} is outside the committed file"
        return out
    line = vrs_lines[n - 1]
    parsed = VRS_ROW.match(line)
    if not parsed:
        out["detail"] = f"line {n} is not a standings row"
        return out
    standings, points, name = parsed.group(1), parsed.group(2), parsed.group(3).strip()
    norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
    if norm(name) != norm(team):
        alias = aliases.get(team.lower())
        if not alias or norm(alias["official_name"]) != norm(name):
            out["detail"] = (f"line {n} names {name!r}, not {team!r}"
                             + (f" (documented alias is {alias['official_name']!r})" if alias else ""))
            return out
        out["alias_of"], out["evidence_url"] = name, alias["evidence_url"]
    if standings_claimed and str(standings_claimed).strip() and str(standings).strip() != str(standings_claimed).strip():
        out["detail"] = f"line {n} lists standing {standings}, the row publishes {standings_claimed}"
        return out
    if points_claimed and str(points_claimed).strip() and str(points).strip() != str(points_claimed).strip():
        out["detail"] = f"line {n} lists {points} points, the row publishes {points_claimed}"
        return out
    out["ok"] = True
    out["detail"] = f"line {n}: {name} #{standings} {points} points"
    return out


def own_line(fid: str, own: dict | None, cs2: dict | None, checks: dict | None = None) -> dict | None:
    """Our originated line: the documented picks-full model when present.

    ``checks`` carries the anchor-verification verdict for each side. A row whose rating could not
    be confirmed at the cited official line is not published as a number -- it is blanked and
    flagged, exactly like any other value that cannot be sourced.
    """
    if own:
        p_a, p_b = fnum(own.get("own_p_a_pct")), fnum(own.get("own_p_b_pct"))
        ver_a = (checks or {}).get("a") or {}
        ver_b = (checks or {}).get("b") or {}
        research_line = (own.get("research") or "no").strip().lower() == "yes"
        unverified = [] if research_line else [
            side for side, ver in (("team A", ver_a), ("team B", ver_b))
            if checks is not None and not ver.get("ok")]
        if unverified:
            return {
                "p_a": None, "p_b": None,
                "method": (own.get("method") or "").strip(),
                "format": (own.get("series_format") or "").strip(),
                "rating_url_a": (own.get("vrs_url_a") or "").strip(),
                "rating_url_b": (own.get("vrs_url_b") or "").strip(),
                "hltv_match_url": (own.get("hltv_match_url") or "").strip(),
                "research": (own.get("research") or "no").strip().lower() == "yes",
                "flags": (own.get("flags") or "").strip(),
                "verified": False,
                "verification": {"a": ver_a, "b": ver_b},
                "unverified_sides": unverified,
            }
        if p_a is not None and p_b is not None:
            research = (own.get("research") or "no").strip().lower() == "yes"
            return {
                "p_a": p_a,
                "p_b": p_b,
                "method": (own.get("method") or "").strip(),
                "format": (own.get("series_format") or "").strip(),
                "rating_url_a": (own.get("vrs_url_a") or "").strip(),
                "rating_url_b": (own.get("vrs_url_b") or "").strip(),
                "hltv_match_url": (own.get("hltv_match_url") or "").strip(),
                "research": research,
                "flags": (own.get("flags") or "").strip(),
                "verified": True,
                "verification": {"a": ver_a, "b": ver_b},
                "unverified_sides": [],
            }
    if cs2:
        p_a, p_b = fnum(cs2.get("own_p_a_pct")), fnum(cs2.get("own_p_b_pct"))
        if p_a is not None and p_b is not None:
            return {
                "p_a": p_a,
                "p_b": p_b,
                "method": (cs2.get("own_basis") or "").strip(),
                "format": (cs2.get("best_of") or "").strip(),
                "rating_url_a": (cs2.get("vrs_url_a") or "").strip(),
                "rating_url_b": (cs2.get("vrs_url_b") or "").strip(),
                "hltv_match_url": "",
                "research": False,
                "flags": (cs2.get("flags") or "").strip(),
                "verified": None,
                "verification": {},
                "unverified_sides": [],
            }
    return None


def research_candidates(fid: str, every: dict | None, execu: dict | None) -> list[dict]:
    """Published research estimates for a fixture whose teams are not rated."""
    out = []
    if every:
        p_a, p_b = fnum(every.get("our_series_p_a_pct")), fnum(every.get("our_series_p_b_pct"))
        if p_a is not None and p_b is not None:
            out.append({
                "source": "every/ (arena/75fd29ee) researched rating line",
                "p_a": p_a, "p_b": p_b,
                "url": (every.get("pick_source_url") or "").strip() or
                       (every.get("rating_a_source_url") or "").strip(),
                "read_utc": iso(parse_utc(every.get("market_captured_utc"))) or "",
                "note": (every.get("pick_basis") or "").strip(),
            })
    if execu:
        p_a, p_b = fnum(execu.get("model_prob_a_pct")), fnum(execu.get("model_prob_b_pct"))
        if p_a is not None and p_b is not None:
            out.append({
                "source": "executive/ (arena/5545dbb8) model line",
                "p_a": p_a, "p_b": p_b,
                "url": (execu.get("rating_a_source") or "").strip(),
                "read_utc": iso(parse_utc(execu.get("last_verified_utc"))) or "",
                "note": (execu.get("basis_detail") or "").strip(),
            })
    return out


def confidence_label(p: float | None, margin: float | None) -> str:
    if p is None or margin is None:
        return "no basis"
    if margin <= 2.0:
        return "coin-flip"
    if p >= 70:
        return "heavy favourite"
    if p >= 60:
        return "strong favourite"
    if p >= 55:
        return "slight favourite"
    return "narrow favourite"


# ---------------------------------------------------------------------------
# build rows
# ---------------------------------------------------------------------------
def build_rows(inputs: dict, now: datetime) -> tuple[list[dict], list[dict], dict]:
    feeds_rows = [r for r in inputs["feeds"]["rows"]]
    cs2_by = index_by(inputs["cs2"]["rows"], "fixture_id")
    execu_by = index_by(inputs["executive"]["rows"], "match_id")
    every_by = index_by(inputs["every"]["rows"], "fixture_id")
    pf_market_by = index_by(inputs["picks_full_market"]["rows"], "match_id")
    pf_own_by = index_by(inputs["picks_full_own"]["rows"], "match_id")

    vrs_lines, vrs_meta = parse_vrs_file()
    aliases = load_alias_map()

    seen: dict[str, dict] = {}
    for row in feeds_rows:
        fid = str(row.get("fixture_id", "")).strip()
        if fid:
            seen[fid] = row

    # The open fixture set is the union of the boards' open sets, so a fixture a
    # single board has already captured is never hidden by another board's lag.
    open_ids = set(seen)
    for src, key in ((inputs["cs2"]["rows"], "fixture_id"),
                     (inputs["executive"]["rows"], "match_id"),
                     (inputs["every"]["rows"], "fixture_id")):
        for row in src:
            state = (row.get("state") or row.get("status") or "").strip().lower()
            fid = str(row.get(key, "")).strip()
            if state == "open" and fid:
                open_ids.add(fid)

    rows: list[dict] = []
    flags: dict[str, dict] = {}

    def add_flag(code: str, meaning: str, fid: str, source_url: str = "", detail: str = ""):
        entry = flags.setdefault(code, {"code": code, "meaning": meaning, "rows": [], "urls": set()})
        entry["rows"].append({"fixture_id": fid, "source_url": source_url, "detail": detail})
        if is_http(source_url):
            entry["urls"].add(source_url)

    for fid in sorted(open_ids, key=lambda x: (seen.get(x, {}).get("lock_utc", ""), x)):
        feed = seen.get(fid, {})
        cs2 = cs2_by.get(fid)
        execu = execu_by.get(fid)
        every = every_by.get(fid)
        pf_market = pf_market_by.get(fid)
        pf_own = pf_own_by.get(fid)
        checks = None
        if pf_own:
            checks = {
                side: verify_rating_anchor(pf_own.get(f"vrs_url_{side}", ""), pf_own.get(f"team_{side}", ""),
                                           pf_own.get(f"vrs_standing_{side}", ""), pf_own.get(f"vrs_points_{side}", ""),
                                           vrs_lines, aliases)
                for side in ("a", "b")
            }
        own = own_line(fid, pf_own, cs2, checks)
        research = research_candidates(fid, every, execu)
        cands = market_candidates(fid, feed, cs2, execu, every, pf_market)

        row_flags: list[str] = []
        headline = cands[0] if cands else None
        basis_rung = ""
        p_a = p_b = None
        source_url = ""
        read_utc = ""
        basis_label = ""
        basis_detail = ""

        if headline:
            basis_rung = f"market-{headline['rung']}"
            p_a, p_b = headline["p_a"], headline["p_b"]
            source_url = headline["url"]
            read_utc = headline["read_utc"]
            basis_label = headline["rung_label"]
            basis_detail = f"{headline['book']} — {headline['caveat']}"
            if headline["rung"] in (2, 3):
                row_flags.append("C-RELAYED-BOOK-PRICE")
                add_flag("C-RELAYED-BOOK-PRICE",
                         "The headline price is relayed by an aggregator rather than read from the "
                         "bookmaker's own site; the bookmaker match URL is linked on the row so the price "
                         "can be checked by hand.",
                         fid, headline["url"], f'{headline["book"]} {headline["p_a"]:.1f}/{headline["p_b"]:.1f}')
            if headline["rung"] == 4:
                row_flags.append("C-PREDICTION-MARKET-PRICE")
                add_flag("C-PREDICTION-MARKET-PRICE",
                         "The headline probability comes from a prediction market (traded prices, no "
                         "bookmaker margin); thin books move quickly.",
                         fid, headline["url"], f'{headline["p_a"]:.1f}/{headline["p_b"]:.1f}')
            if not is_http(source_url):
                row_flags.append("C-NO-SOURCE-URL")
        elif own and not own.get("verified", True):
            basis_rung = "unverified"
            basis_label = "own line withheld -- rating could not be confirmed at the cited line"
            basis_detail = ("; ".join(f"{s}: {v.get('detail', '')}" for s, v in own["verification"].items()))
            source_url = own["rating_url_a"]
            read_utc = iso(parse_utc((pf_own_by.get(fid) or {}).get("captured_utc"))) or \
                iso(parse_utc((execu or {}).get("last_verified_utc")))
            row_flags.append("C-OWN-LINE-UNVERIFIED")
            add_flag("C-OWN-LINE-UNVERIFIED",
                     "The official rating row cited for this fixture's own originated line could not be "
                     "confirmed at the URL anchor (the line names another team, or the standing/points "
                     "differ). The own-line probability is withheld rather than published.",
                     fid, own["rating_url_a"], basis_detail)
            if own.get("research"):
                row_flags.append("C-RESEARCH-LINE")
        elif own and own.get("p_a") is not None:
            basis_rung = "own-line"
            p_a, p_b = own["p_a"], own["p_b"]
            source_url = own["rating_url_a"]
            read_utc = iso(parse_utc((execu or {}).get("last_verified_utc"))) or \
                iso(parse_utc((pf_own_by.get(fid) or {}).get("captured_utc")))
            basis_label = "own line · Valve Regional Standings + HLTV ranking"
            basis_detail = own["method"]
            row_flags.append("C-NO-OUTSIDE-MARKET")
            if own["research"]:
                basis_rung = "research"
                basis_label = "research line · team not in the official standings"
                row_flags.append("C-RESEARCH-LINE")
                if research:
                    fav_a = p_a >= p_b
                    values = [(own["p_a"] if fav_a else own["p_b"])]
                    for r in research:
                        values.append(r["p_a"] if fav_a else r["p_b"])
                    lo, hi = min(values), max(values)
                    fav_name = feed.get("team_a") if fav_a else feed.get("team_b")
                    basis_detail += (
                        f" — published estimates for {fav_name}'s win probability span "
                        f"{lo:.1f}–{hi:.1f}%; treated as unverified."
                    )
                    for r in research:
                        add_flag("C-RESEARCH-RANGE", "More than one research estimate exists for a fixture "
                                                     "whose team is absent from the official standings; the board "
                                                     "publishes a range and labels it unverified.",
                                 fid, r["url"], f"{r['source']}: {r['p_a']:.1f}/{r['p_b']:.1f}% ({r['note']})")
        else:
            basis_rung = "none"
            basis_label = "no basis -- blank, not guessed"
            row_flags.append("C-NO-BASIS")
            add_flag("C-NO-BASIS",
                     "No outside price and no official rating could be resolved for this fixture in the "
                     "current captures; probabilities stay blank.",
                     fid, "")

        pick = ""
        pick_pct = None
        margin = None
        if p_a is not None and p_b is not None:
            pick = feed.get("team_a", "") if p_a >= p_b else feed.get("team_b", "")
            pick_pct = max(p_a, p_b)
            margin = abs(p_a - p_b)
            if margin <= 2.0:
                row_flags.append("C-THIN-MARKET")
                add_flag("C-THIN-MARKET",
                         "The two published probabilities are within 2 points of each other; the pick is a "
                         "coin-flip and is labelled as one.",
                         fid, source_url, f"{p_a:.1f} / {p_b:.1f}")
            if basis_rung.startswith("market") and own:
                market_fav_a = p_a >= p_b
                own_fav_a = own["p_a"] >= own["p_b"]
                if market_fav_a != own_fav_a:
                    row_flags.append("C-MARKET-MODEL-SPLIT")
                    add_flag("C-MARKET-MODEL-SPLIT",
                             "The outside market's favourite and this board's own originated line name "
                             "different winners; both are published and the pick follows the market.",
                             fid, source_url,
                             f"market {p_a:.1f}/{p_b:.1f} vs own line {own['p_a']:.1f}/{own['p_b']:.1f}")

        # documented aliases used by the own line: always visible on the row
        for side, ver in ((own or {}).get("verification") or {}).items():
            if ver.get("alias_of"):
                row_flags.append("C-ALIAS-RATING-ROW")
                add_flag("C-ALIAS-RATING-ROW",
                         "The official standings row used for this team names a different spelling; the "
                         "equivalence is documented with an evidence link and was re-checked against the "
                         "committed standings line (name and points).",
                         fid, ver.get("evidence_url", ""),
                         f"Hotspawn {('team A' if side == 'a' else 'team B')} -> official row "
                         f"{ver['alias_of']!r} ({ver.get('detail','')})")

        # format + identity flags come from the component boards, not invented here
        if not str(feed.get("format_bo", "")).strip():
            row_flags.append("C-FORMAT-UNKNOWN")
        feed_flags = str(feed.get("flags", ""))
        if "MF-02" in feed_flags:
            row_flags.append("C-OPPONENT-CONFLICT")
            add_flag("C-OPPONENT-CONFLICT",
                     "An outside source lists one of the teams at the same kickoff against a different "
                     "opponent; that listing was not used for either team's probability.",
                     fid, "", "")
        if "MF-05" in feed_flags or "MF-06" in feed_flags or "MF-14" in feed_flags:
            row_flags.append("C-QUOTE-REJECTED")
            add_flag("C-QUOTE-REJECTED",
                     "A prediction-market listing existed for this fixture but its quote failed the feed's "
                     "quality gate (spread, depth, degenerate or suspended price) and was not used.",
                     fid, "", "")
        if "MF-01" in feed_flags or "MF-11" in feed_flags:
            row_flags.append("C-NO-SECONDARY-MARKET")
            add_flag("C-NO-SECONDARY-MARKET",
                     "Neither the bookmaker relay nor Polymarket listed a usable price for this fixture in "
                     "the current capture; if a price appears here it comes from another capture or from "
                     "this board's own line.",
                     fid, "", "")
        board_flag_text = ";".join(x for x in [
            str(feed.get("flags", "")).strip(),
            str((execu or {}).get("flags", "")).strip(),
            str((cs2 or {}).get("flags", "")).strip(),
            str((every or {}).get("flags", "")).strip(),
            (own or {}).get("flags", "").strip(),
        ] if x)
        if re.search(r"FL-ALIAS|FL-AMBIGUOUS-NAME|A-ALIAS|FL-DUPLICATE-VRS", board_flag_text):
            row_flags.append("C-NAME-VARIANT")
            add_flag("C-NAME-VARIANT",
                     "The same team appears under more than one name or with a duplicate rating entry "
                     "across sources; the alias the board matched on is recorded on the row.",
                     fid, "", "")

        hotspawn_match = (feed.get("hotspawn_url") or "").strip()
        if hotspawn_match.endswith("/cs2-pickems") or hotspawn_match.endswith("/lobby"):
            hotspawn_match = ""
        hltv_match = (own or {}).get("hltv_match_url", "") or (every or {}).get("hltv_match_url", "") or ""

        lock_dt = parse_utc(feed.get("lock_utc") or (execu or {}).get("lock_utc") or
                            (cs2 or {}).get("lock_utc"))
        start_dt = parse_utc(feed.get("start_utc") or (execu or {}).get("start_utc") or
                             (cs2 or {}).get("start_utc"))
        state = "open"
        if lock_dt and now >= lock_dt:
            state = "locked"

        rows.append({
            "fixture_id": fid,
            "competition": (feed.get("competition") or (execu or {}).get("tournament") or
                            (cs2 or {}).get("competition") or "").strip(),
            "tier": (feed.get("tier") or (execu or {}).get("tier") or
                     (cs2 or {}).get("tier") or "").strip(),
            "team_a": (feed.get("team_a") or (execu or {}).get("team_a") or
                       (cs2 or {}).get("team_a") or "").strip(),
            "team_b": (feed.get("team_b") or (execu or {}).get("team_b") or
                       (cs2 or {}).get("team_b") or "").strip(),
            "start_utc": iso(start_dt),
            "lock_utc": iso(lock_dt),
            "state": state,
            "series_format": (("BO" + str(feed.get("format_bo")).strip())
                              if str(feed.get("format_bo", "")).strip() else
                              ((own or {}).get("format") or (cs2 or {}).get("best_of") or "")),
            "format_source": (feed.get("format_source") or (cs2 or {}).get("best_of_source") or "").strip(),
            "basis_rung": basis_rung,
            "basis_label": basis_label,
            "basis_detail": basis_detail,
            "p_a_pct": p_a,
            "p_b_pct": p_b,
            "pick": pick,
            "pick_pct": pick_pct,
            "margin_pp": margin,
            "confidence": confidence_label(pick_pct, margin),
            "source_url": source_url,
            "read_utc": read_utc,
            "market_candidates": cands,
            "own_line": own,
            "research_lines": research,
            "hltv_match_url": hltv_match,
            "hotspawn_match_url": hotspawn_match,
            "board_flags": board_flag_text,
            "flags": sorted(set(row_flags)),
        })

    meta = summarise(rows, inputs, now)
    # curated manual-review findings, maintained by hand in console/data/review_findings.csv
    findings_path = DATA / "review_findings.csv"
    if findings_path.exists():
        with findings_path.open(encoding="utf-8") as fh:
            for f in csv.DictReader(fh):
                code = (f.get("code") or "").strip()
                if not code:
                    continue
                add_flag(code, (f.get("finding") or "").strip(),
                         (f.get("fixture_id") or "").strip() or "*",
                         (f.get("source_url") or "").strip(),
                         (f.get("detail") or "").strip())

    return rows, sorted(flags.values(), key=lambda f: (-len(f["rows"]), f["code"])), meta


def summarise(rows: list[dict], inputs: dict, now: datetime) -> dict:
    open_rows = [r for r in rows if r["state"] == "open"]
    with_pick = [r for r in open_rows if r["pick"]]
    market = [r for r in open_rows if r["basis_rung"].startswith("market")]
    own = [r for r in open_rows if r["basis_rung"] == "own-line"]
    research = [r for r in open_rows if r["basis_rung"] == "research"]
    inputs_meta = []
    for key, spec in INPUTS.items():
        inputs_meta.append({
            "key": key,
            "label": spec["label"],
            "page": spec["page"],
            "file": inputs[key]["file"],
            "captured_utc": inputs[key]["captured_utc"],
            "sha256": inputs[key]["sha256"],
            "rows": len(inputs[key]["rows"]),
        })
    vrs_lines, vrs_meta = parse_vrs_file()
    anchor_counts = {"verified": 0, "alias": 0, "unverified": 0, "absent": 0}
    for r in rows:
        own_row = r.get("own_line")
        if not own_row:
            continue
        if not own_row.get("verified", True):
            anchor_counts["unverified"] += 1
            continue
        for ver in (own_row.get("verification") or {}).values():
            if ver.get("alias_of"):
                anchor_counts["alias"] += 1
            elif ver.get("ok"):
                anchor_counts["verified"] += 1
            else:
                anchor_counts["absent"] += 1
    stamps = [parse_utc(i["captured_utc"]) for i in inputs_meta]
    stamps = [s for s in stamps if s]
    data_as_of = max(stamps) if stamps else None
    age_h = (now - data_as_of).total_seconds() / 3600 if data_as_of else None
    return {
        "generated_for_utc": iso(now),
        "data_as_of_utc": iso(data_as_of),
        "newest_input_age_hours": round(age_h, 2) if age_h is not None else None,
        "max_input_age_hours": MAX_INPUT_AGE_HOURS,
        "stale": bool(age_h is not None and age_h > MAX_INPUT_AGE_HOURS),
        "counts": {
            "rows": len(rows),
            "open": len(open_rows),
            "locked": len(rows) - len(open_rows),
            "open_with_pick": len(with_pick),
            "open_market_basis": len(market),
            "open_own_line_basis": len(own),
            "open_research_basis": len(research),
            "open_without_pick": len(open_rows) - len(with_pick),
            "flags": sum(len(r["flags"]) for r in rows),
            "rows_with_flags": len([r for r in rows if r["flags"]]),
        },
        "inputs": inputs_meta,
        "rating_file": {**vrs_meta, "anchors": anchor_counts},
        "rules": {
            "hotspawn_role": "fixture identity, kickoff/lock times, competition and tier only",
            "hotspawn_crowd_percent_used": False,
            "rungs": [
                "1 · book read directly (Pinnacle public guest response)",
                "2 · book relayed by bo3.gg (bookmaker match URL linked)",
                "3 · book relayed by EGamersWorld (aggregator-mediated)",
                "4 · prediction market (Polymarket traded prices)",
                "5 · own originated line (Valve Regional Standings + HLTV ranking, formula published)",
                "6 · research line for a team absent from the official standings (labelled, flagged)",
                "— · blank + flag when nothing above can be sourced",
            ],
            "never_averaged": "rungs are never averaged; the headline is the best available rung and the "
                              "others are shown beside it",
        },
    }


# ---------------------------------------------------------------------------
# invariants
# ---------------------------------------------------------------------------
def check_invariants(rows: list[dict], meta: dict) -> None:
    ids = [r["fixture_id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise BuildError("duplicate fixture ids in the consolidated board")
    if not rows:
        raise BuildError("no fixtures parsed from the input boards")
    for r in rows:
        if r["p_a_pct"] is None and r["p_b_pct"] is None:
            continue
        if r["p_a_pct"] is None or r["p_b_pct"] is None:
            raise BuildError(f"{r['fixture_id']}: only one side has a probability")
        total = r["p_a_pct"] + r["p_b_pct"]
        if abs(total - 100.0) > 0.25:
            raise BuildError(f"{r['fixture_id']}: probabilities sum to {total:.2f}, not 100")
        if not is_http(r["source_url"]):
            raise BuildError(f"{r['fixture_id']}: published probability without a source URL")
        if "hotspawn.com" in host_of(r["source_url"]):
            raise BuildError(f"{r['fixture_id']}: probability sourced from Hotspawn, which is forbidden")
        if r["pick"] and r["pick"] not in (r["team_a"], r["team_b"]):
            raise BuildError(f"{r['fixture_id']}: pick {r['pick']!r} is not one of the teams")
        if r["pick"] and r["p_a_pct"] == r["p_b_pct"]:
            raise BuildError(f"{r['fixture_id']}: pick published for an exact tie")
        if not r["read_utc"]:
            raise BuildError(f"{r['fixture_id']}: published probability without a read time")
    if meta["stale"]:
        raise BuildError(
            f"newest input capture is {meta['newest_input_age_hours']} h old "
            f"(limit {MAX_INPUT_AGE_HOURS} h); refusing to publish a stale board")


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------
CSS = """
:root{--bg:#0f1216;--panel:#171c22;--panel2:#1e242c;--line:#2b333d;--fg:#e8edf3;--muted:#9aa7b4;
--accent:#6d4bbd;--good:#3fb950;--warn:#d29922;--bad:#f85149}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:20px 14px 64px}
a{color:#8fb4ff}
h1{font-size:clamp(22px,5.4vw,32px);margin:0 0 6px;line-height:1.2}
h2{font-size:13.5px;letter-spacing:.07em;text-transform:uppercase;color:#cfd8e3;margin:26px 0 10px}
p{margin:8px 0}.lead{color:var(--muted)}.small{font-size:13px}.muted{color:var(--muted)}
.toplink{display:inline-block;margin:0 10px 8px 0;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.card h3{margin:0 0 4px;font-size:15px}.card p{margin:0;font-size:12.5px;color:var(--muted)}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.stat b{display:block;font-size:24px;line-height:1.2}.stat span{color:var(--muted);font-size:12px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px}
.note{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
border-radius:8px;padding:10px 12px;font-size:13px;color:var(--muted);margin:12px 0}
.note.warn{border-left-color:var(--warn)}
.tag{display:inline-block;font-size:10.5px;font-weight:700;border:1px solid var(--line);border-radius:999px;
padding:1px 7px;color:var(--muted);margin-right:4px;white-space:nowrap}
.tag.t1{border-color:var(--good);color:#7ee787}.tag.t2{border-color:#58a6ff;color:#a5d0ff}
.tag.t3{border-color:var(--warn);color:#e3b341}.tag.t4{border-color:var(--accent);color:#c9b6ff}
.tag.flag{border-color:var(--warn);color:#e3b341}
.filters{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 4px}
.filters button,.filters a{font:inherit;font-size:12.5px;background:var(--panel2);color:var(--fg);
border:1px solid var(--line);border-radius:999px;padding:5px 11px;text-decoration:none;cursor:pointer}
.filters button[aria-pressed="true"]{border-color:var(--accent);color:#c9b6ff}
.m{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px;margin:10px 0}
.m.locked{opacity:.62}
.m .head{display:flex;justify-content:space-between;gap:8px;align-items:baseline;flex-wrap:wrap}
.m .comp{font-size:12.5px;color:var(--muted)}
.m .when{font-size:12.5px;color:var(--muted);white-space:nowrap}
.m .teams{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:10px 0 6px}
.team{background:var(--panel2);border-radius:9px;padding:8px 10px;border:1px solid transparent}
.team.win{border-color:var(--good)}
.team .n{display:block;font-weight:650;font-size:14.5px;overflow-wrap:anywhere}
.team .p{display:block;font-size:20px;font-weight:700;margin-top:2px}
.bar{height:6px;background:#0b0e12;border-radius:999px;overflow:hidden;margin-top:5px}
.bar i{display:block;height:100%;background:var(--accent)}
.team.win .bar i{background:var(--good)}
.pick{margin:8px 0 4px;font-size:15px}
.pick b{color:#7ee787;font-size:16.5px}
.basis{font-size:12.5px;color:var(--muted);overflow-wrap:anywhere}
.basis a{overflow-wrap:anywhere}
details{margin-top:8px}summary{cursor:pointer;font-size:12.5px;color:#a9b7c6}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 6px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.tablewrap{overflow-x:auto;-webkit-overflow-scrolling:touch}
footer{color:var(--muted);font-size:12.5px;margin-top:34px;border-top:1px solid var(--line);padding-top:16px}
code{background:#0b0e12;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:12.5px}
ul{padding-left:20px}li{margin:3px 0;font-size:13.5px;color:#cfd8e3}
@media(min-width:760px){.wrap{padding:26px 20px 70px}}
"""


def render_style() -> str:
    return CSS.strip() + "\n"


def tag_class(rung: str) -> str:
    return {"market-1": "t1", "market-2": "t2", "market-3": "t3", "market-4": "t3",
            "own-line": "t4", "research": "t4"}.get(rung, "flag")


def match_card(row: dict, meta: dict) -> str:
    fid = row["fixture_id"]
    win_a = row["pick"] == row["team_a"]
    win_b = row["pick"] == row["team_b"]
    pa = f'{row["p_a_pct"]:.1f}%' if row["p_a_pct"] is not None else "—"
    pb = f'{row["p_b_pct"]:.1f}%' if row["p_b_pct"] is not None else "—"
    bar_a = f'{row["p_a_pct"]:.1f}' if row["p_a_pct"] is not None else "50"
    bar_b = f'{row["p_b_pct"]:.1f}' if row["p_b_pct"] is not None else "50"
    pick_txt = (f'<b>{esc(row["pick"])}</b> at <b>{row["pick_pct"]:.1f}%</b> '
                f'<span class="tag">{esc(row["confidence"])}</span>') if row["pick"] else \
        '<b class="muted">no pick published — nothing verifiable to base one on</b>'
    flags = "".join(f'<span class="tag flag">{esc(f)}</span>' for f in row["flags"])
    alt_rows = []
    for c in row["market_candidates"][1:]:
        alt_rows.append(f'<li>{esc(c["book"])} ({esc(c["rung_label"])}): {c["p_a"]:.1f}% / '
                        f'{c["p_b"]:.1f}% — read {esc(c["read_utc"] or "unknown")} — '
                        f'<a href="{esc(c["url"])}" rel="noopener">source</a></li>')
    own = row["own_line"]
    if own and row["basis_rung"] != "research":
        if own.get("p_a") is None:
            alt_rows.append('<li>our own line is <b>withheld</b> — the cited official rating row could not '
                            'be confirmed: '
                            + " · ".join(esc(v.get("detail", "")) for v in (own.get("verification") or {}).values())
                            + f' — <a href="{esc(own["rating_url_a"])}" rel="noopener">check line A</a> · '
                            f'<a href="{esc(own["rating_url_b"])}" rel="noopener">check line B</a></li>')
        else:
            alt_rows.append(f'<li>our own line ({esc(own["method"] or "method on file")}): '
                            f'{own["p_a"]:.1f}% / {own["p_b"]:.1f}% — '
                            f'<a href="{esc(own["rating_url_a"])}" rel="noopener">Valve standings (team A)</a> · '
                            f'<a href="{esc(own["rating_url_b"])}" rel="noopener">team B</a></li>')
    for r in row["research_lines"]:
        alt_rows.append(f'<li>{esc(r["source"])}: {r["p_a"]:.1f}% / {r["p_b"]:.1f}% — '
                        f'<a href="{esc(r["url"])}" rel="noopener">source</a></li>')
    alts = f'<details><summary>all published numbers for this match</summary><ul>{"".join(alt_rows)}</ul></details>' \
        if alt_rows else ""
    links = []
    if row["hotspawn_match_url"]:
        links.append(f'<a href="{esc(row["hotspawn_match_url"])}" rel="noopener">Hotspawn match page</a>')
    if row["hltv_match_url"]:
        links.append(f'<a href="{esc(row["hltv_match_url"])}" rel="noopener">HLTV match page (format/rosters)</a>')
    if row["source_url"]:
        links.append(f'<a href="{esc(row["source_url"])}" rel="noopener">source of the published line</a>')
    fmt = row["series_format"] or "format unknown"
    return f'''<article class="m{ ' locked' if row['state']=='locked' else '' }" id="{slug(fid)}"
 data-lock="{esc(row['lock_utc'])}" data-basis="{esc(row['basis_rung'])}"
 data-flag="{'1' if row['flags'] else '0'}" data-teams="{esc((row['team_a']+' '+row['team_b']).lower())}">
 <div class="head">
  <span class="comp">{esc(row['competition'])} · Tier {esc((row['tier'] or '?').upper())} · {esc(fmt)} · <code>{esc(fid)}</code></span>
  <span class="when" data-lock-label>locks {esc(row['lock_utc'] or 'time unknown')} UTC</span>
 </div>
 <div class="teams">
  <div class="team{' win' if win_a else ''}"><span class="n">{esc(row['team_a'])}</span><span class="p">{pa}</span>
   <div class="bar"><i style="width:{bar_a}%"></i></div></div>
  <div class="team{' win' if win_b else ''}"><span class="n">{esc(row['team_b'])}</span><span class="p">{pb}</span>
   <div class="bar"><i style="width:{bar_b}%"></i></div></div>
 </div>
 <p class="pick">PICK: {pick_txt}</p>
 <p class="basis"><span class="tag {tag_class(row['basis_rung'])}">{esc(row['basis_label'])}</span>
  read {esc(row['read_utc'] or '—')} · {esc(row['basis_detail'])}<br>
  {' · '.join(links)}</p>
 {alts}
 <p class="basis">{flags}</p>
</article>'''


def render_index(rows: list[dict], flags: list[dict], meta: dict) -> str:
    c = meta["counts"]
    cards = "\n".join(match_card(r, meta) for r in rows)
    srcs = " · ".join(
        f'<a href="../{esc(i["page"])}">{esc(i["label"])}</a> (as of {esc(i["captured_utc"] or "unknown")})'
        for i in meta["inputs"])
    stale_note = ('<div class="note warn"><b>Inputs are stale.</b> The newest capture behind this page is '
                  f'{meta["newest_input_age_hours"]} h old (limit {meta["max_input_age_hours"]} h); the build '
                  'refuses to republish in that state, so this copy is the last verified one.</div>'
                  ) if meta["stale"] else ""
    top_links = "".join([
        '<a class="toplink" href="index.html"><b>All picks (this board)</b></a>',
        '<a class="toplink" href="flagged.html">Flagged for Review</a>',
        '<a class="toplink" href="methodology.html">How the numbers are chosen</a>',
        '<a class="toplink" href="sources.html">Sources &amp; read times</a>',
        '<a class="toplink" href="data/picks.csv">picks.csv</a>',
        '<a class="toplink" href="data/picks.json">picks.json</a>',
        '<a class="toplink" href="../index.html">← Site home</a>',
    ])
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Every CS2 match · picks &amp; probabilities | Hotspawn independent lines</title>
<meta name="description" content="One row for every open Counter-Strike 2 match on the Hotspawn Pick'em board: both win probabilities from outside betting lines or our own originated line, the explicit pick and the source link behind every number.">
<link rel="stylesheet" href="style.css"></head><body><main class="wrap">
<p class="small">{top_links}</p>
<h1>Every open CS2 match — pick &amp; probability</h1>
<p class="lead">One card per open fixture on the <a href="https://play.hotspawn.com/cs2-pickems" rel="noopener">Hotspawn CS2 Pick'em board</a>.
Hotspawn supplies <b>fixture identity and lock times only</b>; every probability comes from an outside
betting line or from this project's own originated line, each with the source link and the minute it was read.
Crowd pick percentages are never used.</p>
{stale_note}
<div class="stats">
 <div class="stat"><b>{c['open']}</b><span>open matches</span></div>
 <div class="stat"><b>{c['open_with_pick']}</b><span>have a pick</span></div>
 <div class="stat"><b>{c['open_market_basis']}</b><span>from outside markets</span></div>
 <div class="stat"><b>{c['open_own_line_basis']}</b><span>from our own line</span></div>
 <div class="stat"><b>{c['open_research_basis']}</b><span>research line (flagged)</span></div>
 <div class="stat"><b>{c['open_without_pick']}</b><span>blank &amp; flagged</span></div>
</div>
<div class="note"><b>Data as of {esc(meta['data_as_of_utc'] or 'unknown')}</b> — assembled from the boards below.
{CADENCE_TEXT} Rungs are never averaged: the headline is the best available rung and every other published
number for the match is listed under “all published numbers”. Build {esc(meta['generated_for_utc'])}.
<br><br>{srcs}</div>
<h2>The board</h2>
<div class="filters" role="group" aria-label="Filter matches">
 <button type="button" data-filter="all" aria-pressed="true">All {len(rows)}</button>
 <button type="button" data-filter="market" aria-pressed="false">Outside market</button>
 <button type="button" data-filter="own" aria-pressed="false">Own line</button>
 <button type="button" data-filter="research" aria-pressed="false">Research</button>
 <button type="button" data-filter="flag" aria-pressed="false">Flagged</button>
 <button type="button" data-filter="open" aria-pressed="false">Not locked</button>
</div>
<p class="small muted" id="filter-note">Times show in your device's local zone when JavaScript is available; the stored times are UTC.</p>
{cards}
<footer>
 <p><b>Rules.</b> A pick is published only when its probability has a source URL and a read time. Rungs are
 never averaged. Values that cannot be confirmed stay blank and are flagged on
 <a href="flagged.html">Flagged for Review</a>. No Hotspawn crowd percentage is read, stored or shown.</p>
 <p>Probability labels: <b>market</b> = de-vigged price of a bookmaker or prediction market;
 <b>own line</b> = Valve Regional Standings + HLTV ranking through the published formula, provisional and
 uncalibrated; <b>research</b> = labelled estimate for a team absent from the official standings, flagged as
 unverified. Analysis only, not betting advice.</p>
 <p class="small">Machine-readable: <a href="data/picks.csv">picks.csv</a> ·
 <a href="data/picks.json">picks.json</a> · <a href="data/coverage.json">coverage.json</a> ·
 <a href="data/sources.csv">sources.csv</a></p>
</footer>
</main><script src="app.js"></script></body></html>
'''


def render_flagged(rows: list[dict], flags: list[dict], meta: dict) -> str:
    body = []
    published_ids = {r["fixture_id"] for r in rows}
    for f in flags:
        seen_pairs = set()
        row_list = []
        for r in f["rows"]:
            key = (r["fixture_id"], r["detail"])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            link = f' — <a href="{esc(r["source_url"])}" rel="noopener">source</a>' if is_http(r["source_url"]) else ""
            detail = f' <span class="muted">({esc(r["detail"])})</span>' if r.get("detail") else ""
            fid = r["fixture_id"]
            label = (f'<a href="../console/index.html#{slug(fid)}">{esc(fid)}</a>'
                     if fid in published_ids else f'<b>{esc(fid)}</b> (not in this captured slate)')
            row_list.append(f'<li>{label}{link}{detail}</li>')
        body.append(f'''<section class="m"><div class="head"><b><code>{esc(f["code"])}</code></b>
 <span class="muted">{len(f["rows"])} row(s)</span></div>
 <p class="basis">{esc(f["meaning"])}</p><ul>{''.join(row_list)}</ul></section>''')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Flagged for Review | Consolidated CS2 picks board</title>
<link rel="stylesheet" href="style.css"></head><body><main class="wrap">
<p class="small"><a href="index.html">← All picks</a> · <a href="methodology.html">Method</a> ·
<a href="sources.html">Sources</a> · <a href="../index.html">Site home</a></p>
<h1>Flagged for Review</h1>
<p class="lead">Every condition that makes a row on this board less than fully verified, with the fixtures it
affects and the source link to check by hand. Flags never block publication of the underlying figures —
they mark them.</p>
<div class="note">Data as of {esc(meta['data_as_of_utc'] or 'unknown')}. {len(flags)} flag codes across
{meta['counts']['rows']} rows. Registered at row level on
<a href="index.html">the board</a> and reproduced here with counts.
<code>R-228-*</code> entries are curated manual-review findings maintained in
<code>console/data/review_findings.csv</code>; the site-level irregularities IR-228-01..03 found by this
integration are fixed and documented in
<a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/reviews/228bb5bc-verification.md" rel="noopener">the review record</a>.</div>
{''.join(body)}
<footer><p class="small">These flags are informative, not blockers: the brief requires unverified values to be
published blank and flagged rather than guessed or silently dropped.</p></footer>
</main></body></html>
'''


def render_methodology(meta: dict) -> str:
    rungs = "".join(f"<li>{esc(r)}</li>" for r in meta["rules"]["rungs"])
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Method | Consolidated CS2 picks board</title>
<link rel="stylesheet" href="style.css"></head><body><main class="wrap">
<p class="small"><a href="index.html">← All picks</a> · <a href="flagged.html">Flagged for Review</a> ·
<a href="sources.html">Sources</a> · <a href="../index.html">Site home</a></p>
<h1>How every number on this board is chosen</h1>
<h2>What Hotspawn is used for</h2>
<p class="lead">{esc(meta["rules"]["hotspawn_role"])}. Hotspawn's crowd pick percentage is
<b>never</b> read as an input and is never displayed as a probability
(<code>hotspawn_crowd_percent_used = false</code> in <a href="data/coverage.json">coverage.json</a>).</p>
<h2>The rungs</h2>
<ol>{rungs}</ol>
<p>{esc(meta["rules"]["never_averaged"])}. A lower rung is shown as a cross-check, never blended in.</p>
<h2>What the probability labels mean</h2>
<ul>
 <li><b>Market</b> — the de-vigged two-way price of an outside market. Rungs 1–4 above, in order:
  a book read directly, then a book relayed by an aggregator, then a prediction market.</li>
 <li><b>Own line</b> — our originated line from the official Valve Regional Standings plus the HLTV world
  ranking, pushed through a published logistic formula and the sourced series-format transform
  (BO1 <code>p</code>, BO3 <code>p²(3−2p)</code>, BO5 <code>p³(10−15p+6p²)</code>, k = 0.4568).
  This is a provisional, uncalibrated model, published as such, with the arithmetic on
  <a href="../picks-full/own-lines.html">picks-full/own-lines.html</a>.</li>
 <li><b>Research</b> — a labelled estimate for a team absent from the official standings
  (roster-mapped); published only with flag <code>C-RESEARCH-LINE</code>, with every research estimate for
  the fixture shown as a range.</li>
 <li><b>Blank + flag</b> — nothing above could be sourced. No value is invented, inferred or copied from
  another fixture.</li>
</ul>
<h2>Confidence labels</h2>
<ul>
 <li><b>heavy favourite</b> — pick probability ≥ 70%</li>
 <li><b>strong favourite</b> — 60–69.9% · <b>slight favourite</b> — 55–59.9% · <b>narrow favourite</b> — 50–54.9%</li>
 <li><b>coin-flip</b> — the two sides are within 2 points (<code>C-THIN-MARKET</code>)</li>
</ul>
<h2>Freshness and failure behaviour</h2>
<p>This page is assembled from the committed captures of the source boards listed on
<a href="sources.html">Sources</a>. It is rebuilt on every schedule run and on every change to those files.
If the newest input is more than {meta["max_input_age_hours"]} hours old the build fails closed: nothing is
republished and the last verified copy stays live. Data as of {esc(meta['data_as_of_utc'] or 'unknown')}.</p>
<h2>What this board does not claim</h2>
<ul>
 <li>It does not guarantee live coverage: a source can refuse automated access or a match can be listed
  without any market.</li>
 <li>It does not treat an aggregator-reported price as verified at the book itself; the bookmaker's own
  match URL is linked on the row so it can be checked by hand.</li>
 <li>It publishes probabilities, not certainties. Analysis only, not betting advice.</li>
</ul>
</main></body></html>
'''


def render_sources(meta: dict) -> str:
    rf = meta.get("rating_file") or {}
    anc = rf.get("anchors") or {}
    rating_note = {
        "file": rf.get("file", "n/a"),
        "sha": (rf.get("sha256") or "n/a")[:16] + "…",
        "integrity": " — matches the hash the picks board published" if rf.get("integrity_ok") else
                     " — HASH MISMATCH, treat the ratings as unverified",
        "verified": anc.get("verified", 0),
        "alias": anc.get("alias", 0),
        "absent": anc.get("absent", 0) + anc.get("unverified", 0),
    }
    rating_note_html = (
        '<div class="note">The own originated lines are re-checked here: every cited Valve Regional '
        'Standings link is opened in the committed copy of the official file '
        f'(<code>{esc(rating_note["file"])}</code>, SHA-256 <code>{esc(rating_note["sha"])}</code>'
        f'{esc(rating_note["integrity"])}) and the line named by the URL anchor is confirmed to be the '
        'team (or a documented, evidence-linked alias) with the same points. '
        f'{rating_note["verified"]} anchors re-checked exactly, {rating_note["alias"]} resolved through a '
        f'documented alias, {rating_note["absent"]} not present (the labelled research line).</div>')
    rows = []
    for i in meta["inputs"]:
        rows.append(f'<tr><td><a href="../{esc(i["page"])}">{esc(i["label"])}</a></td>'
                    f'<td><code>{esc(i["file"])}</code></td><td>{esc(i["captured_utc"] or "unknown")}</td>'
                    f'<td class="small"><code>{esc(i["sha256"][:16])}…</code></td>'
                    f'<td>{i["rows"]}</td></tr>')
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sources | Consolidated CS2 picks board</title>
<link rel="stylesheet" href="style.css"></head><body><main class="wrap">
<p class="small"><a href="index.html">← All picks</a> · <a href="flagged.html">Flagged for Review</a> ·
<a href="methodology.html">Method</a> · <a href="../index.html">Site home</a></p>
<h1>Sources behind this board</h1>
<p class="lead">This page is assembled from committed captures only; it never calls a source itself. Each row
below links to the board that made the capture, with the file, its capture time and the SHA-256 of the exact
file read.</p>
<p class="lead" id="rating-check">{rating_note}</p>
<div class="tablewrap"><table><thead><tr><th>Board</th><th>File</th><th>Captured (UTC)</th>
<th>SHA-256 (head)</th><th>Rows</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
{rating_note_html}
<h2>Curated manual-review findings</h2>
<div class="note">Hand-maintained findings that are not derivable from the input files live in
<a href="data/review_findings.csv">data/review_findings.csv</a> and are rendered on the
<a href="flagged.html">Flagged for Review</a> page as <code>R-228-*</code> entries: the
PCIFIC/WRAITH PCIFIC name variant, the Envy/3DMAX alias location, the Pinnacle endpoint-only
citation and the EGamersWorld CI refusal.</div>
<h2>Original sources those boards read</h2>
<div class="tablewrap"><table><thead><tr><th>Source</th><th>What it provides</th><th>Where</th></tr></thead><tbody>
<tr><td>Hotspawn Pick'em</td><td>Fixture identity, teams, competition, tier, kickoff and lock epoch — never a probability</td><td><a href="https://play.hotspawn.com/cs2-pickems" rel="noopener">play.hotspawn.com/cs2-pickems</a></td></tr>
<tr><td>Pinnacle (public guest response)</td><td>Bookmaker moneyline, read directly</td><td><a href="https://www.pinnacle.com/en/esports/games/cs2/matchups/" rel="noopener">pinnacle.com CS2 matchups</a></td></tr>
<tr><td>bo3.gg public API</td><td>Bookmaker odds relayed with the bookmaker match URL, plus series format</td><td><a href="https://bo3.gg/matches" rel="noopener">bo3.gg/matches</a></td></tr>
<tr><td>EGamersWorld</td><td>Aggregator-reported bc.game odds (labelled, not verified at the book)</td><td><a href="https://egamersworld.com/counterstrike/matches" rel="noopener">egamersworld.com</a></td></tr>
<tr><td>Polymarket</td><td>Prediction-market traded prices for the same fixtures</td><td><a href="https://polymarket.com/esports/cs2" rel="noopener">polymarket.com/esports/cs2</a></td></tr>
<tr><td>Valve Regional Standings</td><td>Official rating points behind the own originated line</td><td><a href="https://github.com/ValveSoftware/counter-strike_regional_standings" rel="noopener">ValveSoftware/counter-strike_regional_standings</a></td></tr>
<tr><td>HLTV</td><td>World ranking, match pages (series format, rosters, results)</td><td><a href="https://www.hltv.org/ranking/teams" rel="noopener">hltv.org/ranking/teams</a></td></tr>
</tbody></table></div>
<footer><p class="small">Data as of {esc(meta['data_as_of_utc'] or 'unknown')}.
Rows whose source refused automated access are blank and flagged, never filled in.</p></footer>
</main></body></html>
'''


APP_JS = """
// Mobile helpers only: the full board is server-rendered, so it works without this file.
(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll('.m'));
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.filters button'));
  function apply(kind) {
    cards.forEach(function (c) {
      var basis = c.getAttribute('data-basis') || '';
      var show = true;
      if (kind === 'market') show = basis.indexOf('market') === 0;
      else if (kind === 'own') show = basis === 'own-line' || basis === 'research';
      else if (kind === 'research') show = basis === 'research';
      else if (kind === 'flag') show = c.getAttribute('data-flag') === '1';
      else if (kind === 'open') show = !c.classList.contains('locked');
      c.style.display = show ? '' : 'none';
    });
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-filter') === kind)); });
  }
  buttons.forEach(function (b) {
    b.addEventListener('click', function () { apply(b.getAttribute('data-filter')); });
  });
  function localise() {
    cards.forEach(function (c) {
      var iso = c.getAttribute('data-lock');
      if (!iso) return;
      var t = new Date(iso);
      if (isNaN(t.getTime())) return;
      var label = c.querySelector('[data-lock-label]');
      var rel = '';
      var diff = t.getTime() - Date.now();
      if (diff <= 0) { rel = ' · locked'; c.classList.add('locked'); }
      else {
        var h = Math.floor(diff / 3600000), m = Math.round((diff % 3600000) / 60000);
        rel = ' · in ' + (h > 0 ? h + 'h ' : '') + m + 'm';
      }
      if (label) label.textContent = 'locks ' + t.toLocaleString() + rel;
    });
  }
  localise();
  setInterval(localise, 60000);
})();
"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def write_outputs(rows: list[dict], flags: list[dict], meta: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)

    csv_cols = [
        "fixture_id", "competition", "tier", "team_a", "team_b", "start_utc", "lock_utc", "state",
        "series_format", "series_format_source", "basis_rung", "basis_label", "basis_detail",
        "p_a_pct", "p_b_pct", "pick", "pick_pct", "margin_pp", "confidence",
        "source_url", "read_utc", "hltv_match_url", "hotspawn_match_url", "flags", "board_flags",
    ]
    with (DATA / "picks.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=csv_cols, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            out = {k: (f"{r[k]:.1f}" if isinstance(r.get(k), float) else r.get(k, "")) for k in csv_cols}
            out["flags"] = ";".join(r["flags"])
            w.writerow(out)

    json_rows = []
    for r in rows:
        j = {k: v for k, v in r.items() if k not in ("market_candidates", "own_line", "research_lines")}
        j["market_candidates"] = r["market_candidates"]
        j["own_line"] = r["own_line"]
        j["research_lines"] = r["research_lines"]
        json_rows.append(j)
    (DATA / "picks.json").write_text(json.dumps({
        "meta": meta, "rules": meta["rules"], "rows": json_rows,
    }, indent=1, sort_keys=False), encoding="utf-8")

    (DATA / "coverage.json").write_text(json.dumps(meta, indent=1, sort_keys=False), encoding="utf-8")

    with (DATA / "sources.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["board", "file", "page", "captured_utc", "sha256", "rows"])
        for i in meta["inputs"]:
            w.writerow([i["label"], i["file"], i["page"], i["captured_utc"], i["sha256"], i["rows"]])

    with (DATA / "flags.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["code", "rows", "meaning", "fixtures"])
        for f in flags:
            w.writerow([f["code"], len(f["rows"]), f["meaning"],
                        ";".join(sorted({r["fixture_id"] for r in f["rows"]}))])

    (OUT / "index.html").write_text(render_index(rows, flags, meta), encoding="utf-8")
    (OUT / "flagged.html").write_text(render_flagged(rows, flags, meta), encoding="utf-8")
    (OUT / "methodology.html").write_text(render_methodology(meta), encoding="utf-8")
    (OUT / "sources.html").write_text(render_sources(meta), encoding="utf-8")
    (OUT / "style.css").write_text(render_style(), encoding="utf-8")
    (OUT / "app.js").write_text(APP_JS, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    now_env = os.environ.get("CONSOLE_NOW_UTC", "").strip()
    now = parse_utc(now_env) if now_env else datetime.now(timezone.utc)
    inputs, _ = load_inputs(now)
    rows, flags, meta = build_rows(inputs, now)
    check_invariants(rows, meta)
    write_outputs(rows, flags, meta)
    c = meta["counts"]
    print(f"[console] {c['open']} open / {c['rows']} rows · {c['open_with_pick']} picks "
          f"({c['open_market_basis']} market, {c['open_own_line_basis']} own line, "
          f"{c['open_research_basis']} research) · {c['open_without_pick']} blank · "
          f"data as of {meta['data_as_of_utc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
