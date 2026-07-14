#!/usr/bin/env python3
"""Regenera el bundle Python embebido para el dashboard (PY_BUNDLE, usado
por el generador real en el navegador via Pyodide) -- ahora en su propio
archivo `py_bundle.js` (separado de relaciones_espaciales.html, a
peticion del usuario tras el rediseño completo de la interfaz).

USO: ejecutar despues de CUALQUIER cambio a un archivo .py bajo
`src/housing_generator/` -- si no, el dashboard sigue ejecutando
codigo VIEJO en el navegador, en silencio, sin ningun error visible.
`tests/unit/test_dashboard_sanity.py::test_pyodide_bundle_is_not_stale_against_the_real_source`
detecta esto para bridge.py especificamente, pero regenerar tras
cualquier cambio es la practica correcta, no solo para ese archivo.

    python scripts/regenerar_bundle_pyodide.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"
PY_BUNDLE_JS = ROOT / "html" / "py_bundle.js"


def build_bundle() -> dict:
    bundle = {}
    base = SRC / "housing_generator"
    for path in sorted(base.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        bundle[rel] = path.read_text(encoding="utf-8")
    return bundle


def main():
    bundle = build_bundle()
    bundle_json = json.dumps(bundle, ensure_ascii=False)

    content = (
        "// Bundle del codigo fuente Python de housing_generator, embebido para\n"
        "// Pyodide (generador real en el navegador). Regenerar con:\n"
        "//   python scripts/regenerar_bundle_pyodide.py\n"
        "// NO editar a mano -- se sobreescribe por completo en cada regeneracion.\n"
        f"const PY_BUNDLE = {bundle_json};\n"
    )
    PY_BUNDLE_JS.write_text(content, encoding="utf-8")

    print(f"Bundle regenerado: {len(bundle)} archivos, {len(bundle_json)} caracteres JSON.")
    print(f"Escrito en {PY_BUNDLE_JS}")


if __name__ == "__main__":
    main()
