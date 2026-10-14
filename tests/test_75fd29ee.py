#!/usr/bin/env python3
"""tests/test_75fd29ee.py — verification suite for session arena/75fd29ee (`every/` board).

Covers the session's acceptance criteria:
  * a pick exists for EVERY open CS2 fixture on the Hotspawn Pick'em slate (or a
    documented, flagged no-pick with a reason — never silent omission);
  * every published table row carries at least one https:// source link;
  * probabilities only come from outside market lines or originated rating lines —
    Hotspawn crowd percentages are never an input (columns, pages, coverage);
  * unverified values stay blank and flagged — never inferred;
  * the originated-line arithmetic is exactly the slate model (Elo-400 logistic,
    BO3/BO5 transforms, equal-weight blend) — verified against slate/data/own_lines.csv;
  * placeholder bookmaker prices (1.80/1.80) are rejected as market evidence;
  * no broken internal links in every/*.html.
"""

from __future__ import annotations

import csv
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVERY = ROOT / "every"
DATA = EVERY / "data"

import sys
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
_spec = importlib.util.spec_from_file_location("b75", ROOT / "scripts/75fd29ee_build.py")
b75 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b75)


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class TestModelParity(unittest.TestCase):
    def test_elo_and_series_functions(self):
        self.assertAlmostEqual(b75.elo_p(1000, 1000), 0.5, places=10)
        self.assertAlmostEqual(b75.series_from_map(0.5, 3), 0.5, places=10)
        self.assertAlmostEqual(b75.series_from_map(0.7, 3), 0.7 ** 2 * (3 - 2 * 0.7), places=10)
        self.assertAlmostEqual(b75.series_from_map(0.6, 5), 0.6 ** 3 * (10 - 15 * 0.6 + 6 * 0.36), places=10)
        self.assertEqual(b75.series_from_map(0.6, None), None)

    def test_devig(self):
        pa, pb, ov = b75.devig(2.0, 2.0)
        self.assertAlmostEqual(pa, 0.5, places=10)
        self.assertAlmostEqual(pb, 0.5, places=10)
        self.assertAlmostEqual(ov, 0.0, places=10)

    def test_originated_line_matches_slate_where_inputs_agree(self):
        """Every fixture whose rating inputs are unambiguous must reproduce slate's own_map_p_a."""
        rows = {r["fixture_id"]: r for r in load_csv(DATA / "picks.csv")}
        own = {r["fixture_id"]: r for r in load_csv(ROOT / "slate/data/own_lines.csv")}
        checked = 0
        for fid, row in rows.items():
            o = own.get(fid)
            if not o or not o.get("own_map_p_a") or row["our_map_p_a_pct"] == "":
                continue
            if "FL-DUPLICATE-VRS-DISAMBIGUATED" in row["flags"] or "E-01-RATED-VIA-RESEARCH" in row["flags"]:
                continue  # documented input differences (IRREG-02 / researched ratings)
            self.assertAlmostEqual(
                float(row["our_map_p_a_pct"]), float(o["own_map_p_a"]), delta=0.05,
                msg=f"{fid}: originated line diverges from slate model without a documented cause")
            checked += 1
        self.assertGreaterEqual(checked, 15, "expected the majority of rows to prove formula parity")


class TestPicksCoverage(unittest.TestCase):
    def setUp(self):
        self.rows = load_csv(DATA / "picks.csv")
        self.by_id = {r["fixture_id"]: r for r in self.rows}

    def test_every_open_cs2_fixture_has_a_pick_row(self):
        open_ids = {r["fixture_id"] for r in load_csv(ROOT / "slate/data/fixtures.csv")
                    if r.get("sport") == "cs2" and r.get("live_status") == "open"}
        self.assertTrue(open_ids, "slate fixture snapshot missing")
        self.assertEqual(set(self.by_id), open_ids,
                         "picks set must equal the open CS2 fixture set exactly")

    def test_every_fixture_has_pick_or_documented_absence(self):
        for r in self.rows:
            if not r["pick"]:
                self.assertTrue(("E-02-NO-PICK" in r["flags"]) or ("E-02-TIE" in r["flags"]),
                                f"{r['fixture_id']}: missing pick without a documented flag")
            else:
                self.assertTrue(r["pick_pct"] == "" or 0 < float(r["pick_pct"]) < 100)

    def test_lfo10_fixture_is_resolved_from_researched_rating(self):
        r = self.by_id.get("1079624")
        self.assertIsNotNone(r, "FORZE Reload vs LFO 10 must appear")
        self.assertEqual(r["pick"], "FORZE Reload")
        self.assertIn("hltv.org/valve-ranking", r["rating_b_source_url"])
        self.assertEqual(float(r["rating_b_vrs_points"]), 771.0)

    def test_pick_hierarchy_market_over_model(self):
        for r in self.rows:
            if r["market_tier"] in ("primary", "aggregator"):
                self.assertNotIn("E-02-MODEL-PICK", r["flags"],
                                 f"{r['fixture_id']}: model pick must not override a market line")


class TestSourcesAndHonesty(unittest.TestCase):
    def setUp(self):
        self.rows = load_csv(DATA / "picks.csv")

    def test_every_row_has_an_https_source(self):
        for r in self.rows:
            urls = [r["hotspawn_lobby_url"], r["hotspawn_match_url"], r["market_url"],
                    r["pick_source_url"], r["rating_a_source_url"], r["rating_b_source_url"],
                    r["hltv_match_url"]]
            self.assertTrue(any(u.startswith("https://") for u in urls if u),
                            f"{r['fixture_id']}: row without any https source link")

    def test_no_hotspawn_crowd_inputs(self):
        cols = " ".join(self.rows[0].keys()).lower()
        for banned in ("crowd", "total_picks", "hotspawn_pct", "pick_percent_a"):
            self.assertNotIn(banned, cols)
        cov = json.loads((DATA / "coverage.json").read_text())
        self.assertIs(cov["hotspawn_crowd_used"], False)

    def test_placeholder_odds_never_used(self):
        for r in self.rows:
            if r["market_odds_a"]:
                pair = (float(r["market_odds_a"]), float(r["market_odds_b"]))
                self.assertNotEqual(pair, (1.8, 1.8),
                                    f"{r['fixture_id']}: 1.80/1.80 placeholder used as a market line")

    def test_devig_recomputes_from_published_odds(self):
        for r in self.rows:
            if r["market_odds_a"]:
                pa, pb, _ = b75.devig(float(r["market_odds_a"]), float(r["market_odds_b"]))
                self.assertAlmostEqual(pa * 100, float(r["market_p_a_pct"]), delta=0.05)
                self.assertAlmostEqual(pb * 100, float(r["market_p_b_pct"]), delta=0.05)

    def test_unverified_values_stay_blank(self):
        for r in self.rows:
            if not r["rating_a_source_url"]:
                self.assertIn(r["our_map_p_a_pct"], ("",),
                              f"{r['fixture_id']}: probability without a rating source")
            if not r["pick_source_url"] and not r["market_url"]:
                self.assertIn("E-02", r["flags"], "undocumented pick source")


class TestPages(unittest.TestCase):
    PAGES = ["index.html", "methodology.html", "flagged.html", "sources.html"]

    def test_pages_exist(self):
        for p in self.PAGES:
            self.assertTrue((EVERY / p).exists(), f"missing every/{p}")

    def test_no_placeholder_tokens(self):
        for p in self.PAGES:
            html = (EVERY / p).read_text(encoding="utf-8")
            for bad in (">None<", "NaN", "undefined", "{esc", "None%"):
                self.assertNotIn(bad, html, f"{p}: token {bad} leaked into the page")

    def test_internal_links_resolve(self):
        for p in self.PAGES:
            html = (EVERY / p).read_text(encoding="utf-8")
            for href in re.findall(r'href="([^"]+)"', html):
                if href.startswith(("http://", "https://", "#", "mailto:")):
                    continue
                target = (EVERY / href.split("#")[0]).resolve()
                self.assertTrue(target.exists(), f"{p}: broken internal link {href}")

    def test_picks_table_rows_carry_links(self):
        html = (EVERY / "index.html").read_text(encoding="utf-8")
        body = html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        rows = body.split("<tr>")[1:]
        self.assertGreaterEqual(len(rows), 20)
        for chunk in rows:
            self.assertIn("https://", chunk, "picks table row without a source link")
            self.assertIn("PICK:", chunk)

    def test_exec_summary_present(self):
        html = (EVERY / "index.html").read_text(encoding="utf-8")
        self.assertIn("Where to find the picks", html)
        self.assertIn('name="viewport"', html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
