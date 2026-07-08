from typing import List, Optional
from shapely.geometry import Polygon
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# Confirmado por investigacion externa (Infinigen Indoors, 2024, apendice
# D.5 "Adding staircases"): "we compute the intersection of the space
# assigned as staircase rooms on consecutive floors... rejected when the
# consecutive staircase [does not] intersect [sufficiently]". Aqui se
# adapta a nuestra arquitectura (arbol de particion por planta, generado
# de forma independiente, no busqueda conjunta): en vez de un "hueco"
# compartido durante la busqueda, la planta de ABAJO se genera primero y
# su escalera ya resuelta se pasa como referencia FIJA a este validador
# al generar la planta de ARRIBA -- la alineacion se convierte asi en
# una restriccion dura mas dentro del mismo mecanismo de recocido
# simulado ya existente, sin necesitar un tipo de movimiento nuevo.
ESCALERA_ALINEACION_MIN_OVERLAP_RATIO = 0.90


class EscaleraAlineacionValidator(ConstraintValidatorPort):
    """Exige que la huella de RoomType.STAIRCASE en esta planta se solape
    sustancialmente (>=90% del area de la mas pequena de las dos) con la
    huella YA RESUELTA de la escalera en la planta de abajo.

    `reference_boundary=None` significa "no hay escalera que alinear en
    la planta de abajo" (planta base del edificio, o esa planta no tiene
    escalera) -- en ese caso este validador no aplica en absoluto."""

    def __init__(self, reference_boundary: Optional[Polygon]):
        self._reference = reference_boundary

    def validate(self, layout: Layout) -> ValidationResult:
        staircases = [r for r in layout.rooms if r.room_type == RoomType.STAIRCASE and r.is_placed]

        if self._reference is None:
            return ValidationResult()  # nada que alinear en esta pareja de plantas

        if not staircases:
            return ValidationResult(violations=[
                "La planta inferior tiene escalera pero esta planta no declara ninguna "
                "RoomType.STAIRCASE -- la escalera no puede quedar sin continuidad"
            ])

        violations: List[str] = []
        for stair in staircases:
            intersection_area = stair.boundary.polygon.intersection(self._reference).area
            smaller_area = min(stair.boundary.polygon.area, self._reference.area)
            ratio = intersection_area / smaller_area if smaller_area > 0 else 0.0
            if ratio < ESCALERA_ALINEACION_MIN_OVERLAP_RATIO:
                violations.append(
                    f"'{stair.id}': solapamiento con la escalera de la planta inferior de "
                    f"{ratio:.0%}, por debajo del minimo exigido "
                    f"({ESCALERA_ALINEACION_MIN_OVERLAP_RATIO:.0%})"
                )
        return ValidationResult(violations=violations)
