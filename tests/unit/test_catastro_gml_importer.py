from pathlib import Path
import pytest
from housing_generator.infrastructure.persistence.catastro_gml_importer import importar_parcela_gml

FIXTURES = Path(__file__).parents[1] / "fixtures" / "catastro"


def _leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8")


def test_parses_real_parcela_sin_edificar_from_sede_catastro():
    # datos reales aportados por el usuario, sacados directamente de la
    # Sede Electronica del Catastro (parcela 4278011NG2947N, Galicia,
    # sin edificar). Ver [ARCH:catastro-gml-importer].
    resultado = importar_parcela_gml(_leer("parcela_sin_edificar.gml"))
    assert resultado.referencia_catastral == "4278011NG2947N"
    assert resultado.area_declarada_m2 == pytest.approx(349.0)
    assert resultado.area_calculada_m2 == pytest.approx(349.2, abs=0.5)


def test_parses_real_parcela_edificada_from_sede_catastro():
    # parcela colindante a la anterior, con edificacion real (misma
    # sesion, mismo origen de datos).
    resultado = importar_parcela_gml(_leer("parcela_edificada.gml"))
    assert resultado.referencia_catastral == "4278010NG2947N"
    assert resultado.area_declarada_m2 == pytest.approx(358.0)
    assert resultado.area_calculada_m2 == pytest.approx(358.2, abs=0.5)


def test_computed_area_matches_declared_area_within_rounding_tolerance():
    # mismo criterio de validacion que usa el propio Catastro: el area
    # declarada debe coincidir, redondeada al m2, con la superficie
    # real del poligono -- confirma que nuestros datos de prueba son
    # internamente consistentes (y que el parser no tiene un error de
    # signo/orden que desplazaria el area calculada).
    for nombre in ("parcela_sin_edificar.gml", "parcela_edificada.gml"):
        resultado = importar_parcela_gml(_leer(nombre))
        assert resultado.discrepancia_area_pct < 1.0, f"{nombre}: discrepancia excesiva"


def test_polygon_is_translated_to_local_coordinates_not_utm_absolutes():
    # las coordenadas UTM reales son del orden de 524000/4697000 --
    # inutilizables directamente para Lot (coordenadas relativas). El
    # poligono devuelto debe empezar cerca de (0,0), no en UTM.
    resultado = importar_parcela_gml(_leer("parcela_sin_edificar.gml"))
    minx, miny, maxx, maxy = resultado.poligono.bounds
    assert minx == pytest.approx(0.0, abs=0.01)
    assert miny == pytest.approx(0.0, abs=0.01)
    assert maxx < 100  # una parcela real de 349m2 no mide cientos de miles de metros


def test_real_parcels_are_genuinely_irregular_not_rectangular():
    # hallazgo real de la investigacion: la parcela real NO es un
    # rectangulo simple -- 15 vertices (no 4), confirma que no es
    # aproximable a un rectangulo sin perder informacion real. Medido
    # por numero de vertices, no por el ratio contra su propio
    # rectangulo envolvente en ejes: desde que el parser alinea el
    # poligono al sistema de coordenadas del rectangulo de trabajo
    # (OBB, corrigiendo un bug real de generacion -- ver
    # [ARCH:parcela-real]), el rectangulo alineado a ejes EN ESE
    # SISTEMA coincide con el OBB por construccion, y ese ratio ya no
    # mide irregularidad.
    resultado = importar_parcela_gml(_leer("parcela_sin_edificar.gml"))
    num_vertices = len(list(resultado.poligono.exterior.coords)) - 1  # sin contar el cierre repetido
    assert num_vertices > 4  # un rectangulo real tendria exactamente 4


def test_oriented_rectangle_is_a_much_better_fit_than_axis_aligned():
    # el hallazgo central de la investigacion: el rectangulo ORIENTADO
    # (OBB, minimum_rotated_rectangle) aprovecha 88-94% del area real,
    # muy por encima del ~53% del alineado a ejes -- confirma que es
    # la eleccion correcta para el "rectangulo de trabajo" del
    # generador, sin necesitar ninguna libreria de "rectangulo
    # inscrito optimo" (las 3 investigadas fueron descartadas).
    for nombre in ("parcela_sin_edificar.gml", "parcela_edificada.gml"):
        resultado = importar_parcela_gml(_leer(nombre))
        aprovechamiento_obb = resultado.area_calculada_m2 / resultado.rectangulo_trabajo.area
        assert aprovechamiento_obb > 0.85, f"{nombre}: OBB deberia aprovechar >85%"


def test_working_rectangle_fully_contains_the_real_polygon():
    # propiedad geometrica que SIEMPRE debe cumplirse para cualquier
    # poligono: minimum_rotated_rectangle contiene el poligono
    # original completo (nunca al reves). Comprobado por AREA de
    # interseccion, no con covers()/contains(): confirmado que ambos
    # predicados topologicos fallan aqui por ruido de punto flotante
    # puro (area fuera del rectangulo: ~1e-26 m2, insignificante) --
    # los propios vertices del poligono definen el OBB, asi que caen
    # justo en su borde, donde la aritmetica de punto flotante es mas
    # fragil. Comparar areas es la forma correcta y robusta de
    # verificar "contencion practica" en geometria de punto flotante.
    for nombre in ("parcela_sin_edificar.gml", "parcela_edificada.gml"):
        resultado = importar_parcela_gml(_leer(nombre))
        interseccion = resultado.rectangulo_trabajo.intersection(resultado.poligono)
        assert interseccion.area == pytest.approx(resultado.poligono.area, abs=1e-6)


def test_invalid_xml_raises_value_error_not_a_crash():
    with pytest.raises(ValueError, match="XML"):
        importar_parcela_gml("esto no es XML en absoluto <<<")


def test_xml_without_poslist_raises_clear_value_error():
    # un XML valido pero que no es un GML de parcela catastral --
    # mensaje claro, no un traceback interno confuso.
    with pytest.raises(ValueError, match="posList"):
        importar_parcela_gml("<?xml version='1.0'?><root><algo>otra cosa</algo></root>")


def test_missing_area_value_falls_back_to_computed_area():
    # si el archivo no trae cp:areaValue (caso raro pero posible),
    # no debe fallar -- usa el area calculada como declarada tambien,
    # de forma que discrepancia_area_pct de 0, no un error.
    gml_sin_area = _leer("parcela_sin_edificar.gml").replace(
        '<cp:areaValue uom="m2">349</cp:areaValue>', ""
    )
    resultado = importar_parcela_gml(gml_sin_area)
    assert resultado.area_declarada_m2 == pytest.approx(resultado.area_calculada_m2)
    assert resultado.discrepancia_area_pct == pytest.approx(0.0)


def test_working_rectangle_is_axis_aligned_matching_the_generators_own_frame():
    # HALLAZGO REAL, encontrado al verificar la generacion de extremo a
    # extremo: minimum_rotated_rectangle normalmente NO esta alineado a
    # ejes (rotado hasta 151.9 grados en un caso real), pero el
    # generador coloca estancias en box(0,0,ancho,fondo), SIEMPRE
    # alineado a ejes. Sin corregir esto, poligono y rectangulo_trabajo
    # quedaban en sistemas de coordenadas distintos -- geometricamente
    # inconsistentes con lo que el generador usa de verdad, causando
    # que estancias "validas" segun el validador realmente cayeran
    # fuera del poligono real. Ver [ARCH:parcela-real].
    for nombre in ("parcela_sin_edificar.gml", "parcela_edificada.gml"):
        resultado = importar_parcela_gml(_leer(nombre))
        minx, miny, maxx, maxy = resultado.rectangulo_trabajo.bounds
        from shapely.geometry import box
        rect_alineado = box(minx, miny, maxx, maxy)
        # si el OBB ya esta alineado a ejes, su area coincide con la de
        # su propio rectangulo envolvente en ejes (serian el mismo
        # objeto geometrico)
        assert resultado.rectangulo_trabajo.area == pytest.approx(rect_alineado.area, rel=0.001)
        # y su esquina inferior izquierda esta en el origen (mismo
        # convenio que box(0,0,ancho_m,fondo_m) al construir el Lot real)
        assert minx == pytest.approx(0.0, abs=0.01)
        assert miny == pytest.approx(0.0, abs=0.01)


def test_polygon_and_working_rectangle_are_in_the_same_coordinate_frame():
    # propiedad de seguridad central de todo el arreglo: el poligono
    # real y el rectangulo de trabajo deben estar en el MISMO sistema
    # de coordenadas -- verificado con la propiedad de contencion (ya
    # probada en otro test), pero aqui ademas se confirma que el
    # poligono real cae dentro de las coordenadas 0..ancho, 0..fondo
    # del rectangulo alineado, no en un sistema rotado aparte.
    resultado = importar_parcela_gml(_leer("parcela_sin_edificar.gml"))
    minx, miny, maxx, maxy = resultado.rectangulo_trabajo.bounds
    poly_minx, poly_miny, poly_maxx, poly_maxy = resultado.poligono.bounds
    assert poly_minx >= minx - 0.01
    assert poly_miny >= miny - 0.01
    assert poly_maxx <= maxx + 0.01
    assert poly_maxy <= maxy + 0.01
