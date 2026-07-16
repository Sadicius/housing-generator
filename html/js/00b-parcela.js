// ---------------- ZONA 0: PARCELA (vista previa de huella, reactiva) ----------------
// Calculo puramente en JS, sin pasar por Pyodide -- misma logica que
// Lot.buildable_area en Python (resta de retranqueo), pero para dar
// retroalimentacion INSTANTANEA mientras el usuario escribe, no
// esperar una llamada a Python para algo que es geometria simple de
// rectangulos. A peticion del usuario: "estaria bien poder ver la
// huella resultante antes de ir al programa".
//
// Fase A (importacion de Catastro): cuando hay una parcela importada
// (GML real), el dibujo cambia -- poligono real + rectangulo de
// trabajo (OBB) superpuesto + zona de afeccion calculada con
// shapely.buffer() via Pyodide (un recorte de poligono correcto es
// dificil de hacer bien en JS puro, se reutiliza la infraestructura
// que ya esta cargada en vez de anadir una libreria de geometria
// nueva). Ver [ARCH:catastro-gml-importer].

let PARCELA_IMPORTADA = null;  // null = manual; si no, {referencia_catastral, poligono_real, rectangulo_trabajo, area_calculada_m2, area_declarada_m2, discrepancia_area_pct, zona_afeccion, _gmlOriginal}

function leerParcelaForm(){
  const num = (id) => {
    const v = document.getElementById(id).value;
    return v === '' ? null : parseFloat(v);
  };
  return {
    anchoM: parseFloat(document.getElementById('gen-lot-w').value) || 14,
    fondoM: parseFloat(document.getElementById('gen-lot-h').value) || 16,
    streetSide: document.getElementById('gen-street-side').value,
    retranqueoM: num('gen-retranqueo'),
    edificabilidad: num('gen-edificabilidad'),
    ocupacionMaximaPct: num('gen-ocupacion-maxima'),
    alturaMaximaPlantas: num('gen-altura-maxima'),
    frenteMinimoM: num('gen-frente-minimo'),
    fondoEdificacionM: num('gen-fondo-edificacion'),
  };
}

function calcularHuella(datos){
  // mismo calculo que Lot.buildable_area (Python) -- parcela reducida
  // por retranqueo en los 4 lados (sin medianeras aqui, la Zona 0 no
  // gestiona ese dato todavia). Solo se usa en el caso MANUAL -- con
  // parcela importada, la zona de afeccion real viene de Pyodide.
  const r = datos.retranqueoM || 0;
  const huella = {
    x0: r, y0: r,
    x1: Math.max(r, datos.anchoM - r),
    y1: Math.max(r, datos.fondoM - r),
  };
  huella.colapsada = (datos.anchoM - 2 * r <= 0) || (datos.fondoM - 2 * r <= 0);
  return huella;
}

function _puntosSvg(coords, px, py){
  return coords.map(c => `${px(c[0])},${py(c[1])}`).join(' ');
}

function renderParcelaPreview(){
  const datos = leerParcelaForm();
  const svg = document.getElementById('parcela-preview');
  const resumen = document.getElementById('parcela-resumen');
  if(!svg || !resumen) return;

  if(PARCELA_IMPORTADA){
    renderParcelaImportada(datos, svg, resumen);
    return;
  }

  // ---- caso MANUAL: rectangulo simple, calculo instantaneo en JS ----
  const huella = calcularHuella(datos);
  const margen = 20;
  const escala = Math.min((300 - 2 * margen) / datos.anchoM, (300 - 2 * margen) / datos.fondoM);
  const px = (x) => margen + x * escala;
  const py = (y) => 300 - margen - y * escala;  // invertir Y (SVG crece hacia abajo)

  let svgContent = `
    <rect x="${px(0)}" y="${py(datos.fondoM)}" width="${datos.anchoM * escala}" height="${datos.fondoM * escala}"
          fill="none" stroke="var(--ink-faint)" stroke-width="1.5" stroke-dasharray="4,3"/>`;

  if(!huella.colapsada){
    svgContent += `
      <rect x="${px(huella.x0)}" y="${py(huella.y1)}" width="${(huella.x1 - huella.x0) * escala}" height="${(huella.y1 - huella.y0) * escala}"
            fill="var(--pa)" fill-opacity="0.35" stroke="var(--pa)" stroke-width="2"/>`;
  }

  svgContent += _lineaFrente(datos, px, py);
  svgContent += _lineaFondoEdificacion(datos, px, py);
  svg.innerHTML = svgContent;

  const superficieParcela = datos.anchoM * datos.fondoM;
  const superficieHuella = huella.colapsada ? 0 : (huella.x1 - huella.x0) * (huella.y1 - huella.y0);
  resumen.innerHTML = _resumenHtml(datos, superficieParcela, superficieHuella, huella.colapsada, 'manual');
}

function _clasificarLadoCardinal(p1, p2, centroide){
  // misma logica que retranqueo_variable_por_lado (Python, lot.py):
  // clasifica un lado por la direccion cardinal mas cercana a su
  // normal saliente (la que apunta lejos del centroide), no asume
  // que el poligono ya este alineado a ejes. Version JS para
  // respuesta instantanea al pulsar un lado en la vista previa, sin
  // ida y vuelta a Pyodide para algo que es geometria simple.
  const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
  const normalA = [-dy, dx];
  const puntoMedio = [(p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2];
  const haciaCentroide = [centroide[0] - puntoMedio[0], centroide[1] - puntoMedio[1]];
  const normalSaliente = (normalA[0] * haciaCentroide[0] + normalA[1] * haciaCentroide[1]) < 0
    ? normalA : [-normalA[0], -normalA[1]];
  let anguloDeg = Math.atan2(normalSaliente[1], normalSaliente[0]) * 180 / Math.PI;
  if(anguloDeg < 0) anguloDeg += 360;
  if(anguloDeg >= 45 && anguloDeg < 135) return 'north';
  if(anguloDeg >= 135 && anguloDeg < 225) return 'west';
  if(anguloDeg >= 225 && anguloDeg < 315) return 'south';
  return 'east';
}

function _centroidePoligono(coords){
  let area = 0, cx = 0, cy = 0;
  for(let i = 0; i < coords.length - 1; i++){
    const cruz = coords[i][0] * coords[i+1][1] - coords[i+1][0] * coords[i][1];
    area += cruz;
    cx += (coords[i][0] + coords[i+1][0]) * cruz;
    cy += (coords[i][1] + coords[i+1][1]) * cruz;
  }
  area = area / 2;
  if(Math.abs(area) < 1e-9) return coords[0];
  return [cx / (6 * area), cy / (6 * area)];
}

function _ladosClicables(poligono, px, py){
  // cada lado del poligono real como un <line> pulsable -- a peticion
  // del usuario: "una parcela podria tener una vinculacion diferente
  // o incluso necesitar que la marque". Pulsar un lado clasifica su
  // direccion cardinal y selecciona esa opcion en "Lado de calle",
  // en vez de limitarse a elegir a ciegas entre N/S/E/O sin ver la
  // parcela real. Ver [ARCH:selector-calle-poligono-real].
  const centroide = _centroidePoligono(poligono);
  const streetSideEl = document.getElementById('gen-street-side');
  const actual = streetSideEl ? streetSideEl.value : null;
  let svgLados = '';
  for(let i = 0; i < poligono.length - 1; i++){
    const p1 = poligono[i], p2 = poligono[i + 1];
    const direccion = _clasificarLadoCardinal(p1, p2, centroide);
    const esActual = direccion === actual;
    svgLados += `<line class="parcela-lado-clicable" data-direccion="${direccion}"
        x1="${px(p1[0])}" y1="${py(p1[1])}" x2="${px(p2[0])}" y2="${py(p2[1])}"
        stroke="${esActual ? 'var(--cyan)' : 'transparent'}" stroke-width="${esActual ? 5 : 10}"
        stroke-linecap="round" style="cursor:pointer;"><title>Marcar como lado de calle (${direccion})</title></line>`;
  }
  return svgLados;
}

function renderParcelaImportada(datos, svg, resumen){
  // ---- caso IMPORTADO: poligono real + OBB + zona de afeccion ----
  // Se dibuja la version en ORIENTACION REAL (sin la rotacion que
  // alinea el rectangulo de trabajo al generador) -- hallazgo real
  // del usuario: mostrar la version rotada "no es adecuado para una
  // buena interpretacion" de como es la parcela de verdad respecto al
  // norte. El generador sigue usando la version alineada por
  // separado (poligono_real/rectangulo_trabajo), sin cambios. Ver
  // [ARCH:parcela-orientacion-real].
  const p = PARCELA_IMPORTADA;
  const poligono = p.poligono_orientacion_real;
  const rectangulo = p.rectangulo_trabajo_orientacion_real;
  const zonaAfeccion = p.zona_afeccion_orientacion_real;
  const todosLosPuntos = poligono.concat(rectangulo);
  const xs = todosLosPuntos.map(c => c[0]), ys = todosLosPuntos.map(c => c[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const margen = 20;
  const escala = Math.min((300 - 2 * margen) / (maxX - minX || 1), (300 - 2 * margen) / (maxY - minY || 1));
  const px = (x) => margen + (x - minX) * escala;
  const py = (y) => 300 - margen - (y - minY) * escala;

  let svgContent = `<polygon points="${_puntosSvg(poligono, px, py)}"
      fill="var(--ink-faint)" fill-opacity="0.5" stroke="var(--ink-dim)" stroke-width="1.5"/>`;
  svgContent += `<polygon points="${_puntosSvg(rectangulo, px, py)}"
      fill="none" stroke="var(--ink-faint)" stroke-width="1.5" stroke-dasharray="5,4"/>`;

  const afeccionColapsada = zonaAfeccion !== null && zonaAfeccion !== undefined && zonaAfeccion.length === 0;
  if(zonaAfeccion && zonaAfeccion.length > 0){
    svgContent += `<polygon points="${_puntosSvg(zonaAfeccion, px, py)}"
        fill="var(--pa)" fill-opacity="0.4" stroke="var(--pa)" stroke-width="2"/>`;
  } else if(!zonaAfeccion){
    // sin retranqueo pedido -- la huella util es el propio poligono real
    svgContent += `<polygon points="${_puntosSvg(poligono, px, py)}"
        fill="var(--pa)" fill-opacity="0.25" stroke="none"/>`;
  }

  svgContent += _lineaFrente(datos, px, py);
  svgContent += _lineaFondoEdificacion(datos, px, py);
  svgContent += _ladosClicables(poligono, px, py);
  svg.innerHTML = svgContent;
  svg.querySelectorAll('.parcela-lado-clicable').forEach(el => {
    el.addEventListener('click', () => {
      const streetSideEl = document.getElementById('gen-street-side');
      if(streetSideEl){
        streetSideEl.value = el.dataset.direccion;
        streetSideEl.dispatchEvent(new Event('input', {bubbles: true}));
      }
    });
  });

  const superficieAfeccion = (zonaAfeccion && zonaAfeccion.length > 0)
    ? _areaPoligono(zonaAfeccion)
    : (afeccionColapsada ? 0 : p.area_calculada_m2);
  resumen.innerHTML = _resumenHtml(datos, p.area_calculada_m2, superficieAfeccion, afeccionColapsada, 'importado');
}

function _areaPoligono(coords){
  // formula del "shoelace" -- area de un poligono simple a partir de
  // sus vertices, sin depender de shapely para algo que ya tenemos
  // calculado en el propio array de puntos.
  let area = 0;
  for(let i = 0; i < coords.length - 1; i++){
    area += coords[i][0] * coords[i+1][1] - coords[i+1][0] * coords[i][1];
  }
  return Math.abs(area / 2);
}

function _lineaFrente(datos, px, py){
  // resalta el lado de calle -- misma logica en ambos casos (manual/
  // importado), usando el ancho/fondo del formulario (que en el caso
  // importado ya viene relleno con las dimensiones del rectangulo de
  // trabajo tras la importacion).
  const streetLine = {
    south: `M${px(0)},${py(0)} L${px(datos.anchoM)},${py(0)}`,
    north: `M${px(0)},${py(datos.fondoM)} L${px(datos.anchoM)},${py(datos.fondoM)}`,
    east: `M${px(datos.anchoM)},${py(0)} L${px(datos.anchoM)},${py(datos.fondoM)}`,
    west: `M${px(0)},${py(0)} L${px(0)},${py(datos.fondoM)}`,
  }[datos.streetSide];
  return `<path d="${streetLine}" stroke="var(--cyan)" stroke-width="4" stroke-linecap="round"/>`;
}

function _lineaFondoEdificacion(datos, px, py){
  // linea discontinua paralela al lado de calle, a la distancia de
  // fondo_edificacion_m -- a peticion del usuario ("tampoco esta
  // representado en el visor"). Sin fondoEdificacionM, no dibuja nada.
  if(datos.fondoEdificacionM === null || datos.fondoEdificacionM === undefined) return '';
  const f = datos.fondoEdificacionM;
  const linea = {
    south: `M${px(0)},${py(f)} L${px(datos.anchoM)},${py(f)}`,
    north: `M${px(0)},${py(datos.fondoM - f)} L${px(datos.anchoM)},${py(datos.fondoM - f)}`,
    east: `M${px(datos.anchoM - f)},${py(0)} L${px(datos.anchoM - f)},${py(datos.fondoM)}`,
    west: `M${px(f)},${py(0)} L${px(f)},${py(datos.fondoM)}`,
  }[datos.streetSide];
  return `<path d="${linea}" stroke="var(--terracota)" stroke-width="1.5" stroke-dasharray="6,4"/>`;
}

function _resumenHtml(datos, superficieParcela, superficieHuella, huellaColapsada, fuente){
  // mismas formulas que ViabilidadUrbanisticaValidator (Python), aqui
  // en JS para respuesta instantanea sin llamar a Pyodide en el caso
  // manual -- en el caso importado, superficieParcela/superficieHuella
  // ya vienen calculadas del poligono real, no del rectangulo.
  const frenteActual = (datos.streetSide === 'north' || datos.streetSide === 'south') ? datos.anchoM : datos.fondoM;
  const etiquetaFuente = fuente === 'importado'
    ? `<span class="parcela-fuente-tag importado">Importado (Catastro)</span>`
    : `<span class="parcela-fuente-tag manual">Manual</span>`;

  const lineas = [`<span class="stat">Parcela: <b>${superficieParcela.toFixed(1)}m²</b>${etiquetaFuente}</span>`];

  if(fuente === 'importado' && PARCELA_IMPORTADA){
    const p = PARCELA_IMPORTADA;
    lineas.push(`<span class="stat">Referencia catastral: <b>${p.referencia_catastral}</b></span>`);
    if(p.discrepancia_area_pct > 1.0){
      lineas.push(`<span class="stat parcela-error">✗ el área declarada (${p.area_declarada_m2}m²) difiere ${p.discrepancia_area_pct}% de la calculada del polígono</span>`);
    }
  }

  lineas.push(huellaColapsada
    ? `<span class="stat parcela-error">✗ retranqueo excesivo: no queda área edificable</span>`
    : `<span class="stat">Área edificable tras retranqueo: <b>${superficieHuella.toFixed(1)}m²</b></span>`);

  if(datos.edificabilidad !== null){
    const techoMax = datos.edificabilidad * superficieParcela;
    lineas.push(`<span class="stat">Edificabilidad permite hasta <b>${techoMax.toFixed(1)}m²</b> de techo total (todas las plantas)</span>`);
  }
  if(datos.ocupacionMaximaPct !== null){
    const huellaMax = (datos.ocupacionMaximaPct / 100) * superficieParcela;
    const cumpleOcupacion = superficieHuella <= huellaMax || huellaColapsada;
    lineas.push(`<span class="stat ${cumpleOcupacion ? '' : 'parcela-error'}">${cumpleOcupacion ? '' : '✗ '}Ocupación máxima permite hasta <b>${huellaMax.toFixed(1)}m²</b> de huella en planta</span>`);
  }
  if(datos.alturaMaximaPlantas !== null){
    lineas.push(`<span class="stat">Altura máxima: <b>${datos.alturaMaximaPlantas}</b> planta(s)</span>`);
  }
  if(datos.frenteMinimoM !== null){
    const cumple = frenteActual >= datos.frenteMinimoM;
    lineas.push(`<span class="stat ${cumple ? '' : 'parcela-error'}">${cumple ? '✓' : '✗'} Frente actual ${frenteActual.toFixed(1)}m (mínimo ${datos.frenteMinimoM.toFixed(1)}m)</span>`);
  }

  return lineas.join('');
}

async function manejarArchivoCatastro(file){
  const statusEl = document.getElementById('parcela-import-status');
  statusEl.className = 'parcela-import-status';
  statusEl.textContent = 'Leyendo archivo...';

  try{
    const contenido = await file.text();
    const retranqueoM = leerParcelaForm().retranqueoM;
    const resultado = await analizarParcelaCatastroReal(contenido, retranqueoM, (msg) => { statusEl.textContent = msg; });

    if(!resultado.ok){
      statusEl.className = 'parcela-import-status error';
      statusEl.textContent = '✗ ' + resultado.error;
      return;
    }

    resultado._gmlOriginal = contenido;
    PARCELA_IMPORTADA = resultado;
    document.getElementById('gen-lot-w').value = resultado.ancho_m;
    document.getElementById('gen-lot-h').value = resultado.fondo_m;

    // marca de progreso: Zona 0 "completada" tras importar una parcela
    // real con exito -- mismo patron que Zona 1 tras generar un plano.
    const zonaParcela = document.querySelector('[data-zona="parcela"]');
    if(zonaParcela) zonaParcela.classList.add('done');

    statusEl.className = 'parcela-import-status ok';
    statusEl.textContent = `✓ Parcela ${resultado.referencia_catastral} importada (${resultado.area_calculada_m2}m²)`;
    renderParcelaPreview();
  } catch(err){
    statusEl.className = 'parcela-import-status error';
    statusEl.textContent = '✗ No se pudo leer el archivo: ' + err.message;
  }
}

async function reanalizarZonaAfeccionSiHayImportada(){
  // el retranqueo cambio DESPUES de importar -- recalcular la zona de
  // afeccion real (via Pyodide, no instantaneo como el caso manual,
  // pero necesario para que el recorte del poligono siga siendo
  // correcto). Se vuelve a llamar a analizar_parcela_catastro entero
  // -- mas simple que mantener el estado a medias.
  if(!PARCELA_IMPORTADA || !PARCELA_IMPORTADA._gmlOriginal) return;
  const retranqueoM = leerParcelaForm().retranqueoM;
  const resultado = await analizarParcelaCatastroReal(PARCELA_IMPORTADA._gmlOriginal, retranqueoM, () => {});
  if(resultado.ok){
    resultado._gmlOriginal = PARCELA_IMPORTADA._gmlOriginal;
    PARCELA_IMPORTADA = resultado;
    renderParcelaPreview();
  }
}

function initParcelaPreview(){
  const ids = [
    'gen-lot-w', 'gen-lot-h', 'gen-street-side',
    'gen-edificabilidad', 'gen-ocupacion-maxima', 'gen-altura-maxima', 'gen-frente-minimo', 'gen-fondo-edificacion',
  ];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if(el) el.addEventListener('input', renderParcelaPreview);
  });
  const retranqueoEl = document.getElementById('gen-retranqueo');
  if(retranqueoEl){
    retranqueoEl.addEventListener('input', () => {
      renderParcelaPreview();  // caso manual: instantaneo
      reanalizarZonaAfeccionSiHayImportada();  // caso importado: recalculo real via Pyodide
    });
  }

  const dropZone = document.getElementById('parcela-drop-zone');
  const fileInput = document.getElementById('parcela-gml-input');
  if(fileInput){
    fileInput.addEventListener('change', async (e) => {
      if(e.target.files && e.target.files[0]){
        await manejarArchivoCatastro(e.target.files[0]);
      }
    });
  }
  if(dropZone){
    ['dragover', 'dragenter'].forEach(evt => dropZone.addEventListener(evt, (e) => {
      e.preventDefault(); dropZone.classList.add('dragover');
    }));
    ['dragleave', 'drop'].forEach(evt => dropZone.addEventListener(evt, (e) => {
      e.preventDefault(); dropZone.classList.remove('dragover');
    }));
    dropZone.addEventListener('drop', async (e) => {
      e.preventDefault();
      if(e.dataTransfer.files && e.dataTransfer.files[0]){
        await manejarArchivoCatastro(e.dataTransfer.files[0]);
      }
    });
  }

  renderParcelaPreview();
}
