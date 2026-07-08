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
    """Nodo del arbol. Una hoja tiene `room_id`; un nodo interno tiene
    `direction` ("h" | "v") y dos subarboles `first`/`second`.

    `ratio_override`: proporcion del corte FORZADA manualmente (0-1,
    fraccion de `first`), en vez de derivarla siempre del area declarada
    de las estancias. Inspirado en Merrell/Schkufza/Koltun 2010
    ("Sliding a wall" como proposal move independiente de "swapping
    rooms") -- investigacion externa confirmada, no una idea propia
    inventada sin referencia. Sin esto, la proporcion de cada corte
    quedaba SIEMPRE atada al area declarada de cada estancia, sin ningun
    grado de libertad independiente para ajustar forma/ancho libre sin
    cambiar topologia. `None` (por defecto) preserva el comportamiento
    anterior exacto -- calculo derivado del area."""
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
        return self.first.leaves() + self.second.leaves()

    def internal_nodes(self) -> List["PartitionNode"]:
        if self.is_leaf:
            return []
        return [self] + self.first.internal_nodes() + self.second.internal_nodes()


def build_random_tree(room_ids: List[str], rng: random.Random) -> PartitionNode:
    """Construye un arbol de topologia aleatoria que contiene cada
    room_id exactamente una vez (punto de partida para la busqueda)."""
    if len(room_ids) == 1:
        return PartitionNode(room_id=room_ids[0])

    shuffled = list(room_ids)
    rng.shuffle(shuffled)
    split = rng.randint(1, len(shuffled) - 1)
    first = build_random_tree(shuffled[:split], rng)
    second = build_random_tree(shuffled[split:], rng)
    direction = rng.choice(("h", "v"))
    return PartitionNode(direction=direction, first=first, second=second)


def place_tree(node: PartitionNode, rectangle: Polygon, areas: Dict[str, float]) -> Dict[str, Polygon]:
    """Recorre el arbol y devuelve, para cada room_id, el rectangulo que
    le corresponde dentro de `rectangle`, proporcional al area total de
    estancias de cada subarbol en cada corte."""
    if node.is_leaf:
        return {node.room_id: rectangle}

    minx, miny, maxx, maxy = rectangle.bounds
    first_area = sum(areas[leaf.room_id] for leaf in node.first.leaves())
    second_area = sum(areas[leaf.room_id] for leaf in node.second.leaves())
    total = first_area + second_area or 1.0
    ratio = node.ratio_override if node.ratio_override is not None else (first_area / total)

    if node.direction == "v":  # corte vertical: reparte a lo largo de X
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
SLIDE_WALL_MIN_RATIO = 0.15      # limites para evitar cortes degenerados
SLIDE_WALL_MAX_RATIO = 0.85


def _current_ratio(node: PartitionNode, areas: Dict[str, float]) -> float:
    """Proporcion EFECTIVA actual de un nodo interno: su `ratio_override`
    si ya tiene uno, o la derivada de las areas declaradas si no -- es
    el punto de partida real para "deslizar" desde ahi, no un valor fijo."""
    if node.ratio_override is not None:
        return node.ratio_override
    first_area = sum(areas[leaf.room_id] for leaf in node.first.leaves())
    second_area = sum(areas[leaf.room_id] for leaf in node.second.leaves())
    total = first_area + second_area or 1.0
    return first_area / total


def random_neighbor(tree: PartitionNode, rng: random.Random, areas: Dict[str, float]) -> PartitionNode:
    """Genera un arbol vecino mediante UNO de cuatro movimientos aleatorios:
    - intercambiar la estancia de dos hojas cualesquiera
    - invertir la direccion de corte (h<->v) de un nodo interno
    - intercambiar los dos subarboles de un nodo interno (efecto espejo)
    - "deslizar pared": perturbar la proporcion de un corte existente,
      independientemente de las areas declaradas (`ratio_override`) --
      inspirado en Merrell/Schkufza/Koltun 2010 ("Sliding a wall" como
      proposal move propio, distinto de "swapping rooms"). Los tres
      primeros son los habituales en recocido simulado sobre slicing
      floorplans; el cuarto cubre un grado de libertad que antes no
      existia en absoluto: sin el, la unica forma de corregir una
      violacion de forma/ancho libre era cambiar topologia (que
      estancia va con cual), nunca ajustar un corte ya bueno en si mismo.
      La perturbacion parte de la proporcion EFECTIVA actual (`_current_ratio`),
      no de un valor fijo -- un deslizamiento real, no un salto.
    """
    new_tree = copy.deepcopy(tree)
    move = rng.choice(("swap_leaves", "flip_direction", "swap_children", "slide_wall"))

    if move == "swap_leaves":
        leaves = new_tree.leaves()
        if len(leaves) >= 2:
            a, b = rng.sample(leaves, 2)
            a.room_id, b.room_id = b.room_id, a.room_id
        return new_tree

    internals = new_tree.internal_nodes()
    if not internals:
        return new_tree
    target = rng.choice(internals)

    if move == "flip_direction":
        target.direction = "v" if target.direction == "h" else "h"
    elif move == "swap_children":
        target.first, target.second = target.second, target.first
    else:  # slide_wall
        current = _current_ratio(target, areas)
        delta = rng.uniform(-SLIDE_WALL_STEP, SLIDE_WALL_STEP)
        target.ratio_override = min(SLIDE_WALL_MAX_RATIO, max(SLIDE_WALL_MIN_RATIO, current + delta))
    return new_tree
