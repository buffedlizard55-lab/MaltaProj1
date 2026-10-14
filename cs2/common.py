#!/usr/bin/env python3
"""Shared plumbing for the Hotspawn CS2 line board (session arena/a174d77f).

Design rules that every module in ``cs2/`` follows:

* Public pages only, honest User-Agent, no login, no keys, no bot evasion.
* A value that could not be read is left blank and flagged; it is never inferred.
* Every number written to ``cs2/data`` is traceable to a URL + capture time + SHA-256 of the
  exact bytes it came from (``cs2/data/provenance.json``).
* Hotspawn's own crowd pick percentages are read for the coverage audit only and are dropped
  before the analysis dataset is written.

The agent sandbox has no general internet access, so the fetching runs on GitHub Actions
(``.github/workflows/cs2-a174d77f.yml``); the model/build/tests run anywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent          # .../cs2
REPO = ROOT.parent
DATA = ROOT / "data"
RAW = DATA / "raw"

# Deliberately NOT a browser impersonation.  An honest, identifiable UA is both the polite way to
# read a public page and, as it turns out, the one HLTV's edge accepts: a neighbour pipeline in this
# repository (model/fetch.py) reaches the ranking page with "Mozilla/5.0 (compatible; MaltaProj1-
# model/1.0; +https://github.com/...)" while a fake Chrome/126 from the same runner gets 403.
# So we say who we are, where the code lives, and we never retry a refusal as a disguised client.
UA = ("Mozilla/5.0 (compatible; MaltaProj1-cs2/1.0; "
      "+https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/cs2)")
BASE_HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

LOG_PATH = Path(os.environ.get("CS2_LOG", str(DATA / "collect.log")))
provenance: list[dict] = []


# ---------------------------------------------------------------------------- clock / io
def now_dt() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_dt().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not isinstance(value, str) or len(value) < 19:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).replace(microsecond=0, tzinfo=timezone.utc) if dt.tzinfo \
        else dt.replace(tzinfo=timezone.utc)


def log(msg: str) -> None:
    line = f"[{now_iso()}] {msg}"
    print(line, flush=True)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False) + "\n",
                   encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log(f"read_json {path.name}: {exc}")
        return default


def write_csv(path: Path, rows: list[dict], columns: list[str] | None = None) -> None:
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    cols = columns or list({}.fromkeys([k for r in rows for k in r]))
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in cols})


def read_csv(path: Path) -> list[dict]:
    import csv
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------- HTTP
def record(entry: dict) -> None:
    provenance.append(entry)


def flush_provenance(path: Path | None = None) -> None:
    write_json(path or (DATA / "provenance.json"), provenance)


def http_get(url: str, timeout: int = 40, accept: str | None = None,
             retries: int = 2, headers: dict | None = None) -> dict:
    """GET with two retries. Returns status/bytes/sha256/error + body bytes; never raises."""
    hdr = dict(BASE_HEADERS)
    if accept:
        hdr["Accept"] = accept
    if headers:
        hdr.update(headers)
    entry = {"url": url, "fetched_utc": now_iso(), "via": "urllib", "status": None,
             "bytes": None, "sha256": None, "error": None, "attempts": 0}
    body = b""
    for attempt in range(retries + 1):
        entry["attempts"] = attempt + 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr),
                                        timeout=timeout) as resp:
                body = resp.read(30_000_000)
                entry.update(status=resp.status, bytes=len(body),
                             sha256=hashlib.sha256(body).hexdigest(), error=None)
            break
        except urllib.error.HTTPError as exc:      # noqa: PERF203
            entry.update(status=exc.code, error=f"HTTPError {exc.code}")
            if exc.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2.0 * (attempt + 1))
                continue
            break
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            entry.update(error=f"{type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            break
    record(entry)
    if entry["status"] != 200:
        log(f"fetch {entry['status'] or 'ERR'} {url} :: {entry['error'] or ''}")
    return {**entry, "body": body}


def get_json(url: str, **kw) -> tuple[object | None, dict]:
    got = http_get(url, accept="application/json", **kw)
    if not got["body"]:
        return None, got
    try:
        return json.loads(got["body"].decode("utf-8", errors="replace")), got
    except json.JSONDecodeError as exc:
        got["error"] = f"JSON: {exc}"
        log(f"json parse failed {url}: {exc}")
        return None, got


def save_raw(name: str, body: bytes) -> str | None:
    """Keep the exact bytes that produced a number, gzip-compressed, for later re-verification."""
    import gzip
    if body is None:
        return None
    RAW.mkdir(parents=True, exist_ok=True)
    dated = name if re.search(r"_\d{4}_\d{2}_\d{2}$", name) else \
        f"{name}_{time.strftime('%Y_%m_%d')}"
    out = RAW / f"{dated}.json.gz"
    with gzip.open(out, "wb", compresslevel=6) as fh:
        fh.write(body)
    return out.name


# ---------------------------------------------------------------------------- team names
NOISE = {"team", "esports", "gaming", "club", "squad", "pro", "pc"}


def norm(text: str) -> str:
    """casefold + strip accents/punctuation, collapse whitespace."""
    if not isinstance(text, str):
        return ""
    out = unicodedata.normalize("NFKD", text)
    out = "".join(ch for ch in out if not unicodedata.combining(ch))
    out = out.casefold()
    out = out.replace("\u2018", "").replace("\u2019", "").replace("'", "").replace("`", "")
    out = re.sub(r"[^a-z0-9+\-]+", " ", out)
    return re.sub(r"\s+", " ", out).strip()


def norm_core(text: str) -> str:
    """norm() without the marketing noise words; used only as a documented second-pass key."""
    toks = [t for t in norm(text).split() if t not in NOISE]
    return " ".join(toks) or norm(text)


def alias_lookup(name: str, aliases: dict) -> str:
    """Evidence-backed renames only (see cs2/aliases.json); unknown names pass through.

    The file maps a source spelling to either the target name (string) or a record carrying
    ``alias_of`` plus the evidence links that justify the rename.
    """
    key = norm(name)
    for src, tgt in (aliases or {}).items():
        if src.startswith("_"):
            continue
        target = tgt.get("alias_of") if isinstance(tgt, dict) else tgt
        if norm(src) == key and isinstance(target, str):
            return target
    return name


def pair_keys(a: str, b: str, aliases: dict | None = None) -> list[tuple[str, str, str]]:
    """Return candidate (key_a, key_b, method) pairs, strictest first.

    ``method`` is published on every row so a reader can see how a bookmaker fixture was tied
    to a Hotspawn fixture. Only ``exact`` and ``alias`` are accepted by the model; anything
    looser is refused and flagged.
    """
    aliases = aliases or {}
    aa, bb = alias_lookup(a, aliases), alias_lookup(b, aliases)
    out = [(norm(aa), norm(bb), "exact")]
    if norm_core(aa) != norm(aa) or norm_core(bb) != norm(bb):
        out.append((norm_core(aa), norm_core(bb), "noise-stripped"))
    return out


def key_pair(a: str, b: str) -> tuple[str, str]:
    """Canonical, order-independent key for one matchup pair."""
    ka, kb = norm(a), norm(b)
    return (ka, kb) if ka <= kb else (kb, ka)


# ---------------------------------------------------------------------------- odds math
def american_to_decimal(price) -> float | None:
    """American -> decimal.  A valid American price is >= +100 or <= -100; anything else (0, a
    decimal already, a stray field) is refused rather than converted."""
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if value == 0 or abs(value) < 100:
        return None
    return round(1 + (value / 100 if value > 0 else 100 / abs(value)), 6)


def is_decimal(price) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    return round(value, 4) if 1.01 <= value <= 1000 else None


def devig_two_way(odds_a: float, odds_b: float) -> tuple[float, float, float] | None:
    """Multiplicative de-vig of a two-way market: p_i = (1/o_i) / sum(1/o_j).

    Returns (p_a, p_b, overround_pct).  None when the prices are not a valid two-way market
    (draw prices are excluded upstream: a 3-way market is not the pick'em question).
    """
    if not odds_a or not odds_b or odds_a <= 1.0 or odds_b <= 1.0:
        return None
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    tot = ia + ib
    if tot <= 0 or tot > 4:
        return None
    return ia / tot, ib / tot, (tot - 1.0) * 100.0


def series_prob(p_map: float, best_of: int) -> float:
    """Probability of winning a best-of-n series given one-map win probability p."""
    n = int(best_of or 1)
    if n <= 1:
        return p_map
    need = (n // 2) + 1
    total = 0.0
    for k in range(need, n + 1):
        total += _comb(n, k) * (p_map ** k) * ((1.0 - p_map) ** (n - k))
    return min(max(total, 0.0), 1.0)


def _comb(n: int, k: int) -> int:
    import math
    return math.comb(n, k)


def pct(value: float | None, digits: int = 1) -> str:
    return "" if value is None else f"{value * 100:.{digits}f}"


def hours_between(iso_a: str | None, iso_b: str | None) -> float | None:
    da, db = parse_iso(iso_a), parse_iso(iso_b)
    if not da or not db:
        return None
    return (da - db).total_seconds() / 3600.0


def rel_time(iso: str | None) -> str:
    dt = parse_iso(iso)
    if not dt:
        return ""
    secs = int((dt - now_dt()).total_seconds())
    sign = "in " if secs >= 0 else ""
    secs = abs(secs)
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    tail = f"{d}d {h}h" if d else (f"{h}h {m:02d}m" if h else f"{m}m")
    return (sign + tail) if secs else "now"


def budget(default_seconds: int = 900) -> float:
    return time.time() + int(os.environ.get("CS2_BUDGET_SECONDS", default_seconds))


def over_budget(deadline: float) -> bool:
    if time.time() > deadline:
        log("collection budget reached - remaining sources are recorded as not attempted")
        return True
    return False


def eprint(*args) -> None:  # pragma: no cover
    print(*args, file=sys.stderr, flush=True)
