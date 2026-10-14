# Source re-read verification — session `arena/bdc98a9a`

**Deliverable:** <https://buffedlizard55-lab.github.io/MaltaProj1/reread/index.html> (mobile-first),
flagged rows at <https://buffedlizard55-lab.github.io/MaltaProj1/reread/flagged.html>.
**Question answered:** for every external URL the merged pick boards cite, does the source still say
what the board prints beside it — and if a runner cannot read it, is that recorded instead of filled in?

## What was re-read

`reread/collect.py` extracts the cited URL *and the value claimed beside it* from the merged boards'
own data files, then re-reads each URL live in CI:

| Board (file read read-only) | Cited values |
|---|---|
| `data/fbcccda2/every_pick.csv` (every-match picks) | 192 |
| `data/63ee81ba/picks.csv` (full-coverage board) | 28 |
| `cs2/data/analysis.csv` (line-analysis board) | 280 |
| **deduplicated worklist** | **288** |

Run: `2026-10-14T03:42:58Z`, CI run `38506905679`, machine-readable result
`reread/data/source_check.csv` (one row per cited value, source link on every row) plus the fetch log
with a SHA-256 per body in `reread/data/log.jsonl`.

## Result

**188 of 288 cited values re-read exactly as published. 0 rows where a live source contradicted a
published value. 83 refused, 17 not-checkable, 0 dead links, 0 placeholder pairs.**

| Kind of citation | Total | Re-read as printed | Needs review |
|---|---|---|---|
| Valve Regional Standings line (`github.com`/`raw.githubusercontent.com`) | 131 | **131** | 0 |
| HLTV team page (team exists, name present) | 39 | **39** | 0 |
| HLTV match page (team names + series format) | 30 | 13 | 17 refused |
| EGamersWorld match page (market quote) | 44 | 0 | 42 refused, 2 no odds table served |
| Hotspawn fixture page (identity only) | 26 | 2 | 24 refused |
| Pinnacle page / guest API | 15 | 0 | 15 not-checkable |
| Polymarket event (reference only) | 3 | 3 | 0 |

By host: `raw.githubusercontent.com` 92, `www.hltv.org` 73, `egamersworld.com` 40, `github.com` 39,
`www.hotspawn.com` 24, `guest.api.arcadia.pinnacle.com` 10, `www.pinnacle.com` 5, `polymarket.com` 3,
`play.hotspawn.com` 2.

## Findings

- **SRC-01 — Valve rating provenance is solid.** All 131 citations of a Valve Regional Standings line
  re-read at the cited anchor: the line really does carry that team and that rank. Example:
  `FORZE Reload`, rank 84, `<…/standings_global_2026_10_05.md?plain=1#L89>`. This is the input behind
  the board's own lines, and it is the one input that is fully machine-verifiable today.
- **SRC-02 — chief finding: the EGamersWorld quotes cannot be re-read from CI.** All 44 EGamersWorld
  citations were opened again; 42 were refused (HTTP 403 to a plain client *and* to a headless
  Chromium with a normal user agent), 2 served a page with no parsable named-book table. Those pages
  are the source of **19 of the 28 open-fixture picks** on the every-match board (the board's own
  tier note; this verifier only re-read the links, it did not recount the picks)
  (e.g. `Gothic 2.05 / Lavked 1.64` on
  <https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B>). The values
  are **not contradicted** — they are **not confirmable** from a GitHub runner, which is exactly the
  risk the repository audit raised when it found these prices are literals in data files. Anyone
  relying on a Tier-B price should open the link from a normal browser before the match.
- **SRC-03 — HLTV serves team pages but bot-checks match pages.** 39/39 HLTV team pages re-read
  (headless Chromium was needed for most of them), but 17 of 30 match pages returned 403 even through
  a browser. Refusals are recorded as refusals; the affected rows keep their link and the "refused"
  chip so a human can check the page in one tap.
- **SRC-04 — Hotspawn per-fixture pages refuse the runner too.** 24 of 26 `www.hotspawn.com/matches/…`
  pages returned 403. Hotspawn is used in this repository for **fixture identity and series format
  only**; its crowd percentages are never parsed, and the test suite asserts that
  (`tests/test_bdc98a9a_verify.py::WorklistTests::test_hotspawn_claims_are_identity_only`).
- **SRC-05 — Pinnacle citations are not per-match permalinks any more.** 10 guest-API payloads no
  longer contain the pairing (markets disappear from that response after the match starts), and 5
  citations are the generic matchups listing, which carries no per-match state. `not-checkable`, not
  `mismatch`: nothing contradicts the published prices.
- **SRC-06 — team-name renames are handled from evidence, not by guessing.** Four Hotspawn spellings
  differ from the organiser's (`WROTBERRY`→`WBT`, `RoundsGG`→`ROUNDS`, `BB Team`→`BetBoom`,
  `PVISION`→`PARIVISION`). The verifier reads `cs2/aliases.json` (each entry has a confirming session
  and an evidence URL) and reports `alias:` rather than a false mismatch. Before that rule, 8 rows
  showed as mismatches; after it, 0 do.
- **SRC-07 — prediction-market pages re-read cleanly** (3/3 Polymarket event pages found both teams).
  They remain a *reference*; the repository never lets a prediction market decide a pick.

## Requests (no other board's data was edited)

1. **Board owners of the EGW-backed picks** (`arena/fbcccda2`, `arena/63ee81ba`, `arena/a174d77f`):
   because the source refuses CI, archive the odds block you read (as `cs2/` does with raw captures)
   or record the read time per price, so a reader can tell a fresh read from a literal.
2. **Integration owner:** one card linking `reread/index.html` was added to the landing page's
   executive-summary grid by this session as its final integration action (no other shared output was
   touched); keep it if the numbering still fits, or move it next to the picks links.
3. **Hotspawn per-match pages:** nothing to fix — the refusal is on Hotspawn's side and is recorded.

## Reproduce

```bash
python3 reread/collect.py                 # re-read every cited URL (needs network)
python3 scripts/bdc98a9a_verify_build.py  # render reread/*.html from the result
python3 -m unittest tests.test_bdc98a9a_verify -v
```

CI: `.github/workflows/reread-bdc98a9a.yml` — hourly at `:37`, plus a run whenever a board's data file
or this verifier changes. Validation runs on every branch; generated files are committed on `main` and
on this session's branch only, and a raise inside the collector is published as `reread/data/error.json`
before the job turns red.
