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
