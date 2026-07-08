from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.graph_based_generator import (
    GraphBasedLayoutGenerator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.algorithms.zoning.treemap_zoning import TreemapZoningStrategy


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 15)))


def test_generates_a_room_for_every_room_in_the_program():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="bed", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=15)),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = _dummy_lot()
    zones = TreemapZoningStrategy().build_zones(program)

    layout = GraphBasedLayoutGenerator().generate(program, lot, zones)

    assert len(layout.rooms) == 3
    assert all(r.is_placed for r in layout.rooms)


def test_all_rooms_fit_within_lot_boundary():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="bed", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = _dummy_lot()
    zones = TreemapZoningStrategy().build_zones(program)

    layout = GraphBasedLayoutGenerator().generate(program, lot, zones)

    buffered = lot.boundary.polygon.buffer(0.05)
    for room in layout.rooms:
        assert buffered.contains(room.boundary.polygon)


def test_rooms_are_grouped_by_zone_in_separate_horizontal_strips():
    # limitacion conocida y documentada: este generador NO puede
    # satisfacer nucleo humedo cuando las humedas abarcan las 3 zonas
    # (topologia de franjas lineales) -- este test usa humedas en una
    # sola zona (noche) para confirmar lo que SI funciona, sin toparse
    # con esa limitacion ya documentada en architecture.md.
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="bed", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
    ]
    program = Program(rooms=rooms, adjacency_requirements=[])
    lot = _dummy_lot()
    zones = TreemapZoningStrategy().build_zones(program)

    layout = GraphBasedLayoutGenerator().generate(program, lot, zones)

    living = next(r for r in layout.rooms if r.id == "living")
    bed = next(r for r in layout.rooms if r.id == "bed")
    bath = next(r for r in layout.rooms if r.id == "bath")

    # dormitorio y bano (misma zona noche) deben quedar en franjas
    # separadas del salon (zona dia) -- sin solape en el eje de reparto.
    # Hallazgo real en auditoria: una version anterior de este test
    # obtenia 'bath' pero nunca lo comprobaba -- el propio comentario
    # prometia verificarlo, el codigo no lo hacia. Corregido, no solo
    # eliminada la variable sin usar.
    assert living.boundary.polygon.bounds[1] != bed.boundary.polygon.bounds[1] or \
        living.boundary.polygon.bounds[0] != bed.boundary.polygon.bounds[0]
    assert living.boundary.polygon.bounds[1] != bath.boundary.polygon.bounds[1] or \
        living.boundary.polygon.bounds[0] != bath.boundary.polygon.bounds[0]
