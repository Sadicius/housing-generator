from typing import List, Optional
from shapely.geometry import Polygon
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# Ver [ARCH:escalera-alineacion].
ESCALERA_ALINEACION_MIN_OVERLAP_RATIO = 0.90


class EscaleraAlineacionValidator(ConstraintValidatorPort):
    """Exige que la huella de STAIRCASE en esta planta se solape
    sustancialmente (≥90%) con la huella ya resuelta de la planta de
    abajo. Ver [ARCH:escalera-alineacion]."""

    def __init__(
        self, reference_boundary: Optional[Polygon], floor_below_exists: bool = True
    ):
        self._reference = reference_boundary
        self._floor_below_exists = floor_below_exists

    def validate(self, layout: Layout) -> ValidationResult:
        staircases = [
            r for r in layout.rooms if r.room_type == RoomType.STAIRCASE and r.is_placed
        ]

        if not self._floor_below_exists:
            return (
                ValidationResult()
            )  # planta mas baja del edificio -- nada que alinear

        if self._reference is None:
            if staircases:
                return ValidationResult(
                    violations=[
                        "Esta planta declara escalera, pero la planta inferior no tiene ninguna "
                        "-- la escalera no arranca de ningun sitio"
                    ]
                )
            return (
                ValidationResult()
            )  # ninguna de las dos plantas tiene escalera -- correcto

        if not staircases:
            return ValidationResult(
                violations=[
                    "La planta inferior tiene escalera pero esta planta no declara ninguna "
                    "RoomType.STAIRCASE -- la escalera no puede quedar sin continuidad"
                ]
            )

        violations: List[str] = []
        for stair in staircases:
            intersection_area = stair.boundary.polygon.intersection(
                self._reference
            ).area
            smaller_area = min(stair.boundary.polygon.area, self._reference.area)
            ratio = intersection_area / smaller_area if smaller_area > 0 else 0.0
            if ratio < ESCALERA_ALINEACION_MIN_OVERLAP_RATIO:
                violations.append(
                    f"'{stair.id}': solapamiento con la escalera de la planta inferior de "
                    f"{ratio:.0%}, por debajo del minimo exigido "
                    f"({ESCALERA_ALINEACION_MIN_OVERLAP_RATIO:.0%})"
                )
        return ValidationResult(violations=violations)
