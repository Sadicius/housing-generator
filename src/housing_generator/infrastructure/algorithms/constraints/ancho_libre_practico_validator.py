from typing import List, Set
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import evaluate_minimum_width

# NO NORMATIVO -- criterio de ingenieria practica, confirmado
# explicitamente con el usuario. Ver [ARCH:ancho-libre-practico].
ANCHO_LIBRE_PRACTICO_M = 1.20

TIPOS_SIN_ANCHO_NORMATIVO: Set[RoomType] = {
    RoomType.DINING_ROOM,
    RoomType.STUDY,
    RoomType.TOILET,
    RoomType.LAUNDRY,
    RoomType.DRYING_AREA,
    RoomType.STORAGE,
    RoomType.ENTRANCE_HALL,
    RoomType.GARAGE,
    RoomType.TECHNICAL_ROOM,
}


class AnchoLibrePracticoValidator(ConstraintValidatorPort):
    """Ancho libre mínimo NO normativo (1.20m) para tipos que el
    decreto deja sin ancho libre especificado -- evita formas
    técnicamente conformes en área pero inservibles en la práctica.
    Ver [ARCH:ancho-libre-practico]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type not in TIPOS_SIN_ANCHO_NORMATIVO or not room.is_placed:
                continue
            v, w = evaluate_minimum_width(
                room.id, room.boundary.polygon, ANCHO_LIBRE_PRACTICO_M,
                violation_message=(
                    f"ancho libre por debajo del minimo practico de ingenieria "
                    f"({ANCHO_LIBRE_PRACTICO_M:.2f}m, NO normativo -- el Decreto 29/2010 "
                    f"no especifica ancho libre para este tipo, pero una estancia mas "
                    f"estrecha que esto no es utilizable en la practica)"
                ),
                warning_message="forma no rectangular, no se puede verificar el ancho libre práctico",
            )
            violations.extend(v)
            warnings.extend(w)

        return ValidationResult(violations=violations, warnings=warnings)
