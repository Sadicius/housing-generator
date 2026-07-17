import copy
import math
import random
from typing import Dict, List, Optional, Tuple

from shapely.affinity import scale, translate
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.infrastructure.geometry.shapely_utils import polygon_to_shapes
from housing_generator.infrastructure.algorithms.layout_generation.btree_partition import (
    BStarNode,
    build_random_tree,
    compute_positions,
    force_aspect_ratio,
    random_neighbor,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)


ORIENTACIONES = [(False, False), (True, False), (False, True), (True, True)]
ORIENTATION_MOVE_PROBABILITY = 0.1  # NO normativo, mismo criterio que
# btree_partition.ESCAPE_PROBABILITY: con que frecuencia se prueba una
# orientacion distinta en vez de mutar el arbol -- solo tiene efecto
# cuando hay escalera compartida (reference_stair), ver
# [ARCH:escalera-compartida].
STAIR_CORNER_PREFERENCE_WEIGHT = 0.1  # NO normativo, mismo tipo de
# decision de ingenieria que el resto de pesos blandos -- pequeno a
# proposito, la escalera solo debe "preferir" la esquina, nunca
# dominar sobre las restricciones duras reales. Ver
# [ARCH:escalera-compartida].


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
        reference_stair: Optional[BaseGeometry] = None,
    ):
        self._constraint_validator = constraint_validator
        self._max_iterations = max_iterations
        self._initial_temperature = initial_temperature
        self._cooling_rate = cooling_rate
        self._seed = seed
        self._soft_scorer = soft_constraint_scorer
        # huella de la escalera YA resuelta en la planta de referencia
        # (la de abajo) -- si esta planta tambien tiene una escalera,
        # se ancla a esta forma+posicion EXACTA en vez de buscarla por
        # recocido, convirtiendo la alineacion entre plantas
        # (EscaleraAlineacionValidator) en una garantia estructural, no
        # un objetivo probabilistico. Ver [ARCH:escalera-compartida].
        self._reference_stair = reference_stair

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        rng = random.Random(self._seed)  # recreado en cada llamada, seed reproducible siempre
        room_ids = [room.id for room in program.rooms]
        areas = {room.id: room.dimensions.area_m2 for room in program.rooms}
        stair_room_id = self._stair_room_id(program) if self._reference_stair is not None else None

        current_tree = build_random_tree(room_ids, rng)
        if stair_room_id is not None:
            current_tree = self._anchor_stair_shape(current_tree, stair_room_id)
        current_orientation = (False, False)
        current_layout = self._materialize(current_tree, program, lot, areas, stair_room_id, current_orientation)
        current_hard, current_soft, current_locked = self._evaluate(current_layout, room_ids)

        best_layout = current_layout
        best_hard, best_soft = current_hard, current_soft

        temperature = self._initial_temperature
        for _ in range(self._max_iterations):
            if best_hard == 0 and best_soft == 0:
                break

            # con escalera compartida, la traslacion queda FIJA (ancla a
            # la referencia) -- se pierde la libertad de centrar el
            # resto del empaquetado que antes daba el anclaje por
            # entrance_side. El espejado (4 orientaciones posibles
            # alrededor del mismo punto de anclaje, la escalera sigue
            # coincidiendo exacto en las 4) devuelve un grado de libertad
            # barato para que el resto de estancias aun puedan encontrar
            # una orientacion que si toque el exterior. Ver
            # [ARCH:escalera-compartida].
            if stair_room_id is not None and rng.random() < ORIENTATION_MOVE_PROBABILITY:
                candidate_tree = current_tree
                candidate_orientation = self._random_other_orientation(current_orientation, rng)
            else:
                candidate_tree = random_neighbor(current_tree, rng, areas, locked_room_ids=current_locked)
                if stair_room_id is not None:
                    candidate_tree = self._anchor_stair_shape(candidate_tree, stair_room_id)
                candidate_orientation = current_orientation
            candidate_layout = self._materialize(
                candidate_tree, program, lot, areas, stair_room_id, candidate_orientation,
            )
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
                current_tree, current_orientation, current_layout = candidate_tree, candidate_orientation, candidate_layout
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
        # metadatos de compatibilidad -- el generador clasico
        # (SimulatedAnnealingLayoutGenerator, eliminado) los exponia,
        # hallazgo real al eliminarlo: un test dependia de
        # metadata["hard_violations"] existiendo, KeyError sin esto.
        best_layout.metadata["annealing_score"] = best_hard
        best_layout.metadata["hard_violations"] = best_hard
        best_layout.metadata["soft_penalty"] = best_soft
        return best_layout

    def _materialize(
        self, tree: BStarNode, program: Program, lot: Lot, areas: Dict[str, float],
        stair_room_id: Optional[str] = None, orientation: Tuple[bool, bool] = (False, False),
    ) -> Layout:
        # a diferencia del arbol de particion (huella decidida de
        # antemano, ver footprint.py), aqui la huella es el RESULTADO
        # del propio empaquetado -- se calcula primero (siempre parte
        # de (0,0)) y se ancla despues, no al reves. Ver [ARCH:btree-partition].
        positions = compute_positions(tree, areas)
        if orientation != (False, False):
            positions = self._mirror_positions(positions, orientation)
        buildable_polygon = lot.buildable_area.polygon
        if stair_room_id is not None and self._reference_stair is not None:
            offset_x, offset_y = self._anchor_offset_to_reference_stair(
                positions[stair_room_id], self._reference_stair,
            )
        else:
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

    @staticmethod
    def _anchor_offset_to_reference_stair(
        own_stair: Polygon, reference_stair: BaseGeometry,
    ) -> Tuple[float, float]:
        """Traslada el empaquetado para que la escalera de ESTA planta
        (`own_stair`, en las coordenadas crudas del arbol, siempre con
        la misma forma que la referencia gracias a `_anchor_stair_shape`)
        caiga EXACTAMENTE sobre la posicion absoluta de la escalera ya
        resuelta en la planta de referencia -- en vez de centrar el
        conjunto por `entrance_side`. Con la misma forma garantizada,
        una simple traslacion basta para el 100% de solape. Ver
        [ARCH:escalera-compartida]."""
        own_minx, own_miny, _, _ = own_stair.bounds
        ref_minx, ref_miny, _, _ = reference_stair.bounds
        return ref_minx - own_minx, ref_miny - own_miny

    @staticmethod
    def _stair_room_id(program: Program) -> Optional[str]:
        """Primera estancia STAIRCASE del programa, o None si esta
        planta no tiene escalera propia -- en ese caso no hay nada que
        anclar a la referencia, se usa el anclaje normal por
        `entrance_side`. Ver [ARCH:escalera-compartida]."""
        return next((r.id for r in program.rooms if r.room_type == RoomType.STAIRCASE), None)

    def _anchor_stair_shape(self, tree: BStarNode, stair_room_id: str) -> BStarNode:
        """Fuerza la escalera del arbol a la MISMA proporcion (ancho/alto)
        que `self._reference_stair`, tras CUALQUIER mutacion -- sea cual
        sea el nodo que ahora represente esa estancia (un `swap` pudo
        haberla movido a un nodo con otra proporcion). Con la misma area
        declarada (convenio del programa: la escalera mide lo mismo en
        todas las plantas) y la misma proporcion, la forma resultante es
        IDENTICA a la referencia -- basta una traslacion para el 100% de
        solape, ver `_anchor_offset_to_reference_stair`. Ver
        [ARCH:escalera-compartida]."""
        assert self._reference_stair is not None
        minx, miny, maxx, maxy = self._reference_stair.bounds
        target_aspect_ratio = (maxx - minx) / (maxy - miny)
        return force_aspect_ratio(tree, stair_room_id, target_aspect_ratio)

    @staticmethod
    def _mirror_positions(
        positions: Dict[str, Polygon], orientation: Tuple[bool, bool],
    ) -> Dict[str, Polygon]:
        """Espeja TODO el empaquetado (horizontal y/o vertical) alrededor
        del centro del conjunto -- conserva la forma y el area de cada
        estancia (incluida la escalera, ya anclada), solo cambia que
        estancia queda a cada lado. Ver [ARCH:escalera-compartida]."""
        mirror_h, mirror_v = orientation
        minx, miny, maxx, maxy = unary_union(list(positions.values())).bounds
        centro = ((minx + maxx) / 2, (miny + maxy) / 2)
        xfact = -1 if mirror_h else 1
        yfact = -1 if mirror_v else 1
        return {
            room_id: scale(poly, xfact=xfact, yfact=yfact, origin=centro)
            for room_id, poly in positions.items()
        }

    @staticmethod
    def _random_other_orientation(
        current: Tuple[bool, bool], rng: random.Random,
    ) -> Tuple[bool, bool]:
        opciones = [o for o in ORIENTACIONES if o != current]
        return rng.choice(opciones)

    def _stair_corner_penalty(self, layout: Layout) -> float:
        """Preferencia BLANDA (gradiente real, no conteo binario) para
        que la escalera de la planta que DEFINE la posicion compartida
        quede cerca de una esquina del area edificable -- practica real
        confirmada en la literatura de generacion multi-planta (nucleo
        de circulacion vertical en esquinas con dos paredes exteriores,
        para dejar sitio al resto de estancias tocar el exterior; ver
        commit). Solo activa cuando `self._reference_stair is None`
        (esta planta decide la posicion, no la hereda de otra) -- las
        plantas siguientes ya tienen la posicion forzada, nada que
        preferir ahi. Distancia continua (no 0/1) a proposito: da
        gradiente real a la busqueda, a diferencia de un validador duro
        que solo sabe "cumple/no cumple". Ver [ARCH:escalera-compartida]."""
        stair = next((r for r in layout.rooms if r.room_type == RoomType.STAIRCASE and r.is_placed), None)
        if stair is None:
            return 0.0
        minx, miny, maxx, maxy = layout.lot.buildable_area.polygon.bounds
        cx, cy = stair.boundary.polygon.centroid.coords[0]
        esquinas = [(minx, miny), (minx, maxy), (maxx, miny), (maxx, maxy)]
        distancia_minima = min(math.hypot(cx - ex, cy - ey) for ex, ey in esquinas)
        return distancia_minima * STAIR_CORNER_PREFERENCE_WEIGHT

    def _evaluate(self, layout: Layout, all_room_ids: List[str]) -> Tuple[int, float, set]:
        """Una sola validacion por layout, reutilizada para la
        puntuacion (duro/blando) Y el bloqueo progresivo -- mismo
        patron que `SimulatedAnnealingLayoutGenerator._evaluate`."""
        violations = self._constraint_validator.validate(layout).violations
        hard = len(violations)
        soft = self._soft_scorer.score(layout) if self._soft_scorer else 0.0
        if self._reference_stair is None:
            soft += self._stair_corner_penalty(layout)
        violating_ids = {
            room_id for room_id in all_room_ids
            if any(f"'{room_id}'" in v for v in violations)
        }
        locked = set(all_room_ids) - violating_ids
        return hard, soft, locked
