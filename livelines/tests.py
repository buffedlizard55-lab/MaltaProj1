#!/usr/bin/env python3
"""Invariants for the livelines board.

These fail the build rather than let an unverifiable number reach the site:
  * every open fixture has either a pick with both sides summing to 100, or is published as a bound
    on unresolved.html with no pick;
  * every row that publishes a market probability names the source URL and the read time;
  * no Hotspawn crowd value is stored anywhere on this board;
  * every row carries at least one source link;
  * the de-vig arithmetic re-derives from the printed prices;
  * the built HTML has no broken internal link and no '#' placeholder href;
  * rebuilding with a pinned clock reproduces picks.csv byte for byte.
"""
from __future__ import annotations

import csv
import filecmp
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "livelines"
DATA = OUT / "data"
PAGES = ["index.html", "picks.html", "unresolved.html", "flagged.html", "methodology.html",
         "sources.html", "cadence.html"]
PINNED = "2026-10-14T04:45:00Z"


def load_picks():
    with (DATA / "picks.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestLivelines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_picks()
        cls.open_rows = [r for r in cls.rows if r["state"] == "open"]
        cls.coverage = json.loads((DATA / "coverage.json").read_text())
        cls.calib = json.loads((DATA / "calibration.json").read_text())
        cls.picks_json = json.loads((DATA / "picks.json").read_text())

    def test_every_open_fixture_is_decided_or_published_as_unresolved(self):
        for r in self.open_rows:
            if r["pick"]:
                self.assertIn(r["basis"], ("T1", "T2", "T3"), r["match_id"])
                self.assertTrue(r["pick"] in (r["team_a"], r["team_b"]), r["match_id"])
            else:
                self.assertEqual(r["basis"], "T4", r["match_id"])
                self.assertIn("FL-NO-OUTSIDE-LINE", r["flags"], r["match_id"])

    def test_probabilities_sum_to_100(self):
        for r in self.open_rows:
            if r["prob_a_pct"] and r["prob_b_pct"]:
                total = float(r["prob_a_pct"]) + float(r["prob_b_pct"])
                self.assertAlmostEqual(total, 100.0, delta=0.25, msg=r["match_id"])

    def test_market_rows_name_their_source_and_time(self):
        for r in self.open_rows:
            if r["basis"] in ("T1", "T2"):
                self.assertTrue(r["market_source"], r["match_id"])
                self.assertTrue(r["market_url"].startswith("http"), r["match_id"])
                self.assertRegex(r["market_captured_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", r["match_id"])

    def test_devig_rederives_from_printed_prices(self):
        for r in self.open_rows:
            if r["basis"] not in ("T1", "T2"):
                continue
            a, b = float(r["market_odds_a"]), float(r["market_odds_b"])
            if "share price" in r["market_kind"]:
                pa, pb = a / (a + b) * 100.0, b / (a + b) * 100.0
            else:
                pa, pb = 1 / a, 1 / b
                s = pa + pb
                pa, pb = pa / s * 100.0, pb / s * 100.0
            self.assertAlmostEqual(pa, float(r["prob_a_pct"]), delta=0.15, msg=r["match_id"])
            self.assertAlmostEqual(pb, float(r["prob_b_pct"]), delta=0.15, msg=r["match_id"])

    def test_pick_is_the_higher_probability_side(self):
        for r in self.open_rows:
            if not r["pick"]:
                continue
            pa, pb = float(r["prob_a_pct"]), float(r["prob_b_pct"])
            expected = r["team_a"] if pa >= pb else r["team_b"]
            self.assertEqual(r["pick"], expected, r["match_id"])

    def test_no_hotspawn_crowd_value_is_stored(self):
        # no stored fixture/pick object may carry a crowd field of any spelling
        data = json.loads((DATA / "picks.json").read_text())
        for row in data["rows"]:
            for key in row:
                self.assertNotIn("crowd", key.lower(), row["match_id"])
                self.assertNotIn("picked", key.lower(), row["match_id"])
        for entry in data["placeholders_rejected"] + data["live_reads"]:
            for key in entry:
                self.assertNotIn("picked", str(key).lower())
        live = json.loads((DATA / "live_reads.json").read_text())
        lobby = [r for r in live["reads"] if r["id"] == "HS-LOBBY"][0]
        self.assertTrue(lobby["observed"]["crowd_percentages_present_on_page"])
        self.assertFalse(lobby["observed"]["crowd_percentages_stored_here"])

    def test_every_row_has_a_source_link(self):
        for r in self.rows:
            self.assertRegex(r["source_links"], r"https?://", r["match_id"])

    def test_bound_rows_are_labelled_as_bounds(self):
        for r in self.rows:
            if r["basis"] == "T4":
                self.assertIn("Bound", r["basis_label"])
                self.assertIn("lower bound", r["basis_label"].lower() + " " + r["notes"].lower(), r["match_id"])

    def test_calibration_is_reported_with_both_objectives(self):
        c = self.calib["calibration"]
        self.assertTrue(c["fitted"])
        self.assertGreater(c["n"], 3)
        self.assertTrue(20.0 <= c["scale"] <= 2000.0)
        self.assertIsNotNone(c["mae_pp"])
        self.assertIn("logloss_alternative", c)
        self.assertIn("candidate_transforms", c)
        for name, cand in c["candidate_transforms"].items():
            self.assertIn("n", cand, name)

    def test_coverage_counts_match_the_rows(self):
        c = self.coverage
        self.assertEqual(c["open_fixtures"], len(self.open_rows))
        self.assertEqual(c["open_with_pick"], len([r for r in self.open_rows if r["pick"]]))
        self.assertEqual(c["open_own_line_basis"], len([r for r in self.open_rows if r["basis"] == "T3"]))
        self.assertEqual(c["open_bound_only"], len([r for r in self.open_rows if r["basis"] == "T4"]))
        self.assertEqual(c["open_market_basis"], len([r for r in self.open_rows if r["basis"] in ("T1", "T2")]))

    def test_pages_have_no_broken_internal_link_and_are_mobile_ready(self):
        for name in PAGES:
            p = OUT / name
            self.assertTrue(p.exists(), name)
            html = p.read_text()
            self.assertIn('name="viewport"', html, name)
            self.assertNotRegex(html, r'href="#"', name)
            for m in re.finditer(r'href="([^"]+)"', html):
                u = m.group(1)
                if u.startswith(("http", "#", "mailto")):
                    continue
                self.assertTrue((p.parent / u.split("#")[0]).resolve().exists(), f"{name} -> {u}")

    def test_rebuild_is_deterministic_with_a_pinned_clock(self):
        with tempfile.TemporaryDirectory() as td:
            fixed = pathlib.Path(td) / "picks.csv"
            fixed.write_bytes((DATA / "picks.csv").read_bytes())
            env = dict(os.environ, LIVELINES_NOW=PINNED)
            subprocess.run([sys.executable, str(OUT / "build.py")], cwd=ROOT, env=env,
                           check=True, stdout=subprocess.DEVNULL)
            same = filecmp.cmp(fixed, DATA / "picks.csv", shallow=False)
            # restore the real-clock build so the published board is not left on a pinned clock
            subprocess.run([sys.executable, str(OUT / "build.py")], cwd=ROOT, check=True,
                           stdout=subprocess.DEVNULL)
        self.assertTrue(same, "rebuild with a pinned clock changed picks.csv")

    def test_no_placeholder_prices_in_published_rows(self):
        for r in self.open_rows:
            if r["basis"] in ("T1", "T2"):
                a, b = float(r["market_odds_a"]), float(r["market_odds_b"])
                self.assertFalse(abs(a - 1.8) < 1e-9 and abs(b - 1.8) < 1e-9, r["match_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
