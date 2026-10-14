# Verification — session 57dbfba4 (gap-resolution), 2026-10-14

## Claim
From `console/data/picks.csv` (snapshot 2026-10-14T04:23:08Z, 28 open): 25 rows resolve on the featured
outside-market route; exactly 3 do not: `1081112` Banda chuya vs 6666 (own-line), `1081120` mellren vs
Privateer (own-line), `1079624` FORZE Reload vs LFO 10 (research). `gap-resolution/` publishes those 3
separately, with the research ladder and limitations, and an executive summary linking to the updated
picks list. No probability was created in this session — every % is copied from the console board and
asserted by `tests/test_57dbfba4.py` (probs sum to 100, pick ∈ teams, HLTV + rating source on every row).

## Research ladder actually performed (2026-10-14, in order)
1. **HLTV first** — match pages 2399462 / 2399471 / 2399301 (linked per row) confirm fixture, teams and BO3;
   HLTV event 9442 lists FORZE Reload #90 / LFO 10 #170; HLTV team 13882 is 6666.
   Sources: https://www.hltv.org/matches/2399462/banda-chuya-vs-6666-cct-2026-europe-series-12-closed-qualifier ·
   https://www.hltv.org/matches/2399471/mellren-vs-privateer-cct-2026-europe-series-12-closed-qualifier ·
   https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11 ·
   https://www.hltv.org/events/9442/cct-2026-europe-series-11
2. **Esports books / betting lines** — EGamersWorld match pages for Banda chuya vs 6666 and mellren vs
   Privateer Gaming confirm date/time/BO3 but show only the 1.8 placeholder (no two-sided price);
   FORZE Reload's EGW page has a blank opponent + 1.8/1.8. No Pinnacle/Thunderpick quote for these fixtures
   exists in the committed board captures. Placeholders were rejected, not de-vigged.
   Sources: https://egamersworld.com/counterstrike/match/4kY9VAmiEg/banda-chuya-vs-6666-JdPgKgp5y ·
   https://egamersworld.com/counterstrike/match/4kY9VAmiEg/mellren-vs-privateer-gaming-ASh_MyDBS
3. **Polymarket (live read of the CCT Europe tab, 2026-10-14, all 3 chunks)** — 10 markets listed;
   Banda chuya vs 6666 is not among them; FORZE Reload is listed vs **Sökerorg** (opponent conflict → rejected);
   mellren vs Privateer Gaming is listed at 94¢/93¢ with **$0.00 volume** (untraded placeholder → rejected).
   Source: https://polymarket.com/esports/cs2/cct-europe
4. **Own originated line (fallback, labelled)** — Valve VRS 2026-10-05 + HLTV ranking, k=0.4568, BO3, as
   computed by the consolidated board (`console/data/picks.csv`, per-row GitHub line links). LFO 10 is absent
   from the VRS file, so 1079624 stays a flagged RESEARCH line (PF-02).

## Irregularities flagged (published on gap-resolution/flagged.html, U-01…U-07)
Opponent conflict (U-03), $0-volume placeholders (U-02), unrated team (U-04), ratings dated 2026-10-05 (U-05),
name variants (U-06). None block publication; no values were inferred to fill them.

## Checks
`python3 scripts/57dbfba4_build.py` OK (fail-closed invariants) · `tests/test_57dbfba4.py` 5/5 ·
repo link audit run before PR. Refresh: `gap-resolution-57dbfba4.yml` every 4 h (within the 4–8 h requirement),
console board hourly; a failed run publishes nothing.
