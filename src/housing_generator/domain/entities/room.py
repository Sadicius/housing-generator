from dataclasses import dataclass
from typing import Optional
from housing_generator.domain.enums import (
    RoomType,
    ZoneType,
    SpaceCategory,
    NivelPlanta,
    DEFAULT_ROOM_ZONE,
    DEFAULT_WET_ROOMS,
    DEFAULT_SPACE_CATEGORY,
    DEFAULT_SERVICE_SUBTYPE,
    DEFAULT_MIN_EXTERIOR_SIDES,
)
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary


@dataclass
class Room:
    """Una estancia a ubicar en la vivienda (entidad de dominio).

    `boundary` es None hasta que un LayoutGenerator la coloca en el espacio;
    hasta entonces Room solo representa el requisito programatico.
    """
    id: str
    name: str
    room_type: RoomType
    dimensions: Dimensions
    zone: Optional[ZoneType] = None
    is_wet: Optional[bool] = None
    space_category: Optional[SpaceCategory] = None
    service_subtype: Optional[str] = None
    min_exterior_sides: Optional[int] = None
    # Solo relevante para RoomType.KITCHEN: cocina abierta en un unico
    # espacio con el salon (caso tipico de estudio/loft). Ver
    # CocinaIntegradaValidator -- confirmado contra nhv.lua
    # (validarCocinaIntegrada), no un supuesto propio.
    integrated_in_largest_room: bool = False
    vertical_opening_m2: Optional[float] = None
    boundary: Optional[Boundary] = None
    # Planta a la que pertenece esta estancia (multi-planta). `None` =
    # vivienda de una sola planta (comportamiento previo sin cambios) --
    # se asume PLANTA_BAJA implicitamente en ese caso por el resto del
    # sistema, sin necesidad de declararlo.
    level: Optional[NivelPlanta] = None

    def __post_init__(self):
        if self.zone is None:
            self.zone = DEFAULT_ROOM_ZONE.get(self.room_type, ZoneType.DAY)
        if self.is_wet is None:
            self.is_wet = self.room_type in DEFAULT_WET_ROOMS
        if self.space_category is None:
            self.space_category = DEFAULT_SPACE_CATEGORY.get(self.room_type, SpaceCategory.OTROS)
        if self.service_subtype is None:
            self.service_subtype = DEFAULT_SERVICE_SUBTYPE.get(self.room_type)
        if self.min_exterior_sides is None:
            self.min_exterior_sides = DEFAULT_MIN_EXTERIOR_SIDES.get(self.room_type, 0)

    @property
    def is_placed(self) -> bool:
        return self.boundary is not None
