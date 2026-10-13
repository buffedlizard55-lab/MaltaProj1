"""Synthetic parser fixtures only; these are never published as real matches."""
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from collector.hotspawn import epoch_ms, extract_records, project_page
from collector.pinnacle import normalize_quotes, relevant_response
from collector.runner import Ledger
from scripts.validate import ValidationError, validate_data

NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)
LOBBY = "https://play.hotspawn.com/lobby"
FIXTURE = {
    "id": "1234567", "competition_id": "test-only", "competition_name": "Synthetic test tournament",
    "sport_alias": "cs2", "sport_name": "Counter-Strike 2", "status": "scheduled",
    "scheduled_start_time": "1791966600000", "lock_time": "1791966240000", "lock_offset_sec": 360,
    "best_of": None, "series_format": None, "tier": "b", "stage": None,
    "participants0_id": "unit-a", "participants0_name": "Alpha",
    "participants1_id": "unit-b", "participants1_name": "Bravo",
    "participants0_picked_percent": 100, "participants1_picked_percent": 0,
}


def source_html(record=None, card=True):
    record = record or FIXTURE
    state = {
        "fixture-cache": {"s": 200, "u": "https://phpstack-1372681-6459848.cloudwaysapps.com/api/v1/fixtures", "b": [record]},
        "unrelated-leaderboard": {"s": 200, "u": "https://example.invalid/leaderboard", "b": {"entries": [{"email": "synthetic-test@example.invalid", "userId": "synthetic"}]}},
    }
    rendered = '''<h2>Closing Soon</h2><app-pickem-vs-card><div class="vs-card-team-name">Alpha</div><div class="vs-card-team-name">Bravo</div><div class="vs-card-tournament">Synthetic test tournament</div><a href="https://www.hotspawn.com/matches/unit-test-only-1234567">View match</a></app-pickem-vs-card>''' if card else ""
    return ('<html><body>All tiers (1)' + rendered + '<script id="ng-state" type="application/json">' + json.dumps(state) + '</script></body></html>').encode()


def packets(event_changes=None, market_changes=None):
    event = {"id": 101, "type": "matchup", "parentId": None, "parent": None, "isLive": False, "status": "pending", "startTime": "2026-10-14T08:30:00Z", "bestOfX": 3,
             "league": {"name": "CS2 - Synthetic test tournament", "sport": {"id": 12}}, "periods": [{"period": 0, "status": "open"}],
             "participants": [{"alignment": "home", "name": "Alpha"}, {"alignment": "away", "name": "Bravo"}]}
    market = {"matchupId": 101, "type": "moneyline", "period": 0, "isAlternate": False, "status": "open", "cutoffAt": "2026-10-14T08:30:00Z", "version": 123,
              "prices": [{"designation": "away", "price": 200}, {"designation": "home", "price": -200}]}
    event.update(event_changes or {})
    market.update(market_changes or {})
    common = {"retrieved_at": "2026-10-13T17:59:00Z", "observed_in": "https://www.pinnacle.com/en/esports/matchups/highlights/"}
    return [{**common, "url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/highlighted", "evidence_id": "test-events", "body": [event]},
            {**common, "url": "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/highlighted/straight", "evidence_id": "test-markets", "body": [market]}]


class HotspawnTests(unittest.TestCase):
    def test_public_fixture_state_and_explicit_epoch(self):
        projection = project_page(source_html(), LOBBY)
        rows, inventory, info = extract_records(projection, "test-evidence")
        self.assertEqual(info["parsed_board_count"], 1)
        self.assertEqual(len(inventory), 1)
        self.assertEqual(rows[0]["start_time"], "2026-10-14T08:30:00Z")
        self.assertEqual(rows[0]["lock_time"], "2026-10-14T08:24:00Z")
        self.assertIsNone(rows[0]["best_of"])
        self.assertEqual(rows[0]["source_url"], "https://www.hotspawn.com/matches/unit-test-only-1234567")

    def test_unrelated_personal_and_crowd_values_are_excluded(self):
        projection = project_page(source_html(), LOBBY)
        serialized = json.dumps(projection)
        for forbidden in ("synthetic-test@example", "userId", "picked_percent", "unrelated-leaderboard"):
            self.assertNotIn(forbidden, serialized)

    def test_missing_names_stay_blank_but_the_row_is_retained(self):
        rows, inventory, _ = extract_records(project_page(source_html({**FIXTURE, "participants0_name": None}), LOBBY), "test")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(inventory), 1)
        self.assertIsNone(rows[0]["team_a"])
        self.assertEqual(rows[0]["team_b"], "Bravo")

    def test_source_state_is_not_assumed_rendered(self):
        rows, inventory, info = extract_records(project_page(source_html(card=False), LOBBY), "test")
        self.assertEqual(rows, [])
        self.assertEqual(len(inventory), 1)
        self.assertFalse(inventory[0]["on_rendered_board"])
        self.assertEqual(inventory[0]["source_url"], LOBBY)

    def test_card_identity_conflict_is_not_filled(self):
        rows, _, info = extract_records(project_page(source_html({**FIXTURE, "participants0_name": "Different"}), LOBBY), "test")
        self.assertEqual(rows, [])
        self.assertEqual(info["conflicting_card_ids"], ["1234567"])

    def test_no_state_fails_closed(self):
        with self.assertRaises(ValueError):
            project_page(b"<html>changed source</html>", LOBBY)

    def test_epoch_is_not_guessed_from_local_time_or_countdown(self):
        for bad in ("Oct 14, 04:30", "2026-10-14T08:30:00", "1791966600", "14h 30m", None, True):
            self.assertIsNone(epoch_ms(bad))


class PinnacleTests(unittest.TestCase):
    def test_exact_whole_match_market_and_native_conversion(self):
        links = ["https://www.pinnacle.com/en/esports/test-only/alpha-vs-bravo/101/"]
        quotes, _ = normalize_quotes(packets(), links, NOW)
        self.assertEqual(len(quotes), 1)
        quote = quotes[0]
        self.assertEqual(quote["odds_a"], 1.5)
        self.assertEqual(quote["odds_b"], 3.)
        self.assertEqual(quote["team_a"], "Alpha")
        self.assertEqual(quote["native_format"], "american")
        self.assertEqual(quote["source_url"], links[0])
        self.assertEqual(quote["event_evidence_id"], "test-events")

    def test_only_observed_event_links(self):
        quotes, _ = normalize_quotes(packets(), [], NOW)
        self.assertEqual(quotes[0]["source_url"], packets()[0]["observed_in"])
        self.assertNotIn("alpha-vs-bravo", quotes[0]["source_url"])

    def test_map_handicap_closed_draw_alternate_and_started_rejected(self):
        for change in ({"period": 1}, {"type": "spread"}, {"status": "suspended"}, {"isAlternate": True}, {"cutoffAt": "2026-10-13T17:00:00Z"}, {"prices": [{"designation": "home", "price": -200}, {"designation": "away", "price": 200}, {"designation": "draw", "price": 300}]}):
            with self.subTest(change=change):
                self.assertEqual(normalize_quotes(packets(market_changes=change), [], NOW)[0], [])
        for change in ({"isLive": True}, {"status": "started"}, {"parentId": 100}, {"startTime": "2026-10-14T08:30:00"}, {"startTime": "2026-10-13T17:00:00Z"}, {"league": {"name": "Unknown", "sport": {"id": 12}}}):
            with self.subTest(change=change):
                self.assertEqual(normalize_quotes(packets(event_changes=change), [], NOW)[0], [])

    def test_repeated_source_body_and_timestamp_ties_use_capture_order(self):
        original = packets()
        original[0]["capture_sequence"] = 1
        changed = {**original[0], "evidence_id": "another-events-body", "capture_sequence": 2}
        repeated = {**original[0], "capture_sequence": 3}
        forward, _ = normalize_quotes([original[0], changed, repeated, original[1]], [], NOW)
        reordered, _ = normalize_quotes([changed, repeated, original[1]], [], NOW)
        self.assertEqual(forward, reordered)
        self.assertEqual(forward[0]["event_evidence_id"], "test-events")

    def test_later_suspended_market_does_not_resurrect_earlier_open_price(self):
        original = packets()
        later = {**original[1], "retrieved_at": "2026-10-13T17:59:30Z", "evidence_id": "later-market", "body": [{**original[1]["body"][0], "status": "suspended"}]}
        self.assertEqual(normalize_quotes(original + [later], [], NOW)[0], [])

    def test_link_choice_is_stable_across_evidence_order(self):
        a = "https://www.pinnacle.com/en/esports/a-test/alpha-vs-bravo/101/"
        b = "https://www.pinnacle.com/en/esports/b-test/alpha-vs-bravo/101/"
        first, _ = normalize_quotes(packets(), [a, b], NOW)
        second, _ = normalize_quotes(packets(), [b, a], NOW)
        self.assertEqual(first, second)
        self.assertEqual(first[0]["source_url"], a)

    def test_private_or_unobserved_origins_not_accepted(self):
        self.assertFalse(relevant_response("https://api.pinnacle.com/v2/odds"))
        self.assertFalse(relevant_response("https://guest.api.arcadia.pinnacle.com/0.1/account"))
        self.assertFalse(relevant_response("https://untrusted.invalid/matchups"))

    def test_source_names_not_guessed(self):
        event = {"participants": [{"alignment": "home", "name": "PVISION"}, {"alignment": "away", "name": "BB Team"}]}
        quotes, _ = normalize_quotes(packets(event_changes=event), [], NOW)
        self.assertEqual(quotes[0]["team_a"], "PVISION")
        self.assertEqual(quotes[0]["team_b"], "BB Team")


class EvidenceTests(unittest.TestCase):
    def make_snapshot(self, folder):
        ledger = Ledger(folder)
        projection = project_page(source_html(), LOBBY)
        entry = ledger.json(projection, url=LOBBY, at="2026-10-13T17:59:00Z", source_id="hotspawn", kind="hotspawn_fixture_transfer_state", description="Synthetic test evidence, never production")
        rows, inventory, _ = extract_records(projection, entry["id"])
        from collector.analytics import analyze_match
        for row in rows:
            row["analysis"] = analyze_match(row, [], NOW)
        return {"schema_version": 1, "generated_at": "2026-10-13T18:00:00Z", "matches": rows, "inventory": inventory, "quotes": [], "evidence": list(ledger.entries.values()), "sources": [{"id": "hotspawn", "url": LOBBY}], "findings": [], "coverage": {"status": "partial"}}

    def test_every_populated_field_rechecked_and_missing_values_null(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            data = self.make_snapshot(folder)
            self.assertEqual(validate_data(data, folder)["unpriced_count"], 1)
            data["matches"][0]["best_of"] = 3
            with self.assertRaises(ValueError):
                validate_data(data, folder)

    def test_source_content_hash_corruption_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            data = self.make_snapshot(folder)
            path = folder / data["evidence"][0]["file"]
            path.write_bytes(gzip.compress(b"{}"))
            with self.assertRaises(ValidationError):
                validate_data(data, folder)

    def test_unverified_probability_cannot_be_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            data = self.make_snapshot(folder)
            data["matches"][0]["analysis"]["probability_a"] = .5
            with self.assertRaises(ValidationError):
                validate_data(data, folder)

    def test_complete_list_claim_requires_positive_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            data = self.make_snapshot(folder)
            data["coverage"]["status"] = "complete"
            with self.assertRaises(ValidationError):
                validate_data(data, folder)


if __name__ == "__main__":
    unittest.main()
