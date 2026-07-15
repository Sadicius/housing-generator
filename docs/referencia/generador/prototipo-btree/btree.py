"""Prototipo aislado de arbol B* (Chang & Chang 2000) -- FASE 0 de la
migracion planificada. No toca el proyecto real. Objetivo unico:
confirmar que el mecanismo de contorno esta bien entendido antes de
comprometerse con nada mas.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List


@dataclass
class BStarNode:
    module_id: str
    left: Optional["BStarNode"] = None   # "el bloque mas bajo, pegado a la derecha"
    right: Optional["BStarNode"] = None  # "el primer bloque arriba, misma X"


def compute_positions(root: BStarNode, dims: Dict[str, Tuple[float, float]]) -> Dict[str, Tuple[float, float, float, float]]:
    """Calcula (x, y, w, h) de cada modulo via el algoritmo de contorno.
    Estructura de contorno: lista de segmentos (x1, x2, altura), el
    'perfil' de lo ya ocupado."""
    positions: Dict[str, Tuple[float, float, float, float]] = {}
    contour: List[Tuple[float, float, float]] = []  # (x1, x2, altura)

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
        w, h = dims[node.module_id]
        y = height_in_range(x, x + w)
        positions[node.module_id] = (x, y, w, h)
        update_contour(x, x + w, y + h)
        place(node.left, x + w)   # hijo izquierdo: pegado a la derecha del padre
        place(node.right, x)      # hijo derecho: misma X que el padre, encima

    place(root, 0.0)
    return positions
