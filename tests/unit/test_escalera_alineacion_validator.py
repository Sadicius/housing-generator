from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.escalera_alineacion_validator import (
    EscaleraAlineacionValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _stair(room_id, polygon) -> Room:
    r = Room(id=room_id, name=room_id, room_type=RoomType.STAIRCASE, dimensions=Dimensions(area_m2=polygon.area))
    r.boundary = Boundary(polygon=polygon)
    return r


def test_no_floor_below_at_all_means_not_applicable():
    # esta es la planta mas baja del edificio -- no hay nada con lo que alinear
    stair = _stair("s", box(0, 0, 1, 3))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    result = EscaleraAlineacionValidator(reference_boundary=None, floor_below_exists=False).validate(layout)
    assert result.violations == []


def test_floor_below_exists_without_staircase_but_this_floor_has_one_fails():
    # BUG REAL encontrado en auditoria: antes, este caso (SI hay planta
    # inferior, pero no declara escalera) se trataba igual que "no hay
    # planta inferior" -- dejaba pasar sin deteccion una escalera que no
    # arranca de ningun sitio. Confirmado que ahora SI se detecta.
    stair = _stair("s", box(0, 0, 1, 3))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    violations = EscaleraAlineacionValidator(
        reference_boundary=None, floor_below_exists=True,
    ).validate(layout).violations
    assert len(violations) == 1
    assert "no arranca" in violations[0]


def test_floor_below_exists_without_staircase_and_this_floor_also_has_none_passes():
    # ninguna de las dos plantas tiene escalera -- correcto, no es un error
    living = Room(id="l", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 4, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = EscaleraAlineacionValidator(reference_boundary=None, floor_below_exists=True).validate(layout)
    assert result.violations == []


def test_reference_exists_but_this_floor_has_no_staircase_fails():
    living = Room(id="l", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 4, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = EscaleraAlineacionValidator(reference_boundary=box(0, 0, 1, 3)).validate(layout)
    assert len(result.violations) == 1
    assert "continuidad" in result.violations[0]


def test_exact_same_footprint_passes():
    ref = box(2, 2, 3, 5)  # 1x3 = 3m2
    stair = _stair("s", box(2, 2, 3, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    result = EscaleraAlineacionValidator(reference_boundary=ref).validate(layout)
    assert result.violations == []


def test_slightly_offset_but_mostly_overlapping_footprint_passes():
    ref = box(2, 2, 3, 5)  # area 3
    # desplazada 0.05m en X -- solapa el 95% del area aprox
    stair = _stair("s", box(2.05, 2, 3.05, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    result = EscaleraAlineacionValidator(reference_boundary=ref).validate(layout)
    assert result.violations == []


def test_barely_overlapping_footprint_fails():
    ref = box(0, 0, 1, 3)  # area 3
    stair = _stair("s", box(0.8, 0, 1.8, 3))  # solo 20% de solape aprox
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    violations = EscaleraAlineacionValidator(reference_boundary=ref).validate(layout).violations
    assert len(violations) == 1


def test_completely_disjoint_footprint_fails():
    ref = box(0, 0, 1, 3)
    stair = _stair("s", box(10, 10, 11, 13))
    layout = Layout(lot=_dummy_lot(), rooms=[stair], zones=[])

    violations = EscaleraAlineacionValidator(reference_boundary=ref).validate(layout).violations
    assert len(violations) == 1
