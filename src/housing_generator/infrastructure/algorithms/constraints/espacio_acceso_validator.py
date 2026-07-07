from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_inscribe_square

# A.2 (numeracion exacta incierta tras la renumeracion del Decreto
# 128/2023 -- el fragmento aparecio junto a A.4 en las fuentes
# consultadas, probablemente perteneciente a A.3.3 "Espacios de
# comunicacion" en la version vigente): "El espacio de acceso interior
# de la vivienda debera admitir la inscripcion de un cuadrado de 1,50 m
# de lado, libre de obstaculos, en contacto con la puerta de entrada y
# cuya superficie util podra estar incluida en la superficie util
# minima de la estancia mayor en caso de que el acceso a la vivienda se
# realice directamente a traves de ella."
ESPACIO_ACCESO_CUADRADO_M = 1.50

# "En contacto con la puerta de entrada" NO se comprueba aqui -- este
# proyecto no modela puertas/accesos en absoluto (mismo hueco de modelo
# ya identificado en relaciones_espaciales.md: "acceso/puertas"). Se
# documenta como alcance pendiente, no como aviso repetido en cada
# validacion (a diferencia de datos que faltan caso a caso, esto falta
# siempre, de forma sistematica, hasta que se aborde el modelo de
# puertas como pieza propia).


class EspacioAccesoValidator(ConstraintValidatorPort):
    """Cuadrado inscribible de 1.50m en el recibidor (RoomType.ENTRANCE_HALL).

    Si no hay ENTRANCE_HALL en el programa, el requisito NO APLICA (lista
    vacia, sin avisos) -- la propia norma exime este caso cuando el
    acceso a la vivienda se realiza directamente a traves de la estancia
    mayor, sin recibidor propio; ese caso ya queda cubierto por el
    minimo de la estancia mayor (Tabla 1), no por este validador.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type != RoomType.ENTRANCE_HALL:
                continue
            if not room.is_placed:
                continue

            cumple = can_inscribe_square(room.boundary.polygon, ESPACIO_ACCESO_CUADRADO_M)
            if cumple is False:
                violations.append(
                    f"'{room.id}': no admite el cuadrado de {ESPACIO_ACCESO_CUADRADO_M:.2f}m "
                    f"de lado exigido en el espacio de acceso interior"
                )
            elif cumple is None:
                warnings.append(
                    f"'{room.id}': forma no rectangular, no se puede verificar el cuadrado "
                    f"de acceso interior de {ESPACIO_ACCESO_CUADRADO_M:.2f}m"
                )

        return ValidationResult(violations=violations, warnings=warnings)
