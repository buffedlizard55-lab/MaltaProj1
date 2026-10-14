#!/usr/bin/env python3
"""tests/test_63ee81ba.py — verification suite for the full-coverage picks board.

Run:  python3 -m unittest tests/test_63ee81ba.py -v
"""
import csv
import hashlib
import importlib.util
import json
import math
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "63ee81ba"
SITE = ROOT / "picks-full"

spec = importlib.util.spec_from_file_location("b63ee81ba", ROOT / "scripts" / "63ee81ba_build.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


def read_csv(name):
    with (DATA / name).open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


class TestBuildScript(unittest.TestCase):
    def test_pin_checks_pass(self):
        self.assertEqual(B.verify_pins(), [])

    def test_vrs_file_hash_pinned(self):
        f = B.DATA_DIR / "vrs_2026_10_05.md"
        self.assertTrue(f.exists(), "pinned VRS file missing from data/63ee81ba/")
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        self.assertEqual(h, B.VRS_SHA256)

    def test_calibration_k_matches_repo(self):
        cal = json.loads((B.ROOT / "model" / "input" / "vrs" / "calibration.json").read_text())
        self.assertTrue(cal.get("adopted"))
        self.assertAlmostEqual(float(cal["k_published"]), B.K, places=6)


class TestDatasets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixtures = read_csv("fixtures.csv")
        cls.teams = read_csv("teams.csv")
        cls.market = read_csv("market_lines.csv")
        cls.own = read_csv("own_lines.csv")
        cls.picks = read_csv("picks.csv")
        cls.flags = read_csv("flags.csv")
        cls.cov = json.loads((DATA / "coverage.json").read_text())

    def test_28_open_fixtures(self):
        self.assertEqual(len(self.fixtures), 28)
        self.assertEqual(len(self.picks), 28)
        self.assertEqual(len(self.market), 28)
        self.assertEqual(len(self.own), 28)

    def test_every_row_has_source_links(self):
        url_re = re.compile(r"^https?://[^\s]+")
        for r in self.fixtures:
            self.assertTrue(url_re.match(r["hltv_match_url"]), r["match_id"])
            self.assertTrue(url_re.match(r["hotspawn_match_url"]) or url_re.match(r["hotspawn_lobby_url"]), r["match_id"])
        for r in self.market:
            self.assertTrue(url_re.match(r["source_url"]), r["match_id"])
        for r in self.teams:
            self.assertTrue(url_re.match(r["vrs_url"]), r["team"])
        for r in self.flags:
            self.assertTrue(url_re.match(r["source_urls"].split(" | ")[0]), r["flag_id"])

    def test_lock_is_start_minus_360s(self):
        for r in self.fixtures:
            from datetime import datetime, timedelta
            s = datetime.strptime(r["start_utc"], "%Y-%m-%dT%H:%M:%SZ")
            l = datetime.strptime(r["lock_utc"], "%Y-%m-%dT%H:%M:%SZ")
            self.assertEqual((l - s).total_seconds(), -360, r["match_id"])

    def test_series_formats(self):
        fmts = {r["match_id"]: r["series_format"] for r in self.fixtures}
        for mid in ("1080279", "1080280", "1080281", "1080282", "1080283", "1080284",
                    "1080285", "1080286", "1080287", "1080288", "1080289", "1080290"):
            self.assertEqual(fmts[mid], "BO1", mid)
        for mid, v in fmts.items():
            if mid not in {"1080279", "1080280", "1080281", "1080282", "1080283", "1080284",
                           "1080285", "1080286", "1080287", "1080288", "1080289", "1080290"}:
                self.assertEqual(v, "BO3", mid)

    def test_no_crowd_fields_anywhere(self):
        for name in ("fixtures.csv", "picks.csv", "market_lines.csv", "own_lines.csv", "teams.csv"):
            text = (DATA / name).read_text(encoding="utf-8")
            low = text.lower()
            for banned in ("crowd", "picked_percent", "total_picks"):
                self.assertNotIn(banned, low, f"{name} contains crowd field {banned}")

    def test_market_devig_math(self):
        for r in self.market:
            if not r["odds_a"]:
                self.assertEqual(r["devig_p_a_pct"], "")
                self.assertEqual(r["overround_pct"], "")
                continue
            ia, ib = 1.0 / float(r["odds_a"]), 1.0 / float(r["odds_b"])
            pa = ia / (ia + ib) * 100.0
            self.assertAlmostEqual(float(r["devig_p_a_pct"]), pa, delta=0.11, msg=r["match_id"])
            self.assertAlmostEqual(float(r["devig_p_b_pct"]), 100.0 - pa, delta=0.11, msg=r["match_id"])
            self.assertAlmostEqual(float(r["overround_pct"]), (ia + ib - 1.0) * 100.0, delta=0.11)

    def test_own_line_math(self):
        for r in self.own:
            if not r["own_p_a_pct"]:
                continue
            a = float(r["points_a_effective"])
            b = float(r["points_b_effective"])
            p = B.p_map(a, b)
            s = B.p_series(p, r["series_format"])
            self.assertAlmostEqual(float(r["own_p_a_pct"]), s * 100.0, delta=0.11, msg=r["match_id"])
            self.assertAlmostEqual(float(r["map_p_a"]), p, places=4, msg=r["match_id"])

    def test_own_line_requires_both_ratings_or_research(self):
        for r in self.own:
            if r["own_p_a_pct"]:
                if r["research"] == "yes":
                    continue
                self.assertTrue(r["vrs_points_a"] and r["vrs_points_b"],
                                f"{r['match_id']}: own line without both VRS ratings")
            else:
                self.assertTrue(r["research"] == "no" or r["match_id"] == "1079624")

    def test_24_priced_4_placeholder(self):
        priced = [r for r in self.market if r["odds_a"]]
        unpriced = [r for r in self.market if not r["odds_a"]]
        self.assertEqual(len(priced), 24)
        self.assertEqual(len(unpriced), 4)
        for r in unpriced:
            self.assertIn("PF-01", r["flags"], r["match_id"])

    def test_every_fixture_has_pick(self):
        for r in self.picks:
            self.assertTrue(r["pick"], f"{r['match_id']} has no pick")
            self.assertTrue(r["pick"] in (r["team_a"], r["team_b"]), r["match_id"])
            self.assertAlmostEqual(float(r["pick_prob_pct"]),
                                   max(float(r["published_p_a_pct"]), float(r["published_p_b_pct"])),
                                   delta=0.11, msg=r["match_id"])

    def test_published_pairs_sum_100(self):
        for r in self.picks:
            self.assertAlmostEqual(float(r["published_p_a_pct"]) + float(r["published_p_b_pct"]), 100.0, delta=0.1)

    def test_research_line_labelled(self):
        by_id = {r["match_id"]: r for r in self.own}
        r = by_id["1079624"]
        self.assertEqual(r["research"], "yes")
        self.assertIn("RESEARCH", r["method"])
        self.assertIn("PF-02", r["flags"])
        self.assertNotIn("1100", r["vrs_points_b"], "LFO 10 official points must stay blank")
        self.assertEqual(r["points_b_effective"], "813")

    def test_flags_register(self):
        ids = {r["flag_id"] for r in self.flags}
        for need in ("PF-01", "PF-02", "PF-03", "PF-04", "PF-05", "PF-06", "PF-07", "PF-08", "PF-09"):
            self.assertIn(need, ids)

    def test_coverage_counts(self):
        c = self.cov["counts"]
        self.assertEqual(c["open_fixtures"], 28)
        self.assertEqual(c["with_pick"], 28)
        self.assertEqual(c["with_external_market_line"], 24)
        self.assertEqual(c["with_research_line"], 1)
        self.assertFalse(self.cov["hotspawn_crowd_data_used"])


class TestSite(unittest.TestCase):
    PAGES = ["index.html", "s-tier.html", "b-tier.html", "c-tier.html", "tournaments.html",
             "market-lines.html", "own-lines.html", "sources.html", "methodology.html", "flagged.html"]

    def test_all_pages_exist(self):
        for p in self.PAGES:
            self.assertTrue((SITE / p).is_file(), p)

    def test_viewport_and_nav_on_every_page(self):
        for p in self.PAGES:
            html = (SITE / p).read_text(encoding="utf-8")
            self.assertIn('name="viewport"', html, p)
            for nav in self.PAGES:
                self.assertIn(f'href="{nav}"', html, f"{p} missing nav link {nav}")

    def test_index_lists_all_28_cards(self):
        html = (SITE / "index.html").read_text(encoding="utf-8")
        for mid in [r["match_id"] for r in read_csv("picks.csv")]:
            self.assertIn(f'id="f-{mid}"', html, f"missing card for {mid}")

    def test_flagged_anchors_match_cards(self):
        flg = (SITE / "flagged.html").read_text(encoding="utf-8")
        for p in self.PAGES:
            html = (SITE / p).read_text(encoding="utf-8")
            for m in set(re.findall(r'flagged\.html#([a-z0-9-]+)', html)):
                self.assertIn(f'id="{m}"', flg, f"{p} -> flagged.html#{m} missing anchor")

    def test_no_crowd_wording_as_probability(self):
        for p in self.PAGES:
            html = (SITE / p).read_text(encoding="utf-8").lower()
            for banned in ("crowd pick percentage is used", "crowd % ="):
                self.assertNotIn(banned, html, p)


if __name__ == "__main__":
    unittest.main(verbosity=2)
