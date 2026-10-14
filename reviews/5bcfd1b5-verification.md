# Verification — session `arena/5bcfd1b5` (2026-10-14, UTC)

**Scope.** Give every Counter-Strike 2 fixture Hotspawn lists a pick and a win probability, using
only outside sources for the numbers; publish a mobile-first board with an executive summary; check
Hotspawn regularly for newly listed matches; review the repository line by line against official
sources and flag every irregularity with a link. Nothing here is silently corrected, and no value
that could not be confirmed was filled in — those cells are blank and flagged.

**Snapshot.** Hotspawn `/lobby` and `/cs2-pickems` read 2026-10-14 02:50–02:55Z (all chunks). Board
capture inherited from `cs2/data/analysis.csv` at **02:35:29Z**. EGamersWorld CS2 listing read
02:52–02:55Z (chunks 0–4 of 15). Valve Regional Standings read from
`ValveSoftware/counter-strike_regional_standings` commit
`eec4853d7bcf0f1f7efe7f0d901234bef7e98b75` via the GitHub contents API. HLTV match, team and event
pages read 02:40–03:10Z. Board generated **2026-10-14T03:47:12Z**.

**Headline result.** 89 fixtures on the board; **86 carry a pick** (85 with a numeric probability).
The **open slate is 28/28** — every match still pickable in Hotspawn's game has a pick. On `main`
before this session the same 89 fixtures yielded 64 picks and 27/28 open.

---

## A. Coverage of the Hotspawn CS2 slate

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| A-1 | The Hotspawn payload holds **89 CS2 fixtures**: 28 open, 2 started/locked, 59 expired (June–July 2026). All 89 are on the board; none is omitted. | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) · [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) | **Verified this session** (`data/5bcfd1b5/every_match.csv`) |
| A-2 | The **28 open fixtures** match the live page's rendered open cards exactly (Oct 14 ×13, Oct 15 ×8, Oct 16 ×7). | [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) | **Verified** — 28/28 rendered, 28/28 with a pick |
| A-3 | Hotspawn prints **"68 matches this week"** and its tier filter prints **"All tiers (88)"**, while the payload in the same response holds **89** CS2 rows. `cs2/data/capture.json` on `main` records `hotspawn_total_cs2_filter_count: 89`. | [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) | **Irregularity IR-05-06.** We publish the 89 payload rows and record the disagreement; no printed count is asserted as coverage. |
| A-4 | **4 fixtures have no Hotspawn permalink** (1081111, 1081112, 1081113, 1081120 — CCT Europe 2026 Series #12 Play-In). Those rows link the CS2 lobby plus the official HLTV match page instead of printing a broken URL. 25 of 89 rows do carry a permalink. | [HLTV event 9456](https://www.hltv.org/events/9456/cct-2026-europe-series-12-closed-qualifier) | **Irregularity IR-05-07** (also the null-permalink crash in CI run 38489574648) |
| A-5 | A scheduled live check now re-reads Hotspawn every 3 hours and **merges any newly listed fixture onto the board** with the same rating cascade, flagged `LIVE-NEW-FIXTURE`. Proven end to end with a synthetic fixture: it resolved to Valve #34/1427 vs #3/1911 and produced a tier-C pick. | `.github/workflows/allpicks-5bcfd1b5.yml` · `scripts/5bcfd1b5_livecheck.py` | **Verified** (test `test_new_hotspawn_fixtures_are_merged_and_picked`) |
| A-6 | Hotspawn's point value is **not in the payload** for a live-discovered fixture, so `points` is left blank on those rows rather than inferred from the tier. | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) | Blank by design; asserted in tests |

## B. Official team ratings

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| B-1 | Ratings are taken from the **Valve period in force at the match date**. Periods actually used: 2026-06-01 (49 sides), 2026-07-06 (10), 2026-10-05 (29). Eight official files are committed gzipped under `data/5bcfd1b5/vrs/` with a SHA-256 manifest in `coverage.json`; the October global file's hash matches the one `arena/8944bb84` committed. | [Valve live/2026](https://github.com/ValveSoftware/counter-strike_regional_standings/tree/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026) | **Verified** — every citation re-read from Valve's own bytes in `test_cited_valve_line_says_what_we_published`: **164 sides** carry a single pinned citation and the **12 ambiguous sides** cite *both* admissible rows, so every rating on the board is clickable back to an exact Valve line |
| B-2 | **Root cause of `main`'s 25 blank picks:** every prior board resolved teams only against `standings_global_2026_10_05.md`, but 23 of the blank fixtures were played 2026-06-26 → 2026-07-10. `cs2/data/analysis.csv` proves it: every `vrs_url_*` on a June fixture points at the October file. | [Valve 2026-06-01](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md) | **Irregularity IR-05-01 — fixed here** |
| B-3 | **Galorys** is ranked by Valve at **#85 / 1099 pts** (line 90 of the October file) yet `data/8944bb84/ratings.csv` has no Galorys row and that board left fixture 1081076 blank. | [Valve line 90](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L90) | **Irregularity IR-05-02** — a lookup gap, not a data gap |
| B-4 | **12 team-sides have an ambiguous name**: Valve legitimately publishes two same-name rows (e.g. Keyd #119/991 and #359/416 in June). All admissible rows are evaluated. Where every combination agrees on the favourite (9 fixtures) the pick is published at its **conservative bound** and the full range is printed beside it. Where they disagree (3 fixtures) **no probability and no pick** are published. | [Valve 2026-06-01 L124](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md?plain=1#L124) · [L364](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md?plain=1#L364) | **Verified**; brackets recomputed from Valve's bytes in `test_bracketed_own_line_matches_all_combinations_of_valve_rows` |
| B-5 | **94 inherited duplicate-name row pins** (from `data/8944bb84/ratings.csv`) were **re-validated line by line against Valve's own file** before use — team name, standing and points must all still agree: **94 accepted, 0 rejected**. 4 fixture sides are actually resolved by a pin. | [Valve live/2026](https://github.com/ValveSoftware/counter-strike_regional_standings/tree/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026) | **Verified this session** |
| B-6 | **28 team-sides use a rating period later than the match date** (22 fixture rows; a row where both sides are anachronistic counts once) (the team was absent from the period in force). Every one is flagged `RATING-PERIOD-LATER-THAN-MATCH` on the row and on the card. | `data/5bcfd1b5/every_match.csv` column `rating_note` | **Verified**; asserted in `test_later_period_fallback_is_always_flagged` |
| B-7 | **LFO 10** is absent from all five Valve periods under any name. A roster search of its HLTV five (Jackinho, Sapec, flaw, dottie, tvs) returns at most 3/5 overlap, with Entropy (#156/813) — a different team. Valve ranks LFO 7, LFO 8 and LFO 9 but not LFO 10. | [HLTV 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) · [Valve 2026-10-05](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) | **Unranked — verified.** No rating invented; see D-2 |
| B-8 | **SUKEBAN** is `HLTV: Unranked` / `VRS: Unranked` (team 14091) and forfeited its fixture. | [HLTV 2399460](https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-south-america-2026-series-7) | **Verified** — recorded as an official result, not a prediction |

### B.9 Name aliases — every one carries roster evidence and a non-Hotspawn URL

| Hotspawn name | Resolves to | Period | Evidence | Link |
|---|---|---|---|---|
| Envy | **3DMAX** (#21, 1500 pts) | 2026-10-05 | HLTV's Envy lineup — Graviti, Kursy, Maka, misutaaa, Lucky — is a **5/5 exact match** to Valve's #21 row | [HLTV 2399137](https://www.hltv.org/matches/2399137/heroic-vs-envy-stake-pulse-beat-iii) · [Valve L26](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L26) |
| Keyd | **Keyd Stars** | 2026-06-01 | HLTV files fixture 1051790 as "Keyd Stars vs. Yawara"; HLTV event 9239's participant table names the team "Keyd Stars" (914 Valve pts). June has **two** Keyd Stars rows, so both stay admissible and the bracket test decides | [HLTV 2395423](https://www.hltv.org/matches/2395423/keyd-stars-vs-yawara-thunderpick-world-championship-2026-south-america-series-1) · [HLTV event 9239](https://www.hltv.org/events/9239/thunderpick-world-championship-2026-south-america-series-1) |
| Patins de Ferrari | **Patins da Ferrari** (#241, 692 pts) | 2026-08-03 | EGamersWorld's slug `patins-de-ferrari-XBfksnqnWl` is titled "Patins da Ferrari"; Valve's August roster is CutzMeretz, history, mlhzin, nicks, t9rnay — **5/5**. Absent from June, so the row is labelled anachronistic | [Valve L246](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_08_03.md?plain=1#L246) |
| ex-Tricked | **Tricked** (#50, 1251 pts) | 2026-06-01 | HLTV team 4602's transfer log and Liquipedia both date Boye, IceBerg, leakz, NickyB, salazar (+ coach Rejin) leaving Tricked at **2026-06-01**, and Valve's 2026-06-01 file ranks exactly those five as `Tricked` — so the same Valve-ranked roster played the 2026-06-27 fixtures as "ex-Tricked" | [HLTV team 4602](https://www.hltv.org/team/4602/tricked) · [Liquipedia Tricked Esport](https://liquipedia.net/counterstrike/Tricked_Esport) · [Valve L55](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md?plain=1#L55) |
| ex-MANA | **MANA** (#143, 907 pts) | 2026-06-01 | **Valve's own files** carry the continuity: June #143/907 ammar, BledarD, cerber, SENER1, xonn1k → July #160/815 ammar, arbnorz, BledarD, cerber, xonn1k (4-player core) | [Valve L148](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md?plain=1#L148) |
| WROTBERRY | **WBT** (#60, 1201 pts) | 2026-10-05 only | Inherited pin, re-checked. **Note:** in Valve's *June* standings the team appears under its own name `WROTBERRY`, so the June fixture (1052749) is *not* alias-resolved. The alias is claimed only in periods where the alias name is what matched | [Valve L236 (June)](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md?plain=1#L236) |
| RoundsGG | **ROUNDS** (#310, 548 pts) | 2026-10-05 | Inherited pin, re-checked against Valve's file | [Valve L315](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L315) |

**Rejected alias.** `SINQU` (June #307) and `SINQU REHTI` (July #332) are **different entities**; no
alias was created. `ex-Keyd Stars` was **not** aliased to `Keyd Stars` either — the June fixtures and
the October fixture are different rosters and both resolve on their own names.

## C. Outside market prices

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| C-1 | **26 of 89 fixtures are priced by an outside book**: 7 tier A (Pinnacle's public guest moneyline feed, read by CI at 02:35:36Z) and 19 tier B. Probabilities are de-vigged: `p(A) = (1/o_A)/((1/o_A)+(1/o_B))`; the overround is printed on every row. | [Pinnacle CS2 matchups](https://www.pinnacle.com/en/esports/games/cs2/matchups/) · [EGamersWorld](https://egamersworld.com/counterstrike/matches) | **Verified** — arithmetic re-derived independently in `test_devig_arithmetic_is_exact` |
| C-2 | **14 prices were read live this session** from EGamersWorld at 02:52Z and are recorded with exact URLs and read times in `data/5bcfd1b5/market_reads.csv`; 11 accepted, 3 rejected. They independently confirm 10 of the prices `arena/8944bb84` committed. | [EGamersWorld](https://egamersworld.com/counterstrike/matches) | **Verified this session** |
| C-3 | **`1.80/1.80` is EGamersWorld's un-priced placeholder**, not a market. Three fixtures show it (1081112, 1081113, 1079624). De-vigging it would fabricate a 50/50, so all three are **rejected and flagged** `MARKET-PLACEHOLDER`. | [EGW 1081112](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/banda-chuya-vs-6666-JdPgKgp5y) · [EGW 1079624](https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3) | **Verified** — asserted in `test_placeholder_odds_are_never_used` |
| C-4 | **Pinnacle's guest API returns HTTP 401 from this sandbox**, so no tier-A price was read live here; tier A reuses `main`'s scheduled CI capture and says so on every row. Only CI can read that endpoint. | `guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight` | **Access limitation recorded**, not a data gap |
| C-5 | **Aggregator orientation differs from Hotspawn's.** EGamersWorld lists `your end` first on 1081105 while Hotspawn lists SUKEBAN first. Odds are mapped **by team name, never by column position**, and every swap is recorded. | [EGW 1081105](https://egamersworld.com/counterstrike/match/x) | **Verified** — asserted in `test_market_reads_record_orientation` |
| C-6 | **Prices drift inside an hour.** 1080177 Falcons v NiP: Pinnacle 1.254/4.010 at 01:48Z vs 1.27027/3.85 at 02:35:36Z. 1080176 9z v Aurora: 3.550/1.307 vs 3.41/1.325733. Both are real reads of a moving market. Every price row now prints its read time. | [Pinnacle CS2 matchups](https://www.pinnacle.com/en/esports/games/cs2/matchups/) | **Irregularity IR-05-05** |
| C-7 | **`data/8944bb84/external_lines.csv` carries two different reads per row** (`primary_*` and `egw_*`) with no marker saying which is published, and they disagree on 8 fixtures. The first draft of this board paired Pinnacle's *label* with EGamersWorld's *odds and URL*, misattributing all 8. Fixed: label, odds and URL now always come from the same read, and the other read is printed as a labelled cross-check. | [Pinnacle read for 1079546](https://guest.api.arcadia.pinnacle.com/0.1/matchups/1638279105/markets/related/straight) · [EGW read for 1079546](https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_) | **Irregularity IR-05-11 — found and fixed this session** |
| C-8 | **Polymarket** had no reachable CS2 market for these fixtures in this session. It is not a source for any number on this board. | — | Not used |

## D. Picks

| # | Finding | Source link | Status |
|---|---------|-------------|--------|
| D-1 | Pick hierarchy, first usable tier wins, never averaged: **A** primary book (7) · **B** book price not re-read this cycle (19) · **C** own line, both teams uniquely ranked in the period in force (25) · **D** own line via alias / pinned duplicate / later period (34) · **E** directional, probability blank (1) · **F** no pick (3). The tier is printed on every card and row. | `allpicks/methodology.html` | **Verified** — `test_tier_hierarchy_is_respected` |
| D-2 | **1079624 FORZE Reload v LFO 10 → directional pick FORZE Reload, probability deliberately blank.** FORZE Reload is Valve #84/1100; LFO 10 has no Valve entry in any period, is `Unranked` on HLTV, and no book prices it (EGamersWorld lists a **blank opponent** at 1.80/1.80). Publishing a percentage would require inventing a rating for an unranked team. | [HLTV 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) · [Valve L89](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L89) | **Tier E — verified**, flagged `PICK-WITHOUT-PROBABILITY` |
| D-3 | **3 fixtures carry no pick at all**, all expired June duplicates where admissible same-name Valve rows disagree on the favourite: 1051339 Acend v Infinite (team-A range 45.4–83.7%), 1052599 Mai Tai v Megoshort (48.6–69.6%), 1052700 GameHunters v VEXA (47.6–58.4%). Left blank, flagged `RATING-AMBIGUOUS` + `NO-PICK`. **No open fixture is blank.** | [Valve 2026-06-01](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_06_01.md) | **Deliberate blanks — verified** |
| D-4 | **Model:** `p_map(A) = 1/(1+10^(−k·(pts_A−pts_B)/400))`, **k = 0.4630**, inherited from `cs2/data/summary.json` (MLE on **14,188** Valve-published match results; out-of-sample log-loss 0.6509, Brier 0.2296, against raw Valve k 0.6915/0.2410). Read at build time, never hard-coded. **84 fixtures** have our own line. | `cs2/data/summary.json` | **Verified** — `test_model_constant_is_inherited_not_invented`, `test_own_line_is_reproducible_from_valve_points` |
| D-5 | **Format-invariance result (published on the board):** both series transforms — BO3 `p²(3−2p)` and BO5 `p³(10−15p+6p²)` — are strictly increasing on [0,1] and fix 0.5, so **the favourite side never depends on the format**; only the margin does. 30 fixtures have an HLTV-verified format and 59 do not, so an unverified format still supports a defensible pick and is labelled a single-map estimate. | [HLTV matches](https://www.hltv.org/matches) | **Proved** over 10,001 grid points in `test_series_transforms_are_order_preserving_and_fix_even` |
| D-6 | **Hotspawn's crowd `%% picked` and HLTV's "Pick a winner" vote are never probability inputs.** HLTV shows 87.5/12.5 on 1079624; that number appears nowhere in the output. The board carries no crowd column at all, and the shared collector used for the live check documents that crowd values are discarded. | [HLTV 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) | **Verified** — `test_hotspawn_crowd_is_never_a_probability`, `test_collector_projects_no_crowd_value` |
| D-7 | **Official results recorded where they exist:** 1081105 your end 1–0 SUKEBAN (forfeit — "unable to field a complete roster"). | [HLTV 2399460](https://www.hltv.org/matches/2399460/your-end-vs-sukeban-cct-south-america-2026-series-7) | **Verified** — a result, not a prediction |

## E. Repository irregularities

Eleven irregularities were raised while reviewing `main` line by line. All eleven are published with
their source links on **[allpicks/flagged.html](../allpicks/flagged.html)** as IR-05-01 … IR-05-11,
and are summarised in sections A–D above. The four that change a published number:

| ID | Irregularity | Effect if left unfixed |
|---|---|---|
| **IR-05-01** | Every board resolved ratings against Valve's October file only | 23 fixtures blank although Valve ranks both teams in the June/July files |
| **IR-05-03** | HLTV's `VRS: #N` badges are **not** Valve's published standings — HLTV shows LFO 10 at "VRS #169" where Valve's file has **Honvéd** at #169, and HEROIC at "VRS #22" where Valve ranks it **#15** (1550 pts). HLTV links to `/valve-ranking/teams/2026/october/14`, a daily mirror | Mixing the two numbering systems silently corrupts every rating |
| **IR-05-04** | Two boards on `main` disagree about "Envy": `data/8944bb84/ratings.csv` says #21/3DMAX, `COORDINATION.md` records an earlier claim of "#20 / VRS #27" (VRS #27 is **GamerLegion**) | A wrong rating for a tier-S fixture. Settled 5/5 on roster: **Envy = 3DMAX**; the #27 claim is wrong |
| **IR-05-11** | `external_lines.csv` holds two disagreeing reads per row with no published marker | 8 rows misattributed — found in this session's own first draft and fixed |

Also recorded, not fixed here (they belong to other sessions' file scopes): **IR-05-06** Hotspawn's
printed counts vs its payload; **IR-05-07** four missing permalinks; **IR-05-08** EGamersWorld lists
1079624 with no away team; **IR-05-09** stale PR #54; **IR-05-10** two published boards use
different own-line constants and periods and are not interchangeable.

Two further irregularities inherited from earlier reviews were re-confirmed and are handled here:
Valve's files contain **31 duplicate team names**, and naive top-to-bottom parsing overwrites the
active roster with an older one and can **flip a pick** (ex-RUSTEC #92/1066 overwritten by #152/824;
6666 #127/923 by #368/425; Banda Chuya #165/801 by #373/402) — so no row is ever resolved by
"take the higher standing".

## F. Build, site and test verification

| Check | Command | Result |
|---|---|---|
| Board builds offline from committed evidence | `python3 scripts/5bcfd1b5_build.py` | 89 fixtures, 86 picks, 12 flags |
| Build is byte-reproducible | `test_build_is_deterministic` | pass (run timestamps normalised) |
| Verification suite | `python3 -m unittest discover -s tests -p 'test_5bcfd1b5.py' -v` | **55 tests, 0 failures** |
| Site renders | `python3 scripts/5bcfd1b5_site.py` | 11 pages |
| Committed HTML matches the renderer | `test_site_rebuilds_identically` | pass |
| Internal links | `test_no_broken_internal_links` | **0 broken** across 11 pages |
| Citation URLs well formed and commit-pinned | `test_no_broken_citation_urls` | pass — a `.md.md` double-extension bug in Valve citations was found and fixed |
| Repository-wide audit | `python3 scripts/audit_91e444dd.py` | **179 HTML pages, 0 link errors** |
| Every Valve citation re-read from Valve's bytes | `test_cited_valve_line_says_what_we_published` | 164 single-citation sides: file, line, team, standing, points and roster all agree |
| Mobile configuration | `test_all_nav_pages_exist_and_are_mobile_configured` | viewport meta + lang on all 11 pages |
| Pick and probability visible on every open card | `test_open_page_has_one_card_per_open_match_with_pick_and_bar` | 28/28 cards starred, barred and linked |

Two bugs were found by this verification and fixed before publication:

1. **`.md.md` in Valve citation URLs** — `source_url()` appended `.md` to a filename that already
   carried it, so 84 pinned citations pointed at a non-existent path.
2. **Bracketed picks showed only the conservative bound** — `pick_pct_hi` was computed and stored
   but never rendered, so a reader saw "51.9%" where the honest statement is "51.9%–83.3%". Cards and
   tables now print the range and explain why.

## G. Source-access limits in this session

| Source | Reachable from | Note |
|---|---|---|
| `play.hotspawn.com` | `fetch_page` only | `curl` from the sandbox fails with `SSL_ERROR_SYSCALL`; CI reaches it (the live check is the proof path) |
| `www.hltv.org` | `fetch_page` only | returns 403 to CI, so HLTV is a verification source here, not a CI input |
| `egamersworld.com` | `fetch_page` only | read live at 02:52Z; 14 prices captured |
| Pinnacle guest API | **neither** | HTTP 401 from the sandbox; only CI can read it, hence tier A reuses the committed CI capture |
| `github.com` / `api.github.com` | `curl`, `gh api` | Valve's official standings were read this way and committed gzipped |
| Polymarket | not reachable | no CS2 market found for these fixtures; not used |
| `hltv.org/ranking/teams/2026/june/1` | `fetch_page` | 59 chunks — impractical; local Valve period files were used instead |

## H. Reproduce

```bash
python3 scripts/5bcfd1b5_livecheck.py    # optional: re-read Hotspawn, report new/changed fixtures
python3 scripts/5bcfd1b5_build.py        # ratings -> lines -> picks -> flags  (offline)
python3 scripts/5bcfd1b5_site.py         # render allpicks/ from the committed CSVs
python3 -m unittest discover -s tests -p 'test_5bcfd1b5.py' -v
python3 scripts/audit_91e444dd.py --output /tmp/audit.json
```

Data: `data/5bcfd1b5/{every_match.csv, team_ratings.csv, market_reads.csv, flags.csv,
coverage.json, livecheck.json}` and the committed Valve bytes in `data/5bcfd1b5/vrs/*.md.gz`.
Site: `allpicks/`. CI: `.github/workflows/allpicks-5bcfd1b5.yml`, every 3 hours at :47.

**Not betting advice.** Market probabilities are de-vigged bookmaker prices. Our own lines are
estimates from Valve's published standings points through a logistic fitted on Valve's own results;
they are not calibrated per tournament and they diverge from the market on some matches. Those
divergences are printed side by side on `allpicks/market.html`, not reconciled silently.
