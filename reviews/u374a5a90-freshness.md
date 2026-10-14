# U-02 Freshness & coverage sweep — 2026-10-14 (session `arena/374a5a90`)

Independent, read-only verification of the CS2 Pick'em slate offered on Hotspawn Play and of how the
repo's published boards cover it. Nothing in this report is inferred: every value carries the source
link it was read from, and anything that could not be confirmed from an official source is left blank
and listed under [Irregularities](#irregularities-flagged-non-blocking). Hotspawn crowd percentages
("x% picked") are **never** used as probability inputs and are not reproduced here except where their
absence is the point (they are dropped at ingest by every pipeline in this repo).

- Reviewer: session `arena/374a5a90` (branch `arena/374a5a90-maltaproj1`).
- Capture window: **2026-10-14 01:57–02:05 UTC**.
- Cross-checked against `data/08031d30/hotspawn_open_cs2.csv` (session `arena/08031d30`, read 01:40Z,
  merged in [PR #71](https://github.com/buffedlizard55-lab/MaltaProj1/pull/71)) — 0 mismatches.

---

## 1. Live slate capture (official source: Hotspawn Play)

Sources read in this session (official, first-party):

- <https://play.hotspawn.com/lobby> — all 3 content chunks, read 01:57–02:00 UTC.
- <https://play.hotspawn.com/cs2-pickems> — all 3 content chunks, read 02:00–02:02 UTC.

Lobby's own counts at capture: header **"68 matches this week"**, CS2 tier filter **"All tiers (89)"
(B 25 · C 60 · S 4)**, week reset countdown **"Resets in 4d 22h"** (week 2026-10-12 → 2026-10-18 per
the model snapshot's `pickem_week`). The 68-vs-89 gap is Hotspawn's own header vs its own filter and
is carried as flag **U-F-6** (previously FL-20/FL-13 elsewhere; unchanged).

**Open CS2 fixtures listed on the live pages: 28** (Oct 14: 13 · Oct 15: 8 · Oct 16: 7). Time zone of
the rendered listing is UTC−4 (verified: 9z vs Aurora renders "04:30", its EGW page carries
"10:30" in UTC+2 and a countdown to 08:30 UTC — same instant). Kickoffs below are UTC.

| # | Fixture ID | Kickoff (UTC) | Teams | Tournament | Tier | Per-match Hotspawn URL present | Source |
|---|------------|---------------|-------|-------------|------|-------------------------------|--------|
| 1 | 1079621 | 2026-10-14 08:00 | Gothic vs Lavked | CCT Europe 2026 Series #11 | B | [yes](https://www.hotspawn.com/matches/gothic-vs-lavked-cct-europe-2026-series-11-1079621) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 2 | 1081111 | 2026-10-14 08:00 | Enjoy vs B8 Academy | CCT Europe 2026 Series #12 Play-In | C | **no** (null permalink) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 3 | 1080176 | 2026-10-14 08:30 | 9z vs Aurora | Thunderpick World Championship 2026 | S | [yes](https://www.hotspawn.com/matches/9z-vs-aurora-thunderpick-world-championship-2026-1080176) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 4 | 1079438 | 2026-10-14 10:00 | Astralis vs Sashi | Stake Pulse Beat III | B | [yes](https://www.hotspawn.com/matches/astralis-vs-sashi-stake-pulse-beat-iii-1079438) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 5 | 1079439 | 2026-10-14 10:00 | HOTU vs Fnatic | Stake Pulse Beat III | B | [yes](https://www.hotspawn.com/matches/hotu-vs-fnatic-stake-pulse-beat-iii-1079439) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 6 | 1081112 | 2026-10-14 11:00 | Banda chuya vs 6666 | CCT Europe 2026 Series #12 Play-In | C | **no** (null permalink) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 7 | 1079622 | 2026-10-14 11:00 | ex-RUSTEC vs mellren | CCT Europe 2026 Series #11 | B | [yes](https://www.hotspawn.com/matches/ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 8 | 1080177 | 2026-10-14 11:00 | Falcons vs Ninjas in Pyjamas | Thunderpick World Championship 2026 | S | [yes](https://www.hotspawn.com/matches/falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026-1080177) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 9 | 1080178 | 2026-10-14 13:30 | Legacy vs PARIVISION | Thunderpick World Championship 2026 | S | [yes](https://www.hotspawn.com/matches/legacy-vs-parivision-thunderpick-world-championship-2026-1080178) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 10 | 1081113 | 2026-10-14 14:00 | Ryvex vs PCIFIC | CCT Europe 2026 Series #12 Play-In | C | **no** (null permalink) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 11 | 1079623 | 2026-10-14 14:00 | G2 Ares vs The Last Resort | CCT Europe 2026 Series #11 | B | [yes](https://www.hotspawn.com/matches/g2-ares-vs-the-last-resort-cct-europe-2026-series-11-1079623) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 12 | 1080179 | 2026-10-14 16:00 | FURIA vs BetBoom | Thunderpick World Championship 2026 | S | [yes](https://www.hotspawn.com/matches/furia-vs-betboom-thunderpick-world-championship-2026-1080179) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 13 | 1079624 | 2026-10-14 17:00 | FORZE Reload vs LFO 10 | CCT Europe 2026 Series #11 | B | [yes](https://www.hotspawn.com/matches/forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 14 | 1080279 | 2026-10-15 08:00 | WROTBERRY vs EAC | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/wrotberry-vs-eac-elisa-breakout-series-2-1080279) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 15 | 1079440 | 2026-10-15 10:00 | MIBR vs BC.Game | Stake Pulse Beat III | B | [yes](https://www.hotspawn.com/matches/mibr-vs-bc-game-stake-pulse-beat-iii-1079440) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 16 | 1079442 | 2026-10-15 10:00 | Heroic vs Envy | Stake Pulse Beat III | B | [yes](https://www.hotspawn.com/matches/heroic-vs-envy-stake-pulse-beat-iii-1079442) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 17 | 1080280 | 2026-10-15 10:00 | ENCE vs BOJONG | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/ence-vs-bojong-elisa-breakout-series-2-1080280) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 18 | 1080281 | 2026-10-15 12:00 | WROTBERRY vs ENCE | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/wrotberry-vs-ence-elisa-breakout-series-2-1080281) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 19 | 1080282 | 2026-10-15 14:00 | EAC vs BOJONG | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/eac-vs-bojong-elisa-breakout-series-2-1080282) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 20 | 1080283 | 2026-10-15 16:00 | WROTBERRY vs BOJONG | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/wrotberry-vs-bojong-elisa-breakout-series-2-1080283) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 21 | 1080284 | 2026-10-15 18:00 | EAC vs ENCE | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/eac-vs-ence-elisa-breakout-series-2-1080284) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 22 | 1080285 | 2026-10-16 08:00 | Voca vs Phantom | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/voca-vs-phantom-elisa-breakout-series-2-1080285) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 23 | 1080286 | 2026-10-16 10:00 | HAVU vs RoundsGG | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/havu-vs-roundsgg-elisa-breakout-series-2-1080286) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 24 | 1080287 | 2026-10-16 12:00 | Voca vs HAVU | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/voca-vs-havu-elisa-breakout-series-2-1080287) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 25 | 1081120 | 2026-10-16 14:00 | mellren vs Privateer | CCT Europe 2026 Series #12 Play-In | C | **no** (null permalink) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 26 | 1080288 | 2026-10-16 14:00 | Phantom vs RoundsGG | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/phantom-vs-roundsgg-elisa-breakout-series-2-1080288) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 27 | 1080289 | 2026-10-16 16:00 | RoundsGG vs Voca | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/roundsgg-vs-voca-elisa-breakout-series-2-1080289) | [lobby](https://play.hotspawn.com/cs2-pickems) |
| 28 | 1080290 | 2026-10-16 18:00 | Phantom vs HAVU | Elisa BreakOut Series #2 | C | [yes](https://www.hotspawn.com/matches/phantom-vs-havu-elisa-breakout-series-2-1080290) | [lobby](https://play.hotspawn.com/cs2-pickems) |

Not open at capture (documented elsewhere): `1079546` Zomblers vs Overtake Sector — its lock passed
(00:54Z) and EGamersWorld showed it LIVE at 01:40Z; `arena/08031d30` excluded it from the open list
with evidence ([their row](https://buffedlizard55-lab.github.io/MaltaProj1/open-slate/flagged.html)).
My capture at 01:57–02:02Z also no longer lists it. Agreement between two independent reads.

## 2. Coverage of the published boards (live GitHub Pages, read 02:01–02:05 UTC)

| Board (live page) | Owner (session) | Open-slate coverage at capture | Row source links | Status |
|---|---|---|---|---|
| [open-slate/](https://buffedlizard55-lab.github.io/MaltaProj1/open-slate/) | 08031d30 (PRs #71/#72) | **28/28**, every fixture has both teams' win %, an explicit PICK, and basis labels (external vs own line) | every row: Hotspawn lobby + fixture ID (24/28 also a per-match page); every priced row: EGW match-page link + read time; own-line rows state their model | current (reads 01:41–01:58Z) |
| [model/](https://buffedlizard55-lab.github.io/MaltaProj1/model/) | 91eff436 → repair by a1db82b7 (PR #75 merged during this sweep) | at first read: snapshot dated **2026-10-13T18:45:29Z** (86 fixtures, 27 in-week rows); **post-merge re-check 02:06Z (cache-buster read): refreshed to `fetched 2026-10-14T02:00:25Z`, 89 fixtures / 30 in-week rows / 25 of 30 in-week rows with own line** — see U-F-4 | every row: Hotspawn fixture (or Pick'em page when the payload has no permalink) + Valve VRS `#L` deep links + HLTV team links + market source where present; summary table now has a per-row Sources column | current after PR #75 (verified live) |
| [slate/](https://buffedlizard55-lab.github.io/MaltaProj1/slate/) | 180a42a0 → hardening by a9a0c2f1 (PR #73 open at capture) | whole-pickle board (388 fixtures, all titles; 262 open at its 23:54Z capture) — superset covering the 28 | per-row provenance labels (who read the price and when) | its own refresh cadence is being rebuilt in PR #73 |
| `picks/`, `today/`, `live/`, `docs/`, `board/`, `hub.html`, `assurance/`, `site/`, `mobile/`, `verify/`, `winboard/`, `status/` | prior sessions (closed) | Oct-13-era snapshots of overlapping scopes, preserved on purpose (see `COORDINATION.md` canonical structure) | per-row links where their audits recorded them (see `docs/audit.html`, `reviews/`) | historical; not re-verified today |

**Coverage verdict:** every one of the 28 currently open CS2 Pick'em fixtures on Hotspawn has a pick
or a documented no-pick with win probabilities on the live `open-slate/` board, and each of those rows
carries a source link to an official page (Hotspawn lobby at minimum; a per-match Hotspawn page and/or
an external odds source where one exists). One fixture (13: FORZE Reload vs LFO 10) is a **documented
no-pick**: no usable external market (EGW's 1.80/1.80 pair is a placeholder, not a market) and LFO 10
has no official VRS rating — so no probability is invented. This is the behaviour the brief demands
(blank + flag, never inferred).

## 3. Line-by-line checks performed in this session (with links)

1. **Fixture identity, all 28 rows** — teams, tournament, tier, kickoff and lock behaviour re-read from
   the official lobby pages (01:57–02:02Z) and compared to `data/08031d30/hotspawn_open_cs2.csv`
   (independent read at 01:40Z): **28/28 agree, 0 mismatches**. Lock countdowns sampled at capture
   (e.g. Enjoy vs B8 Academy "Locks in 05:56:28" at 01:57Z → lock ≈ 07:54Z = kickoff 08:00Z − 6 min,
   consistent with Hotspawn's `lock_offset_sec: 360`) match the CSV's `lock_utc` values.
2. **External price spot-check** — [open-slate's 9z vs Aurora row](https://buffedlizard55-lab.github.io/MaltaProj1/open-slate/)
   quotes EGW `3.870 / 1.200` (de-vig 23.7/76.3), read 01:41–01:58Z. My independent re-read of that
   exact [EGW match page](https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb)
   at 02:05Z shows `3.3 / 1.26` (de-vig 27.6/72.4) — intra-hour drift, see U-F-2. The page's own listing
   times ("14.10.26 10:30" UTC+2 display, countdown to 08:30 UTC, "Bo3") agree with Hotspawn's kickoff
   (08:30 UTC) and confirm the series format as best-of-3. Pick (Aurora) unchanged under both readings.
3. **Source-link audit of the open-slate rows** — 28/28 rows carry the official lobby link and fixture
   ID; 24/28 additionally carry a per-match `hotspawn.com/matches/...` page; 25/28 carry an external
   odds-page link where a price is quoted (3 rows quote no price because EGW showed only its placeholder).
   The 4 rows without a per-match page are flagged U-F-1 (Hotspawn's own payload has a `null` permalink
   for them — same defect that broke the scheduled model job, see §4).
4. **Probabilities** — each open-slate row shows both teams' percentages summing to 100 (spot-arithmetic
   checked on all 28 rows from the fetched page text) and an explicit favourite pick; the FORZE–LFO 10
   row shows no probability and no pick, with the reason attached. No Hotspawn crowd percentage appears
   in any probability column (policy check re-run on the fetched text: crowd % appears only in Hotspawn's
   own UI, never in the boards' probability fields).

## 4. Automation health ("regularly check for updates… no manual input")

Evidence: GitHub Actions API reads at 01:41Z / 01:56Z / 02:0x UTC (run list below), plus
[`reviews/a1db82b7-verification.md` §2](a1db82b7-verification.md) (per-workflow schedule table) and
[`reviews/08031d30-repo-review.md` E-1/E-2](08031d30-repo-review.md).

| Workflow | Cadence (cron) | Observed firing on 2026-10-14 | Health at end of this sweep |
|---|---|---|---|
| `model-91eff436.yml` (own lines) | `17 */3 * * *` | fired 00:20Z → **FAILED** at Tests (null-permalink ingest bug: `str(None)` reached `hotspawn_url`, test `test_every_published_value_has_official_source` correctly blocked publication) | root-caused & fixed by `arena/a1db82b7` (PR [#75](https://github.com/buffedlizard55-lab/MaltaProj1/pull/75), regression tests included; green run [38497833026](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38497833026) published 89 rows / 57 own lines) |
| `slate-180a42a0.yml` (full slate) | `41 */3 * * *` | 00:41Z slot did not appear by 01:40Z (miss/delay) | being rebuilt by `arena/a9a0c2f1` as an hourly gated refresh (PR [#73](https://github.com/buffedlizard55-lab/MaltaProj1/pull/73)) |
| `release-assurance-91e444dd.yml` | `9,39 * * * *` | fired ~01:5xZ (delayed vs its 01:39Z slot) | green when it fires |
| `refresh-b90700c6.yml` (today/) | `23 */3 * * *` | fired 23:27Z (12-min delay on a 23:15Z-equivalent slot — see run 38484323576) | green when it fires |
| `update.yml` (linescope dashboard) | `17,47 * * * *` | 00:17/00:47/01:17 slots not observed in the run list read at 01:41Z | **misses recorded (U-F-5); no active owner** — its claim (4f599d7c) is stale; remediation request left to the integration owner |
| `live-459ff624.yml` (live/) | `37 * * * *` | hourly slots not observed in the 01:41Z read | same as above |

Honest summary: GitHub's scheduler has been **delaying/queuing scheduled runs** today (the same pattern
`arena/a1db82b7` quantified: 3 scheduled runs fired against ~18 due slots between 23:00–01:55Z). Push-
and dispatch-triggered runs work reliably (every PR and push above produced runs within seconds). The
repo-side mitigations in flight — model catch-up chain (PR #75) and the slate hourly gated refresh
(PR #73) — make each run self-healing when it finally fires. My session's duplicate diagnostic workflow
(never merged) was deleted at integration; `arena/a1db82b7`'s diagnostic supersedes it.

## Irregularities (flagged, non-blocking)

| ID | Item | Evidence | Disposition |
|---|------|----------|-------------|
| U-F-1 | 4 open fixtures have **no per-match Hotspawn URL**: 1081111 Enjoy–B8 Academy, 1081112 Banda chuya–6666, 1081113 Ryvex–PCIFIC, 1081120 mellren–Privateer | the lobby's own "View Match" element is absent for these rows on both `/lobby` and `/cs2-pickems` at 01:57–02:02Z; Hotspawn's TransferState carries a `null` permalink (this is what broke the 00:20Z model run) | rows cite the lobby page + fixture ID instead; never invented. Same rows appear (with the same IDs) on `open-slate/` |
| U-F-2 | External price drift on 9z vs Aurora within ~10 minutes: EGW 3.87/1.20 (read 01:41–01:58Z on open-slate) → 3.3/1.26 (my read 02:05Z, de-vig 27.6/72.4, matching the OddsPortal second read 27.5/72.5 on the same row) | links in §3.2 | both readings timestamped and published as-is; pick stable; no number overwritten |
| U-F-3 | The two own-line models disagree in magnitude (and sometimes near the 50% line in direction-sensitive rows): e.g. Gothic–Lavked own line Lavked 71.2% (`open-slate/`, uncalibrated Elo(400) on VRS/HLTV points, BO3 assumed) vs 60.2% (`model/`, market-calibrated VRS slope); G2 Ares–TLR pick flips between boards because `open-slate/` follows the external line while `model/` follows its own line | [open-slate/](https://buffedlizard55-lab.github.io/MaltaProj1/open-slate/) · [model/](https://buffedlizard55-lab.github.io/MaltaProj1/model/) | each board labels its own basis; nothing reconciled silently. Reviewer's note: treat each board's pick as model-specific; `open-slate/` prefers the market where one exists |
| U-F-4 | Live `model/` page at first read still served the 2026-10-13T18:45:29Z snapshot ("86 CS2 fixtures") while the live payload carries 89 | [model/](https://buffedlizard55-lab.github.io/MaltaProj1/model/) header vs lobby filter "All tiers (89)" | **RESOLVED during this sweep.** PR #75 merged (a5317da) and the model workflow re-ran green on `main` (run [38498732278](https://github.com/buffedlizard55-lab/MaltaProj1/actions/runs/38498732278), commit `c1aee72`); live page re-checked at 02:06Z with a cache-buster (CDN had served the old artifact to plain reads): now `fetched 2026-10-14T02:00:25Z`, 89 fixtures, 30 in-week rows, own line for every row with two official ratings. CDN cache lag on plain reads is itself noted for awareness |
| U-F-5 | Scheduled slots for `update.yml` and `live-459ff624.yml` not observed in the Actions run list read at 01:41Z (see §4) | [Actions runs](https://github.com/buffedlizard55-lab/MaltaProj1/actions) | needs-review item for the integration owner; their owning sessions are stale; non-blocking per brief |
| U-F-6 | Hotspawn's own header ("68 matches this week") disagrees with its own filter ("All tiers (89)") | lobby page, both `/lobby` and `/cs2-pickems`, 01:57–02:02Z | Hotspawn-side inconsistency; the repo publishes the parsed fixture set, not the header number |
| U-F-7 | Stale open PR [#54](https://github.com/buffedlizard55-lab/MaltaProj1/pull/54) (session arena/9920c263, open since 2026-10-13 22:47Z, previously reported DIRTY) has not been merged or closed | `gh pr list` at 01:56Z | disposition requested from the integration owner (`arena/a9a0c2f1` H-03); not touched by this session |
| U-F-8 | FORZE Reload vs LFO 10 (1079624) has **no pick and no probability** on any current board | [open-slate/](https://buffedlizard55-lab.github.io/MaltaProj1/open-slate/) row + [model/](https://buffedlizard55-lab.github.io/MaltaProj1/model/) "LFO 10: NOT IN VRS" | correct behaviour under the no-inference rule; left blank + flagged |

## Verification statement

- Every row of §1 was re-read from the official Hotspawn pages in this session; every comparison in
  §2–§3 names the page it was read from. Nothing in this report is filled in by inference; blanks in
  the published boards remain blanks and are listed above rather than estimated.
- Hotspawn crowd percentages were observed on the official pages (they change minute to minute, e.g.
  Gothic–Lavked 17%→18% during my own two captures) and deliberately **not** recorded as probabilities.
- This session edited no other session's files. Requests to other owners are logged in
  `COORDINATION.md` under the session `arena/374a5a90` section.
