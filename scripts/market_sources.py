"""Conservative readers for official sportsbook and prediction-market pages.

Only independently sourced two-way series Match Winner markets are eligible.
Anything ambiguous, missing, suspended, closed, or mapped only by a fuzzy name
match is left unpriced for the refresh pipeline to flag.
"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from hotspawn import DATE_RE
from odds import as_percent, no_vig_two_way

POLYMARKET_API = "https://gamma-api.polymarket.com"
POLYMARKET_WEB = "https://polymarket.com"
THUNDERPICK_ROOT = "https://thunderpick.io"
THUNDERPICK_INDEX = {
    "CS2": "https://thunderpick.io/esports/cs2-betting",
    "LoL": "https://thunderpick.io/esports/league-of-legends",
}
THUNDERPICK_ROUTE = {"CS2": "cs2-betting", "LoL": "league-of-legends"}

# These are spelling variants observed on the linked official pages. There is
# deliberately no edit-distance/team-name guessing: unknown variants stay blank.
TEAM_ALIASES: dict[str, set[str]] = {
    "9z": {"9z team"},
    "aurora": {"aurora gaming"},
    "sashi": {"sashi esport"},
    "ex keyd stars": {"keyd stars", "exkeyd stars"},
}

# Sponsor prefixes are removed only where they are explicit in the competition
# label (e.g. Hotspawn's "Stake Pulse Beat III" vs Thunderpick's "Pulse Beat III").
TOURNAMENT_PREFIXES = ("stake ", "thunderpick ")
AMERICAN_RE = re.compile(r"^[+-]\s*\d{1,6}(?:,\d{3})*(?:\.\d+)?$")


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value)).casefold()
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", unaccented))


def _team_variants(team: str) -> set[str]:
    key = normalize_name(team)
    variants = {key}
    variants.update(normalize_name(item) for item in TEAM_ALIASES.get(key, set()))
    # Accept only a small set of common, semantically redundant official
    # suffixes. This is not used to identify a fixture on its own; both teams,
    # competition, and calendar date are checked independently.
    for variant in tuple(variants):
        for suffix in (" team", " gaming", " esport", " esports"):
            if variant.endswith(suffix):
                variants.add(variant[: -len(suffix)].strip())
    return {variant for variant in variants if variant}


def same_team(left: str, right: str) -> bool:
    return bool(_team_variants(left) & _team_variants(right))


def _contains_team(text: str, team: str) -> bool:
    haystack = normalize_name(text)
    for variant in sorted(_team_variants(team), key=len, reverse=True):
        # Tokenized normalized strings keep short names such as 9z intact.
        if f" {variant} " in f" {haystack} ":
            return True
    return False


def _parse_explicit_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _raw_month_day(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    match = DATE_RE.search(value)
    if not match:
        return None
    token = match.group(0).split(",", 1)[0]
    try:
        parsed = datetime.strptime(token, "%b %d")
    except ValueError:
        try:
            parsed = datetime.strptime(token, "%B %d")
        except ValueError:
            return None
    return parsed.month, parsed.day


def _event_utc_time(event: dict[str, Any]) -> datetime | None:
    # Use an explicitly zoned field only; never infer a zone from the browser,
    # event title, or Hotspawn's unlabeled lobby clock.
    for key in ("gameStartTime", "eventStartTime", "startTime", "startDate"):
        parsed = _parse_explicit_datetime(event.get(key))
        if parsed is not None:
            return parsed
    return None


def _json_list(value: Any) -> list[Any] | None:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, list) else None
    return None


def _is_true(value: Any) -> bool:
    return value is True or (isinstance(value, str) and value.casefold() == "true")


def _is_false(value: Any) -> bool:
    return value is False or (isinstance(value, str) and value.casefold() == "false")


def _walk_dicts(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _search_events(payload: Any) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in _walk_dicts(payload):
        slug = item.get("slug")
        title = item.get("title") or item.get("name") or item.get("question")
        if not isinstance(slug, str) or not isinstance(title, str):
            continue
        if not (item.get("eventStartTime") or item.get("gameStartTime") or item.get("startDate")):
            continue
        if slug in seen:
            continue
        seen.add(slug)
        events.append(item)
    return events


def _exact_pair_in_text(text: str, team_a: str, team_b: str) -> bool:
    return _contains_team(text, team_a) and _contains_team(text, team_b)


def _event_title(event: dict[str, Any]) -> str:
    return " ".join(
        str(event.get(key, ""))
        for key in ("title", "name", "question", "description")
        if event.get(key)
    )


class PolymarketSource:
    """Resolve active exact-date series Match Winner markets from Gamma API."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.cache: dict[tuple[str, str, str], tuple[dict[str, Any] | None, str]] = {}

    def quote_for(self, fixture: dict[str, Any], retrieved_at: datetime) -> tuple[dict[str, Any] | None, str]:
        team_a, team_b = fixture["teamA"], fixture["teamB"]
        date_key = fixture.get("hotspawnTimeLabel") or ""
        cache_key = (normalize_name(team_a), normalize_name(team_b), date_key)
        if cache_key in self.cache:
            return self.cache[cache_key]
        query = f"{team_a} {team_b}"
        try:
            # Keep the unauthenticated public search feed within a polite,
            # predictable request rate for a large weekly fixture set.
            time.sleep(0.08)
            response = self.session.get(
                f"{POLYMARKET_API}/public-search",
                params={"q": query},
                timeout=25,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            result = (None, f"Polymarket public search failed: {exc}")
            self.cache[cache_key] = result
            return result

        expected_month_day = _raw_month_day(fixture.get("hotspawnTimeLabel"))
        event_candidates: list[tuple[dict[str, Any], datetime]] = []
        for event in _search_events(payload):
            if _is_true(event.get("closed")) or _is_false(event.get("active")):
                continue
            if not _exact_pair_in_text(_event_title(event), team_a, team_b):
                continue
            utc_start = _event_utc_time(event)
            if utc_start is None:
                continue
            if expected_month_day and (utc_start.month, utc_start.day) != expected_month_day:
                continue
            event_candidates.append((event, utc_start))

        if len(event_candidates) != 1:
            reason = (
                "No active Polymarket event with an exact team pair and explicit matching calendar date was verified."
                if not event_candidates
                else "More than one active Polymarket event matched the exact pair/date; quote left blank."
            )
            result = (None, reason)
            self.cache[cache_key] = result
            return result

        event, utc_start = event_candidates[0]
        slug = event["slug"]
        api_url = f"{POLYMARKET_API}/markets?slug={quote(slug, safe='-') }"
        try:
            response = self.session.get(api_url, timeout=25)
            response.raise_for_status()
            market_payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            result = (None, f"Polymarket market details failed: {exc}")
            self.cache[cache_key] = result
            return result

        markets = market_payload if isinstance(market_payload, list) else market_payload.get("markets", []) if isinstance(market_payload, dict) else []
        matching_markets = []
        for market in markets:
            if not isinstance(market, dict):
                continue
            group_title = market.get("groupItemTitle")
            if not isinstance(group_title, str) or group_title.strip().casefold() != "match winner":
                continue
            if _is_true(market.get("closed")) or _is_false(market.get("active")):
                continue
            outcomes = _json_list(market.get("outcomes"))
            prices = _json_list(market.get("outcomePrices"))
            if not outcomes or not prices or len(outcomes) != 2 or len(prices) != 2:
                continue
            mapped: dict[str, Decimal] = {}
            try:
                for outcome, price in zip(outcomes, prices):
                    if not isinstance(outcome, str):
                        continue
                    numeric = Decimal(str(price))
                    if not numeric.is_finite() or numeric < 0 or numeric > 1:
                        continue
                    if same_team(outcome, team_a):
                        mapped["a"] = numeric
                    elif same_team(outcome, team_b):
                        mapped["b"] = numeric
            except Exception:
                continue
            if set(mapped) == {"a", "b"}:
                matching_markets.append((market, mapped))

        if len(matching_markets) != 1:
            reason = (
                "No active official Polymarket series Match Winner contract with both exact team outcomes was verified."
                if not matching_markets
                else "More than one active series Match Winner contract matched; exchange quote left blank."
            )
            result = (None, reason)
            self.cache[cache_key] = result
            return result

        market, mapped = matching_markets[0]
        price_a = mapped["a"]
        price_b = mapped["b"]
        market_slug = str(market.get("slug") or slug)
        ui_slug = str(event.get("slug") or market_slug)
        volume = market.get("volumeNum", market.get("volume", event.get("volume")))
        try:
            volume_usd = float(volume) if volume is not None else None
        except (TypeError, ValueError):
            volume_usd = None
        source_updated_at = market.get("updatedAt") or market.get("updated_at")
        result = (
            {
                "name": "Polymarket",
                "marketType": "prediction-market series Match Winner; not a sportsbook",
                "priceA": float(price_a * Decimal(100)),
                "priceB": float(price_b * Decimal(100)),
                "priceUnit": "cents per outcome share",
                "sourceUpdatedAt": source_updated_at,
                "retrievedAtUtc": retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                "volumeUsd": volume_usd,
                "sourceUrl": f"{POLYMARKET_WEB}/event/{ui_slug}",
                "apiUrl": api_url,
                "eventStartAtUtc": utc_start.isoformat().replace("+00:00", "Z"),
            },
            "verified",
        )
        self.cache[cache_key] = result
        return result


def _competition_key(value: str) -> str:
    key = normalize_name(value)
    for prefix in TOURNAMENT_PREFIXES:
        normalized_prefix = normalize_name(prefix)
        if key.startswith(normalized_prefix + " "):
            key = key[len(normalized_prefix) + 1 :]
    return key


def _tournament_links(html: str, game: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    route = THUNDERPICK_ROUTE[game]
    found: dict[str, dict[str, str]] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, str(anchor.get("href", "")).strip())
        parsed = urlparse(href)
        if parsed.netloc.casefold() not in {"thunderpick.io", "www.thunderpick.io"}:
            continue
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 4 or parts[0] != "esports" or parts[1] != route or not parts[3].isdigit():
            continue
        label = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True)).strip()
        label = re.sub(r"\s+\d+$", "", label).strip()
        if not label:
            continue
        canonical_url = f"{THUNDERPICK_ROOT}{parsed.path}"
        found[canonical_url] = {"name": label, "url": canonical_url}
    return list(found.values())


def _matching_tournaments(fixture: dict[str, Any], tournaments: list[dict[str, str]]) -> list[dict[str, str]]:
    expected = _competition_key(str(fixture.get("tournament") or ""))
    if not expected:
        return []
    matches = []
    for item in tournaments:
        actual = _competition_key(item["name"])
        if expected == actual:
            matches.append(item)
    return matches


def _slug_team_pair(match_slug: str) -> tuple[str, str] | None:
    if "-vs-" not in match_slug:
        return None
    left, right = match_slug.rsplit("-vs-", 1)
    if not left or not right:
        return None
    return left.replace("-", " "), right.replace("-", " ")


def _match_links(html: str, tournament_url: str, fixture: dict[str, Any]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    route = THUNDERPICK_ROUTE[fixture["game"]]
    target_tournament_url = urlparse(tournament_url).path.rstrip("/")
    found: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = urljoin(tournament_url, str(anchor.get("href", "")).strip())
        parsed = urlparse(href)
        if parsed.netloc.casefold() not in {"thunderpick.io", "www.thunderpick.io"}:
            continue
        path = parsed.path.rstrip("/")
        parts = [part for part in path.split("/") if part]
        if len(parts) < 6 or parts[0] != "esports" or parts[1] != route or not parts[-1].isdigit():
            continue
        if not path.startswith(target_tournament_url + "/"):
            continue
        pair = _slug_team_pair(parts[-2])
        if pair is None:
            continue
        if not (
            (same_team(pair[0], fixture["teamA"]) and same_team(pair[1], fixture["teamB"]))
            or (same_team(pair[1], fixture["teamA"]) and same_team(pair[0], fixture["teamB"]))
        ):
            continue
        found.add(f"{THUNDERPICK_ROOT}{path}")
    return sorted(found)


def _american_for_team(market_text: str, team: str) -> str | None:
    variants = sorted(_team_variants(team), key=len, reverse=True)
    for variant in variants:
        escaped = re.escape(variant).replace(r"\ ", r"\s+")
        pattern = re.compile(rf"(?<![a-z0-9]){escaped}\s+([+-]\s*\d{{1,6}}(?:,\d{{3}})*(?:\.\d+)?)(?!\w)", re.IGNORECASE)
        found = pattern.search(market_text)
        if found:
            return found.group(1).replace(" ", "").replace(",", "")
    return None


def parse_thunderpick_match_winner(
    html: str,
    fixture: dict[str, Any],
    source_url: str,
    context_url: str,
    retrieved_at: datetime,
) -> tuple[dict[str, Any] | None, str]:
    """Extract only the named Match Winner two-way market from a detail page."""

    soup = BeautifulSoup(html, "html.parser")
    full_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).replace("\xa0", " ")
    match = re.search(r"\bMatch\s+Winner\b", full_text, re.IGNORECASE)
    if not match:
        return None, "Official Thunderpick detail page has no explicit Match Winner market label."
    market_text = full_text[match.end() :]
    stop = re.search(
        r"\b(?:Match\s+Stats|Map\s+[123]|Map\s+Winner|Player\s+Props|Totals?|Handicaps?)\b",
        market_text,
        re.IGNORECASE,
    )
    if stop:
        market_text = market_text[: stop.start()]

    odds_a = _american_for_team(market_text, fixture["teamA"])
    odds_b = _american_for_team(market_text, fixture["teamB"])
    if not odds_a or not odds_b:
        return None, "Thunderpick Match Winner did not expose two signed American prices for the exact fixture teams."
    if not AMERICAN_RE.fullmatch(odds_a) or not AMERICAN_RE.fullmatch(odds_b):
        return None, "Thunderpick prices were not verified as signed American odds."

    page_month_day = _raw_month_day(full_text)
    fixture_month_day = _raw_month_day(fixture.get("hotspawnTimeLabel"))
    if not page_month_day or not fixture_month_day or page_month_day != fixture_month_day:
        return None, "Thunderpick detail-page date did not explicitly match the Hotspawn fixture's displayed calendar date."

    try:
        fair = no_vig_two_way(odds_a, odds_b)
    except ValueError as exc:
        return None, f"Thunderpick two-way odds could not be normalized: {exc}"
    return (
        {
            "name": "Thunderpick",
            "market": "Match Winner",
            "oddsFormat": "American",
            "oddsA": odds_a,
            "oddsB": odds_b,
            "rawProbabilityA": float(as_percent(fair["raw_a"])),
            "rawProbabilityB": float(as_percent(fair["raw_b"])),
            "overroundPct": float(as_percent(fair["overround"])),
            "noVigProbabilityA": float(as_percent(fair["fair_a"])),
            "noVigProbabilityB": float(as_percent(fair["fair_b"])),
            "verifiedOn": retrieved_at.astimezone(timezone.utc).date().isoformat(),
            "retrievedAtUtc": retrieved_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "sourceTimestamp": None,
            "sourceUrl": source_url,
            "contextUrl": context_url,
        },
        "verified",
    )


class ThunderpickSource:
    """Discover exact fixture pages from the bookmaker's official indexes."""

    def __init__(self, session: requests.Session):
        self.session = session
        self._tournaments: dict[str, tuple[list[dict[str, str]], str | None]] = {}
        self._html_cache: dict[str, str] = {}

    def _get_html(self, url: str) -> str:
        if url not in self._html_cache:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            self._html_cache[url] = response.text
        return self._html_cache[url]

    def _get_tournaments(self, game: str) -> tuple[list[dict[str, str]], str | None]:
        if game in self._tournaments:
            return self._tournaments[game]
        index_url = THUNDERPICK_INDEX[game]
        try:
            html = self._get_html(index_url)
            result = (_tournament_links(html, game, index_url), None)
        except requests.RequestException as exc:
            result = ([], f"Thunderpick {game} index request failed: {exc}")
        self._tournaments[game] = result
        return result

    def quote_for(self, fixture: dict[str, Any], retrieved_at: datetime) -> tuple[dict[str, Any] | None, str]:
        tournaments, index_error = self._get_tournaments(fixture["game"])
        if index_error:
            return None, index_error
        matches = _matching_tournaments(fixture, tournaments)
        if len(matches) != 1:
            if not matches:
                return None, "No Thunderpick tournament page with an exact competition-title match was found."
            return None, "More than one Thunderpick tournament page matched the exact competition title."

        tournament = matches[0]
        try:
            tournament_html = self._get_html(tournament["url"])
        except requests.RequestException as exc:
            return None, f"Thunderpick tournament page request failed: {exc}"
        details = _match_links(tournament_html, tournament["url"], fixture)
        if not details:
            return None, "No direct Thunderpick match page with the exact team pair was found in this tournament."

        quoted: list[dict[str, Any]] = []
        reasons: list[str] = []
        for detail_url in details:
            try:
                detail_html = self._get_html(detail_url)
            except requests.RequestException as exc:
                reasons.append(f"Thunderpick match page request failed: {exc}")
                continue
            quote_data, reason = parse_thunderpick_match_winner(
                detail_html,
                fixture,
                detail_url,
                tournament["url"],
                retrieved_at,
            )
            if quote_data:
                quoted.append(quote_data)
            else:
                reasons.append(reason)
        if len(quoted) == 1:
            return quoted[0], "verified"
        if len(quoted) > 1:
            return None, "More than one exact-date Thunderpick Match Winner page matched; bookmaker quote left blank."
        return None, reasons[0] if reasons else "No two-sided exact-match Thunderpick quote could be verified."
