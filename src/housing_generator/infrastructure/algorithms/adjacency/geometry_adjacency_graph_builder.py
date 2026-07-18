from typing import Optional
import networkx as nx
from housing_generator.application.ports.adjacency_graph_builder_port import (
    AdjacencyGraphBuilderPort,
)
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.room import Room


class GeometryAdjacencyGraphBuilder(AdjacencyGraphBuilderPort):
    """Construye el grafo de adyacencia real midiendo la longitud del
    segmento de borde compartido entre cada par de estancias colocadas
    (no un simple `touches()`, que también da positivo con un contacto
    de esquina). Cachea por referencia real al `Layout`, no por `id()`
    -- ver [ARCH:geometry-adjacency-graph] para el porqué.
    """

    def __init__(self, min_shared_edge_m: float = 0.1):
        self._min_shared_edge_m = min_shared_edge_m
        self._cache_layout_ref: Optional[Layout] = None
        self._cache_result: Optional[nx.Graph] = None

    def build(self, layout: Layout) -> nx.Graph:
        if layout is self._cache_layout_ref:
            return self._cache_result

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
            for room_b in placed_rooms[i + 1 :]:
                shared_length = self._shared_boundary_length(room_a, room_b)
                if shared_length >= self._min_shared_edge_m:
                    graph.add_edge(room_a.id, room_b.id, shared_length_m=shared_length)

        self._cache_layout_ref = layout
        self._cache_result = graph
        return graph

    @staticmethod
    def _shared_boundary_length(room_a: Room, room_b: Room) -> float:
        boundary_a = room_a.boundary.polygon.boundary
        boundary_b = room_b.boundary.polygon.boundary
        return boundary_a.intersection(boundary_b).length
