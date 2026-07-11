"""Importador de `seleccion_plantas.json` (exportacion del dashboard,
pestaña "Sección vertical") hacia un `Program` real utilizable por el
generador -- retomado de docs/CONTINUIDAD.md, ultimo pendiente real.

**[RESUELTO] Limitaciones eliminadas de raiz, no solo documentadas**: el
dashboard ahora captura CANTIDAD real (cuantas estancias de cada tipo
por planta, ya no maximo 1) y AREA real declarada por el usuario (ya no
un valor generico de relleno) -- ver `docs/architecture.md`. El formato
nuevo (`version: 2`) trae `{"type": ..., "count": ..., "area_m2": ...}`
por entrada en vez de un simple nombre de tipo. Compatibilidad hacia
atras con el formato anterior (solo nombres de tipo, sin version)
preservada -- por si existe algun `seleccion_plantas.json` exportado
antes de este cambio: en ese caso SI se sigue usando
`AREAS_POR_DEFECTO_M2` como aproximacion, exactamente como antes.

**[RESUELTO] `tipo_vivienda` conectado de verdad, no solo exportado.**
Hallazgo real de la auditoria de flujo completo: el dashboard exportaba
`tipo_vivienda` (aislada/pareada/adosada) desde hace varias rondas,
pero NINGUN sitio de Python lo leia -- elegir "adosada" en el panel
automatico no tenia ningun efecto real al generar, se perdia en
silencio. `import_seleccion_plantas` ahora tambien resuelve
`medianera_sides` a partir de ese campo, listo para pasarselo a `Lot`.
"""
import json
from pathlib import Path
from typing import Dict, FrozenSet, List, NamedTuple, Optional, Union
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, NivelPlanta, DISPLAY_NAMES
from housing_generator.domain.services.type_adjacency_catalog import generate_adjacency_requirements

# Areas por defecto, genericas -- solo se usan con el formato ANTIGUO
# (sin cantidad/area declaradas) o si una entrada del formato nuevo no
# trae area_m2 valida. NO derivadas de Tabla 1/2 (esas dependen del
# numero total de estancias del programa completo, que no se puede
# conocer de antemano sin ya haber decidido las areas).
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

# tipo_vivienda (dashboard) -> Lot.medianera_sides. "pareada" usa UN
# lado (elegido "east" por convencion propia -- el dashboard no
# pregunta orientacion real, no hay forma de saber cual lado concreto
# corresponde a la parcela real del usuario); "adosada" usa DOS lados
# opuestos (este y oeste), el patron tipico de vivienda entre
# medianeras a ambos lados. Sin sorpresas: quien necesite una
# orientacion real distinta puede construir su propio `Lot` en Python
# en vez de depender de esta convencion por defecto.
MEDIANERA_SIDES_BY_TIPO_VIVIENDA: Dict[str, FrozenSet[str]] = {
    "aislada": frozenset(),
    "pareada": frozenset({"east"}),
    "adosada": frozenset({"east", "west"}),
}


class SeleccionImportada(NamedTuple):
    """Resultado de `import_seleccion_plantas`: el `Program` real, y los
    `medianera_sides` resueltos a partir de `tipo_vivienda` -- listos
    para pasarselos directamente a `Lot(medianera_sides=...)`."""
    program: Program
    medianera_sides: FrozenSet[str]


def import_seleccion_plantas(
    source: Union[str, Path, dict],
    areas_m2: Optional[Dict[RoomType, float]] = None,
) -> SeleccionImportada:
    """Construye un `Program` real a partir del JSON exportado por el
    dashboard, y resuelve `medianera_sides` a partir de `tipo_vivienda`
    (si el JSON lo trae -- formato antiguo no lo tiene, resuelve a
    aislada/sin medianera). `source` puede ser una ruta de archivo o el
    dict ya cargado. `areas_m2` sobreescribe `AREAS_POR_DEFECTO_M2` por
    tipo, usado como respaldo si una entrada no trae area propia.

    Soporta el formato nuevo (`version: 2`, con cantidad y area reales
    por entrada) y el antiguo (lista plana de nombres de tipo, sin
    cantidad ni area -- una estancia por tipo/planta, area generica).

    Las relaciones de adyacencia del `Program` resultante se derivan
    automaticamente del catalogo formalizado
    (`generate_adjacency_requirements`), no hace falta declararlas.

    Devuelve `SeleccionImportada(program, medianera_sides)` -- ver esa
    clase para como usar `medianera_sides` con `Lot`.
    """
    if isinstance(source, (str, Path)):
        with open(source, encoding="utf-8") as f:
            payload = json.load(f)
    else:
        payload = source

    default_areas = {**AREAS_POR_DEFECTO_M2, **(areas_m2 or {})}
    rooms: List[Room] = []

    for level_name, entries in payload.get("levels", {}).items():
        level = NivelPlanta[level_name]
        for entry in entries:
            if isinstance(entry, str):
                # formato antiguo: solo el nombre de tipo, sin cantidad ni area
                type_name, count, area = entry, 1, None
            else:
                # formato nuevo: {"type": ..., "count": ..., "area_m2": ...}
                type_name = entry["type"]
                count = max(1, int(entry.get("count", 1)))
                area = entry.get("area_m2")

            room_type = RoomType[type_name]
            final_area = area if area else default_areas.get(room_type, 10.0)

            for i in range(1, count + 1):
                suffix = f"_{i}" if count > 1 else ""
                room_id = f"{type_name.lower()}_{level_name.lower()}{suffix}"
                display_name = DISPLAY_NAMES.get(room_type, room_type.value)
                if count > 1:
                    display_name = f"{display_name} {i}"
                rooms.append(Room(
                    id=room_id,
                    name=display_name,
                    room_type=room_type,
                    dimensions=Dimensions(area_m2=final_area),
                    level=level,
                ))

    adjacency = generate_adjacency_requirements(rooms)
    program = Program(rooms=rooms, adjacency_requirements=adjacency)

    tipo_vivienda = payload.get("tipo_vivienda", "aislada")
    medianera_sides = MEDIANERA_SIDES_BY_TIPO_VIVIENDA.get(tipo_vivienda, frozenset())

    return SeleccionImportada(program=program, medianera_sides=medianera_sides)
