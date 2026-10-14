"""Row-for-row reconciliation of the live Hotspawn CS2 open-fixture read against the
published consolidated board (console/data/picks.csv).

Inputs (committed, read-only here):
  reconcile/live_lobby_read_2026_10_14.csv  - lobby render (ET display, countdown anchored)
  reconcile/live_cs2_pickems_read_2026_10_14.csv - /cs2-pickems render (UTC display)
  console/data/picks.csv                     - the board being checked

Crowd percentages ("% picked") are deliberately NOT read or stored.
Output: reconcile/reconciliation.csv and reconcile/summary.json
"""
import csv, json, re, sys, datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "reconcile"
BOARD = ROOT / "console" / "data" / "picks.csv"
LOBBY = HERE / "live_lobby_read_2026_10_14.csv"
CSP = HERE / "live_cs2_pickems_read_2026_10_14.csv"
ET_OFFSET = dt.timedelta(hours=4)          # America/New_York in mid-October (EDT, UTC-4)
YEAR = 2026
LOCK_TOLERANCE_MIN = 6                     # board lock = start - 6 min (payload); UI countdown runs to start


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def parse_et(s):
    m = re.match(r"(\w{3}) (\d{1,2}), (\d{2}):(\d{2})", s)
    mon = {"Oct": 10}[m.group(1)]
    local = dt.datetime(YEAR, mon, int(m.group(2)), int(m.group(3)), int(m.group(4)))
    return local + ET_OFFSET  # naive UTC


def parse_countdown(c):
    """'03:22:35' or '1d 3h 22m' -> timedelta"""
    if re.match(r"^\d\d:\d\d:\d\d$", c):
        h, m, s = map(int, c.split(":"))
        return dt.timedelta(hours=h, minutes=m, seconds=s)
    d = re.match(r"(\d+)d (\d+)h (\d+)m", c)
    return dt.timedelta(days=int(d.group(1)), hours=int(d.group(2)), minutes=int(d.group(3)))


def parse_csp_utc(s):
    m = re.match(r"(\w{3}) (\d{1,2}), (\d{2}):(\d{2})", s)
    return dt.datetime(YEAR, 10, int(m.group(2)), int(m.group(3)), int(m.group(4)))


def main():
    lobby = list(csv.DictReader(LOBBY.open()))
    csp = list(csv.DictReader(CSP.open()))
    board = list(csv.DictReader(BOARD.open(encoding="utf-8")))
    assert len(lobby) == 28 and len(csp) == 28, (len(lobby), len(csp))

    by_pair = {}
    for b in board:
        by_pair.setdefault(frozenset([norm(b["team_a"]), norm(b["team_b"])]), []).append(b)

    rows, flags_total = [], {}
    def flag(code):
        flags_total[code] = flags_total.get(code, 0) + 1

    # implied render time of each lobby row (countdown anchor)
    render_times = []
    for L in lobby:
        start_et = parse_et(L["rendered_local_et"])
        cd = parse_countdown(L["countdown_locks_in"])
        render_times.append(start_et - cd)  # UTC of the render
    lobby_render = min(render_times), max(render_times)
    spread = (lobby_render[1] - lobby_render[0]).total_seconds()
    csp_renders = []
    for C in csp:
        csp_renders.append(None)
    for L, C in zip(lobby, csp):
        pass

    for i, L in enumerate(lobby):
        C = csp[i]  # same row order by construction (both pages list the same sequence)
        lobby_start = parse_et(L["rendered_local_et"])
        csp_start = parse_csp_utc(C["rendered_date_time"])
        pair = frozenset([norm(L["team_a"]), norm(L["team_b"])])
        cands = by_pair.get(pair, [])
        # same pairing AND same start instant
        match = [b for b in cands if dt.datetime.strptime(b["start_utc"], "%Y-%m-%dT%H:%M:%SZ") == lobby_start]
        r = {
            "live_row": L["row"], "live_section": L["page_section"],
            "live_team_a": L["team_a"], "live_team_b": L["team_b"],
            "live_tournament": L["tournament"], "live_tier": L["tier"],
            "live_start_utc_from_lobby": lobby_start.strftime("%Y-%m-%dT%H:%MZ"),
            "live_start_utc_from_cs2pickems": csp_start.strftime("%Y-%m-%dT%H:%MZ"),
            "lobby_and_cs2pickems_agree": "yes" if lobby_start == csp_start else "no",
            "live_hotspawn_fixture_id": L["hotspawn_fixture_id_from_url"] or "not visible on rendered page",
            "board_fixture_id": "", "board_pick": "", "board_pick_pct": "", "board_p_a_pct": "",
            "board_p_b_pct": "", "board_basis_rung": "", "board_source_url": "", "board_flags": "",
            "result": "", "notes": "",
        }
        notes = []
        if len(match) == 1:
            b = match[0]
            r["board_fixture_id"] = b["fixture_id"]
            r["board_pick"] = b["pick"]; r["board_pick_pct"] = b["pick_pct"]
            r["board_p_a_pct"] = b["p_a_pct"]; r["board_p_b_pct"] = b["p_b_pct"]
            r["board_basis_rung"] = b["basis_rung"]; r["board_source_url"] = b["source_url"]
            r["board_flags"] = b["board_flags"]
            # identity: board team order vs live team order
            if norm(b["team_a"]) != norm(L["team_a"]):
                notes.append("team order differs (board A = live B); probabilities re-mapped by name")
                flag("ORDER-SWAP")
            if b["hotspawn_match_url"] == "" and L["hotspawn_fixture_id_from_url"] == "":
                notes.append("no Hotspawn match link on the rendered page; ID from the board only")
            if L["hotspawn_fixture_id_from_url"] and L["hotspawn_fixture_id_from_url"] != b["fixture_id"]:
                notes.append("live URL id differs from board id"); flag("ID-MISMATCH")
            if L["hotspawn_fixture_id_from_url"] == "":
                flag("ID-NOT-VISIBLE")
            # lock: board lock vs UI start countdown
            blk = dt.datetime.strptime(b["lock_utc"], "%Y-%m-%dT%H:%M:%SZ")
            gap = (lobby_start - blk).total_seconds() / 60
            if abs(gap - LOCK_TOLERANCE_MIN) > 0.5:
                notes.append(f"board lock is {gap:.0f} min before the UI start"); flag("LOCK-GAP-NOT-6MIN")
            # internal consistency of the published row
            pa, pb = float(b["p_a_pct"]), float(b["p_b_pct"])
            if abs(pa + pb - 100) > 0.11:
                notes.append("p_a + p_b != 100"); flag("SUM-NOT-100")
            fav = b["team_a"] if pa > pb else b["team_b"] if pb > pa else "TIE"
            if fav != b["pick"]:
                notes.append("pick is not the higher probability"); flag("PICK-NOT-FAVOURITE")
            if b["pick_pct"] and abs(float(b["pick_pct"]) - max(pa, pb)) > 0.11:
                notes.append("pick_pct != max probability"); flag("PICKPCT-MISMATCH")
            if "hotspawn" in b["basis_rung"].lower() or "hotspawn" in b["basis_detail"].lower():
                notes.append("basis mentions Hotspawn"); flag("HOTSPAWN-BASIS")
            r["result"] = "match"
        elif len(match) == 0:
            r["result"] = "MISSING ON BOARD"
            flag("MISSING-ON-BOARD")
        else:
            r["result"] = "AMBIGUOUS"
            flag("AMBIGUOUS")
        if not r["board_pick"] and r["result"] == "match":
            flag("NO-PICK")
        r["notes"] = "; ".join(notes)
        rows.append(r)

    # Board rows that are not on the live page (extra on board)
    live_pairs = {frozenset([norm(L["team_a"]), norm(L["team_b"])]) for L in lobby}
    extra = [b["fixture_id"] for b in board if frozenset([norm(b["team_a"]), norm(b["team_b"])]) not in live_pairs]
    for e in extra:
        flag("EXTRA-ON-BOARD")

    out = HERE / "reconciliation.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    matched = sum(1 for r in rows if r["result"] == "match")
    with_pick = sum(1 for r in rows if r["board_pick"])
    summary = {
        "live_open_fixtures": len(lobby),
        "lobby_render_utc_range": [lobby_render[0].strftime("%Y-%m-%dT%H:%M:%SZ"), lobby_render[1].strftime("%Y-%m-%dT%H:%M:%SZ")],
        "lobby_render_spread_seconds": spread,
        "board_rows": len(board),
        "matched_one_to_one": matched,
        "live_fixtures_with_board_pick": with_pick,
        "board_rows_not_on_live_page": extra,
        "flag_counts": flags_total,
        "crowd_percentages_read": False,
    }
    (HERE / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if matched == 28 and with_pick == 28 and not extra else 1


if __name__ == "__main__":
    sys.exit(main())
