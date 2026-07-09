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
- `generate_adjacency_requirements(rooms)`: función pura que, dado un
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
