from shapely.geometry import box, Polygon
from housing_generator.infrastructure.algorithms.constraints.escalera_ancho_libre_validator import (
    EscaleraAnchoLibreValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def test_staircase_narrower_than_minimum_fails():
    stair = Room(id="s", name="Escalera", room_type=RoomType.STAIRCASE, dimensions=Dimensions(area_m2=3))
    stair.boundary = Boundary(polygon=box(0, 0, 0.6, 5))  # 0.6m, por debajo de 0.80m

    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])
    violations = EscaleraAnchoLibreValidator().validate(layout).violations

    assert len(violations) == 1


def test_staircase_meeting_minimum_passes():
    stair = Room(id="s", name="Escalera", room_type=RoomType.STAIRCASE, dimensions=Dimensions(area_m2=4))
    stair.boundary = Boundary(polygon=box(0, 0, 0.80, 5))

    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])
    result = EscaleraAnchoLibreValidator().validate(layout)

    assert result.violations == [] and result.warnings == []


def test_other_room_types_are_ignored():
    corridor = Room(id="c", name="Pasillo", room_type=RoomType.CORRIDOR, dimensions=Dimensions(area_m2=2))
    corridor.boundary = Boundary(polygon=box(0, 0, 0.5, 4))  # estrecho, pero no es escalera

    layout = Layout(lot=_dummy_lot(), rooms=[corridor], zones=[])
    result = EscaleraAnchoLibreValidator().validate(layout)

    assert result.violations == [] and result.warnings == []


def test_non_rectangular_staircase_is_a_warning_not_violation():
    l_shape = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 3), (0, 3)])
    stair = Room(id="s", name="Escalera", room_type=RoomType.STAIRCASE, dimensions=Dimensions(area_m2=l_shape.area))
    stair.boundary = Boundary(polygon=l_shape)

    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])
    result = EscaleraAnchoLibreValidator().validate(layout)

    assert result.violations == []
    assert len(result.warnings) == 1


def test_unplaced_staircase_is_skipped():
    stair = Room(id="s", name="Escalera", room_type=RoomType.STAIRCASE, dimensions=Dimensions(area_m2=4))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    result = EscaleraAnchoLibreValidator().validate(layout)
    assert result.violations == [] and result.warnings == []
