#!/usr/bin/env python3
"""Rebuild data/matches.csv = fixtures x market lines x our own rank model.

NEVER uses Hotspawn pick % as a probability input (display-only column).

Inputs (all sourced, see file headers):
  data/fixtures.csv  - the 26 verified Pick'em fixtures (Hotspawn + HLTV/EGW cross-refs)
  data/lines.csv     - external bookmaker lines (EGamersWorld aggregated bookmaker odds)
  data/ratings.csv   - HLTV world ranks, each row sourced

Market model: implied p = 1/odds; overround removed proportionally (de-vig):
  p_A = (1/odds_a) / (1/odds_a + 1/odds_b)
Own model (rank-only, reproducible):
  rating(team) = 2000 - 300 * log10(HLTV world rank)
  P(A) = 1 / (1 + 10 ** (-(rating_A - rating_B)/400))
  Blank if either rank is unverified - never inferred.

Pick rule (documented):
  - market de-vig favorite wins the pick;
  - if the two de-vig probabilities are within 2.0 pts -> "No confident pick";
  - if no verified market line AND no verified pair of ranks -> "No pick (no verified line)";
  - if no market line but both ranks verified -> pick the own-model favorite, labelled MODEL-PICK.

Divergence flag: |market_p - model_p| >= 12.5 pts on the market favorite (both present).
Run: python3 scripts/model.py   (writes data/matches.csv)
"""
import csv, math, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
D = ROOT / 'data'

ratings = {}
for row in csv.DictReader(open(D / 'ratings.csv')):
    if row['hltv_world_rank']:
        ratings[row['team'].strip().lower()] = int(row['hltv_world_rank'])

ALIAS = {  # fixture display name (lowercase) -> ratings.csv key (lowercase)
    'wrotberry': 'wbt',
    'roundsgg': 'rounds',
    'ninjas in pyjamas': 'nip',
    'betboom': 'betboom',
    'sashi': 'sashi',
    'envy': 'envy',
    'phantom esports': 'phantom',
    'the last resort': 'the last resort',
    'ea copenhagen': 'eac',
    'esport academy copenhagen': 'eac',
    'sashi esport': 'sashi',
    'bc.game': 'bc.game',
    'bc.game esports': 'bc.game',
    'bcgame': 'bc.game',
}

def rank_of(name):
    n = name.strip().lower()
    if n in ratings:
        return ratings[n]
    if n in ALIAS and ALIAS[n] in ratings:
        return ratings[ALIAS[n]]
    return None

def own_prob(a, b):
    ra, rb = rank_of(a), rank_of(b)
    if not ra or not rb:
        return ''
    Ra = 2000 - 300 * math.log10(ra)
    Rb = 2000 - 300 * math.log10(rb)
    return round(100 / (1 + 10 ** (-(Ra - Rb) / 400)), 1)

def devig(oa, ob):
    ia, ib = 1 / oa, 1 / ob
    s = ia + ib
    return round(100 * ia / s, 1), round(100 * ib / s, 1), round(100 * s - 100, 1)

lines = {r['id']: r for r in csv.DictReader(open(D / 'lines.csv')) if r['scope'] == 'match'}

rows = []
for f in csv.DictReader(open(D / 'fixtures.csv')):
    lid = f['id']
    ln = lines.get(lid, {})
    oa = (ln.get('odds_a') or '').strip()
    ob = (ln.get('odds_b') or '').strip()
    pa = pb = vig = ''
    if oa and ob:
        pa, pb, vig = devig(float(oa), float(ob))
    mp = own_prob(f['team_a'], f['team_b'])
    mb = round(100 - mp, 1) if mp != '' else ''

    # Pick
    if pa != '':
        if abs(pa - pb) <= 2.0:
            pick, pick_p = 'No confident pick (line ~even)', max(pa, pb)
        else:
            fav_a = pa > pb
            pick = f['team_a'] if fav_a else f['team_b']
            pick_p = pa if fav_a else pb
    elif mp != '':
        fav_a = mp >= 50
        pick = ('MODEL-PICK ' + f['team_a']) if fav_a else ('MODEL-PICK ' + f['team_b'])
        pick_p = max(mp, mb)
    else:
        pick, pick_p = 'No pick (no verified line)', ''

    # Divergence note
    div = ''
    if pa != '' and mp != '':
        fav_a = pa > pb
        mkt = pa if fav_a else pb
        mdl = mp if fav_a else mb
        if abs(mkt - mdl) >= 12.5:
            div = f'model vs market divergence: market {mkt}% vs model {mdl}% on {pick}'

    rows.append({
        'id': lid,
        'start_display': f['start_display'],
        'tournament': f['tournament'],
        'tier': f['tier'],
        'format': f['format'],
        'points': f['points'],
        'team_a': f['team_a'],
        'team_b': f['team_b'],
        'odds_a': oa,
        'odds_b': ob,
        'market_p_a_pct': pa,
        'market_p_b_pct': pb,
        'overround_pct': vig,
        'own_model_p_a_pct': mp,
        'own_model_p_b_pct': mb,
        'pick': pick,
        'pick_win_p_pct': pick_p,
        'divergence_note': div,
        'odds_source': 'EGamersWorld (aggregated bookmaker odds)' if (oa and ob) else 'none verified',
        'odds_source_url': (ln.get('source_url') or '') if (oa and ob) else '',
        'odds_snapshot_utc': (ln.get('snapshot_utc') or '') if (oa and ob) else '',
        'hotspawn_url': f['hotspawn_url'],
        'crossref_url': f['crossref_url'],
        'crossref_source': f['crossref_source'],
        'hotspawn_pick_a_pct_snapshot': '',
        'verification': 'fixture verified (Hotspawn + %s)' % f['crossref_source'] if (oa or mp != '') else 'fixture verified; line & probabilities blank - flagged',
    })

# Attach the 18:10 UTC crowd snapshot for display only (never an input).
CROWD = {
 'H-01': 86,'H-02': 11,'H-03': 10,'H-04': 5,'H-05': 95,'H-06': 9,'H-07': 89,'H-08': 89,
 'H-09': 83,'H-10': 100,'H-11': 89,'H-12': 89,'H-13': 73,'H-14': 30,'H-15': 90,'H-16': 94,
 'H-17': 29,'H-18': 93,'H-19': 87,'H-20': 27,'H-21': 27,'H-22': 93,'H-23': 64,'H-24': 93,
 'H-25': 0,'H-26': 100,
}
for r in rows:
    r['hotspawn_pick_a_pct_snapshot'] = CROWD.get(r['id'], '')

out = D / 'matches.csv'
with open(out, 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

# Console summary for verification
def s(v):
    return str(v) if v != '' else '-'
for r in rows:
    print(f"{r['id']:5s} {r['team_a']:>14s} vs {r['team_b']:<18s} odds {s(r['odds_a']):>6s}/{s(r['odds_b']):<6s} mkt {s(r['market_p_a_pct']):>5s}/{s(r['market_p_b_pct']):<5s} mdl {s(r['own_model_p_a_pct']):>5s}/{s(r['own_model_p_b_pct']):<5s} pick: {r['pick']} ({s(r['pick_win_p_pct'])})")
print(f"\n{len(rows)} rows -> {out}")
