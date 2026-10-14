# Full-coverage CS2 picks — line-by-line review (`arena/63ee81ba`)

- **Session / branch:** `arena/63ee81ba` (`arena/63ee81ba-maltaproj1`)
- **Snapshot of record:** `2026-10-14T02:48:00Z` (end of the EGW listing read; Hotspawn payload read 02:38Z)
- **Board:** [`picks-full/index.html`](../picks-full/index.html) — 28 open fixtures, **28/28 picks**
- **Data:** [`data/63ee81ba/`](../data/63ee81ba/) (fixtures, teams, market_lines, own_lines, picks, flags, coverage)
- **Build / tests:** [`scripts/63ee81ba_build.py`](../scripts/63ee81ba_build.py), [`tests/test_63ee81ba.py`](../tests/test_63ee81ba.py) (22 tests, all passing)
- **Automation:** [`.github/workflows/picks-full-63ee81ba.yml`](../.github/workflows/picks-full-63ee81ba.yml) (hourly + push, fail-closed)
- **Crowd data used:** none (0.0% weight — structurally excluded; test-enforced)

## 1. Task coverage

| Requirement | Status | Evidence |
|---|---|---|
| Pick (or explicit % per team) for **every** open Hotspawn CS2 match | ✅ 28/28 | `data/63ee81ba/picks.csv`; `test_every_fixture_has_pick` |
| Low-tier + unpriced matches covered via research sources | ✅ 4 unpriced rows: 3 own lines (both teams rated), 1 labelled RESEARCH line (LFO 10, PF-02) | `own_lines.csv` rows 1081112/1081113/1079624/1081120 |
| Outside betting lines, up to date, de-vigged, per-row source + read time | ✅ 24/24 priced rows (EGW 02:48Z; Pinnacle 01:48Z; Polymarket 02:46Z) | `market_lines.csv`; `test_market_devig_math` |
| Own lines for all matches from CS2 research (VRS + HLTV) | ✅ 28/28 own lines (1 research-labelled) | `own_lines.csv`; `test_own_line_math` |
| Mobile-friendly; probabilities + pick obvious; source link per row | ✅ card layout, viewport meta, per-card source pills | `picks-full/` pages; `test_viewport_and_nav_on_every_page` |
| In-site links from landing page; easy on phone | ✅ exec summary + primary CTA on root `index.html` | `index.html#exec-summary` |
| Regular automated check for Hotspawn updates | ✅ hourly workflow, fail-closed | workflow above |
| Line-by-line verification; unconfirmable = blank + flagged | ✅ 10 flags (PF-01..PF-10) | `flags.csv`, `picks-full/flagged.html` |

## 2. Sources (all row-linked in the data files)

| Source | Used for | Read / pin |
|---|---|---|
| Hotspawn `/cs2-pickems` + `/lobby` payload | fixture list, team order, tiers, start/lock epochs | live 2026-10-14T02:38Z; CI capture 02:18:56Z (`slate/data/fixtures.csv`) |
| Valve VRS `standings_global_2026_10_05.md` (commit `eec4853d`) | team ratings for own lines | re-fetched + sha256-verified 02:35Z (`data/63ee81ba/vrs_2026_10_05.md`, `df96e7fc…`) |
| `model/input/vrs/calibration.json` | calibrated slope k=0.4568 (adopted; MLE on 6,765 Valve results) | repo file, hash-checked at build time |
| HLTV World Ranking 2026-10-12 + official match pages 2399134–2399471 | roster verification, series format (BO1/BO3), results | verified 02:26Z via `data/8944bb84/ratings.csv` |
| EGamersWorld (bc.game feed) | primary outside moneylines (24/28) | listing chunks 0–9 read 02:40–02:48Z; identical to independent 01:48Z read (session 8944bb84) |
| Pinnacle direct guest API | cross-check (7 fixtures) | 01:48Z (session 8944bb84, cited) |
| Polymarket CCT Europe (view-only) | cross-check (5 usable; 2 unusable, flagged) | 02:46Z |

## 3. The 28 picks (snapshot 2026-10-14T02:48Z, times UTC)

| # | Start | Matchup (Hotspawn order) | P(A)/P(B) | Pick (basis) |
|---|---|---|---|---|
| 1081111 | 10-14 08:00 | Enjoy vs B8 Academy | 60.2/39.8 | **Enjoy** (market 1.52/2.30) |
| 1079621 | 10-14 08:00 | Gothic vs Lavked | 44.4/55.6 | **Lavked** (market 2.05/1.64) |
| 1080176 | 10-14 08:30 | 9z vs Aurora | 23.7/76.3 | **Aurora** (market 3.87/1.20) |
| 1079438 | 10-14 10:00 | Astralis vs Sashi | 85.3/14.7 | **Astralis** (market 1.09/6.33) |
| 1079439 | 10-14 10:00 | HOTU vs Fnatic | 48.9/51.1 | **Fnatic** (market 1.89/1.81) — close |
| 1081112 | 10-14 11:00 | Banda chuya vs 6666 | 38.2/61.8 | **6666** (own line: VRS #165/801 vs #127/923) |
| 1079622 | 10-14 11:00 | ex-RUSTEC vs mellren | 65.7/34.3 | **ex-RUSTEC** (market 1.40/2.68) |
| 1080177 | 10-14 11:00 | Falcons vs NiP | 76.8/23.2 | **Falcons** (market 1.19/3.95) |
| 1080178 | 10-14 13:30 | Legacy vs PARIVISION | 55.5/44.5 | **Legacy** (market 1.66/2.07) |
| 1081113 | 10-14 14:00 | Ryvex vs PCIFIC | 35.0/65.0 | **PCIFIC** (own line: #139/870 vs #207/714; identity PF-03) |
| 1079623 | 10-14 14:00 | G2 Ares vs The Last Resort | 62.4/37.6 | **G2 Ares** (market 1.465/2.436) |
| 1080179 | 10-14 16:00 | FURIA vs BetBoom | 67.1/32.9 | **FURIA** (market 1.40/2.86) |
| 1079624 | 10-14 17:00 | FORZE Reload vs LFO 10 | 75.9/24.1 | **FORZE Reload** (RESEARCH line, PF-02) |
| 1080279 | 10-15 08:00 | WROTBERRY vs EAC | 45.7/54.3 | **EAC** (market 2.01/1.69, BO1) |
| 1079440 | 10-15 10:00 | MIBR vs BC.Game | 56.3/43.7 | **MIBR** (market 1.62/2.09) |
| 1079442 | 10-15 10:00 | Heroic vs Envy | 63.0/37.0 | **Heroic** (market 1.45/2.47) |
| 1080280 | 10-15 10:00 | ENCE vs BOJONG | 70.9/29.1 | **ENCE** (market 1.30/3.17, BO1) |
| 1080281 | 10-15 12:00 | WROTBERRY vs ENCE | 56.5/43.5 | **WROTBERRY** (market 1.62/2.107, BO1) |
| 1080282 | 10-15 14:00 | EAC vs BOJONG | 77.2/22.8 | **EAC** (market 1.19/4.02, BO1) |
| 1080283 | 10-15 16:00 | WROTBERRY vs BOJONG | 76.7/23.3 | **WROTBERRY** (market 1.21/3.99, BO1) |
| 1080284 | 10-15 18:00 | EAC vs ENCE | 60.9/39.1 | **EAC** (market 1.51/2.35, BO1) |
| 1080285 | 10-16 08:00 | Voca vs Phantom | 48.6/51.4 | **Phantom** (market 1.87/1.77, BO1) — close |
| 1080286 | 10-16 10:00 | HAVU vs RoundsGG | 77.2/22.8 | **HAVU** (market 1.19/4.02, BO1) |
| 1080287 | 10-16 12:00 | Voca vs HAVU | 66.2/33.8 | **Voca** (market 1.38/2.70, BO1) |
| 1081120 | 10-16 14:00 | mellren vs Privateer | 78.5/21.5 | **mellren** (own line: #125/932 vs #271/608) |
| 1080288 | 10-16 14:00 | Phantom vs RoundsGG | 86.5/13.5 | **Phantom** (market 1.08/6.94, BO1) |
| 1080289 | 10-16 16:00 | RoundsGG vs Voca | 14.2/85.8 | **Voca** (market 6.40/1.063, BO1; order note PF-09) |
| 1080290 | 10-16 18:00 | Phantom vs HAVU | 67.8/32.2 | **Phantom** (market 1.36/2.87, BO1) |

Confidence: 11 OBVIOUS LOCK (≥70%) · 10 STRONG (60–69%) · 4 SOLID LEAN (55–59%) · 3 CLOSE (<55%).

## 4. Verification performed (line by line)

1. **Fixture set.** Live `/cs2-pickems` read (3 chunks, 02:38–02:41Z) parsed 28 open cards; team order,
   tiers and points cross-checked against the scheduled CI payload capture (`slate/data/fixtures.csv`,
   02:18:56Z) — identical 28 IDs; `live/data/snapshot.json` (02:07Z) independently lists the same 28 open.
2. **Times.** Card countdowns prove the display frame is UTC−4 (PF-06); all times published are payload
   epochs; lock = start − 360s verified in the payload for all 28 (`test_lock_is_start_minus_360s`).
3. **Series format.** Each of the 28 fixtures mapped to its official HLTV match page (2399134–2399471);
   all 12 Elisa BreakOut Series 2 matches are BO1, the rest BO3 (`test_series_formats`).
4. **Team ratings.** All 34 teams resolved in `data/8944bb84/ratings.csv` (verified 02:26Z against the
   2026-10-05 VRS file + HLTV match lineups; duplicate same-name VRS rows disambiguated by roster).
   VRS file re-fetched and sha256-verified this session.
5. **Market lines.** Every EGW quote re-read from the live listing this session (02:40–02:48Z) and
   identical to the independent 01:48Z read; de-vig arithmetic re-checked by test.
6. **Model.** k=0.4568 confirmed against `model/input/vrs/calibration.json` (adopted, k_published);
   own-line values recomputed by `test_own_line_math`.

## 5. Irregularities & flags (published on the board, none block the release)

| ID | Sev | Summary |
|---|---|---|
| PF-01 | MEDIUM | EGW 1.80/1.80 placeholders rejected as lines (4 fixtures) — replaced by own lines, never treated as 50/50 |
| PF-02 | HIGH | LFO 10 absent by name in 2026-10-05 VRS → official line blank; roster-mapped RESEARCH line only (vs VRS #156 Entropy 813 pts, per HLTV match 2399301 + Valve's ≥3-player identity rule) |
| PF-03 | MEDIUM | PCIFIC identity: Hotspawn "PCIFIC" vs EGW/PM "WRAITH PCIFIC" (HLTV 2399463 + VRS #139 roster favour PCIFIC; PM quote cross-check only, 17.7 pp gap) |
| PF-04 | HIGH | Polymarket FORZE market lists opponent "Sökerorg" ≠ Hotspawn "LFO 10" (EGW blank) → PM quote context-only, not the line |
| PF-05 | LOW | Polymarket mellren vs Privateer Gaming degenerate (94¢/94¢, $0 vol) → not used |
| PF-06 | INFO | Hotspawn countdown display = UTC−4; payload epochs are the truth (arithmetic proof recorded) |
| PF-07 | INFO | Polymarket read view-only (US geo banner; content readable) |
| PF-08 | INFO | Lock = start − 360s, verified in payload + live countdown |
| PF-09 | LOW | #1080289 listed Voca-first on EGW; odds oriented to Hotspawn order (pick unaffected) |
| PF-10 | INFO | 4 locked + 59 stale fixtures listed for completeness (59 retained with sources on the 8944bb84 page) |

## 6. What the automation does (and does not do)

Hourly (cron 47) + on push: `live/collect.py` re-captures Hotspawn payload, latest VRS file, Pinnacle, EGW,
Polymarket, HLTV → `scripts/63ee81ba_build.py --live` verifies snapshot freshness, reports open-slate drift
(new/disappeared fixture IDs), VRS-file drift and EGW quote movement → test suite must pass → commit only if
`data/63ee81ba`/`picks-full` changed. **Fail-closed:** any failed step publishes nothing; the board only
changes through a source-linked build change, so it can never silently serve an unverified pick.
