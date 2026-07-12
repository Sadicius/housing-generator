import copy
import math
import random
from typing import Dict, List, Optional

from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.infrastructure.algorithms.layout_generation.partition_tree import (
    PartitionNode,
    build_random_tree,
    place_tree,
    random_neighbor,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)


class SimulatedAnnealingLayoutGenerator(LayoutGeneratorPort):
    """Genera el layout con un árbol de partición sobre todas las
    estancias a la vez, buscando la mejor topología mediante recocido
    simulado. Función objetivo: comparación lexicográfica (duro,
    blando), duro siempre dominante. Ver [ARCH:simulated-annealing].
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
        # rng recreado en cada llamada, para que seed sea reproducible
        # siempre, no solo la primera vez. Ver [ARCH:simulated-annealing].
        self._rng = random.Random(self._seed)

        room_ids = [r.id for r in program.rooms]
        areas = {r.id: r.dimensions.area_m2 for r in program.rooms}

        current_tree = build_random_tree(room_ids, self._rng)
        current_layout = self._materialize(current_tree, program, lot, areas)
        current_hard, current_soft = self._score(current_layout)

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            candidate_tree = random_neighbor(current_tree, self._rng, areas)
            candidate_layout = self._materialize(candidate_tree, program, lot, areas)
            candidate_hard, candidate_soft = self._score(candidate_layout)

            # comparacion lexicografica: si lo duro cambia, decide solo
            # el delta duro; lo blando solo cuenta si empata. Ver
            # [ARCH:simulated-annealing].
            if candidate_hard != current_hard:
                delta = candidate_hard - current_hard
            else:
                delta = candidate_soft - current_soft

            accepted = delta <= 0 or self._rng.random() < math.exp(-delta / max(temperature, 1e-9))
            if accepted:
                current_tree, current_layout = candidate_tree, candidate_layout
                current_hard, current_soft = candidate_hard, candidate_soft
                if (current_hard, current_soft) < (best_hard, best_soft):
                    best_layout = current_layout
                    best_hard, best_soft = current_hard, current_soft

            temperature *= self._cooling_rate

        best_layout.metadata["annealing_score"] = best_hard  # compatibilidad: violaciones duras del mejor layout
        best_layout.metadata["hard_violations"] = best_hard
        best_layout.metadata["soft_penalty"] = best_soft
        return best_layout

    def _score(self, layout: Layout) -> tuple:
        hard_violations = len(self._constraint_validator.validate(layout).violations)
        soft_penalty = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        return (hard_violations, soft_penalty)

    def _materialize(
        self,
        tree: PartitionNode,
        program: Program,
        lot: Lot,
        areas: Dict[str, float],
    ) -> Layout:
        # area edificable: parcela completa, o reducida por retranqueo
        # (ver Lot.buildable_area).
        placements = place_tree(tree, lot.buildable_area.polygon, areas)

        placed_rooms = []
        for room in program.rooms:
            placed_room = copy.copy(room)  # copia superficial: no muta el Room del Program original
            placed_room.boundary = Boundary(polygon=placements[room.id])
            placed_rooms.append(placed_room)

        zones_map: Dict = {}
        for room in placed_rooms:
            zones_map.setdefault(room.zone, []).append(room.id)
        built_zones = [Zone(zone_type=zone_type, room_ids=ids) for zone_type, ids in zones_map.items()]

        return Layout(lot=lot, rooms=placed_rooms, zones=built_zones)
