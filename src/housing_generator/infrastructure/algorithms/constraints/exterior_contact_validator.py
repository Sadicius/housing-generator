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
    `room.min_exterior_sides` lados con contacto real al límite del
    solar. Ver [ARCH:exterior-contact]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        # borde del area edificable, no de la parcela legal completa.
        # Ver [ARCH:exterior-contact].
        lot_polygon = layout.lot.buildable_area.polygon
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
