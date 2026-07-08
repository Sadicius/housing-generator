from shapely.geometry import box
from housing_generator.infrastructure.algorithms.adjacency.door_graph import build_door_graph
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


def test_must_be_near_pair_with_real_shared_wall_gets_a_door():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    dining = _placed("dining", RoomType.DINING_ROOM, box(4, 0, 8, 5))  # comparte 5m de borde
    req = [AdjacencyRequirement("living", "dining", AdjacencyStrength.MUST_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[living, dining], zones=[])

    graph = build_door_graph(layout, req)

    assert graph.has_edge("living", "dining")


def test_adjacent_pair_without_declared_requirement_has_no_door():
    # dos estancias que ACABAN adyacentes por la geometria, pero SIN
    # ningun AdjacencyRequirement(MUST_BE_NEAR) declarado entre ellas --
    # exactamente el caso "cerca pero sin puerta directa" que antes no
    # se podia distinguir.
    bed1 = _placed("bed1", RoomType.BEDROOM, box(0, 0, 3, 4))
    bed2 = _placed("bed2", RoomType.BEDROOM, box(3, 0, 6, 4))  # comparte pared, sin requisito
    layout = Layout(lot=_dummy_lot(), rooms=[bed1, bed2], zones=[])

    graph = build_door_graph(layout, [])

    assert not graph.has_edge("bed1", "bed2")
    # pero ambas SI aparecen como nodos (existen en el layout)
    assert "bed1" in graph.nodes and "bed2" in graph.nodes


def test_must_be_near_declared_but_not_actually_adjacent_gets_no_door():
    # requisito declarado, pero la geometria final NO los dejo tocandose
    # (p.ej. el generador no pudo satisfacerlo) -- no hay puerta real
    # aunque la intencion existiera.
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    dining = _placed("dining", RoomType.DINING_ROOM, box(10, 0, 14, 5))  # lejos, no tocan
    req = [AdjacencyRequirement("living", "dining", AdjacencyStrength.MUST_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[living, dining], zones=[])

    graph = build_door_graph(layout, req)

    assert not graph.has_edge("living", "dining")


def test_must_be_away_requirement_never_produces_a_door():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    garage = _placed("garage", RoomType.GARAGE, box(4, 0, 8, 5))  # tocando, pero MUST_BE_AWAY
    req = [AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY)]
    layout = Layout(lot=_dummy_lot(), rooms=[living, garage], zones=[])

    graph = build_door_graph(layout, req)

    assert not graph.has_edge("living", "garage")


def test_shared_wall_shorter_than_door_width_gets_no_door():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    # solo 0.5m de borde compartido (esquina), por debajo del umbral 1.0m
    entrance = _placed("entrance", RoomType.ENTRANCE_HALL, box(4, 4.5, 6, 6))
    req = [AdjacencyRequirement("living", "entrance", AdjacencyStrength.MUST_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[living, entrance], zones=[])

    graph = build_door_graph(layout, req)

    assert not graph.has_edge("living", "entrance")


def test_unplaced_rooms_are_excluded_entirely():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 5))
    unplaced = Room(id="unplaced", name="x", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=5))
    req = [AdjacencyRequirement("living", "unplaced", AdjacencyStrength.MUST_BE_NEAR)]
    layout = Layout(lot=_dummy_lot(), rooms=[living, unplaced], zones=[])

    graph = build_door_graph(layout, req)

    assert "unplaced" not in graph.nodes
    assert not graph.has_edge("living", "unplaced")
