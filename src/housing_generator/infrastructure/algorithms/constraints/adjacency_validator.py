from typing import List, Optional
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import AdjacencyStrength

# Longitud minima de borde compartido para "unidas por un lado" (no
# solo esquina) -- lo bastante para que quepa una puerta.
MUST_BE_NEAR_MIN_SHARED_LENGTH_M = 1.0


class AdjacencyConstraintValidator(ConstraintValidatorPort):
    """Comprueba restricciones duras:
    - toda estancia debe estar colocada
    - el limite del solar debe contener cada estancia
    - las estancias marcadas MUST_BE_AWAY no deben tocarse
    - las estancias marcadas MUST_BE_NEAR deben compartir un borde de al
      menos MUST_BE_NEAR_MIN_SHARED_LENGTH_M (no basta con tocarse en un
      punto o un tramo muy corto)
    """

    def __init__(self, adjacency_requirements: Optional[list] = None, touch_tolerance_m: float = 0.05):
        self._requirements = adjacency_requirements or []
        self._tolerance = touch_tolerance_m

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []

        # layout.lot no cambia entre iteraciones del recocido -- calcular
        # el buffer UNA vez por validacion, no una vez POR ESTANCIA (bug
        # de rendimiento real, encontrado con cProfile: 2748 llamadas a
        # .buffer() para 458 evaluaciones en una prueba de 6 estancias,
        # exactamente 6x mas de lo necesario). Ver [ARCH:adjacency-validator].
        lot_boundary_buffered = layout.lot.boundary.polygon.buffer(self._tolerance)

        for room in layout.rooms:
            if not room.is_placed:
                violations.append(f"La estancia '{room.id}' no fue colocada")
                continue
            if not lot_boundary_buffered.contains(room.boundary.polygon):
                violations.append(f"La estancia '{room.id}' queda fuera del limite del solar")

        rooms_by_id = {r.id: r for r in layout.rooms if r.is_placed}
        for req in self._requirements:
            room_a = rooms_by_id.get(req.room_a_id)
            room_b = rooms_by_id.get(req.room_b_id)
            if not room_a or not room_b:
                continue

            if req.strength == AdjacencyStrength.MUST_BE_AWAY:
                if room_a.boundary.polygon.distance(room_b.boundary.polygon) < self._tolerance:
                    violations.append(
                        f"Las estancias '{req.room_a_id}' y '{req.room_b_id}' deben estar "
                        f"separadas pero son adyacentes"
                    )

            elif req.strength == AdjacencyStrength.MUST_BE_NEAR:
                shared_length = room_a.boundary.polygon.boundary.intersection(
                    room_b.boundary.polygon.boundary
                ).length
                if shared_length < MUST_BE_NEAR_MIN_SHARED_LENGTH_M:
                    violations.append(
                        f"Las estancias '{req.room_a_id}' y '{req.room_b_id}' deben compartir "
                        f"al menos {MUST_BE_NEAR_MIN_SHARED_LENGTH_M:.2f}m de borde, pero "
                        f"comparten {shared_length:.2f}m"
                    )

        return ValidationResult(violations=violations)
