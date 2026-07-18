from typing import List
from shapely.geometry import Polygon
from shapely.ops import unary_union
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# Continuidad de bajantes. Ver [ARCH:nucleo-humedo-vertical].


class NucleoHumedoVerticalValidator(ConstraintValidatorPort):
    """Cada estancia húmeda debe solapar en planta con alguna húmeda
    de la planta inmediatamente inferior. Sin referencia, no aplica.
    Ver [ARCH:nucleo-humedo-vertical]."""

    def __init__(self, reference_wet_boundaries: List[Polygon]):
        self._reference_union = (
            unary_union(reference_wet_boundaries) if reference_wet_boundaries else None
        )

    def validate(self, layout: Layout) -> ValidationResult:
        if self._reference_union is None:
            return ValidationResult()

        wet_rooms = [r for r in layout.rooms if r.is_wet and r.is_placed]
        violations: List[str] = []
        for room in wet_rooms:
            overlap = room.boundary.polygon.intersection(self._reference_union).area
            if overlap <= 0:
                violations.append(
                    f"'{room.id}': sin solape en planta con ninguna estancia humeda de la "
                    f"planta inferior -- continuidad de bajantes rota"
                )
        return ValidationResult(violations=violations)
