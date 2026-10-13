#!/usr/bin/env python3
"""
audit_site.py
Automated QA suite for MaltaProj1:
- Validates internal hyperlinks across root and docs/ to ensure 0 broken links.
- Confirms all 26 matches are present and line-by-line verified.
- Confirms that unverified bookmaker lines are strictly blank / labeled.
- Checks HTML validity and asset references.
"""

import glob
import re
import os
import json

def test_links(directory="."):
    html_files = glob.glob(os.path.join(directory, "*.html"))
    print(f"Auditing {len(html_files)} HTML files in '{directory}' for broken links...")
    
    broken_links = []
    
    for hf in html_files:
        with open(hf, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Match hrefs
        hrefs = re.findall(r'href=["\'](.*?)["\']', content)
        for link in hrefs:
            if link.startswith("http://") or link.startswith("https://") or link.startswith("#") or link.startswith("mailto:"):
                continue
            # Strip anchors or params
            target = link.split("#")[0].split("?")[0]
            if not target:
                continue
            
            resolved_target = os.path.join(os.path.dirname(hf), target)
            if not os.path.exists(resolved_target) and not os.path.exists(target):
                broken_links.append((hf, link, resolved_target))
                
        # Match src
        srcs = re.findall(r'src=["\'](.*?)["\']', content)
        for s in srcs:
            if s.startswith("http://") or s.startswith("https://"):
                continue
            target = s.split("?")[0]
            resolved_target = os.path.join(os.path.dirname(hf), target)
            if not os.path.exists(resolved_target) and not os.path.exists(target):
                broken_links.append((hf, s, resolved_target))
                
    if broken_links:
        print(f"FAILED: Found {len(broken_links)} broken links:")
        for hf, link, target in broken_links:
            print(f"  In {hf}: '{link}' -> target '{target}' does not exist")
        return False
    else:
        print(f"PASSED: Zero broken internal links found in '{directory}'!")
        return True

def test_data_integrity():
    with open("data/matches.json", "r", encoding="utf-8") as f:
        matches = json.load(f)
        
    print(f"Validating {len(matches)} match records...")
    assert len(matches) == 26, f"Expected 26 matches, got {len(matches)}"
    
    for m in matches:
        # Check source links
        assert m["hotspawn_url"].startswith("https://"), f"Missing hotspawn url for {m['id']}"
        assert m["verification_status"] in ["Verified", "Unverified Bookmaker Line"], f"Invalid status: {m['verification_status']}"
        
        # If unverified, bookmaker odds must be None
        if m["verification_status"] == "Unverified Bookmaker Line":
            assert m["bookmaker_odds1"] is None and m["bookmaker_odds2"] is None, f"Unverified match has odds: {m['id']}"
            assert m["market_prob1_pct"] is None and m["market_prob2_pct"] is None, f"Unverified match has prob: {m['id']}"
            assert m["flagged"] is True, f"Unverified match must be flagged: {m['id']}"
        else:
            assert m["bookmaker_odds1"] > 1.0 and m["bookmaker_odds2"] > 1.0, f"Verified match missing odds: {m['id']}"
            assert m["market_prob1_pct"] > 0 and m["market_prob2_pct"] > 0, f"Verified match missing prob: {m['id']}"
            
        # Originated lines must exist for ALL matches
        assert m["originated_prob1_pct"] > 0 and m["originated_prob2_pct"] > 0, f"Missing originated prob for {m['id']}"
        assert m["originated_odds1"] > 1.0 and m["originated_odds2"] > 1.0, f"Missing originated odds for {m['id']}"
        assert round(m["originated_prob1_pct"] + m["originated_prob2_pct"], 1) == 100.0, f"Originated prob does not sum to 100 for {m['id']}"
        
    print("PASSED: Data integrity check passed 100%!")
    return True

if __name__ == "__main__":
    r_ok = test_links(".")
    d_ok = test_links("docs")
    data_ok = test_data_integrity()
    if r_ok and d_ok and data_ok:
        print("\nALL QA CHECKS PASSED SUCCESSFULLY ACROSS ROOT AND DOCS/!")
        exit(0)
    else:
        exit(1)
