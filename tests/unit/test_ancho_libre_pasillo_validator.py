from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_pasillo_validator import (
    AnchoLibrePasilloValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_corridor_below_1_meter_fails():
    corridor = Room(
        id="c",
        name="Pasillo",
        room_type=RoomType.CORRIDOR,
        dimensions=Dimensions(area_m2=3),
    )
    corridor.boundary = Boundary(polygon=box(0, 0, 0.85, 4.0))

    layout = Layout(lot=_dummy_lot(), rooms=[corridor], zones=[])
    violations = AnchoLibrePasilloValidator().validate(layout).violations

    assert len(violations) == 1
    assert "c" in violations[0]


def test_corridor_at_1_meter_passes():
    corridor = Room(
        id="c",
        name="Pasillo",
        room_type=RoomType.CORRIDOR,
        dimensions=Dimensions(area_m2=4),
    )
    corridor.boundary = Boundary(polygon=box(0, 0, 1.00, 4.0))

    layout = Layout(lot=_dummy_lot(), rooms=[corridor], zones=[])
    assert AnchoLibrePasilloValidator().validate(layout).violations == []


def test_non_corridor_rooms_are_ignored():
    bath = Room(
        id="b",
        name="Bano",
        room_type=RoomType.BATHROOM,
        dimensions=Dimensions(area_m2=3),
    )
    bath.boundary = Boundary(
        polygon=box(0, 0, 0.5, 6.0)
    )  # estrecho, pero no es pasillo

    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])
    assert AnchoLibrePasilloValidator().validate(layout).violations == []
