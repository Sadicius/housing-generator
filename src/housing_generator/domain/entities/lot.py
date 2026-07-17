import math
from dataclasses import dataclass, field
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

    `retranqueo_por_lado`: dict opcional con claves de
    `{"north","south","east","west"}`, retranqueo específico en
    metros para ESE lado -- lados sin entrada usan `retranqueo_m`
    (el valor único de siempre). Hallazgo real del usuario: "el
    retranqueo (m) no se puede desplegar para indicar los diferentes
    retranqueos a cada colindante o vial" -- misma crítica que ya
    había señalado el arquitecto consultado antes. Funciona igual
    para el rectángulo manual que para `poligono_real` (cada lado se
    clasifica por la dirección cardinal más cercana a su normal
    saliente). Vacío (por defecto) = mismo comportamiento uniforme de
    siempre, sin ningún cambio. Ver [ARCH:retranqueo-variable].

    `fondo_edificacion_m`: profundidad máxima edificable medida desde
    el lindero de `street_side` (el vial) hacia el interior de la
    parcela -- `None` = sin restricción de fondo. Hallazgo real del
    usuario: "no existe apartado de fondo de edificación, tampoco
    está representado en el visor" -- mismo concepto que ya había
    señalado el arquitecto consultado antes ("aunque tengas metros
    cuadrados de sobra, no puedes construir a más de 12 o 15 metros
    de profundidad desde el vial"). Se mide desde el lindero real de
    la parcela (antes de aplicar retranqueo), el convenio profesional
    habitual. Para `poligono_real` (parcela irregular), se usa el
    lado del rectángulo envolvente en la dirección de `street_side`
    como referencia -- aproximación simple documentada, no sigue el
    contorno irregular exacto del lindero de calle real. Ver
    [ARCH:fondo-edificacion].

    `linea_edificacion_m`: retranqueo MÍNIMO obligatorio desde el
    lindero de `street_side` (reserva municipal, p.ej. ensanche futuro
    de la vía) -- `None` = sin esa reserva. A diferencia de
    `retranqueo_m`/`retranqueo_por_lado` (elección del arquitecto para
    separarse de los linderos), este valor lo fija el PXOM del
    ayuntamiento y es un MÍNIMO: si el retranqueo que el arquitecto ya
    declaró en el lado de calle es mayor, no cambia nada; si es menor
    (o no declaró ninguno), se usa este valor en su lugar SOLO en ese
    lado -- el resto de lados conservan su propio retranqueo. Nunca se
    asume un valor por defecto (mismo principio que el resto de
    parámetros urbanísticos): siempre lo aporta el usuario desde su
    ficha urbanística real, nunca se infiere del catastro. Ver
    [ARCH:linea-edificacion].

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
    retranqueo_por_lado: dict = field(default_factory=dict)
    fondo_edificacion_m: Optional[float] = None
    linea_edificacion_m: Optional[float] = None

    def _clip_fondo_edificacion(self, poligono: Polygon, poligono_referencia: Polygon) -> Polygon:
        """Recorta `poligono` para que no sobrepase `fondo_edificacion_m`
        medido desde el lindero de `street_side` de `poligono_referencia`
        (la parcela real, sin reducir por retranqueo -- el convenio
        profesional habitual). Sin `fondo_edificacion_m`, no hace nada.
        Ver [ARCH:fondo-edificacion]."""
        if self.fondo_edificacion_m is None or self.fondo_edificacion_m <= 0:
            return poligono
        minx, miny, maxx, maxy = poligono_referencia.bounds
        f = self.fondo_edificacion_m
        if self.street_side == "south":
            limite = box(minx - 1, miny, maxx + 1, miny + f)
        elif self.street_side == "north":
            limite = box(minx - 1, maxy - f, maxx + 1, maxy + 1)
        elif self.street_side == "east":
            limite = box(maxx - f, miny - 1, maxx + 1, maxy + 1)
        else:  # west
            limite = box(minx - 1, miny - 1, minx + f, maxy + 1)
        recortado = poligono.intersection(limite)
        if recortado.is_empty or recortado.geom_type != "Polygon":
            return Polygon()
        return recortado

    def _por_lado_efectivo(self) -> dict:
        """`retranqueo_por_lado` fusionado con `linea_edificacion_m` --
        el lado de `street_side` usa el MAYOR de los dos (la reserva
        municipal nunca reduce un retranqueo que el arquitecto ya
        declaró más generoso), el resto de lados quedan sin tocar.
        Vacío si ninguno de los dos está en uso -- mismo resultado que
        antes de introducir `linea_edificacion_m`. Ver
        [ARCH:linea-edificacion], [ARCH:retranqueo-variable]."""
        por_lado = dict(self.retranqueo_por_lado)
        if self.linea_edificacion_m is not None and self.linea_edificacion_m > 0:
            actual = por_lado.get(self.street_side, self.retranqueo_m or 0.0)
            por_lado[self.street_side] = max(actual, self.linea_edificacion_m)
        return por_lado

    @property
    def area_edificable_real(self) -> Boundary:
        """Área edificable de verdad: si hay `poligono_real`
        (importado), es ESE polígono reducido por retranqueo vía
        `.buffer(-r)` (preciso para forma irregular, respeta los
        lindes reales) -- NO el rectángulo `box()` de `buildable_area`,
        que puede sobresalir del polígono real. Si no hay
        `poligono_real` (caso manual), coincide exactamente con
        `buildable_area`. Si `retranqueo_por_lado` tiene entradas, o
        hay `linea_edificacion_m`, usa retranqueo variable por
        dirección cardinal en vez de uniforme (ver
        `_por_lado_efectivo`). `fondo_edificacion_m`, si está
        presente, recorta el resultado además. Ver [ARCH:parcela-real],
        [ARCH:retranqueo-variable], [ARCH:fondo-edificacion],
        [ARCH:linea-edificacion]."""
        if self.poligono_real is None:
            return self.buildable_area

        por_lado_efectivo = self._por_lado_efectivo()
        if por_lado_efectivo:
            resultado = retranqueo_variable_por_lado(
                self.poligono_real, por_lado_efectivo, self.retranqueo_m or 0.0,
            )
        else:
            r = self.retranqueo_m or 0.0
            if r <= 0:
                resultado = self.poligono_real
            else:
                reducido = self.poligono_real.buffer(-r)
                resultado = reducido if not reducido.is_empty and reducido.geom_type == "Polygon" else Polygon()

        resultado = self._clip_fondo_edificacion(resultado, self.poligono_real)
        return Boundary(polygon=resultado)

    @property
    def frente_actual_m(self) -> float:
        """Ancho real de la parcela en el lado que da a la calle
        (`street_side`). Con `poligono_real` (importado, irregular):
        suma la longitud de los lados del polígono real clasificados
        como `street_side` -- NUNCA el rectángulo envolvente, que
        puede sobre/subestimar el frente real. Hallazgo real del
        arquitecto consultado: "el frente actual... está calculado
        sobre un rectángulo supuesto. Debe calcularse sobre el
        segmento real que toca el vial" -- confirmado como cierto:
        antes de esto, `frente_actual_m` ignoraba `poligono_real` por
        completo, incluso cuando existía, con el riesgo de que
        `ViabilidadUrbanisticaValidator` (frente mínimo) validara un
        valor que no corresponde a la parcela real. Sin
        `poligono_real` (caso manual, rectángulo), el lado norte/sur
        mide el ancho en X, este/oeste el fondo en Y -- equivalente
        exacto para un rectángulo simple. Ver [ARCH:lot],
        [ARCH:parcela-real]."""
        if self.poligono_real is not None:
            coords = list(self.poligono_real.exterior.coords)[:-1]
            centroide = self.poligono_real.centroid
            n = len(coords)
            total = 0.0
            for i in range(n):
                p1, p2 = coords[i], coords[(i + 1) % n]
                if clasificar_lado_cardinal(p1, p2, centroide) == self.street_side:
                    total += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            return total

        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        if self.street_side in ("north", "south"):
            return maxx - minx
        return maxy - miny

    @property
    def buildable_area(self) -> Boundary:
        """Área edificable real: parcela reducida por retranqueo,
        excepto en lados de medianera. Si `retranqueo_por_lado` tiene
        entradas, o hay `linea_edificacion_m`, usa retranqueo variable
        por dirección cardinal en vez del valor único `retranqueo_m`
        (ver `_por_lado_efectivo`). `fondo_edificacion_m`, si está
        presente, recorta el resultado además. Ver [ARCH:lot],
        [ARCH:retranqueo-variable], [ARCH:fondo-edificacion],
        [ARCH:linea-edificacion]."""
        por_lado_efectivo = self._por_lado_efectivo()
        if por_lado_efectivo:
            # medianera siempre a retranqueo 0, sin importar lo que
            # digan retranqueo_m/retranqueo_por_lado para ese lado --
            # mismo criterio que el caso uniforme de abajo.
            for lado in self.medianera_sides:
                por_lado_efectivo[lado] = 0.0
            resultado = retranqueo_variable_por_lado(
                self.boundary.polygon, por_lado_efectivo, self.retranqueo_m or 0.0,
            )
            resultado = self._clip_fondo_edificacion(resultado, self.boundary.polygon)
            return Boundary(polygon=resultado)

        if (self.retranqueo_m is None or self.retranqueo_m <= 0) and not self.medianera_sides:
            resultado = self._clip_fondo_edificacion(self.boundary.polygon, self.boundary.polygon)
            return Boundary(polygon=resultado)

        minx, miny, maxx, maxy = self.boundary.polygon.bounds
        r = self.retranqueo_m or 0.0
        new_minx = minx if "west" in self.medianera_sides else minx + r
        new_maxx = maxx if "east" in self.medianera_sides else maxx - r
        new_miny = miny if "south" in self.medianera_sides else miny + r
        new_maxy = maxy if "north" in self.medianera_sides else maxy - r

        if new_minx >= new_maxx or new_miny >= new_maxy:
            # retranqueo excesivo: colapsa a vacio, no a rectangulo invertido
            return Boundary(polygon=Polygon())
        resultado = self._clip_fondo_edificacion(box(new_minx, new_miny, new_maxx, new_maxy), self.boundary.polygon)
        return Boundary(polygon=resultado)

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



def clasificar_lado_cardinal(p1, p2, centroide) -> str:
    """Clasifica el lado p1->p2 por la dirección cardinal más cercana
    a su normal saliente (la que apunta lejos del centroide) -- no
    asume que el polígono ya esté alineado a ejes. Compartida por
    `retranqueo_variable_por_lado`, `Lot.frente_actual_m` (antes
    duplicada inline solo en la primera) y `perimeter_carving.py`
    (tallado perimetral del generador). Pública porque se reutiliza
    fuera de este módulo -- ver [ARCH:retranqueo-variable]."""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    longitud = math.hypot(dx, dy)
    if longitud < 1e-9:
        return "north"  # lado degenerado (longitud ~0): direccion arbitraria, sin efecto real
    dir_x, dir_y = dx / longitud, dy / longitud
    normal_a = (-dir_y, dir_x)
    punto_medio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
    cx = centroide.x if hasattr(centroide, "x") else centroide[0]
    cy = centroide.y if hasattr(centroide, "y") else centroide[1]
    hacia_centroide = (cx - punto_medio[0], cy - punto_medio[1])
    normal_saliente = normal_a if (normal_a[0] * hacia_centroide[0] + normal_a[1] * hacia_centroide[1]) < 0 \
        else (-normal_a[0], -normal_a[1])
    angulo_deg = math.degrees(math.atan2(normal_saliente[1], normal_saliente[0])) % 360
    if 45 <= angulo_deg < 135:
        return "north"
    elif 135 <= angulo_deg < 225:
        return "west"
    elif 225 <= angulo_deg < 315:
        return "south"
    return "east"


def retranqueo_variable_por_lado(
    poligono: Polygon, retranqueo_por_lado: dict, retranqueo_default_m: float = 0.0,
) -> Polygon:
    """Reduce `poligono` con un retranqueo DISTINTO por lado, en vez
    del retranqueo único que aplica `.buffer(-r)`. Hallazgo real del
    usuario: "el retranqueo (m) no se puede desplegar para indicar
    los diferentes retranqueos a cada colindante o vial" -- misma
    crítica que ya había señalado el arquitecto consultado antes.

    `retranqueo_por_lado`: dict con claves de `{"north","south",
    "east","west"}`, valores en metros. Lados sin entrada usan
    `retranqueo_default_m`. Funciona igual para un rectángulo simple
    (los 4 lados SON exactamente N/S/E/O) que para un polígono
    importado irregular (cada lado se CLASIFICA por la dirección
    cardinal más cercana a su normal saliente, no asume que el
    polígono ya esté alineado a ejes).

    Algoritmo: para cada lado, se calcula la línea desplazada hacia
    el interior por su propio retranqueo, extendida muy por fuera del
    polígono en ambas direcciones, y se recorta el resultado
    acumulado con el semiplano interior de esa línea -- equivalente
    geométrico real de "todos los semiplanos a la vez", no una
    aproximación visual. Devuelve `Polygon()` vacío si el retranqueo
    colapsa el área por completo (mismo criterio que
    `Lot.area_edificable_real` con el retranqueo uniforme).

    Ver [ARCH:retranqueo-variable].
    """
    coords = list(poligono.exterior.coords)[:-1]  # sin el punto de cierre repetido
    if len(coords) < 3:
        return Polygon()

    centroide = poligono.centroid
    extension = max(poligono.bounds[2] - poligono.bounds[0], poligono.bounds[3] - poligono.bounds[1]) * 20 + 100

    resultado: Polygon = poligono
    n = len(coords)
    for i in range(n):
        p1 = coords[i]
        p2 = coords[(i + 1) % n]
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        longitud = math.hypot(dx, dy)
        if longitud < 1e-9:
            continue
        dir_x, dir_y = dx / longitud, dy / longitud
        # normal saliente candidata (dos opciones perpendiculares) --
        # se queda con la que apunta LEJOS del centroide, esa es la
        # exterior de verdad para un poligono simple.
        normal_a = (-dir_y, dir_x)
        punto_medio = ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)
        hacia_centroide = (centroide.x - punto_medio[0], centroide.y - punto_medio[1])
        normal_saliente = normal_a if (normal_a[0] * hacia_centroide[0] + normal_a[1] * hacia_centroide[1]) < 0 \
            else (-normal_a[0], -normal_a[1])

        direccion = clasificar_lado_cardinal(p1, p2, centroide)
        retranqueo_lado = retranqueo_por_lado.get(direccion, retranqueo_default_m)
        if retranqueo_lado <= 0:
            continue

        normal_interior = (-normal_saliente[0], -normal_saliente[1])
        offset_p1 = (p1[0] + normal_interior[0] * retranqueo_lado, p1[1] + normal_interior[1] * retranqueo_lado)
        offset_p2 = (p2[0] + normal_interior[0] * retranqueo_lado, p2[1] + normal_interior[1] * retranqueo_lado)
        lejos_p1 = (offset_p1[0] - dir_x * extension, offset_p1[1] - dir_y * extension)
        lejos_p2 = (offset_p2[0] + dir_x * extension, offset_p2[1] + dir_y * extension)
        lejos_p2_interior = (lejos_p2[0] + normal_interior[0] * extension, lejos_p2[1] + normal_interior[1] * extension)
        lejos_p1_interior = (lejos_p1[0] + normal_interior[0] * extension, lejos_p1[1] + normal_interior[1] * extension)
        semiplano = Polygon([lejos_p1, lejos_p2, lejos_p2_interior, lejos_p1_interior])

        resultado = resultado.intersection(semiplano)
        if resultado.is_empty:
            return Polygon()

    if resultado.geom_type != "Polygon":
        return Polygon()
    return resultado
