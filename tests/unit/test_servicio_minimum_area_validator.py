from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.servicio_minimum_area_validator import (
    ServicioMinimumAreaValidator,
    tabla_servicios_para,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _room(room_id: str, room_type: RoomType, area_m2: float) -> Room:
    return Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=area_m2))


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_tabla_servicios_para_matches_source_for_known_row_counts():
    assert tabla_servicios_para(1)["cocina"] == 5
    assert tabla_servicios_para(2)["cocina"] == 7
    assert tabla_servicios_para(4)["aseo"] == 1.5
    assert "aseo" not in tabla_servicios_para(2)  # no exigido con <4 estancias
    assert tabla_servicios_para(8) == tabla_servicios_para(6)  # ambos usan la fila "mas de cinco"


def test_passes_when_services_meet_their_minimum_for_the_room_count():
    # 2 estancias (living, bed) -> tabla fila 2: cocina 7, bano 5, lavadero 1.5, almacenamiento 2
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed = _room("bed", RoomType.BEDROOM, 12)
    kitchen = _room("kitchen", RoomType.KITCHEN, 7)
    bathroom = _room("bathroom", RoomType.BATHROOM, 5)

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed, kitchen, bathroom], zones=[])
    assert ServicioMinimumAreaValidator().validate(layout).violations == []


def test_reports_violation_when_kitchen_is_below_minimum_for_room_count():
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed = _room("bed", RoomType.BEDROOM, 12)
    kitchen = _room("kitchen", RoomType.KITCHEN, 5)  # 2 estancias exige 7, incumple

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed, kitchen], zones=[])
    violations = ServicioMinimumAreaValidator().validate(layout).violations

    assert len(violations) == 1
    assert "kitchen" in violations[0] and "cocina" in violations[0]


def test_toilet_below_four_estancias_is_not_checked():
    # solo 2 estancias -> "aseo" no tiene minimo definido en Tabla 2, no debe violar nada
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed = _room("bed", RoomType.BEDROOM, 12)
    toilet = _room("toilet", RoomType.TOILET, 0.5)  # diminuto a propósito

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed, toilet], zones=[])
    violations = ServicioMinimumAreaValidator().validate(layout).violations

    assert violations == []


def test_toilet_from_four_estancias_onward_is_checked():
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed1 = _room("bed1", RoomType.MASTER_BEDROOM, 12)
    bed2 = _room("bed2", RoomType.BEDROOM, 8)
    bed3 = _room("bed3", RoomType.BEDROOM, 8)  # 4 estancias en total
    toilet = _room("toilet", RoomType.TOILET, 0.5)  # exige 1.5m2 a partir de 4 estancias

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed1, bed2, bed3, toilet], zones=[])
    violations = ServicioMinimumAreaValidator().validate(layout).violations

    assert len(violations) == 1
    assert "toilet" in violations[0] and "aseo" in violations[0]


def test_rooms_without_service_subtype_are_ignored():
    living = _room("living", RoomType.LIVING_ROOM, 3)  # muy pequena, pero no es servicio
    hall = _room("hall", RoomType.ENTRANCE_HALL, 1)

    layout = Layout(lot=_dummy_lot(), rooms=[living, hall], zones=[])
    assert ServicioMinimumAreaValidator().validate(layout).violations == []


def test_integrated_kitchen_is_excluded_from_tabla_2_own_check():
    # cocina integrada: se valida con CocinaIntegradaValidator (superficie
    # combinada), no aqui -- aunque sea diminuta, Tabla 2 no debe marcarla.
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed = _room("bed", RoomType.BEDROOM, 12)
    kitchen = Room(
        id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
        dimensions=Dimensions(area_m2=1), integrated_in_largest_room=True,
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living, bed, kitchen], zones=[])
    assert ServicioMinimumAreaValidator().validate(layout).violations == []


def test_total_num_estancias_override_uses_building_wide_row_not_local_count():
    # multi-planta: esta planta no tiene NINGUNA estancia local (solo la
    # cocina), pero el edificio completo tiene 3 -- sin el override,
    # local_count=0 caeria en la fila de 1 estancia (TABLA_2[1],
    # cocina=5m2); con el override, la fila real de 3 (cocina=7m2).
    kitchen = _room("kitchen", RoomType.KITCHEN, 6)
    kitchen.service_subtype = "cocina"
    layout = Layout(lot=_dummy_lot(), rooms=[kitchen], zones=[])

    sin_override = ServicioMinimumAreaValidator().validate(layout)
    assert sin_override.violations == []  # 6m2 >= 5m2 (fila de 1 estancia, local_count=0 -> TABLA_2[1])

    con_override = ServicioMinimumAreaValidator(total_num_estancias_override=3).validate(layout)
    assert len(con_override.violations) == 1  # 6m2 < 7m2 (fila real de 3 estancias)
