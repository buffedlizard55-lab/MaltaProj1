#!/usr/bin/env python3
"""O-01: originate OUR OWN line for every Hotspawn CS2 Pick'em fixture (session arena/91eff436).

Inputs (written by model/fetch.py, each with URL, fetch time and SHA-256):
  model/input/hotspawn_cs2_fixtures.json  fixture identity only (pick % dropped on ingest)
  model/input/vrs/standings_global_*.md   Valve Regional Standings, official Valve GitHub data
  model/input/vrs/meta.json               Valve repo commit, path and standings date
  model/input/hltv_ranking.json           HLTV World Ranking (roster cross-check, display)

Model: Valve's own expected-win-rate function from the VRS repository
(model/fit.js -> Fit.priorWinExpectation, default rd = 75, with model/glicko.js). Algebraically:
    P(A beats B) = 1 / (1 + 10 ** (-g * (pts_A - pts_B) / 400))
    g = 1 / sqrt(1 + 3 * q^2 * rd^2 / pi^2),  q = ln(10) / 400,  rd = 75
model/test_model.py checks this closed form against Valve's actual JavaScript.

Team resolution (no fuzzy matching, nothing inferred):
  1. A VRS row whose name equals the Hotspawn name (case-insensitive) is a candidate.
  2. If HLTV's ranking lists the same name, its player list is compared with each candidate's
     roster. Valve's model/team.js treats rosters sharing >= 3 players as the same team
     (TEAM_OVERLAP_TO_SHARE_ROSTER = 3).
  3. Exactly one qualifying VRS row: use it. Several: AMBIGUOUS. None: NOT IN VRS or
     ROSTER MISMATCH. AMBIGUOUS, NOT IN VRS and ROSTER MISMATCH all leave the line blank and
     raise a flag.
Hotspawn pick percentages never reach this script: fetch.py drops them on ingest.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INP = ROOT / "input"
OUT = ROOT / "data"
SITE = ROOT / "index.html"

Q = math.log(10) / 400.0
RD = 75.0  # Valve model/fit.js defaultGlickoParams.rd
G = 1.0 / math.sqrt(1.0 + 3.0 * Q * Q * RD * RD / (math.pi ** 2))
OVERLAP = 3  # Valve model/team.js TEAM_OVERLAP_TO_SHARE_ROSTER

VALVE_REPO = "https://github.com/ValveSoftware/counter-strike_regional_standings"
VALVE_FIT = VALVE_REPO + "/blob/{c}/model/fit.js"
VALVE_GLICKO = VALVE_REPO + "/blob/{c}/model/glicko.js"
VALVE_TEAM = VALVE_REPO + "/blob/{c}/model/team.js"
VALVE_README = VALVE_REPO + "/blob/{c}/readme.md"
LOBBY = "https://play.hotspawn.com/cs2-pickems"


def valve_expected(pa: float, pb: float) -> float:
    """Valve VRS expected win rate of A vs B (fit.js priorWinExpectation, rd=75)."""
    return 1.0 / (1.0 + 10.0 ** (G * (pa - pb) / -400.0))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).casefold()


def utc(ms) -> str:
    if ms in (None, "", "0"):
        return ""
    return datetime.fromtimestamp(int(ms) / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")


def load_inputs():
    fx = json.loads((INP / "hotspawn_cs2_fixtures.json").read_text())
    meta = json.loads((INP / "vrs" / "meta.json").read_text())
    md = INP / "vrs" / Path(meta["path"]).name
    vrs = []
    for i, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        m = re.match(r"\|\s*(\d+)\s*\|\s*(-?\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*\[details\]\((.*?)\)", line)
        if m:
            base = meta["path"].rsplit("/", 1)[0]
            vrs.append({
                "standing": int(m[1]), "points": int(m[2]), "name": m[3].strip(),
                "roster": [p.strip() for p in m[4].split(",") if p.strip()],
                "line": i,
                "url": f"{VALVE_REPO}/blob/{meta['commit']}/{meta['path']}?plain=1#L{i}",
                "details_url": f"{VALVE_REPO}/blob/{meta['commit']}/{base}/{m[5].strip()}",
            })
    hltv_path = INP / "hltv_ranking.json"
    hltv = json.loads(hltv_path.read_text()) if hltv_path.exists() else {"teams": []}
    log_path = INP / "fetch_log.json"
    flog = json.loads(log_path.read_text()) if log_path.exists() else {}
    return fx, meta, vrs, hltv, flog


def overlap(a: list[str], b: list[str]) -> int:
    return len({x.casefold() for x in a} & {x.casefold() for x in b})


def resolve(name: str, vrs: list[dict], hltv_by: dict) -> dict:
    """Resolve one Hotspawn team name to a VRS row. Returns a dict with status and evidence."""
    cands = [r for r in vrs if norm(r["name"]) == norm(name)]
    h = hltv_by.get(norm(name))
    res = {"team": name, "vrs": None, "hltv": h, "candidates": cands, "status": "", "note": ""}
    if h and h.get("players"):
        named_ok = [r for r in cands if overlap(r["roster"], h["players"]) >= OVERLAP]
        if len(named_ok) == 1:
            res.update(vrs=named_ok[0], status="VERIFIED: VRS name + HLTV roster",
                       note=f"{overlap(named_ok[0]['roster'], h['players'])} shared players"
                            + (f"; disambiguates {len(cands)} same-name VRS rows" if len(cands) > 1 else ""))
            return res
        if len(named_ok) > 1:
            res.update(status="AMBIGUOUS", note=f"{len(named_ok)} same-name VRS rows each share >= {OVERLAP} players with HLTV roster")
            return res
        by_roster = [r for r in vrs if overlap(r["roster"], h["players"]) >= OVERLAP]
        if len(by_roster) == 1:
            r = by_roster[0]
            res.update(vrs=r, status="VERIFIED: HLTV roster -> VRS (name differs)",
                       note=f"HLTV '{h['name']}' players match VRS '{r['name']}' ({overlap(r['roster'], h['players'])} shared)")
            return res
        if len(by_roster) > 1:
            res.update(status="AMBIGUOUS", note=f"HLTV roster shares >= {OVERLAP} players with {len(by_roster)} VRS rows")
            return res
        if cands:
            res.update(status="ROSTER MISMATCH", note=f"same-name VRS row(s) share < {OVERLAP} players with HLTV's current roster")
            return res
        res.update(status="NOT IN VRS", note="no VRS row by name or by HLTV roster")
        return res
    if len(cands) == 1:
        res.update(vrs=cands[0], status="VERIFIED: VRS name", note="not in HLTV ranking; roster not cross-checked")
    elif len(cands) > 1:
        res.update(status="AMBIGUOUS", note=f"{len(cands)} same-name VRS rows; no HLTV roster to disambiguate")
    else:
        res.update(status="NOT IN VRS", note="not in Valve Regional Standings (and not in HLTV ranking)")
    return res


def band(p: float) -> str:
    q = max(p, 1 - p)
    return "strong" if q >= 0.75 else ("lean" if q >= 0.60 else "toss-up")


def main() -> int:
    fx, meta, vrs, hltv, flog = load_inputs()
    commit = meta["commit"]
    hltv_by = {norm(t["name"]): t for t in hltv.get("teams", [])}
    hltv_url = hltv.get("canonical_url", "https://www.hltv.org/ranking/teams")
    fetched = fx["fetched_utc"]
    week = fx.get("pickem_week") or {}
    week_start = week.get("weekStartUtc", "")
    fetched_dt = datetime.strptime(fetched, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    ws_dt = datetime.fromisoformat(week_start.replace("Z", "+00:00")) if week_start else None
    perm = fx.get("permalinks", {})

    names = sorted({f["participants0_name"] for f in fx["fixtures"]} | {f["participants1_name"] for f in fx["fixtures"]}, key=str.casefold)
    teams = {n: resolve(n, vrs, hltv_by) for n in names}

    rows = []
    for f in sorted(fx["fixtures"], key=lambda f: (int(f["scheduled_start_time"] or 0), f["id"])):
        a, b = f["participants0_name"], f["participants1_name"]
        ra, rb = teams[a], teams[b]
        st = datetime.fromtimestamp(int(f["scheduled_start_time"]) / 1000, timezone.utc)
        if ws_dt and st < ws_dt:
            section = "stale"      # scheduled before the current pick'em week, still status=scheduled
        elif st < fetched_dt:
            section = "started"    # inside this pick'em week but start time already passed at snapshot
        else:
            section = "upcoming"
        row = {
            "hotspawn_match_id": f["id"], "section": section,
            "scheduled_start_utc": utc(f["scheduled_start_time"]), "lock_utc": utc(f["lock_time"]),
            "hotspawn_status": f["status"], "competition": f["competition_name"], "tier": (f["tier"] or "").upper(),
            "stage": f["stage"] or "", "best_of": f["best_of"] if f["best_of"] is not None else "",
            "team_a": a, "team_b": b,
            "hotspawn_url": perm.get(str(f["id"]), LOBBY),
        }
        for side, r in (("a", ra), ("b", rb)):
            v, h = r["vrs"], r["hltv"]
            row[f"vrs_{side}_name"] = v["name"] if v else ""
            row[f"vrs_{side}_standing"] = v["standing"] if v else ""
            row[f"vrs_{side}_points"] = v["points"] if v else ""
            row[f"vrs_{side}_url"] = v["url"] if v else ""
            row[f"hltv_{side}_rank"] = h["rank"] if h else ""
            row[f"hltv_{side}_url"] = f"https://www.hltv.org/team/{h['team_id']}/{h['slug']}" if h and h.get("team_id") else ""
            row[f"resolution_{side}"] = r["status"]
        reasons = []
        if ra["vrs"] and rb["vrs"] and ra["vrs"] is not rb["vrs"]:
            p = valve_expected(ra["vrs"]["points"], rb["vrs"]["points"])
            row.update({
                "own_p_a": round(100 * p, 1), "own_p_b": round(100 * (1 - p), 1),
                "fair_odds_a": round(1 / p, 2), "fair_odds_b": round(1 / (1 - p), 2),
                "pick": a if p > 0.5 else (b if p < 0.5 else ""),
                "confidence": band(p) if p != 0.5 else "toss-up",
                "line_status": "OWN LINE",
            })
            if any(r["status"].startswith("VERIFIED: HLTV roster") for r in (ra, rb)):
                reasons.append("team matched to VRS by roster (name differs) - review")
        else:
            for r in (ra, rb):
                if not r["vrs"]:
                    reasons.append(f"{r['team']}: {r['status']}")
            if ra["vrs"] is not None and ra["vrs"] is rb["vrs"]:
                reasons.append("both names resolve to the same VRS row")
            row.update({"own_p_a": "", "own_p_b": "", "fair_odds_a": "", "fair_odds_b": "",
                        "pick": "", "confidence": "", "line_status": "BLANK - UNVERIFIED"})
        if section == "stale":
            reasons.append("Hotspawn lists a scheduled date before this pick'em week (stale listing)")
        row["notes"] = "; ".join(reasons)
        rows.append(row)

    # ---------- flags ----------
    flags = []

    def flag(fid, sev, subject, detail, links):
        flags.append({"id": fid, "severity": sev, "subject": subject, "detail": detail, "links": " ".join(links)})

    def fixtures_of(t):
        return [r["hotspawn_match_id"] for r in rows if t in (r["team_a"], r["team_b"])]

    n = 0
    for t, r in teams.items():
        st = r["status"]
        if st.startswith("VERIFIED: VRS name +") or st == "VERIFIED: VRS name":
            continue
        n += 1
        fid = f"M-{n:02d}"
        ids = ", ".join(fixtures_of(t))
        links = [LOBBY]
        if r["hltv"] and r["hltv"].get("team_id"):
            links.append(f"https://www.hltv.org/team/{r['hltv']['team_id']}/{r['hltv']['slug']}")
        if st == "NOT IN VRS":
            flag(fid, "unverified", f"{t}: not in Valve Regional Standings ({meta['standings_date']})",
                 f"No VRS row named '{t}'" + (" and no VRS roster matching HLTV's" if r["hltv"] else "")
                 + f". Own line left BLANK for fixture(s) {ids}. Near-name rows are NOT substituted.",
                 links + [meta["blob_url"]])
        elif st == "AMBIGUOUS":
            c = "; ".join(f"#{x['standing']} {x['name']} {x['points']} pts [{', '.join(x['roster'])}]" for x in r["candidates"]) or r["note"]
            flag(fid, "unverified", f"{t}: ambiguous VRS identity",
                 f"{r['note']}. Candidates: {c}. Line left BLANK for fixture(s) {ids}.",
                 links + [x["url"] for x in r["candidates"]])
        elif st == "ROSTER MISMATCH":
            c = "; ".join(f"#{x['standing']} {x['name']} [{', '.join(x['roster'])}]" for x in r["candidates"])
            flag(fid, "unverified", f"{t}: VRS roster differs from HLTV current roster",
                 f"HLTV lists [{', '.join(r['hltv']['players'])}]; VRS same-name row(s): {c}. Line left BLANK for fixture(s) {ids}.",
                 links + [x["url"] for x in r["candidates"]])
        elif st.startswith("VERIFIED: HLTV roster"):
            v = r["vrs"]
            flag(fid, "needs review", f"{t}: rated via roster as VRS '{v['name']}'",
                 f"{r['note']}. HLTV players [{', '.join(r['hltv']['players'])}] vs VRS roster [{', '.join(v['roster'])}]. "
                 f"Line published for fixture(s) {ids}; please confirm the org/name change.",
                 links + [v["url"]])

    stale = [r for r in rows if r["section"] == "stale"]
    if stale:
        first, last = stale[0]["scheduled_start_utc"], stale[-1]["scheduled_start_utc"]
        flag("M-S1", "needs review", f"{len(stale)} Hotspawn fixtures have scheduled dates before this pick'em week",
             f"Hotspawn's TransferState lists {len(stale)} of {len(rows)} CS2 fixtures with scheduled_start_time "
             f"{first} .. {last} UTC (week starts {week_start}), still status='scheduled' and lock times in the past. "
             "They are not rendered as cards in the lobby. Lines are still computed (current VRS) for completeness but "
             "are informational only.", [LOBBY])
    hdr, tot = fx.get("lobby_header_matches_this_week"), fx.get("lobby_filter_all_tiers")
    cur = len(rows) - len(stale)
    if hdr is not None and hdr != cur:
        flag("M-S2", "needs review", "Hotspawn lobby counts disagree",
             f"Lobby header says '{hdr} matches this week'; filter says All tiers ({tot}); TransferState holds "
             f"{len(rows)} fixtures, of which {cur} are dated inside the current pick'em week.", [LOBBY])
    if all(f["best_of"] is None for f in fx["fixtures"]):
        flag("M-S3", "info", "Series format not published by Hotspawn",
             "best_of / series_format are null for every fixture. Valve's expected win rate is match-level and "
             "format-agnostic, so no BO1/BO3 adjustment is applied.", [LOBBY])
    flag("M-S4", "info", f"Ratings date: VRS standings of {meta['standings_date']}",
         f"Valve publishes the Regional Standings monthly; this run uses {meta['path']} at commit {commit[:10]}. "
         "Results after that date are not reflected.", [meta["blob_url"]])
    flag("M-S5", "info", "Valve's own calibration caveat",
         "Valve's README: the expected-vs-observed slope is shallower than 1; the model 'tends to underestimate win "
         "rates at the low end and overestimate at the high end'. Treat extreme percentages with caution.",
         [VALVE_README.format(c=commit)])
    for k in ("hotspawn", "vrs", "hltv"):
        e = flog.get(k, {})
        if e and not str(e.get("result", "")).startswith("OK"):
            flag(f"M-F-{k}", "needs review", f"Input refresh failed: {k}",
                 f"{e.get('result')} (HTTP {e.get('http_status')}, {e.get('fetched_utc')}). Previous snapshot used.",
                 [e.get("url", "")])

    # ---------- outputs ----------
    OUT.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0].keys())
    with (OUT / "lines.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    trows = []
    for t, r in teams.items():
        v, h = r["vrs"], r["hltv"]
        trows.append({
            "hotspawn_team": t, "resolution": r["status"], "note": r["note"],
            "vrs_name": v["name"] if v else "", "vrs_standing": v["standing"] if v else "",
            "vrs_points": v["points"] if v else "", "vrs_roster": ", ".join(v["roster"]) if v else "",
            "vrs_url": v["url"] if v else "", "vrs_details_url": v["details_url"] if v else "",
            "hltv_rank": h["rank"] if h else "", "hltv_points": h["points"] if h else "",
            "hltv_players": ", ".join(h["players"]) if h else "",
            "hltv_url": f"https://www.hltv.org/team/{h['team_id']}/{h['slug']}" if h and h.get("team_id") else "",
            "fixtures": ", ".join(fixtures_of(t)),
        })
    with (OUT / "teams.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(trows[0].keys()))
        w.writeheader()
        w.writerows(trows)
    with (OUT / "flags.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "severity", "subject", "detail", "links"])
        w.writeheader()
        w.writerows(flags)
    inputs = {
        "hotspawn": {"url": fx["source_url"], "fetched_utc": fetched, "html_sha256": fx.get("html_sha256"),
                     "fixtures": len(rows), "pickem_week": week},
        "vrs": {k: meta[k] for k in ("repo", "commit", "commit_date", "path", "standings_date", "sha256", "blob_url")},
        "hltv": {k: hltv.get(k) for k in ("canonical_url", "ranking_date", "fetched_utc", "html_sha256", "team_count")},
        "model": {"formula": "P(A)=1/(1+10^(-g*(ptsA-ptsB)/400)), g=1/sqrt(1+3q^2*rd^2/pi^2), q=ln10/400, rd=75",
                  "g": round(G, 6), "valve_fit_js": VALVE_FIT.format(c=commit),
                  "valve_glicko_js": VALVE_GLICKO.format(c=commit), "roster_overlap_rule": OVERLAP,
                  "valve_team_js": VALVE_TEAM.format(c=commit)},
    }
    payload = {"inputs": inputs, "fixtures": rows, "teams": trows, "flags": flags}
    (OUT / "lines.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    # Digest over the substance (fixtures/teams/flags + input identities, not fetch timestamps).
    subst = json.dumps({"f": rows, "t": trows, "x": flags, "v": meta["commit"], "h": hltv.get("ranking_date")},
                       sort_keys=True, ensure_ascii=False)
    (OUT / "digest.txt").write_text(hashlib.sha256(subst.encode()).hexdigest() + "\n")
    SITE.write_text(render(payload, meta, hltv, fx, hltv_url))
    n_line = sum(1 for r in rows if r["line_status"] == "OWN LINE")
    print(f"fixtures={len(rows)} own_lines={n_line} blank={len(rows) - n_line} teams={len(trows)} flags={len(flags)}")
    return 0


# ---------------------------------------------------------------- HTML rendering
CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#5d6778;--line:#e3e6eb;--acc:#2457d6;--ok:#127a3c;--warn:#a15c00;--bad:#b42318}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--ink)}
header{background:#111827;color:#fff;padding:14px 20px}header a{color:#c7d2fe}header h1{margin:0;font-size:18px}
header p{margin:4px 0 0;color:#cbd5e1;font-size:13px}nav{display:flex;gap:6px;flex-wrap:wrap;padding:10px 20px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
nav a{padding:6px 10px;border-radius:6px;text-decoration:none;color:var(--ink);background:#eef1f6}nav a:hover{background:#dfe5f0}
main{padding:16px 20px;max-width:1500px;margin:auto}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px}.card b{display:block;font-size:22px}.card span{color:var(--mute);font-size:12px}
section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:16px}h2{font-size:16px;margin:2px 0 8px}
.note{color:var(--mute);font-size:12.5px;margin:4px 0 8px}.tw{overflow:auto;max-height:75vh}table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{border-bottom:1px solid var(--line);padding:5px 7px;text-align:left;vertical-align:top;white-space:nowrap}th{background:#f1f3f7;position:sticky;top:0;cursor:pointer}
td.wrap{white-space:normal;min-width:260px}tr:hover td{background:#fafbfd}.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11.5px;background:#eef1f6}.ok{background:#e5f4ea;color:var(--ok)}.warn{background:#fff3e0;color:var(--warn)}.bad{background:#fde8e7;color:var(--bad)}
.pick{font-weight:600}input[type=search]{padding:6px 9px;border:1px solid var(--line);border-radius:6px;min-width:260px;margin-bottom:8px}
a{color:var(--acc)}footer{color:var(--mute);font-size:12px;padding:10px 20px 30px;max-width:1500px;margin:auto}
"""

JS = """
function filt(inp,id){const q=inp.value.toLowerCase();document.querySelectorAll('#'+id+' tbody tr').forEach(r=>{r.style.display=r.textContent.toLowerCase().includes(q)?'':'none'})}
document.querySelectorAll('table.sort').forEach(t=>{t.querySelectorAll('th').forEach((th,i)=>{th.title='Click to sort';th.addEventListener('click',()=>{const b=t.tBodies[0];const rs=[...b.rows];const d=th.dataset.d=th.dataset.d==='a'?'d':'a';
rs.sort((x,y)=>{const A=x.cells[i].dataset.v??x.cells[i].textContent.trim(),B=y.cells[i].dataset.v??y.cells[i].textContent.trim();const nA=parseFloat(A),nB=parseFloat(B);
const c=(!isNaN(nA)&&!isNaN(nB))?nA-nB:A.localeCompare(B);return d==='a'?c:-c});rs.forEach(r=>b.appendChild(r))})})});
"""


def e(s) -> str:
    return html.escape("" if s is None else str(s))


def a(url: str, text: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(text)}</a>' if url else ""


def pill(status: str) -> str:
    cls = "ok" if status.startswith("VERIFIED: VRS name") else ("warn" if status.startswith("VERIFIED") else "bad")
    short = {"VERIFIED: VRS name + HLTV roster": "VRS+HLTV roster", "VERIFIED: VRS name": "VRS name",
             "VERIFIED: HLTV roster -> VRS (name differs)": "roster match, name differs"}.get(status, status)
    return f'<span class="pill {cls}">{e(short)}</span>'


def fixture_table(rows, tid):
    head = ("<tr><th>Start (UTC)</th><th>Tournament</th><th>Tier</th><th>Team A</th><th>Team B</th>"
            "<th>VRS pts A</th><th>VRS pts B</th><th>Our P(A)</th><th>Our P(B)</th><th>Fair odds A</th><th>Fair odds B</th>"
            "<th>Pick</th><th>Conf.</th><th>Status</th><th>Sources</th><th>Notes</th></tr>")
    body = []
    for r in rows:
        own = r["line_status"] == "OWN LINE"
        st = '<span class="pill ok">own line</span>' if own and not r["notes"] else (
            '<span class="pill warn">own line - review</span>' if own else '<span class="pill bad">blank - unverified</span>')
        src = " · ".join(x for x in [
            a(r["hotspawn_url"], "Hotspawn fixture"),
            a(r["vrs_a_url"], "VRS A"), a(r["vrs_b_url"], "VRS B"),
            a(r["hltv_a_url"], "HLTV A"), a(r["hltv_b_url"], "HLTV B")] if x)
        pa = f"{r['own_p_a']}%" if own else ""
        pb = f"{r['own_p_b']}%" if own else ""
        body.append(
            f"<tr><td data-v='{e(r['scheduled_start_utc'])}'>{e(r['scheduled_start_utc'])}</td><td>{e(r['competition'])}</td><td>{e(r['tier'])}</td>"
            f"<td>{e(r['team_a'])}</td><td>{e(r['team_b'])}</td>"
            f"<td class=num>{e(r['vrs_a_points'])}</td><td class=num>{e(r['vrs_b_points'])}</td>"
            f"<td class=num data-v='{e(r['own_p_a'])}'>{pa}</td><td class=num data-v='{e(r['own_p_b'])}'>{pb}</td>"
            f"<td class=num>{e(r['fair_odds_a'])}</td><td class=num>{e(r['fair_odds_b'])}</td>"
            f"<td class=pick>{e(r['pick'])}</td><td>{e(r['confidence'])}</td><td>{st}</td><td>{src}</td><td class=wrap>{e(r['notes'])}</td></tr>")
    return (f"<input type=search placeholder='Filter rows…' oninput=\"filt(this,'{tid}')\">"
            f"<div class=tw><table id='{tid}' class=sort><thead>{head}</thead><tbody>{''.join(body)}</tbody></table></div>")


def render(p, meta, hltv, fx, hltv_url) -> str:
    rows, teams, flags, inp = p["fixtures"], p["teams"], p["flags"], p["inputs"]
    up = [r for r in rows if r["section"] in ("upcoming", "started")]
    stale = [r for r in rows if r["section"] == "stale"]
    n_line = sum(1 for r in rows if r["line_status"] == "OWN LINE")
    n_up_line = sum(1 for r in up if r["line_status"] == "OWN LINE")
    commit = meta["commit"]
    trs = []
    for t in teams:
        trs.append(
            f"<tr><td>{e(t['hotspawn_team'])}</td><td>{pill(t['resolution'])}</td><td>{a(t['vrs_url'], t['vrs_name'])}</td>"
            f"<td class=num>{e(t['vrs_standing'])}</td><td class=num>{e(t['vrs_points'])}</td><td class=wrap>{e(t['vrs_roster'])}</td>"
            f"<td>{a(t['vrs_details_url'], 'VRS details' if t['vrs_details_url'] else '')}</td>"
            f"<td class=num>{e(t['hltv_rank'])}</td><td class=num>{e(t['hltv_points'])}</td><td class=wrap>{e(t['hltv_players'])}</td>"
            f"<td>{a(t['hltv_url'], 'HLTV team')}</td><td class=wrap>{e(t['note'])}</td><td class=wrap>{e(t['fixtures'])}</td></tr>")
    frs = []
    for f in flags:
        cls = {"unverified": "bad", "needs review": "warn"}.get(f["severity"], "")
        links = " ".join(a(u, f"[{i + 1}]") for i, u in enumerate(f["links"].split()) if u)
        frs.append(f"<tr><td>{e(f['id'])}</td><td><span class='pill {cls}'>{e(f['severity'])}</span></td><td class=wrap>{e(f['subject'])}</td>"
                   f"<td class=wrap>{e(f['detail'])}</td><td>{links}</td></tr>")
    h = inp["hltv"]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Own lines (Valve VRS model) — Hotspawn CS2 Pick'em</title><style>{CSS}</style></head><body>
<header><h1>Own lines — Valve Regional Standings model</h1>
<p>Our own originated win probability for every Hotspawn CS2 Pick'em fixture. Hotspawn crowd picks are never used. Analysis only — not betting advice.
&nbsp;<a href="../">← main dashboard</a></p></header>
<nav><a href="#week">This week</a><a href="#stale">Stale listings</a><a href="#teams">Team ratings</a><a href="#flags">Flagged for review</a><a href="#method">Method &amp; sources</a><a href="data/lines.csv">lines.csv</a><a href="data/teams.csv">teams.csv</a><a href="data/flags.csv">flags.csv</a></nav>
<main>
<div class=cards>
<div class=card><b>{len(rows)}</b><span>CS2 fixtures in Hotspawn TransferState</span></div>
<div class=card><b>{len(up)}</b><span>dated in current pick'em week</span></div>
<div class=card><b>{n_up_line}/{len(up)}</b><span>this-week fixtures with our line</span></div>
<div class=card><b>{n_line}/{len(rows)}</b><span>all fixtures with our line</span></div>
<div class=card><b>{len(flags)}</b><span>flags</span></div>
<div class=card><b>{e(meta['standings_date'])}</b><span>VRS standings date</span></div>
</div>
<p class=note>Fixtures: <a href="{e(inp['hotspawn']['url'])}">{e(inp['hotspawn']['url'])}</a>, fetched {e(inp['hotspawn']['fetched_utc'])} (pick'em week {e((inp['hotspawn']['pickem_week'] or {}).get('weekStartUtc', ''))} → {e((inp['hotspawn']['pickem_week'] or {}).get('weekEndUtc', ''))}).
Ratings: <a href="{e(meta['blob_url'])}">Valve VRS {e(meta['path'])}</a> @ <code>{e(commit[:10])}</code>.
Roster cross-check: <a href="{e(h.get('canonical_url') or hltv_url)}">HLTV World Ranking {e(h.get('ranking_date') or '')}</a> (fetched {e(h.get('fetched_utc') or '')}). All times UTC.</p>
<section id=week><h2>This week — {len(up)} fixtures</h2>
<p class=note>Blank = a team could not be matched to an official VRS rating without guessing; see the Notes column and Flagged for review. "Pick" is the side our line favours; confidence: strong ≥75%, lean 60–75%, toss-up &lt;60%.</p>
{fixture_table(up, 'tw')}</section>
<section id=stale><h2>Stale listings — {len(stale)} fixtures scheduled before this pick'em week</h2>
<p class=note>Hotspawn's own data still lists these as status "scheduled" with past start/lock times; they are not shown as cards in the lobby. Lines are computed for completeness only.</p>
{fixture_table(stale, 'ts')}</section>
<section id=teams><h2>Team ratings — {len(teams)} Hotspawn team names</h2>
<p class=note>Each Hotspawn name is matched to the Valve Regional Standings by exact (case-insensitive) name; when HLTV's ranking lists the team, its players are compared with the VRS roster (Valve's own rule: ≥{OVERLAP} shared players = same team).</p>
<input type=search placeholder="Filter teams…" oninput="filt(this,'tt')"><div class=tw><table id=tt class=sort><thead><tr><th>Hotspawn team</th><th>Resolution</th><th>VRS team</th><th>VRS #</th><th>VRS pts</th><th>VRS roster</th><th>Details</th><th>HLTV #</th><th>HLTV pts</th><th>HLTV players</th><th>HLTV</th><th>Note</th><th>Fixtures</th></tr></thead><tbody>{''.join(trs)}</tbody></table></div></section>
<section id=flags><h2>Flagged for review — {len(flags)}</h2>
<p class=note>Unverified = value left blank. Needs review = value published but please confirm. Info = context.</p>
<div class=tw><table id=tf class=sort><thead><tr><th>ID</th><th>Severity</th><th>Subject</th><th>Detail</th><th>Sources</th></tr></thead><tbody>{''.join(frs)}</tbody></table></div></section>
<section id=method><h2>Method &amp; sources</h2>
<ol>
<li><b>Fixtures</b> — <a href="{LOBBY}">play.hotspawn.com/cs2-pickems</a> is server-rendered Angular; its <code>&lt;script id="ng-state"&gt;</code> TransferState holds the full fixture list (id, teams, competition, tier, <code>scheduled_start_time</code>). Only identity fields are kept; <code>participants*_picked_percent</code> and <code>total_picks</code> are dropped on ingest.</li>
<li><b>Ratings</b> — official <a href="{VALVE_REPO}">Valve Regional Standings</a> points (global list, {e(meta['standings_date'])}). Each team row links to its exact line in Valve's file and to Valve's per-team details page.</li>
<li><b>Our line</b> — Valve's own expected-win-rate function (<a href="{e(inp['model']['valve_fit_js'])}">fit.js priorWinExpectation</a> with <a href="{e(inp['model']['valve_glicko_js'])}">glicko.js</a>, rd = 75): <code>P(A) = 1 / (1 + 10^(−g·(pts<sub>A</sub> − pts<sub>B</sub>)/400))</code>, g = {inp['model']['g']}. Fair decimal odds = 1/P. This closed form is unit-tested against Valve's actual JavaScript.</li>
<li><b>Roster check</b> — <a href="{e(h.get('canonical_url') or hltv_url)}">HLTV World Ranking</a> player lists vs VRS rosters (<a href="{e(inp['model']['valve_team_js'])}">team.js</a>: ≥{OVERLAP} shared players = same team). Ambiguous, missing or mismatched teams → blank + flag. No fuzzy or near-name matching.</li>
<li><b>Market lines</b> — external bookmaker collection is owned by session 79a1c6c8 (C-02) per <a href="https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/COORDINATION.md">COORDINATION.md</a>; this page does not scrape bookmakers.</li>
</ol>
<p class=note>Reproduce: <code>python3 model/fetch.py &amp;&amp; python3 model/build.py &amp;&amp; python3 model/test_model.py</code>. Refreshed automatically by <code>.github/workflows/model-91eff436.yml</code>.</p>
</section></main>
<footer>Session arena/91eff436 · task O-01 · data files: <a href="data/lines.json">lines.json</a>. Not affiliated with Hotspawn, Valve or HLTV. Not betting advice.</footer>
<script>{JS}</script></body></html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
