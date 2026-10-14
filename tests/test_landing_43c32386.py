"""Regression tests for landing integration; no external-source verification is claimed."""
import subprocess
import unittest
from pathlib import Path
from html.parser import HTMLParser
ROOT = Path(__file__).resolve().parent.parent

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            self.ids.append(attrs['id'])
        if tag == 'a' and 'href' in attrs:
            self.links.append(attrs['href'])

class LandingTests(unittest.TestCase):
    def test_evidence_renderer(self):
        result = subprocess.run(['node', 'tests/landing_43c32386.cjs'], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_accessibility_and_local_links(self):
        text = (ROOT / 'index.html').read_text()
        parser = PageParser()
        parser.feed(text)
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        for href in parser.links:
            if '://' in href or href.startswith(('#','mailto:')):
                continue
            path = ROOT / href.split('#')[0].split('?')[0]
            self.assertTrue(path.exists(), href)
        for required in ['name="viewport"','class="skip"','<noscript>','for="match-search"','aria-live="polite"']:
            self.assertIn(required,text)
        self.assertNotIn('All 28 open CS2 picks — one per match →', text.split('<details class="archive">')[0])

if __name__ == '__main__':
    unittest.main()
