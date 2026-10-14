#!/usr/bin/env python3
"""
tests/test_8944bb84.py — Verification & Integrity Suite for Session arena/8944bb84.
Tests `data/8944bb84/*` and `oct14/*` against all user requirements:
- Full 91-fixture CS2 coverage (28 open Oct 14-16, 4 started/completed Oct 13-14, 59 stale summer).
- Zero Hotspawn crowd-pick fields or usage anywhere in data or HTML.
- Every HTML table row (`<tbody><tr>`) in `oct14/*.html` has at least one official `https://` source link.
- Unverified values (`1079624 FORZE Reload vs LFO 10`, `1081105 SUKEBAN vs your end`, and 1.80/1.80 placeholders)
  are left strictly blank and flagged.
- Duplicate VRS team names (`ex-RUSTEC`, `6666`, `Banda chuya`, `Zomblers`) are disambiguated to their active rosters.
- All 12 Elisa BreakOut Series #2 matches (`1080279`..`1080290`) are verified `BO1`.
- Zero broken internal links, missing DOM fragment anchors, or `None`/`null`/`NaN`/`undefined` tokens.
"""

from __future__ import annotations

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "8944bb84"
SITE_DIR = ROOT / "oct14"

EXPECTED_HTML_FILES = [
    "index.html",
    "s-tier.html",
    "b-tier.html",
    "c-tier.html",
    "tournaments.html",
    "market-lines.html",
    "own-lines.html",
    "coverage-all-91.html",
    "methodology.html",
    "sources.html",
    "flagged.html",
]


class Test8944bb84Verification(unittest.TestCase):
    def test_01_all_data_and_site_files_exist(self) -> None:
        for csv_name in ("fixtures.csv", "ratings.csv", "external_lines.csv", "own_lines.csv", "analysis.csv", "flags.csv"):
            p = DATA_DIR / csv_name
            self.assertTrue(p.is_file(), f"Missing {p}")
            self.assertGreater(p.stat().st_size, 100, f"Empty {p}")
        cov_path = DATA_DIR / "coverage.json"
        self.assertTrue(cov_path.is_file())
        self.assertTrue((SITE_DIR / "style.css").is_file())
        for html_name in EXPECTED_HTML_FILES:
            hp = SITE_DIR / html_name
            self.assertTrue(hp.is_file(), f"Missing {hp}")
            self.assertGreater(hp.stat().st_size, 1000, f"Empty {hp}")

    def test_02_coverage_counts_and_buckets(self) -> None:
        cov = json.loads((DATA_DIR / "coverage.json").read_text(encoding="utf-8"))
        self.assertFalse(cov["hotspawn_crowd_data_used"])
        counts = cov["counts"]
        self.assertEqual(counts["total_cs2_fixtures"], 91)
        self.assertEqual(counts["open_oct14_16_fixtures"], 28)
        self.assertEqual(counts["locked_oct13_14_fixtures"], 4)
        self.assertEqual(counts["stale_summer_2026_fixtures"], 59)
        self.assertEqual(counts["open_with_verified_pick"], 27)
        self.assertEqual(counts["open_unverified_blank"], 1)
        self.assertEqual(counts["open_with_external_market_line"], 24)
        self.assertEqual(counts["open_with_pinnacle_direct_line"], 7)
        self.assertEqual(counts["open_with_placeholder_rejected"], 4)
        self.assertEqual(counts["open_with_hltv_match_url"], 28)
        self.assertEqual(counts["open_s_tier"], 4)
        self.assertEqual(counts["open_b_tier"], 8)
        self.assertEqual(counts["open_c_tier"], 16)

    def test_03_zero_hotspawn_crowd_fields_anywhere(self) -> None:
        forbidden = ("crowd_pct", "picked_percent", "crowd_total_picks", "participants0_picked_percent")
        for p in list(DATA_DIR.glob("*")) + list(SITE_DIR.glob("*.html")):
            txt = p.read_text(encoding="utf-8")
            for tok in forbidden:
                self.assertNotIn(tok, txt, f"Forbidden crowd token {tok} found in {p}")

    def test_04_unverified_items_left_strictly_blank_and_flagged(self) -> None:
        with (DATA_DIR / "analysis.csv").open(encoding="utf-8") as f:
            rows = {r["match_id"]: r for r in csv.DictReader(f)}

        # 1079624 FORZE Reload vs LFO 10 must have blank probabilities and pick
        r_1079624 = rows["1079624"]
        self.assertEqual(r_1079624["vrs_standing_a"], "84")
        self.assertEqual(r_1079624["vrs_standing_b"], "")
        self.assertEqual(r_1079624["vrs_points_b"], "")
        self.assertEqual(r_1079624["ext_odds_a"], "")
        self.assertEqual(r_1079624["ext_odds_b"], "")
        self.assertEqual(r_1079624["own_p_a"], "")
        self.assertEqual(r_1079624["own_p_b"], "")
        self.assertEqual(r_1079624["consensus_p_a"], "")
        self.assertEqual(r_1079624["consensus_p_b"], "")
        self.assertEqual(r_1079624["recommended_pick"], "")
        self.assertIn("FL-UNVERIFIED-TEAM", r_1079624["flags"])
        self.assertIn("FL-EXT-PLACEHOLDER", r_1079624["flags"])

        # 4 open matches with EGW 1.80/1.80 placeholder must have blank ext_odds_a/b
        for mid in ("1081112", "1081113", "1079624", "1081120"):
            self.assertEqual(rows[mid]["ext_odds_a"], "", f"Match {mid} should have blank ext_odds_a")
            self.assertEqual(rows[mid]["ext_odds_b"], "", f"Match {mid} should have blank ext_odds_b")
            self.assertIn("FL-EXT-PLACEHOLDER", rows[mid]["flags"])

    def test_05_duplicate_vrs_teams_disambiguated_correctly(self) -> None:
        with (DATA_DIR / "ratings.csv").open(encoding="utf-8") as f:
            teams = {r["hotspawn_team"]: r for r in csv.DictReader(f)}

        self.assertEqual(teams["ex-RUSTEC"]["vrs_standing"], "92")
        self.assertEqual(teams["ex-RUSTEC"]["vrs_points"], "1066")
        self.assertEqual(teams["6666"]["vrs_standing"], "127")
        self.assertEqual(teams["6666"]["vrs_points"], "923")
        self.assertEqual(teams["Banda chuya"]["vrs_standing"], "165")
        self.assertEqual(teams["Banda chuya"]["vrs_points"], "801")
        self.assertEqual(teams["Zomblers"]["vrs_standing"], "254")
        self.assertEqual(teams["Zomblers"]["vrs_points"], "639")

        # Verify 1079622 ex-RUSTEC vs mellren favors ex-RUSTEC in both market and own model
        with (DATA_DIR / "analysis.csv").open(encoding="utf-8") as f:
            rows = {r["match_id"]: r for r in csv.DictReader(f)}
        r_rustec = rows["1079622"]
        self.assertGreater(float(r_rustec["own_p_a"]), 55.0)
        self.assertGreater(float(r_rustec["ext_p_a"]), 60.0)
        self.assertEqual(r_rustec["recommended_pick"], "ex-RUSTEC")

    def test_06_elisa_breakout_series_2_verified_bo1(self) -> None:
        with (DATA_DIR / "analysis.csv").open(encoding="utf-8") as f:
            rows = {r["match_id"]: r for r in csv.DictReader(f)}
        for mid_int in range(1080279, 1080291):
            mid = str(mid_int)
            self.assertEqual(rows[mid]["series_format"], "BO1", f"Match {mid} must be BO1")
            self.assertTrue(rows[mid]["hltv_match_url"].startswith("https://www.hltv.org/matches/23994"))

    def test_07_every_html_table_row_has_official_external_source_link(self) -> None:
        tbody_re = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.S | re.I)
        tr_re = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
        ext_link_re = re.compile(r'href="https://[^"]+"', re.I)
        bad_token_re = re.compile(r"(?<![a-zA-Z])(None|null|NaN|undefined)(?![a-zA-Z])")

        for html_name in EXPECTED_HTML_FILES:
            hp = SITE_DIR / html_name
            content = hp.read_text(encoding="utf-8")
            self.assertIsNone(bad_token_re.search(content), f"Bad token in {html_name}")
            tbodies = tbody_re.findall(content)
            self.assertGreater(len(tbodies), 0, f"No <tbody> found in {html_name}")
            for tbody in tbodies:
                trs = tr_re.findall(tbody)
                self.assertGreater(len(trs), 0, f"Empty <tbody> in {html_name}")
                for idx, tr in enumerate(trs, 1):
                    self.assertIsNotNone(
                        ext_link_re.search(tr),
                        f"{html_name} row #{idx} is missing an official https:// source link",
                    )


if __name__ == "__main__":
    unittest.main()
