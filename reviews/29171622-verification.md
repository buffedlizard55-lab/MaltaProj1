# Every-match gap, research rung F, and executive-summary review — arena/29171622

Date: 17 October 2026 UTC (research window 2026-10-16T23:50Z – 2026-10-17T00:15Z).
Branch: `arena/29171622-maltaproj1`.

Scope: the maintained primary `hotspawn/` board, its research ladder, the root executive summary and its
navigation. Not a certification of the repository's dozens of historical alternative dashboards.

---

## 1. What was asked and what actually exists

| Request | What is true now | Where it lives |
|---|---|---|
| Review TWC 2026 day 1 incl. the 9z upset over Aurora and the recent Aurora roster change | Days 1–3 re-read from HLTV's event results and match pages. Aurora's "recent" change is a **July 2026** rebuild (MAJ3R out 2 Jul, Jimpphat + coach ash 3 Jul, kyxsan 8 Jul) — about three months before TWC, not a fresh emergency substitution. No onboarding penalty is quantified. | `hotspawn/research/29171622/twc_days.json`, [TWC page](../hotspawn/twc.html) |
| Review days 2–3 and use them to guide day-4 picks, favouring contrarian-but-not-stupid picks | Day 4 has **no Hotspawn listing at all** (see §2), so a graded pre-lock pick is impossible. Outside lines are published as a dated market watch instead, and all three sources for both semifinals are shown. | [twc.html#day4](../hotspawn/twc.html#day4) |
| Resolve picks for the low-tier / unbet-on matches (HLTV first, then esportsbooks / betting lines) | All 21 open Hotspawn CS2 fixtures now carry a pick. The last two (1081861, 1081863) were resolved by a new documented rung F. | [picks.html](../hotspawn/picks.html) |
| A separate unresolved-picks + limitations section, included in the executive summary | The section exists and now lists the **actual rows** from the live snapshot, not generic prose. | [root summary](../index.html#unresolved-summary), [unresolved.html](../hotspawn/unresolved.html) |
| Fix navigation so picks are easy to find and read on a phone | Picks are the first quick link on every page; every table has a mobile escape (scroll wrapper or row stacking), enforced by a test. | [index.html](../index.html) |

---

## 2. Hard constraint: Hotspawn has no TWC 2026 Malta main-event rows

Audited `hotspawn/data/raw/hotspawn_state_{lobby,cs2-pickems,thp-pickems}.json.gz` (79 687 / 79 692 / 10 510 chars)
and `hotspawn/data/all_fixtures.csv`: 83 fixtures across 19 competitions. **All eight** rows whose competition contains
"Thunderpick" are stale June-2026 *South American Series #1* qualifiers. There is no live TWC semifinal row.

Consequence: day-4 semifinals cannot be Hotspawn picks. `hotspawn/twc_watch.py` correctly returns an empty day-4 row
set and the page says so explicitly. Publishing a "pick" there would have meant inventing a Hotspawn listing, a crowd
ownership sample and a lock time — so nothing of the kind is published.

## 3. Day-4 schedule, re-verified

| Match | Start (UTC) | HLTV | Format |
|---|---|---|---|
| FURIA vs Aurora | **2026-10-17T14:00:00Z** | [2399414](https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026) | BO3 semifinal |
| Falcons vs BETBOOM | **2026-10-17T17:00:00Z** | [2399415](https://www.hltv.org/matches/2399415/falcons-vs-betboom-thunderpick-world-championship-2026) | BO3 semifinal |
| 3rd-place decider | 2026-10-18T07:30:00Z | [2399416](https://www.hltv.org/matches/2399416/) | BO3 |
| Grand final | 2026-10-18T11:00:00Z | [2399417](https://www.hltv.org/matches/2399417/) | **BO5** |

Event: [Thunderpick World Championship 2026](https://www.hltv.org/events/8932/thunderpick-world-championship-2026),
14–18 Oct 2026, $1 000 000, 8 teams, Malta.

## 4. Two corrections to a merged file from another session

`hotspawn/research/day4_twc2026.json` is owned by session `arena/ef2db3af` (merged as PR #179). It published two wrong
values that the pages render as fact. Both were corrected **in place and logged in the file itself**
(`corrections_29171622`), then mirrored into my own
`hotspawn/research/29171622/twc_days.json` under `corrections_applied_to_shared_file`. Nothing was silently overwritten
and no second contradictory source was created.

**4.1 Start times were reader-local, labelled UTC.** The file said `2026-10-17T10:00:00Z` and `13:00:00Z`. HLTV renders
kickoff in the reader's timezone, which was **UTC-4** on the fetch path. Three timestamped machine sources in the same
capture all return 14:00Z / 17:00Z:

- Pinnacle guest API, read 2026-10-16T23:52:04Z → `start_utc` 2026-10-17T14:00:00Z and 2026-10-17T17:00:00Z
- bo3.gg API, read 2026-10-16T23:52:04Z → same two values
- Polymarket gamma API, read 2026-10-16T23:52:06Z → same two values

The offset is confirmed by the VOID Autumn Cup page on the same fetch path: it shows 23:00 for a match the API records
at 03:00Z the next day.

**4.2 The Falcons price was mis-de-vigged.** `implied_a` was `0.87` for odds 1.20 / 4.00. The true de-vig is
(1/1.20) / (1/1.20 + 1/4.00) = **0.7692**; 0.87 is neither the raw 0.8333 nor the de-vigged figure. That error produced
an "implied 25% … much higher than the market's ~13%" sentence. BETBOOM is priced **20.5%–24.0%**, not 13%.

**4.3 Two sources were missing from the Falcons row.** Pinnacle (1.257069 / 3.98) and Polymarket (0.795 / 0.205) were
already in `hotspawn/data/capture.json` and had been omitted, which made a three-source price look single-source.

Day-4 lines after correction (all read 2026-10-16T23:52Z, margin removed / normalised):

| Match | Pinnacle | bo3.gg / Thunderpick | Polymarket |
|---|---|---|---|
| FURIA vs Aurora | 1.80 / 2.03 → FURIA **53.0%** | 1.85 / 1.85 → **50.0%** | 0.525 / 0.475 → **52.5%** |
| Falcons vs BETBOOM | 1.257069 / 3.98 → Falcons **76.0%** | 1.20 / 4.00 → **76.9%** | 0.795 / 0.205 → **79.5%** |

FURIA–Aurora is a coin flip on every source, so there is no favourite to fade. Falcons–BETBOOM has BETBOOM at
20.5–24.0%: a genuine long shot, and bo3.gg pricing *Falcons ≥1 map* at 1.05 says an upset must come 2-1, not as a sweep.

## 5. Research rung F — direction only, never a percentage

Two open fixtures (1081861 Lynn Vision vs Morningstar, 1081863 Chinggis Warriors vs WXM) reached rung D with no
bookmaker price, no prediction-market price, no HLTV ranking for one side and no Valve Regional Standings row for that
side. Rung E (roster-disambiguated Valve points) is impossible because the fallback needs candidates for **both** teams.

**The rule.** Publish a direction — and explicitly no win probability — when HLTV's own match page and analytics page
give a one-sided verdict: every "in favour of" line on one side, every "against" line on the other, and the published
head-to-head is concordant. Rule and six rejection checks are in
[`gap_verdicts.json`](../hotspawn/research/29171622/gap_verdicts.json).

**The gate in `model.py`** requires all of: rung D, status open, no identity conflict, an HLTV-stated format,
`verdict.one_sided`, empty `against_pick` / `in_favour_of_other`, and non-empty `in_favour_of_pick` / `against_other`.
It clears `FORMAT_UNKNOWN` and `UNRESOLVED`, and adds `DIRECTION_ONLY`, `NO_PERCENTAGE`, `RESEARCH_FALLBACK`, `NO_MARKET`.

| Fixture | Pick | HLTV's published reasons | Sources |
|---|---|---|---|
| 1081861 Lynn Vision vs Morningstar | **Lynn Vision** | Better form ranking; won 4 of the last 5; better ranked (#39). Against Morningstar: core lineup has played only 2 matches together, only 3 maps in 30 days, worse ranked (Unranked). H2H Lynn Vision 3-0, all by 2-0. | [match](https://www.hltv.org/matches/2399576/lynn-vision-vs-morningstar-macemedia-void-autumn-cup-2026) · [analytics](https://www.hltv.org/betting/analytics/2399576/lynn-vision-vs-morningstar-macemedia-void-autumn-cup-2026) |
| 1081863 Chinggis Warriors vs WXM | **Chinggis Warriors** | Better form ranking; better ranked (#61). Against WXM: fewer maps played, worse ranked (Unranked). **No published head-to-head** — this is the weaker of the two cases and the page says so. | [match](https://www.hltv.org/matches/2399578/chinggis-warriors-vs-wxm-macemedia-void-autumn-cup-2026) · [analytics](https://www.hltv.org/betting/analytics/2399578/chinggis-warriors-vs-wxm-macemedia-void-autumn-cup-2026) |

**Six sources were tried and rejected for both** (recorded on each row):

1. **Pinnacle guest API** — neither fixture appears in the captured CS2 matchup set.
2. **Polymarket gamma API** — neither fixture appears in the captured quote set.
3. **bo3.gg / Thunderpick** — 1081861 has a page with no odds pair; 1081863 has no page at all (404 at the dated slug used for the other three quarter-finals).
4. **EGamersWorld** — both have pages, but the displayed price is **1.8 / 1.8**, the placeholder EGamersWorld shows on every unpriced match. A placeholder is not a market price.
5. **HLTV betting tables** — only a Stake sweepstakes promotion; no bookmaker price for either fixture.
6. **Valve official Regional Standings** (`eec4853d7bcf0f1f7efe7f0d901234bef7e98b75`) — no row for Morningstar or WXM in the 2026-10-05 global, Europe or Asia files.

HLTV is specialist reporting, not the tournament organizer. Its verdict lines are quoted verbatim and attributed; no
percentage is derived from them.

## 6. Snapshot after the change

```
model: 21 open / 83 fixtures; picks 21
rungs   {'A':2, 'B':11, 'C':3, 'D':0, 'E':3, 'F':2}
classes {'VALUE':4,'CONTRARIAN':3,'SITUATIONAL':2,'LONG SHOT':3,'CHALK':4,
         'EVIDENCE LIMITED':1,'NO CROWD DATA':2,'DIRECTION ONLY':2}
verify: row audit 83 / 83 source fixtures; 0 errors
tests:  Ran 89 tests … OK
```

**Zero unresolved open rows.** Two rows publish a direction with blank probability columns rather than an invented number.

## 7. Rendering and navigation changes

- `hotspawn/build.py` — added `RUNG_TEXT["F"]`; `card()` prints `Pick: <name>` with a `no % published` chip and no bars
  for rung F; `unresolved_section()` gained a **"Direction-only picks (research rung F)"** table (in both full and
  compact mode) listing the pick, HLTV's own quoted reasons, the ranking evidence, why there is no percentage, and every
  rejected source; `landing.json` now carries `open_direction_only` and a `gaps[]` array; the "Limitations that apply to
  every pick" list gained a rung-F bullet.
- `index.html` (root) — the unresolved section now lists the **actual** rows from the live snapshot (`#gap-list`), each
  labelled "Direction-only — pick with no percentage" or "Unresolved — no pick", each linking into
  `hotspawn/picks.html#m<id>`. The inline renderer now counts rung F as a researched resolution.
- `hotspawn/build.py` — fixed a pre-existing cosmetic bug where a refused HLTV request rendered as
  `HTTP ; … read .` on 18 rows; it now reads `not requested: HLTV refused the preceding request; circuit breaker
  respects the refusal.`
- `hotspawn/model.py` — rung-F rows keep their direction (an unconditional `pick = None` reset was wiping it);
  `strategy()` returns `DIRECTION ONLY` instead of `None` when no probability exists; the stale "format not
  independently confirmed" clause is dropped from the published limitation once HLTV has confirmed the format.

## 8. Tests added

- `hotspawn/tests.py` → `DirectionRung` (4 tests): the verdict pack is fully sourced; every rung-F row carries a
  direction and **no** `p_a` / `p_b` / `pick_p` / `own_p_a`; the verdict is genuinely one-sided (nothing published
  against the pick); the quoted lines on the row match the pack verbatim; rung F never overrides a price or own line;
  the rendered card contains `Pick:` and `no % published`.
- `hotspawn/tests.py` → `test_every_table_escapes_horizontal_overflow_on_a_phone`: every table must have either the
  `.tablewrap` scroll container or an explicit `min-width:0` plus narrow-viewport row stacking.
- `tests/test_landing_43c32386.py`: the Node VM test that runs the **actual inline renderer** now covers rung F counting,
  the gap list contents, and the no-gaps case.

## 9. Mobile

Chromium cannot be downloaded in this sandbox, so `hotspawn/mobile_check.py` honestly reports
`browser unavailable; no layout claim made` here and makes **no** green claim. The most recent real Chromium run
(2026-10-16 23:48Z, refresh run 38982544209) passed all **27** checks at 360 / 390 / 768 px, recorded in
`hotspawn/data/mobile_check.json`. Because I could not re-run it locally, the static overflow test in §8 was added
instead of assuming; it accepts both legitimate mobile patterns.

## 10. Irregularities and limitations

- **Hotspawn carries no TWC 2026 Malta rows** (§2). Day-4 semifinal guidance is a dated outside market watch, not a pick.
- **Two direction-only rows publish no probability** (§5). They have no leaderboard leverage and no EV cost, by design.
- **HLTV 403 → collector circuit breaker**: `capture.json` records a 403 and every later `research_attempt` for
  1081861–1081864 says "not requested". Direct fetches succeed; the collector should back off per host. An HLTV
  `hltv_rank` of `null` must not be read as evidence of absence.
- **HLTV's own analytics text is internally inconsistent** for 1081863: it says "won 4 out of the last 5" while the same
  page's results strip shows 2 wins in 5. The page quotes only HLTV's verdict lines with attribution and asserts no
  percentage.
- **EGamersWorld's 1.8 / 1.8 is a placeholder**, never used as a line.
- Graded tallies are unchanged and small (day 1 3/4, day 2 2/3, graded since launch n=4 / 3 correct; 1080201 has no
  archived pick). Four results are not four archived pre-lock predictions.
- The user's "recent Aurora roster change" premise is stale (July 2026). The dated rebuild is reported instead of
  inventing a new move.
- Win probabilities are project calculations on source observations, **not** officially verified future outcomes.
  Relayed sportsbook prices stay secondary/flagged. Hotspawn crowd percentages are never a probability input.
