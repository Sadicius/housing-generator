# Generador -- contacto exterior y envolvente (investigación, decisión cerrada)

> Referencia técnica -- documentado el 2026-07-17 a petición del usuario tras una sesión de auditoría completa del flujo (revisión de arquitecto) que encontró un bug real (`ParcelaRealValidator` perdía el retranqueo en `floor_lot`, ya corregido) y este hallazgo de fondo. No fue un bug puntual -- era una característica estructural del generador actual.
>
> **[DECIDIDO, 2026-07-18]** El rediseño "periferia hacia el centro" descrito abajo (`PerimeterCoreLayoutGenerator`) se implementó (Fases 0-3), se probó contra los 5 escenarios de aceptación, y confirmó tener su PROPIO bloqueo estructural (fragmentación del núcleo en piezas que solo tocan 1-2 estancias perimetrales, causando "paso obligado" -- 25 violaciones estables en 20.000 iteraciones × 5 semillas) sin resolver el problema original. Se decidió retirar ese código y mantener `BTreeLayoutGenerator` + las mitigaciones ya probadas (escalera compartida, preferencia de esquina, `retry_seeds=20`). Ver `docs/CONTINUIDAD.md`, sección "Decisiones de arquitectura tomadas", para el razonamiento completo de la decisión. Este documento se conserva íntegro como registro de la investigación (útil si se retoma en el futuro), no como pendiente activo.

## [ARCH:escalera-compartida] Escalera compartida entre plantas -- implementado, insuficiente por sí solo

**Problema de partida**: `EscaleraAlineacionValidator` exige ≥90% de
solape entre la huella de la escalera de cada planta, generadas de
forma INDEPENDIENTE (`GenerateBuildingUseCase` no hace búsqueda
conjunta). La búsqueda tenía que acertar por pura coincidencia una
posición que solapara lo suficiente con una planta ya resuelta, sin
ninguna guía hacia ese objetivo -- el usuario reportó haber probado
semillas/iteraciones muchas veces sin éxito para viviendas
multi-planta, y confirmó explícitamente que subir iteraciones no
ayudaba -- la verificación normativa de los validadores implicados se
hizo antes de tocar código, ambos (90% de solape, contacto exterior)
confirmados como asunciones de ingeniería correctamente etiquetadas,
no cifras normativas mal derivadas.

**Causa raíz real, confirmada, no asumida**: la función objetivo del
recocido simulado (`BTreeLayoutGenerator._evaluate`) cuenta
violaciones (`hard = len(violations)`), 0 o 1 por regla -- sin
magnitud. Un 89% de solape (falta un 1%) cuenta exactamente igual de
mal que un 0% de solape. Sin gradiente hacia "te estás acercando", la
búsqueda no tiene señal que la guíe, solo puede acertar por azar.
Confirmado contra la literatura real de floorplanning con simulated
annealing: los enfoques modernos penalizan por GRADO de violación
(área/distancia que falta), no por conteo binario -- ver fuentes al
final.

**Solución implementada** (`BTreeLayoutGenerator.reference_stair`,
opcional): cuando una planta hereda la posición de la escalera de la
planta de abajo, se fuerza su `aspect_ratio` EXACTO
(`btree_partition.force_aspect_ratio`, reaplicado tras CUALQUIER
mutación del árbol, sea cual sea el nodo que ahora represente la
escalera) y se traslada el paquete entero para que caiga exactamente
sobre la referencia -- 100% de solape GARANTIZADO por construcción,
no buscado. `EscaleraAlineacionValidator` pasa siempre en vez de ser
un objetivo probabilístico.

**Efecto secundario real, encontrado verificando con datos reales, no
asumido**: fijar la traslación a un punto externo hace perder el
centrado automático que el anclaje por `entrance_side` daba gratis al
resto de estancias -- el paquete puede quedar flotando lejos del
perímetro del solar, dificultando el contacto exterior de otras
piezas. Reproducido de forma aislada (generando SOLO la planta
superior, con una escalera de referencia sintética, sin depender de
que la planta baja también convergiera por su cuenta): 30/30 semillas
fallan por el mismo motivo exacto (`'master': 0 lados con contacto
exterior`), no por mala suerte -- geométricamente, con la escalera
anclada cerca del centro del solar (16×16, referencia en (6,6)-(8,8)),
el paquete de ~33m² compacto no alcanza ningún borde salvo que adopte
una forma muy alargada, que la búsqueda sin gradiente casi nunca
encuentra.

**Mitigación parcial añadida** (`STAIR_CORNER_PREFERENCE_WEIGHT`):
preferencia BLANDA (gradiente real por distancia, no conteo binario)
para que la planta que DEFINE la posición de la escalera (sin
`reference_stair`, la primera planta) prefiera colocarla cerca de una
esquina del área edificable -- práctica real confirmada en la
literatura de generación multi-planta ("stairs and elevators should
be placed only in corners bounded by two exterior walls"). Verificado
con datos reales tras añadirlo: sigue sin converger de forma fiable
en el escenario de 2 plantas del usuario (30 semillas, mayoría
siguen fallando) -- mitiga, no resuelve. Es una preferencia débil por
diseño (peso bajo a propósito, nunca debe dominar sobre las
restricciones duras reales), no una garantía.

Tests: 9 nuevos (`force_aspect_ratio`, anclaje exacto forma+posición,
supervivencia a mutaciones, preferencia de esquina con gradiente
real, inerte en plantas ya ancladas). Suite unitaria 467, pyflakes
limpio.

## [ARCH:contacto-exterior-arquitectura] Causa raíz de fondo: empaquetado "de dentro hacia fuera"

El generador actual (`BTreeLayoutGenerator`/`btree_partition.py`)
construye el paquete de estancias desde un origen abstracto (0,0) vía
el algoritmo de contorno de Chang & Chang (2000), y solo DESPUÉS
comprueba si el resultado, ya colocado y trasladado, toca el
perímetro del solar por casualidad (`ExteriorContactValidator`,
post-hoc). No hay ninguna noción de "esta estancia necesita fachada"
durante la construcción del árbol -- se descubre al validar, no antes.

Esto explica por qué el problema de contacto exterior reaparece en
varios contextos distintos de esta sesión y de sesiones anteriores
(no es exclusivo de la escalera compartida): el mismo patrón
"funciona a veces, falla otras, sin gradiente hacia mejorar" aparece
en los 20+ fallos de integración preexistentes encontrados al empezar
esta sesión (`kitchen`/`master`/`living`/`entrance` sin contacto
exterior en escenarios diversos).

### La alternativa real, confirmada contra la literatura

El "space allocation problem" (SAP) en arquitectura describe un
enfoque real usado en varios trabajos serios de generación de
plantas: **"periferia hacia el centro"** -- se inicializa la envolvente
completa del edificio y se TALLAN las estancias privadas/con
necesidad de fachada desde el borde HACIA DENTRO, dejando que el área
sin repartir forme naturalmente el núcleo público central (donde van
las piezas sin necesidad de exterior: baños, pasillos, trasteros --
coincide exactamente con `DEFAULT_MIN_EXTERIOR_SIDES=0` en
`domain/enums.py`, ya modelado en este proyecto pero no usado para
guiar la generación, solo para validarla después).

Esto GARANTIZA el contacto exterior por construcción para toda
estancia que lo necesite, en vez de perseguirlo por búsqueda ciega --
mismo principio que ya se aplicó para la escalera compartida (ver
[ARCH:escalera-compartida] arriba), pero aplicado a TODA la planta, no
solo a un elemento.

### Por qué GFLAN (ya citado en este proyecto) no sirve aquí directamente

GFLAN (arxiv 2512.16275, ya citado en `generate_building.py` para la
idea de derivar el rectángulo de partida del polígono real reducido)
usa un enfoque de deep learning (CNN + Transformer-GNN) para colocar
centroides de estancias y regresar sus rectángulos -- no hace
"periferia hacia el centro" (coloca por probabilidad aprendida en
TODA la envolvente, no desde el borde), necesita datos de
entrenamiento reales, y su propio paper reconoce explícitamente que
solo cubre una planta ("single-story, single-envelope setting"), sin
ninguna estrategia de escalera/circulación vertical. No es portable
a este proyecto (basado en reglas, sin red neuronal ni datos de
entrenamiento) ni resolvería multi-planta aunque lo fuera.

### Tensión real, documentada, relevante para el propio diseño

La literatura de eficiencia energética de edificios confirma una
tensión genuina entre compacidad y perímetro: formas cuadradas/cúbicas
minimizan la superficie exterior (mejor eficiencia térmica, menor
ratio superficie/volumen), mientras que formas más alargadas acercan
más superficie útil al perímetro (mejor luz natural/ventilación). El
algoritmo actual persigue formas compactas (técnica squarified
treemap, heredada del árbol de partición) precisamente porque eso
minimiza estancias como "tiras finas" -- pero esa misma compacidad es
lo que dificulta que TODO toque el exterior. No hay una respuesta
única "mejor" -- es un trade-off de diseño real que cualquier
solución futura (perímetro-primero u otra) tendría que decidir
explícitamente, no ignorar.

## Estado: decisión tomada, código retirado

"Periferia hacia el centro" SÍ se implementó (Fases 0-3:
`perimeter_carving.py`, `perimeter_core_partition.py`,
`perimeter_core_layout_generator.py`) y sí resolvió el contacto
exterior por construcción -- pero al conectarla al pipeline completo
(Fase 3) reveló un segundo problema estructural, distinto del
original: fragmentación del núcleo en piezas del residuo que solo
tocan 1-2 estancias perimetrales, causando "paso obligado"
(`PasilloTopologiaValidator`) de forma tan estable como el problema
que pretendía resolver. Confirmado con 5 semillas × 20.000
iteraciones (6-7x el presupuesto real de los tests): mismo número
exacto de violaciones siempre -- no es un problema de búsqueda que más
iteraciones fueran a resolver.

**Decisión (2026-07-18)**: no vale la pena mantener dos generadores
sin que ninguno resuelva el problema de fondo. Se retiró el código de
"periferia hacia el centro" del repositorio y se mantiene
`BTreeLayoutGenerator` con las mitigaciones ya probadas y en
producción (escalera compartida, preferencia de esquina,
`retry_seeds=20`). Si se retoma en el futuro, la investigación de este
documento (incluidas las fuentes de abajo) sigue siendo el punto de
partida correcto -- pero haría falta además una solución específica
para la redundancia de contacto núcleo-perímetro (candidata: garantizar
por construcción, a nivel de grafo, que ninguna estancia protegida sea
un punto de corte -- no solo por proximidad geométrica, que es lo que
`_grouping_proximity_penalty` ya resolvía sin ser suficiente).

### Fuentes (investigación real antes de proponer nada, no asumido)

- GFLAN: Generative Functional Layouts -- https://arxiv.org/html/2512.16275
- MULTI-STORY FLOOR PLAN GENERATION (EasyChair) -- https://easychair.org/publications/paper/C78B/open
- An approach to the multi-level space allocation problem in architecture using a hybrid evolutionary technique -- https://www.sciencedirect.com/science/article/abs/pii/S0926580513001027
- An Improved Simulated Annealing Algorithm With Excessive Length Penalty for Fixed-Outline Floorplanning (IEEE) -- https://ieeexplore.ieee.org/document/9032191/
- A compactness measure of sustainable building forms (Royal Society Open Science) -- https://royalsocietypublishing.org/doi/10.1098/rsos.181265
- BSD-061: The Function of Form -- Building Shape and Energy -- https://buildingscience.com/documents/insights/bsi-061-function-form-building-shape-and-energy
