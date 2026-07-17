"""Fase 3 del rediseño "periferia hacia el centro": el bucle de
recocido simulado real, conectando las piezas ya construidas y
probadas por separado (Fase 0: `RoomOverlapValidator`; Fase 1:
`perimeter_carving.py`; Fase 2: `perimeter_core_partition.py`) en un
`LayoutGeneratorPort` completo. Ver
docs/referencia/generador/contacto-exterior-y-envolvente.md,
[ARCH:perimeter-core-layout-generator].
"""
import math
import random
from typing import List, Optional, Set, Tuple

from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.infrastructure.algorithms.layout_generation.perimeter_carving import (
    tallable_length_per_side,
)
from housing_generator.infrastructure.algorithms.layout_generation.perimeter_core_partition import (
    build_initial_perimeter_core_state,
    find_entrance_hall_id,
    random_neighbor_perimeter_core,
    materialize_perimeter_core,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)


class PerimeterCoreLayoutGenerator(LayoutGeneratorPort):
    """Genera el layout con el rediseño "periferia hacia el centro"
    (tallado perimetral + núcleo B*, `perimeter_core_partition.py`) --
    pieza intercambiable vía `LayoutGeneratorPort`, EN PARALELO a
    `BTreeLayoutGenerator`, no en sustitución todavía (mismo patrón de
    migración en paralelo que ya se usó para `BTreeLayoutGenerator` --
    ver su propio docstring). Sustituir de verdad exige antes
    confirmar, con datos reales, que este generador converge en los
    casos que `BTreeLayoutGenerator` no puede (los 5 `xfail` de
    `test_generate_layout_use_case.py`) sin regresionar en los que ya
    funcionan -- decisión pendiente con el usuario, no automática.

    Mismo bucle de recocido simulado y misma función objetivo
    (comparación lexicográfica duro/blando, duro siempre dominante)
    que `BTreeLayoutGenerator` -- lo que cambia es cómo se materializa
    cada candidato (`materialize_perimeter_core`: talla el perímetro
    contra el borde real del solar, en vez de empaquetar ciego desde
    el origen y anclar después) y cómo se genera un vecino
    (`random_neighbor_perimeter_core`: combina mutaciones de perímetro
    -- `move_to_side`/`swap_sides`/etc. -- y de núcleo -- `swap_modules`/
    `move_module`/etc., sin cambios). Sin `reference_stair` (escalera
    compartida multi-planta, Fase 4, fuera de alcance aquí).
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
        all_room_ids = [room.id for room in program.rooms]
        areas = {room.id: room.dimensions.area_m2 for room in program.rooms}
        entrance_hall_id = find_entrance_hall_id(program)

        tallable = tallable_length_per_side(lot.area_edificable_real.polygon, lot.medianera_sides)
        available_sides = [side for side, length in tallable.items() if length > 0]

        current_state = build_initial_perimeter_core_state(program, lot, rng)
        current_layout = materialize_perimeter_core(current_state, program, lot)
        current_hard, current_soft, current_locked = self._evaluate(current_layout, all_room_ids)

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            candidate_state = random_neighbor_perimeter_core(
                current_state, rng, areas, entrance_hall_id, available_sides,
                locked_room_ids=current_locked,
            )
            candidate_layout = materialize_perimeter_core(candidate_state, program, lot)
            candidate_hard, candidate_soft, candidate_locked = self._evaluate(candidate_layout, all_room_ids)

            # comparacion lexicografica: si lo duro cambia, decide solo
            # el delta duro; lo blando solo cuenta si empata. Ver
            # [ARCH:simulated-annealing] (mismo criterio que
            # BTreeLayoutGenerator).
            delta: float
            if candidate_hard != current_hard:
                delta = candidate_hard - current_hard
            else:
                delta = candidate_soft - current_soft

            accepted = delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-9))
            if accepted:
                current_state, current_layout = candidate_state, candidate_layout
                current_hard, current_soft, current_locked = candidate_hard, candidate_soft, candidate_locked
                if (current_hard, current_soft) < (best_hard, best_soft):
                    best_layout = current_layout
                    best_hard, best_soft = current_hard, current_soft

            temperature *= self._cooling_rate

        if best_hard > 0:
            raise LayoutGenerationError(
                f"No se pudo generar un layout valido (perimetro+nucleo). Ultimas violaciones: "
                f"{self._constraint_validator.validate(best_layout).violations}"
            )
        # metadatos de compatibilidad -- mismo convenio que BTreeLayoutGenerator.
        best_layout.metadata["annealing_score"] = best_hard
        best_layout.metadata["hard_violations"] = best_hard
        best_layout.metadata["soft_penalty"] = best_soft
        return best_layout

    def _evaluate(self, layout: Layout, all_room_ids: List[str]) -> Tuple[int, float, Set[str]]:
        """Una sola validación por layout, reutilizada para la
        puntuación (duro/blando) Y el bloqueo progresivo -- mismo
        patrón que `BTreeLayoutGenerator._evaluate`."""
        violations = self._constraint_validator.validate(layout).violations
        hard = len(violations)
        soft = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        violating_ids = {
            room_id for room_id in all_room_ids
            if any(f"'{room_id}'" in v for v in violations)
        }
        locked = set(all_room_ids) - violating_ids
        return hard, soft, locked
