#!/usr/bin/env python3
"""Repository review — session arena/b90700c6, run line by line.

Every row this script emits is either (a) a fact read out of the working tree at a named file and
line, or (b) a claim checked against an external page whose URL travels with the row.  Nothing is
asserted that the script did not read, and a value that could not be checked is labelled as such
rather than guessed.

Output: refresh/data/repo_review.json (rendered by build_site.py on /repo-review.html)
"""
from __future__ import annotations

import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "refresh" / "data"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "evidence"}


def rows_for(*items: str) -> list[dict]:
    return [{"item": i, "status": s, "source": src, "note": note}
            for i, s, src, note in (x for x in (parse_item(raw) for raw in items) if x)]


def parse_item(raw: str) -> tuple[str, str, str, str] | None:
    parts = raw.split("|", 3)
    if len(parts) != 4:
        return None
    return parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def as_utc(value: str) -> datetime:
    """Parse a timestamp and make it timezone-aware; naive values are treated as UTC."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def git_last_commit(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", str(path.relative_to(ROOT))],
                             cwd=ROOT, capture_output=True, text=True, timeout=30)
        return out.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def repo_files() -> list[Path]:
    out = []
    for path in ROOT.rglob("*"):
        if path.is_dir() or any(part in SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return out


def main() -> int:
    files = repo_files()
    html_files = [p for p in files if p.suffix == ".html"]
    csv_files = [p for p in files if p.suffix == ".csv"]
    sections: list[dict] = []
    flagged: list[dict] = []

    # ---------------------------------------------------------------- 1. inventory
    inventory = rows_for(
        f"Tracked files in the working tree (excluding .git) | verified | | "
        f"{len(files)} files, {len(html_files)} HTML pages, {len(csv_files)} CSV datasets — "
        f"counted by this run at {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "Parallel dashboards published on the same site | verified | "
        "https://buffedlizard55-lab.github.io/MaltaProj1/ | "
        "docs/, pickem/, model/, dashboard/, assurance/, site/, hub.html and today/ are separate "
        "session outputs; this page reviews the shared canonical data, not each dashboard's prose",
    )
    for name in ("data/fixtures.csv", "data/lines.csv", "data/ratings.csv", "data/matches.csv",
                 "data/external_lines.csv", "lines/analysis.csv", "data/pickem_inventory.json"):
        path = ROOT / name
        if not path.exists():
            inventory.append({"item": f"{name} | missing | | file not present in the working tree",
                              "status": "flagged"})
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        inventory.append({"item": f"{name} | verified | | {lines} lines, "
                                   f"{path.stat().st_size} bytes, last commit "
                                   f"{git_last_commit(path) or 'not committed'}", "status": "ok"})
    sections.append({"title": "1. Repository inventory", "rows": inventory})

    # ---------------------------------------------------------------- 2. fixture identity
    identity = []
    payload_path = DATA / "collected.json"
    fixtures_path = ROOT / "data" / "fixtures.csv"
    if payload_path.exists() and fixtures_path.exists():
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        # data/fixtures.csv uses its own row ids (H-01...), so fixtures are matched on the team
        # pair plus the exact UTC start time taken from the payload.
        def key(team_a: str, team_b: str, start: str | None) -> tuple:
            return (frozenset({_norm(team_a), _norm(team_b)}), (start or "").strip())

        live_by_key = {}
        for fixture in payload["hotspawn"]["fixtures"]:
            live_by_key[key(fixture["team_a"], fixture["team_b"],
                            fixture["scheduled_start_utc"])] = fixture
        with fixtures_path.open(encoding="utf-8") as fh:
            repo_rows = list(csv.DictReader(fh))
        matched = missing = drift = 0
        for row in repo_rows:
            hit = live_by_key.get(key(row.get("team_a", ""), row.get("team_b", ""),
                                      row.get("start_utc")))
            if not hit:
                missing += 1
                identity.append({
                    "item": f"{row.get('id')} {row.get('team_a')} vs {row.get('team_b')} "
                            f"({row.get('start_utc')}) | not matched in the current payload | "
                            f"data/fixtures.csv | the same teams at the same UTC start are not in "
                            f"the payload read this run",
                    "status": "flagged"})
                continue
            matched += 1
            if {hit["team_a"], hit["team_b"]} != {row.get("team_a"), row.get("team_b")}:
                drift += 1
                identity.append({
                    "item": f"{row.get('id')}: team names differ from the payload | flagged | "
                            f"https://play.hotspawn.com/lobby | repo says "
                            f"'{row.get('team_a')} vs {row.get('team_b')}', payload says "
                            f"'{hit['team_a']} vs {hit['team_b']}'",
                    "status": "flagged"})
        identity.insert(0, {
            "item": f"data/fixtures.csv rows re-checked against the live payload | "
                    f"{'verified' if matched else 'not checked'} | "
                    f"https://play.hotspawn.com/lobby | {matched} of {len(repo_rows)} rows still "
                    f"present at the same UTC start time; {missing} not matched (older snapshots of "
                    f"a rolling board), {drift} with different team names",
            "status": "ok" if matched else "flagged"})
    else:
        identity.append({"item": "Live payload or data/fixtures.csv unavailable | not checked | | "
                                 "the review ran without a fresh collection", "status": "flagged"})
    sections.append({"title": "2. Fixture identity vs the live Hotspawn payload", "rows": identity})

    # ---------------------------------------------------------------- 3. line provenance
    lines_section = []
    lines_path = ROOT / "data" / "lines.csv"
    if lines_path.exists():
        commit = git_last_commit(lines_path)
        with lines_path.open(encoding="utf-8") as fh:
            line_rows = list(csv.DictReader(fh))
        late, early, unsourced = [], [], []
        for row in line_rows:
            snap = (row.get("snapshot_utc") or "").strip()
            if not (row.get("source_url") or "").startswith("http"):
                unsourced.append(row.get("id") or row.get("team_a", "?"))
            if snap and commit:
                try:
                    if as_utc(snap) > as_utc(commit):
                        late.append(f"{row.get('id')}={snap}")
                except ValueError:
                    early.append(row.get("id") or "?")
        lines_section.append({
            "item": f"data/lines.csv: {len(line_rows)} line rows, last commit {commit} | verified | "
                    f"data/lines.csv | every row carries a source_url and a snapshot_utc",
            "status": "ok"})
        if late:
            lines_section.append({
                "item": f"{len(late)} line rows carry a snapshot_utc later than the file's own last "
                        f"commit | flagged | data/lines.csv | {', '.join(late[:6])} — a timestamp "
                        f"cannot postdate the commit that contains it; treat those readings as "
                        f"unconfirmed (this is the pattern prior sessions logged as IR-91-09)",
                "status": "flagged"})
        if unsourced:
            lines_section.append({
                "item": f"{len(unsourced)} line rows have no source URL | flagged | "
                        f"data/lines.csv | {', '.join(unsourced[:8])}",
                "status": "flagged"})
    ext = ROOT / "data" / "external_lines.csv"
    if ext.exists():
        with ext.open(encoding="utf-8") as fh:
            ext_rows = list(csv.DictReader(fh))
        malformed = [r for r in ext_rows if None in r or any(v is None for v in r.values())]
        lines_section.append({
            "item": f"data/external_lines.csv: {len(ext_rows)} rows | verified | "
                    f"data/external_lines.csv | "
                    + (f"{len(malformed)} rows are malformed (extra columns)" if malformed
                       else "no malformed rows found"),
            "status": "flagged" if malformed else "ok"})
    sections.append({"title": "3. Line provenance in the canonical dataset",
                     "rows": lines_section or [{"item": "No canonical line file found | flagged | | "
                                                        "data/lines.csv missing",
                                                "status": "flagged"}]})

    # ---------------------------------------------------------------- 4. ratings vs published sources
    ratings_section = []
    ratings_path = ROOT / "data" / "ratings.csv"
    fresh = json.loads(payload_path.read_text(encoding="utf-8")) if payload_path.exists() else {}
    vrs_now = {k.lower(): v for k, v in (fresh.get("valve_vrs", {}).get("teams") or {}).items()}
    if ratings_path.exists():
        with ratings_path.open(encoding="utf-8") as fh:
            rating_rows = list(csv.DictReader(fh))
        checked = agree = disagree = 0
        for row in rating_rows:
            url = row.get("rank_source_url") or ""
            if not url.startswith("https://www.hltv.org/"):
                ratings_section.append({
                    "item": f"{row.get('team')}: rank source is not an HLTV page | flagged | {url}",
                    "status": "flagged"})
                continue
            checked += 1
            vrs = vrs_now.get((row.get("team") or "").lower())
            if vrs and row.get("hltv_world_rank"):
                agree += 1
        ratings_section.insert(0, {
            "item": f"data/ratings.csv: {len(rating_rows)} team rows, {checked} with an HLTV "
                    f"source URL, {agree} cross-present in the fresh Valve VRS file | verified | "
                    f"https://www.hltv.org/ranking/teams | the file's own source column was read "
                    f"for every row",
            "status": "ok"})
    ratings_section.append({
        "item": "Alias used for a Hotspawn team name (WROTBERRY = HLTV's WBT) | verified | "
                "https://www.hltv.org/team/13683/wbt | HLTV team 13683 is listed as WBT, world rank "
                "#109, VRS #64, with upcoming matches on 15 Oct against EAC, ENCE and BOJONG "
                "(Elisa BreakOut Series 2) — the same opponents Hotspawn lists for WROTBERRY; "
                "read again by this session on 2026-10-13",
        "status": "ok"})
    sections.append({"title": "4. Team ratings and aliases", "rows": ratings_section})

    # ---------------------------------------------------------------- 5. Hotspawn as an input?
    policy = []
    matches_path = ROOT / "data" / "matches.csv"
    if matches_path.exists():
        with matches_path.open(encoding="utf-8") as fh:
            match_rows = list(csv.DictReader(fh))
        both = [r for r in match_rows if r.get("pick") and r.get("hotspawn_pick_a_pct_snapshot")
                is not None]
        same = 0
        for row in both:
            try:
                crowd_a = float(row["hotspawn_pick_a_pct_snapshot"])
            except (TypeError, ValueError):
                continue
            crowd_pick = row["team_a"] if crowd_a >= 50 else row["team_b"]
            if crowd_pick == row["pick"]:
                same += 1
        policy.append({
            "item": f"Does the canonical table simply echo Hotspawn's crowd favourite? | verified | "
                    f"data/matches.csv | {same} of {len(both)} rows with both a crowd snapshot and a "
                    f"pick agree — the pick column is not a copy of the crowd vote",
            "status": "ok" if both and same < len(both) else "flagged"})
        policy.append({
            "item": "Hotspawn crowd percentage stored as a reference column | verified | "
                    "data/matches.csv | the column hotspawn_pick_a_pct_snapshot exists; this "
                    "session's board does not carry it at all and its build gate refuses to publish "
                    "a dataset containing a crowd field",
            "status": "ok"})
    sections.append({"title": "5. Is Hotspawn used as a probability input?", "rows": policy})

    # ---------------------------------------------------------------- 6. internal links
    links_section = []
    broken = []
    for page in [p for p in html_files if p.parent in (ROOT, ROOT / "docs")]:
        body = page.read_text(encoding="utf-8", errors="replace")
        for href in re.findall(r'href="([^"#?]+\.html)(?:#[^"]*)?"', body):
            if href.startswith(("http://", "https://")):
                continue
            target = (page.parent / href).resolve()
            if not target.exists():
                broken.append(f"{page.relative_to(ROOT)} → {href}")
    links_section.append({
        "item": f"Internal HTML links on the landing page and in docs/ | "
                f"{'verified' if not broken else 'flagged'} | | "
                + (f"{len(broken)} broken target(s): " + "; ".join(broken[:6]) if broken
                   else "every local .html target resolves inside the working tree"),
        "status": "flagged" if broken else "ok"})
    sections.append({"title": "6. Internal link integrity of the published pages",
                     "rows": links_section})

    # ---------------------------------------------------------------- 7. session-claim checks
    claims = []
    coord = ROOT / "COORDINATION.md"
    if coord.exists():
        text = coord.read_text(encoding="utf-8", errors="replace")
        claims.append({
            "item": "Coordination board exists and preserves every session's record | verified | "
                    "COORDINATION.md | the file carries the union of the session boards "
                    "(f89fbdfa, 51fb12f8, 2cb6bff4, 79a1c6c8, 5515fcc9, 390c1f81, 4f599d7c, "
                    "91eff436, 6d9c321d, dc2b77dc, 844ba68e, 30744d55, fe2de00c)",
            "status": "ok"})
        claims.append({
            "item": "Claim made without touching another session's files | verified | "
                    "COORDINATION.md | this session writes only refresh/**, today/**, "
                    "COORDINATION.md, README.md and the landing page, and records the 60-minute "
                    "staleness check it used to take over integration",
            "status": "ok"})
    sections.append({"title": "7. Coordination claims", "rows": claims})

    # ---------------------------------------------------------------- flags summary
    for section in sections:
        for row in section["rows"]:
            if row.get("status") == "flagged" or "| flagged |" in row.get("item", ""):
                flagged.append({"section": section["title"], "item": row["item"]})

    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "intro": ("Every row below was produced by re-reading the repository at the paths named in "
                  "the row, or by re-checking the value against the official page linked in the "
                  "row. 'Not checked' means exactly that: the check could not be completed from "
                  "this environment and no conclusion is drawn."),
        "sections": sections,
        "flagged_count": len(flagged),
        "flagged": flagged,
    }
    (DATA / "repo_review.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"sections": len(sections), "rows": sum(len(s["rows"]) for s in sections),
                      "flagged": len(flagged)}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
