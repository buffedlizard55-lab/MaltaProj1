#!/usr/bin/env python3
"""tests/test_1b6ae823.py — invariants for the research tier, the originated lines and the cadence.

Session ``arena/1b6ae823`` added three things to the executive board:

1. an **originated line for every fixture** (official HLTV world ranking → logistic → stated series length);
2. a **fifth basis tier** ("Research · official ranking line") used only where no outside price and no VRS
   point pair exists, so a low-tier fixture that no betting site prices still gets a pick, labelled as ours;
3. a **cadence page** that publishes which workflow refreshes the board, when it last ran and how old every
   input is — plus consumption of this repository's own hourly secondary feed (read-only, its own minute).

Each test re-derives the published number from the stored inputs under ``executive/data/``. A page that
prints something its own inputs do not produce fails here, and the refresh workflow commits nothing until
these pass (fail-closed publication).

Run: ``python -m unittest tests.test_1b6ae823 -v``
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
EXEC = ROOT / "executive"
DATA = EXEC / "data"
FEED_CSV = ROOT / "feeds" / "data" / "market_feed.csv"
sys.path.insert(0, str(EXEC))

import ownlines  # noqa: E402

CROWD_TOKENS = ("picked_percent", "total_picks", "crowd_pct", "crowd_percent")


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def stamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def https_url(value: object) -> bool:
    try:
        parts = urlsplit(str(value or ""))
    except ValueError:
        return False
    return parts.scheme == "https" and bool(parts.netloc) and not parts.username and not parts.password


class OwnLineMathTests(unittest.TestCase):
    """The maths itself, checked against independent enumerations rather than against the builder."""

    def test_series_closed_forms_match_enumeration(self):
        for bo in (1, 3, 5, 7):
            first_to = ownlines.maps_to_win(bo)
            for step in range(1, 100):
                p = step / 100.0
                enumerated = 0.0
                for k in range(first_to):                     # maps lost before the deciding win
                    n = first_to - 1 + k
                    enumerated += math.comb(n, first_to - 1) * (p ** first_to) * ((1 - p) ** k)
                self.assertAlmostEqual(ownlines.series_probability(p, bo), enumerated, places=12,
                                       msg=f"BO{bo} at p={p}")

    def test_series_formula_known_values(self):
        self.assertAlmostEqual(ownlines.series_probability(0.5, 3), 0.5, places=12)
        self.assertAlmostEqual(ownlines.series_probability(0.6, 3), 3 * 0.36 - 2 * 0.216, places=12)
        self.assertAlmostEqual(ownlines.series_probability(0.6, 5),
                               10 * 0.6 ** 3 - 15 * 0.6 ** 4 + 6 * 0.6 ** 5, places=12)
        # A longer series must favour the stronger side and penalise the weaker one, never the reverse.
        self.assertGreater(ownlines.series_probability(0.65, 5), ownlines.series_probability(0.65, 3))
        self.assertLess(ownlines.series_probability(0.35, 5), ownlines.series_probability(0.35, 3))

    def test_logistic_is_symmetric_and_official_scale_matches_valve(self):
        self.assertAlmostEqual(ownlines.logit_ratio(100, 50, 200) + ownlines.logit_ratio(50, 100, 200), 1.0, places=12)
        # Valve's own published relation: 400 points ≈ 90% (model/glicko.js in the standings repository).
        self.assertAlmostEqual(ownlines.logit_ratio(1800, 1400, ownlines.RATIO_POINTS), 10 / 11, places=12)

    def test_format_parsing_never_invents_a_length(self):
        self.assertEqual(ownlines.format_to_best_of("BO5"), 5)
        self.assertEqual(ownlines.format_to_best_of("bo1"), 1)
        self.assertEqual(ownlines.format_to_best_of(3.0), 3)
        self.assertEqual(ownlines.format_to_best_of("3.0"), 3)
        self.assertIsNone(ownlines.format_to_best_of(""))
        self.assertIsNone(ownlines.format_to_best_of(None))
        self.assertIsNone(ownlines.format_to_best_of(2), "an even-length series is not a CS2 format")

    def test_calibration_is_deterministic_and_refuses_small_samples(self):
        samples = [(10.0, 0.6), (20.0, 0.7), (-5.0, 0.45), (30.0, 0.75), (15.0, 0.65)]
        first = ownlines.calibrate_scale(samples)
        second = ownlines.calibrate_scale(list(reversed(samples)))
        self.assertTrue(first["fitted"])
        self.assertEqual(first["scale"], second["scale"], "the fit must not depend on the input order")
        thin = ownlines.calibrate_scale(samples[:3])
        self.assertFalse(thin["fitted"])
        self.assertEqual(thin["scale"], ownlines.DEFAULT_RANK_SCALE)


class PublishedOwnLinesTests(unittest.TestCase):
    """Every published own line must come out of the stored official ranking, at the published scale."""

    @classmethod
    def setUpClass(cls):
        if not (DATA / "analysis.csv").exists():
            raise unittest.SkipTest("executive/data/analysis.csv is missing — run executive/build.py")
        cls.rows = read_rows(DATA / "analysis.csv")
        cls.summary = read_json(DATA / "summary.json", {}) or {}
        ranking = read_json(DATA / "hltv_ranking.json", {}) or {}
        cls.teams = ranking.get("teams") or []
        cls.ranks: dict[str, int] = {}
        for team in cls.teams:
            if str(team.get("rank", "")).isdigit():
                cls.ranks.setdefault(str(team.get("name", "")).casefold(), int(team["rank"]))
        cls.rank_floor = max(cls.ranks.values()) if cls.ranks else 0
        cls.ratings = {r.get("team"): r for r in read_rows(DATA / "ratings.csv")}
        cls.open_rows = [r for r in cls.rows if r.get("status") == "open"]

    def _published_rank(self, row: dict, side: str) -> int:
        """The rank number printed for one side, or the official bound when the team is absent."""
        raw = (row.get(f"own_rank_{side}") or "").strip()
        return int(raw) if raw.isdigit() else self.rank_floor + 1

    def test_own_lines_recompute_from_the_stored_ranking(self):
        cal = (self.summary.get("own_lines") or {}).get("calibration") or {}
        scale = float(cal.get("scale") or 0)
        self.assertGreater(scale, 0, "the published calibration scale is missing")
        checked = 0
        for row in self.rows:
            published = row.get("own_prob_a_pct")
            if not published:
                continue
            flags = row.get("flags", "")
            for side in ("a", "b"):
                if not (row.get(f"own_rank_{side}") or "").strip().isdigit():
                    self.assertIn("FL-RANK-FLOOR-BOUND", flags,
                                  f"{row['match_id']}: side {side} is bounded without the bound flag")
                    continue
                names = {str(row[f"team_{side}"]).casefold(),
                         str((self.ratings.get(row[f"team_{side}"]) or {}).get("hltv_name", "")).casefold()}
                official = {self.ranks[name] for name in names if name in self.ranks}
                self.assertIn(int(row[f"own_rank_{side}"]), official,
                              f"{row['match_id']}: rank {row[f'own_rank_{side}']} for {row[f'team_{side}']} "
                              f"is not that team's number in the official ranking {sorted(official)}")
            strength_a = self.rank_floor - self._published_rank(row, "a")
            strength_b = self.rank_floor - self._published_rank(row, "b")
            per_map = ownlines.logit_ratio(strength_a, strength_b, scale)
            best_of = ownlines.format_to_best_of(row.get("own_best_of")) or 1
            self.assertAlmostEqual(per_map * 100.0, float(row.get("own_prob_map_a_pct") or 0), delta=0.6,
                                   msg=f"{row['match_id']}: the per-map line does not match the ranking")
            series = ownlines.series_probability(per_map, best_of) * 100.0
            self.assertAlmostEqual(series, float(published), delta=0.15,
                                   msg=f"{row['match_id']}: published own line {published} vs recomputed "
                                       f"{series:.1f} (ranks {row.get('own_rank_a')}/{row.get('own_rank_b')}, "
                                       f"BO{best_of})")
            checked += 1
        self.assertGreater(checked, 0, "no own lines were published at all")

    def test_calibration_reproduces_the_published_scale(self):
        cal = (self.summary.get("own_lines") or {}).get("calibration") or {}
        pairs = []
        for row in self.rows:
            if row.get("basis_tier") not in ("1", "2") or not row.get("market_prob_a_pct"):
                continue
            ra = (row.get("own_rank_a") or "").strip()
            rb = (row.get("own_rank_b") or "").strip()
            if not (ra.isdigit() and rb.isdigit()):
                continue                       # bounded rows are excluded from the fit, by design
            if not ownlines.format_to_best_of(row.get("series_format")):
                continue
            pairs.append(((self.rank_floor - int(ra)) - (self.rank_floor - int(rb)),
                          float(row["market_prob_a_pct"]) / 100.0,
                          ownlines.format_to_best_of(row.get("series_format")) or 1))
        self.assertEqual(cal.get("n", 0), len(pairs), "the published sample size is not the pairs available")
        if not pairs:
            self.assertFalse(cal.get("fitted"), "no pairs but the page claims a fitted scale")
            self.assertEqual(float(cal.get("scale")), ownlines.DEFAULT_RANK_SCALE)
            return
        self.assertTrue(cal.get("fitted"), "enough priced fixtures to fit, yet no fit is published")
        recomputed = ownlines.calibrate_scale(pairs)
        published = float(cal["scale"])

        def mae_at(scale: float) -> float:
            """The builder's own objective, recomputed from the published rows."""
            return 100.0 * sum(abs(ownlines.series_probability(ownlines.logit_ratio(dr, 0.0, scale), bo) - p)
                               for dr, p, bo in pairs) / len(pairs)

        # The fit runs on the unrounded probabilities the collector held; this test can only rebuild
        # them from the published row, which is rounded to a tenth of a percent.  On a near-tie two
        # neighbouring grid points then swap places, so the contract is not "the same integer" but
        # "the published scale is a minimiser within that rounding noise, and not further than one
        # grid step from the recomputed one".  The printed error must be the error of the fit printed.
        best = mae_at(float(recomputed["scale"]))
        self.assertLessEqual(mae_at(published), best + 0.05,
                             f"published scale {published:g} scores {mae_at(published):.3f} pp while the "
                             f"grid optimum {float(recomputed['scale']):g} scores {best:.3f} pp")
        self.assertLessEqual(abs(published - float(recomputed["scale"])), 1.0,
                             "the published scale drifts more than one grid step from the recomputed argmin")
        self.assertAlmostEqual(float(cal["mae_pp"]), mae_at(published), delta=0.15,
                               msg="the MAE printed next to the scale is not that scale's error")

    def test_every_open_fixture_carries_an_own_line_or_a_reason(self):
        missing = [r["match_id"] for r in self.open_rows
                   if not r.get("own_prob_a_pct") and not r.get("flags")]
        self.assertEqual(missing, [], "open fixtures with neither an own line nor a flag")
        coverage = self.summary.get("coverage") or {}
        self.assertEqual(coverage.get("open_own_line"),
                         len([r for r in self.open_rows if r.get("own_prob_a_pct")]),
                         "the published own-line coverage does not match the rows")

    def test_research_tier_is_only_used_where_no_price_exists(self):
        for row in self.rows:
            if row.get("basis_tier") != "5":
                continue
            self.assertFalse(row.get("market_source"),
                             f"{row['match_id']}: a research line printed over a readable price")
            self.assertIn("FL-RESEARCH-BASIS", row.get("flags", ""))
            self.assertTrue(row.get("own_sources"), "a T5 row must link the official ranking it used")
            self.assertTrue(row.get("pick"), "a T5 row must still give a pick")

    def test_a_price_never_comes_from_hotspawn(self):
        for row in self.rows:
            for url in (row.get("source_links") or "").split(" | "):
                if not url:
                    continue
                self.assertTrue(https_url(url), f"{row['match_id']}: non-https source {url!r}")
                host = urlsplit(url).netloc
                if "hotspawn" in host:
                    self.assertTrue(row["hotspawn_match_url"] == url or row["hotspawn_pickem_url"] == url,
                                    f"{row['match_id']}: {url} is not a fixture-identity link")
            basis = (row.get("basis_detail") or "").lower()
            self.assertNotIn("picked", basis, f"{row['match_id']}: the basis text mentions crowd picks")
            if row.get("basis_tier") in ("1", "2"):
                self.assertTrue(row.get("market_captured_utc"),
                                f"{row['match_id']}: a priced row without its read time")
                self.assertTrue(row.get("prob_a_pct") and row.get("prob_b_pct"),
                                f"{row['match_id']}: priced row without probabilities")

    def test_stated_series_format_always_names_where_it_was_stated(self):
        for row in self.rows:
            if not row.get("series_format"):
                continue
            self.assertTrue(row.get("series_format_source") or row.get("market_source"),
                            f"{row['match_id']}: a series length with no source for it")
            if row.get("series_format_source"):
                self.assertTrue(https_url(row["series_format_source"]),
                                f"{row['match_id']}: format source is not an https URL")


class FeedConsumptionTests(unittest.TestCase):
    """The board may read this repository's hourly secondary feed — with its own timestamp, or not at all."""

    def test_feed_quotes_keep_their_own_minute_and_page(self):
        payload = read_json(DATA / "secondary_lines.json", {}) or {}
        feed = payload.get("feed") or {}
        if feed.get("status") != "ok":
            self.skipTest(f"feed not used this run (status {feed.get('status')!r})")
        quotes = [q for q in (payload.get("quotes") or []) if q.get("feed")]
        self.assertGreaterEqual(len(quotes), int(feed.get("used") or 0) - 1,
                                "the feed reported quotes that never reached the board")
        for quote in quotes:
            self.assertTrue(https_url(quote.get("source_url")),
                            f"feed quote without an https listing page: {quote.get('source_url')!r}")
            when = stamp(quote.get("captured_utc"))
            self.assertIsNotNone(when, "feed quote without its own capture minute")
            self.assertLessEqual(when, datetime.now(timezone.utc), "a capture from the future is impossible")
            self.assertNotIn("hotspawn", str(quote.get("source_url", "")))

    def test_feed_is_only_read_never_written(self):
        self.assertFalse((DATA / "market_feed.csv").exists(),
                         "executive/data must not shadow the feed owner's file")
        self.assertFalse((DATA / "capture.json").exists(),
                         "executive/data must not shadow the feed owner's capture record")

    def test_stale_feed_is_refused_not_recycled(self):
        sys.path.insert(0, str(EXEC))
        import feedline
        if not FEED_CSV.exists():
            self.skipTest("no feed file in this checkout")
        rows = read_rows(FEED_CSV)
        future = datetime(2027, 1, 1, tzinfo=timezone.utc)
        stale = feedline.read_quotes(now=future)
        self.assertEqual(stale["status"], "stale",
                         "a feed read 12+ h after its capture must be refused outright")
        self.assertEqual(stale["quotes"], [], "a refused feed must yield no quote at all")


class CadenceTests(unittest.TestCase):
    def test_cadence_page_exists_and_states_the_window(self):
        page = EXEC / "cadence.html"
        self.assertTrue(page.exists(), "executive/cadence.html was not built")
        text = page.read_text(encoding="utf-8")
        self.assertIn('name="viewport"', text)
        self.assertIn("4–8 h", text)
        self.assertIn("actions/workflows/executive-5545dbb8.yml", text)
        for token in (">None<", "undefined", "nan%"):
            self.assertNotIn(token, text, f"cadence.html prints a placeholder: {token}")

    def test_workflow_cadence_is_in_the_requested_window(self):
        workflow = ROOT / ".github" / "workflows" / "executive-5545dbb8.yml"
        text = workflow.read_text(encoding="utf-8")
        crons = re.findall(r'-\s*cron:\s*["\']([^"\']+)["\']', text)
        self.assertTrue(crons, "no cron found on the board's workflow")
        for cron in crons:
            fields = cron.split()
            self.assertEqual(len(fields), 5, f"not a cron expression: {cron!r}")
            self.assertTrue(fields[1].startswith("*/"),
                            f"cadence {cron!r} is not an every-N-hours interval")
            step = int(fields[1][2:])
            self.assertGreaterEqual(step, 4, "the board refreshes more often than every 4 h")
            self.assertLessEqual(step, 8, "the board refreshes less often than every 8 h")

    def test_cadence_record_is_written_by_the_collector(self):
        cadence = read_json(DATA / "cadence.json")
        if cadence is None:
            self.skipTest("cadence.json is written by collect.py; this checkout has not run it")
        self.assertEqual(cadence.get("cadence_hours"), 4)
        self.assertTrue(stamp(cadence.get("generated_utc")), "cadence.json has no readable time")
        self.assertIn(cadence.get("event"), ("schedule", "push", "workflow_dispatch", "pull_request", "local"))
        if cadence.get("schedule_cron"):
            self.assertTrue(re.match(r"^\d+ \*/\d+ \* \* \*$", cadence["schedule_cron"]),
                            f"unexpected cron recorded: {cadence['schedule_cron']!r}")

    def test_summary_reports_the_snapshot_age_honestly(self):
        summary = read_json(DATA / "summary.json", {}) or {}
        meta = summary.get("meta") or {}
        self.assertIn("snapshot_age_text", meta)
        self.assertIn("hotspawn_read_text", meta)
        generated, captured = stamp(meta.get("generated_utc")), stamp(meta.get("capture_utc"))
        if generated and captured:
            self.assertGreaterEqual(generated, captured,
                                    "the board was built before the capture it publishes")


class MobileLandingTests(unittest.TestCase):
    """The brief's complaint was that the site is confusing to use on a phone."""

    @classmethod
    def setUpClass(cls):
        page = ROOT / "index.html"
        cls.html = page.read_text(encoding="utf-8") if page.exists() else ""

    def test_landing_is_mobile_ready(self):
        self.assertIn('name="viewport" content="width=device-width', self.html)
        self.assertIn('<html lang="en">', self.html)

    @staticmethod
    def _visible_html(markup: str) -> str:
        """Everything outside a collapsed <details> block — what a phone user sees before tapping."""
        out: list[str] = []
        depth, pos = 0, 0
        for match in re.finditer(r"<(/?)details\b[^>]*>", markup, re.I):
            if depth == 0:
                out.append(markup[pos:match.start()])
            depth = max(0, depth + (-1 if match.group(1) == "/" else 1))
            pos = match.end()
        if depth == 0:
            out.append(markup[pos:])
        return "".join(out)

    def test_one_visible_executive_summary(self):
        """The brief's complaint was competing summaries; archived blocks must stay collapsed."""
        visible = self._visible_html(self.html)
        headings = [re.sub(r"<[^>]+>", "", h).strip()
                    for h in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", visible, re.S)]
        summaries = [h for h in headings if h.lower().startswith("executive summary")]
        self.assertLessEqual(len(summaries), 1,
                             f"{len(summaries)} competing executive-summary headings are visible: {summaries}")
        self.assertLessEqual(headings.count(headings[0]) if headings else 0, 1)
        self.assertGreaterEqual(len(headings), 3, "the visible landing has too little structure to navigate")
        # everything from earlier sessions survives — it is just collapsed, not deleted
        archived = re.findall(r"<details.*?</details>", self.html, re.S)
        self.assertTrue(archived, "no collapsed archive of the earlier boards")

    def test_picks_are_one_tap_away_and_the_flagged_page_is_linked(self):
        self.assertIn('href="executive/picks.html"', self.html)
        self.assertIn('href="executive/flagged.html"', self.html)
        self.assertIn('href="executive/cadence.html"', self.html)
        # The route to the picks must be reachable from the very top of the page, not buried below the fold.
        head, _, body = self.html.partition("<body")
        early = re.findall(r'href="([^"]+)"', body[:1500])
        self.assertTrue(any("picks" in href or href.startswith("#") for href in early[:4]),
                        f"first in-body links are {early[:4]}")

    def test_every_internal_link_on_the_landing_resolves(self):
        checked = 0
        for href in re.findall(r'href="([^"#]+)(?:#[^"]*)?"', self.html):
            if href.startswith(("http", "mailto:", "data:")) or not href:
                continue
            target = (ROOT / href).resolve()
            self.assertTrue(target.exists(), f"landing page links to a missing file: {href}")
            checked += 1
        self.assertGreaterEqual(checked, 8, "the landing page has almost nothing to navigate to")

    def test_no_third_party_requests_on_the_landing(self):
        for token in ("<iframe", "cdn.", "googleapis", "googletagmanager", "<script src=\"http"):
            self.assertNotIn(token, self.html, f"the landing page pulls in {token}")


class NoCrowdDataTests(unittest.TestCase):
    """Hotspawn's crowd is the thing the brief forbids as an input.

    The rule is about *stored values*, so the gate walks the parsed JSON rather than grepping the
    bytes: an ingest log that says which fields it dropped is allowed to spell their names, a fixture
    record that carries one is not. The board's own build check (``executive/tests.py``) keeps the
    same rule at fixture level; this one covers every file the board writes.
    """

    CROWD_KEYS = CROWD_TOKENS + ("pickedpercentage", "pickpercentage", "pick_percent", "pick_pct")
    LOG_KEYS = ("crowd_fields_dropped", "dropped_fields", "fields_dropped")

    def _crowd_values(self, node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}"
                lowered = str(key).lower().strip("_")
                if lowered in self.CROWD_KEYS or lowered.endswith(self.CROWD_KEYS):
                    if value not in (None, "", [], {}, 0, 0.0):
                        yield here, value
                if lowered in self.LOG_KEYS:
                    continue
                yield from self._crowd_values(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from self._crowd_values(value, f"{path}[{index}]")

    def test_no_hotspawn_crowd_value_in_the_board_data(self):
        offenders = []
        for path in sorted(list(DATA.glob("*.json")) + [EXEC / "aliases.json"]):
            payload = read_json(path, None)
            if payload is None:
                continue
            offenders.extend(f"{path.name}{where} = {value!r}"
                             for where, value in self._crowd_values(payload))
        for path in sorted(DATA.glob("*.csv")):
            header = (path.read_text(encoding="utf-8", errors="ignore").splitlines() or [""])[0]
            names = [name.strip().lower() for name in header.split(",")]
            offenders.extend(f"{path.name} column {name!r}" for name in names
                             if name in self.CROWD_KEYS or name.endswith(self.CROWD_KEYS))
        self.assertEqual(offenders, [], "the board stored a Hotspawn crowd value: " + "; ".join(offenders[:6]))

    def test_the_ingest_log_records_what_it_dropped(self):
        payload = read_json(DATA / "hotspawn_pages.json", None)
        if payload is None:
            self.skipTest("no Hotspawn ingest log in this checkout")
        dropped = payload.get("crowd_fields_dropped")
        self.assertIsInstance(dropped, list, "the ingest log must record the crowd fields it removed")
        self.assertTrue(dropped, "the ingest log recorded no dropped crowd fields at all")


if __name__ == "__main__":
    unittest.main(verbosity=2)
