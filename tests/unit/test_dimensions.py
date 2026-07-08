import pytest
from housing_generator.domain.value_objects.dimensions import Dimensions


def test_valid_dimensions_construct_without_error():
    d = Dimensions(area_m2=10, min_width_m=2.0, max_aspect_ratio=2.5, ceiling_height_m=2.5)
    assert d.area_m2 == 10


def test_zero_or_negative_area_is_rejected():
    with pytest.raises(ValueError):
        Dimensions(area_m2=0)
    with pytest.raises(ValueError):
        Dimensions(area_m2=-5)


def test_zero_or_negative_min_width_is_rejected():
    with pytest.raises(ValueError):
        Dimensions(area_m2=10, min_width_m=0)
    with pytest.raises(ValueError):
        Dimensions(area_m2=10, min_width_m=-1)


def test_zero_or_negative_ceiling_height_is_rejected_when_declared():
    with pytest.raises(ValueError):
        Dimensions(area_m2=10, ceiling_height_m=0)
    with pytest.raises(ValueError):
        Dimensions(area_m2=10, ceiling_height_m=-2.5)


def test_undeclared_ceiling_height_defaults_to_none_without_error():
    d = Dimensions(area_m2=10)
    assert d.ceiling_height_m is None
