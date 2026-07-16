import pytest
from shapely.geometry import box
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.boundary import Boundary


def test_no_retranqueo_buildable_area_equals_full_parcel():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))
    assert lot.buildable_area.polygon.equals(lot.boundary.polygon)


def test_retranqueo_shrinks_buildable_area():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)

    assert lot.buildable_area.area_m2 < lot.boundary.area_m2
    # un cuadrado de 20x20 reducido 3m por cada lado -> 14x14 = 196
    assert lot.buildable_area.area_m2 == pytest.approx(14 * 14, rel=0.01)


def test_buildable_area_stays_within_full_parcel():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
    assert lot.boundary.contains(lot.buildable_area)


def test_zero_retranqueo_behaves_like_none():
    lot_none = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))
    lot_zero = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=0.0)
    assert lot_zero.buildable_area.polygon.equals(lot_none.buildable_area.polygon)


def test_excessive_retranqueo_can_collapse_buildable_area():
    # un retranqueo mayor que la mitad del lado mas corto colapsa el area
    # edificable -- esto es correcto (la parcela es demasiado pequena
    # para ese retranqueo), no un bug: se documenta el comportamiento.
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 5, 5)), retranqueo_m=3.0)
    assert lot.buildable_area.area_m2 == 0


def test_no_medianera_behaves_like_before():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
    assert lot.buildable_area.area_m2 == pytest.approx(14 * 14, rel=0.01)
    assert lot.medianera_boundary_segments() == []


def test_one_medianera_side_has_no_retranqueo_on_that_side_only():
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 15)), retranqueo_m=3.0,
        medianera_sides=frozenset({"east"}),
    )
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, miny, maxy) == (3.0, 3.0, 12.0)  # retranqueo normal en oeste/sur/norte
    assert maxx == 20.0  # SIN retranqueo en el lado de medianera (este)


def test_two_medianera_sides_adosada():
    # vivienda adosada tipica: medianeras en dos lados opuestos (este y oeste)
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 15)), retranqueo_m=3.0,
        medianera_sides=frozenset({"east", "west"}),
    )
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, maxx) == (0.0, 20.0)  # sin retranqueo en ninguno de los dos lados de medianera
    assert (miny, maxy) == (3.0, 12.0)  # retranqueo normal en sur/norte


def test_medianera_boundary_segments_use_original_lot_position():
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 15)), retranqueo_m=3.0,
        medianera_sides=frozenset({"east"}),
    )
    segments = lot.medianera_boundary_segments()
    assert len(segments) == 1
    assert list(segments[0].coords) == [(20.0, 0.0), (20.0, 15.0)]  # linde ORIGINAL, no encogido


def test_medianera_without_retranqueo_still_removes_that_side():
    # medianera sin retranqueo declarado (r=0 en el resto de lados) --
    # el lado de medianera sigue sin retranqueo (coincide con el resto
    # en este caso), pero medianera_boundary_segments() sigue poblado
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 15)), medianera_sides=frozenset({"north"}))
    assert lot.buildable_area.polygon.equals(lot.boundary.polygon)  # sin retranqueo, coincide igual
    assert len(lot.medianera_boundary_segments()) == 1


def _poligono_real_de_fixture():
    # misma parcela real usada en test_catastro_gml_importer.py --
    # 349.2m2, genuinamente irregular (confirmado en la investigacion:
    # solo 53.6% de su rectangulo alineado a ejes).
    from pathlib import Path
    from housing_generator.infrastructure.persistence.catastro_gml_importer import importar_parcela_gml
    fixture = Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    resultado = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    return resultado.poligono


def test_area_edificable_real_without_poligono_real_matches_buildable_area():
    # caso manual de siempre -- sin poligono_real, coincide exactamente
    # con buildable_area, ningun cambio de comportamiento.
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
    assert lot.area_edificable_real.polygon.equals(lot.buildable_area.polygon)


def test_area_edificable_real_uses_the_real_polygon_not_the_bounding_box():
    poligono_real = _poligono_real_de_fixture()
    minx, miny, maxx, maxy = poligono_real.bounds
    lot = Lot(boundary=Boundary(polygon=box(minx, miny, maxx, maxy)), poligono_real=poligono_real)

    # sin retranqueo: coincide con el poligono real (349.2m2), NO con
    # el rectangulo envolvente (que seria mayor)
    assert lot.area_edificable_real.polygon.area == pytest.approx(poligono_real.area)
    assert lot.area_edificable_real.polygon.area < box(minx, miny, maxx, maxy).area


def test_area_edificable_real_applies_retranqueo_via_buffer_on_real_polygon():
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, retranqueo_m=3.0)

    area_reducida = lot.area_edificable_real.polygon.area
    assert area_reducida < poligono_real.area  # se redujo de verdad
    assert area_reducida == pytest.approx(154.0, abs=5.0)  # verificado a mano en la investigacion


def test_area_edificable_real_collapses_gracefully_on_excessive_retranqueo():
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, retranqueo_m=15.0)

    assert lot.area_edificable_real.polygon.is_empty


def test_area_edificable_real_stays_within_the_true_legal_boundary():
    # propiedad de seguridad central de toda esta pieza: el area
    # edificable real NUNCA debe salirse del poligono real, a
    # diferencia del rectangulo de trabajo (que si puede sobresalir,
    # confirmado en la investigacion -- hasta 49m2 en un caso real).
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, retranqueo_m=2.0)

    interseccion = lot.area_edificable_real.polygon.intersection(poligono_real)
    assert interseccion.area == pytest.approx(lot.area_edificable_real.polygon.area, abs=1e-6)
