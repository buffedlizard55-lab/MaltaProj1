#!/usr/bin/env python3
"""A3 — fit our own line's curve on Valve's published data (no look-ahead, no bookmaker input).

Valve's own README says the raw VRS expected-vs-observed curve has a slope "shallower than we'd
like": it "tends to underestimate win rates at the low end and overestimate at the high end"
(https://github.com/ValveSoftware/counter-strike_regional_standings/blob/<commit>/readme.md).
So we do not use the raw curve: we re-fit the slope by maximum likelihood on the match results
Valve publishes in the very same repository, and validate it out of sample.

Method (Valve's own evaluation recipe, applied between monthly snapshots):
  For every consecutive pair of global snapshots (S_prev, S_cur), read S_cur's per-team details
  tables.  Each row is one match that contributed to that roster's Final Rank Value and carries
  Match ID, date, W/L and the roster that played.  A match is usable when it appears in exactly
  two team tables (one W, one L) and each side's roster matches exactly one row of S_prev with
  >= 3 shared players (Valve's own TEAM_OVERLAP_TO_SHARE_ROSTER = 3 in model/team.js).  Each
  side's PRE-MATCH rating is that S_prev row's Points — ratings always predate the result.
  Curve family:  P(A beats B) = 1 / (1 + 10 ** (-k * (pts_A - pts_B) / 400)).
  k is fitted by maximum likelihood; the last window is held out for scoring.

Usage:  VRS_REPO_DIR=/path/to/counter-strike_regional_standings python3 cs2/calibrate.py
Output: cs2/data/calibration.json   (if it cannot be produced, model.py falls back to Valve's raw
k and every own line is labelled "raw curve, uncalibrated" — it is never silently calibrated)
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "data" / "calibration.json"
OVERLAP = 3                                   # Valve model/team.js TEAM_OVERLAP_TO_SHARE_ROSTER
Q = math.log(10) / 400.0
RD = 75.0                                     # Valve model/fit.js defaultGlickoParams.rd
K_VALVE = 1.0 / math.sqrt(1.0 + 3.0 * Q * Q * RD * RD / (math.pi ** 2))

STANDINGS_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", re.M)


def standings(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = STANDINGS_ROW.match(line.strip())
        if m and m.group(2).isdigit():
            rows.append({"rank": int(m.group(1)), "points": int(m.group(2)), "name": m.group(3).strip(),
                         "roster": frozenset(x.strip().casefold() for x in m.group(4).split(",") if x.strip())})
    return rows


def details_matches(dirp: Path, lo: date, hi: date) -> dict:
    """{match_id: [(roster, won, day)]} for matches with lo < date <= hi, deduplicated by Match ID."""
    found: dict[str, list] = {}
    for f in sorted(dirp.glob("*.md")):
        header = None
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("| Match Played"):
                header = [c.strip() for c in line.strip().strip("|").split("|")]
                continue
            if not header or not line.startswith("|") or set(line) <= {"|", "-", ":", " "}:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != len(header):
                header = None
                continue
            row = dict(zip(header, cells))
            try:
                day = date.fromisoformat(row["Date"])
            except (KeyError, ValueError):
                continue
            if not (lo < day <= hi) or row.get("W/L") not in ("W", "L"):
                continue
            roster = frozenset(x.strip().casefold() for x in row.get("Roster", "").split(",") if x.strip())
            found.setdefault(row["Match ID"], []).append((roster, row["W/L"] == "W", day))
    return found


def prematch_points(roster: frozenset, prev: list[dict]) -> int | None:
    hits = [row for row in prev if len(row["roster"] & roster) >= OVERLAP]
    return hits[0]["points"] if len(hits) == 1 else None


def p_of(k: float, delta: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-k * delta / 400.0))


def score(data, k: float) -> tuple[float, float]:
    logloss, brier, n = 0.0, 0.0, 0
    for delta, won in data:
        p = min(max(p_of(k, delta), 1e-9), 1 - 1e-9)
        logloss += -(won * math.log(p) + (1 - won) * math.log(1 - p))
        brier += (p - won) ** 2
        n += 1
    return logloss / max(n, 1), brier / max(n, 1)


def fit_k(data) -> float:
    lo, hi = 0.05, 3.0
    for _ in range(200):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if score(data, m1)[0] > score(data, m2)[0]:
            lo = m1
        else:
            hi = m2
    return round((lo + hi) / 2, 4)


def main() -> int:
    repo = Path(os.environ.get("VRS_REPO_DIR", "/tmp/vrs"))
    if not (repo / "live").is_dir():
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"status": "unavailable",
                                   "reason": f"{repo}/live not found; set VRS_REPO_DIR"}, indent=1) + "\n")
        print("calibrate: VRS_REPO_DIR/live missing - wrote an 'unavailable' marker")
        return 0
    files: list[Path] = sorted((repo / "live").glob("*/standings_global_*.md"))
    dated = []
    for path in files:
        m = re.search(r"(\d{4})_(\d{2})_(\d{2})", path.name)
        if m:
            dated.append((date(int(m.group(1)), int(m.group(2)), int(m.group(3))), path))
    dated.sort()
    windows, skipped = [], 0
    pool: list[tuple[float, float]] = []
    for (day_prev, path_prev), (day_cur, path_cur) in zip(dated, dated[1:]):
        prev = standings(path_prev)
        detail_dir = path_prev.parent / "details" / day_cur.strftime("%Y_%m_%d")
        if not detail_dir.is_dir():
            continue
        usable = []
        for _match_id, rows in details_matches(detail_dir, day_prev, day_cur).items():
            if len(rows) != 2 or {r[1] for r in rows} != {True, False}:
                skipped += 1
                continue
            winners = [r for r in rows if r[1]]
            losers = [r for r in rows if not r[1]]
            if len(winners) != 1 or len(losers) != 1:
                skipped += 1
                continue
            pa = prematch_points(winners[0][0], prev)
            pb = prematch_points(losers[0][0], prev)
            if pa == pb:
                skipped += 1
                continue
            if pa is None or pb is None:
                skipped += 1
                continue
            usable.append((float(pa - pb), 1.0))
        if not usable:
            continue
        pool += usable
        windows.append({"s_prev": day_prev.isoformat(), "s_cur": day_cur.isoformat(),
                        "n": len(usable), "skipped": skipped})
        skipped = 0
    if len(pool) < 200:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps({"status": "insufficient_data", "n": len(pool)}, indent=1) + "\n")
        return 0
    split = max(1, int(len(windows) * 0.8))
    # regroup the pool by window so the held-out split is by window, never by row
    samples: list[list[tuple[float, float]]] = []
    idx = 0
    for win in windows:
        samples.append(pool[idx:idx + win["n"]])
        idx += win["n"]
    train = [row for rows in samples[:split] for row in rows]
    test = [row for rows in samples[split:] for row in rows]
    k_train = fit_k(train)
    out = {
        "status": "ok",
        "method": ("MLE slope k for P=1/(1+10^(-k*delta/400)); delta = previous-snapshot VRS "
                   "points difference; both sides of every match identified by roster "
                   f"(>= {OVERLAP} shared players, unique) in the previous snapshot"),
        "valve_repo": "https://github.com/ValveSoftware/counter-strike_regional_standings",
        "valve_commit": os.popen(f"git -C {repo} rev-parse HEAD").read().strip() or "unknown",
        "k_valve_raw": round(K_VALVE, 6),
        "windows": windows,
        "train_windows": f"{windows[0]['s_prev']}..{windows[split-1]['s_cur']}",
        "test_windows": f"{windows[split-1]['s_cur']}..{windows[-1]['s_cur']}" if test else "",
        "n_total": len(pool), "n_train": len(train), "n_test": len(test),
        "k_fit_on_train": k_train,
        "out_of_sample": {
            "raw_valve_k": dict(zip(("log_loss", "brier"), score(test, K_VALVE))),
            "calibrated_train_k": dict(zip(("log_loss", "brier"), score(test, k_train))),
        },
    }
    out["adopted"] = out["out_of_sample"]["calibrated_train_k"]["log_loss"] < \
        out["out_of_sample"]["raw_valve_k"]["log_loss"]
    out["k_published"] = k_train if out["adopted"] else round(K_VALVE, 4)
    out["n_note"] = ("published slope refit on all windows" if out["adopted"]
                     else "calibration did not beat Valve's raw curve out of sample; raw curve kept")
    if out["adopted"]:
        out["k_published"] = fit_k(pool)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"calibrate: n={out['n_total']} k_valve={out['k_valve_raw']} "
          f"k_train={k_train} k_published={out['k_published']} adopted={out['adopted']} "
          f"oos_logloss raw={out['out_of_sample']['raw_valve_k']['log_loss']} "
          f"cal={out['out_of_sample']['calibrated_train_k']['log_loss']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
