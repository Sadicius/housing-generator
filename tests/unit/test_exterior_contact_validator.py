from shapely.geometry import box, Polygon
from housing_generator.infrastructure.algorithms.constraints.exterior_contact_validator import (
    ExteriorContactValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 10, 10)))


def test_living_room_touching_exterior_passes():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    living.boundary = Boundary(polygon=box(0, 0, 4, 4))  # esquina, toca exterior

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    assert ExteriorContactValidator().validate(layout).violations == []


def test_living_room_fully_interior_fails():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=9))
    living.boundary = Boundary(polygon=box(3, 3, 6, 6))  # totalmente interior

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    violations = ExteriorContactValidator().validate(layout).violations

    assert len(violations) == 1
    assert "living" in violations[0]


def test_bathroom_fully_interior_passes_no_exterior_required():
    bath = Room(id="b", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5))
    bath.boundary = Boundary(polygon=box(3, 3, 6, 6))  # interior, pero bano no exige exterior

    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])
    assert ExteriorContactValidator().validate(layout).violations == []


def test_non_rectangular_room_requiring_exterior_is_a_warning_not_violation():
    l_shape = Polygon([(3, 3), (6, 3), (6, 5), (5, 5), (5, 6), (3, 6)])  # interior, forma en L
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=l_shape.area))
    living.boundary = Boundary(polygon=l_shape)

    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])
    result = ExteriorContactValidator().validate(layout)

    assert result.violations == []
    assert len(result.warnings) == 1


def test_unplaced_room_is_skipped():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    layout = Layout(lot=_dummy_lot(), rooms=[living], zones=[])

    result = ExteriorContactValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_room_touching_buildable_area_edge_passes_even_with_retranqueo():
    # parcela 10x10 con retranqueo de 2m -> area edificable de (2,2) a (8,8).
    # la estancia toca el borde del AREA EDIFICABLE, no el de la parcela --
    # debe contar como contacto exterior real (ahi esta el jardin/exterior).
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 10, 10)), retranqueo_m=2.0)
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    living.boundary = Boundary(polygon=box(2, 2, 6, 6))  # esquina del area edificable (2,2)-(8,8)

    layout = Layout(lot=lot, rooms=[living], zones=[])
    assert ExteriorContactValidator().validate(layout).violations == []


def test_room_only_near_legal_parcel_line_but_not_buildable_edge_fails_with_retranqueo():
    # si por error una estancia quedase pegada a la linea de parcela real
    # (dentro de la franja de retranqueo, lo cual no deberia ocurrir si el
    # generador respeta buildable_area) NO debe contar como contacto
    # exterior valido -- confirma que se mide contra el area edificable.
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 10, 10)), retranqueo_m=2.0)
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=9))
    living.boundary = Boundary(polygon=box(3.5, 3.5, 6.5, 6.5))  # centrada, lejos de ambos bordes

    layout = Layout(lot=lot, rooms=[living], zones=[])
    violations = ExteriorContactValidator().validate(layout).violations
    assert len(violations) == 1


def test_room_against_medianera_wall_does_not_count_as_exterior_contact():
    # retomado de docs/CONTINUIDAD.md ("vivienda pareada/adosada"): una
    # estancia pegada a la pared de medianera (sin retranqueo ahi) NO
    # debe contar ese lado como contacto exterior real.
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 10, 10)), retranqueo_m=2.0,
        medianera_sides=frozenset({"east"}),
    )
    # area edificable: (2,2)-(10,8) -- sin retranqueo en el este (medianera)
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=8))
    living.boundary = Boundary(polygon=box(8, 4, 10, 6))  # pegada SOLO al lado este (medianera)

    layout = Layout(lot=lot, rooms=[living], zones=[])
    violations = ExteriorContactValidator().validate(layout).violations
    assert len(violations) == 1  # 0 lados de contacto exterior real (el unico que toca es medianera)


def test_room_against_both_medianera_and_real_exterior_in_adosada():
    # vivienda adosada (2 medianeras, este y oeste) -- una estancia que
    # toca el borde SUR (exterior real) y el borde ESTE (medianera) debe
    # contar solo 1 lado exterior real, no 2.
    lot = Lot(
        boundary=Boundary(polygon=box(0, 0, 10, 10)), retranqueo_m=2.0,
        medianera_sides=frozenset({"east", "west"}),
    )
    # area edificable: (0,2)-(10,8) -- sin retranqueo en este/oeste
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=16))
    living.boundary = Boundary(polygon=box(6, 2, 10, 6))  # toca sur (exterior real) y este (medianera)

    layout = Layout(lot=lot, rooms=[living], zones=[])
    result = ExteriorContactValidator().validate(layout)
    assert result.violations == []  # 1 lado real (sur) es suficiente para min_exterior_sides=1
