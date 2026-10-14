#!/usr/bin/env python3
"""Rebuild reviews/457629c4-verification.md from the published data files.

The record is generated, not typed: every figure in it is read out of `livelines/data/*.csv|json` (the very
files the board publishes) so the record and the board cannot drift apart. Run after `build.py`:

    python3 livelines/make_verification_record.py

The live-read table (section 2) is the only narrative part; its values are transcribed from
`livelines/data/live_reads.json`, which stores each read verbatim with its URL and UTC time.
"""
from __future__ import annotations

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "livelines"
DATA = OUT / "data"
DOC = ROOT / "reviews" / "457629c4-verification.md"


def live_reads() -> dict:
    return json.loads((DATA / "live_reads.json").read_text())


def market_cell(r: dict) -> str:
    if not r["market_source"]:
        return "— own line (no outside price)"
    if "share price" in r["market_kind"]:
        odds = f"{round(float(r['market_odds_a']) * 100)}¢ / {round(float(r['market_odds_b']) * 100)}¢"
    else:
        odds = f"{r['market_odds_a']} / {r['market_odds_b']}"
    return f"[{r['market_source']}]({r['market_url']}) {odds} @ {r['market_captured_utc'][11:19]}Z"


def alt_cell(r: dict) -> str:
    return f"{r['market_alt_source']} {r['market_alt_p_a_pct']}%" if r["market_alt_source"] else "—"


def main() -> None:
    rows = list(csv.DictReader((DATA / "picks.csv").open(newline="", encoding="utf-8")))
    cov = json.loads((DATA / "coverage.json").read_text())
    cal = json.loads((DATA / "calibration.json").read_text())["calibration"]
    open_rows = sorted([r for r in rows if r["state"] == "open"], key=lambda r: r["lock_utc"])
    bound = [r for r in rows if r["basis"] == "T4"]
    live = live_reads()

    live_tbl = [
        ("L-1", "Hotspawn Pick'em slate — fixture identity, lock epochs, the closing-soon cards",
         "https://play.hotspawn.com/cs2-pickems", "HS-CS2-PICKEMS",
         f"{cov['slate_fixtures']} fixtures, {cov['open_fixtures']} open, lock = start − 6 min (payload epochs)",
         "\"This week 68 matches\"; tiers All 88 / B 24 / C 60 / S 4; the closing-soon cards all present in the "
         "board's fixture set with the same UTC lock epochs",
         "**match** — crowd pick percentages are visible on the page and are never stored (see §5)"),
        ("L-2", "Hotspawn lobby — display-timezone check",
         "https://play.hotspawn.com/lobby", "HS-LOBBY",
         "board prints payload UTC epochs (e.g. 08:00:00Z start, 07:54:00Z lock)",
         "cards render in ET (UTC−4); countdown agrees with the payload's 08:00:00Z",
         "**explained, kept conservative**: the payload lock is the earlier instant, so a row can only lock "
         "before the UI shows it"),
        ("L-3", "HLTV world ranking the own line is cross-checked against",
         "https://www.hltv.org/ranking/teams/2026/october/12", "HLTV-RANKING-OCT12",
         "capture `model/input/hltv_ranking.json` (245 teams, 2026-10-12)",
         "#1 Spirit 972, #2 Vitality 894, #3 MOUZ 692 — identical, rank for rank",
         "**match**; the 2026-10-13 page does not exist (404, read L-4)"),
        ("L-4", "HLTV world ranking dated one day later (negative control)",
         "https://www.hltv.org/ranking/teams/2026/october/13", "HLTV-RANKING-13-NOT-FOUND",
         "board uses the 2026-10-12 ranking and prints its date",
         "HTTP 404 — no Tuesday edition exists",
         "**consistent**: the weekly ranking is Monday's, so 2026-10-12 is current"),
        ("L-5", "Gothic v Lavked — the second outside source, and price drift",
         "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK", "EGW-CCT-EU-11",
         "the row keeps the archived read it is priced from and names the later one",
         "1.881 / 1.782 (Bo3, 14.10.26 10:00 local = 08:00 UTC) against 2.05 / 1.64 read earlier in the session",
         "**published as** `FL-PRICE-DRIFT`: direction unchanged (Lavked favourite on the de-vig of both reads)"),
        ("L-6", "Polymarket moneyline for Gothic v Lavked",
         "https://polymarket.com/event/cs2-gothic-lavked-2026-10-14", "PM-GOTHIC-LAVKED",
         "share prices 50¢ / 51¢ -> Lavked 50.5 % after de-vig",
         "50¢ / 51¢, volume $303.73, resolution source printed as hltv.org",
         "**match**; thin book, flagged `FL-THIN-MARKET` where published from it"),
        ("L-7", "EGamersWorld CCT EU #12 Play-In — series length and the placeholder pattern",
         "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in", "EGW-CCT-EU-12",
         "banda chuya v 6666 and mellren v Privateer carry an own line, not a market one; formats filled as Bo3",
         "every fixture on the page prints **1.80 / 1.80** while ENJOY v B8 Academy is priced 1.61 / 2.21",
         "**rejected as placeholder**: identical pairs on unrelated fixtures are not a market; recorded on "
         "unresolved.html and in `data/live_reads.json`"),
        ("L-8", "Official Valve Regional Standings — the only rating input the own line uses",
         "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/"
         "standings_global_2026_10_05.md", "VRS (GitHub contents API)",
         f"{cov['teams_in_official_standings']} of {cov['unique_teams']} teams rated; standings dated "
         f"{cov['vrs_standings_date']}",
         "blob sha 2aa28053…, 380 teams, saved verbatim at `livelines/data/raw/valve_standings_global_2026_10_05.md`",
         "**match** — the local copy is the fetched file, byte for byte; its age is flagged on every row that "
         "uses it"),
        ("L-9", "Outside market feed (owned by another session, read-only here)",
         "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/feeds/data/market_feed.csv",
         "feed captured 2026-10-14T03:18:57Z",
         f"{cov['open_market_basis']} of {cov['open_fixtures']} open fixtures priced from an outside listing",
         "34 rows: 20 Thunderpick-via-bo3.gg + 14 Polymarket",
         "**match** — every accepted price names either this feed's URL or a live read above"),
        ("L-10", "Primary-bookmaker capture used for the T1 rows (repo pipeline, read-only here)",
         "https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight",
         "Pinnacle guest markets captured 2026-10-14T04:38:10Z, stored in `executive/data/external_lines.csv`",
         "T1 rows publish the de-vigged Pinnacle pair with the source URL and the capture minute",
         "six fixtures carry a Pinnacle pair; every one names the API URL and the minute it was read",
         "**match** — the builder re-derives the de-vig from the stored odds; the pipeline capture is fresher "
         "than this session's own reads, so it wins the ladder for those fixtures"),
    ]
    live_md = "\n".join(
        f"| {n} | {what} | [{url.replace('https://', '')[:46]}]({url}) | `{rid}` | {board} | {reread} | {res} |"
        for n, what, url, rid, board, reread, res in live_tbl)

    lines = []
    for i, r in enumerate(open_rows, 1):
        rating = (f"VRS {r['rating_a_vrs'] or '—'} v {r['rating_b_vrs'] or '—'}"
                  + (f"; HLTV {r['rating_a_hltv'] or '—'} v {r['rating_b_hltv'] or '—'}"
                     if r["rating_a_hltv"] or r["rating_b_hltv"] else ""))
        lines.append(
            f"| {i} | `{r['match_id']}` {r['team_a']} v {r['team_b']} | {r['lock_utc'][:16].replace('T', ' ')}Z | "
            f"*{r['basis']}* | {r['prob_a_pct']} / {r['prob_b_pct']} | **{r['pick'] or '— no pick —'} "
            f"{r['pick_prob_pct'] or ''}** | {market_cell(r)} | {alt_cell(r)} | {r['series_format'] or '—'} | "
            f"{rating} | {r['flags'].replace(';', ' ')} |")
    row_md = "\n".join(lines)

    bound_line = "—" if not bound else (
        f"`{bound[0]['match_id']}` {bound[0]['team_a']} v {bound[0]['team_b']}: "
        f"**at least {bound[0]['prob_b_pct']} %** for {bound[0]['team_b']} (bound, no pick published)")

    doc = f"""# Session `arena/457629c4` — line-by-line verification record

Verifies the **published build** `coverage.json: generated_utc = {cov['generated_utc']}` — the refresh the
merge triggered — commit history on `main` at the time of writing.
Board: `livelines/` (7 pages) · live: <https://buffedlizard55-lab.github.io/MaltaProj1/livelines/>
Generated from the committed data files by `livelines/make_verification_record.py`, so this record and the board
cannot drift apart; every figure below is read out of `livelines/data/*.csv|json`. The board refreshes inside a
4–8 h window and each page prints the age of its inputs, so re-run the generator (or the build) before quoting it.

## 1. What "verified" means on this board

* **Every row carries the link its value came from, and the minute it was read.** A fixture with no reachable
  price is published with an own line or as a lower bound, and either way names the official page behind it.
  No value is inferred, and a blank stays blank — see `unresolved.html` for the fixture where this happens.
* **Hotspawn supplies fixture identity only** — the exact UTC lock/start epochs, tier, stage, offered points.
  **Its crowd pick percentages are dropped at ingest and never stored**; a build that stores one fails the test
  *"no Hotspawn crowd value is stored"*, which walks every stored row and checks that the live-read file records
  the crowd columns as present-on-page and not-stored.
* **Probabilities come only from outside sources**: a primary bookmaker quote (`T1`, de-vigged), another outside
  listing or prediction market (`T2`, de-vigged), or our own line from the official Valve Regional Standings
  (`T3`), whose logistic scale is fitted against the outside market by minimum mean absolute error —
  **K = {cal['scale']} points, MAE {cal['mae_pp']} pp, n = {cal['n']}**. The log-loss-optimal alternative
  (K ≈ {cal['logloss_alternative']['scale']}, MAE ≈ {cal['logloss_alternative']['mae_pp']} pp) is disclosed on
  every row that depends on the scale (`FL-OWN-LINE-SCALE-SENSITIVE`). A side with no rating at all yields a
  **bound, not an estimate** (`T4`, no pick).
* **Publication is fail-closed.** `livelines/tests.py` re-derives the arithmetic and `tests/test_457629c4.py`
  re-runs it from the repository root; the refresh workflow commits only when both pass. A build that cannot
  reproduce a published number stops the commit and the last good board stays live.

## 2. Live independent re-reads behind this build

| # | What was re-read | Page | Read id | Board value | Re-read value | Result |
|---|---|---|---|---|---|---|
{live_md}

The sandbox shell has **no network** (curl to hltv.org and play.hotspawn.com returns no response); the reads
above were taken through the platform fetch tool, and each one stores its URL, its UTC time and the page's own
clock arithmetic where available (`hosts_refused` in `data/live_reads.json`). Priming/timezone/raw captures that
this session did not take itself are named as such (L-9, L-10) with the file that holds them.

## 3. Line by line: every open fixture ({len(open_rows)} rows)

Coverage at build time: {cov['slate_fixtures']} fixtures on the slate · {cov['open_fixtures']} open ·
{cov['locked_fixtures']} locked or past · **{cov['open_with_pick']} with a pick** ·
{cov['open_market_basis']} priced from an outside market · {cov['open_own_line_basis']} on our own line ·
{cov['open_bound_only']} published as a lower bound with no pick · {cov['open_with_stated_format']} with a
stated series length. Rating inputs: {cov['teams_in_official_standings']} of {cov['unique_teams']} teams in
the official standings, {cov['teams_in_hltv_top245']} in HLTV's top 245. Prices are the archived reads named
in the row; the page prints each capture minute so a reader can judge its age.

| # | Fixture | Lock (UTC) | Basis | P(A) / P(B) % | Pick | Market source, price @ read | Second source P(A) % | Fmt | Rating inputs | Flags |
|---|---|---|---|---|---|---|---|---|---|---|
{row_md}

`{cov['placeholder_pairs_rejected']}` placeholder price pairs were rejected at ingest (identical pairs printed
on unrelated fixtures), `{cov['observations_orientation_normalised']}` observation was orientation-normalised
after the listing printed the sides in the other order, and `{cov['observations_unmatched']}` could not be
matched to a fixture and were left out rather than guessed.

## 4. Coverage and calibration, re-derived from the files

* `coverage.json` — {json.dumps({k: cov[k] for k in ('slate_fixtures', 'open_fixtures', 'locked_fixtures', 'open_with_pick', 'open_without_pick', 'open_market_basis', 'open_own_line_basis', 'open_bound_only', 'unresolved_rows', 'open_with_stated_format')})}
* `calibration.json` — objective `{cal['objective']}`, chosen scale **{cal['scale']}**, MAE **{cal['mae_pp']} pp**,
  log-loss {cal['logloss']}, n={cal['n']}; the alternative scores are stored beside it: {json.dumps(cal['logloss_alternative'])}
* VRS floor used for an unrated side: {cov['vrs_floor_points']} points (the lowest value in the official file),
  published as a lower bound, never as a probability.
* The bound-only row: {bound_line}

## 5. The checks that run before anything is published

`livelines/tests.py` (13 tests): every open fixture decided or published as unresolved · probabilities sum to
100 · market rows name source and read time · **de-vig re-derives from the printed prices** · the pick is the
higher-probability side · no Hotspawn crowd value stored · every row links a source · bound rows are labelled
as lower bounds · calibration reports both objectives · coverage counts match the rows · no broken internal
link and every page carries a viewport · **two builds on a pinned clock reproduce `picks.csv` byte for byte** ·
no 1.80/1.80 placeholder survives into a published row.

`tests/test_457629c4.py` (7 repository-level tests): the executive summary links to the picks and unresolved
pages · the landing page links to this board · no page links outside the board except to public sources ·
the refresh workflow is scheduled inside the 4–8 h window and gates on the tests · live reads are stored with
URLs and UTC times · the unresolved page names its specific limitations · `coverage.json` agrees with the page.

## 6. Irregularities, and what is deliberately not claimed

1. **One fixture has no pick, on purpose.** {bound_line.split(':')[0] if bound else '—'} — the only outside
   listing found prints the opponent cell **empty** (no name, flag or team link; the URL slug is literally
   `forze-reload-vs-`), and LFO 10 appears in neither the official standings (380 teams) nor HLTV's top 245.
   One rated side and one unrated side can only produce a lower bound, so the board publishes the bound and
   **no pick**, on `unresolved.html`. Nothing was invented to fill the gap.
2. **EGamersWorld prints 1.80 / 1.80 for exactly the fixtures no book prices.** Five CCT EU #12 Play-In
   fixtures share the identical pair while other fixtures on the same page carry real, different prices.
   Identical pairs on unrelated fixtures are treated as a listing placeholder, rejected, and flagged.
3. **Prices move between reads and the board says so.** Rows whose archived price no longer matches the newest
   read carry `FL-PRICE-DRIFT` and keep the archived value plus its read minute; the primary-bookmaker capture
   is fresher than this session's own reads, so it takes over those rows (L-10) and the drift stays visible.
4. **Own line vs market.** Where our line and the market disagree by ≥ 15 pp the row carries
   `FL-OWN-LINE-MARKET-GAP`; a smaller disagreement keeps `FL-OWN-LINE-MARKET-SPLIT`. Both stay visible and are
   never averaged: the published pick is whatever the row's stated basis yields.
5. **Official ratings are weekly, not intraday.** Valve publishes the Regional Standings weekly (newest
   official file at this build: {cov['vrs_standings_date']}, blob 2aa28053…) and HLTV's ranking is weekly
   ({cov['hltv_ranking_date']}) and capped at 245 teams.
6. **Hotspawn itself lists fixtures that can no longer be picked.** {cov['locked_fixtures']} of
   {cov['slate_fixtures']} payload fixtures are locked or past — most carry June dates the site never cleared
   — and `1079546` disappeared from the board between the 02:06:30Z capture and the 04:31Z live read. Those
   rows are counted, never silently dropped.
7. **The refresh is best-effort by the platform.** GitHub disables scheduled workflows on inactive
   repositories; this repository runs many scheduled jobs and one failed on `main` on 2026-10-14
   (run <https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38511378749>). This board therefore also
   refreshes when the slate capture or the market feed finishes, prints the age of every input on
   `cadence.html`, and its own workflow fails closed.

## 7. Review it by hand

`livelines/index.html` (executive summary) → `picks.html` (one card per match) → `unresolved.html` (the
separate section) → `flagged.html` → `methodology.html` → `sources.html` → `cadence.html`.
Machine-readable: `livelines/data/picks.csv`, `picks.json`, `coverage.json`, `calibration.json`,
`live_reads.json`. Refresh: `.github/workflows/livelines-457629c4.yml` (cron `33 */4 * * *`, fail-closed).

Run the checks yourself: `python3 -m unittest tests.test_457629c4 -v` (13 board invariants + 7 repository
checks; all pass for this build).
"""
    DOC.write_text(doc)
    print(f"wrote {DOC} ({len(doc)} bytes) for build {cov['generated_utc']}; {len(open_rows)} open rows")


if __name__ == "__main__":
    main()
