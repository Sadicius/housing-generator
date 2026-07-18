from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# Tolerancia de solape (m2) -- NO normativa, decision de ingenieria para
# absorber imprecision geometrica de punto flotante entre poligonos que
# deberian ser exactamente adyacentes. Mismo trato que EXTERIOR_MIN_CONTACT_M
# en exterior_contact_validator.py: umbral de ingenieria, no cifra normativa.
ROOM_OVERLAP_TOLERANCE_M2 = 1e-4


class RoomOverlapValidator(ConstraintValidatorPort):
    """Comprueba que ninguna pareja de estancias colocadas se solape en
    area. Hoy esta garantia la da gratis el algoritmo de contorno de
    BTreeLayoutGenerator (compute_positions nunca invade lo ya ocupado),
    pero deja de ser automatica en cuanto la generacion se separe en
    fases independientes (p.ej. tallado perimetral + empaquetado de
    nucleo) -- ver docs/referencia/generador/contacto-exterior-y-envolvente.md.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []

        placed = [room for room in layout.rooms if room.is_placed]
        for i, room_a in enumerate(placed):
            for room_b in placed[i + 1 :]:
                overlap_area = room_a.boundary.polygon.intersection(
                    room_b.boundary.polygon
                ).area
                if overlap_area > ROOM_OVERLAP_TOLERANCE_M2:
                    violations.append(
                        f"'{room_a.id}' y '{room_b.id}' se solapan en "
                        f"{overlap_area:.2f} m2"
                    )

        return ValidationResult(violations=violations)
