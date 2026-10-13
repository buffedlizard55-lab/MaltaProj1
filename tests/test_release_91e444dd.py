import importlib.util
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

spec = importlib.util.spec_from_file_location('release_audit', Path(__file__).resolve().parents[1]/'scripts/audit_91e444dd.py')
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
NOW = datetime(2026, 10, 13, 23, tzinfo=timezone.utc)

class ReleaseAssurance(unittest.TestCase):
    def sample(self):
        return {'meta': {'hotspawn_snapshot_utc': '2026-10-13T22:00:00Z'}, 'matches': [dict(match_id='1', sport='cs2', team_a='A', team_b='B', hotspawn_page='https://play.hotspawn.com/lobby', start_utc='2026-10-14T08:00:00Z', lock_utc='2026-10-14T07:54:00Z', market_p_a_pct=None, market_p_b_pct=None)]}
    def errors(self, data):
        return [i for i in audit.audit_snapshot(data, NOW)['issues'] if i['severity']=='error']
    def test_missing_odds_review_not_fake_probability(self):
        report = audit.audit_snapshot(self.sample(), NOW)
        self.assertEqual(report['counts']['market'], 0)
        self.assertFalse(report['live_source_verification'])
        self.assertFalse(self.errors(self.sample()))
    def test_stale_and_future(self):
        d=self.sample(); d['meta']['hotspawn_snapshot_utc']='2026-10-12T22:00:00Z'
        self.assertIn('RA91-STALE', [i['code'] for i in audit.audit_snapshot(d, NOW)['issues']])
        d['meta']['hotspawn_snapshot_utc']='2026-10-14T22:00:00Z'; self.assertTrue(self.errors(d))
    def test_duplicate(self):
        d=self.sample(); d['matches']*=2; self.assertTrue(self.errors(d))
    def test_untrusted_fixture_source(self):
        d=self.sample(); d['matches'][0]['hotspawn_page']='https://example.com'; self.assertTrue(self.errors(d))
    def test_reproduce_devig_and_reject_hotspawn_odds(self):
        d=self.sample(); r=d['matches'][0]; r.update(market_p_a_pct=60, market_p_b_pct=40,
             market_sources=[dict(url='https://www.pinnacle.com/en/esports', odds_a=1.6, odds_b=2.4, fetched_utc='2026-10-13T22:00:00Z')])
        self.assertFalse(self.errors(d))
        r['market_p_a_pct']=70; r['market_p_b_pct']=30; self.assertTrue(self.errors(d))
        r['market_sources'][0]['url']='https://play.hotspawn.com/lobby'; self.assertTrue(self.errors(d))
    def test_nan_is_not_probability(self):
        self.assertFalse(audit.probability_pair(float('nan'), 50))
        self.assertFalse(audit.probability_pair(True, 99))
    def test_script_text_is_not_a_dom_anchor(self):
        with TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'index.html').write_text('<a href="page.html#real">ok</a><a href="page.html#fake">bad</a>')
            (root/'page.html').write_text('<script>"<div id=\"fake\">"</script><div id="real">')
            result=audit.audit_links(root)
            self.assertEqual(len(result['errors']),1)
            self.assertEqual(result['errors'][0]['link'],'page.html#fake')
    def test_safe_urls(self):
        for url in ['javascript:alert(1)','https://user:pass@example.com','http://example.com',None]:
            self.assertFalse(audit.safe_url(url))
        self.assertTrue(audit.safe_url('https://github.com/ValveSoftware/counter-strike_regional_standings'))
