#!/usr/bin/env python3
"""Build hotspawn/research/fallback_83090640.json from 83090640/research/hltv_observations.json.

Roster-overlap disambiguation rule (documented, reproducible, no free parameters beyond min_overlap):

  When a team name maps to more than one row in Valve's published Regional Standings
  (live/2026/standings_global_2026_10_05.md at commit eec4853), the row used for our own
  line is chosen by nickname overlap with the lineup HLTV lists for the specific match:

    overlap(row) = |nicknames(row.roster) ∩ nicknames(hltv_lineup)|   (accent/case-folded)

  The winner must have overlap >= 3 AND strictly more than any other same-name row.
  If that fails, the fixture stays unresolved (rung D) - a row is never guessed.

  Probabilities are NOT computed here. The model applies its own line formula
  (P = 1/(1+10^(-k*dPoints/400)) with the slope fitted on Valve's published results)
  to the chosen rows. This script only resolves identity, with evidence.

Usage:
  python3 83090640/resolve_fallback.py [--vrs-file PATH/standings_global_2026_10_05.md]
                                       [--out hotspawn/research/fallback_83090640.json]

With --vrs-file the embedded candidate rows are re-verified line-by-line against the
official file before anything is written; without it the embedded rows (each carrying
its permalink) are used as the frozen evidence of record.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OBS = ROOT / "83090640" / "research" / "hltv_observations.json"
MIN_OVERLAP = 3


def fold(text: str) -> str:
    return unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").casefold()


def nick(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", fold(name))


def overlap(roster: list[str], lineup: list[str]) -> int:
    return len({nick(p) for p in roster} & {nick(p) for p in lineup})


def choose(candidates: list[dict], lineup: list[str]) -> tuple[dict | None, dict]:
    scored = sorted(((overlap(c.get("roster") or [], lineup), c) for c in candidates),
                    key=lambda t: (-t[0], -(t[1].get("rank") or 10**9)))
    best = scored[0] if scored else (0, None)
    second = scored[1][0] if len(scored) > 1 else 0
    meta = {"candidates": len(candidates), "overlap_best": best[0], "overlap_second": second}
    if best[1] is not None and best[0] >= MIN_OVERLAP and best[0] > second:
        meta["ok"] = True
        return best[1], meta
    meta["ok"] = False
    return None, meta


def verify_against_file(sides: dict, vrs_file: Path) -> None:
    text = vrs_file.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[int(m.group(1))] = (int(m.group(2)), m.group(3).strip(),
                                     [p.strip() for p in m.group(4).split(",")])
    for side, s in sides.items():
        for cand in s["valve_candidates"]:
            rank = cand["rank"]
            if rank not in rows:
                raise SystemExit(f"rank {rank} not found in {vrs_file}")
            pts, name, roster = rows[rank]
            if pts != cand["points"]:
                raise SystemExit(f"points mismatch rank {rank}: file {pts} vs evidence {cand['points']}")
            if nick(name) != nick(s["team"]):
                raise SystemExit(f"name mismatch rank {rank}: file {name} vs evidence {s['team']}")
            if [nick(p) for p in roster] != [nick(p) for p in cand["roster"]]:
                raise SystemExit(f"roster mismatch rank {rank}: file {roster} vs evidence {cand['roster']}")
    print(f"verified {sum(len(s['valve_candidates']) for s in sides.values())} candidate rows against {vrs_file}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vrs-file", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "hotspawn" / "research" / "fallback_83090640.json")
    args = ap.parse_args()

    obs = json.loads(OBS.read_text(encoding="utf-8"))
    entries = []
    for mid, m in sorted(obs["matches"].items()):
        if args.vrs_file:
            verify_against_file(m["sides"], args.vrs_file)
        sides_out = {}
        ok_all = True
        for side in ("a", "b"):
            s = m["sides"][side]
            chosen, meta = choose(s["valve_candidates"], s["hltv_lineup"])
            ok_all = ok_all and meta["ok"]
            sides_out[side] = {
                "team": s["team"],
                "hltv_lineup": s["hltv_lineup"],
                "hltv_lineup_source": s["hltv_lineup_source"],
                "hltv_rank": s.get("hltv_rank"),
                "hltv_rank_url": s.get("hltv_rank_url"),
                "hltv_rank_note": s.get("hltv_rank_note"),
                "hltv_vrs_display_rank": s.get("hltv_vrs_display_rank"),
                "hltv_vrs_display_url": s.get("hltv_vrs_display_url"),
                "valve_candidates": [
                    {**c, "overlap": overlap(c.get("roster") or [], s["hltv_lineup"])}
                    for c in s["valve_candidates"]
                ],
                "chosen_rank": chosen["rank"] if chosen else None,
                "chosen_points": chosen["points"] if chosen else None,
                "chosen_roster": chosen["roster"] if chosen else None,
                "chosen_details_url": chosen["details_url"] if chosen else None,
                "disambiguation": meta,
                "roster_delta_vs_snapshot": s.get("roster_delta_vs_snapshot"),
                "note": s.get("note"),
            }
        entries.append({
            "match_id": mid,
            "team_a": m["team_a"],
            "team_b": m["team_b"],
            "competition": m["competition"],
            "format": m["format"],
            "format_source": m["format_source"],
            "hltv_match_url": m["hltv_match_url"],
            "hltv_read_utc": m["hltv_read_utc"],
            "hotspawn_match_url": m["hotspawn_match_url"],
            "market_check": m["market_check"],
            "context_form": m["context_form"],
            "sides": sides_out,
            "resolved": ok_all,
        })

    pack = {
        "schema": "hotspawn-research-fallback/1",
        "session": "arena/83090640",
        "generated_utc": obs.get("read_window_utc", "")[:10] + "T07:30:00Z",
        "rule": {
            "description": ("Rung E research fallback: used only when no outside price (rung A/B) and no strict "
                            "own line (rung C) resolved an open fixture. Valve standings rows are disambiguated by "
                            "nickname overlap with the HLTV-listed match lineup (>= 3 shared nicknames and strictly "
                            "more than any other same-name row). The board's own line formula (Valve points, slope k "
                            "fitted on Valve's published results) is then applied to the chosen rows. Rows that fail "
                            "the rule stay unresolved with blanks."),
            "min_overlap": MIN_OVERLAP,
            "valve_file": "live/2026/standings_global_2026_10_05.md",
            "valve_commit": obs["valve_commit"],
            "valve_url": obs["valve_file_url"],
        },
        "entries": entries,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(pack, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for en in entries:
        print(en["match_id"], en["team_a"], "vs", en["team_b"],
              "resolved" if en["resolved"] else "STILL UNRESOLVED",
              {s: (en["sides"][s]["chosen_rank"], en["sides"][s]["chosen_points"],
                   en["sides"][s]["disambiguation"]["overlap_best"]) for s in "ab"})
    return 0 if all(en["resolved"] for en in entries) else 1


if __name__ == "__main__":
    sys.exit(main())
