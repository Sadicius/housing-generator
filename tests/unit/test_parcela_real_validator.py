from pathlib import Path
from shapely.geometry import box
from housing_generator.infrastructure.algorithms.constraints.parcela_real_validator import (
    ParcelaRealValidator,
)
from housing_generator.domain.entities.room import Room
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.enums import RoomType
from housing_generator.infrastructure.persistence.catastro_gml_importer import (
    importar_parcela_gml,
)


def _poligono_real_de_fixture():
    fixture = (
        Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    )
    resultado = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    return resultado.poligono


def _placed(room_id, polygon) -> Room:
    room = Room(
        id=room_id,
        name=room_id,
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=polygon.area),
    )
    room.boundary = Boundary(polygon=polygon)
    return room


def test_no_poligono_real_means_no_violations_at_all():
    # caso manual de siempre -- sin poligono_real, este validador no
    # hace nada, ningun cambio de comportamiento.
    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))
    room = _placed("a", box(5, 5, 15, 15))
    layout = Layout(lot=lot, rooms=[room], zones=[])
    result = ParcelaRealValidator().validate(layout)
    assert result.violations == []


def test_room_fully_inside_real_polygon_passes():
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real)
    # una estancia pequena, bien dentro del poligono real
    centro = poligono_real.centroid
    room_poly = box(centro.x - 1, centro.y - 1, centro.x + 1, centro.y + 1)
    assert poligono_real.contains(
        room_poly
    )  # confirmar el setup del test antes de comprobar

    room = _placed("a", room_poly)
    layout = Layout(lot=lot, rooms=[room], zones=[])
    result = ParcelaRealValidator().validate(layout)
    assert result.violations == []


def test_room_in_the_corner_gap_between_working_rectangle_and_real_polygon_fails():
    # HALLAZGO REAL que motivo este validador: el rectangulo de trabajo
    # (OBB) sobresale del poligono real en las esquinas -- una estancia
    # colocada ahi debe fallar. Se usa el rectangulo envolvente
    # completo (aun mas amplio que el OBB) para garantizar encontrar
    # una esquina que quede fuera del poligono real.
    poligono_real = _poligono_real_de_fixture()
    minx, miny, maxx, maxy = poligono_real.bounds
    lot = Lot(
        boundary=Boundary(polygon=box(minx, miny, maxx, maxy)),
        poligono_real=poligono_real,
    )

    # estancia en la esquina inferior-izquierda del rectangulo
    # envolvente -- fuera del poligono real (confirmado: solo ocupa
    # ~53% de su propio rectangulo envolvente)
    room_poly = box(minx, miny, minx + 2, miny + 2)
    assert not poligono_real.contains(room_poly)  # confirmar el setup

    room = _placed("a", room_poly)
    layout = Layout(lot=lot, rooms=[room], zones=[])
    result = ParcelaRealValidator().validate(layout)
    assert len(result.violations) == 1
    assert "fuera del área edificable real" in result.violations[0]


def test_unplaced_room_is_skipped_not_double_reported():
    # AdjacencyConstraintValidator ya reporta estancias sin colocar --
    # este validador no debe duplicar el aviso.
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real)
    room = Room(
        id="a",
        name="a",
        room_type=RoomType.LIVING_ROOM,
        dimensions=Dimensions(area_m2=10),
    )
    layout = Layout(lot=lot, rooms=[room], zones=[])
    result = ParcelaRealValidator().validate(layout)
    assert result.violations == []


def test_room_within_retranqueo_margin_of_real_polygon_fails():
    # confirma el comportamiento CORREGIDO: el validador usa
    # area_edificable_real (poligono real YA reducido por retranqueo),
    # no el poligono en bruto -- una estancia que esta DENTRO del
    # poligono real pero DENTRO del margen de retranqueo debe fallar
    # igualmente, no solo cuando sobresale del poligono en bruto.
    poligono_real = _poligono_real_de_fixture()
    lot_sin_retranqueo = Lot(
        boundary=Boundary(polygon=poligono_real), poligono_real=poligono_real
    )
    lot_con_retranqueo = Lot(
        boundary=Boundary(polygon=poligono_real),
        poligono_real=poligono_real,
        retranqueo_m=3.0,
    )

    # una estancia junto al borde del poligono real (dentro de el, pero
    # a menos de 3m del linde) -- pasa SIN retranqueo, falla CON retranqueo
    borde = list(poligono_real.exterior.coords)[0]
    hacia_dentro = poligono_real.centroid
    dx, dy = hacia_dentro.x - borde[0], hacia_dentro.y - borde[1]
    largo = (dx**2 + dy**2) ** 0.5
    punto_cercano_al_borde = (
        borde[0] + dx / largo * 1.0,
        borde[1] + dy / largo * 1.0,
    )  # 1m hacia dentro
    room_poly = box(
        punto_cercano_al_borde[0] - 0.3,
        punto_cercano_al_borde[1] - 0.3,
        punto_cercano_al_borde[0] + 0.3,
        punto_cercano_al_borde[1] + 0.3,
    )
    if not poligono_real.contains(room_poly):
        return  # geometria del punto de prueba no cayo dentro, test no aplicable esta vez

    room = _placed("a", room_poly)

    result_sin_retranqueo = ParcelaRealValidator().validate(
        Layout(lot=lot_sin_retranqueo, rooms=[room], zones=[])
    )
    result_con_retranqueo = ParcelaRealValidator().validate(
        Layout(lot=lot_con_retranqueo, rooms=[room], zones=[])
    )

    assert (
        result_sin_retranqueo.violations == []
    )  # dentro del poligono real, sin retranqueo aplicado
    assert (
        len(result_con_retranqueo.violations) == 1
    )  # dentro del margen de retranqueo -> falla
    assert "retranqueo aplicado" in result_con_retranqueo.violations[0]
