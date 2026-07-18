from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, ZoneType


def test_room_gets_default_zone_from_type():
    room = Room(
        id="bed1",
        name="Dormitorio",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=12),
    )
    assert room.zone == ZoneType.NIGHT


def test_room_zone_can_be_overridden():
    room = Room(
        id="study",
        name="Despacho",
        room_type=RoomType.STUDY,
        dimensions=Dimensions(area_m2=10),
        zone=ZoneType.NIGHT,
    )
    assert room.zone == ZoneType.NIGHT


def test_kitchen_bathroom_laundry_are_wet_by_default():
    kitchen = Room(
        id="k",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=10),
    )
    bathroom = Room(
        id="b",
        name="Bano",
        room_type=RoomType.BATHROOM,
        dimensions=Dimensions(area_m2=5),
    )
    laundry = Room(
        id="l",
        name="Lavadero",
        room_type=RoomType.LAUNDRY,
        dimensions=Dimensions(area_m2=5),
    )
    assert kitchen.is_wet is True
    assert bathroom.is_wet is True
    assert laundry.is_wet is True


def test_living_room_and_bedroom_are_not_wet_by_default():
    living = Room(
        id="li",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=20),
    )
    bedroom = Room(
        id="be",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=12),
    )
    assert living.is_wet is False
    assert bedroom.is_wet is False


def test_is_wet_can_be_overridden_for_edge_cases():
    storage_with_drain = Room(
        id="st",
        name="Trastero con desague",
        room_type=RoomType.STORAGE,
        dimensions=Dimensions(area_m2=4),
        is_wet=True,
    )
    assert storage_with_drain.is_wet is True


def test_corridor_and_entrance_hall_default_to_circulation_zone_not_day():
    # Fix de raiz (auditoria): antes zone=DAY, dato falso para
    # circulacion que sirve a varias zonas a la vez.
    corridor = Room(
        id="c",
        name="Pasillo",
        room_type=RoomType.CORRIDOR,
        dimensions=Dimensions(area_m2=3),
    )
    hall = Room(
        id="h",
        name="Vestibulo",
        room_type=RoomType.ENTRANCE_HALL,
        dimensions=Dimensions(area_m2=4),
    )

    assert corridor.zone == ZoneType.CIRCULATION
    assert hall.zone == ZoneType.CIRCULATION
    assert corridor.zone != ZoneType.DAY
    assert hall.zone != ZoneType.DAY
