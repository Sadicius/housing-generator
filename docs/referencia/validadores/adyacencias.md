# Validadores -- adyacencias y topología

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

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

## [ARCH:type-adjacency-catalog] domain/services/type_adjacency_catalog.py

Generado programáticamente desde `docs/fuentes/relaciones_espaciales.md`, no
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
