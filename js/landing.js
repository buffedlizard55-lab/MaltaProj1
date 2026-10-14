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
  function snapshot(data, now) {
    if (!data || !data.fixtures || Array.isArray(data.fixtures) || typeof data.fixtures !== 'object') throw new Error('Invalid fixture evidence');
    const rows = Object.values(data.fixtures);
    if (!rows.length || rows.some(r => !r || !r.match_id || !r.team_a || !r.team_b)) throw new Error('Incomplete fixture evidence');
    const capture = data.capture_utc;
    // Unknown lock times are retained for review rather than silently excluded.
    const visible = rows.filter(r => !Number.isFinite(time(r.lock_utc)) || time(r.lock_utc) > now)
      .sort((a, b) => (time(a.start_utc) || Infinity) - (time(b.start_utc) || Infinity))
      .map(row => ({row, status: assess(row, capture, now)}));
    return {capture, fresh: fresh(capture, now), rows: visible, active: visible.filter(r => r.status.pick).length};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {time, fresh, safeURL, assess, snapshot};
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
  let latest;
  const list = document.getElementById('match-list'), search = document.getElementById('match-search');
  function render() {
    if (!latest) return;
    const view = snapshot(latest, Date.now());
    document.getElementById('freshness').textContent = `${view.fresh ? 'Published observation' : 'STALE / REVIEW'} · Hotspawn capture ${view.capture || 'unverified'}. Source timestamps are checked separately; these are not live odds.`;
    document.getElementById('open-count').textContent = view.rows.length;
    document.getElementById('pick-count').textContent = view.fresh ? view.active : '—';
    document.getElementById('research-count').textContent = view.rows.length - view.active;
    const term = search.value.trim().toLowerCase();
    const selected = view.rows.filter(({row}) => `${row.team_a} ${row.team_b} ${row.tournament}`.toLowerCase().includes(term));
    list.replaceChildren();
    for (const {row, status} of selected) {
      const card = el('article', null, `match ${status.pick ? 'active' : 'review'}`);
      card.append(el('span', status.reason, 'badge'), el('h3', `${row.team_a} vs ${row.team_b}`), el('p', `${row.tournament} · Tier ${row.tier || 'unverified'}`, 'small'));
      card.append(el('p', `Starts ${row.start_utc || 'unverified'} · Locks ${row.lock_utc || 'unverified'}`, 'small'));
      card.append(el('h3', status.pick ? `Pick: ${status.pick}` : 'Pick: — Unverified'));
      const probs = el('div', null, 'probabilities');
      for (const [name, p] of [[row.team_a, status.a], [row.team_b, status.b]]) {
        const cell = el('div'); cell.append(el('span', name), el('b', p == null ? '—' : `${p.toFixed(1)}%`)); probs.append(cell);
      }
      card.append(probs);
      card.append(el('p', status.pick ? `Quote observed ${row.market_captured_utc}. Market-implied estimate, not a guarantee.` : `Available research: ${row.basis_label || 'no usable basis'}. Unconfirmed percentages deliberately left blank.`, 'small'));
      const sources = el('div', null, 'source-links');
      sources.append(link(row.hotspawn_pickem_url || 'https://play.hotspawn.com/cs2-pickems', 'Official fixture source'));
      if (row.hltv_match_url) sources.append(link(row.hltv_match_url, 'HLTV match'));
      if (status.pick) {
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
      const data = await response.json(); snapshot(data, Date.now()); latest = data; render();
    } catch (_) {
      latest = null;
      document.getElementById('freshness').textContent = 'Snapshot unavailable / unverified. No active picks displayed. Open the published research table and inspect its timestamp.';
      for (const id of ['open-count', 'pick-count', 'research-count']) document.getElementById(id).textContent = '—';
      list.replaceChildren(el('p', 'Could not load current evidence. Use the research and coverage links above; no values substituted.'));
      document.getElementById('match-count').textContent = '';
    }
  }
  search.addEventListener('input', render);
  update(); setInterval(update, 60000);
})();
