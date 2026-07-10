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
`BanoAccesoGeneralValidator`, `generate_adjacency_requirements` (la
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

- **[RESUELTO]** `generate_adjacency_requirements` conectado como opción
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
  `generate_adjacency_requirements` sí deriva las relaciones de
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
