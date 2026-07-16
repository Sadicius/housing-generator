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
        # se usa area_edificable_real (poligono real YA reducido por
        # retranqueo), no poligono_real en bruto -- corregido tras
        # revisar el propio diseno: si no se reduce aqui tambien, una
        # estancia podria quedar justo en el linde de propiedad,
        # ignorando el retranqueo para el caso de poligono real (el
        # rectangulo de trabajo SI lo aplica via buildable_area, esto
        # lo dejaba inconsistente). Ver [ARCH:parcela-real].
        area_edificable = layout.lot.area_edificable_real.polygon
        # mismo criterio de rendimiento ya aplicado en AdjacencyConstraintValidator:
        # el buffer se calcula UNA vez por validacion, no una vez por
        # estancia. Ver [ARCH:adjacency-validator].
        area_edificable_buffered = area_edificable.buffer(self._tolerance)

        for room in layout.rooms:
            if not room.is_placed:
                continue  # ya lo reporta AdjacencyConstraintValidator, no duplicar
            if not area_edificable_buffered.contains(room.boundary.polygon):
                sobresale = room.boundary.polygon.difference(area_edificable_buffered)
                violations.append(
                    f"La estancia '{room.id}' queda fuera del área edificable real de la parcela "
                    f"(sobresale {sobresale.area:.1f}m² del linde legal real, con retranqueo aplicado)"
                )

        return ValidationResult(violations=violations)
