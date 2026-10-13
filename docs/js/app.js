async function loadMatches(){
  try{
    const paths=['data/matches.json','../data/matches.json','site/data/matches.json'];
    let data=null;
    for(const p of paths){try{const r=await fetch(p,{cache:'no-store'});if(r.ok){data=await r.json();break}}catch(e){}}
    if(!data)throw new Error('Could not load matches.json');
    return data;
  }catch(e){
    const tb=document.getElementById('matches-body');
    if(tb)tb.innerHTML='<tr><td colspan="10" class="no-data">Failed to load data: '+e.message+'</td></tr>';
    throw e;
  }
}
function tierBadge(t){return '<span class="tier-badge tier-'+t+'">'+t+'</span>'}
function statusPill(s){const cls=s==='yes'?'status-yes':s==='partial'?'status-partial':'status-no';const lbl=s==='yes'?'Verified':s==='partial'?'Partial':'Unverified';return '<span class="status-pill '+cls+'">'+lbl+'</span>'}
function esc(s){if(s===null||s===undefined)return'';return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function probCell(p,cls){if(p===null||p===undefined)return '<span class="no-data">—</span>';return '<span class="prob-bar '+cls+'"><span class="pct">'+p.toFixed(1)+'%</span><span class="bar"><span style="width:'+Math.min(100,Math.max(4,p))+'%"></span></span></span>'}
function renderRow(m){
  const fc=m.flag?'flag-row':'';
  const src=m.source_url?'<a class="src-link" href="'+esc(m.source_url)+'" target="_blank" rel="noopener">'+esc(m.odds_source||'Source')+'</a>':'<span class="no-data">—</span>';
  const hs=(m.hotspawn_pick_pct_a!==null)?'<span class="hs-pick"><strong>'+m.hotspawn_pick_pct_a+'%</strong> / <strong>'+m.hotspawn_pick_pct_b+'%</strong></span>':'<span class="no-data">—</span>';
  const fh=m.flag?'<span class="flag-note">⚠ '+esc(m.flag)+'</span>':'';
  return '<tr class="'+fc+'"><td><div>'+esc(m.date)+'</div><div style="font-size:12px;color:var(--muted)">'+esc(m.time_utc)+' UTC · '+esc(m.format)+'</div></td><td>'+esc(m.tournament)+fh+'</td><td>'+tierBadge(m.tier)+'</td><td class="team-cell">'+esc(m.team_a)+'</td><td>'+probCell(m.implied_prob_a,'prob-a')+'<div style="font-size:11px;color:var(--muted);margin-top:3px">'+(m.odds_a?'@ '+m.odds_a.toFixed(2):'')+'</div></td><td>'+probCell(m.implied_prob_b,'prob-b')+'<div style="font-size:11px;color:var(--muted);margin-top:3px">'+(m.odds_b?'@ '+m.odds_b.toFixed(2):'')+'</div></td><td class="team-cell">'+esc(m.team_b)+'</td><td>'+hs+'</td><td>'+src+'</td><td>'+statusPill(m.verified)+'</td></tr>';
}
function renderTable(matches,tbId){
  const tb=document.getElementById(tbId||'matches-body');if(!tb)return;
  if(!matches.length){tb.innerHTML='<tr><td colspan="10" class="no-data" style="padding:20px;text-align:center">No matches match current filter.</td></tr>';return}
  matches.sort((a,b)=>(a.date+a.time_utc).localeCompare(b.date+b.time_utc));
  tb.innerHTML=matches.map(renderRow).join('');
}
function updateKpis(matches){
  const set=(id,v)=>{const el=document.getElementById(id);if(el)el.textContent=v};
  set('kpi-total',matches.length);
  set('kpi-verified',matches.filter(m=>m.verified==='yes').length);
  set('kpi-unverified',matches.filter(m=>m.verified==='no').length);
  set('kpi-s',matches.filter(m=>m.tier==='S').length);
}
function initDashboard(customFilter){
  loadMatches().then(data=>{
    const gEl=document.getElementById('gen-time');if(gEl)gEl.textContent='Data generated: '+new Date(data.generated_at).toUTCString();
    const cov=document.getElementById('coverage-note');if(cov)cov.textContent=data.note_remaining_matches||'';
    const rerender=()=>{
      let list=customFilter?customFilter(data.matches):data.matches.slice();
      const tier=document.getElementById('tier-filter')?document.getElementById('tier-filter').value:'all';
      const verif=document.getElementById('verif-filter')?document.getElementById('verif-filter').value:'all';
      const q=document.getElementById('search')?document.getElementById('search').value.trim().toLowerCase():'';
      list=list.filter(m=>{
        if(tier!=='all'&&m.tier!==tier)return false;
        if(verif!=='all'&&m.verified!==verif)return false;
        if(q){const hay=(m.tournament+' '+m.team_a+' '+m.team_b+' '+(m.notes||'')).toLowerCase();if(!hay.includes(q))return false}
        return true;
      });
      renderTable(list);
    };
    updateKpis(data.matches);
    rerender();
    ['tier-filter','verif-filter'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('change',rerender)});
    const sf=document.getElementById('search');if(sf)sf.addEventListener('input',rerender);
    const rb=document.getElementById('reset');if(rb)rb.addEventListener('click',()=>{
      if(document.getElementById('tier-filter'))document.getElementById('tier-filter').value='all';
      if(document.getElementById('verif-filter'))document.getElementById('verif-filter').value='all';
      if(document.getElementById('search'))document.getElementById('search').value='';
      rerender();
    });
  });
}
