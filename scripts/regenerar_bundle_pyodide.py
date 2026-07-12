#!/usr/bin/env python3
"""Regenera el bundle Python embebido en el dashboard (PY_BUNDLE, usado
por el generador real en el navegador via Pyodide).

USO: ejecutar despues de CUALQUIER cambio a un archivo .py bajo
`src/housing_generator/` -- si no, el dashboard sigue ejecutando
codigo VIEJO en el navegador, en silencio, sin ningun error visible.
`tests/unit/test_dashboard_sanity.py::test_pyodide_bundle_is_not_stale_against_the_real_source`
detecta esto para bridge.py especificamente, pero regenerar tras
cualquier cambio es la practica correcta, no solo para ese archivo.

    python scripts/regenerar_bundle_pyodide.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
DASHBOARD = ROOT / "docs" / "visualizador" / "relaciones_espaciales.html"


def build_bundle() -> dict:
    bundle = {}
    base = SRC / "housing_generator"
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        bundle[rel] = path.read_text(encoding="utf-8")
    return bundle


def main():
    bundle = build_bundle()
    bundle_js = json.dumps(bundle, ensure_ascii=False)

    html = DASHBOARD.read_text(encoding="utf-8")
    pattern = re.compile(r"const PY_BUNDLE = \{.*?\};\nlet PYODIDE_INSTANCE", re.DOTALL)
    match = pattern.search(html)
    if not match:
        raise SystemExit("No se encontro el bloque 'const PY_BUNDLE = ...;\\nlet PYODIDE_INSTANCE' en el dashboard")

    replacement = f"const PY_BUNDLE = {bundle_js};\nlet PYODIDE_INSTANCE"
    html = html[:match.start()] + replacement + html[match.end():]
    DASHBOARD.write_text(html, encoding="utf-8")

    print(f"Bundle regenerado: {len(bundle)} archivos, {len(bundle_js)} caracteres JSON.")
    print(f"Escrito en {DASHBOARD}")


if __name__ == "__main__":
    main()
