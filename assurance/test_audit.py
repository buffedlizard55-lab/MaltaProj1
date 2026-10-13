import copy
import base64
import os
from unittest.mock import patch, MagicMock
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import unittest
from urllib.parse import unquote, urlparse
import audit
import check_sources

HERE=Path(__file__).resolve().parent

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=[]; self.rows=[]; self.current=None
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag=='a' and 'href' in a:
            self.links.append(a['href'])
            if self.current is not None: self.current.append(a['href'])
        if tag in ('script','img') and 'src' in a: self.links.append(a['src'])
        if tag=='link' and 'href' in a: self.links.append(a['href'])
        if tag=='tr': self.current=[]
    def handle_endtag(self,tag):
        if tag=='tr': self.rows.append(self.current); self.current=None

class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((HERE/'observations.json').read_text()); cls.report=audit.build()
    def qualified(self):
        return copy.deepcopy(self.data['fixtures'][5])
    def test_qualified_primary_pairs(self):
        self.assertEqual([r['id'] for r in self.report['rows'] if r['probability_a'] is not None],['H-01','H-06','H-09','H-15'])
    def test_normalized_pair(self):
        a,b=audit.normalize_pair(47,54); self.assertAlmostEqual(a,47/101); self.assertAlmostEqual(a+b,1)
    def test_invalid_prices(self):
        for value in (0,-1,None,float('nan'),float('inf'),True):
            with self.subTest(value=value),self.assertRaises(ValueError): audit.normalize_pair(value,50)
    def test_no_fuzzy_aliases(self):
        r=self.qualified(); r['observed_team_a']='HOTU Academy'; self.assertTrue(audit.rejection_reasons(r))
    def test_unchecked_moneyline_rejected(self):
        r=self.qualified(); r['moneyline_direct_checked']=False; self.assertTrue(audit.rejection_reasons(r))
    def test_competition_unchecked_rejected(self):
        r=self.qualified(); r['market_competition_checked']=False; self.assertTrue(audit.rejection_reasons(r))
    def test_same_calendar_day_required(self):
        r=self.qualified(); r['market_date']='2026-10-15'; self.assertTrue(audit.rejection_reasons(r))
    def test_source_publisher_required(self):
        r=self.qualified(); r['market_url']='https://play.hotspawn.com/lobby'; self.assertTrue(audit.rejection_reasons(r))
    def test_zero_volume_rejected(self):
        r=self.qualified(); r['volume_display']='$0.00'; self.assertTrue(audit.rejection_reasons(r))
    def test_conflicting_quotes_rejected(self):
        r=self.qualified(); r['conflicting_decimal_pair']=[1.1,7.5]; self.assertTrue(audit.rejection_reasons(r))
    def test_anomalous_price_sum_rejected(self):
        r=self.qualified(); r['observed_cents_a']=97; self.assertTrue(audit.rejection_reasons(r))
    def test_outcome_order_mapping(self):
        r=self.qualified(); r['observed_team_a'],r['observed_team_b']=r['observed_team_b'],r['observed_team_a']
        r['observed_cents_a'],r['observed_cents_b']=r['observed_cents_b'],r['observed_cents_a']
        result=audit.analyze({'fixtures':[r]})[0]; self.assertAlmostEqual(result['probability_a'],47/101)
    def test_no_hotspawn_probability_input(self):
        original=audit.analyze(self.data)
        edited=copy.deepcopy(self.data)
        for r in edited['fixtures']: r['hotspawn_pick_a_pct_snapshot']=100; r['hotspawnTeam1PickPct']=100
        changed=audit.analyze(edited)
        self.assertEqual([r['probability_a'] for r in original],[r['probability_a'] for r in changed])
    def test_suppressed_values_blank(self):
        for r in self.report['rows']:
            if r['reasons']:
                for field in ('probability_a','probability_b','fair_decimal_a','fair_decimal_b','market_lean'): self.assertIsNone(r[field])
    def test_no_timezone_inference(self):
        self.assertTrue(all(r['start_utc'] is None and r['start_timezone'] is None for r in self.report['rows']))
    def test_source_checks_not_verification(self):
        r=check_sources.check('https://unapproved.example/'); self.assertFalse(r['numerical_verification']); self.assertEqual(r['status'],'unverified')
    def test_check_report_preserves_unicode_bytes(self):
        report={'checked_urls':1,'rows':[{'title':'Sökerorg vs Example'}]}
        response=MagicMock(); response.__enter__.return_value.read.return_value=b'{"html_url":"https://github.com/example"}'
        with patch.dict(os.environ,{'GITHUB_TOKEN':'test-only','GITHUB_REPOSITORY':'owner/repo','GITHUB_SHA':'abcdef'}), patch.object(check_sources.urllib.request,'urlopen',return_value=response) as send:
            check_sources.publish_check(report)
        payload=json.loads(send.call_args.args[0].data)
        encoded=payload['output']['text'].split('```text\n',1)[1].split('\n```',1)[0]
        self.assertTrue(encoded.isascii()); self.assertEqual(json.loads(base64.b64decode(encoded)),report)
    def test_unique_fixture_sources(self):
        ids=[r['id'] for r in self.report['rows']]; self.assertEqual(len(ids),len(set(ids)))
        for r in self.report['rows']: self.assertEqual(urlparse(r['fixture_url']).hostname,'www.hotspawn.com'); self.assertEqual(urlparse(r['market_url']).hostname,'polymarket.com')
    def test_source_link_in_every_data_row(self):
        for file in HERE.glob('*.html'):
            p=Links(); p.feed(file.read_text())
            for row in p.rows[1:]:
                self.assertTrue(any(urlparse(url).hostname in ('www.hotspawn.com','play.hotspawn.com','polymarket.com','www.bwin.com','www.hltv.org') for url in row), (file.name,row))
    def test_internal_links_and_anchors(self):
        for file in HERE.glob('*.html'):
            p=Links(); p.feed(file.read_text())
            for url in p.links:
                parts=urlparse(url)
                if parts.scheme or parts.netloc: continue
                dest=(file.parent/unquote(parts.path)).resolve() if parts.path else file
                self.assertTrue(dest.is_file(),(file.name,url))
                if parts.fragment and dest.suffix=='.html':
                    target=Links(); target.feed(dest.read_text()); self.assertIn(parts.fragment,target.ids,(file.name,url))
    def test_probabilities_and_lines_consistent(self):
        for r in self.report['rows']:
            if r['probability_a'] is not None:
                self.assertAlmostEqual(r['probability_a']+r['probability_b'],1)
                self.assertAlmostEqual(r['fair_decimal_a']*r['probability_a'],1)
                self.assertTrue(math.isfinite(r['fair_decimal_b']))
    def test_build_deterministic(self):
        first=(HERE/'report.json').read_bytes(); audit.build(); self.assertEqual(first,(HERE/'report.json').read_bytes())

if __name__=='__main__': unittest.main()
