(function () {
  var input = document.getElementById('filter');
  var hideStale = document.getElementById('hideStale');
  var cards = document.getElementById('cards');
  var empty = document.getElementById('empty');
  if (!cards) { return; }

  function apply() {
    var q = (input && input.value || '').toLowerCase().trim();
    var hidePast = !!(hideStale && hideStale.checked);
    var shown = 0;
    Array.prototype.forEach.call(cards.querySelectorAll('.card'), function (card) {
      var hay = (card.getAttribute('data-search') || '').toLowerCase();
      var stale = card.classList.contains('is-stale');
      var ok = (!q || hay.indexOf(q) !== -1) && !(hidePast && stale);
      card.hidden = !ok;
      if (ok) { shown++; }
    });
    if (empty) { empty.hidden = shown !== 0; }
  }

  if (input) { input.addEventListener('input', apply); }
  if (hideStale) { hideStale.addEventListener('change', apply); }

  // Dim any row whose Hotspawn lock time has already passed in the visitor's real time.
  function markLocks() {
    var now = Date.now();
    Array.prototype.forEach.call(cards.querySelectorAll('.card[data-lock]'), function (card) {
      var stamp = card.getAttribute('data-lock');
      if (!stamp) { return; }
      var when = Date.parse(stamp.replace(' ', 'T') + 'Z');
      if (isNaN(when) || when > now) { return; }
      if (card.classList.contains('is-stale')) { return; }
      card.classList.add('is-stale');
      var head = card.querySelector('.card-head');
      if (head && !head.querySelector('.badge-stale')) {
        var tag = document.createElement('span');
        tag.className = 'badge badge-stale';
        tag.textContent = 'lock time passed';
        head.appendChild(tag);
      }
    });
  }

  markLocks();
  setInterval(markLocks, 60000);
})();
