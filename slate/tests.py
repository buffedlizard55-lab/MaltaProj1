#!/usr/bin/env python3
"""Offline unit tests for the slate/ data pipeline (no network required)."""
import csv, json, math, sys, unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))

import collect  # noqa: E402


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
        """No probability column may equal a Hotspawn crowd percentage."""
        fixtures = {}
        with (DATA / "fixtures.csv").open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                fixtures[row["fixture_id"]] = row
        for row in self.rows():
            fx = fixtures.get(row["fixture_id"])
            if not fx:
                continue
            for pct_key in ("crowd_pct_a_audit_only", "crowd_pct_b_audit_only"):
                if not fx.get(pct_key):
                    continue
                pct = float(fx[pct_key])
                for col in ("market_p_a_pct", "own_p_a_pct", "consensus_p_a_pct"):
                    if row.get(col):
                        self.assertNotEqual(round(float(row[col]), 6), round(pct, 6),
                                            f"{row['fixture_id']} {col} equals crowd {pct_key}")

    def test_provenance_exists_for_every_downloaded_source(self):
        prov = json.loads((DATA / "provenance.json").read_text(encoding="utf-8"))
        self.assertTrue(prov["fetches"], "provenance log is empty")
        for entry in prov["fetches"]:
            self.assertTrue(entry.get("url"))
            self.assertIn(entry.get("path"), ("http", "browser"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
