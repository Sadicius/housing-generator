from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.altura_libre_validator import AlturaLibreValidator
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_missing_height_is_a_warning_not_a_violation():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == []
    assert len(result.warnings) == 1


def test_living_room_at_2_50_or_above_passes_cleanly():
    living = Room(
        id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=20, ceiling_height_m=2.50),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_living_room_between_2_20_and_2_50_is_a_warning_not_a_violation():
    living = Room(
        id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=20, ceiling_height_m=2.30),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == []
    assert len(result.warnings) == 1
    assert "30%" in result.warnings[0]


def test_living_room_below_2_20_is_a_hard_violation():
    living = Room(
        id="living", name="Estar", room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=20, ceiling_height_m=2.00),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert len(result.violations) == 1


def test_bathroom_allows_2_20_directly_without_warning():
    bath = Room(
        id="b", name="Bano", room_type=RoomType.BATHROOM,
        dimensions=Dimensions(area_m2=5, ceiling_height_m=2.20),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_bathroom_below_2_20_still_fails():
    bath = Room(
        id="b", name="Bano", room_type=RoomType.BATHROOM,
        dimensions=Dimensions(area_m2=5, ceiling_height_m=2.10),
    )
    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert len(result.violations) == 1


def test_garage_and_technical_room_are_out_of_scope():
    garage = Room(
        id="g", name="Garaje", room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=18, ceiling_height_m=1.80),  # muy bajo, pero fuera de alcance
    )
    layout = Layout(lot=_dummy_lot(), rooms=[garage], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == [] and result.warnings == []
