import copy
import math
import random
from typing import Dict, List, Optional, Tuple

from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.ops import unary_union

from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.infrastructure.geometry.shapely_utils import polygon_to_shapes
from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
    BStarNode,
    build_random_tree,
    compute_positions,
    random_neighbor,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)


class BTreeLayoutGenerator(LayoutGeneratorPort):
    """Genera el layout con un árbol B* (Chang & Chang 2000) en vez del
    árbol de partición (`SimulatedAnnealingLayoutGenerator`) -- pieza
    intercambiable vía `LayoutGeneratorPort`, en paralelo al sistema
    actual, no en sustitución (Fase 4 de la migración planificada en
    `docs/referencia/generador/prototipo-btree/`).

    Misma función objetivo que el generador actual (comparación
    lexicográfica duro/blando, duro siempre dominante) y mismo bucle
    de recocido -- lo que cambia es la representación geométrica: en
    vez de particionar un rectángulo, se empaquetan las estancias
    directamente, lo que permite siluetas no rectangulares (en L, en
    U, con patio interior) que el árbol de partición no puede
    representar por definición. Ver [ARCH:btree-partition].
    """

    def __init__(
        self,
        constraint_validator: ConstraintValidatorPort,
        max_iterations: int = 2000,
        initial_temperature: float = 10.0,
        cooling_rate: float = 0.995,
        seed: Optional[int] = None,
        soft_constraint_scorer: Optional[SoftConstraintScorer] = None,
    ):
        self._constraint_validator = constraint_validator
        self._max_iterations = max_iterations
        self._initial_temperature = initial_temperature
        self._cooling_rate = cooling_rate
        self._seed = seed
        self._soft_scorer = soft_constraint_scorer

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        rng = random.Random(self._seed)  # recreado en cada llamada, seed reproducible siempre
        room_ids = [room.id for room in program.rooms]
        areas = {room.id: room.dimensions.area_m2 for room in program.rooms}

        current_tree = build_random_tree(room_ids, rng)
        current_layout = self._materialize(current_tree, program, lot, areas)
        current_hard, current_soft, current_locked = self._evaluate(current_layout, room_ids)

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            candidate_tree = random_neighbor(current_tree, rng, areas, locked_room_ids=current_locked)
            candidate_layout = self._materialize(candidate_tree, program, lot, areas)
            candidate_hard, candidate_soft, candidate_locked = self._evaluate(candidate_layout, room_ids)

            # comparacion lexicografica: si lo duro cambia, decide solo
            # el delta duro; lo blando solo cuenta si empata. Ver
            # [ARCH:simulated-annealing].
            delta: float
            if candidate_hard != current_hard:
                delta = candidate_hard - current_hard
            else:
                delta = candidate_soft - current_soft

            accepted = delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-9))
            if accepted:
                current_tree, current_layout = candidate_tree, candidate_layout
                current_hard, current_soft, current_locked = candidate_hard, candidate_soft, candidate_locked
                if (current_hard, current_soft) < (best_hard, best_soft):
                    best_layout = current_layout
                    best_hard, best_soft = current_hard, current_soft

            temperature *= self._cooling_rate

        if best_hard > 0:
            raise LayoutGenerationError(
                f"No se pudo generar un layout valido (arbol B*). Ultimas violaciones: "
                f"{self._constraint_validator.validate(best_layout).violations}"
            )
        return best_layout

    def _materialize(self, tree: BStarNode, program: Program, lot: Lot, areas: Dict[str, float]) -> Layout:
        # a diferencia del arbol de particion (huella decidida de
        # antemano, ver footprint.py), aqui la huella es el RESULTADO
        # del propio empaquetado -- se calcula primero (siempre parte
        # de (0,0)) y se ancla despues, no al reves. Ver [ARCH:btree-partition].
        positions = compute_positions(tree, areas)
        buildable_polygon = lot.buildable_area.polygon
        offset_x, offset_y = self._anchor_offset(buildable_polygon, positions, lot.entrance_side)

        placed_rooms = []
        for room in program.rooms:
            placed_room = copy.copy(room)  # copia superficial: no muta el Room del Program original
            placed_room.boundary = Boundary(polygon=translate(positions[room.id], offset_x, offset_y))
            placed_rooms.append(placed_room)

        zones_map: Dict = {}
        for room in placed_rooms:
            zones_map.setdefault(room.zone, []).append(room.id)
        built_zones = [Zone(zone_type=zone_type, room_ids=ids) for zone_type, ids in zones_map.items()]

        layout = Layout(lot=lot, rooms=placed_rooms, zones=built_zones)
        # VACIO: aqui incluye tanto el exterior (alrededor de la huella)
        # como el interior (huecos DENTRO de la propia silueta del
        # empaquetado, p.ej. un patio rodeado de estancias) -- una sola
        # resta geometrica cubre ambos casos, a diferencia del arbol de
        # particion (huella siempre maciza, solo existe vacio exterior).
        union_estancias = unary_union([r.boundary.polygon for r in placed_rooms])
        vacio_polygon = buildable_polygon.difference(union_estancias)
        layout.metadata["vacio_shapes"] = polygon_to_shapes(vacio_polygon)
        return layout

    @staticmethod
    def _anchor_offset(
        buildable_polygon: Polygon, positions: Dict[str, Polygon], entrance_side: str,
    ) -> Tuple[float, float]:
        """Traslada el empaquetado (que siempre parte de (0,0)) para
        anclarlo al lado de entrada de la parcela, centrado en el eje
        perpendicular -- mismo patrón que `footprint.footprint_rectangle`,
        adaptado a que aquí el tamaño no se elige, es el resultado."""
        minx, miny, maxx, maxy = buildable_polygon.bounds
        buildable_w, buildable_h = maxx - minx, maxy - miny
        px0, py0, px1, py1 = unary_union(list(positions.values())).bounds
        width, height = px1 - px0, py1 - py0

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

        return x0 - px0, y0 - py0

    def _evaluate(self, layout: Layout, all_room_ids: List[str]) -> Tuple[int, float, set]:
        """Una sola validacion por layout, reutilizada para la
        puntuacion (duro/blando) Y el bloqueo progresivo -- mismo
        patron que `SimulatedAnnealingLayoutGenerator._evaluate`."""
        violations = self._constraint_validator.validate(layout).violations
        hard = len(violations)
        soft = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        violating_ids = {
            room_id for room_id in all_room_ids
            if any(f"'{room_id}'" in v for v in violations)
        }
        locked = set(all_room_ids) - violating_ids
        return hard, soft, locked
