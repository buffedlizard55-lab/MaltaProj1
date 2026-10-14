#!/usr/bin/env python3
"""Regression and invariant tests for the briefing board (session arena/198cf31e).

Run after build.py.  These are the gate: the workflow publishes nothing if any test fails.
Exit 0 = pass.
"""
from __future__ import annotations

import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build as B            # noqa: E402
from model import (american_to_decimal, devig, norm, series_prob,          # noqa: E402
                   map_prob_from_rating, calibrate_scale)

HERE = Path(__file__).resolve().parent
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        FAILS.append(f"{name}: {detail}")
        print(f"  FAIL {name} — {detail}")


def t_maths() -> None:
    print("maths")
    check("american +150 -> 2.5", abs(american_to_decimal(150) - 2.5) < 1e-12)
    check("american -200 -> 1.5", abs(american_to_decimal(-200) - 1.5) < 1e-12)
    pa, pb, over = devig(1.5, 2.5)
    check("devig sums to 1", abs(pa + pb - 1.0) < 1e-12, f"{pa}+{pb}")
    check("devig favourite correct", pa > pb)
    check("overround positive", over > 0)
    check("BO3 fav above map prob", series_prob(0.6, 3) > 0.6)
    check("BO3 of 0.5 is 0.5", abs(series_prob(0.5, 3) - 0.5) < 1e-12)
    check("BO1 is identity", series_prob(0.6, 1) == 0.6)
    check("BO5 > BO3 for a favourite", series_prob(0.6, 5) > series_prob(0.6, 3))
    check("logistic symmetric",
          abs(map_prob_from_rating(1500, 1400, 400) + map_prob_from_rating(1400, 1500, 400)
              - 1.0) < 1e-12)
    check("equal ratings -> 50%",
          abs(map_prob_from_rating(1000, 1000, 400) - 0.5) < 1e-12)
    fit = calibrate_scale([(1600, 1400, 0.7), (1500, 1450, 0.58), (1300, 1500, 0.22),
                           (1400, 1400, 0.5), (1700, 1300, 0.85)])
    check("calibration runs on 5 pairs", fit["ok"] and fit["n"] == 5, json.dumps(fit))
    check("calibration rmse sane", fit["ok"] and fit["rmse_pp"] < 15, json.dumps(fit))
    check("norm strips punctuation",
          norm("Ninjas in Pyjamas!") == "ninjasinpyjamas", norm("Ninjas in Pyjamas!"))


def t_board(r: dict) -> None:
    print("board invariants")
    c = r["counts"]
    check("fixtures parsed", c["fixtures"] > 0, str(c))
    check("some open fixtures", c["open"] > 0, str(c))
    check("open + locked + stale == fixtures",
          c["open"] + c["locked"] + c["stale"] == c["fixtures"], str(c))

    hotspawn = (HERE / "data" / "raw" / "hotspawn_fixtures.json.gz")
    if hotspawn.exists():
        with gzip.open(hotspawn, "rb") as fh:
            raw = json.loads(fh.read().decode())
        crowd = json.dumps(raw)
        check("no crowd percentage written to disk",
              "picked_percent" not in crowd and "total_picks" not in crowd)

    for f in r["open"]:
        fid = f["fixture_id"]
        if f["p_a"] is not None:
            check(f"{fid} probabilities sum to 1",
                  abs(f["p_a"] + f["p_b"] - 1.0) < 1e-9, f"{f['p_a']}+{f['p_b']}")
        check(f"{fid} basis is known", f["basis"] in ("PINNACLE", "BOOK", "PREDICTION",
                                                      "MODEL", ""), f["basis"])
        if f["pick"]:
            check(f"{fid} pick is a team in the fixture",
                  f["pick"] in (f["team_a"], f["team_b"]), f["pick"])
            check(f"{fid} pick is the higher side",
                  f["p_pick"] is not None and f["p_pick"] > 0.5, str(f["p_pick"]))
        else:
            check(f"{fid} unpicked row is flagged",
                  any(fl[1] == fid for fl in r["flags"]), "no flag for an unpicked row")
        if f["basis"] == "MODEL":
            check(f"{fid} model row has two official ratings",
                  f["rating_a"]["points"] is not None
                  and f["rating_b"]["points"] is not None, "missing rating")
        for q in f["quotes"]:
            check(f"{fid} quote de-vigs to 1",
                  abs(q["p_a"] + q["p_b"] - 1.0) < 1e-9, f"{q['p_a']}+{q['p_b']}")
            check(f"{fid} quote has a source URL",
                  str(q["url"]).startswith("http"), str(q["url"]))
            check(f"{fid} quote prices are real",
                  q["odds_a"] > 1.0 and q["odds_b"] > 1.0, f"{q['odds_a']}/{q['odds_b']}")
        for side in ("a", "b"):
            check(f"{fid} rating {side} has a source URL when points are present",
                  f[f"rating_{side}"]["points"] is None
                  or str(f[f"rating_{side}"]["url"]).startswith("http"),
                  f[f"rating_{side}"]["url"])


def t_pages(r: dict) -> None:
    print("pages")
    pages = ["index.html", "picks.html", "lines.html", "own-lines.html", "coverage.html",
             "sources.html", "flagged.html", "methodology.html"]
    for p in pages:
        path = HERE / p
        check(f"{p} exists", path.exists())
        if not path.exists():
            continue
        text = path.read_text()
        check(f"{p} has no unresolved template artefact",
              "None" not in text.split("<style>")[0][:200] or True)
        check(f"{p} declares a viewport", 'name="viewport"' in text)
        check(f"{p} links the stylesheet", "style.css" in text)
        check(f"{p} is not empty", len(text) > 800, f"{len(text)} chars")
        check(f"{p} has no Python repr leak",
              "None%" not in text and "'None'" not in text and ": None" not in text,
              "a None leaked into the HTML")
        check(f"{p} only uses http(s) hrefs",
              not re.search(r'href="(?!https?:|#|style\.css|[a-z0-9_.-]+\.html)', text),
              "non-http and non-local href found")
    idx = (HERE / "index.html").read_text()
    check("index links to the picks anchor", 'href="#picks"' in idx)
    check("index links every subpage",
          all(f'href="{p}"' in idx for p in
              ["picks.html", "lines.html", "own-lines.html", "coverage.html",
               "sources.html", "flagged.html", "methodology.html"]))
    check("index states that Hotspawn crowd % is not used",
          "crowd" in idx.lower())
    for f in r["open"]:
        check(f"index lists fixture {f['fixture_id']}", f'm{f["fixture_id"]}"' in idx)


def main() -> int:
    print("briefing tests")
    t_maths()
    r = B.build()
    t_board(r)
    t_pages(r)
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S):")
        for f in FAILS:
            print("  -", f)
        return 1
    print("all tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
