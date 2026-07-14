from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout

# NO NORMATIVO -- criterio de ingenieria confirmado explicitamente,
# no del Decreto 29/2010. Encontrado con un caso real (captura de
# pantalla del usuario): un Pasillo declarado a 4.0m2 se genero mas
# grande que un Dormitorio declarado a 8.0m2 -- ninguna regla exigia
# que el area REALMENTE generada se pareciera al area DECLARADA, solo
# que superase el minimo normativo (Tabla 1/2). Investigado antes de
# fijar el valor: el algoritmo squarified treemap ORIGINAL (Bruls et
# al. 2000, la misma fuente ya citada en este proyecto) se define como
# "area predefinida sin ningun espacio sin usar" -- coincidencia
# exacta por diseno del propio algoritmo. La desviacion la introduce
# nuestra propia extension (`ratio_override`/`slide_wall`, hasta
# +-8% por movimiento, sin limite acumulado ni penalizacion). Sin
# fuente citable para "cuanto es aceptable" en este contexto -- ver
# [ARCH:area-objetivo].
TOLERANCIA_AREA = 0.15


class AreaObjetivoValidator(ConstraintValidatorPort):
    """Compara el área realmente generada de cada estancia colocada
    contra su área declarada (`Room.dimensions.area_m2`) -- violación
    si la desviación supera el ±15% NO normativo. Ver
    [ARCH:area-objetivo]."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if not room.is_placed:
                continue
            area_declarada = room.dimensions.area_m2
            if not area_declarada or area_declarada <= 0:
                continue
            area_generada = room.boundary.polygon.area
            desviacion = abs(area_generada - area_declarada) / area_declarada
            if desviacion > TOLERANCIA_AREA:
                violations.append(
                    f"'{room.id}': area generada {area_generada:.1f}m2 se desvia un "
                    f"{desviacion*100:.0f}% del area declarada {area_declarada:.1f}m2 "
                    f"(NO normativo -- maximo aceptado {TOLERANCIA_AREA*100:.0f}%)"
                )

        return ValidationResult(violations=violations, warnings=warnings)
