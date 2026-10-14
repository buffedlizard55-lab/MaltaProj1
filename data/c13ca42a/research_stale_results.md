# C-02 research trail — verification of the 60 stale Hotspawn CS2 fixtures

Session: `arena/c13ca42a` · checked **2026-10-14T08:35Z** (all reads in this session) · method: direct reads of official HLTV results/event pages (and Liquipedia where the event is not on HLTV), matching each Hotspawn card (teams + card date) to the exact official match record. Every stale card is resolved in `fullpicks/data/stale_results.csv` (machine-readable, one row per card, `read_utc` stamped).

**Outcome: 54/60 verified with official match links · 6/60 unresolved (DraculaN Season 7 — evidence in §3.11).**

## 1. Event mapping (Hotspawn tournament → official event)

| Hotspawn tournament (card name) | Official event | Event page / results page used |
| --- | --- | --- |
| Urban Riga Open #5 | HLTV event 9219 | <https://www.hltv.org/results?event=9219> |
| Thunderpick World Championship 2026: South American Series #1 | HLTV event 9239 | <https://www.hltv.org/results?event=9239> |
| CCT Europe 2026 Challengers #4 | HLTV event 9236 | <https://www.hltv.org/results?event=9236> |
| CCT South America 2026 Series #3 | HLTV event 9233 | <https://www.hltv.org/results?event=9233> |
| European Pro League Series 8 Play-In | HLTV event 9245 (HLTV calls it "Closed Qualifier") | <https://www.hltv.org/results?event=9245> |
| European Pro League Series 8 | HLTV event 9246 (play-in groups + main stage) | <https://www.hltv.org/results?event=9246> |
| Svenska CS-Ligan 2026 | HLTV event 9235 ("Svenska CS-Ligan 2026 **Finals**"; event 9234 holds only the June 21–24 regular-season part) | <https://www.hltv.org/results?event=9235> |
| Rainhas do Clutch 2026 | HLTV event 9179 | <https://www.hltv.org/results?event=9179> |
| LG UltraGear Tournament 2026 | HLTV event 9232 | <https://www.hltv.org/results?event=9232> |
| CCT South America 2026 Series #7 | HLTV event 9452 | <https://www.hltv.org/results?event=9452> |
| DACH CS Masters Season 5 | **Not on HLTV** → Liquipedia `DACH_CS_Masters/Season_5` | <https://liquipedia.net/counterstrike/DACH_CS_Masters/Season_5> |
| DraculaN Season 7 | HLTV event 9312 — **upcoming** (see §3.11) | <https://www.hltv.org/events/9312/draculanan-season-7> |

Naming note: HLTV's stage label for EPL S8 Play-In cards is "Closed Qualifier" (9245); the card label is Hotspawn's own. Card dates matched the HLTV result dates exactly for all 9245 pairs, confirming the mapping.

## 2. Per-tournament resolutions (card → official match)

Format: `card_id teamA vs teamB (card date) → official result (official match id)`.

### 2.1 Urban Riga Open #5 — 12/12 (all group BO1, 2026-06-28)
- 1053431 GAMEHARMONY vs Coalesce → **Coalesce 13-11** ([2395602](https://www.hltv.org/matches/2395602))
- 1053432 Leo vs Aimhaus → **Leo 13-8** ([2395603](https://www.hltv.org/matches/2395603))
- 1053433 GAMEHARMONY vs Aimhaus → **Aimhaus 13-7** ([2395604](https://www.hltv.org/matches/2395604))
- 1053434 Leo vs Coalesce → **Leo 13-11** ([2395605](https://www.hltv.org/matches/2395605))
- 1053435 GAMEHARMONY vs Leo → **Leo 13-7** ([2395606](https://www.hltv.org/matches/2395606))
- 1053436 Aimhaus vs Coalesce → **Coalesce 13-10** ([2395607](https://www.hltv.org/matches/2395607))
- 1053469 BERG vs SINQU REHTI → **BERG 13-7** ([2395608](https://www.hltv.org/matches/2395608))
- 1053439 6666 vs ASTRAL → **ASTRAL 13-4** ([2395609](https://www.hltv.org/matches/2395609))
- 1053470 6666 vs SINQU REHTI → **SINQU REHTI 19-17** ([2395610](https://www.hltv.org/matches/2395610))
- 1053441 ASTRAL vs BERG → **ASTRAL 13-5** ([2395611](https://www.hltv.org/matches/2395611))
- 1053442 6666 vs BERG → **BERG 13-11** ([2395612](https://www.hltv.org/matches/2395612))
- 1053471 ASTRAL vs SINQU REHTI → **ASTRAL 13-6** ([2395613](https://www.hltv.org/matches/2395613))

### 2.2 TWC 2026 SA Series #1 — 8/8
- 1051789 MIBR Academy vs Isurus (06-26) → **MIBR Academy 2-0** ([2395422](https://www.hltv.org/matches/2395422))
- 1051790 Keyd vs Yawara (06-26) → **Keyd (Keyd Stars) 2-0** ([2395423](https://www.hltv.org/matches/2395423))
- 1051800 ShindeN vs MIBR Academy (06-27) → **ShindeN 2-0** ([2395424](https://www.hltv.org/matches/2395424))
- 1051801 Bounty Hunters vs UNO MILLE (06-27) → **UNO MILLE 2-0** ([2395425](https://www.hltv.org/matches/2395425))
- 1053313 Fake do Biru vs LP (06-27) → **LP 2-0** ([2395426](https://www.hltv.org/matches/2395426))
- 1051803 Fluxo vs Keyd (06-27) → **Fluxo 2-0** ([2395427](https://www.hltv.org/matches/2395427))
- 1051804 Fluxo vs UNO MILLE (06-28) → **UNO MILLE 2-1** ([2395428](https://www.hltv.org/matches/2395428))
- 1053679 ShindeN vs LP (06-28) → **ShindeN 2-0** ([2395429](https://www.hltv.org/matches/2395429))
- (Earlier duplicate 2395415, 06-24, is a different group round — not a card pair.)

### 2.3 CCT Europe 2026 Challengers #4 — 8/8
- 1052180 NEW VISION vs Julie&Cie (06-27) → **Julie&Cie 2-1 bo3** ([2395431](https://www.hltv.org/matches/2395431))
- 1052181 Just Players vs OlyBet (06-27) → **Just Players 1-0 (decided)** ([2395432](https://www.hltv.org/matches/2395432))
- 1052599 Mai Tai vs Megoshort (06-27) → **Mai Tai 1-0 (decided)** ([2395433](https://www.hltv.org/matches/2395433))
- 1052183 Misa vs Wampirki (06-27) → **Misa 1-0 (decided)** ([2395434](https://www.hltv.org/matches/2395434))
- 1052184 Atreides vs Donstu (06-28) → **Atreides 2-1 bo3** ([2395435](https://www.hltv.org/matches/2395435))
- 1052185 sAw vs Entropy (06-28) → **Entropy 2-1 bo3** ([2395436](https://www.hltv.org/matches/2395436)) — *see ambiguity note §4.1*
- 1052186 Lilmix vs Subtop De France (06-28) → **Subtop De France 2-1 bo3** ([2395437](https://www.hltv.org/matches/2395437))
- 1052187 BIG Academy vs Endless Journey (06-28) → **Endless Journey 1-0 (decided)** ([2395438](https://www.hltv.org/matches/2395438))

### 2.4 CCT South America 2026 Series #3 — 8/8
- 1052699 Vasco vs Red Feet (06-27) → **Red Feet 1-0 (decided)** ([2395554](https://www.hltv.org/matches/2395554))
- 1052700 GameHunters vs VEXA (06-27) → **GameHunters 2-1 bo3** ([2395555](https://www.hltv.org/matches/2395555))
- 1052701 paiN Academy vs Alka (06-27) → **ALKA 2-1 bo3** ([2395556](https://www.hltv.org/matches/2395556))
- 1052702 Procyon vs BESTIA Academy (06-27) → **BESTIA Academy 1-0 (bo3 decided in 2 maps)** ([2395557](https://www.hltv.org/matches/2395557))
- 1052695 MIBR Academy vs Patins de Ferrari (06-28) → **Patins da Ferrari 2-1 bo3** ([2395558](https://www.hltv.org/matches/2395558))
- 1052696 Yawara vs Blitzkrieg (06-28) → **Yawara 2-0 bo3** ([2395559](https://www.hltv.org/matches/2395559))
- 1052697 METANOIA Wolves vs Guara (06-28) → **GUARA 2-1 bo3** ([2395560](https://www.hltv.org/matches/2395560))
- 1052698 ex-KRÜ vs MAGICOS (06-28) → **MAGICOS 1-0 (decided)** ([2395561](https://www.hltv.org/matches/2395561))

### 2.5 EPL S8 "Play-In" (HLTV: Closed Qualifier, event 9245) — 6/6
Card dates matched HLTV result dates exactly:
- 1052746 Fortress vs Endless Journey (06-26) → **Endless Journey 2-0 bo3** ([2395499](https://www.hltv.org/matches/2395499))
- 1052747 Sashi Academy vs eternal premium (06-26) → **Sashi Academy 2-1 bo3** ([2395497](https://www.hltv.org/matches/2395497))
- 1052748 Inner Circle Academy vs sAw (06-27) → **Inner Circle Academy 2-0 bo3** ([2395500](https://www.hltv.org/matches/2395500))
- 1052749 Misa vs WROTBERRY (06-27) → **Misa 2-0 bo3** ([2395501](https://www.hltv.org/matches/2395501))
- 1052750 Honvéd vs OlyBet (06-28) → **Honvéd 2-1 bo3** ([2395502](https://www.hltv.org/matches/2395502))
- 1052751 ex-MANA vs Subtop De France (06-28) → **ex-MANA 2-1 bo3** ([2395503](https://www.hltv.org/matches/2395503))
- (Several teams met twice in this event — e.g. WBT 2-1 Misa on 07-02 [2395511], SAW 2-0 Entropy on 07-03 [2395455] — disambiguated by card date.)

### 2.6 EPL S8 (event 9246) — 1/1
- 1055478 illwill vs Lavked (card 07-10) → **Lavked 1-0 (decided)** ([2395526](https://www.hltv.org/matches/2395526)) — *HLTV dates it 2026-07-09, one day off the card; it is the only illwill–Lavked fixture in the event's play-in groups. See §4.2.*

### 2.7 Svenska CS-Ligan 2026 (Finals, event 9235) — 6/6
- 1053068 Johnny Speeds vs ReThink (06-26) → **ReThink 2-1 bo3** ([2395365](https://www.hltv.org/matches/2395365))
- 1053069 roamsfiest vs train launcher (06-26) → **train launcher 2-0 bo3** ([2395366](https://www.hltv.org/matches/2395366))
- 1053070 ReThink vs train launcher (06-26) → **ReThink 2-1 bo3** ([2395367](https://www.hltv.org/matches/2395367))
- 1053071 Johnny Speeds vs roamsfiest (06-27) → **roamsfiest 2-1 bo3** ([2395368](https://www.hltv.org/matches/2395368))
- 1053072 train launcher vs roamsfiest (06-27) → **roamsfiest 2-0 bo3** ([2395369](https://www.hltv.org/matches/2395369))
- 1053073 roamsfiest vs ReThink (06-27) → **ReThink 2-1 bo3** ([2395370](https://www.hltv.org/matches/2395370))

### 2.8 Rainhas do Clutch 2026 — 2/2
- 1053146 Atrix vs Clutchain (06-26) → **Clutchain fe 2-0 bo3** ([2395353](https://www.hltv.org/matches/2395353))
- 1052686 shimmer vs MIBR fe (06-26) → **MIBR fe 3-1 bo5** ([2395354](https://www.hltv.org/matches/2395354))

### 2.9 LG UltraGear Tournament 2026 — 1/1
- 1051301 CYBERSHOKE Prospects vs PCIFIC (06-26) → **CYBERSHOKE Prospects 2-0 bo3** ([2395413](https://www.hltv.org/matches/2395413))
- (A PCIFIC 2-1 CYBERSHOKE Prospects match exists on 06-25 [2395406] — different round; card date 06-26 selects 2395413.)

### 2.10 DACH CS Masters Season 5 — 1/1 (Liquipedia, not on HLTV)
- 1052357 BIG Academy vs BERG (06-27) → **BIG Academy 2-0** — Grand Final, offline Munich.
  Evidence: [Liquipedia event page](https://liquipedia.net/counterstrike/DACH_CS_Masters/Season_5) prize table (1st BIG Academy $3,133.17; 2nd Esport BERG $1,481.14), C-Tier 2026 Q1 listing ("Mar 04 – Jun 27, 2026, Munich, BIG Academy / Esport BERG"), and player match logs (e.g. [Tripex17](https://liquipedia.net/counterstrike/Tripex17): "2026-06-27 1st … BIG.A 2 : 0 BERG"; [ZogeN](https://liquipedia.net/counterstrike/ZogeN), [Tree60](https://liquipedia.net/counterstrike/Tree60), [Askan](https://liquipedia.net/counterstrike/Askan): "2026-06-27 2nd … BERG 0 : 2 BIG.A $1,481.14").
  Liquipedia search hit: the tournament page is titled `DACH_CS_Masters/Season_5` (no year in the title).

### 2.11 CCT South America 2026 Series #7 — 1/1
- 1081105 SUKEBAN vs your end (10-13) → **your end 1-0 (decided)** ([2399460](https://www.hltv.org/matches/2399460)), result dated 2026-10-13 — card date matches.

## 3. Unresolved: DraculaN Season 7 — 6/6 fixtures (§3.11 applies to all)

Cards 1051339 (Acend–Infinite), 1051340 (Walczaki–Inner Circle), 1051341 (Sharks–Inner Circle), 1051342 (ex-Tricked–Acend), 1051343 (Sharks–ex-Tricked), 1051344 (Inner Circle–Acend) — card dates 2026-06-26 … 2026-06-28.

### 3.11 Evidence (checked 2026-10-14T08:35Z)
1. HLTV event page <https://www.hltv.org/events/9312/draculanan-season-7>: **Upcoming, 2026-10-19 → 2026-10-23, Bucharest (ROU), $35,000, 24 teams**. Status is *not* finished; **no results of any kind exist** for the event.
2. Official schedule <https://www.hltv.org/events/9312/matches>: first round (Oct 19) named pairs include INFINITE vs Insiders, aimclub vs BASEMENT BOYS, BC.Game vs Drama, WBT vs Nexus, Iberian Soul vs HYPERSPIRIT, Sashi vs MOUZ NXT, ASTRAL vs Leo; Oct 20 upper bracket lists FaZe, Eternal Fire, Envy, BBL, HEROIC, SINNERS, JiJieHao, Luminosity vs TBD. **None of the six Hotspawn pairings (Acend–Infinite, Walczaki–Inner Circle, Sharks–Inner Circle, ex-Tricked–Acend, Sharks–ex-Tricked, Inner Circle–Acend) appears anywhere in the published schedule.** INFINITE (present in the event) plays Insiders, not Acend.
3. Teams seen in the attending list so far: FaZe, Envy, Luminosity, HEROIC, Eternal Fire, SINNERS, JiJieHao, BBL, Iberian Soul, SAW, BC.Game, Leo, INFINITE, BASEMENT BOYS, aimclub, ASTRAL, WBT, Nexus, Drama, MOUZ NXT. Acend, Walczaki, Inner Circle, ex-Tricked and Sharks were not among them in the chunks read.
4. The Hotspawn card dates (June 26–28) predate the official event window (Oct 19–23) by almost four months.

**Decision:** the Hotspawn card data for this tournament is internally inconsistent with the official event. No result exists to verify and no pick can be confirmed from an official source → all six picks are **withheld (blank)** and flagged `UNRESOLVED-DRACULAN` on the board and on <https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/fullpicks/unresolved.html>. This is a data-quality finding about the Hotspawn cards, recorded as a limitation — not a coverage gap in this session's method.

## 4. Ambiguities and caveats (recorded on the board)

1. **sAw–Entropy double-play (1052185).** SAW and Entropy met twice in CCT Europe 2026 Challengers #4: [2395436](https://www.hltv.org/matches/2395436) (2026-06-28, Entropy 2-1 SAW) and [2395455](https://www.hltv.org/matches/2395455) (2026-07-03, SAW 2-0 Entropy). The card date 2026-06-28 selects 2395436 → **Entropy**. Flagged `AMBIGUOUS-DOUBLE-PLAY`.
2. **illwill–Lavked date offset (1055478).** Card date 2026-07-10; HLTV dates the match 2026-07-09. It is the only illwill–Lavked fixture in EPL S8's play-in groups, so the result (**Lavked 1-0**) is certain; the one-day calendar offset is flagged `DATE-OFF-BY-ONE` (same class of card-date error as §3).
3. **Name aliases** (card name → official name), all confirmed as the same teams by context (event, opponents, logos on the HLTV pages): Keyd → Keyd Stars; sAw → SAW; WROTBERRY → WBT; Clutchain → Clutchain fe; shimmer → Shimmer; Alka → ALKA; Guara → GUARA; Donstu → DONSTU; Megoshort → megoshort; Patins de Ferrari → Patins da Ferrari; BERG → Esport BERG (Liquipedia).
4. **Event naming.** EPL S8 "Play-In" (Hotspawn) = "Closed Qualifier" (HLTV 9245). Svenska CS-Ligan 2026 cards land under the companion HLTV event "Svenska CS-Ligan 2026 Finals" (9235), while 9234 holds only the earlier regular-season matches.
5. **HLTV "def" format** = series decided in a single map (treated as BO1 on the board; "bo3"/"bo5" scores are map scores as printed by HLTV).

## 5. Sources consulted (this session, 2026-10-14 ~08:35Z)

- HLTV results pages: events 9219, 9239, 9236, 9233, 9245, 9246 (chunks 0–2), 9235, 9179, 9232, 9452 (as listed above).
- HLTV event pages: 9312 (overview + matches, for the DraculaN finding), 9232/9234/9179/9452 overviews (status checks).
- Liquipedia: search for "DACH CS Masters Season 5"; event page `DACH_CS_Masters/Season_5`; player pages Tripex17, ZogeN, Tree60, Askan (match-log corroboration).
- Hotspawn: live re-read of <https://play.hotspawn.com/cs2-pickems> (card list, 25 open + 3 locked/started today + 60 stale; header "88") — used for the fixture list only; **crowd "picked %" never used as an input**.
- Liquipedia was checked first for DACH (page missing under the guessed `DACH_CS_Masters_2026/Season_5` title; located via site search).
