# Live research log — session `arena/e13aca8a`, 2026-10-14

Purpose: resolve a pick for **every** Hotspawn CS2 fixture that the featured route (primary
esportsbook moneyline) cannot cover, using the ladder **HLTV → esportsbooks → esports betting
lines**, and record every source read so a human can re-check each one. Read window:
**2026-10-14T04:34Z – 05:20Z** (platform web fetch; the agent sandbox itself has no general
egress, which is also why the scheduled GitHub Actions collector remains the refresh path).

Rule followed throughout: **no value without a named page**. Values below are transcribed from
the pages listed. Hotspawn crowd percentages ("14% picked") are visible on every Hotspawn card
and are **never stored or used**. Where a source prints a price this project refuses, the refusal
is recorded with its reason instead of the number.

---

## 1. Slate re-read (E-01) — play.hotspawn.com

| Read | Time (UTC) | What the page printed |
|------|-----------|----------------------|
| https://play.hotspawn.com/lobby | 04:34–04:35 | "68 matches this week"; CS2 tier filter **All (88) · B (24) · C (60) · S (4)**; 28 CS2 cards under Closing Soon + Upcoming (Oct 14–16) |
| https://play.hotspawn.com/cs2-pickems | 04:50–04:52 | same 28 cards; tournament filter with per-tournament counts (17 tournaments) |

Findings (all verifiable against the pages above and `executive/data/fixtures.csv`):

* **28/28 open fixtures on our board appear on the live board with identical pairings.**
  Lock countdowns on the live cards are consistent with `lock = start − 360 s` (the payload
  convention recorded in earlier sessions). Example: Gothic vs Lavked card at 04:31Z read
  "Locks in 03:22:35" → lock 07:54Z = fixture `1079621` `lock_utc` exactly.
* Live pool = **88 CS2 fixtures** vs our inventory 89. The delta is exactly one tournament:
  **ESL Challenger League Season 52: North America - Cup #3** (fixture `1079546`, Zomblers vs
  Overtake Sector) is **no longer listed** (its start 2026-10-14T01:00Z has passed; the card is
  retired). The other 16 tournament counts match the inventory exactly (see
  `executive/data/research_lines.json` → `slate_recheck`).
* Displayed times on `/lobby` are UTC−4 (rendered local); exact UTC times come from the
  committed payload capture (epoch ms) and are cross-checked by the countdowns above.

## 2. Research ladder — HLTV (first rung)

| Source | What it established |
|--------|--------------------|
| https://www.hltv.org/events/9442/cct-2026-europe-series-11 | CCT 2026 Europe Series 11 (Oct 13–25, $25,000, 24 teams). Group-Swiss rows carry HLTV rank badges: **FORZE Reload #90**, **ex-RUSTEC #93**, **Gothic #169**, **LFO 10 #170**. All four of our Series #11 fixtures are listed **bo3**. `FORZE Reload vs LFO 10` → HLTV match **2399301**, 14/10/26. |
| https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11 | fixture identity + bo3 (via event page; match page itself refuses non-browser clients) |
| https://www.hltv.org/team/14084/lfo-10 | **LFO 10** = Sweden; HLTV team id 14084; roster history dottie/Jackinho/Sapec/flaw/tvs; **currently unranked** ("doesn't have a world rank at the moment"), **peak #170** (1 week); win rate 33.3% last 3 months; recent official results: 0:2 ENCE (08/10), 1:2 MOUZ NXT (07/10), 2:0 MAYBE (07/10) in ESL Challenger League S52 Europe Cup 8 (event 9374). |
| https://www.hltv.org/valve-ranking/teams/2026/october/12 | HLTV's **Valve ranking (beta)** page dated Oct 12 lists **LFO 10 #170, 765 Valve points** (roster dottie/flaw/Sapec). ⚠ This page is HLTV's beta projection ("includes matches and secured prize money from unfinished events") — **not** the official weekly Valve file. Used as evidence only, labelled as such. |
| https://www.hltv.org/team/13900/banda-chuya | **Banda Chuya** = HLTV team 13900 (PL); currently unranked, **peak #162** (1 week); win rate 26.7% last 3 months; recent: 3:13 GenOne (11/10, PGL Bucharest 2027 OQ1), 1:2 HYPERSPIRIT (08/10), 2:0 Revise (07/10), 1:2 HYPERSPIRIT (07/10). Upcoming: **vs 6666**, HLTV match **2399462**, CCT 2026 Europe Series 12 Closed Qualifier (event **9456**). |
| https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier | fixture identity (event naming: "Closed Qualifier" = Hotspawn's "Series #12 Play-In") |
| https://github.com/ValveSoftware/counter-strike_regional_standings (GitHub API, `live/2026/`) | Official file inventory re-checked 05:0xZ: **newest global file is still `standings_global_2026_10_05.md`** (monthly cadence: 01_05, 02_02, … 10_05). **LFO 10 has no entry in the official file** — the earlier "absent from every ranking" finding stands for the official file; the Oct 12 numbers exist only on HLTV's beta page. FL-RATINGS-WEEK-OLD remains unavoidable. |

## 3. Research ladder — esportsbooks (second rung)

| Source | What it printed | Used? |
|--------|----------------|-------|
| https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3 | "FORZE Reload VS" 14.10.2026 17:00, **Bo3**, odds **1.8 / 1.8**, opponent lineup **Jackinho, Sapec, dottie, flaw, tvs** (SE) | 1.8/1.8 = equal-pair placeholder → **refused as price**; page used for format + lineup identity |
| https://egamersworld.com/counterstrike/match/4kY9VAmiEg/banda-chuya-vs-6666-JdPgKgp5y | "banda chuya VS 6666" 14.10.2026 11:00 (07:00 on page), **Bo3**; EGW rating **902 vs 515**; last-5 wins 3 vs 5; last-10 wins 7 vs 7; "banda chuya 1.8" (single side) | single-side placeholder → **refused as price**; page used for format + rating/form cross-check (rating labelled a rating, never a price) |
| https://egamersworld.com/counterstrike/match/1sGIL2gAYu/wraith-pcific-vs-ryvex-bBH6HvaalZ | "WRAITH PCIFIC VS Ryvex" 14.10.2026 14:00, **Bo3**; "WRAITH PCIFIC 1.8" (single side); tournament sidebar lists ENJOY–B8 (14.10 04:00), banda chuya–6666 (14.10 07:00), PCIFIC Espor–Ryvex (14.10 10:00), **mellren – Privateer Gaming 16.10 10:00** | single-side placeholder → **refused as price**; used for format + the mellren–Privateer listing |
| bo3.gg relayed prices (in `feeds/data/market_feed.csv`, captured 2026-10-14T03:18:57Z) | decimal moneylines for 21 open fixtures (incl. Elisa BreakOut cards, Stake Pulse, Thunderpick S-tier) | already ingested by the hourly feed; not re-typed here |
| https://bo3.gg/teams/sokerorg | **Sökerorg** roster = **Jackinho, Sapec, tvs, flaw, dottie** (SE) | identity evidence for LFO 10 |

## 4. Research ladder — betting lines / prediction markets (third rung)

Live read of https://polymarket.com/esports/cs2 and https://polymarket.com/esports/cs2/cct-europe
at **2026-10-14T04:50Z** (board: "CS2 (94)" markets). CCT Europe board (10 markets):

| Market (page) | Printed (share prices) | Volume | Verdict |
|---------------|----------------------|--------|---------|
| [cs2-forzer-skr2-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14) "FORZE Reload vs Sökerorg (BO3) - CCT Europe Series #11 Group Stage", Today 1:00 PM (17:00 UTC) | FORZE Reload **88¢** (1.14x) / Sökerorg **16¢** (6.25x) | $373.86 | **ingested** as prediction-market line for `1079624` (identity: Sökerorg = LFO 10, roster-verified 5/5 vs HLTV 14084 + EGW lineups + Liquipedia EPL S7) → de-vig 84.6 / 15.4, pick FORZE Reload |
| [cs2-wraith-ryvex-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-wraith-ryvex-2026-10-14) "WRAITH PCIFIC vs Ryvex (BO3) - Series #12 Group B" | WRAITH PCIFIC **82¢** (1.22x) / Ryvex **21¢** (4.76x) | $666.84 | ingested (research quote; the hourly feed's 03:18Z row is tighter and stays the headline) |
| [cs2-enjoy-b8acad-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-enjoy-b8acad-2026-10-14) "ENJOY vs B8 Academy (BO3) - Series #12 Group A" | ENJOY **62¢** (1.61x) / B8 Academy **39¢** (2.56x) | $1.16K | ingested (feed's 03:18Z row remains headline) |
| [cs2-gothic-lavked-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-gothic-lavked-2026-10-14) | Gothic **50¢** (2.00x) / Lavked **51¢** (1.96x) | $304 | ingested (drift record; EGW 2.05/1.64 remains headline) |
| [cs2-rustec-mellre-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-rustec-mellre-2026-10-14) | ex-RUSTEC **65¢** (1.54x) / mellren **36¢** (2.78x) | $9.67K | ingested (drift record) |
| [cs2-g2a-tlr-2026-10-14](https://polymarket.com/esports/cs2/cct-europe/cs2-g2a-tlr-2026-10-14) | G2 Ares **70¢** (1.43x) / TLR **31¢** (3.23x) | $1.33K | ingested (drift record) |
| [cs2-mellre-pg5-2026-10-16](https://polymarket.com/esports/cs2/cct-europe/cs2-mellre-pg5-2026-10-16) "mellren vs Privateer Gaming (BO3) - Series #12 Group D" | mellren **94¢** (1.06x) / Privateer Gaming **93¢** (1.08x) | **$0.00** | **refused** — uninitialised book (both sides >90¢; a $1 pair sums to $1.87). De-vigging would invent a ~50/50. Title still used as the BO3 source for `1081120` |
| cs2-lilmix-revise-2026-10-16 / cs2-morrow-ill4-2026-10-16 / cs2-ssins-maybe-2026-10-14 | Lilmix 94¢/Revise 93¢; MORROW 94¢/ILLYRIANS 94¢; Saint Sinners 66¢/maybe 35¢ | $0 / $0 / $36.56 | not Hotspawn fixtures — recorded for completeness, not ingested |

**Banda chuya vs 6666 (`1081112`) has no Polymarket market** (the CCT Europe board's 10 markets are
listed above) and no esportsbook two-sided price (EGW prints a single 1.8 placeholder). It is the one
open fixture where the ladder finds **no price anywhere** → the board publishes its own originated
line from the official Valve points (Banda Chuya 801 vs 6666 923 → 33.1 / 66.9, pick **6666**),
cross-checked on HLTV (6666 world-ranked #80 per the committed ranking capture; Banda unranked; form
5-win streak for 6666 vs 26.7% 3-month win rate for Banda). One counter-signal is published, not
reconciled: **EGW's proprietary rating favours Banda Chuya 902 vs 515** → `FL-RESEARCH-CROSSCHECK-CONFLICT`.

## 5. Identity checks (never inferred)

| Listing name | = Hotspawn name | Evidence (≥2 independent pages) |
|--------------|-----------------|--------------------------------|
| Polymarket "Sökerorg" | **LFO 10** | bo3.gg/teams/sokerorg roster Jackinho/Sapec/tvs/flaw/dottie = HLTV 14084 roster = EGW match-page lineup of the opponent; same event (CCT Europe Series #11), same date, same 17:00 UTC slot, same BO3. Liquipedia EPL S7 lists "Sökerorg" with the same five players. |
| Polymarket/EGW "WRAITH PCIFIC" | **PCIFIC** | already roster-verified in reviews/228bb5bc-verification.md R-228-04 (HLTV team 13054; EGW dual listing "PCIFIC Espor"). Re-confirmed on the live Polymarket + EGW pages above. |
| EGW "banda chuya" (PL flag) | **Banda chuya** | HLTV team 13900 page carries the same upcoming fixture (vs 6666, event 9456); names identical. |
| Hotspawn "Privateer" | Polymarket/EGW "Privateer Gaming" | same fixture slot (Series #12 Group D, Oct 16), VRS entry "Privateer" #271 roster Ariant0/Frazehh/JAUSTERE/M1n1maL/Prime = HLTV team 13914 roster Frazehh/Prime/M1n1maL/… |

## 6. What changed on the board because of this pass

| Fixture | Before | After | Why |
|---------|--------|-------|-----|
| `1079624` FORZE Reload vs LFO 10 | T4 provisional bound 98.4/1.6 (LFO 10 unrateable) | **T2 prediction market 84.6/15.4, pick FORZE Reload**, BO3 stated | Polymarket prices the slot (roster-verified alias); HLTV states bo3 |
| `1081112` Banda chuya vs 6666 | T3 own line, format unknown | T3 own line 33.1/66.9, pick 6666, **BO3 stated**, conflict flag published | EGW/HLTV state Bo3; research cross-checks recorded; no price exists anywhere |
| `1081120` mellren vs Privateer | T3 own line, format unknown | T3 own line 86.6/13.4, pick mellren, **BO3 stated**, market refusal published | Polymarket title states BO3; prices refused (no liquidity) |
| `1081111`, `1081113` | T2 (feed) | unchanged headline (feed rows tighter), research quotes recorded as drift | — |
| coverage | 25/28 stated formats | **28/28 stated formats** | research format sources |

Board totals after rebuild (2026-10-14T05:2xZ): 28/28 open fixtures carry a pick + both
probabilities + source links; 26 market basis (5 primary + 21 secondary/prediction), 2 own-line
basis, **0 provisional bounds**, 0 without a pick. Every number's read minute is on its row.

## 7. Files

* Machine-readable input consumed by `executive/build.py`: [`executive/data/research_lines.json`](../../executive/data/research_lines.json)
  (quotes, formats, row notes, refusals, slate recheck — quotes merge into the quote pool with
  their own `captured_utc`; refusals are never ingested as prices).
* Generated output: [`executive/unresolved.html`](../../executive/unresolved.html) (the separate
  unresolved-picks section, linked from the executive summary) + the rebuilt board pages.
* Verification record: [`reviews/e13aca8a-verification.md`](../../reviews/e13aca8a-verification.md).
