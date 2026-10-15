#!/usr/bin/env python3
"""Unit tests for the every-match picks board (session arena/b44b5d5e).

These tests do not touch the network.  They feed a synthetic snapshot through the same
``build``/``self_check``/render functions the workflow uses and assert the rules the brief
sets out:

* a published probability always names its source and links it;
* a market line wins over our own line, and our own line is still shown beside it;
* a prediction-market price is labelled and never de-vigged;
* an unconfirmable fixture is published as an unresolved row, never dropped and never guessed;
* a score taken from Hotspawn's payload is cross-checked against the independent verification
  trail and a disagreement is flagged, not silently resolved;
* the best-of transform used for own lines is the exact one (checked against an enumeration);
* a crowd percentage can never reach the dataset.
"""
from __future__ import annotations

import importlib.util
import json
import math
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "matchpicks"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


build_mod = load("matchpicks_build", HERE / "build.py")
collect_mod = load("matchpicks_collect", HERE / "collect_full.py")

GENERATED = "2026-10-15T06:00:00Z"


def synthetic_snapshot() -> dict:
    """A snapshot with one fixture per rung of the research ladder."""
    fixtures = [
        # 1. Pinnacle moneyline, spelled differently by the source (alias + start tolerance).
        {
            "match_id": "1080201", "sport": "cs2", "competition": "Thunderpick World Championship 2026",
            "tier": "s", "stage": "Group Stage And Playoffs", "points": 7, "best_of": 3,
            "status": "scheduled", "team_a": "Aurora", "team_b": "Ninjas in Pyjamas",
            "start_utc": "2026-10-15T08:30:00Z", "lock_utc": "2026-10-15T08:24:00Z",
            "team_a_score": None, "team_b_score": None,
            "hotspawn_match_url": "https://www.hotspawn.com/?fixtures=waiting-for-information-1080201",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 2. EGamersWorld aggregate only (no primary book on a low-tier match).
        {
            "match_id": "1080279", "sport": "cs2", "competition": "Elisa BreakOut Series #2",
            "tier": "c", "stage": "Waiting For Information", "points": 2, "best_of": 1,
            "status": "scheduled", "team_a": "WROTBERRY", "team_b": "EAC",
            "start_utc": "2026-10-15T12:00:00Z", "lock_utc": "2026-10-15T11:54:00Z",
            "hotspawn_match_url": "https://www.hotspawn.com/matches/wrotberry-vs-eac-elisa-breakout-series-2-1080279",
            "source_url": "https://play.hotspawn.com/cs2-pickems",
        },
        # 3. Prediction market only.
        {
            "match_id": "1081112", "sport": "cs2", "competition": "CCT Europe 2026 Series #12 Play-In",
            "tier": "c", "stage": "Waiting For Information", "points": 2, "best_of": 3,
            "status": "scheduled", "team_a": "banda chuya", "team_b": "6666",
            "start_utc": "2026-10-16T10:00:00Z", "lock_utc": "2026-10-16T09:54:00Z",
            "hotspawn_match_url": "https://www.hotspawn.com/matches/banda-chuya-vs-6666-cct-1081112",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 4. No market at all, both teams in Valve's official standings → own line, series length stated.
        {
            "match_id": "1080280", "sport": "cs2", "competition": "Elisa BreakOut Series #2",
            "tier": "c", "stage": "Waiting For Information", "points": 2, "best_of": 3,
            "status": "scheduled", "team_a": "ENCE", "team_b": "BOJONG",
            "start_utc": "2026-10-16T12:00:00Z", "lock_utc": "2026-10-16T11:54:00Z",
            "hotspawn_match_url": "https://www.hotspawn.com/matches/ence-vs-bojong-1080280",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 5. No market, no VRS pair, but both teams carry an official HLTV rank, no stated length.
        {
            "match_id": "1080290", "sport": "cs2", "competition": "Elisa BreakOut Series #2",
            "tier": "c", "stage": "Waiting For Information", "points": 2, "best_of": None,
            "status": "scheduled", "team_a": "Phantom", "team_b": "HAVU",
            "start_utc": "2026-10-16T14:00:00Z", "lock_utc": "2026-10-16T13:54:00Z",
            "hotspawn_match_url": "https://www.hotspawn.com/matches/phantom-vs-havu-1080290",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 6. Nothing usable: no quote, no VRS, no HLTV rank → must stay blank and unresolved.
        {
            "match_id": "1089999", "sport": "cs2", "competition": "Some Qualifier",
            "tier": "c", "stage": "Waiting For Information", "points": 2, "best_of": None,
            "status": "scheduled", "team_a": "Mystery Mix", "team_b": "Unknown Org",
            "start_utc": "2026-10-16T15:00:00Z", "lock_utc": "2026-10-16T14:54:00Z",
            "hotspawn_match_url": "https://www.hotspawn.com/matches/x-1089999",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 7. Played fixture whose payload score agrees with the independent trail.
        {
            "match_id": "1052746", "sport": "cs2", "competition": "European Pro League Series 8 Play-In",
            "tier": "c", "stage": "Group Stage", "points": 2, "best_of": 3, "status": "finished",
            "team_a": "Fortress", "team_b": "Endless Journey",
            "start_utc": "2026-06-26T10:30:00Z", "lock_utc": "2026-06-26T10:24:00Z",
            "team_a_score": 0, "team_b_score": 2,
            "hotspawn_match_url": "https://www.hotspawn.com/matches/fortress-vs-endless-journey-1052746",
            "source_url": "https://play.hotspawn.com/lobby",
        },
        # 8. Played fixture whose payload score contradicts the independent trail → flagged, both shown.
        {
            "match_id": "1052747", "sport": "cs2", "competition": "European Pro League Series 8 Play-In",
            "tier": "c", "stage": "Group Stage", "points": 2, "best_of": 3, "status": "finished",
            "team_a": "Fortress", "team_b": "Endless Journey",
            "start_utc": "2026-06-26T11:30:00Z", "lock_utc": "2026-06-26T11:24:00Z",
            "team_a_score": 2, "team_b_score": 0,
            "hotspawn_match_url": "https://www.hotspawn.com/matches/y-1052747",
            "source_url": "https://play.hotspawn.com/lobby",
        },
    ]
    incomplete = [
        {
            "match_id": "1080202", "sport": "cs2", "competition": "Thunderpick World Championship 2026",
            "tier": "s", "stage": "Group Stage And Playoffs", "points": 7, "status": "scheduled",
            "team_a": None, "team_b": None, "start_utc": None, "lock_utc": None,
            "missing_fields": ["team_a", "team_b", "start_utc"],
            "payload_keys": ["id", "competition_name", "scheduled_start_time", "tier"],
            "source_url": "https://play.hotspawn.com/lobby",
        },
    ]
    return {
        "schema": 1, "session": "test", "generated_utc": GENERATED,
        "week_text": "72 matches this week", "reset_text": "3d 15h",
        "hotspawn_pages": [{"page": "lobby", "url": "https://play.hotspawn.com/lobby", "status": 200}],
        "fixtures_complete": fixtures, "fixtures_incomplete": incomplete,
        "dom_ids": ["1080201", "9999999"], "dom_only_ids": ["9999999"],
        "crowd_fields_dropped": 12,
        "vrs": {
            "status": "observed",
            "url": "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/live/2026/standings_global_2026_10_05.md",
            "as_of": "2026-10-05", "fetched_utc": GENERATED,
            "teams": [
                {"vrs_rank": 12, "name": "ENCE", "points": 1500.0},
                {"vrs_rank": 60, "name": "BOJONG", "points": 1100.0},
            ],
        },
        "hltv": {
            "status": "observed", "url": "https://www.hltv.org/ranking/teams/2026/october/12",
            "fetched_utc": GENERATED, "total_rows": 208,
            "ranks": {"phantom": 61, "havu": 45, "mystery mix": 0},
            "matched": {},
        },
        "pinnacle": {"status": "observed", "quotes": [{
            "bookmaker": "Pinnacle", "market": "match_winner", "team_a": "Aurora Gaming",
            "team_b": "Ninjas in Pyjamas", "start_utc": "2026-10-15T08:30:00Z",
            "odds_a": 1.25, "odds_b": 3.80, "observed_utc": GENERATED,
            "source_url": "https://www.pinnacle.com/en/esports/matchups/highlights/",
        }]},
        "egw": {"status": "observed", "listing": [], "detail": [{
            "url": "https://egamersworld.com/counterstrike/match/abc/wrotberry-vs-eac-xyz",
            "team_a": "wrotberry", "team_b": "eac", "prices": [1.65, 2.22], "status": 200,
        }]},
        "polymarket": {"status": "observed", "quotes": [{
            "bookmaker": "Polymarket", "kind": "prediction_market", "market": "match_winner",
            "team_a": "banda chuya", "team_b": "6666", "start_utc": "2026-10-16T10:00:00Z",
            "odds_a": 1.33, "odds_b": 4.35, "observed_utc": GENERATED,
            "source_url": "https://polymarket.com/event/cs2-bandachuya-6666-2026-10-16",
            "volume_usd": 4200.0,
        }]},
        "provenance": [],
    }


class SeriesMath(unittest.TestCase):
    @staticmethod
    def enumerated(first_to: int, p: float) -> float:
        """Race to ``first_to`` wins, each map independent: win the last map having taken
        ``first_to - 1`` of the previous ``first_to - 1 + k`` maps."""
        return sum(math.comb(first_to - 1 + k, k) * p ** first_to * (1 - p) ** k
                   for k in range(first_to))

    def test_bo3_transform_matches_enumeration(self):
        for p in (0.05, 0.2, 0.5, 0.73, 0.95):
            self.assertAlmostEqual(build_mod.ownlines.series_probability(p, 3),
                                   self.enumerated(2, p), places=9)

    def test_bo5_transform_matches_enumeration(self):
        for p in (0.1, 0.4, 0.62, 0.9):
            self.assertAlmostEqual(build_mod.ownlines.series_probability(p, 5),
                                   self.enumerated(3, p), places=9)

    def test_closed_forms_match_the_documented_polynomials(self):
        for p in (0.17, 0.5, 0.88):
            self.assertAlmostEqual(build_mod.ownlines.series_probability(p, 3),
                                   3 * p ** 2 - 2 * p ** 3, places=12)
            self.assertAlmostEqual(build_mod.ownlines.series_probability(p, 5),
                                   10 * p ** 3 - 15 * p ** 4 + 6 * p ** 5, places=12)


class Ladder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = synthetic_snapshot()
        cls.built = build_mod.build(cls.snapshot)
        cls.rows = {row["match_id"]: row for row in cls.built["rows"]}
        cls.unresolved = {row["match_id"]: row for row in cls.built["unresolved"]}

    def test_bookmaker_line_wins_and_is_devigged(self):
        row = self.rows["1080201"]
        self.assertEqual(row["market_book"], "Pinnacle")
        implied_a, implied_b = 100 / 1.25, 100 / 3.80
        expected_a = round(100 * implied_a / (implied_a + implied_b), 1)
        self.assertAlmostEqual(float(row["market_p_a_pct"]), expected_a, places=1)
        self.assertAlmostEqual(float(row["p_a"]) + float(row["p_b"]), 100.0, places=1)
        self.assertEqual(row["pick"], "Aurora")
        self.assertIn("Pinnacle", row["probability_source"])
        self.assertTrue(row["market_url"].startswith("https://www.pinnacle.com/"))

    def test_name_variant_is_disclosed_and_flagged(self):
        row = self.rows["1080201"]
        self.assertIn("Aurora Gaming → Aurora", row["aliases"])
        self.assertIn("MP-F10", row["flags"])

    def test_egw_aggregate_used_when_no_primary_book(self):
        row = self.rows["1080279"]
        self.assertEqual(row["market_book"], "EGamersWorld")
        self.assertEqual(row["pick"], "WROTBERRY")
        self.assertTrue(row["market_url"].startswith("https://egamersworld.com/"))
        implied_a, implied_b = 100 / 1.65, 100 / 2.22
        self.assertAlmostEqual(float(row["market_p_a_pct"]),
                               round(100 * implied_a / (implied_a + implied_b), 1), places=1)

    def test_prediction_market_is_labelled_and_not_devigged(self):
        row = self.rows["1081112"]
        self.assertIn("prediction market", row["probability_source"])
        self.assertIn("MP-F25", row["flags"])
        self.assertAlmostEqual(float(row["market_p_a_pct"]), round(100 / 1.33, 1), places=1)
        # an un-de-vigged prediction market can show an overround, which is printed on the row
        self.assertNotEqual(row["market_overround_pct"], "")

    def test_own_line_from_official_vrs_uses_stated_series_length(self):
        row = self.rows["1080280"]
        self.assertEqual(row["market_p_a_pct"], "")
        self.assertIn("Valve Regional Standings", row["own_basis"])
        self.assertEqual(row["own_scope"], "series")
        p_map = 1 / (1 + 10 ** (-(1500.0 - 1100.0) / 400.0))
        expected = 100 * build_mod.ownlines.series_probability(p_map, 3)
        self.assertAlmostEqual(float(row["own_p_a_pct"]), round(expected, 1), places=1)
        self.assertEqual(row["pick"], "ENCE")
        self.assertIn("MP-F01", row["flags"])

    def test_own_line_falls_back_to_official_hltv_rank_and_is_labelled_per_map(self):
        row = self.rows["1080290"]
        self.assertIn("HLTV world ranking", row["own_basis"])
        self.assertEqual(row["own_scope"], "per-map")
        self.assertIn("MP-F05", row["flags"])
        self.assertEqual(row["pick"], "HAVU")
        self.assertAlmostEqual(float(row["own_p_a_pct"]),
                               round(100 * (1 / (1 + 10 ** ((61 - 45) / 100.0))), 1), places=1)

    def test_no_source_means_blank_row_and_unresolved_entry(self):
        row = self.rows["1089999"]
        self.assertEqual(row["p_a"], "")
        self.assertEqual(row["pick"], "")
        self.assertIn("MP-F01", row["flags"])
        self.assertIn("MP-F02", row["flags"])
        self.assertIn("1089999", self.unresolved)

    def test_participantless_fixture_is_published_as_unresolved_not_dropped(self):
        self.assertIn("1080202", self.unresolved)
        entry = self.unresolved["1080202"]
        self.assertEqual(entry["state"], "identity incomplete")
        self.assertIn("MP-F08", entry["flags"])
        self.assertIn("has not published", entry["unresolved_reason"])

    def test_markup_only_id_is_published_as_unresolved(self):
        self.assertIn("9999999", self.unresolved)
        self.assertEqual(self.unresolved["9999999"]["state"], "markup only")

    def test_played_fixture_score_is_cross_checked_both_ways(self):
        agree = self.rows["1052746"]
        self.assertTrue(agree["result_cross_check"].startswith("agrees"))
        self.assertNotIn("MP-F30", agree["flags"])
        disagree = self.rows["1052747"]
        self.assertTrue(disagree["result_cross_check"].startswith("DISAGREES"))
        self.assertIn("MP-F30", disagree["flags"])

    def test_summary_accounting(self):
        summary = self.built["summary"]
        self.assertEqual(summary["open"], summary["open_with_pick"] + summary["open_without_pick"])
        self.assertEqual(summary["fixtures_captured"], len(self.built["rows"]))
        self.assertGreaterEqual(summary["unresolved_total"], 3)
        self.assertEqual(summary["crowd_fields_dropped"], 12)

    def test_self_check_rejects_a_pick_outside_the_two_teams(self):
        rows = [dict(row) for row in self.built["rows"]]
        rows[0]["pick"] = "Someone Else"
        with self.assertRaises(SystemExit):
            build_mod.self_check(rows, self.built["unresolved"], self.built["summary"])

    def test_self_check_rejects_probability_without_source_link(self):
        rows = [dict(row) for row in self.built["rows"]]
        target = next(row for row in rows if row["p_a"])
        target["market_url"] = ""
        target["own_url"] = ""
        with self.assertRaises(SystemExit):
            build_mod.self_check(rows, self.built["unresolved"], self.built["summary"])


class CrowdFields(unittest.TestCase):
    def test_collector_strips_every_crowd_field(self):
        node = {
            "id": 1, "participants0_name": "A", "participants1_name": "B",
            "participants0_picked_percent": 91, "participants1_picked_percent": 9,
            "total_picks": 4321, "scheduled_start_time": 1770000000000,
            "participants": [{"name": "A", "picked_percent": 91}, {"name": "B", "picked_percent": 9}],
        }
        clean = collect_mod.strip_crowd(node)
        self.assertNotIn("participants0_picked_percent", clean)
        self.assertNotIn("total_picks", clean)
        self.assertNotIn("picked_percent", json.dumps(clean))
        self.assertEqual(clean["participants0_name"], "A")


class Pages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = synthetic_snapshot()
        cls.built = build_mod.build(cls.snapshot)
        cls.tmp = tempfile.TemporaryDirectory()
        path = Path(cls.tmp.name)
        rows, unresolved = cls.built["rows"], cls.built["unresolved"]
        summary, meta = cls.built["summary"], cls.built["meta"]
        flags = cls.built["flags"]
        (path / "index.html").write_text(build_mod.render_index(rows, unresolved, flags, summary, meta))
        (path / "all-fixtures.html").write_text(
            build_mod.render_all_fixtures(rows, unresolved, summary, meta))
        (path / "unresolved.html").write_text(build_mod.render_unresolved(rows, unresolved, summary, meta))
        (path / "flagged.html").write_text(build_mod.render_flagged(rows, unresolved, flags, summary, meta))
        (path / "methodology.html").write_text(build_mod.render_methodology(rows, summary, meta))
        cls.pages = {p.name: p.read_text() for p in path.iterdir()}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_page_links_the_other_pages_and_the_stylesheet(self):
        for name, html in self.pages.items():
            self.assertIn('href="style.css"', html)
            for other in ("index.html", "all-fixtures.html", "unresolved.html", "flagged.html",
                          "methodology.html"):
                self.assertIn(f'href="{other}"', html)
            self.assertIn("viewport", html)

    def test_board_rows_carry_a_source_link(self):
        html = self.pages["index.html"]
        self.assertIn("https://www.pinnacle.com/en/esports/matchups/highlights/", html)
        self.assertIn("https://egamersworld.com/counterstrike/match/abc/wrotberry-vs-eac-xyz", html)
        self.assertIn("standings_global_2026_10_05.md", html)
        self.assertIn("https://www.hltv.org/ranking/teams/2026/october/12", html)
        self.assertIn("https://polymarket.com/event/cs2-bandachuya-6666-2026-10-16", html)

    def test_index_keeps_the_open_picks_and_the_inventory_page_carries_the_rest(self):
        index = self.pages["index.html"]
        inventory = self.pages["all-fixtures.html"]
        self.assertIn("1080201", index)          # open fixture, on the landing page
        self.assertNotIn("1052746", index)       # played fixture, moved off the landing page
        self.assertIn("1052746", inventory)
        self.assertIn("1052747", inventory)
        self.assertIn('href="all-fixtures.html"', index)

    def test_unresolved_page_lists_the_identity_and_markup_gaps(self):
        html = self.pages["unresolved.html"]
        self.assertIn("1080202", html)
        self.assertIn("9999999", html)
        self.assertIn("1089999", html)
        self.assertIn("Identity not published by Hotspawn yet", html)

    def test_flagged_page_explains_every_flag_it_renders(self):
        html = self.pages["flagged.html"]
        for flag in self.built["flags"]:
            self.assertIn(flag, html)
            self.assertIn(build_mod.FLAG_TEXT[flag][1][:40], html)

    def test_methodology_states_the_rules_the_board_relies_on(self):
        html = self.pages["methodology.html"]
        self.assertIn("1/odds_A", html)
        self.assertIn("never used", html.lower().replace("not used", "never used"))
        self.assertIn("Unresolved page", html)

    def test_no_hotspawn_crowd_percentage_is_rendered(self):
        for html in self.pages.values():
            self.assertNotIn("picked_percent", html)
            self.assertNotIn("crowd_pct", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
