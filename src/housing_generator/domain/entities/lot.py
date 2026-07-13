from dataclasses import dataclass
from typing import FrozenSet, List, Optional
from shapely.geometry import box, LineString, Polygon
from housing_generator.domain.value_objects.boundary import Boundary


@dataclass(frozen=True)
class Lot:
    """Solar/parcela edificable, con datos simplificados de orientación.

    `retranqueo_m`: separación mínima a los lindes (vivienda AISLADA).
    `None` = sin retranqueo, área edificable = parcela completa.
    `retranqueo_incremento_por_planta_m`: encoge el contorno
    progresivamente planta a planta (`None` = todas comparten contorno).
    `medianera_sides`: subconjunto de {"north","south","east","west"}
    con pared compartida (sin retranqueo, sin contacto exterior ahí);
    vacío = vivienda aislada.

    Ver [ARCH:lot].
    """
    boundary: Boundary
    entrance_side: str = "south"   # north | south | east | west
    street_side: str = "south"
    retranqueo_m: Optional[float] = None
    retranqueo_incremento_por_planta_m: Optional[float] = None
    medianera_sides: FrozenSet[str] = frozenset()

    @property
    def buildable_area(self) -> Boundary:
        """Área edificable real: parcela reducida por retranqueo,
        excepto en lados de medianera. Ver [ARCH:lot]."""
        if (self.retranqueo_m is None or self.retranqueo_m <= 0) and not self.medianera_sides:
            return self.boundary

        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        r = self.retranqueo_m or 0.0
        new_minx = minx if "west" in self.medianera_sides else minx + r
        new_maxx = maxx if "east" in self.medianera_sides else maxx - r
        new_miny = miny if "south" in self.medianera_sides else miny + r
        new_maxy = maxy if "north" in self.medianera_sides else maxy - r

        if new_minx >= new_maxx or new_miny >= new_maxy:
            # retranqueo excesivo: colapsa a vacio, no a rectangulo invertido
            return Boundary(polygon=Polygon())
        return Boundary(polygon=box(new_minx, new_miny, new_maxx, new_maxy))

    def medianera_boundary_segments(self) -> List[LineString]:
        """Segmentos de linde en medianera (posición original de la
        parcela). Usado por `count_exterior_sides`. Ver [ARCH:lot]."""
        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        segments = []
        if "north" in self.medianera_sides:
            segments.append(LineString([(minx, maxy), (maxx, maxy)]))
        if "south" in self.medianera_sides:
            segments.append(LineString([(minx, miny), (maxx, miny)]))
        if "east" in self.medianera_sides:
            segments.append(LineString([(maxx, miny), (maxx, maxy)]))
        if "west" in self.medianera_sides:
            segments.append(LineString([(minx, miny), (minx, maxy)]))
        return segments
