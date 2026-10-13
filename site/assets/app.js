(() => {
  "use strict";

  const ALLOWED_SOURCE_HOSTS = new Set([
    "play.hotspawn.com", "www.hotspawn.com", "hotspawn.com",
    "thunderpick.io", "www.thunderpick.io",
    "polymarket.com", "www.polymarket.com", "gamma-api.polymarket.com",
    "docs.polymarket.com"
  ]);
  const body = document.body;
  const view = body.dataset.view || "overview";
  const snapshotPath = body.dataset.snapshot || "data/snapshot.json";

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function safeSourceUrl(value) {
    if (!value || typeof value !== "string") return null;
    try {
      const parsed = new URL(value, window.location.href);
      if (parsed.protocol !== "https:" || !ALLOWED_SOURCE_HOSTS.has(parsed.hostname.toLowerCase())) return null;
      return parsed.href;
    } catch (_) {
      return null;
    }
  }

  function externalLink(url, label, className) {
    const safe = safeSourceUrl(url);
    if (!safe) return null;
    const anchor = make("a", className || "", label);
    anchor.href = safe;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    return anchor;
  }

  function fmtNumber(value, digits = 1) {
    const number = Number(value);
    return Number.isFinite(number) ? number.toFixed(digits) : "";
  }

  function fmtDateTime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const format = new Intl.DateTimeFormat("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC"
    });
    return `${format.format(date)} UTC`;
  }

  function fmtSnapshotTime(value) {
    if (!value) return "No automated refresh timestamp (checked-in baseline).";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Snapshot timestamp unavailable.";
    return `Snapshot retrieved ${new Intl.DateTimeFormat("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone: "UTC"
    }).format(date)} UTC`;
  }

  function fmtObserved(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat("en-GB", {
      day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit",
      hourCycle: "h23", timeZone: "UTC"
    }).format(date) + " UTC";
  }

  function setNotice(node, text, tone = "neutral") {
    if (!node) return;
    node.className = `notice notice-${tone}`;
    node.textContent = text;
    node.hidden = false;
  }

  function addBlank(td, label = "Unverified") {
    const wrapper = make("div", "empty-value");
    const blank = make("span", "blank-value");
    blank.setAttribute("aria-label", "No verified value");
    wrapper.append(blank, make("span", "flag-pill", label));
    td.append(wrapper);
  }

  function appendFixtureCell(td, row) {
    const teams = make("span", "fixture-teams");
    teams.append(document.createTextNode(row.teamA || "Unknown team"));
    teams.append(make("span", "fixture-vs", "vs"));
    teams.append(document.createTextNode(row.teamB || "Unknown team"));
    td.append(teams);
    if (row.tournament) td.append(make("span", "fixture-meta", row.tournament));
    const normalized = fmtDateTime(row.startAtUtc);
    if (normalized) {
      td.append(make("span", "match-time", normalized));
      if (row.hotspawnTimeLabel) td.append(make("span", "match-time-sub", `Hotspawn label: ${row.hotspawnTimeLabel} · timezone not shown`));
    } else if (row.hotspawnTimeLabel) {
      td.append(make("span", "match-time", row.hotspawnTimeLabel));
      td.append(make("span", "match-time-sub", "Hotspawn display · timezone not shown"));
    } else {
      td.append(make("span", "match-time-sub", "Schedule not verified"));
    }
  }

  function appendBookmakerCell(td, bookmaker) {
    if (!bookmaker || !bookmaker.oddsA || !bookmaker.oddsB) {
      addBlank(td);
      return;
    }
    td.append(make("span", "cell-main", `${bookmaker.oddsA}  /  ${bookmaker.oddsB}`));
    td.append(make("span", "cell-sub", `${bookmaker.name || "Sportsbook"} · ${bookmaker.oddsFormat || "American"} · ${bookmaker.market || "Match Winner"}`));
    if (bookmaker.retrievedAtUtc) td.append(make("span", "cell-sub", `Retrieved ${fmtObserved(bookmaker.retrievedAtUtc)}`));
    else if (bookmaker.verifiedOn) td.append(make("span", "cell-sub", `Checked ${bookmaker.verifiedOn}`));
  }

  function appendProbabilityCell(td, bookmaker) {
    if (!bookmaker || !Number.isFinite(Number(bookmaker.noVigProbabilityA)) || !Number.isFinite(Number(bookmaker.noVigProbabilityB))) {
      addBlank(td);
      return;
    }
    td.append(make("span", "cell-main", `${fmtNumber(bookmaker.noVigProbabilityA)}%  /  ${fmtNumber(bookmaker.noVigProbabilityB)}%`));
    td.append(make("span", "cell-sub", "No-vig · team order matches fixture"));
  }

  function appendExchangeCell(td, exchange) {
    if (!exchange || !Number.isFinite(Number(exchange.priceA)) || !Number.isFinite(Number(exchange.priceB))) {
      addBlank(td);
      return;
    }
    td.append(make("span", "cell-main", `${fmtNumber(exchange.priceA)}¢  /  ${fmtNumber(exchange.priceB)}¢`));
    td.append(make("span", "cell-sub", `${exchange.name || "Prediction market"} · exchange, not sportsbook`));
    if (exchange.sourceUpdatedAt) td.append(make("span", "cell-sub", `Source update ${fmtObserved(exchange.sourceUpdatedAt)}`));
    else if (exchange.retrievedAtUtc) td.append(make("span", "cell-sub", `Retrieved ${fmtObserved(exchange.retrievedAtUtc)}`));
  }

  function appendVerificationCell(td, row) {
    const verifiedCount = Number(Boolean(row.bookmaker)) + Number(Boolean(row.exchange));
    const status = make("span", `status-pill ${verifiedCount ? "verified" : "partial"}`, verifiedCount ? `${verifiedCount} source${verifiedCount === 1 ? "" : "s"} checked` : "Needs verification");
    td.append(status);

    const links = make("div", "source-links");
    const fixtureLink = externalLink(row.sources && row.sources.fixtureUrl, "Hotspawn fixture");
    if (fixtureLink) links.append(fixtureLink);
    const bookLink = row.bookmaker && externalLink(row.bookmaker.sourceUrl, row.bookmaker.name || "Sportsbook");
    if (bookLink) links.append(bookLink);
    const exchangeLink = row.exchange && externalLink(row.exchange.sourceUrl, "Polymarket exchange");
    if (exchangeLink) links.append(exchangeLink);
    if (links.childNodes.length) td.append(links);
    else td.append(make("span", "cell-sub", "Official fixture source unavailable"));

    const flags = Array.isArray(row.flags) ? row.flags.filter(Boolean) : [];
    if (flags.length) {
      const review = make("div", "row-review");
      const details = make("details");
      details.append(make("summary", "", `Review note${flags.length === 1 ? "" : "s"} (${flags.length})`));
      const list = make("ul");
      for (const flag of flags) list.append(make("li", "", flag));
      details.append(list);
      review.append(details);
      td.append(review);
    }
  }

  function makeMatchRow(row) {
    const tr = make("tr", Array.isArray(row.flags) && row.flags.length ? "row-flagged" : "");
    const fixture = make("td");
    const book = make("td");
    const probability = make("td");
    const exchange = make("td");
    const verification = make("td");
    appendFixtureCell(fixture, row);
    appendBookmakerCell(book, row.bookmaker);
    appendProbabilityCell(probability, row.bookmaker);
    appendExchangeCell(exchange, row.exchange);
    appendVerificationCell(verification, row);
    tr.append(fixture, book, probability, exchange, verification);
    return tr;
  }

  function renderTable(tbody, rows) {
    if (!tbody) return;
    tbody.replaceChildren();
    const fragment = document.createDocumentFragment();
    for (const row of rows) fragment.append(makeMatchRow(row));
    tbody.append(fragment);
  }

  function sourceName(source) {
    const labels = {
      CS2: "Counter-Strike 2",
      LoL: "League of Legends"
    };
    return labels[source] || source || "Match category";
  }

  function countByGame(snapshot, game) {
    return (snapshot.matches || []).filter((row) => row.game === game).length;
  }

  function reportCoverage(snapshot) {
    const coverage = snapshot.coverage || {};
    const games = coverage.byGame || {};
    const totals = Object.values(games).map((item) => item && item.statedMatchesThisWeek).filter((item) => Number.isFinite(Number(item)));
    const expected = totals.length ? totals.reduce((sum, item) => sum + Number(item), 0) : null;
    const listed = Number(coverage.listedMatches || (snapshot.matches || []).length);
    if (expected === null) return `Coverage: ${listed} fixture row${listed === 1 ? "" : "s"}; full lobby count not verified.`;
    return `Coverage: ${listed} parsed of ${expected} matches reported this week.`;
  }

  function renderStatus(snapshot) {
    const chip = document.getElementById("snapshot-status");
    if (chip) {
      const complete = Boolean(snapshot.coverage && snapshot.coverage.isComplete);
      chip.className = `snapshot-chip ${complete ? "is-good" : "is-review"}`;
      chip.replaceChildren(make("span", "status-dot"));
      chip.append(document.createTextNode(complete ? "Complete fixture coverage" : "Partial snapshot · review flags"));
    }
    const status = snapshot.snapshotStatus || "unknown";
    const listed = Number(snapshot.coverage && snapshot.coverage.listedMatches || (snapshot.matches || []).length);
    const expectedRows = Object.values((snapshot.coverage && snapshot.coverage.byGame) || {}).reduce((sum, item) => {
      const count = item && item.statedMatchesThisWeek;
      return sum + (Number.isFinite(Number(count)) ? Number(count) : 0);
    }, 0);
    const notice = document.getElementById("snapshot-notice") || document.getElementById("category-notice") || document.getElementById("sources-notice");
    if (status === "current-complete") {
      setNotice(notice, `Current automated snapshot. ${listed} fixtures were parsed and the Hotspawn weekly counts matched. Unverified market cells, if any, are still blank and flagged.`, "success");
    } else if (status === "current-partial") {
      const expectedText = expectedRows ? ` Hotspawn reports ${expectedRows} fixtures this week; ${listed} were parsed.` : " Full listing coverage was not verified.";
      setNotice(notice, `Latest refresh is partial.${expectedText} The data is not presented as a complete lobby; unmatched values remain blank and flagged.`, "review");
    } else {
      setNotice(notice, "This is a checked-in baseline snapshot, not a completed live refresh. The baseline is intentionally partial; the scheduled refresh must succeed before the listing is considered complete. Unknown values are blank and flagged.", "review");
    }
    const updated = document.getElementById("snapshot-updated");
    if (updated) updated.textContent = fmtSnapshotTime(snapshot.generatedAt);
    const coverage = document.getElementById("coverage-meta");
    if (coverage) coverage.textContent = reportCoverage(snapshot);
  }

  function renderOverview(snapshot) {
    renderStatus(snapshot);
    const rows = Array.isArray(snapshot.matches) ? snapshot.matches : [];
    const bookCount = rows.filter((row) => row.bookmaker).length;
    const exchangeCount = rows.filter((row) => row.exchange).length;
    const reviewCount = rows.filter((row) => !row.bookmaker || !row.exchange || (row.flags && row.flags.length)).length;
    const stats = document.querySelectorAll("#overview-stats .stat-card .stat-value");
    [rows.length, bookCount, exchangeCount, reviewCount].forEach((value, index) => {
      if (stats[index]) stats[index].textContent = String(value);
    });
    const cs2 = countByGame(snapshot, "CS2");
    const lol = countByGame(snapshot, "LoL");
    const byGame = (snapshot.coverage && snapshot.coverage.byGame) || {};
    const cs2Total = byGame.CS2 && byGame.CS2.statedMatchesThisWeek;
    const lolTotal = byGame.LoL && byGame.LoL.statedMatchesThisWeek;
    const cs2Count = document.getElementById("cs2-count");
    const lolCount = document.getElementById("lol-count");
    if (cs2Count) cs2Count.textContent = cs2Total ? `${cs2} parsed · ${cs2Total} reported this week` : `${cs2} fixture row${cs2 === 1 ? "" : "s"} in snapshot`;
    if (lolCount) lolCount.textContent = lolTotal ? `${lol} parsed · ${lolTotal} reported this week` : `${lol} fixture row${lol === 1 ? "" : "s"} in snapshot`;

    const tbody = document.getElementById("overview-table-body");
    renderTable(tbody, rows.slice(0, 8));
    const empty = document.getElementById("overview-empty");
    if (empty) empty.hidden = rows.length > 0;
    if (tbody && rows.length === 0 && empty) tbody.replaceChildren();

    const auditItems = Array.isArray(snapshot.auditItems) ? snapshot.auditItems : [];
    const section = document.getElementById("audit-preview-section");
    if (section && auditItems.length) {
      section.hidden = false;
      renderAuditCards(document.getElementById("overview-audit"), auditItems.slice(0, 2));
    }
  }

  function renderCategory(snapshot) {
    renderStatus(snapshot);
    const game = body.dataset.game || "";
    const allRows = (Array.isArray(snapshot.matches) ? snapshot.matches : []).filter((row) => row.game === game);
    const summary = document.getElementById("category-summary");
    if (summary) {
      const gameCoverage = snapshot.coverage && snapshot.coverage.byGame && snapshot.coverage.byGame[game];
      const expected = gameCoverage && gameCoverage.statedMatchesThisWeek;
      summary.textContent = expected
        ? `${allRows.length} parsed fixture${allRows.length === 1 ? "" : "s"} · ${expected} reported this week · ${allRows.filter((row) => row.bookmaker).length} with a verified sportsbook line`
        : `${allRows.length} fixture row${allRows.length === 1 ? "" : "s"} in the current snapshot · ${allRows.filter((row) => row.bookmaker).length} with a verified sportsbook line`;
    }
    const tbody = document.getElementById("category-table-body");
    const empty = document.getElementById("category-empty");
    const filterEmpty = document.getElementById("category-filter-empty");
    const search = document.getElementById("match-search");
    const renderFiltered = () => {
      const term = search ? search.value.trim().toLowerCase() : "";
      const rows = !term ? allRows : allRows.filter((row) => `${row.teamA || ""} ${row.teamB || ""} ${row.tournament || ""}`.toLowerCase().includes(term));
      renderTable(tbody, rows);
      if (empty) empty.hidden = allRows.length !== 0;
      if (filterEmpty) filterEmpty.hidden = !allRows.length || rows.length !== 0;
      if (tbody && allRows.length === 0 && empty) tbody.replaceChildren();
    };
    renderFiltered();
    if (search) search.addEventListener("input", renderFiltered);
  }

  function renderAuditCards(container, items) {
    if (!container) return;
    container.replaceChildren();
    for (const item of items) {
      const card = make("article", "audit-card");
      const head = make("div", "audit-card-head");
      head.append(make("h3", "", item.title || "Review item"));
      head.append(make("span", "status-pill audit-status", item.status || item.severity || "review"));
      card.append(head);
      card.append(make("p", "", item.details || "No additional details were supplied."));
      const sources = make("div", "audit-sources");
      for (const [index, url] of (item.sources || []).entries()) {
        const link = externalLink(url, `Official source ${index + 1}`);
        if (link) sources.append(link);
      }
      if (sources.childNodes.length) card.append(sources);
      container.append(card);
    }
  }

  function renderSources(snapshot) {
    renderStatus(snapshot);
    const coverage = snapshot.coverage || {};
    const coverageHost = document.getElementById("source-coverage");
    if (coverageHost) {
      coverageHost.replaceChildren();
      const byGame = coverage.byGame || {};
      const games = Object.keys(byGame);
      if (!games.length) {
        for (const game of ["CS2", "LoL"]) {
          const count = countByGame(snapshot, game);
          const card = make("article", "coverage-card");
          card.append(make("h3", "", sourceName(game)));
          const dl = make("dl");
          dl.append(make("dt", "", "Rows in baseline"), make("dd", "", String(count)));
          dl.append(make("dt", "", "Full lobby count"), make("dd", "", "Not verified"));
          dl.append(make("dt", "", "Coverage"), make("dd", "", "Partial baseline"));
          card.append(dl);
          coverageHost.append(card);
        }
      } else {
        for (const game of games) {
          const item = byGame[game];
          const card = make("article", "coverage-card");
          card.append(make("h3", "", sourceName(game)));
          const dl = make("dl");
          dl.append(make("dt", "", "Reported this week"), make("dd", "", item.statedMatchesThisWeek == null ? "Not supplied" : String(item.statedMatchesThisWeek)));
          dl.append(make("dt", "", "Parsed fixture cards"), make("dd", "", String(item.parsedFixtures || 0)));
          dl.append(make("dt", "", "Unparsed match links"), make("dd", "", String(item.unparsedMatchLinks || 0)));
          dl.append(make("dt", "", "Coverage"), make("dd", "", item.isComplete ? "Complete" : "Partial"));
          card.append(dl);
          const source = externalLink(item.sourceUrl, "Open official listing");
          if (source) card.append(source);
          coverageHost.append(card);
        }
      }
      const snapshotCard = make("article", "coverage-card");
      snapshotCard.append(make("h3", "", "Snapshot totals"));
      const dl = make("dl");
      dl.append(make("dt", "", "Listed fixtures"), make("dd", "", String(coverage.listedMatches ?? (snapshot.matches || []).length)));
      dl.append(make("dt", "", "Sportsbook lines"), make("dd", "", String(coverage.bookmakerPricedMatches ?? (snapshot.matches || []).filter((row) => row.bookmaker).length)));
      dl.append(make("dt", "", "Exchange references"), make("dd", "", String(coverage.exchangePricedMatches ?? (snapshot.matches || []).filter((row) => row.exchange).length)));
      dl.append(make("dt", "", "Status"), make("dd", "", snapshot.snapshotStatus || "Unknown"));
      snapshotCard.append(dl);
      coverageHost.append(snapshotCard);
    }

    const sourceHost = document.getElementById("source-list");
    if (sourceHost) {
      sourceHost.replaceChildren();
      for (const source of snapshot.sources || []) {
        const item = make("article", "source-item");
        item.append(make("span", "source-item-icon", "↗"));
        const content = make("div");
        content.append(make("h3", "", source.name || source.id || "Source"));
        content.append(make("p", "", source.role || "Source role not recorded."));
        const link = externalLink(source.url, source.url);
        if (link) content.append(link);
        item.append(content);
        sourceHost.append(item);
      }
    }

    const audits = Array.isArray(snapshot.auditItems) ? snapshot.auditItems : [];
    const auditHost = document.getElementById("audit-list");
    renderAuditCards(auditHost, audits);
    const empty = document.getElementById("audit-empty");
    if (empty) empty.hidden = audits.length > 0;
    const count = document.getElementById("audit-count");
    if (count) count.textContent = `${audits.length} item${audits.length === 1 ? "" : "s"}`;
  }

  async function init() {
    try {
      const response = await fetch(snapshotPath, { cache: "no-store" });
      if (!response.ok) throw new Error(`Snapshot request returned ${response.status}`);
      const snapshot = await response.json();
      if (!snapshot || !Array.isArray(snapshot.matches)) throw new Error("Snapshot format is not recognized.");
      if (view === "overview") renderOverview(snapshot);
      else if (view === "category") renderCategory(snapshot);
      else if (view === "sources") renderSources(snapshot);
    } catch (error) {
      const notice = document.getElementById("snapshot-notice") || document.getElementById("category-notice") || document.getElementById("sources-notice");
      setNotice(notice, `Snapshot data could not be loaded: ${error.message}. Check the data URL or the latest deployment.`, "error");
      const chip = document.getElementById("snapshot-status");
      if (chip) {
        chip.className = "snapshot-chip is-error";
        chip.replaceChildren(make("span", "status-dot"), document.createTextNode("Snapshot unavailable"));
      }
    }
  }

  init();
})();
