"""Utilidades geometricas compartidas basadas en shapely.

Se deja como modulo separado para que los generadores de layout no
dupliquen logica de particionado/interseccion cuando se anadan nuevas
estrategias (CSP, genetico, etc.).
"""
import math
from typing import List, Optional, Tuple
from shapely.geometry import Polygon, LineString


def _is_axis_or_rotated_rectangle(polygon: Polygon, relative_tolerance: float = 0.01) -> bool:
    """Comprueba que `polygon` es (aproximadamente) un rectangulo, con
    cualquier rotacion -- no solo alineado a ejes. Compara el area real
    contra la del rectangulo minimo que lo envuelve (`minimum_rotated_rectangle`):
    si coinciden, el poligono ES ese rectangulo."""
    mrr_area = polygon.minimum_rotated_rectangle.area
    if mrr_area <= 0:
        return False
    return abs(polygon.area - mrr_area) <= relative_tolerance * mrr_area


def rectangle_side_lengths(polygon: Polygon) -> Tuple[float, float]:
    """Longitudes de los dos lados adyacentes del rectangulo minimo que
    envuelve `polygon` (valido tanto si esta alineado a ejes como rotado)."""
    mrr = polygon.minimum_rotated_rectangle
    coords = list(mrr.exterior.coords)  # 5 puntos, el ultimo repite el primero
    side_a = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
    side_b = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
    return side_a, side_b


def can_fit_rectangle(polygon: Polygon, side_a_m: float, side_b_m: float) -> Optional[bool]:
    """¿Cabe un rectangulo de `side_a_m` x `side_b_m` dentro de `polygon`
    (en cualquiera de las dos orientaciones)?

    Mismos TRES estados que `can_inscribe_square` (del que esta funcion
    es la generalizacion): True / False / None ("no verificable", nunca
    confundido con "aprobado").
    """
    if not _is_axis_or_rotated_rectangle(polygon):
        return None
    width, height = rectangle_side_lengths(polygon)
    return (width >= side_a_m and height >= side_b_m) or (width >= side_b_m and height >= side_a_m)


def can_inscribe_square(polygon: Polygon, side_length_m: float) -> Optional[bool]:
    """¿Cabe un cuadrado de `side_length_m` de lado dentro de `polygon`?
    Caso particular de `can_fit_rectangle` con los dos lados iguales."""
    return can_fit_rectangle(polygon, side_length_m, side_length_m)


def meets_minimum_width(polygon: Polygon, min_width_m: float) -> Optional[bool]:
    """Ancho libre entre paramentos enfrentados (A.3.2.1 / A.3.2.3): el
    lado MAS CORTO del rectangulo debe ser >= min_width_m. A diferencia
    de `can_fit_rectangle`, aqui el lado corto de LA PROPIA estancia es
    el que se mide directamente, no si cabe otra forma dentro."""
    if not _is_axis_or_rotated_rectangle(polygon):
        return None
    width, height = rectangle_side_lengths(polygon)
    return min(width, height) >= min_width_m


def count_exterior_sides(
    room_polygon: Polygon,
    lot_polygon: Polygon,
    min_contact_m: float = 0.3,
    excluded_segments: Optional[List[LineString]] = None,
) -> Optional[int]:
    """Cuenta cuantos de los 4 lados de `room_polygon` tienen contacto
    real con el limite de `lot_polygon` (al menos `min_contact_m` de
    borde compartido -- umbral distinto y mayor que el de adyacencia
    interior entre estancias, 0.1m, confirmado por el usuario para
    contacto con el exterior).

    `excluded_segments`: lados de la parcela que NO cuentan como
    contacto exterior real aunque toquen `lot_polygon.boundary` --
    retomado de docs/CONTINUIDAD.md ("vivienda pareada/adosada"): una
    pared de medianera (`Lot.medianera_boundary_segments()`) no tiene
    luz ni ventilacion propia, aunque geometricamente sea un "borde de
    la parcela" igual que cualquier otro. `None` (por defecto) preserva
    el comportamiento anterior sin cambios (vivienda aislada, todos los
    lados de la parcela cuentan).

    Devuelve None (no verificable) si `room_polygon` no es rectangular,
    igual que el resto de utilidades de este modulo -- nunca se asume
    un numero de lados exteriores sin poder confirmarlo geometricamente.
    """
    if not _is_axis_or_rotated_rectangle(room_polygon):
        return None

    mrr = room_polygon.minimum_rotated_rectangle
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
    """Evalua el ancho libre minimo (meets_minimum_width, 3 estados) de
    una estancia y devuelve (violaciones, avisos) -- listas de 0 o 1
    elemento cada una, listas para que el llamador haga
    `violations.extend(v); warnings.extend(w)`.

    `violation_message`/`warning_message` ya vienen formateados por
    completo por el llamador (incluido el umbral y cualquier referencia
    normativa) -- este helper solo antepone `'{room_id}': ` y decide
    cual de los dos usar segun el resultado de 3 estados. Diseño
    deliberadamente flexible tras un primer intento mas rigido (umbral
    siempre al final entre parentesis) que no encajaba con
    EscaleraAnchoLibreValidator, cuyo mensaje pone la referencia
    normativa DENTRO del mismo parentesis que el umbral.

    DUPLICACION REAL encontrada en auditoria (deteccion sistematica de
    bloques repetidos entre archivos, no solo intuicion): tres
    validadores distintos (pasillo A.3.2.3, escalera CTE DB-SUA 1,
    trastero B.2.5) repetian exactamente el manejo de los 3 estados de
    `meets_minimum_width`, solo cambiaba el umbral y el texto."""
    cumple = meets_minimum_width(polygon, threshold_m)
    if cumple is False:
        return ([f"'{room_id}': {violation_message}"], [])
    elif cumple is None:
        return ([], [f"'{room_id}': {warning_message}"])
    return ([], [])
