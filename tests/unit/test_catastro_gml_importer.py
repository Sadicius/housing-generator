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
    # hallazgo real de la investigacion: ambas parcelas reales ocupan
    # solo ~53% de su rectangulo alineado a ejes -- confirma que no
    # son aproximables a un rectangulo simple sin perder informacion
    # real. Si esto alguna vez deja de ser cierto (p.ej. cambian los
    # datos de prueba), es una senal de que hay que revisar el test,
    # no solo el codigo.
    from shapely.geometry import box
    resultado = importar_parcela_gml(_leer("parcela_sin_edificar.gml"))
    minx, miny, maxx, maxy = resultado.poligono.bounds
    rect_envolvente = box(minx, miny, maxx, maxy)
    aprovechamiento_aabb = resultado.poligono.area / rect_envolvente.area
    assert aprovechamiento_aabb < 0.6  # genuinamente irregular


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
