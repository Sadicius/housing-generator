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
from typing import Callable, List, Optional, Set, Tuple

import networkx as nx

from housing_generator.application.ports.layout_generator_port import (
    LayoutGeneratorPort,
)
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.ports.adjacency_graph_builder_port import (
    AdjacencyGraphBuilderPort,
)
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.infrastructure.algorithms.constraints.day_night_zoning_validator import (
    zone_grouping_predicates,
)
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

CORE_PROXIMITY_WEIGHT = 1.0  # NO normativo, mismo tipo de decision de
# ingenieria que STAIR_CORNER_PREFERENCE_WEIGHT (btree_layout_generator.py):
# magnitud comparable a una preferencia blanda no satisfecha
# (PESO_CERCA_NO_SATISFECHO=1.0 en soft_constraint_scorer.py) para que el
# hueco entre piezas de nucleo pese de forma similar en la comparacion
# lexicografica. Ver [ARCH:perimeter-core-layout-generator].

# Grupos de estancias que deben quedar geometricamente cerca (o
# CONECTADAS) entre si -- mismos predicados EXACTOS que los 4
# validadores duros (`build_wet_core_validator`/`zone_grouping_predicates`)
# que solo saben "conectado/no conectado" o "a distancia <=N", sin
# ninguna senal de "cuanto falta". `min_exterior_sides==0` (piezas de
# nucleo repartidas por `_assign_core_rooms_to_pieces`, sin validador
# duro propio -- son la causa geometrica de fondo del resto) se suma a
# los 3 agrupamientos de zona + el nucleo humedo, para que el gradiente
# cubra exactamente las 4 categorias de violacion medidas en los 5
# escenarios reales de `test_generate_layout_use_case_v2.py`. Ver
# [ARCH:perimeter-core-layout-generator].
GROUPING_PREDICATES: List[Tuple[Callable[[Room], bool], str]] = [
    (lambda r: r.min_exterior_sides == 0, "piezas de nucleo"),
    (lambda r: r.is_wet, "nucleo humedo"),
] + zone_grouping_predicates()


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
        graph_builder: Optional[AdjacencyGraphBuilderPort] = None,
    ):
        self._constraint_validator = constraint_validator
        self._max_iterations = max_iterations
        self._initial_temperature = initial_temperature
        self._cooling_rate = cooling_rate
        self._seed = seed
        self._soft_scorer = soft_constraint_scorer
        self._graph_builder = graph_builder

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        rng = random.Random(
            self._seed
        )  # recreado en cada llamada, seed reproducible siempre
        all_room_ids = [room.id for room in program.rooms]
        areas = {room.id: room.dimensions.area_m2 for room in program.rooms}
        entrance_hall_id = find_entrance_hall_id(program)

        tallable = tallable_length_per_side(
            lot.area_edificable_real.polygon, lot.medianera_sides
        )
        available_sides = [side for side, length in tallable.items() if length > 0]

        current_state = build_initial_perimeter_core_state(program, lot, rng)
        current_layout = materialize_perimeter_core(current_state, program, lot)
        current_hard, current_soft, current_locked = self._evaluate(
            current_layout, all_room_ids
        )

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            candidate_state = random_neighbor_perimeter_core(
                current_state,
                rng,
                areas,
                entrance_hall_id,
                available_sides,
                locked_room_ids=current_locked,
            )
            candidate_layout = materialize_perimeter_core(candidate_state, program, lot)
            candidate_hard, candidate_soft, candidate_locked = self._evaluate(
                candidate_layout, all_room_ids
            )

            # comparacion lexicografica: si lo duro cambia, decide solo
            # el delta duro; lo blando solo cuenta si empata. Ver
            # [ARCH:simulated-annealing] (mismo criterio que
            # BTreeLayoutGenerator).
            delta: float
            if candidate_hard != current_hard:
                delta = candidate_hard - current_hard
            else:
                delta = candidate_soft - current_soft

            accepted = delta <= 0 or rng.random() < math.exp(
                -delta / max(temperature, 1e-9)
            )
            if accepted:
                current_state, current_layout = candidate_state, candidate_layout
                current_hard, current_soft, current_locked = (
                    candidate_hard,
                    candidate_soft,
                    candidate_locked,
                )
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

    def _evaluate(
        self, layout: Layout, all_room_ids: List[str]
    ) -> Tuple[int, float, Set[str]]:
        """Una sola validación por layout, reutilizada para la
        puntuación (duro/blando) Y el bloqueo progresivo -- mismo
        patrón que `BTreeLayoutGenerator._evaluate`."""
        violations = self._constraint_validator.validate(layout).violations
        hard = len(violations)
        soft = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        soft += self._grouping_proximity_penalty(layout)
        violating_ids = {
            room_id
            for room_id in all_room_ids
            if any(f"'{room_id}'" in v for v in violations)
        }
        locked = set(all_room_ids) - violating_ids
        return hard, soft, locked

    def _grouping_proximity_penalty(self, layout: Layout) -> float:
        """Incentivo BLANDO (gradiente real por distancia, no conteo
        binario) para que cada grupo de `GROUPING_PREDICATES` termine
        formando un único bloque geométricamente conectado --
        `_assign_core_rooms_to_pieces` (perimeter_core_partition.py)
        puede repartir el núcleo entre piezas del residuo DESCONECTADAS
        entre sí (hallazgo real de la Fase 3, ver docstring de
        `test_generate_layout_use_case_v2.py`), lo que además deja
        estancias húmedas/de zona perimetrales (p.ej. `KITCHEN`) sin
        conexión real con el resto de su grupo. Los validadores que
        detectan esto (`NucleoHumedoValidator`/agrupación de zonas
        día-noche-servicio/`PasilloTopologiaValidator`/
        `BanoAccesoGeneralValidator`) solo saben "conectado o no", sin
        ninguna señal de "cuánto falta" -- mismo problema de fondo que
        motivó `_stair_corner_penalty` en `btree_layout_generator.py`,
        mismo remedio aquí, generalizado a los 4 grupos relevantes en
        vez de solo al núcleo. Sin `graph_builder` (no conectado en
        `container.py`), no hay nada que penalizar. Ver
        [ARCH:perimeter-core-layout-generator]."""
        if self._graph_builder is None:
            return 0.0
        graph = self._graph_builder.build(layout)
        return (
            sum(
                self._component_gap_penalty(
                    graph, [r for r in layout.rooms if r.is_placed and predicate(r)]
                )
                for predicate, _label in GROUPING_PREDICATES
            )
            * CORE_PROXIMITY_WEIGHT
        )

    @staticmethod
    def _component_gap_penalty(graph: nx.Graph, members: List[Room]) -> float:
        """Suma de huecos geométricos mínimos necesarios para unir,
        mediante un árbol generador mínimo (Prim) sobre la distancia
        entre componentes, todos los componentes conexos de `members`
        dentro de `graph` en uno solo -- 0.0 si ya hay un único
        componente (o menos de 2 miembros). Ver
        [ARCH:perimeter-core-layout-generator]."""
        if len(members) < 2:
            return 0.0
        subgraph = graph.subgraph([r.id for r in members])
        components = list(nx.connected_components(subgraph))
        if len(components) <= 1:
            return 0.0

        polygons_by_id = {r.id: r.boundary.polygon for r in members}

        def component_gap(a: Set[str], b: Set[str]) -> float:
            return min(
                polygons_by_id[i].distance(polygons_by_id[j]) for i in a for j in b
            )

        connected = [components[0]]
        remaining = components[1:]
        total_gap = 0.0
        while remaining:
            best_idx, best_gap = None, None
            for idx, comp in enumerate(remaining):
                gap = min(component_gap(c, comp) for c in connected)
                if best_gap is None or gap < best_gap:
                    best_idx, best_gap = idx, gap
            total_gap += best_gap
            connected.append(remaining.pop(best_idx))
        return total_gap
