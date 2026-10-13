# Combined repository audit

Audit UTC: **2026-10-13T19:35:23.216879+00:00**
Base commit: [`f1db7c0882b1`](https://github.com/buffedlizard55-lab/MaltaProj1/commit/f1db7c0882b1d6f48df73814a5a0c96a826fab4e)

Read **260 tracked files / 138,798 text lines**; checked **1,564 internal HTML targets**.

> This verifies inventory, syntax/data shape and link consistency—not the truth of every inherited sports assertion. Only the evidence dashboard snapshot is admitted to the primary-bookmaker calculation and rechecked field by field. Other owners' work is preserved, not silently certified or overwritten.

## Review findings (non-blocking outside this dashboard's owned scope)

| File | Review type | Detail | Official repository source |
|---|---|---|---|
| `data/844ba68e/market_quotes.csv` | CSV shape | 1 row(s) have excess fields. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/data/844ba68e/market_quotes.csv) |
| `data/external_lines.csv` | CSV shape | 2 row(s) have excess fields. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/data/external_lines.csv) |
| `docs/flagged.html` | anchor review | No static anchor: verified-lines.html#F-28; may be client-generated. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/docs/flagged.html) |
| `docs/flagged.html` | anchor review | No static anchor: verified-lines.html#F-29; may be client-generated. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/docs/flagged.html) |
| `docs/flagged.html` | anchor review | No static anchor: verified-lines.html#flagged-audit; may be client-generated. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/docs/flagged.html) |
| `docs/verified-lines.html` | anchor review | No static anchor: #F-28; may be client-generated. | [Review file](https://github.com/buffedlizard55-lab/MaltaProj1/blob/f1db7c0882b1d6f48df73814a5a0c96a826fab4e/docs/verified-lines.html) |

## Line-by-line file ledger

Each file has its complete-content SHA-256, text line count, parser checks, referenced hosts and official review link in [repository-audit.json](repository-audit.json). Values of detected personal/contact fields are never repeated in this report.

## Scope-preserving source review

- Legacy `scripts/model.py` and rank-derived tables are not external match-winner quotes. A rank-based estimate is a separate method, not a substitute for an unavailable bookmaker value.
- `pipeline/inventory.py` estimates UTC from countdowns and a five-minute published rule. The official fixture transfer state has explicit UTC-millisecond schedules and explicit lock metadata; the observed 360-second offset conflicts with that 300-second rule. Our snapshot uses the exact schedule and flags the conflict instead of using that estimate.
- `model/` has its own Valve/HLTV inputs, calibration and explicit alias documentation. Its published model estimates require their own method/evidence review and are not merged into this market-based dataset.
- Parallel `assurance/`, `docs/`, `site/`, `pickem/`, root pages and namespace CSVs remain separate outputs. Source URLs alone do not verify a price, market period, capture time, or calibrated probability.
- The new `dashboard/` publishes both CS2 and LoL, full captured source-state inventory, official links on every data row, blanks for unknown fields, expiry and scheduled automatic refresh.
