from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.infrastructure.geometry.shapely_utils import count_exterior_sides

# Umbral de contacto con el exterior (0.3m) -- distinto y mayor que el
# umbral de adyacencia interior entre estancias (0.1m), confirmado por
# el usuario en la sesion de nucleo humedo/grafo de adyacencia.
EXTERIOR_MIN_CONTACT_M = 0.3


class ExteriorContactValidator(ConstraintValidatorPort):
    """Comprueba que cada estancia tenga al menos
    `room.min_exterior_sides` lados con contacto real al limite del
    solar (ver DEFAULT_MIN_EXTERIOR_SIDES en enums.py para el porque de
    cada valor por tipo).

    Misma logica de tres estados que el resto de validadores
    geometricos: violacion si no llega al minimo, aviso si la forma no
    es rectangular (no verificable), nada si la estancia no esta
    colocada todavia.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        # borde del AREA EDIFICABLE, no de la parcela legal completa --
        # con retranqueo declarado (vivienda aislada), la construccion
        # nunca llega a tocar la linea de parcela real, asi que
        # comprobar contra ella nunca daria contacto exterior valido.
        # El borde del area edificable es donde de verdad termina la
        # construccion y empieza el jardin/exterior. Sin retranqueo,
        # ambas coinciden (mismo comportamiento que antes).
        lot_polygon = layout.lot.buildable_area.polygon

        # vivienda pareada/adosada (retomado de docs/CONTINUIDAD.md):
        # los lados de medianera SI forman parte del area edificable
        # (la construccion llega hasta el linde ahi), pero una pared de
        # medianera no tiene luz ni ventilacion propia -- no cuenta como
        # contacto exterior real aunque geometricamente toque el borde.
        excluded_segments = layout.lot.medianera_boundary_segments()

        for room in layout.rooms:
            if not room.is_placed or room.min_exterior_sides <= 0:
                continue

            lados = count_exterior_sides(
                room.boundary.polygon, lot_polygon, EXTERIOR_MIN_CONTACT_M,
                excluded_segments=excluded_segments,
            )

            if lados is None:
                warnings.append(
                    f"'{room.id}': forma no rectangular, no se puede verificar el "
                    f"contacto exterior"
                )
            elif lados < room.min_exterior_sides:
                violations.append(
                    f"'{room.id}': {lados} lado(s) con contacto exterior, "
                    f"por debajo del minimo exigido ({room.min_exterior_sides})"
                )

        return ValidationResult(violations=violations, warnings=warnings)
