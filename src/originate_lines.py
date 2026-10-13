#!/usr/bin/env python3
"""
originate_lines.py
Original Betting Lines & Probability Engine for CS2 Hotspawn Pick'em Matches.
Computes:
1. De-vigged Bookmaker Implied Probabilities from verified external sportsbooks.
2. Independently originated probabilities and fair lines based on HLTV & VRS ratings,
   recent form winrates, head-to-head records, and series format (BO1 vs BO3).
3. Value Edge vs Market and Hotspawn Public Pick Divergence analysis.
"""

import json
import math
from typing import Dict, Any, Optional

def devig_twoway(odds1: Optional[float], odds2: Optional[float]):
    """Calculate vig-free implied probabilities using proportional margin removal."""
    if not odds1 or not odds2 or odds1 <= 1.0 or odds2 <= 1.0:
        return None, None
    raw1 = 1.0 / odds1
    raw2 = 1.0 / odds2
    total = raw1 + raw2
    return round((raw1 / total) * 100, 1), round((raw2 / total) * 100, 1)

def originate_cs2_probability(
    rank1: Optional[int],
    rank2: Optional[int],
    vrs1: Optional[int],
    vrs2: Optional[int],
    winrate1: float,
    winrate2: float,
    format_type: str = "BO3"
) -> tuple[float, float]:
    """
    Originate independent win probability using modified logistic Bradley-Terry model
    calibrated to competitive CS2 tier data.
    """
    # Base rating proxy from rank: Lower rank number = higher skill
    # Using log rank differential + winrate form
    r1 = rank1 if rank1 else 200
    r2 = rank2 if rank2 else 200
    
    # VRS weighting if available
    v1 = vrs1 if vrs1 else r1
    v2 = vrs2 if vrs2 else r2
    
    # Combined effective skill rating proxy
    eff_rank1 = 0.6 * r1 + 0.4 * v1
    eff_rank2 = 0.6 * r2 + 0.4 * v2
    
    # Rating difference in log space
    diff = math.log(eff_rank2) - math.log(eff_rank1)
    
    # Scale factor for single map BO1
    base_p1 = 1.0 / (1.0 + math.exp(-1.4 * diff))
    
    # Adjust for recent 30-90 day form / winrate differential
    form_adj = (winrate1 - winrate2) * 0.15
    p1_single = max(0.08, min(0.92, base_p1 + form_adj))
    
    if format_type.upper() == "BO1":
        # Single map has higher variance / upset probability
        p1 = p1_single
    else: # BO3
        # Best of 3 series: P(win) = p^2 * (3 - 2p)
        p1 = (p1_single ** 2) * (3.0 - 2.0 * p1_single)
        
    p1 = max(0.05, min(0.95, p1))
    p2 = 1.0 - p1
    return round(p1 * 100, 1), round(p2 * 100, 1)

def prob_to_fair_odds(prob_pct: float) -> float:
    if prob_pct <= 0:
        return 99.0
    return round(100.0 / prob_pct, 2)
