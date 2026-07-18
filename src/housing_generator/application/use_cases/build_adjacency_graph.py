import networkx as nx
from housing_generator.domain.entities.program import Program


class BuildAdjacencyGraphUseCase:
    """Convierte los requisitos de adyacencia de un Program en un grafo
    ponderado: la estructura de datos detras del clasico 'diagrama de
    burbujas' que usan los arquitectos en la fase de programacion."""

    _WEIGHTS = {
        "must_be_near": 3,
        "should_be_near": 2,
        "indifferent": 1,
        "must_be_away": -3,
    }

    def execute(self, program: Program) -> nx.Graph:
        graph = nx.Graph()
        for room in program.rooms:
            graph.add_node(
                room.id, name=room.name, room_type=room.room_type, zone=room.zone
            )

        for req in program.adjacency_requirements:
            weight = self._WEIGHTS[req.strength.value]
            graph.add_edge(
                req.room_a_id, req.room_b_id, weight=weight, strength=req.strength
            )

        return graph
