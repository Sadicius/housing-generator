from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.bano_acceso_validator import (
    BanoAccesoGeneralValidator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def _dummy_lot() -> Lot:
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon, **kwargs) -> Room:
    r = Room(id=room_id, name=room_id, room_type=room_type, dimensions=Dimensions(area_m2=polygon.area), **kwargs)
    r.boundary = Boundary(polygon=polygon)
    return r


def _validator():
    return BanoAccesoGeneralValidator(GeometryAdjacencyGraphBuilder())


def test_no_bathrooms_does_not_apply():
    bed = _placed("bed", RoomType.BEDROOM, box(0, 0, 3, 3))
    layout = Layout(lot=_dummy_lot(), rooms=[bed], zones=[])

    result = _validator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_no_circulation_at_all_in_program_does_not_apply():
    # BUG REAL encontrado en auditoria de diagnostico: sin NINGUNA
    # estancia de circulacion en el programa (valido -- "programa
    # minimo" no exige recibidor/pasillo), la regla era estructuralmente
    # IMPOSIBLE de satisfacer sea cual fuera la geometria -- un bano
    # tocando directamente el salon (sin ningun corridor/entrance_hall
    # en absoluto) no deberia fallar esto, no hay nada con lo que
    # exigir la adyacencia.
    bath = _placed("bath", RoomType.BATHROOM, box(0, 0, 2, 3))
    living = _placed("living", RoomType.LIVING_ROOM, box(2, 0, 6, 3))
    layout = Layout(lot=_dummy_lot(), rooms=[bath, living], zones=[])

    result = _validator().validate(layout)
    assert result.violations == [] and result.warnings == []


def test_single_bathroom_captured_in_bedroom_only_fails():
    # el bano SOLO toca el dormitorio -- pero SI hay circulacion en el
    # programa (en otro sitio, sin tocar el bano), para que el fallo
    # sea real ("capturado", no "no aplica por falta de circulacion").
    bed = _placed("bed", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath = _placed("bath", RoomType.BATHROOM, box(3, 0, 5, 4))  # comparte pared solo con bed
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 4, 3, 6))  # toca a bed, NO a bath

    layout = Layout(lot=_dummy_lot(), rooms=[bed, bath, corridor], zones=[])
    violations = _validator().validate(layout).violations

    assert len(violations) == 1
    assert "ningún baño" in violations[0].lower()


def test_single_bathroom_with_corridor_access_passes():
    bed = _placed("bed", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath = _placed("bath", RoomType.BATHROOM, box(3, 0, 5, 4))
    corridor = _placed("corridor", RoomType.CORRIDOR, box(3, 4, 5, 6))  # toca al bano por arriba

    layout = Layout(lot=_dummy_lot(), rooms=[bed, bath, corridor], zones=[])
    result = _validator().validate(layout)

    assert result.violations == []


def test_two_bathrooms_one_ensuite_one_general_passes():
    # bano principal (en-suite, solo toca el dormitorio principal) +
    # bano general (toca el pasillo) -- valido: no los dos necesitan
    # acceso general, basta con uno
    master = _placed("master", RoomType.MASTER_BEDROOM, box(0, 0, 4, 4))
    ensuite = _placed("ensuite", RoomType.BATHROOM, box(4, 0, 6, 4))  # solo toca master
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 4, 6, 5))
    general_bath = _placed("general_bath", RoomType.BATHROOM, box(0, 5, 3, 7))  # toca corridor

    layout = Layout(lot=_dummy_lot(), rooms=[master, ensuite, corridor, general_bath], zones=[])
    result = _validator().validate(layout)

    assert result.violations == []


def test_two_bathrooms_both_captured_fails():
    bed1 = _placed("bed1", RoomType.BEDROOM, box(0, 0, 3, 3))
    bath1 = _placed("bath1", RoomType.BATHROOM, box(3, 0, 5, 3))  # solo toca bed1
    bed2 = _placed("bed2", RoomType.BEDROOM, box(0, 3, 3, 6))
    bath2 = _placed("bath2", RoomType.BATHROOM, box(3, 3, 5, 6))  # solo toca bed2
    corridor = _placed("corridor", RoomType.CORRIDOR, box(0, 6, 3, 8))  # toca solo a bed2, ningun bano

    layout = Layout(lot=_dummy_lot(), rooms=[bed1, bath1, bed2, bath2, corridor], zones=[])
    violations = _validator().validate(layout).violations

    assert len(violations) == 1


def test_entrance_hall_also_counts_as_general_access():
    bed = _placed("bed", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath = _placed("bath", RoomType.BATHROOM, box(3, 0, 5, 4))
    hall = _placed("hall", RoomType.ENTRANCE_HALL, box(3, 4, 5, 6))

    layout = Layout(lot=_dummy_lot(), rooms=[bed, bath, hall], zones=[])
    result = _validator().validate(layout)

    assert result.violations == []


def test_unplaced_bathroom_is_ignored():
    bath = Room(id="bath", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5))
    layout = Layout(lot=_dummy_lot(), rooms=[bath], zones=[])

    result = _validator().validate(layout)
    assert result.violations == [] and result.warnings == []
