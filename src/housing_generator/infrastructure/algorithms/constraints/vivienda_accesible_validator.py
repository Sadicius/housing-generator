from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.geometry.shapely_utils import can_inscribe_square, evaluate_minimum_width

# Retomado de un modulo Lua de un proyecto anterior del usuario
# (accesibilidad.lua), que investigo a fondo DB-SUA (Anejo A, CTE
# estatal) cruzado con el Codigo de Accesibilidad de Galicia (Decreto
# 35/2000, actualizado por el Decreto 74/2013) y la Base 5.4 gallega
# (vivienda adaptada para usuarios de silla de ruedas). OPT-IN: la
# gran mayoria de viviendas NO estan obligadas a cumplir estas
# condiciones -- DB-SUA 9.1, texto literal citado en la fuente Lua:
# "Dentro de los limites de las viviendas... las condiciones de
# accesibilidad unicamente son exigibles en aquellas que deban ser
# accesibles" (una designacion especifica, no cualquier vivienda).
#
# ALCANCE: de todo lo que cubre la fuente Lua (que tambien verifica
# mobiliario -- altura de encimera, aproximacion lateral a la cama,
# hueco bajo fregadero, barras de apoyo...), aqui solo se modela lo
# GEOMETRICAMENTE VERIFICABLE con nuestro `Room` (un rectangulo con
# area, sin mobiliario ni fixtures) -- circulo de giro y ancho de
# pasillo. El resto exigiria modelar mobiliario como piezas propias
# dentro de cada estancia, un salto de complejidad que este proyecto
# no da por los mismos motivos que ya documentamos para C.10 (luz
# directa) o el parametro D de patios: fingir una comprobacion sin
# los datos reales seria peor que no darla.
CIRCULO_GIRO_ACCESIBLE_M = 1.50  # DB-SUA Anejo A / Base 5.4 -- mismo valor en estancias y bano
PASILLO_ACCESIBLE_ANCHO_M = 1.20  # Base 5.4 -- mas exigente que el generico 1.00m (A.3.2.3)

# Tipos de estancia sobre los que tiene sentido exigir el circulo de
# giro en una vivienda accesible -- las mismas piezas que la fuente Lua
# comprueba con `acc.circuloGiro` (estancia mayor, dormitorios, cocina,
# bano) mas RoomType.DINING_ROOM (misma zona de estar, mismo criterio).
# No incluye estancias de servicio pequenas (lavadero, tendedero,
# almacenamiento) -- la fuente Lua tampoco las exige.
TIPOS_CON_CIRCULO_GIRO = {
    RoomType.LIVING_ROOM, RoomType.DINING_ROOM, RoomType.BEDROOM,
    RoomType.MASTER_BEDROOM, RoomType.KITCHEN, RoomType.BATHROOM,
}


class ViviendaAccesibleValidator(ConstraintValidatorPort):
    """Vivienda declarada accesible para usuarios de silla de ruedas
    (DB-SUA Anejo A + Base 5.4 Galicia) -- SOLO activo si se construye
    con `activo=True`. Exige circulo de giro Ø1.50m inscribible en
    estancias habitables + baño, y pasillo ≥1.20m (mas exigente que el
    minimo general de `AnchoLibrePasilloValidator`, 1.00m -- ambos
    validadores conviven, este añade una exigencia adicional, no
    sustituye al general)."""

    def __init__(self, activo: bool = False):
        self.activo = activo

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        if not self.activo:
            return ValidationResult(violations=violations, warnings=warnings)

        for room in layout.rooms:
            if not room.is_placed:
                continue

            if room.room_type in TIPOS_CON_CIRCULO_GIRO:
                cumple = can_inscribe_square(room.boundary.polygon, CIRCULO_GIRO_ACCESIBLE_M)
                if cumple is False:
                    violations.append(
                        f"'{room.id}': vivienda accesible, no admite el circulo de giro "
                        f"de Ø{CIRCULO_GIRO_ACCESIBLE_M:.2f}m exigido (DB-SUA/Base 5.4)"
                    )
                elif cumple is None:
                    warnings.append(
                        f"'{room.id}': forma no rectangular, no se puede verificar el "
                        f"circulo de giro de vivienda accesible"
                    )

            if room.room_type == RoomType.CORRIDOR:
                v, w = evaluate_minimum_width(
                    room.id, room.boundary.polygon, PASILLO_ACCESIBLE_ANCHO_M,
                    violation_message=(
                        f"ancho libre por debajo del minimo de vivienda accesible "
                        f"({PASILLO_ACCESIBLE_ANCHO_M:.2f}m, Base 5.4 -- mas exigente que "
                        f"el general de A.3.2.3)"
                    ),
                    warning_message="forma no rectangular, no se puede verificar el ancho de pasillo accesible",
                )
                violations.extend(v)
                warnings.extend(w)

        return ValidationResult(violations=violations, warnings=warnings)
