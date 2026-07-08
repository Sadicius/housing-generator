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
Todavía no está conectado como opción automática en `container.py`/CLI
(la función existe y funciona, pero nadie la llama por defecto) --
pendiente si se quiere ese último paso de integración.

## Pendiente real, si se retoma

- **Importador JSON (exportación de la sección vertical del dashboard) →
  Program real** — discutido, no construido. Con el catálogo ya
  formalizado, derivaría `Obligatorio` y `Preferencia` automáticamente
  vía `generate_adjacency_requirements`, no habría que construir esa
  parte desde cero.
- **Vivienda pareada/adosada** (medianeras) — solo aislada implementada
  (retranqueo). Extensión natural: añadir "lados de medianera" a `Lot`.
- **Conectar `generate_adjacency_requirements` como opción automática**
  en `container.py`/CLI (hoy solo existe como función que hay que
  llamar a mano antes de construir el `Program`).
- **Reducir el contorno edificable planta a planta** (en vez de compartir
  el mismo en todas) — la opción más compleja de las dos vistas en
  investigación externa (Infinigen Indoors), deliberadamente pospuesta.
- **Ranking global de Tabla 1**: ya resuelto (`global_rank_override`,
  precalculado por `GenerateBuildingUseCase`) — mencionado aquí solo para
  que quede claro que NO es un pendiente, por si se confunde con la nota
  anterior de contorno compartido.
- **GARAGE en sótano vs. contacto exterior**: un garaje en `SOTANO` exige
  también contacto exterior (`ExteriorContactValidator`, acceso
  vehicular) -- solo se puede satisfacer con una rampa que corte el
  nivel de rasante, que el modelo actual no distingue de una fachada
  plana normal. Encontrado al aplicar esta misma convención de
  documentación sobre `niveles_plantas.md`; no es peligroso (no genera
  resultados incorrectos), pero está sin resolver de verdad.

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
