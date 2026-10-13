'use strict';
// No external libraries, trackers or browser requests to localhost.
const notice = document.querySelector('[data-checked]');
if (notice) {
  const elapsed = Date.now() - Date.parse(notice.dataset.checked);
  const age = document.querySelector('#age');
  if (age && Number.isFinite(elapsed)) {
    const minutes = Math.max(0, Math.floor(elapsed / 60000));
    age.textContent = `${minutes < 60 ? `${minutes} minutes` : `${Math.floor(minutes / 60)} hours`} since this audit. Historical snapshot only — not live or executable odds.`;
  }
}
const search = document.querySelector('#search');
const status = document.querySelector('#status');
const rows = Array.from(document.querySelectorAll('tbody tr[data-status]'));
const count = document.querySelector('#result-count');
const empty = document.querySelector('#empty');
function filter() {
  const term = (search?.value || '').trim().toLocaleLowerCase();
  const selected = status?.value || 'all';
  let visible = 0;
  for (const row of rows) {
    row.hidden = !(row.textContent.toLocaleLowerCase().includes(term) && (selected === 'all' || selected === row.dataset.status));
    if (!row.hidden) visible++;
  }
  if (count) count.textContent = `${visible} of ${rows.length} entries`;
  if (empty) empty.hidden = visible !== 0;
}
search?.addEventListener('input', filter);
status?.addEventListener('change', filter);
if (rows.length) filter();
