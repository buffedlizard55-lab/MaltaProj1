"""Audit of the shipped CS2 boards (session arena/26986a4e). Reads committed files only; no network.
Writes reviews/26986a4e-verification.md. Every number in the output is copied from the input files."""
import csv, re, html, pathlib, collections, json

ROOT = pathlib.Path(__file__).resolve().parents[1]
rows = list(csv.DictReader(open(ROOT / "cs2/data/analysis.csv", encoding="utf-8")))
open_rows = [r for r in rows if r["pickable"] == "yes"]
out = []
w = out.append

def link(url, label):
    return f"[{label}]({url})" if url else "—"

# ---- V26-01: row-by-row recheck of the 28 open rows on cs2/ ----
w("## V26-01 — row-by-row recheck of the open CS2 rows (`cs2/data/analysis.csv`)\n")
w("Checks per row: (1) both probabilities present, (2) they sum to 100 ± 0.15, (3) the pick is the team with the higher stated probability, (4) `pick_pct` equals that probability, (5) Hotspawn match URL present, (6) Valve VRS URL for both teams present.\n")
w("| Fixture | Start (UTC) | Tier | Match | Pick | Pick % | Basis | Hotspawn match | Valve VRS (A / B) | Checks | Flags |")
w("|---|---|---|---|---|---|---|---|---|---|---|")
results = collections.Counter()
for r in open_rows:
    a, b = r["team_a"], r["team_b"]
    pa = r["own_p_a_pct"] if r["own_p_a_pct"] else ""
    # the stated probabilities used by the board: consensus if present else own line
    sa = r["consensus_p_a_pct"] or r["own_p_a_pct"]
    sb = r["consensus_p_b_pct"] or r["own_p_b_pct"]
    checks = []
    if not sa or not sb:
        checks.append("no probability → blank, flagged")
        ok = "BLANK (expected)"
    else:
        fa, fb = float(sa), float(sb)
        if abs(fa + fb - 100) > 0.15: checks.append(f"sum {fa+fb:.2f}")
        exp = a if fa > fb else b
        if r["pick"] != exp: checks.append(f"pick {r['pick']} ≠ higher {exp}")
        if abs(float(r["pick_pct"]) - max(fa, fb)) > 0.05: checks.append("pick_pct mismatch")
        ok = "PASS" if not checks else "FAIL: " + "; ".join(checks)
    results[ok.split(":")[0]] += 1
    hs = link(r["hotspawn_match_url"], "match")
    vrs = f"{link(r['vrs_url_a'], 'A')} / {link(r['vrs_url_b'], 'B')}"
    basis = "external market (de-vigged)" if r["pick_basis"].startswith("external") else "own line (Valve VRS)"
    pick_txt = f"{r['pick']}" if r["pick"] else "**none — flagged**"
    pct = r["pick_pct"] or "—"
    w(f"| {r['fixture_id']} | {r['start_utc'][:16].replace('T',' ')} | {r['tier']} | {a} v {b} | {pick_txt} | {pct} | {basis} | {hs} | {vrs} | {ok} | {r['flags'] or '—'} |")
w("")
no_match_page = [r["fixture_id"] for r in open_rows if not r["hotspawn_match_url"]]
no_vrs = [r["fixture_id"] for r in open_rows if not (r["vrs_url_a"] and r["vrs_url_b"])]
w(f"Result: {dict(results)} across {len(open_rows)} open rows. Valve VRS links for both teams missing on: {no_vrs or 'none'}. Per-match Hotspawn page missing on: {no_match_page or 'none'} (these rows link only to the lobby payload, not a per-match page).\n")

# ---- Cross-check: the two boards on main ----
w("## Cross-check — `cs2/` board vs `oct14/` board (both on `main`)\n")
review = (ROOT / "reviews/8944bb84-verification.md").read_text(encoding="utf-8")
cells = {}
for line in review.splitlines():
    if not line.startswith("| `"):
        continue
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    cells[c[0].strip("`")] = c
cs_by_id = {r["fixture_id"]: r for r in open_rows}
w("| Fixture | Match | `cs2/` pick (pct) | `oct14/` pick (pct) | Same pick? | `cs2/` market (Pinnacle, de-vigged) | `oct14/` source of its prices |")
w("|---|---|---|---|---|---|---|")
disagree_pick = 0
for fid, r in cs_by_id.items():
    if fid not in cells:
        continue
    c = cells[fid]
    if len(c) < 10:
        continue
    m = re.search(r"\*\*(.+?)\*\* — ", c[9])
    oct_pick = re.sub(r"\*", "", c[9]).split(" — ")[0] if " — " in c[9] else c[9]
    cs_pick = r["pick"] or "none"
    same = "—"
    if r["pick"]:
        same = "yes" if oct_pick.split(" (")[0].strip() == r["pick"] else "**NO**"
        if same == "**NO**":
            disagree_pick += 1
    mk = f"{r['market_p_a_pct']} / {r['market_p_b_pct']}" if r["market_p_a_pct"] else "— (no quote)"
    src = "EGamersWorld `bc.game` page (hand-copied; see IRREG-26-02)" if "EGamersWorld" in c[6] else "Pinnacle / other"
    ocp = re.search(r"\((\d+\.\d)%\)", c[9])
    ocp_txt = (ocp.group(1) + "%") if ocp else "—"
    w(f"| {fid} | {r['team_a']} v {r['team_b']} | {cs_pick} ({r['pick_pct'] or '—'}) | {oct_pick} ({ocp_txt}) | {same} | {mk} | {src} |")
w("")
w(f"Picks that differ between the two boards: **{disagree_pick}**. Probabilities differ on most rows (see the `oct14/` review table in `reviews/8944bb84-verification.md`).\n")

# ---- V26-02: refresh cadence (numbers taken from `gh run list`, recorded in the review) ----
w("## V26-02 — refresh cadence (GitHub run history, measured 2026-10-14 ~02:35 UTC)\n")
w("Method: `gh run list --workflow <file> --limit 60 --json event,createdAt`, counting `event == schedule`. Expected = the cron in the workflow file.\n")
w("| Workflow | Declared cron | Expected scheduled runs per 3.6 h | Runs seen | Scheduled runs seen | Window (oldest → newest) |")
w("|---|---|---|---|---|---|")
MEASURED = json.load(open(ROOT / "reviews/26986a4e-cadence.json", encoding="utf-8"))
for m in MEASURED:
    wf_text = (ROOT / ".github/workflows" / m["wf"]).read_text(encoding="utf-8") if (ROOT / ".github/workflows" / m["wf"]).exists() else ""
    cm = re.search(r"cron:\s*[\"']([^\"']+)[\"']", wf_text)
    m["cron"] = cm.group(1) if cm else "none"
    per_hour = 0.0
    fields = m["cron"].split()
    if fields and fields[0] != "none":
        mins = fields[0].split(",")
        hours = fields[1]
        if hours == "*": per_hour = len(mins)
        elif hours.startswith("*/"): per_hour = len(mins) / int(hours[2:])
        else: per_hour = len(mins) / 24.0
    exp = per_hour * 3.6
    w(f"| `{m['wf']}` | `{m['cron']}` | {exp:.1f} | {m['total']} | {m['schedule']} | {m['oldest'][:16]} → {m['newest'][:16]} |")
w("")

(ROOT / "reviews/26986a4e-verification.md").write_text(
    "# arena/26986a4e — verification of the shipped CS2 boards\n\n"
    "Generated by `reviews/26986a4e-audit.py` from committed files. No network access was used; "
    "Hotspawn, HLTV, Pinnacle and Pages are unreachable from the workspace, so their values are taken as committed.\n\n"
    + "\n".join(out), encoding="utf-8")
print("\n".join(out)[:600])

FINDINGS = """
## Irregularities (for the Flagged for Review page and the integration owner)

| ID | Severity | Finding | Evidence (click to verify) |
|---|---|---|---|
| IRREG-26-01 | high | **The two boards on `main` disagree.** `cs2/` shows The Last Resort 50.9% over G2 Ares for fixture 1079623 (its own VRS line); `oct14/` shows G2 Ares 56.7%. The other 26 picks agree, but the probability values differ on most rows (table above). Two live pages with different numbers for the same match is the main confusion the user reported. | [cs2 board](https://buffedlizard55-lab.github.io/MaltaProj1/cs2/) · [oct14 board](https://buffedlizard55-lab.github.io/MaltaProj1/oct14/index.html) · [cs2/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/analysis.csv) · [reviews/8944bb84-verification.md](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/reviews/8944bb84-verification.md) |
| IRREG-26-02 | high | **The 17 EGamersWorld `bc.game` prices on `oct14/` are literal values typed into a build script, not fetched.** `scripts/8944bb84_build.py` stores e.g. `"primary_odds_a": "2.330"` (line ~342) and the workflow never requests EGamersWorld. The same-day `cs2` capture shows EGamersWorld returned HTTP 403 on all three attempts (Cloudflare challenge). Under the brief's rule these are not reproducible from a source and must be blank + flagged; `oct14/` instead labels EGamersWorld an "official verified source". Its headline "OBVIOUS LOCK" calls (e.g. Astralis 90.9%, Legacy 72.9%) depend on them. | [scripts/8944bb84_build.py L315–L358](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/scripts/8944bb84_build.py#L315) · [cs2/data/capture.json (egamersworld block)](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/capture.json) · [EGamersWorld matches](https://egamersworld.com/counterstrike/matches) |
| IRREG-26-03 | medium | **Scheduled refresh is not running on schedule.** The `cs2/` board says "hourly" (`13 * * * *`), but in the observed window it had 0 scheduled runs; `slate-180a42a0` (hourly) had 0 scheduled runs across 22 runs in ~3.4 h. Across all nine cron workflows, 5 scheduled runs appeared in the 200 most recent runs (23:00–02:35 UTC). Data only refreshes when a push happens to trigger a run. This conflicts with the brief's "regularly check for updates". | [GitHub Actions runs](https://github.com/buffedlizard55-lab/MaltaProj1/actions) · [cs2-a174d77f.yml](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/.github/workflows/cs2-a174d77f.yml) · [slate-180a42a0.yml](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/.github/workflows/slate-180a42a0.yml) · [GitHub docs, `schedule` event: \"If the load is sufficiently high enough, some queued jobs may be dropped\"](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows) |
| IRREG-26-04 | medium | **Confusing counts on the front page.** `cs2/` says "89 CS2 fixtures on the board" and "84 fixtures flagged"; 59 of the 89 are June–July 2026 stale records (`lock_utc` in the past). Only 28 are open. The user asked for the matches listed on Hotspawn; the stale records are not listed as open. | [cs2/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/analysis.csv) · [Hotspawn lobby](https://play.hotspawn.com/lobby) |
| IRREG-26-05 | medium | **No pick for fixture 1079624 (FORZE Reload v LFO 10).** Blank is correct under the no-inference rule: LFO 10 is absent from the Valve Oct-5 standings and no market quote exists. Request: a CI collection of the HLTV ranking page for LFO 10 (honest identifiable UA, undated URL) — if an official rank exists, a pick can be derived from it. | [VRS 2026-10-05 standings](https://github.com/ValveSoftware/counter-strike_regional_standings/blob/main/live/2026/standings_global_2026_10_05.md) · [HLTV match 2399301](https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11) · [HLTV ranking](https://www.hltv.org/ranking/teams) |
| IRREG-26-06 | low | **Four rows have no per-match Hotspawn page** (1081111, 1081112, 1081113, 1081120): the lobby payload is the only Hotspawn source for these rows. | [cs2/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/analysis.csv) |
| IRREG-26-07 | medium | **Most open picks are not series probabilities.** 19 of 28 open rows are flagged `A-NO-FORMAT` (best-of not confirmed) and 21 are `A-NO-LINE` (no bookmaker quote). The own-line value is a Valve rating-points curve applied to the match, not a verified BO1/BO3 series model. | [cs2/data/analysis.csv](https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/cs2/data/analysis.csv) · [Valve VRS source](https://github.com/ValveSoftware/counter-strike_regional_standings) |

## Requests (logged in COORDINATION.md; no cross-owner edits made)

- To `arena/8944bb84` (owner of `oct14/**`, `scripts/8944bb84_build.py`): remove or blank the 17 EGamersWorld-derived prices (IRREG-26-02) and recompute, or mark them "unverified — not reproducible"; reconcile the probabilities with `cs2/` or state the difference on the page; correct the "official verified source" label for EGamersWorld.
- To `arena/a174d77f` (owner of `cs2/**`, `.github/workflows/cs2-a174d77f.yml`): add an in-page executive summary with anchor links to each tournament section and each open fixture (the landing page currently has 0 in-page anchors); collapse stale records behind a toggle (IRREG-26-04).
- To the integration owner of `main`: the scheduled-refresh problem (IRREG-26-03) needs a workflow-level fix (for example a self-chaining `workflow_dispatch` at the end of each run, which GitHub permits for GITHUB_TOKEN) — not a new cron.
"""
p = ROOT / "reviews/26986a4e-verification.md"
p.write_text(p.read_text(encoding="utf-8") + FINDINGS, encoding="utf-8")
