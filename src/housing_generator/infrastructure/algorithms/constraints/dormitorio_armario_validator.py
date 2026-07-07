from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_fit_rectangle

# Espacio de armario empotrado por dormitorio -- CONFIRMADO por
# investigacion (condiciones minimas de habitabilidad, varias fuentes
# independientes), NO presente en nhv.lua. El espacio cuenta DENTRO de
# la superficie del propio dormitorio (no es un Room aparte):
#   - profundidad minima: 0.60 m
#   - altura minima: 2.20 m -- NO se duplica aqui: la altura general del
#     dormitorio ya la cubre `AlturaLibreValidator` sobre la misma
#     habitacion (el armario esta dentro de ella, no es un volumen aparte
#     con su propia altura independiente).
#   - largo minimo: 1.00 m si la habitacion es de mas de 6m2,
#                   1.50 m si la habitacion es de mas de 8m2
# El umbral exacto para habitaciones de <=6m2 no aparece en las fuentes
# consultadas; se usa 1.00 m como valor conservador por defecto, marcado
# como asuncion, no como cifra normativa confirmada.
ARMARIO_PROFUNDIDAD_MIN_M = 0.60
ARMARIO_LARGO_MIN_PEQUENO_M = 1.00
ARMARIO_LARGO_MIN_GRANDE_M = 1.50
ARMARIO_AREA_UMBRAL_GRANDE_M2 = 8.0


def armario_largo_minimo(area_m2: float) -> float:
    if area_m2 > ARMARIO_AREA_UMBRAL_GRANDE_M2:
        return ARMARIO_LARGO_MIN_GRANDE_M
    return ARMARIO_LARGO_MIN_PEQUENO_M  # incluye <=6m2 como asuncion conservadora


class DormitorioArmarioValidator(ConstraintValidatorPort):
    """Exige que cada dormitorio (BEDROOM, MASTER_BEDROOM) admita, dentro
    de su propia forma, un hueco de armario empotrado de
    `armario_largo_minimo(area) x ARMARIO_PROFUNDIDAD_MIN_M`.

    NO reserva ni resta esa superficie del dormitorio -- solo comprueba
    que la geometria de la habitacion sea capaz de alojarlo, igual que
    el cuadrado inscribible del salon. Misma logica de tres estados:
    violacion si no cabe, aviso si no se puede verificar (forma no
    rectangular), nada si no esta colocado todavia.

    La altura minima (2.20m) no se comprueba EN ESTE validador -- la
    cubre `AlturaLibreValidator` sobre la misma habitacion.
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
