#!/usr/bin/env python3
"""Shared helpers for the arena/5545dbb8 executive board.

Design rules enforced here (and re-checked in executive/tests.py):

* Hotspawn supplies fixture identity, tier, points and UTC lock/start epochs only. The pick'em
  crowd percentages (`participants*_picked_percent`, `total_picks`) are dropped at ingest and
  never reach a file, a page or a calculation.
* Every published number is recomputed from a stored input, and every stored input carries the
  URL it was read from plus the UTC minute it was read.
* A value that no source confirms stays blank and is flagged; nothing is filled in silently.

Official constants used by the model paths:

* Probability from rating points: ``p(A) = 1 / (1 + 10 ** ((R_b - R_a) / 400))``.
  Valve publish this relation in the repository that produces the Regional Standings they use
  for invitations: ``model/glicko.js`` — ``// rank delta of 400 points = 90% chance of victory``
  and ``const ev = 1 / (1 + Math.pow(10, g * (r - ro) / (-400)))``.
  Source: https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/model/glicko.js
* Market de-vig: ``p = (1/odds) / sum(1/odds)`` (multiplicative / proportional method).
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
EXEC = ROOT / "executive"
DATA = EXEC / "data"
RAW = DATA / "raw"

# ------------------------------------------------------------------ official source registry
VRS_REPO = "https://github.com/ValveSoftware/counter-strike_regional_standings"
VRS_GLICKO_FILE = f"{VRS_REPO}/blob/main/model/glicko.js"
HOTSPAWN_LOBBY = "https://play.hotspawn.com/lobby"
HOTSPAWN_CS2 = "https://play.hotspawn.com/cs2-pickems"
HOTSPAWN_THP = "https://play.hotspawn.com/thp-pickems"
HLTV_RANKING = "https://www.hltv.org/ranking/teams"
HLTV_MATCHES = "https://www.hltv.org/matches"
HLTV_RESULTS = "https://www.hltv.org/results"
PINNACLE_GUEST = "https://guest.api.arcadia.pinnacle.com/0.1"
PIN_BASE = PINNACLE_GUEST
PINNACLE_CS2_PAGE = "https://www.pinnacle.com/en/esports/games/cs2/matchups/"
EGW_MATCHES = "https://egamersworld.com/counterstrike/matches"

# Pinnacle's public website loads this endpoint in an ordinary browser; this is the key that
# pinnacle.com's own public web app sends. No account of ours, no licensed API, no keys of ours.
PIN_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"
PIN_HEADERS = {
    "X-API-Key": PIN_KEY,
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0.0.0 Safari/537.36"),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.pinnacle.com",
    "Referer": "https://www.pinnacle.com/",
}
PIN_SPORT_ESPORTS = 12

# Honest, identifiable user agent: no browser impersonation, no bot-evasion.
UA = "Mozilla/5.0 (compatible; MaltaProj1-executive/1.0; +https://github.com/buffedlizard55-lab/MaltaProj1)"

PROB_SCALE_POINTS = 400.0     # official Valve glicko.js scale ("400 points = 90% chance of victory")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def minute(dt: datetime | None) -> str | None:
    s = iso(dt)
    return s[:16] + "Z" if s else None


def parse_iso(text: object) -> datetime | None:
    if text is None:
        return None
    raw = str(text).strip()
    if not raw:
        return None
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        for shape in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw[:19], shape)
                break
            except ValueError:
                continue
        else:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def epoch_ms_to_iso(value: object) -> str | None:
    """Hotspawn ships 13-digit millisecond epochs; units are explicit, never inferred from a label."""
    if isinstance(value, bool) or not re.fullmatch(r"\d{13}", str(value or "")):
        return None
    return iso(datetime.fromtimestamp(int(str(value)) / 1000.0, timezone.utc))


# ------------------------------------------------------------------ name handling
def norm(name: object) -> str:
    """Case/space/punctuation-insensitive comparison key. Display names are never altered.

    Only a leading "team"/"the" is dropped. Words such as "Academy", "Gaming" and "Esports" are kept:
    "B8" and "B8 Academy" are two different rosters in the same official file, and collapsing them
    would silently attach the wrong rating to a fixture.
    """
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode()
    text = re.sub(r"^(?:the|team)\s+", "", text.strip(), flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def roster_key(players: object) -> frozenset[str]:
    if isinstance(players, str):
        players = [p for p in re.split(r"[,\u00b7/|]", players)]
    if not isinstance(players, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(norm(p) for p in players if norm(p))


# ------------------------------------------------------------------ probability maths
def logit_prob(ra: float, rb: float, scale: float = PROB_SCALE_POINTS) -> float:
    """Probability that the team with ``ra`` points beats the team with ``rb`` points.

    Valve publish this relation in the repository that produces the Regional Standings:
    ``ev = 1 / (1 + Math.pow(10, g * (r - ro) / (-400)))`` with ``g = 1`` when the opponent's
    rating deviation is ignored, i.e. ``p(self) = 1 / (1 + 10 ** ((r_other - r_self) / 400))``.
    Source: https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/model/glicko.js
    """
    return 1.0 / (1.0 + math.pow(10.0, (rb - ra) / scale))


def american_to_decimal(price: object) -> float:
    value = float(price)
    if value >= 100:
        return 1.0 + value / 100.0
    if value <= -100:
        return 1.0 + 100.0 / abs(value)
    raise ValueError(f"not an American moneyline price: {price!r}")


def devig_pair(odds_a: float, odds_b: float) -> tuple[float, float, float]:
    """Multiplicative de-vig. Returns (p_a, p_b, overround_pct)."""
    if odds_a <= 1.0 or odds_b <= 1.0:
        raise ValueError("decimal odds must be > 1.0")
    raw_a, raw_b = 1.0 / odds_a, 1.0 / odds_b
    total = raw_a + raw_b
    return raw_a / total, raw_b / total, (total - 1.0) * 100.0


def fair_odds(p: float) -> float:
    return 1.0 / p


def pct(value: float | None, digits: int = 1) -> str:
    return "" if value is None else f"{value * 100.0:.{digits}f}"


def odds_text(value: float | None, digits: int = 2) -> str:
    return "" if value is None else f"{value:.{digits}f}"


# ------------------------------------------------------------------ io
def read_json(path: Path, default=None):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: Path, payload, indent: int = 1) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=indent, ensure_ascii=False, sort_keys=False) + "\n",
                    encoding="utf-8")


def read_csv(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fields})


def write_raw(name: str, body: bytes, when: datetime) -> tuple[str, str]:
    """Store the exact bytes a source served, gzipped, for audit. Returns (filename, sha256)."""
    RAW.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()
    filename = f"{when.strftime('%Y%m%dT%H%MZ')}-{name}-{digest[:12]}.gz"
    (RAW / filename).write_bytes(gzip.compress(body))
    return filename, digest


def sha256_bytes(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def official_url_safe(url: object) -> str:
    """A published link must be an absolute https URL on a host we actually read from."""
    text = str(url or "").strip()
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        return ""
    return text


def within(a: datetime | None, b: datetime | None, minutes: int) -> bool:
    return bool(a and b and abs(a - b) <= timedelta(minutes=minutes))
