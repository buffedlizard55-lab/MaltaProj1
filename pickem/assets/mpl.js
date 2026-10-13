
function filterTable(input, tableId){
  const q = input.value.toLowerCase();
  document.querySelectorAll('#'+tableId+' tbody tr').forEach(tr=>{
    tr.style.display = tr.innerText.toLowerCase().includes(q) ? '' : 'none';
  });
  const shown = [...document.querySelectorAll('#'+tableId+' tbody tr')].filter(t=>t.style.display!=='none').length;
  const chip = document.getElementById(tableId+'-count'); if(chip) chip.textContent = shown + ' rows shown';
}
function sortTable(table, colIndex, numeric){
  const tbody = table.tBodies[0];
  const rows = [...tbody.rows];
  const dir = table.dataset.sortDir === 'asc' ? -1 : 1;
  table.dataset.sortDir = dir === 1 ? 'asc' : 'desc';
  rows.sort((a,b)=>{
    const av = a.cells[colIndex]?.innerText.trim() ?? '', bv = b.cells[colIndex]?.innerText.trim() ?? '';
    if(numeric){ const an=parseFloat(av.replace(/[^0-9.\-]/g,'')), bn=parseFloat(bv.replace(/[^0-9.\-]/g,'')); return (isNaN(an)?-1:an) < (isNaN(bn)?-1:bn) ? dir : -dir; }
    return av < bv ? dir : -dir;
  });
  rows.forEach(r=>tbody.appendChild(r));
}
document.addEventListener('DOMContentLoaded', ()=>{
  document.querySelectorAll('table.sortable th').forEach((th,i)=>{
    th.addEventListener('click', ()=> sortTable(th.closest('table'), i, th.classList.contains('num')));
  });
});
