import json
from typing import List, Optional
from housing_generator.application.ports.layout_repository_port import LayoutRepositoryPort
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.infrastructure.algorithms.adjacency.door_graph import build_door_graph


class JsonLayoutRepository(LayoutRepositoryPort):
    """Serializa los datos esenciales de un Layout. El round-trip completo
    de geometria (via shapely.wkt) se puede anadir cuando haga falta cargar
    layouts guardados, no solo inspeccionarlos."""

    def save(
        self, layout: Layout, path: str,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ) -> None:
        doors = []
        if adjacency_requirements:
            door_graph = build_door_graph(layout, adjacency_requirements)
            doors = [{"room_a": a, "room_b": b} for a, b in door_graph.edges()]

        data = {
            "rooms": [
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.room_type.value,
                    "zone": r.zone.value,
                    "area_m2": r.dimensions.area_m2,
                    "bounds": list(r.boundary.polygon.bounds) if r.boundary else None,
                }
                for r in layout.rooms
            ],
            "doors": doors,
            "metadata": layout.metadata,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, path: str) -> Layout:
        raise NotImplementedError("La carga completa de un Layout desde JSON aun no esta implementada")
