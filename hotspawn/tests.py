#!/usr/bin/env python3
"""Invariants for the every-match board (session arena/22be6967).  Run: python3 hotspawn/tests.py

The refresh workflow publishes new pages only when every test here passes.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import collect  # noqa: E402
import model  # noqa: E402
from common import (Aliases, devig_two_way, norm_name, normalise_prices, own_line,  # noqa: E402
                    parse_iso, read_json)

BOARD = read_json(HERE / "data" / "board.json", {}) or {}
ROWS = BOARD.get("rows", [])
OPEN = [r for r in ROWS if r.get("status") == "open"]
PAGES = ["index.html", "picks.html", "strategy.html", "unresolved.html", "flagged.html", "all.html", "method.html"]
DAY3 = read_json(HERE / "research" / "day3_twc2026.json", {}) or {}
DAY3_ROWS = {r.get("match_id"): r for r in ROWS}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs, self.ids, self.h1, self.scripts, self.styles, self.viewport = [], set(), 0, [], [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])
        if tag == "h1":
            self.h1 += 1
        if tag == "script" and a.get("src"):
            self.scripts.append(a["src"])
        if tag == "link" and a.get("rel") == "stylesheet":
            self.styles.append(a.get("href", ""))
        if tag == "meta" and a.get("name") == "viewport":
            self.viewport = True


class Probabilities(unittest.TestCase):
    def test_board_exists_and_has_open_rows(self):
        self.assertTrue(ROWS, "board.json has no rows")
        self.assertIn("summary", BOARD)

    def test_every_open_fixture_has_a_pick_or_is_flagged_unresolved(self):
        for r in OPEN:
            if r.get("rung") == "D":
                self.assertIsNone(r.get("pick"))
                self.assertIn("UNRESOLVED", r["flags"], r["match_id"])
            else:
                self.assertIn(r.get("pick"), (r["team_a"], r["team_b"]), r["match_id"])

    def test_probabilities_are_complements_in_range(self):
        for r in ROWS:
            if r.get("p_a") is None:
                continue
            self.assertAlmostEqual(r["p_a"] + r["p_b"], 1.0, delta=0.0011, msg=r["match_id"])
            self.assertTrue(0 < r["p_a"] < 1, r["match_id"])
            self.assertEqual(r["pick_p"], max(r["p_a"], r["p_b"]) if "COIN_FLIP" not in r["flags"] else r["pick_p"])

    def test_probability_comes_from_the_labelled_rung(self):
        for r in OPEN:
            if r["rung"] == "A":
                dv = devig_two_way(r["book"]["odds_a"], r["book"]["odds_b"])
                self.assertAlmostEqual(r["p_a"], dv[0], places=3)
            elif r["rung"] == "B":
                self.assertAlmostEqual(r["p_a"], r["pm"]["price_a"] / (r["pm"]["price_a"] + r["pm"]["price_b"]), places=3)
            elif r["rung"] == "C":
                self.assertAlmostEqual(r["p_a"], own_line(r["vrs_a"]["points"], r["vrs_b"]["points"], BOARD["meta"]["k"]), places=3)

    def test_crowd_share_never_changes_a_probability(self):
        """Mutation test: scramble every crowd field and rebuild; probabilities and picks must not move."""
        inp = model.load_inputs()
        base, _ = model.build_rows(inp)
        mutated = copy.deepcopy(inp)
        for fx in mutated["capture"]["hotspawn"]["fixtures"]:
            fx["crowd_a_ownership"], fx["crowd_b_ownership"] = 99, 1
            fx["total_picks_ownership"] = 123456
        again, _ = model.build_rows(mutated)
        for x, y in zip(base, again):
            self.assertEqual((x["p_a"], x["p_b"], x["pick"], x["rung"]), (y["p_a"], y["p_b"], y["pick"], y["rung"]), x["match_id"])

    def test_open_rows_are_really_open_and_stale_rows_really_stale(self):
        ref = parse_iso(BOARD["meta"]["reference_utc"])
        for r in ROWS:
            lock = parse_iso(r.get("lock_utc")) or parse_iso(r.get("start_utc"))
            if r["status"] == "open":
                self.assertGreater(lock, ref, r["match_id"])
            elif r["status"] == "stale":
                self.assertGreater((ref - lock).total_seconds() / 3600, model.STALE_AFTER_H, r["match_id"])

    def test_summary_counts_add_up(self):
        s = BOARD["summary"]
        self.assertEqual(s["open"], len(OPEN))
        self.assertEqual(s["open_with_pick"] + s["open_unresolved"], s["open"])
        self.assertEqual(sum(s["open_rung"].values()), s["open"])


class Sources(unittest.TestCase):
    def test_every_open_row_has_https_sources_and_a_hotspawn_link(self):
        for r in OPEN:
            self.assertTrue(r.get("sources"), r["match_id"])
            self.assertTrue(all(u.startswith("https://") for u in r["sources"]), r["match_id"])
            self.assertTrue(any("hotspawn.com" in u for u in r["sources"]), r["match_id"])

    def test_priced_rows_carry_read_times(self):
        for r in OPEN:
            if r["rung"] == "A":
                self.assertTrue(r["book"].get("read_utc"))
            if r["rung"] == "B":
                self.assertTrue(r["pm"].get("read_utc"))

    def test_research_files_are_sourced(self):
        for row in read_json(HERE / "research" / "aliases.json")["teams"]:
            self.assertTrue(row.get("evidence") and row.get("source_urls"), row["key"])
            self.assertTrue(all(u.startswith("https://") for u in row["source_urls"]))
        for n in read_json(HERE / "research" / "notes.json")["notes"]:
            self.assertIn(n.get("strength"), ("strong", "moderate", "weak"), n["team"])
            self.assertTrue(n.get("source_urls") and n.get("read_utc"), n["team"])
            self.assertTrue(all("hltv.org" in u for u in n["source_urls"]), n["team"])
        for i in read_json(HERE / "research" / "irregularities.json")["items"]:
            self.assertTrue(i.get("evidence"), i["id"])

    def test_day1_review_matches_hltv_results(self):
        d1 = {m["hotspawn_id"]: m for m in BOARD["day1"]["matches"]}
        self.assertEqual(len(d1), 4)
        self.assertEqual(d1["1080176"]["winner"], "9z")
        self.assertEqual({m["winner"] for m in d1.values()}, {"9z", "Falcons", "Legacy", "FURIA"})
        for m in d1.values():
            self.assertTrue(m["hltv"].startswith("https://www.hltv.org/matches/"))
            self.assertAlmostEqual(m["p_a"] + m["p_b"], 1.0, delta=0.001)


class Rule(unittest.TestCase):
    def mk(self, pa, own, ca, factors=None, rung="A"):
        r = {"team_a": "A", "team_b": "B", "p_a": pa, "p_b": 1 - pa, "own_p_a": own, "own_p_b": None if own is None else 1 - own,
             "crowd_a": ca, "crowd_b": 100 - ca, "points": 7, "rung": rung, "flags": [], "factors": factors or []}
        r["pick"] = "A" if pa >= 0.5 else "B"
        return model.strategy(r)

    def test_value_when_crowd_backs_the_underdog(self):
        self.assertEqual(self.mk(0.60, 0.60, 17)["class"], "VALUE")
        self.assertEqual(self.mk(0.60, 0.60, 17)["leaderboard_pick"], "A")

    def test_contrarian_needs_every_estimate_to_agree(self):
        self.assertEqual(self.mk(0.58, 0.43, 73)["class"], "CONTRARIAN")           # Legacy-FURIA shape
        self.assertNotEqual(self.mk(0.577, 0.80, 75)["class"], "CONTRARIAN")       # day-1 Legacy-PARIVISION shape

    def test_situational_needs_a_counting_factor_against_the_favourite(self):
        # A = underdog (9z-like), B = favourite.  A strong factor against the UNDERDOG blocks the play.
        vs_dog = [{"side": "a", "argues_against": True, "strength": "strong", "kind": "stand-in"}]
        weak = [{"side": "a", "argues_against": True, "strength": "weak", "kind": "schedule"}]
        self.assertEqual(self.mk(0.269, 0.3875, 5, vs_dog)["class"], "LONG SHOT")
        self.assertEqual(self.mk(0.269, 0.3875, 5, [])["class"], "LONG SHOT")       # no factor at all
        aurora = [{"side": "b", "argues_against": True, "strength": "moderate", "kind": "roster change"}]
        res = self.mk(1 - 0.731, 0.3875, 5, aurora)                                  # 9z-Aurora: A=9z underdog, B=Aurora
        self.assertEqual(res["class"], "SITUATIONAL")
        self.assertEqual(res["leaderboard_pick"], "A")
        self.assertEqual(self.mk(0.70, 0.65, 90, weak)["class"], "LONG SHOT")       # weak factor never counts

    def test_chalk_and_long_shot(self):
        self.assertEqual(self.mk(0.80, 0.85, 80)["class"], "CHALK")
        self.assertEqual(self.mk(0.76, 0.70, 94)["class"], "LONG SHOT")


class Parsers(unittest.TestCase):
    def test_devig(self):
        pa, pb, over = devig_two_way(3.95, 1.260417)
        self.assertAlmostEqual(pa + pb, 1.0)
        self.assertAlmostEqual(pa, 0.2419, places=3)
        self.assertIsNone(devig_two_way(1.0, 2.0))

    def test_aliases(self):
        al = Aliases()
        self.assertEqual(al.key("WROTBERRY"), al.key("WBT"))
        self.assertEqual(al.key("RoundsGG"), al.key("ROUNDS"))
        self.assertEqual(al.key("BB Team"), al.key("BetBoom"))
        self.assertEqual(al.key("Team Falcons"), al.key("Falcons"))
        self.assertNotEqual(al.key("EAC Extra"), al.key("EAC"))
        self.assertEqual(al.key("Esport Academy Copenhagen"), al.key("EAC"))
        self.assertEqual(norm_name("BC.Game Esports"), norm_name("BC.Game"))

    def test_polymarket_question(self):
        m = collect.PM_QUESTION.match("Counter-Strike: 9z vs Team Falcons (BO3) - Thunderpick World Championship Group A")
        self.assertEqual((m.group("a"), m.group("b"), m.group("fmt")), ("9z", "Team Falcons", "BO3"))

    def test_hltv_ranking_parser(self):
        html = ('<div class="ranked-team standard-box"><span class="position wide-position">#1</span><a href="/team/7020/spirit">x</a>'
                '<span class="name">Spirit</span><span class="points">(972<span> HLTV</span> points)</span>'
                '<div class="rankingNicknames"><span>donk</span></div></div>')
        t = collect.parse_hltv_ranking(html)["teams"][0]
        self.assertEqual((t["rank"], t["name"], t["points"], t["players"]), (1, "Spirit", 972, ["donk"]))

    def test_save_raw_round_trip(self):
        import gzip as _gz
        from common import RAW, save_raw
        rel = save_raw("unit_test_probe", "{\"ok\": true}")
        path = RAW / "unit_test_probe.json.gz"
        try:
            self.assertTrue(rel.endswith("hotspawn/data/raw/unit_test_probe.json.gz"))
            self.assertEqual(_gz.decompress(path.read_bytes()), b'{"ok": true}')
            self.assertEqual(path.read_bytes(), save_raw("unit_test_probe", "{\"ok\": true}") and path.read_bytes())
        finally:
            path.unlink(missing_ok=True)

    def test_valve_standings_parser(self):
        line = "| 17       |   1543 | 9z                   | dgt, HUASOPEEK, luchov, max, meyern                   | [details](details/2026_10_05/0017--9z--dgt-huasopeek-luchov-max-meyern.md) |"
        row = collect.parse_standings(line)[0]
        self.assertEqual((row["rank"], row["points"], row["name"]), (17, 1543, "9z"))


class Pages(unittest.TestCase):
    def test_pages_exist_mobile_ready_and_self_contained(self):
        for name in PAGES:
            text = (HERE / name).read_text(encoding="utf-8")
            p = Links()
            p.feed(text)
            self.assertEqual(p.h1, 1, name)
            self.assertTrue(p.viewport, name)
            self.assertEqual(p.scripts, [], f"{name} loads an external script")
            self.assertTrue(all(not s.startswith("http") for s in p.styles), name)
            self.assertNotRegex(text, r"\bundefined\b|\bNone\b(?![a-z])", name)

    def test_internal_links_resolve(self):
        for name in PAGES:
            p = Links()
            p.feed((HERE / name).read_text(encoding="utf-8"))
            for href in p.hrefs:
                u = urlparse(href)
                if u.scheme or href.startswith("mailto:"):
                    continue
                target = (HERE / u.path).resolve() if u.path else HERE / name
                self.assertTrue(target.exists(), f"{name} -> {href}")
                if u.fragment and target.name.endswith(".html"):
                    q = Links()
                    q.feed(target.read_text(encoding="utf-8"))
                    self.assertIn(u.fragment, q.ids, f"{name} -> {href}")

    def test_picks_page_shows_every_open_fixture_with_both_probabilities(self):
        text = (HERE / "picks.html").read_text(encoding="utf-8")
        for r in OPEN:
            self.assertIn(f'id="m{r["match_id"]}"', text)
        self.assertEqual(text.count('class="card"'), len(OPEN))

    def test_executive_summary_contains_unresolved_section(self):
        text = (HERE / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="unresolved"', text)
        self.assertIn("Limitations that apply to every pick", text)
        self.assertIn('href="picks.html"', text)


class Day3(unittest.TestCase):
    """Thunderpick day-3 evidence file: raw inputs only, every price a real two-way book, official
    points agreeing with the board's own Valve table, and the section rendered + linked."""

    def test_research_file_stores_raw_inputs_only(self):
        matches = DAY3.get("matches") or []
        self.assertTrue(matches, "research/day3_twc2026.json has no matches")
        for m in matches:
            mid = m.get("hotspawn_id")
            self.assertTrue(str(m.get("hltv_match_url", "")).startswith("https://www.hltv.org/matches/"), mid)
            self.assertTrue(m.get("stage"), mid)
            self.assertTrue(m.get("team_a") and m.get("team_b"), mid)
            self.assertTrue(str(m.get("start_utc", "")).endswith("Z"), mid)
            self.assertTrue(m.get("crowd") and m["crowd"].get("source_url", "").startswith("https://"), mid)
            self.assertTrue(m.get("markets"), mid)
            self.assertTrue(m.get("own_line", {}).get("source_url", "").startswith("https://"), mid)
            self.assertTrue(m["own_line"].get("as_of"), mid)
            self.assertTrue(m.get("limitations"), mid)
            for mk in m["markets"]:
                self.assertTrue(str(mk.get("url", "")).startswith("https://"), mid)
                self.assertTrue(mk.get("read_utc"), mid)
                self.assertTrue(mk.get("team_a") and mk.get("team_b"), mid)
                self.assertTrue(mk.get("kind"), mid)
        # no hand-typed probabilities anywhere in the file: only raw inputs (odds, prices, points, shares)
        banned = {"p_a", "p_b", "prob", "probability", "devig_a", "devig_b", "devig_pct", "consensus_pct",
                  "win_prob", "win_pct", "model_p", "p_dog", "p_fav"}

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotIn(str(key).lower(), banned, f"derived field {path}/{key} must be computed at build time")
                    walk(value, f"{path}/{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")

        walk(DAY3)

    def test_every_stored_price_is_a_usable_two_way_market(self):
        for m in DAY3.get("matches") or []:
            for mk in m["markets"]:
                if mk.get("odds_a") is not None and mk.get("odds_b") is not None:
                    dv = devig_two_way(float(mk["odds_a"]), float(mk["odds_b"]))
                    self.assertIsNotNone(dv, mk.get("label"))
                    self.assertAlmostEqual(dv[0] + dv[1], 1.0, delta=1e-6, msg=mk.get("label"))
                else:
                    nrm = normalise_prices(float(mk["price_a"]), float(mk["price_b"]))
                    self.assertIsNotNone(nrm, mk.get("label"))
                    self.assertAlmostEqual(nrm[0] + nrm[1], 1.0, delta=1e-6, msg=mk.get("label"))

    def test_points_and_times_agree_with_the_board(self):
        for m in DAY3.get("matches") or []:
            row = DAY3_ROWS.get(m.get("hotspawn_id"))
            if not row:
                continue                     # fixture not in this snapshot; nothing to cross-check
            self.assertEqual(m["team_a"], row["team_a"], m["hotspawn_id"])
            self.assertEqual(m["team_b"], row["team_b"], m["hotspawn_id"])
            self.assertEqual(m["start_utc"], row["start_utc"], m["hotspawn_id"])
            if m.get("lock_utc"):
                self.assertEqual(m["lock_utc"], row["lock_utc"], m["hotspawn_id"])
            ol = m["own_line"]
            pts = {norm_name(ol["team_a"]): ol["points_a"], norm_name(ol["team_b"]): ol["points_b"]}
            for side, team in (("vrs_a", row["team_a"]), ("vrs_b", row["team_b"])):
                vrs = row.get(side) or {}
                if vrs.get("points") is None:
                    continue
                self.assertEqual(pts.get(norm_name(team)), vrs["points"],
                                 f"{m['hotspawn_id']} {team}: research points must equal Valve's official table")

    def test_section_is_rendered_and_linked(self):
        strategy = (HERE / "strategy.html").read_text(encoding="utf-8")
        index = (HERE / "index.html").read_text(encoding="utf-8")
        picks = (HERE / "picks.html").read_text(encoding="utf-8")
        self.assertIn('id="day3"', strategy)
        self.assertIn('id="day3"', index)
        self.assertIn("strategy.html#day3", picks)
        for m in DAY3.get("matches") or []:
            self.assertIn(m["hltv_match_url"], strategy, m["hotspawn_id"])


    def test_coverage_gaps_are_surfaced_when_they_exist(self):
        """A researched fixture that the live capture missed must be named on the unresolved page and the
        executive summary (never silently dropped), and vanish again once the board picks it up."""
        board = BOARD
        have = {str(r.get("match_id")) for r in board.get("rows", [])}
        gaps = [m for m in DAY3.get("matches") or [] if str(m.get("hotspawn_id")) not in have]
        for name in ("unresolved.html", "index.html"):
            page = (HERE / name).read_text(encoding="utf-8")
            if gaps:
                self.assertIn("Coverage gap — a fixture Hotspawn lists", page, f"{name} should flag the gap")
                for m in gaps:
                    self.assertIn(m["team_a"], page, name)
                    self.assertIn(m["team_b"], page, name)
                    self.assertIn(m["hotspawn_id"], page, name)
                    self.assertIn(f"strategy.html#day3", page, name)
            else:
                self.assertNotIn("Coverage gap — a fixture Hotspawn lists", page, f"{name} should not claim a gap once covered")

    def test_fallback_lean_is_computed_not_typed(self):
        """A researched decider with no board row still shows a pick, and it is the outside-market + own-line
        consensus recomputed from the stored raw inputs - never a hand-typed percentage."""
        board = BOARD
        have = {str(r.get("match_id")) for r in board.get("rows", [])}
        strategy = (HERE / "strategy.html").read_text(encoding="utf-8")
        for m in DAY3.get("matches") or []:
            if str(m.get("hotspawn_id")) in have:
                continue                       # the board has a row: its own pick and rung are rendered instead
            self.assertIn("no board row", strategy, m["hotspawn_id"])
            self.assertIn("outside market + our line only", strategy, m["hotspawn_id"])

if __name__ == "__main__":
    result = unittest.main(verbosity=1, exit=False).result
    sys.exit(0 if result.wasSuccessful() else 1)
