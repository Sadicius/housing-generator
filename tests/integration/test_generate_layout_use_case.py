from shapely.geometry import box
from housing_generator.config.container import build_generate_layout_use_case
from housing_generator.application.dto.generation_request import GenerationRequest
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.enums import RoomType, AdjacencyStrength


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

    use_case = build_generate_layout_use_case(adjacency_requirements=adjacency, seed=3, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    for room in layout.rooms:
        assert lot.boundary.polygon.buffer(0.05).contains(room.boundary.polygon)


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
    # parcela generosa (22x24) con retranqueo de 3m -> area edificable 16x18,
    # suficiente para el programa ampliado pero deja un margen real perimetral
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 22, 24)), retranqueo_m=3.0)

    use_case = build_generate_layout_use_case(adjacency_requirements=adjacency, seed=3, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.is_complete
    buildable = lot.buildable_area.polygon.buffer(0.05)
    for room in layout.rooms:
        # las estancias deben quedar dentro del AREA EDIFICABLE (parcela
        # menos retranqueo), no solo dentro de la parcela completa --
        # esto es lo que distingue este test del anterior.
        assert buildable.contains(room.boundary.polygon), (
            f"'{room.id}' invade la franja de retranqueo"
        )


def test_soft_constraint_should_be_near_is_actually_satisfied_by_the_search():
    # primer punto retomado de docs/CONTINUIDAD.md: restricciones
    # blandas conectadas de verdad a la funcion objetivo, no solo
    # documentadas. Este test confirma que la busqueda las persigue en
    # la practica: sin ninguna restriccion DURA que fuerce a 'study' y
    # 'living' a estar juntos, la preferencia blanda SHOULD_BE_NEAR
    # deberia bastar para que acaben a distancia <=2 saltos.
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

    use_case = build_generate_layout_use_case(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["hard_violations"] == 0
    assert layout.metadata["soft_penalty"] == 0.0  # la preferencia blanda SI se satisface


def test_hard_constraint_never_loses_to_soft_even_when_tempting():
    # restriccion dura (MUST_BE_AWAY) en tension directa con una
    # preferencia blanda (SHOULD_BE_NEAR) para el MISMO par -- lo duro
    # debe ganar siempre, la preferencia blanda debe quedar sacrificada.
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

    use_case = build_generate_layout_use_case(adjacency_requirements=adjacency, seed=1, max_iterations=3000)
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    # lo duro se cumple SIEMPRE, aunque eso obligue a sacrificar lo blando
    assert layout.metadata["hard_violations"] == 0
    living = next(r for r in layout.rooms if r.id == "living")
    garage = next(r for r in layout.rooms if r.id == "garage")
    assert living.boundary.polygon.distance(garage.boundary.polygon) > 0  # de verdad separadas
