#!/usr/bin/env python3
"""Tests for the executive-summary board (session arena/3b5e3fea).

These run against the generated artefacts, so they fail if a rebuild publishes something the
rules below forbid. They deliberately do not need network access.

Run:  python3 -m unittest tests/test_3b5e3fea.py -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = importlib.util.spec_from_file_location("exec_build", os.path.join(ROOT, "scripts", "3b5e3fea_build.py"))
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

PICKS = os.path.join(ROOT, "exec", "data", "picks.json")
AUDIT = os.path.join(ROOT, "exec", "data", "coverage_audit.csv")
KNOWN_FLAGS = {"X-NO-BASIS", "X-MODEL-ONLY", "X-SECONDARY-PRICE", "X-FORMAT-UNVERIFIED", "X-IDENTICAL-ODDS"}
ALLOWED_SOURCES = {"market-direct", "market-secondary", "market-other", "model", "none"}
HOTSPAWN_PLACEHOLDER = ("play.hotspawn.com/cs2-pickems", "play.hotspawn.com/lobby")


def load_picks():
    with open(PICKS, encoding="utf-8") as fh:
        return json.load(fh)


class TestArithmetic(unittest.TestCase):
    def test_devig_known_values(self):
        # Pinnacle 9z v Aurora, American 241 / -307 -> decimal 3.41 / 1.326 (board row 1080176)
        p_a, p_b, over = build.de_vig(3.41, 1.326)
        self.assertAlmostEqual(p_a, 27.9983, places=3)
        self.assertAlmostEqual(p_b, 72.0017, places=3)
        self.assertAlmostEqual(over, 4.7403, places=3)
        self.assertAlmostEqual(p_a + p_b, 100.0, places=6)

    def test_devig_rejects_nonsense(self):
        for a, b in ((None, 2.0), (1.0, 2.0), (0.0, 2.0), ("", "")):
            self.assertEqual(build.de_vig(a, b), (None, None, None))

    def test_devig_is_symmetric(self):
        p_a, p_b, _ = build.de_vig(1.881, 1.782)
        self.assertAlmostEqual(p_a + p_b, 100.0, places=6)
        self.assertLess(p_a, p_b)  # the shorter price is the stronger side


class TestPrecedence(unittest.TestCase):
    """Direct book price beats an aggregator report; a market beats a model; nothing -> blank."""

    def fixture(self):
        return {"fixture_id": "T1", "team_a": "A", "team_b": "B", "start_utc": "2026-10-14T08:00:00Z",
                "lock_utc": "2026-10-14T07:54:00Z", "competition": "Test Cup", "tier": "c",
                "hotspawn_match_url": ""}

    def test_direct_beats_secondary(self):
        cands = [
            {"board": "oct14", "market_book": "bc.game (EGamersWorld)", "market_p_a": 60.0, "market_p_b": 40.0,
             "market_captured_utc": "2026-10-14T02:00:00Z", "captured_utc": "", "best_of": "", "market_url": "https://example.com/x"},
            {"board": "slate", "market_book": "Pinnacle", "market_p_a": 55.0, "market_p_b": 45.0,
             "market_captured_utc": "2026-10-14T01:00:00Z", "captured_utc": "", "best_of": "", "market_url": "https://example.com/y"},
        ]
        row = build.select_line(self.fixture(), cands)
        self.assertEqual(row["line_source"], "market-direct")
        self.assertEqual(row["market_book"], "Pinnacle")
        self.assertEqual(row["pick"], "A")

    def test_market_beats_model(self):
        cands = [
            {"board": "slate", "market_book": "Pinnacle", "market_p_a": 40.0, "market_p_b": 60.0,
             "market_captured_utc": "2026-10-14T01:00:00Z", "captured_utc": "", "best_of": "", "market_url": "https://example.com/y"},
            {"board": "oct14", "market_book": "", "own_p_a": 90.0, "own_p_b": 10.0, "own_basis": "VRS",
             "captured_utc": "2026-10-14T02:00:00Z", "best_of": ""},
        ]
        row = build.select_line(self.fixture(), cands)
        self.assertEqual(row["line_source"], "market-direct")
        self.assertEqual(row["pick"], "B")
        self.assertEqual(row["own_p_a"], 90.0)          # the model is still published, not discarded
        self.assertTrue(row["disagreements"])           # and the disagreement is flagged

    def test_no_basis_is_blank_and_flagged(self):
        row = build.select_line(self.fixture(), [])
        self.assertEqual(row["line_source"], "none")
        self.assertEqual(row["pick"], "")
        self.assertIsNone(row["p_a"])
        self.assertIn("X-NO-BASIS", [f["code"] for f in row["flags"]])

    def test_model_only_row_is_labelled(self):
        cands = [{"board": "oct14", "market_book": "", "own_p_a": 61.0, "own_p_b": 39.0, "own_basis": "VRS",
                  "own_url": "https://github.com/ValveSoftware/counter-strike_regional_standings",
                  "captured_utc": "2026-10-14T02:00:00Z", "best_of": "BO1"}]
        row = build.select_line(self.fixture(), cands)
        self.assertEqual(row["line_source"], "model")
        self.assertEqual(row["pick"], "A")
        self.assertIn("X-MODEL-ONLY", [f["code"] for f in row["flags"]])


class TestPublishedData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = load_picks()

    def test_every_open_fixture_has_identity(self):
        for row in self.payload["open"]:
            with self.subTest(fixture=row["fixture_id"]):
                self.assertTrue(row["fixture_id"])
                self.assertTrue(row["team_a"] and row["team_b"])
                self.assertRegex(row["kickoff_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
                self.assertRegex(row["lock_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_line_source_vocabulary(self):
        for row in self.payload["open"]:
            self.assertIn(row["line_source"], ALLOWED_SOURCES)

    def test_pick_always_has_a_basis_and_a_source_link(self):
        for row in self.payload["open"]:
            if not row["pick"]:
                continue
            with self.subTest(fixture=row["fixture_id"]):
                self.assertTrue(row["pick_basis"], "a pick without a stated basis must not be published")
                self.assertTrue(row["pick_source_url"].startswith("https://"),
                                "a published pick must carry the link it came from")
                self.assertIn(row["pick"], (row["team_a"], row["team_b"]))

    def test_probabilities_are_percentages_that_sum(self):
        for row in self.payload["open"]:
            if row["p_a"] is None:
                self.assertIsNone(row["p_b"])
                continue
            with self.subTest(fixture=row["fixture_id"]):
                self.assertGreaterEqual(row["p_a"], 0.0)
                self.assertLessEqual(row["p_a"], 100.0)
                self.assertAlmostEqual(row["p_a"] + row["p_b"], 100.0, places=1)

    def test_pick_is_the_higher_probability(self):
        for row in self.payload["open"]:
            if not row["pick"]:
                continue
            with self.subTest(fixture=row["fixture_id"]):
                self.assertEqual(row["pick_pct"], max(row["p_a"], row["p_b"]))

    def test_flag_codes_are_known(self):
        for row in self.payload["open"]:
            for flag in row["flags"]:
                self.assertIn(flag["code"], KNOWN_FLAGS)
                self.assertTrue(flag["text"])

    def test_hotspawn_crowd_percentage_is_never_published(self):
        blob = json.dumps(self.payload)
        self.assertNotIn("crowd_pct", blob)
        self.assertNotIn("% picked", blob)
        # Hotspawn appears only as fixture identity / match links
        for row in self.payload["open"]:
            for key, value in row.items():
                if isinstance(value, str) and "hotspawn.com" in value:
                    self.assertTrue(any(value.startswith("https://" + p) for p in HOTSPAWN_PLACEHOLDER)
                                    or value.startswith("https://www.hotspawn.com/matches/")
                                    or value.startswith("https://play.hotspawn.com/"),
                                    f"unexpected Hotspawn value in {key}: {value}")

    def test_inventory_counts_are_consistent(self):
        inv = self.payload["totals"]["inventory"]
        self.assertEqual(inv["payload_rows"], inv["open"] + inv["locked_or_started"])
        self.assertLessEqual(inv["stale_over_a_day"], inv["locked_or_started"])
        self.assertEqual(self.payload["totals"]["open_fixtures"], inv["open"])

    def test_coverage_audit_has_one_row_per_open_fixture(self):
        with open(AUDIT, encoding="utf-8") as fh:
            lines = [l for l in fh.read().splitlines() if l.strip()]
        self.assertEqual(len(lines) - 1, self.payload["totals"]["open_fixtures"])


class TestRenderedPages(unittest.TestCase):
    def test_pages_exist_with_viewport_and_title(self):
        for name in ("index.html", "coverage.html", "sources.html", "methodology.html", "flagged.html"):
            path = os.path.join(ROOT, "exec", name)
            self.assertTrue(os.path.exists(path), name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('name="viewport"', text, name)
            self.assertIn("<title>", text, name)
            self.assertIn('href="style.css"', text, name)

    def test_local_links_resolve(self):
        broken = []
        for name in os.listdir(os.path.join(ROOT, "exec")):
            if not name.endswith(".html"):
                continue
            base = os.path.join(ROOT, "exec")
            with open(os.path.join(base, name), encoding="utf-8") as fh:
                text = fh.read()
            for match in re.finditer(r'(?:href|src)="([^"]+)"', text):
                target = match.group(1)
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                resolved = os.path.normpath(os.path.join(base, target.split("#")[0]))
                if not os.path.exists(resolved):
                    broken.append((name, target))
        self.assertEqual(broken, [], f"broken local links: {broken}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
