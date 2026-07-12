from typing import List, Dict, Optional, Tuple
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.room import Room
from housing_generator.domain.enums import SpaceCategory, RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_inscribe_square

# Tabla 1 (A.3.2.1 en nhv.lua / Decreto 29/2010): superficie util minima
# POR ESTANCIA segun el puesto que ocupa por tamano (E1 = la mayor, E2 =
# la segunda...), NO una superficie total. Portado literalmente de la
# fuente normativa -- estos numeros no son heuristica de este proyecto.
TABLA_1: Dict[int, List[float]] = {
    1: [25],
    2: [16, 12],
    3: [18, 12, 8],
    4: [20, 12, 8, 8],
    5: [22, 12, 8, 8, 6],
}
TABLA_1_MAS_DE_CINCO: List[float] = [25, 12, 8, 8, 8]  # E1..E5 fijos si hay >5 estancias
MINIMO_ESTANCIA_ADICIONAL = 6.0  # E6, E7... cuando hay mas de 5

# A.3.2.1.a: lado del cuadrado inscribible exigido a la estancia mayor
CUADRADO_INSCRIBIBLE_ESTANCIA_MAYOR_LADO_M = 3.30


def minimo_estancia(num_estancias: int, indice: int) -> Optional[float]:
    """Minimo de superficie util para la estancia que ocupa el puesto
    `indice` (1 = la mayor) en una vivienda con `num_estancias` estancias."""
    if num_estancias <= 5:
        fila = TABLA_1.get(num_estancias)
        if fila is None or indice > len(fila):
            return None
        return fila[indice - 1]
    if indice <= 5:
        return TABLA_1_MAS_DE_CINCO[indice - 1]
    return MINIMO_ESTANCIA_ADICIONAL


class EstanciaMinimumAreaValidator(ConstraintValidatorPort):
    """Tabla 1: superficie mínima por puesto de tamaño entre las
    estancias (space_category ESTANCIA). La estancia mayor para el
    cuadrado inscribible (A.3.2.1.a) es siempre el salón. Ver
    [ARCH:estancia-minimum-area].
    """

    def __init__(
        self,
        total_num_estancias_override: Optional[int] = None,
        global_rank_override: Optional[Dict[str, int]] = None,
    ):
        self._total_override = total_num_estancias_override
        self._global_rank = global_rank_override

    def validate(self, layout: Layout) -> ValidationResult:
        estancias = [r for r in layout.rooms if r.space_category == SpaceCategory.ESTANCIA]
        if not estancias:
            return ValidationResult()

        ordenadas = sorted(estancias, key=lambda r: r.dimensions.area_m2, reverse=True)
        num_estancias = self._total_override if self._total_override is not None else len(ordenadas)

        violations = self._check_rank_minimums(ordenadas, num_estancias)
        cuadrado_violations, warnings = self._check_estancia_mayor_cuadrado(estancias, ordenadas)
        violations.extend(cuadrado_violations)

        return ValidationResult(violations=violations, warnings=warnings)

    def _check_rank_minimums(self, ordenadas: List[Room], num_estancias: int) -> List[str]:
        """Tabla 1 propiamente dicha: superficie minima por puesto de
        tamano (E1=mayor, E2=segunda...)."""
        violations: List[str] = []
        for local_i, room in enumerate(ordenadas, start=1):
            puesto = self._global_rank.get(room.id, local_i) if self._global_rank else local_i
            minimo = minimo_estancia(num_estancias, puesto)
            if minimo is not None and room.dimensions.area_m2 < minimo:
                violations.append(
                    f"'{room.id}': {room.dimensions.area_m2:.1f}m2, por debajo del minimo de "
                    f"Tabla 1 para el puesto {puesto} de {num_estancias} estancias ({minimo:.1f}m2)"
                )
        return violations

    def _check_estancia_mayor_cuadrado(
        self, estancias: List[Room], ordenadas: List[Room],
    ) -> Tuple[List[str], List[str]]:
        """A.3.2.1.a: cuadrado inscribible de 3.30m de lado en la
        estancia mayor (siempre el salon, RoomType.LIVING_ROOM)."""
        violations: List[str] = []
        warnings: List[str] = []

        mayor = next((r for r in estancias if r.room_type == RoomType.LIVING_ROOM), None)
        if mayor is None:
            if self._total_override is not None:
                # multi-planta sin salon en ESTA planta = caso normal
                # (esta en otra planta). Ver [ARCH:estancia-minimum-area].
                return violations, warnings
            mayor = ordenadas[0]
            warnings.append(
                f"No hay 'living_room' declarado entre las estancias; se usa '{mayor.id}' "
                f"(la de mayor area) como sustituto de la estancia mayor para el cuadrado "
                f"inscribible -- confirmar si esto es correcto para este programa"
            )

        if mayor.is_placed:
            cabe = can_inscribe_square(mayor.boundary.polygon, CUADRADO_INSCRIBIBLE_ESTANCIA_MAYOR_LADO_M)
            if cabe is False:
                violations.append(
                    f"'{mayor.id}' (estancia mayor): no cabe el cuadrado inscribible de "
                    f"{CUADRADO_INSCRIBIBLE_ESTANCIA_MAYOR_LADO_M:.2f}m de lado"
                )
            elif cabe is None:
                warnings.append(
                    f"'{mayor.id}' (estancia mayor): forma no rectangular, no se puede "
                    f"verificar el cuadrado inscribible de {CUADRADO_INSCRIBIBLE_ESTANCIA_MAYOR_LADO_M:.2f}m "
                    f"con la geometria computacional implementada actualmente"
                )

        return violations, warnings
