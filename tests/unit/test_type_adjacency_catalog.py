from housing_generator.domain.services.type_adjacency_catalog import (
    DEFAULT_TYPE_ADJACENCY,
    CONDICIONAL_PAIRS,
    YA_CUBIERTO_PAIRS,
    get_type_adjacency,
    build_adjacency_requirements,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, AdjacencyStrength


def _room(room_id, room_type, area=10) -> Room:
    return Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=area))


def test_catalog_has_82_real_entries():
    # 120 pares totales - 35 Neutro - 2 Condicional - 1 Ya cubierto = 82
    assert len(DEFAULT_TYPE_ADJACENCY) == 82


def test_condicional_and_ya_cubierto_pairs_are_not_in_the_catalog():
    for pair in CONDICIONAL_PAIRS | YA_CUBIERTO_PAIRS:
        assert pair not in DEFAULT_TYPE_ADJACENCY
        assert (pair[1], pair[0]) not in DEFAULT_TYPE_ADJACENCY


def test_get_type_adjacency_works_regardless_of_argument_order():
    a = get_type_adjacency(RoomType.LIVING_ROOM, RoomType.DINING_ROOM)
    b = get_type_adjacency(RoomType.DINING_ROOM, RoomType.LIVING_ROOM)
    assert a == b == AdjacencyStrength.MUST_BE_NEAR


def test_known_hard_pairs_map_correctly():
    assert get_type_adjacency(RoomType.LIVING_ROOM, RoomType.DINING_ROOM) == AdjacencyStrength.MUST_BE_NEAR
    assert get_type_adjacency(RoomType.DINING_ROOM, RoomType.KITCHEN) == AdjacencyStrength.MUST_BE_NEAR
    assert get_type_adjacency(RoomType.LIVING_ROOM, RoomType.ENTRANCE_HALL) == AdjacencyStrength.MUST_BE_NEAR
    assert get_type_adjacency(RoomType.LAUNDRY, RoomType.DRYING_AREA) == AdjacencyStrength.MUST_BE_NEAR
    assert get_type_adjacency(RoomType.LIVING_ROOM, RoomType.GARAGE) == AdjacencyStrength.MUST_BE_AWAY


def test_generate_requirements_for_a_realistic_program():
    rooms = [
        _room("living", RoomType.LIVING_ROOM),
        _room("dining", RoomType.DINING_ROOM),
        _room("kitchen", RoomType.KITCHEN),
        _room("entrance", RoomType.ENTRANCE_HALL),
        _room("garage", RoomType.GARAGE),
    ]
    reqs = build_adjacency_requirements(rooms)
    pairs_generated = {frozenset((r.room_a_id, r.room_b_id)) for r in reqs}

    assert frozenset(("living", "dining")) in pairs_generated
    assert frozenset(("dining", "kitchen")) in pairs_generated
    assert frozenset(("living", "entrance")) in pairs_generated
    assert frozenset(("living", "garage")) in pairs_generated

    living_garage = next(r for r in reqs if {r.room_a_id, r.room_b_id} == {"living", "garage"})
    assert living_garage.strength == AdjacencyStrength.MUST_BE_AWAY


def test_generate_requirements_skips_condicional_pairs():
    rooms = [_room("bed", RoomType.BEDROOM), _room("bath", RoomType.BATHROOM)]
    reqs = build_adjacency_requirements(rooms)
    assert reqs == []  # BEDROOM-BATHROOM es Condicional, no genera nada aqui


def test_generate_requirements_skips_ya_cubierto_pairs():
    rooms = [_room("kitchen", RoomType.KITCHEN), _room("bath", RoomType.BATHROOM)]
    reqs = build_adjacency_requirements(rooms)
    assert reqs == []  # KITCHEN-BATHROOM ya cubierto por nucleo humedo


def test_generate_requirements_ignores_same_type_pairs():
    rooms = [_room("bed1", RoomType.BEDROOM), _room("bed2", RoomType.BEDROOM)]
    reqs = build_adjacency_requirements(rooms)
    assert reqs == []  # el catalogo no tiene entradas tipo-tipo consigo mismo


def test_generate_requirements_applies_same_relation_to_multiple_instances_of_a_type():
    # dos dormitorios distintos, ambos deben recibir la misma relacion
    # hacia GARAGE (el catalogo es por TIPO, no por instancia unica)
    rooms = [
        _room("bed1", RoomType.BEDROOM),
        _room("bed2", RoomType.BEDROOM),
        _room("garage", RoomType.GARAGE),
    ]
    reqs = build_adjacency_requirements(rooms)
    garage_reqs = [r for r in reqs if "garage" in (r.room_a_id, r.room_b_id)]
    assert len(garage_reqs) == 2
    assert all(r.strength == AdjacencyStrength.SHOULD_BE_AWAY for r in garage_reqs)


def test_generate_requirements_consistent_with_get_type_adjacency():
    rooms = [_room("garage", RoomType.GARAGE), _room("technical", RoomType.TECHNICAL_ROOM)]
    strength = get_type_adjacency(RoomType.GARAGE, RoomType.TECHNICAL_ROOM)
    reqs = build_adjacency_requirements(rooms)
    if strength is None:
        assert reqs == []
    else:
        assert len(reqs) == 1 and reqs[0].strength == strength


def test_build_program_with_auto_adjacency_produces_a_valid_program():
    from housing_generator.domain.services.type_adjacency_catalog import build_program_with_auto_adjacency

    rooms = [
        _room("living", RoomType.LIVING_ROOM),
        _room("dining", RoomType.DINING_ROOM),
        _room("garage", RoomType.GARAGE),
    ]
    program = build_program_with_auto_adjacency(rooms)

    assert program.rooms == rooms
    assert len(program.adjacency_requirements) == len(build_adjacency_requirements(rooms))
    # el Program resultante debe pasar su propia validacion interna
    # (todo AdjacencyRequirement referencia estancias que existen)
    pairs = {frozenset((r.room_a_id, r.room_b_id)) for r in program.adjacency_requirements}
    assert frozenset(("living", "dining")) in pairs
    assert frozenset(("living", "garage")) in pairs
