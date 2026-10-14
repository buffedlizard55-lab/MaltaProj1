#!/usr/bin/env python3
"""arena/5bcfd1b5 — scheduled check for changes to Hotspawn's listed CS2 matches.

Requirement: the board must "regularly check for updates to Hotspawn's listed matches".
This script is that check. It re-reads Hotspawn's public Angular SSR pages, extracts the
fixture inventory from the `<script id="ng-state">` TransferState payload, and diffs it
against the committed board, reporting:

  * fixtures Hotspawn now lists that the board does not have   -> NEW, needs a pick
  * fixtures whose start/lock epoch, teams, tier or format changed
  * fixtures that dropped off Hotspawn's payload
  * the standing disagreement between Hotspawn's printed counts and its payload

Design notes
------------
* The parsing is delegated read-only to `collector/hotspawn.py`, which projects ONLY
  fixture identity, times, tier, format and permalinks, and documents that account,
  leaderboard, score and crowd-pick values are discarded. Nothing here reads a crowd
  percentage, so nothing here can leak one into a probability.
* Times come from the payload's millisecond epochs, never from Hotspawn's printed
  wall-clock text (that text has been read as both UTC and UTC-4 across sessions).
* `compare()` is a pure function so the diff logic is unit-testable offline; only
  `fetch()` touches the network. A network failure is recorded, not raised: an
  unreachable Hotspawn must not fail the board's build.

Usage
-----
    python3 scripts/5bcfd1b5_livecheck.py                # write data/5bcfd1b5/livecheck.json
    python3 scripts/5bcfd1b5_livecheck.py --strict       # exit 2 if Hotspawn lists new fixtures
    python3 scripts/5bcfd1b5_livecheck.py --no-write     # report to stdout only
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

DATA = os.path.join(ROOT, "data", "5bcfd1b5")
BOARD = os.path.join(DATA, "every_match.csv")
OUT = os.path.join(DATA, "livecheck.json")

PAGES = (
    ("lobby", "https://play.hotspawn.com/lobby"),
    ("cs2-pickems", "https://play.hotspawn.com/cs2-pickems"),
)
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0 Safari/537.36")
TIMEOUT = 45


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str) -> tuple[bytes | None, str]:
    """Return (body, error). Never raises: an unreachable source is a finding, not a crash."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read(), ""
    except urllib.error.HTTPError as exc:
        return None, "HTTP %s %s" % (exc.code, exc.reason)
    except urllib.error.URLError as exc:
        return None, "network: %s" % (exc.reason,)
    except Exception as exc:  # noqa: BLE001 - recorded, never raised
        return None, "%s: %s" % (type(exc).__name__, exc)


def collect_live() -> dict:
    """Read both Hotspawn pages and project their fixture inventories."""
    from collector import hotspawn as hs  # read-only reuse of the shared collector

    out: dict = {"fetched_utc": now_utc(), "pages": {}, "records": {}, "errors": []}
    for name, url in PAGES:
        body, err = fetch(url)
        page: dict = {"url": url, "fetched_utc": out["fetched_utc"]}
        if err or body is None:
            page["error"] = err or "empty response"
            out["errors"].append("%s: %s" % (url, page["error"]))
            out["pages"][name] = page
            continue
        try:
            projection = hs.project_page(body, url)
            board, inventory, info = hs.extract_records(projection, "livecheck-5bcfd1b5")
        except ValueError as exc:
            page["error"] = str(exc)
            out["errors"].append("%s: %s" % (url, exc))
            out["pages"][name] = page
            continue
        cs2 = [r for r in inventory if r.get("game") == "cs2"]
        page.update({
            "response_sha256": projection["source_response_sha256"],
            "rendered_cards": info["rendered_card_count"],
            "cached_records": info["cached_record_count"],
            "cs2_records": len(cs2),
            "filter_totals": info["filter_totals"],
            "unparsed_card_ids": info["unparsed_card_ids"],
            "conflicting_card_ids": info["conflicting_card_ids"],
            "privacy_filter": projection["privacy_filter"],
        })
        out["pages"][name] = page
        for r in cs2:
            out["records"].setdefault(r["id"], r)
    return out


def compare(board_rows: list[dict], live: dict) -> dict:
    """Pure diff of the committed board against the live Hotspawn inventory."""
    board = {r["fixture_id"]: r for r in board_rows}
    records = live.get("records", {})
    new, changed, unchanged, dropped = [], [], [], []

    for fid, rec in sorted(records.items()):
        if fid not in board:
            new.append({
                "fixture_id": fid, "team_a": rec.get("team_a"), "team_b": rec.get("team_b"),
                "tournament": rec.get("tournament"), "tier": rec.get("tier"),
                "start_utc": rec.get("start_time"), "lock_utc": rec.get("lock_time"),
                "series_format": rec.get("series_format"), "source_url": rec.get("source_url"),
                "action": "needs a rating lookup, a line and a pick",
            })
            continue
        row = board[fid]
        diffs = []
        for live_key, board_key in (("start_time", "start_utc"), ("lock_time", "lock_utc"),
                                    ("team_a", "team_a"), ("team_b", "team_b"),
                                    ("tournament", "competition"), ("tier", "tier")):
            lv = rec.get(live_key)
            bv = row.get(board_key) or None
            if lv in (None, "") or bv in (None, ""):
                continue
            if str(lv).strip() != str(bv).strip():
                diffs.append({"field": board_key, "board": bv, "hotspawn_now": lv})
        fmt = rec.get("series_format") or ""
        bo = str(rec.get("best_of") or "").replace("BO", "").strip()
        if bo and bo != (row.get("best_of") or ""):
            diffs.append({"field": "best_of", "board": row.get("best_of") or "(blank)",
                          "hotspawn_now": bo, "series_format": fmt})
        if diffs:
            changed.append({"fixture_id": fid, "team_a": row["team_a"], "team_b": row["team_b"],
                            "pick": row["pick"], "pick_pct": row["pick_pct"],
                            "differences": diffs})
        else:
            unchanged.append(fid)

    # With no live inventory at all, "not listed" would report every fixture as vanished,
    # which is noise, not a finding. Only diff dropouts when something was actually read.
    comparable = bool(records)
    if comparable:
        for fid, row in sorted(board.items()):
            if fid not in records:
                dropped.append({"fixture_id": fid, "team_a": row["team_a"],
                                "team_b": row["team_b"], "state": row["state"],
                                "start_utc": row["start_utc"],
                                "expected": row["state"] != "open"})

    live_open = [fid for fid, r in records.items()
                 if r.get("lock_time") and r["lock_time"] > live.get("fetched_utc", "")]
    return {
        "compared_utc": live.get("fetched_utc", ""),
        "board_fixtures": len(board),
        "live_cs2_fixtures": len(records),
        "live_open_fixtures": len(live_open),
        "new_on_hotspawn": new,
        "changed_on_hotspawn": changed,
        "unchanged": len(unchanged),
        "no_longer_listed": dropped,
        "unexpectedly_missing": [d for d in dropped if not d["expected"]],
        "comparison_possible": comparable,
        "count_disagreement": {
            "note": "Hotspawn prints a weekly count and per-filter counts that do not equal the "
                    "number of CS2 rows in its own payload. Recorded, never asserted as coverage.",
            "filter_totals_by_page": {n: p.get("filter_totals") for n, p in live.get("pages",
                                                                                     {}).items()},
            "payload_cs2_rows": len(records),
        },
        "reachable": not live.get("errors"),
        "errors": live.get("errors", []),
        "verdict": ("NEW FIXTURES — the board must be rebuilt to pick them" if new else
                    ("CHANGED — re-verify the affected rows" if changed else
                     ("no live comparison possible — Hotspawn unreachable; the committed board "
                      "is unchanged and its own capture time still applies"
                      if not comparable else "board agrees with Hotspawn's payload"))),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--strict", action="store_true",
                    help="exit 2 when Hotspawn lists fixtures the board does not have")
    ap.add_argument("--no-write", action="store_true", help="report to stdout only")
    args = ap.parse_args(argv)

    with open(BOARD, encoding="utf-8", newline="") as fh:
        board_rows = list(csv.DictReader(fh))

    live = collect_live()
    report = compare(board_rows, live)
    report["pages"] = live["pages"]
    report["generated_by"] = "scripts/5bcfd1b5_livecheck.py (arena/5bcfd1b5)"
    report["crowd_percentages_read"] = False
    report["crowd_note"] = ("collector/hotspawn.py projects fixture identity, epochs, tier, format "
                            "and permalinks only, and documents that crowd pick values are "
                            "discarded; this check reads no crowd percentage.")

    if not args.no_write:
        os.makedirs(DATA, exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1, sort_keys=False)
            fh.write("\n")

    print("[5bcfd1b5 livecheck] %s" % report["verdict"])
    print("[5bcfd1b5 livecheck] board=%d live_cs2=%d live_open=%d new=%d changed=%d "
          "unlisted=%d (unexpected=%d) reachable=%s"
          % (report["board_fixtures"], report["live_cs2_fixtures"], report["live_open_fixtures"],
             len(report["new_on_hotspawn"]), len(report["changed_on_hotspawn"]),
             len(report["no_longer_listed"]), len(report["unexpectedly_missing"]),
             report["reachable"]))
    for n in report["new_on_hotspawn"]:
        print("  NEW  %s  %s vs %s  %s  tier %s  %s"
              % (n["fixture_id"], n["team_a"], n["team_b"], n["tournament"], n["tier"],
                 n["lock_utc"]))
    for c in report["changed_on_hotspawn"][:20]:
        print("  CHG  %s  %s vs %s  %s"
              % (c["fixture_id"], c["team_a"], c["team_b"],
                 "; ".join("%s: %s -> %s" % (d["field"], d["board"], d["hotspawn_now"])
                           for d in c["differences"])))
    for e in report["errors"]:
        print("  ERR  %s" % e)

    if args.strict and report["new_on_hotspawn"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
