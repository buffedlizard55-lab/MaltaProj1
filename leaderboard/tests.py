"""Fail-closed checks for the contrarian leaderboard plan — session arena/2e2b2e5e.

Run: python -m unittest discover -s leaderboard -p tests.py -v
The workflow runs these after every live build; nothing is committed unless they pass.
"""
from __future__ import annotations

import copy
import csv
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build  # noqa: E402
import collect  # noqa: E402
import model  # noqa: E402

PAGES = ["index.html", "day1.html", "factors.html", "unresolved.html", "flagged.html", "method.html"]
ALLOWED_RESEARCH_HOSTS = {"www.hltv.org", "liquipedia.net", "github.com", "www.pinnacle.com", "play.hotspawn.com",
                          "www.hotspawn.com"}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.h1 = [], set(), 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "h1":
            self.h1 += 1


class ModelTests(unittest.TestCase):
    def test_devig_sums_to_one_and_orders(self):
        pa, pb, margin = model.devig(1.36, 3.08)
        self.assertAlmostEqual(pa + pb, 1.0, places=9)
        self.assertGreater(pa, pb)
        self.assertGreater(margin, 0)
        self.assertAlmostEqual(model.american_to_decimal(265), 3.65)
        self.assertAlmostEqual(model.american_to_decimal(-365), 1 + 100 / 365)

    def test_series_transform(self):
        self.assertAlmostEqual(model.series_prob(0.5, 3), 0.5, places=9)
        self.assertGreater(model.series_prob(0.6, 3), 0.6)
        self.assertGreater(model.series_prob(0.6, 5), model.series_prob(0.6, 3))
        self.assertAlmostEqual(model.series_prob(0.6, 1), 0.6)
        self.assertAlmostEqual(model.series_prob(0.6, 3), 0.6 ** 2 * (3 - 2 * 0.6), places=9)

    def test_contrarian_labels(self):
        self.assertEqual(model.contrarian(0.605, 2, 17, 83)["label"], "fade")      # favourite under-owned
        self.assertEqual(model.contrarian(0.534, 7, 69, 31)["label"], "value")     # 46.6% dog, 31% owned
        self.assertEqual(model.contrarian(0.574, 7, 68, 32)["label"], "chalk")     # leverage 1.33 < 1.5
        self.assertEqual(model.contrarian(0.259, 7, 4, 96)["label"], "upset")      # 9z vs Aurora on day 1
        self.assertEqual(model.contrarian(0.80, 2, 95, 5)["label"], "chalk")
        self.assertEqual(model.contrarian(0.6, 2, None, None)["label"], "no crowd data")
        c = model.contrarian(0.534, 7, 69, 31)
        self.assertAlmostEqual(c["ev_cost"], 7 * (0.534 - 0.466), places=6)

    def test_fit_k_recovers_scale(self):
        pairs = [{"points_a": 1500 + d, "points_b": 1500, "best_of": 3,
                  "market_p_a": model.vrs_line(1500 + d, 1500, 3, 0.4)} for d in range(-300, 301, 50)]
        k, n, mae = model.fit_k(pairs)
        self.assertAlmostEqual(k, 0.4, delta=0.02)
        self.assertEqual(n, len(pairs))
        self.assertLess(mae, 0.5)


class ParserTests(unittest.TestCase):
    def test_hotspawn_transferstate(self):
        state = {"1": {"s": 200, "u": "https://x.example/api/v1/fixtures", "b": [{
            "id": 42, "sport_alias": "cs2", "competition_name": "Test Cup", "status": "scheduled", "tier": "s",
            "offered_points": 7, "scheduled_start_time": "1792062000000", "lock_time": "1792061640000",
            "participants0_name": "Alpha", "participants1_name": "Beta", "participants0_picked_percent": 30,
            "participants1_picked_percent": 70, "total_picks": 10}]},
            "2": {"s": 200, "u": "https://x.example/api/v1/pickem-weeks/lobby", "b": {"weekId": 1, "weekStartUtc": "a", "weekEndUtc": "b", "cutoffUtc": "c"}}}
        html = f'<html><body>72 matches this week All tiers (78)<script id="ng-state" type="application/json">{json.dumps(state)}</script></body></html>'
        out = collect.parse_hotspawn_state(html, "lobby", "https://play.hotspawn.com/lobby", "2026-10-15T00:00:00Z")
        self.assertEqual(len(out["fixtures"]), 1)
        self.assertEqual(out["week"]["weekId"], 1)
        self.assertEqual(out["header_matches_this_week"], 72)
        self.assertEqual(out["filter_all_tiers"], 78)
        fx = collect.normalize_fixture(out["fixtures"][0], "lobby", "u", "t", {})
        self.assertEqual(fx["start_utc"], "2026-10-15T11:00:00Z")
        self.assertEqual(fx["lock_utc"], "2026-10-15T10:54:00Z")
        self.assertEqual(fx["ownership"]["crowd_pct_a"], 30)
        self.assertNotIn("crowd_pct_a", {k for k in fx if k != "ownership"})

    def test_vrs_parse(self):
        md = "| Standing | Points | Team Name | Roster | |\n| :- | -: | :- | :- | :- |\n| 1 | 2046 | Spirit | donk, magixx | [d](x) |\n"
        rows = collect.parse_vrs(md)
        self.assertEqual(rows[0]["team"], "Spirit")
        self.assertEqual(rows[0]["points"], 2046)

    def test_names_never_merge_distinct_teams(self):
        research = json.loads(build.RESEARCH.read_text())
        names = build.Names(research["aliases"])
        self.assertNotEqual(names.canon("EAC EXTRA"), names.canon("EAC"))
        self.assertEqual(names.canon("Esport Academy Copenhagen"), names.canon("EAC"))
        self.assertEqual(names.canon("WBT"), names.canon("WROTBERRY"))
        self.assertEqual(names.canon("PVISION"), names.canon("PARIVISION"))
        self.assertEqual(names.canon("BB Team"), names.canon("BetBoom"))
        self.assertEqual(names.canon("ROUNDS"), names.canon("RoundsGG"))
        self.assertEqual(names.canon("Privateer Gaming"), names.canon("Privateer"))
        self.assertNotEqual(names.canon("Phantom Academy"), names.canon("Phantom"))


class PlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capture, cls.research = build.load_inputs()
        cls.now = build.now_from(cls.capture)
        cls.rows, cls.cal, _, _ = build.build_rows(cls.capture, cls.research, cls.now)
        with (HERE / "data" / "plan.csv").open(encoding="utf-8") as fh:
            cls.plan = list(csv.DictReader(fh))
        cls.summary = json.loads((HERE / "data" / "summary.json").read_text())

    def test_crowd_never_moves_a_probability(self):
        mutated = copy.deepcopy(self.capture)
        for fx in mutated["hotspawn"]["fixtures"]:
            fx["ownership"] = {"crowd_pct_a": 100, "crowd_pct_b": 0, "total_picks": 999}
        rows2, _, _, _ = build.build_rows(mutated, self.research, self.now)
        before = {r["fx"]["match_id"]: r["p_a"] for r in self.rows}
        after = {r["fx"]["match_id"]: r["p_a"] for r in rows2}
        self.assertEqual(before, after)

    def test_every_open_fixture_is_picked_or_listed_unresolved(self):
        unresolved_html = (HERE / "unresolved.html").read_text()
        open_rows = [r for r in self.rows if r["status"] == "open"]
        self.assertTrue(open_rows, "no open fixture in the capture")
        for r in open_rows:
            fx = r["fx"]
            if r["p_a"] is None:
                self.assertIn(f'#m{fx["match_id"]}', unresolved_html, fx["match_id"])
            else:
                self.assertIn(r["pick"], (fx["team_a"], fx["team_b"]))
                self.assertTrue(0 < r["p_a"] < 1)

    def test_plan_csv_matches_capture_and_sums(self):
        ids = {fx["match_id"] for fx in self.capture["hotspawn"]["fixtures"]}
        self.assertEqual({r["match_id"] for r in self.plan}, ids)
        for r in self.plan:
            if r["prob_a_pct"]:
                self.assertAlmostEqual(float(r["prob_a_pct"]) + float(r["prob_b_pct"]), 100.0, delta=0.11)
            urls = r["source_urls"].split()
            self.assertTrue(urls, r["match_id"])
            for u in urls:
                self.assertEqual(urlsplit(u).scheme, "https", (r["match_id"], u))
            if r["status"] == "open" and r["prob_a_pct"]:
                self.assertTrue(any("hotspawn.com" not in u for u in urls), r["match_id"])
        self.assertEqual(self.summary["open"], sum(1 for r in self.plan if r["status"] == "open"))
        self.assertEqual(self.summary["open_with_pick"], sum(1 for r in self.plan if r["status"] == "open" and r["pick"]))

    def test_market_probability_reproduces_from_stored_quote(self):
        for r in self.rows:
            if r["status"] == "open" and r["pin"]:
                q = r["pin"]
                self.assertAlmostEqual(q["p_a"] + q["p_b"], 1.0, places=9)
                self.assertAlmostEqual(r["p_a"], q["p_a"], places=9)

    def test_day1_rows_are_complete_and_verified(self):
        with (HERE / "data" / "day1.csv").open(encoding="utf-8") as fh:
            d1 = list(csv.DictReader(fh))
        self.assertEqual(len(d1), 13)
        for r in d1:
            self.assertTrue(r["winner"], r["match_id"])
            self.assertTrue(r["hltv_url"].startswith("https://www.hltv.org/matches/"), r["match_id"])
        strat = self.summary["day1_strategies"]
        self.assertEqual(strat["available"], sum(int(r["points"]) for r in d1))
        self.assertLessEqual(max(strat["crowd_favourite"], strat["market_favourite"], strat["protect"], strat["chase"]), strat["available"])

    def test_research_sources_are_official_https(self):
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, str) and v.startswith("http") and k in ("url", "hltv", "format_source", "capture_url", "source", "lobby_source", "results_source", "schedule_source"):
                        yield v
                    yield from walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    if isinstance(v, str) and v.startswith("http"):
                        yield v
                    yield from walk(v)
        urls = list(walk(self.research))
        self.assertGreater(len(urls), 40)
        for u in urls:
            parts = urlsplit(u)
            self.assertEqual(parts.scheme, "https", u)
            self.assertIn(parts.netloc, ALLOWED_RESEARCH_HOSTS, u)


class PageTests(unittest.TestCase):
    def test_pages_exist_link_and_are_mobile_ready(self):
        css = (HERE / "style.css").read_text()
        self.assertIn("min-height: 44px", css)
        self.assertIn("@media (max-width: 760px)", css)
        for name in PAGES:
            text = (HERE / name).read_text()
            p = LinkParser()
            p.feed(text)
            self.assertEqual(p.h1, 1, name)
            self.assertIn('name="viewport"', text, name)
            self.assertIn('href="#main"', text, name)
            self.assertNotIn("{esc(", text, name)
            self.assertNotIn("None%", text, name)
            for href in p.links:
                parts = urlsplit(href)
                if parts.scheme in ("http", "https"):
                    self.assertTrue(parts.netloc, (name, href))
                    continue
                if not parts.path:
                    self.assertIn(parts.fragment, p.ids, (name, href))
                    continue
                target = (HERE / parts.path).resolve()
                self.assertTrue(target.exists(), (name, href))
                if parts.fragment and target.suffix == ".html":
                    tp = LinkParser()
                    tp.feed(target.read_text())
                    self.assertIn(parts.fragment, tp.ids, (name, href))

    def test_plan_page_states_crowd_policy_and_capture_time(self):
        text = (HERE / "index.html").read_text()
        self.assertIn("never as a win probability", text)
        self.assertRegex(text, r"(Live capture|built from a capture taken) [A-Z][a-z]{2} \d{2} [A-Z][a-z]{2} \d{2}:\d{2} UTC")
        self.assertIn("data-lock=", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
