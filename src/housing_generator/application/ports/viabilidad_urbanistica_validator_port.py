from abc import ABC, abstractmethod
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.application.dto.validation_result import ValidationResult


class ViabilidadUrbanisticaValidatorPort(ABC):
    """Comprueba viabilidad urbanística (edificabilidad, ocupación,
    altura, frente) contra superficies DECLARADAS -- a diferencia de
    `ConstraintValidatorPort`, no necesita un `Layout` ya colocado con
    geometría real, se ejecuta ANTES de generar nada. Ver
    [ARCH:viabilidad-urbanistica]."""

    @abstractmethod
    def validate(self, program: Program, lot: Lot, num_plantas: int) -> ValidationResult:
        ...
