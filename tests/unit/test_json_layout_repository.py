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


def test_save_without_adjacency_requirements_produces_empty_doors_list(tmp_path):
    # compatibilidad hacia atras: sin requisitos, "doors" existe pero vacio
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 4, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path))

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["doors"] == []


def test_save_with_adjacency_requirements_includes_real_doors(tmp_path):
    from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
    from housing_generator.domain.enums import AdjacencyStrength

    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 4, 5))
    dining = Room(id="dining", name="Comedor", room_type=RoomType.DINING_ROOM, dimensions=Dimensions(area_m2=15))
    dining.boundary = Boundary(polygon=box(4, 0, 8, 5))  # comparte 5m con living

    layout = Layout(lot=_dummy_lot(), rooms=[living, dining], zones=[])
    reqs = [AdjacencyRequirement("living", "dining", AdjacencyStrength.MUST_BE_NEAR)]

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path), adjacency_requirements=reqs)

    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["doors"]) == 1
    pair = {data["doors"][0]["room_a"], data["doors"][0]["room_b"]}
    assert pair == {"living", "dining"}


def test_to_dict_matches_what_save_writes_to_disk(tmp_path):
    # retomado al construir el puente de navegador (interface/browser/
    # bridge.py): to_dict() se extrajo de save() para poder usarse en
    # memoria, sin pasar por disco -- confirma que ambos caminos
    # producen exactamente el mismo resultado, no solo uno de ellos.
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25))
    living.boundary = Boundary(polygon=box(0, 0, 5, 5))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    direct_dict = JsonLayoutRepository.to_dict(layout)

    path = tmp_path / "layout.json"
    JsonLayoutRepository().save(layout, str(path))
    saved_dict = json.loads(path.read_text(encoding="utf-8"))

    assert direct_dict == saved_dict
