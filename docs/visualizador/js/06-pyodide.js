// ---------------- GENERADOR REAL EN EL NAVEGADOR (Pyodide) ----------------
// Retomado de una pregunta directa del usuario: el flujo anterior obligaba
// a exportar un JSON, salir al terminal a ejecutar el CLI, y volver a
// cargar el resultado en el visor -- un puente MANUAL entre dos mundos
// que nunca se hablaban. Esto ejecuta el generador real (housing_generator,
// el mismo codigo Python de siempre, sin reescribirlo) DENTRO del propio
// navegador via Pyodide (Python compilado a WebAssembly) -- nada de
// terminal, nada de descargar/subir archivos para el caso normal.
// shapely/geos estan oficialmente soportados por Pyodide (confirmado en
// el changelog oficial antes de construir esto, no asumido); scipy/numpy
// son parte del stack cientifico estandar; networkx es Python puro, se
// instala via micropip sin problema.
let PYODIDE_INSTANCE = null;
let PYODIDE_LOADING = null;

function setGenerateStatus(msg, kind){
  const el = document.getElementById('generate-status');
  el.className = 'generate-status' + (kind ? ' '+kind : '');
  el.innerHTML = kind === 'loading' ? '<span class="bar"></span>' + escapeXml(msg) : escapeXml(msg);
}

async function ensurePyodideReady(onProgress){
  if(PYODIDE_INSTANCE) return PYODIDE_INSTANCE;
  if(PYODIDE_LOADING) return PYODIDE_LOADING;

  PYODIDE_LOADING = (async () => {
    onProgress('Cargando Python en el navegador (Pyodide, primera vez tarda unos segundos)...');
    const pyodide = await loadPyodide();

    onProgress('Instalando shapely, numpy, scipy...');
    await pyodide.loadPackage(['shapely', 'numpy', 'scipy']);

    onProgress('Instalando networkx...');
    await pyodide.loadPackage('micropip');
    const micropip = pyodide.pyimport('micropip');
    await micropip.install('networkx');

    onProgress('Cargando housing_generator...');
    pyodide.FS.mkdirTree('/home/pyodide/src');
    for(const [relPath, content] of Object.entries(PY_BUNDLE)){
      const fullPath = '/home/pyodide/src/' + relPath;
      const dir = fullPath.substring(0, fullPath.lastIndexOf('/'));
      pyodide.FS.mkdirTree(dir);
      pyodide.FS.writeFile(fullPath, content);
    }
    pyodide.runPython("import sys\nsys.path.insert(0, '/home/pyodide/src')\n");

    PYODIDE_INSTANCE = pyodide;
    return pyodide;
  })();

  return PYODIDE_LOADING;
}

async function generarEdificioReal(seleccionPayload, lotW, lotH, seed, maxIterations, retrySeeds, viviendaAccesible, onProgress){
  const pyodide = await ensurePyodideReady(onProgress);
  onProgress('Buscando una distribucion valida (puede reintentar varias semillas)...');

  pyodide.globals.set('payload_json_str', JSON.stringify(seleccionPayload));
  pyodide.globals.set('lot_w_js', lotW);
  pyodide.globals.set('lot_h_js', lotH);
  pyodide.globals.set('seed_js', seed);
  pyodide.globals.set('max_it_js', maxIterations);
  pyodide.globals.set('retry_js', retrySeeds);
  pyodide.globals.set('accesible_js', viviendaAccesible);

  const pyCode = [
    'import json',
    'from housing_generator.interface.browser.bridge import generar_edificio',
    'payload = json.loads(payload_json_str)',
    'resultado = generar_edificio(',
    '    payload, float(lot_w_js), float(lot_h_js),',
    '    seed=int(seed_js), max_iterations=int(max_it_js),',
    '    retry_seeds=int(retry_js), vivienda_accesible=bool(accesible_js),',
    ')',
    'json.dumps(resultado)',
  ].join('\n');
  const resultStr = await pyodide.runPythonAsync(pyCode);
  return JSON.parse(resultStr);
}

async function handleGenerateNow(){
  const btn = document.getElementById('generate-now');
  const payload = buildSeleccionPayload();
  if(Object.keys(payload.levels).length === 0){
    setGenerateStatus('Selecciona al menos una estancia antes de generar (o usa "Generar seleccion" arriba).', 'error');
    return;
  }

  const lotW = parseFloat(document.getElementById('gen-lot-w').value) || 14;
  const lotH = parseFloat(document.getElementById('gen-lot-h').value) || 16;
  const seed = parseInt(document.getElementById('gen-seed').value, 10) || 1;
  const maxIterations = parseInt(document.getElementById('gen-iterations').value, 10) || 4000;
  const accesible = document.getElementById('gen-accesible').checked;

  btn.disabled = true;
  setGenerateStatus('Iniciando...', 'loading');
  try{
    const result = await generarEdificioReal(payload, lotW, lotH, seed, maxIterations, 5, accesible, (msg) => setGenerateStatus(msg, 'loading'));
    if(!result.ok){
      setGenerateStatus('No se pudo generar: ' + result.error, 'error');
      return;
    }
    LOADED_PLANS = Object.entries(result.floors).map(([level, data]) => ({
      label: labelForPlanFile(level + '.json'), data,
    }));
    ACTIVE_PLAN = 0;
    PLANO_TRANSFORM = {mirrorH: false, mirrorV: false, rotation: 0};
    const semillaMsg = result.reintentos > 0
      ? ' (semilla ' + seed + ' no convergio, funciono la ' + result.semilla_usada + ' tras ' + (result.reintentos+1) + ' intentos)'
      : ' (semilla ' + result.semilla_usada + ')';
    setGenerateStatus('Generado correctamente' + semillaMsg + '. Mostrando en el Visor de plano.', 'ok');

    document.querySelector('[data-tab="plano"]').dispatchEvent(new Event('click', {bubbles:true}));
    renderPlanoTabs();
    renderPlano();
  } catch(err){
    setGenerateStatus('Error inesperado: ' + (err && err.message ? err.message : err), 'error');
  } finally {
    btn.disabled = false;
  }
}

function escapeXml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
