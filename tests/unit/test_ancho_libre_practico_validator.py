from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_practico_validator import (
    AnchoLibrePracticoValidator,
    ANCHO_LIBRE_PRACTICO_M,
    TIPOS_SIN_ANCHO_NORMATIVO,
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
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    r.boundary = Boundary(polygon=polygon)
    return r


def test_reproduces_the_real_case_found_by_the_user():
    # el caso real exacto de la captura de pantalla: "Almacen" de 3m2
    # generado como 2.49m x 0.49m -- cumple el area, pero 49cm de fondo
    # es inutilizable en la practica.
    almacen = _placed("almacen", RoomType.STORAGE, box(0, 0, 2.49, 0.49))
    layout = Layout(lot=_dummy_lot(), rooms=[almacen], zones=[])

    result = AnchoLibrePracticoValidator().validate(layout)
    assert len(result.violations) == 1
    assert "NO normativo" in result.violations[0]


def test_dining_room_too_thin_fails():
    # el otro caso real de la misma captura: "Comedor" 3.69m x 11.93m
    comedor = _placed("comedor", RoomType.DINING_ROOM, box(0, 0, 11.93, 0.9))
    layout = Layout(lot=_dummy_lot(), rooms=[comedor], zones=[])

    result = AnchoLibrePracticoValidator().validate(layout)
    assert len(result.violations) == 1


def test_wide_enough_room_passes():
    comedor = _placed("comedor", RoomType.DINING_ROOM, box(0, 0, 5, 2.8))
    layout = Layout(lot=_dummy_lot(), rooms=[comedor], zones=[])

    result = AnchoLibrePracticoValidator().validate(layout)
    assert result.violations == []


def test_exactly_at_threshold_passes():
    room = _placed("r", RoomType.LAUNDRY, box(0, 0, 3, ANCHO_LIBRE_PRACTICO_M))
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AnchoLibrePracticoValidator().validate(layout)
    assert result.violations == []


def test_types_already_covered_elsewhere_are_ignored():
    # LIVING_ROOM ya tiene su propio ancho normativo (AnchoLibreEstanciaValidator,
    # 2.70m) -- este validador no debe comprobarlo tambien (evitar
    # duplicar/contradecir), aunque este validador use un umbral distinto (1.20m)
    salon = _placed("salon", RoomType.LIVING_ROOM, box(0, 0, 10, 1.0))  # muy estrecho
    layout = Layout(lot=_dummy_lot(), rooms=[salon], zones=[])

    result = AnchoLibrePracticoValidator().validate(layout)
    assert result.violations == []  # no le corresponde a ESTE validador


def test_storage_room_trastero_already_covered_elsewhere_is_ignored():
    # STORAGE_ROOM (trastero) ya tiene su propio minimo normativo (B.2.5,
    # TrasteroMinimumAreaValidator, 1.60m) -- no se duplica aqui
    trastero = _placed("trastero", RoomType.STORAGE_ROOM, box(0, 0, 4, 0.5))
    layout = Layout(lot=_dummy_lot(), rooms=[trastero], zones=[])

    result = AnchoLibrePracticoValidator().validate(layout)
    assert result.violations == []


def test_all_nine_uncovered_types_are_included():
    expected = {
        RoomType.DINING_ROOM, RoomType.STUDY, RoomType.TOILET, RoomType.LAUNDRY,
        RoomType.DRYING_AREA, RoomType.STORAGE, RoomType.ENTRANCE_HALL,
        RoomType.GARAGE, RoomType.TECHNICAL_ROOM,
    }
    assert TIPOS_SIN_ANCHO_NORMATIVO == expected


def test_unplaced_room_is_skipped_not_crashed():
    room = Room(id="r", name="r", room_type=RoomType.STUDY, dimensions=Dimensions(area_m2=6))
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AnchoLibrePracticoValidator().validate(layout)
    assert result.violations == []
