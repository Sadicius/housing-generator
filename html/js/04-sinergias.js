// ---------------- SINERGIAS ----------------
const WEIGHT = {oc:3, ol:-3, pc:1, pa:-1, n:0, cond:0, cov:2};
const ZONE_GROUP_ORDER = ['day','night','service','circulation'];
const CAT_COLOR = {estancia:'--cat-estancia', servicio:'--pa', circulacion:'--cyan-dim', otros:'--n'};

// Por defecto solo se muestran las relaciones ESTRUCTURALES (obligatorio
// cerca/lejos + ya cubierto) -- retomado a peticion del usuario: con las
// ~85 aristas no neutras del catalogo completo, el diagrama era
// demasiado denso para comprender de un vistazo. Las de Preferencia se
// activan aparte, sin perder ningun dato (todo sigue disponible, solo
// no se muestra todo a la vez por defecto).
let NETWORK_FILTER = new Set(['oc', 'ol', 'cov']);

function renderNetFilters(){
  const el = document.getElementById('net-filters');
  const options = [
    {k:'oc', label:'Obligatorio cerca'}, {k:'ol', label:'Obligatorio lejos'},
    {k:'cov', label:'Ya cubierto'}, {k:'pc', label:'Preferencia cerca'}, {k:'pa', label:'Preferencia alejar'},
  ];
  el.innerHTML = options.map(({k,label}) => `
    <label><input type="checkbox" data-k="${k}" ${NETWORK_FILTER.has(k)?'checked':''}>
      <span style="color:var(${COLORVAR[k]})">${label}</span></label>
  `).join('');
  el.querySelectorAll('input').forEach(cb => {
    cb.addEventListener('change', () => {
      if(cb.checked) NETWORK_FILTER.add(cb.dataset.k); else NETWORK_FILTER.delete(cb.dataset.k);
      buildNetwork(SCORES);
    });
  });
}

function computeScores(){
  const scores = {}; TYPES.forEach(t => scores[t] = 0);
  PAIRS.forEach(p => {
    const w = WEIGHT[classify(p.relation)];
    scores[p.a] += w; scores[p.b] += w;
  });
  return scores;
}

// Retomado de la metodologia de matriz de relaciones ponderadas
// (clasica en programacion arquitectonica): "el orden descendente de
// las sumatorias define el rango de jerarquia y ubicacion central o
// periferica". Puntuacion mas alta -> rango mas bajo (0) -> posicion
// mas CENTRAL. Empates comparten el mismo rango (rango promedio,
// "competition ranking" estandar) -- misma jerarquia, misma posicion,
// no un desempate arbitrario.
function computeRanks(scores){
  const sorted = TYPES.slice().sort((a,b) => scores[b]-scores[a]);
  const ranks = {};
  let i = 0;
  while(i < sorted.length){
    let j = i;
    while(j+1 < sorted.length && scores[sorted[j+1]] === scores[sorted[i]]) j++;
    const avgRank = (i+j)/2;  // 0-indexado, promedio del grupo empatado
    for(let k=i;k<=j;k++) ranks[sorted[k]] = avgRank;
    i = j+1;
  }
  return ranks;
}

function networkOrder(){
  return TYPES.slice().sort((a,b) => {
    const za = ZONE_GROUP_ORDER.indexOf(PROPS[a].zone), zb = ZONE_GROUP_ORDER.indexOf(PROPS[b].zone);
    return za !== zb ? za - zb : TYPES.indexOf(a) - TYPES.indexOf(b);
  });
}

function hasNonNeutralEdge(t, other){
  return PAIRS.some(p => {
    const cls = classify(p.relation);
    return NETWORK_FILTER.has(cls) && ((p.a===t&&p.b===other)||(p.a===other&&p.b===t));
  });
}

function buildNetwork(scores){
  const order = networkOrder();
  const ranks = computeRanks(scores);
  const n = order.length, cx = 310, cy = 310;
  const MIN_R = 70, MAX_R = 260;  // rango 0 (mas "necesario") = mas central
  const pos = {};
  order.forEach((t,i) => {
    const angle = (i/n)*2*Math.PI - Math.PI/2;
    const radius = n > 1 ? MIN_R + (ranks[t]/(n-1))*(MAX_R-MIN_R) : (MIN_R+MAX_R)/2;
    pos[t] = {x: cx + radius*Math.cos(angle), y: cy + radius*Math.sin(angle)};
  });

  // anillos guia -- confirman visualmente que la posicion central/
  // periferica sigue el rango, no solo el tamano del nodo
  let ringsHtml = '';
  [MIN_R, (MIN_R+MAX_R)/2, MAX_R].forEach(r => {
    ringsHtml += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--line)" stroke-width="0.75" stroke-dasharray="3,5" opacity="0.5"></circle>`;
  });

  let edgesHtml = '';
  PAIRS.forEach(p => {
    const cls = classify(p.relation);
    if(cls === 'n' || cls === 'cond') return;
    if(!NETWORK_FILTER.has(cls)) return;  // respeta el filtro de tipos activos
    const a = pos[p.a], b = pos[p.b];
    const dashed = (cls==='ol' || cls==='pa') ? 'stroke-dasharray="5,4"' : '';
    const width = (cls==='oc'||cls==='ol') ? 2.4 : 1.3;
    edgesHtml += `<line class="net-edge" data-a="${p.a}" data-b="${p.b}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="var(${COLORVAR[cls]})" stroke-width="${width}" opacity="0.55" ${dashed}></line>`;
  });
  edgesHtml = ringsHtml + edgesHtml;

  const maxAbs = Math.max(...Object.values(scores).map(v=>Math.abs(v)), 1);
  let nodesHtml = '';
  order.forEach(t => {
    const p = pos[t];
    const r = 8 + (scores[t] > 0 ? (scores[t]/maxAbs)*9 : 1);
    const ang = Math.atan2(p.y-cy, p.x-cx);
    const lx = p.x + Math.cos(ang)*(r+36), ly = p.y + Math.sin(ang)*(r+14);
    nodesHtml += `<g class="net-node" data-type="${t}">
      <circle class="net-hitarea" cx="${p.x}" cy="${p.y}" r="${r+14}" fill="transparent"></circle>
      <circle cx="${p.x}" cy="${p.y}" r="${r}" fill="var(${CAT_COLOR[PROPS[t].category]||'--n'})" stroke="#2B2622" stroke-width="1.5"></circle>
      <text class="net-label" x="${lx}" y="${ly}" text-anchor="middle">${DISPLAY[t]}</text>
    </g>`;
  });

  const svg = document.getElementById('net-svg');
  svg.innerHTML = edgesHtml + nodesHtml;

  svg.querySelectorAll('.net-node').forEach(node => {
    node.addEventListener('click', () => {
      const t = node.dataset.type;
      const wasActive = node.classList.contains('active-node');
      svg.querySelectorAll('.net-node').forEach(n2 => n2.classList.remove('active-node'));
      if(wasActive){
        svg.querySelectorAll('.net-edge').forEach(e => e.style.opacity = '0.55');
        svg.querySelectorAll('.net-node circle').forEach(c => c.style.opacity = '1');
        return;
      }
      node.classList.add('active-node');
      svg.querySelectorAll('.net-edge').forEach(e => {
        e.style.opacity = (e.dataset.a===t || e.dataset.b===t) ? '0.95' : '0.05';
      });
      svg.querySelectorAll('.net-node').forEach(n2 => {
        const nt = n2.dataset.type;
        n2.querySelector('circle').style.opacity = (nt===t || hasNonNeutralEdge(t,nt)) ? '1' : '0.2';
      });
    });
  });
}

function buildScoreBars(scores){
  const wrap = document.getElementById('score-bars');
  const maxAbs = Math.max(...Object.values(scores).map(v=>Math.abs(v)), 1);
  const sorted = TYPES.slice().sort((a,b) => scores[b]-scores[a]);
  wrap.innerHTML = sorted.map(t => {
    const s = scores[t], pct = Math.abs(s)/maxAbs*50, isNeg = s < 0;
    const left = isNeg ? (50-pct) : 50;
    return `<div class="score-row">
      <span class="lbl">${DISPLAY[t]}</span>
      <div class="bartrack"><div class="barfill ${isNeg?'neg':''}" style="left:${left}%; width:${pct}%;"></div></div>
      <span class="val">${s>0?'+':''}${s}</span>
    </div>`;
  }).join('');
}

function rankItemHtml(p){
  const cls = classify(p.relation);
  return `<div class="rank-item">
    <span class="names">${DISPLAY[p.a]} <span style="color:var(--ink-faint)">×</span> ${DISPLAY[p.b]}</span>
    <span class="tagmini" style="background:var(${COLORVAR[cls]})">${LABELS[cls]}</span>
  </div>`;
}

function csvEscape(v){
  const s = String(v);
  return /[",\n]/.test(s) ? '"' + s.replace(/"/g,'""') + '"' : s;
}

function exportScheduleCSV(){
  // "tabla de planificacion" (Schedule, en terminologia Revit) -- a
  // diferencia del flujo manual habitual (exportar a Excel, cruzar
  // valores 4/2/0 y sumar rangos a mano), aqui la puntuacion y el
  // rango ya estan calculados automaticamente (computeScores/
  // computeRanks) -- esta exportacion solo vuelca esos datos ya
  // calculados a una tabla real, para usar fuera del dashboard.
  const scores = computeScores();
  const ranks = computeRanks(scores);
  const rows = [['tipo','nombre','zona','categoria','area_representativa_m2','puntuacion_sinergia','rango']];

  TYPES.slice().sort((a,b) => ranks[a]-ranks[b]).forEach(t => {
    const p = PROPS[t];
    rows.push([t, DISPLAY[t], p.zone, p.category, DEFAULT_AREA_M2[t] || '', scores[t], ranks[t]]);
  });

  const csv = rows.map(r => r.map(csvEscape).join(',')).join('\n');
  const blob = new Blob([csv], {type: 'text/csv;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'tabla_estancias.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function buildRankings(){
  const withW = PAIRS.map(p => ({...p, w: WEIGHT[classify(p.relation)]}));
  const top = withW.filter(p=>p.w>0).sort((a,b)=>b.w-a.w).slice(0,5);
  const bottom = withW.filter(p=>p.w<0).sort((a,b)=>a.w-b.w).slice(0,5);
  document.getElementById('rank-top').innerHTML = top.map(rankItemHtml).join('');
  document.getElementById('rank-bottom').innerHTML = bottom.map(rankItemHtml).join('');
}

function buildSynergyLegend(){
  const el = document.getElementById('legend-synergy');
  el.innerHTML = ['oc','ol','pc','pa','cov'].map(k =>
    `<span class="item"><span class="sw" style="background:var(${COLORVAR[k]})"></span>${LABELS[k]}</span>`
  ).join('');
}
