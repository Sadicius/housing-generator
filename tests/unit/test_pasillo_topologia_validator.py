from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.pasillo_topologia_validator import (
    PasilloTopologiaValidator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon) -> Room:
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    r.boundary = Boundary(polygon=polygon)
    return r


def _validator():
    return PasilloTopologiaValidator(GeometryAdjacencyGraphBuilder())


def test_kitchen_as_mandatory_passthrough_to_laundry_fails():
    # pasillo -> cocina -> lavadero (en linea recta, paredes reales
    # compartidas): para llegar al lavadero hay que atravesar la cocina.
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 0, 2, 4))
    kitchen = _placed("kitchen", RoomType.KITCHEN, box(2, 0, 6, 4))
    laundry = _placed("laundry", RoomType.LAUNDRY, box(6, 0, 8, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[corridor, kitchen, laundry], zones=[])

    violations = _validator().validate(layout).violations
    assert len(violations) == 1
    assert "kitchen" in violations[0] and "laundry" in violations[0]


def test_living_room_as_passthrough_is_exempt():
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 0, 2, 4))
    living = _placed("living", RoomType.LIVING_ROOM, box(2, 0, 6, 4))
    study = _placed("study", RoomType.STUDY, box(6, 0, 8, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[corridor, living, study], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []


def test_both_rooms_directly_connected_to_corridor_passes():
    corridor = _placed("corridor", RoomType.CORRIDOR, box(2, 0, 4, 6))
    kitchen = _placed("kitchen", RoomType.KITCHEN, box(0, 0, 2, 3))
    laundry = _placed("laundry", RoomType.LAUNDRY, box(0, 3, 2, 6))

    layout = Layout(lot=_dummy_lot(), rooms=[corridor, kitchen, laundry], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []


def test_no_circulation_rooms_at_all_does_not_apply():
    kitchen = _placed("kitchen", RoomType.KITCHEN, box(0, 0, 2, 4))
    laundry = _placed("laundry", RoomType.LAUNDRY, box(2, 0, 4, 4))
    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, laundry], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []


def test_staircase_counts_as_circulation_destination():
    stair = _placed("stair", RoomType.STAIRCASE, box(0, 0, 2, 2))
    bed = _placed("bed", RoomType.BEDROOM, box(2, 0, 5, 2))
    layout = Layout(lot=_dummy_lot(), rooms=[stair, bed], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []


def test_disconnected_rooms_produce_no_false_positive():
    # estancias que ni siquiera se tocan geometricamente -- no hay
    # "paso obligado" que detectar, son simplemente inconexas
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 0, 2, 2))
    kitchen = _placed("kitchen", RoomType.KITCHEN, box(10, 10, 12, 12))  # lejos, sin tocar nada
    layout = Layout(lot=_dummy_lot(), rooms=[corridor, kitchen], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []


def test_realistic_cli_style_layout_does_not_produce_false_positives():
    # reproduce la forma general del programa de ejemplo del CLI (varias
    # estancias, solo un pasillo/recibidor, sin declarar practicamente
    # ninguna adyacencia Obligatoria mas que unas pocas) -- confirma que
    # el fallo real encontrado con el grafo de puertas disperso (9 tests
    # rotos) no se repite usando adyacencia geometrica real.
    entrance = _placed("entrance", RoomType.ENTRANCE_HALL, box(4, 4, 6, 6))
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 4, 4, 8))
    dining = _placed("dining", RoomType.DINING_ROOM, box(0, 0, 4, 4))
    kitchen = _placed("kitchen", RoomType.KITCHEN, box(4, 0, 8, 4))
    bed1 = _placed("bed1", RoomType.BEDROOM, box(6, 4, 10, 8))
    bath = _placed("bath", RoomType.BATHROOM, box(8, 0, 10, 4))

    layout = Layout(lot=_dummy_lot(), rooms=[entrance, living, dining, kitchen, bed1, bath], zones=[])

    result = _validator().validate(layout)
    assert result.violations == []
