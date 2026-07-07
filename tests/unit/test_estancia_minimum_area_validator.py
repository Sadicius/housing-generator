from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.estancia_minimum_area_validator import (
    EstanciaMinimumAreaValidator,
    minimo_estancia,
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


def test_minimo_estancia_matches_tabla_1_for_up_to_five_rooms():
    assert minimo_estancia(1, 1) == 25
    assert minimo_estancia(3, 1) == 18
    assert minimo_estancia(3, 2) == 12
    assert minimo_estancia(3, 3) == 8


def test_minimo_estancia_uses_fixed_e1_e5_beyond_five_rooms():
    assert minimo_estancia(7, 1) == 25
    assert minimo_estancia(7, 5) == 8
    assert minimo_estancia(7, 6) == 6.0
    assert minimo_estancia(7, 7) == 6.0


def test_passes_when_all_estancias_meet_their_rank_minimum():
    living = _room("living", RoomType.LIVING_ROOM, 20)   # puesto 1 de 3 -> minimo 18
    bed1 = _room("bed1", RoomType.MASTER_BEDROOM, 14)     # puesto 2 de 3 -> minimo 12
    bed2 = _room("bed2", RoomType.BEDROOM, 9)             # puesto 3 de 3 -> minimo 8

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed1, bed2], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert result.violations == []


def test_reports_violation_when_an_estancia_is_below_its_rank_minimum():
    living = _room("living", RoomType.LIVING_ROOM, 20)
    bed1 = _room("bed1", RoomType.MASTER_BEDROOM, 14)
    bed2 = _room("bed2", RoomType.BEDROOM, 6)  # puesto 3 de 3 -> minimo 8, incumple

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed1, bed2], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert len(result.violations) == 1
    assert "bed2" in result.violations[0]


def test_kitchen_and_bathroom_do_not_count_as_estancia():
    living = _room("living", RoomType.LIVING_ROOM, 25)   # unica estancia -> minimo 25 (fila 1)
    kitchen = _room("kitchen", RoomType.KITCHEN, 3)       # muy pequena, pero es servicio, no cuenta aqui
    bathroom = _room("bathroom", RoomType.BATHROOM, 2)

    layout = Layout(lot=_dummy_lot(), rooms=[living, kitchen, bathroom], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert result.violations == []


def test_no_estancias_returns_no_violations():
    kitchen = _room("kitchen", RoomType.KITCHEN, 7)
    layout = Layout(lot=_dummy_lot(), rooms=[kitchen], zones=[])

    assert EstanciaMinimumAreaValidator().validate(layout).violations == []


def test_largest_estancia_passes_when_square_fits_in_rectangular_room():
    living = _room("living", RoomType.LIVING_ROOM, 20)
    living.boundary = Boundary(polygon=box(0, 0, 4.0, 5.0))  # 4m x 5m, cabe el cuadrado de 3.30m
    bed = _room("bed", RoomType.BEDROOM, 12)
    bed.boundary = Boundary(polygon=box(4, 0, 8, 3.3))

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert result.violations == []
    assert result.warnings == []


def test_largest_estancia_fails_when_square_does_not_fit_narrow_rectangular_room():
    living = _room("living", RoomType.LIVING_ROOM, 20)
    living.boundary = Boundary(polygon=box(0, 0, 2.0, 10.0))  # 2m de ancho, no cabe el cuadrado de 3.30m
    bed = _room("bed", RoomType.BEDROOM, 10)
    bed.boundary = Boundary(polygon=box(2, 0, 5, 3.3))

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert any("cuadrado inscribible" in v for v in result.violations)


def test_largest_estancia_with_non_rectangular_shape_is_marked_unverifiable_not_violated():
    from shapely.geometry import Polygon

    # forma en L: no es rectangular, no debe contar como violacion
    l_shape = Polygon([(0, 0), (6, 0), (6, 3), (3, 3), (3, 6), (0, 6)])
    living = _room("living", RoomType.LIVING_ROOM, l_shape.area)
    living.boundary = Boundary(polygon=l_shape)
    bed = _room("bed", RoomType.BEDROOM, 10)
    bed.boundary = Boundary(polygon=box(10, 0, 13, 3.3))

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert not any("cuadrado inscribible" in v for v in result.violations)
    assert len(result.warnings) == 1


def test_largest_estancia_unplaced_skips_square_check():
    living = _room("living", RoomType.LIVING_ROOM, 20)  # sin boundary -- no colocada
    bed = _room("bed", RoomType.BEDROOM, 10)
    bed.boundary = Boundary(polygon=box(0, 0, 3, 3.3))

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert not any("cuadrado inscribible" in v for v in result.violations)
    assert result.warnings == []


def test_estancia_mayor_is_always_living_room_even_if_smaller_than_a_bedroom():
    # el dormitorio es mas grande en area que el salon, pero el cuadrado
    # inscribible debe comprobarse sobre el SALON, no sobre el dormitorio
    living = _room("living", RoomType.LIVING_ROOM, 16)
    living.boundary = Boundary(polygon=box(0, 0, 2.0, 8.0))  # 2m de ancho: NO cabe el cuadrado de 3.30m
    bed = _room("bed", RoomType.MASTER_BEDROOM, 20)
    bed.boundary = Boundary(polygon=box(2, 0, 8, 8))  # mas grande en area, y SI cabe el cuadrado

    layout = Layout(lot=_dummy_lot(), rooms=[living, bed], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert any("'living'" in v and "cuadrado inscribible" in v for v in result.violations)
    assert not any("'bed'" in v and "cuadrado inscribible" in v for v in result.violations)


def test_fallback_to_largest_area_when_no_living_room_is_declared_and_warns():
    bed1 = _room("bed1", RoomType.MASTER_BEDROOM, 20)  # la mas grande, sin salon en el programa
    bed1.boundary = Boundary(polygon=box(0, 0, 5, 4))
    bed2 = _room("bed2", RoomType.BEDROOM, 12)
    bed2.boundary = Boundary(polygon=box(5, 0, 8, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[bed1, bed2], zones=[])
    result = EstanciaMinimumAreaValidator().validate(layout)

    assert len(result.warnings) == 1
    assert "bed1" in result.warnings[0] and "living_room" in result.warnings[0]
