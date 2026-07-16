from pathlib import Path
import pytest
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
    result = generar_edificio(payload, lot_width_m=12, lot_height_m=10, seed=1, max_iterations=5000, retry_seeds=5)
    assert result["ok"] is True
    assert result["semilla_usada"] == 4
    assert result["reintentos"] == 3


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
    result = generar_edificio(payload, lot_width_m=12, lot_height_m=10, seed=1, max_iterations=5000, retry_seeds=1)
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


def test_retranqueo_is_honored_from_the_dashboard():
    # hallazgo real al revisar las conexiones entre Python y el
    # dashboard: retranqueo_m ya estaba conectado al CLI
    # (--retranqueo) pero no al puente del navegador -- el dashboard
    # no tenia forma de usarlo. Payload simple (programa minimo, una
    # sola planta) a proposito -- lo que este test verifica es que la
    # CONEXION funciona (el parametro llega y se respeta), no que
    # vuelva a demostrarse la geometria del retranqueo en un escenario
    # dificil (eso ya se verifico con el CLI real, [ARCH:cli-retranqueo]).
    payload = {
        "version": 2,
        "levels": {"PLANTA_BAJA": [
            {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
            {"type": "KITCHEN", "count": 1, "area_m2": 12},
            {"type": "BATHROOM", "count": 1, "area_m2": 6},
            {"type": "LAUNDRY", "count": 1, "area_m2": 6},
            {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
            {"type": "STORAGE", "count": 1, "area_m2": 4},
        ]},
    }
    result = generar_edificio(
        payload, lot_width_m=14, lot_height_m=14, seed=1, max_iterations=3000, retry_seeds=10,
        retranqueo_m=2.0,
    )
    assert result["ok"] is True, result.get("error")
    for floor in result["floors"].values():
        for room in floor["rooms"]:
            x0, y0, x1, y1 = room["bounds"]
            assert x0 >= 2.0 - 0.05 and y0 >= 2.0 - 0.05
            assert x1 <= 12.0 + 0.05 and y1 <= 12.0 + 0.05


def test_experimental_btree_flag_reaches_the_dashboard():
    # mismo hallazgo: --experimental-btree ya funcionaba en el CLI
    # (confirmado que resuelve escenarios que el generador por defecto
    # no puede, ver [ARCH:migracion-btree] Fase 5) pero el dashboard
    # no tenia forma de activarlo. Payload simple a proposito, mismo
    # motivo que test_retranqueo_is_honored_from_the_dashboard.
    payload = {
        "version": 2,
        "levels": {"PLANTA_BAJA": [
            {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
            {"type": "KITCHEN", "count": 1, "area_m2": 12},
            {"type": "BATHROOM", "count": 1, "area_m2": 6},
            {"type": "LAUNDRY", "count": 1, "area_m2": 6},
            {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
            {"type": "STORAGE", "count": 1, "area_m2": 4},
        ]},
    }
    result = generar_edificio(
        payload, lot_width_m=14, lot_height_m=14, seed=1, max_iterations=3000, retry_seeds=10,
        experimental_btree=True,
    )
    assert result["ok"] is True, result.get("error")
    for floor in result["floors"].values():
        assert "vacio_shapes" in floor["metadata"]  # formato del arbol B*, no vacio_rings


def test_analizar_parcela_catastro_with_real_gml_from_the_user(tmp_path):
    # datos reales aportados por el usuario, mismo fixture que
    # test_catastro_gml_importer.py. Verifica el puente completo, no
    # solo el parser aislado -- incluida la serializacion a JSON, que
    # es por donde viaja de verdad hacia el dashboard via Pyodide.
    import json
    from housing_generator.interface.browser.bridge import analizar_parcela_catastro

    fixture_path = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    contenido = fixture_path.read_text(encoding="utf-8")

    resultado = analizar_parcela_catastro(contenido)

    assert resultado["ok"] is True
    assert resultado["referencia_catastral"] == "4278011NG2947N"
    assert resultado["area_declarada_m2"] == pytest.approx(349.0)
    assert resultado["area_calculada_m2"] == pytest.approx(349.2, abs=0.5)
    assert resultado["discrepancia_area_pct"] < 1.0
    assert resultado["ancho_m"] > 0 and resultado["fondo_m"] > 0
    assert len(resultado["poligono_real"]) >= 4
    assert len(resultado["rectangulo_trabajo"]) == 5  # 4 esquinas + cierre
    assert resultado["zona_afeccion"] is None  # sin retranqueo pedido, no se calcula

    # serializa a JSON sin problemas -- es como viaja de verdad al dashboard
    json.dumps(resultado)


def test_analizar_parcela_catastro_computes_zona_afeccion_from_real_polygon(tmp_path):
    # la "zona de afeccion" (retranqueo aplicado) usa el POLIGONO REAL,
    # via shapely.buffer(-retranqueo) -- no el rectangulo de trabajo
    # simplificado. Confirma que reduce el area de forma realista, no
    # solo un numero inventado.
    from housing_generator.interface.browser.bridge import analizar_parcela_catastro
    from shapely.geometry import Polygon

    fixture_path = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    contenido = fixture_path.read_text(encoding="utf-8")

    resultado = analizar_parcela_catastro(contenido, retranqueo_m=3.0)
    assert resultado["zona_afeccion"] is not None
    assert len(resultado["zona_afeccion"]) > 0
    poly_afeccion = Polygon(resultado["zona_afeccion"])
    assert poly_afeccion.area < resultado["area_calculada_m2"]  # se reduce de verdad
    assert poly_afeccion.area == pytest.approx(154.0, abs=5.0)  # verificado a mano


def test_analizar_parcela_catastro_handles_excessive_retranqueo_gracefully():
    # retranqueo tan grande que colapsa el poligono -- lista vacia,
    # no una excepcion ni un poligono invalido.
    from housing_generator.interface.browser.bridge import analizar_parcela_catastro

    fixture_path = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    contenido = fixture_path.read_text(encoding="utf-8")

    resultado = analizar_parcela_catastro(contenido, retranqueo_m=15.0)
    assert resultado["ok"] is True
    assert resultado["zona_afeccion"] == []


def test_analizar_parcela_catastro_rejects_invalid_content_gracefully():
    from housing_generator.interface.browser.bridge import analizar_parcela_catastro

    resultado = analizar_parcela_catastro("esto no es un GML valido")
    assert resultado["ok"] is False
    assert "error" in resultado


def test_generar_edificio_with_real_poligono_real_places_all_rooms_inside_it():
    # HALLAZGO REAL Y GRAVE, confirmado por el usuario con captura del
    # navegador: sin pasar poligono_real_coords, el generador SIEMPRE
    # trabajaba sobre el rectangulo de trabajo, nunca sobre la parcela
    # real -- podia colocar estancias fuera del linde legal real.
    # Verificado y corregido en dos capas: (1) ParcelaRealValidator
    # (restriccion dura), (2) el bug de sistemas de coordenadas
    # distintos entre poligono real y rectangulo de trabajo (rotacion
    # hasta 151.9 grados en un caso real) -- encontrado precisamente
    # al escribir ESTE test de extremo a extremo, no en un test
    # aislado. Ver [ARCH:parcela-real].
    import json
    from pathlib import Path
    from shapely.geometry import Polygon, box
    from housing_generator.interface.browser.bridge import analizar_parcela_catastro, generar_edificio

    fixture_path = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    contenido = fixture_path.read_text(encoding="utf-8")
    analisis = analizar_parcela_catastro(contenido, retranqueo_m=3.0)
    assert analisis["ok"] is True

    payload = {
        "version": 2,
        "levels": {"PLANTA_BAJA": [
            {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
            {"type": "KITCHEN", "count": 1, "area_m2": 10},
            {"type": "BATHROOM", "count": 1, "area_m2": 6},
            {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
            {"type": "LAUNDRY", "count": 1, "area_m2": 4},
            {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
            {"type": "STORAGE", "count": 1, "area_m2": 3},
        ]},
    }
    resultado = generar_edificio(
        payload, analisis["ancho_m"], analisis["fondo_m"],
        seed=1, max_iterations=3000, retry_seeds=15,
        retranqueo_m=3.0, coeficiente_edificabilidad=0.4, ocupacion_maxima_pct=45,
        altura_maxima_plantas=2, frente_minimo_m=12, street_side="south",
        poligono_real_coords=analisis["poligono_real"],
    )

    assert resultado["ok"] is True, resultado.get("error")
    poligono_real = Polygon(analisis["poligono_real"])
    poligono_real_con_margen = poligono_real.buffer(0.15)  # tolerancia razonable, no exigir precision perfecta de punto flotante
    for room in resultado["floors"]["planta_baja"]["rooms"]:
        room_poly = box(*room["bounds"])
        assert poligono_real_con_margen.contains(room_poly), (
            f"'{room['name']}' queda fuera del poligono real de la parcela -- "
            f"exactamente el bug real que este test protege"
        )
    json.dumps(resultado)  # confirma que sigue siendo serializable, viaja igual al dashboard
