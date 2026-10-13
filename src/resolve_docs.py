#!/usr/bin/env python3
"""resolve_docs.py"""
with open("flagged.html", "r", encoding="utf-8") as f:
    flagged_content = f.read()

# Append the deep dive cards from the earlier session into docs/flagged.html
extra_cards = """
    <div class="card-grid" style="margin-top: 2rem;">
      <div class="content-card">
        <h2>Match-Level Analysis &amp; Discrepancy Audits</h2>
        <div style="margin-bottom: 1rem; border-left: 3px solid var(--accent-amber); padding-left: 0.75rem;">
          <h4>MIBR vs BC.Game &bull; Public / Model Skew</h4>
          <p><strong>Tournament:</strong> Stake Pulse Beat III (Tier B)</p>
          <p><strong>Analysis:</strong> Hotspawn public picked BC.Game 68% vs MIBR 32%. In contrast, Polymarket and sportsbooks price MIBR as the favorite at 1.55 (58.9% implied win probability). MIBR recently defeated BC.Game 2-1 and holds a higher HLTV rank (#12 vs #47).</p>
        </div>
        <div style="margin-bottom: 1rem; border-left: 3px solid var(--accent-amber); padding-left: 0.75rem;">
          <h4>HOTU vs Fnatic &bull; Brand Legacy Skew</h4>
          <p><strong>Tournament:</strong> Stake Pulse Beat III (Tier B)</p>
          <p><strong>Analysis:</strong> 91% of Hotspawn players selected Fnatic due to historical brand cachet. Verified betting lines price this fixture as an exact 50/50 pick'em (1.82 / 1.82), while Valve Regional Standings favor HOTU (#34 vs #45).</p>
        </div>
        <div style="margin-bottom: 1rem; border-left: 3px solid var(--accent-amber); padding-left: 0.75rem;">
          <h4>ex-Keyd Stars vs Galorys &bull; Inverted Public Consensus</h4>
          <p><strong>Tournament:</strong> ESL Challenger League SA Cup #3 (Tier B)</p>
          <p><strong>Analysis:</strong> 86% of Hotspawn users chose ex-Keyd Stars, whereas sportsbooks and Polymarket price Galorys as heavy 67.1% favorites (1.40 odds). High value edge opportunity.</p>
        </div>
      </div>
    </div>
"""

# Insert before </main>
if "</main>" in flagged_content:
    combined_flagged = flagged_content.replace("</main>", extra_cards + "\n  </main>")
else:
    combined_flagged = flagged_content

with open("docs/flagged.html", "w", encoding="utf-8") as f:
    f.write(combined_flagged)

# For docs/index.html, use our rich master dashboard
with open("thunderpick.html", "r", encoding="utf-8") as f:
    pass # ensure file exists

# Generate docs/index.html from the index.html build logic (not the redirect)
import sys
sys.path.append("src")
from build_site import build_index, load_data
matches = load_data()

# Read what index was before redirect
# We can run build_index and write to docs/index.html
from build_site import render_header, render_table_rows, render_footer

def build_docs_index(matches):
    total_matches = len(matches)
    verified_books = sum(1 for m in matches if m["bookmaker_odds1"] is not None)
    flagged_count = sum(1 for m in matches if m["flagged"])
    tier_s_count = sum(1 for m in matches if "S" in m["tier"])

    rows = render_table_rows(matches)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hotspawn Reverse Engineering & Esports Lines Origination Hub | Dashboard</title>
  <link rel="stylesheet" href="css/styles.css">
</head>
<body>
  {render_header("dashboard", flagged_count)}

  <main>
    <div class="hero">
      <h1>Hotspawn Pick'Em Reverse Engineering &amp; Independent Betting Lines Hub</h1>
      <p>
        Real-time intelligence and quantitative analysis reverse-engineered from <a href="https://play.hotspawn.com/lobby" target="_blank" rel="noopener" class="source-link">play.hotspawn.com/lobby</a>.
        Matches are tracked across all active tournament circuits, featuring external bookmaker odds, vig-free implied win probabilities,
        independently originated statistical lines (HLTV/VRS rating + format models), and edge analysis highlighting severe public sentiment mispricings.
      </p>
    </div>

    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Matches Monitored</div>
        <div class="stat-value">{total_matches}</div>
        <div class="stat-sub">Across 5 competitive leagues</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Verified Bookmaker Lines</div>
        <div class="stat-value" style="color: var(--accent-green);">{verified_books}</div>
        <div class="stat-sub">From Bwin, EGW, Polymarket, Stake</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Originated Lines Built</div>
        <div class="stat-value" style="color: var(--accent-blue);">{total_matches}</div>
        <div class="stat-sub">Originated for 100% of matches</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Flagship Malta LAN (Tier S)</div>
        <div class="stat-value" style="color: var(--accent-purple);">{tier_s_count}</div>
        <div class="stat-sub">$1,000,000 Thunderpick World Championship</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Flagged for Review</div>
        <div class="stat-value" style="color: var(--accent-amber);">{flagged_count}</div>
        <div class="stat-sub">Unverified lines &amp; public skews</div>
      </div>
    </div>

    <div class="controls-card">
      <div style="display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center;">
        <input type="text" id="searchInput" class="search-input" placeholder="Search teams, tournament, ID...">
        <select id="categoryFilter" class="select-filter">
          <option value="all">All Tournaments</option>
          <option value="Thunderpick WC">Thunderpick WC 2026 (Malta)</option>
          <option value="Stake Pulse">Stake Pulse Beat III</option>
          <option value="CCT Europe">CCT Europe Series #11</option>
          <option value="Elisa BreakOut">Elisa BreakOut Series #2</option>
          <option value="ESL Challenger">ESL Challenger League (NA/SA)</option>
        </select>
        <select id="statusFilter" class="select-filter">
          <option value="all">All Verification Statuses</option>
          <option value="Verified">Verified Bookmaker Lines</option>
          <option value="Unverified Bookmaker Line">Unverified Bookmaker Lines</option>
        </select>
        <label style="font-size: 0.85rem; color: var(--text-muted); display: flex; align-items: center; gap: 0.35rem; cursor: pointer;">
          <input type="checkbox" id="flaggedToggle"> Show Flagged Only
        </label>
      </div>
      <div id="matchCounter" style="font-size: 0.85rem; color: var(--text-muted);">Showing 26 of 26 matches</div>
    </div>

    <div class="table-container">
      <table id="matchesTable">
        <thead>
          <tr>
            <th>ID &amp; Schedule</th>
            <th>Tournament &amp; Tier</th>
            <th>Matchup &amp; Format</th>
            <th>Hotspawn Community %</th>
            <th>Verified Bookmaker Odds</th>
            <th>Market Implied Win %</th>
            <th>Originated Win %</th>
            <th>Originated Fair Odds</th>
            <th>Model Edge vs Market</th>
            <th>Status &amp; Sources</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </div>

    <div class="card-grid">
      <div class="content-card">
        <h2>Reverse Engineering Hotspawn's Pick'Em Engine</h2>
        <p>
          Hotspawn's Pick'em lobby (<a href="https://play.hotspawn.com/lobby" target="_blank" rel="noopener" class="source-link">play.hotspawn.com/lobby</a>) operates as a crowd-sourced esports prediction game with weekly Steam Voucher prize pools ($400 1st place, $200 2nd, $100 3rd, $50 places 4-10).
        </p>
        <ul>
          <li><strong>Scoring Formula:</strong> Base Points (2-7 pts) &times; Tier Multiplier (Tier S = &times;3.0, Tier B = &times;1.5, Tier C = &times;1.0) &times; Streak Multiplier (&times;1.25).</li>
          <li><strong>Closing Rules:</strong> Picks lock precisely 5 minutes before scheduled match start time.</li>
          <li><strong>The Pick % Pitfall:</strong> Hotspawn displays the percentage of users choosing each team. Crucially, as requested, <em>Hotspawn pick percentages are NOT match probabilities</em>—they reflect public recreational sentiment, fandom, and brand recognition.</li>
        </ul>
      </div>

      <div class="content-card">
        <h2>Key Market Inversion &amp; Value Findings</h2>
        <p>
          Comparing true bookmaker betting lines and originated statistical models against Hotspawn picks reveals massive exploitation opportunities:
        </p>
        <ul>
          <li><strong>Fnatic vs HOTU (Stake Pulse III):</strong> Hotspawn users picked Fnatic 91% vs HOTU 9%. In contrast, international sportsbooks price this at 1.82 / 1.82 (a 50/50 dead heat), with HOTU holding a superior Valve Regional Standing (#34 vs #45). Picking HOTU offers massive leaderboard differentiation.</li>
          <li><strong>ex-Keyd Stars vs Galorys (ESL SA):</strong> 86% of Hotspawn players selected ex-Keyd Stars. However, sharp bookmaker markets and Polymarket favor Galorys heavily at 1.40 / 67.1% implied win probability!</li>
          <li><strong>BC.Game vs MIBR (Stake Pulse III):</strong> Hotspawn users skewed 68% onto BC.Game. Real-world betting markets and HLTV ratings favor MIBR at 1.55 (58.9% implied win probability).</li>
        </ul>
      </div>
    </div>
  </main>

  {render_footer()}
  <script src="js/dashboard.js"></script>
</body>
</html>
"""
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

build_docs_index(matches)
print("Resolved docs/flagged.html and docs/index.html successfully!")
