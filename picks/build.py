#!/usr/bin/env python3
"""Hotspawn CS2 Pick'em analysis - build the picks/ site (session arena/9920c263, tasks Q-01..Q-04).

Run from the repository root:   python3 picks/build.py

Inputs (all hand-entered from pages read in this session; every value carries its source URL):
  * LOBBY_ROWS   - fixtures rendered by https://play.hotspawn.com/cs2-pickems (fetched 2026-10-13 ~22:00 UTC).
                   Times on that page are UTC (checked against the countdown timers).
  * MARKET       - decimal 1X2 prices shown on EGamersWorld (EGW) match pages / event schedules, read 2026-10-13
                   21:58-22:04 UTC. EGW labels 1.80/1.80 as a placeholder; placeholders are NOT used.
  * VRS          - Valve Regional Standings 2026-10-05 (commit eec4853), points + line number in the official file.
  * STALE        - 59 CS2 fixtures from the Hotspawn TransferState capture kept in data/6d9c321d/ (not re-verified live).

Probability rules (no Hotspawn crowd % is read or used anywhere):
  * market_p  = de-vigged (proportional) two-way probability from the EGW decimal prices.
  * own_p     = Valve Regional Standings curve  P(A) = 1 / (1 + 10^(-k*(ptsA-ptsB)/400)),  k = 0.4568
                (k = calibrated slope adopted in model/input/vrs/calibration.json, session 91eff436).
  * pick      = higher market_p when a verified market price exists; otherwise higher own_p when both VRS
                entries are unambiguous (labelled "own model only"); otherwise no pick.
Outputs: picks/data/slate.csv, slate.json, stale_listed.csv and every picks/*.html page.
"""
import csv
import datetime
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "picks")
DATA = os.path.join(OUT, "data")
AS_OF = "2026-10-13 22:04 UTC"
K = 0.4568  # calibrated slope, model/input/vrs/calibration.json (k_published)

LOBBY = "https://play.hotspawn.com/cs2-pickems"
EGW_CCT11 = "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"
EGW_TPWC = "https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H"
EGW_STAKE = "https://egamersworld.com/counterstrike/event/stake-pulse-beat-iii-EJZmJpBjeNx"
VRS_FILE_URL = "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md"
VRS_COMMIT = "eec4853d7bcf0f1f7efe7f0d901234bef7e98b75"
VRS_FILE = "live/2026/standings_global_2026_10_05.md"
VRS_URL = "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/%s/%s?plain=1#L" % (VRS_COMMIT, VRS_FILE)
EGW_MATCH = "https://egamersworld.com/counterstrike/match/"
EGW_EVENT_PLAYIN = "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in-1sGIL2gAYu"
EGW_EVENT_ELISA = "https://egamersworld.com/counterstrike/event/elisa-esports-breakout-series-2-4yn491uUVl"
HS_MATCH = "https://www.hotspawn.com/matches/"

# Valve Regional Standings rows used (name as printed in the file, points, line number in the file).
VRS = {
    # key: (name in Valve file, points, line number in the file; verified by parsing the file at eec4853)
    "Legacy": ("Legacy", 1931, 7), "Falcons": ("Falcons", 1843, 11), "FURIA": ("FURIA", 1829, 12),
    "Aurora": ("Aurora", 1716, 14), "Astralis": ("Astralis", 1674, 15), "MIBR": ("MIBR", 1585, 17),
    "Heroic": ("HEROIC", 1550, 20), "9z": ("9z", 1543, 22), "NiP": ("Ninjas in Pyjamas", 1534, 23),
    "HOTU": ("HOTU", 1437, 36), "fnatic": ("fnatic", 1417, 40), "PARIVISION": ("PARIVISION", 1411, 41),
    "BC.Game": ("BC.Game", 1318, 55), "WBT": ("WBT", 1201, 65), "Voca": ("Voca", 1182, 73),
    "Phantom": ("Phantom", 1147, 77), "Sashi": ("Sashi", 1131, 78), "FORZE": ("FORZE Reload", 1100, 89),
    "3DMAX": ("3DMAX", 1500, 26), "EAC": ("EAC", 1035, 108), "ENCE": ("ENCE", 1025, 110),
    "HAVU": ("HAVU", 937, 129), "mellren": ("mellren", 932, 130), "TLR": ("The Last Resort", 926, 131),
    "G2 Ares": ("G2 Ares", 913, 134), "Enjoy": ("Enjoy", 871, 143), "Lavked": ("Lavked", 862, 148),
    "Overtake": ("Overtake Sector", 774, 182), "Gothic": ("Gothic", 705, 216), "Ryvex": ("Ryvex", 714, 212),
    "BOJONG": ("BOJONG", 463, 368), "B8 Academy": ("B8 Academy", 631, 266), "ROUNDS": ("ROUNDS", 548, 315),
    "BetBoom": ("BETBOOM", 1596, 16),
}
# Names that appear on more than one Valve row, or that cannot be matched to Hotspawn's team: no own line.
VRS_AMBIGUOUS = {"Zomblers", "ex-RUSTEC", "6666", "Banda Chuya", "PCIFIC", "LFO 10", "SUKEBAN", "Privateer"}

# Hotspawn team -> VRS key (exact name match unless a note explains a mapping).
TEAM_VRS = {
    "Legacy": "Legacy", "Falcons": "Falcons", "FURIA": "FURIA", "Aurora": "Aurora", "Astralis": "Astralis",
    "MIBR": "MIBR", "Heroic": "Heroic", "9z": "9z", "Ninjas in Pyjamas": "NiP", "HOTU": "HOTU",
    "fnatic": "fnatic", "PARIVISION": "PARIVISION", "BC.Game": "BC.Game", "WROTBERRY": "WBT", "Voca": "Voca",
    "Phantom": "Phantom", "Sashi": "Sashi", "FORZE Reload": "FORZE", "Envy": "3DMAX", "EAC": "EAC",
    "ENCE": "ENCE", "HAVU": "HAVU", "mellren": "mellren", "The Last Resort": "TLR", "G2 Ares": "G2 Ares",
    "Enjoy": "Enjoy", "Lavked": "Lavked", "Overtake Sector": "Overtake", "Gothic": "Gothic", "Ryvex": "Ryvex",
    "BOJONG": "BOJONG", "B8 Academy": "B8 Academy", "RoundsGG": "ROUNDS",
    "BetBoom": "BetBoom", "Fnatic": "fnatic",
}

# ---- lobby rows (order as shown on the page; "id" = Hotspawn match id, "" when the row has no View Match link)
# market: (odds_a, odds_b, url, label) or None
ELISA_NOTE = "EGW event page schedule (decimal odds as shown in the schedule; the event page top bet block names bc.game)"
LOBBY_ROWS = [
    dict(id="", start="2026-10-13 22:00", tournament="CCT South America 2026 Series #7", tier="C", pts=2,
         a="SUKEBAN", b="your end", status="Locked", market=None, note="Locked at 21:54 UTC. Team name 'your end' is unusual: flagged."),
    dict(id="1079546", start="2026-10-14 01:00", tournament="ESL Challenger League Season 52: North America - Cup #3", tier="B", pts=3,
         a="Zomblers", b="Overtake Sector", status="Open", market=(2.52, 1.48, EGW_MATCH + "41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_", "EGW match page headline odds")),
    dict(id="", start="2026-10-14 08:00", tournament="CCT Europe 2026 Series #12 Play-In", tier="C", pts=2,
         a="Enjoy", b="B8 Academy", status="Open", market="placeholder", placeholder_url=EGW_EVENT_PLAYIN,
         note="EGW shows 1.80/1.80 placeholder: no price used."),
    dict(id="1079621", start="2026-10-14 08:00", tournament="CCT Europe 2026 Series #11", tier="B", pts=3,
         a="Gothic", b="Lavked", status="Open", market=(2.05, 1.64, EGW_MATCH + "_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B", "EGW match page headline odds")),
    dict(id="1080176", start="2026-10-14 08:30", tournament="Thunderpick World Championship 2026", tier="S", pts=7,
         a="9z", b="Aurora", status="Open", market=(3.3, 1.26, EGW_MATCH + "5X5sFiL7H/9z-vs-aurora-Es9rrnIhb", "EGW match page headline odds")),
    dict(id="1079438", start="2026-10-14 10:00", tournament="Stake Pulse Beat III", tier="B", pts=3,
         a="Astralis", b="Sashi", status="Open", market=(1.09, 6.27, EGW_MATCH + "EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z", "EGW match page headline odds")),
    dict(id="1079439", start="2026-10-14 10:00", tournament="Stake Pulse Beat III", tier="B", pts=3,
         a="HOTU", b="Fnatic", status="Open", market=(1.9, 1.76, EGW_MATCH + "EJZmJpBjeNx/hotu-vs-fnatic-KjM3caFTC", "EGW match page headline odds")),
    dict(id="", start="2026-10-14 11:00", tournament="CCT Europe 2026 Series #12 Play-In", tier="C", pts=2,
         a="Banda chuya", b="6666", status="Open", market="placeholder", placeholder_url=EGW_EVENT_PLAYIN,
         note="EGW shows 1.80/1.80 placeholder: no price used."),
    dict(id="1079622", start="2026-10-14 11:00", tournament="CCT Europe 2026 Series #11", tier="B", pts=3,
         a="ex-RUSTEC", b="mellren", status="Open", market="placeholder", placeholder_url=EGW_CCT11,
         note="EGW shows 1.80/1.80 placeholder: no price used."),
    dict(id="1080177", start="2026-10-14 11:00", tournament="Thunderpick World Championship 2026", tier="S", pts=7,
         a="Falcons", b="Ninjas in Pyjamas", status="Open", market=(1.21, 3.75, EGW_MATCH + "5X5sFiL7H/falcons-vs-nip-QSa-aeOIR", "EGW match page headline odds")),
    dict(id="1080178", start="2026-10-14 13:30", tournament="Thunderpick World Championship 2026", tier="S", pts=7,
         a="Legacy", b="PARIVISION", status="Open", market=(1.64, 2.08, EGW_MATCH + "5X5sFiL7H/legacy-vs-parivision--TTc59QUDJ", "EGW match page headline odds")),
    dict(id="", start="2026-10-14 14:00", tournament="CCT Europe 2026 Series #12 Play-In", tier="C", pts=2,
         a="Ryvex", b="PCIFIC", status="Open", market="placeholder", placeholder_url=EGW_EVENT_PLAYIN,
         note="EGW lists 'PCIFIC Espor' and 'WRAITH PCIFIC' for this slot; 1.80/1.80 placeholder."),
    dict(id="1079623", start="2026-10-14 14:00", tournament="CCT Europe 2026 Series #11", tier="B", pts=3,
         a="G2 Ares", b="The Last Resort", status="Open", market=(1.44, 2.39, EGW_MATCH + "_rW8GEyWK/g2-ares-vs-the-last-resort-7GWb9EDd9L", "EGW match page headline odds")),
    dict(id="1080179", start="2026-10-14 16:00", tournament="Thunderpick World Championship 2026", tier="S", pts=7,
         a="FURIA", b="BetBoom", status="Open", market=(1.39, 2.81, EGW_MATCH + "5X5sFiL7H/furia-vs-betboom-team-ZeSbzy91oH", "EGW match page headline odds")),
    dict(id="1079624", start="2026-10-14 17:00", tournament="CCT Europe 2026 Series #11", tier="B", pts=3,
         a="FORZE Reload", b="LFO 10", status="Open", market="placeholder", placeholder_url=EGW_CCT11,
         note="EGW shows 1.80/1.80 and no opponent name on the match page. LFO 10 not in Valve standings: no own line."),
    dict(id="1080279", start="2026-10-15 08:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="WROTBERRY", b="EAC", status="Open", market=(2.0, 1.72, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1079440", start="2026-10-15 10:00", tournament="Stake Pulse Beat III", tier="B", pts=3,
         a="MIBR", b="BC.Game", status="Open", market=(1.61, 2.08, EGW_MATCH + "EJZmJpBjeNx/mibr-vs-bcgame-esports-X8nMpUjAX", "EGW match page headline odds")),
    dict(id="1079442", start="2026-10-15 10:00", tournament="Stake Pulse Beat III", tier="B", pts=3,
         a="Heroic", b="Envy", status="Open", market=(1.44, 2.52, EGW_MATCH + "EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC", "EGW match page headline odds")),
    dict(id="1080280", start="2026-10-15 10:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="ENCE", b="BOJONG", status="Open", market=(1.3, 3.2, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080281", start="2026-10-15 12:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="WROTBERRY", b="ENCE", status="Open", market=(1.62, 2.15, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080282", start="2026-10-15 14:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="EAC", b="BOJONG", status="Open", market=(1.2, 4.0, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080283", start="2026-10-15 16:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="WROTBERRY", b="BOJONG", status="Open", market=(1.2, 4.0, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080284", start="2026-10-15 18:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="EAC", b="ENCE", status="Open", market=(1.5, 2.4, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080285", start="2026-10-16 08:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="Voca", b="Phantom", status="Open", market=(1.9, 1.8, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080286", start="2026-10-16 10:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="HAVU", b="RoundsGG", status="Open", market=(1.2, 4.0, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080287", start="2026-10-16 12:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="Voca", b="HAVU", status="Open", market=(1.42, 2.7, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="", start="2026-10-16 14:00", tournament="CCT Europe 2026 Series #12 Play-In", tier="C", pts=2,
         a="mellren", b="Privateer", status="Open", market="placeholder", placeholder_url=EGW_EVENT_PLAYIN,
         note="EGW lists 'Privateer Gaming' (not 'Privateer'); 1.80/1.80 placeholder."),
    dict(id="1080288", start="2026-10-16 14:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="Phantom", b="RoundsGG", status="Open", market=(1.06, 7.0, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080289", start="2026-10-16 16:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="RoundsGG", b="Voca", status="Open", market=(6.3, 1.08, EGW_EVENT_ELISA, ELISA_NOTE)),
    dict(id="1080290", start="2026-10-16 18:00", tournament="Elisa BreakOut Series #2", tier="C", pts=2,
         a="Phantom", b="HAVU", status="Open", market=(1.35, 2.9, EGW_EVENT_ELISA, ELISA_NOTE)),
]

# Hotspawn ids seen in the TransferState capture but not rendered on the live page at 22:04 UTC (started).
STARTED_ROWS = [
    dict(id="1079620", start="2026-10-13 17:00", tournament="CCT Europe 2026 Series #11", tier="B", pts=3,
         a="Black Phoenix", b="6666", status="Started (not pickable)", market=None,
         note="From the 6d9c321d TransferState capture; not rendered on the live lobby at check time."),
    dict(id="1081076", start="2026-10-13 21:00", tournament="ESL Challenger League Season 52: South America - Cup #3", tier="B", pts=3,
         a="ex-Keyd Stars", b="Galorys", status="Started (not pickable)", market=None,
         note="From the 6d9c321d TransferState capture; started 21:00 UTC, not pickable."),
]

TOURNAMENT_OK = {}  # reserved

LINKS = {}


def fmt_pct(p):
    return "" if p is None else "%.1f%%" % (100 * p)


def market_probs(oa, ob):
    ia, ib = 1.0 / oa, 1.0 / ob
    s = ia + ib
    return ia / s, ib / s, (s - 1.0) * 100.0


def own_probs(pa, pb):
    pa_ = 1.0 / (1.0 + 10 ** (-K * (pa - pb) / 400.0))
    return pa_, 1.0 - pa_


def vrs_for(team):
    if team in VRS_AMBIGUOUS:
        return None
    key = TEAM_VRS.get(team)
    if not key:
        return None
    return VRS[key]


PERMALINK = {}
_csvp = os.path.join(ROOT, "data", "6d9c321d", "ng_state_86_fixtures.csv")
if os.path.exists(_csvp):
    import csv as _c
    for _r in _c.DictReader(open(_csvp, encoding="utf-8")):
        if _r.get("hotspawn_permalink"):
            PERMALINK[_r["hotspawn_id"]] = _r["hotspawn_permalink"]


def hs_link(row):
    if row["id"]:
        return PERMALINK.get(row["id"], "%s#%s" % (LOBBY, row["id"]))
    return LOBBY


def build_rows():
    out = []
    for r in LOBBY_ROWS + STARTED_ROWS:
        start = datetime.datetime.strptime(r["start"], "%Y-%m-%d %H:%M")
        lock = start - datetime.timedelta(minutes=6)  # equals lock_time_utc in data/6d9c321d CSV (lock_offset_sec 360); checked on all ID rows
        row = dict(
            hotspawn_id=r["id"], start_utc=r["start"] + " UTC", lock_utc_derived=lock.strftime("%Y-%m-%d %H:%M") + " UTC",
            tournament=r["tournament"], tier=r["tier"], points=r["pts"], team_a=r["a"], team_b=r["b"],
            status=r["status"], note=r.get("note", ""), hotspawn_url=hs_link(r),
            ext_odds_a="", ext_odds_b="", ext_p_a="", ext_p_b="", ext_overround_pct="", ext_source="", ext_url="",
            own_pts_a="", own_pts_b="", own_p_a="", own_p_b="", own_url_a="", own_url_b="",
            pick="", pick_p="", basis="", flags="",
        )
        flags = []
        if not r["id"]:
            flags.append("F-NOID")
        if r["a"] in ("your end",) or r["b"] in ("your end",):
            flags.append("F-NAME")
        if r["a"] in VRS_AMBIGUOUS or r["b"] in VRS_AMBIGUOUS:
            flags.append("F-AMBIG")
        if {r["a"], r["b"]} & {"Envy", "WROTBERRY", "RoundsGG"}:
            flags.append("F-MAP")
        m = r.get("market")
        if isinstance(m, tuple):
            oa, ob, url, label = m
            pa, pb, ov = market_probs(oa, ob)
            row.update(ext_odds_a=oa, ext_odds_b=ob, ext_p_a=round(pa, 4), ext_p_b=round(pb, 4),
                       ext_overround_pct=round(ov, 2), ext_source=label, ext_url=url)
        elif m == "placeholder":
            row.update(ext_source="EGamersWorld: 1.80/1.80 placeholder (not used)", ext_url=r.get("placeholder_url", ""))
            flags.append("F-PLACEHOLDER")
        va, vb = vrs_for(r["a"]), vrs_for(r["b"])
        if va and vb and r["status"] == "Open":
            pa, pb = own_probs(va[1], vb[1])
            row.update(own_pts_a=va[1], own_pts_b=vb[1], own_p_a=round(pa, 4), own_p_b=round(pb, 4),
                       own_url_a=VRS_URL + str(va[2]), own_url_b=VRS_URL + str(vb[2]))
        elif r["status"] == "Open" and (r["a"] not in VRS_AMBIGUOUS and r["b"] not in VRS_AMBIGUOUS):
            flags.append("F-NOOWN")
        # pick
        if r["status"] == "Open":
            if isinstance(m, tuple):
                side = "A" if row["ext_p_a"] >= row["ext_p_b"] else "B"
                row["pick"] = r["a"] if side == "A" else r["b"]
                row["pick_p"] = row["ext_p_a"] if side == "A" else row["ext_p_b"]
                row["basis"] = "External bookmaker line (EGW, de-vigged)"
                if row["own_p_a"] != "":
                    own_side = "A" if row["own_p_a"] >= row["own_p_b"] else "B"
                    row["own_agrees"] = "yes" if own_side == side else "no"
                    if own_side != side:
                        flags.append("F-DISAGREE")
                else:
                    row["own_agrees"] = "n/a"
            elif row["own_p_a"] != "":
                side = "A" if row["own_p_a"] >= row["own_p_b"] else "B"
                row["pick"] = r["a"] if side == "A" else r["b"]
                row["pick_p"] = row["own_p_a"] if side == "A" else row["own_p_b"]
                row["basis"] = "Own model only (Valve VRS curve) - no external line"
                row["own_agrees"] = "n/a"
                flags.append("F-OWNONLY")
            else:
                row["basis"] = "No pick: no verified external line and no unambiguous own line"
                row["own_agrees"] = "n/a"
        elif r["status"] == "Locked":
            row["basis"] = "Locked - no pick possible"
        else:
            row["basis"] = "Started - not pickable"
        if row.get("own_agrees") is None:
            row["own_agrees"] = "n/a"
        if row["pick"]:
            row["pick_p"] = round(row["pick_p"], 4)
        row["flags"] = ";".join(sorted(set(flags)))
        out.append(row)
    out.sort(key=lambda x: (x["start_utc"], x["hotspawn_id"]))
    return out


def stale_rows():
    path = os.path.join(ROOT, "data", "6d9c321d", "ng_state_86_fixtures.csv")
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        if r["category"] != "stale_summer_2026_unclosed":
            continue
        rows.append(dict(hotspawn_id=r["hotspawn_id"], start_utc=r["utc_start"], tournament=r["tournament"],
                         tier=r["tier"], points=r["points"], team_a=r["team1"], team_b=r["team2"],
                         status="Listed, start date passed (not pickable)", hotspawn_url=LOBBY))
    rows.sort(key=lambda x: x["start_utc"])
    return rows


def esc(x):
    return html.escape(str(x), quote=True)


def pct_cell(p):
    return fmt_pct(p) if p not in ("", None) else "blank"


FLAGS = [
    ("F-01", "Lobby count mismatch", "The lobby header says 68 matches this week, but the CS2 filter counts 89 matches and renders 30 rows in the page HTML. The 59 extra rows have June-July 2026 start dates. They are listed on the 'Not pickable' page from an earlier capture, not re-verified line by line.", [LOBBY]),
    ("F-03", "Five rows have no Hotspawn match id", "SUKEBAN-your end, Enjoy-B8 Academy, Banda chuya-6666, Ryvex-PCIFIC and mellren-Privateer have no 'View Match' link. Their rows link to the lobby.", [LOBBY]),
    ("F-04", "'your end' as a team name", "Hotspawn lists 'your end' as an opposing team. Valve's 2026-10-05 standings also contain a team named 'your end' (rank 295, line 300), which is not verified as the same team. The row is locked; no line is used.", [LOBBY, VRS_URL + "300"]),
    ("F-05", "EGW 1.80/1.80 placeholders", "Six open rows show 1.80/1.80 on EGamersWorld: Enjoy-B8, Banda chuya-6666, Ryvex-PCIFIC, mellren-Privateer (CCT Play-In event page), ex-RUSTEC-mellren and FORZE-LFO 10 (read on the EGW match pages; linked here via the CCT #11 event page). They are not prices and were not used. They are left blank.", [EGW_EVENT_PLAYIN, EGW_CCT11, EGW_CCT11]),
    ("F-06", "FORZE Reload opponent not shown on EGW", "The EGW match page for FORZE Reload shows no opponent name; Hotspawn lists LFO 10. LFO 10 is not in the Valve 2026-10-05 standings. No line.", [EGW_CCT11, LOBBY]),
    ("F-07", "Team Envy mapped to 3DMAX in Valve standings", "Hotspawn and EGW say 'Envy' / 'Team Envy'. Valve 2026-10-05 has no 'Envy' row; it has '3DMAX' (1500 pts) with a roster that overlaps Team Envy's EGW lineup (Lucky, Maka, misutaaa, Kursy). We use it as the same team: an identity inference, not a published rename.", [VRS_URL + "26", "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/heroic-vs-team-envy-NcCqzpPZdC"]),
    ("F-08", "Duplicate team names in Valve standings", "Zomblers (lines 259, 264), ex-RUSTEC (lines 97, 157), 6666 (lines 132, 373), Banda Chuya (lines 170, 378) appear twice. Own lines are left blank for these teams. Hotspawn 'PCIFIC' also matches two EGW entries ('PCIFIC Espor', 'WRAITH PCIFIC'), so its own line is blank.", [VRS_URL + "259", VRS_URL + "264", VRS_URL + "97", VRS_URL + "157", VRS_URL + "132", VRS_URL + "373", VRS_URL + "170", VRS_URL + "378", VRS_URL + "144"]),
    ("F-09", "Name mapping for Elisa teams", "Hotspawn 'WROTBERRY' = EGW 'WBT' (WhiteBIT Team per Liquipedia), Hotspawn 'EAC' = EGW 'EA Copenhagen' (Esport Academy Copenhagen per Liquipedia), Hotspawn 'RoundsGG' = EGW 'Rounds' = Valve 'ROUNDS'. Mapping by name only; rosters not re-checked.", ["https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2", EGW_EVENT_ELISA]),
    ("F-10", "Elisa start time differs in Liquipedia", "Liquipedia lists the first Elisa matches at 10:00 EEST (= 07:00 UTC). Hotspawn and bo5.gg list 08:00 UTC, and EGW's page title says 08:00. We use 08:00 UTC.", ["https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2", "https://bo5.gg/cs2/tournaments/elisa-breakout-series-2-group-stage/"]),
    ("F-11", "One headline price per match, not a consensus", "Each market probability comes from one headline price pair on an EGW match page or event schedule. Several bookmakers were not read, so this is not a consensus. Search snippets of the same EGW pages later showed different prices (e.g. Falcons-NiP 1.8 placeholder, HOTU-fnatic 1.82/1.82), so prices move. Our reads: 21:58-22:04 UTC.", [EGW_TPWC, EGW_EVENT_ELISA]),
    ("F-12", "Market and own model disagree", "Four rows are marked F-DISAGREE: the external pick differs from the Valve curve (HOTU vs Fnatic, WROTBERRY vs EAC, Voca vs Phantom, G2 Ares vs The Last Resort). The external line decides the pick; the disagreement is shown for review. Legacy vs PARIVISION has the same side in both (market 55.9%, own 79.7%), a large gap in size only.", [LOBBY]),
    ("F-13", "Own model uses Valve 2026-10-05 standings", "The own line uses the 2026-10-05 standings file at the head commit of the shallow clone (eec4853), eight days old on 2026-10-13. Calibration k = 0.4568 is from model/input/vrs/calibration.json (session 91eff436). We did not re-fit it.", [VRS_FILE_URL, "https://github.com/ValveSoftware/counter-strike_regional_standings"]),
    ("F-14", "Previously published figures superseded", "Earlier stored odds in data/6d9c321d/external_bookmaker_lines.csv and the previous picks/ page differ from the prices read this session (e.g. Falcons-NiP 1.23/3.78 stored vs 1.21/3.75 now; 9z-Aurora 3.76/1.23 stored vs 3.3/1.26 now). We use this session's reads only.", [EGW_MATCH + "5X5sFiL7H/falcons-vs-nip-QSa-aeOIR"]),
    ("F-15", "Locked and started rows", "SUKEBAN-your end was locked at 21:54 UTC. Black Phoenix-6666 (17:00 UTC) and ex-Keyd Stars-Galorys (21:00 UTC) have started. None has a pick.", [LOBBY]),
    ("F-16", "Stale listed fixtures not re-verified", "The 59 fixtures on the 'Not pickable' page were read from an earlier capture (data/6d9c321d). Their dates are June-July 2026, so no probability is given.", ["https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/6d9c321d/ng_state_86_fixtures.csv"]),
]


def write_csv(rows):
    fields = ["hotspawn_id", "start_utc", "lock_utc_derived", "tournament", "tier", "points", "team_a", "team_b",
              "status", "ext_odds_a", "ext_odds_b", "ext_p_a", "ext_p_b", "ext_overround_pct", "ext_source", "ext_url",
              "own_pts_a", "own_pts_b", "own_p_a", "own_p_b", "own_url_a", "own_url_b", "pick", "pick_p", "basis",
              "own_agrees", "hotspawn_url", "flags", "note"]
    with open(os.path.join(DATA, "slate.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(os.path.join(DATA, "slate.json"), "w", encoding="utf-8") as f:
        json.dump({"as_of": AS_OF, "k": K, "vrs_commit": VRS_COMMIT, "rows": rows}, f, ensure_ascii=False, indent=1)
    st = stale_rows()
    with open(os.path.join(DATA, "stale_listed.csv"), "w", newline="", encoding="utf-8") as f:
        fs = ["hotspawn_id", "start_utc", "tournament", "tier", "points", "team_a", "team_b", "status", "hotspawn_url"]
        w = csv.DictWriter(f, fieldnames=fs, extrasaction="ignore")
        w.writeheader()
        for r in st:
            w.writerow(r)
    return st


CSS = """
:root{--ink:#1d2330;--mut:#5b6474;--line:#e3e7ee;--bg:#f6f7fb;--card:#fff;--ok:#0b7a3e;--warn:#9a5b00;--bad:#a4262c;--pick:#0d5bd7}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header.top{background:#0f1a2e;color:#fff;padding:14px 16px}
header.top h1{margin:0;font-size:19px}
header.top p{margin:4px 0 0;color:#c9d3e6;font-size:13px}
nav.menu{display:flex;flex-wrap:wrap;gap:6px;padding:10px 16px;background:#fff;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
nav.menu a{padding:6px 10px;border-radius:999px;background:#eef3ff;color:#0d3d9e;text-decoration:none;font-size:13px}
nav.menu a.on{background:#0d5bd7;color:#fff}
main{max-width:1180px;margin:0 auto;padding:14px 14px 40px}
h2{font-size:17px;margin:20px 0 8px}
.kpis{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.kpi b{display:block;font-size:22px}
.kpi span{font-size:12px;color:var(--mut)}
.note{background:#fff8e6;border:1px solid #f1d58a;border-radius:10px;padding:10px 12px;font-size:13px;margin:12px 0}
.tbl-wrap{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{background:#f3f6fb;font-size:12px;color:var(--mut);position:sticky;top:0}
td.num,th.num{text-align:right;white-space:nowrap}
.pick{color:var(--pick);font-weight:700}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;font-weight:600;margin:1px 2px 1px 0;background:#eef2f7;color:#3c4656}
.b-ext{background:#e6f6ec;color:var(--ok)}.b-own{background:#fff3df;color:var(--warn)}.b-none{background:#f3f4f6;color:#555}
.b-flag{background:#fdecec;color:var(--bad)}
a{color:#0d5bd7}
.cards{display:none}
.card-m{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px}
.card-m .t{font-size:12px;color:var(--mut)}
.card-m .m{font-weight:700;font-size:16px;margin:2px 0 6px}
.card-m .pk{display:flex;justify-content:space-between;align-items:center;background:#eef4ff;border-radius:10px;padding:8px 10px;margin:6px 0}
.card-m .pk .big{font-size:20px;font-weight:800;color:var(--pick)}
.card-m .row{font-size:13px;color:var(--mut);display:flex;flex-wrap:wrap;gap:6px 12px}
.card-m .row b{color:var(--ink)}
.card-m .src{font-size:12px;margin-top:6px;word-break:break-all}
.hide-s{}
@media (max-width:760px){
  .tbl-wrap{display:none}
  .cards{display:block}
  .kpis{grid-template-columns:repeat(2,1fr)}
  .hide-s{display:none}
}
footer{color:var(--mut);font-size:12px;padding:20px 16px;text-align:center}
"""

NAV = [("index.html", "Dashboard"), ("matches.html", "All matches"), ("tournaments.html", "By tournament"),
       ("not-pickable.html", "Not pickable"), ("flagged.html", "Flagged for review"), ("sources.html", "Sources"),
       ("method.html", "Method")]


def page(title, active, body):
    nav = "".join('<a href="%s"%s>%s</a>' % (h, ' class="on"' if h == active else "", esc(t)) for h, t in NAV)
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s | Hotspawn CS2 Pick'em analysis</title><link rel="stylesheet" href="style.css">
<style>%s</style></head>
<body>
<header class="top"><h1>Hotspawn CS2 Pick'em: win probability and pick per match</h1>
<p>Snapshot as of %s · Probabilities from external bookmaker lines (de-vigged) and our own Valve-standings model · Analysis only, not betting advice</p></header>
<nav class="menu">%s</nav>
<main>%s</main>
<footer>Generated by picks/build.py from picks/data/. Every value links its source. Blank = not verified.</footer>
</body></html>
""" % (esc(title), "", AS_OF, nav, body)


def badge_for(row):
    out = []
    if row["ext_p_a"] != "":
        out.append('<span class="badge b-ext">External line</span>')
    elif row["own_p_a"] != "":
        out.append('<span class="badge b-own">Own model only</span>')
    else:
        out.append('<span class="badge b-none">No pick</span>')
    for f in filter(None, row["flags"].split(";")):
        out.append('<span class="badge b-flag">%s</span>' % esc(f))
    return "".join(out)


def sources_html(row):
    parts = ['<a href="%s">Hotspawn</a>' % esc(row["hotspawn_url"])]
    if row["ext_url"]:
        parts.append('<a href="%s">Odds</a>' % esc(row["ext_url"]))
    if row["own_url_a"]:
        parts.append('<a href="%s">Valve VRS (A)</a>' % esc(row["own_url_a"]))
        parts.append('<a href="%s">Valve VRS (B)</a>' % esc(row["own_url_b"]))
    return " · ".join(parts)


def probs_cells(row):
    if row["ext_p_a"] != "":
        mk = "%s %s / %s %s" % (esc(row["team_a"]), esc(row["ext_odds_a"]), esc(row["team_b"]), esc(row["ext_odds_b"]))
        mkp = "%s / %s" % (fmt_pct(row["ext_p_a"]), fmt_pct(row["ext_p_b"]))
    else:
        mk, mkp = "blank (unverified)", "blank"
    if row["own_p_a"] != "":
        ownp = "%s / %s" % (fmt_pct(row["own_p_a"]), fmt_pct(row["own_p_b"]))
    else:
        ownp = "blank"
    return mk, mkp, ownp


def match_table(rows):
    head = "<tr><th>Start (UTC)</th><th>Lock (UTC)</th><th>Tournament</th><th>Match</th><th>Pick</th><th class=num>Pick %</th><th>External odds (decimal)</th><th>External % (A / B)</th><th>Own % (A / B)</th><th>Status &amp; basis</th><th>Sources</th></tr>"
    body = []
    for r in rows:
        mk, mkp, ownp = probs_cells(r)
        pk = ('<span class="pick">%s</span>' % esc(r["pick"])) if r["pick"] else "blank"
        body.append("<tr><td>%s</td><td>%s</td><td>%s<br><span class=\"badge\">Tier %s · %s pts</span></td><td>%s vs %s</td><td>%s</td><td class=num>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s<br>%s<br><small>%s</small></td><td>%s</td></tr>" % (
            esc(r["start_utc"]), esc(r["lock_utc_derived"]), esc(r["tournament"]), esc(r["tier"]), esc(r["points"]),
            esc(r["team_a"]), esc(r["team_b"]), pk, fmt_pct(r["pick_p"]) if r["pick"] else "blank",
            mk, mkp, ownp, esc(r["status"]), badge_for(r), esc(r["basis"]), sources_html(r)))
    return '<div class="tbl-wrap"><table>%s%s</table></div>' % (head, "".join(body))


def match_cards(rows):
    out = []
    for r in rows:
        mk, mkp, ownp = probs_cells(r)
        pk = ('<span class="pick">%s</span>' % esc(r["pick"])) if r["pick"] else "<span>No pick</span>"
        pp = fmt_pct(r["pick_p"]) if r["pick"] else "blank"
        out.append(
            '<div class="card-m"><div class="t">%s UTC · %s</div><div class="m">%s vs %s</div>'
            '<div class="pk"><div>Pick: %s</div><div class="big">%s</div></div>'
            '<div class="row"><span>External: <b>%s</b></span><span>Own: <b>%s</b></span></div>'
            '<div class="row"><span>Odds: <b>%s</b></span></div>'
            '<div class="row">%s</div><div class="src">%s</div>%s</div>' % (
                esc(r["start_utc"]), esc(r["tournament"]), esc(r["team_a"]), esc(r["team_b"]),
                pk, pp, mkp, ownp, mk, badge_for(r), sources_html(r), ""))
    return '<div class="cards">%s</div>' % "".join(out)


def dashboard(rows):
    open_rows = [r for r in rows if r["status"] == "Open"]
    n_open = len(open_rows)
    n_ext = sum(1 for r in open_rows if r["ext_p_a"] != "")
    n_own = sum(1 for r in open_rows if r["ext_p_a"] == "" and r["own_p_a"] != "")
    n_none = sum(1 for r in open_rows if r["pick"] == "")
    n_dis = sum(1 for r in open_rows if "F-DISAGREE" in r["flags"])
    kpis = ('<div class="kpis"><div class="kpi"><b>%d</b><span>Open matches on the live slate</span></div>'
            '<div class="kpi"><b>%d</b><span>Picks from an external line</span></div>'
            '<div class="kpi"><b>%d</b><span>Picks from our own model only</span></div>'
            '<div class="kpi"><b>%d</b><span>No pick (no verified line)</span></div></div>') % (n_open, n_ext, n_own, n_none)
    picks = [r for r in open_rows if r["pick"]]
    picks.sort(key=lambda x: x["start_utc"])
    summary = []
    for r in picks:
        summary.append(r)
    body = (
        "<h2>Picks at a glance (open matches, soonest first)</h2>"
        + '<p class="note">Pick = the side with the higher de-vigged external bookmaker probability. Where no verified external line exists, the pick is our own Valve-standings model, labelled. Hotspawn crowd percentages are never used. %d of %d external-line picks disagree with our own model; see the Flagged page.</p>' % (n_dis, n_ext)
        + kpis
        + match_table(summary) + match_cards(summary)
        + "<h2>Matches with no pick</h2><p>%s</p>" % "; ".join("%s vs %s (%s)" % (esc(r["team_a"]), esc(r["team_b"]), esc(r["start_utc"])) for r in open_rows if not r["pick"])
        + '<p class="note">Snapshot: %s. Lobby: <a href="%s">play.hotspawn.com/cs2-pickems</a>. Odds: EGamersWorld pages (linked on each row). Own model: Valve Regional Standings 2026-10-05 (<a href="https://github.com/ValveSoftware/counter-strike_regional_standings">source repo</a>).</p>' % (AS_OF, LOBBY)
    )
    return body


def tournaments_page(rows):
    groups = {}
    for r in rows:
        groups.setdefault(r["tournament"], []).append(r)
    parts = ["<h2>By tournament</h2><p>Each tournament, with its own table of matches.</p>"]
    for t in sorted(groups):
        parts.append("<h2>%s</h2>" % esc(t))
        parts.append(match_table(groups[t]))
        parts.append(match_cards(groups[t]))
    return "".join(parts)


def not_pickable_page(rows, stale):
    started = [r for r in rows if r["status"] != "Open"]
    parts = ["<h2>Started or locked (not pickable)</h2>"]
    parts.append(match_table(started) + match_cards(started))
    parts.append("<h2>Listed on the Hotspawn lobby with an earlier start date (not pickable)</h2>")
    parts.append('<p class="note">These %d CS2 fixtures are from the Hotspawn TransferState capture kept in <code>data/6d9c321d/</code>. Their start dates are 2026-06-26 to 2026-07-10, so no current probability is given. They were not re-verified line by line this session. Rows link the lobby.</p>' % len(stale))
    head = "<tr><th>Start (UTC)</th><th>Tournament</th><th>Tier</th><th>Match</th><th>Status</th><th>Source</th></tr>"
    body = "".join("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s vs %s</td><td>%s</td><td><a href=\"%s\">Hotspawn lobby</a></td></tr>" % (
        esc(r["start_utc"]), esc(r["tournament"]), esc(r["tier"]), esc(r["team_a"]), esc(r["team_b"]), esc(r["status"]), esc(r["hotspawn_url"])) for r in stale)
    parts.append('<div class="tbl-wrap"><table>%s%s</table></div>' % (head, body))
    return "".join(parts)


def flagged_page():
    parts = ["<h2>Flagged for review</h2>",
             '<p class="note">Irregularities and unverified items. None blocks the merge. Each item links its sources for manual review.</p>']
    head = "<tr><th>ID</th><th>Item</th><th>Detail</th><th>Sources</th></tr>"
    rows = []
    for n, (_, title, detail, srcs) in enumerate(FLAGS, 1):
        fid = "F-%02d" % n
        links = " · ".join('<a href="%s">link %d</a>' % (esc(s), i + 1) for i, s in enumerate(srcs))
        rows.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (fid, esc(title), esc(detail), links))
    parts.append('<div class="tbl-wrap"><table>%s%s</table></div>' % (head, "".join(rows)))
    parts.append("<h2>Per-row flags</h2><p>Codes used in the tables: F-NOID (no Hotspawn match id), F-NAME (unusual team name), F-AMBIG (ambiguous Valve name), F-MAP (team name mapped, see numbered flags), F-PLACEHOLDER (EGW 1.80/1.80, not used), F-NOOWN (no unambiguous Valve row), F-DISAGREE (external pick differs from own model), F-OWNONLY (pick from own model, no external line).</p>")
    return "".join(parts)


def sources_page():
    items = [
        ("Hotspawn CS2 Pick'em lobby (official)", LOBBY, "Fixture list, start times (UTC), team names, lock offset. Crowd % shown on the page is never used."),
        ("Hotspawn lobby (all games)", "https://play.hotspawn.com/lobby", "Count of matches (68 this week) and tier/tournament counts."),
        ("EGamersWorld, CCT Europe 2026 Series #11 (event)", EGW_CCT11, "Event page; ex-RUSTEC-mellren and FORZE-LFO placeholders. Match pages: Gothic-Lavked, G2 Ares-TLR."),
        ("EGamersWorld, Thunderpick World Championship 2026 (event)", EGW_TPWC, "Event page; match pages used for 9z-Aurora, Falcons-NiP, Legacy-PARIVISION, FURIA-BetBoom."),
        ("EGamersWorld, Stake Pulse Beat III (event)", EGW_STAKE, "Event page; match pages used for Astralis-Sashi, HOTU-fnatic, MIBR-BC.Game, Heroic-Team Envy."),
        ("EGamersWorld, Elisa Esports BreakOut Series 2 (event schedule)", EGW_EVENT_ELISA, "All 12 Elisa matches (prices in the event schedule)."),
        ("EGamersWorld, CCT Europe 2026 Series #12 Play-In (event)", EGW_EVENT_PLAYIN, "Placeholder 1.80/1.80 on all four Play-In rows; team names and times."),
        ("Valve Regional Standings 2026-10-05 (official, GitHub)", VRS_FILE_URL, "Points and team names; each own-line row links its line in the file at commit eec4853."),
        ("Valve Regional Standings repository", "https://github.com/ValveSoftware/counter-strike_regional_standings", "Source of the standings file."),
        ("Liquipedia, Elisa BreakOut Series #2", "https://liquipedia.net/counterstrike/Elisa/BreakOut_Series/2", "Team names (WhiteBIT Team, Esport Academy Copenhagen). Time-zone conflict is listed on the Flagged page."),
        ("bo5.gg, Elisa Breakout Series 2 (group stage)", "https://bo5.gg/cs2/tournaments/elisa-breakout-series-2-group-stage/", "Kick-off 08:00 UTC for the first Elisa matches."),
        ("Calibration: model/input/vrs/calibration.json", "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/model/input/vrs/calibration.json", "Slope k = 0.4568 (k_published, adopted)."),
    ]
    rows = "".join('<tr><td>%s</td><td><a href="%s">%s</a></td><td>%s</td></tr>' % (esc(a), esc(b), esc(b), esc(c)) for a, b, c in items)
    return ('<h2>Sources</h2><p>Each row of the tables links the exact page it used. Odds and standings are read from the pages listed here; nothing is inferred.</p>'
            '<div class="tbl-wrap"><table><tr><th>Source</th><th>Link</th><th>Used for</th></tr>%s</table></div>' % rows)


def method_page():
    return """<h2>Method</h2>
<ol>
<li><b>Fixtures.</b> Every row of the live CS2 pick'em lobby (play.hotspawn.com/cs2-pickems) is listed. Start times are UTC. Lock time = start - 6 min (lock_offset_sec 360 in the Hotspawn data).</li>
<li><b>External line.</b> Decimal 1X2 prices shown on EGamersWorld match pages and event schedules (aggregated headline prices). Placeholder 1.80/1.80 pairs are discarded. De-vig is proportional: p_A = (1/odds_A) / (1/odds_A + 1/odds_B). The overround is shown.</li>
<li><b>Own line.</b> Valve's Regional Standings curve, P(A) = 1 / (1 + 10^(-k*(pts_A - pts_B)/400)), with k = 0.4568 (the calibrated slope adopted in model/input/vrs/calibration.json). Points are read from Valve's 2026-10-05 standings file. A team with two Valve rows, or no Valve row, gets no own line.</li>
<li><b>Pick.</b> The higher external probability. If no verified external line exists, the higher own probability is used and labelled "own model only". If neither exists, there is no pick.</li>
<li><b>Not used.</b> Hotspawn crowd percentages (the 'picked' figures) are never read as inputs or shown as probabilities. HLTV world ranks were not used in this session.</li>
<li><b>Limits.</b> The external line is one headline price pair per match, not a bookmaker consensus. Prices move; the capture window is stated on every page. Own lines use the latest published Valve standings (2026-10-05).</li>
</ol>
<p>Reproduce: <code>python3 picks/build.py</code> from the repository root. Inputs are the hand-entered values at the top of that file, each with its source.</p>"""


def main():
    rows = build_rows()
    stale = write_csv(rows)
    pages = {
        "index.html": ("Dashboard", "index.html", dashboard(rows)),
        "matches.html": ("All matches", "matches.html", "<h2>All matches (open, locked and started)</h2>" + match_table(rows) + match_cards(rows)),
        "tournaments.html": ("By tournament", "tournaments.html", tournaments_page(rows)),
        "not-pickable.html": ("Not pickable", "not-pickable.html", not_pickable_page(rows, stale)),
        "flagged.html": ("Flagged for review", "flagged.html", flagged_page()),
        "sources.html": ("Sources", "sources.html", sources_page()),
        "method.html": ("Method", "method.html", method_page()),
    }
    for name, (title, active, body) in pages.items():
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(page(title, active, body))
    with open(os.path.join(OUT, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    print("rows", len(rows), "stale", len(stale), "open", sum(1 for r in rows if r["status"] == "Open"),
          "external", sum(1 for r in rows if r["ext_p_a"] != ""), "picks", sum(1 for r in rows if r["pick"]))


if __name__ == "__main__":
    main()
