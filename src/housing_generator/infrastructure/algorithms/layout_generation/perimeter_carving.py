"""Tallado perimetral (space allocation problem, "periferia hacia el
centro"): dado un polígono de trabajo y las estancias que necesitan
contacto exterior (`Room.min_exterior_sides>=1`), talla sus huellas
desde el borde hacia dentro -- garantiza el contacto exterior por
CONSTRUCCIÓN en vez de perseguirlo por búsqueda ciega, mismo principio
ya probado con `force_aspect_ratio`/anclaje de la escalera compartida
(`btree_partition.py`, `btree_layout_generator.py`). Geometría pura,
determinista, sin recocido simulado ni dependencia de `Program`/
`Layout` -- ver docs/referencia/generador/contacto-exterior-y-envolvente.md
y [ARCH:perimeter-carving].

Estado: Fase 1 del rediseño (geometría de tallado aislada, aún no
conectada al pipeline de generación real). v2: profundidad VARIABLE
por estancia (no banda uniforme por lado) -- corregido tras una
revisión visual real con el usuario: la v1 ("banda uniforme por
lado", ver historial git) forzaba a TODAS las estancias de un mismo
lado a compartir una única profundidad calculada como
`area_total_del_lado / longitud_disponible`, lo que producía formas
absurdas (cocina 1.9x5.2m, dormitorio 6.5x1.5m, ratio 4.2:1) en
cuanto el lote no estaba dimensionado exactamente al programa --
confirmado con números reales, no solo intuición. GFLAN (arxiv
2512.16275, Fig. 1 y Sección 3.1) confirma además que la circulación
NO se predice como pieza propia -- es el área residual tras restar
las estancias del envolvente (`R_living = B \\ Union(R_i)`) -- misma
idea que el núcleo de este módulo.

v2: cada estancia recibe su propia profundidad "ideal" (área +
proporción objetivo `TARGET_ASPECT_RATIO`, acotada por el ancho libre
MÍNIMO real de su tipo -- reutiliza las constantes YA normativas de
`ancho_libre_estancia_validator.py` -- A.3.2.1 -- y las NO normativas
de `ancho_libre_practico_validator.py`, no reinventa umbrales), y se
calibra por bisección contra el área REAL disponible en el polígono
de trabajo (generaliza `_solve_band_depth` de la v1 a nivel de
estancia individual, no de lado completo) -- necesario tanto para
`area_edificable_real` irregular como para el propio hueco que deja
una estancia vecina ya tallada. El núcleo YA NO está garantizado como
rectángulo (puede quedar con forma escalonada/en L cerca de estancias
de profundidad muy distinta en el mismo lado) -- consecuencia
aceptada, más realista que forzar una banda uniforme; sigue estando
protegido por `RoomOverlapValidator` (Fase 0) como red de seguridad.
"""
import math
from typing import Dict, FrozenSet, List, Tuple
from shapely.geometry import Polygon, box
from housing_generator.domain.entities.lot import clasificar_lado_cardinal
from housing_generator.domain.entities.room import Room
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_estancia_validator import (
    ANCHO_LIBRE_ESTANCIA_MAYOR_M,
    ANCHO_LIBRE_DORMITORIO_DOBLE_M,
    ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M,
    ANCHO_LIBRE_COCINA_M,
    DORMITORIO_DOBLE_AREA_UMBRAL_M2,
)
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_practico_validator import (
    ANCHO_LIBRE_PRACTICO_M,
    ANCHO_LIBRE_REDUCIDO_M,
    TIPOS_CON_ANCHO_REDUCIDO,
)

CARDINAL_SIDES = ("south", "east", "north", "west")

# Proporcion "comoda" objetivo (ni cuadrada ni alargada) para el lado
# corto (profundidad) frente al largo (frente) de cada estancia
# perimetral -- NO normativa (el Decreto 29/2010 no fija proporciones
# ideales, solo un ancho libre minimo por tipo y un maximo de 2.5:1
# via ProporcionMaximaValidator/Dimensions.max_aspect_ratio). Elegida
# como punto de partida razonable, acotada siempre por ambos limites
# reales de abajo -- sustituible sin romper el resto de la
# arquitectura. Ver [ARCH:perimeter-carving].
TARGET_ASPECT_RATIO = 1.4

_DORMITORIO_TYPES = {RoomType.BEDROOM, RoomType.MASTER_BEDROOM}


def _min_width_for_room(room: Room) -> float:
    """Ancho libre mínimo real para `room.room_type`, reutilizando las
    constantes ya citadas de A.3.2.1 (`ancho_libre_estancia_validator.py`)
    y las prácticas NO normativas (`ancho_libre_practico_validator.py`)
    -- no introduce ningún umbral nuevo. Ver [ARCH:perimeter-carving]."""
    if room.room_type == RoomType.LIVING_ROOM:
        return ANCHO_LIBRE_ESTANCIA_MAYOR_M
    if room.room_type in _DORMITORIO_TYPES:
        return (
            ANCHO_LIBRE_DORMITORIO_DOBLE_M
            if room.dimensions.area_m2 >= DORMITORIO_DOBLE_AREA_UMBRAL_M2
            else ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M
        )
    if room.room_type == RoomType.KITCHEN:
        return ANCHO_LIBRE_COCINA_M
    if room.room_type in TIPOS_CON_ANCHO_REDUCIDO:
        return ANCHO_LIBRE_REDUCIDO_M
    return ANCHO_LIBRE_PRACTICO_M


def _ideal_room_footprint(room: Room, aspect_ratio_override: float = None) -> Tuple[float, float]:
    """(profundidad, frente) "ideal" de `room`: área declarada
    repartida a `TARGET_ASPECT_RATIO` (o `aspect_ratio_override` si se
    da -- usado por las mutaciones de `perimeter_core_partition.py`,
    Fase 2, para perturbar la proporción de una estancia concreta sin
    tocar esta función), con la profundidad nunca por debajo del ancho
    libre mínimo real de su tipo, y la proporción resultante nunca por
    encima de `room.dimensions.max_aspect_ratio` (2.5 por defecto, ya
    normativo del proyecto). Ver [ARCH:perimeter-carving]."""
    area = room.dimensions.area_m2
    base_ar = aspect_ratio_override if aspect_ratio_override is not None else TARGET_ASPECT_RATIO
    target_ar = min(base_ar, room.dimensions.max_aspect_ratio)
    depth = math.sqrt(area / target_ar)

    min_width = _min_width_for_room(room)
    if depth < min_width:
        depth = min_width

    frontage = area / depth
    if frontage / depth > room.dimensions.max_aspect_ratio:
        depth = math.sqrt(area / room.dimensions.max_aspect_ratio)
        frontage = area / depth

    return depth, frontage


def tallable_length_per_side(polygon: Polygon, medianera_sides: FrozenSet[str]) -> Dict[str, float]:
    """Longitud real de los lados del polígono clasificados por
    dirección cardinal (mismo criterio que `Lot.frente_actual_m`),
    excluyendo los tramos en `medianera_sides` -- nunca tallables,
    igual que en `ExteriorContactValidator`/`count_exterior_sides`.
    Usado solo para decidir a qué lado se asigna cada estancia
    (heurística de reparto), no para la construcción geométrica final."""
    coords = list(polygon.exterior.coords)[:-1]
    centroide = polygon.centroid
    lengths = {side: 0.0 for side in CARDINAL_SIDES}
    n = len(coords)
    for i in range(n):
        p1, p2 = coords[i], coords[(i + 1) % n]
        side = clasificar_lado_cardinal(p1, p2, centroide)
        if side in medianera_sides:
            continue
        lengths[side] += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
    return lengths


def assign_rooms_to_sides(
    rooms: List[Room], tallable_length: Dict[str, float], entrance_side: str,
) -> Dict[str, List[str]]:
    """Reparte `rooms` entre los lados con longitud tallable>0, por
    `room.id` (no por objeto `Room` -- mismo convenio que `BStarNode`
    del núcleo, que solo guarda `room_id`, para que este reparto sea
    directamente el estado inicial mutable de
    `perimeter_core_partition.py::PerimeterState`, Fase 2).
    `ENTRANCE_HALL` va siempre a `entrance_side` (conserva el
    comportamiento de anclaje por entrada que ya funciona bien hoy).
    El resto, en orden de FRENTE ideal descendente (`_ideal_room_footprint`,
    no área bruta -- v2), al lado con MENOR carga relativa (frente ya
    asignado / longitud tallable) -- aproxima cuánta longitud de
    fachada consumirá cada estancia según su propia forma, no según un
    reparto de área que asumía una banda compartida (v1). Heurística
    de ingeniería, NO derivada de la literatura SAP citada en el
    documento de referencia -- primera hipótesis a validar
    empíricamente, sustituible sin romper el resto de la arquitectura.
    Ver [ARCH:perimeter-carving]."""
    available_sides = [side for side in CARDINAL_SIDES if tallable_length[side] > 0]
    if not available_sides:
        raise ValueError(
            "ningun lado del poligono de trabajo tiene longitud tallable "
            "(todos en medianera) -- no se puede tallar el perimetro"
        )

    assignment: Dict[str, List[str]] = {side: [] for side in CARDINAL_SIDES}
    load: Dict[str, float] = {side: 0.0 for side in CARDINAL_SIDES}

    remaining = list(rooms)
    entrance_rooms = [r for r in remaining if r.room_type == RoomType.ENTRANCE_HALL]
    remaining = [r for r in remaining if r.room_type != RoomType.ENTRANCE_HALL]

    entrance_target = entrance_side if entrance_side in available_sides else available_sides[0]
    for room in entrance_rooms:
        _, frontage = _ideal_room_footprint(room)
        assignment[entrance_target].append(room.id)
        load[entrance_target] += frontage

    ideal = {room.id: _ideal_room_footprint(room) for room in remaining}
    for room in sorted(remaining, key=lambda r: ideal[r.id][1], reverse=True):
        side = min(available_sides, key=lambda s: load[s] / tallable_length[s])
        assignment[side].append(room.id)
        load[side] += ideal[room.id][1]

    return assignment


def _room_box(
    side: str, offset: float, frontage: float, depth: float,
    minx: float, miny: float, maxx: float, maxy: float,
) -> Polygon:
    """Rectángulo de una estancia individual, con su cara exterior
    pegada al lado `side` del rectángulo de trabajo actual y su
    extensión tangencial en `[offset, offset+frontage]`."""
    if side == "south":
        return box(offset, miny, offset + frontage, miny + depth)
    elif side == "north":
        return box(offset, maxy - depth, offset + frontage, maxy)
    elif side == "west":
        return box(minx, offset, minx + depth, offset + frontage)
    else:  # east
        return box(maxx - depth, offset, maxx, offset + frontage)


def _solve_room_depth(
    side: str, offset: float, frontage: float, target_area: float,
    remaining: Polygon, minx: float, miny: float, maxx: float, maxy: float,
    initial_depth: float, tol: float = 1e-4, max_iter: int = 40,
) -> float:
    """Profundidad que hace que `_room_box(...).intersection(remaining)`
    tenga área `target_area`, por bisección a partir de `initial_depth`
    -- generaliza `_solve_band_depth` (v1) a nivel de estancia
    individual: hace falta tanto contra un `area_edificable_real`
    irregular como contra el hueco que deja una estancia VECINA ya
    tallada en el mismo lado. Ver [ARCH:perimeter-carving]."""
    lo, hi = 0.0, max(initial_depth, 0.5)
    for _ in range(max_iter):
        if _room_box(side, offset, frontage, hi, minx, miny, maxx, maxy).intersection(remaining).area >= target_area:
            break
        hi *= 1.5
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        area = _room_box(side, offset, frontage, mid, minx, miny, maxx, maxy).intersection(remaining).area
        if abs(area - target_area) <= tol:
            return mid
        if area < target_area:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def carve_from_assignment(
    polygon: Polygon,
    rooms_by_id: Dict[str, Room],
    assignment: Dict[str, List[str]],
    entrance_side: str,
    aspect_overrides: Dict[str, float] = None,
) -> Tuple[Dict[str, Polygon], Polygon]:
    """Construcción geométrica real del tallado, dado un `assignment`
    YA DECIDIDO (lado -> `room_id`s en orden tangencial) -- extraído
    de `carve_perimeter` en la Fase 2 para que
    `perimeter_core_partition.py` pueda materializar un
    `PerimeterState` mutado (tras `move_to_side`/`resize_room`/etc.)
    sin volver a decidir el reparto desde cero cada vez.
    `aspect_overrides`: `room_id` -> proporción objetivo distinta de
    `TARGET_ASPECT_RATIO` (usado por `resize_room`, Fase 2) -- `None`
    o ausencia de una clave concreta usa el valor por defecto.

    Orden de procesado de lados: `entrance_side` primero (prioridad
    arquitectónica, coherente con el anclaje por entrada ya usado en
    `_anchor_offset`), luego el resto en rotación fija
    sur->este->norte->oeste -- cada lado, al procesarse, recorta el
    rectángulo de trabajo restante por la profundidad MÁXIMA de sus
    propias estancias (evita solape de esquina entre lados adyacentes:
    el primero en procesarse se queda la esquina compartida). Dentro
    de un mismo lado, cada estancia se resta de `remaining` antes de
    calcular la siguiente -- no-solape garantizado por construcción,
    igual que entre lados. Ver [ARCH:perimeter-carving].
    """
    overrides = aspect_overrides or {}
    base_order = list(CARDINAL_SIDES)
    start = base_order.index(entrance_side) if entrance_side in base_order else 0
    order = base_order[start:] + base_order[:start]

    minx, miny, maxx, maxy = polygon.bounds
    remaining = polygon
    bites: Dict[str, Polygon] = {}

    for side in order:
        side_room_ids = assignment.get(side, [])
        if not side_room_ids:
            continue

        tangential_start = minx if side in ("south", "north") else miny
        offset = tangential_start
        depths: List[float] = []

        for room_id in side_room_ids:
            room = rooms_by_id[room_id]
            ideal_depth, frontage = _ideal_room_footprint(room, overrides.get(room_id))
            depth = _solve_room_depth(
                side, offset, frontage, room.dimensions.area_m2,
                remaining, minx, miny, maxx, maxy, ideal_depth,
            )
            room_box = _room_box(side, offset, frontage, depth, minx, miny, maxx, maxy)
            bites[room_id] = room_box.intersection(remaining)
            remaining = remaining.difference(room_box)
            depths.append(depth)
            offset += frontage

        max_depth = max(depths)
        if side == "south":
            miny += max_depth
        elif side == "north":
            maxy -= max_depth
        elif side == "west":
            minx += max_depth
        else:  # east
            maxx -= max_depth

    return bites, remaining


def carve_perimeter(
    polygon: Polygon,
    rooms: List[Room],
    medianera_sides: FrozenSet[str] = frozenset(),
    entrance_side: str = "south",
) -> Tuple[Dict[str, Polygon], Polygon]:
    """Talla `rooms` (se asume ya filtradas a `min_exterior_sides>=1`
    por el llamante) contra el borde de `polygon`, de fuera hacia
    dentro. Devuelve `(bites, core)`: `bites` mapea `room.id` -> su
    huella (`Polygon`), `core` es el polígono residual para el
    empaquetado de núcleo (`min_exterior_sides==0`). Lista vacía de
    `rooms` devuelve `({}, polygon)` sin tocar nada.

    Envoltorio de conveniencia: decide el reparto inicial
    (`assign_rooms_to_sides`) y delega la construcción real en
    `carve_from_assignment` -- ver esa función para el algoritmo (v2,
    profundidad variable por estancia). Ver [ARCH:perimeter-carving].
    """
    if not rooms:
        return {}, polygon

    rooms_by_id = {room.id: room for room in rooms}
    tallable_length = tallable_length_per_side(polygon, medianera_sides)
    assignment = assign_rooms_to_sides(rooms, tallable_length, entrance_side)
    return carve_from_assignment(polygon, rooms_by_id, assignment, entrance_side)
