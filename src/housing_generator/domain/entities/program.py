from dataclasses import dataclass, field
from typing import List
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.exceptions import InvalidProgramError


@dataclass
class Program:
    """El encargo de diseno: estancias solicitadas + requisitos de adyacencia."""

    rooms: List[Room]
    adjacency_requirements: List[AdjacencyRequirement] = field(default_factory=list)

    def __post_init__(self):
        ids = [r.id for r in self.rooms]
        if len(ids) != len(set(ids)):
            raise InvalidProgramError("Hay ids de estancia duplicados en el programa")

        room_ids = set(ids)
        for req in self.adjacency_requirements:
            if req.room_a_id not in room_ids or req.room_b_id not in room_ids:
                raise InvalidProgramError(
                    f"Un requisito de adyacencia referencia una estancia inexistente: {req}"
                )

    @property
    def total_area_m2(self) -> float:
        return sum(r.dimensions.area_m2 for r in self.rooms)

    def room_by_id(self, room_id: str) -> Room:
        for r in self.rooms:
            if r.id == room_id:
                return r
        raise KeyError(room_id)
