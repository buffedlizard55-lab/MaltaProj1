#!/usr/bin/env python3
"""Offline unit tests for the slate/ data pipeline (no network required)."""
import csv, json, math, sys, unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))

import collect  # noqa: E402
import guards


class SeriesMath(unittest.TestCase):
    def test_devig_sums_to_one(self):
        pa, pb, margin = collect.devig(1.5, 2.6)
        self.assertAlmostEqual(pa + pb, 1.0, places=9)
        self.assertGreater(margin, 0)

    def test_devig_ignores_margin(self):
        pa, _, _ = collect.devig(2.0, 2.0)
        self.assertAlmostEqual(pa, 0.5, places=9)

    def test_series_bo3_identity_at_half(self):
        self.assertAlmostEqual(collect.series_from_map(0.5, 3), 0.5, places=9)

    def test_series_bo3_monotone(self):
        self.assertLess(collect.series_from_map(0.4, 3), collect.series_from_map(0.55, 3))
        self.assertGreater(collect.series_from_map(0.9, 3), 0.9)

    def test_series_bo5_bounds(self):
        for p in (0.05, 0.3, 0.5, 0.77, 0.95):
            v = collect.series_from_map(p, 5)
            self.assertGreaterEqual(round(v, 9), 0.0)
            self.assertLessEqual(round(v, 9), 1.0)
        self.assertAlmostEqual(collect.series_from_map(0.5, 5), 0.5, places=9)

    def test_bo1_identity(self):
        self.assertAlmostEqual(collect.series_from_map(0.37, 1), 0.37, places=12)

    def test_elo_symmetry(self):
        a = collect.elo_p(1000, 900)
        b = collect.elo_p(900, 1000)
        self.assertAlmostEqual(a + b, 1.0, places=9)
        self.assertAlmostEqual(collect.elo_p(1000, 1000), 0.5, places=12)


class DataInvariants(unittest.TestCase):
    """Runs only when a capture has already been committed."""

    def setUp(self):
        if not (DATA / "analysis.csv").exists() or (DATA / "analysis.csv").stat().st_size == 0:
            self.skipTest("no committed capture to check")

    def rows(self):
        with (DATA / "analysis.csv").open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def test_never_more_than_100_percent(self):
        for row in self.rows():
            for key in ("market_p_a_pct", "market_p_b_pct", "own_p_a_pct", "own_p_b_pct",
                        "own_series_p_a_pct", "own_series_p_b_pct", "consensus_p_a_pct",
                        "pick_pct"):
                if row.get(key):
                    value = float(row[key])
                    self.assertGreaterEqual(value, 0.0, f"{row['fixture_id']} {key}")
                    self.assertLessEqual(value, 100.0, f"{row['fixture_id']} {key}")

    def test_probabilities_complement(self):
        for row in self.rows():
            if row.get("market_p_a_pct") and row.get("market_p_b_pct"):
                self.assertAlmostEqual(float(row["market_p_a_pct"]) + float(row["market_p_b_pct"]),
                                       100.0, places=1)
            if row.get("own_p_a_pct") and row.get("own_p_b_pct"):
                self.assertAlmostEqual(float(row["own_p_a_pct"]) + float(row["own_p_b_pct"]),
                                       100.0, places=1)

    def test_pick_matches_consensus_side(self):
        for row in self.rows():
            if not row.get("pick"):
                continue
            self.assertIn(row["pick"], (row["team_a"], row["team_b"]))
            consensus = row.get("consensus_p_a_pct")
            if consensus:
                expected = row["team_a"] if float(consensus) >= 50 else row["team_b"]
                self.assertEqual(row["pick"], expected, row["fixture_id"])

    def test_every_row_carries_a_hotspawn_source(self):
        for row in self.rows():
            self.assertTrue(row.get("hotspawn_url"), row.get("fixture_id"))

    def test_times_are_utc_and_ordered(self):
        for row in self.rows():
            start = datetime.strptime(row["start_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            lock = datetime.strptime(row["lock_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            self.assertLess(lock, start, row["fixture_id"])

    def test_crowd_percentages_are_audit_only(self):
        # Coincidental equality (e.g. 50/50) is valid. Check dependency separation instead.
        source = (HERE / "collect.py").read_text()
        own_block = source.split("    def own_line(fx: dict)")[1].split("    own_lines =")[0]
        self.assertNotIn("crowd", own_block)
        self.assertNotIn("crowd", (HERE / "guards.py").read_text().split('from datetime')[1])

    def test_provenance_exists_for_every_downloaded_source(self):
        prov = json.loads((DATA / "provenance.json").read_text(encoding="utf-8"))
        self.assertTrue(prov["fetches"], "provenance log is empty")
        for entry in prov["fetches"]:
            self.assertTrue(entry.get("url"))
            self.assertIn(entry.get("path"), ("http", "browser"))


class StrictGuards(unittest.TestCase):
    def test_no_rating_leakage_between_sports(self):
        for row in DataInvariants().rows():
            if row['sport'] != 'cs2':
                for column in ('own_p_a_pct', 'own_series_p_a_pct', 'market_p_a_pct', 'pick'):
                    self.assertFalse(row.get(column), (row['fixture_id'], column))

    def test_unknown_schedule_not_open(self):
        self.assertNotEqual(collect.live_status({}, datetime.now(timezone.utc)), 'open')

    def test_exact_orientation(self):
        self.assertIs(guards.aligned_pair('NAVI', 'Vitality', 'Vitality', 'NAVI', collect.norm), True)
        self.assertIsNone(guards.aligned_pair('NAVI', 'Vitality', 'NAVI Junior', 'Vitality', collect.norm))
        self.assertIsNone(guards.aligned_pair('', 'Vitality', '', 'Vitality', collect.norm))

    def test_missing_kickoff_is_not_match(self):
        self.assertFalse(guards.kickoff_agrees('', '2026-10-14T10:00:00Z'))
        self.assertFalse(guards.kickoff_agrees('2026-10-14T10:00:00Z', '2026-10-14T16:00:00Z'))
        self.assertTrue(guards.kickoff_agrees('2026-10-14T10:00:00Z', '2026-10-14T10:05:00Z'))

    def test_hltv_parser_does_not_borrow_next_match_fields(self):
        html = '<a href="/matches/123/a-vs-b-event">first</a><a href="/matches/124/c-vs-d-event">' + '<div data-unix="1791972000000"><span class="team-name">CC</span><span class="team-name">DD</span>bo3</div>'
        rows = collect.parse_hltv_matches(html)
        self.assertNotIn('123', [r['hltv_match_id'] for r in rows])
        self.assertEqual([r['hltv_match_id'] for r in rows], ['124'])

    def test_primary_quote_age(self):
        now = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        row = dict(rank=0, book='Pinnacle', odds_a=1.5, odds_b=2.6, captured_utc='2026-10-14T09:00:00Z')
        self.assertTrue(guards.eligible_market(row, now))
        for bad in ('2026-10-13T09:00:00Z', '2026-10-14T11:00:00Z', '', '2026-10-14T09:00:00'):
            self.assertFalse(guards.eligible_market(dict(row, captured_utc=bad), now))
        self.assertFalse(guards.eligible_market(dict(row, rank=3), now))
        self.assertFalse(guards.eligible_market(dict(row, odds_a=float('nan')), now))
        self.assertFalse(guards.eligible_market(dict(row, book='EGamersWorld'), now))

    def test_market_preferred_without_arbitrary_blend(self):
        self.assertEqual(guards.pick_probability(60, 20, 3)[0], 60)
        self.assertIsNone(guards.pick_probability(None, 80, None)[0])
        self.assertEqual(guards.pick_probability(None, 80, 3)[0], 80)
        self.assertIsNone(collect.series_from_map(.7, None))

    def test_unknown_format_never_published_as_series(self):
        for row in DataInvariants().rows():
            if row.get('best_of') not in ('1', '3', '5'):
                self.assertFalse(row.get('own_series_p_a_pct'), row['fixture_id'])
                self.assertFalse(row.get('own_series_p_b_pct'), row['fixture_id'])
                self.assertFalse(row.get('pick') and not row.get('market_p_a_pct'), row['fixture_id'])

    def test_primary_market_provenance_and_math(self):
        with (DATA / 'lines.csv').open(encoding='utf-8') as fh:
            lines = list(csv.DictReader(fh))
        for row in DataInvariants().rows():
            if not row.get('market_p_a_pct'):
                continue
            self.assertEqual(row['market_book'], 'Pinnacle')
            candidates = [q for q in lines if q['fixture_id'] == row['fixture_id'] and q['captured_utc'] == row['market_captured_utc'] and q['book'] == 'Pinnacle']
            self.assertTrue(candidates, row['fixture_id'])
            quote = candidates[0]
            a, b, _ = collect.devig(float(row['market_odds_a']), float(row['market_odds_b']))
            self.assertAlmostEqual(a * 100, float(row['market_p_a_pct']), delta=.06)
            self.assertAlmostEqual(b * 100, float(row['market_p_b_pct']), delta=.06)
            self.assertTrue(row['market_url'].startswith('https://www.pinnacle.com/'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
