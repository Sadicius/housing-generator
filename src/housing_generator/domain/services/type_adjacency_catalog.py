"""Catálogo de relaciones espaciales entre tipos de estancia,
formalizado como estructura ejecutable del dominio. Generado
programáticamente desde docs/relaciones_espaciales.md. Ver
[ARCH:type-adjacency-catalog] para qué pares se omiten y por qué.
"""
from typing import Dict, List, Optional, Tuple
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.program import Program
from housing_generator.domain.enums import RoomType, AdjacencyStrength
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Pares fuera del catalogo estatico. Ver [ARCH:type-adjacency-catalog].
CONDICIONAL_PAIRS = {
    (RoomType.BEDROOM, RoomType.BATHROOM),
    (RoomType.MASTER_BEDROOM, RoomType.BATHROOM),
}
YA_CUBIERTO_PAIRS = {
    (RoomType.KITCHEN, RoomType.BATHROOM),
}

DEFAULT_TYPE_ADJACENCY: Dict[Tuple[RoomType, RoomType], AdjacencyStrength] = {
    (RoomType.BATHROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BATHROOM, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BATHROOM, RoomType.ENTRANCE_HALL): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BATHROOM, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BATHROOM, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BATHROOM, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BATHROOM, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BEDROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BEDROOM, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BEDROOM, RoomType.ENTRANCE_HALL): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BEDROOM, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BEDROOM, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BEDROOM, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BEDROOM, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.BEDROOM, RoomType.STUDY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.BEDROOM, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.BATHROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.DINING_ROOM, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.KITCHEN): AdjacencyStrength.MUST_BE_NEAR,
    (RoomType.DINING_ROOM, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.MASTER_BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.DINING_ROOM, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.DINING_ROOM, RoomType.TOILET): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.DRYING_AREA, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.ENTRANCE_HALL, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.ENTRANCE_HALL, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.ENTRANCE_HALL, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.ENTRANCE_HALL, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.KITCHEN, RoomType.BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.KITCHEN, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.ENTRANCE_HALL): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.MASTER_BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.KITCHEN, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.KITCHEN, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.KITCHEN, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LAUNDRY, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LAUNDRY, RoomType.DRYING_AREA): AdjacencyStrength.MUST_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.BATHROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.DINING_ROOM): AdjacencyStrength.MUST_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.ENTRANCE_HALL): AdjacencyStrength.MUST_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.GARAGE): AdjacencyStrength.MUST_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.KITCHEN): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.MASTER_BEDROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.STUDY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.LIVING_ROOM, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.LIVING_ROOM, RoomType.TOILET): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.ENTRANCE_HALL): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.MASTER_BEDROOM, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.MASTER_BEDROOM, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.MASTER_BEDROOM, RoomType.STUDY): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.MASTER_BEDROOM, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.STORAGE, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.STORAGE_ROOM, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.STORAGE_ROOM, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.STUDY, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.STUDY, RoomType.DRYING_AREA): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.STUDY, RoomType.GARAGE): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.STUDY, RoomType.LAUNDRY): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.STUDY, RoomType.STORAGE): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.STUDY, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.STUDY, RoomType.TECHNICAL_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
    (RoomType.TOILET, RoomType.CORRIDOR): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.TOILET, RoomType.ENTRANCE_HALL): AdjacencyStrength.SHOULD_BE_NEAR,
    (RoomType.TOILET, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,
}


def get_type_adjacency(type_a: RoomType, type_b: RoomType) -> Optional[AdjacencyStrength]:
    """Consulta el catalogo para un par de tipos, sin importar el orden
    (el diccionario se genero directamente de una tabla fila/columna,
    no con claves canonicamente ordenadas)."""
    return DEFAULT_TYPE_ADJACENCY.get((type_a, type_b)) or DEFAULT_TYPE_ADJACENCY.get((type_b, type_a))


def build_adjacency_requirements(rooms: List[Room]) -> List[AdjacencyRequirement]:
    """Genera automáticamente los AdjacencyRequirement que aplican a un
    conjunto de estancias, según su RoomType y el catálogo. Se aplica a
    cada par existente por TIPO (dos BEDROOM reciben la misma relación).
    Ver [ARCH:type-adjacency-catalog]."""
    requirements: List[AdjacencyRequirement] = []
    for i, room_a in enumerate(rooms):
        for room_b in rooms[i + 1:]:
            if room_a.room_type == room_b.room_type:
                continue
            type_pair_a = (room_a.room_type, room_b.room_type)
            type_pair_b = (room_b.room_type, room_a.room_type)
            if type_pair_a in CONDICIONAL_PAIRS or type_pair_b in CONDICIONAL_PAIRS:
                continue
            if type_pair_a in YA_CUBIERTO_PAIRS or type_pair_b in YA_CUBIERTO_PAIRS:
                continue

            strength = get_type_adjacency(room_a.room_type, room_b.room_type)
            if strength is not None:
                requirements.append(AdjacencyRequirement(room_a.id, room_b.id, strength))

    return requirements


def build_program_with_auto_adjacency(rooms: List[Room]) -> Program:
    """Construye un `Program` derivando sus `AdjacencyRequirement`
    automáticamente en vez de exigir declararlos a mano. Vive en
    domain/services (lógica de dominio pura, sin infraestructura). Ver
    [ARCH:type-adjacency-catalog]."""
    return Program(rooms=rooms, adjacency_requirements=build_adjacency_requirements(rooms))
