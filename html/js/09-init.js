// ---------------- init + tabs ----------------
initParcelaPreview();
buildMatrix(); buildLegend(); buildSection(); buildCards(); buildSynergyLegend(); renderNetFilters();
const SCORES = computeScores();
buildNetwork(SCORES); buildScoreBars(SCORES); buildRankings();
document.getElementById('export-section').addEventListener('click', exportSectionSelection);
document.getElementById('generate-now').addEventListener('click', handleGenerateNow);
document.getElementById('gantt-start-date').valueAsDate = new Date();
document.getElementById('gantt-add-fase').addEventListener('click', handleAddFase);
document.getElementById('gantt-start-date').addEventListener('change', renderGantt);
renderCatalogoGrid();
document.getElementById('clear-section').addEventListener('click', () => {
  if(!confirm('¿Vaciar toda la selección de todas las plantas?')) return;
  SECTION.selected = {};
  buildSection();
});
document.getElementById('auto-apply').addEventListener('click', applyAutoConfig);
document.getElementById('export-schedule').addEventListener('click', exportScheduleCSV);
document.getElementById('auto-tipo-vivienda').addEventListener('change', (ev) => {
  TIPO_VIVIENDA = ev.target.value;
});
document.getElementById('areas-lock-checkbox').addEventListener('change', (ev) => {
  AREAS_LOCKED = !ev.target.checked;
  buildSection();
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    // acotado al grupo (flow-indicator o subtabs-row) del propio tab --
    // un manejador global rompia el estado de otros grupos al volver a
    // visitarlos (los dejaba sin ningun panel activo). Ver [ARCH:zonas].
    const grupo = tab.closest('.flow-indicator, .subtabs-row') || document;
    const hermanos = grupo.querySelectorAll('.tab');
    hermanos.forEach(t => {
      t.classList.remove('active');
      const panel = document.getElementById('panel-'+t.dataset.tab);
      if(panel) panel.classList.remove('active');
    });
    tab.classList.add('active');
    document.getElementById('panel-'+tab.dataset.tab).classList.add('active');
  });
});

document.querySelectorAll('.zona-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.zona-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.zona-panel').forEach(z => z.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('zona-'+btn.dataset.zona).classList.add('active');
  });
});

// boton "volver al inicio" en la cabecera -- a peticion del usuario
// ("ni puedo volver al inicio... unicamente tenemos este cartel fijo").
// Reutiliza el mismo mecanismo real de cambio de zona, no una copia
// paralela de la logica.
const tituloHome = document.getElementById('titleblock-home');
if(tituloHome){
  tituloHome.addEventListener('click', () => {
    document.querySelector('[data-zona="parcela"]').dispatchEvent(new Event('click', {bubbles:true}));
    window.scrollTo({top: 0, behavior: 'smooth'});
  });
}

// boton "confirmar parcela y continuar a Diseño" -- a peticion del
// usuario ("necesitaria un boton de conexion entre la zona 0 y la
// zona 1 para facilitar la conexion de los datos"). Los campos ya
// se comparten de verdad entre zonas (mismos id, leidos directamente
// por 06-pyodide.js al generar) -- este boton es solo navegacion +
// marca de progreso, no mueve datos por separado.
const confirmarParcelaBtn = document.getElementById('confirmar-parcela');
if(confirmarParcelaBtn){
  confirmarParcelaBtn.addEventListener('click', () => {
    document.querySelector('[data-zona="parcela"]').classList.add('done');
    document.querySelector('[data-zona="diseno"]').dispatchEvent(new Event('click', {bubbles:true}));
    window.scrollTo({top: 0, behavior: 'smooth'});
  });
}

document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.relaciones-view').forEach(v => v.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('view-'+btn.dataset.view).classList.add('active');
  });
});

document.querySelectorAll('.nota-indicador').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelector('[data-zona="consulta"]').dispatchEvent(new Event('click', {bubbles:true}));
    document.querySelector('[data-tab="notas"]').dispatchEvent(new Event('click', {bubbles:true}));
    const bloque = document.getElementById(btn.dataset.nota);
    document.querySelectorAll('.nota-bloque').forEach(b => b.classList.remove('highlight'));
    bloque.classList.add('highlight');
    if(bloque.scrollIntoView) bloque.scrollIntoView({behavior:'smooth', block:'start'});
  });
});

document.getElementById('search-matrix').addEventListener('input', e => filterMatrix(e.target.value));
document.getElementById('search-section').addEventListener('input', e => filterSection(e.target.value));
document.getElementById('search-cards').addEventListener('input', e => filterCards(e.target.value));

document.getElementById('plano-file-input').addEventListener('change', async (ev) => {
  const files = Array.from(ev.target.files);
  if(files.length === 0) return;

  const content = document.getElementById('plano-content');
  let loaded;
  try{
    loaded = await Promise.all(files.map(f => f.text().then(t => ({file: f, data: JSON.parse(t)}))));
  } catch(err){
    content.innerHTML = `<div class="plano-empty plano-error">No se pudo leer uno de los archivos como JSON válido: ${escapeXml(err.message)}</div>`;
    return;
  }

  // Formato consolidado unico (plano_generado.json, boton "exportar
  // plano generado" del propio visor): un solo archivo con
  // {"floors": {"<etiqueta>": {rooms, doors, metadata}, ...}} -- se
  // detecta ANTES de la validacion multi-archivo de mas abajo, ya que
  // este SI es valido aunque no tenga "rooms" en el nivel superior
  // (esta un nivel mas adentro, por planta). Ver [ARCH:exportar-plano-generado].
  if(loaded.length === 1 && loaded[0].data.floors && typeof loaded[0].data.floors === 'object'){
    const floors = loaded[0].data.floors;
    const entradas = Object.entries(floors);
    const invalidas = entradas.filter(([, data]) => !Array.isArray(data.rooms));
    if(invalidas.length === 0 && entradas.length > 0){
      LOADED_PLANS = entradas.map(([label, data]) => ({label, data}));
      ACTIVE_PLAN = 0;
      PLANO_TRANSFORM = {mirrorH: false, mirrorV: false, rotation: 0};
      renderPlanoTabs();
      renderPlano();
      return;
    }
  }

  // BUG REAL encontrado por el usuario probando de verdad: cargar
  // "seleccion_plantas.json" (la exportacion del paso "Programa y
  // generacion" -- tipos y cantidades, SIN geometria resuelta) en vez de
  // un plano ya generado por el CLI (con "rooms"/"bounds") rompia con
  // un TypeError sin capturar a medio camino -- el archivo se veia
  // "seleccionado" pero no pasaba nada mas, sin ningun mensaje. Son dos
  // formatos JSON distintos que salen del mismo dashboard; ahora se
  // detecta explicitamente cual es cual, con un mensaje que dice que
  // hacer, en vez de fallar en silencio.
  const invalid = loaded.filter(({data}) => !Array.isArray(data.rooms));
  if(invalid.length > 0){
    const names = invalid.map(({file}) => file.name).join(', ');
    const looksLikeSeleccion = invalid.some(({data}) => data.levels);
    content.innerHTML = `<div class="plano-empty plano-error">
      <b>${escapeXml(names)}</b> no tiene el formato de un plano generado (falta "rooms").<br>
      ${looksLikeSeleccion
        ? 'Este parece ser un archivo de "selección de plantas" (del paso "Programa y generación") -- usa el botón "Generar plano ahora" en ese paso, o genéralo por el CLI: <code>python -m housing_generator.interface.cli.main --import-seleccion ' + escapeXml(invalid[0].file.name) + ' --output edificio.json</code>, y carga aquí el <code>edificio_planta_*.json</code> resultante, no este archivo.'
        : 'Carga el JSON que produce el CLI (<code>--output layout.json</code>, o los <code>edificio_planta_*.json</code> de <code>--import-seleccion</code>).'}
    </div>`;
    return;
  }

  loaded.sort((a,b) => a.file.name.localeCompare(b.file.name));
  LOADED_PLANS = loaded.map(({file, data}) => ({label: labelForPlanFile(file.name), data}));
  ACTIVE_PLAN = 0;
  PLANO_TRANSFORM = {mirrorH: false, mirrorV: false, rotation: 0};
  renderPlanoTabs();
  renderPlano();
});

function updateMirrorButtonStates(){
  document.getElementById('mirror-h').classList.toggle('active', PLANO_TRANSFORM.mirrorH);
  document.getElementById('mirror-v').classList.toggle('active', PLANO_TRANSFORM.mirrorV);
  document.getElementById('mirror-rotate').classList.toggle('active', PLANO_TRANSFORM.rotation !== 0);
}

document.getElementById('mirror-h').addEventListener('click', () => {
  setPlanoTransform({mirrorH: !PLANO_TRANSFORM.mirrorH});
  updateMirrorButtonStates();
});
document.getElementById('mirror-v').addEventListener('click', () => {
  setPlanoTransform({mirrorV: !PLANO_TRANSFORM.mirrorV});
  updateMirrorButtonStates();
});
document.getElementById('mirror-rotate').addEventListener('click', () => {
  setPlanoTransform({rotation: (PLANO_TRANSFORM.rotation + 90) % 360});
  updateMirrorButtonStates();
});
document.getElementById('mirror-reset').addEventListener('click', () => {
  setPlanoTransform({mirrorH: false, mirrorV: false, rotation: 0});
  updateMirrorButtonStates();
});
document.getElementById('export-plano').addEventListener('click', exportarPlanoGenerado);

// toggle del panel de retranqueo por lado -- a peticion del usuario
// ("el retranqueo (m) no se puede desplegar para indicar los
// diferentes retranqueos a cada colindante o vial").
const retranqueoLadoToggle = document.getElementById('retranqueo-lado-toggle');
const retranqueoLadoPanel = document.getElementById('retranqueo-lado-panel');
if(retranqueoLadoToggle && retranqueoLadoPanel){
  retranqueoLadoToggle.addEventListener('click', () => {
    const abierto = !retranqueoLadoPanel.hidden;
    retranqueoLadoPanel.hidden = abierto;
    retranqueoLadoToggle.textContent = abierto ? 'Retranqueo distinto por lado ▾' : 'Retranqueo distinto por lado ▴';
  });
}
