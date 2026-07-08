import pytest
from shapely.geometry import box
from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength, NivelPlanta


def _two_floor_program() -> Program:
    rooms = [
        # planta baja
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
             dimensions=Dimensions(area_m2=22), level=NivelPlanta.PLANTA_BAJA),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
             dimensions=Dimensions(area_m2=9), level=NivelPlanta.PLANTA_BAJA),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_BAJA),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY,
             dimensions=Dimensions(area_m2=1.5), level=NivelPlanta.PLANTA_BAJA),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA,
             dimensions=Dimensions(area_m2=1.5), level=NivelPlanta.PLANTA_BAJA),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE,
             dimensions=Dimensions(area_m2=3), level=NivelPlanta.PLANTA_BAJA),
        Room(id="stair_pb", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_BAJA),
        # planta superior -- el bano SOLO existe aqui, no en planta baja.
        # RESUELTO: con el ranking global (GenerateBuildingUseCase
        # precalcula el puesto real de cada estancia en el EDIFICIO
        # completo, no solo en su planta), estas areas realistas ya
        # bastan -- antes de resolver esa limitacion, habia que inflar
        # master a 18m2 y bed2 a 12m2 para satisfacer el ranking local
        # (que las trataba como puesto 1/2 de esta planta, en vez de su
        # puesto real 2/3 en el edificio completo, detras del salon).
        Room(id="master", name="Dorm. principal", room_type=RoomType.MASTER_BEDROOM,
             dimensions=Dimensions(area_m2=14), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="bed2", name="Dormitorio 2", room_type=RoomType.BEDROOM,
             dimensions=Dimensions(area_m2=10), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM,
             dimensions=Dimensions(area_m2=5), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="stair_ps", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_SUPERIOR),
    ]
    adjacency = [
        AdjacencyRequirement("living", "entrance", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("master", "bath", AdjacencyStrength.MUST_BE_NEAR),
    ]
    return Program(rooms=rooms, adjacency_requirements=adjacency)


def test_two_floor_building_generates_successfully():
    program = _two_floor_program()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    assert building.is_complete
    assert set(building.floors.keys()) == {NivelPlanta.PLANTA_BAJA, NivelPlanta.PLANTA_SUPERIOR}


def test_staircase_footprints_are_aligned_between_floors():
    program = _two_floor_program()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    stair_pb = next(r for r in building.floors[NivelPlanta.PLANTA_BAJA].rooms if r.id == "stair_pb")
    stair_ps = next(r for r in building.floors[NivelPlanta.PLANTA_SUPERIOR].rooms if r.id == "stair_ps")

    intersection = stair_pb.boundary.polygon.intersection(stair_ps.boundary.polygon).area
    smaller = min(stair_pb.boundary.polygon.area, stair_ps.boundary.polygon.area)
    assert intersection / smaller >= 0.90


def test_wet_rooms_overlap_vertically_between_floors():
    program = _two_floor_program()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    bath = next(r for r in building.floors[NivelPlanta.PLANTA_SUPERIOR].rooms if r.id == "bath")
    wet_below = [r for r in building.floors[NivelPlanta.PLANTA_BAJA].rooms if r.is_wet]

    overlap = any(bath.boundary.polygon.intersection(w.boundary.polygon).area > 0 for w in wet_below)
    assert overlap


def test_programa_minimo_satisfied_across_floors_even_though_no_single_floor_has_it_alone():
    # el bano SOLO esta en planta superior -- planta baja SOLA no
    # cumpliria el programa minimo, pero el EDIFICIO completo si
    program = _two_floor_program()
    pb_types = {r.room_type for r in program.rooms if r.level == NivelPlanta.PLANTA_BAJA}
    assert RoomType.BATHROOM not in pb_types  # confirma la premisa del test

    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))
    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)  # no debe lanzar LayoutGenerationError

    assert building.is_complete


def test_rooms_without_explicit_level_default_to_planta_baja():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=1)),
    ]
    adjacency = [AdjacencyRequirement("bath", "entrance", AdjacencyStrength.MUST_BE_NEAR)]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    assert set(building.floors.keys()) == {NivelPlanta.PLANTA_BAJA}
    assert building.is_complete


def test_per_floor_generation_failure_raises_with_floor_name():
    # planta imposible: parcela demasiado pequena para el programa --
    # fuerza el camino de fallo real de generacion por planta, no solo
    # el camino feliz (hueco de cobertura real encontrado en auditoria).
    from housing_generator.domain.exceptions import LayoutGenerationError

    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=1)),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 3, 3)))  # imposiblemente pequena

    use_case = build_generate_building_use_case(seed=1, max_iterations=50)

    with pytest.raises(LayoutGenerationError, match="planta_baja"):
        use_case.execute(program, lot)


def test_building_wide_programa_minimo_failure_raises():
    # edificio de 2 plantas al que le falta el tendedero y el
    # almacenamiento en TODO el edificio -- fuerza el camino de fallo
    # del programa minimo a nivel de edificio, no solo el camino feliz.
    from housing_generator.domain.exceptions import LayoutGenerationError

    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
             dimensions=Dimensions(area_m2=25), level=NivelPlanta.PLANTA_BAJA),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
             dimensions=Dimensions(area_m2=8), level=NivelPlanta.PLANTA_BAJA),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY,
             dimensions=Dimensions(area_m2=1.5), level=NivelPlanta.PLANTA_BAJA),
        Room(id="bed", name="Dormitorio", room_type=RoomType.BEDROOM,
             dimensions=Dimensions(area_m2=12), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM,
             dimensions=Dimensions(area_m2=5), level=NivelPlanta.PLANTA_SUPERIOR),
        # falta DRYING_AREA y STORAGE en todo el edificio -- programa minimo incompleto
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 14)))

    use_case = build_generate_building_use_case(seed=1, max_iterations=3000)

    with pytest.raises(LayoutGenerationError, match="programa minimo"):
        use_case.execute(program, lot)
