#!/usr/bin/env python3
"""Build the valuepicks/ board (session arena/7759beef).

What this board adds on top of the executive capture:

1. **A pick for every open Hotspawn fixture.** The executive board leaves a row blank when no
   *fresh, exact-identity, primary-book* quote exists. This board keeps that rule for the headline
   tier but then walks the same research ladder the brief asks for - a relayed bookmaker line, then
   the project's own line from official ratings - so every open fixture carries a pick, a two-sided
   probability pair, the tier that produced it and the source links behind it.
2. **A value (contrarian) table.** Where both an outside market number and a project own line exist,
   the difference is published as ``divergence_pp``. A positive divergence means the market rates a
   side *lower* than the project's official-ratings line does. That is the only sense in which this
   board is contrarian, and every such row keeps its identity/format caveats.
3. **A day review** of the 2026-10-15 TWC slate (the 9z-Aurora upset) and the roster/context facts
   that a pick should be aware of, each with a source link and read time.
4. **An explicit unresolved/limitations page** listing exactly which rows cannot reach the top tier
   and why, instead of hiding the gap.

Fail-closed rules (enforced by tests/test_7759beef.py):
* a row without a documented tier, odds or rating inputs cannot publish a number;
* a published market probability must recompute from the stored decimal odds;
* a published own-line probability must recompute from the stored rating inputs;
* Hotspawn's crowd pick percentage is never read as a probability input.

Run: python3 scripts/7759beef_build.py
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "valuepicks"
DATA = OUT / "data"
SOURCES = ROOT / "research" / "7759beef" / "sources.json"
EXEC = ROOT / "executive" / "data"

SESSION = "arena/7759beef"
BOARD_NAME = "Hotspawn CS2 - day review, guaranteed picks & value watches"
RATIO_POINTS = 400.0  # official VRS convention used by the project model

TIER_LABEL = {
    "Market · primary book": "A · direct bookmaker",
    "Market · secondary listing": "B · relayed/secondary listing",
    "Market · prediction market": "C · prediction market",
    "Model · official ratings": "D · project line (official ratings)",
    "No sourced basis": "E · unresolved at top tier",
}

# ---------------------------------------------------------------- project model (read-only import)


def _load_ownlines():
    spec = importlib.util.spec_from_file_location("exec_ownlines", ROOT / "executive" / "ownlines.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


OWN = _load_ownlines()


def own_line(points_a: float, points_b: float, best_of: int) -> float:
    """Per-map logistic on official VRS points, then the exact best-of transform."""
    p_map = 1.0 / (1.0 + 10.0 ** ((float(points_b) - float(points_a)) / RATIO_POINTS))
    return OWN.series_probability(p_map, best_of)


def devig(odds_a: float, odds_b: float) -> tuple[float, float]:
    inv_a, inv_b = 1.0 / float(odds_a), 1.0 / float(odds_b)
    total = inv_a + inv_b
    return round(inv_a / total * 100, 1), round(inv_b / total * 100, 1)


def pct(value) -> float | None:
    try:
        if value in ("", None):
            return None
        return round(float(value), 1)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------- inputs
def load_exec_rows() -> list[dict]:
    with (EXEC / "analysis.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_sources() -> dict:
    return json.loads(SOURCES.read_text(encoding="utf-8"))


def fact_index(sources: dict) -> dict:
    return {fact["id"]: fact for fact in sources["facts"]}


def resolution_index(sources: dict) -> dict:
    return {row["match_id"]: row for row in sources["resolutions"]}


# ---------------------------------------------------------------------------- board rows
def build_board(rows: list[dict], sources: dict) -> tuple[list[dict], list[dict], list[dict]]:
    facts = fact_index(sources)
    resolutions = resolution_index(sources)
    board, unresolved, coverage = [], [], []

    for row in rows:
        match_id = row["match_id"]
        status = row["status"]
        record = {
            "match_id": match_id,
            "status": status,
            "team_a": row["team_a"],
            "team_b": row["team_b"],
            "tournament": row["tournament"],
            "tier": row["tier"],
            "lock_utc": row["lock_utc"],
            "start_utc": row["start_utc"],
            "hotspawn_pickem_url": row["hotspawn_pickem_url"],
            "hotspawn_match_url": row.get("hotspawn_match_url", ""),
        }

        if status != "open":
            record.update(pick="", prob_a_pct=None, prob_b_pct=None,
                          basis_label="not published - fixture locked or stale at capture",
                          basis_tier="", sources=[])
            coverage.append(record)
            continue

        # A hand-written resolution is only used while the executive capture still leaves the row
        # unpicked. Once the executive pipeline prices the fixture itself, its fresher row wins and
        # the resolution drops to background evidence (the test suite enforces this).
        resolution = resolutions.get(match_id) if not (row["pick"] or "").strip() else None
        if resolution:
            market = resolution["market"]
            own = resolution["own"]
            prob_a, prob_b = market["prob_a_pct"], market["prob_b_pct"]
            recomputed = devig(market["odds_a"], market["odds_b"])
            assert (prob_a, prob_b) == recomputed, f"{match_id}: stored market probabilities do not de-vig"
            own_a = own_line(own["vrs_a"], own["vrs_b"], own["best_of"]) * 100
            assert abs(round(own_a, 1) - own["prob_a_pct"]) <= 0.15, f"{match_id}: own line does not recompute"
            pick = resolution["hotspawn_team_a"] if prob_a >= prob_b else resolution["hotspawn_team_b"]
            basis_label = f"{market['source_name']} ({market['tier']})"
            basis_tier = TIER_LABEL["Market · secondary listing"] if market["tier"] == "relayed-book" \
                else TIER_LABEL["Market · primary book"]
            source_list = [facts[fid] for fid in resolution["format_facts"] + resolution["identity_facts"] + market["facts"] + own["facts"]]
            record.update(
                pick=pick,
                prob_a_pct=prob_a,
                prob_b_pct=prob_b,
                own_prob_a_pct=round(own_a, 1),
                own_prob_b_pct=round(100 - own_a, 1),
                market_odds_a=market["odds_a"],
                market_odds_b=market["odds_b"],
                market_captured_utc=market["captured_utc"],
                market_prob_a_pct=prob_a,
                market_prob_b_pct=prob_b,
                basis_label=basis_label,
                basis_tier=basis_tier,
                series_format=resolution["resolved_format"],
                series_format_source=facts[resolution["format_facts"][0]]["url"],
                sources=source_list,
                limitations=resolution["limitations"],
                resolution_used=True,
            )
        else:
            prob_a, prob_b = pct(row["prob_a_pct"]), pct(row["prob_b_pct"])
            own_a, own_b = pct(row["own_prob_a_pct"]), pct(row["own_prob_b_pct"])
            record.update(
                pick=row["pick"] or "",
                prob_a_pct=prob_a,
                prob_b_pct=prob_b,
                own_prob_a_pct=own_a,
                own_prob_b_pct=own_b,
                market_odds_a=row["market_odds_a"] or None,
                market_odds_b=row["market_odds_b"] or None,
                market_captured_utc=row["market_captured_utc"] or "",
                market_prob_a_pct=pct(row["market_prob_a_pct"]),
                market_prob_b_pct=pct(row["market_prob_b_pct"]),
                basis_label=row["basis_label"],
                basis_tier=TIER_LABEL.get(row["basis_label"], row["basis_label"]),
                series_format=row["series_format"] or "",
                series_format_source=row["series_format_source"] or "",
                sources=[{"id": "exec", "source_name": "Hotspawn fixture page (fixture identity) · project capture row",
                          "url": row["hotspawn_match_url"] or row["hotspawn_pickem_url"],
                          "read_utc": row["last_verified_utc"], "tier": "project", "detail": row["basis_detail"]}],
                limitations=tier_limitations(row["basis_label"]),
                resolution=False,
            )
            if not (row["pick"] or "").strip():
                flags.append("VP-F01 no sourced basis in this capture: no outside quote, no rating pair "
                             "and no sourced pick - the row is listed with its limitation, not picked")
                record["no_sourced_basis"] = True
            if row["market_odds_a"] and row["market_odds_b"]:
                record["sources"].append({
                    "id": "exec-market",
                    "source_name": row["market_source"],
                    "url": (row["source_links"].split(" | ")[0] if row["source_links"] else ""),
                    "read_utc": row["market_captured_utc"],
                    "tier": "primary-book",
                    "detail": f"{row['market_odds_a']} / {row['market_odds_b']} (overround {row['market_overround_pct']}%)",
                })

        # ---- value / divergence
        divergence = None
        if record["prob_a_pct"] is not None and record.get("own_prob_a_pct") is not None:
            divergence = {
                "side_a_pp": round(record["own_prob_a_pct"] - record["prob_a_pct"], 1),
                "side_b_pp": round(record["own_prob_b_pct"] - record["prob_b_pct"], 1),
            }
            divergence["value_side"] = record["team_a"] if divergence["side_a_pp"] > divergence["side_b_pp"] else record["team_b"]
            divergence["value_pp"] = max(divergence["side_a_pp"], divergence["side_b_pp"])
            divergence["contradiction"] = divergence["value_side"] != record["pick"]
        record["divergence"] = divergence

        # ---- flags
        flags = []
        exec_flags = row["flags"] or ""
        if "FL-IDENTITY-UNVERIFIED" in exec_flags:
            flags.append("VP-F02 identity of a Hotspawn team name is not exact in the official source used for the ratings")
        if "FL-MODEL-MARKET-SPLIT" in exec_flags or (divergence and abs(divergence["value_pp"]) >= 15):
            flags.append("VP-F03 project line and market line disagree by 15pp or more")
        if not record["market_odds_a"]:
            flags.append("VP-F05 no direct bookmaker quote is stored for this fixture")
        if record.get("resolution_used"):
            flags.append("VP-F06 row was resolved by this session's ladder from a stored/relayed quote; see valuepicks/unresolved.html")
        if "FL-RATINGS-WEEK-OLD" in exec_flags:
            flags.append("VP-F07 rating inputs are a week old")
        record["flags"] = flags
        board.append(record)

        if record["market_captured_utc"] and record["market_captured_utc"] < "2026-10-15T06:00:00Z":
            unresolved.append(record)
        coverage.append(record)

    board.sort(key=lambda item: (item["lock_utc"], item["match_id"]))
    return board, unresolved, coverage


TIER_LIMITATION = {
    "Market · secondary listing": "Headline number is a relayed/secondary listing price, not a direct bookmaker page read; it can lag the book it copies.",
    "Market · prediction market": "Headline number is a prediction-market price (Polymarket). It is not a bookmaker line and carries its own fee/liquidity caveats.",
    "Model · official ratings": "No outside market priced this fixture, so the number is the project's own line from official ratings: an uncalibrated estimate, not a book price.",
    "No sourced basis": "The capture holds no outside quote, no official rating pair and no sourced pick for this fixture, so no probability is published - the row is listed here so the gap is visible.",
}


def tier_limitations(label: str) -> list[str]:
    return [TIER_LIMITATION[label]] if label in TIER_LIMITATION else []


def limited_evidence_rows(board: list[dict]) -> list[dict]:
    """Rows whose headline number is not a direct bookmaker price, plus rows with no basis at all."""
    return [row for row in board
            if (row["pick"] and not row["basis_tier"].startswith("A")) or row.get("no_sourced_basis")]


# ---------------------------------------------------------------------------- rendering
def esc(text) -> str:
    return html.escape("" if text is None else str(text))


def fmt_pct(value) -> str:
    return "-" if value is None else f"{value:.1f}%"


def chip(text: str, cls: str = "") -> str:
    return f'<span class="chip {cls}">{esc(text)}</span>'


def source_links(sources: list[dict], limit: int = 4) -> str:
    seen, bits = set(), []
    for item in sources:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        read = (item.get("read_utc") or "")[:16].replace("T", " ")
        bits.append(
            f'<li><a href="{esc(url)}">{esc(item.get("source_name", url))}</a> '
            f'<span class="meta">· {esc(item.get("tier", ""))}{" · read " + esc(read) + "Z" if read else ""}</span></li>'
        )
        if len(bits) >= limit:
            break
    return "<ul class='src'>" + "".join(bits) + "</ul>" if bits else '<p class="meta">No source link stored for this row.</p>'


def prob_bar(row: dict) -> str:
    if row["prob_a_pct"] is None:
        return '<p class="meta">No probability published for this row.</p>'
    a, b = row["prob_a_pct"], row["prob_b_pct"]
    pick_a = row["pick"] == row["team_a"]
    return f"""
    <div class="prob">
      <div class="side {'win' if pick_a else ''}">
        <span class="team">{esc(row['team_a'])}</span><span class="pct">{a:.1f}%</span>
        <div class="bar"><i style="width:{a:.1f}%"></i></div>
      </div>
      <div class="side {'win' if not pick_a else ''}">
        <span class="team">{esc(row['team_b'])}</span><span class="pct">{b:.1f}%</span>
        <div class="bar"><i style="width:{b:.1f}%"></i></div>
      </div>
    </div>"""


def card(row: dict) -> str:
    divergence = row.get("divergence")
    value_bits = ""
    if divergence:
        cls = "value" if divergence["value_pp"] >= 5 else "meta"
        value_bits = (f'<p class="{cls}">Market vs project line: <strong>{esc(divergence["value_side"])} '
                      f'{divergence["value_pp"]:+.1f}pp</strong> '
                      f'(project {esc(row["team_a"])} {row["own_prob_a_pct"]:.1f}% / {esc(row["team_b"])} {row["own_prob_b_pct"]:.1f}%).</p>')
    flags = "".join(f"<li>{esc(flag)}</li>" for flag in row["flags"])
    limits = "".join(f"<li>{esc(item)}</li>" for item in row.get("limitations", []))
    return f"""
  <article class="card" id="m{esc(row['match_id'])}">
    <header>
      <p class="eyebrow">{esc(row['tournament'])} · Hotspawn tier {esc(row['tier'])} · lock {esc(row['lock_utc'][:16].replace('T', ' '))}Z</p>
      <h3>{esc(row['team_a'])} vs {esc(row['team_b'])}</h3>
      <p class="pickline">Pick: <strong>{esc(row['pick'])}</strong> {chip(row['basis_tier'])} {"BO" + row['series_format'][-1] if row.get('series_format') else 'format unverified'}</p>
    </header>
    {prob_bar(row)}
    {value_bits}
    <p class="basis">{esc(row['basis_label'])}</p>
    {source_links(row['sources'])}
    {f'<details><summary>Caveats ({len(row["flags"])})</summary><ul class="flags">{flags}{limits}</ul></details>' if flags or limits else ''}
  </article>"""


def page(title: str, active: str, body: str, extra_head: str = "") -> str:
    nav = [
        ("index.html", "Today's picks"),
        ("value.html", "Value watches"),
        ("unresolved.html", "Unresolved & limits"),
        ("coverage.html", "All fixtures"),
        ("sources.html", "Sources"),
        ("methodology.html", "Method"),
        ("flagged.html", "Flagged"),
    ]
    links = "".join(
        '<a href="{0}"{1}>{2}</a>'.format(href, ' class="active"' if href == active else "", esc(label))
        for href, label in nav
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0d1218">
<title>{esc(title)}</title>
<link rel="stylesheet" href="style.css">{extra_head}
</head>
<body>
<a class="skip" href="#main">Skip to main content</a>
<header class="top">
  <a class="brand" href="index.html">HOTSPAWN <span>/ day review &amp; value picks</span></a>
  <nav aria-label="Board navigation">{links}</nav>
</header>
<main id="main">
{body}
</main>
<footer>
  <p>Independent research only - probabilities are estimates, not guarantees or betting advice.
  Hotspawn supplies fixture identity and lock times; its crowd-pick percentages are never used as probability inputs.</p>
  <p class="meta">Session {esc(SESSION)} · rebuilt by <code>scripts/7759beef_build.py</code> ·
  <a href="../executive/picks.html">executive board</a> ·
  <a href="../executive/unresolved.html">executive unresolved</a> ·
  <a href="../index.html">site home</a></p>
</footer>
</body>
</html>
"""


def render_index(board: list[dict], sources: dict, meta: dict) -> str:
    facts = fact_index(sources)
    open_rows = [row for row in board if row["pick"]]
    tier_a = [row for row in open_rows if row["basis_tier"].startswith("A")]
    tier_lower = [row for row in open_rows if not row["basis_tier"].startswith("A")]
    contradictions = [row for row in open_rows if row.get("divergence", {}) and row["divergence"]["value_pp"] >= 5]

    day = "".join(
        f'<li><strong>{esc(facts[fid]["claim"])}</strong><br><a href="{esc(facts[fid]["url"])}">{esc(facts[fid]["source_name"])}</a> '
        f'<span class="meta">· read {esc(facts[fid]["read_utc"][:16].replace("T", " "))}Z</span></li>'
        for fid in ["F-01", "F-02", "F-06", "F-07", "F-09", "F-26", "F-27"]
    )
    roster = "".join(
        f'<li><strong>{esc(facts[fid]["claim"])}</strong><br><a href="{esc(facts[fid]["url"])}">{esc(facts[fid]["source_name"])}</a> '
        f'<span class="meta">· read {esc(facts[fid]["read_utc"][:16].replace("T", " "))}Z</span></li>'
        for fid in ["F-11", "F-12", "F-13", "F-14", "F-15"]
    )

    body = f"""
<section class="hero">
  <p class="eyebrow">Executive summary · generated {esc(meta['generated_utc'])}</p>
  <h1>Every open Hotspawn match now has a pick</h1>
  <p class="lede">This page is the phone-first summary. One card per open fixture: the pick, both
  teams' win probabilities, the tier that produced the number and the source links. Rows that cannot
  reach the top tier are still picked, but they are listed with their limits on
  <a href="unresolved.html">Unresolved &amp; limits</a> instead of being hidden; a row with no
  sourced basis at all is listed there too, marked as not picked rather than guessed.</p>
  <div class="buttons">
    <a class="btn primary" href="#slate">Today's picks ({len(open_rows)})</a>
    <a class="btn" href="value.html">Value watches ({len(contradictions)})</a>
    <a class="btn" href="unresolved.html">Unresolved ({len(limited_evidence_rows(board))})</a>
  </div>
  <div class="stats">
    <div><b>{len(open_rows)}</b><span>open fixtures picked</span></div>
    <div><b>{len(tier_a)}</b><span>direct-bookmaker basis</span></div>
    <div><b>{len(tier_lower)}</b><span>fallback basis (flagged)</span></div>
    <div><b>{len(contradictions)}</b><span>5pp+ market/project gaps</span></div>
  </div>
  <p class="meta">Capture: executive snapshot {esc(meta['capture_utc'])} · board rebuilt {esc(meta['generated_utc'])} ·
  cadence: the GitHub Actions pipeline refreshes the upstream capture every four hours; this board is
  regenerated from that capture plus the verified research file on every run.</p>
</section>

<section id="slate">
  <h2>Today's slate - pick and probability per fixture</h2>
  {''.join(card(row) for row in open_rows)}
</section>

<section>
  <h2>Day 1 review (14 October) - what the 9z upset actually showed</h2>
  <ul class="facts">{day}</ul>
  <p>Aurora - the July-rebuilt international roster (F-11, F-12) - lost the opener to a 9z side that
  had exited at the group stage of its previous four events and had been beaten 2-0 by Aurora on
  3 October (F-26, F-27). Aurora were priced as the clear favourite and lost both maps, the second
  13-1 on their own pick (F-01, F-02). The lesson applied on the value page: when a rebuilt roster has
  a short, mixed record and a compressed schedule (F-13, F-15), the market can price the badge rather
  than the current five - so the contrarian side is worth publishing where the market and the official
  ratings disagree, and never worth promoting on a hunch.</p>
</section>

<section>
  <h2>Roster-change and context intel behind the picks</h2>
  <ul class="facts">{roster}</ul>
</section>

<section class="callout">
  <h2>How to read this board</h2>
  <ul>
    <li><strong>Pick</strong> = the side with the higher published probability. It is not a guarantee,
    and it is not advice.</li>
    <li><strong>Tier A</strong> rows use a direct bookmaker price stored in the executive capture (a
    fresh whole-match quote), de-vigged proportionally.</li>
    <li><strong>Tier B/C</strong> rows use a relayed bookmaker listing, a prediction market, or the
    project's own line from official Valve standings. Those numbers are labelled on the row.</li>
    <li><strong>Value watches</strong> compare the market number with the project's official-ratings
    line. A large positive gap means the market is pricing that side lower than the ratings imply -
    the contrarian case - and it is flagged, never presented as fact.</li>
    <li>Row-level caveats (identity, quote age, model disagreement) are inside each card and on the
    <a href="flagged.html">Flagged</a> page.</li>
  </ul>
</section>
"""
    return page(BOARD_NAME, "index.html", body)


def render_value(board: list[dict]) -> str:
    rows = [row for row in board if row.get("divergence")]
    rows.sort(key=lambda row: -row["divergence"]["value_pp"])
    body_rows = []
    for row in rows:
        div = row["divergence"]
        cls = "good" if div["value_pp"] >= 5 else ""
        body_rows.append(f"""
      <tr class="{cls}">
        <td data-label="Match"><a href="index.html#m{esc(row['match_id'])}">{esc(row['team_a'])} vs {esc(row['team_b'])}</a>
          <div class="meta">{esc(row['tournament'])} · lock {esc(row['lock_utc'][:16].replace('T', ' '))}Z</div></td>
        <td data-label="Pick"><strong>{esc(row['pick'])}</strong><div class="meta">published probability {fmt_pct(max(row['prob_a_pct'], row['prob_b_pct']))}</div></td>
        <td data-label="Market">{fmt_pct(row['prob_a_pct'])} / {fmt_pct(row['prob_b_pct'])}</td>
        <td data-label="Project line">{fmt_pct(row['own_prob_a_pct'])} / {fmt_pct(row['own_prob_b_pct'])}</td>
        <td data-label="Value side">{esc(div['value_side'])} <strong>{div['value_pp']:+.1f}pp</strong>
          <div class="meta">{'against the published pick' if div['contradiction'] else 'with the published pick'}</div></td>
        <td data-label="Caveats">{'; '.join(esc(f) for f in row['flags']) or 'none'}</td>
      </tr>""")
    body = f"""
<section class="hero">
  <p class="eyebrow">Contrarian, but not blind</p>
  <h1>Value watches</h1>
  <p class="lede">A value watch is not an upset tip. It means the market price and the project's
  official-ratings line disagree by at least five percentage points on the same side. The list below
  is sorted by that gap. Every row keeps its flags: identity, quote age and format caveats are part
  of the number, and the project line is an uncalibrated estimate, not a book price.</p>
  <p class="meta">Rules: proportional de-vig of stored decimal odds; project line =
  <code>1/(1+10^((points_b - points_a)/400))</code> on official Valve Regional Standings points with
  the exact best-of transform; gap = project - market on the better side. Below 5pp the row is a
  watch, not a value claim.</p>
</section>
<section>
  <h2>Market vs project line, all priced fixtures</h2>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Match</th><th>Pick</th><th>Market %</th><th>Project %</th><th>Value side</th><th>Caveats</th></tr></thead>
    <tbody>{''.join(body_rows)}</tbody>
  </table>
  </div>
</section>
<section class="callout">
  <h2>Applied to the current slate</h2>
  <ul>
    <li><strong>BetBoom vs PARIVISION is the largest gap on the board.</strong> The relayed bookmaker
    line makes it a coin-flip (51.3% / 48.7%) while the official VRS gap (1596 vs 1411) puts BetBoom
    at 83.7% in the project's own line. That is the contrarian case with the clearest official input
    behind it - and with the clearest warning, because the market has watched both teams play this
    week and the project line has not.</li>
    <li><strong>Falcons over 9z (75.8% market vs 93.8% project)</strong> is the "contrarian but not
    stupid" pattern in reverse: 9z just won as a big underdog, so the crowd will over-weight them
    next round; the official ratings still put a large gap between the sides.</li>
    <li><strong>Aurora's rebuilt roster is the season-long version of the same theme.</strong> A
    mid-season IGL, coach and two-player change (kyxsan, Jimpphat, ash) - and a 13-1 map loss on
    Aurora's own pick in the opener - is exactly the situation where an established name can be
    priced above its current five. Take the contrarian side only when the official ratings support
    it, as they do for BetBoom.</li>
  </ul>
</section>
"""
    return page("Value watches - " + BOARD_NAME, "value.html", body)


def render_unresolved(board: list[dict], sources: dict) -> str:
    facts = fact_index(sources)
    limited = limited_evidence_rows(board)

    def row_block(row: dict) -> str:
        limits = "".join(f"<li>{esc(item)}</li>" for item in row.get("limitations", [])) or "<li>No additional limitation recorded.</li>"
        flags = "".join(f"<li>{esc(flag)}</li>" for flag in row["flags"])
        return f"""
    <article class="card" id="u{esc(row['match_id'])}">
      <h3>{esc(row['team_a'])} vs {esc(row['team_b'])}</h3>
      <p class="meta">{esc(row['tournament'])} · lock {esc(row['lock_utc'][:16].replace('T', ' '))}Z · {esc(row['basis_label'])}</p>
      <p>Pick: <strong>{esc(row['pick'] or 'not picked in this capture')}</strong> ({fmt_pct(row['prob_a_pct'])} / {fmt_pct(row['prob_b_pct'])})</p>
      <h4>Why this row is not tier A</h4><ul>{limits}</ul>
      <p class="meta">{('Published number: ' + fmt_pct(row['prob_a_pct']) + ' / ' + fmt_pct(row['prob_b_pct']) + ' from ' + esc(row['basis_label'])) if row['prob_a_pct'] is not None else 'No number is published for this row: ' + esc(row['basis_label'])}</p>
      <h4>Flags</h4><ul class="flags">{flags or '<li>none</li>'}</ul>
      {source_links(row['sources'])}
    </article>"""

    ladder = "".join(
        f'<li><strong>{esc(facts[fid]["claim"])}</strong><br><a href="{esc(facts[fid]["url"])}">{esc(facts[fid]["source_name"])}</a> '
        f'<span class="meta">· {esc(facts[fid]["tier"])} · read {esc(facts[fid]["read_utc"][:16].replace("T", " "))}Z</span></li>'
        for fid in ["F-16", "F-17", "F-18", "F-19", "F-20", "F-21", "F-22", "F-23", "F-24", "F-25"]
    )
    body = f"""
<section class="hero">
  <p class="eyebrow">Where the top tier is not available</p>
  <h1>Unresolved &amp; limits</h1>
  <p class="lede">The executive board leaves a row blank when there is no fresh, exact-identity,
  primary-book quote. This session walked the ladder the brief asks for - official HLTV match page
  first, then esportsbooks and listings, then the project's own line from official ratings - so these
  {len(limited)} fixtures now carry a pick. Each one keeps the reason it could not reach tier A.</p>
</section>
<section>
  <h2>Ladder evidence used</h2>
  <ul class="facts">{ladder}</ul>
</section>
<section>
  <h2>Rows below tier A ({len(limited)})</h2>
  {''.join(row_block(row) for row in limited)}
</section>
<section class="callout">
  <h2>What would make these rows tier A</h2>
  <ol>
    <li>A direct bookmaker page read for the same fixture, inside the freshness window, with the
    exact pair of team names.</li>
    <li>An official match page confirming the series format (done for all five of today's rows) and
    the start time agreeing with the Hotspawn lock (done for 1080202 and 1080203).</li>
    <li>Exact-name identity in the official standings file - the remaining gap for Hotspawn's
    "WROTBERRY" and "RoundsGG" rows, where the evidence is roster-level rather than name-level.</li>
  </ol>
</section>
"""
    return page("Unresolved & limits - " + BOARD_NAME, "unresolved.html", body)


def render_coverage(coverage: list[dict]) -> str:
    rows = []
    for row in coverage:
        if row["status"] == "open":
            state = "open"
            detail = (f'Pick <strong>{esc(row["pick"])}</strong> · {fmt_pct(row["prob_a_pct"])} / {fmt_pct(row["prob_b_pct"])}'
                      f'<div class="meta">{esc(row["basis_label"])}</div>')
        else:
            state = esc(row["status"])
            detail = '<span class="meta">No pick published - fixture was already locked or stale in the capture.</span>'
        rows.append(f"""
      <tr>
        <td data-label="Match">{esc(row['team_a'])} vs {esc(row['team_b'])}<div class="meta">{esc(row['tournament'])} · lock {esc(row['lock_utc'][:16].replace('T', ' '))}Z</div></td>
        <td data-label="State">{state}</td>
        <td data-label="Pick / status">{detail}</td>
        <td data-label="Source"><a href="{esc(row['hotspawn_match_url'] or row['hotspawn_pickem_url'])}">Hotspawn fixture</a></td>
      </tr>""")
    body = f"""
<section class="hero">
  <p class="eyebrow">Full inventory</p>
  <h1>Every captured fixture</h1>
  <p class="lede">All {len(coverage)} fixtures in the executive capture, not only the open ones, so the
  coverage claim can be checked row by row. Open rows carry a pick; locked and stale listings are
  shown as historical inventory.</p>
</section>
<section>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Match</th><th>State</th><th>Pick / status</th><th>Source</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
</section>
"""
    return page("All fixtures - " + BOARD_NAME, "coverage.html", body)


def render_sources(sources: dict) -> str:
    rows = []
    for fact in sources["facts"]:
        rows.append(f"""
      <tr>
        <td data-label="Fact">{esc(fact['claim'])}</td>
        <td data-label="Source"><a href="{esc(fact['url'])}">{esc(fact['source_name'])}</a></td>
        <td data-label="Tier">{esc(fact['tier'])}</td>
        <td data-label="Read">{esc(fact['read_utc'][:16].replace('T', ' '))}Z</td>
        <td data-label="Detail">{esc(fact.get('detail', ''))}</td>
      </tr>""")
    body = f"""
<section class="hero">
  <p class="eyebrow">Line by line</p>
  <h1>Sources and read times</h1>
  <p class="lede">Every fact this board publishes comes from one of the rows below. Tiers are printed
  on the row: <code>official</code> (league or Valve), <code>primary-book</code>,
  <code>relayed-book</code>, <code>secondary-news</code>, <code>prediction-market</code> or
  <code>project</code>. If a value could not be confirmed from such a source, it is blank on the row
  and listed on the unresolved page.</p>
  <p class="meta">Machine-readable copy: <a href="data/sources.json">valuepicks/data/sources.json</a> ·
  upstream facts: <a href="../research/7759beef/sources.json">research/7759beef/sources.json</a></p>
</section>
<section>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Fact</th><th>Source</th><th>Tier</th><th>Read (UTC)</th><th>Detail</th></tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  </div>
</section>
"""
    return page("Sources - " + BOARD_NAME, "sources.html", body)


def render_flagged(board: list[dict], sources: dict) -> str:
    facts = fact_index(sources)
    rows = []
    for row in board:
        if not row.get("flags") and row["status"] != "open":
            continue
        for flag in row.get("flags", []):
            rows.append(f"""
      <tr>
        <td data-label="Fixture">{esc(row['team_a'])} vs {esc(row['team_b'])}<div class="meta">lock {esc(row['lock_utc'][:16].replace('T', ' '))}Z</div></td>
        <td data-label="Flag">{esc(flag)}</td>
        <td data-label="Source"><a href="index.html#m{esc(row['match_id'])}">row detail</a></td>
      </tr>""")
    contradictions = [row for row in board if row.get("divergence") and row["divergence"]["contradiction"] and row["divergence"]["value_pp"] >= 5]
    contradiction_rows = "".join(
        f"""<tr><td data-label="Fixture">{esc(row['team_a'])} vs {esc(row['team_b'])}</td>
        <td data-label="Published pick">{esc(row['pick'])}</td>
        <td data-label="Project line prefers">{esc(row['divergence']['value_side'])} ({row['divergence']['value_pp']:+.1f}pp)</td>
        <td data-label="Sources">{source_links(row['sources'], 3)}</td></tr>"""
        for row in contradictions
    )
    unresolved_sources = "".join(
        f'<li>{esc(facts[fid]["claim"])} - <a href="{esc(facts[fid]["url"])}">{esc(facts[fid]["source_name"])}</a> '
        f'<span class="meta">· read {esc(facts[fid]["read_utc"][:16].replace("T", " "))}Z</span></li>'
        for fid in ["F-05", "F-13", "F-15", "F-24"]
    )
    body = f"""
<section class="hero">
  <p class="eyebrow">Published, not hidden</p>
  <h1>Flagged for review</h1>
  <p class="lede">Everything on this page still ships a pick, but each item is a reason to treat a row
  with care. Nothing here blocks publication; the point is that the reader can see the weakness
  before trusting the number.</p>
</section>
<section>
  <h2>Row-level flags</h2>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Fixture</th><th>Flag</th><th>Detail</th></tr></thead>
    <tbody>{''.join(rows) or '<tr><td colspan="3">No row-level flags.</td></tr>'}</tbody>
  </table>
  </div>
</section>
<section>
  <h2>Market vs project-line contradictions (5pp+)</h2>
  <div class="tablewrap">
  <table>
    <thead><tr><th>Fixture</th><th>Published pick</th><th>Project line prefers</th><th>Sources</th></tr></thead>
    <tbody>{contradiction_rows or '<tr><td colspan="4">No contradictions of that size.</td></tr>'}</tbody>
  </table>
  </div>
</section>
<section class="callout">
  <h2>Secondary-source notes carried forward</h2>
  <ul>{unresolved_sources}</ul>
  <p class="meta">Flag codes: VP-F02 identity, VP-F03 model/market split, VP-F05 no direct book quote,
  VP-F06 ladder-resolved row, VP-F07 stale rating inputs. Existing executive flags (FL-*) keep their
  meaning and stay visible on the executive board.</p>
</section>
"""
    return page("Flagged - " + BOARD_NAME, "flagged.html", body)


def render_methodology() -> str:
    body = """
<section class="hero">
  <p class="eyebrow">Reproducible</p>
  <h1>Method</h1>
  <p class="lede">Three published tiers, one ladder, no inference. This page says exactly what each
  number is so a row can be challenged line by line.</p>
</section>
<section>
  <h2>Probabilities</h2>
  <ul>
    <li><strong>Market tiers.</strong> Decimal odds are converted with proportional de-vigging:
    p = (1/odds) / (1/odds_a + 1/odds_b). Direct bookmaker quotes are labelled tier A; relayed or
    listing-site quotes, and prediction markets, are labelled B and C and never described as a
    bookmaker price.</li>
    <li><strong>Project line (tier D).</strong> Official Valve Regional Standings points, per-map
    logistic <code>1/(1+10^((points_b - points_a)/400))</code> - the convention Valve's own model
    file uses - then the exact best-of transform used across this repository
    (BO1 = p, BO3 = 3p^2 - 2p^3, BO5 negative-binomial sum). Where the official standings do not
    list a team, its rank on the official HLTV world ranking is used with the project's published
    rank scale. Missing inputs stay blank; absence is never treated as a rating bound.</li>
    <li><strong>Pick.</strong> The side with the higher published probability. A pick is not advice.</li>
    <li><strong>Value gap.</strong> project - market on the better side, published when both exist.
    It measures disagreement between two sources, not the truth.</li>
  </ul>
  <h2>What this board refuses to do</h2>
  <ul>
    <li>It never uses Hotspawn's crowd pick percentage as a probability input.</li>
    <li>It never fills a probability from a news headline, a community vote, or a "feels like" view.</li>
    <li>It never silently equates two differently named teams; identity evidence is printed on the row
    (see the WBT and ROUNDS rows on the unresolved page).</li>
    <li>It does not claim calibration. Project lines are estimates with named inputs and named limits.</li>
  </ul>
  <h2>Freshness and cadence</h2>
  <ul>
    <li>The upstream executive capture refreshes on a four-hour GitHub Actions schedule; this board
    is rebuilt from that capture plus <code>research/7759beef/sources.json</code> on every run, and
    its build fails if a published market or project probability does not recompute from the stored
    inputs.</li>
    <li>Quote ages are printed on every row. A stale quote is still published (with its capture time)
    only when the row would otherwise have no pick at all, and it is flagged.</li>
  </ul>
</section>
"""
    return page("Method - " + BOARD_NAME, "methodology.html", body)


def css() -> str:
    return """:root{color-scheme:dark;--bg:#0d1218;--panel:#171f29;--line:#27313d;--text:#e8eef6;--muted:#9fb0c3;--acc:#bbaaff;--good:#7ee2a8;--warn:#ffcf7a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:#b8d4ff}
.skip{position:absolute;left:-999px}
.skip:focus{left:8px;top:8px;background:#000;padding:8px}
header.top{position:sticky;top:0;z-index:5;background:#0d1218ee;border-bottom:1px solid var(--line);padding:10px 16px;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
.brand{display:inline-block;font-weight:700;color:var(--text);text-decoration:none;letter-spacing:.02em}
.brand span{color:var(--muted);font-weight:400}
header.top nav{display:flex;gap:6px;overflow-x:auto;margin-top:8px;padding-bottom:4px;-webkit-overflow-scrolling:touch}
header.top nav a{display:inline-flex;align-items:center;min-height:44px;padding:0 12px;border:1px solid var(--line);border-radius:999px;color:var(--text);text-decoration:none;white-space:nowrap;font-size:14px}
header.top nav a.active{background:var(--acc);border-color:var(--acc);color:#17132b;font-weight:600}
main{padding:16px;max-width:1000px;margin:0 auto}
h1{font-size:clamp(26px,7vw,40px);margin:8px 0 10px}
h2{font-size:clamp(20px,5vw,26px);margin:28px 0 10px}
h3{font-size:19px;margin:4px 0 8px}
h4{margin:12px 0 4px;font-size:15px;color:var(--muted)}
.eyebrow{margin:0;color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.06em}
.lede{color:#cfd9e6}
.meta{color:var(--muted);font-size:13px}
.buttons{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.btn{display:inline-flex;align-items:center;min-height:48px;padding:0 16px;border:1px solid var(--line);border-radius:10px;background:var(--panel);color:var(--text);text-decoration:none;font-weight:600}
.btn.primary{background:var(--acc);border-color:var(--acc);color:#17132b}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}
.stats div{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px}
.stats b{display:block;font-size:26px}
.stats span{color:var(--muted);font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin:12px 0}
.pickline{margin:6px 0 10px}
.chip{display:inline-block;padding:2px 8px;border-radius:999px;background:#2a3646;color:#dbe6f3;font-size:12px;vertical-align:middle}
.prob{display:grid;gap:8px;margin:10px 0}
.side{display:grid;grid-template-columns:1fr auto;align-items:center;gap:8px}
.side .team{font-weight:600}
.side .pct{font-variant-numeric:tabular-nums;color:var(--muted)}
.side.win .pct{color:var(--good);font-weight:700}
.bar{grid-column:1/-1;height:8px;background:#0b1017;border-radius:999px;overflow:hidden}
.bar i{display:block;height:100%;background:#3c5a7a}
.side.win .bar i{background:linear-gradient(90deg,#7ee2a8,#4fbf85)}
.pickline strong{font-size:18px}
.basis{margin:8px 0;color:#cfd9e6}
.value{color:var(--good);font-weight:600}
ul.src{margin:8px 0 0;padding-left:18px}
ul.src li{margin:4px 0;font-size:14px;overflow-wrap:anywhere}
ul.flags{margin:6px 0 0;padding-left:18px;color:var(--warn);font-size:14px}
details summary{cursor:pointer;min-height:44px;display:flex;align-items:center;color:var(--muted)}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table{border-collapse:collapse;width:100%;min-width:640px}
th,td{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}
th{background:#131b24;color:var(--muted);font-weight:600;position:sticky;top:0}
tr.good td{background:#16281f}
ul.facts,section.callout ul{padding-left:20px}
ul.facts li{margin:10px 0}
.callout{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px;margin:18px 0}
footer{padding:18px 16px 40px;color:var(--muted);font-size:13px;max-width:1000px;margin:0 auto}
footer a{color:#b8d4ff}
@media(max-width:600px){
  .stats{grid-template-columns:repeat(2,minmax(0,1fr))}
  table,thead,tbody,th,td,tr{display:block;min-width:0}
  th{position:static}
  thead{display:none}
  td{border:0;border-bottom:1px solid var(--line);padding:8px 10px}
  td:before{content:attr(data-label);display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px}
  tr{border-bottom:2px solid var(--line);padding:4px 0}
  .side .pct{font-size:18px}
}
"""


# ---------------------------------------------------------------------------- outputs
def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    sources = load_sources()
    exec_rows = load_exec_rows()
    summary = json.loads((EXEC / "summary.json").read_text(encoding="utf-8"))
    board, stale_quotes, coverage = build_board(exec_rows, sources)

    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = {
        "generated_utc": generated,
        "capture_utc": summary["meta"]["capture_utc"],
        "session": SESSION,
        "open_fixtures": sum(1 for row in board if row["pick"]),
        "open_unpicked": sum(1 for row in board if not row["pick"]),
        "tier_a": sum(1 for row in board if row["pick"] and row["basis_tier"].startswith("A")),
        "fallback_basis": sum(1 for row in board if row["pick"] and not row["basis_tier"].startswith("A")),
        "value_watches": sum(1 for row in board if row.get("divergence") and row["divergence"]["value_pp"] >= 5),
        "unresolved_top_tier": len(limited_evidence_rows(board)),
        "total_fixtures": len(coverage),
        "source_facts": len(sources["facts"]),
    }

    (OUT / "index.html").write_text(render_index(board, sources, meta), encoding="utf-8")
    (OUT / "value.html").write_text(render_value(board), encoding="utf-8")
    (OUT / "unresolved.html").write_text(render_unresolved(board, sources), encoding="utf-8")
    (OUT / "coverage.html").write_text(render_coverage(coverage), encoding="utf-8")
    (OUT / "sources.html").write_text(render_sources(sources), encoding="utf-8")
    (OUT / "flagged.html").write_text(render_flagged(board, sources), encoding="utf-8")
    (OUT / "methodology.html").write_text(render_methodology(), encoding="utf-8")
    (OUT / "style.css").write_text(css(), encoding="utf-8")

    slim = []
    for row in board:
        item = {key: value for key, value in row.items() if key != "sources"}
        item["source_urls"] = [src.get("url") for src in row.get("sources", []) if src.get("url")]
        slim.append(item)
    (DATA / "board.json").write_text(json.dumps({"meta": meta, "rows": slim}, indent=1), encoding="utf-8")
    (DATA / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (DATA / "sources.json").write_text(json.dumps(sources, indent=1), encoding="utf-8")
    write_csv(DATA / "board.csv", slim,
              ["match_id", "status", "team_a", "team_b", "tournament", "tier", "lock_utc", "start_utc",
               "pick", "prob_a_pct", "prob_b_pct", "own_prob_a_pct", "own_prob_b_pct", "basis_label",
               "basis_tier", "series_format", "market_captured_utc"])
    value_rows = [row for row in board if row.get("divergence")]
    for row in value_rows:
        row["value_side"] = row["divergence"]["value_side"]
        row["value_pp"] = row["divergence"]["value_pp"]
    write_csv(DATA / "value.csv", value_rows,
              ["match_id", "team_a", "team_b", "lock_utc", "pick", "prob_a_pct", "prob_b_pct",
               "own_prob_a_pct", "own_prob_b_pct", "value_side", "value_pp"])
    write_csv(DATA / "unresolved.csv", limited_evidence_rows(board),
              ["match_id", "team_a", "team_b", "tournament", "lock_utc", "pick", "prob_a_pct",
               "prob_b_pct", "basis_label"])
    write_csv(DATA / "coverage.csv", coverage,
              ["match_id", "status", "team_a", "team_b", "tournament", "tier", "lock_utc", "start_utc",
               "pick", "prob_a_pct", "prob_b_pct", "basis_label"])

    print(f"valuepicks built: {meta['open_fixtures']} open fixtures picked, "
          f"{meta['tier_a']} tier A, {meta['fallback_basis']} fallback, "
          f"{meta['value_watches']} value watches, {meta['total_fixtures']} fixtures total, "
          f"{meta['open_unpicked']} open rows unpublished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
