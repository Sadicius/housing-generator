from typing import List, Optional, Tuple
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.room import Room
from housing_generator.domain.enums import RoomType, SpaceCategory
from housing_generator.infrastructure.algorithms.constraints.estancia_minimum_area_validator import (
    minimo_estancia,
)
from housing_generator.infrastructure.algorithms.constraints.servicio_minimum_area_validator import (
    tabla_servicios_para,
)

# A.3.2.2 / nhv.lua (validarCocinaIntegrada): superficie minima del
# CONJUNTO = suma de minimos de cada pieza. Ver [ARCH:cocina-integrada].
APERTURA_VERTICAL_MIN_M2 = 3.5


class CocinaIntegradaValidator(ConstraintValidatorPort):
    """Valida la cocina integrada en la estancia mayor (RoomType.KITCHEN
    con `integrated_in_largest_room=True`): sin cocina integrada, no
    aplica; con cocina pero sin salón, aviso; con ambos, comprueba
    superficie combinada + apertura vertical. Ver [ARCH:cocina-integrada].
    """

    def __init__(self, total_num_estancias_override: Optional[int] = None):
        self._total_override = total_num_estancias_override

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

        local_count = sum(1 for r in layout.rooms if r.space_category == SpaceCategory.ESTANCIA)
        num_estancias = self._total_override if self._total_override is not None else local_count

        area_violations, area_warnings = self._check_combined_area(mayor, cocina, num_estancias)
        opening_violations, opening_warnings = self._check_vertical_opening(mayor, cocina)

        return ValidationResult(
            violations=area_violations + opening_violations,
            warnings=area_warnings + opening_warnings,
        )

    @staticmethod
    def _check_combined_area(mayor: Room, cocina: Room, num_estancias: int) -> Tuple[List[str], List[str]]:
        """Superficie minima del CONJUNTO salon+cocina: suma de los
        minimos de cada pieza por separado (Tabla 1 + Tabla 2)."""
        violations: List[str] = []
        warnings: List[str] = []

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
        return violations, warnings

    @staticmethod
    def _check_vertical_opening(mayor: Room, cocina: Room) -> Tuple[List[str], List[str]]:
        """Apertura vertical minima de relacion entre cocina y salon."""
        violations: List[str] = []
        warnings: List[str] = []

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
        return violations, warnings
