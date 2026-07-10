import json
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import (
    import_seleccion_plantas,
    AREAS_POR_DEFECTO_M2,
)
from housing_generator.domain.enums import RoomType, NivelPlanta


def _sample_payload():
    # mismo formato exacto que exportSectionSelection() en el dashboard:
    # claves de nivel y tipo son los NOMBRES del enum en mayusculas, no
    # los valores en minuscula.
    return {
        "levels": {
            "PLANTA_BAJA": ["LIVING_ROOM", "KITCHEN", "ENTRANCE_HALL", "LAUNDRY", "DRYING_AREA", "STORAGE"],
            "PLANTA_SUPERIOR": ["BEDROOM", "MASTER_BEDROOM", "BATHROOM"],
        },
        "nota": "texto de aviso del dashboard, se ignora al importar",
    }


def test_creates_one_room_per_type_and_level():
    program = import_seleccion_plantas(_sample_payload())
    assert len(program.rooms) == 9  # 6 en planta baja + 3 en planta superior


def test_rooms_have_the_correct_type_and_level():
    program = import_seleccion_plantas(_sample_payload())
    living = next(r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM)
    bed = next(r for r in program.rooms if r.room_type == RoomType.MASTER_BEDROOM)

    assert living.level == NivelPlanta.PLANTA_BAJA
    assert bed.level == NivelPlanta.PLANTA_SUPERIOR


def test_default_areas_are_applied():
    program = import_seleccion_plantas(_sample_payload())
    living = next(r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM)
    assert living.dimensions.area_m2 == AREAS_POR_DEFECTO_M2[RoomType.LIVING_ROOM]


def test_custom_areas_override_defaults():
    program = import_seleccion_plantas(_sample_payload(), areas_m2={RoomType.LIVING_ROOM: 30.0})
    living = next(r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM)
    bath = next(r for r in program.rooms if r.room_type == RoomType.BATHROOM)

    assert living.dimensions.area_m2 == 30.0  # sobreescrita
    assert bath.dimensions.area_m2 == AREAS_POR_DEFECTO_M2[RoomType.BATHROOM]  # sin tocar, sigue el default


def test_adjacency_requirements_are_derived_automatically():
    program = import_seleccion_plantas(_sample_payload())
    # LIVING_ROOM-ENTRANCE_HALL es Obligatorio cerca en el catalogo
    living = next(r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM)
    entrance = next(r for r in program.rooms if r.room_type == RoomType.ENTRANCE_HALL)
    pairs = {frozenset((r.room_a_id, r.room_b_id)) for r in program.adjacency_requirements}
    assert frozenset((living.id, entrance.id)) in pairs


def test_can_load_from_file_path(tmp_path):
    path = tmp_path / "seleccion_plantas.json"
    path.write_text(json.dumps(_sample_payload()), encoding="utf-8")

    program = import_seleccion_plantas(str(path))
    assert len(program.rooms) == 9


def test_empty_levels_produces_empty_program():
    program = import_seleccion_plantas({"levels": {}})
    assert program.rooms == []
    assert program.adjacency_requirements == []
