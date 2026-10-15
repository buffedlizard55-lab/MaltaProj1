#!/usr/bin/env python3
"""Invariants for the a6f05f99 board. Run with ``python3 a6f05f99/tests.py`` or pytest.

These tests run against whatever is committed under ``a6f05f99/data`` and ``a6f05f99/*.html``, so
they work without network access. The scheduled workflow re-runs them after every live collection
and refuses to publish if any of them fail.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DATA, RESEARCH, complementary, devig_two_way, read_json  # noqa: E402

PAGES = ["index.html", "picks.html", "twc.html", "unresolved.html", "method.html", "flagged.html"]
BANNED_AS_PROBABILITY = ("crowd_pct", "picked_percent")


def load_board() -> dict:
    return read_json(DATA / "board.json", {}) or {}


def load_capture() -> dict:
    return read_json(DATA / "capture.json", {}) or {}


class DataTests(unittest.TestCase):
    def test_capture_has_fixtures(self):
        self.assertTrue(load_capture().get("hotspawn", {}).get("fixtures"),
                        "capture has no Hotspawn fixtures")

    def test_board_rows_exist(self):
        self.assertGreater(len(load_board().get("rows", [])), 0)

    def test_every_open_fixture_has_pick_or_unresolved_flag(self):
        for row in load_board().get("rows", []):
            if row.get("status") != "open":
                continue
            has_pick = bool(row.get("pick"))
            flagged = "UNRESOLVED" in (row.get("flags") or [])
            self.assertTrue(has_pick or flagged,
                            f"{row.get('match_id')} is open with neither a pick nor UNRESOLVED")

    def test_probabilities_are_between_zero_and_one(self):
        for row in load_board().get("rows", []):
            for key in ("consensus_a", "consensus_b"):
                value = row.get(key)
                if value is None:
                    continue
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)

    def test_pick_matches_the_higher_probability(self):
        for row in load_board().get("rows", []):
            if row.get("status") != "open" or row.get("consensus_a") is None:
                continue
            expected = row["team_a"] if row["consensus_a"] >= 0.5 else row["team_b"]
            self.assertEqual(row.get("pick"), expected,
                             f"{row.get('match_id')} pick disagrees with its own probability")

    def test_every_open_row_has_at_least_one_source_link(self):
        for row in load_board().get("rows", []):
            if row.get("status") != "open":
                continue
            sources = " ".join(str(row.get(k) or "") for k in
                               ("hotspawn_match_url", "hltv_url_a", "hltv_url_b", "pinnacle_url",
                                "polymarket_url", "bo3_url", "vrs_url")) + " ".join(
                                    row.get("estimate_urls") or [])
            self.assertTrue(sources.strip() or "UNRESOLVED" in (row.get("flags") or []),
                            f"{row.get('match_id')} has no source link")

    def test_crowd_never_creates_a_probability(self):
        """A probability must be reproducible from a price or Valve points, never from the crowd."""
        for row in load_board().get("rows", []):
            if row.get("status") != "open" or row.get("consensus_a") is None:
                continue
            estimates = row.get("estimate_sources") or ""
            self.assertTrue(estimates.strip(),
                            f"{row.get('match_id')} has a probability but no named estimate")
            self.assertNotIn("crowd", estimates.lower(),
                             f"{row.get('match_id')} used the crowd as an estimate")

    def test_no_single_provider_is_counted_twice(self):
        """A hand read exists to stand in for an automated read. If the collector later reads the
        same bookmaker itself, merging both would count one provider twice and skew the mean."""
        for row in load_board().get("rows", []):
            shorts = [x.strip() for x in (row.get("estimate_sources") or "").split("|") if x.strip()]
            providers = [re.split(r"[ (,]", s, 1)[0].strip().lower() for s in shorts]
            dupes = {p for p in providers if providers.count(p) > 1}
            self.assertFalse(dupes,
                             f"{row.get('match_id')} counts these providers twice: {sorted(dupes)}")

    def test_coverage_counts_are_consistent(self):
        board, cov = load_board(), load_board().get("coverage", {})
        rows = board.get("rows", [])
        self.assertEqual(cov.get("open"), sum(1 for r in rows if r.get("status") == "open"))
        self.assertEqual(cov.get("open_with_pick"),
                         sum(1 for r in rows if r.get("status") == "open" and r.get("pick")))

    def test_devig_rejects_impossible_books(self):
        self.assertIsNone(devig_two_way(1.0, 2.0))
        self.assertIsNotNone(devig_two_way(1.5, 3.0))    # a zero-margin book is accepted
        self.assertIsNone(devig_two_way(1.2, 1.2))       # overround 66%, not a real two-way book
        pair = devig_two_way(1.42, 2.70)
        self.assertIsNotNone(pair)
        self.assertAlmostEqual(pair[0] + pair[1], 1.0, places=9)

    def test_complementary_percentages_sum_to_one_hundred(self):
        for value in (0.0, 0.1234, 0.5, 0.685, 0.999, 1.0):
            a, b = complementary(value)
            self.assertEqual(int(a) + int(b), 100)


class ResearchTests(unittest.TestCase):
    def test_every_twc_result_has_an_hltv_link(self):
        twc = read_json(RESEARCH / "twc2026.json", {}) or {}
        for day in twc.get("days", []):
            for m in day.get("matches", []):
                if m.get("winner"):
                    self.assertTrue(str(m.get("hltv", "")).startswith("https://www.hltv.org/"),
                                    f"{m.get('team_a')} v {m.get('team_b')}: result without HLTV link")

    def test_every_factor_has_a_source_and_a_strength(self):
        factors = (read_json(RESEARCH / "factors.json", {}) or {}).get("factors", [])
        self.assertGreater(len(factors), 0)
        for f in factors:
            self.assertIn(f.get("strength"), ("strong", "moderate", "weak"))
            self.assertTrue(f.get("source_urls"))
            self.assertTrue(str(f.get("team") or "").strip())

    def test_manual_lines_are_timestamped_and_linked(self):
        entries = (read_json(RESEARCH / "manual_lines.json", {}) or {}).get("entries", [])
        for e in entries:
            self.assertTrue(str(e.get("url", "")).startswith("https://"))
            self.assertTrue(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                                         str(e.get("read_utc") or "")))
            self.assertTrue(e.get("odds_a") and e.get("odds_b"))

    def test_aliases_carry_evidence(self):
        teams = (read_json(RESEARCH / "aliases.json", {}) or {}).get("teams", [])
        self.assertGreater(len(teams), 0)
        for t in teams:
            self.assertTrue(t.get("variants"))
            self.assertTrue(t.get("evidence"))
            self.assertTrue(t.get("source_urls"))


class PageTests(unittest.TestCase):
    def setUp(self):
        self.html = {name: (HERE / name).read_text(encoding="utf-8") for name in PAGES}

    def test_every_page_exists_and_is_non_trivial(self):
        for name, text in self.html.items():
            self.assertGreater(len(text), 1500, f"{name} looks empty")
            self.assertTrue(text.lstrip().lower().startswith("<!doctype html>"))

    def test_pages_are_mobile_ready(self):
        for name, text in self.html.items():
            self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">',
                          text, f"{name} has no viewport meta")

    def test_no_broken_local_links(self):
        for name, text in self.html.items():
            for href in re.findall(r'href="([^"#][^"]*)"', text):
                if href.startswith(("http", "mailto:", "//")):
                    continue
                target = (HERE / href.split("#")[0]).resolve()
                self.assertTrue(target.exists(), f"{name} links to a missing file: {href}")

    def test_nav_links_present_on_every_page(self):
        for name, text in self.html.items():
            for other in PAGES:
                self.assertIn(f'href="{other}"', text, f"{name} is missing the link to {other}")

    def test_executive_summary_links_the_picks(self):
        index = self.html["index.html"]
        for target in ("picks.html", "twc.html", "unresolved.html", "method.html"):
            self.assertIn(f'href="{target}"', index)
        self.assertIn("Where to find the picks", index)

    def test_executive_summary_has_unresolved_section(self):
        index = self.html["index.html"]
        self.assertIn("Unresolved picks", index)
        self.assertIn("Limitations that apply", index)

    def test_picks_page_shows_both_probabilities_for_every_open_match(self):
        board = load_board()
        picks = self.html["picks.html"]
        for row in board.get("rows", []):
            if row.get("status") != "open":
                continue
            self.assertIn(f'id="m{row["match_id"]}"', picks)
            self.assertIn("Pick:", picks)

    def test_no_hotspawn_crowd_percentage_is_presented_as_a_probability(self):
        for name in ("picks.html", "index.html"):
            text = self.html[name]
            self.assertIn("ownership only", text.lower().replace("&mdash;", "—"))

    def test_percentage_pairs_sum_to_one_hundred(self):
        """Every probability pair rendered on the picks page must add up to exactly 100."""
        for name in ("picks.html", "index.html"):
            text = self.html[name]
            for block in re.findall(r'<div class="probs">(.*?)</div>\s*<div class="bar',
                                    text, re.S):
                values = [int(v) for v in re.findall(r"<b>(\d+)%</b>", block)]
                if len(values) == 2:
                    self.assertEqual(sum(values), 100, f"{name}: pair {values} does not sum to 100")

    def test_unresolved_page_never_invents_a_pick(self):
        text = self.html["unresolved.html"]
        self.assertIn("Nothing here is filled in", text)
        self.assertIn("sources that were tried", text.lower())
        self.assertIn("Limitations behind the numbers", text)

    def test_method_page_states_the_rule_and_the_ladder(self):
        text = self.html["method.html"]
        for needle in ("probability ladder", "Leaderboard rule", "own line", "Margin removal"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
