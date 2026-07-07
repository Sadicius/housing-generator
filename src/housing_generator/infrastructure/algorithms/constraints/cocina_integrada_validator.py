from typing import List, Optional
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType, SpaceCategory
from housing_generator.infrastructure.algorithms.constraints.estancia_minimum_area_validator import (
    minimo_estancia,
)
from housing_generator.infrastructure.algorithms.constraints.servicio_minimum_area_validator import (
    tabla_servicios_para,
)

# A.3.2.2 / nhv.lua (validarCocinaIntegrada): cuando la cocina se abre en
# un unico espacio con la estancia mayor (caso tipico de un estudio), la
# superficie minima del CONJUNTO es la SUMA de los minimos de cada pieza
# por separado (Tabla 1 para la estancia mayor + Tabla 2 para la cocina,
# cada una segun el numero de estancias) -- no un numero fijo propio.
# Ademas exige una apertura vertical minima de relacion entre ambas.
APERTURA_VERTICAL_MIN_M2 = 3.5


class CocinaIntegradaValidator(ConstraintValidatorPort):
    """Valida la cocina integrada en la estancia mayor (RoomType.KITCHEN
    con `integrated_in_largest_room=True`).

    Fiel al comportamiento de la fuente, con tres casos distintos:
    - Si NO hay ninguna cocina marcada como integrada: la funcion NO
      APLICA -- lista vacia, sin avisos. Esto es distinto de "no
      verificable": simplemente no es un caso relevante para este
      programa.
    - Si hay cocina integrada pero no hay salon (`RoomType.LIVING_ROOM`)
      en el programa: AVISO (no se puede determinar la estancia mayor).
    - Si hay ambos: se comprueba la superficie combinada (violacion si
      no alcanza el minimo) y la apertura vertical (violacion si es
      insuficiente; AVISO si no se declaro, nunca aprobacion silenciosa).
    """

    def validate(self, layout: Layout) -> ValidationResult:
        cocina = next(
            (r for r in layout.rooms if r.room_type == RoomType.KITCHEN and r.integrated_in_largest_room),
            None,
        )
        if cocina is None:
            return ValidationResult()

        mayor = next((r for r in layout.rooms if r.room_type == RoomType.LIVING_ROOM), None)
        if mayor is None:
            return ValidationResult(
                warnings=["Cocina integrada declarada pero no hay salón (LIVING_ROOM) en el "
                          "programa -- no se puede determinar la estancia mayor"]
            )

        violations: List[str] = []
        warnings: List[str] = []

        num_estancias = sum(1 for r in layout.rooms if r.space_category == SpaceCategory.ESTANCIA)
        minimo_mayor = minimo_estancia(num_estancias, 1)
        minimo_cocina = tabla_servicios_para(num_estancias).get("cocina")

        if minimo_mayor is not None and minimo_cocina is not None:
            minimo_combinado = minimo_mayor + minimo_cocina
            area_combinada = mayor.dimensions.area_m2 + cocina.dimensions.area_m2
            if area_combinada < minimo_combinado:
                violations.append(
                    f"'{mayor.id}' + '{cocina.id}': superficie combinada {area_combinada:.1f}m2 "
                    f"por debajo del minimo {minimo_combinado:.1f}m2 "
                    f"({minimo_mayor:.1f}m2 estancia mayor + {minimo_cocina:.1f}m2 cocina, "
                    f"cada una segun su propia tabla)"
                )
        else:
            warnings.append(
                f"No se pudo determinar el minimo combinado de '{mayor.id}' + '{cocina.id}' "
                f"-- revisar el numero de estancias"
            )

        if cocina.vertical_opening_m2 is None:
            warnings.append(
                f"'{cocina.id}': falta declarar 'vertical_opening_m2' -- no se puede verificar "
                f"la apertura minima de {APERTURA_VERTICAL_MIN_M2:.1f}m2 con '{mayor.id}'"
            )
        elif cocina.vertical_opening_m2 < APERTURA_VERTICAL_MIN_M2:
            violations.append(
                f"'{cocina.id}': apertura vertical de relación con '{mayor.id}' de "
                f"{cocina.vertical_opening_m2:.1f}m2, por debajo del mínimo "
                f"{APERTURA_VERTICAL_MIN_M2:.1f}m2"
            )

        return ValidationResult(violations=violations, warnings=warnings)
