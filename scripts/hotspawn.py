"""Read-only parser for Hotspawn's public Pick'ems fixture listings.

The parser intentionally extracts fixture metadata and official links only. It
never reads or stores Pick'em picks, crowd shares, percentages, streaks, or
other player-selection data.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

HOTSPAWN_BASE = "https://play.hotspawn.com"
GAME_PAGES = {
    "CS2": f"{HOTSPAWN_BASE}/cs2-pickems",
    "LoL": f"{HOTSPAWN_BASE}/lol-pickems",
}
MONTH = r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
DATE_RE = re.compile(rf"\b(?:{MONTH})\s+\d{{1,2}},\s*\d{{1,2}}:\d{{2}}\b", re.IGNORECASE)
MATCH_PATH_RE = re.compile(r"^/matches/[^/?#]+", re.IGNORECASE)
TEAM_IMAGE_RE = re.compile(r"/teams/[^/?#]+\.(?:svg|png|webp)(?:\?|$)", re.IGNORECASE)


def _text(node: Tag) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def _team_names(card: Tag) -> list[str]:
    names: list[str] = []
    for image in card.find_all("img"):
        source = image.get("src") or image.get("data-src") or ""
        alt = re.sub(r"\s+", " ", str(image.get("alt") or "")).strip()
        if not alt or not TEAM_IMAGE_RE.search(source):
            continue
        if alt.casefold() not in {name.casefold() for name in names}:
            names.append(alt)
    return names


def _fixture_card(anchor: Tag) -> Tag | None:
    """Find the nearest ancestor that looks like one match card."""

    for ancestor in anchor.parents:
        if not isinstance(ancestor, Tag) or ancestor.name in {"body", "html", "[document]"}:
            break
        text = _text(ancestor)
        names = _team_names(ancestor)
        if DATE_RE.search(text) and len(names) == 2 and "who will win" in text.casefold():
            return ancestor
    # Be tolerant of markup changes where the prompt text is hidden, while
    # still requiring a unique date and exactly two team-logo labels.
    for ancestor in anchor.parents:
        if not isinstance(ancestor, Tag) or ancestor.name in {"body", "html", "[document]"}:
            break
        text = _text(ancestor)
        if DATE_RE.search(text) and len(_team_names(ancestor)) == 2:
            return ancestor
    return None


def _tournament_from_card(card_text: str, date_match: re.Match[str]) -> str:
    after = card_text[date_match.end() :]
    before_meta = re.split(
        r"\b(?:Points\s+available|Sign\s+in\s+for\s+streaks|Locks\s+in|Locking\s+soon|View\s+Match|Who\s+will\s+win)\b",
        after,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return re.sub(r"\s+", " ", before_meta).strip(" \t\n·|—-")


def parse_hotspawn_listing(html: str, game: str, page_url: str | None = None) -> dict[str, Any]:
    """Parse one rendered Pick'ems listing into safe fixture-only records."""

    if game not in GAME_PAGES:
        raise ValueError(f"Unsupported Hotspawn game page: {game}")
    page_url = page_url or GAME_PAGES[game]
    soup = BeautifulSoup(html, "html.parser")
    page_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    total_match = re.search(r"(\d+)\s*matches\s+this\s+week", page_text, re.IGNORECASE)
    stated_matches = int(total_match.group(1)) if total_match else None

    fixtures: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    unparsed_links: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, str(anchor.get("href", "")).strip())
        parsed = urlparse(href)
        if parsed.netloc.casefold() not in {"www.hotspawn.com", "hotspawn.com"}:
            continue
        if not MATCH_PATH_RE.match(parsed.path):
            continue
        official_url = f"https://www.hotspawn.com{parsed.path}"
        if official_url in seen_urls:
            continue
        seen_urls.add(official_url)

        card = _fixture_card(anchor)
        if card is None:
            unparsed_links.append(official_url)
            continue
        card_text = _text(card)
        date_match = DATE_RE.search(card_text)
        teams = _team_names(card)
        if not date_match or len(teams) != 2:
            unparsed_links.append(official_url)
            continue

        slug = parsed.path.rstrip("/").rsplit("/", 1)[-1]
        id_match = re.search(r"(\d+)$", slug)
        fixture_id = f"hotspawn-{id_match.group(1)}" if id_match else f"hotspawn-{slug}"
        fixtures.append(
            {
                "id": fixture_id,
                "game": game,
                "tournament": _tournament_from_card(card_text, date_match),
                "teamA": teams[0],
                "teamB": teams[1],
                "hotspawnTimeLabel": date_match.group(0),
                # The lobby clock has no timezone label; do not manufacture UTC.
                "startAtUtc": None,
                "fixtureUrl": official_url,
            }
        )

    return {
        "game": game,
        "pageUrl": page_url,
        "statedMatchesThisWeek": stated_matches,
        "discoveredMatchLinks": len(seen_urls),
        "parsedFixtures": fixtures,
        "unparsedMatchLinks": unparsed_links,
        "coverageComplete": (
            stated_matches is not None
            and len(fixtures) == stated_matches
            and not unparsed_links
        ),
    }
