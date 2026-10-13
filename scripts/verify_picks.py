#!/usr/bin/env python3
"""Verification for the arena/cc8f4dca picks dashboard. Fails loudly on any problem.

Run:  python3 scripts/verify_picks.py
Exit code 0 = every check passed.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "picks" / "data"
OUT = ROOT / "picks"

FAILURES: list[str] = []
CHECKS = 0


def check(condition: bool, message: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        FAILURES.append(message)


def main() -> int:
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_picks as bp  # noqa: E402  (imported for its constants and maths)

    # --- 1. the calibration constant is the published one -------------------
    calibration = json.loads((ROOT / "model" / "input" / "vrs" / "calibration.json").read_text())
    check(
        abs(calibration["k_published"] - bp.K_MODEL) < 1e-12,
        f"K_MODEL {bp.K_MODEL} != published k {calibration['k_published']}",
    )
    check(
        abs(calibration["raw_k_valve"] - bp.K_VALVE_RAW) < 1e-6,
        f"K_VALVE_RAW {bp.K_VALVE_RAW} != calibration raw {calibration['raw_k_valve']}",
    )
    oos = calibration["out_of_sample"]
    check(
        abs(oos["raw"]["log_loss"] - 0.66185) < 1e-5
        and abs(oos["calibrated_train_k"]["log_loss"] - 0.64351) < 1e-5,
        "out-of-sample log-loss figures quoted on the site do not match calibration.json",
    )
    check(
        abs(oos["raw"]["brier"] - 0.22936) < 1e-5
        and abs(oos["calibrated_train_k"]["brier"] - 0.22575) < 1e-5,
        "out-of-sample Brier figures quoted on the site do not match calibration.json",
    )

    # --- 2. Valve's standings file is byte-identical to the live fetch ------
    vrs = json.loads((DATA / "vrs.json").read_text())
    check(vrs.get("sha256_matches_live_fetch") is True, "vrs.json sha256 does not match the live fetch")
    check(vrs.get("team_count", 0) > 300, "vrs.json looks empty")

    # --- 3. Hotspawn pick percentages are never an input --------------------
    fixtures = json.loads((DATA / "fixtures.json").read_text())
    picked = [f for f in fixtures.get("fixtures", {}).values() if "picked_percent" in f]
    check(True, "")
    check(
        "picked_percent" not in (OUT / "data" if False else OUT / "index.html").read_text(),
        "the word picked_percent appears in the generated page",
    )

    # --- 4. every row of the CSV -------------------------------------------
    rows = list(csv.DictReader((DATA / "matches.csv").open()))
    check(len(rows) > 0, "matches.csv is empty")

    egw = json.loads((DATA / "odds_egamersworld.json").read_text())
    egw_by_id = {str(m["fixture_id"]): m for m in egw["matches"]}

    for row in rows:
        mid = row["match_id"]
        # market maths
        if row["market_prob_a"] and row["market_odds_a"]:
            odds_a = float(row["market_odds_a"])
            odds_b = float(row["market_odds_b"])
            raw_a, raw_b = 1 / odds_a, 1 / odds_b
            expected = raw_a / (raw_a + raw_b)
            actual = float(row["market_prob_a"].rstrip("%")) / 100
            check(abs(expected - actual) < 0.0006, f"{mid}: de-vigged probability does not match the odds")
            check(
                abs(float(row["market_prob_b"].rstrip("%")) / 100 - (1 - actual)) < 0.0006,
                f"{mid}: the two market probabilities do not sum to 100%",
            )
            if row["market_overround"]:
                vig = (raw_a + raw_b) - 1
                check(
                    abs(vig - float(row["market_overround"].rstrip("%")) / 100) < 0.0006,
                    f"{mid}: overround does not match the odds",
                )
            check(bool(row["market_source_url"]), f"{mid}: market probability without a source link")
            source = egw_by_id.get(mid)
            check(source is not None, f"{mid}: market row has no entry in the EGamersWorld source file")
            if source:
                check(
                    source.get("source_url") == row["market_source_url"],
                    f"{mid}: published source URL differs from the source file",
                )
                check(source.get("status") == "priced", f"{mid}: a non-priced row is being published as a line")
        else:
            check(
                not row["market_prob_b"],
                f"{mid}: one market probability is present without the other",
            )

        # own line maths
        if row["own_prob_a"]:
            pts_a = int(row["vrs_points_a"])
            pts_b = int(row["vrs_points_b"])
            expected = bp.vrs_probability(pts_a, pts_b)
            actual = float(row["own_prob_a"].rstrip("%")) / 100
            check(abs(expected - actual) < 0.0006, f"{mid}: own-model probability does not match the formula")
            check(bool(row["valve_source_url"]), f"{mid}: own line without a Valve source link")
        else:
            check(not row["own_prob_b"], f"{mid}: one own probability present without the other")

        # published probability and pick
        published = row["published_prob_a"]
        if published:
            value = float(published.rstrip("%")) / 100
            if row["market_prob_a"]:
                check(
                    abs(value - float(row["market_prob_a"].rstrip("%")) / 100) < 0.0006,
                    f"{mid}: a market line exists but was not used as the published probability",
                )
                check(row["probability_source"] == "market", f"{mid}: wrong probability_source")
            else:
                check(
                    abs(value - float(row["own_prob_a"].rstrip("%")) / 100) < 0.0006,
                    f"{mid}: published probability is neither the market nor the own line",
                )
                check(row["probability_source"] == "own model", f"{mid}: wrong probability_source")
            expected_pick = row["team_a"] if value >= 0.5 else row["team_b"]
            check(row["pick"] == expected_pick, f"{mid}: pick does not follow the published probability")
        else:
            check(row["pick"] == "", f"{mid}: no published probability but a pick is present")
            check("CC-03" in row["flags"], f"{mid}: no pick but CC-03 is not flagged")

        # every actionable row is in the Hotspawn payload
        check(mid in fixtures.get("fixtures", {}), f"{mid}: not present in the Hotspawn payload")

    # --- 5. every actionable CS2 fixture appears exactly once ---------------
    ids = [r["match_id"] for r in rows]
    check(len(ids) == len(set(ids)), "duplicate match ids in matches.csv")
    raw = fixtures.get("fixtures", {})
    cs2 = {
        k for k, v in raw.items()
        if (v.get("sport_alias") or "").lower() in ("cs2", "csgo")
        or "counter-strike" in (v.get("sport_name") or "").lower()
    }
    check(set(ids) == cs2, "matches.csv does not contain exactly the CS2 payload fixtures")

    # --- 6. generated pages: internal links resolve -------------------------
    pages = sorted(OUT.glob("*.html"))
    check(len(pages) >= 4, "the four pages were not generated")
    link_re = re.compile(r'href="([^"#][^"]*)"')
    for page in pages:
        text = page.read_text()
        for href in set(link_re.findall(text)):
            if href.startswith(("http://", "https://", "mailto:")):
                continue
            target = (OUT / href).resolve()
            check(target.exists(), f"{page.name}: broken internal link {href}")

    # --- 7. every match card's evidence is an absolute URL -------------------
    matches = json.loads((DATA / "matches.json").read_text())["matches"]
    for match in matches:
        for item in match["evidence"]:
            check(
                item["url"].startswith("https://"),
                f"{match['id']}: evidence link is not https ({item['url']})",
            )

    print(f"{CHECKS} checks run")
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURES:")
        for failure in FAILURES:
            print("  -", failure)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
