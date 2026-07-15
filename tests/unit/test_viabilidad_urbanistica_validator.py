from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.viabilidad_urbanistica_validator import (
    ViabilidadUrbanisticaValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType, NivelPlanta


def _room(room_id, area, level=None) -> Room:
    return Room(id=room_id, name=room_id, room_type=RoomType.LIVING_ROOM,
                dimensions=Dimensions(area_m2=area), level=level)


def _lot(width=20, depth=20, **kwargs) -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, width, depth)), **kwargs)


def test_all_none_means_no_restrictions_at_all():
    program = Program(rooms=[_room("a", 1000)])  # area absurda, no importa: nada esta configurado
    lot = _lot()
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=5)
    assert result.violations == []


def test_edificabilidad_within_limit_passes():
    # parcela 20x20=400m2, edificabilidad 0.5 -> 200m2 de techo maximo
    program = Program(rooms=[_room("a", 150)])
    lot = _lot(coeficiente_edificabilidad=0.5)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert result.violations == []


def test_edificabilidad_exceeded_fails_with_real_numbers_in_message():
    # 400m2 parcela, edificabilidad 0.5 -> 200m2 maximo; declarado 250m2
    program = Program(rooms=[_room("a", 150), _room("b", 100)])
    lot = _lot(coeficiente_edificabilidad=0.5)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert len(result.violations) == 1
    assert "Edificabilidad superada" in result.violations[0]
    assert "250.0m²" in result.violations[0]
    assert "200.0m²" in result.violations[0]


def test_ocupacion_uses_the_largest_floor_not_always_ground_floor():
    # planta baja 80m2, planta superior 120m2 (voladizo) -- la estimacion
    # de huella debe usar la MAYOR (120m2), no siempre la baja
    program = Program(rooms=[
        _room("pb", 80, level=NivelPlanta.PLANTA_BAJA),
        _room("ps", 120, level=NivelPlanta.PLANTA_SUPERIOR),
    ])
    # 400m2 parcela, ocupacion 25% -> 100m2 maximo -- 120m2 (la superior) lo supera
    lot = _lot(ocupacion_maxima_pct=25)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=2)
    assert len(result.violations) == 1
    assert "Ocupación superada" in result.violations[0]
    assert "120.0m²" in result.violations[0]  # la mayor, no la de planta baja


def test_ocupacion_within_limit_passes():
    program = Program(rooms=[_room("pb", 80, level=NivelPlanta.PLANTA_BAJA)])
    lot = _lot(ocupacion_maxima_pct=25)  # 400m2 x 25% = 100m2 maximo, 80m2 declarado
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert result.violations == []


def test_altura_within_limit_passes():
    program = Program(rooms=[_room("a", 10)])
    lot = _lot(altura_maxima_plantas=3)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=2)
    assert result.violations == []


def test_altura_exceeded_fails():
    program = Program(rooms=[_room("a", 10)])
    lot = _lot(altura_maxima_plantas=2)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=3)
    assert len(result.violations) == 1
    assert "Altura superada" in result.violations[0]
    assert "3 plantas" in result.violations[0]
    assert "2 plantas" in result.violations[0]


def test_frente_minimo_within_limit_passes():
    program = Program(rooms=[_room("a", 10)])
    lot = _lot(width=20, depth=15, street_side="south", frente_minimo_m=15)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert result.violations == []  # ancho real 20m >= 15m minimo


def test_frente_minimo_exceeded_fails():
    program = Program(rooms=[_room("a", 10)])
    lot = _lot(width=10, depth=20, street_side="south", frente_minimo_m=15)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert len(result.violations) == 1
    assert "Frente de fachada insuficiente" in result.violations[0]


def test_frente_minimo_uses_the_correct_side_for_east_west_street():
    # calle al este: el "frente" es el fondo (eje Y), no el ancho (eje X)
    program = Program(rooms=[_room("a", 10)])
    lot = _lot(width=10, depth=20, street_side="east", frente_minimo_m=15)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=1)
    assert result.violations == []  # fondo real 20m >= 15m minimo, aunque el ancho (10m) no llegaria


def test_multiple_violations_all_reported_together():
    program = Program(rooms=[_room("a", 300, level=NivelPlanta.PLANTA_BAJA)])
    lot = _lot(width=10, depth=10, coeficiente_edificabilidad=0.5,
               ocupacion_maxima_pct=10, altura_maxima_plantas=1, frente_minimo_m=20)
    result = ViabilidadUrbanisticaValidator().validate(program, lot, num_plantas=3)
    assert len(result.violations) == 4  # las 4 restricciones fallan a la vez, todas reportadas
