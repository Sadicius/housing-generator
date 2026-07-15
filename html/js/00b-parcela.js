// ---------------- ZONA 0: PARCELA (vista previa de huella, reactiva) ----------------
// Calculo puramente en JS, sin pasar por Pyodide -- misma logica que
// Lot.buildable_area en Python (resta de retranqueo), pero para dar
// retroalimentacion INSTANTANEA mientras el usuario escribe, no
// esperar una llamada a Python para algo que es geometria simple de
// rectangulos. A peticion del usuario: "estaria bien poder ver la
// huella resultante antes de ir al programa".

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
  };
}

function calcularHuella(datos){
  // mismo calculo que Lot.buildable_area (Python) -- parcela reducida
  // por retranqueo en los 4 lados (sin medianeras aqui, la Zona 0 no
  // gestiona ese dato todavia).
  const r = datos.retranqueoM || 0;
  const huella = {
    x0: r, y0: r,
    x1: Math.max(r, datos.anchoM - r),
    y1: Math.max(r, datos.fondoM - r),
  };
  huella.colapsada = (datos.anchoM - 2 * r <= 0) || (datos.fondoM - 2 * r <= 0);
  return huella;
}

function renderParcelaPreview(){
  const datos = leerParcelaForm();
  const huella = calcularHuella(datos);
  const svg = document.getElementById('parcela-preview');
  const resumen = document.getElementById('parcela-resumen');
  if(!svg || !resumen) return;

  // encajar la parcela en un viewBox fijo de 300x300, con margen
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

  // indicador del lado de calle
  const streetLine = {
    south: `M${px(0)},${py(0)} L${px(datos.anchoM)},${py(0)}`,
    north: `M${px(0)},${py(datos.fondoM)} L${px(datos.anchoM)},${py(datos.fondoM)}`,
    east: `M${px(datos.anchoM)},${py(0)} L${px(datos.anchoM)},${py(datos.fondoM)}`,
    west: `M${px(0)},${py(0)} L${px(0)},${py(datos.fondoM)}`,
  }[datos.streetSide];
  svgContent += `<path d="${streetLine}" stroke="var(--cyan)" stroke-width="4" stroke-linecap="round"/>`;

  svg.innerHTML = svgContent;

  // resumen numerico -- mismas formulas que ViabilidadUrbanisticaValidator
  // (Python), aqui en JS para respuesta instantanea sin llamar a Pyodide.
  const superficieParcela = datos.anchoM * datos.fondoM;
  const superficieHuella = huella.colapsada ? 0 : (huella.x1 - huella.x0) * (huella.y1 - huella.y0);
  const frenteActual = (datos.streetSide === 'north' || datos.streetSide === 'south') ? datos.anchoM : datos.fondoM;

  const lineas = [];
  lineas.push(`<span class="stat">Parcela: <b>${superficieParcela.toFixed(1)}m²</b></span>`);
  lineas.push(huella.colapsada
    ? `<span class="stat parcela-error">✗ retranqueo excesivo: no queda área edificable</span>`
    : `<span class="stat">Área edificable tras retranqueo: <b>${superficieHuella.toFixed(1)}m²</b></span>`);

  if(datos.edificabilidad !== null){
    const techoMax = datos.edificabilidad * superficieParcela;
    lineas.push(`<span class="stat">Edificabilidad permite hasta <b>${techoMax.toFixed(1)}m²</b> de techo total (todas las plantas)</span>`);
  }
  if(datos.ocupacionMaximaPct !== null){
    const huellaMax = (datos.ocupacionMaximaPct / 100) * superficieParcela;
    lineas.push(`<span class="stat">Ocupación máxima permite hasta <b>${huellaMax.toFixed(1)}m²</b> de huella en planta</span>`);
  }
  if(datos.alturaMaximaPlantas !== null){
    lineas.push(`<span class="stat">Altura máxima: <b>${datos.alturaMaximaPlantas}</b> planta(s)</span>`);
  }
  if(datos.frenteMinimoM !== null){
    const cumple = frenteActual >= datos.frenteMinimoM;
    lineas.push(`<span class="stat ${cumple ? '' : 'parcela-error'}">${cumple ? '✓' : '✗'} Frente actual ${frenteActual.toFixed(1)}m (mínimo ${datos.frenteMinimoM.toFixed(1)}m)</span>`);
  }

  resumen.innerHTML = lineas.join('');
}

function initParcelaPreview(){
  const ids = [
    'gen-lot-w', 'gen-lot-h', 'gen-street-side', 'gen-retranqueo',
    'gen-edificabilidad', 'gen-ocupacion-maxima', 'gen-altura-maxima', 'gen-frente-minimo',
  ];
  ids.forEach(id => {
    const el = document.getElementById(id);
    if(el) el.addEventListener('input', renderParcelaPreview);
  });
  renderParcelaPreview();
}
