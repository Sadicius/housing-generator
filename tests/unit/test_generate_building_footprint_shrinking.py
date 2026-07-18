from shapely.geometry import box
from housing_generator.application.use_cases.generate_building import (
    GenerateBuildingUseCase,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType


def _room(room_id, area) -> Room:
    return Room(
        id=room_id,
        name=room_id,
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=area),
    )


def test_no_increment_returns_polygon_unchanged():
    poly = box(0, 0, 10, 10)
    result = GenerateBuildingUseCase._shrink_for_next_floor(poly, None, [_room("a", 5)])
    assert result.equals(poly)


def test_zero_increment_returns_polygon_unchanged():
    poly = box(0, 0, 10, 10)
    result = GenerateBuildingUseCase._shrink_for_next_floor(poly, 0.0, [_room("a", 5)])
    assert result.equals(poly)


def test_valid_increment_shrinks_the_polygon():
    poly = box(0, 0, 10, 10)  # area 100
    result = GenerateBuildingUseCase._shrink_for_next_floor(poly, 1.0, [_room("a", 5)])
    assert result.bounds == (1.0, 1.0, 9.0, 9.0)  # 1m hacia dentro en los 4 lados
    assert result.area == 64.0  # 8x8


def test_safety_net_falls_back_when_shrunk_area_too_small_for_rooms():
    poly = box(0, 0, 10, 10)  # area 100
    # incremento de 4m -> quedaria 2x2=4m2, insuficiente para 50m2 declarados
    result = GenerateBuildingUseCase._shrink_for_next_floor(poly, 4.0, [_room("a", 50)])
    assert result.equals(poly)  # copia exacta, no un area inviable


def test_safety_net_uses_sum_of_all_rooms_on_that_floor():
    poly = box(0, 0, 10, 10)  # area 100
    # encogido 1m -> 8x8=64m2, suficiente para 60m2 pero no para 70m2
    rooms_fits = [_room("a", 30), _room("b", 30)]  # suma 60 <= 64
    rooms_too_big = [_room("a", 40), _room("b", 30)]  # suma 70 > 64

    result_fits = GenerateBuildingUseCase._shrink_for_next_floor(poly, 1.0, rooms_fits)
    result_too_big = GenerateBuildingUseCase._shrink_for_next_floor(
        poly, 1.0, rooms_too_big
    )

    assert result_fits.area == 64.0  # se encogio
    assert result_too_big.equals(poly)  # red de seguridad activada
