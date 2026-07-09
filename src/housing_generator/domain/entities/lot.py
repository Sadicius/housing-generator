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

    `retranqueo_incremento_por_planta_m`: **[RESUELTO]** retomado de
    docs/CONTINUIDAD.md ("reducir el contorno edificable planta a
    planta"). Investigacion externa confirmada antes de implementar
    (Devans, "Procedural Generation For Dummies: Building Footprints"):
    la tecnica estandar en generacion procedural de edificios es
    "subtractive generation... empezando por la forma de la parcela y
    recortando trozos -- un buen enfoque para generar huellas de plantas
    superiores, ya que la segunda planta suele parecerse a la primera"
    -- con una red de seguridad si el area resultante queda demasiado
    pequena (patron `MinArea{Action:Shrink, Fallback:...}` del mismo
    articulo). Aplicado aqui via `GenerateBuildingUseCase`, que encoge
    progresivamente (`buffer(-incremento)`, mismo mecanismo que
    `buildable_area`) el area de cada planta respecto a la de abajo,
    saltando el encogimiento de esa planta si el resultado no alcanzaria
    para las estancias declaradas (misma huella que la planta inferior
    en ese caso -- la otra opcion valida segun la propia investigacion:
    "copia exacta O subconjunto", nunca invalido, nunca silenciosamente
    mas pequeño de lo necesario). `None` (por defecto) preserva el
    comportamiento anterior: todas las plantas comparten el mismo
    contorno edificable, sin decrecer.

    Vivienda PAREADA/ADOSADA (con medianeras en 1 o 2 lados) queda fuera
    de este alcance por ahora -- ver docs/architecture.md.
    """
    boundary: Boundary
    entrance_side: str = "south"   # north | south | east | west
    street_side: str = "south"
    retranqueo_m: Optional[float] = None
    retranqueo_incremento_por_planta_m: Optional[float] = None

    @property
    def buildable_area(self) -> Boundary:
        """Area edificable real: la parcela reducida hacia dentro por el
        retranqueo declarado. Si no hay retranqueo, coincide con la
        parcela completa."""
        if self.retranqueo_m is None or self.retranqueo_m <= 0:
            return self.boundary
        reduced = self.boundary.polygon.buffer(-self.retranqueo_m)
        return Boundary(polygon=reduced)
