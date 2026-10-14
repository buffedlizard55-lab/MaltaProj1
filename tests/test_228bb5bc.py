#!/usr/bin/env python3
"""Invariants for the consolidated every-match board (session arena/228bb5bc).

Run:  python -m unittest tests/test_228bb5bc.py -v

These tests are the publishing gate: the workflow that regenerates console/
runs them first, and only commits when they pass (fail-closed).
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "console"

_spec = importlib.util.spec_from_file_location("console_build", ROOT / "scripts" / "228bb5bc_build.py")
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)

NOW = datetime(2026, 10, 14, 4, 0, tzinfo=timezone.utc)


def load():
    inputs, _ = cb.load_inputs(NOW)
    return cb.build_rows(inputs, NOW)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RungSelection(unittest.TestCase):
    """The rung rule: best available outside price first, never averaged."""

    def test_primary_book_wins_over_relayed_and_prediction_market(self):
        feeds = {"bookmaker_book": "Thunderpick", "bookmaker_p_a_pct": "40",
                 "bookmaker_p_b_pct": "60", "captured_utc": "2026-10-14T03:00:00Z"}
        cs2 = {"market_book": "Pinnacle", "market_p_a_pct": "35", "market_p_b_pct": "65",
               "market_captured_utc": "2026-10-14T02:00:00Z", "market_url": "https://example.com/p"}
        pf = {"primary_book": "bc.game", "devig_p_a_pct": "38", "devig_p_b_pct": "62",
              "source_url": "https://example.com/e", "captured_utc": "2026-10-14T01:00:00Z"}
        cands = cb.market_candidates("1", feeds, cs2, None, None, pf)
        self.assertEqual([c["rung"] for c in cands], [1, 2, 3])
        self.assertEqual(cands[0]["book"], "Pinnacle")
        self.assertEqual(cands[0]["p_a"], 35.0)

    def test_relayed_book_wins_over_prediction_market(self):
        feeds = {"bookmaker_book": "Thunderpick", "bookmaker_p_a_pct": "40",
                 "bookmaker_p_b_pct": "60", "captured_utc": "2026-10-14T03:00:00Z",
                 "polymarket_p_a_pct": "45", "polymarket_p_b_pct": "55",
                 "polymarket_url": "https://example.com/pm"}
        cands = cb.market_candidates("1", feeds, None, None, None, None)
        self.assertEqual([c["rung"] for c in cands], [2, 4])

    def test_no_candidates_when_every_source_is_blank(self):
        self.assertEqual(cb.market_candidates("1", {}, None, None, None, None), [])

    def test_blank_cells_are_not_zero(self):
        cands = cb.market_candidates("1", {"bookmaker_book": "X", "bookmaker_p_a_pct": "",
                                           "bookmaker_p_b_pct": "0"}, None, None, None, None)
        self.assertEqual(cands, [])


class CommittedBoard(unittest.TestCase):
    """Checks against the data files this repository actually publishes."""

    @classmethod
    def setUpClass(cls):
        cls.rows, cls.flags, cls.meta = load()

    def test_rows_are_unique_and_non_empty(self):
        ids = [r["fixture_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 0)

    def test_every_open_fixture_has_a_pick(self):
        missing = [r["fixture_id"] for r in self.rows if r["state"] == "open" and not r["pick"]]
        self.assertEqual(missing, [], f"open fixtures without a pick: {missing}")

    def test_every_published_probability_has_a_source_url_and_read_time(self):
        for r in self.rows:
            if r["p_a_pct"] is None:
                continue
            self.assertTrue(cb.is_http(r["source_url"]), r["fixture_id"])
            self.assertTrue(r["read_utc"], r["fixture_id"])

    def test_no_probability_is_sourced_from_hotspawn(self):
        for r in self.rows:
            self.assertNotIn("hotspawn.com", cb.host_of(r["source_url"]), r["fixture_id"])
            for c in r["market_candidates"]:
                self.assertNotIn("hotspawn.com", cb.host_of(c["url"]), r["fixture_id"])

    def test_probabilities_sum_to_100(self):
        for r in self.rows:
            if r["p_a_pct"] is None:
                continue
            self.assertAlmostEqual(r["p_a_pct"] + r["p_b_pct"], 100.0, places=1, msg=r["fixture_id"])

    def test_headline_is_the_best_rung_published_beside_its_alternatives(self):
        for r in self.rows:
            if not r["market_candidates"]:
                continue
            best = r["market_candidates"][0]
            self.assertEqual(r["basis_rung"], f"market-{best['rung']}", r["fixture_id"])
            self.assertEqual(round(r["p_a_pct"], 2), round(best["p_a"], 2), r["fixture_id"])
            # never an average: the headline must equal one candidate exactly
            for other in r["market_candidates"][1:]:
                self.assertNotEqual(round(other["p_a"], 2), round(r["p_a_pct"], 2)
                                    if other["rung"] == best["rung"] else -1, r["fixture_id"])

    def test_rows_without_market_fall_back_to_own_line_or_research(self):
        for r in self.rows:
            if r["basis_rung"] in ("own-line", "research"):
                self.assertIsNotNone(r["own_line"], r["fixture_id"])

    def test_research_row_is_flagged_and_shows_a_range(self):
        research = [r for r in self.rows if r["basis_rung"] == "research"]
        for r in research:
            self.assertIn("C-RESEARCH-LINE", r["flags"], r["fixture_id"])
            self.assertIn("span", r["basis_detail"], r["fixture_id"])

    def test_team_names_and_ids_match_the_feed(self):
        feed = {r["fixture_id"]: r for r in cb.read_csv("feeds/data/fixtures.csv")}
        for r in self.rows:
            self.assertIn(r["fixture_id"], feed)
            self.assertEqual(r["team_a"], feed[r["fixture_id"]]["team_a"])
            self.assertEqual(r["team_b"], feed[r["fixture_id"]]["team_b"])

    def test_counts_in_coverage_match_the_rows(self):
        counts = self.meta["counts"]
        self.assertEqual(counts["rows"], len(self.rows))
        self.assertEqual(counts["open"], len([r for r in self.rows if r["state"] == "open"]))
        self.assertEqual(counts["open_with_pick"],
                         len([r for r in self.rows if r["state"] == "open" and r["pick"]]))
        self.assertEqual(counts["open_market_basis"],
                         len([r for r in self.rows if r["state"] == "open" and r["basis_rung"].startswith("market")]))

    def test_meta_declares_that_hotspawn_crowd_data_is_unused(self):
        self.assertFalse(self.meta["rules"]["hotspawn_crowd_percent_used"])

    def test_input_captures_are_recent(self):
        self.assertFalse(self.meta["stale"], self.meta["newest_input_age_hours"])


class GuardRails(unittest.TestCase):
    """The build refuses to publish broken or fabricated rows."""

    def _meta(self, stale=False):
        return {"stale": stale, "newest_input_age_hours": 9.0, "max_input_age_hours": 6.0}

    def test_stale_inputs_raise(self):
        rows = [{"fixture_id": "1", "p_a_pct": None, "p_b_pct": None, "pick": "",
                 "source_url": "", "read_utc": "", "team_a": "a", "team_b": "b"}]
        with self.assertRaises(cb.BuildError):
            cb.check_invariants(rows, self._meta(stale=True))

    def test_hotspawn_sourced_probability_raises(self):
        rows = [{"fixture_id": "1", "p_a_pct": 50.0, "p_b_pct": 50.0, "pick": "",
                 "source_url": "https://play.hotspawn.com/cs2-pickems", "read_utc": "2026-10-14T03:00:00Z",
                 "team_a": "a", "team_b": "b"}]
        with self.assertRaises(cb.BuildError):
            cb.check_invariants(rows, self._meta())

    def test_missing_source_raises(self):
        rows = [{"fixture_id": "1", "p_a_pct": 50.0, "p_b_pct": 50.0, "pick": "a",
                 "source_url": "", "read_utc": "2026-10-14T03:00:00Z", "team_a": "a", "team_b": "b"}]
        with self.assertRaises(cb.BuildError):
            cb.check_invariants(rows, self._meta())

    def test_probabilities_that_do_not_sum_to_100_raise(self):
        rows = [{"fixture_id": "1", "p_a_pct": 50.0, "p_b_pct": 40.0, "pick": "a",
                 "source_url": "https://example.com", "read_utc": "2026-10-14T03:00:00Z",
                 "team_a": "a", "team_b": "b"}]
        with self.assertRaises(cb.BuildError):
            cb.check_invariants(rows, self._meta())

    def test_pick_outside_the_two_teams_raises(self):
        rows = [{"fixture_id": "1", "p_a_pct": 60.0, "p_b_pct": 40.0, "pick": "c",
                 "source_url": "https://example.com", "read_utc": "2026-10-14T03:00:00Z",
                 "team_a": "a", "team_b": "b"}]
        with self.assertRaises(cb.BuildError):
            cb.check_invariants(rows, self._meta())


class RenderedPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (CONSOLE / "index.html").exists():
            subprocess.run([sys.executable, str(ROOT / "scripts" / "228bb5bc_build.py")],
                           cwd=ROOT, check=True, capture_output=True)
        cls.index = (CONSOLE / "index.html").read_text(encoding="utf-8")
        cls.flagged = (CONSOLE / "flagged.html").read_text(encoding="utf-8")
        cls.method = (CONSOLE / "methodology.html").read_text(encoding="utf-8")
        cls.sources = (CONSOLE / "sources.html").read_text(encoding="utf-8")
        cls.picks = json.loads((CONSOLE / "data" / "picks.json").read_text(encoding="utf-8"))

    def test_every_row_renders_as_a_card_with_its_source_link(self):
        for r in self.picks["rows"]:
            self.assertIn(f'id="m-{r["fixture_id"]}"', self.index)
            if r["source_url"]:
                self.assertIn(cb.esc(r["source_url"]), self.index)

    def test_page_never_contains_a_crowd_percentage_label(self):
        lowered = self.index.lower()
        for banned in ("crowd pick %", "picked%", "hotspawn probability", "hotspawn pick %"):
            self.assertNotIn(banned, lowered)

    def test_mobile_viewport_on_every_page(self):
        for html in (self.index, self.flagged, self.method, self.sources):
            self.assertIn('name="viewport"', html)
            self.assertIn("width=device-width", html)

    def test_every_flag_code_is_published_on_the_flagged_page(self):
        with (CONSOLE / "data" / "flags.csv").open(encoding="utf-8") as fh:
            flags = list(csv.DictReader(fh))
        for f in flags:
            self.assertIn(f["code"], self.flagged)

    def test_flagged_page_links_each_row_back_to_the_board(self):
        for fid in ("1079624", "1081112"):
            self.assertIn(f"console/index.html#m-{fid}", self.flagged)

    def test_methodology_states_the_rungs_and_the_blank_rule(self):
        for needle in ("Hotspawn", "rung", "blank", "never averaged"):
            self.assertIn(needle, self.method)

    def test_csv_and_json_agree_on_row_count(self):
        with (CONSOLE / "data" / "picks.csv").open(encoding="utf-8") as fh:
            csv_rows = list(csv.DictReader(fh))
        self.assertEqual(len(csv_rows), len(self.picks["rows"]))

    def test_machine_readable_schema(self):
        row = self.picks["rows"][0]
        for key in ("fixture_id", "team_a", "team_b", "p_a_pct", "pick", "basis_rung",
                    "source_url", "read_utc", "flags"):
            self.assertIn(key, row)


class RatingAnchorChecks(unittest.TestCase):
    """The own line is only published when its official rating row re-checks."""

    LINES = [
        "### Standings as of 2026_10_05<br />",
        "| Standing | Points | Team Name            | Roster |",
        "| 1        |   2046 | Spirit               | donk   |",
        "| 21       |   1500 | 3DMAX                | Graviti|",
        "| 143      |    862 | Lavked               | azukay |",
    ]
    ALIASES = {"envy": {"official_name": "3DMAX", "evidence_url": "https://example.com/ev"}}

    def test_matching_line_verifies(self):
        url = "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/x/standings.md?plain=1#L5"
        out = cb.verify_rating_anchor(url, "Lavked", "143", "862", self.LINES, {})
        self.assertTrue(out["ok"], out["detail"])

    def test_name_mismatch_is_reported(self):
        url = "...?plain=1#L4"
        out = cb.verify_rating_anchor(url, "Envy", "21", "1500", self.LINES, {})
        self.assertFalse(out["ok"])
        self.assertIn("3DMAX", out["detail"])

    def test_documented_alias_is_accepted(self):
        url = "...?plain=1#L4"
        out = cb.verify_rating_anchor(url, "Envy", "21", "1500", self.LINES, self.ALIASES)
        self.assertTrue(out["ok"])
        self.assertEqual(out["alias_of"], "3DMAX")
        self.assertEqual(out["evidence_url"], "https://example.com/ev")

    def test_points_mismatch_is_reported(self):
        url = "...?plain=1#L5"
        out = cb.verify_rating_anchor(url, "Lavked", "143", "999", self.LINES, {})
        self.assertFalse(out["ok"])
        self.assertIn("999", out["detail"])

    def test_missing_anchor_is_reported(self):
        self.assertFalse(cb.verify_rating_anchor("https://example.com/nothing", "Lavked", "", "", self.LINES, {})["ok"])
        self.assertFalse(cb.verify_rating_anchor("...?plain=1#L99", "Lavked", "", "", self.LINES, {})["ok"])

    def test_withheld_own_line_publishes_no_probability(self):
        own = {"own_p_a_pct": "60", "own_p_b_pct": "40", "method": "m", "series_format": "BO3",
               "vrs_url_a": "u", "vrs_url_b": "u", "hltv_match_url": "", "research": "no", "flags": ""}
        checks = {"a": {"ok": False, "detail": "line names another team"},
                  "b": {"ok": True, "detail": "ok"}}
        out = cb.own_line("1", own, None, checks)
        self.assertIsNone(out["p_a"])
        self.assertIsNone(out["p_b"])
        self.assertFalse(out["verified"])

    def test_research_line_is_exempt_from_the_anchor_rule(self):
        own = {"own_p_a_pct": "75.9", "own_p_b_pct": "24.1", "method": "m", "series_format": "BO3",
               "vrs_url_a": "u", "vrs_url_b": "u", "hltv_match_url": "", "research": "yes", "flags": ""}
        checks = {"a": {"ok": True, "detail": "ok"}, "b": {"ok": False, "detail": "team absent"}}
        out = cb.own_line("1", own, None, checks)
        self.assertEqual(out["p_a"], 75.9)
        self.assertTrue(out["research"])


class CommittedRatingFile(unittest.TestCase):
    def test_file_matches_the_published_sha256(self):
        _lines, meta = cb.parse_vrs_file()
        self.assertTrue(meta["integrity_ok"], meta)

    def test_every_published_own_line_anchor_re_check(self):
        lines, _ = cb.parse_vrs_file()
        aliases = cb.load_alias_map()
        own_rows = list(csv.DictReader((ROOT / "data" / "63ee81ba" / "own_lines.csv").open(encoding="utf-8")))
        self.assertGreater(len(own_rows), 0)
        failures = []
        for row in own_rows:
            if (row.get("research") or "").strip().lower() == "yes":
                continue
            for side in ("a", "b"):
                verdict = cb.verify_rating_anchor(row.get(f"vrs_url_{side}", ""), row.get(f"team_{side}", ""),
                                                  row.get(f"vrs_standing_{side}", ""), row.get(f"vrs_points_{side}", ""),
                                                  lines, aliases)
                if not verdict["ok"]:
                    failures.append((row["match_id"], row[f"team_{side}"], verdict["detail"]))
        self.assertEqual(failures, [], f"unverified rating anchors: {failures}")


class LandingPage(unittest.TestCase):
    """The restructured landing page must keep every link it had before."""

    def test_landing_keeps_every_previously_linked_page(self):
        registry = list(csv.DictReader((CONSOLE / "data" / "landing_links.csv").open(encoding="utf-8")))
        html_text = (ROOT / "index.html").read_text(encoding="utf-8")
        hrefs = {h.split("#")[0] for h in __import__("re").findall(r'href="([^"]+)"', html_text)
                 if not h.startswith(("#", "http", "mailto"))}
        missing = [r["path"] for r in registry if r["path"] not in hrefs]
        self.assertEqual(missing, [], f"landing page dropped links: {missing}")

    def test_landing_points_at_the_consolidated_board_and_is_mobile_ready(self):
        html_text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("console/index.html", html_text)
        self.assertIn("console/flagged.html", html_text)
        self.assertIn('name="viewport"', html_text)
        self.assertIn("width=device-width", html_text)

    def test_landing_has_one_executive_summary_and_no_leaked_comment_text(self):
        html_text = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html_text.count('id="live-status"'), 1)
        self.assertNotIn("# Conflict resolved", html_text)
        self.assertIn("Executive summary", html_text)


class Determinism(unittest.TestCase):
    def test_two_builds_with_the_same_clock_are_byte_identical(self):
        env = {"PATH": "/usr/bin:/bin", "CONSOLE_NOW_UTC": "2026-10-14T04:00:00Z"}
        cmd = [sys.executable, str(ROOT / "scripts" / "228bb5bc_build.py")]
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, env=env)
        first = {p.name: digest(p) for p in CONSOLE.rglob("*") if p.is_file()}
        subprocess.run(cmd, cwd=ROOT, check=True, capture_output=True, env=env)
        second = {p.name: digest(p) for p in CONSOLE.rglob("*") if p.is_file()}
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
