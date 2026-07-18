from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# A.3.1.1: altura libre minima. Ver [ARCH:altura-libre].
ALTURA_LIBRE_MIN_M = 2.50
ALTURA_LIBRE_REDUCIDA_M = 2.20

ROOM_TYPES_REDUCCION_DIRECTA = {
    RoomType.ENTRANCE_HALL,  # vestibulo
    RoomType.CORRIDOR,  # pasillo
    RoomType.STAIRCASE,  # escaleras
    RoomType.BATHROOM,  # bano
    RoomType.TOILET,  # aseo
    RoomType.LAUNDRY,  # lavadero
    RoomType.DRYING_AREA,  # tendedero
    RoomType.GARAGE,  # garajes de viviendas unifamiliares
}
ROOM_TYPES_FUERA_DE_ALCANCE = {RoomType.TECHNICAL_ROOM}


class AlturaLibreValidator(ConstraintValidatorPort):
    """Valida `Room.dimensions.ceiling_height_m` contra A.3.1.1. Sin
    altura declarada: aviso. Piezas de reducción directa: violación
    solo si < 2.20m. Resto: violación si < 2.20m, aviso si 2.20-2.50m
    (posible excepción del 30%, no verificable). Ver [ARCH:altura-libre].
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type in ROOM_TYPES_FUERA_DE_ALCANCE:
                continue

            altura = room.dimensions.ceiling_height_m
            if altura is None:
                warnings.append(
                    f"'{room.id}': altura de techo no declarada, no se puede verificar A.3.1.1"
                )
                continue

            if room.room_type in ROOM_TYPES_REDUCCION_DIRECTA:
                if altura < ALTURA_LIBRE_REDUCIDA_M:
                    violations.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo del minimo "
                        f"reducido de A.3.1.1.b ({ALTURA_LIBRE_REDUCIDA_M:.2f}m)"
                    )
            else:
                if altura < ALTURA_LIBRE_REDUCIDA_M:
                    violations.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo incluso del "
                        f"minimo reducido de A.3.1.1 ({ALTURA_LIBRE_REDUCIDA_M:.2f}m)"
                    )
                elif altura < ALTURA_LIBRE_MIN_M:
                    warnings.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo de "
                        f"{ALTURA_LIBRE_MIN_M:.2f}m -- podria cumplir via la excepcion del "
                        f"30% de superficie (A.3.1.1.c), no verificable sin geometria parcial"
                    )

        return ValidationResult(violations=violations, warnings=warnings)
