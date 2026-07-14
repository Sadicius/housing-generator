from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
)

# Nucleo humedo: todas las piezas humedas (cocina, bano, lavadero...)
# deben quedar cerca entre si (confirmado por `nhv.lua`: bajantes
# cortos, ahorro real en fontaneria). Sin fuente normativa que
# especifique un numero concreto (investigado contra CTE DB-HS 5,
# evacuacion de aguas -- da distancias METRICAS de tuberia dentro de
# un mismo cuarto humedo, nunca una distancia entre estancias
# distintas ni un umbral que varie segun cuantas humedas haya).
#
# Distancia GRADUADA segun el numero de humedas -- criterio de
# ingenieria confirmado explicitamente (NO normativo, mismo tipo de
# decision que AnchoLibrePractico/ProporcionMaxima), tras un
# diagnostico real: con 2 humedas, distancia 1 (pared compartida)
# convergia en el 80% de semillas probadas; con 3+ humedas, la MISMA
# exigencia (las 3 mutuamente a distancia 1, un "molinillo" geometrico
# mucho mas restrictivo) bajaba la convergencia a 7-20%. Relajado a
# distancia 2 a partir de 3 humedas -- sigue siendo "cerca" (maximo 1
# estancia de por medio), solo deja de exigir contacto directo mutuo
# entre las tres a la vez. Ver [ARCH:nucleo-humedo-distancia].
NUCLEO_HUMEDO_MAX_DISTANCE_DOS = 1
NUCLEO_HUMEDO_MAX_DISTANCE_TRES_O_MAS = 2


def _nucleo_humedo_max_distance(num_humedas: int) -> int:
    return NUCLEO_HUMEDO_MAX_DISTANCE_DOS if num_humedas <= 2 else NUCLEO_HUMEDO_MAX_DISTANCE_TRES_O_MAS


def build_wet_core_validator(graph_builder: AdjacencyGraphBuilderPort) -> GroupingConstraintValidator:
    """Fabrica el validador de nucleo humedo: primer caso concreto del
    mecanismo generico GroupingConstraintValidator."""
    return GroupingConstraintValidator(
        graph_builder=graph_builder,
        predicate=lambda room: room.is_wet,
        max_distance=_nucleo_humedo_max_distance,
        label="nucleo humedo",
    )
