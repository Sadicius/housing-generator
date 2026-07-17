from typing import Callable, List, Tuple
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.enums import ZoneType, SpaceCategory

# Ver [ARCH:day-night-zoning].
ZONA_DIA_MAX_DISTANCE = 2
ZONA_NOCHE_MAX_DISTANCE = 2

# Excluye circulacion (CORRIDOR/ENTRANCE_HALL): sirve a varias zonas a
# la vez, no debe atraparse en la agrupacion de una sola. Ver [ARCH:day-night-zoning].
def _is_non_circulation_in_zone(zone: ZoneType):
    return lambda room: room.zone == zone and room.space_category != SpaceCategory.CIRCULACION


def zone_grouping_predicates() -> List[Tuple[Callable[[Room], bool], str]]:
    """Los 3 predicados dia/noche/servicio, expuestos para que otros
    consumidores (el incentivo de proximidad de
    `PerimeterCoreLayoutGenerator`) midan EXACTAMENTE lo mismo que
    estos validadores duros -- una sola definicion, sin duplicar el
    predicado y arriesgar que diverjan. Ver [ARCH:day-night-zoning],
    [ARCH:perimeter-core-layout-generator]."""
    return [
        (_is_non_circulation_in_zone(ZoneType.DAY), "zona dia"),
        (_is_non_circulation_in_zone(ZoneType.NIGHT), "zona noche"),
        (_is_non_circulation_in_zone(ZoneType.SERVICE), "zona servicio"),
    ]


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
