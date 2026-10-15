# TWC 2026 day-2 verification and day-3 audit

**Review time:** 2026-10-15 22:30 UTC  
**Hotspawn evidence snapshot:** 2026-10-15 21:34:12 UTC (`hotspawn/data/capture.json`; 88 fixtures, 22 open; all three CS2 pages returned HTTP 200).  
**Scope note:** A later coordination check found an active TWC implementation PR working on the shared renderer, tests, flagged entries, and TWC page. To avoid conflicting edits, this audit adds the non-overlapping day-2 source ledger, `results.json`, and historical-result fallback in `model.py`; it does not edit the shared TWC renderer, `tests.py`, or that branch's generated TWC page. The sourced findings below are intended for integration.

## Executive conclusion

- Day 2 had four verified series. Only three pre-lock picks are present in `hotspawn/data/pick_history.json`; those went **2/3** for the base picks and **2/3** for the leaderboard plan. Aurora–Ninjas in Pyjamas (Hotspawn ID `1080201`) is the missing archive entry: it was locked with no pick or price in `valuepicks/data/coverage.csv`. Its result is recorded, but it is not graded.
- The day-3 Hotspawn-listed Group A decider is **Aurora over 9z** as the default pick: the saved Polymarket read was 68.5%/31.5%, while the independent Valve-points line was 61.25%/38.75%. Hotspawn’s 89%/11% shares are ownership only. The existing strategy class permits 9z as a **situational chase play**, not as the most-likely winner.
- HLTV lists the Group B decider BETBOOM–Legacy, but it is absent from the latest Hotspawn capture. No Hotspawn ID, pick, or probability should be fabricated. Recheck after a later capture.
- The 21:34 Hotspawn snapshot also contains a second Legacy–FURIA record (`1081614`) one hour after the real match row (`1080204`), with zero ownership and only on the tournament-specific page. Treat it as a possible duplicate/placeholder; grade only the frozen `1080204` pick.

## Day-2 result and frozen-pick ledger

Results below are checked against the official HLTV match pages and, where available, the associated HLTV recap. The Hotspawn pick and leaderboard plan are taken only from the frozen pre-lock record; no post-lock line is substituted.

| Hotspawn ID / match | Frozen market pick | Frozen leaderboard play | Verified result | Grade: pick / plan |
|---|---|---|---|---|
| `1080201` Aurora–Ninjas in Pyjamas — [HLTV match](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026), [HLTV report](https://www.hltv.org/news/45724/nip-spared-scheduling-headache-after-early-thunderpick-world-championship-exit) | **No archived pick or probability**; locked 08:24Z. Coverage CSV is blank. | Not recorded | Aurora 2–0 (Cache 13–9, Dust2 13–7) | **Not graded** |
| `1080202` 9z–Falcons — [HLTV match](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026), [HLTV report](https://www.hltv.org/news/45728/falcons-secure-playoff-berth-at-twc-2026) | Falcons, 75.63% in frozen history (source label: Pinnacle) | Falcons (LONG SHOT) | Falcons 2–1 (Nuke 9–13, Mirage 13–8, Dust2 9–13) | **Correct / correct** |
| `1080203` PARIVISION–BetBoom — [HLTV match](https://www.hltv.org/matches/2399410/parivision-vs-betboom-thunderpick-world-championship-2026), [HLTV report](https://www.hltv.org/news/45729/betboom-eliminate-parivision-from-twc) | PARIVISION, 53.42% in frozen history (labelled Pinnacle) | BetBoom (CONTRARIAN) | BetBoom 2–1 (Ancient 13–10 PARIVISION, Anubis 4–13, Mirage 7–13) | **Miss / correct** |
| `1080204` Legacy–FURIA — [HLTV match](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026), [HLTV report](https://www.hltv.org/news/45730/furia-make-twc-playoffs-over-legacy) | FURIA, 57.58% in frozen history (labelled Pinnacle) | Legacy (CONTRARIAN) | FURIA 2–1 (Cache 13–10 Legacy, Inferno 5–13, Mirage 8–13) | **Correct / miss** |

### Market-provenance limitation

The frozen selection and grade are clear, but the historical quote evidence is uneven. The Hotspawn history stores its source label and probability, not the underlying odds or quote URL. For `1080202`, a separate board captures a direct Pinnacle line that is consistent to rounding. For `1080203`, the separate valuepicks archive instead identifies a relayed BetBoom-book quote at 1.85/1.95 (51.3%/48.7%), which is **not** the same quote as Hotspawn’s 53.42% “Pinnacle” record. For `1080204`, valuepicks has a nearby 57.4% primary-market estimate but does not name the operator. Keep these source tiers distinct; grade the frozen side, not an assumed market line. See [valuepicks coverage](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/valuepicks/data/coverage.csv), [source fact F-23](https://cyber.sports.ru/betting/1117401785-betboom-sklonyaetsya-k-pobede-parivision-nad-betboom-team-na-thunderpi.html), and the complete structured notes in [`day2_twc2026.json`](../hotspawn/research/day2_twc2026.json).

## Day-3 Group A: Aurora vs 9z

**Fixture:** Hotspawn `1080205`, BO3 Group A decider; kickoff 14:00 UTC, lock 13:54 UTC in the saved Hotspawn payload. [Hotspawn match](https://www.hotspawn.com/matches/aurora-vs-9z-thunderpick-world-championship-2026-1080205) · [HLTV match](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) · [HLTV event](https://www.hltv.org/events/8932/thunderpick-world-championship-2026).

| Evidence at the saved read | Aurora | 9z | Interpretation |
|---|---:|---:|---|
| Polymarket, 2026-10-15 21:34:15Z | 68.5% | 31.5% | Published market probability; the pick is Aurora. [Market](https://polymarket.com/event/cs2-aur1-9z-2026-10-16) |
| Own line, Valve standings dated 2026-10-05 | 61.25% | 38.75% | Independent rating line, not a sportsbook quote. Ratings: 1716 vs 1543; fitted slope k=0.4598. [Valve standings](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| Hotspawn pick share | 89% | 11% | Ownership only; never an input to either win probability. |

**Call:** Keep **Aurora** as the default / most-likely winner. The model’s 9z SITUATIONAL label means a low-ownership, high-variance choice for a player deliberately chasing; the combined underdog estimate is 35.12%, not a majority chance. The stored EV cost of taking 9z rather than Aurora is 2.59 points in this seven-point match.

The day-1 upset is real evidence that 9z can win this matchup: [9z beat Aurora 2–0](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026), Inferno 13–11 and Nuke 13–1. Day 2 was mixed rather than a reason to flip the probabilities: [Aurora beat NiP 2–0](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026), while [9z lost 1–2 to Falcons](https://www.hltv.org/matches/2399409/9z-vs-falcons-thunderpick-world-championship-2026) but took Mirage 13–8 and lost the other two maps 9–13. These few series are context, not a new probability model.

Aurora’s summer roster change is about three months old by this decider: Jimpphat joined 3 July and kyxsan joined 8 July as IGL ([HLTV roster timeline](https://www.hltv.org/news/44998/rostermania-tracker-summer-2026)). The HLTV team page’s displayed map/tenure counts changed between reads, so the report avoids treating one exact map count as stable. Aurora’s third place at ESL Pro League S24 ([HLTV](https://www.hltv.org/news/45698/aurora-claim-third-at-epl-with-spirit-sweep)) and its day-2 2–0 over NiP temper the roster-change concern. Keep the existing factor **moderate and only a leaderboard tiebreaker**; do not override the market or own-line percentages with it.

### Additional market checks and limitations

- The snapshot’s joined primary probability was Polymarket; no Pinnacle quote was joined to this fixture in that capture.
- [EGamersWorld](https://egamersworld.com/counterstrike/match/5X5sFiL7H/aurora-vs-9z-bH-YrllJx) displayed 1.44/2.70 but did not name the bookmaker.
- [StavkaTV](https://stavka.tv/matches/csgo/16-10-2026-aurora-gaming-9z) displayed Aurora 1.46 at Winline and 9z 2.85 at Betcity; these are different books. Its prose also quoted 1.38/2.70 without identifying one operator. Neither pair can be responsibly treated as a same-book two-way market and de-vigged. Both are excluded from the published probability.

## Day-3 Group B coverage gap

[HLTV match 2399413](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026) identifies BETBOOM–Legacy as the Group B decider on 16 Oct. It is not in the saved Hotspawn capture. HLTV’s rendered `13:00` has no dependable timezone in this read, while [Liquipedia](https://liquipedia.net/counterstrike/Thunderpick/World_Championship/2026) lists 19:00 CEST; no exact UTC start is published here. **No Hotspawn pick, fixture ID, or win percentage is assigned.** Recheck the next scheduled capture; if Hotspawn adds the match, use that row’s lock and run the normal source ladder.

## Additional capture irregularity

The same snapshot has `1080204` Legacy–FURIA at 16:00Z on all three Hotspawn pages, with 33 total picks, and `1081614` at 17:00Z only on `/thp-pickems`, with 0/0 ownership. Both share the tournament ID and team IDs, but HLTV has one day-2 series. Retain both in the raw inventory for audit; only the frozen `1080204` pick is graded. See [Hotspawn tournament page](https://play.hotspawn.com/thp-pickems), [HLTV result](https://www.hltv.org/matches/2399411/legacy-vs-furia-thunderpick-world-championship-2026), and the `capture_irregularities` entry in [`day2_twc2026.json`](../hotspawn/research/day2_twc2026.json).

## Files changed by this audit

- `hotspawn/research/day2_twc2026.json` — sourced day-2 ledger, frozen-pick audit, day-3 evidence, odds limitations, and duplicate-row evidence.
- `hotspawn/research/results.json` — four official day-2 outcomes keyed by Hotspawn fixture ID.
- `hotspawn/model.py` — historical-result fallback for frozen picks missing from the live fixture feed; day-2 aggregate counts.
- Generated `hotspawn/data/board.json`, `summary.json`, `all_fixtures.csv`, `landing.json`, and strategy/index pages — rebuilt from the saved capture.
- `reviews/71c4e4ab-verification.md` — this line-by-line audit.

`hotspawn/tests.py` and the shared TWC page renderer are not changed in this branch while that overlapping implementation is active. The audit preserves the Aurora–NiP no-pick gap and the BetBoom–Legacy Hotspawn coverage gap rather than filling either with a guessed value. The current model run records only the three archived day-2 picks as graded; the result for 1080201 is stored but cannot create a pick.
