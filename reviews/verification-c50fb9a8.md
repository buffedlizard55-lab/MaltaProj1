# Line-by-line verification report — session `arena/c50fb9a8`

**Date:** 2026-10-13, checks run 22:05–22:35 UTC. **Branch:** `arena/c50fb9a8-maltaproj1`.
**Scope (claimed in COORDINATION.md):** V-01 HTML-escape fix (takeover of stale `arena/6d9c321d`), V-02 docs nav link-in
(takeover of stale `arena/390c1f81`), V-03 this verification pass, V-04 integration. Live-refresh work (`picks/**` by
`arena/616c2455`, `today/**` + `refresh/**` by `arena/b90700c6`) is read-only here.

**Policy applied:** every claim below is checked against an official page fetched during this session (links given).
Values that could not be confirmed are **flagged, never filled in**. Hotspawn crowd pick % is never used as a
probability input.

---

## 1. Fixes shipped in this change-set

### V3-01 (fixed by V-01) — unescaped `<script>` literal broke `docs/verified-lines.html` in the browser
- **Problem (confirmed before fix):** `scripts/6d9c321d_build.py` interpolated data strings containing literal
  `<script id='ng-state'>` into visible HTML (generated lines 112, 1342, 1343). The first stray opener made the HTML
  parser treat everything up to the next `</script>` (line 1408) as script text — so anchors `#flagged-audit` (1330),
  `#F-28` (1336) and `#F-29` (1341) did not exist in the parsed DOM. This is the 4-missing-fragment-target finding
  recorded by `arena/3d05c62d` (SCHED-01, 21:15 UTC) as a request to the stale owner `arena/6d9c321d`
  (last commit 18:32 UTC → stale > 60 min at claim time; handoff logged in COORDINATION.md).
- **Fix:** `from html import escape as _esc` in the generator; every free-text data field rendered into visible copy
  (`notes`, `matches`, `summary`, `severity`, team/tournament names, pick classification, source labels, `data-search`)
  is now escaped at render time. Data files are untouched (generator re-run is byte-deterministic:
  `git status` shows only `docs/verified-lines.html` + the generator changed).
- **Proof after fix** (parsed-DOM scan with Python `html.parser`, which honours `<script>` CDATA the way browsers do):
  only one `<script>` token remains (the page's own JS block at 1384); `#F-28`, `#F-29`, `#flagged-audit` all resolve
  as element ids **outside** script; the three links to those anchors from `docs/flagged.html` resolve; the script
  examples still appear on the page as visible escaped text. Diff of the generated page is entity-escaping only
  (`<`→`&lt;`, `'`→`&#x27;`, `&`→`&amp;`) — no content added or removed.

### V3-02 (fixed by V-02) — `model/` missing from the `docs/` navigation (SA-06 residual)
- **Request history:** `arena/91eff436` O-01 integration requests 1–2 and the F-91 closeout asked the docs owner
  (`arena/390c1f81`, generator `scripts/build_docs.py`) to add `../model/` to the nav and `../model/index.html#flags`
  to the Flagged page. Unresolved at 22:05 UTC (owner stale > 60 min; handoff logged).
- **Fix:** `scripts/build_docs.py` nav now includes **Own lines · Valve VRS model** → `../model/index.html`;
  the generated Flagged page links `../model/index.html#flags` for model-level flags; the docs dashboard links
  `../model/` and `docs/verified-lines.html` in its contributed-dashboards list. All generated `docs/` pages rebuilt
  deterministically (diff = the new links only).

---

## 2. Per-row source-link presence (automated, every published table)

Rule: every data row of a published table must carry at least one external link to an official source.

| Page | Data rows with ≥1 link | Rows without any link | Verdict |
|---|---|---|---|
| `docs/matches.html` (canonical 26) | 26 / 26 | 0 | pass |
| `docs/verified-lines.html` (6d9c321d, 27 matches + 86 ng-state) | all | 0 | pass |
| `picks/matches.html` (P-02, 32 rows) | 32 / 32 | 0 | pass |
| `picks/index.html` (P-02 dashboard) | 12 / 12 | 0 | pass |
| `pickem/cs2.html` (payload inventory, 86) | 86 / 86 | 0 | pass |
| `dashboard/cs2.html` (Linescope) | 27 / 27 | 0 | pass |
| `model/index.html` (O-01 VRS model) | 317 / 339 | **22** | see V3-08 |

## 3. Repository link/anchor crawl (after fixes)

67 HTML pages parsed; 4,542 external links (existence of each file/anchor target checked locally):
**0 broken internal file links, 0 broken fragment targets** (the 4 missing targets reported at 21:15 UTC are gone).

## 4. Live spot-checks against official sources (fetched 22:05–22:35 UTC)

| # | Check | Official source (link) | Result |
|---|---|---|---|
| 1 | Live lobby fixture identity × 30 CS2 rows (teams + starts) vs `picks/` P-02 snapshot | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) | **30/30 match, 0 start-time mismatches.** `picks/` additionally keeps 2 started rows (ex-Keyd–Galorys, Black Phoenix–6666) labelled not-pickable; SUKEBAN–your end is locked in the lobby and correctly marked started. |
| 2 | Gothic–Lavked market direction + price | [EGW match page](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) | Direction **confirmed** (Lavked favorite on every surface: match page 2.05/1.64 at 22:15 UTC; stored listing snapshot 1.881/1.782 at 18:47/22:00 UTC; earlier match-page 2.10/1.62 at 18:20). Exact pair differs **between EGW surfaces at the same time** → V3-07. |
| 3 | Valve VRS snapshot values + roster identity | [Valve standings_global_2026_10_05.md @ eec4853](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) (official ValveSoftware org, commit "Updating Regional Standings for 10/5/2026") | **Confirmed:** Legacy = VRS **#2** (1931 pts, roster arT/dumau/latto/n1ssim/try — identical to HLTV team page roster); Aurora #9; 9z #17; NiP #18; Falcons #6. Header reads "Standings as of 2026_10_05". |
| 4 | PARIVISION ranks | [HLTV team page](https://www.hltv.org/team/12467/parivision) | **Confirmed exactly:** World ranking **#11** (Oct-12 snapshot, RU #2) as stored in `data/ratings.csv` (F-07's "HLTV preferred over third-party #20" stands). HLTV's VRS widget shows #11 (EU #9). |
| 5 | Legacy ranks | [HLTV team page](https://www.hltv.org/team/12468/legacy) | Page now shows World **#7** (links [Oct-12 details](https://www.hltv.org/ranking/teams/2026/october/12/details/12468)) and HLTV's VRS widget **#6** (AM #1). `data/ratings.csv` label "World #6 / VRS #2" matches only Valve's file (#2) → V3-04. |
| 6 | WROTBERRY = WBT alias (flag A-07) | [HLTV match 2399418 WBT vs EAC](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) (Elisa BreakOut Series 2, Group A, BO1 LAN, 15 Oct) | **Confirmed:** HLTV lists "WBT" where Hotspawn lists "WROTBERRY", same slot/event/date. Lineups panel shows **HLTV: #109, VRS: #64** → V3-03. |
| 7 | HLTV ranking date (IR-91-13) | [HLTV World ranking](https://www.hltv.org/ranking/teams/2026/october/12) | **Confirmed:** page reads "World ranking on October 12th, 2026". `lines/reference_ranks.json`'s "dated 2026-10-13" label is wrong (already flagged IR-91-13; reconfirmed live). |

## 5. Findings (published, non-blocking)

| ID | Severity | Finding | Evidence (official links) | Action taken |
|---|---|---|---|---|
| V3-01 | bug (fixed) | Unescaped `<script>` examples swallowed `docs/verified-lines.html` body and broke `#F-28`/`#F-29`/`#flagged-audit` | this report §1; generator `scripts/6d9c321d_build.py` | Fixed + proven (V-01); owner request from SCHED-01 now satisfied |
| V3-02 | bug (fixed) | `model/` not linked from `docs/` nav; `model/#flags` not linked from Flagged page (SA-06 residual) | [model/index.html](https://buffedlizard55-lab.github.io/MaltaProj1/model/index.html) | Fixed (V-02); 91eff436 integration requests 1–2 now satisfied |
| V3-03 | **needs review** | `data/ratings.csv` Elisa rows store **VRS** ranks in the `hltv_world_rank` column: WBT 64 (HLTV World is **#109**), EAC 115 (HLTV #110), BOJONG 387 (HLTV #220). The own-model column for the 12 Elisa fixtures mixes rank series. Row labels cite the Elisa event page group table (which shows the VRS number), not the HLTV world ranking. | [HLTV 2399418 lineups](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) (HLTV: #109, VRS: #64) · [HLTV event 9332](https://www.hltv.org/events/9332/elisa-breakout-series-2) · cross-ref `data/6d9c321d/team_ratings_verified.csv` (WROTBERRY: HLTV #109 / VRS #64) | **Not edited** (canonical `data/` owned by earlier sessions; no value inferred). Owner should relabel the column or blank it; affected model cells should be treated as unverified until then |
| V3-04 | **needs review** | `data/ratings.csv` Legacy row label "HLTV Legacy team page (World #6 / VRS #2)": live page shows World **#7** / VRS widget **#6**; "VRS #2" matches only [Valve's file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) (#2). "World #6" is not confirmable from the cited page at review time (F-06 snapshot-drift family). | [HLTV Legacy](https://www.hltv.org/team/12468/legacy) · [Valve file](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) | Not edited; flagged |
| V3-05 | info (confirmed) | IR-91-13 reconfirmed: HLTV ranking is dated **October 12th, 2026**; `lines/reference_ranks.json` says 2026-10-13 | [HLTV ranking](https://www.hltv.org/ranking/teams/2026/october/12) | Already flagged; no edit |
| V3-06 | info (confirmed) | A-07 reconfirmed live: Hotspawn "WROTBERRY" = HLTV "WBT" (team 13683), same Elisa Group A slot | [HLTV 2399418](https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2) | Rows keep "WROTBERRY (WBT)" labelling |
| V3-07 | info | EGW surfaces disagree on the headline pair at the same minute (listing vs match page: 1.881/1.782 vs 2.05/1.64 for Gothic–Lavked, 22:00–22:15 UTC). Favorite direction consistent both times (Lavked). Intra-day drift family (A-10) extended to surface-vs-surface. | [EGW match page](https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B) | Both snapshots remain timestamp-stamped on the site; nothing rewritten |
| V3-08 | **needs review** | `model/index.html` has 22 table rows with **no inline external link**: 3 this-week fixture rows ("No line: …" Zomblers–Overtake, ex-RUSTEC–mellren, FORZE–LFO 10) and 19 team-flag rows ("NOT IN VRS"/"AMBIGUOUS", absence claims). Absence of a VRS row cannot link a positive record, but the 3 fixture rows could at least link their Hotspawn fixture page. | [model/index.html](https://buffedlizard55-lab.github.io/MaltaProj1/model/index.html) | Not edited (`model/**` owned by `arena/91eff436`); request logged |
| V3-09 | info (confirmed) | `picks/` P-02 snapshot agrees with the live lobby on all 30 listed CS2 fixtures (teams + UTC starts, 0 mismatches); 2 extra rows are labelled started/not-pickable | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) | none needed |

## 6. Reproduction of this pass

1. `python3 scripts/6d9c321d_build.py` → regenerates `docs/verified-lines.html` (deterministic; data files unchanged).
2. `python3 scripts/build_docs.py` → regenerates the 10 canonical `docs/` pages (deterministic; diff = nav/links only).
3. Parsed-DOM anchor check (§1 proof) + repository-wide link/anchor crawl (§3) + per-row link scan (§2) — inline
   scripts run during this session; counts recorded above.
4. Live source fetches (§4) at the times stated. Re-check before acting on any price — odds move (A-10).

---
*Analysis only — not betting advice. Hotspawn crowd pick % is never used as a probability input.*
