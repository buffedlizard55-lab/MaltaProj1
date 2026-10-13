"""Recheck normalized fields against retained, privacy-minimized primary evidence."""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

from collector.analytics import parse_time
from collector.hotspawn import normalize_record
from collector.pinnacle import normalize_quotes


def load_body(path: Path) -> object:
    body = path.read_bytes()
    if path.suffix == ".gz":
        body = gzip.decompress(body)
    return json.loads(body)


def pointer(body: object, locator: str) -> object:
    current = body
    for key in locator.split("/")[1:]:
        key = key.replace("~1", "/").replace("~0", "~")
        current = current[int(key)] if isinstance(current, list) else current[key]
    return current


def equal(a: object, b: object) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
    return a == b


def verify_source_records(data: dict, evidence_dir: Path) -> None:
    evidence = {entry["id"]: entry for entry in data.get("evidence", [])}
    bodies = {key: load_body(evidence_dir / entry["file"]) for key, entry in evidence.items()}
    fields = (
        "id", "game", "team_a", "team_b", "team_a_id", "team_b_id", "tournament",
        "competition_id", "start_time", "lock_time", "lock_offset_seconds",
        "best_of", "series_format", "tier", "stage", "source_status", "source_url",
        "lobby_url", "on_rendered_board", "lobby_section",
    )
    for row in data.get("matches", []) + data.get("inventory", []):
        entry = evidence[row["evidence_id"]]
        projection = bodies[row["evidence_id"]]
        if entry.get("kind") != "hotspawn_fixture_transfer_state" or projection.get("source_url") != row["lobby_url"]:
            raise ValueError(f"{row['id']}: fixture origin mismatch")
        raw = pointer(projection, row["evidence_locator"])
        card = next((card for card in projection["rendered_cards"] if card["id"] == row["id"]), None) if row["on_rendered_board"] else None
        expected = normalize_record(raw, row["lobby_url"], row["evidence_id"], row["evidence_locator"], card)
        if not expected["on_rendered_board"]:
            expected["source_url"] = projection["permalinks"].get(row["id"], projection["source_url"])
        for field in fields:
            if not equal(row.get(field), expected.get(field)):
                raise ValueError(f"{row['id']}/{field}: does not match the retained official fixture field")
        if row["on_rendered_board"] and card is None:
            raise ValueError(f"{row['id']}: claimed board entry not in official rendered cards")

    packets = []
    links = []
    for key, entry in evidence.items():
        if entry.get("source_id") == "pinnacle" and entry.get("kind") in {"pinnacle_matchups", "pinnacle_markets"}:
            packets.append({
                "url": entry["url"], "retrieved_at": entry["retrieved_at"], "capture_sequence": entry.get("capture_sequence", 0),
                "observed_in": entry.get("observed_in"), "evidence_id": key, "body": bodies[key],
            })
        if entry.get("kind") == "pinnacle_observed_links":
            links.extend(bodies[key].get("links", []))
    quotes, _ = normalize_quotes(packets, links, parse_time(data["generated_at"]))
    expected_quotes = {quote["id"]: quote for quote in quotes}
    quote_fields = (
        "source_id", "source_role", "event_id", "game", "team_a", "team_b", "tournament",
        "start_time", "best_of", "market_type", "period", "outcome_count", "status", "is_live",
        "native_format", "native_odds_a", "native_odds_b", "odds_a", "odds_b", "observed_at",
        "source_published_at", "capture_sequence", "source_url", "api_url", "evidence_id", "evidence_locator",
        "event_evidence_id", "event_evidence_locator",
    )
    if len(expected_quotes) != len(data.get("quotes", [])):
        raise ValueError("The published quotes do not cover exactly the eligible retained primary inputs")
    for quote in data.get("quotes", []):
        expected = expected_quotes.get(quote["id"])
        if expected is None:
            raise ValueError(f"{quote['id']}: no qualifying primary-bookmaker evidence")
        for field in quote_fields:
            if not equal(quote.get(field), expected.get(field)):
                raise ValueError(f"{quote['id']}/{field}: does not match primary-bookmaker evidence")
