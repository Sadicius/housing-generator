from typing import List
import networkx as nx
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import AdjacencyStrength
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Diseno ya decidido en relaciones_espaciales.md, sin conectar hasta
# ahora -- primer punto retomado de docs/CONTINUIDAD.md. Investigacion
# externa confirmada (curriculum-based course timetabling, arxiv
# 1409.7186): la tecnica estandar para combinar restricciones duras y
# blandas en una funcion de coste de recocido simulado es una SUMA
# PONDERADA, con un peso grande para lo duro (parametro del algoritmo,
# no derivado de una formula) y pesos pequenos especificos por tipo de
# restriccion blanda -- exactamente el patron aplicado aqui, no una
# tecnica inventada sin precedente.
#
# Metrica: saltos en el grafo de adyacencia REAL (misma fuente que
# nucleo humedo/zonificacion/topologia de pasillo -- GeometryAdjacencyGraphBuilder,
# con su cache ya corregida), NO el grafo de puertas disperso ni
# contacto geometrico directo -- decision ya tomada y documentada.
TARGET_CERCA_SALTOS = 2
TARGET_ALEJAR_SALTOS = 3
PESO_CERCA_NO_SATISFECHO = 1.0
PESO_ALEJAR_NO_SATISFECHO = 1.0


class SoftConstraintScorer:
    """Calcula la penalizacion blanda (SHOULD_BE_NEAR/SHOULD_BE_AWAY,
    "Preferencia cerca/alejar" del catalogo) de un Layout, para sumarla
    a las violaciones duras en la funcion objetivo del recocido
    simulado. Nunca genera una ValidationResult ni bloquea nada -- es
    puramente un numero a minimizar, subordinado siempre a las
    restricciones duras (ver SimulatedAnnealingLayoutGenerator._score).

    Si `adjacency_requirements` no contiene ningun SHOULD_BE_NEAR/
    SHOULD_BE_AWAY, `score()` siempre devuelve 0 -- inerte por
    completo, no cambia el comportamiento de programas que solo
    declaran restricciones duras (compatibilidad hacia atras real, no
    solo de interfaz)."""

    def __init__(
        self,
        adjacency_requirements: List[AdjacencyRequirement],
        graph_builder: AdjacencyGraphBuilderPort,
    ):
        self._soft_requirements = [
            req for req in adjacency_requirements
            if req.strength in (AdjacencyStrength.SHOULD_BE_NEAR, AdjacencyStrength.SHOULD_BE_AWAY)
        ]
        self._graph_builder = graph_builder

    def score(self, layout: Layout) -> float:
        if not self._soft_requirements:
            return 0.0

        graph = self._graph_builder.build(layout)
        penalty = 0.0

        for req in self._soft_requirements:
            if req.room_a_id not in graph or req.room_b_id not in graph:
                # no colocadas o no conectadas a nada -- para "cerca" es
                # un incumplimiento real (no hay forma de estar cerca sin
                # estar siquiera en el mismo grafo); para "alejar" no se
                # penaliza (dos estancias totalmente desconectadas ya
                # estan, por definicion, todo lo lejos que se puede pedir).
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
