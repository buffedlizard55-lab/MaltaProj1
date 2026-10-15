"""Acceptance checks for the valuepicks board (session arena/7759beef).

These tests recompute every published number from stored inputs. They fail the build if a page
disagrees with its data, if a pick is missing for an open fixture, if a market probability does not
de-vig from the stored odds, if an own line does not recompute from the stored rating inputs, or if a
row has no source link. Hotspawn's crowd percentage must never appear as a probability input.
"""
import csv
import html as html_module
import importlib.util
import json
import re
import unittest
from pathlib import Path

escape = html_module.escape

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "valuepicks"
DATA = OUT / "data"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


BUILD = _load("vp_build", ROOT / "scripts" / "7759beef_build.py")


class ValuePicksBoardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.board = json.loads((DATA / "board.json").read_text(encoding="utf-8"))
        cls.sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
        cls.meta = cls.board["meta"]
        cls.rows = cls.board["rows"]
        cls.exec_rows = list(csv.DictReader((ROOT / "executive" / "data" / "analysis.csv").open(encoding="utf-8")))
        cls.pages = {
            name: (OUT / name).read_text(encoding="utf-8")
            for name in ("index.html", "value.html", "unresolved.html", "coverage.html",
                         "sources.html", "flagged.html", "methodology.html")
        }

    # ------------------------------------------------------------------ coverage
    def test_every_open_executive_fixture_has_a_pick_and_two_probabilities(self):
        open_exec = {row["match_id"]: row for row in self.exec_rows if row["status"] == "open"}
        picked = {row["match_id"]: row for row in self.rows if row["status"] == "open"}
        self.assertEqual(set(open_exec), set(picked), "board must cover exactly the open fixtures")
        for match_id, row in picked.items():
            if row.get("no_sourced_basis"):
                # Allowed only as an explicit, published gap: the row must say why and be listed on
                # the unresolved page instead of inventing a side.
                with self.subTest(match_id=match_id):
                    self.assertTrue(row["flags"], "an unpicked row must carry its reason")
                    self.assertIn(f'id="u{match_id}"', self.pages["unresolved.html"])
                continue
            with self.subTest(match_id=match_id):
                self.assertTrue(row["pick"].strip(), f"{match_id} has no pick")
                self.assertIn(row["pick"], (row["team_a"], row["team_b"]))
                self.assertIsNotNone(row["prob_a_pct"])
                self.assertIsNotNone(row["prob_b_pct"])
                self.assertAlmostEqual(row["prob_a_pct"] + row["prob_b_pct"], 100.0, delta=0.3)
                self.assertEqual(row["pick"],
                                 row["team_a"] if row["prob_a_pct"] >= row["prob_b_pct"] else row["team_b"])

    def test_coverage_page_lists_every_captured_fixture(self):
        with (DATA / "coverage.csv").open(encoding="utf-8") as handle:
            coverage = list(csv.DictReader(handle))
        self.assertEqual(len(coverage), len(self.exec_rows))
        self.assertEqual(self.meta["total_fixtures"], len(coverage))
        html = self.pages["coverage.html"]
        self.assertEqual(html.count('data-label="Match"'), len(coverage))
        for row in coverage:
            self.assertIn(escape(row["team_a"]), html)
            self.assertIn(escape(row["team_b"]), html)

    # ------------------------------------------------------------------ maths
    def test_market_probabilities_recompute_from_stored_odds(self):
        checked = 0
        for row in self.rows:
            if not row.get("resolution_used"):
                continue
            res = next(r for r in self.sources["resolutions"] if r["match_id"] == row["match_id"])
            market = res["market"]
            with self.subTest(match_id=row["match_id"]):
                self.assertEqual((market["prob_a_pct"], market["prob_b_pct"]),
                                 BUILD.devig(market["odds_a"], market["odds_b"]))
                self.assertEqual((row["prob_a_pct"], row["prob_b_pct"]),
                                 (market["prob_a_pct"], market["prob_b_pct"]))
            checked += 1
        # A hand-written resolution must either be published (checked above) or superseded by a
        # priced executive row - never silently dropped while the row stays unpicked.
        for res in self.sources["resolutions"]:
            row = next(r for r in self.rows if r["match_id"] == res["match_id"])
            if not row.get("resolution_used"):
                self.assertTrue(row["pick"], f"{res['match_id']}: resolution skipped without a pick")
        self.assertGreaterEqual(checked, 1, "expected at least one ladder-resolved row")

    def test_own_lines_recompute_from_official_rating_inputs(self):
        checked = 0
        for res in self.sources["resolutions"]:
            own = res["own"]
            expected = round(BUILD.own_line(own["vrs_a"], own["vrs_b"], own["best_of"]) * 100, 1)
            with self.subTest(match_id=res["match_id"]):
                self.assertAlmostEqual(expected, own["prob_a_pct"], delta=0.15)
                self.assertAlmostEqual(100 - expected, own["prob_b_pct"], delta=0.15)
            checked += 1
        self.assertGreaterEqual(checked, 5)

    def test_series_maths_matches_closed_forms(self):
        p = 0.6
        self.assertAlmostEqual(BUILD.OWN.series_probability(p, 1), p)
        self.assertAlmostEqual(BUILD.OWN.series_probability(p, 3), 3 * p ** 2 - 2 * p ** 3)
        self.assertAlmostEqual(BUILD.OWN.series_probability(p, 5),
                               10 * p ** 3 - 15 * p ** 4 + 6 * p ** 5)

    # ------------------------------------------------------------------ evidence
    def test_every_published_row_has_a_source_link(self):
        for row in self.rows:
            if row["status"] != "open":
                continue
            with self.subTest(match_id=row["match_id"]):
                self.assertTrue(row["source_urls"], f"{row['match_id']} has no source url")
                for url in row["source_urls"]:
                    self.assertTrue(url.startswith("http"), url)

    def test_flagged_page_shows_every_flag_code(self):
        flags = {flag.split()[0] for row in self.rows for flag in row["flags"]}
        html = self.pages["flagged.html"]
        for code in flags:
            self.assertIn(code, html)

    def test_unresolved_page_lists_every_non_tier_a_row(self):
        fallback = [row for row in self.rows
                    if row["status"] == "open" and not row["basis_tier"].startswith("A")]
        html = self.pages["unresolved.html"]
        self.assertEqual(len(fallback), self.meta["fallback_basis"])
        for row in fallback:
            self.assertIn(f'id="u{row["match_id"]}"', html)
        with (DATA / "unresolved.csv").open(encoding="utf-8") as handle:
            unresolved_csv = list(csv.DictReader(handle))
        self.assertEqual({row["match_id"] for row in unresolved_csv}, {row["match_id"] for row in fallback})

    def test_no_hotspawn_crowd_percentage_is_used_as_a_probability(self):
        for row in self.rows:
            evidence = json.dumps(row)
            self.assertNotIn("crowd", evidence.lower())
            if row["status"] == "open":
                self.assertTrue(row["basis_label"], row["match_id"])
                self.assertNotIn("Hotspawn", row["basis_label"])

    def test_source_facts_are_all_linked_and_tiered(self):
        valid_tiers = set(self.sources["tiers"])
        for fact in self.sources["facts"]:
            with self.subTest(fact=fact["id"]):
                self.assertTrue(fact["url"].startswith("http"))
                self.assertIn(fact["tier"], valid_tiers)
                self.assertRegex(fact["read_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    # ------------------------------------------------------------------ pages
    def test_index_page_leads_with_the_slate_and_links_the_subpages(self):
        html = self.pages["index.html"]
        self.assertIn('href="#slate"', html)
        for target in ("value.html", "unresolved.html", "coverage.html", "sources.html",
                       "methodology.html", "flagged.html", "../executive/picks.html"):
            self.assertIn(target, html)
        self.assertEqual(len(re.findall(r"<h1\b", html, re.I)), 1)

    def test_pages_have_no_local_broken_links(self):
        for name, html in self.pages.items():
            for href in re.findall(r'href="([^"#][^"]*)"', html):
                if href.startswith(("http://", "https://", "mailto:")):
                    continue
                target = (OUT / href.split("#")[0]).resolve()
                with self.subTest(page=name, href=href):
                    self.assertTrue(target.exists() or (OUT / href).exists(), f"{name} -> {href}")

    def test_index_cards_use_the_stored_numbers(self):
        html = self.pages["index.html"]
        for row in self.rows:
            if row["status"] != "open":
                continue
            with self.subTest(match_id=row["match_id"]):
                self.assertIn(f'id="m{row["match_id"]}"', html)
                self.assertIn(f"{row['prob_a_pct']:.1f}%", html)
                self.assertIn(f"{row['prob_b_pct']:.1f}%", html)


if __name__ == "__main__":
    unittest.main()
