from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class ValidationResult:
    """Resultado de validar un Layout contra una restriccion.

    Separa dos cosas que `nhv.lua` ya distinguia en varios sitios
    (`esEspacioExteriorDeCalidad`, y ahora `can_inscribe_square`) y que
    una simple `List[str]` de violaciones no puede expresar:

    - `violations`: la restriccion NO se cumple, con los datos disponibles.
      Un layout con violaciones se rechaza.
    - `warnings`: no se puede confirmar NI descartar el cumplimiento con
      los datos/algoritmos disponibles ("no verificable"). Nunca se trata
      como aprobado por defecto, pero tampoco bloquea la generacion como
      una violacion real -- es una tercera categoria, no un termino medio
      entre las otras dos.
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
