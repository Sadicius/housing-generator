from dataclasses import dataclass
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot


@dataclass(frozen=True)
class GenerationRequest:
    """DTO de entrada del caso de uso GenerateLayoutUseCase."""

    program: Program
    lot: Lot
    max_attempts: int = 1
