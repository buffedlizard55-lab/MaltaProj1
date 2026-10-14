# Executive-summary board — verification record (`arena/bdc98a9a`, 2026-10-14 UTC)

Session scope: tasks **E-01** (executive summary + mobile-first pick navigator), **E-02** (a pick for
every match, including the low-tier fixtures no featured book prices), **E-03** (recurring coverage
check against Hotspawn), **E-04** (integration: additive root link, PR, merge, Pages).

Everything below was checked against the page named next to it while writing this file. Where a value
could not be confirmed, the row stays blank on the board and is listed on `exec/flagged.html` — nothing
here is inferred.

## 1. What this session read live (links are the sources)

| Source | URL | What was read | Result |
|---|---|---|---|
| Hotspawn Play — CS2 pick'em | https://play.hotspawn.com/cs2-pickems | full fixture list, three rendered chunks | 88 CS2 fixtures listed, 28 of them open (kickoff ahead of 2026-10-14 02:35Z), tier counts B 24 / C 60 / S 4, "This week 68 matches this week" |
| Hotspawn Play — lobby | https://play.hotspawn.com/lobby | same fixtures plus other titles | same CS2 rows; other titles are out of this board's scope |
| Hotspawn match page | https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624 | kickoff display | "Oct 14, 04:00" local = **17:00 UTC** (payload `scheduled_start_time`); the served clock is UTC−4 |
| HLTV match page | https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11 | series format, teams, kickoff countdown | "Best of 3 (Online) · Swiss round 1", 14 Oct 13:00 local = 17:00 UTC, countdown consistent with the payload |
| HLTV match page — lineup block | same page | rank badges | **FORZE Reload: HLTV #75, VRS #89**; LFO 10 printed with no badge |
| HLTV team page | https://www.hltv.org/team/14084/lfo-10 | ranking status | world ranking **none** ("doesn't have a world rank at the moment"), Valve ranking none, peak −#170, win rate 33.3 % |
| HLTV World Ranking | https://www.hltv.org/ranking/teams | ranking date | "Counter-Strike World ranking on October 12th, 2026" |
| HLTV event page | https://www.hltv.org/events/9442/cct-2026-europe-series-11 | fixture in the event | FORZE Reload vs LFO 10, 14/10/26, bo3 |
| Valve Regional Standings (official Valve repository) | https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md | both teams | **FORZE Reload #84, 1100 points**; **no LFO 10 entry** (the file lists LFO 7, LFO 8 and LFO 9 as separate squads) |
| EGamersWorld match page | https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3 | odds | shows **1.80 / 1.80** with the opponent unnamed — the aggregator's cut-off placeholder, not a market |

## 2. The result for the one fixture nobody else published a pick for

`#1079624` **FORZE Reload vs LFO 10** (CCT Europe 2026 Series #11, tier B, 3 points, lock 16:54 UTC,
start 17:00 UTC) is the single fixture that `data/8944bb84/analysis.csv`, `live/data/slate.csv` and
`cs2/data/analysis.csv` all leave blank. Verified state:

* **Format:** BO3 — HLTV match page 2399301, corroborated by the HLTV event page.
* **Valve Regional Standings:** FORZE Reload rated (#84, 1100); LFO 10 absent.
* **HLTV World Ranking:** FORZE Reload ranked (#75); LFO 10 unranked (team page).
* **Market:** none. EGamersWorld serves only the 1.80/1.80 placeholder, and Pinnacle does not list the
  fixture.

Rule applied (published on `exec/method.html`): with one side ranked by official lists and the other in
neither, a symmetric rating difference does not exist, so **no numeric probability is invented**. The
pick is published as the ranked side, labelled *qualitative (ranked vs unranked)*, with the list checks
linked and the missing input flagged `NO-RATING`. After this change the board has a pick for
**28/28 open fixtures**, 27 of them carrying a number.

## 3. Irregularities observed (published on `exec/flagged.html`, none blocks publication)

* `EXEC-01` — no market exists for `#1079624`; the qualitative pick is the honest ceiling.
* `EXEC-02` — the EGamersWorld 1.80/1.80 reading is a placeholder (same pattern prior sessions flagged);
  the build rejects it by rule and flags any row it would have produced.
* `EXEC-03` — Hotspawn renders times in UTC−4 while the payload carries exact UTC epochs. This board
  prints payload UTC and the lock offset; it never converts from the rendered text.
* `EXEC-04` — Hotspawn's payload still lists 60 fixtures whose kickoff is in the past (June–July 2026,
  plus 13 October). They are published separately as *stale listing*, never as open picks.
* `EXEC-05` — two different rating scales are in use across this repository: this board applies
  `k = 0.4630` (the slope fitted on Valve's published match results by the `cs2/` board, session
  `a174d77f`, recorded in `cs2/data/calibration.json` on PR #82) while `data/8944bb84/` uses
  D = 372.12. The same fixture can therefore carry different model percentages on different boards;
  each board prints its own curve, and this one prints the market figure first whenever a quote exists.
* `EXEC-06` — the market quotes on this board are the repository's captured readings (each row prints
  the read time and the source URL). The collector added here reads fixture identity, Valve's
  standings, HLTV's ranking and HLTV's per-match pages live on every run; it deliberately does not run a
  second bookmaker crawler in parallel with the sessions that own that job, to avoid duplicated
  collection.

## 4. How each published number is verified

The build recomputes, and `tests/test_exec_bdc98a9a.py` re-checks from the published CSV:

* market rows: `p(A) = (1/odds_A) / (1/odds_A + 1/odds_B)` reproduced within 0.15 pp, and the headline is
  the market figure whenever a market exists;
* rating rows: `p(A) = 1 / (1 + 10^(−k·Δpoints/400))`, both sides summing to 100 %, with the points and
  the published line linked on the row;
* every pick equals the higher-probability side, `pick_pct` equals that probability, and fair odds are
  `100/p` within 0.02;
* every open row carries at least one external source URL; every flag carries a source URL;
* no Hotspawn crowd field is parsed, and no column of the board is derived from one;
* every relative link on the generated pages resolves, and the workflow runs the same audit across all
  143 HTML pages in the repository (2 460 static local links, 0 broken; one JS-assembled href skipped as
  not a static target).

## 5. Reproduce

```bash
python exec/collect.py                  # Hotspawn, Valve, HLTV (public pages only)
python scripts/exec_bdc98a9a_build.py   # merge with the repo's captured evidence, render exec/
python -m unittest tests.test_exec_bdc98a9a -v
```

Automation: `.github/workflows/exec-bdc98a9a.yml` — hourly (`17 * * * *`), on pushes to `exec/**`, and by
manual dispatch; commits only `exec/**` after the board tests and the repository-wide link audit pass.
