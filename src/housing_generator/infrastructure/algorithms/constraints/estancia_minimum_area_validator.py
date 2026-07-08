from typing import List, Dict, Optional
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
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
    """Tabla 1: superficie minima por puesto de tamano entre las estancias
    (space_category == ESTANCIA). Ni cocina, ni bano/aseo/lavadero, ni
    circulacion cuentan aqui -- solo estar/comedor/dormitorios/despacho.

    La "estancia mayor" para el cuadrado inscribible (A.3.2.1.a) es
    SIEMPRE el salon (RoomType.LIVING_ROOM) -- confirmado como regla de
    proyecto, no una derivacion automatica por area. El ranking de
    Tabla 1 (puesto 1..N) sigue siendo por tamano real, sin relacion con
    cual sea la estancia mayor; son dos conceptos independientes.
    - Si no hay salon declarado entre las estancias: se usa la de mayor
      area como alternativa, pero se marca como AVISO (no se asume en
      silencio que la sustitucion es equivalente).
    - Si la estancia mayor esta colocada (`boundary` real) y es
      rectangular, se verifica el cuadrado inscribible de forma exacta.
    - Si esta colocada pero NO es rectangular: AVISO, nunca violacion.
    - Si no esta colocada todavia: no se comprueba aqui.

    `total_num_estancias_override`: para vivienda MULTI-PLANTA (ver
    GenerateBuildingUseCase) -- este validador se aplica UNA planta a la
    vez, pero Tabla 1 depende del numero de estancias del EDIFICIO
    COMPLETO, no solo de las de esta planta (bug real encontrado al
    construir el primer edificio de 2 plantas de prueba: una planta con
    1 sola estancia aplicaba la fila de "vivienda de 1 estancia" (25m2)
    en vez de la fila real del edificio). Si se declara, sustituye
    `len(ordenadas)` para elegir la FILA de Tabla 1 correcta.

    `global_rank_override`: **[RESUELTO]** dict room_id -> puesto GLOBAL
    (1=mayor del EDIFICIO completo, no solo de esta planta). Corrige la
    limitacion senalada en el incremento anterior (el ranking quedaba
    atado solo a las estancias de la planta local, podia exigir un
    minimo mas estricto del que corresponderia). `GenerateBuildingUseCase`
    lo precalcula una vez, antes de generar ninguna planta, porque las
    areas son DECLARADAS (no dependen de la geometria ya colocada).
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
        violations: List[str] = []
        warnings: List[str] = []

        for local_i, room in enumerate(ordenadas, start=1):
            puesto = self._global_rank.get(room.id, local_i) if self._global_rank else local_i
            minimo = minimo_estancia(num_estancias, puesto)
            if minimo is not None and room.dimensions.area_m2 < minimo:
                violations.append(
                    f"'{room.id}': {room.dimensions.area_m2:.1f}m2, por debajo del minimo de "
                    f"Tabla 1 para el puesto {puesto} de {num_estancias} estancias ({minimo:.1f}m2)"
                )

        mayor = next((r for r in estancias if r.room_type == RoomType.LIVING_ROOM), None)
        if mayor is None:
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

        return ValidationResult(violations=violations, warnings=warnings)
