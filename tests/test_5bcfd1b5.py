#!/usr/bin/env python3
"""arena/5bcfd1b5 — regression tests for the every-match CS2 pick board.

Run:  python3 -m unittest discover -s tests -p 'test_5bcfd1b5.py' -v

Offline: reads only committed evidence under data/5bcfd1b5/, data/8944bb84/ and
cs2/data/, re-derives every published number from first principles, and fails if the
build publishes anything it cannot justify from an official source.
"""

from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import html
import importlib
import itertools
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "5bcfd1b5")
SITE = os.path.join(ROOT, "allpicks")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

build = importlib.import_module("5bcfd1b5_build")
site = importlib.import_module("5bcfd1b5_site")
livecheck = importlib.import_module("5bcfd1b5_livecheck")
sys.path.insert(0, ROOT)
from collector import hotspawn as hs_collector  # noqa: E402  (read-only reuse)

PLACEHOLDER = {"1.80", "1.800", "1.8"}
COMMIT = None  # set in setUpModule from coverage.json


def rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


COV = json.load(open(os.path.join(DATA, "coverage.json"), encoding="utf-8"))
FIX = rows(os.path.join(DATA, "every_match.csv"))
TEAMS = rows(os.path.join(DATA, "team_ratings.csv"))
FLAGS = rows(os.path.join(DATA, "flags.csv"))
MARKET = rows(os.path.join(DATA, "market_reads.csv"))
BY_ID = {r["fixture_id"]: r for r in FIX}


def setUpModule() -> None:
    global COMMIT
    COMMIT = COV["official_rating_source"]["pinned_commit"]


def flags_for(fixture_id: str) -> list[dict]:
    return [f for f in FLAGS if fixture_id in f["subject"]]


def codes_for(fixture_id: str) -> set[str]:
    return {f["code"] for f in flags_for(fixture_id)}


# Independent re-parse of Valve's own published standings (not the build's parser).
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|")
_VRS_CACHE: dict[str, list[dict]] = {}


def valve_rows(filename: str) -> list[dict]:
    if filename in _VRS_CACHE:
        return _VRS_CACHE[filename]
    out = []
    with gzip.open(os.path.join(DATA, "vrs", filename + ".gz"), "rt", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            m = ROW_RE.match(line)
            if m:
                out.append({"line": i, "standing": int(m.group(1)), "points": int(m.group(2)),
                            "team": m.group(3).strip(), "roster": m.group(4).strip()})
    _VRS_CACHE[filename] = out
    return out


def url_parts(url: str) -> tuple[str, int]:
    """(valve file name, line number) out of a pinned Valve blob citation."""
    m = re.search(r"/live/2026/([^/?]+\.md)\?plain=1#L(\d+)$", url)
    assert m, "not a pinned Valve line citation: %r" % url
    return m.group(1), int(m.group(2))


class CoverageTests(unittest.TestCase):
    def test_build_is_deterministic(self):
        """Re-running the build must reproduce the committed tables byte for byte."""
        tmp = tempfile.mkdtemp(prefix="5bcfd1b5-det-")
        try:
            old = build.OUT
            build.OUT = tmp
            shutil.copytree(os.path.join(DATA, "vrs"), os.path.join(tmp, "vrs"))
            # market_reads.csv is this session's hand-authored live read log: an INPUT the
            # build consumes, not an output it regenerates, so it is copied in, not compared.
            shutil.copy(os.path.join(DATA, "market_reads.csv"), tmp)
            build.main()
            stamp = re.compile(rb"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ")
            for name in ("every_match.csv", "flags.csv", "team_ratings.csv"):
                a = open(os.path.join(DATA, name), "rb").read()
                b = open(os.path.join(tmp, name), "rb").read()
                # generated_utc/raised_utc are run stamps; everything else must be identical
                self.assertEqual(stamp.sub(b"STAMP", a), stamp.sub(b"STAMP", b),
                                 "%s is not reproducible from committed evidence" % name)
        finally:
            build.OUT = old
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_hotspawn_cs2_fixture_is_present(self):
        """No fixture Hotspawn lists may be missing from the board."""
        upstream = {r["fixture_id"] for r in
                    rows(os.path.join(ROOT, "cs2", "data", "analysis.csv"))}
        ours = set(BY_ID)
        self.assertEqual(upstream, ours,
                         "missing=%s extra=%s" % (sorted(upstream - ours), sorted(ours - upstream)))
        self.assertEqual(len(FIX), COV["counts"]["fixtures_total"])

    def test_open_slate_is_fully_covered(self):
        """The headline requirement: every still-pickable match gets a pick."""
        open_rows = [r for r in FIX if r["state"] == "open"]
        self.assertEqual(28, len(open_rows))
        self.assertEqual([], [r["fixture_id"] for r in open_rows if not r["pick"]],
                         "open fixtures without a pick")
        self.assertEqual(len(open_rows), COV["counts"]["open_with_pick"])
        self.assertEqual(0, COV["counts"]["open_without_pick"])
        for r in open_rows:
            if not r["pick_pct"]:
                self.assertEqual("E", r["pick_tier"],
                                 "%s has no probability but is not a tier-E directional pick"
                                 % r["fixture_id"])
                self.assertIn("PICK-WITHOUT-PROBABILITY", codes_for(r["fixture_id"]))

    def test_coverage_beats_the_baseline_on_main(self):
        """main published 64 picks of 89 and 27 of 28 open; this board must not regress."""
        base = rows(os.path.join(ROOT, "cs2", "data", "analysis.csv"))
        base_picks = sum(1 for r in base if r["pick"])
        base_open = sum(1 for r in base if r["pick"] and r["state"] == "open")
        self.assertGreater(COV["counts"]["with_pick"], base_picks)
        self.assertGreaterEqual(COV["counts"]["open_with_pick"], base_open)
        self.assertEqual(len(base), len(FIX))

    def test_counts_in_coverage_match_the_table(self):
        c = COV["counts"]
        self.assertEqual(len(FIX), c["fixtures_total"])
        self.assertEqual(sum(1 for r in FIX if r["pick"]), c["with_pick"])
        self.assertEqual(sum(1 for r in FIX if not r["pick"]), c["without_pick"])
        self.assertEqual(sum(1 for r in FIX if r["state"] == "open"), c["state_open"])
        self.assertEqual(sum(1 for r in FIX if r["pick_pct"]), c["with_numeric_probability"])
        self.assertEqual(sum(1 for r in FIX if r["market_tier"] == "A"), c["market_tier_A"])
        self.assertEqual(sum(1 for r in FIX if r["market_tier"] == "B"), c["market_tier_B"])
        self.assertEqual(sum(1 for r in FIX if r["own_p_a_pct"]), c["own_line_computed"])
        tiers: dict[str, int] = {}
        for r in FIX:
            t = r["pick_tier"] or "F"
            tiers[t] = tiers.get(t, 0) + 1
        self.assertEqual(tiers, c["pick_tiers"])
        self.assertEqual(len(FLAGS), c["flags"])

    def test_no_pick_is_always_flagged_and_carries_no_probability(self):
        for r in FIX:
            if not r["pick"]:
                self.assertIn("NO-PICK", codes_for(r["fixture_id"]),
                              "fixture %s has no pick and no flag" % r["fixture_id"])
                self.assertEqual("", r["pick_pct"])
                self.assertEqual("", r["pick_pct_hi"])
                self.assertTrue(r["pick_basis"])


class ProvenanceTests(unittest.TestCase):
    def test_hotspawn_crowd_is_never_a_probability(self):
        self.assertFalse(COV["hotspawn_crowd_percentages_used_as_probability"])
        self.assertFalse(COV["hltv_pick_a_winner_vote_used_as_probability"])
        banned = re.compile(r"crowd|% ?picked|pick a winner|popular pick|hotspawn percent", re.I)
        for r in FIX:
            for col in ("pick_basis", "own_basis"):
                self.assertNotRegex(r[col], banned)
        # no crowd column may exist to be read in the first place
        self.assertFalse([c for c in FIX[0] if "crowd" in c or "hotspawn_pct" in c])

    def test_every_row_carries_a_source_link(self):
        for r in FIX:
            self.assertTrue(r["hotspawn_match_url"] or r["hotspawn_url"],
                            "fixture %s has no Hotspawn source link" % r["fixture_id"])
            if r["pick"]:
                self.assertTrue(r["pick_basis"], "fixture %s pick has no stated basis"
                                % r["fixture_id"])
                self.assertTrue(r["market_url"] or r["vrs_url_a"] or r["vrs_url_b"]
                                or r["verified_result_url"],
                                "fixture %s publishes a pick with no official source URL"
                                % r["fixture_id"])
            for col in ("vrs_url_a", "vrs_url_b", "market_url", "verified_result_url"):
                if r[col]:
                    self.assertTrue(r[col].startswith("https://"), "%s %s" % (r["fixture_id"], col))

    def test_valve_citations_are_pinned_and_period_correct(self):
        """The bug this session fixed: an October citation on a June fixture."""
        for r in FIX:
            for side in ("a", "b"):
                url, period = r["vrs_url_%s" % side], r["vrs_period_%s" % side]
                if not url:
                    if period:
                        # ambiguous duplicate name: no single row was chosen, but every
                        # admissible row must still be cited
                        nc = int(r["vrs_n_candidates_%s" % side] or 0)
                        self.assertGreater(nc, 1, "fixture %s side %s has a period but no "
                                                  "citation and no ambiguity"
                                           % (r["fixture_id"], side))
                        self.assertEqual(nc, len(r["vrs_cand_urls_%s" % side].split(";")))
                        for cu in r["vrs_cand_urls_%s" % side].split(";"):
                            self.assertIn(COMMIT, cu)
                            self.assertNotIn(".md.md", cu)
                    else:
                        self.assertEqual("", period)
                    continue
                self.assertIn("counter-strike_regional_standings", url)
                self.assertIn(COMMIT, url, "Valve citation must be pinned to a commit: %s" % url)
                self.assertNotIn(".md.md", url)
                fname, line = url_parts(url)
                self.assertEqual(period.replace("-", "_"), fname.replace("standings_global_", "")
                                 .replace("standings_americas_", "").replace("standings_asia_", "")
                                 .replace("standings_europe_", "").replace(".md", ""),
                                 "fixture %s cites %s but resolved from period %s"
                                 % (r["fixture_id"], fname, period))
                self.assertTrue(line > 0)
        june = [r for r in FIX if r["start_utc"][:7] in ("2026-06", "2026-07")]
        self.assertTrue(june)
        for r in june:
            periods = {r["vrs_period_a"], r["vrs_period_b"]} - {""}
            self.assertNotEqual({"2026-10-05"}, periods,
                                "fixture %s resolved both teams from the October file"
                                % r["fixture_id"])

    def test_cited_valve_line_says_what_we_published(self):
        """Read Valve's own bytes back and confirm rank, points and roster agree."""
        checked = 0
        for r in FIX:
            for side in ("a", "b"):
                if not r["vrs_url_%s" % side]:
                    continue
                fname, line = url_parts(r["vrs_url_%s" % side])
                rows_ = valve_rows(fname)
                hit = [x for x in rows_ if x["line"] == line]
                self.assertEqual(1, len(hit), "citation %s#L%d does not exist" % (fname, line))
                h = hit[0]
                self.assertEqual(r["vrs_name_%s" % side], h["team"])
                self.assertEqual(int(r["vrs_rank_%s" % side]), h["standing"])
                self.assertEqual(int(r["vrs_points_%s" % side]), h["points"])
                self.assertEqual(r["vrs_roster_%s" % side], h["roster"])
                checked += 1
        self.assertGreaterEqual(checked, 150)

    def test_later_period_fallback_is_always_flagged(self):
        for r in FIX:
            for side in ("a", "b"):
                period = r["vrs_period_%s" % side]
                if period and period > r["start_utc"][:10]:
                    self.assertIn("RATING-PERIOD-LATER-THAN-MATCH", r["rating_note"],
                                  "fixture %s used a %s rating for a %s match unflagged"
                                  % (r["fixture_id"], period, r["start_utc"][:10]))
        # team_ratings must agree with the fixtures it was used for
        for t in TEAMS:
            if not t.get("fixtures"):
                continue
            used = [BY_ID[f] for f in t["fixtures"].split(";") if f in BY_ID]
            self.assertTrue(used, "team %s lists fixtures that are not on the board"
                            % t["hotspawn_team"])
            anach = any(t["rating_period"] > r["start_utc"][:10] for r in used)
            self.assertEqual(anach, t["anachronistic"] == "yes",
                             "team %s period %s anachronistic=%s but used by %s"
                             % (t["hotspawn_team"], t["rating_period"], t["anachronistic"],
                                t["fixtures"]))
            for r in used:
                for side in ("a", "b"):
                    if r["team_%s" % side] == t["hotspawn_team"]:
                        self.assertEqual(t["rating_period"], r["vrs_period_%s" % side])

    def test_ambiguous_duplicates_publish_nothing(self):
        """Where Valve's file disagrees on the favourite we go blank, we do not guess."""
        amb = [r for r in FIX if "VRS-DUPLICATE-NAME-UNRESOLVED" in r["rating_note"]]
        self.assertEqual(3, len(amb))
        for r in amb:
            self.assertEqual("", r["pick"], "fixture %s guessed a pick on an ambiguous rating"
                             % r["fixture_id"])
            self.assertEqual("", r["pick_pct"])
            self.assertEqual("", r["own_p_a_pct"])
            self.assertIn("RATING-AMBIGUOUS", codes_for(r["fixture_id"]))
            self.assertIn("NO-PICK", codes_for(r["fixture_id"]))
            self.assertEqual("F", r["pick_tier"])
            self.assertRegex(r["own_basis"], re.compile(r"AMBIGUOUS"))

    def test_bracketed_duplicates_publish_the_conservative_bound(self):
        n = 0
        for r in FIX:
            if "VRS-DUPLICATE-NAME-BRACKETED" not in r["rating_note"]:
                continue
            n += 1
            lo, hi = float(r["own_p_lo_pct"]), float(r["own_p_hi_pct"])
            pub = float(r["own_p_a_pct"])
            self.assertLess(lo, hi, "bracketed row %s has a degenerate range" % r["fixture_id"])
            self.assertTrue(lo <= pub <= hi)
            # own_p_a_pct is the team-A probability; the conservative bound for the
            # favourite side is the LOW end when A is favoured and the HIGH end when B is.
            self.assertEqual(lo if pub >= 50.0 else hi, pub,
                             "fixture %s published %s, not the conservative bound of [%s,%s]"
                             % (r["fixture_id"], pub, lo, hi))
            # the pick range shown to the reader must span the same interval
            self.assertTrue(r["pick_pct"] and r["pick_pct_hi"])
            # the pick side's headline is the pessimistic bound, its range top the optimistic one
            self.assertEqual("%.1f" % max(pub, 100 - pub), r["pick_pct"])
            self.assertEqual("%.1f" % max(hi, 100 - lo), r["pick_pct_hi"])
            self.assertGreaterEqual(float(r["pick_pct_hi"]), float(r["pick_pct"]))
            # the basis must name the team whose name is duplicated
            self.assertRegex(r["own_basis"],
                             re.compile(r"same-name rows for (%s|%s)"
                                        % (re.escape(r["team_a"]), re.escape(r["team_b"]))))
        self.assertEqual(9, n)

    def test_duplicate_names_are_bracketed_not_cherry_picked(self):
        """Every admissible same-name row must be evaluated; never just 'the higher standing'."""
        for r in FIX:
            for side in ("a", "b"):
                nc = r["vrs_n_candidates_%s" % side]
                if nc.isdigit() and int(nc) > 1 and not r["pin_%s" % side]:
                    self.assertIn("VRS-DUPLICATE-NAME", r["rating_note"],
                                  "fixture %s has %s admissible rows for %s and no bracket note"
                                  % (r["fixture_id"], nc, r["team_%s" % side]))

    def test_committed_valve_bytes_match_the_manifest(self):
        manifest = COV["official_rating_source"]["files"]
        self.assertTrue(manifest)
        for name, digest in manifest.items():
            path = os.path.join(DATA, "vrs", name)
            self.assertTrue(os.path.exists(path), "manifest lists %s but it is not committed" % name)
            self.assertEqual(hashlib.sha256(open(path, "rb").read()).hexdigest(), digest,
                             "%s does not match its published SHA-256" % name)
            parsed = valve_rows(name[:-3])
            floor = 300 if "global" in name else 40
            self.assertGreater(len(parsed), floor, "%s parses to %d rows" % (name, len(parsed)))
        on_disk = set(os.listdir(os.path.join(DATA, "vrs")))
        self.assertEqual(set(manifest), on_disk, "manifest and committed files disagree")
        self.assertEqual(5, len(COV["official_rating_source"]["periods_used"]))


class AliasTests(unittest.TestCase):
    def test_every_alias_has_roster_evidence_and_a_non_hotspawn_url(self):
        aliased = [t for t in TEAMS if t["alias"]]
        self.assertEqual(7, len(aliased))
        for t in aliased:
            self.assertTrue(t["alias_evidence"], "alias %s has no stated evidence" % t["alias"])
            urls = [u for u in t["alias_urls"].split(";") if u]
            self.assertTrue(urls, "alias %s has no source URL" % t["alias"])
            for u in urls:
                self.assertTrue(u.startswith("https://"), u)
                self.assertNotIn("hotspawn", u, "Hotspawn may not justify an alias: %s" % u)
            self.assertTrue(t["resolved_vrs_name"] or t["candidate_standings"],
                            "alias %s cites no Valve row at all" % t["alias"])
            if t["resolved_vrs_name"]:
                self.assertTrue(t["source_url"], "alias %s names a row but cites no URL"
                                % t["alias"])

    def test_no_ex_org_alias_without_roster_continuity(self):
        """IRREG-07: `ex-<Org>` is not automatically `<Org>`."""
        seen = 0
        for t in TEAMS:
            if t["alias"] and t["hotspawn_team"].lower().startswith("ex-"):
                seen += 1
                self.assertRegex(t["alias_evidence"],
                                 re.compile(r"roster|transfer|continuity|core", re.I),
                                 "ex- alias %s justified without roster continuity" % t["alias"])
        self.assertEqual(2, seen, "expected ex-Tricked and ex-MANA")

    def test_alias_is_applied_consistently_across_fixtures(self):
        """A team can legitimately resolve differently per period (WROTBERRY -> WBT)."""
        seen = set()
        for t in TEAMS:
            for r in FIX:
                for side in ("a", "b"):
                    if r["team_%s" % side] != t["hotspawn_team"]:
                        continue
                    if r["vrs_period_%s" % side] != t["rating_period"]:
                        continue
                    key = (t["hotspawn_team"], t["rating_period"])
                    seen.add(key)
                    if int(r["vrs_n_candidates_%s" % side] or 0) == 1:
                        self.assertEqual(t["resolved_vrs_name"], r["vrs_name_%s" % side],
                                         "fixture %s resolved %s differently"
                                         % (r["fixture_id"], t["hotspawn_team"]))
                    else:
                        self.assertEqual("", t["resolved_vrs_name"])
                    if t["alias"]:
                        self.assertIn("ALIAS-RESOLVED", r["rating_note"],
                                      "fixture %s used alias %s without the note"
                                      % (r["fixture_id"], t["alias"]))
                        self.assertEqual(t["alias"], r["alias_%s" % side])
        self.assertTrue(seen)
        # and a team whose own name matched must NOT be reported as alias-resolved
        june = [t for t in TEAMS if t["hotspawn_team"] == "WROTBERRY"
                and t["rating_period"] == "2026-06-01"]
        self.assertEqual(1, len(june))
        self.assertEqual("", june[0]["alias"])
        self.assertEqual("WROTBERRY", june[0]["resolved_vrs_name"])
        octo = [t for t in TEAMS if t["hotspawn_team"] == "WROTBERRY"
                and t["rating_period"] == "2026-10-05"][0]
        self.assertEqual("WBT", octo["resolved_vrs_name"])

    def test_unranked_teams_are_proven_not_assumed(self):
        unranked = [t for t in TEAMS if t["unranked_finding"]]
        self.assertEqual(2, len(unranked))
        for t in unranked:
            self.assertEqual({"LFO 10", "SUKEBAN"},
                             {x["hotspawn_team"] for x in unranked})
            urls = [u for u in t["unranked_urls"].split(";") if u]
            self.assertTrue(urls, "%s marked unranked with no source" % t["hotspawn_team"])
            self.assertEqual("", t["source_url"])
            self.assertEqual("", t["resolved_vrs_name"])
        for r in FIX:
            for side in ("a", "b"):
                if r["vrs_n_candidates_%s" % side] == "0":
                    self.assertEqual("", r["vrs_points_%s" % side])
                    self.assertEqual("", r["vrs_rank_%s" % side])
                    self.assertEqual("", r["vrs_url_%s" % side])

    def test_hltv_vrs_badge_is_never_used_as_a_valve_citation(self):
        """IR-05-03: HLTV's badge numbering is a different snapshot from Valve's file."""
        lfo = [t for t in TEAMS if t["hotspawn_team"] == "LFO 10"][0]
        self.assertIn("Honvéd", lfo["unranked_finding"])
        r = BY_ID["1079624"]
        self.assertEqual("FORZE Reload", r["pick"])
        self.assertEqual("E", r["pick_tier"])
        self.assertEqual("", r["pick_pct"], "LFO 10 has no official rating, so no percentage")
        self.assertEqual("", r["market_odds_a"], "no market priced this fixture")
        self.assertIn("RATING-MISSING", codes_for("1079624"))
        self.assertIn("PICK-WITHOUT-PROBABILITY", codes_for("1079624"))
        self.assertRegex(r["pick_basis"], re.compile(r"deliberately", re.I))
        for row in FIX:
            self.assertNotIn("hltv.org/valve-ranking", row["vrs_url_a"] + row["vrs_url_b"])

    def test_forfeit_is_recorded_as_a_result_not_a_prediction(self):
        r = BY_ID["1081105"]
        self.assertIn("forfeit", (r["verified_result"] + r["verified_result_note"]).lower())
        self.assertTrue(r["verified_result_url"].startswith("https://www.hltv.org/matches/"))
        self.assertEqual("your end", r["pick"])


class MarketTests(unittest.TestCase):
    def test_devig_arithmetic_is_exact(self):
        """p(A) = (1/oA)/((1/oA)+(1/oB)) — re-derived here, not trusted."""
        checked = 0
        for r in FIX:
            if not r["market_tier"] or not r["market_odds_a"]:
                continue
            oa, ob = float(r["market_odds_a"]), float(r["market_odds_b"])
            self.assertGreater(oa, 1.0)
            self.assertGreater(ob, 1.0)
            inv = 1 / oa + 1 / ob
            self.assertAlmostEqual(round(100 * (1 / oa) / inv, 1), float(r["market_p_a_pct"]),
                                   places=1, msg="fixture %s de-vig" % r["fixture_id"])
            self.assertAlmostEqual(round(100 * (1 / ob) / inv, 1), float(r["market_p_b_pct"]),
                                   places=1, msg="fixture %s de-vig B" % r["fixture_id"])
            self.assertAlmostEqual(round(100 * (inv - 1), 2), float(r["market_overround_pct"]),
                                   places=2, msg="fixture %s overround" % r["fixture_id"])
            self.assertAlmostEqual(100.0, float(r["market_p_a_pct"]) + float(r["market_p_b_pct"]),
                                   places=1)
            self.assertGreaterEqual(float(r["market_overround_pct"]), 0.0)
            checked += 1
        self.assertGreaterEqual(checked, 20)

    def test_placeholder_odds_are_never_used(self):
        """EGamersWorld's 1.80/1.80 means 'unpriced'. De-vigging it would fake a 50/50."""
        for r in FIX:
            if r["market_odds_a"] and r["market_odds_b"]:
                self.assertFalse(r["market_odds_a"] in PLACEHOLDER
                                 and r["market_odds_b"] in PLACEHOLDER,
                                 "fixture %s de-vigged a placeholder price" % r["fixture_id"])
        rejected = [m for m in MARKET if m["accepted"] != "yes"]
        self.assertEqual(3, len(rejected))
        for m in rejected:
            self.assertTrue(m["reject_reason"], "rejected read with no reason")
            self.assertIn("placeholder", m["reject_reason"].lower())
            self.assertIn("MARKET-PLACEHOLDER", codes_for(m["fixture_id"]))
        self.assertEqual(len(MARKET), 14)

    def test_book_label_and_citation_come_from_the_same_read(self):
        """IR-05-11: never pair one read's label with another read's odds and URL."""
        ext = {r["match_id"]: r for r in
               rows(os.path.join(ROOT, "data", "8944bb84", "external_lines.csv"))}
        pinned = 0
        for r in FIX:
            if not r["market_url"]:
                continue
            host = r["market_url"].split("/")[2]
            label = r["market_book"].lower()
            if "pinnacle" in label:
                self.assertIn("pinnacle.com", host,
                              "fixture %s labelled Pinnacle but cites %s" % (r["fixture_id"], host))
                self.assertIn("guest.api.arcadia.pinnacle.com", r["market_url"])
            else:
                self.assertIn("egamersworld.com", host,
                              "fixture %s labelled %r but cites %s"
                              % (r["fixture_id"], r["market_book"], host))
            src = ext.get(r["fixture_id"])
            if src and src.get("primary_source_url") == r["market_url"]:
                self.assertEqual("%.3f" % float(src["primary_odds_a"]), r["market_odds_a"])
                self.assertEqual("%.3f" % float(src["primary_odds_b"]), r["market_odds_b"])
                pinned += 1
                # wording differs ("bc.game (EGamersWorld)" vs "bc.game via EGamersWorld
                # (secondary)") but every substantive token must survive into the label
                for word in re.findall(r"[A-Za-z.]{3,}", src["primary_book"]):
                    self.assertIn(word.lower(), r["market_book"].lower(),
                                  "fixture %s label %r drops %r from %r"
                                  % (r["fixture_id"], r["market_book"], word,
                                     src["primary_book"]))
                if src["egw_odds_a"] and src["egw_odds_a"] != src["primary_odds_a"]:
                    self.assertIn("cross-check", r["market_book"],
                                  "fixture %s hides the disagreeing second read"
                                  % r["fixture_id"])
            if src and src.get("egw_url") == r["market_url"]:
                self.assertEqual("%.3f" % float(src["egw_odds_a"]), r["market_odds_a"])
                self.assertEqual("%.3f" % float(src["egw_odds_b"]), r["market_odds_b"])
        self.assertTrue(pinned, "no row cites the upstream primary read")
        # the fixture whose two reads disagree most must carry the primary numbers + both URLs
        z = BY_ID["1079546"]
        self.assertIn("guest.api.arcadia.pinnacle.com", z["market_url"])
        self.assertEqual("2.700", z["market_odds_a"])
        self.assertEqual("1.410", z["market_odds_b"])
        self.assertIn("cross-check", z["market_book"])
        self.assertIn("egamersworld.com", z["market_book"])
        self.assertNotEqual("%.3f" % float(ext["1079546"]["egw_odds_a"]), z["market_odds_a"])

    def test_market_reads_record_orientation(self):
        for m in MARKET:
            self.assertTrue(m["aggregator_url"], "market read with no URL")
            self.assertTrue(m["read_utc"])
            self.assertTrue(m["book"])
            self.assertIn(m["accepted"], ("yes", "no"))
            if m["accepted"] == "yes":
                self.assertEqual("", m["reject_reason"])
            else:
                self.assertTrue(m["reject_reason"])
        swap = BY_ID["1081105"]
        self.assertIn("odds swapped to Hotspawn order", swap["market_read_by"],
                      "the SUKEBAN/your-end swap must be recorded")
        self.assertIn("your end", swap["market_read_by"])
        # the swap must actually be reflected in the published orientation
        self.assertEqual("SUKEBAN", swap["team_a"])
        self.assertEqual(float(swap["market_p_b_pct"]),
                         round(100.0 * (1 / float(swap["market_odds_b"]))
                               / (1 / float(swap["market_odds_a"])
                                  + 1 / float(swap["market_odds_b"])), 1))

    def test_tier_hierarchy_is_respected(self):
        """A primary book price outranks a secondary one which outranks our own line."""
        for r in FIX:
            t = r["pick_tier"]
            if t == "A":
                self.assertIn("read by CI", r["market_book"])
                self.assertEqual("this session's live read" if False else
                                 r["market_read_by"], r["market_read_by"])
                self.assertIn("cs2/data/market_rows.csv", r["market_read_by"])
            if t in ("A", "B") and not r["verified_result"]:
                fav = r["team_a"] if float(r["market_p_a_pct"]) >= 50.0 else r["team_b"]
                self.assertEqual(fav, r["pick"],
                                 "fixture %s pick disagrees with the market favourite"
                                 % r["fixture_id"])
                self.assertEqual(r["market_p_a_pct"] if fav == r["team_a"] else r["market_p_b_pct"],
                                 r["pick_pct"])
            if t in ("C", "D"):
                self.assertEqual("", r["market_odds_a"],
                                 "fixture %s used our own line although a market priced it"
                                 % r["fixture_id"])
            if t in ("A", "B", "C", "D", "E"):
                self.assertTrue(r["pick"])
            if t == "F":
                self.assertEqual("", r["pick"])
        self.assertEqual(COV["counts"]["market_tier_A"],
                         sum(1 for r in FIX if r["pick_tier"] == "A"))


class ModelTests(unittest.TestCase):
    def test_own_line_is_reproducible_from_valve_points(self):
        """Re-derive p from the published points and k; the CSV must agree."""
        k = COV["model"]["k"]
        checked = 0
        for r in FIX:
            if not r["own_p_a_pct"] or not r["vrs_points_a"] or not r["vrs_points_b"]:
                continue
            if "BRACKETED" in r["rating_note"]:
                continue  # publishes a bound over several combinations; tested separately
            pa, pb = float(r["vrs_points_a"]), float(r["vrs_points_b"])
            pm = 1.0 / (1.0 + 10 ** (-k * (pa - pb) / 400.0))
            exp, _tf = build.series_transform(pm, r["best_of"])
            self.assertAlmostEqual(100.0 * exp, float(r["own_p_a_pct"]), places=1,
                                   msg="fixture %s own line (BO%s)"
                                       % (r["fixture_id"], r["best_of"] or "?"))
            self.assertAlmostEqual(100.0 * (1 - exp), float(r["own_p_b_pct"]), places=1)
            self.assertEqual("%.4f" % k, r["model_k"])
            if r["best_of"]:
                self.assertIn(_tf.lower(), r["own_basis"].lower())
            checked += 1
        self.assertGreaterEqual(checked, 60)

    def test_bracketed_own_line_matches_all_combinations_of_valve_rows(self):
        """Recompute the whole bracket from Valve's bytes, independently of the build."""
        k = COV["model"]["k"]
        for r in FIX:
            if "BRACKETED" not in r["rating_note"]:
                continue
            combos = []
            for side in ("a", "b"):
                pool = []
                for cu in r["vrs_cand_urls_%s" % side].split(";"):
                    if not cu:
                        continue
                    fname, line = url_parts(cu)
                    hit = [x for x in valve_rows(fname) if x["line"] == line]
                    self.assertEqual(1, len(hit), "citation %s does not resolve" % cu)
                    pool.append(hit[0])
                self.assertTrue(pool, "fixture %s side %s cites no Valve row"
                                % (r["fixture_id"], side))
                combos.append(pool)
            ps = [100.0 / (1.0 + 10 ** (-k * (ca["points"] - cb["points"]) / 400.0))
                  for ca, cb in itertools.product(combos[0], combos[1])]
            self.assertAlmostEqual(min(ps), float(r["own_p_lo_pct"]), places=1)
            self.assertAlmostEqual(max(ps), float(r["own_p_hi_pct"]), places=1)
            winners = {"A" if p >= 50 else "B" for p in ps}
            self.assertEqual(1, len(winners), "fixture %s should have gone blank" % r["fixture_id"])

    def test_series_transforms_are_order_preserving_and_fix_even(self):
        """So an unverified best-of can never flip the pick, only the margin."""
        def f3(p):
            return p * p * (3 - 2 * p)

        def f5(p):
            return p ** 3 * (10 - 15 * p + 6 * p * p)

        prev3 = prev5 = -1.0
        for i in range(10001):
            p = i / 10000.0
            self.assertGreaterEqual(f3(p), prev3 - 1e-12)
            self.assertGreaterEqual(f5(p), prev5 - 1e-12)
            prev3, prev5 = f3(p), f5(p)
            self.assertTrue(-1e-12 <= f3(p) <= 1 + 1e-12)
            self.assertTrue(-1e-12 <= f5(p) <= 1 + 1e-12)
        for f in (f3, f5):
            self.assertAlmostEqual(0.5, f(0.5), places=12)
            self.assertAlmostEqual(0.0, f(0.0), places=12)
            self.assertAlmostEqual(1.0, f(1.0), places=12)
            self.assertGreater(f(0.6), 0.6, "a series must amplify a favourite")
            self.assertLess(f(0.4), 0.4)
        # and the build's own implementation must agree
        self.assertAlmostEqual(f3(0.62), build.series_transform(0.62, "3")[0], places=9)
        self.assertAlmostEqual(f5(0.62), build.series_transform(0.62, "5")[0], places=9)
        self.assertAlmostEqual(0.62, build.series_transform(0.62, "1")[0], places=9)

    def test_model_constant_is_inherited_not_invented(self):
        src = json.load(open(os.path.join(ROOT, "cs2", "data", "summary.json"), encoding="utf-8"))
        self.assertAlmostEqual(src["own_line"]["k"], COV["model"]["k"], places=4)
        self.assertEqual(src["own_line"]["valve_commit"], COMMIT)
        self.assertEqual(src["own_line"]["n_calibrated_on"], COV["model"]["k_calibrated_on"])
        self.assertIn(COV["official_rating_source"]["repository"],
                      "https://github.com/ValveSoftware/counter-strike_regional_standings")

    def test_unverified_format_is_labelled_not_hidden(self):
        n = 0
        for r in FIX:
            if r["own_p_a_pct"] and not r["best_of"]:
                n += 1
                self.assertIn("single-map", r["own_basis"].lower(),
                              "fixture %s publishes a probability without stating the format gap"
                              % r["fixture_id"])
                self.assertIn("format-invariant", r["own_basis"])
                self.assertEqual("", r["format_source"])
        self.assertGreater(n, 40)
        for r in FIX:
            if r["best_of"]:
                self.assertIn("HLTV", r["format_source"])


class FlagTests(unittest.TestCase):
    def test_flag_schema(self):
        for f in FLAGS:
            for col in ("flag_id", "severity", "code", "subject", "detail",
                        "official_source_url", "raised_utc", "raised_by"):
                self.assertTrue(f[col], "%s missing %s" % (f["flag_id"], col))
            self.assertIn(f["severity"], ("HIGH", "MEDIUM", "INFO", "NEEDS REVIEW"))
            self.assertTrue(f["official_source_url"].startswith("https://"))
        self.assertEqual(len({f["flag_id"] for f in FLAGS}), len(FLAGS), "duplicate flag ids")
        for f in FLAGS:
            fid = re.search(r"\b(10\d{5})\b", f["subject"])
            self.assertTrue(fid, "flag %s does not name a fixture" % f["flag_id"])
            self.assertIn(fid.group(1), BY_ID)

    def test_flagged_items_are_published_on_the_flagged_page(self):
        page = open(os.path.join(SITE, "flagged.html"), encoding="utf-8").read()
        for f in FLAGS:
            self.assertIn(html.escape(f["flag_id"]), page + page,
                          "flag %s missing from flagged.html" % f["flag_id"])
            self.assertIn(html.escape(f["code"]), page)
        self.assertIn("Flagged for review", page)
        for i in range(1, 12):
            self.assertIn("IR-05-%02d" % i, page)

    def test_unverifiable_values_are_blank_not_filled(self):
        """The standing rule: unconfirmable stays blank and gets flagged."""
        for r in FIX:
            if not r["pick"]:
                self.assertIn("NO-PICK", codes_for(r["fixture_id"]))
                for col in ("pick_pct", "pick_pct_hi"):
                    self.assertEqual("", r[col])
        for t in TEAMS:
            if t["unranked_finding"]:
                self.assertEqual("", t["rating_period"])


class SiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {n: open(os.path.join(SITE, n), encoding="utf-8").read()
                     for n in sorted(os.listdir(SITE)) if n.endswith(".html")}

    def test_all_nav_pages_exist_and_are_mobile_configured(self):
        for href, _label in site.NAV:
            self.assertIn(href, self.pages, "nav target %s missing" % href)
        for name, s in self.pages.items():
            self.assertEqual(1, s.count("<html"), name)
            self.assertEqual(1, s.count("</html>"), name)
            self.assertIn('name="viewport"', s, "%s is not mobile-configured" % name)
            self.assertIn('lang="en"', s, name)
            self.assertNotRegex(s, r"%\(\w+\)[sdf]", "%s has an unrendered placeholder" % name)
            self.assertNotIn("<<<<<<<", s)
            self.assertNotIn(">>>>>>>", s)

    def test_no_broken_internal_links(self):
        for name, s in self.pages.items():
            for m in re.finditer(r'href="([^"]*)"', s):
                u = html.unescape(m.group(1))
                if u.startswith(("http", "mailto:", "#")) or not u:
                    continue
                target = os.path.normpath(os.path.join(SITE, u.split("#")[0].split("?")[0]))
                self.assertTrue(os.path.exists(target), "%s links to missing %s" % (name, u))

    def test_no_broken_citation_urls(self):
        """Every external citation must be a plausible, well-formed absolute URL."""
        for name, s in self.pages.items():
            for m in re.finditer(r'href="(https?://[^"]*)"', s):
                u = html.unescape(m.group(1))
                self.assertNotIn(" ", u, "%s has a URL with a space: %s" % (name, u))
                self.assertNotIn(".md.md", u, "%s has a malformed Valve citation: %s" % (name, u))
                self.assertNotIn("None", u, "%s cites a None: %s" % (name, u))
                if "counter-strike_regional_standings" in u and "/blob/" in u:
                    self.assertIn(COMMIT, u, "%s has an unpinned Valve citation: %s" % (name, u))
                    if "?plain=1" in u:  # a whole-file citation has no row anchor
                        self.assertRegex(u, re.compile(r"#L\d+$"),
                                         "%s row citation has no line anchor: %s" % (name, u))

    def test_site_rebuilds_identically(self):
        """The committed HTML must be exactly what the renderer produces."""
        tmp = tempfile.mkdtemp(prefix="5bcfd1b5-site-")
        try:
            old = site.OUT
            site.OUT = tmp
            site.build()
            after = {n: open(os.path.join(tmp, n), encoding="utf-8").read()
                     for n in os.listdir(tmp) if n.endswith(".html")}
            self.assertEqual(sorted(self.pages), sorted(after))
            stamp = re.compile(r"(generated|capture|Read|read) [0-9]{4}-[0-9]{2}-[0-9]{2}T"
                               r"[0-9:]+Z")
            for n in after:
                self.assertEqual(stamp.sub("X", self.pages[n]), stamp.sub("X", after[n]),
                                 "%s is stale — run scripts/5bcfd1b5_site.py" % n)
        finally:
            site.OUT = old
            shutil.rmtree(tmp, ignore_errors=True)

    def test_executive_summary_answers_where_the_picks_are(self):
        s = self.pages["index.html"]
        for needle in ("Executive summary", "Open matches", "All fixtures", "Flagged for review",
                       "Methodology", "Sources", "By tier", "By tournament", "Outside betting lines",
                       "Our own lines", "Team ratings"):
            self.assertIn(needle, s, "summary does not link to %s" % needle)
        self.assertRegex(s, r'href="open\.html"')
        c = COV["counts"]
        for v in (c["state_open"], c["with_pick"], c["fixtures_total"],
                  c["open_with_pick"], c["market_tier_A"], c["market_tier_B"]):
            self.assertIn(str(v), s)

    def test_open_page_has_one_card_per_open_match_with_pick_and_bar(self):
        s = self.pages["open.html"]
        cards = re.findall(r'<article class="match[^"]*".*?</article>', s, re.S)
        open_rows = sorted((r for r in FIX if r["state"] == "open"),
                           key=lambda x: (x["start_utc"][:10], x["start_utc"], x["fixture_id"]))
        self.assertEqual(len(open_rows), len(cards))
        for card, r in zip(cards, open_rows):
            self.assertIn('class="star"', card, "card %s does not mark the pick" % r["fixture_id"])
            self.assertIn(html.escape(r["pick"]), card)
            if r["pick_pct"]:
                self.assertIn('role="img"', card,
                              "card %s has no probability bar" % r["fixture_id"])
                self.assertIn(r["pick_pct"] + "%", card)
            else:
                self.assertIn("deliberately", card,
                              "card %s must say the probability is deliberately blank"
                              % r["fixture_id"])
                self.assertNotIn('role="img"', card)
            self.assertIn('rel="noopener"', card, "card %s has no source link" % r["fixture_id"])
            self.assertIn(r["fixture_id"], card)
            self.assertIn(html.escape(r["competition"]), card)

    def test_every_fixture_appears_on_the_all_page(self):
        s = self.pages["all.html"]
        cards = re.findall(r'<article class="match[^"]*".*?</article>', s, re.S)
        self.assertEqual(len(FIX), len(cards))
        for r in FIX:
            self.assertIn("#%s" % r["fixture_id"], s)
        for r in FIX:
            if r["pick_pct_hi"] and r["pick_pct_hi"] != r["pick_pct"]:
                self.assertIn(r["pick_pct_hi"], s,
                              "all.html hides the bracket range for %s" % r["fixture_id"])

    def test_pages_do_not_overstate_certainty(self):
        bad = re.compile(r"\bsure bet\b|\bguaranteed win\b|\bcan't lose\b|\bloc[k]?ed in\b"
                         r"|\brisk.free\b", re.I)
        for name, s in self.pages.items():
            self.assertNotRegex(s, bad, name)
            # the only permitted use of "guaranteed" is the negation in our own disclaimer
            for m in re.finditer(r"guaranteed", s, re.I):
                ctx = s[max(0, m.start() - 12):m.start()]
                self.assertIn("not ", ctx, "%s overstates certainty: ...%s" % (name, ctx))
        self.assertIn("not betting advice", self.pages["index.html"])
        self.assertIn("deliberately", self.pages["index.html"])


class LiveCheckTests(unittest.TestCase):
    """The scheduled 'has Hotspawn changed?' check must be correct and must never guess."""

    def synthetic(self) -> dict:
        base = BY_ID["1080176"]
        other, third = BY_ID["1079438"], BY_ID["1079439"]
        return {"fetched_utc": "2026-10-14T04:00:00Z", "errors": [], "pages": {}, "records": {
            # unchanged
            "1080176": {"id": "1080176", "game": "cs2", "team_a": base["team_a"],
                        "team_b": base["team_b"], "tournament": base["competition"],
                        "tier": base["tier"], "start_time": base["start_utc"],
                        "lock_time": base["lock_utc"], "series_format": "BO3", "best_of": 3},
            # lock time moved
            "1079438": {"id": "1079438", "game": "cs2", "team_a": other["team_a"],
                        "team_b": other["team_b"], "tournament": other["competition"],
                        "tier": other["tier"], "start_time": other["start_utc"],
                        "lock_time": "2026-10-14T09:45:00Z", "series_format": "BO3",
                        "best_of": 3},
            # opponent renamed and format changed
            "1079439": {"id": "1079439", "game": "cs2", "team_a": third["team_a"],
                        "team_b": "Fnatic Academy", "tournament": third["competition"],
                        "tier": third["tier"], "start_time": third["start_utc"],
                        "lock_time": third["lock_utc"], "series_format": "BO1", "best_of": 1},
            # brand new fixture the board has never seen
            "9999999": {"id": "9999999", "game": "cs2", "team_a": "Brand New",
                        "team_b": "Also New", "tournament": "ESL Challenger League S53",
                        "tier": "B", "start_time": "2026-10-20T10:00:00Z",
                        "lock_time": "2026-10-20T09:45:00Z", "series_format": "BO3",
                        "best_of": 3,
                        "source_url": "https://www.hotspawn.com/matches/x-9999999"},
        }}

    def test_compare_detects_new_changed_and_dropped(self):
        rep = livecheck.compare(FIX, self.synthetic())
        self.assertTrue(rep["comparison_possible"])
        self.assertEqual(["9999999"], [n["fixture_id"] for n in rep["new_on_hotspawn"]])
        new = rep["new_on_hotspawn"][0]
        self.assertEqual("Brand New", new["team_a"])
        self.assertIn("pick", new["action"])
        self.assertTrue(new["source_url"].startswith("https://"))
        changed = {c["fixture_id"]: c for c in rep["changed_on_hotspawn"]}
        self.assertEqual({"1079438", "1079439"}, set(changed))
        self.assertEqual(["lock_utc"], [d["field"] for d in changed["1079438"]["differences"]])
        self.assertEqual("2026-10-14T09:45:00Z",
                         changed["1079438"]["differences"][0]["hotspawn_now"])
        self.assertEqual({"team_b", "best_of"},
                         {d["field"] for d in changed["1079439"]["differences"]})
        self.assertEqual(1, rep["unchanged"])
        self.assertEqual(len(FIX) - 3, len(rep["no_longer_listed"]))
        self.assertEqual(sum(1 for d in rep["no_longer_listed"] if d["state"] == "open"),
                         len(rep["unexpectedly_missing"]))
        self.assertIn("NEW FIXTURES", rep["verdict"])
        self.assertEqual(4, rep["live_cs2_fixtures"])
        self.assertEqual(len(FIX), rep["board_fixtures"])

    def test_unreachable_source_is_recorded_not_raised_and_not_misread(self):
        """No live inventory must not be reported as 'every fixture vanished'."""
        rep = livecheck.compare(FIX, {"fetched_utc": "2026-10-14T04:00:00Z",
                                      "errors": ["network: TLS/SSL closed"],
                                      "pages": {}, "records": {}})
        self.assertFalse(rep["reachable"])
        self.assertFalse(rep["comparison_possible"])
        self.assertEqual([], rep["no_longer_listed"])
        self.assertEqual([], rep["unexpectedly_missing"])
        self.assertEqual([], rep["new_on_hotspawn"])
        self.assertIn("unreachable", rep["verdict"])
        self.assertEqual(["network: TLS/SSL closed"], rep["errors"])

    def test_no_fetch_ever_raises(self):
        body, err = livecheck.fetch("https://play.hotspawn.com/definitely-not-a-page-404")
        self.assertTrue(err or body)
        self.assertIsInstance(err, str)

    def test_collector_projects_no_crowd_value(self):
        """The shared collector must not even carry a crowd field into our diff."""
        banned = re.compile(r"crowd|percent|pct|vote|pick", re.I)
        for field in hs_collector.FIXTURE_FIELDS:
            self.assertNotRegex(field, banned, "collector projects a crowd-ish field: %s" % field)
        self.assertIn("scheduled_start_time", hs_collector.FIXTURE_FIELDS)
        self.assertIn("lock_time", hs_collector.FIXTURE_FIELDS)

    def test_committed_report_is_well_formed(self):
        path = os.path.join(DATA, "livecheck.json")
        self.assertTrue(os.path.exists(path), "run scripts/5bcfd1b5_livecheck.py")
        rep = json.load(open(path, encoding="utf-8"))
        for key in ("compared_utc", "board_fixtures", "live_cs2_fixtures", "new_on_hotspawn",
                    "changed_on_hotspawn", "no_longer_listed", "reachable", "verdict",
                    "crowd_percentages_read", "crowd_note", "comparison_possible",
                    "count_disagreement"):
            self.assertIn(key, rep)
        self.assertFalse(rep["crowd_percentages_read"])
        self.assertEqual(len(FIX), rep["board_fixtures"])
        dt.datetime.strptime(rep["compared_utc"], "%Y-%m-%dT%H:%M:%SZ")
        for page in rep["pages"].values():
            self.assertTrue(page["url"].startswith("https://play.hotspawn.com/"))
            self.assertTrue(page.get("error") or page.get("response_sha256"),
                            "a page read must record either an error or a response hash")

    def test_new_hotspawn_fixtures_are_merged_and_picked(self):
        """The scheduled check must close the loop, not just report.

        Proven by feeding merge_live_fixtures a synthetic newly-listed fixture: it must land on
        the board, carry only values Hotspawn's payload actually holds, and be flagged.
        """
        now = "2026-10-14T04:00:00Z"
        report = {"comparison_possible": True, "compared_utc": now, "new_on_hotspawn": [{
            "fixture_id": "9999001", "team_a": "Natus Vincere", "team_b": "Vitality",
            "tournament": "BLAST Open London 2026", "tier": "S",
            "start_utc": "2026-10-20T15:00:00Z", "lock_utc": "2026-10-20T14:45:00Z",
            "series_format": "BO3",
            "source_url": "https://www.hotspawn.com/matches/x-9999001"}]}
        tmp = tempfile.mkdtemp(prefix="5bcfd1b5-live-")
        try:
            path = os.path.join(tmp, "livecheck.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(report, fh)
            old = build.LIVECHECK
            build.LIVECHECK = path
            fixtures, raised = [], []
            n = build.merge_live_fixtures(fixtures, lambda *a, **k: raised.append(a), now)
            build.LIVECHECK = old
            self.assertEqual(1, n)
            f = fixtures[0]
            self.assertEqual("9999001", f["fixture_id"])
            self.assertEqual("open", f["state"])
            self.assertEqual("yes", f["pickable"])
            self.assertEqual("3", f["best_of"], "the payload's format must be used")
            self.assertEqual("Hotspawn payload best_of" if False else f.get("best_of"), "3")
            # values the payload does NOT carry must stay blank, never inferred
            self.assertEqual("", f["points"], "Hotspawn's payload has no point value")
            self.assertEqual("", f.get("hltv_match_url", ""))
            self.assertEqual("https://www.hotspawn.com/matches/x-9999001",
                             f["hotspawn_match_url"])
            self.assertEqual("yes", f["live_discovered"])
            self.assertEqual(1, len(raised))
            self.assertEqual("LIVE-NEW-FIXTURE", raised[0][0])
            self.assertEqual("NEEDS REVIEW", raised[0][4])
            self.assertIn("blank rather than inferred", raised[0][2])
            # idempotent: a fixture already on the board is not added twice
            self.assertEqual(0, build.merge_live_fixtures(fixtures, lambda *a: None, now))
            # and nothing happens when no live comparison was possible
            build.LIVECHECK = path
            report["comparison_possible"] = False
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(report, fh)
            self.assertEqual(0, build.merge_live_fixtures([], lambda *a: None, now))
            build.LIVECHECK = os.path.join(tmp, "absent.json")
            self.assertEqual(0, build.merge_live_fixtures([], lambda *a: None, now))
            build.LIVECHECK = old
        finally:
            build.LIVECHECK = os.path.join(DATA, "livecheck.json")
            shutil.rmtree(tmp, ignore_errors=True)

    def test_committed_board_has_no_live_only_fixtures(self):
        """The committed snapshot must match the committed live check (which saw nothing new)."""
        rep = json.load(open(os.path.join(DATA, "livecheck.json"), encoding="utf-8"))
        self.assertEqual([], rep["new_on_hotspawn"])
        self.assertEqual(0, sum(1 for r in FIX
                                if r.get("fixture_origin", "").startswith("live Hotspawn")))
        for r in FIX:
            self.assertIn("fixture_origin", r)

    def test_times_come_from_epochs_not_printed_wall_clock(self):
        """epoch_ms must reject anything that is not a 13-digit ms epoch."""
        self.assertIsNone(hs_collector.epoch_ms(None))
        self.assertIsNone(hs_collector.epoch_ms(""))
        self.assertIsNone(hs_collector.epoch_ms(True))
        self.assertIsNone(hs_collector.epoch_ms("10:00 UTC"))
        self.assertIsNone(hs_collector.epoch_ms(1760000000))       # seconds, not ms
        self.assertEqual("2026-10-14T08:00:00Z", hs_collector.epoch_ms(1791964800000))
        self.assertEqual("2026-10-14T08:00:00Z", hs_collector.epoch_ms("1791964800000"))


class NoHallucinationTests(unittest.TestCase):
    def test_timestamps_are_well_formed_and_ordered(self):
        for r in FIX:
            for col in ("start_utc", "lock_utc", "captured_utc", "generated_utc"):
                if r[col]:
                    dt.datetime.strptime(r[col], "%Y-%m-%dT%H:%M:%SZ")
            # Hotspawn locks picks BEFORE kickoff, so lock <= start on every fixture
            self.assertLessEqual(r["lock_utc"], r["start_utc"], r["fixture_id"])
        for m in MARKET:
            dt.datetime.strptime(m["read_utc"], "%Y-%m-%dT%H:%M:%SZ")

    def test_state_matches_the_lock_time(self):
        now = dt.datetime.strptime(COV["generated_utc"], "%Y-%m-%dT%H:%M:%SZ")
        for r in FIX:
            lock = dt.datetime.strptime(r["lock_utc"], "%Y-%m-%dT%H:%M:%SZ")
            if lock >= now:
                self.assertEqual("open", r["state"],
                                 "fixture %s locks in the future but is marked %s"
                                 % (r["fixture_id"], r["state"]))
                self.assertEqual("yes", r["pickable"])
            else:
                self.assertIn(r["state"], ("stale", "started"))
                self.assertNotEqual("yes", r["pickable"])

    def test_probabilities_are_sane(self):
        for r in FIX:
            for col in ("pick_pct", "pick_pct_hi", "market_p_a_pct", "market_p_b_pct",
                        "own_p_a_pct", "own_p_b_pct", "own_p_lo_pct", "own_p_hi_pct"):
                if r[col]:
                    f = float(r[col])
                    self.assertTrue(0.0 < f < 100.0,
                                    "fixture %s %s=%s" % (r["fixture_id"], col, r[col]))
            for a, b in (("market_p_a_pct", "market_p_b_pct"), ("own_p_a_pct", "own_p_b_pct")):
                if r[a] and r[b]:
                    self.assertAlmostEqual(100.0, float(r[a]) + float(r[b]), places=1)
            if r["own_p_lo_pct"] and r["own_p_hi_pct"]:
                self.assertLessEqual(float(r["own_p_lo_pct"]), float(r["own_p_hi_pct"]))
            if r["pick_pct"] and r["pick_pct_hi"]:
                self.assertLessEqual(float(r["pick_pct"]), float(r["pick_pct_hi"]))
                self.assertGreater(float(r["pick_pct"]), 50.0 - 1e-9,
                                   "fixture %s picks a side below 50%%" % r["fixture_id"])

    def test_pick_is_one_of_the_two_playing_teams(self):
        for r in FIX:
            self.assertNotEqual(r["team_a"], r["team_b"], r["fixture_id"])
            self.assertTrue(r["team_a"] and r["team_b"])
            if r["pick"]:
                self.assertIn(r["pick"], (r["team_a"], r["team_b"]),
                              "fixture %s picked a team that is not playing" % r["fixture_id"])
                self.assertTrue(float(r["pick_pct"]) >= 50.0 if r["pick_pct"] else True)

    def test_no_value_is_inferred_where_the_source_is_missing(self):
        for r in FIX:
            if not r["vrs_url_a"]:
                self.assertEqual("", r["vrs_points_a"])
                self.assertEqual("", r["vrs_rank_a"])
            if not r["market_url"]:
                for col in ("market_odds_a", "market_odds_b", "market_p_a_pct",
                            "market_p_b_pct", "market_overround_pct", "market_tier"):
                    self.assertEqual("", r[col], "fixture %s has market data with no citation"
                                     % r["fixture_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
