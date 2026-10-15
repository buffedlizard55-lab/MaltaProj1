/* Executive board — progressive enhancement only.
   With JavaScript off, the full table and all cards are already in the HTML. */
(function () {
  "use strict";

  var table = document.querySelector(".grid--picks");
  var query = document.getElementById("q");
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chip"));
  if (!table) { return; }

  var rows = Array.prototype.slice.call(table.querySelectorAll("tbody tr"));
  var state = { filter: "all", text: "" };

  function rowMatches(row) {
    var cells = row.textContent.toLowerCase();
    if (state.text && cells.indexOf(state.text) === -1) { return false; }
    var flags = row.getAttribute("data-flags") || "";
    switch (state.filter) {
      case "all": return true;
      case "nopick": return /no pick|—/.test(row.getAttribute("data-pick") || "") || row.getAttribute("data-pick") === "";
      case "open": return row.getAttribute("data-status") === "open";
      case "locked": return row.getAttribute("data-status") === "locked";
      case "market": return ["1", "2"].indexOf(row.getAttribute("data-tier")) !== -1;
      case "model": return ["3", "4"].indexOf(row.getAttribute("data-tier")) !== -1;
      case "provisional": return row.getAttribute("data-tier") === "4" || flags.indexOf("FL-UNLISTED-OPPONENT") !== -1;
      default: return true;
    }
  }

  function apply() {
    var shown = 0;
    rows.forEach(function (row) {
      var ok = rowMatches(row);
      row.classList.toggle("hidden", !ok);
      if (ok) { shown += 1; }
    });
    var counter = document.getElementById("shown");
    if (counter) { counter.textContent = String(shown); }
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      state.filter = chip.getAttribute("data-filter") || "all";
      chips.forEach(function (other) { other.classList.toggle("chip--on", other === chip); });
      apply();
    });
  });

  if (query) {
    query.addEventListener("input", function () {
      state.text = query.value.trim().toLowerCase();
      apply();
    });
  }

  /* Cards are also filterable by the same free-text box, so the phone view stays useful. */
  var cards = Array.prototype.slice.call(document.querySelectorAll(".pick"));
  var cardSearch = document.querySelector("[data-card-search]");
  function filterCards(term) {
    var text = (term || "").trim().toLowerCase();
    cards.forEach(function (card) {
      var haystack = (card.getAttribute("data-search") || card.textContent).toLowerCase();
      card.classList.toggle("hidden", Boolean(text) && haystack.indexOf(text) === -1);
    });
  }
  if (query) { query.addEventListener("input", function () { filterCards(query.value); }); }
  if (cardSearch) {
    cardSearch.addEventListener("input", function () { filterCards(cardSearch.value); });
  }

  document.querySelectorAll("[data-copy]").forEach(function (button) {
    button.addEventListener("click", function () {
      var target = document.querySelector(button.getAttribute("data-copy"));
      if (target && navigator.clipboard) { navigator.clipboard.writeText(target.textContent); }
    });
  });

  apply();
})();

/* Source and deadline clocks are calculated in the visitor's browser, not frozen at build time. */
(function () {
  "use strict";
  function updateClocks() {
    var now = Date.now();
    document.querySelectorAll("[data-source-time]").forEach(function (box) {
      var time = Date.parse(box.dataset.sourceTime);
      var age = (now - time) / 3600000;
      var label = box.querySelector("[data-age]");
      var invalid = !Number.isFinite(age) || age < -0.0834;
      var stale = invalid || age > 8;
      if (label) label.textContent = invalid ? "Source age unknown — do not treat as current." :
        (stale ? "STALE — " : age > 4 ? "Refresh due — " : "") + "Source capture " + age.toFixed(1) + " h ago (" + box.dataset.sourceTime + ").";
      box.classList.toggle("banner--stale", stale || box.dataset.slateCurrent !== "true");
    });
    document.querySelectorAll("[data-lock]").forEach(function (label) {
      var delta = Date.parse(label.dataset.lock) - now;
      if (!Number.isFinite(delta)) { label.textContent = "Lock unverified"; return; }
      label.textContent = delta <= 0 ? "Locked — not an actionable pick" :
        "Locks in " + Math.ceil(delta / 60000) + " min";
      var card = label.closest(".pick");
      if (card) {
        card.classList.toggle("pick--locked", delta <= 0);
        card.dataset.status = delta <= 0 ? "locked" : "open";
      }
    });
  }
  updateClocks();
  setInterval(updateClocks, 30000);
})();
