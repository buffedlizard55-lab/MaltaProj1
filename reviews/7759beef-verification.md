# Session `arena/7759beef` — line-by-line verification record

Board: `valuepicks/` (day review, guaranteed picks, value watches). Branch:
`arena/7759beef-maltaproj1`. Built by `scripts/7759beef_build.py`; invariants in
`tests/test_7759beef.py` (13 tests, all passing at commit time).

Everything published by this board comes from one of two places:

* the committed executive capture (`executive/data/analysis.csv`, `summary.json`,
  `fallback_research.json`, `secondary_lines.json`, `ratings.csv`), which is itself source-linked
  upstream; or
* `research/7759beef/sources.json`, the 25 facts re-read by this session (URL, tier and read time on
  every row).

No number on this board is inferred, and no value is filled in from a headline. Where a value could
not be confirmed, the row says so.

## 1. Coverage check — every open fixture has a pick

Executive capture `2026-10-15T08:51:05Z`, 80 fixtures, 17 open. All 17 publish a pick and a
two-sided probability in `valuepicks/data/board.csv`:

| # | Fixture | Lock (UTC) | Pick | Published % | Tier |
|---|---|---|---|---|---|
| 1 | MIBR vs BC.Game | 09:54 | MIBR | 54.8 / 45.2 | A direct book (Pinnacle) |
| 2 | Heroic vs Envy | 09:54 | Heroic | 65.3 / 34.7 | A direct book (Pinnacle) |
| 3 | ENCE vs BOJONG | 09:54 | ENCE | 71.7 / 28.3 | A direct book (Pinnacle) |
| 4 | 9z vs Falcons | 10:54 | Falcons | 75.8 / 24.2 | A direct book (Pinnacle, stored 08:51:15Z) |
| 5 | WROTBERRY vs ENCE | 11:54 | WROTBERRY | 61.5 / 38.5 | B relayed listing (Thunderpick via bo3.gg, 06:23:29Z) |
| 6 | PARIVISION vs BetBoom | 13:24 | PARIVISION | 51.3 / 48.7 | B relayed book (BetBoom via cyber.sports.ru) |
| 7 | EAC vs BOJONG | 13:54 | EAC | 76.6 / 23.4 | A direct book (Pinnacle) |
| 8 | Legacy vs FURIA | 15:54 | FURIA | 57.4 / 42.6 | A direct book (Pinnacle) |
| 9 | WROTBERRY vs BOJONG | 15:54 | WROTBERRY | 76.9 / 23.1 | B relayed listing (06:23:29Z) |
| 10 | EAC vs ENCE | 17:54 | EAC | 58.6 / 41.4 | A direct book (Pinnacle) |
| 11 | Voca vs Phantom | 16 Oct 07:54 | Phantom | 51.4 / 48.6 | B secondary listing (Thunderpick) |
| 12 | HAVU vs RoundsGG | 16 Oct 09:54 | HAVU | 76.9 / 23.1 | B relayed listing (06:23:29Z) |
| 13 | Voca vs HAVU | 16 Oct 11:54 | Voca | 65.5 / 34.5 | B secondary listing (Thunderpick) |
| 14 | Phantom vs RoundsGG | 16 Oct 13:54 | Phantom | 91.5 / 8.5 | C prediction market (Polymarket) |
| 15 | mellren vs Privateer | 16 Oct 13:54 | mellren | 95.1 / 4.9 | D project line (official ratings) |
| 16 | RoundsGG vs Voca | 16 Oct 15:54 | Voca | 89.0 / 11.0 | C prediction market (Polymarket) |
| 17 | Phantom vs HAVU | 16 Oct 17:54 | Phantom | 68.2 / 31.8 | B secondary listing (Thunderpick) |

The remaining 63 captured fixtures are locked or stale listings from the June 2026 pool; they are
published as inventory on `valuepicks/coverage.html` with no pick and the reason stated, because a
pick on a fixture that locked months ago would be meaningless.

## 2. The five rows this session rebuilt (previously blank on the executive board)

| Fixture | What was missing | What was verified | Result |
|---|---|---|---|
| 9z vs Falcons (`1080202`) | format unknown, quote rejected on a 30-minute kickoff difference | Official match page 2399409 → "Best of 3 (LAN), Group A winners' match"; kickoff 11:00Z against a 10:54Z Hotspawn lock, so the difference was in the stored join, not the match | Pinnacle 3.95 / 1.260417 → 24.2 / 75.8 |
| WROTBERRY vs ENCE (`1080281`) | identity ("WROTBERRY" ≠ any official entry), format unknown, quote aged out | HLTV team 13683 = WBT, roster identical to the official VRS entry (#60, 1201 points); the same page lists WBT vs ENCE and WBT vs BOJONG on 15 Oct. Match page 2399420 → "Best of 1 (LAN), Group A" | Thunderpick 1.50 / 2.40 → 61.5 / 38.5 |
| PARIVISION vs BetBoom (`1080203`) | no quote at all in the executive capture | Match page 2399410 → "Best of 3 (LAN), Group B elimination", 13:30Z start; same-day bookmaker report (BetBoom 1.85 / 1.95) | 51.3 / 48.7 |
| WROTBERRY vs BOJONG (`1080283`) | identity, quote aged out | WBT identity as above; event group-stage format BO1 | Thunderpick 1.20 / 4.00 → 76.9 / 23.1 |
| HAVU vs RoundsGG (`1080286`) | identity ("RoundsGG" ≠ "ROUNDS"), format unknown | HLTV team 12457 = ROUNDS, four of five starters identical to the official VRS entry (#310, 548 points); fixture list matches the Hotspawn card | Thunderpick 1.20 / 4.00 → 76.9 / 23.1 |

De-vig is proportional: `p = (1/odds) / Σ(1/odds)`. The build asserts each stored pair equals the
recomputed pair, so a transcription error cannot ship.

## 3. Day-1 review — what the 9z–Aurora upset actually showed

| Claim | Source | Read |
|---|---|---|
| 9z 2-0 Aurora; Inferno 13-11, Nuke 13-1 | [HLTV news 45718](https://www.hltv.org/news/45718/9z-beat-aurora-2-0-to-kick-off-twc-2026) · [match 2399384](https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026) | 10:02Z |
| luchov 1.61 rating, 97.4 ADR; kyxsan 0.53 | HLTV news 45718 (scoreboard) | 10:02Z |
| 9z +62 VRS points → 1571, third in the Americas | HLTV news 45718 | 10:02Z |
| Aurora −21 → 1817, 4th→5th | [skin.club community report](https://community.skin.club/en/news/9z-defeated-aurora-at-the-start-of-thunderpick-wc-2026) — secondary, published as such | 10:02Z |
| Other day-1 results all 2-0 (Falcons over NiP, Legacy over PARIVISION, FURIA over BetBoom) | [Hotspawn day-1 review](https://www.hotspawn.com/counter-strike/news/thunderpick-world-championship-2026-day-1-review) · [Field Level Media](https://fieldlevelmedia.com/esports/thunderpick-world-championship-opens-with-4-group-stage-sweeps/) | 10:04Z |
| Aurora vs NiP was live at read time; Cache 13-9 Aurora | [match 2399408](https://www.hltv.org/matches/2399408/aurora-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026) | 10:05Z |

Roster/context intel used on the board (all source-linked in `research/7759beef/sources.json`):
Aurora's July-2026 rebuild with kyxsan, Jimpphat and coach ash replacing MAJ3R, soulfly and Fabre
(HLTV news 45082 / 45050); Aurora's coach describing the integration gap in August (secondary summary
of an HLTV interview); NiP adding Krimbo and replacing Virtus.pro in the event (Hotspawn day-2
preview, HLTV news 45688); Aurora's compressed EPL → TWC schedule (esportbet tips, secondary).

## 4. Value watches — the rule, and the caveats

Gap = project own line − market, on the better side, published when both exist. Twelve of the 17 open
fixtures clear 5pp. The largest are PARIVISION–BetBoom (project prefers BetBoom by +35.0pp against a
51.3/48.7 market) and WROTBERRY–BOJONG (+21.7pp, project line 98.6%). Both are flagged: an
uncalibrated project line on official ratings is a disagreement, not a forecast, and the market has
watched these teams this week.

## 5. Irregularities and limitations recorded by this session

* **IR-7759beef-01** — Hotspawn's team names "WROTBERRY" and "RoundsGG" do not appear in the official
  Valve standings file. Identity is published at roster level (five and four identical players,
  plus matching opponents/dates) with flag `VP-F02`, never silently equated.
* **IR-7759beef-02** — No stored direct-book quote exists for 9z vs Falcons after 08:51:15Z; the row
  publishes that capture time rather than pretending freshness, and reads as tier A only in basis.
* **IR-7759beef-03** — The Elisa group-stage format is verified BO1 on a sibling match page
  (2399420) for three of the local fixtures; per-fixture pages for 1080283/1089286 had not started at
  read time. The limitation is printed on the row.
* **IR-7759beef-04** — PARIVISION vs BetBoom's headline comes from a third-party report of a
  bookmaker line (cyber.sports.ru, same day). Other previews report a range (1.79–1.83 / 1.91–2.04)
  that brackets it; the row is tier B, not tier A.
* **IR-7759beef-05** — `executive/data/fallback_research.json` records HTTP 403 for every HLTV
  match-page read by the CI collector at 08:53Z, which is why those rows were blank. The same pages
  were readable from this session's tools at 10:02–10:05Z; the difference is recorded here rather
  than hidden.
* **IR-7759beef-06** — The sandbox cannot reach Hotspawn/HLTV/bookmakers from `bash` (egress is
  restricted to a small host allowlist), so all live reads in this record were performed with the
  session's fetch/search tools; the automated four-hour pipeline remains the collector of record.

## 6. Reproduction

```
python3 scripts/7759beef_build.py        # rebuild valuepicks/ from the committed capture
python3 -m unittest tests.test_7759beef  # 13 invariants (picks, maths, sources, links)
python3 scripts/audit_91e444dd.py        # repository-wide local-link audit
```
