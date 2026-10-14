
// Mobile helpers only: the full board is server-rendered, so it works without this file.
(function () {
  var cards = Array.prototype.slice.call(document.querySelectorAll('.m'));
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.filters button'));
  function apply(kind) {
    cards.forEach(function (c) {
      var basis = c.getAttribute('data-basis') || '';
      var show = true;
      if (kind === 'market') show = basis.indexOf('market') === 0;
      else if (kind === 'own') show = basis === 'own-line' || basis === 'research';
      else if (kind === 'research') show = basis === 'research';
      else if (kind === 'flag') show = c.getAttribute('data-flag') === '1';
      else if (kind === 'open') show = !c.classList.contains('locked');
      c.style.display = show ? '' : 'none';
    });
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-filter') === kind)); });
  }
  buttons.forEach(function (b) {
    b.addEventListener('click', function () { apply(b.getAttribute('data-filter')); });
  });
  function localise() {
    cards.forEach(function (c) {
      var iso = c.getAttribute('data-lock');
      if (!iso) return;
      var t = new Date(iso);
      if (isNaN(t.getTime())) return;
      var label = c.querySelector('[data-lock-label]');
      var rel = '';
      var diff = t.getTime() - Date.now();
      if (diff <= 0) { rel = ' · locked'; c.classList.add('locked'); }
      else {
        var h = Math.floor(diff / 3600000), m = Math.round((diff % 3600000) / 60000);
        rel = ' · in ' + (h > 0 ? h + 'h ' : '') + m + 'm';
      }
      if (label) label.textContent = 'locks ' + t.toLocaleString() + rel;
    });
  }
  localise();
  setInterval(localise, 60000);
})();
