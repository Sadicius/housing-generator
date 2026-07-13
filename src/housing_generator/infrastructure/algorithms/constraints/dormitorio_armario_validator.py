from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_fit_rectangle

# Espacio de armario empotrado, confirmado por investigacion, no en
# nhv.lua. Ver [ARCH:dormitorio-armario].
ARMARIO_PROFUNDIDAD_MIN_M = 0.60
ARMARIO_LARGO_MIN_PEQUENO_M = 1.00
ARMARIO_LARGO_MIN_GRANDE_M = 1.50
ARMARIO_AREA_UMBRAL_GRANDE_M2 = 8.0


def armario_largo_minimo(area_m2: float) -> float:
    if area_m2 > ARMARIO_AREA_UMBRAL_GRANDE_M2:
        return ARMARIO_LARGO_MIN_GRANDE_M
    return ARMARIO_LARGO_MIN_PEQUENO_M  # incluye <=6m2 como asuncion conservadora


class DormitorioArmarioValidator(ConstraintValidatorPort):
    """Exige que cada dormitorio admita, dentro de su propia forma, un
    hueco de armario empotrado. No reserva esa superficie -- solo
    comprueba que la geometría sea capaz de alojarlo. Ver
    [ARCH:dormitorio-armario].
    """

    ROOM_TYPES = {RoomType.BEDROOM, RoomType.MASTER_BEDROOM}

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type not in self.ROOM_TYPES or not room.is_placed:
                continue

            largo = armario_largo_minimo(room.dimensions.area_m2)
            cabe = can_fit_rectangle(room.boundary.polygon, largo, ARMARIO_PROFUNDIDAD_MIN_M)

            if cabe is False:
                violations.append(
                    f"'{room.id}': no admite el hueco de armario empotrado minimo "
                    f"({largo:.2f}m x {ARMARIO_PROFUNDIDAD_MIN_M:.2f}m) dentro de su "
                    f"propia forma"
                )
            elif cabe is None:
                warnings.append(
                    f"'{room.id}': forma no rectangular, no se puede verificar el "
                    f"hueco de armario empotrado"
                )

        return ValidationResult(violations=violations, warnings=warnings)
