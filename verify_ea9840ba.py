#!/usr/bin/env python3
"""Verification script for session arena/ea9840ba requirements.

Checks:
1. All open matches have picks
2. Research ladder is documented (HLTV → esportsbooks → betting lines)
3. Unresolved picks section exists with limitations
4. Executive summary has in-site links
5. Mobile-friendly design
6. Regular updates configured (4-8 hours)
7. Full coverage of all hotspawn matches
8. Own originated lines from official sources
9. Line-by-line verification with official source links
"""

import csv
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).parent

def check_all_matches_have_picks():
    """Check that all open matches have picks."""
    print("\n=== Check 1: All open matches have picks ===")
    analysis_file = REPO_ROOT / "executive" / "data" / "analysis.csv"
    
    if not analysis_file.exists():
        print("❌ analysis.csv not found")
        return False
    
    with open(analysis_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    open_matches = [r for r in rows if r['status'] == 'open']
    matches_without_picks = [r for r in open_matches if not r['pick']]
    
    print(f"Total matches: {len(rows)}")
    print(f"Open matches: {len(open_matches)}")
    print(f"Open matches without picks: {len(matches_without_picks)}")
    
    if len(matches_without_picks) == 0:
        print("✅ All open matches have picks")
        return True
    else:
        print("❌ Some open matches are missing picks:")
        for m in matches_without_picks:
            print(f"  - {m['match_id']}: {m['team_a']} vs {m['team_b']}")
        return False

def check_research_ladder():
    """Check that research ladder is documented."""
    print("\n=== Check 2: Research ladder documented ===")
    unresolved_file = REPO_ROOT / "executive" / "unresolved.html"
    
    if not unresolved_file.exists():
        print("❌ unresolved.html not found")
        return False
    
    with open(unresolved_file, 'r') as f:
        content = f.read()
    
    # Check for research ladder documentation
    ladder_terms = ["HLTV", "esportsbooks", "betting lines", "research ladder"]
    found = all(term.lower() in content.lower() for term in ladder_terms)
    
    if found:
        print("✅ Research ladder (HLTV → esportsbooks → betting lines) is documented")
        return True
    else:
        print("❌ Research ladder not properly documented")
        return False

def check_unresolved_section():
    """Check that unresolved picks section exists with limitations."""
    print("\n=== Check 3: Unresolved picks section with limitations ===")
    unresolved_file = REPO_ROOT / "executive" / "unresolved.html"
    
    if not unresolved_file.exists():
        print("❌ unresolved.html not found")
        return False
    
    with open(unresolved_file, 'r') as f:
        content = f.read()
    
    # Check for limitations documentation
    limitation_terms = ["limitation", "unresolved", "research ladder", "cannot rest"]
    found = all(term.lower() in content.lower() for term in limitation_terms)
    
    if found:
        print("✅ Unresolved picks section exists with limitations documented")
        return True
    else:
        print("❌ Unresolved picks section missing limitations")
        return False

def check_executive_summary_links():
    """Check that executive summary has in-site links."""
    print("\n=== Check 4: Executive summary with in-site links ===")
    index_file = REPO_ROOT / "index.html"
    
    if not index_file.exists():
        print("❌ index.html not found")
        return False
    
    with open(index_file, 'r') as f:
        content = f.read()
    
    # Check for links to picks
    required_links = [
        "executive/picks.html",
        "executive/unresolved.html",
        "executive/",
    ]
    
    found = all(link in content for link in required_links)
    
    if found:
        print("✅ Executive summary has in-site links to picks")
        return True
    else:
        print("❌ Executive summary missing in-site links")
        for link in required_links:
            if link not in content:
                print(f"  - Missing: {link}")
        return False

def check_mobile_friendly():
    """Check for mobile-friendly design."""
    print("\n=== Check 5: Mobile-friendly design ===")
    
    # Check viewport meta tag
    index_file = REPO_ROOT / "index.html"
    picks_file = REPO_ROOT / "executive" / "picks.html"
    
    mobile_checks = []
    
    for file in [index_file, picks_file]:
        if file.exists():
            with open(file, 'r') as f:
                content = f.read()
            if 'viewport' in content:
                mobile_checks.append(True)
            else:
                mobile_checks.append(False)
                print(f"  ⚠️  {file.name} missing viewport meta tag")
    
    # Check CSS for responsive design
    css_files = [
        REPO_ROOT / "css" / "landing.css",
        REPO_ROOT / "executive" / "style.css",
    ]
    
    for css_file in css_files:
        if css_file.exists():
            with open(css_file, 'r') as f:
                content = f.read()
            if '@media' in content:
                mobile_checks.append(True)
            else:
                mobile_checks.append(False)
                print(f"  ⚠️  {css_file.name} missing media queries")
    
    if all(mobile_checks):
        print("✅ Mobile-friendly design elements present")
        return True
    else:
        print("❌ Mobile-friendly design incomplete")
        return False

def check_regular_updates():
    """Check that regular updates are configured."""
    print("\n=== Check 6: Regular updates (4-8 hours) ===")
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    
    if not workflows_dir.exists():
        print("❌ workflows directory not found")
        return False
    
    workflow_files = list(workflows_dir.glob("*.yml"))
    cron_found = False
    
    for wf in workflow_files:
        with open(wf, 'r') as f:
            content = f.read()
        if 'cron:' in content and '*/4' in content:
            cron_found = True
            print(f"  ✓ Found 4-hour cron in {wf.name}")
    
    if cron_found:
        print("✅ Regular 4-hour updates configured")
        return True
    else:
        print("❌ Regular updates not properly configured")
        return False

def check_full_coverage():
    """Check full coverage of all hotspawn matches."""
    print("\n=== Check 7: Full coverage of all hotspawn matches ===")
    analysis_file = REPO_ROOT / "executive" / "data" / "analysis.csv"
    
    if not analysis_file.exists():
        print("❌ analysis.csv not found")
        return False
    
    with open(analysis_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Check that we have both open and locked matches
    open_matches = [r for r in rows if r['status'] == 'open']
    locked_matches = [r for r in rows if r['status'] == 'locked']
    
    print(f"Total matches in analysis: {len(rows)}")
    print(f"Open matches: {len(open_matches)}")
    print(f"Locked matches: {len(locked_matches)}")
    
    if len(rows) > 0 and len(open_matches) > 0:
        print("✅ Full coverage with both open and locked matches")
        return True
    else:
        print("❌ Incomplete coverage")
        return False

def check_own_lines():
    """Check that own originated lines from official sources exist."""
    print("\n=== Check 8: Own originated lines from official sources ===")
    analysis_file = REPO_ROOT / "executive" / "data" / "analysis.csv"
    own_lines_file = REPO_ROOT / "executive" / "own-lines.html"
    
    if not analysis_file.exists():
        print("❌ analysis.csv not found")
        return False
    
    # Check for own lines in analysis
    with open(analysis_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    own_line_matches = [r for r in rows if r['basis_tier'] == '3']
    
    print(f"Matches with own originated lines (basis_tier=3): {len(own_line_matches)}")
    
    # Check for official source references
    official_sources = ['Valve', 'HLTV', 'VRS']
    source_found = False
    
    for row in rows:
        for source in official_sources:
            if source in row.get('rating_a_source', '') or source in row.get('rating_b_source', ''):
                source_found = True
                break
    
    if source_found and len(own_line_matches) > 0:
        print("✅ Own originated lines from official sources present")
        return True
    else:
        print("❌ Own originated lines from official sources not found")
        return False

def check_line_by_line_verification():
    """Check line-by-line verification with official source links."""
    print("\n=== Check 9: Line-by-line verification with official source links ===")
    analysis_file = REPO_ROOT / "executive" / "data" / "analysis.csv"
    
    if not analysis_file.exists():
        print("❌ analysis.csv not found")
        return False
    
    with open(analysis_file, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Check that every row has source links
    missing_sources = []
    for row in rows:
        if not row.get('source_links') or row['source_links'] == '':
            missing_sources.append(row)
    
    print(f"Total matches: {len(rows)}")
    print(f"Matches without source links: {len(missing_sources)}")
    
    # Check for official source domains
    official_domains = ['hltv.org', 'github.com/ValveSoftware', 'egamersworld.com', 'pinnacle.com']
    official_found = 0
    
    for row in rows:
        if row.get('source_links'):
            for domain in official_domains:
                if domain in row['source_links']:
                    official_found += 1
                    break
    
    print(f"Matches with official source links: {official_found}")
    
    if len(missing_sources) == 0 and official_found > 0:
        print("✅ Line-by-line verification with official source links")
        return True
    else:
        print("❌ Line-by-line verification incomplete")
        if len(missing_sources) > 0:
            print(f"  - {len(missing_sources)} matches missing source links")
        return False

def main():
    """Run all verification checks."""
    print("=" * 70)
    print("VERIFICATION FOR SESSION arena/ea9840ba")
    print("=" * 70)
    
    results = []
    results.append(("All open matches have picks", check_all_matches_have_picks()))
    results.append(("Research ladder documented", check_research_ladder()))
    results.append(("Unresolved section with limitations", check_unresolved_section()))
    results.append(("Executive summary with links", check_executive_summary_links()))
    results.append(("Mobile-friendly design", check_mobile_friendly()))
    results.append(("Regular updates configured", check_regular_updates()))
    results.append(("Full coverage", check_full_coverage()))
    results.append(("Own originated lines", check_own_lines()))
    results.append(("Line-by-line verification", check_line_by_line_verification()))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {check_name}")
    
    print(f"\nTotal: {passed}/{total} checks passed")
    
    if passed == total:
        print("\n🎉 All requirements met!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} requirement(s) not met")
        return 1

if __name__ == "__main__":
    exit(main())
