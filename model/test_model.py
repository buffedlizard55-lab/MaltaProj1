#!/usr/bin/env python3
"""Tests for the O-01 own-line model (session arena/91eff436).

Run: python3 model/test_model.py -v
Set VRS_REPO_DIR to a clone of ValveSoftware/counter-strike_regional_standings to also check
our closed form against Valve's actual JavaScript (needs `node`).
"""
from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import build  # noqa: E402

OFFICIAL = ("https://www.hotspawn.com/", "https://play.hotspawn.com/",
            "https://github.com/ValveSoftware/counter-strike_regional_standings/", "https://www.hltv.org/")


class GlickoPort:
    """Line-by-line Python port of Valve's glicko.js team update with fixed RD (fit.js init)."""

    def __init__(self, rank, rd=75.0):
        self.rank, self.rd, self.adj_rank, self.adj_rdsq = rank, rd, 0.0, 0.0

    def add_pending(self, other, score):
        q = math.log(10) / 400
        g = 1 / math.sqrt(1 + (3 * q * q * other.rd * other.rd / (math.pi * math.pi)))
        ev = 1 / (1 + math.pow(10, g * (self.rank - other.rank) / (-400)))
        self.adj_rdsq += g * g * ev * (1 - ev)
        self.adj_rank += g * (score - ev)

    def apply(self):
        q = math.log(10) / 400
        adjusted = 1 / (1 / (self.rd * self.rd) + q * q * self.adj_rdsq)
        self.rank += q * adjusted * self.adj_rank
        self.rd = 75.0  # clampRD with min = max = 75


def prior_win_expectation_port(rv1, rv2):
    t1w, t1l, t2 = GlickoPort(rv1), GlickoPort(rv1), GlickoPort(rv2)
    start = t1w.rank
    t1w.add_pending(t2, 1)
    t1l.add_pending(t2, 0)
    t1w.apply()
    t1l.apply()
    win, loss = t1w.rank - start, start - t1l.rank
    return 1 - (win / (win + loss))


GRID = [(1843, 1534), (1931, 1411), (1500, 1550), (1066, 824), (400, 2046), (1200, 1200), (1716, 1543)]


class TestFormula(unittest.TestCase):
    def test_closed_form_matches_port(self):
        for a, b in GRID:
            self.assertAlmostEqual(build.valve_expected(a, b), prior_win_expectation_port(a, b), places=12)

    def test_symmetry_and_bounds(self):
        for a, b in GRID:
            p = build.valve_expected(a, b)
            self.assertAlmostEqual(p + build.valve_expected(b, a), 1.0, places=12)
            self.assertTrue(0 < p < 1)
        self.assertAlmostEqual(build.valve_expected(1500, 1500), 0.5, places=12)

    @unittest.skipUnless(os.environ.get("VRS_REPO_DIR") and shutil.which("node"), "needs VRS_REPO_DIR + node")
    def test_against_valve_javascript(self):
        mdir = Path(os.environ["VRS_REPO_DIR"]) / "model"
        js = f"""
const Module=require('module'),fs=require('fs'),path=require('path');
const dir={json.dumps(str(mdir))};const file=path.join(dir,'fit.js');
const src=fs.readFileSync(file,'utf8')+'\\nmodule.exports.__Fit=Fit;\\n';
const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(dir);m._compile(src,file);
const f=new m.exports.__Fit();f.init({{rd:75,sampleWindow:604800,analysisWindow:10368000}});
const grid={json.dumps(GRID)};
console.log(JSON.stringify(grid.map(([a,b])=>f.priorWinExpectation({{team1:{{rankValue:a}},team2:{{rankValue:b}}}}))));
"""
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr)
        vals = json.loads(out.stdout.strip().splitlines()[-1])
        for (a, b), v in zip(GRID, vals):
            self.assertAlmostEqual(build.valve_expected(a, b), v, places=12)


class TestOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = list(csv.DictReader((ROOT / "data" / "lines.csv").open(encoding="utf-8")))
        cls.teams = list(csv.DictReader((ROOT / "data" / "teams.csv").open(encoding="utf-8")))
        cls.fx = json.loads((ROOT / "input" / "hotspawn_cs2_fixtures.json").read_text())
        cal = build.load_calibration()
        cls.k = cal["k_published"] if cal else build.G
        cls.cal = cal
        cls.pts = {}
        for t in cls.teams:
            if t["vrs_points"]:
                cls.pts[t["hotspawn_team"]] = int(t["vrs_points"])

    def test_hotspawn_pick_percentages_never_ingested(self):
        blob = json.dumps(self.fx)
        self.assertNotIn("picked_percent", blob.replace('"participants0_picked_percent"', "").replace('"participants1_picked_percent"', ""))
        for f in self.fx["fixtures"]:
            self.assertFalse(any("picked" in k or k == "total_picks" for k in f))
        self.assertNotIn("picked", ",".join(self.rows[0].keys()))

    def test_every_fixture_present_once(self):
        ids = [r["hotspawn_match_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {str(f["id"]) for f in self.fx["fixtures"]})

    def test_lines_recompute_exactly(self):
        for r in self.rows:
            if r["line_status"] != "OWN LINE":
                for k in ("own_p_a", "own_p_b", "fair_odds_a", "fair_odds_b", "pick"):
                    self.assertEqual(r[k], "", f"blank row {r['hotspawn_match_id']} has {k}")
                self.assertTrue(r["notes"], f"blank row {r['hotspawn_match_id']} lacks a reason")
                continue
            a_, b_ = int(r["vrs_a_points"]), int(r["vrs_b_points"])
            p = build.p_k(self.k, a_, b_)
            self.assertAlmostEqual(float(r["own_p_a"]), round(100 * p, 1), places=6)
            self.assertAlmostEqual(float(r["valve_raw_p_a"]), round(100 * build.valve_expected(a_, b_), 1), places=6)
            self.assertAlmostEqual(float(r["own_p_a"]) + float(r["own_p_b"]), 100.0, delta=0.11)
            # the pick is OUR line's favourite and never depends on the market reference
            self.assertEqual(r["pick"], r["team_a"] if p > 0.5 else r["team_b"])

    def test_every_published_value_has_official_source(self):
        for r in self.rows:
            self.assertTrue(r["hotspawn_url"].startswith(OFFICIAL[:2]), r["hotspawn_url"])
            if r["line_status"] == "OWN LINE":
                for side in ("a", "b"):
                    self.assertTrue(r[f"vrs_{side}_url"].startswith(OFFICIAL[2]), r)
            for k in ("hltv_a_url", "hltv_b_url"):
                if r[k]:
                    self.assertTrue(r[k].startswith(OFFICIAL[3]))
        for t in self.teams:
            if t["vrs_points"]:
                self.assertTrue(t["vrs_url"].startswith(OFFICIAL[2]))
            else:
                self.assertTrue(t["resolution"] in ("NOT IN VRS", "AMBIGUOUS", "ROSTER MISMATCH"), t)

    def test_every_row_links_an_official_hotspawn_url(self):
        """Regression guard for the failure of scheduled run 38489574648 (2026-10-14T00:20:08Z):
        a fixture the board had just added carried a null permalink, str(None) reached the page as the
        literal string "None", and the source test failed. Every row must now carry a real URL on an
        official Hotspawn host, and a fixture without a per-match permalink must say so in its notes."""
        for r in self.rows:
            u = r["hotspawn_url"]
            self.assertIsInstance(u, str, r["hotspawn_match_id"])
            self.assertTrue(u.startswith(("https://www.hotspawn.com/", "https://play.hotspawn.com/")),
                            (r["hotspawn_match_id"], u))
            self.assertNotIn(u.strip().lower(), ("none", "null", ""), r["hotspawn_match_id"])
            permalink = self.fx.get("permalinks", {}).get(str(r["hotspawn_match_id"]))
            if permalink is None:
                self.assertIn("no per-match Hotspawn permalink", r["notes"], r["hotspawn_match_id"])
            else:
                self.assertEqual(u, permalink)

    def test_permalinks_ingested_are_real_urls(self):
        """A null/blank permalink must be dropped at ingest, never stringified into a published value."""
        for k, v in (self.fx.get("permalinks") or {}).items():
            self.assertIsInstance(v, str, k)
            self.assertTrue(v.startswith(("https://www.hotspawn.com/", "https://play.hotspawn.com/")), (k, v))

    def test_vrs_values_match_snapshot_file(self):
        meta = json.loads((ROOT / "input" / "vrs" / "meta.json").read_text())
        lines = (ROOT / "input" / "vrs" / Path(meta["path"]).name).read_text(encoding="utf-8").splitlines()
        for t in self.teams:
            if not t["vrs_url"]:
                continue
            ln = int(t["vrs_url"].rsplit("#L", 1)[1])
            cells = [c.strip() for c in lines[ln - 1].split("|")]
            self.assertEqual(cells[1], t["vrs_standing"])
            self.assertEqual(cells[2], t["vrs_points"])
            self.assertEqual(cells[3], t["vrs_name"])

    def test_market_reference_recomputed(self):
        for r in self.rows:
            if r["market_p_a"] == "":
                self.assertEqual(r["edge_pp"], "")
                continue
            oa, ob = float(r["market_odds_a"]), float(r["market_odds_b"])
            self.assertAlmostEqual(float(r["market_p_a"]), round(100 * (1 / oa) / (1 / oa + 1 / ob), 1), places=6)
            if r["own_p_a"] != "":
                self.assertAlmostEqual(float(r["edge_pp"]), round(float(r["own_p_a"]) - float(r["market_p_a"]), 1), delta=0.11)

    def test_calibration_sane(self):
        if not self.cal:
            self.skipTest("no adopted calibration")
        self.assertTrue(0.05 < self.cal["k_published"] < 2.0)
        o = self.cal["out_of_sample"]
        self.assertLess(o["calibrated_train_k"]["log_loss"], o["raw"]["log_loss"])  # adopted only if it helps out of sample
        self.assertAlmostEqual(build.p_k(build.G, 1700, 1500), build.valve_expected(1700, 1500), places=12)

    def test_aliases_are_evidence_backed_and_reverified(self):
        al = json.loads((ROOT / "aliases.json").read_text())["aliases"]
        by = {t["hotspawn_team"]: t for t in self.teams}
        vrs_names = {build.norm(t["vrs_name"]) for t in self.teams if t["vrs_name"]}
        for a in al:
            urls = [e["url"] for e in a["evidence"]]
            self.assertTrue(all(u.startswith(("https://www.hltv.org/", "https://www.hotspawn.com/")) for u in urls), a)
            self.assertTrue(any("hotspawn.com/matches/" in u for u in urls) and any("hltv.org/matches/" in u for u in urls), a)
            t = by.get(a["hotspawn_team"])
            if t is None:
                continue  # team not on the current slate
            if t["resolution"] == build.ALIAS_STATUS:
                self.assertTrue(t["hltv_url"].startswith(f"https://www.hltv.org/team/{a['hltv_team_id']}/"), t)
                self.assertTrue(t["vrs_url"].startswith(OFFICIAL[2]))
                # alias used only when no VRS row carries the Hotspawn name itself
                lines = (ROOT / "input" / "vrs" / Path(json.loads((ROOT / "input" / "vrs" / "meta.json").read_text())["path"]).name).read_text(encoding="utf-8")
                self.assertNotIn(f"| {a['hotspawn_team']} ", lines)

    def test_actionable_only_before_lock(self):
        from datetime import datetime, timezone
        fetched = datetime.strptime(self.fx["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        for r in self.rows:
            if r["section"] in ("started", "stale"):
                self.assertEqual(r["actionable"], "no", r["hotspawn_match_id"])
            else:
                lock = datetime.strptime(r["lock_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                self.assertEqual(r["actionable"], "yes" if lock > fetched else "no", r["hotspawn_match_id"])

    def test_identity_confirmations_cite_hltv(self):
        conf = json.loads((ROOT / "aliases.json").read_text()).get("identity_confirmations", [])
        by = {t["hotspawn_team"]: t for t in self.teams}
        for c in conf:
            self.assertTrue(any(ev["url"].startswith("https://www.hltv.org/news/") for ev in c["evidence"]), c)
            t = by.get(c["hotspawn_team"])
            if t and t["resolution"] == build.CONFIRMED_STATUS:
                self.assertEqual(build.norm(t["vrs_name"]), build.norm(c["vrs_name"]))

    def test_no_fuzzy_name_matching(self):
        for t in self.teams:
            if t["resolution"] in ("VERIFIED: VRS name + HLTV roster", "VERIFIED: VRS name"):
                self.assertEqual(build.norm(t["vrs_name"]), build.norm(t["hotspawn_team"]))


if __name__ == "__main__":
    unittest.main()
