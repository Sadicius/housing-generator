from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.proporcion_maxima_validator import (
    ProporcionMaximaValidator,
    PROPORCION_MAXIMA,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 30, 30)))


def _placed(room_id, room_type, polygon) -> Room:
    r = Room(
        id=room_id,
        name=room_id,
        room_type=room_type,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    r.boundary = Boundary(polygon=polygon)
    return r


def test_reproduces_the_real_case_found_in_the_5_bedroom_scenario():
    # caso real exacto de la bateria de 5 escenarios reales: un
    # dormitorio de 2.11m x 20.00m (9.5:1), normativamente valido
    # (supera el ancho minimo) pero absurdo en proporcion.
    dorm = _placed("dorm1", RoomType.BEDROOM, box(0, 0, 2.11, 20.0))
    layout = Layout(lot=_dummy_lot(), rooms=[dorm], zones=[])

    result = ProporcionMaximaValidator().validate(layout)
    assert len(result.violations) == 1
    assert "NO normativo" in result.violations[0]


def test_applies_to_any_room_type_not_just_specific_ones():
    # a diferencia de los validadores de ancho minimo (solo tipos
    # concretos), este aplica a CUALQUIER tipo -- incluidos los que
    # AnchoLibrePracticoValidator ni siquiera cubre.
    for room_type in [RoomType.GARAGE, RoomType.TECHNICAL_ROOM, RoomType.STORAGE_ROOM]:
        room = _placed("r", room_type, box(0, 0, 1.0, 5.0))  # 5:1
        layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
        result = ProporcionMaximaValidator().validate(layout)
        assert (
            len(result.violations) == 1
        ), f"{room_type} deberia fallar con proporcion 5:1"


def test_within_ratio_passes():
    room = _placed("r", RoomType.LIVING_ROOM, box(0, 0, 5, 6))  # 1.2:1
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ProporcionMaximaValidator().validate(layout)
    assert result.violations == []


def test_exactly_at_threshold_passes():
    room = _placed("r", RoomType.LIVING_ROOM, box(0, 0, 4, 4 * PROPORCION_MAXIMA))
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ProporcionMaximaValidator().validate(layout)
    assert result.violations == []


def test_just_over_threshold_fails():
    room = _placed("r", RoomType.LIVING_ROOM, box(0, 0, 4, 4 * PROPORCION_MAXIMA + 0.1))
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ProporcionMaximaValidator().validate(layout)
    assert len(result.violations) == 1


def test_unplaced_room_is_skipped_not_crashed():
    room = Room(
        id="r", name="r", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)
    )
    layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
    result = ProporcionMaximaValidator().validate(layout)
    assert result.violations == []
