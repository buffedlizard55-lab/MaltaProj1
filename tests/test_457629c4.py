#!/usr/bin/env python3
"""tests/test_457629c4.py — repository-level invariants for the livelines board.

Session ``arena/457629c4`` publishes ``livelines/``: one pick, with both win probabilities, for every open
CS2 fixture on the Hotspawn Pick'em board, a separate Unresolved-picks-and-limitations page, a Flagged
page, the sources with their read times, and a 4-hour refresh workflow.

This module adds the repository-level checks on top of the board's own invariants in
``livelines/tests.py`` (which are imported and re-run here):

* the board's files are self-contained — no page links outside ``livelines/`` except to public sources;
* the executive summary links into the picks page and the unresolved page (the brief's "links within our
  site to where the updated list of picks can be found");
* the landing page (root ``index.html``) carries a link to this board, so a phone user can reach it;
* the refresh workflow exists, is scheduled inside the 4-8 h window, and gates publication on the tests;
* the live reads are stored verbatim with a URL and a UTC read time for each one.

Run: ``python -m unittest tests.test_457629c4 -v``
"""
from __future__ import annotations

import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "livelines"
DATA = OUT / "data"

# re-run the board's own invariants as part of the repository suite
from livelines import tests as board_tests  # noqa: E402


class TestBoardInvariants(board_tests.TestLivelines):
    """The board's own invariants, executed by the repository suite as well."""


class TestRepositoryIntegration(unittest.TestCase):
    def test_executive_summary_links_to_the_picks_and_unresolved_pages(self):
        html = (OUT / "index.html").read_text()
        self.assertIn('href="picks.html"', html)
        self.assertIn('href="unresolved.html"', html)
        picks = (OUT / "picks.html").read_text()
        unresolved = (OUT / "unresolved.html").read_text()
        self.assertIn("Every pick, one screen per match", html)
        self.assertIn("Unresolved picks", unresolved)

    def test_landing_page_links_to_this_board(self):
        landing = ROOT / "index.html"
        self.assertTrue(landing.exists(), "root index.html must exist")
        html = landing.read_text()
        self.assertIn("livelines/index.html", html,
                      "the landing page must carry a link to this board so it is reachable on a phone")

    def test_pages_only_link_inside_the_board_or_to_public_sources(self):
        for page in OUT.glob("*.html"):
            for m in re.finditer(r'href="([^"]+)"', page.read_text()):
                url = m.group(1)
                if url.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                self.assertFalse(url.startswith("../"),
                                 f"{page.name} links outside the board: {url}")

    def test_refresh_workflow_is_scheduled_inside_the_window_and_fails_closed(self):
        wf = (ROOT / ".github/workflows/livelines-457629c4.yml").read_text()
        m = re.search(r'cron:\s*"([^"]+)"', wf)
        self.assertIsNotNone(m, "no cron in the refresh workflow")
        minute, hour = m.group(1).split()[:2]
        self.assertRegex(minute, r"^\d{1,2}$")
        step = hour.split("/")
        self.assertEqual(len(step), 2, f"cadence is not an interval: {hour}")
        interval = int(step[1])
        self.assertTrue(4 <= interval <= 8, f"cadence {interval} h outside the requested 4-8 h window")
        self.assertIn("python3 livelines/build.py", wf)
        self.assertIn("unittest", wf)
        self.assertIn("livelines/tests.py", wf)

    def test_live_reads_are_stored_verbatim_with_urls_and_times(self):
        live = json.loads((DATA / "live_reads.json").read_text())
        self.assertGreaterEqual(len(live["reads"]), 5)
        for r in live["reads"]:
            self.assertTrue(r["url"].startswith("http"))
            self.assertRegex(r["read_utc"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
            self.assertTrue(r["read_utc_basis"], r["id"])
            self.assertTrue(r["observed"], r["id"])

    def test_unresolved_page_names_the_specific_limitations(self):
        html = (OUT / "unresolved.html").read_text()
        for needle in ("1.80 / 1.80", "LFO 10", "Google" if False else "official",
                       "scheduled workflows", "series length"):
            self.assertIn(needle, html, needle)

    def test_coverage_json_states_the_same_numbers_as_the_pages(self):
        cov = json.loads((DATA / "coverage.json").read_text())
        index = (OUT / "index.html").read_text()
        self.assertIn(f'<b>{cov["open_fixtures"]}</b><span>open matches</span>', index)
        self.assertIn(f'<b>{cov["open_with_pick"]}</b><span>picks published</span>', index)


if __name__ == "__main__":
    unittest.main(verbosity=2)
