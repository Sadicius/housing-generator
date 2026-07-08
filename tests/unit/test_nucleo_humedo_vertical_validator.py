from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.nucleo_humedo_vertical_validator import (
    NucleoHumedoVerticalValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon) -> Room:
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area))
    r.boundary = Boundary(polygon=polygon)
    return r


def test_no_reference_wet_rooms_below_means_not_applicable():
    bath = _placed("bath", RoomType.BATHROOM, box(0, 0, 3, 3))
    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])

    result = NucleoHumedoVerticalValidator(reference_wet_boundaries=[]).validate(layout)
    assert result.violations == []


def test_overlapping_wet_room_passes():
    kitchen_below = box(0, 0, 4, 4)  # planta inferior: cocina aqui
    bath_above = _placed("bath", RoomType.BATHROOM, box(1, 1, 3, 3))  # solapa completamente

    layout = Layout(lot=_dummy_lot(), rooms=[bath_above], zones=[])
    result = NucleoHumedoVerticalValidator(reference_wet_boundaries=[kitchen_below]).validate(layout)

    assert result.violations == []


def test_any_wet_type_matches_not_specific_type():
    # planta inferior tiene COCINA, esta planta tiene BAÑO -- deben
    # poder solapar igualmente (regla ya confirmada: "cualquier tipo
    # humedo coincide, no especifico por tipo")
    kitchen_below = box(0, 0, 4, 4)
    bath_above = _placed("bath", RoomType.BATHROOM, box(2, 2, 5, 5))  # solape parcial real

    layout = Layout(lot=_dummy_lot(), rooms=[bath_above], zones=[])
    result = NucleoHumedoVerticalValidator(reference_wet_boundaries=[kitchen_below]).validate(layout)

    assert result.violations == []


def test_non_overlapping_wet_room_fails():
    kitchen_below = box(0, 0, 4, 4)
    bath_above = _placed("bath", RoomType.BATHROOM, box(10, 10, 13, 13))  # lejos, sin solape

    layout = Layout(lot=_dummy_lot(), rooms=[bath_above], zones=[])
    violations = NucleoHumedoVerticalValidator(reference_wet_boundaries=[kitchen_below]).validate(layout).violations

    assert len(violations) == 1


def test_dry_rooms_are_never_checked():
    kitchen_below = box(0, 0, 4, 4)
    living_above = _placed("living", RoomType.LIVING_ROOM, box(10, 10, 14, 14))  # sin solape, pero no es humeda

    layout = Layout(lot=_dummy_lot(), rooms=[living_above], zones=[])
    result = NucleoHumedoVerticalValidator(reference_wet_boundaries=[kitchen_below]).validate(layout)

    assert result.violations == []


def test_multiple_reference_wet_rooms_are_unioned():
    kitchen_below = box(0, 0, 2, 2)
    bathroom_below = box(5, 5, 7, 7)
    bath_above = _placed("bath", RoomType.BATHROOM, box(5.5, 5.5, 6.5, 6.5))  # solapa con la 2a, no la 1a

    layout = Layout(lot=_dummy_lot(), rooms=[bath_above], zones=[])
    result = NucleoHumedoVerticalValidator(
        reference_wet_boundaries=[kitchen_below, bathroom_below]
    ).validate(layout)

    assert result.violations == []
