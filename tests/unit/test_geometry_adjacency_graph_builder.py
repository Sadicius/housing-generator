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


def test_rooms_sharing_a_full_wall_are_connected():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room(
        "b", RoomType.DINING_ROOM, box(4, 0, 8, 4)
    )  # comparten el lado x=4, longitud 4
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.1).build(layout)

    assert graph.has_edge("a", "b")
    assert graph["a"]["b"]["shared_length_m"] == 4.0


def test_rooms_touching_only_at_a_corner_are_not_connected():
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 2, 2))
    room_b = _placed_room(
        "b", RoomType.BEDROOM, box(2, 2, 4, 4)
    )  # solo tocan en el punto (2,2)
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
    room_b = Room(
        id="b",
        name="Sin colocar",
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=10),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = GeometryAdjacencyGraphBuilder().build(layout)

    assert set(graph.nodes) == {"a"}


def test_repeated_calls_with_the_same_layout_object_return_the_cached_result():
    # bug de rendimiento real encontrado en auditoria: 5 validadores
    # distintos comparten la MISMA instancia de este builder y llaman a
    # build() sobre el MISMO Layout dentro de una sola validate() --
    # sin cache, cada uno reconstruia el grafo desde cero (medido:
    # 9.35s -> 4.52s con esta cache, en el programa de ejemplo del CLI).
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room("b", RoomType.KITCHEN, box(4, 0, 8, 4))
    layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    builder = GeometryAdjacencyGraphBuilder()
    graph1 = builder.build(layout)
    graph2 = builder.build(
        layout
    )  # MISMO objeto layout -- debe ser la cache, no recalculo

    assert graph1 is graph2  # misma referencia de objeto, no solo contenido igual


def test_different_layout_object_invalidates_the_cache_even_if_content_is_identical():
    # dos Layout DISTINTOS (id() distinto) con el mismo contenido no
    # deben compartir cache -- cada iteracion del recocido crea un
    # Layout nuevo, la cache debe invalidarse siempre que cambie el
    # objeto, no solo cuando cambia el contenido.
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room("b", RoomType.KITCHEN, box(4, 0, 8, 4))
    layout1 = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])
    layout2 = Layout(
        lot=_dummy_lot(), rooms=[room_a, room_b], zones=[]
    )  # contenido igual, objeto distinto

    builder = GeometryAdjacencyGraphBuilder()
    graph1 = builder.build(layout1)
    graph2 = builder.build(layout2)

    assert graph1 is not graph2  # NO debe reutilizar la cache de layout1
    assert set(graph1.edges) == set(
        graph2.edges
    )  # pero el contenido calculado es correcto en ambos


def test_cache_survives_memory_address_reuse_after_garbage_collection():
    # BUG REAL encontrado y corregido: una primera version cacheaba por
    # id(layout) (entero) -- en un bucle de creacion/descarte como el
    # del recocido simulado, Python reutiliza agresivamente direcciones
    # de memoria de objetos liberados (confirmado empiricamente: de 1000
    # creaciones en bucle, solo 6 id() distintos aparecieron). Este test
    # fuerza exactamente ese escenario: crear un Layout, cachearlo,
    # liberarlo, forzar el recolector de basura, y crear uno NUEVO que
    # con alta probabilidad reutiliza la misma direccion -- confirma que
    # el resultado sigue siendo el CORRECTO para el nuevo layout, no una
    # respuesta obsoleta del que ya no existe.
    import gc

    builder = GeometryAdjacencyGraphBuilder()

    def build_and_discard():
        room = _placed_room("temp", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
        layout = Layout(lot=_dummy_lot(), rooms=[room], zones=[])
        return builder.build(layout)

    for _ in range(50):
        build_and_discard()
    gc.collect()

    # ahora un Layout REAL con contenido distinto y verificable
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room("b", RoomType.KITCHEN, box(4, 0, 8, 4))
    final_layout = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    graph = builder.build(final_layout)
    assert set(graph.nodes) == {"a", "b"}
    assert graph.has_edge(
        "a", "b"
    )  # deben aparecer como adyacentes de verdad, no datos de "temp"


def test_cache_does_not_return_stale_result_after_a_different_layout_in_between():
    # A, luego B, luego A de nuevo (mismo objeto que la primera vez) --
    # como la cache es de una sola entrada, la tercera llamada NO debe
    # devolver la cache (fue sobrescrita por B) sino recalcular -- pero
    # el resultado debe seguir siendo correcto, solo mas lento, nunca
    # incorrecto.
    room_a = _placed_room("a", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    room_b = _placed_room("b", RoomType.KITCHEN, box(4, 0, 8, 4))
    layout_a = Layout(lot=_dummy_lot(), rooms=[room_a, room_b], zones=[])

    room_c = _placed_room("c", RoomType.BEDROOM, box(0, 0, 3, 3))
    layout_b_distinto = Layout(lot=_dummy_lot(), rooms=[room_c], zones=[])

    builder = GeometryAdjacencyGraphBuilder()
    first = builder.build(layout_a)
    builder.build(layout_b_distinto)  # invalida la cache de layout_a
    third = builder.build(
        layout_a
    )  # mismo objeto que "first", pero cache ya invalidada

    assert set(first.edges) == set(
        third.edges
    )  # resultado correcto igualmente, aunque recalculado
