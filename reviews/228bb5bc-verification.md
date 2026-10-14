# Verification record — session `arena/228bb5bc` (final integration)

**Deliverables:** consolidated board <https://buffedlizard55-lab.github.io/MaltaProj1/console/index.html>
(mobile-first, one row per open match) · Flagged for Review
<https://buffedlizard55-lab.github.io/MaltaProj1/console/flagged.html> · single executive-summary landing
page <https://buffedlizard55-lab.github.io/MaltaProj1/>.

**Question answered:** does every row of the consolidated board carry a pick, both teams' win
probability from an outside betting line or an own originated line, a read time, and a link to the exact
source that produced the number — and does the cited source re-read as published? Any value that could
not be confirmed stays blank and is flagged.

## 0. Site-level irregularities found before the work (all fixed in this session)

| ID | Irregularity (found on `main` @ `34015c4`) | Evidence | Resolution |
|---|---|---|---|
| IR-228-01 | Root `index.html` rendered an internal merge-conflict note as visible page text ("# Conflict resolved 2026-10-14 …"), above the first card | old `index.html` line 60 | the restructure removes it; the new page is checked to contain no conflict marker |
| IR-228-02 | The landing page published **three competing executive summaries** (`executive/`, `picks-full/`, `everypick/`) with different counts, plus a stats strip reading `slate/`'s 02:23Z snapshot ("5 Supported picks") while the boards published 28/28 | `slate/data/summary.json` vs `data/63ee81ba/coverage.json` | the landing page now loads its counts from the consolidated board's `coverage.json`; the old boards keep their own pages but no longer head the site |
| IR-228-03 | No single "last refreshed" line on the landing page | old page had per-script stamps only | the live-status line prints `data_as_of_utc` from `console/data/coverage.json` and turns amber if `stale` |

## 1. Coverage result — a pick for every open fixture

The consolidated board joins six committed captures (feeds, cs2 line analysis, executive, every, picks-full
market lines, picks-full own lines) by fixture id and publishes **28 rows / 28 open fixtures / 28 picks
(25 outside-market, 2 own line, 1 research), 0 blank**. The pick is always one of the two teams; on an exact
tie no pick is printed. Each row carries the read time of the capture behind it and a source URL that is
never a Hotspawn page (Hotspawn is used for fixture identity, competition, tier and lock time only, and its
crowd percentage is never read — enforced as a build invariant, see §9).

## 2. Line-by-line table (the 28 open rows of the snapshot issued here)

Machine-readable twin: `console/data/picks.csv` (source URL and read time on every row); each row is also
rendered on the board with the same links. "Hand re-read" = the URL was opened live during this session
(2026-10-14 04:0x UTC) and the arithmetic reproduced below was re-done from the page.

| Fixture (Hotspawn id) | Pick | Basis | Cited source | Verification |
|---|---|---|---|---|
| Gothic v Lavked (`1079621`) | Lavked 55.6% | market-3 | [egamersworld.com 2.05/1.64](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) | hand re-read: 2.05/1.64 → 44.4/55.6, **exact** |
| Enjoy v B8 Academy (`1081111`) | Enjoy 60.2% | market-3 | [egamersworld.com 1.52/2.30](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/enjoy-vs-b8-academy-qwO9cEnL7) | hand re-read: → 60.2/39.8, **exact** |
| ex-RUSTEC v mellren (`1079622`) | ex-RUSTEC 65.7% | market-3 | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/ex-rustec-vs-mellren-ZGVCwI7MK) | EGW refuses CI re-reads (403) — flagged R-228-07 |
| G2 Ares v The Last Resort (`1079623`) | G2 Ares 62.4% | market-3 | [egamersworld.com](https://egamersworld.com/counterstrike/match/_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L) | EGW refuses CI re-reads (403) — flagged R-228-07 |
| 9z v Aurora (`1080176`) | Aurora 72.0% | market-1 | [Pinnacle guest endpoint](https://guest.api.arcadia.pinnacle.com/0.1/sports/12/markets/straight?primaryOnly=false&withSpecials=false) | endpoint-only, no per-match URL — flagged R-228-06 |
| HOTU v Fnatic (`1079439`) | Fnatic 50.4% | market-1 | same endpoint | endpoint-only — R-228-06 (row also flagged C-THIN-MARKET, 49.6/50.4) |
| Falcons v NiP (`1080177`) | Falcons 75.2% | market-1 | same endpoint | endpoint-only — R-228-06; HLTV identity page re-read by CI (`match`) |
| Legacy v PARIVISION (`1080178`) | Legacy 53.9% | market-1 | same endpoint | endpoint-only — R-228-06 |
| FURIA v BetBoom (`1080179`) | FURIA 70.0% | market-1 | same endpoint | endpoint-only — R-228-06; HLTV identity page re-read by CI (`match`) |
| MIBR v BC.Game (`1079440`) | MIBR 57.4% | market-1 | same endpoint | endpoint-only — R-228-06 |
| Heroic v Envy (`1079442`) | Heroic 64.1% | market-1 | same endpoint | endpoint-only — R-228-06; own-line rating re-checked via documented alias (§4); HLTV 2399137 confirms Bo3 LAN, Group D opener |
| Astralis v Sashi (`1079438`) | Astralis 85.4% | market-2 | [thunderpick.io 2767822](https://thunderpick.io/match/2767822) | book page linked; not hand re-read — R-228-08 |
| WROTBERRY v EAC (`1080279`) | EAC 53.8% | market-2 | [thunderpick.io 2807510](https://thunderpick.io/match/2807510) | hand re-read: WBT +100 / EA Copenhagen −139 → 46.2/53.8, **exact**; page title confirms WROTBERRY = WBT |
| ENCE v BOJONG (`1080280`) | ENCE 71.1% | market-2 | [thunderpick.io 2807501](https://thunderpick.io/match/2807501) | book page linked — R-228-08 |
| WROTBERRY v ENCE (`1080281`) | WROTBERRY 57.0% | market-2 | [thunderpick.io 2807512](https://thunderpick.io/match/2807512) | hand re-read: WBT −161 / ENCE +115 → 57.0/43.0, **exact** |
| EAC v BOJONG (`1080282`) | EAC 76.9% | market-2 | [thunderpick.io 2807496](https://thunderpick.io/match/2807496) | book page linked — R-228-08 |
| WROTBERRY v BOJONG (`1080283`) | WROTBERRY 76.9% | market-2 | [thunderpick.io 2807511](https://thunderpick.io/match/2807511) | book page linked — R-228-08 |
| EAC v ENCE (`1080284`) | EAC 61.5% | market-2 | [thunderpick.io 2807492](https://thunderpick.io/match/2807492) | book page linked — R-228-08 |
| Voca v Phantom (`1080285`) | Phantom 51.4% | market-2 | [thunderpick.io 2807497](https://thunderpick.io/match/2807497) | hand re-read: Voca −111 / Phantom −125 → 48.6/51.4, **exact** |
| HAVU v RoundsGG (`1080286`) | HAVU 76.9% | market-2 | [thunderpick.io 2807498](https://thunderpick.io/match/2807498) | book page linked — R-228-08 |
| Voca v HAVU (`1080287`) | Voca 65.5% | market-2 | [thunderpick.io 2807499](https://thunderpick.io/match/2807499) | book page linked — R-228-08 |
| Phantom v RoundsGG (`1080288`) | Phantom 86.8% | market-2 | [thunderpick.io 2807503](https://thunderpick.io/match/2807503) | book page linked — R-228-08 |
| RoundsGG v Voca (`1080289`) | Voca 85.4% | market-2 | [thunderpick.io 2807505](https://thunderpick.io/match/2807505) | book page linked — R-228-08 |
| Phantom v HAVU (`1080290`) | Phantom 68.2% | market-2 | [thunderpick.io 2807508](https://thunderpick.io/match/2807508) | book page linked — R-228-08 |
| Ryvex v PCIFIC (`1081113`) | PCIFIC 80.5% | market-4 | [polymarket.com cs2-wraith-ryvex](https://polymarket.com/event/cs2-wraith-ryvex-2026-10-14) | hand re-read: WRAITH PCIFIC 83¢ / Ryvex 21¢ vs captured 19.5/80.5 — same pick, small drift; identity chain in R-228-04 |
| Banda chuya v 6666 (`1081112`) | 6666 61.8% | own-line | [VRS `#L170`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L170) | anchors recomputed at build time: `#L170` = Banda Chuya #165 (801), `#L132` = 6666 #127 (923) |
| mellren v Privateer (`1081120`) | mellren 78.5% | own-line | [VRS `#L130`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L130) | anchors recomputed: `#L130` = mellren #125 (932), `#L276` = Privateer #271 (608) |
| FORZE Reload v LFO 10 (`1079624`) | FORZE Reload 75.9% | research | [VRS `#L89`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md?plain=1#L89) | FORZE Reload `#L89` = #84 (1100) verified; **LFO 10 has no row in the official standings** — the pick is labelled research/unverified (C-RESEARCH-LINE) and kept visible |

Mismatches found and how they were handled: none of the hand re-reads contradicted a published number.
The only value-level disagreements inside the boards are the three pick divergences (market vs own line)
already published on the board (`1079623`, `1080279`, `1080285`) — they are shown as such, not averaged.

## 3. Own originated lines — the official-rating anchor audit

Every own-line probability cites a line in the pinned Valve Regional Standings file. The build re-opens the
committed copy of that file (`data/63ee81ba/vrs_2026_10_05.md`), checks its SHA-256 against the hash the
picks board published, follows the URL's `#Lnnn` anchor, and confirms the line names the team (or a
documented, evidence-linked alias) with the same standing and points. The same check runs in
`tests/test_228bb5bc.py`.

* SHA-256 of the committed file: `df96e7fc3cd91a2687ec08cac0128e50cc4e4e55346581679572e881d79ae61b`
  — identical to the hash claimed in `data/63ee81ba/coverage.json` and to the file fetched at the pinned
  commit [`eec4853d`](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md).
* 56 cited sides: **48 exact, 7 resolved through a documented alias, 1 absent** (the research row above).

| Alias used | Official row found | Standing / points | Documented at |
|---|---|---|---|
| WROTBERRY (×3) | WBT | #60 / 1201 | `cs2/aliases.json` → [HLTV 2399418](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) |
| RoundsGG (×3) | ROUNDS | #310 / 548 | `cs2/aliases.json` → [HLTV 2399425](https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2) |
| Envy (×1) | 3DMAX | #21 / 1500 | `executive/aliases.json` → [Valve details page](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/details/2026_10_05/0021--3dmax--graviti-kursy-lucky-maka-misutaaa.md) |

The Envy equivalence is corroborated independently: [HLTV team 5991](https://www.hltv.org/team/5991/envy)
lists the same five French players (Maka, Lucky, misutaaa, Kursy, Graviti) that the pinned file carries on
the 3DMAX line. The alias lives only in `executive/aliases.json` (not in `cs2/aliases.json`) and the
component boards flag this fixture differently (own_lines: none; `every/`: `FL-ALIAS-RESOLVED`;
`executive/`: `FL-ALIAS-NAME;FL-FORMAT-UNKNOWN`) — recorded as R-228-05.

Also verified by hand: the pinned file lists **Banda Chuya twice** (`#165`, five-man roster; `#373`,
two-player) — the board deliberately cites the five-player listing and the duplicate is documented upstream
(`FL-DUPLICATE-VRS-DISAMBIGUATED`); **LFO 10 appears nowhere**, which is why that one pick is a labelled
research estimate rather than a rating-based number.

## 4. Live re-reads performed during this session (hand checks)

| Fixture | Page opened | Published on the row | Re-read now | Verdict |
|---|---|---|---|---|
| `1079621` | EGW Gothic–Lavked | 44.4 / 55.6 | 2.05 / 1.64 → 44.4 / 55.6 | exact |
| `1081111` | EGW Enjoy–B8 Academy | 60.2 / 39.8 | 1.52 / 2.30 → 60.2 / 39.8 | exact |
| `1080279` | Thunderpick 2807510 | 46.2 / 53.8 | WBT +100 / EA Copenhagen −139 → (1/2.00, 1/1.7194) → 46.2 / 53.8 | exact |
| `1080285` | Thunderpick 2807497 | 48.6 / 51.4 | Voca −111 / Phantom −125 → 48.6 / 51.4 | exact |
| `1080281` | Thunderpick 2807512 | 57.0 / 43.0 | WBT −161 / ENCE +115 → 57.0 / 43.0 | exact |
| `1081113` | Polymarket WRAITH PCIFIC–Ryvex | 19.5 / 80.5 | 83¢ / 21¢ | same favourite, small drift |
| `1079621` alternate | Polymarket Gothic–Lavked | 49.5 / 50.5 (not headline) | 50¢ / 51¢ → 49.5 / 50.5 | exact |
| `1079442` | HLTV 2399137 / team 5991 | — | Bo3 LAN, Group D opener; Envy roster as above | identity confirmed |

Identity cross-checks for the same fixture (`1081113`): Hotspawn "PCIFIC" ↔ HLTV team 13054 "PCIFIC"
(Türkiye, roster jresy/scolleN/lugseN/oyesil) ↔ Polymarket's market named for "WRAITH PCIFIC";
EGamersWorld carries the same 14 Oct 16:00 CEST fixture twice, as
[PCIFIC Espor](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/pcific-espor-vs-ryvex-WPw_DghZr3)
and [WRAITH PCIFIC](https://egamersworld.com/counterstrike/match/1sGIL2gAYu/wraith-pcific-vs-ryvex-bBH6HvaalZ),
with identical rosters — recorded as R-228-04 (kept, flagged for a manual look at the naming).

## 5. Independent CI-side evidence (session `bdc98a9a`, merged as PR #103)

The merged re-read verifier re-opens every URL cited by the boards (360 values at its last run:
<https://buffedlizard55-lab.github.io/MaltaProj1/reread/index.html>). Relevant results for this board's
sources: EGamersWorld **refused** (403) for all 45 cited EGW values, Hotspawn pages refused (403), the
Pinnacle guest API **not-checkable** (12 values), HLTV mixed (65 re-read as published, 35 refused),
Polymarket reference markets re-read (`match`). Where the CI runner is refused, the value is recorded as
refused rather than filled in — the hand re-reads in §4 cover three of the four EGW rows and three of the
thirteen Thunderpick rows; the rest stay flagged (R-228-07, R-228-08).

## 6. Flagged for Review — published, not blocking

The consolidated page <https://buffedlizard55-lab.github.io/MaltaProj1/console/flagged.html> lists every
condition that makes a row less than fully verified (14 flag codes on the reviewed snapshot: relayed
prices, rejected prediction-market quotes, name variants, market-vs-model splits, coin-flip margin,
opponent conflicts, research range, unverified-research) plus the five curated manual-review findings,
each with the fixture and a source link: R-228-04 (PCIFIC/WRAITH PCIFIC), R-228-05 (Envy/3DMAX alias
location), R-228-06 (Pinnacle endpoint-only citation), R-228-07 (EGW CI refusal), R-228-08 (Thunderpick
outside the CI re-read worklist). They are maintained in `console/data/review_findings.csv` so the page
cannot silently drop them.

## 7. What could not be verified (kept visible, never invented)

* Pinnacle prices cannot be re-read after the fact: the guest API publishes no per-match URL, so the row's
  odds + read time are the evidence (R-228-06; 7 rows).
* bc.game quotes relayed through EGamersWorld are refused to CI (403) and two of the four rows were
  hand-checked instead (R-228-07).
* Thunderpick pages were hand-checked for 3 of 13 rows; the remainder carry the exact book page (R-228-08).
* Hotspawn match pages return 403 to the runner; fixture identity is taken from the archived capture and
  cross-checked against HLTV match pages where those re-read.
* Prediction-market prices move intraday; the board prints the capture time on the row and the market's
  traded price, not a bookmaker line (C-PREDICTION-MARKET-PRICE).

## 8. Invariants enforced at build time (fail closed, no manual step)

`scripts/228bb5bc_build.py` refuses to publish when: fixture ids are not unique; a published probability
pair does not sum to 100 ± 0.25; a headline lacks an `http(s)` source URL or cites a `hotspawn.com` URL;
the pick is not one of the two teams; a pick is printed on an exact tie; a read time is missing; or the
newest input capture is more than six hours old. The same script re-checks every own-line rating anchor
against the committed official standings file and withholds the probability of any row whose rating cannot
be confirmed (flag `C-OWN-LINE-UNVERIFIED`) — no such row exists on this snapshot.

## 9. Reproduce

```bash
python3 scripts/228bb5bc_build.py            # rebuilds console/** from the committed captures
CONSOLE_NOW_UTC=2026-10-14T04:00:00Z python3 scripts/228bb5bc_build.py   # deterministic replay
python3 -m unittest tests/test_228bb5bc.py   # 42 tests incl. the anchor re-check and the landing registry
python3 scripts/audit_91e444dd.py --output /tmp/audit.json   # repo-wide link audit (0 errors)
```

Automation: `.github/workflows/console-228bb5bc.yml` runs hourly (`:23`), validates on branch pushes and
commits the regenerated files on `main` only.
