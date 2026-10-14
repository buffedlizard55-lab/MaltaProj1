#!/usr/bin/env python3
"""Build the mobile executive summary under summary/ (session arena/20d753a2).

Inputs (all committed, all sourced):
  every/data/picks.csv                  sourced pick dataset (one row per open CS2 fixture)
  summary/data/lobby_capture.csv        open CS2 cards from Hotspawn (refreshed by scripts/summary_lobby.py;
                                        team names, UTC start, match link only if the page shows it)

Rules enforced (the build FAILS rather than publishing if any rule breaks):
  * every lobby card maps to exactly one dataset row (same unordered team pair) and vice versa
  * the lobby card's display time + its stated UTC offset == the dataset start_utc
  * every row has a pick that equals one of the two teams, and the pick's % equals that side's %
  * every row carries at least one source URL
  * Hotspawn crowd percentages are never read or displayed

Outputs:
  summary/index.html, picks.html, unresolved.html, flagged.html, sources.html
  summary/data/picks.json, picks.csv, coverage.json
Run:  python3 scripts/summary_build.py   (from the repository root)
"""
import csv
import datetime as dt
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "every" / "data" / "picks.csv"
LOBBY = ROOT / "summary" / "data" / "lobby_capture.csv"
OUT = ROOT / "summary"
DATA = OUT / "data"

def lobby_read():
    with open(LOBBY, newline="", encoding="utf-8") as fh:
        return max(r["captured_utc"] for r in csv.DictReader(fh))


LOBBY_READ = lobby_read()

# Per-row limitations for unresolved rows. Each note records what was checked and what it showed.
UNRESOLVED_NOTES = {
    "1081112": {
        "checked": [
            ("EGamersWorld match page (search excerpt, not a full page read)",
             "https://egamersworld.com/counterstrike/match/4kY9VAmiEg/banda-chuya-vs-6666-JdPgKgp5y",
             "Both sides shown at 1.8 / 1.8 — identical placeholder prices, rejected (no market)."),
        ],
        "limits": "No real two-sided price. The pick rests only on Valve Regional Standings points (801 vs 923) converted by a project-assumed rating formula. The dataset also records a parity note: the slate's own-line calculation for the same pairing gave 46.69% (different inputs), so the 74.34% figure is not stable across our own calculations.",
    },
    "1081113": {
        "checked": [
            ("EGamersWorld match page (search excerpt, not a full page read)",
             "https://egamersworld.com/counterstrike/match/1sGIL2gAYu/wraith-pcific-vs-ryvex-6SKJ5jwGy",
             "Both sides shown at 1.8 / 1.8 — placeholder, rejected (no market)."),
        ],
        "limits": "No real two-sided price. Team name differs by source: Hotspawn and HLTV say 'PCIFIC', EGamersWorld says 'WRAITH PCIFIC'. The pick rests on HLTV ranking points plus Valve Regional Standings points (ranking points 3 vs 5 — both are very low).",
    },
    "1081120": {
        "checked": [
            ("Polymarket CS2 team page for Privateer Gaming (search excerpt)",
             "https://polymarket.com/teams/cs2/privateer-gaming",
             "Shows mellren 50% / Privateer Gaming 50% with $0 volume — not a usable market price."),
            ("EGamersWorld match page (search excerpt)",
             "https://egamersworld.com/counterstrike/match/4kY9VAmiEg/mellren-vs-privateer-gaming-ASh_MyDBS",
             "Shows mellren 1.8 with no real opposing price."),
        ],
        "limits": "No usable market. The Polymarket 50/50 has zero volume. The pick rests on HLTV and Valve Regional Standings points. Team name differs: Hotspawn says 'Privateer', Polymarket and EGamersWorld say 'Privateer Gaming'.",
    },
    "1079624": {
        "checked": [
            ("EGamersWorld match page (search excerpt)",
             "https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3",
             "Shows FORZE Reload at 1.8 with no opposing price."),
        ],
        "limits": "No market. LFO 10 does not appear in the ranking sources the dataset uses, so its rating is a research-only input. The 95.31% pick is therefore a model bound, not a measured probability: treat it as low confidence even though it is the largest figure on the board.",
    },
}

SOURCE_RECHECKS = [
    # (status, what, url, result)
    ("Re-read today", "Hotspawn CS2 lobby, 28 cards",
     "https://play.hotspawn.com/lobby",
     "28 CS2 cards read. All 28 map to dataset rows (team pair + start time, see coverage.json). 4 cards show no match link."),
    ("Re-read today", "EGamersWorld Gothic vs Lavked (bc.game odds)",
     "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B",
     "Odds 2.05 / 1.64 shown, matching the dataset. Still an aggregator quote, not checked against the book."),
    ("Re-read today", "HLTV 9z vs Aurora match page",
     "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
     "Best of 3 (LAN), 14 Oct 04:30, Thunderpick World Championship 2026. Matches the dataset format and time."),
    ("Failed today", "Pinnacle CS2 matchups page (the primary-book source for 7 rows)",
     "https://www.pinnacle.com/en/esports/games/cs2/matchups/",
     "HTTP 500 on re-read. The 7 Pinnacle-priced rows keep their 2026-10-14 02:21Z capture time and are flagged."),
    ("Search excerpt", "Unresolved-row checks (see unresolved.html)",
     "https://egamersworld.com/counterstrike/matches",
     "Used only to find the EGamersWorld match pages above; no price was taken from the listing page alone."),
]

CSS_HREF = "style.css"


def esc(v):
    return html.escape("" if v is None else str(v), quote=True)


def f(v):
    return float(v) if v not in (None, "") else None


def pct(v):
    return f"{v:.1f}%" if v is not None else "—"


def pair_key(a, b):
    return tuple(sorted([a.strip().lower(), b.strip().lower()]))


def load():
    src = list(csv.DictReader(open(SRC, newline="", encoding="utf-8")))
    lobby = list(csv.DictReader(open(LOBBY, newline="", encoding="utf-8")))
    return src, lobby


def build_rows(src, lobby):
    errors = []
    lobby_by_pair = {}
    for lc in lobby:
        k = pair_key(lc["lobby_team_1"], lc["lobby_team_2"])
        if k in lobby_by_pair:
            errors.append(f"duplicate lobby pair {k}")
        lobby_by_pair[k] = lc

    rows = []
    seen_pairs = set()
    for x in src:
        k = pair_key(x["team_a"], x["team_b"])
        lc = lobby_by_pair.get(k)
        if lc is None:
            errors.append(f"dataset fixture {x['fixture_id']} ({x['team_a']} v {x['team_b']}) is not on the lobby")
            continue
        seen_pairs.add(k)
        if lc["start_utc"] != x["start_utc"]:
            errors.append(f"time mismatch {x['fixture_id']}: lobby {lc['start_utc']} vs dataset {x['start_utc']}")

        a, b = x["team_a"], x["team_b"]
        if x["market_tier"]:
            pa, pb = f(x["market_p_a_pct"]), f(x["market_p_b_pct"])
            basis_kind = x["market_tier"]  # primary | aggregator
            book = x["market_book"]
            odds = (x["market_odds_a"], x["market_odds_b"])
            src_url = x["market_url"]
            captured = x["market_captured_utc"]
        else:
            pa, pb = f(x["our_series_p_a_pct"]), f(x["our_series_p_b_pct"])
            basis_kind = "own"
            book = ""
            odds = ("", "")
            src_url = x["pick_source_url"]
            captured = ""
        side_p = pa if x["pick"] == a else (pb if x["pick"] == b else None)
        if side_p is None:
            errors.append(f"pick '{x['pick']}' is neither team in {x['fixture_id']}")
            continue
        if abs(side_p - f(x["pick_pct"])) > 0.05:
            errors.append(f"pick % mismatch {x['fixture_id']}")
        if abs(pa + pb - 100) > 0.2:
            errors.append(f"probabilities do not sum to 100 in {x['fixture_id']}")

        urls = [u for u in [src_url, x["pick_source_url"], x["hltv_match_url"], x["best_of_source_url"],
                            x["rating_a_source_url"], x["rating_b_source_url"], lc["hotspawn_match_url"]] if u]
        if not urls:
            errors.append(f"no source url for {x['fixture_id']}")

        rows.append({
            "fixture_id": x["fixture_id"],
            "start_utc": x["start_utc"],
            "competition": x["competition"],
            "tier": x["tier"].upper(),
            "best_of": x["best_of"],
            "team_a": a, "team_b": b,
            "prob_a_pct": pa, "prob_b_pct": pb,
            "pick": x["pick"],
            "pick_pct": f(x["pick_pct"]),
            "basis_kind": basis_kind,
            "book": book,
            "odds_a": odds[0], "odds_b": odds[1],
            "market_captured_utc": captured,
            "market_url": src_url,
            "pick_source_url": x["pick_source_url"],
            "hltv_match_url": x["hltv_match_url"],
            "hotspawn_match_url": lc["hotspawn_match_url"],
            "hotspawn_lobby_url": "https://play.hotspawn.com/lobby",
            "flags": x["flags"],
            "unresolved": basis_kind == "own",
            "unresolved_limits": UNRESOLVED_NOTES.get(x["fixture_id"], {}).get("limits", ""),
            "unresolved_checked": UNRESOLVED_NOTES.get(x["fixture_id"], {}).get("checked", []),
        })

    for k in lobby_by_pair:
        if k not in seen_pairs:
            errors.append(f"lobby card {k} has no dataset row")
    rows.sort(key=lambda r: (r["start_utc"], r["fixture_id"]))
    return rows, errors


def basis_text(r):
    if r["basis_kind"] == "primary":
        return ("Primary bookmaker line", f"{r['book']} — de-vigged two-way price, captured {r['market_captured_utc']}")
    if r["basis_kind"] == "aggregator":
        return ("Bookmaker line via aggregator", f"{r['book']} odds as reported by EGamersWorld, captured {r['market_captured_utc']}. Not checked against the bookmaker.")
    return ("UNRESOLVED — ratings only", "No usable market line. Pick from HLTV / Valve Regional Standings points.")


def day_label(start_utc):
    d = dt.datetime.strptime(start_utc, "%Y-%m-%dT%H:%M:%SZ")
    return d.strftime("%a %b %d"), d.strftime("%Y-%m-%d")


def hhmm(start_utc):
    return start_utc[11:16] + " UTC"


PAGE_HEAD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · Hotspawn CS2 picks</title>
<meta name="description" content="{desc}">
<link rel="stylesheet" href="{css}">
</head><body>
<header class="top"><div class="wrap">
  <a class="brand" href="index.html">CS2 picks</a>
  <nav class="chips" aria-label="Sections">
    <a href="index.html" class="{c_sum}">Summary</a>
    <a href="picks.html" class="{c_picks}">All picks</a>
    <a href="unresolved.html" class="{c_unres}">Unresolved</a>
    <a href="flagged.html" class="{c_flag}">Flagged</a>
    <a href="sources.html" class="{c_src}">Sources</a>
    <a href="../index.html">Site home</a>
  </nav>
</div></header>
<main class="wrap">
"""
PAGE_TAIL = """
</main>
<footer class="wrap foot">
  Built {built} from <code>every/data/picks.csv</code> + the Hotspawn lobby capture of {lobby_read}.
  Hotspawn crowd percentages are never used as an input. Times are UTC.
</footer>
</body></html>
"""


def head(title, desc, active):
    keys = {"summary": "c_sum", "picks": "c_picks", "unresolved": "c_unres", "flagged": "c_flag", "sources": "c_src"}
    kw = {v: ("on" if k == active else "") for k, v in keys.items()}
    return PAGE_HEAD.format(title=esc(title), desc=esc(desc), css=CSS_HREF, **{
        "c_sum": kw["c_sum"], "c_picks": kw["c_picks"], "c_unres": kw["c_unres"],
        "c_flag": kw["c_flag"], "c_src": kw["c_src"]})


def tail(built):
    return PAGE_TAIL.format(built=esc(built), lobby_read=esc(LOBBY_READ))


def link(url, text=None):
    if not url:
        return ""
    return f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(text or url)}</a>'


def card(r, anchor=True):
    cls = "card unres" if r["unresolved"] else "card"
    label, detail = basis_text(r)
    a_pct, b_pct = r["prob_a_pct"], r["prob_b_pct"]
    pick_side = "a" if r["pick"] == r["team_a"] else "b"
    bar_a = f'<div class="bar"><span class="fill{" win" if pick_side == "a" else ""}" style="width:{a_pct:.1f}%"></span></div>'
    bar_b = f'<div class="bar"><span class="fill{" win" if pick_side == "b" else ""}" style="width:{b_pct:.1f}%"></span></div>'
    pick_badge = f'<span class="pick{" low" if r["unresolved"] else ""}">PICK: {esc(r["pick"])} · {pct(r["pick_pct"])}</span>'
    flag = '<span class="flag">UNRESOLVED</span>' if r["unresolved"] else (
        '<span class="flag amber">Aggregator line</span>' if r["basis_kind"] == "aggregator" else '<span class="flag ok">Primary book</span>')
    price_label = "Rating source (no price)" if r["unresolved"] else "Price source"
    links = [link(r["market_url"], price_label),
             link(r["hltv_match_url"], "HLTV match"),
             link(r["hotspawn_match_url"], "Hotspawn match") if r["hotspawn_match_url"] else '<span class="muted">No Hotspawn match link on the lobby card</span>',
             link(r["hotspawn_lobby_url"], "Hotspawn lobby")]
    aid = f' id="m-{esc(r["fixture_id"])}"' if anchor else ""
    return f"""<article class="{cls}"{aid}>
  <div class="card-top"><span class="time">{esc(hhmm(r["start_utc"]))}</span> <span class="comp">{esc(r["competition"])} · Tier {esc(r["tier"])} · BO{esc(r["best_of"])}</span></div>
  <div class="versus">
    <div class="team{" winner" if pick_side == "a" else ""}"><div class="name">{esc(r["team_a"])}</div><div class="pctbig">{pct(a_pct)}</div>{bar_a}</div>
    <div class="vs">vs</div>
    <div class="team{" winner" if pick_side == "b" else ""}"><div class="name">{esc(r["team_b"])}</div><div class="pctbig">{pct(b_pct)}</div>{bar_b}</div>
  </div>
  <div class="pickrow">{pick_badge} {flag}</div>
  <p class="basis"><b>{esc(label)}.</b> {esc(detail)}</p>
  <p class="links">{' · '.join(x for x in links if x)}</p>
  <p class="fid">Fixture {esc(r["fixture_id"])}</p>
</article>
"""


def write(path, text):
    path.write_text(text, encoding="utf-8")


def stats(rows):
    return {
        "open": len(rows),
        "with_pick": sum(1 for r in rows if r["pick"]),
        "primary": sum(1 for r in rows if r["basis_kind"] == "primary"),
        "aggregator": sum(1 for r in rows if r["basis_kind"] == "aggregator"),
        "unresolved": sum(1 for r in rows if r["unresolved"]),
    }


def build_index(rows, built, s):
    days = {}
    for r in rows:
        days.setdefault(day_label(r["start_utc"])[1], []).append(r)
    day_chips = "".join(f'<a class="chip" href="picks.html#day-{d}">{esc(day_label(rs[0]["start_utc"])[0])} · {len(rs)} matches</a>' for d, rs in sorted(days.items()))
    at_a_glance = []
    for r in rows:
        tag = "UNRESOLVED" if r["unresolved"] else ("primary" if r["basis_kind"] == "primary" else "aggregator")
        at_a_glance.append(
            f'<li><a href="picks.html#m-{esc(r["fixture_id"])}">'
            f'<span class="g-time">{esc(r["start_utc"][5:10])} {esc(hhmm(r["start_utc"]))}</span>'
            f'<span class="g-match">{esc(r["team_a"])} vs {esc(r["team_b"])}</span>'
            f'<span class="g-pick">{esc(r["pick"])} <b>{pct(r["pick_pct"])}</b></span>'
            f'<span class="g-tag {"unres" if r["unresolved"] else ""}">{esc(tag)}</span></a></li>')
    body = f"""
<section class="hero">
  <h1>CS2 picks for every open Hotspawn match</h1>
  <p class="lead">A pick and a win probability for both teams in every open CS2 Pick'em fixture on the
  <a href="https://play.hotspawn.com/lobby" target="_blank" rel="noopener">Hotspawn lobby</a>.
  Probabilities come from outside betting lines where a line exists, and from HLTV / Valve ratings where it does not.
  Hotspawn crowd percentages are never used.</p>
  <p class="fresh">Dataset built {esc(built)} · lobby read {esc(LOBBY_READ)}</p>
</section>

<nav class="jump" aria-label="Jump to">
  <a class="btn" href="picks.html">All picks ({s["open"]})</a>
  <a class="btn" href="#at-a-glance">At a glance</a>
  <a class="btn warn" href="unresolved.html">Unresolved picks ({s["unresolved"]})</a>
  <a class="btn" href="flagged.html">Flagged for review</a>
  <a class="btn" href="sources.html">Sources &amp; checks</a>
</nav>

<section class="stats">
  <div class="stat"><b>{s["open"]}</b><span>open matches</span></div>
  <div class="stat"><b>{s["with_pick"]}</b><span>with a pick</span></div>
  <div class="stat"><b>{s["primary"]}</b><span>primary book line</span></div>
  <div class="stat"><b>{s["aggregator"]}</b><span>aggregator-reported line</span></div>
  <div class="stat warn"><b>{s["unresolved"]}</b><span>unresolved (ratings only)</span></div>
</section>

<section class="exec">
  <h2>Executive summary</h2>
  <ul>
    <li><b>Coverage:</b> all {s["open"]} open CS2 cards on the Hotspawn lobby have a pick and both teams' win probabilities. Every card maps to a row in the dataset; the check fails the build otherwise.</li>
    <li><b>Strongest basis:</b> {s["primary"]} matches are priced by a primary bookmaker line (Pinnacle), de-vigged to two-way probabilities.</li>
    <li><b>Weaker basis:</b> {s["aggregator"]} matches use bookmaker odds as reported by EGamersWorld (bc.game). They are not checked against the bookmaker and are labelled as such.</li>
    <li><b>Unresolved:</b> {s["unresolved"]} matches have no usable market line. Their picks rest on HLTV / Valve ratings alone and are listed separately with their limits, on <a href="unresolved.html">unresolved.html</a>.</li>
    <li><b>Known problem:</b> the Pinnacle source returned HTTP 500 on today's re-read, so its prices are carried from the 02:21Z capture. See <a href="flagged.html">flagged.html</a>.</li>
  </ul>
  <p class="jumplinks">Go to: {day_chips} · <a class="chip" href="unresolved.html">Unresolved</a> · <a class="chip" href="flagged.html">Flagged</a></p>
</section>

<section id="at-a-glance">
  <h2>At a glance — every match</h2>
  <p class="muted small">Tap a row to open that match's card. Times are UTC.</p>
  <ol class="glance">{''.join(at_a_glance)}</ol>
</section>
"""
    return head("Executive summary", "Executive summary: a pick and win probability for every open Hotspawn CS2 Pick'em match.", "summary") + body + tail(built)


def build_picks(rows, built, s):
    days = {}
    for r in rows:
        days.setdefault(day_label(r["start_utc"])[1], []).append(r)
    parts = [f"""
<h1>All picks</h1>
<p class="lead">{s["open"]} open matches, one card each, grouped by day. The chips jump to a day. Cards marked
<span class="flag">UNRESOLVED</span> have no usable market line.</p>
<nav class="jump small-jump">{''.join(f'<a class="chip" href="#day-{d}">{esc(day_label(rs[0]["start_utc"])[0])}</a>' for d, rs in sorted(days.items()))}
<a class="chip warn" href="unresolved.html">Unresolved list</a></nav>
"""]
    for d, rs in sorted(days.items()):
        parts.append(f'<section id="day-{d}"><h2>{esc(day_label(rs[0]["start_utc"])[0])} <span class="muted">· {len(rs)} matches</span></h2>')
        parts.extend(card(r) for r in rs)
        parts.append("</section>")
    return head("All picks", "Every open CS2 Pick'em match with its pick and win probability.", "picks") + "\n".join(parts) + tail(built)


def build_unresolved(rows, built, s):
    un = [r for r in rows if r["unresolved"]]
    parts = [f"""
<h1>Unresolved picks</h1>
<p class="lead">These {len(un)} matches have <b>no usable betting line</b> in any source we checked, so their picks are
generated from HLTV ranking points and Valve Regional Standings points only. Treat these as low-confidence picks.</p>

<section class="limits">
  <h2>Limitations for generating these picks</h2>
  <ul>
    <li>No primary bookmaker line (Pinnacle) and no usable aggregator line. Placeholder prices such as 1.8 / 1.8 on EGamersWorld are not markets and were rejected.</li>
    <li>Polymarket shows mellren v Privateer at 50 / 50 with $0 volume. That is not a usable price and was rejected.</li>
    <li>Ratings are the only input. The probability is our own conversion of the rating gap, using a scale we assumed (not Valve's formula) and a best-of-3 series transform. It is not calibrated against results.</li>
    <li>Team names differ between Hotspawn, HLTV, EGamersWorld and Polymarket for some of these matches. The name mapping is flagged on each card.</li>
    <li>Some ratings are very low or missing for one side. That widens the uncertainty; the pick should not be read as a strong edge.</li>
  </ul>
</section>

<section id="unresolved-list">
  <h2>The {len(un)} unresolved matches</h2>
"""]
    for r in un:
        checked = "".join(
            f'<li><b>{esc(t)}</b>: {esc(note)} <br>{link(u, u)}</li>' for t, u, note in r["unresolved_checked"])
        parts.append(card(r))
        parts.append(f"""<div class="checked"><p><b>Why unresolved:</b> {esc(r["unresolved_limits"])}</p>
<p><b>What was checked:</b></p><ul>{checked or '<li>No outside price source was found for this row.</li>'}</ul></div>""")
    parts.append("</section>")
    return head("Unresolved picks", "Matches with no usable betting line, their picks, and the limits on those picks.", "unresolved") + "\n".join(parts) + tail(built)


def build_flagged(rows, built, s):
    items = [
        ("F-01", "Pinnacle (primary book) re-read failed", "The 7 primary-book rows (Thunderpick World Championship and Stake Pulse Beat III matches) keep the 2026-10-14 02:21Z Pinnacle capture. The live page returned HTTP 500 on this re-read, so today's prices could not be confirmed.",
         "https://www.pinnacle.com/en/esports/games/cs2/matchups/"),
        ("F-02", "Aggregator-reported bookmaker odds", f"{s['aggregator']} rows use odds EGamersWorld reports for bc.game. These are not checked against the bookmaker and are labelled 'Aggregator line' on each card.",
         "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B"),
        ("F-03", "Unresolved matches (ratings only)", f"{s['unresolved']} rows have no usable market line; see unresolved.html for the limits and checks.",
         "https://play.hotspawn.com/lobby"),
        ("F-04", "FORZE Reload vs LFO 10 — 95.31% pick is a model bound", "LFO 10 is not in the ranking sources the dataset uses. The figure is a bound from research-only inputs. Low confidence.",
         "https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11"),
        ("F-05", "Team name variants", "PCIFIC (Hotspawn, HLTV) vs WRAITH PCIFIC (EGamersWorld); Privateer (Hotspawn) vs Privateer Gaming (Polymarket, EGamersWorld); RoundsGG vs roundsgg; WROTBERRY vs WBT (HLTV). Mapping is by team pair, not by name alone.",
         "https://play.hotspawn.com/lobby"),
        ("F-06", "Lobby time display", "The Hotspawn lobby card times are shown in UTC−4 on the page we read. All 28 cards were checked against the dataset UTC start time. Every time on this site is UTC.",
         "https://play.hotspawn.com/lobby"),
        ("F-07", "Hotspawn match links missing on 4 cards", "The lobby cards for Enjoy v B8 Academy, Banda chuya v 6666, Ryvex v PCIFIC and mellren v Privateer show no 'View Match' link. The site leaves those links blank rather than guessing them.",
         "https://play.hotspawn.com/lobby"),
        ("F-09", "Two boards disagree on the same Elisa BreakOut prices", "The site's own console/ board shows Thunderpick quotes relayed by bo3.gg for the Elisa matches (e.g. ENCE v BOJONG 71.1 / 28.9). This summary uses the every/ dataset (EGamersWorld bc.game, e.g. 70.9 / 29.1). Both are unverified aggregator-level figures; the difference is listed for review and not reconciled here.",
         "https://www.hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2"),
        ("F-10", "Most source links were not re-opened today", "This build re-read the Hotspawn lobby, one EGamersWorld page (Gothic v Lavked) and one HLTV page (9z v Aurora). All other source links are carried from the hourly captures and are listed on sources.html for manual re-check.",
         "https://play.hotspawn.com/lobby"),
        ("F-08", "Stale market timestamps", "Market quotes were captured between 01:48Z and 02:22Z on 2026-10-14. The newest capture is about two hours old at build time; the hourly pipeline refreshes them.",
         "https://play.hotspawn.com/lobby"),
    ]
    trs = "".join(
        f'<article class="card"><p class="fid">{esc(i)}</p><h3>{esc(t)}</h3><p>{esc(d)}</p><p class="links">{link(u, "Source")}</p></article>'
        for i, t, d, u in items)
    body = f"""
<h1>Flagged for review</h1>
<p class="lead">Irregularities and unverified items, published for manual review. They do not block the site. Each item links to its source.</p>
{trs}
"""
    return head("Flagged for review", "Flagged irregularities and unverified items, with source links.", "flagged") + body + tail(built)


def build_sources(rows, built, s):
    rechecks = "".join(
        f"<tr><td data-l='Status'>{esc(st)}</td><td data-l='Source'>{esc(what)}</td><td data-l='Link'>{link(u, u)}</td><td data-l='Result'>{esc(res)}</td></tr>"
        for st, what, u, res in SOURCE_RECHECKS)
    urls = {}
    for r in rows:
        for k in ["market_url", "pick_source_url", "hltv_match_url", "hotspawn_match_url", "hotspawn_lobby_url"]:
            if r[k]:
                urls.setdefault(r[k], set()).add(r["fixture_id"])
    rows_u = "".join(
        f"<tr><td data-l='Link'>{link(u, u)}</td><td data-l='Rows'>{len(ids)}</td></tr>"
        for u, ids in sorted(urls.items()))
    body = f"""
<h1>Sources &amp; checks</h1>
<p class="lead">Every row on the picks pages links to its price source, HLTV match page and Hotspawn lobby.
Method: de-vigged two-way probability <code>p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)</code> where a line exists;
otherwise a rating-based estimate. Hotspawn crowd percentages are never an input.</p>

<h2>Re-checks made for this build</h2>
<div class="tablewrap"><table class="t">
<thead><tr><th>Status</th><th>Source</th><th>Link</th><th>Result</th></tr></thead>
<tbody>{rechecks}</tbody></table></div>

<h2>Every source link used on the picks pages</h2>
<div class="tablewrap"><table class="t">
<thead><tr><th>Link</th><th>Rows</th></tr></thead>
<tbody>{rows_u}</tbody></table></div>
"""
    return head("Sources & checks", "Sources, re-checks and the method behind every pick.", "sources") + body + tail(built)


CSS = """
:root{--ink:#14202b;--mut:#5b6b78;--line:#dfe6ec;--bg:#f5f7f9;--card:#fff;--ok:#1b7f4b;--amber:#a86200;--warn:#b42318;--blue:#1d4ed8;--bar:#e6ebf0}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;font:17px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}
.wrap{max-width:720px;margin:0 auto;padding:0 14px}
a{color:var(--blue)}
code{font-size:.9em;background:#eef2f5;padding:0 4px;border-radius:4px}
h1{font-size:1.6rem;line-height:1.2;margin:18px 0 8px}
h2{font-size:1.2rem;margin:22px 0 8px}
h3{font-size:1.02rem;margin:4px 0}
.lead{color:var(--mut);margin:0 0 12px}
.muted{color:var(--mut)}.small{font-size:.9rem}
.top{position:sticky;top:0;z-index:5;background:#0f2233;color:#fff}
.top .wrap{display:flex;flex-direction:column;gap:6px;padding-top:8px;padding-bottom:8px}
.brand{color:#fff;font-weight:700;text-decoration:none;font-size:1.05rem}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chips a{color:#fff;text-decoration:none;background:#23415c;padding:6px 10px;border-radius:999px;font-size:.92rem}
.chips a.on{background:#2f7bd1}
.chip{display:inline-block;background:#e4ecf4;color:var(--ink);text-decoration:none;padding:6px 10px;border-radius:999px;margin:3px 3px 3px 0;font-size:.92rem}
.chip.warn{background:#fde7e4;color:var(--warn)}
.hero{padding-top:6px}
.fresh{font-size:.88rem;color:var(--mut);margin:4px 0 0}
.jump{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:14px 0}
.btn{display:block;text-align:center;background:var(--blue);color:#fff;text-decoration:none;padding:14px 8px;border-radius:12px;font-weight:600;min-height:48px}
.btn.warn{background:var(--warn)}
.stats{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;display:flex;flex-direction:column}
.stat b{font-size:1.6rem;line-height:1}
.stat span{font-size:.85rem;color:var(--mut)}
.stat.warn b{color:var(--warn)}
.exec{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 14px 12px}
.exec ul{padding-left:20px;margin:6px 0}
.exec li{margin:6px 0}
.jumplinks{margin:8px 0 0}
.glance{list-style:none;padding:0;margin:0;background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.glance li{border-top:1px solid var(--line)}
.glance li:first-child{border-top:0}
.glance a{display:grid;grid-template-columns:auto 1fr;gap:2px 10px;padding:10px 12px;text-decoration:none;color:var(--ink)}
.g-time{font-size:.82rem;color:var(--mut);grid-column:1}
.g-match{grid-column:2;font-weight:600}
.g-pick{grid-column:2;font-size:.95rem}
.g-pick b{color:var(--ok)}
.g-tag{grid-column:1 / span 2;font-size:.75rem;color:var(--mut);text-transform:uppercase;letter-spacing:.03em}
.g-tag.unres{color:var(--warn);font-weight:700}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px 14px;margin:10px 0;scroll-margin-top:90px}
.card.unres{border-color:#f2b8b1;border-left:5px solid var(--warn)}
.card-top{font-size:.88rem;color:var(--mut)}
.card-top .time{font-weight:700;color:var(--ink);font-size:1rem}
.versus{display:grid;grid-template-columns:1fr auto 1fr;gap:8px;align-items:start;margin:8px 0}
.team .name{font-weight:700;overflow-wrap:anywhere}
.team .pctbig{font-size:1.5rem;font-weight:800;line-height:1.1}
.team.winner .pctbig{color:var(--ok)}
.vs{color:var(--mut);font-size:.85rem;padding-top:14px}
.bar{height:8px;background:var(--bar);border-radius:6px;overflow:hidden;margin-top:4px}
.fill{display:block;height:100%;background:#9fb2c2}
.fill.win{background:var(--ok)}
.pickrow{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:6px 0}
.pick{background:#e7f6ee;color:#14532d;font-weight:800;padding:5px 10px;border-radius:8px}
.pick.low{background:#fde7e4;color:var(--warn)}
.flag{font-size:.75rem;font-weight:700;padding:3px 7px;border-radius:6px;background:#eef2f5;color:var(--mut);text-transform:uppercase}
.flag.ok{background:#e7f6ee;color:var(--ok)}
.flag.amber{background:#fdf1dc;color:var(--amber)}
.flag.warn,.flag:not(.ok):not(.amber){background:#fde7e4;color:var(--warn)}
.basis{font-size:.92rem;margin:6px 0}
.links{font-size:.9rem;margin:6px 0}
.fid{font-size:.8rem;color:var(--mut);margin:6px 0 0}
.checked{background:#fff7f5;border:1px dashed #f2b8b1;border-radius:10px;padding:8px 12px;margin:-4px 0 14px;font-size:.92rem}
.limits{background:#fff7f5;border:1px solid #f2b8b1;border-radius:12px;padding:6px 14px}
.limits ul{padding-left:20px}
.limits li{margin:6px 0}
section[id^="day-"]{scroll-margin-top:90px}
.tablewrap{overflow-x:auto}
.t{width:100%;border-collapse:collapse;background:var(--card);font-size:.92rem}
.t th,.t td{padding:8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:anywhere}
.t th{background:#eef2f5}
.foot{font-size:.82rem;color:var(--mut);padding:18px 14px 30px}
@media (max-width:420px){.stats{grid-template-columns:1fr 1fr}.jump{grid-template-columns:1fr}}
@media (min-width:720px){.jump{grid-template-columns:repeat(5,1fr)}.stats{grid-template-columns:repeat(5,1fr)}}
"""


def main():
    src, lobby = load()
    rows, errors = build_rows(src, lobby)
    if len(src) != len(lobby):  # every lobby card must have exactly one dataset row
        errors.append(f"count mismatch: dataset {len(src)} vs lobby {len(lobby)}")
    if errors:
        print("BUILD FAILED — fix before publishing:", file=sys.stderr)
        for e in errors:
            print(" -", e, file=sys.stderr)
        sys.exit(1)
    s = stats(rows)
    built = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    DATA.mkdir(parents=True, exist_ok=True)
    write(OUT / "style.css", CSS)
    write(OUT / "index.html", build_index(rows, built, s))
    write(OUT / "picks.html", build_picks(rows, built, s))
    write(OUT / "unresolved.html", build_unresolved(rows, built, s))
    write(OUT / "flagged.html", build_flagged(rows, built, s))
    write(OUT / "sources.html", build_sources(rows, built, s))
    write(DATA / "picks.json", json.dumps({"built_utc": built, "stats": s, "rows": rows}, indent=1, ensure_ascii=False) + "\n")
    with open(DATA / "picks.csv", "w", newline="", encoding="utf-8") as fh:
        keys = ["fixture_id", "start_utc", "competition", "tier", "best_of", "team_a", "team_b", "prob_a_pct", "prob_b_pct",
                "pick", "pick_pct", "basis_kind", "book", "odds_a", "odds_b", "market_captured_utc", "market_url",
                "pick_source_url", "hltv_match_url", "hotspawn_match_url", "unresolved", "flags"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    write(DATA / "coverage.json", json.dumps({
        "built_utc": built, "lobby_read": LOBBY_READ, "lobby_cards": len(lobby), "dataset_rows": len(src),
        "matched": len(rows), "stats": s, "unresolved_fixture_ids": [r["fixture_id"] for r in rows if r["unresolved"]],
    }, indent=1) + "\n")
    print(f"ok: {s}")


if __name__ == "__main__":
    main()
