/* Read-only view of published evidence. No Hotspawn crowd fields are consumed. */
(function () {
  'use strict';
  const SIX_HOURS = 6 * 60 * 60 * 1000;
  function time(value) {
    return typeof value === 'string' && /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? Date.parse(value) : NaN;
  }
  function fresh(value, now) {
    const age = now - time(value);
    return Number.isFinite(age) && age >= 0 && age <= SIX_HOURS;
  }
  function number(value) {
    return value === '' || value == null || typeof value === 'boolean' ? NaN : Number(value);
  }
  function safeURL(value) {
    try { const url = new URL(value); return url.protocol === 'https:' ? url.href : null; }
    catch (_) { return null; }
  }
  function parseCSV(text) {
    const rows = []; let row = [], field = '', quoted = false;
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      if (c === '"') {
        if (quoted && text[i + 1] === '"') { field += '"'; i++; }
        else quoted = !quoted;
      } else if (c === ',' && !quoted) { row.push(field); field = ''; }
      else if (c === '\n' && !quoted) { row.push(field.replace(/\r$/, '')); rows.push(row); row = []; field = ''; }
      else field += c;
    }
    if (field || row.length) { row.push(field.replace(/\r$/, '')); rows.push(row); }
    if (quoted) throw new Error('Incomplete CSV evidence');
    const headings = rows.shift() || [];
    return rows.filter(r => r.length === headings.length).map(r => Object.fromEntries(headings.map((h, i) => [h, r[i]])));
  }
  const norm = value => String(value || '').trim().toLowerCase();
  function parseStandings(markdown) {
    const points = {};
    for (const line of markdown.split('\n')) {
      const fields = line.split('|').map(s => s.trim());
      if (fields.length > 4 && /^\d+$/.test(fields[1]) && /^\d+$/.test(fields[2])) {
        const key = norm(fields[3]);
        // A repeated team label is ambiguous, not an excuse to choose a roster silently.
        points[key] = Object.prototype.hasOwnProperty.call(points, key) ? null : Number(fields[2]);
      }
    }
    return points;
  }
  function model(row, evidence, now, officialRatings) {
    const records = Array.isArray(evidence) ? evidence : [];
    const confirmed = records.filter(r => r.verdict === 'match' && fresh(r.checked_utc, now));
    const format = confirmed.find(r => r.kind === 'hltv_match' && String(r.fixture_id) === String(row.match_id) &&
      norm(r.team_a) === norm(row.team_a) && norm(r.team_b) === norm(row.team_b) &&
      /^https:\/\/(?:www\.)?hltv\.org\/matches\//.test(r.url) && /^(?:BO|Best of )[135]$/.test(r.claimed));
    if (!format) return null;
    const ratings = [row.rating_a, row.rating_b];
    for (let i = 0; i < ratings.length; i++) {
      const rating = ratings[i], team = i === 0 ? row.team_a : row.team_b;
      if (!rating || rating.match_method !== 'exact' || norm(rating.vrs_name) !== norm(team) || !Number.isFinite(number(rating.vrs_points))) return null;
      const official = /^https:\/\/(?:github\.com|raw\.githubusercontent\.com)\/ValveSoftware\/counter-strike_regional_standings\//;
      if (!official.test(rating.vrs_url || '')) return null;
      const date = /standings_global_(\d{4})_(\d{2})_(\d{2})/.exec(rating.vrs_url);
      if (!date) return null;
      const age = now - Date.parse(`${date[1]}-${date[2]}-${date[3]}T00:00:00Z`);
      if (age < 0 || age > 14 * 24 * 3600000) return null;
      const points = (officialRatings || {})[rating.vrs_url];
      if (!points || points[norm(team)] !== number(rating.vrs_points)) return null;
    }
    const bestOf = Number(format.claimed.match(/[135]$/)[0]);
    const p = 1 / (1 + 10 ** ((number(ratings[1].vrs_points) - number(ratings[0].vrs_points)) / 400));
    // Project-assumed 400-point logistic scale, independent maps; not Valve's official forecast.
    const a = 100 * (bestOf === 1 ? p : bestOf === 3 ? p * p * (3 - 2 * p) : p ** 3 * (10 - 15 * p + 6 * p * p));
    if (!Number.isFinite(a) || Math.abs(a - 50) < 0.01) return null;
    return {pick: a > 50 ? row.team_a : row.team_b, a, b: 100 - a, provisional: true,
      reason: 'Provisional model · official inputs, not bookmaker odds', formatURL: format.url, bestOf};
  }
  function assess(row, capture, now) {
    const result = {pick: null, a: null, b: null, reason: 'No confirmed primary line — research required'};
    if (!Number.isFinite(time(row.lock_utc))) { result.reason = 'Lock time unverified'; return result; }
    if (time(row.lock_utc) <= now) { result.reason = 'Locked — no active pick'; return result; }
    if (!fresh(capture, now)) { result.reason = 'Snapshot stale or time unverified'; return result; }
    if (Number(row.basis_tier) !== 1) {
      result.reason = Number(row.basis_tier) === 2 ? 'Secondary price not confirmed with bookmaker' :
        Number(row.basis_tier) === 4 ? 'Unlisted-team assumption — no verified estimate' :
          'Model research only — series / calibration require review';
      return result;
    }
    if (!/pinnacle/i.test(row.market_source || '') || !fresh(row.market_captured_utc, now)) {
      result.reason = 'Primary quote stale or source unverified'; return result;
    }
    const oa = number(row.market_odds_a), ob = number(row.market_odds_b);
    if (!Number.isFinite(oa) || !Number.isFinite(ob) || oa <= 1 || ob <= 1) {
      result.reason = 'Invalid or missing two-sided odds'; return result;
    }
    const a = 100 * (1 / oa) / (1 / oa + 1 / ob), b = 100 - a;
    const sources = Array.isArray(row.basis_sources) ? row.basis_sources : [];
    if (!sources.some(s => { const url = safeURL(s[0]); return url && /(^|\.)pinnacle\.com$/.test(new URL(url).hostname); })) {
      result.reason = 'Primary source link missing'; return result;
    }
    if (!row.team_a || !row.team_b || row.team_a === row.team_b || Math.abs(a - b) < 0.01) {
      result.reason = 'Unresolved teams or tied line'; return result;
    }
    // A display is recalculated from archived odds, never from an upstream predicted percentage.
    return {pick: a > b ? row.team_a : row.team_b, a, b, reason: 'Primary market · margin removed'};
  }
  function snapshot(data, now, evidence, officialRatings) {
    if (!data || !data.fixtures || Array.isArray(data.fixtures) || typeof data.fixtures !== 'object') throw new Error('Invalid fixture evidence');
    const rows = Object.values(data.fixtures);
    if (!rows.length || rows.some(r => !r || !r.match_id || !r.team_a || !r.team_b)) throw new Error('Incomplete fixture evidence');
    const capture = data.capture_utc;
    // Unknown lock times are retained for review rather than silently excluded.
    const visible = rows.filter(r => !Number.isFinite(time(r.lock_utc)) || time(r.lock_utc) > now)
      .sort((a, b) => (time(a.start_utc) || Infinity) - (time(b.start_utc) || Infinity))
      .map(row => {
        let status = assess(row, capture, now);
        // Additional research is consulted only when the primary market route did not resolve the match.
        if (!status.pick && fresh(capture, now) && time(row.lock_utc) > now) status = model(row, evidence, now, officialRatings) || status;
        return {row, status};
      });
    return {capture, fresh: fresh(capture, now), rows: visible, active: visible.filter(r => r.status.pick && !r.status.provisional).length};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {time, fresh, safeURL, assess, snapshot, parseCSV, parseStandings, model};
  if (typeof document === 'undefined') return;
  function el(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function link(url, text) {
    const node = el('a', text), safe = safeURL(url);
    if (safe) { node.href = safe; node.rel = 'noopener noreferrer'; }
    return node;
  }
  let latest; let evidence = []; const officialRatings = {};
  const list = document.getElementById('match-list'), search = document.getElementById('match-search');
  function render() {
    if (!latest) return;
    const view = snapshot(latest, Date.now(), evidence, officialRatings);
    document.getElementById('freshness').textContent = `${view.fresh ? 'Published observation' : 'STALE / REVIEW'} · Hotspawn capture ${view.capture || 'unverified'}. Source timestamps are checked separately; these are not live odds.`;
    document.getElementById('open-count').textContent = view.rows.length;
    document.getElementById('pick-count').textContent = view.fresh ? view.active : '—';
    const models = view.rows.filter(r => r.status.provisional).length;
    document.getElementById('model-count').textContent = models;
    document.getElementById('research-count').textContent = view.rows.length - view.active - models;
    const term = search.value.trim().toLowerCase();
    const selected = view.rows.filter(({row}) => `${row.team_a} ${row.team_b} ${row.tournament}`.toLowerCase().includes(term));
    list.replaceChildren();
    for (const {row, status} of selected) {
      const card = el('article', null, `match ${status.pick && !status.provisional ? 'active' : 'review'}`);
      card.append(el('span', status.reason, 'badge'), el('h3', `${row.team_a} vs ${row.team_b}`), el('p', `${row.tournament} · Tier ${row.tier || 'unverified'}`, 'small'));
      card.append(el('p', `Starts ${row.start_utc || 'unverified'} · Locks ${row.lock_utc || 'unverified'}`, 'small'));
      card.append(el('h3', status.pick ? `${status.provisional ? 'Research pick' : 'Pick'}: ${status.pick}` : 'Pick: — Unverified'));
      const probs = el('div', null, 'probabilities');
      for (const [name, p] of [[row.team_a, status.a], [row.team_b, status.b]]) {
        const cell = el('div'); cell.append(el('span', name), el('b', p == null ? '—' : `${p.toFixed(1)}%`)); probs.append(cell);
      }
      card.append(probs);
      card.append(el('p', status.provisional ? `BO${status.bestOf} project estimate from sourced historical ratings. Uncalibrated; assumes independent maps. Not a verified win probability.` : status.pick ? `Quote observed ${row.market_captured_utc}. Market-implied estimate, not a guarantee.` : `Available research: ${row.basis_label || 'no usable basis'}. Unconfirmed percentages deliberately left blank.`, 'small'));
      const sources = el('div', null, 'source-links');
      sources.append(link(row.hotspawn_pickem_url || 'https://play.hotspawn.com/cs2-pickems', 'Official fixture source'));
      if (row.hltv_match_url) sources.append(link(row.hltv_match_url, 'HLTV match'));
      if (status.provisional) {
        sources.append(link(status.formatURL, 'HLTV series format'), link(row.rating_a.vrs_url, 'Official rating inputs'));
      } else if (status.pick) {
        const source = (row.basis_sources || []).find(s => { const u = safeURL(s[0]); return u && /(^|\.)pinnacle\.com$/.test(new URL(u).hostname); });
        sources.append(link(source[0], 'Bookmaker source'));
      }
      const research = el('a', 'Research & flags →'); research.href = 'executive/picks.html'; sources.append(research);
      card.append(sources); list.append(card);
    }
    if (!selected.length) list.append(el('p', view.rows.length ? 'No matches for this search.' : 'No not-yet-locked fixtures in this capture. Check the coverage page for capture limitations.'));
    document.getElementById('match-count').textContent = `${selected.length} of ${view.rows.length} captured, not-yet-locked / time-unverified fixtures shown.`;
  }
  async function update() {
    try {
      const response = await fetch('executive/data/analysis.json', {cache: 'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json(); snapshot(data, Date.now()); latest = data;
      render();
      try {
        const verification = await fetch('reread/data/source_check.csv', {cache: 'no-store'});
        evidence = verification.ok ? parseCSV(await verification.text()) : [];
      } catch (_) { evidence = []; }
      // Fetch each distinct immutable official standings file once per page session.
      // Failure withholds model estimates; it never substitutes the cached board's claimed points.
      const urls = new Set(Object.values(data.fixtures).flatMap(r => [r.rating_a?.vrs_url, r.rating_b?.vrs_url]).filter(Boolean));
      await Promise.all([...urls].map(async url => {
        if (officialRatings[url]) return;
        const pinned = /^https:\/\/github\.com\/ValveSoftware\/counter-strike_regional_standings\/blob\/([a-f0-9]{40})\/(live\/\d{4}\/standings_global_\d{4}_\d{2}_\d{2}\.md)$/.exec(url);
        if (!pinned) return;
        try {
          const source = await fetch(`https://api.github.com/repos/ValveSoftware/counter-strike_regional_standings/contents/${pinned[2]}?ref=${pinned[1]}`, {signal: AbortSignal.timeout(15000)});
          if (!source.ok) return;
          const blob = await source.json();
          if (blob.encoding !== 'base64' || typeof blob.content !== 'string') return;
          const markdown = new TextDecoder().decode(Uint8Array.from(atob(blob.content.replace(/\s/g, '')), c => c.charCodeAt(0)));
          officialRatings[url] = parseStandings(markdown);
        } catch (_) { /* Official points not confirmed: no fallback estimate. */ }
      }));
      render();
    } catch (_) {
      latest = null;
      document.getElementById('freshness').textContent = 'Snapshot unavailable / unverified. No active picks displayed. Open the published research table and inspect its timestamp.';
      for (const id of ['open-count', 'pick-count', 'model-count', 'research-count']) document.getElementById(id).textContent = '—';
      list.replaceChildren(el('p', 'Could not load current evidence. Use the research and coverage links above; no values substituted.'));
      document.getElementById('match-count').textContent = '';
    }
  }
  search.addEventListener('input', render);
  update(); setInterval(update, 60000);
})();
