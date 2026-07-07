import json
import pytest
from shapely.geometry import box
from housing_generator.infrastructure.persistence.json_layout_repository import JsonLayoutRepository
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def test_save_writes_valid_json_with_expected_fields(tmp_path):
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 4, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    layout.metadata["violations"] = 0

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path))

    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metadata"]["violations"] == 0
    assert len(data["rooms"]) == 1
    assert data["rooms"][0]["id"] == "living"
    assert data["rooms"][0]["type"] == "living_room"
    assert data["rooms"][0]["zone"] == "day"
    assert data["rooms"][0]["area_m2"] == 20
    assert data["rooms"][0]["bounds"] == [0.0, 0.0, 4.0, 5.0]


def test_save_handles_unplaced_room_bounds_as_none(tmp_path):
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["rooms"][0]["bounds"] is None


def test_save_writes_multiple_rooms_in_order(tmp_path):
    rooms = [
        Room(id="a", name="A", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8)),
        Room(id="b", name="B", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5)),
    ]
    layout = Layout(lot=_dummy_lot(), rooms=rooms, zones=[])

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert [r["id"] for r in data["rooms"]] == ["a", "b"]


def test_load_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        JsonLayoutRepository().load("cualquier_ruta.json")
