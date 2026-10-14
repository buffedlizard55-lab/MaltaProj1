"""Regression tests for the shared landing page; no live-source verification is claimed."""
import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.headings = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "a" and "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "h1":
            self.headings.append("h1")


class LandingTests(unittest.TestCase):
    def test_evidence_renderer(self):
        result = subprocess.run(
            ["node", "tests/landing_43c32386.cjs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accessibility_and_local_links(self):
        text = (ROOT / "index.html").read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "duplicate element IDs")
        self.assertEqual(len(parser.headings), 1, "the landing page should have one h1")

        for href in parser.links:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or parsed.path.startswith(("mailto:", "tel:")):
                continue
            path = ROOT / (parsed.path or "index.html")
            self.assertTrue(path.exists(), href)
            if parsed.fragment and not parsed.path:
                self.assertIn(parsed.fragment, parser.ids, href)

        for required in [
            'name="viewport"',
            'class="skip"',
            'href="#main"',
            'id="main"',
            "<noscript>",
            'role="status"',
            'aria-live="polite"',
            'aria-label="Primary navigation"',
            'href="executive/picks.html"',
            'href="executive/unresolved.html"',
            'href="reviews/6f9eab3b-acceptance.html"',
            'href="livelines/index.html"',
            'href="livelines/unresolved.html"',
            'href="fullpicks/index.html"',
            'href="fullpicks/unresolved.html"',
            'href="fullpicks/data/fullpicks_board.csv"',
            'href="dashboard/"',
            'href="docs/audit.html"',
            'href="slate/data/analysis.csv"',
            'href="reviews/43c32386.html"',
            'class="archive"',
        ]:
            self.assertIn(required, text)
        self.assertIn("prefers-reduced-motion", (ROOT / "css/landing.css").read_text())
        self.assertIn("executive/data/summary.json", text)
        self.assertIn("Newer live-read board — flagged pending correction", text)

        # The user sees one picks board before the disclosure; alternatives stay archived.
        visible_landing = text.split('<details class="archive">', 1)[0]
        self.assertNotIn('href="livelines/picks.html"', visible_landing)
        self.assertNotIn('href="briefing/index.html"', visible_landing)
        self.assertNotIn("Other current boards", visible_landing)
        self.assertNotIn("All 28 open CS2 picks", visible_landing)


if __name__ == "__main__":
    unittest.main()
