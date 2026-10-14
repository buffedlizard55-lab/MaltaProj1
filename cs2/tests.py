#!/usr/bin/env python3
"""A6 — offline invariants for the board.  Run after ``model.py`` and ``build.py``:

    python3 cs2/tests.py

Each test is a promise the published site makes to the reader; if a rule is broken the build fails
and nothing is committed.
"""
from __future__ import annotations

import json
import math
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT


def rows(name):
    import csv
    path = DATA / name
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def close(a, b, tol=0.15):
    return abs(float(a) - float(b)) <= tol


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows("analysis.csv")
        cls.market = rows("market_rows.csv")
        cls.flags = rows("flags.csv")
        cls.cap = json.loads((DATA / "capture.json").read_text()) if (DATA / "capture.json").exists() else {}

    def test_dataset_exists(self):
        self.assertTrue(self.rows, "analysis.csv is empty - model.py did not run")

    def test_probabilities_complement(self):
        for col in ("market", "own", "consensus"):
            a, b = f"{col}_p_a_pct", f"{col}_p_b_pct"
            for r in self.rows:
                if r[a] and r[b]:
                    self.assertTrue(close(float(r[a]) + float(r[b]), 100.0),
                                    f"{r['fixture_id']}: {col} probabilities {r[a]}/{r[b]}")

    def test_no_crowd_percentages_are_published(self):
        """Hotspawn crowd fields stay in capture.json; nothing in analysis.csv may equal them."""
        banned = re.compile(r"crowd|picked_percent|total_picks", re.I)
        self.assertFalse([c for c in (self.rows[0].keys()) if banned.search(c)],
                         "a crowd column leaked into the published dataset")
        by_id = {f.get("match_id"): f for f in (self.cap.get("sources", {}).get("hotspawn") or {}).get("fixtures", [])}
        for r in self.rows:
            src = by_id.get(r["fixture_id"]) or {}
            for side in ("a", "b"):
                crowd = src.get(f"crowd_pct_{side}_audit_only")
                for col in ("market_p_a_pct" if side == "a" else "market_p_b_pct",
                            "own_p_a_pct" if side == "a" else "own_p_b_pct"):
                    if crowd in (None, "") or not r[col]:
                        continue
                    self.assertFalse(close(float(crowd), float(r[col]), 0.05),
                                     f"{r['fixture_id']}: {col} equals the Hotspawn crowd percentage")

    def test_pick_is_the_consensus_side(self):
        for r in self.rows:
            if not r["pick"]:
                self.assertFalse(r["consensus_p_a_pct"], f"{r['fixture_id']}: a probability but no pick")
                continue
            self.assertIn(r["pick"], (r["team_a"], r["team_b"]))
            hi = max(float(r["consensus_p_a_pct"]), float(r["consensus_p_b_pct"]))
            self.assertTrue(close(r["pick_pct"], hi), f"{r['fixture_id']}: pick_pct {r['pick_pct']} != {hi}")

    def test_devig_is_reproducible_from_the_published_prices(self):
        by_fixture = {}
        for m in self.market:
            by_fixture.setdefault(m["fixture_id"], []).append(m)
        for r in self.rows:
            if not r["market_p_a_pct"]:
                continue
            prices = by_fixture.get(r["fixture_id"]) or []
            chosen = [p for p in prices if p["book"] == (r["market_book"] or "").split(",")[0].strip()] or prices
            self.assertTrue(chosen, f"{r['fixture_id']}: published market probability with no price row")
            p_a = sum(float(p["implied_p_a_pct"]) for p in chosen) / len(chosen)
            for p in chosen:
                ia, ib = 1 / float(p["odds_a"]), 1 / float(p["odds_b"])
                self.assertTrue(close(p["implied_p_a_pct"], 100 * ia / (ia + ib), 0.2),
                                f"de-vig of {p['book']} not reproducible")
            self.assertTrue(close(r["market_p_a_pct"], p_a, 0.3),
                            f"{r['fixture_id']}: headline market prob {r['market_p_a_pct']} vs mean {p_a:.1f}")

    def test_own_line_reproducible(self):
        for r in self.rows:
            if not (r["own_p_a_pct"] and r["vrs_points_a"] and r["vrs_points_b"]):
                continue
            k = float(r["own_k"])
            d = float(r["vrs_points_a"]) - float(r["vrs_points_b"])
            p = 100 / (1 + 10 ** (-k * d / 400))
            self.assertTrue(close(p, r["own_p_a_pct"], 0.2),
                            f"{r['fixture_id']}: own line {r['own_p_a_pct']} vs recomputed {p:.1f}")

    def test_every_row_has_a_source(self):
        for r in self.rows:
            self.assertTrue(r["hotspawn_url"] or r["hotspawn_match_url"],
                            f"{r['fixture_id']}: row without a source link")
            if r["market_p_a_pct"]:
                self.assertTrue(r["market_url"] and r["market_captured_utc"],
                                f"{r['fixture_id']}: market prob without url/capture time")
            if r["own_p_a_pct"]:
                self.assertTrue(r["vrs_url_a"] and r["vrs_url_b"],
                                f"{r['fixture_id']}: own prob without a Valve standings link")

    def test_blanks_are_flagged(self):
        flagged = {f["fixture_id"] for f in self.flags}
        for r in self.rows:
            if r["pickable"] == "yes" and not r["consensus_p_a_pct"]:
                self.assertIn(r["fixture_id"], flagged,
                              f"{r['fixture_id']}: blank probabilities with no flag")

    def test_times_are_utc_and_ordered(self):
        for r in self.rows:
            for col in ("start_utc", "lock_utc"):
                if r[col]:
                    datetime.strptime(r[col], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if r["start_utc"] and r["lock_utc"]:
                self.assertLessEqual(r["lock_utc"], r["start_utc"],
                                     f"{r['fixture_id']}: lock after start")

    def test_odds_are_sane(self):
        for m in self.market:
            for col in ("odds_a", "odds_b"):
                if m[col]:
                    v = float(m[col])
                    self.assertTrue(1.01 <= v <= 1000, f"{m['book']} {col}={v}")

    def test_vrs_links_point_at_the_exact_row_they_claim(self):
        """Every published rating must be re-findable on the linked line of Valve's own file."""
        import gzip
        raw = sorted((DATA / "raw").glob("vrs_*.json.gz"))
        if not raw:
            self.skipTest("no VRS snapshot archived at this capture")
        lines = gzip.open(raw[0], "rb").read().decode("utf-8", "replace").splitlines()
        for r in self.rows:
            for side in ("a", "b"):
                url, pts, name = (r[f"vrs_url_{side}"], r[f"vrs_points_{side}"],
                                  r[f"vrs_name_{side}"])
                if not (url and pts):
                    continue
                m = re.search(r"#L(\d+)$", url)
                self.assertTrue(m, f"{r['fixture_id']}: rating link has no line anchor: {url}")
                line = lines[int(m.group(1)) - 1]
                self.assertIn(str(pts), line,
                              f"{r['fixture_id']}: {url} does not carry {pts} pts")
                self.assertIn(name.split()[0], line,
                              f"{r['fixture_id']}: {url} is not the row for {name}")

    def test_manually_verified_facts_are_attributed_and_not_stale(self):
        """Anything that came from a human reading a page must stay tied to its evidence."""
        ver_path = ROOT / "fixtures_verified.json"
        ver = json.loads(ver_path.read_text()) if ver_path.exists() else {}
        ver = {k: v for k, v in ver.items() if not k.startswith("_")}
        ids = {r["fixture_id"] for r in self.rows}
        for fid, rec in ver.items():
            self.assertIn(fid, ids, f"cs2/fixtures_verified.json entry {fid} matches no fixture — delete it")
            for key in ("series_len", "source_url", "verified_utc", "read_by"):
                self.assertTrue(rec.get(key), f"verified entry {fid} is missing {key}")
            self.assertTrue(str(rec["source_url"]).startswith("https://"),
                            f"verified entry {fid} has no https evidence link")
        for r in self.rows:
            if r.get("best_of_source") and r.get("best_of_note", "").find("read by") >= 0:
                self.assertIn(r["fixture_id"], ver,
                              f"{r['fixture_id']}: manual format claim with no record in fixtures_verified.json")

    def test_published_prices_exist_in_the_archived_bytes(self):
        """No published book price may be anything other than a number inside the archived payload.

        The archived gzip snapshots under ``cs2/data/raw`` are the exact bytes the collector read, so
        re-deriving the moneyline conversions from them and comparing sets proves the published
        odds were copied, not computed from memory.
        """
        import gzip
        from common import alias_lookup, american_to_decimal, norm
        aliases = json.loads((ROOT / "aliases.json").read_text())
        want = [(norm(alias_lookup(r["team_a"], aliases)), norm(alias_lookup(r["team_b"], aliases)),
                 float(r["odds_a"]), float(r["odds_b"]))
                for r in self.market
                if r.get("book") == "Pinnacle"
                and r.get("odds_a") and r.get("odds_b")]
        if not want:
            self.skipTest("no Pinnacle rows in this capture")

        def load(kind):
            files = sorted((DATA / "raw").glob(f"pinnacle_{kind}*.json.gz"))
            if not files:
                return None
            obj = json.loads(gzip.open(files[-1], "rb").read().decode("utf-8", "replace"))
            if isinstance(obj, dict):
                body = obj.get("body")
                if isinstance(body, str) and body.strip().startswith(("{", "[")):
                    obj = json.loads(body)
                obj = obj.get("events") or obj.get("markets") or []
            return obj

        events, markets = load("matchups"), load("markets")
        if not events or not markets:
            self.skipTest("Pinnacle payload snapshots are not archived at this capture")
        by_id = {str(e.get("id")): e for e in events if isinstance(e, dict)}
        derived = set()
        for m in markets:
            if not isinstance(m, dict) or m.get("type") != "moneyline" or m.get("period") != 0:
                continue
            if m.get("status") != "open" or m.get("isAlternate"):
                continue
            ev = by_id.get(str(m.get("matchupId"))) or {}
            if not str((ev.get("league") or {}).get("name", "")).startswith("CS2 - "):
                continue
            teams = [alias_lookup(p.get("name", ""), aliases) for p in (ev.get("participants") or [])]
            if len(teams) < 2:
                continue
            prices = {p.get("designation"): p.get("price") for p in (m.get("prices") or [])
                      if isinstance(p, dict)}
            da = american_to_decimal(prices.get("home"))
            db = american_to_decimal(prices.get("away"))
            if da and db:
                derived.add((norm(teams[0]), norm(teams[1]), round(da, 4), round(db, 4)))
                derived.add((norm(teams[1]), norm(teams[0]), round(db, 4), round(da, 4)))
        for a, b, oa, ob in want:
            hit = any(a == pa and b == pb and abs(oa - da) < 2e-3 and abs(ob - db) < 2e-3
                      for pa, pb, da, db in derived)
            self.assertTrue(hit, f"published price {a} v {b} {oa}/{ob} is not in the archived payload")

    def test_no_duplicate_fixture(self):
        ids = [r["fixture_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))


class TestSite(unittest.TestCase):
    """No broken internal links anywhere under cs2/."""

    def test_internal_links_resolve(self):
        pages = sorted(SITE.glob("*.html")) + sorted((SITE / "t").glob("*.html"))
        self.assertTrue(pages, "no pages built")
        bad = []
        for page in pages:
            html = page.read_text(encoding="utf-8")
            for href in re.findall(r'href="([^"#]+)(?:#[^"]*)?"', html):
                if href.startswith(("http://", "https://", "mailto:", "javascript:")):
                    continue
                target = (page.parent / href).resolve()
                if not target.exists():
                    bad.append(f"{page.name} -> {href}")
        self.assertFalse(bad, "broken internal links: " + "; ".join(bad[:12]))

    def test_anchors_resolve_on_flagged_page(self):
        path = SITE / "flagged.html"
        html = path.read_text(encoding="utf-8")
        ids = set(re.findall(r'<h2 id="([^"]+)"', html))
        for page in sorted(SITE.glob("*.html")) + sorted((SITE / "t").glob("*.html")):
            for anchor in re.findall(r'href="flagged\.html#([^"]+)"', page.read_text(encoding="utf-8")):
                self.assertIn(anchor, ids, f"{page.name} links to missing anchor #{anchor}")

    def test_pages_declare_viewport_and_are_self_contained(self):
        for page in sorted(SITE.glob("*.html")) + sorted((SITE / "t").glob("*.html")):
            html = page.read_text(encoding="utf-8")
            self.assertIn('name="viewport"', html, f"{page.name}: no viewport meta")
            self.assertFalse(re.search(r'<script[^>]+src="https?://', html),
                             f"{page.name}: third-party script on a page that must work on a phone")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestAnalysis, TestSite):
        if cls.__name__ == "TestAnalysis" and not (DATA / "analysis.csv").exists():
            print("SKIP TestAnalysis (no data yet - run collect.py + model.py first)")
            continue
        suite.addTests(loader.loadTestsFromTestCase(cls))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
