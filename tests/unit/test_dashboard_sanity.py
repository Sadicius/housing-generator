"""Comprobaciones de sanidad sobre el dashboard (HTML/CSS/JS/bundle,
ahora en 4 archivos separados -- ver docs/historico/architecture.md, sección de
la separación de archivos), ejecutables con pytest normal (sin
necesitar Node/navegador). Cierran huecos reales encontrados durante
la sesión que nunca se convirtieron en test permanente, aplicando la
propia convención del proyecto (ver docs/CONTINUIDAD.md, "ninguna
verificación exploratoria cuenta como comprobado").
"""
import json
import re
from pathlib import Path

VISUALIZADOR_DIR = Path(__file__).parents[2] / "html"
HTML_PATH = VISUALIZADOR_DIR / "relaciones_espaciales.html"
CSS_PATH = VISUALIZADOR_DIR / "relaciones_espaciales.css"
JS_DIR = VISUALIZADOR_DIR / "js"
BUNDLE_PATH = VISUALIZADOR_DIR / "py_bundle.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_js() -> str:
    # el JS principal ahora vive en varios archivos (js/00-shared.js,
    # js/01-matriz.js...), uno por pestana -- concatenados para
    # comprobaciones de contenido que no dependen de en cual vive algo
    # concreto, robusto ante reorganizar la division en el futuro.
    return "\n".join(_read(p) for p in sorted(JS_DIR.glob("*.js")))


def test_room_and_door_stroke_width_is_in_meters_not_pixels():
    # BUG REAL encontrado con una captura de pantalla real del usuario:
    # el viewBox del SVG del plano esta en METROS (coordenadas reales de
    # la vivienda), pero .room-rect/.door-mark tenian stroke-width:2/5
    # -- pensados como pixeles razonables, se interpretaban como 2 y 5
    # METROS de grosor de linea, mas grueso que estancias enteras.
    # Umbral: ninguna estancia real del proyecto mide menos de ~0.4m de
    # lado, asi que cualquier stroke-width por encima de 0.5m es
    # sospechoso de estar pensado en pixeles, no en metros.
    css = _read(CSS_PATH)

    room_rect_match = re.search(r"\.room-rect\{[^}]*stroke-width:\s*([\d.]+)", css)
    door_mark_match = re.search(r"\.door-mark\{[^}]*stroke-width:\s*([\d.]+)", css)

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


def test_zones_structure_matches_tabs_and_panels():
    # sustituye al antiguo "7 pestanas planas" tras la reestructuracion
    # por zonas (Diseno/Consulta/Planificacion) -- confirma: 3 zonas
    # reales, cada boton de tab/subtab/flow-step con su panel real
    # correspondiente (una discrepancia aqui es una pestana rota o un
    # panel inaccesible), y que cada zona-panel contiene al menos un
    # panel real.
    html = _read(HTML_PATH)
    zonas = re.findall(r'<button class="zona-btn[^"]*" data-zona="(\w+)">', html)
    zona_panels = re.findall(r'<div class="zona-panel[^"]*" id="zona-(\w+)"', html)
    assert len(zonas) == 3
    assert set(zonas) == set(zona_panels)

    tabs = re.findall(r'class="tab[^"]*" data-tab="(\w+)"', html)
    panels = re.findall(r'<div class="panel[^"]*" id="panel-(\w+)"', html)
    # cronograma no tiene tab propio a proposito: es el unico panel de
    # su zona, sin sub-navegacion necesaria.
    panels_con_tab_esperado = set(panels) - {"cronograma"}
    assert set(tabs) == panels_con_tab_esperado, (
        f"tabs sin panel o paneles sin tab: {set(tabs) ^ panels_con_tab_esperado}"
    )


def test_matriz_and_sinergias_merged_with_view_toggle():
    # confirma la fusion (Matriz de adyacencia + Sinergias en una sola
    # pestana "Relaciones entre tipos", con selector de vista) --
    # ambos contenidos originales deben seguir presentes, solo
    # reorganizados, no perdidos.
    html = _read(HTML_PATH)
    assert 'id="panel-relaciones"' in html
    assert 'data-view="tabla"' in html
    assert 'data-view="red"' in html
    assert 'id="view-tabla"' in html
    assert 'id="view-red"' in html
    assert 'id="matrix-table"' in html  # contenido de la antigua Matriz, conservado
    assert 'id="net-svg"' in html  # contenido de la antigua Sinergias, conservado


def test_scripts_are_positioned_after_all_zone_content_not_mid_document():
    # BUG REAL encontrado al reestructurar por zonas: los scripts
    # clasicos se quedaron en su posicion ORIGINAL (el final de la
    # estructura plana anterior) tras reordenar los paneles en zonas --
    # como el reordenamiento dejo contenido DESPUES de los scripts en
    # el documento, un navegador real fallaria al ejecutar codigo de
    # nivel superior que hace document.getElementById(...) sobre
    # elementos que todavia no existen en el DOM en ese punto del
    # analisis. Corregido moviendolos al final real del body -- este
    # test evita que vuelva a pasar en silencio.
    html = _read(HTML_PATH)
    ultimo_zona_panel_pos = html.rindex('class="zona-panel')
    primer_script_local_pos = html.index('<script src="py_bundle.js">')
    assert primer_script_local_pos > ultimo_zona_panel_pos, (
        "los scripts locales aparecen ANTES de que termine el ultimo zona-panel en el "
        "documento -- fallarian en un navegador real al intentar acceder a elementos "
        "que todavia no existen"
    )


def test_garage_min_exterior_matches_python_default():
    # otro hallazgo real de auditoria anterior (GARAGE.min_exterior
    # desactualizado en el dashboard tras corregirse en Python) --
    # cerrado con un test permanente para que no se repita en silencio.
    from housing_generator.domain.enums import DEFAULT_MIN_EXTERIOR_SIDES, RoomType

    js = _read_js()
    match = re.search(r'"GARAGE":\s*\{[^}]*"min_exterior":\s*(\d+)', js)
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
    # (IBM Plex) mezclada por error con las nuevas, en ninguno de los
    # archivos (HTML: link de Google Fonts; CSS: font-family).
    html = _read(HTML_PATH)
    css = _read(CSS_PATH)
    assert "IBM Plex" not in html
    assert "IBM Plex" not in css.replace("sustituye IBM Plex", "")  # exceptua el propio comentario que lo explica
    assert "Space+Grotesk" in html or "Space Grotesk" in html
    assert "Space Grotesk" in css
    assert "Archivo" in css
    assert "Space Mono" in css


def test_redesign_css_variable_names_preserved_for_javascript():
    # el rediseño cambio los VALORES hexadecimales de la paleta, pero
    # los NOMBRES de las variables CSS deben seguir siendo exactamente
    # los que el JS referencia (COLORVAR, CAT_COLOR, generacion de SVG
    # del plano) -- si un nombre cambia sin actualizar el JS, los
    # colores se romperian en silencio (var() no definida = color por
    # defecto del navegador, sin error visible).
    css = _read(CSS_PATH)
    required_var_names = [
        "--bg:", "--bg-panel:", "--bg-panel-2:", "--line:", "--line-soft:",
        "--ink:", "--ink-dim:", "--ink-faint:", "--cyan:", "--cyan-dim:",
        "--oc:", "--ol:", "--cat-estancia:", "--pc:", "--pa:", "--n:", "--cond:",
        "--zone-day:", "--zone-night:", "--zone-service:", "--zone-circulation:",
        "--ok:", "--warn:", "--bad:",
    ]
    for name in required_var_names:
        assert name in css, f"variable CSS {name} no encontrada -- el JS podria depender de ella"


def test_pyodide_bundle_contains_the_bridge_and_key_modules():
    # generador real en el navegador (Pyodide) -- confirma que el
    # bundle Python (py_bundle.js) incluye el puente (bridge.py) y los
    # modulos clave que necesita para funcionar, sin tener que cargar
    # el navegador real para saberlo.
    bundle_js = _read(BUNDLE_PATH)
    assert "const PY_BUNDLE = {" in bundle_js
    for expected_path in [
        "housing_generator/interface/browser/bridge.py",
        "housing_generator/config/container.py",
        "housing_generator/infrastructure/persistence/seleccion_plantas_importer.py",
        "housing_generator/infrastructure/persistence/json_layout_repository.py",
    ]:
        assert expected_path in bundle_js, f"{expected_path} no encontrado en PY_BUNDLE"


def test_pyodide_cdn_script_tag_present_with_a_pinned_version():
    # version fija (no 'latest'/'dev'), confirmado con la documentacion
    # oficial de Pyodide en el momento de construir esto -- una URL sin
    # version fija podria cambiar de comportamiento sin aviso.
    html = _read(HTML_PATH)
    match = re.search(r'<script src="https://cdn\.jsdelivr\.net/pyodide/(v[\d.]+)/full/pyodide\.js"></script>', html)
    assert match, "no se encontro el script de Pyodide con una version fija (vX.Y.Z)"


def test_html_references_js_files_via_classic_tags_in_order():
    # separacion de archivos (CSS/JS por pestana/bundle) a peticion del
    # usuario -- confirma que el HTML los referencia con <link>/<script
    # src=""> CLASICOS (nunca type="module"), que son los unicos que
    # funcionan abriendo el archivo directamente con file:// sin
    # servidor (confirmado con investigacion antes de separar: los
    # modulos ES y fetch() SI se bloquean desde file://, los scripts/
    # link clasicos no). El orden importa: 00-shared antes que el
    # resto (todas dependen de sus globals), 09-init al final (llama
    # funciones de todos los demas al arrancar, incluido 07-cronograma
    # y 08-catalogo).
    html = _read(HTML_PATH)
    assert 'rel="stylesheet" href="relaciones_espaciales.css"' in html or \
        'href="relaciones_espaciales.css" rel="stylesheet"' in html
    assert '<script src="py_bundle.js"></script>' in html
    assert 'type="module"' not in html

    expected_order = [
        "py_bundle.js", "js/00-shared.js", "js/01-matriz.js", "js/02-seccion.js",
        "js/03-fichas.js", "js/04-sinergias.js", "js/05-visor.js", "js/06-pyodide.js",
        "js/07-cronograma.js", "js/08-catalogo.js", "js/09-init.js",
    ]
    positions = [html.index(f'<script src="{name}">') for name in expected_order]
    assert positions == sorted(positions), "los scripts JS no estan en el orden esperado en el HTML"


def test_generate_now_button_and_status_area_exist():
    html = _read(HTML_PATH)
    assert 'id="generate-now"' in html
    assert 'id="generate-status"' in html
    assert 'id="generate-config"' in html


def test_mirror_mode_controls_exist():
    html = _read(HTML_PATH)
    for control_id in ["mirror-h", "mirror-v", "mirror-rotate", "mirror-reset"]:
        assert f'id="{control_id}"' in html


def test_cronograma_controls_exist():
    html = _read(HTML_PATH)
    for control_id in ["gantt-start-date", "gantt-fase-nombre", "gantt-fase-categoria",
                        "gantt-fase-duracion", "gantt-add-fase", "gantt-table", "gantt-chart-content"]:
        assert f'id="{control_id}"' in html


def test_catalogo_constructivo_has_expected_items_per_category():
    # confirma el alcance acordado explicitamente con el usuario: 10
    # por categoria (composicion por capas + huecos + particiones),
    # y 13 en puentes termicos (lista real y cerrada del propio
    # catalogo CEC, no una muestra recortada).
    js_files = sorted(JS_DIR.glob("*.js"))
    catalogo_js = next(p for p in js_files if p.name == "08-catalogo.js")
    content = _read(catalogo_js)
    match = re.search(r"const CATALOGO_CONSTRUCTIVO = (\{.*?\});", content, re.DOTALL)
    assert match, "no se pudo extraer CATALOGO_CONSTRUCTIVO de 08-catalogo.js"
    data = json.loads(match.group(1))
    expected_categorias = {
        "fachadas": 10, "cubiertas": 10, "forjados": 10, "huecos": 10,
        "particionesVerticales": 10, "particionesHorizontales": 10, "puentesTermicos": 13,
    }
    assert set(data.keys()) == set(expected_categorias.keys())
    for categoria, expected_n in expected_categorias.items():
        assert len(data[categoria]) == expected_n, (
            f"{categoria} tiene {len(data[categoria])} elementos, se esperaban {expected_n}"
        )


def test_catalogo_constructivo_meets_passivhaus_thresholds():
    # confirmado explicitamente con el usuario: fachadas y cubiertas
    # deben cumplir el estandar Passivhaus real (U 0.10-0.15 W/m2K),
    # huecos Uw<=0.80 W/m2K -- forjados y particiones interiores quedan
    # fuera a proposito (no son envolvente termica). Puentes termicos:
    # el valor Passivhaus debe ser claramente menor que el estandar en
    # los 13 (principio de "construccion libre de puentes termicos").
    js_files = sorted(JS_DIR.glob("*.js"))
    catalogo_js = next(p for p in js_files if p.name == "08-catalogo.js")
    content = _read(catalogo_js)
    match = re.search(r"const CATALOGO_CONSTRUCTIVO = (\{.*?\});", content, re.DOTALL)
    data = json.loads(match.group(1))

    for categoria in ("fachadas", "cubiertas"):
        for elem in data[categoria]:
            u = elem["transmitancia_u"]
            assert 0.08 <= u <= 0.16, f"{categoria}/{elem['id']}: U={u} fuera del rango Passivhaus (0.08-0.16)"

    for hueco in data["huecos"]:
        uw = hueco["transmitancia_u_global"]
        assert uw <= 0.80, f"{hueco['id']}: Uw={uw} no cumple el umbral Passivhaus (<=0.80 W/m2K)"

    for pt in data["puentesTermicos"]:
        assert pt["psi_passivhaus"] < pt["psi_estandar"], (
            f"{pt['id']}: el valor Passivhaus ({pt['psi_passivhaus']}) deberia ser menor que "
            f"el estandar ({pt['psi_estandar']}) -- principio de construccion libre de puentes termicos"
        )
        assert pt["psi_passivhaus"] <= 0.15, f"{pt['id']}: Psi Passivhaus={pt['psi_passivhaus']} demasiado alto"


def test_pyodide_bundle_is_not_stale_against_the_real_source():
    # riesgo real de mantenimiento: si alguien edita un .py del
    # generador despues de esto sin regenerar el bundle (py_bundle.js,
    # via scripts/regenerar_bundle_pyodide.py), el navegador seguiria
    # ejecutando el codigo VIEJO en silencio, sin ningun error -- este
    # test compara el contenido REAL de bridge.py (el mas probable de
    # tocarse) contra lo que hay embebido en el bundle, byte a byte.
    src_root = Path(__file__).parents[2] / "src"
    bridge_path = src_root / "housing_generator" / "interface" / "browser" / "bridge.py"
    real_content = bridge_path.read_text(encoding="utf-8")

    bundle_js = _read(BUNDLE_PATH)
    match = re.search(r"const PY_BUNDLE = (\{.*\});", bundle_js, re.DOTALL)
    assert match, "no se pudo extraer PY_BUNDLE de py_bundle.js"
    bundle = json.loads(match.group(1))

    bundled_content = bundle.get("housing_generator/interface/browser/bridge.py")
    assert bundled_content is not None, "bridge.py no esta en el bundle"
    assert bundled_content == real_content, (
        "el bundle embebido (py_bundle.js) de bridge.py esta DESACTUALIZADO respecto al "
        "codigo fuente real -- ejecutar: python scripts/regenerar_bundle_pyodide.py"
    )


def test_inicio_launcher_links_point_to_real_files():
    # INICIO.html en la raiz del proyecto es el punto de entrada --
    # confirma que sus enlaces (dashboard real + documentacion) apuntan
    # a archivos que de verdad existen, no rutas rotas.
    root = Path(__file__).parents[2]
    inicio_path = root / "INICIO.html"
    assert inicio_path.exists(), "INICIO.html deberia existir en la raiz del proyecto"

    html = inicio_path.read_text(encoding="utf-8")
    hrefs = re.findall(r'href="([^"]+)"', html)
    rutas_locales = [h for h in hrefs if not h.startswith("http")]
    assert rutas_locales, "INICIO.html no tiene ningun enlace local"
    for ruta in rutas_locales:
        assert (root / ruta).exists(), f"INICIO.html enlaza a '{ruta}', que no existe"

    # el enlace principal debe apuntar al dashboard real, no a una copia
    assert 'href="html/relaciones_espaciales.html"' in html


def test_install_scripts_exist_and_shell_syntax_is_valid():
    # instalar.sh/instalar.bat automatizan venv+pip install para el CLI
    # (no hace falta para el dashboard). La version .sh se verifica de
    # verdad (bash -n, chequeo de sintaxis sin ejecutar) -- la .bat NO
    # se puede verificar en este entorno (sin Windows/cmd.exe
    # disponibles), revisada a mano con cuidado pero sin ejecucion real.
    import subprocess

    root = Path(__file__).parents[2]
    sh_path = root / "instalar.sh"
    bat_path = root / "instalar.bat"
    assert sh_path.exists(), "instalar.sh deberia existir en la raiz del proyecto"
    assert bat_path.exists(), "instalar.bat deberia existir en la raiz del proyecto"

    result = subprocess.run(["bash", "-n", str(sh_path)], capture_output=True, text=True)
    assert result.returncode == 0, f"instalar.sh tiene un error de sintaxis: {result.stderr}"


def test_scope_notes_moved_to_dedicated_panel_not_always_visible():
    # a peticion del usuario: las notas de alcance (antes siempre
    # visibles arriba de Matriz/Cronograma/Catalogo, ocupando espacio
    # de trabajo permanentemente) se movieron a un panel dedicado
    # ("Notas de alcance", subpestana de Consulta), accesible bajo
    # demanda desde un pequeno indicador en cada pestana afectada.
    html = _read(HTML_PATH)

    # el panel dedicado existe, con las 3 notas reales dentro (movidas,
    # no perdidas ni duplicadas)
    assert 'id="panel-notas"' in html
    assert 'data-tab="notas"' in html
    for ancla in ["nota-relaciones", "nota-catalogo", "nota-cronograma"]:
        assert f'id="{ancla}"' in html

    # exactamente 3 notas de alcance en todo el documento (no 6 -- si
    # aparecieran duplicadas, esto lo detectaria)
    assert html.count('class="caveat"') == 3

    # las 3 viven DENTRO de panel-notas, no sueltas en otro sitio --
    # comprobado indirectamente: cada indicador enlaza a su ancla
    for ancla in ["nota-relaciones", "nota-catalogo", "nota-cronograma"]:
        assert f'data-nota="{ancla}"' in html, f"falta el indicador para {ancla}"


def test_export_plano_generado_button_exists():
    # a peticion del usuario, tras probar el flujo real: exportar la
    # SELECCION (paso 1) y confundirla con el plano YA GENERADO
    # causaba el error "falta rooms" al intentar recargarla. Este
    # boton exporta el resultado real (rooms/doors/metadata) desde el
    # propio visor, en un unico archivo consolidado.
    html = _read(HTML_PATH)
    assert 'id="export-plano"' in html


def test_vacio_shape_rendering_exists():
    # a peticion del usuario: la huella construible no ocupa el 100%
    # de la parcela, el sobrante (vacio, exterior real) se dibuja como
    # capa de fondo en el visor. Ver [ARCH:area-objetivo].
    content = _read_js()
    assert "vacio_rings" in content
    assert "vacio-shape" in content
    css = _read(CSS_PATH)
    assert ".vacio-shape" in css


def test_docs_readme_links_point_to_real_files():
    # docs/README.md es el indice de toda la reorganizacion por temas
    # -- confirma que sus enlaces (locales, no http) apuntan a archivos
    # que existen de verdad, mismo patron que test_inicio_launcher.
    import re
    root = Path(__file__).parents[2]
    readme_path = root / "docs" / "README.md"
    assert readme_path.exists()

    content = readme_path.read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", content)
    locales = [link for link in links if not link.startswith("http")]
    assert locales, "docs/README.md no tiene ningun enlace local"
    for link in locales:
        resolved = (root / "docs" / link).resolve()
        assert resolved.exists(), f"docs/README.md enlaza a '{link}', que no existe"
