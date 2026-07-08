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
    """Genera el layout construyendo un arbol de particion recursivo sobre
    TODAS las estancias del programa a la vez (sin fase previa de reparto
    por macro-zona geometrica) y buscando la mejor topologia mediante
    recocido simulado.

    La funcion objetivo combina violaciones DURAS (siempre dominantes)
    con una penalizacion BLANDA opcional (Preferencia cerca/alejar) --
    ver `_score`. Comparacion LEXICOGRAFICA real (tupla `(duro, blando)`),
    no suma ponderada: una primera version sumaba `duro*peso_grande +
    blando`, que garantiza el orden final correcto pero rompe la
    dinamica de aceptacion del recocido (`exp(-delta/temperatura)`
    reacciona a la magnitud absoluta del delta, no solo al orden
    relativo -- confirmado que rompia tests que no tocaban nada de las
    restricciones blandas). Con la tupla, cuando lo duro cambia entre
    candidato y actual, la aceptacion se decide SOLO por ese delta (a su
    escala natural, igual que antes de anadir nada blando); lo blando
    solo entra en juego cuando lo duro empata.

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
        soft_constraint_scorer: Optional[SoftConstraintScorer] = None,
    ):
        self._constraint_validator = constraint_validator
        self._max_iterations = max_iterations
        self._initial_temperature = initial_temperature
        self._cooling_rate = cooling_rate
        self._seed = seed
        self._soft_scorer = soft_constraint_scorer

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        # BUG REAL encontrado en auditoria: antes, `self._rng` se creaba
        # UNA sola vez en __init__ y esta misma instancia se reutilizaba
        # entre llamadas -- `seed` solo garantizaba un resultado
        # reproducible en la PRIMERA llamada a generate(); cualquier
        # llamada posterior sobre el MISMO generador continuaba desde
        # donde quedo la secuencia aleatoria anterior, no desde la
        # semilla, rompiendo el determinismo que el resto del proyecto
        # da por hecho (confirmado: llamar generate() dos veces seguidas
        # con seed=1 daba resultados distintos la segunda vez). Reiniciar
        # aqui, en cada llamada, hace que la semilla sea reproducible
        # SIEMPRE, no solo la primera vez.
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

            # BUG REAL encontrado al conectar las restricciones blandas:
            # una primera version combinaba duro+blando en un UNICO
            # numero (hard*1000 + soft) para la aceptacion del recocido.
            # Esto garantiza el orden final correcto, pero ROMPE la
            # dinamica de aceptacion: exp(-delta/temperatura) reacciona a
            # la MAGNITUD absoluta del delta, no solo al orden relativo
            # -- multiplicar por 1000 hacia practicamente imposible
            # aceptar CUALQUIER movimiento que empeorase lo duro, incluso
            # al principio con temperatura alta, cambiando el
            # comportamiento ya afinado de todo el proyecto (confirmado:
            # rompio un test de multi-planta que no tocaba nada de esto).
            # Corregido con comparacion LEXICOGRAFICA real: si lo duro
            # cambia, la aceptacion se decide SOLO por el delta duro (a
            # su escala natural, pequeña, igual que antes de tocar nada
            # de esto); solo se mira lo blando cuando lo duro empata.
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
