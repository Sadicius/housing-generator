from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# NO NORMATIVO -- criterio de diseno confirmado explicitamente, no del
# Decreto 29/2010. Ver [ARCH:proporcion-maxima].
PROPORCION_MAXIMA = 2.5


class ProporcionMaximaValidator(ConstraintValidatorPort):
    """Proporción ancho:alto máxima NO normativa (2.5:1) para
    CUALQUIER estancia -- red de seguridad general contra tiras finas
    que cumplen el ancho mínimo pero son absurdas en proporción. Ver
    [ARCH:proporcion-maxima]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if not room.is_placed:
                continue
            bounds = room.boundary.polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            if width <= 0 or height <= 0:
                continue
            ratio = max(width, height) / min(width, height)
            if ratio > PROPORCION_MAXIMA:
                violations.append(
                    f"'{room.id}': proporcion {ratio:.1f}:1 ({width:.2f}m x {height:.2f}m) por encima "
                    f"del maximo practico de {PROPORCION_MAXIMA:.1f}:1 (NO normativo -- criterio de "
                    f"ingenieria confirmado, evita formas alargadas absurdas)"
                )

        return ValidationResult(violations=violations, warnings=warnings)
