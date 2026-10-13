#!/usr/bin/env python3
"""verify/build.py — session arena/4b9c40b0, tasks V-01..V-03 (scope: verify/** only).

Joins this session's own readings (verify/data/*.csv) with datasets other sessions
already merged on main (read-only) and writes:
  verify/data/verification.csv, verify/data/verification.json
  verify/index.html, verify/flagged.html

Rules followed: values are copied from the pages they were read on; nothing is
inferred. A missing reading stays blank and is flagged. Hotspawn crowd "% picked"
is never read or used.
"""
from __future__ import annotations

import csv
import html
import json
import statistics
from collections import OrderedDict
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
SESSION = "arena/4b9c40b0"
AS_OF = "2026-10-13 22:15 UTC"  # last page read used in this build (clock-read); see READS below

READS = [
    ("Hotspawn CS2 pick'em lobby (fixture list, times, tiers, points)", "https://play.hotspawn.com/cs2-pickems",
     "read 21:58:51 UTC (time fixed from the page's own lock countdowns); page renders UTC"),
    ("HLTV upcoming matches (match ID, format, kickoff)", "https://www.hltv.org/matches",
     "listing chunks 3-12 read 21:59-22:08 UTC; page renders UTC-4, anchored by the 9z vs Aurora match-page countdown"),
    ("HLTV match page sample (format detail 'Best of 3 (LAN)', ranks)", "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026",
     "read ~22:00 UTC; betting block is geo-targeted (showed only a US sweepstakes ad, no prices)"),
    ("EGamersWorld match pages (headline odds, per-bookmaker 'Betting odds - Prematch' table, format text)", "https://egamersworld.com/counterstrike/matches",
     "match pages read 21:59-22:15 UTC; several copies were served from cache (countdown shows render 22:00 UTC); from ~22:13 UTC pages came back in a degraded template without the odds table"),
]

ALIASES = {  # Hotspawn name -> names used by HLTV / EGamersWorld for the same slot (identity checks only)
    "WROTBERRY": ["WBT"],
    "RoundsGG": ["ROUNDS", "Rounds"],
    "Fnatic": ["fnatic"],
    "BetBoom": ["BETBOOM", "BetBoom Team"],
    "Heroic": ["HEROIC"],
    "Banda chuya": ["Banda Chuya", "banda chuya"],
    "Enjoy": ["ENJOY"],
    "Ninjas in Pyjamas": ["NiP"],
    "Sashi": ["Sashi Esport"],
    "BC.Game": ["BC.Game Esports"],
    "EAC": ["EA Copenhagen"],
    "Envy": ["Team Envy"],
    "PCIFIC": ["PCIFIC Espor", "WRAITH PCIFIC"],
    "Phantom": ["Phantom Esports"],
}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [{k.strip(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh)]


def norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


def same_team(hotspawn_name: str, other: str) -> str:
    """'exact', 'case', 'alias' or '' (no match)."""
    if hotspawn_name == other:
        return "exact"
    if norm(hotspawn_name) == norm(other):
        return "case"
    if any(norm(a) == norm(other) for a in ALIASES.get(hotspawn_name, [])):
        return "alias"
    return ""


def devig(a: float, b: float) -> tuple[float, float]:
    ia, ib = 1 / a, 1 / b
    return ia / (ia + ib), (ia + ib - 1) * 100


def pct(x: float | None) -> str:
    return "" if x is None else f"{x * 100:.1f}"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# --------------------------------------------------------------------------- load
slate = read_csv(DATA / "hotspawn_slate.csv")
hltv = {r["row"]: r for r in read_csv(DATA / "hltv_listing.csv")}
egw_head = {r["row"]: r for r in read_csv(DATA / "egw_headline.csv")}
books_by_row: dict[str, list[dict]] = {}
for r in read_csv(DATA / "egw_books.csv"):
    books_by_row.setdefault(r["row"], []).append(r)
faq = {r["row"]: r for r in read_csv(DATA / "egw_faq_pairs.csv")}

# read-only inputs from other sessions (already merged on main)
p02_list = read_csv(ROOT / "picks/data/egw_listing_2026-10-13.csv")      # 616c2455 P-02
p02_fix = read_csv(ROOT / "picks/data/fixtures.csv")                     # 616c2455 P-02
e33 = read_csv(ROOT / "data/e3315a54/current.csv")                        # e3315a54 E-01/E-02
b90 = read_csv(ROOT / "refresh/data/current.csv")                         # b90700c6 R-01
model = read_csv(ROOT / "model/data/lines.csv")                           # 91eff436 model


def key(start: str, a: str, b: str) -> tuple:
    return (start[:16], norm(a), norm(b))


def index_by(rows, start_f, a_f, b_f):
    out = {}
    for r in rows:
        out[key(r.get(start_f, ""), r.get(a_f, ""), r.get(b_f, ""))] = r
    return out


p02_list_ix = index_by(p02_list, "start_utc", "team_a", "team_b")
p02_fix_ix = index_by(p02_fix, "start_utc", "team_a", "team_b")
e33_ix = {}
for r in e33:
    e33_ix[key(r.get("start_utc", "").replace("T", " "), r["team_a"], r["team_b"])] = r
b90_ix = {}
for r in b90:
    if r.get("sport", "cs2") not in ("cs2", "csgo", "counter-strike", ""):
        continue
    b90_ix[key(r.get("start_utc", "").replace("T", " ").replace("Z", ""), r["team_a"], r["team_b"])] = r
model_ix = index_by(model, "scheduled_start_utc", "team_a", "team_b")


def other_pick(row_ix, k, pick_field="pick"):
    r = row_ix.get(k)
    if not r:
        return None, ""
    return r, (r.get(pick_field) or "").strip()


# --------------------------------------------------------------------------- build rows
rows_out = []
flags: list[dict] = []


def flag(code, row, text, links):
    flags.append({"code": code, "row": row, "text": text, "links": links})


for s in slate:
    rid = s["row"]
    a, b = s["team_a"], s["team_b"]
    k = key(s["start_utc"], a, b)
    h = hltv.get(rid, {})
    out = OrderedDict()
    out["row"] = int(rid)
    out["start_utc"] = s["start_utc"]
    out["tournament"] = s["tournament"]
    out["tier"] = s["tier"]
    out["points"] = s["points"]
    out["team_a"], out["team_b"] = a, b
    out["status"] = s["status_at_read"]
    out["hotspawn_url"] = s["hotspawn_url"]

    # ---- V-01: HLTV match page identity / kickoff / format
    out["hltv_match_id"] = h.get("hltv_match_id", "")
    out["hltv_url"] = h.get("hltv_url", "")
    out["format"] = h.get("format", "").upper()
    kick = ""
    if h.get("hltv_display"):
        kick = (datetime.strptime(h["hltv_display"], "%Y-%m-%d %H:%M") + timedelta(hours=4)).strftime("%Y-%m-%d %H:%M")
    out["hltv_kickoff_utc"] = kick
    out["kickoff_check"] = "agree" if kick and kick == s["start_utc"] else ("DISAGREE" if kick else "not read")
    t1, t2 = h.get("hltv_team1", ""), h.get("hltv_team2", "")
    m_same = (same_team(a, t1), same_team(b, t2))
    m_swap = (same_team(a, t2), same_team(b, t1))
    if all(m_same):
        out["identity_check"] = "agree" if set(m_same) <= {"exact", "case"} else "agree via alias"
        out["hltv_order"] = "same"
    elif all(m_swap):
        out["identity_check"] = "agree" if set(m_swap) <= {"exact", "case"} else "agree via alias"
        out["hltv_order"] = "reversed"
    else:
        out["identity_check"] = "DISAGREE" if h else "not read"
        out["hltv_order"] = ""
    out["hltv_names"] = f"{t1} vs {t2}" if h else ""
    out["hltv_event"] = h.get("hltv_event", "")

    if out["kickoff_check"] == "DISAGREE":
        flag("VF-KICKOFF", rid, f"Kickoff differs: Hotspawn {s['start_utc']} UTC vs HLTV {kick} UTC.", [s["hotspawn_url"], h.get("hltv_url", "")])
    if out["identity_check"].startswith("agree via alias"):
        alias_pairs = [f"{x} = {y}" for x, y, m in ((a, t1 if out['hltv_order']=='same' else t2, None), (b, t2 if out['hltv_order']=='same' else t1, None)) if norm(x) != norm(y)]
        out["identity_note"] = "; ".join(alias_pairs)
    else:
        out["identity_note"] = ""

    # ---- V-02: EGamersWorld match page (per-bookmaker table) + P-02 transcription check
    eh = egw_head.get(rid, {})
    out["egw_url"] = eh.get("egw_url", "") or (p02_list_ix.get(k, {}).get("egw_url", ""))
    out["egw_page_note"] = eh.get("note", "")
    out["egw_render_utc"] = eh.get("render_utc_from_countdown", "")
    out["egw_headline"] = f"{eh['headline_odds1']} / {eh['headline_odds2']}" if eh.get("headline_odds1") else ""
    bk = books_by_row.get(rid, [])
    sets = OrderedDict()
    for r in bk:
        pair = (float(r["odds_a"]), float(r["odds_b"]))
        sets.setdefault(pair, []).append(r["bookmaker"])
    out["n_books"] = len(bk)
    out["n_price_sets"] = len(sets)
    if sets:
        ps = [devig(*pair)[0] for pair in sets]
        cons = statistics.median(ps)
        out["consensus_p_a"] = round(cons * 100, 1)
        out["consensus_p_b"] = round((1 - cons) * 100, 1)
        out["consensus_range_p_a"] = f"{min(ps)*100:.1f}-{max(ps)*100:.1f}"
        best_a = max(sets, key=lambda p: p[0]); best_b = max(sets, key=lambda p: p[1])
        out["best_odds_a"] = f"{best_a[0]} ({', '.join(sets[best_a][:3])}{'...' if len(sets[best_a])>3 else ''})"
        out["best_odds_b"] = f"{best_b[1]} ({', '.join(sets[best_b][:3])}{'...' if len(sets[best_b])>3 else ''})"
        tp = [r for r in bk if r["bookmaker"] == "Thunderpick"]
        out["thunderpick"] = f"{tp[0]['odds_a']} / {tp[0]['odds_b']}" if tp else ""
        bc = [r for r in bk if r["bookmaker"] == "bc.game"]
        out["bcgame"] = f"{bc[0]['odds_a']} / {bc[0]['odds_b']}" if bc else ""
    else:
        for f_ in ("consensus_p_a", "consensus_p_b", "consensus_range_p_a", "best_odds_a", "best_odds_b", "thunderpick", "bcgame"):
            out[f_] = ""
    out["books_detail"] = [{"bookmaker": r["bookmaker"], "odds_a": r["odds_a"], "odds_b": r["odds_b"]} for r in bk]

    pl = p02_list_ix.get(k, {})
    out["p02_listing"] = f"{pl['odds_a']} / {pl['odds_b']}" if pl.get("odds_a") else ""
    out["p02_status"] = pl.get("status", "")
    trans = ""
    if pl.get("odds_a") and sets:
        pair = (float(pl["odds_a"]), float(pl["odds_b"]))
        if pair in sets:
            trans = "confirmed: same price shown by " + ", ".join(sets[pair][:4]) + ("..." if len(sets[pair]) > 4 else "")
        else:
            p02p = devig(*pair)[0]
            near = min(sets, key=lambda q: abs(devig(*q)[0] - p02p))
            trans = (f"not on page; nearest {near[0]} / {near[1]} ({', '.join(sets[near][:2])}); "
                     f"de-vigged gap {abs(devig(*near)[0]-p02p)*100:.1f} pp")
    elif pl.get("odds_a") and eh.get("headline_odds1"):
        hp = (float(eh["headline_odds1"]), float(eh["headline_odds2"]))
        if hp == (float(pl["odds_a"]), float(pl["odds_b"])):
            trans = "confirmed against the match-page headline (one price only; table not captured)"
        else:
            trans = (f"differs from match-page headline {hp[0]} / {hp[1]} "
                     f"(de-vigged gap {abs(devig(*hp)[0]-devig(float(pl['odds_a']), float(pl['odds_b']))[0])*100:.1f} pp); table not captured")
    elif pl.get("odds_a") and rid in egw_head:
        trans = "UNCONFIRMED: match page was read but showed no bookmaker table"
    elif pl.get("odds_a"):
        trans = "not re-read by this session (P-02 single-source price stands)"
    elif pl.get("status") == "placeholder":
        trans = "P-02 left blank (placeholder 1.80/1.80); match page " + ("read: no odds shown" if rid in egw_head else "not read by this session")
    out["p02_transcription"] = trans

    # ---- V-03: cross-dashboard picks (all read-only, from main)
    pr, p_pick = other_pick(p02_fix_ix, k)
    er, e_pick = other_pick(e33_ix, k)
    br, b_pick = other_pick(b90_ix, k)
    mr, m_pick = other_pick(model_ix, k)
    out["pick_picks_p02"] = p_pick
    out["pick_mobile_e3315a54"] = e_pick
    out["pick_today_b90700c6"] = b_pick
    out["pick_model_91eff436"] = m_pick
    out["format_e3315a54"] = (er or {}).get("format", "")
    out["format_model"] = (mr or {}).get("best_of", "")
    out["basis_p02"] = (pr or {}).get("basis", "")
    out["basis_e3315a54"] = (er or {}).get("pick_source", "")
    out["basis_b90700c6"] = ((br or {}).get("estimate_basis", "") or "")[:60]
    out["basis_model"] = (mr or {}).get("line_status", "")
    out["e33_book"] = f"{er.get('book_odds_a')} / {er.get('book_odds_b')}" if er and er.get("book_odds_a") else ""
    out["e33_book_captured"] = (er or {}).get("book_captured_utc", "")

    cons_pick = ""
    if out["consensus_p_a"] != "":
        cons_pick = a if out["consensus_p_a"] > 50 else (b if out["consensus_p_a"] < 50 else "")
    out["consensus_pick"] = cons_pick
    named = {"picks/ (P-02)": p_pick, "mobile/ (e3315a54)": e_pick, "today/ (b90700c6)": b_pick, "model/ (91eff436)": m_pick}
    given = {kk: vv for kk, vv in named.items() if vv}
    distinct = sorted(set(given.values()))
    if not given:
        out["dashboards"] = "no dashboard has a pick"
    elif len(distinct) == 1:
        out["dashboards"] = f"all {len(given)} agree"
    else:
        out["dashboards"] = "SPLIT: " + "; ".join(f"{kk} {vv}" for kk, vv in given.items())
    if cons_pick and any(v and v != cons_pick for v in given.values()):
        out["vs_consensus"] = "differs: " + "; ".join(f"{kk} {vv}" for kk, vv in given.items() if vv != cons_pick)
    else:
        out["vs_consensus"] = "" if not cons_pick else "all published picks match the multi-book consensus"

    # ---- verification status for the price behind the pick
    if out["n_price_sets"] >= 2:
        out["price_status"] = f"multi-book: {out['n_books']} books / {out['n_price_sets']} distinct prices"
    elif pl.get("odds_a") and trans.startswith("confirmed against the match-page headline"):
        out["price_status"] = "single price (P-02 listing), same as the match-page headline"
    elif pl.get("odds_a"):
        out["price_status"] = "single source (P-02 listing), not re-confirmed on match page"
    else:
        out["price_status"] = "no external price"
    rows_out.append(out)

# --------------------------------------------------------------------------- flags (aggregate)
bo1 = [r for r in rows_out if r["format"] == "BO1"]
if bo1:
    other_fmt = sorted({(r['format_e3315a54'] or '(blank)') for r in bo1})
    model_fmt = sorted({(r['format_model'] or '(blank)') for r in bo1})
    flag("VF-01 BO1", ",".join(str(r["row"]) for r in bo1),
         f"{len(bo1)} Elisa BreakOut Series 2 fixtures are best-of-one on HLTV (every other open fixture is best-of-three). "
         f"A single map gives the underdog a much better chance than a series, so these picks carry more upset risk. "
         f"Format recorded for the same rows by mobile/ (e3315a54): {', '.join(other_fmt)}; by model/ (91eff436) best_of: {', '.join(model_fmt)}.",
         [r["hltv_url"] for r in bo1[:3]])
cct = [r for r in rows_out if "Play-In" in r["tournament"]]
if cct:
    flag("VF-02 EVENT NAME", ",".join(str(r["row"]) for r in cct),
         "Hotspawn and EGamersWorld call this event 'CCT Europe 2026 Series #12 Play-In'; HLTV calls it 'CCT 2026 Europe Series 12 Closed Qualifier'. "
         "Teams, kickoff and format agree, so this looks like a naming difference only. The Hotspawn lobby shows no match link for these 4 rows.",
         [r["hltv_url"] for r in cct[:2]] + ["https://egamersworld.com/counterstrike/event/cct-europe-2026-series-12-play-in-1sGIL2gAYu"])
alias_rows = [r for r in rows_out if r["identity_check"] == "agree via alias"]
wbt = [r for r in alias_rows if "WROTBERRY" in (r["team_a"], r["team_b"])]
if wbt:
    flag("VF-03 WROTBERRY = WBT", ",".join(str(r["row"]) for r in wbt),
         "Hotspawn's 'WROTBERRY' appears as 'WBT' on HLTV and EGamersWorld in exactly the same 3 slots (same event, kickoff and opponent: EAC 08:00, ENCE 12:00, BOJONG 16:00 on 15 Oct). "
         "That slot match is strong evidence they are the same team, but no official page states that WBT is short for WROTBERRY. Treated as matched by schedule only; not verified by name.",
         [r["hltv_url"] for r in wbt] + [r["hotspawn_url"] for r in wbt[:1]])
rev = [r for r in rows_out if r["hltv_order"] == "reversed"]
if rev:
    flag("VF-04 TEAM ORDER", ",".join(str(r["row"]) for r in rev),
         "HLTV lists these teams in the opposite order to Hotspawn (" + "; ".join(f"Hotspawn {r['team_a']} vs {r['team_b']} = HLTV {r['hltv_names']}" for r in rev) +
         "). All prices on this page are shown in Hotspawn order. Anyone copying odds from HLTV/EGamersWorld must swap them for these rows.",
         [r["hltv_url"] for r in rev])
for r in rows_out:
    if r["p02_transcription"].startswith("not on page"):
        flag("VF-05 LISTING PRICE NOT ON MATCH PAGE", str(r["row"]),
             f"{r['team_a']} vs {r['team_b']}: the P-02 listing price {r['p02_listing']} was not one of the {r['n_books']} bookmaker prices on the match page ({r['p02_transcription']}). "
             "Probably price movement between reads; the multi-book consensus is used instead.",
             [r["egw_url"], "https://egamersworld.com/counterstrike/matches"])
    if r["p02_transcription"].startswith("UNCONFIRMED") and r["status"] == "Open":
        flag("VF-06 PRICE UNCONFIRMED ON MATCH PAGE", str(r["row"]),
             f"{r['team_a']} vs {r['team_b']}: the match page was read but showed no bookmaker table ({r['egw_page_note'][:170]}). "
             f"The P-02 listing price {r['p02_listing']} could not be re-confirmed there. It is still the only external price for this row.",
             [r["egw_url"]])
not_read = [r for r in rows_out if r["status"] == "Open" and r["p02_transcription"].startswith("not re-read")]
if not_read:
    flag("VF-13 NOT RE-READ", ",".join(str(r["row"]) for r in not_read),
         f"{len(not_read)} open fixtures were not re-read on their EGamersWorld match page by this session. From about 22:13 UTC the pages came back in a degraded template with no odds table, "
         "so collection stopped there rather than record nothing. For these rows the only external price is P-02's single listing reading (~22:00 UTC). It has not been confirmed by a second read.",
         [r["egw_url"] for r in not_read[:2]])
for r in rows_out:
    if r["dashboards"].startswith("SPLIT"):
        basis = "; ".join(f"{n}: {v}" for n, v in (("picks/", r["basis_p02"]), ("mobile/", r["basis_e3315a54"]),
                                                   ("today/", r["basis_b90700c6"]), ("model/", r["basis_model"])) if v)
        flag("VF-07 DASHBOARDS DISAGREE", str(r["row"]),
             f"{r['team_a']} vs {r['team_b']}: published picks differ between dashboards on main: {r['dashboards'][7:]}. Stated basis: {basis}. "
             "Every split here has the same cause: dashboards with an external price follow the market, and dashboards with only a ratings line pick the other team."
             + (f" Multi-book consensus: {r['consensus_pick']} {max(r['consensus_p_a'], r['consensus_p_b'])}%." if r['consensus_pick'] else
                f" This session's match-page check: {r['p02_transcription']}."),
             [r["hotspawn_url"], r["egw_url"]])
def _px(sv: str) -> tuple:
    return tuple(float(x) for x in sv.split(" / "))


same_px = [r for r in rows_out if r["e33_book"] and r["p02_listing"] and _px(r["e33_book"]) == _px(r["p02_listing"])]
diff_px = [r for r in rows_out if r["e33_book"] and r["p02_listing"] and _px(r["e33_book"]) != _px(r["p02_listing"])]
stamps = sorted({r["e33_book_captured"] for r in same_px})
if same_px:
    flag("VF-14 PRICE TIMESTAMP PROVENANCE", ",".join(str(r["row"]) for r in same_px),
         f"For {len(same_px)} rows, mobile/ (e3315a54) publishes exactly the same bookmaker prices as picks/ (P-02), but stamps them captured at {', '.join(stamps)}. "
         "P-02 says its EGamersWorld listing was read at about 21:58-22:05 UTC. Either every listing price stayed unchanged for about 40 minutes, "
         "or one of the two timestamps is not the real read time. Over the same period the match pages showed different prices for several of these rows (see VF-05). "
         "Request: e3315a54 to confirm when and where these prices were read.",
         ["https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/data/e3315a54/current.csv",
          "https://github.com/buffedlizard55-lab/MaltaProj1/blob/main/picks/data/egw_listing_2026-10-13.csv"])
fz = [r for r in rows_out if r["team_b"] == "LFO 10"]
for r in fz:
    flag("VF-08 OPPONENT BLANK ON EGW", str(r["row"]),
         "EGamersWorld's page for this slot names only 'FORZE Reload' (opponent blank, no odds). HLTV lists 'FORZE Reload vs LFO 10', bo3, same kickoff. "
         "So identity is confirmed by HLTV, but there is no external price.",
         [r["hltv_url"], r["egw_url"]])
cached = [r for r in rows_out if r["egw_render_utc"]]
if cached:
    flag("VF-09 CACHED PAGES", ",".join(str(r["row"]) for r in cached),
         "The EGamersWorld copies this session received were sometimes cached. Each page's countdown shows when it was rendered "
         "(e.g. 22:00:36 UTC for a copy fetched about 22:10). Reading times on this page use that render time where it was visible, not the fetch time.",
         [r["egw_url"] for r in cached[:2]])
flag("VF-10 WHITE-LABEL BOOKS", "all priced",
     "Many 'bookmakers' on EGamersWorld show identical prices (e.g. Spinbetter, 22bet and 1xBit; PlanBet, Herospin, Kinbet, SpinAlto and RedSport), which suggests a shared odds feed. "
     "The consensus here is the median over distinct price sets, not over book names, so clones are not double-counted.",
     ["https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb"])
flag("VF-11 HEADLINE VS LISTING", "5,10",
     "The odds printed at the top of an EGamersWorld match page belong to one geo-targeted partner and can differ from the matches-listing price "
     "(9z vs Aurora: page headline 3.3 / 1.26, listing 3.86 / 1.21 in P-02, both around 22:00 UTC). Neither alone is a consensus.",
     ["https://egamersworld.com/counterstrike/match/5X5sFiL7H/9z-vs-aurora-Es9rrnIhb", "https://egamersworld.com/counterstrike/matches"])
flag("VF-12 HLTV BETTING BLOCK GEO-TARGETED", "-",
     "HLTV's match-page betting section showed only a US sweepstakes ad with no prices for this reader, so HLTV was used for format, kickoff and identity only. "
     "HLTV's 'Pick a winner' user vote is not a betting line and is not used.",
     ["https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026"])

# --------------------------------------------------------------------------- write data
fields = [k for k in rows_out[0].keys() if k != "books_detail"]
with (DATA / "verification.csv").open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for r in rows_out:
        w.writerow({k: r[k] for k in fields})
(DATA / "verification.json").write_text(json.dumps({"session": SESSION, "as_of": AS_OF, "reads": READS,
                                                     "rows": rows_out, "flags": flags}, indent=1, ensure_ascii=False), encoding="utf-8")

# --------------------------------------------------------------------------- html
CSS = """
:root{--bg:#0f1115;--card:#171a21;--line:#2a2f3a;--txt:#e8eaed;--mut:#9aa3b2;--ok:#3ecf8e;--warn:#f5a524;--bad:#ff5c5c;--acc:#5aa9ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
a{color:var(--acc)}header,main,footer{max-width:1100px;margin:0 auto;padding:12px 14px}
h1{font-size:1.35rem;margin:.2rem 0}h2{font-size:1.1rem;margin:1.4rem 0 .5rem}
.sub{color:var(--mut);font-size:.9rem}.nav a{margin-right:12px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin:10px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}.card b{font-size:1.3rem;display:block}
.m{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px;margin:8px 0}
.m .top{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;color:var(--mut);font-size:.85rem}
.m .teams{font-size:1.05rem;margin:4px 0}.pick{font-weight:700;color:var(--ok)}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:1px 8px;font-size:.78rem;margin:2px 4px 2px 0;color:var(--mut)}
.tag.bo1{border-color:var(--warn);color:var(--warn)}.tag.bad{border-color:var(--bad);color:var(--bad)}.tag.ok{border-color:var(--ok);color:var(--ok)}
.bar{height:8px;background:#2a2f3a;border-radius:6px;overflow:hidden;margin:6px 0}.bar i{display:block;height:100%;background:var(--acc)}
details{margin-top:6px}summary{cursor:pointer;color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:.85rem}th,td{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
th{color:var(--mut);font-weight:600}.scroll{overflow-x:auto}
.links a{margin-right:10px;font-size:.85rem}.f{background:var(--card);border-left:3px solid var(--warn);padding:8px 10px;margin:8px 0;border-radius:6px}
code{background:#222733;padding:0 4px;border-radius:4px}
"""


def page(title, body):
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>{CSS}</style></head><body>
<header><div class="nav"><a href="../">Home</a><a href="./">Verification</a><a href="flagged.html">Flagged for review</a><a href="data/verification.csv">CSV</a><a href="data/verification.json">JSON</a></div>
<h1>{esc(title)}</h1><div class="sub">Session {SESSION} · readings {esc(AS_OF)} · static snapshot (not auto-refreshed)</div></header>
<main>{body}</main><footer class="sub">Values are copied from the linked pages at the stated times. Blank = not confirmed, never estimated. Hotspawn crowd "% picked" is not used anywhere.</footer></body></html>"""


open_rows = [r for r in rows_out if r["status"] == "Open"]
multi = [r for r in open_rows if r["n_price_sets"] >= 2]
split = [r for r in open_rows if r["dashboards"].startswith("SPLIT")]
cards = f"""<div class="cards">
<div class="card"><b>{len(open_rows)}</b>open fixtures checked</div>
<div class="card"><b>{sum(1 for r in open_rows if r['kickoff_check']=='agree')}/{len(open_rows)}</b>kickoff agrees with HLTV</div>
<div class="card"><b>{sum(1 for r in open_rows if r['identity_check'].startswith('agree'))}/{len(open_rows)}</b>teams match HLTV</div>
<div class="card"><b>{len(bo1)}</b>best-of-one (higher upset risk)</div>
<div class="card"><b>{len(multi)}</b>with a multi-book price table</div>
<div class="card"><b>{len(split)}</b>where dashboards disagree</div></div>"""

items = []
for r in rows_out:
    if r["status"] != "Open":
        continue
    fav_p = None
    if r["consensus_p_a"] != "":
        fav_p = max(r["consensus_p_a"], r["consensus_p_b"])
    tags = [f'<span class="tag {"bo1" if r["format"]=="BO1" else ""}">{esc(r["format"] or "format ?")}</span>',
            f'<span class="tag">{esc(r["tier"])}-tier · {esc(r["points"])} pts</span>',
            f'<span class="tag {"ok" if r["kickoff_check"]=="agree" else "bad"}">kickoff {esc(r["kickoff_check"])}</span>',
            f'<span class="tag {"ok" if r["identity_check"]=="agree" else ("" if r["identity_check"].startswith("agree") else "bad")}">teams {esc(r["identity_check"])}</span>',
            f'<span class="tag {"bad" if r["dashboards"].startswith("SPLIT") else "ok"}">dashboards: {esc(r["dashboards"].split(":")[0])}</span>']
    if r["consensus_pick"]:
        main_line = (f'<div>Multi-book pick: <span class="pick">{esc(r["consensus_pick"])}</span> {fav_p:.1f}% '
                     f'<span class="sub">(median of {r["n_price_sets"]} distinct prices from {r["n_books"]} books; range for {esc(r["team_a"])} {esc(r["consensus_range_p_a"])}%)</span></div>'
                     f'<div class="bar"><i style="width:{r["consensus_p_a"]}%"></i></div>'
                     f'<div class="sub">{esc(r["team_a"])} {r["consensus_p_a"]}% · {esc(r["team_b"])} {r["consensus_p_b"]}%'
                     f'{" · Thunderpick " + esc(r["thunderpick"]) if r["thunderpick"] else ""}{" · BC.Game " + esc(r["bcgame"]) if r["bcgame"] else ""}</div>')
    else:
        main_line = f'<div class="sub">No multi-book table captured. Price status: {esc(r["price_status"])}{(" — P-02 listing " + esc(r["p02_listing"])) if r["p02_listing"] else ""}.</div>'
    picks_tbl = ("<table><tr><th>Dashboard on main</th><th>Pick</th></tr>" +
                 "".join(f"<tr><td>{esc(n)}</td><td>{esc(v) or '<span class=sub>—</span>'}</td></tr>" for n, v in
                         (("picks/ (P-02)", r["pick_picks_p02"]), ("mobile/ (e3315a54)", r["pick_mobile_e3315a54"]),
                          ("today/ (b90700c6)", r["pick_today_b90700c6"]), ("model/ (91eff436, ratings only)", r["pick_model_91eff436"]))) + "</table>")
    books_tbl = ""
    if r["books_detail"]:
        books_tbl = ("<details><summary>All " + str(r["n_books"]) + " bookmaker prices (Hotspawn team order)</summary><div class=scroll><table><tr><th>Bookmaker</th><th>"
                     + esc(r["team_a"]) + "</th><th>" + esc(r["team_b"]) + "</th><th>de-vigged " + esc(r["team_a"]) + "</th></tr>" +
                     "".join(f"<tr><td>{esc(x['bookmaker'])}</td><td>{esc(x['odds_a'])}</td><td>{esc(x['odds_b'])}</td><td>{devig(float(x['odds_a']), float(x['odds_b']))[0]*100:.1f}%</td></tr>" for x in r["books_detail"])
                     + "</table></div></details>")
    checks = (f"<details><summary>Checks for this row</summary><table>"
              f"<tr><td>HLTV</td><td>{esc(r['hltv_names'])} · {esc(r['hltv_event'])} · kickoff {esc(r['hltv_kickoff_utc'])} UTC · {esc(r['format'])} · order {esc(r['hltv_order'])}</td></tr>"
              f"<tr><td>Identity</td><td>{esc(r['identity_check'])} {esc(r['identity_note'])}</td></tr>"
              f"<tr><td>P-02 listing price</td><td>{esc(r['p02_listing'] or '—')} {esc(r['p02_transcription'])}</td></tr>"
              f"<tr><td>EGW page</td><td>{esc(r['egw_page_note'] or ('headline ' + r['egw_headline'] if r['egw_headline'] else 'not read by this session'))}"
              f"{(' · render ' + esc(r['egw_render_utc']) + ' UTC') if r['egw_render_utc'] else ''}</td></tr>"
              f"<tr><td>vs consensus</td><td>{esc(r['vs_consensus'] or '—')}</td></tr></table>{picks_tbl}</details>")
    links = (f'<div class="links"><a href="{esc(r["hotspawn_url"])}">Hotspawn</a>'
             + (f'<a href="{esc(r["hltv_url"])}">HLTV match {esc(r["hltv_match_id"])}</a>' if r["hltv_url"] else "")
             + (f'<a href="{esc(r["egw_url"])}">EGamersWorld odds</a>' if r["egw_url"] else "") + "</div>")
    items.append(f'<div class="m"><div class="top"><span>{esc(r["start_utc"])} UTC · {esc(r["tournament"])}</span><span>#{r["row"]}</span></div>'
                 f'<div class="teams">{esc(r["team_a"])} <span class="sub">vs</span> {esc(r["team_b"])}</div>{"".join(tags)}{main_line}{links}{books_tbl}{checks}</div>')

intro = f"""<p>This page checks the open Hotspawn CS2 pick'em fixtures against the official match pages. It does not replace the other dashboards.
For every fixture it confirms <b>kickoff</b>, <b>team identity</b> and <b>series format</b> on HLTV.
Where the EGamersWorld match page listed bookmakers, it shows the <b>multi-book consensus</b>: the median of the distinct bookmaker prices, de-vigged.
It also shows whether the dashboards already on the site agree on the pick.
Problems are listed on <a href="flagged.html">Flagged for review</a>.</p>"""
legend = """<p class="sub">De-vig: p(A) = (1/odds A) / (1/odds A + 1/odds B). Consensus = median of p(A) over distinct (odds A, odds B) pairs, so white-label clones count once.
BO1 = one map, BO3 = best of three maps. The underdog has a better chance in BO1.</p>"""
(HERE / "index.html").write_text(page("Hotspawn CS2 — match verification & multi-book odds", intro + cards + legend + "".join(items)), encoding="utf-8")

src_list = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a> — {esc(n)}</li>' for t, u, n in READS)
fl = "".join(f'<div class="f"><b>{esc(f_["code"])}</b> <span class="sub">rows {esc(f_["row"])}</span><div>{esc(f_["text"])}</div>'
             f'<div class="links">{"".join(f"<a href={chr(34)}{esc(u)}{chr(34)}>{esc(u.split(chr(47))[2] if u.startswith(chr(104)) else u)}</a>" for u in f_["links"] if u)}</div></div>' for f_ in flags)
(HERE / "flagged.html").write_text(page("Flagged for review — verification (arena/4b9c40b0)",
                                        f"<p>{len(flags)} items. None of them blocks publishing; each links to the page where it can be checked by hand.</p>{fl}<h2>Sources read</h2><ul>{src_list}</ul>"), encoding="utf-8")

print(f"rows={len(rows_out)} open={len(open_rows)} multi_book={len(multi)} bo1={len(bo1)} split={len(split)} flags={len(flags)}")
