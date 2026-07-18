from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Dimensions:
    """Requisito de area/proporcion/altura de una estancia. Inmutable (value object)."""

    area_m2: float
    min_width_m: float = 2.0
    max_aspect_ratio: float = 2.5
    ceiling_height_m: Optional[float] = (
        None  # A.3.1.1: None = no declarada, no se asume
    )

    def __post_init__(self):
        if self.area_m2 <= 0:
            raise ValueError("area_m2 debe ser positivo")
        if self.min_width_m <= 0:
            raise ValueError("min_width_m debe ser positivo")
        if self.ceiling_height_m is not None and self.ceiling_height_m <= 0:
            raise ValueError("ceiling_height_m debe ser positivo si se declara")
