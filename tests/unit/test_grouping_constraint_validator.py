from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.grouping_constraint_validator import (
    GroupingConstraintValidator,
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


def test_grouping_passes_when_all_members_within_threshold():
    a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed_room("b", RoomType.DINING_ROOM, box(3, 0, 6, 3))  # toca a "a"
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    validator = GroupingConstraintValidator(
        graph_builder=GeometryAdjacencyGraphBuilder(),
        predicate=lambda r: True,
        max_distance=1,
        label="test",
    )

    assert validator.validate(layout).violations == []


def test_grouping_reports_violation_when_distance_exceeds_threshold():
    a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed_room("b", RoomType.DINING_ROOM, box(3, 0, 6, 3))   # distancia 1 de a
    c = _placed_room("c", RoomType.KITCHEN, box(6, 0, 9, 3))       # distancia 1 de b, 2 de a

    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c], zones=[])

    validator = GroupingConstraintValidator(
        graph_builder=GeometryAdjacencyGraphBuilder(),
        predicate=lambda r: True,
        max_distance=1,
        label="test",
    )

    violations = validator.validate(layout).violations
    assert len(violations) == 1
    assert "'a'" in violations[0] and "'c'" in violations[0]


def test_grouping_reports_violation_when_members_are_disconnected():
    a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed_room("b", RoomType.DINING_ROOM, box(50, 50, 53, 53))  # no toca a "a"
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    validator = GroupingConstraintValidator(
        graph_builder=GeometryAdjacencyGraphBuilder(),
        predicate=lambda r: True,
        max_distance=3,
        label="test",
    )

    violations = validator.validate(layout).violations
    assert len(violations) == 1
    assert "no estan conectadas" in violations[0]


def test_grouping_ignores_rooms_not_matching_predicate():
    a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed_room("b", RoomType.BEDROOM, box(50, 50, 53, 53))  # lejos, pero no cumple el predicado
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    validator = GroupingConstraintValidator(
        graph_builder=GeometryAdjacencyGraphBuilder(),
        predicate=lambda r: r.room_type == RoomType.LIVING_ROOM,
        max_distance=1,
        label="test",
    )

    assert validator.validate(layout).violations == []


def test_max_distance_can_be_a_function_of_group_size():
    # max_distance como funcion del numero de miembros del grupo -- no
    # solo un entero fijo. Ver [ARCH:nucleo-humedo-distancia].
    a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed_room("b", RoomType.BEDROOM, box(3, 0, 6, 3))    # toca a, distancia 1
    c = _placed_room("c", RoomType.KITCHEN, box(6, 0, 9, 3))    # toca b, a queda a distancia 2

    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c], zones=[])

    # con 3 miembros, permite distancia 2; con menos, exige distancia 1
    validator = GroupingConstraintValidator(
        graph_builder=GeometryAdjacencyGraphBuilder(),
        predicate=lambda r: True,
        max_distance=lambda n: 2 if n >= 3 else 1,
        label="test",
    )
    assert validator.validate(layout).violations == []
