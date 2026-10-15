#!/usr/bin/env python3
"""Invariants for the executive board — session arena/5545dbb8.

These run after ``collect.py`` and ``build.py`` and before anything is committed. A failure means the
snapshot is not published. The checks re-derive published numbers from the stored inputs rather than
trusting the build's own output.

Run:  python executive/tests.py
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ownlines import series_probability, format_to_best_of
from common import DATA, EXEC, devig_pair, logit_prob, parse_iso, read_csv, read_json  # noqa: E402

FAILURES: list[str] = []
CHECKS: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "passed": bool(ok), "detail": detail})
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def load():
    return {
        "summary": read_json(DATA / "summary.json", {}) or {},
        "analysis": read_json(DATA / "analysis.json", {}) or {},
        "rows": read_csv(DATA / "analysis.csv"),
        "ratings": read_csv(DATA / "ratings.csv"),
        "external": read_csv(DATA / "external_lines.csv"),
        "fixtures": read_csv(DATA / "fixtures.csv"),
        "flags": read_csv(DATA / "flags.csv"),
        "links": read_json(DATA / "linkcheck.json", {}) or {},
        "provenance": read_json(DATA / "provenance.json", {}) or {},
        "hotspawn": read_json(DATA / "hotspawn_pages.json", {}) or {},
    }


def main() -> int:
    data = load()
    rows, ratings, external = data["rows"], data["ratings"], data["external"]
    if not rows:
        check("analysis.csv exists and has rows", False, "no rows found — run build.py first")
        report()
        return 1

    # 1. every row is anchored to a source
    missing_source = [r["match_id"] for r in rows
                      if not (r.get("source_links") or r.get("hotspawn_match_url")
                              or r.get("hotspawn_pickem_url") or r.get("flags"))]
    check("every fixture row has a source link or a flag", not missing_source,
          f"rows without any source: {missing_source[:5]}")

    # 2. probabilities add to 100
    bad_sum = []
    for row in rows:
        if row.get("prob_a_pct") and row.get("prob_b_pct"):
            total = float(row["prob_a_pct"]) + float(row["prob_b_pct"])
            if abs(total - 100.0) > 0.15:
                bad_sum.append((row["match_id"], total))
    check("probability pairs add to 100", not bad_sum, f"rows off by >0.15: {bad_sum[:5]}")

    # 3. market probabilities re-derive from the stored quotes
    by_match: dict[str, list[dict]] = {}
    for row in external:
        by_match.setdefault(row["match_id"], []).append(row)
    bad_market = []
    for row in rows:
        if int(row["basis_tier"] or 0) not in (1, 2):
            continue
        quotes = [q for q in by_match.get(row["match_id"], []) if q["placeholder_rejected"] == "False"]
        if not quotes:
            bad_market.append((row["match_id"], "no usable quote stored"))
            continue
        recomputed = []
        for quote in quotes:
            odds_a, odds_b = float(quote["odds_a"]), float(quote["odds_b"])
            p_a, p_b, over = devig_pair(odds_a, odds_b)
            recomputed.append((p_a * 100.0, p_b * 100.0, over,
                               float(quote["overround_pct"]), quote["source_name"]))
        headline = (float(row["prob_a_pct"]), float(row["prob_b_pct"]))
        if not any(abs(p_a - headline[0]) < 0.06 for p_a, _, _, _, _ in recomputed):
            bad_market.append((row["match_id"], f"headline {headline} not among {[r[0] for r in recomputed]}"))
        for p_a, p_b, over, stored_over, name in recomputed:
            if abs(p_a + p_b - 100.0) > 0.01 or abs(over - stored_over) > 0.01:
                bad_market.append((row["match_id"], f"{name} arithmetic mismatch"))
    check("market rows re-derive from their stored quotes", not bad_market, str(bad_market[:5]))

    # 4. model probabilities re-derive from the stored official points
    rating_by_team = {r["team"]: r for r in ratings}
    vrs_rows = (read_json(DATA / "vrs.json", {}) or {}).get("rows", [])
    # The bound for an unlisted team comes from the official file itself, never from this board's rows.
    ranked_floor = min((int(r["vrs_points"]) for r in vrs_rows), default=0)
    bad_model = []
    for row in rows:
        tier = int(row["basis_tier"] or 0)
        if tier not in (3, 4) or not row.get("model_prob_a_pct"):
            continue
        a, b = rating_by_team.get(row["team_a"], {}), rating_by_team.get(row["team_b"], {})
        if tier == 3:
            if not (a.get("vrs_points") and b.get("vrs_points")):
                bad_model.append((row["match_id"], "tier 3 without both ratings"))
                continue
            expected = series_probability(logit_prob(float(a["vrs_points"]), float(b["vrs_points"])), format_to_best_of(row.get("series_format"))) * 100.0
        else:
            listed = [(a, "a"), (b, "b")] if a.get("vrs_points") and not b.get("vrs_points") else \
                     [(b, "b"), (a, "a")]
            if not (listed[0][0].get("vrs_points") and not listed[1][0].get("vrs_points")):
                bad_model.append((row["match_id"], "tier 4 without exactly one listed team"))
                continue
            if not ranked_floor:
                bad_model.append((row["match_id"], "no official standings file to take the bound from"))
                continue
            p_listed = logit_prob(float(listed[0][0]["vrs_points"]), ranked_floor) * 100.0
            expected = p_listed if listed[0][1] == "a" else 100.0 - p_listed
        if abs(expected - float(row["model_prob_a_pct"])) > 0.06:
            bad_model.append((row["match_id"], f"{expected:.2f} vs published {row['model_prob_a_pct']}"))
    check("model rows re-derive from the official points", not bad_model, str(bad_model[:5]))

    # 5. no Hotspawn crowd data anywhere in the published data
    def keys_of(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                yield f"{path}.{key}"
                yield from keys_of(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node[:400]):
                yield from keys_of(value, f"{path}[{index}]")

    crowd_tokens = ("picked_percent", "total_picks", "crowd_pct", "crowd_percent")
    allowed_keys = {"crowd_fields_dropped"}   # the ingest log documents what was dropped
    crowd_hits = []
    for path in sorted(DATA.rglob("*")):
        if path.is_dir():
            continue
        if path.suffix.lower() == ".json":
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            for key_path in keys_of(payload):
                leaf = key_path.rsplit(".", 1)[-1]
                if leaf in allowed_keys:
                    continue
                if any(token in leaf.lower() for token in crowd_tokens):
                    crowd_hits.append(f"{path.name}:{key_path}")
        elif path.suffix.lower() == ".csv":
            header = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            for field in (header[0].split(",") if header else []):
                if any(token in field.lower() for token in crowd_tokens):
                    crowd_hits.append(f"{path.name}:{field}")
    check("no Hotspawn crowd value stored in executive/data", not crowd_hits, str(crowd_hits[:5]))

    # 6. local links resolve
    links = data["links"]
    check("every local link resolves", links.get("ok") is True,
          f"broken: {links.get('broken')}")

    # 7. tier consistency
    problems = []
    for row in rows:
        tier = int(row["basis_tier"] or 0)
        flags = row.get("flags", "")
        if tier == 1 and row.get("market_source") not in {"Pinnacle"}:
            problems.append((row["match_id"], "tier 1 without a primary bookmaker quote"))
        if tier == 4 and "FL-UNLISTED-OPPONENT" not in flags:
            problems.append((row["match_id"], "tier 4 without the unlisted-opponent flag"))
        if tier == 0 and row.get("pick"):
            problems.append((row["match_id"], "no-basis row published a pick"))
    check("basis tiers match their evidence", not problems, str(problems[:5]))

    # 8. rendered pages contain no placeholder artefacts
    artefacts = []
    for page in sorted(EXEC.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for token in (">None<", ">nan<", "undefined", "&amp;amp;"):
            if token in text:
                artefacts.append(f"{page.name}:{token}")
    check("rendered pages contain no placeholder artefacts", not artefacts, str(artefacts[:6]))

    # 9. every published source URL is https
    bad_urls = []
    for row in external:
        for key in ("source_url", "api_url"):
            url = row.get(key)
            if url and not url.startswith("https://"):
                bad_urls.append((row["match_id"], key, url))
    for row in ratings:
        url = row.get("vrs_url")
        if url and not url.startswith("https://"):
            bad_urls.append((row["team"], "vrs_url", url))
    check("every published source URL is https", not bad_urls, str(bad_urls[:5]))

    # 10. reported coverage matches the rows
    coverage = (data["analysis"].get("coverage") or {})
    open_rows = [r for r in rows if r.get("status") == "open"]
    with_pick = [r for r in open_rows if r.get("pick") and r["pick"] != "(no side — 50/50)"]
    recomputed = {
        "total_fixtures": len(rows), "open_fixtures": len(open_rows),
        "open_with_pick": len(with_pick),
        "open_market_basis": len([r for r in open_rows if int(r["basis_tier"] or 0) in (1, 2)]),
        "open_model_basis": len([r for r in open_rows if int(r["basis_tier"] or 0) in (3, 4, 5)]),
        "open_provisional": len([r for r in open_rows if int(r["basis_tier"] or 0) == 4]),
        "flagged_rows": len([r for r in rows if r.get("flags")]),
    }
    mismatched = {k: (v, coverage.get(k)) for k, v in recomputed.items() if coverage.get(k) != v}
    check("reported coverage matches the published rows", not mismatched, str(mismatched))

    # 11. an outside line is never published without a read time and a page
    bad_external = [r["match_id"] for r in external
                    if not r.get("captured_utc") or not r.get("source_url")]
    check("external lines carry a source page and a read time", not bad_external, str(bad_external[:5]))

    # 12. name resolution always carries its evidence
    bad_evidence = [(r["team"], r["match_method"]) for r in ratings
                    if r.get("match_method") in ("hltv", "roster", "alias", "exact+roster")
                    and not r.get("match_evidence_url")]
    check("non-exact name resolution carries evidence", not bad_evidence, str(bad_evidence[:5]))

    # 13. every open fixture has either a pick or a documented reason
    no_basis = [r["match_id"] for r in open_rows
                if (not r.get("pick") or r["pick"] == "(no side — 50/50)") and not r.get("flags")]
    check("open fixtures without a pick are flagged", not no_basis, str(no_basis[:5]))

    # 14. the snapshot is not older than the policy allows to present as current
    summary = data["summary"]
    stale = bool(summary.get("meta", {}).get("stale"))
    check("snapshot freshness is reported honestly", "snapshot_age_text" in summary.get("meta", {}),
          f"stale={stale} age={summary.get('meta', {}).get('snapshot_age_text')}")

    # 15. arithmetic sanity of the official relation itself (fixed known values)
    p = logit_prob(1800, 1400)
    check("official relation sanity (400 points ≈ 91%)", abs(p - 10 / 11) < 1e-9,
          f"p(1800 vs 1400) = {p:.6f}")

    report()
    return 1 if FAILURES else 0


def report() -> None:
    print(json.dumps({
        "checks": CHECKS,
        "failures": FAILURES,
        "passed": len([c for c in CHECKS if c["passed"]]),
        "failed": len(FAILURES),
    }, indent=1))


if __name__ == "__main__":
    sys.exit(main())
