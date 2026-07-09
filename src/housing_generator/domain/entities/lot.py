from dataclasses import dataclass
from typing import FrozenSet, List, Optional
from shapely.geometry import box, LineString, Polygon
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

    `medianera_sides`: **[RESUELTO]** retomado de docs/CONTINUIDAD.md
    ("vivienda pareada/adosada"). Vivienda con 1 o 2 lados en medianera
    (pared compartida con la parcela vecina, sin separacion): esos lados
    NO llevan retranqueo (la edificacion llega hasta el linde) y NO
    cuentan como contacto exterior real para habitabilidad (una pared
    de medianera no tiene luz ni ventilacion propia -- confirma
    `ExteriorContactValidator`). Subconjunto de
    `{"north","south","east","west"}`; vacio (por defecto) = vivienda
    AISLADA, comportamiento anterior sin cambios. Requiere parcela
    rectangular con lados ortogonales (norte=+y, sur=-y, este=+x,
    oeste=-x) -- misma simplificacion geometrica que el resto del
    proyecto (particion guillotina, todo rectangular).
    """
    boundary: Boundary
    entrance_side: str = "south"   # north | south | east | west
    street_side: str = "south"
    retranqueo_m: Optional[float] = None
    retranqueo_incremento_por_planta_m: Optional[float] = None
    medianera_sides: FrozenSet[str] = frozenset()

    @property
    def buildable_area(self) -> Boundary:
        """Area edificable real: la parcela reducida hacia dentro por el
        retranqueo declarado -- EXCEPTO en los lados de medianera
        (`medianera_sides`), donde la edificacion llega hasta el linde
        sin retranqueo. Sin retranqueo Y sin medianeras, coincide con la
        parcela completa (comportamiento original sin cambios)."""
        if (self.retranqueo_m is None or self.retranqueo_m <= 0) and not self.medianera_sides:
            return self.boundary

        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        r = self.retranqueo_m or 0.0
        new_minx = minx if "west" in self.medianera_sides else minx + r
        new_maxx = maxx if "east" in self.medianera_sides else maxx - r
        new_miny = miny if "south" in self.medianera_sides else miny + r
        new_maxy = maxy if "north" in self.medianera_sides else maxy - r

        if new_minx >= new_maxx or new_miny >= new_maxy:
            # retranqueo excesivo: colapsa a vacio, no a un rectangulo
            # invertido -- mismo comportamiento que el buffer(-x) previo
            # cuando el retranqueo superaba la mitad de la parcela.
            return Boundary(polygon=Polygon())
        return Boundary(polygon=box(new_minx, new_miny, new_maxx, new_maxy))

    def medianera_boundary_segments(self) -> List[LineString]:
        """Los segmentos de linde que son medianera (posicion ORIGINAL de
        la parcela, no del area edificable ya encogida) -- usado por
        `count_exterior_sides` para no contar contacto con estos lados
        como contacto exterior real."""
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
