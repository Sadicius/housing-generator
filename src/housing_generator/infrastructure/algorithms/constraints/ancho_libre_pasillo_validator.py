from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import (
    evaluate_minimum_width,
)

# A.3.2.3: pasillos rectangulares (particion guillotina), ancho
# uniforme -- se aplica el minimo de todo el recorrido (1.00m), no el
# de estrechamiento puntual (0.90m).
ANCHO_LIBRE_PASILLO_M = 1.00


class AnchoLibrePasilloValidator(ConstraintValidatorPort):
    """A.3.2.3: ancho libre de cada CORRIDOR ≥ 1.00m."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type != RoomType.CORRIDOR or not room.is_placed:
                continue
            v, w = evaluate_minimum_width(
                room.id,
                room.boundary.polygon,
                ANCHO_LIBRE_PASILLO_M,
                violation_message=f"ancho libre por debajo del minimo de A.3.2.3 ({ANCHO_LIBRE_PASILLO_M:.2f}m)",
                warning_message="forma no rectangular, no se puede verificar el ancho libre de pasillo (A.3.2.3)",
            )
            violations.extend(v)
            warnings.extend(w)

        return ValidationResult(violations=violations, warnings=warnings)
