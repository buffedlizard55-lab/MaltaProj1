#!/usr/bin/env python3
"""O-01 cross-check (session arena/91eff436): compare rating and fixture values published ELSEWHERE in this repo
with the official snapshots O-01 uses. Read-only: other sessions' files are never edited.
Discrepancies are reported in model/data/crosscheck.csv and logged in COORDINATION.md.

Official references (all under model/input/, each with its source URL and SHA-256):
  * Valve Regional Standings global file (VRS standing and points), the exact Valve file at a pinned commit
  * HLTV World Ranking of the snapshot date (rank and points)
  * Hotspawn TransferState (fixture id, teams, scheduled_start_time)
Only like-for-like comparisons are made. A value labelled with another date is reported as "not comparable",
never as a mismatch.
"""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
import build  # noqa: E402

GH = "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/"


def read_csv(rel: str) -> list[dict]:
    f = REPO / rel
    if not f.exists():
        return []
    with f.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    fx, meta, vrs, hltv, _ = build.load_inputs()
    hltv_by = {build.norm(t["name"]): t for t in hltv.get("teams", [])}
    hltv_by_id = {str(t.get("team_id")): t for t in hltv.get("teams", []) if t.get("team_id")}
    aliases = build.load_aliases()
    hdate = hltv.get("ranking_date", "")
    hurl = hltv.get("canonical_url", "")
    out: list[dict] = []

    def add(check, rel, key, field, published, official, src, status):
        out.append({"check": check, "file": rel, "key": key, "field": field, "published": published,
                    "official": official, "official_source": src, "status": status, "file_url": GH + rel})

    def vrs_row(team: str):
        r = build.resolve(team, vrs, hltv_by, aliases, hltv_by_id)
        return r["vrs"], r["status"]

    # 1) VRS ranks published by 6d9c321d
    rel = "data/6d9c321d/team_ratings_verified.csv"
    for r in read_csv(rel):
        team = r.get("team", "")
        pub = (r.get("vrs_rank") or "").strip()
        if not pub:
            continue
        v, st = vrs_row(team)
        if not v:
            add("VRS standing", rel, team, "vrs_rank", pub, "", meta["blob_url"], f"not resolvable ({st})")
            continue
        add("VRS standing", rel, team, "vrs_rank", pub, str(v["standing"]), v["url"],
            "match" if pub.lstrip("#") == str(v["standing"]) else "MISMATCH")

    # 2) HLTV rank and points labelled with the snapshot date
    tag = hdate.replace("-", "_")
    for rel, rcol, pcol in (("data/6d9c321d/team_ratings_verified.csv", f"hltv_rank_{tag}", "hltv_points"),
                            ("data/844ba68e/ranks.csv", f"hltv_world_rank_{tag}", "hltv_points")):
        rows = read_csv(rel)
        if rows and rcol not in rows[0]:
            add("HLTV rank", rel, "*", rcol, "column absent", "", hurl, "not comparable (different ranking date)")
            continue
        for r in rows:
            team = r.get("team", "")
            h = hltv_by.get(build.norm(team))
            if not h:
                add("HLTV rank", rel, team, rcol, r.get(rcol, ""), "", hurl, "team not in HLTV snapshot")
                continue
            pub = r.get(rcol, "").strip()
            add("HLTV rank", rel, team, rcol, pub, str(h["rank"]), hurl,
                "blank in file" if not pub else ("match" if pub.lstrip("#") == str(h["rank"]) else "MISMATCH"))
            if r.get(pcol, "").strip():
                add("HLTV points", rel, team, pcol, r.get(pcol, ""), str(h["points"]), hurl,
                    "match" if r.get(pcol, "").strip() == str(h["points"]) else "MISMATCH")
    rel = "lines/reference_ranks.json"
    f = REPO / rel
    if f.exists():
        j = json.loads(f.read_text())
        note = j.get("snapshot_note", "")
        m = re.search(r"dated (\d{4}-\d{2}-\d{2})", note)
        if m and hdate and m.group(1) != hdate:
            add("HLTV ranking date", rel, "snapshot_note", "date", m.group(1), hdate, hurl,
                "MISMATCH (official page reads '" + hltv.get("ranking_date_text", "") + "')")
        for team, v in (j.get("teams") or {}).items():
            h = hltv_by.get(build.norm(team))
            if not h:
                continue
            ok = str(v.get("rank")) == str(h["rank"]) and str(v.get("points")) == str(h["points"])
            add("HLTV rank+points", rel, team, "rank/points", f"{v.get('rank')}/{v.get('points')}",
                f"{h['rank']}/{h['points']}", hurl, "match" if ok else "MISMATCH")

    # 3) Fixture identity/times vs Hotspawn TransferState
    ts = {str(f["id"]): f for f in fx["fixtures"]}

    def chk_fixture(rel, fid, ta, tb, start_utc_text):
        f = ts.get(fid)
        if not f:
            add("Fixture", rel, fid, "id", fid, "", build.LOBBY, "not in current TransferState")
            return
        off = build.utc(f["scheduled_start_time"])
        pa, pb = f["participants0_name"], f["participants1_name"]
        teams_ok = {build.norm(ta), build.norm(tb)} == {build.norm(pa), build.norm(pb)}
        add("Fixture teams", rel, fid, "teams", f"{ta} vs {tb}", f"{pa} vs {pb}", build.LOBBY,
            "match" if teams_ok else "MISMATCH")
        m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", start_utc_text or "")
        if m:
            add("Fixture start (UTC)", rel, fid, "start", start_utc_text, off + " UTC", build.LOBBY,
                "match" if f"{m[1]} {m[2]}:{m[3]}" == off else "MISMATCH")

    for r in read_csv("data/6d9c321d/ng_state_86_fixtures.csv"):
        chk_fixture("data/6d9c321d/ng_state_86_fixtures.csv", r.get("hotspawn_id", ""), r.get("team1", ""),
                    r.get("team2", ""), r.get("utc_start", ""))
    for r in read_csv("data/fixtures.csv"):
        m = re.search(r"-(\d{6,8})$", (r.get("hotspawn_url") or "").rstrip("/"))
        if m:
            chk_fixture("data/fixtures.csv", m.group(1), r.get("team_a", ""), r.get("team_b", ""), r.get("start_utc", ""))
    for r in read_csv("lines/analysis.csv"):
        if (r.get("sport") or "").lower() == "cs2":
            chk_fixture("lines/analysis.csv", str(r.get("match_id", "")), r.get("team_a", ""), r.get("team_b", ""),
                        r.get("scheduled_start_utc", ""))

    dest = ROOT / "data" / "crosscheck.csv"
    dest.parent.mkdir(parents=True, exist_ok=True)
    cols = ["check", "file", "key", "field", "published", "official", "official_source", "status", "file_url"]
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(out)
    from collections import Counter
    c = Counter((o["file"], o["status"].split(" ")[0]) for o in out)
    for k, v in sorted(c.items()):
        print(k, v)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
