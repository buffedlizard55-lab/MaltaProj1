#!/usr/bin/env python3
"""Fit the slope of our own line on Valve's own published match results (session arena/22be6967).

Why: Valve's README says its expected-vs-observed curve has a slope "shallower than we'd like" — the
raw curve is too extreme.  So the own line uses P(A beats B) = 1 / (1 + 10 ** (-k * dPoints / 400))
with k fitted by maximum likelihood instead of Valve's raw g = 0.9728.

Recipe (Valve's own evaluation idea, no look-ahead):
  For each consecutive pair of global snapshots (S_prev, S_cur) in ``live/<year>/``, read every
  per-team details table of S_cur.  A row is one rated match (Match ID, date, W/L, roster).  Rows dated
  after S_prev and on/before S_cur are new results.  A match is usable when its Match ID appears for
  exactly one winner and one loser and each side's roster maps to exactly one S_prev team sharing >= 3
  players (Valve's TEAM_OVERLAP_TO_SHARE_ROSTER).  Pre-match rating = that S_prev team's points.
  k maximises the Bernoulli log-likelihood over all windows except the last, which is held out.

Input:  VRS_REPO_DIR (a clone of ValveSoftware/counter-strike_regional_standings).
Output: hotspawn/data/calibration.json.  If it cannot be produced, model.py uses Valve's raw g and
        labels every own line "uncalibrated" — it never silently pretends to be calibrated.
"""
from __future__ import annotations

import math
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, K_VALVE_RAW, now_iso, write_json  # noqa: E402

OUT = DATA / "calibration.json"
ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
DETAIL = re.compile(r"^\|\s*\d+\s*\|\s*(\d+)\s*\|\s*(\d{4})-(\d{2})-(\d{2})\s*\|\s*[^|]*\|\s*([WL])\s*\|.*\|\s*([^|]+?)\s*\|\s*$")
SNAP = re.compile(r"standings_global_(\d{4})_(\d{2})_(\d{2})\.md$")


def snapshot_date(path: Path) -> date:
    m = SNAP.search(path.name)
    return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def standings(path: Path) -> list[tuple[int, frozenset]]:
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = ROW.match(line.strip())
        if m and m.group(2).isdigit():
            roster = frozenset(x.strip().casefold() for x in m.group(4).split(",") if x.strip())
            out.append((int(m.group(2)), roster))
    return out


def lookup(prev: list[tuple[int, frozenset]], roster: frozenset) -> int | None:
    hits = [pts for pts, r in prev if len(r & roster) >= 3]
    return hits[0] if len(hits) == 1 else None


def window_matches(details_dir: Path, lo: date, hi: date) -> dict[str, list]:
    found: dict[str, dict] = {}
    for f in sorted(details_dir.glob("*.md")):
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = DETAIL.match(line.strip())
            if not m:
                continue
            day = date(int(m.group(2)), int(m.group(3)), int(m.group(4)))
            if not (lo < day <= hi):
                continue
            roster = frozenset(x.strip().casefold() for x in m.group(6).split(",") if x.strip())
            rec = found.setdefault(m.group(1), {})
            rec.setdefault(m.group(5), set()).add(roster)
    return found


def collect_pairs(repo: Path) -> list[list[tuple[float, int]]]:
    """Per window: list of (delta = pts_team1 - pts_team2, team1_won) with team1 = winner/loser alternated."""
    snaps = sorted(repo.glob("live/*/standings_global_*.md"), key=snapshot_date)
    windows = []
    for prev_path, cur_path in zip(snaps, snaps[1:]):
        lo, hi = snapshot_date(prev_path), snapshot_date(cur_path)
        details = cur_path.parent / "details" / cur_path.stem.replace("standings_global_", "")
        if not details.is_dir():
            continue
        prev = standings(prev_path)
        pairs, flip = [], False
        for _, sides in sorted(window_matches(details, lo, hi).items()):
            if set(sides) != {"W", "L"} or len(sides["W"]) != 1 or len(sides["L"]) != 1:
                continue
            pw, pl = lookup(prev, next(iter(sides["W"]))), lookup(prev, next(iter(sides["L"])))
            if pw is None or pl is None:
                continue
            # alternate orientation so the sample is symmetric (team1 is not always the winner)
            pairs.append((pw - pl, 1) if not flip else (pl - pw, 0))
            flip = not flip
        if pairs:
            windows.append({"s_prev": str(lo), "s_cur": str(hi), "pairs": pairs})
    return windows


def loglik(k: float, pairs) -> float:
    total = 0.0
    for delta, won in pairs:
        p = 1.0 / (1.0 + 10.0 ** (-k * delta / 400.0))
        p = min(max(p, 1e-9), 1 - 1e-9)
        total += math.log(p if won else 1.0 - p)
    return total


def fit(pairs) -> float:
    lo, hi = 0.01, 2.0
    for _ in range(80):                     # golden-section search on a concave log-likelihood
        m1 = hi - (hi - lo) / 1.618
        m2 = lo + (hi - lo) / 1.618
        if loglik(m1, pairs) < loglik(m2, pairs):
            lo = m1
        else:
            hi = m2
    return round((lo + hi) / 2, 4)


def brier(k: float, pairs) -> float:
    return sum((1.0 / (1.0 + 10.0 ** (-k * d / 400.0)) - w) ** 2 for d, w in pairs) / len(pairs)


def main() -> int:
    repo = Path(os.environ.get("VRS_REPO_DIR", ""))
    if not repo.is_dir():
        write_json(OUT, {"status": "unavailable", "reason": "VRS_REPO_DIR not set or missing",
                         "k": round(K_VALVE_RAW, 6), "k_source": "Valve raw g (uncalibrated)",
                         "generated_utc": now_iso()})
        print("calibrate: no Valve clone; raw Valve curve will be used and labelled uncalibrated")
        return 0
    windows = collect_pairs(repo)
    if len(windows) < 3:
        write_json(OUT, {"status": "insufficient", "windows": len(windows), "k": round(K_VALVE_RAW, 6),
                         "k_source": "Valve raw g (uncalibrated)", "generated_utc": now_iso()})
        print("calibrate: too few windows")
        return 0
    train = [p for w in windows[:-1] for p in w["pairs"]]
    test = windows[-1]["pairs"]
    k = fit(train)
    result = {
        "status": "ok",
        "method": "MLE of k in P = 1/(1+10^(-k*dPoints/400)); dPoints from the previous Valve snapshot; "
                  "rosters matched with >= 3 shared players; last window held out",
        "valve_repo": "https://github.com/ValveSoftware/counter-strike_regional_standings",
        "valve_commit": os.environ.get("VRS_COMMIT") or None,
        "k": k,
        "k_source": "fitted on Valve's published match results",
        "k_valve_raw": round(K_VALVE_RAW, 6),
        "n_train": len(train), "n_test": len(test), "windows": len(windows),
        "first_window": windows[0]["s_prev"], "last_window": f"{windows[-1]['s_prev']}..{windows[-1]['s_cur']}",
        "holdout": {
            "log_loss_fitted": round(-loglik(k, test) / len(test), 4),
            "log_loss_valve_raw": round(-loglik(K_VALVE_RAW, test) / len(test), 4),
            "brier_fitted": round(brier(k, test), 4),
            "brier_valve_raw": round(brier(K_VALVE_RAW, test), 4),
        },
        "generated_utc": now_iso(),
    }
    # adopt the fit only if it beats Valve's raw curve out of sample
    if result["holdout"]["log_loss_fitted"] > result["holdout"]["log_loss_valve_raw"]:
        result["status"] = "rejected_out_of_sample"
        result["k"] = round(K_VALVE_RAW, 6)
        result["k_source"] = "Valve raw g (fit did not beat it out of sample)"
    write_json(OUT, result)
    print(f"calibrate: k={result['k']} ({result['k_source']}); train n={len(train)}, test n={len(test)}; "
          f"holdout log-loss fitted {result['holdout']['log_loss_fitted']} vs raw {result['holdout']['log_loss_valve_raw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
