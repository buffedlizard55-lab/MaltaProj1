#!/usr/bin/env python3
"""Tests for the executive-summary board (session arena/bdc98a9a).

These tests are the promises the page makes to its reader:

  * one row per CS2 fixture in the Hotspawn payload, and never a duplicated id;
  * every open fixture carries a pick, or is flagged so the reader can see why not;
  * no row is published without at least one external source link;
  * every published probability is internally consistent (probabilities sum to 100, the pick is the
    higher side, fair odds are the reciprocal) and the market figure is the de-vigged quote;
  * the Hotspawn community percentage is not an input to anything;
  * every relative link on the generated pages resolves to a file that exists;
  * the pages are mobile-usable (viewport meta, no external scripts or stylesheets).
"""
from __future__ import annotations

import csv
import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXEC = ROOT / "exec"
DATA = EXEC / "data"

PAGES = ["index.html", "picks.html", "coverage.html", "method.html", "sources.html", "flagged.html"]


def rows() -> list[dict]:
    with (DATA / "picks.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def payload_cs2_ids() -> set[str]:
    out = set()
    with (ROOT / "slate" / "data" / "fixtures.csv").open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("sport") == "cs2":
                out.add(row["fixture_id"])
    return out


class TestCoverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.open_rows = [r for r in cls.rows if r["status"] == "open"]
        cls.summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))

    def test_board_exists(self):
        self.assertTrue(self.rows, "exec/data/picks.csv is empty")
        self.assertGreaterEqual(len(self.open_rows), 1, "no open CS2 fixture on the board")

    def test_one_row_per_payload_fixture(self):
        ids = [r["fixture_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "a fixture appears more than once")
        self.assertEqual(set(ids), payload_cs2_ids(),
                         "the board does not cover exactly the CS2 fixtures in the Hotspawn payload")

    def test_every_open_fixture_has_a_pick_or_a_flag(self):
        missing = [r["fixture_id"] for r in self.open_rows if not r["pick"] and not r["flags"]]
        self.assertFalse(missing, f"open fixtures with neither a pick nor a flag: {missing}")

    def test_every_open_fixture_has_a_source_link(self):
        bad = []
        for row in self.open_rows:
            urls = [u for u in (row["market_url"], row["own_url"], row["hotspawn_url"],
                                row["hltv_url"]) if u.startswith("http")]
            if not urls:
                bad.append(row["fixture_id"])
        self.assertFalse(bad, f"open rows without any source link: {bad}")

    def test_summary_counts_match_the_rows(self):
        self.assertEqual(self.summary["payload_fixtures_cs2"], len(self.rows))
        self.assertEqual(self.summary["open_fixtures"], len(self.open_rows))
        self.assertEqual(self.summary["open_with_pick"],
                         len([r for r in self.open_rows if r["pick"]]))
        self.assertEqual(self.summary["open_with_external_market"],
                         len([r for r in self.open_rows if r["market_odds_a"]]))

    def test_open_status_is_not_stale(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        for row in self.open_rows:
            start = datetime.strptime(row["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            self.assertGreaterEqual(start, cutoff,
                                    f"{row['fixture_id']} is published as open but started {start}")

    def test_stale_rows_are_flagged(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=2)
        stale = [r for r in self.rows if r["status"] != "open"
                 and datetime.strptime(r["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < cutoff]
        self.assertTrue(stale, "the payload's stale summer fixtures should still be listed")
        for row in stale:
            self.assertIn("STALE", row["flags"], f"{row['fixture_id']} is not flagged as stale")
        for row in self.rows:
            start = datetime.strptime(row["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if start >= cutoff:
                self.assertNotIn("STALE", row["flags"],
                                 f"{row['fixture_id']} is flagged stale but starts in the future")


class TestMath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = [r for r in rows() if r["status"] == "open"]

    def test_probabilities_sum_to_one_hundred(self):
        for row in self.rows:
            if not row["p_a_pct"]:
                continue
            self.assertAlmostEqual(float(row["p_a_pct"]) + float(row["p_b_pct"]), 100.0, delta=0.21,
                                   msg=f"{row['fixture_id']} probabilities do not sum to 100")

    def test_pick_is_the_higher_side(self):
        for row in self.rows:
            if not row["p_a_pct"] or not row["pick"]:
                continue
            pa, pb = float(row["p_a_pct"]), float(row["p_b_pct"])
            expected = row["team_a"] if pa >= pb else row["team_b"]
            self.assertEqual(row["pick"], expected,
                             f"{row['fixture_id']}: pick is not the higher-probability side")
            self.assertAlmostEqual(float(row["pick_pct"]), max(pa, pb), delta=0.11,
                                   msg=f"{row['fixture_id']}: pick_pct is not the pick's probability")

    def test_market_figure_is_the_devigged_quote(self):
        for row in self.rows:
            if not row["market_odds_a"]:
                continue
            oa, ob = float(row["market_odds_a"]), float(row["market_odds_b"])
            inv_a, inv_b = 1 / oa, 1 / ob
            pa = inv_a / (inv_a + inv_b) * 100
            self.assertAlmostEqual(float(row["market_p_a_pct"]), pa, delta=0.15,
                                   msg=f"{row['fixture_id']}: market probability is not the de-vigged quote")
            if row["basis_code"] in ("T1", "T2"):
                self.assertAlmostEqual(float(row["p_a_pct"]), pa, delta=0.15,
                                       msg=f"{row['fixture_id']}: headline is not the market figure")

    def test_own_line_sides_sum_to_one_hundred(self):
        for row in self.rows:
            if not row["own_p_a_pct"]:
                continue
            self.assertAlmostEqual(float(row["own_p_a_pct"]) + float(row["own_p_b_pct"]), 100.0,
                                   delta=0.21, msg=f"{row['fixture_id']}: own line does not sum to 100")

    def test_fair_odds_are_the_reciprocal(self):
        for row in self.rows:
            if not row["fair_odds_a"]:
                continue
            self.assertAlmostEqual(float(row["fair_odds_a"]), 100 / float(row["p_a_pct"]), delta=0.02,
                                   msg=f"{row['fixture_id']}: fair odds are not 1/p")

    def test_no_placeholder_is_used_as_a_price(self):
        for row in self.rows:
            if row["market_odds_a"] and row["market_odds_a"] == row["market_odds_b"] == "1.800":
                self.fail(f"{row['fixture_id']}: a 1.80/1.80 placeholder was published as a price")


class TestPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_hotspawn_crowd_percentage_is_never_an_input(self):
        columns = set(self.rows[0].keys())
        banned = {"crowd", "crowd_pct", "hotspawn_pct", "hotspawn_probability"}
        self.assertFalse(columns & banned, "a Hotspawn crowd column leaked into the board data")
        for page in PAGES:
            text = (EXEC / page).read_text(encoding="utf-8").lower()
            self.assertNotIn("picked%", text, f"{page} quotes Hotspawn crowd picks")
        with (DATA / "picks.csv").open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                for key, value in row.items():
                    if "crowd" in key.lower() and value:
                        self.fail(f"{key} carries a value")

    def test_every_number_has_a_source(self):
        for row in self.rows:
            if row["p_a_pct"] or row["own_p_a_pct"]:
                self.assertTrue(row["market_url"].startswith("http")
                                or row["own_url"].startswith("http"),
                                f"{row['fixture_id']}: a probability is published with no source link")

    def test_no_number_is_invented_for_unranked_matches(self):
        for row in self.rows:
            if "NO-RATING" in row["flags"] and row["basis_code"] == "T4":
                self.assertFalse(row["p_a_pct"],
                                 f"{row['fixture_id']}: a probability was invented for an unranked side")

    def test_flags_file_matches_rows(self):
        with (DATA / "flags.csv").open(newline="", encoding="utf-8") as fh:
            flags = list(csv.DictReader(fh))
        for flag in flags:
            self.assertTrue(flag["source"].startswith("http"),
                            f"flag on {flag['fixture_id']} has no source link")


class TestPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {p: (EXEC / p).read_text(encoding="utf-8") for p in PAGES}

    def test_pages_exist_and_are_mobile_first(self):
        for name, text in self.pages.items():
            self.assertIn('name="viewport"', text, f"{name} has no viewport meta")
            self.assertIn("@media", (EXEC / "style.css").read_text(encoding="utf-8"),
                          "the stylesheet carries no responsive rules")
            self.assertNotIn("<script src=", text, f"{name} loads an external script")
            self.assertNotIn('rel="stylesheet" href="http', text, f"{name} loads an external stylesheet")

    def test_every_relative_link_resolves(self):
        missing = []
        for name, text in self.pages.items():
            for href in re.findall(r'href="([^"#]+)"', text):
                if href.startswith(("http://", "https://", "mailto:", "#", "javascript:")):
                    continue
                target = (EXEC / name).parent / href
                if not target.exists():
                    missing.append(f"{name} -> {href}")
        self.assertFalse(missing, f"broken local links: {sorted(set(missing))}")

    def test_picks_page_shows_every_open_fixture(self):
        text = self.pages["picks.html"]
        for row in [r for r in rows() if r["status"] == "open"]:
            self.assertIn(row["team_a"].replace("&", "&amp;"), text,
                          f"{row['fixture_id']}: {row['team_a']} is missing from picks.html")
            self.assertIn(row["team_b"].replace("&", "&amp;"), text,
                          f"{row['fixture_id']}: {row['team_b']} is missing from picks.html")

    def test_executive_summary_links_to_the_picks(self):
        text = self.pages["index.html"]
        self.assertIn('href="picks.html"', text)
        self.assertIn('href="coverage.html"', text)

    def test_sources_page_names_each_source(self):
        text = self.pages["sources.html"]
        for host in ("play.hotspawn.com", "hltv.org", "counter-strike_regional_standings", "egamersworld.com"):
            self.assertIsNotNone(re.search(host, text), f"{host} is not named on the sources page")

    def test_style_is_shipped_locally(self):
        self.assertTrue((EXEC / "style.css").exists())
        self.assertGreater((EXEC / "style.css").stat().st_size, 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
