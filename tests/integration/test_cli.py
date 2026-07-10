import json
import subprocess
import sys
from housing_generator.interface.cli.main import build_sample_program, build_sample_lot
from housing_generator.config.container import build_generate_layout_use_case
from housing_generator.application.dto.generation_request import GenerationRequest


def test_sample_program_is_a_complete_minimum_program():
    # el propio programa de ejemplo debe cumplir ViviendaMinimaValidator --
    # si alguien lo edita y quita, p.ej., el tendedero, este test debe fallar
    # antes que descubrirlo en produccion (paso a la version de main.py con
    # git blame identificable, no una ejecucion manual perdida en el historial
    # de una conversacion).
    program = build_sample_program()
    types_present = {r.room_type.value for r in program.rooms}
    for required in ("living_room", "kitchen", "bathroom", "laundry", "drying_area", "storage"):
        assert required in types_present, f"El programa de ejemplo del CLI no tiene {required}"


def test_sample_program_generates_a_valid_layout_with_fixed_seed():
    # semilla fija: determinista, no depende de si el recocido simulado
    # tuvo suerte esta vez (a diferencia de `python -m ...main`, que usa
    # seed=None y puede fallar aleatoriamente segun ya vimos en la sesion).
    program = build_sample_program()
    lot = build_sample_lot()
    use_case = build_generate_layout_use_case(
        adjacency_requirements=program.adjacency_requirements, seed=1, max_iterations=3000
    )
    layout = use_case.execute(GenerationRequest(program=program, lot=lot))

    assert layout.metadata["violations"] == 0
    assert len(layout.rooms) == len(program.rooms)
    for room in layout.rooms:
        assert room.is_placed


def test_cli_end_to_end_as_a_real_subprocess(tmp_path):
    # ejecuta el CLI de verdad, como lo haria un usuario -- no solo import
    # de sus funciones. Confirma que main.py funciona como entry point real.
    output_path = tmp_path / "layout_cli_test.json"
    result = subprocess.run(
        [sys.executable, "-m", "housing_generator.interface.cli.main", "--output", str(output_path)],
        capture_output=True, text=True, timeout=30,
    )

    assert result.returncode == 0, f"El CLI fallo: {result.stderr}"
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["rooms"]) > 0
    assert all(r["bounds"] is not None for r in data["rooms"])


def test_cli_with_auto_adjacency_as_a_real_subprocess(tmp_path):
    # retomado de docs/CONTINUIDAD.md: conectar generate_adjacency_requirements
    # como opcion automatica real en el CLI, no solo una funcion suelta que
    # hay que llamar a mano. Confirma que --auto-adjacency funciona de
    # extremo a extremo como subproceso real, con mas iteraciones/semilla
    # distinta (el conjunto derivado del catalogo -- 44 requisitos en vez
    # de 6 -- es una busqueda notablemente mas dificil, ya documentado).
    output_path = tmp_path / "layout_auto_adjacency.json"
    result = subprocess.run(
        [
            sys.executable, "-m", "housing_generator.interface.cli.main",
            "--output", str(output_path), "--auto-adjacency",
            "--max-iterations", "5000", "--seed", "1",
        ],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, f"El CLI con --auto-adjacency fallo: {result.stderr}"
    assert output_path.exists()

    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(data["rooms"]) == 11
    assert all(r["bounds"] is not None for r in data["rooms"])
    # las puertas solo reflejan pares Obligatorio cerca satisfechos (no
    # las preferencias blandas) -- el catalogo completo de 120 pares solo
    # tiene 4 "Obligatorio cerca" en total (mismo numero que el ejemplo
    # curado a mano, por coincidencia), asi que 4 es lo correcto aqui,
    # no una senal de que el catalogo aporte mas puertas que lo manual.
    assert len(data["doors"]) == 4


def test_cli_with_import_seleccion_as_a_real_subprocess(tmp_path):
    # retomado de docs/CONTINUIDAD.md, ultimo pendiente real: importador
    # JSON (exportacion del dashboard) -> Program real, conectado tambien
    # como opcion real del CLI, no solo una funcion Python suelta.
    import json as json_module

    seleccion_path = tmp_path / "seleccion_plantas.json"
    seleccion_path.write_text(json_module.dumps({
        "levels": {
            "PLANTA_BAJA": ["LIVING_ROOM", "KITCHEN", "ENTRANCE_HALL", "LAUNDRY", "DRYING_AREA", "STORAGE"],
            "PLANTA_SUPERIOR": ["BEDROOM", "MASTER_BEDROOM", "BATHROOM", "CORRIDOR"],
        },
    }), encoding="utf-8")
    output_path = tmp_path / "edificio.json"

    result = subprocess.run(
        [
            sys.executable, "-m", "housing_generator.interface.cli.main",
            "--import-seleccion", str(seleccion_path), "--output", str(output_path),
            "--max-iterations", "4000", "--seed", "1",
        ],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, f"El CLI con --import-seleccion fallo: {result.stderr}"

    pb_path = tmp_path / "edificio_planta_baja.json"
    ps_path = tmp_path / "edificio_planta_superior.json"
    assert pb_path.exists() and ps_path.exists()

    data_pb = json.loads(pb_path.read_text(encoding="utf-8"))
    data_ps = json.loads(ps_path.read_text(encoding="utf-8"))
    assert len(data_pb["rooms"]) == 6
    assert len(data_ps["rooms"]) == 4


def test_cli_retries_seeds_automatically_when_the_first_one_does_not_converge(tmp_path):
    # retomado de un caso real: un usuario cargo un seleccion_plantas.json
    # real (planta baja con salon/comedor/cocina/dorm.ppal/bano/recibidor/
    # lavadero/tendedero/almacen, SIN corridor) y la semilla 1 (la que
    # usa el CLI por defecto) no convergia -- la semilla 4 si. Confirma
    # que ahora el CLI reintenta solo, sin que el usuario tenga que
    # buscar una semilla a mano.
    import json as json_module

    seleccion_path = tmp_path / "seleccion_plantas.json"
    seleccion_path.write_text(json_module.dumps({
        "version": 2,
        "levels": {
            "PLANTA_BAJA": [
                {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
                {"type": "DINING_ROOM", "count": 1, "area_m2": 14},
                {"type": "KITCHEN", "count": 1, "area_m2": 10},
                {"type": "MASTER_BEDROOM", "count": 1, "area_m2": 15},
                {"type": "BATHROOM", "count": 1, "area_m2": 5.5},
                {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
                {"type": "LAUNDRY", "count": 1, "area_m2": 3},
                {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
                {"type": "STORAGE", "count": 1, "area_m2": 3},
            ],
        },
    }), encoding="utf-8")
    output_path = tmp_path / "edificio.json"

    result = subprocess.run(
        [
            sys.executable, "-m", "housing_generator.interface.cli.main",
            "--import-seleccion", str(seleccion_path), "--output", str(output_path),
            "--max-iterations", "5000", "--seed", "1",
        ],
        capture_output=True, text=True, timeout=90,
    )

    assert result.returncode == 0, f"El CLI fallo pese al reintento automatico: {result.stderr}"
    assert "no convergio" in result.stdout  # confirma que de verdad reintento, no que acerto a la primera
    assert (tmp_path / "edificio_planta_baja.json").exists()


def test_cli_fails_clearly_when_retry_seeds_is_exhausted(tmp_path):
    # con retry_seeds=1 (sin reintento), el mismo escenario que arriba
    # SI debe fallar con la semilla 1 -- confirma que el mensaje de
    # fallo tras agotar los reintentos es claro, no una traza confusa.
    import json as json_module

    seleccion_path = tmp_path / "seleccion_plantas.json"
    seleccion_path.write_text(json_module.dumps({
        "version": 2,
        "levels": {
            "PLANTA_BAJA": [
                {"type": "LIVING_ROOM", "count": 1, "area_m2": 25},
                {"type": "DINING_ROOM", "count": 1, "area_m2": 14},
                {"type": "KITCHEN", "count": 1, "area_m2": 10},
                {"type": "MASTER_BEDROOM", "count": 1, "area_m2": 15},
                {"type": "BATHROOM", "count": 1, "area_m2": 5.5},
                {"type": "ENTRANCE_HALL", "count": 1, "area_m2": 4.5},
                {"type": "LAUNDRY", "count": 1, "area_m2": 3},
                {"type": "DRYING_AREA", "count": 1, "area_m2": 2},
                {"type": "STORAGE", "count": 1, "area_m2": 3},
            ],
        },
    }), encoding="utf-8")
    output_path = tmp_path / "edificio.json"

    result = subprocess.run(
        [
            sys.executable, "-m", "housing_generator.interface.cli.main",
            "--import-seleccion", str(seleccion_path), "--output", str(output_path),
            "--max-iterations", "5000", "--seed", "1", "--retry-seeds", "1",
        ],
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode != 0
    assert "No se pudo generar tras probar 1 semillas" in result.stderr
