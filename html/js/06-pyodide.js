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
//
// Ejecucion en un Web Worker, no en el hilo principal: una busqueda de
// recocido simulado de miles de iteraciones bloqueaba la pestana entera
// sin forma de cancelar -- identificado en una auditoria de la
// herramienta, corregido a peticion del usuario. Un Worker normal
// (`new Worker('archivo.js')`) no arranca desde `file://` en Chromium
// (mismo bloqueo de origen que ya afecto a fetch()/modulos ES,
// investigado y documentado en docs/GUIA_USO.md -- por eso el dashboard
// entero usa <script src=""> clasicos) -- se sortea construyendo el
// Worker desde un Blob URL (contenido ya en memoria, nunca se llega a
// pedir un recurso file://), la tecnica estandar para exactamente este
// caso. Si el Worker no llega a arrancar (entorno no previsto), se cae
// automaticamente al camino de siempre (Pyodide en el hilo principal,
// `initPyodideMainThreadFallback`) en vez de dejar la herramienta rota.
const PYODIDE_WORKER_SOURCE = [
  "importScripts('https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.js');",
  '',
  'let pyodide = null;',
  '',
  'async function initPyodideInWorker(bundle){',
  "  postMessage({type: 'progress', message: 'Cargando Python en el navegador (Pyodide, primera vez tarda unos segundos)...'});",
  '  pyodide = await loadPyodide();',
  '',
  "  postMessage({type: 'progress', message: 'Instalando shapely, numpy, scipy...'});",
  "  await pyodide.loadPackage(['shapely', 'numpy', 'scipy']);",
  '',
  "  postMessage({type: 'progress', message: 'Instalando networkx...'});",
  "  await pyodide.loadPackage('micropip');",
  "  const micropip = pyodide.pyimport('micropip');",
  "  await micropip.install('networkx');",
  '',
  "  postMessage({type: 'progress', message: 'Cargando housing_generator...'});",
  "  pyodide.FS.mkdirTree('/home/pyodide/src');",
  '  for(const relPath in bundle){',
  '    const content = bundle[relPath];',
  "    const fullPath = '/home/pyodide/src/' + relPath;",
  "    const dir = fullPath.substring(0, fullPath.lastIndexOf('/'));",
  '    pyodide.FS.mkdirTree(dir);',
  '    pyodide.FS.writeFile(fullPath, content);',
  '  }',
  '  pyodide.runPython("import sys");',
  '  pyodide.runPython("sys.path.insert(0, \'/home/pyodide/src\')");',
  '}',
  '',
  'self.onmessage = async function(ev){',
  '  const msg = ev.data;',
  "  if(msg.type === 'init'){",
  '    try{',
  '      await initPyodideInWorker(msg.bundle);',
  "      postMessage({type: 'ready'});",
  '    } catch(err){',
  "      postMessage({type: 'error', id: null, message: (err && err.message) ? err.message : String(err)});",
  '    }',
  '    return;',
  '  }',
  "  if(msg.type === 'run'){",
  '    try{',
  '      for(const key in msg.globals){',
  '        pyodide.globals.set(key, msg.globals[key]);',
  '      }',
  '      const value = await pyodide.runPythonAsync(msg.code);',
  "      postMessage({type: 'result', id: msg.id, value: value});",
  '    } catch(err){',
  "      postMessage({type: 'error', id: msg.id, message: (err && err.message) ? err.message : String(err)});",
  '    }',
  '  }',
  '};',
].join('\n');

let PYODIDE_MODE = null;               // 'worker' | 'fallback' -- decidido UNA vez
let PYODIDE_BACKEND_READY = null;      // promesa singleton de "listo" (worker o fallback)
let PYODIDE_WORKER = null;
let PYODIDE_FALLBACK_INSTANCE = null;  // pyodide en el hilo principal, solo si el Worker no arranco
let pyodideCallCounter = 0;
const pyodidePendingCalls = new Map(); // id -> {resolve, reject}
let pyodideCurrentOnProgress = null;
let pyodideDispatchQueue = Promise.resolve(); // serializa el ENVIO de cada llamada, ver runPyodideCode

function setGenerateStatus(msg, kind){
  const el = document.getElementById('generate-status');
  el.className = 'generate-status' + (kind ? ' '+kind : '');
  el.innerHTML = kind === 'loading' ? '<span class="bar"></span>' + escapeXml(msg) : escapeXml(msg);
}

function tryInitPyodideWorker(onProgress){
  return new Promise((resolve, reject) => {
    let worker;
    try{
      const blob = new Blob([PYODIDE_WORKER_SOURCE], {type: 'application/javascript'});
      worker = new Worker(URL.createObjectURL(blob));
    } catch(err){
      reject(err);
      return;
    }

    worker.onerror = (ev) => {
      worker.terminate();
      reject(new Error(ev && ev.message ? ev.message : 'fallo desconocido arrancando el Worker de Pyodide'));
    };
    worker.onmessage = (ev) => {
      const msg = ev.data;
      if(msg.type === 'progress'){
        onProgress(msg.message);
      } else if(msg.type === 'ready'){
        PYODIDE_WORKER = worker;
        PYODIDE_MODE = 'worker';
        worker.onmessage = handlePyodideWorkerMessage;
        worker.onerror = handlePyodideWorkerCrash;
        resolve();
      } else if(msg.type === 'error'){
        worker.terminate();
        reject(new Error(msg.message));
      }
    };
    worker.postMessage({type: 'init', bundle: PY_BUNDLE});
  });
}

async function initPyodideMainThreadFallback(onProgress){
  // Camino de respaldo: identico al que usaba siempre esta herramienta
  // antes de mover la ejecucion a un Worker -- Pyodide en el hilo
  // principal, sin proteccion frente al bloqueo de la pestana. Solo se
  // usa si tryInitPyodideWorker() no consigue arrancar (entorno donde
  // el Worker via Blob no esta disponible por algun motivo no previsto)
  // -- preferible a dejar la herramienta rota.
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

  PYODIDE_FALLBACK_INSTANCE = pyodide;
  PYODIDE_MODE = 'fallback';
}

function handlePyodideWorkerMessage(ev){
  const msg = ev.data;
  if(msg.type === 'progress'){
    if(pyodideCurrentOnProgress) pyodideCurrentOnProgress(msg.message);
    return;
  }
  const pending = pyodidePendingCalls.get(msg.id);
  if(!pending) return;
  pyodidePendingCalls.delete(msg.id);
  if(msg.type === 'result'){
    pending.resolve(msg.value);
  } else if(msg.type === 'error'){
    pending.reject(new Error(msg.message));
  }
}

function handlePyodideWorkerCrash(ev){
  // el Worker ya estaba confirmado y funcionando (post-ready) -- si se
  // cae a mitad de una ejecucion, cualquier llamada pendiente se
  // quedaria esperando una respuesta que nunca llega (el mismo
  // "congelado" que se queria evitar con todo este cambio). Se
  // rechazan todas explicitamente en vez de dejarlas colgadas.
  console.error('handlePyodideWorkerCrash: el Worker de Pyodide se detuvo inesperadamente', ev);
  const error = new Error('El Worker de Pyodide se detuvo inesperadamente: ' + (ev && ev.message ? ev.message : ev));
  for(const pending of pyodidePendingCalls.values()){
    pending.reject(error);
  }
  pyodidePendingCalls.clear();
}

function ensurePyodideBackendReady(onProgress){
  if(PYODIDE_BACKEND_READY) return PYODIDE_BACKEND_READY;

  PYODIDE_BACKEND_READY = tryInitPyodideWorker(onProgress).catch((err) => {
    console.warn('ensurePyodideBackendReady: el Worker de Pyodide no arranco, usando el hilo principal como respaldo', err);
    return initPyodideMainThreadFallback(onProgress);
  });

  return PYODIDE_BACKEND_READY;
}

async function runPyodideCode(pyCode, globalsToSet, onProgress){
  await ensurePyodideBackendReady(onProgress);

  const id = ++pyodideCallCounter;
  const resultPromise = new Promise((resolve, reject) => {
    pyodidePendingCalls.set(id, {resolve, reject});
  });

  // serializa el ENVIO real de cada llamada -- dos llamadas a Pyodide
  // (p.ej. reanalizarZonaAfeccionSiHayImportada disparandose en cada
  // pulsacion de tecla del campo de retranqueo) no deben solaparse
  // contra la MISMA instancia compartida (Worker o hilo principal):
  // compartir pyodide.globals entre dos ejecuciones en vuelo a la vez
  // ya era una condicion de carrera real antes de este cambio, no solo
  // teorica.
  pyodideDispatchQueue = pyodideDispatchQueue.then(() => {
    pyodideCurrentOnProgress = onProgress;
    if(PYODIDE_MODE === 'worker'){
      PYODIDE_WORKER.postMessage({type: 'run', id, code: pyCode, globals: globalsToSet});
    } else {
      for(const [key, value] of Object.entries(globalsToSet)){
        PYODIDE_FALLBACK_INSTANCE.globals.set(key, value);
      }
      PYODIDE_FALLBACK_INSTANCE.runPythonAsync(pyCode)
        .then((value) => {
          const pending = pyodidePendingCalls.get(id);
          if(pending){ pyodidePendingCalls.delete(id); pending.resolve(value); }
        })
        .catch((err) => {
          const pending = pyodidePendingCalls.get(id);
          if(pending){ pyodidePendingCalls.delete(id); pending.reject(err); }
        });
    }
    // no dejar que un fallo de ESTA llamada bloquee el envio de la
    // siguiente en la cola -- resultPromise ya propaga el error a
    // quien hizo esta llamada concreta.
    return resultPromise.catch(() => {});
  });

  return resultPromise;
}

async function generarEdificioReal(seleccionPayload, lotW, lotH, seed, maxIterations, retrySeeds, viviendaAccesible, retranqueoM, retranqueoIncremento, edificabilidad, ocupacionMaxima, alturaMaxima, frenteMinimo, streetSide, poligonoRealCoords, clasificacionSuelo, retranqueoPorLado, fondoEdificacion, lineaEdificacion, onProgress){
  onProgress('Buscando una distribucion valida (puede reintentar varias semillas)...');

  // street_side es un string fijo (viene de un <select> con opciones
  // controladas, no puede ser null/vacio) -- sin el riesgo de JsNull
  // que afecta a los valores numericos opcionales, seguro via globals.set()
  // (aplicado dentro del Worker/fallback, ver runPyodideCode).
  const globalsToSet = {
    payload_json_str: JSON.stringify(seleccionPayload),
    lot_w_js: lotW,
    lot_h_js: lotH,
    seed_js: seed,
    max_it_js: maxIterations,
    retry_js: retrySeeds,
    accesible_js: viviendaAccesible,
    street_side_js: streetSide || 'south',
  };

  // BUG REAL encontrado probando en un navegador real (Pyodide de
  // verdad, no accesible en este entorno de desarrollo -- CDN
  // bloqueado): `pyodide.globals.set('x', null)` NO se convierte a
  // `None` de Python como asumia el comentario anterior -- llega como
  // un objeto `JsNull` (proxy de JS), y `JsNull is not None` da
  // `True`, asi que `float(JsNull_instance)` fallaba con
  // "TypeError: float() argument must be a string or a real number,
  // not 'JsNull'". Corregido evitando el paso por variable global
  // para estos valores -- se construye el literal Python DIRECTAMENTE
  // como texto (numero real o la palabra `None`), sin pasar nunca por
  // la conversion null->None de pyodide.globals.set(), que resulto no
  // ser fiable para este caso. Mismo patron para los 4 parametros
  // urbanisticos nuevos (Zona 0) -- misma clase de bug, mismo arreglo.
  const literalOpcional = (valor, envoltorio) => {
    const esNumeroValido = valor !== null && valor !== undefined && !isNaN(valor);
    return esNumeroValido ? `${envoltorio}(${JSON.stringify(valor)})` : 'None';
  };
  const retranqueoLiteral = literalOpcional(retranqueoM, 'float');
  const retranqueoIncrementoLiteral = literalOpcional(retranqueoIncremento, 'float');
  const edificabilidadLiteral = literalOpcional(edificabilidad, 'float');
  const ocupacionMaximaLiteral = literalOpcional(ocupacionMaxima, 'float');
  const alturaMaximaLiteral = literalOpcional(alturaMaxima, 'int');
  const frenteMinimoLiteral = literalOpcional(frenteMinimo, 'float');
  const fondoEdificacionLiteral = literalOpcional(fondoEdificacion, 'float');
  const lineaEdificacionLiteral = literalOpcional(lineaEdificacion, 'float');
  // poligonoRealCoords: array anidado (lista de [x,y]), no un numero
  // simple -- se pasa como JSON embebido directamente en el codigo
  // Python (mismo patron "literal directo, no variable global" que
  // evita el bug de JsNull), en vez de por pyodide.globals.set(),
  // para no depender de como Pyodide convierta arrays anidados.
  const poligonoRealLiteral = (poligonoRealCoords && poligonoRealCoords.length > 0)
    ? `json.loads(${JSON.stringify(JSON.stringify(poligonoRealCoords))})` : 'None';
  // clasificacionSuelo: lista de strings, mismo patron que
  // poligonoRealCoords -- JSON embebido directo, no variable global.
  const clasificacionSueloLiteral = (clasificacionSuelo && clasificacionSuelo.length > 0)
    ? `json.loads(${JSON.stringify(JSON.stringify(clasificacionSuelo))})` : 'None';
  // retranqueoPorLado: dict simple {lado: numero} -- mismo patron de
  // JSON embebido directo.
  const retranqueoPorLadoLiteral = (retranqueoPorLado && Object.keys(retranqueoPorLado).length > 0)
    ? `json.loads(${JSON.stringify(JSON.stringify(retranqueoPorLado))})` : 'None';

  const pyCode = [
    'import json',
    'from housing_generator.interface.browser.bridge import generar_edificio',
    'payload = json.loads(payload_json_str)',
    'resultado = generar_edificio(',
    '    payload, float(lot_w_js), float(lot_h_js),',
    '    seed=int(seed_js), max_iterations=int(max_it_js),',
    '    retry_seeds=int(retry_js), vivienda_accesible=bool(accesible_js),',
    `    retranqueo_m=${retranqueoLiteral},`,
    `    retranqueo_incremento_por_planta_m=${retranqueoIncrementoLiteral},`,
    `    coeficiente_edificabilidad=${edificabilidadLiteral},`,
    `    ocupacion_maxima_pct=${ocupacionMaximaLiteral},`,
    `    altura_maxima_plantas=${alturaMaximaLiteral},`,
    `    frente_minimo_m=${frenteMinimoLiteral},`,
    '    street_side=str(street_side_js),',
    `    poligono_real_coords=${poligonoRealLiteral},`,
    `    clasificacion_suelo=${clasificacionSueloLiteral},`,
    `    retranqueo_por_lado=${retranqueoPorLadoLiteral},`,
    `    fondo_edificacion_m=${fondoEdificacionLiteral},`,
    `    linea_edificacion_m=${lineaEdificacionLiteral},`,
    ')',
    // allow_nan=False: si algun NaN/Infinity de coma flotante se coló en
    // la geometria generada, falla aqui con un error claro en vez de
    // mandar al navegador un JSON no-estandar que JSON.parse no puede leer.
    'json.dumps(resultado, allow_nan=False)',
  ].join('\n');
  const resultStr = await runPyodideCode(pyCode, globalsToSet, onProgress);
  return JSON.parse(resultStr);
}

async function analizarParcelaCatastroReal(gmlContent, retranqueoM, onProgress){
  // Zona 0, Fase A de importacion de Catastro: analiza un GML real
  // (Sede Electronica del Catastro) via Pyodide -- mismo patron que
  // generarEdificioReal, pero el contenido del GML es un string
  // plano, sin riesgo del bug de JsNull (eso solo afecta a valores
  // NULL, no a strings). retranqueoM SI puede ser null (campo
  // opcional) -- mismo patron anti-JsNull ya probado: literal Python
  // directo, no pyodide.globals.set() con null. Ver [ARCH:catastro-gml-importer].
  onProgress('Analizando el archivo catastral...');

  const globalsToSet = {gml_content_js: gmlContent};
  const retranqueoLiteral = (retranqueoM !== null && retranqueoM !== undefined && !isNaN(retranqueoM))
    ? `float(${JSON.stringify(retranqueoM)})` : 'None';
  const pyCode = [
    'import json',
    'from housing_generator.interface.browser.bridge import analizar_parcela_catastro',
    `resultado = analizar_parcela_catastro(gml_content_js, retranqueo_m=${retranqueoLiteral})`,
    'json.dumps(resultado, allow_nan=False)',
  ].join('\n');
  const resultStr = await runPyodideCode(pyCode, globalsToSet, onProgress);
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
  // semilla e iteraciones ya NO son campos manuales -- a peticion del
  // usuario ("sigo viendo raro cuando es algo que deberia ser
  // automatico"): la semilla de partida siempre es 1 (el propio
  // reintento automatico ya explora 1, 2, 3... no hace falta elegirla
  // a mano), y las iteraciones se escalan segun el numero real de
  // estancias del programa -- mismos ordenes de magnitud usados a lo
  // largo de esta sesion (6 estancias ~1500-3000, 10-13 ~3000-4000).
  // Ver [ARCH:btree-generador-por-defecto].
  const seed = 1;
  const totalRooms = Object.values(payload.levels)
    .flat()
    .reduce((sum, entry) => sum + (entry.count || 1), 0);
  const maxIterations = Math.max(1500, totalRooms * 300);
  const accesible = document.getElementById('gen-accesible').checked;
  const retranqueoEl = document.getElementById('gen-retranqueo');
  const retranqueoM = retranqueoEl && retranqueoEl.value !== '' ? parseFloat(retranqueoEl.value) : null;
  const retranqueoIncEl = document.getElementById('gen-retranqueo-incremento');
  const retranqueoIncremento = retranqueoIncEl && retranqueoIncEl.value !== '' ? parseFloat(retranqueoIncEl.value) : null;
  // Zona 0: parametros urbanisticos reales -- mismo patron "vacio = sin
  // restriccion" que retranqueo. Ver [ARCH:viabilidad-urbanistica].
  const numOpcional = (id) => {
    const el = document.getElementById(id);
    return el && el.value !== '' ? parseFloat(el.value) : null;
  };
  const edificabilidad = numOpcional('gen-edificabilidad');
  const ocupacionMaxima = numOpcional('gen-ocupacion-maxima');
  const alturaMaxima = numOpcional('gen-altura-maxima');
  const frenteMinimo = numOpcional('gen-frente-minimo');
  const fondoEdificacion = numOpcional('gen-fondo-edificacion');
  const lineaEdificacion = numOpcional('gen-linea-edificacion');
  const streetSideEl = document.getElementById('gen-street-side');
  const streetSide = streetSideEl ? streetSideEl.value : 'south';
  // si hay una parcela importada de Catastro, pasar su poligono real
  // (en BRUTO, no zona_afeccion -- esa ya viene reducida por
  // retranqueo, y retranqueo_m se aplica dentro de Lot, no hay que
  // aplicarlo dos veces). Hallazgo real, confirmado por el usuario
  // con captura del navegador: sin esto, la generacion siempre
  // trabajaba sobre el rectangulo de trabajo, nunca sobre la parcela
  // real. Ver [ARCH:parcela-real].
  const poligonoRealCoords = (typeof PARCELA_IMPORTADA !== 'undefined' && PARCELA_IMPORTADA)
    ? PARCELA_IMPORTADA.poligono_real : null;
  // retranqueo por lado -- a peticion del usuario. Solo se envian los
  // lados con un valor real puesto, el resto usa retranqueoM (el
  // valor unico de siempre) via el fallback en Lot.
  const retranqueoPorLado = {};
  document.querySelectorAll('.retranqueo-lado-input').forEach(input => {
    if(input.value !== '') retranqueoPorLado[input.dataset.lado] = parseFloat(input.value);
  });
  // clasificacion del suelo (Ley 2/2016) -- puramente informativo,
  // ningun validador aplica reglas distintas segun el valor todavia.
  const clasificacionSuelo = Array.from(document.querySelectorAll('.clasificacion-suelo-check:checked'))
    .map(el => el.value);

  btn.disabled = true;
  setGenerateStatus('Iniciando...', 'loading');
  // 10 -> 20 reintentos: medido con datos reales que la vivienda
  // multi-planta con escalera compartida puede tener una tasa de
  // exito por semilla de solo 10-20% incluso con un programa completo
  // (con distribuidor) -- con 10 intentos la probabilidad de fallo
  // total rondaba el 11-35%, con 20 baja a 1-12%. Barato para los
  // casos que ya convergen (corta en el primer exito). Ver
  // docs/CONTINUIDAD.md.
  const RETRY_SEEDS = 20;
  try{
    const result = await generarEdificioReal(
      payload, lotW, lotH, seed, maxIterations, RETRY_SEEDS, accesible,
      retranqueoM, retranqueoIncremento,
      edificabilidad, ocupacionMaxima, alturaMaxima, frenteMinimo, streetSide,
      poligonoRealCoords, clasificacionSuelo, retranqueoPorLado, fondoEdificacion, lineaEdificacion,
      (msg) => setGenerateStatus(msg, 'loading'),
    );
    if(!result.ok){
      setGenerateStatus('No se pudo generar: ' + result.error, 'error');
      return;
    }
    LOADED_PLANS = Object.entries(result.floors).map(([level, data]) => ({
      label: labelForPlanFile(level + '.json'), data,
    }));
    ACTIVE_PLAN = 0;
    PLANO_TRANSFORM = {mirrorH: false, mirrorV: false, rotation: 0};
    // marca de progreso: Zona 1 "completada" tras la primera generacion
    // real con exito -- refinamiento visual pedido por el usuario, mismo
    // patron .zona-btn.done ya presente en el CSS.
    const zonaDiseno = document.querySelector('[data-zona="diseno"]');
    if(zonaDiseno) zonaDiseno.classList.add('done');
    const semillaMsg = result.reintentos > 0
      ? ' (semilla ' + seed + ' no convergio, funciono la ' + result.semilla_usada + ' tras ' + (result.reintentos+1) + ' intentos)'
      : ' (semilla ' + result.semilla_usada + ')';
    setGenerateStatus('Generado correctamente' + semillaMsg + '. Mostrando en el Visor de plano.', 'ok');

    document.querySelector('[data-tab="plano"]').dispatchEvent(new Event('click', {bubbles:true}));
    renderPlanoTabs();
    renderPlano();
  } catch(err){
    console.error('handleGenerateNow: fallo inesperado generando el edificio', err);
    setGenerateStatus('Error inesperado: ' + (err && err.message ? err.message : err), 'error');
  } finally {
    btn.disabled = false;
  }
}

function escapeXml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
