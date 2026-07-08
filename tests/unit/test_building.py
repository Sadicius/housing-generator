from shapely.geometry import box
from housing_generator.domain.entities.building import Building
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType, NivelPlanta


def _lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 10, 10)))


def _layout(placed: bool = True) -> Layout:
    room = Room(id="r", name="r", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=10))
    if placed:
        room.boundary = Boundary(polygon=box(0, 0, 3, 3))
    return Layout(lot=_lot(), rooms=[room], zones=[])


def test_empty_building_is_not_complete():
    assert Building().is_complete is False


def test_ordered_levels_returns_only_present_levels_bottom_to_top():
    b = Building(floors={
        NivelPlanta.PLANTA_SUPERIOR: _layout(),
        NivelPlanta.SOTANO: _layout(),
        NivelPlanta.PLANTA_BAJA: _layout(),
    })
    assert b.ordered_levels() == [NivelPlanta.SOTANO, NivelPlanta.PLANTA_BAJA, NivelPlanta.PLANTA_SUPERIOR]


def test_level_below_skips_absent_intermediate_levels():
    # SEMISOTANO no existe en este Building -- PLANTA_BAJA debe devolver
    # SOTANO como "de abajo", no None ni fallar
    b = Building(floors={
        NivelPlanta.SOTANO: _layout(),
        NivelPlanta.PLANTA_BAJA: _layout(),
    })
    assert b.level_below(NivelPlanta.PLANTA_BAJA) == NivelPlanta.SOTANO


def test_level_below_of_lowest_present_level_is_none():
    b = Building(floors={NivelPlanta.SOTANO: _layout(), NivelPlanta.PLANTA_BAJA: _layout()})
    assert b.level_below(NivelPlanta.SOTANO) is None


def test_level_below_of_absent_level_is_none():
    b = Building(floors={NivelPlanta.PLANTA_BAJA: _layout()})
    assert b.level_below(NivelPlanta.BAJO_CUBIERTA) is None


def test_is_complete_false_if_any_floor_incomplete():
    b = Building(floors={
        NivelPlanta.PLANTA_BAJA: _layout(placed=True),
        NivelPlanta.PLANTA_SUPERIOR: _layout(placed=False),
    })
    assert b.is_complete is False


def test_is_complete_true_when_all_floors_complete():
    b = Building(floors={
        NivelPlanta.PLANTA_BAJA: _layout(placed=True),
        NivelPlanta.PLANTA_SUPERIOR: _layout(placed=True),
    })
    assert b.is_complete is True
