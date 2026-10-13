'use strict';
(() => {
  const repo = 'buffedlizard55-lab/MaltaProj1';
  const branch = 'arena/4f599d7c-maltaproj1';
  const view = document.body.dataset.view || 'index';
  const views = new Set(['index', 'matches', 'cs2', 'lol', 'inventory', 'markets', 'sources', 'flagged', 'methodology', 'repository']);
  const apiRoot = `https://api.github.com/repos/${repo}`;
  const repoRoot = `https://github.com/${repo}`;
  let snapshot = document.body.dataset.snapshot || '';
  let latestAt = Date.parse(snapshot);
  let verifiedAt = Date.parse(document.body.dataset.verifiedAt || '');
  let expiryListener = null;
  let updating = false;

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

  function bindTables() {
    if (expiryListener) document.removeEventListener('quotes-expired', expiryListener);
    expiryListener = null;
    const table = document.querySelector('[data-filter-table]');
    if (!table) return;
    const rows = [...table.querySelectorAll('tbody tr[data-row]')];
    const search = document.getElementById('match-search');
    const coverage = document.getElementById('coverage-filter');
    const tournament = document.getElementById('tournament-filter');
    const count = document.getElementById('result-count');
    const empty = document.getElementById('no-results');
    const tabs = [...document.querySelectorAll('[data-game-tab]')];
    const params = new URLSearchParams(location.search);
    let chosenGame = params.get('game') || 'all';
    if (!['all', 'cs2', 'lol'].includes(chosenGame)) chosenGame = 'all';
    if (search) search.value = params.get('q') || '';
    if (coverage && [...coverage.options].some(option => option.value === params.get('coverage'))) coverage.value = params.get('coverage');
    if (tournament && [...tournament.options].some(option => option.value === params.get('tournament'))) tournament.value = params.get('tournament');
    const apply = () => {
      const needle = (search?.value || '').trim().toLocaleLowerCase();
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
      for (const [key, value] of [['q', needle], ['game', chosenGame === 'all' ? '' : chosenGame], ['coverage', coverage?.value || ''], ['tournament', tournament?.value || '']]) {
        if (value) next.searchParams.set(key, value); else next.searchParams.delete(key);
      }
      history.replaceState(null, '', next);
    };
    search?.addEventListener('input', apply);
    coverage?.addEventListener('change', apply);
    tournament?.addEventListener('change', apply);
    tabs.forEach(tab => tab.addEventListener('click', () => { chosenGame = tab.dataset.gameTab; apply(); }));
    document.getElementById('clear-filters')?.addEventListener('click', () => {
      if (search) search.value = '';
      if (coverage) coverage.value = '';
      if (tournament) tournament.value = '';
      chosenGame = 'all'; apply();
    });
    table.querySelectorAll('[data-sort]').forEach(button => button.addEventListener('click', () => {
      const key = button.dataset.sort;
      const direction = button.dataset.direction === 'ascending' ? 'descending' : 'ascending';
      table.querySelectorAll('[data-sort]').forEach(other => {
        delete other.dataset.direction; other.closest('th')?.removeAttribute('aria-sort');
      });
      button.dataset.direction = direction;
      button.closest('th')?.setAttribute('aria-sort', direction);
      const sorted = [...rows].sort((a, b) => {
        const av = a.dataset[key] || '', bv = b.dataset[key] || '';
        const comparison = key === 'probability' ? Number(av || -1) - Number(bv || -1) : av.localeCompare(bv);
        return direction === 'ascending' ? comparison : -comparison;
      });
      sorted.forEach(row => table.querySelector('tbody').append(row));
    }));
    document.getElementById('download-csv')?.addEventListener('click', () => {
      const escapeCSV = value => {
        let text = String(value ?? '').replace(/\s+/g, ' ').trim();
        if (/^[=+@-]/.test(text)) text = `'${text}`;
        return `"${text.replaceAll('"', '""')}"`;
      };
      const header = ['Match', 'Tournament', 'Game', 'Start (UTC)', 'Calculated probability A', 'Calculated probability B', 'Fair decimal A', 'Fair decimal B', 'Status', 'Official fixture source', 'External odds sources', 'Snapshot UTC'];
      const lines = [header.map(escapeCSV).join(',')];
      for (const row of [...table.querySelectorAll('tbody tr[data-row]')].filter(item => !item.hidden)) {
        const expired = row.classList.contains('quote-expired');
        const values = [row.dataset.match, row.dataset.tournament, row.dataset.game, row.dataset.start,
          expired ? '' : row.dataset.pa, expired ? '' : row.dataset.pb, expired ? '' : row.dataset.fa, expired ? '' : row.dataset.fb,
          expired ? 'Expired; unverified' : row.dataset.status, row.dataset.source, row.dataset.oddsSources, snapshot];
        lines.push(values.map(escapeCSV).join(','));
      }
      download(new Blob(['\uFEFF' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8'}), 'linescope-filtered-matches.csv');
    });
    apply();
    expiryListener = apply;
    document.addEventListener('quotes-expired', expiryListener);
  }

  function download(blob, name) {
    const url = URL.createObjectURL(blob), link = document.createElement('a');
    link.href = url; link.download = name; document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function updateFreshness() {
    const now = Date.now();
    const age = now - verifiedAt;
    const maxAge = Number(document.body.dataset.maxAge || 3600) * 1000;
    const stale = !Number.isFinite(verifiedAt) || age > maxAge || age < -60000;
    const freshness = document.getElementById('snapshot-freshness');
    if (freshness) {
      const minutes = Math.max(0, Math.floor(age / 60000));
      freshness.textContent = Number.isFinite(verifiedAt)
        ? `${stale ? 'Stale snapshot' : 'Snapshot'} · ${minutes < 60 ? `${minutes}m` : `${Math.floor(minutes / 60)}h`} ago`
        : 'Snapshot unverified';
      freshness.parentElement.querySelector('.dot')?.classList.toggle('amber', stale);
    }
    const banner = document.getElementById('snapshot-banner');
    if (banner) banner.hidden = !stale;
    let changed = false;
    for (const row of document.querySelectorAll('[data-quote-expires]')) {
      const expires = Date.parse(row.dataset.quoteExpires);
      const starts = Date.parse(row.dataset.start || '');
      const expired = stale || !Number.isFinite(expires) || now > expires || (Number.isFinite(starts) && now >= starts);
      if (expired && !row.classList.contains('quote-expired')) { row.classList.add('quote-expired'); changed = true; }
    }
    if (stale) {
      // Do not infer that current coverage is zero: it is unknown, so leave it blank.
      for (const id of ['metric-priced', 'metric-unpriced', 'metric-coverage']) {
        const element = document.getElementById(id);
        if (element) { element.textContent = ''; element.setAttribute('aria-label', 'Current coverage unverified; intentionally blank'); }
      }
    }
    if (changed) document.dispatchEvent(new Event('quotes-expired'));
  }

  async function readPublicFile(path) {
    const url = `${apiRoot}/contents/${path}?ref=${encodeURIComponent(branch)}`;
    const response = await fetch(url, {headers: {Accept: 'application/vnd.github+json'}, credentials: 'omit', cache: 'no-store'});
    if (!response.ok) throw new Error(`Public snapshot access HTTP ${response.status}`);
    let file = await response.json();
    if (file.path !== path || file.type !== 'file') throw new Error('Unexpected public file');
    if (file.encoding !== 'base64' || !file.content) {
      if (!String(file.git_url || '').startsWith(`${apiRoot}/git/blobs/`)) throw new Error('Snapshot body unavailable');
      const blob = await fetch(file.git_url, {headers: {Accept: 'application/vnd.github+json'}, credentials: 'omit'});
      if (!blob.ok) throw new Error('Snapshot blob unavailable');
      file = await blob.json();
    }
    if (file.encoding !== 'base64' || !file.content) throw new Error('Unsupported public file encoding');
    const binary = atob(file.content.replace(/\s/g, ''));
    return new TextDecoder().decode(Uint8Array.from(binary, char => char.charCodeAt(0)));
  }

  function safeFragment(main) {
    // Import trusted compiled markup as inert DOM, never evaluate remote HTML/scripts.
    const allowed = new Set('a div span section table caption thead tbody tr th td button label input select option p h1 h2 h3 strong small code pre details summary svg path rect circle line polyline polygon br footer noscript ul li hr'.split(' '));
    for (const element of main.querySelectorAll('*')) {
      if (!allowed.has(element.tagName.toLowerCase())) { element.remove(); continue; }
      for (const attribute of [...element.attributes]) {
        const name = attribute.name.toLowerCase();
        if (name.startsWith('on') || ['srcdoc', 'src', 'formaction', 'xlink:href'].includes(name)) element.removeAttribute(attribute.name);
        if (name === 'style' && /url\s*\(|expression|@import|javascript/i.test(attribute.value)) element.removeAttribute('style');
      }
      if (element.hasAttribute('href')) {
        const raw = element.getAttribute('href');
        const parsed = new URL(raw, location.href);
        if (!['https:', 'http:'].includes(parsed.protocol) || (parsed.protocol === 'http:' && parsed.origin !== location.origin)) element.removeAttribute('href');
        if (raw.startsWith('data/evidence/')) {
          const filename = raw.slice('data/evidence/'.length);
          if (/^[a-z0-9_.-]+$/i.test(filename)) element.setAttribute('href', `${repoRoot}/blob/${branch}/data/snapshot/evidence/${filename}`);
          else element.removeAttribute('href');
        }
        if (raw === 'data/snapshot.json') {
          element.setAttribute('href', `${repoRoot}/blob/${branch}/data/snapshot/latest.json`);
          element.dataset.liveJson = 'true';
        }
        if (element.getAttribute('target') === '_blank') element.setAttribute('rel', 'noopener noreferrer');
      }
    }
    return document.importNode(main, true);
  }

  function bindJSONDownloads() {
    document.querySelectorAll('[data-live-json]').forEach(link => link.addEventListener('click', async event => {
      event.preventDefault();
      try {
        const text = await readPublicFile('data/snapshot/latest.json');
        const data = JSON.parse(text);
        if (data.schema_version !== 1 || !Array.isArray(data.matches)) throw new Error('Unknown snapshot schema');
        download(new Blob([text], {type: 'application/json;charset=utf-8'}), 'linescope-verified-snapshot.json');
      } catch {
        // Still give access to the official repository without inventing data.
        window.open(link.href, '_blank', 'noopener,noreferrer');
      }
    }));
  }

  function acceptCompiledSnapshot(html, cached = false) {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    const at = Date.parse(doc.body.dataset.snapshot || '');
    const main = doc.querySelector('main#main');
    if (!main || doc.body.dataset.view !== view || !Number.isFinite(at) || at > Date.now() + 60000 || at < latestAt) throw new Error('Unexpected compiled snapshot');
    if (at > latestAt) {
      const focused = document.activeElement?.id;
      const next = safeFragment(main);
      document.getElementById('main').replaceWith(next);
      snapshot = doc.body.dataset.snapshot;
      latestAt = at;
      verifiedAt = Date.parse(doc.body.dataset.verifiedAt || '');
      document.body.dataset.snapshot = snapshot;
      document.body.dataset.verifiedAt = doc.body.dataset.verifiedAt || '';
      bindTables();
      bindJSONDownloads();
      if (focused) document.getElementById(focused)?.focus({preventScroll: true});
    }
    const state = document.getElementById('update-check-status');
    if (state) state.textContent = `${cached ? 'Cached verified branch snapshot' : 'Checked public collection branch'} · scheduled every 30m`;
    updateFreshness();
  }

  async function refreshPublishedData() {
    if (updating || !views.has(view)) return;
    updating = true;
    const key = `maltaproj1:linescope:${view}:v1`;
    try {
      let cached;
      try { cached = JSON.parse(sessionStorage.getItem(key) || 'null'); } catch { cached = null; }
      if (cached && Date.now() - cached.checked < 240000) {
        acceptCompiledSnapshot(cached.html, true);
      } else {
        const html = await readPublicFile(`dashboard/${view}.html`);
        acceptCompiledSnapshot(html);
        try { sessionStorage.setItem(key, JSON.stringify({checked: Date.now(), html})); } catch { /* Storage is optional. */ }
      }
    } catch {
      const state = document.getElementById('update-check-status');
      if (state) state.textContent = 'Automatic check unavailable · dated published snapshot retained';
      updateFreshness();
    } finally {
      updating = false;
    }
  }

  bindTables();
  updateFreshness();
  refreshPublishedData();
  setInterval(updateFreshness, 60000);
  setInterval(refreshPublishedData, 300000);
})();
