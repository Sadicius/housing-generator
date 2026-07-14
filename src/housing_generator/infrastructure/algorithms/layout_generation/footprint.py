"""Cálculo de la huella construible (footprint) dentro del área
edificable de la parcela -- a petición del usuario: la vivienda no
tiene por qué ocupar el 100% de la parcela, real como se sitúan las
viviendas unifamiliares de verdad (siempre queda jardín/patio
alrededor). El sobrante (VACIO) es exterior real, no una pieza más
del reparto de estancias -- ver [ARCH:area-objetivo].

Antes de esto, el árbol de partición llenaba SIEMPRE el 100% del área
edificable con el programa declarado -- si la parcela era mayor que
la suma de áreas, TODAS las estancias se inflaban proporcionalmente
para llenar el hueco (encontrado con un caso real: un Pasillo de
4.0m2 declarados generado más grande que un Dormitorio de 8.0m2).
"""
import math
from shapely.geometry import Polygon, box

FOOTPRINT_BUFFER = 0.15  # margen sobre la suma de areas declaradas -- NO
# normativo, criterio de ingenieria: da margen al recocido para
# satisfacer otras restricciones (adyacencia, contacto exterior...)
# sin inflar las estancias mas alla del +-15% de AreaObjetivoValidator.


def footprint_target_area(total_declared_area: float) -> float:
    """Área objetivo de la huella construible: suma de áreas
    declaradas + margen. Ver [ARCH:area-objetivo]."""
    return total_declared_area * (1 + FOOTPRINT_BUFFER)


def clamp_footprint_width(width: float, footprint_area: float, buildable_w: float, buildable_h: float) -> float:
    """Ancho de huella válido: la huella (width x area/width) debe
    caber dentro del área edificable en ambas dimensiones."""
    min_width = footprint_area / buildable_h  # si width fuera menor, el alto excederia buildable_h
    max_width = buildable_w
    min_width = min(min_width, max_width)  # seguridad si el area no cabe de ningun modo
    return min(max_width, max(min_width, width))


def footprint_rectangle(
    buildable_polygon: Polygon, footprint_width: float, footprint_area: float, entrance_side: str,
) -> Polygon:
    """Rectángulo de la huella construible, del tamaño y proporción
    dados, anclado al lado de entrada de la parcela (la vivienda hacia
    la calle, el vacío detrás/alrededor -- confirmado explícitamente).
    Centrado en el eje perpendicular al de anclaje."""
    minx, miny, maxx, maxy = buildable_polygon.bounds
    buildable_w, buildable_h = maxx - minx, maxy - miny

    width = clamp_footprint_width(footprint_width, footprint_area, buildable_w, buildable_h)
    height = min(buildable_h, footprint_area / width)

    if entrance_side == "south":
        x0 = minx + (buildable_w - width) / 2
        y0 = miny
    elif entrance_side == "north":
        x0 = minx + (buildable_w - width) / 2
        y0 = maxy - height
    elif entrance_side == "west":
        x0 = minx
        y0 = miny + (buildable_h - height) / 2
    else:  # "east"
        x0 = maxx - width
        y0 = miny + (buildable_h - height) / 2

    return box(x0, y0, x0 + width, y0 + height)


FOOTPRINT_RESIZE_STEP = 0.15  # perturbacion relativa maxima del ancho de huella por movimiento


def resize_footprint_width(
    current_width: float, footprint_area: float, buildable_w: float, buildable_h: float, rng,
) -> float:
    """Perturba el ancho de huella (recocido simulado) -- el alto se
    deriva para mantener el area objetivo constante, dentro de los
    limites de la parcela edificable."""
    delta = rng.uniform(-FOOTPRINT_RESIZE_STEP, FOOTPRINT_RESIZE_STEP)
    proposed = current_width * (1 + delta)
    return clamp_footprint_width(proposed, footprint_area, buildable_w, buildable_h)


def initial_footprint_width(footprint_area: float, buildable_w: float, buildable_h: float) -> float:
    """Ancho de huella inicial: lo mas cercano a cuadrado que quepa en
    la parcela edificable, punto de partida razonable para la
    busqueda (que luego explora otras proporciones)."""
    square_width = math.sqrt(footprint_area)
    return clamp_footprint_width(square_width, footprint_area, buildable_w, buildable_h)
