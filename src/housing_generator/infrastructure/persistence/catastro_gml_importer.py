"""Importador de GML de parcela catastral (formato INSPIRE Cadastral
Parcels 4.0, el que entrega la Sede Electrónica del Catastro español).
Investigado con datos reales antes de implementar (2 parcelas reales
de Galicia, una sin edificar y otra edificada) -- ver
`docs/CONTINUIDAD.md`, entrada "Importación de parcela real desde
Catastro (Fase A)".

Deliberadamente SIN GDAL/OGR: el GML de parcela es XML simple y bien
estructurado, `xml.etree.ElementTree` (librería estándar, sin
dependencias nuevas) es suficiente para extraer lo que necesitamos --
GDAL sería la herramienta correcta para reproyecciones o conversión
de formatos complejos, que no es lo que hace falta aquí.

Ver [ARCH:catastro-gml-importer].
"""

import logging
import math
import xml.etree.ElementTree as ET
from typing import NamedTuple
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate

logger = logging.getLogger(__name__)

NS = {
    "gml": "http://www.opengis.net/gml/3.2",
    "cp": "http://inspire.ec.europa.eu/schemas/cp/4.0",
}


class ParcelaImportada(NamedTuple):
    """Resultado de importar un GML de parcela catastral.

    `poligono`/`rectangulo_trabajo`: en coordenadas LOCALES (origen
    trasladado al mínimo x,y del polígono real), Y ROTADOS para que
    el rectángulo de trabajo quede alineado a ejes -- el sistema de
    coordenadas que usa de verdad el generador (`box(0,0,ancho,fondo)`).
    Las coordenadas UTM absolutas (cientos de miles/millones) no
    sirven directamente para nuestro `Lot`, que trabaja en
    coordenadas relativas.

    `poligono_orientacion_real`: el MISMO polígono, trasladado pero
    SIN rotar -- conserva la orientación real respecto al norte
    (las coordenadas UTM de origen ya están orientadas a norte, la
    traslación no cambia ángulos). Uso exclusivo para VISUALIZACIÓN
    (Zona 0 del dashboard) -- el generador nunca lo usa, sigue
    trabajando con `poligono`/`rectangulo_trabajo` alineados. Hallazgo
    real del usuario: mostrar la versión rotada "no es adecuado para
    una buena interpretación" de la parcela real. Ver
    [ARCH:parcela-orientacion-real].

    `area_declarada_m2`: la que trae el propio archivo
    (`cp:areaValue`) -- NO se usa para los cálculos, solo para el
    aviso de discrepancia. `area_calculada_m2`: recalculada del
    polígono real, es la que SÍ alimenta edificabilidad/ocupación --
    mismo criterio que usa el propio Catastro para validar sus
    propios ficheros (la superficie declarada debe coincidir,
    redondeada al m², con la superficie de la geometría).
    """

    referencia_catastral: str
    area_declarada_m2: float
    area_calculada_m2: float
    poligono: Polygon
    rectangulo_trabajo: Polygon
    poligono_orientacion_real: Polygon

    @property
    def discrepancia_area_pct(self) -> float:
        if self.area_declarada_m2 <= 0:
            return 0.0
        return (
            abs(self.area_calculada_m2 - self.area_declarada_m2)
            / self.area_declarada_m2
            * 100
        )


def importar_parcela_gml(contenido: str) -> ParcelaImportada:
    """Parsea un GML de parcela catastral (INSPIRE CadastralParcels
    4.0) y devuelve su polígono real + rectángulo de trabajo (OBB),
    ambos en coordenadas locales.

    El "rectángulo de trabajo" es el rectángulo mínimo ORIENTADO que
    contiene el polígono (`minimum_rotated_rectangle` de shapely) --
    NO el rectángulo alineado a ejes. Confirmado con las 2 parcelas
    reales investigadas: el alineado a ejes solo aprovecha ~53% de su
    propia área (parcelas genuinamente irregulares), el orientado
    aprovecha 88-94% -- mucho mejor ajuste, sin depender de ninguna
    librería de "rectángulo inscrito óptimo" (las 3 investigadas
    fueron descartadas: lentas, rotas, o sin mantener). El rectángulo
    de trabajo SÍ puede sobresalir ligeramente del polígono real en
    las esquinas -- responsabilidad de quien construye, no una
    garantía geométrica absoluta, ver aviso en la Zona 0 del
    dashboard.

    Lanza `ValueError` si el GML no tiene el esquema esperado (no es
    un GML de parcela catastral válido).
    """
    try:
        root = ET.fromstring(contenido)
    except ET.ParseError as e:
        raise ValueError(f"El archivo no es un XML válido: {e}") from e

    referencia_el = root.find(".//cp:nationalCadastralReference", NS)
    area_el = root.find(".//cp:areaValue", NS)
    pos_list_el = root.find(".//gml:posList", NS)

    if pos_list_el is None or pos_list_el.text is None:
        raise ValueError(
            "No se encontró <gml:posList> -- este archivo no parece ser un GML de "
            "parcela catastral (formato INSPIRE CadastralParcels) válido."
        )

    valores = pos_list_el.text.split()
    if len(valores) % 2 != 0:
        raise ValueError(
            f"<gml:posList> tiene un numero impar de valores ({len(valores)}) -- "
            "no se puede agrupar en pares (x,y), el archivo esta corrupto o truncado."
        )
    try:
        coords_utm = [
            (float(valores[i]), float(valores[i + 1]))
            for i in range(0, len(valores), 2)
        ]
    except ValueError as e:
        raise ValueError(f"<gml:posList> contiene un valor no numerico: {e}") from e

    if len(coords_utm) < 3:
        raise ValueError(
            f"<gml:posList> solo tiene {len(coords_utm)} punto(s) -- "
            "hacen falta al menos 3 para formar un poligono."
        )

    poligono_utm = Polygon(coords_utm)
    if not poligono_utm.is_valid or poligono_utm.area <= 0:
        raise ValueError(
            "El poligono descrito por <gml:posList> es invalido o tiene area nula "
            "(puntos colineales o duplicados) -- no se puede usar como parcela."
        )

    minx, miny, _, _ = poligono_utm.bounds
    poligono_local = translate(poligono_utm, xoff=-minx, yoff=-miny)
    rectangulo_trabajo = poligono_local.minimum_rotated_rectangle
    if rectangulo_trabajo.geom_type != "Polygon":
        # poligono degenerado (practicamente una linea) -- el rectangulo
        # minimo orientado colapsa a Point/LineString, sin `.exterior.coords`
        # en 5 puntos utilizable mas abajo.
        raise ValueError(
            f"El rectangulo de trabajo calculado es '{rectangulo_trabajo.geom_type}', "
            "no un poligono -- la parcela es geometricamente degenerada (practicamente "
            "una linea), no se puede usar."
        )

    # BUG REAL encontrado al verificar la generacion de extremo a
    # extremo (confirmado con un caso real: estancias generadas fuera
    # del poligono real, incluso fuera del propio poligono en bruto,
    # no solo del margen de retranqueo): `minimum_rotated_rectangle`
    # normalmente NO esta alineado a ejes (rotado -- confirmado hasta
    # 151.9 grados en un caso real), pero el generador coloca
    # estancias en un rectangulo `box(0,0,ancho,fondo)` SIEMPRE
    # alineado a ejes, empezando en el origen. Sin esta correccion,
    # `poligono` y `rectangulo_trabajo` quedaban en un sistema de
    # coordenadas distinto al que usa de verdad el generador --
    # geometricamente inconsistentes entre si, aunque cada uno por
    # separado fuera correcto. Corregido: se rota TODO (poligono +
    # OBB) para que el OBB quede alineado a ejes con su esquina en
    # (0,0) -- el mismo sistema que usara `box(0,0,ancho_m,fondo_m)`
    # al construir el Lot real. Ver [ARCH:parcela-real].
    obb_coords = list(rectangulo_trabajo.exterior.coords)
    angulo_obb_deg = math.degrees(
        math.atan2(
            obb_coords[1][1] - obb_coords[0][1],
            obb_coords[1][0] - obb_coords[0][0],
        )
    )
    origen_rotacion = obb_coords[0]
    poligono_rotado = rotate(poligono_local, -angulo_obb_deg, origin=origen_rotacion)
    obb_rotado = rotate(rectangulo_trabajo, -angulo_obb_deg, origin=origen_rotacion)

    minx2, miny2, _, _ = obb_rotado.bounds
    poligono_alineado = translate(poligono_rotado, xoff=-minx2, yoff=-miny2)
    obb_alineado = translate(obb_rotado, xoff=-minx2, yoff=-miny2)

    return ParcelaImportada(
        referencia_catastral=(
            referencia_el.text
            if referencia_el is not None and referencia_el.text
            else ""
        ),
        area_declarada_m2=(
            float(area_el.text)
            if area_el is not None and area_el.text
            else poligono_alineado.area
        ),
        area_calculada_m2=poligono_alineado.area,
        poligono=poligono_alineado,
        rectangulo_trabajo=obb_alineado,
        poligono_orientacion_real=poligono_local,
    )
