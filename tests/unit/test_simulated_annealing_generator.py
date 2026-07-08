from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.simulated_annealing_generator import (
    SimulatedAnnealingLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.constraints.wet_core_validator import build_wet_core_validator
from housing_generator.infrastructure.algorithms.constraints.adjacency_validator import AdjacencyConstraintValidator
from housing_generator.infrastructure.algorithms.constraints.composite_constraint_validator import (
    CompositeConstraintValidator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength


def _dummy_lot(w=12, h=15) -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, w, h)))


def test_converges_to_zero_violations_when_a_solution_exists():
    # cocina y bano deben compartir pared (nucleo humedo, distancia <=1):
    # geometricamente posible con solo 2 estancias humedas, a diferencia
    # del caso de 3 zonas no contiguas.
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="bed1", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
        Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
    ]
    program = Program(rooms=rooms)
    lot = _dummy_lot()

    graph_builder = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.1)
    validator = CompositeConstraintValidator([
        AdjacencyConstraintValidator(),
        build_wet_core_validator(graph_builder),
    ])

    generator = SimulatedAnnealingLayoutGenerator(
        constraint_validator=validator, max_iterations=1500, seed=42
    )
    layout = generator.generate(program, lot, zones=[])

    result = validator.validate(layout)
    assert result.violations == []
    assert layout.is_complete


def test_does_not_mutate_the_original_program_rooms():
    rooms = [
        Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
    ]
    program = Program(rooms=rooms)
    lot = _dummy_lot()

    validator = CompositeConstraintValidator([AdjacencyConstraintValidator()])
    generator = SimulatedAnnealingLayoutGenerator(constraint_validator=validator, max_iterations=50, seed=1)
    generator.generate(program, lot, zones=[])

    assert all(r.boundary is None for r in program.rooms)


def test_repeated_calls_to_the_same_instance_with_same_seed_give_identical_results():
    # BUG REAL encontrado en auditoria: antes, self._rng se creaba UNA
    # sola vez en __init__ y se reutilizaba entre llamadas -- seed solo
    # garantizaba reproducibilidad en la PRIMERA llamada a generate();
    # una segunda llamada al MISMO generador continuaba la secuencia
    # aleatoria anterior, no reiniciaba desde la semilla (confirmado:
    # rompia incluso la generacion real del CLI en la 3a llamada
    # repetida). Corregido reiniciando self._rng en cada generate().
    rooms = [
        Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="c", name="C", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
    ]
    program = Program(rooms=rooms)
    lot = _dummy_lot()

    validator = CompositeConstraintValidator([AdjacencyConstraintValidator()])
    generator = SimulatedAnnealingLayoutGenerator(constraint_validator=validator, max_iterations=100, seed=2)

    layout1 = generator.generate(program, lot, zones=[])
    layout2 = generator.generate(program, lot, zones=[])  # MISMO objeto generador, 2a llamada
    layout3 = generator.generate(program, lot, zones=[])  # 3a llamada -- donde fallaba antes

    bounds1 = {r.id: r.boundary.polygon.bounds for r in layout1.rooms}
    bounds2 = {r.id: r.boundary.polygon.bounds for r in layout2.rooms}
    bounds3 = {r.id: r.boundary.polygon.bounds for r in layout3.rooms}

    assert bounds1 == bounds2 == bounds3


def test_all_rooms_end_up_placed_within_the_lot():
    rooms = [
        Room(id="a", name="A", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="b", name="B", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="c", name="C", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
    ]
    program = Program(rooms=rooms)
    lot = _dummy_lot()

    validator = CompositeConstraintValidator([AdjacencyConstraintValidator()])
    generator = SimulatedAnnealingLayoutGenerator(constraint_validator=validator, max_iterations=100, seed=2)
    layout = generator.generate(program, lot, zones=[])

    assert layout.is_complete
    for room in layout.rooms:
        assert lot.boundary.polygon.buffer(0.05).contains(room.boundary.polygon)
