from typing import List, Set
import networkx as nx
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.ports.adjacency_graph_builder_port import (
    AdjacencyGraphBuilderPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType, SpaceCategory

# Puntos de corte sobre adyacencia geometrica real, no grafo de
# puertas. Ver [ARCH:pasillo-topologia].
EXENTOS_DE_LA_REGLA = {RoomType.LIVING_ROOM, RoomType.DINING_ROOM}


class PasilloTopologiaValidator(ConstraintValidatorPort):
    """Ninguna estancia protegida (no circulación, no exenta) puede ser
    un punto de corte obligado hacia otra estancia protegida. Ver
    [ARCH:pasillo-topologia]."""

    def __init__(self, graph_builder: AdjacencyGraphBuilderPort):
        self._graph_builder = graph_builder

    def validate(self, layout: Layout) -> ValidationResult:
        graph = self._graph_builder.build(layout)
        rooms_by_id = {r.id: r for r in layout.rooms if r.is_placed}

        circulation_ids: Set[str] = {
            rid
            for rid in graph.nodes
            if rooms_by_id[rid].space_category == SpaceCategory.CIRCULACION
        }
        if not circulation_ids:
            return (
                ValidationResult()
            )  # nada de circulacion en el grafo -- no hay nada que comprobar

        protected_ids: Set[str] = {
            rid
            for rid in graph.nodes
            if rooms_by_id[rid].space_category != SpaceCategory.CIRCULACION
            and rooms_by_id[rid].room_type not in EXENTOS_DE_LA_REGLA
        }

        violations: List[str] = []
        for candidate_id in protected_ids:
            reduced = graph.copy()
            reduced.remove_node(candidate_id)

            # componentes conexas calculadas UNA vez por candidato, no una
            # vez por PAR -- bug de rendimiento real, encontrado con
            # cProfile a escala mayor (13 estancias): node_connected_component
            # hace su propia busqueda BFS/DFS completa cada vez que se
            # llama, y se llamaba una vez POR CADA other_id, recalculando
            # la misma componente para estancias que ya estaban juntas.
            # nx.connected_components ya da TODAS las componentes en una
            # sola pasada -- el resto es una simple consulta de diccionario.
            component_by_node = {
                node: component
                for component in nx.connected_components(reduced)
                for node in component
            }

            for other_id in protected_ids:
                if other_id == candidate_id or other_id not in component_by_node:
                    continue
                reachable = component_by_node[other_id]
                if not (reachable & circulation_ids):
                    violations.append(
                        f"'{rooms_by_id[candidate_id].id}' actúa como paso obligado hacia "
                        f"'{rooms_by_id[other_id].id}' -- sin ella, esta última queda "
                        f"desconectada de toda circulación"
                    )

        return ValidationResult(violations=violations)
