from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import meets_minimum_width

# A.3.2.1: ancho libre minimo entre paramentos enfrentados. Declarado en
# nhv.lua (NHV.anchoLibreMin) pero nunca conectado a ningun validador en
# la fuente; los valores en si son reales (Anexo I, Decreto de Galicia),
# confirmados de forma independiente. Solo cubre estas 5 categorias --
# comedor, despacho, aseo, lavadero, tendedero, trastero, almacenamiento
# no tienen ancho libre asignado en ningun sitio de la fuente.
ANCHO_LIBRE_ESTANCIA_MAYOR_M = 2.70
ANCHO_LIBRE_DORMITORIO_DOBLE_M = 2.60   # habitacion >= 12m2
ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M = 2.00  # habitacion < 12m2
ANCHO_LIBRE_COCINA_M = 1.80
ANCHO_LIBRE_BANO_M = 1.60
DORMITORIO_DOBLE_AREA_UMBRAL_M2 = 12.0

_DORMITORIO_TYPES = {RoomType.BEDROOM, RoomType.MASTER_BEDROOM}


class AnchoLibreEstanciaValidator(ConstraintValidatorPort):
    """A.3.2.1: comprueba el ancho libre minimo (lado mas corto del
    rectangulo) para estancia mayor, dormitorios, cocina y bano.

    La "estancia mayor" aqui es estrictamente `RoomType.LIVING_ROOM` --
    a diferencia de `EstanciaMinimumAreaValidator`, este validador NO
    hace fallback a la estancia de mayor area si no hay salon declarado
    (para no duplicar ese aviso, que ya emite aquel validador sobre el
    mismo tema): si no hay salon, esta comprobacion concreta simplemente
    no se ejecuta.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        placed_rooms = [r for r in layout.rooms if r.is_placed]

        mayor = next((r for r in placed_rooms if r.room_type == RoomType.LIVING_ROOM), None)
        if mayor is not None:
            self._check(mayor, ANCHO_LIBRE_ESTANCIA_MAYOR_M, "estancia mayor (A.3.2.1.a)", violations, warnings)

        for room in placed_rooms:
            if room.room_type in _DORMITORIO_TYPES:
                if room.dimensions.area_m2 >= DORMITORIO_DOBLE_AREA_UMBRAL_M2:
                    minimo, etiqueta = ANCHO_LIBRE_DORMITORIO_DOBLE_M, "dormitorio doble (A.3.2.1.e/f)"
                else:
                    minimo, etiqueta = ANCHO_LIBRE_DORMITORIO_INDIVIDUAL_M, "dormitorio individual (A.3.2.1.g/h)"
                self._check(room, minimo, etiqueta, violations, warnings)
            elif room.room_type == RoomType.KITCHEN:
                self._check(room, ANCHO_LIBRE_COCINA_M, "cocina (A.3.2.1)", violations, warnings)
            elif room.room_type == RoomType.BATHROOM:
                self._check(room, ANCHO_LIBRE_BANO_M, "bano (A.3.2.1)", violations, warnings)

        return ValidationResult(violations=violations, warnings=warnings)

    @staticmethod
    def _check(room, minimo: float, etiqueta: str, violations: List[str], warnings: List[str]) -> None:
        cumple = meets_minimum_width(room.boundary.polygon, minimo)
        if cumple is False:
            violations.append(
                f"'{room.id}' ({etiqueta}): ancho libre por debajo del minimo de {minimo:.2f}m"
            )
        elif cumple is None:
            warnings.append(
                f"'{room.id}' ({etiqueta}): forma no rectangular, no se puede verificar "
                f"el ancho libre de {minimo:.2f}m"
            )
