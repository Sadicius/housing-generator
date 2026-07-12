// ---------------- VISOR DE PLANO ----------------
// (fusionado desde plano_viewer.html a peticion del usuario -- "FLOORS"
// ya existe arriba con otro significado del todo distinto, de ahi
// LOADED_PLANS/ACTIVE_PLAN en vez de FLOORS/ACTIVE)
const PLANO_ZONE_COLOR = {day:'var(--zone-day)', night:'var(--zone-night)', service:'var(--zone-service)', circulation:'var(--zone-circulation)'};
const PLANO_ZONE_LABEL = {day:'Día', night:'Noche', service:'Servicio', circulation:'Circulación'};

let LOADED_PLANS = [];   // [{label, data}], data = el JSON tal cual ({rooms, doors, metadata})
let ACTIVE_PLAN = 0;

function labelForPlanFile(filename){
  const m = filename.match(/planta_(\w+)/i) || filename.match(/(sotano|semisotano|bajo_cubierta)/i);
  if(m) return m[0].replace(/_/g,' ').replace(/^\w/, c => c.toUpperCase());
  return filename.replace(/\.json$/i, '');
}

function renderPlanoTabs(){
  const wrap = document.getElementById('floor-tabs');
  if(LOADED_PLANS.length <= 1){ wrap.innerHTML = ''; return; }
  wrap.innerHTML = LOADED_PLANS.map((f, i) => {
    const hv = f.data.metadata && f.data.metadata.hard_violations;
    const badge = (hv === 0) ? '<span class="badge ok">✓</span>' : (hv > 0 ? `<span class="badge bad">${hv}</span>` : '');
    return `<button class="floor-tab ${i===ACTIVE_PLAN?'active':''}" data-i="${i}">${f.label}${badge}</button>`;
  }).join('');
  wrap.querySelectorAll('.floor-tab').forEach(btn => {
    btn.addEventListener('click', () => { ACTIVE_PLAN = parseInt(btn.dataset.i,10); renderPlanoTabs(); renderPlano(); });
  });
}
// ---------------- MODO ESPEJO (visor de plano) ----------------
// Retomado de una sugerencia del usuario: el generador no considera
// orientacion solar (SolarExposureValidator sigue aparcado) -- un
// plano puede ser funcionalmente bueno pero con la zona de dia mirando
// al lado "equivocado". Reflejar/rotar un plano YA generado es una
// transformacion geometrica pura que conserva EXACTAMENTE las
// relaciones de adyacencia (las marcas de puerta se recalculan solas a
// partir de los bounds nuevos, via sharedWallMidpoint) -- no toca el
// generador Python en absoluto, es puro cliente.
let PLANO_TRANSFORM = { mirrorH: false, mirrorV: false, rotation: 0 };  // rotation en {0,90,180,270}

function planoCanvasBounds(rooms){
  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  rooms.forEach(r => {
    const [x0,y0,x1,y1] = r.bounds;
    minX=Math.min(minX,x0); minY=Math.min(minY,y0); maxX=Math.max(maxX,x1); maxY=Math.max(maxY,y1);
  });
  return {minX, minY, maxX, maxY};
}

function applyPlanoTransform(rooms, transform){
  if(!transform.mirrorH && !transform.mirrorV && transform.rotation === 0) return rooms;
  const canvas = planoCanvasBounds(rooms);
  const W0 = canvas.maxX - canvas.minX, H0 = canvas.maxY - canvas.minY;

  return rooms.map(r => {
    let [x0,y0,x1,y1] = r.bounds;
    // normalizar al origen del lote (por si no empieza en 0,0)
    x0 -= canvas.minX; x1 -= canvas.minX; y0 -= canvas.minY; y1 -= canvas.minY;
    let W = W0, H = H0;

    if(transform.mirrorH){ const nx0=W-x1, nx1=W-x0; x0=nx0; x1=nx1; }
    if(transform.mirrorV){ const ny0=H-y1, ny1=H-y0; y0=ny0; y1=ny1; }

    const steps = (transform.rotation / 90) % 4;
    for(let i=0;i<steps;i++){
      // rotacion 90 grados horaria: (x,y) -> (y, W-x); el nuevo lienzo es HxW
      const nx0=y0, nx1=y1, ny0=W-x1, ny1=W-x0;
      x0=nx0; x1=nx1; y0=ny0; y1=ny1;
      const tmp=W; W=H; H=tmp;
    }
    return Object.assign({}, r, {bounds: [x0,y0,x1,y1]});
  });
}

function setPlanoTransform(partial){
  PLANO_TRANSFORM = Object.assign({}, PLANO_TRANSFORM, partial);
  renderPlano();
}

// Punto medio del segmento de pared compartida entre dos rectangulos
// axis-aligned (bounds [x0,y0,x1,y1]) -- para marcar puertas. Sin
// libreria de geometria en el cliente: logica directa de bordes,
// suficiente porque toda la geometria del proyecto es rectangular.
function sharedWallMidpoint(a, b){
  const EPS = 0.05;
  if(Math.abs(a[2]-b[0]) < EPS || Math.abs(b[2]-a[0]) < EPS){
    const x = Math.abs(a[2]-b[0]) < EPS ? a[2] : a[0];
    const oy0 = Math.max(a[1], b[1]), oy1 = Math.min(a[3], b[3]);
    if(oy1 > oy0) return {x, y: (oy0+oy1)/2, vertical:true};
  }
  if(Math.abs(a[3]-b[1]) < EPS || Math.abs(b[3]-a[1]) < EPS){
    const y = Math.abs(a[3]-b[1]) < EPS ? a[3] : a[1];
    const ox0 = Math.max(a[0], b[0]), ox1 = Math.min(a[2], b[2]);
    if(ox1 > ox0) return {x: (ox0+ox1)/2, y, vertical:false};
  }
  return null;
}

function renderPlano(){
  const content = document.getElementById('plano-content');
  const floor = LOADED_PLANS[ACTIVE_PLAN];
  if(!floor){ content.innerHTML = '<div class="plano-empty">Carga un archivo para ver la planta generada.</div>'; return; }

  const rooms = applyPlanoTransform(floor.data.rooms.filter(r => r.bounds), PLANO_TRANSFORM);
  if(rooms.length === 0){
    content.innerHTML = '<div class="plano-empty">Este archivo no tiene estancias con geometría resuelta.</div>';
    return;
  }

  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  rooms.forEach(r => {
    const [x0,y0,x1,y1] = r.bounds;
    minX=Math.min(minX,x0); minY=Math.min(minY,y0); maxX=Math.max(maxX,x1); maxY=Math.max(maxY,y1);
  });
  const pad = Math.max((maxX-minX), (maxY-minY)) * 0.04;
  const vbX = minX-pad, vbY = minY-pad, vbW = (maxX-minX)+pad*2, vbH = (maxY-minY)+pad*2;

  // SVG usa Y creciendo hacia abajo; nuestros planos usan Y creciendo
  // hacia arriba (norte = +y, ver Lot) -- se invierte con un transform,
  // no recalculando coordenadas a mano (mas facil de verificar).
  let svgBody = `<g transform="translate(0, ${vbY*2+vbH}) scale(1,-1)">`;
  rooms.forEach(r => {
    const [x0,y0,x1,y1] = r.bounds;
    const color = PLANO_ZONE_COLOR[r.zone] || 'var(--ink-faint)';
    svgBody += `<rect class="room-rect" x="${x0}" y="${y0}" width="${x1-x0}" height="${y1-y0}" fill="${color}" fill-opacity="0.55" data-id="${r.id}"></rect>`;
  });

  (floor.data.doors || []).forEach(d => {
    const ra = rooms.find(r => r.id === d.room_a), rb = rooms.find(r => r.id === d.room_b);
    if(!ra || !rb) return;
    const mid = sharedWallMidpoint(ra.bounds, rb.bounds);
    if(!mid) return;
    const doorWidth = 0.9;
    if(mid.vertical) svgBody += `<line class="door-mark" x1="${mid.x}" y1="${mid.y-doorWidth/2}" x2="${mid.x}" y2="${mid.y+doorWidth/2}"></line>`;
    else svgBody += `<line class="door-mark" x1="${mid.x-doorWidth/2}" y1="${mid.y}" x2="${mid.x+doorWidth/2}" y2="${mid.y}"></line>`;
  });
  svgBody += `</g>`;

  // etiquetas FUERA del grupo invertido, para que el texto no salga en espejo
  let labelsBody = '';
  rooms.forEach(r => {
    const [x0,y0,x1,y1] = r.bounds;
    const cx = (x0+x1)/2, cy = vbY*2+vbH - (y0+y1)/2;
    const w = x1-x0, h = y1-y0;
    // el tamano de fuente considera TANTO las dimensiones de la estancia
    // COMO la longitud del nombre (bug real encontrado en verificacion:
    // "Dormitorio principal" desbordaba su propio rectangulo si solo se
    // miraban las dimensiones) -- el minimo de ambos criterios.
    const fontByRoom = Math.max(0.28, Math.min(w,h) * 0.16);
    const fontByTextWidth = (w * 0.85) / (Math.max(r.name.length, 6) * 0.6);
    const fontSize = Math.max(0.18, Math.min(fontByRoom, fontByTextWidth));
    labelsBody += `<text class="room-label" x="${cx}" y="${cy}" font-size="${fontSize}">
        <tspan class="name" x="${cx}" dy="-0.6em">${escapeXml(r.name)}</tspan>
        <tspan class="area" x="${cx}" dy="1.3em">${r.area_m2.toFixed(1)}m²</tspan>
      </text>`;
  });

  const svg = `<svg viewBox="${vbX} ${vbY} ${vbW} ${vbH}" xmlns="http://www.w3.org/2000/svg">${svgBody}${labelsBody}</svg>`;

  const md = floor.data.metadata || {};
  const hv = md.hard_violations ?? 0;
  const sp = md.soft_penalty ?? 0;
  const warnings = md.warnings ?? 0;
  const totalArea = rooms.reduce((s,r) => s+r.area_m2, 0);
  const zonesPresent = [...new Set(rooms.map(r=>r.zone))];

  content.innerHTML = `
    <div class="plano-stage">
      <div class="plano-canvas">${svg}</div>
      <div class="plano-side">
        <div class="plano-box">
          <h3>Resumen</h3>
          <div class="plano-stat"><span>Estancias</span><b>${rooms.length}</b></div>
          <div class="plano-stat"><span>Superficie total</span><b>${totalArea.toFixed(1)}m²</b></div>
          <div class="plano-stat ${hv>0?'bad':'ok'}"><span>Violaciones duras</span><b>${hv}</b></div>
          <div class="plano-stat"><span>Penalización blanda</span><b>${typeof sp === 'number' ? sp.toFixed(1) : sp}</b></div>
          <div class="plano-stat"><span>Avisos</span><b>${warnings}</b></div>
        </div>
        <div class="plano-box">
          <h3>Zonas</h3>
          <div class="legend">${zonesPresent.map(z => `<span class="item"><span class="sw" style="background:${PLANO_ZONE_COLOR[z]}"></span>${PLANO_ZONE_LABEL[z]||z}</span>`).join('')}</div>
        </div>
        <div class="plano-box">
          <h3>Estancias (${rooms.length})</h3>
          ${rooms.slice().sort((a,b)=>b.area_m2-a.area_m2).map(r =>
            `<div class="plano-room-item" data-id="${r.id}"><span><span class="sw" style="background:${PLANO_ZONE_COLOR[r.zone]}"></span>${escapeXml(r.name)}</span><span>${r.area_m2.toFixed(1)}m²</span></div>`
          ).join('')}
        </div>
      </div>
    </div>`;

  content.querySelectorAll('.plano-room-item').forEach(item => {
    item.addEventListener('mouseenter', () => {
      const rect = content.querySelector(`.room-rect[data-id="${item.dataset.id}"]`);
      if(rect) rect.setAttribute('fill-opacity', '0.9');
    });
    item.addEventListener('mouseleave', () => {
      const rect = content.querySelector(`.room-rect[data-id="${item.dataset.id}"]`);
      if(rect) rect.setAttribute('fill-opacity', '0.55');
    });
  });
}
