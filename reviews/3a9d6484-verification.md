# Independent verification — published Hotspawn CS2 board (PR #177 snapshot)

- **Session**: `arena/3a9d6484` · **Branch**: `arena/3a9d6484-maltaproj1`
- **Verified revision**: `main` = `098c49ceec4467389f4801dbeba870f7ac13596c` (post-merge of
  [PR #177](https://github.com/buffedlizard55-lab/MaltaProj1/pull/177), merged 2026-10-16T19:46:10Z)
- **Verification window**: 2026-10-16 19:44–20:15 UTC (every external value below re-read live in this window)
- **Scope**: second-verifier pass over the **published** board and its rendered pages. This session does **not**
  edit `hotspawn/**` (owner `arena/4061d8f1`, published) and does **not** open a competing integration PR.
  Method note: the sandbox shell cannot reach Hotspawn/HLTV/bo3.gg (network allowlist), so every live read below was
  made with the agent web-fetch tool; in-sandbox checks are limited to repository data and GitHub API reads.

**Verdict: PASS with 7 logged defects.** The published board is structurally complete (16/16 open rows carry a
valid pick, two-sided probabilities summing to 1.000000, and a live source list — every row includes an HLTV link),
its two formerly-blank relayed rows reproduce **exactly** from the quotes I read independently, and its day-1…day-3
narrative matches HLTV. The defects below are reporting/traceability and one main-side CI breakage; none of them is a
fabricated or unsourced value.

---

## 1. What was verified, and against what

| # | Check | Result | Evidence (source) |
|---|-------|--------|-------------------|
| 1 | Snapshot claims: 83 fixtures / 16 open / 16 picks / 0 unresolved | matches published data | [summary.json @098c49c](https://github.com/buffedlizard55-lab/MaltaProj1/blob/098c49ceec4467389f4801dbeba870f7ac13596c/hotspawn/data/summary.json), [live exec summary](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/index.html) |
| 2 | Structural invariants on all 16 open rows (pick validity, probability sum, source link, kickoff/lock) | 0 errors | [board.json @098c49c](https://github.com/buffedlizard55-lab/MaltaProj1/blob/098c49ceec4467389f4801dbeba870f7ac13596c/hotspawn/data/board.json) |
| 3 | Numeric reproduction of relayed quotes vs my own live reads | 4/4 reproduced exactly | §3 below |
| 4 | Day-1…day-3 result text vs HLTV | consistent | [HLTV results, event 8932](https://www.hltv.org/results?event=8932), [news 45736](https://www.hltv.org/news/45736/aurora-beat-9z-to-secure-third-consecutive-top-four-appearance), [news 45729](https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc), [news 45730](https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy) |
| 5 | Day-4 TWC main-event rows kept blank (no invented pick/probability) | correctly disclosed | [twc.html @098c49c](https://github.com/buffedlizard55-lab/MaltaProj1/blob/098c49ceec4467389f4801dbeba870f7ac13596c/hotspawn/twc.html), [live twc page](https://buffedlizard55-lab.github.io/MaltaProj1/hotspawn/twc.html) |
| 6 | Live site deploy after merge | served 19:41Z snapshot, all nav targets resolve | [pages run 38957523254 → success](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38957523254) |
| 7 | Open rows' source hosts | hltv.org in 16/16; 7 rows carry a relayed-book quote; 1 row behind an affiliate redirect (D4) | board.json source lists |

---

## 2. Line-by-line audit of the 16 published open rows

`p` = published pick probability; sum = `p_a + p_b` (machine-checked, 6 dp); src = count of http source links.

| Match ID | Fixture (A vs B) | Rung | Pick | p (pick) | sum | src | Locks (UTC) | HLTV source |
|---|---|---|---|---|---|---|---|---|
| 1079170 | BET-M vs Just Players | B | BET-M | 0.6699 | 1.000000 | 6 | 2026-10-17 07:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081510 | Eternal Fire vs Nuclear TigeRES | B | Eternal Fire | 0.5000 | 1.000000 | 6 | 2026-10-17 07:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1079171 | GenOne vs Butterfly | C | GenOne | 0.5677 | 1.000000 | 5 | 2026-10-17 10:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081513 | Bebop vs Donstu | E | Donstu | 0.5198 | 1.000000 | 9 | 2026-10-17 10:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081515 | Apogee Betclic vs Nemesis | B | Nemesis | 0.6699 | 1.000000 | 6 | 2026-10-17 13:54 | [bo3.gg](https://bo3.gg/matches/betclic-apogee-esports-vs-team-nemesis-cs-17-10-2026) |
| 1079173 | BakS vs Fire Flux | B | BakS | 0.7000 | 1.000000 | 6 | 2026-10-17 16:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081126 | Banda chuya vs Enjoy | E | Enjoy | 0.5462 | 1.000000 | 9 | 2026-10-18 07:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081521 | ex-6666 vs Privateer | E | ex-6666 | 0.6971 | 1.000000 | 9 | 2026-10-18 13:39 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081522 | antidaun vs Phantom Academy | E | Phantom Academy | 0.5599 | 1.000000 | 10 | 2026-10-18 13:39 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081526 | Infinite vs Insiders | B | Infinite | 0.6900 | 1.000000 | 5 | 2026-10-19 08:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081527 | aimclub vs BASEMENT BOYS | B | BASEMENT BOYS | 0.5469 | 1.000000 | 6 | 2026-10-19 08:54 | [bo3.gg](https://bo3.gg/matches/aimclub-vs-basement-boys-19-10-2026) |
| 1081528 | BC.Game vs Drama | B | BC.Game | 0.7500 | 1.000000 | 5 | 2026-10-19 08:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081529 | Nexus vs WROTBERRY | B | WROTBERRY | 0.5376 | 1.000000 | 6 | 2026-10-19 08:54 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081530 | Iberian Soul vs HyperSpirit | B | Iberian Soul | 0.6585 | 1.000000 | 6 | 2026-10-19 10:39 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081531 | Sashi vs mouz NXT | B | Sashi | 0.6281 | 1.000000 | 6 | 2026-10-19 10:39 | [HLTV](https://www.hltv.org/results?event=8932) |
| 1081532 | ASTRAL vs Leo | B | Leo | 0.5050 | 1.000000 | 5 | 2026-10-19 10:39 | [HLTV](https://www.hltv.org/results?event=8932) |

Notes: all 16 picks are one of the two listed teams; all probabilities are two-sided and margin-normalised (D4/D5
below cover the two traceability caveats). Flag distribution: `RELAYED_BOOK` 7 rows, research-ladder
(`MODEL_ONLY`/`NO_MARKET`/`RESEARCH_FALLBACK`) 4 rows, `COIN_FLIP` 2 rows, `ALIAS` 2, `MODEL_MARKET_SPLIT` 1,
`BOOKMAKER_UNVERIFIED`+`ROSTER_UNVERIFIED` 1 (row 1081527).

---

## 3. Numeric reproduction of relayed quotes (independent arithmetic)

The board's rule is: decimal odds → implied probabilities → remove the bookmaker margin → keep the two-sided split.
I re-read the underlying quotes myself and re-ran the arithmetic:

| Row / market | Published value | Quote I re-read independently | Arithmetic result | Verdict |
|---|---|---|---|---|
| 1081515 Apogee Betclic–Nemesis (Bo3, 17 Oct) | Apogee 0.3301 / Nemesis 0.6699 | bo3.gg 2.80 / 1.38 ([match page](https://bo3.gg/matches/betclic-apogee-esports-vs-team-nemesis-cs-17-10-2026)) | overround 8.18%; margin-removed **0.3301 / 0.6699** | reproduced exactly |
| 1081527 aimclub–BASEMENT BOYS (Bo1, 19 Oct) | aimclub 0.4531 / BASEMENT BOYS 0.5469 | bo3.gg 2.04 / 1.69 ([match page](https://bo3.gg/matches/aimclub-vs-basement-boys-19-10-2026)) | overround 8.19%; margin-removed **0.4531 / 0.5469** | reproduced exactly |
| TWC SF1 FURIA–Aurora — external market watch | FURIA 50.0% / Aurora 50.0% | EGW 1.85 / 1.85 ([event page](https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H)) | overround 8.11%; margin-removed **0.50 / 0.50** | reproduced |
| TWC SF1 FURIA–Aurora — Polymarket row | FURIA 52.0% / Aurora 48.0% | match-winner market 0.52 / 0.48, `updatedAt` 19:44:51Z ([gamma-api](https://gamma-api.polymarket.com/events?slug=cs2-furia-aur1-2026-10-17)) | two-sided, sums to 1.00 | reproduced |

Extra finding on the Polymarket source: the *per-map* markets on the same event are **not** usable as evidence —
the Map 2 market shows `bestBid 0.15 / bestAsk 0.78` (spread 0.63, liquidity ≈ 1.3k) and a 0.465/0.535 print that is
noise at that spread. Only the match-winner market (liquidity ≈ 10k) supports the published 52/48. Recommendation:
never cite the map markets, and if a map market is ever quoted, flag it as thin.

---

## 4. Result / narrative verification (day 1 – day 3)

| Published narrative | My independent re-read | Verdict |
|---|---|---|
| Day 1: four series all 2-0; favourites 3/4; upset 9z 2-0 Aurora | HLTV day-1 rows incl. [9z–Aurora](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) | consistent |
| Day 2: Aurora 2-0 NIP · Falcons 2-1 9z · BETBOOM 2-1 PARIVISION · FURIA 2-1 Legacy | [2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026), [news 45729](https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc), [news 45730](https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy) | consistent |
| Day 3: Aurora 2-0 9z — Cache 13-11, Inferno 13-4; veto changed vs day 1 | [2399412](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026), [news 45736](https://www.hltv.org/news/45736/aurora-beat-9z-to-secure-third-consecutive-top-four-appearance) | consistent |
| Day 3 decider BETBOOM–Legacy left ungraded while live | page still shows LIVE with Mirage unplayed at my re-read (§5) | correct to withhold a grade |
| Day-4 semis not published as picks (no Hotspawn listing in capture) | disclosed on exec summary and TWC page as a listing limitation | correct under the no-inference rule |

---

## 5. Live / unresolved state at close of verification (~20:05Z)

- `2399413` BETBOOM vs Legacy (group-B decider) was **still LIVE 1-1** at my re-read — Nuke 16-13 BETBOOM,
  Dust2 11-13 Legacy, Mirage in progress ([HLTV match page](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026)).
  Therefore: do **not** grade row `1081775`, and do **not** finalise the SF2 pairing
  ([2399415](https://www.hltv.org/matches/2399415/falcons-vs-betboom-legacy-winner-thunderpick-world-championship-2026)).
- Day-4 schedule as read: SF1 [2399414](https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026)
  17 Oct 14:00Z; the 3rd-place match and grand final (BO5) are 18 Oct and remain unpairable.
- The board's own limitation disclosure — "no open TWC main-event fixture dated 17 October in this capture" — is
  accurate: the only TWC row in the capture was the decider, which locks/has locked, so there is no open TWC row to
  carry an SF pick. The external market watch on the TWC page is correctly labelled "not a Hotspawn pick".

---

## 6. Defects logged (report-only — this session does not edit the owner's paths)

| ID | Defect | Evidence | Impact |
|---|---|---|---|
| D1 | Published workflow's `push.branches` omits `arena/3a9d6484-maltaproj1`, so pushes from this session's branch cannot trigger the collector | [`.github/workflows/hotspawn-22be6967.yml` line 18 @098c49c](https://github.com/buffedlizard55-lab/MaltaProj1/blob/098c49ceec4467389f4801dbeba870f7ac13596c/.github/workflows/hotspawn-22be6967.yml#L18) | cosmetic for publication (main's own cron `29 */4 * * *` refreshes the board); retained as a merge-resolution note |
| D2 | "Live picks board" (`livelines-457629c4.yml`) is failing on `main` — job `board`, step 5 `Invariants` — 4 times today: 16:55:28Z, 16:55:57Z, 19:43:24Z, [19:46:14Z run 38957352383](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38957352383); last success 13:33:24Z | gh run list/history for the workflow | a `main` surface (not this session's namespace) has been stale for hours; needs an owner |
| D3 | `capture.json` traceability: 36 relayed esportsbook quotes, but none join to rows `1081515`/`1081527` by `match_id` | [capture.json @098c49c](https://github.com/buffedlizard55-lab/MaltaProj1/blob/098c49ceec4467389f4801dbeba870f7ac13596c/hotspawn/data/capture.json) | the two rows' quotes are provable only from the provider URL (as in §3), not from the stored capture; a `provider_id`/URL join key would close it |
| D4 | Row `1081527` cites its book quote behind an **affiliate redirect** (`refpa04636.pro/L?...utm_source=bo3_odds_ww...`) rather than an operator domain; the payload path does identify the bo3.gg line table (`.../379139476-aimclub-BASEMENT-BOYS`) | board.json source list for 1081527 | cannot be read as an official operator page; recommend canonical link or an explicit `AFFILIATE_REDIRECT` flag on the row |
| D5 | The collector's **global** HLTV backoff breaker means one 403 suppresses every later HLTV lookup in the same run — `gap_research` shows 15/16 targets "not requested" | owner `collect.py`; patch offered at [`reviews/3a9d6484-hltv-backoff-request.patch`](https://github.com/buffedlizard55-lab/MaltaProj1/blob/arena/3a9d6484-maltaproj1/reviews/3a9d6484-hltv-backoff-request.patch) | coverage of the gap-research ladder is thinner than the run reports; the patch makes retries per-row with a bounded backoff |
| D6 | bo3.gg's post-match team-form strip renders a **map** result as "1-0"/"0-1"; reading it as a series score is a misread trap | my re-read of both bo3.gg match pages (the aimclub row showed 0 games at read, so no published value is affected) | documentation-only; add to the relay notes so future sessions do not import a false series score |
| D7 | Published `COORDINATION.md` (5,344 lines @098c49c) contains **zero** references to `arena/3a9d6484`; this branch's copy (5,391 lines) holds the session's claim/withdrawal block | `git show origin/main:COORDINATION.md` vs branch | the owner's integration merge did not carry concurrent sessions' claim rows; recommend the next integrator preserves parallel blocks when merging |

Also carried forward (unchanged, all disclosed in the published `flagged.html`): IR-01/IR-02 unverified clock
attribution, IR-03 open roster-name discrepancy (Valve vs HLTV), IR-04 open stand-in question on Voca–Phantom.

---

## 7. Deliberately left blank (cannot be established without inference)

- Final score/winner of `2399413` and therefore the grade of row `1081775` and the SF2 pairing.
- 3rd-place and grand-final participants (18 Oct) — no fixtures exist to price yet.
- Whether the Hotspawn lobby itself displays the 2.80/1.38 and 2.04/1.69 quotes: I verified the **provider**
  quotes and the board's arithmetic, not a Hotspawn screen read of those two rows.
- The owner's `research/day4_twc2026.json` extras (e.g. a "Thunderpick direct -118/-118" line) — attributed to that
  session, not independently reproduced here; not used in any of my figures.
- Any roster-change/rest adjustment for Aurora's day-4 form: no measured basis; the board correctly applies none.

## 8. Recommendation

Publish status can stand as-is: no fabricated values, no unsourced rows, and both relayed rows reproduce exactly.
The three follow-ups worth an owner: **D2** (main-side live-lines invariants), **D3/D4** (quote traceability join
key + affiliate-redirect flag), and **D5** (per-row HLTV retry patch, already authored). Nothing here blocks the
published board, and nothing here justifies a competing PR.
