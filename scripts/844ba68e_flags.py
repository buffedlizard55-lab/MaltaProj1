#!/usr/bin/env python3
"""Session 844ba68e: publish flags F-16..F-27 on the Flagged for Review page and link the own-lines page.

Idempotent: the inserted block is wrapped in marker comments and replaced on every run.
Only one nav link is added per page, and only if it is not already present.
"""
import html
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
START = "<!-- 844ba68e-flags:start -->"
END = "<!-- 844ba68e-flags:end -->"

FLAGS = [
    ("F-16", "main data/matches.json H-04 odds do not match Polymarket",
     "data/matches.json (main) lists 9z 3.45 / Aurora 1.37 for H-04 and calls it verified. The live Polymarket listing shows 9z 3.85 (26¢) / Aurora Gaming 1.33 (75¢), $28.95K volume, Tomorrow 4:30 AM. The same file gives '9z ranked #14', which is the VRS figure on the HLTV match page. World ranking is #17.",
     "H-04 (data/matches.json, data/matches.csv)",
     "https://polymarket.com/esports/cs2/thunderpick-world-championship/cs2-9z-aur1-2026-10-14"),
    ("F-17", "main data/matches.json prices H-12 with an LFO 10 line that does not exist",
     "matches.json gives FORZE Reload 1.05 vs LFO 10 1.27 for H-12. The only FORZE Reload match in the listing is FORZE Reload vs Sökerorg (1:00 PM, $0.00 volume). No LFO 10 price exists. H-12 is blank in this session's data.",
     "H-12",
     "https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14"),
    ("F-18", "main data/matches.json marks $0-volume Polymarket rows as verified",
     "Rows H-13 and H-16 to H-26 are marked 'verified' or 'partially_verified' but the listing shows $0.00 volume for each. H-16 BOJONG price (47¢) is missing from matches.json. H-19 is marked 'No external odds found', yet the listing shows WBT 87¢ / BOJONG 48¢ at $0.00 volume. These readings are recorded here and not used for picks.",
     "H-13, H-16 to H-26",
     "https://polymarket.com/esports/cs2/elisa-breakout"),
    ("F-19", "Correction: Envy is ranked on HLTV, not unranked",
     "The Flagged page entry F-06 in the earlier board lists Envy among teams without a verified top-41 rank. The HLTV world ranking of 2026-10-12 shows Envy at #20 (96 HLTV points). H-15 therefore has a rank-model line. That line favours Envy (57.5%), while Polymarket favours Heroic (66.4%), so H-15 has no pick.",
     "H-15 (earlier F-06 entry)",
     "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-20", "HLTV match pages show VRS, not world ranking",
     "HLTV match pages show VRS points and rank (for example 9z 1516 pts #14 and Aurora 1839 pts #5 on the 9z vs Aurora VRS panel). The world ranking page is different (9z #17, Aurora #6). Only the world ranking page is used for ranks in this session. Earlier entries from match pages (for example HOTU #42) are superseded by the 2026-10-12 world ranking (HOTU #41).",
     "ratings.csv, matches.json (rank fields)",
     "https://www.hltv.org/matches/2399384/9z-vs-aurora-thunderpick-world-championship-2026"),
    ("F-21", "Overtake, Zomblers and other rank claims on main are unverified",
     "matches.json says 'HLTV shows Overtake Sector ranked #161 vs Zomblers #224'. Neither team is in HLTV ranks 1–41 on the 2026-10-12 page, and no page checked here confirms #161 or #224. No rank is used for these teams. Sashi #90 (in the matches.json notes) is also unconfirmed.",
     "H-02, H-05",
     "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-22", "Polymarket display times agree with Hotspawn for all 26 fixtures",
     "In this session's listing, every Polymarket start time (Today / Tomorrow / Oct 15 / Oct 16 labels) matches the Hotspawn start time for the same team pair. The 6-hour difference that F-02 reports for eGamersWorld was not reproduced: the EGW match page for Astralis vs Sashi Esport shows 14.10.26 06:00, the same as Hotspawn. F-02 is left as written until someone confirms its source. Matching uses team pair, date and slug.",
     "All rows; EGW rows H-05",
     "https://egamersworld.com/counterstrike/match/EJZmJpBjeNx/astralis-vs-sashi-esport-aGet1AP-0Z"),
    ("F-23", "Name mappings between Hotspawn and market sites (inferred)",
     "Mapped by team pair, date and time, not by name: Polymarket 'Overtake' = Hotspawn 'Overtake Sector' (H-02); 'WBT' = 'WROTBERRY' (H-13, H-17, H-19, not stated on Polymarket); 'NIP' / 'Team Falcons' = 'Ninjas in Pyjamas' / 'Falcons' (H-08); 'Aurora Gaming' = 'Aurora' (H-04); 'Sashi Esport' = 'Sashi' (H-05); 'BetBoom Team' = 'BetBoom' (H-11); 'BC.Game Esports' = 'BC.Game' (H-14); 'Esport Academy Copenhagen' = 'EAC'.",
     "H-02, H-04, H-05, H-08, H-11, H-13, H-14, H-17, H-19",
     "https://polymarket.com/esports/cs2"),
    ("F-24", "Aggregator odds name no bookmaker",
     "EGamersWorld shows Astralis 1.07 / Sashi Esport 5.9 without naming the bookmakers (H-05). stavka.tv (a Russian-language tipster site) gives 9z 3.50 / Aurora 1.30 for H-04 and names no bookmaker. Both are used only as secondary, de-vigged inputs. Neither changes a pick on its own.",
     "H-04, H-05",
     "https://stavka.tv/matches/csgo/14-10-2026-9z-aurora-gaming"),
    ("F-25", "Low-liquidity or overround markets are not used for picks",
     "Polymarket volume below $1,000 is shown but not used: H-03 $220.44, H-07 $55.00, H-10 $55.78, H-18 $304.98, H-20 $3.08, and all $0.00 rows. H-13 (WBT vs EAC) has an overround of 115¢ and is also not used. The liquid rows that were used sum to 101¢ on both sides.",
     "H-03, H-07, H-10, H-13, H-16 to H-26",
     "https://polymarket.com/esports/cs2/elisa-breakout"),
    ("F-26", "Rank-only line is sensitive to rank gaps (H-14)",
     "BC.Game is #70 on the 2026-10-12 HLTV ranking (12 points), verified this session. The rank-only model gives MIBR 79.0%, against Polymarket 54.4%, so the consensus is 66.7% for MIBR. This is a large gap for a model that has no roster, form or map input. Treat H-14 with caution.",
     "H-14",
     "https://www.hltv.org/ranking/teams/2026/october/12"),
    ("F-27", "Coordination record: overlapping sessions and open PR",
     "PR #4 (arena/51fb12f8) was still open when this session started, and PR #9 (51fb12f8 integration) later replaced docs/index.html and docs/flagged.html. That replacement removed the static flag list F-01 to F-15 from the earlier board, and this session's nav link and F-16 to F-27 had to be re-applied on top. Several boards (3ee8c478, 79a1c6c8 C-04, 4f599d7c T04, 390c1f81 #9-10) claim overlapping integration or line work. Claims for this session are in COORDINATION.md on main.",
     "COORDINATION.md, docs/index.html, docs/flagged.html",
     "https://github.com/buffedlizard55-lab/MaltaProj1/pull/9"),
]


def block():
    rows = []
    for fid, issue, detail, affects, url in FLAGS:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "<td><a href=\"{}\" target=\"_blank\" rel=\"noopener\">source</a></td></tr>".format(
                fid, html.escape(issue), html.escape(detail), html.escape(affects), html.escape(url, quote=True)))
    return (START + "\n"
            "<section class=\"flags-844ba68e\" id=\"flags-844ba68e\">\n"
            "<h2>Session 844ba68e: additional flags (F-16 to F-27)</h2>\n"
            "<p>Checked against the live Polymarket CS2 listing, the HLTV world ranking of 2026-10-12, and the EGW and stavka.tv pages on 2026-10-13. "
            "These flags do not block publication. Own lines and picks: <a href=\"own-lines.html\">own-lines.html</a>.</p>\n"
            "<div style=\"overflow-x:auto\"><table><thead><tr><th>ID</th><th>Issue</th><th>Detail</th><th>Affects</th><th>Link</th></tr></thead>"
            "<tbody>" + "".join(rows) + "</tbody></table></div>\n"
            "</section>\n" + END + "\n")


def insert_block(path):
    s = open(path, encoding="utf-8").read()
    if START in s and END in s:
        pre, rest = s.split(START, 1)
        _, post = rest.split(END, 1)
        s = pre + block() + post.lstrip("\n")
    else:
        anchor = "<h2>Sources consulted</h2>"
        assert s.count(anchor) == 1, "anchor not unique in flagged.html"
        s = s.replace(anchor, block() + anchor)
    open(path, "w", encoding="utf-8").write(s)


def add_nav_link(path, before, link):
    s = open(path, encoding="utf-8").read()
    if "own-lines.html" in s:
        return
    assert s.count(before) >= 1, "nav anchor missing in " + path
    s = s.replace(before, link + before, 1)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    insert_block(os.path.join(DOCS, "flagged.html"))
    add_nav_link(os.path.join(DOCS, "flagged.html"),
                 '<a href="methodology.html">Methodology</a></nav>',
                 '<a href="own-lines.html">Own lines &amp; picks</a>')
    add_nav_link(os.path.join(DOCS, "index.html"),
                 '    <a href="methodology.html">Methodology</a>\n',
                 '    <a href="own-lines.html">Own lines &amp; picks</a>\n')
    print("flags", len(FLAGS), "inserted")
