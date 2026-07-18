from shapely.geometry import box, Polygon
from housing_generator.infrastructure.algorithms.constraints.dormitorio_armario_validator import (
    DormitorioArmarioValidator,
    armario_largo_minimo,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_armario_largo_minimo_thresholds():
    assert armario_largo_minimo(5.0) == 1.00
    assert armario_largo_minimo(7.0) == 1.00
    assert armario_largo_minimo(9.0) == 1.50


def test_bedroom_with_enough_space_passes():
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=9),
    )
    bed.boundary = Boundary(polygon=box(0, 0, 3, 3))  # 3x3, cabe 1.5x0.6 de sobra

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    result = DormitorioArmarioValidator().validate(layout)

    assert result.violations == []


def test_bedroom_too_narrow_for_wardrobe_fails():
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.MASTER_BEDROOM,
        dimensions=Dimensions(area_m2=9),
    )
    bed.boundary = Boundary(
        polygon=box(0, 0, 0.4, 22.5)
    )  # muy estrecho: 0.4m de ancho, no cabe 0.6m de fondo

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    result = DormitorioArmarioValidator().validate(layout)

    assert len(result.violations) == 1
    assert "bed" in result.violations[0]


def test_non_bedroom_rooms_are_ignored():
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=9),
    )
    living.boundary = Boundary(
        polygon=box(0, 0, 0.4, 22.5)
    )  # tan estrecho como el caso anterior

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    result = DormitorioArmarioValidator().validate(layout)

    assert result.violations == []


def test_non_rectangular_bedroom_is_unverifiable_not_violated():
    l_shape = Polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=l_shape.area),
    )
    bed.boundary = Boundary(polygon=l_shape)

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    result = DormitorioArmarioValidator().validate(layout)

    assert result.violations == []
    assert len(result.warnings) == 1


def test_unplaced_bedroom_is_skipped():
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=9),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])

    result = DormitorioArmarioValidator().validate(layout)
    assert result.violations == []
    assert result.warnings == []
