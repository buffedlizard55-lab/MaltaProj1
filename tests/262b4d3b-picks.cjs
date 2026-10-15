'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const api = require('../js/262b4d3b-picks.js');

const ROOT = path.resolve(__dirname, '..');
const NOW = Date.parse('2026-10-14T08:39:00Z');
const csvText = fs.readFileSync(path.join(ROOT, 'live/data/slate.csv'), 'utf8');
const rows = api.parseCSV(csvText);
const meta = JSON.parse(fs.readFileSync(path.join(ROOT, 'live/data/snapshot_meta.json'), 'utf8'));
const execData = JSON.parse(fs.readFileSync(path.join(ROOT, 'exec/data/picks.json'), 'utf8'));
const view = api.buildView(rows, meta, execData, NOW);
const liveById = new Map(rows.map(row => [String(row.match_id), row]));
const activeById = new Map(view.active.map(item => [String(item.row.match_id), item]));

// CSV parsing is quote-aware and rejects malformed or structurally inconsistent evidence.
assert.deepEqual(api.parseCSV('\uFEFFone,two\r\n"a,b","a""b"\r\n'), [{one: 'a,b', two: 'a"b'}]);
assert.throws(() => api.parseCSV('a,b\n"unclosed'));
assert.throws(() => api.parseCSV('a,a\n1,2'));
assert.throws(() => api.parseCSV('a,b\n1'));
assert.equal(api.parseTime('2026-10-14T07:58:35'), NaN);
assert.equal(api.safeURL('javascript:alert(1)'), null);
assert.equal(api.safeURL('http://example.com'), null);
assert.equal(api.officialVrsDate(liveById.get('1079622').vrs_url), '2026-10-05');
assert.equal(api.officialVrsDate('https://github.com/ValveSoftware.evil/counter-strike_regional_standings/blob/' + 'a'.repeat(40) + '/live/2026/standings_global_2026_10_05.md'), null);
assert.match(api.stableVrsURL(liveById.get('1079622')), /eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/);

// HLTV evidence must be on the real match host and identify both exact names in its slug.
assert.equal(api.validHltvMatch('https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11', 'FORZE Reload', 'LFO 10'), true);
assert.equal(api.validHltvMatch('https://www.hltv.org/matches/2399418/wbt-vs-eac-elisa-breakout-series-2', 'WROTBERRY', 'EAC'), false);
assert.equal(api.validHltvMatch('https://www.hltv.org/matches/2399425/havu-vs-rounds-elisa-breakout-series-2', 'HAVU', 'RoundsGG'), false);
assert.equal(api.validHltvMatch('https://hltv.org.evil.test/matches/2399301/forze-reload-vs-lfo-10', 'FORZE Reload', 'LFO 10'), false);

// Snapshot and current lock-time logic use only the 88-row live CSV + metadata.
assert.equal(view.totalFixtures, 88);
assert.equal(meta.fixtures, rows.length);
assert.equal(view.generatedUTC, '2026-10-14T07:58:35Z');
assert.equal(view.active.length, 25);
assert.equal(view.marketCount, 8);
assert.equal(view.modelCount, 10);
assert.equal(view.unresolvedCount, 7);
assert.equal(view.unknownTime, 0);
assert.equal(view.execFresh, true);
assert.equal(view.active.length, rows.filter(row => Date.parse(row.lock_utc) > NOW).length);
assert.equal(activeById.has('1080176'), false); // 9z–Aurora's 08:24Z lock has passed.
assert.deepEqual(rows.filter(row => Object.keys(row).some(key => /^crowd/i.test(key))), []);
assert.doesNotMatch(fs.readFileSync(path.join(ROOT, 'js/262b4d3b-picks.js'), 'utf8'), /live\/data\/snapshot\.json|crowd_pct|crowd_probability/i);

// Prediction-market quote is admitted only for the exact fixture, event, time and checked scope.
const sashi = activeById.get('1079438');
assert.equal(sashi.primary.kind, 'prediction-market');
assert.equal(sashi.primary.pick, 'Astralis');
assert.equal(sashi.primary.a, 84.5);
assert.equal(sashi.primary.b, 15.5);
assert.match(sashi.primary.label, /not de-vigged/);
assert.match(sashi.primary.sourceURL, /cs2-ast10-sashi-2026-10-14/);
const changedPM = {...liveById.get('1079438'), ext_observed_utc: '2026-10-14T08:39:00Z'};
assert.equal(api.marketAssessment(changedPM, NOW).valid, false);
assert.match(api.marketAssessment(changedPM, NOW).reason, /later quote/);
const mapQuotePM = {...liveById.get('1079438'), ext_p_a_pct: '76', ext_p_b_pct: '24', final_p_a_pct: '76', final_p_b_pct: '24'};
assert.equal(api.marketAssessment(mapQuotePM, NOW).valid, false);
assert.match(api.marketAssessment(mapQuotePM, NOW).reason, /later quote/);
const lfoPM = {...liveById.get('1079624'), ext_bookmaker: 'Polymarket prediction market',
  ext_p_a_pct: '77', ext_p_b_pct: '23', final_p_a_pct: '77', final_p_b_pct: '23',
  ext_url: 'https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14',
  ext_observed_utc: '2026-10-14T08:39:00Z', pick: 'FORZE Reload'};
assert.equal(api.marketAssessment(lfoPM, NOW).valid, false);
assert.match(api.marketAssessment(lfoPM, NOW).reason, /scope is not verified/);

// Direct-bookmaker probabilities are recalculated from the stored odds and source links.
const pinnacle = activeById.get('1079439');
assert.equal(pinnacle.primary.kind, 'market');
assert.match(pinnacle.primary.label, /Pinnacle.*de-vigged/);
assert.match(pinnacle.primary.details, /FL-12/);
assert.ok(pinnacle.flags.includes('FL-12'));
assert.equal(pinnacle.primary.pick, 'Fnatic');
assert.ok(Math.abs(pinnacle.primary.a + pinnacle.primary.b - 100) < 1e-8);
const badHost = {...liveById.get('1079439'), ext_url: 'https://pinnacle.com.evil.test/'};
assert.equal(api.marketAssessment(badHost, NOW).valid, false);
const staleLine = {...liveById.get('1079439'), ext_observed_utc: '2026-10-14T01:00:00Z'};
assert.equal(api.marketAssessment(staleLine, NOW).valid, false);
const badFavorite = {...liveById.get('1079439'), pick: 'HOTU'};
assert.equal(api.marketAssessment(badFavorite, NOW).valid, false);
const closeLine = {...liveById.get('1079439'), ext_odds_a: '1.97', ext_odds_b: '2.03',
  ext_p_a_pct: '50.75', ext_p_b_pct: '49.25', final_p_a_pct: '50.75', final_p_b_pct: '49.25', pick: 'No confident pick'};
const closeAssessment = api.marketAssessment(closeLine, NOW);
assert.equal(closeAssessment.valid, true);
assert.equal(closeAssessment.pick, null);
const egwLine = {...liveById.get('1079439'), ext_bookmaker: 'EGamersWorld (aggregated bookmaker prices)',
  ext_url: 'https://egamersworld.com/counterstrike/match/fixture-123/hotu-vs-fnatic',
  ext_odds_a: '2.060', ext_odds_b: '1.752'};
assert.equal(api.marketAssessment(egwLine, NOW).valid, true);
const egwWrongPair = {...egwLine, ext_url: 'https://egamersworld.com/counterstrike/match/fixture-123/hotu-vs-other-team'};
assert.equal(api.marketAssessment(egwWrongPair, NOW).valid, false);
const egwPlaceholder = {...egwLine, ext_odds_a: '1.800', ext_odds_b: '1.800',
  ext_p_a_pct: '50.0', ext_p_b_pct: '50.0', final_p_a_pct: '50.0', final_p_b_pct: '50.0', pick: 'No confident pick'};
assert.equal(api.marketAssessment(egwPlaceholder, NOW).valid, false);
assert.match(api.marketAssessment(egwPlaceholder, NOW).reason, /placeholder/);

// Own estimates are recalculated from two official Valve points and an exact same-row HLTV BO.
const rustec = activeById.get('1079622');
assert.equal(rustec.primary.kind, 'model');
assert.equal(rustec.primary.pick, 'ex-RUSTEC');
assert.equal(rustec.primary.format.bestOf, 3);
assert.match(rustec.primary.details, /uncalibrated/i);
assert.match(rustec.primary.sourceURL, /github.com\/ValveSoftware\/counter-strike_regional_standings\/blob\/eec4853/);
assert.ok(Math.abs(rustec.primary.a + rustec.primary.b - 100) < 1e-8);
const mapP = 1 / (1 + 10 ** ((932 - 1066) / 400));
assert.ok(Math.abs(rustec.primary.a - 100 * mapP * mapP * (3 - 2 * mapP)) < 1e-8);
assert.equal(activeById.get('1080279').primary, null); // WROTBERRY is not guessed to equal HLTV's WBT.
assert.equal(activeById.get('1079624').primary, null); // LFO 10 has no two-sided official rating.
assert.ok(activeById.get('1080279').flags.some(flag => /identity is unverified/.test(flag)));

// Every displayed probability has a source, a complementary pair and a consistent pick.
for (const item of view.active) {
  const hotspawn = api.safeURL(item.row.hotspawn_url);
  assert.ok(hotspawn && /(^|\.)hotspawn\.com$/.test(hotspawn.hostname));
  if (!item.primary) continue;
  const line = item.primary;
  assert.ok(api.probabilityPair(line.a, line.b, 1e-8), item.row.match_id);
  if (line.pick) assert.equal(line.pick, line.a > line.b ? item.row.team_a : item.row.team_b, item.row.match_id);
  assert.ok(api.safeURL(line.sourceURL), item.row.match_id);
  if (line.kind === 'model') {
    assert.equal(api.validHltvMatch(line.formatURL, item.row.team_a, item.row.team_b), true, item.row.match_id);
    assert.ok(api.safeURL(line.formatURL));
  }
}

// Stale captures, stale format joins, duplicate IDs and corrupted counts fail closed.
const staleView = api.buildView(rows, {...meta, generated_utc: '2026-10-14T01:00:00Z'}, execData, NOW);
assert.equal(staleView.snapshotFresh, false);
assert.equal(staleView.marketCount, 0);
assert.equal(staleView.modelCount, 0);
assert.equal(staleView.unresolvedCount, 25);
const oldExec = {...execData, generated_utc: '2026-10-14T01:00:00Z'};
const noFormatView = api.buildView(rows, meta, oldExec, NOW);
assert.equal(noFormatView.marketCount, 8);
assert.equal(noFormatView.modelCount, 0);
const badJoin = JSON.parse(JSON.stringify(execData));
const rustecExec = badJoin.open.find(record => record.fixture_id === '1079622');
rustecExec.team_b = 'unrelated team';
const badJoinView = api.buildView(rows, meta, badJoin, NOW);
assert.equal(activeById.get('1079622').primary.kind, 'model');
assert.equal(badJoinView.active.find(item => item.row.match_id === '1079622').primary, null);
assert.throws(() => api.buildView(rows, {...meta, fixtures: 87}, execData, NOW), /count does not match/);
assert.throws(() => api.buildView([...rows, rows[0]], {...meta, fixtures: 89}, execData, NOW), /missing\/duplicate ID/);

console.log('262b4d3b evidence checks passed: fresh live inventory, strict lock filtering, scoped prices, exact format/rating joins, transparent VRS math, unresolved blanks, and fail-closed freshness.');
