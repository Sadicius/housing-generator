from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.adjacency_validator import (
    AdjacencyConstraintValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength


def _placed_room(room_id: str, polygon) -> Room:
    room = Room(
        id=room_id,
        name=room_id,
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    room.boundary = Boundary(polygon=polygon)
    return room


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_must_be_near_passes_when_shared_edge_is_long_enough_for_a_door():
    a = _placed_room("a", box(0, 0, 4, 4))
    b = _placed_room("b", box(4, 0, 8, 4))  # comparten el lado x=4, longitud 4m
    req = [AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)]

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    violations = AdjacencyConstraintValidator(req).validate(layout).violations

    assert violations == []


def test_must_be_near_fails_when_shared_edge_is_too_short_for_a_door():
    a = _placed_room("a", box(0, 0, 4, 4))
    b = _placed_room("b", box(4, 3.5, 8, 4.5))  # solo comparten 0.5m de borde
    req = [AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)]

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    violations = AdjacencyConstraintValidator(req).validate(layout).violations

    assert len(violations) == 1
    assert "'a'" in violations[0] and "'b'" in violations[0]


def test_must_be_near_fails_when_rooms_do_not_touch_at_all():
    a = _placed_room("a", box(0, 0, 4, 4))
    b = _placed_room("b", box(50, 50, 54, 54))
    req = [AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)]

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    violations = AdjacencyConstraintValidator(req).validate(layout).violations

    assert len(violations) == 1


def test_must_be_away_still_works_alongside_must_be_near():
    a = _placed_room("a", box(0, 0, 4, 4))
    b = _placed_room("b", box(4, 0, 8, 4))  # cerca de a (cumple must_be_near)
    c = _placed_room("c", box(50, 50, 54, 54))  # lejos de a (cumple must_be_away)
    reqs = [
        AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("a", "c", AdjacencyStrength.MUST_BE_AWAY),
    ]

    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c], zones=[])
    assert AdjacencyConstraintValidator(reqs).validate(layout).violations == []


def test_unplaced_rooms_are_reported_and_requirements_involving_them_are_skipped():
    a = _placed_room("a", box(0, 0, 4, 4))
    b = Room(
        id="b",
        name="b",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=10),
    )  # sin colocar
    req = [AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)]

    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])
    violations = AdjacencyConstraintValidator(req).validate(layout).violations

    assert any("'b'" in v and "no fue colocada" in v for v in violations)
    # no debe intentar comprobar MUST_BE_NEAR contra una estancia sin colocar
    assert not any("compartir al menos" in v for v in violations)
