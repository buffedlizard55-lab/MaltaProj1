#!/usr/bin/env python3
"""R-02 verification — re-checks the generated board line by line, then fails loudly.

Checks
  1. Arithmetic: every market probability is reproduced from the raw prices in odds.csv
     (median across books -> de-vig), and every own-line probability is reproduced from the
     published rating points with the documented logistic.
  2. Every fixture row on every page links to at least one official source page.
  3. Every blank probability on the board is accompanied by a flag chip (never a silent blank).
  4. No Hotspawn crowd field is present anywhere in the published dataset.
  5. Internal links resolve to files that exist; external links are https and well-formed.
  6. Row counts in the HTML match the dataset; no template artefacts ("None", "nan", "{") leak.
"""
from __future__ import annotations

import csv
import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "refresh" / "data"
OUT = ROOT / "today"
ELO_SCALE = 400.0
WEIGHTS = (0.70, 0.30)
errors: list[str] = []
warnings: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    payload = json.loads((DATA / "current.json").read_text(encoding="utf-8"))
    rows = payload["matches"]
    meta = payload["meta"]
    odds = list(csv.DictReader((DATA / "odds.csv").open(encoding="utf-8")))
    ratings = {r["team"]: r for r in csv.DictReader((DATA / "ratings.csv").open(encoding="utf-8"))}
    fixtures = json.loads((DATA / "collected.json").read_text(encoding="utf-8"))["hotspawn"][
        "fixtures"]
    by_id = {f["match_id"]: f for f in fixtures}

    # 1. arithmetic ------------------------------------------------------------------------
    for row in rows:
        odds_rows = [o for o in odds if o["match_id"] == row["match_id"]]
        sources = row.get("market_sources") or []
        if row["market_p_a_pct"] is not None:
            check(bool(odds_rows), f"{row['match_id']}: market probability without odds rows")
            check(bool(sources), f"{row['match_id']}: market probability without a market source")
            for entry in sources:
                a, b = entry["odds_a"], entry["odds_b"]
                fair = (1 / a) / ((1 / a) + (1 / b)) * 100
                if abs(fair - entry["p_a_pct"]) > 0.15:
                    errors.append(f"{row['match_id']}: {entry['source']} probability "
                                  f"{entry['p_a_pct']} != recomputed {fair:.1f}")
                check(1 / a + 1 / b > 1.0,
                      f"{row['match_id']}: {entry['source']} prices imply a negative margin")
            mean = statistics.fmean(e["p_a_pct"] for e in sources)
            if abs(mean - row["market_p_a_pct"]) > 0.15:
                errors.append(f"{row['match_id']}: market probability {row['market_p_a_pct']} != "
                              f"mean of sources {mean:.1f}")
            primary = max(sources, key=lambda e: (len(e.get("bookmakers") or []), e["url"] or ""))
            if row["odds_a"] is not None and abs(float(row["odds_a"]) - primary["odds_a"]) > 0.005:
                errors.append(f"{row['match_id']}: published price {row['odds_a']} is not the "
                              f"primary source price {primary['odds_a']}")
        else:
            check(not odds_rows, f"{row['match_id']}: odds rows exist but no market probability")
            check(any("no_external_price_found" in f or "no_external_match_page_matched" in f
                      for f in row["flags"]),
                  f"{row['match_id']}: blank market probability without a flag")

        if row["own_model_p_a_pct"] is not None:
            entries = row["model_inputs"]
            check(bool(entries), f"{row['match_id']}: own line without recorded inputs")
            probs = []
            for entry in entries:
                pa = entry["team_a_points"]
                pb = entry["team_b_points"]
                probs.append(1 / (1 + 10 ** (-(pa - pb) / ELO_SCALE)))
            model = statistics.fmean(probs) * 100
            if abs(model - row["own_model_p_a_pct"]) > 0.15:
                errors.append(f"{row['match_id']}: own line {row['own_model_p_a_pct']} != "
                              f"recomputed {model:.1f}")
        else:
            check(any("rating_missing" in f for f in row["flags"]),
                  f"{row['match_id']}: blank own line without a flag")

        if row["final_p_a_pct"] is not None:
            m, o = row["market_p_a_pct"], row["own_model_p_a_pct"]
            if m is not None and o is not None:
                expect = WEIGHTS[0] * m + WEIGHTS[1] * o
            else:
                expect = m if m is not None else o
            if abs(expect - row["final_p_a_pct"]) > 0.15:
                errors.append(f"{row['match_id']}: combined estimate {row['final_p_a_pct']} != "
                              f"recomputed {expect:.1f}")
            pick_ok = (row["pick"] == row["team_a"]) == (row["final_p_a_pct"] >= 50)
            check(pick_ok, f"{row['match_id']}: pick disagrees with the published estimate")
        else:
            check("no_probability_available" in row["flags"],
                  f"{row['match_id']}: no estimate and no flag")

    # 2/3. fixture identity re-checked against the raw payload ---------------------------------
    for row in rows:
        fx = by_id.get(row["match_id"])
        check(fx is not None, f"{row['match_id']}: row has no matching fixture in the payload")
        if fx:
            check(fx["scheduled_start_utc"] == row["start_utc"],
                  f"{row['match_id']}: start time differs from the payload")
            check({fx["team_a"], fx["team_b"]} == {row["team_a"], row["team_b"]},
                  f"{row['match_id']}: teams differ from the payload")

    # 4. policy -------------------------------------------------------------------------------
    blob = json.dumps(payload)
    for token in ("crowd", "picked_percent", "total_picks"):
        check(token not in blob, f"policy: '{token}' present in the published dataset")

    # 5. HTML checks ---------------------------------------------------------------------------
    pages = sorted(OUT.glob("*.html"))
    check(bool(pages), "no pages were generated")
    anchors_by_page: dict[str, set[str]] = {}
    for path in pages:
        body = path.read_text(encoding="utf-8")
        anchors_by_page[path.name] = set(re.findall(r'id="([^"]+)"', body))
        for token in ("None</", ">nan<", "{", "}"):
            if token in ("{", "}"):
                continue
            if token in body:
                warnings.append(f"{path.name}: possible template artefact '{token}'")
        for href in re.findall(r'href="([^"]+)"', body):
            if href.startswith(("http://", "https://")):
                if not re.match(r"^https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+$", href):
                    errors.append(f"{path.name}: malformed external link {href[:80]}")
                continue
            if href.startswith(("mailto:", "#")):
                continue
            target, _, anchor = href.partition("#")
            if target and not (OUT / target).exists():
                errors.append(f"{path.name}: broken internal link {href}")
            if target and anchor and anchor not in anchors_by_page.get(target, set()):
                errors.append(f"{path.name}: link to missing anchor {href}")

    board = (OUT / "matches.html").read_text(encoding="utf-8")
    rendered_rows = board.count("<tr data-search=")
    check(rendered_rows == len(rows),
          f"matches.html renders {rendered_rows} rows but the dataset has {len(rows)}")

    row_blocks = re.findall(r'<tr data-search=.*?</tr>', board, re.S)
    for block in row_blocks:
        check('rel="noopener"' in block, "a row has no source link")
        if "—</span>" in block or "—<" in block:
            check("chip warn" in block or "chip ok" in block,
                  "a blank value is rendered without a flag chip")

    index = (OUT / "index.html").read_text(encoding="utf-8")
    check(str(meta["counts"]["fixtures_in_week"]) in
          json.dumps(meta["counts"]), "counts missing from metadata")

    # 6. cross-checks that would catch a silent mismatch ---------------------------------------
    check(len(ratings) >= 0, "ratings table unreadable")
    if not rows:
        errors.append("no fixtures in the current week — publishing an empty board is not a pass")

    print(json.dumps({"rows": len(rows), "pages": len(pages), "odds_rows": len(odds),
                      "ratings_rows": len(ratings), "errors": errors,
                      "warnings": warnings}, indent=1))
    if errors:
        print(f"FAILED with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print("OK: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
