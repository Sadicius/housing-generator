from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_inscribe_square

# Espacio de acceso interior, cuadrado 1.50m. Ver [ARCH:espacio-acceso].
ESPACIO_ACCESO_CUADRADO_M = 1.50


class EspacioAccesoValidator(ConstraintValidatorPort):
    """Cuadrado inscribible de 1.50m en el recibidor (ENTRANCE_HALL).
    Sin ENTRANCE_HALL en el programa, no aplica. Ver
    [ARCH:espacio-acceso]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type != RoomType.ENTRANCE_HALL:
                continue
            if not room.is_placed:
                continue

            cumple = can_inscribe_square(room.boundary.polygon, ESPACIO_ACCESO_CUADRADO_M)
            if cumple is False:
                violations.append(
                    f"'{room.id}': no admite el cuadrado de {ESPACIO_ACCESO_CUADRADO_M:.2f}m "
                    f"de lado exigido en el espacio de acceso interior"
                )
            elif cumple is None:
                warnings.append(
                    f"'{room.id}': forma no rectangular, no se puede verificar el cuadrado "
                    f"de acceso interior de {ESPACIO_ACCESO_CUADRADO_M:.2f}m"
                )

        return ValidationResult(violations=violations, warnings=warnings)
