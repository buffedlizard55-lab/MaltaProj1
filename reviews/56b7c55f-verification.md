# Verification record — session `arena/56b7c55f` (2026-10-16 23:47 UTC → 2026-10-17 ~00:20 UTC)

Line-by-line record of what this session verified, where it was read, and what was corrected. Every
row carries the official page used for the read. Nothing here is a new probability source: the board's
prices come from the automated capture, and this document records the manual reads that audit them.

Branch: `arena/56b7c55f-maltaproj1`. Board: `hotspawn/**`. Research files changed:
`research/day4_twc2026.json`, `research/day3_twc2026.json`, `research/results.json`,
`research/fallback_83090640.json`, `research/hltv_links.json`, `research/irregularities.json`.

## 1. TWC 2026 results (the day-1 → day-3 review the brief asks for)

| Match | Verified result | Source (read time UTC) |
|---|---|---|
| Day 1 — 9z vs Aurora | 9z 2-0 Aurora (Inferno 13-11, Nuke 13-1) | <https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026> (results list 23:48Z) |
| Day 1 — Falcons vs NiP | Falcons 2-0 NiP | <https://www.hltv.org/results?event=8932> (23:48Z) |
| Day 1 — Legacy vs PARIVISION | Legacy 2-0 PARIVISION | <https://www.hltv.org/results?event=8932> (23:48Z) |
| Day 1 — FURIA vs BETBOOM | FURIA 2-0 BETBOOM | <https://www.hltv.org/results?event=8932> (23:48Z) |
| Day 2 — Aurora vs NiP | Aurora 2-0 NiP (NiP eliminated) | <https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026> |
| Day 2 — 9z vs Falcons | Falcons 2-1 9z | <https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026> |
| Day 2 — PARIVISION vs BETBOOM | BETBOOM 2-1 PARIVISION (PARIVISION eliminated) | <https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026> |
| Day 2 — Legacy vs FURIA | FURIA 2-1 Legacy | <https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026> |
| Day 3 — Aurora vs 9z (Group A decider) | Aurora 2-0 9z — Cache 13-11, Inferno 13-4; Aurora picked Cache, 9z picked Inferno, Aurora removed Nuke | <https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026> (23:48Z) |
| Day 3 — BETBOOM vs Legacy (Group B decider) | **BETBOOM 2-1 Legacy** — Nuke 16-13 (4:8, 8:4, OT 4:1), Dust2 11-13, Mirage 13-11; BETBOOM removed Inferno, Legacy removed Anubis, BETBOOM picked Nuke, Legacy picked Dust2, BETBOOM removed Cache, Legacy removed Ancient, Mirage left over | <https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026> (23:52Z, three chunks) |

BETBOOM-Legacy was **still live (1-1) at the previous 19:29–19:34Z check**; the final score, veto and
map scores above close that gap and are now in `research/results.json` (key `1081775`), so the grading
table shows the frozen pick against a verified result (graded since launch: n=5).

Grading consequence: the frozen pre-lock pick on `1081775` was Legacy (38.6%), the verified winner was
BETBOOM → miss; `1080205` (Aurora, 67.4%) → correct. Both appear on `strategy.html#grading`.

## 2. Day-4 semifinals — schedule, format, participants, prices

| Item | Verified value | Source (read time) |
|---|---|---|
| Semifinal 1 | FURIA vs Aurora, BO3 (LAN), HLTV match 2399414, start **2026-10-17T14:00Z** | <https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026>; start corroborated by the page countdown (14h 10m 54s at 23:53Z) and <https://polymarket.com/event/cs2-furia-aur1-2026-10-17> |
| Semifinal 2 | Falcons vs **BETBOOM**, BO3 (LAN), HLTV match 2399415, start **2026-10-17T17:00Z** | <https://www.hltv.org/matches/2399415/falcons-vs-betboom-thunderpick-world-championship-2026>; start from <https://polymarket.com/event/cs2-fal2-bb3-2026-10-17> |
| Lineup check | FURIA: molodoy, yuurih, FalleN, KSCERATO, YEKINDAR — Aurora: Jimpphat, kyxsan, Wicadia, woxic, XANTARES (their decider page) — Falcons: karrigan, NiKo, m0NESY, TeSeS, kyousuke — BETBOOM: Magnojez, Boombl4, d1Ledez, zorte, S1ren | HLTV lineup panels on 2399414 / 2399415 (23:53–23:54Z) and 2399412 |
| Valve points (own line inputs) | FURIA 1829 (row 7), Aurora 1716 (row 9), Falcons 1843 (row 6), BETBOOM 1596 (row 11), snapshot 2026-10-05 | <https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md> plus the four `details/2026_10_05/00xx--*.md` rows linked in the research file |
| Own line | FURIA 57.4% / Aurora 42.6%; Falcons 65.8% / BETBOOM 34.2% — recomputed at build time from the points above and the fitted slope k = 0.4598 | `hotspawn/data/calibration.json` (k, 46 windows, 13,609 train / 901 test) and `common.py: own_line()`; verified by `tests.Day4OwnLine` |
| Captured prices (not hand-read) | FURIA-Aurora: Pinnacle 1.80/2.03 → 53.0/47.0 after margin; Thunderpick via bo3.gg 1.85/1.85 → 50.0/50.0; Polymarket 0.525/0.475. Falcons-BETBOOM: Pinnacle 1.257069/3.98 → 76.0/24.0; relay 1.20/4.00 → 76.9/23.1; Polymarket 0.795/0.205 | `data/capture.json` written by workflow runs 38983509979 / 38984409230 / 38983616287 (all succeeded); rendered live on `twc.html#day4` |
| Crowd context (never a probability) | HLTV pick-a-winner: FURIA 35.2 / Aurora 64.8; Falcons 79.3 / BETBOOM 20.7 at 23:53Z | HLTV match pages above |

**Listing status:** three consecutive captures (23:50:42Z, 23:52:01Z, 00:01:50Z) hold 83 CS2 fixtures
each and **no TWC main-event fixture**; the lobby's tournament filter shows only stale June rows from
"…South American Series #1". Both semifinals therefore stay research-only — no invented pick, no
ownership fade, no grading. Recorded as irregularity `D4-04`.

## 3. The two picks that remain unresolved (rung D, blanks published)

| Fixture | Blocker (verified) | Evidence |
|---|---|---|
| 1081861 Lynn Vision vs Morningstar (HLTV 2399576, BO3) | Morningstar has **no row** in Valve's 380-row 2026-10-05 standings and no HLTV world rank, so no independent own line exists; no eligible match-winner price in Pinnacle (0/40), Polymarket (0/58) or the bo3.gg relay (`quote: null`). HLTV's analytics page carries form/rank prose only — no odds. | <https://www.hltv.org/matches/2399576/lynn-vision-vs-morningstar-macemedia-void-autumn-cup-2026>, <https://www.hltv.org/betting/analytics/2399576/lynn-vision-vs-morningstar-macemedia-void-autumn-cup-2026>, <https://bo3.gg/matches/lynn-vision-vs-morningstar-20-10-2026> |
| 1081863 Chinggis Warriors vs WXM (HLTV 2399578, BO3) | WXM has no Valve row and no HLTV rank; Chinggis Warriors itself matches **two** same-name rows (87 and 220), so the documented roster-overlap rule was applied and published. No eligible price anywhere. | <https://www.hltv.org/matches/2399578/chinggis-warriors-vs-wxm-macemedia-void-autumn-cup-2026>, <https://www.hltv.org/betting/analytics/2399578/chinggis-warriors-vs-wxm-macemedia-void-autumn-cup-2026>, <https://bo3.gg/matches/chinggis-warriors-vs-wept-xyloid-melancholy-20-10-2026> |

Both rows keep blank probabilities, are linked from the executive summary (`#unresolved`) and carry a
per-match research record in `research/fallback_83090640.json`. The reason text was made precise
(irregularity `IR-41`): absence from Valve's file is now stated as absence, not as ambiguous identity.

## 4. Claims from the merged day-4 draft (PR #179, session `arena/ef2db3af`) re-checked

| Claim | Status | Fix applied |
|---|---|---|
| FURIA-Aurora kickoff 10:00Z / Falcons-BETBOOM 13:00Z | **corrected** | HLTV renders a local clock; countdown + Polymarket give 14:00Z / 17:00Z |
| Falcons-BETBOOM relay implies 87% | **corrected** | 1.20/4.00 de-vigs to 76.9%/23.1% (8.33% margin) |
| Magnojez was BETBOOM's standout (1.17 rating, 62-50) | **refuted** | Per-map tables show zorte and S1ren as BETBOOM's best-rated players; Magnojez leads none (0.99, 1.24, 0.74, 0.74) |
| Aurora beat FURIA 2-1 ten days ago; Aurora lead H2H 3-2 | **partly verified** | HLTV H2H panel confirms FURIA 1:2 Aurora at ESL Pro League S24 within 30 days; the exact date and 3-2 count were not re-verified |
| BETBOOM 2-0 Falcons (June 2026) | **unverified** | Not republished as fact |
| Map-pool percentages (FURIA Inferno 69%, Aurora Anubis 76%, Falcons Dust2 73%, Mirage 45%) | **unverified** | Replaced by the Falcons/BETBOOM three-month panel actually read; others not republished |
| "Aurora is the bookmaker favourite with the best odds" | **flagged** | Recorded as HLTV's own statement; the captured two-way prices have FURIA marginally ahead |
| Aurora/FURIA "won 3 of last 5", Aurora better form ranking | **verified** | Verbatim in HLTV's analytics pros/cons panels |

Every row above is also displayed on `twc.html#day4` in a merge-audit table, so a reader sees the
correction rather than a silently edited number.

## 5. Repo / pipeline receipts

| Step | Result |
|---|---|
| Workflow run on this branch (push trigger, commit `3436e3e`) | run **38984409230** — success; collect → calibrate → model → build → verify → 90 tests → phone check (360/390/768 px) → auto-commit |
| Capture freshness used by the pages | `reference_utc 2026-10-17T00:01:50Z` (capture), k = 0.4598, 21 open / 19 with pick / 2 unresolved |
| Row audit | `verify.py`: 83/83 source fixtures, 0 errors |
| Test suite | `hotspawn/tests.py`: 90 pass, including the new `Day3CompletedDeciders`, `Day4OwnLine`, `Day4MergeAudit` |
| Cross-session conflict | main carried PR #179's day-4 rewrite of the same file/rendered page; resolved by merging main into this branch, keeping both sessions' work and auditing every contested number (section 4) |

## 6. Manual-review links (one click each)

- Board: <https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/index.html> · picks
  <https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/picks.html> · TWC day-4
  <https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/twc.html#day4> · unresolved
  <https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/unresolved.html>
- Raw data: `hotspawn/data/picks.csv`, `hotspawn/data/board.json`, `hotspawn/data/capture.json`
- Newly flagged items: `D4-04`, `IR-41` … `IR-46` in `hotspawn/research/irregularities.json`
  (published on `flagged.html`).

**Nothing in this session was inferred or back-filled.** Values that could not be verified stay blank
and are listed above with the reason; `D4-04`, `IR-43` and `IR-45` remain flagged for review.
