# Evidence snapshot schema v1

`data/snapshot/latest.json` is collected automatically, never maintained through a manual match/price form. All timestamps have explicit UTC/timezone information; precise observation timestamps keep microseconds. Null means unconfirmed and renders blank.

## Root

| Field | Meaning |
|---|---|
| `schema_version` | Supported contract version, currently1 |
| `generated_at`, `collection_started_at` | Actual collector UTC instants; not bookmaker publication time |
| `collection_run_url`, `collection_code_commit` | Actual Actions run and checked-out code reference when available |
| `coverage` | `complete`, `partial`, `unavailable` or `unverified`; page observations and explicit reconciliation checks |
| `matches` | Distinct source-matched rendered pick’em cards, both supported titles |
| `inventory` | Every retained distinct fixture-state record, including cached/historical entries; not a current-eligibility claim |
| `quotes` | Strictly eligible, externally observed primary-bookmaker whole-match moneylines |
| `sources` | Official links, purpose, actual access/observation status, policy links |
| `evidence` | Retained bytes, source URL, retrieval instant, content hash, capture sequence, locator metadata |
| `findings` | Review items with official links; unknown/flagged values do not block a structurally valid publication |
| `verification` | Source/calc checks and record counts; partial inventory is explicitly not certified complete |
| `automation` | Fixed branch and planned schedule/delivery, not a guarantee that GitHub cron runs exactly on time |

## Fixture rows

Provider `id`, game, both names/IDs, competition name/ID, source status, exact schedule and lock, `lock_offset_seconds`, tier/stage, and `best_of`/`series_format` are mapped only from their corresponding official fields. Missing names, timing or formats remain null. `source_url` is an actual official permalink or the actual official state page, never an invented slug. `evidence_id` plus `evidence_locator` (JSON Pointer) identifies the exact retained source record. `on_rendered_board`, `lobby_section` and `source_pages` record observed page membership, not a prediction/result.

`matches[].analysis` has only two states:

- `calculated`: referenced external inputs, complementary no-vig probabilities, reciprocal fair decimal odds, independent-book count, and a method label;
- `unverified`: no invented prior; probability/fair-price values are null and inputs empty.

Crowd picks, streaks, arbitrary rank transformations and Hotspawn point multipliers do not appear as analysis inputs. A past source start does not establish a winner/result.

## Primary quote rows

A quote retains actual bookmaker/event identity, game, native named sides, source league label, explicit UTC start, confirmed open/prematch state, and two-outcome whole-match semantics. `native_odds_a/b` are source values; `odds_a/b` are explicitly calculated American-to-decimal conversions. `source_published_at` is null unless actually exposed and confirmed; the current adapter does not fabricate it from market version or retrieval time.

`evidence_id/locator` references the raw market. `event_evidence_id/locator` references the raw event metadata. `observed_at` and `capture_sequence` are actual collector provenance, preserving repeated-response ordering. `source_url` is an actual observed event hyperlink or public page, and `api_url` is an actual browser-observed guest request—not a licensed endpoint, key or guessed route.

Only an eligible latest market is admitted. A later closed/suspended observation cancels an earlier open one. Exact game/pair/UTC matching allows reversal and harmless case/Unicode/whitespace normalization, not unconfirmed name aliases.

## Evidence

Evidence files are bounded `*.json.gz` objects with deterministic gzip headers. SHA-256 is checked on decompressed retained bytes. Filenames are basename-only; path traversal is rejected.

Kinds:

- `hotspawn_fixture_transfer_state`: explicitly privacy-filtered fixture cache/card/permalink projection; selected source fields unchanged, unrelated original state discarded;
- `pinnacle_matchups` / `pinnacle_markets`: unchanged allowed JSON captured through the public website;
- `pinnacle_observed_links`: actual esports DOM hyperlinks only;
- `official_policy_excerpt`: only the confirmed policy sentence.

HTTP200/source URL/retrieval instant are required for substantive evidence. The fixture projection records `source_response_sha256` separately because the unrelated original HTML is not republished. Personal-contact values, accounts, cookies, tokens, headers and crowd values are not retained. Old working-tree evidence not referenced by the current snapshot is pruned.

## Validation/publication gates

1. Required schema, unique identities and safe HTTPS links.
2. Actual primary origin, stored content hash, precise record locator and source-field equality for every populated normalized field.
3. Explicit supported game, two known outcomes, whole-match/open/prematch semantics; no live/map/draw/suspended or ambiguous substitute.
4. Recomputed no-vig arithmetic, input/reference counts and source matching at the snapshot calculation time.
5. Complete inventory claims require all positive reconciliations; partial/flagged data remains publishable as partial.
6. Every generated data row has an official-source link; every internal page, asset, download and anchor exists.
7. Runtime expiry and stale-source warnings hide values without re-dating the snapshot or inferring current zero coverage.

No field is filled simply because another file contains a plausible number.
