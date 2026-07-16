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


def test_three_floor_building_chains_staircase_alignment_at_both_junctions():
    # caso limite encontrado en auditoria posterior a multi-planta:
    # sotano + planta_baja + planta_superior, comprobando que la
    # escalera se alinea correctamente en las DOS uniones consecutivas,
    # no solo en una (riesgo real de que la segunda union se relajara
    # por error al encadenar referencias).
    rooms = [
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE,
             dimensions=Dimensions(area_m2=15), level=NivelPlanta.SOTANO),
        Room(id="stair_s", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.SOTANO),
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
             dimensions=Dimensions(area_m2=22), level=NivelPlanta.PLANTA_BAJA),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
             dimensions=Dimensions(area_m2=8), level=NivelPlanta.PLANTA_BAJA),
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
        Room(id="bed", name="Dormitorio", room_type=RoomType.BEDROOM,
             dimensions=Dimensions(area_m2=12), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM,
             dimensions=Dimensions(area_m2=5), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="stair_ps", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_SUPERIOR),
    ]
    adjacency = [AdjacencyRequirement("living", "entrance", AdjacencyStrength.MUST_BE_NEAR)]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    assert set(building.floors.keys()) == {
        NivelPlanta.SOTANO, NivelPlanta.PLANTA_BAJA, NivelPlanta.PLANTA_SUPERIOR
    }

    def overlap_ratio(a, b):
        inter = a.boundary.polygon.intersection(b.boundary.polygon).area
        return inter / min(a.boundary.polygon.area, b.boundary.polygon.area)

    s_s = next(r for r in building.floors[NivelPlanta.SOTANO].rooms if r.id == "stair_s")
    s_pb = next(r for r in building.floors[NivelPlanta.PLANTA_BAJA].rooms if r.id == "stair_pb")
    s_ps = next(r for r in building.floors[NivelPlanta.PLANTA_SUPERIOR].rooms if r.id == "stair_ps")

    assert overlap_ratio(s_s, s_pb) >= 0.90
    assert overlap_ratio(s_pb, s_ps) >= 0.90


def test_building_with_level_gap_skips_absent_intermediate_levels():
    # caso limite encontrado en auditoria: SOTANO + PLANTA_SUPERIOR,
    # sin PLANTA_BAJA ni SEMISOTANO -- la escalera debe alinearse
    # contra SOTANO (el nivel presente inmediatamente inferior), no
    # fallar ni tratarlo como si no hubiera planta inferior.
    rooms = [
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE,
             dimensions=Dimensions(area_m2=15), level=NivelPlanta.SOTANO),
        Room(id="storage_r", name="Trastero", room_type=RoomType.STORAGE_ROOM,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.SOTANO),
        Room(id="stair_s", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.SOTANO),
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
             dimensions=Dimensions(area_m2=25), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN,
             dimensions=Dimensions(area_m2=8), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM,
             dimensions=Dimensions(area_m2=5), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY,
             dimensions=Dimensions(area_m2=1.5), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA,
             dimensions=Dimensions(area_m2=1.5), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE,
             dimensions=Dimensions(area_m2=2), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="corridor", name="Pasillo", room_type=RoomType.CORRIDOR,
             dimensions=Dimensions(area_m2=3), level=NivelPlanta.PLANTA_SUPERIOR),
        Room(id="stair_ps", name="Escalera", room_type=RoomType.STAIRCASE,
             dimensions=Dimensions(area_m2=4), level=NivelPlanta.PLANTA_SUPERIOR),
    ]
    adjacency = [AdjacencyRequirement("bath", "corridor", AdjacencyStrength.MUST_BE_NEAR)]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    assert set(building.floors.keys()) == {NivelPlanta.SOTANO, NivelPlanta.PLANTA_SUPERIOR}
    assert building.level_below(NivelPlanta.PLANTA_SUPERIOR) == NivelPlanta.SOTANO


def test_progressive_footprint_shrinking_between_floors():
    # retomado de docs/CONTINUIDAD.md ("reducir el contorno edificable
    # planta a planta"). Investigacion externa confirmada antes de
    # implementar (Devans, "Procedural Generation For Dummies: Building
    # Footprints"): tecnica estandar de generacion procedural, "empezar
    # por la parcela y recortar trozos" -- confirma que la planta
    # superior queda geometricamente contenida en la huella de la
    # planta inferior, no solo que "cabe" por casualidad.
    from shapely.ops import unary_union

    program = _two_floor_program()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 18, 18)), retranqueo_incremento_por_planta_m=1.5)

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)

    huella_pb = unary_union([r.boundary.polygon for r in building.floors[NivelPlanta.PLANTA_BAJA].rooms])
    huella_ps = unary_union([r.boundary.polygon for r in building.floors[NivelPlanta.PLANTA_SUPERIOR].rooms])

    assert huella_pb.bounds == (0.0, 0.0, 18.0, 18.0)
    assert huella_ps.bounds == (1.5, 1.5, 16.5, 16.5)  # exactamente 1.5m hacia dentro en los 4 lados
    assert huella_pb.buffer(0.1).contains(huella_ps)  # subconjunto real, no solo coincidencia


def test_excessive_shrink_increment_falls_back_to_same_footprint_as_below():
    # red de seguridad (patron MinArea{Action:Shrink, Fallback:...} de
    # la misma investigacion): un incremento que dejaria un area
    # inviable para las estancias de esa planta NO debe hacer fallar la
    # generacion -- debe usar la misma huella que la planta de abajo
    # (la otra opcion valida: "copia exacta O subconjunto", nunca una
    # huella invalida).
    from shapely.ops import unary_union

    program = _two_floor_program()
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)), retranqueo_incremento_por_planta_m=8.0)

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000,
    )
    building = use_case.execute(program, lot)  # NO debe lanzar LayoutGenerationError

    huella_pb = unary_union([r.boundary.polygon for r in building.floors[NivelPlanta.PLANTA_BAJA].rooms])
    huella_ps = unary_union([r.boundary.polygon for r in building.floors[NivelPlanta.PLANTA_SUPERIOR].rooms])
    assert huella_pb.bounds == huella_ps.bounds == (0.0, 0.0, 16.0, 16.0)


def test_generation_with_real_imported_polygon_never_places_rooms_outside_it():
    # HALLAZGO REAL, confirmado con captura del navegador del usuario:
    # antes de esto, el generador SIEMPRE trabajaba sobre el rectangulo
    # de trabajo (OBB), nunca sobre el poligono real importado -- una
    # vivienda generada podia colocar estancias en las esquinas donde
    # el rectangulo sobresale del poligono real (hasta 49m2 en un caso
    # real, confirmado en la investigacion). Verificado aqui de
    # extremo a extremo, con la misma parcela real usada en el resto
    # de la Fase A, no datos sinteticos. Ver [ARCH:parcela-real].
    from pathlib import Path
    from housing_generator.infrastructure.persistence.catastro_gml_importer import importar_parcela_gml

    fixture = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    resultado = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    poligono_real = resultado.poligono
    minx, miny, maxx, maxy = poligono_real.bounds

    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=10)),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4.5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=3)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=3)),
    ]
    program = Program(rooms=rooms)
    lot = Lot(boundary=Boundary(polygon=box(minx, miny, maxx, maxy)), poligono_real=poligono_real, retranqueo_m=1.0)

    building = None
    for seed in range(1, 11):
        use_case = build_generate_building_use_case(seed=seed, max_iterations=3000)
        try:
            building = use_case.execute(program, lot)
            break
        except Exception:
            continue

    assert building is not None, "ninguna de 10 semillas convergio"
    poligono_real_con_tolerancia = poligono_real.buffer(0.06)  # margen minimo, mismo que usa el validador
    planta = list(building.floors.values())[0]
    for room in planta.rooms:
        if room.is_placed:
            assert poligono_real_con_tolerancia.contains(room.boundary.polygon), (
                f"'{room.id}' quedo fuera del poligono real de la parcela -- "
                f"esto es exactamente el bug real que este test protege"
            )
