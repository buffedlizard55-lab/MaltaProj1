'use strict';
// No odds scraping or inferred values in the browser. Same-origin stored observations only.
const $ = id => document.getElementById(id);
const state = {data: null};
const FIXTURE_HOSTS = new Set(['play.hotspawn.com','www.hotspawn.com','hotspawn.com']);
function safeURL(value, fixture = false) {
  try { const u = new URL(value); return u.protocol === 'https:' && !u.username && !u.password && (!fixture || FIXTURE_HOSTS.has(u.hostname)) ? u.href : null; }
  catch { return null; }
}
function node(tag, text, cls) { const e=document.createElement(tag); if(text !== undefined) e.textContent=text; if(cls)e.className=cls; return e; }
function link(label, url, fixture=false) {
  const target=safeURL(url, fixture); if(!target)return node('span','Source unverified','blank');
  const a=node('a',label);a.href=target;a.target='_blank';a.rel='noopener noreferrer';return a;
}
function pair(a,b) { return typeof a==='number' && typeof b==='number' && Number.isFinite(a) && Number.isFinite(b) && a>=0 && b>=0 && a<=100 && b<=100 && Math.abs(a+b-100)<=.2; }
function stamp(value) { if(typeof value!=='string'||!/(Z|[+-]\d\d:\d\d)$/.test(value))return null;const d=new Date(value);return Number.isFinite(d.getTime())?d:null; }
function rows() { return (state.data?.matches || []).filter(r=>r.sport==='cs2'); }
function cell(row,label) { const td=node('td');td.dataset.label=label;row.append(td);return td; }
function renderTable() {
  if(!$('fixtures'))return;
  const query=($('search')?.value||'').trim().toLowerCase(), filter=$('filter')?.value||'all', now=Date.now();
  const fragment=document.createDocumentFragment();let count=0;
  for(const r of rows()) {
    const lock=stamp(r.lock_utc), locked=lock ? lock.getTime()<=now : null;
    if(filter==='open' && locked!==false)continue;
    if(filter==='missing' && pair(r.market_p_a_pct,r.market_p_b_pct))continue;
    if(!`${r.team_a} ${r.team_b} ${r.competition} ${r.match_id}`.toLowerCase().includes(query))continue;
    count++;const tr=node('tr');
    let td=cell(tr,'Match');td.append(node('strong',`${r.team_a||'Unverified'} vs ${r.team_b||'Unverified'}`), node('small',r.competition||'Competition unverified'),node('small',`#${r.match_id||'Unverified'} · ${r.tier||'Tier unverified'}`));
    td=cell(tr,'Lock time');td.append(node('span',lock?lock.toISOString().replace('.000Z',' UTC'):'Time unverified'),node('small',locked===null?'Lock status unverified':locked?'Locked — not an actionable pick':'Open at browser check time'));
    td=cell(tr,'External market — A / B');
    if(pair(r.market_p_a_pct,r.market_p_b_pct)){
      td.append(node('span',`${r.market_p_a_pct.toFixed(1)}% / ${r.market_p_b_pct.toFixed(1)}%`,'pair'));
      for(const s of r.market_sources||[]) {td.append(node('small',`Captured: ${s.fetched_utc||'unverified'}`),link(s.source||'External observation',s.url));}
      td.append(node('small','Stored observation; source values not independently live-verified here.'));
    } else {td.append(node('span','—','blank'),node('small','Unverified / no external line in this snapshot'));}
    td=cell(tr,'Rating model — A / B');
    if(pair(r.own_model_p_a_pct,r.own_model_p_b_pct)){
      td.append(node('span',`${r.own_model_p_a_pct.toFixed(1)}% / ${r.own_model_p_b_pct.toFixed(1)}%`,'pair'),node('small','Provisional model estimate, not a verified probability'));
      for(const s of r.model_inputs||[])td.append(link(s.source||'Model input',s.url),node('br'));
    }else td.append(node('span','—','blank'),node('small','Unverified / insufficient sourced ratings'));
    td=cell(tr,'Published model / market pick');
    if(r.pick && [r.team_a,r.team_b].includes(r.pick) && (pair(r.market_p_a_pct,r.market_p_b_pct)||pair(r.own_model_p_a_pct,r.own_model_p_b_pct))) {
      td.append(node('strong',r.pick,'pick'),node('small',r.estimate_basis||'Basis unverified'),node('small',locked?'Historical / locked': 'Estimate — not a guaranteed outcome'));
    }else td.append(node('span','—','blank'),node('small','No supportable pick'));
    td=cell(tr,'Official fixture source');td.append(link('Hotspawn fixture page',r.hotspawn_page,true),node('small','Link presence checked; live fixture identity not re-verified by this view.'));
    fragment.append(tr);
  }
  $('fixtures').replaceChildren(fragment);$('showing').textContent=`${count} of ${rows().length} stored CS2 fixtures shown. No fixed match-count assumption.`;
}
function issue(title, detail, url, label='Review source') {
  const e=node('article',undefined,'issue');e.append(node('h3',title),node('p',detail));if(url)e.append(link(label,url));return e;
}
function renderFlags() {
  if(!$('findings'))return;
  const fragment=document.createDocumentFragment();
  const data=state.data, source='https://play.hotspawn.com/lobby';
  const pages=data.meta?.pickem_page_header_counts||[];
  fragment.append(issue('RA91-COVERAGE · A snapshot is not proof of complete live coverage','The upstream collector reads multiple Hotspawn pages. Page headers, cached payload rows and rendered cards can disagree. The counts below are separate observations, not interchangeable definitions of pickable matches.',source,'Official lobby'));
  for(const p of pages.filter(p=>['lobby','cs2-pickems','thp-pickems'].includes(p.page)))fragment.append(issue(`Stored page observation: ${p.page}`,`Header count: ${p.matches_this_week_text ?? 'unverified'} · payload rows: ${p.rows_in_payload ?? 'unverified'} · rendered cards: ${p.cards_rendered ?? 'unverified'}. Captured by the upstream collector, not re-read here.`,p.url));
  const missing=rows().filter(r=>!pair(r.market_p_a_pct,r.market_p_b_pct));
  fragment.append(issue(`RA91-NOMARKET · ${missing.length}/${rows().length} stored CS2 rows have no external market probability`,'A successful refresh can still return zero odds. Market fields stay blank; model estimates are not a substitute for verified sportsbook observations.','https://egamersworld.com/counterstrike/matches','External coverage (aggregator, not a primary bookmaker)'));
  fragment.append(issue('RA91-MODEL · Model estimates require calibration review','The today/ collector uses a 400-point Elo transform on rating points. Other repository models use different calibration. These outputs are calculated estimates, never official team-win probabilities. Compare the model methodology and flagged pages before relying on them.','https://github.com/ValveSoftware/counter-strike_regional_standings','Official Valve model and standings'));
  fragment.append(issue('RA91-AUTO · Publication and collection are different checks','The R-01 workflow continues after failed collect/build/render/verify steps. The Refresh verified snapshot workflow writes to a session branch instead of the Pages main branch. Neither a green workflow nor a recent render timestamp alone establishes fresh verified market coverage.','https://github.com/buffedlizard55-lab/MaltaProj1/tree/main/.github/workflows','Official repository workflows'));
  for(const r of rows()){
    const details=[];if(!pair(r.market_p_a_pct,r.market_p_b_pct))details.push('External win probability unverified / unavailable.');
    if(pair(r.own_model_p_a_pct,r.own_model_p_b_pct))details.push('Rating-model estimate is provisional; calibration/source-value verification remains separate.');
    else details.push('Own-model probability unavailable.');
    if((stamp(r.lock_utc)?.getTime()||Infinity)<=Date.now())details.push('Locked at the browser check time.');
    fragment.append(issue(`#${r.match_id} · ${r.team_a} vs ${r.team_b}`,details.join(' '),r.hotspawn_page,'Official fixture page'));
  }
  $('findings').replaceChildren(fragment);
}
async function readSnapshot() {
  $('load-state').textContent='Reading the published source snapshot…';
  try {
    const response=await fetch('../today/data/current.json',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const data=await response.json();if(!Array.isArray(data.matches)||!data.meta)throw new Error('Invalid snapshot schema');state.data=data;
    const captured=stamp(data.meta.hotspawn_snapshot_utc), age=captured ? (Date.now()-captured.getTime())/3600000 : null;
    $('load-state').textContent=captured?`Official-fixture capture reported by collector: ${captured.toISOString()} · ${age<0?'FUTURE TIMESTAMP — REVIEW':age>6?'STALE — OVER SIX HOURS OLD':`${Math.floor(age*60)} minutes old`}. Browser read: ${new Date().toISOString()}.`:'Capture timestamp unverified — freshness unknown.';
    const rs=rows(); if($('total')){
      $('total').textContent=rs.length;$('open').textContent=rs.filter(r=>stamp(r.lock_utc)?.getTime()>Date.now()).length;
      $('market').textContent=rs.filter(r=>pair(r.market_p_a_pct,r.market_p_b_pct)).length;
      $('model').textContent=rs.filter(r=>pair(r.own_model_p_a_pct,r.own_model_p_b_pct)).length;
    }
    renderTable();renderFlags();
  }catch(e){state.data=null;$('load-state').textContent=`Source snapshot unavailable (${e.message}). Coverage and probabilities are unverified; no values substituted.`;if($('fixtures'))$('fixtures').replaceChildren();if($('findings'))$('findings').replaceChildren();for(const id of ['total','open','market','model'])if($(id))$(id).textContent='—';}
}
async function readRuns() {
  if(!$('run-list'))return;
  try {
    const r=await fetch('https://api.github.com/repos/buffedlizard55-lab/MaltaProj1/actions/runs?branch=main&per_page=50',{cache:'no-store'});if(!r.ok)throw new Error(`HTTP ${r.status}`);
    const d=await r.json(), list=document.createDocumentFragment(), seen=new Set();
    for(const run of d.workflow_runs||[]){
      if(seen.has(run.name)||!['R-01 refresh (b90700c6)','O-01 own-line model (VRS)','Refresh verified snapshot','Independent coverage and release assurance','pages-build-deployment'].includes(run.name))continue;
      seen.add(run.name);const li=node('li');li.append(link(run.name,run.html_url),node('span',` — ${run.status} / ${run.conclusion||'pending'} · ${run.created_at}`));list.append(li);
    }
    if(!seen.size)list.append(node('li','No relevant main-branch runs in the latest 50 results. Status unverified.'));
    $('run-list').replaceChildren(list);$('run-state').textContent=`GitHub API checked at ${new Date().toISOString()}. Workflow success does not verify odds coverage.`;
  }catch(e){$('run-state').textContent=`GitHub status unavailable (${e.message}); no successful deployment inferred.`;}
}
$('search')?.addEventListener('input',renderTable);$('filter')?.addEventListener('change',renderTable);
$('reload')?.addEventListener('click',()=>{readSnapshot();readRuns();});
readSnapshot();readRuns();setInterval(()=>{readSnapshot();readRuns();},300000);
