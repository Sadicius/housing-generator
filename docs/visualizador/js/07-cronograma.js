// ---------------- CRONOGRAMA DE OBRA ----------------
// Herramienta de VISUALIZACION pura -- el usuario introduce fases y
// duraciones, aqui solo se encadenan (cada fase empieza donde termina
// la anterior) y se dibujan. No estima duraciones por si sola: no
// existe, que hayamos podido confirmar, una fuente publica con
// rendimientos de obra reales por fase para vivienda unifamiliar en
// Galicia -- ver la nota de alcance en el propio panel y
// [ARCH:cronograma-obra] en architecture.md.

const GANTT_CATEGORIAS = [
  {id: 'tierras', label: 'Movimiento de tierras', color: '--fase-tierras'},
  {id: 'cimentacion', label: 'Cimentación', color: '--fase-cimentacion'},
  {id: 'estructura', label: 'Estructura', color: '--fase-estructura'},
  {id: 'cerramientos', label: 'Cerramientos', color: '--fase-cerramientos'},
  {id: 'cubierta', label: 'Cubierta', color: '--fase-cubierta'},
  {id: 'instalaciones', label: 'Instalaciones', color: '--fase-instalaciones'},
  {id: 'tabiqueria', label: 'Tabiquería', color: '--fase-tabiqueria'},
  {id: 'acabados', label: 'Revestimientos y acabados', color: '--fase-acabados'},
  {id: 'carpinteria', label: 'Carpintería', color: '--fase-carpinteria'},
  {id: 'urbanizacion', label: 'Urbanización', color: '--fase-urbanizacion'},
];
const GANTT_CAT_BY_ID = Object.fromEntries(GANTT_CATEGORIAS.map(c => [c.id, c]));

let GANTT_FASES = [];  // {id, nombre, categoria, duracionDias}
let GANTT_NEXT_ID = 1;

function populateGanttCategorias(){
  const sel = document.getElementById('gantt-fase-categoria');
  sel.innerHTML = GANTT_CATEGORIAS.map(c => `<option value="${c.id}">${escapeXml(c.label)}</option>`).join('');
}

function ganttStartDate(){
  const val = document.getElementById('gantt-start-date').value;
  return val ? new Date(val + 'T00:00:00') : new Date();
}

function addDays(date, days){
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function formatFecha(date){
  return date.toLocaleDateString('es-ES', {day:'2-digit', month:'2-digit', year:'numeric'});
}

// Encadena las fases en orden: cada una empieza donde termina la
// anterior (sin paralelismo en esta primera version).
function computeGanttSchedule(){
  let cursor = ganttStartDate();
  return GANTT_FASES.map(fase => {
    const inicio = new Date(cursor);
    const fin = addDays(inicio, fase.duracionDias);
    cursor = fin;
    return {...fase, inicio, fin};
  });
}

function handleAddFase(){
  const nombreInput = document.getElementById('gantt-fase-nombre');
  const nombre = nombreInput.value.trim();
  const categoria = document.getElementById('gantt-fase-categoria').value;
  const duracionDias = parseInt(document.getElementById('gantt-fase-duracion').value, 10);

  if(!nombre){
    nombreInput.focus();
    return;
  }
  if(!duracionDias || duracionDias < 1){
    return;
  }

  GANTT_FASES.push({id: GANTT_NEXT_ID++, nombre, categoria, duracionDias});
  nombreInput.value = '';
  nombreInput.focus();
  renderGantt();
}

function removeFase(id){
  GANTT_FASES = GANTT_FASES.filter(f => f.id !== id);
  renderGantt();
}

function moveFase(id, delta){
  const idx = GANTT_FASES.findIndex(f => f.id === id);
  const newIdx = idx + delta;
  if(idx < 0 || newIdx < 0 || newIdx >= GANTT_FASES.length) return;
  const [item] = GANTT_FASES.splice(idx, 1);
  GANTT_FASES.splice(newIdx, 0, item);
  renderGantt();
}

function renderGanttTable(schedule){
  const tbody = document.querySelector('#gantt-table tbody');
  tbody.innerHTML = schedule.map((f, i) => {
    const cat = GANTT_CAT_BY_ID[f.categoria];
    return `<tr>
      <td><span class="sw" style="background:var(${cat.color})"></span><span class="fase-nombre">${escapeXml(f.nombre)}</span></td>
      <td>${escapeXml(cat.label)}</td>
      <td>${f.duracionDias} días</td>
      <td>${formatFecha(f.inicio)} → ${formatFecha(f.fin)}</td>
      <td>
        <button data-action="up" data-id="${f.id}" ${i===0?'disabled':''}>↑</button>
        <button data-action="down" data-id="${f.id}" ${i===schedule.length-1?'disabled':''}>↓</button>
        <button data-action="del" data-id="${f.id}">eliminar</button>
      </td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.dataset.id, 10);
      if(btn.dataset.action === 'del') removeFase(id);
      else if(btn.dataset.action === 'up') moveFase(id, -1);
      else if(btn.dataset.action === 'down') moveFase(id, 1);
    });
  });
}

function renderGanttChart(schedule){
  const content = document.getElementById('gantt-chart-content');
  if(schedule.length === 0){
    content.innerHTML = '<div class="plano-empty">Añade fases para ver el cronograma.</div>';
    return;
  }

  const projectStart = schedule[0].inicio;
  const projectEnd = schedule[schedule.length - 1].fin;
  const totalDays = Math.max(1, Math.round((projectEnd - projectStart) / 86400000));

  const rowH = 34, leftPad = 8, topPad = 24, chartW = 900;
  const pxPerDay = chartW / totalDays;
  const chartH = topPad + schedule.length * rowH + 24;

  let bars = '';
  schedule.forEach((f, i) => {
    const cat = GANTT_CAT_BY_ID[f.categoria];
    const x = leftPad + Math.round((f.inicio - projectStart) / 86400000) * pxPerDay;
    const w = Math.max(2, f.duracionDias * pxPerDay);
    const y = topPad + i * rowH;
    bars += `<rect x="${x}" y="${y}" width="${w}" height="${rowH - 8}" fill="var(${cat.color})" fill-opacity="0.85" rx="2"></rect>`;
    bars += `<text x="${x + 6}" y="${y + (rowH-8)/2 + 4}" class="gantt-bar-label">${escapeXml(f.nombre)}</text>`;
  });

  // lineas de semana + marca de "hoy" si cae dentro del rango
  let gridlines = '';
  for(let d = 0; d <= totalDays; d += 7){
    const x = leftPad + d * pxPerDay;
    gridlines += `<line x1="${x}" y1="${topPad-6}" x2="${x}" y2="${chartH-16}" stroke="var(--line-soft)" stroke-width="0.5"></line>`;
    gridlines += `<text x="${x}" y="${topPad-10}" class="gantt-axis-label">${formatFecha(addDays(projectStart, d))}</text>`;
  }
  const today = new Date(); today.setHours(0,0,0,0);
  let todayLine = '';
  if(today >= projectStart && today <= projectEnd){
    const x = leftPad + Math.round((today - projectStart) / 86400000) * pxPerDay;
    todayLine = `<line x1="${x}" y1="${topPad-6}" x2="${x}" y2="${chartH-16}" class="gantt-today-line"></line>`;
  }

  const svg = `<svg viewBox="0 0 ${chartW + leftPad*2} ${chartH}" xmlns="http://www.w3.org/2000/svg">${gridlines}${todayLine}${bars}</svg>`;
  content.innerHTML = `<div class="gantt-chart-box">${svg}</div>`;
}

function renderGantt(){
  const schedule = computeGanttSchedule();
  renderGanttTable(schedule);
  renderGanttChart(schedule);
}

populateGanttCategorias();
