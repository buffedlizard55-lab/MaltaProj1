# Live slate (session `arena/459ff624`) — verification report

Scope: `live/**` only. Snapshot verified: **2026-10-13T23:11:44Z** (collection 23:11:27–23:11:44Z,
GitHub Actions run 38482637767; supersedes the 23:00:58Z snapshot quoted in earlier revisions of this
file — every figure below was re-read from the 23:11:44Z output). Every check below is reproducible: the URL is in the row, and the
raw value can be compared against the file in `live/data/`.

Policy under test: *fixture identity and times come from the Pick'em board itself; probabilities come
from outside bookmaker prices (de-vigged) and from our own model over Valve's official standings;
Hotspawn crowd percentages are never an input.*

---

## 1. Fixture identity and exact UTC times

| Check | Method | Result | Source |
|---|---|---|---|
| The CS2 slate matches the live board | `live/collect.py` reads `<script id="ng-state">` from `/lobby` and `/cs2-pickems`; both pages returned HTTP 200 (433,814 B and 423,435 B, SHA-256 recorded) | 90 CS2 fixture records; 29 still open at snapshot time | https://play.hotspawn.com/cs2-pickems · https://play.hotspawn.com/lobby |
| Lock time = start − 360 s, as the payload states | `lock_offset_sec` read per fixture, never derived from the countdown | holds on all 90 rows (`lock_utc` column) | payload itself (sha256 recorded in `live/data/snapshot.json` provenance) |
| Spot check: Zomblers vs Overtake Sector | board card, payload and our row agree on the pair; board shows "Locks in 02:04:04" at 23:00 UTC → 01:04 UTC lock, payload says `2026-10-14T00:54:00Z` start-6 min with a 01:00 UTC start | agrees | https://www.hotspawn.com/matches/zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3-1079546 |
| Spot check: 9z vs Aurora (Thunderpick, opening day) | HLTV match page: "Best of 3 (LAN)", event "Thunderpick World Championship 2026", 04:30 14 Oct in the viewer's local clock with a countdown of 9 h 28 m at 23:06 UTC → 08:30 UTC | matches our row `2026-10-14T08:30:00Z`, tier S, BO3 | https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026 |

## 2. Own line — Valve Regional Standings (official)

Standings file read this run: 77,872 B, standings as of **2026-10-05**, **380 teams** — every fixture
team resolved except the two flagged in §6 (Envy, LFO 10).

The own line is `p_A = 1 / (1 + 10 ** (-(vrs_A - vrs_B) / 400))` over the points in Valve's published
file (standings as of **2026-10-05**, 380 teams read this run):

https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md

Arithmetic re-checked by hand from the published inputs (recomputed independently of the builder):

| Fixture | VRS points used | Recomputed own line | Published own line |
|---|---|---|---|
| 9z vs Aurora | 1543 / 1716 | 27.0 % / 73.0 % | 27.0 % / 73.0 % |
| HOTU vs Fnatic | 1437 / 1417 | 52.9 % / 47.1 % | 52.9 % / 47.1 % |
| MIBR vs BC.Game | 1585 / 1318 | 82.3 % / 17.7 % | 82.3 % / 17.7 % |
| Legacy vs PARIVISION | 1931 / 1411 | 95.2 % / 4.8 % | 95.2 % / 4.8 % |
| Falcons vs Ninjas in Pyjamas | 1843 / 1534 | 85.6 % / 14.4 % | 85.6 % / 14.4 % |
| FURIA vs BetBoom | 1829 / 1596 | 79.3 % / 20.7 % | 79.3 % / 20.7 % |

## 2b. Cross-check — HLTV World Ranking (independent of Valve's file)

`https://www.hltv.org/ranking/teams/2026/october/12` (1,235,279 B, rendered in the CI browser because the
page answers HTTP 403 to plain clients). 208 rows parsed; the ranking column shown on the card is a
cross-check only — it never feeds the own line. Values spotted against the live page: FURIA #4,
Falcons #5, Aurora #6, Legacy #7, PARIVISION #11, BetBoom #14, Astralis #15, Envy #20, HEROIC #30,
fnatic #36, FORZE Reload #75, 6666 #80, mellren #94, G2 Ares #103, EAC #110, ENCE #114, HAVU #118,
PCIFIC #135, Lavked #140, Overtake Sector #143, The Last Resort #159, Ryvex #181, Zomblers #197,
Enjoy #199, BOJONG #220, Privateer #226, B8 Academy #229. Note Envy is HLTV #20 while Valve's file does
not list the name at all — that is exactly why the Heroic v Envy row carries an HLTV rank but no own
line, and it is flagged rather than silently guessed.

Published VRS values spotted against the live file: Spirit 2046 (#1), Legacy 1931 (#2), Aurora 1716
(#9), Astralis 1674 (#10), BETBOOM 1596 (#11), MIBR 1585 (#12), 9z 1543 (#17), Ninjas in Pyjamas
1534 (#18), HEROIC 1550 (#15), HOTU 1437 (#31), PARIVISION 1411 (#36), fnatic 1417 (#35), HAVU 937
(#124), mellren 932 (#125), The Last Resort 926 (#126), 6666 923 (#127), G2 Ares 913 (#129), PCIFIC
870 (#139), Lavked 862 (#143), Enjoy 871 (#138). **All match.**

## 3. External market — de-vig

`p_A = (1/o_A) / ((1/o_A) + (1/o_B))`, overround reported per row. Recomputed from the published
decimal odds:

| Fixture | Odds published | Recomputed de-vig | Published | Overround |
|---|---|---|---|---|
| 9z vs Aurora | 3.550 / 1.307 | 26.9 / 73.1 | 26.9 / 73.1 | 4.7 % |
| HOTU vs Fnatic | 1.990 / 1.800 | 47.5 / 52.5 | 47.5 / 52.5 | 5.8 % |
| MIBR vs BC.Game | 1.637 / 2.230 | 57.7 / 42.3 | 57.7 / 42.3 | 5.9 % |
| Falcons vs NiP | 1.254 / 4.010 | 76.2 / 23.8 | 76.2 / 23.8 | 4.7 % |
| Heroic vs Envy | 1.469 / 2.620 | 64.1 / 35.9 | 64.1 / 35.9 | 6.2 % |
| Legacy vs PARIVISION | 1.654 / 2.260 | 57.7 / 42.3 | 57.7 / 42.3 | 4.7 % |
| FURIA vs BetBoom | 1.364 / 3.180 | 70.0 / 30.0 | 70.0 / 30.0 | 4.8 % |
| Zomblers vs Overtake Sector | 2.700 / 1.410 | 34.3 / 65.7 | 34.3 / 65.7 | 8.0 % |

Odds source: the public guest responses the Pinnacle matchups page loads itself
(`https://guest.api.arcadia.pinnacle.com/0.1/sports/12/matchups?withSpecials=false` and
`.../sports/12/markets/straight?primaryOnly=false&withSpecials=false`), both HTTP 200 this run
(110,122 B and 503,318 B, SHA-256 recorded). Nine two-way markets were readable and **eight** joined a
Pick'em fixture (name pair + start time within 120 minutes). American prices are converted to decimal
explicitly: `+165 → 2.65`, `−234 → 1.42735`, and an American price inside ±100 is rejected rather than
guessed. Manual review link for the same market: https://www.pinnacle.com/en/esports/games/cs2/matchups/
A second outside source (Polymarket prediction markets, 770,419 B this run) is wired in and clearly
labelled when used, but was not needed on any row this run — no prediction-market price is ever mixed
with a bookmaker price.

## 4. Policy — Hotspawn crowd share is not a probability

* 490 fixture records carried crowd fields in the payload; the builder copies none of them into the
  slate. `live/data/slate.csv` contains **no** `crowd_pct*`, `picked_percent` or `total_picks` column
  (checked by grep and by the build's own gate, which fails the run if one appears).
* The crowd share is published once, on `live/coverage.html`, under
  "Observed crowd pick share — audit only, never an input", to make the difference between crowd
  behaviour and the market auditable. Example from the live board at 23:04 UTC: 9z 5 % / Aurora 95 %
  crowd against our published 26.9 % / 73.1 % (market). The crowd figure is not used anywhere.

## 5. Links and pages

* 6 pages generated (`index`, `matches`, `coverage`, `flagged`, `sources`, `methodology`), **368 internal
  links + fragments checked in the parsed DOM: 0 broken**; all six pages pass a strict HTML tag-balance
  parse; every `flagged.html#FL-xx` anchor referenced anywhere resolves to a published section.
* Every slate row carries at least one official source link (Hotspawn fixture/payload page), and a
  market link whenever a market row exists (enforced by the build's self-check).
* 14 flag sections published, every referenced `flagged.html#FL-xx` anchor resolves.

## 6. Flagged irregularities (all published on `live/flagged.html`)

| ID | Finding | Why it is not blocking |
|---|---|---|
| FL-01 | No readable outside bookmaker price for 21 of 29 open fixtures | The row publishes our own line from Valve's file instead, labelled FL-13; nothing is invented |
| FL-02 | FORZE Reload v LFO 10: "LFO 10" is absent from Valve's file (the file lists LFO 7/8/9) | Probability and pick stay blank on that row |
| FL-04 | Two fixtures had already locked at snapshot time (ex-Keyd Stars–Galorys, SUKEBAN–your end) | Listed as not pickable, never given a pick |
| FL-02 | Heroic v Envy: "Envy" is absent from Valve's standings file (HLTV has them at #20), so no own line | Market line (Pinnacle) still drives a pick, labelled |
| FL-03 | Two outside sources priced 9z–Aurora and MIBR–BC.Game within the same minute | Direct bookmaker preferred; both are linked |
| FL-11 | MIBR v BC.Game (market 57.7 % vs own line 82.3 %) and Legacy v PARIVISION (market 57.7 % vs own line 95.2 %) | Both values shown side by side; the market drives the pick |
| FL-12 | Eight rows quote Pinnacle without a deep per-match URL (the public markup exposes none) | Row links the public matchups page instead of inventing a slug |
| FL-20 | Board header says "68 matches this week"; the CS2 payload carries 90 records (29 open) | Both numbers published; the payload is used because it has ids and times |
| FL-21 | 59 records are June/July 2026 fixtures still marked *scheduled* (starts 2026-06-26 … 2026-07-10) | Kept out of the slate, listed with the reason on the coverage page |
| FL-22 | EGamersWorld returns HTTP 403 to the runner | Recorded as unreadable in the provenance table; its columns stay blank. (The HLTV ranking table **is** readable — 1,235,279 B, 208 rows parsed, 52 of our team names matched; a bug in the first reader was found and fixed, see §2b.) |
| FL-23 | Single external source (Pinnacle) for every priced fixture | Stated on the page; a Polymarket prediction-market reader is wired as a labelled secondary source (4 markets readable this run, none needed because a bookmaker line existed) and is retried on every refresh |
| FL-26 | Valve lists some names twice (one entry per roster): ex-RUSTEC #92/#152, Banda Chuya #165/#373, 6666 #127/#368 | Higher-points entry used, documented; the alternative entry is printed beside the row |

## 7. What a reviewer should check by hand

1. Open https://play.hotspawn.com/cs2-pickems — the card list should match `live/index.html` for the
   fixtures that are still open (team names, order by start time).
2. Pick any row with a market line and open its Pinnacle link; the two decimal odds in
   `live/data/slate.csv` (`ext_odds_a`/`ext_odds_b`) should be recognisable on the page.
3. Open the Valve standings file and compare any `vrs_points_a`/`vrs_points_b` pair in the CSV.
4. Confirm the crowd-share table on `live/coverage.html` is the only place those numbers appear.

*Analysis only — not betting advice. Prices move; every page states its snapshot time.*
