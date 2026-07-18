"""Fitness function (Neal Ford / Rebecca Parsons, "Building Evolutionary
Architectures"): comprobación automática y continua de que una
característica arquitectónica se sigue cumpliendo, no solo que quedó
documentada una vez.

Retomado de investigar el proyecto "architecture-decision-record" y el
concepto de fitness functions a petición del usuario -- el hueco real
que esto cierra: `vulture` (detector de código muerto) solo se había
ejecutado a mano, cuando alguien lo pidió explícitamente. Así fue como
`infrastructure/browser_bridge.py` (78 líneas, un archivo completo
huérfano) sobrevivió sin que nadie lo notara durante varias rondas de
refactorización, hasta una auditoría manual ocasional. Este test hace
esa misma comprobación en cada pase de la suite -- el próximo archivo
huérfano se detecta solo, no por casualidad.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_no_new_dead_code():
    """Ejecuta vulture contra src/ con la lista blanca ya confirmada
    (vulture_whitelist.py) -- cualquier hallazgo nuevo, no revisado
    todavía, hace fallar este test. Si el hallazgo es legítimo (una
    pieza intencionada, como ya pasó con las alternativas de
    arquitectura hexagonal), añadir la línea correspondiente a
    vulture_whitelist.py tras revisarla, no ignorar el test."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vulture",
            str(ROOT / "src"),
            str(ROOT / "vulture_whitelist.py"),
            "--min-confidence",
            "60",
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )

    assert result.returncode == 0, (
        "vulture encontró código potencialmente muerto sin revisar:\n\n"
        f"{result.stdout}\n"
        "Si es un hallazgo legítimo (código realmente sin usar), elimínalo. "
        "Si es una pieza intencionada (ver ejemplos en vulture_whitelist.py -- "
        "arquitectura alternativa con tests propios, API usada solo en tests/, "
        "decisión de diseño deliberada, llamada dinámica desde JS), añádela a "
        "vulture_whitelist.py con un comentario explicando por qué, no la ignores "
        "sin más."
    )
