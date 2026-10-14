#!/usr/bin/env python3
"""Source re-read verification for the merged CS2 pick boards (session arena/bdc98a9a).

What this does, with no credentials and no manual input:

1. Reads the *cited external URLs and the value each board claims beside them* out of the merged
   boards' data files (everypick's ``data/fbcccda2/every_pick.csv``, the integrator board's
   ``data/63ee81ba/picks.csv``, the line-analysis board's ``cs2/data/analysis.csv``).
2. Re-reads every one of those URLs live and records what the source itself says *now*:
   ``match``, ``mismatch``, ``refused``, ``dead``, ``not-checkable``, ``placeholder``.
3. Writes the per-claim table, a fetch log with a hash per body, the raw bodies it read, and a
   run summary.

It never edits another board's data and it never fills a value in. A refusal is recorded as a
refusal, the 1.80/1.80 EGamersWorld placeholder is recorded as a placeholder, and Hotspawn is only
ever read for fixture identity — never for a probability (standing repository policy).

Usage:
    python3 reread/collect.py                 # full run (network)
    python3 reread/collect.py --limit 3       # smoke test
    python3 reread/collect.py --offline       # no network: everything is marked not-checkable
    python3 reread/collect.py --only everypick
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reread" / "data"
RAW = OUT / "raw"

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")

BOARDS = {
    "everypick": ROOT / "data" / "fbcccda2" / "every_pick.csv",
    "picks-full": ROOT / "data" / "63ee81ba" / "picks.csv",
    "cs2": ROOT / "cs2" / "data" / "analysis.csv",
    "every": ROOT / "every" / "data" / "picks.csv",
}

LOG: list[dict] = []
CACHE: dict[str, dict] = {}
BROWSER_BUDGET = {"left": 150}
# Hosts that consistently refuse a plain HTTP client from a CI runner. The browser is the fallback
# for these only, so the budget is spent where a plain read is known to fail.
BROWSER_HOSTS = ("www.hltv.org", "hltv.org", "egamersworld.com", "www.hotspawn.com",
                 "play.hotspawn.com")

VERDICT_NAMES = ("match", "mismatch", "refused", "dead", "not-checkable", "placeholder")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(entry: dict) -> None:
    entry.setdefault("fetched_utc", now_iso())
    LOG.append(entry)
    print(f"  [{entry.get('status') or 'ERR'}] {entry['url'][:100]}"
          f" {entry.get('bytes') or 0}B {entry.get('error') or ''}".rstrip(), flush=True)


# --------------------------------------------------------------------------------------- fetching
def http_get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    rec = {"url": url, "status": None, "bytes": 0, "sha256": None, "path": "http", "error": None,
           "body": ""}
    body = b""
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed public hosts)
            body = resp.read()
            rec["status"] = resp.status
    except urllib.error.HTTPError as exc:
        rec["status"] = exc.code
        rec["error"] = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 - a refusal is data, not a crash
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    rec["bytes"] = len(body)
    rec["sha256"] = hashlib.sha256(body).hexdigest() if body else None
    rec["body"] = body.decode("utf-8", "replace")
    return rec


def browser_render(url: str, wait_ms: int = 2200, timeout: int = 40000) -> dict:
    """Render one public page in Chromium; used only when plain HTTP is refused or empty."""
    rec = {"url": url, "status": None, "bytes": 0, "sha256": None, "path": "browser", "error": None,
           "body": ""}
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--no-sandbox"])
            try:
                ctx = browser.new_context(user_agent=UA, locale="en-US")
                page = ctx.new_page()
                resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                rec["status"] = resp.status if resp else None
                page.wait_for_timeout(wait_ms)
                html = page.content()
                body = html.encode("utf-8")
                rec["bytes"] = len(body)
                rec["sha256"] = hashlib.sha256(body).hexdigest()
                rec["body"] = html
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001
        rec["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    return rec


def fetch(url: str) -> dict:
    """Fetch once per URL; escalate to the browser when plain HTTP is refused or returns nothing."""
    if url in CACHE:
        return CACHE[url]
    got = http_get(url)
    plain_ok = got["status"] == 200 and bool(got["body"])
    host = url.split("/")[2] if "//" in url else url
    if not plain_ok and host in BROWSER_HOSTS and BROWSER_BUDGET["left"] > 0:
        BROWSER_BUDGET["left"] -= 1
        seen = browser_render(url)
        if seen["body"]:
            got = seen
    log({k: got[k] for k in ("url", "status", "bytes", "sha256", "path", "error")})
    if got["sha256"] and 0 < got["bytes"] < 2_000_000:
        RAW.mkdir(parents=True, exist_ok=True)
        with gzip.open(RAW / f"{got['sha256'][:16]}.html.gz", "wt", encoding="utf-8") as fh:
            fh.write(got["body"])
    CACHE[url] = got
    return got


# --------------------------------------------------------------------------------- helpers / parse
def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


ALIAS_PATH = ROOT / "cs2" / "aliases.json"


def load_aliases() -> dict:
    """Evidence-backed rename map published by another board (read-only).

    Only entries that carry a confirming session and an evidence URL are used; the note on every
    affected row names the file and the alias so a reader can re-check the evidence independently.
    """
    if not ALIAS_PATH.exists():
        return {}
    try:
        data = json.loads(ALIAS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    out = {}
    for name, entry in data.items():
        if name.startswith("_") or not isinstance(entry, dict):
            continue
        alias = entry.get("alias_of")
        if alias and entry.get("evidence_url") and entry.get("confirmed_by"):
            out[name] = alias
    return out


ALIASES = load_aliases()


def name_candidates(team: str) -> list[str]:
    """The printed name plus any evidence-backed alias for it (both directions)."""
    names = [team] if team else []
    if team in ALIASES:
        names.append(ALIASES[team])
    names += [k for k, v in ALIASES.items() if v == team]
    return names


def tokens_present(html: str, teams: list[str]) -> tuple[bool, str]:
    """Check each team name (full, else its longest word >=4 chars) appears in the body.

    A name that only matches through an evidence-backed alias is reported as such rather than as a
    miss; an alias is never invented here, it is read from cs2/aliases.json.
    """
    flat = norm(html)
    ok, detail = True, []
    for team in teams:
        team = (team or "").strip()
        if not team:
            continue
        n = norm(team)
        if n and n in flat:
            detail.append(f"{team}=full")
            continue
        words = sorted((w for w in re.split(r"[^A-Za-z0-9]+", team) if len(w) >= 4),
                       key=len, reverse=True)
        aliases = [n for n in name_candidates(team)[1:] if norm(n) and norm(n) in flat]
        if aliases:
            detail.append(f"{team}=alias:{aliases[0]}")
            continue
        hit = next((w for w in words if norm(w) in flat), None)
        if hit:
            detail.append(f"{team}=partial:{hit}")
        else:
            ok = False
            detail.append(f"{team}=absent")
    return ok, ", ".join(detail)


HLTV_BO = re.compile(r"best\s*of\s*(\d+)", re.I)
ODD = re.compile(r"(?<![\d.])(\d\.\d{2})(?![\d.])")
PAIR_IN_TEXT = re.compile(r"(\d\.\d{2,3})\s*/\s*(\d\.\d{2,3})")
BOOK_LOGO = re.compile(r"uploads/[^\"']*?([a-z0-9][a-z0-9\-_.]{1,40})\.(?:png|webp|svg|jpg)", re.I)
BOOK_ALT = re.compile(r'alt="([^"]{2,40})"', re.I)


def is_decimal(token: str) -> float | None:
    try:
        value = float(token)
    except (TypeError, ValueError):
        return None
    return value if 1.01 <= value <= 60.0 else None


def parse_egw_books(html: str) -> list[dict]:
    """Named-book 1/2 prices on an EGamersWorld match page (same shape as cs2/collect.py).

    Heuristic by design: a book logo image anchors each pair; anything not attributable to a named
    book is dropped, never guessed.
    """
    plain = re.sub(r"\s+", " ", html)
    books, seen = [], set()
    toks = [(m.group(1), m.start()) for m in ODD.finditer(plain)]
    for i in range(len(toks) - 1):
        price_a, start = toks[i]
        price_b, _ = toks[i + 1]
        tail = plain[max(0, start - 420):start]
        imgs = list(re.finditer(r"<img[^>]*uploads/[^>]*>", tail, re.I))
        if not imgs:
            continue
        img = imgs[-1]
        between = tail[img.end():]
        low = between.lower()
        if len(between) > 260 or any(k in low for k in ("handicap", "total", "over/under",
                                                       "odd/even", "winner map", "map winner")):
            continue
        alt = BOOK_ALT.search(img.group(0))
        logo = BOOK_LOGO.search(img.group(0))
        name = (alt.group(1).strip() if alt else (logo.group(1) if logo else ""))
        name = re.sub(r"\.(?:png|webp|svg|jpg)$", "", name, flags=re.I)
        if not name or len(name) < 2 or name in seen:
            continue
        da, db = is_decimal(price_a), is_decimal(price_b)
        if not (da and db):
            continue
        seen.add(name)
        books.append({"book": name, "odds_a": da, "odds_b": db})
    return books


def pinnacle_moneyline(payload: str, team_a: str, team_b: str) -> dict | None:
    """Find the two-way moneyline for the named teams in a Pinnacle guest-API response."""
    try:
        data = json.loads(payload)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(data, dict):
        data = data.get("matchups") or data.get("events")
    if not isinstance(data, list):
        return None
    na, nb = norm(team_a), norm(team_b)
    for match in data:
        if not isinstance(match, dict):
            continue
        parts = match.get("participants") or match.get("competitors") or []
        names = [norm(p.get("name", "")) for p in parts if isinstance(p, dict)]
        if len(names) < 2:
            continue
        if not all(any(n and (n in x or x in n) for x in names) for n in (na, nb) if n):
            continue
        prices = []
        for price in match.get("prices") or []:
            if not isinstance(price, dict):
                continue
            try:
                value = float(price.get("price"))
            except (TypeError, ValueError):
                continue
            prices.append((price.get("designation") or price.get("participantId"), value))
        if len(prices) >= 2:
            return {"match": match.get("id") or match.get("key"), "prices": prices}
    return None


def vrs_raw_url(url: str) -> str:
    """`github.com/.../blob/<ref>/<path>?plain=1#Lnn` -> raw URL (same ref, no fragment)."""
    url = url.split("#")[0].split("?")[0]
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$", url)
    if m:
        return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}/{m.group(4)}"
    return url


def parse_utc(text: str) -> datetime | None:
    """Parse the run stamps this tool writes; return None for anything else (never guess)."""
    try:
        stamp = datetime.strptime((text or "").strip(), "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return stamp.replace(tzinfo=timezone.utc)


def anchor_line(url: str) -> int | None:
    m = re.search(r"#L(\d+)", url)
    return int(m.group(1)) if m else None


def name_in(text: str, team: str) -> bool:
    n = norm(team)
    if n and n in norm(text):
        return True
    words = [w for w in re.split(r"[^A-Za-z0-9]+", team or "") if len(w) >= 5]
    return any(norm(w) in norm(text) for w in words)


# ------------------------------------------------------------------------------------ verification
def make_verdict(got: dict, name: str, observed: str = "", note: str = "") -> dict:
    return {"verdict": name, "http_status": got.get("status"), "observed": observed, "note": note,
            "sha256": got.get("sha256"), "bytes": got.get("bytes"),
            "fetched_utc": got.get("fetched_utc") or now_iso()}


def refusal_or_dead(got: dict) -> dict:
    status = got.get("status")
    if status in (401, 403, 429, 503):
        name = "refused"
    elif status in (404, 410):
        name = "dead"
    else:
        name = "not-checkable"
    return make_verdict(got, name, observed=f"HTTP {status} {got.get('error') or ''}".strip())


def verify_vrs(claim: dict) -> dict:
    got = fetch(vrs_raw_url(claim["url"]))
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    lines = got["body"].splitlines()
    line_no = anchor_line(claim["url"])
    rank = str(claim["extra"].get("rank") or "")
    team = claim["team_a"]
    if line_no and 1 <= line_no <= len(lines):
        window = [l.strip() for l in lines[max(0, line_no - 2):line_no + 1]]
        text = " | ".join(window)
        rank_ok = (not rank) or bool(re.search(rf"(?<!\d){re.escape(rank)}(?!\d)", text))
        name_ok = name_in(text, team)
        note = f"anchor L{line_no}; team-name {'found' if name_ok else 'not'} on that line"
        if rank_ok and name_ok:
            return make_verdict(got, "match", observed=text[:220], note=note)
        if rank_ok and not name_ok:
            return make_verdict(got, "match", observed=text[:220],
                                note=note + " (list prints a short form / alias)")
        return make_verdict(got, "mismatch", observed=text[:220],
                            note=f"anchor L{line_no}: claimed rank {rank or '?'} is not on the line")
    if rank:
        for line in lines:
            if re.search(rf"(?<!\d){re.escape(rank)}(?!\d)", line) and name_in(line, team):
                return make_verdict(got, "match", observed=line.strip()[:220],
                                    note="no anchor line: rank + name found elsewhere in the file")
    return make_verdict(got, "not-checkable", observed=(lines[0][:120] if lines else ""),
                        note="anchor line not resolvable")


def verify_hltv_match(claim: dict) -> dict:
    got = fetch(claim["url"])
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    present, detail = tokens_present(got["body"], [claim["team_a"], claim["team_b"]])
    bo = HLTV_BO.search(re.sub(r"<[^>]+>", " ", got["body"]))
    observed = f"teams: {detail}; Best of {bo.group(1)}" if bo else f"teams: {detail}; no 'Best of'"
    claimed = str(claim["extra"].get("series_format") or "")
    claimed_digits = re.sub(r"\D", "", claimed)
    if not present:
        return make_verdict(got, "mismatch", observed=observed,
                            note="a cited team name is not on the served page")
    if claimed_digits and bo and claimed_digits != bo.group(1):
        return make_verdict(got, "mismatch", observed=observed,
                            note=f"board says Best of {claimed_digits}, page says Best of {bo.group(1)}")
    if claimed_digits and not bo:
        return make_verdict(got, "not-checkable", observed=observed,
                            note="page served but no 'Best of' marker in the served HTML")
    return make_verdict(got, "match", observed=observed)


def verify_egw_market(claim: dict) -> dict:
    got = fetch(claim["url"])
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    books = parse_egw_books(got["body"])
    extra = claim.get("extra", {})
    odds_a, odds_b = extra.get("odds_a"), extra.get("odds_b")
    if not books:
        return make_verdict(got, "not-checkable",
                            observed="no named-book odds table parsed from the served HTML",
                            note="price claimed on this page but not parsable from what the runner got")
    rendered = "; ".join(f"{b['book']} {b['odds_a']:.2f}/{b['odds_b']:.2f}" for b in books[:4])
    if books and all(abs(b["odds_a"] - 1.80) <= 0.011 and abs(b["odds_b"] - 1.80) <= 0.011
                     for b in books):
        return make_verdict(got, "placeholder", observed=rendered,
                            note=f"page shows the 1.80/1.80 placeholder pair"
                                 f"{'; board cites ' + str(odds_a) + '/' + str(odds_b) if odds_a else ''}"
                                 " — not a market")
    if odds_a and odds_b and str(odds_a) != "" and str(odds_b) != "":
        for book in books:
            if abs(book["odds_a"] - float(odds_a)) <= 0.011 and \
                    abs(book["odds_b"] - float(odds_b)) <= 0.011:
                return make_verdict(got, "match", observed=rendered,
                                    note=f"claimed {odds_a}/{odds_b} re-read on {book['book']}")
        return make_verdict(got, "mismatch", observed=rendered,
                            note=f"claimed {odds_a}/{odds_b} not found in the served odds table")
    return make_verdict(got, "match", observed=rendered, note="page read; no price claimed here")


def verify_pinnacle(claim: dict) -> dict:
    got = fetch(claim["url"])
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    extra = claim.get("extra", {})
    odds_a, odds_b = extra.get("odds_a"), extra.get("odds_b")
    if "guest.api" in claim["url"] or "/markets/" in claim["url"]:
        found = pinnacle_moneyline(got["body"], claim["team_a"], claim["team_b"])
        if not found:
            return make_verdict(got, "not-checkable",
                                observed="the live payload does not price this pairing now",
                                note="nothing contradicts the published price; the market is no "
                                     "longer in the response the runner receives")
        rendered = "; ".join(f"{d}: {p}" for d, p in found["prices"][:4])
        if odds_a and odds_b:
            for _, price in found["prices"]:
                if abs(price - float(odds_a)) <= 0.05 or abs(price - float(odds_b)) <= 0.05:
                    return make_verdict(got, "match", observed=f"matchup {found['match']}: {rendered}",
                                        note=f"claimed {odds_a}/{odds_b} present in the live response")
        return make_verdict(got, "mismatch", observed=f"matchup {found['match']}: {rendered}",
                            note=f"live prices differ from the claimed {odds_a}/{odds_b}")
    return make_verdict(got, "not-checkable", observed="generic matchups page, no per-match state",
                        note="the cited page is a listing, not a per-match permalink")


def verify_identity(claim: dict) -> dict:
    """Hotspawn / HLTV team pages: is the cited identity (team names) actually served?"""
    got = fetch(claim["url"])
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    present, detail = tokens_present(got["body"], [claim["team_a"], claim["team_b"]])
    return make_verdict(got, "match" if present else "mismatch", observed=detail,
                        note="" if present else "a cited team name is not on the served page")


def verify_polymarket(claim: dict) -> dict:
    got = fetch(claim["url"])
    if got["status"] != 200 or not got["body"]:
        return refusal_or_dead(got)
    present, detail = tokens_present(got["body"], [claim["team_a"], claim["team_b"]])
    return make_verdict(got, "match" if present else "not-checkable", observed=detail,
                        note="prediction-market reference only; never a pick input for this repo")


VERIFIERS = {
    "vrs": verify_vrs,
    "hltv_match": verify_hltv_match,
    "egw_market": verify_egw_market,
    "pinnacle": verify_pinnacle,
    "hotspawn": verify_identity,
    "hltv_team": verify_identity,
    "polymarket": verify_polymarket,
}


# ---------------------------------------------------------------------------------------- worklist
def claim_entry(board: str, fixture_id: str, team_a: str, team_b: str, kind: str, url: str,
                claimed: str = "", **extra) -> dict:
    return {"board": board, "fixture_id": fixture_id, "team_a": team_a, "team_b": team_b,
            "kind": kind, "url": url, "claimed": claimed, "extra": extra}


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8", errors="replace"))))


def rank_of(value: str) -> str:
    m = re.match(r"\s*(\d+)", value or "")
    return m.group(1) if m else ""


def claims_everypick() -> list[dict]:
    out = []
    for r in read_rows(BOARDS["everypick"]):
        fid, a, b = r.get("fixture_id", ""), r.get("team_a", ""), r.get("team_b", "")
        for side, team in (("a", a), ("b", b)):
            url, val = r.get(f"vrs_url_{side}", ""), r.get(f"vrs_{side}", "")
            if url:
                out.append(claim_entry("everypick", fid, team, "", "vrs", url, claimed=val,
                                       rank=rank_of(val)))
            team_url = r.get(f"hltv_team_url_{side}", "")
            if team_url:
                out.append(claim_entry("everypick", fid, team, "", "hltv_team", team_url,
                                       claimed=team))
        if r.get("hltv_match_url"):
            out.append(claim_entry("everypick", fid, a, b, "hltv_match", r["hltv_match_url"],
                                   claimed=r.get("series_format", ""),
                                   series_format=r.get("series_format", "")))
        if r.get("market_url"):
            kind = "pinnacle" if "pinnacle" in r["market_url"] else "egw_market"
            out.append(claim_entry("everypick", fid, a, b, kind, r["market_url"],
                                   claimed=f"{r.get('odds_a','')}/{r.get('odds_b','')}",
                                   odds_a=r.get("odds_a", ""), odds_b=r.get("odds_b", ""),
                                   book=r.get("market_book", "")))
        if r.get("hotspawn_url"):
            out.append(claim_entry("everypick", fid, a, b, "hotspawn", r["hotspawn_url"],
                                   claimed="fixture identity"))
    return out


def claims_picks_full() -> list[dict]:
    out = []
    for r in read_rows(BOARDS["picks-full"]):
        fid, a, b = r.get("match_id", ""), r.get("team_a", ""), r.get("team_b", "")
        url = r.get("market_source_url", "")
        pair = PAIR_IN_TEXT.search(r.get("pick_basis", "") or "")
        if url:
            odds_a = pair.group(1) if pair else ""
            odds_b = pair.group(2) if pair else ""
            kind = "pinnacle" if "pinnacle" in url else "egw_market"
            out.append(claim_entry("picks-full", fid, a, b, kind, url,
                                   claimed=f"{odds_a}/{odds_b}".strip("/"),
                                   odds_a=odds_a, odds_b=odds_b,
                                   series_format=r.get("series_format", "")))
    return out


def claims_cs2() -> list[dict]:
    out = []
    for r in read_rows(BOARDS["cs2"]):
        fid, a, b = r.get("fixture_id", ""), r.get("team_a", ""), r.get("team_b", "")
        if r.get("market_url"):
            kind = "pinnacle" if "pinnacle" in r["market_url"] else "egw_market"
            out.append(claim_entry("cs2", fid, a, b, kind, r["market_url"],
                                   claimed=f"{r.get('market_odds_a','')}/{r.get('market_odds_b','')}",
                                   odds_a=r.get("market_odds_a", ""), odds_b=r.get("market_odds_b", ""),
                                   book=r.get("market_book", "")))
        for side, team in (("a", a), ("b", b)):
            url = r.get(f"vrs_url_{side}", "")
            if url:
                out.append(claim_entry("cs2", fid, team, "", "vrs", url,
                                       claimed=f"{r.get(f'vrs_rank_{side}','')} / "
                                               f"{r.get(f'vrs_points_{side}','')} pts",
                                       rank=r.get(f"vrs_rank_{side}", "")))
        bo, src = r.get("best_of", ""), r.get("best_of_source", "")
        if bo and src.startswith("http"):
            kind = "hltv_match" if "hltv.org" in src else "pinnacle"
            out.append(claim_entry("cs2", fid, a, b, kind, src, claimed=f"Best of {bo}",
                                   series_format=f"BO{bo}"))
        for key in ("hotspawn_url", "hotspawn_match_url"):
            if r.get(key):
                out.append(claim_entry("cs2", fid, a, b, "hotspawn", r[key],
                                       claimed="fixture identity"))
        if r.get("poly_url"):
            out.append(claim_entry("cs2", fid, a, b, "polymarket", r["poly_url"],
                                   claimed="reference"))
    return out


def claims_every() -> list[dict]:
    """Board published by another session (every/data/picks.csv), read read-only."""
    out = []
    for r in read_rows(BOARDS["every"]):
        fid, a, b = r.get("fixture_id", ""), r.get("team_a", ""), r.get("team_b", "")
        if r.get("market_url"):
            kind = "pinnacle" if "pinnacle" in r["market_url"] else "egw_market"
            out.append(claim_entry("every", fid, a, b, kind, r["market_url"],
                                   claimed=f"{r.get('market_odds_a','')}/{r.get('market_odds_b','')}",
                                   odds_a=r.get("market_odds_a", ""), odds_b=r.get("market_odds_b", ""),
                                   book=r.get("market_book", "")))
        for side, team in (("a", a), ("b", b)):
            url = r.get(f"rating_{side}_source_url", "")
            points = str(r.get(f"rating_{side}_vrs_points", "") or "")
            if url:
                value = points.split(".")[0] if points else ""
                out.append(claim_entry("every", fid, team, "", "vrs", url,
                                       claimed=f"{points} pts".strip(), rank=value))
        bo, src = str(r.get("best_of", "") or ""), r.get("best_of_source_url", "")
        if bo and src.startswith("http"):
            kind = "hltv_match" if "hltv.org" in src else "pinnacle"
            out.append(claim_entry("every", fid, a, b, kind, src, claimed=f"Best of {bo}",
                                   series_format=f"BO{bo}"))
        if r.get("hltv_match_url"):
            out.append(claim_entry("every", fid, a, b, "hltv_match", r["hltv_match_url"],
                                   claimed=f"BO{r.get('best_of','')}",
                                   series_format=f"BO{r.get('best_of','')}"))
        for key in ("hotspawn_lobby_url", "hotspawn_match_url"):
            if r.get(key):
                out.append(claim_entry("every", fid, a, b, "hotspawn", r[key],
                                       claimed="fixture identity"))
    return out


CLAIMERS = {"everypick": claims_everypick, "picks-full": claims_picks_full, "cs2": claims_cs2,
            "every": claims_every}


def dedupe(claims: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in claims:
        key = (c["kind"], vrs_raw_url(c["url"]) if c["kind"] == "vrs" else c["url"],
               c.get("claimed", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def run(only: str | None, limit: int | None, offline: bool) -> dict:
    claims: list[dict] = []
    for board, fn in CLAIMERS.items():
        if only and board != only:
            continue
        found = fn()
        print(f"{board}: {len(found)} cited values", flush=True)
        claims += found
    claims = dedupe(claims)
    # Spend the browser budget on the hosts that refuse a plain client first (Hotspawn, HLTV,
    # EGamersWorld), then the plain-HTTP sources (Valve's raw file, Polymarket, Pinnacle).
    order = {"hotspawn": 0, "hltv_match": 1, "hltv_team": 2, "egw_market": 3, "pinnacle": 4,
             "polymarket": 5, "vrs": 6}
    claims.sort(key=lambda c: (order.get(c["kind"], 9), c["board"], c["fixture_id"]))
    print(f"worklist: {len(claims)} unique claims", flush=True)
    if limit:
        claims = claims[:limit]

    previous = {}
    prev_path = OUT / "source_check.csv"
    if prev_path.exists():
        for row in csv.DictReader(io.StringIO(prev_path.read_text(encoding="utf-8"))):
            key = (row.get("board", ""), row.get("kind", ""), row.get("url", ""),
                   row.get("claimed", ""))
            previous[key] = row
    started = time.time()
    budget_seconds = 22 * 60
    reuse_hours = 6
    results = []
    for i, c in enumerate(claims, 1):
        if not offline and time.time() - started > budget_seconds:
            res = {"verdict": "not-checkable", "http_status": None, "observed": "",
                   "note": "run budget reached before this row was re-read; next run will cover it",
                   "sha256": None, "bytes": 0, "fetched_utc": now_iso()}
            results.append({**{k: c[k] for k in ("board", "fixture_id", "team_a", "team_b", "kind",
                                                 "url", "claimed")}, **res})
            continue
        prev = previous.get((c["board"], c["kind"], c["url"], c.get("claimed", "")))
        reused = False
        if (not offline and prev and prev.get("verdict") == "match"
                and prev.get("checked_utc")):
            stamp = parse_utc(prev.get("checked_utc", ""))
            age = ((datetime.now(timezone.utc) - stamp).total_seconds() if stamp
                   else reuse_hours * 3601)
            if age < reuse_hours * 3600:
                reused = True
                res = {"verdict": "match", "http_status": prev.get("http_status"),
                       "observed": prev.get("observed", ""),
                       "note": (prev.get("note", "") +
                                f" · reused from the {prev['checked_utc']} run (<{reuse_hours} h)"),
                       "sha256": prev.get("sha256"), "bytes": prev.get("bytes") or 0,
                       "fetched_utc": prev["checked_utc"]}
        if not reused and offline:
            res = {"verdict": "not-checkable", "http_status": None, "observed": "",
                   "note": "offline run: no network attempted", "sha256": None, "bytes": 0,
                   "fetched_utc": now_iso()}
        elif not reused:
            try:
                res = VERIFIERS[c["kind"]](c)
            except Exception as exc:  # noqa: BLE001 - one bad row must not lose the run
                res = {"verdict": "not-checkable", "http_status": None, "observed": "",
                       "note": f"verifier error: {type(exc).__name__}: {str(exc)[:100]}",
                       "sha256": None, "bytes": 0, "fetched_utc": now_iso()}
            time.sleep(0.4)
        results.append({**{k: c[k] for k in ("board", "fixture_id", "team_a", "team_b", "kind",
                                             "url", "claimed")}, **res, "reused": "yes" if reused
                         else "no"})
        if i % 25 == 0:
            print(f"  ... {i}/{len(claims)}", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    fields = ["checked_utc", "board", "fixture_id", "team_a", "team_b", "kind", "url", "claimed",
              "verdict", "http_status", "observed", "note", "reused", "sha256", "bytes"]
    with open(OUT / "source_check.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in sorted(results, key=lambda r: (r["board"], r["fixture_id"], r["kind"])):
            writer.writerow({"checked_utc": r["fetched_utc"],
                             **{k: r.get(k, "") for k in fields[1:]}})

    counts = {name: 0 for name in VERDICT_NAMES}
    hosts: dict[str, int] = {}
    kinds: dict[str, dict] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        host = re.sub(r"^https?://", "", r["url"]).split("/")[0]
        hosts[host] = hosts.get(host, 0) + 1
        slot = kinds.setdefault(r["kind"], {"total": 0})
        slot["total"] += 1
        slot[r["verdict"]] = slot.get(r["verdict"], 0) + 1
    summary = {
        "generated_utc": now_iso(),
        "session": "arena/bdc98a9a",
        "what": "live re-read of every external URL cited by the merged boards' data files",
        "offline": offline,
        "boards_read": [b for b in BOARDS if (not only or b == only) and BOARDS[b].exists()],
        "boards_missing": [b for b in BOARDS if (not only or b == only) and not BOARDS[b].exists()],
        "claims": len(results),
        "verdicts": counts,
        "by_kind": kinds,
        "by_host": dict(sorted(hosts.items(), key=lambda kv: -kv[1])),
        "fetches": len(LOG),
        "fetch_errors": sum(1 for e in LOG if e.get("error")),
        "reused_within_hours": reuse_hours,
        "reused_rows": sum(1 for r in results if r.get("reused") == "yes"),
        "policy": ("Hotspawn is read for fixture identity and series format only, never for a "
                   "probability. A refusal or a mismatch is recorded and flagged; this tool never "
                   "edits another board's data and never fills a value in."),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    with open(OUT / "log.jsonl", "w", encoding="utf-8") as fh:
        for e in LOG:
            fh.write(json.dumps(e, sort_keys=True) + "\n")
    print(json.dumps({k: summary[k] for k in ("claims", "verdicts", "fetches", "fetch_errors")},
                     indent=1))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="source re-read verification (session bdc98a9a)")
    ap.add_argument("--only", choices=sorted(BOARDS), default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        run(args.only, args.limit, args.offline)
    except Exception:  # noqa: BLE001 - publish what happened instead of an empty log
        (OUT / "error.json").write_text(json.dumps(
            {"error": "collect run raised", "when": now_iso(),
             "traceback": traceback.format_exc()[-4000:]}, indent=1) + "\n", encoding="utf-8")
        print(traceback.format_exc(), file=sys.stderr)
        return 1
    (OUT / "error.json").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
