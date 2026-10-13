#!/usr/bin/env python3
"""Build an isolated, dependency-free, progressively enhanced Pages dashboard."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.analytics import MAX_QUOTE_AGE_SECONDS, parse_time, iso_time

REPO = "https://github.com/buffedlizard55-lab/MaltaProj1"
HOTSPAWN = "https://play.hotspawn.com/lobby"
ICON_PATHS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "list": '<path d="M8 5h13M8 12h13M8 19h13"/><path d="M3 5h1M3 12h1M3 19h1"/>',
    "game": '<rect x="3" y="5" width="18" height="14" rx="4"/><path d="M6 12h6M9 9v6M16 10h.01M18 14h.01"/>',
    "chart": '<path d="M3 3v18h18M7 15l4-5 4 3 6-8"/>',
    "link": '<path d="M10 13a5 5 0 007 0l3-3a5 5 0 00-7-7l-2 2M14 11a5 5 0 00-7 0l-3 3a5 5 0 007 7l2-2"/>',
    "flag": '<path d="M5 22V3M5 3c5-4 8 4 14 0v11c-6 4-9-4-14 0"/>',
    "book": '<path d="M12 5v16M3 4c3-1 6-1 9 1 3-2 6-2 9-1v15c-3-1-6-1-9 1-3-2-6-2-9-1z"/>',
    "code": '<path d="M8 5l-6 7 6 7M16 5l6 7-6 7M14 3l-4 18"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 16v5h16v-5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7h.01"/>',
    "search": '<circle cx="10" cy="10" r="6"/><path d="M15 15l6 6"/>',
    "menu": '<path d="M3 6h18M3 12h18M3 18h18"/>',
}


def e(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def icon(name: str) -> str:
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{ICON_PATHS[name]}</svg>'


def ext(url: str, label: str, cls: str = "source-link") -> str:
    if not isinstance(url, str) or not url.startswith("https://"):
        return ""
    return f'<a class="{e(cls)}" href="{e(url)}" target="_blank" rel="noopener noreferrer">{e(label)}</a>'


def stamp(value: str | None, full: bool = False) -> str:
    parsed = parse_time(value)
    if parsed is None:
        return ""
    return parsed.strftime("%d %b %Y · %H:%M UTC" if full else "%d %b · %H:%M UTC")


def pill(text: str, color: str = "gray", cls: str = "") -> str:
    return f'<span class="pill {e(color)} {e(cls)}">{e(text)}</span>'


def probability_cells(match: dict, quotes: dict) -> tuple[str, str, str]:
    analysis = match.get("analysis") or {}
    if analysis.get("status") != "calculated":
        return '<td class="probability-cell" aria-label="Probability unverified; intentionally blank"></td>', '<td aria-label="Fair line unverified; intentionally blank"></td>', ""
    a, b = analysis["probability_a"], analysis["probability_b"]
    pa = f'<span class="{"favorite" if a >= b else ""}">{a * 100:.1f}%</span>'
    pb = f'<span class="{"favorite" if b > a else ""}">{b * 100:.1f}%</span>'
    probabilities = f'<td class="probability-cell"><div class="probability-values live-value" aria-label="Calculated: {e(match["team_a"])} {a * 100:.1f} percent; {e(match["team_b"])} {b * 100:.1f} percent">{pa}{pb}</div><div class="probability-bar" aria-hidden="true"><span style="width:{a * 100:.3f}%"></span></div></td>'
    lines = f'<td><div class="line-pair live-value">{analysis["fair_odds_a"]:.2f}<span>/</span>{analysis["fair_odds_b"]:.2f}</div><div class="subtle">Calculated · decimal</div></td>'
    times = [parse_time(quotes[item["quote_id"]].get("observed_at")) for item in analysis["inputs"] if item["quote_id"] in quotes]
    times = [time for time in times if time]
    expiry = iso_time(min(times) + timedelta(seconds=MAX_QUOTE_AGE_SECONDS)) if times else ""
    return probabilities, lines, expiry


def match_row(match: dict, quote_map: dict) -> str:
    analysis = match.get("analysis") or {}
    priced = analysis.get("status") == "calculated"
    probability, lines, expires = probability_cells(match, quote_map)
    sources = ext(match.get("source_url"), "Hotspawn")
    odds_urls = []
    for item in analysis.get("inputs", []):
        quote = quote_map.get(item["quote_id"], {})
        url = quote.get("source_url")
        if url and url not in odds_urls:
            sources += ext(url, quote.get("source_name", quote.get("source_id", "Odds source")))
            odds_urls.append(url)
    parsed_start = parse_time(match.get("start_time"))
    start = f'{parsed_start.strftime("%d %b %Y")}<span class="subtle">{parsed_start.strftime("%H:%M")} UTC</span>' if parsed_start else ""
    pair = f'{match.get("team_a") or ""} vs {match.get("team_b") or ""}'
    marker = (match.get("team_a") or "")[:2].upper()
    game = match.get("game", "")
    tournament = match.get("tournament") or ""
    if priced:
        count = analysis.get("source_count", 0)
        status = pill("Calculated", "blue", "quote-state") + pill("Expired · unverified", "amber", "expiry-state")
        detail = f'{count} independent book{"s" if count != 1 else ""}'
    else:
        status = '<a href="flagged.html">' + pill("Unverified", "amber") + '</a>'
        detail = "No eligible external quote"
    attrs = {
        "row": match.get("id", ""), "game": game, "tournament": tournament,
        "search": f'{pair} {tournament} {game}', "match": pair,
        "start": match.get("start_time") or "", "priced": str(priced).lower(),
        "probability": analysis.get("probability_a") if priced else "",
        "pa": f'{analysis["probability_a"] * 100:.4f}' if priced else "",
        "pb": f'{analysis["probability_b"] * 100:.4f}' if priced else "",
        "fa": f'{analysis["fair_odds_a"]:.6f}' if priced else "",
        "fb": f'{analysis["fair_odds_b"]:.6f}' if priced else "",
        "status": "Calculated" if priced else "Unverified",
        "source": match.get("source_url") or "", "odds-sources": " | ".join(odds_urls),
    }
    if expires:
        attrs["quote-expires"] = expires
    attributes = " ".join(f'data-{key}="{e(value)}"' for key, value in attrs.items())
    evidence_note = match.get("evidence_locator") or ""
    return f'''<tr {attributes}>
<td class="match-cell"><div class="match-pair"><span class="team-mark" aria-hidden="true">{e(marker)}</span><span>{e(match.get("team_a"))}</span><span class="vs">vs</span><span>{e(match.get("team_b"))}</span></div><div class="match-meta"><span class="game-chip">{e(game.upper())}</span><span class="tournament-label" title="{e(tournament)}">{e(tournament)}</span></div></td>
<td class="start-time">{start}</td>{probability}{lines}
<td>{status}<div class="evidence-note">{e(detail)}</div></td><td class="sources-cell">{sources}</td></tr>'''


def match_table(matches: list[dict], data: dict, title: str, subtitle: str, filters: bool = True, overview: bool = False) -> str:
    quote_map = {quote["id"]: quote for quote in data.get("quotes", [])}
    tournaments = sorted({match.get("tournament") for match in matches if match.get("tournament")})
    options = "".join(f'<option value="{e(value)}">{e(value)}</option>' for value in tournaments)
    tabs = ""
    if filters:
        cs2_count = sum(match.get("game") == "cs2" for match in matches)
        lol_count = sum(match.get("game") == "lol" for match in matches)
        tabs = f'''<div class="game-tabs" role="group" aria-label="Game category"><button type="button" class="game-tab" data-game-tab="all" aria-pressed="true">All matches <span class="tab-count">{len(matches)}</span></button><button type="button" class="game-tab" data-game-tab="cs2" aria-pressed="false">Counter-Strike 2 <span class="tab-count">{cs2_count}</span></button><button type="button" class="game-tab" data-game-tab="lol" aria-pressed="false">League of Legends <span class="tab-count">{lol_count}</span></button></div>'''
    toolbar = f'''<div class="toolbar"><div class="search-wrap">{icon("search")}<label class="sr-only" for="match-search">Search team or tournament</label><input class="search" id="match-search" type="search" placeholder="Search a team or tournament…" autocomplete="off"></div><label class="sr-only" for="coverage-filter">Market coverage</label><select class="select" id="coverage-filter"><option value="">All coverage</option><option value="priced">With external odds</option><option value="unverified">Unverified / blank</option></select><label class="sr-only" for="tournament-filter">Tournament</label><select class="select" id="tournament-filter"><option value="">All tournaments</option>{options}</select><button class="button" id="clear-filters" type="button">Reset filters</button></div>''' if filters else ""
    rows = "".join(match_row(match, quote_map) for match in matches)
    empty = '<div class="empty"><strong>No verified fixtures are available in this snapshot.</strong>Source access or parsing must succeed before match values can be published. See <a href="flagged.html">Flagged for Review</a>.</div>' if not matches else ""
    filter_attr = "data-filter-table" if filters else ""
    action = '<a href="matches.html" class="button">All matches →</a>' if overview else f'<button class="button" type="button" id="download-csv">{icon("download")} Export CSV</button>' if filters else ""
    def sort_label(key, label):
        return f'<button class="sort" data-sort="{key}" type="button">{label}</button>' if filters else label
    return f'''<section class="panel"><div class="panel-heading"><div><h2>{e(title)}</h2><p>{e(subtitle)}</p></div>{action}</div>{tabs}{toolbar}<div class="table-scroll"><table {filter_attr}><caption class="sr-only">{e(title)}. Probabilities and fair odds are calculated, not Hotspawn crowd picks. Blank means unverified.</caption><thead><tr><th scope="col">{sort_label("match", "Match / tournament")}</th><th scope="col">{sort_label("start", "Start · UTC")}</th><th scope="col">{sort_label("probability", "Our probability")}</th><th scope="col">Our fair line</th><th scope="col">Evidence status</th><th scope="col">Official sources</th></tr></thead><tbody>{rows}</tbody></table></div>{empty}<div class="empty no-results" id="no-results" hidden><strong>No matches found.</strong>Try a different team, tournament, or coverage filter.</div><div class="table-footer"><span id="result-count">Showing {len(matches)} fixtures</span><a href="methodology.html">How we calculate these lines ↗</a></div></section>'''


def metrics(data: dict) -> str:
    matches = data.get("matches", [])
    priced = sum((match.get("analysis") or {}).get("status") == "calculated" for match in matches)
    pct = f'{100 * priced / len(matches):.0f}%' if matches else ""
    cards = [
        ("Official fixtures captured", str(len(matches)), "list", "Source records, not filter totals", ""),
        ("Matches with our lines", str(priced), "chart", "Outside match-winner odds only", "metric-priced"),
        ("Market coverage", pct, "link", "Priced / captured fixtures", "metric-coverage"),
        ("Intentionally unpriced", str(len(matches) - priced), "flag", "Unverified values stay blank", "metric-unpriced"),
    ]
    return '<div class="metrics">' + ''.join(f'<div class="metric"><div class="metric-label">{label}<span class="metric-icon">{icon(symbol)}</span></div><div class="metric-value" {f"id={identifier}" if identifier else ""}>{e(value)}</div><div class="metric-note">{e(note)}</div></div>' for label, value, symbol, note, identifier in cards) + '</div>'


def source_mini(data: dict) -> str:
    rows = ""
    for source in data.get("sources", [])[:4]:
        status = source.get("status", "unverified")
        color = "green" if status == "observed" else "amber"
        rows += f'<div class="mini-source"><div><strong>{e(source["name"])}</strong><small>{e(source.get("role_label"))}</small></div>{pill("Observed" if status == "observed" else "Needs review", color)}</div>'
    return rows or '<p>No source retrieval has been verified.</p>'


def overview(data: dict) -> str:
    matches = data.get("matches", [])
    status = data.get("coverage", {}).get("status", "unverified")
    note = "A timestamped inventory, not a live betting feed. Only explicit external match-winner prices are used."
    if status != "complete":
        note += " The source inventory is incomplete or cannot yet be reconciled; full-list claims are withheld."
    notice = f'<div class="notice">{icon("info")}<p><strong>Independent lines. Transparent evidence.</strong> {e(note)} <a href="sources.html">View source checks →</a></p></div>'
    categories = ""
    for game, label, url in (("cs2", "Counter-Strike 2", "cs2.html"), ("lol", "League of Legends", "lol.html")):
        count = sum(match.get("game") == game for match in matches)
        categories += f'<a class="category-row" href="{url}"><span class="category-icon">{game.upper()}</span><span class="category-text"><strong>{label}</strong><small>Official fixtures + independently calculated lines</small></span><span class="category-count">{count} matches</span></a>'
    upcoming = [match for match in matches if (parse_time(match.get("start_time")) or datetime.max.replace(tzinfo=timezone.utc)) > datetime.now(timezone.utc)]
    highlighted = sorted(upcoming or matches, key=lambda match: match.get("start_time") or "9999")[:8]
    return notice + metrics(data) + match_table(highlighted, data, "The pick’em board", "Next captured fixtures · team order matches the source", filters=False, overview=True) + f'''<div class="lower-grid"><section class="panel compact-panel"><h2>Browse by game</h2><p>Keep the board focused on the matches you follow.</p>{categories}</section><section class="panel compact-panel"><h2>Source health</h2><p>Access status is separate from odds verification.</p>{source_mini(data)}<a class="inline-link" href="sources.html">All source checks →</a></section></div><p class="footnote">“Our probability” removes each bookmaker’s margin, then averages eligible independent books equally. It is a derived market estimate, not a verified chance of winning. We do not use Hotspawn crowd picks, HLTV pick indicators, rankings, tournament outrights, or invented prices. Every blank is intentional. <a href="methodology.html">Read the full methodology.</a></p>'''


def quote_table(data: dict) -> str:
    rows = ""
    for quote in data.get("quotes", []):
        a, b = quote.get("odds_a"), quote.get("odds_b")
        expiry = ""
        observed = parse_time(quote.get("observed_at"))
        if observed:
            expiry = f' data-quote-expires="{e(iso_time(observed + timedelta(seconds=MAX_QUOTE_AGE_SECONDS)))}" data-start="{e(quote.get("start_time"))}"'
        rows += f'''<tr{expiry}><td><strong>{e(quote.get("team_a"))} vs {e(quote.get("team_b"))}</strong><div class="subtle">{e(quote.get("tournament"))} · {e(quote.get("game", "").upper())}</div></td><td>{e(quote.get("source_name"))}</td><td class="nowrap"><span class="live-value">{a:.4f} / {b:.4f}</span></td><td>{e(stamp(quote.get("observed_at"), True))}</td><td>{pill("Official quote", "green", "quote-state")}{pill("Expired · unverified", "amber", "expiry-state")}<div class="subtle">Match winner · 2 outcomes</div></td><td>{ext(quote.get("source_url"), "Bookmaker event")}{ext(quote.get("api_url"), "Official response")}</td></tr>'''
    empty = '<div class="empty"><strong>No eligible primary-bookmaker quotes in this snapshot.</strong>We do not substitute crowd picks, rankings, tournament outrights, or secondary tipster prices. Source limitations are listed on <a href="flagged.html">Flagged for Review</a>.</div>' if not rows else ""
    return f'''<div class="notice">{icon("info")}<p><strong>Raw inputs, separate from our analysis.</strong> These are observed decimal prices from official bookmaker interfaces. They are snapshots, not executable offers. Suspended, live, map-only, draw, and stale markets are excluded.</p></div><section class="panel wide-table"><div class="panel-heading"><div><h2>External match-winner markets</h2><p>{len(data.get("quotes", []))} eligible quote records · unchanged source team names</p></div><a class="button" href="data/snapshot.json">Download evidence JSON</a></div><div class="table-scroll"><table><caption class="sr-only">Primary-bookmaker match-winner price observations</caption><thead><tr><th>Bookmaker fixture</th><th>Bookmaker</th><th>Decimal A / B</th><th>Observed · UTC</th><th>Verification</th><th>Official sources</th></tr></thead><tbody>{rows}</tbody></table></div>{empty}</section>'''


def sources_page(data: dict) -> str:
    rows = ""
    for source in data.get("sources", []):
        status = source.get("status", "unverified")
        rows += f'''<tr><td><strong>{e(source.get("name"))}</strong><div class="subtle">{e(source.get("role_label"))}</div></td><td class="detail">{e(source.get("usage"))}</td><td>{pill("Observed" if status == "observed" else "Unverified", "green" if status == "observed" else "amber")}<div class="subtle">{e(source.get("http_status"))}</div></td><td>{e(stamp(source.get("observed_at"), True))}</td><td>{ext(source.get("url"), "Official site")}{ext(source.get("policy_url"), "Official policy")}{ext(source.get("api_url"), "Observed interface")}</td></tr>'''
    evidence_rows = ""
    for entry in data.get("evidence", []):
        path = entry.get("file")
        evidence_link = f'<a class="source-link" href="data/evidence/{e(Path(path).name)}">Retained source evidence</a>' if path else ""
        evidence_rows += f'''<tr><td class="flag-code">{e(entry.get("id"))}</td><td class="detail">{e(entry.get("description"))}<div class="subtle">SHA-256: <code>{e(entry.get("sha256"))}</code></div></td><td>{e(stamp(entry.get("retrieved_at"), True))}</td><td>{ext(entry.get("url"), "Official response")}{evidence_link}</td></tr>'''
    return f'''<div class="notice">{icon("info")}<p><strong>A link is not proof of a price.</strong> Source access, a parsed observation, and a calculated result are different states. Only retained, timestamped primary-bookmaker evidence can populate our lines. HTTP 200 alone is not verification.</p></div><section class="panel wide-table"><div class="panel-heading"><div><h2>Source registry</h2><p>Primary origins and explicit usage restrictions</p></div></div><div class="table-scroll"><table><caption class="sr-only">Official sources and retrieval status</caption><thead><tr><th>Source / role</th><th>How it is used</th><th>Access state</th><th>Observed · UTC</th><th>Manual review</th></tr></thead><tbody>{rows}</tbody></table></div></section><section class="panel wide-table"><div class="panel-heading"><div><h2>Evidence ledger</h2><p>Content hashes and retrieval timestamps for row-level checking</p></div></div><div class="table-scroll"><table><caption class="sr-only">Retained primary-source evidence</caption><thead><tr><th>Evidence ID</th><th>Observation / content hash</th><th>Retrieved · UTC</th><th>Source + snapshot</th></tr></thead><tbody>{evidence_rows}</tbody></table></div></section><p class="footnote">Evidence retention is intentionally small. The collector never logs account credentials, submits picks, or places wagers. Research and implementation: <a href="{REPO}/tree/main/research" target="_blank" rel="noopener noreferrer">repository source notes ↗</a>.</p>'''


def inventory_page(data: dict) -> str:
    rows = ""
    at = parse_time(data.get("generated_at"))
    inventory = data.get("inventory", [])
    for row in sorted(inventory, key=lambda item: item.get("start_time") or "9999"):
        started = parse_time(row.get("start_time"))
        past = bool(started and at and started <= at)
        presence = pill("Rendered card", "blue") if row.get("on_rendered_board") else pill("Cached state only", "gray")
        timing = '<div class="subtle">Start is in the past; result not inferred</div>' if past else ""
        format_value = row.get("series_format") if row.get("series_format") is not None else row.get("best_of")
        rows += f'<tr><td><strong>{e(row.get("team_a"))} vs {e(row.get("team_b"))}</strong><div class="subtle">{e(row.get("tournament"))} · ID {e(row.get("id"))}</div></td><td>{e(row.get("game", "").upper())}</td><td class="nowrap">{e(stamp(row.get("start_time"), True))}{timing}</td><td>{e(row.get("source_status"))}</td><td>{e(format_value)}</td><td>{presence}</td><td>{ext(row.get("source_url"), "Official fixture/state")}{ext(row.get("lobby_url"), "Official lobby")}</td></tr>'
    return f'<div class="notice warning">{icon("info")}<p><strong>Source state is not the current pick’em board.</strong> All {len(inventory)} distinct captured fixture-state entries are listed here, including historical records and cached-only entries. A past timestamp does not prove a result. Only rendered, source-matched cards populate the board pages; missing formats stay blank.</p></div><section class="panel wide-table"><div class="panel-heading"><div><h2>Full captured source-state inventory</h2><p>Every retained fixture entry · raw source status preserved</p></div><a class="button" href="matches.html">Rendered board →</a></div><div class="table-scroll"><table><caption class="sr-only">All fixture-state records captured from official public lobbies, not an inferred current match list</caption><thead><tr><th>Source fixture</th><th>Game</th><th>Scheduled start · UTC</th><th>Source status</th><th>Format (if confirmed)</th><th>Presence in this observation</th><th>Official sources</th></tr></thead><tbody>{rows}</tbody></table></div></section>'


def flagged_page(data: dict) -> str:
    findings = list(data.get("findings", []))
    for match in data.get("matches", []):
        if (match.get("analysis") or {}).get("status") == "calculated":
            continue
        findings.append({
            "id": f'M-{match["id"]}', "category": "Missing market", "severity": "unverified",
            "title": f'{match.get("team_a", "")} vs {match.get("team_b", "")}',
            "detail": "No fresh, open, two-sided official match-winner quote passed exact game, team-pair, and UTC-start matching. Probability and fair-line values remain blank.",
            "source_urls": [{"url": match.get("source_url"), "label": "Official fixture"}],
        })
    rows = ""
    for finding in findings:
        links = "".join(ext(source["url"], source.get("label", "Official source")) for source in finding.get("source_urls", []) if source.get("url"))
        rows += f'<tr><td class="flag-code">{e(finding.get("id"))}</td><td>{pill(finding.get("category", "Review"), "amber")}</td><td class="detail"><span class="flag-title">{e(finding.get("title"))}</span>{e(finding.get("detail"))}</td><td>{pill("Needs review", "amber")}</td><td>{links}</td></tr>'
    return f'''<div class="notice warning">{icon("flag")}<p><strong>Published, not hidden.</strong> These findings do not block a working site. They do block unsupported data claims. Missing values are blank; no estimate is substituted. This page includes every captured fixture without an eligible market.</p></div><section class="panel wide-table"><div class="panel-heading"><div><h2>Flagged for Review</h2><p>{len(findings)} findings · official links for manual review</p></div><a class="button" href="data/snapshot.json">Evidence JSON</a></div><div class="table-scroll"><table><caption class="sr-only">Unverified data, irregularities, and their official sources</caption><thead><tr><th>ID</th><th>Category</th><th>Finding / impact</th><th>Status</th><th>Official sources</th></tr></thead><tbody>{rows}</tbody></table></div>{'<div class="empty">No findings recorded.</div>' if not rows else ''}</section>'''


def methodology_page(data: dict) -> str:
    implementation = REPO + "/blob/main/collector/analytics.py"
    return f'''<section class="panel"><div class="prose"><h2>Independent of Hotspawn’s crowd</h2><p>Hotspawn provides the eligible fixture identities and schedules, never a win-probability signal. Crowd picks are not imported into the analytical schema. HLTV rankings, HLTV community indicators, secondary tipster forecasts, and tournament outrights are not substitutes for match odds.</p><h2>What “our line” means</h2><p>Our line is a reproducible, margin-free market estimate derived from outside bookmaker prices. It is not a statistically calibrated prediction or an independently verified chance of winning. “Calculated” means the arithmetic and its source inputs have been checked; it does not mean a team’s true win probability is known.</p><h3>1. Admit only the correct market</h3><ul><li>Primary bookmaker evidence, official source URL, content hash, and explicit retrieval timestamp.</li><li>Exactly two outcomes, both valid decimal prices greater than 1; whole-match winner only.</li><li>Not live, suspended, a map market, a handicap, a draw market, or a tournament outright.</li><li>Freshness: at most {MAX_QUOTE_AGE_SECONDS // 60} minutes since observation; exclude quotes once the match starts.</li><li>Exact game, team pair, and timezone-confirmed UTC start. Only case, whitespace, and Unicode representation are normalized. We do not guess team aliases or infer missing timezones.</li><li>Ambiguous distinct events for the same book and fixture are excluded. Team order may be reversed only with exact identity matching.</li></ul><h3>2. Remove each bookmaker’s margin</h3><div class="formula">q(A) = 1 / decimal_odds(A)<br>q(B) = 1 / decimal_odds(B)<br>overround = q(A) + q(B) − 1<br>p(A) = q(A) / [q(A) + q(B)]<br>p(B) = q(B) / [q(A) + q(B)]</div><h3>3. Combine independent books</h3><p>Use the latest eligible matched quote from each bookmaker, then take the equally weighted arithmetic mean of its no-vig p(A). Set p(B) = 1 − p(A). One book gets one vote; duplicate markets do not add weight. With one book, the result is labeled a one-source calculation, not a market consensus.</p><div class="formula">our_p(A) = mean(p_book_1(A), …, p_book_n(A))<br>our_fair_decimal(A) = 1 / our_p(A)<br>our_fair_decimal(B) = 1 / [1 − our_p(A)]</div><p>We never add a fabricated bookmaker margin, pick a favorite without evidence, or assign a 50/50 prior to an unpriced fixture. Displayed percentages are rounded to one decimal place and fair decimal odds to two; calculations retain full precision in the downloadable JSON.</p><h2>Blank, observed, calculated, and stale</h2><ul><li><strong>Blank / unverified:</strong> no supported input. Values are intentionally omitted.</li><li><strong>Observed:</strong> a source was retrieved and its response inspected; this alone does not verify an odds value.</li><li><strong>Calculated:</strong> eligible external inputs are attached and the specified arithmetic is reproducible.</li><li><strong>Stale:</strong> the snapshot or quote has expired. The browser hides expired probabilities/prices and keeps source links visible.</li></ul><h2>Collection and completeness</h2><p>The scheduled collector runs without manual entries. It retains source timestamps and hashes, checks every normalized record against captured evidence, and publishes any source failure or inventory mismatch. A successful HTML request does not prove the lobby is complete. Filter totals, weekly totals, rendered cards, and underlying state may refer to different sets; mismatches are reported rather than reconciled by invention.</p><h2>Review the implementation</h2><p>{ext(implementation, "Official repository: probability implementation", "inline-link")} · {ext(REPO + "/tree/main/tests", "Verification tests", "inline-link")} · {ext(HOTSPAWN, "Official lobby", "inline-link")}</p><p>Analysis only. No account login, automatic pick submission, wagering, affiliate links, or financial advice.</p></div></section>'''


def repository_page(data: dict) -> str:
    rows = ""
    for check in data.get("verification", {}).get("checks", []):
        links = "".join(ext(url, "Official source") for url in check.get("source_urls", [])) or ext(REPO, "Official repository")
        rows += f'<tr><td><strong>{e(check.get("name"))}</strong></td><td class="detail">{e(check.get("detail"))}</td><td>{pill("Passed" if check.get("passed") else "Needs review", "green" if check.get("passed") else "amber")}</td><td>{links}</td></tr>'
    return f'''<div class="notice">{icon("code")}<p><strong>Preserving parallel work.</strong> This dashboard is isolated under <code>dashboard/</code>. Existing CSVs, the legacy rank model, and other sessions’ pages are not used to populate these lines and have not been overwritten.</p></div><section class="panel wide-table"><div class="panel-heading"><div><h2>Verification report</h2><p>{e(stamp(data.get("verification", {}).get("completed_at"), True))} · row-level evidence checks</p></div><a class="button" href="data/snapshot.json">Full report JSON</a></div><div class="table-scroll"><table><caption class="sr-only">Repository and data verification checks with official sources</caption><thead><tr><th>Check</th><th>What was verified</th><th>Result</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></div></section><section class="panel"><div class="prose"><h2>Repository review and coordination</h2><p>The starting repository contained a one-line README. Concurrent sessions later added a static CS2 extract, a rank-based heuristic, and source notes. Those are retained as separately owned work, not promoted to bookmaker-line evidence. Broad or overlapping claims were logged and this session’s paths narrowed to avoid conflicts.</p><p>{ext(REPO + "/blob/main/COORDINATION.md", "Shared task board and integration log", "inline-link")} · {ext(REPO + "/tree/main/research", "Source and repository audit notes", "inline-link")}</p><h2>Scope of verification</h2><p>Every populated match field must be traceable to the captured official state or markup. Every odds value must have a primary-bookmaker response and match-market semantics. Each calculated probability is recomputed by tests and the validator. Any field not confirmed by the corresponding official source remains blank and is flagged.</p><p>The collector reports external access failures honestly. The build checks every internal page, asset, download, and navigation link. It does not describe unreachable external pages as successfully verified.</p></div></section>'''


def layout(key: str, title: str, description: str, content: str, data: dict) -> str:
    navigation = [
        ("index", "Overview", "grid"), ("matches", "All matches", "list"),
        ("cs2", "Counter-Strike 2", "game"), ("lol", "League of Legends", "game"),
        ("markets", "External markets", "chart"), ("inventory", "Source inventory", "list"), ("sources", "Sources & evidence", "link"),
        ("flagged", "Flagged for Review", "flag"), ("methodology", "Methodology", "book"),
        ("repository", "Repository audit", "code"),
    ]
    links = ""
    for i, (page, label, symbol) in enumerate(navigation):
        if i == 0:
            links += '<div class="nav-heading">Workspace</div>'
        if i == 6:
            links += '<div class="nav-heading">Transparency</div>'
        active = ' active' if key == page else ''
        current = ' aria-current="page"' if key == page else ''
        links += f'<a class="nav-item{active}" href="{page}.html"{current}>{icon(symbol)}{label}</a>'
    at = data.get("generated_at") or ""
    observed = data.get("coverage", {}).get("observed_at") or ""
    label = data.get("coverage", {}).get("status", "unverified")
    coverage_pill = pill("Inventory complete" if label == "complete" else "Inventory needs review", "green" if label == "complete" else "amber")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Source-linked esports match inventory and independently calculated no-vig lines. Unknown values remain blank."><meta name="color-scheme" content="light"><title>{e(title)} · Linescope</title><link rel="stylesheet" href="assets/dashboard.css"><script src="assets/dashboard.js" defer></script><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"></head>
<body data-view="{e(key)}" data-snapshot="{e(at)}" data-verified-at="{e(observed)}" data-max-age="{MAX_QUOTE_AGE_SECONDS}"><a class="skip" href="#main">Skip to content</a>
<aside class="sidebar" id="sidebar"><a class="brand" href="index.html" aria-label="Linescope overview"><span class="brand-mark" aria-hidden="true">≋</span><span><strong>linescope</strong><small>Esports · evidence first</small></span></a><nav aria-label="Dashboard navigation">{links}</nav><div class="sidebar-bottom"><div class="side-status"><span class="dot"></span>Independent of crowd picks</div><p>Official fixtures. Outside odds.<br>Blank where evidence is missing.</p>{ext(REPO, "MaltaProj1 on GitHub", "inline-link")}</div></aside>
<div id="mobile-shade" class="mobile-shade" aria-hidden="true"></div><div class="app"><header class="topbar"><button id="menu-toggle" class="menu-toggle" type="button" aria-controls="sidebar" aria-expanded="false" aria-label="Open dashboard navigation">{icon("menu")}<strong>linescope</strong></button><div class="breadcrumb">Workspace<span>/</span><b>{e(title)}</b></div><div class="top-actions"><span class="snapshot-indicator"><span class="dot amber"></span><span id="snapshot-freshness">{e(stamp(observed)) or 'Snapshot unverified'}</span></span>{ext(REPO, "Repository ↗", "repo-link")}</div></header>
<main class="main" id="main"><div class="page-heading"><div><div class="eyebrow"><span class="dot" style="background:var(--blue)"></span>Hotspawn pick’em analysis</div><h1>{e(title)}</h1><p class="page-description">{e(description)}</p></div><div class="heading-actions">{coverage_pill}<a class="button" href="{HOTSPAWN}" target="_blank" rel="noopener noreferrer">Official lobby ↗</a></div></div>
<div id="snapshot-banner" class="notice warning snapshot-banner" hidden>{icon("clock")}<p><strong>This snapshot is stale or unverified.</strong> Expired quotes and their calculated lines are hidden. Fixture names may reflect a previous collection, not the current lobby. <a href="flagged.html">Review collection limitations →</a></p></div>
<noscript><div class="notice warning"><p>This is a dated, published snapshot. JavaScript is required for automatic updates and quote expiry; displayed prices are historical observations, not current offers.</p></div></noscript>{content}<footer class="footer"><span>Linescope · MaltaProj1<br>Analysis only. No automatic picks or wagers.<br><span id="update-check-status">Published snapshot · automatic check pending</span></span><span>Blank = unverified · probabilities = calculated<br><a href="sources.html">Sources</a> · <a href="methodology.html">Methodology</a> · <a href="flagged.html">Flagged for Review</a></span></footer></main></div></body></html>'''


def build(data_path: Path, output: Path) -> list[Path]:
    data = json.loads(data_path.read_text())
    output.mkdir(parents=True, exist_ok=True)
    (output / "assets").mkdir(exist_ok=True)
    (output / "data" / "evidence").mkdir(parents=True, exist_ok=True)
    for asset in ("dashboard.css", "dashboard.js"):
        shutil.copyfile(ROOT / "webui" / asset, output / "assets" / asset)
    (output / "assets" / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="18" fill="#4566e8"/><path d="M16 23h32M16 32h32M16 41h32" stroke="#fff" stroke-width="5" stroke-linecap="round"/></svg>')
    (output / "data" / "snapshot.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    for evidence in data.get("evidence", []):
        if evidence.get("file"):
            source = data_path.parent / "evidence" / Path(evidence["file"]).name
            if not source.is_file():
                raise ValueError(f"Missing retained evidence: {source}")
            shutil.copyfile(source, output / "data" / "evidence" / source.name)
    keep_evidence = {entry.get("file") for entry in data.get("evidence", [])}
    for previous in (output / "data" / "evidence").glob("*.json.gz"):
        if previous.name not in keep_evidence:
            previous.unlink()
    matches = sorted(data.get("matches", []), key=lambda item: item.get("start_time") or "9999")
    pages = {
        "index": ("The pick’em board, with evidence.", "A simple view of official matches, outside betting markets, and our independently calculated fair lines. No crowd-pick probabilities. No invented values.", overview(data)),
        "matches": ("All matches", "Every captured fixture in one source-linked table. Filter by game, tournament, or verified market coverage.", metrics(data) + match_table(matches, data, "Official fixture inventory", "Blank probability and line cells are unverified, not 50/50 estimates.")),
        "cs2": ("Counter-Strike 2", "Source-confirmed CS2 fixtures, outside match-winner markets, and transparent no-vig calculations.", match_table([item for item in matches if item.get("game") == "cs2"], data, "CS2 pick’em fixtures", "Exact game, team pair, and UTC start are required for odds matching.")),
        "lol": ("League of Legends", "LoL fixtures are collected separately so the full pick’em scope is not mistaken for a CS2-only board.", match_table([item for item in matches if item.get("game") == "lol"], data, "League of Legends fixtures", "Unpriced regional matches remain visible, with blank probabilities.")),
        "markets": ("External markets", "The primary-bookmaker observations behind our calculations. Hotspawn is never an odds source.", quote_table(data)),
        "inventory": ("Source-state inventory", "All captured fixture entries, including cached and historical records—kept separate from the rendered pick’em board.", inventory_page(data)),
        "sources": ("Sources & evidence", "Open every official source, inspect its retrieval status, and trace populated values back to timestamped evidence.", sources_page(data)),
        "flagged": ("Flagged for Review", "Inventory mismatches, unverified fields, missing markets, and source limitations—published for review, never silently filled.", flagged_page(data)),
        "methodology": ("How our lines are calculated", "A reproducible market-based calculation, with strict evidence gates and no unsupported priors.", methodology_page(data)),
        "repository": ("Repository audit", "What was checked, what remains unverified, and how parallel work has been preserved.", repository_page(data)),
    }
    outputs = []
    for key, (title, description, content) in pages.items():
        path = output / f"{key}.html"
        path.write_text(layout(key, title, description, content, data))
        outputs.append(path)
    (output / ".nojekyll").write_text("")
    (output / "404.html").write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Page not found · Linescope</title><link rel="stylesheet" href="assets/dashboard.css"></head><body><main class="main"><h1>Page not found</h1><p><a href="index.html">Return to the dashboard</a></p></main></body></html>')
    return outputs


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/snapshot/latest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "dashboard")
    args = parser.parse_args()
    paths = build(args.data, args.output)
    print(f"Built {len(paths)} dashboard pages at {args.output}")
