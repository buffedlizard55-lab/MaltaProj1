"""Session arena/c13ca42a — tests for the full-coverage pick'em board (C-02/C-04/C-06).

Covers the verification invariants that must hold for the published board:
  * the canonical 88-fixture set (28 open + 60 stale) is fully joined,
  * every stale fixture has exactly one result row, and verified rows carry a
    winner that is one of the two card teams, a score, and an https source link,
  * unresolved rows carry NO winner/score (never fabricated) and a flag,
  * the generated board CSV and both HTML pages contain every fixture,
  * the C-02 research record (stale_result_rows.py) is internally consistent.
"""

import csv
import importlib.util
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "data", "c13ca42a"))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestC13ca42aData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = list(csv.DictReader(open(os.path.join(ROOT, "executive", "data", "analysis.csv"), newline="", encoding="utf-8")))
        cls.stale_fx = list(csv.DictReader(open(os.path.join(ROOT, "fullpicks", "data", "stale_fixtures_from_executive.csv"), newline="", encoding="utf-8")))
        cls.results = list(csv.DictReader(open(os.path.join(ROOT, "fullpicks", "data", "stale_results.csv"), newline="", encoding="utf-8")))
        cls.board = list(csv.DictReader(open(os.path.join(ROOT, "fullpicks", "data", "fullpicks_board.csv"), newline="", encoding="utf-8")))
        srr = load_module("stale_result_rows_c13", os.path.join(ROOT, "data", "c13ca42a", "stale_result_rows.py"))
        cls.srr_rows = srr.ROWS
        cls.index_html = open(os.path.join(ROOT, "fullpicks", "index.html"), encoding="utf-8").read()
        cls.unres_html = open(os.path.join(ROOT, "fullpicks", "unresolved.html"), encoding="utf-8").read()

    def test_fixture_counts(self):
        self.assertEqual(len(self.analysis), 88)
        self.assertEqual(len(self.stale_fx), 60)
        self.assertEqual(len(self.results), 60)
        self.assertEqual(len(self.board), 88)
        self.assertEqual(len({r["match_id"] for r in self.analysis}), 88)

    def test_status_split(self):
        from collections import Counter
        self.assertEqual(Counter(r["status"] for r in self.analysis), {"locked": 60, "open": 28})
        self.assertEqual(Counter(r["group"] for r in self.board), {"open": 28, "played": 54, "unresolved": 6})
        self.assertEqual(Counter(r["status"] for r in self.results), {"verified": 54, "unresolved": 6})

    def test_join_integrity(self):
        fx = {r["match_id"]: r for r in self.stale_fx}
        for r in self.results:
            f = fx[r["match_id"]]
            self.assertEqual(r["team_a"], f["team_a"])
            self.assertEqual(r["team_b"], f["team_b"])
            self.assertEqual(r["card_start_utc"], f["start_utc"])
            self.assertEqual(r["tournament"], f["tournament"])

    def test_research_rows_match_csv(self):
        self.assertEqual(len(self.srr_rows), 60)
        by_id = {r["match_id"]: r for r in self.results}
        for mid, status, winner, score, fmt, rdate, url, flag in self.srr_rows:
            r = by_id[mid]
            self.assertEqual(r["status"], status)
            self.assertEqual(r["winner"], winner)
            self.assertEqual(r["score"], score)
            self.assertEqual(r["series_format"], fmt)
            self.assertEqual(r["result_date"], rdate)
            self.assertEqual(r["official_source_url"], url)
            self.assertEqual(r["flag"], flag)

    def test_verified_rows_complete(self):
        for r in self.results:
            if r["status"] != "verified":
                continue
            for field in ("winner", "score", "series_format", "result_date", "official_source_url"):
                self.assertTrue(r[field].strip(), f"{r['match_id']} missing {field}")
            self.assertTrue(r["winner"].strip().lower() in (r["team_a"].lower(), r["team_b"].lower()),
                            f"{r['match_id']} winner {r['winner']!r} not a card team")
            self.assertRegex(r["score"].strip(), r"^\d+-\d+$")
            self.assertTrue(r["official_source_url"].startswith("https://"))
            self.assertTrue(re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["result_date"].strip()))

    def test_unresolved_rows_never_fabricated(self):
        unresolved = [r for r in self.results if r["status"] == "unresolved"]
        self.assertEqual(len(unresolved), 6)
        for r in unresolved:
            self.assertEqual(r["winner"].strip(), "")
            self.assertEqual(r["score"].strip(), "")
            self.assertTrue(r["flag"].strip().startswith("UNRESOLVED-DRACULAN"))
            self.assertTrue(r["official_source_url"].startswith("https://"))
            # All six must be DraculaN Season 7 cards.
            self.assertEqual(r["tournament"], "DraculaN Season 7")
        for r in self.board:
            if r["group"] == "unresolved":
                self.assertEqual(r["pick"].strip(), "")
                self.assertEqual(r["winner"].strip(), "")

    def test_open_rows_have_pick_and_probs(self):
        for r in self.board:
            if r["group"] != "open":
                continue
            self.assertTrue(r["pick"].strip())
            pa, pb, pp = float(r["prob_a_pct"]), float(r["prob_b_pct"]), float(r["pick_prob_pct"])
            self.assertTrue(0 < pa < 100 and 0 < pb < 100)
            self.assertAlmostEqual(pa + pb, 100.0, delta=0.05)
            self.assertTrue(0 < pp < 100)
            self.assertTrue(r["source_links"].strip())
            # Pick must be one of the two teams.
            self.assertIn(r["pick"].strip().lower(), (r["team_a"].lower(), r["team_b"].lower()))

    def test_every_board_row_has_source(self):
        for r in self.board:
            has_result_src = bool(r["source_url"].strip())
            has_links = bool(r["source_links"].strip())
            self.assertTrue(has_result_src or has_links, f"{r['match_id']} has no source at all")
            for u in filter(None, (x.strip() for x in r["source_links"].split("|"))):
                self.assertTrue(u.startswith("https://"), f"{r['match_id']} non-https link {u!r}")
            if r["source_url"].strip():
                self.assertTrue(r["source_url"].strip().startswith("https://"))

    def test_html_covers_all_fixtures(self):
        for r in self.board:
            self.assertIn(r["match_id"], self.index_html)
        for r in self.board:
            if r["group"] == "unresolved":
                self.assertIn(r["match_id"], self.unres_html)

    def test_html_policy_statements(self):
        for page, name in ((self.index_html, "board"), (self.unres_html, "unresolved")):
            low = page.lower()
            self.assertIn("never", low, f"{name}: must state crowd % policy")
            self.assertIn("unresolved", low, f"{name}: must reference unresolved section")
        self.assertIn("draculanan-season-7", self.unres_html)
        self.assertIn("liquipedia.net/counterstrike/dach_cs_masters/season_5", self.index_html.lower())

    def test_flagged_caveats_present(self):
        flags = {r["match_id"]: r["flag"] for r in self.results}
        self.assertIn("AMBIGUOUS-DOUBLE-PLAY", flags["1052185"])
        self.assertIn("DATE-OFF-BY-ONE", flags["1055478"])
        # Name alias caveats must exist for every alias row.
        alias_rows = [r["match_id"] for r in self.results if r["flag"].startswith("Name alias")]
        self.assertGreaterEqual(len(alias_rows), 8)

    def test_build_script_check_passes(self):
        import subprocess
        proc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "c13ca42a_build_fullpicks.py"), "--check"],
                              capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("invariants pass", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
