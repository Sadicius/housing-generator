from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import evaluate_minimum_width

# B.2.5 (trastero): superficie minima FIJA, no escala con el numero de
# estancias -- a diferencia de "almacenamiento" (Tabla 2). Confirmado en
# nhv.lua (NHV.trastero.area = 4.00), con la propia fuente admitiendo que
# esta regla nunca estuvo realmente implementada pese a estar declarada.
TRASTERO_AREA_MIN_M2 = 4.00
TRASTERO_ANCHO_LIBRE_MIN_M = 1.60

# Ancho de puerta (0.80m) sigue pendiente -- requiere modelar puertas/
# accesos, que este proyecto no modela todavia (mismo hueco identificado
# en relaciones_espaciales.md: "acceso/puertas").


class TrasteroMinimumAreaValidator(ConstraintValidatorPort):
    """B.2.5: superficie minima fija Y ancho libre minimo para trasteros
    (RoomType.STORAGE_ROOM). Distinto de ServicioMinimumAreaValidator
    (Tabla 2), que cubre "almacenamiento" (RoomType.STORAGE) con un
    minimo que SI escala con el numero de estancias.

    El ancho de puerta (0.80m, tambien en B.2.5) NO se comprueba aqui --
    requiere modelar puertas/accesos, pendiente en todo el proyecto.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []
        for room in layout.rooms:
            if room.room_type != RoomType.STORAGE_ROOM:
                continue
            if room.dimensions.area_m2 < TRASTERO_AREA_MIN_M2:
                violations.append(
                    f"'{room.id}': {room.dimensions.area_m2:.1f}m2, por debajo del minimo "
                    f"fijo de B.2.5 para trasteros ({TRASTERO_AREA_MIN_M2:.1f}m2)"
                )
            if room.is_placed:
                v, w = evaluate_minimum_width(
                    room.id, room.boundary.polygon, TRASTERO_ANCHO_LIBRE_MIN_M,
                    violation_message=(
                        f"ancho libre por debajo del minimo de B.2.5 ({TRASTERO_ANCHO_LIBRE_MIN_M:.2f}m)"
                    ),
                    warning_message="forma no rectangular, no se puede verificar el ancho libre de trastero (B.2.5)",
                )
                violations.extend(v)
                warnings.extend(w)
        return ValidationResult(violations=violations, warnings=warnings)
