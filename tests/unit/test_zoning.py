from housing_generator.infrastructure.algorithms.zoning.treemap_zoning import TreemapZoningStrategy
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, ZoneType


def test_zoning_groups_rooms_by_zone_type():
    rooms = [
        Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20)),
        Room(id="bed1", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=12)),
        Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=18)),
    ]
    program = Program(rooms=rooms)
    zones = TreemapZoningStrategy().build_zones(program)

    zone_map = {z.zone_type: z.room_ids for z in zones}
    assert zone_map[ZoneType.DAY] == ["living"]
    assert zone_map[ZoneType.NIGHT] == ["bed1"]
    assert zone_map[ZoneType.SERVICE] == ["garage"]
