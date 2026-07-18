from pathlib import Path
import pytest
from shapely.geometry import box
from housing_generator.domain.entities.lot import retranqueo_variable_por_lado
from housing_generator.infrastructure.persistence.catastro_gml_importer import (
    importar_parcela_gml,
)


def test_rectangle_gets_exact_bounds_from_different_retranqueo_per_side():
    cuadrado = box(0, 0, 20, 20)
    resultado = retranqueo_variable_por_lado(
        cuadrado, {"south": 5, "north": 1, "east": 2, "west": 3}
    )
    minx, miny, maxx, maxy = resultado.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((3.0, 5.0, 18.0, 19.0))
    assert resultado.area == pytest.approx((18 - 3) * (19 - 5))


def test_uniform_default_matches_the_classic_buffer_exactly():
    # sin entradas especificas por lado, debe coincidir EXACTAMENTE
    # con el retranqueo uniforme de siempre (.buffer(-r)) -- confirma
    # que la funcion nueva no cambia el comportamiento del caso
    # manual mas comun cuando no se usa la funcionalidad nueva.
    cuadrado = box(0, 0, 20, 20)
    resultado = retranqueo_variable_por_lado(cuadrado, {}, retranqueo_default_m=3.0)
    esperado = cuadrado.buffer(-3.0)
    assert resultado.area == pytest.approx(esperado.area)
    assert resultado.bounds == pytest.approx(esperado.bounds)


def test_zero_retranqueo_on_all_sides_returns_the_full_polygon():
    cuadrado = box(0, 0, 20, 20)
    resultado = retranqueo_variable_por_lado(cuadrado, {}, retranqueo_default_m=0.0)
    assert resultado.area == pytest.approx(cuadrado.area)


def test_excessive_retranqueo_collapses_to_empty_polygon_not_a_crash():
    cuadrado = box(0, 0, 10, 10)
    resultado = retranqueo_variable_por_lado(
        cuadrado, {"south": 8, "north": 8}, retranqueo_default_m=0.0
    )
    assert resultado.is_empty


def test_real_irregular_parcel_produces_a_valid_smaller_polygon():
    # misma parcela real usada en el resto de la Fase A -- confirma
    # que la funcion funciona sobre un poligono genuinamente
    # irregular, no solo sobre rectangulos de prueba.
    fixture = (
        Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    )
    resultado_import = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    poligono_real = resultado_import.poligono_orientacion_real

    resultado = retranqueo_variable_por_lado(
        poligono_real, {"south": 5}, retranqueo_default_m=1.0
    )
    assert resultado.is_valid
    assert resultado.geom_type == "Polygon"
    assert 0 < resultado.area < poligono_real.area


def test_asymmetric_retranqueo_on_real_parcel_reduces_more_than_uniform_minimum():
    # el lado con mayor retranqueo (south=5) debe reducir mas area que
    # si todos los lados usaran el minimo (1) -- confirma que el
    # retranqueo por lado tiene efecto real, no solo se acepta y se
    # ignora en la practica.
    fixture = (
        Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    )
    resultado_import = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    poligono_real = resultado_import.poligono_orientacion_real

    con_asimetria = retranqueo_variable_por_lado(
        poligono_real, {"south": 5}, retranqueo_default_m=1.0
    )
    todo_uniforme_bajo = retranqueo_variable_por_lado(
        poligono_real, {}, retranqueo_default_m=1.0
    )
    assert con_asimetria.area < todo_uniforme_bajo.area
