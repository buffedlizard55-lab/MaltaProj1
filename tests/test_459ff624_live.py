"""Unit tests for session arena/459ff624 — live slate build rules.

They run without network access: a small snapshot stands in for the collector's output and
each rule that protects the published numbers is asserted directly.

Run: python3 -m unittest tests.test_459ff624_live -v
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_build():
    spec = importlib.util.spec_from_file_location("live_build_459ff624", ROOT / "live" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


build = load_build()


def fixture(match_id, team_a, team_b, start, lock, **extra):
    row = {"match_id": match_id, "sport": "cs2", "team_a": team_a, "team_b": team_b,
           "start_utc": start, "lock_utc": lock, "competition": "Test Cup", "tier": "b",
           "stage": "group", "offered_points": 3, "status": "scheduled",
           "source_url": "https://play.hotspawn.com/lobby",
           "hotspawn_match_url": f"https://www.hotspawn.com/matches/{match_id}",
           "crowd_pct_a": 50, "crowd_pct_b": 50, "crowd_total_picks": 7}
    row.update(extra)
    return row


def quote(team_a, team_b, odds_a, odds_b, start=None, bookmaker="Pinnacle"):
    return {"bookmaker": bookmaker, "source_label": bookmaker, "team_a": team_a, "team_b": team_b,
            "odds_a": odds_a, "odds_b": odds_b,
            "start_utc": start, "observed_utc": "2026-10-13T22:00:00Z",
            "source_url": "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
            "note": "test"}


def snapshot(fixtures, quotes=(), vrs_teams=(), tainted=0, pinnacle_status="observed"):
    return {
        "schema": 1,
        "generated_utc": "2026-10-13T22:00:00Z",
        "collection_started_utc": "2026-10-13T21:59:00Z",
        "week_text": None, "reset_text": None,
        "hotspawn_pages": [{"page": "lobby", "url": "https://play.hotspawn.com/lobby",
                            "status": 200, "state_rows": len(fixtures), "cards": len(fixtures),
                            "week_text": None, "reset_text": None, "error": None}],
        "fixtures": list(fixtures),
        "fixtures_with_crowd_fields": tainted,
        "vrs": {"status": "observed",
                "url": "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/main/live/2026/standings_global_2026_10_05.md",
                "as_of": "2026-10-05", "teams": [{"vrs_rank": 1, "name": n, "points": p}
                                                 for n, p in vrs_teams]},
        "pinnacle": {"status": pinnacle_status,
                     "quotes": [q for q in quotes if q["bookmaker"] == "Pinnacle"]},
        "egw": {"status": "unavailable", "listing_url": "https://egamersworld.com/counterstrike/matches",
                "listing": [], "detail": [q for q in quotes if q["bookmaker"] == "EGamersWorld"]},
        "hltv": {"status": "observed", "url": "https://www.hltv.org/ranking/teams/2026/october/12",
                 "ranks": {"Alpha": 10, "Bravo": 40}, "matched": {}, "total_rows": 2},
        "provenance": [],
    }


class BuildRules(unittest.TestCase):
    def test_devig_is_normalised_and_reports_overround(self):
        p_a, p_b, over = build.devig(2.0, 2.0)
        self.assertEqual((p_a, p_b), (50.0, 50.0))
        self.assertEqual(over, 0.0)
        p_a, p_b, over = build.devig(1.5, 3.0)
        self.assertAlmostEqual(p_a + p_b, 100.0, places=6)
        self.assertAlmostEqual(over, 100 * (1 / 1.5 + 1 / 3.0 - 1), places=6)

    def test_own_line_follows_valve_points(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        vrs_teams=[("Alpha", 1700.0), ("Bravo", 1500.0)])
        rows = build.build_rows(snap)
        self.assertAlmostEqual(float(rows[0]["own_p_a_pct"]), 100 / (1 + 10 ** (-200 / 400)), places=1)
        self.assertEqual(rows[0]["probability_source"], "our own line (Valve VRS)")
        self.assertEqual(rows[0]["pick"], "Alpha")
        self.assertIn("FL-13", rows[0]["flags"])

    def test_market_drives_headline_when_present(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.5, 3.0, "2026-10-14T10:00:00Z")],
                        vrs_teams=[("Alpha", 1500.0), ("Bravo", 1700.0)])
        rows = build.build_rows(snap)
        self.assertAlmostEqual(float(rows[0]["ext_p_a_pct"]), 66.7, places=1)
        self.assertEqual(rows[0]["probability_source"], "external market (de-vigged)")
        self.assertEqual(rows[0]["pick"], "Alpha")
        self.assertNotIn("FL-01", rows[0]["flags"])
        self.assertIn("FL-11", rows[0]["flags"])  # market and own line disagree

    def test_reversed_quote_order_is_joined_correctly(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Bravo", "Alpha", 3.0, 1.5, "2026-10-14T10:00:00Z")])
        rows = build.build_rows(snap)
        # the quote lists Bravo first at 3.00 and Alpha at 1.50, so Alpha is the favourite
        self.assertAlmostEqual(float(rows[0]["ext_p_a_pct"]), 66.7, places=1)
        self.assertAlmostEqual(float(rows[0]["ext_p_b_pct"]), 33.3, places=1)
        self.assertEqual(rows[0]["pick"], "Alpha")

    def test_start_time_outside_tolerance_is_rejected(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.5, 3.0, "2026-10-15T10:00:00Z")])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["ext_p_a_pct"], "")
        self.assertIn("FL-01", rows[0]["flags"])

    def test_alias_join_for_wrotberry(self):
        snap = snapshot([fixture("1", "WROTBERRY", "EAC", "2026-10-15T08:00:00Z", "2026-10-15T07:54:00Z")],
                        quotes=[quote("WBT", "EA Copenhagen", 2.0, 1.72)])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["ext_p_a_pct"], "46.2")
        self.assertIn("FL-10", rows[0]["flags"])

    def test_crowd_fields_never_reach_the_slate(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        tainted=1)
        rows = build.build_rows(snap)
        for banned in ("crowd_pct_a", "crowd_pct_b", "crowd_total_picks"):
            self.assertNotIn(banned, rows[0])
        self.assertNotIn("50", [rows[0].get("pick_pct", "")])

    def test_blank_when_nothing_verified(self):
        snap = snapshot([fixture("1", "Nobody", "Unknown", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["final_p_a_pct"], "")
        self.assertEqual(rows[0]["pick"], "")
        self.assertIn("FL-02", rows[0]["flags"])
        self.assertIn("FL-04", rows[0]["flags"])
        self.assertEqual(build.self_check(rows, snap), [])

    def test_close_market_gives_no_confident_pick(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.95, 1.95)])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["pick"], "No confident pick")

    def test_locked_fixtures_are_not_pickable(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-13T20:00:00Z", "2026-10-13T19:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.5, 3.0, "2026-10-13T20:00:00Z")])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["pickable"], "no")
        self.assertTrue(rows[0]["not_pickable_reason"])

    def test_egw_placeholder_pairs_are_ignored(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.8, 1.8, bookmaker="EGamersWorld")])
        rows = build.build_rows(snap)
        self.assertEqual(rows[0]["ext_p_a_pct"], "")

    def test_every_row_keeps_a_source_link(self):
        snap = snapshot([fixture("1", "Alpha", "Bravo", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")],
                        quotes=[quote("Alpha", "Bravo", 1.5, 3.0, "2026-10-14T10:00:00Z")])
        rows = build.build_rows(snap)
        for row in rows:
            self.assertTrue(row["hotspawn_url"].startswith("https://"))
            self.assertTrue(row["ext_url"].startswith("https://"))

    def test_flags_always_carry_text_and_a_link(self):
        snap = snapshot([fixture("1", "Nobody", "Unknown", "2026-10-14T10:00:00Z", "2026-10-14T09:54:00Z")])
        rows = build.build_rows(snap)
        flags = build.collect_flags(rows, snap)
        self.assertTrue(flags)
        for flag in flags:
            self.assertTrue(flag["text"])
            self.assertTrue(flag["source_url"].startswith("http"))


if __name__ == "__main__":
    unittest.main()
