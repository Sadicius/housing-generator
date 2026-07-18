from typing import List
import networkx as nx
from housing_generator.application.ports.adjacency_graph_builder_port import (
    AdjacencyGraphBuilderPort,
)
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import AdjacencyStrength
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Ver [ARCH:soft-constraint-scorer].
TARGET_CERCA_SALTOS = 2
TARGET_ALEJAR_SALTOS = 3
PESO_CERCA_NO_SATISFECHO = 1.0
PESO_ALEJAR_NO_SATISFECHO = 1.0


class SoftConstraintScorer:
    """Calcula la penalización blanda de un Layout, para sumarla a las
    violaciones duras en la función objetivo del recocido -- nunca
    bloquea nada. Ver [ARCH:soft-constraint-scorer]."""

    def __init__(
        self,
        adjacency_requirements: List[AdjacencyRequirement],
        graph_builder: AdjacencyGraphBuilderPort,
    ):
        self._soft_requirements = [
            req
            for req in adjacency_requirements
            if req.strength
            in (AdjacencyStrength.SHOULD_BE_NEAR, AdjacencyStrength.SHOULD_BE_AWAY)
        ]
        self._graph_builder = graph_builder

    def score(self, layout: Layout) -> float:
        if not self._soft_requirements:
            return 0.0

        graph = self._graph_builder.build(layout)
        penalty = 0.0

        for req in self._soft_requirements:
            if req.room_a_id not in graph or req.room_b_id not in graph:
                # solo dispara si la estancia no esta colocada. Ver
                # [ARCH:soft-constraint-scorer].
                if req.strength == AdjacencyStrength.SHOULD_BE_NEAR:
                    penalty += PESO_CERCA_NO_SATISFECHO
                continue

            if nx.has_path(graph, req.room_a_id, req.room_b_id):
                distance = nx.shortest_path_length(graph, req.room_a_id, req.room_b_id)
            else:
                distance = float("inf")

            if req.strength == AdjacencyStrength.SHOULD_BE_NEAR:
                if distance > TARGET_CERCA_SALTOS:
                    penalty += PESO_CERCA_NO_SATISFECHO
            else:  # SHOULD_BE_AWAY
                if distance < TARGET_ALEJAR_SALTOS:
                    penalty += PESO_ALEJAR_NO_SATISFECHO

        return penalty
