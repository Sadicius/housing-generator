from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType, SpaceCategory

# Regla "Condicional" del catalogo. Ver [ARCH:bano-acceso].


class BanoAccesoGeneralValidator(ConstraintValidatorPort):
    """Al menos un BATHROOM debe tener adyacencia real con circulación
    (CORRIDOR o ENTRANCE_HALL) -- ninguno puede quedar capturado
    exclusivamente dentro de un dormitorio si es el único con acceso
    general. Sin BATHROOM colocado, o sin NINGUNA circulación en el
    programa (no aplica -- no hay nada con lo que exigir adyacencia),
    no aplica. Ver [ARCH:bano-acceso].
    """

    def __init__(self, graph_builder: AdjacencyGraphBuilderPort):
        self._graph_builder = graph_builder

    def validate(self, layout: Layout) -> ValidationResult:
        bathrooms = [r for r in layout.rooms if r.is_placed and r.room_type == RoomType.BATHROOM]
        if not bathrooms:
            return ValidationResult()

        graph = self._graph_builder.build(layout)
        circulation_ids = {
            r.id for r in layout.rooms
            if r.is_placed and r.space_category == SpaceCategory.CIRCULACION
        }
        if not circulation_ids:
            # BUG REAL encontrado en auditoria de diagnostico: sin
            # NINGUNA estancia de circulacion en el programa (valido --
            # "programa minimo" no exige recibidor/pasillo), esta regla
            # era IMPOSIBLE de satisfacer sea cual fuera la geometria
            # (neighbors & circulation_ids nunca podia ser no-vacio).
            # Mismo patron "no aplica" que EspacioAccesoValidator.
            return ValidationResult()

        for bath in bathrooms:
            if bath.id not in graph:
                continue
            neighbors = set(graph.neighbors(bath.id))
            if neighbors & circulation_ids:
                return ValidationResult()  # al menos uno tiene acceso general -- regla satisfecha

        violations: List[str] = [
            f"Ningún baño tiene acceso directo desde circulación general (CORRIDOR/ENTRANCE_HALL) "
            f"-- con {len(bathrooms)} baño(s) en el programa, al menos uno no puede quedar "
            f"capturado exclusivamente dentro de un dormitorio"
        ]
        return ValidationResult(violations=violations)
