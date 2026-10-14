"""Offline checks for the open-slate build (session arena/08031d30).

Run:  python3 -m unittest tests/test_08031d30.py -v
"""
import csv
import datetime as dt
import importlib.util
import os
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "08031d30")

_spec = importlib.util.spec_from_file_location(
    "build_08031d30", os.path.join(ROOT, "scripts", "08031d30_build.py"))
B = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B)


def read_csv(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return list(csv.DictReader(f))


class HotspawnList(unittest.TestCase):
    def setUp(self):
        self.rows = read_csv("hotspawn_open_cs2.csv")

    def test_live_open_count_matches_the_page(self):
        # The live CS2 pick'em page (fetched 2026-10-14 01:41-01:58Z) lists 28 open fixtures.
        live = [r for r in self.rows if r["on_live_hotspawn_list"] == "yes"]
        self.assertEqual(len(live), 28)
        self.assertEqual(len({r["fixture_id"] for r in live}), 28)

    def test_every_live_row_has_a_hotspawn_source(self):
        for r in self.rows:
            if r["on_live_hotspawn_list"] == "yes":
                self.assertTrue(r["hotspawn_lobby_url"].startswith("https://play.hotspawn.com/"), r["fixture_id"])

    def test_display_time_is_utc_minus_4_on_every_row(self):
        # The page shows local times without a zone name; UTC-4 is inferred from agreement with the payload UTC.
        for r in self.rows:
            if r["on_live_hotspawn_list"] != "yes":
                continue
            shown = dt.datetime.strptime(r["hotspawn_display_as_shown"], "%b %d, %H:%M")
            shown = shown.replace(year=2026, month=10)
            utc = dt.datetime.fromisoformat(r["kickoff_utc"].replace("Z", "+00:00")).replace(tzinfo=None)
            self.assertEqual(shown + dt.timedelta(hours=4), utc, r["fixture_id"])

    def test_excluded_row_is_not_on_the_list(self):
        ex = [r for r in self.rows if r["on_live_hotspawn_list"] != "yes"]
        self.assertEqual([r["fixture_id"] for r in ex], ["1079546"])
        kick = dt.datetime.fromisoformat(ex[0]["kickoff_utc"].replace("Z", "+00:00"))
        now = dt.datetime(2026, 10, 14, 1, 41, tzinfo=dt.timezone.utc)
        self.assertLess(kick, now)


class MarketReads(unittest.TestCase):
    def test_no_placeholder_pair_is_used_as_a_market(self):
        for r in read_csv("market_reads.csv"):
            if r["source"].find("PLACEHOLDER") >= 0:
                self.assertEqual((float(r["odds_a"]), float(r["odds_b"])), (1.8, 1.8))
        slate = read_csv("open_slate.csv")
        for r in slate:
            if r["external_odds_a"]:
                self.assertNotEqual((float(r["external_odds_a"]), float(r["external_odds_b"])), (1.8, 1.8),
                                    r["fixture_id"])

    def test_every_fresh_read_has_a_url_and_window(self):
        for r in read_csv("market_reads.csv"):
            self.assertTrue(r["source_url"].startswith("https://"), r["fixture_id"])
            self.assertTrue(r["read_window_utc"], r["fixture_id"])


class OpenSlate(unittest.TestCase):
    def setUp(self):
        self.rows = read_csv("open_slate.csv")

    def test_one_row_per_live_open_fixture(self):
        self.assertEqual(len(self.rows), 28)

    def test_probabilities_sum_to_100_when_present(self):
        for r in self.rows:
            if r["p_team_a_pct"]:
                s = float(r["p_team_a_pct"]) + float(r["p_team_b_pct"])
                self.assertAlmostEqual(s, 100.0, delta=0.15, msg=r["fixture_id"])

    def test_pick_is_the_higher_probability(self):
        for r in self.rows:
            if not r["pick"]:
                continue
            pa, pb = float(r["p_team_a_pct"]), float(r["p_team_b_pct"])
            expected = r["team_a"] if pa >= pb else r["team_b"]
            self.assertEqual(r["pick"], expected, r["fixture_id"])

    def test_every_row_links_its_external_or_own_basis(self):
        for r in self.rows:
            if r["external_status"]:
                self.assertTrue(r["external_url"].startswith("https://"), r["fixture_id"])
            elif r["pick"]:
                self.assertIn("own line", r["pick_basis"], r["fixture_id"])

    def test_no_crowd_percentage_is_an_input(self):
        # Hotspawn "picked" percentages are never read by the build; the page has no such column.
        with open(os.path.join(DATA, "open_slate.csv"), encoding="utf-8") as f:
            self.assertNotIn("picked", f.read().lower())

    def test_fresh_pick_matches_hand_devig(self):
        by = {r["fixture_id"]: r for r in self.rows}
        # Enjoy 1.52 / B8 2.30 (EGamersWorld match page): 1/1.52 = .6579, 1/2.30 = .4348, total 1.0927.
        self.assertEqual(by["1081111"]["pick"], "Enjoy")
        self.assertAlmostEqual(float(by["1081111"]["p_team_a_pct"]), 60.2, delta=0.1)
        # Falcons 1.19 / NiP 3.95 (EGamersWorld listing).
        self.assertEqual(by["1080177"]["pick"], "Falcons")
        self.assertAlmostEqual(float(by["1080177"]["p_team_a_pct"]), 76.8, delta=0.1)

    def test_placeholder_fixtures_have_no_external_probability(self):
        by = {r["fixture_id"]: r for r in self.rows}
        for fid in ("1081112", "1081113", "1079624"):
            self.assertEqual(by[fid]["external_status"], "", fid)


class Devig(unittest.TestCase):
    def test_sums_to_100(self):
        pa, pb, _ = B.devig(1.52, 2.3)
        self.assertAlmostEqual(pa + pb, 100.0, places=6)

    def test_overround_is_positive(self):
        _, _, ov = B.devig(1.52, 2.3)
        self.assertGreater(ov, 0)


if __name__ == "__main__":
    unittest.main()
