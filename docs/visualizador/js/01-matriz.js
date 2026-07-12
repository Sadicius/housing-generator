// ---------------- MATRIZ ----------------
function buildMatrix(){
  const table = document.getElementById('matrix-table');
  let html = '<tr><th></th>';
  TYPES.forEach(t => html += `<th class="colhead" data-type="${t}">${DISPLAY[t]}</th>`);
  html += '</tr>';
  TYPES.forEach((rowType,i) => {
    html += `<tr><th class="rowhead" data-type="${rowType}">${DISPLAY[rowType]}</th>`;
    TYPES.forEach((colType,j) => {
      if(i===j){ html += '<td class="diag"></td>'; return; }
      if(j<i){ html += '<td class="lower"></td>'; return; }
      const pair = findPair(rowType,colType);
      const cls = pair ? classify(pair.relation) : 'n';
      html += `<td class="cell" style="background:var(${COLORVAR[cls]})" data-a="${rowType}" data-b="${colType}" title="${DISPLAY[rowType]} × ${DISPLAY[colType]}"></td>`;
    });
    html += '</tr>';
  });
  table.innerHTML = html;

  table.querySelectorAll('td.cell').forEach(td => {
    td.addEventListener('click', () => showDetail(td.dataset.a, td.dataset.b));
  });
}

function showDetail(a,b){
  const pair = findPair(a,b);
  if(!pair) return;
  document.getElementById('detail-a').textContent = DISPLAY[a];
  document.getElementById('detail-b').textContent = DISPLAY[b];
  const cls = classify(pair.relation);
  const tag = document.getElementById('detail-tag');
  tag.textContent = pair.relation.replace(/\*\*/g,'');
  tag.style.background = `var(${COLORVAR[cls]})`;
  document.getElementById('detail-motivo').textContent = pair.motivo;
  document.getElementById('detail-panel').classList.add('show');
}

function buildLegend(){
  const el = document.getElementById('legend-matrix');
  el.innerHTML = Object.keys(LABELS).map(k =>
    `<span class="item"><span class="sw" style="background:var(${COLORVAR[k]})"></span>${LABELS[k]}</span>`
  ).join('');
}

function filterMatrix(query){
  const q = query.trim().toLowerCase();
  const match = t => !q || DISPLAY[t].toLowerCase().includes(q) || t.toLowerCase().includes(q);
  document.querySelectorAll('#matrix-table th.colhead, #matrix-table th.rowhead').forEach(th => {
    th.classList.toggle('dim', !match(th.dataset.type));
  });
  document.querySelectorAll('#matrix-table td.cell').forEach(td => {
    const dim = q && !match(td.dataset.a) && !match(td.dataset.b);
    td.classList.toggle('dim', dim);
  });
}
