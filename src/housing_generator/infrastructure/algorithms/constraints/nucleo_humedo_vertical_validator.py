from typing import List
from shapely.geometry import Polygon
from shapely.ops import unary_union
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# docs/niveles_plantas.md, "Relacion vertical: continuidad de
# instalaciones (bajantes)" -- documentado desde hace tiempo, nunca
# implementable por falta de generacion multi-planta. Regla: cualquier
# estancia humeda (is_wet) de esta planta debe solapar en (x,y) con
# ALGUNA humeda de la planta inmediatamente inferior -- "cualquier tipo
# humedo coincide, no especifico por tipo" (ya confirmado en ese
# documento). A diferencia de la escalera (que exige near-alineacion
# exacta por continuidad estructural), aqui basta con solape real
# (interseccion de area > 0): las bajantes necesitan poder discurrir
# verticalmente por la zona humeda, no que las piezas coincidan pieza
# a pieza.


class NucleoHumedoVerticalValidator(ConstraintValidatorPort):
    """Cada estancia humeda de esta planta debe solapar en planta con
    alguna humeda de la planta inmediatamente inferior (continuidad de
    bajantes). `reference_wet_boundaries=[]` (planta de abajo sin
    humedas, o no hay planta de abajo) significa que este validador no
    aplica -- no se puede comprobar continuidad contra una planta que no
    tiene ninguna humeda con la que solapar."""

    def __init__(self, reference_wet_boundaries: List[Polygon]):
        self._reference_union = unary_union(reference_wet_boundaries) if reference_wet_boundaries else None

    def validate(self, layout: Layout) -> ValidationResult:
        if self._reference_union is None:
            return ValidationResult()

        wet_rooms = [r for r in layout.rooms if r.is_wet and r.is_placed]
        violations: List[str] = []
        for room in wet_rooms:
            overlap = room.boundary.polygon.intersection(self._reference_union).area
            if overlap <= 0:
                violations.append(
                    f"'{room.id}': sin solape en planta con ninguna estancia humeda de la "
                    f"planta inferior -- continuidad de bajantes rota"
                )
        return ValidationResult(violations=violations)
