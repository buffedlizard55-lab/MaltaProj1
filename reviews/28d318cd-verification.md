# Verification record — arena/28d318cd (live Hotspawn reconciliation)

Checked: 2026-10-14T05:00Z. Scope S-01..S-05 (COORDINATION.md). Files: `reconcile/**`, this file.

## What was checked

- Hotspawn `/lobby` (ET, countdown-anchored at 04:37:25Z) and `/cs2-pickems` (UTC, stale at ~02:50Z; F-09). Both list the same 28 open fixtures (F-10 for the 68-match header).
- Reconciliation to `console/data/picks.csv` (origin/main): 28/28 one-to-one, 28/28 with a pick, 0 extra rows (`reconcile/summary.json`).
- Line-by-line re-check of each row (`reconcile/reread.csv`, produced by `reconcile/build.py`).

## Result counts

- reproduced: 11
- differs: 1
- placeholder — not reproducible: 1
- reproduced — identity open: 1
- unverifiable: 1
- not re-read: 13

## Unresolved picks (no bookmaker or prediction-market price)

- 1081112 Banda chuya vs 6666 — own line, roster identity open (F-02).
- 1081120 mellren vs Privateer — own line, reproduces 78.5 / 21.5 (unique names).
- 1079624 FORZE Reload vs LFO 10 — research only, unverifiable (F-11).

## Row table

| Fixture | Match | Board pick | Board % (A / B) | Recheck | Recomputed (A / B) | Result | Source |
|---|---|---|---|---|---|---|---|
| 1079621 | Gothic vs Lavked | Lavked | 44.4 / 55.6 | decimal de-vig | 44.44 / 55.56 | reproduced | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) |
| 1081111 | Enjoy vs B8 Academy | Enjoy | 60.2 / 39.8 | decimal de-vig | 60.21 / 39.79 | reproduced | [egamersworld.com](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7) |
| 1079623 | G2 Ares vs The Last Resort | G2 Ares | 62.4 / 37.6 | decimal de-vig | 62.76 / 37.24 | differs | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L) |
| 1079622 | ex-RUSTEC vs mellren | ex-RUSTEC | 65.7 / 34.3 | decimal de-vig | 50.00 / 50.00 | placeholder — not reproducible | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK) |
| 1080279 | WROTBERRY vs EAC | EAC | 46.2 / 53.8 | american de-vig | 46.23 / 53.77 | reproduced | [thunderpick.io](https://thunderpick.io/esports/cs2-betting/elisa-breakout-series-2/11360/wbt-vs-ea-copenhagen/2807510) |
| 1080176 | 9z vs Aurora | Aurora | 28.0 / 72.0 | american de-vig | 27.99 / 72.01 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1079439 | HOTU vs Fnatic | Fnatic | 49.6 / 50.4 | american de-vig | 49.58 / 50.42 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1080177 | Falcons vs Ninjas in Pyjamas | Falcons | 75.2 / 24.8 | american de-vig | 75.19 / 24.81 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1080178 | Legacy vs PARIVISION | Legacy | 53.9 / 46.1 | american de-vig | 53.92 / 46.08 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1080179 | FURIA vs BetBoom | FURIA | 70.0 / 30.0 | american de-vig | 69.99 / 30.01 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1079440 | MIBR vs BC.Game | MIBR | 57.4 / 42.6 | american de-vig | 57.37 / 42.63 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1079442 | Heroic vs Envy | Heroic | 64.1 / 35.9 | american de-vig | 64.07 / 35.93 | reproduced | [guest.api.arcadia.pinnacle.com](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) |
| 1081120 | mellren vs Privateer | mellren | 78.5 / 21.5 | P_map=1/(1+10^(-k*dP/400)), BO3=p^2(3-2p) | 78.52 / 21.48 | reproduced | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| 1081112 | Banda chuya vs 6666 | 6666 | 38.2 / 61.8 | P_map + BO3 (as above) | 38.17 / 61.83 | reproduced — identity open | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| 1079624 | FORZE Reload vs LFO 10 | FORZE Reload | 75.9 / 24.1 | none — opponent not in VRS table | — | unverifiable | [github.com](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| 1079438 | Astralis vs Sashi | Astralis | 85.4 / 14.6 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2767822) |
| 1081113 | Ryvex vs PCIFIC | PCIFIC | 19.5 / 80.5 | — | — | not re-read | [polymarket.com](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) |
| 1080280 | ENCE vs BOJONG | ENCE | 71.1 / 28.9 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807501) |
| 1080281 | WROTBERRY vs ENCE | WROTBERRY | 57.0 / 43.0 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807512) |
| 1080282 | EAC vs BOJONG | EAC | 76.9 / 23.1 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807496) |
| 1080283 | WROTBERRY vs BOJONG | WROTBERRY | 76.9 / 23.1 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807511) |
| 1080284 | EAC vs ENCE | EAC | 61.5 / 38.5 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807492) |
| 1080285 | Voca vs Phantom | Phantom | 48.6 / 51.4 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807497) |
| 1080286 | HAVU vs RoundsGG | HAVU | 76.9 / 23.1 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807498) |
| 1080287 | Voca vs HAVU | Voca | 65.5 / 34.5 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807499) |
| 1080288 | Phantom vs RoundsGG | Phantom | 86.8 / 13.2 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807503) |
| 1080289 | RoundsGG vs Voca | Voca | 14.6 / 85.4 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807505) |
| 1080290 | Phantom vs HAVU | Phantom | 68.2 / 31.8 | — | — | not re-read | [thunderpick.io](https://thunderpick.io/match/2807508) |

## Flags (full text in reconcile/flagged.html)

- **F-01 [HIGH] ex-RUSTEC vs mellren: board value does not reproduce** (1079622). Board: ex-RUSTEC 65.7 / 34.3 (EGamersWorld, read 02:48Z). Live EGamersWorld read 04:39Z: 1.80 / 1.80 (= 50.0 / 50.0). The picks-full board already treats 1.80/1.80 as a placeholder. Pick: ex-RUSTEC. *Action:* Re-read the price before lock (10:54Z). Until then the 65.7 value is not confirmed.
- **F-02 [HIGH] Banda chuya vs 6666: duplicate team names in the Valve table; the probability depends on which roster** (1081112). VRS 2026-10-05 has two rows named 'Banda Chuya' (rank 165 / 801 pts, AdrieN-ezox-maaryy-Showk-tomiko; rank 373 / 402 pts, ezox-manio) and two rows named '6666' (rank 127 / 923 pts; rank 368 / 425 pts). The board's 38.2 / 61.8 reproduces only with rank 165 and rank 127. Other combinations: 6666 (923) vs Banda rank 373 -> 6666 89.4%; 6666 rank 368 (425) vs Banda rank 165 -> Banda 81.9% (pick flips); 6666 rank 368 vs Banda rank 373 -> 6666 52.3%. Hotspawn's roster for either team is not shown on the page. *Action:* Confirm both rosters against the Hotspawn/HLTV match page before publishing a probability. Pick stays '6666' only if the 923-point 6666 and 801-point Banda are the teams playing.
- **F-03 [MED] Ryvex vs PCIFIC: two EGamersWorld listings for the same slot** (1081113). EGamersWorld lists 'PCIFIC Espor vs Ryvex' and 'WRAITH PCIFIC vs Ryvex' at 14.10 16:00 (= 14:00Z). The Polymarket market is 'cs2-wraith-ryvex-2026-10-14'. Board R-228-04 records the identity as confirmed; this read does not show the confirmation. Board pick: PCIFIC 80.5% (Polymarket). Not re-read today. *Action:* Re-check the identity on the HLTV page before lock. The 'WRAITH' and 'PCIFIC' names both appear, so this is an open question for the reader.
- **F-04 [MED] G2 Ares vs The Last Resort: small mismatch with the live read** (1079623). Board 62.4 / 37.6 (EGamersWorld, 02:48Z). Live 04:39Z: 1.43 / 2.41 -> 62.76 / 37.24 (difference -0.36 pp). The 0.4 pp gap is larger than the rounding of the decimal odds, so the price likely moved. *Action:* Update the board value from a fresh read. The pick (G2 Ares) is unchanged.
- **F-05 [MED] Bookmaker attribution and price dispersion on the Gothic vs Lavked row** (1079621). Board attributes the 2.05 / 1.64 price to bc.game via EGamersWorld. The bookmaker list I read (chunks 0-2) shows 2.05 / 1.64 at SpinAlto, RedSport, PlanBet and Kinbet, not bc.game. Spinbetter, 22bet and 1xBit show 1.881 / 1.782 = 48.7 / 51.3, a 4.2 pp spread from the board's 44.4 / 55.6. The percentages match the board; the attribution is not confirmed. *Action:* Correct the source label to the bookmaker that actually posts the price, or record the spread.
- **F-06 [MED] HOTU vs Fnatic: pick margin under 1 pp** (1079439). Pinnacle capture 2026-10-14T02:45Z: HOTU -110 / Fnatic -114 -> 49.6 / 50.4. Reproduces on recompute. The pick is a near coin flip. *Action:* Show as a near-even pick (no confidence tier).
- **F-07 [HIGH] Four Play-In rows have no Hotspawn match link visible on the rendered page** (1081111, 1081112, 1081113, 1081120). The /lobby and /cs2-pickems renders show the 28 fixtures (names, times, tournament, tier) but no 'View match' link or fixture ID for these four rows. The board's IDs (1081111, 1081112, 1081113, 1081120) come from the board's own payload capture and cannot be confirmed from the page. *Action:* Check the IDs against a Hotspawn match URL before using them as identity. Treat the rows as identity-unconfirmed until then.
- **F-08 [HIGH] Site front door shows no picks** (all). The root landing page (index.html, owned by arena/198cf31e, task B-04) is served from a stale snapshot dated 2026-10-13T19:42:13Z, so picks show as blank. The consolidated board at console/index.html shows 28 of 28 picks as of 04:23Z. *Action:* Owner of B-04 to refresh the landing snapshot. This session did not edit index.html (scope).
- **F-09 [MED] Hotspawn pages render at different times** (all). /cs2-pickems countdowns anchor to a render near 02:50:21Z; /lobby countdowns anchor to 04:37:25Z. Both list the same 28 fixtures. The 1h47m gap is not shown to readers. Lock times use the /lobby anchor. *Action:* Treat /cs2-pickems as a stale source for timing. Use /lobby.
- **F-10 [MED] '68 matches this week' on /cs2-pickems vs 28 listed** (all). The /cs2-pickems header says '68 matches this week'. Only 28 fixtures are listed as open ('Closing Soon' 13, 'Upcoming' 15). The 40-match gap is not explained on the page. *Action:* Scope every coverage claim to '28 open fixtures visible on the public page at read time'.
- **F-11 [MED] Research pick FORZE Reload vs LFO 10 has no official line** (1079624). LFO 10 is absent from the Valve 2026-10-05 table (LFO 7, 8 and 9 are present, at ranks 279, 285 and 297). The board's 75.9 (range 75.9-98.4) is a research estimate that cannot be recomputed from an official source. FORZE Reload is 1100 pts (rank 84). *Action:* Leave the probability blank under the 'never infer' rule, or keep it labelled RESEARCH and unverified. This is a policy decision for the owner.
- **F-12 [MED] Most prices come through aggregators, not the bookmaker's own feed** (13 rows). Pinnacle (own guest API) covers 7 rows. Thunderpick is read through bo3.gg relays for 13 rows (1079438, 1080279-1080290 excluding 1080279 read directly on Thunderpick). EGamersWorld relays 4 rows. Polymarket covers 1 row. Relays are not official bookmaker sites. *Action:* Keep the source link on every row. Label the source type (bookmaker API / aggregator / prediction market / own line) on the page.
- **F-13 [LOW] Rows not re-read in this session** (13 rows). 13 rows were not re-read today (see reconcile/reread.csv, result 'not re-read'). Their values are the board's, unchanged, and are not confirmed by this session. *Action:* Re-read in the next refresh.
- **F-14 [HIGH] Two boards on main disagree on win probabilities** (14 rows (8 by ≥1 pp)). console/data/picks.csv and executive/data/analysis.csv (both on main) give the same pick on 28/28 fixtures but different win probabilities on 14 rows, 8 of them by at least 1 pp: 1079624 +22.5 (research), 1081120 +8.1 (own line), 1081112 -5.1 (own line), 1080179 -2.9, 1079439 -2.1, 1080176 -1.8, 1079442 -1.8, 1080177 +1.3. Per-row values are in reconcile/cross_board.csv. The console values reproduce from the committed Pinnacle capture (02:45Z); the executive values come from a different snapshot or method, not reconciled here. *Action:* Owners of both boards to agree on one value per row and state the snapshot time. Until then both values are shown with the source for each.
- **F-15 [MED] Two different own-line methods on main** (1081112, 1081120). Console: Valve points with the repo's k = 0.4568 and the BO3 transform (reproduces 38.2 / 61.8 and 78.5 / 21.5). Executive: rank-based 1/(1+10^((rank_b−rank_a)/212)) with a fitted scale (33.1 / 66.9 and 86.6 / 13.4). The picks agree (6666 and mellren) but the probabilities do not. *Action:* Pick one own-line method for all open rows and document it. Not decided here.

## Sources

- Hotspawn: https://play.hotspawn.com/lobby · https://play.hotspawn.com/cs2-pickems
- Valve VRS 2026-10-05 (repo copy `cs2/data/raw/vrs_standings_global_2026_10_05.json.gz`): https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md
- Pinnacle guest API (committed capture): https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false
- EGW_GOTHIC (2026-10-14T04:38Z): https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B — headline 2.05 / 1.64; same pair at SpinAlto, RedSport, PlanBet, Kinbet; 1.881 / 1.782 at Spinbetter, 22bet, 1xBit; 'bc.game' not seen in chunks 0-2
- EGW_ENJOY (2026-10-14T04:38Z): https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7 — headline ENJOY 1.52 / B8 Academy 2.3 (chunk 0; bookmaker list not read)
- EGW_RUSTEC (2026-10-14T04:39Z): https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK — headline ex-RUSTEC 1.8 / mellren 1.8
- EGW_G2 (2026-10-14T04:39Z): https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L — headline G2 Ares 1.43 / The Last Resort 2.41 (chunk 0)
- TP_WBT (2026-10-14T04:39Z): https://thunderpick.io/esports/cs2-betting/elisa-breakout-series-2/11360/wbt-vs-ea-copenhagen/2807510 — Match Winner WBT +100 / EA Copenhagen -139 (chunk 1); BO1, 'October 15, 04:00' (UTC-4 render)
