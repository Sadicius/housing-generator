from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.wet_core_validator import (
    build_wet_core_validator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _placed_room(room_id: str, room_type: RoomType, polygon) -> Room:
    room = Room(
        id=room_id,
        name=room_id,
        room_type=room_type,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    room.boundary = Boundary(polygon=polygon)
    return room


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_wet_core_passes_when_all_wet_rooms_share_walls_with_each_other():
    # cocina, bano y lavadero mutuamente adyacentes (forman un nucleo compacto)
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room(
        "bathroom", RoomType.BATHROOM, box(3, 0, 6, 3)
    )  # toca cocina
    laundry = _placed_room(
        "laundry", RoomType.LAUNDRY, box(0, 3, 6, 5)
    )  # toca cocina Y bano
    living = _placed_room(
        "living", RoomType.LIVING_ROOM, box(20, 20, 25, 25)
    )  # lejos, no es humeda

    layout = Layout(
        lot=_dummy_lot(), rooms=[kitchen, bathroom, laundry, living], zones=[]
    )

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_wet_core_with_only_two_wet_rooms_still_requires_distance_one():
    # con 2 humedas, la exigencia sigue siendo distancia 1 (pared
    # compartida) -- confirma que la relajacion NO se aplica a este
    # caso, solo a partir de 3 humedas. Ver [ARCH:nucleo-humedo-distancia].
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room(
        "bathroom", RoomType.BATHROOM, box(4, 0, 7, 3)
    )  # NO toca cocina (hueco de 1m)

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations
    assert len(violations) == 1


def test_wet_core_with_three_wet_rooms_allows_distance_two():
    # con 3+ humedas, la exigencia se relaja a distancia 2 -- criterio
    # de ingenieria confirmado explicitamente (NO normativo, sin
    # fuente que respalde un numero concreto), tras diagnostico real:
    # exigir que las 3 se toquen mutuamente (distancia 1 para todas
    # las parejas) bajaba la convergencia al 7-20% de semillas
    # probadas; con distancia 2, sigue siendo "cerca" (maximo una
    # estancia de por medio), sin exigir contacto directo mutuo entre
    # las tres. Ver [ARCH:nucleo-humedo-distancia].
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room(
        "bathroom", RoomType.BATHROOM, box(3, 0, 6, 3)
    )  # toca cocina, distancia 1
    laundry = _placed_room(
        "laundry", RoomType.LAUNDRY, box(6, 0, 9, 3)
    )  # toca bano, cocina a distancia 2

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom, laundry], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    assert validator.validate(layout).violations == []


def test_wet_core_with_three_wet_rooms_still_fails_beyond_distance_two():
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room(
        "bathroom", RoomType.BATHROOM, box(3, 0, 6, 3)
    )  # toca cocina, distancia 1
    hall = _placed_room(
        "hall", RoomType.ENTRANCE_HALL, box(6, 0, 9, 3)
    )  # entre bano y lavadero, no humeda
    laundry = _placed_room(
        "laundry", RoomType.LAUNDRY, box(9, 0, 12, 3)
    )  # toca hall, cocina a distancia 3

    layout = Layout(
        lot=_dummy_lot(), rooms=[kitchen, bathroom, hall, laundry], zones=[]
    )

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations

    assert len(violations) == 1
    assert "kitchen" in violations[0] and "laundry" in violations[0]


def test_wet_core_reports_violation_when_wet_rooms_are_disconnected():
    kitchen = _placed_room("kitchen", RoomType.KITCHEN, box(0, 0, 3, 3))
    bathroom = _placed_room(
        "bathroom", RoomType.BATHROOM, box(50, 50, 53, 53)
    )  # aislado del resto

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom], zones=[])

    validator = build_wet_core_validator(GeometryAdjacencyGraphBuilder())
    violations = validator.validate(layout).violations

    assert len(violations) == 1
    assert "no estan conectadas" in violations[0]
