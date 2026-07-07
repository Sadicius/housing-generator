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


class SimulatedAnnealingLayoutGenerator(LayoutGeneratorPort):
    """Genera el layout construyendo un arbol de particion recursivo sobre
    TODAS las estancias del programa a la vez (sin fase previa de reparto
    por macro-zona geometrica) y buscando la mejor topologia mediante
    recocido simulado.

    La funcion objetivo es, deliberadamente, solo el NUMERO de violaciones
    que reporta `constraint_validator` -- restricciones duras unicamente,
    sin ponderacion ni blandas, tal como se acordo.

    DIFERENCIA DE ARQUITECTURA respecto a GraphBasedLayoutGenerator: este
    generador recibe el ConstraintValidatorPort como dependencia PROPIA
    (no solo GenerateLayoutUseCase), porque necesita invocarlo miles de
    veces durante la busqueda interna. Generacion y validacion quedan
    acopladas dentro de esta clase concreta -- ambas siguen siendo
    intercambiables por separado en el resto del sistema (siguen siendo
    ports), pero esta implementacion en particular necesita las dos.

    `zones` (el parametro del puerto `LayoutGeneratorPort`) se ignora
    deliberadamente: este generador no reparte geometria por macro-zona,
    construye su propia agrupacion interna a partir de `room.zone` solo
    para poblar `Layout.zones` (compatibilidad con el resto del sistema),
    no para particionar el solar.
    """

    def __init__(
        self,
        constraint_validator: ConstraintValidatorPort,
        max_iterations: int = 2000,
        initial_temperature: float = 10.0,
        cooling_rate: float = 0.995,
        seed: Optional[int] = None,
    ):
        self._constraint_validator = constraint_validator
        self._max_iterations = max_iterations
        self._initial_temperature = initial_temperature
        self._cooling_rate = cooling_rate
        self._rng = random.Random(seed)

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        room_ids = [r.id for r in program.rooms]
        areas = {r.id: r.dimensions.area_m2 for r in program.rooms}

        current_tree = build_random_tree(room_ids, self._rng)
        current_layout = self._materialize(current_tree, program, lot, areas)
        current_score = self._score(current_layout)

        best_tree = current_tree
        best_layout = current_layout
        best_score = current_score

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_score == 0:
                break

            candidate_tree = random_neighbor(current_tree, self._rng)
            candidate_layout = self._materialize(candidate_tree, program, lot, areas)
            candidate_score = self._score(candidate_layout)

            delta = candidate_score - current_score
            accepted = delta <= 0 or self._rng.random() < math.exp(-delta / max(temperature, 1e-9))
            if accepted:
                current_tree, current_layout, current_score = candidate_tree, candidate_layout, candidate_score
                if current_score < best_score:
                    best_tree, best_layout, best_score = current_tree, current_layout, current_score

            temperature *= self._cooling_rate

        best_layout.metadata["annealing_score"] = best_score
        return best_layout

    def _score(self, layout: Layout) -> int:
        return len(self._constraint_validator.validate(layout).violations)

    def _materialize(
        self,
        tree: PartitionNode,
        program: Program,
        lot: Lot,
        areas: Dict[str, float],
    ) -> Layout:
        # area edificable: la parcela completa si no hay retranqueo
        # declarado, o la parcela reducida por el retranqueo si lo hay
        # (vivienda unifamiliar aislada -- ver Lot.buildable_area).
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
