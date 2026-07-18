from typing import List
from housing_generator.application.ports.adjacency_graph_builder_port import (
    AdjacencyGraphBuilderPort,
)
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
)
from housing_generator.domain.enums import ZoneType, SpaceCategory

# Ver [ARCH:day-night-zoning].
ZONA_DIA_MAX_DISTANCE = 2
ZONA_NOCHE_MAX_DISTANCE = 2


# Excluye circulacion (CORRIDOR/ENTRANCE_HALL): sirve a varias zonas a
# la vez, no debe atraparse en la agrupacion de una sola. Ver [ARCH:day-night-zoning].
def _is_non_circulation_in_zone(zone: ZoneType):
    return (
        lambda room: room.zone == zone
        and room.space_category != SpaceCategory.CIRCULACION
    )


def build_day_zone_grouping_validator(
    graph_builder: AdjacencyGraphBuilderPort,
    max_distance: int = ZONA_DIA_MAX_DISTANCE,
) -> GroupingConstraintValidator:
    return GroupingConstraintValidator(
        graph_builder=graph_builder,
        predicate=_is_non_circulation_in_zone(ZoneType.DAY),
        max_distance=max_distance,
        label="zona dia",
    )


def build_night_zone_grouping_validator(
    graph_builder: AdjacencyGraphBuilderPort,
    max_distance: int = ZONA_NOCHE_MAX_DISTANCE,
) -> GroupingConstraintValidator:
    return GroupingConstraintValidator(
        graph_builder=graph_builder,
        predicate=_is_non_circulation_in_zone(ZoneType.NIGHT),
        max_distance=max_distance,
        label="zona noche",
    )


def build_day_night_zoning_validators(
    graph_builder: AdjacencyGraphBuilderPort,
) -> List[GroupingConstraintValidator]:
    """Conveniencia: las dos validaciones juntas, en una lista."""
    return [
        build_day_zone_grouping_validator(graph_builder),
        build_night_zone_grouping_validator(graph_builder),
    ]


# Zonificacion de servicio: extension propia, no en nhv.lua. Ver
# [ARCH:day-night-zoning].
ZONA_SERVICIO_MAX_DISTANCE = 2


def build_service_zone_grouping_validator(
    graph_builder: AdjacencyGraphBuilderPort,
    max_distance: int = ZONA_SERVICIO_MAX_DISTANCE,
) -> GroupingConstraintValidator:
    return GroupingConstraintValidator(
        graph_builder=graph_builder,
        predicate=_is_non_circulation_in_zone(ZoneType.SERVICE),
        max_distance=max_distance,
        label="zona servicio",
    )
