from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, SpaceCategory


def test_living_dining_bedrooms_and_study_are_estancia():
    for room_type in (
        RoomType.LIVING_ROOM,
        RoomType.DINING_ROOM,
        RoomType.BEDROOM,
        RoomType.MASTER_BEDROOM,
        RoomType.STUDY,
    ):
        room = Room(
            id="x", name="x", room_type=room_type, dimensions=Dimensions(area_m2=10)
        )
        assert room.space_category == SpaceCategory.ESTANCIA, room_type


def test_kitchen_bathroom_laundry_storage_are_servicio():
    for room_type in (
        RoomType.KITCHEN,
        RoomType.BATHROOM,
        RoomType.TOILET,
        RoomType.LAUNDRY,
        RoomType.DRYING_AREA,
        RoomType.STORAGE,
    ):
        room = Room(
            id="x", name="x", room_type=room_type, dimensions=Dimensions(area_m2=10)
        )
        assert room.space_category == SpaceCategory.SERVICIO, room_type


def test_entrance_hall_and_corridor_are_circulacion():
    for room_type in (RoomType.ENTRANCE_HALL, RoomType.CORRIDOR):
        room = Room(
            id="x", name="x", room_type=room_type, dimensions=Dimensions(area_m2=5)
        )
        assert room.space_category == SpaceCategory.CIRCULACION, room_type


def test_garage_and_technical_room_are_otros():
    for room_type in (RoomType.GARAGE, RoomType.TECHNICAL_ROOM):
        room = Room(
            id="x", name="x", room_type=room_type, dimensions=Dimensions(area_m2=15)
        )
        assert room.space_category == SpaceCategory.OTROS, room_type


def test_space_category_can_be_overridden():
    room = Room(
        id="x",
        name="Zona de estar en garaje reformado",
        room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=15),
        space_category=SpaceCategory.ESTANCIA,
    )
    assert room.space_category == SpaceCategory.ESTANCIA
