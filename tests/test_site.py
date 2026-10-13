"""Offline site/link checks. Synthetic fixtures stay inside temporary folders."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_site import build
from scripts.validate import ValidationError, validate_site

REPO = "https://github.com/buffedlizard55-lab/MaltaProj1"


class SiteTests(unittest.TestCase):
    def snapshot(self):
        return {
            "schema_version": 1, "generated_at": "2026-10-13T18:00:00Z",
            "matches": [], "inventory": [], "quotes": [], "evidence": [],
            "sources": [{"id": "hotspawn", "name": "Hotspawn Play", "url": "https://play.hotspawn.com/lobby", "status": "unverified"}],
            "findings": [{"id": "synthetic-test-finding", "category": "Unit test", "title": "Synthetic fixture, never production", "detail": "<script>window.shouldNotRun=1</script>", "source_urls": [{"url": REPO, "label": "Official repository"}]}],
            "coverage": {"status": "unavailable", "observed_at": None},
            "verification": {"checks": []},
        }

    def build_snapshot(self, temp, data=None):
        temp = Path(temp)
        source = temp / "snapshot.json"
        source.write_text(json.dumps(data or self.snapshot()))
        out = temp / "dashboard"
        build(source, out)
        return out

    def test_all_category_pages_and_links_work_with_empty_unknown_data(self):
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_snapshot(temp)
            result = validate_site(out)
            self.assertEqual(result["pages"], 11)
            self.assertEqual(result["rows_without_official_source"], 0)
            for name in ("index", "matches", "cs2", "lol", "inventory", "markets", "sources", "flagged", "methodology", "repository"):
                self.assertTrue((out / f"{name}.html").is_file())
            self.assertIn('data-view="matches"', (out / "matches.html").read_text())
            self.assertNotIn('class="sort"', (out / "index.html").read_text())

    def test_untrusted_source_strings_are_escaped(self):
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_snapshot(temp)
            page = (out / "flagged.html").read_text()
            self.assertNotIn('<script>window.shouldNotRun', page)
            self.assertIn('&lt;script&gt;window.shouldNotRun', page)

    def test_internal_broken_link_blocks_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_snapshot(temp)
            (out / "inventory.html").unlink()
            with self.assertRaises(ValidationError):
                validate_site(out)

    def test_data_row_without_official_source_blocks_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            out = self.build_snapshot(temp)
            file = out / "sources.html"
            file.write_text(file.read_text().replace('</tbody>', '<tr><td>Synthetic unlinked row</td></tr></tbody>', 1))
            with self.assertRaises(ValidationError):
                validate_site(out)


if __name__ == "__main__":
    unittest.main()
