from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType


def test_living_room_requires_one_exterior_side_by_default():
    room = Room(
        id="x",
        name="x",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=16),
    )
    assert room.min_exterior_sides == 1


def test_bathroom_requires_zero_exterior_sides_by_default():
    room = Room(
        id="x", name="x", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)
    )
    assert room.min_exterior_sides == 0


def test_drying_area_requires_one_exterior_side_unlike_laundry():
    laundry = Room(
        id="l", name="l", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=5)
    )
    drying = Room(
        id="d",
        name="d",
        room_type=RoomType.DRYING_AREA,
        dimensions=Dimensions(area_m2=3),
    )
    assert laundry.min_exterior_sides == 0
    assert drying.min_exterior_sides == 1


def test_min_exterior_sides_can_be_overridden():
    room = Room(
        id="x",
        name="x",
        room_type=RoomType.STORAGE_ROOM,
        dimensions=Dimensions(area_m2=4),
        min_exterior_sides=1,
    )
    assert room.min_exterior_sides == 1


def test_garage_requires_zero_exterior_sides_by_default():
    # [RESUELTO] investigacion confirmada (Decreto 29/2010 + nhv.lua +
    # discusion real de arquitectos en foro): el contacto exterior de
    # GARAGE nunca estuvo respaldado por normativa de habitabilidad para
    # vivienda unifamiliar -- "garajes colectivos" (B.2.6) es de edificio
    # con varios vecinos, confirmado explicitamente que NO aplica a
    # unifamiliar ("no disponen de ninguno de ellos por tipologia").
    # nhv.lua tambien declara explicitamente no modelar "garajes de
    # viviendas unifamiliares". GARAGE ya es SpaceCategory.OTROS,
    # excluido de A.1.2 (iluminacion/ventilacion de piezas habitables) --
    # consistente con no exigir contacto exterior tampoco aqui.
    room = Room(
        id="g",
        name="Garaje",
        room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=15),
    )
    assert room.min_exterior_sides == 0


def test_garage_exterior_side_can_still_be_required_explicitly():
    # sigue siendo OPCIONAL por proyecto -- quien quiera exigirlo por
    # motivos practicos propios (acceso vehicular, aunque no sea
    # normativo de habitabilidad) puede declararlo explicitamente.
    room = Room(
        id="g",
        name="Garaje",
        room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=15),
        min_exterior_sides=1,
    )
    assert room.min_exterior_sides == 1
