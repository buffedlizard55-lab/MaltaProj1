'use strict';
(() => {
  const sidebar = document.getElementById('sidebar');
  const menu = document.getElementById('menu-toggle');
  const shade = document.getElementById('mobile-shade');
  const setMenu = open => {
    sidebar?.classList.toggle('open', open);
    shade?.classList.toggle('open', open);
    menu?.setAttribute('aria-expanded', String(open));
    if (open) sidebar?.querySelector('a')?.focus();
    else menu?.focus();
  };
  menu?.addEventListener('click', () => setMenu(!sidebar.classList.contains('open')));
  shade?.addEventListener('click', () => setMenu(false));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && sidebar?.classList.contains('open')) setMenu(false);
    if (event.key === 'Tab' && sidebar?.classList.contains('open') && matchMedia('(max-width:700px)').matches) {
      const links = [...sidebar.querySelectorAll('a, button')];
      const first = links[0], last = links[links.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }
  });

  const table = document.querySelector('[data-filter-table]');
  if (table) {
    const rows = [...table.querySelectorAll('tbody tr[data-row]')];
    const search = document.getElementById('match-search');
    const game = document.getElementById('game-filter');
    const coverage = document.getElementById('coverage-filter');
    const tournament = document.getElementById('tournament-filter');
    const count = document.getElementById('result-count');
    const empty = document.getElementById('no-results');
    const tabs = [...document.querySelectorAll('[data-game-tab]')];
    const params = new URLSearchParams(location.search);
    let tabGame = params.get('game') || 'all';
    if (search) search.value = params.get('q') || '';
    if (game && [...game.options].some(option => option.value === tabGame)) game.value = tabGame;
    if (coverage && [...coverage.options].some(option => option.value === params.get('coverage'))) coverage.value = params.get('coverage');
    const apply = () => {
      const needle = (search?.value || '').trim().toLocaleLowerCase();
      const chosenGame = game?.value || tabGame;
      let visible = 0;
      for (const row of rows) {
        const isPriced = row.dataset.priced === 'true' && !row.classList.contains('quote-expired');
        const matches = (!needle || row.dataset.search.toLocaleLowerCase().includes(needle))
          && (chosenGame === 'all' || row.dataset.game === chosenGame)
          && (!tournament?.value || row.dataset.tournament === tournament.value)
          && (!coverage?.value || (coverage.value === 'priced' ? isPriced : !isPriced));
        row.hidden = !matches;
        if (matches) visible++;
      }
      if (count) count.textContent = `Showing ${visible} of ${rows.length} fixtures`;
      if (empty) empty.hidden = visible > 0 || rows.length === 0;
      tabs.forEach(tab => tab.setAttribute('aria-pressed', String(tab.dataset.gameTab === chosenGame)));
      const next = new URL(location.href);
      for (const [key, value] of [['q', needle], ['game', chosenGame === 'all' ? '' : chosenGame], ['coverage', coverage?.value || '']]) {
        if (value) next.searchParams.set(key, value); else next.searchParams.delete(key);
      }
      history.replaceState(null, '', next);
    };
    [search, game, coverage, tournament].forEach(control => control?.addEventListener(control === search ? 'input' : 'change', apply));
    tabs.forEach(tab => tab.addEventListener('click', () => { tabGame = tab.dataset.gameTab; if (game) game.value = tabGame; apply(); }));
    document.getElementById('clear-filters')?.addEventListener('click', () => {
      if (search) search.value = '';
      if (game) game.value = 'all';
      if (coverage) coverage.value = '';
      if (tournament) tournament.value = '';
      tabGame = 'all'; apply();
    });
    table.querySelectorAll('[data-sort]').forEach(button => button.addEventListener('click', () => {
      const key = button.dataset.sort;
      const direction = button.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
      table.querySelectorAll('[data-sort]').forEach(other => other.removeAttribute('aria-sort'));
      button.setAttribute('aria-sort', direction);
      const sorted = [...rows].sort((a, b) => {
        const av = a.dataset[key] || '', bv = b.dataset[key] || '';
        const comparison = key === 'probability' ? Number(av || -1) - Number(bv || -1) : av.localeCompare(bv);
        return direction === 'ascending' ? comparison : -comparison;
      });
      const body = table.querySelector('tbody');
      sorted.forEach(row => body.append(row));
    }));
    document.getElementById('download-csv')?.addEventListener('click', () => {
      // These exact displayed values, never prices hidden due to expiry.
      const csvEscape = value => {
        let text = String(value ?? '').replace(/\s+/g, ' ').trim();
        if (/^[=+@-]/.test(text)) text = `'${text}`;
        return `"${text.replaceAll('"', '""')}"`;
      };
      const header = ['Match', 'Tournament', 'Game', 'Start (UTC)', 'Calculated probability A', 'Calculated probability B', 'Fair decimal A', 'Fair decimal B', 'Status', 'Official fixture source', 'External odds sources'];
      const lines = [header.map(csvEscape).join(',')];
      for (const row of rows.filter(item => !item.hidden)) {
        const expired = row.classList.contains('quote-expired');
        const values = [row.dataset.match, row.dataset.tournament, row.dataset.game, row.dataset.start,
          expired ? '' : row.dataset.pa, expired ? '' : row.dataset.pb, expired ? '' : row.dataset.fa, expired ? '' : row.dataset.fb,
          expired ? 'Expired; unverified' : row.dataset.status, row.dataset.source, row.dataset.oddsSources];
        lines.push(values.map(csvEscape).join(','));
      }
      const blob = new Blob(['\uFEFF' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'});
      const url = URL.createObjectURL(blob), link = document.createElement('a');
      link.href = url; link.download = 'linescope-filtered-matches.csv'; document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    apply();
    document.addEventListener('quotes-expired', apply);
  }

  const snapshot = document.body.dataset.snapshot;
  const latestAt = Date.parse(snapshot || '');
  const verifiedAt = Date.parse(document.body.dataset.verifiedAt || snapshot || '');
  const maxAge = Number(document.body.dataset.maxAge || 3600) * 1000;
  const freshness = document.getElementById('snapshot-freshness');
  const banner = document.getElementById('snapshot-banner');
  const datedRows = [...document.querySelectorAll('[data-quote-expires]')];
  const updateFreshness = () => {
    const now = Date.now();
    const age = now - verifiedAt;
    const stale = !Number.isFinite(verifiedAt) || age > maxAge || age < -60000;
    if (freshness) {
      const minutes = Math.max(0, Math.floor(age / 60000));
      freshness.textContent = Number.isFinite(verifiedAt) ? `${stale ? 'Stale snapshot' : 'Snapshot'} · ${minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h`} ago` : 'Snapshot unverified';
      freshness.parentElement.querySelector('.dot')?.classList.toggle('amber', stale);
    }
    if (banner) banner.hidden = !stale;
    let changed = false;
    for (const row of datedRows) {
      const expires = Date.parse(row.dataset.quoteExpires);
      const starts = Date.parse(row.dataset.start || '');
      const expired = !Number.isFinite(expires) || now > expires || (Number.isFinite(starts) && now >= starts);
      if (expired && !row.classList.contains('quote-expired')) { row.classList.add('quote-expired'); changed = true; }
    }
    if (changed) {
      const allRows = [...document.querySelectorAll('tr[data-row]')];
      const priced = allRows.filter(row => row.dataset.priced === 'true' && !row.classList.contains('quote-expired')).length;
      const set = (id, value) => { const element = document.getElementById(id); if (element) element.textContent = String(value); };
      if (allRows.length) { set('metric-priced', priced); set('metric-unpriced', allRows.length - priced); set('metric-coverage', `${Math.round(100 * priced / allRows.length)}%`); }
      document.dispatchEvent(new Event('quotes-expired'));
    }
  };
  updateFreshness();
  setInterval(updateFreshness, 60000);

  // Static Pages only: poll this site's own snapshot, never call a remote sportsbook from a browser.
  if (snapshot) setInterval(async () => {
    try {
      const response = await fetch(`data/snapshot.json?checked=${Date.now()}`, {cache: 'no-store'});
      if (!response.ok) return;
      const next = await response.json();
      if (next.generated_at && next.generated_at !== snapshot && Date.parse(next.generated_at) > latestAt) location.reload();
    } catch { /* Retain timestamped data; freshness and fail-closed expiry still apply. */ }
  }, 300000);
})();
