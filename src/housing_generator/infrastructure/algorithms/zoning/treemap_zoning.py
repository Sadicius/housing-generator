from typing import List
from collections import defaultdict
from housing_generator.application.ports.zoning_strategy_port import ZoningStrategyPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.zone import Zone


class TreemapZoningStrategy(ZoningStrategyPort):
    """Agrupa estancias en Zone segun su ZoneType declarado (dia/noche/servicio).

    El dimensionado/posicionamiento de las zonas en si se deja al
    LayoutGenerator; esta estrategia solo decide el *agrupamiento*,
    replicando el paso clasico de 'diagrama de zonificacion' previo a
    la traduccion a diagrama de burbujas y luego a planta.
    """

    def build_zones(self, program: Program) -> List[Zone]:
        grouped = defaultdict(list)
        for room in program.rooms:
            grouped[room.zone].append(room.id)

        return [
            Zone(zone_type=zone_type, room_ids=room_ids)
            for zone_type, room_ids in grouped.items()
        ]
