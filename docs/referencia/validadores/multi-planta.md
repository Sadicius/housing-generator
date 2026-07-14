# Validadores -- multi-planta

> Referencia técnica por componente -- extraído de `docs/historico/architecture.md` el 2026-07-14 al reorganizar la documentación por temas. El histórico cronológico completo (por qué se tomó cada decisión, en qué sesión) sigue en `docs/historico/architecture.md`; aquí solo vive la referencia consolidada, agrupada por tema.

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
