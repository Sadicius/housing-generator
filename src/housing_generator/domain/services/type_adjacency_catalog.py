"""Catalogo de 120 pares de relaciones espaciales entre tipos de estancia,
formalizado como estructura ejecutable del dominio.

Generado PROGRAMATICAMENTE desde docs/relaciones_espaciales.md (no
transcrito a mano -- fuente de errores dado el volumen). Si el
catalogo cambia en el Markdown, regenerar este archivo con el mismo
script (ver docs/architecture.md, seccion de este incremento).

Los tres huecos de modelo que bloqueaban esta formalizacion (acceso/
puertas, topologia de paso/terminal, cardinalidad) estan resueltos --
ver docs/CONTINUIDAD.md. El propio catalogo ya reclasificado a 5
categorias reales + Neutro documental + un caso especial (ver
relaciones_espaciales.md, seccion "Terminologia").

Deliberadamente OMITIDOS de este diccionario (82 entradas de las 120
pares totales):
- 35 pares "Neutro": ausencia de entrada = sin requisito generado, no
  hace falta un valor especial.
- 2 pares "Condicional" (BEDROOM/MASTER_BEDROOM x BATHROOM): NO son un
  valor estatico de tabla -- se resuelven con logica evaluada contra el
  Program real (ver BanoAccesoGeneralValidator), generar aqui un
  AdjacencyRequirement fijo seria incorrecto (depende del nº de banos
  del Program completo, no del par en si).
- 1 par "Ya cubierto" (KITCHEN-BATHROOM): ya exigido por el validador
  de nucleo humedo (ambas son is_wet) -- generar un AdjacencyRequirement
  aqui duplicaria la misma exigencia por dos caminos distintos.
"""
from typing import Dict, List, Optional, Tuple
from housing_generator.domain.entities.room import Room
from housing_generator.domain.enums import RoomType, AdjacencyStrength
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement

# Pares deliberadamente fuera de este catalogo estatico -- ver docstring
# del modulo. Se declaran aqui (no solo en un comentario) para que
# quien formalice reglas nuevas pueda comprobar programaticamente que
# un par "Condicional" no deberia tener tambien una entrada aqui.
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
    (RoomType.TOILET, RoomType.STORAGE_ROOM): AdjacencyStrength.SHOULD_BE_AWAY,}


def get_type_adjacency(type_a: RoomType, type_b: RoomType) -> Optional[AdjacencyStrength]:
    """Consulta el catalogo para un par de tipos, sin importar el orden
    (el diccionario se genero directamente de una tabla fila/columna,
    no con claves canonicamente ordenadas)."""
    return DEFAULT_TYPE_ADJACENCY.get((type_a, type_b)) or DEFAULT_TYPE_ADJACENCY.get((type_b, type_a))


def generate_adjacency_requirements(rooms: List[Room]) -> List[AdjacencyRequirement]:
    """Genera automaticamente los AdjacencyRequirement (Obligatorio y
    Preferencia) que aplican a un conjunto de estancias, segun sus
    RoomType y el catalogo formalizado.

    Se aplica a CADA PAR de estancias existentes cuyo (tipo_a, tipo_b)
    tenga entrada en el catalogo -- si un Program tiene dos BEDROOM,
    ambos reciben la misma relacion hacia, por ejemplo, BATHROOM (el
    catalogo es por TIPO, no por instancia unica). Pares del mismo tipo
    nunca generan nada (el catalogo no tiene entradas tipo-tipo consigo
    mismo: son 120 pares de tipos DISTINTOS, C(16,2)).

    No genera nada para pares CONDICIONAL_PAIRS ni YA_CUBIERTO_PAIRS
    (ver docstring del modulo) -- esos se resuelven con sus propios
    validadores, no con un AdjacencyRequirement estatico.
    """
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
