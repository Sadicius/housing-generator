from typing import List
import networkx as nx
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import AdjacencyStrength
from housing_generator.infrastructure.algorithms.constraints.adjacency_validator import (
    MUST_BE_NEAR_MIN_SHARED_LENGTH_M,
)

# Grafo de puertas: capa separada de la adyacencia geometrica. Ver
# [ARCH:door-graph].


def build_door_graph(layout: Layout, adjacency_requirements: List[AdjacencyRequirement]) -> nx.Graph:
    """Subconjunto disperso del grafo de adyacencia geométrica: solo
    pares con MUST_BE_NEAR declarado Y satisfecho por la geometría
    final. No modela geometría de puertas (posición/ancho/apertura).
    Ver [ARCH:door-graph]."""
    graph = nx.Graph()
    placed_ids = {r.id for r in layout.rooms if r.is_placed}
    rooms_by_id = {r.id: r for r in layout.rooms if r.is_placed}

    for room_id in placed_ids:
        room = rooms_by_id[room_id]
        graph.add_node(room_id, name=room.name, room_type=room.room_type)

    for req in adjacency_requirements:
        if req.strength != AdjacencyStrength.MUST_BE_NEAR:
            continue
        if req.room_a_id not in placed_ids or req.room_b_id not in placed_ids:
            continue

        room_a = rooms_by_id[req.room_a_id]
        room_b = rooms_by_id[req.room_b_id]
        shared_length = room_a.boundary.polygon.boundary.intersection(
            room_b.boundary.polygon.boundary
        ).length
        if shared_length >= MUST_BE_NEAR_MIN_SHARED_LENGTH_M:  # mismo umbral que AdjacencyConstraintValidator
            graph.add_edge(req.room_a_id, req.room_b_id, shared_length_m=shared_length)

    return graph
