"""Importador de `seleccion_plantas.json` (exportacion del dashboard,
pestaña "Sección vertical") hacia un `Program` real utilizable por el
generador -- retomado de docs/CONTINUIDAD.md, ultimo pendiente real.

LIMITACION HONESTA, heredada del propio formato exportado (el dashboard
ya lo advierte en su campo "nota"): el JSON es una SELECCION DE TIPOS
por planta (que tipos de estancia hay en cada planta), no un programa
completo -- no lleva cuenta de CUANTAS estancias de cada tipo (nunca
mas de una por tipo y planta, aunque una vivienda real pueda querer
dos dormitorios en la misma planta) ni sus AREAS reales. Este
importador construye UNA `Room` por cada (tipo, planta) del JSON, con
un area por defecto razonable pero generica (`AREAS_POR_DEFECTO_M2`) --
pensada para revisar y ajustar despues, no para usar tal cual en un
proyecto real. Las relaciones de adyacencia SI se derivan del todo,
automaticamente, via el catalogo formalizado
(`generate_adjacency_requirements`) -- eso no tiene esta limitacion.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, NivelPlanta
from housing_generator.domain.services.type_adjacency_catalog import generate_adjacency_requirements

# Areas por defecto, genericas -- NO derivadas de Tabla 1/2 (esas dependen
# del numero total de estancias del programa completo, que este importador
# no puede conocer de antemano sin ya haber decidido las areas). Valores
# razonables de partida para que el Program resultante sea generable sin
# fallar por superficie insuficiente en la mayoria de casos tipicos --
# no un sustituto de revisar las areas reales del proyecto.
AREAS_POR_DEFECTO_M2: Dict[RoomType, float] = {
    RoomType.LIVING_ROOM: 25.0,
    RoomType.DINING_ROOM: 14.0,
    RoomType.KITCHEN: 10.0,
    RoomType.BEDROOM: 12.0,
    RoomType.MASTER_BEDROOM: 15.0,
    RoomType.BATHROOM: 5.5,
    RoomType.TOILET: 3.0,
    RoomType.ENTRANCE_HALL: 4.5,
    RoomType.STUDY: 9.0,
    RoomType.LAUNDRY: 3.0,
    RoomType.DRYING_AREA: 2.0,
    RoomType.STORAGE: 3.0,
    RoomType.STORAGE_ROOM: 4.0,
    RoomType.GARAGE: 18.0,
    RoomType.TECHNICAL_ROOM: 3.0,
    RoomType.CORRIDOR: 4.0,
}


def import_seleccion_plantas(
    source: Union[str, Path, dict],
    areas_m2: Optional[Dict[RoomType, float]] = None,
) -> Program:
    """Construye un `Program` real a partir del JSON exportado por el
    dashboard. `source` puede ser una ruta de archivo o el dict ya
    cargado. `areas_m2` sobreescribe `AREAS_POR_DEFECTO_M2` por tipo,
    para los casos donde el valor generico no sea razonable.

    Las relaciones de adyacencia del `Program` resultante se derivan
    automaticamente del catalogo formalizado
    (`generate_adjacency_requirements`), no hace falta declararlas.
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = source

    areas = {**AREAS_POR_DEFECTO_M2, **(areas_m2 or {})}
    rooms: List[Room] = []

    for level_name, type_names in payload.get("levels", {}).items():
        level = NivelPlanta[level_name]
        for type_name in type_names:
            room_type = RoomType[type_name]
            room_id = f"{type_name.lower()}_{level_name.lower()}"
            rooms.append(Room(
                id=room_id,
                name=room_id,
                room_type=room_type,
                dimensions=Dimensions(area_m2=areas.get(room_type, 10.0)),
                level=level,
            ))

    adjacency = generate_adjacency_requirements(rooms)
    return Program(rooms=rooms, adjacency_requirements=adjacency)
