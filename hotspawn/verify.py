#!/usr/bin/env python3
"""Reconcile every published row with captured source inputs; no network and no inferred facts.

The row audit is a reproducibility check, NOT a claim that future outcomes are verified. A new
capture must keep all fixtures, including unresolved rows; stale or conflicting evidence is flagged.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model
from common import DATA, read_json, write_json


def main() -> int:
    board = read_json(DATA / 'board.json', {})
    capture = read_json(DATA / 'capture.json', {})
    expected, _ = model.build_rows(model.load_inputs())
    original = {str(f['match_id']): f for f in capture.get('hotspawn', {}).get('fixtures', [])}
    actual = {str(r['match_id']): r for r in board.get('rows', [])}
    errors, audit = [], []
    if not original or set(original) != set(actual) or len(actual) != len(board.get('rows', [])):
        errors.append('Fixture inventory missing, duplicated, or not equal to the source capture')
    for row in expected:
        mid = str(row['match_id'])
        r, fx = actual.get(mid, {}), original[mid]
        failures = []
        for key in ('team_a', 'team_b', 'start_utc', 'lock_utc', 'competition', 'tier'):
            if r.get(key) != fx.get(key): failures.append(key + ' differs from Hotspawn')
        for key in ('p_a', 'p_b', 'own_p_a', 'own_p_b', 'pick', 'pick_p', 'rung', 'format', 'flags'):
            if r.get(key) != row.get(key): failures.append(key + ' cannot be reproduced')
        if r.get('pick') and not r.get('sources'): failures.append('missing source links')
        errors.extend(mid + ': ' + err for err in failures)
        audit.append({'match_id': mid, 'input_reconciliation': 'pass' if not failures else 'fail',
                      'source_url': fx.get('source_url'), 'source_read_utc': fx.get('read_utc'),
                      'probability_basis': r.get('basis'), 'sources': r.get('sources', []),
                      'flags': r.get('flags', []), 'errors': failures})
    write_json(DATA / 'row_audit.json', {'capture_reference_utc': board.get('meta', {}).get('reference_utc'),
               'description': 'Stored-input reconciliation, not outcome verification or a live external link crawl.',
               'rows': audit, 'errors': errors, 'status': 'failed' if errors else 'passed'})
    print(f'row audit: {len(audit)} / {len(original)} source fixtures; {len(errors)} errors')
    for error in errors: print(error)
    return 1 if errors else 0

if __name__ == '__main__':
    raise SystemExit(main())
