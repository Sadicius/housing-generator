# Dashboard -- cronograma de obra

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

## [ARCH:cronograma-obra] Cronograma de obra -- pestaña 06

A partir de investigar `gantt-elastic` (rechazado: Vue, dominio
distinto -- ver intercambio previo) el usuario propuso una pestaña
propia de cronograma de ejecución de obra. Investigado antes de
construir nada: no existe, que hayamos podido confirmar, una fuente
pública con rendimientos de obra reales por fase para vivienda
unifamiliar en Galicia -- la Base de datos da Construción de Galicia
(BDC, oficial, Observatorio de Vivenda/Xunta) es una herramienta de
precios/presupuestos (formato FIEBDC, pensada para programas de
presupuestos profesionales), no de plazos; derivar duraciones reales
de ahí sería un proyecto de investigación aparte, no algo para
construir de paso. Cifras agregadas encontradas (12-14 meses obra
tradicional, 3-4 meses prefabricada) son totales de proyecto, no
desglosables por fase.

- **Decisión de alcance, confirmada explícitamente**: herramienta de
  VISUALIZACIÓN pura. El usuario introduce fases y duración estimada
  (nombre, categoría, días) -- nosotros solo las encadenamos (cada
  fase empieza donde termina la anterior, sin paralelismo en esta
  primera versión) y las dibujamos. Nota de alcance visible en el
  propio panel, con enlace a la BDC real, dejando claro que esto no
  estima nada por su cuenta.
- 10 categorías típicas de fase de obra residencial (movimiento de
  tierras, cimentación, estructura, cerramientos, cubierta,
  instalaciones, tabiquería, acabados, carpintería, urbanización),
  cada una con su color -- nuevas variables CSS `--fase-*`.
- Implementado en `js/07-cronograma.js` (nuevo, antes del `init`,
  cargado ANTES para que sus funciones existan cuando `08-init.js`
  adjunta los listeners -- `07-init.js` renombrado a `08-init.js`).
  Sin nueva pieza Python: es puro cliente, mismo patrón que el modo
  espejo.
- Gráfico dibujado en SVG a mano (mismo patrón que el visor de plano,
  no una librería nueva) -- barras por fase, líneas de semana, marca
  de "hoy" si cae dentro del rango.
- Verificado con `jsdom`: encadenado de fechas correcto (probado con
  3 fases de duraciones distintas, fechas exactas confirmadas),
  reordenar fases (mover arriba/abajo) recalcula el cronograma
  completo correctamente, eliminar fases también. Verificado también
  con `wkhtmltoimage` + análisis de píxeles que las 8 categorías de
  prueba se dibujan con colores distintos y proporciones de tamaño
  coherentes con su duración declarada.
- Tests de sanidad actualizados: 6 pestañas (antes 5), orden de
  archivos JS actualizado con `07-cronograma.js`, nuevo test de
  controles del cronograma.
- Suite final: 345 unitarios, pyflakes limpio.
