import pytest
from shapely.geometry import box
from housing_generator.application.use_cases.generate_building import (
    GenerateBuildingUseCase,
)
from housing_generator.infrastructure.algorithms.constraints.bano_acceso_validator import (
    BanoAccesoGeneralValidator,
)
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.domain.entities.building import Building
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType, NivelPlanta
from housing_generator.domain.exceptions import LayoutGenerationError


def _lot():
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def _placed(room_id, room_type, polygon):
    r = Room(
        id=room_id,
        name=room_id,
        room_type=room_type,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    r.boundary = Boundary(polygon=polygon)
    return r


def _use_case():
    # solo se necesita el bano_acceso_validator real para este metodo --
    # el resto de fabricas no se invocan al llamar _check_bano_acceso_general
    # directamente (no pasa por execute()/generate).
    return GenerateBuildingUseCase(
        per_floor_validators_factory=None,
        layout_generator_factory=None,
        zoning_strategy=None,
        programa_minimo_validator=None,
        bano_acceso_validator=BanoAccesoGeneralValidator(
            GeometryAdjacencyGraphBuilder()
        ),
    )


def test_no_bathrooms_anywhere_does_not_raise():
    living = _placed("living", RoomType.LIVING_ROOM, box(0, 0, 4, 4))
    layout = Layout(lot=_lot(), rooms=[living], zones=[])
    building = Building(floors={NivelPlanta.PLANTA_BAJA: layout})

    _use_case()._check_bano_acceso_general(building)  # no debe lanzar


def test_all_bathrooms_captured_in_bedrooms_on_every_floor_raises():
    # planta baja: bano SOLO toca un dormitorio -- pero SI hay
    # circulacion en la planta (sin tocar el bano), para que el fallo
    # sea real ("capturado"), no "no aplica por falta de circulacion".
    bed_pb = _placed("bed_pb", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath_pb = _placed("bath_pb", RoomType.BATHROOM, box(3, 0, 5, 4))
    corridor_pb = _placed(
        "corridor_pb", RoomType.CORRIDOR, box(0, 4, 3, 6)
    )  # toca a bed_pb, no a bath_pb
    layout_pb = Layout(lot=_lot(), rooms=[bed_pb, bath_pb, corridor_pb], zones=[])

    # planta superior: mismo problema, otro bano tambien capturado
    bed_ps = _placed("bed_ps", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath_ps = _placed("bath_ps", RoomType.BATHROOM, box(3, 0, 5, 4))
    corridor_ps = _placed("corridor_ps", RoomType.CORRIDOR, box(0, 4, 3, 6))
    layout_ps = Layout(lot=_lot(), rooms=[bed_ps, bath_ps, corridor_ps], zones=[])

    building = Building(
        floors={
            NivelPlanta.PLANTA_BAJA: layout_pb,
            NivelPlanta.PLANTA_SUPERIOR: layout_ps,
        }
    )

    with pytest.raises(LayoutGenerationError, match="Ninguna planta"):
        _use_case()._check_bano_acceso_general(building)


def test_one_floor_with_accessible_bathroom_is_enough_for_the_whole_building():
    # planta baja: bano SI accesible (toca el recibidor)
    hall_pb = _placed("hall_pb", RoomType.ENTRANCE_HALL, box(0, 0, 3, 4))
    bath_pb = _placed("bath_pb", RoomType.BATHROOM, box(3, 0, 5, 4))
    layout_pb = Layout(lot=_lot(), rooms=[hall_pb, bath_pb], zones=[])

    # planta superior: bano en-suite, capturado -- pero NO importa,
    # basta con que planta baja ya tenga uno accesible
    bed_ps = _placed("bed_ps", RoomType.BEDROOM, box(0, 0, 3, 4))
    bath_ps = _placed("bath_ps", RoomType.BATHROOM, box(3, 0, 5, 4))
    layout_ps = Layout(lot=_lot(), rooms=[bed_ps, bath_ps], zones=[])

    building = Building(
        floors={
            NivelPlanta.PLANTA_BAJA: layout_pb,
            NivelPlanta.PLANTA_SUPERIOR: layout_ps,
        }
    )

    _use_case()._check_bano_acceso_general(building)  # no debe lanzar


def test_staircase_counts_as_circulation_access():
    # un bano junto al rellano de la escalera SI cuenta como accesible
    # (RoomType.STAIRCASE es SpaceCategory.CIRCULACION) -- confirma el
    # comportamiento real observado en el test de integracion de 2 plantas.
    stair = _placed("stair", RoomType.STAIRCASE, box(0, 0, 2, 2))
    bath = _placed("bath", RoomType.BATHROOM, box(2, 0, 4, 2))
    layout = Layout(lot=_lot(), rooms=[stair, bath], zones=[])
    building = Building(floors={NivelPlanta.PLANTA_SUPERIOR: layout})

    _use_case()._check_bano_acceso_general(building)  # no debe lanzar
