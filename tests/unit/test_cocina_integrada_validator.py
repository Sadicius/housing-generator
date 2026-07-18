from housing_generator.infrastructure.algorithms.constraints.cocina_integrada_validator import (
    CocinaIntegradaValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType
from shapely.geometry import box


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_no_integrated_kitchen_does_not_apply_no_violations_no_warnings():
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=25),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=3),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_integrated_kitchen_without_living_room_warns():
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=12),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=10),
        integrated_in_largest_room=True,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[bed, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert result.violations == []
    assert len(result.warnings) == 1
    assert "no hay salón" in result.warnings[0]


def test_combined_area_below_minimum_fails():
    # 1 sola estancia (living) -> minimoMayor=25 (fila 1); 1 servicio -> minimoCocina=5 (fila 1)
    # combinado minimo = 30. Declaramos 20+5=25, por debajo.
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=20),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=5),
        integrated_in_largest_room=True,
        vertical_opening_m2=4.0,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert len(result.violations) == 1
    assert "superficie combinada" in result.violations[0]


def test_combined_area_meets_minimum_passes():
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=25),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=5),
        integrated_in_largest_room=True,
        vertical_opening_m2=4.0,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_missing_vertical_opening_warns_not_violates():
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=25),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=5),
        integrated_in_largest_room=True,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert result.violations == []
    assert len(result.warnings) == 1
    assert "vertical_opening_m2" in result.warnings[0]


def test_vertical_opening_below_minimum_fails():
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=25),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=5),
        integrated_in_largest_room=True,
        vertical_opening_m2=2.0,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen], zones=[])

    result = CocinaIntegradaValidator().validate(layout)
    assert len(result.violations) == 1
    assert "apertura vertical" in result.violations[0]


def test_total_num_estancias_override_prevents_silent_approval_in_multi_planta():
    # BUG REAL encontrado en auditoria de logica: este validador nunca
    # recibio el mismo arreglo multi-planta que EstanciaMinimumAreaValidator
    # y ServicioMinimumAreaValidator -- sin el override, contaba solo
    # las estancias de ESTA planta (2: salon + 1 dormitorio), aplicando
    # un minimo combinado mas bajo (23m2 = 16+7) del que corresponderia
    # al edificio completo (5 estancias reales -> 31m2 = 22+9). Un area
    # combinada de 25m2 pasaba SIN avisar con el conteo local, pese a
    # ser insuficiente para el edificio real.
    living = Room(
        id="living",
        name="Estar",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=18),
    )
    bed = Room(
        id="bed",
        name="Dorm",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=12),
    )
    kitchen = Room(
        id="kitchen",
        name="Cocina",
        room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=7),
        integrated_in_largest_room=True,
        vertical_opening_m2=5.0,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, bed, kitchen], zones=[])

    sin_override = CocinaIntegradaValidator().validate(layout)
    assert (
        sin_override.violations == []
    )  # 25m2 >= 23m2 (fila local de 2 estancias) -- aprobaba mal

    con_override = CocinaIntegradaValidator(total_num_estancias_override=5).validate(
        layout
    )
    assert (
        len(con_override.violations) == 1
    )  # 25m2 < 31m2 (fila real del edificio de 5 estancias)
