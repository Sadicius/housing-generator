from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.trastero_minimum_area_validator import (
    TrasteroMinimumAreaValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_trastero_below_fixed_minimum_fails():
    trastero = Room(id="t", name="Trastero", room_type=RoomType.STORAGE_ROOM, dimensions=Dimensions(area_m2=3))
    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])

    violations = TrasteroMinimumAreaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "t" in violations[0]


def test_trastero_at_or_above_fixed_minimum_passes():
    trastero = Room(id="t", name="Trastero", room_type=RoomType.STORAGE_ROOM, dimensions=Dimensions(area_m2=4))
    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])

    assert TrasteroMinimumAreaValidator().validate(layout).violations == []


def test_almacenamiento_general_is_not_affected_by_trastero_rule():
    # "almacenamiento" (STORAGE) tiene su propio minimo en Tabla 2, que
    # escala con el numero de estancias -- no debe verse afectado por el
    # minimo fijo de trastero, aunque tenga menos de 4.00m2
    storage = Room(id="s", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=1))
    layout = Layout(lot=_dummy_lot(), rooms=[storage], zones=[])

    assert TrasteroMinimumAreaValidator().validate(layout).violations == []


def test_trastero_narrower_than_ancho_libre_fails():
    trastero = Room(id="t", name="Trastero", room_type=RoomType.STORAGE_ROOM, dimensions=Dimensions(area_m2=5))
    trastero.boundary = Boundary(polygon=box(0, 0, 1.2, 4.2))  # 1.2m de ancho, por debajo de 1.60m

    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])
    violations = TrasteroMinimumAreaValidator().validate(layout).violations

    assert any("ancho libre" in v for v in violations)


def test_trastero_meeting_ancho_libre_passes():
    trastero = Room(id="t", name="Trastero", room_type=RoomType.STORAGE_ROOM, dimensions=Dimensions(area_m2=5))
    trastero.boundary = Boundary(polygon=box(0, 0, 1.60, 3.2))

    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])
    result = TrasteroMinimumAreaValidator().validate(layout)

    assert result.violations == [] and result.warnings == []


def test_trastero_non_rectangular_is_unverifiable_not_violated():
    from shapely.geometry import Polygon
    l_shape = Polygon([(0, 0), (3, 0), (3, 1.5), (1.5, 1.5), (1.5, 3), (0, 3)])
    trastero = Room(id="t", name="Trastero", room_type=RoomType.STORAGE_ROOM, dimensions=Dimensions(area_m2=l_shape.area))
    trastero.boundary = Boundary(polygon=l_shape)

    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])
    result = TrasteroMinimumAreaValidator().validate(layout)

    assert not any("ancho libre" in v for v in result.violations)
    assert len(result.warnings) == 1
