"""Read only fixture-specific state in public Hotspawn Angular SSR pages.

Never retain leaderboard/account transfer-cache entries or crowd pick values.
The retained projection documents this privacy filter explicitly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
import re

from collector.analytics import iso_time

FIXTURE_FIELDS = (
    "id", "competition_id", "competition_name", "sport_alias", "sport_name",
    "status", "scheduled_start_time", "lock_time", "lock_offset_sec",
    "best_of", "series_format", "tier", "stage", "start_time", "end_time",
    "participants0_id", "participants0_name", "participants1_id", "participants1_name",
)


class TransferState(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.recording = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "ng-state":
            self.recording = True

    def handle_data(self, data):
        if self.recording:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.recording = False


def epoch_ms(value: object) -> str | None:
    # Units are explicit in the observed frontend implementation, not inferred
    # from a locale-rendered wall-clock label or countdown.
    if isinstance(value, bool) or not re.fullmatch(r"\d{13}", str(value or "")):
        return None
    try:
        return iso_time(datetime.fromtimestamp(int(value) / 1000, timezone.utc))
    except (ValueError, OverflowError, OSError):
        return None


def project_page(body: bytes, url: str) -> dict:
    html = body.decode("utf-8")
    parser = TransferState()
    parser.feed(html)
    if not parser.parts:
        raise ValueError("Official page has no recognizable Angular fixture transfer state")
    state = json.loads("".join(parser.parts))
    cache = {}
    permalinks = {}
    for key, entry in state.items():
        if not isinstance(entry, dict) or entry.get("s") != 200:
            continue
        endpoint = entry.get("u", "")
        data = entry.get("b")
        if endpoint.endswith("/api/v1/fixtures") and isinstance(data, list):
            records = []
            for record in data:
                if not isinstance(record, dict) or "participants0_name" not in record:
                    continue
                records.append({field: record.get(field) for field in FIXTURE_FIELDS})
            cache[key] = {"url": endpoint, "status": 200, "body": records}
        elif endpoint.endswith("/fixtures/permalinks") and isinstance(data, dict):
            for fixture_id, link in data.get("permalinks", {}).items():
                if isinstance(link, str) and link.startswith("https://www.hotspawn.com/matches/"):
                    permalinks[str(fixture_id)] = link
    if not cache:
        raise ValueError("No successful fixture cache in official page")

    cards = []
    for found in re.finditer(r"<app-pickem-vs-card\b[^>]*>(.*?)</app-pickem-vs-card>", html, re.S):
        chunk = found.group(1)
        link = re.search(r'href="(https://www\.hotspawn\.com/matches/[^"#]+?-(\d{5,12}))"', chunk)
        teams = re.findall(r'class="vs-card-team-name">\s*([^<]+?)\s*</div>', chunk)
        tournament = re.search(r'class="vs-card-tournament">\s*([^<]+?)\s*</div>', chunk)
        if not link:
            continue
        section = None
        for heading in re.finditer(r'<h2\b[^>]*>\s*([^<]+?)\s*</h2>', html[:found.start()]):
            label = unescape(heading.group(1)).strip()
            if label in {"Closing Soon", "Upcoming", "Live"}:
                section = label
        cards.append({
            "id": link.group(2), "source_url": unescape(link.group(1)),
            "team_a": unescape(teams[0]).strip() if len(teams) > 0 else None,
            "team_b": unescape(teams[1]).strip() if len(teams) > 1 else None,
            "tournament": unescape(tournament.group(1)).strip() if tournament else None,
            "section": section,
        })
    filter_totals = sorted({int(value) for value in re.findall(r'All (?:tiers|tournaments|teams)\s*\((\d+)\)', html)})
    return {
        "kind": "hotspawn_fixture_transfer_state", "source_url": url,
        "source_response_sha256": sha256(body).hexdigest(),
        "privacy_filter": "Only fixture cache, official fixture permalinks and rendered card identity. Account/leaderboard data, scores and crowd picks discarded.",
        "cache": cache, "permalinks": permalinks, "rendered_cards": cards,
        "filter_totals": filter_totals,
    }


def normalize_record(record: dict, source_url: str, evidence_id: str, locator: str, card: dict | None = None) -> dict:
    fixture_id = str(record["id"])
    return {
        "id": fixture_id,
        "game": record.get("sport_alias") if record.get("sport_alias") in {"cs2", "lol"} else None,
        "team_a": record.get("participants0_name") if isinstance(record.get("participants0_name"), str) and record["participants0_name"].strip() else None,
        "team_b": record.get("participants1_name") if isinstance(record.get("participants1_name"), str) and record["participants1_name"].strip() else None,
        "team_a_id": record.get("participants0_id"), "team_b_id": record.get("participants1_id"),
        "tournament": record.get("competition_name"), "competition_id": record.get("competition_id"),
        "start_time": epoch_ms(record.get("scheduled_start_time")),
        "lock_time": epoch_ms(record.get("lock_time")),
        "lock_offset_seconds": record.get("lock_offset_sec"),
        "best_of": record.get("best_of"), "series_format": record.get("series_format"),
        "tier": record.get("tier"), "stage": record.get("stage"),
        "source_status": record.get("status"),
        "source_url": card["source_url"] if card else source_url,
        "lobby_url": source_url,
        "on_rendered_board": card is not None,
        "lobby_section": card.get("section") if card else None,
        "evidence_id": evidence_id, "evidence_locator": locator,
        "source_pages": [source_url],
        "status": "source_confirmed",
    }


def extract_records(projection: dict, evidence_id: str) -> tuple[list[dict], list[dict], dict]:
    cards = {card["id"]: card for card in projection["rendered_cards"]}
    inventory: dict[str, dict] = {}
    for key, entry in projection["cache"].items():
        for index, record in enumerate(entry["body"]):
            if record.get("sport_alias") not in {"cs2", "lol"} or not re.fullmatch(r"\d{5,12}", str(record.get("id", ""))):
                continue
            normalized = normalize_record(record, projection["source_url"], evidence_id, f"/cache/{key}/body/{index}", cards.get(str(record["id"])))
            if not normalized["on_rendered_board"]:
                normalized["source_url"] = projection["permalinks"].get(str(record["id"]), projection["source_url"])
            inventory[normalized["id"]] = normalized
    board = []
    unparsed = []
    card_conflicts = []
    for card_id, card in cards.items():
        record = inventory.get(card_id)
        if record is None:
            unparsed.append(card_id)
            continue
        # Verbatim DOM identity and underlying source state must agree.
        if any(card.get(key) is not None and record.get(key) is not None and card[key] != record[key] for key in ("team_a", "team_b", "tournament")):
            card_conflicts.append(card_id)
            continue
        board.append(record)
    info = {
        "source_url": projection["source_url"], "rendered_card_count": len(cards),
        "parsed_board_count": len(board), "cached_record_count": len(inventory),
        "filter_totals": projection["filter_totals"],
        "unparsed_card_ids": unparsed, "conflicting_card_ids": card_conflicts,
    }
    return board, list(inventory.values()), info
