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
    # por zonas (Parcela/Diseno/Consulta/Planificacion) -- confirma: 4
    # zonas reales (Zona 0 "Parcela" anadida despues, mismo patron),
    # cada boton de tab/subtab/flow-step con su panel real
    # correspondiente (una discrepancia aqui es una pestana rota o un
    # panel inaccesible), y que cada zona-panel contiene al menos un
    # panel real.
    html = _read(HTML_PATH)
    zonas = re.findall(r'<button class="zona-btn[^"]*" data-zona="(\w+)">', html)
    zona_panels = re.findall(r'<div class="zona-panel[^"]*" id="zona-(\w+)"', html)
    assert len(zonas) == 4
    assert set(zonas) == set(zona_panels)

    tabs = re.findall(r'class="tab[^"]*" data-tab="(\w+)"', html)
    panels = re.findall(r'<div class="panel[^"]*" id="panel-(\w+)"', html)
    # cronograma y parcela no tienen tab propio a proposito: son el
    # unico panel de su zona, sin sub-navegacion necesaria.
    panels_con_tab_esperado = set(panels) - {"cronograma", "parcela"}
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


def test_retranqueo_controls_are_wired_end_to_end():
    # hallazgo real al revisar las conexiones del dashboard a peticion
    # del usuario: la funcionalidad de retranqueo ya estaba correctamente
    # implementada de extremo a extremo (HTML -> JS -> Python), pero sin
    # NINGUN test que la protegiera -- si alguien tocaba uno de los tres
    # eslabones sin querer, nada lo habria detectado. Verifica los tres
    # eslabones reales, no solo que "algo con ese nombre existe en algun
    # sitio".
    html = _read(HTML_PATH)
    js = _read(JS_DIR / "06-pyodide.js")

    # eslabon 1: los dos controles existen en el HTML con el id exacto
    # que el JS espera
    for control_id in ("gen-retranqueo", "gen-retranqueo-incremento"):
        assert f'id="{control_id}"' in html, f"falta el control {control_id} en el HTML"

    # eslabon 2: handleGenerateNow los lee del DOM y los pasa a
    # generarEdificioReal (no silenciosamente ignorados)
    assert "getElementById('gen-retranqueo')" in js
    assert "getElementById('gen-retranqueo-incremento')" in js
    assert "retranqueoM, retranqueoIncremento" in js

    # eslabon 3: generarEdificioReal los reenvia de verdad al Python real
    # (no solo los recibe y los descarta)
    assert "retranqueo_m=" in js
    assert "retranqueo_incremento_por_planta_m=" in js


def test_retranqueo_none_case_does_not_rely_on_pyodide_null_conversion():
    # BUG REAL encontrado en un navegador de verdad (no reproducible en
    # este entorno de desarrollo, CDN de Pyodide bloqueado): sin
    # retranqueo, el usuario obtuvo "TypeError: float() argument must
    # be a string or a real number, not 'JsNull'". Causa raiz:
    # `pyodide.globals.set('x', null)` NO se convierte a `None` de
    # Python de forma fiable -- llega como un objeto `JsNull`, y
    # `JsNull is not None` da `True`. Corregido evitando el paso por
    # variable global para este valor -- se construye el literal
    # Python DIRECTAMENTE como texto ('None' o 'float(numero)'), nunca
    # via pyodide.globals.set(). Este test protege que no se reintroduzca
    # el patron que causo el bug real.
    js = _read(JS_DIR / "06-pyodide.js")
    assert "retranqueo_js" not in js, (
        "reaparecio el paso de retranqueo por variable global de pyodide -- "
        "esto fue exactamente lo que causo el bug real de JsNull en un navegador"
    )
    assert "retranqueoLiteral" in js
    assert "retranqueoIncrementoLiteral" in js
    assert "`    retranqueo_m=${retranqueoLiteral}," in js
    assert "`    retranqueo_incremento_por_planta_m=${retranqueoIncrementoLiteral}," in js


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

    # el panel dedicado existe, con las 5 notas reales dentro (movidas,
    # no perdidas ni duplicadas) -- nota-ancho-practico y nota-parcela
    # anadidas despues, mismo patron.
    assert 'id="panel-notas"' in html
    assert 'data-tab="notas"' in html
    anclas = ["nota-relaciones", "nota-catalogo", "nota-cronograma", "nota-ancho-practico", "nota-parcela"]
    for ancla in anclas:
        assert f'id="{ancla}"' in html

    # exactamente 5 notas de alcance en todo el documento (no 8 -- si
    # aparecieran duplicadas, esto lo detectaria)
    assert html.count('class="caveat"') == len(anclas)

    # las 5 viven DENTRO de panel-notas, no sueltas en otro sitio --
    # comprobado indirectamente: cada indicador enlaza a su ancla
    for ancla in anclas:
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
    assert "vacio_shapes" in content
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


def test_js_pairs_hard_relationships_match_the_real_python_catalog():
    # hallazgo real al revisar las conexiones del dashboard a peticion
    # del usuario: cuando se relajaron 3 de las 5 relaciones
    # obligatorias del catalogo Python ([ARCH:relaciones-obligatorias-revisadas]),
    # el commit correspondiente nunca toco html/js/00-shared.js -- la
    # Matriz, Fichas y Sinergias del dashboard seguian mostrando
    # "Obligatorio" para 3 pares que el generador real ya trata como
    # preferencia blanda. Corregido a mano; este test evita que la
    # proxima vez que cambie el catalogo Python, el dashboard se quede
    # desincronizado en silencio otra vez.
    import sys
    sys.path.insert(0, str(Path(__file__).parents[2] / "src"))
    from housing_generator.domain.services.type_adjacency_catalog import DEFAULT_TYPE_ADJACENCY
    from housing_generator.domain.enums import AdjacencyStrength

    js = _read(JS_DIR / "00-shared.js")
    match = re.search(r"const PAIRS = (\[.*\]);", js)
    assert match, "no se pudo extraer PAIRS de 00-shared.js"
    pairs = json.loads(match.group(1))
    js_relation_by_pair = {frozenset((p["a"], p["b"])): p["relation"] for p in pairs}

    discrepancias = []
    todos_los_pares_relevantes = set()
    for (type_a, type_b) in DEFAULT_TYPE_ADJACENCY.keys():
        key = frozenset((type_a.value.upper(), type_b.value.upper()))
        if key in js_relation_by_pair:
            todos_los_pares_relevantes.add((type_a, type_b))

    for (type_a, type_b) in todos_los_pares_relevantes:
        strength = DEFAULT_TYPE_ADJACENCY[(type_a, type_b)]
        key = frozenset((type_a.value.upper(), type_b.value.upper()))
        js_relation = js_relation_by_pair.get(key, "")
        js_dice_obligatorio = "obligatorio" in js_relation.lower()
        es_lejos_en_js = js_dice_obligatorio and "lejo" in js_relation.lower()
        es_cerca_en_js = js_dice_obligatorio and not es_lejos_en_js

        if strength == AdjacencyStrength.MUST_BE_NEAR and not es_cerca_en_js:
            discrepancias.append(f"{type_a.value}-{type_b.value}: Python=MUST_BE_NEAR, JS='{js_relation}'")
        elif strength == AdjacencyStrength.MUST_BE_AWAY and not es_lejos_en_js:
            discrepancias.append(f"{type_a.value}-{type_b.value}: Python=MUST_BE_AWAY, JS='{js_relation}'")
        elif strength not in (AdjacencyStrength.MUST_BE_NEAR, AdjacencyStrength.MUST_BE_AWAY) and js_dice_obligatorio:
            discrepancias.append(f"{type_a.value}-{type_b.value}: Python={strength.value} (NO obligatorio), pero JS='{js_relation}'")

    assert not discrepancias, "PAIRS en 00-shared.js desincronizado del catalogo Python real:\n" + "\n".join(discrepancias)


def test_zona_parcela_controls_exist_with_correct_ids():
    # Zona 0, a peticion del usuario: "estaria bien poder ver la
    # huella resultante antes de ir al programa". Verifica que los 8
    # controles de parcela existen con el id exacto que 00b-parcela.js
    # y 06-pyodide.js esperan.
    html = _read(HTML_PATH)
    assert 'id="zona-parcela"' in html
    assert 'data-zona="parcela"' in html
    for control_id in (
        "gen-lot-w", "gen-lot-h", "gen-street-side", "gen-retranqueo",
        "gen-retranqueo-incremento", "gen-edificabilidad", "gen-ocupacion-maxima",
        "gen-altura-maxima", "gen-frente-minimo",
    ):
        assert f'id="{control_id}"' in html, f"falta el control {control_id}"
    assert 'id="parcela-preview"' in html
    assert 'id="parcela-resumen"' in html


def test_zona_parcela_preview_js_is_loaded_and_wired_to_generation():
    # eslabon 1: el script existe y se carga
    html = _read(HTML_PATH)
    assert 'src="js/00b-parcela.js"' in html
    js_parcela = _read(JS_DIR / "00b-parcela.js")
    assert "function renderParcelaPreview" in js_parcela
    assert "function initParcelaPreview" in js_parcela

    # eslabon 2: 09-init.js llama a la inicializacion de verdad
    js_init = _read(JS_DIR / "09-init.js")
    assert "initParcelaPreview()" in js_init

    # eslabon 3: los 4 parametros urbanisticos + street_side llegan
    # hasta la llamada real a Python, no solo se leen y descartan
    js_pyodide = _read(JS_DIR / "06-pyodide.js")
    assert "numOpcional('gen-edificabilidad')" in js_pyodide
    assert "coeficiente_edificabilidad=" in js_pyodide
    assert "ocupacion_maxima_pct=" in js_pyodide
    assert "altura_maxima_plantas=" in js_pyodide
    assert "frente_minimo_m=" in js_pyodide
    assert "street_side=str(street_side_js)" in js_pyodide


def test_zona_parcela_preview_uses_the_same_null_safe_pattern_as_retranqueo():
    # mismo patron ya probado (evita el bug real de JsNull) aplicado a
    # los 4 parametros nuevos -- no deben pasar por pyodide.globals.set()
    # como valores potencialmente null.
    js = _read(JS_DIR / "06-pyodide.js")
    assert "edificabilidad_js" not in js  # no se paso por variable global
    assert "literalOpcional" in js
    assert "edificabilidadLiteral" in js
    assert "ocupacionMaximaLiteral" in js
    assert "alturaMaximaLiteral" in js
    assert "frenteMinimoLiteral" in js


def test_catastro_import_controls_exist_with_correct_ids():
    # Fase A de importacion de Catastro, a peticion del usuario. Verifica
    # que los controles de importacion existen con el id exacto que
    # 00b-parcela.js espera.
    html = _read(HTML_PATH)
    assert 'id="parcela-drop-zone"' in html
    assert 'id="parcela-gml-input"' in html
    assert 'id="parcela-import-status"' in html
    assert 'accept=".gml,.xml"' in html


def test_catastro_import_js_is_loaded_and_wired_to_the_bridge():
    js_parcela = _read(JS_DIR / "00b-parcela.js")
    assert "function manejarArchivoCatastro" in js_parcela
    assert "function renderParcelaImportada" in js_parcela
    assert "PARCELA_IMPORTADA" in js_parcela

    # eslabon real: el archivo llega hasta analizarParcelaCatastroReal,
    # no solo se lee y se descarta
    assert "analizarParcelaCatastroReal(contenido" in js_parcela

    # eslabon real: la funcion existe en 06-pyodide.js y llega hasta
    # Python de verdad (mismo patron que generarEdificioReal)
    js_pyodide = _read(JS_DIR / "06-pyodide.js")
    assert "async function analizarParcelaCatastroReal" in js_pyodide
    assert "analizar_parcela_catastro(gml_content_js" in js_pyodide


def test_catastro_import_retranqueo_uses_the_same_null_safe_pattern():
    # mismo patron anti-JsNull ya probado (bug real encontrado en el
    # navegador) aplicado tambien aqui -- retranqueoM puede ser null,
    # se construye como literal Python directo, no via variable global.
    js = _read(JS_DIR / "06-pyodide.js")
    assert "retranqueoLiteral" in js
    assert "retranqueo_m=${retranqueoLiteral}" in js


def test_zona_afeccion_recalculates_on_retranqueo_change_after_import():
    # hallazgo real de diseno: cambiar el retranqueo DESPUES de
    # importar debe recalcular la zona de afeccion de verdad (via
    # Pyodide), no quedarse con el valor de la primera importacion.
    js = _read(JS_DIR / "00b-parcela.js")
    assert "function reanalizarZonaAfeccionSiHayImportada" in js
    assert "reanalizarZonaAfeccionSiHayImportada()" in js


def test_real_polygon_reaches_generation_not_just_the_preview():
    # HALLAZGO REAL, confirmado por el usuario con captura del
    # navegador: el resumen de la Zona 0 mostraba numeros correctos
    # del poligono real, pero generar_edificio() solo recibia
    # ancho/fondo -- la generacion SIEMPRE trabajaba sobre el
    # rectangulo, nunca sobre la forma real. Verifica los 3 eslabones
    # reales de la conexion completa. Ver [ARCH:parcela-real].
    js_pyodide = _read(JS_DIR / "06-pyodide.js")

    # eslabon 1: generarEdificioReal acepta y reenvia el poligono real
    assert "poligonoRealCoords" in js_pyodide
    assert "poligono_real_coords=${poligonoRealLiteral}" in js_pyodide

    # eslabon 2: handleGenerateNow lee PARCELA_IMPORTADA de verdad, no
    # solo lo ignora
    assert "PARCELA_IMPORTADA.poligono_real" in js_pyodide

    # eslabon 3: se pasa el poligono EN BRUTO (no zona_afeccion) --
    # confirma que no se aplica el retranqueo dos veces
    assert "PARCELA_IMPORTADA.zona_afeccion" not in js_pyodide.split("handleGenerateNow")[1].split("async function")[0]


def test_seed_and_iterations_are_automatic_not_manual_fields():
    # a peticion del usuario ("sigo viendo raro cuando es algo que
    # deberia ser automatico"): gen-seed/gen-iterations eliminados del
    # HTML, la semilla de partida siempre es 1 (el reintento automatico
    # ya explora desde ahi) y las iteraciones se escalan segun el
    # numero real de estancias del programa, no un numero fijo elegido
    # a mano. Ver [ARCH:btree-generador-por-defecto].
    html = _read(HTML_PATH)
    assert 'id="gen-seed"' not in html
    assert 'id="gen-iterations"' not in html

    js = _read(JS_DIR / "06-pyodide.js")
    assert "const seed = 1" in js
    assert "totalRooms" in js
    assert "Math.max(1500, totalRooms * 300)" in js


def test_no_classic_generator_option_remains_anywhere_in_the_dashboard():
    # el generador clasico se elimino por completo del proyecto a
    # peticion explicita del usuario -- confirma que no queda ningun
    # resto (casilla, variable, nombre de parametro) en el dashboard.
    html = _read(HTML_PATH)
    js = _read(JS_DIR / "06-pyodide.js")
    assert "generador-clasico" not in html
    assert "generadorClasico" not in js
    assert "usar_generador_clasico" not in js
    assert "gen-experimental-btree" not in html
    assert "experimental_btree" not in js


def test_plano_viewer_includes_north_arrow_and_scale_bar():
    # rediseno visual a peticion del usuario (revision de arquitecto:
    # "el visor de plano viewer es probablemente el punto de mayor
    # oportunidad perdida"). Norte + escala grafica dentro del propio
    # SVG (mismo sistema de coordenadas en metros que las estancias),
    # no una superposicion HTML aparte -- escalan solas con el dibujo.
    js = _read(JS_DIR / "05-visor.js")
    assert "norteSvg" in js
    assert "escalaSvg" in js
    assert "text-anchor=\"middle\" fill=\"var(--ink-faint)\">N</text>" in js
    # la escala se redondea a un multiplo razonable segun el ancho del
    # plano, no un numero arbitrario fijo
    assert "escalaBaseM = vbW > 30 ? 5 : vbW > 12 ? 2 : 1" in js


def test_redesign_preserves_every_css_variable_name_the_js_references():
    # el rediseno cambio los VALORES hexadecimales, nunca los NOMBRES
    # de las variables -- el JS ya las referencia directamente (SVG
    # inline, getPropertyValue) y no se toco ninguna linea de esa
    # logica. Si un nombre desapareciera del CSS, esas referencias
    # quedarian silenciosamente rotas (var() sin definir no falla,
    # simplemente no pinta nada).
    css = _read(CSS_PATH)
    js_all = "".join(_read(JS_DIR / f) for f in [
        "00-shared.js", "01-matriz.js", "04-sinergias.js", "05-visor.js", "07-cronograma.js",
    ])
    import re
    nombres_referenciados = set(re.findall(r"--[a-z][a-z-]*[a-z]\b", js_all))
    for nombre in nombres_referenciados:
        assert f"{nombre}:" in css, f"variable {nombre} referenciada desde JS mais ya no definida en el CSS"


def test_header_content_reflects_the_whole_tool_not_just_the_original_matrix():
    # hallazgo real de contenido, senalado por el usuario: la cabecera
    # seguia describiendo solo la matriz de relaciones ("16 tipos, 120
    # pares"), resto de cuando la pagina entera era solo eso -- ahora
    # es una herramienta de 4 zonas (parcela, diseno, consulta,
    # planificacion). Las cifras citadas deben ser reales, no
    # supuestas -- verificadas contra el enum y los archivos de
    # validadores reales antes de escribirlas.
    html = _read(HTML_PATH)
    assert "housing_generator</h1>" in html
    assert "Matriz de relaciones espaciales</h1>" not in html
    assert "árbol B*" in html or "arbol B*" in html
    # cifras citadas en el bloque meta deben coincidir con la realidad
    from housing_generator.domain.enums import RoomType
    assert f"<div><span>tipos de estancia</span>{len(list(RoomType))}</div>" in html


def test_nota_indicador_button_lives_inside_its_own_panel_not_orphaned():
    # hallazgo real: el boton de nota de "Relaciones entre tipos" vivia
    # huerfano a nivel superior de la pagina (antes de elegir ninguna
    # zona), resto de cuando la pagina entera era la matriz. Movido
    # dentro de #panel-relaciones, mismo patron que Parcela/Cronograma.
    html = _read(HTML_PATH)
    assert 'id="panel-relaciones"><button class="nota-indicador" data-nota="nota-relaciones"' in html


def test_stale_tab_name_seccion_vertical_does_not_appear_anywhere():
    # hallazgo real: "pestaña Sección vertical" ya no existe (ahora es
    # el paso "Programa y generación" dentro de Zona 1 Diseño) pero se
    # seguia mencionando en la nota de alcance Y en un mensaje de error
    # real que ve el usuario al cargar un archivo equivocado.
    html = _read(HTML_PATH)
    js = _read(JS_DIR / "09-init.js")
    assert "Sección vertical" not in html
    assert "Sección vertical" not in js
    assert "Programa y generación" in js


def test_zona_done_marker_activates_after_real_success_not_just_css():
    # refinamiento visual pedido por el usuario ("aun podria refinarse
    # mas"): el CSS .zona-btn.done ya existia pero sin logica JS que lo
    # activara -- confirma que Zona 0 se marca tras importar una parcela
    # real, y Zona 1 tras generar un plano real, no solo que la clase
    # CSS exista sin usarse en ningun sitio.
    js_parcela = _read(JS_DIR / "00b-parcela.js")
    js_pyodide = _read(JS_DIR / "06-pyodide.js")
    assert "zonaParcela.classList.add('done')" in js_parcela
    assert "zonaDiseno.classList.add('done')" in js_pyodide


def test_header_has_real_navigation_not_just_a_fixed_sign():
    # a peticion del usuario: "ni puedo volver al inicio, ni puedo ir a
    # la parte de documentacion... unicamente tenemos este cartel fijo".
    html = _read(HTML_PATH)
    js = _read(JS_DIR / "09-init.js")
    assert 'id="titleblock-home"' in html
    assert 'href="../docs/GUIA_USO.md"' in html
    assert "getElementById('titleblock-home')" in js
    assert "dataset.zona" in js or "data-zona=\"parcela\"" in js


def test_confirmar_parcela_button_connects_zona_0_to_zona_1():
    # a peticion del usuario: "necesitaria un boton de conexion entre
    # la zona 0 y la zona 1 para facilitar la conexion de los datos".
    html = _read(HTML_PATH)
    js = _read(JS_DIR / "09-init.js")
    assert 'id="confirmar-parcela"' in html
    assert "getElementById('confirmar-parcela')" in js
    assert "data-zona=\"diseno\"" in js


def test_parcela_preview_draws_true_orientation_not_the_generator_aligned_version():
    # hallazgo real del usuario ("rota la orientacion real de la
    # parcela, cosa que no es adecuado para una buena interpretacion"):
    # la vista previa debe dibujar poligono_orientacion_real, no
    # poligono_real (que esta rotado para encajar con el generador).
    js = _read(JS_DIR / "00b-parcela.js")
    assert "const poligono = p.poligono_orientacion_real" in js
    assert "const rectangulo = p.rectangulo_trabajo_orientacion_real" in js
    assert "const zonaAfeccion = p.zona_afeccion_orientacion_real" in js
