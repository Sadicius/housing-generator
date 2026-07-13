from typing import Callable, List, Optional
import networkx as nx
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.room import Room


class GroupingConstraintValidator(ConstraintValidatorPort):
    """Comprueba que las estancias que cumplen `predicate` estén a
    distancia (paredes a cruzar) ≤ `max_distance` entre sí, sobre el
    grafo de adyacencia real. Mecanismo genérico: sirve tanto para
    núcleo húmedo como para zonificación día/noche/servicio, solo
    cambian los parámetros.
    """

    def __init__(
        self,
        graph_builder: AdjacencyGraphBuilderPort,
        predicate: Callable[[Room], bool],
        max_distance: int,
        label: str,
    ):
        self._graph_builder = graph_builder
        self._predicate = predicate
        self._max_distance = max_distance
        self._label = label

    def validate(self, layout: Layout) -> ValidationResult:
        graph = self._graph_builder.build(layout)
        members = [r.id for r in layout.rooms if r.is_placed and self._predicate(r)]

        violations: List[str] = []
        for i, room_a_id in enumerate(members):
            for room_b_id in members[i + 1:]:
                distance = self._distance(graph, room_a_id, room_b_id)
                if distance is None:
                    violations.append(
                        f"'{room_a_id}' y '{room_b_id}' ({self._label}) no estan conectadas "
                        f"en el grafo de adyacencia real"
                    )
                elif distance > self._max_distance:
                    violations.append(
                        f"'{room_a_id}' y '{room_b_id}' ({self._label}) estan a distancia "
                        f"{distance}, por encima del maximo permitido ({self._max_distance})"
                    )
        return ValidationResult(violations=violations)

    @staticmethod
    def _distance(graph: nx.Graph, a: str, b: str) -> Optional[int]:
        try:
            return nx.shortest_path_length(graph, a, b)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
