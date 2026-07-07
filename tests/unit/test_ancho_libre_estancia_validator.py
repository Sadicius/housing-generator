from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.ancho_libre_estancia_validator import (
    AnchoLibreEstanciaValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 100, 100)))


def test_living_room_below_2_70_fails():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 2.0, 10.0))  # 2m de ancho, por debajo de 2.70m

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    violations = AnchoLibreEstanciaValidator().validate(layout).violations

    assert len(violations) == 1
    assert "estancia mayor" in violations[0]


def test_living_room_at_2_70_passes():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=20))
    living.boundary = Boundary(polygon=box(0, 0, 2.70, 8.0))

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    assert AnchoLibreEstanciaValidator().validate(layout).violations == []


def test_dormitorio_doble_uses_2_60_threshold_when_area_is_12_or_more():
    bed = Room(id="bed", name="Dorm", room_type=RoomType.MASTER_BEDROOM, dimensions=Dimensions(area_m2=12))
    bed.boundary = Boundary(polygon=box(0, 0, 2.30, 6.0))  # menos de 2.60m

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    violations = AnchoLibreEstanciaValidator().validate(layout).violations

    assert len(violations) == 1
    assert "dormitorio doble" in violations[0]


def test_dormitorio_individual_uses_2_00_threshold_when_area_below_12():
    bed = Room(id="bed", name="Dorm", room_type=RoomType.BEDROOM, dimensions=Dimensions(area_m2=8))
    bed.boundary = Boundary(polygon=box(0, 0, 2.00, 4.0))  # justo 2.00m, cumple individual

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    assert AnchoLibreEstanciaValidator().validate(layout).violations == []


def test_kitchen_and_bathroom_use_their_own_thresholds():
    kitchen = Room(id="k", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=8))
    kitchen.boundary = Boundary(polygon=box(0, 0, 1.70, 5.0))  # menos de 1.80m
    bathroom = Room(id="b", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5))
    bathroom.boundary = Boundary(polygon=box(2, 0, 3.70, 3.0))  # 1.70m, cumple 1.60m

    layout = Layout(lot=_dummy_lot(), rooms=[kitchen, bathroom], zones=[])
    violations = AnchoLibreEstanciaValidator().validate(layout).violations

    assert len(violations) == 1
    assert "'k'" in violations[0] and "cocina" in violations[0]


def test_dining_room_and_study_are_not_checked_no_threshold_in_source():
    dining = Room(id="d", name="Comedor", room_type=RoomType.DINING_ROOM, dimensions=Dimensions(area_m2=10))
    dining.boundary = Boundary(polygon=box(0, 0, 0.5, 20.0))  # absurdamente estrecho

    layout = Layout(lot=_dummy_lot(), rooms=[dining], zones=[])
    assert AnchoLibreEstanciaValidator().validate(layout).violations == []


def test_no_living_room_means_no_estancia_mayor_check_and_no_warning():
    # a diferencia de EstanciaMinimumAreaValidator, este validador NO
    # hace fallback ni avisa si no hay salon -- simplemente no comprueba
    # nada para "estancia mayor" en ese caso.
    bed = Room(id="bed", name="Dorm", room_type=RoomType.MASTER_BEDROOM, dimensions=Dimensions(area_m2=20))
    bed.boundary = Boundary(polygon=box(0, 0, 0.5, 40.0))  # absurdamente estrecho, pero no es dormitorio<12? es >=12

    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])
    result = AnchoLibreEstanciaValidator().validate(layout)

    # si hubiera fallback a "mayor area", este dormitorio (unico, luego
    # el de mayor area) se comprobaria contra 2.70m y fallaria -- pero
    # aqui debe fallar solo por la regla de DORMITORIO doble (2.60m), no
    # por ninguna logica de "estancia mayor" aplicada a un dormitorio.
    assert len(result.violations) == 1
    assert "dormitorio doble" in result.violations[0]
    assert "estancia mayor" not in result.violations[0]
