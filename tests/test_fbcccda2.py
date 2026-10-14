import csv, json, os, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p): return list(csv.DictReader(open(os.path.join(ROOT, p), encoding="utf-8")))
class EveryPick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rd("data/fbcccda2/every_pick.csv"); cls.cov = json.load(open(os.path.join(ROOT, "data/fbcccda2/coverage.json")))
    def test_every_open_cs2_has_pick(self):
        self.assertEqual(len(self.rows), 28); self.assertTrue(all(r["pick"] for r in self.rows))
        self.assertEqual(self.cov["counts"], {"open_cs2":28,"with_pick":28,"with_numeric_pct":27,"tier_A":5,"tier_B":19,"tier_C":3,"tier_D":1,"no_pick":0})
    def test_devig_sums_and_pick_is_favourite(self):
        for r in self.rows:
            if r["p_a_pct"]:
                self.assertAlmostEqual(float(r["p_a_pct"])+float(r["p_b_pct"]), 100.0, delta=0.15, msg=r["fixture_id"])
                fav = r["team_a"] if float(r["p_a_pct"]) >= float(r["p_b_pct"]) else r["team_b"]
                self.assertEqual(r["pick"], fav, r["fixture_id"])
                self.assertNotEqual((r["odds_a"], r["odds_b"]), ("1.80","1.80"))
    def test_guided_lean_blank_pct(self):
        d = [r for r in self.rows if r["pick_tier"]=="D"]
        self.assertEqual(len(d),1); self.assertEqual(d[0]["fixture_id"],"1079624")
        self.assertEqual(d[0]["pick"],"FORZE Reload"); self.assertEqual(d[0]["p_a_pct"],"")
    def test_every_row_sourced(self):
        for r in self.rows:
            self.assertTrue(r["hotspawn_url"].startswith("https://play.hotspawn.com"), r["fixture_id"])
            self.assertTrue(r["hltv_match_url"].startswith("https://www.hltv.org/matches/"), r["fixture_id"])
            self.assertIn(r["pick_tier"], "ABCD")
    def test_site_pages_exist_and_mobile(self):
        for p in ["everypick/index.html","everypick/flagged.html","everypick/methodology.html"]:
            t = open(os.path.join(ROOT,p), encoding="utf-8").read()
            self.assertIn('name="viewport"', t); self.assertIn("Executive summary" if p.endswith("index.html") else "Flagged" if "flagged" in p else "Tier", t)
        idx = open(os.path.join(ROOT,"everypick/index.html"), encoding="utf-8").read()
        for r in self.rows: self.assertIn(r["pick"], idx)
if __name__ == "__main__": unittest.main()
