from shapely.geometry import box
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
    room = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    room.boundary = Boundary(polygon=polygon)
    return room


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_rooms_sharing_a_full_wall_are_connected():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room("b", RoomType.DINING_ROOM, box(4, 0, 8, 4))  # comparten el lado x=4, longitud 4
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.1).build(layout)

    assert graph.has_edge("a", "b")
    assert graph["a"]["b"]["shared_length_m"] == 4.0


def test_rooms_touching_only_at_a_corner_are_not_connected():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    room_b = _placed_room("b", RoomType.BEDROOM, box(2, 2, 4, 4))  # solo tocan en el punto (2,2)
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.1).build(layout)

    assert not graph.has_edge("a", "b")


def test_rooms_not_touching_are_not_connected():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    room_b = _placed_room("b", RoomType.BEDROOM, box(10, 10, 12, 12))
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.1).build(layout)

    assert not graph.has_edge("a", "b")


def test_threshold_filters_out_short_shared_edges():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    # comparten un tramo de pared muy corto (0.05m) desplazando la segunda caja
    room_b = _placed_room("b", RoomType.BEDROOM, box(4, 3.95, 8, 4.95))
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph_strict = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.3).build(layout)
    graph_loose = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.01).build(layout)

    assert not graph_strict.has_edge("a", "b")
    assert graph_loose.has_edge("a", "b")


def test_unplaced_rooms_are_excluded_from_the_graph():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = Room(id="b", name="Sin colocar", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=10))
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder().build(layout)

    assert set(graph.nodes) == {"a"}
