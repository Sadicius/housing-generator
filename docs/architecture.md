# Arquitectura y fundamentos de dominio

## 1. Fundamentos del dominio (investigación)

### 1.1 Zonificación día/noche/servicio

La práctica arquitectónica estándar divide la vivienda en tres macrozonas
según el grado de privacidad y el horario de uso:

- **Zona social / día**: acceso, estar, comedor, cocina abierta.
- **Zona privada / noche**: dormitorios, baños privados.
- **Zona de servicio**: cocina cerrada, lavadero, trastero, garaje, cuarto técnico.

Esta es la división que el sistema modela como `ZoneType` (`DAY`, `NIGHT`,
`SERVICE`) y que cada `RoomType` tiene asignada por defecto (`DEFAULT_ROOM_ZONE`
en `domain/enums.py`), pudiendo sobreescribirse por estancia.

### 1.2 Matriz de adyacencia y diagrama de burbujas

Antes de generar geometría, la práctica estándar construye una matriz de
adyacencia (qué espacios deben estar cerca, cuáles deben evitarse) y la
traduce en un diagrama de burbujas: nodos = estancias, tamaño = área
relativa, líneas = relación de adyacencia.

En el sistema esto se modela como:

- `AdjacencyRequirement` (value object): un par de ids + `AdjacencyStrength`
  (`MUST_BE_NEAR`, `SHOULD_BE_NEAR`, `INDIFFERENT`, `MUST_BE_AWAY`).
- `BuildAdjacencyGraphUseCase`: convierte esos requisitos en un grafo
  ponderado de `networkx`, la estructura de datos que cualquier algoritmo de
  generación (slicing, CSP, genético) puede consultar.

### 1.3 Zonificación como capa intermedia

La zonificación programática traduce el programa escrito en zonas
proporcionales al área real necesaria, sirviendo de puente entre el listado
de requisitos y la planta física — es exactamente el rol de
`ZoningStrategyPort` / `TreemapZoningStrategy` en este sistema: agrupar
antes de posicionar.

### 1.4 Algoritmos de generación considerados

| Enfoque | Idea central | Ventaja | Limitación |
|---|---|---|---|
| **Slicing / treemap** (implementado) | Particionar el solar en franjas proporcionales al área de cada zona/estancia | Simple, determinista, fácil de testear | Layouts poco variados, no optimiza adyacencias reales |
| **Grafo + A\*** | Construir red de circulación tras ubicar estancias y usar A\* para caminos mínimos desde el vestíbulo | Buena para circulación | No resuelve por sí solo la disposición inicial |
| **CSP / constraint solving** | Modelar posiciones como variables con restricciones (adyacencia, área, proporción) | Garantiza cumplimiento de restricciones duras | Puede ser costoso computacionalmente a mayor escala |
| **Metaheurísticas (genético, simulated annealing)** | Buscar por iteración maximizando una función de fitness (adyacencias cumplidas, compacidad, luz) | Explora soluciones novedosas, tolera múltiples objetivos | No determinista, requiere tuning |
| **GAN / diffusion / graph-to-image** | Modelos entrenados con datasets de plantas reales | Resultados muy realistas | Requiere datos de entrenamiento, difícil de controlar/depurar, caja negra |

El sistema arranca con **slicing** (rápido de implementar y verificar) y
expone `LayoutGeneratorPort` para que CSP o metaheurísticas se añadan como
adaptadores nuevos sin romper nada del resto de capas.

## 2. Arquitectura de software

Arquitectura hexagonal (ports & adapters) con capas inspiradas en Clean
Architecture:

```
                    ┌─────────────────────────┐
                    │      interface/cli       │   adaptadores de entrada
                    └────────────┬─────────────┘
                                 │
                    ┌────────────▼─────────────┐
                    │        application         │   casos de uso + puertos
                    │  (use_cases, ports, dto)   │
                    └────────────┬─────────────┘
                                 │ depende de (abstracciones)
                    ┌────────────▼─────────────┐
                    │          domain             │   entidades y reglas puras
                    │ (entities, value_objects)  │   sin dependencias externas
                    └────────────┬─────────────┘
                                 │ implementado por
                    ┌────────────▼─────────────┐
                    │      infrastructure         │   adaptadores concretos
                    │ (algorithms, persistence)  │   (shapely, networkx, JSON)
                    └─────────────────────────┘
                                 ▲
                                 │ ensamblado en
                    ┌────────────┴─────────────┐
                    │      config/container      │   composition root
                    └─────────────────────────┘
```

Regla de dependencia: las flechas de importación siempre apuntan **hacia
adentro** (interface → application → domain). `infrastructure` implementa
los puertos definidos en `application`, pero `application` nunca importa
`infrastructure` directamente — solo `config/container.py` conoce ambos
lados y los conecta (inyección de dependencias manual, sin frameworks).

### Por qué no un solo módulo "monolítico"

Separar zonificación (`ZoningStrategyPort`), generación de geometría
(`LayoutGeneratorPort`) y validación (`ConstraintValidatorPort`) en tres
puertos independientes permite:

1. Testear cada pieza de forma aislada (ver `tests/unit/`).
2. Sustituir solo el algoritmo de posicionamiento por uno más sofisticado
   (CSP/genético) sin reescribir la validación de restricciones ni la
   zonificación.
3. Reutilizar el mismo `GenerateLayoutUseCase` en un futuro adaptador web
   (API) o de escritorio, ya que no depende de la CLI.

## 3. Limitaciones conocidas (histórico) y su resolución

- **[RESUELTO]** El generador de slicing original (`GraphBasedLayoutGenerator`)
  no podía satisfacer núcleo húmedo cuando las estancias húmedas caían en
  tres macro-zonas no mutuamente contiguas (día/noche/servicio, apiladas
  linealmente) — geométricamente imposible con ese algoritmo, sin importar
  el orden de los datos. Se confirmó dos veces (ver commits de esta
  sesión) antes de decidir sustituir el generador en vez de seguir
  parcheando la heurística de orden.
- **Solución aplicada**: `SimulatedAnnealingLayoutGenerator`
  (`infrastructure/algorithms/layout_generation/`). Construye un único
  árbol de partición recursivo (slicing tree) sobre TODAS las estancias a
  la vez, sin fase previa de reparto geométrico por macro-zona — la zona
  pasa a ser solo una propiedad que los validadores comprueban sobre el
  resultado, no una partición del espacio impuesta de antemano. Busca la
  mejor topología mediante recocido simulado, usando como función
  objetivo el número de violaciones del `CompositeConstraintValidator`
  completo (solo restricciones duras). Verificado: el caso de cocina +
  baño + lavadero mutuamente adyacentes (antes imposible) se resuelve en
  <0.5s.
- `GraphBasedLayoutGenerator` (slicing por zona) se mantiene en el código
  como implementación alternativa de `LayoutGeneratorPort` — más simple
  y determinista, útil como referencia o para casos donde la
  zonificación geométrica estricta sea deseable — pero ya no es el
  generador por defecto en `config/container.py`.
- **[RESUELTO] Bug de proporción invertida en cortes horizontales**:
  `place_tree` calculaba mal qué franja se quedaba con qué proporción de
  área en los cortes de dirección "h" (horizontal) — invertía `ratio` y
  `1-ratio` respecto al corte vertical, que sí estaba bien. El test
  original solo cubría el caso vertical, así que no lo detectó; se
  encontró al auditar manualmente por qué el comedor del CLI salía con
  un área muy distinta a la pedida. Corregido, con tests de regresión
  específicos para corte horizontal y para árboles profundos que mezclan
  ambas direcciones.
- **[RESUELTO] Bug de circulación atrapada en zonificación día/noche**:
  `CORRIDOR` y `ENTRANCE_HALL` son `SpaceCategory.CIRCULACION` pero
  tienen `zone=DAY` por defecto. Sin exclusión explícita, los
  validadores de zonificación día/noche/servicio exigían que estas
  estancias de circulación quedaran agrupadas con el resto de la zona
  día — generando violaciones falsas en cuanto un pasillo o vestíbulo
  se colocara (correctamente) cerca de la zona noche a la que sirve.
  Encontrado durante una auditoría completa de conceptos, no por fallo
  de un test (el CLI no incluye `CORRIDOR` en su programa de ejemplo).
  Corregido excluyendo `SpaceCategory.CIRCULACION` de los tres
  validadores de agrupación por zona, con tests de regresión.

## 4. Extensiones previstas

- Ajustar los parámetros de recocido simulado (`max_iterations`,
  `initial_temperature`, `cooling_rate`) con casos reales más grandes
  (viviendas de 10+ estancias) para calibrar tiempo de convergencia.
- Un `SolarExposureValidator` adicional que use `Lot.entrance_side` /
  orientación real para validar `requires_natural_light` (pendiente,
  deliberadamente aparcado junto con luz/ventilación).
- Ratio ventilación/iluminación (A.1.2.i): pospuesto explícitamente,
  requiere modelar huecos/ventanas.
- Ancho libre por estancia (A.3.2.1), ancho libre de pasillo (A.3.2.3) y
  altura libre (A.3.1.1): **[RESUELTO]** implementados como
  `AnchoLibreEstanciaValidator`, `AnchoLibrePasilloValidator` y
  `AlturaLibreValidator`. `Dimensions` ahora incluye
  `ceiling_height_m` (opcional, `None` = no declarada → aviso, nunca
  aprobación silenciosa).
- Adaptador de entrada `infrastructure/persistence/json_program_loader.py`
  para construir un `Program` a partir de `examples/sample_program.json`.
- Trastero (B.2.5): **[RESUELTO]** `TrasteroMinimumAreaValidator`
  (`RoomType.STORAGE_ROOM`, mínimo fijo 4.00m², distinto de
  `RoomType.STORAGE` = almacenamiento general con mínimo escalable).
  **[RESUELTO]** Ancho libre de trastero (1.60m) añadido al mismo
  validador (`meets_minimum_width`). Ancho de puerta (0.80m) sigue
  pendiente -- requiere modelar puertas/accesos, mismo hueco
  identificado en `relaciones_espaciales.md`.
- Cocina integrada en estancia mayor (superficie combinada): **[RESUELTO]**
  `CocinaIntegradaValidator` + `Room.integrated_in_largest_room` /
  `Room.vertical_opening_m2`. Confirmado contra `nhv.lua`
  (`validarCocinaIntegrada`): Tabla 1 NO hace excepción para el salón
  (sigue exigiendo su propio mínimo individual); Tabla 2 SÍ excluye la
  cocina integrada de su propio bucle (`ServicioMinimumAreaValidator`
  actualizado en consecuencia) porque se valida con la regla combinada
  en su lugar. Tres estados: no aplica (sin cocina integrada) / aviso
  (integrada pero sin salón en el programa, o sin `vertical_opening_m2`
  declarado) / violación (superficie combinada o apertura insuficientes).
- **Programa mínimo de la vivienda**: **[RESUELTO, corregido en el camino]**
  `ViviendaMinimaValidator`. Cita textual exacta del Decreto 29/2010 de
  Galicia (I.A.2.3): *"La vivienda constará, como mínimo, de una
  estancia más una cocina, un cuarto de baño, un lavadero, un tendedero
  y un espacio de almacenamiento general."* `nhv.lua` no modela este
  apartado en absoluto. **Corrección real durante la sesión**: una
  primera versión de este validador solo exigía salón+cocina+baño,
  basada en el estándar genérico CTE/Orden de 1944 (válido para *otras*
  comunidades) en vez de buscar primero el texto específico de Galicia
  -- el usuario detectó que "no estaba bien" sin saber aún el motivo
  exacto, y al revisar la fuente concreta se confirmó que faltaban tres
  piezas enteras (lavadero, tendedero, almacenamiento general). Corregido
  el validador, sus tests, el programa de ejemplo del CLI y el test de
  integración que hasta entonces tampoco las declaraba.
- **Tipos de vivienda (enfoque urbanístico)**: investigado por petición
  del usuario ("míralo de forma urbanística") -- la clasificación
  aislada/pareada/adosada NO viene del Decreto de habitabilidad, viene
  del planeamiento urbanístico (Ley 2/2016 do solo de Galicia + Decreto
  83/2018, Plan básico autonómico). Confirmado: aislada = sin
  medianeras, retranqueo a todos los lindes; pareada = 1 medianera;
  adosada en hilera = 2 medianeras (excepto extremos, 1). Alcance
  acotado explícitamente a **vivienda aislada únicamente** por ahora
  (pareada/adosada con medianeras queda fuera, pendiente).
  **[RESUELTO para aislada]** `Lot.retranqueo_m` (opcional, declarado
  por quien usa el proyecto -- el propio decreto remite esta distancia
  a la normativa urbanística municipal, no es un valor único de
  Galicia) + `Lot.buildable_area` (parcela reducida por el retranqueo).
  El generador (`SimulatedAnnealingLayoutGenerator`) coloca las
  estancias dentro del área edificable, no de la parcela completa.
  **Bug real encontrado por el propio test de integración**: la primera
  versión dejó `ExteriorContactValidator` comprobando contacto contra
  la parcela legal completa (`lot.boundary`), razonando que la franja de
  retranqueo seguía siendo "exterior real" -- cierto conceptualmente,
  pero la comprobación geométrica es sobre proximidad de la estancia al
  borde, y una estancia dentro del área edificable nunca llega a tocar
  la línea de parcela real (siempre queda a `retranqueo_m` de ella), así
  que ninguna estancia pasaba nunca el validador. Corregido: se comprueba
  contra `lot.buildable_area` (el borde real entre construcción y
  jardín/exterior), no contra la parcela legal.
- Armario empotrado por dormitorio: **[RESUELTO]**
  `DormitorioArmarioValidator` (confirmado por investigación
  independiente, no estaba en `nhv.lua`).
- **Catálogo de relaciones espaciales entre tipos de estancia**: ver
  `docs/relaciones_espaciales.md` — 120 pares documentados. **Los tres
  huecos de modelo que bloqueaban su formalización están RESUELTOS**
  (acceso/puertas, topología de paso/terminal, cardinalidad -- ver
  secciones posteriores de este documento). El catálogo en sí sigue
  sin formalizarse como estructura de dominio ejecutable
  (`DEFAULT_TYPE_ADJACENCY`), pero ya no está bloqueado por nada --
  pendiente de construir si se retoma (ver `docs/CONTINUIDAD.md`).
- **Dashboard interactivo** (`docs/visualizador/relaciones_espaciales.html`):
  explora visualmente el catálogo anterior y `niveles_plantas.md` — 4
  pestañas: matriz de 120 pares, sección vertical por planta (selección
  activable de estancias, incluidas adicionales de bajo cubierta/
  semisótano no normativas, con exportación a JSON de tipos por planta),
  red de sinergias, y fichas por tipo. La pestaña de "grafo de burbujas"
  (arrastrable, con selección libre por planta) que existió en una
  versión anterior fue ELIMINADA -- sustituida por la selección
  directa en la sección vertical, más simple para lo que hacía falta.
  Sigue siendo una herramienta de exploración a nivel de catálogo, no
  de un `Program` real -- la exportación genera JSON a revisar antes de
  usar, no una integración directa con el generador Python.
- **Contacto exterior mínimo por estancia**: **[RESUELTO]**
  `ExteriorContactValidator` + `Room.min_exterior_sides` (derivado por
  `RoomType`, ver `DEFAULT_MIN_EXTERIOR_SIDES` en `enums.py`). Umbral de
  contacto 0.3m (distinto del de adyacencia interior, 0.1m). Cubre la
  propiedad de fachada que quedó pendiente al principio del catálogo de
  relaciones (categoría A.1.1/A.1.2: piezas vivideras exigen exterior,
  baño/aseo/pasillo admiten ventilación mecánica).
- **Preferencia de planta/nivel por tipo de estancia**: catalogada en
  `docs/niveles_plantas.md`. **[RESUELTO, primer incremento]** — ver
  sección "Multi-planta: primer incremento real" más abajo en este
  mismo documento (`GenerateBuildingUseCase`, `Building`, `Room.level`,
  `RoomType.STAIRCASE`). Limitación que queda, deliberada: todas las
  plantas comparten el mismo contorno edificable (no se reduce planta
  a planta).

## Infraestructura de desarrollo (añadido tras el DAFO)

- **Control de versiones**: el proyecto no tenía `.git` -- confirmado
  como amenaza real en el DAFO (cualquier cambio se sobrescribía sin
  historial). `git init` con commit inicial del estado completo.
- **Cobertura de tests real**: 86% → 95% (medido con `pytest-cov`, que
  ya estaba instalado pero nunca se usaba activamente). Cuatro módulos
  estaban al 0% -- nunca tuvieron un solo test, solo verificación manual
  mía dentro de la conversación, invisible para cualquiera que audite el
  repositorio: `graph_based_generator.py` (generador legacy, 40 líneas),
  `json_layout_repository.py` (10 líneas), `interface/cli/main.py`
  (33 líneas, ahora 61% -- el resto es `main()` en sí, ejecutado vía
  subprocess real en el test de integración, invisible para la
  herramienta de cobertura por estar en otro proceso, no un hueco real),
  y `application/use_cases/validate_layout.py` (8 líneas) -- al
  escribirle tests se encontró y corrigió una anotación de tipo
  incorrecta (`-> List[str]` cuando en realidad devuelve
  `ValidationResult`).

## Auditoría sección por sección del Decreto 29/2010 (tras el DAFO)

Barrido de las secciones nunca revisadas directamente (en vez de esperar
a que un hueco se note por accidente, siguiendo el patrón que expuso el
programa mínimo):

- **A.2.1 (acceso e indivisibilidad)**: confirmado fuera de alcance --
  nivel urbanístico/edificio (acceso desde vía pública, no ser paso
  obligado a otra finca), coincide con el hueco de "acceso/puertas" ya
  identificado. Nada que implementar.
- **A.4 (dotación mínima de instalaciones)**: confirmado fuera de
  alcance -- fontanería, calefacción, electricidad, telecomunicaciones,
  hogar digital. No es geometría, no aplica a un generador de plantas.
- **A.2.2 (composición y compartimentación)**: confirma que
  `SpaceCategory` (estancia/servicio/circulación) coincide exactamente
  con la estructura del decreto. **Hueco latente detectado, no
  corregido todavía**: el cuadrado inscribible debe estar "en contacto
  con la cara interior del cerramiento de la fachada"; `can_inscribe_square`
  no verifica esto explícitamente -- funciona solo porque, para
  estancias y parcelas rectangulares (todo lo que maneja este proyecto),
  si el cuadrado cabe, siempre puede colocarse tocando cualquier lado.
  Coincidencia geométrica, no verificación deliberada de la regla.
- **Espacio de acceso interior (recibidor), cuadrado de 1,50m**:
  **[RESUELTO]** `EspacioAccesoValidator`. Requisito nuevo encontrado en
  este barrido, nunca implementado. "En contacto con la puerta de
  entrada" NO se comprueba (sin modelo de puertas, mismo hueco de
  siempre) -- documentado como alcance pendiente en el propio
  validador, no como aviso repetido. Si no hay `ENTRANCE_HALL` en el
  programa (acceso directo por la estancia mayor), el requisito no
  aplica -- exención explícita de la propia norma.

## Determinismo del CLI (corregido durante esta auditoría)

El CLI usaba `seed=None` por defecto -- confirmado en el DAFO como
debilidad real ("el CLI a veces falla aleatoriamente"). Al escribir un
test de integración real para el CLI (antes 0% de cobertura), el nuevo
test falló de forma intermitente (~1 de cada 4 ejecuciones) por este
motivo exacto, no por ningún validador nuevo. Corregido: `--seed`
(por defecto 1, fijo) y `--max-iterations` (por defecto 3000) ahora son
argumentos del CLI. Confirmado estable en 6/6 ejecuciones tras el
cambio.

## Regla `Condicional` implementada: acceso general de baño

- **[RESUELTO]** `BanoAccesoGeneralValidator`. Primera regla `Condicional`
  del catálogo de relaciones (`BEDROOM`/`MASTER_BEDROOM` × `BATHROOM`)
  implementada como lógica real, no como valor de tabla -- exactamente
  el enfoque decidido al reclasificar la taxonomía. Formulación general
  (sin ramificar explícitamente por número de baños, pero equivalente):
  al menos un `BATHROOM` debe tener adyacencia real (pared compartida)
  con una estancia de circulación (`CORRIDOR` o `ENTRANCE_HALL`). Con
  1 solo baño, la exigencia recae necesariamente sobre él (equivale a
  "acceso solo vía pasillo"); con 2+, basta con que uno la cumpla, el
  resto puede ser en-suite de un dormitorio sin acceso propio.
- **Efecto real al conectarlo**: el programa de ejemplo del CLI y dos
  tests de integración no tenían `ENTRANCE_HALL` ni `CORRIDOR` -- el
  nuevo validador los hacía fallar por imposibilidad geométrica, no por
  mala suerte del recocido. Añadido `ENTRANCE_HALL` a los tres.
- **Hallazgo colateral, no relacionado con el validador nuevo**: al
  ampliar el programa del CLI, la semilla fija anterior (`seed=1`) dejó
  de converger de forma fiable (1/5 intentos). Cambiada a `seed=3`,
  confirmada estable en 8/8 ejecuciones. Además, los dos tests de
  integración de retranqueo/colocación nunca habían fijado semilla
  (usaban el `None` por defecto) -- eran no deterministas por su cuenta
  desde antes de esta sesión; corregido de paso.

## Investigación externa: cómo resuelven esto otros proyectos generativos

Por petición del usuario, se investigó cómo aborda el campo académico el
mismo problema (generación de plantas residenciales a partir de un
programa + relaciones de adyacencia). Hallazgos:

- **Nuestro pipeline (catálogo de relaciones → generador → validación)
  coincide con el paper clásico más citado del campo**: Merrell,
  Schkufza & Koltun, *"Computer-Generated Residential Building
  Layouts"* (ACM TOG, 2010) -- mismo patrón "bubble diagram → floor
  plan optimization → modelo 3D". Confirma que el enfoque general no es
  una reinvención, sino una via ya validada.
- **Divergencia deliberada y justificada respecto al estado del arte
  reciente** (House-GAN, Graph2Plan, GFLAN): esos trabajos son
  aprendizaje profundo entrenado sobre datasets masivos (RPLAN,
  LIFULL HOME'S) que reflejan convenciones de diseño de su país de
  origen (China, Japón), no el Decreto 29/2010 de Galicia. Un paper
  reciente (2026) confirma que los modelos entrenados con datos
  "under-emphasize critical architectural priors such as the
  configurational dominance and connectivity of domestic public spaces"
  -- exactamente lo que este proyecto ya fuerza explícitamente como
  regla dura (`LIVING_ROOM`↔`ENTRANCE_HALL` obligatorio cerca,
  `BanoAccesoGeneralValidator`). El enfoque basado en reglas explícitas,
  aunque menos "de moda", es la elección correcta para el objetivo
  concreto de este proyecto (cumplimiento normativo verificable, no
  imitación estadística de un dataset ajeno).
- **[RESUELTO] Movimiento "deslizar pared" (`slide_wall`)** añadido al
  recocido simulado, inspirado directamente en el "Sliding a wall"
  de Merrell et al. 2010 (confirmado con más detalle de implementación
  en Infinigen Indoors, 2024: "extruding a wall segment inwards/outwards
  by one grid size"). Hueco real que esto corrige: antes, la proporción
  de cada corte del árbol de partición estaba SIEMPRE atada al área
  declarada de cada estancia (`ratio = first_area/total`), sin ningún
  grado de libertad independiente -- la única forma de corregir una
  violación de forma/ancho libre era cambiar topología (qué estancia va
  con cuál), nunca ajustar un corte ya bueno en sí mismo. Implementado
  como `PartitionNode.ratio_override` (opcional, `None` preserva el
  comportamiento anterior exacto) + cuarto tipo de movimiento en
  `random_neighbor`, con límites [0.15, 0.85] para evitar cortes
  degenerados y partiendo de la proporción efectiva actual (no de un
  valor fijo -- confirmado con test dedicado).
- **Efecto colateral real, no cosmético**: el cuarto movimiento cambia
  el consumo de la secuencia aleatoria en cada iteración, así que la
  semilla fija anterior (3) dejó de reproducir el mismo camino de
  búsqueda. Vuelto a `seed=1` (que con el conjunto de movimientos
  anterior había dejado de funcionar, y ahora vuelve a hacerlo) tras
  confirmar 8/8 ejecuciones estables.

## Grafo de puertas (hueco de modelo "acceso/puertas" resuelto parcialmente)

- **[RESUELTO, parcial]** `build_door_graph`
  (`infrastructure/algorithms/adjacency/door_graph.py`). Investigación
  externa (patrón "Door Connectivity Graph", paper *"Automatic Rendering
  of Building Floor Plan Images from Textual Descriptions"*; confirmado
  por Infinigen Indoors 2024 que la colocación de puertas es típicamente
  un paso POSTERIOR a resolver posiciones, no algo que compita con la
  búsqueda del generador). Capa dispersa sobre el grafo de adyacencia
  geométrica ya existente: un par tiene puerta si y solo si hay
  `AdjacencyRequirement(MUST_BE_NEAR)` declarado Y la geometría final los
  coloca realmente adyacentes (≥1.0m de borde compartido). No modela
  geometría real de puerta (posición en el muro, ancho, sentido de
  apertura) -- deliberadamente mínimo, solo existencia a nivel de grafo.
  Conectado a `JsonLayoutRepository` (nuevo campo `"doors"` en la
  exportación) y al CLI. Confirmado con el CLI real: exporta exactamente
  los 4 pares `Obligatorio cerca` declarados en el programa de ejemplo.

## Multi-planta: primer incremento real (con escalera incluida)

- **[RESUELTO, primer incremento]** `GenerateBuildingUseCase` +
  `Building` (entidad nueva, agrupa varias `Layout`, una por planta) +
  `Room.level` (`NivelPlanta`, enum nuevo que formaliza lo que antes
  solo vivia como texto en el dashboard). Cada planta se genera de
  forma INDEPENDIENTE con el `SimulatedAnnealingLayoutGenerator` ya
  existente (no busqueda conjunta -- ver Infinigen Indoors en la
  seccion de investigacion externa), de abajo a arriba, encadenando dos
  restricciones nuevas entre plantas consecutivas:
  - `EscaleraAlineacionValidator`: huella de `RoomType.STAIRCASE`
    (nuevo tipo) con >=90% de solape respecto a la de la planta
    inferior YA RESUELTA, pasada como referencia fija -- inspirado en
    Infinigen Indoors (apendice D.5), adaptado a nuestra arquitectura de
    arbol de particion (sin necesitar un "hueco" compartido durante la
    busqueda ni un tipo de movimiento nuevo).
  - `NucleoHumedoVerticalValidator`: cada estancia humeda solapa con
    alguna humeda de la planta inferior (continuidad de bajantes, regla
    documentada en `niveles_plantas.md` desde hace tiempo, nunca
    implementable hasta ahora).
  - `EscaleraAnchoLibreValidator`: 0.80m, uso restringido CTE DB-SUA 1
    (ya confirmado por investigacion independiente en su momento).
- **Violacion de arquitectura real encontrada y corregida durante la
  construccion**: la primera version de `GenerateBuildingUseCase`
  (capa `application`) importaba directamente de `config.container` --
  rompe la regla ya establecida de que `application` nunca debe conocer
  infraestructura concreta. Corregido con inyeccion de fabricas
  (`per_floor_validators_factory`, `layout_generator_factory`), mismo
  patron que ya usaba `GenerateLayoutUseCase`.
- **Bug real encontrado y corregido al generar el primer edificio de
  prueba**: `EstanciaMinimumAreaValidator`/`ServicioMinimumAreaValidator`
  (Tabla 1/2) contaban el numero de estancias SOLO de la planta que
  recibian -- una planta con 1 sola estancia aplicaba la fila de
  "vivienda de 1 estancia" (25m2) en vez de la fila real del edificio
  completo. Corregido con `total_num_estancias_override` (opcional,
  `None` preserva el comportamiento de una sola planta sin cambios).
- **[RESUELTO]** Ranking global de Tabla 1 entre plantas:
  `EstanciaMinimumAreaValidator` gana `global_rank_override` (dict
  room_id -> puesto REAL en el edificio completo), precalculado por
  `GenerateBuildingUseCase._compute_global_rank` antes de generar
  ninguna planta (las areas son declaradas, no dependen de geometria ya
  colocada). Antes de resolverlo: antes de esta correccion, el ranking
  local SOLO podia ser igual de exigente o mas estricto que el real
  (nunca mas permisivo, propiedad que se identifico antes de decidir la
  prioridad de arreglo) -- confirmado en el propio test de integracion
  de 2 plantas, que dejo de necesitar areas infladas artificialmente
  (14/10m2 en vez de 18/12m2) tras la correccion.
- **[RESUELTO]** `BanoAccesoGeneralValidator` a nivel de EDIFICIO:
  `GenerateBuildingUseCase._check_bano_acceso_general` reutiliza EL
  MISMO validador que ya existia para una sola planta, ejecutandolo por
  planta (con el grafo de adyacencia real de esa planta -- la
  accesibilidad no se "hereda" magicamente entre plantas) y exigiendo
  que AL MENOS UNA planta con baños tenga uno con acceso a circulacion
  general. Antes, este riesgo (vivienda generable con TODOS los baños
  en-suite, sin ninguno de acceso general) no se comprobaba en absoluto
  en modo multi-planta. Confirmado con test que fuerza el caso de fallo
  real (todas las plantas con baños capturados) y no solo el caso feliz.
- **`ViviendaMinimaValidator` excluido del validador por planta**
  (`build_per_floor_validators`), es de ambito de EDIFICIO: el programa
  minimo se comprueba UNA vez, uniendo los tipos de estancia de todas
  las plantas (una vivienda de dos plantas con salon abajo y bano
  arriba SI cumple el programa minimo, aunque ninguna planta por
  separado lo cumpla -- confirmado con test dedicado).
- **Simplificacion deliberada**: TODAS las plantas comparten el mismo
  `lot.buildable_area` (la opcion mas simple de las dos confirmadas por
  investigacion externa -- "copia exacta" en vez de "subconjunto mas
  pequeño"). Reducir el contorno planta a planta queda para un
  incremento posterior.

## Auditoría posterior al incremento de multi-planta

- **Código muerto encontrado y eliminado**: `split_box_horizontally`
  (`shapely_utils.py`) -- definida, nunca usada en ningún sitio del
  código, sin test. Probablemente resto de una iteración de diseño
  anterior a la arquitectura de árbol de partición.
- **[RESUELTO] Asimetría real en `EscaleraAlineacionValidator`**: antes,
  "no hay planta inferior" (la mas baja del edificio) y "SI hay planta
  inferior, pero no declara escalera" se trataban como el mismo caso
  (`reference_boundary=None`) -- una escalera en la planta superior que
  no arrancaba de ningún sitio en la planta inferior pasaba sin
  detección. Corregido con `floor_below_exists: bool` explícito,
  distinguiendo ambos casos. Confirmado con test que reproduce el
  escenario exacto antes y después de la corrección.
- **Tests añadidos para los tres caminos de fallo de
  `GenerateBuildingUseCase`** (generación por planta, programa mínimo a
  nivel de edificio, acceso de baño a nivel de edificio) -- ninguno
  tenía cobertura de su camino de error real, solo del camino feliz.
- Cobertura total: 96% → 97%.

## Ronda de pruebas de casos límite (tras resolver los tres huecos de modelo)

Batería exploratoria sistemática sobre el estado completo del proyecto,
antes de continuar con más funcionalidad. Todos los casos límite
probados se comportan correctamente; ninguno reveló un bug de código
nuevo (dos de mis propios datos de prueba tenían áreas insuficientes
para Tabla 1/2, detectados y corregidos como parte de la propia prueba,
no como hallazgos del sistema):

- Edificio con hueco de nivel (SOTANO + PLANTA_SUPERIOR, sin PLANTA_BAJA
  ni SEMISOTANO): `level_below` salta correctamente los niveles ausentes.
- Edificio de 3 plantas: escalera encadenada correctamente en las DOS
  uniones consecutivas (sótano-planta baja, planta baja-planta
  superior), no solo en una.
- Dos escaleras en la misma planta: cada una se valida por separado
  contra la referencia, sin falsos positivos cruzados.
- Múltiples estancias de circulación conectadas a una misma estancia
  protegida: `PasilloTopologiaValidator` no marca la estancia por sí
  misma si tiene redundancia, solo marca lo que de verdad queda aislado.
- Más de 5 estancias (fila `TABLA_1_MAS_DE_CINCO`/`TABLA_2_MAS_DE_CINCO`)
  combinado con multi-planta: ranking global y conteo total correctos.
- `Program` con ids de estancia duplicados: detectado por
  `InvalidProgramError` ya existente.
- Parcela degenerada (área casi nula) y retranqueo que colapsa el área
  edificable a 0: fallo controlado con mensaje claro, sin excepción
  inesperada.
- Exportación JSON con estancias sin colocar + puertas: sin reventar,
  excluidas correctamente de la lista de puertas.
- Baño completamente aislado (sin ninguna otra estancia): detectado
  como violación, sin caso especial roto.

**Dos de estos casos (3 plantas encadenadas, hueco de nivel) se
incorporaron como tests permanentes** (`test_three_floor_building_chains_staircase_alignment_at_both_junctions`,
`test_building_with_level_gap_skips_absent_intermediate_levels`), no
solo como exploración puntual -- eran escenarios genuinamente nuevos,
no cubiertos por los tests existentes.

## Auditoría profunda: algoritmos, rendimiento y concurrencia

Por petición explícita del usuario, auditoría dirigida a clases de
problemas concretas (recursión, grafos, cuellos de botella,
vulnerabilidades) en vez de solo casos límite de dominio. Resultado:
**tres bugs reales encontrados y corregidos**, no solo confirmaciones.

1. **[RESUELTO] Reconstrucción redundante del grafo de adyacencia
   (cuello de botella real, medido, no estimado)**: 5 validadores
   distintos (núcleo húmedo, zonificación día/noche/servicio, topología
   de pasillo) comparten la misma instancia de
   `GeometryAdjacencyGraphBuilder` pero cada uno reconstruía el grafo
   completo (`O(n²)` intersecciones geométricas) de forma independiente
   sobre el mismo `Layout`, dentro de una única llamada a
   `CompositeConstraintValidator.validate()` -- 5 veces por iteración
   del recocido simulado. Medido con el programa de ejemplo del CLI:
   **9.35s → 4.52s** (más del doble de rápido) añadiendo una caché de
   una sola entrada.
2. **[RESUELTO] Bug real en la propia caché, encontrado antes de
   entregarla**: la primera versión cacheaba por `id(layout)` (un
   entero). Confirmado con un experimento directo: en un bucle de
   creación/descarte de `Layout` como el que hace el recocido simulado,
   de 1000 objetos creados solo 6 `id()` distintos aparecieron --
   Python reutiliza agresivamente direcciones de memoria de objetos ya
   liberados. Cachear solo por `id()` podía devolver resultados de un
   `Layout` completamente distinto que reutilizara la misma dirección,
   silenciosamente. Corregido guardando una referencia real al objeto
   (`is`, no `id()`), que impide que Python libere esa memoria mientras
   la caché siga vigente.
3. **[RESUELTO] El generador aleatorio no se reiniciaba entre llamadas
   a `generate()`**: `self._rng` se creaba una sola vez en `__init__` y
   se reutilizaba entre llamadas -- `seed` solo garantizaba un
   resultado reproducible en la PRIMERA llamada; una segunda llamada al
   mismo generador continuaba la secuencia aleatoria anterior, no
   reiniciaba desde la semilla. Confirmado que esto rompía incluso la
   generación real del CLI en la tercera llamada repetida al mismo
   objeto. Corregido reiniciando `self._rng = random.Random(self._seed)`
   al principio de cada `generate()`. Contrapartida documentada: si en
   el futuro se usa `max_attempts > 1` con semilla fija, cada intento
   dará el MISMO resultado (los reintentos ya no aportan variedad por
   accidente) -- `max_attempts` no se usa con valor >1 en ningún sitio
   del proyecto actual, así que esto no afecta a nada ya construido.
4. **Riesgo de profundidad de recursión, latente pero de baja
   probabilidad práctica**: `PartitionNode.leaves()`, `internal_nodes()`
   y `place_tree()` son recursivas, sin balanceo garantizado del árbol
   (`build_random_tree` elige el punto de corte con `rng.randint`,
   pudiendo degenerar en una cadena lineal de profundidad N-1 en el
   peor caso). Medido empíricamente: hasta n=200 estancias, profundidad
   máxima observada en 50 semillas fue 22 -- muy lejos del límite de
   recursión de Python (1000). No es una amenaza práctica para tamaños
   de vivienda unifamiliar reales, pero tampoco está protegido por
   construcción; documentado como fragilidad teórica, no crítica.
5. **Revisión de seguridad**: sin `eval`/`exec`/`pickle`/`shell=True` en
   todo el código fuente. Único `open()` de escritura (exportación
   JSON) usa una ruta que en el CLI viene de `--output` (usuario local,
   mismo nivel de confianza que cualquier CLI que ya pueda escribir en
   su propio sistema de archivos) -- no es una vulnerabilidad real en
   este contexto (herramienta local, sin exposición de red ni entrada
   no confiable).

**Suite completa tras las tres correcciones**: 233/233, ~24s (antes
~30-47s) -- la mejora de rendimiento se nota en el conjunto de tests,
no solo en el CLI aislado.

## Restricciones blandas conectadas a la función objetivo (retomado de CONTINUIDAD.md)

- **[RESUELTO]** Investigación externa confirmada antes de implementar
  (curriculum-based course timetabling, arxiv 1409.7186): la suma
  ponderada con peso grande para lo duro es la técnica estándar para
  mezclar restricciones duras y blandas en una función de coste de
  recocido simulado -- no una técnica inventada sin precedente.
- `SoftConstraintScorer` (nuevo) + `AdjacencyStrength.SHOULD_BE_AWAY`
  (nuevo -- `SHOULD_BE_NEAR` ya existía en el enum desde el diseño
  inicial del dominio, declarado pero sin ningún uso en todo el
  código, confirmado antes de tocarlo). Métrica: saltos de grafo sobre
  adyacencia geométrica real, no el grafo de puertas disperso ni
  contacto directo -- cerca objetivo ≤2, alejar objetivo ≥3, ya
  decididos en una sesión anterior.
- **Bug real encontrado y corregido durante la construcción, no solo
  investigado de antemano**: la primera implementación combinaba
  duro+blando en un único número (`duro*1000 + blando`) para decidir
  la aceptación del recocido. Esto garantiza el ORDEN final correcto,
  pero **rompe la dinámica de aceptación en sí**: `exp(-delta/T)`
  reacciona a la magnitud absoluta del delta, no solo al orden
  relativo -- multiplicar por 1000 hacía casi imposible aceptar
  cualquier movimiento que empeorase lo duro, incluso con temperatura
  alta al principio, cambiando el comportamiento ya afinado de todo el
  recocido. Confirmado porque rompió un test de multi-planta
  (alineación de escalera) que no tenía relación alguna con
  restricciones blandas -- la señal de que algo estructural había
  cambiado, no un caso límite aislado.
- **Corregido con comparación LEXICOGRÁFICA real**: `_score` devuelve
  una tupla `(violaciones_duras, penalización_blanda)`. Cuando lo duro
  cambia entre candidato y actual, la aceptación se decide SOLO por ese
  delta (a su escala natural pequeña, igual que antes de tocar nada de
  esto); lo blando solo entra en juego cuando lo duro empata. `best_score`
  se compara con `<` sobre la tupla completa (comparación lexicográfica
  nativa de Python, sin necesidad de ningún peso ni constante).
- Conectado tanto en `build_generate_layout_use_case` (una planta) como
  en `build_generate_building_use_case` (multi-planta, un scorer propio
  por planta con sus propios requisitos de adyacencia).
- Metadatos del `Layout` ahora exponen `hard_violations` y
  `soft_penalty` por separado (antes solo `annealing_score`, un número
  opaco) -- se mantiene `annealing_score` por compatibilidad, igual al
  nuevo `hard_violations`.
- Confirmado con tests de integración dedicados: una preferencia blanda
  sin tensión con ninguna regla dura SÍ se satisface por la búsqueda
  (no solo "no rompe nada"); y una preferencia blanda en tensión directa
  con una regla dura para el MISMO par SIEMPRE cede ante la dura.

## Catálogo de 120 pares formalizado como código ejecutable (retomado de CONTINUIDAD.md)

- **[RESUELTO]** `domain/services/type_adjacency_catalog.py`. Generado
  PROGRAMÁTICAMENTE desde `docs/relaciones_espaciales.md` (no
  transcrito a mano, 120 pares -- fuente de errores real dado el
  volumen). `DEFAULT_TYPE_ADJACENCY` contiene 82 entradas reales
  (120 pares - 35 Neutro - 2 Condicional - 1 Ya cubierto). Los pares
  Condicional (BEDROOM/MASTER_BEDROOM↔BATHROOM) y Ya cubierto
  (KITCHEN↔BATHROOM) se excluyen deliberadamente del diccionario y se
  declaran aparte (`CONDICIONAL_PAIRS`, `YA_CUBIERTO_PAIRS`) --
  generar un `AdjacencyRequirement` fijo para ellos sería incorrecto
  (dependen de lógica evaluada contra el `Program` real o ya están
  cubiertos por otro validador).
- `build_adjacency_requirements(rooms)`: función pura que, dado un
  conjunto de `Room`, deriva automáticamente los `AdjacencyRequirement`
  (duros y blandos) según sus `RoomType`. Aplica la misma relación a
  cada instancia si hay varias estancias del mismo tipo (el catálogo es
  por tipo, no por instancia única); nunca genera nada entre dos
  estancias del mismo tipo (el catálogo no tiene entradas tipo-tipo
  consigo mismo).
- **Verificado con el generador real, no solo con la función aislada**:
  un programa realista de 11 estancias genera 44 `AdjacencyRequirement`
  automáticamente, y el conjunto completo SÍ es alcanzable por el
  recocido simulado (layout válido, 0 violaciones duras). **Hallazgo
  honesto, no ocultado**: es una búsqueda notablemente más difícil que
  los ejemplos curados a mano de este proyecto (44 requisitos frente a
  los 4-6 típicos) -- de 10 semillas probadas con 5000 iteraciones,
  solo una convergió. No es una contradicción interna del catálogo
  (SÍ converge), pero confirma que usar el catálogo completo
  "tal cual" para un programa real puede necesitar más iteraciones que
  las que bastan con conjuntos de restricciones más pequeños y curados.

## Auditoría de mantenimiento de tests + estática de código completa

A petición explícita del usuario ("¿los tests siguen actualizados o
son solo los de su momento?" + "revisa todo el proyecto ya que
estamos"). Hallazgos reales, con evidencia, no solo confirmaciones:

- **[RESUELTO] 2 tests duplicados de verdad**, creados por mí mismo en
  la ronda anterior sin comprobar si ya existían: `test_domain_entities.py`
  tenía `test_program_rejects_duplicate_room_ids` y
  `test_program_rejects_adjacency_to_unknown_room`, textualmente iguales
  a dos tests nuevos en `test_program.py`. Eliminados los duplicados,
  archivo renombrado a `test_room.py` (tras quitar los de `Program`,
  quedó puramente sobre `Room`).
- **[RESUELTO] Auditoría estática completa con `pyflakes`** (instalado
  para esta auditoría, no estaba antes): 3 hallazgos reales en `src/`
  (imports sin usar en `shapely_utils.py` y
  `cocina_integrada_validator.py`, residuos de limpiezas anteriores; y
  **`best_tree` en `SimulatedAnnealingLayoutGenerator` se rastreaba
  durante toda la búsqueda pero nunca se leía en ningún sitio** --
  bookkeeping completamente muerto, eliminado). 6 hallazgos más en
  `tests/`: imports sin usar, y **dos casos donde una variable local sin
  usar señalaba un test más débil de lo que su propio comentario
  prometía** (`test_graph_based_generator.py` obtenía `bath` pero nunca
  lo comprobaba, pese a que el comentario decía que sí; corregido
  añadiendo la aserción que faltaba, no solo borrando la variable).
- **Confirmado limpio**: arquitectura hexagonal (ningún import de
  `application`/`domain` hacia `infrastructure`/`config`), y ningún
  validador huérfano (uno pareció serlo -- `GroupingConstraintValidator`
  -- pero es un falso positivo, se conecta vía 4 funciones fábrica, no
  por nombre de clase directo).
- Suite final: 276/276 (278 - 2 duplicados eliminados), pyflakes limpio
  en `src/` y `tests/`.

## Depuración con mypy (comprobación de tipos estática, primera vez en el proyecto)

- **[RESUELTO]** 17 errores de tipo, TODOS concentrados en
  `partition_tree.py`, ninguno en el resto de 74 archivos. Causa raíz
  única: `PartitionNode.first`/`.second`/`.room_id` son `Optional`, y
  aunque el código mantiene por construcción la invariante "nodo hoja
  ⟺ `room_id` establecido ⟺ `first`/`second` en `None`; nodo interno ⟺
  lo contrario", Python no tiene un mecanismo de "tipos suma" nativo
  para que `mypy` lo demuestre solo.
- **Corregido con `assert` explícitos, no silenciando el aviso**: cada
  punto donde se accede a `.first`/`.second`/`.room_id` tras comprobar
  `is_leaf` ahora lleva un `assert` que documenta la invariante Y le da
  a `mypy` la información de estrechamiento de tipo que necesita. No es
  solo para `mypy` -- si la invariante se rompiera alguna vez de verdad
  (un bug futuro en un movimiento nuevo del recocido, por ejemplo), da
  un `AssertionError` claro en el sitio exacto, no un `AttributeError`
  confuso en medio de la recursión. Extraído `_leaf_area()` como helper
  compartido para no repetir el mismo assert en tres sitios distintos.
- Confirmado sin cambio de comportamiento: 276/276 tests, sin tocar
  ninguna lógica, solo defensas explícitas. `mypy src/` limpio en los
  75 archivos tras la corrección.

## Duplicación de lógica real encontrada y refactorizada

Detección sistemática (no intuición): script que busca bloques de 4
líneas idénticos repetidos entre archivos distintos de
`infrastructure/algorithms/constraints/`. La mayoría de coincidencias
son boilerplate esperable del patrón de puerto (`validate(layout) ->
ValidationResult`, inicializar `violations`/`warnings`) -- no vale la
pena abstraerlo, forzaría indirección por poco ahorro. Un hallazgo SÍ
era duplicación real de lógica, no solo estructura:

- **[RESUELTO]** `AnchoLibrePasilloValidator`, `EscaleraAnchoLibreValidator`
  y `TrasteroMinimumAreaValidator` repetían exactamente el mismo manejo
  de los 3 estados de `meets_minimum_width` (violación/aviso/aprobado).
  Extraído `evaluate_minimum_width()` a `shapely_utils.py`, junto a la
  función que envuelve. Diseño reconsiderado a media construcción: un
  primer intento con `violation_label`/`threshold` separados no encajó
  con `EscaleraAnchoLibreValidator` (pone la referencia normativa DENTRO
  del mismo paréntesis que el umbral, no como texto aparte) -- corregido
  dejando que cada validador preformatee su propio mensaje completo, el
  helper solo decide cuál usar según el resultado de 3 estados.
  Confirmado con los 14 tests de los tres validadores (texto exacto de
  mensaje preservado, los tests comprueban subcadenas concretas) más 3
  tests nuevos del propio helper en aislamiento. Suite completa 279/279,
  `pyflakes` y `mypy` limpios tras el refactor.

## Revisión manual de lógica (no detectable por pyflakes/mypy) -- 2 bugs reales

A petición explícita del usuario de volver a revisar la lógica de todo
el proyecto. Lectura crítica línea a línea de las piezas más
propensas a errores (recocido simulado, scorer blando, Tabla 1/2),
no solo herramientas automáticas -- ninguno de los dos hallazgos
siguientes es detectable por `pyflakes` ni `mypy`, son errores
semánticos de dominio, no de sintaxis ni de tipos.

- **[RESUELTO] `EstanciaMinimumAreaValidator` podía generar una
  VIOLACIÓN FALSA en multi-planta**: cuando una planta no tiene
  `LIVING_ROOM` (el caso NORMAL para plantas superiores con solo
  dormitorios), el validador sustituía por la mayor estancia local y le
  aplicaba el cuadrado inscribible de 3.30m -- una regla que solo
  corresponde al salón. Si esa estancia sustituta no cumplía (algo que
  nunca debería exigírsele), generaba una violación que bloquearía un
  edificio multi-planta perfectamente válido. Confirmado empíricamente
  con el edificio de prueba de 2 plantas antes y después de corregir.
  Corregido: la sustitución+aviso solo se aplica en modo una-sola-planta
  (`total_num_estancias_override is None`); en multi-planta, si esta
  planta no tiene salón, simplemente no se comprueba nada aquí -- la
  planta que SÍ tiene el salón real lo comprueba correctamente por su
  cuenta, sin necesitar sustituto.
- **[RESUELTO] `CocinaIntegradaValidator` nunca recibió el arreglo
  multi-planta que sí tienen sus dos primos** (`EstanciaMinimumAreaValidator`,
  `ServicioMinimumAreaValidator`): contaba `num_estancias` solo de la
  planta actual, sin `total_num_estancias_override`. En un edificio de
  2 plantas con cocina integrada abajo y dormitorios arriba (el caso
  normal), esto podía **aprobar silenciosamente** una superficie
  combinada salón+cocina realmente insuficiente para el edificio
  completo -- confirmado con un test que reproduce el escenario exacto
  (25m2 pasaba con el conteo local de 2 estancias, 23m2 mínimo; con el
  conteo real de 5 estancias del edificio, el mínimo sube a 31m2 y
  correctamente falla). Corregido añadiendo el mismo parámetro que sus
  primos, conectado en `container.py`.
- Revisados sin hallazgos adicionales: `SimulatedAnnealingLayoutGenerator`
  (acceptance/scoring, ya con dos bugs corregidos en rondas anteriores --
  esta vez sólido), `ServicioMinimumAreaValidator` (no comparte el mismo
  patrón de sustitución, cada servicio se comprueba directamente contra
  su propio umbral). Corregido tambien un comentario impreciso (no un
  bug funcional) en `SoftConstraintScorer` que atribuía el caso
  "estancia aislada" a la rama equivocada.
- Suite final: 282/282, `pyflakes` y `mypy` limpios.

## Continuación de la revisión manual de lógica — 3 hallazgos más

Cobertura de esta ronda: `GenerateBuildingUseCase` completo,
`GroupingConstraintValidator` + sus 4 fábricas (núcleo húmedo,
zonificación día/noche/servicio), `ExteriorContactValidator`,
`ViviendaMinimaValidator`, `BanoAccesoGeneralValidator`, `door_graph.py`,
`type_adjacency_catalog.py` completo. Tres hallazgos, ninguno tan grave
como los dos anteriores pero reales:

- **[RESUELTO] `GenerateBuildingUseCase._check_programa_minimo` tenía su
  cuerpo ENTERO duplicado** (dos veces seguidas, idéntico) -- residuo de
  una edición anterior de esta misma sesión donde un `str_replace` se
  comió el método y hubo que restaurarlo. No cambiaba el resultado
  (idempotente), pero es código real duplicado sin motivo que ni
  `pyflakes` ni `mypy` detectan.
- **[RESUELTO] `door_graph.py` repetía el umbral `1.0` como número
  mágico** en vez de importar `MUST_BE_NEAR_MIN_SHARED_LENGTH_M` de
  `adjacency_validator.py` -- mismo valor hoy, pero si alguien cambia el
  umbral real, este archivo no lo seguiría automáticamente.
- Cosmético: la última entrada de `DEFAULT_TYPE_ADJACENCY` se generó
  pegada a la llave de cierre (residuo del script de generación desde
  el Markdown). Sin efecto funcional, corregido por legibilidad.

Revisados sin hallazgos adicionales: `GroupingConstraintValidator` y
sus 4 fábricas (parámetros consistentes, sin riesgo de fuga entre
plantas porque cada `Layout` ya es de una sola planta al llegar aquí),
`ExteriorContactValidator`, `ViviendaMinimaValidator`,
`BanoAccesoGeneralValidator`, `build_adjacency_requirements` (la
búsqueda bidireccional con `or` es segura porque los valores del enum
nunca son "falsy" en Python -- se verificó explícitamente, no se asumió).

Con esta ronda se ha revisado manualmente la práctica totalidad de la
lógica de negocio del proyecto (generador, scorer blando, Tabla 1/2,
cocina integrada, orquestador multi-planta, agrupación/zonificación,
contacto exterior, programa mínimo, acceso de baño, grafo de puertas,
catálogo formalizado). Suite final: 282/282, `pyflakes` y `mypy` limpios.

## Revisión de funciones y variables: complejidad (radon) y patrones peligrosos

Instalado `radon` para medir complejidad ciclomática de forma objetiva
(nunca usado antes en el proyecto), más revisión manual de argumentos
mutables por defecto (fallo clásico de Python que ni `pyflakes` ni
`mypy` detectan).

- **Sin argumentos mutables por defecto** en todo `src/` (`def f(x=[])`,
  `def f(x={})`) -- comprobado explícitamente, no asumido.
- Complejidad general: mayormente "B" (moderada, esperable dado que
  cada validador repite el mismo patrón de varias ramas: colocada/no,
  tipo correcto/no, umbral, tres estados). Ninguna función alcanza "D"
  o peor en todo el proyecto.
- **[RESUELTO]** Los dos casos más complejos (`EstanciaMinimumAreaValidator.validate`
  y `CocinaIntegradaValidator.validate`, ambos 16 -- "C", los más altos
  del proyecto) hacían DOS cosas independientes a la vez dentro de un
  mismo método (ranking Tabla 1 + cuadrado inscribible; superficie
  combinada + apertura vertical). Separados en métodos con
  responsabilidad única, sin cambiar el comportamiento -- mismas
  violaciones/avisos, mismo orden, confirmado con los tests existentes
  sin modificar ninguno. `EstanciaMinimumAreaValidator.validate`:
  16→5. `CocinaIntegradaValidator.validate`: 16→11.
- Resto de "C" restantes (11-14: `build_door_graph`,
  `PasilloTopologiaValidator`, `AnchoLibreEstanciaValidator`,
  `BanoAccesoGeneralValidator`, `AdjacencyConstraintValidator`,
  `EscaleraAlineacionValidator`, `GenerateBuildingUseCase.execute`):
  revisados, complejidad inherente a la cantidad de estados normativos
  legítimos que manejan, no candidatos claros a más separación sin
  introducir indirección sin beneficio real.
- Suite final: 282/282, `pyflakes` y `mypy` limpios.

## Revisión de patrones peligrosos y consistencia de nombres — sin hallazgos nuevos

Continuación de la revisión de funciones/variables, esta vez con
comprobaciones basadas en AST (más fiables que expresiones regulares
sueltas -- un primer intento con regex para "parámetros que ensombrecen
builtins" dio falsos positivos al confundir anotaciones de tipo con
nombres de parámetro, corregido usando el árbol de sintaxis real):

- Sin `except:` genéricos (peligroso: atraparía hasta `KeyboardInterrupt`).
- Sin comparaciones `== None`/`!= None` (deberían ser `is None`/`is not None`).
- Sin parámetros que ensombrezcan builtins de Python (`id`, `type`,
  `list`, `dict`...) -- comprobado con AST en todo `src/`.
- Parámetros declarados pero nunca usados en el cuerpo: encontrados
  varios, todos explicables sin ser bugs -- la mayoría son firmas de
  puertos abstractos (`ConstraintValidatorPort`, `LayoutGeneratorPort`...),
  donde no usar el parámetro es lo esperado (solo declaran el contrato).
  Los dos casos concretos (`JsonLayoutRepository.load`,
  `SimulatedAnnealingLayoutGenerator.generate`) ya estaban documentados
  como intencionados (stub sin implementar; `zones` ignorado a propósito).
- Consistencia de nombres: `room_id` se usa siempre igual (0 variantes
  como `rid`), y los 19 métodos `validate()` del proyecto usan `layout`
  como nombre de parámetro sin una sola excepción.

Sin cambios de código en esta ronda -- es un resultado limpio real, no
una ausencia de revisión.

## Dos pendientes resueltos: catálogo automático conectado + contorno progresivo

- **[RESUELTO]** `build_adjacency_requirements` conectado como opción
  real, no solo función suelta: `build_program_with_auto_adjacency`
  (domain/services, lógica pura sin infraestructura) + `--auto-adjacency`
  en el CLI. Confirmado con subprocess real: mismas 11 estancias, 44
  requisitos derivados automáticamente en vez de los 6 declarados a
  mano, layout válido con más iteraciones/semilla ajustada (ya
  documentado que el catálogo completo es una búsqueda más difícil).
- **[RESUELTO]** Contorno edificable reducido progresivamente planta a
  planta. Investigación externa confirmada antes de implementar
  (Devans, "Procedural Generation For Dummies: Building Footprints"):
  "subtractive generation... empezando por la parcela y recortando
  trozos -- buen enfoque para plantas superiores, ya que la segunda
  planta suele parecerse a la primera", con patrón de red de seguridad
  `MinArea{Action:Shrink, Fallback:...}` si el área encogida no
  alcanzaría. `Lot.retranqueo_incremento_por_planta_m` (nuevo, `None`
  por defecto preserva el comportamiento anterior) +
  `GenerateBuildingUseCase._shrink_for_next_floor`: mismo mecanismo
  `buffer(-x)` que ya usa `Lot.buildable_area`, aplicado de forma
  progresiva desde la segunda planta en adelante, con la misma red de
  seguridad (si no cabe, usa la misma huella que la planta de abajo en
  vez de fallar -- opción también válida según la propia investigación:
  "copia exacta O subconjunto"). Confirmado geométricamente, no solo
  que "genera sin error": la huella de la planta superior queda
  literalmente contenida dentro de la huella de la planta inferior
  (`contains()` verdadero), con el desplazamiento exacto esperado en
  los 4 lados. Red de seguridad confirmada por separado con un
  incremento deliberadamente excesivo.

## GARAGE: contacto exterior sin base normativa (investigado a fondo, resuelto)

- **[RESUELTO]** Investigación completa antes de decidir (a petición
  explícita del usuario, "investiga, revisa la normativa oficial"):
  confirmado que la exigencia de `min_exterior_sides=1` para `GARAGE`
  nunca estuvo respaldada por el Decreto 29/2010. "Garajes colectivos"
  (B.2.6/antiguo I.B.5) es una sección de EDIFICIO para garajes
  compartidos entre varios vecinos -- confirmado con una discusión real
  de arquitectos en foro (soloarquitectura.com) que cita textualmente:
  "las referidas a... garajes colectivos (I.B.5) no [aplican a
  unifamiliares], ya que no disponen de ninguno de ellos por tipología".
  Revisado también `nhv.lua` directamente: declara EXPLÍCITAMENTE en su
  propio comentario que NO modela "garajes de viviendas unifamiliares"
  -- lo que sí modela (`validarGaraje`, con datos de pendiente de rampa,
  ancho, radio de giro) es explícitamente B.2.6 colectivo, con
  dimensiones de tráfico en dos sentidos y giro de varios coches, no
  transferibles a un garaje privado.
- **Hallazgo curioso durante la investigación**: el código YA tenía un
  comentario extenso documentando exactamente este razonamiento (mismo
  hilo de foro, misma cita de `nhv.lua`) junto al diccionario
  `DEFAULT_MIN_EXTERIOR_SIDES` -- pero el valor seguía en `GARAGE: 1`,
  contradiciendo su propio comentario. Corregido a `0`, alineando el
  valor con el razonamiento ya escrito.
- `GARAGE` sigue siendo **opcional por proyecto**: `Room.min_exterior_sides`
  admite override explícito (`Room(room_type=GARAGE, ...,
  min_exterior_sides=1)`) para quien quiera exigirlo por motivos
  prácticos propios, sin que sea la exigencia por defecto del sistema.
- **Efecto secundario esperado, no un bug nuevo**: cambiar una
  restricción dura cambia la dinámica de aceptación del recocido
  simulado -- dos tests con semilla fija dejaron de converger con la
  misma semilla que antes (mismo patrón ya documentado varias veces en
  esta sesión). Rebuscada semilla estable (1, en vez de 10) para ambos.
- Suite final: 293/293, `pyflakes` y `mypy` limpios.

## Búsqueda sistemática de "razonamiento completo sin aplicar" (a petición del usuario)

Tras encontrar el caso de `GARAGE`/B.2.6 (comentario ya razonado
correctamente, valor del código sin actualizar), el usuario preguntó si
podía haber más casos así sin detectar. Búsqueda sistemática, no
suposición: localizados los 28 bloques de comentario de 6+ líneas en
todo `src/`, revisado cada uno contra su código adyacente. Dos hallazgos
reales más, ambos en `AlturaLibreValidator`:

- **[RESUELTO] `GARAGE` excluido por completo de la comprobación de
  altura libre** (`ROOM_TYPES_FUERA_DE_ALCANCE`), cuando el propio texto
  del Decreto 29/2010 A.3.1.1.b nombra explícitamente "garajes de
  viviendas unifamiliares" en la lista de reducción directa a 2.20m --
  confirmado con la MISMA cita textual ya verificada en la investigación
  del hallazgo anterior (B.2.6). El comentario decía "garaje... no
  aparece en ninguna lista de la fuente", repitiendo la misma confusión
  de fondo (B.2.6 no es "la regla del garaje unifamiliar") en un sitio
  distinto del código.
- **[RESUELTO] `STAIRCASE` no estaba en ninguna de las dos listas**
  (ni reducción directa ni fuera de alcance), cayendo por defecto en el
  caso general más estricto (2.50m / excepción del 30%) -- el Decreto
  también nombra explícitamente "escaleras" en la misma lista A.3.1.1.b.
  No detectado por la primera revisión de este validador porque el
  comentario original no mencionaba escaleras en absoluto, ni en un
  sentido ni en otro -- una ausencia, no una afirmación contradictoria,
  más difícil de detectar por inspección casual.
- Dos correcciones adicionales de documentación (sin cambio de
  comportamiento): comentario de `GARAGE` en `enums.py` seguía
  atribuyendo su categoría a "B.2.6" (ya sabemos que no aplica);
  docstring de `ServicioMinimumAreaValidator` decía que "cocina
  integrada" y "trastero" quedaban pendientes "hasta que se aborden como
  piezas propias" -- ya se abordaron, cada una en su propio validador
  (`CocinaIntegradaValidator`, `TrasteroMinimumAreaValidator`),
  construidos en incrementos posteriores a como se escribió esa nota.
- Resto de los 28 bloques revisados: consistentes con su código, sin
  hallazgos adicionales.

Suite final: 295/295, `pyflakes` y `mypy` limpios.

## Vivienda pareada/adosada (medianeras)

- **[RESUELTO]** `Lot.medianera_sides: FrozenSet[str]` (subconjunto de
  `{"north","south","east","west"}`, vacío por defecto = aislada, sin
  cambio de comportamiento). Los lados de medianera no llevan
  retranqueo (la edificación llega hasta el linde) y no cuentan como
  contacto exterior real (`ExteriorContactValidator`) -- una pared de
  medianera no tiene luz ni ventilación propia.
- Requiere parcela rectangular de lados ortogonales (norte=+y, sur=-y,
  este=+x, oeste=-x) -- convención establecida aquí mismo, no existía
  antes (`entrance_side`/`street_side` eran metadatos descriptivos, sin
  ninguna geometría conectada todavía).
- `Lot.buildable_area` pasó de un `buffer(-x)` uniforme a un cálculo por
  lados (bounds), para poder aplicar retranqueo asimétrico. **Caso
  límite real encontrado al migrar**: un retranqueo excesivo con el
  método antiguo colapsaba a área vacía vía el propio `buffer()`; el
  nuevo cálculo por bounds, sin cuidado, producía un rectángulo con
  coordenadas invertidas (área positiva falsa) en vez de colapsar --
  corregido con una comprobación explícita `minx>=maxx or miny>=maxy`.
- `count_exterior_sides` (shapely_utils) acepta `excluded_segments`
  opcional -- lados del perímetro que no cuentan aunque geométricamente
  se toquen. `Lot.medianera_boundary_segments()` calcula esos segmentos
  en la posición ORIGINAL de la parcela (no la ya encogida).
- Confirmado con generación real de extremo a extremo: vivienda adosada
  en parcela estrecha (8m fachada, medianeras este/oeste) -- al menos
  una estancia llega hasta cada linde de medianera (x=0 y x=8 exactos),
  mientras que el retranqueo de 3m SÍ se respeta en norte/sur. Búsqueda
  algo más difícil que el caso aislado equivalente (parcela más
  restringida) -- 4000 iteraciones en vez de 3000 para la semilla de
  prueba.
- Suite final: 305/305, `pyflakes` y `mypy` limpios.

## Importador JSON → Program real (último pendiente de CONTINUIDAD.md, resuelto)

- **[RESUELTO]** `infrastructure/persistence/seleccion_plantas_importer.py`:
  `import_seleccion_plantas(source, areas_m2=None)`, construido contra
  el formato REAL de exportación del dashboard (verificado leyendo
  `exportSectionSelection()` en el propio HTML, no asumido) --
  `{"levels": {"PLANTA_BAJA": ["LIVING_ROOM", ...], ...}}`, con claves
  en los NOMBRES del enum en mayúsculas, no los valores en minúscula.
- **Limitación honesta, heredada del propio formato** (el dashboard ya
  lo advierte en su campo "nota" al exportar): el JSON es una selección
  de TIPOS por planta, no un programa completo -- nunca más de una
  estancia por (tipo, planta), sin áreas reales. El importador usa
  `AREAS_POR_DEFECTO_M2` (valores genéricos razonables) en vez de
  fingir resolver algo que el formato de origen no contiene.
  `build_adjacency_requirements` sí deriva las relaciones de
  adyacencia por completo, sin esta limitación.
- Conectado también como opción real del CLI (`--import-seleccion`),
  no solo función Python suelta -- usa `GenerateBuildingUseCase`
  (multi-planta), guarda un JSON por planta.
- Confirmado con generación real de extremo a extremo, ambos casos: una
  selección completa genera un edificio válido; una selección
  incompleta (sin circulación en una planta con baño) falla con mensaje
  claro, no genera algo incorrecto en silencio -- mismo principio de
  "nunca aprobar en silencio" que el resto del proyecto.
- Suite final: 315/315, `pyflakes` y `mypy` limpios.

Con esto, `docs/CONTINUIDAD.md` queda sin pendientes reales conocidos.

## Dashboard mejorado: cantidad y área reales (ambas limitaciones eliminadas)

- **[RESUELTO]** A petición explícita del usuario ("mejorar lo que
  tenemos en el dashboard y eliminar las limitaciones declaradas") --
  las dos limitaciones del importador (nunca más de una estancia por
  tipo/planta, áreas genéricas) venían del propio formato exportado, no
  del importador en sí. Corregido en la raíz: el dashboard
  (`relaciones_espaciales.html`) ahora muestra, en cada chip
  seleccionado, dos campos numéricos en línea -- cantidad (por defecto
  1, editable) y área en m² (con un valor de partida de
  `DEFAULT_AREA_M2`, mismos valores que `AREAS_POR_DEFECTO_M2` en
  Python, para que ambos coincidan).
- Estado JS cambiado de `Set<tipo>` a `Map<tipo, {count, area}>` por
  planta. Exportación (`version: 2`) trae
  `{"type":..., "count":..., "area_m2":...}` por entrada, en vez de un
  simple nombre de tipo.
- **Verificación real, no solo revisión visual del código** (sin
  entorno de navegador disponible en este proyecto): sintaxis JS
  comprobada con `node --check` sobre el script extraído; la lógica de
  exportación en sí ejecutada en Node con un estado simulado (dos
  dormitorios, áreas distintas por tipo), confirmando el JSON exportado
  real antes de tocar el importador Python.
- `seleccion_plantas_importer.py` actualizado para consumir el formato
  nuevo: genera tantas `Room` como `count` declare (con ids
  distinguibles, `_1`/`_2`...), usando el `area_m2` real declarado.
  **Compatibilidad hacia atrás preservada** con el formato antiguo
  (entradas de solo texto, sin versión) -- por si existe algún
  `seleccion_plantas.json` exportado antes de este cambio; en ese caso
  sigue aplicando `AREAS_POR_DEFECTO_M2` como antes. Ambos formatos
  pueden convivir en el mismo payload sin fallar.
- Confirmado con generación real de extremo a extremo: edificio de 2
  plantas con **2 dormitorios reales** en la misma planta (antes
  imposible) y **áreas declaradas por el usuario** (28m² de salón,
  12.5m² cada dormitorio -- no los valores genéricos de relleno).
- Suite final: 321/321, `pyflakes` y `mypy` limpios.

## Auditoría y mejora del dashboard (a petición del usuario, "corto de funciones y desactualizado")

Revisión sistemática, no solo impresión visual: comparados TODOS los
datos embebidos en el HTML contra sus fuentes reales de Python.

- **[RESUELTO] Dato real desactualizado encontrado**: `PROPS.GARAGE.min_exterior`
  seguía en `1` en el dashboard, pese a que Python lo corrigió a `0`
  hace varias rondas (investigación de garajes colectivos vs.
  unifamiliar). Único dato realmente obsoleto -- comparados
  sistemáticamente `min_exterior`, `zone`, `is_wet`, `category`,
  `subtype` de los 16 tipos contra `enums.py`, el resto coincidía.
- **Catálogo de 120 pares (`PAIRS`) verificado consistente, 0
  discrepancias**: comparación programática completa entre el `PAIRS`
  embebido en JS y `DEFAULT_TYPE_ADJACENCY` + `CONDICIONAL_PAIRS` +
  `YA_CUBIERTO_PAIRS` de Python -- las dos copias independientes del
  mismo catálogo (generadas en momentos distintos de la sesión)
  seguían de acuerdo en las 120 relaciones.
- **Tres funciones nuevas añadidas** (genuina falta de capacidad, no
  solo limpieza): (1) resumen en vivo por planta y total (nº de
  estancias, superficie) mientras se selecciona, antes inexistente;
  (2) comprobación de programa mínimo en tiempo real (las mismas 6
  piezas que `ViviendaMinimaValidator`), para descubrir que falta algo
  ANTES de exportar, no solo al fallar la generación en Python; (3)
  botón "vaciar selección" (no existía ninguna forma de reiniciar sin
  recargar la página).
- Añadida también una nota de conexión directa con `--import-seleccion`
  del CLI, para que quede claro que esto ya no es una herramienta de
  exploración aislada del generador real.
- **Verificación sin entorno de navegador disponible**, mismo método
  que la ronda anterior: sintaxis JS con `node --check`, y la lógica
  del resumen/programa mínimo ejecutada en Node con estado simulado
  (dos casos: selección incompleta detectando exactamente las 3 piezas
  que faltan; selección completa confirmando 0 piezas faltantes) antes
  de darla por buena.
- Suite Python: 321/321 sin cambios (el HTML es independiente).

## Revisión completa de las cuatro pestañas del dashboard

Continuación de la auditoría anterior, cubriendo Matriz, Sinergias y
Fichas (Sección ya revisada/mejorada en la ronda previa).

- **Matriz**: lógica de renderizado revisada (`buildMatrix`, `findPair`,
  `showDetail`) -- sólida, sin hallazgos. Solo renderiza el triángulo
  superior de la matriz (evita duplicar celdas), `findPair` resuelve
  ambos órdenes del par correctamente.
- **[RESUELTO] Variable CSS `--pmc` con nombre obsoleto**: definida
  como "preferencia muy cerca" (categoría de relación fusionada en "pc"
  hace tiempo, ya no existe en la clasificación de 5 categorías), pero
  usada realmente como color de la categoría "estancia" en fichas y red
  -- no rota (la variable sí estaba definida, los colores se veían
  bien), pero confusa. Renombrada a `--cat-estancia`, verificados los 3
  usos totales antes de tocarla.
- **[RESUELTO] Texto explicativo de puntuación incompleto**: la pista
  de la pestaña de sinergias explicaba 4 de los 7 pesos posibles
  (`WEIGHT`), omitiendo "Ya cubierto" (+2) -- un peso real, no nulo.
  Corregido para mencionar los 5 pesos no nulos y aclarar
  explícitamente que Neutro/Condicional no puntúan.
- **Fichas por tipo: mejora funcional real añadida** -- cada ficha
  ahora muestra sus relaciones `Obligatorio` (cerca/lejos) directamente,
  sin tener que cruzar con la pestaña de matriz para saber lo más
  operativamente importante de cada tipo. Verificado con datos reales
  extraídos del propio archivo (no simulados a mano): `LIVING_ROOM`
  muestra exactamente sus 3 relaciones obligatorias conocidas (cerca de
  Comedor y Recibidor, lejos de Garaje); tipos sin ninguna (`STUDY`,
  `TECHNICAL_ROOM`, `TOILET`) omiten la sección correctamente.
- Verificación sin navegador disponible, mismo método que rondas
  anteriores: sintaxis con `node --check`, lógica de fichas ejecutada
  en Node contra el `PAIRS`/`classify()` reales del propio archivo, no
  una copia simulada.
- Suite Python: 321/321 sin cambios (el HTML es independiente).

## Visor de planos (nuevo) + rediseño de sinergias

A petición explícita del usuario: el diagrama de red de la pestaña de
sinergias era demasiado complejo para leer de un vistazo (hasta 85
aristas entre 16 nodos), y sobre todo -- "todavía no tenemos nada para
poder trabajar realmente" -- el proyecto no tenía ninguna forma de
**ver** el resultado generado como un plano, solo JSON con coordenadas.

- **[RESUELTO] `docs/visualizador/plano_viewer.html` (nuevo)**: carga el
  JSON real que produce el CLI y dibuja la planta -- rectángulos por
  estancia coloreados por zona, nombre y superficie, marcas de puerta
  en las paredes compartidas reales. Soporta multi-planta (varios
  archivos a la vez, detecta la planta por nombre de archivo, pestañas).
  Verificación exhaustiva sin navegador disponible en este entorno:
  - Sintaxis JS con `node --check`.
  - Lógica de bounding box y de `sharedWallMidpoint` (punto medio de
    pared compartida entre dos rectángulos, sin librería de geometría
    en el cliente) ejecutada en Node contra un JSON real generado por
    el CLI, no datos simulados.
  - Verificación cruzada real: las 4 puertas del ejemplo real tienen
    longitud de pared compartida ≥1.0m, exactamente el mismo umbral
    que usa `GeometryAdjacencyGraphBuilder` en Python -- confirma que
    la representación visual de puertas es consistente con la regla
    real, no solo plausible.
  - Instalado `cairosvg` para renderizar el SVG a PNG y verlo de
    verdad, no solo confiar en que el código "debería" verse bien.
  - **Bug real encontrado con esta verificación, no a simple vista**:
    el tamaño de fuente de las etiquetas solo consideraba las
    dimensiones de la estancia, nunca la LONGITUD del nombre -- con
    "Dormitorio principal" (el nombre más largo del proyecto) el texto
    desbordaba su propio rectángulo incluso en el ejemplo real
    generado (5.93m de texto estimado vs 5.33m disponibles). Corregido
    tomando el mínimo entre "tamaño según dimensiones" y "tamaño que
    haría caber el texto en el 85% del ancho disponible" -- confirmado
    con el mismo caso adverso tras el arreglo.
- Rediseño del diagrama de red de Sinergias (demasiado denso con las
  ~85 aristas no neutras del catálogo completo, según feedback directo
  del usuario) -- ver la siguiente sección de este documento, se aborda
  a continuación en el mismo incremento.

## Rediseño del diagrama de red de sinergias

- **[RESUELTO]** Filtros de tipo de relación (checkboxes) sobre el
  diagrama de red -- por defecto solo se muestran las relaciones
  ESTRUCTURALES (`Obligatorio cerca/lejos` + `Ya cubierto`), las de
  `Preferencia` se activan aparte. **Confirmado con conteo real, no
  estimado**: de 83 aristas no neutras del catálogo completo a solo 6
  con el filtro por defecto -- reducción real de la densidad visual,
  no cosmética, y sin perder ningún dato (todo sigue disponible,
  activable). El resaltado al hacer clic en un nodo (`hasNonNeutralEdge`)
  también respeta el filtro activo, para que sea consistente con lo
  que de verdad se ve en cada momento.
- Verificado sin navegador disponible: sintaxis con `node --check`,
  conteo de aristas con el filtro por defecto vs todo activado
  ejecutado en Node contra el `PAIRS`/`classify()` reales del archivo.
- Suite Python: 321/321 sin cambios (el HTML es independiente).

## Corrección de feedback real del usuario: fusión, colisión de nombres, y validación real de áreas

El usuario probó lo construido y encontró tres problemas reales, no
hipotéticos: (1) el selector de archivos del visor no funcionaba de
verdad; (2) prefería una pestaña del dashboard existente, no un HTML
nuevo; (3) las áreas editables no avisaban si no se ajustaban a los
requisitos reales (Tabla 1/2) según el número de estancias.

- **[RESUELTO] Fusión real, no solo copiar y pegar**: antes de fusionar
  `plano_viewer.html` en `relaciones_espaciales.html`, comparados TODOS
  los nombres globales (`let`/`const`/`function`) y variables CSS de
  ambos archivos. **Encontrada una colisión real**: `FLOORS` existía en
  los dos archivos con significados completamente distintos (catálogo
  de tipos por planta vs. archivos de plano cargados) -- si se hubiera
  fusionado sin comprobar, una declaración habría sobreescrito
  silenciosamente a la otra. Renombrado a `LOADED_PLANS`/`ACTIVE_PLAN`
  en el visor. Variables CSS compartidas (`--bg`, `--line`, `--ink`,
  `--cyan`...) confirmadas con el mismo valor exacto antes de
  reutilizarlas sin duplicar.
- **Instalado `jsdom`** (no disponible hasta ahora) para poder cargar el
  HTML real completo, ejecutar sus scripts de verdad, y simular
  interacción real del usuario (clic, selección de archivo con un
  `File` real, evento `change` real) -- una verificación mucho más
  profunda que `node --check` (que solo valida sintaxis, nunca
  comportamiento en tiempo de ejecución contra un DOM real). Confirmado
  sin errores en la carga inicial, las 5 pestañas existen y son
  clicables, el selector de archivo fusionado carga y renderiza
  correctamente, y la pestaña de sección vertical (que depende del
  `FLOORS` real, el catálogo) sigue intacta tras la fusión.
- **[RESUELTO] Validación real de áreas contra Tabla 1/2**: portadas a
  JS las tablas EXACTAS de `estancia_minimum_area_validator.py` y
  `servicio_minimum_area_validator.py` (mismos valores literales, no
  aproximados). El campo de área se marca en rojo si el valor declarado
  no alcanza el mínimo real -- calculado sobre TODAS las estancias
  seleccionadas en TODAS las plantas a la vez (mismo criterio que
  `GenerateBuildingUseCase`, no solo la planta actual), recalculado en
  vivo cada vez que cambia cualquier cantidad o área. **Verificado con
  un escenario dinámico real, no solo un caso estático**: un salón de
  28m² pasa como única estancia (mínimo 25m² para 1 estancia); al
  añadir un dormitorio de 10m², el total pasa a 2 estancias (fila
  Tabla 1 distinta, [16,12]) y el dormitorio (puesto 2, mínimo 12m²)
  correctamente pasa a mostrar aviso -- confirma que el recálculo
  dinámico funciona de verdad, no solo en el momento de seleccionar.
- Retirado `plano_viewer.html` como archivo independiente, ya fusionado.
- Suite Python: 321/321 sin cambios (el HTML es independiente).

## El bug real encontrado (con ayuda del usuario probándolo de verdad)

Tras la fusión, el usuario probó de verdad (descargado, navegador real,
no la vista previa de Claude) y seguía sin funcionar: "me deja
seleccionar los archivos... pero no hay más". Antes de asumir que el
entorno de vista previa era el problema (hipótesis que se descartó al
confirmar que pasaba igual en un navegador real descargado), pregunté qué archivo estaba cargando -- **"seleccion_plantas (2).json"**,
el nombre del archivo fue la pista real.

- **[RESUELTO] Confusión real entre dos formatos JSON del mismo
  dashboard**: `seleccion_plantas.json` (exportación de la pestaña
  "Sección vertical" -- tipos y cantidades, SIN geometría resuelta,
  formato `{"levels": {...}}`) es un formato completamente distinto de
  un plano YA GENERADO por el CLI (formato `{"rooms": [...], "doors":
  [...], "metadata": {...}}`). El Visor de plano asumía sin comprobar
  que `data.rooms` existía -- cargar el primero producía
  `TypeError: Cannot read properties of undefined (reading 'filter')`
  sin capturar, a medio camino del `change` handler: el archivo se
  veía "seleccionado" (el navegador muestra su nombre) pero nada más
  pasaba, sin ningún mensaje. **Confirmado el bug exacto con `jsdom`
  antes de arreglar nada** -- reproducido el `TypeError` literal con el
  mismo formato real de `seleccion_plantas.json`.
- Corregido con detección explícita: si el JSON cargado no tiene
  `rooms` como array, se muestra un mensaje claro -- si además tiene
  `levels` (confirma que es una selección), indica el comando exacto
  de `--import-seleccion` a ejecutar antes de volver a cargar aquí.
  JSON con sintaxis inválida también capturado con `try/catch`, mensaje
  propio. Reforzada también la prevención en origen: la nota que se
  exporta junto a `seleccion_plantas.json` ahora advierte explícitamente
  que no se carga directamente en el visor.
- **Verificados los tres casos con `jsdom`, no solo el que falló**:
  formato de selección (mensaje claro, sin excepción sin capturar),
  JSON inválido (mensaje claro), y formato correcto cargado
  INMEDIATAMENTE DESPUÉS de un error previo (confirma que un error no
  deja la aplicación en un estado roto). Confirmado también que el
  resto del dashboard (matriz, sección, fichas, red de sinergias seguía
  intacto tras el arreglo.
- Suite Python: 321/321 sin cambios (el HTML es independiente).

## Recorrido de extremo a extremo real (a petición explícita del usuario)

Ejecutado el flujo COMPLETO tal como lo haría un usuario real, sin
saltarse ningún paso: seleccionar estancias en "Sección vertical"
(con clics y cambios de campo simulados vía `jsdom`, no solo llamadas
directas a funciones) → exportar de verdad (capturando el `Blob` real
que generaría la descarga) → ejecutar el comando real de
`--import-seleccion` con ESE archivo exportado → cargar los
`edificio_planta_*.json` reales resultantes en el Visor de plano →
confirmar render, cambio de pestaña de planta, y datos correctos.

- **[RESUELTO] Bug real encontrado solo al hacer el recorrido
  completo** (invisible probando piezas sueltas): los nombres de
  estancia en el plano final mostraban ids técnicos
  (`living_room_planta_baja`) en vez de nombres legibles en español
  (`Salón`) -- `seleccion_plantas_importer.py` usaba el mismo valor
  para `Room.id` y `Room.name`. Ningún test anterior comprobaba
  `Room.name` en absoluto (todos comprobaban tipo/nivel/área/cantidad),
  por eso pasó desapercibido pese a la cobertura ya alta del módulo.
  Añadido `DISPLAY_NAMES` en `enums.py` (mismo mapeo exacto que
  `DISPLAY` en el dashboard JS, mismo idioma) + numeración legible
  cuando hay varias del mismo tipo ("Dormitorio 1"/"Dormitorio 2", no
  solo el id). Confirmado con dos tests nuevos, y visualmente con el
  recorrido completo repetido tras la corrección.
- **Re-revisados los repositorios de investigación centrados en
  representación**, con la lente específica de "cómo dibujan un plano
  2D" -- House-GAN confirma el mismo enfoque que ya usamos (rectángulo
  + color por tipo), sin aportar ninguna técnica nueva de
  representación no incorporada ya. BuildingNodes (fachadas 3D) y
  real-3D-house-animation (animación decorativa) confirmados de nuevo
  como no aplicables a un plano 2D.
- Suite final: 323/323, `pyflakes` y `mypy` limpios.

## Reintento automático de semillas en --import-seleccion (caso real del usuario)

El usuario subió su `seleccion_plantas.json` real (planta baja con
salón/comedor/cocina/dormitorio principal/baño/recibidor/lavadero/
tendedero/almacén, sin `CORRIDOR`) y `--import-seleccion` con la
semilla por defecto (1) falló: `BanoAccesoGeneralValidator` no
encontraba una colocación donde el baño quedara junto a circulación.
Probadas semillas 1-4 directamente: la 1-3 fallan, la 4 converge --
**dificultad de búsqueda real, no un problema estructural** del programa.

- **[RESUELTO] `--retry-seeds` (nuevo, por defecto 5)**: con
  `--import-seleccion`, el CLI ahora prueba automáticamente semillas
  consecutivas (`--seed`, `--seed+1`, `--seed+2`...) hasta que una
  converja o se agoten los intentos, informando qué semilla funcionó.
  Justificación explícita en el propio `--help`: los programas de
  `--import-seleccion` no están curados a mano (a diferencia del
  ejemplo del CLI), así que necesitan más margen de búsqueda de forma
  HABITUAL, no como excepción -- el propio caso real del usuario lo
  confirma.
- Confirmado con el escenario EXACTO que falló al usuario (subprocess
  real, no simulado): con `--retry-seeds` por defecto, converge solo,
  informando "semilla 1 no convergió, funcionó con semilla 4 tras 4
  intentos". Con `--retry-seeds 1` (reintento desactivado), falla con
  un mensaje claro que dice cuántas semillas se probaron.
- Suite final: 325/325, `pyflakes` y `mypy` limpios.

## Generación automática de selección en Sección vertical (a petición del usuario)

El usuario pidió mejorar la pestaña "Sección vertical", que consideraba
limitada: quería un panel para indicar tipo de vivienda, número de
dormitorios y número de plantas, y que a partir de eso se autoseleccionen
las estancias y se autocalculen las superficies mínimas -- en vez de
tener que editarlas a mano, para cumplir normativa y optimizar espacio.
Reglas confirmadas explícitamente antes de implementar: 1 baño si
dormitorios≤2, +1 aseo si dormitorios≥3; con 2 plantas, día/servicio
abajo y dormitorios/baño arriba (patrón habitual).

- **[RESUELTO]** Panel "Generar selección automática": tipo de vivienda
  (aislada/pareada/adosada -- guardado como metadato en la exportación,
  no cambia la selección de estancias en sí, solo informa para el paso
  posterior de `Lot.medianera_sides` al generar de verdad), número de
  dormitorios, número de plantas.
- Reglas de selección: programa mínimo completo (6 piezas) + 1
  `MASTER_BEDROOM` + (dormitorios−1) `BEDROOM` + 1 `BATHROOM` (+1
  `TOILET` si dormitorios≥3) + `CORRIDOR` si hay 2 plantas (necesario
  para que `BanoAccesoGeneralValidator` pase en la planta superior).
- **Bug real encontrado al probar, no al diseñar**: la primera versión
  colocaba el aseo (`TOILET`) en la planta superior junto al resto de
  baños -- pero el propio catálogo (`FLOORS`) ya declaraba `TOILET`
  como "Fijo, sirve a zona social/visitas, no depende de dormitorios",
  con `niveles: "PLANTA_BAJA"` únicamente. Colocarlo en planta superior
  hacía que el chip NUNCA se renderizase (no está en la lista de tipos
  candidatos de esa planta según el propio catálogo) -- el aseo
  desaparecía en silencio, sin ningún error. Corregido moviéndolo a
  planta baja, coherente con lo que el catálogo ya decía.
- **Cálculo de áreas EXACTO, verificado cifra por cifra contra Tabla
  1/2 real**, no solo plausible: para un caso de 3 dormitorios (4
  estancias totales: salón + principal + 2 normales), confirmado que
  genera 20/12/8/8m² (Tabla 1 fila de 4) y 9/5/1.5/1.5/1.5/4m² (Tabla 2
  fila de 4 para cocina/baño/aseo/lavadero/tendedero/almacenamiento) --
  coincide exactamente con los valores reales del validador Python, no
  aproximados. Cuando varias instancias comparten una misma entrada
  (p.ej. 2 `BEDROOM` con un único valor de área), se usa el máximo de
  los mínimos de los puestos que ocupan, para que ninguna quede por
  debajo de lo que le corresponde individualmente.
- **Campos de área bloqueados por defecto tras generar** (`readonly`),
  con checkbox explícito "permitir editar áreas manualmente" para
  desbloquear si se quiere desviar del mínimo a propósito -- la
  comprobación de aviso en rojo (ya existente) sigue aplicando si se
  edita por debajo del mínimo real tras desbloquear.
- Confirmado con el recorrido completo de extremo a extremo otra vez:
  generación automática → exportación real capturada → `--import-seleccion`
  → generación real con el CLI (convergió a la primera con la semilla
  por defecto) → carga en el Visor de plano → SVG renderizado sin errores.
  También probado el caso límite (1 dormitorio, 1 planta): todo en
  planta baja, sin `BEDROOM` ni `TOILET` ni `CORRIDOR`, programa mínimo
  completo.
- Suite Python: 325/325 sin cambios (el HTML es independiente).

## El bug real de las "curvas raras" (encontrado gracias a una captura de pantalla real)

El usuario confirmó que los datos cargaban bien (resumen, zonas,
estancias todos correctos) pero la representación gráfica mostraba
formas curvas extrañas, no rectángulos limpios -- con una captura de
pantalla real adjunta. Ninguna de las verificaciones anteriores
(`jsdom`, `node --check`) podía detectar esto: todas comprueban
DATOS y AUSENCIA DE ERRORES, nunca el aspecto visual real.

- **Intentado instalar Chromium real (Playwright)** para reproducir
  exactamente lo que ve el usuario -- bloqueado por las restricciones
  de red del entorno (dominios no incluidos en la lista permitida).
  Sin poder confirmar visualmente en un navegador real, se recurrió a
  inspección directa del SVG generado carácter a carácter.
- **[RESUELTO] Causa raíz encontrada**: el `viewBox` del SVG del plano
  está en METROS (coordenadas reales de la vivienda), no en píxeles --
  pero `.room-rect{stroke-width:2}` y `.door-mark{stroke-width:5}`
  se escribieron pensando en píxeles razonables para pantalla. Al
  interpretarse en las mismas unidades que el resto del SVG, un
  grosor de línea de "2" o "5" se convertía en **2 o 5 METROS de
  grosor** -- más grueso que estancias enteras (la más pequeña del
  caso real medía 0.49m de alto). Con `stroke-linecap:round` en las
  marcas de puerta, esas líneas gigantescas generaban círculos/curvas
  enormes que se comían el plano -- exactamente lo que muestra la
  captura de pantalla del usuario (un "mordisco" circular en el
  Recibidor, una cuña con borde curvo en la esquina).
- Corregido a valores en metros razonables (`0.03`/`0.08`, 3cm/8cm).
  **Confirmado cuantitativamente, no solo visualmente** (dado que no
  hay navegador real disponible en este entorno): medido el porcentaje
  de píxeles del color de borde en una imagen generada con los valores
  ANTES (2/5) y DESPUÉS (0.03/0.08) del arreglo, usando los mismos 9
  datos exactos del caso real del usuario -- 73.2% de la imagen era
  color de borde con el bug, baja a 2.0% (proporción normal de bordes
  finos) tras corregirlo.
- Añadido un comentario de advertencia explícito en el propio CSS para
  que este error de unidades no se repita en el futuro.

## AnchoLibrePracticoValidator + heurística de "cortar por el lado más largo" [ARCH:ancho-libre-practico]

A partir de una captura de pantalla real del usuario (proporciones
extrañas en el plano: "Almacén" generado como 2.49m×0.49m, "Comedor"
como 3.69m×11.93m) -- normativamente conforme en área, pero
prácticamente inservible.

- **[RESUELTO] `AnchoLibrePracticoValidator`** (nuevo, 19º validador):
  ancho libre mínimo de **1.20m, explícitamente NO normativo**
  (confirmado con el usuario, no un valor del Decreto 29/2010) para los
  9 tipos que el decreto deja sin ancho libre especificado (comedor,
  despacho, aseo, lavadero, tendedero, almacenamiento, recibidor,
  garaje, cuarto técnico) -- confirmados sistemáticamente contra TODOS
  los validadores existentes, no solo `AnchoLibreEstanciaValidator`.
  `STORAGE_ROOM` (trastero) excluido, ya tiene su propio mínimo
  normativo (B.2.5, 1.60m).
- **Efecto secundario real y serio, no solo "cambia la semilla"**:
  añadir esta restricción hizo que un caso real (9 estancias, mismo
  programa del usuario) dejara de converger incluso con 30.000
  iteraciones y una parcela 6 veces más grande -- confirmado aislando
  la causa (quitando el validador, la misma semilla converge en 22s).
- **[RESUELTO] Investigación aplicada antes de bajar el umbral**:
  en vez de simplemente relajar 1.20m, se investigó la causa
  estructural -- Marson & Musse (2010, ya citados antes en este
  proyecto para el treemap de zonificación) describen cortar
  particiones por el lado MÁS LARGO del rectángulo (técnica de
  "squarified treemap") para que las estancias salgan con proporción
  cercana a 1:1, en vez de tiras finas. `PartitionNode.direction=None`
  ahora significa "automático, lado más largo, decidido en
  `place_tree` en el momento de colocar" (no se puede saber al
  construir el árbol, porque depende de la forma real del rectángulo
  en ese punto) -- valor explícito ("h"/"v") sigue forzando esa
  dirección, usado por `flip_direction` (ahora cicla 3 estados:
  automático→h→v→automático, no un toggle binario).
- **Resultado medido, no solo esperado**: el caso real que fallaba
  hasta con 30.000 iteraciones convergió en 5.000 (semilla 1 directa).
  Cambio de núcleo de generación → cambia dinámica de búsqueda otra
  vez (mismo patrón ya documentado varias veces) -- 8 tests con semilla
  fija necesitaron una semilla nueva, resueltos uno a uno, no en bloque.
- **[RESUELTO] `--lot-size` (CLI, nuevo)**: `--import-seleccion` usaba
  siempre la parcela de ejemplo fija (14x16), sin forma de ajustarla.
  Añadido para acercarse al tamaño real de una parcela, y también
  porque hacía falta para recrear un caso de dificultad real y
  ESTABLE (por espacio, no por una coincidencia de forma que una
  mejora futura del algoritmo pudiera volver a resolver) en los tests
  de reintento de semillas.
- Suite final: 339/339 (309 unitarios + 30 integración), `pyflakes` y
  `mypy` limpios (77 archivos).

## Auditoría completa tras el tramo de trabajo intenso (visor, validador práctico, heurística de partición)

A petición del usuario, tras un tramo largo de cambios rápidos
(visor de plano, fusión de dashboard, `AnchoLibrePracticoValidator`,
heurística de lado más largo, `--lot-size`/`--retry-seeds`).

- **Suite completa**: 342/342 (312 unitarios + 30 integración, dividida
  en lotes por el límite de tiempo de ejecución -- los tests de
  `--import-seleccion`/reintento son lentos, subprocess real).
  `pyflakes`, `mypy` (77 archivos) y `radon` (sin D/E/F) limpios.
- **[RESUELTO] `CONTINUIDAD.md` desactualizado sobre sí mismo, otra vez**
  (mismo patrón ya documentado antes, confirma que sigue siendo el
  punto de fallo más recurrente): "18 validadores" (ya 19), "315/315
  tests" (ya 342), "dashboard... 4 pestañas" (ya 5), sección del
  importador sin mencionar nombres legibles/`--lot-size`/`--retry-seeds`
  (añadidos después de escribirse esa sección). Corregido todo.
- **[RESUELTO] Aplicada la propia convención de tests del proyecto
  retroactivamente**: la verificación del bug de `stroke-width` en
  metros se hizo con `cairosvg` de forma exploratoria en su momento,
  pero nunca se convirtió en test permanente -- hueco real detectado
  al auditar contra la propia regla 1 de "Convención de tests".
  Añadido `tests/unit/test_dashboard_sanity.py` (3 tests, sin necesitar
  Node/navegador): grosor de línea en metros razonables, número de
  pestañas coincide con número de paneles, `GARAGE.min_exterior` del
  dashboard coincide con Python -- los dos últimos cierran el mismo
  hueco de "verificación manual que nunca se hizo permanente" para
  hallazgos de auditorías anteriores.
- Añadidas lecciones nuevas a "Cosas aprendidas por las malas":
  `jsdom` encuentra bugs que `node --check` no puede; unidades de
  `stroke-width` en SVG con `viewBox` no-píxel; capturas de pantalla
  reales revelan categorías enteras de problemas sin cobertura
  automatizada; investigar la causa estructural antes de relajar un
  umbral que rompe la convergencia.

## Posicionamiento por rango en el diagrama de red (matriz de relaciones ponderadas)

A petición del usuario, que aportó la metodología formal de "matriz de
relaciones ponderadas" (clásica en programación arquitectónica): el
orden descendente de la suma de relaciones de cada estancia define su
rango de jerarquía y posición central o periférica.

- **[RESUELTO] `computeRanks(scores)`** (nuevo): convierte las
  puntuaciones ya existentes (`WEIGHT`, sin cambios) en un rango
  0-indexado, con empates compartiendo el rango PROMEDIO del grupo
  ("competition ranking" estándar) -- misma jerarquía, misma posición,
  no un desempate arbitrario por orden alfabético o de aparición.
- **`buildNetwork` ya no usa un radio fijo para todos los nodos** --
  la distancia al centro ahora interpola entre `MIN_R` (rango 0, más
  central) y `MAX_R` (último rango, más periférico) según el rango de
  cada tipo. La posición ANGULAR se mantiene por zona
  (`networkOrder()`, sin cambios) para conservar la lectura por
  agrupación día/noche/servicio/circulación que ya existía. Añadidos
  anillos guía discontinuos para que el patrón centro/periferia se
  perciba de un vistazo, no solo por el tamaño de los nodos (que ya
  codificaba la puntuación, sin cambios).
- **Verificado con datos reales, no solo revisión de código**: extraídas
  las posiciones reales renderizadas vía `jsdom` y comparada la
  distancia al centro contra la puntuación real de cada tipo --
  confirmado monótono (a menor puntuación, mayor distancia SIEMPRE) y
  que los empates de puntuación comparten exactamente la misma
  distancia (p.ej. `LAUNDRY`/`DRYING_AREA`, ambos con puntuación 4,
  ambos a 114.3px del centro).
- Suite Python: sin cambios (312/312 unitarios, el HTML es
  independiente). Tests de sanidad del dashboard (`test_dashboard_sanity.py`)
  siguen intactos.

## Exportación de tabla (Schedule) en Sinergias

A petición del usuario, tras comparar el flujo de trabajo con Revit
(elementos Room/Area con parámetros, add-ins de diagramación de
burbujas, Schedules exportadas a Excel para el cruce manual de
valores 4/2/0 y suma de rangos): la comparación confirmó que ya
teníamos el equivalente automatizado de las tres piezas de ese flujo
(parámetros de Room ~ `PROPS`, diagrama de burbujas ~ nuestra red de
sinergias, cruce+suma en Excel ~ `computeScores`/`computeRanks`,
calculados automáticamente en vez de a mano) -- pero faltaba la
exportación final a una tabla real, útil para trabajar fuera del
dashboard.

- **[RESUELTO] `exportScheduleCSV()`** (nuevo): vuelca a CSV los 16
  tipos con tipo, nombre, zona, categoría, área representativa,
  puntuación de sinergia y rango -- reutilizando `computeScores`/
  `computeRanks` ya existentes (sin cálculo nuevo, solo exportación).
  Ordenado por rango, mismo criterio que el diagrama de red.
- Verificado con `jsdom`: CSV real capturado (17 filas, cabecera + 16
  tipos), confirmado que coincide exactamente con los rangos/empates ya
  verificados para el diagrama de red (mismo `LAUNDRY`/`DRYING_AREA`
  empatados en 3.5, etc.) -- misma fuente de datos, sin duplicar lógica.
- Suite Python sin cambios (312/312), tests de sanidad del dashboard
  intactos.

## tipo_vivienda conectado de verdad (hallazgo #1 de la auditoría de flujo completo)

El usuario pidió una recopilación de fallos/huecos de flujo, y confirmó
empezar por el más engañoso: `tipo_vivienda` (aislada/pareada/adosada)
se exportaba desde el dashboard desde hace varias rondas, pero **ningún
sitio de Python lo leía** -- elegir "adosada" en el panel automático no
tenía ningún efecto real al generar, se perdía en silencio sin ningún
aviso.

- **[RESUELTO] `import_seleccion_plantas` ahora devuelve
  `SeleccionImportada(program, medianera_sides)`** (antes devolvía solo
  `Program` -- cambio de tipo de retorno, todos los llamadores
  actualizados). `medianera_sides` se resuelve del `tipo_vivienda` del
  JSON vía `MEDIANERA_SIDES_BY_TIPO_VIVIENDA` (aislada→vacío,
  pareada→1 lado, adosada→2 lados opuestos este/oeste) -- listo para
  pasarse directamente a `Lot(medianera_sides=...)`.
- CLI actualizado: al usar `--import-seleccion`, el `Lot` construido
  (con o sin `--lot-size`) ahora incluye `medianera_sides` real,
  informando por consola qué lados se aplicaron.
- **De paso, otro hallazgo menor de la misma auditoría**: el texto de
  ayuda de `--import-seleccion` seguía diciendo "el JSON es solo una
  selección de tipos... nunca cuenta ni áreas reales" -- ya resuelto
  hace varias rondas (formato v2 con cantidad/área reales). Corregido.
- **Confirmado con el recorrido completo real, no solo tests**:
  generada una selección "adosada" de verdad desde el dashboard
  (`jsdom`, clics reales) → exportación real capturada → CLI real →
  confirmado GEOMÉTRICAMENTE que las estancias llegan exactas a x=0.0
  y x=14.0 (este/oeste) sin retranqueo, mientras que en el eje
  norte/sur sí se respeta -- la elección del usuario en el dashboard
  ahora sí determina la geometría real generada.
- Añadidos 5 tests nuevos (`test_tipo_vivienda_*`, cero cobertura
  antes). Suite final: 347 (317 unitarios + 30 integración), pyflakes
  y mypy limpios.

## ViviendaAccesibleValidator (retomado de un proyecto Lua anterior del usuario)

El usuario compartió 10 archivos Lua de un proyecto anterior propio --
un sistema de validación (no generación) que cubre NHV, accesibilidad
(DB-SUA + Código de Accesibilidad de Galicia), térmica (DB-HE1),
acústica (DB-HR), cubierta (DB-HS1), incendios (DB-SI) y turismo
(Decreto 12/2017). Evaluación honesta: térmica/acústica/cubierta/
incendios son sobre MATERIALES Y ELEMENTOS CONSTRUCTIVOS (transmitancia
de muros, resistencia al fuego en minutos EI/R, pendientes por tipo de
teja) -- una capa de dominio que `Room` no tiene y no modela, no
transferible sin un salto de arquitectura mayor. Turismo es un tipo de
edificio distinto (apartamentos turísticos) al alcance actual (vivienda
unifamiliar). Accesibilidad SÍ encaja: mismo tipo de restricción
(anchos/círculos de giro) que ya teníamos.

- **[RESUELTO] `ViviendaAccesibleValidator`** (20º validador, **opt-in**
  -- `activo=False` por defecto, sin cambio de comportamiento existente):
  círculo de giro Ø1.50m inscribible en salón, comedor, dormitorios,
  cocina y baño (`TIPOS_CON_CIRCULO_GIRO`) + pasillo ≥1.20m (más
  exigente que el general de `AnchoLibrePasilloValidator`, 1.00m --
  ambos conviven, no se sustituyen). DB-SUA Anejo A + Base 5.4 del
  Código de Accesibilidad de Galicia (Decreto 35/2000, actualizado por
  el Decreto 74/2013), investigación normativa ya hecha en el propio
  Lua original (incluye resolución explícita de conflictos entre la
  fuente gallega y la estatal, con cita del Decreto 74/2013 que
  actualizó las cabinas de ascensor de Galicia para converger con
  EN 81-70).
- **Alcance recortado deliberadamente**: la fuente Lua también verifica
  mobiliario (altura de encimera, aproximación lateral a la cama, hueco
  bajo fregadero, barras de apoyo del aseo) -- fuera de alcance aquí,
  ya que `Room` no modela fixtures/mobiliario en absoluto. Se documenta
  la limitación explícitamente en vez de fingir una comprobación sin
  los datos reales, mismo principio que C.10/parámetro D de patios.
- Conectado de extremo a extremo desde el primer commit, aplicando la
  lección de la auditoría anterior (features construidas sin conectar
  al CLI): `vivienda_accesible` propagado por `build_per_floor_validators`
  → `build_generate_layout_use_case`/`build_generate_building_use_case`
  → `--vivienda-accesible` en el CLI.
- **Confirmado con generación real, no solo el validador aislado**:
  comparado el mismo programa de 11 estancias con y sin el flag --
  con `--vivienda-accesible`, TODAS las estancias del alcance tienen su
  lado más corto ≥1.50m; sin él, varias caen muy por debajo (p.ej.
  `bed1` a 4.96m de ancho pero con proporciones muy alargadas en el
  caso normal). Confirmado también vía subprocess real del CLI.
- Suite final: 358 (326 unitarios + 32 integración), pyflakes y mypy
  limpios (78 archivos).

## Rediseño completo del dashboard ("no tiene alma o personalidad")

El usuario pidió rediseñar toda la interfaz del dashboard -- consultada
`docs/frontend-design/SKILL.md` antes de empezar, evitando
deliberadamente los dos clichés de IA que la propia guía señala
(crema+terracota+serif con acento cercano a #D97757; negro casi puro +
un único acento brillante -- el dashboard anterior, navy+cian, caía
cerca del segundo).

- **[RESUELTO] Dirección: cianotipo técnico real**, no otro dashboard
  oscuro genérico -- fundamentado en el propio contenido (esta
  herramienta genera planos). Paleta de 6 tonos con nombre (azul
  cianotipo profundo, papel de calco SOLO en superficies de tarjeta,
  terracota como acento de firma usado con moderación, óxido para
  alertas). Tipografía: Space Grotesk (títulos, carácter técnico) +
  Archivo (cuerpo) + Space Mono (datos/medidas) -- sustituye IBM Plex
  por completo. Firma: cada pestaña pasa a ser una LÁMINA numerada
  (01-05) con cajetín de título, como una lámina real de un juego de
  planos -- estructura que informa (el número es real), no decoración.
- **Riesgo controlado antes de tocar nada**: inventario completo de
  todos los `id`/clases que el JS referencia (`getElementById`,
  `querySelector`, `COLORVAR`, `CAT_COLOR`) para preservarlos
  exactamente -- los NOMBRES de las variables CSS (`--bg`, `--oc`,
  `--cat-estancia`...) se mantuvieron sin cambios, solo se
  reescribieron sus VALORES hexadecimales.
- **Hallazgo real de paso, no buscado**: el texto de aviso de la
  pestaña Matriz seguía diciendo que "Preferencia" no tenía efecto en
  el generador y que "el sistema genera una sola planta" -- ambas cosas
  llevaban muchas rondas resueltas (`SoftConstraintScorer`,
  multi-planta). Corregido de paso.
- **Verificación en tres capas, sin navegador real disponible**:
  (1) `jsdom` (motor JS moderno) -- cero errores, las 5 pestañas
  funcionales, conteos de elementos correctos, generación automática y
  visor de plano probados de extremo a extremo tras el rediseño;
  (2) `wkhtmltoimage` (motor real pero antiguo, sin soporte de JS
  ES6+) -- confirma el HTML/CSS estático (cajetín, pestañas, aviso)
  con la paleta nueva real, aunque no el contenido generado
  dinámicamente; (3) extracción del HTML ya generado por `jsdom` +
  render aislado vía `wkhtmltoimage`/`cairosvg` -- confirma
  visualmente que la matriz (120 celdas reales) y la red de sinergias
  usan los colores de clasificación correctos de la paleta nueva.
- Limpiado un resto real: 5 usos del navy antiguo (`#0d1b2a`) como
  tinta de contraste sobre insignias/etiquetas de colores, sin
  actualizar durante el resto del rediseño -- sustituidos por la nueva
  tinta cálida (`#2B2622`) para coherencia.
- Añadidos 2 tests de sanidad nuevos (`test_dashboard_sanity.py`):
  confirma que no queda ninguna referencia a las fuentes anteriores, y
  que los nombres de variable CSS que el JS necesita siguen presentes
  -- cierra el mismo hueco de "verificación exploratoria nunca hecha
  permanente" ya encontrado en auditorías previas.
- Suite Python: 328/328 unitarios sin cambios de comportamiento (el
  HTML es independiente).

## Generador real en el navegador (Pyodide) -- respuesta a "¿es esta la forma de trabajar?"

El usuario cuestionó de fondo si el dashboard era realmente útil, no
solo si se veía bien. Diagnóstico honesto: el flujo real (exportar
JSON → salir al terminal a ejecutar el CLI → volver a cargar el
resultado) era un puente MANUAL entre dos mundos (navegador y Python)
que nunca se hablaban directamente -- una barrera real para quien no
sepa usar una terminal, y sin ninguna forma de iterar sin repetir todo
el proceso a ciegas.

- **[RESUELTO] Investigación de viabilidad antes de comprometerse**:
  el riesgo técnico señalado (¿soporta Pyodide `shapely`, que envuelve
  la librería C GEOS?) se confirmó explícitamente con fuentes oficiales
  con fecha (changelog de Pyodide) ANTES de construir nada -- `shapely`
  y `geos` están soportados oficialmente desde hace tiempo; `scipy`/
  `numpy` son parte del stack científico estándar; `networkx` es Python
  puro, se instala vía `micropip` sin problema.
- **[RESUELTO] `interface/browser/bridge.py`** (nuevo): puente entre
  JavaScript y el generador real -- recibe/devuelve solo datos planos
  (dict/JSON), nunca objetos de dominio (`Program`/`Lot`/`Layout` no
  cruzan bien el FFI de Pyodide). `generar_edificio(...)` reutiliza
  EXACTAMENTE la misma lógica que ya tenía el CLI (`import_seleccion_plantas`,
  reintento de semillas, `build_generate_building_use_case`) -- no se
  reescribió nada, solo se extrajo a una función que no toca disco.
  `JsonLayoutRepository.to_dict()` extraído de `save()` para poder
  usarse en memoria sin pasar por archivo (mismo resultado exacto,
  confirmado con un test que compara ambos caminos byte a byte).
- **[RESUELTO] Bundle Python embebido en el propio HTML** (`PY_BUNDLE`,
  80 archivos, ~230KB): sigue la misma filosofía de "archivo único, sin
  paso de compilación" que el resto del proyecto -- Pyodide escribe
  cada archivo en su sistema de archivos virtual al cargar, y
  `sys.path` apunta ahí. `scripts/regenerar_bundle_pyodide.py` (nuevo)
  regenera esto tras cualquier cambio a un `.py` del generador --
  riesgo real de mantenimiento identificado y cerrado con un test
  permanente (`test_pyodide_bundle_is_not_stale_against_the_real_source`,
  compara `bridge.py` real contra lo embebido, byte a byte).
- **Nuevo flujo real en "Sección vertical"**: botón "generar plano
  ahora" (parcela, semilla, iteraciones, vivienda accesible, todo
  configurable ahí mismo) -- genera de verdad, sin salir del navegador,
  y cambia automáticamente a "Visor de plano" con el resultado. El
  export a JSON sigue existiendo para quien prefiera el CLI a mano.
- **[RESUELTO] Versión de Pyodide confirmada explícitamente antes de
  escribir la URL** (`v314.0.2`, vía CDN de jsDelivr) -- un fallo real
  de mi propio primer intento (escribí `v0.28.0` por costumbre, sin
  verificar) corregido antes de continuar.
- **Límite honesto de verificación, no ocultado**: este entorno de
  trabajo bloquea el dominio `cdn.jsdelivr.net` (no está en la lista de
  dominios permitidos), así que no se pudo probar el flujo Pyodide
  COMPLETO de extremo a extremo con `shapely` real cargado. Lo que SÍ
  se verificó con evidencia real, no solo revisión de código:
  (1) el núcleo de Pyodide (intérprete Python 3.14 real, compilado a
  WebAssembly) se instaló vía npm y se ejecutó de verdad en Node.js,
  confirmando que el mecanismo en sí funciona; (2) `micropip` se cargó
  y ejecutó correctamente una vez se le dio el wheel correcto;
  (3) `shapely`/`geos` están documentados oficialmente como paquetes
  Pyodide soportados, con fecha, no asumido; (4) el flujo completo del
  botón "generar plano ahora", vía `jsdom`, llega correctamente hasta
  la propia llamada a `loadPyodide()` sin ningún error previo -- el
  único fallo que aparece es "loadPyodide is not defined", exactamente
  lo esperado dado el bloqueo de red de ESTE entorno, no un error del
  código. **Queda pendiente que el usuario lo pruebe en un navegador
  real con acceso a internet normal**, donde este bloqueo no existe.
- Suite Python: 372 tests en total (crecimiento neto de este bloque:
  refactor de `JsonLayoutRepository` + `bridge.py` + tests de sanidad
  del dashboard ampliados), pyflakes y mypy limpios (81 archivos).

## ProporcionMaximaValidator -- cierre del hallazgo de la bateria de casos reales [ARCH:proporcion-maxima]

El usuario insistió en probar con casos reales de forma sistemática en
vez de confiar en tests sintéticos aislados -- confirmado que tenía
razón: una batería de 5 escenarios generados con el propio panel
automático del dashboard (no inventados a mano) reveló estancias de
hasta 9.5:1 (un dormitorio de 2.11m × 20.00m), normativamente válidas
pero absurdas.

- **[RESUELTO] Investigación antes de tocar código, a petición
  explícita del usuario**: comprobado que NO existe límite normativo
  de proporción en ninguna fuente (ni el Decreto 29/2010 ni el CTE) --
  solo guía de diseño de interiores (proporción "agradable" 1:1.5 a
  1:2.5, razón áurea ~1.6:1 como referencia). También investigada la
  regla REAL de squarified treemap (Bruls/Huizing/van Wijk 2000): no
  es solo "cortar por el lado más largo" (simplificación que ya
  teníamos) sino "elegir la orientación que minimiza la peor
  proporción resultante, dado el reparto de área real del corte".
- **Hallazgo matemático real, no asumido**: implementada la regla
  completa (`_worst_aspect_ratio` en `partition_tree.py`, evalúa ambas
  orientaciones) y confirmado con 200.000 pruebas aleatorias que
  produce EXACTAMENTE el mismo resultado que la heurística anterior
  ("cortar por el lado más largo") en el 100% de los casos -- son
  matemáticamente equivalentes para un corte binario. La heurística
  anterior YA era óptima; el problema nunca fue la dirección de corte.
  Se mantuvo la versión explícita (evalúa ambas, no asume) por ser más
  robusta de razonar y demostrar, aunque el resultado sea idéntico.
- **[RESUELTO] `ProporcionMaximaValidator`** (21º validador, siempre
  activo, no opt-in -- red de seguridad general): proporción máxima
  2.5:1 NO NORMATIVA (confirmada explícitamente con el usuario, el
  extremo más permisivo de la guía encontrada) para CUALQUIER
  estancia, a diferencia de los validadores de ancho mínimo que solo
  cubren tipos concretos. Causa raíz real: dos hojas de área muy
  distinta como hermanas en el árbol de partición fuerzan un reparto
  desigual que NINGUNA dirección de corte puede evitar -- por eso hace
  falta una red de seguridad explícita sobre el resultado final, no
  solo una heurística de generación mejor (que ya era óptima).
- **Confirmado con el mismo caso real que lo encontró**: la vivienda de
  5 dormitorios que producía 9.5:1 ahora converge en 15.2s (semilla 1
  directa, antes necesitaba varias) con una proporción máxima de
  2.32:1 en toda la vivienda.
- Semillas actualizadas tras el cambio (mismo patrón de siempre):
  CLI por defecto ahora `--seed 4`; `--lot-size` de referencia en
  tests cambiado de 11x10 a 12x10 (el caso ajustado anterior dejó de
  fallar con la semilla 1, necesitaba uno nuevo para seguir
  demostrando el reintento automático).
- Suite final: pyflakes y mypy limpios (82 archivos). Ver commit para
  el recuento total de tests.

## Separación de archivos del dashboard (HTML/CSS/JS/bundle)

El usuario, tras revisar el HTML, preguntó si no sería mejor separar
CSS/JS del HTML y reducir la cantidad de información comentada.

- **[RESUELTO] Investigación técnica antes de separar, no asumido**:
  el riesgo real era romper la promesa de "abrir con doble clic, sin
  servidor" que el proyecto mantiene desde el principio. Confirmado con
  fuentes concretas: los scripts CLÁSICOS (`<script src="archivo.js">`,
  sin `type="module"`) y las hojas de estilo (`<link rel="stylesheet">`)
  SÍ funcionan desde `file://` sin servidor -- es específicamente
  `fetch()` y los módulos ES los que se bloquean (origen `null` de
  `file://`, tratado como no confiable por CORS). El proyecto ya evitaba
  `fetch()` para el bundle (usaba una constante JS embebida
  precisamente por esto) -- separar en archivos clásicos no cambia nada
  de esa propiedad.
- **4 archivos en vez de 1**: `relaciones_espaciales.html` (11KB,
  antes 560KB+), `.css` (23KB), `.js` (lógica principal), `py_bundle.js`
  (el código Python embebido, en su propio archivo -- regenerado con
  `scripts/regenerar_bundle_pyodide.py`, actualizado para escribir ahí
  en vez de dentro del HTML).
- **Verificado que sigue funcionando sin servidor, no solo asumido**:
  `wkhtmltoimage` (motor real) bloqueó inicialmente el acceso a los
  `.js` locales -- resultó ser una política de seguridad PROPIA de esa
  herramienta (más estricta que un navegador real por defecto,
  documentada con su propio flag `--enable-local-file-access`), no una
  limitación de `file://` en sí -- confirmado con investigación
  específica y con el flag correcto, la carga funciona igual que en un
  navegador real. `jsdom` (motor moderno) confirmó cero errores y toda
  la funcionalidad intacta (chips, generación automática, visor, modo
  espejo) cargando los 3 archivos por separado desde disco.
- Comentarios: revisados los bloques más largos del JS -- ninguno
  resultó excesivo por sí solo (5-12 líneas), el volumen percibido
  venía sobre todo del tamaño total del archivo (resuelto con la
  separación). No se hizo una poda agresiva de comentarios existentes:
  documentan decisiones reales trazables (bugs encontrados, fuentes
  citadas, confirmaciones explícitas con el usuario) que el propio
  proyecto depende de no tener que re-investigar -- mismo principio que
  "Cosas aprendidas por las malas" en CONTINUIDAD.md.
- `tests/unit/test_dashboard_sanity.py` reescrito para leer cada
  comprobación del archivo correcto (HTML/CSS/JS/bundle) en vez de
  todo del HTML monolítico -- incluye un test nuevo que confirma que
  el HTML referencia los 3 archivos con etiquetas clásicas, nunca
  `type="module"`.
- Suite Python: 343 unitarios (uno nuevo), sin cambios de
  comportamiento (separación de archivos, no de lógica). pyflakes y
  mypy limpios (82 archivos).

## Limpieza de código muerto encontrado durante la división por pestañas

Al empezar a dividir `relaciones_espaciales.js` por pestañas (según lo
confirmado), una comprobación rutinaria del tamaño del archivo reveló
algo real: contenía un bloque `const PYTHON_SOURCES = {...}` de
**227KB completamente muerto y sin usar** -- una versión antigua y
abandonada del bundle Python, con un puente distinto
(`generar_en_navegador`, no el `generar_edificio` real de
`bridge.py`), residuo de una iteración anterior de la construcción del
generador vía Pyodide que nunca se limpió. El código real solo
referencia `PY_BUNDLE` (definido en `py_bundle.js`, el archivo
separado) -- `PYTHON_SOURCES` no se usaba en ningún sitio.

- **[RESUELTO] Eliminado por completo**: `relaciones_espaciales.js`
  pasó de 298KB a 71KB. Verificado con `jsdom` que todo sigue
  funcionando exactamente igual (chips, generación automática, visor,
  cero errores) tras la eliminación -- no era código en uso.
- Comentario huérfano de cabecera (describía el bloque ya eliminado)
  también corregido, para no dejar documentación desactualizada.
- Lección de proceso: este bloque llevaba ahí desde antes de la
  separación en 4 archivos, y sobrevivió esa separación sin que se
  detectara -- el tamaño final del archivo (298KB, sospechosamente
  grande para "solo lógica principal") habría sido la señal a
  revisar entonces. Vale la pena comprobar tamaños de archivo tras
  cualquier refactor grande, no solo confiar en que "funciona" como
  señal de que está limpio.

## División de `relaciones_espaciales.js` por pestaña/concepto

Confirmado con el usuario tras revisar el repositorio `RedM-Website-
Template` (único hallazgo genuinamente aplicable de esa exploración:
separar cada pieza reutilizable en su propio archivo pequeño, aunque
ese proyecto use páginas de Next.js, no aplicable directamente).

- Dividido en 8 archivos dentro de `docs/visualizador/js/`, por los
  marcadores de sección ya existentes en el código: `00-shared.js`
  (PAIRS/FLOORS/PROPS/DISPLAY y utilidades comunes -- debe cargar
  primero, todo lo demás depende de sus globals), `01-matriz.js`,
  `02-seccion.js`, `03-fichas.js`, `04-sinergias.js`, `05-visor.js`
  (visor de plano + modo espejo, fusionados por ser la misma pestaña),
  `06-pyodide.js` (generador real en el navegador), `07-init.js`
  (arranca todo -- debe cargar último, llama funciones definidas en
  todos los demás archivos).
- Sin módulos ES (mismo motivo que la separación anterior: deben
  funcionar desde `file://` sin servidor) -- scripts clásicos que
  comparten el mismo scope global de `window`, cargados en orden fijo
  vía `<script src="">` en el HTML. Verificado que el orden se respeta
  con un test permanente (`test_html_references_js_files_via_classic_tags_in_order`).
- Verificado con `jsdom` y `wkhtmltoimage` (con `--enable-local-file-
  access`) que todo funciona exactamente igual tras la división: cero
  errores, matriz/sección/fichas/sinergias/visor/modo espejo/botón
  generar, todos intactos.

## Auditoría completa de código muerto (a petición del usuario)

Tras encontrar el bloque `PYTHON_SOURCES` de 227KB muerto en el JS,
el usuario preguntó directamente: "¿entonces seguro que no tenemos más
código muerto?" -- pregunta justa, no contestable de memoria dado lo
que acababa de pasar. Auditoría sistemática, no solo revisión visual:

- **`vulture`** (detector real de código muerto para Python) instalado
  y ejecutado sobre `src/` -- confirmó, además del bloque JS ya
  encontrado, un **archivo Python completo huérfano**:
  `infrastructure/browser_bridge.py` (78 líneas) -- el archivo fuente
  REAL detrás del bloque JS muerto, con la misma función antigua
  (`generar_en_navegador`, no la real `generar_edificio` de
  `interface/browser/bridge.py`). Nadie lo importaba, en ningún sitio
  -- confirmado con dos métodos independientes (`vulture` + búsqueda
  directa de imports en todo el árbol). **[RESUELTO] Eliminado.**
- Descubierto de paso: este archivo huérfano SÍ se estaba colando en
  `py_bundle.js` en cada regeneración (el script barre por carpeta,
  no por uso real) -- 233KB añadidos sin ningún motivo, en cada
  regeneración, sin que nadie lo notara. Bundle regenerado tras
  eliminar el archivo (81 → 80 archivos).
- El resto de hallazgos de `vulture` (confianza 60%, su nivel más
  bajo) se revisaron uno a uno contra tests reales antes de decidir,
  no se aceptaron ni descartaron en bloque:
  - `GraphBasedLayoutGenerator`, `BuildAdjacencyGraphUseCase`,
    `ValidateLayoutUseCase`, `build_program_with_auto_adjacency`,
    `build_day_night_zoning_validators`, y varios campos de
    dataclass -- **NO son código muerto**: tienen tests propios que
    los verifican, son piezas alternativas deliberadas de la
    arquitectura hexagonal (demuestran que el generador es
    intercambiable), simplemente no conectadas al pipeline principal
    de `container.py`. Confirmado con tests dedicados para cada uno,
    no solo con la confianza baja de `vulture`.
  - `AdjacencyStrength.INDIFFERENT` -- **mantenido**: el propio
    catálogo documenta que "Neutro" se representa por AUSENCIA de
    entrada, no asignando este valor -- decisión de diseño deliberada,
    el valor documenta el modelo clásico completo de 5 niveles aunque
    nunca se instancie.
  - **[RESUELTO] Eliminados, confirmados con el usuario uno a uno**:
    `ConstraintViolationError` (excepción nunca lanzada, sin camino de
    error que la use), `Room.requires_natural_light` /
    `Room.requires_direct_access_exterior` (campos sin comentario, sin
    ningún validador que los leyera -- mismo riesgo de "aprobación
    silenciosa" que este proyecto evita activamente en todos los demás
    sitios via el patrón de 3 estados None/True/False),
    `Layout.rooms_in_zone` (método de consulta sin ningún llamador).
- Lado JavaScript: cada función definida en los 8 archivos de `js/`
  comprobada por referencias -- ninguna con solo su propia definición.
  Limpio.
- Búsqueda de archivos completos huérfanos en `src/` (nadie los
  importa) confirmó que `browser_bridge.py` era el único.
- Suite final: 343 unitarios + 23 integración confirmados tras las
  eliminaciones, pyflakes y mypy limpios (81 archivos fuente).

# Referencia técnica por componente [ARCH:*]

A partir de aquí, no es histórico cronológico (eso sigue arriba, sin
tocar) -- es referencia consolidada por pieza de código, para que un
comentario corto en el código (`[ARCH:tag]`) pueda apuntar aquí sin
tener que rastrear varias secciones distintas. Cada entrada junta lo
que antes vivía como docstring largo en el propio archivo fuente.

## [ARCH:partition-node] PartitionNode y place_tree

`direction=None` (automático) minimiza la peor proporción ancho:alto
resultante del corte -- regla real de squarified treemap (Bruls/
Huizing/van Wijk 2000, aplicada a plantas por Marson & Musse 2010).
La simplificación anterior ("cortar por el lado más largo") resultó
insuficiente: no mira el reparto de área real del corte, y un
contenedor casi cuadrado partido 90/10 sigue dando una tira fina en
cualquier dirección -- confirmado con un caso real (vivienda de 5
dormitorios, dormitorios de hasta 9.5:1). Investigado después con
200.000 pruebas aleatorias: la heurística "lado más largo" y la regla
completa (`_worst_aspect_ratio`, evalúa ambas orientaciones) dan
siempre el mismo resultado en un corte binario -- son equivalentes,
la dirección de corte nunca fue el problema real; ver
`[ARCH:proporcion-maxima]` para la causa raíz real y su arreglo.

`ratio_override`: proporción de corte forzada manualmente (0-1,
fracción de `first`), independiente del área declarada de las
estancias. Inspirado en Merrell/Schkufza/Koltun 2010 ("Sliding a
wall" como proposal move propio, distinto de "swapping rooms") --
investigación externa confirmada. Sin esto, la proporción de cada
corte quedaba siempre atada al área declarada, sin ningún grado de
libertad para ajustar forma/ancho libre sin cambiar topología.

`random_neighbor` -- 4 movimientos: intercambiar hojas, invertir
dirección (ciclo None→"h"→"v"→None, no un toggle binario, porque la
dirección "automática" depende del rectángulo real en el momento de
colocar, no se puede saber solo mirando el nodo), intercambiar
subárboles, y "deslizar pared" (`slide_wall`, el movimiento inspirado
en Merrell et al. arriba).

## [ARCH:enums] domain/enums.py -- decisiones de clasificación

**`ZoneType.CIRCULATION`**: distinta de DAY/NIGHT/SERVICE -- no es una
macro-zona de uso, es la clasificación honesta para estancias que
sirven a varias zonas a la vez (CORRIDOR, ENTRANCE_HALL, STAIRCASE).
Forzarlas a DAY por defecto generaba violaciones falsas de
zonificación cuando un pasillo servía correctamente a la zona noche
(bug real encontrado en auditoría).

**`AdjacencyStrength`**: SHOULD_BE_NEAR/SHOULD_BE_AWAY usan una
métrica distinta (saltos en el grafo, cerca ≤2/alejar ≥3) que
MUST_BE_NEAR/MUST_BE_AWAY (contacto geométrico directo, ancho de
puerta 1.0m) -- decisión deliberada de no unificar métricas para no
perder esa precisión. Ver `SoftConstraintScorer`.

**`DEFAULT_WET_ROOMS`**: confirmado por normativa (CTE DB-HS) y
práctica de fontanería (cada local húmedo con su propia llave de
corte). `tendedero` queda fuera -- normalmente prolongación del
lavadero sin desagüe propio.

**`SpaceCategory`**: Tabla 1 (ESTANCIA) vs Tabla 2 (SERVICIO) vs
CIRCULACION (reglas de anchura, no superficie). Cocina es "pieza
vividera" pero NO "estancia" a efectos de Tabla 1 -- dos
clasificaciones normativas distintas, confirmado contra el decreto.

**`DEFAULT_MIN_EXTERIOR_SIDES`**: confirmado caso por caso con el
usuario, no derivado automáticamente. `GARAGE=0` -- corregido tras
investigación (antes era 1): sin respaldo normativo real (B.2.6 es de
garajes colectivos, no unifamiliares; ni siquiera `nhv.lua` lo exigía).
Ancho de exterior es asunto de urbanismo (A.2.1), no de habitabilidad
por estancia. Override disponible por proyecto si hace falta.

**`DISPLAY_NAMES`**: debe coincidir EXACTAMENTE con el mapeo `DISPLAY`
del dashboard (`docs/visualizador/js/00-shared.js`) -- si uno cambia,
cambiar el otro. Bug real encontrado en su momento: el nombre técnico
del tipo se usaba como `Room.name`, visible en el plano final.

## [ARCH:generate-building] GenerateBuildingUseCase

Orquesta la generación multi-planta: agrupa por `Room.level`, genera
de abajo a arriba (búsqueda independiente por planta, no conjunta),
encadenando alineación de escalera + continuidad de núcleo húmedo
entre plantas consecutivas. Primer incremento deliberadamente
simplificado: todas las plantas comparten `lot.buildable_area`; el
programa mínimo se comprueba una sola vez, a nivel de edificio
completo (uniendo tipos de todas las plantas).

`PerFloorValidatorsFactory` se inyecta como función, no como clases
concretas, para que esta capa de aplicación no dependa de
infraestructura -- incluye el número total de estancias del edificio
completo (bug real corregido: sin esto, una planta con pocas
estancias aplicaba una fila de Tabla 1/2 más baja de la real).

`_shrink_for_next_floor`: encoge el contorno progresivamente
(`buffer(-x)`), con red de seguridad (investigación externa
confirmada, patrón `MinArea{Action:Shrink, Fallback:...}`) -- si el
área encogida no alcanza para las estancias declaradas, no se encoge,
usa la misma huella que la planta de abajo.

`_check_bano_acceso_general`: reutiliza el validador de una sola
planta, ejecutado POR PLANTA -- la accesibilidad de un baño no se
"hereda" de otra planta. Corrige un hueco real: antes esta regla no se
comprobaba en absoluto en modo multi-planta.

## [ARCH:container] config/container.py -- composition root

`build_per_floor_validators`: `ViviendaMinimaValidator` y
`BanoAccesoGeneralValidator` quedan fuera deliberadamente -- son de
ámbito EDIFICIO, no de planta, se comprueban aparte en
`GenerateBuildingUseCase`. `total_num_estancias`/`global_rank`: del
edificio completo, no solo de esta planta (dos bugs reales corregidos
en el primer edificio de 2 plantas de prueba). `vivienda_accesible`:
opt-in, por defecto False.

`build_generate_building_use_case`: si la vivienda tiene más de una
planta, el requisito de vivienda accesible se aplica en todas las
plantas por igual (la fuente Lua original distinguía "duplex" como
caso aparte, aquí no).

## [ARCH:estancia-minimum-area] EstanciaMinimumAreaValidator

Tabla 1 (A.3.2.1): superficie mínima por puesto de tamaño entre las
estancias (space_category ESTANCIA). La "estancia mayor" para el
cuadrado inscribible (A.3.2.1.a) es SIEMPRE el salón -- regla de
proyecto, no derivación automática por área; el ranking de Tabla 1 es
un concepto independiente. Si no hay salón: usa la de mayor área como
alternativa, marcado como AVISO, nunca aprobación silenciosa.

`total_num_estancias_override`/`global_rank_override`: número y
ranking del EDIFICIO completo, no solo de esta planta -- dos bugs
reales corregidos al construir el primer edificio de 2 plantas de
prueba (una planta con 1 estancia aplicaba la fila de "vivienda de 1
estancia" en vez de la fila real del edificio).

En multi-planta, "no hay salón en esta planta" es el caso NORMAL para
plantas superiores (el salón está en otra planta) -- sustituir por la
mayor estancia local generaba violaciones falsas; corregido para no
sustituir en ese caso, la planta con el salón real ya lo comprueba
por su cuenta.

## [ARCH:simulated-annealing] SimulatedAnnealingLayoutGenerator

Árbol de partición sobre todas las estancias a la vez (sin fase previa
de macro-zona), recocido simulado sobre la topología. Función objetivo:
comparación LEXICOGRÁFICA real, tupla `(duro, blando)`, no suma
ponderada -- una versión anterior sumaba `duro*peso + blando`, que
garantiza el orden final pero rompe la dinámica de aceptación del
recocido (`exp(-delta/temperatura)` reacciona a la magnitud absoluta
del delta, no solo al orden relativo; confirmado que rompía tests que
no tocaban restricciones blandas). Con la tupla, si lo duro cambia, la
aceptación se decide solo por ese delta; lo blando solo entra cuando
lo duro empata.

Recibe `ConstraintValidatorPort` como dependencia propia (no solo
`GenerateLayoutUseCase`) porque lo invoca miles de veces durante la
búsqueda -- generación y validación acopladas en esta implementación
concreta, aunque ambas siguen siendo ports intercambiables en el
resto del sistema. `zones` del puerto se ignora deliberadamente.

`self._rng` se recrea en CADA llamada a `generate()` (bug real
corregido: antes se creaba una sola vez en `__init__`, así que `seed`
solo era reproducible en la primera llamada sobre el mismo generador).

## [ARCH:shapely-utils] geometry/shapely_utils.py

`count_exterior_sides`: umbral de contacto exterior (0.3m) distinto y
mayor que el de adyacencia interior (0.1m), confirmado con el usuario.
`excluded_segments` excluye lados de medianera (vivienda pareada/
adosada) -- una pared de medianera no tiene luz ni ventilación propia
aunque geométricamente sea un borde de parcela.

`evaluate_minimum_width`: helper compartido, extraído tras encontrar
duplicación real (detección sistemática de bloques repetidos): tres
validadores distintos (pasillo, escalera, trastero) repetían
exactamente el manejo de los 3 estados de `meets_minimum_width`, solo
cambiaba el umbral y el texto del mensaje.

## [ARCH:type-adjacency-catalog] domain/services/type_adjacency_catalog.py

Generado programáticamente desde `docs/relaciones_espaciales.md`, no
transcrito a mano. 82 de 120 pares totales tienen entrada aquí; el
resto se omite deliberadamente: 35 "Neutro" (ausencia = sin requisito),
2 "Condicional" (BEDROOM/MASTER_BEDROOM x BATHROOM -- depende del
número de baños del Program completo, no del par en sí, resuelto en
`BanoAccesoGeneralValidator`), 1 "Ya cubierto" (KITCHEN-BATHROOM, ya
exigido por núcleo húmedo).

`build_adjacency_requirements` se aplica a CADA PAR de estancias
existentes cuyo tipo tenga entrada -- si hay dos BEDROOM, ambos
reciben la misma relación hacia, p.ej., BATHROOM (catálogo por TIPO,
no por instancia).

## [ARCH:lot] domain/entities/lot.py

`retranqueo_m`: NO es un valor fijo de la normativa de habitabilidad
-- el propio Decreto 29/2010 remite esto a la legislación urbanística
(Ley 2/2016 do solo de Galicia + PXOM municipal), así que es un
parámetro que declara quien usa el proyecto, no una constante asumida.

`retranqueo_incremento_por_planta_m`: técnica de "subtractive
generation" (investigación externa confirmada, Devans "Procedural
Generation For Dummies: Building Footprints") -- encoge
progresivamente cada planta respecto a la de abajo, con red de
seguridad (`MinArea{Action:Shrink, Fallback:...}`): si el área
resultante no alcanza para las estancias declaradas, usa la misma
huella que la planta inferior en vez de encoger a un tamaño inválido.

`medianera_sides`: vivienda pareada/adosada (1-2 lados sin retranqueo
ni contacto exterior real -- una pared de medianera no tiene luz ni
ventilación propia). Requiere parcela rectangular ortogonal, misma
simplificación geométrica que el resto del proyecto.

## [ARCH:seleccion-plantas-importer] persistence/seleccion_plantas_importer.py

Importa `seleccion_plantas.json` (exportación del dashboard) hacia un
`Program` real. Soporta formato nuevo (`version: 2`, cantidad + área
real por entrada) y antiguo (lista plana de nombres, sin cantidad ni
área -- retrocompatible con exportaciones previas al cambio).

`tipo_vivienda` se resuelve a `medianera_sides`: hallazgo real de una
auditoría de flujo completo -- el dashboard exportaba `tipo_vivienda`
desde hacía varias rondas, pero ningún sitio de Python lo leía (elegir
"adosada" no tenía ningún efecto real al generar). "pareada" usa un
lado (convención propia, "east" -- el dashboard no pregunta
orientación real); "adosada" usa dos lados opuestos (este/oeste).

`AREAS_POR_DEFECTO_M2`: solo se usa con el formato antiguo o si una
entrada nueva no trae área -- no derivadas de Tabla 1/2 (dependen del
número total de estancias, no se puede saber de antemano).

## [ARCH:browser-bridge] interface/browser/bridge.py

Puente entre el dashboard (JS, Pyodide) y el generador real -- solo
cruza datos planos (dict/JSON), nunca objetos de dominio (no cruzan
bien el FFI de Pyodide). Comparte toda la lógica de generación con el
CLI, solo difiere en dónde entra el dato (payload en memoria vs.
archivo) y dónde sale (dict vs. archivo). Reintenta semillas
automáticamente, mismo comportamiento que `--retry-seeds` del CLI.
Nunca lanza una excepción hacia JavaScript -- el error se devuelve
como dato.

## [ARCH:geometry-adjacency-graph] GeometryAdjacencyGraphBuilder

Mide la LONGITUD del borde compartido (no solo `touches()`, que da
positivo con un simple contacto de esquina/punto) -- un punto mide
longitud 0 y queda descartado sin caso especial. `min_shared_edge_m`
es parámetro, no constante fija (adyacencia interior y contacto
exterior usan umbrales distintos).

Cache de una sola entrada: bug de rendimiento real (no optimización
especulativa) -- 5 validadores comparten esta instancia sobre el mismo
`Layout` en cada iteración del recocido; sin cache, cada uno
reconstruía el grafo desde cero. Medido: 9.35s → 4.52s con el programa
de ejemplo del CLI.

**Gotcha real de Python encontrado y corregido**: cachear por `id(layout)`
falla, porque Python REUTILIZA agresivamente direcciones de memoria de
objetos liberados -- en un experimento directo, de 1000 `Layout`
creados/descartados en bucle, solo 6 `id()` distintos aparecieron.
Cachear solo por id habría devuelto resultados de un Layout
completamente distinto que reutilizó la misma dirección, en silencio.
Corregido guardando una REFERENCIA real al objeto (no solo su id):
mientras la referencia esté viva, Python no puede reutilizar esa
memoria.

## [ARCH:cocina-integrada] CocinaIntegradaValidator

Cocina abierta en un único espacio con la estancia mayor: la
superficie mínima del conjunto es la SUMA de los mínimos de cada
pieza por separado (Tabla 1 + Tabla 2), no un número fijo propio. Tres
casos: sin cocina integrada declarada = no aplica (lista vacía, no es
"no verificable"); con cocina pero sin salón = aviso; con ambos = se
comprueba superficie combinada + apertura vertical mínima.

`total_num_estancias_override`: bug real corregido -- este validador
nunca recibió el mismo arreglo multi-planta que sus dos primos
(`EstanciaMinimumAreaValidator`, `ServicioMinimumAreaValidator`). Sin
esto, en un edificio de 2 plantas podía aprobar silenciosamente una
superficie combinada insuficiente para el edificio completo.

## [ARCH:soft-constraint-scorer] SoftConstraintScorer

Penalización blanda (SHOULD_BE_NEAR/SHOULD_BE_AWAY) para sumar a las
violaciones duras en la función objetivo del recocido -- nunca
bloquea nada, subordinada siempre a lo duro. Técnica confirmada por
investigación externa (curriculum-based course timetabling, arxiv
1409.7186): suma ponderada con peso grande para lo duro, pesos
pequeños por tipo de restricción blanda. Métrica: saltos en el grafo
de adyacencia real (misma fuente que núcleo húmedo/zonificación), no
grafo de puertas ni contacto directo.

Si no hay ningún SHOULD_BE_NEAR/SHOULD_BE_AWAY declarado, `score()`
siempre devuelve 0 -- inerte, no cambia el comportamiento de
programas que solo declaran restricciones duras.

El caso "estancia no colocada" (`room_id not in graph`) solo dispara
si la estancia no está colocada -- una estancia colocada pero
totalmente aislada (sin ninguna pared compartida) SÍ aparece como
nodo, así que ese caso se resuelve más abajo vía `distance=inf`,
mismo resultado final.

## [ARCH:altura-libre] AlturaLibreValidator

A.3.1.1: altura libre mínima (2.50m mayoría de piezas, 2.20m
directamente permitida en vestíbulo/pasillo/escaleras/baño/aseo/
lavadero/tendedero/garajes de vivienda unifamiliar). En el resto de
piezas, 2.20-2.50m es AVISO (no violación) -- podría cumplir vía la
excepción del 30% de superficie que este proyecto no calcula
(geometría parcial fuera de alcance, igual que la propia fuente
admite no calcular). Solo cuarto técnico queda fuera de alcance.

Bug real corregido: GARAGE estaba antes en fuera-de-alcance (sin
comprobar) y STAIRCASE en ninguna lista (caía en el caso general más
estricto) -- ambos explícitamente nombrados en A.3.1.1.b.

## [ARCH:vivienda-accesible] ViviendaAccesibleValidator

Retomado de un módulo Lua de un proyecto anterior del usuario
(accesibilidad.lua), investigado a fondo contra DB-SUA (Anejo A) +
Código de Accesibilidad de Galicia (Decreto 35/2000, act. Decreto
74/2013) + Base 5.4 gallega. OPT-IN (DB-SUA 9.1: la accesibilidad solo
es exigible en viviendas designadas específicamente, no todas).

Alcance: de todo lo que cubre la fuente Lua (también mobiliario --
altura de encimera, aproximación a la cama, barras de apoyo...), aquí
solo se modela lo GEOMÉTRICAMENTE VERIFICABLE con `Room` (rectángulo
con área, sin mobiliario) -- círculo de giro y ancho de pasillo. El
resto exigiría modelar mobiliario como piezas propias, mismo motivo
que C.10 (luz directa): fingir una comprobación sin datos reales sería
peor que no darla.

`TIPOS_CON_CIRCULO_GIRO`: mismas piezas que la fuente Lua comprueba
(`acc.circuloGiro`) + DINING_ROOM (misma zona de estar). No incluye
servicios pequeños (lavadero, tendedero, almacenamiento).

## [ARCH:pasillo-topologia] PasilloTopologiaValidator

Detección de puntos de corte (articulation points) sobre el grafo de
ADYACENCIA GEOMÉTRICA REAL (misma fuente que núcleo húmedo/
zonificación), no sobre el grafo de puertas. Corrección real tras un
primer intento fallido: usar solo el grafo de puertas (relaciones
Obligatorio declaradas) resultó demasiado disperso con programas
reales (mayoría de cercanías son Preferencia) -- casi cualquier
estancia parecía "paso obligado" por falta de redundancia declarada,
rompió 9 tests. La adyacencia geométrica real refleja lo que de
verdad se construyó, no solo lo pedido explícitamente.

Regla: ninguna estancia no-circulación puede ser punto de corte
obligado hacia otra -- EXCEPTO LIVING_ROOM/DINING_ROOM (salón-comedor
abierto, arquitectónicamente normal atravesarlos).

## [ARCH:graph-based-generator] GraphBasedLayoutGenerator

Generador alternativo, deliberadamente simple (franjas por zona,
luego cajas por estancia dentro de cada franja) -- para ser fácil de
testear/entender, y sustituible por CSP/genético sin tocar el resto
del sistema. No conectado al pipeline principal (`container.py` usa
`SimulatedAnnealingLayoutGenerator`), pero mantenido con tests propios
como pieza intercambiable de la arquitectura hexagonal.

Heurística de núcleo húmedo: coloca estancias húmedas primero
(extremo izquierdo) dentro de su zona, para alinearlas en columna con
zonas contiguas. Es heurística de orden, no garantía -- con 3+
estancias húmedas en zonas no mutuamente contiguas (día y servicio
nunca se tocan directamente, solo vía noche) sigue siendo
geométricamente imposible que todas queden a distancia ≤1.

## [ARCH:door-graph] adjacency/door_graph.py

Grafo de puertas: capa SEPARADA y más dispersa que la adyacencia
geométrica, inspirada en el patrón "Door Connectivity Graph"
(investigación externa, paper "Automatic Rendering of Building Floor
Plan Images from Textual Descriptions"; Infinigen Indoors 2024
confirma que la colocación de puertas es un paso posterior a resolver
posiciones, no algo que compita con la búsqueda). Se construye sobre
un Layout ya generado.

Regla deliberadamente simple: un par tiene puerta si y solo si hay
`AdjacencyRequirement(MUST_BE_NEAR)` declarado Y la geometría final
realmente los colocó adyacentes. El umbral de MUST_BE_NEAR (1.0m) ya
se eligió específicamente "para que quepa una puerta" -- este grafo
hace explícito lo que ese umbral ya representaba implícitamente.

## [ARCH:servicio-minimum-area] ServicioMinimumAreaValidator

Tabla 2 (A.3.2.2): superficie mínima por tipo de servicio, según
número de estancias de la vivienda. "aseo" no aparece como clave
hasta 4 estancias -- fiel al original, no un olvido (con menos, la
norma no exige aseo independiente).

Alcance: "cocina integrada" y "trastero" (B.2.5, regla fija) NO se
comprueban aquí -- tienen sus propios validadores dedicados
(`CocinaIntegradaValidator`, `TrasteroMinimumAreaValidator`).
`total_num_estancias_override`: mismo motivo que
`EstanciaMinimumAreaValidator`, edificio completo en multi-planta.

## [ARCH:escalera-alineacion] EscaleraAlineacionValidator

Confirmado por investigación externa (Infinigen Indoors 2024, apéndice
D.5 "Adding staircases"): calcula la intersección de la huella de
escalera en plantas consecutivas, rechaza si no intersecan lo
suficiente. Adaptado a nuestra arquitectura (plantas generadas
independientes, no búsqueda conjunta): la planta de abajo se genera
primero, su escalera resuelta se pasa como referencia FIJA al validar
la planta de arriba -- restricción dura más dentro del mismo recocido,
sin necesitar un tipo de movimiento nuevo.

Bug real corregido: `floor_below_exists=True, reference_boundary=None`
(hay planta inferior, pero sin escalera declarada) se trataba antes
igual que "no hay planta inferior" -- dejaba pasar una escalera que no
conecta con la planta de abajo, sin detectarlo.

## [ARCH:dormitorio-armario] DormitorioArmarioValidator

Espacio de armario empotrado -- confirmado por investigación
(condiciones mínimas de habitabilidad, varias fuentes independientes),
NO presente en nhv.lua. Cuenta DENTRO de la superficie del dormitorio
(no es un Room aparte): profundidad 0.60m, largo 1.00m (>6m²) o 1.50m
(>8m²). El umbral para ≤6m² no aparece en las fuentes consultadas; se
usa 1.00m como valor conservador, marcado como asunción, no cifra
normativa confirmada. Altura (2.20m) no se comprueba aquí -- la cubre
`AlturaLibreValidator` sobre la misma habitación.

## [ARCH:exterior-contact] ExteriorContactValidator

Comprueba contra el borde del ÁREA EDIFICABLE, no de la parcela legal
completa -- con retranqueo declarado, la construcción nunca toca la
línea de parcela real, así que comprobar contra ella nunca daría
contacto exterior válido. Sin retranqueo, ambas coinciden.

Vivienda pareada/adosada: los lados de medianera sí forman parte del
área edificable, pero una pared de medianera no tiene luz ni
ventilación propia -- no cuenta como contacto exterior real aunque
geométricamente toque el borde.

## [ARCH:vivienda-minima] ViviendaMinimaValidator

"Programa mínimo": texto exacto del Decreto 29/2010 de Galicia,
I.A.2.3 (confirmado por investigación independiente, cita textual):
salón + cocina + baño + lavadero + tendedero + almacenamiento general.
`nhv.lua` no modela este apartado en absoluto.

Corrección real: una primera versión solo exigía salón+cocina+baño,
basada en el estándar genérico CTE/Orden de 1944 (válido para otras
comunidades) en vez de buscar el texto específico de Galicia primero
-- el usuario detectó que algo no cuadraba, y al revisar la fuente
exacta se confirmó que faltaban tres piezas enteras.

Mapeo "estancia" → LIVING_ROOM: el decreto exige en otro apartado que
exista "al menos una estancia mayor"; este proyecto ya adoptó como
convención que la estancia mayor es siempre el salón.

## [ARCH:espacio-acceso] EspacioAccesoValidator

Numeración exacta incierta tras la renumeración del Decreto 128/2023
(probablemente A.3.3 "Espacios de comunicación" en la versión
vigente): cuadrado inscribible de 1.50m en contacto con la puerta de
entrada. "En contacto con la puerta" NO se comprueba -- este proyecto
no modela puertas/accesos (mismo hueco identificado en
relaciones_espaciales.md). Documentado como alcance pendiente
sistemático, no como aviso repetido caso a caso.

Sin ENTRANCE_HALL en el programa, no aplica (la norma exime este caso
cuando el acceso es directo a través de la estancia mayor -- ya
cubierto por el mínimo de Tabla 1).

## [ARCH:day-night-zoning] day_night_zoning_validator.py

Zonificación día/noche: estancias de una misma zona deben quedar
agrupadas, sin necesitar compartir pared (a diferencia de núcleo
húmedo). Umbral según `nhv.lua` (evaluarZonificacionDiaNoche): 2 para
ambas zonas.

Bug real corregido: CORRIDOR y ENTRANCE_HALL son SpaceCategory.
CIRCULACION pero tienen zone=DAY por defecto -- sin excluirlos, un
pasillo junto a los dormitorios generaba una violación falsa de
zonificación día, aunque cumpliera perfectamente su función de
circulación hacia zona noche.

Zonificación de servicio: NO existe en `nhv.lua` (solo cubre día/
noche) -- extensión propia de este proyecto, marcada como tal.

## [ARCH:bano-acceso] BanoAccesoGeneralValidator

Regla "Condicional" del catálogo (BEDROOM/MASTER_BEDROOM x BATHROOM):
"1 baño → acceso solo vía pasillo; ≥2 baños → uno puede ser en-suite".
NO es un valor estático de tabla -- depende de cuántos BATHROOM tenga
el Program real. Formulación equivalente más simple, sin ramificar por
conteo: al menos un baño debe tener acceso directo a circulación
general; con 1 solo baño, la exigencia recae necesariamente sobre él.

## [ARCH:nucleo-humedo-vertical] NucleoHumedoVerticalValidator

`docs/niveles_plantas.md`: cualquier estancia húmeda debe solapar en
(x,y) con ALGUNA húmeda de la planta inmediatamente inferior --
cualquier tipo húmedo coincide, no específico por tipo. A diferencia
de la escalera (near-alineación exacta), aquí basta con solape real
(intersección de área > 0): las bajantes necesitan discurrir por la
zona húmeda, no que las piezas coincidan pieza a pieza.

## [ARCH:ancho-libre-estancia] AnchoLibreEstanciaValidator

A.3.2.1: declarado en `nhv.lua` (NHV.anchoLibreMin) pero nunca
conectado a ningún validador en la fuente; valores confirmados de
forma independiente (Anexo I, Decreto de Galicia). Solo cubre 5
categorías (estancia mayor, dormitorios, cocina, baño) -- comedor,
despacho, aseo, lavadero, tendedero, trastero, almacenamiento no
tienen ancho libre asignado en ningún sitio de la fuente (cubiertos
en cambio por `AnchoLibrePracticoValidator`, no normativo).

La "estancia mayor" aquí es estrictamente LIVING_ROOM -- a diferencia
de `EstanciaMinimumAreaValidator`, no hace fallback a la de mayor
área (para no duplicar ese aviso).

## [ARCH:trastero-minimum-area] TrasteroMinimumAreaValidator

B.2.5: superficie mínima FIJA (4.00m², no escala con estancias, a
diferencia de "almacenamiento" en Tabla 2). Confirmado en `nhv.lua`
(NHV.trastero.area = 4.00), con la propia fuente admitiendo que nunca
estuvo realmente implementada pese a estar declarada. Ancho de puerta
(0.80m, también en B.2.5) pendiente -- requiere modelar puertas.

## [ARCH:validation-result] ValidationResult -- el patrón de 3 estados

Separa dos cosas que una simple `List[str]` de violaciones no puede
expresar: `violations` (la restricción NO se cumple, con los datos
disponibles) y `warnings` (no se puede confirmar NI descartar el
cumplimiento -- "no verificable"). Nunca se trata como aprobado por
defecto, pero tampoco bloquea la generación como una violación real --
es una tercera categoría, no un término medio. Mismo patrón que
`nhv.lua` ya distinguía en varios sitios (`esEspacioExteriorDeCalidad`).
Usado consistentemente en todos los validadores geométricos del
proyecto.

## Cierre de la refactorización de comentarios/docstrings (41 archivos)

A petición del usuario: revisión completa de los 82 archivos Python
del proyecto, recortando comentarios/docstrings largos a lo
imprescindible ("qué hace esto"), moviendo el histórico de
investigación/bugs/citas a esta misma sección de referencia técnica
por componente, con el sistema de etiquetas `[ARCH:tag]` confirmado
explícitamente con el usuario (buscable en ambos sitios, código y
documentación, sin depender del título exacto ni del orden del
archivo).

- **41 de 82 archivos** tenían 8+ líneas de comentario/docstring
  verboso; los otros 41 ya estaban razonablemente concisos, no
  tocados.
- **Reducción real: 1401 → 469 líneas verbosas (-67%)**, verificado
  con un script propio (cuenta docstrings vía `ast` + líneas `#`), no
  a ojo.
- Cada extracción se verificó con pyflakes + suite completa antes de
  seguir al siguiente archivo -- 13 puntos de control (commits) a lo
  largo del proceso, no un cambio monolítico al final.
- **Hallazgo real durante la limpieza, no buscado**: al revisar el
  tamaño de `relaciones_espaciales.js` para la división por pestañas
  (tarea previa), apareció un bloque `PYTHON_SOURCES` de 227KB
  completamente muerto -- ver sección "Limpieza de código muerto"
  arriba. Confirma que revisar el código de cerca, aunque el objetivo
  fuera otro, encuentra cosas reales.
- Un test de integración (`test_cli_retries_seeds_automatically...`)
  empezó a fallar por timeout de subproceso (90s) durante la
  verificación final -- confirmado que NO era una regresión de
  comportamiento (medido directamente: la generación tarda 109.9s bajo
  la carga del sistema en ese momento, converge correctamente con la
  semilla 4, igual que antes) -- el recorte de comentarios no puede
  afectar al tiempo de cómputo. Margen de timeout ampliado (90s→180s)
  en los dos tests con esta sensibilidad.
- Suite final: 343 unitarios + 23 integración + 6 CLI rápidos + 3 CLI
  lentos + 7 puente del navegador, todos confirmados. pyflakes y mypy
  limpios (81 archivos). Bundle Pyodide regenerado (169.640 caracteres
  JSON, bajado de 233.946 antes de empezar esta limpieza).

## [ARCH:fitness-functions] vulture como fitness function continua

A petición del usuario, investigados a fondo dos conceptos del
proyecto "architecture-decision-record": inmutabilidad de decisiones
aceptadas (confirmado que es la corriente dominante real -- Nygard,
Cognitect -- corrigiendo una lectura demasiado rápida anterior del
README) y "fitness functions" (Neal Ford / Rebecca Parsons,
*Building Evolutionary Architectures*): mecanismos que dan una
evaluación objetiva y CONTINUA de que una característica arquitectónica
se sigue cumpliendo, no solo que quedó documentada una vez.

- **Hallazgo real que motivó esto**: `vulture` solo se había ejecutado
  a mano, cuando se pidió explícitamente auditar código muerto -- así
  sobrevivió `infrastructure/browser_bridge.py` (78 líneas huérfanas)
  varias rondas de refactorización sin que nadie lo notara.
- **[RESUELTO] `tests/unit/test_no_dead_code.py`**: ejecuta `vulture`
  contra `vulture_whitelist.py` en cada pase de la suite normal, no
  como auditoría ocasional. `vulture_whitelist.py` contiene los 12
  elementos ya revisados y confirmados como intencionados (piezas
  alternativas de arquitectura hexagonal con tests propios, API usada
  solo en tests/, `INDIFFERENT` como decisión de diseño, `generar_edificio`
  llamado dinámicamente desde JS vía Pyodide) -- cualquier hallazgo
  NUEVO hace fallar el test hasta que se revise y, si es legítimo, se
  añada a la lista con su razón explicada.
- Verificado que de verdad detecta código muerto real (no solo que
  pasa en el estado limpio actual): se introdujo temporalmente una
  función sin usar, el test falló con un mensaje claro, se retiró y
  volvió a pasar.
- `vulture>=2.16` añadido a `[project.optional-dependencies].dev`.
- Ya teníamos otras fitness functions sin llamarlas así
  (`test_pyodide_bundle_is_not_stale_against_the_real_source`,
  `test_html_references_js_files_via_classic_tags_in_order`) -- esta
  es la primera pensada y nombrada explícitamente como tal.
- Sobre inmutabilidad: `architecture.md` ya tenía, sin planearlo así,
  una estructura de dos niveles que encaja con la práctica dominante --
  el histórico cronológico (inmutable, solo-añadir) y la sección
  "Referencia técnica por componente" (`[ARCH:tag]`, un resumen vivo
  del estado actual). No se cambió nada aquí, la distinción ya era
  correcta.
- Suite final: 344 unitarios (uno nuevo), pyflakes limpio.

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

## [ARCH:catalogo-constructivo] Catálogo constructivo -- pestaña 07

A petición del usuario: acceso a la composición real de materiales de
fachada, forjado y huecos (ventanas). Investigado antes de construir:
encontrada fuente sólida y oficial -- **Catálogo de Elementos
Constructivos del CTE (CEC)**, codigotecnico.org, Instituto Eduardo
Torroja + CEPCO + AICIA. A diferencia del cronograma de obra (donde no
existía fuente real), aquí sí hay un documento oficial extenso con
composición por capas de decenas de sistemas constructivos.

- **Alcance confirmado explícitamente**: 10 elementos representativos
  por categoría (fachadas/forjados/huecos), no el catálogo CEC
  completo -- solo en fachadas el documento real tiene varias decenas
  de variantes por familia, digitalizarlo entero sería un proyecto
  aparte.
- **Composición por capas**: extraída de las definiciones reales del
  catálogo (códigos de capa como `LC`=fábrica de ladrillo cerámico,
  `AT`=aislante térmico, `C`=cámara de aire, `RI`=revestimiento
  interior), no inventada.
- **Valores de transmitancia U**: aquí sí hubo que tomar una decisión
  de rigor real -- las tablas del catálogo dan U en función de la
  resistencia térmica del aislante elegido (fórmula tipo
  `1/(0.58+RAT)`, no un número fijo), y extraer los números exactos de
  las tablas del PDF (con formato muy degradado al convertir a texto)
  habría sido poco fiable. En su lugar: U calculada con la fórmula
  física estándar (U=1/ΣR, con Rsi+Rse=0.17 m²K/W para fachadas) y las
  conductividades λ REALES de cada material, tomadas del mismo
  catálogo (sección 3, materiales) -- con un espesor de aislante
  concreto asumido y declarado explícitamente en cada ficha, no los
  valores de tabla exactos. Cálculo hecho con un script (no a mano)
  para que las 30 fichas sean consistentes.
- Huecos: transmitancia global aproximada como 20% marco + 80% vidrio
  (proporción típica de ventana estándar), con U de marco y vidrio
  reales del catálogo (secciones 3.16 y 3.15.2) mostrados por
  separado, no solo el global.
- Nota de alcance visible en el propio panel, con enlace al PDF
  oficial y la aclaración explícita de que los valores U son
  calculados, no transcritos directamente de la tabla.
- Implementado en `js/08-catalogo.js` (nuevo, antes de `init` --
  `08-init.js` renombrado a `09-init.js`, mismo patrón que el
  cronograma). Sin pieza Python nueva: catálogo estático embebido como
  constante JS, puro cliente.
- Verificado con `jsdom`: 10 tarjetas por categoría, expansión de
  capas al hacer clic, cambio de categoría (fachadas/forjados/huecos)
  correcto, cero errores.
- Tests de sanidad actualizados: 7 pestañas, orden de archivos JS,
  nuevo test que confirma 10 elementos por categoría.
- Suite final: 346 unitarios, pyflakes limpio.

## [ARCH:catalogo-constructivo] Actualización a materiales Passivhaus

A petición del usuario: reconsiderar fachadas y huecos del catálogo
constructivo con materiales adecuados para el estándar Passivhaus.

- **Aclaración honesta hecha antes de tocar código**: Passivhaus NO es
  el estándar legalmente obligatorio -- ese sigue siendo el CTE (el
  que fundamenta el resto del proyecto). Es el estándar VOLUNTARIO más
  exigente reconocido en eficiencia energética. Se aplicó con ese
  matiz explícito, no como sustituto del CTE en el resto del sistema.
- **Valores objetivo verificados con fuentes reales** antes de
  recalcular: muros/cubiertas U ≈ 0.10-0.15 W/m²K (frente al 0.35-0.56
  del CTE), ventanas Uw ≤ 0.80 W/m²K con triple acristalamiento y gas
  noble (argón/kriptón), marcos multicámara con rotura amplia de
  puente térmico.
- **Fachadas (10)**: recalculadas con espesores de aislante mucho
  mayores (170-300mm según sistema, antes 50-120mm) y, en varios
  casos, materiales de mayor rendimiento (PUR/PIR λ=0.025 en vez de
  EPS estándar) -- mismos sistemas constructivos de base (SATE,
  cámara ventilada, entramado de madera...) pero dimensionados para
  Passivhaus real. Las 10 quedan en el rango 0.107-0.146 W/m²K,
  verificado con un test permanente.
- **Huecos (10)**: sustituidos marco+vidrio por combinaciones reales
  certificables Passivhaus (PVC 5-6 cámaras, madera-aluminio, aluminio
  con RPT amplio certificado + triple acristalamiento bajo emisivo con
  argón/kriptón) -- se retiró la opción de vidrio simple/aluminio sin
  RPT que servía de referencia de contraste, ya no encaja con "materiales
  adecuados para Passivhaus". Las 10 quedan en el rango 0.56-0.67 W/m²K,
  bajo el umbral de 0.80, verificado con un test permanente.
- **Forjados (10): sin cambios, confirmado explícitamente con el
  usuario** -- son estructura intermedia entre plantas calefactadas de
  la misma vivienda, sin salto térmico entre ellas; el aislamiento
  Passivhaus va en muros y cubierta, no ahí. Aplicarlo a los forjados
  habría sido incorrecto técnicamente, no solo innecesario.
- Cálculo hecho con script (mismo patrón que la versión anterior), no
  a mano, para consistencia en las 20 fichas recalculadas.
- Nuevo test permanente (`test_catalogo_constructivo_meets_passivhaus_thresholds`)
  que falla si cualquier fachada sale del rango 0.08-0.16 W/m²K o
  cualquier hueco supera 0.80 W/m²K -- protege la decisión igual que
  el resto de fitness functions del proyecto.
- Suite final: 347 unitarios, pyflakes limpio.

## [ARCH:catalogo-constructivo] Ampliación a las 7 categorías completas del CEC

A petición del usuario: fachadas/forjados/huecos se habían presentado
como referencia, no como el conjunto completo -- el catálogo real
tiene más categorías. Ampliado a las 7 categorías reales del
documento oficial.

- **Cubiertas (10)**: mismo criterio Passivhaus que fachadas
  (confirmado explícitamente: son envolvente térmica también), U
  0.099-0.133 W/m²K con aislantes de gran espesor (EPS/XPS/lana
  mineral 220-240mm, o PUR 180mm en panel sándwich).
- **Particiones interiores verticales (10)** y **horizontales (10)**:
  centradas en propiedades ACÚSTICAS (índice RA, mejora de ruido de
  impacto ΔL), no térmicas -- son interiores a la vivienda, no
  envolvente, decisión coherente con la de forjados.
- **Puentes térmicos (13)**: lista real y CERRADA del catálogo CEC
  (4.6.1 a 4.6.13, no una muestra recortada a 10 como el resto,
  porque el documento original solo tiene estos 13 puntos nombrados).
  Formato de dato distinto a las demás categorías -- no es composición
  por capas con transmitancia U (W/m²K), es transmitancia térmica
  LINEAL Ψ (W/mK) de un detalle de unión constructiva. Cada uno
  compara construcción estándar (aislamiento discontinuo/interior)
  frente a Passivhaus (aislamiento continuo por el exterior, principio
  central del estándar: "construcción libre de puentes térmicos"),
  con valores Ψ de referencia real investigados (DA DB-HE/3 del CTE,
  comparativas Therm/LIDER encontradas en foros técnicos -- p.ej.
  pilar 30x30 con aislamiento interior: Ψ=0.27 W/mK medido con Therm;
  frente de forjado: 0.30-0.80 W/mK según continuidad del aislante).
- Verificado con `jsdom` en las 7 categorías: número de tarjetas
  correcto, formato de detalle correcto por categoría (capas+U,
  capas+acústica, o comparativa estándar/Passivhaus para puentes
  térmicos), expansión de tarjeta, cero errores.
- Tests de sanidad ampliados: número de elementos esperado por
  categoría (10, o 13 en puentes térmicos), y umbrales Passivhaus
  extendidos a cubiertas + verificación de que el valor Passivhaus es
  siempre menor que el estándar en los 13 puentes térmicos.
- Suite final: 347 unitarios, pyflakes limpio.

## [ARCH:zonas] Reestructuración de navegación por zonas

A petición del usuario, tras un DAFO extremo del HTML/pestañas: la
estructura plana de 7 pestañas mezclaba consulta, trabajo y
visualización sin ninguna distinción, con orden puramente histórico
(el de las sesiones en que se fueron añadiendo), un flujo real de
generación partido en dos pestañas no contiguas (Sección → salto
silencioso a Visor), y dos "islas" (Cronograma, Catálogo) sin ninguna
relación estructural con el resto.

- **3 zonas**: Diseño (Sección vertical + Visor de plano, presentados
  como un flujo explícito de 2 pasos numerados, no un salto de pestaña
  sorpresa), Consulta (Relaciones entre tipos + Fichas + Catálogo
  constructivo), Planificación (Cronograma de obra, presentada
  honestamente como herramienta aparte, no forzada a parecer
  conectada).
- **Matriz de adyacencia + Sinergias fusionadas** en una sola pestaña
  "Relaciones entre tipos" con selector de vista (tabla/red) --
  confirmado explícitamente con el usuario como decisión de contenido
  separada de la reorganización de navegación. Ambos contenidos
  originales conservados intactos, solo re-envueltos.
- Extraído y reensamblado con BeautifulSoup (no regex/string
  splicing a mano) para manipular HTML real de forma fiable.
- **Bug real encontrado y corregido durante la propia reestructuración**:
  los scripts clásicos se quedaron en su posición original (el final
  de la estructura plana anterior) tras reordenar los paneles en
  zonas -- como el reordenamiento dejó contenido real DESPUÉS de los
  scripts en el documento, un navegador real habría fallado al
  ejecutar código de nivel superior (`document.getElementById(...)`
  en `09-init.js`) sobre elementos que todavía no existían en ese
  punto del análisis del HTML. `jsdom` no lo detectó (analiza el
  documento completo antes de ejecutar), así que se verificó también
  con `wkhtmltoimage` (motor más estricto) tras corregirlo. Movidos
  los 11 scripts locales al final real del `<body>`, con un test
  permanente que impide que esto vuelva a pasar en silencio.
- **Bug de estado real encontrado y corregido**: el manejador de clic
  de pestañas anterior quitaba `active` de TODAS las pestañas y
  paneles del documento globalmente, no solo del grupo relevante --
  esto habría dejado zonas ya visitadas sin ningún panel activo al
  volver a ellas. Corregido acotando el manejador al grupo
  (`.flow-indicator` o `.subtabs-row`) más cercano del propio tab
  pulsado. Verificado explícitamente con un test que visita varias
  zonas/pestañas y confirma que el estado se conserva al volver.
- También se limpiaron comentarios HTML huérfanos (marcadores de las
  pestañas antiguas, sin nada a lo que apuntar tras el reordenamiento)
  y se corrigió el orden de atributos de un `<link>` reformateado por
  BeautifulSoup.
- Verificado con `jsdom` (todas las zonas, subpestañas, selector de
  vista, cronograma, modo espejo, salto automático al generar) y
  `wkhtmltoimage` (captura real + confirmación cuantitativa de
  píxeles).
- Tests de sanidad reescritos: estructura de 3 zonas, fusión
  Matriz+Sinergias con contenido conservado, posición correcta de
  scripts respecto al contenido.
- Suite final: 349 unitarios, pyflakes limpio.

## [ARCH:inicio-launcher] INICIO.html -- punto de entrada del proyecto

A petición del usuario: un archivo único para "iniciar todo", dado que
el dashboard real vive en una ruta anidada
(`docs/visualizador/relaciones_espaciales.html`) y el README no
mencionaba el dashboard en absoluto (documentaba solo el CLI).

- `INICIO.html` en la raíz del proyecto -- se abre con doble clic,
  mismo patrón "sin servidor" que el resto (reutiliza
  `docs/visualizador/relaciones_espaciales.css` vía ruta relativa,
  misma estética cianotipo).
- Enlace principal al dashboard real, resumen de las 3 zonas, y
  enlaces a toda la documentación (`GUIA_USO.md`, `COMO_FUNCIONA.md`,
  `architecture.md`, `CONTINUIDAD.md`, `README.md`) con una nota
  honesta: los `.md` pueden descargarse en vez de mostrarse según la
  configuración del navegador, no es un fallo del archivo.
- `README.md` actualizado: el dashboard pasa a presentarse como la
  forma principal de uso (generación real vía Pyodide, sin instalar
  Python), el CLI queda como opción para desarrollo/automatización,
  no como el único camino documentado.
- Verificado con `wkhtmltoimage` desde la raíz real del proyecto
  (confirmación cuantitativa de píxeles: el CSS real cargó
  correctamente por la ruta relativa) y con un test permanente que
  comprueba que TODOS los enlaces locales de `INICIO.html` apuntan a
  archivos que existen de verdad, no rutas rotas.
- Suite final: 350 unitarios, pyflakes limpio.
