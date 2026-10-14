"""Acceptance checks for the root landing and its verified executive snapshot feed."""
import json
import math
import re
import unittest
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


class LandingAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "index.html").read_text(encoding="utf-8")
        cls.analysis = json.loads((ROOT / "executive/data/analysis.json").read_text(encoding="utf-8"))
        cls.summary = json.loads((ROOT / "executive/data/summary.json").read_text(encoding="utf-8"))

    def test_one_verified_primary_board_and_research_navigation(self):
        self.assertEqual(len(re.findall(r"<h1\b", self.html, re.I)), 1)
        first_quick_link = self.html.split('<div class="quick-links"', 1)[1].split("</div>", 1)[0]
        self.assertIn('href="executive/picks.html"', first_quick_link)
        self.assertIn('href="executive/unresolved.html"', first_quick_link)
        self.assertIn('href="executive/own-lines.html"', first_quick_link)
        for path in (
            "executive/picks.html",
            "executive/unresolved.html",
            "executive/own-lines.html",
            "executive/lines.html",
            "executive/sources.html",
            "executive/methodology.html",
            "executive/flagged.html",
            "executive/coverage.html",
            "executive/cadence.html",
            "reviews/6f9eab3b-acceptance.html",
        ):
            self.assertIn(f'href="{path}"', self.html)
        self.assertIn("Other dashboards &amp; historical research", self.html)
        self.assertIn("newer parallel board has a broken Valve source link", self.html)
        self.assertIn('href="livelines/picks.html"', self.html)  # archive only
        archive_position = self.html.index('<details class="archive">')
        self.assertGreater(self.html.index('href="livelines/picks.html"'), archive_position)

    def test_summary_counts_match_captured_open_rows(self):
        data = self.analysis
        summary = self.summary
        coverage = summary["coverage"]
        fixtures = data["fixtures"]
        capture = data["meta"]["capture_utc"]
        self.assertEqual(data["capture_utc"], capture)
        self.assertEqual(summary["meta"]["capture_utc"], capture)
        open_rows = [row for row in fixtures.values() if row.get("status") == "open"]
        self.assertEqual(len(fixtures), coverage["total_fixtures"])
        self.assertEqual(len(open_rows), coverage["open_fixtures"])
        picked = [row for row in open_rows if isinstance(row.get("pick"), str) and row["pick"].strip()]
        self.assertEqual(len(picked), coverage["open_with_pick"])
        self.assertEqual(len(open_rows) - len(picked), coverage["open_no_pick"])
        self.assertEqual(
            sum(str(row.get("basis_label", "")).startswith("Market ·") for row in picked),
            coverage["open_market_basis"]
        )
        self.assertEqual(
            sum(str(row.get("basis_label", "")).startswith("Model ·") for row in picked),
            coverage["open_model_basis"],
        )
        for row in open_rows:
            self.assertTrue(row.get("pick"), row.get("match_id"))
            a, b = float(row["prob_a_pct"]), float(row["prob_b_pct"])
            self.assertTrue(math.isfinite(a) and math.isfinite(b), row.get("match_id"))
            self.assertAlmostEqual(a + b, 100.0, delta=0.2, msg=row.get("match_id"))
            self.assertTrue(row.get("basis_sources"), row.get("match_id"))
            for link, _label in row["basis_sources"]:
                parsed = urlsplit(link)
                self.assertEqual(parsed.scheme, "https", (row.get("match_id"), link))
                self.assertTrue(parsed.netloc, (row.get("match_id"), link))
            self.assertTrue(row.get("hotspawn_pickem_url", "").startswith("https://play.hotspawn.com/"))
        self.assertEqual(coverage["open_with_pick"] + coverage["open_no_pick"], coverage["open_fixtures"])

    def test_mobile_accessible_actions_and_honest_freshness(self):
        self.assertIn('name="viewport"', self.html)
        self.assertIn('href="#main"', self.html)
        self.assertIn('id="main"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("min-height: 44px", self.html)
        self.assertIn("@media (max-width: 520px)", self.html)
        self.assertIn('role="status"', self.html)
        self.assertIn('fetch(url, { cache: "no-store"', self.html)
        self.assertIn('window.setInterval(loadSummary, 15 * 60000)', self.html)
        self.assertIn("Date.now() - Date.parse(value)", self.html)
        self.assertIn("beyond the requested 4–8 hour update window", self.html)
        self.assertIn("GitHub Actions refreshes are scheduled every four hours but run best-effort", self.html)
        self.assertIn("Hotspawn crowd-pick percentages are never probability inputs", self.html)
        self.assertNotIn("All 28 open", self.html)
        self.assertNotIn("0.0 h old", self.html)
        self.assertIn('var url = "executive/data/summary.json?published=" + Date.now()', self.html)
        self.assertNotIn('fetch("livelines/data/picks.json', self.html)

    def test_local_landing_links_resolve(self):
        from html.parser import HTMLParser

        class LinkParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    attrs = dict(attrs)
                    if "href" in attrs:
                        self.links.append(attrs["href"])

        parser = LinkParser()
        parser.feed(self.html)
        for href in parser.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or parsed.path.startswith(("mailto:", "tel:")):
                continue
            target = ROOT / (parsed.path or "index.html")
            self.assertTrue(target.exists(), href)


if __name__ == "__main__":
    unittest.main()
