#!/usr/bin/env python3
"""Build the arena/cc8f4dca picks dashboard.

Reads only committed, timestamped source data under ``picks/data/`` plus the HLTV ranking
snapshot already in the repository, and writes ``picks/*.html``, ``picks/data/matches.csv``
and ``picks/data/matches.json``.

Rules enforced here (re-checked by scripts/verify_picks.py):
  * Hotspawn supplies fixture identity only. ``picked_percent`` is never read as a probability.
  * Every published number is computed from a value present in a fetched source file.
    A value that cannot be matched is left blank and published on the Flagged page.
  * Market probability comes from external bookmaker moneyline odds (de-vigged).
  * Our own line comes from Valve's official Regional Standings through a calibrated logistic.
"""

from __future__ import annotations

import csv
import html as html_lib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "picks" / "data"
OUT = ROOT / "picks"
ASSETS = OUT / "assets"

# ---------------------------------------------------------------------------
# Model constants
# ---------------------------------------------------------------------------
# P(win) = 1 / (1 + 10 ** (-K * (pts_a - pts_b) / 400))
#   K = 0.4568 — maximum-likelihood slope fitted on 6,765 match results that Valve publishes in
#   its own standings repository, always using a rating snapshot that predates the match.
#   Valve's raw curve is K = g(rd = 75) = 0.972821, which Valve's README calls "shallower than
#   we'd like". Held-out 2026-08-03..2026-10-05: log loss 0.66185 -> 0.64351,
#   Brier 0.22936 -> 0.22575. Fit and diagnostics: model/input/vrs/calibration.json
#   (session arena/91eff436). scripts/verify_picks.py re-checks the numbers against that file.
K_MODEL = 0.4568
K_VALVE_RAW = 0.972821
VRS_BLOB_URL = (
    "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/"
    "live/2026/standings_global_2026_10_05.md"
)
HOTSPawn_URL = "https://play.hotspawn.com/cs2-pickems"

# ---------------------------------------------------------------------------
# Team-name resolution. Every non-identity mapping carries its evidence.
# ---------------------------------------------------------------------------
# hotspawn name (normalised) -> VRS name (normalised), with the evidence link and confidence.
ALIASES: dict[str, dict[str, str]] = {
    "wrotberry": {
        "vrs": "wbt",
        "why": "EGamersWorld's own team page for this roster is /counterstrike/team/wrotberry-... "
               "and is displayed as WBT; the WBT roster in Valve's file (DemQQ, Psycho, "
               "s4ltovsk1yy, Smash, tyr1k) is exactly the five EGamersWorld lists.",
        "source": "https://egamersworld.com/counterstrike/team/wrotberry-0I2cpR8LZA",
        "confidence": "confirmed (roster)",
    },
    "envy": {
        "vrs": "3dmax",
        "why": "HLTV reported on 29-9-2026 that Envy signed the ex-3DMAX roster; HLTV's Envy team "
               "page lists Maka, Lucky, misutaaa, Kursy and Graviti, the same five as row 21 "
               "'3DMAX' in Valve's 2026-10-05 file.",
        "source": "https://www.hltv.org/news/45594/envy-return-to-cs-with-ex-3dmax-roster",
        "confidence": "confirmed (roster)",
    },
    "roundsgg": {
        "vrs": "rounds",
        "why": "EGamersWorld displays the team as 'Rounds' with the logo file roundsgg-logo.webp, "
               "in the same event at the same UTC start time.",
        "source": "https://egamersworld.com/counterstrike/match/4yn491uUVl/havu-vs-rounds-rg48QwsiJ9",
        "confidence": "confirmed (logo filename + event/time)",
    },
    "ninjas in pyjamas": {"vrs": "ninjas in pyjamas", "why": "", "source": "", "confidence": "exact"},
    "betboom": {"vrs": "betboom", "why": "", "source": "", "confidence": "exact"},
}

# Names that are deliberately NOT resolved to a rating. Left blank, never guessed.
UNRESOLVED: dict[str, str] = {
    "zomblers": "Two different 'Zomblers' rosters exist in Valve's 2026-10-05 file "
                "(rank 254: CAJUN, CoolComs, FxRE, man327, Pose1doNN; rank 259: CAJUN, CoolComs, "
                "FxRE, Pose1doNN, Zoker). Which one Hotspawn means is not verifiable here, so no "
                "own line is produced.",
    "ex rustec": "Two different 'ex-RUSTEC' rosters exist in Valve's file (rank 92 and rank 152). "
                 "Not verifiable here, so no own line is produced.",
    "lfo 10": "Valve's file has 'LFO 7', 'LFO 8' and 'LFO 9' but no 'LFO 10'. No match, so no own "
              "line is produced.",
    "eac": "Not present in Valve's 2026-10-05 file. EGamersWorld calls this side 'EA Copenhagen' "
           "in the same event at the same time, but no rating row can be confirmed, so no own "
           "line is produced.",
}

# Teams whose VRS row is taken on name alone (flagged for review, never presented as confirmed).
NEEDS_REVIEW_TEAMS = {
    "phantom": "Valve's file has 'Phantom' (rank 72) and 'Phantom Academy' (rank 172). The "
               "non-academy row is used, but its roster has not been cross-checked against the "
               "Polish organisation EGamersWorld calls 'Phantom Esports'.",
    "havu": "Name match only; roster not cross-checked.",
    "voca": "Name match only; roster not cross-checked.",
    "bojong": "Name match only; roster not cross-checked.",
    "wbt": "Roster confirmed against EGamersWorld.",
}


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def esc(value) -> str:
    return html_lib.escape("" if value is None else str(value), quote=True)


def iso_utc(ms) -> str:
    try:
        value = int(ms)
    except (TypeError, ValueError):
        return ""
    if value > 10_000_000_000:
        value //= 1000
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%d %H:%M")


def parse_utc(text: str):
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalise(name: str | None) -> str:
    if not name:
        return ""
    value = name.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def no_vig(odds_a, odds_b):
    if not odds_a or not odds_b or odds_a <= 1 or odds_b <= 1:
        return None, None, None
    raw_a, raw_b = 1.0 / odds_a, 1.0 / odds_b
    total = raw_a + raw_b
    return raw_a / total, raw_b / total, total - 1.0


def vrs_probability(points_a, points_b):
    if points_a is None or points_b is None:
        return None
    return 1.0 / (1.0 + 10.0 ** (-(K_MODEL * (points_a - points_b)) / 400.0))


def pct(value, digits: int = 1) -> str:
    return "" if value is None else f"{value * 100:.{digits}f}%"


def confidence_band(probability) -> str:
    if probability is None:
        return "no line"
    edge = abs(probability - 0.5)
    if edge >= 0.25:
        return "strong"
    if edge >= 0.12:
        return "clear"
    if edge >= 0.04:
        return "lean"
    return "toss-up"


FLAG_TEXT = {
    "CC-01": "No external bookmaker moneyline was found for this pairing. The market column is blank.",
    "CC-02": "No own line: at least one side could not be resolved to a row in Valve's official standings.",
    "CC-03": "Neither a market line nor an own line could be produced, so no pick is published.",
    "CC-04": "The market line and our own model disagree on the favourite. Both are shown; the pick follows the market.",
    "CC-05": "A team-name mapping was used to match the external source. Evidence is linked on the row.",
    "CC-06": "This fixture's lock time is in the past at the snapshot time. The row is historical, not actionable.",
    "CC-07": "An external price was found but it is the source's placeholder default, not a real market price.",
    "CC-08": "Team identity taken from Valve's standings on name alone; roster not cross-checked.",
}


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def main() -> int:
    fixtures_doc = load_json(DATA / "fixtures.json", {}) or {}
    vrs_doc = load_json(DATA / "vrs.json", {}) or {}
    egw_doc = load_json(DATA / "odds_egamersworld.json", {}) or {}
    pinnacle_doc = load_json(DATA / "odds_pinnacle.json", {}) or {}
    hltv_doc = load_json(ROOT / "model" / "input" / "hltv_ranking.json", {}) or {}

    raw_fixtures = fixtures_doc.get("fixtures") or {}
    pages = fixtures_doc.get("pages") or []
    hotspawn_fetched = pages[0].get("fetched_utc") if pages else None

    vrs_by_name = {}
    for team in vrs_doc.get("teams") or []:
        vrs_by_name[normalise(team.get("name"))] = team

    hltv_by_name = {}
    for team in hltv_doc.get("teams") or []:
        hltv_by_name[normalise(team.get("name"))] = team

    # External bookmaker lines, keyed by Hotspawn fixture id where the source gives it,
    # otherwise by normalised team pair.
    egw_rows = {str(m.get("fixture_id")): m for m in egw_doc.get("matches") or []}
    egw_identity = {normalise(i["hotspawn_name"]): i for i in egw_doc.get("identity_evidence") or []}

    pinnacle_index = {}
    for entry in pinnacle_doc.get("matchups") or []:
        if not entry.get("home_name") or not entry.get("away_name"):
            continue
        pinnacle_index[frozenset({normalise(entry["home_name"]), normalise(entry["away_name"])})] = entry

    # Snapshot time = latest of the source captures; used for "as of" and staleness.
    snapshot_utc = egw_doc.get("captured_utc") or hotspawn_fetched or "unknown"
    # Whether a pick is still playable is judged at render time.
    snapshot_dt = datetime.now(timezone.utc)

    rows = []
    for fixture_id, fixture in sorted(raw_fixtures.items()):
        sport = (fixture.get("sport_alias") or "").lower()
        sport_name = (fixture.get("sport_name") or "").lower()
        if sport not in ("cs2", "csgo") and "counter-strike" not in sport_name:
            continue

        team_a = fixture.get("participants0_name")
        team_b = fixture.get("participants1_name")
        lock_dt = parse_utc(iso_utc(fixture.get("lock_time")))
        start_dt = parse_utc(iso_utc(fixture.get("scheduled_start_time")))

        flags: list[str] = []
        notes: list[str] = []
        evidence: list[dict[str, str]] = [
            {
                "label": "Hotspawn fixture",
                "url": HOTSPawn_URL,
            }
        ]

        # ---- external bookmaker line -------------------------------------
        market = egw_rows.get(str(fixture_id))
        market_odds_a = market_odds_b = None
        market_url = market_book = market_captured = None
        market_p_a = market_p_b = overround = None
        if market and market.get("status") == "priced":
            odds_a, odds_b = market.get("odds_a"), market.get("odds_b")
            # The source lists the sides in its own order; realign to the Hotspawn order.
            if normalise(market.get("team_a")) != normalise(team_a) and normalise(
                market.get("team_b")
            ) == normalise(team_a):
                odds_a, odds_b = odds_b, odds_a
            elif normalise(market.get("team_a")) != normalise(team_a):
                # Names differ (alias). Resolve through the identity table before trusting order.
                mapped_a = egw_identity.get(normalise(team_a), {}).get("source_name", "")
                if normalise(mapped_a) != normalise(market.get("team_a")):
                    odds_a, odds_b = odds_b, odds_a
            p_a, p_b, overround = no_vig(odds_a, odds_b)
            market_odds_a, market_odds_b = odds_a, odds_b
            market_p_a, market_p_b = p_a, p_b
            market_url = market.get("source_url")
            market_book = "EGamersWorld aggregated bookmaker moneyline"
            market_captured = egw_doc.get("captured_utc")
            evidence.append({"label": "Bookmaker line (EGamersWorld)", "url": market_url})
        elif market and market.get("status") == "placeholder":
            flags.append("CC-07")
            notes.append(FLAG_TEXT["CC-07"])
            evidence.append({"label": "EGamersWorld page (placeholder price)", "url": market.get("source_url")})
        else:
            flags.append("CC-01")
            notes.append(FLAG_TEXT["CC-01"])

        # ---- own line from Valve's official standings ---------------------
        def resolve(team_name):
            key = normalise(team_name)
            if key in UNRESOLVED:
                return None, UNRESOLVED[key], None
            alias = ALIASES.get(key)
            lookup = alias["vrs"] if alias else key
            row = vrs_by_name.get(lookup)
            if row is None:
                return None, f"Not present in Valve's 2026-10-05 global standings under the name " \
                             f"'{team_name}'. No rating, so no own line.", alias
            return row, None, alias

        vrs_a, reason_a, alias_a = resolve(team_a)
        vrs_b, reason_b, alias_b = resolve(team_b)
        own_p_a = vrs_probability(
            vrs_a["points"] if vrs_a else None, vrs_b["points"] if vrs_b else None
        )
        own_p_b = None if own_p_a is None else 1 - own_p_a
        if own_p_a is None:
            flags.append("CC-02")
            for reason in (reason_a, reason_b):
                if reason:
                    notes.append(reason)
        if vrs_a and vrs_b:
            evidence.append({"label": "Valve Regional Standings (both teams)", "url": VRS_BLOB_URL})
        for name in (team_a, team_b):
            alias = ALIASES.get(normalise(name))
            if alias and alias.get("why"):
                flags.append("CC-05")
                notes.append(f"{name}: {alias['why']}")
                evidence.append({"label": f"Identity evidence — {name}", "url": alias["source"]})
            review = NEEDS_REVIEW_TEAMS.get(normalise(name))
            if review and "not cross-checked" in review:
                flags.append("CC-08")
                notes.append(f"{name}: {review}")

        # ---- pick --------------------------------------------------------
        final_a = market_p_a if market_p_a is not None else own_p_a
        final_b = market_p_b if market_p_b is not None else own_p_b
        source_used = "market" if market_p_a is not None else ("own model" if own_p_a is not None else "none")
        if final_a is not None:
            pick = team_a if final_a >= 0.5 else team_b
        else:
            pick = None
            flags.append("CC-03")
            notes.append(FLAG_TEXT["CC-03"])

        if market_p_a is not None and own_p_a is not None and (market_p_a - 0.5) * (own_p_a - 0.5) < 0:
            flags.append("CC-04")
            notes.append(FLAG_TEXT["CC-04"])

        actionable = bool(lock_dt and lock_dt > snapshot_dt)
        if lock_dt and lock_dt <= snapshot_dt:
            flags.append("CC-06")
            notes.append(FLAG_TEXT["CC-06"])

        hltv_a = hltv_by_name.get(normalise(team_a))
        hltv_b = hltv_by_name.get(normalise(team_b))

        rows.append(
            {
                "id": fixture_id,
                "competition": fixture.get("competition_name"),
                "tier": (fixture.get("tier") or "").upper(),
                "team_a": team_a,
                "team_b": team_b,
                "start_utc": start_dt.strftime("%Y-%m-%d %H:%M") if start_dt else "",
                "lock_utc": lock_dt.strftime("%Y-%m-%d %H:%M") if lock_dt else "",
                "lock_dt": lock_dt,
                "actionable": actionable,
                "market_odds_a": market_odds_a,
                "market_odds_b": market_odds_b,
                "market_p_a": market_p_a,
                "market_p_b": market_p_b,
                "market_overround": overround,
                "market_book": market_book,
                "market_url": market_url,
                "market_captured": market_captured,
                "vrs_a": vrs_a["points"] if vrs_a else None,
                "vrs_b": vrs_b["points"] if vrs_b else None,
                "vrs_a_rank": vrs_a["rank"] if vrs_a else None,
                "vrs_b_rank": vrs_b["rank"] if vrs_b else None,
                "hltv_a": hltv_a.get("rank") if hltv_a else None,
                "hltv_b": hltv_b.get("rank") if hltv_b else None,
                "hltv_a_url": f"https://www.hltv.org/team/{hltv_a['team_id']}/{hltv_a['slug']}" if hltv_a else None,
                "hltv_b_url": f"https://www.hltv.org/team/{hltv_b['team_id']}/{hltv_b['slug']}" if hltv_b else None,
                "own_p_a": own_p_a,
                "own_p_b": own_p_b,
                "final_p_a": final_a,
                "final_p_b": final_b,
                "source_used": source_used,
                "pick": pick,
                "confidence": confidence_band(final_a),
                "flags": sorted(set(flags)),
                "notes": notes,
                "evidence": evidence,
            }
        )

    rows.sort(
        key=lambda r: (
            not r["actionable"],
            r["lock_dt"] or datetime.max.replace(tzinfo=timezone.utc),
            r["competition"] or "",
        )
    )
    active = [r for r in rows if r["actionable"]]
    stale = [r for r in rows if not r["actionable"]]

    write_csv(rows)
    write_json(rows, snapshot_utc, hotspawn_fetched)
    write_css()
    write_js()
    write_index(rows, active, stale, snapshot_utc, hotspawn_fetched, egw_doc, vrs_doc, hltv_doc)
    write_methodology(snapshot_utc)
    write_sources(egw_doc, vrs_doc, hltv_doc, fixtures_doc, pinnacle_doc, snapshot_utc)
    write_flagged(rows, snapshot_utc)

    print(f"actionable fixtures: {len(active)}   other CS2 rows: {len(stale)}")
    print(f"market lines: {sum(1 for r in active if r['market_p_a'] is not None)}"
          f"   own lines: {sum(1 for r in active if r['own_p_a'] is not None)}"
          f"   picks: {sum(1 for r in active if r['pick'])}")
    return 0


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "match_id", "tournament", "tier", "lock_utc", "start_utc", "actionable",
    "team_a", "team_b",
    "market_odds_a", "market_odds_b", "market_prob_a", "market_prob_b", "market_overround",
    "market_bookmaker", "market_source_url", "market_captured_utc",
    "vrs_points_a", "vrs_points_b", "vrs_rank_a", "vrs_rank_b", "valve_source_url",
    "hltv_rank_a", "hltv_rank_b", "hltv_source_url_a", "hltv_source_url_b",
    "own_prob_a", "own_prob_b", "published_prob_a", "published_prob_b",
    "probability_source", "pick", "confidence", "flags", "notes",
]


def write_csv(rows):
    path = DATA / "matches.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(CSV_COLUMNS)
        for row in rows:
            writer.writerow([
                row["id"], row["competition"], row["tier"], row["lock_utc"], row["start_utc"],
                "yes" if row["actionable"] else "no",
                row["team_a"], row["team_b"],
                "" if row["market_odds_a"] is None else f"{row['market_odds_a']:g}",
                "" if row["market_odds_b"] is None else f"{row['market_odds_b']:g}",
                "" if row["market_p_a"] is None else f"{row['market_p_a'] * 100:.1f}%",
                "" if row["market_p_b"] is None else f"{row['market_p_b'] * 100:.1f}%",
                "" if row["market_overround"] is None else f"{row['market_overround'] * 100:.2f}%",
                row["market_book"] or "", row["market_url"] or "", row["market_captured"] or "",
                row["vrs_a"] if row["vrs_a"] is not None else "",
                row["vrs_b"] if row["vrs_b"] is not None else "",
                row["vrs_a_rank"] or "", row["vrs_b_rank"] or "",
                VRS_BLOB_URL if (row["vrs_a"] and row["vrs_b"]) else "",
                row["hltv_a"] or "", row["hltv_b"] or "",
                row["hltv_a_url"] or "", row["hltv_b_url"] or "",
                "" if row["own_p_a"] is None else f"{row['own_p_a'] * 100:.1f}%",
                "" if row["own_p_b"] is None else f"{row['own_p_b'] * 100:.1f}%",
                "" if row["final_p_a"] is None else f"{row['final_p_a'] * 100:.1f}%",
                "" if row["final_p_b"] is None else f"{row['final_p_b'] * 100:.1f}%",
                row["source_used"], row["pick"] or "", row["confidence"],
                ";".join(row["flags"]), " | ".join(row["notes"]),
            ])


def write_json(rows, snapshot_utc, hotspawn_fetched):
    payload = {
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "snapshot_utc": snapshot_utc,
        "hotspawn_fetched_utc": hotspawn_fetched,
        "model": {
            "formula": "P(win) = 1 / (1 + 10 ** (-K * (points_a - points_b) / 400))",
            "K": K_MODEL,
            "valve_raw_K": K_VALVE_RAW,
            "rating_source": VRS_BLOB_URL,
            "calibration_source": "model/input/vrs/calibration.json",
        },
        "matches": [
            {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}
            for row in rows
        ],
    }
    (DATA / "matches.json").write_text(json.dumps(payload, indent=2))


def nav(active_page: str) -> str:
    pages = [
        ("index.html", "Picks"),
        ("methodology.html", "Method"),
        ("sources.html", "Sources"),
        ("flagged.html", "Flagged"),
    ]
    return "".join(
        f'<a class="nav-link{" is-active" if name == active_page else ""}" href="{name}">{esc(label)}</a>'
        for name, label in pages
    )


def page(title: str, heading: str, body: str, active_page: str, subtitle: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="stylesheet" href="assets/picks.css">
</head>
<body>
<header class="site-header">
  <div class="wrap">
    <div class="brand">
      <span class="brand-mark">HS</span>
      <span class="brand-text"><strong>Hotspawn CS2 Pick'em</strong><span>independent win probabilities</span></span>
    </div>
    <nav class="nav">{nav(active_page)}</nav>
  </div>
</header>
<main class="wrap">
  <h1>{esc(heading)}</h1>
  {f'<p class="subtitle">{subtitle}</p>' if subtitle else ''}
  {body}
</main>
<footer class="site-footer">
  <div class="wrap">
    <p>Analysis only — not betting advice. Probabilities never use Hotspawn's crowd pick percentages;
       Hotspawn is used only to list the fixtures. Anything that cannot be confirmed from a linked
       source is left blank and listed on the <a href="flagged.html">Flagged for Review</a> page.</p>
  </div>
</footer>
</body>
</html>
"""


def match_card(row: dict) -> str:
    p_a, p_b = row["final_p_a"], row["final_p_b"]
    width_a = f"{(p_a or 0) * 100:.1f}"
    width_b = f"{(p_b or 0) * 100:.1f}"
    pick = row["pick"]
    classes = ["card"]
    if not row["actionable"]:
        classes.append("is-stale")
    if pick is None:
        classes.append("is-nopick")

    def team_line(name, final_p, market_p, own_p, odds, vrs_rank, vrs_pts, hltv_rank, hltv_url, is_pick):
        bits = [f'<span class="team-name">{esc(name)}</span>']
        bits.append('<span class="team-meta">')
        meta = []
        if vrs_rank:
            meta.append(f"VRS #{vrs_rank}")
        if hltv_rank and hltv_url:
            meta.append(f'<a href="{esc(hltv_url)}">HLTV #{hltv_rank}</a>')
        elif hltv_rank:
            meta.append(f"HLTV #{hltv_rank}")
        bits.append(" · ".join(meta))
        bits.append("</span>")
        prob = f'<span class="team-prob">{esc(pct(final_p))}</span>'
        return f"""<div class="team{" is-pick" if is_pick else ""}">
  <div class="team-id">{''.join(bits)}</div>
  {prob}
</div>"""

    bar = ""
    if p_a is not None:
        bar = f"""<div class="bar" role="img" aria-label="{esc(pct(p_a))} to {esc(pct(p_b))}">
  <div class="bar-a" style="width:{width_a}%"></div>
  <div class="bar-b" style="width:{width_b}%"></div>
</div>"""

    detail_rows = []
    if row["market_p_a"] is not None:
        odds_a_text = format(row["market_odds_a"], "g")
        odds_b_text = format(row["market_odds_b"], "g")
        vig_text = (
            ", vig " + format(row["market_overround"] * 100, ".1f") + "%"
            if row["market_overround"] is not None
            else ""
        )
        detail_rows.append(
            f'<div class="detail"><span>Market line</span><b>{esc(pct(row["market_p_a"]))} / '
            f'{esc(pct(row["market_p_b"]))}</b><span class="muted">'
            f'{esc(odds_a_text)} vs {esc(odds_b_text)}{esc(vig_text)}'
            f'</span></div>'
        )
    if row["own_p_a"] is not None:
        detail_rows.append(
            f'<div class="detail"><span>Our model</span><b>{esc(pct(row["own_p_a"]))} / '
            f'{esc(pct(row["own_p_b"]))}</b><span class="muted">Valve VRS '
            f'{row["vrs_a"]} vs {row["vrs_b"]}</span></div>'
        )
    if row["market_p_a"] is None and row["own_p_a"] is None:
        detail_rows.append('<div class="detail"><span>No line</span><b class="blank">—</b>'
                           '<span class="muted">unverified, see Flagged</span></div>')

    links = "".join(
        f'<a class="src" href="{esc(item["url"])}" rel="noopener noreferrer">{esc(item["label"])}</a>'
        for item in row["evidence"]
    )

    pick_html = (
        f'<div class="pick"><span class="pick-label">Pick</span> '
        f'<span class="pick-team">{esc(pick)}</span> '
        f'<span class="pick-conf conf-{esc(row["confidence"].replace("-", ""))}">{esc(row["confidence"])}</span>'
        f'<span class="pick-src">from {esc(row["source_used"])}</span></div>'
        if pick else
        '<div class="pick"><span class="pick-label">Pick</span> '
        '<span class="pick-team none">No pick — no verified line</span></div>'
    )

    badge = ""
    if "CC-04" in row["flags"]:
        badge = '<span class="badge badge-warn">market / model disagree</span>'
    if not row["actionable"]:
        badge = '<span class="badge badge-stale">lock time passed</span>'

    return f"""<article class="{' '.join(classes)}" data-search="{esc((row['competition'] or '') + ' ' + row['team_a'] + ' ' + row['team_b'])}" data-lock="{esc(row['lock_utc'])}">
  <div class="card-head">
    <span class="tier tier-{esc((row['tier'] or 'na').lower())}">{esc(row['tier'] or '—')}</span>
    <span class="comp">{esc(row['competition'])}</span>
    {badge}
  </div>
  <div class="card-time">Starts <b>{esc(row['start_utc'])} UTC</b> · picks lock {esc(row['lock_utc'])} UTC</div>
  <div class="teams">
    {team_line(row['team_a'], p_a, row['market_p_a'], row['own_p_a'], row['market_odds_a'],
               row['vrs_a_rank'], row['vrs_a'], row['hltv_a'], row['hltv_a_url'], pick == row['team_a'])}
    {team_line(row['team_b'], p_b, row['market_p_b'], row['own_p_b'], row['market_odds_b'],
               row['vrs_b_rank'], row['vrs_b'], row['hltv_b'], row['hltv_b_url'], pick == row['team_b'])}
  </div>
  {bar}
  {pick_html}
  <div class="details">{''.join(detail_rows)}</div>
  <div class="sources">{links}</div>
</article>"""


def write_index(rows, active, stale, snapshot_utc, hotspawn_fetched, egw_doc, vrs_doc, hltv_doc):
    cards = "".join(match_card(row) for row in active)
    stale_cards = "".join(match_card(row) for row in stale) if stale else ""

    with_market = sum(1 for r in active if r["market_p_a"] is not None)
    with_own = sum(1 for r in active if r["own_p_a"] is not None)
    with_pick = sum(1 for r in active if r["pick"])

    stale_block = ""
    if stale_cards:
        stale_block = f"""
  <section class="section">
    <h2>Other CS2 rows carried in the Hotspawn payload ({len(stale)})</h2>
    <p class="note">Hotspawn's server-rendered payload still lists these fixtures, but their lock
    times are in the past — most of them are dated June/July 2026. They are shown for completeness
    and are not playable picks. No bookmaker prices them.</p>
    <div class="cards">{stale_cards}</div>
  </section>"""

    body = f"""
  <section class="stats">
    <div class="stat"><b>{len(active)}</b><span>playable fixtures</span></div>
    <div class="stat"><b>{with_market}</b><span>with a bookmaker line</span></div>
    <div class="stat"><b>{with_own}</b><span>with our own line</span></div>
    <div class="stat"><b>{with_pick}</b><span>picks published</span></div>
  </section>

  <section class="panel">
    <p><b>Snapshot:</b> bookmaker lines read {esc(egw_doc.get('captured_utc', 'unknown'))}
    (window {esc(egw_doc.get('capture_window_utc', ''))}); Hotspawn lobby payload fetched
    {esc(hotspawn_fetched or 'unknown')}; Valve standings dated {esc(vrs_doc.get('standings_date', ''))};
    HLTV world ranking dated {esc(hltv_doc.get('ranking_date', ''))}.</p>
    <p class="note">The published percentage is the external bookmaker line (de-vigged) where one
    exists, otherwise our own model. Both are shown on every card so you can see where they agree
    and where they do not. Hotspawn's crowd pick % is never used.</p>
  </section>

  <section class="section">
    <div class="filter-row">
      <input id="filter" type="search" placeholder="Filter by team or tournament…" aria-label="Filter matches">
      <label class="toggle"><input id="hideStale" type="checkbox"> <span>Hide past locks</span></label>
    </div>
    <div class="cards" id="cards">{cards}</div>
    <p class="empty" id="empty" hidden>No match fits that filter.</p>
  </section>
{stale_block}
"""
    html = page(
        "Hotspawn CS2 Pick'em — win probabilities",
        "This week's picks",
        body,
        "index.html",
        subtitle="Every CS2 Pick'em fixture Hotspawn currently offers, with a win probability for each team.",
    )
    html = html.replace("</body>", '<script src="assets/picks.js"></script>\n</body>')
    (OUT / "index.html").write_text(html)


def write_methodology(snapshot_utc):
    body = f"""
  <section class="panel">
    <h2>1. Where the fixtures come from</h2>
    <p>The match list is read from Hotspawn's own server-rendered pick'em payload
    (<code>&lt;script id="ng-state"&gt;</code>) on
    <a href="https://play.hotspawn.com/cs2-pickems">play.hotspawn.com/cs2-pickems</a> and
    <a href="https://play.hotspawn.com/lobby">play.hotspawn.com/lobby</a>. Every fixture carries an
    id, both team names, the competition, the tier, and <code>scheduled_start_time</code> /
    <code>lock_time</code> as millisecond epochs, so the UTC start and lock times on this site are the
    site's own values with no timezone guessing.</p>
    <p>Hotspawn is used <b>only</b> to identify the fixtures. Its "N% picked" crowd figures are not
    read into any calculation.</p>
  </section>

  <section class="panel">
    <h2>2. Market probability — external bookmaker lines</h2>
    <p>Lines come from <a href="https://egamersworld.com/counterstrike/matches">EGamersWorld</a>,
    which publishes an aggregated bookmaker moneyline per match — its own match pages describe the
    number as the bookmaker consensus (for example, on the WBT vs ENCE page: "the majority of
    bookmaker companies believe in WBT victory. Odds on them are equal to 1.618"). Decimal odds
    <i>a</i> and <i>b</i> are converted to probabilities by removing the overround:</p>
    <pre>P(a) = (1/a) / (1/a + 1/b)      P(b) = (1/b) / (1/a + 1/b)</pre>
    <p>The overround itself (1/a + 1/b − 1) is shown on each row, so you can see the bookmaker's
    margin. Where a source shows its generic 1.8 / 1.8 default rather than a real price, the field is
    left blank and flagged — a placeholder is not a line.</p>
  </section>

  <section class="panel">
    <h2>3. Our own line — Valve's official standings</h2>
    <p>We also originate a line ourselves from
    <a href="{VRS_BLOB_URL}">Valve's official Counter-Strike Regional Standings</a> (global, dated
    2026-10-05). The rating difference is converted with a logistic:</p>
    <pre>P(a wins) = 1 / (1 + 10 ^ ( -K · (points_a − points_b) / 400 ))      K = {K_MODEL}</pre>
    <p>Valve publishes its own expected-win curve as <code>K = g(rd = 75) = {K_VALVE_RAW}</code>
    (<code>fit.js</code>, <code>priorWinExpectation</code>), and notes in the repository README that
    this slope is "shallower than we'd like". The slope used here was fitted by maximum likelihood on
    6,765 match results that Valve publishes in the same repository, always with the rating snapshot
    taken <i>before</i> the match, and scored out of sample on 2026-08-03 → 2026-10-05:</p>
    <table class="table">
      <thead><tr><th>Curve</th><th>Log loss</th><th>Brier</th></tr></thead>
      <tbody>
        <tr><td>Valve's raw slope ({K_VALVE_RAW})</td><td>0.66185</td><td>0.22936</td></tr>
        <tr><td>Fitted slope ({K_MODEL})</td><td>0.64351</td><td>0.22575</td></tr>
      </tbody>
    </table>
    <p>Full diagnostics: <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/model/input/vrs/calibration.json">model/input/vrs/calibration.json</a>
    (fitted by session <code>arena/91eff436</code>; the numbers are re-checked against that file by
    <code>scripts/verify_picks.py</code>).</p>
    <p>A team that is <b>not</b> in Valve's file, or that matches two different rows, gets no own
    line. The cell stays blank and the reason is published — we never pick a row by guessing.</p>
  </section>

  <section class="panel">
    <h2>4. What the published percentage is</h2>
    <ul>
      <li>If an external bookmaker line exists, the published probability is that line, de-vigged.</li>
      <li>Otherwise it is our own model probability.</li>
      <li>If neither exists, no pick is published.</li>
    </ul>
    <p>Both numbers are shown on every card. Where the market and our model disagree about which team
    is the favourite, the card is marked and the match is listed on the
    <a href="flagged.html">Flagged for Review</a> page.</p>
    <p>Confidence bands are just the distance from a coin flip: <b>lean</b> ≥ 54%, <b>clear</b> ≥ 62%,
    <b>strong</b> ≥ 75%. They describe how lopsided the line is, not a guarantee.</p>
  </section>

  <section class="panel">
    <h2>5. Known limitations</h2>
    <ul>
      <li>Valve's standings are a 2026-10-05 snapshot; rosters can change between the snapshot and
          the match.</li>
      <li>The own model uses rating only — no map veto, current form, stand-in or travel input.</li>
      <li>Elisa BreakOut matches are best-of-one, which is higher variance than a best-of-three; the
          model does not adjust for series length.</li>
      <li>Only the full-match winner market is used. Map and handicap prices are ignored.</li>
    </ul>
  </section>
"""
    (OUT / "methodology.html").write_text(
        page("Method — Hotspawn CS2 Pick'em analysis", "How these numbers are produced",
             body, "methodology.html",
             subtitle="Every formula, input and limitation, with links to the sources.")
    )


def write_sources(egw_doc, vrs_doc, hltv_doc, fixtures_doc, pinnacle_doc, snapshot_utc):
    def rows_for(items):
        return "".join(items)

    hotspawn_rows = rows_for(
        f"""<tr><td>Hotspawn CS2 pick'em lobby</td>
        <td><a href="https://play.hotspawn.com/cs2-pickems">play.hotspawn.com/cs2-pickems</a></td>
        <td>{esc((fixtures_doc.get('pages') or [{}])[0].get('fetched_utc', ''))}</td>
        <td>{(fixtures_doc.get('pages') or [{}])[0].get('http_status', '')}</td>
        <td>Fixture identity, teams, competition, tier, UTC start and lock times. Pick % ignored.</td></tr>
        <tr><td>Hotspawn general lobby</td>
        <td><a href="https://play.hotspawn.com/lobby">play.hotspawn.com/lobby</a></td>
        <td>{esc(((fixtures_doc.get('pages') or [{}, {}])[1:2] or [{}])[0].get('fetched_utc', ''))}</td>
        <td>{((fixtures_doc.get('pages') or [{}, {}])[1:2] or [{}])[0].get('http_status', '')}</td>
        <td>Second read of the same payload; union of fixtures.</td></tr>"""
    )

    egw_rows = ""
    for match in egw_doc.get("matches") or []:
        if match.get("status") != "priced":
            continue
        egw_rows += f"""<tr><td>{esc(match['event'])} — {esc(match['team_a'])} v {esc(match['team_b'])}</td>
        <td><a href="{esc(match['source_url'])}">{esc(match['source_url'])}</a></td>
        <td>{esc(egw_doc.get('captured_utc', ''))}</td><td>200</td>
        <td>{esc(f"{match['odds_a']:g}")} / {esc(f"{match['odds_b']:g}")} ({esc(match['format'])})</td></tr>"""

    body = f"""
  <section class="panel">
    <h2>Fixture source (identity only)</h2>
    <div class="table-scroll">
      <table class="table"><thead><tr><th>Source</th><th>URL</th><th>Fetched (UTC)</th><th>HTTP</th><th>What it supplied</th></tr></thead>
      <tbody>{hotspawn_rows}</tbody></table>
    </div>
  </section>

  <section class="panel">
    <h2>External bookmaker lines</h2>
    <p>List page: <a href="{esc(egw_doc.get('source_list_page', ''))}">{esc(egw_doc.get('source_list_page', ''))}</a>
    — read {esc(egw_doc.get('captured_utc', ''))}, window {esc(egw_doc.get('capture_window_utc', ''))}.
    Times on that site are {esc(egw_doc.get('displayed_timezone', ''))}.</p>
    <div class="table-scroll">
      <table class="table"><thead><tr><th>Match</th><th>Source page</th><th>Captured (UTC)</th><th>HTTP</th><th>Price read</th></tr></thead>
      <tbody>{egw_rows}</tbody></table>
    </div>
  </section>

  <section class="panel">
    <h2>Ratings for our own line</h2>
    <div class="table-scroll">
      <table class="table"><thead><tr><th>Source</th><th>URL</th><th>Fetched / dated</th><th>Check</th><th>What it supplied</th></tr></thead>
      <tbody>
        <tr><td>Valve Software — Counter-Strike Regional Standings (global)</td>
        <td><a href="{VRS_BLOB_URL}">{VRS_BLOB_URL}</a></td>
        <td>standings dated {esc(vrs_doc.get('standings_date', ''))}; live fetch checked
        {esc(vrs_doc.get('live_fetch_checked_utc', ''))}</td>
        <td>SHA-256 <code>{esc((vrs_doc.get('sha256') or '')[:16])}…</code>
        {'matches the live file' if vrs_doc.get('sha256_matches_live_fetch') else 'MISMATCH — do not use'}</td>
        <td>{esc(str(vrs_doc.get('team_count', '')))} ranked teams with points and rosters.</td></tr>
        <tr><td>HLTV world ranking</td>
        <td><a href="{esc(hltv_doc.get('canonical_url', 'https://www.hltv.org/ranking/teams'))}">{esc(hltv_doc.get('canonical_url', 'https://www.hltv.org/ranking/teams'))}</a></td>
        <td>{esc(hltv_doc.get('ranking_date', ''))} (read {esc(hltv_doc.get('fetched_utc', ''))})</td>
        <td>{esc(hltv_doc.get('team_count', ''))} teams parsed</td>
        <td>Shown alongside each team as a cross-check. Not an input to either probability.</td></tr>
      </tbody></table>
    </div>
  </section>

  <section class="panel">
    <h2>Secondary / attempted sources</h2>
    <div class="table-scroll">
      <table class="table"><thead><tr><th>Source</th><th>URL</th><th>Result</th><th>Use</th></tr></thead>
      <tbody>
        <tr><td>Pinnacle public guest feed</td>
        <td><a href="https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/highlighted">guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups/highlighted</a></td>
        <td>HTTP 200 — matchups returned, but the price endpoints
        (<code>/markets/moneyline</code>) answer 401 to an unauthenticated client.</td>
        <td>Used to cross-check one start time (Falcons v Ninjas In Pyjamas,
        <code>cutoffAt 2026-10-14T11:00:00Z</code>) and thereby confirm EGamersWorld's display
        timezone. No Pinnacle price is published.</td></tr>
        <tr><td>Oddsportal</td>
        <td><a href="https://www.oddsportal.com/esports/counter-strike/">oddsportal.com/esports/counter-strike</a></td>
        <td>HTTP 200, but it lists only 3 CS2 tournaments, none of them on this slate.</td>
        <td>Not used.</td></tr>
        <tr><td>HLTV</td>
        <td><a href="https://www.hltv.org/ranking/teams/2026/october/12">hltv.org/ranking/teams</a></td>
        <td>Ranking page already in the repository from session arena/91eff436
        (read {esc(hltv_doc.get('fetched_utc', ''))}); Live match pages are blocked to this
        environment's automated reads.</td>
        <td>Displayed per team as a cross-check only.</td></tr>
      </tbody></table>
    </div>
  </section>
"""
    (OUT / "sources.html").write_text(
        page("Sources — Hotspawn CS2 Pick'em analysis", "Every source behind every number",
             body, "sources.html",
             subtitle="Each row links the exact page or file a value was read from.")
    )


def write_flagged(rows, snapshot_utc):
    items = []
    for row in rows:
        if not row["flags"]:
            continue
        flag_badges = "".join(
            f'<span class="badge badge-warn" title="{esc(FLAG_TEXT.get(flag, ""))}">{esc(flag)}</span>'
            for flag in row["flags"]
        )
        note_list = "".join(f"<li>{esc(note)}</li>" for note in row["notes"]) or "<li>See the flag description below.</li>"
        sources = "".join(
            f'<a class="src" href="{esc(item["url"])}" rel="noopener noreferrer">{esc(item["label"])}</a>'
            for item in row["evidence"]
        )
        items.append(f"""<article class="card flag-card">
  <div class="card-head">
    <span class="comp">{esc(row['competition'])}</span>
    <span class="muted">{esc(row['start_utc'])} UTC</span>
  </div>
  <div class="card-time"><b>{esc(row['team_a'])}</b> v <b>{esc(row['team_b'])}</b></div>
  <div class="badges">{flag_badges}</div>
  <ul class="flag-notes">{note_list}</ul>
  <div class="sources">{sources}</div>
</article>""")

    flag_table = "".join(
        f"<tr><td><code>{esc(flag)}</code></td><td>{esc(text)}</td></tr>"
        for flag, text in FLAG_TEXT.items()
    )
    count = len(items)

    body = f"""
  <section class="panel">
    <p><b>{count}</b> of {len(rows)} rows carry at least one flag. Nothing on this page blocks the
    rest of the site — it is the honest list of what could not be confirmed, with the evidence that
    is available. Values that cannot be confirmed are left blank in the tables rather than filled in.</p>
  </section>

  <section class="section">
    <h2>Flagged matches</h2>
    <div class="cards">{''.join(items) or '<p class="note">Nothing flagged.</p>'}</div>
  </section>

  <section class="section">
    <h2>What each flag means</h2>
    <div class="table-scroll">
      <table class="table"><thead><tr><th>Flag</th><th>Meaning</th></tr></thead>
      <tbody>{flag_table}</tbody></table>
    </div>
  </section>

  <section class="section">
    <h2>Repository-wide irregularities found while reading the board</h2>
    <ul class="flag-notes">
      <li><b>CC-R1 — Hotspawn carries stale fixtures.</b> The server-rendered payload lists far more
      CS2 fixtures than are playable: every row says <code>status: scheduled</code>, but most have
      lock times in June/July 2026. Only rows whose lock time is still in the future are picks.</li>
      <li><b>CC-R2 — "60/68 matches this week".</b> The lobby header count (68 at 22:19 UTC) is a
      live, client-computed count across both game titles and does not equal the number of playable
      CS2 fixtures. The filter panel on the CS2 page counted 85–90 rows, of which only 25 had a
      future lock time at this snapshot.</li>
      <li><b>CC-R3 — no series format on Hotspawn.</b> The payload's <code>best_of</code> /
      <code>series_format</code> fields are null for every fixture. Series length (Bo1 vs Bo3) is
      taken from EGamersWorld where shown and is not modelled.</li>
      <li><b>CC-R4 — placeholder prices.</b> EGamersWorld shows a generic 1.8 / 1.8 for matches it
      has not priced (for example FORZE Reload's CCT fixture). Those are not lines and are left blank.</li>
    </ul>
  </section>
"""
    (OUT / "flagged.html").write_text(
        page("Flagged for Review — Hotspawn CS2 Pick'em analysis", "Flagged for review",
             body, "flagged.html",
             subtitle="Unverified values, name mappings and disagreements — with the evidence for each.")
    )


def write_css():
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "picks.css").write_text("""
:root{
  --bg:#0e1116; --panel:#161b22; --panel-2:#1c2230; --line:#2a3140;
  --text:#e6edf3; --muted:#9aa7b8; --accent:#4d9fff; --good:#3fb950; --warn:#d29922; --bad:#f85149;
  --radius:12px;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);
  font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--accent)}
.wrap{max-width:1080px;margin:0 auto;padding:0 14px}
.site-header{position:sticky;top:0;z-index:20;background:rgba(14,17,22,.94);
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line)}
.site-header .wrap{display:flex;align-items:center;justify-content:space-between;gap:12px;
  min-height:58px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:10px}
.brand-mark{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;
  background:linear-gradient(135deg,#4d9fff,#7b61ff);font-weight:700;color:#08101c;font-size:14px}
.brand-text{display:flex;flex-direction:column;line-height:1.15}
.brand-text strong{font-size:15px}
.brand-text span{font-size:12px;color:var(--muted)}
.nav{display:flex;gap:4px;flex-wrap:wrap}
.nav-link{padding:7px 11px;border-radius:8px;color:var(--muted);text-decoration:none;font-size:14px}
.nav-link:hover{background:var(--panel-2);color:var(--text)}
.nav-link.is-active{background:var(--panel-2);color:var(--text);font-weight:600}
main{padding:18px 14px 48px}
h1{font-size:clamp(20px,5vw,28px);margin:6px 0 4px}
h2{font-size:18px;margin:0 0 10px}
.subtitle{color:var(--muted);margin:0 0 16px;font-size:15px}
.note{color:var(--muted);font-size:14px}
.muted{color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:14px;margin:0 0 18px}
.panel p{margin:0 0 10px}
.panel p:last-child{margin-bottom:0}
.panel ul{margin:0;padding-left:20px}
.panel li{margin-bottom:6px}
pre{background:#0b0f15;border:1px solid var(--line);border-radius:8px;padding:10px;overflow-x:auto;
  font-size:14px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 16px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);
  padding:12px;text-align:center}
.stat b{display:block;font-size:24px;line-height:1.1}
.stat span{font-size:12px;color:var(--muted)}
.section{margin:0 0 26px}
.filter-row{display:flex;gap:10px;align-items:center;margin:0 0 12px;flex-wrap:wrap}
#filter{flex:1;min-width:180px;background:var(--panel);border:1px solid var(--line);
  border-radius:9px;color:var(--text);padding:9px 11px;font-size:15px}
.toggle{font-size:14px;color:var(--muted);display:flex;align-items:center;gap:6px}
.cards{display:grid;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:var(--radius);padding:13px}
.card.is-stale{opacity:.62}
.card.is-nopick{border-color:#4a3320}
.card-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:7px}
.tier{font-size:11px;font-weight:700;letter-spacing:.04em;padding:3px 7px;border-radius:6px;
  background:var(--panel-2);color:var(--muted)}
.tier-s{background:#3b2f10;color:#f0c674}
.tier-b{background:#12304a;color:#79c0ff}
.tier-c{background:#25303a;color:#9aa7b8}
.comp{font-size:13px;color:var(--muted);flex:1;min-width:120px}
.card-time{font-size:13px;color:var(--muted);margin-bottom:10px}
.teams{display:flex;flex-direction:column;gap:6px}
.team{display:flex;align-items:center;justify-content:space-between;gap:10px;
  background:var(--panel-2);border:1px solid transparent;border-radius:9px;padding:9px 11px}
.team.is-pick{border-color:var(--good);background:#12241a}
.team-id{display:flex;flex-direction:column;min-width:0}
.team-name{font-weight:600;font-size:16px;overflow-wrap:anywhere}
.team-meta{font-size:12px;color:var(--muted)}
.team-prob{font-size:19px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.bar{display:flex;height:8px;border-radius:6px;overflow:hidden;background:#0b0f15;margin:9px 0 11px}
.bar-a{background:var(--accent)}
.bar-b{background:#7b61ff}
.pick{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.pick-label{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.pick-team{font-weight:700;font-size:17px;color:var(--good)}
.pick-team.none{color:var(--warn);font-size:15px}
.pick-conf{font-size:11px;padding:3px 7px;border-radius:6px;background:var(--panel-2);color:var(--muted)}
.conf-strong{background:#12241a;color:#56d364}
.conf-clear{background:#122a24;color:#4ac58a}
.conf-lean{background:#2a2413;color:#d9b263}
.pick-src{font-size:12px;color:var(--muted)}
.details{display:grid;gap:5px;margin-bottom:10px}
.detail{display:flex;align-items:baseline;gap:8px;font-size:13px;flex-wrap:wrap}
.detail span:first-child{color:var(--muted);min-width:92px}
.detail b{font-variant-numeric:tabular-nums}
.detail .blank{color:var(--warn)}
.sources{display:flex;flex-wrap:wrap;gap:6px}
.src{font-size:12px;background:var(--panel-2);border:1px solid var(--line);border-radius:999px;
  padding:4px 10px;text-decoration:none;color:var(--text)}
.src:hover{border-color:var(--accent)}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}
.badge{font-size:11px;padding:3px 8px;border-radius:6px}
.badge-warn{background:#33280f;color:#e3b341}
.badge-stale{background:#2b2119;color:#c9a26d}
.flag-notes{margin:8px 0;padding-left:20px;font-size:14px;color:var(--muted)}
.flag-notes li{margin-bottom:5px}
.flag-card{border-left:3px solid var(--warn)}
.empty{color:var(--muted);text-align:center;padding:18px}
.table-scroll{overflow-x:auto}
.table{width:100%;border-collapse:collapse;font-size:14px}
.table th,.table td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);
  vertical-align:top}
.table th{color:var(--muted);font-weight:600;font-size:13px;white-space:nowrap}
.table td a{overflow-wrap:anywhere}
.site-footer{border-top:1px solid var(--line);padding:16px 0 34px;color:var(--muted);font-size:13px}
@media (max-width:640px){
  .stats{grid-template-columns:repeat(2,1fr)}
  .site-header .wrap{min-height:52px}
  .nav-link{padding:6px 9px;font-size:13px}
  .team-prob{font-size:18px}
}
""")


def write_js():
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "picks.js").write_text("""(function () {
  var input = document.getElementById('filter');
  var hideStale = document.getElementById('hideStale');
  var cards = document.getElementById('cards');
  var empty = document.getElementById('empty');
  if (!cards) { return; }

  function apply() {
    var q = (input && input.value || '').toLowerCase().trim();
    var hidePast = !!(hideStale && hideStale.checked);
    var shown = 0;
    Array.prototype.forEach.call(cards.querySelectorAll('.card'), function (card) {
      var hay = (card.getAttribute('data-search') || '').toLowerCase();
      var stale = card.classList.contains('is-stale');
      var ok = (!q || hay.indexOf(q) !== -1) && !(hidePast && stale);
      card.hidden = !ok;
      if (ok) { shown++; }
    });
    if (empty) { empty.hidden = shown !== 0; }
  }

  if (input) { input.addEventListener('input', apply); }
  if (hideStale) { hideStale.addEventListener('change', apply); }

  // Dim any row whose Hotspawn lock time has already passed in the visitor's real time.
  function markLocks() {
    var now = Date.now();
    Array.prototype.forEach.call(cards.querySelectorAll('.card[data-lock]'), function (card) {
      var stamp = card.getAttribute('data-lock');
      if (!stamp) { return; }
      var when = Date.parse(stamp.replace(' ', 'T') + 'Z');
      if (isNaN(when) || when > now) { return; }
      if (card.classList.contains('is-stale')) { return; }
      card.classList.add('is-stale');
      var head = card.querySelector('.card-head');
      if (head && !head.querySelector('.badge-stale')) {
        var tag = document.createElement('span');
        tag.className = 'badge badge-stale';
        tag.textContent = 'lock time passed';
        head.appendChild(tag);
      }
    });
  }

  markLocks();
  setInterval(markLocks, 60000);
})();
""")


if __name__ == "__main__":
    sys.exit(main())
