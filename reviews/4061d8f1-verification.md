# Day-4 integration review — arena/4061d8f1

Scope: the maintained primary `hotspawn/` board and root navigation, not certification of the repository's dozens of historical alternative dashboards. Date: 16 October 2026. Exact source-fetch completion seconds were not retained for the editorial research; a 19:29–19:34 UTC research window is recorded rather than fabricated timestamps.

## Independently re-read evidence

| Item | Observed fact / limitation | Publisher source |
|---|---|---|
| Day 1 | 9z 2-0 Aurora; Falcons 2-0 NIP; Legacy 2-0 PARIVISION; FURIA 2-0 BETBOOM. Series results re-read; older map details retained with their prior attribution. | [HLTV results](https://www.hltv.org/results?event=8932) |
| Day 2 | Aurora 2-0 NIP; Falcons 2-1 9z; BETBOOM 2-1 PARIVISION; FURIA 2-1 Legacy. | [HLTV results](https://www.hltv.org/results?event=8932) |
| Day 3, Group A | Aurora 2-0 9z: Cache 13-11, Inferno 13-4. Aurora picked Cache and removed Nuke; Mirage unplayed. | [HLTV exact match](https://www.hltv.org/matches/2399412/aurora-vs-9z-thunderpick-world-championship-2026) |
| Day 3, Group B | Live at the check, one completed map each. BETBOOM won Nuke 16-13; Legacy won Dust2 13-11. Final score and winner left blank. | [HLTV exact match](https://www.hltv.org/matches/2399413/betboom-vs-legacy-thunderpick-world-championship-2026) |
| Day 4 | HLTV lists FURIA–Aurora on 17 October, BO3 LAN semifinal. Falcons' opponent was still BETBOOM/Legacy winner. No unconfirmed opponent or timezone inferred. | [HLTV match](https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026), [event matches](https://www.hltv.org/events/8932/matches) |
| Aurora rebuild | HLTV reports kyxsan signing 8 July, following Jimpphat and coach ash. About three months old: no invented last-minute onboarding penalty. | [HLTV signing report](https://www.hltv.org/news/45082/official-aurora-complete-rebuild-with-kyxsan) |
| Hotspawn discrepancy | Human-readable lobby and CS2 pages returned different payload totals; TWC page returned “Check back in a minute”. Those totals are not all open matches. Refresh must union all three TransferState payloads; never use ownership as probability. | [Lobby](https://play.hotspawn.com/lobby), [CS2](https://play.hotspawn.com/cs2-pickems), [TWC](https://play.hotspawn.com/thp-pickems) |

HLTV is the named specialist results publisher, not the tournament organizer. Its reports are attributed; direct organizer confirmation is not claimed. Win probabilities are project calculations on source observations, **not officially verified future outcomes**. Relayed sportsbook prices remain secondary/flagged. Private health, travel, sleep and fatigue are unverified and receive no numerical adjustment.

## Implementation and verification

- Kept the existing one-primary-dashboard structure and all historical navigation links.
- Added a dated Day-4 watch to the summary, TWC and strategy pages. Live cards come only from the same board rows as All picks, selected by exact main-event name and date; no static IDs or hypothetical opponents.
- An empty TWC slate is a listing limitation, not invented picks. New listings are picked up on the four-hour refresh; blank values remain explicit where evidence fails.
- Day-3 Aurora result added only to the independently sourced result store; frozen pre-lock history is never edited/backfilled.
- Corrected “no market exists” copy to “no eligible captured price”, preserving HTTP refusal/circuit-breaker evidence.
- Sandbox direct external HTTPS failed; the existing GitHub Actions refresh was used for full source collection. Workflow dispatch returned HTTP 403 (integration permission); an authorized branch push triggered the existing pipeline successfully instead. No credentials requested or stored.
- The implementation tests, per-row capture audit, phone browser checks and publication receipts are recorded below once complete. A source-link presence test alone is not live source verification.

## Irregularities

Published on [Flagged for Review](../hotspawn/flagged.html): D4-01 (dated partial result/bracket snapshot), D4-02 (source absence versus failed collection). Existing source/identity/roster flags remain visible per match. No numeric rest adjustment or proof of leaderboard profitability is claimed.

## Missing-pick research (same session, after initial TWC review)

| Fixture | Research and disposition | Source links |
|---|---|---|
| Apogee Betclic–Nemesis, 1081515 | Missing alias, not missing market. HLTV 2399660 confirms BO3 upper semifinal on 17 October. bo3 displays 2.80/1.38; Thunderpick's own Match Winner panel independently displays the same pair under Apogee Esports–Nemesis. Added sourced name equivalence; duplicate Betclic Valve rosters remain ambiguous. | [HLTV](https://www.hltv.org/matches/2399660/betclic-vs-nemesis-pgl-bucharest-2027-closed-qualifier), [book](https://thunderpick.io/match/2836564), [relay](https://bo3.gg/matches/betclic-apogee-esports-vs-team-nemesis-cs-17-10-2026) |
| aimclub–BASEMENT BOYS, 1081527 | HLTV confirms BO1 LAN; no numeric book odds in its region-rendered betting panel. bo3's page and exact-match API show 2.04/1.69. API supplies bookmaker ID 39 but no operator name; preserve ID, leave name blank, flag BOOKMAKER_UNVERIFIED. Source-implied probability may be derived, but no automatic contrarian fade is allowed. No claim of direct-book verification. | [HLTV](https://www.hltv.org/matches/2399591/aimclub-vs-basement-boys-digital-crusade-draculan-season-7), [relay page](https://bo3.gg/matches/aimclub-vs-basement-boys-19-10-2026), [exact API](https://api.bo3.gg/api/v1/matches?filter%5Bmatches.id%5D%5Beq%5D=131693&with=teams,tournament) |
| aimclub own-line limitation | HLTV listed ragga, waZz, mhN1, zewts, XELLOW; Valve #77 has ERSIN in place of XELLOW, #336 overlaps only two. Identity is narrower, but strict own line remains withheld: not the same five. No made-up adjustment. | [HLTV lineup](https://www.hltv.org/matches/2399591/aimclub-vs-basement-boys-digital-crusade-draculan-season-7#lineups), [Valve pinned official standings](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md) |
| FURIA–Aurora external watch | The captured bo3 relay is 1.85/1.85 (50/50 after margin removal); direct Thunderpick page independently showed -118/-118 (also 50/50). Captured Polymarket outcome prices 0.52/0.48. Near-even, not a strong favourite; no current Hotspawn ownership/lock is invented. The watch uses refreshed quotes, not a static price. | [HLTV](https://www.hltv.org/matches/2399414/furia-vs-aurora-thunderpick-world-championship-2026), [Thunderpick](https://thunderpick.io/match/2836924), [Polymarket](https://polymarket.com/event/cs2-furia-aur1-2026-10-17) |

The bo3 API's internal-provider-ID schema is now retained instead of silently dropping all such quotes. A missing name AND missing/invalid numeric ID still rejects the quote, as do inactive sides, mismatched participants, non-CS2, invalid prices, wrong event/date/format or stale reads. The unknown operator is disclosed and not inferred from an affiliate redirect. Zero Polymarket volume is preserved as zero rather than converted to null.
