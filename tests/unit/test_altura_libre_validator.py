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


def test_technical_room_is_out_of_scope():
    technical = Room(
        id="t", name="Cuarto tecnico", room_type=RoomType.TECHNICAL_ROOM,
        dimensions=Dimensions(area_m2=4, ceiling_height_m=1.80),  # muy bajo, pero fuera de alcance
    )
    layout = Layout(lot=_dummy_lot(), rooms=[technical], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_garage_gets_direct_reduction_like_vestibulo_or_bathroom():
    # [RESUELTO] bug real encontrado en auditoria: GARAGE estaba
    # excluido por completo (ROOM_TYPES_FUERA_DE_ALCANCE), pero el
    # Decreto 29/2010 A.3.1.1.b nombra explicitamente "garajes de
    # viviendas unifamiliares" en la lista de reduccion directa a
    # 2.20m -- confirmado por investigacion normativa directa (misma
    # investigacion que encontro que B.2.6 NO aplica a GARAGE unifamiliar,
    # pero esta seccion A.3.1.1 SI aplica). Ahora se comprueba igual que
    # vestibulo/pasillo/escaleras/bano/aseo/lavadero/tendedero.
    garage_bajo = Room(
        id="g1", name="Garaje", room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=18, ceiling_height_m=1.80),  # por debajo de 2.20m
    )
    garage_ok = Room(
        id="g2", name="Garaje", room_type=RoomType.GARAGE,
        dimensions=Dimensions(area_m2=18, ceiling_height_m=2.20),  # exactamente el minimo reducido
    )
    layout = Layout(lot=_dummy_lot(), rooms=[garage_bajo, garage_ok], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert len(result.violations) == 1
    assert "g1" in result.violations[0]
    assert result.warnings == []


def test_staircase_gets_direct_reduction_too():
    # mismo hallazgo: "escaleras" tambien aparece explicitamente en la
    # lista de A.3.1.1.b, y STAIRCASE no estaba en ninguna de las dos
    # listas (caia en el caso general mas estricto, 2.50m/excepcion 30%).
    stair_bajo = Room(
        id="s", name="Escalera", room_type=RoomType.STAIRCASE,
        dimensions=Dimensions(area_m2=4, ceiling_height_m=2.0),  # por debajo de 2.20m
    )
    layout = Layout(lot=_dummy_lot(), rooms=[stair_bajo], zones=[])

    result = AlturaLibreValidator().validate(layout)
    assert len(result.violations) == 1
    assert "s" in result.violations[0]
    assert "A.3.1.1.b" in result.violations[0]  # reduccion directa, no el caso general
