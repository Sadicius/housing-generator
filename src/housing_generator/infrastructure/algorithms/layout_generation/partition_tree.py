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
    `direction` y dos subarboles `first`/`second`.

    `direction`: **[RESUELTO, retomado tras un caso real]** `None` (por
    defecto) significa "automatica -- cortar siempre por el lado MAS
    LARGO del rectangulo, en el momento de colocar" (investigacion
    externa: Marson & Musse 2010, tecnica de squarified treemap para
    generar plantas con estancias de proporcion cercana a 1:1). Un
    valor explicito ("h"/"v") FUERZA esa direccion, anulando el
    automatismo -- usado por el movimiento `flip_direction` como via de
    escape para que el recocido pueda explorar topologias distintas a
    la "natural" cuando haga falta.

    Encontrado con un caso real: con la direccion puramente aleatoria
    de antes, estancias pequeñas emparejadas por azar con una estancia
    grande podian acabar como tiras finas (ancho libre insuficiente),
    y anadir una restriccion de ancho minimo practico
    (AnchoLibrePracticoValidator) volvio esto una dificultad de
    busqueda mucho mayor -- confirmado que quitando el validador la
    misma semilla convergia en 22s, con el activo fallaba incluso con
    30000 iteraciones. Cortar por el lado mas largo por defecto reduce
    la aparicion de tiras finas desde el propio punto de partida, en
    vez de depender de que el recocido las evite por pura suerte.

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
    """Construye un arbol de topologia aleatoria que contiene cada
    room_id exactamente una vez (punto de partida para la busqueda).

    `direction=None` (automatica, corta por el lado mas largo -- ver
    docstring de PartitionNode) es el punto de partida por defecto,
    no un valor h/v elegido al azar como antes -- el azar de direccion
    ahora es responsabilidad exclusiva del movimiento `flip_direction`
    durante la busqueda, no de la construccion inicial."""
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
    first_area = sum(_leaf_area(leaf, areas) for leaf in node.first.leaves())
    second_area = sum(_leaf_area(leaf, areas) for leaf in node.second.leaves())
    total = first_area + second_area or 1.0
    ratio = node.ratio_override if node.ratio_override is not None else (first_area / total)

    # direccion EFECTIVA: si no hay override explicito ("h"/"v" forzado
    # por flip_direction), cortar por el lado mas largo del rectangulo
    # actual -- tecnica de squarified treemap (Marson & Musse 2010),
    # ver docstring de PartitionNode para el porque real de este cambio.
    if node.direction is not None:
        effective_direction = node.direction
    else:
        width, height = maxx - minx, maxy - miny
        effective_direction = "v" if width > height else "h"

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
SLIDE_WALL_MIN_RATIO = 0.15      # limites para evitar cortes degenerados
SLIDE_WALL_MAX_RATIO = 0.85


def _current_ratio(node: PartitionNode, areas: Dict[str, float]) -> float:
    """Proporcion EFECTIVA actual de un nodo interno: su `ratio_override`
    si ya tiene uno, o la derivada de las areas declaradas si no -- es
    el punto de partida real para "deslizar" desde ahi, no un valor fijo."""
    if node.ratio_override is not None:
        return node.ratio_override
    assert node.first is not None and node.second is not None, \
        "Nodo interno sin first/second -- invariante del arbol violada"
    first_area = sum(_leaf_area(leaf, areas) for leaf in node.first.leaves())
    second_area = sum(_leaf_area(leaf, areas) for leaf in node.second.leaves())
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
        # ciclo None (automatica, lado mas largo) -> "h" forzado ->
        # "v" forzado -> None -- ya no es un toggle ciego h<->v, porque
        # la direccion "natural" ahora depende del rectangulo real en
        # el momento de colocar, no se puede saber solo mirando el
        # nodo. Ciclar por los 3 estados le da al recocido la misma
        # libertad de explorar topologias no-cuadradas cuando haga
        # falta (p.ej. un pasillo que conviene mantener alargado en la
        # misma direccion), sin perder el punto de partida "automatico"
        # por defecto.
        if target.direction is None:
            target.direction = "h"
        elif target.direction == "h":
            target.direction = "v"
        else:
            target.direction = None
    elif move == "swap_children":
        target.first, target.second = target.second, target.first
    else:  # slide_wall
        current = _current_ratio(target, areas)
        delta = rng.uniform(-SLIDE_WALL_STEP, SLIDE_WALL_STEP)
        target.ratio_override = min(SLIDE_WALL_MAX_RATIO, max(SLIDE_WALL_MIN_RATIO, current + delta))
    return new_tree
