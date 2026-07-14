import random
import pytest
from shapely.geometry import box
from housing_generator.infrastructure.algorithms.layout_generation.footprint import (
    footprint_target_area,
    footprint_rectangle,
    initial_footprint_width,
    resize_footprint_width,
    FOOTPRINT_BUFFER,
)


def test_footprint_target_area_adds_the_buffer():
    assert footprint_target_area(100.0) == 100.0 * (1 + FOOTPRINT_BUFFER)


def test_initial_footprint_is_close_to_square_when_it_fits():
    width = initial_footprint_width(footprint_area=100.0, buildable_w=20.0, buildable_h=20.0)
    assert width == 10.0  # sqrt(100) = 10, cabe sin problema


def test_initial_footprint_clamped_when_square_would_not_fit():
    # sqrt(100)=10 no cabria en un edificable de 8x30 (ancho maximo 8)
    width = initial_footprint_width(footprint_area=100.0, buildable_w=8.0, buildable_h=30.0)
    assert width <= 8.0


def test_footprint_rectangle_has_the_target_area():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="south")
    assert rect.area == 100.0


def test_footprint_anchored_to_south_touches_the_south_edge():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="south")
    minx, miny, maxx, maxy = rect.bounds
    assert miny == 0.0  # toca el lado sur (entrada), el vacio queda al norte


def test_footprint_anchored_to_north_touches_the_north_edge():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="north")
    minx, miny, maxx, maxy = rect.bounds
    assert maxy == 20.0


def test_footprint_anchored_to_east_touches_the_east_edge():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="east")
    minx, miny, maxx, maxy = rect.bounds
    assert maxx == 20.0


def test_footprint_anchored_to_west_touches_the_west_edge():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="west")
    minx, miny, maxx, maxy = rect.bounds
    assert minx == 0.0


def test_footprint_is_centered_on_the_perpendicular_axis():
    buildable = box(0, 0, 20, 20)
    rect = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="south")
    minx, miny, maxx, maxy = rect.bounds
    assert minx == 5.0 and maxx == 15.0  # centrado en X (10m de ancho en un edificable de 20m)


def test_footprint_never_exceeds_buildable_bounds():
    buildable = box(0, 0, 10, 10)
    # area objetivo mayor que el propio edificable -- no deberia exceder los limites
    rect = footprint_rectangle(buildable, footprint_width=50.0, footprint_area=500.0, entrance_side="south")
    minx, miny, maxx, maxy = rect.bounds
    assert maxx - minx <= 10.0 + 1e-6
    assert maxy - miny <= 10.0 + 1e-6


def test_resize_footprint_width_stays_within_buildable_bounds():
    rng = random.Random(1)
    width = 10.0
    for _ in range(200):
        width = resize_footprint_width(width, footprint_area=100.0, buildable_w=20.0, buildable_h=20.0, rng=rng)
        assert 0 < width <= 20.0
        height = 100.0 / width
        assert height <= 20.0 + 1e-6


def test_vacio_is_the_remainder_of_buildable_minus_footprint():
    buildable = box(0, 0, 20, 20)
    footprint = footprint_rectangle(buildable, footprint_width=10.0, footprint_area=100.0, entrance_side="south")
    vacio = buildable.difference(footprint)
    assert vacio.area == pytest.approx(300.0)  # 400 - 100
