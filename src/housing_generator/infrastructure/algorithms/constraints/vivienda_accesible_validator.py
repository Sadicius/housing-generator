from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import (
    can_inscribe_square,
    evaluate_minimum_width,
)

# DB-SUA Anejo A + Base 5.4 Galicia, OPT-IN. Ver [ARCH:vivienda-accesible].
CIRCULO_GIRO_ACCESIBLE_M = 1.50  # DB-SUA Anejo A / Base 5.4
PASILLO_ACCESIBLE_ANCHO_M = 1.20  # Base 5.4 -- mas exigente que A.3.2.3

# Ver [ARCH:vivienda-accesible] para el criterio de esta lista.
TIPOS_CON_CIRCULO_GIRO = {
    RoomType.LIVING_ROOM,
    RoomType.DINING_ROOM,
    RoomType.BEDROOM,
    RoomType.MASTER_BEDROOM,
    RoomType.KITCHEN,
    RoomType.BATHROOM,
}


class ViviendaAccesibleValidator(ConstraintValidatorPort):
    """Vivienda declarada accesible (DB-SUA Anejo A + Base 5.4 Galicia)
    -- solo activo con `activo=True`. Exige círculo de giro Ø1.50m en
    estancias habitables + baño, y pasillo ≥1.20m (además del mínimo
    general, no lo sustituye). Ver [ARCH:vivienda-accesible]."""

    def __init__(self, activo: bool = False):
        self.activo = activo

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        if not self.activo:
            return ValidationResult(violations=violations, warnings=warnings)

        for room in layout.rooms:
            if not room.is_placed:
                continue

            if room.room_type in TIPOS_CON_CIRCULO_GIRO:
                cumple = can_inscribe_square(
                    room.boundary.polygon, CIRCULO_GIRO_ACCESIBLE_M
                )
                if cumple is False:
                    violations.append(
                        f"'{room.id}': vivienda accesible, no admite el circulo de giro "
                        f"de Ø{CIRCULO_GIRO_ACCESIBLE_M:.2f}m exigido (DB-SUA/Base 5.4)"
                    )
                elif cumple is None:
                    warnings.append(
                        f"'{room.id}': forma no rectangular, no se puede verificar el "
                        f"circulo de giro de vivienda accesible"
                    )

            if room.room_type == RoomType.CORRIDOR:
                v, w = evaluate_minimum_width(
                    room.id,
                    room.boundary.polygon,
                    PASILLO_ACCESIBLE_ANCHO_M,
                    violation_message=(
                        f"ancho libre por debajo del minimo de vivienda accesible "
                        f"({PASILLO_ACCESIBLE_ANCHO_M:.2f}m, Base 5.4 -- mas exigente que "
                        f"el general de A.3.2.3)"
                    ),
                    warning_message="forma no rectangular, no se puede verificar el ancho de pasillo accesible",
                )
                violations.extend(v)
                warnings.extend(w)

        return ValidationResult(violations=violations, warnings=warnings)
