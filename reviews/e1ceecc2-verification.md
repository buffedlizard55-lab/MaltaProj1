# Line-by-line verification — session `arena/e1ceecc2` (2026-10-15, ~22:2x–23:5x UTC)

Scope: TWC 2026 day-1/day-2 review with day-3 picking guidance, a re-check that every open Hotspawn CS2
fixture carries a pick plus both probabilities plus sources, mobile/landing discovery for the new page,
and the three repository checks that were red on `main` before this session.

Every row below was read from the source named, at the read time shown. Nothing is inferred: where a value
could not be confirmed it is blank and listed under "Not verified / flagged".

## 1. Event facts (Thunderpick World Championship 2026)

| Claim published on the site | Value | Source (read UTC) |
|---|---|---|
| Organizer, venue, dates, prize pool, tier | GAM3RS_X · BLAST Arena Studios, Attard, Malta · 2026-10-14 → 2026-10-18 · USD 1,000,000 · S-Tier | https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026 (2026-10-15 22:40Z) |
| Bracket and prize share | HLTV event 8932; $500,000 player share / $500,000 club share | https://www.hltv.org/events/8932/thunderpick-world-championship-2026 (2026-10-15 22:35Z) |
| Format: two 4-team GSL groups, BO3; BO3 semis, third-place decider, BO5 grand final | as stated | https://tips.gg/article/thunderpick-wc2026-winner-odds/ (2026-10-15 22:41Z) + Liquipedia page above |

## 2. Every series of days 1–2 (8 rows, one HLTV match page each)

| Day | Series | Maps | HLTV match page | Liquipedia cross-check |
|---|---|---|---|---|
| 14 Oct, Group A opener | 9z 2-0 Aurora | Inferno 13-11, Nuke 13-1 | https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026 | group table + match block (same scores) |
| 14 Oct, Group A opener | Falcons 2-0 Ninjas in Pyjamas | Ancient 16-13, Dust II 13-6 | https://www.hltv.org/matches/2399385/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026 | same |
| 14 Oct, Group B opener | Legacy 2-0 PARIVISION | Dust II 13-11, Mirage 16-14 | https://www.hltv.org/matches/2399386/legacy-vs-parivision-thunderpick-world-championship-2026 | same |
| 14 Oct, Group B opener | FURIA 2-0 BetBoom Team | Ancient 13-10, Mirage 13-9 | https://www.hltv.org/matches/2399387/furia-vs-betboom-team-thunderpick-world-championship-2026 | same |
| 15 Oct, Group A elimination | Aurora 2-0 Ninjas in Pyjamas (NIP out) | Cache 13-9, Dust II 13-7 | https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026 | same |
| 15 Oct, Group A winners' | Falcons 2-1 9z (Falcons through) | Nuke 9-13, Mirage 13-8, Dust II 9-13 | https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026 | same |
| 15 Oct, Group B elimination | BetBoom Team 2-1 PARIVISION (PARIVISION out) | Ancient 13-10, Anubis 4-13, Mirage 7-13 | https://www.hltv.org/matches/2399410/parivision-vs-betboom-team-thunderpick-world-championship-2026 | same |
| 15 Oct, Group B winners' | FURIA 2-1 Legacy (FURIA through) | Cache 13-10, Inferno 5-13, Mirage 8-13 | https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026 | same |

Independent narrative cross-checks used for the notes column (never for numbers):
https://www.hotspawn.com/counter-strike/news/thunderpick-world-championship-2026-day-2-review (2026-10-15 22:20Z),
https://esports.gg/news/counter-strike-2/cs2-thunderpick-world-championship-2026-results/ (22:15Z),
https://pley.gg/cs2/thunderpick-world-championship-2026/ (22:16Z).

Group tables (records, rounds, diff) as published on the Liquipedia event page, read 2026-10-15 22:40Z:
Group A Falcons 2-0 (63-50), 9z 1-1 (57-46), Aurora 1-1 (38-42), NIP 0-2 (35-55);
Group B FURIA 2-0 (62-45), BetBoom 1-1 (55-50), Legacy 1-1 (55-61), PARIVISION 0-2 (49-65).

## 3. Day-3 deciders — every number, its source and its limit

**9z vs Aurora (Group A decider, 2026-10-16 14:00Z, BO3) — Hotspawn fixture 1080205.**

| Value | As published | Source (read UTC) | Used for |
|---|---|---|---|
| Polymarket price Aurora 68.5 / 9z 31.5 | yes | https://polymarket.com/event/cs2-aur1-9z-2026-10-16 (2026-10-15 21:34:15Z, board `rung B`) | headline pick (Aurora) |
| Thunderpick (esportsbook) relayed by bo3.gg Aurora 65.53 / 9z 34.47 | yes | https://thunderpick.io/match/2830808 (capture 2026-10-15 20:31:27Z, console board rung 2) | second line, flagged as relayed |
| EGamersWorld listing Aurora 1.44 / 9z 2.70 (de-vig 65.2 / 34.8) | yes | https://egamersworld.com/counterstrike/match/5X5sFiL7H/aurora-vs-9z-bH-YrllJx (2026-10-15 22:55Z) | third line, flagged aggregator-quoted |
| stavka.tv quotes Aurora 1.38 / 9z 2.70 (66/34) | yes | https://stavka.tv/matches/csgo/16-10-2026-aurora-gaming-9z (2026-10-15 22:45Z) | context only (aggregator-quoted, not used as a line) |
| Our own line Aurora 61.25 / 9z 38.75 | yes | Valve standings 2026-10-05 (Aurora #9 1716, 9z #17 1543) + `k = 0.4598` fitted on Valve's published results: https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md | divergence / leaderboard play |
| Hotspawn crowd Aurora 89% / 9z 11% | yes | https://play.hotspawn.com/lobby (2026-10-15 21:34:12Z) | ownership only — never a probability |
| Lock/start 2026-10-16 13:54Z / 14:00Z | yes | Hotspawn payload (board row 1080205) + Liquipedia "Oct 16 10:00 EDT" | countdown |
| HLTV match id 2399412 | yes | https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026 (2026-10-15 22:36Z) | link |

Pick published: **Aurora** (market side), leaderboard play **9z** (+7.25pp against our own line, 7 points at
stake, S-tier). Limits printed on the page: no Pinnacle line for this fixture; second line is relayed, third is
aggregator-quoted; all prices read 20:31–22:55Z and can move before the 13:54Z lock; the crowd share is ownership.

**Legacy vs BetBoom Team (Group B decider, 2026-10-16 17:00Z, BO3) — not listed on Hotspawn.**

| Value | As published | Source (read UTC) |
|---|---|---|
| Not in Hotspawn's CS2 payload (only 2 TWC rows: 1080205 + the played Legacy-FURIA row) | yes | https://play.hotspawn.com/lobby (21:34:12Z) and the raw payload capture in `hotspawn/data/capture.json` |
| Scheduled 2026-10-16 17:00Z | yes | https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026 (22:40Z) |
| Only outside price found: EGamersWorld 1.80 / 1.80 | rejected as a placeholder tie | https://egamersworld.com/counterstrike/match/5X5sFiL7H/betboom-team-vs-legacy-a0-2p2fTz (22:56Z) |
| Our own line Legacy 70.83 / BetBoom 29.17 | yes | Valve standings 2026-10-05 (Legacy #2 1931, BETBOOM #11 1596), same formula |
| Pick shown | **Legacy** (own line, labelled "not on Hotspawn", information only) | — |

## 4. Roster / onboarding / rest facts (each with its source)

| Fact | Source (read UTC) |
|---|---|
| Aurora: coach Fabre benched 2026-06-29; MAJ3R and soulfly out 2026-07-02; Jimpphat + coach ashhh signed 2026-07-03; kyxsan acquired from Falcons as IGL 2026-07-08; active five XANTARES, woxic, Wicadia, Jimpphat, kyxsan | https://liquipedia.net/counterstrike/Aurora_Gaming (22:30Z) |
| Jimpphat from MOUZ and coach Ashley "ash" Batty; MAJ3R, soulfly, Fabre out | https://players.com.ua/en/news/jimpphat-and-ash-join-aurora/ (03.07.2026 article; 22:30Z) |
| kyxsan completes a six-day rebuild, arrives from Falcons | https://www.techtimes.com/articles/319928/20260708/kyxsan-joins-aurora-igl-complete-six-day-counter-strike-2-rebuild.htm (22:31Z) |
| Coach ash (Aug 2026) on the new system still bedding in | https://cs2news.com/news/ash-aurora-new-system-ewc-2026 (22:31Z) |
| Virtus.pro withdrew 2026-10-09 (health/visa) and Ninjas in Pyjamas replaced them | Liquipedia note (3) under Participants (22:40Z) |
| PARIVISION benched slaxejezzz and signed HObbit on 2026-09-17 | Liquipedia note (1) (22:40Z) |
| Valve's 2026-10-05 standings still list PARIVISION with slaxejezzz | `model/input/vrs/standings_global_2026_10_05.md` (22:50Z) |
| Legacy's arT missed Katowice and was back for this event; Hotspawn: "looked good since arT returned from illness" | https://tribuna.com/amp/en/betting/blogs/thunderpick-world-championship-2026-odds-favorites-our-predi/ (22:42Z) · https://www.hotspawn.com/counter-strike/news/thunderpick-world-championship-2026-day-2-preview (22:25Z) |
| 9z unchanged: dgt, HUASOPEEK, luchov, max, meyern — 38 rated matches together since 2026-04-22 | Valve standings 2026-10-05 (21:34Z) |

## 5. What this session changed, and the check that proves it

| Change | File(s) | Evidence |
|---|---|---|
| New TWC 2026 page (day-1/2 review, groups, situations, day-3 picks) | `hotspawn/twc.html`, `hotspawn/build.py` (nav + `twc_page()` + `pair_bar()`), `hotspawn/research/twc2026.json` | `python3 hotspawn/build.py` → 7 pages; `hotspawn/tests.py` 29 tests OK, including 4 new TWC checks (8 series each with an HLTV + Liquipedia link, every day-3 limitation printed, every situation row sourced) |
| Console board no longer publishes a pick on an exact tie; test builds can no longer overwrite the published board | `scripts/228bb5bc_build.py`, `tests/test_228bb5bc.py` | `CONSOLE_NOW_UTC=2026-10-14T04:00:00Z python3 scripts/228bb5bc_build.py` → passes; `python3 -m unittest tests.test_228bb5bc` → 45 OK (was 1 error) |
| Executive coverage counts a coin flip as "no pick" | `executive/build.py`, `executive/tests.py` | `python3 executive/build.py` → 15/15 checks pass; `tests/test_landing_43c32386.py` → 4 OK (was 1 failure) |
| livelines no longer crashes on an observation outside the current slate | `livelines/build.py` | `python3 -m unittest tests.test_457629c4` → 20 OK (was 1 error) |
| Root landing: TWC 2026 in the header nav, in "Start here", and in the research grid | `index.html` | landing acceptance tests pass; link audit below |
| Every irregularity above published for review | `hotspawn/research/irregularities.json` (IR-13…IR-21), rendered on `hotspawn/flagged.html` | `hotspawn/tests.py` requires each item to carry evidence |

Repository checks after the changes:

* `python3 -m unittest discover -s tests -t .` → **408 tests, 2 failures**, both the pre-existing `valuepicks`
  board drift (IR-18), which cannot be repaired without a live collector run (no outbound network in this
  shell). Baseline before this session: 405 tests, 3 failures + 2 errors.
* `python3 scripts/audit_91e444dd.py` → **266 pages, 6,020 local links, 0 errors**.
* `python3 hotspawn/tests.py` → 29 invariants OK (crowd share never moves a probability; every open row carries
  a pick + both probabilities + https sources; internal links resolve).
* `python3 hotspawn/mobile_check.py` → "skipped" locally (playwright is not installed in this sandbox); the
  new page was added to its page list and is checked on every workflow run. The page uses only the board's
  existing responsive classes (`.tablewrap` for wide tables, `.bars`/`.bar`, `details`) and no fixed widths.

## 6. Not verified / flagged (published on the Flagged for Review page)

1. **Legacy vs BetBoom has no outside price** — only an EGamersWorld 1.80/1.80 placeholder, rejected. The pick
   is our own points-only line and is labelled as such (IR-13, IR-15).
2. **Hotspawn lists the same TWC fixture twice** (1080204 and 1081614, Legacy vs FURIA) with lock times an hour
   apart (IR-14).
3. **HLTV's "82.7% / 17.3%" figure** on the decider page is unlabelled and matches no outside line, so it is not
   used (IR-20).
4. **Pre-event outright prices disagree between sources** (Aurora 4.30 / 6.30 / 8.00); context only (IR-21).
5. **`valuepicks/` two failing invariants** (IR-18): needs its live four-hourly refresh; not the primary route.
6. **Aurora's rebuild is not "recent"** in the sense the brief implies: 2026-07-03/07-08, i.e. 3.3 months and 17
   Valve-rated matches before this decider. It is published as context with those dates rather than as a fresh
   disruption, and it is the reason 9z (not Aurora) is the leaderboard play.
7. No Pinnacle line was found for either decider at read time; the featured rung (A) is therefore not used for
   either fixture, and both are resolved through the research ladder and printed as such.

Read times on this page are UTC. Where a source shows a local zone (Liquipedia EDT/CEST, EGamersWorld local),
the UTC conversion is stated next to the value that came from it.
