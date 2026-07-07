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
