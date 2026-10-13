"""Normalize public Pinnacle website responses observed in an ordinary browser.

This does not access the licensed api.pinnacle.com service, log in, copy API keys,
or call unobserved endpoints. American prices are explicitly converted to decimal.
"""
from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urlparse

from collector.analytics import american_to_decimal, iso_time, parse_time

PUBLIC_PAGE = "https://www.pinnacle.com/en/esports/matchups/highlights/"
PUBLIC_PAGES = (
    PUBLIC_PAGE,
    "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
    "https://www.pinnacle.com/en/esports/games/league-of-legends/matchups/",
)


def game_for_league(name: str) -> str | None:
    if not isinstance(name, str):
        return None
    if name.startswith("CS2 - "):
        return "cs2"
    if name.startswith("League of Legends - "):
        return "lol"
    return None


def relevant_response(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.hostname != "guest.api.arcadia.pinnacle.com":
        return False
    return "/matchups" in parsed.path or "/markets/" in parsed.path


def event_link(event_id: int | str, links: list[str], page_url: str) -> str:
    # Only an actually observed hyperlink; never invent a slug/deep link.
    for link in links:
        parsed = urlparse(link)
        if parsed.scheme == "https" and parsed.hostname == "www.pinnacle.com" and re.search(rf"/{re.escape(str(event_id))}/?$", parsed.path):
            return link
    return page_url


def normalize_quotes(packets: list[dict], links: list[str], now: datetime) -> tuple[list[dict], dict]:
    events: dict[int, tuple[dict, dict, int]] = {}
    markets: list[tuple[dict, dict, int]] = []
    for packet in packets:
        data = packet.get("body")
        if not isinstance(data, list) or not relevant_response(packet.get("url", "")):
            continue
        if "/matchups" in packet["url"]:
            for index, event in enumerate(data):
                if isinstance(event, dict) and isinstance(event.get("id"), int):
                    previous = events.get(event["id"])
                    if previous is None or packet["retrieved_at"] >= previous[1]["retrieved_at"]:
                        events[event["id"]] = (event, packet, index)
        elif "/markets/" in packet["url"]:
            markets.extend((market, packet, index) for index, market in enumerate(data) if isinstance(market, dict))

    result: dict[tuple[str, int], dict] = {}
    counters = {"event_records": len(events), "market_records": len(markets), "wrong_period_or_type": 0, "closed_live_or_started": 0, "unsupported_or_unconfirmed": 0}
    for market, packet, market_index in markets:
        if market.get("type") != "moneyline" or market.get("period") != 0 or market.get("isAlternate") is not False:
            counters["wrong_period_or_type"] += 1
            continue
        event_record = events.get(market.get("matchupId"))
        if event_record is None:
            counters["unsupported_or_unconfirmed"] += 1
            continue
        event, event_packet, event_index = event_record
        league = event.get("league") or {}
        game = game_for_league(league.get("name", ""))
        participants = event.get("participants")
        prices = market.get("prices")
        if (game is None or (league.get("sport") or {}).get("id") != 12
                or "parentId" not in event or "parent" not in event
                or event.get("parentId") is not None or event.get("parent") is not None
                or event.get("type") != "matchup" or not isinstance(participants, list)
                or len(participants) != 2 or not isinstance(prices, list) or len(prices) != 2):
            counters["unsupported_or_unconfirmed"] += 1
            continue
        start = parse_time(event.get("startTime"))
        cutoff = parse_time(market.get("cutoffAt"))
        period = next((item for item in event.get("periods", []) if item.get("period") == 0), None)
        if (event.get("isLive") is not False or event.get("status") != "pending"
                or market.get("status") != "open" or start is None or start <= now
                or cutoff is None or cutoff <= now or period is None or period.get("status") != "open"):
            counters["closed_live_or_started"] += 1
            continue
        names = {item.get("alignment"): item.get("name") for item in participants}
        native = {item.get("designation"): item.get("price") for item in prices}
        if set(names) != {"home", "away"} or set(native) != {"home", "away"} or not all(isinstance(value, str) and value for value in names.values()):
            counters["unsupported_or_unconfirmed"] += 1
            continue
        try:
            a, b = american_to_decimal(native["home"]), american_to_decimal(native["away"])
        except ValueError:
            counters["unsupported_or_unconfirmed"] += 1
            continue
        quote = {
            "id": f'pinnacle:{event["id"]}:{market.get("version")}',
            "source_id": "pinnacle", "source_name": "Pinnacle", "source_role": "primary_bookmaker",
            "event_id": str(event["id"]), "game": game,
            "team_a": names["home"], "team_b": names["away"],
            "tournament": league["name"], "start_time": iso_time(start),
            "best_of": event.get("bestOfX"),
            "market_type": "match_winner", "period": "match", "outcome_count": 2,
            "status": "open", "is_live": False,
            "native_format": "american", "native_odds_a": native["home"], "native_odds_b": native["away"],
            "odds_a": a, "odds_b": b, "decimal_format_note": "Calculated conversion from native American prices; not rounded website display values.",
            "observed_at": packet["retrieved_at"], "source_published_at": None,
            "source_url": event_link(event["id"], links, packet.get("observed_in") or PUBLIC_PAGE),
            "api_url": packet["url"], "evidence_id": packet["evidence_id"],
            "evidence_locator": f"/{market_index}",
            "event_evidence_id": event_packet["evidence_id"], "event_evidence_locator": f"/{event_index}",
            "identity_rule": "Exact game, team-pair names (case/whitespace/Unicode only), and UTC start; no aliases guessed.",
        }
        key = (quote["source_id"], event["id"])
        if key not in result or quote["observed_at"] >= result[key]["observed_at"]:
            result[key] = quote
    counters["eligible_quote_records"] = len(result)
    return sorted(result.values(), key=lambda quote: (quote["start_time"], quote["id"])), counters
