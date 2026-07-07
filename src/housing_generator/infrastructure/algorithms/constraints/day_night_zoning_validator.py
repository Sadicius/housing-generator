from typing import List
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
)
from housing_generator.domain.enums import ZoneType, SpaceCategory

# Zonificacion dia/noche: las estancias de una misma zona deben quedar
# agrupadas en la planta, pero -- a diferencia del nucleo humedo -- NO
# hace falta que compartan pared entre si, solo que no queden dispersas.
# Umbral segun `nhv.lua` (evaluarZonificacionDiaNoche): 2 para ambas
# zonas. Sujeto a confirmacion/ajuste.
ZONA_DIA_MAX_DISTANCE = 2
ZONA_NOCHE_MAX_DISTANCE = 2

# BUG ENCONTRADO EN AUDITORIA: CORRIDOR y ENTRANCE_HALL son
# SpaceCategory.CIRCULACION pero tienen zone=DAY por defecto (ver
# DEFAULT_ROOM_ZONE). Sin esta exclusion, un pasillo colocado junto a
# los dormitorios (su funcion real en un diseno concreto) generaba una
# VIOLACION FALSA de zonificacion dia, por estar "lejos" de living/
# dining/kitchen -- aunque el pasillo este cumpliendo perfectamente su
# funcion de circulacion hacia la zona noche. La circulacion, por
# definicion, sirve a varias zonas a la vez; no debe quedar atrapada en
# la agrupacion de una sola.
def _is_non_circulation_in_zone(zone: ZoneType):
    return lambda room: room.zone == zone and room.space_category != SpaceCategory.CIRCULACION


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
    """Conveniencia: las dos validaciones juntas, en una lista -- lista para
    cuando se resuelva como se combinan varios validadores en el caso de uso."""
    return [
        build_day_zone_grouping_validator(graph_builder),
        build_night_zone_grouping_validator(graph_builder),
    ]


# Zonificacion de servicio: NO existe en nhv.lua (evaluarZonificacionDiaNoche
# solo cubre dia/noche) -- es una extension propia de este proyecto, no una
# regla portada de la fuente normativa. Se marca como tal, igual que
# `nhv.lua` distingue explicitamente sus propias heuristicas de diseno
# (PASIVO.factorHueco, PESOS_ORIENTACION...) de las reglas normativas.
# Umbral elegido igual al de dia/noche (2) por consistencia, ajustable.
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
