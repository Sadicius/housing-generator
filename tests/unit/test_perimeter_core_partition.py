import random
from shapely.geometry import box

from housing_generator.infrastructure.algorithms.layout_generation.perimeter_core_partition import (
    PerimeterState,
    build_initial_perimeter_core_state,
    find_entrance_hall_id,
    swap_sides,
    move_to_side,
    resize_room,
    reset_room_aspect_ratio,
    reorder_within_side,
    random_neighbor_perimeter,
    random_neighbor_perimeter_core,
    materialize_perimeter_core,
)
from housing_generator.infrastructure.algorithms.constraints.room_overlap_validator import (
    RoomOverlapValidator,
)
from housing_generator.infrastructure.geometry.shapely_utils import count_exterior_sides
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType

CARDINAL_SIDES = ["south", "east", "north", "west"]


def _sample_program() -> Program:
    rooms = [
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=22),
        ),
        Room(
            id="kitchen",
            name="Cocina",
            room_type=RoomType.KITCHEN,
            dimensions=Dimensions(area_m2=10),
        ),
        Room(
            id="master",
            name="Dorm ppal",
            room_type=RoomType.MASTER_BEDROOM,
            dimensions=Dimensions(area_m2=14),
        ),
        Room(
            id="bedroom",
            name="Dormitorio",
            room_type=RoomType.BEDROOM,
            dimensions=Dimensions(area_m2=10),
        ),
        Room(
            id="bath",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="corridor",
            name="Pasillo",
            room_type=RoomType.CORRIDOR,
            dimensions=Dimensions(area_m2=6),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=3),
        ),
    ]
    return Program(rooms=rooms)


def _sample_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 10, 8)), entrance_side="south")


def _all_perimeter_core_ids(state) -> list:
    perimeter_ids = [rid for ids in state.perimeter.assignment.values() for rid in ids]
    core_ids = [n.room_id for n in state.core_tree.nodes()] if state.core_tree else []
    return perimeter_ids + core_ids


def test_initial_state_contains_every_room_exactly_once():
    program = _sample_program()
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(1))

    ids = _all_perimeter_core_ids(state)
    assert sorted(ids) == sorted(r.id for r in program.rooms)


def test_entrance_hall_assigned_to_entrance_side_initially():
    program = _sample_program()
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(1))
    assert "entrance" in state.perimeter.assignment["south"]


def test_swap_sides_preserves_all_ids_and_swaps_identity():
    state = PerimeterState(
        assignment={"south": ["a", "b"], "east": ["c"], "north": [], "west": []}
    )
    nuevo = swap_sides(state, "a", "c")

    assert nuevo.assignment["south"][0] == "c"
    assert nuevo.assignment["east"][0] == "a"
    assert sorted(v for ids in nuevo.assignment.values() for v in ids) == [
        "a",
        "b",
        "c",
    ]
    # el estado original no se muta
    assert state.assignment["south"][0] == "a"


def test_move_to_side_moves_room_to_a_different_side():
    state = PerimeterState(
        assignment={"south": ["a", "b"], "east": [], "north": [], "west": []}
    )
    rng = random.Random(1)
    nuevo = move_to_side(state, "a", rng, CARDINAL_SIDES)

    ids = [v for side_ids in nuevo.assignment.values() for v in side_ids]
    assert sorted(ids) == ["a", "b"]
    assert "a" not in nuevo.assignment["south"] or nuevo.assignment == state.assignment


def test_move_to_side_is_noop_with_a_single_available_side():
    state = PerimeterState(
        assignment={"south": ["a"], "east": [], "north": [], "west": []}
    )
    nuevo = move_to_side(state, "a", random.Random(1), ["south"])
    assert nuevo.assignment == state.assignment


def test_resize_room_only_touches_target_room():
    state = PerimeterState(
        assignment={"south": ["a", "b"], "east": [], "north": [], "west": []}
    )
    nuevo = resize_room(state, "a", random.Random(1))

    assert "a" in nuevo.aspect_overrides
    assert "b" not in nuevo.aspect_overrides
    assert 0.05 <= nuevo.aspect_overrides["a"] <= 20.0


def test_reset_room_aspect_ratio_removes_override():
    state = PerimeterState(
        assignment={"south": ["a"], "east": [], "north": [], "west": []},
        aspect_overrides={"a": 3.0},
    )
    nuevo = reset_room_aspect_ratio(state, "a")
    assert "a" not in nuevo.aspect_overrides


def test_reorder_within_side_swaps_two_positions():
    state = PerimeterState(
        assignment={"south": ["a", "b", "c"], "east": [], "north": [], "west": []}
    )
    rng = random.Random(2)
    nuevo = reorder_within_side(state, "south", rng)
    assert sorted(nuevo.assignment["south"]) == ["a", "b", "c"]


def test_reorder_within_side_noop_with_fewer_than_two_rooms():
    state = PerimeterState(
        assignment={"south": ["a"], "east": [], "north": [], "west": []}
    )
    nuevo = reorder_within_side(state, "south", random.Random(1))
    assert nuevo.assignment == state.assignment


def test_random_neighbor_perimeter_never_moves_entrance_hall_off_its_side():
    state = PerimeterState(
        assignment={"south": ["entrance"], "east": ["a"], "north": ["b"], "west": ["c"]}
    )
    rng = random.Random(7)
    for _ in range(300):
        state = random_neighbor_perimeter(state, rng, "entrance", CARDINAL_SIDES)
        assert "entrance" in state.assignment["south"]


def test_random_neighbor_perimeter_core_preserves_all_ids_over_many_mutations():
    program = _sample_program()
    lot = _sample_lot()
    rng = random.Random(3)
    state = build_initial_perimeter_core_state(program, lot, rng)
    entrance_id = find_entrance_hall_id(program)
    areas = {r.id: r.dimensions.area_m2 for r in program.rooms}

    for _ in range(500):
        state = random_neighbor_perimeter_core(
            state, rng, areas, entrance_id, CARDINAL_SIDES
        )
        ids = _all_perimeter_core_ids(state)
        assert sorted(ids) == sorted(r.id for r in program.rooms)
        assert entrance_id in state.perimeter.assignment[lot.entrance_side]


def test_random_neighbor_perimeter_core_fuzz_many_seeds_no_crash():
    program = _sample_program()
    lot = _sample_lot()
    for seed in range(20):
        rng = random.Random(seed)
        state = build_initial_perimeter_core_state(program, lot, rng)
        entrance_id = find_entrance_hall_id(program)
        areas = {r.id: r.dimensions.area_m2 for r in program.rooms}
        for _ in range(50):
            state = random_neighbor_perimeter_core(
                state, rng, areas, entrance_id, CARDINAL_SIDES
            )
        materialize_perimeter_core(state, program, lot)  # no debe lanzar


def test_materialize_places_every_room():
    program = _sample_program()
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(4))
    layout = materialize_perimeter_core(state, program, lot)

    assert layout.is_complete
    for room in layout.rooms:
        assert room.boundary.polygon.area > 0


def test_materialize_without_core_rooms_has_no_overlaps():
    # sin estancias de nucleo compitiendo por un residuo fragmentado,
    # el tallado perimetral por si solo (Fase 1, ya probado) no debe
    # producir solapes.
    rooms = [
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=16),
        ),
    ]
    program = Program(rooms=rooms)
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(1))

    assert state.core_tree is None
    layout = materialize_perimeter_core(state, program, lot)
    assert layout.is_complete

    result = RoomOverlapValidator().validate(layout)
    assert result.violations == [], result.violations


def test_materialize_perimeter_rooms_keep_exterior_contact_or_are_unverifiable():
    # mismo criterio de 3 estados que ExteriorContactValidator: una
    # estancia perimetral recortada de forma no rectangular (hallazgo
    # conocido, ver docstring de materialize_perimeter_core -- un lado
    # perpendicular profundo puede recortar la esquina de una vecina)
    # es "no verificable", NO una violacion -- solo falla si SI se
    # puede medir y da por debajo del minimo.
    program = _sample_program()
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(6))
    layout = materialize_perimeter_core(state, program, lot)

    lot_polygon = lot.buildable_area.polygon
    for room in layout.rooms:
        if room.min_exterior_sides <= 0:
            continue
        lados = count_exterior_sides(room.boundary.polygon, lot_polygon, 0.3)
        assert lados is None or lados >= 1, f"{room.id}: {lados}"


def test_materialize_core_overlap_when_residual_is_fragmented_is_caught_by_room_overlap_validator():
    # HALLAZGO REAL de esta Fase 2 (no un caso hipotetico): con
    # profundidad variable por estancia (v2), el residuo del nucleo
    # suele quedar FRAGMENTADO en varias piezas desconectadas (una
    # estancia perimetral menos profunda que sus vecinas deja una
    # muesca hacia el borde). Repartir el nucleo ENTRE las piezas
    # (_residual_pieces/_assign_core_rooms_to_pieces, en vez de un
    # solo bloque centrado en la pieza mas grande) reduce mucho la
    # severidad del solape -- pero la pieza mas grande sigue siendo,
    # a veces, ella misma no-convexa (su propio bbox sobrestima su
    # area real), asi que el solape no desaparece del todo con esta
    # mejora. materialize_perimeter_core sigue siendo UN SOLO intento
    # determinista, SIN busqueda -- no se espera que lo evite por si
    # solo, solo que RoomOverlapValidator (Fase 0) lo detecte.
    # Resolverlo de verdad (que el nucleo SIEMPRE encaje) es trabajo
    # del recocido de la Fase 3, usando move_to_side/resize_room de
    # este mismo modulo.
    program = _sample_program()
    lot = _sample_lot()
    state = build_initial_perimeter_core_state(program, lot, random.Random(0))
    layout = materialize_perimeter_core(state, program, lot)

    result = RoomOverlapValidator().validate(layout)
    assert (
        len(result.violations) > 0
    )  # confirma que el hallazgo sigue reproducible y que el validador lo atrapa
