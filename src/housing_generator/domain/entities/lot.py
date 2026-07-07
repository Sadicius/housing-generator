from dataclasses import dataclass
from typing import Optional
from housing_generator.domain.value_objects.boundary import Boundary


@dataclass(frozen=True)
class Lot:
    """Solar/parcela edificable, con datos simplificados de orientacion.

    `retranqueo_m`: separacion minima obligatoria a los lindes de
    parcela (vivienda unifamiliar AISLADA -- sin medianeras, todos los
    lados pueden tener contacto exterior real). NO es un valor fijo de
    la normativa de habitabilidad: el propio Decreto 29/2010 remite esta
    cuestion a "la legislacion urbanistica vigente segun la
    clasificacion del suelo" (Ley 2/2016 do solo de Galicia + PXOM de
    cada ayuntamiento) -- por eso es un parametro que declara quien usa
    este proyecto, no una constante que este proyecto pueda asumir.
    `None` significa "sin retranqueo declarado", y el area edificable
    coincide con la parcela completa (comportamiento actual, sin cambios).

    Vivienda PAREADA/ADOSADA (con medianeras en 1 o 2 lados) queda fuera
    de este alcance por ahora -- ver docs/architecture.md.
    """
    boundary: Boundary
    entrance_side: str = "south"   # north | south | east | west
    street_side: str = "south"
    retranqueo_m: Optional[float] = None

    @property
    def buildable_area(self) -> Boundary:
        """Area edificable real: la parcela reducida hacia dentro por el
        retranqueo declarado. Si no hay retranqueo, coincide con la
        parcela completa."""
        if self.retranqueo_m is None or self.retranqueo_m <= 0:
            return self.boundary
        reduced = self.boundary.polygon.buffer(-self.retranqueo_m)
        return Boundary(polygon=reduced)
