#!/usr/bin/env python3
"""Calibrate the VRS expected-win curve on Valve's own published data (O-01, session arena/91eff436).

Why: Valve's README says the raw expected-vs-observed slope "is shallower than we'd like" because the
model "tends to underestimate win rates at the low end and overestimate at the high end". This script
measures that on official data and fits our own slope.

Method (Valve's evaluation recipe, applied to monthly snapshots):
  For each pair of consecutive snapshots (S_prev, S_cur), take every match listed in S_cur's per-team
  details tables (live/<year>/details/<S_cur>/*.md) dated after S_prev and on or before S_cur. Each table
  row carries Match ID, date, W/L and the roster that played, so both sides of a match are identified by
  their own rows (deduplicated by Match ID). Each side's PRE-MATCH rating is the S_prev global standings
  points of the unique S_prev row sharing >= 3 players with the roster that played (Valve team.js rule).
  Matches where either side has no unique S_prev row are skipped. No look-ahead: ratings always predate
  the match.
  Model family: P(win) = 1 / (1 + 10 ** (-k * delta / 400)). Valve's raw curve is k = g = 0.97282
  (fit.js priorWinExpectation, rd = 75). k is fitted by maximum likelihood.
  Validation: fit on the earlier windows, score log loss and Brier on the most recent windows (held out),
  for raw k = g versus fitted k. The published slope is then refit on all windows.

Usage: VRS_REPO_DIR=/path/to/counter-strike_regional_standings python3 model/calibrate.py
Output: model/input/vrs/calibration.json
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from build import G, OVERLAP, VALVE_REPO  # noqa: E402

ROW = re.compile(r"\|\s*(\d+)\s*\|\s*(-?\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*\[details\]")


def parse_standings(p: Path) -> list[dict]:
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        m = ROW.match(line)
        if m:
            out.append({"points": int(m[2]), "name": m[3].strip(),
                        "roster": frozenset(x.strip().casefold() for x in m[4].split(",") if x.strip())})
    return out


def parse_details(dirp: Path, lo: date, hi: date) -> dict:
    """Return {match_id: [(roster_frozenset, won_bool, date)]} for matches with lo < date <= hi."""
    matches: dict[str, list] = {}
    for f in dirp.glob("*.md"):
        txt = f.read_text(encoding="utf-8")
        hdr = None
        for line in txt.splitlines():
            if line.startswith("| Match Played"):
                hdr = [c.strip() for c in line.strip().strip("|").split("|")]
                continue
            if hdr and line.startswith("|") and not line.startswith("| -") and not line.startswith("| :"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) != len(hdr):
                    continue
                row = dict(zip(hdr, cells))
                try:
                    d = date.fromisoformat(row["Date"])
                except (KeyError, ValueError):
                    continue
                if not (lo < d <= hi) or row.get("W/L") not in ("W", "L"):
                    continue
                roster = frozenset(x.strip().casefold() for x in row.get("Roster", "").split(",") if x.strip())
                matches.setdefault(row["Match ID"], []).append((roster, row["W/L"] == "W", d))
            elif hdr and not line.startswith("|") and line.strip():
                hdr = None if line.startswith("#") else hdr
    return matches


def lookup(roster: frozenset, standings: list[dict]):
    hits = [r for r in standings if len(r["roster"] & roster) >= OVERLAP]
    return hits[0]["points"] if len(hits) == 1 else None


def p_of(k: float, delta: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-k * delta / 400.0))


def loglik(k: float, data) -> float:
    s = 0.0
    for delta, y in data:
        p = min(max(p_of(k, delta), 1e-12), 1 - 1e-12)
        s += math.log(p) if y else math.log(1 - p)
    return s


def fit_k(data) -> float:
    a, b = 0.01, 3.0
    phi = (math.sqrt(5) - 1) / 2
    c, d = b - phi * (b - a), a + phi * (b - a)
    for _ in range(80):
        if loglik(c, data) > loglik(d, data):
            b = d
        else:
            a = c
        c, d = b - phi * (b - a), a + phi * (b - a)
    return (a + b) / 2


def metrics(k: float, data) -> dict:
    n = len(data)
    ll = -loglik(k, data) / n
    brier = sum((p_of(k, d) - y) ** 2 for d, y in data) / n
    bins = []
    for lo in [i / 10 for i in range(5, 10)]:  # fold to favourite's perspective
        sel = [(max(p_of(k, d), 1 - p_of(k, d)), (y if p_of(k, d) >= 0.5 else 1 - y)) for d, y in data]
        sel = [(p, y) for p, y in sel if lo <= p < lo + 0.1 or (lo == 0.9 and p >= 1.0)]
        if sel:
            bins.append({"bin": f"{int(lo * 100)}-{int(lo * 100) + 10}%", "n": len(sel),
                         "mean_expected": round(sum(p for p, _ in sel) / len(sel), 4),
                         "observed": round(sum(y for _, y in sel) / len(sel), 4)})
    return {"n": n, "log_loss": round(ll, 5), "brier": round(brier, 5), "favourite_bins": bins}


def main() -> int:
    repo = Path(os.environ.get("VRS_REPO_DIR", "/tmp/vrs"))
    if not (repo / "live").is_dir():
        print(f"VRS_REPO_DIR not a Valve VRS clone: {repo}")
        return 1
    commit = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%H"], capture_output=True, text=True).stdout.strip()
    snaps = []
    for p in repo.glob("live/*/standings_global_*.md"):
        m = re.search(r"(\d{4})_(\d{2})_(\d{2})\.md$", p.name)
        if m:
            snaps.append((date(int(m[1]), int(m[2]), int(m[3])), p))
    snaps.sort()
    # Calibrate on the model year in use (Valve revises the model between seasons). Use the snapshots of
    # the latest snapshot's year plus the last snapshot of the previous year as the first S_prev.
    latest_year = snaps[-1][0].year
    use = [s for s in snaps if s[0].year == latest_year]
    prev_year = [s for s in snaps if s[0].year == latest_year - 1]
    if prev_year:
        use = [prev_year[-1]] + use
    windows = []
    for (d0, p0), (d1, p1) in zip(use, use[1:]):
        det = p1.parent / "details" / p1.name.replace("standings_global_", "").replace(".md", "")
        if not det.is_dir():
            continue
        prev = parse_standings(p0)
        ms = parse_details(det, d0, d1)
        data, skipped = [], 0
        for mid, sides in ms.items():
            if len(sides) != 2 or sides[0][1] == sides[1][1]:
                skipped += 1
                continue
            pa, pb = lookup(sides[0][0], prev), lookup(sides[1][0], prev)
            if pa is None or pb is None:
                skipped += 1
                continue
            data.append((pa - pb, 1 if sides[0][1] else 0))
        windows.append({"s_prev": d0.isoformat(), "s_cur": d1.isoformat(), "n": len(data), "skipped": skipped,
                        "data": data})
    allw = [w for w in windows if w["n"]]
    if len(allw) < 3:
        print("not enough windows")
        return 1
    test_w, train_w = allw[-2:], allw[:-2]
    train = [x for w in train_w for x in w["data"]]
    test = [x for w in test_w for x in w["data"]]
    k_train = fit_k(train)
    full = train + test
    k_all = fit_k(full)
    out = {
        "method": "MLE slope k for P=1/(1+10^(-k*delta/400)); delta = previous-snapshot VRS points difference; "
                  "both sides identified by roster (>=3 shared players, unique) in the previous snapshot.",
        "valve_repo": VALVE_REPO, "valve_commit": commit,
        "windows": [{k: w[k] for k in ("s_prev", "s_cur", "n", "skipped")} for w in windows],
        "raw_k_valve": round(G, 6),
        "train_windows": f"{train_w[0]['s_prev']}..{train_w[-1]['s_cur']}",
        "test_windows": f"{test_w[0]['s_prev']}..{test_w[-1]['s_cur']}",
        "k_fit_on_train": round(k_train, 4),
        "out_of_sample": {"raw": metrics(G, test), "calibrated_train_k": metrics(k_train, test)},
        "in_sample_all": {"raw": metrics(G, full), "calibrated": metrics(k_all, full)},
        "k_published": round(k_all, 4),
        "n_total": len(full),
    }
    oos = out["out_of_sample"]
    out["adopted"] = oos["calibrated_train_k"]["log_loss"] < oos["raw"]["log_loss"]
    dest = ROOT / "input" / "vrs" / "calibration.json"
    dest.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "windows"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
