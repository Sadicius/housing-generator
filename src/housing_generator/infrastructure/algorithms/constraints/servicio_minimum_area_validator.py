from typing import List, Dict, Optional
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import SpaceCategory

# Tabla 2 (A.3.2.2 en nhv.lua / Decreto 29/2010): superficie util minima
# por TIPO DE SERVICIO, segun el numero de estancias de la vivienda (no
# el tamano del servicio en si). Portado literalmente de la fuente
# normativa. "aseo" no aparece como clave hasta 4 estancias -- eso es
# fiel al original, no un olvido: con menos de 4 estancias la norma no
# exige un aseo independiente, asi que si el programa declara uno de
# todas formas, no hay minimo que comprobar (ver nota en el validador).
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
    """Tabla 2: superficie minima por tipo de servicio (cocina, bano,
    aseo, lavadero, tendedero, almacenamiento), segun el numero de
    estancias de la vivienda.

    NOTA DE ALCANCE (deliberada, no un descuido): no se modela todavia
    "cocina integrada en estancia mayor" (superficie combinada distinta,
    ver `validarCocinaIntegrada` en nhv.lua) ni "trastero" B.2.5 (regla
    fija de 4.00m2, distinta de "almacenamiento"). Ambos quedan fuera de
    este validador hasta que se aborden como piezas propias.

    `total_num_estancias_override`: mismo motivo que en
    `EstanciaMinimumAreaValidator` -- para vivienda MULTI-PLANTA, Tabla 2
    depende del numero de estancias del EDIFICIO COMPLETO, no solo de
    las de esta planta.
    """

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
                # cocina integrada: se valida con CocinaIntegradaValidator
                # (superficie combinada con la estancia mayor), no aqui --
                # misma exclusion que en nhv.lua (`not e.integradaEnEstanciaMayor`).
                continue
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
