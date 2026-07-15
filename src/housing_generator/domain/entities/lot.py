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

    Parámetros urbanísticos (Zona 0, "Introducción de datos") -- todos
    opcionales, mismo convenio que `retranqueo_m`: `None` = sin esa
    restricción concreta. Investigados contra fuentes reales (varios
    PGOU municipales, no solo teoría) antes de añadirlos -- son el
    conjunto estándar de una ficha urbanística real, confirmado
    también contra el framework académico REGEN (2026): edificabilidad
    y ocupación son restricciones SEPARADAS (una sobre el techo total,
    otra sobre la huella en planta), no una sola cosa.

    `coeficiente_edificabilidad`: m² de techo permitidos por m² de
    parcela (m²t/m²s) -- limita la SUMA de superficies de todas las
    plantas.
    `ocupacion_maxima_pct`: % de la parcela que puede cubrir la huella
    en planta (0-100).
    `altura_maxima_plantas`: número máximo de plantas sobre rasante.
    `frente_minimo_m`: ancho mínimo de fachada al vial (`street_side`).

    Ver [ARCH:lot].
    """
    boundary: Boundary
    entrance_side: str = "south"   # north | south | east | west
    street_side: str = "south"
    retranqueo_m: Optional[float] = None
    retranqueo_incremento_por_planta_m: Optional[float] = None
    medianera_sides: FrozenSet[str] = frozenset()
    coeficiente_edificabilidad: Optional[float] = None
    ocupacion_maxima_pct: Optional[float] = None
    altura_maxima_plantas: Optional[int] = None
    frente_minimo_m: Optional[float] = None

    @property
    def frente_actual_m(self) -> float:
        """Ancho real de la parcela en el lado que da a la calle
        (`street_side`) -- para parcela rectangular simple, el lado
        norte/sur mide lo mismo que el ancho en X; el lado este/oeste,
        lo mismo que el fondo en Y. Ver [ARCH:lot]."""
        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        if self.street_side in ("north", "south"):
            return maxx - minx
        return maxy - miny

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
