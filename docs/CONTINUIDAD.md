# housing_generator — Estado del proyecto (documento de continuidad)

> Este documento existe para que una conversación nueva (sin el historial de
> esta) pueda retomar el trabajo sin perder contexto. Los docs técnicos
> detallados siguen en `docs/architecture.md` (decisiones + auditorías),
> `docs/relaciones_espaciales.md` (catálogo de 120 pares + huecos de modelo)
> y `docs/niveles_plantas.md` (niveles, escalera, bajantes). Este documento
> es un resumen de alto nivel para orientarse rápido, no un sustituto de esos.

## Qué es esto

Sistema generativo de plantas residenciales en Python, cumplimiento del
Decreto 29/2010 de Galicia (habitabilidad, modificado por Decreto 128/2023).
Arquitectura hexagonal estricta. Generación por recocido simulado sobre un
árbol de partición. 15 validadores normativos + multi-planta con escalera.

**Estado en el momento de escribir esto**: 234/234 tests, 97% cobertura,
15 commits de git, working tree limpio.

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
  architecture.md            decisiones + auditorías, en orden cronológico
  relaciones_espaciales.md   catálogo de 120 pares de adyacencia + huecos de modelo
  niveles_plantas.md         niveles, escalera (CTE DB-SUA 1), bajantes

docs/visualizador/relaciones_espaciales.html   dashboard standalone (4 pestañas)
```

Para entender el estado real, **`docs/architecture.md` es la fuente de verdad**
— cada sección nueva se añadió cronológicamente con lo que se decidió, lo que
se encontró roto, y por qué. Merece la pena leerlo entero antes de tocar nada
grande.

## Los 15 validadores (todos en `infrastructure/algorithms/constraints/`)

Por planta (`build_per_floor_validators` en `container.py`): Adjacency,
NucleoHumedo, zonificación día/noche/servicio, EstanciaMinimumArea (Tabla 1),
ServicioMinimumArea (Tabla 2), DormitorioArmario, TrasteroMinimumArea,
AnchoLibreEstancia, AnchoLibrePasillo, AlturaLibre, ExteriorContact,
CocinaIntegrada, EspacioAcceso, EscaleraAnchoLibre, PasilloTopologia.

De ámbito EDIFICIO (no por planta, se comprueban aparte en
`GenerateBuildingUseCase`): ViviendaMinima (programa mínimo, une todas las
plantas), BanoAccesoGeneral (al menos un baño con acceso general en ALGUNA
planta).

Entre plantas consecutivas (parametrizados con la planta ya resuelta):
EscaleraAlineacion (huella ≥90% de solape), NucleoHumedoVertical (bajantes).

## Multi-planta — cómo funciona

`GenerateBuildingUseCase.execute(program, lot)`: agrupa `program.rooms` por
`Room.level` (`NivelPlanta`), genera cada planta de abajo a arriba con el
MISMO generador de una sola planta (búsqueda independiente, no conjunta),
pasando referencias fijas (huella de escalera, huellas húmedas) de la planta
ya resuelta a la siguiente. `RoomType.STAIRCASE` conecta plantas.

**Simplificación deliberada, no resuelta**: todas las plantas comparten el
mismo `lot.buildable_area` (mismo contorno para todas). Reducir el contorno
planta a planta queda pendiente si se retoma.

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

## Pendiente real, si se retoma

- **Formalizar el catálogo de 120 pares como estructura ejecutable**
  (`DEFAULT_TYPE_ADJACENCY`) — ya no bloqueado (los 3 huecos de modelo que
  lo impedían están resueltos, y las restricciones blandas ya tienen
  mecanismo real al que conectarse). Pendiente de construir.
- **Importador JSON (exportación de la sección vertical del dashboard) →
  Program real** — discutido, no construido. Derivaría `Obligatorio` Y
  ahora también `Preferencia` automáticamente del catálogo formalizado.
- **Vivienda pareada/adosada** (medianeras) — solo aislada implementada
  (retranqueo). Extensión natural: añadir "lados de medianera" a `Lot`.
- **Reducir el contorno edificable planta a planta** (en vez de compartir
  el mismo en todas) — la opción más compleja de las dos vistas en
  investigación externa (Infinigen Indoors), deliberadamente pospuesta.
- **Ranking global de Tabla 1**: ya resuelto (`global_rank_override`,
  precalculado por `GenerateBuildingUseCase`) — mencionado aquí solo para
  que quede claro que NO es un pendiente, por si se confunde con la nota
  anterior de contorno compartido.

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
  rebuscar una semilla estable cada vez que esto cambia (pasó dos veces
  en esta sesión).
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

## Cómo verificar que todo sigue en orden

```bash
cd housing_generator
python -m pytest -q                                          # deberia dar 234 passed
python -m pytest --cov=housing_generator --cov-report=term-missing -q  # 97%
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
