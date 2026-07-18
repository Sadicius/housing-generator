"""Enumeraciones y mapeos base del dominio de zonificacion residencial."""

from enum import Enum


class ZoneType(str, Enum):
    """Macro-zonas según grado de privacidad y horario de uso.
    CIRCULATION no es una macro-zona de uso, es la clasificación para
    estancias que sirven a varias a la vez (CORRIDOR, ENTRANCE_HALL).
    Ver [ARCH:enums].
    """

    DAY = "day"  # Social/publica: estar, comedor, cocina abierta, acceso
    NIGHT = "night"  # Privada: dormitorios, banos privados
    SERVICE = "service"  # Servicio: lavadero, trasteros, garaje, cuarto tecnico
    CIRCULATION = "circulation"  # Vestibulo/pasillo: sirve a varias zonas, no es una


class RoomType(str, Enum):
    LIVING_ROOM = "living_room"
    DINING_ROOM = "dining_room"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    BATHROOM = "bathroom"
    TOILET = "toilet"  # aseo: sin banera/ducha, min. distinto al de BATHROOM
    ENTRANCE_HALL = "entrance_hall"
    STUDY = "study"
    LAUNDRY = "laundry"
    DRYING_AREA = "drying_area"  # tendedero
    STORAGE = "storage"  # almacenamiento general (Tabla 2: despensa, ropa de cama...)
    STORAGE_ROOM = "storage_room"  # trastero (B.2.5: regla fija, objetos/trastos, distinto de almacenamiento)
    GARAGE = "garage"
    TECHNICAL_ROOM = "technical_room"
    CORRIDOR = "corridor"
    STAIRCASE = "staircase"  # escalera interior -- conecta dos plantas, huella debe alinearse entre ambas


class AdjacencyStrength(str, Enum):
    """Fuerza de un requisito de adyacencia: cerca/lejos obligatorio o
    preferente, o indiferente. SHOULD_BE_* usa una métrica distinta de
    MUST_BE_* -- ver [ARCH:enums] y `SoftConstraintScorer`."""

    MUST_BE_NEAR = "must_be_near"
    SHOULD_BE_NEAR = "should_be_near"
    INDIFFERENT = "indifferent"
    SHOULD_BE_AWAY = "should_be_away"
    MUST_BE_AWAY = "must_be_away"


# Zona por defecto por tipo, editable via Room.zone. Ver [ARCH:enums].
DEFAULT_ROOM_ZONE = {
    RoomType.LIVING_ROOM: ZoneType.DAY,
    RoomType.DINING_ROOM: ZoneType.DAY,
    RoomType.KITCHEN: ZoneType.DAY,
    RoomType.ENTRANCE_HALL: ZoneType.CIRCULATION,
    RoomType.STUDY: ZoneType.DAY,
    RoomType.CORRIDOR: ZoneType.CIRCULATION,
    RoomType.STAIRCASE: ZoneType.CIRCULATION,
    RoomType.TOILET: ZoneType.DAY,
    RoomType.BEDROOM: ZoneType.NIGHT,
    RoomType.MASTER_BEDROOM: ZoneType.NIGHT,
    RoomType.BATHROOM: ZoneType.NIGHT,
    RoomType.LAUNDRY: ZoneType.SERVICE,
    RoomType.DRYING_AREA: ZoneType.SERVICE,
    RoomType.STORAGE: ZoneType.SERVICE,
    RoomType.STORAGE_ROOM: ZoneType.SERVICE,
    RoomType.GARAGE: ZoneType.SERVICE,
    RoomType.TECHNICAL_ROOM: ZoneType.SERVICE,
}


# Locales con conexion a fontaneria/saneamiento. Ver [ARCH:enums].
DEFAULT_WET_ROOMS = {
    RoomType.KITCHEN,
    RoomType.BATHROOM,
    RoomType.TOILET,
    RoomType.LAUNDRY,
}


class SpaceCategory(str, Enum):
    """Clasificación normativa para superficie mínima: ESTANCIA (Tabla
    1), SERVICIO (Tabla 2, cocina/baño/aseo/lavadero/tendedero/
    almacenamiento), CIRCULACION (reglas de anchura), OTROS (fuera de
    Tabla 1/2). Ver [ARCH:enums]."""

    ESTANCIA = "estancia"
    SERVICIO = "servicio"
    CIRCULACION = "circulacion"
    OTROS = "otros"  # garaje, cuarto tecnico... fuera de Tabla 1 y Tabla 2


DEFAULT_SPACE_CATEGORY = {
    RoomType.LIVING_ROOM: SpaceCategory.ESTANCIA,
    RoomType.DINING_ROOM: SpaceCategory.ESTANCIA,
    RoomType.BEDROOM: SpaceCategory.ESTANCIA,
    RoomType.MASTER_BEDROOM: SpaceCategory.ESTANCIA,
    RoomType.STUDY: SpaceCategory.ESTANCIA,
    RoomType.KITCHEN: SpaceCategory.SERVICIO,
    RoomType.BATHROOM: SpaceCategory.SERVICIO,
    RoomType.TOILET: SpaceCategory.SERVICIO,
    RoomType.LAUNDRY: SpaceCategory.SERVICIO,
    RoomType.DRYING_AREA: SpaceCategory.SERVICIO,
    RoomType.STORAGE: SpaceCategory.SERVICIO,  # "almacenamiento" (Tabla 2), confirmado
    RoomType.STORAGE_ROOM: SpaceCategory.SERVICIO,  # "trastero" (B.2.5, regla fija -- NO Tabla 2)
    RoomType.ENTRANCE_HALL: SpaceCategory.CIRCULACION,
    RoomType.CORRIDOR: SpaceCategory.CIRCULACION,
    RoomType.STAIRCASE: SpaceCategory.CIRCULACION,
    RoomType.GARAGE: SpaceCategory.OTROS,  # no es pieza vividera, fuera de Tabla 1/2
    RoomType.TECHNICAL_ROOM: SpaceCategory.OTROS,
}


# Clave de Tabla 2 (A.3.2.2 / nhv.lua) para cada RoomType de categoria
# SERVICIO. Solo los tipos presentes aqui participan en la validacion de
# Tabla 2; el resto (ESTANCIA/CIRCULACION/OTROS) queda fuera por diseno.
DEFAULT_SERVICE_SUBTYPE = {
    RoomType.KITCHEN: "cocina",
    RoomType.BATHROOM: "bano",
    RoomType.TOILET: "aseo",
    RoomType.LAUNDRY: "lavadero",
    RoomType.DRYING_AREA: "tendedero",
    RoomType.STORAGE: "almacenamiento",
}


# Minimo de lados con contacto exterior real por tipo, vivienda
# UNIFAMILIAR. Confirmado caso por caso con el usuario. GARAGE=0 --
# corregido tras investigacion (sin respaldo normativo real). Ver
# [ARCH:enums].
#
# DISPLAY_NAMES debe coincidir EXACTAMENTE con DISPLAY en
# html/js/00-shared.js -- ver [ARCH:enums].
DISPLAY_NAMES = {
    RoomType.LIVING_ROOM: "Salón",
    RoomType.DINING_ROOM: "Comedor",
    RoomType.KITCHEN: "Cocina",
    RoomType.BEDROOM: "Dormitorio",
    RoomType.MASTER_BEDROOM: "Dormitorio principal",
    RoomType.BATHROOM: "Baño",
    RoomType.TOILET: "Aseo",
    RoomType.ENTRANCE_HALL: "Recibidor",
    RoomType.STUDY: "Despacho",
    RoomType.LAUNDRY: "Lavadero",
    RoomType.DRYING_AREA: "Tendedero",
    RoomType.STORAGE: "Almacén",
    RoomType.STORAGE_ROOM: "Trastero",
    RoomType.GARAGE: "Garaje",
    RoomType.TECHNICAL_ROOM: "Cuarto técnico",
    RoomType.CORRIDOR: "Pasillo",
    RoomType.STAIRCASE: "Escalera",
}

DEFAULT_MIN_EXTERIOR_SIDES = {
    RoomType.LIVING_ROOM: 1,
    RoomType.DINING_ROOM: 1,
    RoomType.KITCHEN: 1,
    RoomType.BEDROOM: 1,
    RoomType.MASTER_BEDROOM: 1,
    RoomType.BATHROOM: 0,
    RoomType.TOILET: 0,
    RoomType.ENTRANCE_HALL: 1,
    RoomType.STUDY: 1,
    RoomType.LAUNDRY: 0,
    RoomType.DRYING_AREA: 1,
    RoomType.STORAGE: 0,
    RoomType.STORAGE_ROOM: 0,
    RoomType.GARAGE: 0,
    RoomType.TECHNICAL_ROOM: 0,
    RoomType.CORRIDOR: 0,
    RoomType.STAIRCASE: 0,
}


# Niveles/plantas de una vivienda -- formaliza como enum lo que hasta
# ahora solo vivia como texto en docs/fuentes/niveles_plantas.md y en el
# dashboard (JS). SOTANO=-2 ... BAJO_CUBIERTA=4 permite comparar
# "por encima/por debajo de" con < > directamente sobre el valor.
class NivelPlanta(str, Enum):
    SOTANO = "sotano"
    SEMISOTANO = "semisotano"
    PLANTA_BAJA = "planta_baja"
    PLANTA_SUPERIOR = "planta_superior"
    BAJO_CUBIERTA = "bajo_cubierta"


# Orden vertical de abajo a arriba -- indice = posicion relativa, no un
# numero de planta real (SEMISOTANO no siempre existe entre SOTANO y
# PLANTA_BAJA, pero cuando ambos existen este es su orden correcto).
NIVEL_PLANTA_ORDEN = [
    NivelPlanta.SOTANO,
    NivelPlanta.SEMISOTANO,
    NivelPlanta.PLANTA_BAJA,
    NivelPlanta.PLANTA_SUPERIOR,
    NivelPlanta.BAJO_CUBIERTA,
]
