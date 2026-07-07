import networkx as nx
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.room import Room


class GeometryAdjacencyGraphBuilder(AdjacencyGraphBuilderPort):
    """Construye el grafo de adyacencia real midiendo la longitud del
    segmento de borde compartido entre cada par de estancias colocadas.

    Un simple `touches()` de shapely tambien da positivo con un contacto
    de una sola esquina (un punto), que no es una pared real. Por eso se
    mide la LONGITUD de la interseccion de los bordes y se exige un
    minimo configurable (`min_shared_edge_m`) para que cuente como
    adyacencia real -- un punto de contacto mide longitud 0 y queda
    descartado automaticamente, sin caso especial.

    `min_shared_edge_m` es deliberadamente un parametro, no una constante
    fija: la distincion entre adyacencia interior (pared entre dos
    estancias) y contacto con el exterior (fachada/limite de solar) usa
    umbrales distintos segun el caso de uso.
    """

    def __init__(self, min_shared_edge_m: float = 0.1):
        self._min_shared_edge_m = min_shared_edge_m

    def build(self, layout: Layout) -> nx.Graph:
        graph = nx.Graph()
        placed_rooms = [r for r in layout.rooms if r.is_placed]

        for room in placed_rooms:
            graph.add_node(
                room.id,
                name=room.name,
                room_type=room.room_type,
                zone=room.zone,
                is_wet=room.is_wet,
            )

        for i, room_a in enumerate(placed_rooms):
            for room_b in placed_rooms[i + 1:]:
                shared_length = self._shared_boundary_length(room_a, room_b)
                if shared_length >= self._min_shared_edge_m:
                    graph.add_edge(room_a.id, room_b.id, shared_length_m=shared_length)

        return graph

    @staticmethod
    def _shared_boundary_length(room_a: Room, room_b: Room) -> float:
        boundary_a = room_a.boundary.polygon.boundary
        boundary_b = room_b.boundary.polygon.boundary
        return boundary_a.intersection(boundary_b).length
