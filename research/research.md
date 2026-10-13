# Public-source reverse engineering and verification

Session: `4f599d7c` · 2026-10-13 UTC · repository `buffedlizard55-lab/MaltaProj1`.

## Deliverable and scope

The supplemental, evidence-first site is **[Linescope dashboard](https://buffedlizard55-lab.github.io/MaltaProj1/dashboard/)**. It does not overwrite the root hub or other sessions' models/pages. It provides overview, all rendered matches, CS2, LoL, external markets, full captured source-state inventory, sources/evidence, **Flagged for Review**, methodology and repository audit.

Hotspawn supplies fixture identity/eligibility metadata only. Its pick percentages, score/points multipliers, streaks and ratings are not probability inputs. The normalized evidence discards crowd-pick fields entirely. Each new data-table row links an official source; unconfirmed fields are null/blank, not a guess, a prior, an outright conversion or a 50/50 fallback.

## Official sources inspected

| Official source | Verified observation / purpose | Review link |
|---|---|---|
| Hotspawn general lobby | Public Angular SSR; fixture state and rendered card identity | https://play.hotspawn.com/lobby |
| Hotspawn CS2 | Separate CS2 board, state, filter/rendered counts | https://play.hotspawn.com/cs2-pickems |
| Hotspawn LoL | LoL is part of the full scope, not a CS2-only inventory | https://play.hotspawn.com/lol-pickems |
| Hotspawn sponsored board | Additional rendered identities deduplicated by actual provider ID | https://play.hotspawn.com/thp-pickems |
| Hotspawn rules | Published lock-time sentence, compared with explicit backend metadata | https://play.hotspawn.com/how-it-works |
| Hotspawn frontend script | Observed `getMatchStartMs` and `mapFixtureToPickem`; confirms numeric milliseconds and explains UI fallbacks we reject | https://play.hotspawn.com/main-YNSCYNCE.js |
| Pinnacle public highlights | Actual primary-bookmaker prices observed through the normal website; no account/login interaction | https://www.pinnacle.com/en/esports/matchups/highlights/ |
| Pinnacle CS2 / LoL games | Wider public coverage than homepage highlights | https://www.pinnacle.com/en/esports/games/cs2/matchups/ · https://www.pinnacle.com/en/esports/games/league-of-legends/matchups/ |
| Pinnacle publisher API policy | Licensed API policy re-read from its official GitHub README; not an excuse to access a restricted API | https://github.com/pinnacleapi/pinnacleapi-documentation |
| Thunderpick | HTTP403 to the runner; prices not admitted and no challenge bypass | https://thunderpick.io/esports/cs2-betting |
| HLTV | HTTP403 to the runner; reference-only in this dataset, no rank/pick probabilities substituted | https://www.hltv.org/matches |

Source status is timestamped. HTTP200 alone does **not** verify an odds value. The current snapshot and Sources page contain the actual retrieval observations; they supersede these historical notes.

## Hotspawn: exact public interface, not guessed pagination

The site is Angular, not assumed Next.js. Public HTML contains `<script id="ng-state" type="application/json">`. Its HTTP transfer cache has:

- fixture cache entries with `u` ending `/api/v1/fixtures`, `s: 200`, and `b` arrays;
- fixture IDs, `sport_alias`, both participant names/IDs, competition metadata, source status, explicit `scheduled_start_time`, `lock_time` and `lock_offset_sec`;
- an ordinary frontend-used permalink response with a privileged-looking `/api/v1/admin/gamification/fixtures/permalinks` path. We read the publicly delivered state and actual links; we do not enumerate admin routes or make authenticated requests;
- unrelated leaderboard/account entries, which the production allowlist does **not** retain.

`collector/hotspawn.py` reads the full fixture arrays, separately enumerates every rendered `<app-pickem-vs-card>` and official match hyperlink, and checks DOM names/competition against source state. It stores all distinct retained source-state records on **Source inventory**; only rendered, source-matched cards populate the board pages. Missing names remain blank and the row is retained; an actual DOM/state identity conflict is flagged rather than auto-filled.

The observed frontend has `getMatchStartMs(t)`: `Number(t.startsAt)` is returned directly when finite and positive; otherwise it tries `new Date(...)`. `mapFixtureToPickem` assigns `scheduled_start_time ?? start_time ?? new Date().toISOString()`. Our implementation does **not** copy the last two fallbacks when the explicit schedule is absent. Thirteen-digit scheduled milliseconds are converted to timezone-aware UTC. No local wall clock, countdown approximation, five-minute reconstruction, or guessed timezone is used.

### Counts and irregularities

The verified 19:17:27 UTC snapshot captured **258** distinct rendered board fixtures (**27 CS2 / 231 LoL**), **380** distinct fixture-state records, **14** eligible primary moneylines, and **8** exact fixture matches with calculated lines. **250** fixture lines were intentionally blank. This is a timestamped observation, not a promise that 258 equals every eligible match in the site's weekly counter.

- Filter totals, weekly counters, rendered cards and cached state refer to different/unreconciled populations. Coverage remains **partial**; a full-list claim is withheld.
- Older records still have `status: scheduled` although their explicit start is in the past. No result or present eligibility is inferred.
- `best_of` / `series_format` are absent on many official records. They stay null/blank, even when another source supplies a format.
- The published rule specifies five minutes (300 seconds), but captured explicit fixture metadata includes 360-second offsets. Actual source schedules and locks are retained; the conflict is flagged.
- Normalized primary source data does not include crowd percentages or leaderboard/contact values.

## Pinnacle: normal public browsing, no licensed-API access

The site itself requests guest event/market JSON under `guest.api.arcadia.pinnacle.com`. The discovery browser observed public GETs such as:

- `/0.1/sports/12/matchups/highlighted`
- `/0.1/sports/12/markets/highlighted/straight?primaryOnly=false`
- game/league matchup and straight-market responses encountered while visiting the official CS2 and LoL pages.

The collector visits those official pages in ordinary Playwright Chromium. It captures only GET responses actually observed in the page, with HTTP200, on the exact guest host and event/market path allowlist. It never calls the closed `api.pinnacle.com` service, copies request headers/API keys, logs in, visits wallets/KYC/accounts, submits a pick/bet, or bypasses a challenge. Human review uses actual event hyperlinks extracted from the public DOM; no deep-link slug is invented. Guest URLs may not be independently readable outside their normal website context; the public site links and retained JSON provide the review path.

Admitted records require explicit:

1. supported esports game from the publisher's league label and `sport.id: 12`;
2. whole-match parent event (`type: matchup`, explicit null parent fields), two named home/away participants, UTC `startTime`, `isLive: false`, `status: pending`;
3. `type: moneyline`, `period: 0`, `isAlternate: false`, `status: open`;
4. exactly two home/away prices and a future cutoff/start.

Map/round markets, totals, handicaps, outrights, draws, alternate/live/closed/started records are excluded. Native integer American prices are explicitly converted to decimal, rather than pretending the website's rounded decimal display is an exact source number. This conversion was checked against the ordinary site's visible Decimal Odds prices.

Repeated responses are ordered by precise UTC retrieval plus an explicit capture sequence. The retained ledger preserves the same ordering. A later suspended/closed primary market invalidates an earlier open price; it is never resurrected as the latest quote. Publisher last-change time is not exposed/confirmed, so `source_published_at` remains null and is flagged; `observed_at` means our real retrieval observation, not a bookmaker publication timestamp or a guaranteed executable offer.

## Matching and independent calculations

Matching is exact supported game + team pair + UTC start, allowing only Unicode normalization, case and whitespace. Reversed home/away order is handled explicitly. Fuzzy/abbreviated team aliases are not guessed. Multiple eligible event identities from one book are ambiguous and excluded. Competition labels are retained separately rather than overwritten or silently canonicalized.

Observed unresolved examples include `PARIVISION` / `PVISION`, `BetBoom` / `BB Team`, and `Anubis Gaming` / `Anubis`. A same-time event sharing only one exact team name is a review clue, not verified identity. Those fixture lines remain blank, with both official review links.

For each eligible bookmaker with decimal sides `d_A`, `d_B`:

```
q_A = 1 / d_A
q_B = 1 / d_B
p_A = q_A / (q_A + q_B)
p_B = q_B / (q_A + q_B)
```

Distinct books receive equal weight, not one weight per duplicated quote. Our fair decimal line is `1 / mean(p)`. Current admitted inputs are from one primary book; the page clearly shows one independent book. This is a **calculated market estimate**, not an empirically calibrated true winning probability, bookmaker offer, arbitrage promise, or wagering recommendation. No unsupported rank/Elo priors are used when a price is unavailable.

A quote must be observed no more than 3,600 seconds ago and before the scheduled match. The browser hides expired quote/derived values, preserves review links and warns about stale fixture inventory; it does not turn an unknown current coverage value into a made-up zero. A new snapshot is not re-dated if collection/validation fails.

## Privacy correction and retention

Initial broad inspection captured an unrelated public leaderboard response containing personal-contact fields. No values are repeated here. The temporary archive was removed and the session-owned return commit amended. The four superseded broad Actions artifacts were successfully deleted with the scoped Actions token; API listing independently confirmed none remained. The original broad collector is retired.

Production evidence is either an explicitly **privacy-filtered fixture-only transfer-state projection**, a minimal policy sentence, actual public event hyperlinks, or unchanged allowed bookmaker event/market JSON. SHA-256 applies to retained bytes; the fixture projection also records the full source-response hash without republishing the unrelated original HTML. Working-tree evidence is pruned to current referenced files, and Actions artifacts retain seven days. Ignored tooling/screenshots/raw research are not deliverables or probability inputs.

## Autonomous refresh and legacy GitHub Pages

Pages remains `main:/` with the repository's existing legacy setup. No unsupported administrative switch to custom Actions Pages is made.

`.github/workflows/update.yml` schedules public collection every 30 minutes (GitHub may delay cron). Every run tests parsers/math, collects sources, rechecks raw field pointers/content hashes, builds the site, checks every internal link and official-link requirement, then pushes **only** `arena/4f599d7c-maltaproj1`.

The static Pages client reads its view's verified compiled HTML from GitHub's official public contents API, with a public blob fallback for larger files. It imports only inert DOM, drops scripts/event-handler content, keeps existing CSS/JavaScript, preserves filters and rewrites current evidence links to the actual session-branch files. No remote JavaScript is evaluated and no token is stored in the browser. Five-minute checks, four-minute per-view session caching and one-minute expiry checks limit quota use. Rate/access failures retain the dated snapshot with a visible status; old values are not made fresh.

**Keep that session branch.** Repository auto-deletion after merge was verified false. There is no user data-entry step, funded-account credential, manual fixture patch, manual review gate, or routine merge requirement for refresh.

## Repository review and verification

- [Combined line/file audit](repository-audit.md): all tracked text lines read; file hashes, syntax/data shape and internal-target checks. Parallel sports assertions are not automatically certified.
- [Machine file ledger](repository-audit.json): exact paths, line counts and review links; no detected contact values copied.
- `scripts/validate.py`: every populated snapshot field and derived result rechecked against its own retained primary source / exact calculation, plus every dashboard internal page/asset/download/anchor and source-linked table row.
- 37 offline tests passed at this checkpoint. Actual Chromium153 checks passed at1440px/390px: real counts, search, query persistence, game/coverage filters, accessible sorting, empty states, CSV, complete captured source-state rows, expiry, mobile menu/Escape and no horizontal page overflow/browser errors.
- Other root/docs models and CSVs remain read-only, with explicit review boundaries and links. No source claim is silently upgraded by merging another session.

## Reproduce

```sh
python -m pip install -r requirements.txt
python -m playwright install --with-deps chromium
python -m unittest discover -s tests -v
# Live collection requires normal public internet, available on the Actions runner:
python scripts/collect.py
python scripts/build_site.py
python scripts/validate.py
python research/audit_repository.py
```

The sandbox's outbound host restriction is why live HTTP/browser collection runs on GitHub Actions, not a hidden proxy or fabricated local fixture file. PR/merge/deployment results are recorded in `COORDINATION.md` and the release record when independently confirmed.
