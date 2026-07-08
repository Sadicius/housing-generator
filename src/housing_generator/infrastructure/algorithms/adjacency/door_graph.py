from typing import List
import networkx as nx
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import AdjacencyStrength

# Hueco de modelo identificado en relaciones_espaciales.md: "acceso/
# puertas -- 'cerca pero sin puerta directa' no se podia expresar con la
# geometria actual". Resuelto aqui de forma deliberadamente minima,
# inspirado en el patron "Door Connectivity Graph" (grafo de puertas
# como capa SEPARADA y mas dispersa que la de adyacencia geometrica,
# en vez de modelar geometria real de puertas -- posicion, ancho,
# sentido de apertura) encontrado en investigacion externa (paper
# "Automatic Rendering of Building Floor Plan Images from Textual
# Descriptions"). Infinigen Indoors (2024) confirma ademas que la
# colocacion de puertas es tipicamente un paso POSTERIOR a resolver las
# posiciones, no algo que compita con la busqueda del generador -- este
# grafo se construye sobre un Layout ya generado, no durante la busqueda.
#
# Regla de "tiene puerta" (deliberadamente simple, no exhaustiva):
# un par de estancias tiene puerta si y solo si hay un
# AdjacencyRequirement(MUST_BE_NEAR) declarado para ese par Y la
# geometria final realmente los coloco adyacentes. El umbral de
# MUST_BE_NEAR (1.0m de borde compartido) ya se eligio especificamente
# "para que quepa una puerta" (confirmado por el usuario al implementar
# AdjacencyConstraintValidator) -- este grafo simplemente hace explicito
# lo que ese umbral ya representaba implicitamente, sin inventar una
# regla nueva. Cualquier otro par de estancias adyacentes (comparten
# pared por optimizacion geometrica, sin requisito declarado) queda
# fuera: "cerca pero sin puerta directa", exactamente el caso que antes
# no se podia distinguir.


def build_door_graph(layout: Layout, adjacency_requirements: List[AdjacencyRequirement]) -> nx.Graph:
    """Grafo de puertas: subconjunto DISPERSO del grafo de adyacencia
    geometrica real, solo los pares con un AdjacencyRequirement(MUST_BE_NEAR)
    declarado Y satisfecho por la geometria final. No modela geometria de
    puertas (posicion/ancho/apertura) -- solo si existe una, a nivel de
    grafo, igual que la propia adyacencia no modela grosor de muro."""
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
        if shared_length >= 1.0:  # mismo umbral que AdjacencyConstraintValidator
            graph.add_edge(req.room_a_id, req.room_b_id, shared_length_m=shared_length)

    return graph
