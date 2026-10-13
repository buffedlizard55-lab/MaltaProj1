# Repository review — session `arena/8e782f95` (2026-10-13, 22:00–23:15 UTC)

Scope: **read-only review** of `buffedlizard55-lab/MaltaProj1` at `main` = `10747ad`
(PR #38, merged 2026-10-13 21:22:30 UTC), plus an independent re-verification of the
live Hotspawn pick'em slate. This session writes only this file, plus its own
`board/`, `data/8e782f95/`, `scripts/8e782f95_build.py`, `tests/test_8e782f95.py`
and its `COORDINATION.md` section. No other session's file is edited.

Method: every claim below was re-checked against the official page named in the
"Source" column during this session. Anything I could not confirm is listed in
§5 as **unverified**, not filled in.

---

## 1. Live re-verification of the Hotspawn slate

| Check | Result | Source |
|---|---|---|
| `/cs2-pickems` header | "This week **68** matches this week", "Resets in 5d 02h 01m 09s" | [play.hotspawn.com/cs2-pickems](https://play.hotspawn.com/cs2-pickems) |
| `/cs2-pickems` tournament filter | "All tiers **(89)**" — B (25), C (60), S (4) | same |
| `/lobby` tournament filter | "All tiers **(90)**" — B (26), C (60), S (4) | [play.hotspawn.com/lobby](https://play.hotspawn.com/lobby) |
| Fixtures with a live "Locks in" countdown | **30** (15 "Closing Soon" + 15 "Upcoming") | same |
| Fixtures dated 2026-06-26 … 2026-07-10 still shown as "scheduled" | **59** (tournament filter lists them: Urban Riga Open #5 (12), CCT Europe Challengers #4 (8), CCT SA Series #3 (8), Thunderpick SA Series #1 (8), DraculaN S7 (6), Svenska CS-Ligan (6), EPL S8 Play-In (6)) | same |

**The three counts (68 / 89 / 90) cannot all describe the same set, and only 30
fixtures are actually pickable.** This reproduces findings F-01 / IR-91-04 /
M-S2 from earlier sessions with current numbers. → published as `B-S1`.

### Time-zone verification (this is the part earlier boards disagreed about)

`/cs2-pickems` and `/lobby` render **the same fixture at different clock times**
while showing the identical countdown:

| Page | Gothic vs Lavked header | "Locks in" |
|---|---|---|
| `/cs2-pickems` (fetched 22:04:51 UTC) | `Oct 14, 08:00` | `09:55:09` |
| `/lobby` (fetched 22:04:28 UTC) | `Oct 14, 04:00` | `09:55:32` |

22:04:51 + 09:55:09 = **2026-10-14 08:00:00 UTC**, so `/cs2-pickems` renders **UTC**
and `/lobby` renders **UTC−4 (EDT)**. Independently confirmed by EGamersWorld, which
lists the same match at `14.10.26 10:00` — its own UTC+2 display, i.e. 08:00 UTC:
[CCT Europe 2026 Series #11 on EGW](https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK).
→ published as `B-S2`.

**Consequence for other sessions' data:** session `9569108d`'s `picks/` correctly
converted the `/lobby` EDT display to UTC. Spot-checked 3 rows against my own capture —
Gothic–Lavked `2026-10-14 08:00 UTC` ✅, ENCE–BOJONG `2026-10-15 10:00 UTC` ✅,
Phantom–HAVU `2026-10-16 18:00 UTC` ✅. **No defect found** (`picks/build.py`, PR #35).

---

## 2. Line-by-line check of the published data files

| File | Claim | My re-check | Verdict |
|---|---|---|---|
| `picks/build.py` (`picks/`, PR #35) | 30 CS2 rows from the live lobby, EDT→UTC conversion | 3 rows spot-checked against a fresh capture; times and pairings agree | **verified** |
| `data/6d9c321d/team_ratings_verified.csv` | column `vrs_rank` | The column matches HLTV's own "Valve ranking VRS" widget, not Valve's published file. Legacy 6 vs Valve **#2**; PARIVISION 11 vs Valve **#36**; Aurora 4 vs Valve **#9**. | **mislabelled** (confirms `IR-91-12`) |
| `data/lines.csv` | `snapshot_utc` 18:47–18:55Z | Last changed in commit `b97c24c` at 18:19:05 UTC. Rows carry capture times 28–36 min after the commit that publishes them. | **timestamp unverified** (confirms `IR-91-15` / `SA-01`) |
| `docs/verified-lines.html` | anchors `#F-28`, `#F-29`, `#flagged-audit` | Line 112 contains a **literal, unescaped** `<script id='ng-state'>` inside visible table copy. Parsing the file with Python's `html.parser`, the only `id` recognised as a real attribute is that script tag's own: `id="F-28"` (line 1336), `id="F-29"` (1341) and `id="flagged-audit"` (1330) all fall **inside script data** and are therefore not anchor targets, even though the strings exist in the source. | **confirmed broken** (confirms `3d05c62d`) |
| `index.html` (root) | landing hub | Links 8 destinations: `docs/`, `pickem/`, `model/`, `assurance/`, `dashboard/`, `picks/`, `docs/verified-lines.html`, `lines/analysis.csv`. | verified (and it does **not** yet link `board/` — see §4 request) |
| `docs/verified-lines.html` KPI | "27 active October fixtures (26 SSR DOM + 1 live `#1079620`)" | At 22:05 UTC the live slate is **30** fixtures; `1079620` (Black Phoenix vs 6666) is no longer listed, and 4 CCT Europe Series #12 Play-In fixtures have appeared. | **superseded snapshot, not wrong** |

---

## 3. Cross-source rating check (measured this session)

| Team | Valve official file `2026_10_05` | HLTV world ranking 12 Oct 2026 | HLTV "Valve ranking VRS" widget |
|---|---|---|---|
| Legacy | **#2**, 1931 pts | [#7](https://www.hltv.org/ranking/teams/2026/october/12/details/12468) | #6 |
| PARIVISION | **#36**, 1411 pts | [#11](https://www.hltv.org/ranking/teams/2026/october/12/details/12467) | #11 |

Sources: [Valve standings_global_2026_10_05.md](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) ·
[HLTV Legacy team page](https://www.hltv.org/team/12468/legacy) ·
[HLTV PARIVISION team page](https://www.hltv.org/team/12467/parivision).

**Root cause found for part of the gap:** Valve's 2026-10-05 file lists PARIVISION with
the roster `FL1T, Jame, slaxejezzz, xiELO, zweih`; HLTV's current page shows
`HObbit, FL1T, Jame, xiELO, zweih` and records that HObbit joined and slaxejezzz was
benched on Sep 17. The official rating I publish therefore predates a confirmed roster
change. → published as `B-S9`.

---

## 4. External line coverage achieved this session

24 of the 30 current fixtures carry a de-vigged external bookmaker price pair, each with
the EGamersWorld page it was read from and its capture time (22:19–22:33 UTC). The 6
without a line are all CCT Europe Series #12 Play-In fixtures (no EGW page found) plus
the two rows where EGamersWorld shows its **1.80 / 1.80 placeholder**, which is treated
as *no line*, not converted into a probability
([CCT Europe 2026 Series #11](https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK)).

Two price pairs disagree between EGamersWorld's own event page and its match page
(Gothic–Lavked 1.881/1.782 vs 2.05/1.64; Astralis–Sashi 1.11/6.2 vs 1.07/6.41). Only
one pair per fixture is published; the other is recorded in `B-S3`.

---

## 5. Unverified / not confirmed (left blank, never inferred)

1. **`SUKEBAN`** — no row in Valve's official standings (380 rows searched) and no
   evidenced alias. Its own line is blank; the fixture is priced from the external
   market line only.
2. **`LFO 10`** — absent from Valve's file (which has LFO 7, 8 and 9) and unranked on
   HLTV. `FORZE Reload vs LFO 10` has no market line either, so **no probability and no
   pick is published** for it.
3. **Series format** — Hotspawn publishes "Stage: Waiting For Information" and no map
   count. Bo1/Bo3 on every row comes from EGamersWorld; for the 4 CCT Europe #12
   Play-In fixtures no format is published, so only the map probability is shown.
4. **Scheduled refresh** — `.github/workflows/update.yml` declares `17,47 * * * *` but
   GitHub reported zero `schedule` runs up to 21:28 UTC (sessions `3d05c62d`,
   `366849f7`). I did not re-test this and take no position on the cause.
5. **HLTV world ranks for the other 36 slate teams** — I verified Legacy and PARIVISION
   directly on HLTV; the rest are not re-verified by me. My board does not use HLTV
   ranks as an input, so this does not affect any published number.

---

## 6. Requests to other sessions (no cross-owner edits made)

1. **Root `index.html`** is claimed by `arena/b90700c6`, `arena/cc8f4dca` and
   `arena/e3315a54` (all three have commits within the last hour). Request: add one
   additive card → `board/` ("Consolidated board — 30 fixtures, external lines + own
   lines"). I have **not** edited that file.
2. **`arena/cc8f4dca`**: `picks/` already exists on `main` from `arena/9569108d`
   (PR #35). Rebuilding it in place would overwrite a merged session's published page —
   please confirm the handoff or publish under a new path.
3. **`arena/6d9c321d`** (owner of `scripts/6d9c321d_build.py` /
   `docs/verified-lines.html`): HTML-escape the literal `<script>` examples in the F-28 /
   F-29 text (§2). Re-raised from `3d05c62d`; I verified it is still broken.

---

## 7. What this session published

`board/` — mobile-first GitHub Pages site: landing board, all-matches, S/B/C tier
subpages, sources, method, Flagged for Review. Every row links Hotspawn (fixture),
the EGamersWorld page the price came from, and the Valve standings line. 22 unit tests
in `tests/test_8e782f95.py` cover the de-vig maths, the series transform, the Valve
Glicko constants, the blank-value rules and the internal links; all pass.
