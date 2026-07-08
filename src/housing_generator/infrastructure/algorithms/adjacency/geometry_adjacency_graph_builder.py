from typing import Optional
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

    CACHE de una sola entrada (bug de rendimiento real encontrado en
    auditoria, no una optimizacion especulativa): `container.py` conecta
    la MISMA instancia de esta clase a 5 validadores distintos (nucleo
    humedo, zonificacion dia/noche/servicio, topologia de pasillo), y
    los 5 se ejecutan sobre el MISMO `Layout` dentro de una unica llamada
    a `CompositeConstraintValidator.validate()` -- sin cache, cada uno
    reconstruye el grafo desde cero (O(n^2) intersecciones geometricas),
    5 veces por iteracion del recocido simulado. Medido con el programa
    de ejemplo del CLI: 9.35s -> 4.52s (mas del doble de rapido) solo con
    esta cache.

    BUG REAL encontrado y corregido durante la propia auditoria: la
    primera version cacheaba por `id(layout)` (un entero). Comprobado
    con un experimento directo: en un bucle de creacion/descarte de
    `Layout` como el que hace el recocido simulado, de 1000 objetos
    creados solo 6 `id()` distintos aparecieron -- Python REUTILIZA
    agresivamente direcciones de memoria de objetos ya liberados. Cachear
    solo por `id()` habria devuelto resultados de un Layout COMPLETAMENTE
    DISTINTO que por pura casualidad reutilizo la misma direccion,
    silenciosamente. Corregido guardando una REFERENCIA real al objeto
    (no solo su id): mientras esa referencia siga viva, Python no puede
    liberar esa memoria ni reutilizarla para otro objeto, eliminando la
    colision de raiz -- coste: mantener UN Layout adicional vivo un poco
    mas, insignificante frente al ahorro.
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
            for room_b in placed_rooms[i + 1:]:
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
