from housing_generator.interface.browser.bridge import generar_edificio


def _payload_completo(tipo_vivienda="aislada"):
    return {
        "version": 2,
        "tipo_vivienda": tipo_vivienda,
        "levels": {
            "PLANTA_BAJA": [
                {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
                {"type": "KITCHEN", "count": 1, "area_m2": 10},
                {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
                {"type": "LAUNDRY", "count": 1, "area_m2": 3},
                {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
                {"type": "STORAGE", "count": 1, "area_m2": 3},
            ],
            "PLANTA_SUPERIOR": [
                {"type": "BEDROOM", "count": 2, "area_m2": 12},
                {"type": "BATHROOM", "count": 1, "area_m2": 5.5},
                {"type": "CORRIDOR", "count": 1, "area_m2": 4},
            ],
        },
    }


def test_successful_generation_returns_ok_with_floors():
    result = generar_edificio(_payload_completo(), lot_width_m=14, lot_height_m=16, seed=1, max_iterations=5000)
    assert result["ok"] is True
    assert "planta_baja" in result["floors"]
    assert "planta_superior" in result["floors"]
    assert result["floors"]["planta_baja"]["metadata"]["hard_violations"] == 0


def test_result_shape_matches_what_the_viewer_already_consumes():
    # el visor de plano (renderPlano en el dashboard) ya sabe leer
    # {rooms, doors, metadata} -- confirma que el puente produce
    # EXACTAMENTE esa forma, sin tener que adaptar el JS del visor
    result = generar_edificio(_payload_completo(), lot_width_m=14, lot_height_m=16, seed=1, max_iterations=5000)
    floor = result["floors"]["planta_baja"]
    assert set(floor.keys()) == {"rooms", "doors", "metadata"}
    assert all({"id", "name", "type", "zone", "area_m2", "bounds"} <= set(r.keys()) for r in floor["rooms"])


def test_medianera_from_tipo_vivienda_reaches_the_generated_geometry():
    # mismo hallazgo que en el CLI (hueco #1 de la auditoria de flujo):
    # confirma que tambien aqui tipo_vivienda llega de verdad a la
    # geometria generada, no solo se informa en la respuesta.
    result = generar_edificio(_payload_completo("adosada"), lot_width_m=14, lot_height_m=16, seed=1, max_iterations=5000)
    assert result["ok"] is True
    assert result["medianera_sides"] == ["east", "west"]

    all_bounds = [r["bounds"] for r in result["floors"]["planta_baja"]["rooms"]]
    min_x = min(b[0] for b in all_bounds)
    max_x = max(b[2] for b in all_bounds)
    assert min_x == 0.0   # sin retranqueo en el lado de medianera
    assert max_x == 14.0  # idem


def test_retries_seeds_automatically_and_reports_how_many():
    # mismo escenario ajustado ya usado en los tests del CLI (11x10,
    # semilla 1 falla, semilla 3 converge) -- confirma que el puente
    # reintenta igual que --retry-seeds, e informa la semilla real usada.
    payload = {
        "version": 2, "tipo_vivienda": "aislada",
        "levels": {"PLANTA_BAJA": [
            {"type": "LIVING_ROOM", "count": 1, "area_m2": 25}, {"type": "DINING_ROOM", "count": 1, "area_m2": 14},
            {"type": "KITCHEN", "count": 1, "area_m2": 10}, {"type": "MASTER_BEDROOM", "count": 1, "area_m2": 15},
            {"type": "BATHROOM", "count": 1, "area_m2": 5.5}, {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
            {"type": "LAUNDRY", "count": 1, "area_m2": 3}, {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
            {"type": "STORAGE", "count": 1, "area_m2": 3},
        ]},
    }
    result = generar_edificio(payload, lot_width_m=11, lot_height_m=10, seed=1, max_iterations=5000, retry_seeds=5)
    assert result["ok"] is True
    assert result["semilla_usada"] == 3
    assert result["reintentos"] == 2


def test_fails_gracefully_without_raising_when_retries_exhausted():
    payload = {
        "version": 2, "tipo_vivienda": "aislada",
        "levels": {"PLANTA_BAJA": [
            {"type": "LIVING_ROOM", "count": 1, "area_m2": 25}, {"type": "DINING_ROOM", "count": 1, "area_m2": 14},
            {"type": "KITCHEN", "count": 1, "area_m2": 10}, {"type": "MASTER_BEDROOM", "count": 1, "area_m2": 15},
            {"type": "BATHROOM", "count": 1, "area_m2": 5.5}, {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
            {"type": "LAUNDRY", "count": 1, "area_m2": 3}, {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
            {"type": "STORAGE", "count": 1, "area_m2": 3},
        ]},
    }
    result = generar_edificio(payload, lot_width_m=11, lot_height_m=10, seed=1, max_iterations=5000, retry_seeds=1)
    assert result["ok"] is False
    assert "error" in result
    assert result["semillas_probadas"] == 1


def test_empty_selection_fails_gracefully_not_with_a_crash():
    result = generar_edificio({"levels": {}}, lot_width_m=14, lot_height_m=16)
    assert result["ok"] is False
    assert "estancia" in result["error"]


def test_vivienda_accesible_flag_is_honored():
    from housing_generator.infrastructure.algorithms.constraints.vivienda_accesible_validator import (
        TIPOS_CON_CIRCULO_GIRO, CIRCULO_GIRO_ACCESIBLE_M,
    )
    result = generar_edificio(
        _payload_completo(), lot_width_m=14, lot_height_m=16, seed=1, max_iterations=5000,
        vivienda_accesible=True,
    )
    assert result["ok"] is True
    for floor in result["floors"].values():
        for room in floor["rooms"]:
            if room["type"] in {t.value for t in TIPOS_CON_CIRCULO_GIRO}:
                x0, y0, x1, y1 = room["bounds"]
                assert min(x1 - x0, y1 - y0) >= CIRCULO_GIRO_ACCESIBLE_M - 0.01
