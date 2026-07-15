import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.infrastructure.algorithms.constraints.composite_constraint_validator import (
    CompositeConstraintValidator,
)
from housing_generator.infrastructure.algorithms.constraints.vivienda_minima_validator import (
    ViviendaMinimaValidator,
)
from housing_generator.infrastructure.algorithms.layout_generation.btree_layout_generator import (
    BTreeLayoutGenerator,
)
from housing_generator.config.container import build_per_floor_validators


def _programa_minimo():
    return Program(rooms=[
        Room(id="salon", name="Salon", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="cocina", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=12)),
        Room(id="bano", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=6)),
        Room(id="lavadero", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=6)),
        Room(id="tendedero", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
        Room(id="almacen", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=4)),
    ])


def _validador_real():
    graph_builder = GeometryAdjacencyGraphBuilder(min_shared_edge_m=0.5)
    validators = build_per_floor_validators([], graph_builder) + [ViviendaMinimaValidator()]
    return CompositeConstraintValidator(validators)


def _generar_con_reintento(program, lot, max_seeds=10, max_iterations=1500):
    """Mismo patron de reintento real que usa el CLI -- un generador
    nuevo por semilla (max_attempts en una sola llamada no varia el
    seed entre intentos, confirmado en sesiones anteriores)."""
    composite = _validador_real()
    ultimo_error = None
    for seed in range(1, max_seeds + 1):
        gen = BTreeLayoutGenerator(constraint_validator=composite, max_iterations=max_iterations, seed=seed)
        try:
            return gen.generate(program, lot, zones=[])
        except Exception as e:
            ultimo_error = e
    raise AssertionError(f"ninguna de {max_seeds} semillas convergio -- ultimo error: {ultimo_error}")


def test_btree_generator_places_all_rooms_without_overlap():
    program = _programa_minimo()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))
    layout = _generar_con_reintento(program, lot)

    assert len(layout.rooms) == len(program.rooms)
    rects = [r.boundary.polygon for r in layout.rooms]
    union = unary_union(rects)
    assert union.area == pytest.approx(sum(r.area for r in rects))  # sin solapes


def test_btree_generator_respects_all_hard_constraints():
    program = _programa_minimo()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))
    layout = _generar_con_reintento(program, lot)

    composite = _validador_real()
    violations = composite.validate(layout).violations
    assert violations == [], f"quedaron violaciones sin resolver: {violations}"


def test_btree_generator_computes_void_metadata():
    program = _programa_minimo()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))
    layout = _generar_con_reintento(program, lot)

    assert "vacio_rings" in layout.metadata
    assert len(layout.metadata["vacio_rings"]) > 0  # la parcela es mas grande que las estancias


def test_btree_generator_is_deterministic_given_a_fixed_seed():
    # mismo seed, mismo resultado -- sin esto, nada de lo demas importa.
    program = _programa_minimo()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))
    composite = _validador_real()

    gen1 = BTreeLayoutGenerator(constraint_validator=composite, max_iterations=1500, seed=1)
    gen2 = BTreeLayoutGenerator(constraint_validator=composite, max_iterations=1500, seed=1)
    layout1 = gen1.generate(program, lot, zones=[])
    layout2 = gen2.generate(program, lot, zones=[])

    bounds1 = sorted((r.id, r.boundary.polygon.bounds) for r in layout1.rooms)
    bounds2 = sorted((r.id, r.boundary.polygon.bounds) for r in layout2.rooms)
    assert bounds1 == bounds2
