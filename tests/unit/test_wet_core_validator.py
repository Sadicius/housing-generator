from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.wet_core_validator import build_wet_core_validator
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


def test_wet_core_passes_when_all_wet_rooms_share_walls_with_each_other():
    # cocina, bano y lavadero mutuamente adyacentes (forman un nucleo compacto)
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room("bathroom", RoomType.BATHROOM, box(3, 0, 6, 3))   # toca cocina
    laundry = _placed_room("laundry", RoomType.LAUNDRY, box(0, 3, 6, 5))      # toca cocina Y bano
    living = _placed_room("living", RoomType.LIVING_ROOM, box(20, 20, 25, 25))  # lejos, no es humeda

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom, laundry, living], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_wet_core_reports_violation_when_a_wet_room_is_two_walls_away():
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room("bathroom", RoomType.BATHROOM, box(3, 0, 6, 3))  # toca cocina, distancia 1
    laundry = _placed_room("laundry", RoomType.LAUNDRY, box(6, 0, 9, 3))    # toca bano, pero cocina queda a distancia 2

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom, laundry], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations

    assert len(violations) == 1
    assert "kitchen" in violations[0] and "laundry" in violations[0]


def test_wet_core_reports_violation_when_wet_rooms_are_disconnected():
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room("bathroom", RoomType.BATHROOM, box(50, 50, 53, 53))  # aislado del resto

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations

    assert len(violations) == 1
    assert "no estan conectadas" in violations[0]
