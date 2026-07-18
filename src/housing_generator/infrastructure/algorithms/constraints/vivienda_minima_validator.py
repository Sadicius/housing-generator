from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# Programa minimo: Decreto 29/2010, I.A.2.3. Ver [ARCH:vivienda-minima].


class ViviendaMinimaValidator(ConstraintValidatorPort):
    """Comprueba que el Program contenga las seis piezas del programa
    mínimo legal: salón, cocina, baño completo, lavadero, tendedero y
    almacenamiento general. Ver [ARCH:vivienda-minima]."""

    _REQUIRED = [
        (
            RoomType.LIVING_ROOM,
            "un salón (LIVING_ROOM) -- una estancia de estar-comedor",
        ),
        (RoomType.KITCHEN, "una cocina (KITCHEN)"),
        (
            RoomType.BATHROOM,
            "un baño completo (BATHROOM) -- un aseo (TOILET) no sustituye este requisito",
        ),
        (RoomType.LAUNDRY, "un lavadero (LAUNDRY)"),
        (RoomType.DRYING_AREA, "un tendedero (DRYING_AREA)"),
        (RoomType.STORAGE, "un espacio de almacenamiento general (STORAGE)"),
    ]

    def validate(self, layout: Layout) -> ValidationResult:
        types_present = {r.room_type for r in layout.rooms}
        violations: List[str] = [
            f"Programa mínimo incompleto: falta {descripcion}"
            for room_type, descripcion in self._REQUIRED
            if room_type not in types_present
        ]
        return ValidationResult(violations=violations)
