'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {assess, snapshot, safeURL, fresh} = require('../js/landing.js');
const now = Date.parse('2026-10-14T04:00:00Z');
const capture = '2026-10-14T03:26:31Z';
const row = {match_id:'1', team_a:'A', team_b:'B', lock_utc:'2026-10-15T10:00:00Z', basis_tier:1, market_source:'Pinnacle', market_captured_utc:capture, market_odds_a:'2', market_odds_b:'3', basis_sources:[['https://www.pinnacle.com/en/esports/','Book']]};
assert.equal(assess(row,capture,now).pick,'A');
assert.ok(Math.abs(assess(row,capture,now).a-60)<1e-10);
assert.ok(Math.abs(assess(row,capture,now).b-40)<1e-10);
for(const patch of [{basis_tier:2},{basis_tier:3},{basis_tier:4},{market_odds_a:''},{market_odds_a:1},{market_odds_a:'Infinity'},{market_odds_a:true},{market_source:'Aggregator Pinnacle report',basis_tier:2},{market_captured_utc:'2026-10-13T01:00:00Z'},{market_captured_utc:'2026-10-15T01:00:00Z'},{basis_sources:[]},{basis_sources:[['https://pinnacle.com.evil.test','Spoof']]},{lock_utc:'unknown'},{lock_utc:'2026-10-14T04:00:00Z'},{team_b:'A'}]) {
 assert.equal(assess({...row,...patch},capture,now).pick,null,JSON.stringify(patch));
}
assert.equal(assess(row,'2026-10-13T01:00:00Z',now).pick,null);
assert.equal(assess(row,'2026-10-15T01:00:00Z',now).pick,null);
assert.equal(assess({...row,market_odds_b:2},capture,now).pick,null);
assert.equal(safeURL('javascript:alert(1)'),null);
assert.equal(safeURL('http://example.com'),null);
assert.equal(fresh('2026-10-14T03:00:00',now),false);
assert.throws(()=>snapshot({fixtures:[]},now));
const data=JSON.parse(fs.readFileSync('executive/data/analysis.json','utf8'));
const view=snapshot(data,now);
assert.equal(view.rows.length,Object.values(data.fixtures).filter(r=>!Number.isFinite(Date.parse(r.lock_utc))||Date.parse(r.lock_utc)>now).length);
assert.ok(view.active<=view.rows.length);
for(const {row:r,status:s} of view.rows) {
 assert.ok(r.hotspawn_pickem_url.startsWith('https://play.hotspawn.com/'));
 if(s.pick) { assert.ok(Math.abs(s.a+s.b-100)<1e-8); assert.equal(s.pick,s.a>s.b?r.team_a:r.team_b); }
 else {assert.equal(s.a,null);assert.equal(s.b,null);}
}
assert.equal(snapshot(data,Date.parse('2026-10-20T00:00:00Z')).rows.length,0);
assert.equal(snapshot(data,Date.parse('2026-10-14T10:00:00Z')).active,0);
console.log('Landing evidence checks passed: freshness, lock, source, odds, fallback, URL safety, every current row.');
