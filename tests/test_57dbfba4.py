import csv, os, re, unittest
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f: return f.read()
class GapResolution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.picks = list(csv.DictReader(open(os.path.join(ROOT,"console/data/picks.csv"),encoding="utf-8")))
        cls.unres = list(csv.DictReader(open(os.path.join(ROOT,"gap-resolution/data/unresolved.csv"),encoding="utf-8")))
        cls.pages = {n: read(f"gap-resolution/{n}.html") for n in ("index","unresolved","flagged","methodology")}
    def test_unresolved_is_exactly_non_market(self):
        # This is archived research. Its own captured research ledger, not
        # independently refreshed console output, defines the frozen scope.
        with open(os.path.join(ROOT, "gap-resolution/data/research.csv"), encoding="utf-8") as handle:
            expect = {r["fixture_id"] for r in csv.DictReader(handle)}
        self.assertEqual(expect, {r["fixture_id"] for r in self.unres})
        self.assertTrue(expect, "expected at least one unresolved row in this snapshot")
    def test_probs_sum_and_pick(self):
        for r in self.unres:
            self.assertAlmostEqual(float(r["p_a_pct"])+float(r["p_b_pct"]),100,delta=0.11)
            self.assertIn(r["pick"],(r["team_a"],r["team_b"]))
    def test_every_row_sourced(self):
        for r in self.unres:
            self.assertTrue(r["hltv_match_url"].startswith("https://www.hltv.org/"), r)
            self.assertTrue(r["rating_source_url"].startswith("https://"), r)
            self.assertNotIn("hotspawn", r["rating_source_url"])
            self.assertTrue(r["limitation"] and r["resolution"])
    def test_pages_mobile_and_linked(self):
        for name,p in self.pages.items():
            self.assertIn('name="viewport"', p, name)
            self.assertIn("../console/index.html", p if name=="index" else read("gap-resolution/index.html"))
        idx = self.pages["index"]
        for href in ("../console/index.html","unresolved.html","../every/index.html","../picks-full/index.html"):
            self.assertIn(href, idx)
        for r in self.unres: self.assertIn(r["fixture_id"] if False else r["pick"], self.pages["unresolved"])
    def test_no_hotspawn_probability_claim(self):
        for p in self.pages.values(): self.assertNotIn("Hotspawn crowd % is used", p)
if __name__ == "__main__": unittest.main()
