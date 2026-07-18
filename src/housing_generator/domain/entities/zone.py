from dataclasses import dataclass, field
from typing import List, Optional
from housing_generator.domain.enums import ZoneType
from housing_generator.domain.value_objects.boundary import Boundary


@dataclass
class Zone:
    """Macro-zona (dia / noche / servicio) que agrupa varias estancias."""

    zone_type: ZoneType
    room_ids: List[str] = field(default_factory=list)
    boundary: Optional[Boundary] = None

    def add_room(self, room_id: str) -> None:
        if room_id not in self.room_ids:
            self.room_ids.append(room_id)
