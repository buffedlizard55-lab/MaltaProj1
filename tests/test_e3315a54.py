from __future__ import annotations

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "e3315a54"
MOBILE = ROOT / "mobile"


class E3315A54PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        def load_csv(path):
            with path.open(encoding="utf-8", newline="") as handle:
                return list(csv.DictReader(handle))
        cls.current = load_csv(DATA / "current.csv")
        cls.stale = load_csv(DATA / "stale.csv")
        cls.flags = load_csv(DATA / "flags.csv")
        cls.snapshot = json.loads((DATA / "snapshot.json").read_text(encoding="utf-8"))

    def test_coverage_and_unique_fixture_ids(self):
        self.assertEqual(len(self.current), 32)
        self.assertEqual(len(self.stale), 59)
        self.assertEqual(len(self.current) + len(self.stale), 91)
        codes = [r["code"] for r in self.current + self.stale]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertEqual(self.snapshot["coverage"]["total_cs2"], 91)

    def test_no_crowd_probability_input_is_published(self):
        for row in self.current + self.stale:
            self.assertFalse(any("crowd" in key.lower() for key in row))
            self.assertNotIn("picked", row.get("notes", "").lower())
            self.assertNotIn("crowd", row.get("notes", "").lower())
            self.assertNotIn("crowd", row.get("status_note", "").lower())
        self.assertFalse(self.snapshot["crowd_percentages_used"])

    def test_probability_pairs_are_normalized(self):
        for row in self.current:
            if row["market_p_a"]:
                self.assertAlmostEqual(float(row["market_p_a"]) + float(row["market_p_b"]), 100.0, places=1)
            if row["own_p_a"]:
                self.assertAlmostEqual(float(row["own_p_a"]) + float(row["own_p_b"]), 100.0, places=1)

    def test_picks_have_a_calculation_and_started_rows_are_suppressed(self):
        for row in self.current:
            if row["actionable"] == "yes":
                if row["pick"]:
                    self.assertTrue(row["market_p_a"] or row["own_p_a"])
                    self.assertIn(row["pick"], (row["team_a"], row["team_b"]))
            else:
                self.assertEqual(row["pick"], "")
        self.assertEqual({r["match_status"] for r in self.current if r["code"] in {"H-00", "H-01"}}, {"completed_not_actionable", "live_not_actionable"})

    def test_every_row_has_at_least_one_official_source_link(self):
        payload = self.snapshot
        for row in payload["current"] + payload["stale"]:
            links = row.get("source_links", [])
            self.assertTrue(links, row["code"])
            self.assertTrue(all(str(url).startswith("https://") for _, url in links), row["code"])

    def test_source_hosts_are_expected(self):
        allowed = ("hotspawn.com", "hltv.org", "github.com", "egamersworld.com", "pinnacle.com")
        for row in self.snapshot["current"] + self.snapshot["stale"]:
            for _, url in row.get("source_links", []):
                self.assertTrue(any(host in url for host in allowed), url)

    def test_internal_mobile_links_resolve(self):
        for page in MOBILE.glob("*.html"):
            text = page.read_text(encoding="utf-8")
            for href in re.findall(r'href=["\']([^"\'#?]+)', text):
                if href.startswith(("http:", "https:", "mailto:", "javascript:")):
                    continue
                target = (page.parent / href).resolve()
                self.assertTrue(target.exists(), f"{page}: {href}")

    def test_flags_are_source_linked(self):
        self.assertGreater(len(self.flags), 0)
        for flag in self.flags:
            links = json.loads(flag["source_links"])
            self.assertTrue(links, flag["flag_id"])
            self.assertTrue(all(len(link) == 2 and link[1].startswith("https://") for link in links))


if __name__ == "__main__":
    unittest.main()
