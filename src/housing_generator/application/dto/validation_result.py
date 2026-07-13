from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de validar un Layout contra una restricción. Separa
    `violations` (no se cumple) de `warnings` (no verificable con los
    datos disponibles -- tercera categoría, no aprobado por defecto ni
    bloqueo). Ver [ARCH:validation-result].
    """
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0

    @staticmethod
    def merge(results: List["ValidationResult"]) -> "ValidationResult":
        violations: List[str] = []
        warnings: List[str] = []
        for result in results:
            violations.extend(result.violations)
            warnings.extend(result.warnings)
        return ValidationResult(violations=violations, warnings=warnings)
