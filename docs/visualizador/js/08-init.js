// ---------------- init + tabs ----------------
buildMatrix(); buildLegend(); buildSection(); buildCards(); buildSynergyLegend(); renderNetFilters();
const SCORES = computeScores();
buildNetwork(SCORES); buildScoreBars(SCORES); buildRankings();
document.getElementById('export-section').addEventListener('click', exportSectionSelection);
document.getElementById('generate-now').addEventListener('click', handleGenerateNow);
document.getElementById('gantt-start-date').valueAsDate = new Date();
document.getElementById('gantt-add-fase').addEventListener('click', handleAddFase);
document.getElementById('gantt-start-date').addEventListener('change', renderGantt);
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
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-'+tab.dataset.tab).classList.add('active');
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

  // BUG REAL encontrado por el usuario probando de verdad: cargar
  // "seleccion_plantas.json" (la exportacion de la pestaña Sección
  // vertical -- tipos y cantidades, SIN geometria resuelta) en vez de
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
        ? 'Este parece ser un archivo de "selección de plantas" (de la pestaña Sección vertical) -- primero hay que generarlo de verdad: <code>python -m housing_generator.interface.cli.main --import-seleccion ' + escapeXml(invalid[0].file.name) + ' --output edificio.json</code>, y cargar aquí el <code>edificio_planta_*.json</code> resultante, no este archivo.'
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