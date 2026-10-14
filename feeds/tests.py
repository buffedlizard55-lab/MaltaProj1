#!/usr/bin/env python3
"""Tests + publication invariants for the secondary-market feed (session arena/a0bdf924).

Run: python3 feeds/tests.py   (exit 0 = publishable).  No network access needed.
"""
from __future__ import annotations

import csv
import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))
import match as M  # noqa: E402


def rows(name):
    p = DATA / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


class Names(unittest.TestCase):
    def test_norm(self):
        self.assertEqual(M.norm_name("Team Falcons"), "falcons")
        self.assertEqual(M.norm_name("BC.Game Esports"), "bcgame")
        self.assertEqual(M.norm_name("Aurora Gaming"), "aurora")
        self.assertEqual(M.norm_name("Sökerorg"), "sokerorg")
        self.assertEqual(M.norm_name("ENJOY"), M.norm_name("Enjoy"))
        self.assertNotEqual(M.norm_name("B8"), M.norm_name("B8 Academy"))
        self.assertNotEqual(M.norm_name("FORZE"), M.norm_name("FORZE Reload"))
        self.assertEqual(M.norm_name("Team"), "team")  # never reduced to nothing

    def test_relation(self):
        self.assertEqual(M.name_relation("Falcons", "Team Falcons")[0], "exact")
        self.assertEqual(M.name_relation("Ninjas in Pyjamas", "NIP")[0], "variant")
        self.assertEqual(M.name_relation("RoundsGG", "ROUNDS")[0], "variant")
        self.assertEqual(M.name_relation("LFO 10", "Sökerorg")[0], "different")
        al = M.Aliases([{"names": ["WROTBERRY", "WBT"], "evidence_url": "https://example.org/e"}])
        self.assertEqual(M.name_relation("WROTBERRY", "WBT", al), ("alias", "https://example.org/e"))


class Prices(unittest.TestCase):
    def test_devig(self):
        d = M.devig_decimal(1.42, 2.7)
        self.assertAlmostEqual(d["p_a"] + d["p_b"], 1.0, places=12)
        self.assertAlmostEqual(d["overround"], 1 / 1.42 + 1 / 2.7 - 1, places=12)
        self.assertAlmostEqual(d["p_a"], (1 / 1.42) / (1 / 1.42 + 1 / 2.7), places=12)
        self.assertIsNone(M.devig_decimal(1.0, 2.0))
        self.assertIsNone(M.devig_decimal("x", 2.0))

    def pm_event(self, **kw):
        market = {"sportsMarketType": "moneyline", "outcomes": '["ENJOY", "B8 Academy"]',
                  "outcomePrices": '["0.61", "0.39"]', "bestBid": 0.60, "bestAsk": 0.62,
                  "spread": 0.02, "liquidityNum": 2500, "volumeNum": 300, "closed": False,
                  "acceptingOrders": True, "gameStartTime": "2026-10-14 08:00:00+00", "id": "1"}
        market.update(kw.pop("market", {}))
        ev = {"id": "9", "slug": "cs2-enjoy-b8acad-2026-10-14",
              "title": "Counter-Strike: ENJOY vs B8 Academy (BO3) - CCT Europe", "markets": [
                  {"sportsMarketType": "child_moneyline", "outcomes": '["ENJOY", "B8 Academy"]',
                   "outcomePrices": '["0.5", "0.5"]', "question": "Map 1 Winner"}, market]}
        ev.update(kw)
        return ev

    def test_polymarket_ok(self):
        q = M.polymarket_quote(self.pm_event())
        self.assertTrue(q["ok"], q.get("reject"))
        self.assertEqual(q["format_bo"], 3)
        self.assertEqual(q["kickoff_utc"], "2026-10-14T08:00:00Z")
        self.assertAlmostEqual(q["p_a"], 0.61, places=9)
        self.assertEqual(q["source_url"], "https://polymarket.com/event/cs2-enjoy-b8acad-2026-10-14")

    def test_polymarket_gates(self):
        self.assertFalse(M.polymarket_quote(self.pm_event(market={"spread": 0.2}))["ok"])
        self.assertFalse(M.polymarket_quote(self.pm_event(market={"liquidityNum": 20}))["ok"])
        self.assertFalse(M.polymarket_quote(self.pm_event(market={"outcomePrices": '["0.97","0.97"]'}))["ok"])
        self.assertFalse(M.polymarket_quote(self.pm_event(market={"closed": True}))["ok"])
        self.assertFalse(M.polymarket_quote(self.pm_event(live=True))["ok"])

    def bo3(self, bu=True, active=True, swap=False):
        t1 = {"id": 1406, "name": "GenOne"}
        t2 = {"id": 24507, "name": "6666"}
        s1 = {"name": "GenOne", "coeff": 1.42, "active": active, "team_id": 1406}
        s2 = {"name": "6666", "coeff": 2.7, "active": active, "team_id": 24507}
        if swap:
            s1, s2 = s2, s1
        return {"id": 131159, "slug": "genone-vs-sixsixsixsix-14-10-2026", "status": "upcoming",
                "bo_type": 3, "start_date": "2026-10-14T08:00:00.000+00:00", "team1": t1, "team2": t2,
                "tournament": {"name": "NODWIN Clutch Series 13"},
                "bet_updates": ({"path": "https://thunderpick.io/match/2812130", "provider": "thunderpick",
                                 "team_1": s1, "team_2": s2} if bu else None)}

    def test_bo3(self):
        q = M.bo3_quote(self.bo3())
        self.assertTrue(q["ok"], q.get("reject"))
        self.assertEqual(q["book"], "Thunderpick")
        self.assertEqual(q["format_bo"], 3)
        self.assertEqual(q["kickoff_utc"], "2026-10-14T08:00:00Z")
        self.assertGreater(q["p_a"], q["p_b"])
        qs = M.bo3_quote(self.bo3(swap=True))   # relay lists team_2 first -> realigned by team id
        self.assertAlmostEqual(qs["p_a"], q["p_a"], places=12)
        self.assertFalse(M.bo3_quote(self.bo3(bu=False))["ok"])
        self.assertFalse(M.bo3_quote(self.bo3(active=False))["ok"])


class Matching(unittest.TestCase):
    fx = {"team_a": "Enjoy", "team_b": "B8 Academy", "start_utc": "2026-10-14T08:00:00Z"}

    def q(self, a, b, ko):
        return {"team_a": a, "team_b": b, "kickoff_utc": ko}

    def test_exact_and_swap(self):
        r = M.match_quote(self.fx, self.q("ENJOY", "B8 Academy", "2026-10-14T08:00:00Z"))
        self.assertEqual((r["status"], r["swap"], r["quality"]), ("accepted", False, "exact"))
        r = M.match_quote(self.fx, self.q("B8 Academy", "Enjoy", "2026-10-14T08:40:00Z"))
        self.assertEqual((r["status"], r["swap"]), ("accepted", True))

    def test_windows(self):
        r = M.match_quote(self.fx, self.q("Enjoy", "B8 Academy", "2026-10-14T10:00:00Z"))
        self.assertEqual(r["status"], "candidate")
        r = M.match_quote(self.fx, self.q("Enjoy", "B8 Academy", "2026-10-15T08:00:00Z"))
        self.assertEqual(r["status"], "none")

    def test_variant_and_conflict(self):
        fx = {"team_a": "Falcons", "team_b": "Ninjas in Pyjamas", "start_utc": "2026-10-14T11:00:00Z"}
        r = M.match_quote(fx, self.q("Team Falcons", "NIP", "2026-10-14T11:00:00Z"))
        self.assertEqual((r["status"], r["quality"]), ("accepted", "variant"))
        r = M.match_quote(fx, self.q("Team Falcons", "NIP", "2026-10-14T11:30:00Z"))
        self.assertNotEqual(r["status"], "accepted")
        fx2 = {"team_a": "FORZE Reload", "team_b": "LFO 10", "start_utc": "2026-10-14T17:00:00Z"}
        r = M.match_quote(fx2, self.q("FORZE Reload", "Sökerorg", "2026-10-14T17:00:00Z"))
        self.assertEqual(r["status"], "conflict")
        r = M.match_quote(fx2, self.q("B8", "B8 Academy", "2026-10-14T17:00:00Z"))
        self.assertEqual(r["status"], "none")

    def test_time_parse(self):
        for s in ("2026-10-14T08:00:00Z", "2026-10-14 08:00:00+00", "2026-10-14T08:00:00.000+00:00",
                  "1791964800000"):
            self.assertEqual(M.iso(M.parse_time(s)), "2026-10-14T08:00:00Z", s)


@unittest.skipUnless((DATA / "capture.json").exists(), "no capture yet")
class Published(unittest.TestCase):
    def test_rederive_from_archived_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "feeds"
            shutil.copytree(HERE, dst, ignore=shutil.ignore_patterns("__pycache__"))
            res = subprocess.run([sys.executable, str(dst / "join.py")], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stderr)
            for name in ("market_feed.csv", "fixtures.csv", "review.csv", "flags.csv", "summary.json"):
                self.assertEqual((dst / "data" / name).read_bytes(), (DATA / name).read_bytes(),
                                 f"{name} does not re-derive from the archived captures")

    def test_no_crowd_data_anywhere(self):
        with gzip.open(DATA / "raw" / "hotspawn_fixtures.json.gz", "rt", encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("picked_percent", text)
        self.assertNotIn("total_picks", text)
        for name in ("market_feed.csv", "fixtures.csv"):
            header = (DATA / name).read_text(encoding="utf-8").splitlines()[0].lower()
            self.assertNotIn("crowd", header)
            self.assertNotIn("picked", header)

    def test_feed_rows(self):
        for r in rows("market_feed.csv"):
            pa, pb = float(r["p_a_pct"]), float(r["p_b_pct"])
            self.assertAlmostEqual(pa + pb, 100.0, delta=0.02, msg=r["fixture_id"])
            self.assertTrue(r["source_url"].startswith("https://"), r)
            self.assertTrue(r["hotspawn_url"].startswith("https://"), r)
            self.assertTrue(r["captured_utc"], r)
            fav = r["team_a"] if pa > pb else r["team_b"] if pb > pa else ""
            self.assertEqual(r["favourite"], fav)
            if r["source"] == "bo3.gg":
                d = M.devig_decimal(r["price_a"], r["price_b"])
                self.assertAlmostEqual(100 * d["p_a"], pa, delta=0.01)
                self.assertTrue(r["book_url"].startswith("https://") or r["book"], r)

    def test_fixture_rows(self):
        summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
        fx = rows("fixtures.csv")
        self.assertEqual(len(fx), summary["open_cs2_fixtures"])
        as_of = M.parse_time(summary["as_of_utc"])
        for r in fx:
            self.assertTrue(r["hotspawn_url"].startswith("https://"), r)
            self.assertGreater(M.parse_time(r["lock_utc"]), as_of, r)
            ps = [float(x) for x in (r["bookmaker_p_a_pct"], r["polymarket_p_a_pct"]) if x]
            self.assertEqual(int(r["n_sources"]), len(ps))
            if ps:
                self.assertAlmostEqual(float(r["secondary_p_a_pct"]), sum(ps) / len(ps), delta=0.011)
                self.assertNotIn("MF-01", r["flags"].split(";"))
            else:
                self.assertEqual(r["secondary_p_a_pct"], "")
                self.assertIn("MF-01", r["flags"].split(";"))


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.viewport, self.rows_without_http = [], False, 0
        self._in_row, self._row_http = False, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport = True
        if tag in ("a", "link") and a.get("href"):
            self.links.append(a["href"])
            if self._in_row and a["href"].startswith("https://"):
                self._row_http = True
        if tag == "tr":
            self._in_row, self._row_http = True, False

    def handle_endtag(self, tag):
        if tag == "tr" and self._in_row:
            self._in_row = False
            if not self._row_http:
                self.rows_without_http += 1


@unittest.skipUnless((HERE / "index.html").exists(), "pages not built yet")
class Pages(unittest.TestCase):
    def test_pages(self):
        for name in ("index.html", "flagged.html", "method.html"):
            p = _Links()
            p.feed((HERE / name).read_text(encoding="utf-8"))
            self.assertTrue(p.viewport, name)
            for href in p.links:
                if re.match(r"^(https?:|mailto:|#)", href):
                    continue
                target = (HERE / href.split("#")[0]).resolve()
                self.assertTrue(target.exists(), f"{name}: broken local link {href}")
            if name == "index.html":
                # header row has no link; every data row must carry an official https source
                self.assertLessEqual(p.rows_without_http, 1, "index row without a source link")


if __name__ == "__main__":
    unittest.main(verbosity=2)
