from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# A.3.1.1: altura libre minima entre pavimento y techo terminados.
# - alturaLibreMin (2.50m): la mayoria de piezas.
# - alturaLibreReducida (2.20m): DIRECTAMENTE permitida, sin condicion,
#   en vestibulo/pasillo/ESCALERAS/bano/aseo/lavadero/tendedero/GARAJES
#   DE VIVIENDAS UNIFAMILIARES (A.3.1.1.b, texto exacto confirmado por
#   investigacion normativa directa -- ver docs/architecture.md,
#   hallazgo de la revision "mas informacion relevante sin aplicar").
# - En el RESTO de piezas, 2.20m se admite como MAXIMO en una fraccion
#   de la superficie util (30%) -- el resto debe llegar a 2.50m. Es una
#   comprobacion de geometria PARCIAL (que parte de la planta queda bajo
#   una viga/bajante) que este proyecto NO calcula, igual que la propia
#   fuente admite no calcular: en vez de asumir cumplimiento o violacion,
#   se emite un AVISO recordando la excepcion (A.3.1.1.c).
# Solo cuarto tecnico queda fuera de alcance: no aparece en ninguna
# lista de la fuente consultada.
#
# [RESUELTO -- bug real encontrado en auditoria] Antes, GARAGE estaba en
# ROOM_TYPES_FUERA_DE_ALCANCE (sin comprobar en absoluto) y STAIRCASE no
# estaba en ninguna de las dos listas (caia en el caso general de
# 2.50m/excepcion del 30%, mas estricto de lo que le corresponde) --
# ambos EXPLICITAMENTE nombrados en A.3.1.1.b, confirmado con el mismo
# texto normativo citado arriba. El comentario anterior decia "garaje...
# no aparece en ninguna lista de la fuente", repitiendo la misma
# confusion ya corregida en DEFAULT_MIN_EXTERIOR_SIDES (B.2.6 no es "la
# regla propia del garaje unifamiliar" -- es de garajes COLECTIVOS, no
# aplica aqui; la reduccion de altura SI aparece, en la seccion A que si
# aplica a unifamiliar).
ALTURA_LIBRE_MIN_M = 2.50
ALTURA_LIBRE_REDUCIDA_M = 2.20

ROOM_TYPES_REDUCCION_DIRECTA = {
    RoomType.ENTRANCE_HALL,  # vestibulo
    RoomType.CORRIDOR,       # pasillo
    RoomType.STAIRCASE,      # escaleras
    RoomType.BATHROOM,       # bano
    RoomType.TOILET,         # aseo
    RoomType.LAUNDRY,        # lavadero
    RoomType.DRYING_AREA,    # tendedero
    RoomType.GARAGE,         # garajes de viviendas unifamiliares
}
ROOM_TYPES_FUERA_DE_ALCANCE = {RoomType.TECHNICAL_ROOM}


class AlturaLibreValidator(ConstraintValidatorPort):
    """Valida `Room.dimensions.ceiling_height_m` contra A.3.1.1.

    - Sin altura declarada (`ceiling_height_m is None`): AVISO, nunca se
      asume cumplimiento ni se penaliza como violacion.
    - Piezas de reduccion directa: violacion solo si < 2.20m.
    - Resto de piezas: violacion si < 2.20m; AVISO (no violacion) si
      esta entre 2.20m y 2.50m, porque podria estar cubierta por la
      excepcion del 30% que este validador no puede comprobar; sin
      aviso si >= 2.50m.
    """

    def validate(self, layout: Layout) -> ValidationResult:
        violations: List[str] = []
        warnings: List[str] = []

        for room in layout.rooms:
            if room.room_type in ROOM_TYPES_FUERA_DE_ALCANCE:
                continue

            altura = room.dimensions.ceiling_height_m
            if altura is None:
                warnings.append(
                    f"'{room.id}': altura de techo no declarada, no se puede verificar A.3.1.1"
                )
                continue

            if room.room_type in ROOM_TYPES_REDUCCION_DIRECTA:
                if altura < ALTURA_LIBRE_REDUCIDA_M:
                    violations.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo del minimo "
                        f"reducido de A.3.1.1.b ({ALTURA_LIBRE_REDUCIDA_M:.2f}m)"
                    )
            else:
                if altura < ALTURA_LIBRE_REDUCIDA_M:
                    violations.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo incluso del "
                        f"minimo reducido de A.3.1.1 ({ALTURA_LIBRE_REDUCIDA_M:.2f}m)"
                    )
                elif altura < ALTURA_LIBRE_MIN_M:
                    warnings.append(
                        f"'{room.id}': altura libre {altura:.2f}m por debajo de "
                        f"{ALTURA_LIBRE_MIN_M:.2f}m -- podria cumplir via la excepcion del "
                        f"30% de superficie (A.3.1.1.c), no verificable sin geometria parcial"
                    )

        return ValidationResult(violations=violations, warnings=warnings)
