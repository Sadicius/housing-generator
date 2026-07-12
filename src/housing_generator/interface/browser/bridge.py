"""Puente entre el dashboard (JavaScript, en el navegador) y el
generador real (este mismo paquete Python) -- pensado para ejecutarse
dentro de Pyodide (Python compilado a WebAssembly, corriendo en el
propio navegador), no como un servidor aparte.

Retomado de una pregunta directa del usuario ("¿es esta la forma de
trabajar?"): el flujo anterior obligaba a exportar un JSON desde el
dashboard, salir al terminal a ejecutar el CLI, y volver a cargar el
resultado en el visor -- un puente manual entre dos mundos que nunca
se hablaban. Esta funcion es ese puente, pero automatico: recibe datos
planos (dict, lo que ya produce `exportSectionSelection()` en el
dashboard) y devuelve datos planos (el mismo formato que ya consume
`renderPlano()` en el visor) -- todo dentro del mismo proceso del
navegador, sin pasar por disco ni por una terminal.

Deliberadamente NO expone objetos de dominio (Program, Lot, Layout) a
JavaScript -- estos no cruzan bien el puente FFI de Pyodide (requieren
conversion caso a caso, fragil de mantener). Solo dicts/listas/
numeros/strings, lo unico que JSON.parse/JSON.stringify entienden
igual de bien a los dos lados.
"""
from typing import Optional
from shapely.geometry import box

from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas


def generar_edificio(
    seleccion_payload: dict,
    lot_width_m: float,
    lot_height_m: float,
    seed: int = 1,
    max_iterations: int = 3000,
    retry_seeds: int = 5,
    vivienda_accesible: bool = False,
) -> dict:
    """Genera un edificio real a partir de una seleccion del dashboard
    (mismo formato que `seleccion_plantas.json`) y una parcela
    rectangular. Reintenta semillas automaticamente, MISMO
    comportamiento que `--retry-seeds` del CLI (misma razon: los
    programas del dashboard no estan curados a mano, necesitan mas
    margen de busqueda de forma habitual) -- de hecho, esta funcion y
    el CLI comparten toda la logica de generacion, solo difieren en
    donde entra el dato (payload en memoria vs. archivo en disco) y
    donde sale el resultado (dict en memoria vs. archivo en disco).

    Devuelve SIEMPRE un dict con la forma:
      {"ok": True, "semilla_usada": N, "reintentos": N,
       "floors": {"planta_baja": {"rooms":[...], "doors":[...], "metadata":{...}}, ...}}
    o, si fallan todos los intentos:
      {"ok": False, "error": "mensaje legible", "semillas_probadas": N}

    Nunca lanza una excepcion hacia JavaScript -- el error se devuelve
    como dato, mas facil de manejar desde el lado JS que un traceback
    de Python cruzando el puente FFI.
    """
    try:
        seleccion = import_seleccion_plantas(seleccion_payload)
    except (KeyError, ValueError) as e:
        return {"ok": False, "error": f"El JSON de selección no tiene el formato esperado: {e}", "semillas_probadas": 0}

    program = seleccion.program
    if not program.rooms:
        return {"ok": False, "error": "La selección no tiene ninguna estancia -- añade al menos el programa mínimo.", "semillas_probadas": 0}

    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, lot_width_m, lot_height_m)),
        medianera_sides=seleccion.medianera_sides,
    )

    building = None
    last_error: Optional[Exception] = None
    attempts = max(1, retry_seeds)
    used_seed = seed

    for attempt in range(attempts):
        used_seed = seed + attempt
        use_case = build_generate_building_use_case(
            adjacency_requirements=program.adjacency_requirements,
            seed=used_seed,
            max_iterations=max_iterations,
            vivienda_accesible=vivienda_accesible,
        )
        try:
            building = use_case.execute(program, lot)
            break
        except LayoutGenerationError as e:
            last_error = e

    if building is None:
        return {
            "ok": False,
            "error": f"No se pudo generar tras probar {attempts} semillas (desde {seed} hasta {seed + attempts - 1}). "
                     f"Último error: {last_error}",
            "semillas_probadas": attempts,
        }

    floors = {}
    for level, layout in building.floors.items():
        floors[level.value] = JsonLayoutRepository.to_dict(layout, adjacency_requirements=program.adjacency_requirements)

    return {
        "ok": True,
        "semilla_usada": used_seed,
        "reintentos": used_seed - seed,
        "medianera_sides": sorted(seleccion.medianera_sides),
        "floors": floors,
    }
