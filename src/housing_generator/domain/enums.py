"""Enumeraciones y mapeos base del dominio de zonificacion residencial."""
from enum import Enum


class ZoneType(str, Enum):
    """Macro-zonas segun grado de privacidad y horario de uso.

    Es la division clasica que emplea el diseno residencial: social/dia,
    privada/noche y de servicio. CIRCULATION es distinta de las otras
    tres: no es una macro-zona de uso, es la clasificacion honesta para
    estancias que no pertenecen a ninguna (ver mas abajo, CORRIDOR y
    ENTRANCE_HALL) -- una circulacion sirve a varias zonas a la vez, y
    forzarla a DAY por defecto era un dato falso (encontrado en
    auditoria: generaba violaciones falsas de zonificacion cuando un
    pasillo servia correctamente a la zona noche).
    """
    DAY = "day"          # Social/publica: estar, comedor, cocina abierta, acceso
    NIGHT = "night"       # Privada: dormitorios, banos privados
    SERVICE = "service"   # Servicio: lavadero, trasteros, garaje, cuarto tecnico
    CIRCULATION = "circulation"  # Vestibulo/pasillo: sirve a varias zonas, no es una


class RoomType(str, Enum):
    LIVING_ROOM = "living_room"
    DINING_ROOM = "dining_room"
    KITCHEN = "kitchen"
    BEDROOM = "bedroom"
    MASTER_BEDROOM = "master_bedroom"
    BATHROOM = "bathroom"
    TOILET = "toilet"              # aseo: sin banera/ducha, min. distinto al de BATHROOM
    ENTRANCE_HALL = "entrance_hall"
    STUDY = "study"
    LAUNDRY = "laundry"
    DRYING_AREA = "drying_area"    # tendedero
    STORAGE = "storage"            # almacenamiento general (Tabla 2: despensa, ropa de cama...)
    STORAGE_ROOM = "storage_room"  # trastero (B.2.5: regla fija, objetos/trastos, distinto de almacenamiento)
    GARAGE = "garage"
    TECHNICAL_ROOM = "technical_room"
    CORRIDOR = "corridor"


class AdjacencyStrength(str, Enum):
    """Fuerza de un requisito de adyacencia, siguiendo la matriz clasica
    'debe estar cerca / deberia estar cerca / indiferente / debe estar lejos'."""
    MUST_BE_NEAR = "must_be_near"
    SHOULD_BE_NEAR = "should_be_near"
    INDIFFERENT = "indifferent"
    MUST_BE_AWAY = "must_be_away"


# Zona por defecto de cada tipo de estancia, editable por el llamador
# (Room.zone se puede sobreescribir explicitamente).
# CORRIDOR y ENTRANCE_HALL -> CIRCULATION, no DAY: son circulacion, no
# pertenecen a una macro-zona de uso (ver ZoneType.CIRCULATION arriba).
# TOILET -> DAY: es un supuesto de diseno (aseo de cortesia, tipicamente
# cerca del acceso/zona dia para visitas), no una regla normativa -- si
# tu programa necesita un aseo en zona noche, sobreescribe `zone` a mano.
DEFAULT_ROOM_ZONE = {
    RoomType.LIVING_ROOM: ZoneType.DAY,
    RoomType.DINING_ROOM: ZoneType.DAY,
    RoomType.KITCHEN: ZoneType.DAY,
    RoomType.ENTRANCE_HALL: ZoneType.CIRCULATION,
    RoomType.STUDY: ZoneType.DAY,
    RoomType.CORRIDOR: ZoneType.CIRCULATION,
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


# "Local humedo": estancias con conexion a fontaneria/saneamiento (agua
# corriente + desague). Confirmado por normativa (CTE DB-HS distingue
# "locales secos" de "locales humedos": cocinas, banos, aseos) y por
# practica de proyecto de fontaneria (cada local humedo lleva su propia
# llave de corte independiente: banos, aseos, cocinas, cuartos de lavado).
# `tendedero` se deja fuera por defecto: normalmente es prolongacion del
# lavadero sin desague propio, no un punto de agua independiente.
DEFAULT_WET_ROOMS = {
    RoomType.KITCHEN,
    RoomType.BATHROOM,
    RoomType.TOILET,
    RoomType.LAUNDRY,
}


class SpaceCategory(str, Enum):
    """Clasificacion normativa para superficie minima (Tabla 1 vs Tabla 2):
    que cuenta como "estancia" (Tabla 1: pieza habitable sin instalaciones
    propias -- estar, comedor, dormitorios, despacho) frente a "servicio"
    (Tabla 2: cocina, bano, aseo, lavadero, tendedero, almacenamiento --
    escalan con el numero de estancias, no por puesto de tamano) y
    "circulacion" (vestibulo/pasillo: reglas de anchura, no de superficie).
    Confirmado contra Decreto 29/2010 (Galicia) y normativas municipales:
    cocina es "pieza vividera" (categoria A.1.1, luz/exterior) pero NO es
    "estancia" a efectos de Tabla 1 -- son dos clasificaciones distintas.
    """
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
    RoomType.GARAGE: SpaceCategory.OTROS,        # regla propia B.2.6, no Tabla 1/2
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


# Minimo de lados con contacto real al exterior por tipo de estancia
# (vivienda UNIFAMILIAR -- en bloque de viviendas ENTRANCE_HALL daria al
# nucleo de comunicaciones, no al exterior real). Confirmado caso por
# caso con el usuario, no derivado automaticamente de SpaceCategory --
# BATHROOM y TOILET admiten ventilacion mecanica (0), pero DRYING_AREA
# exige ventilacion natural directa (1) pese a ser tambien "servicio".
# TECHNICAL_ROOM: 0 exigido, aunque por comodidad de acceso tecnico se
# prefiera 1 en la practica -- eso es preferencia de diseno, no regla.
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
    RoomType.GARAGE: 1,
    RoomType.TECHNICAL_ROOM: 0,
    RoomType.CORRIDOR: 0,
}
