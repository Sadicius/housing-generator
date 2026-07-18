from dataclasses import dataclass
from shapely.geometry import Polygon


@dataclass(frozen=True)
class Boundary:
    """Envuelve un Polygon de shapely: la huella de un solar o de una estancia."""

    polygon: Polygon

    @property
    def area_m2(self) -> float:
        return self.polygon.area

    @property
    def centroid(self):
        return self.polygon.centroid

    def contains(self, other: "Boundary") -> bool:
        return self.polygon.contains(other.polygon)
