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

    `floor_below_exists=False`: no hay ninguna planta inferior en el
    edificio (esta es la planta mas baja) -- no aplica en absoluto, no
    hay nada con lo que alinear.

    `floor_below_exists=True, reference_boundary=None`: SI hay planta
    inferior, pero esa planta NO declara ninguna escalera -- si ESTA
    planta si tiene una, es una escalera que no arranca de ningun sitio
    (violacion). Bug real encontrado en auditoria: antes, este caso se
    trataba igual que "no hay planta inferior" (mismo `None`), dejando
    pasar sin deteccion una escalera que no conecta con la planta de
    abajo. Confirmado con test que reproduce el caso exacto antes de
    corregirlo."""

    def __init__(self, reference_boundary: Optional[Polygon], floor_below_exists: bool = True):
        self._reference = reference_boundary
        self._floor_below_exists = floor_below_exists

    def validate(self, layout: Layout) -> ValidationResult:
        staircases = [r for r in layout.rooms if r.room_type == RoomType.STAIRCASE and r.is_placed]

        if not self._floor_below_exists:
            return ValidationResult()  # planta mas baja del edificio -- nada que alinear

        if self._reference is None:
            if staircases:
                return ValidationResult(violations=[
                    "Esta planta declara escalera, pero la planta inferior no tiene ninguna "
                    "-- la escalera no arranca de ningun sitio"
                ])
            return ValidationResult()  # ninguna de las dos plantas tiene escalera -- correcto

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
