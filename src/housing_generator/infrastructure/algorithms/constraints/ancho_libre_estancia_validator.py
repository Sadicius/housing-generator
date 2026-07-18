from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import meets_minimum_width

# A.3.2.1: ancho libre minimo. Ver [ARCH:ancho-libre-estancia].
ANCHO_LIBRE_ESTANCIA_MAYOR_M = 2.70
ANCHO_LIBRE_DORMITORIO_DOBLE_M = 2.60  # habitacion >= 12m2
ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M = 2.00  # habitacion < 12m2
ANCHO_LIBRE_COCINA_M = 1.80
ANCHO_LIBRE_BANO_M = 1.60
DORMITORIO_DOBLE_AREA_UMBRAL_M2 = 12.0

_DORMITORIO_TYPES = {RoomType.BEDROOM, RoomType.MASTER_BEDROOM}


class AnchoLibreEstanciaValidator(ConstraintValidatorPort):
    """A.3.2.1: ancho libre mínimo para estancia mayor, dormitorios,
    cocina y baño. Ver [ARCH:ancho-libre-estancia]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        placed_rooms = [r for r in layout.rooms if r.is_placed]

        mayor = next(
            (r for r in placed_rooms if r.room_type == RoomType.LIVING_ROOM), None
        )
        if mayor is not None:
            self._check(
                mayor,
                ANCHO_LIBRE_ESTANCIA_MAYOR_M,
                "estancia mayor (A.3.2.1.a)",
                violations,
                warnings,
            )

        for room in placed_rooms:
            if room.room_type in _DORMITORIO_TYPES:
                if room.dimensions.area_m2 >= DORMITORIO_DOBLE_AREA_UMBRAL_M2:
                    minimo, etiqueta = (
                        ANCHO_LIBRE_DORMITORIO_DOBLE_M,
                        "dormitorio doble (A.3.2.1.e/f)",
                    )
                else:
                    minimo, etiqueta = (
                        ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M,
                        "dormitorio individual (A.3.2.1.g/h)",
                    )
                self._check(room, minimo, etiqueta, violations, warnings)
            elif room.room_type == RoomType.KITCHEN:
                self._check(
                    room, ANCHO_LIBRE_COCINA_M, "cocina (A.3.2.1)", violations, warnings
                )
            elif room.room_type == RoomType.BATHROOM:
                self._check(
                    room, ANCHO_LIBRE_BANO_M, "bano (A.3.2.1)", violations, warnings
                )

        return ValidationResult(violations=violations, warnings=warnings)

    @staticmethod
    def _check(
        room, minimo: float, etiqueta: str, violations: List[str], warnings: List[str]
    ) -> None:
        cumple = meets_minimum_width(room.boundary.polygon, minimo)
        if cumple is False:
            violations.append(
                f"'{room.id}' ({etiqueta}): ancho libre por debajo del minimo de {minimo:.2f}m"
            )
        elif cumple is None:
            warnings.append(
                f"'{room.id}' ({etiqueta}): forma no rectangular, no se puede verificar "
                f"el ancho libre de {minimo:.2f}m"
            )
