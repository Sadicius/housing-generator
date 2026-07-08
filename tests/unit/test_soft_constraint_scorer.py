from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon) -> Room:
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    r.boundary = Boundary(polygon=polygon)
    return r


def _scorer(reqs):
    return SoftConstraintScorer(reqs, GeometryAdjacencyGraphBuilder())


def test_no_soft_requirements_always_scores_zero():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    assert _scorer([]).score(layout) == 0.0


def test_should_be_near_satisfied_within_target_distance_scores_zero():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed("b", RoomType.DINING_ROOM, box(3, 0, 6, 3))  # adyacentes, distancia 1
    reqs = [AdjacencyRequirement("a", "b", AdjacencyStrength.SHOULD_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    assert _scorer(reqs).score(layout) == 0.0


def test_should_be_near_beyond_target_distance_is_penalized():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.KITCHEN, box(2, 0, 4, 2))
    c = _placed("c", RoomType.DINING_ROOM, box(4, 0, 6, 2))
    d = _placed("d", RoomType.STUDY, box(6, 0, 8, 2))  # a-b-c-d en cadena: a a d hay 3 saltos
    reqs = [AdjacencyRequirement("a", "d", AdjacencyStrength.SHOULD_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c, d], zones=[])

    assert _scorer(reqs).score(layout) == 1.0


def test_should_be_away_satisfied_beyond_target_distance_scores_zero():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.KITCHEN, box(2, 0, 4, 2))
    c = _placed("c", RoomType.DINING_ROOM, box(4, 0, 6, 2))
    d = _placed("d", RoomType.GARAGE, box(6, 0, 8, 2))  # 3 saltos -- justo en el objetivo (>=3)
    reqs = [AdjacencyRequirement("a", "d", AdjacencyStrength.SHOULD_BE_AWAY)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c, d], zones=[])

    assert _scorer(reqs).score(layout) == 0.0


def test_should_be_away_too_close_is_penalized():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 3, 3))
    b = _placed("b", RoomType.GARAGE, box(3, 0, 6, 3))  # adyacentes directas, distancia 1
    reqs = [AdjacencyRequirement("a", "b", AdjacencyStrength.SHOULD_BE_AWAY)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    assert _scorer(reqs).score(layout) == 1.0


def test_should_be_away_completely_disconnected_scores_zero():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.GARAGE, box(10, 10, 12, 12))
    reqs = [AdjacencyRequirement("a", "b", AdjacencyStrength.SHOULD_BE_AWAY)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    assert _scorer(reqs).score(layout) == 0.0


def test_should_be_near_completely_disconnected_is_penalized():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.KITCHEN, box(10, 10, 12, 12))
    reqs = [AdjacencyRequirement("a", "b", AdjacencyStrength.SHOULD_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    assert _scorer(reqs).score(layout) == 1.0


def test_must_be_near_and_must_be_away_requirements_are_ignored_by_soft_scorer():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.KITCHEN, box(10, 10, 12, 12))
    reqs = [AdjacencyRequirement("a", "b", AdjacencyStrength.MUST_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b], zones=[])

    assert _scorer(reqs).score(layout) == 0.0


def test_multiple_unsatisfied_soft_requirements_accumulate():
    a = _placed("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    b = _placed("b", RoomType.KITCHEN, box(10, 10, 12, 12))
    c = _placed("c", RoomType.GARAGE, box(20, 20, 22, 22))
    reqs = [
        AdjacencyRequirement("a", "b", AdjacencyStrength.SHOULD_BE_NEAR),
        AdjacencyRequirement("a", "c", AdjacencyStrength.SHOULD_BE_NEAR),
    ]
    layout = Layout(lot=_dummy_lot(), rooms=[a, b, c], zones=[])

    assert _scorer(reqs).score(layout) == 2.0
