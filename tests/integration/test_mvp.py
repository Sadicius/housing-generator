"""Smoke test del MVP: ejecuta el generador una vez de extremo a extremo
(subprocess real del CLI, no una reconstrucción interna) y valida que la
salida existe y no está corrupta -- el "¿esto arranca de verdad?" que
pide un MVP, separado de la suite completa (502 unitarios + integración),
que ya cubre la lógica en detalle. Ver README_MVP.md.
"""

import json
import subprocess
import sys


def test_default_demo_generates_a_valid_non_corrupt_layout(tmp_path):
    """Camino feliz del MVP: planta única, semilla fija por defecto --
    el escenario que README_MVP.md documenta como fiable. Sin --seed/
    --import-seleccion: mismo comando que un usuario nuevo ejecutaría
    siguiendo el README."""
    output_path = tmp_path / "layout.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "housing_generator.interface.cli.main",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, f"El CLI termino con error:\n{result.stderr}"
    assert output_path.exists(), "El CLI no escribio el archivo de salida"

    data = json.loads(output_path.read_text(encoding="utf-8"))

    # esquema minimo esperado -- si esto cambia sin querer, algo rompio
    # el contrato JSON que consume el dashboard (ver JsonLayoutRepository.to_dict)
    assert set(data.keys()) == {"rooms", "doors", "metadata"}
    assert isinstance(data["rooms"], list) and len(data["rooms"]) > 0
    assert isinstance(data["doors"], list)
    assert isinstance(data["metadata"], dict)
    assert (
        data["metadata"]["hard_violations"] == 0
    ), "El layout de ejemplo por defecto deberia converger sin violaciones duras"

    for room in data["rooms"]:
        assert set(room.keys()) == {"id", "name", "type", "zone", "area_m2", "bounds"}
        assert room["area_m2"] > 0
        bounds = room["bounds"]
        assert (
            bounds is not None and len(bounds) == 4
        ), f"'{room['id']}' tiene bounds corruptos/degenerados: {bounds}"
        minx, miny, maxx, maxy = bounds
        assert (
            maxx > minx and maxy > miny
        ), f"'{room['id']}' tiene un area geometrica nula o negativa: {bounds}"
        # nada de NaN/Infinity coladas (ver allow_nan=False en JsonLayoutRepository.save)
        assert all(
            v == v and abs(v) != float("inf") for v in bounds
        ), f"'{room['id']}' tiene NaN/Infinity en bounds: {bounds}"


def test_impossible_program_fails_clearly_not_silently_or_hanging(tmp_path):
    """Modo seguro: un retranqueo que deja el area edificable
    imposiblemente pequena para el programa de ejemplo debe fallar
    RAPIDO con un mensaje claro (exit code != 0, motivo legible en
    stderr) -- nunca colgarse ni terminar con exito silencioso sobre
    una vivienda invalida. --lot-size no aplica al modo por defecto
    (solo a --import-seleccion) -- --retranqueo si, es la forma real
    de forzar una parcela inviable aqui."""
    output_path = tmp_path / "no_deberia_escribirse.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "housing_generator.interface.cli.main",
            "--retranqueo",
            "6",
            "--max-iterations",
            "50",
            "--retry-seeds",
            "2",
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode != 0, "Una parcela imposible no deberia terminar con exito"
    assert (
        not output_path.exists()
    ), "No deberia escribirse ningun archivo de salida cuando la generacion falla"
