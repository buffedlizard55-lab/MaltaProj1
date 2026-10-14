#!/usr/bin/env python3
"""tests/test_5545dbb8.py — repository test discovery entry point for the executive board.

Runs the executive board's own invariant suite (executive/tests.py) as a unittest, so the repository's
``python -m unittest discover -s tests`` covers this session's output too. No network access is needed:
the suite only reads what collect.py/build.py already stored under executive/data/.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "executive" / "tests.py"


class ExecutiveBoardTests(unittest.TestCase):
    maxDiff = None

    def test_executive_invariants(self):
        self.assertTrue(SUITE.exists(), "executive/tests.py is missing")
        run = subprocess.run([sys.executable, str(SUITE)], capture_output=True, text=True,
                             cwd=str(ROOT))
        try:
            payload = json.loads(run.stdout)
        except json.JSONDecodeError:
            self.fail(f"executive/tests.py produced no JSON.\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}")
        self.assertEqual(payload["failures"], [], f"executive invariants failed: {payload['failures']}")
        self.assertGreaterEqual(payload["passed"], 10, "suspiciously few checks ran")
        self.assertEqual(run.returncode, 0, "executive/tests.py exited non-zero")

    def test_pages_exist_and_are_mobile_ready(self):
        for name in ("index.html", "picks.html", "flagged.html", "methodology.html", "sources.html",
                     "lines.html", "own-lines.html", "coverage.html", "verification.html",
                     "tournaments.html"):
            page = ROOT / "executive" / name
            self.assertTrue(page.exists(), f"{name} missing")
            text = page.read_text(encoding="utf-8")
            self.assertIn('name="viewport"', text, f"{name} has no mobile viewport meta")
            self.assertIn("style.css", text, f"{name} does not load the stylesheet")

    def test_no_third_party_requests_in_pages(self):
        for page in sorted((ROOT / "executive").glob("*.html")):
            text = page.read_text(encoding="utf-8")
            for pattern in ("http://", "cdn.", "<iframe"):
                self.assertNotIn(pattern, text, f"{page.name} contains {pattern}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
