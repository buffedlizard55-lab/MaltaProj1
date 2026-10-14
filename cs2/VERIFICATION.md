# Verification — how every number on `cs2/` was checked

This file is the human-readable half of the record. The machine-readable half, which is what
`cs2/verification.html` renders, is `cs2/data/verification.json` (16 entries as of
2026-10-14). Both are written by the session that did the work (`arena/a174d77f`), never by the
pipeline, so a check that failed to hold is recorded as a refusal instead of quietly disappearing.

## What the board promises, and what proves it

| Promise | Proof, repeatable by anyone |
| --- | --- |
| Every CS2 fixture on the Hotspawn board is covered | The four public pick'em pages are parsed from `<script id="ng-state">` (TransferState), which holds the fixture list independently of how many cards the page paints. Our count (89 CS2 rows) equals the site's own filter counters on the same page (`All tiers (89)`, `All teams (89)`, and 4+25+60 tier chips). The one row that appears only on the lobby page (1079546, Zomblers v Overtake Sector, started 01:00Z) is identified and explained, not hidden. |
| Probabilities come from betting lines, never from Hotspawn's crowd | `cs2/tests.py::test_no_crowd_percentages_are_published` fails the build if any published column lands within 0.05 pp of the crowd figure for the same side. Crowd fields are kept only in `capture.json` under `*_audit_only` names. |
| No number was typed by a person | The collector is the only writer of `analysis.csv`. Prices come from Pinnacle's public guest response — the payload Pinnacle's own CS2 page loads — and are archived as bytes. `cs2/tests.py::test_published_prices_exist_in_the_archived_bytes` re-derives every published price pair from those archived bytes and refuses a pair that is not in them. |
| Anything unverifiable is blank and flagged | Missing rating → `A-NO-RATING`; no external price → `A-NO-LINE`; no sourced series length → `A-NO-FORMAT`; ambiguous pairing → `A-AMBIG-PAIR`; kickoff disagreement → `A-KICKOFF-GAP`; a book page refusing us → `A-REFUSED` with the status. Every flag code is explained on `flagged.html` with the fixture list. |
| Each row can be traced | Cards link the board page (or say plainly that the operator served no per-match URL and name the payload row), the priced source with its capture minute, Valve's standings line with a `#L<n>` anchor, and the flag anchors. |

## The arithmetic, shown once, in full

Fixture 1080177, Falcons v Ninjas in Pyjamas, Thunderpick World Championship 2026, Bo3, kickoff
2026-10-14T11:00:00Z (lock 10:54:00Z).

1. Archived payload for matchup `1638111675`, whole-match market, `type == "moneyline"`,
   `period == 0`, `status == "open"`: home `-370`, away `+285`.
2. American → decimal: `-370 → 1 + 100/370 = 1.27027`; `+285 → 1 + 285/100 = 3.85000`.
3. Implied: `1/1.27027 = 78.723 %`, `1/3.85000 = 25.974 %`; sum `104.697 %` → overround `4.70 %`.
4. Multiplicative de-vig: `78.723/104.697 = 75.2 %`, `25.974/104.697 = 24.8 %` → published.
5. Our own line for the same fixture: Valve's global snapshot 2026-10-05 gives Falcons 1843
   (line 11) and NiP 1534 (line 23). With our re-fitted slope `k = 0.463`:
   `1 / (1 + 10^(-0.463 × (1843 − 1534) / 400)) = 69.5 %`.
6. Both point at Falcons, so the pick is Falcons at the priced 75.2 %; the 5.7 pp gap between the
   book and our line is published rather than averaged away.

Repeat step 1–4 offline without a network:

```python
import sys, json, gzip; sys.path.insert(0, "cs2")
import common, collect
# monkeypatch get_json to replay cs2/data/raw/pinnacle_*.json.gz, then call collect.collect_pinnacle()
```

`cs2/tests.py` does the equivalent automatically on every run.

## Where the sources ended and the honest blanks began

At 02:07Z Pinnacle's guest endpoint listed 14 esports leagues, 4 of them CS2, 10 priced CS2
matchups in total, while the board offered 28 open CS2 fixtures. So 21 fixtures have no external
line to be had from the one book feed the runner can reach, and they carry our own line plus
`A-NO-LINE`. Other aggregators were probed and recorded, not silently dropped: EGamersWorld 403
(real Chromium render included — the challenge persisted), HLTV's dated ranking 403, 1xBet HTTP
203 geo-block page, Bovada 404, MarathonBet 403, Betexplorer 404, FreeTips 404, VPrognoze no
response, Bwin 403. Two hosts did answer — bo3.gg (13 kB) and OddsDigger (255 kB) — and until a
parser exists for them they contribute nothing but an archived snapshot and a shape report.

## Identity checks that changed coverage

Four renames, each with a link, a UTC moment and the reason; without them four fixtures would have
published nothing:

* `PVISION → PARIVISION` and `BB Team → BetBoom` (Pinnacle writes the short form; HLTV's event 8932
  bracket for the Thunderpick World Championship puts those names in the same group as the board).
* `WROTBERRY → WBT` and `RoundsGG → ROUNDS` (the organiser's own match pages: HLTV 2399418 lists
  "WBT vs. EAC, Elisa BreakOut Series 2, Group A, Best of 1 (LAN), 04:00 15 Oct" rendered in UTC−4,
  i.e. 08:00Z, which is the minute the board's `WROTBERRY v EAC` row carries; HLTV 2399427 does the
  same for Phantom v ROUNDS at 14:00Z on 16 Oct). Renames are used only to look up an official
  rating; the board still prints the name Hotspawn publishes, and `A-ALIAS` says so.

`LFO 10` is *not* aliased: Valve's snapshot lists LFO 7, LFO 8 and LFO 9, and nothing we could reach
says which of those (if any) is the squad in this CCT bracket, so that one fixture publishes no pick.

## Our own line, and why the curve is not Valve's

Valve's README says the raw expected-score curve is shallower than they would like. We re-fit the
slope by maximum likelihood on 14,188 match results taken from the same repository between monthly
snapshots (a match is usable when it appears in exactly two teams' tables, one W and one L, and each
side's roster overlaps a previous-snapshot row by ≥3 players — Valve's own rule), and adopt it only
because it wins out of sample: log loss 0.6915 → 0.6509, Brier 0.2410 → 0.2297. Published `k` is
0.463; the neighbouring O-01 pipeline in this repository independently lands on 0.4568. The fit's
unit is a match result, which is the unit the board asks for, so no map-to-series transform is
layered on top — the series length is published where a source states it and blank where none does.

## Cross-board comparison (computed, not asserted)

`cs2/data/board_comparison_open_slate.json` (regenerated by hand during this session) matches our
open rows against `open-slate/index.html`, the board arena/08031d30 merged into `main`, fixture id by
fixture id: 24 of 27 comparable picks agree, 3 differ, 1 of ours carries no pick. Every one of the 3
is a fixture where they hold an EGamersWorld price we cannot reach and we hold only our own line, and
all three are near coin-flips (50.9 %, 60.9 %, 52.3 %). They also assume "best-of-3" for rows no
source states a format for; we leave those blank. The comparison table, including the disagreements,
is rendered on `cs2/verification.html`.

## Neighbouring pipeline, diagnosed without touching it

`model/` (owned by `arena/91eff436`) has a scheduled run that fails its own test step, and CI logs
are not readable from the sandbox. Our workflow therefore reproduces their pipeline in a throwaway
copy under `$RUNNER_TEMP` and commits only the log (`cs2/data/model_diag.log`). Result: 13 of 14
tests pass on a fresh fetch; the failure is `test_model.py:136`,
`test_every_published_value_has_official_source`, asserting
`r["hotspawn_url"].startswith(OFFICIAL)` on a row whose value is `None` — a fixture for which the
operator serves no per-match URL. Their fix is theirs to make (fall back to the board URL and label
it, which is what we do); we have not edited their files.
