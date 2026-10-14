# Repository review — session `arena/3b5e3fea` (2026-10-14, UTC)

Scope: read-only review of the boards this session summarizes, while building the executive-summary board
(`exec/`) and the coverage audit. Nothing in another session's files was edited; every item below is recorded
here and rendered on `exec/flagged.html`. Line-level evidence is the linked file and the quoted column.

Read at: 2026-10-14 02:20–02:55 UTC. Repo state: `main` @ `936d577` (PR #82, #83, #85 merged), this session's
branch `arena/3b5e3fea-maltaproj1`.

---

## Verified irregularities

- **R-1 — the hourly board's own text contradicts its own published number (verified).**
  `slate/data/analysis.csv`, fixture `1079621` (Gothic v Lavked) publishes
  `own_p_a_pct=28.83`, `own_p_b_pct=71.17` and at the same time the sentence
  `pick_basis = "no probability available — market unavailable and no official rating for both teams"`.
  Both teams *do* carry an official rating in the same board's own file: `slate/data/ratings.csv` lists
  `Gothic … vrs=705.0` and `Lavked … vrs=862.0` (Gothic also carries flag `S-F-05`, one source only).
  Either the basis sentence is stale or the pick was blanked for a different reason (series format), but as
  published the two fields cannot both be right.
  Sources: [slate/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/analysis.csv) ·
  [slate/data/ratings.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/ratings.csv) ·
  [slate/data/own_lines.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/own_lines.csv).
  Status: **flagged, not corrected** (file owned by another session).

- **R-2 — 23 of 28 open matches have no pick on the board a phone visitor lands on (verified).**
  On the hourly board, `slate/data/analysis.csv` leaves `pick` empty on 23 of the 28 open CS2 rows with the
  flag `S-F-11;S-F-08: series format unverified; series probability and model-only match pick blank`, while
  `data/8944bb84/analysis.csv` (28 rows, `series_format` filled for every open row) and
  `data/fbcccda2/every_pick.csv` both name a side for 27 of those same 28. The rows are not missing — the
  summary a visitor reads first simply does not show them.
  Sources: [slate/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/analysis.csv) ·
  [data/8944bb84/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/8944bb84/analysis.csv) ·
  [data/fbcccda2/every_pick.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/fbcccda2/every_pick.csv).
  Status: **published on `exec/coverage.html` and `exec/flagged.html`**; the underlying board is untouched.

- **R-3 — three matches where merged boards name different winners (verified).**
  Comparing every merged board that names a side for the same fixture id:
  | Fixture | Board A | Board B | This page |
  |---|---|---|---|
  | `1079623` G2 Ares v The Last Resort | `cs2`: The Last Resort | `oct14` + `everypick` + `open-slate`: G2 Ares | G2 Ares (outside price) |
  | `1080279` WROTBERRY v EAC | `cs2` + `oct14`: WROTBERRY | `everypick` + `open-slate`: EAC | EAC (outside price) |
  | `1080285` Voca v Phantom | `cs2` + `oct14`: Voca | `everypick` + `open-slate`: Phantom | Phantom (outside price) |
  All three are near coin-flips and the split is market-versus-model: the rows that disagree with the
  market are the ones whose model line was fitted without an outside price. The exec board prints both the
  market and the model number on every card and lists the mismatch in the row's disagreement block rather
  than averaging it away.
  Sources: the four files above plus [open-slate/data/08031d30/open_slate.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/08031d30/open_slate.csv)
  (path as committed) and [slate/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/analysis.csv).
  Status: **published**; no board's pick was overwritten.

- **R-4 — 17 of the 24 outside prices cannot be re-fetched by any pipeline (verified).**
  Those rows are priced from `bc.game` as reported by EGamersWorld. Session `a174d77f` recorded EGamersWorld
  refusing its runner (Cloudflare, even with a headless render) and archived the refusal; this session's
  sandbox cannot reach it either. The prices are therefore single-observation reports: they are labelled
  `X-SECONDARY-PRICE` and "bookmaker price (aggregator)" on every exec row, and they are never presented as
  a directly verified bookmaker quote.
  Sources: [COORDINATION.md § arena/a174d77f](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/COORDINATION.md) ·
  [reviews/cs2-a174d77f.md](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/reviews/cs2-a174d77f.md) ·
  [everypick/methodology.html](https://buffedlizard55-lab.github.io/MaltaProj1/everypick/methodology.html).
  Status: **flagged**.

- **R-5 — Polymarket's low-tier CS2 markets are per-map, not series (verified from the API).**
  `https://gamma-api.polymarket.com/events?slug=cs2-gothic-lavked-2026-10-14` returns an event whose child
  markets are `Map 1 Winner` (0.485 / 0.515) and `Map 2 Winner`, with `sportsMarketType: child_moneyline`.
  Republishing a map price as "Gothic 51% to win the match" would be wrong for a BO3. Any board that ingests
  Polymarket must filter for a whole-match market; the exec board publishes a prediction-market value only
  when such a market exists, always labelled as a market and never as a bookmaker, and it never pushes it
  into the pick precedence.
  Sources: [gamma-api.polymarket.com event](https://gamma-api.polymarket.com/events?slug=cs2-gothic-lavked-2026-10-14) ·
  [polymarket.com/esports/cs2](https://polymarket.com/esports/cs2).
  Status: **documented on `exec/sources.html`**; enforced in `exec/collect_polymarket.py`.

- **R-6 — the open-slate review copy carries no lock time (verified).**
  `data/08031d30/open_slate.csv` has a `kickoff_utc` column and no lock column; the Hotspawn payload gives
  `lock_offset_sec: 360` for these fixtures, i.e. picks lock six minutes before kickoff. Anyone reusing that
  file's kickoff as a lock time is six minutes optimistic. The exec board takes lock times from the payload
  spine (`slate/data/fixtures.csv`) only, and says so on `exec/methodology.html`.
  Sources: [data/08031d30/open_slate.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/08031d30/open_slate.csv) ·
  [slate/data/fixtures.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/fixtures.csv).
  Status: **documented**; another session's file untouched.

- **R-7 — the rendered Hotspawn card clock is not UTC (verified).**
  The live board shows `Oct 14, 04:00` with `Locks in 05:21:21` for fixture `1079621` while its payload gives
  `start_utc 2026-10-14T08:00:00Z`, `lock_utc 2026-10-14T07:54:00Z` — the card clock is UTC−4. Reading the
  card without converting is a four-hour error; the exec board prints UTC plus the countdown-verified payload
  time and never the rendered clock.
  Sources: [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) ·
  [slate/data/fixtures.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/fixtures.csv).
  Status: **documented**.

- **R-8 — no CI checks are reported on some merged PRs (verified).**
  `gh pr checks 82` answered "no checks reported on the 'arena/a174d77f-maltaproj1' branch" and
  `gh pr view 82 --json statusCheckRollup` returned `[]` while that PR was open and merged. Runs do exist for
  those sessions (they are cited in their logs), so this is a reporting/trigger gap (bot-authored pushes do not
  start follow-on workflows), not a claim about their content. Recorded so nobody reads "no checks" as "all
  checks passed".
  Sources: [PR #82](https://github.com/buffedlizard55-lab/MaltaProj1/pull/82) ·
  [workflow runs](https://github.com/buffedlizard55-lab/MaltaProj1/actions).
  Status: **published**.

## Verified correct (spot-checks that passed)

- **C-1.** Pinnacle's public guest response for `9z v Aurora` (`matchupId 1638111785`) returned
  `home 241 / away −307` on 2026-10-14 02:34 UTC (`cutoffAt 2026-10-14T08:30:00+00:00`); de-vigged that is
  **27.998 % / 72.002 %**, which reproduces the value `slate/data/lines.csv` publishes (27.99 / 72.01) and the
  exec board's row. Source: [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638111785/markets/related/straight).
- **C-2.** The live Hotspawn CS2 board at 02:34–02:40 UTC lists the same 28 open fixtures, with the same
  teams and kickoff order, as `slate/data/fixtures.csv` (13 on 14 Oct, 8 on 15 Oct, 7 on 16 Oct), and its own
  header counts (88 CS2 rows, tier chips B 24 / C 60 / S 4) match the payload. No fixture was missing on
  either side of the comparison. Sources: [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) ·
  [slate/data/fixtures.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/fixtures.csv).
- **C-3.** Every one of the 39 teams appearing in the 28 open fixtures carries at least one official rating in
  `slate/data/ratings.csv` except `LFO 10`, which is the single row the exec board leaves blank (`X-NO-BASIS`)
  — the same conclusion `cs2/` reached independently (27 of 28 picks). Sources:
  [slate/data/ratings.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/slate/data/ratings.csv) ·
  [cs2/data/summary.json](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/summary.json).

## Notes for the integration owner

- `exec/` adds no new collection of bookmaker prices: it aggregates the boards above, labels each row's rung
  and publishes the audit of who covered what. If a board is removed or renamed, the coverage page will show
  the missing column rather than a silent drop.
- The root landing page now has an additive card for `exec/` at the top of the current-board section; no other
  card or sentence there was changed.
