#!/usr/bin/env python3
"""P-01 (arena/9569108d): build the current-slate Hotspawn pick'em analysis site.

Inputs
  * FIXTURES below: one row per fixture visible in the live Hotspawn lobby
    (https://play.hotspawn.com/lobby, fetched 2026-10-13 ~21:15-21:30 UTC),
    plus two started fixtures kept for transparency. Lobby times are shown in
    EDT (UTC-4) and converted to UTC here.
  * External lines: EGamersWorld headline odds copied from the EGW match, event or
    listing page named in each row (fetched in the same session). Method is
    de-vig of a two-way price pair. Only rows whose page was read are priced.
  * Own line: model/data/lines.csv (session 91eff436, Valve Regional Standings
    model, read-only). Probabilities are taken as published there; not re-run.
Outputs (picks/): index.html, matches.html, tournaments.html, flagged.html,
  sources.html, method.html, style.css, data/fixtures.csv, data/fixtures.json
Run: python3 picks/build.py   (from the repository root)
"""
import csv, datetime, html, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "picks")
AS_OF = "2026-10-13 22:00 UTC"
NOW = datetime.datetime(2026, 10, 13, 22, 0)
EGW_LISTING = "https://egamersworld.com/counterstrike/matches"
OVERRIDE_CSV = os.path.join(OUT, "data", "egw_listing_2026-10-13.csv")
EXT_SRC = "EGamersWorld CS2 matches listing (headline odds), read 2026-10-13 ~22:00 UTC"

LOBBY = "https://play.hotspawn.com/lobby"
EGW_CCT11 = "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"
EGW_STAKE = "https://egamersworld.com/counterstrike/event/stake-pulse-beat-iii-EJZmJpBjeNx"
EGW_TP = "https://egamersworld.com/counterstrike/event/thunderpick-world-championship-2026-5X5sFiL7H"
EGW_SA7 = "https://egamersworld.com/counterstrike/event/cct-south-america-2026-series-7-0U32SId-H"
HS = "https://www.hotspawn.com/matches/"

# id, start_utc, lobby_edt, tournament, tier, points, stage, team_a, team_b,
# hotspawn_url, ext(odds_a, odds_b) or None, ext_url, ext_source, status
# Status: "open" = lobby listed and lock time not yet reached at AS_OF;
#         "started" = start time passed; not pickable.
FIXTURES = [
 ("", "2026-10-13 22:00", "Oct 13 18:00", "CCT South America 2026 Series #7", "C", 2, "",
  "SUKEBAN", "your end", LOBBY, (2.96, 1.33), EGW_SA7, "EGamersWorld event page listing (headline odds)"),
 ("1079546", "2026-10-14 01:00", "Oct 13 21:00", "ESL Challenger League S52: North America - Cup #3", "B", 3, "",
  "Zomblers", "Overtake Sector", HS + "zomblers-vs-overtake-sector-esl-challenger-league-season-52-north-america-cup-3-1079546",
  (2.52, 1.48), "https://egamersworld.com/counterstrike/match/41yion_ONx/zomblers-vs-overtake-sector-3aN5jQsN_", "EGamersWorld match page (headline odds)"),
 ("", "2026-10-14 08:00", "Oct 14 04:00", "CCT Europe 2026 Series #12 Play-In", "C", 2, "",
  "Enjoy", "B8 Academy", LOBBY, None, "", ""),
 ("1079621", "2026-10-14 08:00", "Oct 14 04:00", "CCT Europe 2026 Series #11", "B", 3, "",
  "Gothic", "Lavked", HS + "gothic-vs-lavked-cct-europe-2026-series-11-1079621",
  (2.05, 1.64), "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B", "EGamersWorld match page (headline odds)"),
 ("1080176", "2026-10-14 08:30", "Oct 14 04:30", "Thunderpick World Championship 2026", "S", 7, "Group stage and playoffs",
  "9z", "Aurora", HS + "9z-vs-aurora-thunderpick-world-championship-2026-1080176",
  (3.8, 1.22), "https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb", "EGamersWorld Thunderpick event page listing (headline odds)"),
 ("1079438", "2026-10-14 10:00", "Oct 14 06:00", "Stake Pulse Beat III", "B", 3, "",
  "Astralis", "Sashi", HS + "astralis-vs-sashi-stake-pulse-beat-iii-1079438",
  (1.09, 6.27), "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z", "EGamersWorld match page (headline odds)"),
 ("1079439", "2026-10-14 10:00", "Oct 14 06:00", "Stake Pulse Beat III", "B", 3, "",
  "HOTU", "Fnatic", HS + "hotu-vs-fnatic-stake-pulse-beat-iii-1079439", None, "", ""),
 ("", "2026-10-14 11:00", "Oct 14 07:00", "CCT Europe 2026 Series #12 Play-In", "C", 2, "",
  "Banda chuya", "6666", LOBBY, None, "", ""),
 ("1079622", "2026-10-14 11:00", "Oct 14 07:00", "CCT Europe 2026 Series #11", "B", 3, "",
  "ex-RUSTEC", "mellren", HS + "ex-rustec-vs-mellren-cct-europe-2026-series-11-1079622", None, "", ""),
 ("1080177", "2026-10-14 11:00", "Oct 14 07:00", "Thunderpick World Championship 2026", "S", 7, "Group stage and playoffs",
  "Falcons", "Ninjas in Pyjamas", HS + "falcons-vs-ninjas-in-pyjamas-thunderpick-world-championship-2026-1080177",
  (1.2, 4.0), "https://egamersworld.com/counterstrike/match/5X5sFiL7H/falcons-vs-nip-QSa-aeOIR", "EGamersWorld Thunderpick event page listing (headline odds)"),
 ("1080178", "2026-10-14 13:30", "Oct 14 09:30", "Thunderpick World Championship 2026", "S", 7, "Group stage and playoffs",
  "Legacy", "PARIVISION", HS + "legacy-vs-parivision-thunderpick-world-championship-2026-1080178", None, "", ""),
 ("", "2026-10-14 14:00", "Oct 14 10:00", "CCT Europe 2026 Series #12 Play-In", "C", 2, "",
  "Ryvex", "PCIFIC", LOBBY, None, "", ""),
 ("1079623", "2026-10-14 14:00", "Oct 14 10:00", "CCT Europe 2026 Series #11", "B", 3, "",
  "G2 Ares", "The Last Resort", HS + "g2-ares-vs-the-last-resort-cct-europe-2026-series-11-1079623",
  (1.465, 2.436), EGW_CCT11, "EGamersWorld event page bets block (bc.game prices)"),
 ("1080179", "2026-10-14 16:00", "Oct 14 12:00", "Thunderpick World Championship 2026", "S", 7, "Group stage and playoffs",
  "FURIA", "BetBoom", HS + "furia-vs-betboom-thunderpick-world-championship-2026-1080179", None, "", ""),
 ("1079624", "2026-10-14 17:00", "Oct 14 13:00", "CCT Europe 2026 Series #11", "B", 3, "",
  "FORZE Reload", "LFO 10", HS + "forze-reload-vs-lfo-10-cct-europe-2026-series-11-1079624", None, "", ""),
 ("1080279", "2026-10-15 08:00", "Oct 15 04:00", "Elisa BreakOut Series #2", "C", 2, "",
  "WROTBERRY", "EAC", HS + "wrotberry-vs-eac-elisa-breakout-series-2-1080279", None, "", ""),
 ("1079440", "2026-10-15 10:00", "Oct 15 06:00", "Stake Pulse Beat III", "B", 3, "",
  "MIBR", "BC.Game", HS + "mibr-vs-bc-game-stake-pulse-beat-iii-1079440", None, "", ""),
 ("1079442", "2026-10-15 10:00", "Oct 15 06:00", "Stake Pulse Beat III", "B", 3, "",
  "Heroic", "Envy", HS + "heroic-vs-envy-stake-pulse-beat-iii-1079442", None, "", ""),
 ("1080280", "2026-10-15 10:00", "Oct 15 06:00", "Elisa BreakOut Series #2", "C", 2, "",
  "ENCE", "BOJONG", HS + "ence-vs-bojong-elisa-breakout-series-2-1080280", None, "", ""),
 ("1080281", "2026-10-15 12:00", "Oct 15 08:00", "Elisa BreakOut Series #2", "C", 2, "",
  "WROTBERRY", "ENCE", HS + "wrotberry-vs-ence-elisa-breakout-series-2-1080281", None, "", ""),
 ("1080282", "2026-10-15 14:00", "Oct 15 10:00", "Elisa BreakOut Series #2", "C", 2, "",
  "EAC", "BOJONG", HS + "eac-vs-bojong-elisa-breakout-series-2-1080282", None, "", ""),
 ("1080283", "2026-10-15 16:00", "Oct 15 12:00", "Elisa BreakOut Series #2", "C", 2, "",
  "WROTBERRY", "BOJONG", HS + "wrotberry-vs-bojong-elisa-breakout-series-2-1080283", None, "", ""),
 ("1080284", "2026-10-15 18:00", "Oct 15 14:00", "Elisa BreakOut Series #2", "C", 2, "",
  "EAC", "ENCE", HS + "eac-vs-ence-elisa-breakout-series-2-1080284", None, "", ""),
 ("1080285", "2026-10-16 08:00", "Oct 16 04:00", "Elisa BreakOut Series #2", "C", 2, "",
  "Voca", "Phantom", HS + "voca-vs-phantom-elisa-breakout-series-2-1080285", None, "", ""),
 ("1080286", "2026-10-16 10:00", "Oct 16 06:00", "Elisa BreakOut Series #2", "C", 2, "",
  "HAVU", "RoundsGG", HS + "havu-vs-roundsgg-elisa-breakout-series-2-1080286", None, "", ""),
 ("1080287", "2026-10-16 12:00", "Oct 16 08:00", "Elisa BreakOut Series #2", "C", 2, "",
  "Voca", "HAVU", HS + "voca-vs-havu-elisa-breakout-series-2-1080287", None, "", ""),
 ("", "2026-10-16 14:00", "Oct 16 10:00", "CCT Europe 2026 Series #12 Play-In", "C", 2, "",
  "mellren", "Privateer", LOBBY, None, "", ""),
 ("1080288", "2026-10-16 14:00", "Oct 16 10:00", "Elisa BreakOut Series #2", "C", 2, "",
  "Phantom", "RoundsGG", HS + "phantom-vs-roundsgg-elisa-breakout-series-2-1080288", None, "", ""),
 ("1080289", "2026-10-16 16:00", "Oct 16 12:00", "Elisa BreakOut Series #2", "C", 2, "",
  "RoundsGG", "Voca", HS + "roundsgg-vs-voca-elisa-breakout-series-2-1080289", None, "", ""),
 ("1080290", "2026-10-16 18:00", "Oct 16 14:00", "Elisa BreakOut Series #2", "C", 2, "",
  "Phantom", "HAVU", HS + "phantom-vs-havu-elisa-breakout-series-2-1080290", None, "", ""),
 # Started before AS_OF; kept for transparency only.
 ("1081076", "2026-10-13 21:00", "Oct 13 17:00", "ESL Challenger League S52: South America - Cup #3", "B", 3, "",
  "ex-Keyd Stars", "Galorys", HS + "ex-keyd-stars-vs-galorys-esl-challenger-league-season-52-south-america-cup-3-1081076",
  (2.62, 1.40), "https://egamersworld.com/counterstrike/match/Nylyio3_OEx/ex-keyd-stars-vs-galorys-0LRbemybp", "EGamersWorld match page (headline odds)"),
 ("1079620", "2026-10-13 17:00", "Oct 13 13:00", "CCT Europe 2026 Series #11", "B", 3, "",
  "Black Phoenix", "6666", HS + "black-phoenix-vs-6666-cct-europe-2026-series-11-1079620", None, "", ""),
]

NO_ID_NOTE = "No Hotspawn match ID visible in the lobby capture; the fixture is listed but its ID is not verified."


def load_listing():
    """EGW listing readings (picks/data/egw_listing_2026-10-13.csv), keyed by (start_utc, team_a, team_b)."""
    out = {}
    with open(OVERRIDE_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[(r["start_utc"], r["team_a"], r["team_b"])] = r
    return out


def load_own():
    own = {}
    with open(os.path.join(ROOT, "model", "data", "lines.csv"), newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            own[r["hotspawn_match_id"]] = r
    return own


def pct(x):
    return None if x is None else round(x * 100, 1)


def build_rows():
    own_all = load_own()
    listing = load_listing()
    rows = []
    for i, fx in enumerate(FIXTURES, 1):
        (fid, start, edt, tour, tier, pts, stage, a, b, hs_url, ext, ext_url, ext_src) = fx
        lst = listing.get((start, a, b))
        if lst is None:
            raise SystemExit(f"no EGW listing reading for {start} {a} vs {b}")
        if lst["status"] == "ok":
            ext = (float(lst["odds_a"]), float(lst["odds_b"]))
            ext_url, ext_src = lst["egw_url"], EXT_SRC
        else:
            ext, ext_url, ext_src = None, lst["egw_url"], lst["status"]
        start_dt = datetime.datetime.strptime(start, "%Y-%m-%d %H:%M")
        lock_dt = start_dt - datetime.timedelta(minutes=6)
        started = start_dt <= NOW
        status = "Started (not pickable)" if started else ("Open" if lock_dt > NOW else "Locked")
        flags = []
        own_agrees_default = "n/a"
        r = dict(seq=i, hotspawn_id=fid, start_utc=start, lock_utc=lock_dt.strftime("%Y-%m-%d %H:%M"),
                 lobby_display_edt=edt, tournament=tour, tier=tier, points=pts, stage=stage,
                 team_a=a, team_b=b, hotspawn_url=hs_url, status=status)
        if not fid:
            flags.append("F-NOID")
        # External line (de-vigged two-way pair).
        if ext:
            oa, ob = ext
            ia, ib = 1 / oa, 1 / ob
            pa = ia / (ia + ib)
            r.update(ext_odds_a=oa, ext_odds_b=ob, ext_overround_pct=round((ia + ib - 1) * 100, 2),
                     ext_p_a=pct(pa), ext_p_b=pct(1 - pa), ext_source=ext_src, ext_url=ext_url)
        else:
            r.update(ext_odds_a=None, ext_odds_b=None, ext_overround_pct=None, ext_p_a=None,
                     ext_p_b=None, ext_source=lst["note"] or "No verified price", ext_url=ext_url)
            flags.append("F-NOLINE")
            if lst["status"] == "placeholder":
                flags.append("F-PLACEHOLDER")
        # Own line (VRS model, read-only).
        o = own_all.get(fid) if fid else None
        if o and o["own_p_a"]:
            pa_own = float(o["own_p_a"]) / 100
            if o["team_a"].lower() != a.lower():
                # team order differs: flip (model stores its own team_a)
                if o["team_b"].lower() == a.lower():
                    pa_own = 1 - pa_own
                else:
                    raise SystemExit(f"own-model team mismatch for {fid}: {o['team_a']} vs {a}")
            r.update(own_p_a=pct(pa_own), own_p_b=pct(1 - pa_own), own_url=o["vrs_a_url"] or "",
                     own_hltv_a=o["hltv_a_url"], own_hltv_b=o["hltv_b_url"])
        else:
            r.update(own_p_a=None, own_p_b=None, own_url="", own_hltv_a="", own_hltv_b="")
            if fid:
                flags.append("F-NOOWN")
        # Pick: external line is primary; own model only when no external line.
        r["own_agrees"] = own_agrees_default
        if status != "Open":
            r.update(pick="", pick_p=None, basis=("Not pickable: start time has passed" if started
                     else "Not pickable: lobby lock time has passed"))
        elif r["ext_p_a"] is not None:
            side = a if r["ext_p_a"] >= r["ext_p_b"] else b
            r.update(pick=side, pick_p=max(r["ext_p_a"], r["ext_p_b"]), basis="External bookmaker line (de-vigged)")
            if r["own_p_a"] is not None:
                own_side = a if r["own_p_a"] >= r["own_p_b"] else b
                r["own_agrees"] = "yes" if own_side == side else "no"
                if own_side != side:
                    flags.append("F-DISAGREE")
            else:
                r["own_agrees"] = "n/a"
        elif r["own_p_a"] is not None:
            side = a if r["own_p_a"] >= r["own_p_b"] else b
            r.update(pick=side, pick_p=max(r["own_p_a"], r["own_p_b"]), basis="Own VRS model only (no external line)")
            r["own_agrees"] = "n/a"
        else:
            r.update(pick="", pick_p=None, basis="No pick: no verified external line and no own line")
            r["own_agrees"] = "n/a"
        if started:
            flags.append("F-STARTED")
        if status == "Locked":
            flags.append("F-LOCKED")
        if r["ext_p_a"] is not None and r["ext_p_a"] and abs(r["ext_p_a"] - 50) < 3 and status == "Open":
            flags.append("F-NEAR50")
        r["flags"] = flags
        rows.append(r)
    return rows


FLAG_TEXT = {
 "F-NOID": ("Unverified ID", "Listed in the live lobby but no Hotspawn match ID/link is visible in the capture. " + NO_ID_NOTE),
 "F-NOLINE": ("No verified external line", "No EGamersWorld price was captured for this fixture in this session. Left blank; no value inferred."),
 "F-NOOWN": ("No own line", "Our VRS model has no line for this fixture (team not resolvable to one official row, or not in the model). Left blank."),
 "F-DISAGREE": ("Model vs market disagree", "Our VRS model favours the other side from the external line. Shown as found; review."),
 "F-STARTED": ("Started", "Start time has passed at the as-of time. Shown for transparency; not pickable."),
 "F-LOCKED": ("Locked", "Lobby lock time has passed at the as-of time (Hotspawn shows 'Locked'). Shown for transparency; not pickable."),
 "F-PLACEHOLDER": ("EGW placeholder", "EGamersWorld lists 1.80/1.80 (or no opponent) for this fixture. Treated as a placeholder, not odds. Left blank; no value inferred."),
 "F-NEAR50": ("Near coin-flip", "External probability within 3 points of 50/50. Low-confidence pick."),
}


def fmt_p(p):
    return "—" if p is None else f"{p:.1f}%"


def fmt_odds(o):
    return "—" if o is None else f"{o:.2f}"


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


CSS = """
:root{--bg:#0f1420;--card:#171e2e;--ink:#e8edf7;--mut:#9aa6bf;--acc:#5ad1a0;--warn:#f5b84b;--bad:#ff7a7a;--line:#26304a;--link:#8ec5ff}
*{box-sizing:border-box}html,body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
a{color:var(--link)}header{padding:14px 16px;background:#0b101b;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
header .brand{font-weight:700;font-size:17px;margin-right:12px}nav a{margin-right:12px;text-decoration:none;font-size:14px;display:inline-block;padding:4px 0}
main{padding:16px;max-width:1200px;margin:0 auto}h1{font-size:22px;margin:4px 0 6px}h2{font-size:17px;margin:22px 0 8px}
.sub{color:var(--mut);font-size:13px;margin-bottom:12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}.kpi b{display:block;font-size:22px}.kpi span{color:var(--mut);font-size:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;text-decoration:none;color:var(--ink);display:block}
.card b{display:block;margin-bottom:4px}.card span{color:var(--mut);font-size:13px}
table{width:100%;border-collapse:collapse;background:var(--card);border-radius:10px;overflow:hidden;font-size:14px}
th,td{padding:8px 9px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#121a2a;color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.03em}
.pick{font-weight:700;color:var(--acc)}.nopick{color:var(--warn);font-weight:600}.muted{color:var(--mut)}
.badge{display:inline-block;padding:1px 7px;border-radius:999px;font-size:11px;border:1px solid var(--line);margin:1px 2px 1px 0;color:var(--mut)}
.badge.warn{color:var(--warn);border-color:var(--warn)}.badge.bad{color:var(--bad);border-color:var(--bad)}.badge.ok{color:var(--acc);border-color:var(--acc)}
.note{background:#1c2438;border:1px solid var(--line);border-radius:10px;padding:10px 12px;color:var(--mut);font-size:13px;margin:10px 0}
footer{color:var(--mut);font-size:12px;padding:20px 16px;text-align:center}
@media (max-width:760px){
  header nav a{margin-right:9px;font-size:13px}
  table.responsive thead{display:none}
  table.responsive,table.responsive tbody,table.responsive tr,table.responsive td{display:block;width:100%}
  table.responsive tr{border-bottom:1px solid var(--line);padding:8px 4px}
  table.responsive td{border:0;padding:3px 6px;display:flex;justify-content:space-between;gap:10px}
  table.responsive td::before{content:attr(data-label);color:var(--mut);font-size:12px;flex:0 0 40%}
  table.responsive td.nolabel::before{content:none}
  table.responsive td.nolabel{display:block}
}
"""

NAV = [("index.html", "Dashboard"), ("matches.html", "All matches"), ("tournaments.html", "By tournament"),
       ("flagged.html", "Flagged for review"), ("sources.html", "Sources"), ("method.html", "Method")]


def page(title, active, body):
    cur = ' aria-current="page"'
    nav = "".join('<a href="%s"%s>%s</a>' % (href, cur if href == active else "", label) for href, label in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · Hotspawn CS2 Pick'em analysis</title>
<link rel="stylesheet" href="style.css">
</head><body>
<header><span class="brand">Hotspawn CS2 Pick'em · analysis</span><nav>{nav}</nav></header>
<main>{body}</main>
<footer>Probabilities: external bookmaker prices (EGamersWorld, de-vigged) and our VRS model. Hotspawn crowd % is never used. As of {AS_OF}. <a href="../">Repository home</a></footer>
</body></html>
"""


def pick_cell(r):
    if r["pick"]:
        return f'<span class="pick">{esc(r["pick"])}</span> <span class="muted">({fmt_p(r["pick_p"])})</span>'
    return '<span class="nopick">No pick</span>'


def flag_badges(r):
    out = []
    for f in r["flags"]:
        cls = "bad" if f in ("F-NOID", "F-NOLINE", "F-PLACEHOLDER") else ("warn" if f not in ("F-STARTED",) else "")
        out.append(f'<span class="badge {cls}">{esc(FLAG_TEXT[f][0])}</span>')
    return "".join(out)


def source_cell(r):
    links = []
    if r["ext_url"]:
        links.append(f'<a href="{esc(r["ext_url"])}" rel="noopener">EGW odds</a>')
    if r["hotspawn_url"]:
        links.append(f'<a href="{esc(r["hotspawn_url"])}" rel="noopener">Hotspawn</a>')
    if r["own_url"]:
        links.append(f'<a href="{esc(r["own_url"])}" rel="noopener">Valve VRS</a>')
    return " · ".join(links) if links else '<span class="muted">—</span>'


def match_table(rows, responsive=True):
    head = "<tr><th>#</th><th>Start (UTC)</th><th>Tier · pts</th><th>Match</th><th>External win %</th><th>Own model win %</th><th>Pick</th><th>Status</th><th>Flags</th><th>Sources</th></tr>"
    body = []
    for r in rows:
        match = f'<b>{esc(r["team_a"])}</b> vs <b>{esc(r["team_b"])}</b><div class="muted">{esc(r["tournament"])}</div>'
        ext = (f'{esc(r["team_a"])} {fmt_p(r["ext_p_a"])} · {esc(r["team_b"])} {fmt_p(r["ext_p_b"])}'
               f'<div class="muted">odds {fmt_odds(r["ext_odds_a"])} / {fmt_odds(r["ext_odds_b"])}</div>') if r["ext_p_a"] is not None else '<span class="nopick">Unverified (blank)</span>'
        own = (f'{esc(r["team_a"])} {fmt_p(r["own_p_a"])} · {esc(r["team_b"])} {fmt_p(r["own_p_b"])}') if r["own_p_a"] is not None else '<span class="muted">Blank</span>'
        body.append(
            f'<tr><td data-label="#">{r["seq"]}</td>'
            f'<td data-label="Start (UTC)">{esc(r["start_utc"])}<div class="muted">lock {esc(r["lock_utc"])}</div></td>'
            f'<td data-label="Tier · pts">{esc(r["tier"])} · {r["points"]}</td>'
            f'<td data-label="Match">{match}</td>'
            f'<td data-label="External win %">{ext}</td>'
            f'<td data-label="Own model win %">{own}</td>'
            f'<td data-label="Pick">{pick_cell(r)}<div class="muted">{esc(r["basis"])}</div></td>'
            f'<td data-label="Status">{esc(r["status"])}</td>'
            f'<td data-label="Flags">{flag_badges(r)}</td>'
            f'<td data-label="Sources">{source_cell(r)}</td></tr>')
    cls = ' class="responsive"' if responsive else ""
    return f"<table{cls}><thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"


def write(path, text):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    rows = build_rows()
    open_rows = [r for r in rows if r["status"] == "Open"]
    n_ext = sum(1 for r in rows if r["ext_p_a"] is not None and r["status"] != "Started (not pickable)")
    n_own = sum(1 for r in rows if r["own_p_a"] is not None and r["status"] != "Started (not pickable)")
    n_pick = sum(1 for r in rows if r["pick"])
    n_flag = sum(1 for r in rows if any(f != "F-STARTED" for f in r["flags"]))

    # Data exports
    os.makedirs(os.path.join(OUT, "data"), exist_ok=True)
    cols = ["seq", "hotspawn_id", "start_utc", "lock_utc", "lobby_display_edt", "tournament", "tier", "points", "stage",
            "team_a", "team_b", "status", "ext_odds_a", "ext_odds_b", "ext_overround_pct", "ext_p_a", "ext_p_b",
            "ext_source", "ext_url", "own_p_a", "own_p_b", "own_url", "pick", "pick_p", "basis", "own_agrees",
            "hotspawn_url", "flags"]
    with open(os.path.join(OUT, "data", "fixtures.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            rr = dict(r)
            rr["flags"] = ";".join(r["flags"])
            w.writerow(rr)
    with open(os.path.join(OUT, "data", "fixtures.json"), "w", encoding="utf-8") as f:
        json.dump({"as_of": AS_OF, "lobby_source": LOBBY, "rows": rows}, f, indent=1, ensure_ascii=False)

    # Landing
    next_rows = [r for r in rows if r["status"] == "Open" and r["pick"]][:12]
    cat_cards = [("matches.html", "All matches", f"{len(rows)} lobby rows: probabilities, pick, sources, status"),
                 ("tournaments.html", "By tournament", "Same data grouped by event (Thunderpick, Stake, CCT, Elisa)"),
                 ("flagged.html", "Flagged for review", f"{n_flag} rows carry a flag; irregularities in other sessions' data"),
                 ("sources.html", "Sources", "Every source URL, what it was used for, and when it was read"),
                 ("method.html", "Method", "How probabilities, picks and blanks are produced")]
    cards = "".join(f'<a class="card" href="{h}"><b>{esc(t)}</b><span>{esc(d)}</span></a>' for h, t, d in cat_cards)
    landing = f"""
<h1>Current CS2 slate: win probability and pick per match</h1>
<div class="sub">Source of fixtures: Hotspawn live lobby · Prices: EGamersWorld (de-vigged) · Own line: Valve Regional Standings model · As of {AS_OF}</div>
<div class="kpis">
  <div class="kpi"><b>{len(rows) - 2}</b><span>Fixtures in lobby</span></div>
  <div class="kpi"><b>{len(open_rows)}</b><span>Open for picks</span></div>
  <div class="kpi"><b>{n_ext}</b><span>With external line</span></div>
  <div class="kpi"><b>{n_own}</b><span>With own model line</span></div>
  <div class="kpi"><b>{n_pick}</b><span>Rows with a pick</span></div>
</div>
<div class="note"><b>Pick rule.</b> The pick is the side with the higher external (bookmaker-derived) win probability. Our own VRS-model line is shown next to it as a cross-check; where the two disagree the row is flagged. Hotspawn crowd % is never an input. A blank means no verified line exists, and none is inferred.</div>
<h2>Next picks (open rows, earliest first)</h2>
<div class="sub">Full table with every row and flags: <a href="matches.html">All matches</a></div>
{match_table(next_rows)}
<h2>Explore</h2>
<div class="cards">{cards}</div>
"""
    write("index.html", page("Dashboard", "index.html", landing))

    write("matches.html", page("All matches", "matches.html",
          f"<h1>All Hotspawn CS2 fixtures in the lobby</h1><div class=\"sub\">{len(rows)} rows (2 started rows kept for transparency). Win % = share of the pair's de-vigged probability.</div>"
          + match_table(rows)))

    groups = {}
    for r in rows:
        groups.setdefault(r["tournament"], []).append(r)
    sec = []
    for t, rs in sorted(groups.items(), key=lambda kv: kv[1][0]["start_utc"]):
        sec.append(f"<h2>{esc(t)} <span class=\"muted\">({len(rs)})</span></h2>{match_table(rs)}")
    write("tournaments.html", page("By tournament", "tournaments.html",
          "<h1>By tournament</h1><div class=\"sub\">Fixtures grouped by event, earliest group first.</div>" + "".join(sec)))

    flagged_rows = [r for r in rows if any(f != "F-STARTED" for f in r["flags"]) or r["flags"]]
    fl_items = []
    for r in rows:
        for f in r["flags"]:
            title, text = FLAG_TEXT[f]
            srcs = " · ".join(x for x in [
                f'<a href="{esc(r["hotspawn_url"])}">Hotspawn fixture</a>' if r["hotspawn_url"] else "",
                f'<a href="{esc(r["ext_url"])}">EGW page</a>' if r["ext_url"] else "",
                f'<a href="{esc(r["own_url"])}">Valve VRS row</a>' if r["own_url"] else ""] if x)
            fl_items.append(f"<tr><td data-label=\"Row\">#{r['seq']} {esc(r['team_a'])} vs {esc(r['team_b'])}</td>"
                            f"<td data-label=\"Flag\"><span class=\"badge\">{esc(title)}</span></td>"
                            f"<td data-label=\"Detail\">{esc(text)}</td><td data-label=\"Sources\">{srcs}</td></tr>")
    gen = ("<h2>Irregularities in source data (for owner review)</h2><table class=\"responsive\"><thead><tr><th>Item</th><th>Flag</th><th>Detail</th><th>Sources</th></tr></thead><tbody>"
           + "".join(fl_items) + "</tbody></table>")
    irr = [
     ("IR-9569-01", "Lobby header says 68 matches this week, but only 30 CS2 rows are visible in the lobby capture. The gap (~38) is unexplained and may include LoL or non-listed rows.", LOBBY),
     ("IR-9569-02", "The lobby shows times in EDT (UTC-4). Some earlier repo files record start times as the rendered local clock, not UTC (see IR-91-05 in COORDINATION.md). All times here are converted to UTC from the lobby display.", LOBBY),
     ("IR-9569-03", "EGamersWorld shows times in UTC+2. Its odds pages were matched to Hotspawn fixtures by team names and converted kickoff times.", "https://egamersworld.com/counterstrike/events"),
     ("IR-9569-04", "The existing repo file data/6d9c321d/external_bookmaker_lines.csv carries EGW prices labelled '1.80/1.80 placeholder' for H-00, 1079622 and 1079624. Those are placeholders, not odds. They are not used here.", "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
     ("IR-9569-05", "Several stored EGW links in the repo reuse one match ID across different fixtures (for example _rW8GEyWK for Black Phoenix, Gothic, ex-RUSTEC and FORZE), and some point at blog pages. They were not used.", "https://egamersworld.com/counterstrike/event/cct-europe-2026-series-11-_rW8GEyWK"),
     ("IR-9569-06", "Stored prices disagree with the live pages. Example: Gothic vs Lavked stored 2.10/1.62 (a BC.Game row in data/6d9c321d) vs live headline 2.05/1.64; Astralis vs Sashi stored 1.11/6.20 (model/data/lines.csv) vs live headline 1.09/6.27. Stored and live rows are different captures; live headline values are used here.", "https://egamersworld.com/counterstrike/match/_rW8GEyWK/gothic-vs-lavked-GGmfuJ1n4B"),
     ("IR-9569-07", "The own VRS line for 1079621 and others is taken from model/data/lines.csv as published. It was not re-run here, and its VRS source file was dated 2026-10-05.", "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md"),
     ("IR-9569-08", "Five lobby rows have no visible Hotspawn match ID: SUKEBAN vs your end, Enjoy vs B8 Academy, Banda chuya vs 6666, Ryvex vs PCIFIC, mellren vs Privateer. They are shown as unverified and have no pick.", LOBBY),
     ("IR-9569-09", "Lock time is taken as start minus 6 minutes, which matches the Hotspawn payload value of lock_offset_sec = 360 recorded for other fixtures. It is not confirmed per fixture.", "https://play.hotspawn.com/lobby"),
     ("IR-9569-10", "The EGW headline price is an aggregator figure, and its bookmaker source is not shown on the headline. Only one price pair per match is used, so the sample is thin and there is single-source concentration risk.", "https://egamersworld.com/counterstrike/events"),
     ("IR-2210-01", "Prices were re-read from the EGamersWorld CS2 listing on 2026-10-13 ~22:00 UTC. They differ from the earlier per-match readings kept in this repo (for example Gothic vs Lavked 2.05/1.64 then, 1.881/1.782 now; Falcons vs NiP 1.2/4.0 then, 1.23/3.81 now). The current listing values are used; the earlier values are superseded.", EGW_LISTING),
     ("IR-2210-02", "Four fixtures show 1.80/1.80 (or no opponent name) on the EGamersWorld listing: Banda chuya vs 6666, Ryvex vs PCIFIC, FORZE Reload vs LFO 10, mellren vs Privateer. They are treated as placeholders, left blank and have no pick unless the own model covers them.", EGW_LISTING),
     ("IR-2210-03", "EGamersWorld shows 'WBT' for the team Hotspawn lists as WROTBERRY. The identity was carried over from the prior session (A-07). It was not re-verified in this session. Please check it against HLTV or Liquipedia.", EGW_LISTING),
     ("IR-2210-04", "Hotspawn lists SUKEBAN vs your end (CCT South America Series #7) as Locked at the as-of time. It is shown but not picked.", LOBBY),
     ("IR-2210-05", "All external prices come from one aggregator (EGamersWorld headline odds). No second bookmaker or independent line was read for any row in this session. Single-source concentration risk applies to every priced row.", EGW_LISTING),
     ("IR-2210-06", "The site is a static snapshot. It was built at 2026-10-13 ~22:00 UTC and is not refreshed automatically. Prices and lock state will be stale after a short time.", LOBBY),
     ("IR-9569-11", "The ng-state capture in data/6d9c321d lists 59 stale fixtures from June–July 2026 still marked 'scheduled'. They are excluded here because the live lobby no longer lists them.", "https://play.hotspawn.com/lobby"),
    ]
    irr_html = ("<h2>Review items (published, non-blocking)</h2><table class=\"responsive\"><thead><tr><th>ID</th><th>Item</th><th>Source</th></tr></thead><tbody>"
                + "".join(f"<tr><td data-label=\"ID\">{i}</td><td data-label=\"Item\">{esc(t)}</td><td data-label=\"Source\"><a href=\"{esc(u)}\">link</a></td></tr>" for i, t, u in irr)
                + "</tbody></table>")
    write("flagged.html", page("Flagged for review", "flagged.html",
          "<h1>Flagged for review</h1><div class=\"sub\">Unverified or irregular items. Published, not blocking. Each item links its source so it can be checked.</div>"
          + gen + irr_html))

    srcs = [
     ("Hotspawn live lobby (fixture list, times, lock state; Hotspawn crowd % not used)", LOBBY, "Fixture list (CS2 rows), tiers, points, times in EDT, Locked/Open state, 2026-10-13 ~21:58-22:02 UTC"),
     ("Hotspawn fixture pages (per fixture)", HS, "Fixture links; exact per-row URL in the table"),
     ("EGamersWorld CS2 matches listing (headline odds for every open row)", EGW_LISTING, "External bookmaker-odds source for every priced row. Read 2026-10-13 ~22:00 UTC. Per-row match link in the table and in data/egw_listing_2026-10-13.csv"),
     ("EGamersWorld CCT Europe Series #11 event page", EGW_CCT11, "Event context only (team list); prices come from the listing"),
     ("EGamersWorld Stake Pulse Beat III event page", EGW_STAKE, "Event context only"),
     ("EGamersWorld Thunderpick event page", EGW_TP, "Event context only"),
     ("EGamersWorld CCT South America Series #7 event page", EGW_SA7, "Event context only"),
     ("Valve Regional Standings (official GitHub), used by our model", "https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md", "Own VRS-model inputs (read via model/, not re-run)"),
     ("HLTV World Ranking, used by our model", "https://www.hltv.org/ranking/teams/2026/october/12", "Cross-check ranks (model/)"),
    ]
    srows = "".join(f"<tr><td data-label=\"Source\">{esc(a)}</td><td data-label=\"Link\"><a href=\"{esc(u)}\">{esc(u)}</a></td><td data-label=\"Used for\">{esc(b)}</td></tr>" for a, u, b in srcs)
    write("sources.html", page("Sources", "sources.html",
          "<h1>Sources</h1><div class=\"sub\">Every external URL used on this site. Fetched in session on 2026-10-13 (~21:58–22:05 UTC) unless stated.</div>"
          f"<table class=\"responsive\"><thead><tr><th>Source</th><th>Link</th><th>Used for</th></tr></thead><tbody>{srows}</tbody></table>"))

    method = """
<h1>Method</h1>
<div class="note"><b>External line.</b> EGamersWorld CS2 matches listing headline odds for both sides (one reading per row, 2026-10-13 ~22:00 UTC; the reading and link for each row are in <code>picks/data/egw_listing_2026-10-13.csv</code>). Implied probability = 1/odds. The two-way pair is normalised: p_A = (1/o_A)/((1/o_A)+(1/o_B)). Overround is shown per row. Prices of 1.80/1.80 or with no opponent name are treated as placeholders and left blank.</div>
<div class="note"><b>Own line.</b> The Valve Regional Standings points of each roster, through the calibrated model in <code>model/</code> (session 91eff436). Values are read from <code>model/data/lines.csv</code> as published. They are not re-run here. Blank where the team cannot be resolved to one official row.</div>
<div class="note"><b>Pick.</b> Pick = side with higher external probability. If no external line exists, the own-model side is shown and labelled "own model only". If neither exists, no pick.</div>
<div class="note"><b>Times.</b> Lobby display is EDT. Converted to UTC. Lock = start − 6 min (see Flagged IR-9569-09). A row whose lock time has passed at the as-of time is shown as Locked and is not pickable.</div>
<div class="note"><b>Not used.</b> Hotspawn crowd percentages are never an input or displayed. HLTV community %, Polymarket, and any other prediction source are not used.</div>
<div class="note"><b>Build.</b> <code>python3 picks/build.py</code> regenerates every page and <code>data/fixtures.csv</code> from the inputs above.</div>
"""
    write("method.html", page("Method", "method.html", method))

    # Downloads and style
    with open(os.path.join(OUT, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)
    print(f"rows={len(rows)} open={len(open_rows)} ext={n_ext} own={n_own} picks={n_pick} flagged_rows={n_flag}")


if __name__ == "__main__":
    main()
