from typing import List, Set
import networkx as nx
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType, SpaceCategory

# Segundo hueco de modelo de relaciones_espaciales.md: "topologia de
# circulacion (de paso vs. terminal)". KITCHEN-CORRIDOR senalaba "el
# pasillo debe llevar a la cocina, no atravesarla" -- formalizado aqui
# con deteccion de puntos de corte (articulation points) sobre el
# grafo de ADYACENCIA GEOMETRICA REAL (misma fuente que ya usan nucleo
# humedo y zonificacion dia/noche/servicio -- GeometryAdjacencyGraphBuilder,
# umbral 0.1m de pared compartida), NO sobre el grafo de puertas
# disperso (build_door_graph).
#
# CORRECCION REAL tras un primer intento fallido: la primera version
# usaba el grafo de puertas (solo relaciones Obligatorio cerca
# declaradas explicitamente) -- con programas reales, donde la mayoria
# de "cercanias" son Preferencia (no Obligatorio), ese grafo resulto
# demasiado disperso: casi CUALQUIER estancia parecia un "paso
# obligado" simplemente porque no habia redundancia de conexiones
# declaradas (rompio 9 tests, incluido el CLI). Usar la adyacencia
# geometrica real (que existe siempre, declarada o no) resuelve esto:
# refleja lo que de verdad se construyo, no solo lo que se pidio
# explicitamente.
#
# Regla (confirmada con el usuario, con excepcion explicita): ninguna
# estancia que NO sea de circulacion (CORRIDOR/ENTRANCE_HALL/STAIRCASE,
# SpaceCategory.CIRCULACION) puede ser un punto de corte obligado entre
# la circulacion y OTRA estancia -- EXCEPTO LIVING_ROOM y DINING_ROOM,
# exentas (en un salon-comedor abierto es arquitectonicamente normal
# atravesarlos para llegar a otras zonas).
EXENTOS_DE_LA_REGLA = {RoomType.LIVING_ROOM, RoomType.DINING_ROOM}


class PasilloTopologiaValidator(ConstraintValidatorPort):
    """Ninguna estancia protegida (no circulacion, no exenta) puede ser
    un punto de corte obligado entre la circulacion y otra estancia
    protegida -- si quitarla del grafo de adyacencia geometrica real
    deja a otra sin camino hacia ninguna estancia de circulacion, se
    esta obligando a atravesarla para llegar a algun sitio."""

    def __init__(self, graph_builder: AdjacencyGraphBuilderPort):
        self._graph_builder = graph_builder

    def validate(self, layout: Layout) -> ValidationResult:
        graph = self._graph_builder.build(layout)
        rooms_by_id = {r.id: r for r in layout.rooms if r.is_placed}

        circulation_ids: Set[str] = {
            rid for rid in graph.nodes
            if rooms_by_id[rid].space_category == SpaceCategory.CIRCULACION
        }
        if not circulation_ids:
            return ValidationResult()  # nada de circulacion en el grafo -- no hay nada que comprobar

        protected_ids: Set[str] = {
            rid for rid in graph.nodes
            if rooms_by_id[rid].space_category != SpaceCategory.CIRCULACION
            and rooms_by_id[rid].room_type not in EXENTOS_DE_LA_REGLA
        }

        violations: List[str] = []
        for candidate_id in protected_ids:
            reduced = graph.copy()
            reduced.remove_node(candidate_id)

            for other_id in protected_ids:
                if other_id == candidate_id or other_id not in reduced:
                    continue
                reachable = nx.node_connected_component(reduced, other_id)
                if not (reachable & circulation_ids):
                    violations.append(
                        f"'{rooms_by_id[candidate_id].id}' actúa como paso obligado hacia "
                        f"'{rooms_by_id[other_id].id}' -- sin ella, esta última queda "
                        f"desconectada de toda circulación"
                    )

        return ValidationResult(violations=violations)
