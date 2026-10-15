#!/usr/bin/env python3
"""Shared helpers — Hotspawn CS2 every-match coverage board, session ``arena/a6f05f99``.

Everything here is deliberately dependency-free (standard library only) so the board can be
rebuilt by an unattended GitHub Actions runner with no package install step.

Design rules that the whole module obeys:

* Hotspawn's own crowd pick share is **never** a probability input.  It is carried separately as
  ``crowd_*_ownership`` and is used only to measure how contrarian a play is.
* A probability is only ever produced from (a) an outside price, or (b) our own line built from
  official Valve Regional Standings points / HLTV world-ranking points.  Nothing is invented and
  nothing is copied from Hotspawn's own percentages.
* Every row keeps the URL it came from and the UTC time it was read.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
RESEARCH = HERE / "research"
RAW = DATA / "raw"

SESSION = "arena/a6f05f99"
LOBBY = "https://play.hotspawn.com/lobby"

# Slope of the Valve-points win-probability curve, P = 1/(1+10^(-k*dPoints/400)).
# Fitted by session arena/22be6967 (``hotspawn/calibrate.py``) on 13,609 official Valve-rated
# matches; held-out log-loss 0.6395 vs 0.6541 for Valve's own raw slope.  Kept as a constant here
# so this board never depends on another session's files at build time.
K_VALVE = 0.4598
K_VALVE_PROVENANCE = (
    "k = 0.4598, fitted by session arena/22be6967 on 13,609 official Valve-rated matches "
    "(held-out log-loss 0.6395 vs 0.6541 for Valve's raw slope); see hotspawn/data/calibration.json "
    "and hotspawn/calibrate.py in this repository."
)

UA = ("Mozilla/5.0 (compatible; MaltaProj1-a6f05f99/1.0; "
      "+https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/a6f05f99)")
HTML_HEADERS = {"User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"}
JSON_HEADERS = {"User-Agent": UA, "Accept": "application/json,text/plain;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9"}

PROVENANCE: list[dict] = []


# ---------------------------------------------------------------------------------------- time
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ms_to_iso(value) -> str | None:
    try:
        ms = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if ms <= 0:
        return None
    return iso(datetime.fromtimestamp(ms / 1000, tz=timezone.utc))


def hours_between(a: str | None, b: str | None) -> float | None:
    ta, tb = parse_iso(a), parse_iso(b)
    if ta is None or tb is None:
        return None
    return (ta - tb).total_seconds() / 3600.0


def age_hours(read_utc: str | None, reference: str | None) -> float | None:
    return None if not read_utc else hours_between(reference, read_utc)


# ----------------------------------------------------------------------------------------- http
def http_get(url: str, headers: dict | None = None, timeout: int = 45, retries: int = 2) -> dict:
    rec: dict = {"url": url, "status": None, "bytes": 0, "sha256": None, "error": None,
                 "fetched_utc": None, "body": b""}
    for attempt in range(retries + 1):
        rec["fetched_utc"] = now_iso()
        try:
            req = urllib.request.Request(url, headers=headers or JSON_HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                rec.update(status=resp.status, body=body, bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest(), error=None)
                break
        except urllib.error.HTTPError as exc:
            rec.update(status=exc.code, error=f"HTTP {exc.code}")
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except Exception as exc:  # noqa: BLE001 - transport failures are recorded, never hidden
            rec.update(error=f"{type(exc).__name__}: {exc}"[:240])
        time.sleep(1.5 * (attempt + 1))
    PROVENANCE.append({k: rec[k] for k in ("url", "status", "bytes", "sha256", "error",
                                           "fetched_utc")})
    return rec


def get_json(url: str, headers: dict | None = None, timeout: int = 45):
    rec = http_get(url, headers=headers, timeout=timeout)
    if rec["status"] != 200 or not rec["body"]:
        return None, rec
    try:
        return json.loads(rec["body"].decode("utf-8", "replace")), rec
    except ValueError as exc:
        rec["error"] = f"JSON: {exc}"[:200]
        return None, rec


def log(msg: str) -> None:
    print(f"[a6f05f99 {now_iso()}] {msg}", flush=True)


# ---------------------------------------------------------------------------------------- files
def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path: Path, payload) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                          encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    import csv
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


# --------------------------------------------------------------------------------- probabilities
def american_to_decimal(price) -> float | None:
    try:
        value = float(price)
    except (TypeError, ValueError):
        return None
    if value >= 100:
        return 1.0 + value / 100.0
    if value <= -100:
        return 1.0 + 100.0 / abs(value)
    return None


def devig_two_way(odds_a, odds_b) -> tuple[float, float, float] | None:
    """Proportional margin removal for a two-way decimal-odds market -> (p_a, p_b, overround %)."""
    try:
        a, b = float(odds_a), float(odds_b)
    except (TypeError, ValueError):
        return None
    if a <= 1.0 or b <= 1.0:
        return None
    ia, ib = 1.0 / a, 1.0 / b
    total = ia + ib
    if total < 0.98 or total > 1.25:      # not a plausible two-way book
        return None
    return ia / total, ib / total, (total - 1.0) * 100.0


def normalise_prices(pa, pb) -> tuple[float, float] | None:
    try:
        a, b = float(pa), float(pb)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0 or a + b <= 0:
        return None
    return a / (a + b), b / (a + b)


def own_line(points_a, points_b, best_of: int | None = None, k: float = K_VALVE) -> float | None:
    """P(A beats B) from official Valve Regional Standings points (logistic on the points gap)."""
    try:
        pa, pb = float(points_a), float(points_b)
    except (TypeError, ValueError):
        return None
    if pa <= 0 or pb <= 0:
        return None
    return 1.0 / (1.0 + 10.0 ** (-k * (pa - pb) / 400.0))


def mean(values: list[float]) -> float | None:
    vals = [v for v in values if isinstance(v, (int, float))]
    return sum(vals) / len(vals) if vals else None


def pct(value, places: int = 1) -> str:
    return "" if value is None else f"{round(float(value) * 100, places):.{places}f}"


# ---------------------------------------------------------------------------------------- names
_DROP = {"team", "esports", "esport", "gaming", "gg", "club", "the", "cs", "cs2", "e"}


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")


def norm_name(name: str) -> str:
    tokens = re.findall(r"[a-z0-9]+", fold(name).casefold())
    kept = [t for t in tokens if t not in _DROP]
    return "".join(kept or tokens)


class Aliases:
    """Verified team-name equivalences (``research/aliases.json``); every entry carries evidence."""

    def __init__(self, path: Path | None = None):
        self.rows = (read_json(path or RESEARCH / "aliases.json", {"teams": []}) or {}).get("teams", [])
        self.to_key: dict[str, str] = {}
        self.evidence: dict[str, dict] = {}
        for row in self.rows:
            key = row.get("key")
            if not key:
                continue
            self.evidence[key] = row
            for variant in [row.get("display", key)] + list(row.get("variants", [])):
                self.to_key[norm_name(variant)] = key

    def key(self, name: str) -> str:
        n = norm_name(name)
        return self.to_key.get(n, n)

    def used(self, name: str) -> dict | None:
        return self.evidence.get(self.key(name))


def ensure_dirs() -> None:
    for path in (DATA, RESEARCH, RAW):
        path.mkdir(parents=True, exist_ok=True)


def complementary(p: float | None) -> tuple[str, str]:
    """Two percentages that always add up to exactly 100 (independent rounding can show 79/22)."""
    if p is None:
        return "", ""
    a = round(float(p) * 100)
    return f"{a}", f"{100 - a}"
