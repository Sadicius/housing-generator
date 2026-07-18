from dataclasses import dataclass
from housing_generator.domain.enums import AdjacencyStrength


@dataclass(frozen=True)
class AdjacencyRequirement:
    """Requisito de adyacencia (no dirigido) entre dos estancias, por id.

    Es la unidad minima de datos de la clasica 'matriz de adyacencia' /
    'diagrama de burbujas' empleada en programacion arquitectonica.
    """

    room_a_id: str
    room_b_id: str
    strength: AdjacencyStrength

    def involves(self, room_id: str) -> bool:
        return room_id in (self.room_a_id, self.room_b_id)

    def other(self, room_id: str) -> str:
        if room_id == self.room_a_id:
            return self.room_b_id
        if room_id == self.room_b_id:
            return self.room_a_id
        raise ValueError(f"La estancia {room_id} no pertenece a este requisito")
