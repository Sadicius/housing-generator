"""Árbol B* (Chang & Chang, 2000) para distribuir TODAS las estancias
de un programa en un solar de una sola vez -- representación NO-guillotina
alternativa a `partition_tree.py`, que solo puede representar particiones
donde cada corte divide el rectángulo entero de lado a lado. Formas en L,
en U, o con patio interior son, por definición, imposibles con guillotina
pura, sin importar cuánto se mejore la búsqueda.

A diferencia de `PartitionNode` (donde las hojas son estancias y los
nodos internos son cortes), aquí CADA nodo representa una estancia
directamente. Las coordenadas X las decide la propia estructura del
árbol; las coordenadas Y requieren una estructura de contorno (perfil
tipo "skyline" de lo ya ocupado) -- ver `compute_positions`.

Migración planificada a fondo, con las decisiones de diseño y el
prototipo verificado, en `docs/referencia/generador/prototipo-btree/`.
Ver [ARCH:btree-partition].
"""
import copy
import math
import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from shapely.geometry import Polygon, box


@dataclass
class BStarNode:
    """Nodo del árbol B*. Cada nodo es una estancia -- no hay distinción
    hoja/nodo interno como en `PartitionNode`.

    `left`: "el bloque más bajo, pegado a la derecha del padre"
    (x = x_padre + ancho_padre). `right`: "el primer bloque arriba,
    misma X que el padre" (x = x_padre). `aspect_ratio`: ancho/alto
    buscable, preserva el área declarada exactamente sea cual sea su
    valor -- mismo espíritu que `ratio_override`/`slide_wall` del
    árbol de partición, adaptado a que aquí cada nodo ES una estancia,
    no un corte.

    [ARCH:btree-partition]
    """
    room_id: str
    aspect_ratio: float = 1.0
    left: Optional["BStarNode"] = None
    right: Optional["BStarNode"] = None

    def nodes(self) -> List["BStarNode"]:
        """Todos los nodos del subárbol, incluido este -- equivalente a
        `leaves()` de `PartitionNode`, pero aquí TODO nodo es una
        estancia, no solo las hojas."""
        result = [self]
        if self.left is not None:
            result += self.left.nodes()
        if self.right is not None:
            result += self.right.nodes()
        return result


def build_random_tree(room_ids: List[str], rng: random.Random) -> BStarNode:
    """Construye un árbol B* de topología aleatoria, cada room_id una
    vez -- punto de partida para la búsqueda. Inserción sucesiva en un
    hueco libre (`left`/`right` vacío) elegido al azar entre todos los
    nodos ya colocados, no una construcción recursiva por división
    (a diferencia de `partition_tree.build_random_tree`, que sí lo es
    -- el árbol B* se construye de forma incremental por naturaleza)."""
    if not room_ids:
        raise ValueError("room_ids no puede estar vacío")
    shuffled = list(room_ids)
    rng.shuffle(shuffled)
    root = BStarNode(room_id=shuffled[0])
    for room_id in shuffled[1:]:
        huecos = [
            (nodo, lado)
            for nodo in root.nodes()
            for lado in ("left", "right")
            if getattr(nodo, lado) is None
        ]
        nodo, lado = rng.choice(huecos)
        setattr(nodo, lado, BStarNode(room_id=room_id))
    return root


# Cache de una sola entrada, por REFERENCIA real (no por id()) -- mismo
# patron ya probado en GeometryAdjacencyGraphBuilder
# ([ARCH:geometry-adjacency-graph]): cachear por id() falla porque
# Python reutiliza agresivamente direcciones de memoria de objetos
# liberados. Motivo real, medido con cProfile, no optimizacion
# especulativa: `random_neighbor` ya calcula las posiciones del
# candidato para comprobar el bloqueo progresivo
# (ver compute_positions en random_neighbor mas abajo) -- sin esta
# cache, `_materialize` las recalculaba desde cero para el MISMO
# arbol justo despues, 2748 llamadas para 1360 evaluaciones medidas
# (~2x redundante). Ver [ARCH:btree-partition].
_cache_root_ref: Optional[BStarNode] = None
_cache_areas_ref: Optional[Dict[str, float]] = None
_cache_positions: Optional[Dict[str, Polygon]] = None


def compute_positions(root: BStarNode, areas: Dict[str, float]) -> Dict[str, Polygon]:
    """Calcula la posición real de cada estancia vía el algoritmo de
    contorno (Chang & Chang 2000) -- devuelve polígonos shapely, mismo
    formato que `place_tree()` del árbol de partición, para que el
    resto del sistema (validadores, persistencia, visor) no note
    ninguna diferencia entre representaciones.

    El contorno es una lista de segmentos (x1, x2, altura) -- el
    "perfil" de lo ya ocupado. Cada estancia nueva "cae" hasta
    apoyarse en lo que ya hay ocupado en su rango de X (como en
    Tetris), no en una posición fija de antemano.
    """
    global _cache_root_ref, _cache_areas_ref, _cache_positions
    if root is _cache_root_ref and areas is _cache_areas_ref:
        assert _cache_positions is not None
        return _cache_positions

    positions: Dict[str, Polygon] = {}
    contour: List[Tuple[float, float, float]] = []

    def height_in_range(x1: float, x2: float) -> float:
        max_h = 0.0
        for (cx1, cx2, cy) in contour:
            if cx1 < x2 and cx2 > x1:  # se solapan en X
                max_h = max(max_h, cy)
        return max_h

    def update_contour(x1: float, x2: float, y: float) -> None:
        nuevo = []
        for (cx1, cx2, cy) in contour:
            if cx2 <= x1 or cx1 >= x2:
                nuevo.append((cx1, cx2, cy))
            else:
                if cx1 < x1:
                    nuevo.append((cx1, x1, cy))
                if cx2 > x2:
                    nuevo.append((x2, cx2, cy))
        nuevo.append((x1, x2, y))
        contour[:] = sorted(nuevo)

    def place(node: Optional[BStarNode], x: float) -> None:
        if node is None:
            return
        area = areas[node.room_id]
        w = math.sqrt(area * node.aspect_ratio)
        h = math.sqrt(area / node.aspect_ratio)
        y = height_in_range(x, x + w)
        positions[node.room_id] = box(x, y, x + w, y + h)
        update_contour(x, x + w, y + h)
        place(node.left, x + w)  # hijo izquierdo: pegado a la derecha del padre
        place(node.right, x)     # hijo derecho: misma X que el padre, encima

    place(root, 0.0)
    _cache_root_ref, _cache_areas_ref, _cache_positions = root, areas, positions
    return positions


def swap_modules(root: BStarNode, id_a: str, id_b: str) -> BStarNode:
    """Op3 (Chang & Chang): intercambia qué estancia ocupa cada nodo --
    la forma del árbol no cambia, solo la identidad. Equivalente
    directo a `swap_leaves` del árbol de partición."""
    nuevo = copy.deepcopy(root)
    for nodo in nuevo.nodes():
        if nodo.room_id == id_a:
            nodo.room_id = id_b
        elif nodo.room_id == id_b:
            nodo.room_id = id_a
    return nuevo


def _find_node(root: BStarNode, room_id: str) -> BStarNode:
    for nodo in root.nodes():
        if nodo.room_id == room_id:
            return nodo
    raise ValueError(f"'{room_id}' no esta en el arbol")


def _find_parent(root: BStarNode, objetivo: BStarNode) -> Tuple[Optional[BStarNode], Optional[str]]:
    def buscar(nodo: Optional[BStarNode], padre: Optional[BStarNode], lado: Optional[str]):
        if nodo is None:
            return None
        if nodo is objetivo:
            return (padre, lado)
        r = buscar(nodo.left, nodo, "left")
        if r is not None:
            return r
        return buscar(nodo.right, nodo, "right")
    resultado = buscar(root, None, None)
    assert resultado is not None, "el nodo objetivo no pertenece a este arbol"
    return resultado


def move_module(root: BStarNode, room_id: str, rng: random.Random) -> BStarNode:
    """Op2 (Chang & Chang): extrae una estancia de su posición actual y
    la inserta en un hueco libre completamente distinto del árbol --
    a diferencia de `swap_modules`, esto SÍ cambia la forma del árbol,
    no solo quién ocupa cada hueco. Es el movimiento que no existe en
    el árbol de partición actual, y el que ataca de raíz la limitación
    ya diagnosticada (los movimientos actuales solo reasignan
    identidad, nunca crean huecos nuevos). Ver [ARCH:btree-partition].

    Solo mueve nodos hoja (sin hijos) -- mover un nodo con
    descendientes exigiría decidir qué hacer con ellos (reinsertarlos
    también, o dejarlos colgando de donde estaban), fuera de alcance
    de este movimiento simple. Si el nodo elegido no es hoja, no-op
    (devuelve el árbol sin cambios).
    """
    nuevo = copy.deepcopy(root)
    objetivo = _find_node(nuevo, room_id)
    if objetivo.left is not None or objetivo.right is not None:
        return nuevo  # no-op: mover nodos con descendientes queda fuera de alcance

    padre, lado = _find_parent(nuevo, objetivo)
    if padre is None:
        return nuevo  # es la raiz sin hijos -- no hay nada que mover (arbol de 1 nodo)
    assert lado is not None, "si hay padre, siempre hay lado -- invariante de _find_parent"
    setattr(padre, lado, None)

    huecos = [
        (nodo, lado2)
        for nodo in nuevo.nodes()
        for lado2 in ("left", "right")
        if getattr(nodo, lado2) is None
    ]
    if not huecos:
        setattr(padre, lado, objetivo)  # sin huecos disponibles, deshacer
        return nuevo
    nuevo_padre, nuevo_lado = rng.choice(huecos)
    assert nuevo_lado is not None
    setattr(nuevo_padre, nuevo_lado, objetivo)
    return nuevo


def resize_module(root: BStarNode, room_id: str, rng: random.Random, step: float = 0.15) -> BStarNode:
    """Redimensiona una estancia "blanda" (área fija, proporción
    variable) -- equivalente a `slide_wall` del árbol de partición,
    adaptado a que aquí la proporción vive en la propia estancia, no
    en un corte. Perturba `aspect_ratio` multiplicativamente (nunca
    negativo, evita colapsar a una franja de anchura/altura cero)."""
    nuevo = copy.deepcopy(root)
    nodo = _find_node(nuevo, room_id)
    factor = 1 + rng.uniform(-step, step)
    nodo.aspect_ratio = max(0.05, min(20.0, nodo.aspect_ratio * factor))
    return nuevo


def reset_aspect_ratio(root: BStarNode, room_id: str) -> BStarNode:
    """Restablece la proporción de una estancia a 1:1 (cuadrada) --
    equivalente a `reset_ratio` del árbol de partición: deshace la
    deriva acumulada por varios `resize_module` sucesivos, dándole a
    la búsqueda una forma real de deshacer, no solo de generar."""
    nuevo = copy.deepcopy(root)
    _find_node(nuevo, room_id).aspect_ratio = 1.0
    return nuevo


def swap_children(root: BStarNode, room_id: str) -> BStarNode:
    """Intercambia los hijos `left`/`right` de una estancia -- lo que
    antes iba "pegado a la derecha" pasa a ir "encima", y viceversa.
    Movimiento local, más barato que `move_module`."""
    nuevo = copy.deepcopy(root)
    nodo = _find_node(nuevo, room_id)
    nodo.left, nodo.right = nodo.right, nodo.left
    return nuevo


ESCAPE_PROBABILITY = 0.15  # NO normativo, mismo criterio que
# partition_tree.ESCAPE_PROBABILITY: con que frecuencia se ignora el
# bloqueo por completo, para no quedarse atascado si arreglar algo
# exige desplazar temporalmente una estancia ya bloqueada.


def random_neighbor(
    root: BStarNode,
    rng: random.Random,
    areas: Dict[str, float],
    locked_room_ids: Optional[set] = None,
) -> BStarNode:
    """Genera un árbol vecino mediante uno de cinco movimientos:
    intercambiar, mover, redimensionar, restablecer proporción, o
    intercambiar hijos. Ver [ARCH:btree-partition].

    `locked_room_ids`: bloqueo progresivo por COMPROBACIÓN REAL (a
    diferencia de `partition_tree.random_neighbor`, que protege por
    posición en el árbol) -- en árbol B* el contorno es compartido,
    así que tocar una estancia puede desplazar a otra que no se tocó
    directamente (confirmado con código durante la Fase 2 de esta
    migración: cambiar el tamaño de una estancia desplazaba a otra dos
    niveles por debajo, sin tocarla). Se recalculan las posiciones
    antes/después del movimiento candidato y se rechaza (se devuelve
    el árbol sin cambios) si alguna estancia bloqueada se desplazó
    como efecto colateral -- confirmado con el usuario como la opción
    preferida (más costosa, pero más flexible que proteger solo la
    cadena de antecesores). Con probabilidad `ESCAPE_PROBABILITY`, se
    ignora el bloqueo por completo (válvula de escape, evita atascos).
    """
    ignorar_bloqueo = not locked_room_ids or rng.random() < ESCAPE_PROBABILITY
    bloqueadas: set = set() if ignorar_bloqueo or locked_room_ids is None else locked_room_ids

    nodos = root.nodes()
    room_id = rng.choice([n.room_id for n in nodos])
    # BUG REAL encontrado al ejecutar tests de integracion tras eliminar
    # el generador clasico: con un solo nodo en el arbol (programa de
    # una sola estancia), "swap" no tiene con quien intercambiar --
    # antes invisible porque nunca se habia probado el arbol B* contra
    # un programa de 1 sola estancia. Excluido dinamicamente cuando no
    # hay al menos 2 nodos, en vez de asumir que siempre los hay.
    posibles_moves = ["swap", "move", "resize", "reset", "swap_children"] if len(nodos) >= 2 \
        else ["move", "resize", "reset", "swap_children"]
    move = rng.choice(posibles_moves)

    if move == "swap":
        otro = rng.choice([n.room_id for n in nodos if n.room_id != room_id])
        candidato = swap_modules(root, room_id, otro)
    elif move == "move":
        candidato = move_module(root, room_id, rng)
    elif move == "resize":
        candidato = resize_module(root, room_id, rng)
    elif move == "reset":
        candidato = reset_aspect_ratio(root, room_id)
    else:  # swap_children
        candidato = swap_children(root, room_id)

    if not bloqueadas:
        return candidato

    pos_antes = compute_positions(root, areas)
    pos_despues = compute_positions(candidato, areas)
    for locked_id in bloqueadas:
        antes = pos_antes[locked_id].bounds
        despues = pos_despues[locked_id].bounds
        if antes != despues:
            return root  # movimiento rechazado, devuelve el arbol sin cambios
    return candidato
