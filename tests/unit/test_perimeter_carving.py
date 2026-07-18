import pytest
from shapely.geometry import box, LineString, Polygon
from housing_generator.infrastructure.algorithms.layout_generation.perimeter_carving import (
    carve_perimeter,
)
from housing_generator.infrastructure.geometry.shapely_utils import count_exterior_sides
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType

TOLERANCIA_AREA = 0.15  # mismo criterio que AreaObjetivoValidator, NO normativo


def _room(id_, room_type, area_m2):
    return Room(
        id=id_, name=id_, room_type=room_type, dimensions=Dimensions(area_m2=area_m2)
    )


def test_empty_rooms_returns_polygon_unchanged():
    polygon = box(0, 0, 10, 10)
    bites, core = carve_perimeter(polygon, [])
    assert bites == {}
    assert core.equals(polygon)


def test_rectangular_lot_every_room_area_within_tolerance():
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
        _room("bedroom", RoomType.BEDROOM, 9),
    ]
    bites, core = carve_perimeter(polygon, rooms, entrance_side="south")

    assert set(bites.keys()) == {"entrance", "living", "kitchen", "bedroom"}
    for room in rooms:
        bite_area = bites[room.id].area
        declared = room.dimensions.area_m2
        desviacion = abs(bite_area - declared) / declared
        assert desviacion <= TOLERANCIA_AREA, f"{room.id}: {bite_area} vs {declared}"

    assert core.area > 0
    assert core.within(polygon.buffer(1e-6))


def test_rectangular_lot_every_room_touches_exterior():
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
        _room("bedroom", RoomType.BEDROOM, 9),
    ]
    bites, _ = carve_perimeter(polygon, rooms, entrance_side="south")

    for room in rooms:
        lados = count_exterior_sides(bites[room.id], polygon, 0.3)
        assert lados is not None and lados >= 1, f"{room.id}: {lados}"


def test_entrance_hall_always_on_entrance_side():
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
    ]
    bites, _ = carve_perimeter(polygon, rooms, entrance_side="north")

    entrance_bite = bites["entrance"]
    # lado norte del solar: y = 20
    north_edge = LineString([(0, 20), (20, 20)])
    assert entrance_bite.intersection(north_edge).length >= 0.3


def test_no_overlap_between_bites():
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
        _room("bedroom", RoomType.BEDROOM, 9),
        _room("study", RoomType.STUDY, 6),
    ]
    bites, _ = carve_perimeter(polygon, rooms, entrance_side="south")

    ids = list(bites.keys())
    for i, id_a in enumerate(ids):
        for id_b in ids[i + 1 :]:
            overlap = bites[id_a].intersection(bites[id_b]).area
            assert overlap < 1e-6, f"{id_a} y {id_b} se solapan en {overlap}m2"


def test_core_plus_bites_reconstructs_original_area():
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
        _room("bedroom", RoomType.BEDROOM, 9),
    ]
    bites, core = carve_perimeter(polygon, rooms, entrance_side="south")

    total_bites_area = sum(b.area for b in bites.values())
    assert total_bites_area + core.area == pytest.approx(polygon.area, rel=1e-6)


def test_generous_lot_does_not_distort_room_proportions():
    # hallazgo real de una revision visual con el usuario: con un
    # solar bastante mas grande que el programa, la v1 (banda uniforme
    # compartida por lado) repartia el area total del lado entre TODA
    # la longitud disponible, produciendo tiras absurdas (p.ej. cocina
    # 1.9x5.2m, ratio 2.7 -- por encima del maximo de
    # ProporcionMaximaValidator). v2 (profundidad variable por
    # estancia) debe mantener cada estancia dentro de una proporcion
    # razonable incluso cuando el lote tiene mucho mas perimetro del
    # que el programa necesita.
    polygon = box(0, 0, 22, 20)  # deliberadamente mucho mayor que el programa
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 22),
        _room("kitchen", RoomType.KITCHEN, 10),
        _room("master", RoomType.MASTER_BEDROOM, 14),
        _room("bedroom", RoomType.BEDROOM, 10),
    ]
    bites, _ = carve_perimeter(polygon, rooms, entrance_side="south")

    for room in rooms:
        minx, miny, maxx, maxy = bites[room.id].bounds
        w, h = maxx - minx, maxy - miny
        ratio = max(w, h) / min(w, h)
        assert ratio <= room.dimensions.max_aspect_ratio + 1e-6, (
            f"{room.id}: {w:.2f}x{h:.2f}m, ratio {ratio:.2f} supera "
            f"max_aspect_ratio ({room.dimensions.max_aspect_ratio})"
        )


def test_medianera_side_gives_no_room_its_only_exterior_contact():
    # solar adosada: medianera al este. Una estancia puede seguir
    # tocando ese borde con un lado corto (igual que en una vivienda
    # adosada real -- ver test_room_against_both_medianera_and_real_exterior_in_adosada
    # en test_exterior_contact_validator.py), pero SIEMPRE debe tener
    # contacto exterior REAL (no medianera) suficiente por otro lado --
    # eso es lo que de verdad garantiza el tallado, no "nunca tocar
    # la medianera".
    polygon = box(0, 0, 20, 20)
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
        _room("bedroom", RoomType.BEDROOM, 9),
        _room("study", RoomType.STUDY, 6),
    ]
    bites, core = carve_perimeter(
        polygon,
        rooms,
        medianera_sides=frozenset({"east"}),
        entrance_side="south",
    )

    east_edge_segment = [LineString([(20, 0), (20, 20)])]
    for room in rooms:
        lados = count_exterior_sides(
            bites[room.id],
            polygon,
            0.3,
            excluded_segments=east_edge_segment,
        )
        assert (
            lados is not None and lados >= 1
        ), f"{room.id}: {lados} lados reales (excluyendo medianera)"

    # el nucleo tambien queda estrictamente dentro del poligono de trabajo
    assert core.within(polygon.buffer(1e-6))


def test_entrance_side_falls_back_when_it_is_a_medianera():
    # entrance_side declarado en un lado que resulta ser medianera --
    # no debe fallar, se reparte igual en los lados disponibles.
    polygon = box(0, 0, 10, 10)
    rooms = [_room("entrance", RoomType.ENTRANCE_HALL, 4)]
    bites, core = carve_perimeter(
        polygon,
        rooms,
        medianera_sides=frozenset({"south", "east", "west"}),
        entrance_side="south",
    )
    assert "entrance" in bites
    north_edge = LineString([(0, 10), (10, 10)])
    assert bites["entrance"].intersection(north_edge).length >= 0.3


def test_all_sides_medianera_raises():
    polygon = box(0, 0, 10, 10)
    rooms = [_room("entrance", RoomType.ENTRANCE_HALL, 4)]
    with pytest.raises(ValueError):
        carve_perimeter(
            polygon,
            rooms,
            medianera_sides=frozenset({"north", "south", "east", "west"}),
            entrance_side="south",
        )


def test_irregular_polygon_near_cut_corner_still_meets_area_tolerance():
    # hallazgo real de una revision visual: con una esquina cortada
    # (aproxima un area_edificable_real irregular), las estancias
    # asignadas a los lados que tocan esa esquina (este/norte aqui)
    # generaban bites con hasta 28% menos area de la declarada --
    # muy por encima del +-15% NO normativo de AreaObjetivoValidator --
    # porque la profundidad de banda se calculaba con area/longitud
    # del RECTANGULO ENVOLVENTE, no con el area real ya recortada por
    # el poligono. carve_perimeter debe calibrar la profundidad contra
    # el area real (biseccion), no solo dividir.
    irregular = Polygon(
        [(0, 0), (16, 0), (16, 11), (11, 16), (0, 16)]
    )  # esquina NE cortada
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room(
            "living", RoomType.LIVING_ROOM, 20
        ),  # cae en el lado este, junto al corte
        _room("kitchen", RoomType.KITCHEN, 10),  # lado oeste, lejos del corte
        _room(
            "master", RoomType.MASTER_BEDROOM, 13
        ),  # cae en el lado norte, junto al corte
    ]
    bites, _ = carve_perimeter(irregular, rooms, entrance_side="south")

    for room in rooms:
        bite_area = bites[room.id].area
        declared = room.dimensions.area_m2
        desviacion = abs(bite_area - declared) / declared
        assert desviacion <= TOLERANCIA_AREA, (
            f"{room.id}: {bite_area:.2f}m2 generado vs {declared}m2 declarado "
            f"({desviacion*100:.0f}% de desviacion)"
        )


def test_irregular_polygon_bites_stay_inside_real_boundary():
    # area_edificable_real irregular: un pentagono con una esquina
    # cortada (aproxima una parcela real no rectangular). El
    # rectangulo envolvente sobresale de esta forma -- confirma que
    # los bites se recortan contra el poligono real, no solo la bbox.
    irregular = Polygon([(0, 0), (20, 0), (20, 15), (15, 20), (0, 20)])
    rooms = [
        _room("entrance", RoomType.ENTRANCE_HALL, 4),
        _room("living", RoomType.LIVING_ROOM, 16),
        _room("kitchen", RoomType.KITCHEN, 9),
    ]
    bites, core = carve_perimeter(irregular, rooms, entrance_side="south")

    for room_id, bite in bites.items():
        assert bite.within(irregular.buffer(1e-6)), f"{room_id} sale del poligono real"
    assert core.within(irregular.buffer(1e-6))
