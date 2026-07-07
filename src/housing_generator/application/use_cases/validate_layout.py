from housing_generator.application.ports.constraint_validator_port import ConstraintValidatorPort
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout


class ValidateLayoutUseCase:
    def __init__(self, constraint_validator: ConstraintValidatorPort):
        self._constraint_validator = constraint_validator

    def execute(self, layout: Layout) -> ValidationResult:
        return self._constraint_validator.validate(layout)
