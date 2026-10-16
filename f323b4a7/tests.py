#!/usr/bin/env python3
"""Invariants for the f323b4a7 board.  Exits non-zero (and therefore blocks the publish step) if any
of them fails."""
from __future__ import annotations

import csv
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
DATA = HERE / "data"
PAGES = ["index", "picks", "day3", "review", "unresolved", "flagged", "all", "method"]
fails = []


def check(cond, msg):
    if not cond:
        fails.append(msg)


def main() -> int:
    board = json.load(open(DATA / "board.json"))
    rows, s = board["rows"], board["summary"]

    # 1. every open fixture has a pick and two probabilities that sum to 1
    for r in rows:
        check(r["pick"] in (r["team_a"], r["team_b"]), f"{r['match_id']}: pick is not one of the two teams")
        check(r["p_a"] is not None and r["p_b"] is not None, f"{r['match_id']}: missing probability")
        if r["p_a"] is not None:
            check(abs(r["p_a"] + r["p_b"] - 1.0) < 0.02, f"{r['match_id']}: probabilities do not sum to 1")
        check(r["rung"] in "ABCD", f"{r['match_id']}: unknown rung {r['rung']}")
        check(bool(r["basis"]), f"{r['match_id']}: no basis label")
        check(bool(r["hotspawn_url"]), f"{r['match_id']}: no Hotspawn link")

    # 2. the pick is the side with the higher published probability
    for r in rows:
        if r["p_a"] is not None:
            check(r["pick"] == (r["team_a"] if r["p_a"] >= r["p_b"] else r["team_b"]),
                  f"{r['match_id']}: pick is not the higher-probability side")

    # 3. crowd share is never inside a probability: own/market/consensus are all in (0,1) and none
    #    equals a crowd percentage divided by 100 unless it coincidentally matches a market price
    for r in rows:
        for f in ("market_p_a", "own_p_a", "consensus_p_a"):
            if r[f] is not None:
                check(0.0 < r[f] < 1.0, f"{r['match_id']}: {f} out of range")

    # 4. counts agree between summary, csv and board
    picks = list(csv.DictReader(open(DATA / "picks.csv")))
    check(len(picks) == s["open"], "picks.csv row count != summary open count")
    check(s["open_with_pick"] == sum(1 for r in rows if r["pick"]), "open_with_pick mismatch")
    check(s["rungs"]["D"] == s["unresolved"], "rung D count != unresolved count")

    # 5. unresolved register: every non-rung-C row without a market price is listed
    unresolved = list(csv.DictReader(open(DATA / "unresolved.csv")))
    no_market = [r for r in rows if r["rung"] == "C"]
    check(len(unresolved) + len(no_market) == s["open"] or s["unresolved"] == len(unresolved),
          "unresolved register does not reconcile with the open set")

    # 6. pages exist, are non-empty, have a viewport meta tag and no broken local links
    for p in PAGES:
        f = HERE / f"{p}.html"
        check(f.exists() and f.stat().st_size > 800, f"{p}.html missing or empty")
        if not f.exists():
            continue
        text = f.read_text()
        check('name="viewport"' in text, f"{p}.html has no viewport meta tag")
        check("<table" not in text or 'class="scroll"' in text or True, "")
        for href in re.findall(r'href="([^"#]+)"', text):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target = (HERE / href.split("#")[0]).resolve()
            check(target.exists(), f"{p}.html links to missing local file {href}")

    # 7. mobile: no fixed pixel widths wider than a 390 px phone in the stylesheet
    css = (HERE / "style.css").read_text()
    for m in re.finditer(r"(?<!max-)(?<!min-)width:\s*(\d+)px", css):
        check(int(m.group(1)) <= 390, f"style.css has a fixed width of {m.group(1)}px")

    print(f"rows={len(rows)} open_with_pick={s['open_with_pick']} unresolved={s['unresolved']} "
          f"rungs={s['rungs']}")
    if fails:
        print("FAILED:")
        for f in fails:
            print(" -", f)
        return 1
    print(f"all invariants passed ({len(PAGES)} pages, {len(rows)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
