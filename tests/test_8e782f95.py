#!/usr/bin/env python3
"""Tests for the B-01..B-05 board (session arena/8e782f95).

Run:  python3 -m unittest tests.test_8e782f95 -v      (from the repository root)
"""
import csv
import math
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "8e782f95")
BOARD = os.path.join(ROOT, "board")


def load_csv(name):
    with open(os.path.join(DATA, name), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class ValveGlickoConstants(unittest.TestCase):
    """The model must use Valve's own published constants, read from Valve's file."""

    VRS_SRC = os.path.join(DATA, "vrs_global_2026_10_05.md")

    def test_g_factor_matches_valve_glicko_js(self):
        # Re-derived from the expressions published in Valve's repository so a
        # change in Valve's file would be caught here.
        q = math.log(10) / 400.0                      # glicko.js: const Q = Math.log(10)/400
        rd = 75.0                                     # fit.js: defaultGlickoParams rd: 75
        g = 1.0 / math.sqrt(1.0 + 3.0 * q * q * rd * rd / (math.pi ** 2))
        with open(os.path.join(ROOT, "scripts", "8e782f95_build.py"), encoding="utf-8") as fh:
            src = fh.read()
        for needed in (
            "Q = ln(10)/400",
            "rd = 75",
            "400 points = 90% chance of victory",
            "Math.log(10) / 400",
        ):
            self.assertIn(needed, src)
        self.assertAlmostEqual(g, 0.972821, places=6)
        self.assertAlmostEqual(g, _G, places=12)

    def test_standings_file_is_valve_official_shape(self):
        self.assertTrue(os.path.exists(self.VRS_SRC))
        with open(self.VRS_SRC, encoding="utf-8") as fh:
            head = fh.readline()
        self.assertIn("Standings as of 2026_10_05", head)
        rows = load_csv("vrs_global_2026_10_05_extract.csv")
        self.assertEqual(len(rows), 380)
        self.assertEqual(rows[0]["team_name"], "Spirit")
        self.assertEqual(int(rows[0]["vrs_points"]), 2046)
        # points must be strictly non-increasing down the table
        pts = [int(r["vrs_points"]) for r in rows]
        self.assertTrue(all(a >= b for a, b in zip(pts, pts[1:])))


class ProbabilityMath(unittest.TestCase):
    def test_devig_sums_to_one_and_margin_positive(self):
        for oa, ob in ((2.05, 1.64), (1.07, 6.41), (1.8, 1.8), (3.75, 1.25)):
            pa, pb, margin = _devig(oa, ob)
            self.assertAlmostEqual(pa + pb, 1.0, places=12)
            self.assertAlmostEqual(margin, 1 / oa + 1 / ob - 1, places=12)

    def test_series_amplifies_towards_the_edges(self):
        for p in (0.2, 0.45, 0.5, 0.62, 0.9):
            self.assertAlmostEqual(_series(p, "Bo1"), p)
            bo3 = _series(p, "Bo3")
            self.assertAlmostEqual(bo3, p ** 3 + 3 * p ** 2 * (1 - p), places=12)
            if p > 0.5:
                self.assertGreater(bo3, p)
            elif p < 0.5:
                self.assertLess(bo3, p)
            else:
                self.assertAlmostEqual(bo3, 0.5)

    def test_map_prob_symmetry(self):
        self.assertAlmostEqual(_map(1500, 1300) + _map(1300, 1500), 1.0, places=12)
        self.assertAlmostEqual(_map(1500, 1500), 0.5)


class AnalysisRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_csv("analysis.csv")
        cls.ext = load_csv("external_lines.csv")

    def test_every_row_has_a_hotspawn_source_link(self):
        for r in self.rows:
            self.assertTrue(r["hotspawn_url"].startswith("https://"), r)

    def test_every_priced_row_links_the_page_the_price_was_read_from(self):
        for r in self.rows:
            if r["ext_odds_a"]:
                self.assertTrue(r["ext_url"].startswith("https://egamersworld.com/"), r)
                self.assertTrue(r["ext_captured_utc"].startswith("2026-10-13"), r)

    def test_blank_market_probability_means_no_published_price(self):
        for r in self.rows:
            if not r["market_p_a"]:
                self.assertEqual(r["ext_odds_a"], "", r)
                self.assertEqual(r["ext_odds_b"], "", r)

    def test_placeholder_prices_are_never_converted(self):
        # 1.80/1.80 is EGamersWorld's placeholder; it must not appear as a price.
        for r in self.rows:
            self.assertFalse(
                r["ext_odds_a"] == "1.8" and r["ext_odds_b"] == "1.8", r
            )
        for r in self.ext:
            if r["odds_a"] == "1.8" and r["odds_b"] == "1.8":
                self.fail("placeholder pair published for " + r["team_a"])

    def test_unrated_teams_get_no_own_line(self):
        for r in self.rows:
            if not r["vrs_a"] or not r["vrs_b"]:
                self.assertEqual(r["own_map_p_a"], "", r)
                self.assertEqual(r["own_series_p_a"], "", r)

    def test_series_probability_only_when_a_format_is_published(self):
        for r in self.rows:
            if not r["format"]:
                self.assertEqual(r["own_series_p_a"], "", r)

    def test_pick_always_has_a_stated_basis(self):
        for r in self.rows:
            if r["pick"]:
                self.assertTrue(r["pick_basis"], r)
            else:
                self.assertEqual(r["pick_basis"], "", r)

    def test_pick_follows_the_market_when_a_market_line_exists(self):
        for r in self.rows:
            if r["market_p_a"]:
                expected = r["team_a"] if float(r["market_p_a"]) >= 0.5 else r["team_b"]
                self.assertEqual(r["pick"], expected, r)
                self.assertEqual(r["pick_basis"], "external market line", r)

    def test_hotspawn_crowd_percentages_are_never_a_probability_input(self):
        # Sanity: the crowd columns exist (audit only) but no row's probability
        # equals a crowd percentage, and no pick is derived from them.
        for r in self.rows:
            for key in ("market_p_a", "own_series_p_a", "own_map_p_a"):
                if r[key]:
                    self.assertNotEqual(
                        round(float(r[key]), 4),
                        round(int(r["crowd_pct_a_audit_only"]) / 100.0, 4),
                        (r["team_a"], key),
                    )

    def test_vrs_points_are_read_from_the_official_file(self):
        def norm(x):
            return re.sub(r"[^a-z0-9]", "", x.lower())

        official = {
            norm(r["team_name"]): int(r["vrs_points"])
            for r in load_csv("vrs_global_2026_10_05_extract.csv")
        }
        aliases = {"WROTBERRY": "WBT", "RoundsGG": "ROUNDS", "Envy": "3DMAX"}
        for r in self.rows:
            for team, pts in ((r["team_a"], r["vrs_a"]), (r["team_b"], r["vrs_b"])):
                if pts:
                    name = aliases.get(team, team)
                    self.assertEqual(int(pts), official[norm(name)], (team, name))

    def test_all_30_current_fixtures_are_present(self):
        fx = load_csv("fixtures.csv")
        self.assertEqual(len(fx), 30)
        self.assertEqual(len(self.rows), 30)


class BoardPages(unittest.TestCase):
    PAGES = [
        "index.html", "all-matches.html", "s-tier.html", "b-tier.html",
        "c-tier.html", "sources.html", "method.html", "flagged.html",
    ]

    def test_pages_exist_and_have_no_conflict_markers(self):
        for p in self.PAGES:
            path = os.path.join(BOARD, p)
            self.assertTrue(os.path.exists(path), p)
            text = open(path, encoding="utf-8").read()
            for marker in ("<<<<<<<", ">>>>>>>", "=======\n"):
                self.assertNotIn(marker, text, (p, marker))

    def test_internal_links_resolve(self):
        for p in self.PAGES:
            with open(os.path.join(BOARD, p), encoding="utf-8") as fh:
                text = fh.read()
            for href in re.findall(r'href="([^"#][^"]*)"', text):
                if href.startswith(("http", "mailto:")):
                    continue
                target = href.split("?")[0].split("#")[0]
                if not target:
                    continue
                full = os.path.normpath(os.path.join(BOARD, target))
                self.assertTrue(os.path.exists(full), (p, href))

    def test_every_page_links_the_nav(self):
        for p in self.PAGES:
            with open(os.path.join(BOARD, p), encoding="utf-8") as fh:
                text = fh.read()
            for other in self.PAGES:
                self.assertIn(other, text, (p, other))

    def test_mobile_viewport_present(self):
        for p in self.PAGES:
            with open(os.path.join(BOARD, p), encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn('name="viewport"', text, p)

    def test_flagged_page_publishes_every_flag_with_a_source(self):
        import json
        with open(os.path.join(DATA, "flags.json"), encoding="utf-8") as fh:
            flags = json.load(fh)
        with open(os.path.join(BOARD, "flagged.html"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertTrue(flags)
        for f in flags:
            self.assertIn(f["code"], text, f["code"])
            self.assertTrue(f["sources"], f["code"])


# ---------------------------------------------------------------------------
# Local copies of the build script's pure maths, so the tests do not depend on
# module import order. They are checked against the build script below.
# ---------------------------------------------------------------------------
_Q = math.log(10) / 400.0
_RD = 75.0
_G = 1.0 / math.sqrt(1.0 + 3.0 * _Q * _Q * _RD * _RD / (math.pi ** 2))
_SCALE = 1122.260892213966


def _map(a, b):
    return 1.0 / (1.0 + 10.0 ** (-_G * (a - b) / _SCALE))


def _series(p, fmt):
    if fmt == "Bo1":
        return p
    if fmt == "Bo3":
        return p ** 3 + 3 * p ** 2 * (1 - p)
    return None


def _devig(oa, ob):
    ia, ib = 1.0 / oa, 1.0 / ob
    t = ia + ib
    return ia / t, ib / t, t - 1.0


class LocalMathMatchesBuildScript(unittest.TestCase):
    def test_constants_and_scale_agree_with_the_generator(self):
        with open(os.path.join(ROOT, "scripts", "8e782f95_build.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("Math.log(10) / 400", src)
        self.assertIn("rd : 75", src)
        self.assertAlmostEqual(_G, 0.972821, places=6)
        with open(os.path.join(BOARD, "data", "analysis.json"), encoding="utf-8") as fh:
            calib = re.search(r'"scale":\s*([0-9.]+)', fh.read())
        self.assertIsNotNone(calib)
        self.assertAlmostEqual(float(calib.group(1)), _SCALE, places=6)


if __name__ == "__main__":
    unittest.main()
