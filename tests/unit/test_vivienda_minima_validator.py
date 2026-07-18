from housing_generator.infrastructure.algorithms.constraints.vivienda_minima_validator import (
    ViviendaMinimaValidator,
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


def _room(room_id: str, room_type: RoomType, area_m2: float = 10) -> Room:
    return Room(
        id=room_id,
        name=room_id,
        room_type=room_type,
        dimensions=Dimensions(area_m2=area_m2),
    )


def _complete_minimum_rooms():
    return [
        _room("living", RoomType.LIVING_ROOM, 25),
        _room("kitchen", RoomType.KITCHEN, 7),
        _room("bathroom", RoomType.BATHROOM, 5),
        _room("laundry", RoomType.LAUNDRY, 1.5),
        _room("drying", RoomType.DRYING_AREA, 1.5),
        _room("storage", RoomType.STORAGE, 1),
    ]


def test_only_garage_fails_all_six():
    garage = _room("garage", RoomType.GARAGE, 18)
    layout = Layout(lot=_dummy_lot(), rooms=[garage], zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 6
    assert any("salón" in v for v in violations)
    assert any("cocina" in v for v in violations)
    assert any("baño" in v for v in violations)
    assert any("lavadero" in v for v in violations)
    assert any("tendedero" in v for v in violations)
    assert any("almacenamiento" in v for v in violations)


def test_complete_minimum_program_passes():
    layout = Layout(lot=_dummy_lot(), rooms=_complete_minimum_rooms(), zones=[])
    assert ViviendaMinimaValidator().validate(layout).violations == []


def test_missing_laundry_only_reports_single_violation():
    rooms = [r for r in _complete_minimum_rooms() if r.room_type != RoomType.LAUNDRY]
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "lavadero" in violations[0]


def test_missing_drying_area_only_reports_single_violation():
    rooms = [
        r for r in _complete_minimum_rooms() if r.room_type != RoomType.DRYING_AREA
    ]
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "tendedero" in violations[0]


def test_missing_storage_only_reports_single_violation():
    rooms = [r for r in _complete_minimum_rooms() if r.room_type != RoomType.STORAGE]
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "almacenamiento" in violations[0]


def test_toilet_alone_does_not_satisfy_bathroom_requirement():
    rooms = [r for r in _complete_minimum_rooms() if r.room_type != RoomType.BATHROOM]
    rooms.append(_room("toilet", RoomType.TOILET, 2))
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "baño" in violations[0]


def test_bedroom_alone_does_not_satisfy_living_room_requirement():
    rooms = [
        r for r in _complete_minimum_rooms() if r.room_type != RoomType.LIVING_ROOM
    ]
    rooms.append(_room("bed", RoomType.BEDROOM, 12))
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    violations = ViviendaMinimaValidator().validate(layout).violations
    assert len(violations) == 1
    assert "salón" in violations[0]


def test_extra_rooms_beyond_minimum_still_pass():
    rooms = _complete_minimum_rooms() + [
        _room("dining", RoomType.DINING_ROOM, 15),
        _room("bed1", RoomType.MASTER_BEDROOM, 16),
        _room("bed2", RoomType.BEDROOM, 12),
        _room("garage", RoomType.GARAGE, 18),
    ]
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    assert ViviendaMinimaValidator().validate(layout).violations == []
