"""Puente entre el dashboard (JavaScript, en el navegador) y el
generador real (este mismo paquete Python), pensado para ejecutarse
dentro de Pyodide -- no un servidor aparte. Solo cruza datos planos
(dict/JSON), nunca objetos de dominio. Ver [ARCH:browser-bridge].
"""
import math
from typing import Optional
from shapely.geometry import box, Polygon

from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.entities.lot import Lot, CLASIFICACIONES_SUELO_VALIDAS
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas
from housing_generator.infrastructure.persistence.catastro_gml_importer import importar_parcela_gml


def analizar_parcela_catastro(gml_content: str, retranqueo_m: Optional[float] = None) -> dict:
    """Analiza un GML de parcela catastral (Sede Electrónica del
    Catastro, formato INSPIRE CadastralParcels) y devuelve los datos
    que la Zona 0 del dashboard necesita para la vista previa: el
    polígono real, el rectángulo de trabajo (OBB) y sus dimensiones
    (para rellenar `gen-lot-w`/`gen-lot-h` automáticamente).

    El generador sigue necesitando un rectángulo simple, sin rotación
    -- por eso solo se extraen el ANCHO y el FONDO del rectángulo de
    trabajo, no su orientación real respecto a la parcela. La
    orientación SÍ se usa para dibujar la vista previa (polígono real
    + rectángulo superpuesto, ambos en las mismas coordenadas locales).

    `retranqueo_m` (opcional): si se da, calcula también la "zona de
    afección" -- el polígono real reducido por retranqueo mediante
    `.buffer(-retranqueo_m)` de shapely, no el rectángulo simple. Un
    recorte de polígono correcto es genuinamente difícil de hacer bien
    en JS puro (por eso se reutiliza Pyodide/shapely, que ya está
    cargado, en vez de añadir una librería de geometría nueva al
    dashboard). Si el retranqueo colapsa el polígono a un área vacía,
    `zona_afeccion` es una lista vacía, no un error.

    Devuelve SIEMPRE un dict:
      {"ok": True, "referencia_catastral": ..., "area_declarada_m2": ...,
       "area_calculada_m2": ..., "discrepancia_area_pct": ...,
       "poligono_real": [[x,y],...], "rectangulo_trabajo": [[x,y],...],
       "poligono_orientacion_real": [[x,y],...],
       "rectangulo_trabajo_orientacion_real": [[x,y],...],
       "zona_afeccion_orientacion_real": [[x,y],...] o None,
       "ancho_m": ..., "fondo_m": ..., "zona_afeccion": [[x,y],...] o None}
    o, si el archivo no es válido:
      {"ok": False, "error": "mensaje legible"}

    `poligono_orientacion_real`/`zona_afeccion_orientacion_real`: la
    MISMA parcela y zona de afección, pero SIN la rotación que alinea
    el rectángulo de trabajo al generador -- conservan la orientación
    real respecto al norte, para que la Zona 0 del dashboard la
    dibuje de forma interpretable. Hallazgo real del usuario: mostrar
    la versión rotada "no es adecuado para una buena interpretación".
    El generador sigue usando `poligono`/`rectangulo_trabajo`
    (alineados), sin cambios. Ver [ARCH:parcela-orientacion-real].

    Ver [ARCH:catastro-gml-importer].
    """
    try:
        resultado = importar_parcela_gml(gml_content)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    coords_rect = list(resultado.rectangulo_trabajo.exterior.coords)[:-1]  # sin el punto de cierre repetido
    ancho_m = math.hypot(coords_rect[1][0] - coords_rect[0][0], coords_rect[1][1] - coords_rect[0][1])
    fondo_m = math.hypot(coords_rect[2][0] - coords_rect[1][0], coords_rect[2][1] - coords_rect[1][1])

    zona_afeccion = None
    zona_afeccion_orientacion_real = None
    if retranqueo_m is not None and retranqueo_m > 0:
        afeccion_poly = resultado.poligono.buffer(-retranqueo_m)
        if not afeccion_poly.is_empty and afeccion_poly.geom_type == "Polygon":
            zona_afeccion = [list(c) for c in afeccion_poly.exterior.coords]
        else:
            zona_afeccion = []  # retranqueo excesivo, colapsa a vacio -- no es un error

        afeccion_real = resultado.poligono_orientacion_real.buffer(-retranqueo_m)
        if not afeccion_real.is_empty and afeccion_real.geom_type == "Polygon":
            zona_afeccion_orientacion_real = [list(c) for c in afeccion_real.exterior.coords]
        else:
            zona_afeccion_orientacion_real = []

    return {
        "ok": True,
        "referencia_catastral": resultado.referencia_catastral,
        "area_declarada_m2": resultado.area_declarada_m2,
        "area_calculada_m2": round(resultado.area_calculada_m2, 1),
        "discrepancia_area_pct": round(resultado.discrepancia_area_pct, 2),
        "poligono_real": [list(c) for c in resultado.poligono.exterior.coords],
        "rectangulo_trabajo": [list(c) for c in resultado.rectangulo_trabajo.exterior.coords],
        "poligono_orientacion_real": [list(c) for c in resultado.poligono_orientacion_real.exterior.coords],
        "rectangulo_trabajo_orientacion_real": [
            list(c) for c in resultado.poligono_orientacion_real.minimum_rotated_rectangle.exterior.coords
        ],
        "zona_afeccion_orientacion_real": zona_afeccion_orientacion_real,
        "ancho_m": round(ancho_m, 2),
        "fondo_m": round(fondo_m, 2),
        "zona_afeccion": zona_afeccion,
    }


def generar_edificio(
    seleccion_payload: dict,
    lot_width_m: float,
    lot_height_m: float,
    seed: int = 1,
    max_iterations: int = 3000,
    retry_seeds: int = 5,
    vivienda_accesible: bool = False,
    retranqueo_m: Optional[float] = None,
    retranqueo_incremento_por_planta_m: Optional[float] = None,
    poligono_real_coords: Optional[list] = None,
    coeficiente_edificabilidad: Optional[float] = None,
    ocupacion_maxima_pct: Optional[float] = None,
    altura_maxima_plantas: Optional[int] = None,
    frente_minimo_m: Optional[float] = None,
    street_side: str = "south",
    clasificacion_suelo: Optional[list] = None,
) -> dict:
    """Genera un edificio real a partir de una selección del dashboard
    y una parcela rectangular. Reintenta semillas automáticamente
    (mismo comportamiento que `--retry-seeds` del CLI).

    `retranqueo_m`/`retranqueo_incremento_por_planta_m`: mismos
    conceptos ya conectados al CLI (`--retranqueo`/`--retranqueo-incremento`)
    -- sin forma de usarlos desde el dashboard hasta ahora, encontrado
    al revisar las conexiones entre Python y el dashboard a petición
    del usuario. El generador es siempre el árbol B* (Chang & Chang
    2000) -- el generador clásico (árbol de partición/guillotina) se
    eliminó por completo del proyecto a petición explícita del
    usuario, ver `docs/referencia/generador/prototipo-btree/`,
    [ARCH:btree-generador-por-defecto].

    `coeficiente_edificabilidad`/`ocupacion_maxima_pct`/`altura_maxima_plantas`/
    `frente_minimo_m`: parámetros urbanísticos reales (Zona 0 del
    dashboard, "Introducción de datos") -- mismos conceptos ya
    conectados al CLI (`--edificabilidad`, `--ocupacion-maxima`,
    `--altura-maxima-plantas`, `--frente-minimo`). Si el programa no
    es viable, `GenerateBuildingUseCase` lo detecta ANTES de generar
    nada (ver [ARCH:viabilidad-urbanistica]) -- el error llega aquí
    igual que cualquier otro `LayoutGenerationError`, sin tratamiento
    especial.

    `poligono_real_coords`: lista de [x,y] del polígono REAL de la
    parcela (importado de Catastro, mismas coordenadas locales que
    `analizar_parcela_catastro` devuelve). Hallazgo real, confirmado
    por el usuario con captura del navegador: sin esto, el generador
    SIEMPRE trabajaba sobre el rectángulo de trabajo (`lot_width_m`×
    `lot_height_m`), nunca sobre la forma real -- una vivienda podía
    colocar estancias en las esquinas donde el rectángulo sobresale
    del polígono real (hasta 49m² en un caso real). Con esto,
    `ParcelaRealValidator` (restricción dura) rechaza cualquier
    estancia que sobresalga del área edificable real. `None` (caso
    manual, sin importar) -- mismo comportamiento de siempre, sin
    cambios. Ver [ARCH:parcela-real].

    Devuelve SIEMPRE un dict:
      {"ok": True, "semilla_usada": N, "reintentos": N,
       "floors": {"planta_baja": {"rooms":[...], "doors":[...], "metadata":{...}}, ...}}
    o, si fallan todos los intentos:
      {"ok": False, "error": "mensaje legible", "semillas_probadas": N}

    Ver [ARCH:browser-bridge].
    """
    try:
        seleccion = import_seleccion_plantas(seleccion_payload)
    except (KeyError, ValueError) as e:
        return {"ok": False, "error": f"El JSON de selección no tiene el formato esperado: {e}", "semillas_probadas": 0}

    program = seleccion.program
    if not program.rooms:
        return {"ok": False, "error": "La selección no tiene ninguna estancia -- añade al menos el programa mínimo.", "semillas_probadas": 0}

    poligono_real = Polygon(poligono_real_coords) if poligono_real_coords else None
    clasificacion_valida = frozenset(clasificacion_suelo or []) & CLASIFICACIONES_SUELO_VALIDAS
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, lot_width_m, lot_height_m)),
        medianera_sides=seleccion.medianera_sides,
        retranqueo_m=retranqueo_m,
        retranqueo_incremento_por_planta_m=retranqueo_incremento_por_planta_m,
        coeficiente_edificabilidad=coeficiente_edificabilidad,
        ocupacion_maxima_pct=ocupacion_maxima_pct,
        altura_maxima_plantas=altura_maxima_plantas,
        frente_minimo_m=frente_minimo_m,
        street_side=street_side,
        poligono_real=poligono_real,
        clasificacion_suelo=clasificacion_valida,
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
