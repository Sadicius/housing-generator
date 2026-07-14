"""Arbol de particion recursivo (slicing tree) para distribuir TODAS las
estancias de un programa en un solar de una sola vez, sin una fase previa
de reparto por macro-zona geometrica.

Cada hoja del arbol contiene una estancia; cada nodo interno divide su
rectangulo en dos, en horizontal o vertical, con una proporcion
determinada por el area total de estancias de cada subarbol. Es la
representacion clasica de "slicing floorplan" usada en floorplanning
(particion guillotina): cualquier arbol binario con una direccion de
corte por nodo interno se traduce en una planta rectangular valida sin
solapes ni huecos.
"""
import copy
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from shapely.geometry import Polygon, box


@dataclass
class PartitionNode:
    """Nodo del árbol. Una hoja tiene `room_id`; un nodo interno tiene
    `direction` y dos subárboles `first`/`second`.

    `direction`: None = automática (minimiza la peor proporción
    ancho:alto del corte). "h"/"v" fuerza esa dirección, usado por
    `flip_direction` para explorar topologías no automáticas.
    `ratio_override`: proporción del corte forzada manualmente (0-1,
    fracción de `first`), en vez de derivarla del área declarada.

    [ARCH:partition-node]
    """
    room_id: Optional[str] = None
    direction: Optional[str] = None
    first: Optional["PartitionNode"] = None
    second: Optional["PartitionNode"] = None
    ratio_override: Optional[float] = None

    @property
    def is_leaf(self) -> bool:
        return self.room_id is not None

    def leaves(self) -> List["PartitionNode"]:
        if self.is_leaf:
            return [self]
        # invariante mantenida por construccion (build_random_tree,
        # random_neighbor): un nodo NO-hoja siempre tiene first/second.
        # mypy no puede demostrarlo solo (Python no tiene "tipos suma"
        # nativos para esto) -- el assert documenta la invariante Y le
        # da a mypy la informacion de estrechamiento de tipo que necesita.
        assert self.first is not None and self.second is not None, \
            "Nodo interno sin first/second -- invariante del arbol violada"
        return self.first.leaves() + self.second.leaves()

    def internal_nodes(self) -> List["PartitionNode"]:
        if self.is_leaf:
            return []
        assert self.first is not None and self.second is not None, \
            "Nodo interno sin first/second -- invariante del arbol violada"
        return [self] + self.first.internal_nodes() + self.second.internal_nodes()


def build_random_tree(room_ids: List[str], rng: random.Random) -> PartitionNode:
    """Construye un árbol de topología aleatoria, cada room_id una vez
    (punto de partida para la búsqueda). `direction=None` en todos los
    nodos -- ver [ARCH:partition-node]."""
    if len(room_ids) == 1:
        return PartitionNode(room_id=room_ids[0])

    shuffled = list(room_ids)
    rng.shuffle(shuffled)
    split = rng.randint(1, len(shuffled) - 1)
    first = build_random_tree(shuffled[:split], rng)
    second = build_random_tree(shuffled[split:], rng)
    return PartitionNode(direction=None, first=first, second=second)


def _leaf_area(leaf: "PartitionNode", areas: Dict[str, float]) -> float:
    """Area de una hoja -- helper compartido por place_tree y
    _current_ratio, evita repetir el assert de invariante en cada sitio."""
    assert leaf.room_id is not None, "Nodo no-hoja pasado a _leaf_area -- invariante violada"
    return areas[leaf.room_id]


def _worst_aspect_ratio(width: float, height: float, ratio: float, direction: str) -> float:
    """Peor proporción ancho:alto entre las dos piezas de cortar
    width x height en `ratio` (fracción de `first`), en `direction`.
    Ver [ARCH:partition-node]."""
    if direction == "v":
        w1, h1 = width * ratio, height
        w2, h2 = width * (1 - ratio), height
    else:
        w1, h1 = width, height * ratio
        w2, h2 = width, height * (1 - ratio)
    r1 = max(w1, h1) / max(min(w1, h1), 1e-6)
    r2 = max(w2, h2) / max(min(w2, h2), 1e-6)
    return max(r1, r2)


def _area_derived_ratio(node: PartitionNode, areas: Dict[str, float]) -> float:
    """Proporcion derivada PURAMENTE del area declarada de cada
    subarbol, ignorando cualquier ratio_override existente -- el punto
    de referencia "justo" tanto para el corte por defecto (place_tree)
    como para acotar cuanto puede alejarse slide_wall (ver mas abajo,
    [ARCH:area-objetivo])."""
    assert node.first is not None and node.second is not None, \
        "Nodo interno sin first/second -- invariante del arbol violada"
    first_area = sum(_leaf_area(leaf, areas) for leaf in node.first.leaves())
    second_area = sum(_leaf_area(leaf, areas) for leaf in node.second.leaves())
    total = first_area + second_area or 1.0
    return first_area / total


def place_tree(node: PartitionNode, rectangle: Polygon, areas: Dict[str, float]) -> Dict[str, Polygon]:
    """Recorre el arbol y devuelve, para cada room_id, el rectangulo que
    le corresponde dentro de `rectangle`, proporcional al area total de
    estancias de cada subarbol en cada corte."""
    if node.is_leaf:
        assert node.room_id is not None
        return {node.room_id: rectangle}

    assert node.first is not None and node.second is not None, \
        "Nodo interno sin first/second -- invariante del arbol violada"
    minx, miny, maxx, maxy = rectangle.bounds
    ratio = node.ratio_override if node.ratio_override is not None else _area_derived_ratio(node, areas)

    # direccion efectiva: automatica minimiza la peor proporcion
    # resultante (ver [ARCH:partition-node]), o la forzada por override.
    width, height = maxx - minx, maxy - miny
    if node.direction is not None:
        effective_direction = node.direction
    else:
        ratio_v = _worst_aspect_ratio(width, height, ratio, "v")
        ratio_h = _worst_aspect_ratio(width, height, ratio, "h")
        effective_direction = "v" if ratio_v <= ratio_h else "h"

    if effective_direction == "v":  # corte vertical: reparte a lo largo de X
        split_x = minx + (maxx - minx) * ratio
        first_box = box(minx, miny, split_x, maxy)
        second_box = box(split_x, miny, maxx, maxy)
    else:  # corte horizontal: reparte a lo largo de Y
        split_y = miny + (maxy - miny) * ratio
        first_box = box(minx, miny, maxx, split_y)
        second_box = box(minx, split_y, maxx, maxy)

    placements: Dict[str, Polygon] = {}
    placements.update(place_tree(node.first, first_box, areas))
    placements.update(place_tree(node.second, second_box, areas))
    return placements


SLIDE_WALL_STEP = 0.08          # perturbacion maxima por movimiento (+-8%)
# BUG REAL encontrado por el usuario (captura de pantalla: un Pasillo
# de 4.0m2 declarados generado mas grande que un Dormitorio de 8.0m2)
# e investigado a fondo tras anadir AreaObjetivoValidator: los limites
# ABSOLUTOS anteriores (0.15/0.85) permitian que el ratio de CUALQUIER
# corte se alejara hasta esos extremos sin importar su proporcion
# "justa" (derivada del area) -- para un corte cuya proporcion justa
# es, p.ej., 3% (una estancia diminuta junto a un subarbol grande),
# nada impedia deslizarlo hasta el 85% (28 veces su area justa) tras
# muchas iteraciones de recocido, sin ninguna fuerza que lo devolviera
# -- confirmado empiricamente: 0 de 20 semillas distintas conseguian
# generar un layout valido con validacion de area activa, no era mala
# suerte de semilla, era estructural. Corregido acotando RELATIVO a la
# proporcion justa de cada corte (`_area_derived_ratio`), no con una
# ventana absoluta igual para todos los cortes. Ver [ARCH:area-objetivo].
SLIDE_WALL_MAX_DEVIATION = 0.20  # +-20% relativo al ratio justo (derivado del area)
SLIDE_WALL_ABSOLUTE_MIN = 0.05    # limite de seguridad, evita cortes degenerados
SLIDE_WALL_ABSOLUTE_MAX = 0.95


def _current_ratio(node: PartitionNode, areas: Dict[str, float]) -> float:
    """Proporcion EFECTIVA actual de un nodo interno: su `ratio_override`
    si ya tiene uno, o la derivada de las areas declaradas si no -- es
    el punto de partida real para "deslizar" desde ahi, no un valor fijo."""
    if node.ratio_override is not None:
        return node.ratio_override
    return _area_derived_ratio(node, areas)


def _clear_stale_overrides(node: PartitionNode, room_ids: set) -> bool:
    """Limpia `ratio_override` en cualquier nodo interno cuyo subarbol
    contenga alguna de las estancias en `room_ids` -- tras un
    swap_leaves, un ratio_override ya fijado en un antecesor quedaria
    calculado para la estancia VIEJA (area distinta), sin que nada lo
    invalidase. Devuelve si el subarbol de `node` contiene alguna de
    esas estancias (para la recursion). Ver [ARCH:area-objetivo]."""
    if node.is_leaf:
        return node.room_id in room_ids
    assert node.first is not None and node.second is not None, \
        "Nodo interno sin first/second -- invariante del arbol violada"
    contiene = (
        _clear_stale_overrides(node.first, room_ids)
        or _clear_stale_overrides(node.second, room_ids)
    )
    if contiene:
        node.ratio_override = None
    return contiene


def random_neighbor(tree: PartitionNode, rng: random.Random, areas: Dict[str, float]) -> PartitionNode:
    """Genera un árbol vecino mediante uno de cuatro movimientos:
    intercambiar hojas, invertir dirección, intercambiar subárboles,
    o "deslizar pared" (perturbar la proporción de un corte). Ver
    [ARCH:partition-node]."""
    new_tree = copy.deepcopy(tree)
    move = rng.choice(("swap_leaves", "flip_direction", "swap_children", "slide_wall"))

    if move == "swap_leaves":
        leaves = new_tree.leaves()
        if len(leaves) >= 2:
            a, b = rng.sample(leaves, 2)
            a.room_id, b.room_id = b.room_id, a.room_id
            _clear_stale_overrides(new_tree, {a.room_id, b.room_id})
        return new_tree

    internals = new_tree.internal_nodes()
    if not internals:
        return new_tree
    target = rng.choice(internals)

    if move == "flip_direction":
        # ciclo None -> "h" -> "v" -> None (ver [ARCH:partition-node])
        if target.direction is None:
            target.direction = "h"
        elif target.direction == "h":
            target.direction = "v"
        else:
            target.direction = None
    elif move == "swap_children":
        # el ratio_override (si lo hay) representa "fraccion de first" --
        # tras intercambiar first/second, ese numero fijo quedaria
        # aplicado al lado CONTRARIO del que se calculo, invirtiendo el
        # corte -- mismo tipo de problema que swap_leaves. Se limpia
        # para que se recalcule desde el area real de cada lado.
        target.first, target.second = target.second, target.first
        target.ratio_override = None
    else:  # slide_wall
        current = _current_ratio(target, areas)
        natural = _area_derived_ratio(target, areas)
        delta = rng.uniform(-SLIDE_WALL_STEP, SLIDE_WALL_STEP)
        proposed = current + delta
        min_bound = max(natural * (1 - SLIDE_WALL_MAX_DEVIATION), SLIDE_WALL_ABSOLUTE_MIN)
        max_bound = min(natural * (1 + SLIDE_WALL_MAX_DEVIATION), SLIDE_WALL_ABSOLUTE_MAX)
        target.ratio_override = min(max_bound, max(min_bound, proposed))
    return new_tree
