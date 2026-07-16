"""Comprueba que cada estancia colocada quede DENTRO del polígono
REAL de la parcela (`Lot.poligono_real`, importado de Catastro) --
no solo dentro del rectángulo de trabajo simplificado
(`Lot.boundary`), que puede sobresalir del polígono real hasta un
12-22% en las esquinas (confirmado con 2 parcelas reales de Galicia
durante la investigación).

Sin esto, una vivienda generada podría colocar estancias fuera del
linde legal real de la parcela -- hallazgo real, señalado por el
usuario tras revisar la Zona 0 en un navegador de verdad.

Si `Lot.poligono_real` es `None` (caso manual, sin importar de
Catastro), este validador no hace nada -- mismo convenio que el
resto de campos opcionales. Ver [ARCH:parcela-real].
"""
from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout


class ParcelaRealValidator(ConstraintValidatorPort):
    """Restricción dura: toda estancia debe caer dentro del polígono
    real de la parcela (`Lot.poligono_real`), no solo dentro del
    rectángulo de trabajo simplificado. Ver [ARCH:parcela-real]."""

    def __init__(self, touch_tolerance_m: float = 0.05):
        self._tolerance = touch_tolerance_m

    def validate(self, layout: Layout) -> ValidationResult:
        if layout.lot.poligono_real is None:
            return ValidationResult(violations=[])

        violations: List[str] = []
        # mismo criterio de rendimiento ya aplicado en AdjacencyConstraintValidator:
        # el buffer se calcula UNA vez por validacion, no una vez por
        # estancia. Ver [ARCH:adjacency-validator].
        poligono_real_buffered = layout.lot.poligono_real.buffer(self._tolerance)

        for room in layout.rooms:
            if not room.is_placed:
                continue  # ya lo reporta AdjacencyConstraintValidator, no duplicar
            if not poligono_real_buffered.contains(room.boundary.polygon):
                sobresale = room.boundary.polygon.difference(poligono_real_buffered)
                violations.append(
                    f"La estancia '{room.id}' queda fuera del polígono real de la parcela "
                    f"(sobresale {sobresale.area:.1f}m² del linde legal real)"
                )

        return ValidationResult(violations=violations)
