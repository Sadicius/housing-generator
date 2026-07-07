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
    `direction` ("h" | "v") y dos subarboles `first`/`second`."""
    room_id: Optional[str] = None
    direction: Optional[str] = None
    first: Optional["PartitionNode"] = None
    second: Optional["PartitionNode"] = None

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
    ratio = first_area / total

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


def random_neighbor(tree: PartitionNode, rng: random.Random) -> PartitionNode:
    """Genera un arbol vecino mediante UNO de tres movimientos aleatorios,
    los tres habituales en recocido simulado sobre slicing floorplans:
    - intercambiar la estancia de dos hojas cualesquiera
    - invertir la direccion de corte (h<->v) de un nodo interno
    - intercambiar los dos subarboles de un nodo interno (efecto espejo)
    """
    new_tree = copy.deepcopy(tree)
    move = rng.choice(("swap_leaves", "flip_direction", "swap_children"))

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
    else:  # swap_children
        target.first, target.second = target.second, target.first
    return new_tree
