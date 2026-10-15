"""Scoped regression checks for the current-picks integration (no network access)."""
from __future__ import annotations

import subprocess
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.links: list[str] = []
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        self.tags.append((tag, values))
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "a" and values.get("href") is not None:
            self.links.append(values["href"] or "")


class LandingIntegrationTests(unittest.TestCase):
    def parse(self, path: str) -> tuple[str, PageParser]:
        text = (ROOT / path).read_text(encoding="utf-8")
        parser = PageParser()
        parser.feed(text)
        return text, parser

    def assert_local_links_resolve(self, page: str, parser: PageParser) -> None:
        local_ids = set(parser.ids)
        for href in parser.links:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc or href.startswith("mailto:"):
                continue
            if not parts.path:
                self.assertIn(parts.fragment, local_ids, f"{page}: broken fragment {href}")
                continue
            target = (ROOT / parts.path.split("?")[0]).resolve()
            self.assertTrue(target.exists(), f"{page}: missing local link {href}")
            if parts.fragment and target in {ROOT / "index.html", ROOT / "current-picks.html"}:
                _, destination = self.parse(target.relative_to(ROOT).as_posix())
                self.assertIn(parts.fragment, destination.ids, f"{page}: missing local anchor {href}")

    def test_node_evidence_regressions(self) -> None:
        check = subprocess.run(["node", "--check", "js/262b4d3b-picks.js"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
        run = subprocess.run(["node", "tests/262b4d3b-picks.cjs"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_root_has_one_clear_current_route_and_a_one_tap_review_route(self) -> None:
        text, parser = self.parse("index.html")
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "root IDs must be unique")
        primary = [attrs for tag, attrs in parser.tags if tag == "a" and attrs.get("id") == "primary-picks"]
        self.assertEqual(len(primary), 1)
        self.assertEqual(primary[0].get("href"), "current-picks.html")
        self.assertIn('href="current-picks.html#unresolved"', text)
        self.assertIn('href="live/flagged.html"', text)
        self.assertIn('id="landing-status"', text)
        self.assertIn('aria-live="polite"', text)
        self.assertIn('href="#matches"', text)
        self.assertIn('id="matches"', text)
        self.assertIn('id="archive"', text)
        self.assertIn('id="match-search"', text)
        self.assertIn('action="current-picks.html"', text)
        self.assertNotIn("All 28 open CS2 picks — one per match →", text.split('<details class="archive"', 1)[0])
        self.assertIn("84.6% / 15.4%", text)
        self.assertIn("Map 1", text)
        self.assert_local_links_resolve("index.html", parser)

    def test_phone_first_current_view_and_unresolved_evidence(self) -> None:
        text, parser = self.parse("current-picks.html")
        self.assertEqual(len(parser.ids), len(set(parser.ids)), "current-picks IDs must be unique")
        for required in (
            'name="viewport"', 'class="skip"', 'id="pick-list"', 'id="pick-search"',
            'id="tier-filter"', 'id="unresolved"', 'id="unresolved-list"', '<noscript>',
            'aria-live="polite"', 'max-width:560px',
        ):
            self.assertIn(required, text)
        self.assertIn("Both probabilities are intentionally blank.", text)
        self.assertIn("not sufficient to transfer the price", text)
        self.assertIn("Polymarket", text)
        self.assert_local_links_resolve("current-picks.html", parser)

    def test_current_page_uses_the_fresh_fixture_spine_only(self) -> None:
        script = (ROOT / "js/262b4d3b-picks.js").read_text(encoding="utf-8")
        self.assertIn("live/data/slate.csv", script)
        self.assertIn("live/data/snapshot_meta.json", script)
        self.assertIn("exec/data/picks.json", script)
        self.assertNotIn("live/data/snapshot.json", script)
        self.assertNotIn("slate/data/fixtures.csv", script)
        self.assertIn("exact fixture ID", (ROOT / "current-picks.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
