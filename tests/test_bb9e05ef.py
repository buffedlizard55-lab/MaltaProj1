"""Fail-closed source policy and row coverage regression tests; no network."""
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'executive'))
import evidence
import ownlines
spec = importlib.util.spec_from_file_location('bb_build', ROOT / 'executive/build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
collect_spec = importlib.util.spec_from_file_location('bb_collect', ROOT / 'executive/collect.py')
collect = importlib.util.module_from_spec(collect_spec)
collect_spec.loader.exec_module(collect)
NOW = datetime(2026, 10, 15, 9, tzinfo=timezone.utc)


def quote(**kwargs):
    return dict({'team_a': 'Alpha', 'team_b': 'Beta', 'odds_a': 1.5, 'odds_b': 2.8,
                 'market_type': 'match_winner', 'status': 'open',
                 'captured_utc': '2026-10-15T08:00:00Z', 'start_time': '2026-10-15T12:00:00Z',
                 'source_url': 'https://www.pinnacle.com/en/esports/', 'source_name': 'Pinnacle'}, **kwargs)


class EvidencePolicy(unittest.TestCase):
    def test_stale_missing_future_and_map_quotes_are_rejected(self):
        self.assertEqual(evidence.quote_rejection(quote(), NOW), '')
        for q in (quote(captured_utc=''), quote(captured_utc='2026-10-14T00:00:00Z'),
                  quote(captured_utc='2026-10-16T00:00:00Z'), quote(market_type='map_1'),
                  quote(status='closed'), quote(match_quality='alias')):
            self.assertTrue(evidence.quote_rejection(q, NOW), q)

    def test_nonfinite_or_one_sided_price_cannot_be_published(self):
        for value in (float('nan'), float('inf'), 1, 0, None):
            self.assertTrue(evidence.quote_rejection(quote(odds_a=value), NOW))

    def test_hotspawn_never_supplies_the_price(self):
        self.assertTrue(evidence.quote_rejection(quote(source_url='https://play.hotspawn.com/lobby'), NOW))

    def test_exact_eight_hour_cutoff(self):
        self.assertFalse(evidence.quote_rejection(quote(captured_utc='2026-10-15T01:00:00Z'), NOW))
        self.assertTrue(evidence.quote_rejection(quote(captured_utc='2026-10-15T00:59:59Z'), NOW))

    def test_equal_legitimate_prices_are_not_inferred_to_be_placeholders(self):
        fixture = {'team_a': 'Alpha', 'team_b': 'Beta', 'start_utc': '2026-10-15T12:00:00Z'}
        matched = build.assigned_quotes(fixture, [quote(odds_a=2, odds_b=2)])
        self.assertFalse(matched[0]['placeholder'])
        self.assertEqual(matched[0]['p_a'], .5)

    def test_price_orientation_and_wrong_kickoff(self):
        fixture = {'team_a': 'Beta', 'team_b': 'Alpha', 'start_utc': '2026-10-15T12:00:00Z'}
        matched = build.assigned_quotes(fixture, [quote()])
        self.assertAlmostEqual(matched[0]['p_a'], 1/2.8 / (1/1.5 + 1/2.8))
        self.assertEqual(build.assigned_quotes(fixture, [quote(start_time='2026-10-16T12:00:00Z')]), [])

    def test_full_slate_requires_both_surfaces_and_live_read(self):
        data = {'mode': 'live', 'fetched_utc': '2026-10-15T08:00:00Z', 'pages': [
            {'url': u, 'http_status': 200, 'fixture_count': 10} for u in
            ('https://play.hotspawn.com/lobby', 'https://play.hotspawn.com/cs2-pickems')]}
        self.assertTrue(evidence.slate_health(data, NOW)['current'])
        for mode in ('previous_capture', 'repo_capture'):
            self.assertFalse(evidence.slate_health({**data, 'mode': mode}, NOW)['current'])
        self.assertFalse(evidence.slate_health({**data, 'pages': data['pages'][:1]}, NOW)['current'])
        self.assertFalse(evidence.slate_health({**data, 'identity_conflicts': ['123']}, NOW)['current'])

    def test_invalid_transfer_state_is_a_recorded_failure(self):
        with patch.object(collect, 'http_get', return_value=(200, b'<script id="ng-state">oops</script>', 'https://play.hotspawn.com/lobby')):
            entry, rows, _, _ = collect.parse_hotspawn_page('https://play.hotspawn.com/lobby')
        self.assertEqual(rows, [])
        self.assertIn('FAILED', entry['result'])

    def test_future_and_old_ratings_are_not_current(self):
        self.assertTrue(evidence.rating_is_recent('2026-10-12', NOW))
        self.assertFalse(evidence.rating_is_recent('2026-09-01', NOW))
        self.assertFalse(evidence.rating_is_recent('2026-11-01', NOW))


class StrictOwnLines(unittest.TestCase):
    def row(self, rank_a='5', rank_b='20', fmt='BO3'):
        return {'match_id': '1', 'team_a': 'Alpha', 'team_b': 'Beta', '_build_now': NOW,
                'rating_a': {'hltv_rank': rank_a}, 'rating_b': {'hltv_rank': rank_b},
                'series_format': fmt, 'basis_tier': 0, 'flags': []}

    def run_line(self, row):
        ownlines.originate([row], {'ranking_date': '2026-10-12'}, [{'rank': 5}, {'rank': 20}], {})
        return row

    def test_missing_rank_is_not_a_floor_rank(self):
        r = self.run_line(self.row(rank_b=''))
        self.assertIsNone(r['own']['p_series'])
        self.assertEqual(r['basis_tier'], 0)
        self.assertIn('FL-RANK-MISSING', r['flags'])

    def test_unknown_format_is_not_bo1(self):
        r = self.run_line(self.row(fmt=''))
        self.assertIsNone(r['own']['p_series'])
        self.assertIsNone(r['own']['best_of'])

    def test_coinflip_has_no_fabricated_side(self):
        r = self.run_line(self.row(rank_a='5', rank_b='5'))
        self.assertEqual(r['pick'], '(no side — 50/50)')
        self.assertEqual(r['pick_prob_pct'], '')

    def test_source_values_generate_labelled_estimate(self):
        r = self.run_line(self.row())
        self.assertEqual(r['basis_tier'], 5)
        self.assertTrue(r['own']['sources'])
        self.assertGreater(float(r['prob_a_pct']), 50)

    def test_fit_respects_each_samples_series_transform(self):
        samples = [(dr, ownlines.series_probability(ownlines.logit_ratio(dr, 0, 80), bo), bo)
                   for dr, bo in ((10, 1), (20, 3), (30, 5), (-40, 3))]
        result = ownlines.calibrate_scale(samples)
        self.assertEqual(result['scale'], 80)
        self.assertLess(result['mae_pp'], .001)


class ResearchIdentity(unittest.TestCase):
    def test_format_requires_exact_teams_and_epoch(self):
        import research
        row = {'team_a': 'Alpha', 'team_b': 'Beta', 'start_utc': '2026-10-15T12:00:00Z'}
        epoch = str(int(datetime(2026, 10, 15, 12, tzinfo=timezone.utc).timestamp() * 1000))
        self.assertEqual(research.format_evidence('Best of 3 (Online)', ['Alpha', 'Beta'], epoch, row), (3, ''))
        for teams, kick, text in ((['Alpha', 'Other'], epoch, 'Best of 3'),
                                  (['Alpha', 'Beta'], None, 'Best of 3'),
                                  (['Alpha', 'Beta'], epoch, 'Format unknown')):
            fmt, reason = research.format_evidence(text, teams, kick, row)
            self.assertIsNone(fmt)
            self.assertTrue(reason)


class PublishedContract(unittest.TestCase):
    def test_row_audit_matches_full_captured_inventory(self):
        report = json.loads((ROOT / 'executive/data/row_verification.json').read_text())
        source = json.loads((ROOT / 'executive/data/hotspawn_pages.json').read_text())
        self.assertEqual(report['errors'], [])
        self.assertEqual({r['match_id'] for r in report['rows']}, {str(f['id']) for f in source['fixtures']})
        self.assertTrue(all(r['fixture_source'].startswith('https://') for r in report['rows']))

    def test_clock_and_unresolved_are_accessible(self):
        html = (ROOT / 'executive/picks.html').read_text()
        self.assertIn('data-source-time=', html)
        self.assertIn('data-lock=', html)
        self.assertIn('name="viewport"', html)
        unresolved = (ROOT / 'executive/unresolved.html').read_text()
        self.assertIn('No supported pick', unresolved)
        self.assertNotIn('Every open match has a pick.', unresolved)
        self.assertIn('min-height: 44px', (ROOT / 'executive/style.css').read_text())


if __name__ == '__main__':
    unittest.main()
