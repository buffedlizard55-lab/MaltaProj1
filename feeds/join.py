#!/usr/bin/env python3
"""Join archived source captures to the open Hotspawn CS2 fixtures (session arena/a0bdf924).

Input : feeds/data/capture.json + feeds/data/raw/{hotspawn_fixtures,polymarket_events,
        bo3_matches}.json.gz (written by feeds/collect.py), feeds/aliases.json.
Output: feeds/data/market_feed.csv|json  one row per accepted, quality-passed source quote
        feeds/data/fixtures.csv|json     one row per open Hotspawn CS2 fixture (coverage summary)
        feeds/data/review.csv            conflicts, kickoff mismatches, rejected quotes
        feeds/data/flags.csv             flag register (code, fixture, message, source links)
        feeds/data/summary.json          counts used by the pages and the tests

Deterministic: same inputs -> byte-identical outputs (tests re-run this and diff).
"""
from __future__ import annotations

import csv
import gzip
import io
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import match as M  # noqa: E402

DATA = HERE / "data"
RAW = DATA / "raw"
LOBBY = "https://play.hotspawn.com/cs2-pickems"

FEED_COLS = ["fixture_id", "start_utc", "lock_utc", "competition", "tier", "team_a", "team_b",
             "source", "book", "source_url", "book_url", "source_event", "source_team_a",
             "source_team_b", "price_a", "price_b", "price_kind", "implied_a_pct",
             "implied_b_pct", "overround_pct", "p_a_pct", "p_b_pct", "favourite",
             "format_bo", "source_kickoff_utc", "kickoff_delta_min", "match_quality",
             "match_note", "liquidity_usd", "volume_usd", "spread", "captured_utc",
             "hotspawn_url", "flags"]
FIX_COLS = ["fixture_id", "start_utc", "lock_utc", "competition", "tier", "team_a", "team_b",
            "format_bo", "format_source", "bookmaker_book", "bookmaker_p_a_pct",
            "bookmaker_p_b_pct", "bookmaker_url", "polymarket_p_a_pct", "polymarket_p_b_pct",
            "polymarket_url", "secondary_p_a_pct", "secondary_p_b_pct", "secondary_favourite",
            "n_sources", "status", "hotspawn_url", "captured_utc", "flags"]
REVIEW_COLS = ["fixture_id", "team_a", "team_b", "start_utc", "source", "kind", "source_event",
               "source_team_a", "source_team_b", "source_kickoff_utc", "kickoff_delta_min",
               "detail", "source_url"]
FLAG_COLS = ["code", "fixture_id", "match", "message", "source_url", "hotspawn_url"]

FLAG_TEXT = {
    "MF-01": "No secondary market found: neither Polymarket nor the bookmaker quote relayed by "
             "bo3.gg lists this fixture (or every listing failed a quality gate). Blank, not inferred.",
    "MF-02": "Opponent conflict: a source lists one of the teams at the same kickoff against a "
             "different opponent. Not used.",
    "MF-03": "Kickoff mismatch: both team names match but the source's kickoff differs by more "
             "than the allowed window. Not used.",
    "MF-04": "Name variant accepted (substring/initials) with identical opponent and kickoff. "
             "Review the identity link.",
    "MF-05": "Polymarket listing found but its quote failed a quality gate (spread, depth, "
             "degenerate prices, closed/live). Not used.",
    "MF-06": "Bookmaker quote relayed by bo3.gg found but unusable (suspended, invalid odds or "
             "margin). Not used.",
    "MF-07": "Sources disagree on the favourite.",
    "MF-08": "Sources disagree on the series format (best-of).",
    "MF-09": "Bookmaker price read through bo3.gg's public API relay, not from the bookmaker's "
             "own site; the bookmaker match URL is linked for manual checking.",
    "MF-10": "Polymarket is a prediction market (traded probabilities, no bookmaker margin); "
             "thin books move quickly.",
    "MF-11": "A source was unavailable in this run; its column is blank for every fixture.",
    "MF-12": "Hotspawn fixture list taken from another board's committed capture because the "
             "site did not answer this run.",
    "MF-13": "Hotspawn's payload does not state the series format (best_of/series_format null); "
             "format comes from the external source named in the row.",
}


def load_raw(name: str):
    path = RAW / f"{name}.json.gz"
    if not path.exists():
        return []
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def pct(x) -> str:
    return "" if x is None else f"{100.0 * x:.2f}"


def num(x, nd=3) -> str:
    if x is None or x == "":
        return ""
    try:
        text = f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return ""
    return text.rstrip("0").rstrip(".") if "." in text else text


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, lineterminator="\n", extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})
    path.write_text(buf.getvalue(), encoding="utf-8")


def fixture_view(raw: dict) -> dict:
    fid = str(raw.get("id"))
    return {"fixture_id": fid, "team_a": raw.get("participants0_name") or "",
            "team_b": raw.get("participants1_name") or "",
            "start_utc": raw.get("start_utc") or "", "lock_utc": raw.get("lock_utc") or "",
            "competition": raw.get("competition_name") or "", "tier": (raw.get("tier") or "").lower(),
            "hs_best_of": raw.get("best_of") or raw.get("series_format") or "",
            "hotspawn_url": raw.get("hotspawn_match_url") or LOBBY,
            "captured_utc": raw.get("captured_utc") or ""}


def main() -> int:
    capture = json.loads((DATA / "capture.json").read_text(encoding="utf-8"))
    aliases = M.Aliases.load(HERE / "aliases.json")
    as_of = M.parse_time(capture.get("generated_utc"))
    fixtures_raw = load_raw("hotspawn_fixtures")
    pm_events = load_raw("polymarket_events")
    bo3_matches = load_raw("bo3_matches")
    pm_quotes = [M.polymarket_quote(e) for e in pm_events]
    bo3_quotes = [M.bo3_quote(m) for m in bo3_matches]
    for q in pm_quotes:
        q["captured_utc"] = (capture.get("polymarket", {}).get("requests") or [{}])[0].get("fetched_utc", "")
    for q in bo3_quotes:
        q["captured_utc"] = (capture.get("bo3", {}).get("requests") or [{}])[0].get("fetched_utc", "")

    open_fx = []
    for raw in fixtures_raw:
        fx = fixture_view(raw)
        lock = M.parse_time(fx["lock_utc"])
        if lock and as_of and lock > as_of:
            open_fx.append(fx)
    open_fx.sort(key=lambda f: (f["start_utc"], f["fixture_id"]))

    feed_rows, fix_rows, review_rows, flags = [], [], [], []
    hs_fallback = capture.get("hotspawn", {}).get("fallback")
    unavailable = [name for name, key in (("Polymarket", "polymarket"), ("bo3.gg", "bo3"))
                   if capture.get(key, {}).get("status") != "observed"]
    for name in unavailable:
        flags.append({"code": "MF-11", "fixture_id": "", "match": "",
                      "message": f"{name} unavailable in this run ({FLAG_TEXT['MF-11']})",
                      "source_url": "", "hotspawn_url": ""})
    if open_fx and not any(f["hs_best_of"] for f in open_fx):
        flags.append({"code": "MF-13", "fixture_id": "", "match": "",
                      "message": FLAG_TEXT["MF-13"] + f" Applies to all {len(open_fx)} open fixtures in this capture.",
                      "source_url": "", "hotspawn_url": LOBBY})
    if hs_fallback:
        flags.append({"code": "MF-12", "fixture_id": "", "match": "",
                      "message": f"{FLAG_TEXT['MF-12']} Used {hs_fallback.get('path')} generated "
                                 f"{hs_fallback.get('generated_utc')}.",
                      "source_url": "", "hotspawn_url": LOBBY})

    for fx in open_fx:
        label = f"{fx['team_a']} vs {fx['team_b']}"
        used: dict[str, dict] = {}
        row_flags: list[str] = []
        for quotes in (bo3_quotes, pm_quotes):
            best = None
            for q in quotes:
                rel = M.match_quote(fx, q, aliases)
                if rel["status"] == "none":
                    continue
                if rel["status"] == "accepted":
                    if best is None or (rel["delta_min"] or 0) < (best[1]["delta_min"] or 0):
                        best = (q, rel)
                    continue
                review_rows.append({
                    "fixture_id": fx["fixture_id"], "team_a": fx["team_a"], "team_b": fx["team_b"],
                    "start_utc": fx["start_utc"], "source": q["source"], "kind": rel["quality"],
                    "source_event": q.get("title") or q.get("league") or "",
                    "source_team_a": q.get("team_a"), "source_team_b": q.get("team_b"),
                    "source_kickoff_utc": q.get("kickoff_utc"),
                    "kickoff_delta_min": num(rel["delta_min"], 0), "detail": rel["note"],
                    "source_url": q.get("source_url")})
                code = "MF-02" if rel["status"] == "conflict" else "MF-03"
                if code not in row_flags:
                    row_flags.append(code)
                flags.append({"code": code, "fixture_id": fx["fixture_id"], "match": label,
                              "message": f"{q['source']}: {rel['note']}",
                              "source_url": q.get("source_url"), "hotspawn_url": fx["hotspawn_url"]})
            if best is None:
                continue
            q, rel = best
            if not q.get("ok") and q.get("reject") == "no bookmaker quote relayed":
                continue          # listed without odds: not a rejection (format is still read below)
            if not q.get("ok"):
                code = "MF-05" if q["source"] == "Polymarket" else "MF-06"
                if code not in row_flags:
                    row_flags.append(code)
                review_rows.append({
                    "fixture_id": fx["fixture_id"], "team_a": fx["team_a"], "team_b": fx["team_b"],
                    "start_utc": fx["start_utc"], "source": q["source"], "kind": "rejected-quote",
                    "source_event": q.get("title") or q.get("league") or "",
                    "source_team_a": q.get("team_a"), "source_team_b": q.get("team_b"),
                    "source_kickoff_utc": q.get("kickoff_utc"),
                    "kickoff_delta_min": num(rel["delta_min"], 0), "detail": q.get("reject", ""),
                    "source_url": q.get("source_url")})
                flags.append({"code": code, "fixture_id": fx["fixture_id"], "match": label,
                              "message": f"{q['source']}: {q.get('reject', '')}",
                              "source_url": q.get("source_url"), "hotspawn_url": fx["hotspawn_url"]})
                continue
            swap = rel["swap"]
            p_a = q["p_b"] if swap else q["p_a"]
            p_b = q["p_a"] if swap else q["p_b"]
            pr_a = q.get("price_b") if swap else q.get("price_a")
            pr_b = q.get("price_a") if swap else q.get("price_b")
            im_a = q.get("implied_b") if swap else q.get("implied_a")
            im_b = q.get("implied_a") if swap else q.get("implied_b")
            src_a = q.get("team_b") if swap else q.get("team_a")
            src_b = q.get("team_a") if swap else q.get("team_b")
            f_codes = []
            if rel["quality"] == "variant":
                f_codes.append("MF-04")
                flags.append({"code": "MF-04", "fixture_id": fx["fixture_id"], "match": label,
                              "message": f"{q['source']}: {rel['note']}",
                              "source_url": q.get("source_url"), "hotspawn_url": fx["hotspawn_url"]})
            f_codes.append("MF-09" if q["source"] == "bo3.gg" else "MF-10")
            row = {
                "fixture_id": fx["fixture_id"], "start_utc": fx["start_utc"],
                "lock_utc": fx["lock_utc"], "competition": fx["competition"], "tier": fx["tier"],
                "team_a": fx["team_a"], "team_b": fx["team_b"], "source": q["source"],
                "book": q.get("book", ""), "source_url": q.get("source_url", ""),
                "book_url": q.get("book_url", ""),
                "source_event": q.get("title") or q.get("league") or "",
                "source_team_a": src_a, "source_team_b": src_b,
                "price_a": num(pr_a), "price_b": num(pr_b),
                "price_kind": "decimal odds" if q["source"] == "bo3.gg" else "share price (USD 0-1)",
                "implied_a_pct": pct(im_a), "implied_b_pct": pct(im_b),
                "overround_pct": pct(q.get("overround")), "p_a_pct": pct(p_a), "p_b_pct": pct(p_b),
                "favourite": M.pick_from(p_a, fx["team_a"], fx["team_b"]),
                "format_bo": q.get("format_bo") or "", "source_kickoff_utc": q.get("kickoff_utc"),
                "kickoff_delta_min": num(rel["delta_min"], 0), "match_quality": rel["quality"],
                "match_note": rel["note"], "liquidity_usd": num(q.get("liquidity_usd"), 2),
                "volume_usd": num(q.get("volume_usd"), 2), "spread": num(q.get("spread")),
                "captured_utc": q.get("captured_utc", ""), "hotspawn_url": fx["hotspawn_url"],
                "flags": ";".join(f_codes), "_p_a": p_a}
            used[q["source"]] = row
            feed_rows.append(row)

        bk, pmr = used.get("bo3.gg"), used.get("Polymarket")
        ps = [r["_p_a"] for r in (bk, pmr) if r]
        sec = sum(ps) / len(ps) if ps else None
        formats = {str(r["format_bo"]) for r in (bk, pmr) if r and r["format_bo"]}
        listed_only_src = ""
        # bo3.gg lists the format for every match it carries, even without a usable quote
        if not formats:
            for q in bo3_quotes:
                rel = M.match_quote(fx, q, aliases)
                if rel["status"] == "accepted" and q.get("format_bo"):
                    formats.add(str(q["format_bo"]))
                    listed_only_src = "bo3.gg (match listed, no usable quote)"
                    break
        if bk and pmr and bk["favourite"] and pmr["favourite"] and bk["favourite"] != pmr["favourite"]:
            row_flags.append("MF-07")
            flags.append({"code": "MF-07", "fixture_id": fx["fixture_id"], "match": label,
                          "message": f"{bk['book']} via bo3.gg favours {bk['favourite']} "
                                     f"({bk['p_a_pct']}% {fx['team_a']}); Polymarket favours "
                                     f"{pmr['favourite']} ({pmr['p_a_pct']}% {fx['team_a']})",
                          "source_url": pmr["source_url"], "hotspawn_url": fx["hotspawn_url"]})
        if len(formats) > 1:
            row_flags.append("MF-08")
            flags.append({"code": "MF-08", "fixture_id": fx["fixture_id"], "match": label,
                          "message": f"best-of disagrees across sources: {sorted(formats)}",
                          "source_url": (bk or pmr)["source_url"], "hotspawn_url": fx["hotspawn_url"]})
        if not ps:
            if "MF-01" not in row_flags:
                row_flags.insert(0, "MF-01")
            flags.append({"code": "MF-01", "fixture_id": fx["fixture_id"], "match": label,
                          "message": FLAG_TEXT["MF-01"], "source_url": "",
                          "hotspawn_url": fx["hotspawn_url"]})
        if len(formats) == 1:
            fmt = next(iter(formats))
            fmt_source = ", ".join(r["source"] for r in (bk, pmr) if r and str(r["format_bo"]) == fmt) \
                or listed_only_src
        else:
            fmt, fmt_source = "", ("sources disagree" if formats else "")
        status = "priced (2 sources)" if len(ps) == 2 else "priced (1 source)" if ps else "no secondary market"
        fix_rows.append({
            "fixture_id": fx["fixture_id"], "start_utc": fx["start_utc"], "lock_utc": fx["lock_utc"],
            "competition": fx["competition"], "tier": fx["tier"], "team_a": fx["team_a"],
            "team_b": fx["team_b"], "format_bo": fmt, "format_source": fmt_source,
            "bookmaker_book": bk["book"] if bk else "", "bookmaker_p_a_pct": bk["p_a_pct"] if bk else "",
            "bookmaker_p_b_pct": bk["p_b_pct"] if bk else "",
            "bookmaker_url": (bk["book_url"] or bk["source_url"]) if bk else "",
            "polymarket_p_a_pct": pmr["p_a_pct"] if pmr else "",
            "polymarket_p_b_pct": pmr["p_b_pct"] if pmr else "",
            "polymarket_url": pmr["source_url"] if pmr else "",
            "secondary_p_a_pct": pct(sec), "secondary_p_b_pct": pct(1 - sec) if sec is not None else "",
            "secondary_favourite": M.pick_from(sec, fx["team_a"], fx["team_b"]),
            "n_sources": len(ps), "status": status, "hotspawn_url": fx["hotspawn_url"],
            "captured_utc": fx["captured_utc"], "flags": ";".join(dict.fromkeys(row_flags))})

    for r in feed_rows:
        r.pop("_p_a", None)
    flags.sort(key=lambda f: (f["code"], f["fixture_id"], f["message"]))
    summary = {
        "generated_utc": capture.get("generated_utc"), "as_of_utc": M.iso(as_of),
        "hotspawn_cs2_fixtures": len(fixtures_raw), "open_cs2_fixtures": len(open_fx),
        "priced_any": sum(1 for r in fix_rows if r["n_sources"]),
        "priced_both": sum(1 for r in fix_rows if r["n_sources"] == 2),
        "priced_bookmaker": sum(1 for r in fix_rows if r["bookmaker_p_a_pct"]),
        "priced_polymarket": sum(1 for r in fix_rows if r["polymarket_p_a_pct"]),
        "format_known": sum(1 for r in fix_rows if r["format_bo"]),
        "feed_rows": len(feed_rows), "review_rows": len(review_rows), "flags": len(flags),
        "polymarket_events": len(pm_events), "bo3_matches": len(bo3_matches),
        "polymarket_status": capture.get("polymarket", {}).get("status"),
        "bo3_status": capture.get("bo3", {}).get("status"),
        "hotspawn_fallback": hs_fallback,
        "hotspawn_pages": [{k: p.get(k) for k in ("page", "url", "status", "cs2_rows", "fetched_utc")}
                           for p in capture.get("hotspawn", {}).get("pages", [])],
        "probes": [{k: p.get(k) for k in ("source", "url", "status", "bytes", "error", "fetched_utc")}
                   for p in capture.get("probes", [])],
    }
    write_csv(DATA / "market_feed.csv", FEED_COLS, feed_rows)
    write_csv(DATA / "fixtures.csv", FIX_COLS, fix_rows)
    write_csv(DATA / "review.csv", REVIEW_COLS, review_rows)
    write_csv(DATA / "flags.csv", FLAG_COLS, flags)
    (DATA / "market_feed.json").write_text(json.dumps(feed_rows, indent=1, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
    (DATA / "fixtures.json").write_text(json.dumps(fix_rows, indent=1, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    (DATA / "summary.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
    (DATA / "flag_codes.json").write_text(json.dumps(FLAG_TEXT, indent=1, ensure_ascii=False) + "\n",
                                          encoding="utf-8")
    print(f"join: {len(open_fx)} open CS2 fixtures; priced by any secondary source "
          f"{summary['priced_any']} (bookmaker {summary['priced_bookmaker']}, Polymarket "
          f"{summary['priced_polymarket']}, both {summary['priced_both']}); format known "
          f"{summary['format_known']}; {len(review_rows)} review rows; {len(flags)} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main())
