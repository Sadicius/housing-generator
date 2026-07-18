import json
import logging
import os
from typing import List, Optional
from housing_generator.application.ports.layout_repository_port import (
    LayoutRepositoryPort,
)
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.infrastructure.algorithms.adjacency.door_graph import (
    build_door_graph,
)

logger = logging.getLogger(__name__)


class JsonLayoutRepository(LayoutRepositoryPort):
    """Serializa los datos esenciales de un Layout. El round-trip completo
    de geometria (via shapely.wkt) se puede anadir cuando haga falta cargar
    layouts guardados, no solo inspeccionarlos."""

    @staticmethod
    def to_dict(
        layout: Layout,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ) -> dict:
        """Extraido de `save()` para reutilizar la MISMA serializacion
        (rooms/doors/metadata) sin pasar por disco -- retomado al
        construir el puente de navegador (`interface/browser/bridge.py`),
        que necesita el dict en memoria, no un archivo."""
        doors = []
        if adjacency_requirements:
            door_graph = build_door_graph(layout, adjacency_requirements)
            doors = [{"room_a": a, "room_b": b} for a, b in door_graph.edges()]

        rooms = []
        for r in layout.rooms:
            # `bounds` de un poligono vacio/degenerado es `()`, no una
            # tupla de 4 -- serializarlo tal cual produce `"bounds": []`,
            # que el visor (JS) no espera (accede a bounds[0..3] sin
            # comprobar longitud). Se normaliza a `None` -- mismo
            # significado que "sin geometria" que ya usa `not r.boundary`.
            bounds = None
            if r.boundary and not r.boundary.polygon.is_empty:
                raw_bounds = r.boundary.polygon.bounds
                if len(raw_bounds) == 4:
                    bounds = list(raw_bounds)
                else:
                    logger.warning(
                        "JsonLayoutRepository.to_dict: '%s' tiene bounds degenerados %r, se serializa como None",
                        r.id,
                        raw_bounds,
                    )
            rooms.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "type": r.room_type.value,
                    "zone": r.zone.value,
                    "area_m2": r.dimensions.area_m2,
                    "bounds": bounds,
                }
            )

        return {
            "rooms": rooms,
            "doors": doors,
            "metadata": layout.metadata,
        }

    def save(
        self,
        layout: Layout,
        path: str,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ) -> None:
        data = self.to_dict(layout, adjacency_requirements)

        parent_dir = os.path.dirname(os.path.abspath(path))
        try:
            os.makedirs(parent_dir, exist_ok=True)
        except OSError as e:
            logger.error(
                "JsonLayoutRepository.save: no se pudo crear el directorio '%s': %s",
                parent_dir,
                e,
            )
            raise

        try:
            with open(path, "w", encoding="utf-8") as f:
                # allow_nan=False: falla explicito en vez de escribir un
                # JSON no-estandar (NaN/Infinity) que `JSON.parse` del
                # visor no puede leer -- mejor un error claro aqui que un
                # archivo "valido" que rompe silenciosamente en el navegador.
                json.dump(data, f, indent=2, ensure_ascii=False, allow_nan=False)
        except ValueError as e:
            logger.error(
                "JsonLayoutRepository.save: geometria no serializable en '%s' (NaN/Infinity real): %s",
                path,
                e,
            )
            raise
        except OSError as e:
            logger.error(
                "JsonLayoutRepository.save: no se pudo escribir '%s': %s", path, e
            )
            raise

    def load(self, path: str) -> Layout:
        raise NotImplementedError(
            "La carga completa de un Layout desde JSON aun no esta implementada"
        )
