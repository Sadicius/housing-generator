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

async function generarEdificioReal(seleccionPayload, lotW, lotH, seed, maxIterations, retrySeeds, viviendaAccesible, retranqueoM, retranqueoIncremento, edificabilidad, ocupacionMaxima, alturaMaxima, frenteMinimo, streetSide, poligonoRealCoords, clasificacionSuelo, onProgress){
  const pyodide = await ensurePyodideReady(onProgress);
  onProgress('Buscando una distribucion valida (puede reintentar varias semillas)...');

  pyodide.globals.set('payload_json_str', JSON.stringify(seleccionPayload));
  pyodide.globals.set('lot_w_js', lotW);
  pyodide.globals.set('lot_h_js', lotH);
  pyodide.globals.set('seed_js', seed);
  pyodide.globals.set('max_it_js', maxIterations);
  pyodide.globals.set('retry_js', retrySeeds);
  pyodide.globals.set('accesible_js', viviendaAccesible);
  // street_side es un string fijo (viene de un <select> con opciones
  // controladas, no puede ser null/vacio) -- sin el riesgo de JsNull
  // que afecta a los valores numericos opcionales, seguro via globals.set().
  pyodide.globals.set('street_side_js', streetSide || 'south');

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
    ')',
    'json.dumps(resultado)',
  ].join('\n');
  const resultStr = await pyodide.runPythonAsync(pyCode);
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
  const pyodide = await ensurePyodideReady(onProgress);
  onProgress('Analizando el archivo catastral...');

  pyodide.globals.set('gml_content_js', gmlContent);
  const retranqueoLiteral = (retranqueoM !== null && retranqueoM !== undefined && !isNaN(retranqueoM))
    ? `float(${JSON.stringify(retranqueoM)})` : 'None';
  const pyCode = [
    'import json',
    'from housing_generator.interface.browser.bridge import analizar_parcela_catastro',
    `resultado = analizar_parcela_catastro(gml_content_js, retranqueo_m=${retranqueoLiteral})`,
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
  // clasificacion del suelo (Ley 2/2016) -- puramente informativo,
  // ningun validador aplica reglas distintas segun el valor todavia.
  const clasificacionSuelo = Array.from(document.querySelectorAll('.clasificacion-suelo-check:checked'))
    .map(el => el.value);

  btn.disabled = true;
  setGenerateStatus('Iniciando...', 'loading');
  try{
    const result = await generarEdificioReal(
      payload, lotW, lotH, seed, maxIterations, 10, accesible,
      retranqueoM, retranqueoIncremento,
      edificabilidad, ocupacionMaxima, alturaMaxima, frenteMinimo, streetSide,
      poligonoRealCoords, clasificacionSuelo,
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
    setGenerateStatus('Error inesperado: ' + (err && err.message ? err.message : err), 'error');
  } finally {
    btn.disabled = false;
  }
}

function escapeXml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
