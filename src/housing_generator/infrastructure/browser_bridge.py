"""Funcion puente para el Visor de plano en el navegador (Pyodide).

Envuelve el mismo camino real que ya usa el CLI (--import-seleccion +
reintento automatico de semillas), pero como funcion que recibe/devuelve
JSON en vez de leer/escribir archivos -- para poder llamarla directamente
desde JavaScript sin pasar por disco.
"""
import json
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas
from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.infrastructure.algorithms.adjacency.door_graph import build_door_graph
from shapely.geometry import box


def generar_en_navegador(
    seleccion_json_str: str,
    lot_width: float,
    lot_height: float,
    retranqueo_m: float,
    seed_inicial: int,
    max_iterations: int,
    retry_seeds: int,
    vivienda_accesible: bool,
) -> str:
    """Genera un edificio completo a partir del mismo formato de JSON que
    exporta la pestaña "Sección vertical", devolviendo un JSON con el
    resultado de TODAS las plantas a la vez (a diferencia del CLI, que
    escribe un archivo por planta) -- listo para pasarselo directamente a
    LOADED_PLANS en el visor, sin descargar/subir nada.
    """
    payload = json.loads(seleccion_json_str)
    seleccion = import_seleccion_plantas(payload)
    program = seleccion.program

    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, lot_width, lot_height)),
        retranqueo_m=retranqueo_m if retranqueo_m > 0 else None,
        medianera_sides=seleccion.medianera_sides,
    )

    last_error = None
    for attempt in range(max(1, retry_seeds)):
        seed = seed_inicial + attempt
        use_case = build_generate_building_use_case(
            adjacency_requirements=program.adjacency_requirements,
            seed=seed, max_iterations=max_iterations,
            vivienda_accesible=vivienda_accesible,
        )
        try:
            building = use_case.execute(program, lot)
        except LayoutGenerationError as e:
            last_error = str(e)
            continue

        floors_out = {}
        for level, layout in building.floors.items():
            door_graph = build_door_graph(layout, program.adjacency_requirements)
            floors_out[level.value] = {
                "rooms": [
                    {
                        "id": r.id, "name": r.name, "type": r.room_type.value,
                        "zone": r.zone.value, "area_m2": r.dimensions.area_m2,
                        "bounds": list(r.boundary.polygon.bounds) if r.boundary else None,
                    }
                    for r in layout.rooms
                ],
                "doors": [{"room_a": a, "room_b": b} for a, b in door_graph.edges()],
                "metadata": layout.metadata,
            }
        return json.dumps({
            "ok": True, "seed_used": seed, "attempts": attempt + 1,
            "medianera_sides": sorted(seleccion.medianera_sides), "floors": floors_out,
        })

    return json.dumps({"ok": False, "error": last_error, "attempts": retry_seeds})
