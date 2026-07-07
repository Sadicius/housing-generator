from typing import List, Dict
from shapely.geometry import Polygon, box
from housing_generator.application.ports.layout_generator_port import LayoutGeneratorPort
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.zone import Zone
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import ZoneType

# Orden de las zonas a lo largo del eje de "profundidad", desde la fachada/
# acceso hacia el interior, siguiendo el gradiente de privacidad
# dia -> noche -> servicio habitual en vivienda residencial.
_ZONE_ORDER = [ZoneType.DAY, ZoneType.NIGHT, ZoneType.SERVICE]


class GraphBasedLayoutGenerator(LayoutGeneratorPort):
    """Generador de particionado (slicing) simplificado:

    1. Divide el solar en franjas horizontales, una por zona, con tamano
       proporcional al area total de estancias de cada zona (paso de
       diagrama de zonificacion).
    2. Dentro de cada franja de zona, vuelve a dividir en cajas por
       estancia, proporcional al area solicitada de cada una (paso de
       traduccion diagrama de burbujas -> planta).

    Es deliberadamente simple para que sea facil de testear y entender,
    y para poder sustituirlo despues por un generador basado en resolucion
    de restricciones (CSP) o en un algoritmo genetico que implemente el
    mismo LayoutGeneratorPort sin tocar el resto del sistema.
    """

    def generate(self, program: Program, lot: Lot, zones: List[Zone]) -> Layout:
        minx, miny, maxx, maxy = lot.boundary.polygon.bounds
        total_height = maxy - miny

        ordered_zones = sorted(
            zones,
            key=lambda z: _ZONE_ORDER.index(z.zone_type) if z.zone_type in _ZONE_ORDER else 99,
        )

        zone_areas: Dict[ZoneType, float] = {
            zone.zone_type: sum(
                program.room_by_id(rid).dimensions.area_m2 for rid in zone.room_ids
            )
            for zone in ordered_zones
        }
        total_area = sum(zone_areas.values()) or 1.0

        placed_rooms = list(program.rooms)
        rooms_by_id = {r.id: r for r in placed_rooms}

        cursor_y = miny
        for zone in ordered_zones:
            zone_height = total_height * (zone_areas[zone.zone_type] / total_area)
            zone_box = box(minx, cursor_y, maxx, cursor_y + zone_height)
            zone.boundary = Boundary(polygon=zone_box)

            self._place_rooms_in_zone(zone, zone_box, rooms_by_id)
            cursor_y += zone_height

        return Layout(lot=lot, rooms=placed_rooms, zones=ordered_zones)

    def _place_rooms_in_zone(self, zone: Zone, zone_box: Polygon, rooms_by_id: Dict) -> None:
        minx, miny, maxx, maxy = zone_box.bounds
        zone_width = maxx - minx
        zone_rooms = [rooms_by_id[rid] for rid in zone.room_ids]

        # Heuristica para nucleo humedo: las estancias humedas se colocan
        # PRIMERO (extremo izquierdo) dentro de su zona. Como las zonas se
        # apilan verticalmente en el mismo orden de X, esto alinea las
        # estancias humedas de zonas contiguas (p.ej. cocina en dia,
        # bano en noche) en la misma columna, maximizando la probabilidad
        # de que compartan pared real -- sin esto, cada zona particiona su
        # ancho de forma independiente y las estancias humedas casi nunca
        # coinciden en X. Es una heuristica de orden, no una garantia: con
        # 3+ estancias humedas repartidas en zonas NO mutuamente contiguas
        # (dia y servicio nunca se tocan directamente, solo a traves de
        # noche) sigue siendo geometricamente imposible que todas queden a
        # distancia <=1 entre si -- eso requeriria cambiar la topologia de
        # zonificacion (que dia/noche/servicio se toquen entre si en un
        # punto comun), no solo el orden de colocacion.
        zone_rooms = sorted(zone_rooms, key=lambda r: not r.is_wet)

        total_area = sum(r.dimensions.area_m2 for r in zone_rooms) or 1.0

        cursor_x = minx
        for room in zone_rooms:
            share = room.dimensions.area_m2 / total_area
            width = zone_width * share
            room_box = box(cursor_x, miny, cursor_x + width, maxy)
            room.boundary = Boundary(polygon=room_box)
            cursor_x += width
