from typing import Callable, Dict, List, Optional
from shapely.geometry import box
from shapely.geometry.base import BaseGeometry
from housing_generator.application.ports.zoning_strategy_port import ZoningStrategyPort
from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.ports.viabilidad_urbanistica_validator_port import (
    ViabilidadUrbanisticaValidatorPort,
)
from housing_generator.domain.entities.building import Building
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import NivelPlanta, NIVEL_PLANTA_ORDEN, RoomType, SpaceCategory
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Fabrica de validadores por planta -- funcion, no clases concretas
# (aplicacion no depende de infraestructura). Ver [ARCH:generate-building].
PerFloorValidatorsFactory = Callable[
    [List[AdjacencyRequirement], Optional[BaseGeometry], List[BaseGeometry], int, Dict[str, int], bool],
    ConstraintValidatorPort,
]
LayoutGeneratorFactory = Callable[[ConstraintValidatorPort, List[AdjacencyRequirement]], LayoutGeneratorPort]


class GenerateBuildingUseCase:
    """Orquesta la generación de una vivienda de varias plantas: agrupa
    por `Room.level`, genera cada planta de abajo a arriba (búsqueda
    independiente por planta), encadenando alineación de escalera y
    continuidad de núcleo húmedo entre plantas consecutivas. Ver
    [ARCH:generate-building].
    """

    def __init__(
        self,
        per_floor_validators_factory: PerFloorValidatorsFactory,
        layout_generator_factory: LayoutGeneratorFactory,
        zoning_strategy: ZoningStrategyPort,
        programa_minimo_validator: ConstraintValidatorPort,
        bano_acceso_validator: ConstraintValidatorPort,
        viabilidad_urbanistica_validator: Optional[ViabilidadUrbanisticaValidatorPort] = None,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ):
        self._per_floor_validators_factory = per_floor_validators_factory
        self._layout_generator_factory = layout_generator_factory
        self._zoning_strategy = zoning_strategy
        self._programa_minimo_validator = programa_minimo_validator
        self._bano_acceso_validator = bano_acceso_validator
        self._viabilidad_urbanistica_validator = viabilidad_urbanistica_validator
        self._adjacency_requirements = adjacency_requirements or []

    def execute(self, program: Program, lot: Lot) -> Building:
        rooms_by_level = self._group_by_level(program.rooms)
        levels = [lvl for lvl in NIVEL_PLANTA_ORDEN if lvl in rooms_by_level]

        # comprobacion de viabilidad urbanistica ANTES de generar nada
        # -- mismo espiritu que un informe de viabilidad real (Fase 4
        # de la hoja de ruta investigada con el usuario): si el
        # programa no es urbanisticamente viable, decirlo al instante,
        # no despues de minutos de busqueda que nunca podia tener
        # exito. Ver [ARCH:viabilidad-urbanistica].
        if self._viabilidad_urbanistica_validator is not None:
            viabilidad = self._viabilidad_urbanistica_validator.validate(program, lot, len(levels))
            if not viabilidad.is_valid:
                raise LayoutGenerationError(
                    f"Programa no viable urbanisticamente: {viabilidad.violations}"
                )

        total_num_estancias = sum(1 for r in program.rooms if r.space_category == SpaceCategory.ESTANCIA)
        global_rank = self._compute_global_rank(program.rooms)

        building = Building()
        previous_layout: Optional[Layout] = None
        # HALLAZGO REAL, confirmado con captura del navegador: antes de
        # esto, se usaba SIEMPRE lot.buildable_area.polygon (el
        # rectangulo de trabajo), nunca el poligono real importado --
        # una vivienda generada podia colocar estancias en las
        # esquinas donde el rectangulo sobresale del poligono real
        # (hasta 49m2 en un caso real). Investigado antes de
        # implementar: la tecnica real (GFLAN 2025) es seguir
        # generando con un rectangulo de partida, pero derivarlo del
        # poligono real YA reducido por retranqueo (mas ajustado, no
        # el rectangulo completo sin reducir) -- el rectangulo sigue
        # pudiendo sobresalir un poco en las esquinas, por eso
        # ParcelaRealValidator (restriccion dura) es la garantia real,
        # no el ajuste de este rectangulo de partida. Se mantiene
        # axis-aligned (bounds, no minimum_rotated_rectangle) a
        # proposito -- una rotacion complicaria el sistema de
        # coordenadas que usa el resto del pipeline (anclaje,
        # entrance_side). Ver [ARCH:parcela-real].
        if lot.poligono_real is not None:
            area_real = lot.area_edificable_real.polygon
            if area_real.is_empty:
                # mismo comportamiento que buildable_area colapsada (caja):
                # un poligono vacio real, no un box con NaN -- el resto del
                # pipeline ya sabe fallar con claridad ante esto.
                current_buildable_polygon: BaseGeometry = area_real
            else:
                minx, miny, maxx, maxy = area_real.bounds
                current_buildable_polygon = box(minx, miny, maxx, maxy)
        else:
            current_buildable_polygon = lot.buildable_area.polygon

        for level in levels:
            level_rooms = rooms_by_level[level]
            level_room_ids = {r.id for r in level_rooms}
            level_adjacency = [
                req for req in self._adjacency_requirements
                if req.room_a_id in level_room_ids and req.room_b_id in level_room_ids
            ]
            level_program = Program(rooms=level_rooms, adjacency_requirements=level_adjacency)

            reference_stair = self._staircase_boundary(previous_layout)
            reference_wet = self._wet_boundaries(previous_layout)
            floor_below_exists = previous_layout is not None

            # encogimiento progresivo del contorno, solo desde la 2a
            # planta. Ver [ARCH:generate-building].
            if floor_below_exists:
                current_buildable_polygon = self._shrink_for_next_floor(
                    current_buildable_polygon, lot.retranqueo_incremento_por_planta_m, level_rooms,
                )
            floor_lot = Lot(
                boundary=Boundary(polygon=current_buildable_polygon),
                entrance_side=lot.entrance_side,
                street_side=lot.street_side,
                retranqueo_m=None,  # ya aplicado al construir current_buildable_polygon
                poligono_real=lot.poligono_real,  # para que ParcelaRealValidator compruebe cada planta
            )

            composite = self._per_floor_validators_factory(
                level_adjacency, reference_stair, reference_wet, total_num_estancias, global_rank,
                floor_below_exists,
            )
            generator = self._layout_generator_factory(composite, level_adjacency)
            zones = self._zoning_strategy.build_zones(level_program)
            layout = generator.generate(level_program, floor_lot, zones)

            result = composite.validate(layout)
            if not result.is_valid:
                raise LayoutGenerationError(
                    f"No se pudo generar un layout valido para la planta '{level.value}'. "
                    f"Ultimas violaciones: {result.violations}"
                )

            building.floors[level] = layout
            previous_layout = layout

        self._check_programa_minimo(building)
        self._check_bano_acceso_general(building)
        return building

    @staticmethod
    def _shrink_for_next_floor(
        previous_polygon: BaseGeometry, increment_m: Optional[float], level_rooms: List[Room],
    ) -> BaseGeometry:
        """Encoge el contorno de la planta anterior por `increment_m`
        (mismo mecanismo que `Lot.buildable_area`). Con red de
        seguridad -- ver [ARCH:generate-building]."""
        if increment_m is None or increment_m <= 0:
            return previous_polygon

        shrunk = previous_polygon.buffer(-increment_m)
        required_area = sum(r.dimensions.area_m2 for r in level_rooms)
        if shrunk.area < required_area:
            return previous_polygon  # red de seguridad: copia exacta, no un area inviable
        return shrunk

    @staticmethod
    def _compute_global_rank(rooms: List[Room]) -> Dict[str, int]:
        """Puesto de Tabla 1 (1=mayor) de cada estancia entre TODAS las
        del edificio, precalculado antes de generar ninguna planta --
        las areas son DECLARADAS en el Program, no dependen de la
        geometria ya colocada, asi que esto se puede saber de antemano."""
        estancias = [r for r in rooms if r.space_category == SpaceCategory.ESTANCIA]
        ordenadas = sorted(estancias, key=lambda r: r.dimensions.area_m2, reverse=True)
        return {room.id: puesto for puesto, room in enumerate(ordenadas, start=1)}

    @staticmethod
    def _group_by_level(rooms: List[Room]) -> Dict[NivelPlanta, List[Room]]:
        grouped: Dict[NivelPlanta, List[Room]] = {}
        for room in rooms:
            level = room.level or NivelPlanta.PLANTA_BAJA
            grouped.setdefault(level, []).append(room)
        return grouped

    @staticmethod
    def _staircase_boundary(layout: Optional[Layout]) -> Optional[BaseGeometry]:
        if layout is None:
            return None
        for room in layout.rooms:
            if room.room_type == RoomType.STAIRCASE and room.is_placed:
                return room.boundary.polygon
        return None

    @staticmethod
    def _wet_boundaries(layout: Optional[Layout]) -> List[BaseGeometry]:
        if layout is None:
            return []
        return [r.boundary.polygon for r in layout.rooms if r.is_wet and r.is_placed]

    def _check_bano_acceso_general(self, building: Building) -> None:
        """Reutiliza el validador de una sola planta, ejecutado POR
        PLANTA -- la accesibilidad de un baño no se hereda de otra
        planta. Ver [ARCH:generate-building]."""
        any_bathroom_anywhere = any(
            r.room_type == RoomType.BATHROOM for layout in building.floors.values() for r in layout.rooms
        )
        if not any_bathroom_anywhere:
            return  # ninguna planta tiene banos -- ViviendaMinimaValidator ya lo habria bloqueado antes

        for layout in building.floors.values():
            has_bathroom_here = any(r.room_type == RoomType.BATHROOM for r in layout.rooms)
            if not has_bathroom_here:
                continue
            if self._bano_acceso_validator.validate(layout).is_valid:
                return  # esta planta ya tiene al menos un bano con acceso general -- suficiente

        raise LayoutGenerationError(
            "Ninguna planta del edificio tiene un baño con acceso directo a circulación "
            "general (CORRIDOR/ENTRANCE_HALL) -- con varias plantas, todos los baños "
            "quedarían en-suite, sin ninguno de acceso general para el conjunto de la vivienda"
        )

    def _check_programa_minimo(self, building: Building) -> None:
        all_rooms = [room for layout in building.floors.values() for room in layout.rooms]
        synthetic_layout = Layout(
            lot=next(iter(building.floors.values())).lot,
            rooms=all_rooms,
            zones=[],
        )
        result = self._programa_minimo_validator.validate(synthetic_layout)
        if not result.is_valid:
            raise LayoutGenerationError(
                f"El edificio completo no cumple el programa minimo de vivienda "
                f"(comprobado uniendo todas las plantas): {result.violations}"
            )
