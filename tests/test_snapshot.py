import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_site import check_site
from validate_snapshot import validate_snapshot


class SnapshotAndSiteTests(unittest.TestCase):
    def test_checked_in_snapshot_passes_validation(self):
        snapshot = json.loads((ROOT / "site" / "data" / "snapshot.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_snapshot(snapshot), [])

    def test_every_seed_fixture_has_an_official_source_link(self):
        snapshot = json.loads((ROOT / "site" / "data" / "snapshot.json").read_text(encoding="utf-8"))
        for row in snapshot["matches"]:
            with self.subTest(row=row["id"]):
                self.assertTrue(row["sources"]["fixtureUrl"].startswith("https://www.hotspawn.com/matches/"))

    def test_missing_sportsbook_value_without_flag_fails_closed(self):
        snapshot = json.loads((ROOT / "site" / "data" / "snapshot.json").read_text(encoding="utf-8"))
        row = next(item for item in snapshot["matches"] if item["bookmaker"] is None)
        row["flags"] = []
        self.assertTrue(any("missing sportsbook value" in error for error in validate_snapshot(snapshot)))

    def test_static_site_routes_and_assets_are_intact(self):
        self.assertEqual(check_site(ROOT / "site"), [])


if __name__ == "__main__":
    unittest.main()
