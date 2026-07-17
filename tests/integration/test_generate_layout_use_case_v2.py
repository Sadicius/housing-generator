"""Criterio de aceptación de la Fase 3 (recocido simulado sobre
`perimeter_core_partition.py`): los mismos 5 escenarios que están
marcados `xfail(strict=False)` en `test_generate_layout_use_case.py`
contra `BTreeLayoutGenerator` (huella de empaquetado mucho menor que
el lote, confirmado estructural -- ver el motivo documentado ahí),
copiados EXACTAMENTE pero apuntando a `build_generate_layout_use_case_v2`
(`PerimeterCoreLayoutGenerator`). Cuando estos tests pasen (sin
`xfail`), será la confirmación real (no solo un smoke-test aislado)
de que el rediseño "periferia hacia el centro" resuelve el problema
de contacto exterior que motivó todo el rediseño. Ver
docs/referencia/generador/contacto-exterior-y-envolvente.md,
[ARCH:perimeter-core-layout-generator].

Estado real (no un smoke-test aislado, confirmado en los 5 escenarios):
todavía fallan, `xfail(strict=False)` -- el smoke-test aislado de esta
Fase 3 SÍ converge (hard=0 en <0.3s), pero en los 5 escenarios reales
el reparto del núcleo en piezas separadas (pedido explícitamente por
el usuario tras la revisión visual anterior -- mejora medida: severidad
de solape de hasta 5.7m² a 0.07-1.8m² por par) tiene un coste no
anticipado: las estancias de núcleo quedan geométricamente
DESCONECTADAS entre sí con mucha frecuencia (cada pieza del residuo es
un fragmento separado, sin garantía de tocarse), lo que rompe en
cascada `NucleoHumedoVerticalValidator`/agrupación de zonas día-noche-
servicio/`PasilloTopologiaValidator` (docenas de "paso obligado")/
`BanoAccesoGeneralValidator` -- presente en los 5 casos, dominante
sobre cualquier otro motivo. Un segundo hallazgo, más puntual (2 de 5
casos): `_solve_room_depth` (perimeter_carving.py) calibra solo por
ÁREA, sin acotar por `max_aspect_ratio` -- en un hueco muy comprimido
puede producir una estancia de 0.80x14.00m (ratio 17.5:1). Pendiente
para una sesión futura: incentivo de proximidad entre piezas de núcleo
(soft, o mutación de "acercar piezas") + acotar la bisección de
profundidad por `max_aspect_ratio`, no solo por área.
"""
import pytest
from shapely.geometry import box
from housing_generator.config.container import build_generate_layout_use_case_v2
from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength

_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO = (
    "El reparto del nucleo entre piezas separadas del residuo (Fase 2, para reducir "
    "la severidad del solape) deja con frecuencia las estancias de nucleo geometricamente "
    "desconectadas entre si -- rompe NucleoHumedoVerticalValidator/agrupacion de zonas/"
    "PasilloTopologiaValidator/BanoAccesoGeneralValidator. El smoke-test aislado de esta "
    "Fase 3 SI converge (hard=0); estos 5 escenarios reales confirman que hace falta un "
    "incentivo de proximidad entre piezas de nucleo (o una mutacion que las acerque) antes "
    "de poder quitar este xfail. Ver docstring del modulo."
)


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO, strict=False)
def test_generate_layout_places_all_rooms_within_lot():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="bed1", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=7)),
        Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=2)),
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=15)),
    ]
    adjacency = [
        AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY),
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 17, 18)))

    use_case = build_generate_layout_use_case_v2(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    for room in layout.rooms:
        assert lot.boundary.polygon.buffer(0.05).contains(room.boundary.polygon)


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO, strict=False)
def test_generate_layout_respects_retranqueo_vivienda_aislada():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="bed1", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=7)),
        Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=2)),
    ]
    adjacency = [AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR)]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 22, 24)), retranqueo_m=3.0)

    use_case = build_generate_layout_use_case_v2(adjacency_requirements=adjacency, seed=3, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    buildable = lot.buildable_area.polygon.buffer(0.05)
    for room in layout.rooms:
        assert buildable.contains(room.boundary.polygon), f"'{room.id}' invade la franja de retranqueo"


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO, strict=False)
def test_soft_constraint_should_be_near_is_actually_satisfied_by_the_search():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=7)),
        Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=2)),
        Room(id="study", name="Despacho", room_type=RoomType.STUDY, dimensions=Dimensions(area_m2=12)),
    ]
    adjacency = [
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("study", "living", AdjacencyStrength.SHOULD_BE_NEAR),
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_layout_use_case_v2(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0
    assert layout.metadata["soft_penalty"] == 0.0


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO, strict=False)
def test_hard_constraint_never_loses_to_soft_even_when_tempting():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=7)),
        Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=2)),
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=15)),
    ]
    adjacency = [
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY),
        AdjacencyRequirement("living", "garage", AdjacencyStrength.SHOULD_BE_NEAR),  # tension directa
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_layout_use_case_v2(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0
    living = next(r for r in layout.rooms if r.id == "living")
    garage = next(r for r in layout.rooms if r.id == "garage")
    assert living.boundary.polygon.distance(garage.boundary.polygon) > 0


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_NUCLEO_FRAGMENTADO, strict=False)
def test_vivienda_adosada_respects_medianera_sides_end_to_end():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=22)),
        Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=9)),
        Room(id="entrance", name="Recibidor", room_type=RoomType.ENTRANCE_HALL, dimensions=Dimensions(area_m2=4)),
        Room(id="bed1", name="Dormitorio", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
        Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=3)),
        Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=2)),
        Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=3)),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 8, 20)), retranqueo_m=3.0,
        medianera_sides=frozenset({"east", "west"}),
    )

    use_case = build_generate_layout_use_case_v2(seed=2, max_iterations=4000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0

    all_bounds = [r.boundary.polygon.bounds for r in layout.rooms]
    min_x = min(b[0] for b in all_bounds)
    max_x = max(b[2] for b in all_bounds)
    min_y = min(b[1] for b in all_bounds)
    max_y = max(b[3] for b in all_bounds)

    assert min_x == pytest.approx(0.0, abs=0.01)
    assert max_x == pytest.approx(8.0, abs=0.01)
    assert min_y >= 3.0 - 0.01
    assert max_y <= 17.0 + 0.01
