# Line-board verification report — session `arena/180a42a0`

Scope: the Hotspawn Play pick'em slate and the line board this session publishes under `slate/`.
Everything below is checkable from the repository and from the linked public pages. Nothing in this
report corrects another session's file; disagreements are recorded and left in place.

## 1. What was read, and when

| Source | URL | How | Result |
|--------|-----|-----|--------|
| Hotspawn Play — lobby, CS2, Thunderpick, LoL pick'ems | `play.hotspawn.com/{lobby,cs2-pickems,thp-pickems,lol-pickems}` | server-rendered `ng-state` payload, in the CI job | 388 fixtures, 262 with a lock time still ahead of the capture |
| Hotspawn match index | `www.hotspawn.com/matches` | read by this session (the CI runner receives HTTP 403 from this host) | per-match URLs for the fixtures it lists; its own times are printed with an explicit `UTC` suffix and agree with the payload epoch |
| HLTV world ranking | `hltv.org/ranking/teams/2026/october/12` | fetcher | 245 teams with rank + points (the source of the HLTV half of the originated line) |
| HLTV upcoming matches | `hltv.org/matches` | fetcher | HTTP 403 ("Just a moment…") on every attempt — recorded as a refusal, never filled in; the kickoff cross-check therefore uses the listing another session captured (`verify/data/hltv_listing.csv`, converted from its printed UTC−4 to UTC) |
| Valve Regional Standings | `github.com/ValveSoftware/counter-strike_regional_standings` `live/2026/standings_global_2026_10_05.md` | fetcher | 380 rated rows; the source of the Valve half of the originated line |
| Pinnacle public guest API | `guest.api.arcadia.pinnacle.com` via `pinnacle.com/en/esports/games/cs2/matchups/` | fetcher | moneyline quotes served: `/leagues/{id}/matchups` (plain shape) answered where the `withSpecials` shape returned 403 |
| EGamersWorld | `egamersworld.com/counterstrike/matches`, event pages | session read through the project's fetch service; the CI runner gets HTTP 403 | 15 prices read by this session, each row carrying its page URL and read time |

Every fetch is logged with status, byte size and SHA-256 in `slate/data/provenance.json`; the CI
job's own log is committed to `slate/data/last_run.log` on the branch.

## 2. Coverage

Per-page totals in the capture (a fixture can appear on more than one page):

| Page | Rows in payload | stale (start in the past) | started | open |
|------|-----------------|---------------------------|---------|------|
| `lobby` | 90 | 59 | 2 | 29 |
| `cs2-pickems` | 89 | 59 | 1 | 29 |
| `thp-pickems` | 13 | 0 | 0 | 13 |
| `lol-pickems` | 298 | 55 | 10 | 233 |

- The union is 388 fixtures; 262 have a lock time in the future. Every one of them is published in
  `slate/fixtures.html` with its exact UTC start/lock epoch and the page it came from — the board
  never drops a row it cannot price; it publishes it blank and flags it.
- **Hotspawn's own counters do not match the payload it serves.** The CS2/Thunderpick/lobby pages
  print "68 matches this week" and the LoL page prints "131"; the payload yields 30 CS2 fixtures
  with a start inside the current week window and 97 LoL. Both numbers are recorded in
  `slate/data/coverage.json` and on the Flagged page (`S-F-02`); the payload list is treated as the
  authoritative coverage and the printed counters are not used for anything.
- Stale rows (start weeks in the past, still listed) are published, marked, and never given a line
  or pick (`S-F-03`).

## 3. Market readings — three provenance classes, never mixed silently

Per row the headline price is, in order: (1) the price this CI run read from Pinnacle, (2) the price
this CI run read from an EGamersWorld page if it served one, (3) a price this session read through
the project's fetch service (recorded in `slate/data/market_readings_session.csv` with its page URL
and read time), (4) failing all of those, the newest source-linked price already published in this
repository. Class 4 is always labelled with the session that read it and its capture time, and is
listed on the Flagged page (`S-F-16`); class 3 is labelled `session arena/180a42a0` and flagged
(`S-F-18`). Every reading, including superseded ones, is published in `slate/data/lines.csv`.

De-vig: `p_a = (1/o_a) / (1/o_a + 1/o_b)`; the overround is `(1/o_a + 1/o_b − 1)·100`.

In the capture committed as `slate/data/coverage.json` (generated 2026-10-13T23:33:05Z): Pinnacle read
15 matchups, all 15 carrying an open moneyline (808 related markets seen, 793 declined as
handicap/total/alternate markets); this session's capture file contributed 13 matched readings,
2 unmatched because their fixtures had already started; the carried class supplied the headline for
9 fixtures whose own page neither this run nor this session could read. 25 of 29 CS2 fixtures and 4
of 233 LoL fixtures carry a market line; nothing is estimated for the rest.

## 4. Own originated lines

`own_p_a` = mean of two independent estimates, each converted to a series probability:

- HLTV ranking points → Elo (`1/(1+10^((p_b−p_a)/400))` on the ranking points)
- Valve Regional Standings points → the same Elo form

Series transform: BO1 identity, BO3 `p²(3−2p)`, BO5 `p³(10−15p+6p²)`. Where no source states the
format, BO3 is assumed **and the row says so** (`S-F-08`). A team with no exact name match in either
official source gets no rating and its fixture gets **no** originated line (`S-F-04`, `S-F-11`).

Aliases are used only with an evidence link (`slate/aliases.json`), each use stays visible on the
row and on the Flagged page (`S-F-06`):

| Hotspawn spelling | Official spelling | Evidence |
|---|---|---|
| WROTBERRY | WBT | HLTV match 2399418 "WBT vs. EAC", Elisa BreakOut Series 2, same slot |
| RoundsGG | ROUNDS (HLTV team 12457) | HLTV event 9332 lists the same three group-B slots |
| Envy | 3DMAX | HLTV team 5991 roster = the roster Valve lists as 3DMAX (points 1500) |
| EAC | EA Copenhagen (price-source spelling only) | EGamersWorld's Elisa page prices "WBT vs EA Copenhagen" in the slot the payload carries as "WROTBERRY vs EAC at 08:00Z"; the other three participants match exactly |

## 5. Cross-table comparison (read-only)

Rows this capture publishes vs rows of the same fixtures in the repository's other tables:

| Table | Open fixtures matched |
|-------|----------------------|
| `today/data/current.csv` | 121 / 262 |
| `picks/data/fixtures.csv` | 29 / 262 (CS2 only) |
| `board/data/analysis.csv` | 29 / 262 (CS2 only) |
| `verify/data/verification.csv` | 29 / 262 (CS2 only) |
| `model/data/lines.csv` | 25 / 262 (CS2 only) |

For the 29 CS2 fixtures, value-level comparison:

- De-vigged market probabilities agree between this board and the other tables to within about one
  point on most rows; the visible differences (e.g. `Zomblers vs Overtake Sector` 34.3 here vs 37.0
  in `board/` and 38.0 in `picks/`; `9z vs Aurora` 26.9 vs 25.0 vs 23.9) are consistent with prices
  moving between read times (22:00–23:38 UTC) — the pick side is identical in every table that has
  a price for the fixture. No contradicted pick was found.
- Originated lines differ more, and are expected to: this board averages HLTV ranking points and
  Valve standings points; `board/` uses a Valve-only model; `picks/` uses its own. Example: `Heroic
  vs Envy` 44.8 here vs 52.5 in `board/`. The two are not the same quantity, so the board never
  presents them as a disagreement; only market-vs-model divergence within one row is flagged
  (`S-F-09`).
- Kickoff cross-check against the other sessions' HLTV listing: **23 agree, 0 differ** for the
  fixtures both tables carry. Doing that check needed a deliberate conversion: that file's printed
  times are UTC−4 (its `18:00` is this board's `22:00Z`), so `slate/verified.html` converts it and
  says so in the column heading.

## 6. Irregularities found (all verifiable from the links)

1. **EGamersWorld shows a placeholder `1.80 / 1.80` for fixtures it has no price for.** Seen on the
   CCT Europe #11 event page for `FORZE Reload vs <opponent not rendered>` and `ex-RUSTEC vs
   mellren` while the same fixtures carry real prices on EGW's own listing. A placeholder pair is
   never used as a price; the affected row is left blank or keeps an older labelled reading.
   (`egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK`)
2. **EGamersWorld's match widget rendered `0 / 0` for all four Stake Pulse Beat III fixtures** at
   read time while its own schedule row carried a real price for `Astralis vs Sashi`; the other
   three rows on this board therefore carry the older labelled readings. (`…/stake-pulse-beat-iii-EJZmJpBjeNx`)
3. **Printed times on the pick'em pages are viewer-local; the payload epoch and the countdown are
   authoritative.** The same fixture is printed `18:00` in one render and `22:00` in another for an
   epoch of `2026-10-13T22:00:00Z`, and `www.hotspawn.com/matches` prints the same fixture as
   `22:00 UTC`. This is why `verify/data/hltv_listing.csv` needs +4 h before comparing, and why no
   time on this board is taken from printed text (`S-F-01`).
4. **Hotspawn header counters vs payload:** see §2 — 68 / 131 printed, 30 / 97 in the week window
   by payload epoch. Recorded, not reconciled; both are published.
5. **`/matches/<id>` alone is not a per-match page** — it redirects to the matches index (tested with
   id 1079624). Per-match pages need the slug, e.g.
   `www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624`. This board
   attaches the slug form when the index serves it; tables that publish the bare-id form are flagged
   here for their owner rather than edited.
6. **`www.hotspawn.com/matches` refuses the CI runner (HTTP 403)** while `play.hotspawn.com` serves
   it fine, so the scheduled job cannot attach per-match Hotspawn URLs; the build omits the cell
   rather than guessing the slug. (Read successfully by this session, which is how the per-match URL
   shape and the explicit `UTC` times in irregularity 3 were confirmed.)
7. **`FORZE Reload vs LFO 10` (14 Oct 17:00Z) cannot be priced from the sources read so far.** LFO 10
   has no row in the HLTV ranking (team page exists: `hltv.org/team/14084/lfo-10`) and none in the
   Valve standings, and EGW shows the placeholder pair for it. The row is published blank with
   `S-F-04`/`S-F-11` and its HLTV match link (`hltv.org/matches/2399301/…`) for manual review.
8. **Nine fixtures are priced from a carried reading** where neither this run nor this session could
   read a fresh price; each is labelled with the reading session and its capture time and flagged
   (`S-F-16`).

## 7. How to re-check

- Rebuild everything: `.github/workflows/slate-180a42a0.yml` (dispatch, or wait for the 3-hourly
  schedule). It re-reads the sources, rebuilds `slate/`, runs the 14 offline tests and commits both
  the data and the pages back to the branch it ran from.
- Locally: `python3 slate/collect.py && python3 slate/build.py && python3 slate/tests.py`.
- The latest job log is committed as `slate/data/last_run.log`; per-source status/SHA-256 is in
  `slate/data/provenance.json`; every price reading is in `slate/data/lines.csv`; the per-fixture
  checks are in `slate/data/audit.csv` and on `slate/verified.html`.

## 8. Links for manual review

- Board: `slate/index.html` · CS2: `slate/cs2.html` · all fixtures: `slate/fixtures.html` ·
  market lines: `slate/lines.html` · own lines: `slate/own-lines.html` · verification:
  `slate/verified.html` · flagged: `slate/flagged.html` · sources: `slate/sources.html`
- Hotspawn: `play.hotspawn.com/cs2-pickems`, `www.hotspawn.com/matches`
- HLTV: `hltv.org/ranking/teams/2026/october/12`, match pages as linked per row
- Valve: `github.com/ValveSoftware/counter-strike_regional_standings` (`live/2026/standings_global_2026_10_05.md`)
- Pinnacle: `pinnacle.com/en/esports/games/cs2/matchups/`
- EGamersWorld: `egamersworld.com/counterstrike/matches` and the event pages linked per row
