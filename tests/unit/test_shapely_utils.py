from shapely.geometry import box, Polygon
from shapely.affinity import rotate
from housing_generator.infrastructure.geometry.shapely_utils import can_inscribe_square


def test_square_fits_in_exact_size_room():
    room = box(0, 0, 3.30, 3.30)
    assert can_inscribe_square(room, 3.30) is True


def test_square_fits_in_larger_room():
    room = box(0, 0, 5, 5)
    assert can_inscribe_square(room, 3.30) is True


def test_square_does_not_fit_in_narrow_room():
    room = box(0, 0, 2.0, 10.0)
    assert can_inscribe_square(room, 3.30) is False


def test_square_fits_in_rotated_rectangle():
    # mismo rectangulo que el primer test, pero rotado 30 grados: debe
    # seguir cabiendo el cuadrado, porque se mide sobre el propio
    # rectangulo (minimum_rotated_rectangle), no sobre el bounding box
    # alineado a ejes (que seria mas grande tras rotar).
    room = rotate(box(0, 0, 4.0, 5.0), 30, origin=(0, 0))
    assert can_inscribe_square(room, 3.30) is True


def test_non_rectangular_polygon_is_unverifiable():
    l_shape = Polygon([(0, 0), (6, 0), (6, 3), (3, 3), (3, 6), (0, 6)])
    assert can_inscribe_square(l_shape, 3.30) is None


def test_triangle_is_unverifiable():
    triangle = Polygon([(0, 0), (10, 0), (5, 10)])
    assert can_inscribe_square(triangle, 3.30) is None


def test_rectangle_fits_regardless_of_orientation():
    from housing_generator.infrastructure.geometry.shapely_utils import can_fit_rectangle
    room = box(0, 0, 1.0, 3.0)  # 1m x 3m
    assert can_fit_rectangle(room, 1.5, 0.6) is True   # cabe girado (3m >= 1.5, 1m >= 0.6)
    assert can_fit_rectangle(room, 0.6, 1.5) is True   # mismo caso, argumentos intercambiados


def test_rectangle_does_not_fit_when_both_orientations_fail():
    from housing_generator.infrastructure.geometry.shapely_utils import can_fit_rectangle
    room = box(0, 0, 0.4, 3.0)  # demasiado estrecho en ambas orientaciones para 0.6 de fondo
    assert can_fit_rectangle(room, 1.5, 0.6) is False


def test_degenerate_zero_area_polygon_is_never_a_rectangle():
    # linea (area 0), no un poligono real -- rama defensiva de
    # _is_axis_or_rotated_rectangle (mrr_area <= 0), sin cubrir hasta
    # ahora. Al no ser un rectangulo real, el resultado correcto es
    # None ("no verificable"), no False -- mismo patron de tres estados
    # que usa el resto del proyecto para formas no rectangulares.
    from housing_generator.infrastructure.geometry.shapely_utils import can_fit_rectangle
    degenerate = Polygon([(0, 0), (5, 0), (0, 0)])  # colapsado a una linea
    assert degenerate.area == 0
    assert can_fit_rectangle(degenerate, 1.0, 1.0) is None
