"""Tests for the mobile executive summary (session arena/20d753a2).

Run:  python3 -m unittest tests.test_20d753a2
"""
import csv
import json
import pathlib
import re
import subprocess
import sys
import unittest
from html.parser import HTMLParser
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parent.parent
SUMMARY = ROOT / "summary"
UNRESOLVED_IDS = {"1081112", "1081113", "1079624", "1081120"}
PAGES = ["index.html", "picks.html", "unresolved.html", "flagged.html", "sources.html"]


class _Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
        self.ids = set()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "id" in d:
            self.ids.add(d["id"])
        if tag == "a" and d.get("href"):
            self.hrefs.append(d["href"])


class SummaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # rebuild so the tests always check the committed generator output
        subprocess.run([sys.executable, str(ROOT / "scripts" / "summary_build.py")], check=True,
                       cwd=str(ROOT), capture_output=True)
        cls.data = json.loads((SUMMARY / "data" / "picks.json").read_text(encoding="utf-8"))
        cls.rows = cls.data["rows"]

    def test_every_open_match_has_a_pick_and_both_probabilities(self):
        self.assertEqual(len(self.rows), 28)
        for r in self.rows:
            self.assertIn(r["pick"], (r["team_a"], r["team_b"]), r["fixture_id"])
            self.assertIsNotNone(r["prob_a_pct"], r["fixture_id"])
            self.assertIsNotNone(r["prob_b_pct"], r["fixture_id"])
            self.assertAlmostEqual(r["prob_a_pct"] + r["prob_b_pct"], 100, delta=0.2, msg=r["fixture_id"])
            side = r["prob_a_pct"] if r["pick"] == r["team_a"] else r["prob_b_pct"]
            self.assertAlmostEqual(side, r["pick_pct"], delta=0.05, msg=r["fixture_id"])

    def test_every_row_has_a_source_link(self):
        for r in self.rows:
            urls = [r["market_url"], r["pick_source_url"], r["hltv_match_url"], r["hotspawn_lobby_url"]]
            self.assertTrue(any(urls), r["fixture_id"])

    def test_unresolved_section_is_exactly_the_rows_without_a_market(self):
        got = {r["fixture_id"] for r in self.rows if r["unresolved"]}
        self.assertEqual(got, UNRESOLVED_IDS)
        for r in self.rows:
            if r["unresolved"]:
                self.assertEqual(r["basis_kind"], "own")
                self.assertTrue(r["unresolved_limits"], r["fixture_id"])
            else:
                self.assertIn(r["basis_kind"], ("primary", "aggregator"))

    def test_hotspawn_crowd_percentages_are_never_shown_or_read(self):
        for page in PAGES:
            text = (SUMMARY / page).read_text(encoding="utf-8")
            self.assertNotIn("picked", text.lower(), page)
        src = (ROOT / "scripts" / "summary_build.py").read_text(encoding="utf-8")
        self.assertNotIn("% picked", src)

    def test_coverage_matches_lobby_capture(self):
        cov = json.loads((SUMMARY / "data" / "coverage.json").read_text(encoding="utf-8"))
        self.assertEqual(cov["lobby_cards"], 28)
        self.assertEqual(cov["matched"], 28)
        self.assertEqual(cov["stats"]["with_pick"], 28)

    def test_csv_matches_json(self):
        with open(SUMMARY / "data" / "picks.csv", newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual({r["fixture_id"] for r in rows}, {r["fixture_id"] for r in self.rows})

    def test_pages_exist_and_all_local_links_resolve(self):
        pages = {}
        for page in PAGES:
            path = SUMMARY / page
            self.assertTrue(path.exists(), page)
            c = _Collect()
            c.feed(path.read_text(encoding="utf-8"))
            pages[page] = c
        for page, c in pages.items():
            for href in c.hrefs:
                u = urlparse(href)
                if u.scheme or href.startswith("mailto:"):
                    continue
                target_path, frag = u.path, u.fragment
                if not target_path:
                    target = SUMMARY / page
                else:
                    target = (SUMMARY / target_path).resolve()
                if target_path and target_path.startswith(".."):
                    self.assertTrue(target.exists(), f"{page}: {href}")
                    continue
                self.assertTrue(target.exists(), f"{page}: missing {href}")
                if frag and target.suffix == ".html":
                    tgt_ids = pages[target.name].ids if target.name in pages else _ids(target)
                    self.assertIn(frag, tgt_ids, f"{page}: anchor {href}")

    def test_summary_links_to_every_section(self):
        text = (SUMMARY / "index.html").read_text(encoding="utf-8")
        for needle in ["picks.html", "unresolved.html", "flagged.html", "sources.html", "#at-a-glance"]:
            self.assertIn(needle, text)
        self.assertIn("Unresolved", text)

    def test_mobile_viewport_and_single_column_layout(self):
        for page in PAGES:
            text = (SUMMARY / page).read_text(encoding="utf-8")
            self.assertIn('name="viewport" content="width=device-width,initial-scale=1"', text, page)
        css = (SUMMARY / "style.css").read_text(encoding="utf-8")
        self.assertIn("max-width:720px", css)

    def test_root_landing_links_to_summary(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="summary/index.html"', text)


def _ids(path):
    c = _Collect()
    c.feed(path.read_text(encoding="utf-8"))
    return c.ids


if __name__ == "__main__":
    unittest.main()
