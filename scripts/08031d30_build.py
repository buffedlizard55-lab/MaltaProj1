#!/usr/bin/env python3
"""Build the open-slate page for session arena/08031d30.

Inputs (all in this repo):
  data/08031d30/hotspawn_open_cs2.csv   Hotspawn CS2 open list read on 2026-10-14 (hand-transcribed from the
                                        fetched official pages; every row carries the page it came from).
  data/08031d30/market_reads.csv        External bookmaker / odds-site reads made in this session, with URL + window.
  slate/data/analysis.csv               Published board of session 180a42a0 (read-only). Used ONLY for two things:
                                        (a) carried external prices for rows not re-read this session, labelled
                                        "carried", and (b) the originated own-line probabilities, labelled "carried".
Outputs:
  data/08031d30/open_slate.csv          One row per open fixture: probabilities, pick, basis, sources, flags.
  open-slate/index.html                 Mobile-first page (cards on phones, table on desktop).
  open-slate/flagged.html               Flagged for Review, with source links.

Rules (also published on the page):
  * Hotspawn crowd % is never an input to any probability or pick.
  * External prices are de-vigged two-way odds: p = (1/odds_a) / (1/odds_a + 1/odds_b).
  * A 1.80/1.80 pair is treated as a placeholder (not a market) and is never used.
  * Pick = higher external probability; if no external line, higher own-line probability (labelled own-only);
    if neither, no pick.
Run:  python3 scripts/08031d30_build.py
"""
import csv
import html
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "08031d30")
BOARD = os.path.join(ROOT, "slate", "data", "analysis.csv")
OUT_DIR = os.path.join(ROOT, "open-slate")

PLACEHOLDER = (1.8, 1.8)
NEAR_EVEN = 5.0  # percentage points: flag when the favourite is closer than this to 50%


def same(name_on_source, name):
    """Team-name match that tolerates case and suffixes such as 'ENJOY' vs 'Enjoy' or '9z Team' vs '9z'."""
    x, y = name_on_source.casefold().strip(), name.casefold().strip()
    return x == y or x.startswith(y + " ") or y.startswith(x + " ")


def devig(odds_a, odds_b):
    ia, ib = 1.0 / odds_a, 1.0 / odds_b
    s = ia + ib
    return 100.0 * ia / s, 100.0 * ib / s, 100.0 * (s - 1.0)


def load_hotspawn():
    with open(os.path.join(DATA, "hotspawn_open_cs2.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_reads():
    out = {}
    with open(os.path.join(DATA, "market_reads.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["fixture_id"], []).append(r)
    return out


def load_board():
    with open(BOARD, encoding="utf-8") as f:
        return {r["fixture_id"]: r for r in csv.DictReader(f)}


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build_rows():
    hs = load_hotspawn()
    reads = load_reads()
    board = load_board()
    rows = []
    for h in hs:
        fid = h["fixture_id"]
        if h["on_live_hotspawn_list"] != "yes":
            continue  # excluded rows are reported on the flagged page only
        a, b = h["team_a"], h["team_b"]
        flags = []
        ext = None  # dict with p_a, p_b, source, url, read, basis, fmt, odds
        # 1) fresh reads made in this session (first valid two-way read wins; placeholders skipped)
        for r in reads.get(fid, []):
            oa, ob = fnum(r["odds_a"]), fnum(r["odds_b"])
            if oa is None or ob is None:
                continue
            if (oa, ob) == PLACEHOLDER:
                src = r["source"].split(" (")[0]
                flags.append(f"Placeholder 1.80/1.80 pair on {src} ignored: not a market (see reviews/08031d30-repo-review.md)")
                continue
            if not same(r["team_a_on_source"], a):
                oa, ob = ob, oa  # source lists the teams in the other order
            pa, pb, ov = devig(oa, ob)
            if ext is None:
                ext = dict(p_a=pa, p_b=pb, odds_a=oa, odds_b=ob, source=r["source"], url=r["source_url"],
                           read=r["read_window_utc"], fmt=r["format_shown"], overround=ov, status="fresh")
            else:
                ext.setdefault("also", []).append(
                    (r["source"], r["source_url"], round(pa, 1), round(pb, 1), r["read_window_utc"]))
        # 2) carried board price (read by 180a42a0 on 2026-10-13), used only if no fresh read
        bd = board.get(fid)
        if ext is None and bd and bd.get("market_odds_a") and bd.get("market_odds_b"):
            oa, ob = fnum(bd["market_odds_a"]), fnum(bd["market_odds_b"])
            if oa and ob and (oa, ob) != PLACEHOLDER:
                if bd["team_a"] != a:
                    oa, ob = ob, oa
                pa, pb, ov = devig(oa, ob)
                ext = dict(p_a=pa, p_b=pb, odds_a=oa, odds_b=ob, source=bd["market_source"],
                           url=bd["market_url"], read=bd["market_captured_utc"], fmt="not stated on this read",
                           overround=ov, status="carried")
                flags.append("External price carried from 2026-10-13 board read; not re-read in this session")
        # 3) own line (carried from the published board; HLTV ranking + Valve VRS basis)
        own = None
        if bd and fnum(bd.get("own_series_p_a_pct")) is not None:
            pa = fnum(bd["own_series_p_a_pct"])
            if bd["team_a"] != a:
                pa = 100.0 - pa
            own = dict(p_a=pa, p_b=100.0 - pa, basis=bd.get("own_series_basis", "") or "HLTV + VRS (board)")
        elif bd and fnum(bd.get("own_p_a_pct")) is not None:
            pa = fnum(bd["own_p_a_pct"])
            if bd["team_a"] != a:
                pa = 100.0 - pa
            own = dict(p_a=pa, p_b=100.0 - pa, basis=bd.get("own_basis", "") or "HLTV + VRS (board)")
        if own is None:
            flags.append("No own line: at least one team has no official rating in the board's sources")
        for side, o in (("A", ext and ext["odds_a"]), ("B", ext and ext["odds_b"])):
            if o and o < 1.10:
                flags.append(f"Extreme price: odds {o:.3f} on the {side} side. Verify on the source match page")
        # 4) pick
        if ext:
            pa, pb = ext["p_a"], ext["p_b"]
            basis = "external line (" + ext["status"] + ")"
        elif own:
            pa, pb = own["p_a"], own["p_b"]
            basis = "own line only (no external line)"
            if not ext:
                flags.append("Pick is from the own line only: no external line for this fixture")
        else:
            pa, pb, basis = None, None, "no pick: no external line and no own line"
        if pa is not None:
            pick = a if pa >= pb else b
            fav = max(pa, pb)
            if abs(fav - 50.0) < NEAR_EVEN:
                flags.append(f"Near coin-flip: favourite {fav:.1f}% (under {NEAR_EVEN:.0f} points from 50%)")
            if ext and own and ((ext["p_a"] - 50) * (own["p_a"] - 50) < 0):
                flags.append("External and own line disagree on the favourite")
        else:
            pick = ""
        if ext and ext.get("fmt", "") in ("", "not stated on this read"):
            flags.append("Series format not stated on the price read")
        rows.append(dict(h=h, ext=ext, own=own, pick=pick, pa=pa, pb=pb, basis=basis, flags=flags))
    return rows


def pct(x):
    return "" if x is None else f"{x:.1f}%"


def esc(s):
    return html.escape(str(s if s is not None else ""))


def card(r):
    h, ext, own = r["h"], r["ext"], r["own"]
    a, b = h["team_a"], h["team_b"]
    pa, pb = r["pa"], r["pb"]
    if pa is None:
        probs = '<p class="none">No external line and no own line: <b>no pick</b>.</p>'
    else:
        fav_a = pa >= pb
        probs = f"""
        <div class="team {'win' if fav_a else ''}"><span>{esc(a)}</span><b>{pct(pa)}</b></div>
        <div class="bar"><i style="width:{pa:.1f}%"></i></div>
        <div class="team {'win' if not fav_a else ''}"><span>{esc(b)}</span><b>{pct(pb)}</b></div>"""
    pick_html = (f'<div class="pick">PICK: <b>{esc(r["pick"])}</b></div>' if r["pick"]
                 else '<div class="pick nopick">PICK: none</div>')
    if ext:
        srcline = (f'External: {esc(ext["source"])}, odds {ext["odds_a"]:.3f} / {ext["odds_b"]:.3f}, '
                   f'de-vig {ext["p_a"]:.1f}/{ext["p_b"]:.1f}, read {esc(ext["read"])} '
                   f'(<a href="{esc(ext["url"])}">source</a>)')
        for src, url, qa, qb, rd in ext.get("also", []):
            srcline += (f'<br>Second read: {esc(src)}, de-vig {qa:.1f}/{qb:.1f}, read {esc(rd)} '
                        f'(<a href="{esc(url)}">source</a>)')
    else:
        srcline = "External: no usable line (see flags)"
    own_line = (f'Own line: {esc(a)} {pct(own["p_a"])} / {esc(b)} {pct(own["p_b"])} '
                f'<span class="muted">({esc(own["basis"])})</span>') if own else "Own line: blank (no official rating)"
    flags_html = "".join(f"<li>{esc(f)}</li>" for f in r["flags"])
    return f"""
    <article class="card" id="m{esc(h['fixture_id'])}">
      <header>
        <div class="when">{esc(h['kickoff_utc'].replace('T', ' ').replace('Z', ' UTC'))}</div>
        <div class="comp">{esc(h['competition'])} · tier {esc(h['tier'])} · {esc(h['points'])} pts</div>
      </header>
      {probs}
      {pick_html}
      <div class="meta">{srcline}<br>{own_line}</div>
      <div class="meta">Hotspawn: <a href="{esc(h['hotspawn_lobby_url'])}">pick'em lobby</a>
        {(' · <a href="' + esc(h['hotspawn_match_url']) + '">match page</a>') if h['hotspawn_match_url'] else ''}
        · fixture {esc(h['fixture_id'])}</div>
      {('<ul class="flags">' + flags_html + '</ul>') if flags_html else ''}
    </article>"""


CSS = """
:root{--ink:#18202a;--mut:#5d6b7a;--bg:#f5f7fa;--card:#fff;--ok:#0a7d3b;--warn:#a15c00;--line:#dde3ea}
*{box-sizing:border-box}body{margin:0;font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header.top{background:#16324f;color:#fff;padding:14px 16px}header.top h1{margin:0;font-size:20px}header.top p{margin:4px 0 0;font-size:13px;opacity:.9}
nav{display:flex;flex-wrap:wrap;gap:8px;padding:10px 16px;background:#fff;border-bottom:1px solid var(--line)}
nav a{font-size:14px;padding:6px 10px;border-radius:999px;background:#eef3f8;color:#16324f;text-decoration:none}
main{padding:12px;max-width:1100px;margin:0 auto;display:grid;gap:12px;grid-template-columns:1fr}
@media(min-width:760px){main{grid-template-columns:1fr 1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}
.card header{padding:0;background:none;color:var(--ink)}.when{font-weight:700}.comp{font-size:13px;color:var(--mut)}
.team{display:flex;justify-content:space-between;padding:6px 0 2px;font-size:17px}.team.win span{font-weight:700}
.team b{font-variant-numeric:tabular-nums}.bar{height:8px;background:#e8edf3;border-radius:4px;overflow:hidden}
.bar i{display:block;height:100%;background:#2b6cb0}
.pick{margin:10px 0 4px;display:inline-block;padding:4px 10px;border-radius:8px;background:#e6f4ea;color:var(--ok);font-weight:600}
.pick.nopick{background:#f1f3f5;color:var(--mut)}
.meta{font-size:13px;color:var(--mut);margin-top:6px;word-break:break-word}.muted{color:var(--mut)}
.none{color:var(--mut)}.flags{font-size:12px;color:var(--warn);margin:8px 0 0;padding-left:18px}
section h2{font-size:18px;margin:18px 12px 0}footer{font-size:12px;color:var(--mut);padding:16px}
table{border-collapse:collapse;width:100%;background:#fff;font-size:14px}td,th{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
"""


def page(title, body, active):
    nav = "".join(
        f'<a href="{href}"{" aria-current=page" if key == active else ""}>{label}</a>'
        for key, href, label in [("slate", "index.html", "Open slate"), ("flags", "flagged.html", "Flagged for Review"),
                                 ("home", "../index.html", "Home")])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title>
<style>{CSS}</style></head><body>
<header class="top"><h1>{esc(title)}</h1><p>Hotspawn CS2 pick'em · open fixtures · probabilities from external prices and own ratings</p></header>
<nav>{nav}</nav>
{body}
<footer>Hotspawn crowd % is never used. External prices are de-vigged. Times are UTC (from the Hotspawn payload recorded in
data/08031d30). Generated by scripts/08031d30_build.py from data/08031d30/. Snapshot: 2026-10-14 ~01:41–02:00 UTC.</footer>
</body></html>"""


def main():
    rows = build_rows()
    rows.sort(key=lambda r: r["h"]["kickoff_utc"])
    # CSV of the page's data
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "open_slate.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["fixture_id", "kickoff_utc", "competition", "tier", "team_a", "team_b", "p_team_a_pct",
                    "p_team_b_pct", "pick", "pick_basis", "external_status", "external_source", "external_url",
                    "external_read_utc", "external_odds_a", "external_odds_b", "own_p_team_a_pct",
                    "own_p_team_b_pct", "own_basis", "flags", "hotspawn_lobby_url", "hotspawn_match_url"])
        for r in rows:
            h, e, o = r["h"], r["ext"], r["own"]
            w.writerow([h["fixture_id"], h["kickoff_utc"], h["competition"], h["tier"], h["team_a"], h["team_b"],
                        f"{r['pa']:.1f}" if r["pa"] is not None else "", f"{r['pb']:.1f}" if r["pb"] is not None else "",
                        r["pick"], r["basis"], e["status"] if e else "", e["source"] if e else "",
                        e["url"] if e else "", e["read"] if e else "",
                        f"{e['odds_a']:.3f}" if e else "", f"{e['odds_b']:.3f}" if e else "",
                        f"{o['p_a']:.1f}" if o else "", f"{o['p_b']:.1f}" if o else "", o["basis"] if o else "",
                        " | ".join(r["flags"]), h["hotspawn_lobby_url"], h["hotspawn_match_url"]])
    os.makedirs(OUT_DIR, exist_ok=True)
    days = {}
    for r in rows:
        days.setdefault(r["h"]["kickoff_utc"][:10], []).append(r)
    body = ['<section><h2>Open fixtures: %d (Hotspawn CS2 pick\'em, read 2026-10-14)</h2></section><main>' % len(rows)]
    body += [card(r) for r in rows]
    body.append("</main>")
    with open(os.path.join(OUT_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("Open CS2 slate: win probabilities & picks", "".join(body), "slate"))

    flagged = []
    with open(os.path.join(DATA, "hotspawn_open_cs2.csv"), encoding="utf-8") as f:
        for h in csv.DictReader(f):
            if h["on_live_hotspawn_list"] != "yes":
                note = h["note"].replace("EXCLUDED. ", "", 1)
                flagged.append((h["fixture_id"], f"{h['team_a']} v {h['team_b']}",
                                "EXCLUDED from the open list. " + note, h["hotspawn_lobby_url"]))
    for r in rows:
        for fl in r["flags"]:
            flagged.append((r["h"]["fixture_id"], f"{r['h']['team_a']} v {r['h']['team_b']}", fl,
                            r["h"]["hotspawn_lobby_url"]))
    rows_html = "".join(
        f"<tr><td>{esc(fid)}</td><td>{esc(m)}</td><td>{esc(fl)}</td>"
        f"<td><a href='{esc(u)}'>Hotspawn lobby</a></td></tr>" for fid, m, fl, u in flagged)
    extra = f"""<section><h2>Flagged for Review</h2><p class="meta" style="margin:8px 12px">Non-blocking. Items are
    published here for manual review; nothing in them is silently corrected. Excluded fixture rows are listed below.</p>
    <div style="padding:0 12px;overflow-x:auto"><table><tr><th>Fixture</th><th>Match</th><th>Flag</th><th>Source</th></tr>
    {rows_html}</table></div></section>"""
    with open(os.path.join(OUT_DIR, "flagged.html"), "w", encoding="utf-8") as f:
        f.write(page("Flagged for Review: open CS2 slate", extra, "flags"))
    print(f"open fixtures={len(rows)} flags={len(flagged)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
