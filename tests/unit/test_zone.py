from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.enums import ZoneType


def test_add_room_appends_a_new_id():
    zone = Zone(zone_type=ZoneType.DAY)
    zone.add_room("living")
    assert zone.room_ids == ["living"]


def test_add_room_does_not_duplicate_an_existing_id():
    zone = Zone(zone_type=ZoneType.DAY, room_ids=["living"])
    zone.add_room("living")
    assert zone.room_ids == ["living"]


def test_add_room_preserves_insertion_order():
    zone = Zone(zone_type=ZoneType.NIGHT)
    zone.add_room("bed1")
    zone.add_room("bed2")
    assert zone.room_ids == ["bed1", "bed2"]
