from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.ports.adjacency_graph_builder_port import AdjacencyGraphBuilderPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType, SpaceCategory

# Regla "Condicional" del catalogo de relaciones espaciales
# (BEDROOM/MASTER_BEDROOM x BATHROOM, ver relaciones_espaciales.md):
# "1 bano -> acceso solo via pasillo; >=2 banos -> uno puede ser en-suite".
#
# NO es un valor estatico de tabla (TipoA, TipoB) -- depende de cuantos
# RoomType.BATHROOM tenga el Program real. Formulacion equivalente y mas
# simple que no necesita ramificar por conteo: al menos UN bano debe
# tener acceso directo (pared compartida) a circulacion general
# (CORRIDOR o ENTRANCE_HALL). Con 1 solo bano, esa exigencia recae
# necesariamente sobre el (equivale a "acceso solo via pasillo"); con 2+,
# basta con que UNO la cumpla, los demas pueden ser en-suite de un
# dormitorio sin acceso propio a circulacion.


class BanoAccesoGeneralValidator(ConstraintValidatorPort):
    """Al menos un RoomType.BATHROOM debe tener adyacencia real (pared
    compartida) con una estancia de circulacion (CORRIDOR o
    ENTRANCE_HALL) -- ningun bano puede quedar "capturado" exclusivamente
    dentro de un dormitorio si es el unico (o el unico con acceso general)
    de la vivienda.

    Si no hay ningun BATHROOM colocado, no aplica (lista vacia, sin
    avisos) -- ViviendaMinimaValidator ya exige que exista al menos uno;
    este validador no duplica esa exigencia, solo comprueba el acceso.
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
