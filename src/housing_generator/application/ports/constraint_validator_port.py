from abc import ABC, abstractmethod
from housing_generator.domain.entities.layout import Layout
from housing_generator.application.dto.validation_result import ValidationResult


class ConstraintValidatorPort(ABC):
    """Valida un Layout contra restricciones duras/blandas."""

    @abstractmethod
    def validate(self, layout: Layout) -> ValidationResult:
        ...
