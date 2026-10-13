#!/usr/bin/env python3
"""Originate OUR OWN match-win probabilities. NEVER uses Hotspawn pick %.
Inputs: ONLY the HLTV world ranks in data/ratings.csv (each row sourced there).
Model (documented, reproducible, rank-only):
  rating(team) = 2000 - 300 * log10(rank)
  P(A beats B) = 1 / (1 + 10 ** (-(rating_A - rating_B)/400))   (standard Elo logistic)
Fair decimal odds = 1 / P.  A bookmaker-style line adds a 5% overround:
  offered = fair / 1.05 per side, renormalised in output table notes.
If either rank is missing the probability is BLANK (unverified) - never inferred.
Run: python3 scripts/model.py  -> prints CSV rows for data/matches.csv columns own_p_*
"""
import csv, math, pathlib
r={}
for row in csv.DictReader(open(pathlib.Path(__file__).parent.parent/'data/ratings.csv')):
    if row['hltv_world_rank']: r[row['team'].lower()]=(int(row['hltv_world_rank']),row['team'])
def prob(a,b):
    if a.lower() not in r or b.lower() not in r: return ''
    ra=2000-300*math.log10(r[a.lower()][0]); rb=2000-300*math.log10(r[b.lower()][0])
    return round(100/(1+10**(-(ra-rb)/400)),1)
if __name__=='__main__':
    for row in csv.DictReader(open(pathlib.Path(__file__).parent.parent/'data/matches.csv')):
        print(row['id'], row['team_a'], 'vs', row['team_b'], '-> own P(A)% =', prob(row['team_a'],row['team_b']))
