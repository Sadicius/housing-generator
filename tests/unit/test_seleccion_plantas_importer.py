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


def _sample_payload_v2():
    # formato nuevo real, tal como lo exporta el dashboard extendido:
    # cada entrada trae su propia cantidad y area, no solo el tipo.
    return {
        "version": 2,
        "levels": {
            "PLANTA_BAJA": [
                {"type": "LIVING_ROOM", "count": 1, "area_m2": 28},
                {"type": "KITCHEN", "count": 1, "area_m2": 11},
            ],
            "PLANTA_SUPERIOR": [
                {"type": "BEDROOM", "count": 2, "area_m2": 11},
                {"type": "BATHROOM", "count": 1, "area_m2": 5.5},
            ],
        },
    }


def test_v2_format_creates_multiple_rooms_for_count_greater_than_one():
    # limitacion real ELIMINADA (no solo documentada): el formato
    # antiguo nunca podia declarar dos dormitorios en la misma planta.
    program = import_seleccion_plantas(_sample_payload_v2())
    bedrooms = [r for r in program.rooms if r.room_type == RoomType.BEDROOM]
    assert len(bedrooms) == 2
    assert bedrooms[0].id != bedrooms[1].id  # ids distintos, no colision


def test_v2_format_uses_the_real_declared_area_not_the_generic_default():
    # segunda limitacion real ELIMINADA: el area declarada por el
    # usuario en el dashboard se usa tal cual, no el valor generico de
    # AREAS_POR_DEFECTO_M2 (que para LIVING_ROOM es 25.0, no 28).
    program = import_seleccion_plantas(_sample_payload_v2())
    living = next(r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM)
    assert living.dimensions.area_m2 == 28  # el valor declarado, no el generico (25)


def test_v2_format_all_rooms_of_same_type_share_the_declared_area():
    program = import_seleccion_plantas(_sample_payload_v2())
    bedrooms = [r for r in program.rooms if r.room_type == RoomType.BEDROOM]
    assert all(r.dimensions.area_m2 == 11 for r in bedrooms)


def test_v2_format_missing_area_falls_back_to_generic_default():
    # robustez: si una entrada del formato nuevo no trae area_m2 (dato
    # incompleto), no debe fallar -- cae al mismo respaldo generico que
    # el formato antiguo.
    payload = {"levels": {"PLANTA_BAJA": [{"type": "STUDY", "count": 1}]}}
    program = import_seleccion_plantas(payload)
    study = program.rooms[0]
    assert study.dimensions.area_m2 == AREAS_POR_DEFECTO_M2[RoomType.STUDY]


def test_old_and_new_format_can_coexist_in_the_same_payload():
    # robustez adicional: un archivo con algunas entradas en formato
    # antiguo (string) y otras en nuevo (dict) no debe fallar -- por si
    # alguien edita un JSON exportado antes a mano.
    payload = {"levels": {"PLANTA_BAJA": ["LIVING_ROOM", {"type": "KITCHEN", "count": 2, "area_m2": 9}]}}
    program = import_seleccion_plantas(payload)
    assert len([r for r in program.rooms if r.room_type == RoomType.LIVING_ROOM]) == 1
    assert len([r for r in program.rooms if r.room_type == RoomType.KITCHEN]) == 2
