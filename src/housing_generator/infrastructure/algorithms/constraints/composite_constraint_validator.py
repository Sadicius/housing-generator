from typing import List
from housing_generator.application.ports.constraint_validator_port import (
    ConstraintValidatorPort,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout


class CompositeConstraintValidator(ConstraintValidatorPort):
    """Ejecuta varios ConstraintValidatorPort sobre el mismo Layout y
    fusiona sus resultados (violaciones + avisos de todos, unidos).

    Permite que GenerateLayoutUseCase siga aceptando UN solo
    ConstraintValidatorPort mientras el sistema acumula validadores
    independientes (nucleo humedo, zonificacion, Tabla 1, Tabla 2...)
    sin que ninguno tenga que saber de los demas.
    """

    def __init__(self, validators: List[ConstraintValidatorPort]):
        self._validators = validators

    def validate(self, layout: Layout) -> ValidationResult:
        return ValidationResult.merge([v.validate(layout) for v in self._validators])
