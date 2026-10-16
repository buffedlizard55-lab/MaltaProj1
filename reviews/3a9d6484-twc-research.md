# TWC 2026 day 1–4 research dossier — session `arena/3a9d6484`

Independent research contribution. Every value below was read live from the linked source with the fetch tool on
**2026-10-16 between 19:44Z and 20:15Z** unless a row says otherwise. Nothing here is copied from another agent's
summary, and nothing is inferred: a value that could not be confirmed from the linked source is left **blank** and
marked *unverified*. Hotspawn's crowd percentages are never used as probabilities.

Scope of this file: the day-1 upset review the user asked for, the Aurora roster-change premise, day-2/day-3 result
review, and day-4 (17 Oct) picks. The primary board (`hotspawn/**`) is owned by session `arena/4061d8f1`; this file
only *requests* integration (see §7) and does not edit that board.

**Status after PR #177 (added 2026-10-16 20:25Z):** the board owner merged
[PR #177](https://github.com/buffedlizard55-lab/MaltaProj1/pull/177) at 19:46:10Z, and `main` @ `098c49c` is now the
published board. Integration requests that landed: the day-4 watch and the external market watch are live on
`hotspawn/twc.html`, and the executive summary surfaces the "no day-4 main-event fixture in this capture" limitation.
Still open after the merge: a Hotspawn listing for SF1/SF2 (a pick can only be submitted where the lobby lists the
match; the four-hourly collector captures it automatically if it appears), the `capture.json` join-key gap (D3), the
affiliate-redirect source on row 1081527 (D4), and the HLTV backoff patch (D5) — all logged in
`reviews/3a9d6484-verification.md` §6 and in `COORDINATION.md`.

---

## 1. Fixture facts — day 1 to day 4 (verified)

| Day | Stage | Series | Score | Maps (as published) | Source (read 2026-10-16) |
|---|---|---|---|---|---|
| 1 — Wed 14 Oct | Group A opener | **9z** vs Aurora | **9z 2-0** | Inferno 13-11 9z · Nuke 13-1 9z | [HLTV news 45736](https://www.hltv.org/news/45736/aurora-beat-9z-to-secure-third-consecutive-top-four-appearance) (re-read 20:0xZ), [HLTV 2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) |
| 1 | Group A opener | **Falcons** vs Ninjas in Pyjamas | **Falcons 2-0** | Ancient 16-13 OT · Dust II 13-6 | [HLTV event 8932 bracket](https://www.hltv.org/events/8932/thunderpick-world-championship-2026) (read 19:47Z) |
| 1 | Group B opener | **Legacy** vs PARIVISION | **Legacy 2-0** | Dust II 13-11 · Mirage 16-14 OT | [HLTV event 8932 bracket](https://www.hltv.org/events/8932/thunderpick-world-championship-2026) |
| 1 | Group B opener | **FURIA** vs BETBOOM | **FURIA 2-0** | — *(map scores not re-read in this session: unverified here)* | [HLTV analytics 2399414](https://www.hltv.org/betting/analytics/2399414/furia-vs-aurora-thunderpick-world-championship-2026) lists "BETBOOM 2 : 0 LAN" in FURIA's last five results |
| 2 — Thu 15 Oct | Group A winners' | **Falcons** vs 9z | **Falcons 2-1** | — *(not re-read here: unverified)* | [HLTV event 8932 bracket](https://www.hltv.org/events/8932/thunderpick-world-championship-2026) |
| 2 | Group A elimination | **Aurora** vs Ninjas in Pyjamas | **Aurora 2-0** | Cache 13-9 · Dust2 13-7 | [HLTV 2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) + [HLTV news 45724](https://www.hltv.org/news/45724/nip-spared-scheduling-headache-after-early-thunderpick-world-championship-exit) |
| 2 | Group B winners' | **FURIA** vs Legacy | **FURIA 2-1** | — *(not re-read here: unverified)* | [HLTV event 8932 bracket](https://www.hltv.org/events/8932/thunderpick-world-championship-2026) + [HLTV news 45730](https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy) |
| 2 | Group B elimination | **BETBOOM** vs PARIVISION | **BETBOOM 2-1** | — *(not re-read here: unverified)* | [HLTV news 45729](https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc) |
| 3 — Fri 16 Oct | **Group A decider** | **Aurora** vs 9z | **Aurora 2-0** | Cache 13-11 Aurora · Inferno 13-4 Aurora | [HLTV news 45736](https://www.hltv.org/news/45736/aurora-beat-9z-to-secure-third-consecutive-top-four-appearance) (16-10-2026 12:21), [HLTV 2399412](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) |
| 3 | **Group B decider** | BETBOOM vs Legacy | **in progress at read** (1-1 in maps) | Nuke 16-13 BETBOOM (OT) · Dust2 13-11 Legacy · Mirage pending | [HLTV 2399413](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026) (read 19:58Z, page showed "LIVE"), [EGamersWorld event](https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H) (odds BetBoom 2.40 / Legacy 1.50, read 19:57Z) |

Day 3 Group A decider detail as published by HLTV: Aurora "decided against the Nuke pick the second time around and
opted for Cache instead", kyxsan 33-20 (1.45 rating) and Wicadia the CT anchor on Inferno. The same report notes the
7 October meeting "just 10 days ago" where **Aurora beat FURIA 2-1 at ESL Pro League Season 24**
([HLTV 2398743](https://www.hltv.org/matches/2398743/furia-vs-aurora-esl-pro-league-season-24)).

## 2. Day-4 fixtures, format and start times (verified)

| # | Stage | Series | Format | Start (UTC) | HLTV match |
|---|---|---|---|---|---|
| 1 | Semifinal 1 | **FURIA vs Aurora** | BO3, LAN | **2026-10-17 14:00Z** | [2399414](https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026) |
| 2 | Semifinal 2 | **Falcons vs BETBOOM/Legacy winner** | BO3, LAN | **2026-10-17 17:00Z** | [2399415](https://www.hltv.org/matches/2399415/falcons-vs-betboom-legacy-winner-thunderpick-world-championship-2026) |
| 3 | 3rd-place decider (day 5) | TBD vs TBD | BO3 | 2026-10-18 11:30Z | [2399416](https://www.hltv.org/matches/2399416/thunderpick-world-championship-2026-3rd-place-decider-match-thunderpick-world-championship-2026) |
| 4 | Grand final (day 5) | TBD vs TBD | **BO5** | 2026-10-18 15:00Z | [2399417](https://www.hltv.org/matches/2399417/thunderpick-world-championship-2026-grand-final-thunderpick-world-championship-2026) |

How the times were established: HLTV's own pages render 10:00 / 13:00 / 07:30 / 11:00 in the reader's local time
(US Eastern), and Polymarket's contract for semifinal 1 states `gameStartTime 2026-10-17 14:00:00+00`
([Polymarket event JSON](https://gamma-api.polymarket.com/events?slug=cs2-furia-aur1-2026-10-17), read 19:52Z);
Liquipedia lists the same two semifinals as "Oct 17 - 10:00 EDT" and "Oct 17 - 13:00 EDT"
([Liquipedia TWC 2026](https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026), read 19:44Z).
Venue: **BLAST Arena Studios, Attard, Malta** (Liquipedia infobox) — this closes the "exact studio locality not
verified" note in `hotspawn/research/twc2026.json`.

## 3. Outside lines for day 4 (never Hotspawn)

| Fixture | Source | Raw price | De-vigged / implied | Read (UTC) |
|---|---|---|---|---|
| FURIA vs Aurora | EGamersWorld (BC.Game relay) | FURIA **1.85** · Aurora **1.85** | **50.0% / 50.0%** (overround 108.1%) | 2026-10-16 19:57Z |
| FURIA vs Aurora | Polymarket "Match Winner" | FURIA **0.52** · Aurora **0.48** | 52% / 48% | 2026-10-16 19:52Z (market `updatedAt` 19:30:53Z) |
| FURIA vs Aurora | HLTV odds & prediction page | numeric bookmaker prices not shown in the fetched block | — | 20:0xZ |
| FURIA vs Aurora | HLTV analytics summary (qualitative) | — | "**Aurora is the bookmaker favorite with the best odds**" | 20:0xZ |
| Falcons vs BETBOOM/Legacy winner | — | **blank — no market exists until the decider finishes (unverified)** | — | — |

Honest reading of the disagreement: Polymarket and our own Valve-points line lean **FURIA**, EGamersWorld is
dead even, and HLTV's bookmaker-aggregate summary leans **Aurora**. This is exactly the `MODEL_MARKET_SPLIT`
situation the board's flag set already defines; the two-way markets agree the series is close to a coin flip.

## 4. Our own originated line (no bookmaker input)

Method, identical to the published board: `P(A) = 1 / (1 + 10^(-k·Δpoints/400))` with **k = 0.4598** fitted in
`hotspawn/calibrate.py` on Valve's published match results, and Δpoints taken from Valve's official standings
snapshot **2026-10-05** (`eec4853`, [global standings](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md),
cloned in this session; rows re-read from the file).

| Team | Valve rank | Valve points | Roster as published by Valve |
|---|---|---|---|
| Legacy | #2 | 1931 | — |
| Falcons | #6 | 1843 | — |
| FURIA | #7 | 1829 | — |
| Aurora | #9 | 1716 | — |
| BETBOOM | #11 | 1596 | — |
| 9z | #17 | 1543 | — |
| Ninjas in Pyjamas | #18 | 1534 | — |
| Nemesis | #29 | 1455 | mag1k3Y, r3salt, Sdaim, SELLTER, tex1y |
| Betclic (Betclic Apogee) | #45 | 1333 | Demho, ex1st, Prism, Qlocuu, ultimate |
| aimclub | #77 | 1113 | ERSIN, mhN1, ragga, waZz, zewts |
| BASEMENT BOYS | #102 | 1036 | kAlash, kr1vda, maggent, OWNER, Tr0ublE |

Originated probabilities (computed in this session, arithmetic only):

| Fixture | Our own line | Cross-check (HLTV world ranking, read 20:0xZ) |
|---|---|---|
| FURIA vs Aurora | **FURIA 57.4% / Aurora 42.6%** | FURIA #4, Aurora #6 (HLTV analytics panel) |
| Falcons vs Legacy | **Legacy 55.8% / Falcons 44.2%** | — *(HLTV ranks for this pairing not re-read: unverified)* |
| Falcons vs BETBOOM | **Falcons 65.8% / BETBOOM 34.2%** | — *(same)* |

## 5. Day-4 picks

Pick rule applied (documented board rule, unchanged): use the highest-confidence **source-backed** probability — a
de-vigged outside line when one exists for that fixture, otherwise the labelled own line — and never use the Hotspawn
crowd share as a probability. Contrarian "leaderboard" plays stay gated behind the transparency gates in §6.

| Fixture | Headline pick | Probability used | Basis | Contrarian note |
|---|---|---|---|---|
| **FURIA vs Aurora** (17 Oct 14:00Z) | **FURIA** | 57.4% (own line) / 52% (Polymarket) | own line + Polymarket agree on direction; EGW even; HLTV summary leans Aurora | Aurora is the popular side after a 2-0 decider win and a 2-1 EPL win over FURIA 10 days ago, so FURIA is the *unpopular* side of a near-coin-flip — but see §6: no Hotspawn ownership exists for this fixture yet, so no contrarian claim is made |
| **Falcons vs Legacy** (if Legacy win the decider) | **Legacy** | 55.8% (own line) | Valve points 1931 vs 1843 | Falcon-heavy crowd would make Legacy the contrarian side |
| **Falcons vs BETBOOM** (if BETBOOM win the decider) | **Falcons** | 65.8% (own line) | Valve points 1843 vs 1596 | low-upside chalk; only worth a fade if the crowd is near-unanimous |

## 6. Leaderboard strategy — contrarian but not stupid (what is verifiable, and what is not)

Verified inputs:

- Hotspawn's Thunderpick pick'em leaderboard at read time: **1st leggy2000 33 points, 2nd zanderlisama 31 points**
  ([play.hotspawn.com/thp-pickems](https://play.hotspawn.com/thp-pickems), read 19:44Z). The board resets weekly
  ("Resets in 2d 04h …"); the prize for 1st is a $400 Steam voucher (`hotspawn/data/capture.json`, `week.prizes`).
- Points per match come from Hotspawn's own payload (`points` field): S-tier TWC matches are 7 points, B-tier 3,
  C-tier 2 (`hotspawn/data/board.json`).

Therefore the *only* thing that climbs the leaderboard is being right on high-point matches where the field is wrong
or split. The published rule for that is the three documented gates — underdog ≥30% by an eligible outside line,
ownership ≥10 percentage points below the favourite, and ≥10 recorded crowd picks — and **none of the three can be
evaluated for the day-4 semifinals yet, because Hotspawn has not listed them** (the newest Hotspawn read at 19:31Z
contains no semifinal fixture; `hotspawn/data/summary.json` shows 16 open fixtures, of which the only TWC row,
`1081775`, is the decider). The honest instruction for day 4 is therefore: **take the probability pick, and only
re-evaluate for a chase once the Hotspawn card and its ownership numbers exist** (the next unattended refresh picks
them up automatically — see §7). Do not force several correlated upsets; one deliberate fade is the maximum the
evidence supports.

The day-1 upset is *context, not a strategy*: 9z beating Aurora 2-0 was verified, and Aurora then beat the same
opponent 2-0 in the decider. A single upset does not make the favourite's next line wrong.

## 7. Integration requests for the board owner (`arena/4061d8f1`)

1. **Two open rows are unresolved in the 19:31Z snapshot and both are resolvable from sources already captured** —
   this is the user's "every match must have a pick" requirement:
   - `1081515` **Apogee Betclic vs Nemesis** (PGL Bucharest 2027 CQ, BO3, lock 2026-10-17 13:54Z, 3 pts).
     Captured evidence: Polymarket "Betclic Apogee Esports vs Team Nemesis (BO3) – PGL Bucharest Closed Qualifier
     Playoffs" **0.315 / 0.685**; bo3.gg lists the same fixture BO3 at 2026-10-17 14:00Z; Valve lists Nemesis #29
     (1455) and Betclic #45 (1333) → own line **Nemesis 58.0% / Betclic 42.0%**. Pick: **Nemesis**
     Sources as captured in `hotspawn/data/capture.json`: market <https://polymarket.com/event/cs2-bca-nem-2026-10-17>,
     fixture <https://bo3.gg/matches/betclic-apogee-esports-vs-team-nemesis-cs-17-10-2026>,
     event <https://liquipedia.net/counterstrike/PGL/2027/Bucharest/Qualifier>.
     Root cause of the blank: the name
     "Apogee Betclic" (Hotspawn) is not aliased to "Betclic Apogee Esports" (Polymarket) / "Betclic" (Valve), so
     every rung misses.
   - `1081527` **aimclub vs BASEMENT BOYS** (DraculaN Season 7, BO1, lock 2026-10-19 08:54Z, 3 pts).
     Captured evidence: Polymarket **0.50 / 0.50** (dead heat); bo3.gg BO1 2026-10-19 09:00Z; Valve aimclub #77
     (1113) vs BASEMENT BOYS #102 (1036) → own line **aimclub 55.1% / BASEMENT BOYS 44.9%**; HLTV lists the fixture
     as BO1 with [{aimclub #100}](https://www.hltv.org/team/6810/aimclub) vs
     [{BASEMENT BOYS #96}](https://www.hltv.org/team/13181/basement-boys) and EGamersWorld prices aimclub **1.80**
     ([EGW match page](https://egamersworld.com/counterstrike/match/V1JAWhPomg/aimclub-vs-basement-boys-TxC6-kx8ZJ),
     read 20:0xZ). Pick: **aimclub** (55.1% own line; 1.80 ⇒ 55.6% raw implied). Root cause: aimclub appears twice
     in Valve's file (#77 and #336, different rosters) so `unique()` withholds the own line, and the HLTV
     roster-disambiguation rung was never attempted because of the circuit breaker below.
2. **Fix the global HLTV circuit breaker in `hotspawn/collect.py`.** The 19:31Z capture shows every gap-research row
   *after* the first refusal marked `"not requested: HLTV refused the preceding request; circuit breaker respects the
   refusal"` (`hotspawn/data/capture.json` → `gap_research.hltv`). One rate-limited request therefore silences the
   whole HLTV rung for the run, which is the direct cause of blank rows in low-coverage tournaments. A per-row
   backoff (sleep, retry once, then continue with the next row) keeps HLTV's refusal respected without losing the
   rung for every remaining fixture. The behaviour is asserted by
   `hotspawn/tests.py::test_hltv_refusal_circuit_breaker_preserves_unattempted_status`, so that test must be updated
   in the same change.
3. **Add the day-4 rows to `hotspawn/research/twc2026.json`** (semifinals with the §2/§3/§5 values and per-row
   source links) so `hotspawn/twc.html` shows the playoff schedule even before Hotspawn lists the fixtures, and
   record the day-3 results (Aurora 2-0 9z; Group B decider pending at read).
4. **Alias entries**: "Apogee Betclic" ↔ "Betclic Apogee Esports" ↔ "Betclic" (with the Polymarket + Valve evidence
   URLs above), in the style of the existing `hotspawn/research/aliases.json` entries.
5. **Mobile executive summary**: the user's ask is one tap from the executive summary to the picks, TWC day-4,
   unresolved and flagged lists. Current `hotspawn/index.html` links the pages in body copy; the request is a
   prominent, thumb-sized jump list at the top of the page and the same on the root `index.html`.

## 8. Flagged for review (irregularities found in this research, all non-blocking)

- **IR-3A-01 — Aurora "recent roster change" premise is not supported by the record.** The rebuild was completed on
  **8 July 2026** (kyxsan from Falcons; Jimpphat and coach ash three days earlier; out: MAJ3R, soulfly, coach Fabre) —
  [HLTV news 45082](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan),
  [HLTV Aurora team page transfers](https://www.hltv.org/team/11861/aurora), [Liquipedia timeline](https://liquipedia.net/counterstrike/Aurora_Gaming).
  That is ~14 weeks before TWC, not a pre-event change, and Aurora have since reached three consecutive top-four
  finishes (HLTV news 45736). No Aurora roster move in October 2026 was found in these sources.
- **IR-3A-02 — the one genuinely fresh change in the event window was Ninjas in Pyjamas replacing Virtus.pro**
  (announced 9 October, [HLTV news 45724](https://www.hltv.org/news/45724/nip-spared-scheduling-headache-after-early-thunderpick-world-championship-exit));
  NIP then lost 0-2 and 0-2 and were eliminated. If the user's "onboarding a new roster" hypothesis is to be used,
  this is the only TWC data point for it, and it points the other way.
- **IR-3A-03 — Liquipedia lists a future/undated roster move for Betclic Apogee** ("October 17th – bench POLO"),
  i.e. an entry dated after this read, on the same page as the TWC roster timeline. Not used anywhere in this
  dossier; recorded so it can be re-checked after 17 October.
- **IR-3A-04 — the 19:31Z Hotspawn capture is flagged `complete: false`** (`hotspawn/data/capture.json`) with an
  empty `conflicts` list, while all three surfaces returned HTTP 200. The cause is not explained by the file, so the
  board publishes a partial-coverage flag on every row; this should be explained or fixed by the owner.
- **IR-3A-05 — 83 fixtures in the 19:31Z read versus 100 in the 13:23Z read** (same day, same three surfaces). The
  difference is consistent with Hotspawn retiring finished fixtures, but no Hotspawn changelog exists for it; the
  board's own "stale listings" counter (61) is the only record.

## 9. Sources used in this dossier

- Hotspawn: <https://play.hotspawn.com/lobby>, <https://play.hotspawn.com/cs2-pickems>,
  <https://play.hotspawn.com/thp-pickems> (read by the unattended refresh at 19:31:18–19:31:20Z, raw state in
  `hotspawn/data/raw/hotspawn_state_*.json.gz`); leaderboard read 19:44Z.
- HLTV: event 8932 overview/matches, matches 2399412, 2399413, 2399414, 2399415, 2399416, 2399417, news 45736,
  news 45082, team pages 11861 (Aurora), 6810 (aimclub), 13181 (BASEMENT BOYS), ranking
  <https://www.hltv.org/ranking/teams>.
- Valve (official): `ValveSoftware/counter-strike_regional_standings` commit `eec4853`, global standings 2026-10-05.
- EGamersWorld: TWC 2026 event page, CS2 match list, aimclub vs BASEMENT BOYS match page.
- Polymarket: `gamma-api` event `cs2-furia-aur1-2026-10-17`, search results for the two gap rows.
- Liquipedia: TWC 2026 overview, PGL Bucharest 2027 Closed Qualifier, DraculaN Season 7, Aurora Gaming.
- Repo files reused (not re-verified here): `hotspawn/data/{board.json,capture.json,summary.json}`.
