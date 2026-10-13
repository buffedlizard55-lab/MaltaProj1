import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from hotspawn import parse_hotspawn_listing
from market_sources import (
    PolymarketSource,
    _competition_key,
    _match_links,
    _tournament_links,
    parse_thunderpick_match_winner,
)


class FakeResponse:
    def __init__(self, payload, text=None):
        self.payload = payload
        self.text = text or ""

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        if params:
            key = (url, tuple(sorted(params.items())))
        else:
            key = url
        return FakeResponse(self.responses[key])


class HotspawnParserTests(unittest.TestCase):
    def test_reads_fixture_metadata_but_not_pick_percentages_or_timezone(self):
        html = """
        <div>This week 1 matches this week</div>
        <article class="match-card">
          <div>Oct 14, 04:30</div>
          <div>Thunderpick World Championship 2026</div>
          <div>Points available 7 pts Tier S</div>
          <a href="https://www.hotspawn.com/matches/9z-vs-aurora-1080176">View Match</a>
          <div>Who will win?</div>
          <img src="https://assets.example/teams/1.svg" alt="9z" />
          <span>0% picked</span>
          <img src="https://assets.example/teams/2.svg" alt="Aurora" />
          <span>100% picked</span>
        </article>
        """
        result = parse_hotspawn_listing(html, "CS2")
        self.assertEqual(result["statedMatchesThisWeek"], 1)
        self.assertTrue(result["coverageComplete"])
        self.assertEqual(len(result["parsedFixtures"]), 1)
        fixture = result["parsedFixtures"][0]
        self.assertEqual((fixture["teamA"], fixture["teamB"]), ("9z", "Aurora"))
        self.assertEqual(fixture["tournament"], "Thunderpick World Championship 2026")
        self.assertEqual(fixture["hotspawnTimeLabel"], "Oct 14, 04:30")
        self.assertIsNone(fixture["startAtUtc"])
        self.assertFalse(any("picked" in key.casefold() for key in fixture))

    def test_partial_unparsed_links_are_not_claimed_complete(self):
        html = """
        <div>This week 2 matches this week</div>
        <article>
          Oct 14, 04:30 Thunderpick World Championship 2026 Points available
          <a href="https://www.hotspawn.com/matches/one-1080176">View Match</a>
          Who will win? <img src="/teams/1.svg" alt="9z" /><img src="/teams/2.svg" alt="Aurora" />
        </article>
        <a href="https://www.hotspawn.com/matches/two-1234567">View Match</a>
        """
        result = parse_hotspawn_listing(html, "CS2")
        self.assertFalse(result["coverageComplete"])
        self.assertEqual(len(result["parsedFixtures"]), 1)
        self.assertEqual(len(result["unparsedMatchLinks"]), 1)


class ThunderpickParserTests(unittest.TestCase):
    def setUp(self):
        self.fixture = {
            "game": "CS2",
            "tournament": "Thunderpick World Championship 2026",
            "teamA": "9z",
            "teamB": "Aurora",
            "hotspawnTimeLabel": "Oct 14, 04:30",
        }
        self.now = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)

    def test_only_main_match_winner_prices_are_parsed(self):
        html = """
        <h1>9z Team vs Aurora Betting Odds</h1>
        <p>October 14, 04:30</p>
        <section>
          <span>Main</span><span>Match Winner</span>
          <span>9z Team</span><span>+280</span>
          <span>Aurora</span><span>-455</span>
          <span>Match Stats</span>
          <span>Map Winner</span><span>9z Team</span><span>-120</span>
        </section>
        """
        quote, reason = parse_thunderpick_match_winner(
            html,
            self.fixture,
            "https://thunderpick.io/esports/cs2-betting/world/11024/9z-team-vs-aurora/2796376",
            "https://thunderpick.io/esports/cs2-betting/world/11024",
            self.now,
        )
        self.assertEqual(reason, "verified")
        self.assertEqual(quote["oddsA"], "+280")
        self.assertEqual(quote["oddsB"], "-455")
        self.assertAlmostEqual(quote["noVigProbabilityA"], 24.30, places=2)
        self.assertAlmostEqual(quote["noVigProbabilityB"], 75.70, places=2)
        self.assertIn("thunderpick.io", quote["sourceUrl"])

    def test_unlabeled_timezone_is_not_required_or_inferred_for_probability(self):
        html = """
        <div>Match Winner 9z Team +280 Aurora -455 Match Stats</div>
        <div>October 14, 04:30</div>
        """
        quote, reason = parse_thunderpick_match_winner(
            html, self.fixture, "https://thunderpick.io/event", "https://thunderpick.io/tournament", self.now
        )
        self.assertEqual(reason, "verified")
        self.assertNotIn("startAtUtc", quote)

    def test_date_mismatch_leaves_price_blank(self):
        html = """
        <div>Match Winner 9z Team +280 Aurora -455 Match Stats</div>
        <div>October 15, 04:30</div>
        """
        quote, reason = parse_thunderpick_match_winner(
            html, self.fixture, "https://thunderpick.io/event", "https://thunderpick.io/tournament", self.now
        )
        self.assertIsNone(quote)
        self.assertIn("date", reason)

    def test_competition_page_discovery_is_exact_and_extracts_match_link(self):
        index_url = "https://thunderpick.io/esports/cs2-betting"
        index_html = """
        <a href="/esports/cs2-betting/thunderpick-world-championship-2026/11024">Thunderpick World Championship 2026 6</a>
        <a href="/esports/cs2-betting/pulse-beat-iii/11173">Pulse Beat III 5</a>
        """
        tournaments = _tournament_links(index_html, "CS2", index_url)
        self.assertEqual(len(tournaments), 2)
        self.assertEqual(_competition_key("Stake Pulse Beat III"), _competition_key("Pulse Beat III"))
        fixture = self.fixture
        tournament_url = tournaments[0]["url"]
        tournament_html = """
        <a href="/esports/cs2-betting/thunderpick-world-championship-2026/11024/9z-team-vs-aurora/2796376">9z vs Aurora</a>
        <a href="/esports/cs2-betting/thunderpick-world-championship-2026/11024/liquid-vs-jijiehao/2819718">Liquid vs JiJieHao</a>
        """
        links = _match_links(tournament_html, tournament_url, fixture)
        self.assertEqual(
            links,
            ["https://thunderpick.io/esports/cs2-betting/thunderpick-world-championship-2026/11024/9z-team-vs-aurora/2796376"],
        )


class PolymarketParserTests(unittest.TestCase):
    def test_exact_active_series_match_winner_maps_outcomes_not_order(self):
        search_url = "https://gamma-api.polymarket.com/public-search"
        search_params = (("q", "9z Aurora"),)
        market_url = "https://gamma-api.polymarket.com/markets?slug=cs2-9z-aur1-2026-10-14"
        responses = {
            (search_url, search_params): {
                "events": [
                    {
                        "title": "9z Team vs Aurora Gaming",
                        "slug": "cs2-9z-aur1-2026-10-14",
                        "active": True,
                        "closed": False,
                        "gameStartTime": "2026-10-14T08:30:00Z",
                    }
                ]
            },
            market_url: [
                {
                    "groupItemTitle": "Match Winner",
                    "active": True,
                    "closed": False,
                    "outcomes": json.dumps(["Aurora Gaming", "9z Team"]),
                    "outcomePrices": json.dumps(["0.745", "0.255"]),
                    "updatedAt": "2026-10-13T17:55:29Z",
                    "volumeNum": "26101.10",
                },
                {
                    "groupItemTitle": "Map 1 Winner",
                    "active": True,
                    "closed": False,
                    "outcomes": json.dumps(["Aurora Gaming", "9z Team"]),
                    "outcomePrices": json.dumps(["0.725", "0.275"]),
                },
            ],
        }
        source = PolymarketSource(FakeSession(responses))
        fixture = {
            "teamA": "9z",
            "teamB": "Aurora",
            "hotspawnTimeLabel": "Oct 14, 04:30",
        }
        quote, reason = source.quote_for(fixture, datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc))
        self.assertEqual(reason, "verified")
        self.assertEqual(quote["priceA"], 25.5)
        self.assertEqual(quote["priceB"], 74.5)
        self.assertIn("not a sportsbook", quote["marketType"])
        self.assertEqual(quote["eventStartAtUtc"], "2026-10-14T08:30:00Z")

    def test_closed_or_wrong_date_event_is_not_matched(self):
        search_url = "https://gamma-api.polymarket.com/public-search"
        search_params = (("q", "9z Aurora"),)
        responses = {
            (search_url, search_params): {
                "events": [
                    {
                        "title": "9z Team vs Aurora Gaming",
                        "slug": "old-event",
                        "active": True,
                        "closed": False,
                        "gameStartTime": "2026-10-15T08:30:00Z",
                    }
                ]
            }
        }
        source = PolymarketSource(FakeSession(responses))
        quote, _ = source.quote_for(
            {"teamA": "9z", "teamB": "Aurora", "hotspawnTimeLabel": "Oct 14, 04:30"},
            datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc),
        )
        self.assertIsNone(quote)


if __name__ == "__main__":
    unittest.main()
