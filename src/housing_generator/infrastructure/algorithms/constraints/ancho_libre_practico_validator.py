from typing import List, Set
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import evaluate_minimum_width

# NO NORMATIVO -- criterio de ingenieria practica, confirmado
# explicitamente con el usuario, no un valor del Decreto 29/2010.
#
# Hallazgo real: AnchoLibreEstanciaValidator (A.3.2.1) solo cubre 5
# categorias porque el propio decreto no especifica ancho libre minimo
# para el resto de tipos -- confirmado e investigado en su momento, no
# un descuido. Pero eso significaba que el generador podia producir
# formas NORMATIVAMENTE CONFORMES y PRACTICAMENTE INSERVIBLES: un caso
# real (captura de pantalla del usuario) mostro un "Almacen" de 3m2
# generado como 2.49m x 0.49m -- 49 CENTIMETROS de fondo, cumple el
# area exigida pero es inutilizable en la practica (no cabe ni una
# balda). El decreto no exige un minimo ahi porque asume, con razon,
# que ningun arquitecto real dibujaria eso -- pero un generador
# automatico sin este limite si puede, y sin darse cuenta.
#
# Cubre los tipos que NO tienen ningun otro ancho libre comprobado en
# ningun validador del proyecto (ver docs/architecture.md para el
# listado exacto verificado): comedor, despacho, aseo, lavadero,
# tendedero, almacenamiento, recibidor, garaje, cuarto tecnico.
# Trastero (STORAGE_ROOM) ya tiene su propio minimo normativo (B.2.5,
# TrasteroMinimumAreaValidator, 1.60m) -- no se duplica aqui.
ANCHO_LIBRE_PRACTICO_M = 1.20

TIPOS_SIN_ANCHO_NORMATIVO: Set[RoomType] = {
    RoomType.DINING_ROOM,
    RoomType.STUDY,
    RoomType.TOILET,
    RoomType.LAUNDRY,
    RoomType.DRYING_AREA,
    RoomType.STORAGE,
    RoomType.ENTRANCE_HALL,
    RoomType.GARAGE,
    RoomType.TECHNICAL_ROOM,
}


class AnchoLibrePracticoValidator(ConstraintValidatorPort):
    """Ancho libre mínimo NO NORMATIVO (1.20m, criterio de ingeniería
    confirmado explícitamente, no del Decreto 29/2010) para los tipos
    de estancia que el decreto deja sin ancho libre especificado --
    evita formas técnicamente conformes en área pero inservibles en la
    práctica (p.ej. un almacén de 49cm de fondo)."""

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type not in TIPOS_SIN_ANCHO_NORMATIVO or not room.is_placed:
                continue
            v, w = evaluate_minimum_width(
                room.id, room.boundary.polygon, ANCHO_LIBRE_PRACTICO_M,
                violation_message=(
                    f"ancho libre por debajo del minimo practico de ingenieria "
                    f"({ANCHO_LIBRE_PRACTICO_M:.2f}m, NO normativo -- el Decreto 29/2010 "
                    f"no especifica ancho libre para este tipo, pero una estancia mas "
                    f"estrecha que esto no es utilizable en la practica)"
                ),
                warning_message="forma no rectangular, no se puede verificar el ancho libre práctico",
            )
            violations.extend(v)
            warnings.extend(w)

        return ValidationResult(violations=violations, warnings=warnings)
