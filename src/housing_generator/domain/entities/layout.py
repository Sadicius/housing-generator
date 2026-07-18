from dataclasses import dataclass, field
from typing import List, Dict
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.lot import Lot


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
