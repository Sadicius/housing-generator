from shapely.geometry import box, Polygon
from housing_generator.infrastructure.geometry.shapely_utils import count_exterior_sides


def test_room_in_corner_has_two_exterior_sides():
    lot = box(0, 0, 10, 10)
    room = box(0, 0, 4, 4)  # esquina inferior izquierda: toca el lado izquierdo y el inferior del solar
    assert count_exterior_sides(room, lot) == 2


def test_room_fully_interior_has_zero_exterior_sides():
    lot = box(0, 0, 10, 10)
    room = box(3, 3, 6, 6)  # no toca ningun borde del solar
    assert count_exterior_sides(room, lot) == 0


def test_room_spanning_full_width_has_one_exterior_side_on_each_touching_edge():
    lot = box(0, 0, 10, 10)
    room = box(0, 0, 10, 3)  # toca el borde inferior en todo su ancho, y los laterales izq/der tambien
    # bottom completo (10m), left (0 a 3, 3m), right (0 a 3, 3m) -- los tres >= 0.3m
    assert count_exterior_sides(room, lot) == 3


def test_short_contact_below_threshold_does_not_count():
    lot = box(0, 0, 10, 10)
    room = box(0, 9.9, 0.2, 10)  # esquina, pero con lados de solo 0.2m y 0.1m de contacto
    lados = count_exterior_sides(room, lot, min_contact_m=0.3)
    assert lados == 0


def test_non_rectangular_room_is_unverifiable():
    lot = box(0, 0, 10, 10)
    l_shape = Polygon([(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])
    assert count_exterior_sides(l_shape, lot) is None


def test_excluded_segment_does_not_count_as_exterior_contact():
    # retomado de docs/CONTINUIDAD.md ("vivienda pareada/adosada"): una
    # pared de medianera excluida no debe contar como contacto exterior
    # real, aunque toque geometricamente el borde de la parcela.
    from shapely.geometry import LineString

    lot = box(0, 0, 10, 10)
    room = box(7, 0, 10, 3)  # toca el borde inferior (exterior real) Y el derecho (medianera)
    medianera_este = LineString([(10, 0), (10, 10)])

    sin_exclusion = count_exterior_sides(room, lot)
    con_exclusion = count_exterior_sides(room, lot, excluded_segments=[medianera_este])

    assert sin_exclusion == 2  # abajo + derecha, sin saber que la derecha es medianera
    assert con_exclusion == 1  # solo abajo cuenta como exterior real


def test_excluded_segment_on_a_side_the_room_does_not_touch_has_no_effect():
    from shapely.geometry import LineString

    lot = box(0, 0, 10, 10)
    room = box(0, 0, 3, 3)  # esquina inferior izquierda, no toca el lado este
    medianera_este = LineString([(10, 0), (10, 10)])

    assert count_exterior_sides(room, lot, excluded_segments=[medianera_este]) == 2  # abajo + izquierda
