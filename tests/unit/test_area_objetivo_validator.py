from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.area_objetivo_validator import (
    AreaObjetivoValidator,
    TOLERANCIA_AREA,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 30, 30)))


def _placed_with_declared_area(room_id, room_type, polygon, area_declarada) -> Room:
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=area_declarada))
    r.boundary = Boundary(polygon=polygon)
    return r


def test_reproduces_the_real_case_found_by_the_user():
    # caso real exacto de la captura de pantalla del usuario: un
    # Pasillo declarado a 4.0m2 se genero visiblemente mas grande que
    # un Dormitorio declarado a 8.0m2 -- aqui reproducido con un
    # Pasillo generado a 7.0m2 (75% de desviacion sobre su declarado).
    pasillo = _placed_with_declared_area("pasillo", RoomType.CORRIDOR, box(0, 0, 3.5, 2.0), area_declarada=4.0)
    layout = Layout(lot=_dummy_lot(), rooms=[pasillo], zones=[])

    result = AreaObjetivoValidator().validate(layout)
    assert len(result.violations) == 1
    assert "NO normativo" in result.violations[0]


def test_within_tolerance_passes():
    # 10% de desviacion, dentro del +-15% acordado
    room = _placed_with_declared_area("r", RoomType.BEDROOM, box(0, 0, 4, 2.2), area_declarada=8.0)  # 8.8m2 generado
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert result.violations == []


def test_exactly_at_threshold_passes():
    area_declarada = 8.0
    area_generada = area_declarada * (1 + TOLERANCIA_AREA)
    room = _placed_with_declared_area("r", RoomType.BEDROOM, box(0, 0, 4, area_generada / 4), area_declarada=area_declarada)
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert result.violations == []


def test_just_over_threshold_fails():
    area_declarada = 8.0
    area_generada = area_declarada * (1 + TOLERANCIA_AREA) + 0.5
    room = _placed_with_declared_area("r", RoomType.BEDROOM, box(0, 0, 4, area_generada / 4), area_declarada=area_declarada)
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert len(result.violations) == 1


def test_deviation_below_target_also_fails_not_just_above():
    # la desviacion importa en ambos sentidos -- una estancia MUCHO
    # mas pequeña que lo declarado tambien es una discrepancia real
    room = _placed_with_declared_area("r", RoomType.BEDROOM, box(0, 0, 2, 2), area_declarada=12.0)  # 4m2 generado
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert len(result.violations) == 1


def test_applies_to_circulation_types_too():
    # el caso real que motivo esto era justo un CORRIDOR -- confirma
    # que no esta excluido como en otros validadores
    room = _placed_with_declared_area("r", RoomType.CORRIDOR, box(0, 0, 4, 4), area_declarada=4.0)  # 16m2 generado
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert len(result.violations) == 1


def test_unplaced_room_is_skipped_not_crashed():
    room = Room(id="r", name="r", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12))
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = AreaObjetivoValidator().validate(layout)
    assert result.violations == []
