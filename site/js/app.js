// Shared dashboard logic: loads matches.json and renders into tables.

async function loadMatches() {
  try {
    // Support both root and site-subpage contexts
    const paths = ['site/data/matches.json', 'data/matches.json', '../data/matches.json'];
    let data = null;
    for (const p of paths) {
      try {
        const r = await fetch(p, { cache: 'no-store' });
        if (r.ok) { data = await r.json(); break; }
      } catch (e) { /* try next */ }
    }
    if (!data) throw new Error('Could not load matches.json');
    return data;
  } catch (e) {
    console.error(e);
    document.getElementById('matches-body').innerHTML =
      '<tr><td colspan="10" class="no-data">Failed to load data: ' + e.message + '</td></tr>';
    throw e;
  }
}

function fmtPct(p) {
  if (p === null || p === undefined) return '—';
  return p.toFixed(1) + '%';
}

function tierBadge(t) {
  return `<span class="tier-badge tier-${t}">${escapeHtml(t)}</span>`;
}

function statusPill(s) {
  const cls = s === 'yes' ? 'status-yes' : s === 'partial' ? 'status-partial' : 'status-no';
  const label = s === 'yes' ? 'Verified' : s === 'partial' ? 'Partial' : 'Unverified';
  return `<span class="status-pill ${cls}">${label}</span>`;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function probCell(p, cls, hasFlag) {
  if (p === null || p === undefined) {
    return '<span class="no-data">—</span>';
  }
  return `<span class="prob-bar ${cls}">
    <span class="pct">${p.toFixed(1)}%</span>
    <span class="bar"><span style="width:${Math.min(100,Math.max(4,p))}%"></span></span>
  </span>`;
}

function renderRow(m) {
  const flagClass = m.flag ? 'flag-row' : '';
  const srcHtml = m.source_url
    ? `<a class="src-link" href="${escapeHtml(m.source_url)}" target="_blank" rel="noopener">${escapeHtml(m.odds_source || 'Source')}</a>`
    : '<span class="no-data">—</span>';
  const hsHtml = (m.hotspawn_pick_pct_a !== null)
    ? `<span class="hs-pick"><strong>${m.hotspawn_pick_pct_a}%</strong> / <strong>${m.hotspawn_pick_pct_b}%</strong></span>`
    : '<span class="no-data">—</span>';
  const flagHtml = m.flag ? `<span class="flag-note">⚠ ${escapeHtml(m.flag)}</span>` : '';

  return `<tr class="${flagClass}">
    <td>
      <div>${escapeHtml(m.date)}</div>
      <div style="font-size:12px;color:var(--muted)">${escapeHtml(m.time_utc)} UTC · ${escapeHtml(m.format)}</div>
    </td>
    <td>${escapeHtml(m.tournament)}${flagHtml}</td>
    <td>${tierBadge(m.tier)}</td>
    <td class="team-cell">${escapeHtml(m.team_a)}</td>
    <td>${probCell(m.implied_prob_a, 'prob-a')}
        <div style="font-size:11px;color:var(--muted);margin-top:3px">${m.odds_a ? '@ ' + m.odds_a.toFixed(2) : ''}</div>
    </td>
    <td>${probCell(m.implied_prob_b, 'prob-b')}
        <div style="font-size:11px;color:var(--muted);margin-top:3px">${m.odds_b ? '@ ' + m.odds_b.toFixed(2) : ''}</div>
    </td>
    <td class="team-cell">${escapeHtml(m.team_b)}</td>
    <td>${hsHtml}</td>
    <td>${srcHtml}</td>
    <td>${statusPill(m.verified)}</td>
  </tr>`;
}

function matchesFilters(matches) {
  const tier = document.getElementById('tier-filter').value;
  const verif = document.getElementById('verif-filter').value;
  const q = document.getElementById('search').value.trim().toLowerCase();
  return matches.filter(m => {
    if (tier !== 'all' && m.tier !== tier) return false;
    if (verif !== 'all' && m.verified !== verif) return false;
    if (q) {
      const hay = (m.tournament + ' ' + m.team_a + ' ' + m.team_b + ' ' + (m.notes||'')).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderTable(matches, tbodyId) {
  const tbody = document.getElementById(tbodyId || 'matches-body');
  if (!tbody) return;
  if (!matches.length) {
    tbody.innerHTML = '<tr><td colspan="10" class="no-data" style="padding:20px;text-align:center">No matches match current filter.</td></tr>';
    return;
  }
  // Sort: by date, then time
  matches.sort((a,b) => (a.date + a.time_utc).localeCompare(b.date + b.time_utc));
  tbody.innerHTML = matches.map(renderRow).join('');
}

function updateKpis(matches) {
  const total = matches.length;
  const ver = matches.filter(m => m.verified === 'yes').length;
  const unv = matches.filter(m => m.verified === 'no').length;
  const s = matches.filter(m => m.tier === 'S').length;
  const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  set('kpi-total', total);
  set('kpi-verified', ver);
  set('kpi-unverified', unv);
  set('kpi-s', s);
}

function initDashboard(customFilter) {
  loadMatches().then(data => {
    // Gen time
    const gEl = document.getElementById('gen-time');
    if (gEl) gEl.textContent = 'Data generated: ' + new Date(data.generated_at).toUTCString();
    const cov = document.getElementById('coverage-note');
    if (cov) cov.textContent = data.note_remaining_matches || '';

    let matches = data.matches;
    if (customFilter) matches = customFilter(matches);

    updateKpis(data.matches);
    renderTable(matches);

    const tierF = document.getElementById('tier-filter');
    const verifF = document.getElementById('verif-filter');
    const searchF = document.getElementById('search');
    const resetB = document.getElementById('reset');
    const rerender = () => {
      let list = customFilter ? customFilter(data.matches) : data.matches.slice();
      // Apply global filters on top
      const tier = tierF ? tierF.value : 'all';
      const verif = verifF ? verifF.value : 'all';
      const q = searchF ? searchF.value.trim().toLowerCase() : '';
      list = list.filter(m => {
        if (tier !== 'all' && m.tier !== tier) return false;
        if (verif !== 'all' && m.verified !== verif) return false;
        if (q) {
          const hay = (m.tournament + ' ' + m.team_a + ' ' + m.team_b + ' ' + (m.notes||'')).toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
      renderTable(list);
    };
    if (tierF) tierF.addEventListener('change', rerender);
    if (verifF) verifF.addEventListener('change', rerender);
    if (searchF) searchF.addEventListener('input', rerender);
    if (resetB) resetB.addEventListener('click', () => {
      if (tierF) tierF.value = 'all';
      if (verifF) verifF.value = 'all';
      if (searchF) searchF.value = '';
      rerender();
    });
  });
}
