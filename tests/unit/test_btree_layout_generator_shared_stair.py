from shapely.geometry import box
from housing_generator.application.dto.validation_result import ValidationResult
from housing_generator.domain.entities.layout import Layout
from housing_generator.domain.entities.lot import Lot
from housing_generator.domain.entities.program import Program
from housing_generator.domain.entities.room import Room
from housing_generator.domain.value_objects.adjacency import AdjacencyRequirement
from housing_generator.domain.value_objects.boundary import Boundary
from housing_generator.domain.value_objects.dimensions import Dimensions
from housing_generator.domain.enums import AdjacencyStrength, RoomType
from housing_generator.infrastructure.algorithms.adjacency.geometry_adjacency_graph_builder import (
    GeometryAdjacencyGraphBuilder,
)
from housing_generator.infrastructure.algorithms.layout_generation.btree_layout_generator import (
    BTreeLayoutGenerator,
)
from housing_generator.infrastructure.algorithms.layout_generation.soft_constraint_scorer import (
    SoftConstraintScorer,
)


class _ValidadorSiempreValido:
    def validate(self, layout):
        return ValidationResult(violations=[])


def _lot():
    return Lot(boundary=Boundary(polygon=box(0, 0, 20, 20)))


def test_stair_lands_exactly_on_the_reference_when_shape_and_area_match():
    # reference_stair no cuadrado (4m x 2m, area 8) a proposito -- si el
    # anclaje solo tradujera sin forzar la proporcion, una escalera con
    # otra forma no encajaria exactamente por mucho que se traslade.
    reference_stair = box(5, 5, 9, 7)
    program = Program(
        rooms=[
            Room(
                id="stair",
                name="Escalera",
                room_type=RoomType.STAIRCASE,
                dimensions=Dimensions(area_m2=8),
            ),
            Room(
                id="bed",
                name="Dormitorio",
                room_type=RoomType.BEDROOM,
                dimensions=Dimensions(area_m2=10),
            ),
        ]
    )
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(),
        seed=1,
        reference_stair=reference_stair,
    )
    layout = generator.generate(program, _lot(), zones=[])

    stair = next(r for r in layout.rooms if r.id == "stair")
    assert stair.boundary.polygon.equals(reference_stair)


def test_without_reference_stair_behaves_like_before():
    program = Program(
        rooms=[
            Room(
                id="stair",
                name="Escalera",
                room_type=RoomType.STAIRCASE,
                dimensions=Dimensions(area_m2=4),
            ),
            Room(
                id="bed",
                name="Dormitorio",
                room_type=RoomType.BEDROOM,
                dimensions=Dimensions(area_m2=10),
            ),
        ]
    )
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(), seed=1
    )
    layout = generator.generate(program, _lot(), zones=[])

    assert all(
        r.is_placed for r in layout.rooms
    )  # genera con normalidad, sin reference_stair


def test_floor_without_its_own_staircase_ignores_the_reference_without_crashing():
    # planta superior de un edificio de 3 (p.ej.) que ya no necesita
    # seguir subiendo -- no tiene STAIRCASE en su propio programa, pero
    # generate_building.py igualmente le pasaria el reference_stair de
    # la planta de abajo. No debe fallar ni intentar anclar nada.
    reference_stair = box(5, 5, 7, 7)
    program = Program(
        rooms=[
            Room(
                id="bed",
                name="Dormitorio",
                room_type=RoomType.BEDROOM,
                dimensions=Dimensions(area_m2=10),
            ),
        ]
    )
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(),
        seed=1,
        reference_stair=reference_stair,
    )
    layout = generator.generate(program, _lot(), zones=[])

    assert all(r.is_placed for r in layout.rooms)


def test_stair_shape_stays_locked_even_after_many_mutations():
    # con un validador que siempre aprueba, el recocido corta en la
    # primera iteracion (best_hard=0 de entrada) sin mutar nada -- para
    # probar de verdad que el anclaje sobrevive a mutaciones reales, se
    # añade una penalizacion blanda (SHOULD_BE_NEAR bed<->bath) que
    # mantiene la busqueda activa durante las max_iterations, ya que
    # rara vez llega a 0 exacto por puro azar. La escalera debe seguir
    # coincidiendo exactamente con la referencia pase lo que pase con
    # el resto del arbol.
    reference_stair = box(5, 5, 7, 7)
    program = Program(
        rooms=[
            Room(
                id="stair",
                name="Escalera",
                room_type=RoomType.STAIRCASE,
                dimensions=Dimensions(area_m2=4),
            ),
            Room(
                id="bed",
                name="Dormitorio",
                room_type=RoomType.BEDROOM,
                dimensions=Dimensions(area_m2=10),
            ),
            Room(
                id="bath",
                name="Bano",
                room_type=RoomType.BATHROOM,
                dimensions=Dimensions(area_m2=5),
            ),
        ],
        adjacency_requirements=[
            AdjacencyRequirement(
                room_a_id="bed",
                room_b_id="bath",
                strength=AdjacencyStrength.SHOULD_BE_NEAR,
            ),
        ],
    )
    soft_scorer = SoftConstraintScorer(
        program.adjacency_requirements, GeometryAdjacencyGraphBuilder()
    )
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(),
        seed=7,
        max_iterations=200,
        reference_stair=reference_stair,
        soft_constraint_scorer=soft_scorer,
    )
    layout = generator.generate(program, _lot(), zones=[])

    stair = next(r for r in layout.rooms if r.id == "stair")
    assert stair.boundary.polygon.equals(reference_stair)


def test_corner_penalty_is_smaller_in_a_corner_than_in_the_center():
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(), seed=1
    )
    lot = _lot()  # box(0, 0, 20, 20) -- esquinas en (0,0),(0,20),(20,0),(20,20)

    stair_en_esquina = Room(
        id="stair",
        name="Escalera",
        room_type=RoomType.STAIRCASE,
        dimensions=Dimensions(area_m2=4),
    )
    stair_en_esquina.boundary = Boundary(polygon=box(0, 0, 2, 2))
    layout_esquina = Layout(lot=lot, rooms=[stair_en_esquina], zones=[])
    penalty_esquina = generator._stair_corner_penalty(layout_esquina)

    stair_centrada = Room(
        id="stair",
        name="Escalera",
        room_type=RoomType.STAIRCASE,
        dimensions=Dimensions(area_m2=4),
    )
    stair_centrada.boundary = Boundary(polygon=box(9, 9, 11, 11))
    layout_centro = Layout(lot=lot, rooms=[stair_centrada], zones=[])
    penalty_centro = generator._stair_corner_penalty(layout_centro)

    assert 0.0 < penalty_esquina < penalty_centro


def test_corner_penalty_is_inert_when_stair_is_already_anchored_to_a_reference():
    # con reference_stair (planta que HEREDA la posicion, no la define),
    # la preferencia de esquina no se aplica -- ya esta decidida, nada
    # que preferir.
    reference_stair = box(5, 5, 7, 7)
    generator = BTreeLayoutGenerator(
        constraint_validator=_ValidadorSiempreValido(),
        seed=1,
        reference_stair=reference_stair,
    )
    stair_centrada = Room(
        id="stair",
        name="Escalera",
        room_type=RoomType.STAIRCASE,
        dimensions=Dimensions(area_m2=4),
    )
    stair_centrada.boundary = Boundary(polygon=box(9, 9, 11, 11))
    layout_centro = Layout(lot=_lot(), rooms=[stair_centrada], zones=[])
    _, soft, _ = generator._evaluate(layout_centro, ["stair"])
    assert soft == 0.0
