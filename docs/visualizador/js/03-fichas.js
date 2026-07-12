// ---------------- FICHAS ----------------
function buildCards(){
  const wrap = document.getElementById('cards-wrap');
  const catColor = {estancia:'--cat-estancia', servicio:'--pa', circulacion:'--cyan-dim', otros:'--n'};
  wrap.innerHTML = TYPES.map(t => {
    const p = PROPS[t];
    const floor = FLOORS.find(f => f.type === t);
    const obligatorias = PAIRS.filter(pr => (pr.a===t || pr.b===t) && ['oc','ol'].includes(classify(pr.relation)));
    const obligatoriasHtml = obligatorias.length > 0 ? `<div class="floor-note" style="margin-top:8px;">
        <b>Relaciones obligatorias:</b><br>
        ${obligatorias.map(pr => {
          const other = pr.a===t ? pr.b : pr.a;
          const cls = classify(pr.relation);
          return `<span style="color:var(${COLORVAR[cls]})">${cls==='oc'?'cerca de':'lejos de'} ${DISPLAY[other]}</span>`;
        }).join(' · ')}
      </div>` : '';
    return `
    <div class="card" data-type="${t}">
      <h3>${DISPLAY[t]} <span style="color:var(--ink-faint); font-size:11px; font-weight:400;">(${t.toLowerCase()})</span></h3>
      <div class="row"><span class="k">zona</span><span class="v">${p.zone}</span></div>
      <div class="row"><span class="k">categoría</span><span class="v"><span class="pill" style="background:var(${catColor[p.category]||'--n'}); color:#2B2622;">${p.category}</span></span></div>
      <div class="row"><span class="k">estancia húmeda</span><span class="v ${p.is_wet?'yes':''}">${p.is_wet ? 'sí' : 'no'}</span></div>
      <div class="row"><span class="k">subtipo (Tabla 2)</span><span class="v">${p.subtype || '—'}</span></div>
      <div class="row"><span class="k">lados a exterior (mín.)</span><span class="v ${p.min_exterior>0?'yes':''}">${p.min_exterior}</span></div>
      ${floor ? `<div class="floor-note"><b>Planta:</b> ${floor.niveles.replace(/\*\*/g,'')} · <b>${floor.fuerza}</b><br>${floor.notas}</div>` : ''}
      ${obligatoriasHtml}
    </div>`;
  }).join('');
}

function filterCards(query){
  const q = query.trim().toLowerCase();
  document.querySelectorAll('#cards-wrap .card').forEach(card => {
    const t = card.dataset.type;
    const match = !q || DISPLAY[t].toLowerCase().includes(q) || t.toLowerCase().includes(q);
    card.style.display = match ? '' : 'none';
  });
}
