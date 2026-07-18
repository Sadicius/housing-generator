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
de solape de hasta 5.7m² a 0.07-1.8m² por par) tenía un coste no
anticipado: las estancias de núcleo quedaban geométricamente
DESCONECTADAS entre sí con mucha frecuencia.

**[RESUELTO, no era suficiente por sí solo]** Incentivo de proximidad
(`PerimeterCoreLayoutGenerator._grouping_proximity_penalty`, gradiente
real por distancia -- árbol generador mínimo sobre el hueco entre
componentes conexos, mismo patrón que `_stair_corner_penalty` de
`btree_layout_generator.py`), generalizado a los 4 grupos que antes
rompían en cascada (piezas de núcleo por `min_exterior_sides==0`,
núcleo húmedo, zona día/noche/servicio -- `GROUPING_PREDICATES`).
Verificado con datos reales: las piezas de núcleo SÍ terminan formando
un único componente conectado en los 5 escenarios (confirmado
inspeccionando el grafo de adyacencia real del estado final, no solo
el smoke-test).

**Hallazgo real, más preciso, tras verificar con el incentivo ya
puesto**: lo que sigue bloqueando los 5 escenarios NO es distancia/
proximidad -- es que `PasilloTopologiaValidator` sigue señalando
docenas de "paso obligado" (puntos de corte/articulación del grafo de
circulación). Confirmado ESTRUCTURAL, no de búsqueda: el mismo
escenario 1 con 5 semillas distintas Y 20000 iteraciones (6-7x el
presupuesto real de estos tests) converge SIEMPRE al mismo número
exacto de violaciones "paso obligado" (25) -- ninguna semilla ni
presupuesto de iteraciones adicional lo reduce ni un poco, la firma
de un óptimo estructural, no de una búsqueda insuficiente. Causa
probable: el tallado perimetral confina el núcleo a UNA sola bolsa del
residuo, que por construcción solo puede tocar 1-2 estancias
perimetrales -- esas quedan como punto de corte inevitable hacia todo
el resto del núcleo, sin que ninguna mutación actual (`move_to_side`/
`swap_sides`/`swap_modules`/`move_module`) cree una segunda vía de
conexión independiente. Un gradiente de distancia no ataca esto: dos
piezas ya en contacto (distancia 0) siguen siendo el único punto de
corte. Pendiente para una sesión futura, con el usuario: una mutación o
incentivo distinto (redundancia de contacto núcleo-perímetro, no
proximidad) -- decisión de arquitectura, no un ajuste más del mismo
tipo. Un segundo hallazgo, más puntual (2 de 5 casos), SIN investigar
todavía: `_solve_room_depth` (perimeter_carving.py) calibra solo por
ÁREA, sin acotar por `max_aspect_ratio` -- en un hueco muy comprimido
puede producir una estancia de 0.80x14.00m (ratio 17.5:1).
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

_MOTIVO_XFAIL_PASO_OBLIGADO = (
    "El incentivo de proximidad entre piezas de nucleo (PerimeterCoreLayoutGenerator."
    "_grouping_proximity_penalty, gradiente real por distancia, generalizado a nucleo/"
    "nucleo humedo/zona dia/zona noche/zona servicio) ya funciona -- las piezas de nucleo "
    "SI terminan conectadas entre si en los 5 escenarios, verificado con el grafo de "
    "adyacencia real del estado final. Lo que sigue bloqueando la convergencia es distinto "
    "y mas amplio: PasilloTopologiaValidator sigue senalando docenas de 'paso obligado' "
    "(puntos de corte del grafo de circulacion). Confirmado ESTRUCTURAL, no de busqueda: "
    "el mismo escenario con 5 semillas y 20000 iteraciones (6-7x el presupuesto real) "
    "converge siempre al mismo numero exacto de violaciones -- ninguna semilla ni "
    "presupuesto adicional lo reduce. Un gradiente de distancia no ataca esto (dos piezas "
    "ya en contacto siguen siendo el unico punto de corte); hace falta una mutacion o "
    "incentivo de REDUNDANCIA de contacto nucleo-perimetro, no de proximidad -- decision "
    "de arquitectura pendiente con el usuario. Ver docstring del modulo."
)


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_PASO_OBLIGADO, strict=False)
def test_generate_layout_places_all_rooms_within_lot():
    rooms = [
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=20),
        ),
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="bed1",
            name="Dorm",
            room_type=RoomType.BEDROOM,
            dimensions=Dimensions(area_m2=12),
        ),
        Room(
            id="kitchen",
            name="Cocina",
            room_type=RoomType.KITCHEN,
            dimensions=Dimensions(area_m2=7),
        ),
        Room(
            id="bathroom",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="laundry",
            name="Lavadero",
            room_type=RoomType.LAUNDRY,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="drying",
            name="Tendedero",
            room_type=RoomType.DRYING_AREA,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=2),
        ),
        Room(
            id="garage",
            name="Garaje",
            room_type=RoomType.GARAGE,
            dimensions=Dimensions(area_m2=15),
        ),
    ]
    adjacency = [
        AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY),
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 17, 18)))

    use_case = build_generate_layout_use_case_v2(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    for room in layout.rooms:
        assert lot.boundary.polygon.buffer(0.05).contains(room.boundary.polygon)


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_PASO_OBLIGADO, strict=False)
def test_generate_layout_respects_retranqueo_vivienda_aislada():
    rooms = [
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=20),
        ),
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="bed1",
            name="Dorm",
            room_type=RoomType.BEDROOM,
            dimensions=Dimensions(area_m2=12),
        ),
        Room(
            id="kitchen",
            name="Cocina",
            room_type=RoomType.KITCHEN,
            dimensions=Dimensions(area_m2=7),
        ),
        Room(
            id="bathroom",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="laundry",
            name="Lavadero",
            room_type=RoomType.LAUNDRY,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="drying",
            name="Tendedero",
            room_type=RoomType.DRYING_AREA,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=2),
        ),
    ]
    adjacency = [
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR)
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 22, 24)), retranqueo_m=3.0)

    use_case = build_generate_layout_use_case_v2(
        adjacency_requirements=adjacency, seed=3, max_iterations=3000
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    buildable = lot.buildable_area.polygon.buffer(0.05)
    for room in layout.rooms:
        assert buildable.contains(
            room.boundary.polygon
        ), f"'{room.id}' invade la franja de retranqueo"


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_PASO_OBLIGADO, strict=False)
def test_soft_constraint_should_be_near_is_actually_satisfied_by_the_search():
    rooms = [
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=20),
        ),
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="kitchen",
            name="Cocina",
            room_type=RoomType.KITCHEN,
            dimensions=Dimensions(area_m2=7),
        ),
        Room(
            id="bathroom",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="laundry",
            name="Lavadero",
            room_type=RoomType.LAUNDRY,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="drying",
            name="Tendedero",
            room_type=RoomType.DRYING_AREA,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=2),
        ),
        Room(
            id="study",
            name="Despacho",
            room_type=RoomType.STUDY,
            dimensions=Dimensions(area_m2=12),
        ),
    ]
    adjacency = [
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("study", "living", AdjacencyStrength.SHOULD_BE_NEAR),
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_layout_use_case_v2(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0
    assert layout.metadata["soft_penalty"] == 0.0


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_PASO_OBLIGADO, strict=False)
def test_hard_constraint_never_loses_to_soft_even_when_tempting():
    rooms = [
        Room(
            id="living",
            name="Estar",
            room_type=RoomType.LIVING_ROOM,
            dimensions=Dimensions(area_m2=25),
        ),
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="kitchen",
            name="Cocina",
            room_type=RoomType.KITCHEN,
            dimensions=Dimensions(area_m2=7),
        ),
        Room(
            id="bathroom",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="laundry",
            name="Lavadero",
            room_type=RoomType.LAUNDRY,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="drying",
            name="Tendedero",
            room_type=RoomType.DRYING_AREA,
            dimensions=Dimensions(area_m2=1.5),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=2),
        ),
        Room(
            id="garage",
            name="Garaje",
            room_type=RoomType.GARAGE,
            dimensions=Dimensions(area_m2=15),
        ),
    ]
    adjacency = [
        AdjacencyRequirement("bathroom", "entrance", AdjacencyStrength.MUST_BE_NEAR),
        AdjacencyRequirement("living", "garage", AdjacencyStrength.MUST_BE_AWAY),
        AdjacencyRequirement(
            "living", "garage", AdjacencyStrength.SHOULD_BE_NEAR
        ),  # tension directa
    ]
    program = Program(rooms=rooms, adjacency_requirements=adjacency)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 16)))

    use_case = build_generate_layout_use_case_v2(
        adjacency_requirements=adjacency, seed=1, max_iterations=3000
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0
    living = next(r for r in layout.rooms if r.id == "living")
    garage = next(r for r in layout.rooms if r.id == "garage")
    assert living.boundary.polygon.distance(garage.boundary.polygon) > 0


@pytest.mark.xfail(reason=_MOTIVO_XFAIL_PASO_OBLIGADO, strict=False)
def test_vivienda_adosada_respects_medianera_sides_end_to_end():
    rooms = [
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
            dimensions=Dimensions(area_m2=9),
        ),
        Room(
            id="entrance",
            name="Recibidor",
            room_type=RoomType.ENTRANCE_HALL,
            dimensions=Dimensions(area_m2=4),
        ),
        Room(
            id="bed1",
            name="Dormitorio",
            room_type=RoomType.BEDROOM,
            dimensions=Dimensions(area_m2=12),
        ),
        Room(
            id="bath",
            name="Bano",
            room_type=RoomType.BATHROOM,
            dimensions=Dimensions(area_m2=5),
        ),
        Room(
            id="laundry",
            name="Lavadero",
            room_type=RoomType.LAUNDRY,
            dimensions=Dimensions(area_m2=3),
        ),
        Room(
            id="drying",
            name="Tendedero",
            room_type=RoomType.DRYING_AREA,
            dimensions=Dimensions(area_m2=2),
        ),
        Room(
            id="storage",
            name="Almacen",
            room_type=RoomType.STORAGE,
            dimensions=Dimensions(area_m2=3),
        ),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 8, 20)),
        retranqueo_m=3.0,
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
