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
import xml.etree.ElementTree as ET
from typing import NamedTuple
from shapely.geometry import Polygon
from shapely.affinity import translate

NS = {
    "gml": "http://www.opengis.net/gml/3.2",
    "cp": "http://inspire.ec.europa.eu/schemas/cp/4.0",
}


class ParcelaImportada(NamedTuple):
    """Resultado de importar un GML de parcela catastral.

    `poligono`/`rectangulo_trabajo`: en coordenadas LOCALES (origen
    trasladado al mínimo x,y del polígono real) -- las coordenadas
    UTM absolutas (cientos de miles/millones) no sirven directamente
    para nuestro `Lot`, que trabaja en coordenadas relativas.

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

    @property
    def discrepancia_area_pct(self) -> float:
        if self.area_declarada_m2 <= 0:
            return 0.0
        return abs(self.area_calculada_m2 - self.area_declarada_m2) / self.area_declarada_m2 * 100


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
    coords_utm = [(float(valores[i]), float(valores[i + 1])) for i in range(0, len(valores), 2)]
    poligono_utm = Polygon(coords_utm)

    minx, miny, _, _ = poligono_utm.bounds
    poligono_local = translate(poligono_utm, xoff=-minx, yoff=-miny)
    rectangulo_trabajo = poligono_local.minimum_rotated_rectangle

    return ParcelaImportada(
        referencia_catastral=referencia_el.text if referencia_el is not None and referencia_el.text else "",
        area_declarada_m2=float(area_el.text) if area_el is not None and area_el.text else poligono_local.area,
        area_calculada_m2=poligono_local.area,
        poligono=poligono_local,
        rectangulo_trabajo=rectangulo_trabajo,
    )
