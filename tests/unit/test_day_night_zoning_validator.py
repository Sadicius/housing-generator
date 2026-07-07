from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.day_night_zoning_validator import (
    build_day_zone_grouping_validator,
    build_night_zone_grouping_validator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _placed_room(room_id: str, room_type: RoomType, polygon) -> Room:
    room = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    room.boundary = Boundary(polygon=polygon)
    return room


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_day_zone_passes_when_rooms_are_within_two_walls_of_each_other():
    # living - dining - kitchen en fila: living a kitchen queda a distancia 2 (limite exacto)
    living = _placed_room("living", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    dining = _placed_room("dining", RoomType.DINING_ROOM, box(3, 0, 6, 3))
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(6, 0, 9, 3))

    layout = Layout(lot=_dummy_lot(), rooms=[living, dining, kitchen], zones=[])

    validator = build_day_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_day_zone_reports_violation_when_a_day_room_is_scattered_too_far():
    living = _placed_room("living", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    dining = _placed_room("dining", RoomType.DINING_ROOM, box(3, 0, 6, 3))
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(6, 0, 9, 3))
    study = _placed_room("study", RoomType.STUDY, box(9, 0, 12, 3))  # distancia 3 de living

    layout = Layout(lot=_dummy_lot(), rooms=[living, dining, kitchen, study], zones=[])

    validator = build_day_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations

    assert len(violations) == 1
    assert "living" in violations[0] and "study" in violations[0]


def test_night_zone_ignores_day_zone_rooms():
    bed1 = _placed_room("bed1", RoomType.MASTER_BEDROOM, box(0, 0, 3, 3))
    bed2 = _placed_room("bed2", RoomType.BEDROOM, box(3, 0, 6, 3))
    living_far_away = _placed_room("living", RoomType.LIVING_ROOM, box(50, 50, 53, 53))  # zona dia, ignorado aqui

    layout = Layout(lot=_dummy_lot(), rooms=[bed1, bed2, living_far_away], zones=[])

    validator = build_night_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_corridor_placed_near_bedrooms_does_not_falsely_violate_day_zone():
    # Regresion (encontrada en auditoria, corregida de raiz): CORRIDOR
    # tenia zone=DAY por defecto pese a ser SpaceCategory.CIRCULACION.
    # Ahora su zona por defecto es ZoneType.CIRCULATION (no DAY), asi que
    # ni siquiera hace falta el filtro de space_category para que este
    # caso pase -- se deja como defensa adicional, no como el mecanismo
    # principal.
    living = _placed_room("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    dining = _placed_room("dining", RoomType.DINING_ROOM, box(4, 0, 8, 5))
    bed1 = _placed_room("bed1", RoomType.BEDROOM, box(0, 10, 3, 13))
    corridor = _placed_room("corridor", RoomType.CORRIDOR, box(3, 10, 5, 13))  # junto al dormitorio

    layout = Layout(lot=_dummy_lot(), rooms=[living, dining, bed1, corridor], zones=[])

    validator = build_day_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_entrance_hall_placed_away_from_day_rooms_does_not_falsely_violate_day_zone():
    # Mismo caso, para ENTRANCE_HALL (tambien CIRCULACION; zona por
    # defecto ahora ZoneType.CIRCULATION, ya no DAY)
    living = _placed_room("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    hall = _placed_room("hall", RoomType.ENTRANCE_HALL, box(50, 50, 52, 52))  # muy lejos

    layout = Layout(lot=_dummy_lot(), rooms=[living, hall], zones=[])

    validator = build_day_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_circulation_zone_is_excluded_by_predicate_alone_without_space_category_filter():
    # Confirma el arreglo DE RAIZ: el predicado `room.zone == ZoneType.DAY`
    # ya excluye CIRCULATION sin ayuda del filtro de space_category,
    # porque CORRIDOR/ENTRANCE_HALL ya no llevan zone=DAY en absoluto.
    from housing_generator.domain.enums import ZoneType

    corridor = _placed_room("corridor", RoomType.CORRIDOR, box(50, 50, 52, 52))
    assert corridor.zone == ZoneType.CIRCULATION  # no DAY, no NIGHT, no SERVICE

    living = _placed_room("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living, corridor], zones=[])

    # el pasillo, aunque lejos, no aparece como violacion porque su zona
    # (CIRCULATION) nunca coincide con DAY -- no hace falta el filtro
    # adicional de space_category para que esto funcione
    validator = build_day_zone_grouping_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []
