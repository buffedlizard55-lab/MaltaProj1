# Repo review — session `arena/08031d30` (2026-10-14, UTC)

Scope: read-only review of the open Hotspawn CS2 slate and of the refresh/publish machinery, with a source link for each
item and a flag for manual review. Nothing here is silently corrected. Items marked **unverified** could not be confirmed
from an official or readable source in this session.

Snapshot: Hotspawn CS2 pick'em page read 2026-10-14 01:41–01:58Z (3 chunks). EGamersWorld CS2 listing read the same
window (chunks 0–4 of 16). OddsPortal Thunderpick WC page read the same window. HLTV ranking 2026/october/12 read (chunk 0
of 59 only). Source-access limits are listed at the end.

## A. Coverage of the live Hotspawn CS2 slate

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| A-1 | The live CS2 pick'em page lists **28 open fixtures** (Oct 14: 13, Oct 15: 8, Oct 16: 7). All 28 fixture IDs, team pairs and kickoffs match open CS2 rows in the published board (`slate/data/fixtures.csv`). | https://play.hotspawn.com/cs2-pickems · https://play.hotspawn.com/lobby | **Verified this session** (data: `data/08031d30/hotspawn_open_cs2.csv`) |
| A-2 | Board row **1079546** Zomblers v Overtake Sector is labelled `open`, but its lock (00:54Z) and kickoff (01:00Z) had already passed at this read. It is not on the live list. EGamersWorld lists it **LIVE**, Bo3, at 03:00 EGW time (UTC+2) = 01:00Z. | https://egamersworld.com/counterstrike/matches · https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_ | **Irregularity — board row stale.** Excluded from the open list. |
| A-3 | Hotspawn's CS2 page and lobby both say **"68 matches this week"**. The visible open list has 28 entries, plus 1 started row. The remaining ~39 are not visible on either page. The tier filter total (B 25 + C 60 + S 4 = 89) matches the board's 89 CS2 rows, so the 68 count is not explained by the board. | https://play.hotspawn.com/cs2-pickems | **Unverified / unreconciled.** Not treated as a coverage gap in the open list, but the count is not explained. |
| A-4 | Hotspawn does **not state its display time zone**. The UTC-4 offset was inferred because all 28 displayed times equal the payload-derived UTC (board, 180a42a0) plus 4 hours. | https://play.hotspawn.com/cs2-pickems | Flag: inferred, not stated on the page. |
| A-5 | The UTC times rely on the board's parse of the Hotspawn server-rendered payload (180a42a0). This session's tools return rendered text, not the raw payload, so the payload itself was not re-read. | https://play.hotspawn.com/cs2-pickems | Trust chain: board parse → this session's check (rendered times agree on 28/28). |

## B. External prices

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| B-1 | **Placeholder pairs.** Three open fixtures show exactly **1.80 / 1.80** on EGamersWorld (no market): 1081112 Banda chuya v 6666, 1081113 Ryvex v PCIFIC (a second listing, WRAITH PCIFIC v Ryvex, also 1.80/1.80), and 1079624 FORZE Reload v (opponent slot blank on the listing). The earlier session already flagged this pattern as F-28. All three are **left blank** here. | https://egamersworld.com/counterstrike/matches · https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y · https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3 | Irregularity. Own-line-only pick (1081112, 1081113) or no pick (1079624). |
| B-2 | **Bookmaker identity not shown.** EGW "Make a bet" links point to `egamersworld.com/#`, so the book behind each EGW price is not named. The CCT Europe Series #11 event page labels its bets block as "by bc.game". EGW prices may therefore come from one bookmaker (single-book concentration). | https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK | **Unverified:** which book(s) EGW displays. Flagged. |
| B-3 | **Second source differs.** OddsPortal's Thunderpick WC page gives 9z v Aurora 3.40/1.29 (EGW 3.87/1.20) and Falcons v NiP 1.26/3.65 (EGW 1.19/3.95). The book is not named in the read. | https://www.oddsportal.com/esports/counter-strike/counter-strike-thunderpick-world-championship/ | Both kept on the page, labelled "Second read". |
| B-4 | **Stake Pulse Beat III has no odds on OddsPortal** at this read ("Next Matches will appear here as soon as bookmaker betting odds become available"). | https://www.oddsportal.com/esports/counter-strike/counter-strike-stake-pulse-beat-iii/ | Not a failure of the source; no odds exist on that page at read time. |
| B-5 | **Carried prices (not re-read this session).** 14 fixtures (all 8 Oct 15 rows, and 6 Oct 16 rows; 1081120 has no price at all) use prices read by earlier sessions on 2026-10-13 (22:00 EGW listing, 23:36 EGW event pages, 23:52 Pinnacle). They are labelled "carried" on the page. The Pinnacle public matchups page returned HTTP 500 to this session. | https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl | Carried, flagged. |
| B-6 | **Identical prices on two fixtures.** 1080282 EAC v BOJONG and 1080283 WROTBERRY v BOJONG both show 1.20 / 4.00 (board read 23:36Z). Possible, but unusual; not re-read here. | https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl | **Unverified** → verify on the match pages. |
| B-7 | **Extreme prices.** 1079438 Astralis v Sashi 1.09 (EGW, fresh); 1080288 Phantom v RoundsGG 1.05 / 7.11 (carried); 1080289 RoundsGG v Voca 6.40 / 1.063 (carried). Flagged on the page. | https://egamersworld.com/counterstrike/matches | Flagged. |
| B-8 | **Series format.** EGW lists **Bo3** on every fresh Oct 14 read (Enjoy v B8 also confirmed on its match page). The carried Oct 15–16 prices do not state the format on the read (board flag S-F-08). | https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7 | Verified for Oct 14; unverified for Oct 15–16. |

## C. Name and identity mismatches (to confirm)

| # | Hotspawn | Other source | Link | Status |
|---|----------|--------------|------|--------|
| C-1 | Sashi (1079438) | "Sashi Esport" on EGW | https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z | **Unverified:** same team? |
| C-2 | PCIFIC (1081113) | "PCIFIC Espor" and "WRAITH PCIFIC" on EGW | https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3 | **Unverified:** which PCIFIC? (Placeholder price, so no pick depends on it.) |
| C-3 | BetBoom (1080179) | "BetBoom Team" on EGW | https://egamersworld.com/counterstrike/match/5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH | Likely same team; flagged. |
| C-4 | 9z (1080176) | "9z Team" on OddsPortal | https://www.oddsportal.com/esports/counter-strike/counter-strike-thunderpick-world-championship/ | Likely same team; flagged. |

## D. Own lines (originated from official ratings)

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| D-1 | Own-line probabilities on the page are **carried from the published board** (`slate/data/own_lines.csv`, session 180a42a0: HLTV ranking + Valve VRS). They were **not re-derived** this session. The board's own basis text says the Elo-to-series step is **"best-of-3 assumed"** for these rows, so an own line is not a verified series format. | https://www.hltv.org/ranking/teams/2026/october/12 | Carried, flagged. The format assumption is visible on each card's basis text. |
| D-2 | HLTV ranking 2026/october/12 was read at chunk 0 only (page 1 of 59). The team ranks behind the own lines were **not independently re-verified** this session. | https://www.hltv.org/ranking/teams/2026/october/12 | **Unverified** for the 28 teams. |
| D-3 | External and own line **disagree on the favourite** in 5 fixtures (each flagged on the page): HOTU v Fnatic (external Fnatic 51.1%, own HOTU 51.1%); ex-RUSTEC v mellren (external ex-RUSTEC 65.7%, own mellren 57.5%); G2 Ares v The Last Resort (external G2 Ares 62.4%, own TLR 50.6%); WROTBERRY v EAC (carried; external EAC 53.8%, own WROTBERRY 61.1%); Voca v Phantom (carried; external Phantom 51.4%, own Voca 53.0%). Near coin-flips (under 5 points from 50%) are also flagged: Gothic v Lavked, HOTU v Fnatic, Banda chuya v 6666, WROTBERRY v EAC, Voca v Phantom. | `open-slate/flagged.html` | Flagged. |

## E. Refresh, publish and repository machinery

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| E-1 | **Scheduled model refresh failed.** `model-91eff436` ("O-01 own-line model (VRS)") scheduled run 38489574648 (2026-10-14 00:20Z) failed in the step "Tests (incl. check against Valve's own fit.js/glicko.js)". Its log could not be retrieved (`EOF`). The owning session's last commit is 2026-10-13. | https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38489574648 | Irregularity. Owner `arena/91eff436`; not edited here. |
| E-2 | **3-hourly slate schedule not observed.** `slate-180a42a0.yml` cron `41 */3 * * *` should have fired at 00:41Z. No scheduled run appears in `gh run list` after 2026-10-13 23:54Z (last capture run 38486458907). Re-checked at the end of this session (see log). | https://github.com/buffedlizard55-lab/MaltaProj1/actions/workflows/slate-180a42a0.yml | Irregularity, re-check recorded in COORDINATION. |
| E-3 | **Concurrent pushes.** Session `arena/a9a0c2f1` (claim at 01:42Z: H-01..H-03 covering `slate/**`, the slate workflow, `index.html`, `README.md`) pushed three commits between 01:43Z and 01:46Z. Those commits triggered runs 38497270864, 38497409104 (cancelled) and 38497485985. | https://github.com/buffedlizard55-lab/MaltaProj1/actions | Noted. This session did **not** edit those paths. |
| E-4 | **Open PR #54** (`arena/9920c263`, full CS2 slate) is `DIRTY`/`CONFLICTING`; last owner commit 2026-10-13 22:09Z. | https://github.com/buffedlizard55-lab/MaltaProj1/pull/54 | Stale PR; owner or integrator to close or rebase. |
| E-5 | **Stale claims on the board.** Many `in progress` rows in `COORDINATION.md` have no commits for >60 minutes (last activity 2026-10-13). Some sections also mark the same task `done` (the "Task board (final)" section). | https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/COORDINATION.md | Flag. Stale claims were not taken over except as logged. |
| E-6 | **Dashboard sprawl.** The root landing page links about 20 published boards (`slate/`, `winboard/`, `picks/`, `board/`, `mobile/`, `model/`, `dashboard/`, `pickem/`, `docs/`, `hub.html`, `site/`, `today/`, `status/`, `live/`, `verify/`, `assurance/`, …), each with its own fixture list, pick logic and "canonical" claim. | https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/index.html | Flag for the integrator: pick one canonical board. |

## F. Source-access limits (this session)

- Pinnacle public matchups page: HTTP 500 to `fetch_page`.
- EGamersWorld `/counterstrike` and `/counter-strike`: one returned HTTP 500; `/counterstrike` and `/counterstrike/matches` were readable.
- HLTV ranking: readable at chunk 0 of 59. Not all pages read.
- The sandbox cannot reach these hosts directly. All reads were through `fetch_page`.
- Not read this session: EGW listing chunks 5–15 (Oct 15–16 prices).
