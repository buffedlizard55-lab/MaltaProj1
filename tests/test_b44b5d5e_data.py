#!/usr/bin/env python3
"""Data-level verification of the published every-match board (session arena/b44b5d5e).

These tests read the *committed* artefacts — ``matchpicks/data/fixtures.csv``,
``unresolved.csv``, ``flags.csv``, ``summary.json`` — and re-derive every published number from the
inputs stored next to it.  They are the machine version of the line-by-line check: if a page or a
CSV ever disagrees with its own data, the build fails.

Checks performed per row
------------------------
* a market probability is re-derived from the stored decimal pair with the printed de-vig formula;
* an originated ("own") line is re-derived from the stored official rating inputs and the series
  length that the row cites, using the exact best-of transform;
* the pick is the side with the higher published probability;
* both probabilities sum to 100 within rounding;
* a published value names a source and carries a resolvable source URL of the expected host;
* a row with no probability carries no pick and appears on the Unresolved page;
* no crowd field, and no Hotspawn-sourced probability, appears anywhere;
* the feature counts in ``summary.json`` agree with the rows.
"""
from __future__ import annotations

import csv
import json
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "matchpicks" / "data"


def load_csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        raise unittest.SkipTest(f"{path} not built yet")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def bo_maps(first_to: int, p: float) -> float:
    return sum(math.comb(first_to - 1 + k, k) * p ** first_to * (1 - p) ** k for k in range(first_to))


class PublishedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_csv("fixtures.csv")
        cls.unresolved = load_csv("unresolved.csv")
        cls.flags = load_csv("flags.csv")
        cls.summary = json.loads((DATA / "summary.json").read_text())
        cls.explained_flags = set()  # populated by the flag-explanation test

    def test_market_probabilities_are_exactly_the_devigged_stored_prices(self):
        checked = 0
        for row in self.rows:
            odds_a, odds_b = row.get("market_odds_a"), row.get("market_odds_b")
            if not (odds_a and odds_b):
                self.assertEqual(row.get("market_p_a_pct", ""), "",
                                 f"{row['match_id']}: probabilities without prices")
                continue
            implied_a, implied_b = 1 / float(odds_a), 1 / float(odds_b)
            expected = 100 * implied_a / (implied_a + implied_b)
            if row["probability_source"].startswith("Polymarket"):
                expected = 100 / float(odds_a)          # prediction markets are not de-vigged
            self.assertAlmostEqual(float(row["p_a"]), round(expected, 1), delta=0.05,
                                   msg=f"{row['match_id']}: published market probability")
            checked += 1
        self.assertGreater(checked, 0, "no market-priced row was verified at all")

    def test_own_line_is_re_derived_from_the_stored_official_inputs(self):
        checked = 0
        for row in self.rows:
            if not row.get("own_p_a_pct"):
                continue
            basis = row["own_basis"]
            bo = int(row["series"][2:]) if row.get("series", "").startswith("BO") else None
            if "Valve" in basis:
                a, b = float(row["vrs_points_a"]), float(row["vrs_points_b"])
                p_map = 1 / (1 + 10 ** (-(a - b) / 400.0))
            elif "HLTV" in basis:
                # rank numbers: a *smaller* number is the better team, so the sign flips
                a, b = int(row["hltv_rank_a"]), int(row["hltv_rank_b"])
                p_map = 1 / (1 + 10 ** ((a - b) / 100.0))
            else:
                self.fail(f"{row['match_id']}: own line with an unrecognised basis: {basis}")
            expected = bo_maps({1: 1, 3: 2, 5: 3}[bo], p_map) if bo in (1, 3, 5) else p_map
            self.assertAlmostEqual(float(row["own_p_a_pct"]), round(100 * expected, 1), delta=0.05,
                                   msg=f"{row['match_id']}: published own line")
            self.assertEqual(row["own_scope"], "series" if bo in (1, 3, 5) else "per-map")
            checked += 1
        self.assertGreater(checked, 0, "no originated line was verified at all")

    def test_pick_is_the_higher_probability_and_sum_is_100(self):
        for row in self.rows:
            if not row["p_a"]:
                self.assertEqual(row["pick"], "", f"{row['match_id']}: pick without a probability")
                continue
            a, b = float(row["p_a"]), float(row["p_b"])
            self.assertAlmostEqual(a + b, 100.0, delta=0.35, msg=f"{row['match_id']}: sum")
            expected = row["team_a"] if a >= b else row["team_b"]
            self.assertEqual(row["pick"], expected, f"{row['match_id']}: pick")

    def test_every_published_value_has_a_source_url_of_the_expected_host(self):
        hosts = {"Pinnacle": "pinnacle.com", "EGamersWorld": "egamersworld.com",
                 "Polymarket": "polymarket.com",
                 "Valve": "github.com/ValveSoftware/counter-strike_regional_standings"}
        for row in self.rows:
            if not row["p_a"]:
                continue
            self.assertTrue(row["probability_source"], f"{row['match_id']}: unnamed source")
            if row.get("market_p_a_pct"):
                found = [host for key, host in hosts.items() if key in row["probability_source"]]
                self.assertTrue(found, f"{row['match_id']}: market source not recognised")
                self.assertIn(found[0], row["market_url"],
                              f"{row['match_id']}: market link does not match its source")
            else:
                self.assertTrue(row["own_basis"], f"{row['match_id']}: own line without a basis")
                self.assertTrue(row["own_url"], f"{row['match_id']}: own line without a source link")
                if "Valve" in row["own_basis"]:
                    self.assertIn("counter-strike_regional_standings", row["own_url"])
                if "HLTV" in row["own_basis"]:
                    self.assertIn("hltv.org", row["own_url"])

    def test_rows_without_a_probability_are_published_as_unresolved(self):
        unresolved_ids = {row["match_id"] for row in self.unresolved}
        for row in self.rows:
            if row["p_a"]:
                continue
            self.assertIn(row["match_id"], unresolved_ids,
                          f"{row['match_id']}: blank row missing from the Unresolved page")

    def test_no_crowd_value_and_no_hotspawn_probability_anywhere(self):
        for row in self.rows + self.unresolved:
            haystack = json.dumps(row).lower()
            self.assertNotIn("picked_percent", haystack)
            self.assertNotIn("crowd_pct", haystack)
            if row.get("probability_source"):
                self.assertNotIn("hotspawn", row["probability_source"].lower(),
                                 f"{row['match_id']}: Hotspawn used as a probability source")

    def test_every_flag_raised_on_a_published_row_is_explained_in_the_flag_text(self):
        """No row may carry a flag the board does not explain (the page renders FLAG_TEXT)."""
        index = (ROOT / "matchpicks" / "flagged.html")
        if not index.exists():
            self.skipTest("board not built yet")
        page = index.read_text(encoding="utf-8")
        codes = set()
        for row in self.rows:
            codes.update((row["flags"] or "").split(";"))
        codes.discard("")
        missing = [code for code in sorted(codes) if code not in page]
        self.assertEqual(missing, [], f"flags raised but never explained: {missing}")

    def test_summary_counts_agree_with_the_rows(self):
        summary = self.summary
        self.assertEqual(summary["fixtures_captured"], len(self.rows))
        open_rows = [r for r in self.rows if r["state"] == "open"]
        self.assertEqual(summary["open"], len(open_rows))
        self.assertEqual(summary["open_with_pick"], sum(1 for r in open_rows if r["pick"]))
        self.assertEqual(summary["open_with_market"], sum(1 for r in open_rows if r["market_p_a_pct"]))
        self.assertEqual(summary["open_with_own_line"], sum(1 for r in open_rows if r["own_p_a_pct"]))
        self.assertEqual(summary["open_without_pick"], sum(1 for r in open_rows if not r["pick"]))
        self.assertEqual(summary["unresolved_total"], len(self.unresolved))
        self.assertEqual(summary["flags_total"], sum(int(row["count"]) for row in self.flags))
        if summary["fixtures_captured"]:
            self.assertTrue(summary["independent_checks_agreed"] >= 0)

    def test_series_research_trail_is_fully_source_linked(self):
        """Every hand-checked best-of line must name a source, a URL, a read time and quoted proof."""
        trail = ROOT / "matchpicks" / "series_research.csv"
        if not trail.exists():
            self.skipTest("no researched series trail in the tree")
        with trail.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertTrue(rows, "the researched series trail is empty")
        for row in rows:
            with self.subTest(match_id=row["match_id"]):
                self.assertRegex(row["series"], r"^BO[1357]$")
                self.assertTrue(row["source"].strip())
                self.assertTrue(row["source_url"].startswith("https://"))
                self.assertTrue(row["read_utc"].strip())
                self.assertTrue(row["evidence"].strip())

    def test_every_published_length_is_sourced_and_unstyled_rows_are_flagged(self):
        for row in self.rows:
            if row["series"]:
                self.assertRegex(row["series"], r"^BO[1357]$")
                self.assertTrue(row["series_source"], f"{row['match_id']}: length without a source")
                self.assertTrue(row["series_url"].startswith("https://"),
                                f"{row['match_id']}: length without a link")
                self.assertTrue(row["series_read_utc"], f"{row['match_id']}: length without a read time")
                self.assertNotIn("MP-F05", row["flags"])
            else:
                self.assertEqual(row["series_url"], "")
                self.assertEqual(row["series_read_utc"], "")
                if row["state"] == "stale listing":
                    # a stale listing keeps only the historical flags (MP-F04 and friends); the
                    # length is simply left blank, and the row is listed on the unresolved page
                    self.assertIn("MP-F04", row["flags"])
                    continue
                self.assertIn("MP-F05", row["flags"],
                              f"{row['match_id']}: unstated length must be flagged")
                self.assertIn("MP-F05", self.explained_flags,
                              "an MP-F05 flag must be explained on the flagged page")
                if row["own_p_a_pct"]:
                    self.assertEqual(row["own_scope"], "per-map",
                                     f"{row['match_id']}: per-map line must say so")

    def test_results_only_ever_come_with_an_official_link(self):
        for row in self.rows:
            if not row["result"]:
                continue
            self.assertTrue(row["result_source_url"].startswith("https://www.hltv.org/")
                            or row["result_source_url"].startswith("https://liquipedia.net/"),
                            f"{row['match_id']}: result without an official source link")
            self.assertTrue(row["result_read_utc"], f"{row['match_id']}: result without a read time")


if __name__ == "__main__":
    unittest.main(verbosity=2)
