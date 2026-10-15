# Verification record — every-match Hotspawn CS2 picks board (`arena/b44b5d5e`)

Session: `arena/b44b5d5e-maltaproj1` · branch `arena/b44b5d5e-maltaproj1` · board: `matchpicks/`
Written 2026-10-15 (UTC). Every row on the board links the source it was read from; this file records
**how those sources were checked**, what was found, and what is still unverified.

## 1. What the board claims, and what backs it

| Claim on the board | Source of record | Verification performed |
| --- | --- | --- |
| The Hotspawn Pick'em lobby lists **80 CS2 fixtures**, of which 59 are stale listings from 26 Jun – 10 Jul 2026 | `https://play.hotspawn.com/lobby` (Angular TransferState payload, read every run) | Count re-derived from the committed capture (`matchpicks/data/snapshot.json`: `state_rows = complete_rows = 80`, `incomplete_rows = 0`). Stale-date range printed from `fixtures.csv`. |
| Fixture identity, tier, offered points, exact `start_utc` / `lock_utc` | same payload (`match_id`, `tier`, `points`, `scheduled_start_time`, `lock_time`) | Read directly; the board publishes the epoch-derived UTC value, not a rendered string. |
| **No crowd pick percentage is ever used** | — | Enforced in code: crowd fields are dropped at ingest (`crowd_fields_dropped` counted per capture, 1437 in the capture of 08:27Z) and the build fails if the string `crowd` appears in a row; a data test re-checks the committed CSV. |
| Outside price #1: **Pinnacle** (public guest response the matchups page loads itself) | `https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups?withSpecials=false` via `https://www.pinnacle.com/en/esports/matchups/highlights/` | 14 whole-match quotes in the capture; American prices converted to decimal, de-vigged with the stored formula and re-derived by `tests/test_b44b5d5e_data.py`. |
| Outside price #2: **Polymarket** (prediction market, never de-vigged, labelled) | `https://gamma-api.polymarket.com/…` via the public event page | 6 quotes with volume/liquidity and `observed_utc`; flagged MP-F25 so it is never read as a bookmaker price. |
| Own originated line (probabilities per team for **every** fixture a source can price) | official **Valve Regional Standings** file, else the official **HLTV world ranking #** | Re-derived from the stored VRS points / rank pair by the data test; per-map → series conversion uses the exact best-of enumeration only when the series length is sourced, otherwise the row says `per-map` and is flagged MP-F05. |
| **Series length** where published | Hotspawn payload (never states one) → HLTV match list captured live → hand-checked official HLTV match/event page (`matchpicks/series_research.csv`) → official match page linked by the verified result trail | 74 of 80 rows now carry a sourced length (53 from the result trail's official match pages, 15 from a researched HLTV match page, 6 from a researched HLTV event page); 6 rows stay blank and flagged MP-F05. Sources re-read by hand on 2026-10-15 — see §2. |
| Results for played fixtures | repository result trail, every row carrying an official HLTV/Liquipedia URL and its own read time | 54 rows publish a result with a link; 6 rows are recorded as unresolvable (DraculaN, see §3); 20 rows have no independent result on file and say so. **Hotspawn's payload is never used for a score** (see §3, I2). |
| Stale/ambiguous fixtures are never silently dropped | `matchpicks/data/unresolved.csv` + `unresolved.html` | 24 unresolved rows with the reason and the flags on each; ids of markup-only fixtures are listed inside one grouped row instead of being invented as fixtures. |

## 2. Independent re-reads performed by this session (2026-10-15, UTC)

| Fixture | Page read | Page says | Board row |
| --- | --- | --- | --- |
| `1080280` ENCE vs BOJONG (Elisa BreakOut Series 2) | `hltv.org/matches/2399419/ence-vs-bojong-elisa-breakout-series-2` | "Best of 1 (LAN)", Group A, 15 Oct 06:00 | `series = BO1`, scheduled — agrees |
| `1080202` 9z vs Falcons (Thunderpick WC 2026) | `hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026` | "Best of 3 (LAN)", Group A winners' match, 15 Oct 07:00, HLTV forecast 9z 17.4 % restated as core winrate | `series = BO3`, market pick Falcons — agrees |
| `1081105` SUKEBAN vs your end (CCT SA S7) | `hltv.org/matches/2399460/your-end-vs-sukeban-cct-2026-south-america-series-7` | "Best of 3 (Online)", Swiss R1, **SUKEBAN forfeited** → 1-0 default; your end VRS #300, SUKEBAN unranked | `result = your end 1-0` (trail), `series = BO3`, no pick (both sides unpriced and one unranked) — agrees |
| `1079621` Gothic vs Lavked (CCT Europe S11) | `hltv.org/matches/2399298/gothic-vs-lavked-cct-2026-europe-series-11` | "Best of 3 (Online)", Swiss R1, **Gothic forfeited** → Lavked 1-0 | `series = BO3` from the same page; result published from the trail — agrees |
| Stale row `1051301` CYBERSHOKE Prospects vs PCIFIC | `hltv.org/matches/2395413/cybershoke-prospects-vs-pcific-myskill-lg-ultragear-tournament-2026` | "2 : 0", 26 Jun 2026, "Best of 3 (LAN)", Grand final | trail row `2-0 bo3` — agrees |
| Stale row `1052746` Fortress vs Endless Journey | `hltv.org/matches/2395499/fortress-vs-endless-journey-european-pro-league-series-8-closed-qualifier` | "0 : 2" (Endless Journey), 26 Jun 2026, "Best of 3 (Online)" | trail row `Endless Journey 2-0 bo3` — agrees |
| Elisa BreakOut Series 2 format for all 12 listed fixtures | `hltv.org/events/9332/elisa-breakout-series-2` (read 2026-10-15; re-read 502 at 09:0xZ) + `liquipedia.net/counterstrike/Elisa/BreakOut_Series/2` | every group match Best of 1 | 12 rows `BO1` — agrees |
| Stake Pulse Beat III (`1079440`, `1079442`) | `hltv.org/events/9223/stake-pulse-beat-iii` | Formats: "Group stage: GSL Bo3 / Playoffs: Single elimination Bo3" | 2 rows `BO3` — agrees |
| CCT 2026 Europe Series 12 Closed Qualifier (`1081120` mellren–Privateer) | `hltv.org/events/9456/cct-2026-europe-series-12-closed-qualifier` + the HLTV match list row "16:00 bo3 … Group D Elimination Match" | "Group stage: GSL Bo3" | row `BO3` — agrees |
| Official ratings used by the own line | `github.com/ValveSoftware/counter-strike_regional_standings` (latest published file **2026-10-05**), `hltv.org/ranking/teams/2026/october/12` | as cited on the rows | rows cite file date and URL; the age of the VRS file is disclosed as a limitation on the board. |

## 3. Irregularities found (all published on the board's "Flagged for review" page)

* **I1 — duplicate flag code.** `MP-F32` was defined twice in `FLAG_TEXT` ("result unverified" and
  "capture gap closed"), so one meaning silently overwrote the other and the flagged page explained
  the wrong thing. Fixed: `MP-F32` = result unverified, the capture-gap flag is now `MP-F34`, and the
  flagged page renders **every** documented code, including codes no row raised in a capture.
* **I2 — Hotspawn publishes no usable score.** Every fixture in the payload, including ones from
  26 June, is `status = "scheduled"` with `0-0`. The board therefore never publishes a payload score
  as a result; results come only from the independent trail with the official page linked. Flag
  MP-F31/MP-F32 cover the cases where nothing independent exists.
* **I3 — cross-sport id inflation.** The first capture reported 244 "CS2" ids that only exist in page
  markup; they were fixtures of other sports on the same lobby. The collector now subtracts payload
  ids of **all** sports (`payload_ids_all`), and the current capture reports `dom_only_ids = 0`.
* **I4 — DraculaN Season 7 date contradiction (6 rows).** Hotspawn lists six fixtures dated
  26–28 Jun 2026 (ids `1051339`–`1051344`); HLTV's Digital Crusade DraculaN Season 7 runs 19–23 Oct
  2026. No result is published for these rows (trail status `unresolved`, reason quoted) and no series
  length is invented; they are on the unresolved page and flagged MP-F04/MP-F32.
* **I5 — forfeits presented as scores.** `1081105` (1-0, SUKEBAN forfeit) and `1079621` (Lavked 1-0,
  Gothic forfeit) are defaults, not played series. The board labels them as recorded by the official
  match page; a reader must not treat the 1-0 as a map score.
* **I6 — live source refusals from the automated runner.** HLTV's `/matches` page answers the runner's
  browser with Cloudflare's "Just a moment…" interstitial (HTTP 403, recorded per capture) and
  EGamersWorld answers HTTP 403 as well. The board therefore (a) joins the HLTV match list only when
  the capture really read it, (b) falls back to the hand-checked, source-linked research trail
  (MP-F33), and (c) publishes the aggregator tier as unavailable instead of substituting a guess. The
  next capture re-tries both.
* **I8 — dead source links in the result trail (found by this session, 2026-10-15).** 54 of the
  trail's rows link the id-only form `https://www.hltv.org/matches/<id>`, which HLTV answers with
  **HTTP 404 "Page not found"** — a link a reader cannot open is not a source. Verified against two
  of them by hand: `/matches/2395365` → 404, while `/matches/2395365/x` and
  `/matches/2395497/<slug>` both return the correct canonical page (HLTV ignores the slug segment and
  redirects). The board therefore appends a slug built from the two team names
  (`/matches/2395365/johnny-speeds-vs-rethink`) and flags the repair **MP-F35**; a data test now fails
  if any published link is the id-only form again. The same re-reads re-confirmed two published
  results: Johnny Speeds 1-2 ReThink ("Best of 3 (LAN)", 26 Jun, Svenska CS-Ligan Finals) and Sashi
  Academy 2-1 eternal premium ("Best of 3 (Online)", 26 Jun, EPL Series 8 CQ) — both agree with the
  trail's winner/score/series.
* **I7 — refresh races.** The 4-hourly workflow's commit step could fail when the working session
  pushed at the same moment (run `38706401986`). The step now rebases with `-X theirs` (every committed
  file is regenerated output) and retries the push four times before failing.

## 4. Still unverified, and deliberately left blank

* the six DraculaN rows: no result, no series length;
* 20 played fixtures with no independent result on file: result blank, note says so;
* six fixtures whose series length no read source states: `series` blank, MP-F05 (own line still
  published, explicitly labelled `per-map`);
* HLTV's own forecast percentages are **not** used as a probability anywhere (the user's rule: no
  Hotspawn crowd figure and no third-party model output as a probability); only bookmaker/prediction
  market prices and our own originated line are published.

## 5. How to reproduce

```bash
python3 matchpicks/collect_full.py        # writes matchpicks/data/snapshot.json (public reads only)
python3 matchpicks/build.py               # writes matchpicks/data/*.csv + matchpicks/*.html
python3 -m unittest tests.test_b44b5d5e tests.test_b44b5d5e_data
```

The workflow `.github/workflows/matchpicks-b44b5d5e.yml` runs exactly these three steps every four
hours (plus hourly captures by the repository's other boards) and commits only when all of them pass.
