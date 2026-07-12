// ---------------- SECCION (plantas) ----------------
function parseLevels(nivelesStr){
  // separa "SOTANO / SEMISOTANO / PLANTA_BAJA" (indiferente) o
  // "PLANTA_BAJA → PLANTA_SUPERIOR" (cadena de respaldo)
  const isChain = nivelesStr.includes('→');
  const parts = nivelesStr.split(isChain ? '→' : '/').map(s => s.trim());
  return {isChain, levels: parts.map(p => p.replace(/\(opcional\)/,'').trim().match(/[A-Z_]+/)?.[0]).filter(Boolean)};
}

// Estancias adicionales disponibles SOLO en esta herramienta (uso
// practico del arquitecto), no forman parte de la cadena normativa de
// niveles_plantas.md -- se muestran con un estilo distinto (borde
// ambar) para que quede claro que no proceden del catalogo.
const EXTRA_TYPES_BY_LEVEL = {
  BAJO_CUBIERTA: ['BEDROOM', 'MASTER_BEDROOM', 'BATHROOM'],
  SEMISOTANO: ['STUDY'],
};

// Mismos valores que AREAS_POR_DEFECTO_M2 en
// seleccion_plantas_importer.py -- punto de partida razonable que el
// usuario ajusta, no un minimo normativo ni una imposicion.
const DEFAULT_AREA_M2 = {
  LIVING_ROOM:25, DINING_ROOM:14, KITCHEN:10, BEDROOM:12, MASTER_BEDROOM:15,
  BATHROOM:5.5, TOILET:3, ENTRANCE_HALL:4.5, STUDY:9, LAUNDRY:3, DRYING_AREA:2,
  STORAGE:3, STORAGE_ROOM:4, GARAGE:18, TECHNICAL_ROOM:3, CORRIDOR:4,
};

const SECTION = { selected: {} };  // level -> Map(RoomType -> {count, area})
let AREAS_LOCKED = false;  // si true, los campos de area son readonly (bloqueados al minimo normativo)
let TIPO_VIVIENDA = 'aislada';  // metadato guardado en la exportacion, no cambia la seleccion de estancias

function ensureSectionSelected(level){
  if(!SECTION.selected[level]) SECTION.selected[level] = new Map();
  return SECTION.selected[level];
}

function candidateTypesForLevel(level){
  const fromCatalog = FLOORS.filter(f => {
    if(f.type === 'CORRIDOR') return false;
    const {levels} = parseLevels(f.niveles);
    return levels.includes(level);
  }).map(f => f.type);
  const extra = EXTRA_TYPES_BY_LEVEL[level] || [];
  return [...fromCatalog, 'CORRIDOR', ...extra];
}

// Mismas 6 piezas que ViviendaMinimaValidator.REQUIRED_TYPES en Python
// (programa minimo, Decreto 29/2010 I.A.2.3) -- para dar feedback
// inmediato en el dashboard, antes de exportar y descubrirlo solo al
// intentar generar.
const PROGRAMA_MINIMO_TYPES = ['LIVING_ROOM', 'KITCHEN', 'BATHROOM', 'LAUNDRY', 'DRYING_AREA', 'STORAGE'];

function renderSectionSummary(){
  const el = document.getElementById('section-summary');
  if(!el) return;

  let totalRooms = 0, totalArea = 0;
  const presentTypes = new Set();
  const perLevel = [];

  LEVEL_ORDER.forEach(level => {
    const sel = ensureSectionSelected(level);
    if(sel.size === 0) return;
    let levelRooms = 0, levelArea = 0;
    sel.forEach((v, t) => {
      levelRooms += v.count;
      levelArea += v.count * v.area;
      presentTypes.add(t);
    });
    totalRooms += levelRooms;
    totalArea += levelArea;
    perLevel.push(`${LEVEL_LABEL[level]}: ${levelRooms} estancias, ${levelArea.toFixed(1)}m²`);
  });

  const faltan = PROGRAMA_MINIMO_TYPES.filter(t => !presentTypes.has(t));
  const programaHtml = faltan.length === 0
    ? `<span class="stat programa-ok">✓ programa mínimo completo</span>`
    : `<span class="stat programa-falta">✗ falta: ${faltan.map(t => DISPLAY[t]).join(', ')}</span>`;

  el.innerHTML = totalRooms === 0
    ? `<span class="stat">Sin estancias seleccionadas todavía.</span>`
    : `<span class="stat"><b>${totalRooms}</b> estancias, <b>${totalArea.toFixed(1)}m²</b> en total</span>`
      + perLevel.map(s => `<span class="stat">${s}</span>`).join('')
      + programaHtml;
}

// Mismos valores EXACTOS que TABLA_1/TABLA_2 en Python (ver
// estancia_minimum_area_validator.py, servicio_minimum_area_validator.py)
// -- retomado a peticion del usuario: las areas editables no avisaban
// si el valor declarado no alcanzaba el minimo real segun el numero
// total de estancias, dejando al usuario sin saber si "se estan
// ajustando en funcion del numero de estancias y de los requisitos".
const TABLA_1 = {1:[25], 2:[16,12], 3:[18,12,8], 4:[20,12,8,8], 5:[22,12,8,8,6]};
const TABLA_1_MAS_DE_CINCO = [25,12,8,8,8];
const MINIMO_ESTANCIA_ADICIONAL = 6.0;
const TABLA_2 = {
  1:{cocina:5, bano:5, lavadero:1.5, tendedero:1.5, almacenamiento:1},
  2:{cocina:7, bano:5, lavadero:1.5, tendedero:1.5, almacenamiento:2},
  3:{cocina:7, bano:5, lavadero:1.5, tendedero:1.5, almacenamiento:3},
  4:{cocina:9, bano:5, aseo:1.5, lavadero:1.5, tendedero:1.5, almacenamiento:4},
  5:{cocina:9, bano:5, aseo:1.5, lavadero:1.5, tendedero:1.5, almacenamiento:5},
};
const TABLA_2_MAS_DE_CINCO = {cocina:10, bano:5, aseo:1.5, lavadero:1.5, tendedero:1.5, almacenamiento:6};

function minimoEstancia(numEstancias, puesto){
  if(numEstancias <= 5){
    const fila = TABLA_1[numEstancias];
    if(!fila || puesto > fila.length) return null;
    return fila[puesto-1];
  }
  if(puesto <= 5) return TABLA_1_MAS_DE_CINCO[puesto-1];
  return MINIMO_ESTANCIA_ADICIONAL;
}

function tablaServiciosPara(numEstancias){
  if(TABLA_2[numEstancias]) return TABLA_2[numEstancias];
  if(numEstancias < 1) return TABLA_2[1];
  return TABLA_2_MAS_DE_CINCO;
}

// Calcula, para TODAS las estancias seleccionadas (todas las plantas a
// la vez, igual que hace GenerateBuildingUseCase con el ranking global),
// cuales no alcanzan el minimo real de Tabla 1/2 -- devuelve un Map
// "level|type" -> mensaje de aviso, para pintar cada chip en rojo si
// corresponde.
function computeAreaWarnings(){
  const allEntries = [];  // {level, type, count, area, category, subtype}
  LEVEL_ORDER.forEach(level => {
    const sel = ensureSectionSelected(level);
    sel.forEach((v, t) => {
      const p = PROPS[t];
      if(!p) return;
      allEntries.push({level, type:t, count:v.count, area:v.area, category:p.category, subtype:p.subtype});
    });
  });

  // total de ESTANCIAS (categoria "estancia", cuenta cada instancia -- 2
  // dormitorios cuentan como 2) -- mismo criterio que GenerateBuildingUseCase
  const totalEstancias = allEntries.filter(e => e.category === 'estancia')
    .reduce((s,e) => s + e.count, 0);

  const warnings = new Map();  // "level|type" -> mensaje

  // Tabla 1: ordenar TODAS las instancias de estancia por area declarada
  // descendente, asignar puesto 1..N (una entrada con count=2 genera 2
  // "instancias" del mismo tamano para el ranking, igual que en Python)
  const estanciaInstances = [];
  allEntries.filter(e => e.category === 'estancia').forEach(e => {
    for(let i=0;i<e.count;i++) estanciaInstances.push(e);
  });
  estanciaInstances.sort((a,b) => b.area - a.area);
  estanciaInstances.forEach((e, i) => {
    const puesto = i+1;
    const minimo = minimoEstancia(totalEstancias, puesto);
    if(minimo !== null && e.area < minimo){
      const key = `${e.level}|${e.type}`;
      warnings.set(key, `Tabla 1: puesto ${puesto} de ${totalEstancias} exige ≥${minimo}m² (declarado ${e.area}m²)`);
    }
  });

  // Tabla 2: por subtipo, minimo segun el total de estancias
  const tabla2Fila = tablaServiciosPara(totalEstancias);
  allEntries.filter(e => e.category === 'servicio' && e.subtype).forEach(e => {
    const minimo = tabla2Fila[e.subtype];
    if(minimo !== undefined && e.area < minimo){
      const key = `${e.level}|${e.type}`;
      warnings.set(key, `Tabla 2 (${e.subtype}): ${totalEstancias} estancias exige ≥${minimo}m² (declarado ${e.area}m²)`);
    }
  });

  return warnings;
}

function applyAreaWarnings(){
  const warnings = computeAreaWarnings();
  document.querySelectorAll('.chip.selected').forEach(chip => {
    const key = `${chip.dataset.level}|${chip.dataset.type}`;
    const areaInput = chip.querySelector('.chip-area');
    if(!areaInput) return;
    const msg = warnings.get(key);
    areaInput.classList.toggle('area-warn', !!msg);
    areaInput.title = msg || 'Área en m² de cada una';
  });
}

// Orden canonico para asignar "puesto" de Tabla 1 ANTES de saber areas
// reales (la generacion automatica calcula el area a partir del
// puesto, no al reves) -- salon siempre el mayor, luego el dormitorio
// principal, luego el resto. Coincide con la convencion ya usada en
// todo el proyecto (LIVING_ROOM = estancia mayor).
const CANONICAL_ESTANCIA_ORDER = ['LIVING_ROOM', 'MASTER_BEDROOM', 'BEDROOM', 'DINING_ROOM', 'STUDY'];

function recalculateAutoAreas(){
  const allEntries = [];
  LEVEL_ORDER.forEach(level => {
    const sel = ensureSectionSelected(level);
    sel.forEach((v, t) => allEntries.push({level, type:t, v}));
  });

  const estanciaEntries = allEntries.filter(e => PROPS[e.type] && PROPS[e.type].category === 'estancia');
  estanciaEntries.sort((a,b) => CANONICAL_ESTANCIA_ORDER.indexOf(a.type) - CANONICAL_ESTANCIA_ORDER.indexOf(b.type));
  const totalEstancias = estanciaEntries.reduce((s,e) => s + e.v.count, 0);

  let puesto = 1;
  estanciaEntries.forEach(e => {
    // si count>1 (varios dormitorios del mismo tipo), cada instancia
    // ocupa un puesto consecutivo -- se usa el MAS EXIGENTE (area mayor)
    // de los puestos que ocupa, para que TODAS las instancias cumplan
    // aunque compartan un unico valor de area en esta entrada.
    const puestosDeEsteGrupo = [];
    for(let i=0;i<e.v.count;i++){ puestosDeEsteGrupo.push(puesto); puesto++; }
    const minimo = Math.max(...puestosDeEsteGrupo.map(p => minimoEstancia(totalEstancias, p) || 0));
    e.v.area = minimo;
  });

  const tabla2Fila = tablaServiciosPara(totalEstancias);
  allEntries.filter(e => PROPS[e.type] && PROPS[e.type].category === 'servicio').forEach(e => {
    const subtype = PROPS[e.type].subtype;
    e.v.area = (subtype && tabla2Fila[subtype]) || DEFAULT_AREA_M2[e.type] || 10;
  });

  // circulacion (ENTRANCE_HALL, CORRIDOR) -- sin fila de Tabla 1/2 propia
  allEntries.filter(e => PROPS[e.type] && PROPS[e.type].category === 'circulacion').forEach(e => {
    e.v.area = DEFAULT_AREA_M2[e.type] || 4;
  });
}

function applyAutoConfig(){
  const dormitorios = Math.max(1, parseInt(document.getElementById('auto-dormitorios').value, 10) || 1);
  const plantas = parseInt(document.getElementById('auto-plantas').value, 10);
  TIPO_VIVIENDA = document.getElementById('auto-tipo-vivienda').value;

  SECTION.selected = {};
  const pbSet = ensureSectionSelected('PLANTA_BAJA');
  const nocheSet = plantas === 2 ? ensureSectionSelected('PLANTA_SUPERIOR') : pbSet;

  // programa minimo (dia/servicio) -- siempre en planta baja
  pbSet.set('LIVING_ROOM', {count:1, area:0});
  pbSet.set('KITCHEN', {count:1, area:0});
  pbSet.set('ENTRANCE_HALL', {count:1, area:0});
  pbSet.set('LAUNDRY', {count:1, area:0});
  pbSet.set('DRYING_AREA', {count:1, area:0});
  pbSet.set('STORAGE', {count:1, area:0});

  // dormitorios: 1 principal + (N-1) normales -- reglas confirmadas con
  // el usuario antes de implementar, no supuestas
  nocheSet.set('MASTER_BEDROOM', {count:1, area:0});
  const bedCount = dormitorios - 1;
  if(bedCount > 0) nocheSet.set('BEDROOM', {count:bedCount, area:0});

  // banos: 1 bano siempre (arriba, junto a los dormitorios); +1 aseo si
  // hay 3 o mas dormitorios -- el aseo va en PLANTA_BAJA, no arriba con
  // el resto de banos: el propio catalogo (FLOORS) ya declara TOILET
  // como "Fijo, sirve a zona social/visitas, no depende de dormitorios"
  // -- bug real encontrado al probar: colocarlo en planta superior
  // haria que el chip no se renderizase nunca (no esta en la lista de
  // tipos candidatos de esa planta segun el propio catalogo).
  nocheSet.set('BATHROOM', {count:1, area:0});
  if(dormitorios >= 3) pbSet.set('TOILET', {count:1, area:0});

  // pasillo en planta superior si hay 2 plantas -- necesario para que
  // el bano de arriba tenga acceso general (BanoAccesoGeneralValidator),
  // confirmado con un caso real que fallaba sin esto
  if(plantas === 2) nocheSet.set('CORRIDOR', {count:1, area:0});

  recalculateAutoAreas();

  AREAS_LOCKED = true;
  const lockCheckbox = document.getElementById('areas-lock-checkbox');
  if(lockCheckbox) lockCheckbox.checked = false;
  buildSection();
}

function buildSection(){
  const wrap = document.getElementById('section-wrap');
  let html = '';
  LEVEL_ORDER.slice().reverse().forEach(level => {
    const types = candidateTypesForLevel(level);
    const selected = ensureSectionSelected(level);
    const extraSet = new Set(EXTRA_TYPES_BY_LEVEL[level] || []);

    html += `<div class="level" data-level="${level}">
      <div class="lvl-label">${LEVEL_LABEL[level]}${LEVEL_RASANTE[level] ? `<span class="rasante">${LEVEL_RASANTE[level]}</span>` : ''}</div>`;
    types.forEach(t => {
      const isExtra = extraSet.has(t);
      const isSel = selected.has(t);
      const cls = ['chip', isExtra ? 'extra' : '', isSel ? 'selected' : ''].filter(Boolean).join(' ');
      const title = t === 'CORRIDOR' ? 'Circulación, disponible en todas las plantas' :
        (isExtra ? 'Adicional de esta herramienta, no procede de niveles_plantas.md' : (FLOORS.find(f=>f.type===t)||{}).notas || '');
      const vals = isSel ? selected.get(t) : {count:1, area: DEFAULT_AREA_M2[t] || 10};
      const readonlyAttr = AREAS_LOCKED ? 'readonly' : '';
      const controls = isSel ? `<span class="chip-controls">
          <input type="number" class="chip-count" min="1" step="1" value="${vals.count}" title="Cantidad de estancias de este tipo">
          <span class="unit">×</span>
          <input type="number" class="chip-area" min="1" step="0.5" value="${vals.area}" ${readonlyAttr} title="Área en m² de cada una">
          <span class="unit">m²</span>
        </span>` : '';
      html += `<span class="${cls}" data-type="${t}" data-level="${level}" title="${title}">${DISPLAY[t]}${controls}</span>`;
    });
    html += `</div>`;
  });
  wrap.innerHTML = html;

  wrap.querySelectorAll('.chip').forEach(chip => {
    chip.addEventListener('click', (ev) => {
      if(ev.target.closest('.chip-controls')) return;  // click en los inputs no debe (des)seleccionar
      const level = chip.dataset.level, t = chip.dataset.type;
      const sel = ensureSectionSelected(level);
      if(sel.has(t)) sel.delete(t);
      else sel.set(t, {count: 1, area: DEFAULT_AREA_M2[t] || 10});
      buildSection();  // re-renderiza para mostrar/ocultar los controles de este chip
    });
  });

  wrap.querySelectorAll('.chip-count, .chip-area').forEach(input => {
    input.addEventListener('click', ev => ev.stopPropagation());
    input.addEventListener('change', () => {
      const chip = input.closest('.chip');
      const level = chip.dataset.level, t = chip.dataset.type;
      const sel = ensureSectionSelected(level);
      const current = sel.get(t) || {count:1, area: DEFAULT_AREA_M2[t] || 10};
      if(input.classList.contains('chip-count')) current.count = Math.max(1, parseInt(input.value, 10) || 1);
      else current.area = Math.max(0.5, parseFloat(input.value) || (DEFAULT_AREA_M2[t] || 10));
      sel.set(t, current);
      renderSectionSummary();
      applyAreaWarnings();
    });
  });

  renderSectionSummary();
  applyAreaWarnings();
}

function filterSection(query){
  const q = query.trim().toLowerCase();
  document.querySelectorAll('#section-wrap .chip').forEach(chip => {
    const t = chip.dataset.type;
    const match = !q || DISPLAY[t].toLowerCase().includes(q) || t.toLowerCase().includes(q);
    chip.style.display = match ? '' : 'none';
  });
}

function buildSeleccionPayload(){
  const levels = {};
  LEVEL_ORDER.forEach(level => {
    const sel = ensureSectionSelected(level);
    if(sel.size > 0){
      levels[level] = Array.from(sel.entries()).map(([type, v]) => (
        {type, count: v.count, area_m2: v.area}
      ));
    }
  });
  return {
    version: 2,
    levels,
    tipo_vivienda: TIPO_VIVIENDA,
    nota: 'Seleccion de esta herramienta de exploracion (catalogo), con cantidad y area '
        + 'declaradas por el usuario -- ya no son valores genericos de relleno, pero siguen '
        + 'siendo una PRIMERA aproximacion a revisar antes de un proyecto real. '
        + 'Las estancias bajo "extra" (bajo cubierta: dormitorios/bano; semisotano: despacho) '
        + 'son uso practico de esta herramienta, no proceden de niveles_plantas.md. '
        + 'Para generar directamente, usa el boton "Generar plano ahora" -- este archivo '
        + 'exportado es solo para quien prefiera el CLI a mano '
        + '(python -m housing_generator.interface.cli.main --import-seleccion '
        + 'seleccion_plantas.json --output edificio.json) o quiera archivar la seleccion.',
  };
}

function exportSectionSelection(){
  const payload = buildSeleccionPayload();

  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'seleccion_plantas.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
