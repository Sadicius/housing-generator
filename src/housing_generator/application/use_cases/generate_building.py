from typing import Callable, Dict, List, Optional
from shapely.geometry.base import BaseGeometry
from housing_generator.application.ports.zoning_strategy_port import ZoningStrategyPort
from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.domain.entities.building import Building
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import NivelPlanta, NIVEL_PLANTA_ORDEN, RoomType, SpaceCategory
from housing_generator.domain.exceptions import LayoutGenerationError
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Firma de la fabrica de validadores por planta: recibe los requisitos
# de adyacencia de ESA planta, la huella de escalera de referencia de la
# planta inferior (o None), la lista de huellas humedas de referencia
# (o vacia), y el numero TOTAL de estancias del EDIFICIO COMPLETO (para
# que Tabla 1/2 elijan la fila correcta -- bug real encontrado al
# generar el primer edificio de prueba: sin esto, una planta con pocas
# estancias aplicaba una fila de Tabla 1/2 mas baja de la que
# corresponderia con el conteo real del edificio). Devuelve el
# validador COMPLETO (compuesto) para esa planta. Se inyecta como
# funcion, no como clases concretas, para que esta capa de aplicacion no
# dependa de infraestructura (regla ya establecida en
# GenerateLayoutUseCase -- se encontro y corrigio aqui una violacion
# real de esa regla durante la construccion de este caso de uso: la
# primera version importaba directamente de config.container).
PerFloorValidatorsFactory = Callable[
    [List[AdjacencyRequirement], Optional[BaseGeometry], List[BaseGeometry], int],
    ConstraintValidatorPort,
]
LayoutGeneratorFactory = Callable[[ConstraintValidatorPort], LayoutGeneratorPort]


class GenerateBuildingUseCase:
    """Orquesta la generacion de una vivienda de VARIAS plantas: agrupa
    `program.rooms` por `Room.level`, genera cada planta de abajo a
    arriba (una busqueda independiente por planta, no conjunta -- ver
    docs/architecture.md), encadenando dos restricciones ENTRE plantas
    consecutivas a traves de `per_floor_validators_factory`:
    - alineacion de huella de escalera con la planta de abajo YA
      RESUELTA (pasada como referencia fija -- no hace falta busqueda
      conjunta ni un tipo de movimiento nuevo en el recocido simulado).
    - continuidad vertical de nucleo humedo (solape en planta con alguna
      humeda de la planta inferior).

    Primer incremento deliberadamente simplificado (ver
    docs/architecture.md): TODAS las plantas comparten el mismo
    `lot.buildable_area`; el programa minimo de vivienda se comprueba
    UNA sola vez, a nivel de EDIFICIO completo (uniendo los tipos de
    todas las plantas), no por planta -- una vivienda de dos plantas con
    salon abajo y bano arriba SI cumple el programa minimo, aunque
    ninguna planta por separado lo cumpla.
    """

    def __init__(
        self,
        per_floor_validators_factory: PerFloorValidatorsFactory,
        layout_generator_factory: LayoutGeneratorFactory,
        zoning_strategy: ZoningStrategyPort,
        programa_minimo_validator: ConstraintValidatorPort,
        adjacency_requirements: Optional[List[AdjacencyRequirement]] = None,
    ):
        self._per_floor_validators_factory = per_floor_validators_factory
        self._layout_generator_factory = layout_generator_factory
        self._zoning_strategy = zoning_strategy
        self._programa_minimo_validator = programa_minimo_validator
        self._adjacency_requirements = adjacency_requirements or []

    def execute(self, program: Program, lot: Lot) -> Building:
        rooms_by_level = self._group_by_level(program.rooms)
        levels = [lvl for lvl in NIVEL_PLANTA_ORDEN if lvl in rooms_by_level]
        total_num_estancias = sum(1 for r in program.rooms if r.space_category == SpaceCategory.ESTANCIA)

        building = Building()
        previous_layout: Optional[Layout] = None

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

            composite = self._per_floor_validators_factory(
                level_adjacency, reference_stair, reference_wet, total_num_estancias
            )
            generator = self._layout_generator_factory(composite)
            zones = self._zoning_strategy.build_zones(level_program)
            layout = generator.generate(level_program, lot, zones)

            result = composite.validate(layout)
            if not result.is_valid:
                raise LayoutGenerationError(
                    f"No se pudo generar un layout valido para la planta '{level.value}'. "
                    f"Ultimas violaciones: {result.violations}"
                )

            building.floors[level] = layout
            previous_layout = layout

        self._check_programa_minimo(building)
        return building

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
