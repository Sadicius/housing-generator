#!/bin/bash
# Instala el entorno de Python para el CLI de housing_generator --
# NO hace falta para usar el dashboard (docs/visualizador/
# relaciones_espaciales.html), que no necesita instalar nada. Esto es
# solo para desarrollo o uso del CLI (python -m housing_generator...).
#
# Uso:
#   bash instalar.sh
#   (o: chmod +x instalar.sh && ./instalar.sh)
#
# Idempotente: si .venv ya existe, no lo recrea, solo reinstala/
# actualiza las dependencias.

set -e
cd "$(dirname "$0")"

echo "housing_generator -- instalando entorno de Python..."
echo ""

PYTHON_BIN=""
for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1; then
        PYTHON_BIN="$candidato"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "ERROR: no se encontro python3 ni python en el PATH."
    echo "Instala Python 3.10 o superior antes de continuar: https://www.python.org/downloads/"
    exit 1
fi

echo "Python encontrado: $($PYTHON_BIN --version)"

if [ ! -d ".venv" ]; then
    echo "Creando entorno virtual en .venv/ ..."
    "$PYTHON_BIN" -m venv .venv
else
    echo ".venv/ ya existe, reutilizando."
fi

echo "Instalando dependencias (esto puede tardar un minuto)..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e ".[dev]"

echo ""
echo "Listo. Dos formas de usar el CLI a partir de ahora:"
echo ""
echo "  1) Activar el entorno en esta terminal (recomendado si vas a usarlo varias veces):"
echo "       source .venv/bin/activate"
echo "       python -m housing_generator.interface.cli.main --output layout.json"
echo ""
echo "  2) O llamarlo directamente, sin activar nada:"
echo "       .venv/bin/python -m housing_generator.interface.cli.main --output layout.json"
echo ""
echo "Para ejecutar los tests: .venv/bin/pytest -v"
echo ""
echo "Recuerda: el dashboard (INICIO.html) no necesita nada de esto -- se abre directamente."
