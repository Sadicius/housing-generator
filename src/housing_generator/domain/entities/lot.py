from dataclasses import dataclass
from typing import FrozenSet, List, Optional
from shapely.geometry import box, LineString, Polygon
from housing_generator.domain.value_objects.boundary import Boundary

# Categorias reales de la Ley 2/2016 del suelo de Galicia (articulos
# 16-30), verificadas contra el texto real antes de codificarlas.
CLASIFICACIONES_SUELO_VALIDAS = frozenset({
    "urbano_consolidado",
    "urbano_no_consolidado",
    "nucleo_rural_tradicional",
    "nucleo_rural_comun",
    "urbanizable",
    "rustico_ordinario",
    "rustico_especial_proteccion",
})


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

    `poligono_real`: polígono IRREGULAR real de la parcela (mismo
    sistema de coordenadas locales que `boundary.polygon`), cuando
    procede de una importación real (Catastro) -- `None` en el caso
    manual de siempre, donde `boundary.polygon` ya ES la parcela (un
    rectángulo). Investigado con 2 parcelas reales de Galicia antes de
    añadirlo: el rectángulo de trabajo (`boundary`) puede sobresalir
    del polígono real hasta un 12-22% en las esquinas -- generar
    dentro del rectángulo sin más podría colocar estancias fuera del
    linde legal real. Ver [ARCH:parcela-real].

    `clasificacion_suelo`: subconjunto de las categorías reales de la
    Ley 2/2016 del suelo de Galicia (artículos 16-30, verificadas
    contra el texto real antes de codificarlas, no inventadas):
    `"urbano_consolidado"`, `"urbano_no_consolidado"`,
    `"nucleo_rural_tradicional"`, `"nucleo_rural_comun"`,
    `"urbanizable"`, `"rustico_ordinario"`,
    `"rustico_especial_proteccion"`. Vacío = sin clasificar. Una
    parcela puede tener más de una categoría si linda con distintas
    zonas del planeamiento -- hallazgo real del usuario ("generalmente
    tiene 1 tipo pero podría tener varios"). Campo puramente
    INFORMATIVO por ahora -- ningún validador aplica reglas distintas
    según la clasificación todavía (no hay una fuente investigada que
    codifique reglas automáticas por categoría), se guarda para
    referencia del arquitecto, no para cálculo. Ver
    [ARCH:clasificacion-suelo].

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
    poligono_real: Optional[Polygon] = None
    clasificacion_suelo: FrozenSet[str] = frozenset()

    @property
    def area_edificable_real(self) -> Boundary:
        """Área edificable de verdad: si hay `poligono_real`
        (importado), es ESE polígono reducido por retranqueo vía
        `.buffer(-r)` (preciso para forma irregular, respeta los
        lindes reales) -- NO el rectángulo `box()` de `buildable_area`,
        que puede sobresalir del polígono real. Si no hay
        `poligono_real` (caso manual), coincide exactamente con
        `buildable_area`. Ver [ARCH:parcela-real]."""
        if self.poligono_real is None:
            return self.buildable_area
        r = self.retranqueo_m or 0.0
        if r <= 0:
            return Boundary(polygon=self.poligono_real)
        reducido = self.poligono_real.buffer(-r)
        if reducido.is_empty or reducido.geom_type != "Polygon":
            return Boundary(polygon=Polygon())
        return Boundary(polygon=reducido)

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
