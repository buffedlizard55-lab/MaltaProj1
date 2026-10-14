#!/usr/bin/env python3
"""Tests for the source re-read verifier (session arena/bdc98a9a).

They run without network access: the network-touching verifiers are exercised with an injected
fetch result, so the suite proves the *decision rules* (match / mismatch / refused / placeholder)
rather than depending on what a remote host returns today.

Run:  python3 -m unittest tests.test_bdc98a9a_verify -v
"""

from __future__ import annotations

import csv
import html as html_escape_mod
import importlib.util
import io
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect = load("verify_collect", ROOT / "reread" / "collect.py")
build = load("verify_build", ROOT / "scripts" / "bdc98a9a_verify_build.py")

EGW_SNIPPET = """
<div class="odds">
 <div class="odd-row"><img src="/uploads/bc-game-logo.png" alt="bc.game">
   <span class="odd">1.52</span><span class="odd">2.30</span></div>
 <div class="odd-row"><img src="/uploads/betboom-logo.png" alt="BetBoom">
   <span class="odd">1.50</span><span class="odd">2.35</span></div>
 <div class="handicap"><img src="/uploads/bc-game-logo.png" alt="bc.game">
   <span class="odd">1.900</span><span class="odd">1.900</span></div>
</div>
"""

HLTV_SNIPPET = ("<html><body><h1>Astralis vs Sashi</h1>"
                "<div class='preformatted-text'>Best of 3 (Online)</div>"
                "<div>Astralis and Sashi meet in the Stake Pulse Beat III group stage.</div>"
                "</body></html>")


def fake_fetch(status: int, body: str = ""):
    def _fetch(url: str) -> dict:
        return {"url": url, "status": status, "bytes": len(body), "sha256": "deadbeef" if body else None,
                "path": "http", "error": None if status == 200 else f"HTTP {status}", "body": body,
                "fetched_utc": "2026-10-14T03:00:00Z"}
    return _fetch


class ParseTests(unittest.TestCase):
    def test_egw_book_parser_reads_named_pairs_and_skips_handicap(self):
        books = collect.parse_egw_books(EGW_SNIPPET)
        self.assertEqual([b["book"] for b in books], ["bc.game", "BetBoom"])
        self.assertAlmostEqual(books[0]["odds_a"], 1.52, places=3)
        self.assertAlmostEqual(books[0]["odds_b"], 2.30, places=3)

    def test_vrs_url_conversion_and_anchor(self):
        url = ("https://github.com/ValveSoftware/counter-strike_regional_standings/blob/"
               "eec4853/live/2026/standings_global_2026_10_05.md?plain=1#L89")
        self.assertEqual(
            collect.vrs_raw_url(url),
            "https://raw.githubusercontent.com/ValveSoftware/counter-strike_regional_standings/"
            "eec4853/live/2026/standings_global_2026_10_05.md")
        self.assertEqual(collect.anchor_line(url), 89)

    def test_rank_of_and_tokens(self):
        self.assertEqual(collect.rank_of("84 (1100 pts)"), "84")
        self.assertEqual(collect.rank_of(""), "")
        ok, detail = collect.tokens_present("Gothic vs Lavked preview", ["Gothic", "Lavked"])
        self.assertTrue(ok, detail)
        ok, detail = collect.tokens_present("something else", ["Gothic", "Lavked"])
        self.assertFalse(ok)

    def test_pinnacle_moneyline_reads_prices(self):
        payload = ('[{"id": 1, "participants": [{"name": "9z"}, {"name": "Aurora"}], '
                   '"prices": [{"designation": "home", "price": 3.41}, '
                   '{"designation": "away", "price": 1.3257}]}]')
        found = collect.pinnacle_moneyline(payload, "9z", "Aurora")
        self.assertIsNotNone(found)
        self.assertAlmostEqual(sorted(p for _, p in found["prices"])[-1], 3.41, places=2)
        self.assertIsNone(collect.pinnacle_moneyline(payload, "Gothic", "Lavked"))


class VerdictTests(unittest.TestCase):
    def claim(self, **kw):
        base = {"board": "unit", "fixture_id": "1", "team_a": "Astralis", "team_b": "Sashi",
                "kind": "hltv_match", "url": "https://www.hltv.org/matches/1/x", "claimed": "BO3",
                "extra": {"series_format": "BO3"}}
        base.update(kw)
        return base

    def test_hltv_match_matches_and_detects_best_of_mismatch(self):
        collect.fetch = fake_fetch(200, HLTV_SNIPPET)
        got = collect.verify_hltv_match(self.claim())
        self.assertEqual(got["verdict"], "match")
        self.assertIn("Best of 3", got["observed"])
        got = collect.verify_hltv_match(self.claim(claimed="BO1", extra={"series_format": "BO1"}))
        self.assertEqual(got["verdict"], "mismatch")
        self.assertIn("page says Best of 3", got["note"])

    def test_hltv_refusal_is_recorded_not_filled(self):
        collect.fetch = fake_fetch(403)
        got = collect.verify_hltv_match(self.claim())
        self.assertEqual(got["verdict"], "refused")
        self.assertIsNone(got["sha256"])

    def test_dead_link_is_dead(self):
        collect.fetch = fake_fetch(404)
        got = collect.verify_hltv_match(self.claim())
        self.assertEqual(got["verdict"], "dead")

    def test_egw_placeholder_pair_is_flagged(self):
        collect.fetch = fake_fetch(200, EGW_SNIPPET)
        got = collect.verify_egw_market(self.claim(
            kind="egw_market", extra={"odds_a": "1.52", "odds_b": "2.30"}))
        self.assertEqual(got["verdict"], "match")
        got = collect.verify_egw_market(self.claim(
            kind="egw_market", extra={"odds_a": "1.30", "odds_b": "3.30"}))
        self.assertEqual(got["verdict"], "mismatch")
        collect.fetch = fake_fetch(200, '<img src="/uploads/x-logo.png" alt="X"><b>1.80</b> <b>1.80</b>')
        got = collect.verify_egw_market(self.claim(
            kind="egw_market", extra={"odds_a": "1.30", "odds_b": "3.30"}))
        self.assertEqual(got["verdict"], "placeholder", got)

    def test_vrs_line_verified_at_the_anchor(self):
        body = "\n".join(["# Valve Regional Standings"] + [f"line {i}" for i in range(1, 8)] +
                         ["88. Team X 900", "89. FORZE Reload 1100", "90. Team Y 800"] +
                         [f"line {i}" for i in range(11, 20)])
        collect.fetch = fake_fetch(200, body)
        claim = {"board": "unit", "fixture_id": "1", "team_a": "FORZE Reload", "team_b": "",
                 "kind": "vrs", "url": "https://github.com/o/r/blob/main/f.md?plain=1#L10",
                 "claimed": "89 / 1100 pts", "extra": {"rank": "89"}}
        got = collect.verify_vrs(claim)
        self.assertEqual(got["verdict"], "match", got)
        bad = dict(claim, extra={"rank": "75"})
        self.assertEqual(collect.verify_vrs(bad)["verdict"], "mismatch")

    def test_utc_parser_returns_aware_time_and_null_for_junk(self):
        stamp = collect.parse_utc("2026-10-14T03:29:46Z")
        self.assertIsNotNone(stamp)
        self.assertIsNotNone(stamp.tzinfo)
        age = (__import__("datetime").datetime.now(collect.timezone.utc) - stamp).total_seconds()
        self.assertGreaterEqual(age, 0)
        self.assertIsNone(collect.parse_utc(""))
        self.assertIsNone(collect.parse_utc("not a date"))

    def test_every_verdict_name_is_known(self):
        for name in collect.VERDICT_NAMES:
            self.assertIn(name, build.CHIPS)


class WorklistTests(unittest.TestCase):
    def test_claims_have_urls_and_known_kinds(self):
        for board, fn in collect.CLAIMERS.items():
            claims = fn()
            self.assertTrue(claims or not collect.BOARDS[board].exists(), board)
            for c in claims:
                self.assertTrue(c["url"].startswith("http"), c)
                self.assertIn(c["kind"], collect.VERIFIERS, c)
                self.assertNotIn("crowd", c["url"], c)

    def test_hotspawn_claims_are_identity_only(self):
        for c in collect.claims_everypick() + collect.claims_cs2():
            if c["kind"] == "hotspawn":
                self.assertEqual(c["claimed"], "fixture identity")

    def test_dedupe_collapses_repeats(self):
        one = collect.claim_entry("b", "1", "A", "B", "vrs", "https://x/y#L1", claimed="1")
        two = collect.claim_entry("b", "2", "A", "B", "vrs", "https://x/y#L1", claimed="1")
        self.assertEqual(len(collect.dedupe([one, two])), 1)


class RenderTests(unittest.TestCase):
    def test_claim_cell_keeps_the_source_link_and_observed_value(self):
        row = {"url": "https://egamersworld.com/x", "claimed": "1.52/2.30", "observed": "bc.game 1.52/2.30",
               "note": "ok", "verdict": "match", "kind": "egw_market", "board": "everypick",
               "fixture_id": "1", "team_a": "Enjoy", "team_b": "B8 Academy"}
        cell = build.claim_cell(row)
        self.assertIn("https://egamersworld.com/x", cell)
        self.assertIn("bc.game 1.52/2.30", cell)
        html = build.claims_table([row])
        self.assertIn('class="chip ok"', html)
        sections = build.fixture_sections([row])
        self.assertIn("#1 Enjoy vs B8 Academy", sections)

    def test_published_page_rows_all_carry_a_link(self):
        path = ROOT / "reread" / "data" / "source_check.csv"
        if not path.exists():
            self.skipTest("no re-read published yet")
        rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"))))
        self.assertTrue(rows)
        index = (ROOT / "reread" / "index.html").read_text(encoding="utf-8")
        for row in rows:
            self.assertTrue(row["url"].startswith("http"))
            self.assertIn(html_escape_mod.escape(row["url"]), index, row["url"])
        for row in rows:
            self.assertTrue(row["verdict"] in collect.VERDICT_NAMES, row["verdict"])
            self.assertNotIn("crowd", row["observed"].lower())

    def test_flagged_page_only_lists_rows_needing_review(self):
        path = ROOT / "reread" / "flagged.html"
        if not path.exists():
            self.skipTest("no re-read published yet")
        html = path.read_text(encoding="utf-8")
        self.assertNotIn('class="chip ok"', html)


if __name__ == "__main__":
    unittest.main()
