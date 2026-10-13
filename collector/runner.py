"""Autonomous, evidence-first public collection. Execute live on Actions runners."""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from collector.analytics import analyze_match, iso_time, normalized_name, parse_time
from collector.hotspawn import extract_records, project_page
from collector.pinnacle import PUBLIC_PAGES, normalize_quotes, relevant_response

REPO = "https://github.com/buffedlizard55-lab/MaltaProj1"
USER_AGENT = "MaltaProj1-evidence-collector/1.0 (+https://github.com/buffedlizard55-lab/MaltaProj1)"
LOBBIES = (
    "https://play.hotspawn.com/lobby",
    "https://play.hotspawn.com/cs2-pickems",
    "https://play.hotspawn.com/lol-pickems",
    "https://play.hotspawn.com/thp-pickems",
)
RULES_URL = "https://play.hotspawn.com/how-it-works"
PINC_POLICY = "https://github.com/pinnacleapi/pinnacleapi-documentation"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_public(url: str) -> tuple[int, bytes, str]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"})
    try:
        with urlopen(request, timeout=35) as response:
            body = response.read(12_000_001)
            if len(body) > 12_000_000:
                raise ValueError("Public response exceeded the bounded collection size")
            return response.status, body, response.url
    except HTTPError as error:
        return error.code, b"", error.url


class Ledger:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, dict] = {}

    def store(self, body: bytes, url: str, at: str, source_id: str, kind: str, description: str, observed_in: str | None = None, source_response_sha256: str | None = None) -> dict:
        digest = hashlib.sha256(body).hexdigest()
        identifier = f"{kind}-{digest[:16]}-{hashlib.sha256(url.encode()).hexdigest()[:6]}"
        filename = identifier + ".json.gz"
        (self.folder / filename).write_bytes(gzip.compress(body, mtime=0))
        metadata = {
            "id": identifier, "source_id": source_id, "kind": kind, "file": filename,
            "url": url, "retrieved_at": at, "http_status": 200, "sha256": digest,
            "description": description, "observed_in": observed_in,
        }
        if source_response_sha256:
            metadata["source_response_sha256"] = source_response_sha256
        self.entries[identifier] = metadata
        return metadata

    def json(self, value: object, **kwargs) -> dict:
        return self.store(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode(), **kwargs)


def source_record(identifier: str, name: str, url: str, role: str, usage: str) -> dict:
    return {"id": identifier, "name": name, "url": url, "role_label": role, "usage": usage, "status": "unverified", "http_status": None, "observed_at": None}


def finding(identifier: str, category: str, title: str, detail: str, urls: list[tuple[str, str]]) -> dict:
    return {"id": identifier, "category": category, "severity": "unverified", "title": title, "detail": detail, "source_urls": [{"url": url, "label": label} for url, label in urls]}


async def collect_pinnacle(ledger: Ledger) -> tuple[list[dict], list[str], list[dict]]:
    from playwright.async_api import async_playwright
    packets: list[dict] = []
    links: list[str] = []
    page_checks: list[dict] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(timezone_id="UTC", viewport={"width": 1440, "height": 1000})
        for target in PUBLIC_PAGES:
            page = await context.new_page()
            pending: list = []

            async def capture(response):
                if not relevant_response(response.url) or response.request.method != "GET" or response.status != 200:
                    return
                try:
                    body = await response.body()
                    if len(body) > 8_000_000:
                        return
                    data = json.loads(body)
                    if not isinstance(data, list):
                        return
                    # Explicit endpoint allowlist. Do not retain accounts, keys,
                    # sessions, KYC, wallets, or unrelated personal fields.
                    if re.search(r'"(?:email|password|accessToken|userId)"\s*:', body.decode("utf-8"), re.I):
                        return
                    at = iso_time(utc_now())
                    kind = "pinnacle_matchups" if "/matchups" in response.url else "pinnacle_markets"
                    entry = ledger.store(body, response.url, at, "pinnacle", kind, "Unchanged public website event/market JSON, observed in a normal unauthenticated browser.", observed_in=target)
                    packets.append({"url": response.url, "retrieved_at": at, "observed_in": target, "evidence_id": entry["id"], "body": data})
                except (ValueError, RuntimeError):
                    return

            page.on("response", lambda response: pending.append(asyncio.create_task(capture(response))))
            check = {"url": target, "status": None, "observed_at": None}
            try:
                response = await page.goto(target, wait_until="domcontentloaded", timeout=60_000)
                check["status"] = response.status if response else None
                check["observed_at"] = iso_time(utc_now())
                if response and response.status == 200:
                    # Wait for the site's ordinary price requests, not an evasion tool.
                    await page.wait_for_timeout(10_000)
                    observed = await page.locator('a[href]').evaluate_all("nodes => nodes.map(node => node.href)")
                    selected = sorted({link for link in observed if urlparse(link).hostname == "www.pinnacle.com" and "/en/esports/" in urlparse(link).path})
                    links.extend(selected)
                    ledger.json({"kind": "pinnacle_observed_links", "source_url": page.url, "links": selected}, url=page.url, at=iso_time(utc_now()), source_id="pinnacle", kind="pinnacle_observed_links", description="Only actual esports hyperlinks extracted from the public DOM; no deep links invented.")
                else:
                    check["error"] = "Public website did not return HTTP 200; no challenge bypass attempted."
            except Exception as error:
                check["error"] = type(error).__name__
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
            await page.close()
            page_checks.append(check)
        await context.close()
        await browser.close()
    return packets, sorted(set(links)), page_checks


def collect(output: Path) -> dict:
    ledger = Ledger(output.parent / "evidence")
    started = iso_time(utc_now())
    sources = [
        source_record("hotspawn", "Hotspawn Play", LOBBIES[0], "Primary · eligibility only", "Official board identities, source-state inventory, schedules and lock metadata. Never a probability signal."),
        source_record("pinnacle", "Pinnacle", PUBLIC_PAGES[0], "Primary · outside bookmaker", "Public website whole-match moneyline markets, including the observed guest responses. Not the closed licensed API."),
        source_record("thunderpick", "Thunderpick", "https://thunderpick.io/esports/cs2-betting", "Primary · outside bookmaker", "Access checked without login or bypass. No unsupported quotes are substituted when inaccessible."),
        source_record("hltv", "HLTV", "https://www.hltv.org/matches", "Secondary · reference only", "Access checked for context; ranks and community pick indicators never populate this market-based analysis."),
        source_record("hotspawn-rules", "Hotspawn rules", RULES_URL, "Official · policy", "Compare the published lock-time rule with the explicit fixture metadata. Never derive UTC start times from countdowns."),
        source_record("pinnacle-api-policy", "Pinnacle API policy", PINC_POLICY, "Official · API policy", "Read the publisher's current licensed-API access statement. The collector uses only public website responses."),
    ]
    sources[1]["policy_url"] = PINC_POLICY
    source_map = {source["id"]: source for source in sources}
    board: dict[str, dict] = {}
    inventory: dict[str, dict] = {}
    page_info = []
    findings = []
    policy_seconds = None

    for url in LOBBIES:
        info = {"source_url": url, "http_status": None, "parsed_board_count": 0, "cached_record_count": 0, "observed_at": None}
        try:
            status, body, final = get_public(url)
            at = iso_time(utc_now())
            info.update(http_status=status, observed_at=at)
            if status != 200 or urlparse(final).hostname != "play.hotspawn.com":
                raise ValueError(f"Official lobby retrieval HTTP {status}")
            projection = project_page(body, url)
            entry = ledger.json(projection, url=url, at=at, source_id="hotspawn", kind="hotspawn_fixture_transfer_state", description="Fixture-only Angular SSR transfer-state projection; source fields unchanged, unrelated personal/crowd fields excluded.", source_response_sha256=projection["source_response_sha256"])
            rows, all_rows, details = extract_records(projection, entry["id"])
            info.update(details)
            for target, records in ((inventory, all_rows), (board, rows)):
                for row in records:
                    row["lobby_current"] = True
                    row["observed_at"] = at
                    existing = target.get(row["id"])
                    if existing:
                        previous_pages = existing.get("source_pages", [])
                        # Keep the latest successful source observation; record any
                        # changed identity/schedule as a review finding, not an inference.
                        different = [field for field in ("team_a", "team_b", "start_time", "game", "tournament") if existing.get(field) != row.get(field)]
                        if different:
                            findings.append(finding(f"F-CHANGE-{row['id']}", "Source changed", "Official observations differ", f"Fixture {row['id']} changed fields between official page retrievals: {', '.join(different)}. The later response is retained; both observations remain in the evidence ledger.", [(url, "Later official page"), (existing["lobby_url"], "Earlier official page")]))
                        row["source_pages"] = sorted(set(previous_pages + row["source_pages"]))
                    target[row["id"]] = row
            source_map["hotspawn"].update(status="observed", http_status=200, observed_at=at)
        except Exception as error:
            info["error"] = f"{type(error).__name__}: {error}"
            findings.append(finding(f"F-LOBBY-{len(page_info)+1}", "Source access", "Official lobby could not be confirmed", info["error"] + ". No fixtures or values are invented for this page.", [(url, "Official lobby")]))
        page_info.append(info)
        print(json.dumps({"source": url, "http_status": info["http_status"], "board_rows": info["parsed_board_count"], "state_rows": info["cached_record_count"], "error": info.get("error")}), flush=True)

    try:
        status, body, _ = get_public(RULES_URL)
        at = iso_time(utc_now())
        source_map["hotspawn-rules"].update(http_status=status, observed_at=at)
        text = " ".join(re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace")).split())
        excerpt = re.search(r"(?:Your picks|Picks) lock (\d+) minutes before the scheduled start time[^.]*\.", text, re.I)
        if status == 200 and excerpt:
            policy_seconds = int(excerpt.group(1)) * 60
            source_map["hotspawn-rules"]["status"] = "observed"
            ledger.json({"kind": "official_policy_excerpt", "source_url": RULES_URL, "text": excerpt.group(0)}, url=RULES_URL, at=at, source_id="hotspawn-rules", kind="official_policy_excerpt", description="Only the official lock-rule sentence retained; unrelated page state discarded.", source_response_sha256=hashlib.sha256(body).hexdigest())
    except Exception:
        pass

    packets, event_links, bookmaker_checks = [], [], []
    try:
        packets, event_links, bookmaker_checks = asyncio.run(collect_pinnacle(ledger))
    except Exception as error:
        findings.append(finding("F-PINNACLE-BROWSER", "Source access", "Public bookmaker browser collection failed", type(error).__name__ + ": no alternative credentials, bypass, or fabricated odds used.", [(PUBLIC_PAGES[0], "Official bookmaker")]))
    if packets:
        source_map["pinnacle"].update(status="observed", http_status=200, observed_at=max(packet["retrieved_at"] for packet in packets), api_url="https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/highlighted")
    for check in bookmaker_checks:
        if check.get("status") != 200 or check.get("error"):
            findings.append(finding(f"F-PINNACLE-PAGE-{len(findings)+1}", "Source access", "A bookmaker category could not be confirmed", f"HTTP {check.get('status')}; {check.get('error', '')}. This category is not assumed complete.", [(check["url"], "Official bookmaker page")]))

    for identifier in ("thunderpick", "hltv"):
        source = source_map[identifier]
        try:
            status, _, _ = get_public(source["url"])
            source.update(http_status=status, observed_at=iso_time(utc_now()))
            # A status alone is not odds verification. No quote parser is claimed.
            if status == 200:
                source["usage"] += " HTTP 200 observed, but no independently validated quote adapter is published for this origin."
            findings.append(finding(f"F-ACCESS-{identifier.upper()}", "Source limitation", f"{source['name']} is not an eligible odds input in this run", f"HTTP {status}. Source prices are not confirmed by this adapter; no result is substituted. A successful response alone does not verify a betting line.", [(source["url"], "Official source")]))
        except Exception as error:
            findings.append(finding(f"F-ACCESS-{identifier.upper()}", "Source limitation", f"{source['name']} could not be confirmed", type(error).__name__ + ". No access challenge or authentication restriction is bypassed.", [(source["url"], "Official source")]))

    policy_api = "https://api.github.com/repos/pinnacleapi/pinnacleapi-documentation/contents/README.md"
    licensed_excerpt = None
    try:
        status, body, _ = get_public(policy_api)
        at = iso_time(utc_now())
        source_map["pinnacle-api-policy"].update(http_status=status, observed_at=at, api_url=policy_api)
        if status == 200:
            payload = json.loads(body)
            readme = base64.b64decode(payload["content"]).decode("utf-8")
            match = re.search(r"Access to Pinnacle API suite has been closed for the general public since [^.]+\.", readme)
            if match:
                licensed_excerpt = match.group(0)
                source_map["pinnacle-api-policy"]["status"] = "observed"
                ledger.json({"kind": "official_policy_excerpt", "source_url": PINC_POLICY, "text": licensed_excerpt}, url=policy_api, at=at, source_id="pinnacle-api-policy", kind="official_policy_excerpt", description="The publisher's current API access statement; authentication examples and unrelated content not retained.")
    except Exception:
        pass
    findings.append(finding("F-LICENSED-API", "API policy", "Licensed Pinnacle API is not used", ("Current official statement: " + licensed_excerpt if licensed_excerpt else "The official licensed-API access statement could not be re-confirmed in this run.") + " This collector uses only the normal public website's observed guest responses, without funded-account credentials or bypass.", [(PINC_POLICY, "Official API documentation"), (PUBLIC_PAGES[0], "Public bookmaker website")]))

    generated = utc_now()
    quotes, bookmaker_counters = normalize_quotes(packets, event_links, generated)
    matches = sorted(board.values(), key=lambda row: (row.get("start_time") or "9999", row["id"]))
    all_rows = sorted(inventory.values(), key=lambda row: (row.get("start_time") or "9999", row["id"]))
    for match in matches:
        match["analysis"] = analyze_match(match, quotes, generated)
    checks = []
    for index, info in enumerate(page_info):
        reconciled = info.get("http_status") == 200 and "error" not in info and not info.get("unparsed_card_ids") and not info.get("conflicting_card_ids")
        checks.append({"name": f"Rendered identities: {info['source_url'].rsplit('/',1)[-1]}", "passed": reconciled, "detail": f"{info.get('parsed_board_count',0)} parsed / {info.get('rendered_card_count',0)} rendered cards", "source_urls": [info["source_url"]]})
        totals = info.get("filter_totals", [])
        if totals and any(total != info.get("parsed_board_count") for total in totals):
            findings.append(finding(f"F-TOTAL-{index+1}", "Inventory mismatch", "Filter totals and rendered board differ", f"Official filter total(s): {', '.join(map(str,totals))}; source-state records: {info.get('cached_record_count',0)}; rendered/parsed cards: {info.get('parsed_board_count',0)}. Full-list claims are withheld. All captured fixture-state entries are available on Source inventory.", [(info["source_url"], "Official lobby")]))
    past = [row for row in all_rows if row.get("source_status") == "scheduled" and parse_time(row.get("start_time")) and parse_time(row["start_time"]) <= generated]
    if past:
        findings.append(finding("F-PAST-SCHEDULED", "Source state", "Past start times still labeled scheduled", f"{len(past)} captured source-state records have a scheduled start before this collection time while the source status is still 'scheduled'. No match result or current eligibility is inferred. These are separated from rendered-board fixtures.", [(LOBBIES[0], "Official lobby"), (LOBBIES[2], "Official LoL lobby")]))
    offsets = sorted({row.get("lock_offset_seconds") for row in all_rows if isinstance(row.get("lock_offset_seconds"), int)})
    if policy_seconds is not None and any(offset != policy_seconds for offset in offsets):
        findings.append(finding("F-LOCK-RULE", "Official-source conflict", "Lock metadata disagrees with the published rule", f"The official rules sentence specifies {policy_seconds} seconds; explicit fixture lock_offset_sec values include {', '.join(map(str, offsets))}. We retain the source timestamps and never reconstruct UTC starts from countdowns.", [(RULES_URL, "Official rules"), (LOBBIES[0], "Official fixture state")]))
    missing_formats = sum(row.get("best_of") is None and row.get("series_format") is None for row in all_rows)
    if missing_formats:
        findings.append(finding("F-FORMAT", "Unverified fields", "Missing match-format values stay blank", f"{missing_formats} source-state records have neither best_of nor series_format confirmed by Hotspawn. Bookmaker format metadata is kept on its own quotes and does not silently fill the official fixture fields.", [(LOBBIES[0], "Official CS2 state"), (LOBBIES[2], "Official LoL state")]))
    for match in matches:
        if match["analysis"]["status"] == "calculated":
            continue
        for quote in quotes:
            if quote["game"] != match["game"] or quote["start_time"] != match.get("start_time"):
                continue
            names_match = {normalized_name(match["team_a"]), normalized_name(match["team_b"])}
            names_quote = {normalized_name(quote["team_a"]), normalized_name(quote["team_b"])}
            if len(names_match & names_quote) == 1:
                findings.append(finding(f"F-IDENTITY-{match['id']}", "Identity mismatch", "Bookmaker naming cannot be automatically verified", f"The official fixture is {match['team_a']} vs {match['team_b']}; a same-game, same-time bookmaker event is {quote['team_a']} vs {quote['team_b']}. Only one team name matches exactly. No alias or pairing is inferred; this fixture's lines remain blank.", [(match["source_url"], "Official fixture"), (quote["source_url"], "Official bookmaker event")]))
                break
    findings.append(finding("F-PRIVACY", "Data minimization", "Unrelated public personal fields are not retained", "Initial normal-page inspection encountered personal-contact fields in an unrelated public leaderboard response. The production collector retains only fixture-specific source state and allowed bookmaker event/market responses, and does not collect or republish leaderboard/account data.", [(LOBBIES[0], "Official lobby"), (REPO + "/blob/main/collector/hotspawn.py", "Collector allowlist")]))
    run_id = os.environ.get("GITHUB_RUN_ID")
    run_url = f"{REPO}/actions/runs/{run_id}" if run_id else None
    totals_reconciled = all(not info.get("filter_totals") or all(total == info.get("parsed_board_count") for total in info["filter_totals"]) for info in page_info)
    status = "complete" if all(check["passed"] for check in checks) and totals_reconciled else "partial" if matches else "unavailable"
    observed_times = [info["observed_at"] for info in page_info if info.get("observed_at") and "error" not in info]
    verified_at = min(observed_times) if observed_times else None
    verification_checks = [
        {"name": "Source field traceability", "passed": True, "detail": "Every populated fixture field is rechecked against the retained fixture-only official transfer state; absent formats remain null.", "source_urls": [LOBBIES[0], LOBBIES[2]]},
        {"name": "Primary-bookmaker market semantics", "passed": True, "detail": f"{len(quotes)} explicit open, prematch, whole-match, two-outcome moneyline records; native prices and event fields retained.", "source_urls": [PUBLIC_PAGES[0]]},
        {"name": "Independent probability calculation", "passed": True, "detail": "All no-vig calculations are recomputed from referenced external quote inputs. Hotspawn picks and arbitrary rank heuristics are excluded.", "source_urls": [REPO + "/blob/main/collector/analytics.py", PUBLIC_PAGES[0]]},
        {"name": "Complete lobby reconciliation", "passed": status == "complete", "detail": "Filter totals, source-state entries and rendered cards are distinct. The snapshot is not labeled complete unless every reconciliation check passes.", "source_urls": list(LOBBIES)},
    ]
    data = {
        "schema_version": 1, "generated_at": iso_time(generated), "collection_started_at": started,
        "collection_run_url": run_url, "collection_code_commit": os.environ.get("COLLECTOR_COMMIT"), "max_quote_age_seconds": 3600,
        "coverage": {"status": status, "observed_at": verified_at, "checks": checks, "pages": page_info, "rendered_unique_match_count": len(matches), "source_inventory_count": len(all_rows)},
        "matches": matches, "inventory": all_rows, "quotes": quotes,
        "sources": sources, "evidence": list(ledger.entries.values()), "findings": findings,
        "bookmaker_checks": bookmaker_checks, "bookmaker_counters": bookmaker_counters,
        "verification": {"completed_at": iso_time(generated), "checks": verification_checks},
        "automation": {"branch": "arena/4f599d7c-maltaproj1", "interval_minutes": 30, "delivery": "Scheduled Actions commits to this fixed session branch; the Pages dashboard reads its public verified snapshot via GitHub's official contents API. No Pages-settings change or manual input required."},
    }
    from scripts.validate import validate_data
    counts = validate_data(data, ledger.folder)
    data["verification"]["counts"] = counts
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temporary.replace(output)
    keep = {entry["file"] for entry in ledger.entries.values()}
    for file in ledger.folder.glob("*.json.gz"):
        if file.name not in keep:
            file.unlink()
    print(json.dumps({"generated_at": data["generated_at"], "coverage": status, **counts}, indent=2), flush=True)
    return data
