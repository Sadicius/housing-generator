# housing_generator — Estado del proyecto (documento de continuidad)

> Este documento existe para que una conversación nueva (sin el historial de
> esta) pueda retomar el trabajo sin perder contexto. Los docs técnicos
> detallados siguen en `docs/architecture.md` (decisiones + auditorías),
> `docs/relaciones_espaciales.md` (catálogo de 120 pares + huecos de modelo)
> y `docs/niveles_plantas.md` (niveles, escalera, bajantes). Este documento
> es un resumen de alto nivel para orientarse rápido, no un sustituto de esos.
>
> Para USAR el proyecto (CLI, API Python, ejemplos verificados), ver
> `docs/GUIA_USO.md`. Para entender CÓMO FUNCIONA por dentro (arquitectura,
> algoritmo, validadores), ver `docs/COMO_FUNCIONA.md` -- ambos son
> documentación de referencia del estado ACTUAL, se reescriben in-place
> cuando algo cambia (misma convención que este documento), no logs
> históricos como `architecture.md`.

## Qué es esto

Sistema generativo de plantas residenciales en Python, cumplimiento del
Decreto 29/2010 de Galicia (habitabilidad, modificado por Decreto 128/2023).
Arquitectura hexagonal estricta. Generación por recocido simulado sobre un
árbol de partición (con heurística de "cortar por el lado más largo",
Marson & Musse 2010). 19 validadores normativos/prácticos + 1 combinador,
multi-planta con escalera y contorno progresivo, vivienda aislada y
pareada/adosada, dashboard con visor de plano y generación automática.

**Estado en el momento de escribir esto**: 381/381 tests (54 commits).
Estas cifras quedarán obsoletas en cuanto se añada algo más -- si no
coinciden con `git log --oneline | wc -l` y `pytest -q`, confiar en el
comando, no en este número.

## Convención de documentación — evitar que esto se repita

Esto ya ha pasado dos veces (dos rondas distintas encontraron
`architecture.md` y `relaciones_espaciales.md` afirmando como
"pendiente" cosas que ya estaban resueltas en otra sección del mismo
documento). La causa no fue un despiste puntual — es que la estructura
mezcla estado actual con narrativa histórica en el mismo sitio.

**Regla de separación, a partir de ahora:**

1. **Este documento (`CONTINUIDAD.md`) es la ÚNICA fuente de verdad
   sobre qué queda pendiente.** Se reescribe, no se amplía sin más --
   cada vez que algo de la lista de pendientes se resuelve, se quita de
   aquí en el mismo momento en que se resuelve, no en una limpieza
   posterior.
2. **`architecture.md` es un log histórico de solo-añadir, NUNCA una
   fuente de "estado actual".** Cada sección cuenta qué pasó en ese
   momento. Si algo queda pendiente al escribir una sección nueva, debe
   remitir a este documento (`docs/CONTINUIDAD.md`) en vez de afirmarlo
   por su cuenta con frases tipo "no implementado" sin matizar -- así,
   si se resuelve más adelante, solo hace falta actualizar un sitio.
2b. **`GUIA_USO.md` y `COMO_FUNCIONA.md` son documentación de referencia
   del estado ACTUAL** (cómo usar el proyecto, cómo funciona por
   dentro) -- se reescriben in-place cuando algo relevante cambia,
   igual que este documento, NUNCA se amplían con un historial de "antes
   era así". Si un incremento cambia un flag del CLI, un conteo de
   validadores, una firma pública, etc., actualizar el pasaje concreto
   de estos dos documentos es parte de cerrar esa tarea -- mismo
   principio que el punto 3 de abajo, aplicado también a estos dos.
3. **Paso obligatorio al cerrar cualquier tarea que resuelva algo de la
   lista de pendientes de arriba**: antes de dar la tarea por
   terminada, buscar (`grep`) las palabras clave relacionadas en
   `architecture.md`, `relaciones_espaciales.md` y `niveles_plantas.md`
   para encontrar y corregir cualquier frase que lo siga describiendo
   como pendiente -- en la misma respuesta que resuelve la tarea, no
   como una auditoría aparte más adelante.
4. **Auditorías periódicas de documentación completa** (como la que
   encontró este problema) siguen siendo una red de seguridad útil,
   pero no el mecanismo principal -- confiar solo en eso es lo que
   dejó acumularse el problema dos veces antes de notarlo.

## Convención de tests — evitar código muerto/sin probar invisible

El usuario preguntó, con razón: "los tests que dices haber hecho,
¿están actualizados, o son solo los que se hicieron en su momento?".
Al comprobarlo de verdad (no de memoria), aparecieron 5 casos reales
de código sin usar ni probar desde el principio de la sesión,
invisibles porque "la suite pasa" nunca los señaló como problema:
`AdjacencyRequirement.involves()`/`.other()`, `Zone.add_room()`,
`Program.total_area_m2`/`.room_by_id()`, las tres validaciones de
error de `Dimensions.__post_init__`, y el camino de fallo de
`GenerateLayoutUseCase` (comprobado a mano con `bash_tool` en su
momento, nunca convertido en test permanente).

**La causa raíz**: "la suite pasa" solo detecta CONTRADICCIONES con lo
que ya se prueba -- nunca detecta código que nunca se ejerció desde el
principio, ni verificaciones hechas a mano que nunca se convirtieron en
test real. Son dos fallos de proceso distintos, el mismo síntoma
(confianza infundada) que ya vimos con la documentación obsoleta.

**Regla, a partir de ahora:**

1. **Ninguna verificación exploratoria (`bash_tool`, `python -c`) cuenta
   como "comprobado" para dar una tarea por terminada.** Si merece la
   pena comprobarlo, merece la pena que sea un test permanente -- la
   conversión es parte de cerrar la tarea, no un paso opcional
   posterior.
2. **Los huecos de cobertura son un hallazgo a investigar, no solo un
   número que aceptar.** Cuando la cobertura de un archivo (sobre todo
   uno que se acaba de tocar) no llega al 100%, mirar las líneas
   concretas sin cubrir antes de seguir -- no basta con que el
   porcentaje agregado del proyecto "suene bien".
3. **Barrido periódico de código sin uso** (no solo sin cobertura de
   test): `grep` de métodos declarados que nunca se llaman en ningún
   sitio del propio código fuente, no solo en los tests. Mismo patrón
   que la convención de documentación -- una auditoría periódica es red
   de seguridad, no el mecanismo principal.
4. **Antes de escribir un test nuevo, comprobar si ya existe uno
   equivalente.** Se encontró un caso real: al cerrar el hueco de
   `Program.total_area_m2`/`.room_by_id()`, escribí también tests para
   la validación de ids duplicados y de adyacencia a estancia
   desconocida -- que YA existían, textualmente iguales, en
   `test_domain_entities.py`. Un `grep` rápido del nombre de la clase/
   método en `tests/` antes de escribir evita esto.
5. **Herramientas de análisis estático (`pyflakes` u otras) forman
   parte de la auditoría, no solo `pytest`.** Encontraron bookkeeping
   completamente muerto (`best_tree` en el generador, nunca leído) que
   ningún test detectaría nunca, porque no verificar comportamiento --
   solo ocupaba ciclos sin ningún efecto observable.
6. **Cuando se encuentra un comentario con razonamiento completo que
   contradice el valor real del código junto a él, buscar sistemáticamente
   si se repite** -- no asumir que fue un caso aislado. Se encontró así
   (`GARAGE`/altura libre, dos hallazgos más en la misma búsqueda que
   encontró el primero de `GARAGE`/contacto exterior): localizar todos
   los bloques de comentario largos (`grep`/script, no revisión manual
   archivo por archivo) y revisar cada uno contra su código adyacente.
   La señal más fiable: frases como "no aparece en ninguna lista",
   "queda fuera de alcance", "no aplica" -- son exactamente donde una
   exclusión se pudo quedar desactualizada tras una investigación
   posterior que SÍ encontró la referencia.

## Cómo orientarse rápido

```
src/housing_generator/
  domain/           entidades puras (Room, Program, Layout, Building, Lot)
                     + enums (RoomType, NivelPlanta, SpaceCategory...)
  application/       casos de uso (GenerateLayoutUseCase, GenerateBuildingUseCase)
                     + ports (interfaces) -- NUNCA importa de infrastructure/config
  infrastructure/    validadores concretos, generador, adyacencia, geometría
  config/            container.py -- ÚNICO sitio que conecta piezas concretas
  interface/cli/     punto de entrada de línea de comandos

docs/
  GUIA_USO.md                como usar el proyecto (CLI, API Python, ejemplos verificados)
  COMO_FUNCIONA.md           arquitectura y algoritmo, estado actual
  architecture.md            decisiones + auditorías, en orden cronológico
  relaciones_espaciales.md   catálogo de 120 pares de adyacencia + huecos de modelo
  niveles_plantas.md         niveles, escalera (CTE DB-SUA 1), bajantes

docs/visualizador/relaciones_espaciales.html   dashboard standalone (5 pestañas,
                                                 incluido el Visor de plano)
```

Para entender el estado real, **`docs/architecture.md` es la fuente de verdad**
— cada sección nueva se añadió cronológicamente con lo que se decidió, lo que
se encontró roto, y por qué. Merece la pena leerlo entero antes de tocar nada
grande.

## Los 21 validadores normativos/prácticos + 1 combinador (todos en `infrastructure/algorithms/constraints/`)

Por planta (`build_per_floor_validators` en `container.py`, 17 clases,
20 instancias contando las 4 de `GroupingConstraintValidator`): Adjacency,
NucleoHumedo, zonificación día/noche/servicio, EstanciaMinimumArea (Tabla 1),
ServicioMinimumArea (Tabla 2), DormitorioArmario, TrasteroMinimumArea,
AnchoLibreEstancia, AnchoLibrePractico (NO normativo, 1.20m confirmado
explícitamente, ver sección de aprendizajes), AnchoLibrePasillo, AlturaLibre,
ExteriorContact, CocinaIntegrada, EspacioAcceso, EscaleraAnchoLibre,
PasilloTopologia, ViviendaAccesible (**opt-in**, `vivienda_accesible=True` --
inactivo por defecto, círculo de giro Ø1.50m + pasillo 1.20m, DB-SUA/Base
5.4, retomado de un proyecto Lua anterior del usuario -- ver architecture.md),
ProporcionMaxima (NO normativo, 2.5:1 confirmado explícitamente, siempre
activo -- red de seguridad contra estancias tipo "tira fina" que cumplen
el ancho mínimo pero son absurdas en proporción, encontrado con una batería
de casos reales, ver architecture.md).

De ámbito EDIFICIO (no por planta, se comprueban aparte en
`GenerateBuildingUseCase`): ViviendaMinima (programa mínimo, une todas las
plantas), BanoAccesoGeneral (al menos un baño con acceso general en ALGUNA
planta).

Entre plantas consecutivas (parametrizados con la planta ya resuelta):
EscaleraAlineacion (huella ≥90% de solape), NucleoHumedoVertical (bajantes).

`CompositeConstraintValidator` agrupa todos los anteriores tras la misma
interfaz -- no es una regla normativa en sí, es el combinador (17+2+2=21
reglas). Detalle completo con tabla resumen en `docs/COMO_FUNCIONA.md`.

## Multi-planta — cómo funciona

`GenerateBuildingUseCase.execute(program, lot)`: agrupa `program.rooms` por
`Room.level` (`NivelPlanta`), genera cada planta de abajo a arriba con el
MISMO generador de una sola planta (búsqueda independiente, no conjunta),
pasando referencias fijas (huella de escalera, huellas húmedas) de la planta
ya resuelta a la siguiente. `RoomType.STAIRCASE` conecta plantas.

**[RESUELTO]** El contorno edificable puede reducirse progresivamente
planta a planta (`Lot.retranqueo_incremento_por_planta_m`, opcional --
`None` por defecto preserva el comportamiento de mismo contorno para
todas). Ver `docs/architecture.md`.

## Los tres huecos de modelo originales — TODOS resueltos

1. Acceso/puertas → `build_door_graph` (capa dispersa sobre adyacencia real,
   solo pares con `Obligatorio cerca` satisfecho geométricamente)
2. Topología de pasillo (paso/terminal) → `PasilloTopologiaValidator`
   (puntos de corte sobre adyacencia geométrica real, no el grafo de
   puertas disperso — un primer intento con el grafo de puertas rompió 9
   tests, ver architecture.md)
3. Cardinalidad (baño según nº de baños) → `BanoAccesoGeneralValidator`

## Restricciones blandas — RESUELTO

`SoftConstraintScorer` + `AdjacencyStrength.SHOULD_BE_AWAY` (nuevo;
`SHOULD_BE_NEAR` ya existía en el enum sin usar). Conectado al recocido
simulado con comparación LEXICOGRÁFICA `(duro, blando)` — no suma
ponderada (esa primera versión rompía la dinámica de aceptación del
recocido, ver architecture.md). Confirmado con tests: la preferencia
blanda se satisface cuando no hay tensión con lo duro, y lo duro nunca
cede aunque haya tensión directa para el mismo par.

## Catálogo de 120 pares formalizado — RESUELTO

`domain/services/type_adjacency_catalog.py`. `DEFAULT_TYPE_ADJACENCY`
(82 entradas reales, generado programáticamente desde
`relaciones_espaciales.md`, no transcrito a mano) +
`generate_adjacency_requirements(rooms)` (deriva `AdjacencyRequirement`
duros y blandos automáticamente por `RoomType`). Verificado con el
generador real: un programa de 11 estancias genera 44 requisitos
automáticamente y produce un layout válido. Hallazgo honesto: usar el
catálogo completo es una búsqueda más difícil que los ejemplos curados
a mano (más iteraciones/intentos de semilla necesarios) -- no es una
contradicción del catálogo, solo un espacio de búsqueda más restringido.
**[RESUELTO]** Conectado como opción automática real:
`build_program_with_auto_adjacency` (domain/services) + `--auto-adjacency`
en el CLI.

## Importador JSON → Program real — RESUELTO

`infrastructure/persistence/seleccion_plantas_importer.py`:
`import_seleccion_plantas(source, areas_m2=None)`, construido contra el
formato REAL de exportación del dashboard (verificado en el propio
HTML, no asumido). **Las dos limitaciones originales (una sola
estancia por tipo/planta, áreas genéricas) se eliminaron en el propio
dashboard** -- cada chip seleccionado ahora captura cantidad real y
área en m² declarada por el usuario (formato `version: 2`),
compatibilidad conservada con JSON exportados antes de este cambio.
Nombres legibles en español (`DISPLAY_NAMES` en `enums.py`, mismo
mapeo que el dashboard) -- bug real encontrado en el recorrido
completo: usaba el id técnico como nombre visible.

Conectado en el CLI (`--import-seleccion`), con `--lot-size ANCHOxFONDO`
(parcela de ejemplo fija por defecto, 14x16) y `--retry-seeds` (5 por
defecto -- los programas de `--import-seleccion` no están curados a
mano, necesitan más margen de búsqueda de forma habitual, confirmado
con un caso real donde la semilla 1 no convergía). Confirmado con
generación real de extremo a extremo repetidamente.

## Pendiente real, si se retoma

**Cytoscape.js para la pestaña "Sinergias"** (investigado a fondo, no
implementado -- decisión explícita de posponerlo): sustituiría la red
SVG dibujada a mano (posicionamiento radial estático) por una red
interactiva real (arrastrar nodos, zoom, selección por caja). Viable
técnicamente -- `cytoscape.min.js` (UMD, MIT, muy establecida) tiene
bundle standalone real cargable con `<script src="">` clásico desde
CDN (unpkg/jsDelivr/CDNJS), funciona desde `file://` igual que Pyodide.
Coste real, no trivial: se renderiza en `<canvas>`, no SVG -- nuestras
variables CSS no se le pueden pasar directamente, hay que leer los
valores computados vía JS. Gotcha documentado por la propia librería
que nos afecta de verdad: necesita que su contenedor tenga dimensiones
reales en el momento de inicializarse, y nuestras pestañas inactivas
usan `display:none` -- inicializar mientras la pestaña está oculta le
daría tamaño cero. Solución conocida (inicializar solo al abrir la
pestaña la primera vez, + `cy.resize()`+`cy.fit()` al mostrarla) pero
es trabajo real de integración, no "añadir una librería y ya".

**El más urgente**: **probar el generador real en el navegador
(Pyodide) en un navegador de verdad, con internet normal.** Se
construyó respondiendo a que el usuario cuestionara si el dashboard
era realmente una forma de trabajar -- verificado todo lo posible
dentro de este entorno (el núcleo de Pyodide se instaló y ejecutó de
verdad vía npm/Node, `shapely`/`geos` confirmados como paquetes Pyodide
oficiales con fecha, el flujo completo del botón llega correctamente
hasta la llamada a `loadPyodide()` sin errores previos), pero el CDN
real (`cdn.jsdelivr.net`) está bloqueado en este entorno de trabajo, así
que la carga real de `shapely` dentro del navegador NUNCA se probó de
extremo a extremo. Alta confianza en que funcione (documentación
oficial con fecha, no una suposición), pero sigue siendo, técnicamente,
sin confirmar en el escenario real. Ver `docs/architecture.md`, sección
"Generador real en el navegador (Pyodide)".

**Zona de desembarco de escalera separada del pasillo principal**:
señalado en una crítica externa que el usuario compartió (parcialmente
acertada, parcialmente ya cubierta o sin fundamento -- ver el
intercambio donde se evaluó punto por punto). No tenemos nada
explícito que exija un espacio de llegada diferenciado en la unión
escalera-planta superior -- `EscaleraAlineacionValidator` solo
comprueba solape de huella entre plantas, `PasilloTopologiaValidator`
evita puntos muertos pero no exige esta distinción concreta. No
investigado a fondo todavía si es un hueco genuino o si el
comportamiento actual ya lo resuelve indirectamente.

Auditoría de flujo completo realizada a petición del usuario (recopilar
fallos/huecos de flujo, no solo bugs sueltos). El hallazgo #1
(`tipo_vivienda` sin conectar) ya está RESUELTO -- ver
`docs/architecture.md`. El hueco de fondo (no había forma de generar
sin salir a una terminal) también está RESUELTO -- ver la sección de
Pyodide arriba. Quedan estos, por orden de cómo se listaron:

- **`retranqueo_m` (retranqueo básico de vivienda aislada) no es
  configurable desde el CLI** -- toda vivienda generada por CLI tiene
  retranqueo cero, aunque el concepto está implementado y probado.
  Necesitaría un `--retranqueo N` análogo a `--lot-size`.
- **`retranqueo_incremento_por_planta_m` (contorno progresivo entre
  plantas) tampoco tiene ninguna opción de CLI** -- función construida
  e investigada (Devans, Infinigen) pero solo accesible escribiendo
  Python a mano.
- **El panel de generación automática de "Sección vertical" solo cubre
  1-2 plantas** (planta baja/superior) -- sótano, semisótano y bajo
  cubierta quedan fuera de la generación automática (sí accesibles a
  mano, chip a chip, sin cambios).
- **`AnchoLibrePracticoValidator` (1.20m) no aparece mencionado en
  ningún sitio del dashboard** -- el usuario no tiene forma de saber,
  desde la interfaz, que esta restricción existe y puede estar
  bloqueando una generación.
- **Las puertas del visor son una marca genérica (0.9m) en la pared
  compartida, no una posición/ancho/sentido de apertura real** --
  documentado como limitación en su momento, pero fácil de olvidar.
- **`CocinaIntegrada` (cocina abierta al salón) no tiene ninguna forma
  de activarse ni explicarse desde el dashboard.**
- **`--vivienda-accesible` (nuevo) tampoco aparece mencionado en el
  dashboard** -- mismo patrón que `AnchoLibrePracticoValidator`, un
  flag real del CLI sin ningún reflejo en la interfaz.

**Proyecto Lua anterior del usuario, evaluado (10 archivos: nhv.lua ya
conocido + main.lua, accesibilidad.lua, termica.lua, acustica.lua,
cubierta.lua, incendios.lua, turismo.lua, ejemplo_planta.lua,
test_framework.lua, volcado_constantes.lua)**: accesibilidad ya
conectada (`ViviendaAccesibleValidator`, ver arriba). **NO transferible
sin un salto de arquitectura mayor**: térmica (DB-HE1), acústica
(DB-HR), cubierta (DB-HS1) e incendios (DB-SI) son sobre MATERIALES Y
ELEMENTOS CONSTRUCTIVOS (transmitancia de muros, resistencia al fuego
en EI/R, pendiente de cubierta por tipo de teja) -- una capa de dominio
que `Room` no tiene (no modela paredes/materiales/estructura, solo
geometría de estancias). No descartar de raíz si el proyecto alguna
vez amplía su alcance a elementos constructivos, pero no es una
extensión natural de lo que hay hoy. Turismo (Decreto 12/2017) es un
tipo de edificio distinto (apartamentos turísticos), fuera del alcance
de vivienda unifamiliar estándar.

**Optimización de orientaciones + generación de fachada con patrones
solares reales** (`main.lua`, funciones `optimizarOrientaciones` y
`generarFachada`) -- prior art concreto y ya funcionando para
`SolarExposureValidator` (ver más abajo, sigue aparcado): sombra
estacional verano/equinoccio/invierno, no solo una idea de
investigación externa como la referencia de `building-sunlight-simulator`
ya documentada. Si se retoma `SolarExposureValidator`, revisar esto
primero -- puede ahorrar la investigación desde cero.

Y este número, como cualquier otro de este documento, se quedará
obsoleto en cuanto haya un incremento nuevo (ver "Cosas aprendidas por
las malas" más abajo). Antes de asumir que sigue siendo así, releer el
documento entero, no solo esta sección. El único punto aparcado
deliberadamente (distinto de los de arriba, que sí son pendientes
activos) es `SolarExposureValidator`, documentado abajo con referencia
externa si se retoma -- decisión de alcance, no un hueco.
- **`SolarExposureValidator`** (asoleamiento/orientación) — sigue
  deliberadamente aparcado, pero con una referencia externa concreta
  encontrada si se retoma: `github.com/SeanWong17/building-sunlight-simulator`
  (Three.js/WebGL). Usa trigonometría esférica estándar para posición
  solar -- altura `sin(h) = sin(φ)sin(δ) + cos(φ)cos(δ)cos(ω)`, azimut
  `cos(A) = (sin(h)sin(φ) − sin(δ)) / (cos(h)cos(φ))` (φ=latitud,
  δ=declinación solar según día del año, ω=ángulo horario según hora) --
  y proyección de sombras entre edificios vecinos por ray-casting,
  acumulando horas de luz directa por vivienda. La parte de sombras
  entre vecinos probablemente no aplica a nuestro alcance actual (una
  sola parcela, sin edificios vecinos modelados), pero las fórmulas de
  posición solar en sí son un punto de partida útil para una versión
  simplificada (orientación de fachada vs. ventana solar representativa,
  sin geometría de vecinos).

## Cosas aprendidas por las malas — no las repitas

- **Nunca cachear por `id(objeto)` en Python.** Python reutiliza
  direcciones de memoria de objetos liberados de forma agresiva (medido:
  1000 creaciones en bucle → 6 `id()` distintos). Si necesitas cachear por
  identidad de objeto, guarda una referencia real (`obj is cached_ref`),
  nunca solo su `id()`.
- **Un generador aleatorio (`random.Random(seed)`) creado en `__init__` y
  reutilizado en cada llamada a un método NO da resultados reproducibles
  en llamadas repetidas** — solo la primera. Si se necesita determinismo
  por llamada, reiniciar el RNG al principio del método, no en el
  constructor.
- **Antes de asumir que algo funciona igual en multi-planta que en una
  sola planta, preguntar: ¿este validador necesita ver TODAS las
  estancias del edificio, o le basta con las de esta planta?**
  (`ViviendaMinima`, Tabla 1/2 y `BanoAccesoGeneral` necesitaban ámbito de
  edificio; el resto no). Este fue el bug más recurrente de toda la
  sesión de multi-planta.
- **Antes de implementar una regla de teoría de grafos, medir con
  programas REALES, no solo con el caso ideal.** `PasilloTopologiaValidator`
  con el grafo de puertas disperso rompió 9 tests porque los programas
  reales declaran pocos `Obligatorio` — usar la adyacencia geométrica
  real lo resolvió.
- **Cuando cambias qué movimientos aleatorios usa el recocido simulado
  (o cualquier cosa que consuma la secuencia de `random.Random`), las
  semillas fijas dejan de reproducir el mismo resultado** — hay que
  rebuscar una semilla estable cada vez que esto cambia (pasó muchas
  veces ya en el proyecto; dejar de contarlas y asumirlo como algo
  habitual, no una sorpresa cada vez).
- **Investigar cómo resuelven el mismo problema otros proyectos antes de
  construir algo desde cero** dio resultado real, no solo referencias
  bonitas: la técnica de "deslizar pared" (Merrell et al. 2010), el
  patrón de "grafo de puertas" separado de la adyacencia geométrica, y el
  mecanismo de "hueco de escalera compartido" (Infinigen Indoors 2024) se
  adoptaron y funcionaron.
- **Combinar duro+blando con `duro*peso_grande + blando` garantiza el
  orden final correcto, pero puede romper la DINÁMICA de un recocido
  simulado** — `exp(-delta/temperatura)` reacciona a la magnitud
  absoluta del delta, no solo al orden relativo; un peso grande hace
  casi imposible aceptar cualquier movimiento que empeore lo duro,
  incluso con temperatura alta al principio. Usar comparación
  LEXICOGRÁFICA real (tupla `(duro, blando)`, decidir el delta de
  aceptación solo por el componente que de verdad cambió) preserva la
  dinámica ya afinada. Se encontró porque rompió un test de multi-planta
  que no tenía relación alguna con restricciones blandas -- esa fue la
  señal de que algo estructural había cambiado, no un caso aislado.
- **Este mismo documento (`CONTINUIDAD.md`) se quedó obsoleto varias
  veces sobre sí mismo**, pese a ser el que exige no hacerlo: el título
  de una sección decía "15 validadores" con una lista que ya sumaba 18;
  dos secciones marcadas "RESUELTO" seguían describiendo como
  "pendiente" algo ya resuelto en una ronda posterior; y las cifras del
  encabezado (tests/cobertura/commits) llevaban varias rondas sin
  actualizar. Ninguno de estos números se mantiene solo -- cada vez que
  alguien pregunta "¿seguro que es lo único pendiente?", vale la pena
  releer el documento entero, no solo la sección de pendientes.
- **`jsdom` (cargar y ejecutar el HTML real, simular clics/eventos
  reales) encuentra bugs que `node --check` nunca puede** — `--check`
  solo valida sintaxis, nunca comportamiento en tiempo de ejecución
  contra un DOM real. Encontró una colisión de nombres real (`FLOORS`
  con dos significados distintos en los dos archivos fusionados) y un
  `TypeError` sin capturar (cargar el formato de archivo equivocado en
  el visor) que ninguna lectura de código habría detectado con la misma
  certeza.
- **En un SVG, `stroke-width` se interpreta en las mismas unidades que
  el `viewBox`.** Si el `viewBox` está en metros (coordenadas reales de
  una vivienda, no píxeles de pantalla), un `stroke-width` pensado como
  "un valor razonable en píxeles" se convierte en metros de grosor --
  bug real que generaba curvas/círculos gigantes tragándose el plano.
  Cualquier valor de grosor de línea en un SVG con coordenadas no-pixel
  hay que pensarlo explícitamente en esas unidades, no copiarlo de un
  ejemplo pensado para píxeles.
- **Cuando una captura de pantalla real del usuario revela un problema
  que ninguna verificación automatizada detectó, no asumir que el
  problema es "solo esta vez" -- preguntarse si hay una categoría
  entera de problemas (aspecto visual, proporciones, unidades) que
  ninguna de las herramientas de verificación disponibles puede cubrir
  en absoluto**, y decirlo con esa misma claridad en vez de fingir
  cobertura completa.
- **Antes de relajar un umbral que "hace la búsqueda más difícil",
  investigar si hay una técnica conocida para resolver la causa
  estructural, no solo el síntoma.** `AnchoLibrePracticoValidator` por
  sí solo hizo que un caso real dejara de converger incluso con 30.000
  iteraciones -- la heurística de "cortar por el lado más largo"
  (Marson & Musse 2010, ya citados antes en este mismo proyecto para
  el treemap de zonificación) lo redujo a 5.000, sin bajar ningún
  mínimo. Aislar la causa (quitando temporalmente el validador nuevo,
  confirmando que SIN él la misma semilla converge rápido) confirmó que
  era la causa real antes de invertir tiempo en la investigación.

## Cómo verificar que todo sigue en orden

```bash
cd housing_generator
python -m pytest -q                                          # deberia dar 342 passed (o mas) -- tarda varios minutos, los tests de --import-seleccion/reintento son lentos (subprocess real)
python -m pytest --cov=housing_generator --cov-report=term-missing -q  # 85%+ (o mas)
python -m housing_generator.interface.cli.main --output /tmp/x.json    # CLI real
git log --oneline | head -5                                   # historial reciente
```

## Preferencias de trabajo de esta sesión (para mantener el mismo estilo)

- Incrementos pequeños, con tests antes de dar nada por bueno.
- Verificar contra la fuente normativa exacta (Decreto 29/2010 de Galicia),
  nunca asumir desde estándares genéricos de otras comunidades — esto
  falló una vez (programa mínimo) y se corrigió.
- Documentar honestamente lo que queda sin resolver, no ocultarlo.
- Antes de aceptar un resultado, preguntarse "¿estamos seguros?" — varias
  correcciones reales de esta sesión salieron de esa pregunta, no de un
  fallo visible.
- Antes de construir algo grande, confirmar el alcance con preguntas
  concretas de opción múltiple, no asumir.
