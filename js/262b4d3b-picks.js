/* Current landing view: fixture identity comes from the newest live/ Hotspawn CSV.
 * No raw snapshot or Hotspawn crowd fields are fetched. Probabilities fail closed. */
(function (root) {
  'use strict';

  const MAX_SNAPSHOT_AGE_MS = 6 * 60 * 60 * 1000;
  const MAX_MARKET_AGE_MS = 6 * 60 * 60 * 1000;
  const MAX_RATING_AGE_MS = 14 * 24 * 60 * 60 * 1000;
  const OWN_LINE_SCALE = 400;
  const NO_PICK_MARGIN_PP = 2;
  const PM_SERIES_SCOPE = Object.freeze({
    // Re-read 2026-10-14 ~08:39Z: this event has a separate Series Lines > Moneyline
    // market whose rules resolve on the overall match winner. The live CSV stores only
    // a composite event URL, so admit only the exact manually checked 07:58 capture; any
    // later quote remains withheld until its submarket identity is recorded/checked again.
    '1079438': Object.freeze({slug: 'cs2-ast10-sashi-2026-10-14', readUTC: '2026-10-14T07:58:31Z', a: 84.5, b: 15.5})
  });

  function parseCSV(text) {
    if (typeof text !== 'string') throw new Error('CSV evidence is not text');
    const source = text.replace(/^\uFEFF/, '');
    const records = [];
    let record = [];
    let field = '';
    let quoted = false;
    for (let i = 0; i < source.length; i += 1) {
      const char = source[i];
      if (char === '"') {
        if (quoted && source[i + 1] === '"') {
          field += '"';
          i += 1;
        } else {
          quoted = !quoted;
        }
      } else if (char === ',' && !quoted) {
        record.push(field);
        field = '';
      } else if ((char === '\n' || char === '\r') && !quoted) {
        if (char === '\r' && source[i + 1] === '\n') i += 1;
        record.push(field);
        if (record.some(value => value !== '')) records.push(record);
        record = [];
        field = '';
      } else {
        field += char;
      }
    }
    if (quoted) throw new Error('Unclosed quoted CSV field');
    if (field !== '' || record.length) {
      record.push(field);
      if (record.some(value => value !== '')) records.push(record);
    }
    if (!records.length) throw new Error('CSV evidence has no header');
    const headers = records.shift().map(value => value.trim());
    if (!headers.length || headers.some(value => !value) || new Set(headers).size !== headers.length) {
      throw new Error('CSV evidence has invalid or duplicate headers');
    }
    return records.map((values, index) => {
      if (values.length !== headers.length) throw new Error(`CSV row ${index + 2} has the wrong number of fields`);
      return Object.fromEntries(headers.map((header, column) => [header, values[column]]));
    });
  }

  function parseTime(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(value)) return NaN;
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  }

  function parseDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d\d-\d\d$/.test(value)) return NaN;
    const parsed = Date.parse(`${value}T00:00:00Z`);
    return Number.isFinite(parsed) ? parsed : NaN;
  }

  function numeric(value) {
    if (value == null || value === '' || typeof value === 'boolean') return NaN;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : NaN;
  }

  function probabilityPair(a, b, tolerance = 0.25) {
    return Number.isFinite(a) && Number.isFinite(b) && a >= 0 && a <= 100 && b >= 0 && b <= 100 &&
      Math.abs(a + b - 100) <= tolerance;
  }

  function safeURL(value) {
    try {
      const parsed = new URL(value);
      return parsed.protocol === 'https:' && !parsed.username && !parsed.password ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  function hasHost(url, domain) {
    return Boolean(url && (url.hostname === domain || url.hostname.endsWith(`.${domain}`)));
  }

  function officialVrsDate(value) {
    const url = safeURL(value);
    if (!url) return null;
    let match = null;
    if (url.hostname === 'raw.githubusercontent.com') {
      match = /^\/ValveSoftware\/counter-strike_regional_standings\/[^/]+\/live\/(\d{4})\/standings_global_(\d{4})_(\d{2})_(\d{2})\.md$/.exec(url.pathname);
    } else if (url.hostname === 'github.com') {
      match = /^\/ValveSoftware\/counter-strike_regional_standings\/blob\/[0-9a-f]{40}\/live\/(\d{4})\/standings_global_(\d{4})_(\d{2})_(\d{2})\.md$/.exec(url.pathname);
    }
    if (!match || match[1] !== match[2]) return null;
    return `${match[2]}-${match[3]}-${match[4]}`;
  }

  function slugContainsTeam(slug, team) {
    const tokenize = value => String(value || '').toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').split('-').filter(Boolean);
    const haystack = tokenize(slug);
    const needle = tokenize(team);
    if (!needle.length) return false;
    return haystack.some((_, start) => needle.every((part, offset) => haystack[start + offset] === part));
  }

  function validHltvMatch(value, teamA, teamB) {
    const url = safeURL(value);
    if (!url || !hasHost(url, 'hltv.org') || !/^\/matches\/\d+\//.test(url.pathname)) return false;
    const slug = decodeURIComponent(url.pathname.split('/').filter(Boolean).pop() || '');
    return slugContainsTeam(slug, teamA) && slugContainsTeam(slug, teamB);
  }

  function stableVrsURL(row) {
    const source = String(row.vrs_url || '');
    const asOf = officialVrsDate(source);
    if (asOf === '2026-10-05') {
      return 'https://github.com/ValveSoftware/counter-strike_regional_standings/blob/eec4853d7bcf0f1f7efe7f0d901234bef7e98b75/live/2026/standings_global_2026_10_05.md';
    }
    return source;
  }

  function expectedWinner(a, b, teamA, teamB, pick) {
    const noPick = !pick || /^no confident pick$/i.test(pick);
    if (Math.abs(a - b) < 0.01) return {valid: noPick, pick: null};
    const favored = a > b ? teamA : teamB;
    if (noPick) return {valid: Math.abs(a - b) < NO_PICK_MARGIN_PP, pick: null};
    return {valid: pick === favored, pick: favored};
  }

  function ageFresh(value, now, maxAge) {
    const stamp = parseTime(value);
    return Number.isFinite(stamp) && stamp <= now && now - stamp <= maxAge;
  }

  function marketAssessment(row, now) {
    const book = String(row.ext_bookmaker || '');
    if (!book) return {valid: false, reason: ''};
    const source = safeURL(row.ext_url);
    if (!source) return {valid: false, reason: 'Market source URL is missing or unsafe.'};
    if (!ageFresh(row.ext_observed_utc, now, MAX_MARKET_AGE_MS)) {
      return {valid: false, reason: 'Market observation is older than six hours or has no valid UTC read time.'};
    }

    let a;
    let b;
    let kind;
    let label;
    let details;
    if (/pinnacle/i.test(book)) {
      if (!hasHost(source, 'pinnacle.com')) return {valid: false, reason: 'Pinnacle source host could not be confirmed.'};
      const oddsA = numeric(row.ext_odds_a);
      const oddsB = numeric(row.ext_odds_b);
      if (!(oddsA > 1 && oddsB > 1)) return {valid: false, reason: 'Pinnacle quote is not a finite two-sided decimal line.'};
      const rawA = 100 / oddsA;
      const rawB = 100 / oddsB;
      const total = rawA + rawB;
      if (!(total > 0)) return {valid: false, reason: 'Pinnacle implied-price denominator is invalid.'};
      a = 100 * rawA / total;
      b = 100 - a;
      kind = 'market';
      label = 'Direct bookmaker · Pinnacle (de-vigged)';
      details = `Pinnacle decimal odds ${oddsA.toFixed(3)} / ${oddsB.toFixed(3)}; probability recalculated without the overround. The available source URL is generic, so the row remains flagged FL-12 for missing per-match deep link.`;
    } else if (/egamersworld/i.test(book)) {
      if (!hasHost(source, 'egamersworld.com') || !/^\/counterstrike\/match\//.test(source.pathname)) {
        return {valid: false, reason: 'EGamersWorld source is not a per-match Counter-Strike page.'};
      }
      const egwSlug = decodeURIComponent(source.pathname.split('/').filter(Boolean).pop() || '');
      if (!slugContainsTeam(egwSlug, row.team_a) || !slugContainsTeam(egwSlug, row.team_b)) {
        return {valid: false, reason: 'EGamersWorld page slug does not confirm both exact fixture team names.'};
      }
      const oddsA = numeric(row.ext_odds_a);
      const oddsB = numeric(row.ext_odds_b);
      if (!(oddsA > 1.01 && oddsA <= 40 && oddsB > 1.01 && oddsB <= 40)) {
        return {valid: false, reason: 'EGamersWorld price is not a finite two-sided decimal pair.'};
      }
      if (Math.abs(oddsA - 1.8) < 0.0001 && Math.abs(oddsB - 1.8) < 0.0001) {
        return {valid: false, reason: 'EGamersWorld 1.80/1.80 placeholder is not a usable quote.'};
      }
      const rawA = 100 / oddsA;
      const rawB = 100 / oddsB;
      const total = rawA + rawB;
      a = 100 * rawA / total;
      b = 100 - a;
      kind = 'market';
      label = 'Secondary bookmaker prices · EGamersWorld aggregate (de-vigged)';
      details = `Per-match EGamersWorld decimal prices ${oddsA.toFixed(3)} / ${oddsB.toFixed(3)}; probability recalculated without the overround. Verify the underlying book on the linked page.`;
    } else if (/polymarket/i.test(book)) {
      const requiredScope = PM_SERIES_SCOPE[String(row.match_id || '')];
      if (!requiredScope || !source.pathname.includes(requiredScope.slug)) {
        return {valid: false, reason: 'Prediction-market contract scope is not verified for this fixture; price withheld.'};
      }
      const impliedA = numeric(row.ext_p_a_pct);
      const impliedB = numeric(row.ext_p_b_pct);
      if (!probabilityPair(impliedA, impliedB)) return {valid: false, reason: 'Prediction-market implied prices are not a complementary two-sided pair.'};
      if (row.ext_observed_utc !== requiredScope.readUTC || Math.abs(impliedA - requiredScope.a) > 0.01 || Math.abs(impliedB - requiredScope.b) > 0.01) {
        return {valid: false, reason: 'This Polymarket event URL does not identify a submarket for a later quote; only the exact manually checked capture is admitted.'};
      }
      a = impliedA;
      b = impliedB;
      kind = 'prediction-market';
      label = 'Polymarket · verified series moneyline (not a bookmaker; not de-vigged)';
      details = 'Series Moneyline submarket; implied prices are shown as read, not de-vigged.';
    } else {
      return {valid: false, reason: 'External source type is not approved by this landing view; price withheld.'};
    }

    const storedA = numeric(row.ext_p_a_pct);
    const storedB = numeric(row.ext_p_b_pct);
    const finalA = numeric(row.final_p_a_pct);
    const finalB = numeric(row.final_p_b_pct);
    if (!probabilityPair(storedA, storedB) || !probabilityPair(finalA, finalB) ||
        Math.abs(a - storedA) > 0.35 || Math.abs(b - storedB) > 0.35 ||
        Math.abs(a - finalA) > 0.35 || Math.abs(b - finalB) > 0.35) {
      return {valid: false, reason: 'Captured market values do not reproduce the published two-sided probability pair.'};
    }
    const decision = expectedWinner(a, b, row.team_a, row.team_b, String(row.pick || ''));
    if (!decision.valid) return {valid: false, reason: 'Published pick does not match the market favorite or its no-pick threshold.'};
    return {
      valid: true,
      kind,
      label,
      details,
      a,
      b,
      pick: decision.pick,
      sourceURL: source.href,
      capturedUTC: row.ext_observed_utc,
      oddsA: numeric(row.ext_odds_a),
      oddsB: numeric(row.ext_odds_b),
      overround: numeric(row.ext_overround_pct),
      reason: ''
    };
  }

  function formatEvidence(row, execData, execFresh, execById) {
    if (!execFresh || !execData || !execById) {
      return {valid: false, reason: 'No fresh cross-board HLTV format evidence; series estimate withheld.'};
    }
    const matches = execById.get(String(row.match_id)) || [];
    if (matches.length !== 1) {
      return {valid: false, reason: 'No unique exact-ID format record; series estimate withheld.'};
    }
    const evidence = matches[0];
    const source = safeURL(evidence.best_of_source);
    const sameOrder = String(evidence.team_a || '').trim().toLowerCase() === String(row.team_a || '').trim().toLowerCase() &&
      String(evidence.team_b || '').trim().toLowerCase() === String(row.team_b || '').trim().toLowerCase();
    if (!sameOrder || evidence.lock_utc !== row.lock_utc || evidence.kickoff_utc !== row.start_utc) {
      return {valid: false, reason: 'Cross-board format record does not match exact team order, kickoff, and lock; series estimate withheld.', sourceURL: source && source.href};
    }
    const bestOf = /^BO([135])$/.exec(String(evidence.best_of || ''));
    if (!bestOf) return {valid: false, reason: 'Series format is not a supported BO1/BO3/BO5 value; estimate withheld.', sourceURL: source && source.href};
    if (!validHltvMatch(evidence.best_of_source, row.team_a, row.team_b)) {
      return {valid: false, reason: 'HLTV format link does not identify both exact Hotspawn team names; alias/identity is unverified, so estimate withheld.', sourceURL: source && source.href};
    }
    return {valid: true, bestOf: Number(bestOf[1]), url: evidence.best_of_source, execGeneratedUTC: execData.generated_utc};
  }

  function vrsModel(row, format, now) {
    if (!format || !format.valid) return {valid: false, reason: format && format.reason ? format.reason : 'No fresh same-fixture HLTV best-of source; series estimate withheld.'};
    const asOf = parseDate(row.vrs_as_of);
    const urlDate = officialVrsDate(row.vrs_url);
    const pointsA = numeric(row.vrs_points_a);
    const pointsB = numeric(row.vrs_points_b);
    if (!urlDate || urlDate !== row.vrs_as_of || !Number.isFinite(asOf) || asOf > now || now - asOf > MAX_RATING_AGE_MS ||
        !(pointsA > 0) || !(pointsB > 0)) {
      return {valid: false, reason: 'A two-sided, current official Valve rating is not verified.'};
    }
    const mapA = 1 / (1 + 10 ** ((pointsB - pointsA) / OWN_LINE_SCALE));
    const publishedOwnA = numeric(row.own_p_a_pct);
    const publishedOwnB = numeric(row.own_p_b_pct);
    if (!probabilityPair(publishedOwnA, publishedOwnB) || Math.abs(100 * mapA - publishedOwnA) > 0.35 ||
        Math.abs((100 - 100 * mapA) - publishedOwnB) > 0.35) {
      return {valid: false, reason: 'The official-rating inputs do not reproduce the stored VRS line.'};
    }
    const p = mapA;
    const seriesA = format.bestOf === 1 ? p : format.bestOf === 3 ? p * p * (3 - 2 * p) :
      p ** 3 * (10 - 15 * p + 6 * p * p);
    const a = 100 * seriesA;
    const b = 100 - a;
    const pick = Math.abs(a - b) < NO_PICK_MARGIN_PP ? null : (a > b ? row.team_a : row.team_b);
    return {
      valid: true,
      kind: 'model',
      label: `Own research estimate · VRS points → BO${format.bestOf} series`,
      details: `Project assumption: 400-point per-map logistic, then an independent-map BO${format.bestOf} transform. Uncalibrated; not an official forecast.`,
      a,
      b,
      pick,
      sourceURL: stableVrsURL(row),
      formatURL: format.url,
      ratingAsOf: row.vrs_as_of,
      format,
      reason: ''
    };
  }

  function evaluateRow(row, context) {
    const lock = parseTime(row.lock_utc);
    if (!Number.isFinite(lock)) return {row, active: false, status: 'unknown-time', primary: null, flags: ['Lock time missing or invalid.']};
    if (lock <= context.now) return {row, active: false, status: 'locked', primary: null, flags: []};

    if (!context.snapshotFresh) {
      return {row, active: true, status: 'stale-snapshot', primary: null,
        flags: ['Latest Hotspawn fixture snapshot is older than six hours or has an invalid/future UTC timestamp.']};
    }

    const market = marketAssessment(row, context.now);
    const format = formatEvidence(row, context.execData, context.execFresh, context.execById);
    const model = vrsModel(row, format, context.now);
    const flags = String(row.flags || '').split(';').map(value => value.trim()).filter(Boolean);
    if (market.reason) flags.push(market.reason);
    if (!market.valid && model.reason && String(row.ext_bookmaker || '')) flags.push(model.reason);

    if (market.valid) {
      return {row, active: true, status: 'priced', primary: market, market, model: model.valid ? model : null,
        formatEvidence: format, flags: [...new Set(flags)]};
    }
    if (model.valid) {
      return {row, active: true, status: 'research-model', primary: model, market: null, rejectedMarket: market.reason,
        model, formatEvidence: format, flags: [...new Set(flags)]};
    }
    if (market.reason) flags.push(market.reason);
    if (model.reason) flags.push(model.reason);
    return {row, active: true, status: 'unresolved', primary: null, market: null, model: null, formatEvidence: format,
      flags: [...new Set(flags)]};
  }

  function buildView(csvRows, meta, execData, now = Date.now()) {
    if (!Array.isArray(csvRows) || !csvRows.length) throw new Error('No Hotspawn fixture rows in the latest live snapshot');
    if (!meta || !Number.isFinite(numeric(meta.fixtures)) || numeric(meta.fixtures) !== csvRows.length) {
      throw new Error('Hotspawn snapshot metadata count does not match the fixture CSV');
    }
    const ids = new Set();
    for (const row of csvRows) {
      const id = String(row.match_id || '').trim();
      if (!id || ids.has(id) || !String(row.team_a || '').trim() || !String(row.team_b || '').trim()) {
        throw new Error('Fixture CSV contains a missing/duplicate ID or team name');
      }
      ids.add(id);
      const hotspawn = safeURL(row.hotspawn_url);
      if (!hotspawn || !hasHost(hotspawn, 'hotspawn.com')) throw new Error(`Fixture ${id} has no official Hotspawn source URL`);
    }
    const captureTime = parseTime(meta.generated_utc);
    const snapshotFresh = Number.isFinite(captureTime) && captureTime <= now && now - captureTime <= MAX_SNAPSHOT_AGE_MS;
    const execTime = execData && parseTime(execData.generated_utc);
    const execFresh = Number.isFinite(execTime) && execTime <= now && now - execTime <= MAX_SNAPSHOT_AGE_MS;
    const execById = new Map();
    if (execFresh && Array.isArray(execData.open)) {
      for (const record of execData.open) {
        const id = String(record.fixture_id || '');
        if (!execById.has(id)) execById.set(id, []);
        execById.get(id).push(record);
      }
    }
    const context = {now, snapshotFresh, execData: execFresh ? execData : null, execFresh, execById};
    const evaluated = csvRows.map(row => evaluateRow(row, context));
    const active = evaluated.filter(item => item.active)
      .sort((left, right) => (parseTime(left.row.start_utc) || Infinity) - (parseTime(right.row.start_utc) || Infinity));
    const unknownTime = evaluated.filter(item => item.status === 'unknown-time').length;
    const marketCount = active.filter(item => item.primary && item.primary.kind !== 'model').length;
    const modelCount = active.filter(item => item.primary && item.primary.kind === 'model').length;
    const unresolvedCount = active.length - marketCount - modelCount;
    return {
      generatedUTC: meta.generated_utc,
      generatedAt: captureTime,
      snapshotFresh,
      execGeneratedUTC: execFresh ? execData.generated_utc : '',
      execFresh,
      totalFixtures: csvRows.length,
      active,
      unknownTime,
      marketCount,
      modelCount,
      unresolvedCount,
      lockedOrPast: csvRows.length - active.length - unknownTime
    };
  }

  function formatUTC(value) {
    const time = parseTime(value);
    if (!Number.isFinite(time)) return 'unverified UTC';
    return new Date(time).toISOString().replace('.000Z', 'Z');
  }

  function relativeAge(value, now = Date.now()) {
    const stamp = parseTime(value);
    if (!Number.isFinite(stamp) || stamp > now) return 'time unverified';
    const minutes = Math.floor((now - stamp) / 60000);
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return `${hours} h ${rest} min ago`;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {parseCSV, parseTime, numeric, probabilityPair, safeURL, officialVrsDate, validHltvMatch, stableVrsURL, marketAssessment,
      formatEvidence, vrsModel, evaluateRow, buildView, formatUTC, relativeAge, PM_SERIES_SCOPE};
  }
  if (typeof document === 'undefined') return;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function appendLink(container, url, label) {
    const safe = safeURL(url);
    const internal = typeof url === 'string' && /^(?:[a-z0-9_-]+\/)*[a-z0-9_.-]+\.html(?:#[a-z0-9_-]+)?$/i.test(url);
    if (!safe && !internal) return;
    const link = element('a', label);
    link.href = safe ? safe.href : url;
    if (safe) {
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
    }
    container.append(link);
  }

  async function readText(url) {
    const response = await fetch(`${url}?fresh=${Date.now()}`, {cache: 'no-store'});
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.text();
  }

  async function loadData() {
    const [csvText, metaText, execText] = await Promise.all([
      readText('live/data/slate.csv'),
      readText('live/data/snapshot_meta.json'),
      readText('exec/data/picks.json').catch(() => '')
    ]);
    const meta = JSON.parse(metaText);
    let execData = null;
    if (execText) {
      try { execData = JSON.parse(execText); } catch (_) { execData = null; }
    }
    return {rows: parseCSV(csvText), meta, execData};
  }

  function formatPercent(value) {
    return `${value.toFixed(1)}%`;
  }

  function appendProbabilityBar(container, name, value, side) {
    const cell = element('div', null, 'probability-cell');
    cell.append(element('span', name, 'probability-name'), element('b', formatPercent(value)));
    const track = element('div', null, `probability-track ${side}`);
    track.setAttribute('role', 'img');
    track.setAttribute('aria-label', `${name}: ${formatPercent(value)}`);
    const fill = element('span');
    fill.style.width = `${Math.max(0, Math.min(100, value))}%`;
    track.append(fill);
    cell.append(track);
    container.append(cell);
  }

  function renderCard(item, now) {
    const row = item.row;
    const primary = item.primary;
    const isUnresolved = !primary;
    const card = element('article', null, `match ${isUnresolved ? 'review' : 'active'}`);
    card.id = `match-${row.match_id}`;
    card.dataset.fixtureId = row.match_id;
    const topline = element('div', null, 'match-topline');
    topline.append(element('span', `Tier ${String(row.tier || 'unverified').toUpperCase()}`, 'badge'));
    topline.append(element('span', row.competition || 'Competition unverified', 'small'));
    topline.append(element('span', `Hotspawn ID ${row.match_id}`, 'small'));
    card.append(topline);
    card.append(element('h2', `${row.team_a} vs ${row.team_b}`));
    card.append(element('p', `Starts ${formatUTC(row.start_utc)} · locks ${formatUTC(row.lock_utc)}`, 'small'));

    if (primary) {
      const call = primary.pick ? `Pick: ${primary.pick}` : 'No lean · within the published no-pick threshold';
      card.append(element('p', call, 'pick-call'));
      const probabilities = element('div', null, 'probabilities');
      appendProbabilityBar(probabilities, row.team_a, primary.a, 'a');
      appendProbabilityBar(probabilities, row.team_b, primary.b, 'b');
      card.append(probabilities);
      card.append(element('p', primary.label, 'basis-label'));
      card.append(element('p', primary.details, 'small'));
      if (primary.kind === 'market' || primary.kind === 'prediction-market') {
        card.append(element('p', `Quote observed ${formatUTC(primary.capturedUTC)} (${relativeAge(primary.capturedUTC, now)}).`, 'small'));
      } else {
        card.append(element('p', `Rating input as of ${primary.ratingAsOf} · HLTV confirms BO${primary.format.bestOf} · analysis build ${formatUTC(primary.format.execGeneratedUTC)}.`, 'small'));
      }
      if (item.model && primary.kind !== 'model') {
        const divergence = Math.abs(primary.a - item.model.a);
        const comparison = `${row.team_a} ${formatPercent(item.model.a)} · ${row.team_b} ${formatPercent(item.model.b)} (separate project VRS/series model)`;
        card.append(element('p', `${divergence >= 15 ? 'Large market/model split · review' : 'Own-line cross-check'}: ${comparison}`, divergence >= 15 ? 'review-note' : 'small'));
      }
    } else {
      card.append(element('p', 'Pick: — unresolved; no verified series probability published.', 'pick-call'));
      const probabilities = element('div', null, 'probabilities');
      for (const name of [row.team_a, row.team_b]) {
        const cell = element('div', null, 'probability-cell');
        cell.append(element('span', name, 'probability-name'), element('b', '—'));
        probabilities.append(cell);
      }
      card.append(probabilities);
      card.append(element('p', 'No verified two-sided market or rating basis is available. Percentages are intentionally blank.', 'basis-label'));
    }

    const links = element('div', null, 'source-links');
    appendLink(links, row.hotspawn_url, 'Official Hotspawn fixture');
    const sourceMarket = item.market && item.market.sourceURL ? item.market : null;
    if (sourceMarket) {
      const sourceLabel = sourceMarket.kind === 'prediction-market' ? 'Polymarket series market' :
        /pinnacle/i.test(String(row.ext_bookmaker || '')) ? 'Pinnacle public markets page · no per-match deep link (FL-12)' :
          /egamersworld/i.test(String(row.ext_bookmaker || '')) ? 'EGamersWorld per-match page · underlying book to review' : 'Market source';
      appendLink(links, sourceMarket.sourceURL, sourceLabel);
    }
    else if (row.ext_url) appendLink(links, row.ext_url, 'Rejected / unverified market reference');
    const model = item.model || (primary && primary.kind === 'model' ? primary : null);
    if (model) {
      appendLink(links, model.sourceURL, 'Official Valve VRS file');
      appendLink(links, model.formatURL, 'HLTV match & best-of');
    } else {
      if (row.vrs_url) appendLink(links, stableVrsURL(row), 'Official Valve standings source');
      const candidate = item.formatEvidence && item.formatEvidence.sourceURL ? item.formatEvidence.sourceURL : row.hltv_url;
      const candidateURL = safeURL(candidate);
      if (candidateURL && hasHost(candidateURL, 'hltv.org')) {
        const exact = validHltvMatch(candidateURL.href, row.team_a, row.team_b);
        appendLink(links, candidateURL.href, exact ? 'HLTV match & format reference' : 'HLTV reference (identity not verified)');
      }
    }
    const flags = String(row.flags || '').split(';').map(value => value.trim()).filter(Boolean);
    if (item.flags && item.flags.length) {
      appendLink(links, 'live/flagged.html', `Flagged for Review${flags.length ? ` (${flags.join(', ')})` : ''}`);
    }
    if (String(row.match_id) === '1079624') {
      appendLink(links, 'https://www.hltv.org/matches/2399301/forze-reload-vs-lfo-10-cct-2026-europe-series-11', 'HLTV match');
      appendLink(links, 'https://www.hltv.org/team/14084/lfo-10', 'HLTV LFO 10 profile');
      appendLink(links, 'https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3', 'EGamersWorld listing');
      appendLink(links, 'https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14', 'Polymarket contract scopes');
    }
    card.append(links);

    if (item.flags && item.flags.length) {
      const flagText = item.flags.slice(0, 4).join(' · ');
      card.append(element('p', `Review flags: ${flagText}${item.flags.length > 4 ? ' · more on Flagged for Review' : ''}`, 'small'));
    }
    return card;
  }

  function renderPicks(view, dataError) {
    const list = document.getElementById('pick-list');
    if (!list) return;
    list.replaceChildren();
    if (dataError || !view) {
      list.append(element('p', 'Current evidence is unavailable or failed its integrity checks. No match probabilities are shown. Open the captured inventory and source/flag pages below.', 'notice'));
      return;
    }
    const search = document.getElementById('pick-search');
    const tier = document.getElementById('tier-filter');
    const term = search ? search.value.trim().toLowerCase() : '';
    const selectedTier = tier ? tier.value : '';
    const selected = view.active.filter(item => {
      const matchesTerm = `${item.row.team_a} ${item.row.team_b} ${item.row.competition} ${item.row.match_id}`.toLowerCase().includes(term);
      return matchesTerm && (!selectedTier || String(item.row.tier).toUpperCase() === selectedTier);
    });
    if (!view.snapshotFresh) {
      list.append(element('p', 'Snapshot stale / unverified. Fixture rows are listed only for manual review; all estimates were suppressed.', 'notice'));
    }
    selected.forEach(item => list.append(renderCard(item, Date.now())));
    if (!selected.length) list.append(element('p', view.active.length ? 'No matches for this filter.' : 'No fixture with a verified future lock appears in this capture. See the coverage audit for locked and stale rows.'));
    const count = document.getElementById('display-count');
    if (count) count.textContent = `Showing ${selected.length} of ${view.active.length} fixtures whose captured UTC lock is still ahead. The lock filter is recalculated in your browser.`;
  }

  function renderUnresolved(view, dataError) {
    const target = document.getElementById('unresolved-list');
    if (!target) return;
    target.replaceChildren();
    if (dataError || !view) {
      target.append(element('p', 'Unresolved inventory is unavailable because the source checks failed. No estimates are substituted.', 'small'));
      return;
    }
    const items = view.active.filter(item => !item.primary);
    if (!items.length) {
      target.append(element('p', 'No currently unlocked row is unresolved in this capture. A later refresh may add one; source timestamps still apply.', 'small'));
      return;
    }
    target.append(element('p', `${items.length} current fixture${items.length === 1 ? '' : 's'} have no verified market or research probability. Both team values and the pick remain blank.`, 'small'));
    for (const item of items) {
      const row = item.row;
      const article = element('article', null, 'unresolved-item');
      article.dataset.fixtureId = row.match_id;
      article.append(element('h3', `Hotspawn ${row.match_id}: ${row.team_a} vs ${row.team_b}`));
      article.append(element('p', `No pick · ${formatUTC(row.lock_utc)} lock · ${String(row.tier || 'tier unverified').toUpperCase()} · ${row.competition || 'competition unverified'}.`));
      const reasons = (item.flags || []).slice(0, 5).join(' · ') || 'No verified two-sided probability basis.';
      article.append(element('p', `Reason / review flags: ${reasons}`, 'small'));
      const links = element('div', null, 'source-links');
      appendLink(links, row.hotspawn_url, 'Hotspawn fixture');
      if (row.vrs_url) appendLink(links, stableVrsURL(row), 'Official Valve rating source');
      const candidate = item.formatEvidence && item.formatEvidence.sourceURL ? item.formatEvidence.sourceURL : row.hltv_url;
      const candidateURL = safeURL(candidate);
      if (candidateURL && hasHost(candidateURL, 'hltv.org')) {
        const exact = validHltvMatch(candidateURL.href, row.team_a, row.team_b);
        appendLink(links, candidateURL.href, exact ? 'HLTV match reference' : 'HLTV alias/format candidate (identity not verified)');
      }
      if (row.ext_url) appendLink(links, row.ext_url, 'Rejected / unverified market reference');
      if (String(row.match_id) === '1079624') {
        appendLink(links, 'https://www.hltv.org/team/14084/lfo-10', 'HLTV LFO 10 profile');
        appendLink(links, 'https://egamersworld.com/counterstrike/match/_rW8GEyWK/forze-reload-vs-Gr_YhyKi3', 'EGamersWorld identity lead');
        appendLink(links, 'https://polymarket.com/esports/cs2/cct-europe/cs2-forzer-skr2-2026-10-14', 'Polymarket contract scopes');
      }
      appendLink(links, 'live/flagged.html', 'Flagged for Review');
      article.append(links);
      target.append(article);
    }
  }

  function applyRoot(view, dataError) {
    const status = document.getElementById('landing-status');
    if (!status) return;
    const ids = {
      open: document.getElementById('root-open'),
      supported: document.getElementById('root-supported'),
      market: document.getElementById('root-market'),
      model: document.getElementById('root-model'),
      unresolved: document.getElementById('root-unresolved'),
      total: document.getElementById('root-total')
    };
    if (dataError || !view) {
      status.textContent = 'Published fixture evidence is unavailable or failed validation. No counts or probabilities have been substituted.';
      Object.values(ids).forEach(node => { if (node) node.textContent = '—'; });
      return;
    }
    if (ids.open) ids.open.textContent = String(view.active.length);
    if (ids.supported) ids.supported.textContent = String(view.marketCount + view.modelCount);
    if (ids.market) ids.market.textContent = String(view.marketCount);
    if (ids.model) ids.model.textContent = String(view.modelCount);
    if (ids.unresolved) ids.unresolved.textContent = String(view.unresolvedCount);
    if (ids.total) ids.total.textContent = String(view.totalFixtures);
    const capture = formatUTC(view.generatedUTC);
    const built = view.execGeneratedUTC ? ` · separate HLTV best-of cross-check build ${formatUTC(view.execGeneratedUTC)}` : ' · HLTV best-of cross-check unavailable';
    const age = view.snapshotFresh ? relativeAge(view.generatedUTC) : 'STALE / REVIEW';
    status.textContent = `Hotspawn fixture capture ${capture} (${age}); ${view.totalFixtures} captured CS2 rows. Lock times are re-evaluated at page time.${built}. The later build is not used for the fixture count.`;
  }

  function boot() {
    const pickList = document.getElementById('pick-list');
    const rootStatus = document.getElementById('landing-status');
    if (!pickList && !rootStatus) return;
    let latest = null;
    let failed = false;
    const update = async () => {
      try {
        const bundle = await loadData();
        latest = buildView(bundle.rows, bundle.meta, bundle.execData, Date.now());
        failed = false;
        applyRoot(latest, false);
        renderPicks(latest, false);
        renderUnresolved(latest, false);
      } catch (error) {
        latest = null;
        failed = true;
        applyRoot(null, true);
        renderPicks(null, true);
        renderUnresolved(null, true);
        const meta = document.getElementById('capture-status');
        if (meta) meta.textContent = `Evidence load failed: ${error.message}`;
      }
    };
    const search = document.getElementById('pick-search');
    const tier = document.getElementById('tier-filter');
    if (search && typeof window !== 'undefined') {
      const term = new URLSearchParams(window.location.search).get('q');
      if (term) search.value = term;
    }
    if (search) search.addEventListener('input', () => renderPicks(latest, failed));
    if (tier) tier.addEventListener('change', () => renderPicks(latest, failed));
    update();
    // The source workflows refresh hourly (best-effort); the page re-evaluates lock times each minute.
    setInterval(update, 60 * 1000);
  }

  boot();
})(typeof globalThis !== 'undefined' ? globalThis : this);
