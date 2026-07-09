from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import evaluate_minimum_width

# CTE DB-SUA 1, escalera de USO RESTRINGIDO (interior de vivienda
# unifamiliar -- confirmado por investigacion independiente en
# docs/niveles_plantas.md: "la escalera interior de un alojamiento...
# se considera de uso restringido cualquiera que sea el numero de
# usuarios"). Ancho minimo 0.80m -- NO el de uso general (1.00-1.20m,
# zonas comunes de edificio), que no aplica a este caso.
ESCALERA_ANCHO_LIBRE_MIN_M = 0.80


class EscaleraAnchoLibreValidator(ConstraintValidatorPort):
    """Ancho libre minimo de RoomType.STAIRCASE (0.80m, uso restringido
    CTE DB-SUA 1). No comprueba huella/contrahuella de peldanos
    (geometria de escalon, fuera de alcance -- ver niveles_plantas.md)
    ni alineacion entre plantas (ver EscaleraAlineacionValidator, aparte)."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []
        for room in layout.rooms:
            if room.room_type != RoomType.STAIRCASE or not room.is_placed:
                continue
            v, w = evaluate_minimum_width(
                room.id, room.boundary.polygon, ESCALERA_ANCHO_LIBRE_MIN_M,
                violation_message=(
                    f"ancho libre por debajo del minimo de escalera de uso "
                    f"restringido ({ESCALERA_ANCHO_LIBRE_MIN_M:.2f}m, CTE DB-SUA 1)"
                ),
                warning_message="forma no rectangular, no se puede verificar el ancho libre de escalera",
            )
            violations.extend(v)
            warnings.extend(w)
        return ValidationResult(violations=violations, warnings=warnings)
