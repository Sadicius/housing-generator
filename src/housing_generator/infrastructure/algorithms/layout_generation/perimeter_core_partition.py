"""Fase 2 del rediseño "periferia hacia el centro": estado MUTABLE
para el tallado perimetral (`PerimeterState`), sus 5 mutaciones --
espejo funcional 1:1 de las 5 que ya tiene `btree_partition.py` para
el núcleo, mismo estilo de copia inmutable (cada mutación devuelve un
estado NUEVO, no muta in-place) -- e integración con el árbol B* del
núcleo (reutilizado SIN CAMBIOS). `materialize_perimeter_core` es una
función PURA que, dado un estado, produce un `Layout` completo
(perímetro + núcleo) -- todavía sin recocido simulado ni wiring a
`container.py`/`GenerateBuildingUseCase` (eso es la Fase 3). Ver
docs/referencia/generador/contacto-exterior-y-envolvente.md,
[ARCH:perimeter-core-partition].

Motivación: la Fase 1 (`perimeter_carving.py::carve_perimeter`) es una
única pasada determinista -- documentó un caso conocido, no resuelto
a propósito, donde dos lados perpendiculares con estancias profundas
comprimen el tramo tangencial de un tercer lado, dejando a una
estancia con menos área de la declarada. `move_to_side`/`swap_sides`
son exactamente el mecanismo que permitiría a una búsqueda futura
(Fase 3) escapar de ese caso.
"""
import copy
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.ops import unary_union

from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.enums import RoomType
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.infrastructure.algorithms.layout_generation.perimeter_carving import (
    TARGET_ASPECT_RATIO,
    tallable_length_per_side,
    assign_rooms_to_sides,
    carve_from_assignment,
)
from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
    BStarNode,
    build_random_tree,
    compute_positions,
    random_neighbor,
)


@dataclass
class PerimeterState:
    """Estado mutable del tallado perimetral: qué `room_id` ocupa cada
    lado cardinal y en qué orden tangencial (determina vecindad de
    esquina), más las proporciones perturbadas respecto a
    `TARGET_ASPECT_RATIO` (ausencia de clave = usa el valor por
    defecto). Ver [ARCH:perimeter-core-partition]."""
    assignment: Dict[str, List[str]]
    aspect_overrides: Dict[str, float] = field(default_factory=dict)


@dataclass
class PerimeterCoreState:
    """Estado combinado: tallado perimetral + árbol B* del núcleo
    (`None` si el programa no tiene ninguna estancia
    `min_exterior_sides==0`). Ver [ARCH:perimeter-core-partition]."""
    perimeter: PerimeterState
    core_tree: Optional[BStarNode]


def find_entrance_hall_id(program: Program) -> Optional[str]:
    """Primera estancia ENTRANCE_HALL del programa, o `None` -- mismo
    patrón que `BTreeLayoutGenerator._stair_room_id`."""
    return next((r.id for r in program.rooms if r.room_type == RoomType.ENTRANCE_HALL), None)


def build_initial_perimeter_core_state(
    program: Program, lot: Lot, rng: random.Random,
) -> PerimeterCoreState:
    """Estado inicial: reparto perimetral vía `assign_rooms_to_sides`
    (Fase 1, sin cambios) + árbol B* aleatorio para las estancias de
    núcleo (`min_exterior_sides==0`, mismo `build_random_tree` que ya
    usa `BTreeLayoutGenerator`). `core_tree` es `None` si el programa
    no tiene ninguna estancia de núcleo -- caso legítimo (programas
    muy pequeños), no un error."""
    perimeter_rooms = [r for r in program.rooms if r.min_exterior_sides > 0]
    core_rooms = [r for r in program.rooms if r.min_exterior_sides == 0]

    polygon = lot.area_edificable_real.polygon
    tallable = tallable_length_per_side(polygon, lot.medianera_sides)
    assignment = assign_rooms_to_sides(perimeter_rooms, tallable, lot.entrance_side)
    perimeter_state = PerimeterState(assignment=assignment, aspect_overrides={})

    core_tree = build_random_tree([r.id for r in core_rooms], rng) if core_rooms else None

    return PerimeterCoreState(perimeter=perimeter_state, core_tree=core_tree)


def _find_side(state: PerimeterState, room_id: str) -> Tuple[str, int]:
    for side, ids in state.assignment.items():
        if room_id in ids:
            return side, ids.index(room_id)
    raise ValueError(f"'{room_id}' no esta en el estado perimetral")


def swap_sides(state: PerimeterState, id_a: str, id_b: str) -> PerimeterState:
    """Espejo de `swap_modules` (núcleo): intercambia qué estancia
    ocupa cada posición (lado + índice) -- la estructura de listas no
    cambia, solo la identidad en cada hueco."""
    nuevo = copy.deepcopy(state)
    side_a, idx_a = _find_side(nuevo, id_a)
    side_b, idx_b = _find_side(nuevo, id_b)
    nuevo.assignment[side_a][idx_a] = id_b
    nuevo.assignment[side_b][idx_b] = id_a
    return nuevo


def move_to_side(
    state: PerimeterState, room_id: str, rng: random.Random, available_sides: List[str],
) -> PerimeterState:
    """Espejo de `move_module` (núcleo): saca la estancia de su lado
    actual y la inserta en una posición aleatoria de OTRO lado --
    ataca directamente el caso conocido de la Fase 1 (estancia
    comprimida por lados perpendiculares profundos). No-op si solo hay
    un lado disponible. El llamante es responsable de no pasar el
    `room_id` de `ENTRANCE_HALL` aquí (permanece anclado a
    `entrance_side`, mismo principio que protege la escalera
    compartida entre plantas)."""
    nuevo = copy.deepcopy(state)
    current_side, idx = _find_side(nuevo, room_id)
    otros = [s for s in available_sides if s != current_side]
    if not otros:
        return nuevo
    nuevo.assignment[current_side].pop(idx)
    destino = rng.choice(otros)
    posicion = rng.randint(0, len(nuevo.assignment[destino]))
    nuevo.assignment[destino].insert(posicion, room_id)
    return nuevo


def resize_room(state: PerimeterState, room_id: str, rng: random.Random, step: float = 0.15) -> PerimeterState:
    """Espejo de `resize_module` (núcleo): perturba la proporción
    objetivo de una estancia multiplicativamente (mismo `step` ±15%,
    mismo clamp `[0.05, 20]`)."""
    nuevo = copy.deepcopy(state)
    actual = nuevo.aspect_overrides.get(room_id, TARGET_ASPECT_RATIO)
    factor = 1 + rng.uniform(-step, step)
    nuevo.aspect_overrides[room_id] = max(0.05, min(20.0, actual * factor))
    return nuevo


def reset_room_aspect_ratio(state: PerimeterState, room_id: str) -> PerimeterState:
    """Espejo de `reset_aspect_ratio` (núcleo): deshace la deriva
    acumulada de varios `resize_room`, volviendo a `TARGET_ASPECT_RATIO`
    (elimina el override; no-op si no había ninguno)."""
    nuevo = copy.deepcopy(state)
    nuevo.aspect_overrides.pop(room_id, None)
    return nuevo


def reorder_within_side(state: PerimeterState, side: str, rng: random.Random) -> PerimeterState:
    """Espejo de `swap_children` (núcleo): intercambia dos posiciones
    dentro del mismo lado -- movimiento local, más barato que
    `move_to_side`. No-op si el lado tiene menos de 2 estancias."""
    nuevo = copy.deepcopy(state)
    ids = nuevo.assignment[side]
    if len(ids) < 2:
        return nuevo
    i, j = rng.sample(range(len(ids)), 2)
    ids[i], ids[j] = ids[j], ids[i]
    return nuevo


def random_neighbor_perimeter(
    state: PerimeterState, rng: random.Random,
    entrance_hall_id: Optional[str], available_sides: List[str],
) -> PerimeterState:
    """Genera un estado perimetral vecino eligiendo uno de los 5
    movimientos al azar -- mismo patrón que `random_neighbor` del
    núcleo. `entrance_hall_id` queda excluido de `move`/`swap`
    (permanece anclado a `entrance_side`)."""
    all_ids = [rid for ids in state.assignment.values() for rid in ids]
    movable_ids = [rid for rid in all_ids if rid != entrance_hall_id]
    sides_with_2_plus = [s for s, ids in state.assignment.items() if len(ids) >= 2]

    posibles = ["resize", "reset"]
    if movable_ids and len(available_sides) >= 2:
        posibles.append("move")
    if len(movable_ids) >= 2:
        posibles.append("swap")
    if sides_with_2_plus:
        posibles.append("reorder")

    move = rng.choice(posibles)
    if move == "resize":
        return resize_room(state, rng.choice(all_ids), rng)
    elif move == "reset":
        return reset_room_aspect_ratio(state, rng.choice(all_ids))
    elif move == "move":
        return move_to_side(state, rng.choice(movable_ids), rng, available_sides)
    elif move == "swap":
        id_a, id_b = rng.sample(movable_ids, 2)
        return swap_sides(state, id_a, id_b)
    else:  # reorder
        return reorder_within_side(state, rng.choice(sides_with_2_plus), rng)


def random_neighbor_perimeter_core(
    state: PerimeterCoreState, rng: random.Random, areas: Dict[str, float],
    entrance_hall_id: Optional[str], available_sides: List[str],
    locked_room_ids: Optional[Set[str]] = None,
) -> PerimeterCoreState:
    """Combina las mutaciones de perímetro y núcleo: elige al azar
    (50/50) cuál de los dos mutar. Si no hay estancias de núcleo
    (`core_tree is None`), muta siempre el perímetro. El núcleo se
    muta con `random_neighbor` de `btree_partition.py` SIN NINGÚN
    cambio -- `locked_room_ids` se filtra a solo los `room_id` que
    existen en `core_tree` (bug real encontrado al conectar esta
    función a un generador real: `locked_room_ids` incluye estancias
    PERIMETRALES, que `compute_positions(core_tree, ...)` no conoce --
    `random_neighbor` lanzaba `KeyError` al intentar comprobar si una
    de ellas se había desplazado)."""
    if state.core_tree is not None and rng.random() < 0.5:
        core_ids = {node.room_id for node in state.core_tree.nodes()}
        core_locked = (locked_room_ids or set()) & core_ids
        nuevo_core = random_neighbor(state.core_tree, rng, areas, core_locked)
        return PerimeterCoreState(perimeter=state.perimeter, core_tree=nuevo_core)
    nuevo_perimetro = random_neighbor_perimeter(state.perimeter, rng, entrance_hall_id, available_sides)
    return PerimeterCoreState(perimeter=nuevo_perimetro, core_tree=state.core_tree)


def _center_within(container_bounds: Tuple[float, float, float, float], content_bounds: Tuple[float, float, float, float]) -> Tuple[float, float]:
    """Desplazamiento para centrar `content_bounds` dentro de
    `container_bounds` -- mismo cálculo de centrado que
    `BTreeLayoutGenerator._anchor_offset`, sin preferencia de lado (el
    núcleo no tiene `entrance_side` propio)."""
    cminx, cminy, cmaxx, cmaxy = container_bounds
    pminx, pminy, pmaxx, pmaxy = content_bounds
    x0 = cminx + ((cmaxx - cminx) - (pmaxx - pminx)) / 2
    y0 = cminy + ((cmaxy - cminy) - (pmaxy - pminy)) / 2
    return x0 - pminx, y0 - pminy


def _residual_pieces(residual: Polygon) -> List[Polygon]:
    """El residuo puede quedar fragmentado en varias piezas
    desconectadas (hallazgo real: con profundidad variable por
    estancia -- v2 --, un lado con una estancia más superficial que
    sus vecinas deja una muesca hacia el borde, separada del bloque
    central por el resto de lados ya tallados a su propia profundidad
    máxima). Devuelve las piezas ordenadas por área descendente (vacío
    si el residuo está vacío). Ver [ARCH:perimeter-core-partition]."""
    if residual.is_empty:
        return []
    if residual.geom_type == "MultiPolygon":
        return sorted(residual.geoms, key=lambda g: -g.area)
    return [residual]


def _assign_core_rooms_to_pieces(
    ordered_room_ids: List[str], rooms_by_id: Dict, pieces: List[Polygon],
) -> List[List[str]]:
    """Reparte las estancias de núcleo entre las piezas del residuo --
    NO como un solo bloque (hallazgo real de esta Fase 2: un bloque
    único, centrado contra la pieza más grande, se solapaba con el
    perímetro casi siempre). Mismo patrón de reparto por carga relativa
    que `assign_rooms_to_sides` (Fase 1), adaptado de "lado con más
    longitud tallable" a "pieza con más área libre". El ORDEN de
    `ordered_room_ids` importa: se espera la traversal del propio
    `core_tree` (`BStarNode.nodes()`, pre-orden) para que las
    mutaciones de topología (`swap_modules`/`move_module`, sin cambios)
    puedan cambiar qué pieza recibe cada estancia -- no solo su forma.
    Ver [ARCH:perimeter-core-partition]."""
    groups: List[List[str]] = [[] for _ in pieces]
    load = [0.0] * len(pieces)
    for room_id in ordered_room_ids:
        area = rooms_by_id[room_id].dimensions.area_m2
        idx = min(range(len(pieces)), key=lambda i: load[i] / pieces[i].area)
        groups[idx].append(room_id)
        load[idx] += area
    return groups


def _chain_tree(room_ids: List[str], aspect_ratios: Dict[str, float]) -> BStarNode:
    """Árbol B* mínimo (cadena simple por `left`) para un grupo de
    estancias YA decidido -- preserva la `aspect_ratio` de cada una
    (efecto de `resize_room`/`resize_module` sobre el `core_tree`
    global), a diferencia de reconstruir con `build_random_tree`
    (que perdería esa perturbación, reiniciando a 1.0). La topología
    en cadena no importa aquí -- cada grupo se empaqueta y ancla de
    forma independiente, no hay relación geométrica entre grupos de
    piezas distintas. Ver [ARCH:perimeter-core-partition]."""
    root = BStarNode(room_id=room_ids[0], aspect_ratio=aspect_ratios.get(room_ids[0], 1.0))
    actual = root
    for room_id in room_ids[1:]:
        siguiente = BStarNode(room_id=room_id, aspect_ratio=aspect_ratios.get(room_id, 1.0))
        actual.left = siguiente
        actual = siguiente
    return root


def materialize_perimeter_core(state: PerimeterCoreState, program: Program, lot: Lot) -> Layout:
    """Produce un `Layout` completo a partir de `state`: talla el
    perímetro (`carve_from_assignment`, Fase 1, sin cambios en su
    algoritmo) y reparte el núcleo entre las piezas del residuo
    (`_residual_pieces`/`_assign_core_rooms_to_pieces`) -- NO como un
    solo bloque B* centrado en la pieza más grande (primer intento de
    esta Fase 2: se solapaba con el perímetro casi siempre, porque el
    residuo suele quedar FRAGMENTADO en varias piezas desconectadas
    con profundidad variable por estancia). Cada pieza recibe su
    propio sub-grupo de estancias (`_chain_tree`, preserva
    `aspect_ratio` de `state.core_tree`), empaquetado y centrado de
    forma independiente contra ESA pieza.

    Sigue sin haber garantía de que el núcleo encaje sin solape --
    esta función es un único intento determinista, SIN búsqueda (a
    diferencia de `BTreeLayoutGenerator.generate()`, que prueba miles
    de candidatos y rechaza los que violan restricciones duras). Aquí
    no hay bucle que rechace nada: `RoomOverlapValidator`/
    `ParcelaRealValidator` son quienes detectan el problema, no esta
    función quien lo evita. Resolverlo de verdad (que el núcleo
    SIEMPRE encaje) es trabajo del recocido simulado de la Fase 3 --
    exactamente el tipo de caso que `move_to_side`/`resize_room`
    (este módulo) existen para poder corregir por búsqueda. Sin
    `reference_stair` (multi-planta, Fase 4, fuera de alcance aquí).
    Ver [ARCH:perimeter-core-partition].
    """
    rooms_by_id = {room.id: room for room in program.rooms}
    polygon = lot.area_edificable_real.polygon

    perimeter_bites, core_residual = carve_from_assignment(
        polygon, rooms_by_id, state.perimeter.assignment, lot.entrance_side,
        state.perimeter.aspect_overrides,
    )
    placed_polygons: Dict[str, Polygon] = dict(perimeter_bites)

    if state.core_tree is not None:
        pieces = _residual_pieces(core_residual)
        if pieces:
            ordered_room_ids = [node.room_id for node in state.core_tree.nodes()]
            aspect_ratios = {node.room_id: node.aspect_ratio for node in state.core_tree.nodes()}
            groups = _assign_core_rooms_to_pieces(ordered_room_ids, rooms_by_id, pieces)

            for piece, group_room_ids in zip(pieces, groups):
                if not group_room_ids:
                    continue
                group_tree = _chain_tree(group_room_ids, aspect_ratios)
                group_areas = {rid: rooms_by_id[rid].dimensions.area_m2 for rid in group_room_ids}
                group_positions = compute_positions(group_tree, group_areas)
                offset_x, offset_y = _center_within(
                    piece.bounds, unary_union(list(group_positions.values())).bounds,
                )
                for room_id, poly in group_positions.items():
                    placed_polygons[room_id] = translate(poly, offset_x, offset_y)

    placed_rooms = []
    for room in program.rooms:
        placed = copy.copy(room)  # copia superficial: no muta el Room del Program original
        placed.boundary = Boundary(polygon=placed_polygons[room.id])
        placed_rooms.append(placed)

    zones_map: Dict = {}
    for room in placed_rooms:
        zones_map.setdefault(room.zone, []).append(room.id)
    built_zones = [Zone(zone_type=zone_type, room_ids=ids) for zone_type, ids in zones_map.items()]

    return Layout(lot=lot, rooms=placed_rooms, zones=built_zones)
