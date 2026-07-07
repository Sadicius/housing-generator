from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
)

# Nucleo humedo: todas las piezas humedas (cocina, bano, lavadero...)
# deben compartir pared entre si (distancia 1 = pared compartida,
# confirmado por `nhv.lua`: bajantes cortos, ahorro real en fontaneria).
NUCLEO_HUMEDO_MAX_DISTANCE = 1


def build_wet_core_validator(graph_builder: AdjacencyGraphBuilderPort) -> GroupingConstraintValidator:
    """Fabrica el validador de nucleo humedo: primer caso concreto del
    mecanismo generico GroupingConstraintValidator."""
    return GroupingConstraintValidator(
        graph_builder=graph_builder,
        predicate=lambda room: room.is_wet,
        max_distance=NUCLEO_HUMEDO_MAX_DISTANCE,
        label="nucleo humedo",
    )
