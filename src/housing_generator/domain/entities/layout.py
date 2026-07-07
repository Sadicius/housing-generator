from dataclasses import dataclass, field
from typing import List, Dict
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.enums import ZoneType


@dataclass
class Layout:
    """Resultado generado: estancias colocadas en el espacio, agrupadas en zonas."""
    lot: Lot
    rooms: List[Room]
    zones: List[Zone]
    metadata: Dict[str, float] = field(default_factory=dict)  # p.ej. score de fitness

    @property
    def is_complete(self) -> bool:
        return all(r.is_placed for r in self.rooms)

    def rooms_in_zone(self, zone_type: ZoneType) -> List[Room]:
        zone_room_ids = {
            rid for z in self.zones if z.zone_type == zone_type for rid in z.room_ids
        }
        return [r for r in self.rooms if r.id in zone_room_ids]
