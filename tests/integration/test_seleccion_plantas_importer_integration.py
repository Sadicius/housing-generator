import pytest
from shapely.geometry import box
from housing_generator.infrastructure.persistence.seleccion_plantas_importer import import_seleccion_plantas
from housing_generator.config.container import build_generate_building_use_case
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.exceptions import LayoutGenerationError


def test_complete_selection_generates_a_real_building_end_to_end():
    # retomado de docs/CONTINUIDAD.md, ultimo pendiente real. Confirma
    # que el JSON exportado por el dashboard, tal cual, produce un
    # edificio real y valido con el generador -- no solo una estructura
    # de datos plausible.
    payload = {
        "levels": {
            "PLANTA_BAJA": ["LIVING_ROOM", "KITCHEN", "ENTRANCE_HALL", "LAUNDRY", "DRYING_AREA", "STORAGE"],
            "PLANTA_SUPERIOR": ["BEDROOM", "MASTER_BEDROOM", "BATHROOM", "CORRIDOR"],
        },
    }
    program = import_seleccion_plantas(payload)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=2, max_iterations=4000,
    )
    building = use_case.execute(program, lot)

    assert len(building.floors) == 2
    all_ids = {r.id for layout in building.floors.values() for r in layout.rooms}
    assert "bathroom_planta_superior" in all_ids


def test_incomplete_selection_fails_honestly_not_silently():
    # limitacion real y documentada del formato importado: es una
    # SELECCION DE TIPOS, no un programa validado -- si la seleccion
    # del dashboard no incluye circulacion en una planta con bano, la
    # generacion debe fallar con un mensaje claro, no generar algo
    # incorrecto en silencio.
    payload = {
        "levels": {
            "PLANTA_BAJA": ["LIVING_ROOM", "KITCHEN", "ENTRANCE_HALL", "LAUNDRY", "DRYING_AREA", "STORAGE"],
            "PLANTA_SUPERIOR": ["BEDROOM", "MASTER_BEDROOM", "BATHROOM"],  # sin CORRIDOR
        },
    }
    program = import_seleccion_plantas(payload)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=4000,
    )
    with pytest.raises(LayoutGenerationError, match="acceso directo a circulación general"):
        use_case.execute(program, lot)


def test_v2_format_with_two_bedrooms_and_real_areas_generates_end_to_end():
    # [RESUELTO] las dos limitaciones originales (max 1 estancia por
    # tipo/planta, areas genericas) eliminadas de raiz en el dashboard,
    # no solo documentadas -- confirmado con el generador real, no solo
    # con la estructura de datos: 2 dormitorios reales en la misma
    # planta, con el area exacta que declararia un usuario del dashboard.
    payload = {
        "version": 2,
        "levels": {
            "PLANTA_BAJA": [
                {"type": "LIVING_ROOM", "count": 1, "area_m2": 28},
                {"type": "KITCHEN", "count": 1, "area_m2": 11},
                {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 5},
                {"type": "LAUNDRY", "count": 1, "area_m2": 3},
                {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
                {"type": "STORAGE", "count": 1, "area_m2": 4},
            ],
            "PLANTA_SUPERIOR": [
                {"type": "BEDROOM", "count": 2, "area_m2": 12.5},
                {"type": "BATHROOM", "count": 1, "area_m2": 6},
                {"type": "CORRIDOR", "count": 1, "area_m2": 4},
            ],
        },
    }
    program = import_seleccion_plantas(payload)
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 16, 18)))

    use_case = build_generate_building_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=2, max_iterations=4000,
    )
    building = use_case.execute(program, lot)

    superior_ids = {r.id for r in building.floors[list(building.floors)[1]].rooms}
    assert "bedroom_planta_superior_1" in superior_ids
    assert "bedroom_planta_superior_2" in superior_ids  # 2 dormitorios reales, no 1
