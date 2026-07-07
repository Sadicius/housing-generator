from typing import List
from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.enums import RoomType

# "Programa mínimo": texto EXACTO del Decreto 29/2010 de Galicia,
# apartado I.A.2.3 (confirmado por investigacion independiente, cita
# textual): "La vivienda constará, como mínimo, de una estancia más una
# cocina, un cuarto de baño, un lavadero, un tendedero y un espacio de
# almacenamiento general." nhv.lua no modela este apartado en absoluto.
#
# CORRECCION: una primera version de este validador solo exigia
# salon+cocina+bano, basada en el estandar generico CTE/Orden de 1944
# (valido para otras comunidades) en vez de buscar el texto especifico
# de Galicia primero -- el usuario detecto que algo no cuadraba, y al
# revisar la fuente exacta se confirmo que faltaban tres piezas enteras
# (lavadero, tendedero, almacenamiento general).
#
# Mapeo de "estancia" -> RoomType.LIVING_ROOM: el propio decreto exige
# en otro apartado (A.3.2.1.a) que exista "al menos una estancia mayor"
# en toda vivienda; este proyecto ya adopto como convencion que la
# estancia mayor es siempre el salon (confirmado explicitamente por el
# usuario en una sesion anterior), asi que "una estancia" en el programa
# minimo se interpreta como ese mismo salon, no como categoria generica.


class ViviendaMinimaValidator(ConstraintValidatorPort):
    """Comprueba que el Program contenga las seis piezas del programa
    mínimo legal (Decreto 29/2010, I.A.2.3): salón, cocina, baño
    completo, lavadero, tendedero y almacenamiento general. Sin este
    validador, un `Program` con, por ejemplo, solo un garaje, pasaría el
    resto de los validadores del composite sin ningún aviso."""

    _REQUIRED = [
        (RoomType.LIVING_ROOM, "un salón (LIVING_ROOM) -- una estancia de estar-comedor"),
        (RoomType.KITCHEN, "una cocina (KITCHEN)"),
        (RoomType.BATHROOM, "un baño completo (BATHROOM) -- un aseo (TOILET) no sustituye este requisito"),
        (RoomType.LAUNDRY, "un lavadero (LAUNDRY)"),
        (RoomType.DRYING_AREA, "un tendedero (DRYING_AREA)"),
        (RoomType.STORAGE, "un espacio de almacenamiento general (STORAGE)"),
    ]

    def validate(self, layout: Layout) -> ValidationResult:
        types_present = {r.room_type for r in layout.rooms}
        violations: List[str] = [
            f"Programa mínimo incompleto: falta {descripcion}"
            for room_type, descripcion in self._REQUIRED
            if room_type not in types_present
        ]
        return ValidationResult(violations=violations)
