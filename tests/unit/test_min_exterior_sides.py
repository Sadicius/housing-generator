from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType


def test_living_room_requires_one_exterior_side_by_default():
    room = Room(id="x", name="x", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    assert room.min_exterior_sides == 1


def test_bathroom_requires_zero_exterior_sides_by_default():
    room = Room(id="x", name="x", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5))
    assert room.min_exterior_sides == 0


def test_drying_area_requires_one_exterior_side_unlike_laundry():
    laundry = Room(id="l", name="l", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=5))
    drying = Room(id="d", name="d", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=3))
    assert laundry.min_exterior_sides == 0
    assert drying.min_exterior_sides == 1


def test_min_exterior_sides_can_be_overridden():
    room = Room(
        id="x", name="x", room_type=RoomType.STORAGE_ROOM,
        dimensions=Dimensions(area_m2=4), min_exterior_sides=1,
    )
    assert room.min_exterior_sides == 1
