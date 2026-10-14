/* exec/app.js — keeps the summary current without a rebuild.
   Re-reads data/picks.json; if the committed file is newer than the copy baked into the page,
   it re-renders the match cards and the coverage tiles. Falls back to the baked HTML on any error. */
(function () {
  "use strict";
  var STALE_HOURS = 3;
  function fmtPct(v) { return (v === null || v === undefined) ? "—" : Number(v).toFixed(1) + "%"; }
  function escapeHtml(s) {
    return String(s === null || s === undefined ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function chips(row) {
    var out = "";
    (row.flags || []).forEach(function (f) {
      out += '<li><span class="code">' + escapeHtml(f.code) + "</span> " + escapeHtml(f.text) + "</li>";
    });
    return out ? '<ul class="flags">' + out + "</ul>" : "";
  }
  function card(row) {
    var lead = (row.p_a !== null && row.p_b !== null) ? (row.p_a >= row.p_b ? "a" : "b") : "";
    var basisLabel = {
      "market-direct": "bookmaker price (direct)",
      "market-secondary": "bookmaker price (aggregator)",
      "market-other": "bookmaker price (other listing)",
      "model": "our line from official ratings",
      "none": "no basis"
    }[row.line_source] || row.line_source;
    var market = "—";
    if (row.market_p_a !== null && row.market_p_a !== undefined) {
      market = fmtPct(row.market_p_a) + " / " + fmtPct(row.market_p_b) +
        " (" + escapeHtml(row.market_book || "book") + ")";
      if (row.market_url) {
        market += ' · <a href="' + escapeHtml(row.market_url) + '" rel="noopener">quote</a>';
      }
    }
    var own = (row.own_p_a === null || row.own_p_a === undefined) ? "—" :
      fmtPct(row.own_p_a) + " / " + fmtPct(row.own_p_b) +
      (row.own_url ? ' · <a href="' + escapeHtml(row.own_url) + '" rel="noopener">ratings</a>' : "");
    var pick = row.pick ?
      '<span class="pick">' + escapeHtml(row.pick) + " " + fmtPct(row.pick_pct) + "</span>" :
      '<span class="pick none">no pick</span>';
    var src = row.pick_source_url ?
      ' · <a href="' + escapeHtml(row.pick_source_url) + '" rel="noopener">source</a>' :
      ' · <span class="warn">no source</span>';
    return '<article class="card fixture" data-lock="' + escapeHtml(row.lock_utc) + '">' +
      '<header><div class="when">' + escapeHtml(row.kickoff_utc) +
      '<span class="tier">' + escapeHtml(row.tier || "?") + '-tier</span></div>' +
      '<div class="comp">' + escapeHtml(row.competition) + "</div>" +
      "<h3>" + escapeHtml(row.team_a) + ' <span class="vs">vs</span> ' + escapeHtml(row.team_b) + "</h3></header>" +
      '<div class="probs">' +
      '<div class="side' + (lead === "a" ? " lead" : "") + '"><span class="team">' + escapeHtml(row.team_a) +
      '</span><span class="pct">' + fmtPct(row.p_a) + "</span></div>" +
      '<div class="side' + (lead === "b" ? " lead" : "") + '"><span class="team">' + escapeHtml(row.team_b) +
      '</span><span class="pct">' + fmtPct(row.p_b) + "</span></div></div>" +
      '<p class="pickline">Pick: ' + pick + ' <span class="basis">· ' + escapeHtml(basisLabel) + "</span></p>" +
      '<dl class="detail"><dt>Basis</dt><dd>' + escapeHtml(row.pick_basis || "no basis published") + src + "</dd>" +
      "<dt>Market</dt><dd>" + market + "</dd>" +
      "<dt>Our line</dt><dd>" + own + "</dd>" +
      "<dt>Pred. mkt</dt><dd>" + (row.poly_reference ?
        fmtPct(row.poly_reference.p_a) + " / " + fmtPct(row.poly_reference.p_b) +
        " (prediction market, not a bookmaker)" +
        (row.poly_reference.url ? ' · <a href="' + escapeHtml(row.poly_reference.url) + '" rel="noopener">market</a>' : "")
        : "—") + "</dd>" +
      "<dt>Format</dt><dd>" + escapeHtml(row.best_of || "not sourced") + "</dd>" +
      "<dt>Match</dt><dd>" +
      (row.hotspawn_match_url ? '<a href="' + escapeHtml(row.hotspawn_match_url) + '" rel="noopener">Hotspawn</a>' : "Hotspawn") +
      (row.pick_page ? ' · <a href="' + escapeHtml(row.pick_page) + '">board row</a>' : "") +
      "</dd></dl>" + chips(row) + "</article>";
  }
  function markLocked() {
    var now = Date.now();
    document.querySelectorAll("[data-lock]").forEach(function (el) {
      var lock = Date.parse(el.getAttribute("data-lock"));
      if (lock && lock < now) {
        el.classList.add("locked");
        if (!el.querySelector(".locked-note")) {
          var note = document.createElement("p");
          note.className = "locked-note";
          note.textContent = "Locked — this pick can no longer be submitted.";
          el.appendChild(note);
        }
      }
    });
  }
  function ageBadge(iso) {
    var el = document.getElementById("generated");
    if (!el || !iso) { return; }
    var when = Date.parse(iso);
    if (!when) { return; }
    var hours = (Date.now() - when) / 3600000;
    var stamp = el.parentElement;
    if (hours > STALE_HOURS) {
      stamp.classList.add("stale");
      el.insertAdjacentHTML("afterend",
        ' <strong class="warn">stale by ' + hours.toFixed(1) + " h — check the boards before acting</strong>");
    }
  }
  function refresh() {
    fetch("data/picks.json", { cache: "no-store" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.json();
    }).then(function (data) {
      var baked = document.getElementById("generated");
      if (baked && data.generated_utc && data.generated_utc > baked.textContent.trim()) {
        var cards = document.getElementById("cards");
        if (cards && data.open) {
          cards.innerHTML = data.open.map(card).join("");
        }
        baked.textContent = data.generated_utc;
      }
      ageBadge((data && data.generated_utc) || (baked && baked.textContent.trim()));
      markLocked();
    }).catch(function () { markLocked(); });
  }
  document.addEventListener("DOMContentLoaded", function () {
    markLocked();
    refresh();
    setInterval(markLocked, 30000);
  });
}());
