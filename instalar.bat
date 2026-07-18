@echo off
REM Instala el entorno de Python para el CLI de housing_generator --
REM NO hace falta para usar el dashboard (html\relaciones_espaciales.html),
REM que no necesita instalar nada. Esto es solo para desarrollo o uso del CLI.
REM
REM Uso: doble clic sobre este archivo, o "instalar.bat" desde cmd.
REM
REM Idempotente: si .venv ya existe, no lo recrea, solo reinstala/
REM actualiza las dependencias.

cd /d "%~dp0"

echo housing_generator -- instalando entorno de Python...
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: no se encontro "python" en el PATH.
    echo Instala Python 3.10 o superior antes de continuar: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version

if not exist ".venv" (
    echo Creando entorno virtual en .venv\ ...
    python -m venv .venv
) else (
    echo .venv\ ya existe, reutilizando.
)

echo Instalando dependencias ^(esto puede tardar un minuto^)...
.venv\Scripts\pip install --quiet --upgrade pip
.venv\Scripts\pip install --quiet -e ".[dev]"

echo.
echo Listo. Dos formas de usar el CLI a partir de ahora:
echo.
echo   1^) Activar el entorno en esta terminal ^(recomendado si vas a usarlo varias veces^):
echo        .venv\Scripts\activate
echo        python -m housing_generator.interface.cli.main --output layout.json
echo.
echo   2^) O llamarlo directamente, sin activar nada:
echo        .venv\Scripts\python -m housing_generator.interface.cli.main --output layout.json
echo.
echo Para ejecutar los tests: .venv\Scripts\pytest -v
echo.
echo Recuerda: el dashboard ^(INICIO.html^) no necesita nada de esto -- se abre directamente.
pause
