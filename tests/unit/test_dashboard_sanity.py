"""Comprobaciones de sanidad sobre el CSS del dashboard, ejecutables
con pytest normal (sin necesitar Node/navegador) -- cierran huecos
reales encontrados durante la sesion que nunca se convirtieron en
test permanente, aplicando la propia convencion del proyecto (ver
docs/CONTINUIDAD.md, "ninguna verificacion exploratoria cuenta como
comprobado").
"""
import json
import re
from pathlib import Path

DASHBOARD_PATH = Path(__file__).parents[2] / "docs" / "visualizador" / "relaciones_espaciales.html"


def _read_dashboard() -> str:
    return DASHBOARD_PATH.read_text(encoding="utf-8")


def test_room_and_door_stroke_width_is_in_meters_not_pixels():
    # BUG REAL encontrado con una captura de pantalla real del usuario:
    # el viewBox del SVG del plano esta en METROS (coordenadas reales de
    # la vivienda), pero .room-rect/.door-mark tenian stroke-width:2/5
    # -- pensados como pixeles razonables, se interpretaban como 2 y 5
    # METROS de grosor de linea, mas grueso que estancias enteras.
    # Verificado cuantitativamente en su momento (73% de la imagen era
    # color de borde con el bug, 2% corregido) pero nunca convertido en
    # test permanente -- se cierra ese hueco aqui. Umbral: ninguna
    # estancia real del proyecto mide menos de ~0.4m de lado, asi que
    # cualquier stroke-width por encima de 0.5m es sospechoso de estar
    # pensado en pixeles, no en metros.
    html = _read_dashboard()

    room_rect_match = re.search(r"\.room-rect\{[^}]*stroke-width:\s*([\d.]+)", html)
    door_mark_match = re.search(r"\.door-mark\{[^}]*stroke-width:\s*([\d.]+)", html)

    assert room_rect_match, "no se encontro la regla .room-rect en el CSS"
    assert door_mark_match, "no se encontro la regla .door-mark en el CSS"

    room_rect_width = float(room_rect_match.group(1))
    door_mark_width = float(door_mark_match.group(1))

    assert room_rect_width < 0.5, (
        f".room-rect stroke-width={room_rect_width} parece pensado en pixeles, "
        f"no en metros (el viewBox del plano esta en metros)"
    )
    assert door_mark_width < 0.5, (
        f".door-mark stroke-width={door_mark_width} parece pensado en pixeles, "
        f"no en metros (el viewBox del plano esta en metros)"
    )


def test_dashboard_has_five_tabs_matching_the_panels():
    # confirma que el numero de pestanas declaradas coincide con el
    # numero de paneles reales -- una discrepancia aqui significa una
    # pestana sin panel (rota) o un panel sin pestana (inaccesible).
    html = _read_dashboard()
    tabs = re.findall(r'<button class="tab[^"]*" data-tab="(\w+)">', html)
    panels = re.findall(r'<div class="panel[^"]*" id="panel-(\w+)"', html)

    assert len(tabs) == 5
    assert set(tabs) == set(panels)


def test_garage_min_exterior_matches_python_default():
    # otro hallazgo real de auditoria anterior (GARAGE.min_exterior
    # desactualizado en el dashboard tras corregirse en Python) --
    # cerrado con un test permanente para que no se repita en silencio.
    from housing_generator.domain.enums import DEFAULT_MIN_EXTERIOR_SIDES, RoomType

    html = _read_dashboard()
    match = re.search(r'"GARAGE":\s*\{[^}]*"min_exterior":\s*(\d+)', html)
    assert match, "no se encontro la entrada de GARAGE en PROPS"

    dashboard_value = int(match.group(1))
    python_value = DEFAULT_MIN_EXTERIOR_SIDES[RoomType.GARAGE]
    assert dashboard_value == python_value, (
        f"PROPS.GARAGE.min_exterior ({dashboard_value}) no coincide con "
        f"DEFAULT_MIN_EXTERIOR_SIDES[GARAGE] en Python ({python_value})"
    )


def test_redesign_uses_the_new_typefaces_not_the_old_ones():
    # rediseño completo (paleta cianotipo + Space Grotesk/Archivo/Space
    # Mono), a peticion del usuario ("no tiene alma o personalidad") --
    # confirma que no quedo ninguna referencia a las fuentes anteriores
    # (IBM Plex) mezclada por error con las nuevas.
    html = _read_dashboard()
    assert "IBM Plex" not in html.replace("sustituye IBM Plex", "")  # exceptua el propio comentario que lo explica
    assert "Space Grotesk" in html
    assert "Archivo" in html
    assert "Space Mono" in html


def test_redesign_css_variable_names_preserved_for_javascript():
    # el rediseño cambio los VALORES hexadecimales de la paleta, pero
    # los NOMBRES de las variables CSS deben seguir siendo exactamente
    # los que el JS referencia (COLORVAR, CAT_COLOR, generacion de SVG
    # del plano) -- si un nombre cambia sin actualizar el JS, los
    # colores se romperian en silencio (var() no definida = color por
    # defecto del navegador, sin error visible).
    html = _read_dashboard()
    required_var_names = [
        "--bg:", "--bg-panel:", "--bg-panel-2:", "--line:", "--line-soft:",
        "--ink:", "--ink-dim:", "--ink-faint:", "--cyan:", "--cyan-dim:",
        "--oc:", "--ol:", "--cat-estancia:", "--pc:", "--pa:", "--n:", "--cond:",
        "--zone-day:", "--zone-night:", "--zone-service:", "--zone-circulation:",
        "--ok:", "--warn:", "--bad:",
    ]
    for name in required_var_names:
        assert name in html, f"variable CSS {name} no encontrada -- el JS podria depender de ella"


def test_pyodide_bundle_contains_the_bridge_and_key_modules():
    # generador real en el navegador (Pyodide) -- confirma que el
    # bundle Python embebido incluye el puente (bridge.py) y los
    # modulos clave que necesita para funcionar, sin tener que cargar
    # el navegador real para saberlo.
    html = _read_dashboard()
    assert "const PY_BUNDLE = {" in html
    for expected_path in [
        "housing_generator/interface/browser/bridge.py",
        "housing_generator/config/container.py",
        "housing_generator/infrastructure/persistence/seleccion_plantas_importer.py",
        "housing_generator/infrastructure/persistence/json_layout_repository.py",
    ]:
        assert expected_path in html, f"{expected_path} no encontrado en PY_BUNDLE"


def test_pyodide_cdn_script_tag_present_with_a_pinned_version():
    # version fija (no 'latest'/'dev'), confirmado con la documentacion
    # oficial de Pyodide en el momento de construir esto -- una URL sin
    # version fija podria cambiar de comportamiento sin aviso.
    html = _read_dashboard()
    match = re.search(r'<script src="https://cdn\.jsdelivr\.net/pyodide/(v[\d.]+)/full/pyodide\.js"></script>', html)
    assert match, "no se encontro el script de Pyodide con una version fija (vX.Y.Z)"


def test_generate_now_button_and_status_area_exist():
    html = _read_dashboard()
    assert 'id="generate-now"' in html
    assert 'id="generate-status"' in html
    assert 'id="generate-config"' in html


def test_mirror_mode_controls_exist():
    html = _read_dashboard()
    for control_id in ["mirror-h", "mirror-v", "mirror-rotate", "mirror-reset"]:
        assert f'id="{control_id}"' in html


def test_pyodide_bundle_is_not_stale_against_the_real_source():
    # riesgo real de mantenimiento: si alguien edita un .py del
    # generador despues de esto sin regenerar el bundle embebido, el
    # navegador seguiria ejecutando el codigo VIEJO en silencio, sin
    # ningun error -- este test compara el contenido REAL de bridge.py
    # (el mas probable de tocarse) contra lo que hay embebido en el
    # dashboard, byte a byte.
    import re as re_module
    from pathlib import Path

    html = _read_dashboard()
    src_root = Path(__file__).parents[2] / "src"
    bridge_path = src_root / "housing_generator" / "interface" / "browser" / "bridge.py"
    real_content = bridge_path.read_text(encoding="utf-8")

    # extraer PY_BUNDLE como JSON real (no regex parcial) para comparar
    # el valor exacto de esa clave, no solo si la ruta aparece en el HTML
    match = re_module.search(r"const PY_BUNDLE = (\{.*?\});\nlet PYODIDE_INSTANCE", html, re_module.DOTALL)
    assert match, "no se pudo extraer PY_BUNDLE del HTML"
    bundle = json.loads(match.group(1))

    bundled_content = bundle.get("housing_generator/interface/browser/bridge.py")
    assert bundled_content is not None, "bridge.py no esta en el bundle"
    assert bundled_content == real_content, (
        "el bundle embebido de bridge.py esta DESACTUALIZADO respecto al codigo fuente real -- "
        "hay que regenerar el bundle (ver docs/architecture.md, seccion del generador en el navegador)"
    )
