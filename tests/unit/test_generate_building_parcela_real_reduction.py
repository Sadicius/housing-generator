import pytest
from pathlib import Path
from housing_generator.application.use_cases.generate_building import (
    GenerateBuildingUseCase,
)
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import RoomType, NivelPlanta
from housing_generator.infrastructure.persistence.catastro_gml_importer import (
    importar_parcela_gml,
)


def _poligono_real_de_fixture():
    # misma parcela real usada en test_lot.py/test_catastro_gml_importer.py --
    # 349.2m2, genuinamente irregular.
    fixture = (
        Path(__file__).parents[1] / "fixtures" / "catastro" / "parcela_sin_edificar.gml"
    )
    resultado = importar_parcela_gml(fixture.read_text(encoding="utf-8"))
    return resultado.poligono


class _ValidadorSiempreValido:
    def validate(self, layout):
        return ValidationResult(violations=[])


class _ZonificacionVacia:
    def build_zones(self, program):
        return []


class _GeneradorDeMentira:
    """No coloca geometria real -- solo captura el `lot` recibido
    (sera `floor_lot`) para poder inspeccionar despues que
    ParcelaRealValidator reciba el poligono correcto. Suficiente
    porque el validador compuesto de este test siempre aprueba, no
    hace falta geometria real de estancias."""

    def generate(self, program, lot, zones):
        return Layout(lot=lot, rooms=list(program.rooms), zones=[])


def _use_case():
    return GenerateBuildingUseCase(
        per_floor_validators_factory=lambda *a: _ValidadorSiempreValido(),
        layout_generator_factory=lambda *a: _GeneradorDeMentira(),
        zoning_strategy=_ZonificacionVacia(),
        programa_minimo_validator=_ValidadorSiempreValido(),
        bano_acceso_validator=_ValidadorSiempreValido(),
    )


def _room(room_id, level):
    return Room(
        id=room_id,
        name=room_id,
        room_type=RoomType.BEDROOM,
        dimensions=Dimensions(area_m2=10),
        level=level,
    )


def test_floor_lot_uses_the_retranqueo_reduced_polygon_not_the_raw_one():
    # Bug real corregido: floor_lot pasaba lot.poligono_real SIN reducir
    # a ParcelaRealValidator (via layout.lot), perdiendo por completo el
    # retranqueo declarado para toda parcela importada -- confirmado
    # reproduciendo con esta misma fixture (154.0m2 esperados vs 349.2m2,
    # el poligono crudo). Aqui se comprueba directamente que
    # floor_lot.area_edificable_real (lo que ParcelaRealValidator usa de
    # verdad) coincide con el area YA reducida del lot original.
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(
        boundary=Boundary(polygon=poligono_real),
        poligono_real=poligono_real,
        retranqueo_m=3.0,
    )
    area_reducida_esperada = lot.area_edificable_real.polygon.area
    assert (
        area_reducida_esperada < poligono_real.area
    )  # confirma que la reduccion es real, no un no-op

    program = Program(rooms=[_room("bed", NivelPlanta.PLANTA_BAJA)])
    building = _use_case().execute(program, lot)
    floor_lot = building.floors[NivelPlanta.PLANTA_BAJA].lot

    assert floor_lot.poligono_real is not None
    assert floor_lot.area_edificable_real.polygon.area == pytest.approx(
        area_reducida_esperada
    )
    assert (
        floor_lot.area_edificable_real.polygon.area < poligono_real.area
    )  # nunca el crudo sin reducir


def test_floor_lot_real_boundary_shrinks_progressively_across_floors():
    poligono_real = _poligono_real_de_fixture()
    lot = Lot(
        boundary=Boundary(polygon=poligono_real),
        poligono_real=poligono_real,
        retranqueo_m=1.0,
        retranqueo_incremento_por_planta_m=1.0,
    )
    program = Program(
        rooms=[
            _room("bed_pb", NivelPlanta.PLANTA_BAJA),
            _room("bed_ps", NivelPlanta.PLANTA_SUPERIOR),
        ]
    )

    building = _use_case().execute(program, lot)
    area_pb = building.floors[
        NivelPlanta.PLANTA_BAJA
    ].lot.area_edificable_real.polygon.area
    area_ps = building.floors[
        NivelPlanta.PLANTA_SUPERIOR
    ].lot.area_edificable_real.polygon.area

    assert (
        area_ps < area_pb
    )  # planta superior: el mismo encogimiento progresivo que el rectangulo de trabajo


def test_floor_lot_without_poligono_real_is_unaffected():
    from shapely.geometry import box

    lot = Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)), retranqueo_m=2.0)
    program = Program(rooms=[_room("bed", NivelPlanta.PLANTA_BAJA)])

    building = _use_case().execute(program, lot)
    floor_lot = building.floors[NivelPlanta.PLANTA_BAJA].lot

    assert floor_lot.poligono_real is None  # caso manual de siempre, sin cambios
