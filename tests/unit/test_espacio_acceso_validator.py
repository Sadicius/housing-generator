from shapely.geometry import box, Polygon
from housing_generator.infrastructure.algorithms.constraints.espacio_acceso_validator import (
    EspacioAccesoValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def test_no_entrance_hall_does_not_apply_no_violations_no_warnings():
    # acceso directo por la estancia mayor -- exento explicitamente por
    # la propia norma, no es "no verificable"
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = EspacioAccesoValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_entrance_hall_too_small_for_square_fails():
    hall = Room(id="hall", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=1.5))
    hall.boundary = Boundary(polygon=box(0, 0, 1.0, 1.5))  # 1.0m de ancho, no admite cuadrado de 1.50m

    layout = Layout(lot=_dummy_lot(), rooms=[hall], zones=[])
    violations = EspacioAccesoValidator().validate(layout).violations

    assert len(violations) == 1
    assert "hall" in violations[0]


def test_entrance_hall_admitting_square_passes():
    hall = Room(id="hall", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=3))
    hall.boundary = Boundary(polygon=box(0, 0, 1.5, 2.0))

    layout = Layout(lot=_dummy_lot(), rooms=[hall], zones=[])
    result = EspacioAccesoValidator().validate(layout)

    assert result.violations == [] and result.warnings == []


def test_unplaced_entrance_hall_is_skipped():
    hall = Room(id="hall", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=3))
    layout = Layout(lot=_dummy_lot(), rooms=[hall], zones=[])

    result = EspacioAccesoValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_non_rectangular_entrance_hall_is_a_warning_not_violation():
    l_shape = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])
    hall = Room(id="hall", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=l_shape.area))
    hall.boundary = Boundary(polygon=l_shape)

    layout = Layout(lot=_dummy_lot(), rooms=[hall], zones=[])
    result = EspacioAccesoValidator().validate(layout)

    assert result.violations == []
    assert len(result.warnings) == 1


def test_other_room_types_are_ignored():
    kitchen = Room(id="k", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=3))
    kitchen.boundary = Boundary(polygon=box(0, 0, 1.0, 3.0))  # muy estrecha, pero no es ENTRANCE_HALL

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen], zones=[])
    result = EspacioAccesoValidator().validate(layout)

    assert result.violations == [] and result.warnings == []
