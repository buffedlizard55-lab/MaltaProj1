# Line-by-line verification review — `every/` picks board (session arena/75fd29ee)

- **Session**: `arena/75fd29ee` (`arena/75fd29ee-maltaproj1`)
- **Verified**: 2026-10-14 02:40–03:10 UTC
- **Published pages**: [`every/index.html`](../every/index.html) (all picks + executive summary),
  [`every/methodology.html`](../every/methodology.html), [`every/flagged.html`](../every/flagged.html),
  [`every/sources.html`](../every/sources.html)
- **Machine-readable data**: [`every/data/picks.csv`](../every/data/picks.csv) (28 rows),
  [`every/data/coverage.json`](../every/data/coverage.json), [`every/data/flags.csv`](../every/data/flags.csv)
- **Zero Hotspawn crowd input**: `coverage.json.hotspawn_crowd_used = false`, asserted by `tests/test_75fd29ee.py`.

## 1. Coverage claim (verified against the live slate snapshot)

| Item | Count | How verified |
|---|---:|---|
| Open CS2 Pick'em fixtures in `slate/data/fixtures.csv` (snapshot 2026-10-14T02:23:08Z) | 28 | row-by-row `sport=cs2`, `live_status=open` |
| Rows in `every/data/picks.csv` | 28 | set equality asserted in `tests/test_75fd29ee.py::test_every_open_cs2_fixture_has_a_pick_row` |
| Matches with a published pick | **28 / 28** | 7 primary market + 17 aggregator-reported market + 4 originated-line picks |
| Matches with a win probability | 28 / 28 | every pick_pct recomputed from its cited quote or rating inputs in tests |
| Rows without any https source link | 0 | `test_every_row_has_an_https_source` |

## 2. All 28 picks with sources (generated from `every/data/picks.csv` — identical values)

| ID | Start UTC | Competition (tier, format) | Teams | Market line | Market P(A)/P(B) | Our line P(A)/P(B) | Pick | Flags |
|---|---|---|---|---|---|---|---|---|
| `1079621` | 2026-10-14 08:00 | CCT Europe 2026 Series #11 (B, BO3) | Gothic vs Lavked | bc.game/EGW 2.05/1.64 | 44.44/55.56 | 20.14/79.86 | **Lavked 55.56%** | E-02-AGGREGATOR-LINE |
| `1081111` | 2026-10-14 08:00 | CCT Europe 2026 Series #12 Play-In (C, BO3) | Enjoy vs B8 Academy | bc.game/EGW 1.52/2.3 | 60.21/39.79 | 69.98/30.02 | **Enjoy 60.21%** | E-02-AGGREGATOR-LINE |
| `1080176` | 2026-10-14 08:30 | Thunderpick World Championship 2026 (S, BO3) | 9z vs Aurora | Pinnacle 3.41/1.326 | 28.0/72.0 | 11.12/88.88 | **Aurora 72.0%** | — |
| `1079438` | 2026-10-14 10:00 | Stake Pulse Beat III (B, BO3) | Astralis vs Sashi | bc.game/EGW 1.09/6.33 | 85.31/14.69 | 99.48/0.52 | **Astralis 85.31%** | E-02-AGGREGATOR-LINE |
| `1079439` | 2026-10-14 10:00 | Stake Pulse Beat III (B, BO3) | HOTU vs Fnatic | Pinnacle 1.99/1.8 | 47.49/52.51 | 51.73/48.27 | **Fnatic 52.51%** | E-02-DIVERGENCE |
| `1079622` | 2026-10-14 11:00 | CCT Europe 2026 Series #11 (B, BO3) | ex-RUSTEC vs mellren | bc.game/EGW 1.4/2.68 | 65.69/34.31 | 63.27/36.73 | **ex-RUSTEC 65.69%** | AGGREGATOR-LINE; SLATE-PARITY; DUPLICATE-VRS |
| `1080177` | 2026-10-14 11:00 | Thunderpick World Championship 2026 (S, BO3) | Falcons vs Ninjas in Pyjamas | Pinnacle 1.27/3.85 | 75.2/24.8 | 96.16/3.84 | **Falcons 75.2%** | — |
| `1081112` | 2026-10-14 11:00 | CCT Europe 2026 Series #12 Play-In (C, BO3) | Banda chuya vs 6666 | (none — 1.80/1.80 placeholder rejected) | — | 25.66/74.34 | **6666 74.34%** | MODEL-PICK; SLATE-PARITY; DUPLICATE-VRS |
| `1080178` | 2026-10-14 13:30 | Thunderpick World Championship 2026 (S, BO3) | Legacy vs PARIVISION | Pinnacle 1.654/2.26 | 57.74/42.26 | 92.45/7.55 | **Legacy 57.74%** | — |
| `1079623` | 2026-10-14 14:00 | CCT Europe 2026 Series #11 (B, BO3) | G2 Ares vs The Last Resort | bc.game/EGW 1.465/2.436 | 62.45/37.55 | 49.03/50.97 | **G2 Ares 62.45%** | AGGREGATOR-LINE; DIVERGENCE |
| `1081113` | 2026-10-14 14:00 | CCT Europe 2026 Series #12 Play-In (C, BO3) | Ryvex vs PCIFIC | (none — placeholder rejected) | — | 34.93/65.07 | **PCIFIC 65.07%** | MODEL-PICK |
| `1080179` | 2026-10-14 16:00 | Thunderpick World Championship 2026 (S, BO3) | FURIA vs BetBoom | Pinnacle 1.364/3.18 | 69.98/30.02 | 93.0/7.0 | **FURIA 69.98%** | — |
| `1079624` | 2026-10-14 17:00 | CCT Europe 2026 Series #11 (B, BO3) | FORZE Reload vs LFO 10 | (none — placeholder rejected) | — | 95.31/4.69 | **FORZE Reload 95.31%** | MODEL-PICK; E-01 research flags |
| `1080279` | 2026-10-15 08:00 | Elisa BreakOut Series #2 (C, BO1) | WROTBERRY vs EAC | bc.game/EGW 2.01/1.69 | 45.68/54.32 | 61.11/38.89 | **EAC 54.32%** | AGGREGATOR-LINE; DIVERGENCE; ALIAS-RESOLVED |
| `1079440` | 2026-10-15 10:00 | Stake Pulse Beat III (B, BO3) | MIBR vs BC.Game | Pinnacle 1.649/2.22 | 57.38/42.62 | 85.34/14.66 | **MIBR 57.38%** | — |
| `1079442` | 2026-10-15 10:00 | Stake Pulse Beat III (B, BO3) | Heroic vs Envy | Pinnacle 1.469/2.62 | 64.07/35.93 | 51.47/48.53 | **Heroic 64.07%** | ALIAS-RESOLVED |
| `1080280` | 2026-10-15 10:00 | Elisa BreakOut Series #2 (C, BO1) | ENCE vs BOJONG | bc.game/EGW 1.3/3.17 | 70.92/29.08 | 73.47/26.53 | **ENCE 70.92%** | E-02-AGGREGATOR-LINE |
| `1080281` | 2026-10-15 12:00 | Elisa BreakOut Series #2 (C, BO1) | WROTBERRY vs ENCE | bc.game/EGW 1.62/2.107 | 56.53/43.47 | 61.68/38.32 | **WROTBERRY 56.53%** | AGGREGATOR-LINE; ALIAS-RESOLVED |
| `1080282` | 2026-10-15 14:00 | Elisa BreakOut Series #2 (C, BO1) | EAC vs BOJONG | bc.game/EGW 1.19/4.02 | 77.16/22.84 | 73.57/26.43 | **EAC 77.16%** | E-02-AGGREGATOR-LINE |
| `1080283` | 2026-10-15 16:00 | Elisa BreakOut Series #2 (C, BO1) | WROTBERRY vs BOJONG | bc.game/EGW 1.21/3.99 | 76.73/23.27 | 74.66/25.34 | **WROTBERRY 76.73%** | AGGREGATOR-LINE; ALIAS-RESOLVED |
| `1080284` | 2026-10-15 18:00 | Elisa BreakOut Series #2 (C, BO1) | EAC vs ENCE | bc.game/EGW 1.51/2.35 | 60.88/39.12 | 50.72/49.28 | **EAC 60.88%** | E-02-AGGREGATOR-LINE |
| `1080285` | 2026-10-16 08:00 | Elisa BreakOut Series #2 (C, BO1) | Voca vs Phantom | bc.game/EGW 1.87/1.77 | 48.63/51.37 | 53.02/46.98 | **Phantom 51.37%** | AGGREGATOR-LINE; DIVERGENCE |
| `1080286` | 2026-10-16 10:00 | Elisa BreakOut Series #2 (C, BO1) | HAVU vs RoundsGG | bc.game/EGW 1.19/4.02 | 77.16/22.84 | 70.62/29.38 | **HAVU 77.16%** | AGGREGATOR-LINE; ALIAS-RESOLVED |
| `1080287` | 2026-10-16 12:00 | Elisa BreakOut Series #2 (C, BO1) | Voca vs HAVU | bc.game/EGW 1.38/2.7 | 66.18/33.82 | 65.83/34.17 | **Voca 66.18%** | E-02-AGGREGATOR-LINE |
| `1080288` | 2026-10-16 14:00 | Elisa BreakOut Series #2 (C, BO1) | Phantom vs RoundsGG | bc.game/EGW 1.08/6.94 | 86.53/13.47 | 74.03/25.97 | **Phantom 86.53%** | AGGREGATOR-LINE; ALIAS-RESOLVED |
| `1081120` | 2026-10-16 14:00 | CCT Europe 2026 Series #12 Play-In (C, BO3) | mellren vs Privateer | (none — placeholder rejected) | — | 73.41/26.59 | **mellren 73.41%** | MODEL-PICK |
| `1080289` | 2026-10-16 16:00 | Elisa BreakOut Series #2 (C, BO1) | RoundsGG vs Voca | bc.game/EGW 6.4/1.063 | 14.24/85.76 | 25.19/74.81 | **Voca 85.76%** | AGGREGATOR-LINE; ALIAS-RESOLVED |
| `1080290` | 2026-10-16 18:00 | Elisa BreakOut Series #2 (C, BO1) | Phantom vs HAVU | bc.game/EGW 1.36/2.87 | 67.85/32.15 | 63.65/36.35 | **Phantom 67.85%** | E-02-AGGREGATOR-LINE |

Per-row source links (Hotspawn lobby, HLTV match page, book quote URL, Valve file line anchors,
HLTV team pages) are on the published page and in `every/data/picks.csv`; they are omitted from this
markdown table only for width.

## 3. Verification performed

1. **Formula parity with the canonical model.** The originated-line arithmetic is byte-for-byte the
   documented slate model (`slate/collect.py`: Elo logistic scale 400; BO3 `p²(3−2p)`;
   BO5 `p³(10−15p+6p²)`; equal-weight mean of the HLTV-points and VRS-points sides).
   `tests/test_75fd29ee.py::test_originated_line_matches_slate_where_inputs_agree` reproduces
   slate's `own_map_p_a` on **18 of 20** comparable open fixtures (all 18 exact to 0.00).
   The two documented differences are the IRREG-02 duplicate-name rows below.
2. **Market arithmetic.** Every published market percentage is re-derived from the published decimal
   odds by `test_devig_recomputes_from_published_odds` (two-way de-vig).
3. **Sources.** Every row carries at least one `https://` link (`test_every_row_has_an_https_source`);
   every table row on `every/index.html` carries links (`test_picks_table_rows_carry_links`);
   internal links resolve (`test_internal_links_resolve`).
4. **LFO 10 research (E-01) — read line by line during this session:**
   - HLTV Valve global ranking 2026-10-10 entry read directly:
     `#168 LFO 10 (771 Valve points) EU`, roster dottie/flaw/Sapec —
     <https://www.hltv.org/valve-ranking/teams/2026/october/10> (page states "Valve global ranking on
     October 10th, 2026").
   - HLTV match page 2399301 read directly: "Best of 3 (Online)", FORZE Reload badges HLTV #75 / VRS #89,
     LFO 10 badges "HLTV: Unranked / VRS: #169", lineup Jackinho/Sapec/flaw/dottie/tvs —
     <https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11>.
   - EGamersWorld match page read directly: same five-player opponent lineup, "Bo3",
     prices shown 1.8/1.8 (placeholder → rejected) —
     <https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3>.
   - Valve's official standings file (`standings_global_2026_10_05.md`, fetched from the
     ValveSoftware GitHub API during this session) has **no** "LFO 10" row; it lists the same 3-man
     core under **"Entropy" #156, 813 pts** (roster "dottie, flaw, Sapec, tevsii, Toshas", line 161) —
     <https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L161>.
     Identity chain (exact name on HLTV + roster overlap with both match pages) is recorded in
     `data/75fd29ee/team_research.csv`; Entropy's 813 pts are **not** used.
5. **Series formats.** BO labels on every row come from HLTV match pages (read via session 8944bb84's
   per-row `hltv_match_url`, independently spot-checked for 2399301 in this session). This also
   corrects slate's S-F-08 gap: the 12 Elisa BreakOut Series #2 fixtures are **BO1**, not the assumed
   BO3 expansion (IRREG-05 in `reviews/8944bb84-verification.md`).

## 4. Irregularities flagged (non-blocking, published on `every/flagged.html`)

| ID | Finding | Handling | Source |
|---|---|---|---|
| IRREG-02 (carried) | Valve's 2026-10-05 file lists duplicate team names; `slate/collect.py` keeps the wrong (partial-roster) rows for ex-RUSTEC (824 vs verified 1066), 6666 (425 vs 923), Banda Chuya (402 vs 801). Slate's own-line for `1079622` and `1081112` is therefore wrong-direction. | This board uses the roster-verified rows (line-anchored Valve links). The two parity differences (42.54→59.26, 46.69→33.13) are exactly these rows and are flagged `FL-DUPLICATE-VRS-DISAMBIGUATED;E-02-SLATE-PARITY`. | [Valve file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) · [HLTV 2399299](https://www.hltv.org/matches/2399299/ex-rustec-vs-mellren-cct-2026-europe-series-11) |
| FL-EXT-PLACEHOLDER (carried) | EGamersWorld showed 1.80/1.80 placeholder prices for `1081112`, `1081113`, `1079624`, `1081120`. | Rejected as market evidence; those four fall through to the originated line. | [EGamersWorld](https://egamersworld.com/counterstrike/matches) |
| E-01-MIXED-SNAPSHOT / E-01-RANK-DRIFT | LFO 10's rating comes from the 2026-10-10 HLTV Valve ranking (771 pts) while other teams use the 2026-10-05 Valve file; the live match-page badge reads VRS #169 vs the dated page's #168. | Both observations published per-row; the dated snapshot value is used; Entropy's older value is not used. | [ranking page](https://www.hltv.org/valve-ranking/teams/2026/october/10) · [match 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) |
| E-02-DIVERGENCE (4 rows) | Market and model favourites disagree on `1079439` (Fnatic vs HOTU), `1079623` (G2 Ares vs The Last Resort), `1080279` (EAC vs WROTBERRY), `1080285` (Phantom vs Voca). | Market favourite drives the pick (hierarchy rule); both numbers shown; divergence flagged. | per-row quote + rating links on the page |
| ALIAS-RESOLVED (carried) | WROTBERRY→WBT, RoundsGG→ROUNDS, EAC→EA Copenhagen, Envy→3DMAX via evidence-linked aliases. | Used with flags; evidence URLs in `slate/aliases.json` and row notes. | [HLTV 2399418](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) |

## 5. Inputs and reproducibility

`python3 scripts/75fd29ee_build.py` rebuilds `every/` from committed evidence only
(`slate/data/*`, `data/8944bb84/*`, `data/75fd29ee/*`) — no network required.
`python3 -m unittest tests.test_75fd29ee -v` re-runs the 17 acceptance checks.
`.github/workflows/every-75fd29ee.yml` rebuilds and republishes on schedule so the picks list tracks
the hourly Hotspawn snapshot.
