#!/usr/bin/env python3
"""Check every normalized record, its evidence, calculations and internal links."""
from __future__ import annotations

import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.analytics import analyze_match, parse_time, valid_decimal

REPO_URL = "https://github.com/buffedlizard55-lab/MaltaProj1"
FIXTURE_HOSTS = {"play.hotspawn.com", "www.hotspawn.com"}
BOOKMAKER_HOSTS = {"thunderpick.io", "www.pinnacle.com", "www.rivalry.com", "gg.bet", "www.bwin.com", "sports.bwin.com"}


class ValidationError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def source_url(url: str | None) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password and not re.search(r"(?:token|secret|password|api[_-]?key)=", parsed.query, re.I)


def close(actual: object, expected: object, label: str) -> None:
    if expected is None:
        require(actual is None, f"{label}: unverified value must be null")
    elif isinstance(expected, float):
        require(isinstance(actual, (int, float)) and not isinstance(actual, bool) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10), f"{label}: calculation mismatch")
    else:
        require(actual == expected, f"{label}: value mismatch")


def validate_data(data: dict, evidence_dir: Path | None = None) -> dict:
    require(data.get("schema_version") == 1, "Unknown snapshot schema")
    now = parse_time(data.get("generated_at"))
    require(now is not None, "generated_at requires an explicit timezone")
    matches, quotes = data.get("matches"), data.get("quotes")
    require(isinstance(matches, list) and isinstance(quotes, list), "Match and quote arrays required")
    require(len({match.get("id") for match in matches}) == len(matches), "Duplicate match IDs")
    require(len({quote.get("id") for quote in quotes}) == len(quotes), "Duplicate quote IDs")
    evidence = {entry["id"]: entry for entry in data.get("evidence", [])}
    require(len(evidence) == len(data.get("evidence", [])), "Duplicate evidence IDs")
    if evidence_dir is not None:
        for entry in evidence.values():
            require(source_url(entry.get("url")), f"{entry['id']}: invalid evidence URL")
            require(parse_time(entry.get("retrieved_at")) is not None, f"{entry['id']}: unverified retrieval time")
            require(entry.get("http_status") == 200, f"{entry['id']}: non-200 response cannot substantiate values")
            filename = entry.get("file")
            require(isinstance(filename, str) and Path(filename).name == filename, f"{entry['id']}: unsafe evidence filename")
            path = evidence_dir / filename
            require(path.is_file(), f"Missing evidence file: {path}")
            body = path.read_bytes()
            if path.suffix == ".gz":
                body = gzip.decompress(body)
            require(hashlib.sha256(body).hexdigest() == entry.get("sha256"), f"{entry['id']}: source content hash mismatch")

    sources = {entry["id"]: entry for entry in data.get("sources", [])}
    for source in sources.values():
        require(source_url(source.get("url")), f"{source['id']}: official source link missing")
    for quote in quotes:
        label = quote.get("id") or "quote without ID"
        require(quote.get("evidence_id") in evidence, f"{label}: source evidence missing")
        require(quote.get("source_id") in sources, f"{label}: source not registered")
        require(quote.get("source_role") == "primary_bookmaker", f"{label}: not primary-bookmaker evidence")
        require(source_url(quote.get("source_url")) and urlparse(quote["source_url"]).hostname in BOOKMAKER_HOSTS, f"{label}: official bookmaker event link required")
        require(valid_decimal(quote.get("odds_a")) and valid_decimal(quote.get("odds_b")), f"{label}: invalid or missing two-sided prices")
        require(quote.get("outcome_count") == 2 and quote.get("period") == "match" and quote.get("market_type") == "match_winner", f"{label}: wrong market semantics")
        require(quote.get("status") == "open" and quote.get("is_live") is False, f"{label}: closed/live market")
        require(parse_time(quote.get("observed_at")) is not None and parse_time(quote.get("start_time")) is not None, f"{label}: timestamp unverified")
        require(quote.get("team_a") and quote.get("team_b") and quote["team_a"] != quote["team_b"], f"{label}: two named outcomes required")
        require(quote.get("evidence_locator"), f"{label}: precise source locator required")
        require("picked_percent_a" not in quote and "hotspawn_probability" not in quote, f"{label}: forbidden probability input")

    priced = 0
    for match in matches:
        label = match.get("id") or "match without ID"
        require(match.get("game") in {"cs2", "lol"}, f"{label}: unsupported/unverified game")
        require(source_url(match.get("source_url")) and urlparse(match["source_url"]).hostname in FIXTURE_HOSTS, f"{label}: official fixture link required")
        require(match.get("evidence_id") in evidence, f"{label}: fixture evidence missing")
        require(match.get("evidence_locator"), f"{label}: precise source locator required")
        require("picked_percent_a" not in match and "hotspawn_probability" not in match, f"{label}: crowd percentage imported")
        require(all(match.get(field) is None or isinstance(match.get(field), str) and bool(match[field].strip()) for field in ("team_a", "team_b")), f"{label}: unconfirmed names must be null, not inferred")
        if match.get("start_time") is not None:
            require(parse_time(match["start_time"]) is not None, f"{label}: inferred/unzoned start time")
        expected = analyze_match(match, quotes, now)
        actual = match.get("analysis")
        require(isinstance(actual, dict), f"{label}: analysis object required")
        for key, value in expected.items():
            if key == "inputs":
                require(len(actual.get(key, [])) == len(value), f"{label}: input count mismatch")
                for ai, ei in zip(actual[key], value):
                    for field, expected_value in ei.items():
                        close(ai.get(field), expected_value, f"{label}/{field}")
            else:
                close(actual.get(key), value, f"{label}/{key}")
        if actual["status"] == "calculated":
            priced += 1
            require(match.get("start_time") is not None, f"{label}: missing start time must leave probability blank")
            require(math.isclose(actual["probability_a"] + actual["probability_b"], 1, abs_tol=1e-12), f"{label}: probabilities do not sum to 1")
    inventory = data.get("inventory", [])
    require(isinstance(inventory, list) and len({row.get("id") for row in inventory}) == len(inventory), "Duplicate/malformed source-inventory rows")
    for row in inventory:
        require(row.get("evidence_id") in evidence and row.get("evidence_locator"), f"{row.get('id')}: source-inventory evidence missing")
        require(source_url(row.get("source_url")) and urlparse(row["source_url"]).hostname in FIXTURE_HOSTS, f"{row.get('id')}: official source-inventory URL missing")
    findings = data.get("findings", [])
    for finding in findings:
        require(finding.get("source_urls"), f"{finding.get('id')}: finding has no review source")
        require(all(source_url(source.get("url")) for source in finding["source_urls"]), f"{finding.get('id')}: invalid review source")
    coverage = data.get("coverage", {})
    require(coverage.get("status") in {"complete", "partial", "unavailable", "unverified"}, "Unknown inventory state")
    if coverage.get("status") == "complete":
        checks = coverage.get("checks", [])
        require(checks and all(check.get("passed") is True for check in checks), "Complete-list claim lacks positive reconciliation checks")
    # Reparse the retained primary responses rather than trusting normalized rows.
    if evidence_dir is not None:
        from collector.verification import verify_source_records
        verify_source_records(data, evidence_dir)
    return {"match_count": len(matches), "quote_count": len(quotes), "priced_count": priced, "unpriced_count": len(matches) - priced, "inventory_count": len(inventory), "evidence_count": len(evidence), "finding_count": len(findings)}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []
        self.ids: set[str] = set()
        self.titles = 0
        self.h1 = 0
        self.rows_without_source = 0
        self.in_row = False
        self.in_head = False
        self.row_has_official = False
        self.row_has_cell = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "title":
            self.titles += 1
        if tag == "h1":
            self.h1 += 1
        if tag == "thead":
            self.in_head = True
        if tag == "tr" and not self.in_head:
            self.in_row = True
            self.row_has_official = False
            self.row_has_cell = False
        if tag == "td" and self.in_row:
            self.row_has_cell = True
        for attr in ("href", "src"):
            if attrs.get(attr):
                url = attrs[attr]
                self.links.append(url)
                if self.in_row and source_url(url):
                    self.row_has_official = True

    def handle_endtag(self, tag):
        if tag == "thead":
            self.in_head = False
        if tag == "tr" and self.in_row:
            if self.row_has_cell and not self.row_has_official:
                self.rows_without_source += 1
            self.in_row = False


def validate_site(output: Path) -> dict:
    parsed: dict[Path, Links] = {}
    for file in output.rglob("*.html"):
        doc = Links()
        doc.feed(file.read_text())
        require(doc.titles == 1 and doc.h1 == 1, f"{file}: one title and h1 required")
        require(doc.rows_without_source == 0, f"{file}: a data row lacks an official external source link")
        parsed[file.resolve()] = doc
    checked = 0
    for file, doc in parsed.items():
        for url in doc.links:
            link = urlparse(url)
            if link.scheme or link.netloc:
                require(link.scheme == "https", f"{file}: insecure external URL {url}")
                continue
            target = (file.parent / unquote(link.path)).resolve() if link.path else file
            if target.is_dir():
                target /= "index.html"
            require(target.is_file(), f"{file}: broken internal link {url}")
            if link.fragment and target in parsed:
                require(unquote(link.fragment) in parsed[target].ids, f"{file}: missing anchor {url}")
            checked += 1
    for file in output.rglob("*.css"):
        for url in re.findall(r'url\([\"\']?([^\"\')]+)', file.read_text()):
            if url.startswith("data:"):
                continue
            parsed_url = urlparse(url)
            require(not parsed_url.scheme and not parsed_url.netloc, f"{file}: unexpected remote asset")
            require((file.parent / url).is_file(), f"{file}: missing CSS asset {url}")
    require(len(parsed) >= 9, "Dashboard category/subpages missing")
    return {"pages": len(parsed), "internal_links_checked": checked, "rows_without_official_source": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/snapshot/latest.json")
    parser.add_argument("--site", type=Path, default=ROOT / "dashboard")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    counts = validate_data(data, args.data.parent / "evidence")
    links = validate_site(args.site)
    print(json.dumps({"data": counts, "site": links}, indent=2))
