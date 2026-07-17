from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.room_overlap_validator import (
    RoomOverlapValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def test_non_overlapping_rooms_pass():
    a = Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    a.boundary = Boundary(polygon=box(0, 0, 4, 4))
    b = Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=16))
    b.boundary = Boundary(polygon=box(4, 0, 8, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    assert RoomOverlapValidator().validate(layout).violations == []


def test_adjacent_rooms_sharing_only_an_edge_pass():
    # comparten exactamente el borde x=4 -- interseccion de area 0, no un solape real.
    a = Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    a.boundary = Boundary(polygon=box(0, 0, 4, 4))
    b = Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=16))
    b.boundary = Boundary(polygon=box(4, 0, 8, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    result = RoomOverlapValidator().validate(layout)
    assert result.violations == []


def test_overlapping_rooms_fail():
    a = Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    a.boundary = Boundary(polygon=box(0, 0, 4, 4))
    b = Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=16))
    b.boundary = Boundary(polygon=box(2, 2, 6, 6))  # se solapa en (2,2)-(4,4)

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    violations = RoomOverlapValidator().validate(layout).violations

    assert len(violations) == 1
    assert "a" in violations[0] and "b" in violations[0]


def test_three_rooms_only_overlapping_pair_reported():
    a = Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    a.boundary = Boundary(polygon=box(0, 0, 4, 4))
    b = Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=16))
    b.boundary = Boundary(polygon=box(2, 2, 6, 6))  # se solapa con a
    c = Room(id="c", name="C", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=16))
    c.boundary = Boundary(polygon=box(10, 10, 14, 14))  # no se solapa con nadie

    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c], zones=[])
    violations = RoomOverlapValidator().validate(layout).violations

    assert len(violations) == 1
    assert "a" in violations[0] and "b" in violations[0]


def test_unplaced_room_is_skipped():
    a = Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    a.boundary = Boundary(polygon=box(0, 0, 4, 4))
    b = Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=16))  # sin colocar

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    assert RoomOverlapValidator().validate(layout).violations == []
