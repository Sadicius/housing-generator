from typing import List, Dict, Optional
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import SpaceCategory

# Tabla 2 (A.3.2.2). Ver [ARCH:servicio-minimum-area].
TABLA_2: Dict[int, Dict[str, float]] = {
    1: {"cocina": 5, "bano": 5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 1},
    2: {"cocina": 7, "bano": 5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 2},
    3: {"cocina": 7, "bano": 5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 3},
    4: {"cocina": 9, "bano": 5, "aseo": 1.5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 4},
    5: {"cocina": 9, "bano": 5, "aseo": 1.5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 5},
}
TABLA_2_MAS_DE_CINCO: Dict[str, float] = {
    "cocina": 10, "bano": 5, "aseo": 1.5, "lavadero": 1.5, "tendedero": 1.5, "almacenamiento": 6,
}


def tabla_servicios_para(num_estancias: int) -> Dict[str, float]:
    """Fila de Tabla 2 correspondiente a `num_estancias` (numero de
    estancias -- categoria ESTANCIA, no numero total de piezas)."""
    if num_estancias in TABLA_2:
        return TABLA_2[num_estancias]
    if num_estancias < 1:
        return TABLA_2[1]
    return TABLA_2_MAS_DE_CINCO


class ServicioMinimumAreaValidator(ConstraintValidatorPort):
    """Tabla 2: superficie mínima por tipo de servicio (cocina, baño,
    aseo, lavadero, tendedero, almacenamiento), según número de
    estancias. Ver [ARCH:servicio-minimum-area]."""

    def __init__(self, total_num_estancias_override: Optional[int] = None):
        self._total_override = total_num_estancias_override

    def validate(self, layout: Layout) -> ValidationResult:
        local_count = sum(1 for r in layout.rooms if r.space_category == SpaceCategory.ESTANCIA)
        num_estancias = self._total_override if self._total_override is not None else local_count
        tabla = tabla_servicios_para(num_estancias)

        violations: List[str] = []
        for room in layout.rooms:
            if room.service_subtype is None:
                continue
            if room.integrated_in_largest_room:
                continue  # se valida en CocinaIntegradaValidator
            minimo = tabla.get(room.service_subtype)
            if minimo is None:
                continue
            if room.dimensions.area_m2 < minimo:
                violations.append(
                    f"'{room.id}' ({room.service_subtype}): {room.dimensions.area_m2:.1f}m2, "
                    f"por debajo del minimo de Tabla 2 para {num_estancias} estancias "
                    f"({minimo:.1f}m2)"
                )

        return ValidationResult(violations=violations)
