"""Utilidades geometricas compartidas basadas en shapely.

Se deja como modulo separado para que los generadores de layout no
dupliquen logica de particionado/interseccion cuando se anadan nuevas
estrategias (CSP, genetico, etc.).
"""

import logging
import math
from typing import List, Optional, Tuple
from shapely.geometry import Polygon, LineString

logger = logging.getLogger(__name__)


def _rectangle_mrr_if_valid(
    polygon: Polygon, relative_tolerance: float = 0.01
) -> Optional[Polygon]:
    """Calcula `minimum_rotated_rectangle` UNA sola vez y comprueba si
    `polygon` es (aproximadamente) ese rectangulo -- devuelve el propio
    mrr si es valido, o None si no. Consolidado tras un hallazgo real
    de cProfile (no optimizacion especulativa): `_is_axis_or_rotated_rectangle`
    y `rectangle_side_lengths` se llamaban SIEMPRE juntas, cada una
    calculando `minimum_rotated_rectangle` por separado sobre el MISMO
    poligono -- 9160 llamadas medidas en una prueba real, el doble de
    las necesarias. Ver [ARCH:shapely-utils]."""
    mrr = polygon.minimum_rotated_rectangle
    mrr_area = mrr.area
    if mrr_area <= 0:
        return None
    if abs(polygon.area - mrr_area) > relative_tolerance * mrr_area:
        return None
    return mrr


def _mrr_side_lengths(mrr: Polygon) -> Tuple[float, float]:
    coords = list(mrr.exterior.coords)  # 5 puntos, el ultimo repite el primero
    side_a = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    side_b = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
    return side_a, side_b


def can_fit_rectangle(
    polygon: Polygon, side_a_m: float, side_b_m: float
) -> Optional[bool]:
    """¿Cabe un rectangulo de `side_a_m` x `side_b_m` dentro de `polygon`
    (en cualquiera de las dos orientaciones)?

    Mismos TRES estados que `can_inscribe_square` (del que esta funcion
    es la generalizacion): True / False / None ("no verificable", nunca
    confundido con "aprobado").
    """
    mrr = _rectangle_mrr_if_valid(polygon)
    if mrr is None:
        return None
    width, height = _mrr_side_lengths(mrr)
    return (width >= side_a_m and height >= side_b_m) or (
        width >= side_b_m and height >= side_a_m
    )


def can_inscribe_square(polygon: Polygon, side_length_m: float) -> Optional[bool]:
    """¿Cabe un cuadrado de `side_length_m` de lado dentro de `polygon`?
    Caso particular de `can_fit_rectangle` con los dos lados iguales."""
    return can_fit_rectangle(polygon, side_length_m, side_length_m)


def meets_minimum_width(polygon: Polygon, min_width_m: float) -> Optional[bool]:
    """Ancho libre entre paramentos enfrentados (A.3.2.1 / A.3.2.3): el
    lado MAS CORTO del rectangulo debe ser >= min_width_m. A diferencia
    de `can_fit_rectangle`, aqui el lado corto de LA PROPIA estancia es
    el que se mide directamente, no si cabe otra forma dentro."""
    mrr = _rectangle_mrr_if_valid(polygon)
    if mrr is None:
        return None
    width, height = _mrr_side_lengths(mrr)
    return min(width, height) >= min_width_m


def count_exterior_sides(
    room_polygon: Polygon,
    lot_polygon: Polygon,
    min_contact_m: float = 0.3,
    excluded_segments: Optional[List[LineString]] = None,
) -> Optional[int]:
    """Cuenta cuántos de los 4 lados de `room_polygon` tienen contacto
    real con el límite de `lot_polygon` (`min_contact_m` de borde
    compartido). `excluded_segments`: lados de medianera, no cuentan
    como exterior real. Ver [ARCH:shapely-utils]."""
    mrr = _rectangle_mrr_if_valid(room_polygon)
    if mrr is None:
        return None

    coords = list(mrr.exterior.coords)  # 5 puntos, el ultimo repite el primero
    lot_boundary = lot_polygon.boundary
    if excluded_segments:
        for seg in excluded_segments:
            lot_boundary = lot_boundary.difference(seg.buffer(1e-6))

    count = 0
    for i in range(4):
        side = LineString([coords[i], coords[i + 1]])
        overlap_length = side.intersection(lot_boundary).length
        if overlap_length >= min_contact_m:
            count += 1
    return count


def evaluate_minimum_width(
    room_id: str,
    polygon: Polygon,
    threshold_m: float,
    violation_message: str,
    warning_message: str,
) -> tuple:
    """Evalúa el ancho libre mínimo (3 estados) y devuelve
    (violaciones, avisos), listo para `violations.extend(v)`. Helper
    compartido por varios validadores. Ver [ARCH:shapely-utils]."""
    cumple = meets_minimum_width(polygon, threshold_m)
    if cumple is False:
        return ([f"'{room_id}': {violation_message}"], [])
    elif cumple is None:
        return ([], [f"'{room_id}': {warning_message}"])
    return ([], [])


def polygon_to_shapes(geom) -> List[dict]:
    """Convierte una geometría (`Polygon` o `MultiPolygon`) en una
    lista de "formas", cada una con su anillo exterior y sus anillos
    interiores (huecos, p.ej. un patio rodeado por todos lados)
    AGRUPADOS juntos -- a diferencia de una lista plana de anillos,
    esto preserva qué hueco pertenece a qué forma. Necesario para
    renderizarlo correctamente en el visor (recorte real del hueco,
    no otra pieza más pintada encima con el mismo color) -- hallazgo
    real al revisar las conexiones entre Python y el dashboard: la
    lista plana anterior no permitía distinguir "esto es un hueco de
    esta forma" de "esto es una pieza separada del MultiPolygon".
    Compartida entre `SimulatedAnnealingLayoutGenerator` (nunca
    produce huecos, huella siempre maciza) y `BTreeLayoutGenerator`
    (sí puede producirlos). Ver [ARCH:shapely-utils], [ARCH:btree-partition].

    Formato: `[{"exterior": [[x,y],...], "interiors": [[[x,y],...], ...]}, ...]`

    Robustez: una resta geometrica (`buildable.difference(...)`) puede
    degenerar por precision de punto flotante en un `GeometryCollection`
    con fragmentos sin area (`LineString`/`Point`) mezclados con el
    `Polygon` real -- ninguno de esos fragmentos tiene `.exterior`, asi
    que se descartan explicitamente en vez de asumir que todo lo que no
    es `MultiPolygon` es un `Polygon` valido.
    """
    if geom is None or geom.is_empty:
        return []

    if geom.geom_type == "Polygon":
        polygons = [geom]
    elif geom.geom_type == "MultiPolygon":
        polygons = list(geom.geoms)
    elif geom.geom_type == "GeometryCollection":
        polygons = []
        for part in geom.geoms:
            if part.is_empty:
                continue
            if part.geom_type == "Polygon":
                polygons.append(part)
            elif part.geom_type == "MultiPolygon":
                polygons.extend(part.geoms)
        descartados = len(list(geom.geoms)) - len(polygons)
        if descartados:
            logger.warning(
                "polygon_to_shapes: %d fragmento(s) sin area (Point/LineString) "
                "descartados de un GeometryCollection degenerado",
                descartados,
            )
    else:
        logger.warning(
            "polygon_to_shapes: geometria degenerada de tipo '%s' sin area, "
            "descartada sin dibujar nada",
            geom.geom_type,
        )
        return []

    return [
        {
            "exterior": [list(coord) for coord in poly.exterior.coords],
            "interiors": [
                [list(coord) for coord in interior.coords]
                for interior in poly.interiors
            ],
        }
        for poly in polygons
        if not poly.is_empty
    ]
