from shapely.geometry import box
from housing_generator.application.use_cases.validate_layout import ValidateLayoutUseCase
from housing_generator.infrastructure.algorithms.constraints.vivienda_minima_validator import (
    ViviendaMinimaValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType


def test_delegates_validation_to_the_injected_validator():
    garage = Room(id="garage", name="Garaje", room_type=RoomType.GARAGE, dimensions=Dimensions(area_m2=18))
    layout = Layout(lot=Lot(boundary=Boundary(polygon=box(0, 0, 10, 10))), rooms=[garage], zones=[])

    use_case = ValidateLayoutUseCase(constraint_validator=ViviendaMinimaValidator())
    result = use_case.execute(layout)

    assert len(result.violations) == 6  # programa minimo completo, solo hay garaje


def test_passes_through_empty_result_when_layout_is_valid():
    living = Room(id="living", name="Estar", room_type=RoomType.LIVING_ROOM, dimensions=Dimensions(area_m2=25))
    kitchen = Room(id="kitchen", name="Cocina", room_type=RoomType.KITCHEN, dimensions=Dimensions(area_m2=7))
    bathroom = Room(id="bathroom", name="Bano", room_type=RoomType.BATHROOM, dimensions=Dimensions(area_m2=5))
    laundry = Room(id="laundry", name="Lavadero", room_type=RoomType.LAUNDRY, dimensions=Dimensions(area_m2=1.5))
    drying = Room(id="drying", name="Tendedero", room_type=RoomType.DRYING_AREA, dimensions=Dimensions(area_m2=1.5))
    storage = Room(id="storage", name="Almacen", room_type=RoomType.STORAGE, dimensions=Dimensions(area_m2=1))
    layout = Layout(
        lot=Lot(boundary=Boundary(polygon=box(0, 0, 10, 10))),
        rooms=[living, kitchen, bathroom, laundry, drying, storage],
        zones=[],
    )

    use_case = ValidateLayoutUseCase(constraint_validator=ViviendaMinimaValidator())
    result = use_case.execute(layout)

    assert result.violations == []
