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
from housing_generator.infrastructure.algorithms.layout_generation.footprint import (
    footprint_target_area,
    footprint_rectangle,
    initial_footprint_width,
    resize_footprint_width,
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

        # huella construible: NO ocupa el 100% de la parcela -- se
        # calcula del tamano justo para el programa declarado (+
        # margen), el resto queda como VACIO real (exterior). La
        # PROPORCION de la huella (ancho:alto) tambien es parte de la
        # busqueda, no fija -- confirmado explicitamente. Ver
        # [ARCH:area-objetivo].
        buildable = lot.buildable_area.polygon
        bminx, bminy, bmaxx, bmaxy = buildable.bounds
        buildable_w, buildable_h = bmaxx - bminx, bmaxy - bminy
        footprint_area = footprint_target_area(sum(areas.values()))
        current_footprint_width = initial_footprint_width(footprint_area, buildable_w, buildable_h)

        current_tree = build_random_tree(room_ids, self._rng)
        current_layout = self._materialize(current_tree, current_footprint_width, footprint_area, program, lot, areas)
        current_hard, current_soft, current_locked = self._evaluate(current_layout, room_ids)

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            if self._rng.random() < 0.2:  # 20%: redimensionar huella, no tocar arbol
                candidate_tree = current_tree
                candidate_footprint_width = resize_footprint_width(
                    current_footprint_width, footprint_area, buildable_w, buildable_h, self._rng
                )
            else:
                # bloqueo progresivo: las estancias SIN violaciones
                # actuales quedan protegidas de la mayoria de
                # movimientos -- ver [ARCH:locking-progresivo].
                candidate_tree = random_neighbor(current_tree, self._rng, areas, locked_room_ids=current_locked)
                candidate_footprint_width = current_footprint_width

            candidate_layout = self._materialize(candidate_tree, candidate_footprint_width, footprint_area, program, lot, areas)
            candidate_hard, candidate_soft, candidate_locked = self._evaluate(candidate_layout, room_ids)

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
                current_footprint_width = candidate_footprint_width
                current_hard, current_soft, current_locked = candidate_hard, candidate_soft, candidate_locked
                if (current_hard, current_soft) < (best_hard, best_soft):
                    best_layout = current_layout
                    best_hard, best_soft = current_hard, current_soft

            temperature *= self._cooling_rate

        best_layout.metadata["annealing_score"] = best_hard  # compatibilidad: violaciones duras del mejor layout
        best_layout.metadata["hard_violations"] = best_hard
        best_layout.metadata["soft_penalty"] = best_soft
        return best_layout

    def _evaluate(self, layout: Layout, all_room_ids: List[str]) -> tuple:
        """Una sola validacion por layout, reutilizada para la
        puntuacion (duro/blando) Y el bloqueo progresivo -- evita
        validar dos veces por iteracion. Devuelve
        (hard, soft, locked_room_ids)."""
        violations = self._constraint_validator.validate(layout).violations
        hard = len(violations)
        soft = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        violating_ids = {
            room_id for room_id in all_room_ids
            if any(f"'{room_id}'" in v for v in violations)
        }
        locked = set(all_room_ids) - violating_ids
        return hard, soft, locked

    def _materialize(
        self,
        tree: PartitionNode,
        footprint_width: float,
        footprint_area: float,
        program: Program,
        lot: Lot,
        areas: Dict[str, float],
    ) -> Layout:
        # huella construible dentro del area edificable, NO toda ella
        # -- ver footprint.py, [ARCH:area-objetivo].
        buildable_polygon = lot.buildable_area.polygon
        footprint_polygon = footprint_rectangle(buildable_polygon, footprint_width, footprint_area, lot.entrance_side)
        placements = place_tree(tree, footprint_polygon, areas)

        placed_rooms = []
        for room in program.rooms:
            placed_room = copy.copy(room)  # copia superficial: no muta el Room del Program original
            placed_room.boundary = Boundary(polygon=placements[room.id])
            placed_rooms.append(placed_room)

        zones_map: Dict = {}
        for room in placed_rooms:
            zones_map.setdefault(room.zone, []).append(room.id)
        built_zones = [Zone(zone_type=zone_type, room_ids=ids) for zone_type, ids in zones_map.items()]

        layout = Layout(lot=lot, rooms=placed_rooms, zones=built_zones)
        # VACIO: exterior real (jardin/patio), no un Room del dominio
        # -- solo geometria para el visor. Coordenadas directas (no WKT)
        # para que el visor las dibuje sin necesitar un parser de WKT en
        # JS -- una lista de anillos, cada uno lista de [x,y] (soporta
        # Polygon y MultiPolygon si la resta produce varias piezas
        # separadas). Ver [ARCH:area-objetivo].
        vacio_polygon = buildable_polygon.difference(footprint_polygon)
        layout.metadata["vacio_rings"] = self._polygon_to_rings(vacio_polygon)
        return layout

    @staticmethod
    def _polygon_to_rings(geom) -> List[List[List[float]]]:
        if geom.is_empty:
            return []
        polygons = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        return [[list(coord) for coord in poly.exterior.coords] for poly in polygons]
