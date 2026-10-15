"""Shared helpers for the every-match Hotspawn CS2 board (session arena/22be6967).

Design rules that every module relies on:

* Public pages and public JSON only, an honest User-Agent, no keys, no logins, no bot evasion.
* Every network read is recorded (url, HTTP status, bytes, sha256, UTC read time) so each value on
  the site can be traced to the exact response it came from.
* Hotspawn supplies fixture identity, times, points and the crowd pick share.  The crowd share is
  carried under names that say ``ownership`` and is used ONLY by the leaderboard-strategy layer;
  it is never an input to any probability.
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
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"
RESEARCH = ROOT / "research"
SESSION = "arena/22be6967"
REPO_URL = "https://github.com/buffedlizard55-lab/MaltaProj1"
SITE_URL = "https://buffedlizard55-lab.github.io/MaltaProj1/"
UA = ("MaltaProj1-hotspawn-board/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1; "
      "public pages only)")

# Valve's model (model/glicko.js + model/fit.js in ValveSoftware/counter-strike_regional_standings):
# expected win rate = 1 / (1 + 10 ** (-g * delta / 400)) with g = 1/sqrt(1 + 3 Q^2 RD^2 / pi^2),
# Q = ln(10)/400 and the fixed RD of 75 used by fit.js.  calibrate.py refits the slope.
Q = math.log(10) / 400.0
VALVE_RD = 75.0
K_VALVE_RAW = 1.0 / math.sqrt(1.0 + 3.0 * Q * Q * VALVE_RD * VALVE_RD / (math.pi ** 2))

PROVENANCE: list[dict] = []


# ----------------------------------------------------------------------------------- time
def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def now_iso() -> str:
    return now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).strip().replace(" ", "T")
    if text.endswith("+00"):
        text = text[:-3] + "+00:00"
    text = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def ms_to_iso(value) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    digits = re.sub(r"\D", "", str(value))
    if len(digits) != 13:
        return None
    try:
        return datetime.fromtimestamp(int(digits) / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def hours_between(a: str | None, b: str | None) -> float | None:
    da, db = parse_iso(a), parse_iso(b)
    if not da or not db:
        return None
    return (da - db).total_seconds() / 3600.0


# ----------------------------------------------------------------------------------- http
def http_get(url: str, timeout: int = 40, retries: int = 2, accept: str | None = None,
             headers: dict | None = None) -> dict:
    hdr = {"User-Agent": UA, "Accept": accept or "text/html,application/json;q=0.9,*/*;q=0.5",
           "Accept-Language": "en"}
    if headers:
        hdr.update(headers)
    out = {"url": url, "status": None, "body": b"", "error": None, "fetched_utc": now_iso(),
           "bytes": 0, "sha256": None}
    for attempt in range(retries + 1):
        out["fetched_utc"] = now_iso()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                out.update(status=r.status, body=body, error=None, bytes=len(body),
                           sha256=hashlib.sha256(body).hexdigest())
                break
        except urllib.error.HTTPError as exc:
            out.update(status=exc.code, error=f"HTTPError {exc.code}")
            if exc.code in (401, 403, 404, 410):
                break
        except Exception as exc:  # noqa: BLE001 - every failure is recorded, never hidden
            out.update(error=f"{type(exc).__name__}: {exc}"[:300])
        time.sleep(1.5 * (attempt + 1))
    PROVENANCE.append({k: out[k] for k in ("url", "status", "error", "fetched_utc", "bytes", "sha256")})
    return out


def get_json(url: str, **kw):
    got = http_get(url, accept="application/json", **kw)
    if got["status"] != 200 or not got["body"]:
        return None, got
    try:
        return json.loads(got["body"].decode("utf-8", errors="replace")), got
    except json.JSONDecodeError as exc:
        got["error"] = f"JSONDecodeError: {exc}"
        return None, got


# ---------------------------------------------------------------------------------- files
def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_raw(name: str, payload: bytes | str) -> str:
    """Keep only the latest copy per source (gzip) so the repository does not grow every run."""
    RAW.mkdir(parents=True, exist_ok=True)
    data = payload.encode("utf-8") if isinstance(payload, str) else (payload or b"")
    path = RAW / f"{name}.json.gz"
    with gzip.open(path, "wb", compresslevel=9, mtime=0) as fh:
        fh.write(data)
    return str(path.relative_to(ROOT.parent))


# ---------------------------------------------------------------------------------- odds
def american_to_decimal(value) -> float | None:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v >= 100:
        return round(1.0 + v / 100.0, 6)
    if v <= -100:
        return round(1.0 + 100.0 / abs(v), 6)
    return None


def devig_two_way(odds_a: float, odds_b: float) -> tuple[float, float, float] | None:
    """Proportional (multiplicative) margin removal for a two-way decimal-odds market.

    Returns (p_a, p_b, overround_pct).  None when the prices are not a valid two-way book.
    """
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


def normalise_prices(pa: float, pb: float) -> tuple[float, float] | None:
    try:
        a, b = float(pa), float(pb)
    except (TypeError, ValueError):
        return None
    if a <= 0 or b <= 0 or a + b <= 0:
        return None
    return a / (a + b), b / (a + b)


def own_line(points_a: float, points_b: float, k: float) -> float:
    """P(A beats B) on the Valve curve with slope ``k`` (calibrated by calibrate.py)."""
    return 1.0 / (1.0 + 10.0 ** (-k * (float(points_a) - float(points_b)) / 400.0))


# ---------------------------------------------------------------------------------- names
_DROP = {"team", "esports", "esport", "gaming", "gg", "club", "the", "cs", "cs2"}


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii")
    return text.casefold()


def norm_name(name: str) -> str:
    """Lower-cased, accent-free, punctuation-free key; generic words like 'Team' are dropped."""
    tokens = re.findall(r"[a-z0-9]+", fold(name))
    kept = [t for t in tokens if t not in _DROP]
    return "".join(kept or tokens)


class Aliases:
    """Verified team-name equivalences (research/aliases.json).  Every entry carries evidence."""

    def __init__(self, path: Path | None = None):
        self.rows = read_json(path or RESEARCH / "aliases.json", {"teams": []}).get("teams", [])
        self.to_key: dict[str, str] = {}
        self.evidence: dict[str, dict] = {}
        for row in self.rows:
            key = row["key"]
            self.evidence[key] = row
            for variant in [row.get("display", key)] + list(row.get("variants", [])):
                self.to_key[norm_name(variant)] = key

    def key(self, name: str) -> str:
        n = norm_name(name)
        return self.to_key.get(n, n)

    def used(self, name: str) -> dict | None:
        """The alias row when ``name`` only matches through a verified alias (not by its own spelling)."""
        n = norm_name(name)
        key = self.to_key.get(n)
        if key is None:
            return None
        row = self.evidence.get(key)
        if row and norm_name(row.get("display", key)) != n:
            return row
        return None


def pct(value: float | None, digits: int = 0) -> str:
    if value is None:
        return ""
    return f"{value * 100:.{digits}f}%"


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def utc_label(value: str | None) -> str:
    dt = parse_iso(value)
    return dt.strftime("%a %d %b %H:%M UTC") if dt else ""


def ensure_dirs() -> None:
    for d in (DATA, RAW):
        d.mkdir(parents=True, exist_ok=True)


def relative_age_hours(value: str | None, ref: datetime | None = None) -> float | None:
    dt = parse_iso(value)
    if not dt:
        return None
    return ((ref or now_utc()) - dt).total_seconds() / 3600.0


def within(value: str | None, start: datetime, end: datetime) -> bool:
    dt = parse_iso(value)
    return bool(dt and start <= dt <= end)



def run_main(fn) -> None:
    """Run a pipeline entry point; on a crash print the traceback AND a GitHub ::error annotation
    (annotations are readable through the API even when raw job logs are not)."""
    import os
    import traceback
    try:
        code = fn()
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        print(tb, flush=True)
        if os.environ.get("GITHUB_ACTIONS"):
            msg = tb[-1800:].replace("%", "%25").replace("\r", "").replace("\n", "%0A")
            print(f"::error title={os.path.basename(getattr(fn, '__module__', 'script') or 'script')} crashed::{msg}", flush=True)
        raise SystemExit(1)
    raise SystemExit(code or 0)


__all__ = [name for name in dir() if not name.startswith("_")]
_ = timedelta  # re-exported for callers via ``from common import *``
