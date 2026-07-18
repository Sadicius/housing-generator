from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.vivienda_accesible_validator import (
    ViviendaAccesibleValidator,
    CIRCULO_GIRO_ACCESIBLE_M,
    PASILLO_ACCESIBLE_ANCHO_M,
    TIPOS_CON_CIRCULO_GIRO,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon) -> Room:
    r = Room(
        id=room_id,
        name=room_id,
        room_type=room_type,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    r.boundary = Boundary(polygon=polygon)
    return r


def test_inactive_by_default_produces_no_violations_even_when_room_is_too_small():
    # OPT-IN: por defecto (activo=False), ni siquiera una estancia
    # claramente insuficiente para el circulo de giro debe generar avisos
    dormitorio = _placed(
        "dorm", RoomType.BEDROOM, box(0, 0, 2.5, 2.5)
    )  # < 1.50m no, pero probemos mas pequeno
    dormitorio_pequeno = _placed("dorm2", RoomType.BEDROOM, box(0, 0, 1.0, 3.0))
    layout = Layout(lot=_dummy_lot(), rooms=[dormitorio, dormitorio_pequeno], zones=[])

    result = ViviendaAccesibleValidator(activo=False).validate(layout)
    assert result.violations == [] and result.warnings == []


def test_active_detects_room_too_small_for_turning_circle():
    # 1.0m x 3.0m -- el lado corto (1.0m) no admite el circulo de 1.50m
    dormitorio = _placed("dorm", RoomType.BEDROOM, box(0, 0, 1.0, 3.0))
    layout = Layout(lot=_dummy_lot(), rooms=[dormitorio], zones=[])

    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert len(result.violations) == 1
    assert "circulo de giro" in result.violations[0]


def test_active_passes_when_room_admits_the_circle():
    dormitorio = _placed("dorm", RoomType.BEDROOM, box(0, 0, 3.0, 3.0))
    layout = Layout(lot=_dummy_lot(), rooms=[dormitorio], zones=[])

    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert result.violations == []


def test_active_checks_corridor_width_more_strictly_than_the_general_1m():
    # 1.10m -- cumple el minimo GENERAL (1.00m, AnchoLibrePasilloValidator)
    # pero NO el de vivienda accesible (1.20m, Base 5.4)
    pasillo = _placed("pasillo", RoomType.CORRIDOR, box(0, 0, 4.0, 1.10))
    layout = Layout(lot=_dummy_lot(), rooms=[pasillo], zones=[])

    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert len(result.violations) == 1
    assert "1.20" in result.violations[0]


def test_active_corridor_at_1_2_passes():
    pasillo = _placed(
        "pasillo", RoomType.CORRIDOR, box(0, 0, 4.0, PASILLO_ACCESIBLE_ANCHO_M)
    )
    layout = Layout(lot=_dummy_lot(), rooms=[pasillo], zones=[])

    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert result.violations == []


def test_types_not_in_scope_are_ignored_even_when_small():
    # LAUNDRY no esta en TIPOS_CON_CIRCULO_GIRO -- una estancia
    # diminuta de este tipo no debe generar aviso de circulo de giro
    lavadero = _placed("lav", RoomType.LAUNDRY, box(0, 0, 1.0, 2.0))
    layout = Layout(lot=_dummy_lot(), rooms=[lavadero], zones=[])

    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert result.violations == []


def test_all_expected_types_are_in_scope():
    expected = {
        RoomType.LIVING_ROOM,
        RoomType.DINING_ROOM,
        RoomType.BEDROOM,
        RoomType.MASTER_BEDROOM,
        RoomType.KITCHEN,
        RoomType.BATHROOM,
    }
    assert TIPOS_CON_CIRCULO_GIRO == expected


def test_exactly_at_threshold_passes():
    room = _placed(
        "r",
        RoomType.LIVING_ROOM,
        box(0, 0, CIRCULO_GIRO_ACCESIBLE_M, CIRCULO_GIRO_ACCESIBLE_M),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert result.violations == []


def test_unplaced_room_is_skipped_not_crashed():
    room = Room(
        id="r", name="r", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)
    )
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ViviendaAccesibleValidator(activo=True).validate(layout)
    assert result.violations == []
