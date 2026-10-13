from copy import deepcopy
from datetime import datetime, timezone, timedelta
import math
import unittest

from collector.analytics import analyze_match, american_to_decimal, eligible_quote, iso_time, match_orientation, no_vig, normalized_name, parse_time

NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
MATCH = {"id": "fixture-only", "game": "cs2", "team_a": "Alpha Academy", "team_b": "Bravo", "start_time": "2026-10-14T09:00:00Z"}
QUOTE = {"id": "fixture-quote", "source_id": "fixture-book", "source_role": "primary_bookmaker", "event_id": "fixture-event", "game": "cs2", "team_a": "Alpha Academy", "team_b": "Bravo", "start_time": "2026-10-14T09:00:00Z", "observed_at": "2026-10-13T17:50:00Z", "market_type": "match_winner", "period": "match", "status": "open", "is_live": False, "outcome_count": 2, "evidence_id": "fixture-evidence", "source_url": "https://example.org/test-fixture", "odds_a": 1.5, "odds_b": 3.0}


class AnalyticsTests(unittest.TestCase):
    def test_no_vig_and_fair_prices(self):
        actual = no_vig(1.5, 3.0)
        self.assertAlmostEqual(actual["probability_a"], 2 / 3)
        self.assertAlmostEqual(actual["probability_b"], 1 / 3)
        self.assertAlmostEqual(actual["overround"], 0)
        self.assertAlmostEqual(actual["fair_odds_a"], 1.5)

    def test_removes_margin(self):
        actual = no_vig(1.8, 1.8)
        self.assertEqual(actual["probability_a"], .5)
        self.assertAlmostEqual(actual["overround"], 1 / 9)

    def test_invalid_odds_rejected(self):
        for bad in (None, True, False, 1, 0, -3, float("nan"), float("inf"), "2.5"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                no_vig(bad, 2)

    def test_american_conversion(self):
        self.assertAlmostEqual(american_to_decimal(150), 2.5)
        self.assertAlmostEqual(american_to_decimal(-200), 1.5)
        for bad in (0, 99, -99, True, "150", float("nan")):
            with self.assertRaises(ValueError):
                american_to_decimal(bad)

    def test_explicit_timezone_only(self):
        self.assertIsNone(parse_time("2026-10-14T09:00:00"))
        self.assertEqual(parse_time("2026-10-14T11:00:00+02:00"), parse_time(MATCH["start_time"]))
        self.assertIsNone(parse_time("not a date"))
        with self.assertRaises(ValueError):
            iso_time(datetime(2026, 10, 13))

    def test_name_normalization_does_not_invent_aliases(self):
        self.assertEqual(normalized_name("  BRAVO  "), "bravo")
        self.assertNotEqual(normalized_name("Alpha"), normalized_name("Alpha Academy"))
        self.assertNotEqual(normalized_name("9z"), normalized_name("9z Team"))
        self.assertNotEqual(normalized_name("BC.Game"), normalized_name("BC Game"))

    def test_exact_match_reversed_orientation(self):
        self.assertIs(match_orientation(MATCH, QUOTE), False)
        reverse = {**QUOTE, "team_a": "Bravo", "team_b": "Alpha Academy", "odds_a": 3., "odds_b": 1.5}
        self.assertIs(match_orientation(MATCH, reverse), True)
        actual = analyze_match(MATCH, [reverse], NOW)
        self.assertAlmostEqual(actual["probability_a"], 2 / 3)
        self.assertTrue(actual["inputs"][0]["reversed"])

    def test_wrong_game_time_and_team_rejected(self):
        for change in ({"game": "lol"}, {"start_time": "2026-10-14T09:05:00Z"}, {"team_a": "Alpha"}):
            self.assertIsNone(match_orientation(MATCH, {**QUOTE, **change}))

    def test_live_map_suspended_draw_and_stale_rejected(self):
        for change in (
            {"is_live": True}, {"period": "map_1"}, {"market_type": "map_winner"},
            {"status": "suspended"}, {"outcome_count": 3}, {"source_role": "pickem"},
            {"observed_at": "2026-10-13T16:59:59Z"}, {"observed_at": "2026-10-13T18:00:01Z"},
            {"start_time": "2026-10-13T17:00:00Z"}, {"evidence_id": None}, {"odds_a": None},
        ):
            with self.subTest(change=change):
                self.assertFalse(eligible_quote({**QUOTE, **change}, NOW))

    def test_no_quotes_no_prior(self):
        actual = analyze_match({**MATCH, "picked_percent_a": 99}, [], NOW)
        self.assertIsNone(actual["probability_a"])
        self.assertIsNone(actual["fair_odds_a"])
        self.assertEqual(actual["source_count"], 0)

    def test_pick_percentages_have_no_effect(self):
        baseline = analyze_match(MATCH, [QUOTE], NOW)
        for pct in (0, 50, 100):
            self.assertEqual(baseline, analyze_match({**MATCH, "picked_percent_a": pct}, [QUOTE], NOW))

    def test_equal_weight_per_book_not_per_quote(self):
        duplicate = {**QUOTE, "id": "fixture-duplicate", "observed_at": "2026-10-13T17:55:00Z"}
        second_book = {**QUOTE, "id": "fixture-second", "source_id": "fixture-second-book", "odds_a": 2., "odds_b": 2.}
        actual = analyze_match(MATCH, [QUOTE, duplicate, second_book], NOW)
        self.assertEqual(actual["source_count"], 2)
        self.assertAlmostEqual(actual["probability_a"], (2 / 3 + .5) / 2)
        self.assertAlmostEqual(actual["spread"], 1 / 6)
        self.assertIn("fixture-duplicate", [item["quote_id"] for item in actual["inputs"]])

    def test_ambiguous_duplicate_events_excluded(self):
        actual = analyze_match(MATCH, [QUOTE, {**QUOTE, "id": "other", "event_id": "other-event"}], NOW)
        self.assertIsNone(actual["probability_a"])
        self.assertEqual(actual["excluded_sources"], ["fixture-book"])

    def test_output_finite_and_complementary(self):
        for a, b in ((1.01, 100), (2.13, 1.7), (20, 1.03), (2.2, 2.2)):
            actual = no_vig(a, b)
            self.assertAlmostEqual(actual["probability_a"] + actual["probability_b"], 1)
            self.assertTrue(all(math.isfinite(value) for value in actual.values()))


if __name__ == "__main__":
    unittest.main()
