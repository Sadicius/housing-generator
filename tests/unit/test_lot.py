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


def test_clasificacion_suelo_defaults_to_empty_and_accepts_real_categories():
    from housing_generator.domain.entities.lot import CLASIFICACIONES_SUELO_VALIDAS
    lot_sin_clasificar = Lot(boundary=Boundary(polygon=box(0, 0, 14, 16)))
    assert lot_sin_clasificar.clasificacion_suelo == frozenset()

    lot_con_dos = Lot(
        boundary=Boundary(polygon=box(0, 0, 14, 16)),
        clasificacion_suelo=frozenset({"urbano_consolidado", "urbanizable"}),
    )
    assert lot_con_dos.clasificacion_suelo == {"urbano_consolidado", "urbanizable"}
    assert lot_con_dos.clasificacion_suelo <= CLASIFICACIONES_SUELO_VALIDAS


def test_buildable_area_uses_retranqueo_por_lado_for_manual_rectangle():
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 20)),
        retranqueo_por_lado={"south": 5, "north": 1, "east": 2, "west": 3},
    )
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((3.0, 5.0, 18.0, 19.0))


def test_buildable_area_retranqueo_por_lado_respects_medianera_at_zero():
    # una medianera siempre debe quedar a retranqueo 0, aunque
    # retranqueo_por_lado diga otra cosa para ese lado -- mismo
    # criterio que el caso uniforme de siempre.
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 20)),
        retranqueo_por_lado={"south": 5, "east": 2},
        medianera_sides=frozenset({"east"}),
    )
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert maxx == pytest.approx(20.0)  # sin retranqueo en el lado medianero


def test_area_edificable_real_uses_retranqueo_por_lado_for_imported_polygon():
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(
        boundary=Boundary(polygon=poligono_real),
        poligono_real=poligono_real,
        retranqueo_por_lado={"south": 5},
        retranqueo_m=1.0,
    )
    area_variable = lot.area_edificable_real.polygon.area
    lot_uniforme = Lot(
        boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, retranqueo_m=1.0,
    )
    area_uniforme = lot_uniforme.area_edificable_real.polygon.area
    assert area_variable < area_uniforme  # el lado sur mas exigente reduce mas


def test_empty_retranqueo_por_lado_does_not_change_existing_behavior():
    # sin entradas (caso por defecto de siempre), debe coincidir
    # EXACTAMENTE con el comportamiento uniforme -- ningun cambio para
    # quien no use esta funcionalidad nueva.
    lot_nuevo = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0, retranqueo_por_lado={})
    lot_viejo = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
    assert lot_nuevo.buildable_area.polygon.equals(lot_viejo.buildable_area.polygon)


def test_fondo_edificacion_clips_from_the_street_side_south():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)), street_side="south", fondo_edificacion_m=10.0)
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((0.0, 0.0, 14.0, 10.0))


def test_fondo_edificacion_combines_with_uniform_retranqueo():
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 14, 20)), street_side="south",
        fondo_edificacion_m=10.0, retranqueo_m=1.0,
    )
    assert lot.buildable_area.polygon.bounds == pytest.approx((1.0, 1.0, 13.0, 10.0))


def test_fondo_edificacion_respects_street_side_east():
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)), street_side="east", fondo_edificacion_m=8.0)
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (round(minx, 1), round(maxx, 1)) == (6.0, 14.0)


def test_fondo_edificacion_none_does_not_change_existing_behavior():
    lot_con_none = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)), fondo_edificacion_m=None)
    lot_sin_campo = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)))
    assert lot_con_none.buildable_area.polygon.equals(lot_sin_campo.buildable_area.polygon)


def test_frente_actual_m_without_poligono_real_matches_rectangle_side():
    # caso manual de siempre -- sin poligono_real, coincide exactamente
    # con el ancho/fondo del rectangulo, ningun cambio de comportamiento.
    lot_sur = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)), street_side="south")
    assert lot_sur.frente_actual_m == pytest.approx(14.0)  # ancho en X

    lot_este = Lot(boundary=Boundary(polygon=box(0, 0, 14, 20)), street_side="east")
    assert lot_este.frente_actual_m == pytest.approx(20.0)  # fondo en Y


def test_frente_actual_m_uses_the_real_polygon_side_not_the_bounding_box():
    # propiedad central de esta pieza: el frente real de una parcela
    # irregular puede ser mayor O menor que el ancho del rectangulo
    # envolvente en esa misma direccion -- nunca debe coincidir con el
    # rectangulo por casualidad. Valores verificados a mano sobre la
    # parcela real de la fixture (25.74m de ancho en X, 15.47m en Y).
    poligono_real = _poligono_real_de_fixture()
    bbox_ancho_x = poligono_real.bounds[2] - poligono_real.bounds[0]
    bbox_ancho_y = poligono_real.bounds[3] - poligono_real.bounds[1]

    lot_sur = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="south")
    assert lot_sur.frente_actual_m == pytest.approx(27.80, abs=0.01)
    assert lot_sur.frente_actual_m != pytest.approx(bbox_ancho_x)  # NO el rectangulo envolvente

    lot_norte = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="north")
    assert lot_norte.frente_actual_m == pytest.approx(23.80, abs=0.01)
    assert lot_norte.frente_actual_m != pytest.approx(bbox_ancho_x)

    lot_este = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="east")
    assert lot_este.frente_actual_m == pytest.approx(15.50, abs=0.01)
    assert lot_este.frente_actual_m != pytest.approx(bbox_ancho_y)

    lot_oeste = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="west")
    assert lot_oeste.frente_actual_m == pytest.approx(10.40, abs=0.01)
    assert lot_oeste.frente_actual_m != pytest.approx(bbox_ancho_y)


def test_fondo_edificacion_applies_to_area_edificable_real_too():
    poligono_real = _poligono_real_de_fixture()
    lot_con_fondo = Lot(
        boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real,
        street_side="south", fondo_edificacion_m=8.0,
    )
    lot_sin_fondo = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="south")
    assert lot_con_fondo.area_edificable_real.polygon.area < lot_sin_fondo.area_edificable_real.polygon.area


def test_linea_edificacion_none_does_not_change_existing_behavior():
    lot_con_none = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0, linea_edificacion_m=None)
    lot_sin_campo = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=3.0)
    assert lot_con_none.buildable_area.polygon.equals(lot_sin_campo.buildable_area.polygon)


def test_linea_edificacion_pushes_back_only_the_street_side_when_larger():
    # sin retranqueo declarado (0) en un solar 20x20, street_side=south --
    # la reserva municipal de 5m debe recortar SOLO el lado sur, el resto
    # de lados quedan intactos (sin retranqueo propio).
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), street_side="south", linea_edificacion_m=5.0)
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((0.0, 5.0, 20.0, 20.0))


def test_linea_edificacion_does_not_reduce_a_larger_declared_retranqueo():
    # el arquitecto ya declaro 6m de retranqueo uniforme -- una reserva
    # municipal de 3m no debe reducirlo, el minimo obligatorio ya esta
    # superado.
    lot_con_linea = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 20)), street_side="south",
        retranqueo_m=6.0, linea_edificacion_m=3.0,
    )
    lot_sin_linea = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), street_side="south", retranqueo_m=6.0)
    assert lot_con_linea.buildable_area.polygon.equals(lot_sin_linea.buildable_area.polygon)


def test_linea_edificacion_combines_with_retranqueo_por_lado():
    # retranqueo_por_lado ya declara 2m en el lado de calle (sur) --
    # menor que la reserva municipal de 5m, debe prevalecer la reserva
    # SOLO en ese lado, el resto de entradas del dict quedan intactas.
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 20, 20)), street_side="south",
        retranqueo_por_lado={"south": 2.0, "east": 1.0}, linea_edificacion_m=5.0,
    )
    minx, miny, maxx, maxy = lot.buildable_area.polygon.bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((0.0, 5.0, 19.0, 20.0))


def test_linea_edificacion_applies_to_area_edificable_real_too():
    poligono_real = _poligono_real_de_fixture()
    lot_con_linea = Lot(
        boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real,
        street_side="south", linea_edificacion_m=8.0,
    )
    lot_sin_linea = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real, street_side="south")
    assert lot_con_linea.area_edificable_real.polygon.area < lot_sin_linea.area_edificable_real.polygon.area
